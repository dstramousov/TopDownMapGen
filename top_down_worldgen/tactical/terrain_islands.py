from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

WALKABLE_SYMBOLS: frozenset[str] = frozenset("+.bfmwcRSG")
DEFAULT_BLOCKED_SYMBOL = "T"
DEFAULT_SMALL_ISLAND_MAX_TILES = 12


@dataclass(frozen=True, slots=True)
class TerrainIslandRepairResult:
    """Result of isolated 2D walkable terrain cleanup."""

    rows: list[str]
    report: dict[str, Any]


def elevation_cell_points(
    tactical_data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    """Return valid coordinates occupied by explicit object-derived elevation cells.

    Args:
        tactical_data: Runtime tactical map data.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        Set of in-bounds ``(x, y)`` coordinates from ``elevation.cells``.
    """
    elevation = tactical_data.get("elevation")
    if not isinstance(elevation, dict):
        return set()

    points: set[tuple[int, int]] = set()
    for cell in elevation.get("cells", []):
        if not isinstance(cell, dict):
            continue
        try:
            x = int(cell.get("x"))
            y = int(cell.get("y"))
        except (TypeError, ValueError):
            continue
        if 0 <= x < width and 0 <= y < height:
            points.add((x, y))
    return points


def repair_terrain_islands(
    rows: list[str],
    *,
    blocked_points: Iterable[tuple[int, int]] | None = None,
    small_island_max_tiles: int = DEFAULT_SMALL_ISLAND_MAX_TILES,
    fill_symbol: str = DEFAULT_BLOCKED_SYMBOL,
) -> TerrainIslandRepairResult:
    """Remove tiny isolated 2D walkable islands from ASCII terrain rows.

    The cleanup preserves the start-connected walkable component. Other walkable
    components are either removed when tiny, or preserved and reported when they
    are large enough to be intentional future regions. The function does not
    carve connectors and does not modify blocked terrain except replacing tiny
    island cells with ``fill_symbol``.

    Args:
        rows: Rectangular ASCII terrain rows.
        blocked_points: Additional coordinates treated as non-walkable during
            component analysis, typically object-derived structural depth cells.
        small_island_max_tiles: Maximum isolated component size to remove.
        fill_symbol: ASCII tile used to replace removed island cells.

    Returns:
        Repaired rows and a JSON-serializable repair report.
    """
    width, height = _dimensions(rows)
    if width == 0 or height == 0:
        return TerrainIslandRepairResult(
            rows=list(rows),
            report=_empty_report(reason="empty_map"),
        )

    blocked = _bounded_points(blocked_points or (), width=width, height=height)
    components = _walkable_components(rows, blocked_points=blocked)
    main_index = _main_component_index(rows, components)

    repaired = [list(row) for row in rows]
    removed_components: list[dict[str, Any]] = []
    preserved_components: list[dict[str, Any]] = []

    for index, component in enumerate(components):
        if index == main_index:
            continue
        contains_critical = _contains_any_tile(rows, component, {"S", "G"})
        component_record = _component_record(component)
        if len(component) <= small_island_max_tiles and not contains_critical:
            for x, y in component:
                repaired[y][x] = fill_symbol
            removed_components.append(component_record)
        else:
            preserved_components.append(component_record | {"contains_critical_tile": contains_critical})

    repaired_rows = ["".join(row) for row in repaired]
    components_after = _walkable_components(repaired_rows, blocked_points=blocked)
    report = _build_report(
        width=width,
        height=height,
        small_island_max_tiles=small_island_max_tiles,
        fill_symbol=fill_symbol,
        blocked_points=len(blocked),
        components_before=components,
        components_after=components_after,
        main_index=main_index,
        removed_components=removed_components,
        preserved_components=preserved_components,
    )
    return TerrainIslandRepairResult(rows=repaired_rows, report=report)


def _dimensions(rows: list[str]) -> tuple[int, int]:
    if not rows:
        return 0, 0
    width = len(rows[0])
    if width == 0:
        return 0, len(rows)
    for index, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(
                f"terrain rows must be rectangular: row={index} width={len(row)} expected={width}",
            )
    return width, len(rows)


def _bounded_points(
    points: Iterable[tuple[int, int]],
    *,
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    bounded: set[tuple[int, int]] = set()
    for x, y in points:
        if 0 <= x < width and 0 <= y < height:
            bounded.add((x, y))
    return bounded


def _walkable_components(
    rows: list[str],
    *,
    blocked_points: set[tuple[int, int]],
) -> list[set[tuple[int, int]]]:
    height = len(rows)
    width = len(rows[0]) if height else 0
    seen: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []

    for y, row in enumerate(rows):
        for x, symbol in enumerate(row):
            point = (x, y)
            if point in seen or not _is_walkable_symbol(symbol) or point in blocked_points:
                continue
            component = _flood_component(rows, start=point, blocked_points=blocked_points)
            seen.update(component)
            components.append(component)

    components.sort(key=lambda component: (-len(component), _component_sort_key(component)))
    return components


def _flood_component(
    rows: list[str],
    *,
    start: tuple[int, int],
    blocked_points: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    height = len(rows)
    width = len(rows[0]) if height else 0
    visited = {start}
    queue: deque[tuple[int, int]] = deque([start])

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            point = (nx, ny)
            if point in visited or point in blocked_points:
                continue
            if not _is_walkable_symbol(rows[ny][nx]):
                continue
            visited.add(point)
            queue.append(point)
    return visited


def _main_component_index(rows: list[str], components: list[set[tuple[int, int]]]) -> int | None:
    start = _find_tile(rows, "S")
    if start is not None:
        for index, component in enumerate(components):
            if start in component:
                return index
    return 0 if components else None


def _find_tile(rows: list[str], symbol: str) -> tuple[int, int] | None:
    for y, row in enumerate(rows):
        x = row.find(symbol)
        if x >= 0:
            return (x, y)
    return None


def _is_walkable_symbol(symbol: str) -> bool:
    return symbol in WALKABLE_SYMBOLS


def _contains_any_tile(
    rows: list[str],
    component: set[tuple[int, int]],
    symbols: set[str],
) -> bool:
    return any(rows[y][x] in symbols for x, y in component)


def _component_record(component: set[tuple[int, int]]) -> dict[str, Any]:
    min_x = min(x for x, _ in component)
    max_x = max(x for x, _ in component)
    min_y = min(y for _, y in component)
    max_y = max(y for _, y in component)
    return {
        "size_tiles": len(component),
        "bounds": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": max_x - min_x + 1,
            "height": max_y - min_y + 1,
        },
    }


def _component_sort_key(component: set[tuple[int, int]]) -> tuple[int, int]:
    min_x = min(x for x, _ in component)
    min_y = min(y for _, y in component)
    return (min_y, min_x)


def _build_report(
    *,
    width: int,
    height: int,
    small_island_max_tiles: int,
    fill_symbol: str,
    blocked_points: int,
    components_before: list[set[tuple[int, int]]],
    components_after: list[set[tuple[int, int]]],
    main_index: int | None,
    removed_components: list[dict[str, Any]],
    preserved_components: list[dict[str, Any]],
) -> dict[str, Any]:
    main_component_size = 0
    if main_index is not None and 0 <= main_index < len(components_before):
        main_component_size = len(components_before[main_index])
    removed_tiles = sum(int(item["size_tiles"]) for item in removed_components)
    preserved_tiles = sum(int(item["size_tiles"]) for item in preserved_components)
    return {
        "schema_version": "terrain-island-report-v1",
        "status": "ok",
        "dimensions": {"width": width, "height": height, "tiles": width * height},
        "rules": {
            "scope": "2d_walkable_components_before_elevation_generation",
            "small_island_max_tiles": small_island_max_tiles,
            "fill_symbol": fill_symbol,
            "blocked_points_source": "explicit_object_elevation_cells",
            "large_islands": "preserved_and_reported",
            "connectors": "not_carved",
        },
        "summary": {
            "components_before": len(components_before),
            "components_after": len(components_after),
            "main_component_size": main_component_size,
            "small_islands_removed": len(removed_components),
            "small_island_tiles_removed": removed_tiles,
            "large_islands_preserved": len(preserved_components),
            "large_island_tiles_preserved": preserved_tiles,
            "blocked_points": blocked_points,
        },
        "removed_components": removed_components,
        "preserved_components": preserved_components,
    }


def _empty_report(*, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "terrain-island-report-v1",
        "status": "skipped",
        "reason": reason,
        "summary": {
            "components_before": 0,
            "components_after": 0,
            "main_component_size": 0,
            "small_islands_removed": 0,
            "small_island_tiles_removed": 0,
            "large_islands_preserved": 0,
            "large_island_tiles_preserved": 0,
            "blocked_points": 0,
        },
        "removed_components": [],
        "preserved_components": [],
    }
