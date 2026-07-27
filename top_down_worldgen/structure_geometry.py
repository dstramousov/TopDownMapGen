from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MICRO_DIVISION = 4
FULL_MICRO_MASK = 0xFFFF

STRUCTURE_TYPE_NAMES: dict[int, str] = {
    0: "none",
    1: "ruin_wall",
    2: "ruin_floor",
    10: "fortress_wall",
    11: "fortress_tower",
    12: "fortress_gate",
    13: "fortress_keep",
    14: "fortress_building",
    15: "fortress_floor",
    20: "building_wall",
    21: "building_floor",
}

_NAME_TO_ID = {name: value for value, name in STRUCTURE_TYPE_NAMES.items()}


@dataclass(frozen=True, slots=True)
class StructureGeometry:
    """Logical structure classification and per-tile micro occupancy."""

    type_rows: list[list[int]]
    mask_rows: list[list[int]]
    summary: dict[str, int]


def build_structure_geometry(
    *,
    terrain_rows: list[list[str]],
    fortress_plan: object | None,
) -> StructureGeometry:
    """Build structure type and 4x4 occupancy layers from current map data."""
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if terrain_rows else 0
    if any(len(row) != width for row in terrain_rows):
        raise ValueError("Structure geometry requires rectangular terrain rows")

    type_rows = [[0 for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(terrain_rows):
        for x, terrain in enumerate(row):
            if terrain == "ruin_wall_blocker":
                type_rows[y][x] = _NAME_TO_ID["ruin_wall"]
            elif terrain == "ruin_floor":
                type_rows[y][x] = _NAME_TO_ID["ruin_floor"]

    _overlay_fortress_types(type_rows, fortress_plan)
    mask_rows = [
        [FULL_MICRO_MASK if value else 0 for value in row]
        for row in type_rows
    ]
    counts: dict[str, int] = {name: 0 for name in STRUCTURE_TYPE_NAMES.values()}
    for row in type_rows:
        for value in row:
            counts[STRUCTURE_TYPE_NAMES[value]] += 1
    counts["micro_cells"] = sum(value != 0 for row in type_rows for value in row)
    return StructureGeometry(type_rows=type_rows, mask_rows=mask_rows, summary=counts)


def sparse_micro_cells(geometry: StructureGeometry) -> list[dict[str, int]]:
    """Return non-empty micro masks in deterministic row-major order."""
    return [
        {"x": x, "y": y, "mask": mask}
        for y, row in enumerate(geometry.mask_rows)
        for x, mask in enumerate(row)
        if mask
    ]


def _overlay_fortress_types(
    type_rows: list[list[int]],
    fortress_plan: object | None,
) -> None:
    if not isinstance(fortress_plan, dict):
        return
    materialization = fortress_plan.get("materialization")
    if not isinstance(materialization, dict):
        return
    entries = materialization.get("structure_types")
    if not isinstance(entries, list):
        return
    height = len(type_rows)
    width = len(type_rows[0]) if type_rows else 0
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 3:
            continue
        x, y, name = entry
        if not isinstance(x, int) or not isinstance(y, int) or not isinstance(name, str):
            continue
        type_id = _NAME_TO_ID.get(name)
        if type_id is None:
            continue
        if 0 <= x < width and 0 <= y < height:
            type_rows[y][x] = type_id
