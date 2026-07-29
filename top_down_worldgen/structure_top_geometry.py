from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import atan2

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
    tower_components = _components(tower_points)
    tower_roof_components = [
        _fill_component_holes(component) for component in tower_components
    ]
    tower_roofs = set().union(*tower_roof_components) if tower_roof_components else set()
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

    tower_crenellations: set[tuple[int, int]] = set()
    tower_connection_clearance: set[tuple[int, int]] = set()
    for tower_roof in tower_roof_components:
        ring = _ordered_outer_ring(tower_roof)
        excluded = _connection_clearance_points(ring, wall_points)
        tower_connection_clearance.update(excluded)
        tower_crenellations.update(
            _select_grouped_crenellations(ring, excluded=excluded)
        )

    if top_surface:
        fortress_center = _point_centroid(top_surface)
        wall_outer_boundary = _outward_wall_boundary(
            wall_points=wall_points,
            top_surface=top_surface,
            fortress_center=fortress_center,
        )
    else:
        wall_outer_boundary = set()
    wall_crenellations: set[tuple[int, int]] = set()
    wall_connection_clearance = _points_near(wall_outer_boundary, tower_roofs)
    for component in _components(wall_outer_boundary):
        ordered = _ordered_boundary_component(component)
        wall_crenellations.update(
            _select_grouped_crenellations(
                ordered,
                excluded=wall_connection_clearance,
            )
        )
    crenellations = wall_crenellations | tower_crenellations

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
            "tower_crenellation_subtiles": len(tower_crenellations),
            "wall_crenellation_subtiles": len(wall_crenellations),
            "tower_connection_clearance_subtiles": len(
                tower_connection_clearance
            ),
            "wall_connection_clearance_subtiles": len(
                wall_connection_clearance
            ),
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




def _point_centroid(
    points: set[tuple[int, int]],
) -> tuple[float, float]:
    """Return the arithmetic center of a non-empty point set."""
    if not points:
        raise ValueError("Cannot calculate centroid of an empty point set")
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _outward_wall_boundary(
    *,
    wall_points: set[tuple[int, int]],
    top_surface: set[tuple[int, int]],
    fortress_center: tuple[float, float],
) -> set[tuple[int, int]]:
    """Return only wall-edge subtiles facing away from the fortress center."""
    center_x, center_y = fortress_center
    outward: set[tuple[int, int]] = set()
    for point in wall_points:
        point_distance = (point[0] - center_x) ** 2 + (point[1] - center_y) ** 2
        for dx, dy in _CARDINAL_NEIGHBORS:
            neighbor = (point[0] + dx, point[1] + dy)
            if neighbor in top_surface:
                continue
            neighbor_distance = (neighbor[0] - center_x) ** 2 + (
                neighbor[1] - center_y
            ) ** 2
            if neighbor_distance > point_distance:
                outward.add(point)
                break
    return outward

def _components(points: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    """Return deterministic cardinally connected point components."""
    components: list[set[tuple[int, int]]] = []
    remaining = set(points)
    while remaining:
        seed = min(remaining, key=lambda point: (point[1], point[0]))
        component = _flood_component(seed, remaining)
        remaining.difference_update(component)
        components.append(component)
    return components


def _ordered_outer_ring(points: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Return a clockwise outer boundary order for a round tower roof."""
    exterior = _exterior_empty_points(points)
    boundary = [
        point
        for point in points
        if any(
            (point[0] + dx, point[1] + dy) in exterior
            for dx, dy in _CARDINAL_NEIGHBORS
        )
    ]
    if not boundary:
        return []

    center_x = sum(point[0] for point in points) / len(points)
    center_y = sum(point[1] for point in points) / len(points)
    return sorted(
        boundary,
        key=lambda point: (
            atan2(point[1] - center_y, point[0] - center_x),
            (point[0] - center_x) ** 2 + (point[1] - center_y) ** 2,
        ),
    )


def _select_grouped_crenellations(
    ordered_points: list[tuple[int, int]],
    *,
    excluded: set[tuple[int, int]],
    merlon_run: int = 2,
    gap_run: int = 2,
) -> set[tuple[int, int]]:
    """Select grouped merlons from an ordered defensive edge."""
    if merlon_run <= 0 or gap_run <= 0:
        raise ValueError("merlon and gap runs must be positive")
    period = merlon_run + gap_run
    return {
        point
        for index, point in enumerate(ordered_points)
        if index % period < merlon_run and point not in excluded
    }


def _connection_clearance_points(
    ring: list[tuple[int, int]],
    wall_points: set[tuple[int, int]],
    *,
    radius: int = 2,
) -> set[tuple[int, int]]:
    """Return ring points reserved for wall-to-tower walkway openings."""
    if not ring or not wall_points:
        return set()
    contact_indexes = [
        index
        for index, point in enumerate(ring)
        if _has_nearby_point(point, wall_points, distance=1)
    ]
    excluded: set[tuple[int, int]] = set()
    ring_size = len(ring)
    for index in contact_indexes:
        for offset in range(-radius, radius + 1):
            excluded.add(ring[(index + offset) % ring_size])
    return excluded


def _points_near(
    points: set[tuple[int, int]],
    targets: set[tuple[int, int]],
    *,
    distance: int = 1,
) -> set[tuple[int, int]]:
    """Return points within Chebyshev distance of any target point."""
    if not points or not targets:
        return set()
    return {
        point
        for point in points
        if _has_nearby_point(point, targets, distance=distance)
    }


def _has_nearby_point(
    point: tuple[int, int],
    targets: set[tuple[int, int]],
    *,
    distance: int,
) -> bool:
    """Return whether a target exists within the requested square radius."""
    x, y = point
    return any(
        (x + dx, y + dy) in targets
        for dy in range(-distance, distance + 1)
        for dx in range(-distance, distance + 1)
    )


def _ordered_boundary_component(
    points: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Return a deterministic path-like order for one wall-edge component."""
    if not points:
        return []
    neighbors = {
        point: sorted(
            (
                (point[0] + dx, point[1] + dy)
                for dx, dy in _CARDINAL_NEIGHBORS
                if (point[0] + dx, point[1] + dy) in points
            ),
            key=lambda value: (value[1], value[0]),
        )
        for point in points
    }
    endpoints = [point for point, adjacent in neighbors.items() if len(adjacent) == 1]
    if endpoints and all(len(adjacent) <= 2 for adjacent in neighbors.values()):
        current = min(endpoints, key=lambda point: (point[1], point[0]))
        previous: tuple[int, int] | None = None
        ordered: list[tuple[int, int]] = []
        while current is not None:
            ordered.append(current)
            candidates = [
                neighbor
                for neighbor in neighbors[current]
                if neighbor != previous
            ]
            next_point = candidates[0] if candidates else None
            previous, current = current, next_point
        return ordered

    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    if max_x - min_x >= max_y - min_y:
        return sorted(points, key=lambda point: (point[0], point[1]))
    return sorted(points, key=lambda point: (point[1], point[0]))

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
