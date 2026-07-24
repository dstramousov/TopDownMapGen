from __future__ import annotations

from top_down_worldgen.legacy.engine import (
    DerivedConfig,
    GenerationTuning,
    MapGenerator,
    Point,
    PublicConfig,
    Rect,
    Region,
    RegionKind,
    RuinSiteKind,
)
from top_down_worldgen.legacy.terrain_guidance import TerrainGuidance
from top_down_worldgen.tactical.runtime_objects import _ruin_site_reserved_positions
from top_down_worldgen.validation import (
    _ruin_site_foundations_flat,
    _ruin_sites_valid,
)


def _config(
    size: int,
    *,
    tuning: GenerationTuning | None = None,
) -> PublicConfig:
    """Return a stable square legacy-engine configuration."""
    return PublicConfig(
        seed=12345,
        map_width_tiles=size,
        map_height_tiles=size,
        chunk_width_tiles=16,
        chunk_height_tiles=16,
        biome_profile="forest_ruins",
        generation_tuning=tuning or GenerationTuning(),
    )


def _guidance(
    width: int,
    height: int,
    *,
    default_level: int,
    overrides: dict[tuple[int, int], int] | None = None,
) -> TerrainGuidance:
    """Return guidance with explicit integer natural levels."""
    overrides = overrides or {}
    natural_levels = tuple(
        tuple(overrides.get((x, y), default_level) for x in range(width))
        for y in range(height)
    )
    normalized = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    zero_slope = tuple(tuple(0.0 for _ in range(width)) for _ in range(height))
    natural_slopes = tuple(tuple(0 for _ in range(width)) for _ in range(height))
    return TerrainGuidance(
        width=width,
        height=height,
        seed=12345,
        elevation_style="flatland",
        elevation_rows=normalized,
        moisture_rows=normalized,
        slope_rows=zero_slope,
        natural_level_rows=natural_levels,
        natural_slope_rows=natural_slopes,
    )


def test_ruin_site_budget_scales_with_map_area() -> None:
    """Ensure site frequency and building budget grow with map area."""
    small = DerivedConfig.from_public(_config(192))
    medium = DerivedConfig.from_public(_config(320))
    large = DerivedConfig.from_public(_config(400))

    assert (small.village_site_count, small.ruin_building_budget) == (1, 15)
    assert (medium.village_site_count, medium.ruin_building_budget) == (2, 41)
    assert (large.village_site_count, large.ruin_building_budget) == (2, 64)
    assert small.isolated_site_count < medium.isolated_site_count < large.isolated_site_count


def test_zero_ruins_scale_disables_sites_and_buildings() -> None:
    """Ensure public ruins_scale=0 removes all planned ruin content."""
    derived = DerivedConfig.from_public(
        _config(320, tuning=GenerationTuning(ruins_scale=0.0)),
    )

    assert derived.village_site_count == 0
    assert derived.isolated_site_count == 0
    assert derived.farmstead_site_count == 0
    assert derived.outpost_site_count == 0
    assert derived.ruin_building_budget == 0


def test_flat_foundation_requires_one_nonnegative_natural_level() -> None:
    """Accept a flat footprint and reject one mixed or negative level."""
    rect = Rect(20, 20, 29, 27)
    flat = MapGenerator(
        _config(96),
        terrain_guidance=_guidance(96, 96, default_level=4),
    )
    mixed = MapGenerator(
        _config(96),
        terrain_guidance=_guidance(
            96,
            96,
            default_level=4,
            overrides={(24, 24): 5},
        ),
    )
    negative = MapGenerator(
        _config(96),
        terrain_guidance=_guidance(96, 96, default_level=-1),
    )

    assert flat._flat_foundation_level(rect) == 4  # noqa: SLF001
    assert mixed._flat_foundation_level(rect) is None  # noqa: SLF001
    assert negative._flat_foundation_level(rect) is None  # noqa: SLF001


def test_building_budget_is_grouped_into_semantic_sites() -> None:
    """Ensure the allocator favors villages while keeping isolated sites singular."""
    generator = MapGenerator(_config(320))
    kinds = (
        RuinSiteKind.VILLAGE,
        RuinSiteKind.VILLAGE,
        RuinSiteKind.FARMSTEAD,
        RuinSiteKind.FARMSTEAD,
        RuinSiteKind.OUTPOST,
        RuinSiteKind.ISOLATED_BUILDING,
        RuinSiteKind.ISOLATED_BUILDING,
        RuinSiteKind.ISOLATED_BUILDING,
        RuinSiteKind.ISOLATED_BUILDING,
        RuinSiteKind.ISOLATED_BUILDING,
        RuinSiteKind.ISOLATED_BUILDING,
    )
    regions = [
        Region(
            region_id=index,
            center=Point(20 + index, 20),
            kind=RegionKind.SMALL_RUIN,
            ruin_site_kind=kind,
        )
        for index, kind in enumerate(kinds)
    ]

    counts = generator._allocate_site_building_counts(regions)  # noqa: SLF001

    assert sum(counts.values()) == generator._derived.ruin_building_budget  # noqa: SLF001
    assert all(counts[index] == 1 for index in range(5, 11))
    assert counts[0] >= counts[2] >= counts[4] > counts[5]
    assert counts[1] >= counts[3]


def test_ruin_site_metadata_reserves_foundations_and_validates_levels() -> None:
    """Ensure runtime placement and validation honor planned foundations."""
    site = {
        "id": 0,
        "region_id": 3,
        "type": "farmstead",
        "center": [12, 12],
        "road_anchor": [9, 12],
        "orientation": "east_west",
        "architectural_profile": "rural_cluster",
        "requested_buildings": 1,
        "placed_buildings": 1,
        "buildings": [
            {
                "id": 0,
                "rect": {"left": 10, "top": 10, "right": 13, "bottom": 12},
                "foundation_elevation": 4,
                "entrance": [10, 11],
                "outside_approach": [9, 11],
                "orientation": "east_west",
                "is_main": True,
            },
        ],
    }
    runtime_data = {
        "ruin_sites": {
            "schema_version": "ruin-site-plan-v1",
            "sites": [site],
        },
        "elevation": {
            "default": 0,
            "cells": [
                {"x": x, "y": y, "level": 4}
                for y in range(10, 13)
                for x in range(10, 14)
            ]
            + [{"x": 9, "y": 11, "level": 4}],
        },
    }

    assert _ruin_sites_valid(runtime_data, width=32, height=32)
    assert _ruin_site_foundations_flat(runtime_data, width=32, height=32)
    reserved = _ruin_site_reserved_positions(runtime_data)
    assert (10, 10) in reserved
    assert (13, 12) in reserved
    assert (9, 11) in reserved

    runtime_data["elevation"]["cells"][0]["level"] = 5
    assert not _ruin_site_foundations_flat(runtime_data, width=32, height=32)


def test_ruin_site_planning_is_deterministic_for_same_seed() -> None:
    """Ensure identical inputs create identical semantic site metadata."""
    width = 96
    height = 96
    guidance = _guidance(width, height, default_level=3)
    first = MapGenerator(_config(width), terrain_guidance=guidance)
    second = MapGenerator(_config(width), terrain_guidance=guidance)

    first.generate()
    second.generate()

    assert first.ruin_sites_metadata() == second.ruin_sites_metadata()
    assert first.ruin_foundation_cells() == second.ruin_foundation_cells()
