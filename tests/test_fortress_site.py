from __future__ import annotations

from top_down_worldgen.config import FortressConfig
from top_down_worldgen.tactical.fortress_site import (
    analyze_lake_island_fortress_site,
)


def _enabled_config() -> FortressConfig:
    return FortressConfig.from_raw(
        {
            "enabled": True,
            "archetype": "lake_island",
            "max_count": 1,
            "lake_island": {"enabled": True},
        },
    )


def _lake_grid(*, width: int, height: int, margin: int) -> list[list[int]]:
    rows = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(margin, height - margin):
        for x in range(margin, width - margin):
            rows[y][x] = -3
    return rows


def test_lake_island_site_selects_large_flatland_lake() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=20)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "selected"
    assert report["summary"]["lake_components"] == 1
    assert report["summary"]["eligible_components"] == 1
    selected = report["selected_site"]
    assert selected is not None
    assert selected["planned_fortress_span_tiles"] == 24
    assert selected["planned_island_span_tiles"] == 36
    assert selected["available_water_ring_tiles"] >= 6


def test_lake_island_site_rejects_small_water_component() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=65)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "not_found"
    assert report["summary"]["eligible_components"] == 0
    assert report["selected_site"] is None
    assert report["candidates"][0]["rejection_reasons"] == [
        "area_below_minimum",
    ]


def test_lake_island_site_is_disabled_for_super_flatland() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=20)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="super_flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "unsupported_elevation_style"
    assert report["summary"]["lake_components"] == 0


def test_lake_island_site_is_deterministic() -> None:
    elevation_rows = _lake_grid(width=180, height=160, margin=20)

    first = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )
    second = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert first == second


def test_lake_island_materialization_builds_deterministic_island() -> None:
    from top_down_worldgen.tactical.fortress_island import materialize_lake_island

    elevation_rows = _lake_grid(width=160, height=160, margin=20)
    site_report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )
    runtime_rows = [list(row) for row in elevation_rows]
    runtime_data = {
        "elevation": {"default": 0, "cells": [], "summary": {}},
        "elevation_generation_report": {
            "summary": {},
            "geography": {
                "grids": {
                    "geographic_level_grid": {"rows": [list(row) for row in elevation_rows]},
                    "runtime_level_grid": {"rows": runtime_rows},
                    "slope_grid": {"rows": [[0] * 160 for _ in range(160)]},
                },
            },
        },
    }

    first = materialize_lake_island(
        runtime_data=runtime_data,
        site_report=site_report,
        seed=42,
        elevation_style="flatland",
    )

    assert first.changed_tiles > 0
    assert first.island_tiles > 0
    assert first.shoreline_tiles > 0
    assert first.core_tiles > 0
    assert first.entrance_anchor is not None
    materialization = first.site_report["island_materialization"]
    assert materialization["elevation_levels"] == {
        "shoreline": 0,
        "interior": 1,
        "core": 2,
    }
    grids = first.runtime_data["elevation_generation_report"]["geography"]["grids"]
    assert max(max(row) for row in grids["geographic_level_grid"]["rows"]) == 2


def test_lake_island_fortress_plan_has_round_towers_and_gate() -> None:
    from top_down_worldgen.tactical.fortress_island import materialize_lake_island
    from top_down_worldgen.tactical.fortress_plan import (
        PLAN_GATE,
        PLAN_TOWER,
        PLAN_WALL,
        build_lake_island_fortress_plan,
    )

    elevation_rows = _lake_grid(width=180, height=180, margin=20)
    site_report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )
    runtime_data = {
        "elevation": {"default": 0, "cells": [], "summary": {}},
        "elevation_generation_report": {
            "summary": {},
            "geography": {
                "grids": {
                    "geographic_level_grid": {"rows": [list(row) for row in elevation_rows]},
                    "runtime_level_grid": {"rows": [list(row) for row in elevation_rows]},
                    "slope_grid": {"rows": [[0] * 180 for _ in range(180)]},
                },
            },
        },
    }
    island = materialize_lake_island(
        runtime_data=runtime_data,
        site_report=site_report,
        seed=42,
        elevation_style="flatland",
    )
    plan = build_lake_island_fortress_plan(
        runtime_data=island.runtime_data,
        site_report=island.site_report,
        island_mask_rows=island.mask_rows,
        seed=42,
    )

    flat = [value for row in plan.plan_rows for value in row]
    assert PLAN_GATE in flat
    assert PLAN_TOWER in flat
    assert PLAN_WALL in flat
    assert plan.tower_count >= 6
    assert plan.site_report["fortress_plan"]["materialized_to_terrain"] is False



def test_fortress_shell_materializes_blockers_gate_and_heights() -> None:
    from top_down_worldgen.tactical.fortress_materialize import (
        FORTRESS_GATE_TOWER_HEIGHT,
        FORTRESS_TOWER_HEIGHT,
        FORTRESS_WALL_HEIGHT,
        materialize_fortress_shell,
    )
    from top_down_worldgen.tactical.fortress_plan import (
        PLAN_GATE,
        PLAN_TOWER,
        PLAN_WALL,
    )

    rows = ["+" * 25 for _ in range(25)]
    plan_rows = [[0 for _ in range(25)] for _ in range(25)]
    plan_rows[1][1] = PLAN_WALL
    plan_rows[2][2] = PLAN_TOWER
    plan_rows[20][20] = PLAN_TOWER
    plan_rows[3][3] = PLAN_GATE
    site_report = {
        "fortress_plan": {
            "gate_center": {"x": 3, "y": 3},
            "gate_tower_centers": [{"x": 2, "y": 2}],
            "materialized_to_terrain": False,
        },
    }

    result = materialize_fortress_shell(
        rows=rows,
        runtime_data={},
        site_report=site_report,
        plan_rows=plan_rows,
    )

    assert result.rows[1][1] == "#"
    assert result.rows[2][2] == "#"
    assert result.rows[20][20] == "#"
    assert result.rows[3][3] == "R"
    entries = {
        (x, y): height
        for x, y, height in result.site_report["fortress_plan"]["materialization"]["structure_heights"]
    }
    assert entries[(1, 1)] == FORTRESS_WALL_HEIGHT
    assert entries[(2, 2)] == FORTRESS_GATE_TOWER_HEIGHT
    assert entries[(20, 20)] == FORTRESS_TOWER_HEIGHT
    assert result.site_report["fortress_plan"]["materialized_to_terrain"] is True
