#!/usr/bin/env python3
"""Render pseudo-3D geographic previews from four map corners."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from top_down_worldgen.tactical.traversal import DEFAULT_TRAVERSAL_RULES

LOGGER = logging.getLogger(__name__)

OUTPUT_SIZE_DEFAULT = (2560, 1440)
DEFAULT_OUTPUT_DIR_NAME = "geography_3d_preview"
DEFAULT_VIEWS = ("nw", "ne", "se", "sw")
BACKGROUND_COLOR = (22, 24, 24, 255)
TITLE_COLOR = (235, 232, 215, 255)
MUTED_TEXT_COLOR = (180, 174, 150, 255)
GRID_LINE_COLOR = (38, 38, 34, 85)
SHADOW_COLOR = (0, 0, 0, 42)
ELEVATION_FORMAT_MIN_LEVEL = -5
ELEVATION_FORMAT_MAX_LEVEL = 20

ELEVATION_COLORS: dict[int, tuple[int, int, int, int]] = {
    -5: (36, 95, 111, 255),
    -4: (48, 119, 128, 255),
    -3: (64, 143, 139, 255),
    -2: (87, 164, 148, 255),
    -1: (118, 186, 157, 255),
    0: (76, 132, 72, 255),
    1: (96, 153, 77, 255),
    2: (126, 174, 83, 255),
    3: (160, 190, 89, 255),
    4: (194, 204, 96, 255),
    5: (215, 198, 94, 255),
    6: (222, 181, 84, 255),
    7: (217, 160, 74, 255),
    8: (203, 137, 66, 255),
    9: (184, 117, 59, 255),
    10: (161, 99, 54, 255),
    11: (143, 88, 58, 255),
    12: (127, 80, 62, 255),
    13: (111, 74, 66, 255),
    14: (99, 73, 70, 255),
    15: (118, 100, 91, 255),
    16: (140, 129, 118, 255),
    17: (164, 160, 148, 255),
    18: (191, 190, 178, 255),
    19: (219, 219, 209, 255),
    20: (246, 246, 238, 255),
}

WALKABILITY_COLORS: dict[str, tuple[int, int, int, int]] = {
    "reachable": (78, 145, 72, 255),
    "slow": (209, 184, 80, 255),
    "blocked": (23, 31, 23, 255),
    "water": (43, 116, 180, 255),
    "structural": (132, 79, 165, 255),
    "unreachable": (207, 62, 58, 255),
    "start": (246, 246, 238, 255),
    "goal": (255, 204, 80, 255),
}

TRAVERSAL_COLORS: dict[str, tuple[int, int, int, int]] = {
    "reachable": (78, 145, 72, 255),
    "slope": (205, 175, 74, 255),
    "blocked": (23, 31, 23, 255),
    "water": (43, 116, 180, 255),
    "structural": (132, 79, 165, 255),
    "too_steep": (222, 84, 58, 255),
    "unreachable": (168, 46, 54, 255),
    "terrain_island": (96, 101, 94, 255),
    "start": (246, 246, 238, 255),
    "goal": (255, 204, 80, 255),
}

TERRAIN_TRAVERSAL_COLORS: dict[str, tuple[int, int, int, int]] = {
    "reachable": (82, 150, 77, 255),
    "slow": (214, 177, 70, 255),
    "blocked": (79, 42, 39, 255),
    "water": (45, 119, 184, 255),
    "structural": (136, 80, 167, 255),
    "unreachable": (211, 61, 57, 255),
    "tree": (35, 91, 39, 255),
    "start": (246, 246, 238, 255),
    "goal": (255, 204, 80, 255),
}

TERRAIN_TINTS: dict[str, tuple[tuple[int, int, int, int], float]] = {
    "old_overgrown_road": ((205, 184, 127, 255), 0.52),
    "water_slow": ((42, 118, 182, 255), 0.64),
    "ruin_wall_blocker": ((112, 109, 103, 255), 0.56),
    "ruin_floor": ((153, 143, 120, 255), 0.42),
    "cracked_ground": ((151, 111, 72, 255), 0.34),
    "bush_slow_concealment": ((52, 106, 53, 255), 0.34),
    "flower_decor": ((176, 160, 93, 255), 0.16),
    "mushroom_decor": ((155, 125, 101, 255), 0.18),
    "tree_blocker": ((48, 103, 50, 255), 0.42),
}

WALKABILITY_LABELS: dict[str, str] = {
    "reachable": "reachable walkable",
    "slow": "slow / difficult",
    "blocked": "blocked",
    "water": "water",
    "structural": "structural depth",
    "unreachable": "unreachable walkable",
    "start": "start",
    "goal": "goal",
}

TRAVERSAL_LABELS: dict[str, str] = {
    "reachable": "3D reachable",
    "slope": "3D slope / difficult",
    "blocked": "blocked terrain",
    "water": "water",
    "structural": "structural marker",
    "too_steep": "2D walkable, too steep",
    "unreachable": "2D walkable, unreachable",
    "terrain_island": "2D terrain island",
    "start": "start",
    "goal": "goal",
}

TERRAIN_TRAVERSAL_LABELS: dict[str, str] = {
    "reachable": "walkable ground",
    "slow": "walkable, slow",
    "blocked": "blocked terrain",
    "water": "water / wet terrain",
    "structural": "structural depth",
    "unreachable": "unreachable walkable",
    "tree": "tree blocker",
    "start": "start",
    "goal": "goal",
}

MARKER_OVERLAY_CODES = {"structural", "start", "goal"}

VIEW_LABELS: dict[str, str] = {
    "nw": "NW camera",
    "ne": "NE camera",
    "se": "SE camera",
    "sw": "SW camera",
}


@dataclass(frozen=True, slots=True)
class HeightMap:
    """Loaded geographic elevation grid.

    Attributes:
        rows: Geographic elevation levels.
        width: Map width in tiles.
        height: Map height in tiles.
        min_level: Lowest level present.
        max_level: Highest level present.
        seed: Generation seed, if available.
        map_class: Size-aware elevation profile class.
        active_range: Active generator range.
        overlay_name: Optional diagnostic overlay name.
        overlay_rows: Optional overlay classes per tile.
        terrain_rows: Optional semantic terrain types per tile.
        overlay_counts: Optional overlay category counts.
    """

    rows: list[list[int]]
    width: int
    height: int
    min_level: int
    max_level: int
    seed: int | None
    map_class: str
    active_range: tuple[int, int] | None
    overlay_name: str
    overlay_rows: list[list[str]] | None
    terrain_rows: list[list[str]] | None
    overlay_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class RenderScale:
    """Computed isometric render scale."""

    tile_width: float
    tile_height: float
    height_step: float
    offset_x: float
    offset_y: float


@dataclass(frozen=True, slots=True)
class OverlayData:
    """Runtime diagnostic overlay data used by the 3D renderer."""

    overlay_rows: list[list[str]]
    counts: dict[str, int]
    terrain_rows: list[list[str]] | None = None


def main() -> int:
    """Run the pseudo-3D preview renderer."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args()
    try:
        height_map = load_height_map(args.path, overlay=args.overlay)
        output_dir = args.output_dir or _default_output_dir(args.path)
        output_dir.mkdir(parents=True, exist_ok=True)
        views = _normalize_views(args.views)
        for view in views:
            output_path = output_dir / _output_filename(args.overlay, view)
            render_view(
                height_map,
                view=view,
                output_path=output_path,
                output_size=(args.width, args.height),
                draw_grid=not args.no_grid,
            )
            LOGGER.info("3D-preview создан: %s", output_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        LOGGER.error("Не удалось создать 3D-preview")
        LOGGER.error("- %s", exc)
        return 1
    return 0


def load_height_map(path: Path, *, overlay: str) -> HeightMap:
    """Load geographic elevation rows from a generated output directory.

    Args:
        path: Output directory, _manifest.json, map_package directory, or map.json path.
        overlay: Diagnostic overlay to render.

    Returns:
        Loaded height map and optional overlay.

    Raises:
        FileNotFoundError: If required files are missing.
        ValueError: If package files are malformed.
    """
    map_json_path = _resolve_map_json_path(path)
    output_root = map_json_path.parent.parent
    map_index = _read_object(map_json_path)
    dimensions = _require_object(map_index, "dimensions")
    width = _require_int(dimensions, "width_tiles")
    height = _require_int(dimensions, "height_tiles")
    runtime_rows = _read_runtime_height_rows(map_json_path.parent, map_index, width=width, height=height)
    generation_report = _read_generation_report(output_root)
    geography = _optional_object(generation_report.get("geography"))
    if not geography:
        raise ValueError("tactical_map.json lacks elevation_generation_report.geography")
    geographic_rows = _read_geographic_height_rows(
        geography,
        fallback_rows=runtime_rows,
        width=width,
        height=height,
    )
    levels = [level for row in geographic_rows for level in row]
    profile = _optional_object(generation_report.get("profile"))
    active_range = _read_int_range(profile.get("active_range"))
    seed = _read_seed(output_root)
    overlay_rows: list[list[str]] | None = None
    terrain_rows: list[list[str]] | None = None
    overlay_counts: dict[str, int] = {}
    if overlay == "walkability":
        overlay_data = _read_walkability_data(
            output_root=output_root,
            package_dir=map_json_path.parent,
            map_index=map_index,
            geography=geography,
            width=width,
            height=height,
        )
        overlay_rows = overlay_data.overlay_rows
        overlay_counts = overlay_data.counts
    elif overlay == "traversal":
        overlay_data = _read_traversal_data(
            output_root=output_root,
            package_dir=map_json_path.parent,
            map_index=map_index,
            geography=geography,
            geographic_rows=geographic_rows,
            width=width,
            height=height,
        )
        overlay_rows = overlay_data.overlay_rows
        overlay_counts = overlay_data.counts
    elif overlay == "terrain_traversal":
        overlay_data = _read_terrain_traversal_data(
            output_root=output_root,
            package_dir=map_json_path.parent,
            map_index=map_index,
            geography=geography,
            width=width,
            height=height,
        )
        overlay_rows = overlay_data.overlay_rows
        terrain_rows = overlay_data.terrain_rows
        overlay_counts = overlay_data.counts
    return HeightMap(
        rows=geographic_rows,
        width=width,
        height=height,
        min_level=min(levels) if levels else 0,
        max_level=max(levels) if levels else 0,
        seed=seed,
        map_class=str(profile.get("map_class", "unknown")),
        active_range=active_range,
        overlay_name=overlay,
        overlay_rows=overlay_rows,
        terrain_rows=terrain_rows,
        overlay_counts=overlay_counts,
    )


def render_view(
    height_map: HeightMap,
    *,
    view: str,
    output_path: Path,
    output_size: tuple[int, int],
    draw_grid: bool,
) -> None:
    """Render one pseudo-3D isometric view.

    Args:
        height_map: Geographic height map.
        view: View code: nw, ne, se, or sw.
        output_path: Target PNG path.
        output_size: Output image size in pixels.
        draw_grid: Whether to draw subtle top grid lines.
    """
    image = Image.new("RGBA", output_size, BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image, "RGBA")
    oriented_rows = _orient_grid(height_map.rows, view)
    oriented_overlay = _orient_grid(height_map.overlay_rows, view) if height_map.overlay_rows else None
    oriented_terrain = _orient_grid(height_map.terrain_rows, view) if height_map.terrain_rows else None
    scale = _compute_scale(oriented_rows, output_size)
    _draw_soft_shadow(draw, oriented_rows=oriented_rows, scale=scale)
    _draw_isometric_map(
        draw,
        overlay_name=height_map.overlay_name,
        oriented_rows=oriented_rows,
        oriented_overlay=oriented_overlay,
        oriented_terrain=oriented_terrain,
        scale=scale,
        draw_grid=draw_grid,
    )
    _draw_title(draw, height_map=height_map, view=view, output_size=output_size)
    if height_map.overlay_name != "geography":
        _draw_overlay_legend(draw, height_map=height_map, output_size=output_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output_path, quality=95)


def _draw_isometric_map(
    draw: ImageDraw.ImageDraw,
    *,
    overlay_name: str,
    oriented_rows: list[list[int]],
    oriented_overlay: list[list[str]] | None,
    oriented_terrain: list[list[str]] | None,
    scale: RenderScale,
    draw_grid: bool,
) -> None:
    height = len(oriented_rows)
    width = len(oriented_rows[0]) if height else 0
    min_level = min((level for row in oriented_rows for level in row), default=0)
    for y in range(height):
        for x in range(width):
            level = oriented_rows[y][x]
            overlay_code = None
            if oriented_overlay and y < len(oriented_overlay) and x < len(oriented_overlay[y]):
                overlay_code = oriented_overlay[y][x]
            terrain = None
            if oriented_terrain and y < len(oriented_terrain) and x < len(oriented_terrain[y]):
                terrain = oriented_terrain[y][x]
            color = _tile_color(level, overlay_name, overlay_code, terrain)
            top = _tile_top_polygon(x, y, level, min_level=min_level, scale=scale)
            east_level = oriented_rows[y][x + 1] if x + 1 < width else min_level
            south_level = oriented_rows[y + 1][x] if y + 1 < height else min_level
            if level > east_level:
                draw.polygon(
                    _east_face_polygon(x, y, level, east_level, min_level=min_level, scale=scale),
                    fill=_shade_color(color, 0.68),
                )
            if level > south_level:
                draw.polygon(
                    _south_face_polygon(x, y, level, south_level, min_level=min_level, scale=scale),
                    fill=_shade_color(color, 0.52),
                )
            draw.polygon(top, fill=color)
            if draw_grid:
                draw.line(top + [top[0]], fill=GRID_LINE_COLOR, width=1)
            if overlay_name == "terrain_traversal":
                _draw_terrain_feature(
                    draw,
                    top=top,
                    terrain=terrain,
                    overlay_code=overlay_code,
                    scale=scale,
                )
            if overlay_code in MARKER_OVERLAY_CODES:
                _draw_overlay_marker(draw, top=top, overlay_code=overlay_code, overlay_name=overlay_name)


def _draw_soft_shadow(
    draw: ImageDraw.ImageDraw,
    *,
    oriented_rows: list[list[int]],
    scale: RenderScale,
) -> None:
    height = len(oriented_rows)
    width = len(oriented_rows[0]) if height else 0
    if width <= 0 or height <= 0:
        return
    corners = [
        _project_point(0, 0, 0, min_level=0, scale=scale),
        _project_point(width, 0, 0, min_level=0, scale=scale),
        _project_point(width, height, 0, min_level=0, scale=scale),
        _project_point(0, height, 0, min_level=0, scale=scale),
    ]
    shadow = [(x + scale.tile_width * 0.75, y + scale.tile_height * 0.95) for x, y in corners]
    draw.polygon(shadow, fill=SHADOW_COLOR)


def _draw_title(
    draw: ImageDraw.ImageDraw,
    *,
    height_map: HeightMap,
    view: str,
    output_size: tuple[int, int],
) -> None:
    font = _load_font(26)
    small_font = _load_font(18)
    margin = 28
    overlay_title_by_name = {
        "geography": "Geographic",
        "walkability": "Walkability",
        "traversal": "Traversal",
        "terrain_traversal": "Terrain + traversal",
    }
    overlay_title = overlay_title_by_name.get(height_map.overlay_name, height_map.overlay_name.title())
    title = f"{overlay_title} 3D preview — {VIEW_LABELS.get(view, view.upper())}"
    subtitle = (
        f"map {height_map.width}x{height_map.height}, levels {height_map.min_level}..{height_map.max_level}, "
        f"profile {height_map.map_class}"
    )
    if height_map.active_range is not None:
        subtitle += f", active {height_map.active_range[0]}..{height_map.active_range[1]}"
    if height_map.seed is not None:
        subtitle += f", seed {height_map.seed}"
    draw.rectangle((18, 18, output_size[0] - 18, 82), fill=(20, 21, 19, 185))
    draw.text((margin, 25), title, fill=TITLE_COLOR, font=font)
    draw.text((margin, 55), subtitle, fill=MUTED_TEXT_COLOR, font=small_font)


def _draw_overlay_legend(
    draw: ImageDraw.ImageDraw,
    *,
    height_map: HeightMap,
    output_size: tuple[int, int],
) -> None:
    font = _load_font(20)
    small_font = _load_font(16)
    x0 = output_size[0] - 430
    y0 = 104
    line_h = 30
    labels = _overlay_labels(height_map.overlay_name)
    colors = _overlay_colors(height_map.overlay_name)
    keys = tuple(labels.keys())
    height = 52 + line_h * len(keys)
    title_by_name = {
        "traversal": "Traversal overlay",
        "terrain_traversal": "Terrain + traversal overlay",
    }
    title = title_by_name.get(height_map.overlay_name, "Walkability overlay")
    draw.rectangle((x0 - 16, y0 - 16, output_size[0] - 18, y0 + height), fill=(20, 21, 19, 195))
    draw.text((x0, y0 - 6), title, fill=TITLE_COLOR, font=font)
    total = max(1, height_map.width * height_map.height)
    for index, key in enumerate(keys):
        y = y0 + 34 + index * line_h
        color = colors[key]
        count = int(height_map.overlay_counts.get(key, 0))
        percent = count * 100.0 / total
        draw.rectangle((x0, y + 3, x0 + 22, y + 22), fill=color, outline=(15, 15, 12, 220))
        label = labels[key]
        text = f"{label:<27} {count:>6} {percent:>5.1f}%"
        draw.text((x0 + 34, y), text, fill=MUTED_TEXT_COLOR, font=small_font)


def _tile_top_polygon(
    x: int,
    y: int,
    level: int,
    *,
    min_level: int,
    scale: RenderScale,
) -> list[tuple[float, float]]:
    p00 = _project_point(x, y, level, min_level=min_level, scale=scale)
    p10 = _project_point(x + 1, y, level, min_level=min_level, scale=scale)
    p11 = _project_point(x + 1, y + 1, level, min_level=min_level, scale=scale)
    p01 = _project_point(x, y + 1, level, min_level=min_level, scale=scale)
    return [p00, p10, p11, p01]


def _east_face_polygon(
    x: int,
    y: int,
    level: int,
    lower_level: int,
    *,
    min_level: int,
    scale: RenderScale,
) -> list[tuple[float, float]]:
    top_a = _project_point(x + 1, y, level, min_level=min_level, scale=scale)
    top_b = _project_point(x + 1, y + 1, level, min_level=min_level, scale=scale)
    bottom_b = _project_point(x + 1, y + 1, lower_level, min_level=min_level, scale=scale)
    bottom_a = _project_point(x + 1, y, lower_level, min_level=min_level, scale=scale)
    return [top_a, top_b, bottom_b, bottom_a]


def _south_face_polygon(
    x: int,
    y: int,
    level: int,
    lower_level: int,
    *,
    min_level: int,
    scale: RenderScale,
) -> list[tuple[float, float]]:
    top_a = _project_point(x, y + 1, level, min_level=min_level, scale=scale)
    top_b = _project_point(x + 1, y + 1, level, min_level=min_level, scale=scale)
    bottom_b = _project_point(x + 1, y + 1, lower_level, min_level=min_level, scale=scale)
    bottom_a = _project_point(x, y + 1, lower_level, min_level=min_level, scale=scale)
    return [top_a, top_b, bottom_b, bottom_a]


def _project_point(
    x: float,
    y: float,
    level: int,
    *,
    min_level: int,
    scale: RenderScale,
) -> tuple[float, float]:
    z = (level - min_level) * scale.height_step
    screen_x = (x - y) * scale.tile_width * 0.5 + scale.offset_x
    screen_y = (x + y) * scale.tile_height * 0.5 - z + scale.offset_y
    return (screen_x, screen_y)


def _compute_scale(oriented_rows: list[list[int]], output_size: tuple[int, int]) -> RenderScale:
    height = len(oriented_rows)
    width = len(oriented_rows[0]) if height else 0
    width_px, height_px = output_size
    margin_x = 110.0
    margin_top = 110.0
    margin_bottom = 90.0
    levels = [level for row in oriented_rows for level in row]
    min_level = min(levels) if levels else 0
    max_level = max(levels) if levels else 0
    span = max(1, max_level - min_level)
    tile_by_width = (width_px - margin_x * 2.0) * 2.0 / max(1, width + height)
    tile_by_height = (height_px - margin_top - margin_bottom) / max(
        1.0,
        (width + height) * 0.25 + span * 0.34,
    )
    tile_width = max(3.0, min(28.0, tile_by_width, tile_by_height))
    tile_height = tile_width * 0.5
    height_step = tile_width * 0.34
    iso_width = (width + height) * tile_width * 0.5
    iso_height = (width + height) * tile_height * 0.5 + span * height_step
    offset_x = (width_px - iso_width) * 0.5 + height * tile_width * 0.5
    offset_y = (height_px - iso_height) * 0.5 + span * height_step + 38.0
    return RenderScale(
        tile_width=tile_width,
        tile_height=tile_height,
        height_step=height_step,
        offset_x=offset_x,
        offset_y=offset_y,
    )


def _orient_grid(rows: list[list[Any]] | None, view: str) -> list[list[Any]]:
    if not rows:
        return []
    if view == "nw":
        return [list(row) for row in rows]
    if view == "se":
        return [list(reversed(row)) for row in reversed(rows)]
    if view == "ne":
        return [[rows[y][x] for y in range(len(rows) - 1, -1, -1)] for x in range(len(rows[0]))]
    if view == "sw":
        return [[rows[y][x] for y in range(len(rows))] for x in range(len(rows[0]) - 1, -1, -1)]
    raise ValueError(f"Unsupported view: {view}")


def _tile_color(
    level: int,
    overlay_name: str,
    overlay_code: str | None,
    terrain: str | None = None,
) -> tuple[int, int, int, int]:
    base = _level_color(level)
    if overlay_name == "terrain_traversal":
        return _terrain_traversal_tile_color(base, terrain=terrain, overlay_code=overlay_code)
    if not overlay_code or overlay_code in MARKER_OVERLAY_CODES:
        return base
    colors = _overlay_colors(overlay_name)
    return colors.get(overlay_code, colors.get("reachable", base))


def _terrain_traversal_tile_color(
    base: tuple[int, int, int, int],
    *,
    terrain: str | None,
    overlay_code: str | None,
) -> tuple[int, int, int, int]:
    color = base
    tint = TERRAIN_TINTS.get(terrain or "")
    if tint is not None:
        color = _blend_color(color, tint[0], tint[1])
    if overlay_code == "blocked":
        weight = 0.30 if terrain == "tree_blocker" else 0.48
        color = _blend_color(color, TERRAIN_TRAVERSAL_COLORS["blocked"], weight)
    elif overlay_code == "slow":
        color = _blend_color(color, TERRAIN_TRAVERSAL_COLORS["slow"], 0.28)
    elif overlay_code == "water":
        color = _blend_color(color, TERRAIN_TRAVERSAL_COLORS["water"], 0.40)
    elif overlay_code == "structural":
        color = _blend_color(color, TERRAIN_TRAVERSAL_COLORS["structural"], 0.48)
    elif overlay_code == "unreachable":
        color = _blend_color(color, TERRAIN_TRAVERSAL_COLORS["unreachable"], 0.60)
    elif overlay_code == "reachable":
        color = _blend_color(color, TERRAIN_TRAVERSAL_COLORS["reachable"], 0.10)
    return color


def _overlay_colors(overlay_name: str) -> dict[str, tuple[int, int, int, int]]:
    if overlay_name == "traversal":
        return TRAVERSAL_COLORS
    if overlay_name == "terrain_traversal":
        return TERRAIN_TRAVERSAL_COLORS
    return WALKABILITY_COLORS


def _overlay_labels(overlay_name: str) -> dict[str, str]:
    if overlay_name == "traversal":
        return TRAVERSAL_LABELS
    if overlay_name == "terrain_traversal":
        return TERRAIN_TRAVERSAL_LABELS
    return WALKABILITY_LABELS


def _draw_overlay_marker(
    draw: ImageDraw.ImageDraw,
    *,
    top: list[tuple[float, float]],
    overlay_code: str,
    overlay_name: str,
) -> None:
    color = _overlay_colors(overlay_name).get(overlay_code, WALKABILITY_COLORS["structural"])
    center_x = sum(point[0] for point in top) / 4.0
    center_y = sum(point[1] for point in top) / 4.0
    width = max(4.0, abs(top[1][0] - top[0][0]) * 0.34)
    height = max(3.0, abs(top[2][1] - top[1][1]) * 0.44)
    if overlay_code == "structural":
        marker = [
            (center_x, center_y - height),
            (center_x + width, center_y),
            (center_x, center_y + height),
            (center_x - width, center_y),
        ]
        draw.polygon(marker, fill=color, outline=(22, 16, 24, 230))
        return
    radius = max(3.0, min(width, height) * 0.9)
    draw.ellipse(
        (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
        fill=color,
        outline=(20, 18, 14, 235),
        width=1,
    )


def _draw_terrain_feature(
    draw: ImageDraw.ImageDraw,
    *,
    top: list[tuple[float, float]],
    terrain: str | None,
    overlay_code: str | None,
    scale: RenderScale,
) -> None:
    """Draw a compact semantic feature above one terrain tile.

    Args:
        draw: PIL drawing context.
        top: Projected top polygon of the tile.
        terrain: Semantic terrain type.
        overlay_code: Walkability classification.
        scale: Current isometric render scale.
    """
    center_x = sum(point[0] for point in top) / 4.0
    center_y = sum(point[1] for point in top) / 4.0
    if terrain == "tree_blocker":
        _draw_tree_marker(draw, center=(center_x, center_y), scale=scale)
        return
    if terrain == "ruin_wall_blocker":
        _draw_blocked_marker(draw, top=top, color=(64, 58, 54, 225))
        return
    if overlay_code == "blocked":
        _draw_blocked_marker(draw, top=top, color=(89, 42, 38, 220))
        return
    if overlay_code == "slow":
        radius = max(1.0, scale.tile_width * 0.10)
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=(236, 195, 74, 225),
        )


def _draw_tree_marker(
    draw: ImageDraw.ImageDraw,
    *,
    center: tuple[float, float],
    scale: RenderScale,
) -> None:
    """Draw a small tree rooted on a projected terrain tile."""
    center_x, center_y = center
    tree_height = max(4.0, scale.tile_width * 0.95)
    crown_width = max(2.5, scale.tile_width * 0.34)
    trunk_width = max(1, round(scale.tile_width * 0.08))
    trunk_top = center_y - tree_height * 0.52
    draw.line(
        (center_x, center_y, center_x, trunk_top),
        fill=(91, 61, 36, 245),
        width=trunk_width,
    )
    lower_y = center_y - tree_height * 0.38
    middle_y = center_y - tree_height * 0.64
    top_y = center_y - tree_height
    outline = (18, 47, 22, 235)
    draw.polygon(
        [
            (center_x, top_y),
            (center_x + crown_width * 0.72, middle_y),
            (center_x - crown_width * 0.72, middle_y),
        ],
        fill=(43, 112, 48, 245),
        outline=outline,
    )
    draw.polygon(
        [
            (center_x, middle_y - tree_height * 0.18),
            (center_x + crown_width, lower_y),
            (center_x - crown_width, lower_y),
        ],
        fill=TERRAIN_TRAVERSAL_COLORS["tree"],
        outline=outline,
    )


def _draw_blocked_marker(
    draw: ImageDraw.ImageDraw,
    *,
    top: list[tuple[float, float]],
    color: tuple[int, int, int, int],
) -> None:
    """Draw a compact cross on a blocked non-tree tile."""
    draw.line((top[0], top[2]), fill=color, width=1)
    draw.line((top[1], top[3]), fill=color, width=1)


def _level_color(level: int) -> tuple[int, int, int, int]:
    clamped = max(ELEVATION_FORMAT_MIN_LEVEL, min(ELEVATION_FORMAT_MAX_LEVEL, level))
    return ELEVATION_COLORS.get(clamped, ELEVATION_COLORS[0])


def _shade_color(color: tuple[int, int, int, int], factor: float) -> tuple[int, int, int, int]:
    red, green, blue, alpha = color
    return (
        max(0, min(255, int(red * factor))),
        max(0, min(255, int(green * factor))),
        max(0, min(255, int(blue * factor))),
        alpha,
    )


def _blend_color(
    base: tuple[int, int, int, int],
    tint: tuple[int, int, int, int],
    weight: float,
) -> tuple[int, int, int, int]:
    """Blend a diagnostic tint while preserving the elevation color signal."""
    clamped = max(0.0, min(1.0, weight))
    return (
        round(base[0] * (1.0 - clamped) + tint[0] * clamped),
        round(base[1] * (1.0 - clamped) + tint[1] * clamped),
        round(base[2] * (1.0 - clamped) + tint[2] * clamped),
        base[3],
    )


def _read_walkability_data(
    *,
    output_root: Path,
    package_dir: Path,
    map_index: dict[str, Any],
    geography: dict[str, Any],
    width: int,
    height: int,
) -> OverlayData:
    runtime_grids = _read_object(_package_ref_path(package_dir, map_index.get("runtime_grids")))
    terrain_layer = _read_object(_package_ref_path(package_dir, _require_object(map_index, "layers").get("terrain")))
    collision_rows = _read_collision_rows(runtime_grids, width=width, height=height)
    movement_rows = _read_movement_rows(runtime_grids, width=width, height=height)
    terrain_rows = _read_terrain_rows(terrain_layer, width=width, height=height)
    source_rows = _read_source_rows(geography, width=width, height=height)
    water_rows = _read_water_rows(geography, width=width, height=height)
    start = _read_point(_optional_object(map_index.get("points")).get("start"))
    goal = _read_point(_optional_object(map_index.get("points")).get("goal"))
    reachable = _reachable_points(
        start,
        collision_rows=collision_rows,
        movement_rows=movement_rows,
        width=width,
        height=height,
    )
    rows: list[list[str]] = []
    counts: Counter[str] = Counter()
    for y in range(height):
        output_row: list[str] = []
        for x in range(width):
            key = _walkability_code(
                x,
                y,
                collision_rows=collision_rows,
                movement_rows=movement_rows,
                terrain_rows=terrain_rows,
                source_rows=source_rows,
                water_rows=water_rows,
                reachable=reachable,
                start=start,
                goal=goal,
            )
            output_row.append(key)
            counts[key] += 1
        rows.append(output_row)
    _write_walkability_report(
        output_root / "geography_3d_preview" / "walkability_report.json",
        counts=counts,
        start=start,
        goal=goal,
        total=width * height,
    )
    return OverlayData(overlay_rows=rows, counts=dict(counts))


def _read_terrain_traversal_data(
    *,
    output_root: Path,
    package_dir: Path,
    map_index: dict[str, Any],
    geography: dict[str, Any],
    width: int,
    height: int,
) -> OverlayData:
    """Load semantic terrain and 2D walkability for the combined preview."""
    runtime_grids = _read_object(_package_ref_path(package_dir, map_index.get("runtime_grids")))
    terrain_layer = _read_object(
        _package_ref_path(package_dir, _require_object(map_index, "layers").get("terrain"))
    )
    collision_rows = _read_collision_rows(runtime_grids, width=width, height=height)
    movement_rows = _read_movement_rows(runtime_grids, width=width, height=height)
    terrain_rows = _read_terrain_rows(terrain_layer, width=width, height=height)
    source_rows = _read_source_rows(geography, width=width, height=height)
    water_rows = _read_water_rows(geography, width=width, height=height)
    start = _read_point(_optional_object(map_index.get("points")).get("start"))
    goal = _read_point(_optional_object(map_index.get("points")).get("goal"))
    reachable = _reachable_points(
        start,
        collision_rows=collision_rows,
        movement_rows=movement_rows,
        width=width,
        height=height,
    )
    rows: list[list[str]] = []
    counts: Counter[str] = Counter()
    for y in range(height):
        output_row: list[str] = []
        for x in range(width):
            key = _walkability_code(
                x,
                y,
                collision_rows=collision_rows,
                movement_rows=movement_rows,
                terrain_rows=terrain_rows,
                source_rows=source_rows,
                water_rows=water_rows,
                reachable=reachable,
                start=start,
                goal=goal,
            )
            output_row.append(key)
            counts[key] += 1
            if terrain_rows[y][x] == "tree_blocker":
                counts["tree"] += 1
        rows.append(output_row)
    _write_terrain_traversal_report(
        output_root / "geography_3d_preview" / "terrain_traversal_report.json",
        counts=counts,
        start=start,
        goal=goal,
        total=width * height,
    )
    return OverlayData(
        overlay_rows=rows,
        counts=dict(counts),
        terrain_rows=terrain_rows,
    )


def _walkability_code(
    x: int,
    y: int,
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    terrain_rows: list[list[str]],
    source_rows: list[str],
    water_rows: list[str],
    reachable: set[tuple[int, int]],
    start: tuple[int, int] | None,
    goal: tuple[int, int] | None,
) -> str:
    point = (x, y)
    if start == point:
        return "start"
    if goal == point:
        return "goal"
    movement = movement_rows[y][x]
    terrain = terrain_rows[y][x]
    source = source_rows[y][x] if y < len(source_rows) and x < len(source_rows[y]) else "G"
    water = water_rows[y][x] if y < len(water_rows) and x < len(water_rows[y]) else "D"
    passable = collision_rows[y][x] != "1" and movement is not None
    if not passable:
        return "blocked"
    if source == "S" or water == "X":
        return "structural"
    if source == "W" or water in {"B", "S"} or terrain == "water_slow":
        return "water"
    if point not in reachable:
        return "unreachable"
    if isinstance(movement, int | float) and movement > 1:
        return "slow"
    return "reachable"


def _reachable_points(
    start: tuple[int, int] | None,
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    if start is None:
        return set()
    sx, sy = start
    if not (0 <= sx < width and 0 <= sy < height):
        return set()
    if collision_rows[sy][sx] == "1" or movement_rows[sy][sx] is None:
        return set()
    visited = {(sx, sy)}
    queue: deque[tuple[int, int]] = deque([(sx, sy)])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in visited:
                continue
            if collision_rows[ny][nx] == "1" or movement_rows[ny][nx] is None:
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))
    return visited




def _read_traversal_data(
    *,
    output_root: Path,
    package_dir: Path,
    map_index: dict[str, Any],
    geography: dict[str, Any],
    geographic_rows: list[list[int]],
    width: int,
    height: int,
) -> OverlayData:
    runtime_grids = _read_object(_package_ref_path(package_dir, map_index.get("runtime_grids")))
    terrain_layer = _read_object(_package_ref_path(package_dir, _require_object(map_index, "layers").get("terrain")))
    collision_rows = _read_collision_rows(runtime_grids, width=width, height=height)
    movement_rows = _read_movement_rows(runtime_grids, width=width, height=height)
    terrain_rows = _read_terrain_rows(terrain_layer, width=width, height=height)
    source_rows = _read_source_rows(geography, width=width, height=height)
    water_rows = _read_water_rows(geography, width=width, height=height)
    start = _read_point(_optional_object(map_index.get("points")).get("start"))
    goal = _read_point(_optional_object(map_index.get("points")).get("goal"))
    reachable_2d = _reachable_points_2d_enterable(
        start,
        collision_rows=collision_rows,
        movement_rows=movement_rows,
        source_rows=source_rows,
        width=width,
        height=height,
    )
    reachable = _reachable_points_3d(
        start,
        collision_rows=collision_rows,
        movement_rows=movement_rows,
        source_rows=source_rows,
        geographic_rows=geographic_rows,
        width=width,
        height=height,
        max_delta=DEFAULT_TRAVERSAL_RULES.max_natural_delta,
    )
    cliff_edges = _count_passable_cliff_edges(
        collision_rows=collision_rows,
        movement_rows=movement_rows,
        source_rows=source_rows,
        geographic_rows=geographic_rows,
        width=width,
        height=height,
        max_delta=DEFAULT_TRAVERSAL_RULES.max_natural_delta,
    )
    rows: list[list[str]] = []
    counts: Counter[str] = Counter()
    two_d_walkable = 0
    for y in range(height):
        output_row: list[str] = []
        for x in range(width):
            if _is_2d_passable(x, y, collision_rows=collision_rows, movement_rows=movement_rows):
                two_d_walkable += 1
            key = _traversal_code(
                x,
                y,
                collision_rows=collision_rows,
                movement_rows=movement_rows,
                terrain_rows=terrain_rows,
                source_rows=source_rows,
                water_rows=water_rows,
                geographic_rows=geographic_rows,
                reachable_2d=reachable_2d,
                reachable=reachable,
                start=start,
                goal=goal,
            )
            output_row.append(key)
            counts[key] += 1
        rows.append(output_row)
    goal_reachable = goal in reachable if goal is not None else False
    _write_traversal_report(
        output_root / "geography_3d_preview" / "traversal_report.json",
        counts=counts,
        start=start,
        goal=goal,
        total=width * height,
        two_d_walkable=two_d_walkable,
        two_d_reachable=len(reachable_2d),
        reachable_3d=len(reachable),
        cliff_edges=cliff_edges,
        goal_reachable=goal_reachable,
    )
    return OverlayData(overlay_rows=rows, counts=dict(counts))


def _traversal_code(
    x: int,
    y: int,
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    terrain_rows: list[list[str]],
    source_rows: list[str],
    water_rows: list[str],
    geographic_rows: list[list[int]],
    reachable_2d: set[tuple[int, int]],
    reachable: set[tuple[int, int]],
    start: tuple[int, int] | None,
    goal: tuple[int, int] | None,
) -> str:
    point = (x, y)
    if start == point:
        return "start"
    if goal == point:
        return "goal"
    source = source_rows[y][x] if y < len(source_rows) and x < len(source_rows[y]) else "G"
    water = water_rows[y][x] if y < len(water_rows) and x < len(water_rows[y]) else "D"
    terrain = terrain_rows[y][x]
    if _is_structural_source(source=source, water=water):
        return "structural"
    if not _is_2d_passable(x, y, collision_rows=collision_rows, movement_rows=movement_rows):
        return "blocked"
    if _is_water_source(source=source, water=water, terrain=terrain):
        return "water"
    if point not in reachable_2d:
        return "terrain_island"
    if point not in reachable:
        if _touches_reachable_cliff(
            x,
            y,
            reachable=reachable,
            collision_rows=collision_rows,
            movement_rows=movement_rows,
            source_rows=source_rows,
            geographic_rows=geographic_rows,
            max_delta=DEFAULT_TRAVERSAL_RULES.max_natural_delta,
        ):
            return "too_steep"
        return "unreachable"
    movement = movement_rows[y][x]
    if isinstance(movement, int | float) and movement > 1:
        return "slope"
    if _has_reachable_slope_neighbor(x, y, reachable=reachable, geographic_rows=geographic_rows):
        return "slope"
    return "reachable"


def _reachable_points_3d(
    start: tuple[int, int] | None,
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    source_rows: list[str],
    geographic_rows: list[list[int]],
    width: int,
    height: int,
    max_delta: int,
) -> set[tuple[int, int]]:
    if start is None:
        return set()
    sx, sy = start
    if not (0 <= sx < width and 0 <= sy < height):
        return set()
    if not _can_enter_3d(sx, sy, collision_rows=collision_rows, movement_rows=movement_rows, source_rows=source_rows):
        return set()
    visited = {(sx, sy)}
    queue: deque[tuple[int, int]] = deque([(sx, sy)])
    while queue:
        x, y = queue.popleft()
        current_level = geographic_rows[y][x]
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in visited:
                continue
            if not _can_enter_3d(nx, ny, collision_rows=collision_rows, movement_rows=movement_rows, source_rows=source_rows):
                continue
            if abs(geographic_rows[ny][nx] - current_level) > max_delta:
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))
    return visited


def _reachable_points_2d_enterable(
    start: tuple[int, int] | None,
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    source_rows: list[str],
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    if start is None:
        return set()
    sx, sy = start
    if not (0 <= sx < width and 0 <= sy < height):
        return set()
    if not _can_enter_3d(sx, sy, collision_rows=collision_rows, movement_rows=movement_rows, source_rows=source_rows):
        return set()
    visited = {(sx, sy)}
    queue: deque[tuple[int, int]] = deque([(sx, sy)])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in visited:
                continue
            if not _can_enter_3d(nx, ny, collision_rows=collision_rows, movement_rows=movement_rows, source_rows=source_rows):
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))
    return visited


def _can_enter_3d(
    x: int,
    y: int,
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    source_rows: list[str],
) -> bool:
    if not _is_2d_passable(x, y, collision_rows=collision_rows, movement_rows=movement_rows):
        return False
    source = source_rows[y][x] if y < len(source_rows) and x < len(source_rows[y]) else "G"
    return source != "S"


def _is_2d_passable(
    x: int,
    y: int,
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
) -> bool:
    return collision_rows[y][x] != "1" and movement_rows[y][x] is not None


def _is_structural_source(*, source: str, water: str) -> bool:
    return source == "S" or water == "X"


def _is_water_source(*, source: str, water: str, terrain: str) -> bool:
    return source == "W" or water in {"B", "S"} or terrain == "water_slow"


def _touches_reachable_cliff(
    x: int,
    y: int,
    *,
    reachable: set[tuple[int, int]],
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    source_rows: list[str],
    geographic_rows: list[list[int]],
    max_delta: int,
) -> bool:
    current_level = geographic_rows[y][x]
    width = len(geographic_rows[0]) if geographic_rows else 0
    height = len(geographic_rows)
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if not (0 <= nx < width and 0 <= ny < height):
            continue
        if (nx, ny) not in reachable:
            continue
        if not _can_enter_3d(nx, ny, collision_rows=collision_rows, movement_rows=movement_rows, source_rows=source_rows):
            continue
        if abs(geographic_rows[ny][nx] - current_level) > max_delta:
            return True
    return False


def _has_reachable_slope_neighbor(
    x: int,
    y: int,
    *,
    reachable: set[tuple[int, int]],
    geographic_rows: list[list[int]],
) -> bool:
    current_level = geographic_rows[y][x]
    width = len(geographic_rows[0]) if geographic_rows else 0
    height = len(geographic_rows)
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if not (0 <= nx < width and 0 <= ny < height):
            continue
        if (nx, ny) in reachable and abs(geographic_rows[ny][nx] - current_level) == 1:
            return True
    return False


def _count_passable_cliff_edges(
    *,
    collision_rows: list[str],
    movement_rows: list[list[float | None]],
    source_rows: list[str],
    geographic_rows: list[list[int]],
    width: int,
    height: int,
    max_delta: int,
) -> int:
    count = 0
    for y in range(height):
        for x in range(width):
            if not _can_enter_3d(x, y, collision_rows=collision_rows, movement_rows=movement_rows, source_rows=source_rows):
                continue
            current_level = geographic_rows[y][x]
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if not _can_enter_3d(nx, ny, collision_rows=collision_rows, movement_rows=movement_rows, source_rows=source_rows):
                    continue
                if abs(geographic_rows[ny][nx] - current_level) > max_delta:
                    count += 1
    return count


def _write_traversal_report(
    path: Path,
    *,
    counts: Counter[str],
    start: tuple[int, int] | None,
    goal: tuple[int, int] | None,
    total: int,
    two_d_walkable: int,
    two_d_reachable: int,
    reachable_3d: int,
    cliff_edges: int,
    goal_reachable: bool,
) -> None:
    unreachable_walkable = int(counts.get("unreachable", 0)) + int(counts.get("too_steep", 0))
    _write_overlay_report(
        path,
        schema_version="3d-traversal-preview-report-v1",
        labels=TRAVERSAL_LABELS,
        counts=counts,
        start=start,
        goal=goal,
        total=total,
        extra={
            "rules": {
                "max_natural_delta": DEFAULT_TRAVERSAL_RULES.max_natural_delta,
                "structural_depth": "marker_only_not_geographic_traversal",
                "water": "classified_separately_from_structural_depth",
            },
            "summary": {
                "two_d_walkable_tiles": two_d_walkable,
                "two_d_reachable_tiles": two_d_reachable,
                "two_d_terrain_island_tiles": int(counts.get("terrain_island", 0)),
                "three_d_reachable_tiles": reachable_3d,
                "unreachable_walkable_tiles": unreachable_walkable,
                "too_steep_tiles": int(counts.get("too_steep", 0)),
                "passable_cliff_edges": cliff_edges,
                "goal_reachable_3d": goal_reachable,
            },
        },
    )

def _write_terrain_traversal_report(
    path: Path,
    *,
    counts: Counter[str],
    start: tuple[int, int] | None,
    goal: tuple[int, int] | None,
    total: int,
) -> None:
    """Write category counts for the combined terrain/traversal preview."""
    _write_overlay_report(
        path,
        schema_version="3d-terrain-traversal-preview-report-v1",
        labels=TERRAIN_TRAVERSAL_LABELS,
        counts=counts,
        start=start,
        goal=goal,
        total=total,
        extra={
            "rendering": {
                "elevation_color_preserved": True,
                "semantic_terrain_tints": True,
                "tree_blockers_rendered_as_objects": True,
            }
        },
    )


def _write_walkability_report(
    path: Path,
    *,
    counts: Counter[str],
    start: tuple[int, int] | None,
    goal: tuple[int, int] | None,
    total: int,
) -> None:
    _write_overlay_report(
        path,
        schema_version="3d-walkability-preview-report-v1",
        labels=WALKABILITY_LABELS,
        counts=counts,
        start=start,
        goal=goal,
        total=total,
        extra={},
    )


def _write_overlay_report(
    path: Path,
    *,
    schema_version: str,
    labels: dict[str, str],
    counts: Counter[str],
    start: tuple[int, int] | None,
    goal: tuple[int, int] | None,
    total: int,
    extra: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "start": _point_payload(start),
        "goal": _point_payload(goal),
        "total_tiles": total,
        "categories": {
            key: {
                "label": labels[key],
                "count": int(counts.get(key, 0)),
                "percent": round(int(counts.get(key, 0)) * 100.0 / total, 3) if total > 0 else 0.0,
            }
            for key in labels
        },
    }
    payload.update(extra)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

def _point_payload(point: tuple[int, int] | None) -> dict[str, int] | None:
    if point is None:
        return None
    return {"x": point[0], "y": point[1]}


def _read_point(value: Any) -> tuple[int, int] | None:
    point = _optional_object(value)
    x = point.get("x")
    y = point.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return (x, y)
    return None


def _read_collision_rows(runtime_grids: dict[str, Any], *, width: int, height: int) -> list[str]:
    rows = _optional_object(_optional_object(runtime_grids.get("grids")).get("collision_grid")).get("rows")
    if not isinstance(rows, list):
        return ["1" * width for _ in range(height)]
    output = [row[:width] for row in rows[:height] if isinstance(row, str) and len(row) >= width]
    if len(output) != height:
        raise ValueError("collision_grid size mismatch")
    return output


def _read_movement_rows(runtime_grids: dict[str, Any], *, width: int, height: int) -> list[list[float | None]]:
    rows = _optional_object(_optional_object(runtime_grids.get("grids")).get("movement_grid")).get("rows")
    if not isinstance(rows, list):
        return [[None for _ in range(width)] for _ in range(height)]
    output: list[list[float | None]] = []
    for row_index, row in enumerate(rows[:height]):
        if not isinstance(row, list):
            raise ValueError(f"movement_grid row {row_index} must be a list")
        values: list[float | None] = []
        for value in row[:width]:
            values.append(float(value) if isinstance(value, int | float) else None)
        if len(values) != width:
            raise ValueError(f"movement_grid width mismatch at row {row_index}")
        output.append(values)
    if len(output) != height:
        raise ValueError("movement_grid height mismatch")
    return output


def _read_terrain_rows(terrain_layer: dict[str, Any], *, width: int, height: int) -> list[list[str]]:
    rows = terrain_layer.get("rows")
    if not isinstance(rows, list):
        return [["unknown" for _ in range(width)] for _ in range(height)]
    output: list[list[str]] = []
    for row in rows[:height]:
        if isinstance(row, list):
            output.append([str(value) for value in row[:width]])
    if len(output) != height or any(len(row) != width for row in output):
        raise ValueError("terrain layer size mismatch")
    return output


def _read_source_rows(geography: dict[str, Any], *, width: int, height: int) -> list[str]:
    source_grid = _optional_object(_optional_object(geography.get("grids")).get("source_grid"))
    rows = source_grid.get("rows")
    if isinstance(rows, list):
        output = [row[:width] for row in rows[:height] if isinstance(row, str) and len(row) >= width]
        if len(output) == height:
            return output
    return ["G" * width for _ in range(height)]


def _read_water_rows(geography: dict[str, Any], *, width: int, height: int) -> list[str]:
    water_grid = _optional_object(_optional_object(geography.get("grids")).get("water_lowland_grid"))
    rows = water_grid.get("rows")
    if isinstance(rows, list):
        output = [row[:width] for row in rows[:height] if isinstance(row, str) and len(row) >= width]
        if len(output) == height:
            return output
    return ["D" * width for _ in range(height)]


def _resolve_map_json_path(path: Path) -> Path:
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


def _map_json_from_manifest(path: Path) -> Path:
    manifest = _read_object(path)
    for entry in _optional_list(manifest.get("primary_outputs")):
        if not isinstance(entry, dict):
            continue
        if entry.get("kind") == "map_package:index":
            raw_path = entry.get("path")
            if isinstance(raw_path, str):
                return _require_file((path.parent / raw_path).resolve())
    return _require_file(path.parent / "map_package" / "map.json")


def _read_runtime_height_rows(
    package_dir: Path,
    map_index: dict[str, Any],
    *,
    width: int,
    height: int,
) -> list[list[int]]:
    runtime_path = _package_ref_path(package_dir, map_index.get("runtime_grids"))
    runtime_grids = _read_object(runtime_path)
    rows = _optional_object(_optional_object(runtime_grids.get("grids")).get("height_grid")).get("rows")
    return _read_int_rows(rows, width=width, height=height, label="runtime height_grid")


def _read_generation_report(output_root: Path) -> dict[str, Any]:
    tactical_map = _read_object(output_root / "tactical_map.json")
    generation_report = _optional_object(tactical_map.get("elevation_generation_report"))
    if not generation_report:
        raise ValueError("tactical_map.json lacks elevation_generation_report")
    return generation_report


def _read_geographic_height_rows(
    geography: dict[str, Any],
    *,
    fallback_rows: list[list[int]],
    width: int,
    height: int,
) -> list[list[int]]:
    rows = _optional_object(_optional_object(geography.get("grids")).get("geographic_level_grid")).get("rows")
    if rows is None:
        return fallback_rows
    return _read_int_rows(rows, width=width, height=height, label="geographic_level_grid")


def _read_int_rows(value: Any, *, width: int, height: int, label: str) -> list[list[int]]:
    if not isinstance(value, list):
        raise ValueError(f"Expected {label}.rows to be a list")
    output: list[list[int]] = []
    for row_index, row in enumerate(value[:height]):
        if not isinstance(row, list):
            raise ValueError(f"Expected {label} row {row_index} to be a list")
        values = [int(cell) for cell in row[:width] if isinstance(cell, int | float)]
        if len(values) != width:
            raise ValueError(f"{label} width mismatch at row {row_index}: expected {width}, got {len(values)}")
        output.append(values)
    if len(output) != height:
        raise ValueError(f"{label} height mismatch: expected {height}, got {len(output)}")
    return output


def _package_ref_path(package_dir: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Expected package file reference")
    return _require_file((package_dir / value).resolve())


def _default_output_dir(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_dir() and candidate.name != "map_package":
        return candidate / DEFAULT_OUTPUT_DIR_NAME
    map_json = _resolve_map_json_path(path)
    return map_json.parent.parent / DEFAULT_OUTPUT_DIR_NAME


def _read_seed(output_root: Path) -> int | None:
    summary = _read_optional_object(output_root / "world_summary_report.json")
    generation = _optional_object(summary.get("world_generation"))
    seed = generation.get("seed")
    return seed if isinstance(seed, int) else None


def _read_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _read_optional_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_object(path)


def _require_file(path: Path) -> Path:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def _require_object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object field: {key}")
    return value


def _optional_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _require_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Expected integer field: {key}")
    return value


def _read_int_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    first, second = value
    if isinstance(first, int | float) and isinstance(second, int | float):
        return (int(first), int(second))
    return None


def _normalize_views(raw_views: Sequence[str]) -> list[str]:
    output: list[str] = []
    for raw_view in raw_views:
        for part in raw_view.split(","):
            view = part.strip().lower()
            if not view:
                continue
            if view not in VIEW_LABELS:
                raise ValueError(f"Unsupported view: {view}")
            if view not in output:
                output.append(view)
    return output or list(DEFAULT_VIEWS)


def _output_filename(overlay: str, view: str) -> str:
    if overlay == "geography":
        return f"view_{view}.png"
    return f"{overlay}_{view}.png"


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render 2560x1440 pseudo-3D geographic previews from four map corners.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Output directory, _manifest.json, map_package directory, or map.json path.",
    )
    parser.add_argument(
        "--overlay",
        choices=("geography", "walkability", "traversal", "terrain_traversal"),
        default="geography",
        help="Diagnostic overlay to render. Default: geography.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for generated preview PNG files. Defaults to <output-root>/geography_3d_preview.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=OUTPUT_SIZE_DEFAULT[0],
        help="Output image width in pixels. Default: 2560.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=OUTPUT_SIZE_DEFAULT[1],
        help="Output image height in pixels. Default: 1440.",
    )
    parser.add_argument(
        "--views",
        nargs="*",
        default=list(DEFAULT_VIEWS),
        help="Views to render: nw ne se sw. Comma-separated values are also accepted.",
    )
    parser.add_argument(
        "--no-grid",
        action="store_true",
        help="Disable subtle top-face grid lines.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
