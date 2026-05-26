#!/usr/bin/env python3
"""Render a simple PNG preview from a generated TopDownMapGen world package."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw

LOGGER = logging.getLogger(__name__)
MAP_PACKAGE_INDEX_KIND = "map_package:index"
DEFAULT_PREVIEW_NAME = "world_preview.png"

TERRAIN_COLORS: dict[str, tuple[int, int, int, int]] = {
    "grass": (82, 124, 64, 255),
    "old_overgrown_road": (137, 117, 80, 255),
    "tree_blocker": (35, 75, 42, 255),
    "bush_slow_concealment": (59, 105, 52, 255),
    "flower_decor": (94, 132, 69, 255),
    "mushroom_decor": (91, 116, 76, 255),
    "water_slow": (58, 103, 128, 255),
    "cracked_ground": (117, 103, 84, 255),
    "ruin_wall_blocker": (91, 91, 86, 255),
    "ruin_floor": (116, 114, 104, 255),
    "start": (70, 145, 88, 255),
    "goal": (154, 83, 72, 255),
}
FALLBACK_TERRAIN_COLOR = (96, 96, 96, 255)
BLOCKED_OVERLAY_COLOR = (0, 0, 0, 80)
OBJECT_COLOR = (220, 210, 130, 230)
OBJECT_FOOTPRINT_COLOR = (255, 236, 150, 120)
START_COLOR = (70, 230, 100, 255)
GOAL_COLOR = (240, 80, 70, 255)
GRID_COLOR = (0, 0, 0, 35)


@dataclass(frozen=True, slots=True)
class PreviewSummary:
    """Summary of a rendered world preview.

    Attributes:
        root: Output root directory.
        map_json_path: Path to map_package/map.json.
        output_path: Generated preview image path.
        width_tiles: Map width in tiles.
        height_tiles: Map height in tiles.
        cell_size_px: Preview cell size in pixels.
        terrain_type_count: Number of terrain types observed.
        blocked_tiles: Number of blocked tiles in the collision layer.
        runtime_objects: Number of runtime objects drawn or read.
        start: Start point.
        goal: Goal point.
    """

    root: Path
    map_json_path: Path
    output_path: Path
    width_tiles: int
    height_tiles: int
    cell_size_px: int
    terrain_type_count: int
    blocked_tiles: int
    runtime_objects: int
    start: dict[str, int] | None
    goal: dict[str, int] | None


def render_preview(
    package_path: Path,
    *,
    output_path: Path | None = None,
    cell_size_px: int = 4,
    draw_objects: bool = True,
    draw_collision_overlay: bool = False,
    draw_grid: bool = False,
) -> PreviewSummary:
    """Render a simple PNG preview from public world package files.

    Args:
        package_path: Output directory, manifest path, map_package directory, or map.json.
        output_path: Optional PNG output path. Defaults to output root/world_preview.png.
        cell_size_px: Rendered preview cell size in pixels.
        draw_objects: Whether to draw runtime object markers.
        draw_collision_overlay: Whether to overlay blocked cells.
        draw_grid: Whether to draw a light tile grid.

    Returns:
        Preview summary.

    Raises:
        FileNotFoundError: If a required package file is missing.
        ValueError: If package files are malformed.
    """
    if cell_size_px < 1:
        raise ValueError("cell_size_px must be at least 1")

    map_json_path = resolve_map_json_path(package_path)
    package_dir = map_json_path.parent
    root = package_dir.parent
    map_index = _read_object(map_json_path)

    dimensions = _require_object(map_index, "dimensions")
    width = _require_int(dimensions, "width_tiles")
    height = _require_int(dimensions, "height_tiles")

    layers = _require_object(map_index, "layers")
    objects = _optional_object(map_index.get("objects"))
    terrain = _read_required_package_object(package_dir, layers, "terrain")
    collision = _read_required_package_object(package_dir, layers, "collision")
    start_goal = _read_optional_package_object(package_dir, layers.get("start_goal"))
    runtime_objects = _read_optional_package_object(
        package_dir,
        objects.get("runtime_objects"),
    )

    terrain_rows = _read_type_rows(terrain, width=width, height=height)
    collision_rows = _read_collision_rows(collision, width=width, height=height)
    object_items = _optional_list(runtime_objects.get("items"))
    start = _optional_point(start_goal.get("start"))
    goal = _optional_point(start_goal.get("goal"))

    image = Image.new(
        "RGBA",
        (width * cell_size_px, height * cell_size_px),
        FALLBACK_TERRAIN_COLOR,
    )
    draw = ImageDraw.Draw(image, "RGBA")

    _draw_terrain(draw, terrain_rows=terrain_rows, cell_size_px=cell_size_px)
    if draw_collision_overlay:
        _draw_collision_overlay(
            draw,
            collision_rows=collision_rows,
            cell_size_px=cell_size_px,
        )
    if draw_objects:
        _draw_runtime_objects(
            draw,
            objects=object_items,
            cell_size_px=cell_size_px,
            width=width,
            height=height,
        )
    _draw_point(draw, start, cell_size_px=cell_size_px, color=START_COLOR)
    _draw_point(draw, goal, cell_size_px=cell_size_px, color=GOAL_COLOR)
    if draw_grid:
        _draw_grid(draw, width=width, height=height, cell_size_px=cell_size_px)

    final_output_path = output_path or root / DEFAULT_PREVIEW_NAME
    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(final_output_path)

    return PreviewSummary(
        root=root,
        map_json_path=map_json_path,
        output_path=final_output_path,
        width_tiles=width,
        height_tiles=height,
        cell_size_px=cell_size_px,
        terrain_type_count=len({cell for row in terrain_rows for cell in row}),
        blocked_tiles=sum(cell == "1" for row in collision_rows for cell in row),
        runtime_objects=len(object_items),
        start=start,
        goal=goal,
    )


def resolve_map_json_path(path: Path) -> Path:
    """Resolve map_package/map.json from common public output paths.

    Args:
        path: Output directory, manifest path, map_package directory, or map.json path.

    Returns:
        Path to map_package/map.json.

    Raises:
        FileNotFoundError: If map.json cannot be resolved.
        ValueError: If a manifest is malformed or lacks the package index.
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


def print_summary(summary: PreviewSummary) -> None:
    """Print a concise render summary.

    Args:
        summary: Preview summary.
    """
    LOGGER.info("World preview: OK")
    LOGGER.info("Root: %s", summary.root)
    LOGGER.info("Map package: %s", summary.map_json_path)
    LOGGER.info(
        "Map: %sx%s tiles, preview cell size %s px",
        summary.width_tiles,
        summary.height_tiles,
        summary.cell_size_px,
    )
    LOGGER.info("Rendered:")
    LOGGER.info("- terrain types: %s", summary.terrain_type_count)
    LOGGER.info("- blocked tiles: %s", summary.blocked_tiles)
    LOGGER.info("- runtime object markers: %s", summary.runtime_objects)
    LOGGER.info("- start: %s", _format_point(summary.start))
    LOGGER.info("- goal: %s", _format_point(summary.goal))
    LOGGER.info("Output: %s", summary.output_path)


def _draw_terrain(
    draw: ImageDraw.ImageDraw,
    *,
    terrain_rows: list[list[str]],
    cell_size_px: int,
) -> None:
    for y, row in enumerate(terrain_rows):
        for x, terrain_type in enumerate(row):
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=TERRAIN_COLORS.get(terrain_type, FALLBACK_TERRAIN_COLOR),
            )


def _draw_collision_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    collision_rows: list[str],
    cell_size_px: int,
) -> None:
    for y, row in enumerate(collision_rows):
        for x, cell in enumerate(row):
            if cell == "1":
                draw.rectangle(_cell_rect(x, y, cell_size_px), fill=BLOCKED_OVERLAY_COLOR)


def _draw_runtime_objects(
    draw: ImageDraw.ImageDraw,
    *,
    objects: list[Any],
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    for item in objects:
        if not isinstance(item, dict):
            continue
        footprint = _footprint(item.get("footprint"), width=width, height=height)
        for x, y in footprint:
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=OBJECT_FOOTPRINT_COLOR,
            )
        point = _object_point(item, width=width, height=height)
        if point is None:
            continue
        _draw_small_marker(draw, point["x"], point["y"], cell_size_px, OBJECT_COLOR)


def _draw_point(
    draw: ImageDraw.ImageDraw,
    point: dict[str, int] | None,
    *,
    cell_size_px: int,
    color: tuple[int, int, int, int],
) -> None:
    if point is None:
        return
    x = point["x"]
    y = point["y"]
    padding = max(1, cell_size_px // 5)
    draw.ellipse(
        (
            x * cell_size_px + padding,
            y * cell_size_px + padding,
            (x + 1) * cell_size_px - padding - 1,
            (y + 1) * cell_size_px - padding - 1,
        ),
        fill=color,
    )


def _draw_small_marker(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    cell_size_px: int,
    color: tuple[int, int, int, int],
) -> None:
    padding = max(1, cell_size_px // 4)
    draw.rectangle(
        (
            x * cell_size_px + padding,
            y * cell_size_px + padding,
            (x + 1) * cell_size_px - padding - 1,
            (y + 1) * cell_size_px - padding - 1,
        ),
        fill=color,
    )


def _draw_grid(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    height: int,
    cell_size_px: int,
) -> None:
    for x in range(width + 1):
        pixel_x = x * cell_size_px
        draw.line((pixel_x, 0, pixel_x, height * cell_size_px), fill=GRID_COLOR)
    for y in range(height + 1):
        pixel_y = y * cell_size_px
        draw.line((0, pixel_y, width * cell_size_px, pixel_y), fill=GRID_COLOR)


def _cell_rect(x: int, y: int, cell_size_px: int) -> tuple[int, int, int, int]:
    return (
        x * cell_size_px,
        y * cell_size_px,
        (x + 1) * cell_size_px - 1,
        (y + 1) * cell_size_px - 1,
    )


def _footprint(value: Any, *, width: int, height: int) -> list[tuple[int, int]]:
    if not isinstance(value, list):
        return []
    points: list[tuple[int, int]] = []
    for point in value:
        if (
            isinstance(point, list)
            and len(point) == 2
            and isinstance(point[0], int)
            and isinstance(point[1], int)
            and 0 <= point[0] < width
            and 0 <= point[1] < height
        ):
            points.append((point[0], point[1]))
    return points


def _object_point(item: dict[str, Any], *, width: int, height: int) -> dict[str, int] | None:
    x = item.get("x")
    y = item.get("y")
    if isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height:
        return {"x": x, "y": y}
    position = item.get("position")
    if (
        isinstance(position, list)
        and len(position) == 2
        and isinstance(position[0], int)
        and isinstance(position[1], int)
        and 0 <= position[0] < width
        and 0 <= position[1] < height
    ):
        return {"x": position[0], "y": position[1]}
    return None


def _map_json_from_manifest(manifest_path: Path) -> Path:
    manifest = _read_object(manifest_path)
    output_dir = manifest_path.parent
    artifacts = [
        *_optional_list(manifest.get("primary_outputs")),
        *_optional_list(manifest.get("files")),
    ]
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("kind") != MAP_PACKAGE_INDEX_KIND:
            continue
        relative_path = artifact.get("path")
        if not isinstance(relative_path, str):
            raise ValueError("Map package artifact path must be a string")
        return _require_file(output_dir / relative_path)
    raise ValueError("Manifest does not contain a map_package:index artifact")


def _read_required_package_object(
    package_dir: Path,
    index: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    relative_path = index.get(key)
    if not isinstance(relative_path, str):
        raise ValueError(f"Expected package path field: {key}")
    return _read_object(package_dir / relative_path)


def _read_optional_package_object(package_dir: Path, relative_path: Any) -> dict[str, Any]:
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


def _read_type_rows(data: dict[str, Any], *, width: int, height: int) -> list[list[str]]:
    rows = data.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        raise ValueError("Expected terrain.rows to be a list of rows")
    if len(rows) != height:
        raise ValueError(f"terrain height mismatch: expected {height}, got {len(rows)}")
    result: list[list[str]] = []
    for row_index, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(
                f"terrain width mismatch at row {row_index}: expected {width}, got {len(row)}",
            )
        typed_row: list[str] = []
        for value in row:
            if not isinstance(value, str):
                raise ValueError(f"terrain contains non-string cell at row {row_index}")
            typed_row.append(value)
        result.append(typed_row)
    return result


def _read_collision_rows(data: dict[str, Any], *, width: int, height: int) -> list[str]:
    rows = data.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
        raise ValueError("Expected collision.rows to be a list of strings")
    if len(rows) != height:
        raise ValueError(f"collision height mismatch: expected {height}, got {len(rows)}")
    for row_index, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(
                f"collision width mismatch at row {row_index}: expected {width}, got {len(row)}",
            )
        invalid = set(row) - {"0", "1"}
        if invalid:
            raise ValueError(f"collision contains invalid values: {sorted(invalid)}")
    return rows


def _optional_point(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return None
    return {"x": x, "y": y}


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


def _require_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Expected integer field: {key}")
    return value


def _format_point(point: dict[str, int] | None) -> str:
    if point is None:
        return "missing"
    return f"({point['x']},{point['y']})"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Render a simple PNG preview from a generated world package.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Output directory, _manifest.json, map_package directory, or map.json path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="PNG output path. Defaults to <output-root>/world_preview.png.",
    )
    parser.add_argument(
        "--cell-size",
        type=int,
        default=4,
        help="Preview cell size in pixels. Default: 4.",
    )
    parser.add_argument(
        "--no-objects",
        action="store_true",
        help="Do not draw runtime object markers.",
    )
    parser.add_argument(
        "--collision-overlay",
        action="store_true",
        help="Overlay blocked cells on top of terrain colors.",
    )
    parser.add_argument(
        "--grid",
        action="store_true",
        help="Draw a light tile grid. Useful for small maps.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the preview renderer CLI."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    try:
        summary = render_preview(
            args.path,
            output_path=args.output,
            cell_size_px=args.cell_size,
            draw_objects=not args.no_objects,
            draw_collision_overlay=args.collision_overlay,
            draw_grid=args.grid,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        LOGGER.error("World preview: FAILED")
        LOGGER.error("- %s", exc)
        return 1
    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
