from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from . import __version__
from .constants import WALKABLE_SYMBOLS
from .paths import OutputPaths
from .utils.json_io import read_json

REPORT_SCHEMA_VERSION = "world-summary-report-v1"
WORLD_DENSITY_REPORT_SCHEMA_VERSION = "world-density-report-v1"
ELEVATION_DENSITY_REPORT_SCHEMA_VERSION = "elevation-density-report-v1"

_TERRAIN_TARGETS: dict[str, tuple[float, float]] = {
    "forest": (35.0, 55.0),
    "road": (3.0, 8.0),
    "swamp": (2.0, 7.0),
    "ruins": (2.0, 8.0),
    "open_ground": (30.0, 55.0),
}
_MOVEMENT_TARGETS: dict[str, tuple[float, float]] = {
    "slow": (4.0, 14.0),
    "blocked": (35.0, 60.0),
}
_DEFAULT_ELEVATION_TARGETS: dict[str, tuple[float, float]] = {
    "underground_-5_-1": (3.0, 12.0),
    "ground_0": (25.0, 55.0),
    "low_raised_1_4": (20.0, 45.0),
    "hills_5_10": (8.0, 25.0),
    "highlands_11_16": (1.0, 12.0),
    "landmarks_17_20": (0.1, 3.0),
}
_COLLISION_TARGETS: dict[str, tuple[float, float]] = {
    "blocked": (35.0, 60.0),
}
_TRANSITION_TARGETS: dict[str, tuple[int, int]] = {
    "total": (20, 50000),
}


def build_world_reports(
    *,
    outputs: OutputPaths,
    rows: list[str],
    runtime_data: dict[str, Any],
    resolved_seed: int,
    render_enabled: bool,
    rendered_layers: list[str],
    validation_report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build all machine-readable world summary reports.

    Args:
        outputs: Standard output paths.
        rows: ASCII terrain rows.
        runtime_data: Runtime tactical map object.
        resolved_seed: Concrete generation seed.
        render_enabled: Whether PNG rendering was enabled.
        rendered_layers: Names of rendered PNG layers.
        validation_report: Final validation report.

    Returns:
        Tuple of world density, elevation density, and combined summary reports.
    """
    width = len(rows[0]) if rows else 0
    height = len(rows)
    total_tiles = width * height
    terrain_report = _build_world_density_report(rows=rows, runtime_data=runtime_data)
    elevation_report = _build_elevation_density_report(
        outputs=outputs,
        total_tiles=total_tiles,
        runtime_data=runtime_data,
    )
    structure = _build_world_structure(outputs=outputs, runtime_data=runtime_data)
    debug_files = _build_debug_files(outputs=outputs, render_enabled=render_enabled)
    status = _overall_status(terrain_report, elevation_report, validation_report)
    summary = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generator_version": __version__,
        "pipeline": "world",
        "status": status,
        "world_generation": {
            "output": str(outputs.output_dir),
            "map": {"width": width, "height": height, "tiles": total_tiles},
            "seed": resolved_seed,
            "status": "ok" if status != "failed" else "failed",
        },
        "world_density": terrain_report,
        "elevation_density": elevation_report,
        "world_structure": structure,
        "terrain_guidance": _dict(runtime_data.get("terrain_guidance")),
        "render": {
            "enabled": render_enabled,
            "layers": rendered_layers,
            "status": "ok" if render_enabled else "skipped",
        },
        "debug_files": debug_files,
        "validation": {
            "status": validation_report.get("status", "unknown"),
            "warnings": validation_report.get("warnings", []),
            "errors": validation_report.get("errors", []),
        },
        "overall": {
            "status": status,
            "notes": _overall_notes(terrain_report, elevation_report, validation_report),
        },
    }
    return terrain_report, elevation_report, summary


def format_console_summary(summary: dict[str, Any]) -> str:
    """Format a compact Russian generation summary.

    Args:
        summary: Combined world summary report.

    Returns:
        Multi-line text block for CLI output.
    """
    generation = _dict(summary.get("world_generation"))
    map_info = _dict(generation.get("map"))
    density = _dict(summary.get("world_density"))
    elevation = _dict(summary.get("elevation_density"))
    structure = _dict(summary.get("world_structure"))
    validation = _dict(summary.get("validation"))
    overall = _dict(summary.get("overall"))
    terrain_guidance = _dict(summary.get("terrain_guidance"))

    terrain = _dict(density.get("terrain"))
    collision = _dict(density.get("collision"))
    geography = _dict(elevation.get("geography"))
    standing_water = _dict(geography.get("standing_water"))
    slope_bands = _dict(_dict(geography.get("slope")).get("bands"))
    profile = _dict(elevation.get("profile"))
    elevation_summary = _dict(elevation.get("summary"))
    traversal = _dict(_dict(elevation.get("traversal_repair")).get("summary"))
    islands = _dict(_dict(elevation.get("terrain_island_repair")).get("summary"))

    warnings = validation.get("warnings")
    warning_items = warnings if isinstance(warnings, list) else []
    errors = validation.get("errors")
    error_items = errors if isinstance(errors, list) else []

    lines = [
        f"TopDownMapGen v{summary.get('generator_version', __version__)}",
        "",
        "Карта:",
        (
            f"  размер: {map_info.get('width', 0)} × {map_info.get('height', 0)}"
            f" = {map_info.get('tiles', 0)} тайлов"
        ),
        f"  seed: {generation.get('seed')}",
        (
            "  стиль высот: "
            f"{_path_text(profile.get('style', 'normal'))} — "
            f"{_translate_character(profile.get('character'))}"
        ),
        (
            "  диапазон высот: "
            f"{elevation_summary.get('min_level', 0)}.."
            f"{elevation_summary.get('max_level', 0)}"
        ),
        "",
        "Основные показатели:",
        _metric_line_ru("лес", _dict(terrain.get("forest"))),
        _metric_line_ru("дороги", _dict(terrain.get("road"))),
        _metric_line_ru("болотная местность", _dict(terrain.get("swamp"))),
        _metric_line_ru("руины", _dict(terrain.get("ruins"))),
        _metric_line_ru("открытая земля", _dict(terrain.get("open_ground"))),
        _metric_line_ru("заблокировано", _dict(collision.get("blocked"))),
    ]

    if standing_water:
        water = _dict(standing_water.get("water_total"))
        wet = _dict(standing_water.get("wet_lowland_total"))
        lines.append(f"  {'стоячая вода:':<22}{float(water.get('percent', 0.0)):>6.1f}%")
        lines.append(f"  {'влажные низины:':<22}{float(wet.get('percent', 0.0)):>6.1f}%")
    if slope_bands:
        steep = float(_dict(slope_bands.get("steep")).get("percent", 0.0))
        cliff = float(_dict(slope_bands.get("cliff")).get("percent", 0.0))
        lines.append(f"  {'крутые склоны:':<22}{steep:>6.1f}%")
        lines.append(f"  {'обрывы:':<22}{cliff:>6.1f}%")

    if terrain_guidance.get("enabled"):
        evaluated = int(terrain_guidance.get("region_candidates_evaluated", 0))
        rejected = int(terrain_guidance.get("region_candidates_rejected_steep", 0))
        guided_routes = int(terrain_guidance.get("guided_road_routes", 0))
        fallback_routes = int(terrain_guidance.get("fallback_road_routes", 0))
        steep_road_tiles = int(terrain_guidance.get("road_steep_tiles", 0))
        cliff_road_tiles = int(terrain_guidance.get("road_cliff_tiles", 0))
        average_road_slope = float(terrain_guidance.get("average_road_slope", 0.0))
        lines.extend(
            [
                "",
                "Географическая адаптация terrain:",
                (
                    f"  кандидатов регионов: {evaluated}, отклонено крутых: {rejected}, "
                    f"fallback: {int(terrain_guidance.get('region_steep_fallbacks', 0))}"
                ),
                f"  перемещено руин на ровные площадки: {int(terrain_guidance.get('ruin_regions_relocated', 0))}",
                f"  маршрутов по рельефу: {guided_routes}, fallback: {fallback_routes}",
                f"  средний локальный уклон дорог: {average_road_slope:.4f}",
                f"  тайлов дорог на крутых участках: {steep_road_tiles}",
                (
                    f"  тайлов дорог через обрывы: {cliff_road_tiles} "
                    f"{_status_tag_ru(cliff_road_tiles == 0, warning=True)}"
                ),
                f"  сохранено естественных барьеров от открытой земли: {int(terrain_guidance.get('open_ground_barrier_tiles_skipped', 0))}",
                f"  сохранено естественных барьеров от дорог: {int(terrain_guidance.get('path_barrier_tiles_skipped', 0))}",
                f"  отклонено неподходящих болотных зон: {int(terrain_guidance.get('wetland_candidates_rejected', 0))}",
                f"  отклонено неподходящих лесных зон: {int(terrain_guidance.get('forest_candidates_rejected', 0))}",
                f"  руин с плохим footprint: {int(terrain_guidance.get('ruin_bad_footprints', 0))}",
            ]
        )

    lines.extend(["", "Проходимость:"])
    if traversal:
        unreachable_before = int(traversal.get("unreachable_before", 0))
        unreachable_after = int(traversal.get("unreachable_after", 0))
        adjusted = int(traversal.get("adjusted_tiles", 0))
        lines.append(
            f"  недостижимые тайлы: {unreachable_before} -> "
            f"{unreachable_after} {_status_tag_ru(unreachable_after == 0)}"
        )
        lines.append(f"  traversal repair: изменено {adjusted} тайлов")
    if islands:
        removed = int(islands.get("small_island_tiles_removed", 0))
        preserved = int(islands.get("large_islands_preserved", 0))
        lines.append(f"  удалено мелких островов: {removed} тайлов")
        lines.append(
            f"  сохранено крупных островов: {preserved} "
            f"{_status_tag_ru(preserved == 0, warning=True)}"
        )

    lines.extend(
        [
            "",
            "Структура мира:",
            f"  места: {int(structure.get('places', 0))}",
            f"  маршруты: {int(structure.get('routes', 0))}",
            f"  маркеры: {int(structure.get('markers', 0))}",
            f"  runtime-объекты: {int(structure.get('runtime_objects', 0))}",
            "",
            "Результаты:",
            "  map package: output/map_package/map.json",
            "  основной preview: output/full_world_preview.png",
            "  отчёты: output/*.json",
            f"  статус: {_translate_status(overall.get('status'))}",
        ],
    )

    if error_items:
        lines.append(f"  ошибки проверки: {len(error_items)}")
    if warning_items:
        lines.append(f"  предупреждения: {len(warning_items)}")
        for warning in warning_items[:5]:
            lines.append(f"    - {_format_validation_warning_ru(warning)}")
    else:
        lines.append("  предупреждения: нет")
    return "\n".join(lines)


def _metric_line_ru(label: str, metric: dict[str, Any]) -> str:
    """Format one targeted percentage metric in Russian."""
    percent = float(metric.get("percent", 0.0))
    status = str(metric.get("status", "ok"))
    return f"  {label + ':':<22}{percent:>6.1f}% {_status_tag_ru(status != 'warn')}"


def _status_tag_ru(ok: bool, *, warning: bool = False) -> str:
    """Return a compact Russian status tag."""
    if ok:
        return "[ОК]"
    return "[ПРЕДУПРЕЖДЕНИЕ]" if warning else "[ВНЕ ЦЕЛИ]"


def _translate_status(value: Any) -> str:
    """Translate a report status to Russian."""
    return {
        "ok": "успешно",
        "warning": "успешно с предупреждениями",
        "failed": "ошибка",
        "passed": "успешно",
        "passed_with_warnings": "успешно с предупреждениями",
        "skipped": "пропущено",
    }.get(str(value), str(value))


def _translate_character(value: Any) -> str:
    """Translate known elevation character descriptions to Russian."""
    return {
        "nearly flat -1..1 micro relief": "почти плоский микрорельеф -1..1",
        "soft lowland terrain": "мягкая низинная местность",
        "playable rolling terrain": "игровые холмы и долины",
        "balanced terrain": "сбалансированный рельеф",
        "rough broken terrain": "пересечённая рваная местность",
        "frequent mountain terrain": "частый горный рельеф",
        "large sparse plateaus": "крупные редкие плато",
    }.get(str(value), str(value))


def _format_validation_warning_ru(value: Any) -> str:
    """Format one validation warning for console output."""
    warning = _dict(value)
    code = str(warning.get("code", "unknown_warning"))
    if code == "tactical_points_near_map_edge":
        details = _dict(warning.get("details"))
        total = sum(int(item) for item in details.values() if isinstance(item, int))
        return f"тактические точки рядом с краем карты: {total}"
    if code == "quality.map_package_main_path_elevation_reachable":
        return "главный маршрут map package не подтверждён как проходимый по высотам"
    return code

def _build_world_density_report(*, rows: list[str], runtime_data: dict[str, Any]) -> dict[str, Any]:
    width = len(rows[0]) if rows else 0
    height = len(rows)
    total = width * height
    tile_counts = Counter(tile for row in rows for tile in row)
    movement_costs = _dict(runtime_data.get("movement_costs"))
    terrain = {
        "forest": _metric(tile_counts.get("T", 0), total, _TERRAIN_TARGETS["forest"]),
        "road": _metric(tile_counts.get(".", 0), total, _TERRAIN_TARGETS["road"]),
        "swamp": _metric(tile_counts.get("w", 0), total, _TERRAIN_TARGETS["swamp"]),
        "ruins": _metric(tile_counts.get("#", 0) + tile_counts.get("R", 0), total, _TERRAIN_TARGETS["ruins"]),
        "open_ground": _metric(
            sum(tile_counts.get(tile, 0) for tile in ("+", "c", "f", "m", "S", "G")),
            total,
            _TERRAIN_TARGETS["open_ground"],
        ),
    }
    blocked_count = sum(count for tile, count in tile_counts.items() if tile not in WALKABLE_SYMBOLS)
    walkable_count = total - blocked_count
    slow_count = 0
    normal_count = 0
    for tile, count in tile_counts.items():
        if tile not in WALKABLE_SYMBOLS:
            continue
        cost = movement_costs.get(tile)
        if isinstance(cost, int | float) and cost > 1:
            slow_count += count
        else:
            normal_count += count
    return {
        "schema_version": WORLD_DENSITY_REPORT_SCHEMA_VERSION,
        "dimensions": {"width": width, "height": height, "tiles": total},
        "terrain": terrain,
        "collision": {
            "blocked": _metric(blocked_count, total, _COLLISION_TARGETS["blocked"]),
            "walkable": _metric(walkable_count, total, None),
        },
        "movement": {
            "normal": _metric(normal_count, total, None),
            "slow": _metric(slow_count, total, _MOVEMENT_TARGETS["slow"]),
            "blocked": _metric(blocked_count, total, _MOVEMENT_TARGETS["blocked"]),
        },
        "tile_counts": dict(sorted(tile_counts.items())),
    }


def _build_elevation_density_report(
    *,
    outputs: OutputPaths,
    total_tiles: int,
    runtime_data: dict[str, Any],
) -> dict[str, Any]:
    runtime_grids = _read_json_or_empty(outputs.map_package_runtime_grids)
    elevation_model = _read_json_or_empty(outputs.map_package_elevation_model)
    transitions_package = _read_json_or_empty(outputs.map_package_elevation_transitions)
    generation_report = _dict(runtime_data.get("elevation_generation_report"))
    profile = _dict(generation_report.get("profile"))
    elevation_targets = _elevation_targets(profile)
    height_rows = _height_rows(runtime_grids)
    counts = Counter(level for row in height_rows for level in row)
    total = total_tiles or sum(counts.values())
    bands = {
        "underground_-5_-1": _metric(
            sum(counts.get(level, 0) for level in range(-5, 0)),
            total,
            elevation_targets["underground_-5_-1"],
        ),
        "ground_0": _metric(counts.get(0, 0), total, elevation_targets["ground_0"]),
        "low_raised_1_4": _metric(
            sum(counts.get(level, 0) for level in range(1, 5)),
            total,
            elevation_targets["low_raised_1_4"],
        ),
        "hills_5_10": _metric(
            sum(counts.get(level, 0) for level in range(5, 11)),
            total,
            elevation_targets["hills_5_10"],
        ),
        "highlands_11_16": _metric(
            sum(counts.get(level, 0) for level in range(11, 17)),
            total,
            elevation_targets["highlands_11_16"],
        ),
        "landmarks_17_20": _metric(
            sum(counts.get(level, 0) for level in range(17, 21)),
            total,
            elevation_targets["landmarks_17_20"],
        ),
    }
    summary = _dict(elevation_model.get("summary"))
    transitions = _dict(transitions_package.get("summary"))
    return {
        "schema_version": ELEVATION_DENSITY_REPORT_SCHEMA_VERSION,
        "summary": {
            "min_level": summary.get("min_level", min(counts) if counts else 0),
            "max_level": summary.get("max_level", max(counts) if counts else 0),
            "levels_present": summary.get("levels_present", [str(level) for level in sorted(counts)]),
            "level_counts": {str(level): counts[level] for level in sorted(counts)},
            "level_zero_percent": _percent(counts.get(0, 0), total),
        },
        "profile": profile,
        "bands": bands,
        "adjacent_delta": _dict(generation_report.get("adjacent_delta")),
        "region_transition_shaping": _dict(generation_report.get("region_transition_shaping")),
        "main_route_alignment": _dict(generation_report.get("main_route_alignment")),
        "traversal_repair": _dict(generation_report.get("traversal_repair")),
        "terrain_island_repair": _dict(runtime_data.get("terrain_island_repair")),
        "geography": _geography_summary(_dict(generation_report.get("geography"))),
        "transitions": {
            "total": int(transitions.get("total", 0)),
            "by_type": _dict(transitions.get("by_type")),
            "by_connector": _dict(transitions.get("by_connector")),
            "movement_allowed": int(transitions.get("movement_allowed", 0)),
            "movement_blocked": int(transitions.get("movement_blocked", 0)),
        },
    }



def _geography_summary(geography: dict[str, Any]) -> dict[str, Any]:
    output = dict(geography)
    grids = output.pop("grids", None)
    if isinstance(grids, dict):
        output["debug_grids"] = {
            "geographic_level_grid": "available" if "geographic_level_grid" in grids else "missing",
            "runtime_level_grid": "available" if "runtime_level_grid" in grids else "missing",
            "source_grid": "available" if "source_grid" in grids else "missing",
            "mask_grid": "available" if "mask_grid" in grids else "missing",
            "moisture_grid": "available" if "moisture_grid" in grids else "missing",
            "slope_grid": "available" if "slope_grid" in grids else "missing",
            "water_lowland_grid": "available" if "water_lowland_grid" in grids else "missing",
            "region_grid": "available" if "region_grid" in grids else "missing",
        }
    return output

def _build_world_structure(*, outputs: OutputPaths, runtime_data: dict[str, Any]) -> dict[str, int]:
    routes = _read_json_or_empty(outputs.map_package_routes)
    markers = _read_json_or_empty(outputs.map_package_markers)
    return {
        "places": len(_list(runtime_data.get("places"))),
        "routes": len(_list(routes.get("items"))),
        "markers": len(_list(markers.get("items"))),
        "runtime_objects": len(_list(runtime_data.get("runtime_objects"))),
    }


def _build_debug_files(*, outputs: OutputPaths, render_enabled: bool) -> dict[str, str]:
    files = {
        "world_density": outputs.world_density_report,
        "elevation_density": outputs.elevation_density_report,
        "world_summary": outputs.world_summary_report,
        "terrain_island_report": outputs.terrain_island_report,
        "terrain_guidance_report": outputs.terrain_guidance_report,
        "generation_log": outputs.log_file,
        "full_world_preview": outputs.output_dir / "full_world_preview.png",
        "elevation_preview": outputs.output_dir / "elevation_preview.png",
        "elevation_source_preview": outputs.output_dir / "elevation_source_preview.png",
        "geography_preview": outputs.output_dir / "geography_preview.png",
        "moisture_preview": outputs.output_dir / "moisture_preview.png",
        "water_lowland_preview": outputs.output_dir / "water_lowland_preview.png",
        "slope_preview": outputs.output_dir / "slope_preview.png",
        "3d_preview_nw": outputs.output_dir / "geography_3d_preview" / "view_nw.png",
        "3d_preview_ne": outputs.output_dir / "geography_3d_preview" / "view_ne.png",
        "3d_preview_se": outputs.output_dir / "geography_3d_preview" / "view_se.png",
        "3d_preview_sw": outputs.output_dir / "geography_3d_preview" / "view_sw.png",
        "3d_walkability_nw": outputs.output_dir / "geography_3d_preview" / "walkability_nw.png",
        "3d_walkability_ne": outputs.output_dir / "geography_3d_preview" / "walkability_ne.png",
        "3d_walkability_se": outputs.output_dir / "geography_3d_preview" / "walkability_se.png",
        "3d_walkability_sw": outputs.output_dir / "geography_3d_preview" / "walkability_sw.png",
        "3d_walkability_report": outputs.output_dir / "geography_3d_preview" / "walkability_report.json",
        "3d_traversal_nw": outputs.output_dir / "geography_3d_preview" / "traversal_nw.png",
        "3d_traversal_ne": outputs.output_dir / "geography_3d_preview" / "traversal_ne.png",
        "3d_traversal_se": outputs.output_dir / "geography_3d_preview" / "traversal_se.png",
        "3d_traversal_sw": outputs.output_dir / "geography_3d_preview" / "traversal_sw.png",
        "3d_traversal_report": outputs.output_dir / "geography_3d_preview" / "traversal_report.json",
        "validation_report": outputs.validation_report,
        "runtime_grids": outputs.map_package_runtime_grids,
        "elevation_model": outputs.map_package_elevation_model,
        "elevation_transitions": outputs.map_package_elevation_transitions,
        "map_package": outputs.map_package_map,
    }
    if render_enabled:
        files["base_render"] = outputs.layer_base_map
    return {key: str(value) for key, value in files.items()}


def _overall_status(
    terrain_report: dict[str, Any],
    elevation_report: dict[str, Any],
    validation_report: dict[str, Any],
) -> str:
    if validation_report.get("status") == "failed":
        return "failed"
    statuses: list[str] = []
    for section in ("terrain", "collision", "movement"):
        for metric in _dict(terrain_report.get(section)).values():
            if isinstance(metric, dict):
                statuses.append(str(metric.get("status", "ok")))
    for metric in _dict(elevation_report.get("bands")).values():
        if isinstance(metric, dict):
            statuses.append(str(metric.get("status", "ok")))
    if any(status == "warn" for status in statuses):
        return "warning"
    return "ok"


def _overall_notes(
    terrain_report: dict[str, Any],
    elevation_report: dict[str, Any],
    validation_report: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    if validation_report.get("status") in {"passed", "passed_with_warnings"}:
        notes.append("map package validation passed")
    if _all_targets_ok(_dict(terrain_report.get("terrain"))):
        notes.append("terrain density is within targets")
    if _all_targets_ok(_dict(elevation_report.get("bands"))):
        profile = _dict(elevation_report.get("profile")).get("map_class")
        if isinstance(profile, str) and profile:
            notes.append(f"elevation distribution is within {profile} size-aware targets")
        else:
            notes.append("elevation distribution is within next-gen targets")
    if _dict(elevation_report.get("summary")).get("level_zero_percent", 100.0) < 60.0:
        notes.append("level 0 is no longer the dominant 99% flat plane")
    repair_summary = _dict(_dict(elevation_report.get("traversal_repair")).get("summary"))
    if repair_summary and repair_summary.get("goal_reachable_after"):
        notes.append("start to goal is 3D-reachable after traversal repair")
    island_summary = _dict(_dict(elevation_report.get("terrain_island_repair")).get("summary"))
    removed_tiles = int(island_summary.get("small_island_tiles_removed", 0)) if island_summary else 0
    if removed_tiles > 0:
        notes.append(f"removed {removed_tiles} tiny isolated walkable terrain tiles")
    warnings = validation_report.get("warnings")
    if isinstance(warnings, list) and warnings:
        notes.append(f"validation warnings: {len(warnings)}")
    return notes


def _all_targets_ok(metrics: dict[str, Any]) -> bool:
    return all(not isinstance(metric, dict) or metric.get("status") != "warn" for metric in metrics.values())


def _elevation_targets(profile: dict[str, Any]) -> dict[str, tuple[float, float]]:
    targets = dict(_DEFAULT_ELEVATION_TARGETS)
    raw_targets = _dict(profile.get("band_targets_percent"))
    for key, value in raw_targets.items():
        if not isinstance(value, list | tuple) or len(value) != 2:
            continue
        low, high = value
        if isinstance(low, int | float) and isinstance(high, int | float):
            targets[str(key)] = (float(low), float(high))
    return targets


def _height_rows(runtime_grids: dict[str, Any]) -> list[list[int]]:
    rows = _dict(_dict(runtime_grids.get("grids")).get("height_grid")).get("rows")
    if not isinstance(rows, list):
        return []
    output: list[list[int]] = []
    for row in rows:
        if isinstance(row, list):
            output.append([int(value) for value in row if isinstance(value, int | float)])
    return output


def _metric(count: int, total: int, target: tuple[float, float] | None) -> dict[str, Any]:
    percent = _percent(count, total)
    data: dict[str, Any] = {"count": count, "percent": percent}
    if target is not None:
        data["target_percent"] = [target[0], target[1]]
        data["status"] = "ok" if target[0] <= percent <= target[1] else "warn"
    return data


def _format_targeted_metric(label: str, metric: dict[str, Any]) -> str:
    count = int(metric.get("count", 0))
    percent = float(metric.get("percent", 0.0))
    target = metric.get("target_percent")
    suffix = ""
    if isinstance(target, list) and len(target) == 2:
        suffix = f" [{str(metric.get('status', 'ok'))}, target {target[0]:g}–{target[1]:g}]"
    return f"    {label + ':':<22}{count:>7} tiles = {percent:>6.1f}%{suffix}"



def _format_plain_metric(label: str, metric: dict[str, Any]) -> str:
    count = int(metric.get("count", 0))
    percent = float(metric.get("percent", 0.0))
    return f"    {label + ':':<22}{count:>7} tiles = {percent:>6.1f}%"

def _format_transition_metric(label: str, value: Any) -> str:
    count = int(value) if isinstance(value, int | float) else 0
    target = _TRANSITION_TARGETS.get(label)
    suffix = ""
    if target is not None:
        status = "ok" if target[0] <= count <= target[1] else "warn"
        suffix = f" [{status}, target {target[0]}–{target[1]}]"
    return f"    {label + ':':<22}{count:>7}{suffix}"


def _status_tag(status: str) -> str:
    return f"[{status}]"


def _percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count * 100.0 / total, 3)


def _read_json_or_empty(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _path_text(value: Any) -> str:
    return str(value) if value is not None else ""


def _range_text(value: Any) -> str:
    if isinstance(value, list | tuple) and len(value) == 2:
        return f"{value[0]}..{value[1]}"
    return "unknown"
