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
        "render": {
            "enabled": render_enabled,
            "layers": rendered_layers,
            "status": "ok" if render_enabled else "skipped",
        },
        "debug_files": debug_files,
        "overall": {
            "status": status,
            "notes": _overall_notes(terrain_report, elevation_report, validation_report),
        },
    }
    return terrain_report, elevation_report, summary


def format_console_summary(summary: dict[str, Any]) -> str:
    """Format a compact human-readable generation summary.

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
    render = _dict(summary.get("render"))
    debug_files = _dict(summary.get("debug_files"))
    overall = _dict(summary.get("overall"))

    lines = [
        "==> summary",
        f"TopDownMapGen v{summary.get('generator_version', __version__)}",
        f"Pipeline: {summary.get('pipeline', 'world')}",
        "",
        "World generation:",
        f"  output: {_path_text(generation.get('output'))}",
        f"  map:    {map_info.get('width', 0)} x {map_info.get('height', 0)} = {map_info.get('tiles', 0)} tiles",
        f"  seed:   {generation.get('seed')}",
        f"  status: {generation.get('status', 'unknown')}",
        "",
        "World density:",
        "  terrain:",
    ]
    for key, label in (
        ("forest", "forest"),
        ("road", "road"),
        ("swamp", "swamp"),
        ("ruins", "ruins"),
        ("open_ground", "open ground"),
    ):
        lines.append(_format_targeted_metric(label, _dict(_dict(density.get("terrain")).get(key))))
    lines.extend(["", "  collision:"])
    for key, label in (("blocked", "blocked"), ("walkable", "walkable")):
        lines.append(_format_targeted_metric(label, _dict(_dict(density.get("collision")).get(key))))
    lines.extend(["", "  movement:"])
    for key, label in (("normal", "normal"), ("slow", "slow"), ("blocked", "blocked")):
        lines.append(_format_targeted_metric(label, _dict(_dict(density.get("movement")).get(key))))
    lines.extend(["", "  elevation profile:"])
    profile = _dict(elevation.get("profile"))
    lines.extend(
        [
            f"    map class:        {_path_text(profile.get('map_class', 'unknown'))}",
            f"    format range:     {_range_text(profile.get('format_range'))}",
            f"    active range:     {_range_text(profile.get('active_range'))}",
            f"    rare range:       {_range_text(profile.get('rare_range'))}",
            f"    terrace target:   {_range_text(profile.get('terrace_target_size_tiles'))} tiles",
            f"    smoothing passes: {int(profile.get('score_smoothing_passes', 0))}",
            f"    max natural delta:{int(profile.get('max_natural_delta', 0)):>2}",
        ],
    )
    lines.extend(["", "  elevation:"])
    bands = _dict(elevation.get("bands"))
    for key, label in (
        ("underground_-5_-1", "underground -5..-1"),
        ("ground_0", "ground 0"),
        ("low_raised_1_4", "raised 1..4"),
        ("hills_5_10", "hills 5..10"),
        ("highlands_11_16", "highlands 11..16"),
        ("landmarks_17_20", "landmarks 17..20"),
    ):
        lines.append(_format_targeted_metric(label, _dict(bands.get(key))))
    summary_info = _dict(elevation.get("summary"))
    lines.extend(
        [
            f"    min level:        {summary_info.get('min_level', 0):>5}",
            f"    max level:        {summary_info.get('max_level', 0):>5}",
            "",
            "  geography:",
        ],
    )
    geography = _dict(elevation.get("geography"))
    macro_regions = _dict(geography.get("macro_regions"))
    lines.append(f"    macro regions:     {int(macro_regions.get('count', 0)):>5}")
    sources = _dict(geography.get("sources"))
    if sources:
        geography_source = float(_dict(sources.get("geography")).get("percent", 0.0))
        water_source = float(_dict(sources.get("water")).get("percent", 0.0))
        structural_source = float(_dict(sources.get("structural_depth")).get("percent", 0.0))
        lines.append(
            f"    sources: geography {geography_source:.1f}%, "
            f"water {water_source:.1f}%, structural {structural_source:.1f}%",
        )
    masks = _dict(geography.get("masks"))
    for key, label in (
        ("basins", "basins"),
        ("lowlands", "lowlands"),
        ("plains", "plains"),
        ("hills", "hills"),
        ("plateaus", "plateaus"),
        ("ridges", "ridges"),
        ("mountains", "mountains"),
        ("peaks", "peaks"),
    ):
        metric = _dict(masks.get(key))
        if metric:
            lines.append(_format_plain_metric(label, metric))
    moisture = _dict(geography.get("moisture"))
    if moisture:
        lines.append(
            f"    moisture avg:      {float(moisture.get('avg', 0.0)):>5.3f}"
            f" [{float(moisture.get('min', 0.0)):>5.3f}..{float(moisture.get('max', 0.0)):>5.3f}]",
        )
    standing_water = _dict(geography.get("standing_water"))
    if standing_water:
        water_total = float(_dict(standing_water.get("water_total")).get("percent", 0.0))
        wet_lowland = float(_dict(standing_water.get("wet_lowland_total")).get("percent", 0.0))
        dry_lowland = float(_dict(standing_water.get("dry_lowland_total")).get("percent", 0.0))
        structural = float(_dict(standing_water.get("structural_total")).get("percent", 0.0))
        lines.append(
            f"    standing water: water {water_total:.1f}%, "
            f"wet lowland {wet_lowland:.1f}%, dry lowland {dry_lowland:.1f}%",
        )
        lines.append(f"    water model:       no rivers, structural depth {structural:.1f}%")
    slope_bands = _dict(_dict(geography.get("slope")).get("bands"))
    if slope_bands:
        flat = float(_dict(slope_bands.get("flat")).get("percent", 0.0))
        gentle = float(_dict(slope_bands.get("gentle")).get("percent", 0.0))
        steep = float(_dict(slope_bands.get("steep")).get("percent", 0.0))
        cliff = float(_dict(slope_bands.get("cliff")).get("percent", 0.0))
        lines.append(f"    slope: flat {flat:.1f}%, gentle {gentle:.1f}%, steep {steep:.1f}%, cliff {cliff:.1f}%")
    traversal_repair = _dict(elevation.get("traversal_repair"))
    repair_summary = _dict(traversal_repair.get("summary"))
    if repair_summary:
        lines.append(
            "    traversal repair: "
            f"{int(repair_summary.get('unreachable_before', 0))} -> "
            f"{int(repair_summary.get('unreachable_after', 0))} unreachable, "
            f"adjusted {int(repair_summary.get('adjusted_tiles', 0))} tiles, "
            f"goal {'ok' if repair_summary.get('goal_reachable_after') else 'blocked'}",
        )
    terrain_island_repair = _dict(elevation.get("terrain_island_repair"))
    island_summary = _dict(terrain_island_repair.get("summary"))
    if island_summary:
        lines.append(
            "    terrain islands:  "
            f"removed {int(island_summary.get('small_islands_removed', 0))} small "
            f"({int(island_summary.get('small_island_tiles_removed', 0))} tiles), "
            f"preserved {int(island_summary.get('large_islands_preserved', 0))} large",
        )
    lines.extend(["", "  elevation transitions:"])
    transitions = _dict(elevation.get("transitions"))
    lines.append(_format_transition_metric("total", transitions.get("total", 0)))
    connector_counts = _dict(transitions.get("by_connector"))
    type_counts = _dict(transitions.get("by_type"))
    for key, label, source in (
        ("slope", "slopes", connector_counts),
        ("ramp", "ramps", connector_counts),
        ("stairs", "stairs", connector_counts),
        ("bridge_edge", "bridge edges", type_counts),
        ("steep_transition", "steep edges", type_counts),
        ("step_up", "step up", type_counts),
        ("step_down", "step down", type_counts),
    ):
        lines.append(f"    {label + ':':<22}{int(source.get(key, 0)):>7}")
    lines.extend(["", "  world structure:"])
    for key, label in (
        ("places", "places"),
        ("routes", "routes"),
        ("markers", "markers"),
        ("runtime_objects", "runtime objects"),
    ):
        lines.append(f"    {label + ':':<22}{int(structure.get(key, 0)):>7} {_status_tag('ok')}")
    lines.extend(
        [
            "",
            "Render:",
            f"  enabled: {str(render.get('enabled', False)).lower()}",
            f"  status:  {render.get('status', 'unknown')}",
            "",
            "Debug files:",
        ],
    )
    for label, path in debug_files.items():
        lines.append(f"  {str(label).replace('_', ' ') + ':':<29}{_path_text(path)}")
    lines.extend(["", "Overall:", f"  status: {overall.get('status', 'unknown')}"])
    notes = overall.get("notes")
    if isinstance(notes, list) and notes:
        lines.append("  notes:")
        for note in notes:
            lines.append(f"    - {note}")
    return "\n".join(lines)


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
