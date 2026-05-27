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
    assert (visual_output / "debug/autotile_masks.json").exists()
    assert (visual_output / "debug/autotile_report.json").exists()
    assert (visual_output / "debug/unmapped_terrain_report.json").exists()
    assert (visual_output / "debug/decoration_report.json").exists()

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
    assert any(item["sprite_id"] == "object.trench" for item in visual_objects["items"])
    assert any(
        str(item["sprite_id"]).startswith("decor.")
        for item in visual_objects["items"]
    )

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
        "09_final_preview.png",
    ]
    assert all(path.exists() for path in paths)


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
                ["tree_blocker", "grass", "grass", "grass"],
                ["tree_blocker", "old_overgrown_road", "road", "grass"],
                ["grass", "road", "water_slow", "water"],
                ["cracked_ground", "flower_decor", "water", "goal"],
            ],
        },
    )
    _write_json(
        package_dir / "runtime_grids.json",
        {"schema_version": "runtime-grids-v1", "kind": "runtime_grids", "grids": {}},
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
        "objects/places.json": {"schema_version": "places-v3", "items": []},
        "world_graph.json": {"schema_version": "world-graph-v2", "nodes": []},
        "routes.json": {"schema_version": "routes-v1", "items": []},
        "gameplay_zones.json": {"schema_version": "gameplay-zones-v1", "items": []},
        "elevation_model.json": {"schema_version": "elevation-model-v5", "features": []},
    }.items():
        _write_json(package_dir / relative_path, payload)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
