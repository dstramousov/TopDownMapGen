from __future__ import annotations

import pytest

from top_down_worldgen.tactical.vegetation_visual import reconcile_tree_collision
from top_down_worldgen.vegetation_geometry import build_vegetation_geometry


def test_vegetation_geometry_maps_symbols_and_ranges() -> None:
    """Ensure final visual symbols map to stable type and height ranges."""
    result = build_vegetation_geometry(
        visual_rows=[".TBRP"],
        elevation_rows=[[0, 0, 0, -1, 0]],
        resolved_seed=123,
    )

    assert result.type_rows == [[0, 1, 2, 3, 4]]
    assert result.height_rows[0][0] == 0
    assert 2 <= result.height_rows[0][1] <= 5
    assert 1 <= result.height_rows[0][2] <= 2
    assert result.height_rows[0][3:] == [1, 1]
    assert result.summary.total_vegetation_tiles == 4
    assert result.summary.visual_type_mismatches == 0


def test_vegetation_geometry_is_deterministic() -> None:
    """Ensure identical inputs and seed produce identical grids."""
    visual_rows = ["TTTTT", "TBBBT", "TRPRT", "TTTTT"]
    elevation_rows = [[0] * 5 for _ in visual_rows]

    first = build_vegetation_geometry(
        visual_rows=visual_rows,
        elevation_rows=elevation_rows,
        resolved_seed=987654321,
    )
    second = build_vegetation_geometry(
        visual_rows=visual_rows,
        elevation_rows=elevation_rows,
        resolved_seed=987654321,
    )

    assert first.type_rows == second.type_rows
    assert first.height_rows == second.height_rows
    assert first.summary == second.summary


def test_dense_forest_center_is_taller_than_edge() -> None:
    """Ensure forest depth raises trees without independent tile noise."""
    size = 11
    result = build_vegetation_geometry(
        visual_rows=["T" * size for _ in range(size)],
        elevation_rows=[[0] * size for _ in range(size)],
        resolved_seed=42,
    )

    edge_heights = [
        result.height_rows[y][x]
        for y in range(size)
        for x in range(size)
        if x in {0, size - 1} or y in {0, size - 1}
    ]
    center_height = result.height_rows[size // 2][size // 2]

    assert set(edge_heights) == {2}
    assert center_height >= 4


def test_neighboring_tree_heights_change_gradually() -> None:
    """Ensure coherent tree patches do not create vertical spikes."""
    visual_rows = ["T" * 17 for _ in range(13)]
    result = build_vegetation_geometry(
        visual_rows=visual_rows,
        elevation_rows=[[0] * 17 for _ in range(13)],
        resolved_seed=314159,
    )

    maximum_delta = 0
    for y, row in enumerate(result.height_rows):
        for x, value in enumerate(row):
            if x + 1 < len(row):
                maximum_delta = max(
                    maximum_delta,
                    abs(value - result.height_rows[y][x + 1]),
                )
            if y + 1 < len(result.height_rows):
                maximum_delta = max(
                    maximum_delta,
                    abs(value - result.height_rows[y + 1][x]),
                )

    assert maximum_delta <= 1


def test_highland_tree_height_is_capped() -> None:
    """Ensure visible highland trees cannot reach the lowland maximum."""
    result = build_vegetation_geometry(
        visual_rows=["TTT"],
        elevation_rows=[[17, 17, 17]],
        resolved_seed=9,
    )

    assert max(result.height_rows[0]) <= 3
    assert min(result.height_rows[0]) >= 2


def test_map_without_vegetation_has_zero_grids() -> None:
    """Ensure a vegetation-free map still produces complete zero grids."""
    result = build_vegetation_geometry(
        visual_rows=["....", "...."],
        elevation_rows=[[0, 1, 2, 3], [4, 3, 2, 1]],
        resolved_seed=1,
    )

    assert result.type_rows == [[0, 0, 0, 0], [0, 0, 0, 0]]
    assert result.height_rows == [[0, 0, 0, 0], [0, 0, 0, 0]]
    assert result.summary.total_vegetation_tiles == 0
    assert result.summary.average_tree_height == 0.0


def test_geometry_uses_reconciled_visual_rows() -> None:
    """Ensure geometry follows the final post-connectivity vegetation mask."""
    collision = reconcile_tree_collision(
        rows=["TT"],
        visual_rows=[".T"],
    )

    result = build_vegetation_geometry(
        visual_rows=collision.visual_rows,
        elevation_rows=[[0, 0]],
        resolved_seed=7,
    )

    assert result.type_rows == [[0, 1]]
    assert result.height_rows[0][0] == 0
    assert 2 <= result.height_rows[0][1] <= 5


def test_unknown_visual_symbol_is_rejected() -> None:
    """Ensure unsupported visual symbols fail instead of silently degrading."""
    with pytest.raises(ValueError, match="unknown vegetation visual symbol"):
        build_vegetation_geometry(
            visual_rows=["TX"],
            elevation_rows=[[0, 0]],
            resolved_seed=5,
        )
