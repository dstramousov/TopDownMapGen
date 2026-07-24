from top_down_worldgen.tactical.elevation import _semantic_main_route_points


def test_semantic_main_route_does_not_fall_back_to_start_goal() -> None:
    rows = [
        "S....G",
        "......",
    ]

    assert _semantic_main_route_points(rows, {}) == []


def test_semantic_main_route_uses_places_without_start_goal_endpoints() -> None:
    rows = [
        "S....G",
        "......",
    ]
    tactical_data = {
        "places": [
            {
                "id": "a",
                "center": {"x": 1, "y": 1},
                "danger_level": 1,
                "loot_level": 1,
            },
            {
                "id": "b",
                "center": {"x": 3, "y": 1},
                "danger_level": 1,
                "loot_level": 1,
            },
            {
                "id": "c",
                "center": {"x": 4, "y": 1},
                "danger_level": 1,
                "loot_level": 1,
            },
        ],
    }

    points = _semantic_main_route_points(rows, tactical_data)

    assert len(points) >= 2
    assert (0, 0) not in points
    assert (5, 0) not in points
    assert set(points).issubset({(1, 1), (3, 1), (4, 1)})
