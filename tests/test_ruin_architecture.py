from __future__ import annotations

from top_down_worldgen.legacy.ruin_architecture import (
    BuildingArchetype,
    architecture_plan_is_valid,
    generate_ruin_architecture,
)
from top_down_worldgen.structure_height import build_structure_height


def _plan(*, site_kind: str, building_id: int = 0, is_main: bool = True):
    return generate_ruin_architecture(
        rect=(10, 10, 22, 19),
        entrance=(16, 10),
        site_kind=site_kind,
        building_id=building_id,
        is_main=is_main,
        orientation="east_west",
        destruction_direction="north",
        destruction_severity="moderate",
        resolved_seed=12345,
        site_id=7,
    )


def test_ruin_architecture_is_deterministic_and_readable() -> None:
    """Ensure identical inputs produce one valid connected destruction plan."""
    first = _plan(site_kind="village")
    second = _plan(site_kind="village")

    assert first == second
    assert architecture_plan_is_valid(first)
    assert first.external_door not in first.wall_points
    assert first.metrics.isolated_wall_tiles == 0
    assert first.metrics.longest_straight_run >= 3
    assert first.metrics.accessible_floor_ratio >= 0.80
    assert first.metrics.maximum_adjacent_height_delta <= 1
    assert all(1 <= height <= 3 for _x, _y, height in first.wall_heights)


def test_site_kind_selects_related_building_archetypes() -> None:
    """Ensure site roles produce architecture appropriate to their purpose."""
    farm_main = _plan(site_kind="farmstead")
    farm_secondary = _plan(
        site_kind="farmstead",
        building_id=1,
        is_main=False,
    )
    outpost = _plan(site_kind="outpost")

    assert farm_main.archetype in {
        BuildingArchetype.SMALL_HOUSE,
        BuildingArchetype.LONG_HOUSE,
    }
    assert farm_secondary.archetype == BuildingArchetype.BARN
    assert outpost.archetype == BuildingArchetype.OUTPOST_BUILDING


def test_planned_damage_heights_override_legacy_height_generation() -> None:
    """Ensure architecture metadata is the source of structure heights."""
    plan = _plan(site_kind="village")
    width = 30
    height = 25
    terrain = [["grass" for _ in range(width)] for _ in range(height)]
    collision = [["0" for _ in range(width)] for _ in range(height)]
    for x, y, _value in plan.wall_heights:
        terrain[y][x] = "ruin_wall_blocker"
        collision[y][x] = "1"
    payload = {
        "sites": [
            {
                "buildings": [
                    {
                        "architecture": plan.to_dict(),
                    }
                ]
            }
        ]
    }

    result = build_structure_height(
        terrain_rows=terrain,
        collision_rows=["".join(row) for row in collision],
        resolved_seed=999,
        ruin_sites=payload,
    )

    for x, y, expected in plan.wall_heights:
        assert result.rows[y][x] == expected
    assert result.summary.architecture_planned_tiles == len(plan.wall_heights)
    assert result.summary.legacy_fallback_tiles == 0


def test_destruction_severity_preserves_more_architecture_when_lighter() -> None:
    """Ensure lighter damage retains more walls than stronger damage."""
    plans = {
        severity: generate_ruin_architecture(
            rect=(10, 10, 22, 19),
            entrance=(16, 10),
            site_kind="village",
            building_id=3,
            is_main=False,
            orientation="east_west",
            destruction_direction="north",
            destruction_severity=severity,
            resolved_seed=777,
            site_id=2,
        )
        for severity in ("light", "moderate", "heavy")
    }

    assert all(architecture_plan_is_valid(plan) for plan in plans.values())
    assert (
        plans["light"].metrics.wall_destroyed_ratio
        < plans["moderate"].metrics.wall_destroyed_ratio
        < plans["heavy"].metrics.wall_destroyed_ratio
    )
    assert plans["light"].metrics.outer_wall_retained_ratio > 0.75
    assert plans["light"].metrics.largest_component_ratio >= 0.72


def test_window_sill_hints_are_low_preserved_facade_tiles() -> None:
    """Ensure window hints remain walls and preserve valid height gradients."""
    plan = _plan(site_kind="village")
    heights = {(x, y): height for x, y, height in plan.wall_heights}

    assert plan.to_dict()["schema_version"] == "ruin-building-architecture-v2"
    assert plan.metrics.window_sill_hint_count == len(plan.window_sill_hints)
    for point in plan.window_sill_hints:
        assert heights[point] == 1
        neighbor_heights = [
            heights[neighbor]
            for neighbor in (
                (point[0], point[1] - 1),
                (point[0] - 1, point[1]),
                (point[0] + 1, point[1]),
                (point[0], point[1] + 1),
            )
            if neighbor in heights
        ]
        assert neighbor_heights
        assert max(abs(value - 1) for value in neighbor_heights) <= 1
