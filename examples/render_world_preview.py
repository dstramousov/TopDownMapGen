#!/usr/bin/env python3
"""Render a simple PNG preview from a generated TopDownMapGen world package."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

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
BUNKER_FILL_COLOR = (94, 78, 62, 245)
BUNKER_OUTLINE_COLOR = (255, 238, 120, 255)
BUNKER_TEXT_COLOR = (255, 245, 190, 255)
OBJECT_FOOTPRINT_COLOR = (255, 236, 150, 120)
OBJECT_COLLISION_FOOTPRINT_COLOR = (255, 160, 80, 140)
OBJECT_VISUAL_BOUNDS_COLOR = (255, 255, 255, 105)
FIRING_PORT_COLOR = (255, 235, 70, 255)
START_COLOR = (70, 230, 100, 255)
GOAL_COLOR = (240, 80, 70, 255)
GRID_COLOR = (0, 0, 0, 35)
ELEVATION_FORMAT_MIN_LEVEL = -5
ELEVATION_FORMAT_MAX_LEVEL = 20
ELEVATION_LEGEND_PANEL_WIDTH_PX = 380
ELEVATION_LEGEND_BACKGROUND = (30, 31, 28, 255)
ELEVATION_LEGEND_TEXT = (232, 230, 216, 255)
ELEVATION_LEGEND_MUTED_TEXT = (174, 170, 151, 255)
ELEVATION_LEGEND_BAR = (220, 216, 190, 255)
ELEVATION_LEGEND_BAR_BACKGROUND = (66, 64, 56, 255)
ELEVATION_CONTOUR_COLOR = (35, 35, 30, 105)
ELEVATION_ZERO_OVERLAY_ALPHA = 0
ELEVATION_OVERLAY_ALPHA = 145
ELEVATION_OPAQUE_COLORS: dict[int, tuple[int, int, int, int]] = {
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
GEOGRAPHY_COLORS: dict[str, tuple[int, int, int, int]] = {
    "B": (54, 104, 150, 255),
    "L": (78, 151, 176, 255),
    "P": (99, 148, 80, 255),
    "H": (168, 181, 88, 255),
    "T": (204, 173, 83, 255),
    "R": (157, 103, 68, 255),
    "M": (122, 101, 88, 255),
    "K": (231, 230, 218, 255),
}
GEOGRAPHY_FALLBACK_COLOR = (90, 90, 84, 255)
SLOPE_COLORS: dict[int, tuple[int, int, int, int]] = {
    0: (94, 145, 76, 255),
    1: (190, 184, 92, 255),
    2: (196, 116, 67, 255),
    3: (136, 62, 57, 255),
}
ELEVATION_SOURCE_COLORS: dict[str, tuple[int, int, int, int]] = {
    "G": (92, 146, 78, 255),
    "W": (42, 105, 177, 255),
    "S": (136, 96, 164, 255),
}
ELEVATION_SOURCE_LABELS: dict[str, str] = {
    "G": "geography",
    "W": "water",
    "S": "structural",
}
WATER_LOWLAND_COLORS: dict[str, tuple[int, int, int, int]] = {
    "B": (12, 48, 122, 255),
    "S": (52, 126, 190, 255),
    "W": (70, 151, 145, 255),
    "L": (122, 171, 124, 255),
    "D": (101, 143, 82, 255),
    "X": (136, 96, 164, 255),
}
WATER_LOWLAND_LABELS: dict[str, str] = {
    "B": "deep water",
    "S": "shallow water",
    "W": "wet lowland",
    "L": "dry lowland",
    "D": "dry land",
    "X": "structural",
}
WATER_ELEVATION_COLORS: dict[int, tuple[int, int, int, int]] = {
    -5: (8, 25, 84, 255),
    -4: (12, 43, 119, 255),
    -3: (16, 66, 150, 255),
    -2: (24, 91, 176, 255),
    -1: (44, 124, 200, 255),
    0: (68, 152, 207, 255),
}
STRUCTURAL_ELEVATION_COLORS: dict[int, tuple[int, int, int, int]] = {
    -5: (52, 42, 79, 255),
    -4: (70, 52, 98, 255),
    -3: (89, 62, 118, 255),
    -2: (110, 73, 140, 255),
    -1: (134, 88, 164, 255),
}

TRANSITION_COLORS: dict[str, tuple[int, int, int, int]] = {
    "connector_edge": (120, 240, 120, 240),
    "bridge_edge": (120, 210, 255, 240),
    "step_up": (255, 215, 80, 220),
    "step_down": (100, 170, 255, 220),
    "steep_transition": (255, 80, 80, 240),
}
TRANSITION_TEXT_COLOR = (255, 255, 255, 255)
PLACE_OUTLINE_COLOR = (255, 255, 255, 230)
PLACE_TEXT_COLOR = (255, 255, 255, 255)
GAMEPLAY_ZONE_FILL_COLORS: dict[str, tuple[int, int, int, int]] = {
    "safe_area": (70, 220, 110, 70),
    "encounter_area": (240, 190, 80, 70),
    "ambush_area": (255, 120, 60, 80),
    "loot_area": (255, 230, 80, 80),
    "boss_area": (230, 70, 70, 95),
    "stealth_area": (80, 170, 120, 75),
    "traversal_area": (120, 190, 255, 75),
    "secret_area": (190, 100, 255, 85),
    "danger_area": (255, 80, 80, 80),
    "story_area": (180, 150, 255, 75),
    "extraction_area": (90, 230, 200, 80),
}
GAMEPLAY_ZONE_OUTLINE_COLOR = (255, 255, 255, 180)
WORLD_GRAPH_EDGE_COLOR = (255, 255, 255, 190)
WORLD_GRAPH_MAIN_PATH_COLOR = (255, 245, 80, 240)
WORLD_GRAPH_NODE_COLOR = (255, 255, 255, 230)
ROUTE_COLORS: dict[str, tuple[int, int, int, int]] = {
    "main_road": (255, 245, 80, 240),
    "side_path": (120, 230, 255, 220),
    "hidden_path": (210, 120, 255, 230),
    "patrol_route": (255, 150, 70, 210),
    "escape_route": (110, 255, 160, 220),
}
ROUTE_FALLBACK_COLOR = (255, 255, 255, 210)


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
        multi_tile_objects: Number of runtime objects with multi-cell footprints.
        elevation_levels: Elevation levels observed in height_grid.
        elevation_level_counts: Number of tiles per elevation level.
        elevation_total_tiles: Number of tiles included in elevation statistics.
        elevation_transitions: Number of elevation transitions read.
        places: Number of semantic places read.
        gameplay_zones: Number of gameplay zones read.
        routes: Number of semantic routes read.
        world_graph_edges: Number of world graph edges read.
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
    multi_tile_objects: int
    elevation_levels: list[int]
    elevation_level_counts: dict[int, int]
    elevation_total_tiles: int
    elevation_transitions: int
    places: int
    gameplay_zones: int
    routes: int
    world_graph_edges: int
    start: dict[str, int] | None
    goal: dict[str, int] | None


def render_preview(
    package_path: Path,
    *,
    output_path: Path | None = None,
    cell_size_px: int = 4,
    draw_objects: bool = True,
    draw_collision_overlay: bool = False,
    draw_elevation_overlay: bool = False,
    draw_transition_overlay: bool = False,
    draw_places_overlay: bool = False,
    draw_gameplay_zones_overlay: bool = False,
    draw_routes_overlay: bool = False,
    draw_world_graph_overlay: bool = False,
    draw_grid: bool = False,
    draw_elevation_legend: bool = False,
    draw_elevation_only: bool = False,
    draw_elevation_contours: bool = False,
    draw_moisture_only: bool = False,
    draw_slope_only: bool = False,
    draw_geography_only: bool = False,
    draw_source_only: bool = False,
    draw_water_lowlands_only: bool = False,
) -> PreviewSummary:
    """Render a simple PNG preview from public world package files.

    Args:
        package_path: Output directory, manifest path, map_package directory, or map.json.
        output_path: Optional PNG output path. Defaults to output root/world_preview.png.
        cell_size_px: Rendered preview cell size in pixels.
        draw_objects: Whether to draw runtime object markers.
        draw_collision_overlay: Whether to overlay blocked cells.
        draw_elevation_overlay: Whether to overlay height_grid levels.
        draw_transition_overlay: Whether to draw elevation transitions.
        draw_places_overlay: Whether to draw semantic places.
        draw_gameplay_zones_overlay: Whether to draw neutral gameplay zones.
        draw_routes_overlay: Whether to draw semantic routes.
        draw_world_graph_overlay: Whether to draw world graph nodes and edges.
        draw_grid: Whether to draw a light tile grid.
        draw_elevation_legend: Whether to append a right-side elevation legend panel.
        draw_elevation_only: Whether to render height_grid as the base map.
        draw_elevation_contours: Whether to draw contour lines on elevation boundaries.
        draw_moisture_only: Whether to render the moisture field as the base map.
        draw_slope_only: Whether to render slope categories as the base map.
        draw_geography_only: Whether to render geographic masks as the base map.
        draw_source_only: Whether to render elevation source classes as the base map.
        draw_water_lowlands_only: Whether to render standing water and lowland classes.

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
    places = _read_optional_package_object(package_dir, objects.get("places"))
    world_graph = _read_optional_package_object(package_dir, map_index.get("world_graph"))
    routes = _read_optional_package_object(package_dir, map_index.get("routes"))
    gameplay_zones = _read_optional_package_object(
        package_dir,
        map_index.get("gameplay_zones"),
    )
    runtime_grids = _read_optional_package_object(
        package_dir,
        map_index.get("runtime_grids"),
    )
    elevation_transitions = _read_optional_package_object(
        package_dir,
        map_index.get("elevation_transitions"),
    )

    terrain_rows = _read_type_rows(terrain, width=width, height=height)
    collision_rows = _read_collision_rows(collision, width=width, height=height)
    height_rows = _read_height_rows(runtime_grids, width=width, height=height)
    transition_items = _optional_list(elevation_transitions.get("items"))
    object_items = _optional_list(runtime_objects.get("items"))
    place_items = _optional_list(places.get("items"))
    gameplay_zone_items = _optional_list(gameplay_zones.get("items"))
    route_items = _optional_list(routes.get("items"))
    world_graph_edges = _optional_list(world_graph.get("edges"))
    start = _optional_point(start_goal.get("start"))
    goal = _optional_point(start_goal.get("goal"))
    level_counts = _elevation_level_counts(height_rows)
    elevation_report = _read_optional_output_object(root / "elevation_density_report.json")
    geography_report = _read_generation_geography(root)
    source_rows = _read_elevation_source_rows(geography_report, width=width, height=height)
    geographic_height_rows = _read_geographic_height_rows(
        geography_report,
        height_rows=height_rows,
        width=width,
        height=height,
    )

    map_width_px = width * cell_size_px
    map_height_px = height * cell_size_px
    legend_width_px = _legend_panel_width(map_width_px) if draw_elevation_legend else 0
    image = Image.new(
        "RGBA",
        (map_width_px + legend_width_px, map_height_px),
        FALLBACK_TERRAIN_COLOR,
    )
    draw = ImageDraw.Draw(image, "RGBA")

    geography_base_only = (
        draw_elevation_only
        or draw_moisture_only
        or draw_slope_only
        or draw_geography_only
        or draw_source_only
        or draw_water_lowlands_only
    )
    if draw_moisture_only:
        _draw_moisture_base_map(
            draw,
            moisture_rows=_read_moisture_rows(geography_report, width=width, height=height),
            height_rows=height_rows,
            cell_size_px=cell_size_px,
        )
    elif draw_slope_only:
        _draw_slope_base_map(
            draw,
            slope_rows=_read_slope_rows(geography_report, height_rows=height_rows, width=width, height=height),
            cell_size_px=cell_size_px,
        )
    elif draw_geography_only:
        _draw_geography_base_map(
            draw,
            mask_rows=_read_geography_mask_rows(
                geography_report,
                height_rows=geographic_height_rows,
                width=width,
                height=height,
            ),
            cell_size_px=cell_size_px,
        )
    elif draw_source_only:
        _draw_elevation_source_base_map(
            draw,
            source_rows=source_rows,
            cell_size_px=cell_size_px,
        )
    elif draw_water_lowlands_only:
        _draw_water_lowland_base_map(
            draw,
            water_lowland_rows=_read_water_lowland_rows(
                geography_report,
                height_rows=geographic_height_rows,
                source_rows=source_rows,
                moisture_rows=_read_moisture_rows(geography_report, width=width, height=height),
                width=width,
                height=height,
            ),
            cell_size_px=cell_size_px,
        )
    elif draw_elevation_only:
        _draw_elevation_base_map(
            draw,
            height_rows=height_rows,
            terrain_rows=terrain_rows,
            source_rows=source_rows,
            cell_size_px=cell_size_px,
        )
    else:
        _draw_terrain(draw, terrain_rows=terrain_rows, cell_size_px=cell_size_px)
    if draw_collision_overlay and not geography_base_only:
        _draw_collision_overlay(
            draw,
            collision_rows=collision_rows,
            cell_size_px=cell_size_px,
        )
    if draw_elevation_overlay and not geography_base_only:
        _draw_elevation_overlay(
            draw,
            height_rows=height_rows,
            terrain_rows=terrain_rows,
            source_rows=source_rows,
            cell_size_px=cell_size_px,
        )
    if draw_elevation_contours or draw_elevation_only or draw_slope_only or draw_geography_only:
        contour_height_rows = geographic_height_rows if draw_geography_only or draw_slope_only else height_rows
        _draw_elevation_contours(
            draw,
            height_rows=contour_height_rows,
            cell_size_px=cell_size_px,
        )
    if draw_transition_overlay:
        _draw_transition_overlay(
            draw,
            transitions=transition_items,
            cell_size_px=cell_size_px,
            width=width,
            height=height,
        )
    if draw_gameplay_zones_overlay:
        _draw_gameplay_zones_overlay(
            draw,
            zones=gameplay_zone_items,
            cell_size_px=cell_size_px,
            width=width,
            height=height,
        )
    if draw_routes_overlay:
        _draw_routes_overlay(
            draw,
            routes=route_items,
            cell_size_px=cell_size_px,
            width=width,
            height=height,
        )
    if draw_world_graph_overlay:
        _draw_world_graph_overlay(
            draw,
            graph=world_graph,
            cell_size_px=cell_size_px,
            width=width,
            height=height,
        )
    if draw_places_overlay:
        _draw_places_overlay(
            draw,
            places=place_items,
            cell_size_px=cell_size_px,
            width=width,
            height=height,
        )
    if draw_objects and not geography_base_only:
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
    if draw_elevation_legend:
        _draw_elevation_legend(
            draw,
            panel_x=map_width_px,
            panel_width=legend_width_px,
            panel_height=map_height_px,
            level_counts=level_counts,
            source_counts=_elevation_source_counts(source_rows),
            total_tiles=width * height,
            report=elevation_report,
        )

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
        multi_tile_objects=sum(_has_multi_tile_footprint(item) for item in object_items),
        elevation_levels=sorted(level_counts),
        elevation_level_counts=level_counts,
        elevation_total_tiles=width * height,
        elevation_transitions=len(transition_items),
        places=len(place_items),
        gameplay_zones=len(gameplay_zone_items),
        routes=len(route_items),
        world_graph_edges=len(world_graph_edges),
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
    LOGGER.info("Preview создан: %s", summary.output_path)


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


def _draw_elevation_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    height_rows: list[list[int]],
    terrain_rows: list[list[str]],
    source_rows: list[str],
    cell_size_px: int,
) -> None:
    font = ImageFont.load_default() if cell_size_px >= 8 else None
    for y, row in enumerate(height_rows):
        for x, level in enumerate(row):
            terrain_type = _terrain_type_at(terrain_rows, x=x, y=y)
            source = _source_at(source_rows, x=x, y=y)
            color = _elevation_overlay_color(level, terrain_type=terrain_type, source=source)
            if color[3] > 0:
                draw.rectangle(_cell_rect(x, y, cell_size_px), fill=color)
            if font is not None and level != 0:
                label = str(level) if level < 0 else f"+{level}"
                draw.text(
                    (x * cell_size_px + 1, y * cell_size_px),
                    label,
                    fill=TRANSITION_TEXT_COLOR,
                    font=font,
                )




def _draw_moisture_base_map(
    draw: ImageDraw.ImageDraw,
    *,
    moisture_rows: list[list[float]],
    height_rows: list[list[int]],
    cell_size_px: int,
) -> None:
    """Draw the generated moisture field as a standalone map."""
    if not moisture_rows:
        moisture_rows = _fallback_moisture_rows(height_rows)
    for y, row in enumerate(moisture_rows):
        for x, value in enumerate(row):
            draw.rectangle(_cell_rect(x, y, cell_size_px), fill=_moisture_color(value))


def _draw_slope_base_map(
    draw: ImageDraw.ImageDraw,
    *,
    slope_rows: list[list[int]],
    cell_size_px: int,
) -> None:
    """Draw slope categories as a standalone map."""
    for y, row in enumerate(slope_rows):
        for x, value in enumerate(row):
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=SLOPE_COLORS.get(min(3, max(0, value)), SLOPE_COLORS[3]),
            )


def _draw_geography_base_map(
    draw: ImageDraw.ImageDraw,
    *,
    mask_rows: list[str],
    cell_size_px: int,
) -> None:
    """Draw geographic masks as a standalone map."""
    for y, row in enumerate(mask_rows):
        for x, code in enumerate(row):
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=GEOGRAPHY_COLORS.get(code, GEOGRAPHY_FALLBACK_COLOR),
            )


def _draw_elevation_base_map(
    draw: ImageDraw.ImageDraw,
    *,
    height_rows: list[list[int]],
    terrain_rows: list[list[str]],
    source_rows: list[str],
    cell_size_px: int,
) -> None:
    """Draw height_grid as a source-aware hypsometric elevation map."""
    for y, row in enumerate(height_rows):
        for x, level in enumerate(row):
            terrain_type = _terrain_type_at(terrain_rows, x=x, y=y)
            source = _source_at(source_rows, x=x, y=y)
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=_elevation_opaque_color(level, terrain_type=terrain_type, source=source),
            )


def _draw_elevation_source_base_map(
    draw: ImageDraw.ImageDraw,
    *,
    source_rows: list[str],
    cell_size_px: int,
) -> None:
    """Draw elevation source classes as a standalone debug map."""
    for y, row in enumerate(source_rows):
        for x, source in enumerate(row):
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=ELEVATION_SOURCE_COLORS.get(source, GEOGRAPHY_FALLBACK_COLOR),
            )


def _draw_water_lowland_base_map(
    draw: ImageDraw.ImageDraw,
    *,
    water_lowland_rows: list[str],
    cell_size_px: int,
) -> None:
    """Draw standing water and lowland classes as a standalone map."""
    for y, row in enumerate(water_lowland_rows):
        for x, code in enumerate(row):
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=WATER_LOWLAND_COLORS.get(code, GEOGRAPHY_FALLBACK_COLOR),
            )


def _draw_elevation_contours(
    draw: ImageDraw.ImageDraw,
    *,
    height_rows: list[list[int]],
    cell_size_px: int,
) -> None:
    """Draw thin boundary lines where neighboring elevation levels differ."""
    height = len(height_rows)
    width = len(height_rows[0]) if height_rows else 0
    if width <= 0 or height <= 0:
        return
    for y, row in enumerate(height_rows):
        for x, level in enumerate(row):
            left = x * cell_size_px
            top = y * cell_size_px
            right = (x + 1) * cell_size_px - 1
            bottom = (y + 1) * cell_size_px - 1
            if x + 1 < width and height_rows[y][x + 1] != level:
                draw.line((right, top, right, bottom), fill=ELEVATION_CONTOUR_COLOR)
            if y + 1 < height and height_rows[y + 1][x] != level:
                draw.line((left, bottom, right, bottom), fill=ELEVATION_CONTOUR_COLOR)



def _draw_elevation_legend(
    draw: ImageDraw.ImageDraw,
    *,
    panel_x: int,
    panel_width: int,
    panel_height: int,
    level_counts: dict[int, int],
    source_counts: dict[str, int],
    total_tiles: int,
    report: dict[str, Any],
) -> None:
    """Draw a right-side elevation legend with counts and percentages."""
    font = _load_legend_font(16)
    padding = 14
    line_height = 20
    x = panel_x
    draw.rectangle(
        (x, 0, x + panel_width - 1, panel_height - 1),
        fill=ELEVATION_LEGEND_BACKGROUND,
    )
    cursor_y = padding
    draw.text((x + padding, cursor_y), "Elevation legend", fill=ELEVATION_LEGEND_TEXT, font=font)
    cursor_y += line_height + 6

    profile = _optional_object(report.get("profile"))
    summary = _optional_object(report.get("summary"))
    if profile:
        draw.text(
            (x + padding, cursor_y),
            f"profile: {_legend_text(profile.get('map_class'))}",
            fill=ELEVATION_LEGEND_MUTED_TEXT,
            font=font,
        )
        cursor_y += line_height
        draw.text(
            (x + padding, cursor_y),
            f"active: {_range_text(profile.get('active_range'))}",
            fill=ELEVATION_LEGEND_MUTED_TEXT,
            font=font,
        )
        cursor_y += line_height
    min_level = summary.get("min_level", min(level_counts) if level_counts else 0)
    max_level = summary.get("max_level", max(level_counts) if level_counts else 0)
    draw.text(
        (x + padding, cursor_y),
        f"levels: {min_level}..{max_level} / tiles: {total_tiles}",
        fill=ELEVATION_LEGEND_MUTED_TEXT,
        font=font,
    )
    cursor_y += line_height + 8

    cursor_y = _draw_elevation_band_summary(
        draw,
        x=x + padding,
        y=cursor_y,
        panel_width=panel_width - padding * 2,
        total_tiles=total_tiles,
        level_counts=level_counts,
        font=font,
    )
    cursor_y += 7
    cursor_y = _draw_elevation_source_summary(
        draw,
        x=x + padding,
        y=cursor_y,
        panel_width=panel_width - padding * 2,
        total_tiles=total_tiles,
        source_counts=source_counts,
        font=font,
    )
    cursor_y += 7

    draw.text((x + padding, cursor_y), "Level       tiles       %", fill=ELEVATION_LEGEND_TEXT, font=font)
    cursor_y += line_height + 3
    max_count = max(level_counts.values()) if level_counts else 1
    bar_x = x + padding + 198
    bar_width = max(50, panel_width - padding * 2 - 198)
    for level in range(ELEVATION_FORMAT_MIN_LEVEL, ELEVATION_FORMAT_MAX_LEVEL + 1):
        if cursor_y + line_height > panel_height - padding:
            break
        count = level_counts.get(level, 0)
        percent = _legend_percent(count, total_tiles)
        color = _elevation_opaque_color(level)
        draw.rectangle((x + padding, cursor_y + 2, x + padding + 13, cursor_y + 13), fill=color)
        draw.text(
            (x + padding + 19, cursor_y),
            f"{level:>3} {count:>10} {percent:>6.1f}%",
            fill=ELEVATION_LEGEND_TEXT if count else ELEVATION_LEGEND_MUTED_TEXT,
            font=font,
        )
        draw.rectangle(
            (bar_x, cursor_y + 4, bar_x + bar_width, cursor_y + 10),
            fill=ELEVATION_LEGEND_BAR_BACKGROUND,
        )
        filled_width = int(round(bar_width * count / max_count)) if max_count else 0
        if filled_width > 0:
            draw.rectangle(
                (bar_x, cursor_y + 4, bar_x + filled_width, cursor_y + 10),
                fill=ELEVATION_LEGEND_BAR,
            )
        cursor_y += line_height



def _draw_elevation_band_summary(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    panel_width: int,
    total_tiles: int,
    level_counts: dict[int, int],
    font: ImageFont.ImageFont,
) -> int:
    bands = (
        ("low/depth -5..-1", range(-5, 0)),
        ("ground 0", range(0, 1)),
        ("raised 1..4", range(1, 5)),
        ("hills 5..10", range(5, 11)),
        ("highlands 11..16", range(11, 17)),
        ("landmarks 17..20", range(17, 21)),
    )
    line_height = 20
    draw.text((x, y), "Bands", fill=ELEVATION_LEGEND_TEXT, font=font)
    y += line_height + 2
    max_count = max(
        (sum(level_counts.get(level, 0) for level in levels) for _, levels in bands),
        default=1,
    )
    bar_x = x + 178
    bar_width = max(50, panel_width - 178)
    for label, levels in bands:
        count = sum(level_counts.get(level, 0) for level in levels)
        percent = _legend_percent(count, total_tiles)
        draw.text(
            (x, y),
            f"{label:<18} {percent:>5.1f}%",
            fill=ELEVATION_LEGEND_MUTED_TEXT,
            font=font,
        )
        draw.rectangle((bar_x, y + 4, bar_x + bar_width, y + 10), fill=ELEVATION_LEGEND_BAR_BACKGROUND)
        filled_width = int(round(bar_width * count / max_count)) if max_count else 0
        if filled_width > 0:
            draw.rectangle((bar_x, y + 4, bar_x + filled_width, y + 10), fill=ELEVATION_LEGEND_BAR)
        y += line_height
    return y


def _draw_elevation_source_summary(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    panel_width: int,
    total_tiles: int,
    source_counts: dict[str, int],
    font: ImageFont.ImageFont,
) -> int:
    """Draw source split for runtime elevation values."""
    line_height = 20
    draw.text((x, y), "Sources", fill=ELEVATION_LEGEND_TEXT, font=font)
    y += line_height + 2
    max_count = max(source_counts.values(), default=1)
    bar_x = x + 178
    bar_width = max(50, panel_width - 178)
    for code in ("G", "W", "S"):
        count = source_counts.get(code, 0)
        percent = _legend_percent(count, total_tiles)
        label = ELEVATION_SOURCE_LABELS.get(code, code)
        draw.rectangle((x, y + 3, x + 13, y + 14), fill=ELEVATION_SOURCE_COLORS.get(code, GEOGRAPHY_FALLBACK_COLOR))
        draw.text(
            (x + 19, y),
            f"{label + ':':<14} {percent:>5.1f}%",
            fill=ELEVATION_LEGEND_MUTED_TEXT,
            font=font,
        )
        draw.rectangle((bar_x, y + 4, bar_x + bar_width, y + 10), fill=ELEVATION_LEGEND_BAR_BACKGROUND)
        filled_width = int(round(bar_width * count / max_count)) if max_count else 0
        if filled_width > 0:
            draw.rectangle((bar_x, y + 4, bar_x + filled_width, y + 10), fill=ELEVATION_LEGEND_BAR)
        y += line_height
    return y


def _read_generation_geography(root: Path) -> dict[str, Any]:
    tactical_map = _read_optional_output_object(root / "tactical_map.json")
    generation_report = _optional_object(tactical_map.get("elevation_generation_report"))
    return _optional_object(generation_report.get("geography"))


def _read_moisture_rows(geography: dict[str, Any], *, width: int, height: int) -> list[list[float]]:
    moisture_grid = _optional_object(_optional_object(geography.get("grids")).get("moisture_grid"))
    scale = moisture_grid.get("scale", 1000)
    if not isinstance(scale, int | float) or scale <= 0:
        scale = 1000
    rows = moisture_grid.get("rows")
    if not isinstance(rows, list):
        return []
    output: list[list[float]] = []
    for row in rows[:height]:
        if not isinstance(row, list):
            continue
        values = [float(value) / float(scale) for value in row[:width] if isinstance(value, int | float)]
        if len(values) == width:
            output.append([max(0.0, min(1.0, value)) for value in values])
    return output if len(output) == height else []


def _read_slope_rows(
    geography: dict[str, Any],
    *,
    height_rows: list[list[int]],
    width: int,
    height: int,
) -> list[list[int]]:
    slope_grid = _optional_object(_optional_object(geography.get("grids")).get("slope_grid"))
    rows = slope_grid.get("rows")
    if isinstance(rows, list):
        output: list[list[int]] = []
        for row in rows[:height]:
            if not isinstance(row, list):
                continue
            values = [int(value) for value in row[:width] if isinstance(value, int | float)]
            if len(values) == width:
                output.append(values)
        if len(output) == height:
            return output
    return _compute_slope_rows(height_rows)


def _read_geography_mask_rows(
    geography: dict[str, Any],
    *,
    height_rows: list[list[int]],
    width: int,
    height: int,
) -> list[str]:
    mask_grid = _optional_object(_optional_object(geography.get("grids")).get("mask_grid"))
    rows = mask_grid.get("rows")
    if isinstance(rows, list):
        output = [row[:width] for row in rows[:height] if isinstance(row, str) and len(row) >= width]
        if len(output) == height:
            return output
    return _fallback_geography_mask_rows(height_rows)


def _read_elevation_source_rows(geography: dict[str, Any], *, width: int, height: int) -> list[str]:
    source_grid = _optional_object(_optional_object(geography.get("grids")).get("source_grid"))
    rows = source_grid.get("rows")
    if isinstance(rows, list):
        output = [row[:width] for row in rows[:height] if isinstance(row, str) and len(row) >= width]
        if len(output) == height:
            return output
    return ["G" * width for _ in range(height)]


def _read_geographic_height_rows(
    geography: dict[str, Any],
    *,
    height_rows: list[list[int]],
    width: int,
    height: int,
) -> list[list[int]]:
    level_grid = _optional_object(_optional_object(geography.get("grids")).get("geographic_level_grid"))
    rows = level_grid.get("rows")
    if isinstance(rows, list):
        output: list[list[int]] = []
        for row in rows[:height]:
            if not isinstance(row, list):
                continue
            values = [int(value) for value in row[:width] if isinstance(value, int | float)]
            if len(values) == width:
                output.append(values)
        if len(output) == height:
            return output
    return height_rows


def _read_water_lowland_rows(
    geography: dict[str, Any],
    *,
    height_rows: list[list[int]],
    source_rows: list[str],
    moisture_rows: list[list[float]],
    width: int,
    height: int,
) -> list[str]:
    water_grid = _optional_object(_optional_object(geography.get("grids")).get("water_lowland_grid"))
    rows = water_grid.get("rows")
    if isinstance(rows, list):
        output = [row[:width] for row in rows[:height] if isinstance(row, str) and len(row) >= width]
        if len(output) == height:
            return output
    return _fallback_water_lowland_rows(
        height_rows,
        source_rows=source_rows,
        moisture_rows=moisture_rows,
    )


def _compute_slope_rows(height_rows: list[list[int]]) -> list[list[int]]:
    height = len(height_rows)
    width = len(height_rows[0]) if height_rows else 0
    output = [[0 for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(height_rows):
        for x, level in enumerate(row):
            output[y][x] = max(
                (
                    abs(level - height_rows[ny][nx])
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                    if 0 <= nx < width and 0 <= ny < height
                ),
                default=0,
            )
    return output


def _fallback_moisture_rows(height_rows: list[list[int]]) -> list[list[float]]:
    if not height_rows:
        return []
    levels = [level for row in height_rows for level in row]
    minimum = min(levels)
    maximum = max(levels)
    span = max(1, maximum - minimum)
    return [[1.0 - ((level - minimum) / span) for level in row] for row in height_rows]


def _fallback_geography_mask_rows(height_rows: list[list[int]]) -> list[str]:
    slope_rows = _compute_slope_rows(height_rows)
    output: list[str] = []
    for y, row in enumerate(height_rows):
        chars: list[str] = []
        for x, level in enumerate(row):
            slope = slope_rows[y][x]
            if level >= 17:
                chars.append("K")
            elif level >= 11:
                chars.append("R" if slope >= 2 else "M")
            elif level >= 7:
                chars.append("R" if slope >= 2 else "T")
            elif level >= 3:
                chars.append("H")
            elif level < -1:
                chars.append("B")
            elif level < 0:
                chars.append("L")
            else:
                chars.append("P")
        output.append("".join(chars))
    return output


def _fallback_water_lowland_rows(
    height_rows: list[list[int]],
    *,
    source_rows: list[str],
    moisture_rows: list[list[float]],
) -> list[str]:
    output: list[str] = []
    for y, row in enumerate(height_rows):
        chars: list[str] = []
        for x, level in enumerate(row):
            source = _source_at(source_rows, x=x, y=y) or "G"
            moisture = moisture_rows[y][x] if y < len(moisture_rows) and x < len(moisture_rows[y]) else 0.5
            if source == "S":
                chars.append("X")
            elif source == "W":
                chars.append("B" if level <= -2 else "S")
            elif level < 0:
                chars.append("W" if moisture >= 0.68 else "L")
            elif level <= 1 and moisture >= 0.82:
                chars.append("W")
            else:
                chars.append("D")
        output.append("".join(chars))
    return output


def _moisture_color(value: float) -> tuple[int, int, int, int]:
    value = max(0.0, min(1.0, value))
    if value < 0.5:
        t = value / 0.5
        return _interpolate_color((156, 124, 75, 255), (91, 142, 83, 255), t)
    t = (value - 0.5) / 0.5
    return _interpolate_color((91, 142, 83, 255), (67, 139, 181, 255), t)


def _interpolate_color(
    start: tuple[int, int, int, int],
    end: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(start, end, strict=True))


def _elevation_opaque_color(
    level: int,
    *,
    terrain_type: str | None = None,
    source: str | None = None,
) -> tuple[int, int, int, int]:
    level = max(ELEVATION_FORMAT_MIN_LEVEL, min(ELEVATION_FORMAT_MAX_LEVEL, level))
    if terrain_type == "water_slow" or source == "W":
        return WATER_ELEVATION_COLORS.get(min(0, level), WATER_ELEVATION_COLORS[0])
    if source == "S" and level < 0:
        return STRUCTURAL_ELEVATION_COLORS.get(level, STRUCTURAL_ELEVATION_COLORS[-5])
    return ELEVATION_OPAQUE_COLORS.get(level, (255, 255, 255, 255))


def _elevation_overlay_color(
    level: int,
    *,
    terrain_type: str | None = None,
    source: str | None = None,
) -> tuple[int, int, int, int]:
    red, green, blue, _alpha = _elevation_opaque_color(level, terrain_type=terrain_type, source=source)
    alpha = ELEVATION_ZERO_OVERLAY_ALPHA if level == 0 and source != "W" else ELEVATION_OVERLAY_ALPHA
    return red, green, blue, alpha



def _elevation_level_counts(height_rows: list[list[int]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in height_rows:
        for level in row:
            counts[level] = counts.get(level, 0) + 1
    return dict(sorted(counts.items()))



def _elevation_source_counts(source_rows: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in source_rows:
        for source in row:
            counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items()))


def _terrain_type_at(terrain_rows: list[list[str]], *, x: int, y: int) -> str | None:
    if 0 <= y < len(terrain_rows) and 0 <= x < len(terrain_rows[y]):
        return terrain_rows[y][x]
    return None


def _source_at(source_rows: list[str], *, x: int, y: int) -> str | None:
    if 0 <= y < len(source_rows) and 0 <= x < len(source_rows[y]):
        return source_rows[y][x]
    return None


def _legend_panel_width(map_width_px: int) -> int:
    return max(ELEVATION_LEGEND_PANEL_WIDTH_PX, min(560, map_width_px // 4))



def _load_legend_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()



def _legend_percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return count * 100.0 / total



def _legend_text(value: Any) -> str:
    return str(value) if value is not None else "unknown"



def _range_text(value: Any) -> str:
    if isinstance(value, list | tuple) and len(value) == 2:
        return f"{value[0]}..{value[1]}"
    return "unknown"


def _draw_transition_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    transitions: list[Any],
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    font = ImageFont.load_default() if cell_size_px >= 8 else None
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        source = _transition_point(transition.get("from"), width=width, height=height)
        target = _transition_point(transition.get("to"), width=width, height=height)
        if source is None or target is None:
            continue
        transition_type = transition.get("type")
        color = TRANSITION_COLORS.get(
            transition_type if isinstance(transition_type, str) else "",
            (255, 255, 255, 220),
        )
        sx, sy = _cell_center(source["x"], source["y"], cell_size_px)
        tx, ty = _cell_center(target["x"], target["y"], cell_size_px)
        draw.line((sx, sy, tx, ty), fill=color, width=max(1, cell_size_px // 4))
        if font is not None:
            label = _transition_label(transition)
            mx = (sx + tx) // 2
            my = (sy + ty) // 2
            draw.text((mx, my), label, fill=TRANSITION_TEXT_COLOR, font=font)


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
        if _is_bunker(item):
            _draw_bunker(
                draw,
                item,
                cell_size_px=cell_size_px,
                width=width,
                height=height,
            )
            continue
        visual_bounds = _visual_bounds(item.get("visual_bounds"), width=width, height=height)
        if visual_bounds is not None:
            draw.rectangle(
                _bounds_rect(visual_bounds, cell_size_px),
                outline=OBJECT_VISUAL_BOUNDS_COLOR,
                width=1,
            )
        footprint = _footprint(item.get("footprint"), width=width, height=height)
        for x, y in footprint:
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=OBJECT_FOOTPRINT_COLOR,
            )
        collision_footprint = _footprint(
            item.get("collision_footprint"),
            width=width,
            height=height,
        )
        for x, y in collision_footprint:
            draw.rectangle(
                _cell_rect(x, y, cell_size_px),
                fill=OBJECT_COLLISION_FOOTPRINT_COLOR,
            )
        _draw_firing_ports(
            draw,
            item.get("firing_ports"),
            cell_size_px=cell_size_px,
            width=width,
            height=height,
        )
        point = _object_point(item, width=width, height=height)
        if point is None:
            continue
        _draw_small_marker(draw, point["x"], point["y"], cell_size_px, OBJECT_COLOR)


def _is_bunker(item: dict[str, Any]) -> bool:
    """Return whether an object should use the explicit bunker preview style."""
    object_type = item.get("type")
    return isinstance(object_type, str) and object_type.startswith("buried_bunker_")


def _draw_bunker(
    draw: ImageDraw.ImageDraw,
    item: dict[str, Any],
    *,
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    """Draw a bunker as bold B-marked footprint cells."""
    footprint = _footprint(item.get("footprint"), width=width, height=height)
    collision_footprint = _footprint(
        item.get("collision_footprint"),
        width=width,
        height=height,
    )
    cells = collision_footprint or footprint
    for x, y in cells:
        rect = _cell_rect(x, y, cell_size_px)
        draw.rectangle(rect, fill=BUNKER_FILL_COLOR, outline=BUNKER_OUTLINE_COLOR)
        if cell_size_px >= 6:
            draw.text(
                (x * cell_size_px + max(1, cell_size_px // 4), y * cell_size_px),
                "B",
                fill=BUNKER_TEXT_COLOR,
            )
    visual_bounds = _visual_bounds(item.get("visual_bounds"), width=width, height=height)
    if visual_bounds is not None:
        draw.rectangle(
            _bounds_rect(visual_bounds, cell_size_px),
            outline=BUNKER_OUTLINE_COLOR,
            width=max(1, cell_size_px // 4),
        )
    _draw_firing_ports(
        draw,
        item.get("firing_ports"),
        cell_size_px=cell_size_px,
        width=width,
        height=height,
    )


def _draw_firing_ports(
    draw: ImageDraw.ImageDraw,
    value: Any,
    *,
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    if not isinstance(value, list):
        return
    for port in value:
        if not isinstance(port, dict):
            continue
        positions = _footprint(port.get("positions"), width=width, height=height)
        for x, y in positions:
            padding = max(1, cell_size_px // 3)
            draw.ellipse(
                (
                    x * cell_size_px + padding,
                    y * cell_size_px + padding,
                    (x + 1) * cell_size_px - padding - 1,
                    (y + 1) * cell_size_px - padding - 1,
                ),
                fill=FIRING_PORT_COLOR,
            )



def _draw_gameplay_zones_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    zones: list[Any],
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    """Draw gameplay zone bounds and labels."""
    font = ImageFont.load_default() if cell_size_px >= 6 else None
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        bounds = _minmax_bounds(zone.get("bounds"), width=width, height=height)
        if bounds is None:
            continue
        zone_type = zone.get("type") if isinstance(zone.get("type"), str) else "unknown"
        fill = GAMEPLAY_ZONE_FILL_COLORS.get(zone_type, (255, 255, 255, 55))
        rect = _minmax_bounds_rect(bounds, cell_size_px)
        draw.rectangle(rect, fill=fill, outline=GAMEPLAY_ZONE_OUTLINE_COLOR)
        if font is not None:
            _draw_text(draw, _zone_label(zone_type), bounds["min_x"], bounds["min_y"], cell_size_px, font, PLACE_TEXT_COLOR)
        for point in _zone_points(zone.get("entry_points")):
            _draw_cross(draw, point["x"], point["y"], cell_size_px, GAMEPLAY_ZONE_OUTLINE_COLOR)


def _draw_places_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    places: list[Any],
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    """Draw semantic place bounds and entrances."""
    font = ImageFont.load_default() if cell_size_px >= 6 else None
    for place in places:
        if not isinstance(place, dict):
            continue
        bounds = _minmax_bounds(place.get("bounds"), width=width, height=height)
        if bounds is None:
            continue
        draw.rectangle(
            _minmax_bounds_rect(bounds, cell_size_px),
            outline=PLACE_OUTLINE_COLOR,
            width=max(1, cell_size_px // 5),
        )
        if font is not None:
            label = _short_id(str(place.get("type", "place")))
            _draw_text(draw, label, bounds["min_x"], bounds["min_y"], cell_size_px, font, PLACE_TEXT_COLOR)
        for point in _zone_points(place.get("entrances")):
            _draw_cross(draw, point["x"], point["y"], cell_size_px, PLACE_OUTLINE_COLOR)


def _draw_world_graph_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    graph: dict[str, Any],
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    """Draw world graph nodes and edges."""
    nodes = _world_graph_nodes_by_id(graph, width=width, height=height)
    main_edge_ids = set(_string_values(_optional_object(graph.get("main_path")).get("edge_ids")))
    for edge in _optional_list(graph.get("edges")):
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        edge_id = edge.get("id")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        source_point = nodes.get(source)
        target_point = nodes.get(target)
        if source_point is None or target_point is None:
            continue
        color = WORLD_GRAPH_MAIN_PATH_COLOR if edge_id in main_edge_ids else WORLD_GRAPH_EDGE_COLOR
        _draw_line_between_points(draw, source_point, target_point, cell_size_px, color)
    for point in nodes.values():
        _draw_small_marker(draw, point["x"], point["y"], cell_size_px, WORLD_GRAPH_NODE_COLOR)


def _draw_routes_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    routes: list[Any],
    cell_size_px: int,
    width: int,
    height: int,
) -> None:
    """Draw semantic route waypoints."""
    font = ImageFont.load_default() if cell_size_px >= 8 else None
    for route in routes:
        if not isinstance(route, dict):
            continue
        waypoints = _route_waypoints(route.get("waypoints"), width=width, height=height)
        if not waypoints:
            continue
        route_type = route.get("type") if isinstance(route.get("type"), str) else "unknown"
        color = ROUTE_COLORS.get(route_type, ROUTE_FALLBACK_COLOR)
        _draw_polyline(draw, waypoints, cell_size_px, color)
        if font is not None:
            first = waypoints[0]
            _draw_text(draw, _route_label(route_type), first["x"], first["y"], cell_size_px, font, color)


def _zone_points(value: Any) -> list[dict[str, int]]:
    points: list[dict[str, int]] = []
    for item in _optional_list(value):
        if not isinstance(item, dict):
            continue
        point = _point_object(item.get("position")) or _point_object(item)
        if point is not None:
            points.append(point)
    return points


def _route_waypoints(value: Any, *, width: int, height: int) -> list[dict[str, int]]:
    points: list[dict[str, int]] = []
    for item in _optional_list(value):
        point = _point_object(item)
        if point is None:
            continue
        if 0 <= point["x"] < width and 0 <= point["y"] < height:
            points.append(point)
    return points


def _world_graph_nodes_by_id(
    graph: dict[str, Any],
    *,
    width: int,
    height: int,
) -> dict[str, dict[str, int]]:
    nodes: dict[str, dict[str, int]] = {}
    for node in _optional_list(graph.get("nodes")):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        position = _point_object(node.get("position"))
        if not isinstance(node_id, str) or position is None:
            continue
        if 0 <= position["x"] < width and 0 <= position["y"] < height:
            nodes[node_id] = position
    return nodes


def _draw_polyline(
    draw: ImageDraw.ImageDraw,
    points: list[dict[str, int]],
    cell_size_px: int,
    color: tuple[int, int, int, int],
) -> None:
    if len(points) < 2:
        point = points[0] if points else None
        if point is not None:
            _draw_cross(draw, point["x"], point["y"], cell_size_px, color)
        return
    centers = [_cell_center(point["x"], point["y"], cell_size_px) for point in points]
    draw.line(centers, fill=color, width=max(1, cell_size_px // 4))
    for point in points:
        _draw_cross(draw, point["x"], point["y"], cell_size_px, color)


def _draw_line_between_points(
    draw: ImageDraw.ImageDraw,
    source: dict[str, int],
    target: dict[str, int],
    cell_size_px: int,
    color: tuple[int, int, int, int],
) -> None:
    sx, sy = _cell_center(source["x"], source["y"], cell_size_px)
    tx, ty = _cell_center(target["x"], target["y"], cell_size_px)
    draw.line((sx, sy, tx, ty), fill=color, width=max(1, cell_size_px // 5))


def _draw_cross(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    cell_size_px: int,
    color: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = _cell_rect(x, y, cell_size_px)
    draw.line((left, top, right, bottom), fill=color, width=max(1, cell_size_px // 5))
    draw.line((left, bottom, right, top), fill=color, width=max(1, cell_size_px // 5))


def _draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    cell_size_px: int,
    font: ImageFont.ImageFont,
    color: tuple[int, int, int, int],
) -> None:
    draw.text((x * cell_size_px + 1, y * cell_size_px), text, fill=color, font=font)


def _point_object(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return {"x": x, "y": y}
    return None


def _minmax_bounds(value: Any, *, width: int, height: int) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    if all(key in value for key in ("min_x", "min_y", "max_x", "max_y")):
        min_x = value.get("min_x")
        min_y = value.get("min_y")
        max_x = value.get("max_x")
        max_y = value.get("max_y")
    elif all(key in value for key in ("x", "y", "width", "height")):
        min_x = value.get("x")
        min_y = value.get("y")
        max_x = value.get("x") + value.get("width") - 1 if isinstance(value.get("x"), int) and isinstance(value.get("width"), int) else None
        max_y = value.get("y") + value.get("height") - 1 if isinstance(value.get("y"), int) and isinstance(value.get("height"), int) else None
    else:
        return None
    if not all(isinstance(item, int) for item in (min_x, min_y, max_x, max_y)):
        return None
    min_x = max(0, min(width - 1, min_x))
    min_y = max(0, min(height - 1, min_y))
    max_x = max(0, min(width - 1, max_x))
    max_y = max(0, min(height - 1, max_y))
    if max_x < min_x or max_y < min_y:
        return None
    return {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y}


def _minmax_bounds_rect(
    bounds: dict[str, int],
    cell_size_px: int,
) -> tuple[int, int, int, int]:
    return (
        bounds["min_x"] * cell_size_px,
        bounds["min_y"] * cell_size_px,
        (bounds["max_x"] + 1) * cell_size_px - 1,
        (bounds["max_y"] + 1) * cell_size_px - 1,
    )


def _string_values(value: Any) -> list[str]:
    return [item for item in _optional_list(value) if isinstance(item, str)]


def _zone_label(zone_type: str) -> str:
    return "".join(part[:1].upper() for part in zone_type.split("_") if part)[:3] or "Z"


def _route_label(route_type: str) -> str:
    return "".join(part[:1].upper() for part in route_type.split("_") if part)[:3] or "R"


def _short_id(value: str) -> str:
    return "".join(part[:1].upper() for part in value.split("_") if part)[:3] or "P"

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


def _cell_center(x: int, y: int, cell_size_px: int) -> tuple[int, int]:
    return (
        x * cell_size_px + cell_size_px // 2,
        y * cell_size_px + cell_size_px // 2,
    )


def _bounds_rect(
    bounds: dict[str, int],
    cell_size_px: int,
) -> tuple[int, int, int, int]:
    return (
        bounds["x"] * cell_size_px,
        bounds["y"] * cell_size_px,
        (bounds["x"] + bounds["width"]) * cell_size_px - 1,
        (bounds["y"] + bounds["height"]) * cell_size_px - 1,
    )


def _visual_bounds(
    value: Any,
    *,
    width: int,
    height: int,
) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    bounds_width = value.get("width")
    bounds_height = value.get("height")
    if not all(isinstance(item, int) for item in (x, y, bounds_width, bounds_height)):
        return None
    if bounds_width <= 0 or bounds_height <= 0:
        return None
    if x >= width or y >= height or x + bounds_width <= 0 or y + bounds_height <= 0:
        return None
    return {
        "x": max(0, x),
        "y": max(0, y),
        "width": min(bounds_width, width - max(0, x)),
        "height": min(bounds_height, height - max(0, y)),
    }


def _has_multi_tile_footprint(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    footprint = item.get("footprint")
    return isinstance(footprint, list) and len(footprint) > 1


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



def _read_optional_output_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return _read_object(path)


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


def _read_height_rows(data: dict[str, Any], *, width: int, height: int) -> list[list[int]]:
    grids = _optional_object(data.get("grids"))
    height_grid = _optional_object(grids.get("height_grid"))
    rows = height_grid.get("rows")
    if not isinstance(rows, list):
        return [[0 for _ in range(width)] for _ in range(height)]
    result: list[list[int]] = []
    for y in range(height):
        source_row = rows[y] if y < len(rows) else []
        row: list[int] = []
        if isinstance(source_row, list):
            for x in range(width):
                value = source_row[x] if x < len(source_row) else 0
                row.append(value if isinstance(value, int) else 0)
        else:
            row = [0 for _ in range(width)]
        result.append(row)
    return result


def _transition_point(
    value: Any,
    *,
    width: int,
    height: int,
) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height:
        return {"x": x, "y": y}
    return None


def _transition_label(transition: dict[str, Any]) -> str:
    connector = transition.get("suggested_connector")
    if connector == "ramp":
        return "R"
    if connector == "stairs":
        return "S"
    if connector == "bridge":
        return "B"
    if connector == "slope":
        return "/"
    transition_type = transition.get("type")
    if transition_type == "steep_transition":
        return "!"
    return "↕"


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
        "--elevation-overlay",
        action="store_true",
        help="Overlay height_grid levels on top of terrain colors.",
    )
    parser.add_argument(
        "--transition-overlay",
        action="store_true",
        help="Draw elevation transitions such as slopes, ramps, bridges, and steep edges.",
    )
    parser.add_argument(
        "--places-overlay",
        action="store_true",
        help="Draw semantic place bounds and entrances.",
    )
    parser.add_argument(
        "--gameplay-zones-overlay",
        action="store_true",
        help="Draw neutral gameplay zone bounds.",
    )
    parser.add_argument(
        "--routes-overlay",
        action="store_true",
        help="Draw semantic routes from routes.json.",
    )
    parser.add_argument(
        "--world-graph-overlay",
        action="store_true",
        help="Draw world graph nodes and edges.",
    )
    parser.add_argument(
        "--semantic-overlays",
        action="store_true",
        help="Draw places, gameplay zones, routes, and world graph overlays.",
    )
    parser.add_argument(
        "--grid",
        action="store_true",
        help="Draw a light tile grid. Useful for small maps.",
    )
    parser.add_argument(
        "--elevation-legend",
        action="store_true",
        help="Append a right-side elevation legend with per-level counts.",
    )
    parser.add_argument(
        "--elevation-only",
        action="store_true",
        help="Render height_grid as a standalone hypsometric elevation map.",
    )
    parser.add_argument(
        "--elevation-contours",
        action="store_true",
        help="Draw contour-like lines between different height levels.",
    )
    parser.add_argument(
        "--moisture-only",
        action="store_true",
        help="Render the generated moisture field as a standalone map.",
    )
    parser.add_argument(
        "--slope-only",
        action="store_true",
        help="Render slope categories as a standalone map.",
    )
    parser.add_argument(
        "--geography-only",
        action="store_true",
        help="Render geographic masks as a standalone map.",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Render geography/water/structural elevation source classes.",
    )
    parser.add_argument(
        "--water-lowlands-only",
        action="store_true",
        help="Render standing water, wet lowlands, dry lowlands, and structural depth.",
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
            draw_elevation_overlay=args.elevation_overlay,
            draw_transition_overlay=args.transition_overlay,
            draw_places_overlay=args.places_overlay or args.semantic_overlays,
            draw_gameplay_zones_overlay=args.gameplay_zones_overlay or args.semantic_overlays,
            draw_routes_overlay=args.routes_overlay or args.semantic_overlays,
            draw_world_graph_overlay=args.world_graph_overlay or args.semantic_overlays,
            draw_grid=args.grid,
            draw_elevation_legend=args.elevation_legend,
            draw_elevation_only=args.elevation_only,
            draw_elevation_contours=args.elevation_contours,
            draw_moisture_only=args.moisture_only,
            draw_slope_only=args.slope_only,
            draw_geography_only=args.geography_only,
            draw_source_only=args.source_only,
            draw_water_lowlands_only=args.water_lowlands_only,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        LOGGER.error("Не удалось создать preview")
        LOGGER.error("- %s", exc)
        return 1
    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
