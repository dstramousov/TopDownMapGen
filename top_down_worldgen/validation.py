from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from .manifest import VALIDATION_REPORT_SCHEMA_VERSION
from .tactical.places import (
    MAX_PLACES,
    MIN_PLACES,
    MIN_PLACE_DISTANCE_TILES,
    PLACE_TYPE_NAMES,
)
from .tactical.runtime_objects import (
    BUNKER_TYPES,
    COLLISION_MOVEMENT_VALUES,
    COLLISION_PROJECTILE_VALUES,
    COLLISION_VISION_VALUES,
    COMBAT_PROPERTY_VALUE_MAX,
    COMBAT_PROPERTY_VALUE_MIN,
    COVER_TYPES,
    INTEREST_POINT_TYPES,
    LANDMARK_MIN_DISTANCE_TILES,
    LANDMARK_TYPES,
    MAX_AMMO_CACHES,
    MAX_ELEVATION_LEVEL,
    MAX_OBJECT_HEIGHT,
    MAX_MEDKIT_CACHES,
    MAX_LANDMARKS,
    MAX_RUNTIME_OBJECTS,
    MAX_TRENCHES,
    MIN_AMMO_CACHES,
    MIN_MEDKIT_CACHES,
    MIN_LANDMARKS,
    MIN_TRENCHES,
    PASSABLE_OBJECT_TILES,
    MIN_ELEVATION_LEVEL,
    MIN_OBJECT_HEIGHT,
    RUNTIME_OBJECT_TYPE_NAMES,
    TRENCH_ELEVATION_LEVEL,
)
from .paths import OutputPaths
from .utils.json_io import write_json

EDGE_WARNING_MARGIN_TILES = 1
SOFT_VALIDATION_CHECKS = frozenset(
    {
        "combat_zones_non_empty",
        "runtime_objects_non_empty",
        "runtime_objects_counts_within_limits",
        "interest_points_non_empty",
        "ammo_caches_within_limits",
        "medkit_caches_within_limits",
        "trenches_non_empty",
        "trenches_within_limits",
        "landmarks_within_limits",
        "landmarks_min_distance",
        "places_non_empty",
        "places_counts_within_limits",
        "places_min_distance",
    },
)


def build_validation_report(
    *,
    outputs: OutputPaths,
    rows: list[str],
    width: int,
    height: int,
    runtime_data: dict[str, Any],
    resolved_seed: int,
) -> dict[str, Any]:
    """Build a detailed validation report for generated artifacts.

    Args:
        outputs: Output path bundle.
        rows: ASCII map rows.
        width: Resolved map width in tiles.
        height: Resolved map height in tiles.
        runtime_data: Runtime tactical map data.
        resolved_seed: Concrete uint64 seed used by this generation run.

    Returns:
        JSON-serializable validation report.
    """
    map_data = runtime_data.get("map", {})
    tile_grid = _string_list(map_data.get("tile_grid"))
    tile_counts = map_data.get("tile_counts", {})
    checks = {
        "ascii_map_exists": outputs.generated_map.exists(),
        "ascii_map_non_empty": bool(rows),
        "ascii_map_rectangular": _is_rectangular(rows, width),
        "dimensions_match": map_data.get("width") == width
        and map_data.get("height") == height,
        "tactical_map_exists": outputs.tactical_map.exists(),
        "tactical_debug_exists": outputs.tactical_map_debug.exists(),
        "tile_grid_embedded": tile_grid == rows,
        "metrics_exists": outputs.metrics.exists(),
        "object_catalog_exists": outputs.object_catalog.exists(),
        "map_package_index_exists": outputs.map_package_map.exists(),
        "map_package_markers_exists": outputs.map_package_markers.exists(),
        "map_package_runtime_grids_exists": outputs.map_package_runtime_grids.exists(),
        "map_package_world_graph_exists": outputs.map_package_world_graph.exists(),
        "map_package_routes_exists": outputs.map_package_routes.exists(),
        "map_package_tile_grid_exists": outputs.map_package_tile_grid.exists(),
        "map_package_terrain_exists": outputs.map_package_terrain.exists(),
        "map_package_movement_costs_exists": (
            outputs.map_package_movement_costs.exists()
        ),
        "map_package_collision_exists": outputs.map_package_collision.exists(),
        "map_package_elevation_exists": outputs.map_package_elevation.exists(),
        "map_package_start_goal_exists": outputs.map_package_start_goal.exists(),
        "map_package_gameplay_exists": _map_package_gameplay_exists(outputs),
        "map_package_objects_exist": _map_package_objects_exist(outputs),
        "map_package_catalogs_exist": _map_package_catalogs_exist(outputs),
        "map_package_render_hints_exist": _map_package_render_hints_exist(outputs),
        "single_start_exists": _count_tiles(tile_grid, "S") == 1,
        "single_goal_exists": _count_tiles(tile_grid, "G") == 1,
        "tile_grid_matches_dimensions": _grid_matches_dimensions(
            tile_grid,
            width=width,
            height=height,
        ),
        "tile_counts_match_grid": _tile_counts_match_grid(tile_counts, tile_grid),
        "combat_zones_non_empty": bool(_dict_list(runtime_data.get("combat_zones"))),
        "enemy_spawns_match_allowed_zones": _enemy_spawns_match_allowed_zones(
            runtime_data,
        ),
        "fallbacks_have_zone_refs": _fallbacks_have_zone_refs(runtime_data),
        "flank_routes_have_waypoints": _flank_routes_have_waypoints(
            runtime_data,
            width=width,
            height=height,
        ),
        "zone_cover_refs_valid": _zone_cover_refs_valid(runtime_data),
        "runtime_objects_non_empty": bool(_runtime_objects(runtime_data)),
        "runtime_objects_have_unique_ids": _runtime_objects_have_unique_ids(
            runtime_data,
        ),
        "runtime_objects_inside_map": _runtime_objects_inside_map(
            runtime_data,
            width=width,
            height=height,
        ),
        "runtime_objects_have_valid_types": _runtime_objects_have_valid_types(
            runtime_data,
        ),
        "runtime_objects_have_valid_cover": _runtime_objects_have_valid_cover(
            runtime_data,
        ),
        "runtime_objects_have_valid_heights": _runtime_objects_have_valid_heights(
            runtime_data,
        ),
        "runtime_objects_have_valid_elevation": _runtime_objects_have_valid_elevation(
            runtime_data,
        ),
        "runtime_objects_have_footprints": _runtime_objects_have_footprints(
            runtime_data,
        ),
        "runtime_objects_have_collision_footprints": (
            _runtime_objects_have_collision_footprints(runtime_data)
        ),
        "runtime_objects_have_visual_bounds": _runtime_objects_have_visual_bounds(
            runtime_data,
        ),
        "runtime_objects_have_pivots": _runtime_objects_have_pivots(runtime_data),
        "runtime_object_collision_footprints_inside_map": (
            _runtime_object_collision_footprints_inside_map(
                runtime_data,
                width=width,
                height=height,
            )
        ),
        "runtime_objects_have_collision_profiles": (
            _runtime_objects_have_collision_profiles(runtime_data)
        ),
        "runtime_objects_have_combat_properties": (
            _runtime_objects_have_combat_properties(runtime_data)
        ),
        "cover_values_in_range": _combat_property_values_in_range(
            runtime_data,
            property_name="cover_value",
        ),
        "concealment_values_in_range": _combat_property_values_in_range(
            runtime_data,
            property_name="concealment_value",
        ),
        "trench_objects_have_stance_hints": _trench_objects_have_stance_hints(
            runtime_data,
        ),
        "bunker_objects_have_firing_ports": _bunker_objects_have_firing_ports(
            runtime_data,
        ),
        "explosive_objects_tagged": _explosive_objects_tagged(runtime_data),
        "loot_objects_tagged": _loot_objects_tagged(runtime_data),
        "runtime_objects_do_not_overlap_start_goal": (
            _runtime_objects_do_not_overlap_start_goal(runtime_data, tile_grid)
        ),
        "runtime_objects_do_not_overlap": _runtime_objects_do_not_overlap(
            runtime_data,
        ),
        "runtime_objects_avoid_blocked_tiles": _runtime_objects_avoid_blocked_tiles(
            runtime_data,
            tile_grid,
        ),
        "runtime_objects_counts_within_limits": (
            len(_runtime_objects(runtime_data)) <= MAX_RUNTIME_OBJECTS
        ),
        "interest_points_non_empty": bool(_interest_points(runtime_data)),
        "ammo_caches_within_limits": _runtime_object_type_count_within_limits(
            runtime_data,
            object_type="ammo_cache",
            min_count=MIN_AMMO_CACHES,
            max_count=MAX_AMMO_CACHES,
        ),
        "medkit_caches_within_limits": _runtime_object_type_count_within_limits(
            runtime_data,
            object_type="medkit_cache",
            min_count=MIN_MEDKIT_CACHES,
            max_count=MAX_MEDKIT_CACHES,
        ),
        "interest_points_inside_map": _runtime_objects_inside_map(
            {"runtime_objects": _interest_points(runtime_data)},
            width=width,
            height=height,
        ),
        "interest_points_do_not_overlap": _runtime_objects_do_not_overlap(
            {"runtime_objects": _interest_points(runtime_data)},
        ),
        "interest_points_avoid_start_goal": (
            _runtime_objects_do_not_overlap_start_goal(
                {"runtime_objects": _interest_points(runtime_data)},
                tile_grid,
            )
        ),
        "interest_points_do_not_overlap_cover": _interest_points_do_not_overlap_cover(
            runtime_data,
        ),
        "trenches_non_empty": bool(_trenches(runtime_data)),
        "trenches_within_limits": _runtime_object_type_count_within_limits(
            runtime_data,
            object_type="trench",
            min_count=MIN_TRENCHES,
            max_count=MAX_TRENCHES,
        ),
        "trench_cells_have_negative_elevation": (
            _trench_cells_have_negative_elevation(runtime_data)
        ),
        "trench_footprints_inside_map": _runtime_objects_inside_map(
            {"runtime_objects": _trenches(runtime_data)},
            width=width,
            height=height,
        ),
        "trenches_do_not_overlap_start_goal": (
            _runtime_objects_do_not_overlap_start_goal(
                {"runtime_objects": _trenches(runtime_data)},
                tile_grid,
            )
        ),
        "trenches_do_not_overlap_blocked_tiles": (
            _runtime_objects_avoid_blocked_tiles(
                {"runtime_objects": _trenches(runtime_data)},
                tile_grid,
            )
        ),
        "elevation_cells_match_trench_footprints": (
            _elevation_cells_match_trench_footprints(runtime_data)
        ),
        "trench_shapes_valid": _trench_shapes_valid(runtime_data),
        "trench_footprints_connected": _trench_footprints_connected(runtime_data),
        "l_shaped_trenches_have_corner": _l_shaped_trenches_have_corner(runtime_data),
        "landmarks_within_limits": _landmarks_within_limits(runtime_data),
        "landmarks_inside_map": _runtime_objects_inside_map(
            {"runtime_objects": _landmarks(runtime_data)},
            width=width,
            height=height,
        ),
        "landmarks_do_not_overlap": _runtime_objects_do_not_overlap(
            {"runtime_objects": _landmarks(runtime_data)},
        ),
        "landmarks_avoid_start_goal": (
            _runtime_objects_do_not_overlap_start_goal(
                {"runtime_objects": _landmarks(runtime_data)},
                tile_grid,
            )
        ),
        "landmarks_min_distance": _landmarks_min_distance(runtime_data),
        "elevation_cells_inside_map": _elevation_cells_inside_map(
            runtime_data,
            width=width,
            height=height,
        ),
        "elevation_levels_valid": _elevation_levels_valid(runtime_data),
        "places_non_empty": bool(_places(runtime_data)),
        "places_have_unique_ids": _places_have_unique_ids(runtime_data),
        "places_have_valid_types": _places_have_valid_types(runtime_data),
        "places_have_valid_object_refs": _places_have_valid_object_refs(runtime_data),
        "places_have_v2_metadata": _places_have_v2_metadata(runtime_data),
        "places_have_bounds": _places_have_bounds(runtime_data),
        "places_have_entrances": _places_have_entrances(runtime_data),
        "places_have_connections": _places_have_connections(runtime_data),
        "places_inside_map": _places_inside_map(
            runtime_data,
            width=width,
            height=height,
        ),
        "places_counts_within_limits": _places_counts_within_limits(runtime_data),
        "places_min_distance": _places_min_distance(runtime_data),
    }
    checks.update(
        _build_map_package_consistency_checks(
            outputs=outputs,
            width=width,
            height=height,
        ),
    )
    failed_checks = [name for name, passed in checks.items() if not passed]
    errors = [name for name in failed_checks if name not in SOFT_VALIDATION_CHECKS]
    warnings = build_validation_warnings(
        runtime_data=runtime_data,
        width=width,
        height=height,
    )
    warnings.extend(_soft_check_warnings(failed_checks))
    return {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "status": _validation_status(errors=errors, warnings=warnings),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "metadata": {
            "width": width,
            "height": height,
            "resolved_seed": resolved_seed,
            "artifact_count": _count_existing_outputs(outputs),
        },
    }


def _validation_status(*, errors: list[str], warnings: list[dict[str, Any]]) -> str:
    if errors:
        return "failed"
    if warnings:
        return "passed_with_warnings"
    return "passed"


def _soft_check_warnings(failed_checks: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "code": f"quality.{name}",
            "level": "warning",
            "message": f"Soft validation check failed: {name}",
        }
        for name in failed_checks
        if name in SOFT_VALIDATION_CHECKS
    ]


def _map_package_gameplay_exists(outputs: OutputPaths) -> bool:
    return all(
        path.exists()
        for path in (
            outputs.map_package_combat_zones,
            outputs.map_package_cover_points,
            outputs.map_package_choke_points,
            outputs.map_package_flank_routes,
            outputs.map_package_enemy_spawn_zones,
            outputs.map_package_fallback_positions,
        )
    )


def _map_package_objects_exist(outputs: OutputPaths) -> bool:
    return (
        outputs.map_package_runtime_objects.exists()
        and outputs.map_package_places.exists()
    )


def _map_package_catalogs_exist(outputs: OutputPaths) -> bool:
    return (
        outputs.map_package_tile_types.exists()
        and outputs.map_package_object_types.exists()
    )


def _map_package_render_hints_exist(outputs: OutputPaths) -> bool:
    return (
        outputs.map_package_render_profile.exists()
        and outputs.map_package_tile_render_hints.exists()
        and outputs.map_package_object_render_hints.exists()
    )


def _build_map_package_consistency_checks(
    *,
    outputs: OutputPaths,
    width: int,
    height: int,
) -> dict[str, bool]:
    if not outputs.map_package_map.exists():
        return _failed_package_checks()
    package = _load_package_context(outputs)
    if package is None:
        return _failed_package_checks()
    return {
        "map_package_files_have_schema_versions": (
            _package_files_have_schema_versions(package)
        ),
        "map_package_dimensions_match_layers": _package_dimensions_match_layers(
            package,
            width=width,
            height=height,
        ),
        "map_package_runtime_grids_have_required_grids": (
            _runtime_grids_have_required_grids(package)
        ),
        "map_package_runtime_grids_match_dimensions": (
            _runtime_grids_match_dimensions(package, width=width, height=height)
        ),
        "map_package_markers_inside_map": _package_markers_inside_map(
            package,
            width=width,
            height=height,
        ),
        "map_package_start_goal_markers_match_layer": (
            _package_start_goal_markers_match_layer(package)
        ),
        "map_package_start_goal_not_blocked": _package_start_goal_not_blocked(package),
        "map_package_runtime_object_refs_valid": _package_runtime_object_refs_valid(
            package,
        ),
        "map_package_places_reference_existing_objects": (
            _package_places_reference_existing_objects(package)
        ),
        "map_package_places_reference_existing_markers": (
            _package_places_reference_existing_markers(package)
        ),
        "map_package_places_entrances_inside_map": (
            _package_places_entrances_inside_map(package, width=width, height=height)
        ),
        "map_package_world_graph_refs_valid": _package_world_graph_refs_valid(
            package,
        ),
        "map_package_world_graph_main_path_valid": (
            _package_world_graph_main_path_valid(package)
        ),
        "map_package_routes_refs_valid": _package_routes_refs_valid(package),
        "map_package_route_waypoints_inside_map": _package_route_waypoints_inside_map(
            package,
            width=width,
            height=height,
        ),
    }


def _failed_package_checks() -> dict[str, bool]:
    return {
        "map_package_files_have_schema_versions": False,
        "map_package_dimensions_match_layers": False,
        "map_package_runtime_grids_have_required_grids": False,
        "map_package_runtime_grids_match_dimensions": False,
        "map_package_markers_inside_map": False,
        "map_package_start_goal_markers_match_layer": False,
        "map_package_start_goal_not_blocked": False,
        "map_package_runtime_object_refs_valid": False,
        "map_package_places_reference_existing_objects": False,
        "map_package_places_reference_existing_markers": False,
        "map_package_places_entrances_inside_map": False,
        "map_package_world_graph_refs_valid": False,
        "map_package_world_graph_main_path_valid": False,
        "map_package_routes_refs_valid": False,
        "map_package_route_waypoints_inside_map": False,
    }


def _load_package_context(outputs: OutputPaths) -> dict[str, Any] | None:
    try:
        package_dir = outputs.map_package_dir
        map_index = _read_json_object(outputs.map_package_map)
        layers = _json_object(map_index.get("layers"))
        objects = _json_object(map_index.get("objects"))
        catalogs = _json_object(map_index.get("catalogs"))
        render = _json_object(map_index.get("render"))
        return {
            "map_index": map_index,
            "tile_grid": _read_json_object(package_dir / str(layers.get("tile_grid"))),
            "terrain": _read_json_object(package_dir / str(layers.get("terrain"))),
            "collision": _read_json_object(package_dir / str(layers.get("collision"))),
            "movement_costs": _read_json_object(
                package_dir / str(layers.get("movement_costs")),
            ),
            "elevation": _read_json_object(package_dir / str(layers.get("elevation"))),
            "start_goal": _read_json_object(package_dir / str(layers.get("start_goal"))),
            "markers": _read_json_object(package_dir / str(map_index.get("markers"))),
            "runtime_grids": _read_json_object(
                package_dir / str(map_index.get("runtime_grids")),
            ),
            "world_graph": _read_json_object(
                package_dir / str(map_index.get("world_graph")),
            ),
            "routes": _read_json_object(package_dir / str(map_index.get("routes"))),
            "runtime_objects": _read_json_object(
                package_dir / str(objects.get("runtime_objects")),
            ),
            "places": _read_json_object(package_dir / str(objects.get("places"))),
            "tile_types": _read_json_object(package_dir / str(catalogs.get("tile_types"))),
            "object_types": _read_json_object(
                package_dir / str(catalogs.get("object_types")),
            ),
            "render_profile": _read_json_object(package_dir / str(render.get("profile"))),
            "tile_render_hints": _read_json_object(
                package_dir / str(render.get("tile_render_hints")),
            ),
            "object_render_hints": _read_json_object(
                package_dir / str(render.get("object_render_hints")),
            ),
        }
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _json_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _package_files_have_schema_versions(package: dict[str, Any]) -> bool:
    required = (
        "map_index",
        "tile_grid",
        "terrain",
        "collision",
        "movement_costs",
        "elevation",
        "start_goal",
        "markers",
        "runtime_grids",
        "world_graph",
        "routes",
        "runtime_objects",
        "places",
        "tile_types",
        "object_types",
        "render_profile",
        "tile_render_hints",
        "object_render_hints",
    )
    for key in required:
        schema_version = _json_object(package.get(key)).get("schema_version")
        if not isinstance(schema_version, str) or not schema_version:
            return False
    return True


def _package_dimensions_match_layers(
    package: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    return all(
        _package_layer_dimensions_match(_json_object(package.get(key)), width=width, height=height)
        for key in ("tile_grid", "terrain", "collision", "elevation", "start_goal")
    )


def _package_layer_dimensions_match(
    data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    return data.get("width") == width and data.get("height") == height


def _runtime_grids_have_required_grids(package: dict[str, Any]) -> bool:
    grids = _json_object(_json_object(package.get("runtime_grids")).get("grids"))
    required = {
        "movement_grid",
        "collision_grid",
        "projectile_block_grid",
        "vision_block_grid",
        "cover_grid",
        "concealment_grid",
        "height_grid",
    }
    return required.issubset(grids)


def _runtime_grids_match_dimensions(
    package: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    grids = _json_object(_json_object(package.get("runtime_grids")).get("grids"))
    for grid in grids.values():
        if not isinstance(grid, dict):
            return False
        rows = grid.get("rows")
        if not isinstance(rows, list) or len(rows) != height:
            return False
        for row in rows:
            if isinstance(row, str):
                if len(row) != width:
                    return False
            elif isinstance(row, list):
                if len(row) != width:
                    return False
            else:
                return False
    return True


def _package_markers_inside_map(
    package: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for marker in _dict_list(_json_object(package.get("markers")).get("items")):
        point = _mapping_point(marker.get("position"))
        if point is None or not _point_in_bounds(point, width=width, height=height):
            return False
    return True


def _package_start_goal_markers_match_layer(package: dict[str, Any]) -> bool:
    start_goal = _json_object(package.get("start_goal"))
    start = _mapping_point(start_goal.get("start"))
    goal = _mapping_point(start_goal.get("goal"))
    if start is None or goal is None:
        return False
    markers = _dict_list(_json_object(package.get("markers")).get("items"))
    marker_by_type = {str(marker.get("type")): marker for marker in markers}
    return (
        _mapping_point(_json_object(marker_by_type.get("start")).get("position")) == start
        and _mapping_point(_json_object(marker_by_type.get("goal")).get("position")) == goal
    )


def _package_start_goal_not_blocked(package: dict[str, Any]) -> bool:
    start_goal = _json_object(package.get("start_goal"))
    for point in (_mapping_point(start_goal.get("start")), _mapping_point(start_goal.get("goal"))):
        if point is None or _collision_grid_value(package, point) != "0":
            return False
    return True


def _collision_grid_value(package: dict[str, Any], point: tuple[int, int]) -> str | None:
    grids = _json_object(_json_object(package.get("runtime_grids")).get("grids"))
    collision_grid = _json_object(grids.get("collision_grid"))
    rows = collision_grid.get("rows")
    if not isinstance(rows, list):
        return None
    x, y = point
    try:
        row = rows[y]
    except IndexError:
        return None
    if isinstance(row, str) and 0 <= x < len(row):
        return row[x]
    if isinstance(row, list) and 0 <= x < len(row):
        return str(row[x])
    return None


def _package_runtime_object_refs_valid(package: dict[str, Any]) -> bool:
    object_types = set(_json_object(_json_object(package.get("object_types")).get("types")))
    for item in _dict_list(_json_object(package.get("runtime_objects")).get("items")):
        object_id = item.get("id")
        object_type = item.get("type")
        if not isinstance(object_id, str) or not object_id:
            return False
        if not isinstance(object_type, str) or object_type not in object_types:
            return False
    return True


def _package_places_reference_existing_objects(package: dict[str, Any]) -> bool:
    object_ids = _package_runtime_object_ids(package)
    for place in _dict_list(_json_object(package.get("places")).get("items")):
        refs = _place_object_ref_ids(place)
        if not refs:
            return False
        if any(ref not in object_ids for ref in refs):
            return False
    return True


def _place_object_ref_ids(place: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    object_refs = place.get("object_refs")
    if isinstance(object_refs, list):
        for ref in object_refs:
            if isinstance(ref, str):
                refs.append(ref)
            elif isinstance(ref, dict) and isinstance(ref.get("id"), str):
                refs.append(ref["id"])
    refs.extend(_string_list(place.get("object_ids")))
    return sorted(set(refs))


def _package_places_reference_existing_markers(package: dict[str, Any]) -> bool:
    marker_ids = _package_marker_ids(package)
    for place in _dict_list(_json_object(package.get("places")).get("items")):
        refs = _string_list(place.get("marker_refs"))
        if any(ref not in marker_ids for ref in refs):
            return False
    return True


def _package_places_entrances_inside_map(
    package: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for place in _dict_list(_json_object(package.get("places")).get("items")):
        entrances = _dict_list(place.get("entrances"))
        if not entrances:
            return False
        for entrance in entrances:
            point = _mapping_point(entrance.get("position"))
            if point is None or not _point_in_bounds(point, width=width, height=height):
                return False
    return True


def _package_world_graph_refs_valid(package: dict[str, Any]) -> bool:
    nodes = _dict_list(_json_object(package.get("world_graph")).get("nodes"))
    edges = _dict_list(_json_object(package.get("world_graph")).get("edges"))
    node_ids = {str(node.get("id")) for node in nodes if isinstance(node.get("id"), str)}
    if not {"marker:start", "marker:goal"}.issubset(node_ids):
        return False
    marker_ids = _package_marker_ids(package)
    place_ids = _package_place_ids(package)
    for node in nodes:
        source = node.get("source")
        if source == "markers" and str(node.get("marker_ref")) not in marker_ids:
            return False
        if source == "places" and str(node.get("place_ref")) not in place_ids:
            return False
    for edge in edges:
        if str(edge.get("source")) not in node_ids or str(edge.get("target")) not in node_ids:
            return False
    return True


def _package_world_graph_main_path_valid(package: dict[str, Any]) -> bool:
    graph = _json_object(package.get("world_graph"))
    node_ids = {
        str(node.get("id"))
        for node in _dict_list(graph.get("nodes"))
        if isinstance(node.get("id"), str)
    }
    main_path = _json_object(graph.get("main_path"))
    path_nodes = _string_list(main_path.get("node_ids"))
    if len(path_nodes) < 2:
        return False
    if path_nodes[0] != "marker:start" or path_nodes[-1] != "marker:goal":
        return False
    return all(node_id in node_ids for node_id in path_nodes)


def _package_routes_refs_valid(package: dict[str, Any]) -> bool:
    graph = _json_object(package.get("world_graph"))
    node_ids = {
        str(node.get("id"))
        for node in _dict_list(graph.get("nodes"))
        if isinstance(node.get("id"), str)
    }
    edge_ids = {
        str(edge.get("id"))
        for edge in _dict_list(graph.get("edges"))
        if isinstance(edge.get("id"), str)
    }
    valid_types = {"main_road", "side_path", "hidden_path", "patrol_route", "escape_route"}
    for route in _dict_list(_json_object(package.get("routes")).get("items")):
        if route.get("type") not in valid_types:
            return False
        if any(node_id not in node_ids for node_id in _string_list(route.get("node_ids"))):
            return False
        if any(edge_id not in edge_ids for edge_id in _string_list(route.get("edge_ids"))):
            return False
    return True


def _package_route_waypoints_inside_map(
    package: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for route in _dict_list(_json_object(package.get("routes")).get("items")):
        for waypoint in _dict_list(route.get("waypoints")):
            point = _mapping_point(waypoint)
            if point is None or not _point_in_bounds(point, width=width, height=height):
                return False
    return True


def _package_runtime_object_ids(package: dict[str, Any]) -> set[str]:
    return {
        str(item.get("id"))
        for item in _dict_list(_json_object(package.get("runtime_objects")).get("items"))
        if isinstance(item.get("id"), str)
    }


def _package_marker_ids(package: dict[str, Any]) -> set[str]:
    return {
        str(item.get("id"))
        for item in _dict_list(_json_object(package.get("markers")).get("items"))
        if isinstance(item.get("id"), str)
    }


def _package_place_ids(package: dict[str, Any]) -> set[str]:
    return {
        str(item.get("id"))
        for item in _dict_list(_json_object(package.get("places")).get("items"))
        if isinstance(item.get("id"), str)
    }


def _mapping_point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    try:
        return int(value["x"]), int(value["y"])
    except (KeyError, TypeError, ValueError):
        return None


def write_validation_report(report: dict[str, Any], path: Path) -> None:
    """Write a validation report to disk.

    Args:
        report: Validation report JSON object.
        path: Output path.
    """
    write_json(report, path)


def validation_summary_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """Build compact manifest validation summary from a detailed report.

    Args:
        report: Detailed validation report.

    Returns:
        Compact validation summary.
    """
    return {
        "status": report.get("status", "failed"),
        "checks": report.get("checks", {}),
        "errors": report.get("errors", []),
        "warnings": report.get("warnings", []),
    }


def build_validation_warnings(
    *,
    runtime_data: dict[str, Any],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    """Build non-failing validation warnings.

    Args:
        runtime_data: Runtime tactical map data.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        List of warning descriptors.
    """
    warnings: list[dict[str, Any]] = []
    edge_counts = {
        "cover_points_near_edge": _count_points_near_edge(
            runtime_data.get("cover_points", []),
            width=width,
            height=height,
        ),
        "choke_points_near_edge": _count_points_near_edge(
            runtime_data.get("choke_points", []),
            width=width,
            height=height,
        ),
        "enemy_spawns_near_edge": _count_points_near_edge(
            runtime_data.get("enemy_spawn_zones", []),
            width=width,
            height=height,
        ),
        "fallbacks_near_edge": _count_points_near_edge(
            runtime_data.get("fallback_positions", []),
            width=width,
            height=height,
        ),
    }
    if any(edge_counts.values()):
        warnings.append(
            {
                "code": "tactical_points_near_map_edge",
                "level": "warning",
                "details": edge_counts,
            },
        )
    return warnings


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _is_rectangular(rows: list[str], width: int) -> bool:
    return bool(rows) and width > 0 and all(len(row) == width for row in rows)


def _grid_matches_dimensions(tile_grid: list[str], *, width: int, height: int) -> bool:
    return (
        bool(tile_grid)
        and height > 0
        and width > 0
        and len(tile_grid) == height
        and all(len(row) == width for row in tile_grid)
    )


def _tile_counts_match_grid(tile_counts: Any, tile_grid: list[str]) -> bool:
    if not isinstance(tile_counts, dict) or not tile_grid:
        return False
    actual = dict(sorted(Counter("".join(tile_grid)).items()))
    try:
        normalized = {str(key): int(value) for key, value in tile_counts.items()}
    except (TypeError, ValueError):
        return False
    return normalized == actual


def _count_tiles(tile_grid: list[str], tile: str) -> int:
    return sum(row.count(tile) for row in tile_grid)


def _enemy_spawns_match_allowed_zones(runtime_data: dict[str, Any]) -> bool:
    zones = _dict_list(runtime_data.get("combat_zones"))
    zone_by_id = {str(zone.get("id")): zone for zone in zones}
    spawns = _dict_list(runtime_data.get("enemy_spawn_zones"))
    for spawn in spawns:
        zone_id = spawn.get("zone_id")
        zone = zone_by_id.get(str(zone_id))
        if zone is None:
            return False
        if zone.get("enemy_spawns_allowed") is not True:
            return False
        if spawn.get("type") != zone.get("type"):
            return False
    return True


def _fallbacks_have_zone_refs(runtime_data: dict[str, Any]) -> bool:
    zone_ids = {str(zone.get("id")) for zone in _dict_list(runtime_data.get("combat_zones"))}
    cover_ids = {str(point.get("id")) for point in _dict_list(runtime_data.get("cover_points"))}
    for fallback in _dict_list(runtime_data.get("fallback_positions")):
        if str(fallback.get("zone_id")) not in zone_ids:
            return False
        cover_point_id = fallback.get("cover_point_id")
        if cover_point_id is not None and str(cover_point_id) not in cover_ids:
            return False
    return True


def _flank_routes_have_waypoints(
    runtime_data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for route in _dict_list(runtime_data.get("flank_routes")):
        waypoints = route.get("waypoints")
        if not isinstance(waypoints, list) or not waypoints:
            return False
        for waypoint in waypoints:
            point = _point(waypoint)
            if point is None or not _point_in_bounds(point, width=width, height=height):
                return False
    return True


def _zone_cover_refs_valid(runtime_data: dict[str, Any]) -> bool:
    cover_ids = {str(point.get("id")) for point in _dict_list(runtime_data.get("cover_points"))}
    for zone in _dict_list(runtime_data.get("combat_zones")):
        cover_point_ids = zone.get("cover_point_ids", [])
        if not isinstance(cover_point_ids, list):
            return False
        for cover_id in cover_point_ids:
            if str(cover_id) not in cover_ids:
                return False
    return True



def _runtime_objects(runtime_data: dict[str, Any]) -> list[dict[str, Any]]:
    return _dict_list(runtime_data.get("runtime_objects"))


def _interest_points(runtime_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in _runtime_objects(runtime_data)
        if item.get("type") in INTEREST_POINT_TYPES
    ]


def _landmarks(runtime_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in _runtime_objects(runtime_data)
        if item.get("type") in LANDMARK_TYPES
    ]


def _landmarks_within_limits(runtime_data: dict[str, Any]) -> bool:
    count = len(_landmarks(runtime_data))
    return MIN_LANDMARKS <= count <= MAX_LANDMARKS


def _landmarks_min_distance(runtime_data: dict[str, Any]) -> bool:
    landmarks = _landmarks(runtime_data)
    for index, first in enumerate(landmarks):
        first_points = _runtime_object_points(first)
        if not first_points:
            return False
        for second in landmarks[index + 1 :]:
            second_points = _runtime_object_points(second)
            if not second_points:
                return False
            if _minimum_point_distance(first_points, second_points) < LANDMARK_MIN_DISTANCE_TILES:
                return False
    return True


def _minimum_point_distance(
    first_points: list[tuple[int, int]],
    second_points: list[tuple[int, int]],
) -> int:
    return min(
        abs(first[0] - second[0]) + abs(first[1] - second[1])
        for first in first_points
        for second in second_points
    )


def _trenches(runtime_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in _runtime_objects(runtime_data)
        if item.get("type") == "trench"
    ]


def _trench_cells_have_negative_elevation(runtime_data: dict[str, Any]) -> bool:
    elevation_by_point = _elevation_level_by_point(runtime_data)
    for trench in _trenches(runtime_data):
        points = _runtime_object_points(trench)
        if not points:
            return False
        for point in points:
            if elevation_by_point.get(point) != TRENCH_ELEVATION_LEVEL:
                return False
    return True


def _elevation_cells_match_trench_footprints(runtime_data: dict[str, Any]) -> bool:
    negative_object_points: set[tuple[int, int]] = set()
    for item in _runtime_objects(runtime_data):
        if item.get("type") not in {"trench", "pit"} | BUNKER_TYPES:
            continue
        points = _runtime_object_points(item)
        if not points:
            return False
        negative_object_points.update(points)
    negative_elevation_points = {
        point
        for point, level in _elevation_level_by_point(runtime_data).items()
        if level == TRENCH_ELEVATION_LEVEL
    }
    return negative_object_points == negative_elevation_points




def _trench_shapes_valid(runtime_data: dict[str, Any]) -> bool:
    valid_shapes = {"line", "l_shape"}
    for trench in _trenches(runtime_data):
        if trench.get("shape", "line") not in valid_shapes:
            return False
    return True


def _trench_footprints_connected(runtime_data: dict[str, Any]) -> bool:
    for trench in _trenches(runtime_data):
        points = set(_runtime_object_points(trench))
        if not points:
            return False
        pending = {next(iter(points))}
        visited: set[tuple[int, int]] = set()
        while pending:
            point = pending.pop()
            if point in visited:
                continue
            visited.add(point)
            x, y = point
            neighbors = {
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            }
            pending.update(neighbors & points - visited)
        if visited != points:
            return False
    return True


def _l_shaped_trenches_have_corner(runtime_data: dict[str, Any]) -> bool:
    for trench in _trenches(runtime_data):
        if trench.get("shape") != "l_shape":
            continue
        points = set(_runtime_object_points(trench))
        if len(points) < 3:
            return False
        xs = {x for x, _ in points}
        ys = {y for _, y in points}
        if len(xs) < 2 or len(ys) < 2:
            return False
        if not any(_orthogonal_neighbor_count(point, points) >= 2 for point in points):
            return False
    return True


def _orthogonal_neighbor_count(
    point: tuple[int, int],
    points: set[tuple[int, int]],
) -> int:
    x, y = point
    return sum(
        neighbor in points
        for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
    )


def _elevation_level_by_point(runtime_data: dict[str, Any]) -> dict[tuple[int, int], int]:
    levels: dict[tuple[int, int], int] = {}
    for cell in _elevation_cells(runtime_data):
        point = _point_from_xy(cell)
        if point is None:
            continue
        try:
            levels[point] = int(cell.get("level"))
        except (TypeError, ValueError):
            continue
    return levels


def _runtime_object_type_count_within_limits(
    runtime_data: dict[str, Any],
    *,
    object_type: str,
    min_count: int,
    max_count: int,
) -> bool:
    count = sum(
        1
        for item in _runtime_objects(runtime_data)
        if item.get("type") == object_type
    )
    return min_count <= count <= max_count


def _interest_points_do_not_overlap_cover(runtime_data: dict[str, Any]) -> bool:
    cover_points: set[tuple[int, int]] = set()
    interest_points: set[tuple[int, int]] = set()
    for item in _runtime_objects(runtime_data):
        points = _runtime_object_points(item)
        if not points:
            return False
        target = interest_points if item.get("type") in INTEREST_POINT_TYPES else cover_points
        target.update(points)
    return interest_points.isdisjoint(cover_points)


def _runtime_objects_have_unique_ids(runtime_data: dict[str, Any]) -> bool:
    ids: list[str] = []
    for item in _runtime_objects(runtime_data):
        object_id = item.get("id")
        if not isinstance(object_id, str) or not object_id:
            return False
        ids.append(object_id)
    return len(ids) == len(set(ids))


def _runtime_objects_inside_map(
    runtime_data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for item in _runtime_objects(runtime_data):
        points = _runtime_object_points(item)
        if not points:
            return False
        for point in points:
            if not _point_in_bounds(point, width=width, height=height):
                return False
    return True


def _runtime_objects_have_valid_types(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        if item.get("type") not in RUNTIME_OBJECT_TYPE_NAMES:
            return False
    return True


def _runtime_objects_have_valid_cover(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        if item.get("cover_type") not in COVER_TYPES:
            return False
    return True


def _runtime_objects_have_valid_heights(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        try:
            height = int(item.get("height"))
        except (TypeError, ValueError):
            return False
        if not MIN_OBJECT_HEIGHT <= height <= MAX_OBJECT_HEIGHT:
            return False
    return True


def _runtime_objects_have_valid_elevation(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        try:
            elevation = int(item.get("elevation"))
        except (TypeError, ValueError):
            return False
        if not MIN_ELEVATION_LEVEL <= elevation <= MAX_ELEVATION_LEVEL:
            return False
    return True



def _runtime_objects_have_collision_profiles(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        profile = item.get("collision_profile")
        if not isinstance(profile, dict):
            return False
        if profile.get("movement") not in COLLISION_MOVEMENT_VALUES:
            return False
        if profile.get("projectiles") not in COLLISION_PROJECTILE_VALUES:
            return False
        if profile.get("vision") not in COLLISION_VISION_VALUES:
            return False
    return True


def _runtime_objects_have_combat_properties(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        properties = item.get("combat_properties")
        if not isinstance(properties, dict):
            return False
        if not isinstance(properties.get("explosive"), bool):
            return False
        if not isinstance(properties.get("loot"), bool):
            return False
        for property_name in ("cover_value", "concealment_value"):
            if not _combat_property_value_in_range(properties.get(property_name)):
                return False
    return True


def _combat_property_values_in_range(
    runtime_data: dict[str, Any],
    *,
    property_name: str,
) -> bool:
    for item in _runtime_objects(runtime_data):
        properties = item.get("combat_properties")
        if not isinstance(properties, dict):
            return False
        if not _combat_property_value_in_range(properties.get(property_name)):
            return False
    return True


def _combat_property_value_in_range(value: Any) -> bool:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return False
    return COMBAT_PROPERTY_VALUE_MIN <= normalized <= COMBAT_PROPERTY_VALUE_MAX


def _trench_objects_have_stance_hints(runtime_data: dict[str, Any]) -> bool:
    for trench in _trenches(runtime_data):
        hints = trench.get("stance_hints")
        if not isinstance(hints, dict):
            return False
        if hints.get("standing") != "exposed":
            return False
        if hints.get("crouching") != "protected_from_flat_fire":
            return False
    return True


def _explosive_objects_tagged(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        properties = item.get("combat_properties")
        if not isinstance(properties, dict) or properties.get("explosive") is not True:
            continue
        tags = item.get("tags")
        if not isinstance(tags, list):
            return False
        normalized_tags = {str(tag) for tag in tags}
        if "explosive" not in normalized_tags and "explosive_candidate" not in normalized_tags:
            return False
    return True


def _loot_objects_tagged(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        properties = item.get("combat_properties")
        if not isinstance(properties, dict) or properties.get("loot") is not True:
            continue
        tags = item.get("tags")
        if not isinstance(tags, list) or "loot" not in {str(tag) for tag in tags}:
            return False
    return True

def _runtime_objects_have_footprints(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        points = _runtime_object_points(item)
        if not points:
            return False
        footprint = item.get("footprint")
        if not isinstance(footprint, list):
            return False
    return True


def _runtime_objects_have_collision_footprints(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        value = item.get("collision_footprint")
        if not isinstance(value, list):
            return False
        if any(_point(point) is None for point in value):
            return False
    return True


def _runtime_objects_have_visual_bounds(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        bounds = item.get("visual_bounds")
        if not isinstance(bounds, dict):
            return False
        try:
            width = int(bounds.get("width"))
            height = int(bounds.get("height"))
            int(bounds.get("x"))
            int(bounds.get("y"))
        except (TypeError, ValueError):
            return False
        if width <= 0 or height <= 0:
            return False
    return True


def _bunker_objects_have_firing_ports(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        if item.get("type") not in BUNKER_TYPES:
            continue
        ports = item.get("firing_ports")
        if not isinstance(ports, list) or len(ports) != 2:
            return False
        for port in ports:
            if not isinstance(port, dict):
                return False
            if port.get("side") not in {"north", "south", "east", "west"}:
                return False
            positions = port.get("positions")
            if not isinstance(positions, list) or not positions:
                return False
            if any(_point(position) is None for position in positions):
                return False
            try:
                int(port.get("elevation"))
            except (TypeError, ValueError):
                return False
    return True


def _runtime_objects_have_pivots(runtime_data: dict[str, Any]) -> bool:
    for item in _runtime_objects(runtime_data):
        pivot = item.get("pivot")
        if not isinstance(pivot, dict):
            return False
        try:
            int(pivot.get("x"))
            int(pivot.get("y"))
        except (TypeError, ValueError):
            return False
        if not isinstance(pivot.get("space"), str):
            return False
    return True


def _runtime_object_collision_footprints_inside_map(
    runtime_data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for item in _runtime_objects(runtime_data):
        for point in _runtime_object_collision_points(item):
            if not _point_in_bounds(point, width=width, height=height):
                return False
    return True



def _runtime_objects_do_not_overlap_start_goal(
    runtime_data: dict[str, Any],
    tile_grid: list[str],
) -> bool:
    protected = _protected_tile_positions(tile_grid)
    if not protected:
        return True
    for item in _runtime_objects(runtime_data):
        if any(point in protected for point in _runtime_object_points(item)):
            return False
    return True


def _runtime_objects_do_not_overlap(runtime_data: dict[str, Any]) -> bool:
    occupied: set[tuple[int, int]] = set()
    for item in _runtime_objects(runtime_data):
        points = _runtime_object_points(item)
        if not points:
            return False
        for point in points:
            if point in occupied:
                return False
            occupied.add(point)
    return True


def _runtime_objects_avoid_blocked_tiles(
    runtime_data: dict[str, Any],
    tile_grid: list[str],
) -> bool:
    if not tile_grid:
        return False
    for item in _runtime_objects(runtime_data):
        for point in _runtime_object_points(item):
            x, y = point
            if y < 0 or y >= len(tile_grid) or x < 0 or x >= len(tile_grid[y]):
                return False
            if tile_grid[y][x] not in PASSABLE_OBJECT_TILES:
                return False
    return True


def _elevation_cells_inside_map(
    runtime_data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for cell in _elevation_cells(runtime_data):
        point = _point_from_xy(cell)
        if point is None or not _point_in_bounds(point, width=width, height=height):
            return False
    return True


def _elevation_levels_valid(runtime_data: dict[str, Any]) -> bool:
    elevation = runtime_data.get("elevation", {})
    if not isinstance(elevation, dict):
        return False
    try:
        default_level = int(elevation.get("default", 0))
    except (TypeError, ValueError):
        return False
    if not MIN_ELEVATION_LEVEL <= default_level <= MAX_ELEVATION_LEVEL:
        return False
    for cell in _elevation_cells(runtime_data):
        try:
            level = int(cell.get("level"))
        except (TypeError, ValueError):
            return False
        if not MIN_ELEVATION_LEVEL <= level <= MAX_ELEVATION_LEVEL:
            return False
    return True


def _elevation_cells(runtime_data: dict[str, Any]) -> list[dict[str, Any]]:
    elevation = runtime_data.get("elevation", {})
    if not isinstance(elevation, dict):
        return []
    return _dict_list(elevation.get("cells"))


def _runtime_object_points(item: dict[str, Any]) -> list[tuple[int, int]]:
    footprint = item.get("footprint")
    if isinstance(footprint, list):
        points = [_point(point) for point in footprint]
        return [point for point in points if point is not None]
    point = _point(item.get("position"))
    if point is not None:
        return [point]
    point = _point_from_xy(item)
    if point is not None:
        return [point]
    return []


def _runtime_object_collision_points(item: dict[str, Any]) -> list[tuple[int, int]]:
    collision_footprint = item.get("collision_footprint")
    if isinstance(collision_footprint, list):
        points = [_point(point) for point in collision_footprint]
        return [point for point in points if point is not None]
    return []


def _point_from_xy(item: dict[str, Any]) -> tuple[int, int] | None:
    try:
        return int(item["x"]), int(item["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _protected_tile_positions(tile_grid: list[str]) -> set[tuple[int, int]]:
    protected: set[tuple[int, int]] = set()
    for y, row in enumerate(tile_grid):
        for x, tile in enumerate(row):
            if tile in {"S", "G"}:
                protected.add((x, y))
    return protected



def _places(runtime_data: dict[str, Any]) -> list[dict[str, Any]]:
    value = runtime_data.get("places")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _places_have_unique_ids(runtime_data: dict[str, Any]) -> bool:
    ids: list[str] = []
    for place in _places(runtime_data):
        place_id = place.get("id")
        if not isinstance(place_id, str) or not place_id:
            return False
        ids.append(place_id)
    return len(ids) == len(set(ids))


def _places_have_valid_types(runtime_data: dict[str, Any]) -> bool:
    for place in _places(runtime_data):
        if place.get("type") not in PLACE_TYPE_NAMES:
            return False
    return True


def _places_have_valid_object_refs(runtime_data: dict[str, Any]) -> bool:
    object_ids = {
        str(item.get("id"))
        for item in _runtime_objects(runtime_data)
        if isinstance(item.get("id"), str) and item.get("id")
    }
    for place in _places(runtime_data):
        refs = place.get("object_ids")
        if not isinstance(refs, list) or not refs:
            return False
        normalized_refs: list[str] = []
        for ref in refs:
            if not isinstance(ref, str) or ref not in object_ids:
                return False
            normalized_refs.append(ref)
        anchor_ref = place.get("anchor_object_id")
        if not isinstance(anchor_ref, str) or anchor_ref not in normalized_refs:
            return False
    return True




def _places_have_v2_metadata(runtime_data: dict[str, Any]) -> bool:
    for place in _places(runtime_data):
        if not isinstance(place.get("story_role"), str) or not place.get("story_role"):
            return False
        if not isinstance(place.get("encounter_type"), str) or not place.get("encounter_type"):
            return False
        if not _normalized_float(place.get("danger_level")):
            return False
        if not _normalized_float(place.get("loot_level")):
            return False
        if not isinstance(place.get("biome_tags"), list):
            return False
    return True


def _places_have_bounds(runtime_data: dict[str, Any]) -> bool:
    for place in _places(runtime_data):
        bounds = place.get("bounds")
        if not isinstance(bounds, dict):
            return False
        values = []
        for key in ("min_x", "min_y", "max_x", "max_y"):
            value = bounds.get(key)
            if not isinstance(value, int):
                return False
            values.append(value)
        min_x, min_y, max_x, max_y = values
        if min_x > max_x or min_y > max_y:
            return False
    return True


def _places_have_entrances(runtime_data: dict[str, Any]) -> bool:
    for place in _places(runtime_data):
        entrances = place.get("entrances")
        if not isinstance(entrances, list) or not entrances:
            return False
        for entrance in entrances:
            if not isinstance(entrance, dict):
                return False
            if not isinstance(entrance.get("side"), str):
                return False
            position = entrance.get("position")
            if not isinstance(position, dict) or _point_from_xy(position) is None:
                return False
    return True


def _places_have_connections(runtime_data: dict[str, Any]) -> bool:
    place_ids = {
        str(place.get("id"))
        for place in _places(runtime_data)
        if isinstance(place.get("id"), str)
    }
    for place in _places(runtime_data):
        connected = place.get("connected_places")
        if not isinstance(connected, list):
            return False
        for place_id in connected:
            if not isinstance(place_id, str) or place_id not in place_ids:
                return False
    return True


def _normalized_float(value: Any) -> bool:
    return isinstance(value, int | float) and 0.0 <= float(value) <= 1.0


def _places_inside_map(
    runtime_data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> bool:
    for place in _places(runtime_data):
        center = place.get("center")
        if not isinstance(center, dict):
            return False
        point = _point_from_xy(center)
        if point is None or not _point_in_bounds(point, width=width, height=height):
            return False
        try:
            radius = int(place.get("radius"))
        except (TypeError, ValueError):
            return False
        if radius <= 0:
            return False
    return True


def _places_counts_within_limits(runtime_data: dict[str, Any]) -> bool:
    place_count = len(_places(runtime_data))
    return MIN_PLACES <= place_count <= MAX_PLACES


def _places_min_distance(runtime_data: dict[str, Any]) -> bool:
    centers: list[tuple[int, int]] = []
    for place in _places(runtime_data):
        center = place.get("center")
        if not isinstance(center, dict):
            return False
        point = _point_from_xy(center)
        if point is None:
            return False
        centers.append(point)
    for index, first in enumerate(centers):
        for second in centers[index + 1:]:
            if _manhattan(first, second) < MIN_PLACE_DISTANCE_TILES:
                return False
    return True


def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])

def _count_points_near_edge(
    items: Any,
    *,
    width: int,
    height: int,
) -> int:
    if not isinstance(items, list) or width <= 0 or height <= 0:
        return 0
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        point = _point(item.get("position"))
        if point is None:
            continue
        if _is_near_edge(point, width=width, height=height):
            count += 1
    return count


def _is_near_edge(point: tuple[int, int], *, width: int, height: int) -> bool:
    x, y = point
    margin = EDGE_WARNING_MARGIN_TILES
    return (
        x <= margin
        or y <= margin
        or x >= width - 1 - margin
        or y >= height - 1 - margin
    )


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def _point_in_bounds(point: tuple[int, int], *, width: int, height: int) -> bool:
    x, y = point
    return 0 <= x < width and 0 <= y < height


def _count_existing_outputs(outputs: OutputPaths) -> int:
    candidates = [
        outputs.generated_map,
        outputs.raw_tactical_map,
        outputs.tactical_map,
        outputs.tactical_map_debug,
        outputs.metrics,
        outputs.engine_config,
        outputs.manifest,
        outputs.validation_report,
        outputs.layer_base_map,
        outputs.layer_combat_zones,
        outputs.layer_cover_points,
        outputs.layer_choke_points,
        outputs.layer_flank_routes,
        outputs.layer_enemy_spawn_zones,
        outputs.layer_fallback_positions,
        outputs.layer_runtime_objects,
        outputs.layer_all_debug,
        outputs.map_package_map,
        outputs.map_package_markers,
        outputs.map_package_runtime_grids,
        outputs.map_package_world_graph,
        outputs.map_package_routes,
        outputs.map_package_tile_grid,
        outputs.map_package_terrain,
        outputs.map_package_movement_costs,
        outputs.map_package_collision,
        outputs.map_package_elevation,
        outputs.map_package_start_goal,
        outputs.map_package_combat_zones,
        outputs.map_package_cover_points,
        outputs.map_package_choke_points,
        outputs.map_package_flank_routes,
        outputs.map_package_enemy_spawn_zones,
        outputs.map_package_fallback_positions,
        outputs.map_package_runtime_objects,
        outputs.map_package_places,
        outputs.map_package_tile_types,
        outputs.map_package_object_types,
        outputs.map_package_render_profile,
        outputs.map_package_tile_render_hints,
        outputs.map_package_object_render_hints,
    ]
    return sum(path.exists() for path in candidates)
