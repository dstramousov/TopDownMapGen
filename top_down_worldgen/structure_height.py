"""Deterministic derived layer for ruined structure heights."""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass

RUIN_FLOOR = "ruin_floor"
RUIN_WALL = "ruin_wall_blocker"
_MIN_HEIGHT = 1
_MAX_HEIGHT = 3
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
    height_counts: tuple[int, int, int, int]
    connected_wall_components: int
    average_wall_height: float
    maximum_adjacent_height_delta: int
    collision_mismatches: int

    def to_dict(self) -> dict[str, int | float]:
        """Return a JSON-compatible summary.

        Returns:
            Stable summary dictionary.
        """
        return {
            "ruin_floor_tiles": self.ruin_floor_tiles,
            "ruin_wall_tiles": self.ruin_wall_tiles,
            "height_0": self.height_counts[0],
            "height_1": self.height_counts[1],
            "height_2": self.height_counts[2],
            "height_3": self.height_counts[3],
            "connected_wall_components": self.connected_wall_components,
            "average_wall_height": round(self.average_wall_height, 6),
            "maximum_adjacent_height_delta": (
                self.maximum_adjacent_height_delta
            ),
            "invalid_wall_height_0": 0,
            "invalid_floor_height": 0,
            "invalid_non_ruin_height": 0,
            "collision_mismatches": self.collision_mismatches,
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
) -> StructureHeightResult:
    """Build deterministic ruined-wall heights from final terrain.

    Heights are logical levels above the top surface of the ground. The
    function never changes terrain, collision, or any other runtime grid.

    Args:
        terrain_rows: Final terrain type grid.
        collision_rows: Final zero/one collision rows.
        resolved_seed: Concrete generation seed.

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

    rows = [[0 for _ in range(width)] for _ in range(height)]
    component_ids = [[_NO_COMPONENT for _ in range(width)] for _ in range(height)]
    components = _find_components(terrain_rows, component_ids)

    for component_id, component in enumerate(components):
        _assign_component_heights(
            rows=rows,
            component_ids=component_ids,
            component_id=component_id,
            component=component,
            resolved_seed=resolved_seed,
        )

    _validate_invariants(terrain_rows, collision_rows, rows)
    summary = _build_summary(
        terrain_rows=terrain_rows,
        collision_rows=collision_rows,
        rows=rows,
        component_ids=component_ids,
        component_count=len(components),
    )
    return StructureHeightResult(rows=rows, summary=summary)


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
        rows[y][x] = max(_MIN_HEIGHT, min(_MAX_HEIGHT, base_height + delta))

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
                value = min(_MAX_HEIGHT, value + 1)
            updated[y][x] = max(_MIN_HEIGHT, min(_MAX_HEIGHT, value))
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
) -> None:
    for y, terrain_row in enumerate(terrain_rows):
        for x, terrain in enumerate(terrain_row):
            value = rows[y][x]
            if not 0 <= value <= _MAX_HEIGHT:
                raise ValueError("structure height is outside the uint8 contract")
            if terrain == RUIN_WALL:
                if not _MIN_HEIGHT <= value <= _MAX_HEIGHT:
                    raise ValueError("ruin wall has no visible structure height")
                if collision_rows[y][x] != "1":
                    raise ValueError("ruin wall is not blocked in collision grid")
            elif value != 0:
                raise ValueError("non-wall tile has a non-zero structure height")


def _build_summary(
    *,
    terrain_rows: list[list[str]],
    collision_rows: list[str],
    rows: list[list[int]],
    component_ids: list[list[int]],
    component_count: int,
) -> StructureHeightSummary:
    counts = [0, 0, 0, 0]
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
    )
