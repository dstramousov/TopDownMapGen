from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from .config import PublicConfig
from .legacy_runner import LegacyEngineRunner
from .paths import OutputPaths
from .render.layers import LayerRenderer
from .tactical.fallback import FallbackPositionBuilder
from .tactical.objectives import ObjectiveProfileSelector
from .tactical.optimizer import TacticalOptimizer
from .utils.json_io import read_json, write_json


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
        log_file: Path | None,
    ) -> PipelineResult:
        """Run the complete generation pipeline.

        Args:
            config_path: Public config path.
            output_map: ASCII map output path.
            tile_size_px: Render tile size.
            render: Whether to render PNG debug layers.
            log_file: Optional legacy engine log path.

        Returns:
            PipelineResult.
        """
        started = perf_counter()
        config = PublicConfig.from_file(config_path)
        outputs = OutputPaths.from_output_map(output_map)
        outputs.output_dir.mkdir(parents=True, exist_ok=True)

        config.write_engine_config(outputs.engine_config)

        engine_started = perf_counter()
        LegacyEngineRunner(self._project_root / "top_down_worldgen" / "legacy" / "engine.py").run(
            config_path=outputs.engine_config,
            map_out=outputs.generated_map,
            tactical_out=outputs.raw_tactical_map,
            log_file=log_file,
        )
        engine_time_ms = (perf_counter() - engine_started) * 1000.0

        tactical_started = perf_counter()
        raw_data = read_json(outputs.raw_tactical_map)
        runtime_data, debug_data = TacticalOptimizer().optimize(raw_data)
        runtime_data, debug_data = FallbackPositionBuilder().add(runtime_data, debug_data)
        runtime_data, debug_data = ObjectiveProfileSelector(config.objective_profile).apply(runtime_data, debug_data)
        runtime_data["version"] = "0.19-runtime"
        debug_data["version"] = "0.19-debug"

        write_json(runtime_data, outputs.tactical_map)
        write_json(debug_data, outputs.tactical_map_debug)
        tactical_time_ms = (perf_counter() - tactical_started) * 1000.0

        render_time_ms = 0.0
        if render:
            render_started = perf_counter()
            LayerRenderer(self._project_root / "assets", tile_size_px).render_all(
                outputs.generated_map,
                outputs.tactical_map_debug,
                {
                    "base": outputs.layer_base_map,
                    "combat": outputs.layer_combat_zones,
                    "cover": outputs.layer_cover_points,
                    "choke": outputs.layer_choke_points,
                    "flank": outputs.layer_flank_routes,
                    "spawn": outputs.layer_enemy_spawn_zones,
                    "fallback": outputs.layer_fallback_positions,
                    "all": outputs.layer_all_debug,
                },
            )
            render_time_ms = (perf_counter() - render_started) * 1000.0

        total_time_ms = (perf_counter() - started) * 1000.0
        rows = outputs.generated_map.read_text(encoding="utf-8").splitlines()
        width = len(rows[0]) if rows else 0
        height = len(rows)
        objective = runtime_data.get("objective", {})
        optimization = runtime_data.get("optimization", {})

        metrics = {
            "version": "clean_refactor",
            "map_width_tiles": width,
            "map_height_tiles": height,
            "tile_size_px": tile_size_px,
            "engine_time_ms": round(engine_time_ms, 2),
            "tactical_time_ms": round(tactical_time_ms, 2),
            "render_time_ms": round(render_time_ms, 2),
            "total_time_ms": round(total_time_ms, 2),
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
            "original_cover_points": optimization.get("original_cover_points"),
            "selected_cover_points": optimization.get("selected_cover_points"),
        }
        outputs.metrics.write_text(self._format_metrics(metrics), encoding="utf-8")
        return PipelineResult(metrics=metrics, outputs=outputs)

    @staticmethod
    def _format_metrics(metrics: dict[str, Any]) -> str:
        lines = ["Top-down worldgen v0.19 refactor metrics", ""]
        for key, value in metrics.items():
            lines.append(f"{key}: {value}")
        lines.append("")
        return "\n".join(lines)
