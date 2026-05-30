from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_json_object, write_json_object
from .models import VisualProfile, WorldPackage

DEFAULT_VISUAL_DENSITY_RULES: dict[str, dict[str, float]] = {
    "visual_objects_per_1000_tiles": {"min": 40.0, "max": 60.0, "critical_max": 100.0},
    "decorations_per_1000_tiles": {"min": 35.0, "max": 55.0, "critical_max": 90.0},
    "place_treatment_objects_per_place": {"min": 1.0, "max": 4.0, "critical_max": 8.0},
}


class VisualDensityReporter:
    """Build visual density diagnostics for a generated visual map."""

    def build_report(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        visual_layers: dict[str, Any],
        visual_objects: dict[str, Any],
        visual_debug: dict[str, Any],
        decoration_result: dict[str, Any],
        place_treatment_result: dict[str, Any],
        elevation_visual_result: dict[str, Any] | None = None,
        boundary_visual_result: dict[str, Any] | None = None,
        forest_overlay_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a JSON-serializable visual density report.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            visual_layers: Generated visual layers.
            visual_objects: Generated visual objects.
            visual_debug: Terrain/autotile debug data.
            decoration_result: Decoration mapper result.
            place_treatment_result: Place treatment mapper result.
            elevation_visual_result: Optional elevation visual mapper result.
            boundary_visual_result: Optional boundary visual mapper result.
            forest_overlay_result: Optional forest overlay mapper result.

        Returns:
            Visual density report.
        """
        width = _int_value(visual_layers.get("width"), _int_value(world.index.get("width"), 0))
        height = _int_value(visual_layers.get("height"), _int_value(world.index.get("height"), 0))
        area_tiles = max(width * height, 0)
        rules = _load_density_rules(profile.root_dir)
        items = _items(visual_objects)
        total = len(items)
        runtime_total = _summary_int(visual_objects, "runtime_total")
        decoration_total = _summary_int(visual_objects, "decoration_total")
        place_total = _summary_int(visual_objects, "place_treatment_total")
        elevation_visual_total = _summary_int(visual_objects, "elevation_visual_total")
        boundary_visual_total = _summary_int(visual_objects, "boundary_visual_total")
        forest_overlay_total = _summary_int(visual_objects, "forest_overlay_total")
        places_total = len(_items(world.places))

        by_source = {
            "runtime": runtime_total,
            "decorations": decoration_total,
            "place_treatment": place_total,
            "elevation_visual": elevation_visual_total,
            "boundary_visual": boundary_visual_total,
            "forest_overlay": forest_overlay_total,
        }
        by_category = _count_categories(items)
        top_sprites = _top_counts(_count_by(items, "sprite_id"), limit=10)
        visual_density = _per_1000(total, area_tiles)
        decoration_density = _per_1000(decoration_total, area_tiles)
        place_density = _safe_ratio(place_total, places_total)

        autotile_summary = visual_debug.get("autotile_summary", {})
        if not isinstance(autotile_summary, dict):
            autotile_summary = {}
        fallbacks = autotile_summary.get("fallbacks", {})
        fallback_total = sum(value for value in fallbacks.values() if isinstance(value, int)) if isinstance(fallbacks, dict) else 0
        unmapped = visual_debug.get("unmapped_terrain", {})
        unmapped_total = _int_value(unmapped.get("total_cells") if isinstance(unmapped, dict) else None, 0)

        return {
            "schema_version": "visual-density-report-v1",
            "kind": "visual_density_report",
            "profile": profile.profile.get("id", "unknown"),
            "map": {"width": width, "height": height, "area_tiles": area_tiles},
            "visual_objects": {
                "total": total,
                "per_1000_tiles": visual_density,
                **_target_status(visual_density, rules["visual_objects_per_1000_tiles"]),
            },
            "by_source": by_source,
            "decorations": {
                "total": decoration_total,
                "per_1000_tiles": decoration_density,
                **_target_status(decoration_density, rules["decorations_per_1000_tiles"]),
            },
            "place_treatment": {
                "places_total": places_total,
                "objects_total": place_total,
                "objects_per_place": place_density,
                **_target_status(place_density, rules["place_treatment_objects_per_place"]),
            },
            "by_category": dict(sorted(by_category.items())),
            "top_sprites": top_sprites,
            "autotiling": {
                "groups": autotile_summary.get("groups", {}),
                "fallback_total": fallback_total,
                "status": "ok" if fallback_total == 0 else "has_fallbacks",
            },
            "unmapped_terrain": {
                "total": unmapped_total,
                "status": "ok" if unmapped_total == 0 else "has_unmapped_terrain",
            },
            "elevation_visual": _elevation_visual_summary(world, elevation_visual_result),
            "boundary_visual": _boundary_visual_summary(boundary_visual_result),
            "forest_overlay": _forest_overlay_summary(forest_overlay_result),
            "source_reports": {
                "decoration_total": _report_total(decoration_result),
                "place_treatment_total": _report_total(place_treatment_result),
                "boundary_visual_total": _report_total(boundary_visual_result or {}),
            },
            "quality": {
                "status": _overall_status(
                    [
                        _target_status(visual_density, rules["visual_objects_per_1000_tiles"])["status"],
                        _target_status(decoration_density, rules["decorations_per_1000_tiles"])["status"],
                        _target_status(place_density, rules["place_treatment_objects_per_place"])["status"],
                        "ok" if fallback_total == 0 else "high",
                        "ok" if unmapped_total == 0 else "high",
                    ],
                ),
            },
        }


def write_visual_density_report(report: dict[str, Any], path: Path) -> None:
    """Write a visual density report.

    Args:
        report: Report payload.
        path: Output path.
    """
    write_json_object(report, path)


def format_visual_density_summary(report: dict[str, Any]) -> list[str]:
    """Format compact visual density report lines for console output.

    Args:
        report: Visual density report.

    Returns:
        Lines suitable for logging or printing.
    """
    visual = report.get("visual_objects", {})
    decorations = report.get("decorations", {})
    place = report.get("place_treatment", {})
    by_source = report.get("by_source", {})
    by_category = report.get("by_category", {})
    top_sprites = report.get("top_sprites", [])
    autotiling = report.get("autotiling", {})
    unmapped = report.get("unmapped_terrain", {})
    elevation = report.get("elevation_visual", {})
    boundary = report.get("boundary_visual", {})

    lines = [
        "Visual density:",
        _format_density_line("objects", visual, "/ 1000 tiles"),
        _format_density_line("decorations", decorations, "/ 1000 tiles"),
        _format_density_line("place", place, "/ place", value_key="objects_per_place"),
        "",
        "By source:",
        "  " + _format_inline_counts(by_source),
        "",
        "By category:",
        "  " + _format_inline_counts(by_category),
        "",
        "Top sprites:",
    ]
    for item in top_sprites[:5]:
        if isinstance(item, dict):
            lines.append(f"  {item.get('id', 'unknown')}: {item.get('count', 0)}")
    lines.extend(
        [
            "",
            "Autotiling:",
            f"  fallbacks: {_int_value(autotiling.get('fallback_total'), 0)} [{autotiling.get('status', 'unknown')}]",
            f"  unmapped terrain: {_int_value(unmapped.get('total'), 0)} [{unmapped.get('status', 'unknown')}]",
            "",
            "Elevation visual:",
            f"  lowlands: {_int_value(elevation.get('lowlands'), 0)}, raised: {_int_value(elevation.get('raised'), 0)}, transitions: {_int_value(elevation.get('transitions'), 0)} [{elevation.get('status', 'unknown')}]",
            "",
            "Boundary visual:",
            f"  markers: {_int_value(boundary.get('total'), 0)} [{boundary.get('status', 'unknown')}]",
        ],
    )
    return lines




def _forest_overlay_summary(forest_overlay_result: dict[str, Any] | None = None) -> dict[str, Any]:
    report = forest_overlay_result.get("report") if isinstance(forest_overlay_result, dict) else None
    summary = report.get("summary") if isinstance(report, dict) else None
    if not isinstance(summary, dict):
        return {
            "total": 0,
            "by_kind": {},
            "by_edge": {},
            "failed_placements": 0,
            "sampled_markers": 0,
            "status": "missing_report",
        }
    failed = summary.get("failed_placements")
    failed_total = sum(value for value in failed.values() if isinstance(value, int)) if isinstance(failed, dict) else 0
    return {
        "total": _int_value(summary.get("total"), 0),
        "by_kind": summary.get("by_kind", {}),
        "by_edge": summary.get("by_edge", {}),
        "failed_placements": failed_total,
        "sampled_markers": _sum_int_mapping(summary.get("sampled_markers")),
        "status": "ok" if failed_total == 0 else "has_failed_placements",
    }

def _boundary_visual_summary(boundary_visual_result: dict[str, Any] | None = None) -> dict[str, Any]:
    report = boundary_visual_result.get("report") if isinstance(boundary_visual_result, dict) else None
    summary = report.get("summary") if isinstance(report, dict) else None
    if not isinstance(summary, dict):
        return {
            "total": 0,
            "by_boundary_type": {},
            "by_edge": {},
            "failed_placements": 0,
            "status": "missing_report",
        }
    failed = summary.get("failed_placements")
    failed_total = sum(value for value in failed.values() if isinstance(value, int)) if isinstance(failed, dict) else 0
    return {
        "total": _int_value(summary.get("total"), 0),
        "by_boundary_type": summary.get("by_boundary_type", {}),
        "by_edge": summary.get("by_edge", {}),
        "failed_placements": failed_total,
        "sampled_markers": _sum_int_mapping(summary.get("sampled_markers")),
        "status": "ok" if failed_total == 0 else "has_failed_placements",
    }


def _elevation_visual_summary(world: WorldPackage, elevation_visual_result: dict[str, Any] | None = None) -> dict[str, Any]:
    report = elevation_visual_result.get("report") if isinstance(elevation_visual_result, dict) else None
    summary = report.get("summary") if isinstance(report, dict) else None
    if isinstance(summary, dict):
        failed = summary.get("failed_placements")
        failed_total = sum(value for value in failed.values() if isinstance(value, int)) if isinstance(failed, dict) else 0
        lowland_markers = _int_value(summary.get("lowland_markers"), 0)
        raised_markers = (
            _int_value(summary.get("raised_markers"), 0)
            + _int_value(summary.get("platform_markers"), 0)
            + _int_value(summary.get("high_point_markers"), 0)
        )
        return {
            "lowlands": lowland_markers,
            "raised": raised_markers,
            "high": _int_value(summary.get("high_point_markers"), 0),
            "transitions": _int_value(summary.get("transition_markers"), 0),
            "landmarks": _int_value(summary.get("landmark_markers"), 0),
            "failed_placements": failed_total,
            "sampled_markers": _sum_int_mapping(summary.get("sampled_markers")),
            "status": "ok" if failed_total == 0 else "has_failed_placements",
        }

    rows = _runtime_grid_rows(world.runtime_grids, "height_grid")
    lowlands = 0
    raised = 0
    high = 0
    landmarks = 0
    for row in rows:
        if not isinstance(row, list):
            continue
        for value in row:
            if isinstance(value, int):
                if value < 0:
                    lowlands += 1
                if value >= 1:
                    raised += 1
                if value >= 2:
                    high += 1
                if value >= 4:
                    landmarks += 1
    transitions = world.elevation_model.get("transitions")
    transition_count = len(transitions) if isinstance(transitions, list) else 0
    if transition_count == 0:
        model_summary = world.elevation_model.get("summary")
        if isinstance(model_summary, dict):
            transition_count = _int_value(model_summary.get("total"), 0)
    return {
        "lowlands": lowlands,
        "raised": raised,
        "high": high,
        "transitions": transition_count,
        "landmarks": landmarks,
        "failed_placements": 0,
        "status": "ok",
    }


def _runtime_grid_rows(runtime_grids: dict[str, Any], grid_name: str) -> list[Any]:
    grids = runtime_grids.get("grids")
    if not isinstance(grids, dict):
        return []
    grid = grids.get(grid_name)
    if not isinstance(grid, dict):
        return []
    rows = grid.get("rows")
    return rows if isinstance(rows, list) else []

def _load_density_rules(profile_dir: Path) -> dict[str, dict[str, float]]:
    path = profile_dir / "visual_density_rules.json"
    if not path.exists():
        return DEFAULT_VISUAL_DENSITY_RULES
    data = read_json_object(path)
    result = dict(DEFAULT_VISUAL_DENSITY_RULES)
    for key, fallback in DEFAULT_VISUAL_DENSITY_RULES.items():
        raw = data.get(key)
        result[key] = _rule(raw, fallback) if isinstance(raw, dict) else fallback
    return result


def _rule(raw: dict[str, Any], fallback: dict[str, float]) -> dict[str, float]:
    return {
        "min": _float_value(raw.get("min"), fallback["min"]),
        "max": _float_value(raw.get("max"), fallback["max"]),
        "critical_max": _float_value(raw.get("critical_max"), fallback["critical_max"]),
    }


def _target_status(value: float, rule: dict[str, float]) -> dict[str, Any]:
    minimum = rule["min"]
    maximum = rule["max"]
    critical_max = rule["critical_max"]
    if value < minimum:
        status = "low"
    elif value <= maximum:
        status = "ok"
    elif value >= critical_max:
        status = "critical"
    else:
        status = "high"
    return {
        "target_min": minimum,
        "target_max": maximum,
        "critical_max": critical_max,
        "status": status,
    }


def _overall_status(statuses: list[str]) -> str:
    if "critical" in statuses:
        return "critical"
    if "high" in statuses:
        return "warning"
    if "low" in statuses:
        return "warning"
    return "ok"


def _count_categories(items: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        source_type = str(item.get("source_object_type", ""))
        rule_id = str(item.get("decoration_rule_id") or item.get("place_treatment_rule_id") or "")
        sprite_id = str(item.get("sprite_id", ""))
        tags = item.get("source_tags", [])
        tag_text = " ".join(str(tag) for tag in tags) if isinstance(tags, list) else ""
        haystack = f"{source_type} {rule_id} {sprite_id} {tag_text}"
        if source_type == "visual_forest_overlay":
            counts["forest_overlay"] += 1
        elif source_type == "visual_boundary":
            counts["boundary"] += 1
        elif source_type == "visual_elevation":
            counts["elevation"] += 1
        elif source_type == "visual_place_treatment":
            counts["place"] += 1
        elif source_type != "visual_decoration":
            counts["runtime"] += 1
        elif "swamp" in haystack:
            counts["swamp"] += 1
        elif "road" in haystack or "plank" in haystack:
            counts["road"] += 1
        elif "ruin" in haystack or "brick" in haystack or "stone" in haystack or "block" in haystack:
            counts["ruins"] += 1
        elif "place" in haystack or "scene" in haystack:
            counts["place"] += 1
        else:
            counts["other"] += 1
    return counts


def _count_by(items: list[dict[str, Any]], key: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        value = item.get(key)
        if isinstance(value, str) and value:
            counts[value] += 1
    return counts


def _top_counts(counts: Counter[str], *, limit: int) -> list[dict[str, Any]]:
    return [
        {"id": key, "count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _format_density_line(
    label: str,
    data: Any,
    suffix: str,
    *,
    value_key: str = "per_1000_tiles",
) -> str:
    if not isinstance(data, dict):
        data = {}
    value = _float_value(data.get(value_key), 0.0)
    status = str(data.get("status", "unknown"))
    target_min = _float_value(data.get("target_min"), 0.0)
    target_max = _float_value(data.get("target_max"), 0.0)
    return f"  {label:<12} {value:5.1f} {suffix:<12} [{status}, target {target_min:g}-{target_max:g}]"


def _format_inline_counts(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "none"
    return ", ".join(f"{key}: {count}" for key, count in sorted(value.items()))


def _summary_int(payload: dict[str, Any], key: str) -> int:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return _int_value(summary.get(key), 0)
    return 0


def _report_total(result: dict[str, Any]) -> int:
    report = result.get("report")
    if isinstance(report, dict):
        summary = report.get("summary")
        if isinstance(summary, dict):
            return _int_value(summary.get("total"), 0)
    return 0


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("items")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _per_1000(total: int, area_tiles: int) -> float:
    return round((total / area_tiles) * 1000.0, 2) if area_tiles > 0 else 0.0


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 2) if denominator > 0 else 0.0


def _sum_int_mapping(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    return sum(item for item in value.values() if isinstance(item, int))


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default


def _float_value(value: Any, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default
