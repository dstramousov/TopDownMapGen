#!/usr/bin/env python3
"""Inspect a generated TopDownMapGen world package as an external consumer."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
MAP_PACKAGE_INDEX_KIND = "map_package:index"


@dataclass(frozen=True, slots=True)
class GridStats:
    """Summary for a row-major grid.

    Attributes:
        width: Grid width in cells.
        height: Grid height in cells.
        unique_values: Sorted unique cell values.
    """

    width: int
    height: int
    unique_values: list[str]


@dataclass(frozen=True, slots=True)
class CollisionStats:
    """Summary for the collision layer.

    Attributes:
        passable: Number of passable cells.
        blocked: Number of blocked cells.
        total: Total number of cells.
    """

    passable: int
    blocked: int
    total: int

    @property
    def blocked_ratio(self) -> float:
        """Return blocked cell ratio."""
        if self.total == 0:
            return 0.0
        return self.blocked / self.total


@dataclass(frozen=True, slots=True)
class MovementStats:
    """Summary for movement costs.

    Attributes:
        cost_count: Number of concrete movement costs.
        min_cost: Minimum movement cost, if present.
        max_cost: Maximum movement cost, if present.
    """

    cost_count: int
    min_cost: int | float | None
    max_cost: int | float | None


@dataclass(frozen=True, slots=True)
class ElevationStats:
    """Summary for elevation values.

    Attributes:
        cell_count: Number of elevation cells.
        min_level: Minimum elevation level, if present.
        max_level: Maximum elevation level, if present.
    """

    cell_count: int
    min_level: int | None
    max_level: int | None


@dataclass(slots=True)
class InspectionReport:
    """World package inspection report.

    Attributes:
        root: Output root directory.
        map_json_path: Path to map_package/map.json.
        generator_version: Generator version declared by map.json.
        package_schema_version: Map package schema version.
        resolved_seed: Concrete seed used for the generation run.
        profile: Objective profile name.
        width: Map width in tiles.
        height: Map height in tiles.
        tile_size_px: Tile size in pixels.
        start: Start point.
        goal: Goal point.
        tile_grid: Tile grid summary.
        terrain: Terrain grid summary.
        collision: Collision summary.
        movement: Movement cost summary.
        elevation: Elevation summary.
        marker_count: Number of gameplay markers.
        runtime_grid_count: Number of ready-to-use runtime grids.
        world_graph_node_count: Number of semantic world graph nodes.
        world_graph_edge_count: Number of semantic world graph edges.
        world_graph_main_path_length: Number of nodes in the main semantic path.
        route_count: Number of semantic routes.
        route_type_counts: Per-route-type counts.
        gameplay_zone_count: Number of neutral gameplay zones.
        gameplay_zone_type_counts: Per-zone-type counts.
        gameplay_counts: Per-gameplay-layer item counts.
        runtime_object_count: Number of runtime objects.
        runtime_object_type_count: Number of runtime object types used by instances.
        multi_tile_object_count: Number of objects with more than one footprint tile.
        max_object_footprint_tiles: Largest runtime object footprint size.
        max_collision_footprint_tiles: Largest collision footprint size.
        place_count: Number of semantic places.
        tile_type_count: Number of tile type definitions.
        object_type_count: Number of object type definitions.
        tile_render_hint_count: Number of tile render hints.
        object_render_hint_count: Number of object render hints.
        warnings: Non-fatal inspection warnings.
    """

    root: Path
    map_json_path: Path
    generator_version: str
    package_schema_version: str
    resolved_seed: int | str
    profile: str
    width: int
    height: int
    tile_size_px: int
    start: dict[str, int] | None
    goal: dict[str, int] | None
    tile_grid: GridStats
    terrain: GridStats
    collision: CollisionStats
    movement: MovementStats
    elevation: ElevationStats
    elevation_model_levels: list[str]
    elevation_model_feature_count: int
    elevation_model_transition_count: int
    elevation_missing_levels: list[str]
    elevation_missing_feature_types: list[str]
    elevation_feature_count: int
    elevation_transition_count: int
    marker_count: int
    runtime_grid_count: int
    world_graph_node_count: int
    world_graph_edge_count: int
    world_graph_main_path_length: int
    route_count: int
    route_type_counts: dict[str, int]
    gameplay_zone_count: int
    gameplay_zone_type_counts: dict[str, int]
    gameplay_counts: dict[str, int]
    runtime_object_count: int
    runtime_object_type_count: int
    multi_tile_object_count: int
    max_object_footprint_tiles: int
    max_collision_footprint_tiles: int
    place_count: int
    tile_type_count: int
    object_type_count: int
    tile_render_hint_count: int
    object_render_hint_count: int
    warnings: list[str] = field(default_factory=list)


def inspect_world_package(path: Path) -> InspectionReport:
    """Inspect a generated world package using only public output files.

    Args:
        path: Output directory, manifest path, map_package directory, or map.json path.

    Returns:
        World package inspection report.

    Raises:
        FileNotFoundError: If a required public artifact is missing.
        ValueError: If a required artifact is malformed.
    """
    map_json_path = resolve_map_json_path(path)
    package_dir = map_json_path.parent
    root = package_dir.parent
    map_index = _read_object(map_json_path)

    dimensions = _require_object(map_index, "dimensions")
    width = _require_int(dimensions, "width_tiles")
    height = _require_int(dimensions, "height_tiles")
    tile_size_px = _require_int(dimensions, "tile_size_px")

    layers = _require_object(map_index, "layers")
    gameplay = _optional_object(map_index.get("gameplay"))
    objects = _require_object(map_index, "objects")
    catalogs = _optional_object(map_index.get("catalogs"))
    render = _optional_object(map_index.get("render"))

    tile_grid = _read_required_package_object(package_dir, layers, "tile_grid")
    terrain = _read_required_package_object(package_dir, layers, "terrain")
    collision = _read_required_package_object(package_dir, layers, "collision")
    movement = _read_required_package_object(package_dir, layers, "movement_costs")
    elevation = _read_required_package_object(package_dir, layers, "elevation")
    start_goal = _read_optional_package_object(package_dir, layers.get("start_goal"))
    markers = _read_optional_package_object(package_dir, map_index.get("markers"))
    runtime_grids = _read_optional_package_object(
        package_dir,
        map_index.get("runtime_grids"),
    )
    world_graph = _read_optional_package_object(
        package_dir,
        map_index.get("world_graph"),
    )
    routes = _read_optional_package_object(package_dir, map_index.get("routes"))
    gameplay_zones = _read_optional_package_object(
        package_dir,
        map_index.get("gameplay_zones"),
    )
    elevation_model = _read_optional_package_object(
        package_dir,
        map_index.get("elevation_model"),
    )
    elevation_features = _read_optional_package_object(
        package_dir,
        map_index.get("elevation_features"),
    )
    elevation_transitions = _read_optional_package_object(
        package_dir,
        map_index.get("elevation_transitions"),
    )

    runtime_objects = _read_required_package_object(
        package_dir,
        objects,
        "runtime_objects",
    )
    places = _read_optional_package_object(package_dir, objects.get("places"))
    tile_types = _read_optional_package_object(package_dir, catalogs.get("tile_types"))
    object_types = _read_optional_package_object(package_dir, catalogs.get("object_types"))
    tile_render_hints = _read_optional_package_object(
        package_dir,
        render.get("tile_render_hints"),
    )
    object_render_hints = _read_optional_package_object(
        package_dir,
        render.get("object_render_hints"),
    )
    if isinstance(render.get("profile"), str):
        _read_optional_package_object(package_dir, render.get("profile"))

    points = _optional_object(map_index.get("points"))
    start = _optional_point(start_goal.get("start") or points.get("start"))
    goal = _optional_point(start_goal.get("goal") or points.get("goal"))

    tile_grid_stats = _inspect_ascii_grid(
        tile_grid,
        width=width,
        height=height,
        key="rows",
        name="tile_grid",
    )
    terrain_stats = _inspect_type_grid(
        terrain,
        width=width,
        height=height,
        key="rows",
        name="terrain",
    )
    collision_stats = _inspect_collision_grid(
        collision,
        width=width,
        height=height,
    )
    movement_stats = _inspect_movement_costs(movement)
    elevation_stats = _inspect_elevation(elevation)
    elevation_model_summary = _optional_object(elevation_model.get("summary"))
    gameplay_counts = _inspect_gameplay(package_dir, gameplay)
    route_items = _optional_list(routes.get("items"))
    gameplay_zone_items = _optional_list(gameplay_zones.get("items"))
    runtime_items = _optional_list(runtime_objects.get("items"))
    place_items = _optional_list(places.get("items"))
    warnings = _build_warnings(
        start=start,
        goal=goal,
        tile_type_count=len(_optional_object(tile_types.get("types"))),
        object_type_count=len(_optional_object(object_types.get("types"))),
        tile_render_hint_count=len(_optional_object(tile_render_hints.get("hints"))),
        object_render_hint_count=len(_optional_object(object_render_hints.get("hints"))),
    )

    return InspectionReport(
        root=root,
        map_json_path=map_json_path,
        generator_version=_optional_str(map_index.get("generator_version"), "unknown"),
        package_schema_version=_optional_str(
            map_index.get("package_schema_version"),
            "unknown",
        ),
        resolved_seed=map_index.get("resolved_seed", "unknown"),
        profile=_optional_str(map_index.get("profile"), "unknown"),
        width=width,
        height=height,
        tile_size_px=tile_size_px,
        start=start,
        goal=goal,
        tile_grid=tile_grid_stats,
        terrain=terrain_stats,
        collision=collision_stats,
        movement=movement_stats,
        elevation=elevation_stats,
        elevation_model_levels=_string_values(elevation_model_summary.get("levels_present")),
        elevation_model_feature_count=_optional_int(elevation_model_summary.get("feature_count")),
        elevation_model_transition_count=_optional_int(elevation_model_summary.get("transition_count")),
        elevation_missing_levels=_string_values(
            _optional_object(elevation_model.get("v1_completion")).get("missing_levels"),
        ),
        elevation_missing_feature_types=_string_values(
            _optional_object(elevation_model.get("v1_completion")).get("missing_feature_types"),
        ),
        elevation_feature_count=len(_optional_list(elevation_features.get("items"))),
        elevation_transition_count=len(_optional_list(elevation_transitions.get("items"))),
        marker_count=len(_optional_list(markers.get("items"))),
        runtime_grid_count=len(_optional_object(runtime_grids.get("grids"))),
        world_graph_node_count=len(_optional_list(world_graph.get("nodes"))),
        world_graph_edge_count=len(_optional_list(world_graph.get("edges"))),
        world_graph_main_path_length=len(
            _optional_list(_optional_object(world_graph.get("main_path")).get("node_ids")),
        ),
        route_count=len(route_items),
        route_type_counts=_count_by_key(route_items, "type"),
        gameplay_zone_count=len(gameplay_zone_items),
        gameplay_zone_type_counts=_count_by_key(gameplay_zone_items, "type"),
        gameplay_counts=gameplay_counts,
        runtime_object_count=len(runtime_items),
        runtime_object_type_count=len(_unique_types(runtime_items)),
        multi_tile_object_count=sum(_footprint_size(item) > 1 for item in runtime_items),
        max_object_footprint_tiles=max(
            (_footprint_size(item) for item in runtime_items),
            default=0,
        ),
        max_collision_footprint_tiles=max(
            (_collision_footprint_size(item) for item in runtime_items),
            default=0,
        ),
        place_count=len(place_items),
        tile_type_count=len(_optional_object(tile_types.get("types"))),
        object_type_count=len(_optional_object(object_types.get("types"))),
        tile_render_hint_count=len(_optional_object(tile_render_hints.get("hints"))),
        object_render_hint_count=len(_optional_object(object_render_hints.get("hints"))),
        warnings=warnings,
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


def print_report(report: InspectionReport) -> None:
    """Print a human-friendly inspection report.

    Args:
        report: Inspection report to print.
    """
    LOGGER.info("World package: OK")
    LOGGER.info("Root: %s", report.root)
    LOGGER.info("Generator: %s", report.generator_version)
    LOGGER.info("Package schema: %s", report.package_schema_version)
    LOGGER.info("Seed: %s", report.resolved_seed)
    LOGGER.info("Profile: %s", report.profile)
    LOGGER.info(
        "Map: %sx%s tiles, tile size %s px",
        report.width,
        report.height,
        report.tile_size_px,
    )
    LOGGER.info("")
    LOGGER.info("Entrypoints:")
    LOGGER.info("- manifest: OK")
    LOGGER.info("- map_package/map.json: OK (%s)", report.map_json_path)
    LOGGER.info("")
    LOGGER.info("Layers:")
    LOGGER.info(
        "- tile_grid: OK, %sx%s, unique_symbols=%s",
        report.tile_grid.width,
        report.tile_grid.height,
        len(report.tile_grid.unique_values),
    )
    LOGGER.info(
        "- terrain: OK, %sx%s, unique_types=%s",
        report.terrain.width,
        report.terrain.height,
        len(report.terrain.unique_values),
    )
    LOGGER.info(
        "- collision: OK, passable=%s, blocked=%s, blocked_ratio=%.3f",
        report.collision.passable,
        report.collision.blocked,
        report.collision.blocked_ratio,
    )
    LOGGER.info(
        "- movement_costs: OK, count=%s, min=%s, max=%s",
        report.movement.cost_count,
        _format_optional(report.movement.min_cost),
        _format_optional(report.movement.max_cost),
    )
    LOGGER.info(
        "- elevation: OK, cells=%s, levels=%s..%s",
        report.elevation.cell_count,
        _format_optional(report.elevation.min_level),
        _format_optional(report.elevation.max_level),
    )
    LOGGER.info(
        "- elevation_model: OK, levels=%s, features=%s, transitions=%s",
        report.elevation_model_levels,
        report.elevation_model_feature_count,
        report.elevation_model_transition_count,
    )
    LOGGER.info(
        "- elevation_v1: %s",
        "complete" if not report.elevation_missing_levels and not report.elevation_missing_feature_types else "warnings",
    )
    if report.elevation_missing_levels:
        LOGGER.warning("  missing elevation levels: %s", report.elevation_missing_levels)
    if report.elevation_missing_feature_types:
        LOGGER.warning("  missing elevation feature types: %s", report.elevation_missing_feature_types)
    LOGGER.info(
        "- elevation_features: OK, total=%s",
        report.elevation_feature_count,
    )
    LOGGER.info(
        "- elevation_transitions: OK, total=%s",
        report.elevation_transition_count,
    )
    LOGGER.info(
        "- start_goal: OK, start=%s, goal=%s",
        _format_point(report.start),
        _format_point(report.goal),
    )
    LOGGER.info("- markers: OK, count=%s", report.marker_count)
    LOGGER.info("- runtime_grids: OK, grids=%s", report.runtime_grid_count)
    LOGGER.info(
        "- world_graph: OK, nodes=%s, edges=%s, main_path_nodes=%s",
        report.world_graph_node_count,
        report.world_graph_edge_count,
        report.world_graph_main_path_length,
    )
    LOGGER.info(
        "- routes: OK, total=%s, types=%s",
        report.route_count,
        report.route_type_counts,
    )
    LOGGER.info(
        "- gameplay_zones: OK, total=%s, types=%s",
        report.gameplay_zone_count,
        report.gameplay_zone_type_counts,
    )
    LOGGER.info("")
    LOGGER.info("Objects:")
    LOGGER.info(
        "- runtime objects: %s total, %s types",
        report.runtime_object_count,
        report.runtime_object_type_count,
    )
    LOGGER.info(
        "- multi-tile objects: %s, max footprint=%s, max collision footprint=%s",
        report.multi_tile_object_count,
        report.max_object_footprint_tiles,
        report.max_collision_footprint_tiles,
    )
    LOGGER.info("- places: %s total", report.place_count)
    LOGGER.info("")
    LOGGER.info("Gameplay:")
    for name, count in sorted(report.gameplay_counts.items()):
        LOGGER.info("- %s: %s", name, count)
    LOGGER.info("")
    LOGGER.info("Catalogs:")
    LOGGER.info("- tile types: %s", report.tile_type_count)
    LOGGER.info("- object types: %s", report.object_type_count)
    LOGGER.info("")
    LOGGER.info("Render hints:")
    LOGGER.info("- tile hints: %s", report.tile_render_hint_count)
    LOGGER.info("- object hints: %s", report.object_render_hint_count)
    if report.warnings:
        LOGGER.info("")
        LOGGER.info("Warnings:")
        for warning in report.warnings:
            LOGGER.info("- %s", warning)
    LOGGER.info("")
    LOGGER.info("Result:")
    LOGGER.info("- package is loadable by an external consumer")


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


def _inspect_ascii_grid(
    data: dict[str, Any],
    *,
    width: int,
    height: int,
    key: str,
    name: str,
) -> GridStats:
    rows = _require_string_list(data, key)
    _validate_grid_dimensions(rows, width=width, height=height, name=name)
    unique_values = sorted({cell for row in rows for cell in row})
    return GridStats(width=width, height=height, unique_values=unique_values)


def _inspect_type_grid(
    data: dict[str, Any],
    *,
    width: int,
    height: int,
    key: str,
    name: str,
) -> GridStats:
    rows = data.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        raise ValueError(f"Expected list row grid field for {name}.{key}")
    if len(rows) != height:
        raise ValueError(f"{name} height mismatch: expected {height}, got {len(rows)}")
    values: set[str] = set()
    for row_index, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(
                f"{name} width mismatch at row {row_index}: "
                f"expected {width}, got {len(row)}",
            )
        for value in row:
            if not isinstance(value, str):
                raise ValueError(f"{name} contains non-string cell at row {row_index}")
            values.add(value)
    return GridStats(width=width, height=height, unique_values=sorted(values))


def _inspect_collision_grid(
    data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> CollisionStats:
    rows = _require_string_list(data, "rows")
    _validate_grid_dimensions(rows, width=width, height=height, name="collision")
    passable = 0
    blocked = 0
    for row in rows:
        for cell in row:
            if cell == "0":
                passable += 1
            elif cell == "1":
                blocked += 1
            else:
                raise ValueError(f"Unknown collision value: {cell!r}")
    return CollisionStats(passable=passable, blocked=blocked, total=width * height)


def _inspect_movement_costs(data: dict[str, Any]) -> MovementStats:
    values = _numeric_values(_optional_object(data.get("costs_by_type")))
    if not values:
        values = _numeric_values(_optional_object(data.get("costs_by_tile")))
    return MovementStats(
        cost_count=len(values),
        min_cost=min(values) if values else None,
        max_cost=max(values) if values else None,
    )


def _inspect_elevation(data: dict[str, Any]) -> ElevationStats:
    elevation = _optional_object(data.get("elevation"))
    levels: list[int] = []
    for key, value in elevation.items():
        if isinstance(value, int):
            levels.append(value)
            continue
        if isinstance(value, dict):
            level = value.get("level") or value.get("elevation")
            if isinstance(level, int):
                levels.append(level)
                continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    level = item.get("level") or item.get("elevation")
                    if isinstance(level, int):
                        levels.append(level)
                elif isinstance(item, int):
                    levels.append(item)
            continue
        if key in {"cells", "items"} and isinstance(value, list):
            continue
    return ElevationStats(
        cell_count=len(levels),
        min_level=min(levels) if levels else None,
        max_level=max(levels) if levels else None,
    )


def _inspect_gameplay(package_dir: Path, gameplay: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, relative_path in gameplay.items():
        if not isinstance(name, str) or not isinstance(relative_path, str):
            continue
        data = _read_object(package_dir / relative_path)
        counts[name] = len(_optional_list(data.get("items")))
    return counts


def _validate_grid_dimensions(
    rows: list[str],
    *,
    width: int,
    height: int,
    name: str,
) -> None:
    if len(rows) != height:
        raise ValueError(f"{name} height mismatch: expected {height}, got {len(rows)}")
    for row_index, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(
                f"{name} width mismatch at row {row_index}: "
                f"expected {width}, got {len(row)}",
            )


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


def _optional_str(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        return value
    return fallback


def _numeric_values(data: dict[str, Any]) -> list[int | float]:
    return [value for value in data.values() if isinstance(value, int | float)]


def _footprint_size(item: Any) -> int:
    if not isinstance(item, dict):
        return 0
    footprint = item.get("footprint")
    if not isinstance(footprint, list):
        return 0
    return sum(1 for point in footprint if _is_point_list(point))


def _collision_footprint_size(item: Any) -> int:
    if not isinstance(item, dict):
        return 0
    footprint = item.get("collision_footprint")
    if not isinstance(footprint, list):
        return 0
    return sum(1 for point in footprint if _is_point_list(point))


def _is_point_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], int)
    )


def _unique_types(items: list[Any]) -> set[str]:
    types: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if isinstance(item_type, str):
            types.add(item_type)
    return types



def _count_by_key(items: list[Any], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(key)
        if not isinstance(value, str):
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts

def _build_warnings(
    *,
    start: dict[str, int] | None,
    goal: dict[str, int] | None,
    tile_type_count: int,
    object_type_count: int,
    tile_render_hint_count: int,
    object_render_hint_count: int,
) -> list[str]:
    warnings: list[str] = []
    if start is None:
        warnings.append("start point is missing")
    if goal is None:
        warnings.append("goal point is missing")
    if tile_type_count == 0:
        warnings.append("tile type catalog is empty")
    if object_type_count == 0:
        warnings.append("object type catalog is empty")
    if tile_render_hint_count == 0:
        warnings.append("tile render hints are empty")
    if object_render_hint_count == 0:
        warnings.append("object render hints are empty")
    return warnings


def _format_point(point: dict[str, int] | None) -> str:
    if point is None:
        return "missing"
    return f"({point['x']},{point['y']})"


def _format_optional(value: object) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _optional_int(value: Any) -> int:
    return int(value) if isinstance(value, int) else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect a TopDownMapGen world package as an external consumer.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Output directory, _manifest.json, map_package directory, or map.json.",
    )
    return parser


def main() -> int:
    """Run the inspection CLI.

    Returns:
        Process exit code.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_parser().parse_args()
    try:
        report = inspect_world_package(args.path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.error("World package: FAILED")
        LOGGER.error("- %s", exc)
        return 1
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
