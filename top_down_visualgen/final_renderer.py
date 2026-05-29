from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

from .asset_loader import VisualAssetLoader
from .models import VisualProfile


class FinalAssetRenderer:
    """Render the final asset-backed visual map PNG."""

    def __init__(self, asset_loader: VisualAssetLoader | None = None) -> None:
        """Initialize the renderer.

        Args:
            asset_loader: Optional reusable asset loader.
        """
        self._asset_loader = asset_loader or VisualAssetLoader()

    def render(
        self,
        *,
        visual_layers: dict[str, Any],
        visual_objects: dict[str, Any],
        profile: VisualProfile,
        output_path: Path,
    ) -> dict[str, Any]:
        """Render final PNG from visual layers and asset manifest.

        Args:
            visual_layers: Visual layers JSON object.
            visual_objects: Visual objects JSON object.
            profile: Loaded visual profile.
            output_path: PNG output path.

        Returns:
            Render report JSON-compatible object.

        Raises:
            ValueError: If visual layer data is malformed.
            FileNotFoundError: If a required asset file is missing.
        """
        layer = _terrain_layer(visual_layers)
        rows = layer.get("rows")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Visual terrain layer contains no rows")
        height_tiles = len(rows)
        width_tiles = len(rows[0]) if isinstance(rows[0], list) else 0
        if width_tiles <= 0:
            raise ValueError("Visual terrain layer width must be positive")

        tile_size = _tile_size(profile, visual_layers)
        image = Image.new("RGBA", (width_tiles * tile_size, height_tiles * tile_size), (0, 0, 0, 255))
        missing_tiles: Counter[str] = Counter()
        missing_sprites: Counter[str] = Counter()
        tile_counts: Counter[str] = Counter()
        sprite_counts: Counter[str] = Counter()

        for y, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != width_tiles:
                raise ValueError("Visual terrain rows must have equal width")
            for x, tile_id in enumerate(row):
                if not isinstance(tile_id, str):
                    tile_id = "debug.missing_tile"
                asset = self._asset_loader.load_tile(profile, tile_id)
                if asset.missing:
                    missing_tiles[tile_id] += 1
                tile_counts[tile_id] += 1
                tile_image = _fit_tile(asset.image, tile_size)
                image.alpha_composite(tile_image, (x * tile_size, y * tile_size))

        sorted_objects = sorted(
            [item for item in visual_objects.get("items", []) if isinstance(item, dict)],
            key=lambda item: item.get("sort_key", []),
        )
        rendered_sprites = 0
        skipped_sprites = 0
        for item in sorted_objects:
            sprite_id = item.get("sprite_id")
            position = item.get("position")
            if not isinstance(sprite_id, str) or not isinstance(position, dict):
                skipped_sprites += 1
                continue
            x = position.get("x")
            y = position.get("y")
            if not isinstance(x, int) or not isinstance(y, int):
                skipped_sprites += 1
                continue
            asset = self._asset_loader.load_sprite(profile, sprite_id)
            if asset.missing:
                missing_sprites[sprite_id] += 1
            sprite_counts[sprite_id] += 1
            paste_x, paste_y = _sprite_paste_position(
                tile_x=x,
                tile_y=y,
                tile_size=tile_size,
                manifest=asset.manifest,
            )
            _alpha_composite_clipped(image, asset.image, paste_x, paste_y)
            rendered_sprites += 1

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGBA").save(output_path)

        return {
            "schema_version": "final-render-report-v1",
            "kind": "final_asset_render_report",
            "output": output_path.as_posix(),
            "size_px": {
                "width": image.width,
                "height": image.height,
            },
            "map_size_tiles": {
                "width": width_tiles,
                "height": height_tiles,
            },
            "tile_size_px": tile_size,
            "summary": {
                "rendered_tiles": width_tiles * height_tiles,
                "rendered_sprites": rendered_sprites,
                "skipped_sprites": skipped_sprites,
                "missing_tile_uses": sum(missing_tiles.values()),
                "missing_sprite_uses": sum(missing_sprites.values()),
                "unique_tiles": len(tile_counts),
                "unique_sprites": len(sprite_counts),
            },
            "top_tiles": _top_counts(tile_counts),
            "top_sprites": _top_counts(sprite_counts),
            "missing_tiles": dict(sorted(missing_tiles.items())),
            "missing_sprites": dict(sorted(missing_sprites.items())),
            "quality": {
                "status": "ok" if not missing_tiles and not missing_sprites and skipped_sprites == 0 else "warning",
            },
        }


def _alpha_composite_clipped(base: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(base.width, x + overlay.width)
    bottom = min(base.height, y + overlay.height)
    if right <= left or bottom <= top:
        return
    crop_left = left - x
    crop_top = top - y
    crop_right = crop_left + (right - left)
    crop_bottom = crop_top + (bottom - top)
    cropped = overlay.crop((crop_left, crop_top, crop_right, crop_bottom))
    base.alpha_composite(cropped, (left, top))


def _terrain_layer(visual_layers: dict[str, Any]) -> dict[str, Any]:
    layers = visual_layers.get("layers")
    if not isinstance(layers, list):
        raise ValueError("visual_layers.layers must be a list")
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "terrain_base":
            return layer
    raise ValueError("Missing terrain_base visual layer")


def _tile_size(profile: VisualProfile, visual_layers: dict[str, Any]) -> int:
    profile_size = profile.assets_manifest.get("tile_size")
    if isinstance(profile_size, list) and profile_size and isinstance(profile_size[0], int):
        return max(1, profile_size[0])
    layer_size = visual_layers.get("tile_size_px")
    if isinstance(layer_size, int) and layer_size > 0:
        return layer_size
    return 16


def _fit_tile(image: Image.Image, tile_size: int) -> Image.Image:
    if image.size == (tile_size, tile_size):
        return image
    return image.resize((tile_size, tile_size), Image.Resampling.NEAREST)


def _sprite_paste_position(
    *,
    tile_x: int,
    tile_y: int,
    tile_size: int,
    manifest: dict[str, Any],
) -> tuple[int, int]:
    pivot = manifest.get("pivot")
    if not (isinstance(pivot, list) and len(pivot) >= 2):
        pivot = manifest.get("sort_anchor")
    if not (isinstance(pivot, list) and len(pivot) >= 2):
        pivot = [tile_size // 2, tile_size]
    pivot_x = pivot[0] if isinstance(pivot[0], int) else tile_size // 2
    pivot_y = pivot[1] if isinstance(pivot[1], int) else tile_size
    anchor_x = tile_x * tile_size + tile_size // 2
    anchor_y = tile_y * tile_size + tile_size
    return anchor_x - pivot_x, anchor_y - pivot_y


def _top_counts(counter: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    return [
        {"id": key, "count": count}
        for key, count in counter.most_common(limit)
    ]
