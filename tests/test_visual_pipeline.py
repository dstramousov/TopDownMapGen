from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from top_down_visualgen.pipeline import VisualPipeline


def test_visual_pipeline_writes_contract_outputs(tmp_path: Path) -> None:
    """Visual pipeline writes the MVP output contract."""
    output_dir = tmp_path / "output"
    _write_minimal_world_package(output_dir)
    visual_output = output_dir / "visual_map"

    result = VisualPipeline().run(
        input_dir=output_dir,
        profile_dir=Path("top_down_visualgen/profiles/dark_forest"),
        output_dir=visual_output,
        preview=True,
        preview_tile_size_px=2,
        chunk_size_tiles=2,
    )

    assert result.visual_map_path.exists()
    assert result.visual_layers_path.exists()
    assert result.visual_objects_path.exists()
    assert result.visual_chunks_path.exists()
    assert result.preview_path is not None
    assert result.preview_path.exists()

    visual_map = _read_json(result.visual_map_path)
    assert visual_map["schema_version"] == "visual-map-v1"
    assert visual_map["contract"]["changes_gameplay"] is False
    assert visual_map["files"]["visual_layers"] == "visual_layers.json"
    assert visual_map["files"]["visual_objects"] == "visual_objects.json"
    assert visual_map["files"]["visual_chunks"] == "visual_chunks.json"
    assert visual_map["files"]["preview"] == "preview.png"
    assert visual_map["files"]["debug_autotile_masks"] == "debug/autotile_masks.json"
    assert visual_map["files"]["debug_autotile_report"] == "debug/autotile_report.json"
    assert (
        visual_map["files"]["debug_unmapped_terrain_report"]
        == "debug/unmapped_terrain_report.json"
    )
    assert (
        visual_map["files"]["debug_visual_density_report"]
        == "debug/visual_density_report.json"
    )
    assert (
        visual_map["files"]["debug_elevation_visual_report"]
        == "debug/elevation_visual_report.json"
    )
    assert (
        visual_map["files"]["debug_boundary_visual_report"]
        == "debug/boundary_visual_report.json"
    )
    assert (
        visual_map["files"]["debug_forest_mass_experiment_report"]
        == "debug/forest_mass_experiment_report.json"
    )
    assert (visual_output / "debug/autotile_masks.json").exists()
    assert (visual_output / "debug/autotile_report.json").exists()
    assert (visual_output / "debug/unmapped_terrain_report.json").exists()
    assert (visual_output / "debug/decoration_report.json").exists()
    assert (visual_output / "debug/place_treatment_report.json").exists()
    assert (visual_output / "debug/visual_density_report.json").exists()
    assert (visual_output / "debug/elevation_visual_report.json").exists()
    assert (visual_output / "debug/boundary_visual_report.json").exists()
    assert (visual_output / "debug/forest_mass_experiment_report.json").exists()
    assert result.debug_visual_density_report_path.exists()
    assert result.debug_elevation_visual_report_path.exists()
    assert result.debug_boundary_visual_report_path.exists()
    assert result.debug_forest_mass_experiment_report_path.exists()

    visual_layers = _read_json(result.visual_layers_path)
    assert "debug" not in visual_layers
    rows = visual_layers["layers"][0]["rows"]
    assert rows[0][0] == "forest.cap_n"
    assert rows[1][1] == "road.turn_es"
    assert rows[2][2] == "swamp.isolated"
    assert rows[3][3] == "grass.base"

    autotile_report = _read_json(visual_output / "debug/autotile_report.json")
    assert autotile_report["quality"]["status"] == "ok"
    assert autotile_report["summary"]["groups"]["road"] == 3

    unmapped_report = _read_json(visual_output / "debug/unmapped_terrain_report.json")
    assert unmapped_report["quality"]["status"] == "ok"
    assert unmapped_report["summary"]["counts"] == {}

    visual_objects = _read_json(result.visual_objects_path)
    assert visual_objects["summary"]["runtime_total"] == 1
    assert visual_objects["summary"]["decoration_total"] >= 1
    assert visual_objects["summary"]["place_treatment_total"] >= 1
    assert visual_objects["summary"]["elevation_visual_total"] >= 1
    assert visual_objects["summary"]["boundary_visual_total"] >= 1
    assert any(item["sprite_id"] == "object.trench" for item in visual_objects["items"])
    assert any(
        str(item["sprite_id"]).startswith("decor.")
        for item in visual_objects["items"]
    )
    assert any(
        item.get("source_object_type") == "visual_place_treatment"
        and item.get("scene_variant_id") == "minor_supplies"
        and item.get("visual_role")
        for item in visual_objects["items"]
    )
    assert any(
        item.get("source_object_type") == "visual_elevation"
        and item.get("elevation_visual_kind") in {"lowland", "raised", "transition"}
        for item in visual_objects["items"]
    )
    assert any(
        item.get("source_object_type") == "visual_boundary"
        and item.get("boundary_visual_type")
        for item in visual_objects["items"]
    )

    decoration_report = _read_json(visual_output / "debug/decoration_report.json")
    assert "swamp_isolated_reeds" in decoration_report["summary"]["by_rule"]

    place_report = _read_json(visual_output / "debug/place_treatment_report.json")
    assert place_report["schema_version"] == "visual-debug-place-treatment-report-v2"
    assert place_report["quality"]["status"] == "ok"
    assert "small_loot_pocket_scene" in place_report["summary"]["by_rule"]
    assert "minor_supplies" in place_report["summary"]["by_scene_variant"]
    assert place_report["summary"]["by_role"]

    density_report = _read_json(visual_output / "debug/visual_density_report.json")
    assert density_report["schema_version"] == "visual-density-report-v1"
    assert density_report["visual_objects"]["total"] == visual_objects["summary"]["total"]
    assert "by_category" in density_report
    assert "top_sprites" in density_report
    assert density_report["by_source"]["elevation_visual"] >= 1
    assert density_report["by_source"]["boundary_visual"] >= 1
    assert density_report["elevation_visual"]["lowlands"] >= 1
    assert density_report["boundary_visual"]["total"] >= 1

    elevation_visual_report = _read_json(visual_output / "debug/elevation_visual_report.json")
    assert elevation_visual_report["schema_version"] == "visual-debug-elevation-visual-report-v1"
    assert elevation_visual_report["quality"]["status"] == "ok"
    assert elevation_visual_report["summary"]["lowland_markers"] >= 1

    boundary_visual_report = _read_json(visual_output / "debug/boundary_visual_report.json")
    assert boundary_visual_report["schema_version"] == "visual-debug-boundary-visual-report-v1"
    assert boundary_visual_report["quality"]["status"] == "ok"
    assert boundary_visual_report["summary"]["total"] >= 1

    forest_mass_report = _read_json(
        visual_output / "debug/forest_mass_experiment_report.json"
    )
    assert forest_mass_report["schema_version"] == (
        "visual-debug-forest-mass-experiment-v1"
    )
    assert forest_mass_report["policy"]["changes_final_render"] is False
    assert forest_mass_report["policy"]["changes_gameplay"] is False
    assert forest_mass_report["summary"]["forest_tiles"] >= 1
    assert forest_mass_report["summary"]["forest_regions"] >= 1

    decoration_rules = _read_json(
        Path("top_down_visualgen/profiles/dark_forest/decoration_rules.json")
    )
    rule_ids = {rule["id"] for rule in decoration_rules["rules"]}
    assert "road_overgrown_patches" in rule_ids
    assert "road_influence_edge_grass" in rule_ids
    assert "ruin_floor_rubble" in rule_ids
    assert "ruin_wall_debris" in rule_ids

    place_rules = _read_json(
        Path("top_down_visualgen/profiles/dark_forest/place_visual_rules.json")
    )
    place_rule_ids = {rule["id"] for rule in place_rules["rules"]}
    assert "ruined_camp_scene" in place_rule_ids
    assert "small_loot_pocket_scene" in place_rule_ids

    sprite_ids = set(_read_json(
        Path("top_down_visualgen/profiles/dark_forest/visual_tilesets.json")
    )["sprites"])
    assert "decor.ruin_rubble_01" in sprite_ids
    assert "decor.fallen_bricks_01" in sprite_ids
    assert "decor.hidden_cache_marker_01" in sprite_ids
    assert "decor.old_backpack_01" in sprite_ids
    assert "decor.broken_column_01" in sprite_ids
    assert "decor.rusty_barbed_wire_01" in sprite_ids

    assert place_rules["schema_version"] == "place-visual-rules-v2"
    assert place_rules["world_style"]["id"] == "dark_forest_post_soviet_ruins"
    assert "object_role_distribution" in place_rules
    assert "scene_catalog" in place_rules
    ruined_camp_rule = next(
        rule for rule in place_rules["rules"] if rule["id"] == "ruined_camp_scene"
    )
    assert "scene_variants" in ruined_camp_rule
    assert ruined_camp_rule["scene_variants"][0]["weighted_pool"]

    micro_scene_doc = Path("docs/visual_micro_scenes_dark_forest.md")
    assert micro_scene_doc.exists()
    assert "dark_forest_post_soviet_ruins" in micro_scene_doc.read_text(
        encoding="utf-8"
    )

    elevation_doc = Path("docs/visual_elevation_dark_forest.md")
    assert elevation_doc.exists()
    elevation_doc_text = elevation_doc.read_text(encoding="utf-8")
    assert "visual_only_landmark" in elevation_doc_text
    assert "boundary_treatment" in elevation_doc_text

    elevation_rules = _read_json(
        Path("top_down_visualgen/profiles/dark_forest/elevation_visual_rules.json")
    )
    assert elevation_rules["schema_version"] == "elevation-visual-rules-v2"
    assert elevation_rules["style_decisions"]["level_4_policy"] == "visual_only_landmark"
    assert elevation_rules["levels"]["4"]["traversable"] is False
    assert elevation_rules["boundary_treatment"]["status"] == "separate_boundary_visual_system"

    boundary_rules = _read_json(
        Path("top_down_visualgen/profiles/dark_forest/boundary_visual_rules.json")
    )
    assert boundary_rules["schema_version"] == "boundary-visual-rules-v2"
    assert boundary_rules["policy"]["changes_gameplay"] is False
    assert "dense_forest_wall" in boundary_rules["boundary_types"]

    sprite_ids = set(_read_json(
        Path("top_down_visualgen/profiles/dark_forest/visual_tilesets.json")
    )["sprites"])
    assert "elevation.ancient_beacon_base" in sprite_ids
    assert "elevation.trench_wall_edge" in sprite_ids
    assert "boundary.dense_forest_wall" in sprite_ids

    visual_chunks = _read_json(result.visual_chunks_path)
    assert visual_chunks["summary"]["total"] == 4


def test_visual_step_renderer_writes_debug_pngs(tmp_path: Path) -> None:
    """Visual step renderer writes diagnostic PNGs."""
    output_dir = tmp_path / "output"
    _write_minimal_world_package(output_dir)
    steps_output = output_dir / "visual_map" / "debug" / "steps"

    from top_down_visualgen.package_loader import WorldPackageLoader
    from top_down_visualgen.profile_loader import VisualProfileLoader
    from top_down_visualgen.step_renderer import VisualPipelineStepRenderer

    world = WorldPackageLoader().load(output_dir)
    profile = VisualProfileLoader().load(Path("top_down_visualgen/profiles/dark_forest"))
    paths = VisualPipelineStepRenderer().render_steps(
        world=world,
        profile=profile,
        output_dir=steps_output,
        tile_size_px=2,
    )

    assert [path.name for path in paths] == [
        "00_world_terrain.png",
        "01_base_visual_tiles.png",
        "02_road_autotile.png",
        "03_water_autotile.png",
        "04_swamp_autotile.png",
        "05_forest_autotile.png",
        "06_autotile_fallbacks.png",
        "07_objects.png",
        "08_decoration.png",
        "09_place_treatment.png",
        "10_elevation_visual.png",
        "11_boundary_visual.png",
        "12_final_preview.png",
        "13_forest_mass_experiment.png",
        "14_forest_mass_overlay.png",
        "15_forest_mass_compare.png",
        "16_forest_mass_overlay_clean.png",
        "17_forest_mass_compare_clean.png",
    ]
    assert all(path.exists() for path in paths)
    assert (steps_output.parent / "forest_mass_experiment_report.json").exists()
    assert (steps_output.parent / "forest_mass_overlay_report.json").exists()
    assert (steps_output.parent / "forest_mass_overlay_clean_report.json").exists()
    clean_report = _read_json(steps_output.parent / "forest_mass_overlay_clean_report.json")
    assert clean_report["schema_version"] == "visual-debug-forest-mass-overlay-v2"
    assert clean_report["policy"]["changes_final_render"] is False
    assert clean_report["quality"]["bounds_policy"] == "reject_full_bounds_outside_canvas"


def _write_minimal_world_package(output_dir: Path) -> None:
    package_dir = output_dir / "map_package"
    (package_dir / "layers").mkdir(parents=True)
    (package_dir / "objects").mkdir(parents=True)

    _write_json(
        package_dir / "map.json",
        {
            "schema_version": "map-package-map-v11",
            "package_schema_version": "map-package-v1",
            "generator_version": "0.0.52",
            "resolved_seed": 123,
            "profile": "test",
            "dimensions": {"width_tiles": 4, "height_tiles": 4, "tile_size_px": 16},
            "layers": {"terrain": "layers/terrain.json"},
            "elevation_model": "elevation_model.json",
            "elevation_features": "elevation_features.json",
            "elevation_transitions": "elevation_transitions.json",
            "objects": {
                "runtime_objects": "objects/runtime_objects.json",
                "places": "objects/places.json",
            },
        },
    )
    _write_json(output_dir / "_manifest.json", {"schema_version": "generation-manifest-v39"})
    _write_json(
        package_dir / "layers/terrain.json",
        {
            "schema_version": "terrain-layer-v1",
            "kind": "terrain",
            "width": 4,
            "height": 4,
            "format": "type_rows",
            "rows": [
                ["tree_blocker", "grass", "ruin_wall_blocker", "grass"],
                ["tree_blocker", "old_overgrown_road", "road", "grass"],
                ["grass", "road", "water_slow", "water"],
                ["cracked_ground", "ruin_floor", "water", "goal"],
            ],
        },
    )
    _write_json(
        package_dir / "runtime_grids.json",
        {
            "schema_version": "runtime-grids-v1",
            "kind": "runtime_grids",
            "grids": {
                "height_grid": {
                    "rows": [
                        [0, 1, 0, 0],
                        [0, -1, 0, 0],
                        [0, 0, 2, 0],
                        [0, 0, 0, 4],
                    ]
                }
            },
        },
    )
    _write_json(
        package_dir / "objects/runtime_objects.json",
        {
            "schema_version": "object-instances-v4",
            "kind": "runtime_objects",
            "items": [
                {
                    "id": "trench_000",
                    "type": "trench",
                    "x": 1,
                    "y": 1,
                    "position": [1, 1],
                    "sort_anchor": {
                        "x": 1,
                        "y": 1,
                        "elevation": -1,
                        "space": "tile",
                        "rule": "y_then_elevation_then_x",
                    },
                    "draw_layer": "terrain_overlay",
                }
            ],
        },
    )
    for relative_path, payload in {
        "objects/places.json": {
            "schema_version": "places-v3",
            "items": [
                {
                    "id": "loot_place_000",
                    "type": "small_loot_pocket",
                    "center": {"x": 3, "y": 0},
                    "bounds": {"min_x": 3, "min_y": 0, "max_x": 3, "max_y": 1},
                    "entrances": []
                }
            ],
        },
        "world_graph.json": {"schema_version": "world-graph-v2", "nodes": []},
        "routes.json": {"schema_version": "routes-v1", "items": []},
        "gameplay_zones.json": {"schema_version": "gameplay-zones-v1", "items": []},
        "elevation_model.json": {"schema_version": "elevation-model-v5", "features": []},
        "elevation_features.json": {"schema_version": "elevation-features-v3", "items": []},
        "elevation_transitions.json": {
            "schema_version": "elevation-transitions-v4",
            "items": [
                {"id": "transition_0", "type": "slope", "position": {"x": 1, "y": 1}}
            ],
        },
    }.items():
        _write_json(package_dir / relative_path, payload)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
