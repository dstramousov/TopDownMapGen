from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from .config import PublicConfig
from .legacy_runner import LegacyEngineRunner
from .logging_utils import timed_stage
from .manifest import (
    ASCII_MAP_SCHEMA_VERSION,
    ENGINE_CONFIG_SCHEMA_VERSION,
    METRICS_SCHEMA_VERSION,
    PNG_LAYER_SCHEMA_VERSION,
    RAW_TACTICAL_MAP_SCHEMA_VERSION,
    TACTICAL_DEBUG_SCHEMA_VERSION,
    TACTICAL_MAP_SCHEMA_VERSION,
    VALIDATION_REPORT_SCHEMA_VERSION,
    OutputArtifact,
    build_manifest,
    write_manifest,
)
from .paths import OutputPaths
from .render.layers import LayerRenderer
from .tactical.fallback import FallbackPositionBuilder
from .tactical.grid import attach_tile_grid
from .tactical.runtime_objects import attach_runtime_layers
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
                },
            )

        with timed_stage(
            LOGGER,
            "pipeline.prepare_outputs",
            output_map=output_map,
        ) as metrics:
            outputs = OutputPaths.from_output_map(output_map)
            outputs.output_dir.mkdir(parents=True, exist_ok=True)
            config.write_engine_config(outputs.engine_config)
            metrics.update(
                {
                    "output_dir": outputs.output_dir,
                    "engine_config": outputs.engine_config,
                },
            )

        engine_started = perf_counter()
        with timed_stage(LOGGER, "pipeline.legacy_engine") as metrics:
            engine_path = self._project_root / "top_down_worldgen" / "legacy" / "engine.py"
            LegacyEngineRunner(engine_path).run(
                config_path=outputs.engine_config,
                map_out=outputs.generated_map,
                tactical_out=outputs.raw_tactical_map,
                log_file=log_file,
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
            runtime_data = attach_runtime_layers(runtime_data, seed=config.resolved_seed)
            runtime_data["version"] = "0.24-runtime"
            debug_data["version"] = "0.20-debug"

            write_json(runtime_data, outputs.tactical_map)
            write_json(debug_data, outputs.tactical_map_debug)
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
                    "elevation_cells": len(
                        runtime_data.get("elevation", {}).get("cells", []),
                    ),
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
            "elevation_cells": len(runtime_data.get("elevation", {}).get("cells", [])),
            "original_cover_points": optimization.get("original_cover_points"),
            "selected_cover_points": optimization.get("selected_cover_points"),
            "connectivity_components_before": connectivity_repair.get("components_before"),
            "connectivity_components_after": connectivity_repair.get("components_after"),
            "connectivity_filled_components": connectivity_repair.get("filled_components"),
            "connectivity_connected_components": connectivity_repair.get("connected_components"),
            "connectivity_tiles_changed": connectivity_repair.get("tiles_changed"),
        }
        with timed_stage(
            LOGGER,
            "pipeline.write_metrics",
            metrics_path=outputs.metrics,
        ) as log_metrics:
            outputs.metrics.write_text(self._format_metrics(metrics), encoding="utf-8")
            log_metrics.update({"metrics_count": len(metrics)})

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

        LOGGER.info("Pipeline completed total_time_ms=%.2f", total_time_ms)
        return PipelineResult(metrics=metrics, outputs=outputs)

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
                outputs.engine_config,
                "engine_config",
                False,
                True,
                ENGINE_CONFIG_SCHEMA_VERSION,
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
