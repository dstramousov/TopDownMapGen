from top_down_worldgen.tactical.start_goal import (
    finalize_runtime_objects_for_final_terrain,
    relocate_start_goal,
    runtime_object_points,
)


def test_relocate_start_goal_uses_final_dry_component() -> None:
    rows = [
        "~~~~~~~",
        "~S....~",
        "~.....~",
        "~~~~..~",
        "~....G~",
        "~.....~",
        "~~~~~~~",
    ]
    elevation = [
        [-2] * 7,
        [-2, -2, 0, 0, 0, 0, -2],
        [-2, 0, 0, 0, 0, 0, -2],
        [-2, -2, -2, -2, 0, 0, -2],
        [-2, 0, 0, 0, 0, 0, -2],
        [-2, 0, 0, 0, 0, 0, -2],
        [-2] * 7,
    ]

    result = relocate_start_goal(
        rows=rows,
        elevation_rows=elevation,
        seed=123,
    )

    start = result.report["start"]
    goal = result.report["goal"]
    assert start["elevation"] >= 0
    assert goal["elevation"] >= 0
    assert result.report["path_distance_tiles"] is not None
    assert sum(row.count("S") for row in result.rows) == 1
    assert sum(row.count("G") for row in result.rows) == 1
    assert result.rows[1][1] == "~"


def test_runtime_objects_are_marked_flooded_and_points_are_collected() -> None:
    objects = [
        {"type": "crate", "position": [1, 1]},
        {"type": "bridge", "footprint": [[2, 1], [3, 1]]},
    ]
    rows = ["~~~~~", "~.~.~", "~~~~~"]

    updated, report = finalize_runtime_objects_for_final_terrain(objects, rows=rows)

    assert runtime_object_points(updated) == {(1, 1), (2, 1), (3, 1)}
    assert updated[0].get("flooded") is None
    assert updated[1]["flooded"] is True
    assert report["flooded_objects"] == 1
