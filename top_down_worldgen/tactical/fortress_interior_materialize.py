from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fortress_interior import (
    INTERIOR_HOUSE_FLOOR,
    INTERIOR_HOUSE_WALL,
    INTERIOR_KEEP_FLOOR,
    INTERIOR_KEEP_WALL,
    INTERIOR_NONE,
    INTERIOR_PATH,
    INTERIOR_TREE,
)

FORTRESS_KEEP_HEIGHT = 16
FORTRESS_HOUSE_HEIGHT = 4


@dataclass(frozen=True, slots=True)
class FortressInteriorMaterializationResult:
    """Materialized keep, houses, paths, and trees inside a fortress."""

    rows: list[str]
    runtime_data: dict[str, Any]
    site_report: dict[str, Any]
    keep_wall_tiles: int
    keep_floor_tiles: int
    house_wall_tiles: int
    house_floor_tiles: int
    path_tiles: int
    tree_tiles: int


def materialize_fortress_interior(
    *,
    rows: list[str],
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    interior_rows: list[list[int]],
) -> FortressInteriorMaterializationResult:
    """Apply the planned fortress interior to terrain and structure metadata."""
    if not interior_rows:
        return FortressInteriorMaterializationResult(
            rows=rows,
            runtime_data=runtime_data,
            site_report=site_report,
            keep_wall_tiles=0,
            keep_floor_tiles=0,
            house_wall_tiles=0,
            house_floor_tiles=0,
            path_tiles=0,
            tree_tiles=0,
        )

    height = len(rows)
    width = len(rows[0]) if rows else 0
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("Fortress interior materialization requires rectangular rows")
    if len(interior_rows) != height or any(len(row) != width for row in interior_rows):
        raise ValueError("Fortress interior dimensions do not match terrain rows")

    mutable_rows = [list(row) for row in rows]
    structure_heights: list[list[int]] = []
    structure_types: list[list[int | str]] = []
    counts = {
        INTERIOR_KEEP_WALL: 0,
        INTERIOR_KEEP_FLOOR: 0,
        INTERIOR_HOUSE_WALL: 0,
        INTERIOR_HOUSE_FLOOR: 0,
        INTERIOR_PATH: 0,
        INTERIOR_TREE: 0,
    }

    for y, interior_row in enumerate(interior_rows):
        for x, value in enumerate(interior_row):
            if value == INTERIOR_NONE:
                continue
            if value == INTERIOR_KEEP_WALL:
                mutable_rows[y][x] = "#"
                structure_heights.append([x, y, FORTRESS_KEEP_HEIGHT])
                structure_types.append([x, y, "fortress_keep"])
            elif value == INTERIOR_KEEP_FLOOR:
                mutable_rows[y][x] = "R"
                structure_types.append([x, y, "fortress_floor"])
            elif value == INTERIOR_HOUSE_WALL:
                mutable_rows[y][x] = "#"
                structure_heights.append([x, y, FORTRESS_HOUSE_HEIGHT])
                structure_types.append([x, y, "fortress_building"])
            elif value == INTERIOR_HOUSE_FLOOR:
                mutable_rows[y][x] = "R"
                structure_types.append([x, y, "fortress_floor"])
            elif value == INTERIOR_PATH:
                mutable_rows[y][x] = "R"
                structure_types.append([x, y, "fortress_floor"])
            elif value == INTERIOR_TREE:
                mutable_rows[y][x] = "T"
            else:
                raise ValueError(f"Unknown fortress interior value: {value}")
            counts[value] += 1

    updated_site_report = dict(site_report)
    plan_report = dict(updated_site_report.get("fortress_plan", {}))
    shell_materialization = dict(plan_report.get("materialization", {}))
    merged_heights = list(shell_materialization.get("structure_heights", []))
    merged_heights.extend(structure_heights)
    merged_types = list(shell_materialization.get("structure_types", []))
    merged_types.extend(structure_types)
    shell_materialization["structure_heights"] = merged_heights
    shell_materialization["structure_types"] = merged_types
    shell_materialization["interior"] = {
        "status": "materialized",
        "height_levels_above_ground": {
            "keep": FORTRESS_KEEP_HEIGHT,
            "house": FORTRESS_HOUSE_HEIGHT,
        },
        "keep_wall_tiles": counts[INTERIOR_KEEP_WALL],
        "keep_floor_tiles": counts[INTERIOR_KEEP_FLOOR],
        "house_wall_tiles": counts[INTERIOR_HOUSE_WALL],
        "house_floor_tiles": counts[INTERIOR_HOUSE_FLOOR],
        "path_tiles": counts[INTERIOR_PATH],
        "tree_tiles": counts[INTERIOR_TREE],
    }
    plan_report["materialization"] = shell_materialization
    updated_site_report["fortress_plan"] = plan_report

    interior_report = dict(updated_site_report.get("fortress_interior_plan", {}))
    interior_report["materialized_to_terrain"] = True
    interior_report["materialization"] = shell_materialization["interior"]
    updated_site_report["fortress_interior_plan"] = interior_report

    policy = dict(updated_site_report.get("policy", {}))
    policy["phase"] = "fortress_interior_materialized"
    updated_site_report["policy"] = policy

    updated_runtime = dict(runtime_data)
    updated_runtime["fortress_site"] = updated_site_report
    updated_runtime["fortress_plan"] = plan_report
    updated_runtime["fortress_interior_plan"] = interior_report

    return FortressInteriorMaterializationResult(
        rows=["".join(row) for row in mutable_rows],
        runtime_data=updated_runtime,
        site_report=updated_site_report,
        keep_wall_tiles=counts[INTERIOR_KEEP_WALL],
        keep_floor_tiles=counts[INTERIOR_KEEP_FLOOR],
        house_wall_tiles=counts[INTERIOR_HOUSE_WALL],
        house_floor_tiles=counts[INTERIOR_HOUSE_FLOOR],
        path_tiles=counts[INTERIOR_PATH],
        tree_tiles=counts[INTERIOR_TREE],
    )
