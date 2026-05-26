#!/usr/bin/env python3
"""Load and summarize a generated map package."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
MAP_PACKAGE_INDEX_KIND = "map_package:index"


@dataclass(frozen=True, slots=True)
class MapPackageSummary:
    """Small summary of a loaded map package.

    Attributes:
        width: Map width in tiles.
        height: Map height in tiles.
        tile_size_px: Tile size in pixels.
        start: Start point, if present.
        goal: Goal point, if present.
        runtime_object_count: Number of runtime objects.
        blocked_tile_count: Number of blocked cells from tile collision.
        gameplay_layers: Gameplay layer names declared by the package.
        tile_type_count: Number of declared tile type definitions.
        object_type_count: Number of declared object type definitions.
        tile_render_hint_count: Number of declared terrain render hints.
        object_render_hint_count: Number of declared object render hints.
    """

    width: int
    height: int
    tile_size_px: int
    start: dict[str, int] | None
    goal: dict[str, int] | None
    runtime_object_count: int
    blocked_tile_count: int
    gameplay_layers: list[str]
    tile_type_count: int
    object_type_count: int
    tile_render_hint_count: int
    object_render_hint_count: int


def load_summary(path: Path) -> MapPackageSummary:
    """Load a map package summary from an output directory or map.json path.

    Args:
        path: Generation output directory, manifest path, package directory,
            or map.json.

    Returns:
        Loaded map package summary.

    Raises:
        FileNotFoundError: If the package index or required files are missing.
        ValueError: If required JSON structures are malformed.
    """
    map_json_path = resolve_map_json_path(path)
    package_dir = map_json_path.parent
    map_index = _read_object(map_json_path)

    dimensions = _require_object(map_index, "dimensions")
    width = _require_int(dimensions, "width_tiles")
    height = _require_int(dimensions, "height_tiles")
    tile_size_px = _require_int(dimensions, "tile_size_px")

    layers = _require_object(map_index, "layers")
    objects = _require_object(map_index, "objects")
    gameplay = _optional_object(map_index.get("gameplay"))
    catalogs = _optional_object(map_index.get("catalogs"))
    render = _optional_object(map_index.get("render"))

    collision = _read_object(package_dir / _require_str(layers, "collision"))
    start_goal_path = layers.get("start_goal")
    start_goal = (
        _read_object(package_dir / start_goal_path)
        if isinstance(start_goal_path, str)
        else {}
    )
    runtime_objects = _read_object(
        package_dir / _require_str(objects, "runtime_objects"),
    )
    tile_types = _read_optional_object(package_dir, catalogs.get("tile_types"))
    object_types = _read_optional_object(package_dir, catalogs.get("object_types"))
    tile_render_hints = _read_optional_object(
        package_dir,
        render.get("tile_render_hints"),
    )
    object_render_hints = _read_optional_object(
        package_dir,
        render.get("object_render_hints"),
    )

    collision_rows = _require_string_list(collision, "rows")
    blocked_count = sum(cell == "1" for row in collision_rows for cell in row)

    object_items = _optional_list(runtime_objects.get("items"))
    points = _optional_object(map_index.get("points"))

    return MapPackageSummary(
        width=width,
        height=height,
        tile_size_px=tile_size_px,
        start=_optional_point(start_goal.get("start") or points.get("start")),
        goal=_optional_point(start_goal.get("goal") or points.get("goal")),
        runtime_object_count=len(object_items),
        blocked_tile_count=blocked_count,
        gameplay_layers=sorted(gameplay),
        tile_type_count=len(_optional_object(tile_types.get("types"))),
        object_type_count=len(_optional_object(object_types.get("types"))),
        tile_render_hint_count=len(_optional_object(tile_render_hints.get("hints"))),
        object_render_hint_count=len(_optional_object(object_render_hints.get("hints"))),
    )


def resolve_map_json_path(path: Path) -> Path:
    """Resolve map_package/map.json from common generation paths.

    Args:
        path: Output directory, manifest path, package directory, or map.json path.

    Returns:
        Path to map_package/map.json.

    Raises:
        FileNotFoundError: If map.json cannot be resolved.
        ValueError: If the manifest does not describe a map package index.
    """
    candidate = path.expanduser().resolve()
    if candidate.is_file() and candidate.name == "map.json":
        return candidate
    if candidate.is_dir() and candidate.name == "map_package":
        return _require_file(candidate / "map.json")
    if candidate.is_dir():
        manifest_path = candidate / "_manifest.json"
        if manifest_path.exists():
            return _map_json_from_manifest(manifest_path)
        return _require_file(candidate / "map_package" / "map.json")
    if candidate.is_file() and candidate.name == "_manifest.json":
        return _map_json_from_manifest(candidate)
    raise FileNotFoundError(f"Cannot resolve map package index from: {path}")


def build_collision_grid(collision_rows: list[str]) -> list[list[bool]]:
    """Build a boolean collision grid from encoded collision rows.

    Args:
        collision_rows: Row strings where "1" means blocked and "0" means passable.

    Returns:
        A row-major grid where True means blocked.
    """
    return [[cell == "1" for cell in row] for row in collision_rows]


def _map_json_from_manifest(manifest_path: Path) -> Path:
    manifest = _read_object(manifest_path)
    output_dir = manifest_path.parent
    files = _optional_list(manifest.get("files"))
    primary_outputs = _optional_list(manifest.get("primary_outputs"))
    for artifact in [*primary_outputs, *files]:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("kind") == MAP_PACKAGE_INDEX_KIND:
            relative_path = artifact.get("path")
            if not isinstance(relative_path, str):
                raise ValueError("Map package artifact path must be a string")
            return _require_file(output_dir / relative_path)
    raise ValueError("Manifest does not contain a map_package:index artifact")


def _read_optional_object(package_dir: Path, relative_path: Any) -> dict[str, Any]:
    if not isinstance(relative_path, str):
        return {}
    return _read_object(package_dir / relative_path)


def _read_object(path: Path) -> dict[str, Any]:
    with _require_file(path).open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _require_object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object field: {key}")
    return value


def _optional_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _optional_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _require_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Expected string list field: {key}")
    return value


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Expected string field: {key}")
    return value


def _require_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Expected integer field: {key}")
    return value


def _optional_point(value: Any) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Point must be an object or null")
    x = value.get("x")
    y = value.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("Point must contain integer x and y")
    return {"x": x, "y": y}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load and summarize a TopDownMapGen map package.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Output directory, _manifest.json, map_package directory, or map.json.",
    )
    return parser


def main() -> int:
    """Run the example CLI.

    Returns:
        Process exit code.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_parser().parse_args()
    summary = load_summary(args.path)
    LOGGER.info(
        "Map: %sx%s tiles, tile_size=%spx",
        summary.width,
        summary.height,
        summary.tile_size_px,
    )
    LOGGER.info("Start: %s", summary.start)
    LOGGER.info("Goal: %s", summary.goal)
    LOGGER.info("Runtime objects: %s", summary.runtime_object_count)
    LOGGER.info("Tile types: %s", summary.tile_type_count)
    LOGGER.info("Object types: %s", summary.object_type_count)
    LOGGER.info("Tile render hints: %s", summary.tile_render_hint_count)
    LOGGER.info("Object render hints: %s", summary.object_render_hint_count)
    LOGGER.info("Blocked cells: %s", summary.blocked_tile_count)
    LOGGER.info("Gameplay layers: %s", ", ".join(summary.gameplay_layers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
