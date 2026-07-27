from __future__ import annotations

from dataclasses import dataclass
from math import hypot
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
    solid_type_ids = {
        _NAME_TO_ID["ruin_wall"],
        _NAME_TO_ID["fortress_wall"],
        _NAME_TO_ID["fortress_tower"],
        _NAME_TO_ID["fortress_keep"],
        _NAME_TO_ID["fortress_building"],
        _NAME_TO_ID["building_wall"],
    }
    mask_rows = [
        [FULL_MICRO_MASK if value in solid_type_ids else 0 for value in row]
        for row in type_rows
    ]
    _overlay_fortress_wall_masks(
        type_rows=type_rows,
        mask_rows=mask_rows,
        fortress_plan=fortress_plan,
    )
    _overlay_round_tower_masks(
        type_rows=type_rows,
        mask_rows=mask_rows,
        fortress_plan=fortress_plan,
    )

    counts: dict[str, int] = {name: 0 for name in STRUCTURE_TYPE_NAMES.values()}
    full_micro_cells = 0
    partial_micro_cells = 0
    for y, row in enumerate(type_rows):
        for x, value in enumerate(row):
            counts[STRUCTURE_TYPE_NAMES[value]] += 1
            mask = mask_rows[y][x]
            if mask == FULL_MICRO_MASK:
                full_micro_cells += 1
            elif mask:
                partial_micro_cells += 1
    counts["micro_cells"] = full_micro_cells + partial_micro_cells
    counts["full_micro_cells"] = full_micro_cells
    counts["partial_micro_cells"] = partial_micro_cells
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


def _overlay_fortress_wall_masks(
    *,
    type_rows: list[list[int]],
    mask_rows: list[list[int]],
    fortress_plan: object | None,
) -> None:
    """Rasterize fortress wall center lines into 4x4 solid masks."""
    if not isinstance(fortress_plan, dict):
        return
    raw_segments = fortress_plan.get("segments")
    if not isinstance(raw_segments, list):
        return
    thickness = fortress_plan.get("wall_thickness_tiles", 3)
    if not isinstance(thickness, int):
        thickness = 3
    half_width = max(0.5, thickness / 2.0)
    segments = _parse_wall_segments(raw_segments)
    if not segments:
        return

    fortress_wall_id = _NAME_TO_ID["fortress_wall"]
    for y, row in enumerate(type_rows):
        for x, type_id in enumerate(row):
            if type_id != fortress_wall_id:
                continue
            mask = _wall_tile_mask(
                x=x,
                y=y,
                segments=segments,
                half_width=half_width,
            )
            if mask:
                mask_rows[y][x] = mask


def _parse_wall_segments(
    raw_segments: list[object],
) -> tuple[tuple[float, float, float, float], ...]:
    parsed: list[tuple[float, float, float, float]] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            continue
        values = (start.get("x"), start.get("y"), end.get("x"), end.get("y"))
        if not all(isinstance(value, int) for value in values):
            continue
        parsed.append(tuple(float(value) for value in values))
    return tuple(parsed)


def _wall_tile_mask(
    *,
    x: int,
    y: int,
    segments: tuple[tuple[float, float, float, float], ...],
    half_width: float,
) -> int:
    mask = 0
    for subtile_y in range(MICRO_DIVISION):
        for subtile_x in range(MICRO_DIVISION):
            sample_x = x - 0.5 + (subtile_x + 0.5) / MICRO_DIVISION
            sample_y = y - 0.5 + (subtile_y + 0.5) / MICRO_DIVISION
            if any(
                _point_segment_distance(sample_x, sample_y, *segment) <= half_width
                for segment in segments
            ):
                mask |= 1 << (subtile_y * MICRO_DIVISION + subtile_x)
    return mask


def _point_segment_distance(
    px: float,
    py: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> float:
    dx = x1 - x0
    dy = y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq <= 0.0:
        return hypot(px - x0, py - y0)
    t = ((px - x0) * dx + (py - y0) * dy) / length_sq
    t = min(1.0, max(0.0, t))
    nearest_x = x0 + t * dx
    nearest_y = y0 + t * dy
    return hypot(px - nearest_x, py - nearest_y)


def _overlay_round_tower_masks(
    *,
    type_rows: list[list[int]],
    mask_rows: list[list[int]],
    fortress_plan: object | None,
) -> None:
    """Replace full fortress-tower masks with sampled round wall masks."""
    if not isinstance(fortress_plan, dict):
        return
    towers = fortress_plan.get("towers")
    if not isinstance(towers, list):
        return

    wall_thickness_tiles = fortress_plan.get("wall_thickness_tiles", 3)
    if not isinstance(wall_thickness_tiles, int):
        wall_thickness_tiles = 3
    wall_radius = max(1, (wall_thickness_tiles - 1) // 2)
    parsed_towers = _parse_towers(towers, wall_radius=wall_radius)
    if not parsed_towers:
        return

    fortress_tower_id = _NAME_TO_ID["fortress_tower"]
    for y, row in enumerate(type_rows):
        for x, type_id in enumerate(row):
            if type_id != fortress_tower_id:
                continue
            mask = _round_tower_tile_mask(x=x, y=y, towers=parsed_towers)
            if mask:
                mask_rows[y][x] = mask


def _parse_towers(
    towers: list[object],
    *,
    wall_radius: int,
) -> tuple[tuple[float, float, float, float], ...]:
    parsed: list[tuple[float, float, float, float]] = []
    for item in towers:
        if not isinstance(item, dict):
            continue
        center = item.get("center")
        radius = item.get("radius_tiles")
        if not isinstance(center, dict) or not isinstance(radius, int):
            continue
        center_x = center.get("x")
        center_y = center.get("y")
        if not isinstance(center_x, int) or not isinstance(center_y, int):
            continue
        outer_radius = float(radius) + 0.35
        inner_radius = float(max(1, radius - wall_radius - 1))
        parsed.append((float(center_x), float(center_y), inner_radius, outer_radius))
    return tuple(parsed)


def _round_tower_tile_mask(
    *,
    x: int,
    y: int,
    towers: tuple[tuple[float, float, float, float], ...],
) -> int:
    mask = 0
    for subtile_y in range(MICRO_DIVISION):
        for subtile_x in range(MICRO_DIVISION):
            if _subtile_overlaps_tower_ring(
                tile_x=x,
                tile_y=y,
                subtile_x=subtile_x,
                subtile_y=subtile_y,
                towers=towers,
            ):
                bit_index = subtile_y * MICRO_DIVISION + subtile_x
                mask |= 1 << bit_index
    return mask


def _subtile_overlaps_tower_ring(
    *,
    tile_x: int,
    tile_y: int,
    subtile_x: int,
    subtile_y: int,
    towers: tuple[tuple[float, float, float, float], ...],
) -> bool:
    """Return whether sampled points in one subtile touch any tower ring."""
    base_x = tile_x - 0.5 + subtile_x / MICRO_DIVISION
    base_y = tile_y - 0.5 + subtile_y / MICRO_DIVISION
    sample_offsets = (0.125, 0.5, 0.875)
    for center_x, center_y, inner_radius, outer_radius in towers:
        for offset_y in sample_offsets:
            sample_y = base_y + offset_y / MICRO_DIVISION
            for offset_x in sample_offsets:
                sample_x = base_x + offset_x / MICRO_DIVISION
                distance = hypot(sample_x - center_x, sample_y - center_y)
                if inner_radius < distance <= outer_radius:
                    return True
    return False
