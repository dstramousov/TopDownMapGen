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


def test_fortress_wall_top_is_flat_across_elevation_changes() -> None:
    """Ensure wall structure levels compensate terrain into one flat top."""
    result = build_structure_height(
        terrain_rows=[["grass", "grass", "grass"]],
        collision_rows=["000"],
        resolved_seed=1,
        structure_type_rows=[[10, 10, 10]],
        elevation_rows=[[0, 2, 5]],
    )

    absolute_tops = [
        elevation + 1 + height
        for elevation, height in zip(
            [0, 2, 5],
            result.rows[0],
            strict=True,
        )
    ]
    assert len(set(absolute_tops)) == 1
    assert result.rows[0] == [11, 9, 6]


def test_stale_coarse_fortress_height_is_cleared() -> None:
    """Ensure old shell metadata cannot leave height outside final geometry."""
    result = build_structure_height(
        terrain_rows=[["grass", "grass"]],
        collision_rows=["00"],
        resolved_seed=1,
        fortress_plan={
            "materialization": {
                "structure_heights": [[0, 0, 6], [1, 0, 6]],
            },
        },
        structure_type_rows=[[10, 0]],
        elevation_rows=[[0, 0]],
    )

    assert result.rows == [[6, 0]]


def test_fortress_tower_top_is_flat_across_elevation_changes() -> None:
    """Ensure one round tower has no lowered roof tiles or pits."""
    result = build_structure_height(
        terrain_rows=[["grass", "grass"], ["grass", "grass"]],
        collision_rows=["00", "00"],
        resolved_seed=1,
        fortress_plan={
            "materialization": {
                "structure_heights": [[0, 0, 7], [1, 0, 10]],
            },
        },
        structure_type_rows=[[11, 11], [11, 11]],
        elevation_rows=[[0, 2], [1, 3]],
    )

    absolute_tops = {
        [[0, 2], [1, 3]][y][x] + 1 + result.rows[y][x]
        for y in range(2)
        for x in range(2)
    }
    assert len(absolute_tops) == 1
