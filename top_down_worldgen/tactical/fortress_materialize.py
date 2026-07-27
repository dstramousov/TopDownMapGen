from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fortress_plan import PLAN_GATE, PLAN_TOWER, PLAN_WALL

FORTRESS_WALL_HEIGHT = 6
FORTRESS_TOWER_HEIGHT = 10
FORTRESS_GATE_TOWER_HEIGHT = 11


@dataclass(frozen=True, slots=True)
class FortressMaterializationResult:
    """Materialized fortress shell and updated runtime metadata."""

    rows: list[str]
    runtime_data: dict[str, Any]
    site_report: dict[str, Any]
    wall_tiles: int
    tower_tiles: int
    gate_tiles: int


def materialize_fortress_shell(
    *,
    rows: list[str],
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    plan_rows: list[list[int]],
) -> FortressMaterializationResult:
    """Materialize planned walls, towers, and gate into the tile grid.

    The existing ruin wall/floor tile symbols are reused for the first
    fortress implementation. Explicit semantic metadata keeps fortress
    structure heights separate from procedural ruin heights.

    Args:
        rows: Current ASCII terrain rows.
        runtime_data: Tactical runtime data.
        site_report: Fortress site report.
        plan_rows: Fortress shell classification grid.

    Returns:
        Updated tile rows and fortress metadata.

    Raises:
        ValueError: If input grid dimensions are inconsistent.
    """
    if not plan_rows:
        return FortressMaterializationResult(
            rows=rows,
            runtime_data=runtime_data,
            site_report=site_report,
            wall_tiles=0,
            tower_tiles=0,
            gate_tiles=0,
        )
    height = len(rows)
    width = len(rows[0]) if rows else 0
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("Fortress materialization requires rectangular rows")
    if len(plan_rows) != height or any(len(row) != width for row in plan_rows):
        raise ValueError("Fortress plan dimensions do not match terrain rows")

    mutable_rows = [list(row) for row in rows]
    structure_heights: list[list[int]] = []
    wall_tiles = 0
    tower_tiles = 0
    gate_tiles = 0

    gate_tower_centers = _gate_tower_centers(site_report)
    for y, plan_row in enumerate(plan_rows):
        for x, value in enumerate(plan_row):
            if value == PLAN_WALL:
                mutable_rows[y][x] = "#"
                structure_heights.append([x, y, FORTRESS_WALL_HEIGHT])
                wall_tiles += 1
            elif value == PLAN_TOWER:
                mutable_rows[y][x] = "#"
                height_value = (
                    FORTRESS_GATE_TOWER_HEIGHT
                    if _is_gate_tower_tile(
                        x=x,
                        y=y,
                        gate_tower_centers=gate_tower_centers,
                    )
                    else FORTRESS_TOWER_HEIGHT
                )
                structure_heights.append([x, y, height_value])
                tower_tiles += 1
            elif value == PLAN_GATE:
                mutable_rows[y][x] = "R"
                gate_tiles += 1

    materialization = {
        "status": "materialized",
        "terrain_encoding": {
            "wall_and_tower": "ruin_wall_blocker",
            "gate": "ruin_floor",
        },
        "height_levels_above_ground": {
            "wall": FORTRESS_WALL_HEIGHT,
            "tower": FORTRESS_TOWER_HEIGHT,
            "gate_tower": FORTRESS_GATE_TOWER_HEIGHT,
        },
        "wall_tiles": wall_tiles,
        "tower_tiles": tower_tiles,
        "gate_tiles": gate_tiles,
        "structure_heights": structure_heights,
    }

    updated_site_report = dict(site_report)
    policy = dict(updated_site_report.get("policy", {}))
    policy["phase"] = "fortress_shell_materialized"
    updated_site_report["policy"] = policy
    plan_report = dict(updated_site_report.get("fortress_plan", {}))
    plan_report["materialized_to_terrain"] = True
    plan_report["materialization"] = materialization
    updated_site_report["fortress_plan"] = plan_report

    updated_runtime = dict(runtime_data)
    updated_runtime["fortress_site"] = updated_site_report
    updated_runtime["fortress_plan"] = plan_report

    return FortressMaterializationResult(
        rows=["".join(row) for row in mutable_rows],
        runtime_data=updated_runtime,
        site_report=updated_site_report,
        wall_tiles=wall_tiles,
        tower_tiles=tower_tiles,
        gate_tiles=gate_tiles,
    )



def _gate_tower_centers(site_report: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    plan = site_report.get("fortress_plan")
    if not isinstance(plan, dict):
        return ()
    raw_centers = plan.get("gate_tower_centers")
    if not isinstance(raw_centers, list):
        return ()
    centers: list[tuple[int, int]] = []
    for item in raw_centers:
        if not isinstance(item, dict):
            continue
        x = item.get("x")
        y = item.get("y")
        if isinstance(x, int) and isinstance(y, int):
            centers.append((x, y))
    return tuple(centers)


def _is_gate_tower_tile(
    *,
    x: int,
    y: int,
    gate_tower_centers: tuple[tuple[int, int], ...],
) -> bool:
    return any(
        (x - center_x) ** 2 + (y - center_y) ** 2 <= 8 ** 2
        for center_x, center_y in gate_tower_centers
    )
