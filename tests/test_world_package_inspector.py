from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_PATH = ROOT / "examples" / "inspect_world_package.py"


def test_world_package_inspector_loads_minimal_package(tmp_path: Path) -> None:
    """Ensure the external inspector can load a minimal world package."""
    output_dir = _write_minimal_package(tmp_path)
    module = _load_inspector_module()

    report = module.inspect_world_package(output_dir)

    assert report.width == 2
    assert report.height == 2
    assert report.tile_size_px == 16
    assert report.start == {"x": 0, "y": 0}
    assert report.goal == {"x": 1, "y": 1}
    assert report.collision.passable == 3
    assert report.collision.blocked == 1
    assert report.world_graph_node_count == 3
    assert report.world_graph_edge_count == 2
    assert report.world_graph_main_path_length == 3
    assert report.route_count == 1
    assert report.route_type_counts == {"main_road": 1}
    assert report.gameplay_zone_count == 1
    assert report.gameplay_zone_type_counts == {"safe_area": 1}
    assert report.runtime_object_count == 1
    assert report.runtime_object_type_count == 1
    assert report.place_count == 1
    assert report.tile_type_count == 4
    assert report.object_type_count == 1
    assert report.tile_render_hint_count == 4
    assert report.object_render_hint_count == 1
    assert report.gameplay_counts == {
        "combat_zones": 1,
        "enemy_spawn_zones": 0,
    }


def test_world_package_inspector_cli_prints_summary(tmp_path: Path) -> None:
    """Ensure the inspector CLI prints a concise consumer-facing summary."""
    output_dir = _write_minimal_package(tmp_path)

    result = subprocess.run(
        [sys.executable, str(INSPECTOR_PATH), str(output_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output = result.stderr

    assert "World package: OK" in output
    assert "Map: 2x2 tiles, tile size 16 px" in output
    assert "world_graph: OK, nodes=3, edges=2, main_path_nodes=3" in output
    assert "routes: OK, total=1, types={'main_road': 1}" in output
    assert "gameplay_zones: OK, total=1, types={'safe_area': 1}" in output
    assert "runtime objects: 1 total, 1 types" in output
    assert "package is loadable by an external consumer" in output


def test_world_package_inspector_cli_fails_on_missing_package(tmp_path: Path) -> None:
    """Ensure missing packages produce a non-zero exit code."""
    result = subprocess.run(
        [sys.executable, str(INSPECTOR_PATH), str(tmp_path / "missing")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "World package: FAILED" in result.stderr


def _write_minimal_package(tmp_path: Path) -> Path:
    output_dir = tmp_path / "output"
    package_dir = output_dir / "map_package"
    for relative_dir in ("layers", "gameplay", "objects", "catalogs", "render"):
        (package_dir / relative_dir).mkdir(parents=True, exist_ok=True)

    _write_json(
        output_dir / "_manifest.json",
        {
            "primary_outputs": [
                {"kind": "map_package:index", "path": "map_package/map.json"},
            ],
            "files": [],
        },
    )
    _write_json(
        package_dir / "map.json",
        {
            "generator_version": "0.0.test",
            "package_schema_version": "map-package-v1",
            "resolved_seed": 123,
            "profile": "test",
            "dimensions": {
                "width_tiles": 2,
                "height_tiles": 2,
                "tile_size_px": 16,
            },
            "points": {
                "start": {"x": 0, "y": 0},
                "goal": {"x": 1, "y": 1},
            },
            "world_graph": "world_graph.json",
            "routes": "routes.json",
            "gameplay_zones": "gameplay_zones.json",
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "terrain": "layers/terrain.json",
                "movement_costs": "layers/movement_costs.json",
                "collision": "layers/collision.json",
                "elevation": "layers/elevation.json",
                "start_goal": "layers/start_goal.json",
            },
            "gameplay": {
                "combat_zones": "gameplay/combat_zones.json",
                "enemy_spawn_zones": "gameplay/enemy_spawn_zones.json",
            },
            "objects": {
                "runtime_objects": "objects/runtime_objects.json",
                "places": "objects/places.json",
            },
            "catalogs": {
                "tile_types": "catalogs/tile_types.json",
                "object_types": "catalogs/object_types.json",
            },
            "render": {
                "profile": "render/render_profile.json",
                "tile_render_hints": "render/tile_render_hints.json",
                "object_render_hints": "render/object_render_hints.json",
            },
        },
    )
    _write_json(package_dir / "layers" / "tile_grid.json", {"rows": ["S+", "TG"]})
    _write_json(
        package_dir / "layers" / "terrain.json",
        {"rows": [["start", "grass"], ["tree_blocker", "goal"]]},
    )
    _write_json(package_dir / "layers" / "collision.json", {"rows": ["00", "10"]})
    _write_json(
        package_dir / "layers" / "movement_costs.json",
        {"costs_by_type": {"start": 1, "grass": 1, "goal": 1}},
    )
    _write_json(
        package_dir / "layers" / "elevation.json",
        {"elevation": {"cells": [{"x": 0, "y": 1, "level": -1}]}},
    )
    _write_json(
        package_dir / "layers" / "start_goal.json",
        {"start": {"x": 0, "y": 0}, "goal": {"x": 1, "y": 1}},
    )
    _write_json(
        package_dir / "gameplay" / "combat_zones.json",
        {"items": [{"id": "zone_0"}]},
    )
    _write_json(package_dir / "gameplay" / "enemy_spawn_zones.json", {"items": []})
    _write_json(
        package_dir / "world_graph.json",
        {
            "nodes": [
                {"id": "marker:start", "type": "start"},
                {"id": "place_0", "type": "test_place"},
                {"id": "marker:goal", "type": "goal"},
            ],
            "edges": [
                {"id": "edge_000", "source": "marker:start", "target": "place_0"},
                {"id": "edge_001", "source": "place_0", "target": "marker:goal"},
            ],
            "main_path": {"node_ids": ["marker:start", "place_0", "marker:goal"]},
        },
    )
    _write_json(
        package_dir / "routes.json",
        {
            "items": [
                {
                    "id": "main_road_000",
                    "type": "main_road",
                    "node_ids": ["marker:start", "place_0", "marker:goal"],
                },
            ],
        },
    )
    _write_json(
        package_dir / "gameplay_zones.json",
        {
            "items": [
                {
                    "id": "zone_000",
                    "type": "safe_area",
                    "linked_markers": ["start"],
                },
            ],
        },
    )
    _write_json(
        package_dir / "objects" / "runtime_objects.json",
        {"items": [{"id": "tree_0", "type": "tree"}]},
    )
    _write_json(
        package_dir / "objects" / "places.json",
        {"items": [{"id": "place_0", "type": "test_place"}]},
    )
    _write_json(
        package_dir / "catalogs" / "tile_types.json",
        {"types": {"start": {}, "grass": {}, "tree_blocker": {}, "goal": {}}},
    )
    _write_json(
        package_dir / "catalogs" / "object_types.json",
        {"types": {"tree": {}}},
    )
    _write_json(package_dir / "render" / "render_profile.json", {"kind": "render_profile"})
    _write_json(
        package_dir / "render" / "tile_render_hints.json",
        {"hints": {"start": {}, "grass": {}, "tree_blocker": {}, "goal": {}}},
    )
    _write_json(
        package_dir / "render" / "object_render_hints.json",
        {"hints": {"tree": {}}},
    )
    return output_dir


def _load_inspector_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("inspect_world_package", INSPECTOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["inspect_world_package"] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
