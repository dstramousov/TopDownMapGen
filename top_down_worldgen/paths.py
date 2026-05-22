from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OutputPaths:
    """All generated output paths."""

    output_dir: Path
    generated_map: Path
    raw_tactical_map: Path
    tactical_map: Path
    tactical_map_debug: Path
    metrics: Path
    log_file: Path
    engine_config: Path
    layer_base_map: Path
    layer_combat_zones: Path
    layer_cover_points: Path
    layer_choke_points: Path
    layer_flank_routes: Path
    layer_enemy_spawn_zones: Path
    layer_fallback_positions: Path
    layer_runtime_objects: Path
    layer_all_debug: Path
    manifest: Path
    validation_report: Path
    object_catalog: Path

    @classmethod
    def from_output_map(cls, map_path: Path) -> "OutputPaths":
        """Build standard output paths near map file.

        Args:
            map_path: ASCII map output path.

        Returns:
            OutputPaths instance.
        """
        output_dir = map_path.parent
        return cls(
            output_dir=output_dir,
            generated_map=map_path,
            raw_tactical_map=output_dir / "_raw_tactical_map.json",
            tactical_map=output_dir / "tactical_map.json",
            tactical_map_debug=output_dir / "tactical_map_debug.json",
            metrics=output_dir / "metrics.txt",
            log_file=output_dir / "generation.log",
            engine_config=output_dir / "_engine_config.json",
            layer_base_map=output_dir / "layer_base_map.png",
            layer_combat_zones=output_dir / "layer_combat_zones.png",
            layer_cover_points=output_dir / "layer_cover_points.png",
            layer_choke_points=output_dir / "layer_choke_points.png",
            layer_flank_routes=output_dir / "layer_flank_routes.png",
            layer_enemy_spawn_zones=output_dir / "layer_enemy_spawn_zones.png",
            layer_fallback_positions=output_dir / "layer_fallback_positions.png",
            layer_runtime_objects=output_dir / "layer_runtime_objects.png",
            layer_all_debug=output_dir / "layer_all_debug.png",
            manifest=output_dir / "_manifest.json",
            validation_report=output_dir / "validation_report.json",
            object_catalog=output_dir / "object_catalog.md",
        )
