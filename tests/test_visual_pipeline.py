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
        profile_dir=Path("visual_profiles/default"),
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
    assert (visual_output / "debug/autotile_masks.json").exists()

    visual_layers = _read_json(result.visual_layers_path)
    assert "debug" not in visual_layers
    rows = visual_layers["layers"][0]["rows"]
    assert rows[0][0] == "forest.s"
    assert rows[1][1] == "road.es"
    assert rows[2][2] == "water.es"

    visual_objects = _read_json(result.visual_objects_path)
    assert visual_objects["items"][0]["sprite_id"] == "object.trench"
    assert visual_objects["items"][0]["sort_anchor"]["y"] == 1

    visual_chunks = _read_json(result.visual_chunks_path)
    assert visual_chunks["summary"]["total"] == 4


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
                ["tree_blocker", "road", "road", "grass"],
                ["grass", "road", "water", "water"],
                ["grass", "grass", "water", "grass"],
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
