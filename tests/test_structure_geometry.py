from top_down_worldgen.structure_geometry import (
    FULL_MICRO_MASK,
    MICRO_DIVISION,
    build_structure_geometry,
    sparse_micro_cells,
)


def test_structure_geometry_classifies_ruins_and_fortress() -> None:
    terrain = [
        ["grass", "ruin_wall_blocker", "ruin_floor"],
        ["ruin_floor", "ruin_wall_blocker", "grass"],
    ]
    fortress_plan = {
        "materialization": {
            "structure_types": [
                [0, 1, "fortress_floor"],
                [1, 1, "fortress_tower"],
            ],
        },
    }

    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=fortress_plan,
    )

    assert MICRO_DIVISION == 4
    assert result.type_rows == [[0, 1, 2], [15, 11, 0]]
    assert result.mask_rows == [
        [0, FULL_MICRO_MASK, FULL_MICRO_MASK],
        [FULL_MICRO_MASK, FULL_MICRO_MASK, 0],
    ]
    assert sparse_micro_cells(result) == [
        {"x": 1, "y": 0, "mask": FULL_MICRO_MASK},
        {"x": 2, "y": 0, "mask": FULL_MICRO_MASK},
        {"x": 0, "y": 1, "mask": FULL_MICRO_MASK},
        {"x": 1, "y": 1, "mask": FULL_MICRO_MASK},
    ]
