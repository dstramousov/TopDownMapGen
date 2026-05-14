from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from top_down_worldgen.logging_utils import timed_stage


LOGGER = logging.getLogger(__name__)


class LayerRenderer:
    """Renders all debug map layers from final tactical data."""

    TILE_FILES = {
        "+": "grass_plus.png",
        ".": "old_road_dot.png",
        "T": "tree_T.png",
        "b": "bush_b.png",
        "f": "flower_f.png",
        "m": "mushroom_m.png",
        "w": "water_w.png",
        "c": "cracked_ground_c.png",
        "#": "ruin_wall_hash.png",
        "R": "ruin_floor_R.png",
        "S": "start_S.png",
        "G": "goal_G.png",
    }

    def __init__(self, assets_dir: Path, tile_size_px: int = 16) -> None:
        """Initialize renderer.

        Args:
            assets_dir: Asset root directory.
            tile_size_px: Tile size in pixels.
        """
        if tile_size_px not in {16, 32}:
            raise ValueError("tile_size_px must be 16 or 32")
        self._tile_size_px = tile_size_px
        self._tiles_dir = assets_dir / f"tiles_{tile_size_px}"
        self._tiles = self._load_tiles()

    def render_all(
        self,
        map_path: Path,
        tactical_debug_path: Path,
        outputs: dict[str, Path],
        *,
        include_debug_images: bool = True,
    ) -> list[str]:
        """Render map layers.

        Args:
            map_path: ASCII map path.
            tactical_debug_path: Debug tactical map path.
            outputs: Output layer paths by name.
            include_debug_images: Whether to render PNG debug overlays.

        Returns:
            Names of rendered layers.
        """
        with timed_stage(
            LOGGER,
            "LayerRenderer.render_all",
            map_path=map_path,
            tactical_debug_path=tactical_debug_path,
            tile_size_px=self._tile_size_px,
            include_debug_images=include_debug_images,
        ) as metrics:
            rows = self._read_rows(map_path)
            data = json.loads(tactical_debug_path.read_text(encoding="utf-8"))
            base = self._render_base(rows)
            base.save(outputs["base"])
            rendered_layers = ["base"]

            if include_debug_images:
                overlay_specs = {
                    "combat": {"combat"},
                    "cover": {"cover"},
                    "choke": {"choke"},
                    "flank": {"flank"},
                    "spawn": {"spawn"},
                    "fallback": {"fallback"},
                    "all": {"combat", "cover", "choke", "flank", "spawn", "fallback"},
                }
                for name, layers in overlay_specs.items():
                    self._save_overlay(base, data, outputs[name], layers)
                    rendered_layers.append(name)
            else:
                LOGGER.info("PNG debug layers skipped by CLI flag")

            metrics.update(
                {
                    "map_rows": len(rows),
                    "map_cols": len(rows[0]) if rows else 0,
                    "combat_zones": len(data.get("combat_zones", [])),
                    "cover_points": len(data.get("cover_points", [])),
                    "choke_points": len(data.get("choke_points", [])),
                    "flank_routes": len(data.get("flank_routes", [])),
                    "enemy_spawn_zones": len(data.get("enemy_spawn_zones", [])),
                    "fallback_positions": len(data.get("fallback_positions", [])),
                    "rendered_layers": len(rendered_layers),
                    "debug_layers_rendered": max(0, len(rendered_layers) - 1),
                },
            )
            return rendered_layers

    def _save_overlay(
        self,
        base: Image.Image,
        data: dict[str, Any],
        output_path: Path,
        layers: set[str],
    ) -> None:
        dimmed = Image.alpha_composite(base, Image.new("RGBA", base.size, (0, 0, 0, 95)))
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = self._font(max(8, self._tile_size_px // 2))

        if "combat" in layers:
            self._draw_combat(draw, data, font)
        if "cover" in layers:
            self._draw_cover(draw, data)
        if "choke" in layers:
            self._draw_choke(draw, data)
        if "flank" in layers:
            self._draw_flank(draw, data)
        if "spawn" in layers:
            self._draw_spawn(draw, data)
        if "fallback" in layers:
            self._draw_fallback(draw, data)

        Image.alpha_composite(dimmed, overlay).save(output_path)

    def _render_base(self, rows: list[str]) -> Image.Image:
        image = Image.new(
            "RGBA",
            (len(rows[0]) * self._tile_size_px, len(rows) * self._tile_size_px),
            (0, 0, 0, 255),
        )
        for y, row in enumerate(rows):
            for x, symbol in enumerate(row):
                image.alpha_composite(
                    self._tiles.get(symbol, self._tiles["+"]),
                    (x * self._tile_size_px, y * self._tile_size_px),
                )
        return image

    def _draw_combat(self, draw: ImageDraw.ImageDraw, data: dict[str, Any], font: ImageFont.ImageFont) -> None:
        colors = {
            "safe_start": ((80, 230, 120, 60), (80, 255, 120, 220)),
            "goal_encounter": ((190, 80, 230, 70), (210, 100, 255, 225)),
            "central_ruins_combat": ((235, 65, 65, 75), (255, 60, 60, 235)),
            "side_ruin_encounter": ((255, 155, 55, 65), (255, 160, 55, 225)),
            "forest_ambush": ((240, 220, 80, 60), (255, 235, 85, 220)),
        }
        for zone in data.get("combat_zones", []):
            if not isinstance(zone, dict):
                continue
            center = self._point(zone.get("center"))
            if center is None:
                continue
            radius = int(zone.get("radius", 1)) * self._tile_size_px
            cx = center[0] * self._tile_size_px + self._tile_size_px // 2
            cy = center[1] * self._tile_size_px + self._tile_size_px // 2
            fill, outline = colors.get(str(zone.get("type", "")), ((255, 255, 255, 45), (255, 255, 255, 190)))
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill, outline=outline, width=2)
            draw.text((cx + 4, cy + 4), str(zone.get("id", "")), font=font, fill=(255, 255, 255, 235), stroke_width=1, stroke_fill=(0, 0, 0, 220))

    def _draw_cover(self, draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
        for cover in data.get("cover_points", []):
            if not isinstance(cover, dict):
                continue
            position = self._point(cover.get("position"))
            if position is None:
                continue
            x = position[0] * self._tile_size_px + self._tile_size_px // 2
            y = position[1] * self._tile_size_px + self._tile_size_px // 2
            hard = str(cover.get("cover_type", "")) == "hard"
            radius = max(2, self._tile_size_px // (5 if hard else 6))
            color = (55, 120, 255, 220) if hard else (60, 230, 210, 185)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)

    def _draw_choke(self, draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
        for choke in data.get("choke_points", []):
            if not isinstance(choke, dict):
                continue
            position = self._point(choke.get("position"))
            if position is None:
                continue
            x = position[0] * self._tile_size_px + self._tile_size_px // 2
            y = position[1] * self._tile_size_px + self._tile_size_px // 2
            radius = max(4, self._tile_size_px // 3)
            draw.line((x - radius, y, x + radius, y), fill=(255, 40, 40, 235), width=2)
            draw.line((x, y - radius, x, y + radius), fill=(255, 40, 40, 235), width=2)

    def _draw_flank(self, draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
        for route in data.get("flank_routes", []):
            if not isinstance(route, dict):
                continue
            points = []
            for waypoint in route.get("waypoints", []):
                point = self._point(waypoint)
                if point is not None:
                    points.append((
                        point[0] * self._tile_size_px + self._tile_size_px // 2,
                        point[1] * self._tile_size_px + self._tile_size_px // 2,
                    ))
            if len(points) >= 2:
                concealment = float(route.get("concealment", 0.0))
                alpha = int(130 + min(105, concealment * 105))
                draw.line(points, fill=(255, 230, 70, alpha), width=max(2, self._tile_size_px // 5), joint="curve")

    def _draw_spawn(self, draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
        for spawn in data.get("enemy_spawn_zones", []):
            if not isinstance(spawn, dict):
                continue
            position = self._point(spawn.get("position"))
            if position is None:
                continue
            cx = position[0] * self._tile_size_px + self._tile_size_px // 2
            cy = position[1] * self._tile_size_px + self._tile_size_px // 2
            radius = max(4, self._tile_size_px // 3)
            spawn_type = str(spawn.get("spawn_type", ""))
            if spawn_type == "wave_entry":
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 70, 70, 115), outline=(255, 40, 40, 245), width=2)
            elif spawn_type == "blocking_squad":
                draw.rectangle((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 180, 70, 115), outline=(255, 160, 40, 245), width=2)
            else:
                draw.rectangle((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 90, 255, 100), outline=(255, 90, 255, 240), width=2)

    def _draw_fallback(self, draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
        for fallback in data.get("fallback_positions", []):
            if not isinstance(fallback, dict):
                continue
            position = self._point(fallback.get("position"))
            if position is None:
                continue
            cx = position[0] * self._tile_size_px + self._tile_size_px // 2
            cy = position[1] * self._tile_size_px + self._tile_size_px // 2
            size = max(5, self._tile_size_px // 2)
            points = [(cx, cy - size), (cx - size, cy + size), (cx + size, cy + size)]
            draw.polygon(points, fill=(115, 255, 120, 210), outline=(255, 255, 255, 235))

    def _load_tiles(self) -> dict[str, Image.Image]:
        with timed_stage(
            LOGGER,
            "LayerRenderer._load_tiles",
            tiles_dir=self._tiles_dir,
            tile_size_px=self._tile_size_px,
        ) as metrics:
            tiles: dict[str, Image.Image] = {}
            resized_count = 0
            for symbol, filename in self.TILE_FILES.items():
                path = self._tiles_dir / filename
                if not path.exists():
                    raise FileNotFoundError(path)
                image = Image.open(path).convert("RGBA")
                if image.size != (self._tile_size_px, self._tile_size_px):
                    image = image.resize(
                        (self._tile_size_px, self._tile_size_px),
                        Image.Resampling.NEAREST,
                    )
                    resized_count += 1
                tiles[symbol] = image
            metrics.update({"tiles_loaded": len(tiles), "tiles_resized": resized_count})
            return tiles

    @staticmethod
    def _read_rows(map_path: Path) -> list[str]:
        rows = [line for line in map_path.read_text(encoding="utf-8").splitlines() if line]
        if not rows:
            raise ValueError("Map file is empty")
        width = len(rows[0])
        if any(len(row) != width for row in rows):
            raise ValueError("Map rows must have equal width")
        return rows

    @staticmethod
    def _point(value: Any) -> tuple[int, int] | None:
        if not isinstance(value, list) or len(value) != 2:
            return None
        return int(value[0]), int(value[1])

    @staticmethod
    def _font(size: int) -> ImageFont.ImageFont:
        for candidate in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]:
            path = Path(candidate)
            if path.exists():
                return ImageFont.truetype(str(path), size)
        return ImageFont.load_default()
