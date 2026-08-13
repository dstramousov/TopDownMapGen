from __future__ import annotations

from top_down_worldgen.tactical.elevation import (
    build_geography_draft,
    build_natural_geography_model,
)
from top_down_worldgen.tactical.environment_context import (
    REGION_PROFILE_NAMES,
    build_environment_context,
    build_forest_depth_rows,
    build_forest_distance_rows,
)


def test_forest_depth_preserves_semantic_edge_and_deep_forest() -> None:
    """Ensure semantic forest depth is capped without using visual thinning."""
    rows = [["grass" for _ in range(9)] for _ in range(9)]
    for y in range(1, 8):
        for x in range(1, 8):
            rows[y][x] = "tree_blocker"

    depths = build_forest_depth_rows(rows)

    assert depths[1][1] == 1
    assert depths[2][2] == 2
    assert depths[3][3] == 3
    assert depths[4][4] == 4
    assert depths[0][0] == 0


def test_forest_distance_uses_local_chamfer_distance_and_far_clamp() -> None:
    """Ensure forest proximity is zero in forest and clamped at nine tiles."""
    rows = [["grass" for _ in range(21)] for _ in range(3)]
    rows[1][10] = "tree_blocker"

    distances = build_forest_distance_rows(rows)

    assert distances[1][10] == 0
    assert distances[1][9] == 1
    assert distances[0][9] == 1
    assert distances[1][8] == 2
    assert distances[1][0] == 9
    assert distances[1][20] == 9


def test_environment_context_is_deterministic_and_uses_existing_geography() -> None:
    """Ensure public context derives deterministically from geography and terrain."""
    draft = build_geography_draft(
        width=12,
        height=10,
        seed=1234,
        elevation_style="normal",
    )
    model = build_natural_geography_model(
        width=12,
        height=10,
        seed=1234,
        elevation_style="normal",
        geography_draft=draft,
    )
    terrain_rows = [["grass" for _ in range(12)] for _ in range(10)]
    for y in range(2, 8):
        for x in range(3, 9):
            terrain_rows[y][x] = "tree_blocker"

    first = build_environment_context(
        natural_geography=model,
        terrain_rows=terrain_rows,
    )
    second = build_environment_context(
        natural_geography=model,
        terrain_rows=terrain_rows,
    )

    assert first == second
    assert first.width == 12
    assert first.height == 10
    assert len(first.moisture_rows) == 10
    assert len(first.moisture_rows[0]) == 12
    assert all(
        0 <= value <= 1000
        for row in first.moisture_rows
        for value in row
    )
    assert all(
        0 <= value < len(REGION_PROFILE_NAMES)
        for row in first.region_profile_rows
        for value in row
    )
    assert all(
        0 <= value <= 3
        for row in first.slope_band_rows
        for value in row
    )
    assert first.forest_depth_rows[2][3] == 1
    assert first.forest_distance_rows[0][0] > 0
