from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from top_down_worldgen.render.layers import LayerRenderer


def test_renderer_scales_16px_tiles_when_32px_assets_are_missing(tmp_path: Path) -> None:
    """Ensure 32px rendering works when only the 16px tileset exists."""
    map_path = tmp_path / "generated_map.txt"
    debug_path = tmp_path / "tactical_map_debug.json"
    runtime_path = tmp_path / "tactical_map.json"
    output_path = tmp_path / "layer_base_map.png"

    map_path.write_text("SG\n++\n", encoding="utf-8")
    debug_path.write_text(json.dumps({}), encoding="utf-8")
    runtime_path.write_text(json.dumps({}), encoding="utf-8")

    renderer = LayerRenderer(Path("assets"), tile_size_px=32)
    rendered = renderer.render_all(
        map_path,
        debug_path,
        runtime_path,
        {"base": output_path},
        include_debug_images=False,
    )

    assert rendered == ["base"]
    assert Image.open(output_path).size == (64, 64)
