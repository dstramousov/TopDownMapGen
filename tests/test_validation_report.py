from __future__ import annotations

from pathlib import Path

from top_down_worldgen.paths import OutputPaths
from top_down_worldgen.tactical.runtime_objects import (
    RUNTIME_OBJECT_TYPE_BY_NAME,
    attach_runtime_layers,
)
from top_down_worldgen.validation import build_validation_report


def _write_map_package_files(outputs: OutputPaths) -> None:
    """Create minimal structured map package files for validation tests."""
    for path in (
        outputs.map_package_map,
        outputs.map_package_tile_grid,
        outputs.map_package_terrain,
        outputs.map_package_movement_costs,
        outputs.map_package_collision,
        outputs.map_package_elevation,
        outputs.map_package_start_goal,
        outputs.map_package_combat_zones,
        outputs.map_package_cover_points,
        outputs.map_package_choke_points,
        outputs.map_package_flank_routes,
        outputs.map_package_enemy_spawn_zones,
        outputs.map_package_fallback_positions,
        outputs.map_package_runtime_objects,
        outputs.map_package_places,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")


def _with_gameplay_fields(item: dict[str, object]) -> dict[str, object]:
    spec = RUNTIME_OBJECT_TYPE_BY_NAME[str(item["type"])]
    enriched = dict(item)
    enriched.setdefault("role", spec["role"])
    enriched.setdefault("blocks_movement", spec["blocks_movement"])
    enriched.setdefault("blocks_projectiles", spec["blocks_projectiles"])
    enriched.setdefault("blocks_vision", spec["blocks_vision"])
    enriched.setdefault("interactive", spec["interactive"])
    enriched.setdefault("tags", list(spec["tags"]))
    enriched.setdefault("collision_profile", dict(spec["collision_profile"]))
    enriched.setdefault("combat_properties", dict(spec["combat_properties"]))
    if "stance_hints" in spec:
        enriched.setdefault("stance_hints", dict(spec["stance_hints"]))
    return enriched


def test_validation_report_accepts_consistent_tactical_data(tmp_path: Path) -> None:
    """Ensure content checks pass for a minimal consistent tactical package."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")
    outputs.generated_map.write_text("SG+++\n+++++\n+++++\n", encoding="utf-8")
    outputs.tactical_map.write_text("{}\n", encoding="utf-8")
    outputs.tactical_map_debug.write_text("{}\n", encoding="utf-8")
    outputs.metrics.write_text("metrics\n", encoding="utf-8")
    outputs.object_catalog.write_text("# Object Catalog\n", encoding="utf-8")
    _write_map_package_files(outputs)

    runtime_data = attach_runtime_layers({
        "map": {
            "width": 5,
            "height": 3,
            "tile_grid": ["SG+++", "+++++", "+++++"],
            "tile_counts": {"S": 1, "G": 1, "+": 13},
        },
        "combat_zones": [
            {
                "id": "zone_0",
                "type": "forest_ambush",
                "enemy_spawns_allowed": True,
                "cover_point_ids": ["cover_0"],
            },
        ],
        "cover_points": [{"id": "cover_0", "position": [4, 2]}],
        "enemy_spawn_zones": [
            {"zone_id": "zone_0", "type": "forest_ambush", "position": [4, 2]},
        ],
        "fallback_positions": [
            {"zone_id": "zone_0", "cover_point_id": "cover_0", "position": [4, 2]},
        ],
        "flank_routes": [{"waypoints": [[0, 0], [4, 2]]}],
        "choke_points": [],
    })
    runtime_data["runtime_objects"] = [
        {
            "id": "stone_chunk_000",
            "type": "stone_chunk",
            "role": "hard_cover",
            "x": 4,
            "y": 2,
            "elevation": 0,
            "height": 2,
            "cover_type": "full",
            "blocks_movement": True,
            "blocks_projectiles": True,
            "blocks_vision": True,
            "interactive": False,
            "tags": [],
        },
        {
            "id": "ammo_cache_000",
            "type": "ammo_cache",
            "role": "interest_point",
            "x": 0,
            "y": 2,
            "elevation": 0,
            "height": 1,
            "cover_type": "none",
            "blocks_movement": False,
            "blocks_projectiles": False,
            "blocks_vision": False,
            "interactive": True,
            "tags": ["loot", "ammo"],
        },
        {
            "id": "medkit_cache_000",
            "type": "medkit_cache",
            "role": "interest_point",
            "x": 1,
            "y": 2,
            "elevation": 0,
            "height": 1,
            "cover_type": "none",
            "blocks_movement": False,
            "blocks_projectiles": False,
            "blocks_vision": False,
            "interactive": True,
            "tags": ["loot", "healing"],
        },
        {
            "id": "trench_000",
            "type": "trench",
            "role": "defensive_position",
            "x": 2,
            "y": 1,
            "position": [2, 1],
            "footprint": [[2, 1], [3, 1], [4, 1]],
            "elevation": -1,
            "height": 0,
            "cover_type": "trench",
            "blocks_movement": False,
            "blocks_projectiles": False,
            "blocks_vision": False,
            "interactive": False,
            "tags": ["elevation", "cover", "below_floor"],
        },
        {
            "id": "big_dead_tree_000",
            "type": "big_dead_tree",
            "role": "landmark",
            "x": 2,
            "y": 2,
            "position": [2, 2],
            "elevation": 0,
            "height": 10,
            "cover_type": "full",
            "blocks_movement": True,
            "blocks_projectiles": True,
            "blocks_vision": True,
            "interactive": False,
            "tags": ["landmark", "natural", "high_cover"],
        },
    ]
    runtime_data["runtime_objects"] = [
        _with_gameplay_fields(item) for item in runtime_data["runtime_objects"]
    ]

    runtime_data["elevation"] = {
        "default": 0,
        "cells": [
            {"x": 2, "y": 1, "level": -1},
            {"x": 3, "y": 1, "level": -1},
            {"x": 4, "y": 1, "level": -1},
        ],
    }
    runtime_data["places"] = [
        {
            "id": "old_defensive_position_000",
            "type": "old_defensive_position",
            "role": "defensive_site",
            "center": {"x": 2, "y": 2},
            "radius": 6,
            "object_ids": ["trench_000", "stone_chunk_000", "ammo_cache_000"],
            "anchor_object_id": "trench_000",
            "tags": ["defense", "trench", "human_trace"],
        },
    ]
    runtime_data["places_summary"] = {
        "total": 1,
        "by_type": {"old_defensive_position": 1},
    }

    report = build_validation_report(
        outputs=outputs,
        rows=["SG+++", "+++++", "+++++"],
        width=5,
        height=3,
        runtime_data=runtime_data,
        resolved_seed=42,
    )

    assert report["status"] == "passed"
    assert all(report["checks"].values())


def test_validation_report_rejects_broken_tile_counts(tmp_path: Path) -> None:
    """Ensure tile count mismatches are reported as validation errors."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")
    outputs.generated_map.write_text("SG\n++\n", encoding="utf-8")
    outputs.tactical_map.write_text("{}\n", encoding="utf-8")
    outputs.tactical_map_debug.write_text("{}\n", encoding="utf-8")
    outputs.metrics.write_text("metrics\n", encoding="utf-8")
    outputs.object_catalog.write_text("# Object Catalog\n", encoding="utf-8")
    _write_map_package_files(outputs)

    runtime_data = {
        "map": {
            "width": 2,
            "height": 2,
            "tile_grid": ["SG", "++"],
            "tile_counts": {"S": 1, "G": 1, "+": 99},
        },
        "combat_zones": [],
        "cover_points": [],
        "enemy_spawn_zones": [],
        "fallback_positions": [],
        "flank_routes": [],
        "choke_points": [],
    }

    report = build_validation_report(
        outputs=outputs,
        rows=["SG", "++"],
        width=2,
        height=2,
        runtime_data=runtime_data,
        resolved_seed=42,
    )

    assert report["status"] == "failed"
    assert "tile_counts_match_grid" in report["errors"]
