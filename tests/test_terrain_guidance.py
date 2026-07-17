from __future__ import annotations

from top_down_worldgen.legacy.engine import MapGenerator, Point, PublicConfig
from top_down_worldgen.legacy.terrain_guidance import TerrainGuidance
from top_down_worldgen.tactical.elevation import (
    build_geography_draft,
    build_natural_geography_model,
)
from top_down_worldgen.tactical.geography_guidance import write_geography_guidance


def test_geography_guidance_round_trip(tmp_path) -> None:
    draft = build_geography_draft(
        width=32,
        height=24,
        seed=12345,
        elevation_style="rolling_hills",
    )
    model = build_natural_geography_model(
        width=32,
        height=24,
        seed=12345,
        elevation_style="rolling_hills",
        geography_draft=draft,
    )
    path = tmp_path / "guidance.json"
    write_geography_guidance(model, path)

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
    assert guidance.natural_level_at(10, 10) == model.elevation_rows[10][10]
    assert guidance.natural_slope_at(10, 10) == model.slope_rows[10][10]


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


def test_guidance_classifies_barriers_wetlands_and_forest() -> None:
    width = 8
    height = 8
    elevation = tuple(tuple(0.25 for _ in range(width)) for _ in range(height))
    moisture = tuple(tuple(0.9 for _ in range(width)) for _ in range(height))
    slope = tuple(tuple(0.0 for _ in range(width)) for _ in range(height))
    natural_levels = tuple(tuple(0 for _ in range(width)) for _ in range(height))
    natural_slopes = tuple(
        tuple(3 if x == 4 else 0 for x in range(width))
        for _ in range(height)
    )
    guidance = TerrainGuidance(
        width=width,
        height=height,
        seed=1,
        elevation_style="plateau",
        elevation_rows=elevation,
        moisture_rows=moisture,
        slope_rows=slope,
        natural_level_rows=natural_levels,
        natural_slope_rows=natural_slopes,
    )

    assert guidance.is_comfortable_walk(1, 1)
    assert guidance.is_natural_barrier(4, 1)
    assert guidance.wetland_score(1, 1) > 0.58
    assert guidance.forest_suitability(1, 1) > 0.48
    assert guidance.forest_suitability(4, 1) == 0.0


def test_footprint_level_delta_uses_natural_levels() -> None:
    width = 7
    height = 7
    elevation = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    moisture = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    slope = tuple(tuple(0.0 for _ in range(width)) for _ in range(height))
    levels = tuple(
        tuple(3 if x >= 4 else 0 for x in range(width))
        for _ in range(height)
    )
    guidance = TerrainGuidance(
        width=width,
        height=height,
        seed=1,
        elevation_style="plateau",
        elevation_rows=elevation,
        moisture_rows=moisture,
        slope_rows=slope,
        natural_level_rows=levels,
    )

    assert guidance.footprint_level_delta(2, 3, 1) == 0
    assert guidance.footprint_level_delta(3, 3, 2) == 3


def test_road_metrics_distinguish_steep_from_cliff() -> None:
    width = 5
    height = 3
    flat_rows = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    zero_slope = tuple(tuple(0.0 for _ in range(width)) for _ in range(height))
    natural_slopes = (
        (0, 0, 0, 0, 0),
        (0, 1, 2, 3, 0),
        (0, 0, 0, 0, 0),
    )
    guidance = TerrainGuidance(
        width=width,
        height=height,
        seed=7,
        elevation_style="plateau",
        elevation_rows=flat_rows,
        moisture_rows=flat_rows,
        slope_rows=zero_slope,
        natural_slope_rows=natural_slopes,
    )
    config = PublicConfig(
        seed=7,
        map_width_tiles=width,
        map_height_tiles=height,
        chunk_width_tiles=1,
        chunk_height_tiles=1,
        biome_profile="forest_ruins",
    )
    generator = MapGenerator(config, terrain_guidance=guidance)

    generator._record_road_guidance_metrics(  # noqa: SLF001
        [Point(1, 1), Point(2, 1), Point(3, 1)]
    )
    metrics = generator.terrain_guidance_metrics()

    assert metrics["road_steep_tiles"] == 1
    assert metrics["road_cliff_tiles"] == 1


def test_large_map_guidance_contains_regional_base_terrain(tmp_path) -> None:
    """Ensure large maps receive deterministic regional terrain profiles."""
    draft = build_geography_draft(
        width=256,
        height=256,
        seed=24680,
        elevation_style="mountainous",
    )
    model = build_natural_geography_model(
        width=256,
        height=256,
        seed=24680,
        elevation_style="mountainous",
        geography_draft=draft,
    )
    path = tmp_path / "guidance.json"
    write_geography_guidance(model, path)

    guidance = TerrainGuidance.from_json_file(
        path,
        expected_width=256,
        expected_height=256,
        expected_seed=24680,
    )

    assert guidance.initial_terrain_rows is not None
    assert guidance.terrain_profile_count == len(draft.macro_regions)
    symbols = set("".join(guidance.initial_terrain_rows))
    assert symbols == {"+", "T"}


def test_legacy_size_map_keeps_original_forest_base(tmp_path) -> None:
    """Ensure maps up to 192 tiles keep the legacy all-forest base."""
    draft = build_geography_draft(
        width=192,
        height=192,
        seed=13579,
        elevation_style="mountainous",
    )
    model = build_natural_geography_model(
        width=192,
        height=192,
        seed=13579,
        elevation_style="mountainous",
        geography_draft=draft,
    )
    path = tmp_path / "guidance.json"
    write_geography_guidance(model, path)

    guidance = TerrainGuidance.from_json_file(
        path,
        expected_width=192,
        expected_height=192,
        expected_seed=13579,
    )

    assert guidance.initial_terrain_rows is None


def test_map_generator_uses_regional_base_rows() -> None:
    """Ensure the legacy generator consumes the compact regional base mask."""
    width = 96
    height = 80
    flat_rows = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    zero_slope = tuple(tuple(0.0 for _ in range(width)) for _ in range(height))
    base_rows = tuple(
        "+" * (width // 2) + "T" * (width - width // 2)
        for _ in range(height)
    )
    guidance = TerrainGuidance(
        width=width,
        height=height,
        seed=5,
        elevation_style="flatland",
        elevation_rows=flat_rows,
        moisture_rows=flat_rows,
        slope_rows=zero_slope,
        initial_terrain_rows=base_rows,
        terrain_profile_count=2,
    )
    config = PublicConfig(
        seed=5,
        map_width_tiles=width,
        map_height_tiles=height,
        chunk_width_tiles=16,
        chunk_height_tiles=16,
        biome_profile="forest_ruins",
    )
    generator = MapGenerator(config, terrain_guidance=guidance)

    generator._fill_forest()  # noqa: SLF001
    rows = generator._grid.rows_as_text()  # noqa: SLF001
    metrics = generator.terrain_guidance_metrics()

    assert all(row[: width // 2] == "+" * (width // 2) for row in rows)
    assert all(row[width // 2 :] == "T" * (width - width // 2) for row in rows)
    assert metrics["regional_terrain_enabled"] is True
    assert metrics["terrain_profile_count"] == 2
    assert metrics["initial_tree_percent"] == 50.0
