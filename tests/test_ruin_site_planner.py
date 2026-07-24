from __future__ import annotations

from top_down_worldgen.legacy.engine import (
    GenerationTuning,
    MapGenerator,
    Point,
    PublicConfig,
    Rect,
    Region,
    RegionKind,
    RuinSiteKind,
)
from top_down_worldgen.legacy.settlement_context import (
    SettlementBudgets,
    SettlementProfile,
    allocate_settlement_budgets,
    analyze_settlement_terrain,
    reserve_landmark,
    select_settlement_profile,
    select_settlement_regions,
    site_kind_sequence,
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
    elevation_style: str = "flatland",
    overrides: dict[tuple[int, int], int] | None = None,
    default_slope: int = 0,
    slope_overrides: dict[tuple[int, int], int] | None = None,
) -> TerrainGuidance:
    """Return guidance with explicit integer natural levels and slopes."""
    overrides = overrides or {}
    slope_overrides = slope_overrides or {}
    natural_levels = tuple(
        tuple(overrides.get((x, y), default_level) for x in range(width))
        for y in range(height)
    )
    natural_slopes = tuple(
        tuple(slope_overrides.get((x, y), default_slope) for x in range(width))
        for y in range(height)
    )
    normalized = tuple(tuple(0.5 for _ in range(width)) for _ in range(height))
    zero_slope = tuple(tuple(0.0 for _ in range(width)) for _ in range(height))
    return TerrainGuidance(
        width=width,
        height=height,
        seed=12345,
        elevation_style=elevation_style,
        elevation_rows=normalized,
        moisture_rows=normalized,
        slope_rows=zero_slope,
        natural_level_rows=natural_levels,
        natural_slope_rows=natural_slopes,
    )


def _mountain_guidance(size: int, *, with_plateau: bool) -> TerrainGuidance:
    """Return synthetic mountainous terrain with an optional high plateau."""
    level_overrides: dict[tuple[int, int], int] = {}
    slope_overrides: dict[tuple[int, int], int] = {}
    if with_plateau:
        for y in range(size // 4, size * 3 // 4):
            for x in range(size // 4, size * 3 // 4):
                level_overrides[(x, y)] = 12
                slope_overrides[(x, y)] = 0
        for y in range(8, max(16, size // 4)):
            for x in range(8, max(20, size // 3)):
                level_overrides[(x, y)] = 1
                slope_overrides[(x, y)] = 0
    return _guidance(
        size,
        size,
        default_level=4,
        elevation_style="mountainous",
        overrides=level_overrides,
        default_slope=2,
        slope_overrides=slope_overrides,
    )


def test_settlement_budgets_scale_by_linear_map_size() -> None:
    """Ensure density grows sublinearly instead of tracking map area."""
    budgets = []
    for size in (192, 320, 400):
        context = analyze_settlement_terrain(
            _guidance(size, size, default_level=3),
            width=size,
            height=size,
        )
        budgets.append(
            allocate_settlement_budgets(
                context,
                SettlementProfile.RURAL_PLAIN,
                width=size,
                height=size,
                ruins_scale=1.0,
                buildings_scale=1.0,
                seed=12345,
            )
        )

    assert budgets[0].site_budget < budgets[1].site_budget <= budgets[2].site_budget
    assert budgets[0].building_budget < budgets[1].building_budget < budgets[2].building_budget
    assert budgets[2].building_budget / budgets[0].building_budget < 3.0


def test_zero_ruins_scale_disables_sites_buildings_and_landmark() -> None:
    """Ensure ruins_scale=0 disables all settlement budgets."""
    generator = MapGenerator(
        _config(320, tuning=GenerationTuning(ruins_scale=0.0)),
        terrain_guidance=_guidance(320, 320, default_level=3),
    )

    generator._prepare_settlement_strategy()  # noqa: SLF001

    assert generator._settlement_budgets == SettlementBudgets(0, 0, 0)  # noqa: SLF001
    assert generator._landmark_reservation is None  # noqa: SLF001


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


def test_building_budget_is_an_upper_limit_with_small_archetype_caps() -> None:
    """Ensure site capacities can leave part of the building budget unused."""
    generator = MapGenerator(_config(320))
    generator._settlement_budgets = SettlementBudgets(11, 40, 0)  # noqa: SLF001
    generator._settlement_context = analyze_settlement_terrain(  # noqa: SLF001
        None,
        width=320,
        height=320,
    )
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

    assert 0 < sum(counts.values()) < 40
    assert all(6 <= counts[index] <= 9 for index in (0, 1))
    assert all(2 <= counts[index] <= 3 for index in (2, 3))
    assert 1 <= counts[4] <= 2
    assert all(counts[index] == 1 for index in range(5, 11))


def test_elevation_profile_controls_settlement_pattern_and_landmark() -> None:
    """Ensure high mountainous terrain reserves a stronghold and stays sparse."""
    flat_context = analyze_settlement_terrain(
        _guidance(400, 400, default_level=3, elevation_style="flatland"),
        width=400,
        height=400,
    )
    mountain_context = analyze_settlement_terrain(
        _mountain_guidance(160, with_plateau=True),
        width=160,
        height=160,
    )
    mountain_profile = select_settlement_profile(mountain_context, seed=12345)
    flat_budget = allocate_settlement_budgets(
        flat_context,
        SettlementProfile.RURAL_PLAIN,
        width=400,
        height=400,
        ruins_scale=1.0,
        buildings_scale=1.0,
        seed=12345,
    )
    mountain_budget = allocate_settlement_budgets(
        mountain_context,
        mountain_profile,
        width=400,
        height=400,
        ruins_scale=1.0,
        buildings_scale=1.0,
        seed=12345,
    )
    landmark = reserve_landmark(
        mountain_context,
        mountain_profile,
        budget=mountain_budget.landmark_budget,
        width=160,
        height=160,
    )
    ordinary_regions = select_settlement_regions(
        mountain_context,
        mountain_profile,
        width=160,
        height=160,
        seed=12345,
    )

    assert mountain_profile == SettlementProfile.MOUNTAIN_STRONGHOLD
    assert mountain_budget.site_budget < flat_budget.site_budget
    assert mountain_budget.building_budget < flat_budget.building_budget
    assert landmark is not None
    assert landmark.landmark_type == "mountain_fortress"
    assert all(
        (region.center_x, region.center_y)
        != (landmark.center_x, landmark.center_y)
        for region in ordinary_regions
    )


def test_mountain_without_flat_high_ground_does_not_reserve_fortress() -> None:
    """Ensure rough mountains do not invent an impossible landmark footprint."""
    context = analyze_settlement_terrain(
        _mountain_guidance(96, with_plateau=False),
        width=96,
        height=96,
    )
    profile = select_settlement_profile(context, seed=12345)
    budgets = allocate_settlement_budgets(
        context,
        profile,
        width=96,
        height=96,
        ruins_scale=1.0,
        buildings_scale=1.0,
        seed=12345,
    )

    assert profile == SettlementProfile.SPARSE_FRONTIER
    assert budgets.landmark_budget == 0
    assert reserve_landmark(
        context,
        profile,
        budget=budgets.landmark_budget,
        width=96,
        height=96,
    ) is None


def test_rugged_profile_does_not_force_a_village() -> None:
    """Ensure difficult terrain may consist only of small sites and outposts."""
    kinds = site_kind_sequence(
        SettlementProfile.RUGGED_OUTPOSTS,
        site_budget=5,
        valley_candidates=0,
    )

    assert "village" not in kinds
    assert kinds[0] == "outpost"


def test_settlement_regions_cluster_sites_in_limited_world_areas() -> None:
    """Ensure broad settlement areas do not cover the entire large map."""
    context = analyze_settlement_terrain(
        _guidance(400, 400, default_level=2),
        width=400,
        height=400,
    )
    regions = select_settlement_regions(
        context,
        SettlementProfile.RURAL_PLAIN,
        width=400,
        height=400,
        seed=12345,
    )

    assert 1 <= len(regions) <= 2
    assert all(region.radius <= 100 for region in regions)
    assert sum(3.1416 * region.radius * region.radius for region in regions) < 160000


def test_legacy_ruin_site_metadata_remains_valid() -> None:
    """Ensure runtime placement still accepts v1 planner metadata."""
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
    """Ensure identical inputs create identical v2 settlement metadata."""
    width = 96
    height = 96
    guidance = _guidance(width, height, default_level=3)
    first = MapGenerator(_config(width), terrain_guidance=guidance)
    second = MapGenerator(_config(width), terrain_guidance=guidance)

    first.generate()
    second.generate()

    first_metadata = first.ruin_sites_metadata()
    second_metadata = second.ruin_sites_metadata()
    assert first_metadata["schema_version"] == "ruin-site-plan-v2"
    assert first_metadata == second_metadata
    assert first.ruin_foundation_cells() == second.ruin_foundation_cells()
    runtime_data = {
        "ruin_sites": first_metadata,
        "elevation": {
            "default": 0,
            "cells": first.ruin_foundation_cells(),
        },
    }
    assert _ruin_sites_valid(runtime_data, width=width, height=height)
    assert _ruin_site_foundations_flat(runtime_data, width=width, height=height)
