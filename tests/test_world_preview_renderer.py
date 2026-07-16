from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = ROOT / "examples" / "render_world_preview.py"


def test_world_preview_renderer_writes_png(tmp_path: Path) -> None:
    """Ensure the preview renderer writes a PNG from a minimal package."""
    output_dir = _write_minimal_package(tmp_path)
    module = _load_renderer_module()

    summary = module.render_preview(
        output_dir,
        cell_size_px=8,
        draw_elevation_overlay=True,
        draw_transition_overlay=True,
        draw_places_overlay=True,
        draw_gameplay_zones_overlay=True,
        draw_routes_overlay=True,
        draw_world_graph_overlay=True,
    )

    assert summary.width_tiles == 3
    assert summary.height_tiles == 2
    assert summary.cell_size_px == 8
    assert summary.terrain_type_count == 6
    assert summary.blocked_tiles == 1
    assert summary.runtime_objects == 1
    assert summary.places == 1
    assert summary.gameplay_zones == 1
    assert summary.routes == 1
    assert summary.world_graph_edges == 1
    assert summary.output_path == output_dir / "world_preview.png"
    assert summary.output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_world_preview_renderer_cli_prints_summary(tmp_path: Path) -> None:
    """Ensure the preview renderer CLI prints a concise summary."""
    output_dir = _write_minimal_package(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(RENDERER_PATH),
            str(output_dir),
            "--cell-size",
            "6",
            "--elevation-overlay",
            "--transition-overlay",
            "--semantic-overlays",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Preview создан:" in result.stderr
    assert "Rendered:" not in result.stderr
    assert "terrain types:" not in result.stderr
    assert (output_dir / "world_preview.png").is_file()


def test_world_preview_renderer_cli_fails_on_missing_package(tmp_path: Path) -> None:
    """Ensure missing packages produce a non-zero exit code."""
    result = subprocess.run(
        [sys.executable, str(RENDERER_PATH), str(tmp_path / "missing")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Не удалось создать preview" in result.stderr


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
            "dimensions": {
                "width_tiles": 3,
                "height_tiles": 2,
                "tile_size_px": 16,
            },
            "runtime_grids": "runtime_grids.json",
            "world_graph": "world_graph.json",
            "routes": "routes.json",
            "gameplay_zones": "gameplay_zones.json",
            "elevation_transitions": "elevation_transitions.json",
            "layers": {
                "terrain": "layers/terrain.json",
                "collision": "layers/collision.json",
                "start_goal": "layers/start_goal.json",
            },
            "objects": {
                "runtime_objects": "objects/runtime_objects.json",
                "places": "objects/places.json",
            },
        },
    )
    _write_json(
        package_dir / "layers" / "terrain.json",
        {
            "rows": [
                ["start", "grass", "tree_blocker"],
                ["old_overgrown_road", "water_slow", "goal"],
            ],
        },
    )
    _write_json(package_dir / "layers" / "collision.json", {"rows": ["001", "000"]})
    _write_json(
        package_dir / "layers" / "start_goal.json",
        {"start": {"x": 0, "y": 0}, "goal": {"x": 2, "y": 1}},
    )
    _write_json(
        package_dir / "runtime_grids.json",
        {
            "grids": {
                "height_grid": {
                    "rows": [[0, 1, 2], [0, -1, 0]],
                },
            },
        },
    )
    _write_json(
        package_dir / "elevation_transitions.json",
        {
            "items": [
                {
                    "type": "step_up",
                    "from": {"x": 0, "y": 0},
                    "to": {"x": 1, "y": 0},
                    "suggested_connector": "slope",
                },
                {
                    "type": "bridge_edge",
                    "from": {"x": 1, "y": 0},
                    "to": {"x": 2, "y": 0},
                    "suggested_connector": "bridge",
                },
            ],
        },
    )
    _write_json(
        package_dir / "world_graph.json",
        {
            "nodes": [
                {"id": "place_0", "position": {"x": 1, "y": 0}},
                {"id": "marker:goal", "position": {"x": 2, "y": 1}},
            ],
            "edges": [
                {
                    "id": "edge_000",
                    "source": "place_0",
                    "target": "marker:goal",
                },
            ],
            "main_path": {"edge_ids": ["edge_000"]},
        },
    )
    _write_json(
        package_dir / "routes.json",
        {
            "items": [
                {
                    "id": "main_road_000",
                    "type": "main_road",
                    "waypoints": [{"x": 0, "y": 0}, {"x": 2, "y": 1}],
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
                    "bounds": {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1},
                    "entry_points": [{"position": {"x": 0, "y": 0}}],
                },
            ],
        },
    )
    _write_json(
        package_dir / "objects" / "places.json",
        {
            "items": [
                {
                    "id": "place_0",
                    "type": "safe_clearing",
                    "bounds": {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 1},
                    "entrances": [{"position": {"x": 1, "y": 0}}],
                },
            ],
        },
    )
    _write_json(
        package_dir / "objects" / "runtime_objects.json",
        {
            "items": [
                {
                    "id": "log_0",
                    "type": "fallen_log",
                    "x": 1,
                    "y": 1,
                    "footprint": [[1, 1], [2, 1]],
                },
            ],
        },
    )
    return output_dir


def _load_renderer_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_world_preview", RENDERER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_world_preview"] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
