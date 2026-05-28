#!/usr/bin/env python3
"""Generate a placeholder asset pack from a visual profile assets manifest."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True, slots=True)
class AssetEntry:
    """Normalized manifest asset entry."""

    asset_id: str
    kind: str
    relative_path: Path
    size: tuple[int, int]
    tags: tuple[str, ...]
    draw_layer: str


_CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "boundary": (40, 64, 38),
    "decor": (102, 82, 51),
    "dirt": (126, 91, 54),
    "elevation": (120, 114, 93),
    "forest": (35, 89, 47),
    "grass": (79, 122, 63),
    "place": (113, 94, 64),
    "road": (131, 104, 68),
    "ruins": (112, 110, 100),
    "runtime": (116, 86, 59),
    "swamp": (53, 95, 85),
    "tile": (90, 90, 90),
    "water": (45, 91, 128),
    "debug": (164, 48, 48),
    "missing": (180, 44, 90),
}


def _read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object from a file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _as_size(value: Any) -> tuple[int, int]:
    """Return a safe two-dimensional size tuple."""
    if not isinstance(value, list) or len(value) != 2:
        return (16, 16)
    width = value[0] if isinstance(value[0], int) and value[0] > 0 else 16
    height = value[1] if isinstance(value[1], int) and value[1] > 0 else 16
    return (width, height)


def _as_tags(value: Any) -> tuple[str, ...]:
    """Return a tuple of string tags."""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _asset_root(profile_dir: Path, manifest: dict[str, Any], override: Path | None) -> Path:
    """Resolve the asset root directory."""
    if override is not None:
        return override
    raw_root = manifest.get("asset_root")
    if isinstance(raw_root, str) and raw_root:
        root = Path(raw_root)
        if root.is_absolute():
            return root
        return (profile_dir / root).resolve()
    return (profile_dir / "assets").resolve()


def _normalize_entries(manifest: dict[str, Any]) -> list[AssetEntry]:
    """Normalize tile and sprite entries from a manifest."""
    entries: list[AssetEntry] = []
    for kind, key in (("tile", "tiles"), ("sprite", "sprites")):
        raw_items = manifest.get(key)
        if not isinstance(raw_items, dict):
            continue
        for asset_id, raw_entry in sorted(raw_items.items()):
            if not isinstance(asset_id, str) or not isinstance(raw_entry, dict):
                continue
            path = raw_entry.get("path")
            if not isinstance(path, str) or not path:
                continue
            entries.append(
                AssetEntry(
                    asset_id=asset_id,
                    kind=kind,
                    relative_path=Path(path),
                    size=_as_size(raw_entry.get("size")),
                    tags=_as_tags(raw_entry.get("tags")),
                    draw_layer="tile" if kind == "tile" else str(raw_entry.get("draw_layer", "sprite")),
                )
            )
    return entries


def _category_for(entry: AssetEntry) -> str:
    """Return the display category for an asset entry."""
    if entry.tags:
        return entry.tags[0]
    if "." in entry.asset_id:
        return entry.asset_id.split(".", 1)[0]
    return entry.kind


def _text_code(asset_id: str) -> str:
    """Build a short readable placeholder label."""
    tail = asset_id.split(".")[-1]
    parts = [part for part in tail.replace("-", "_").split("_") if part]
    if not parts:
        return asset_id[:4].upper()
    code = "".join(part[0] for part in parts[:4]).upper()
    return code[:4]


def _color_for(entry: AssetEntry) -> tuple[int, int, int]:
    """Return a deterministic color for an asset entry."""
    category = _category_for(entry)
    base = _CATEGORY_COLORS.get(category, _CATEGORY_COLORS.get(entry.kind, (96, 96, 96)))
    jitter = sum(ord(ch) for ch in entry.asset_id) % 31 - 15
    return tuple(max(0, min(255, channel + jitter)) for channel in base)


def _draw_placeholder(path: Path, entry: AssetEntry, *, overwrite: bool) -> bool:
    """Draw a PNG placeholder asset.

    Args:
        path: Destination PNG path.
        entry: Asset metadata.
        overwrite: Whether existing files may be overwritten.

    Returns:
        True if a file was written, False otherwise.
    """
    if path.exists() and not overwrite:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = entry.size
    base_color = _color_for(entry)
    image = Image.new("RGBA", (width, height), base_color + (255,))
    draw = ImageDraw.Draw(image)
    border = (max(0, base_color[0] - 35), max(0, base_color[1] - 35), max(0, base_color[2] - 35), 255)
    highlight = (min(255, base_color[0] + 45), min(255, base_color[1] + 45), min(255, base_color[2] + 45), 255)

    draw.rectangle((0, 0, width - 1, height - 1), outline=border)
    if width >= 8 and height >= 8:
        draw.line((1, 1, width - 2, height - 2), fill=highlight)
        draw.line((1, height - 2, width - 2, 1), fill=border)

    code = _text_code(entry.asset_id)
    if width >= 16 and height >= 16:
        font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), code, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = max(1, (width - text_width) // 2)
        text_y = max(1, (height - text_height) // 2)
        draw.rectangle(
            (text_x - 1, text_y - 1, text_x + text_width + 1, text_y + text_height + 1),
            fill=(0, 0, 0, 115),
        )
        draw.text((text_x, text_y), code, fill=(245, 245, 230, 255), font=font)

    image.save(path)
    return True


def generate_asset_pack(profile_dir: Path, *, asset_root: Path | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Generate placeholder PNG assets for all manifest entries.

    Args:
        profile_dir: Visual profile directory.
        asset_root: Optional asset root override.
        overwrite: Whether existing PNG files may be overwritten.

    Returns:
        JSON-serializable generation report.
    """
    manifest_path = profile_dir / "assets_manifest.json"
    manifest = _read_json_object(manifest_path)
    resolved_root = _asset_root(profile_dir, manifest, asset_root)
    entries = _normalize_entries(manifest)

    written: list[str] = []
    skipped: list[str] = []
    for entry in entries:
        target = resolved_root / entry.relative_path
        if _draw_placeholder(target, entry, overwrite=overwrite):
            written.append(str(target))
        else:
            skipped.append(str(target))

    report = {
        "schema_version": "asset-pack-generation-report-v1",
        "profile": manifest.get("profile", profile_dir.name),
        "asset_root": str(resolved_root),
        "manifest": str(manifest_path),
        "entries_total": len(entries),
        "written": len(written),
        "skipped_existing": len(skipped),
        "written_files": written[:50],
        "skipped_files": skipped[:50],
    }
    report_path = resolved_root / "asset_pack_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate placeholder PNG assets for a visual profile.")
    parser.add_argument(
        "profile_dir",
        nargs="?",
        default="top_down_visualgen/profiles/dark_forest",
        help="Visual profile directory.",
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=None,
        help="Override asset root directory. Defaults to assets_manifest.asset_root.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing asset files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run placeholder asset pack generation."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = generate_asset_pack(Path(args.profile_dir), asset_root=args.asset_root, overwrite=args.overwrite)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Asset pack generation: FAILED: {exc}", file=sys.stderr)
        return 1

    print("Asset pack generation: OK")
    print(f"  profile:  {report['profile']}")
    print(f"  root:     {report['asset_root']}")
    print(f"  entries:  {report['entries_total']}")
    print(f"  written:  {report['written']}")
    print(f"  skipped:  {report['skipped_existing']}")
    print(f"  report:   {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
