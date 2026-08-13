from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin
from random import Random
from typing import Any

from .fortress_island import (
    MASK_OUTSIDE,
    _copy_int_rows,
    _refresh_mask_grid,
    _refresh_water_grid,
    _restore_runtime_object_elevation,
    _slope_report,
    _slope_rows,
    _sparse_cells,
    _summary,
)
from .runtime_objects import runtime_object_elevation_overrides

SHALLOW_LEVEL = -1
PATH_LEVEL = 0
APPROACH_OUTSIDE = 0
APPROACH_SHALLOW = 1
APPROACH_PATH = 2


@dataclass(frozen=True, slots=True)
class FortressApproachResult:
    """Materialized shallow approach from fortress gate to mainland."""

    rows: list[str]
    runtime_data: dict[str, Any]
    site_report: dict[str, Any]
    approach_rows: list[list[int]]
    changed_tiles: int
    shallow_tiles: int
    path_tiles: int



def skip_fortress_approach(
    *,
    rows: list[str],
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    reason: str,
) -> FortressApproachResult:
    """Record that no dedicated fortress approach is required.

    Args:
        rows: Current ASCII terrain rows.
        runtime_data: Tactical runtime data.
        site_report: Fortress report.
        reason: Stable machine-readable skip reason.

    Returns:
        Unchanged terrain and runtime data with a skipped approach report.
    """
    approach_report = {
        "status": "skipped",
        "reason": reason,
        "changed_tiles": 0,
        "shallow_tiles": 0,
        "path_tiles": 0,
        "length_tiles": 0.0,
    }
    updated_site_report = dict(site_report)
    policy = dict(updated_site_report.get("policy", {}))
    policy["phase"] = "fortress_approach_skipped"
    updated_site_report["policy"] = policy
    updated_site_report["fortress_approach"] = approach_report

    updated_runtime = dict(runtime_data)
    updated_runtime["fortress_site"] = updated_site_report
    updated_runtime["fortress_approach"] = approach_report
    return FortressApproachResult(
        rows=rows,
        runtime_data=updated_runtime,
        site_report=updated_site_report,
        approach_rows=[],
        changed_tiles=0,
        shallow_tiles=0,
        path_tiles=0,
    )

def materialize_shallow_fortress_approach(
    *,
    rows: list[str],
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    island_mask_rows: list[list[int]],
    seed: int,
) -> FortressApproachResult:
    """Create a broad walkable -1 shoal with a gate-width road.

    Args:
        rows: Current ASCII terrain rows.
        runtime_data: Tactical runtime data with elevation grids.
        site_report: Fortress report containing island and gate geometry.
        island_mask_rows: Materialized island mask.
        seed: Resolved world seed.

    Returns:
        Updated terrain, elevation data, report, and approach mask.
    """
    plan = site_report.get("fortress_plan")
    selected = site_report.get("selected_site")
    if not isinstance(plan, dict) or not isinstance(selected, dict):
        return _empty(rows, runtime_data, site_report)
    gate = plan.get("gate_center")
    center = selected.get("center")
    if not isinstance(gate, dict) or not isinstance(center, dict):
        return _empty(rows, runtime_data, site_report)

    report = runtime_data.get("elevation_generation_report")
    geography = report.get("geography") if isinstance(report, dict) else None
    grids = geography.get("grids") if isinstance(geography, dict) else None
    if not isinstance(grids, dict):
        raise ValueError("Missing elevation geography grids")
    geographic_rows = _copy_int_rows(grids, "geographic_level_grid")
    runtime_rows = _copy_int_rows(grids, "runtime_level_grid")
    height = len(geographic_rows)
    width = len(geographic_rows[0]) if geographic_rows else 0
    if width <= 0 or len(runtime_rows) != height:
        raise ValueError("Invalid elevation grids for fortress approach")

    gate_point = (int(gate["x"]), int(gate["y"]))
    center_point = (int(center["x"]), int(center["y"]))
    landing = _find_mainland_landing(
        levels=geographic_rows,
        island_mask_rows=island_mask_rows,
        center=center_point,
        gate=gate_point,
    )
    if landing is None:
        return _empty(rows, runtime_data, site_report)

    gate_width = max(1, int(plan.get("gate_width_tiles", 3)))
    shallow_width = gate_width * 2 + 1
    approach_rows = _build_approach_mask(
        width=width,
        height=height,
        start=gate_point,
        end=landing,
        gate_width=gate_width,
        shallow_width=shallow_width,
        island_mask_rows=island_mask_rows,
        seed=seed,
    )

    mutable_rows = [list(row) for row in rows]
    changed_tiles = 0
    shallow_tiles = 0
    path_tiles = 0
    for y, approach_row in enumerate(approach_rows):
        for x, value in enumerate(approach_row):
            if value == APPROACH_OUTSIDE:
                continue
            if value == APPROACH_SHALLOW and geographic_rows[y][x] < 0:
                if geographic_rows[y][x] != SHALLOW_LEVEL or runtime_rows[y][x] != SHALLOW_LEVEL:
                    changed_tiles += 1
                geographic_rows[y][x] = SHALLOW_LEVEL
                runtime_rows[y][x] = SHALLOW_LEVEL
                shallow_tiles += 1
            elif value == APPROACH_PATH:
                if geographic_rows[y][x] != PATH_LEVEL or runtime_rows[y][x] != PATH_LEVEL:
                    changed_tiles += 1
                geographic_rows[y][x] = PATH_LEVEL
                runtime_rows[y][x] = PATH_LEVEL
                mutable_rows[y][x] = "."
                path_tiles += 1

    _restore_runtime_object_elevation(
        runtime_rows,
        runtime_object_elevation_overrides(runtime_data.get("runtime_objects")),
    )

    slope_rows = _slope_rows(geographic_rows)
    grids["geographic_level_grid"] = {"rows": geographic_rows}
    grids["runtime_level_grid"] = {"rows": runtime_rows}
    grids["slope_grid"] = {"rows": slope_rows}
    _refresh_mask_grid(grids=grids, levels=geographic_rows, slope_rows=slope_rows)
    _refresh_water_grid(grids=grids, levels=geographic_rows)

    updated_report = dict(report)
    updated_geography = dict(geography)
    updated_geography["grids"] = grids
    updated_geography["slope"] = _slope_report(slope_rows)
    updated_report["geography"] = updated_geography
    updated_report["summary"] = _summary(runtime_rows)

    updated_runtime = dict(runtime_data)
    updated_runtime["elevation_generation_report"] = updated_report
    elevation = dict(updated_runtime.get("elevation", {}))
    elevation["default"] = 0
    elevation["cells"] = _sparse_cells(runtime_rows)
    elevation["summary"] = updated_report["summary"]
    updated_runtime["elevation"] = elevation

    approach_report = {
        "status": "materialized",
        "algorithm": "broad_shallow_shoal_with_gate_width_path_v1",
        "seed": seed,
        "gate": {"x": gate_point[0], "y": gate_point[1]},
        "mainland_landing": {"x": landing[0], "y": landing[1]},
        "gate_width_tiles": gate_width,
        "shallow_width_tiles": shallow_width,
        "shallow_level": SHALLOW_LEVEL,
        "path_level": PATH_LEVEL,
        "path_terrain": "old_overgrown_road",
        "changed_tiles": changed_tiles,
        "shallow_tiles": shallow_tiles,
        "path_tiles": path_tiles,
        "length_tiles": round(hypot(landing[0] - gate_point[0], landing[1] - gate_point[1]), 2),
    }
    updated_site_report = dict(site_report)
    policy = dict(updated_site_report.get("policy", {}))
    policy["phase"] = "fortress_approach_materialized"
    updated_site_report["policy"] = policy
    updated_site_report["fortress_approach"] = approach_report
    updated_runtime["fortress_site"] = updated_site_report
    updated_runtime["fortress_approach"] = approach_report

    return FortressApproachResult(
        rows=["".join(row) for row in mutable_rows],
        runtime_data=updated_runtime,
        site_report=updated_site_report,
        approach_rows=approach_rows,
        changed_tiles=changed_tiles,
        shallow_tiles=shallow_tiles,
        path_tiles=path_tiles,
    )


def _empty(
    rows: list[str],
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
) -> FortressApproachResult:
    return FortressApproachResult(
        rows=rows,
        runtime_data=runtime_data,
        site_report=site_report,
        approach_rows=[],
        changed_tiles=0,
        shallow_tiles=0,
        path_tiles=0,
    )


def _find_mainland_landing(
    *,
    levels: list[list[int]],
    island_mask_rows: list[list[int]],
    center: tuple[int, int],
    gate: tuple[int, int],
) -> tuple[int, int] | None:
    height = len(levels)
    width = len(levels[0]) if levels else 0
    base_angle = atan2(gate[1] - center[1], gate[0] - center[0])
    best: tuple[float, int, int] | None = None
    for index in range(-12, 13):
        offset = index * (pi / 72.0)
        angle = base_angle + offset
        seen_water = False
        depth_cost = 0.0
        for step in range(1, max(width, height) + 1):
            x = round(gate[0] + cos(angle) * step)
            y = round(gate[1] + sin(angle) * step)
            if not (0 <= x < width and 0 <= y < height):
                break
            if island_mask_rows[y][x] != MASK_OUTSIDE:
                continue
            level = levels[y][x]
            if level < 0:
                seen_water = True
                depth_cost += max(0, -1 - level) * 0.35
                continue
            if seen_water:
                score = step + depth_cost + abs(index) * 0.4
                candidate = (score, x, y)
                if best is None or candidate < best:
                    best = candidate
            break
    if best is not None:
        return best[1], best[2]
    return _nearest_mainland_landing(
        levels=levels,
        island_mask_rows=island_mask_rows,
        center=center,
        gate=gate,
    )


def _nearest_mainland_landing(
    *,
    levels: list[list[int]],
    island_mask_rows: list[list[int]],
    center: tuple[int, int],
    gate: tuple[int, int],
) -> tuple[int, int] | None:
    """Find the nearest outward land cell when directional rays miss land."""
    height = len(levels)
    width = len(levels[0]) if levels else 0
    outward_x = gate[0] - center[0]
    outward_y = gate[1] - center[1]
    outward_length = hypot(outward_x, outward_y) or 1.0
    best: tuple[float, int, int] | None = None
    for y in range(height):
        for x in range(width):
            if island_mask_rows[y][x] != MASK_OUTSIDE or levels[y][x] < 0:
                continue
            dx = x - gate[0]
            dy = y - gate[1]
            distance = hypot(dx, dy)
            if distance < 2.0:
                continue
            direction_dot = (dx * outward_x + dy * outward_y) / (
                distance * outward_length
            )
            if direction_dot < 0.15:
                continue
            water_samples = 0
            sample_count = max(2, round(distance))
            blocked_by_island = False
            for step in range(1, sample_count):
                t = step / sample_count
                sample_x = round(gate[0] + dx * t)
                sample_y = round(gate[1] + dy * t)
                if not (0 <= sample_x < width and 0 <= sample_y < height):
                    blocked_by_island = True
                    break
                if island_mask_rows[sample_y][sample_x] != MASK_OUTSIDE:
                    continue
                if levels[sample_y][sample_x] < 0:
                    water_samples += 1
            if blocked_by_island or water_samples == 0:
                continue
            angular_penalty = (1.0 - direction_dot) * 12.0
            candidate = (distance + angular_penalty, x, y)
            if best is None or candidate < best:
                best = candidate
    return None if best is None else (best[1], best[2])


def _build_approach_mask(
    *,
    width: int,
    height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    gate_width: int,
    shallow_width: int,
    island_mask_rows: list[list[int]],
    seed: int,
) -> list[list[int]]:
    rows = [[APPROACH_OUTSIDE for _ in range(width)] for _ in range(height)]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = max(1.0, float(dx * dx + dy * dy))
    shallow_half = shallow_width / 2.0
    path_half = gate_width / 2.0
    rng = Random(seed ^ 0xA991_50A1_0A5E)
    edge_phase = rng.random() * 2.0 * pi
    margin = int(shallow_half) + 3
    min_x = max(0, min(start[0], end[0]) - margin)
    max_x = min(width - 1, max(start[0], end[0]) + margin)
    min_y = max(0, min(start[1], end[1]) - margin)
    max_y = min(height - 1, max(start[1], end[1]) + margin)
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            t = ((x - start[0]) * dx + (y - start[1]) * dy) / length_sq
            t = min(1.0, max(0.0, t))
            nearest_x = start[0] + t * dx
            nearest_y = start[1] + t * dy
            distance = hypot(x - nearest_x, y - nearest_y)
            noisy_half = shallow_half * (1.0 + 0.10 * sin(t * 5.0 * pi + edge_phase))
            if distance <= noisy_half and island_mask_rows[y][x] == MASK_OUTSIDE:
                rows[y][x] = APPROACH_SHALLOW
            if distance <= path_half:
                rows[y][x] = APPROACH_PATH
    return rows
