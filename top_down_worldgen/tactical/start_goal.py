from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random
from typing import Any, Iterable

from .traversal import DEFAULT_TRAVERSAL_RULES

WALKABLE_SYMBOLS: frozenset[str] = frozenset("+.bfmwcRSG")
DRY_WALKABLE_SYMBOLS: frozenset[str] = frozenset("+.bfmcRSG")
DEEP_WATER_TILE = "~"
WET_SHORE_TILE = "w"


@dataclass(frozen=True, slots=True)
class StartGoalResult:
    """Late start/goal relocation result."""

    rows: list[str]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FinalTraversalCleanupResult:
    """Final traversable-component diagnostic result."""

    rows: list[str]
    report: dict[str, Any]


def runtime_object_points(objects: Any) -> set[tuple[int, int]]:
    """Return all occupied runtime-object points.

    Args:
        objects: Runtime object collection.

    Returns:
        Set of occupied map coordinates.
    """
    if not isinstance(objects, list):
        return set()
    points: set[tuple[int, int]] = set()
    for item in objects:
        if not isinstance(item, dict):
            continue
        points.update(_object_points(item))
    return points


def finalize_runtime_objects_for_final_terrain(
    objects: Any,
    *,
    rows: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Mark runtime objects covered by final blocked terrain as flooded.

    Args:
        objects: Runtime object collection.
        rows: Final terrain rows after hydrology.

    Returns:
        Updated objects and a diagnostic report.
    """
    if not isinstance(objects, list):
        return [], {
            "schema_version": "final-runtime-object-pruning-v1",
            "input_objects": 0,
            "retained_objects": 0,
            "flooded_objects": 0,
        }

    output: list[dict[str, Any]] = []
    flooded = 0
    for value in objects:
        if not isinstance(value, dict):
            continue
        item = dict(value)
        points = _object_points(item)
        is_flooded = any(not _point_is_object_safe(rows, point) for point in points)
        if is_flooded:
            item["flooded"] = True
            flooded += 1
        else:
            item.pop("flooded", None)
        output.append(item)

    return output, {
        "schema_version": "final-runtime-object-pruning-v1",
        "input_objects": len([item for item in objects if isinstance(item, dict)]),
        "retained_objects": len(output),
        "flooded_objects": flooded,
        "removed_objects": 0,
        "policy": "retain_and_mark_flooded",
    }


def relocate_start_goal(
    *,
    rows: list[str],
    elevation_rows: list[list[int]],
    seed: int,
    excluded_points: Iterable[tuple[int, int]] = (),
) -> StartGoalResult:
    """Relocate start and goal on the final dry traversable map.

    Args:
        rows: Final terrain rows after hydrology.
        elevation_rows: Final elevation grid.
        source_rows: Optional elevation-source grid. Structural source tiles are
            excluded from final traversal exactly as in the 3D preview.
        seed: Deterministic generation seed.
        excluded_points: Coordinates occupied by runtime objects.

    Returns:
        Updated rows and relocation diagnostics.

    Raises:
        ValueError: If no suitable dry traversable component exists.
    """
    width, height = _validate_rows(rows)
    _validate_elevation_rows(elevation_rows, width=width, height=height)
    excluded = set(excluded_points)
    restored_rows = _restore_old_markers(rows, elevation_rows)
    components = _dry_components(
        restored_rows,
        elevation_rows=elevation_rows,
        excluded_points=excluded,
    )
    if not components:
        raise ValueError("no dry traversable component is available for START/GOAL")

    largest = components[0]
    candidates = _preferred_candidates(
        largest,
        rows=restored_rows,
        elevation_rows=elevation_rows,
        excluded_points=excluded,
    )
    if len(candidates) < 2:
        candidates = sorted(largest - excluded, key=lambda point: (point[1], point[0]))
    if len(candidates) < 2:
        raise ValueError("largest traversable component has fewer than two valid points")

    rng = random.Random(seed ^ 0x57A2_690A_1)
    anchor = candidates[rng.randrange(len(candidates))]
    start = _farthest_point(
        anchor,
        allowed=largest,
        rows=restored_rows,
        elevation_rows=elevation_rows,
        preferred=set(candidates),
    )
    goal = _farthest_point(
        start,
        allowed=largest,
        rows=restored_rows,
        elevation_rows=elevation_rows,
        preferred=set(candidates) - {start},
    )
    distances = _distances_from(
        start,
        allowed=largest,
        rows=restored_rows,
        elevation_rows=elevation_rows,
    )

    updated = [list(row) for row in restored_rows]
    updated[start[1]][start[0]] = "S"
    updated[goal[1]][goal[0]] = "G"
    output_rows = ["".join(row) for row in updated]

    return StartGoalResult(
        rows=output_rows,
        report={
            "schema_version": "late-start-goal-report-v1",
            "status": "ok",
            "rules": {
                "selected_after_hydrology": True,
                "minimum_elevation": 0,
                "wet_shore_allowed": False,
                "runtime_object_points_excluded": True,
                "component": "largest_dry_3d_traversable",
                "distance": "cardinal_shortest_path",
            },
            "component_count": len(components),
            "selected_component_tiles": len(largest),
            "candidate_tiles": len(candidates),
            "start": {"x": start[0], "y": start[1], "elevation": elevation_rows[start[1]][start[0]]},
            "goal": {"x": goal[0], "y": goal[1], "elevation": elevation_rows[goal[1]][goal[0]]},
            "path_distance_tiles": distances.get(goal),
        },
    )



def cleanup_unreachable_walkable(
    *,
    rows: list[str],
    elevation_rows: list[list[int]],
    source_rows: list[str] | None = None,
) -> FinalTraversalCleanupResult:
    """Report disconnected traversable areas without changing terrain.

    Args:
        rows: Final terrain rows. START and GOAL markers are optional.
        elevation_rows: Final elevation grid.
        source_rows: Optional elevation-source grid. Structural source tiles are
            excluded from traversable-component diagnostics.

    Returns:
        Original rows and diagnostics for final traversable components.
    """
    width, height = _validate_rows(rows)
    _validate_elevation_rows(elevation_rows, width=width, height=height)
    if source_rows is not None:
        _validate_source_rows(source_rows, width=width, height=height)

    eligible = {
        (x, y)
        for y, row in enumerate(rows)
        for x, symbol in enumerate(row)
        if symbol in WALKABLE_SYMBOLS
        and not _is_structural_source(source_rows, x=x, y=y)
    }
    components = _traversable_components(
        eligible,
        rows=rows,
        elevation_rows=elevation_rows,
    )
    largest_component_tiles = len(components[0]) if components else 0
    disconnected_tiles = max(0, len(eligible) - largest_component_tiles)

    return FinalTraversalCleanupResult(
        rows=list(rows),
        report={
            "schema_version": "final-3d-traversal-cleanup-v2",
            "kind": "final_3d_traversal_cleanup",
            "policy": {
                "mode": "diagnostic_only",
                "reference": "all_final_3d_traversable_components",
                "terrain_mutation": False,
                "start_goal_influence": False,
                "structural_source_tiles_excluded": source_rows is not None,
                "elevation_unchanged": True,
            },
            "summary": {
                "walkable_tiles_before": len(eligible),
                "component_count": len(components),
                "largest_component_tiles": largest_component_tiles,
                "disconnected_walkable_tiles": disconnected_tiles,
                "unreachable_walkable_tiles_before": disconnected_tiles,
                "blocked_as_water": 0,
                "blocked_as_rock": 0,
                "artificial_connectivity_blockers_created": 0,
                "unreachable_walkable_tiles_after": disconnected_tiles,
            },
        },
    )


def _traversable_components(
    eligible: set[tuple[int, int]],
    *,
    rows: list[str],
    elevation_rows: list[list[int]],
) -> list[set[tuple[int, int]]]:
    """Return final traversable components ordered by descending size."""
    remaining = set(eligible)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = min(remaining, key=lambda point: (point[1], point[0]))
        component = set(
            _distances_from(
                start,
                allowed=eligible,
                rows=rows,
                elevation_rows=elevation_rows,
            ),
        )
        components.append(component)
        remaining -= component
    components.sort(
        key=lambda component: (
            -len(component),
            min((y, x) for x, y in component),
        ),
    )
    return components


def _validate_rows(rows: list[str]) -> tuple[int, int]:
    if not rows or not rows[0]:
        raise ValueError("terrain rows must not be empty")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("terrain rows must be rectangular")
    return width, len(rows)


def _validate_source_rows(
    rows: list[str],
    *,
    width: int,
    height: int,
) -> None:
    """Validate elevation-source grid dimensions."""
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError("source rows must match terrain dimensions")


def _is_structural_source(
    source_rows: list[str] | None,
    *,
    x: int,
    y: int,
) -> bool:
    """Return whether a tile is a structural traversal marker."""
    return source_rows is not None and source_rows[y][x] == "S"


def _validate_elevation_rows(
    rows: list[list[int]],
    *,
    width: int,
    height: int,
) -> None:
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError("elevation rows must match terrain dimensions")


def _restore_old_markers(rows: list[str], elevation_rows: list[list[int]]) -> list[str]:
    restored: list[str] = []
    for y, row in enumerate(rows):
        chars = list(row)
        for x, symbol in enumerate(chars):
            if symbol not in {"S", "G"}:
                continue
            level = int(elevation_rows[y][x])
            if -5 <= level <= -2:
                chars[x] = DEEP_WATER_TILE
            elif level == -1:
                chars[x] = WET_SHORE_TILE
            else:
                chars[x] = "."
        restored.append("".join(chars))
    return restored


def _dry_components(
    rows: list[str],
    *,
    elevation_rows: list[list[int]],
    excluded_points: set[tuple[int, int]],
) -> list[set[tuple[int, int]]]:
    eligible = {
        (x, y)
        for y, row in enumerate(rows)
        for x, symbol in enumerate(row)
        if symbol in DRY_WALKABLE_SYMBOLS
        and elevation_rows[y][x] >= 0
        and (x, y) not in excluded_points
    }
    seen: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []
    for point in sorted(eligible, key=lambda item: (item[1], item[0])):
        if point in seen:
            continue
        component = set(_distances_from(
            point,
            allowed=eligible,
            rows=rows,
            elevation_rows=elevation_rows,
        ))
        seen.update(component)
        components.append(component)
    components.sort(key=lambda component: (-len(component), min((y, x) for x, y in component)))
    return components


def _preferred_candidates(
    component: set[tuple[int, int]],
    *,
    rows: list[str],
    elevation_rows: list[list[int]],
    excluded_points: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    height = len(rows)
    width = len(rows[0])
    margin = max(4, min(width, height) // 20)
    candidates = [
        point
        for point in component
        if point not in excluded_points
        and margin <= point[0] < width - margin
        and margin <= point[1] < height - margin
        and elevation_rows[point[1]][point[0]] >= 0
        and rows[point[1]][point[0]] not in {WET_SHORE_TILE, DEEP_WATER_TILE}
    ]
    return sorted(candidates, key=lambda point: (point[1], point[0]))


def _farthest_point(
    start: tuple[int, int],
    *,
    allowed: set[tuple[int, int]],
    rows: list[str],
    elevation_rows: list[list[int]],
    preferred: set[tuple[int, int]],
) -> tuple[int, int]:
    distances = _distances_from(
        start,
        allowed=allowed,
        rows=rows,
        elevation_rows=elevation_rows,
    )
    pool = preferred & distances.keys()
    if not pool:
        pool = set(distances)
    return max(pool, key=lambda point: (distances[point], -point[1], -point[0]))


def _distances_from(
    start: tuple[int, int],
    *,
    allowed: set[tuple[int, int]],
    rows: list[str],
    elevation_rows: list[list[int]],
) -> dict[tuple[int, int], int]:
    if start not in allowed:
        return {}
    distances = {start: 0}
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            point = (nx, ny)
            if point in distances or point not in allowed:
                continue
            if rows[ny][nx] not in WALKABLE_SYMBOLS:
                continue
            if not DEFAULT_TRAVERSAL_RULES.allows_step(
                int(elevation_rows[y][x]),
                int(elevation_rows[ny][nx]),
            ):
                continue
            distances[point] = distances[(x, y)] + 1
            queue.append(point)
    return distances


def _point_is_object_safe(rows: list[str], point: tuple[int, int]) -> bool:
    """Return whether a runtime object may remain on the final terrain tile."""
    x, y = point
    return 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] in DRY_WALKABLE_SYMBOLS


def _point_is_passable(rows: list[str], point: tuple[int, int]) -> bool:
    x, y = point
    return 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] in WALKABLE_SYMBOLS


def _object_points(item: dict[str, Any]) -> set[tuple[int, int]]:
    footprint = item.get("footprint")
    points: set[tuple[int, int]] = set()
    if isinstance(footprint, list):
        for value in footprint:
            point = _point(value)
            if point is not None:
                points.add(point)
    if points:
        return points
    for key in ("position", "center"):
        point = _point(item.get(key))
        if point is not None:
            return {point}
    try:
        return {(int(item["x"]), int(item["y"]))}
    except (KeyError, TypeError, ValueError):
        return set()


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None
