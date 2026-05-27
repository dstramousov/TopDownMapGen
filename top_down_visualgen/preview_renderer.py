from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


class PreviewRenderer:
    """Render a compact visual preview image."""

    def render(
        self,
        *,
        visual_layers: dict[str, Any],
        visual_objects: dict[str, Any],
        tilesets: dict[str, Any],
        output_path: Path,
        tile_size_px: int | None = None,
    ) -> None:
        """Render visual layers and object anchors to a PNG image.

        Args:
            visual_layers: Visual layers JSON object.
            visual_objects: Visual objects JSON object.
            tilesets: Visual tileset/color rules.
            output_path: PNG output path.
            tile_size_px: Optional preview tile size override.

        Raises:
            ValueError: If visual layer rows are missing or malformed.
        """
        layer = _terrain_layer(visual_layers)
        rows = layer.get("rows")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Visual terrain layer contains no rows")

        height = len(rows)
        width = len(rows[0]) if isinstance(rows[0], list) else 0
        if width <= 0:
            raise ValueError("Visual terrain layer width must be positive")

        tile_size = tile_size_px or _int_value(visual_layers.get("tile_size_px"), 16)
        tile_size = max(1, tile_size)
        tile_colors = _tile_colors(tilesets)
        object_colors = _object_colors(tilesets)
        image = Image.new("RGB", (width * tile_size, height * tile_size), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        for y, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != width:
                raise ValueError("Visual terrain rows must have equal width")
            for x, tile_id in enumerate(row):
                color = tile_colors.get(tile_id, tile_colors.get("terrain.unknown", "#ff00ff"))
                draw.rectangle(_tile_rect(x, y, tile_size), fill=color)

        for item in visual_objects.get("items", []):
            if not isinstance(item, dict):
                continue
            position = item.get("position")
            if not isinstance(position, dict):
                continue
            x = position.get("x")
            y = position.get("y")
            if not isinstance(x, int) or not isinstance(y, int):
                continue
            sprite_id = item.get("sprite_id")
            color = object_colors.get(sprite_id, object_colors.get("object.generic", "#ffffff"))
            self._draw_object_anchor(draw, x, y, tile_size, color)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)

    @staticmethod
    def _draw_object_anchor(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        tile_size: int,
        color: str,
    ) -> None:
        margin = max(1, tile_size // 4)
        left = x * tile_size + margin
        top = y * tile_size + margin
        right = (x + 1) * tile_size - margin
        bottom = (y + 1) * tile_size - margin
        if right <= left:
            right = left + 1
        if bottom <= top:
            bottom = top + 1
        draw.ellipse((left, top, right, bottom), fill=color)


def _terrain_layer(visual_layers: dict[str, Any]) -> dict[str, Any]:
    layers = visual_layers.get("layers")
    if not isinstance(layers, list):
        raise ValueError("visual_layers.layers must be a list")
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "terrain_base":
            return layer
    raise ValueError("Missing terrain_base visual layer")


def _tile_colors(tilesets: dict[str, Any]) -> dict[str, str]:
    return _colors_from_section(tilesets, "tiles")


def _object_colors(tilesets: dict[str, Any]) -> dict[str, str]:
    return _colors_from_section(tilesets, "sprites")


def _colors_from_section(tilesets: dict[str, Any], section_name: str) -> dict[str, str]:
    section = tilesets.get(section_name, {})
    if not isinstance(section, dict):
        return {}
    result: dict[str, str] = {}
    for item_id, item in section.items():
        if not isinstance(item_id, str) or not isinstance(item, dict):
            continue
        color = item.get("debug_color")
        if isinstance(color, str) and color.startswith("#"):
            result[item_id] = color
    return result


def _tile_rect(x: int, y: int, tile_size: int) -> tuple[int, int, int, int]:
    return (
        x * tile_size,
        y * tile_size,
        (x + 1) * tile_size - 1,
        (y + 1) * tile_size - 1,
    )


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) and value > 0 else default
