from __future__ import annotations

from top_down_worldgen.config import FortressConfig
from top_down_worldgen.tactical.fortress_site import (
    analyze_lake_island_fortress_site,
)


def _enabled_config() -> FortressConfig:
    return FortressConfig.from_raw(
        {
            "enabled": True,
            "archetype": "island",
            "size": "small",
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
    assert selected["planned_fortress_span_tiles"] == 20
    assert selected["planned_island_span_tiles"] == 32
    assert selected["available_water_ring_tiles"] >= 6


def test_lake_island_site_rejects_small_water_component() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=65)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "selected"
    assert report["summary"]["eligible_components"] == 0
    assert report["resolved_placement"] == "shore"
    assert report["fallback_reason"] == "no_suitable_island_water_body"
    assert report["candidates"][0]["rejection_reasons"] == [
        "area_below_minimum",
    ]


def test_lake_island_site_is_supported_for_super_flatland() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=20)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="super_flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "selected"
    assert report["resolved_placement"] == "island"


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
        PLAN_COURTYARD,
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
    assert 4 <= plan.tower_count <= 7
    report = plan.site_report["fortress_plan"]
    assert report["algorithm"] == "architectural_nodes_mixed_walls_v2"
    assert {segment["kind"] for segment in report["segments"]} <= {"straight", "gentle_curve"}
    centers = [tower["center"] for tower in report["towers"]]
    assert len({(item["x"], item["y"]) for item in centers}) == len(centers)
    assert plan.site_report["fortress_plan"]["materialized_to_terrain"] is False



def test_fortress_shell_materializes_blockers_gate_and_heights() -> None:
    from top_down_worldgen.tactical.fortress_materialize import (
        FORTRESS_GATE_TOWER_HEIGHT,
        FORTRESS_TOWER_HEIGHT,
        FORTRESS_WALL_HEIGHT,
        materialize_fortress_shell,
    )
    from top_down_worldgen.tactical.fortress_plan import (
        PLAN_COURTYARD,
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
    plan_rows[4][4] = PLAN_COURTYARD
    plan_rows[4][5] = PLAN_COURTYARD
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
    assert result.rows[4][4] == "R"
    assert result.rows[4][5] == "R"
    entries = {
        (x, y): height
        for x, y, height in result.site_report["fortress_plan"]["materialization"]["structure_heights"]
    }
    assert entries[(1, 1)] == FORTRESS_WALL_HEIGHT
    assert entries[(2, 2)] == FORTRESS_GATE_TOWER_HEIGHT
    assert entries[(20, 20)] == FORTRESS_TOWER_HEIGHT
    materialization = result.site_report["fortress_plan"]["materialization"]
    assert materialization["courtyard_floor_tiles"] == 2
    assert materialization["courtyard_replaced_tiles"] == 2
    assert materialization["courtyard_foreign_tiles_remaining"] == 0
    assert result.courtyard_floor_tiles == 2
    assert result.site_report["fortress_plan"]["materialized_to_terrain"] is True


def test_small_fortress_scale_on_440_by_400() -> None:
    elevation_rows = _lake_grid(width=440, height=400, margin=40)
    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert report["requirements"]["fortress_span_tiles"] == 40
    assert report["requirements"]["island_span_tiles"] == 52


def test_fortress_size_profiles_are_visibly_distinct_on_304_map() -> None:
    elevation_rows = _lake_grid(width=304, height=304, margin=40)

    spans: dict[str, int] = {}
    for size in ("small", "medium", "huge"):
        report = analyze_lake_island_fortress_site(
            elevation_rows=elevation_rows,
            elevation_style="normal",
            fortress_config=FortressConfig.from_raw(
                {"enabled": True, "archetype": "any", "size": size}
            ),
        )
        spans[size] = report["requirements"]["fortress_span_tiles"]

    assert spans == {"small": 30, "medium": 49, "huge": 73}


def test_shallow_fortress_approach_reaches_mainland_with_gate_width_path() -> None:
    from top_down_worldgen.tactical.fortress_approach import (
        APPROACH_PATH,
        APPROACH_SHALLOW,
        materialize_shallow_fortress_approach,
    )

    width = 80
    height = 60
    levels = [[0 for _ in range(width)] for _ in range(height)]
    island_mask = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(10, 50):
        for x in range(20, 60):
            levels[y][x] = -3
    for y in range(22, 39):
        for x in range(30, 47):
            levels[y][x] = 1
            island_mask[y][x] = 2
    runtime_data = {
        "elevation": {"default": 0, "cells": [], "summary": {}},
        "elevation_generation_report": {
            "summary": {},
            "geography": {
                "grids": {
                    "geographic_level_grid": {"rows": [list(row) for row in levels]},
                    "runtime_level_grid": {"rows": [list(row) for row in levels]},
                    "slope_grid": {"rows": [[0] * width for _ in range(height)]},
                },
            },
        },
    }
    site_report = {
        "selected_site": {"center": {"x": 38, "y": 30}},
        "fortress_plan": {
            "gate_center": {"x": 30, "y": 30},
            "gate_width_tiles": 5,
        },
    }

    result = materialize_shallow_fortress_approach(
        rows=["+" * width for _ in range(height)],
        runtime_data=runtime_data,
        site_report=site_report,
        island_mask_rows=island_mask,
        seed=42,
    )

    flat = [value for row in result.approach_rows for value in row]
    assert APPROACH_SHALLOW in flat
    assert APPROACH_PATH in flat
    assert result.site_report["fortress_approach"]["gate_width_tiles"] == 5
    assert result.site_report["fortress_approach"]["shallow_width_tiles"] == 11
    assert result.path_tiles > 0
    assert any("." in row for row in result.rows)
    levels = result.runtime_data["elevation_generation_report"]["geography"]["grids"]["geographic_level_grid"]["rows"]
    for y, row in enumerate(result.approach_rows):
        for x, value in enumerate(row):
            if value == APPROACH_PATH:
                assert levels[y][x] == 0


def test_fortress_interior_plan_contains_keep_houses_paths_and_trees() -> None:
    from top_down_worldgen.tactical.fortress_interior import (
        INTERIOR_HOUSE_FLOOR,
        INTERIOR_HOUSE_WALL,
        INTERIOR_KEEP_FLOOR,
        INTERIOR_KEEP_WALL,
        INTERIOR_PATH,
        INTERIOR_TREE,
        build_fortress_interior_plan,
    )
    from top_down_worldgen.tactical.fortress_plan import PLAN_COURTYARD, PLAN_GATE, PLAN_WALL

    width = 100
    height = 100
    plan_rows = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(20, 81):
        for x in range(20, 81):
            plan_rows[y][x] = PLAN_COURTYARD
    for x in range(20, 81):
        plan_rows[20][x] = PLAN_WALL
        plan_rows[80][x] = PLAN_WALL
    for y in range(20, 81):
        plan_rows[y][20] = PLAN_WALL
        plan_rows[y][80] = PLAN_WALL
    for x in range(48, 53):
        plan_rows[80][x] = PLAN_GATE

    site_report = {
        "policy": {},
        "fortress_plan": {
            "center": {"x": 50, "y": 50},
            "gate_center": {"x": 50, "y": 80},
            "fortress_span_tiles": 50,
        },
    }
    result = build_fortress_interior_plan(
        runtime_data={},
        site_report=site_report,
        plan_rows=plan_rows,
        seed=42,
    )

    flat = [value for row in result.interior_rows for value in row]
    assert INTERIOR_KEEP_WALL in flat
    assert INTERIOR_KEEP_FLOOR in flat
    assert INTERIOR_HOUSE_WALL in flat
    assert INTERIOR_HOUSE_FLOOR in flat
    assert INTERIOR_PATH in flat
    assert INTERIOR_TREE in flat
    assert 2 <= result.house_count <= 3
    assert 4 <= result.tree_count <= 10
    report = result.site_report["fortress_interior_plan"]
    assert report["keep"]["height_levels_above_ground"] == 16
    assert report["materialized_to_terrain"] is False




def test_fortress_interior_degrades_when_houses_do_not_fit() -> None:
    from top_down_worldgen.tactical.fortress_interior import (
        INTERIOR_KEEP_FLOOR,
        INTERIOR_KEEP_WALL,
        INTERIOR_PATH,
        build_fortress_interior_plan,
    )
    from top_down_worldgen.tactical.fortress_plan import (
        PLAN_COURTYARD,
        PLAN_GATE,
        PLAN_WALL,
    )

    width = 48
    height = 48
    plan_rows = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(10, 39):
        for x in range(10, 39):
            plan_rows[y][x] = PLAN_COURTYARD
    for x in range(10, 39):
        plan_rows[10][x] = PLAN_WALL
        plan_rows[38][x] = PLAN_WALL
    for y in range(10, 39):
        plan_rows[y][10] = PLAN_WALL
        plan_rows[y][38] = PLAN_WALL
    for x in range(23, 26):
        plan_rows[38][x] = PLAN_GATE

    site_report = {
        "policy": {},
        "fortress_plan": {
            "center": {"x": 24, "y": 24},
            "gate_center": {"x": 24, "y": 38},
            "fortress_span_tiles": 32,
        },
    }

    result = build_fortress_interior_plan(
        runtime_data={},
        site_report=site_report,
        plan_rows=plan_rows,
        seed=9069957925987520693,
    )

    flat = [value for row in result.interior_rows for value in row]
    assert INTERIOR_KEEP_WALL in flat
    assert INTERIOR_KEEP_FLOOR in flat
    assert INTERIOR_PATH in flat
    report = result.site_report["fortress_interior_plan"]
    assert report["status"] in {"planned", "degraded"}
    assert report["house_count"] <= report["requested_house_count"]
    if report["status"] == "degraded":
        assert report["degradation_reason"] == "insufficient_courtyard_space"


def test_fortress_interior_keep_placement_falls_back_without_failure() -> None:
    from top_down_worldgen.tactical.fortress_interior import (
        INTERIOR_KEEP_FLOOR,
        INTERIOR_KEEP_WALL,
        build_fortress_interior_plan,
    )
    from top_down_worldgen.tactical.fortress_plan import (
        PLAN_COURTYARD,
        PLAN_GATE,
        PLAN_WALL,
    )

    width = 44
    height = 44
    plan_rows = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(10, 34):
        for x in range(10, 34):
            plan_rows[y][x] = PLAN_COURTYARD
    for x in range(10, 34):
        plan_rows[10][x] = PLAN_WALL
        plan_rows[33][x] = PLAN_WALL
    for y in range(10, 34):
        plan_rows[y][10] = PLAN_WALL
        plan_rows[y][33] = PLAN_WALL
    for x in range(20, 23):
        plan_rows[33][x] = PLAN_GATE

    site_report = {
        "policy": {},
        "fortress_plan": {
            "center": {"x": 22, "y": 22},
            "gate_center": {"x": 21, "y": 33},
            "fortress_span_tiles": 32,
        },
    }
    result = build_fortress_interior_plan(
        runtime_data={},
        site_report=site_report,
        plan_rows=plan_rows,
        seed=99,
    )

    report = result.site_report["fortress_interior_plan"]
    assert report["status"] in {"planned", "degraded"}
    assert report["keep"]["status"] == "planned"
    assert (
        report["keep"]["radius_tiles"]
        <= report["keep"]["requested_radius_tiles"]
    )
    flat = [value for row in result.interior_rows for value in row]
    assert INTERIOR_KEEP_WALL in flat
    assert INTERIOR_KEEP_FLOOR in flat


def test_fortress_interior_can_skip_keep_without_failure() -> None:
    from top_down_worldgen.tactical.fortress_interior import (
        build_fortress_interior_plan,
    )
    from top_down_worldgen.tactical.fortress_plan import (
        PLAN_COURTYARD,
        PLAN_GATE,
    )

    width = 32
    height = 32
    plan_rows = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(12, 19):
        for x in range(12, 19):
            plan_rows[y][x] = PLAN_COURTYARD
    plan_rows[18][15] = PLAN_GATE

    site_report = {
        "policy": {},
        "fortress_plan": {
            "center": {"x": 15, "y": 15},
            "gate_center": {"x": 15, "y": 18},
            "fortress_span_tiles": 24,
        },
    }
    result = build_fortress_interior_plan(
        runtime_data={},
        site_report=site_report,
        plan_rows=plan_rows,
        seed=7,
    )

    report = result.site_report["fortress_interior_plan"]
    assert report["status"] == "degraded"
    assert report["keep"]["status"] == "skipped"
    assert "keep_not_placed" in report["degradation_reasons"]
    assert result.keep_tiles == 0

def test_fortress_interior_plan_is_deterministic() -> None:
    from top_down_worldgen.tactical.fortress_interior import build_fortress_interior_plan
    from top_down_worldgen.tactical.fortress_plan import PLAN_COURTYARD, PLAN_GATE, PLAN_WALL

    width = 90
    height = 90
    plan_rows = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(15, 76):
        for x in range(15, 76):
            plan_rows[y][x] = PLAN_COURTYARD
    for x in range(15, 76):
        plan_rows[15][x] = PLAN_WALL
        plan_rows[75][x] = PLAN_WALL
    for y in range(15, 76):
        plan_rows[y][15] = PLAN_WALL
        plan_rows[y][75] = PLAN_WALL
    for x in range(43, 48):
        plan_rows[75][x] = PLAN_GATE

    site_report = {
        "policy": {},
        "fortress_plan": {
            "center": {"x": 45, "y": 45},
            "gate_center": {"x": 45, "y": 75},
            "fortress_span_tiles": 50,
        },
    }
    first = build_fortress_interior_plan(
        runtime_data={},
        site_report=site_report,
        plan_rows=plan_rows,
        seed=123,
    )
    second = build_fortress_interior_plan(
        runtime_data={},
        site_report=site_report,
        plan_rows=plan_rows,
        seed=123,
    )

    assert first.interior_rows == second.interior_rows
    assert first.site_report == second.site_report


def test_fortress_interior_materialization_exports_keep_and_houses() -> None:
    from top_down_worldgen.tactical.fortress_interior import (
        INTERIOR_HOUSE_FLOOR,
        INTERIOR_HOUSE_WALL,
        INTERIOR_KEEP_FLOOR,
        INTERIOR_KEEP_WALL,
        INTERIOR_PATH,
        INTERIOR_TREE,
    )
    from top_down_worldgen.tactical.fortress_interior_materialize import (
        materialize_fortress_interior,
    )

    interior_rows = [[0 for _ in range(6)] for _ in range(6)]
    interior_rows[1][1] = INTERIOR_KEEP_WALL
    interior_rows[1][2] = INTERIOR_KEEP_FLOOR
    interior_rows[2][1] = INTERIOR_HOUSE_WALL
    interior_rows[2][2] = INTERIOR_HOUSE_FLOOR
    interior_rows[3][1] = INTERIOR_PATH
    interior_rows[3][2] = INTERIOR_TREE
    site_report = {
        "policy": {},
        "fortress_plan": {
            "materialization": {
                "structure_heights": [],
                "structure_types": [],
            },
        },
        "fortress_interior_plan": {},
    }

    result = materialize_fortress_interior(
        rows=["R" * 6 for _ in range(6)],
        runtime_data={},
        site_report=site_report,
        interior_rows=interior_rows,
    )

    assert result.rows[1][1] == "#"
    assert result.rows[1][2] == "R"
    assert result.rows[2][1] == "#"
    assert result.rows[2][2] == "R"
    assert result.rows[3][1] == "R"
    assert result.rows[3][2] == "T"
    materialization = result.site_report["fortress_plan"]["materialization"]
    assert [1, 1, 16] in materialization["structure_heights"]
    assert [1, 1, "fortress_keep"] in materialization["structure_types"]
    assert [1, 2, "fortress_building"] in materialization["structure_types"]
    assert result.site_report["fortress_interior_plan"]["materialized_to_terrain"] is True


def test_fortress_approach_falls_back_to_nearest_outward_land() -> None:
    from top_down_worldgen.tactical.fortress_approach import (
        _find_mainland_landing,
    )
    from top_down_worldgen.tactical.fortress_island import MASK_OUTSIDE

    size = 30
    levels = [[-2 for _ in range(size)] for _ in range(size)]
    island_mask = [[MASK_OUTSIDE for _ in range(size)] for _ in range(size)]
    for y in range(10, 20):
        for x in range(10, 20):
            island_mask[y][x] = 1
            levels[y][x] = 1
    # Land exists outward from the gate, but not on the narrow ray fan.
    for y in range(4, 8):
        for x in range(22, 27):
            levels[y][x] = 0

    landing = _find_mainland_landing(
        levels=levels,
        island_mask_rows=island_mask,
        center=(15, 15),
        gate=(19, 11),
    )

    assert landing is not None
    assert levels[landing[1]][landing[0]] == 0


def test_inland_fortress_approach_is_skipped_without_terrain_changes() -> None:
    from top_down_worldgen.tactical.fortress_approach import (
        skip_fortress_approach,
    )

    rows = ["++++", "++++"]
    runtime_data = {"marker": "unchanged"}
    site_report = {
        "policy": {"phase": "interior_planned"},
        "resolved_placement": "inland",
    }

    result = skip_fortress_approach(
        rows=rows,
        runtime_data=runtime_data,
        site_report=site_report,
        reason="inland_placement",
    )

    assert result.rows == rows
    assert result.approach_rows == []
    assert result.changed_tiles == 0
    assert result.path_tiles == 0
    assert result.site_report["fortress_approach"] == {
        "status": "skipped",
        "reason": "inland_placement",
        "changed_tiles": 0,
        "shallow_tiles": 0,
        "path_tiles": 0,
        "length_tiles": 0.0,
    }
    assert result.runtime_data["marker"] == "unchanged"
