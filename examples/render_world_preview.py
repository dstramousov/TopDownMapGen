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
ELEVATION_COLORS: dict[int, tuple[int, int, int, int]] = {
    -1: (30, 55, 130, 140),
    0: (0, 0, 0, 0),
    1: (190, 170, 80, 120),
    2: (220, 160, 70, 140),
    3: (215, 110, 190, 155),
    4: (245, 245, 100, 175),
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
    if draw_elevation_overlay:
        _draw_elevation_overlay(
            draw,
            height_rows=height_rows,
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
        multi_tile_objects=sum(_has_multi_tile_footprint(item) for item in object_items),
        elevation_levels=sorted({level for row in height_rows for level in row}),
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
    LOGGER.info("- multi-tile objects: %s", summary.multi_tile_objects)
    LOGGER.info("- elevation levels: %s", summary.elevation_levels)
    LOGGER.info("- elevation transitions: %s", summary.elevation_transitions)
    LOGGER.info("- places: %s", summary.places)
    LOGGER.info("- gameplay zones: %s", summary.gameplay_zones)
    LOGGER.info("- routes: %s", summary.routes)
    LOGGER.info("- world graph edges: %s", summary.world_graph_edges)
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


def _draw_elevation_overlay(
    draw: ImageDraw.ImageDraw,
    *,
    height_rows: list[list[int]],
    cell_size_px: int,
) -> None:
    font = ImageFont.load_default() if cell_size_px >= 8 else None
    for y, row in enumerate(height_rows):
        for x, level in enumerate(row):
            color = ELEVATION_COLORS.get(level, (255, 255, 255, 140))
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
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        LOGGER.error("World preview: FAILED")
        LOGGER.error("- %s", exc)
        return 1
    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
