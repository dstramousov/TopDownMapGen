#!/usr/bin/env python3
"""Generate JSON and HTML previews for a visual profile asset registry."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """Single normalized asset registry entry."""

    asset_id: str
    kind: str
    path: str
    size: list[int]
    draw_layer: str
    tags: list[str]
    asset_status: str
    file_exists: bool = False
    asset_file: str | None = None
    preview_src: str | None = None
    pivot: list[int] | None = None
    sort_anchor: list[int] | None = None


def _read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If the file does not contain a JSON object.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _as_str_list(value: Any) -> list[str]:
    """Convert a JSON value to a string list when possible."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_int_pair(value: Any) -> list[int]:
    """Convert a JSON value to an integer pair when possible."""
    if not isinstance(value, list) or len(value) != 2:
        return [0, 0]
    result: list[int] = []
    for item in value:
        result.append(item if isinstance(item, int) else 0)
    return result


def _entry_category(entry: RegistryEntry) -> str:
    """Return a stable display category for an entry."""
    if entry.tags:
        return entry.tags[0]
    if "." in entry.asset_id:
        return entry.asset_id.split(".", 1)[0]
    return "uncategorized"




def _resolve_asset_root(profile_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve the filesystem root used for referenced asset files."""
    raw_root = manifest.get("asset_root")
    if isinstance(raw_root, str) and raw_root:
        root = Path(raw_root)
        if root.is_absolute():
            return root
        return (profile_dir / root).resolve()
    return profile_dir.resolve()


def _resolve_asset_path(asset_root: Path, relative_path: str) -> Path:
    """Resolve a manifest asset path against the configured asset root."""
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return asset_root / path


def _preview_src(asset_path: Path, output_dir: Path | None) -> str | None:
    """Return an HTML-friendly preview src for an existing asset file."""
    if output_dir is None or not asset_path.exists():
        return None
    return os.path.relpath(asset_path, output_dir)


def _normalize_entries(manifest: dict[str, Any], profile_dir: Path, output_dir: Path | None = None) -> list[RegistryEntry]:
    """Normalize tile and sprite mappings into registry entries."""
    entries: list[RegistryEntry] = []
    asset_root = _resolve_asset_root(profile_dir, manifest)
    tiles = manifest.get("tiles")
    if isinstance(tiles, dict):
        for asset_id, raw_entry in sorted(tiles.items()):
            if not isinstance(asset_id, str) or not isinstance(raw_entry, dict):
                continue
            raw_path = str(raw_entry.get("path", ""))
            asset_path = _resolve_asset_path(asset_root, raw_path)
            entries.append(
                RegistryEntry(
                    asset_id=asset_id,
                    kind="tile",
                    path=raw_path,
                    size=_as_int_pair(raw_entry.get("size")),
                    draw_layer="tile",
                    tags=_as_str_list(raw_entry.get("tags")),
                    asset_status=str(raw_entry.get("asset_status", "unknown")),
                    file_exists=asset_path.exists(),
                    asset_file=str(asset_path),
                    preview_src=_preview_src(asset_path, output_dir),
                )
            )

    sprites = manifest.get("sprites")
    if isinstance(sprites, dict):
        for asset_id, raw_entry in sorted(sprites.items()):
            if not isinstance(asset_id, str) or not isinstance(raw_entry, dict):
                continue
            raw_path = str(raw_entry.get("path", ""))
            asset_path = _resolve_asset_path(asset_root, raw_path)
            entries.append(
                RegistryEntry(
                    asset_id=asset_id,
                    kind="sprite",
                    path=raw_path,
                    size=_as_int_pair(raw_entry.get("size")),
                    draw_layer=str(raw_entry.get("draw_layer", "")),
                    tags=_as_str_list(raw_entry.get("tags")),
                    asset_status=str(raw_entry.get("asset_status", "unknown")),
                    file_exists=asset_path.exists(),
                    asset_file=str(asset_path),
                    preview_src=_preview_src(asset_path, output_dir),
                    pivot=_as_int_pair(raw_entry.get("pivot")),
                    sort_anchor=_as_int_pair(raw_entry.get("sort_anchor")),
                )
            )
    return entries


def build_registry_report(profile_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Build an asset registry report from a visual profile.

    Args:
        profile_dir: Visual profile directory.
        output_dir: Optional output directory used to compute relative image paths.

    Returns:
        JSON-serializable registry report.
    """
    manifest_path = profile_dir / "assets_manifest.json"
    manifest = _read_json_object(manifest_path)
    entries = _normalize_entries(manifest, profile_dir, output_dir)

    by_kind: Counter[str] = Counter(entry.kind for entry in entries)
    by_category: Counter[str] = Counter(_entry_category(entry) for entry in entries)
    by_draw_layer: Counter[str] = Counter(entry.draw_layer for entry in entries if entry.kind == "sprite")
    by_status: Counter[str] = Counter(entry.asset_status for entry in entries)
    by_file_status: Counter[str] = Counter("present" if entry.file_exists else "missing" for entry in entries)
    by_tag: Counter[str] = Counter(tag for entry in entries for tag in entry.tags)

    serialized_entries = [
        {
            "id": entry.asset_id,
            "kind": entry.kind,
            "category": _entry_category(entry),
            "path": entry.path,
            "size": entry.size,
            "pivot": entry.pivot,
            "sort_anchor": entry.sort_anchor,
            "draw_layer": entry.draw_layer,
            "tags": entry.tags,
            "asset_status": entry.asset_status,
            "file_exists": entry.file_exists,
            "asset_file": entry.asset_file,
            "preview_src": entry.preview_src,
        }
        for entry in entries
    ]

    return {
        "schema_version": "asset-registry-report-v1",
        "profile": manifest.get("profile", profile_dir.name),
        "world_style": manifest.get("world_style", "unknown"),
        "source_manifest": str(manifest_path),
        "asset_root": str(_resolve_asset_root(profile_dir, manifest)),
        "summary": {
            "total_entries": len(entries),
            "tiles": by_kind.get("tile", 0),
            "sprites": by_kind.get("sprite", 0),
        },
        "by_kind": dict(sorted(by_kind.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_draw_layer": dict(sorted(by_draw_layer.items())),
        "by_asset_status": dict(sorted(by_status.items())),
        "by_file_status": dict(sorted(by_file_status.items())),
        "top_tags": [
            {"tag": tag, "count": count}
            for tag, count in by_tag.most_common(20)
        ],
        "entries": serialized_entries,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON file with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _html_table(entries: list[dict[str, Any]]) -> str:
    """Render registry entries as an HTML table."""
    rows: list[str] = []
    for entry in entries:
        tags = ", ".join(str(tag) for tag in entry.get("tags", []))
        preview_src = entry.get("preview_src")
        if isinstance(preview_src, str) and preview_src:
            preview = f'<img class="asset" src="{html.escape(preview_src)}" alt="{html.escape(str(entry.get("id", "")))}">'
        else:
            preview = '<span class="missing">missing</span>'
        size = "×".join(str(item) for item in entry.get("size", []))
        pivot = entry.get("pivot")
        anchor = entry.get("sort_anchor")
        pivot_text = "—" if pivot is None else ",".join(str(item) for item in pivot)
        anchor_text = "—" if anchor is None else ",".join(str(item) for item in anchor)
        rows.append(
            "<tr>"
            f"<td>{preview}</td>"
            f"<td><code>{html.escape(str(entry.get('id', '')))}</code></td>"
            f"<td>{html.escape(str(entry.get('kind', '')))}</td>"
            f"<td>{html.escape(str(entry.get('category', '')))}</td>"
            f"<td>{html.escape(str(entry.get('draw_layer', '')))}</td>"
            f"<td>{html.escape(size)}</td>"
            f"<td>{html.escape(pivot_text)}</td>"
            f"<td>{html.escape(anchor_text)}</td>"
            f"<td>{html.escape(str(entry.get('asset_status', '')))}</td>"
            f"<td>{'yes' if entry.get('file_exists') else 'no'}</td>"
            f"<td><code>{html.escape(str(entry.get('path', '')))}</code></td>"
            f"<td>{html.escape(tags)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _counter_list(title: str, data: dict[str, Any]) -> str:
    """Render a compact counter block."""
    items = "".join(
        f"<li><span>{html.escape(str(key))}</span><strong>{html.escape(str(value))}</strong></li>"
        for key, value in sorted(data.items())
    )
    return f"<section><h2>{html.escape(title)}</h2><ul class=\"counters\">{items}</ul></section>"


def render_html_report(report: dict[str, Any]) -> str:
    """Render the asset registry report as standalone HTML."""
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    entries = report.get("entries") if isinstance(report.get("entries"), list) else []
    by_category = report.get("by_category") if isinstance(report.get("by_category"), dict) else {}
    by_draw_layer = report.get("by_draw_layer") if isinstance(report.get("by_draw_layer"), dict) else {}
    by_status = report.get("by_asset_status") if isinstance(report.get("by_asset_status"), dict) else {}
    top_tags = report.get("top_tags") if isinstance(report.get("top_tags"), list) else []
    tag_items = "".join(
        f"<li><span>{html.escape(str(item.get('tag', '')))}</span><strong>{html.escape(str(item.get('count', '')))}</strong></li>"
        for item in top_tags
        if isinstance(item, dict)
    )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Asset Registry Preview — {html.escape(str(report.get('profile', 'unknown')))}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #1f2933; background: #f7f7f4; }}
    h1 {{ margin-bottom: 4px; }}
    .subtitle {{ color: #52606d; margin-top: 0; }}
    .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 20px 0; }}
    .card {{ background: #fff; border: 1px solid #d9e2ec; border-radius: 12px; padding: 14px 18px; min-width: 140px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04); }}
    .card strong {{ display: block; font-size: 28px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-bottom: 24px; }}
    section {{ background: #fff; border: 1px solid #d9e2ec; border-radius: 12px; padding: 12px 16px; }}
    .counters {{ list-style: none; padding: 0; margin: 0; }}
    .counters li {{ display: flex; justify-content: space-between; border-bottom: 1px solid #eef2f7; padding: 5px 0; gap: 16px; }}
    .counters li:last-child {{ border-bottom: 0; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e2ec; border-radius: 12px; overflow: hidden; }}
    th, td {{ text-align: left; border-bottom: 1px solid #eef2f7; padding: 7px 9px; font-size: 13px; vertical-align: top; }}
    th {{ background: #e4e7eb; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    img.asset {{ image-rendering: pixelated; width: 32px; height: 32px; object-fit: contain; background: #243b53; border-radius: 4px; padding: 2px; }}
    .missing {{ color: #9b1c1c; font-size: 12px; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>Asset Registry Preview</h1>
  <p class=\"subtitle\">Profile: <code>{html.escape(str(report.get('profile', 'unknown')))}</code> · World style: <code>{html.escape(str(report.get('world_style', 'unknown')))}</code></p>
  <div class=\"summary\">
    <div class=\"card\"><span>Total entries</span><strong>{summary.get('total_entries', 0)}</strong></div>
    <div class=\"card\"><span>Tiles</span><strong>{summary.get('tiles', 0)}</strong></div>
    <div class=\"card\"><span>Sprites</span><strong>{summary.get('sprites', 0)}</strong></div>
  </div>
  <div class=\"grid\">
    {_counter_list('By category', by_category)}
    {_counter_list('By draw layer', by_draw_layer)}
    {_counter_list('By asset status', by_status)}
    <section><h2>Top tags</h2><ul class=\"counters\">{tag_items}</ul></section>
  </div>
  <h2>Entries</h2>
  <table>
    <thead>
      <tr><th>Image</th><th>ID</th><th>Kind</th><th>Category</th><th>Layer</th><th>Size</th><th>Pivot</th><th>Sort anchor</th><th>Status</th><th>File</th><th>Path</th><th>Tags</th></tr>
    </thead>
    <tbody>
      {_html_table([entry for entry in entries if isinstance(entry, dict)])}
    </tbody>
  </table>
</body>
</html>
"""


def generate_asset_registry_preview(profile_dir: Path, output_dir: Path) -> dict[str, Path]:
    """Generate JSON and HTML asset registry preview files.

    Args:
        profile_dir: Visual profile directory.
        output_dir: Destination directory.

    Returns:
        Mapping with generated file paths.
    """
    report = build_registry_report(profile_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "asset_registry_report.json"
    html_path = output_dir / "asset_registry_preview.html"
    _write_json(json_path, report)
    html_path.write_text(render_html_report(report), encoding="utf-8")
    return {"json": json_path, "html": html_path}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Generate an asset registry preview for a visual profile.")
    parser.add_argument(
        "profile_dir",
        nargs="?",
        default="top_down_visualgen/profiles/dark_forest",
        help="Visual profile directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/visual_map/debug"),
        help="Output directory for registry report files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the asset registry preview generator."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        generated = generate_asset_registry_preview(Path(args.profile_dir), args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Asset registry preview: FAILED: {exc}", file=sys.stderr)
        return 1

    report = _read_json_object(generated["json"])
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("Asset registry preview: OK")
    print(f"  entries: {summary.get('total_entries', 0)}")
    print(f"  tiles:   {summary.get('tiles', 0)}")
    print(f"  sprites: {summary.get('sprites', 0)}")
    print(f"  json:    {generated['json']}")
    print(f"  html:    {generated['html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
