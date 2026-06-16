from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .boundary_visual import BoundaryVisualMapper
from .decoration import DecorationMapper, merge_visual_objects
from .elevation_visual import ElevationVisualMapper
from .forest_mass import (
    ForestMassExperimentBuilder,
    render_forest_mass_experiment,
    render_forest_mass_overlay,
    render_forest_mass_overlay_clean,
    render_forest_mass_overlay_placement_fix,
)
from .io import write_json_object
from .models import VisualProfile, WorldPackage
from .object_mapper import ObjectVisualMapper
from .place_treatment import PlaceTreatmentMapper
from .terrain_mapper import TerrainVisualMapper


class VisualPipelineStepRenderer:
    """Render diagnostic images for visual pipeline stages."""

    def __init__(
        self,
        *,
        terrain_mapper: TerrainVisualMapper | None = None,
        object_mapper: ObjectVisualMapper | None = None,
        decoration_mapper: DecorationMapper | None = None,
        place_treatment_mapper: PlaceTreatmentMapper | None = None,
        elevation_visual_mapper: ElevationVisualMapper | None = None,
        boundary_visual_mapper: BoundaryVisualMapper | None = None,
        forest_mass_experiment_builder: ForestMassExperimentBuilder | None = None,
    ) -> None:
        """Initialize the step renderer.

        Args:
            terrain_mapper: Optional terrain mapper.
            object_mapper: Optional object mapper.
            decoration_mapper: Optional decoration mapper.
            place_treatment_mapper: Optional place treatment mapper.
            elevation_visual_mapper: Optional elevation visual mapper.
            boundary_visual_mapper: Optional boundary visual mapper.
            forest_mass_experiment_builder: Optional forest mass experiment builder.
        """
        self._terrain_mapper = terrain_mapper or TerrainVisualMapper()
        self._object_mapper = object_mapper or ObjectVisualMapper()
        self._decoration_mapper = decoration_mapper or DecorationMapper()
        self._place_treatment_mapper = place_treatment_mapper or PlaceTreatmentMapper()
        self._elevation_visual_mapper = elevation_visual_mapper or ElevationVisualMapper()
        self._boundary_visual_mapper = boundary_visual_mapper or BoundaryVisualMapper()
        self._forest_mass_experiment_builder = (
            forest_mass_experiment_builder or ForestMassExperimentBuilder()
        )

    def render_steps(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        output_dir: Path,
        tile_size_px: int | None = None,
    ) -> list[Path]:
        """Render visual pipeline step images.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            output_dir: Directory for step PNG files.
            tile_size_px: Optional debug tile size override.

        Returns:
            List of generated image paths.
        """
        terrain_rows = _terrain_rows(world.terrain)
        visual_layers = self._terrain_mapper.map_terrain(world, profile)
        debug = visual_layers.get("debug")
        autotile_rows = _autotile_rows(debug)
        runtime_visual_objects = self._object_mapper.map_objects(world, profile)
        decoration_result = self._decoration_mapper.map_decorations(
            world=world,
            profile=profile,
            visual_layers=visual_layers,
            visual_debug=debug if isinstance(debug, dict) else {},
        )
        place_treatment_result = self._place_treatment_mapper.map_place_treatments(
            world=world,
            profile=profile,
            visual_layers=visual_layers,
        )
        elevation_visual_result = self._elevation_visual_mapper.map_elevation_visual(
            world=world,
            profile=profile,
            visual_layers=visual_layers,
        )
        boundary_visual_result = self._boundary_visual_mapper.map_boundary_visual(
            world=world,
            profile=profile,
            visual_layers=visual_layers,
        )
        forest_mass_experiment_result = self._forest_mass_experiment_builder.build(
            world=world,
            profile=profile,
        )
        visual_objects = merge_visual_objects(
            runtime_visual_objects=runtime_visual_objects,
            decoration_result=decoration_result,
            place_treatment_result=place_treatment_result,
            elevation_visual_result=elevation_visual_result,
            boundary_visual_result=boundary_visual_result,
        )
        tile_size = tile_size_px or _tile_size_px(world.index, profile)
        tile_size = max(1, tile_size)
        output_dir.mkdir(parents=True, exist_ok=True)

        generated = [
            self._render_terrain_step(
                terrain_rows=terrain_rows,
                profile=profile,
                output_path=output_dir / "00_world_terrain.png",
                tile_size_px=tile_size,
            ),
            self._render_base_tile_step(
                terrain_rows=terrain_rows,
                profile=profile,
                output_path=output_dir / "01_base_visual_tiles.png",
                tile_size_px=tile_size,
            ),
            self._render_autotile_step(
                visual_layers=visual_layers,
                autotile_rows=autotile_rows,
                group_id="road",
                profile=profile,
                output_path=output_dir / "02_road_autotile.png",
                tile_size_px=tile_size,
            ),
            self._render_autotile_step(
                visual_layers=visual_layers,
                autotile_rows=autotile_rows,
                group_id="water",
                profile=profile,
                output_path=output_dir / "03_water_autotile.png",
                tile_size_px=tile_size,
            ),
            self._render_autotile_step(
                visual_layers=visual_layers,
                autotile_rows=autotile_rows,
                group_id="swamp",
                profile=profile,
                output_path=output_dir / "04_swamp_autotile.png",
                tile_size_px=tile_size,
            ),
            self._render_autotile_step(
                visual_layers=visual_layers,
                autotile_rows=autotile_rows,
                group_id="forest",
                profile=profile,
                output_path=output_dir / "05_forest_autotile.png",
                tile_size_px=tile_size,
            ),
            self._render_fallback_step(
                visual_layers=visual_layers,
                autotile_rows=autotile_rows,
                profile=profile,
                output_path=output_dir / "06_autotile_fallbacks.png",
                tile_size_px=tile_size,
            ),
            self._render_objects_step(
                visual_layers=visual_layers,
                visual_objects=runtime_visual_objects,
                profile=profile,
                output_path=output_dir / "07_objects.png",
                tile_size_px=tile_size,
            ),
            self._render_decoration_step(
                visual_layers=visual_layers,
                decoration_result=decoration_result,
                profile=profile,
                output_path=output_dir / "08_decoration.png",
                tile_size_px=tile_size,
            ),
            self._render_place_treatment_step(
                visual_layers=visual_layers,
                place_treatment_result=place_treatment_result,
                profile=profile,
                output_path=output_dir / "09_place_treatment.png",
                tile_size_px=tile_size,
            ),
            self._render_elevation_visual_step(
                visual_layers=visual_layers,
                elevation_visual_result=elevation_visual_result,
                profile=profile,
                output_path=output_dir / "10_elevation_visual.png",
                tile_size_px=tile_size,
            ),
            self._render_boundary_visual_step(
                visual_layers=visual_layers,
                boundary_visual_result=boundary_visual_result,
                profile=profile,
                output_path=output_dir / "11_boundary_visual.png",
                tile_size_px=tile_size,
            ),
            self._render_final_step(
                visual_layers=visual_layers,
                visual_objects=visual_objects,
                profile=profile,
                output_path=output_dir / "12_final_preview.png",
                tile_size_px=tile_size,
            ),
            render_forest_mass_experiment(
                result=forest_mass_experiment_result,
                world=world,
                profile=profile,
                output_path=output_dir / "13_forest_mass_experiment.png",
                tile_size_px=tile_size,
            ),
        ]
        forest_mass_overlay_path = output_dir / "14_forest_mass_overlay.png"
        forest_mass_compare_path = output_dir / "15_forest_mass_compare.png"
        forest_mass_overlay_report = render_forest_mass_overlay(
            result=forest_mass_experiment_result,
            world=world,
            profile=profile,
            visual_layers=visual_layers,
            output_path=forest_mass_overlay_path,
            compare_output_path=forest_mass_compare_path,
            tile_size_px=tile_size,
        )
        generated.extend([forest_mass_overlay_path, forest_mass_compare_path])
        forest_mass_overlay_clean_path = output_dir / "16_forest_mass_overlay_clean.png"
        forest_mass_compare_clean_path = output_dir / "17_forest_mass_compare_clean.png"
        forest_mass_overlay_clean_report = render_forest_mass_overlay_clean(
            result=forest_mass_experiment_result,
            world=world,
            profile=profile,
            visual_layers=visual_layers,
            output_path=forest_mass_overlay_clean_path,
            compare_output_path=forest_mass_compare_clean_path,
            tile_size_px=tile_size,
        )
        generated.extend([forest_mass_overlay_clean_path, forest_mass_compare_clean_path])
        forest_mass_overlay_fix_path = output_dir / "18_forest_mass_overlay_placement_fix.png"
        forest_mass_compare_fix_path = output_dir / "19_forest_mass_compare_placement_fix.png"
        forest_mass_overlay_fix_report = render_forest_mass_overlay_placement_fix(
            result=forest_mass_experiment_result,
            world=world,
            profile=profile,
            visual_layers=visual_layers,
            output_path=forest_mass_overlay_fix_path,
            compare_output_path=forest_mass_compare_fix_path,
            tile_size_px=tile_size,
        )
        generated.extend([forest_mass_overlay_fix_path, forest_mass_compare_fix_path])
        write_json_object(
            forest_mass_experiment_result.to_report(),
            output_dir.parent / "forest_mass_experiment_report.json",
        )
        write_json_object(
            forest_mass_overlay_report,
            output_dir.parent / "forest_mass_overlay_report.json",
        )
        write_json_object(
            forest_mass_overlay_clean_report,
            output_dir.parent / "forest_mass_overlay_clean_report.json",
        )
        write_json_object(
            forest_mass_overlay_fix_report,
            output_dir.parent / "forest_mass_overlay_placement_fix_report.json",
        )
        return generated

    def _render_terrain_step(
        self,
        *,
        terrain_rows: list[list[str]],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        terrain_to_tile = _terrain_to_tile(profile)
        tile_colors = _tile_colors(profile)
        rows = [
            [terrain_to_tile.get(terrain_type, "terrain.unknown") for terrain_type in row]
            for row in terrain_rows
        ]
        _render_tile_rows(
            rows=rows,
            tile_colors=tile_colors,
            output_path=output_path,
            tile_size_px=tile_size_px,
        )
        return output_path

    def _render_base_tile_step(
        self,
        *,
        terrain_rows: list[list[str]],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        terrain_to_tile = _terrain_to_tile(profile)
        default_tile = _string_value(
            profile.terrain_rules.get("default_tile"),
            "terrain.unknown",
        )
        rows = [
            [terrain_to_tile.get(terrain_type, default_tile) for terrain_type in row]
            for row in terrain_rows
        ]
        _render_tile_rows(
            rows=rows,
            tile_colors=_tile_colors(profile),
            output_path=output_path,
            tile_size_px=tile_size_px,
        )
        return output_path

    def _render_autotile_step(
        self,
        *,
        visual_layers: dict[str, Any],
        autotile_rows: list[list[dict[str, Any] | None]],
        group_id: str,
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        muted_rows = [["debug.muted" for _ in row] for row in rows]
        for y, row in enumerate(autotile_rows):
            for x, info in enumerate(row):
                if isinstance(info, dict) and info.get("group") == group_id:
                    muted_rows[y][x] = _string_value(info.get("tile_id"), "terrain.unknown")
        colors = {**_tile_colors(profile), "debug.muted": "#1b1b1b"}
        _render_tile_rows(
            rows=muted_rows,
            tile_colors=colors,
            output_path=output_path,
            tile_size_px=tile_size_px,
        )
        return output_path


    def _render_fallback_step(
        self,
        *,
        visual_layers: dict[str, Any],
        autotile_rows: list[list[dict[str, Any] | None]],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        fallback_rows = [["debug.ok" for _ in row] for row in rows]
        for y, row in enumerate(autotile_rows):
            for x, info in enumerate(row):
                if isinstance(info, dict) and info.get("fallback_used") is True:
                    fallback_rows[y][x] = "debug.fallback"
        colors = {
            **_dimmed_tile_colors(profile),
            "debug.ok": "#1b1b1b",
            "debug.fallback": "#ff00ff",
        }
        _render_tile_rows(
            rows=fallback_rows,
            tile_colors=colors,
            output_path=output_path,
            tile_size_px=tile_size_px,
        )
        return output_path

    def _render_objects_step(
        self,
        *,
        visual_layers: dict[str, Any],
        visual_objects: dict[str, Any],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        image, draw = _new_tile_image(
            width=len(rows[0]),
            height=len(rows),
            tile_size_px=tile_size_px,
            background="#1b1b1b",
        )
        _draw_tile_rows(
            draw=draw,
            rows=rows,
            tile_colors=_dimmed_tile_colors(profile),
            tile_size_px=tile_size_px,
        )
        _draw_object_anchors(
            draw=draw,
            visual_objects=visual_objects,
            sprite_colors=_sprite_colors(profile),
            tile_size_px=tile_size_px,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path


    def _render_decoration_step(
        self,
        *,
        visual_layers: dict[str, Any],
        decoration_result: dict[str, Any],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        image, draw = _new_tile_image(
            width=len(rows[0]),
            height=len(rows),
            tile_size_px=tile_size_px,
            background="#1b1b1b",
        )
        _draw_tile_rows(
            draw=draw,
            rows=rows,
            tile_colors=_dimmed_tile_colors(profile),
            tile_size_px=tile_size_px,
        )
        visual_objects = {"items": decoration_result.get("items", [])}
        _draw_object_anchors(
            draw=draw,
            visual_objects=visual_objects,
            sprite_colors=_sprite_colors(profile),
            tile_size_px=tile_size_px,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path


    def _render_place_treatment_step(
        self,
        *,
        visual_layers: dict[str, Any],
        place_treatment_result: dict[str, Any],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        image, draw = _new_tile_image(
            width=len(rows[0]),
            height=len(rows),
            tile_size_px=tile_size_px,
            background="#1b1b1b",
        )
        _draw_tile_rows(
            draw=draw,
            rows=rows,
            tile_colors=_dimmed_tile_colors(profile),
            tile_size_px=tile_size_px,
        )
        visual_objects = {"items": place_treatment_result.get("items", [])}
        _draw_object_anchors(
            draw=draw,
            visual_objects=visual_objects,
            sprite_colors=_sprite_colors(profile),
            tile_size_px=tile_size_px,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path


    def _render_elevation_visual_step(
        self,
        *,
        visual_layers: dict[str, Any],
        elevation_visual_result: dict[str, Any],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        image, draw = _new_tile_image(
            width=len(rows[0]),
            height=len(rows),
            tile_size_px=tile_size_px,
            background="#1b1b1b",
        )
        _draw_tile_rows(
            draw=draw,
            rows=rows,
            tile_colors=_dimmed_tile_colors(profile),
            tile_size_px=tile_size_px,
        )
        visual_objects = {"items": elevation_visual_result.get("items", [])}
        _draw_object_anchors(
            draw=draw,
            visual_objects=visual_objects,
            sprite_colors=_sprite_colors(profile),
            tile_size_px=tile_size_px,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path


    def _render_boundary_visual_step(
        self,
        *,
        visual_layers: dict[str, Any],
        boundary_visual_result: dict[str, Any],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        image, draw = _new_tile_image(
            width=len(rows[0]),
            height=len(rows),
            tile_size_px=tile_size_px,
            background="#1b1b1b",
        )
        _draw_tile_rows(
            draw=draw,
            rows=rows,
            tile_colors=_dimmed_tile_colors(profile),
            tile_size_px=tile_size_px,
        )
        visual_objects = {"items": boundary_visual_result.get("items", [])}
        _draw_object_anchors(
            draw=draw,
            visual_objects=visual_objects,
            sprite_colors=_sprite_colors(profile),
            tile_size_px=tile_size_px,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path

    def _render_final_step(
        self,
        *,
        visual_layers: dict[str, Any],
        visual_objects: dict[str, Any],
        profile: VisualProfile,
        output_path: Path,
        tile_size_px: int,
    ) -> Path:
        rows = _visual_rows(visual_layers)
        image, draw = _new_tile_image(
            width=len(rows[0]),
            height=len(rows),
            tile_size_px=tile_size_px,
            background="#000000",
        )
        _draw_tile_rows(
            draw=draw,
            rows=rows,
            tile_colors=_tile_colors(profile),
            tile_size_px=tile_size_px,
        )
        _draw_object_anchors(
            draw=draw,
            visual_objects=visual_objects,
            sprite_colors=_sprite_colors(profile),
            tile_size_px=tile_size_px,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Terrain layer must contain non-empty rows")
    result: list[list[str]] = []
    width: int | None = None
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or not all(isinstance(item, str) for item in row):
            raise ValueError(f"Terrain row {row_index} must be a list of strings")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("Terrain rows must have equal width")
        result.append(list(row))
    return result


def _autotile_rows(debug: Any) -> list[list[dict[str, Any] | None]]:
    if not isinstance(debug, dict):
        return []
    rows = debug.get("autotile_masks")
    if not isinstance(rows, list):
        return []
    result: list[list[dict[str, Any] | None]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        result.append([item if isinstance(item, dict) else None for item in row])
    return result


def _visual_rows(visual_layers: dict[str, Any]) -> list[list[str]]:
    layers = visual_layers.get("layers")
    if not isinstance(layers, list):
        raise ValueError("visual_layers.layers must be a list")
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "terrain_base":
            rows = layer.get("rows")
            if isinstance(rows, list) and rows:
                return [[str(item) for item in row] for row in rows if isinstance(row, list)]
    raise ValueError("Missing terrain_base visual layer")


def _terrain_to_tile(profile: VisualProfile) -> dict[str, str]:
    raw_mapping = profile.terrain_rules.get("terrain_to_tile", {})
    if not isinstance(raw_mapping, dict):
        return {}
    return {
        key: value
        for key, value in raw_mapping.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _tile_size_px(index: dict[str, Any], profile: VisualProfile) -> int:
    profile_tile_size = profile.profile.get("tile_size_px")
    if isinstance(profile_tile_size, int) and profile_tile_size > 0:
        return profile_tile_size
    dimensions = index.get("dimensions")
    if isinstance(dimensions, dict):
        tile_size = dimensions.get("tile_size_px")
        if isinstance(tile_size, int) and tile_size > 0:
            return tile_size
    return 16


def _tile_colors(profile: VisualProfile) -> dict[str, str]:
    return _colors_from_section(profile.tilesets, "tiles")



def _dimmed_tile_colors(profile: VisualProfile) -> dict[str, str]:
    result = dict(_tile_colors(profile))
    for key in result:
        result[key] = _dim_color(result[key], 0.45)
    return result


def _sprite_colors(profile: VisualProfile) -> dict[str, str]:
    return _colors_from_section(profile.tilesets, "sprites")


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


def _render_tile_rows(
    *,
    rows: Sequence[Sequence[str]],
    tile_colors: dict[str, str],
    output_path: Path,
    tile_size_px: int,
) -> None:
    image, draw = _new_tile_image(
        width=len(rows[0]) if rows else 0,
        height=len(rows),
        tile_size_px=tile_size_px,
        background="#000000",
    )
    _draw_tile_rows(
        draw=draw,
        rows=rows,
        tile_colors=tile_colors,
        tile_size_px=tile_size_px,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _new_tile_image(
    *,
    width: int,
    height: int,
    tile_size_px: int,
    background: str,
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    if width <= 0 or height <= 0:
        raise ValueError("Step render dimensions must be positive")
    image = Image.new("RGB", (width * tile_size_px, height * tile_size_px), background)
    return image, ImageDraw.Draw(image)


def _draw_tile_rows(
    *,
    draw: ImageDraw.ImageDraw,
    rows: Sequence[Sequence[str]],
    tile_colors: dict[str, str],
    tile_size_px: int,
) -> None:
    for y, row in enumerate(rows):
        for x, tile_id in enumerate(row):
            color = tile_colors.get(str(tile_id), tile_colors.get("terrain.unknown", "#ff00ff"))
            draw.rectangle(_tile_rect(x, y, tile_size_px), fill=color)


def _draw_object_anchors(
    *,
    draw: ImageDraw.ImageDraw,
    visual_objects: dict[str, Any],
    sprite_colors: dict[str, str],
    tile_size_px: int,
) -> None:
    items = visual_objects.get("items", [])
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        position = item.get("position")
        if not isinstance(position, dict):
            continue
        x = position.get("x")
        y = position.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            continue
        sprite_id = _string_value(item.get("sprite_id"), "object.generic")
        color = sprite_colors.get(sprite_id, sprite_colors.get("object.generic", "#ffffff"))
        margin = max(1, tile_size_px // 4)
        draw.ellipse(
            (
                x * tile_size_px + margin,
                y * tile_size_px + margin,
                (x + 1) * tile_size_px - margin,
                (y + 1) * tile_size_px - margin,
            ),
            fill=color,
            outline="#000000",
        )


def _tile_rect(x: int, y: int, tile_size_px: int) -> tuple[int, int, int, int]:
    return (
        x * tile_size_px,
        y * tile_size_px,
        (x + 1) * tile_size_px - 1,
        (y + 1) * tile_size_px - 1,
    )


def _dim_color(color: str, factor: float) -> str:
    if len(color) != 7 or not color.startswith("#"):
        return color
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f"#{int(red * factor):02x}{int(green * factor):02x}{int(blue * factor):02x}"


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default
