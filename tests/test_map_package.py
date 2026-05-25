from __future__ import annotations

import json
from pathlib import Path

from top_down_worldgen.export.map_package import write_map_package
from top_down_worldgen.paths import OutputPaths


def test_write_map_package_creates_structured_outputs(tmp_path: Path) -> None:
    """Ensure structured map package files are written from runtime data."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")
    runtime_data = {
        "map": {
            "width": 2,
            "height": 2,
            "tile_legend": {"S": "start", "G": "goal", "+": "grass"},
            "tile_grid": ["S+", "+G"],
            "tile_counts": {"S": 1, "G": 1, "+": 2},
        },
        "movement_costs": {"+": 1, "S": 1, "G": 1},
        "combat_zones": [{"id": "zone_0"}],
        "cover_points": [{"id": "cover_0"}],
        "choke_points": [],
        "flank_routes": [],
        "enemy_spawn_zones": [],
        "fallback_positions": [],
        "runtime_objects": [{"id": "stone_0", "type": "stone_chunk"}],
        "runtime_objects_summary": {"total": 1},
        "places": [],
        "places_summary": {"total": 0},
        "elevation": {"default": 0, "cells": []},
    }

    write_map_package(
        outputs=outputs,
        runtime_data=runtime_data,
        rows=["S+", "+G"],
        width=2,
        height=2,
        tile_size_px=16,
        seed="random",
        resolved_seed=42,
        profile="clear_map",
    )

    package_index = json.loads(outputs.map_package_map.read_text(encoding="utf-8"))
    tile_grid = json.loads(outputs.map_package_tile_grid.read_text(encoding="utf-8"))
    runtime_objects = json.loads(
        outputs.map_package_runtime_objects.read_text(encoding="utf-8"),
    )

    assert package_index["schema_version"] == "map-package-map-v1"
    assert package_index["dimensions"]["width_tiles"] == 2
    assert package_index["points"]["start"] == {"x": 0, "y": 0}
    assert package_index["points"]["goal"] == {"x": 1, "y": 1}
    assert package_index["layers"]["collision"] == "layers/collision.json"
    assert tile_grid["rows"] == ["S+", "+G"]
    assert runtime_objects["items"][0]["type"] == "stone_chunk"
