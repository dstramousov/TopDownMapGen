from __future__ import annotations

from pathlib import Path

from top_down_worldgen.paths import OutputPaths
from top_down_worldgen.tactical.runtime_objects import (
    RUNTIME_OBJECT_TYPE_NAMES,
    attach_runtime_layers,
)
from top_down_worldgen.validation import build_validation_report


def test_attach_runtime_layers_declares_object_types() -> None:
    """Ensure map-level foundation is attached without mutating input data."""
    source = {"map": {"width": 2, "height": 2}}

    enriched = attach_runtime_layers(source)

    assert source.get("runtime_objects") is None
    assert enriched["runtime_objects"] == []
    assert enriched["elevation"] == {"default": 0, "cells": []}
    assert "trench" in RUNTIME_OBJECT_TYPE_NAMES
    assert any(
        item["type"] == "fallen_log"
        for item in enriched["runtime_object_schema"]["types"]
    )


def test_attach_runtime_layers_generates_interest_points() -> None:
    """Ensure generated runtime objects include tactical interest points."""
    rows = ["+" * 40 for _ in range(24)]
    runtime_data = attach_runtime_layers(
        {
            "map": {
                "width": 40,
                "height": 24,
                "tile_grid": rows,
                "tile_counts": {"+": 40 * 24},
            },
            "combat_zones": [{"id": "zone_0", "center": [20, 12]}],
            "choke_points": [{"position": [18, 12]}],
        },
        seed=1,
    )

    object_types = {item["type"] for item in runtime_data["runtime_objects"]}

    assert "ammo_cache" in object_types
    assert "medkit_cache" in object_types
    assert "trench" in object_types
    assert runtime_data["runtime_objects_summary"]["by_type"]["ammo_cache"] >= 1
    assert runtime_data["runtime_objects_summary"]["by_type"]["medkit_cache"] >= 1
    assert runtime_data["runtime_objects_summary"]["by_type"]["trench"] >= 1
    assert runtime_data["elevation"]["cells"]
    assert all(cell["level"] == -1 for cell in runtime_data["elevation"]["cells"])


def test_validation_accepts_runtime_object_foundation(tmp_path: Path) -> None:
    """Ensure valid runtime objects and elevation cells pass content checks."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")
    outputs.generated_map.write_text("SG+++\n+++++\n+++++\n", encoding="utf-8")
    outputs.tactical_map.write_text("{}\n", encoding="utf-8")
    outputs.tactical_map_debug.write_text("{}\n", encoding="utf-8")
    outputs.metrics.write_text("metrics\n", encoding="utf-8")

    runtime_data = attach_runtime_layers(
        {
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
        },
    )
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
    ]
    runtime_data["elevation"] = {
        "default": 0,
        "cells": [
            {"x": 2, "y": 1, "level": -1},
            {"x": 3, "y": 1, "level": -1},
            {"x": 4, "y": 1, "level": -1},
        ],
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
    assert report["checks"]["runtime_objects_have_valid_types"] is True
    assert report["checks"]["elevation_levels_valid"] is True


def test_validation_rejects_runtime_object_on_start(tmp_path: Path) -> None:
    """Ensure runtime objects cannot overlap protected start or goal tiles."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")
    outputs.generated_map.write_text("SG\n++\n", encoding="utf-8")
    outputs.tactical_map.write_text("{}\n", encoding="utf-8")
    outputs.tactical_map_debug.write_text("{}\n", encoding="utf-8")
    outputs.metrics.write_text("metrics\n", encoding="utf-8")

    runtime_data = attach_runtime_layers(
        {
            "map": {
                "width": 2,
                "height": 2,
                "tile_grid": ["SG", "++"],
                "tile_counts": {"S": 1, "G": 1, "+": 2},
            },
            "combat_zones": [
                {
                    "id": "zone_0",
                    "type": "forest_ambush",
                    "enemy_spawns_allowed": True,
                    "cover_point_ids": ["cover_0"],
                },
            ],
            "cover_points": [{"id": "cover_0", "position": [0, 1]}],
            "enemy_spawn_zones": [
                {"zone_id": "zone_0", "type": "forest_ambush", "position": [1, 1]},
            ],
            "fallback_positions": [
                {"zone_id": "zone_0", "cover_point_id": "cover_0", "position": [0, 1]},
            ],
            "flank_routes": [{"waypoints": [[0, 0], [1, 1]]}],
            "choke_points": [],
        },
    )
    runtime_data["runtime_objects"] = [
        {
            "id": "fallen_log_000",
            "type": "fallen_log",
            "x": 0,
            "y": 0,
            "elevation": 0,
            "height": 1,
            "cover_type": "low",
        },
    ]

    report = build_validation_report(
        outputs=outputs,
        rows=["SG", "++"],
        width=2,
        height=2,
        runtime_data=runtime_data,
        resolved_seed=42,
    )

    assert report["status"] == "failed"
    assert "runtime_objects_do_not_overlap_start_goal" in report["errors"]
