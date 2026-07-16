from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from .config import PublicConfig
from .export.map_package import write_map_package
from .legacy_runner import LegacyEngineRunner
from .logging_utils import timed_stage
from .manifest import (
    ASCII_MAP_SCHEMA_VERSION,
    COLLISION_LAYER_SCHEMA_VERSION,
    ELEVATION_LAYER_SCHEMA_VERSION,
    ELEVATION_MODEL_SCHEMA_VERSION,
    ELEVATION_FEATURES_SCHEMA_VERSION,
    ELEVATION_TRANSITIONS_SCHEMA_VERSION,
    ELEVATION_DENSITY_REPORT_SCHEMA_VERSION,
    ENGINE_CONFIG_SCHEMA_VERSION,
    GAMEPLAY_LAYER_SCHEMA_VERSION,
    GAMEPLAY_ZONES_SCHEMA_VERSION,
    MAP_PACKAGE_MAP_SCHEMA_VERSION,
    MARKERS_SCHEMA_VERSION,
    METRICS_SCHEMA_VERSION,
    MOVEMENT_LAYER_SCHEMA_VERSION,
    OBJECT_INSTANCES_SCHEMA_VERSION,
    OBJECT_CATALOG_SCHEMA_VERSION,
    OBJECT_TYPES_CATALOG_SCHEMA_VERSION,
    OBJECT_RENDER_HINTS_SCHEMA_VERSION,
    RENDER_PROFILE_SCHEMA_VERSION,
    RUNTIME_GRIDS_SCHEMA_VERSION,
    WORLD_GRAPH_SCHEMA_VERSION,
    ROUTES_SCHEMA_VERSION,
    PLACES_SCHEMA_VERSION,
    WORLD_DENSITY_REPORT_SCHEMA_VERSION,
    WORLD_SUMMARY_REPORT_SCHEMA_VERSION,
    TERRAIN_ISLAND_REPORT_SCHEMA_VERSION,
    GEOGRAPHY_GUIDANCE_SCHEMA_VERSION,
    TERRAIN_GUIDANCE_REPORT_SCHEMA_VERSION,
    PNG_LAYER_SCHEMA_VERSION,
    RAW_TACTICAL_MAP_SCHEMA_VERSION,
    TILE_RENDER_HINTS_SCHEMA_VERSION,
    TACTICAL_DEBUG_SCHEMA_VERSION,
    TACTICAL_MAP_SCHEMA_VERSION,
    START_GOAL_LAYER_SCHEMA_VERSION,
    TERRAIN_LAYER_SCHEMA_VERSION,
    TILE_GRID_LAYER_SCHEMA_VERSION,
    TILE_TYPES_CATALOG_SCHEMA_VERSION,
    VALIDATION_REPORT_SCHEMA_VERSION,
    VEGETATION_VISUAL_SCHEMA_VERSION,
    OutputArtifact,
    build_manifest,
    write_manifest,
)
from .object_catalog import write_object_catalog
from .paths import OutputPaths
from .render.layers import LayerRenderer
from .reports import build_world_reports, format_console_summary
from .tactical.elevation import (
    attach_next_gen_elevation,
    build_geography_draft,
    build_natural_geography_model,
)
from .tactical.fallback import FallbackPositionBuilder
from .tactical.geography_guidance import write_geography_guidance
from .tactical.grid import attach_tile_grid
from .tactical.places import attach_places
from .tactical.runtime_objects import attach_runtime_layers, summarize_runtime_objects
from .tactical.terrain_islands import elevation_cell_points, repair_terrain_islands
from .tactical.hydrology import apply_elevation_hydrology
from .tactical.start_goal import (
    cleanup_unreachable_walkable,
    finalize_runtime_objects_for_final_terrain,
    relocate_start_goal,
    runtime_object_points,
)
from .tactical.vegetation_visual import (
    build_visual_vegetation,
    reconcile_tree_collision,
)
from .tactical.objectives import ObjectiveProfileSelector
from .tactical.optimizer import TacticalOptimizer
from .utils.json_io import read_json, write_json
from .validation import (
    build_validation_report,
    validation_summary_from_report,
    write_validation_report,
)


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Pipeline result summary."""

    metrics: dict[str, Any]
    outputs: OutputPaths
    summary: dict[str, Any]
    console_summary: str


class WorldgenPipeline:
    """Single-pass modular world generation pipeline."""

    def __init__(self, project_root: Path) -> None:
        """Initialize pipeline.

        Args:
            project_root: Project root directory.
        """
        self._project_root = project_root

    def run(
        self,
        config_path: Path,
        output_map: Path,
        tile_size_px: int,
        render: bool,
        debug_images: bool,
        log_file: Path | None,
    ) -> PipelineResult:
        """Run the complete generation pipeline.

        Args:
            config_path: Public config path.
            output_map: ASCII map output path.
            tile_size_px: Render tile size.
            render: Whether to render PNG layers.
            debug_images: Whether to render PNG debug overlays.
            log_file: Optional legacy engine log path.

        Returns:
            PipelineResult.
        """
        started = perf_counter()
        LOGGER.info(
            "Pipeline requested config=%s output_map=%s tile_size_px=%s render=%s debug_images=%s",
            config_path,
            output_map,
            tile_size_px,
            render,
            debug_images,
        )

        with timed_stage(
            LOGGER,
            "pipeline.load_config",
            config_path=config_path,
        ) as metrics:
            config = PublicConfig.from_file(config_path)
            metrics.update(
                {
                    "seed": config.seed,
                    "resolved_seed": config.resolved_seed,
                    "map_width_tiles": config.map_width_tiles,
                    "map_height_tiles": config.map_height_tiles,
                    "chunk_width_tiles": config.chunk_width_tiles,
                    "chunk_height_tiles": config.chunk_height_tiles,
                    "biome_profile": config.biome_profile,
                    "objective_profile": config.objective_profile,
                    "elevation_style": config.elevation_style,
                    "generation_tuning": config.generation_tuning.to_dict(),
                },
            )

        with timed_stage(
            LOGGER,
            "pipeline.prepare_outputs",
            output_target=output_map,
        ) as metrics:
            outputs = OutputPaths.from_cli_output(output_map)
            outputs.output_dir.mkdir(parents=True, exist_ok=True)
            config.write_engine_config(outputs.engine_config)
            metrics.update(
                {
                    "output_dir": outputs.output_dir,
                    "generated_map": outputs.generated_map,
                    "engine_config": outputs.engine_config,
                },
            )

        with timed_stage(LOGGER, "pipeline.build_geography_draft") as metrics:
            geography_draft = build_geography_draft(
                width=config.map_width_tiles,
                height=config.map_height_tiles,
                seed=config.resolved_seed,
                elevation_style=config.elevation_style,
            )
            natural_geography = build_natural_geography_model(
                width=config.map_width_tiles,
                height=config.map_height_tiles,
                seed=config.resolved_seed,
                elevation_style=config.elevation_style,
                geography_draft=geography_draft,
            )
            write_geography_guidance(natural_geography, outputs.geography_guidance)
            natural_levels = [
                level
                for row in natural_geography.elevation_rows
                for level in row
            ]
            metrics.update(
                {
                    "macro_regions": len(geography_draft.macro_regions),
                    "region_edges": len(geography_draft.region_edges),
                    "elevation_style": geography_draft.elevation_style,
                    "natural_min_level": min(natural_levels, default=0),
                    "natural_max_level": max(natural_levels, default=0),
                    "guidance_path": outputs.geography_guidance,
                },
            )

        engine_started = perf_counter()
        with timed_stage(LOGGER, "pipeline.legacy_engine") as metrics:
            engine_path = self._project_root / "top_down_worldgen" / "legacy" / "engine.py"
            LegacyEngineRunner(engine_path).run(
                config_path=outputs.engine_config,
                map_out=outputs.generated_map,
                tactical_out=outputs.raw_tactical_map,
                geography_guidance=outputs.geography_guidance,
                log_file=log_file or outputs.log_file,
            )
            rows = outputs.generated_map.read_text(encoding="utf-8").splitlines()
            metrics.update(
                {
                    "map_rows": len(rows),
                    "map_cols": len(rows[0]) if rows else 0,
                    "raw_tactical_map": outputs.raw_tactical_map,
                },
            )
        engine_time_ms = (perf_counter() - engine_started) * 1000.0

        tactical_started = perf_counter()
        with timed_stage(LOGGER, "pipeline.tactical_processing") as metrics:
            raw_data = read_json(outputs.raw_tactical_map)
            raw_data["schema_version"] = RAW_TACTICAL_MAP_SCHEMA_VERSION
            raw_data["generator_version"] = self._project_version()
            raw_data["pipeline_version"] = "pipeline-v1"
            terrain_guidance_report = raw_data.get("terrain_guidance", {})
            if isinstance(terrain_guidance_report, dict):
                write_json(terrain_guidance_report, outputs.terrain_guidance_report)
            write_json(raw_data, outputs.raw_tactical_map)
            LOGGER.info(
                "Raw tactical counts combat_zones=%s cover_points=%s choke_points=%s "
                "flank_routes=%s enemy_spawn_zones=%s",
                len(raw_data.get("combat_zones", [])),
                len(raw_data.get("cover_points", [])),
                len(raw_data.get("choke_points", [])),
                len(raw_data.get("flank_routes", [])),
                len(raw_data.get("enemy_spawn_zones", [])),
            )
            runtime_data, debug_data = TacticalOptimizer().optimize(raw_data)
            runtime_data, debug_data = FallbackPositionBuilder().add(
                runtime_data,
                debug_data,
            )
            runtime_data, debug_data = ObjectiveProfileSelector(
                config.objective_profile,
            ).apply(
                runtime_data,
                debug_data,
            )
            runtime_data = attach_tile_grid(runtime_data, rows)
            runtime_data = attach_runtime_layers(
                runtime_data,
                seed=config.resolved_seed,
                generation_tuning=config.generation_tuning.to_dict(),
            )
            with timed_stage(
                LOGGER,
                "pipeline.terrain_island_repair",
                report_path=outputs.terrain_island_report,
            ) as island_metrics:
                structural_points = elevation_cell_points(
                    runtime_data,
                    width=len(rows[0]) if rows else 0,
                    height=len(rows),
                )
                terrain_island_repair = repair_terrain_islands(
                    rows,
                    blocked_points=structural_points,
                )
                rows = terrain_island_repair.rows
                outputs.generated_map.write_text("\n".join(rows) + "\n", encoding="utf-8")
                write_json(terrain_island_repair.report, outputs.terrain_island_report)
                repair_summary = terrain_island_repair.report.get("summary", {})
                island_metrics.update(
                    {
                        "small_islands_removed": repair_summary.get("small_islands_removed"),
                        "small_island_tiles_removed": repair_summary.get("small_island_tiles_removed"),
                        "large_islands_preserved": repair_summary.get("large_islands_preserved"),
                        "components_before": repair_summary.get("components_before"),
                        "components_after": repair_summary.get("components_after"),
                        "structural_points": len(structural_points),
                    },
                )
            runtime_data = attach_tile_grid(runtime_data, rows)
            runtime_data["terrain_island_repair"] = terrain_island_repair.report
            debug_data["terrain_island_repair"] = terrain_island_repair.report
            runtime_data = attach_places(runtime_data)
            runtime_data = attach_next_gen_elevation(
                runtime_data,
                rows=rows,
                seed=config.resolved_seed,
                elevation_style=config.elevation_style,
                geography_draft=geography_draft,
                natural_geography=natural_geography,
            )
            geography_grids = runtime_data.get("elevation_generation_report", {}).get("geography", {}).get("grids", {})
            elevation_rows = geography_grids.get("geographic_level_grid", {}).get("rows", [])
            hydrology = apply_elevation_hydrology(rows=rows, elevation_rows=elevation_rows)
            rows = hydrology.rows
            runtime_data = attach_tile_grid(runtime_data, rows)
            map_info = dict(runtime_data.get("map", {}))
            tile_legend = dict(map_info.get("tile_legend", {}))
            tile_legend["~"] = "deep_water_blocker"
            map_info["tile_legend"] = tile_legend
            runtime_data["map"] = map_info
            movement_costs = dict(runtime_data.get("movement_costs", {}))
            movement_costs.pop("~", None)
            runtime_data["movement_costs"] = movement_costs
            runtime_data["elevation_hydrology"] = hydrology.report
            debug_data["elevation_hydrology"] = hydrology.report
            terrain_rows = [
                [tile_legend.get(tile, "unknown") for tile in row]
                for row in rows
            ]
            vegetation_visual = build_visual_vegetation(
                terrain_rows=terrain_rows,
                elevation_rows=elevation_rows,
                slope_rows=geography_grids.get("slope_grid", {}).get("rows", []),
                seed=config.resolved_seed,
                reed_density=config.reed_density,
            )
            vegetation_collision = reconcile_tree_collision(
                rows=rows,
                visual_rows=vegetation_visual.rows,
                elevation_rows=elevation_rows,
            )
            rows = vegetation_collision.rows
            vegetation_visual.report["rows"] = vegetation_collision.visual_rows
            runtime_data = attach_tile_grid(runtime_data, rows)
            runtime_data["vegetation_visual"] = vegetation_visual.report
            runtime_data["vegetation_collision_reconciliation"] = vegetation_collision.report
            debug_data["vegetation_collision_reconciliation"] = vegetation_collision.report

            retained_objects, object_pruning = finalize_runtime_objects_for_final_terrain(
                runtime_data.get("runtime_objects"),
                rows=rows,
            )
            runtime_data["runtime_objects"] = retained_objects
            runtime_data["runtime_objects_summary"] = summarize_runtime_objects(retained_objects)
            runtime_data["final_runtime_object_pruning"] = object_pruning
            debug_data["final_runtime_object_pruning"] = object_pruning
            late_start_goal = relocate_start_goal(
                rows=rows,
                elevation_rows=elevation_rows,
                seed=config.resolved_seed,
                excluded_points=runtime_object_points(runtime_data.get("runtime_objects")),
            )
            rows = late_start_goal.rows
            final_traversal_cleanup = cleanup_unreachable_walkable(
                rows=rows,
                elevation_rows=elevation_rows,
                source_rows=geography_grids.get("source_grid", {}).get("rows", []),
            )
            rows = final_traversal_cleanup.rows
            runtime_data = attach_tile_grid(runtime_data, rows)
            runtime_data["late_start_goal"] = late_start_goal.report
            runtime_data["final_3d_traversal_cleanup"] = final_traversal_cleanup.report
            debug_data["late_start_goal"] = late_start_goal.report
            debug_data["final_3d_traversal_cleanup"] = final_traversal_cleanup.report
            outputs.generated_map.write_text("\n".join(rows) + "\n", encoding="utf-8")
            runtime_data["version"] = "0.31-runtime"
            debug_data["version"] = "0.20-debug"

            write_json(runtime_data, outputs.tactical_map)
            write_json(debug_data, outputs.tactical_map_debug)
            write_map_package(
                outputs=outputs,
                runtime_data=runtime_data,
                rows=rows,
                width=config.map_width_tiles,
                height=config.map_height_tiles,
                tile_size_px=tile_size_px,
                seed=config.seed,
                resolved_seed=config.resolved_seed,
                profile=config.objective_profile,
                generation_tuning=config.generation_tuning.to_dict(),
            )
            metrics.update(
                {
                    "runtime_combat_zones": len(runtime_data.get("combat_zones", [])),
                    "runtime_cover_points": len(runtime_data.get("cover_points", [])),
                    "runtime_choke_points": len(runtime_data.get("choke_points", [])),
                    "runtime_flank_routes": len(runtime_data.get("flank_routes", [])),
                    "runtime_enemy_spawn_zones": len(
                        runtime_data.get("enemy_spawn_zones", []),
                    ),
                    "runtime_fallback_positions": len(
                        runtime_data.get("fallback_positions", []),
                    ),
                    "runtime_objects": len(runtime_data.get("runtime_objects", [])),
                    "runtime_object_types": len(runtime_data.get("runtime_objects_summary", {}).get("by_type", {})),
                    "places": len(runtime_data.get("places", [])),
                    "place_types": len(runtime_data.get("places_summary", {}).get("by_type", {})),
                    "elevation_cells": len(
                        runtime_data.get("elevation", {}).get("cells", []),
                    ),
                    "elevation_generator": runtime_data.get("elevation", {}).get("generator", {}).get("name"),
                },
            )
        tactical_time_ms = (perf_counter() - tactical_started) * 1000.0

        render_time_ms = 0.0
        rendered_layers: list[str] = []
        if render:
            render_started = perf_counter()
            with timed_stage(
                LOGGER,
                "pipeline.render_layers",
                tile_size_px=tile_size_px,
            ) as metrics:
                render_outputs = {
                    "base": outputs.layer_base_map,
                    "combat": outputs.layer_combat_zones,
                    "cover": outputs.layer_cover_points,
                    "choke": outputs.layer_choke_points,
                    "flank": outputs.layer_flank_routes,
                    "spawn": outputs.layer_enemy_spawn_zones,
                    "fallback": outputs.layer_fallback_positions,
                    "runtime_objects": outputs.layer_runtime_objects,
                    "all": outputs.layer_all_debug,
                }
                renderer = LayerRenderer(self._project_root / "assets", tile_size_px)
                rendered_layers = renderer.render_all(
                    outputs.generated_map,
                    outputs.tactical_map_debug,
                    outputs.tactical_map,
                    render_outputs,
                    include_debug_images=debug_images,
                )
                metrics.update(
                    {
                        "rendered_layers": len(rendered_layers),
                        "output_dir": outputs.output_dir,
                    },
                )
            render_time_ms = (perf_counter() - render_started) * 1000.0
        else:
            LOGGER.info("Render skipped by CLI flag")

        total_time_ms = (perf_counter() - started) * 1000.0
        rows = outputs.generated_map.read_text(encoding="utf-8").splitlines()
        width = len(rows[0]) if rows else 0
        height = len(rows)
        objective = runtime_data.get("objective", {})
        optimization = runtime_data.get("optimization", {})
        connectivity_repair = runtime_data.get("connectivity_repair", {})

        metrics = {
            "version": "clean_refactor",
            "map_width_tiles": width,
            "map_height_tiles": height,
            "resolved_seed": config.resolved_seed,
            "tile_size_px": tile_size_px,
            "engine_time_ms": round(engine_time_ms, 2),
            "tactical_time_ms": round(tactical_time_ms, 2),
            "render_time_ms": round(render_time_ms, 2),
            "total_time_ms": round(total_time_ms, 2),
            "render_enabled": render,
            "debug_images_enabled": debug_images and render,
            "rendered_layers": rendered_layers,
            "objective_profile": config.objective_profile,
            "elevation_style": config.elevation_style,
            "generation_tuning": config.generation_tuning.to_dict(),
            "spawn_selection_policy": objective.get("spawn_selection_policy"),
            "candidate_spawn_count": objective.get("candidate_spawn_count"),
            "selected_spawn_count": objective.get("selected_spawn_count"),
            "combat_zones": len(runtime_data.get("combat_zones", [])),
            "cover_points": len(runtime_data.get("cover_points", [])),
            "choke_points": len(runtime_data.get("choke_points", [])),
            "flank_routes": len(runtime_data.get("flank_routes", [])),
            "enemy_spawn_zones": len(runtime_data.get("enemy_spawn_zones", [])),
            "fallback_positions": len(runtime_data.get("fallback_positions", [])),
            "runtime_objects": len(runtime_data.get("runtime_objects", [])),
            "runtime_object_types": len(runtime_data.get("runtime_objects_summary", {}).get("by_type", {})),
            "runtime_objects_summary": runtime_data.get("runtime_objects_summary", {}),
            "places": len(runtime_data.get("places", [])),
            "places_summary": runtime_data.get("places_summary", {}),
            "elevation_cells": len(runtime_data.get("elevation", {}).get("cells", [])),
            "original_cover_points": optimization.get("original_cover_points"),
            "selected_cover_points": optimization.get("selected_cover_points"),
            "connectivity_components_before": connectivity_repair.get("components_before"),
            "connectivity_components_after": connectivity_repair.get("components_after"),
            "connectivity_filled_components": connectivity_repair.get("filled_components"),
            "connectivity_connected_components": connectivity_repair.get("connected_components"),
            "connectivity_tiles_changed": connectivity_repair.get("tiles_changed"),
            "terrain_small_islands_removed": runtime_data.get("terrain_island_repair", {})
            .get("summary", {})
            .get("small_islands_removed"),
            "terrain_small_island_tiles_removed": runtime_data.get("terrain_island_repair", {})
            .get("summary", {})
            .get("small_island_tiles_removed"),
            "terrain_large_islands_preserved": runtime_data.get("terrain_island_repair", {})
            .get("summary", {})
            .get("large_islands_preserved"),
        }
        with timed_stage(
            LOGGER,
            "pipeline.write_metrics",
            metrics_path=outputs.metrics,
        ) as log_metrics:
            outputs.metrics.write_text(self._format_metrics(metrics), encoding="utf-8")
            log_metrics.update({"metrics_count": len(metrics)})

        with timed_stage(
            LOGGER,
            "pipeline.write_object_catalog",
            object_catalog_path=outputs.object_catalog,
        ) as log_metrics:
            write_object_catalog(
                path=outputs.object_catalog,
                rows=rows,
                runtime_data=runtime_data,
            )
            log_metrics.update(
                {
                    "runtime_object_types": len(
                        runtime_data.get("runtime_objects_summary", {}).get("by_type", {}),
                    ),
                    "place_types": len(
                        runtime_data.get("places_summary", {}).get("by_type", {}),
                    ),
                    "size_bytes": outputs.object_catalog.stat().st_size,
                },
            )

        validation_report = build_validation_report(
            outputs=outputs,
            rows=rows,
            width=width,
            height=height,
            runtime_data=runtime_data,
            resolved_seed=config.resolved_seed,
        )
        with timed_stage(
            LOGGER,
            "pipeline.write_validation_report",
            validation_report_path=outputs.validation_report,
        ) as log_metrics:
            write_validation_report(validation_report, outputs.validation_report)
            log_metrics.update(
                {
                    "status": validation_report.get("status"),
                    "checks": len(validation_report.get("checks", {})),
                    "errors": len(validation_report.get("errors", [])),
                    "warnings": len(validation_report.get("warnings", [])),
                },
            )

        world_density_report, elevation_density_report, world_summary_report = build_world_reports(
            outputs=outputs,
            rows=rows,
            runtime_data=runtime_data,
            resolved_seed=config.resolved_seed,
            render_enabled=render,
            rendered_layers=rendered_layers,
            validation_report=validation_report,
        )
        with timed_stage(
            LOGGER,
            "pipeline.write_world_reports",
            world_density_report=outputs.world_density_report,
            elevation_density_report=outputs.elevation_density_report,
            world_summary_report=outputs.world_summary_report,
        ) as log_metrics:
            write_json(world_density_report, outputs.world_density_report)
            write_json(elevation_density_report, outputs.elevation_density_report)
            write_json(world_summary_report, outputs.world_summary_report)
            log_metrics.update(
                {
                    "status": world_summary_report.get("status"),
                    "world_density_sections": len(world_density_report),
                    "elevation_bands": len(elevation_density_report.get("bands", {})),
                },
            )

        artifacts = self._build_artifacts(
            outputs,
            render=render,
            rendered_layers=rendered_layers,
        )
        manifest = build_manifest(
            output_dir=outputs.output_dir,
            seed=config.seed,
            resolved_seed=config.resolved_seed,
            profile=config.objective_profile,
            width=width,
            height=height,
            tile_size_px=tile_size_px,
            total_time_ms=total_time_ms,
            engine_time_ms=engine_time_ms,
            tactical_time_ms=tactical_time_ms,
            render_time_ms=render_time_ms,
            render_enabled=render,
            debug_images_enabled=debug_images and render,
            available_debug_layers=list(LayerRenderer.AVAILABLE_DEBUG_LAYERS),
            generated_debug_layers=[layer for layer in rendered_layers if layer != "base"],
            layers=rendered_layers,
            artifacts=artifacts,
            validation_summary=validation_summary_from_report(validation_report),
            metrics=metrics,
            generation_tuning=config.generation_tuning.to_dict(),
            validation_report_path=outputs.validation_report,
        )
        with timed_stage(
            LOGGER,
            "pipeline.write_manifest",
            manifest_path=outputs.manifest,
        ) as log_metrics:
            write_manifest(manifest, outputs.manifest)
            log_metrics.update(
                {
                    "files": len(manifest.get("files", [])),
                    "primary_outputs": len(manifest.get("primary_outputs", [])),
                    "debug_outputs": len(manifest.get("debug_outputs", [])),
                },
            )

        console_summary = format_console_summary(world_summary_report)
        LOGGER.info("Pipeline completed total_time_ms=%.2f", total_time_ms)
        return PipelineResult(
            metrics=metrics,
            outputs=outputs,
            summary=world_summary_report,
            console_summary=console_summary,
        )

    @staticmethod
    def _build_artifacts(
        outputs: OutputPaths,
        *,
        render: bool,
        rendered_layers: list[str],
    ) -> list[OutputArtifact]:
        artifacts = [
            OutputArtifact(
                outputs.generated_map,
                "ascii_map",
                True,
                False,
                ASCII_MAP_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.tactical_map,
                "tactical_map",
                True,
                False,
                TACTICAL_MAP_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.metrics,
                "metrics",
                True,
                False,
                METRICS_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.raw_tactical_map,
                "raw_tactical_map",
                False,
                True,
                RAW_TACTICAL_MAP_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.tactical_map_debug,
                "tactical_debug",
                False,
                True,
                TACTICAL_DEBUG_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.validation_report,
                "validation_report",
                True,
                False,
                VALIDATION_REPORT_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.world_density_report,
                "world_density_report",
                True,
                False,
                WORLD_DENSITY_REPORT_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.elevation_density_report,
                "elevation_density_report",
                True,
                False,
                ELEVATION_DENSITY_REPORT_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.world_summary_report,
                "world_summary_report",
                True,
                False,
                WORLD_SUMMARY_REPORT_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.terrain_island_report,
                "terrain_island_report",
                False,
                True,
                TERRAIN_ISLAND_REPORT_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.geography_guidance,
                "geography_guidance",
                False,
                True,
                GEOGRAPHY_GUIDANCE_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.terrain_guidance_report,
                "terrain_guidance_report",
                False,
                True,
                TERRAIN_GUIDANCE_REPORT_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.object_catalog,
                "object_catalog",
                False,
                False,
                OBJECT_CATALOG_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.engine_config,
                "engine_config",
                False,
                True,
                ENGINE_CONFIG_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.log_file,
                "generation_log",
                False,
                True,
                METRICS_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_map,
                "map_package:index",
                True,
                False,
                MAP_PACKAGE_MAP_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_markers,
                "map_package:markers",
                True,
                False,
                MARKERS_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_runtime_grids,
                "map_package:runtime_grids",
                True,
                False,
                RUNTIME_GRIDS_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_world_graph,
                "map_package:world_graph",
                True,
                False,
                WORLD_GRAPH_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_routes,
                "map_package:routes",
                True,
                False,
                ROUTES_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_gameplay_zones,
                "map_package:gameplay_zones",
                True,
                False,
                GAMEPLAY_ZONES_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_elevation_model,
                "map_package:elevation_model",
                True,
                False,
                ELEVATION_MODEL_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_elevation_features,
                "map_package:elevation_features",
                True,
                False,
                ELEVATION_FEATURES_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_elevation_transitions,
                "map_package:elevation_transitions",
                True,
                False,
                ELEVATION_TRANSITIONS_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_tile_grid,
                "map_package:tile_grid",
                True,
                False,
                TILE_GRID_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_terrain,
                "map_package:terrain",
                True,
                False,
                TERRAIN_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_movement_costs,
                "map_package:movement_costs",
                True,
                False,
                MOVEMENT_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_collision,
                "map_package:collision",
                True,
                False,
                COLLISION_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_elevation,
                "map_package:elevation",
                True,
                False,
                ELEVATION_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_start_goal,
                "map_package:start_goal",
                True,
                False,
                START_GOAL_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_combat_zones,
                "map_package:combat_zones",
                True,
                False,
                GAMEPLAY_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_cover_points,
                "map_package:cover_points",
                True,
                False,
                GAMEPLAY_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_choke_points,
                "map_package:choke_points",
                True,
                False,
                GAMEPLAY_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_flank_routes,
                "map_package:flank_routes",
                True,
                False,
                GAMEPLAY_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_enemy_spawn_zones,
                "map_package:enemy_spawn_zones",
                True,
                False,
                GAMEPLAY_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_fallback_positions,
                "map_package:fallback_positions",
                True,
                False,
                GAMEPLAY_LAYER_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_runtime_objects,
                "map_package:runtime_objects",
                True,
                False,
                OBJECT_INSTANCES_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_places,
                "map_package:places",
                True,
                False,
                PLACES_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_tile_types,
                "map_package:tile_types",
                True,
                False,
                TILE_TYPES_CATALOG_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_object_types,
                "map_package:object_types",
                True,
                False,
                OBJECT_TYPES_CATALOG_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_render_profile,
                "map_package:render_profile",
                True,
                False,
                RENDER_PROFILE_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_tile_render_hints,
                "map_package:tile_render_hints",
                True,
                False,
                TILE_RENDER_HINTS_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_object_render_hints,
                "map_package:object_render_hints",
                True,
                False,
                OBJECT_RENDER_HINTS_SCHEMA_VERSION,
            ),
            OutputArtifact(
                outputs.map_package_vegetation_visual,
                "map_package:vegetation_visual",
                True,
                False,
                VEGETATION_VISUAL_SCHEMA_VERSION,
            ),
        ]
        if render:
            layer_paths = {
                "base": outputs.layer_base_map,
                "combat": outputs.layer_combat_zones,
                "cover": outputs.layer_cover_points,
                "choke": outputs.layer_choke_points,
                "flank": outputs.layer_flank_routes,
                "spawn": outputs.layer_enemy_spawn_zones,
                "fallback": outputs.layer_fallback_positions,
                "runtime_objects": outputs.layer_runtime_objects,
                "all": outputs.layer_all_debug,
            }
            for layer in rendered_layers:
                artifacts.append(
                    OutputArtifact(
                        layer_paths[layer],
                        f"png_layer:{layer}",
                        layer == "base",
                        layer != "base",
                        PNG_LAYER_SCHEMA_VERSION,
                    ),
                )
        return artifacts

    @staticmethod
    def _project_version() -> str:
        from . import __version__

        return __version__

    @staticmethod
    def _format_metrics(metrics: dict[str, Any]) -> str:
        lines = ["Top-down worldgen v0.19 refactor metrics", ""]
        for key, value in metrics.items():
            lines.append(f"{key}: {value}")
        lines.append("")
        return "\n".join(lines)
