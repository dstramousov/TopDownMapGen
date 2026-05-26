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
    terrain = json.loads(outputs.map_package_terrain.read_text(encoding="utf-8"))
    movement = json.loads(
        outputs.map_package_movement_costs.read_text(encoding="utf-8"),
    )
    collision = json.loads(outputs.map_package_collision.read_text(encoding="utf-8"))
    start_goal = json.loads(outputs.map_package_start_goal.read_text(encoding="utf-8"))
    markers = json.loads(outputs.map_package_markers.read_text(encoding="utf-8"))
    runtime_grids = json.loads(
        outputs.map_package_runtime_grids.read_text(encoding="utf-8"),
    )
    runtime_objects = json.loads(
        outputs.map_package_runtime_objects.read_text(encoding="utf-8"),
    )
    tile_types = json.loads(outputs.map_package_tile_types.read_text(encoding="utf-8"))
    object_types = json.loads(
        outputs.map_package_object_types.read_text(encoding="utf-8"),
    )
    render_profile = json.loads(
        outputs.map_package_render_profile.read_text(encoding="utf-8"),
    )
    tile_render_hints = json.loads(
        outputs.map_package_tile_render_hints.read_text(encoding="utf-8"),
    )
    object_render_hints = json.loads(
        outputs.map_package_object_render_hints.read_text(encoding="utf-8"),
    )

    assert package_index["schema_version"] == "map-package-map-v3"
    assert package_index["dimensions"]["width_tiles"] == 2
    assert package_index["points"]["start"] == {"x": 0, "y": 0}
    assert package_index["points"]["goal"] == {"x": 1, "y": 1}
    assert package_index["markers"] == "markers.json"
    assert package_index["runtime_grids"] == "runtime_grids.json"
    assert package_index["layers"]["collision"] == "layers/collision.json"
    assert package_index["layers"]["terrain"] == "layers/terrain.json"
    assert package_index["layers"]["start_goal"] == "layers/start_goal.json"
    assert package_index["catalogs"]["tile_types"] == "catalogs/tile_types.json"
    assert package_index["catalogs"]["object_types"] == "catalogs/object_types.json"
    assert package_index["render"]["profile"] == "render/render_profile.json"
    assert package_index["render"]["tile_render_hints"] == (
        "render/tile_render_hints.json"
    )
    assert package_index["render"]["object_render_hints"] == (
        "render/object_render_hints.json"
    )
    assert tile_grid["rows"] == ["S+", "+G"]
    assert terrain["rows"] == [["start", "grass"], ["grass", "goal"]]
    assert movement["costs_by_type"]["grass"] == 1
    assert collision["format"] == "boolean_rows"
    assert collision["rows"] == ["00", "00"]
    assert start_goal["start"] == {"x": 0, "y": 0}
    assert start_goal["goal"] == {"x": 1, "y": 1}
    assert markers["schema_version"] == "markers-v1"
    assert [item["type"] for item in markers["items"]] == ["start", "goal"]
    assert runtime_grids["schema_version"] == "runtime-grids-v1"
    assert runtime_grids["grids"]["collision_grid"]["rows"] == ["00", "00"]
    assert runtime_grids["grids"]["height_grid"]["rows"] == [[0, 0], [0, 0]]
    assert runtime_objects["items"][0]["type"] == "stone_chunk"
    assert tile_types["types"]["grass"]["walkable"] is True
    assert object_types["types"]["stone_chunk"]["instance_count"] == 1
    assert render_profile["schema_version"] == "render-profile-v1"
    assert "terrain" in render_profile["draw_order"]
    assert tile_render_hints["hints"]["grass"]["visual_group"] == "terrain/grass"
    assert object_render_hints["hints"]["stone_chunk"]["render_mode"] == "sprite"
