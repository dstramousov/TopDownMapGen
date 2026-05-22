from __future__ import annotations

from collections import Counter
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
        "places_inside_map": _places_inside_map(
            runtime_data,
            width=width,
            height=height,
        ),
        "places_counts_within_limits": _places_counts_within_limits(runtime_data),
        "places_min_distance": _places_min_distance(runtime_data),
    }
    errors = [name for name, passed in checks.items() if not passed]
    warnings = build_validation_warnings(
        runtime_data=runtime_data,
        width=width,
        height=height,
    )
    return {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "status": "passed" if not errors else "failed",
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
        if item.get("type") not in {"trench", "pit"}:
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
    ]
    return sum(path.exists() for path in candidates)
