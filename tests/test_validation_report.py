from __future__ import annotations

from pathlib import Path

from top_down_worldgen.paths import OutputPaths
from top_down_worldgen.tactical.runtime_objects import attach_runtime_layers
from top_down_worldgen.validation import build_validation_report


def test_validation_report_accepts_consistent_tactical_data(tmp_path: Path) -> None:
    """Ensure content checks pass for a minimal consistent tactical package."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")
    outputs.generated_map.write_text("SG+\n+++\n", encoding="utf-8")
    outputs.tactical_map.write_text("{}\n", encoding="utf-8")
    outputs.tactical_map_debug.write_text("{}\n", encoding="utf-8")
    outputs.metrics.write_text("metrics\n", encoding="utf-8")

    runtime_data = attach_runtime_layers({
        "map": {
            "width": 3,
            "height": 2,
            "tile_grid": ["SG+", "+++"],
            "tile_counts": {"S": 1, "G": 1, "+": 4},
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
        "flank_routes": [{"waypoints": [[0, 0], [2, 1]]}],
        "choke_points": [],
    })
    runtime_data["runtime_objects"] = [
        {
            "id": "stone_chunk_000",
            "type": "stone_chunk",
            "role": "hard_cover",
            "x": 0,
            "y": 1,
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
            "x": 1,
            "y": 1,
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
            "x": 2,
            "y": 0,
            "elevation": 0,
            "height": 1,
            "cover_type": "none",
            "blocks_movement": False,
            "blocks_projectiles": False,
            "blocks_vision": False,
            "interactive": True,
            "tags": ["loot", "healing"],
        },
    ]

    report = build_validation_report(
        outputs=outputs,
        rows=["SG+", "+++"],
        width=3,
        height=2,
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
