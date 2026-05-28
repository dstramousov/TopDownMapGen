#!/usr/bin/env python3
"""Validate a visual profile assets manifest."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Single validation issue."""

    message: str


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


def _require_mapping(data: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    """Return a required mapping field.

    Args:
        data: Parent JSON object.
        key: Field name.
        path: File path used for diagnostics.

    Returns:
        Mapping value.

    Raises:
        ValueError: If the field is missing or not a mapping.
    """
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping '{key}' in {path}")
    return value


def _validate_size(value: Any, field: str, asset_id: str) -> list[ValidationIssue]:
    """Validate an integer pair field."""
    if not isinstance(value, list) or len(value) != 2:
        return [ValidationIssue(f"{asset_id}: '{field}' must be a two-item list")]
    if not all(isinstance(item, int) and item >= 0 for item in value):
        return [ValidationIssue(f"{asset_id}: '{field}' must contain non-negative integers")]
    return []


def _validate_tiles(
    *,
    visual_tile_ids: set[str],
    manifest_tiles: dict[str, Any],
    profile_dir: Path,
    check_files: bool,
) -> list[ValidationIssue]:
    """Validate tile entries against visual_tilesets.json."""
    issues: list[ValidationIssue] = []
    missing = sorted(visual_tile_ids - set(manifest_tiles))
    for tile_id in missing:
        issues.append(ValidationIssue(f"missing tile manifest entry: {tile_id}"))

    for tile_id, entry in sorted(manifest_tiles.items()):
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(f"{tile_id}: tile entry must be a mapping"))
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            issues.append(ValidationIssue(f"{tile_id}: tile 'path' must be a non-empty string"))
        issues.extend(_validate_size(entry.get("size"), "size", tile_id))
        if check_files and isinstance(path, str) and path:
            asset_path = profile_dir / path
            if not asset_path.exists():
                issues.append(ValidationIssue(f"{tile_id}: asset file does not exist: {asset_path}"))
    return issues


def _validate_sprites(
    *,
    visual_sprite_ids: set[str],
    manifest_sprites: dict[str, Any],
    profile_dir: Path,
    check_files: bool,
) -> list[ValidationIssue]:
    """Validate sprite entries against visual_tilesets.json."""
    issues: list[ValidationIssue] = []
    missing = sorted(visual_sprite_ids - set(manifest_sprites))
    for sprite_id in missing:
        issues.append(ValidationIssue(f"missing sprite manifest entry: {sprite_id}"))

    for sprite_id, entry in sorted(manifest_sprites.items()):
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(f"{sprite_id}: sprite entry must be a mapping"))
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            issues.append(ValidationIssue(f"{sprite_id}: sprite 'path' must be a non-empty string"))
        issues.extend(_validate_size(entry.get("size"), "size", sprite_id))
        issues.extend(_validate_size(entry.get("pivot"), "pivot", sprite_id))
        issues.extend(_validate_size(entry.get("sort_anchor"), "sort_anchor", sprite_id))
        draw_layer = entry.get("draw_layer")
        if not isinstance(draw_layer, str) or not draw_layer:
            issues.append(ValidationIssue(f"{sprite_id}: sprite 'draw_layer' must be a non-empty string"))
        if check_files and isinstance(path, str) and path:
            asset_path = profile_dir / path
            if not asset_path.exists():
                issues.append(ValidationIssue(f"{sprite_id}: asset file does not exist: {asset_path}"))
    return issues


def validate_assets_manifest(profile_dir: Path, *, check_files: bool = False) -> list[ValidationIssue]:
    """Validate the assets manifest for a visual profile.

    Args:
        profile_dir: Visual profile directory.
        check_files: Whether to require referenced asset files to exist.

    Returns:
        List of validation issues. Empty means the contract is valid.
    """
    visual_tilesets_path = profile_dir / "visual_tilesets.json"
    assets_manifest_path = profile_dir / "assets_manifest.json"
    visual_tilesets = _read_json_object(visual_tilesets_path)
    assets_manifest = _read_json_object(assets_manifest_path)

    tiles = _require_mapping(visual_tilesets, "tiles", visual_tilesets_path)
    manifest_tiles = _require_mapping(assets_manifest, "tiles", assets_manifest_path)
    manifest_sprites = _require_mapping(assets_manifest, "sprites", assets_manifest_path)

    raw_sprites = visual_tilesets.get("sprites")
    if not isinstance(raw_sprites, list) or not all(isinstance(item, str) for item in raw_sprites):
        raise ValueError(f"Expected string list 'sprites' in {visual_tilesets_path}")

    issues: list[ValidationIssue] = []
    if assets_manifest.get("schema_version") != "assets-manifest-v1":
        issues.append(ValidationIssue("assets_manifest.schema_version must be assets-manifest-v1"))

    fallbacks = assets_manifest.get("fallbacks")
    if not isinstance(fallbacks, dict):
        issues.append(ValidationIssue("assets_manifest.fallbacks must be a mapping"))
    else:
        missing_tile = fallbacks.get("missing_tile")
        missing_sprite = fallbacks.get("missing_sprite")
        if missing_tile not in manifest_tiles:
            issues.append(ValidationIssue("fallback missing_tile must reference a manifest tile"))
        if missing_sprite not in manifest_sprites:
            issues.append(ValidationIssue("fallback missing_sprite must reference a manifest sprite"))

    issues.extend(
        _validate_tiles(
            visual_tile_ids=set(tiles),
            manifest_tiles=manifest_tiles,
            profile_dir=profile_dir,
            check_files=check_files,
        )
    )
    issues.extend(
        _validate_sprites(
            visual_sprite_ids=set(raw_sprites),
            manifest_sprites=manifest_sprites,
            profile_dir=profile_dir,
            check_files=check_files,
        )
    )
    return issues


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate a visual profile assets manifest.")
    parser.add_argument(
        "profile_dir",
        nargs="?",
        default="top_down_visualgen/profiles/dark_forest",
        help="Visual profile directory.",
    )
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Also require referenced PNG files to exist.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run assets manifest validation."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    profile_dir = Path(args.profile_dir)
    issues = validate_assets_manifest(profile_dir, check_files=args.check_files)
    if issues:
        print("Assets manifest: FAILED")
        for issue in issues:
            print(f"- {issue.message}")
        return 1

    assets_manifest = _read_json_object(profile_dir / "assets_manifest.json")
    print("Assets manifest: OK")
    print(f"  profile: {assets_manifest.get('profile', 'unknown')}")
    print(f"  tiles:   {len(assets_manifest.get('tiles', {}))}")
    print(f"  sprites: {len(assets_manifest.get('sprites', {}))}")
    if not args.check_files:
        print("  files:   not checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
