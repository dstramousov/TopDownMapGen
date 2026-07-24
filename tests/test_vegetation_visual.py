from top_down_worldgen.tactical.vegetation_visual import (
    build_visual_vegetation,
    reconcile_tree_collision,
)


def test_visual_vegetation_removes_trees_from_peaks_without_changing_input() -> None:
    terrain = [["tree_blocker", "tree_blocker", "grass"]]
    elevation = [[8, 18, 20]]
    slopes = [[0, 0, 0]]

    result = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=123,
    )

    assert result.rows[0][1:] == ".."
    assert terrain[0][1] == "tree_blocker"
    assert result.report["summary"]["tree_tiles_before"] == 2
    assert result.report["summary"]["tree_tiles_after"] <= 1
    assert result.report["rules"]["gameplay_collision_unchanged"] is True


def test_visual_vegetation_is_deterministic() -> None:
    terrain = [["tree_blocker"] * 16]
    elevation = [[14] * 16]
    slopes = [[1] * 16]

    first = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=456,
    )
    second = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=456,
    )

    assert first.rows == second.rows
    assert 0 < first.report["summary"]["tree_tiles_after"] < 16


def test_visual_vegetation_removes_lowland_trees_and_adds_seeded_reeds() -> None:
    terrain = [["tree_blocker", "water_slow", "water_slow", "deep_water_blocker"]]
    elevation = [[-1, -1, -1, -2]]
    slopes = [[0, 0, 0, 0]]

    result = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=1,
        shore_reed_density=1.0,
        puddle_reed_density=1.0,
    )

    assert result.rows[0][0] == "."
    assert result.rows[0][3] == "."
    assert "R" in result.rows[0][1:3]
    assert result.report["summary"]["shore_reeds_visible"] >= 1
    assert result.report["summary"]["removed_by_lowland"] == 1


def test_visual_vegetation_thins_original_forest_edge_without_changing_terrain() -> None:
    size = 11
    terrain = [["tree_blocker" for _ in range(size)] for _ in range(size)]
    elevation = [[0 for _ in range(size)] for _ in range(size)]
    slopes = [[0 for _ in range(size)] for _ in range(size)]

    result = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=777,
    )

    visible_edge = sum(
        result.rows[y][x] == "T"
        for y in range(size)
        for x in range(size)
        if x in {0, size - 1} or y in {0, size - 1}
    )
    edge_tiles = size * 4 - 4

    assert visible_edge < edge_tiles
    assert result.rows[size // 2][size // 2] == "T"
    assert all(tile == "tree_blocker" for row in terrain for tile in row)
    assert result.report["summary"]["removed_by_forest_edge"] > 0
    assert result.report["rules"]["forest_edge_depth_tiles"] == 4


def test_visual_vegetation_forest_edge_is_deterministic() -> None:
    terrain = [["tree_blocker" for _ in range(9)] for _ in range(9)]
    elevation = [[0 for _ in range(9)] for _ in range(9)]
    slopes = [[0 for _ in range(9)] for _ in range(9)]

    first = build_visual_vegetation(
        terrain_rows=terrain, elevation_rows=elevation, slope_rows=slopes, seed=42
    )
    second = build_visual_vegetation(
        terrain_rows=terrain, elevation_rows=elevation, slope_rows=slopes, seed=42
    )

    assert first.rows == second.rows


def test_reconcile_tree_collision_opens_only_hidden_tree_tiles() -> None:
    result = reconcile_tree_collision(
        rows=["TT+#~"],
        visual_rows=[".T..."],
    )

    assert result.rows == ["+T+#~"]
    assert result.visual_rows == [".T..."]
    assert result.report["summary"]["opened_tree_tiles"] == 1
    assert result.report["summary"]["retained_visible_tree_tiles"] == 1


def test_reconcile_tree_collision_validates_dimensions() -> None:
    import pytest

    with pytest.raises(ValueError):
        reconcile_tree_collision(rows=["TT"], visual_rows=["."])


def test_reconcile_tree_collision_rejects_isolated_opened_pockets() -> None:
    rows = [
        "TTTTT",
        "T...T",
        "TTTTT",
        "TTTTT",
        "TTTTT",
    ]
    visual_rows = [
        "TTTTT",
        "T...T",
        "TTTTT",
        "T.TTT",
        "TTTTT",
    ]
    elevation = [
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]

    result = reconcile_tree_collision(
        rows=rows,
        visual_rows=visual_rows,
        elevation_rows=elevation,
    )

    assert result.rows[3][1] == "T"
    assert result.visual_rows[3][1] == "T"
    assert result.report["summary"]["rejected_isolated_tiles"] == 1


def test_reconcile_tree_collision_restores_isolated_highland_tree() -> None:
    result = reconcile_tree_collision(
        rows=["T#..", "####"],
        visual_rows=["....", "...."],
        elevation_rows=[[18, 0, 0, 0], [0, 0, 0, 0]],
    )

    assert result.rows[0][0] == "T"
    assert result.visual_rows[0][0] == "T"
    assert result.report["summary"]["rejected_as_visible_tree"] == 1
    assert result.report["summary"]["rejected_as_rock"] == 0
    assert result.report["summary"]["artificial_rock_blockers_created"] == 0


def test_visual_vegetation_distinguishes_shore_and_puddle_reeds() -> None:
    terrain = [["water_slow", "water_slow"]]
    elevation = [[-1, 0]]
    slopes = [[0, 0]]

    result = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=7,
        shore_reed_density=1.0,
        puddle_reed_density=1.0,
    )

    assert result.rows == ["RP"]
    assert result.report["summary"]["shore_reeds_visible"] == 1
    assert result.report["summary"]["puddle_reeds_visible"] == 1
    assert result.report["legend"]["R"] == "shore_reed"
    assert result.report["legend"]["P"] == "puddle_reed"


def test_reclaimed_edge_bushes_are_deterministic_and_walkable_slow() -> None:
    size = 9
    terrain = [["tree_blocker" for _ in range(size)] for _ in range(size)]
    elevation = [[0 for _ in range(size)] for _ in range(size)]
    slopes = [[0 for _ in range(size)] for _ in range(size)]

    visual = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=1234,
        reclaimed_edge_bush_density=1.0,
        reclaimed_altitude_bush_density=0.0,
    )
    collision = reconcile_tree_collision(
        rows=["T" * size for _ in range(size)],
        visual_rows=visual.rows,
        elevation_rows=elevation,
    )

    assert "B" in "".join(visual.rows)
    assert "b" in "".join(collision.rows)
    assert collision.report["summary"]["opened_as_reclaimed_bush"] > 0
    assert visual.report["legend"]["B"] == "reclaimed_bush"


def test_reclaimed_bushes_do_not_grow_above_limit_or_on_cliffs() -> None:
    terrain = [["tree_blocker", "tree_blocker"]]
    elevation = [[17, 18]]
    slopes = [[2, 0]]

    visual = build_visual_vegetation(
        terrain_rows=terrain,
        elevation_rows=elevation,
        slope_rows=slopes,
        seed=1,
        reclaimed_edge_bush_density=1.0,
        reclaimed_altitude_bush_density=1.0,
        reclaimed_bush_max_elevation=17,
    )

    assert "B" not in visual.rows[0]
