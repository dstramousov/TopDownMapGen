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
        [0, 0x0660, 0],
        [0, FULL_MICRO_MASK, 0],
    ]
    assert sparse_micro_cells(result) == [
        {"x": 1, "y": 0, "mask": 0x0660},
        {"x": 1, "y": 1, "mask": FULL_MICRO_MASK},
    ]


def test_round_fortress_tower_uses_partial_micro_masks() -> None:
    terrain = [["grass" for _ in range(9)] for _ in range(9)]
    structure_types = []
    for y in range(1, 8):
        for x in range(1, 8):
            distance_squared = (x - 4) ** 2 + (y - 4) ** 2
            if 1 < distance_squared <= 12:
                terrain[y][x] = "ruin_wall_blocker"
                structure_types.append([x, y, "fortress_tower"])
    fortress_plan = {
        "wall_thickness_tiles": 3,
        "towers": [
            {
                "center": {"x": 4, "y": 4},
                "radius_tiles": 3,
                "kind": "corner_round",
            },
        ],
        "materialization": {"structure_types": structure_types},
    }

    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=fortress_plan,
    )

    tower_masks = [
        result.mask_rows[y][x]
        for x, y, _name in structure_types
    ]
    assert any(0 < mask < FULL_MICRO_MASK for mask in tower_masks)
    assert result.summary["partial_micro_cells"] > 0
    assert result.summary["full_micro_cells"] > 0


def test_round_tower_micro_mask_bit_order_is_top_left_lsb() -> None:
    terrain = [
        ["grass", "grass"],
        ["grass", "ruin_wall_blocker"],
    ]
    fortress_plan = {
        "wall_thickness_tiles": 3,
        "towers": [
            {
                "center": {"x": 0, "y": 0},
                "radius_tiles": 1,
                "kind": "corner_round",
            },
        ],
        "materialization": {
            "structure_types": [[1, 1, "fortress_tower"]],
        },
    }

    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=fortress_plan,
    )

    mask = result.mask_rows[1][1]
    assert mask & 0x0001
    assert not mask & 0x8000


def test_fortress_wall_uses_partial_micro_masks_and_gate_is_open() -> None:
    terrain = [["grass" for _ in range(8)] for _ in range(5)]
    entries = []
    for x in range(1, 7):
        terrain[2][x] = "ruin_wall_blocker"
        entries.append([x, 2, "fortress_wall"])
    terrain[2][4] = "ruin_floor"
    entries.append([4, 2, "fortress_gate"])
    fortress_plan = {
        "wall_thickness_tiles": 1,
        "segments": [
            {
                "start": {"x": 1, "y": 2},
                "end": {"x": 7, "y": 2},
                "kind": "straight",
                "bend": 0.0,
            },
        ],
        "materialization": {"structure_types": entries},
    }

    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=fortress_plan,
    )

    wall_masks = [result.mask_rows[2][x] for x in (1, 2, 3, 5, 6)]
    assert any(0 < mask < FULL_MICRO_MASK for mask in wall_masks)
    assert result.mask_rows[2][4] == 0


def test_ruin_walls_use_thin_connected_micro_masks() -> None:
    terrain = [["grass" for _ in range(5)] for _ in range(5)]
    for x in range(1, 4):
        terrain[2][x] = "ruin_wall_blocker"

    result = build_structure_geometry(terrain_rows=terrain, fortress_plan=None)

    masks = [result.mask_rows[2][x] for x in range(1, 4)]
    assert all(0 < mask < FULL_MICRO_MASK for mask in masks)
    assert masks[1] == 0x0FF0


def test_fortress_keep_outline_uses_connected_micro_masks() -> None:
    terrain = [["grass" for _ in range(5)] for _ in range(5)]
    entries = []
    for x, y in ((1, 1), (2, 1), (3, 1), (1, 2), (3, 2), (1, 3), (2, 3), (3, 3)):
        terrain[y][x] = "ruin_wall_blocker"
        entries.append([x, y, "fortress_keep"])
    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan={"materialization": {"structure_types": entries}},
    )
    assert all(
        0 < result.mask_rows[y][x] < FULL_MICRO_MASK
        for x, y, _name in entries
    )
    assert result.mask_rows[2][2] == 0


def test_ruin_site_wall_runs_are_rasterized_as_one_micro_plan() -> None:
    terrain = [["grass" for _ in range(8)] for _ in range(7)]
    points = ((2, 2), (3, 2), (4, 2), (4, 3), (4, 4))
    for x, y in points:
        terrain[y][x] = "ruin_wall_blocker"
    ruin_sites = {
        "sites": [
            {
                "buildings": [
                    {
                        "architecture": {
                            "wall_runs": [
                                {"points": [[2, 2], [3, 2], [4, 2]]},
                                {"points": [[4, 2], [4, 3], [4, 4]]},
                            ]
                        }
                    }
                ]
            }
        ]
    }

    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=None,
        ruin_sites=ruin_sites,
    )

    assert result.mask_rows[2][3] == 0x0FF0
    assert result.mask_rows[3][4] == 0x6666
    assert result.mask_rows[2][4] not in {0, FULL_MICRO_MASK}
    assert result.mask_rows[2][2] != result.mask_rows[2][3]


def test_ruin_micro_damage_severity_changes_long_wall_shape() -> None:
    terrain = [["grass" for _ in range(10)] for _ in range(5)]
    points = [[x, 2] for x in range(1, 9)]
    for x, y in points:
        terrain[y][x] = "ruin_wall_blocker"

    def build(severity: str):
        return build_structure_geometry(
            terrain_rows=terrain,
            fortress_plan=None,
            ruin_sites={
                "sites": [
                    {
                        "buildings": [
                            {
                                "architecture": {
                                    "destruction_severity": severity,
                                    "wall_runs": [{"points": points}],
                                }
                            }
                        ]
                    }
                ]
            },
        )

    light = build("light")
    heavy = build("heavy")

    assert light.mask_rows[2] != heavy.mask_rows[2]
    assert sum(mask.bit_count() for mask in heavy.mask_rows[2]) < sum(
        mask.bit_count() for mask in light.mask_rows[2]
    )
    assert all(mask != 0 for mask in heavy.mask_rows[2][1:9])


def test_ruin_micro_damage_does_not_leave_singleton_subtiles() -> None:
    terrain = [["grass" for _ in range(8)] for _ in range(8)]
    points = ((2, 2), (3, 2), (4, 2), (4, 3), (4, 4), (4, 5))
    for x, y in points:
        terrain[y][x] = "ruin_wall_blocker"
    geometry = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=None,
        ruin_sites={
            "sites": [
                {
                    "buildings": [
                        {
                            "architecture": {
                                "destruction_severity": "heavy",
                                "wall_runs": [
                                    {"points": [[2, 2], [3, 2], [4, 2]]},
                                    {"points": [[4, 2], [4, 3], [4, 4], [4, 5]]},
                                ],
                            }
                        }
                    ]
                }
            ]
        },
    )
    occupied = set()
    for y, row in enumerate(geometry.mask_rows):
        for x, mask in enumerate(row):
            for sy in range(MICRO_DIVISION):
                for sx in range(MICRO_DIVISION):
                    if mask & (1 << (sy * MICRO_DIVISION + sx)):
                        occupied.add((x * MICRO_DIVISION + sx, y * MICRO_DIVISION + sy))
    assert occupied
    assert all(
        any((x + dx, y + dy) in occupied for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        for x, y in occupied
    )
