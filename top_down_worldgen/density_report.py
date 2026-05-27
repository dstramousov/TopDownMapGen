from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .utils.json_io import read_json, write_json

WORLD_TARGETS: dict[str, dict[str, float]] = {
    "forest_percent": {"min": 35.0, "max": 55.0, "critical_max": 75.0},
    "road_percent": {"min": 3.0, "max": 8.0, "critical_max": 14.0},
    "swamp_percent": {"min": 2.0, "max": 7.0, "critical_max": 14.0},
    "ruins_percent": {"min": 2.0, "max": 8.0, "critical_max": 14.0},
    "open_ground_percent": {"min": 30.0, "max": 55.0, "critical_max": 75.0},
    "blocked_percent": {"min": 35.0, "max": 60.0, "critical_max": 80.0},
    "slow_percent": {"min": 4.0, "max": 14.0, "critical_max": 25.0},
    "lowland_percent": {"min": 0.1, "max": 3.0, "critical_max": 8.0},
    "raised_percent": {"min": 0.1, "max": 2.0, "critical_max": 8.0},
    "high_percent": {"min": 0.05, "max": 1.0, "critical_max": 4.0},
    "tower_percent": {"min": 0.01, "max": 0.2, "critical_max": 1.0},
    "places_total": {"min": 4.0, "max": 35.0, "critical_max": 60.0},
    "transitions_total": {"min": 20.0, "max": 300.0, "critical_max": 500.0},
}

TERRAIN_CATEGORIES: dict[str, set[str]] = {
    "forest": {"tree_blocker", "bush_slow_concealment", "forest", "bush"},
    "road": {"old_overgrown_road", "road", "path", "dirt_road", "overgrown_road"},
    "swamp": {"water_slow", "swamp"},
    "ruins": {"ruin_wall_blocker", "ruin_floor", "ruin", "ruins"},
    "open_ground": {"grass", "cracked_ground", "flower_decor", "mushroom_decor", "start", "goal", "dirt"},
}


class WorldDensityReporter:
    """Build world package density diagnostics."""

    def build_report(self, output_dir: Path) -> dict[str, Any]:
        """Build a world density report from a generated output directory.

        Args:
            output_dir: Generation output directory.

        Returns:
            World density report.
        """
        package_dir = output_dir / "map_package"
        index = read_json(package_dir / "map.json")
        terrain = read_json(package_dir / "layers" / "terrain.json")
        runtime_grids = read_json(package_dir / "runtime_grids.json")
        places = _read_optional_json(package_dir / "objects" / "places.json")
        routes = _read_optional_json(package_dir / "routes.json")
        markers = _read_optional_json(package_dir / "markers.json")
        runtime_objects = _read_optional_json(package_dir / "objects" / "runtime_objects.json")
        elevation_transitions = _read_optional_json(package_dir / "elevation_transitions.json")

        rows = _terrain_rows(terrain)
        height = len(rows)
        width = len(rows[0]) if rows else _index_dimension(index, "width_tiles")
        area_tiles = max(width * height, 0)
        terrain_counts = Counter(cell for row in rows for cell in row)
        category_counts = {
            category: sum(terrain_counts[terrain_type] for terrain_type in terrain_types)
            for category, terrain_types in TERRAIN_CATEGORIES.items()
        }

        collision = _collision_summary(runtime_grids, area_tiles)
        movement = _movement_summary(runtime_grids, area_tiles)
        elevation = _elevation_summary(runtime_grids, area_tiles)
        transition_summary = _transition_summary(elevation_transitions)
        places_total = len(_items(places))

        return {
            "schema_version": "world-density-report-v1",
            "kind": "world_density_report",
            "map": {
                "width": width,
                "height": height,
                "area_tiles": area_tiles,
                "seed": index.get("resolved_seed"),
                "profile": index.get("profile"),
            },
            "terrain": {
                category: {
                    "tiles": count,
                    "percent": _percent(count, area_tiles),
                    **_target_status(_percent(count, area_tiles), WORLD_TARGETS[f"{category}_percent"]),
                }
                for category, count in category_counts.items()
            },
            "terrain_counts": dict(sorted(terrain_counts.items())),
            "collision": collision,
            "movement": movement,
            "elevation": elevation,
            "elevation_transitions": transition_summary,
            "world_structure": {
                "places": {"total": places_total, **_target_status(float(places_total), WORLD_TARGETS["places_total"])},
                "routes": {"total": len(_items(routes)), "status": "ok"},
                "markers": {"total": len(_items(markers)), "status": "ok"},
                "runtime_objects": {"total": len(_items(runtime_objects)), "status": "ok"},
            },
            "quality": {
                "status": _overall_status(
                    [
                        item.get("status", "ok")
                        for section in (collision, movement, elevation, transition_summary)
                        for item in _quality_items(section)
                    ]
                    + [
                        item.get("status", "ok")
                        for item in [*_dict_values_safe({k: v for k, v in category_counts.items()})]
                    ],
                ),
            },
        }


def write_world_density_report(report: dict[str, Any], path: Path) -> None:
    """Write a world density report.

    Args:
        report: Report payload.
        path: Output path.
    """
    write_json(report, path)


def format_world_density_summary(report: dict[str, Any]) -> list[str]:
    """Format compact world density report lines.

    Args:
        report: World density report.

    Returns:
        Lines suitable for console output.
    """
    map_info = report.get("map", {})
    terrain = report.get("terrain", {})
    collision = report.get("collision", {})
    movement = report.get("movement", {})
    elevation = report.get("elevation", {})
    transitions = report.get("elevation_transitions", {})
    structure = report.get("world_structure", {})
    lines = [
        "World density:",
        f"  map: {map_info.get('width', 0)} x {map_info.get('height', 0)} = {map_info.get('area_tiles', 0)} tiles",
        "  terrain:",
    ]
    for key in ("forest", "road", "swamp", "ruins", "open_ground"):
        lines.append(_format_percent_line(key, terrain.get(key, {})))
    lines.extend(
        [
            "  collision:",
            _format_percent_line("blocked", collision.get("blocked", {})),
            "  movement:",
            _format_percent_line("slow", movement.get("slow", {})),
            "  elevation:",
            _format_percent_line("lowlands -1", elevation.get("lowlands", {})),
            _format_percent_line("raised 1+", elevation.get("raised", {})),
            _format_percent_line("high 2+", elevation.get("high", {})),
            _format_percent_line("towers 3+", elevation.get("towers", {})),
            "  elevation transitions:",
            _format_count_line("total", transitions.get("total", {})),
            "  world structure:",
            _format_count_line("places", _nested(structure, "places")),
            _format_count_line("routes", _nested(structure, "routes"), include_target=False),
            _format_count_line("markers", _nested(structure, "markers"), include_target=False),
            _format_count_line("runtime objects", _nested(structure, "runtime_objects"), include_target=False),
        ],
    )
    return lines


def _collision_summary(runtime_grids: dict[str, Any], area_tiles: int) -> dict[str, Any]:
    rows = _grid_rows(runtime_grids, "collision_grid")
    blocked = 0
    walkable = 0
    for row in rows:
        values = row if isinstance(row, list) else list(str(row))
        for value in values:
            if str(value) == "1":
                blocked += 1
            else:
                walkable += 1
    blocked_percent = _percent(blocked, area_tiles)
    return {
        "blocked": {"tiles": blocked, "percent": blocked_percent, **_target_status(blocked_percent, WORLD_TARGETS["blocked_percent"])},
        "walkable": {"tiles": walkable, "percent": _percent(walkable, area_tiles)},
    }


def _movement_summary(runtime_grids: dict[str, Any], area_tiles: int) -> dict[str, Any]:
    rows = _grid_rows(runtime_grids, "movement_grid")
    normal = 0
    slow = 0
    blocked = 0
    for row in rows:
        if not isinstance(row, list):
            continue
        for value in row:
            if value is None:
                blocked += 1
            elif isinstance(value, int | float) and value > 1:
                slow += 1
            else:
                normal += 1
    slow_percent = _percent(slow, area_tiles)
    return {
        "normal": {"tiles": normal, "percent": _percent(normal, area_tiles)},
        "slow": {"tiles": slow, "percent": slow_percent, **_target_status(slow_percent, WORLD_TARGETS["slow_percent"])},
        "blocked": {"tiles": blocked, "percent": _percent(blocked, area_tiles)},
    }


def _elevation_summary(runtime_grids: dict[str, Any], area_tiles: int) -> dict[str, Any]:
    rows = _grid_rows(runtime_grids, "height_grid")
    counts: Counter[int] = Counter()
    for row in rows:
        if not isinstance(row, list):
            continue
        for value in row:
            if isinstance(value, int):
                counts[value] += 1
    lowlands = sum(count for level, count in counts.items() if level < 0)
    raised = sum(count for level, count in counts.items() if level >= 1)
    high = sum(count for level, count in counts.items() if level >= 2)
    towers = sum(count for level, count in counts.items() if level >= 3)
    landmarks = counts.get(4, 0)
    return {
        "levels": {str(level): count for level, count in sorted(counts.items())},
        "lowlands": _targeted_tiles(lowlands, area_tiles, WORLD_TARGETS["lowland_percent"]),
        "ground": {"tiles": counts.get(0, 0), "percent": _percent(counts.get(0, 0), area_tiles)},
        "raised": _targeted_tiles(raised, area_tiles, WORLD_TARGETS["raised_percent"]),
        "high": _targeted_tiles(high, area_tiles, WORLD_TARGETS["high_percent"]),
        "towers": _targeted_tiles(towers, area_tiles, WORLD_TARGETS["tower_percent"]),
        "landmarks": {"tiles": landmarks, "percent": _percent(landmarks, area_tiles)},
    }


def _transition_summary(elevation_transitions: dict[str, Any]) -> dict[str, Any]:
    summary = elevation_transitions.get("summary") if isinstance(elevation_transitions, dict) else None
    if not isinstance(summary, dict):
        summary = {}
    total = _int_value(summary.get("total"), len(_items(elevation_transitions)))
    return {
        "total": {"count": total, **_target_status(float(total), WORLD_TARGETS["transitions_total"])},
        "by_type": summary.get("by_type", {}),
        "by_connector": summary.get("by_connector", {}),
        "movement_allowed": summary.get("movement_allowed", 0),
        "movement_blocked": summary.get("movement_blocked", 0),
    }


def _grid_rows(runtime_grids: dict[str, Any], grid_name: str) -> list[Any]:
    grids = runtime_grids.get("grids")
    if not isinstance(grids, dict):
        return []
    grid = grids.get(grid_name)
    if not isinstance(grid, dict):
        return []
    rows = grid.get("rows")
    return rows if isinstance(rows, list) else []


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, list)]


def _read_optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("items")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _index_dimension(index: dict[str, Any], key: str) -> int:
    dimensions = index.get("dimensions")
    if isinstance(dimensions, dict):
        return _int_value(dimensions.get(key), 0)
    return 0


def _targeted_tiles(count: int, area_tiles: int, target: dict[str, float]) -> dict[str, Any]:
    percent = _percent(count, area_tiles)
    return {"tiles": count, "percent": percent, **_target_status(percent, target)}


def _target_status(value: float, target: dict[str, float]) -> dict[str, Any]:
    minimum = target["min"]
    maximum = target["max"]
    critical_max = target["critical_max"]
    if value < minimum:
        status = "low"
    elif value <= maximum:
        status = "ok"
    elif value >= critical_max:
        status = "critical"
    else:
        status = "high"
    return {"target_min": minimum, "target_max": maximum, "critical_max": critical_max, "status": status}


def _format_percent_line(label: str, data: Any) -> str:
    if not isinstance(data, dict):
        data = {}
    tiles = _int_value(data.get("tiles"), 0)
    percent = _float_value(data.get("percent"), 0.0)
    status = str(data.get("status", "unknown"))
    target_min = _float_value(data.get("target_min"), 0.0)
    target_max = _float_value(data.get("target_max"), 0.0)
    return f"    {label:<13} {tiles:6d} tiles = {percent:5.1f}% [{status}, target {target_min:g}-{target_max:g}]"


def _format_count_line(label: str, data: Any, *, include_target: bool = True) -> str:
    if not isinstance(data, dict):
        data = {}
    count = _int_value(data.get("count"), _int_value(data.get("total"), 0))
    status = str(data.get("status", "ok"))
    if not include_target or "target_min" not in data:
        return f"    {label:<15} {count:6d} [{status}]"
    target_min = _float_value(data.get("target_min"), 0.0)
    target_max = _float_value(data.get("target_max"), 0.0)
    return f"    {label:<15} {count:6d} [{status}, target {target_min:g}-{target_max:g}]"


def _nested(value: Any, key: str) -> dict[str, Any]:
    return value.get(key, {}) if isinstance(value, dict) else {}


def _quality_items(section: Any) -> list[dict[str, Any]]:
    if not isinstance(section, dict):
        return []
    return [value for value in section.values() if isinstance(value, dict) and "status" in value]


def _dict_values_safe(value: dict[str, int]) -> list[dict[str, Any]]:
    return []


def _overall_status(statuses: list[str]) -> str:
    if "critical" in statuses:
        return "critical"
    if "high" in statuses or "low" in statuses:
        return "warning"
    return "ok"


def _percent(count: int, total: int) -> float:
    return round((count / total) * 100.0, 2) if total > 0 else 0.0


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default


def _float_value(value: Any, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default
