from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from PIL import Image

from top_down_visualgen.final_renderer import FinalAssetRenderer
from top_down_visualgen.profile_loader import VisualProfileLoader


PROFILE_DIR = Path("top_down_visualgen/profiles/dark_forest")


def _load_final_render_module() -> ModuleType:
    """Load the final render CLI module."""
    path = Path("bin/render_final_asset_map.py")
    spec = importlib.util.spec_from_file_location("render_final_asset_map", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_final_asset_renderer_writes_png_and_report(tmp_path: Path) -> None:
    """Final renderer writes an asset-backed PNG with the expected dimensions."""
    profile = VisualProfileLoader().load(PROFILE_DIR)
    visual_layers = {
        "tile_size_px": 16,
        "layers": [
            {
                "id": "terrain_base",
                "rows": [
                    ["dirt.base", "road.straight_ew"],
                    ["swamp.fill", "forest.fill"],
                ],
            },
        ],
    }
    visual_objects = {
        "items": [
            {
                "sprite_id": "decor.reeds_01",
                "position": {"x": 0, "y": 0},
                "sort_key": [10, 0, 0, 0, 0],
            },
        ],
    }
    output_path = tmp_path / "final_render.png"

    report = FinalAssetRenderer().render(
        visual_layers=visual_layers,
        visual_objects=visual_objects,
        profile=profile,
        output_path=output_path,
    )

    assert output_path.exists()
    assert report["quality"]["status"] == "ok"
    assert report["summary"]["rendered_tiles"] == 4
    assert report["summary"]["rendered_sprites"] == 1
    with Image.open(output_path) as image:
        assert image.size == (32, 32)


def test_final_render_cli_renders_from_existing_visual_output(tmp_path: Path) -> None:
    """Standalone final render CLI helper renders from existing visual JSON files."""
    module = _load_final_render_module()
    render_final_asset_map = cast(Any, module).render_final_asset_map
    visual_output = tmp_path / "visual_map"
    visual_output.mkdir()
    (visual_output / "debug").mkdir()
    (visual_output / "visual_layers.json").write_text(
        '{"tile_size_px":16,"layers":[{"id":"terrain_base","rows":[["dirt.base"]]}]}',
        encoding="utf-8",
    )
    (visual_output / "visual_objects.json").write_text(
        '{"items":[{"sprite_id":"decor.reeds_01","position":{"x":0,"y":0},"sort_key":[10,0,0,0,0]}]}',
        encoding="utf-8",
    )

    report = render_final_asset_map(
        visual_output=visual_output,
        profile_dir=PROFILE_DIR,
        output_path=visual_output / "final_render.png",
        report_path=visual_output / "debug" / "final_render_report.json",
    )

    assert (visual_output / "final_render.png").exists()
    assert (visual_output / "debug" / "final_render_report.json").exists()
    assert report["summary"]["missing_tile_uses"] == 0
