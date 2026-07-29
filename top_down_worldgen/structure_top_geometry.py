from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .structure_geometry import MICRO_DIVISION, STRUCTURE_TYPE_NAMES, StructureGeometry

_NAME_TO_ID = {name: value for value, name in STRUCTURE_TYPE_NAMES.items()}
_CARDINAL_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass(frozen=True, slots=True)
class StructureTopGeometry:
    """Top-surface masks for fortress walkways and defensive edges."""

    walkway_rows: list[list[int]]
    parapet_rows: list[list[int]]
    crenellation_rows: list[list[int]]
    summary: dict[str, int]


def build_structure_top_geometry(
    geometry: StructureGeometry,
) -> StructureTopGeometry:
    """Build fortress roof, inner parapet, and outer crenellation masks."""
    height = len(geometry.type_rows)
    width = len(geometry.type_rows[0]) if geometry.type_rows else 0
    walkway_rows = [[0 for _ in range(width)] for _ in range(height)]
    parapet_rows = [[0 for _ in range(width)] for _ in range(height)]
    crenellation_rows = [[0 for _ in range(width)] for _ in range(height)]

    wall_id = _NAME_TO_ID["fortress_wall"]
    tower_id = _NAME_TO_ID["fortress_tower"]
    wall_points = _collect_points(geometry, {wall_id})
    tower_points = _collect_points(geometry, {tower_id})
    tower_roofs = _fill_component_holes(tower_points)
    top_surface = wall_points | tower_roofs

    exterior = _exterior_empty_points(top_surface)
    outer_boundary = {
        point
        for point in top_surface
        if any(
            (point[0] + dx, point[1] + dy) in exterior
            for dx, dy in _CARDINAL_NEIGHBORS
        )
    }
    inner_boundary = {
        point
        for point in top_surface
        if any(
            (point[0] + dx, point[1] + dy) not in top_surface
            and (point[0] + dx, point[1] + dy) not in exterior
            for dx, dy in _CARDINAL_NEIGHBORS
        )
    }
    crenellations = {
        point for point in outer_boundary if (point[0] + point[1]) % 2 == 0
    }

    _pack_points(top_surface, walkway_rows)
    _pack_points(inner_boundary, parapet_rows)
    _pack_points(crenellations, crenellation_rows)
    return StructureTopGeometry(
        walkway_rows=walkway_rows,
        parapet_rows=parapet_rows,
        crenellation_rows=crenellation_rows,
        summary={
            "walkway_subtiles": len(top_surface),
            "parapet_subtiles": len(inner_boundary),
            "crenellation_subtiles": len(crenellations),
            "walkway_cells": sum(bool(mask) for row in walkway_rows for mask in row),
            "parapet_cells": sum(bool(mask) for row in parapet_rows for mask in row),
            "crenellation_cells": sum(
                bool(mask) for row in crenellation_rows for mask in row
            ),
            "tower_roof_subtiles": len(tower_roofs),
        },
    )


def sparse_top_cells(top: StructureTopGeometry) -> list[dict[str, int]]:
    """Return sparse top-profile cells in deterministic row-major order."""
    return [
        {
            "x": x,
            "y": y,
            "walkway_mask": top.walkway_rows[y][x],
            "parapet_mask": top.parapet_rows[y][x],
            "crenellation_mask": top.crenellation_rows[y][x],
        }
        for y, row in enumerate(top.walkway_rows)
        for x, _mask in enumerate(row)
        if (
            top.walkway_rows[y][x]
            or top.parapet_rows[y][x]
            or top.crenellation_rows[y][x]
        )
    ]


def _collect_points(
    geometry: StructureGeometry,
    type_ids: set[int],
) -> set[tuple[int, int]]:
    points: set[tuple[int, int]] = set()
    for tile_y, row in enumerate(geometry.type_rows):
        for tile_x, type_id in enumerate(row):
            if type_id not in type_ids:
                continue
            mask = geometry.mask_rows[tile_y][tile_x]
            for subtile_y in range(MICRO_DIVISION):
                for subtile_x in range(MICRO_DIVISION):
                    bit = subtile_y * MICRO_DIVISION + subtile_x
                    if mask & (1 << bit):
                        points.add(
                            (
                                tile_x * MICRO_DIVISION + subtile_x,
                                tile_y * MICRO_DIVISION + subtile_y,
                            )
                        )
    return points


def _fill_component_holes(points: set[tuple[int, int]]) -> set[tuple[int, int]]:
    filled = set(points)
    remaining = set(points)
    while remaining:
        seed = min(remaining, key=lambda point: (point[1], point[0]))
        component = _flood_component(seed, remaining)
        remaining.difference_update(component)
        min_x = min(point[0] for point in component) - 1
        max_x = max(point[0] for point in component) + 1
        min_y = min(point[1] for point in component) - 1
        max_y = max(point[1] for point in component) + 1
        exterior = _flood_empty_box(component, min_x, max_x, min_y, max_y)
        for y in range(min_y + 1, max_y):
            for x in range(min_x + 1, max_x):
                point = (x, y)
                if point not in component and point not in exterior:
                    filled.add(point)
    return filled


def _flood_component(
    seed: tuple[int, int],
    points: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    component = {seed}
    queue = deque([seed])
    while queue:
        x, y = queue.popleft()
        for dx, dy in _CARDINAL_NEIGHBORS:
            neighbor = (x + dx, y + dy)
            if neighbor in points and neighbor not in component:
                component.add(neighbor)
                queue.append(neighbor)
    return component


def _flood_empty_box(
    occupied: set[tuple[int, int]],
    min_x: int,
    max_x: int,
    min_y: int,
    max_y: int,
) -> set[tuple[int, int]]:
    seed = (min_x, min_y)
    exterior = {seed}
    queue = deque([seed])
    while queue:
        x, y = queue.popleft()
        for dx, dy in _CARDINAL_NEIGHBORS:
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor
            if not (min_x <= nx <= max_x and min_y <= ny <= max_y):
                continue
            if neighbor in occupied or neighbor in exterior:
                continue
            exterior.add(neighbor)
            queue.append(neighbor)
    return exterior


def _exterior_empty_points(
    occupied: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    if not occupied:
        return set()
    min_x = min(point[0] for point in occupied) - 1
    max_x = max(point[0] for point in occupied) + 1
    min_y = min(point[1] for point in occupied) - 1
    max_y = max(point[1] for point in occupied) + 1
    return _flood_empty_box(occupied, min_x, max_x, min_y, max_y)


def _pack_points(points: set[tuple[int, int]], rows: list[list[int]]) -> None:
    for micro_x, micro_y in points:
        tile_x, subtile_x = divmod(micro_x, MICRO_DIVISION)
        tile_y, subtile_y = divmod(micro_y, MICRO_DIVISION)
        if 0 <= tile_y < len(rows) and 0 <= tile_x < len(rows[tile_y]):
            rows[tile_y][tile_x] |= 1 << (
                subtile_y * MICRO_DIVISION + subtile_x
            )
