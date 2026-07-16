from __future__ import annotations

from top_down_worldgen.legacy.engine import MapGenerator, PublicConfig
from top_down_worldgen.legacy.terrain_guidance import TerrainGuidance
from top_down_worldgen.tactical.elevation import build_geography_draft
from top_down_worldgen.tactical.geography_guidance import write_geography_guidance


def test_geography_guidance_round_trip(tmp_path) -> None:
    draft = build_geography_draft(
        width=32,
        height=24,
        seed=12345,
        elevation_style="rolling_hills",
    )
    path = tmp_path / "guidance.json"
    write_geography_guidance(draft, path)

    guidance = TerrainGuidance.from_json_file(
        path,
        expected_width=32,
        expected_height=24,
        expected_seed=12345,
    )

    assert guidance.elevation_style == "rolling_hills"
    assert 0.0 <= guidance.elevation_at(10, 10) <= 1.0
    assert 0.0 <= guidance.moisture_at(10, 10) <= 1.0
    assert guidance.slope_at(10, 10) >= 0.0


def test_guided_road_path_avoids_coarse_cliff_barrier() -> None:
    width = 40
    height = 40
    elevation = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    moisture = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    slope_rows = []
    for y in range(height):
        row = []
        for x in range(width):
            blocked = 16 <= x <= 23 and not 14 <= y <= 25
            row.append(0.25 if blocked else 0.0)
        slope_rows.append(tuple(row))
    guidance = TerrainGuidance(
        width=width,
        height=height,
        seed=1,
        elevation_style="plateau",
        elevation_rows=elevation,
        moisture_rows=moisture,
        slope_rows=tuple(slope_rows),
    )

    path = guidance.road_path((2, 2), (37, 37), step=4)

    assert path
    assert all(guidance.slope_at(x, y) < guidance.CLIFF_SLOPE for x, y in path[1:-1])
    assert any(14 <= y <= 25 for x, y in path if 16 <= x <= 23)


def test_map_generator_uses_flat_guidance_for_roads() -> None:
    width = 96
    height = 80
    flat_rows = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    zero_slope = tuple(tuple(0.0 for _ in range(width)) for _ in range(height))
    guidance = TerrainGuidance(
        width=width,
        height=height,
        seed=9876,
        elevation_style="flatland",
        elevation_rows=flat_rows,
        moisture_rows=flat_rows,
        slope_rows=zero_slope,
    )
    config = PublicConfig(
        seed=9876,
        map_width_tiles=width,
        map_height_tiles=height,
        chunk_width_tiles=16,
        chunk_height_tiles=16,
        biome_profile="forest_ruins",
    )

    generator = MapGenerator(config, terrain_guidance=guidance)
    generator.generate()
    metrics = generator.terrain_guidance_metrics()

    assert metrics["enabled"] is True
    assert int(metrics["guided_road_routes"]) > 0
    assert int(metrics["road_cliff_tiles"]) == 0
