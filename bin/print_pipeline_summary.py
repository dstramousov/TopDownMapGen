#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any


DEFAULT_PROFILE = "top_down_visualgen/profiles/dark_forest"


def main() -> int:
    """Print a compact pipeline health summary."""
    parser = argparse.ArgumentParser(description="Print TopDownMapGen pipeline summary.")
    parser.add_argument("output", nargs="?", type=Path, default=Path("output"))
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    args = parser.parse_args()

    try:
        print_pipeline_summary(args.output, args.project_root, args.profile)
    except FileNotFoundError as exc:
        print(f"FAILED: missing summary input: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"FAILED: invalid summary input: {exc}", file=sys.stderr)
        return 1
    return 0


def print_pipeline_summary(output_dir: Path, project_root: Path, profile: str) -> None:
    """Print the final world/visual pipeline summary.

    Args:
        output_dir: Generated world output directory.
        project_root: Project root directory.
        profile: Visual profile path displayed in the report.

    Raises:
        FileNotFoundError: If a required report file is missing.
        ValueError: If a required report file is not a JSON object.
    """
    output_dir = output_dir.resolve()
    project_root = project_root.resolve()
    world_report = _read_json_object(output_dir / "world_density_report.json")
    visual_report = _read_json_object(output_dir / "visual_map" / "debug" / "visual_density_report.json")
    autotile_report = _read_json_object(output_dir / "visual_map" / "debug" / "autotile_report.json")
    unmapped_report = _read_optional_json_object(output_dir / "visual_map" / "debug" / "unmapped_terrain_report.json")
    decoration_report = _read_optional_json_object(output_dir / "visual_map" / "debug" / "decoration_report.json")
    place_report = _read_optional_json_object(output_dir / "visual_map" / "debug" / "place_treatment_report.json")
    manifest = _read_optional_json_object(output_dir / "_manifest.json")

    version = _project_version(project_root)
    map_info = _dict(world_report.get("map"))
    width = _int(map_info.get("width"))
    height = _int(map_info.get("height"))
    area = _int(map_info.get("area_tiles"), width * height)
    seed = map_info.get("seed") or _nested(manifest, "versions").get("resolved_seed") or "unknown"
    world_status = _nested(world_report, "quality").get("status", "ok")
    visual_status = _nested(visual_report, "quality").get("status", "ok")
    overall_status = _overall_status([str(world_status), str(visual_status)])

    lines: list[str] = [
        f"TopDownMapGen v{version}",
        "Pipeline: world -> visual -> debug",
        "",
        "World generation:",
        f"  output: {_display_path(output_dir, project_root)}/",
        f"  map:    {width} x {height} = {area} tiles",
        f"  seed:   {seed}",
        f"  status: {world_status}",
        "",
    ]
    lines.extend(_world_density_lines(world_report))
    lines.extend([
        "",
        "Visual pipeline:",
        f"  profile: {profile}",
        f"  output:  {_display_path(output_dir / 'visual_map', project_root)}/",
        f"  status:  {visual_status}",
        "",
    ])
    lines.extend(_visual_density_lines(visual_report))
    lines.extend(["", *_autotiling_lines(visual_report, autotile_report, unmapped_report)])
    lines.extend(["", *_visual_elevation_lines(visual_report)])
    lines.extend(["", *_debug_file_lines(output_dir, project_root)])
    lines.extend(["", "Overall:", f"  status: {overall_status}", "  notes:"])
    lines.extend(_notes(world_report, visual_report, autotile_report, unmapped_report, decoration_report, place_report))
    print("\n".join(lines))


def _world_density_lines(report: dict[str, Any]) -> list[str]:
    terrain = _dict(report.get("terrain"))
    collision = _dict(report.get("collision"))
    movement = _dict(report.get("movement"))
    elevation = _dict(report.get("elevation"))
    transitions = _dict(report.get("elevation_transitions"))
    structure = _dict(report.get("world_structure"))
    return [
        "World density:",
        "  terrain:",
        _format_tile_percent("forest", terrain.get("forest")),
        _format_tile_percent("road", terrain.get("road")),
        _format_tile_percent("swamp", terrain.get("swamp")),
        _format_tile_percent("ruins", terrain.get("ruins")),
        _format_tile_percent("open ground", terrain.get("open_ground")),
        "",
        "  collision:",
        _format_tile_percent("blocked", _nested(collision, "blocked")),
        _format_tile_percent("walkable", _nested(collision, "walkable"), include_target=False),
        "",
        "  movement:",
        _format_tile_percent("normal", _nested(movement, "normal"), include_target=False),
        _format_tile_percent("slow", _nested(movement, "slow")),
        _format_tile_percent("blocked", _nested(movement, "blocked"), include_target=False),
        "",
        "  elevation:",
        _format_tile_percent("lowlands -1", _nested(elevation, "lowlands")),
        _format_tile_percent("ground 0", _nested(elevation, "ground"), include_target=False),
        _format_tile_percent("raised 1+", _nested(elevation, "raised")),
        _format_tile_percent("high 2+", _nested(elevation, "high")),
        _format_tile_percent("towers 3+", _nested(elevation, "towers")),
        _format_tile_percent("landmarks 4", _nested(elevation, "landmarks"), include_target=False),
        "",
        "  elevation transitions:",
        _format_count("total", _nested(transitions, "total")),
        _format_transition_kind("ramps", transitions),
        _format_transition_kind("stairs", transitions),
        _format_transition_kind("slopes", transitions),
        f"    {'unsafe edges':<15} {_int(transitions.get('movement_blocked')):6d} [ok]",
        "",
        "  world structure:",
        _format_count("places", _nested(structure, "places")),
        _format_count("routes", _nested(structure, "routes"), include_target=False),
        _format_count("markers", _nested(structure, "markers"), include_target=False),
        _format_count("runtime objects", _nested(structure, "runtime_objects"), include_target=False),
    ]


def _visual_density_lines(report: dict[str, Any]) -> list[str]:
    visual = _nested(report, "visual_objects")
    decorations = _nested(report, "decorations")
    place = _nested(report, "place_treatment")
    by_source = _dict(report.get("by_source"))
    by_category = _dict(report.get("by_category"))
    top_sprites = _list(report.get("top_sprites"))
    lines = [
        "Visual density:",
        "  visual objects:",
        f"    total:          {_int(visual.get('total'))}",
        f"    density:        {_float(visual.get('per_1000_tiles')):4.1f} / 1000 tiles [{visual.get('status', 'unknown')}, target {_target(visual)}]",
        "",
        "  by source:",
        f"    runtime:         {_int(by_source.get('runtime'))} = {_per_1000(_int(by_source.get('runtime')), _area(report)):4.1f} / 1000 tiles",
        f"    decorations:    {_int(by_source.get('decorations'))} = {_float(decorations.get('per_1000_tiles')):4.1f} / 1000 tiles [{decorations.get('status', 'unknown')}, target {_target(decorations)}]",
        f"    place treatment: {_int(by_source.get('place_treatment'))} = {_float(place.get('objects_per_place')):4.1f} / place      [{place.get('status', 'unknown')}, target {_target(place)}]",
        "",
        "  by category:",
    ]
    for key in ("swamp", "road", "ruins", "place", "runtime", "other"):
        lines.append(f"    {key + ':':<16} {_int(by_category.get(key)):6d}")
    lines.extend(["", "  top sprites:"])
    for item in top_sprites[:5]:
        if isinstance(item, dict):
            lines.append(f"    {str(item.get('id', 'unknown')) + ':':<30} {_int(item.get('count')):6d}")
    return lines


def _autotiling_lines(visual_report: dict[str, Any], autotile_report: dict[str, Any], unmapped_report: dict[str, Any]) -> list[str]:
    autotiling = _nested(visual_report, "autotiling")
    groups = _dict(autotiling.get("groups")) or _dict(autotile_report.get("groups"))
    unmapped = _nested(visual_report, "unmapped_terrain")
    unmapped_total = _int(unmapped.get("total"), _int(unmapped_report.get("unmapped_total")))
    unmapped_status = str(unmapped.get("status", unmapped_report.get("status", "unknown")))
    return [
        "Autotiling:",
        "  groups:",
        f"    forest:        {_int(groups.get('forest')):6d} tiles",
        f"    road:          {_int(groups.get('road')):6d} tiles",
        f"    swamp:         {_int(groups.get('swamp')):6d} tiles",
        "",
        "  fallbacks:",
        f"    total:         {_int(autotiling.get('fallback_total')):6d} [{autotiling.get('status', 'unknown')}]",
        "",
        "  unmapped terrain:",
        f"    total:         {unmapped_total:6d} [{unmapped_status}]",
    ]


def _visual_elevation_lines(report: dict[str, Any]) -> list[str]:
    elevation = _nested(report, "elevation_visual")
    return [
        "Visual elevation:",
        f"  lowland overlays:    {_int(elevation.get('lowlands')):6d} [{elevation.get('status', 'unknown')}]",
        f"  raised edge markers: {_int(elevation.get('raised')):6d} [{elevation.get('status', 'unknown')}]",
        f"  transition markers:  {_int(elevation.get('transitions')):6d} [{elevation.get('status', 'unknown')}]",
        f"  landmark markers:    {_int(elevation.get('landmarks')):6d} [{elevation.get('status', 'ok')}]",
    ]


def _debug_file_lines(output_dir: Path, project_root: Path) -> list[str]:
    visual_debug = output_dir / "visual_map" / "debug"
    return [
        "Debug files:",
        f"  world density:     {_display_path(output_dir / 'world_density_report.json', project_root)}",
        f"  visual density:    {_display_path(visual_debug / 'visual_density_report.json', project_root)}",
        f"  autotile report:   {_display_path(visual_debug / 'autotile_report.json', project_root)}",
        f"  decoration report: {_display_path(visual_debug / 'decoration_report.json', project_root)}",
        f"  place report:      {_display_path(visual_debug / 'place_treatment_report.json', project_root)}",
        f"  preview:           {_display_path(output_dir / 'visual_map' / 'preview.png', project_root)}",
        f"  steps:             {_display_path(visual_debug / 'steps', project_root)}/",
    ]


def _notes(
    world_report: dict[str, Any],
    visual_report: dict[str, Any],
    autotile_report: dict[str, Any],
    unmapped_report: dict[str, Any],
    decoration_report: dict[str, Any],
    place_report: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    quality = str(_nested(visual_report, "quality").get("status", "unknown"))
    if quality == "ok":
        notes.append("    - density is within dark_forest profile targets")
    else:
        notes.append(f"    - visual density needs attention: {quality}")
    unmapped_total = _int(_nested(visual_report, "unmapped_terrain").get("total"), _int(unmapped_report.get("unmapped_total")))
    notes.append("    - no unmapped terrain" if unmapped_total == 0 else f"    - unmapped terrain cells: {unmapped_total}")
    fallback_total = _int(_nested(visual_report, "autotiling").get("fallback_total"))
    notes.append("    - no autotile fallbacks" if fallback_total == 0 else f"    - autotile fallbacks: {fallback_total}")
    world_quality = str(_nested(world_report, "quality").get("status", "unknown"))
    notes.append("    - elevation distribution is healthy" if world_quality == "ok" else f"    - world density needs attention: {world_quality}")
    if not decoration_report:
        notes.append("    - decoration report is missing")
    if not place_report:
        notes.append("    - place treatment report is missing")
    if not autotile_report:
        notes.append("    - autotile report is missing")
    return notes


def _format_tile_percent(label: str, data: Any, *, include_target: bool = True) -> str:
    payload = _dict(data)
    result = f"    {label + ':':<15} {_int(payload.get('tiles')):6d} tiles = {_float(payload.get('percent')):5.1f}%"
    if include_target and "status" in payload:
        result += f" [{payload.get('status', 'unknown')}, target {_target(payload)}]"
    return result


def _format_count(label: str, data: Any, *, include_target: bool = True) -> str:
    payload = _dict(data)
    count = _int(payload.get("count"), _int(payload.get("total")))
    result = f"    {label + ':':<15} {count:6d}"
    if include_target and "status" in payload:
        result += f" [{payload.get('status', 'unknown')}, target {_target(payload)}]"
    elif "status" in payload:
        result += f" [{payload.get('status', 'ok')}]"
    return result


def _format_transition_kind(label: str, transitions: dict[str, Any]) -> str:
    by_type = _dict(transitions.get("by_type"))
    aliases = {
        "ramps": ("ramp", "stone_ramp"),
        "stairs": ("stairs", "stone_stairs"),
        "slopes": ("slope", "natural_slope"),
    }
    count = sum(_int(by_type.get(key)) for key in aliases.get(label, (label,)))
    return f"    {label + ':':<15} {count:6d}"


def _target(data: dict[str, Any]) -> str:
    return f"{_float(data.get('target_min')):g}–{_float(data.get('target_max')):g}"


def _area(report: dict[str, Any]) -> int:
    return _int(_nested(report, "map").get("area_tiles"))


def _per_1000(count: int, area: int) -> float:
    return round((count / area) * 1000.0, 1) if area > 0 else 0.0


def _overall_status(statuses: list[str]) -> str:
    if any(status in {"critical", "failed", "error"} for status in statuses):
        return "critical"
    if any(status in {"warning", "high", "low", "has_fallbacks", "has_unmapped_terrain"} for status in statuses):
        return "warning"
    return "ok"


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root))
    except ValueError:
        return str(path)


def _project_version(project_root: Path) -> str:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return "unknown"
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project")
    if isinstance(project, dict):
        version = project.get("version")
        if isinstance(version, str):
            return version
    return "unknown"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _read_optional_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _nested(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    return value if isinstance(value, int) else default


def _float(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, int | float) else default


if __name__ == "__main__":
    raise SystemExit(main())
