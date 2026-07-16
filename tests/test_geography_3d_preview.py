from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = ROOT / "examples" / "render_geography_3d_preview.py"


def test_combined_terrain_traversal_preview_renders_tree_objects(tmp_path: Path) -> None:
    """Ensure the combined preview loads terrain and draws tree blockers."""
    output_dir = _write_minimal_output(tmp_path)
    renderer = _load_renderer_module()

    height_map = renderer.load_height_map(output_dir, overlay="terrain_traversal")

    assert height_map.terrain_rows is not None
    assert height_map.terrain_rows[0][1] == "tree_blocker"
    assert height_map.overlay_counts["tree"] == 1
    assert height_map.overlay_counts["blocked"] == 1
    assert height_map.overlay_counts["water"] == 1

    output_path = tmp_path / "terrain_traversal_se.png"
    renderer.render_view(
        height_map,
        view="se",
        output_path=output_path,
        output_size=(640, 480),
        draw_grid=True,
    )

    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(output_path).convert("RGB")
    tree_color = renderer.TERRAIN_TRAVERSAL_COLORS["tree"][:3]
    colors = image.getcolors(maxcolors=image.width * image.height)
    assert colors is not None
    assert any(color == tree_color for _, color in colors)


def test_combined_overlay_preserves_elevation_color_difference() -> None:
    """Ensure terrain tinting does not flatten distinct elevation colors."""
    renderer = _load_renderer_module()

    low = renderer._tile_color(1, "terrain_traversal", "reachable", "grass")
    high = renderer._tile_color(8, "terrain_traversal", "reachable", "grass")
    blocked = renderer._tile_color(1, "terrain_traversal", "blocked", "tree_blocker")

    assert low != high
    assert blocked != low


def _load_renderer_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_geography_3d_preview_test", RENDERER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load geography 3D renderer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_minimal_output(tmp_path: Path) -> Path:
    output_dir = tmp_path / "output"
    package_dir = output_dir / "map_package"
    layers_dir = package_dir / "layers"
    layers_dir.mkdir(parents=True)

    _write_json(
        package_dir / "map.json",
        {
            "dimensions": {"width_tiles": 3, "height_tiles": 2},
            "runtime_grids": "runtime_grids.json",
            "layers": {"terrain": "layers/terrain.json"},
            "points": {
                "start": {"x": 0, "y": 0},
                "goal": {"x": 2, "y": 1},
            },
        },
    )
    _write_json(
        package_dir / "runtime_grids.json",
        {
            "grids": {
                "height_grid": {"rows": [[0, 1, 2], [0, -1, 0]]},
                "collision_grid": {"rows": ["010", "000"]},
                "movement_grid": {
                    "rows": [[1.0, None, 1.0], [1.0, 2.0, 1.0]],
                },
            }
        },
    )
    _write_json(
        layers_dir / "terrain.json",
        {
            "rows": [
                ["start", "tree_blocker", "grass"],
                ["old_overgrown_road", "water_slow", "goal"],
            ]
        },
    )
    _write_json(
        output_dir / "tactical_map.json",
        {
            "elevation_generation_report": {
                "profile": {
                    "map_class": "test",
                    "active_range": [-1, 2],
                },
                "geography": {
                    "grids": {
                        "geographic_level_grid": {
                            "rows": [[0, 1, 2], [0, -1, 0]],
                        },
                        "source_grid": {"rows": ["GGG", "GWG"]},
                        "water_lowland_grid": {"rows": ["DDD", "DBD"]},
                    }
                },
            }
        },
    )
    _write_json(
        output_dir / "world_summary_report.json",
        {"world_generation": {"seed": 12345}},
    )
    return output_dir


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_bush_marker_uses_distinct_cyan_green_color() -> None:
    renderer = _load_renderer_module()
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    scale = renderer.RenderScale(tile_width=16.0, tile_height=8.0, height_step=4.0, offset_x=0.0, offset_y=0.0)

    renderer._draw_bush_marker(draw, center=(32.0, 32.0), scale=scale)

    colors = image.getcolors(maxcolors=image.width * image.height)
    assert colors is not None
    assert any(color == (74, 214, 166, 255) for _, color in colors)


def test_geography_preview_draws_translucent_water_volume(tmp_path: Path) -> None:
    """Ensure deep lake cells receive a translucent surface above the basin."""
    output_dir = _write_minimal_output(tmp_path)
    renderer = _load_renderer_module()
    height_map = renderer.load_height_map(output_dir, overlay="geography")

    # Turn the existing water cell into deep water so the volume is rendered.
    height_map.rows[1][1] = -3
    height_map.water_rows[1][1] = "B"
    output_path = tmp_path / "geography_water.png"
    renderer.render_view(
        height_map,
        view="nw",
        output_path=output_path,
        output_size=(640, 480),
        draw_grid=True,
    )

    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert renderer.WATER_SURFACE_LEVEL == -1
    assert renderer.WATER_VOLUME_COLOR[3] < 96
