from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .chunks import build_visual_chunks
from .decoration import DecorationMapper, merge_visual_objects
from .io import write_json_object
from .models import VisualPipelineResult
from .object_mapper import ObjectVisualMapper
from .package_loader import WorldPackageLoader
from .preview_renderer import PreviewRenderer
from .profile_loader import VisualProfileLoader
from .terrain_mapper import TerrainVisualMapper


class VisualPipeline:
    """Build visual tileset output from a public world package."""

    def __init__(
        self,
        *,
        package_loader: WorldPackageLoader | None = None,
        profile_loader: VisualProfileLoader | None = None,
        terrain_mapper: TerrainVisualMapper | None = None,
        object_mapper: ObjectVisualMapper | None = None,
        preview_renderer: PreviewRenderer | None = None,
        decoration_mapper: DecorationMapper | None = None,
    ) -> None:
        """Initialize the visual pipeline.

        Args:
            package_loader: Optional world package loader.
            profile_loader: Optional visual profile loader.
            terrain_mapper: Optional terrain mapper.
            object_mapper: Optional object mapper.
            preview_renderer: Optional preview renderer.
            decoration_mapper: Optional decoration mapper.
        """
        self._package_loader = package_loader or WorldPackageLoader()
        self._profile_loader = profile_loader or VisualProfileLoader()
        self._terrain_mapper = terrain_mapper or TerrainVisualMapper()
        self._object_mapper = object_mapper or ObjectVisualMapper()
        self._preview_renderer = preview_renderer or PreviewRenderer()
        self._decoration_mapper = decoration_mapper or DecorationMapper()

    def run(
        self,
        *,
        input_dir: Path,
        profile_dir: Path,
        output_dir: Path,
        preview: bool = True,
        preview_tile_size_px: int | None = None,
        chunk_size_tiles: int = 32,
    ) -> VisualPipelineResult:
        """Run the visual pipeline.

        Args:
            input_dir: World generator output directory or map_package directory.
            profile_dir: Visual profile directory.
            output_dir: Directory where visual_map files should be written.
            preview: Whether to render preview.png.
            preview_tile_size_px: Optional preview tile size override.
            chunk_size_tiles: Visual chunk size in tiles.

        Returns:
            Paths produced by the visual pipeline.
        """
        world = self._package_loader.load(input_dir)
        profile = self._profile_loader.load(profile_dir)
        visual_layers = self._terrain_mapper.map_terrain(world, profile)
        visual_debug = self._extract_visual_debug(visual_layers)
        runtime_visual_objects = self._object_mapper.map_objects(world, profile)
        decoration_result = self._decoration_mapper.map_decorations(
            world=world,
            profile=profile,
            visual_layers=visual_layers,
            visual_debug=visual_debug,
        )
        visual_objects = merge_visual_objects(
            runtime_visual_objects=runtime_visual_objects,
            decoration_result=decoration_result,
        )
        width = _int_value(visual_layers.get("width"), 0)
        height = _int_value(visual_layers.get("height"), 0)
        visual_chunks = build_visual_chunks(
            width=width,
            height=height,
            visual_objects=visual_objects,
            chunk_size_tiles=chunk_size_tiles,
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        visual_layers_path = output_dir / "visual_layers.json"
        visual_objects_path = output_dir / "visual_objects.json"
        visual_chunks_path = output_dir / "visual_chunks.json"
        preview_path = output_dir / "preview.png" if preview else None
        visual_map_path = output_dir / "visual_map.json"
        debug_dir = output_dir / "debug"
        debug_autotile_masks_path = debug_dir / "autotile_masks.json"
        debug_autotile_report_path = debug_dir / "autotile_report.json"
        debug_unmapped_terrain_report_path = debug_dir / "unmapped_terrain_report.json"
        debug_decoration_report_path = debug_dir / "decoration_report.json"

        write_json_object(visual_layers, visual_layers_path)
        write_json_object(visual_objects, visual_objects_path)
        write_json_object(visual_chunks, visual_chunks_path)
        write_json_object(_build_autotile_masks_debug(visual_debug), debug_autotile_masks_path)
        write_json_object(_build_autotile_report_debug(visual_debug), debug_autotile_report_path)
        write_json_object(
            _build_unmapped_terrain_report_debug(visual_debug),
            debug_unmapped_terrain_report_path,
        )
        write_json_object(
            _build_decoration_report_debug(decoration_result),
            debug_decoration_report_path,
        )
        if preview_path is not None:
            self._preview_renderer.render(
                visual_layers=visual_layers,
                visual_objects=visual_objects,
                tilesets=profile.tilesets,
                output_path=preview_path,
                tile_size_px=preview_tile_size_px,
            )

        visual_map = self._build_visual_map(
            world=world.index,
            profile=profile.profile,
            profile_dir=profile.root_dir,
            output_dir=output_dir,
            visual_layers_path=visual_layers_path,
            visual_objects_path=visual_objects_path,
            visual_chunks_path=visual_chunks_path,
            preview_path=preview_path,
            debug_autotile_masks_path=debug_autotile_masks_path,
            debug_autotile_report_path=debug_autotile_report_path,
            debug_unmapped_terrain_report_path=debug_unmapped_terrain_report_path,
            debug_decoration_report_path=debug_decoration_report_path,
            visual_layers=visual_layers,
            visual_objects=visual_objects,
            visual_chunks=visual_chunks,
        )
        write_json_object(visual_map, visual_map_path)

        return VisualPipelineResult(
            output_dir=output_dir,
            visual_map_path=visual_map_path,
            visual_layers_path=visual_layers_path,
            visual_objects_path=visual_objects_path,
            visual_chunks_path=visual_chunks_path,
            preview_path=preview_path,
            debug_autotile_masks_path=debug_autotile_masks_path,
            debug_autotile_report_path=debug_autotile_report_path,
            debug_unmapped_terrain_report_path=debug_unmapped_terrain_report_path,
            debug_decoration_report_path=debug_decoration_report_path,
        )

    def _build_visual_map(
        self,
        *,
        world: dict[str, Any],
        profile: dict[str, Any],
        profile_dir: Path,
        output_dir: Path,
        visual_layers_path: Path,
        visual_objects_path: Path,
        visual_chunks_path: Path,
        preview_path: Path | None,
        debug_autotile_masks_path: Path,
        debug_autotile_report_path: Path,
        debug_unmapped_terrain_report_path: Path,
        debug_decoration_report_path: Path,
        visual_layers: dict[str, Any],
        visual_objects: dict[str, Any],
        visual_chunks: dict[str, Any],
    ) -> dict[str, Any]:
        dimensions = world.get("dimensions", {})
        if not isinstance(dimensions, dict):
            dimensions = {}
        return {
            "schema_version": "visual-map-v1",
            "kind": "visual_map",
            "visual_generator_version": __version__,
            "source": {
                "map_package_schema_version": world.get("package_schema_version"),
                "map_package_map_schema_version": world.get("schema_version"),
                "world_generator_version": world.get("generator_version"),
                "resolved_seed": world.get("resolved_seed"),
                "world_profile": world.get("profile"),
            },
            "visual_profile": {
                "id": profile.get("id", "default"),
                "name": profile.get("name", "Default"),
                "path": str(profile_dir),
            },
            "dimensions": {
                "width_tiles": _int_value(
                    visual_layers.get("width"),
                    dimensions.get("width_tiles", 0),
                ),
                "height_tiles": _int_value(
                    visual_layers.get("height"),
                    dimensions.get("height_tiles", 0),
                ),
                "tile_size_px": _int_value(
                    visual_layers.get("tile_size_px"),
                    dimensions.get("tile_size_px", 16),
                ),
            },
            "files": {
                "visual_layers": _relative(output_dir, visual_layers_path),
                "visual_objects": _relative(output_dir, visual_objects_path),
                "visual_chunks": _relative(output_dir, visual_chunks_path),
                "preview": _relative(output_dir, preview_path),
                "debug_dir": "debug",
                "debug_autotile_masks": _relative(
                    output_dir,
                    debug_autotile_masks_path,
                ),
                "debug_autotile_report": _relative(
                    output_dir,
                    debug_autotile_report_path,
                ),
                "debug_unmapped_terrain_report": _relative(
                    output_dir,
                    debug_unmapped_terrain_report_path,
                ),
                "debug_decoration_report": _relative(
                    output_dir,
                    debug_decoration_report_path,
                ),
            },
            "contract": {
                "changes_gameplay": False,
                "moves_markers": False,
                "changes_collision": False,
                "source_of_truth": "map_package",
            },
            "summary": {
                "layer_count": len(visual_layers.get("layers", [])),
                "visual_object_count": len(visual_objects.get("items", [])),
                "visual_chunk_count": len(visual_chunks.get("items", [])),
            },
        }

    @staticmethod
    def _extract_visual_debug(visual_layers: dict[str, Any]) -> dict[str, Any]:
        debug = visual_layers.pop("debug", {})
        return debug if isinstance(debug, dict) else {}


def _relative(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _int_value(value: Any, default: Any) -> int:
    if isinstance(value, int):
        return value
    return default if isinstance(default, int) else 0


def _build_autotile_masks_debug(visual_debug: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "visual-debug-autotile-masks-v2",
        "kind": "visual_debug_autotile_masks",
        "source_layer": "terrain_base",
        "coordinate_space": "tile",
        "autotile_masks": visual_debug.get("autotile_masks", []),
    }


def _build_autotile_report_debug(visual_debug: dict[str, Any]) -> dict[str, Any]:
    summary = visual_debug.get("autotile_summary", {})
    if not isinstance(summary, dict):
        summary = {}
    fallback_total = 0
    fallbacks = summary.get("fallbacks", {})
    if isinstance(fallbacks, dict):
        fallback_total = sum(value for value in fallbacks.values() if isinstance(value, int))
    return {
        "schema_version": "visual-debug-autotile-report-v1",
        "kind": "visual_debug_autotile_report",
        "source_layer": "terrain_base",
        "summary": summary,
        "quality": {
            "fallback_total": fallback_total,
            "status": "ok" if fallback_total == 0 else "has_fallbacks",
        },
    }


def _build_unmapped_terrain_report_debug(visual_debug: dict[str, Any]) -> dict[str, Any]:
    unmapped = visual_debug.get("unmapped_terrain", {})
    if not isinstance(unmapped, dict):
        unmapped = {}
    total_cells = _int_value(unmapped.get("total_cells"), 0)
    return {
        "schema_version": "visual-debug-unmapped-terrain-report-v1",
        "kind": "visual_debug_unmapped_terrain_report",
        "source_layer": "terrain_base",
        "summary": unmapped,
        "quality": {
            "unmapped_total": total_cells,
            "status": "ok" if total_cells == 0 else "has_unmapped_terrain",
        },
    }


def _build_decoration_report_debug(decoration_result: dict[str, Any]) -> dict[str, Any]:
    report = decoration_result.get("report")
    if isinstance(report, dict):
        return report
    return {
        "schema_version": "visual-debug-decoration-report-v1",
        "kind": "visual_debug_decoration_report",
        "source_layer": "terrain_base",
        "rules_enabled": False,
        "summary": {
            "total": 0,
            "by_rule": {},
            "by_sprite_id": {},
            "skipped": {},
        },
        "quality": {"status": "missing_report"},
    }
