from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "examples" / "read_map_package.py"


def test_map_package_docs_exist() -> None:
    """Ensure map package documentation is present."""
    assert (ROOT / "docs" / "map_package_v1.md").is_file()
    assert (ROOT / "docs" / "game_consumer_guide.md").is_file()


def test_read_map_package_example_loads_summary(tmp_path: Path) -> None:
    """Ensure the documented example can load a minimal package."""
    output_dir = tmp_path / "output"
    package_dir = output_dir / "map_package"
    (package_dir / "layers").mkdir(parents=True)
    (package_dir / "gameplay").mkdir()
    (package_dir / "objects").mkdir()

    _write_json(
        output_dir / "_manifest.json",
        {
            "files": [
                {
                    "kind": "map_package:index",
                    "path": "map_package/map.json",
                },
            ],
            "primary_outputs": [],
        },
    )
    _write_json(
        package_dir / "map.json",
        {
            "dimensions": {
                "width_tiles": 2,
                "height_tiles": 2,
                "tile_size_px": 16,
            },
            "points": {
                "start": {"x": 0, "y": 0},
                "goal": {"x": 1, "y": 1},
            },
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "terrain": "layers/terrain.json",
                "collision": "layers/collision.json",
                "movement_costs": "layers/movement_costs.json",
                "start_goal": "layers/start_goal.json",
            },
            "gameplay": {
                "enemy_spawn_zones": "gameplay/enemy_spawn_zones.json",
            },
            "objects": {
                "runtime_objects": "objects/runtime_objects.json",
            },
        },
    )
    _write_json(package_dir / "layers" / "tile_grid.json", {"rows": ["S+", "TG"]})
    _write_json(
        package_dir / "layers" / "terrain.json",
        {"rows": [["start", "grass"], ["tree_blocker", "goal"]]},
    )
    _write_json(
        package_dir / "layers" / "collision.json",
        {"rows": ["00", "10"]},
    )
    _write_json(
        package_dir / "layers" / "start_goal.json",
        {"start": {"x": 0, "y": 0}, "goal": {"x": 1, "y": 1}},
    )
    _write_json(
        package_dir / "layers" / "movement_costs.json",
        {"costs_by_tile": {"+": 1}},
    )
    _write_json(
        package_dir / "objects" / "runtime_objects.json",
        {"items": [{"id": "tree_0", "type": "tree"}]},
    )
    _write_json(package_dir / "gameplay" / "enemy_spawn_zones.json", {"items": []})

    module = _load_example_module()
    summary = module.load_summary(output_dir)

    assert summary.width == 2
    assert summary.height == 2
    assert summary.tile_size_px == 16
    assert summary.start == {"x": 0, "y": 0}
    assert summary.goal == {"x": 1, "y": 1}
    assert summary.runtime_object_count == 1
    assert summary.blocked_tile_count == 1
    assert summary.gameplay_layers == ["enemy_spawn_zones"]


def _load_example_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("read_map_package", EXAMPLE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["read_map_package"] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
