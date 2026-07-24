from __future__ import annotations

from top_down_worldgen.legacy.engine import (
    MapGenerator,
    MapValidator,
    Point,
    PublicConfig,
    Region,
    RegionKind,
    TileType,
)


def _make_generator() -> MapGenerator:
    """Create a tiny generator with stable critical regions."""
    generator = MapGenerator(
        PublicConfig(
            seed=1,
            map_width_tiles=24,
            map_height_tiles=16,
            chunk_width_tiles=8,
            chunk_height_tiles=8,
            biome_profile="forest_ruins",
        ),
    )
    generator._regions = [  # noqa: SLF001
        Region(0, Point(1, 1), RegionKind.START),
        Region(1, Point(3, 1), RegionKind.CENTRAL_RUIN_CLEARING),
        Region(2, Point(5, 1), RegionKind.GOAL),
    ]
    generator._start_region_id = 0  # noqa: SLF001
    generator._central_region_id = 1  # noqa: SLF001
    generator._goal_region_id = 2  # noqa: SLF001
    return generator


def _paint_points(generator: MapGenerator, points: set[Point], tile: TileType) -> None:
    """Paint exact points on the private test grid."""
    for point in points:
        generator._grid.set_tile(point, tile)  # noqa: SLF001


def test_connectivity_diagnostic_preserves_small_isolated_component() -> None:
    """Ensure diagnostics do not remove disconnected walkable islands."""
    generator = _make_generator()
    main = {Point(x, 1) for x in range(1, 6)}
    island = {Point(12, 8), Point(13, 8), Point(12, 9)}
    _paint_points(generator, main, TileType.GRASS)
    _paint_points(generator, island, TileType.GRASS)

    generator._repair_walkable_connectivity()  # noqa: SLF001

    assert len(MapValidator(generator._grid).components()) == 2  # noqa: SLF001
    assert all(
        generator._grid.get_tile(point) == TileType.GRASS  # noqa: SLF001
        for point in island
    )
    metrics = generator.connectivity_repair_metrics()
    assert metrics["diagnostic_only"] == 1
    assert metrics["filled_components"] == 0
    assert metrics["tiles_changed"] == 0


def test_connectivity_diagnostic_does_not_carve_connector() -> None:
    """Ensure diagnostics do not connect large disconnected components."""
    generator = _make_generator()
    main = {Point(x, 1) for x in range(1, 6)}
    large_island = {Point(x, y) for x in range(12, 18) for y in range(6, 12)}
    _paint_points(generator, main, TileType.GRASS)
    _paint_points(generator, large_island, TileType.GRASS)

    generator._repair_walkable_connectivity()  # noqa: SLF001
    metrics = generator.connectivity_repair_metrics()

    assert len(MapValidator(generator._grid).components()) == 2  # noqa: SLF001
    assert metrics["diagnostic_only"] == 1
    assert metrics["connected_components"] == 0
    assert metrics["tiles_changed"] == 0
    assert metrics["failed_repairs"] == 0


def test_traversal_repair_reports_change_breakdown() -> None:
    from top_down_worldgen.tactical.elevation import _repair_change_diagnostics

    diagnostics = _repair_change_diagnostics(
        {(0, 0): (4, 2), (1, 0): (0, 1), (2, 0): (3, 3)},
        terrain_rows=[".+R"],
        total_tiles=6,
        two_d_reachable_tiles=3,
    )

    assert diagnostics["adjusted_by_terrain"] == {
        "open_ground": 1,
        "road": 1,
        "ruin_floor": 1,
    }
    assert diagnostics["direction"] == {"raised": 1, "lowered": 1}
    assert diagnostics["magnitude"]["maximum_abs_delta"] == 2
    assert diagnostics["coverage"]["percent_of_map"] == 50.0


def test_start_goal_placement_does_not_carve_terrain() -> None:
    """Ensure marker placement changes only the two selected tiles."""
    generator = _make_generator()
    before = {
        Point(x, y): generator._grid.get_tile(Point(x, y))  # noqa: SLF001
        for y in range(generator._grid.height)  # noqa: SLF001
        for x in range(generator._grid.width)  # noqa: SLF001
    }
    _paint_points(
        generator,
        {Point(1, 1), Point(5, 1)},
        TileType.GRASS,
    )
    before[Point(1, 1)] = TileType.GRASS
    before[Point(5, 1)] = TileType.GRASS

    generator._place_start_goal()  # noqa: SLF001

    changed = {
        point
        for point, tile in before.items()
        if generator._grid.get_tile(point) != tile  # noqa: SLF001
    }
    assert changed == {Point(1, 1), Point(5, 1)}
    assert generator._grid.get_tile(Point(1, 1)) == TileType.START  # noqa: SLF001
    assert generator._grid.get_tile(Point(5, 1)) == TileType.GOAL  # noqa: SLF001
