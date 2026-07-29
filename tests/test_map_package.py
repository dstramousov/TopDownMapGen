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
    structure_height = json.loads(
        outputs.map_package_structure_height.read_text(encoding="utf-8"),
    )
    structure_type = json.loads(
        outputs.map_package_structure_type.read_text(encoding="utf-8"),
    )
    structure_micro_geometry = json.loads(
        outputs.map_package_structure_micro_geometry.read_text(encoding="utf-8"),
    )
    structure_top_geometry = json.loads(
        outputs.map_package_structure_top_geometry.read_text(encoding="utf-8"),
    )
    vegetation_type = json.loads(
        outputs.map_package_vegetation_type.read_text(encoding="utf-8"),
    )
    vegetation_height = json.loads(
        outputs.map_package_vegetation_height.read_text(encoding="utf-8"),
    )
    start_goal = json.loads(outputs.map_package_start_goal.read_text(encoding="utf-8"))
    markers = json.loads(outputs.map_package_markers.read_text(encoding="utf-8"))
    runtime_grids = json.loads(
        outputs.map_package_runtime_grids.read_text(encoding="utf-8"),
    )
    world_graph = json.loads(
        outputs.map_package_world_graph.read_text(encoding="utf-8"),
    )
    routes = json.loads(outputs.map_package_routes.read_text(encoding="utf-8"))
    gameplay_zones = json.loads(
        outputs.map_package_gameplay_zones.read_text(encoding="utf-8"),
    )
    elevation_model = json.loads(
        outputs.map_package_elevation_model.read_text(encoding="utf-8"),
    )
    elevation_features = json.loads(
        outputs.map_package_elevation_features.read_text(encoding="utf-8"),
    )
    elevation_transitions = json.loads(
        outputs.map_package_elevation_transitions.read_text(encoding="utf-8"),
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

    assert package_index["schema_version"] == "map-package-map-v27"
    assert package_index["dimensions"]["width_tiles"] == 2
    assert package_index["points"]["start"] == {"x": 0, "y": 0}
    assert package_index["points"]["goal"] == {"x": 1, "y": 1}
    assert package_index["markers"] == "markers.json"
    assert package_index["runtime_grids"] == "runtime_grids.json"
    assert package_index["runtime_binary"]["path"] == "map_runtime.vxmap"
    assert package_index["runtime_binary"]["format"] == "vxmap-runtime-v1"
    assert package_index["runtime_binary"]["format_minor"] == 5
    assert len(package_index["runtime_binary"]["build_id"]) == 32
    assert outputs.map_package_runtime_binary.exists()
    assert package_index["world_graph"] == "world_graph.json"
    assert package_index["routes"] == "routes.json"
    assert package_index["gameplay_zones"] == "gameplay_zones.json"
    assert package_index["elevation_model"] == "elevation_model.json"
    assert package_index["elevation_features"] == "elevation_features.json"
    assert package_index["elevation_transitions"] == "elevation_transitions.json"
    assert package_index["layers"]["collision"] == "layers/collision.json"
    assert package_index["layers"]["terrain"] == "layers/terrain.json"
    assert package_index["layers"]["structure_height"] == (
        "layers/structure_height.json"
    )
    assert package_index["layers"]["structure_type"] == "layers/structure_type.json"
    assert package_index["layers"]["structure_micro_geometry"] == (
        "layers/structure_micro_geometry.json"
    )
    assert package_index["layers"]["structure_top_geometry"] == (
        "layers/structure_top_geometry.json"
    )
    assert package_index["layers"]["vegetation_type"] == (
        "layers/vegetation_type.json"
    )
    assert package_index["layers"]["vegetation_height"] == (
        "layers/vegetation_height.json"
    )
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
    assert structure_height["schema_version"] == "structure-height-layer-v3"
    assert structure_height["units"] == "logical_levels_above_ground"
    assert structure_height["ground_reference"] == "elevation_plus_one"
    assert structure_height["rows"] == [[0, 0], [0, 0]]
    assert structure_type["schema_version"] == "structure-type-layer-v1"
    assert structure_type["rows"] == [[0, 0], [0, 0]]
    assert structure_micro_geometry["division"] == 4
    assert structure_micro_geometry["cells"] == []
    assert structure_top_geometry["schema_version"] == (
        "structure-top-geometry-layer-v6"
    )
    assert structure_top_geometry["cells"] == []
    assert vegetation_type["schema_version"] == "vegetation-type-layer-v1"
    assert vegetation_type["rows"] == [[0, 0], [0, 0]]
    assert vegetation_type["dictionary"]["1"] == "tree"
    assert vegetation_height["schema_version"] == "vegetation-height-layer-v1"
    assert vegetation_height["units"] == "logical_levels_above_ground"
    assert vegetation_height["ground_reference"] == "elevation_plus_one"
    assert vegetation_height["rows"] == [[0, 0], [0, 0]]
    assert start_goal["start"] == {"x": 0, "y": 0}
    assert start_goal["goal"] == {"x": 1, "y": 1}
    assert markers["schema_version"] == "markers-v1"
    assert [item["type"] for item in markers["items"]] == ["start", "goal"]
    assert runtime_grids["schema_version"] == "runtime-grids-v1"
    assert world_graph["schema_version"] == "world-graph-v2"
    assert [node["type"] for node in world_graph["nodes"]] == ["start", "goal"]
    assert world_graph["main_path"]["node_ids"] == ["marker:start", "marker:goal"]
    assert routes["schema_version"] == "routes-v1"
    assert routes["items"][0]["type"] == "main_road"
    assert gameplay_zones["schema_version"] == "gameplay-zones-v1"
    assert [item["type"] for item in gameplay_zones["items"]] == [
        "safe_area",
        "extraction_area",
    ]
    assert elevation_model["schema_version"] == "elevation-model-v5"
    assert set(elevation_model["levels"]) >= {"-1", "0", "1", "2", "3", "4"}
    assert elevation_features["schema_version"] == "elevation-features-v3"
    assert elevation_transitions["schema_version"] == "elevation-transitions-v4"
    assert runtime_grids["grids"]["collision_grid"]["rows"] == ["00", "00"]
    assert runtime_grids["grids"]["height_grid"]["rows"] == [[0, 0], [0, 0]]
    assert runtime_objects["items"][0]["type"] == "stone_chunk"
    assert tile_types["types"]["grass"]["walkable"] is True
    assert object_types["types"]["stone_chunk"]["instance_count"] == 1
    assert render_profile["schema_version"] == "render-profile-v1"
    assert "terrain" in render_profile["draw_order"]
    assert tile_render_hints["hints"]["grass"]["visual_group"] == "terrain/grass"
    assert object_render_hints["hints"]["stone_chunk"]["render_mode"] == "sprite"
