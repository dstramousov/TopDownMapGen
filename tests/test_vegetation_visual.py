from top_down_worldgen.tactical.vegetation_visual import build_visual_vegetation


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

    assert result.rows == ["T.."]
    assert terrain[0][1] == "tree_blocker"
    assert result.report["summary"]["tree_tiles_before"] == 2
    assert result.report["summary"]["tree_tiles_after"] == 1
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
