from top_down_worldgen.tactical.terrain_islands import (
    elevation_cell_points,
    repair_terrain_islands,
)


def test_elevation_cell_points_filters_invalid_cells() -> None:
    """Ensure object-derived elevation cells are normalized to valid points."""
    tactical_data = {
        "elevation": {
            "cells": [
                {"x": 1, "y": 2, "level": -1},
                {"x": "3", "y": "4", "level": -1},
                {"x": 9, "y": 9, "level": -1},
                {"x": "bad", "y": 1, "level": -1},
            ],
        },
    }

    assert elevation_cell_points(tactical_data, width=5, height=5) == {(1, 2), (3, 4)}


def test_repair_terrain_islands_removes_small_island() -> None:
    """Ensure tiny disconnected walkable components are replaced by blockers."""
    rows = [
        "STTTTT",
        "++TTTT",
        "TTTTTT",
        "TTT++T",
        "TTTTTT",
        "TTTTTG",
    ]

    result = repair_terrain_islands(rows, small_island_max_tiles=3)

    assert result.rows[3] == "TTTTTT"
    assert result.report["summary"]["small_islands_removed"] == 1
    assert result.report["summary"]["small_island_tiles_removed"] == 2


def test_repair_terrain_islands_preserves_large_island() -> None:
    """Ensure large disconnected components are reported but preserved."""
    rows = [
        "STTTTT",
        "++TTTT",
        "TTTTTT",
        "TT++++",
        "TT++++",
        "TTTTTG",
    ]

    result = repair_terrain_islands(rows, small_island_max_tiles=3)

    assert result.rows == rows
    assert result.report["summary"]["large_islands_preserved"] == 1
    assert result.report["summary"]["large_island_tiles_preserved"] == 9


def test_repair_terrain_islands_uses_structural_points_as_blockers() -> None:
    """Ensure structural depth points split the 2D walkable component."""
    rows = [
        "STTT",
        "++++",
        "TTTT",
    ]

    result = repair_terrain_islands(
        rows,
        blocked_points={(2, 1)},
        small_island_max_tiles=3,
    )

    assert result.rows[1] == "+++T"
    assert result.report["summary"]["small_island_tiles_removed"] == 1
