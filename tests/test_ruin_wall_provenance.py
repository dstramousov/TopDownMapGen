from top_down_worldgen.tactical.ruin_wall_provenance import (
    analyze_ruin_wall_provenance,
)


def test_ruin_wall_provenance_detects_hash_outside_buildings() -> None:
    report = analyze_ruin_wall_provenance(
        rows=[
            ".....",
            ".##..",
            "....#",
        ],
        ruin_sites={
            "sites": [
                {
                    "buildings": [
                        {
                            "rect": {
                                "left": 1,
                                "top": 1,
                                "right": 2,
                                "bottom": 1,
                            },
                        },
                    ],
                },
            ],
        },
    )

    assert report["summary"] == {
        "total_ruin_wall_tiles": 3,
        "inside_planned_buildings": 2,
        "outside_planned_buildings": 1,
        "fortress_wall_tiles_excluded": 0,
        "artificial_connectivity_blockers_created": 0,
    }
    assert report["outside_points"] == [{"x": 4, "y": 2}]


def test_ruin_wall_provenance_accepts_empty_map_without_sites() -> None:
    report = analyze_ruin_wall_provenance(rows=["...", "..."], ruin_sites=None)

    assert report["summary"]["total_ruin_wall_tiles"] == 0
    assert report["summary"]["outside_planned_buildings"] == 0
