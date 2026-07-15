from top_down_worldgen.tactical.river import RiverConfig, RiverGenerator


def _rows(width: int, height: int) -> list[str]:
    return ["." * width for _ in range(height)]


def test_river_is_deterministic_and_crosses_map() -> None:
    rows = _rows(48, 32)
    elevation = [[max(0, 8 - x // 6) for x in range(48)] for _ in range(32)]
    config = RiverConfig(enabled=True, channel_width_min=3, channel_width_max=5)

    first = RiverGenerator().generate(rows=rows, elevation_grid=elevation, seed=123, config=config)
    second = RiverGenerator().generate(rows=rows, elevation_grid=elevation, seed=123, config=config)

    assert first.centerline == second.centerline
    assert first.terrain_rows == second.terrain_rows
    assert first.report["summary"]["touches_map_edge"] is True
    assert first.report["summary"]["river_tiles"] > 0


def test_small_connected_lowland_is_flooded() -> None:
    rows = _rows(40, 24)
    elevation = [[2 for _ in range(40)] for _ in range(24)]
    for y in range(8, 16):
        for x in range(14, 26):
            elevation[y][x] = -1
    config = RiverConfig(
        enabled=True,
        channel_width_min=1,
        channel_width_max=1,
        max_flood_area_ratio=0.2,
        max_flood_distance=20,
    )

    result = RiverGenerator().generate(rows=rows, elevation_grid=elevation, seed=7, config=config)

    assert result.report["summary"]["flooded_tiles"] > 0


def test_large_basin_is_not_fully_flooded() -> None:
    rows = _rows(60, 40)
    elevation = [[0 for _ in range(60)] for _ in range(40)]
    config = RiverConfig(
        enabled=True,
        channel_width_min=1,
        channel_width_max=1,
        max_flood_area_ratio=0.01,
        max_flood_distance=50,
    )

    result = RiverGenerator().generate(rows=rows, elevation_grid=elevation, seed=91, config=config)

    assert result.report["summary"]["flooded_tiles"] <= 24
    assert result.report["summary"]["river_area_ratio"] < 0.2


def test_disabled_generator_is_noop() -> None:
    rows = _rows(20, 10)
    elevation = [[0 for _ in range(20)] for _ in range(10)]

    result = RiverGenerator().generate(
        rows=rows,
        elevation_grid=elevation,
        seed=1,
        config=RiverConfig(enabled=False),
    )

    assert result.terrain_rows == rows
    assert not result.centerline
    assert result.report["summary"]["river_tiles"] == 0
