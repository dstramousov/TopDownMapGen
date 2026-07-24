from __future__ import annotations

import pytest

from top_down_worldgen.structure_height import build_structure_height


def test_structure_height_is_connected_and_deterministic() -> None:
    """Ensure a straight wall has stable locally connected heights."""
    terrain = [["ruin_wall_blocker" for _ in range(10)]]
    collision = ["1" * 10]

    first = build_structure_height(
        terrain_rows=terrain,
        collision_rows=collision,
        resolved_seed=12345,
    )
    second = build_structure_height(
        terrain_rows=terrain,
        collision_rows=collision,
        resolved_seed=12345,
    )

    assert first.rows == second.rows
    assert 1 <= first.rows[0][0] <= 2
    assert 1 <= first.rows[0][-1] <= 2
    assert all(1 <= value <= 3 for value in first.rows[0])
    assert all(
        abs(left - right) <= 1
        for left, right in zip(first.rows[0], first.rows[0][1:], strict=False)
    )
    assert first.summary.connected_wall_components == 1
    assert first.summary.maximum_adjacent_height_delta <= 1


def test_structure_height_preserves_existing_passage() -> None:
    """Ensure a final ruin-floor passage remains a zero-height gap."""
    terrain = [[
        "ruin_wall_blocker",
        "ruin_wall_blocker",
        "ruin_floor",
        "ruin_wall_blocker",
        "ruin_wall_blocker",
    ]]
    collision = ["11011"]

    result = build_structure_height(
        terrain_rows=terrain,
        collision_rows=collision,
        resolved_seed=7,
    )

    assert result.rows[0][2] == 0
    assert all(result.rows[0][index] >= 1 for index in (0, 1, 3, 4))
    assert result.summary.connected_wall_components == 2


def test_structure_height_map_without_ruins_is_zero() -> None:
    """Ensure maps without ruins still receive a complete zero layer."""
    result = build_structure_height(
        terrain_rows=[["grass", "water"], ["start", "goal"]],
        collision_rows=["01", "00"],
        resolved_seed=9,
    )

    assert result.rows == [[0, 0], [0, 0]]
    assert result.summary.ruin_wall_tiles == 0
    assert result.summary.connected_wall_components == 0


def test_structure_height_rejects_passable_ruin_wall() -> None:
    """Ensure invisible collision inconsistencies fail generation."""
    with pytest.raises(ValueError, match="not blocked"):
        build_structure_height(
            terrain_rows=[["ruin_wall_blocker"]],
            collision_rows=["0"],
            resolved_seed=1,
        )
