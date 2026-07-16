from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEEP_WATER_TILE = "~"
WET_SHORE_TILE = "w"
PROTECTED_TILES = frozenset({"S", "G"})


@dataclass(frozen=True, slots=True)
class HydrologyResult:
    """Hydrology-adjusted terrain rows and diagnostics."""

    rows: list[str]
    report: dict[str, Any]


def apply_elevation_hydrology(
    *,
    rows: list[str],
    elevation_rows: list[list[int]],
) -> HydrologyResult:
    """Apply gameplay water semantics to negative elevation levels.

    Args:
        rows: Final ASCII terrain rows.
        elevation_rows: Final geographic elevation rows.

    Returns:
        Terrain rows with deep water and wet shore tiles.
    """
    output: list[str] = []
    counts = {"deep_water": 0, "wet_shore": 0, "protected": 0, "tree_tiles_removed": 0}
    by_level: dict[str, int] = {}
    for y, row in enumerate(rows):
        chars = list(row)
        for x, tile in enumerate(chars):
            level = _level(elevation_rows, x=x, y=y)
            if tile in PROTECTED_TILES:
                if level < 0:
                    counts["protected"] += 1
                continue
            if -5 <= level <= -2:
                if tile == "T":
                    counts["tree_tiles_removed"] += 1
                chars[x] = DEEP_WATER_TILE
                counts["deep_water"] += 1
                by_level[str(level)] = by_level.get(str(level), 0) + 1
            elif level == -1:
                if tile == "T":
                    counts["tree_tiles_removed"] += 1
                chars[x] = WET_SHORE_TILE
                counts["wet_shore"] += 1
                by_level[str(level)] = by_level.get(str(level), 0) + 1
        output.append("".join(chars))
    return HydrologyResult(
        rows=output,
        report={
            "schema_version": "elevation-hydrology-report-v1",
            "kind": "elevation_hydrology",
            "rules": {
                "deep_water_levels": [-5, -4, -3, -2],
                "wet_shore_level": -1,
                "deep_water_walkable": False,
                "wet_shore_walkable": True,
                "wet_shore_movement_class": "water_slow",
            },
            "summary": counts,
            "by_level": by_level,
        },
    )


def _level(rows: list[list[int]], *, x: int, y: int) -> int:
    if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
        return int(rows[y][x])
    return 0
