from top_down_worldgen.structure_top_geometry import build_structure_top_geometry
from top_down_worldgen.structure_geometry import (
    FULL_MICRO_MASK,
    MICRO_DIVISION,
    STRUCTURE_TYPE_NAMES,
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

    occupied = {
        (tile_x * MICRO_DIVISION + subtile_x, tile_y * MICRO_DIVISION + subtile_y)
        for tile_y, row in enumerate(result.mask_rows)
        for tile_x, mask in enumerate(row)
        for subtile_y in range(MICRO_DIVISION)
        for subtile_x in range(MICRO_DIVISION)
        if mask & (1 << (subtile_y * MICRO_DIVISION + subtile_x))
    }
    cross_section = {micro_y for micro_x, micro_y in occupied if micro_x == 9}
    assert len(cross_section) == 6
    assert result.mask_rows[2][4] == 0


def test_ruin_walls_use_thin_connected_micro_masks() -> None:
    terrain = [["grass" for _ in range(5)] for _ in range(5)]
    for x in range(1, 4):
        terrain[2][x] = "ruin_wall_blocker"

    result = build_structure_geometry(terrain_rows=terrain, fortress_plan=None)

    masks = [result.mask_rows[2][x] for x in range(1, 4)]
    assert all(0 < mask < FULL_MICRO_MASK for mask in masks)
    assert masks[1] == 0x0FF0


def test_fortress_keep_is_solid_and_uses_full_roof_footprint() -> None:
    terrain = [["grass" for _ in range(5)] for _ in range(5)]
    entries = []
    for x, y in ((1, 1), (2, 1), (3, 1), (1, 2), (3, 2), (1, 3), (2, 3), (3, 3)):
        terrain[y][x] = "ruin_wall_blocker"
        entries.append([x, y, "fortress_keep"])
    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan={"materialization": {"structure_types": entries}},
    )
    assert all(result.mask_rows[y][x] for x, y, _name in entries)
    assert result.type_rows[2][2] == 13
    assert result.mask_rows[2][2] == FULL_MICRO_MASK


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


def test_fortress_shell_does_not_continue_wall_through_tower_interior() -> None:
    terrain = [["grass" for _ in range(11)] for _ in range(7)]
    entries = []
    for y in range(1, 6):
        for x in range(3, 8):
            distance_squared = (x - 5) ** 2 + (y - 3) ** 2
            if 1 < distance_squared <= 9:
                terrain[y][x] = "ruin_wall_blocker"
                entries.append([x, y, "fortress_tower"])
    for x in range(1, 5):
        terrain[3][x] = "ruin_wall_blocker"
        entries.append([x, 3, "fortress_wall"])

    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan={
            "segments": [
                {
                    "start": {"x": 1, "y": 3},
                    "end": {"x": 5, "y": 3},
                    "kind": "straight",
                    "bend": 0.0,
                }
            ],
            "towers": [
                {
                    "center": {"x": 5, "y": 3},
                    "radius_tiles": 3,
                    "kind": "corner_round",
                }
            ],
            "materialization": {"structure_types": entries},
        },
    )

    assert result.type_rows[3][4] == next(
        type_id
        for type_id, name in STRUCTURE_TYPE_NAMES.items()
        if name == "fortress_tower"
    )
    assert result.mask_rows[3][5] == FULL_MICRO_MASK


def test_fortress_top_geometry_has_flat_roof_and_outer_crenellations() -> None:
    terrain = [["grass" for _ in range(8)] for _ in range(8)]
    fortress_plan = {
        "segments": [
            {"start": {"x": 1, "y": 3}, "end": {"x": 6, "y": 3}}
        ],
        "towers": [],
        "materialization": {
            "structure_types": [[x, 3, "fortress_wall"] for x in range(1, 7)]
        },
    }
    geometry = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=fortress_plan,
    )
    top = build_structure_top_geometry(geometry)

    assert top.summary["temporarily_disabled"] == 0
    assert any(mask for row in top.walkway_rows for mask in row)
    assert any(mask for row in top.parapet_rows for mask in row)
    assert any(mask for row in top.crenellation_rows for mask in row)
    assert top.summary["wall_crenellation_subtiles"] > 0


def test_curved_fortress_wall_uses_one_continuous_micro_band() -> None:
    terrain = [["grass" for _ in range(16)] for _ in range(16)]
    geometry = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan={
            "segments": [
                {
                    "start": {"x": 2, "y": 8},
                    "end": {"x": 13, "y": 8},
                    "kind": "gentle_curve",
                    "bend": 0.22,
                }
            ],
            "towers": [],
            "materialization": {"structure_types": []},
        },
    )

    occupied = _test_micro_points(geometry)
    assert occupied
    assert len(_test_cardinal_components(occupied)) == 1
    row_counts = {
        y: sum(1 for _x, point_y in occupied if point_y == y)
        for y in {point_y for _x, point_y in occupied}
    }
    assert max(row_counts.values()) > min(row_counts.values())


def test_fortress_wall_thickness_scales_from_tower_diameter() -> None:
    terrain = [["grass" for _ in range(20)] for _ in range(20)]
    geometry = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan={
            "segments": [
                {
                    "start": {"x": 3, "y": 10},
                    "end": {"x": 16, "y": 10},
                    "kind": "straight",
                    "bend": 0.0,
                }
            ],
            "towers": [
                {
                    "center": {"x": 16, "y": 10},
                    "radius_tiles": 3,
                    "kind": "corner_round",
                }
            ],
            "materialization": {"structure_types": []},
        },
    )

    wall_id = next(
        type_id
        for type_id, name in STRUCTURE_TYPE_NAMES.items()
        if name == "fortress_wall"
    )
    points = _test_micro_points(geometry, type_id=wall_id)
    sample_x = 8 * MICRO_DIVISION + 1
    ys = {y for x, y in points if x == sample_x}
    assert len(ys) >= 11


def test_round_tower_body_is_symmetric_and_not_deformed_by_wall() -> None:
    terrain = [["grass" for _ in range(17)] for _ in range(13)]
    geometry = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan={
            "segments": [
                {
                    "start": {"x": 1, "y": 6},
                    "end": {"x": 8, "y": 6},
                    "kind": "straight",
                    "bend": 0.0,
                }
            ],
            "towers": [
                {
                    "center": {"x": 9, "y": 6},
                    "radius_tiles": 3,
                    "kind": "corner_round",
                }
            ],
            "materialization": {"structure_types": []},
        },
    )

    tower_id = next(
        type_id
        for type_id, name in STRUCTURE_TYPE_NAMES.items()
        if name == "fortress_tower"
    )
    points = _test_micro_points(geometry, type_id=tower_id)
    axis_x_twice = 2 * 9 * MICRO_DIVISION + 3
    reflected = {(axis_x_twice - x, y) for x, y in points}
    assert points == reflected
    assert any(
        x in {9 * MICRO_DIVISION + 1, 9 * MICRO_DIVISION + 2}
        and y in {6 * MICRO_DIVISION + 1, 6 * MICRO_DIVISION + 2}
        for x, y in points
    )


def _test_micro_points(
    geometry,
    *,
    type_id: int | None = None,
) -> set[tuple[int, int]]:
    points: set[tuple[int, int]] = set()
    for tile_y, row in enumerate(geometry.mask_rows):
        for tile_x, mask in enumerate(row):
            if type_id is not None and geometry.type_rows[tile_y][tile_x] != type_id:
                continue
            for subtile_y in range(MICRO_DIVISION):
                for subtile_x in range(MICRO_DIVISION):
                    bit = 1 << (subtile_y * MICRO_DIVISION + subtile_x)
                    if mask & bit:
                        points.add(
                            (
                                tile_x * MICRO_DIVISION + subtile_x,
                                tile_y * MICRO_DIVISION + subtile_y,
                            )
                        )
    return points


def _test_cardinal_components(
    points: set[tuple[int, int]],
) -> list[set[tuple[int, int]]]:
    remaining = set(points)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        seed = next(iter(remaining))
        component = {seed}
        stack = [seed]
        remaining.remove(seed)
        while stack:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (x + dx, y + dy)
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                component.add(neighbor)
                stack.append(neighbor)
        components.append(component)
    return components


def _test_exterior_points(occupied: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """Return empty points connected to the outside of a test bounding box."""
    min_x = min(x for x, _y in occupied) - 1
    max_x = max(x for x, _y in occupied) + 1
    min_y = min(y for _x, y in occupied) - 1
    max_y = max(y for _x, y in occupied) + 1
    exterior = {(min_x, min_y)}
    queue = [(min_x, min_y)]
    while queue:
        x, y = queue.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor
            if not (min_x <= nx <= max_x and min_y <= ny <= max_y):
                continue
            if neighbor in occupied or neighbor in exterior:
                continue
            exterior.add(neighbor)
            queue.append(neighbor)
    return exterior


def test_gate_metadata_does_not_cut_a_tower_disk() -> None:
    """Ensure a coarse gate tile cannot punch a hole through a tower."""
    terrain = [["grass" for _ in range(9)] for _ in range(9)]
    fortress_plan = {
        "segments": [
            {
                "start": {"x": 1, "y": 4},
                "end": {"x": 8, "y": 4},
                "kind": "straight",
                "bend": 0.0,
            }
        ],
        "towers": [
            {
                "center": {"x": 4, "y": 4},
                "radius_tiles": 3,
                "kind": "gate_round",
            }
        ],
        "gate_center": {"x": 4, "y": 4},
        "gate_width_tiles": 2,
        "materialization": {
            "structure_types": [[4, 4, "fortress_gate"]],
        },
    }

    result = build_structure_geometry(
        terrain_rows=terrain,
        fortress_plan=fortress_plan,
    )

    assert result.type_rows[4][4] == 11
    assert result.mask_rows[4][4] == FULL_MICRO_MASK
