"""Deterministic derived layer for ruined structure heights."""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass

RUIN_FLOOR = "ruin_floor"
RUIN_WALL = "ruin_wall_blocker"
_MIN_HEIGHT = 1
_MAX_RUIN_HEIGHT = 3
_MAX_HEIGHT = 255
_NO_COMPONENT = -1
_NEIGHBORS: tuple[tuple[int, int], ...] = (
    (0, -1),
    (-1, 0),
    (1, 0),
    (0, 1),
)


@dataclass(frozen=True, slots=True)
class StructureHeightSummary:
    """Summary of one generated structure-height layer."""

    ruin_floor_tiles: int
    ruin_wall_tiles: int
    height_counts: tuple[int, ...]
    connected_wall_components: int
    average_wall_height: float
    maximum_adjacent_height_delta: int
    collision_mismatches: int
    architecture_planned_tiles: int
    legacy_fallback_tiles: int

    def to_dict(self) -> dict[str, int | float]:
        """Return a JSON-compatible summary.

        Returns:
            Stable summary dictionary.
        """
        return {
            "ruin_floor_tiles": self.ruin_floor_tiles,
            "ruin_wall_tiles": self.ruin_wall_tiles,
            **{f"height_{index}": count for index, count in enumerate(self.height_counts) if count},
            "connected_wall_components": self.connected_wall_components,
            "average_wall_height": round(self.average_wall_height, 6),
            "maximum_adjacent_height_delta": (
                self.maximum_adjacent_height_delta
            ),
            "invalid_wall_height_0": 0,
            "invalid_floor_height": 0,
            "invalid_non_ruin_height": 0,
            "collision_mismatches": self.collision_mismatches,
            "architecture_planned_tiles": self.architecture_planned_tiles,
            "legacy_fallback_tiles": self.legacy_fallback_tiles,
        }


@dataclass(frozen=True, slots=True)
class StructureHeightResult:
    """Generated structure-height grid and its validation summary."""

    rows: list[list[int]]
    summary: StructureHeightSummary


def build_structure_height(
    *,
    terrain_rows: list[list[str]],
    collision_rows: list[str],
    resolved_seed: int,
    ruin_sites: object | None = None,
    fortress_plan: object | None = None,
    structure_type_rows: list[list[int]] | None = None,
    elevation_rows: list[list[int]] | None = None,
) -> StructureHeightResult:
    """Build deterministic ruined-wall heights from final terrain.

    Heights are logical levels above the top surface of the ground. The
    function never changes terrain, collision, or any other runtime grid.

    Args:
        terrain_rows: Final terrain type grid.
        collision_rows: Final zero/one collision rows.
        resolved_seed: Concrete generation seed.
        ruin_sites: Optional semantic architecture metadata.
        fortress_plan: Optional fortress shell metadata.
        structure_type_rows: Optional final semantic structure type grid.
        elevation_rows: Optional final elevation grid used to flatten wall tops.

    Returns:
        Generated height rows and validation summary.

    Raises:
        ValueError: If grid dimensions are invalid or a ruin wall is passable.
    """
    height = len(terrain_rows)
    if height == 0:
        raise ValueError("structure-height terrain grid must not be empty")
    width = len(terrain_rows[0])
    if width == 0 or any(len(row) != width for row in terrain_rows):
        raise ValueError("structure-height terrain rows have invalid dimensions")
    if len(collision_rows) != height or any(
        len(row) != width or set(row) - {"0", "1"}
        for row in collision_rows
    ):
        raise ValueError("structure-height collision rows have invalid dimensions")
    if structure_type_rows is not None and (
        len(structure_type_rows) != height
        or any(len(row) != width for row in structure_type_rows)
    ):
        raise ValueError("structure-height type rows have invalid dimensions")
    if elevation_rows is not None and (
        len(elevation_rows) != height
        or any(len(row) != width for row in elevation_rows)
    ):
        raise ValueError("structure-height elevation rows have invalid dimensions")

    rows = [[0 for _ in range(width)] for _ in range(height)]
    component_ids = [[_NO_COMPONENT for _ in range(width)] for _ in range(height)]
    components = _find_components(terrain_rows, component_ids)
    planned_heights = _planned_architecture_heights(ruin_sites)
    fortress_heights = _fortress_structure_heights(fortress_plan)

    for component_id, component in enumerate(components):
        _assign_component_heights(
            rows=rows,
            component_ids=component_ids,
            component_id=component_id,
            component=component,
            resolved_seed=resolved_seed,
        )
    architecture_planned_tiles = 0
    for (x, y), value in planned_heights.items():
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError("planned structure height is outside the map")
        if terrain_rows[y][x] != RUIN_WALL:
            raise ValueError("planned structure height does not reference a ruin wall")
        if not _MIN_HEIGHT <= value <= _MAX_RUIN_HEIGHT:
            raise ValueError("planned structure height is outside the supported range")
        rows[y][x] = value
        architecture_planned_tiles += 1
    for (x, y), value in fortress_heights.items():
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError("fortress structure height is outside the map")
        if not _MIN_HEIGHT <= value <= _MAX_HEIGHT:
            raise ValueError("fortress structure height is outside uint8 range")
        rows[y][x] = value

    architecture_tiles: set[tuple[int, int]] = set()
    if structure_type_rows is not None:
        architecture_tiles = _apply_final_fortress_heights(
            rows=rows,
            structure_type_rows=structure_type_rows,
            elevation_rows=elevation_rows,
        )
        _clear_stale_structure_heights(
            rows=rows,
            structure_type_rows=structure_type_rows,
        )

    _validate_invariants(
        terrain_rows,
        collision_rows,
        rows,
        architecture_tiles=architecture_tiles,
        structure_type_rows=structure_type_rows,
    )
    summary = _build_summary(
        terrain_rows=terrain_rows,
        collision_rows=collision_rows,
        rows=rows,
        component_ids=component_ids,
        component_count=len(components),
        architecture_planned_tiles=architecture_planned_tiles,
    )
    return StructureHeightResult(rows=rows, summary=summary)


def _planned_architecture_heights(ruin_sites: object | None) -> dict[tuple[int, int], int]:
    """Return explicit wall heights stored by architecture planning."""
    if not isinstance(ruin_sites, dict):
        return {}
    sites = ruin_sites.get("sites")
    if not isinstance(sites, list):
        return {}
    output: dict[tuple[int, int], int] = {}
    for site in sites:
        if not isinstance(site, dict):
            continue
        buildings = site.get("buildings")
        if not isinstance(buildings, list):
            continue
        for building in buildings:
            if not isinstance(building, dict):
                continue
            architecture = building.get("architecture")
            if not isinstance(architecture, dict):
                continue
            wall_heights = architecture.get("wall_heights")
            if not isinstance(wall_heights, list):
                continue
            for item in wall_heights:
                if not isinstance(item, list) or len(item) != 3:
                    raise ValueError("invalid planned structure-height entry")
                x, y, value = item
                if not all(isinstance(part, int) for part in (x, y, value)):
                    raise ValueError("invalid planned structure-height value")
                point = (x, y)
                existing = output.get(point)
                if existing is not None and existing != value:
                    raise ValueError("conflicting planned structure heights")
                output[point] = value
    return output



def _fortress_structure_heights(fortress_plan: object | None) -> dict[tuple[int, int], int]:
    """Return explicit fortress shell heights from materialization metadata."""
    if not isinstance(fortress_plan, dict):
        return {}
    materialization = fortress_plan.get("materialization")
    if not isinstance(materialization, dict):
        return {}
    entries = materialization.get("structure_heights")
    if not isinstance(entries, list):
        return {}
    output: dict[tuple[int, int], int] = {}
    for item in entries:
        if not isinstance(item, list) or len(item) != 3:
            raise ValueError("invalid fortress structure-height entry")
        x, y, value = item
        if not all(isinstance(part, int) for part in (x, y, value)):
            raise ValueError("invalid fortress structure-height value")
        output[(x, y)] = value
    return output

def _apply_final_fortress_heights(
    *,
    rows: list[list[int]],
    structure_type_rows: list[list[int]],
    elevation_rows: list[list[int]] | None,
) -> set[tuple[int, int]]:
    """Apply final shell heights to every tile touched by micro geometry."""
    wall_type = 10
    tower_type = 11
    keep_type = 13
    architecture_tiles = {
        (x, y)
        for y, row in enumerate(structure_type_rows)
        for x, value in enumerate(row)
        if value in {wall_type, tower_type, keep_type}
    }
    wall_tiles = {
        (x, y)
        for x, y in architecture_tiles
        if structure_type_rows[y][x] == wall_type
    }
    if wall_tiles:
        if elevation_rows is None:
            for x, y in wall_tiles:
                rows[y][x] = 6
        else:
            wall_top = max(elevation_rows[y][x] + 1 + 6 for x, y in wall_tiles)
            for x, y in wall_tiles:
                rows[y][x] = max(1, min(_MAX_HEIGHT, wall_top - elevation_rows[y][x] - 1))
    tower_tiles = {
        point for point in architecture_tiles
        if structure_type_rows[point[1]][point[0]] == tower_type
    }
    keep_tiles = architecture_tiles - wall_tiles - tower_tiles
    _flatten_fortress_tower_tops(
        rows=rows,
        tower_tiles=tower_tiles,
        elevation_rows=elevation_rows,
    )
    _flatten_fortress_tower_tops(
        rows=rows,
        tower_tiles=keep_tiles,
        elevation_rows=elevation_rows,
    )
    return architecture_tiles


def _flatten_fortress_tower_tops(
    *,
    rows: list[list[int]],
    tower_tiles: set[tuple[int, int]],
    elevation_rows: list[list[int]] | None,
) -> None:
    """Give every connected tower one sealed, level top surface."""
    remaining = set(tower_tiles)
    while remaining:
        start = min(remaining, key=lambda point: (point[1], point[0]))
        queue: deque[tuple[int, int]] = deque([start])
        remaining.remove(start)
        component: list[tuple[int, int]] = []
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for delta_x, delta_y in _NEIGHBORS:
                neighbor = (x + delta_x, y + delta_y)
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)

        if elevation_rows is None:
            target_height = max(10, max((rows[y][x] for x, y in component), default=0))
            for x, y in component:
                rows[y][x] = target_height
            continue

        absolute_top = max(
            elevation_rows[y][x] + 1 + max(10, rows[y][x])
            for x, y in component
        )
        for x, y in component:
            rows[y][x] = max(
                1,
                min(_MAX_HEIGHT, absolute_top - elevation_rows[y][x] - 1),
            )


def _clear_stale_structure_heights(
    *,
    rows: list[list[int]],
    structure_type_rows: list[list[int]],
) -> None:
    """Clear heights left behind by superseded coarse structure plans."""
    solid_structure_types = {1, 10, 11, 13, 14, 20}
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            if value and structure_type_rows[y][x] not in solid_structure_types:
                rows[y][x] = 0


def _find_components(
    terrain_rows: list[list[str]],
    component_ids: list[list[int]],
) -> list[list[tuple[int, int]]]:
    height = len(terrain_rows)
    width = len(terrain_rows[0])
    components: list[list[tuple[int, int]]] = []
    for y in range(height):
        for x in range(width):
            if terrain_rows[y][x] != RUIN_WALL:
                continue
            if component_ids[y][x] != _NO_COMPONENT:
                continue
            component_id = len(components)
            queue: deque[tuple[int, int]] = deque([(x, y)])
            component_ids[y][x] = component_id
            component: list[tuple[int, int]] = []
            while queue:
                current_x, current_y = queue.popleft()
                component.append((current_x, current_y))
                for delta_x, delta_y in _NEIGHBORS:
                    neighbor_x = current_x + delta_x
                    neighbor_y = current_y + delta_y
                    if not 0 <= neighbor_x < width or not 0 <= neighbor_y < height:
                        continue
                    if terrain_rows[neighbor_y][neighbor_x] != RUIN_WALL:
                        continue
                    if component_ids[neighbor_y][neighbor_x] != _NO_COMPONENT:
                        continue
                    component_ids[neighbor_y][neighbor_x] = component_id
                    queue.append((neighbor_x, neighbor_y))
            components.append(component)
    return components


def _assign_component_heights(
    *,
    rows: list[list[int]],
    component_ids: list[list[int]],
    component_id: int,
    component: list[tuple[int, int]],
    resolved_seed: int,
) -> None:
    component_roll = _stable_hash(
        resolved_seed,
        component_id,
        0,
        0,
        "component_base",
    ) % 100
    base_height = 3 if component_roll < 35 else 2
    endpoint_targets: dict[tuple[int, int], int] = {}

    if len(component) == 1:
        x, y = component[0]
        roll = _stable_hash(
            resolved_seed,
            component_id,
            x,
            y,
            "singleton_height",
        ) % 100
        rows[y][x] = 1 if roll < 30 else 2 if roll < 80 else 3
        return

    for x, y in component:
        neighbor_count = _component_neighbors(component_ids, component_id, x, y)
        if neighbor_count <= 1:
            roll = _stable_hash(
                resolved_seed,
                component_id,
                x,
                y,
                "endpoint_height",
            ) % 100
            if base_height == 3:
                endpoint_height = 1 if roll < 15 else 2
            else:
                endpoint_height = 1 if roll < 65 else 2
            endpoint_targets[(x, y)] = endpoint_height
            rows[y][x] = endpoint_height
            continue
        coarse_x = x // 5
        coarse_y = y // 5
        roll = _stable_hash(
            resolved_seed,
            component_id,
            coarse_x,
            coarse_y,
            "ruin_structure_height_v1",
        ) % 100
        delta = -1 if roll < 24 else 1 if roll >= 82 else 0
        rows[y][x] = max(_MIN_HEIGHT, min(_MAX_RUIN_HEIGHT, base_height + delta))

    for _ in range(2):
        updated = [row[:] for row in rows]
        for x, y in component:
            endpoint_height = endpoint_targets.get((x, y))
            if endpoint_height is not None:
                updated[y][x] = endpoint_height
                continue
            neighbors = _neighbor_heights(rows, component_ids, component_id, x, y)
            if not neighbors:
                continue
            lower = min(neighbors)
            upper = max(neighbors)
            value = rows[y][x]
            if value >= upper + 2:
                value = upper + 1
            elif value <= lower - 2:
                value = lower - 1
            if all(neighbor < value for neighbor in neighbors):
                value = max(_MIN_HEIGHT, value - 1)
            elif all(neighbor > value for neighbor in neighbors):
                value = min(_MAX_RUIN_HEIGHT, value + 1)
            updated[y][x] = max(_MIN_HEIGHT, min(_MAX_RUIN_HEIGHT, value))
        rows[:] = updated

    for x, y in component:
        for delta_x, delta_y in ((1, 0), (0, 1)):
            neighbor_x = x + delta_x
            neighbor_y = y + delta_y
            if not _same_component(
                component_ids,
                component_id,
                neighbor_x,
                neighbor_y,
            ):
                continue
            left = rows[y][x]
            right = rows[neighbor_y][neighbor_x]
            if left > right + 1:
                rows[y][x] = right + 1
            elif right > left + 1:
                rows[neighbor_y][neighbor_x] = left + 1

    for (x, y), endpoint_height in endpoint_targets.items():
        rows[y][x] = endpoint_height
        for delta_x, delta_y in _NEIGHBORS:
            neighbor_x = x + delta_x
            neighbor_y = y + delta_y
            if not _same_component(
                component_ids,
                component_id,
                neighbor_x,
                neighbor_y,
            ):
                continue
            maximum_neighbor = endpoint_height + 1
            if rows[neighbor_y][neighbor_x] > maximum_neighbor:
                rows[neighbor_y][neighbor_x] = maximum_neighbor


def _stable_hash(
    resolved_seed: int,
    component_id: int,
    x: int,
    y: int,
    salt: str,
) -> int:
    payload = (
        f"{resolved_seed}:{component_id}:{x}:{y}:{salt}".encode("utf-8")
    )
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "little")


def _component_neighbors(
    component_ids: list[list[int]],
    component_id: int,
    x: int,
    y: int,
) -> int:
    return sum(
        _same_component(component_ids, component_id, x + delta_x, y + delta_y)
        for delta_x, delta_y in _NEIGHBORS
    )


def _neighbor_heights(
    rows: list[list[int]],
    component_ids: list[list[int]],
    component_id: int,
    x: int,
    y: int,
) -> list[int]:
    return [
        rows[y + delta_y][x + delta_x]
        for delta_x, delta_y in _NEIGHBORS
        if _same_component(
            component_ids,
            component_id,
            x + delta_x,
            y + delta_y,
        )
    ]


def _same_component(
    component_ids: list[list[int]],
    component_id: int,
    x: int,
    y: int,
) -> bool:
    return (
        0 <= y < len(component_ids)
        and 0 <= x < len(component_ids[0])
        and component_ids[y][x] == component_id
    )


def _validate_invariants(
    terrain_rows: list[list[str]],
    collision_rows: list[str],
    rows: list[list[int]],
    *,
    architecture_tiles: set[tuple[int, int]] | None = None,
    structure_type_rows: list[list[int]] | None = None,
) -> None:
    architecture_tiles = architecture_tiles or set()
    solid_structure_types = {1, 10, 11, 13, 14, 20}
    for y, terrain_row in enumerate(terrain_rows):
        for x, terrain in enumerate(terrain_row):
            value = rows[y][x]
            if not 0 <= value <= _MAX_HEIGHT:
                raise ValueError("structure height is outside the uint8 contract")

            if structure_type_rows is not None:
                structure_type = structure_type_rows[y][x]
                if structure_type in solid_structure_types:
                    if not _MIN_HEIGHT <= value <= _MAX_HEIGHT:
                        raise ValueError("solid structure has no visible height")
                elif value != 0:
                    raise ValueError("non-solid structure has a non-zero height")
                if structure_type == 1 and collision_rows[y][x] != "1":
                    raise ValueError("ruin wall is not blocked in collision grid")
                continue

            if terrain == RUIN_WALL:
                if not _MIN_HEIGHT <= value <= _MAX_HEIGHT:
                    raise ValueError("ruin wall has no visible structure height")
                if collision_rows[y][x] != "1":
                    raise ValueError("ruin wall is not blocked in collision grid")
            elif value != 0 and (x, y) not in architecture_tiles:
                raise ValueError("non-wall tile has a non-zero structure height")


def _build_summary(
    *,
    terrain_rows: list[list[str]],
    collision_rows: list[str],
    rows: list[list[int]],
    component_ids: list[list[int]],
    component_count: int,
    architecture_planned_tiles: int,
) -> StructureHeightSummary:
    counts = [0 for _ in range(_MAX_HEIGHT + 1)]
    ruin_floor_tiles = 0
    ruin_wall_tiles = 0
    wall_height_total = 0
    maximum_delta = 0
    collision_mismatches = 0
    for y, terrain_row in enumerate(terrain_rows):
        for x, terrain in enumerate(terrain_row):
            value = rows[y][x]
            counts[value] += 1
            if terrain == RUIN_FLOOR:
                ruin_floor_tiles += 1
            if terrain != RUIN_WALL:
                continue
            ruin_wall_tiles += 1
            wall_height_total += value
            if collision_rows[y][x] != "1":
                collision_mismatches += 1
            component_id = component_ids[y][x]
            for delta_x, delta_y in ((1, 0), (0, 1)):
                neighbor_x = x + delta_x
                neighbor_y = y + delta_y
                if _same_component(
                    component_ids,
                    component_id,
                    neighbor_x,
                    neighbor_y,
                ):
                    maximum_delta = max(
                        maximum_delta,
                        abs(value - rows[neighbor_y][neighbor_x]),
                    )
    average = wall_height_total / ruin_wall_tiles if ruin_wall_tiles else 0.0
    return StructureHeightSummary(
        ruin_floor_tiles=ruin_floor_tiles,
        ruin_wall_tiles=ruin_wall_tiles,
        height_counts=(counts[0], counts[1], counts[2], counts[3]),
        connected_wall_components=component_count,
        average_wall_height=average,
        maximum_adjacent_height_delta=maximum_delta,
        collision_mismatches=collision_mismatches,
        architecture_planned_tiles=architecture_planned_tiles,
        legacy_fallback_tiles=max(0, ruin_wall_tiles - architecture_planned_tiles),
    )
