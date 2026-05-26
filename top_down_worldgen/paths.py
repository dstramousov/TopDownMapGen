from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAP_FILENAME = "generated_map.txt"


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
    map_package_dir: Path
    map_package_map: Path
    map_package_markers: Path
    map_package_runtime_grids: Path
    map_package_world_graph: Path
    map_package_layers_dir: Path
    map_package_tile_grid: Path
    map_package_terrain: Path
    map_package_movement_costs: Path
    map_package_collision: Path
    map_package_elevation: Path
    map_package_start_goal: Path
    map_package_gameplay_dir: Path
    map_package_combat_zones: Path
    map_package_cover_points: Path
    map_package_choke_points: Path
    map_package_flank_routes: Path
    map_package_enemy_spawn_zones: Path
    map_package_fallback_positions: Path
    map_package_objects_dir: Path
    map_package_runtime_objects: Path
    map_package_places: Path
    map_package_catalogs_dir: Path
    map_package_tile_types: Path
    map_package_object_types: Path
    map_package_render_dir: Path
    map_package_render_profile: Path
    map_package_tile_render_hints: Path
    map_package_object_render_hints: Path

    @classmethod
    def from_cli_output(cls, output_path: Path) -> "OutputPaths":
        """Build standard output paths from a CLI output target.

        Args:
            output_path: Output directory or ASCII map output path.

        Returns:
            OutputPaths instance.
        """
        return cls.from_output_map(resolve_output_map_path(output_path))

    @classmethod
    def from_output_map(cls, map_path: Path) -> "OutputPaths":
        """Build standard output paths near map file.

        Args:
            map_path: ASCII map output path.

        Returns:
            OutputPaths instance.
        """
        output_dir = map_path.parent
        map_package_dir = output_dir / "map_package"
        map_package_layers_dir = map_package_dir / "layers"
        map_package_gameplay_dir = map_package_dir / "gameplay"
        map_package_objects_dir = map_package_dir / "objects"
        map_package_catalogs_dir = map_package_dir / "catalogs"
        map_package_render_dir = map_package_dir / "render"
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
            map_package_dir=map_package_dir,
            map_package_map=map_package_dir / "map.json",
            map_package_markers=map_package_dir / "markers.json",
            map_package_runtime_grids=map_package_dir / "runtime_grids.json",
            map_package_world_graph=map_package_dir / "world_graph.json",
            map_package_layers_dir=map_package_layers_dir,
            map_package_tile_grid=map_package_layers_dir / "tile_grid.json",
            map_package_terrain=map_package_layers_dir / "terrain.json",
            map_package_movement_costs=map_package_layers_dir / "movement_costs.json",
            map_package_collision=map_package_layers_dir / "collision.json",
            map_package_elevation=map_package_layers_dir / "elevation.json",
            map_package_start_goal=map_package_layers_dir / "start_goal.json",
            map_package_gameplay_dir=map_package_gameplay_dir,
            map_package_combat_zones=map_package_gameplay_dir / "combat_zones.json",
            map_package_cover_points=map_package_gameplay_dir / "cover_points.json",
            map_package_choke_points=map_package_gameplay_dir / "choke_points.json",
            map_package_flank_routes=map_package_gameplay_dir / "flank_routes.json",
            map_package_enemy_spawn_zones=map_package_gameplay_dir / "enemy_spawn_zones.json",
            map_package_fallback_positions=map_package_gameplay_dir / "fallback_positions.json",
            map_package_objects_dir=map_package_objects_dir,
            map_package_runtime_objects=map_package_objects_dir / "runtime_objects.json",
            map_package_places=map_package_objects_dir / "places.json",
            map_package_catalogs_dir=map_package_catalogs_dir,
            map_package_tile_types=map_package_catalogs_dir / "tile_types.json",
            map_package_object_types=map_package_catalogs_dir / "object_types.json",
            map_package_render_dir=map_package_render_dir,
            map_package_render_profile=map_package_render_dir / "render_profile.json",
            map_package_tile_render_hints=map_package_render_dir / "tile_render_hints.json",
            map_package_object_render_hints=map_package_render_dir / "object_render_hints.json",
        )


def resolve_output_map_path(output_path: Path) -> Path:
    """Resolve a CLI output target to the ASCII map output file.

    Args:
        output_path: Directory target or concrete map file target.

    Returns:
        Path to the generated ASCII map file.
    """
    if output_path.exists() and output_path.is_dir():
        return output_path / DEFAULT_MAP_FILENAME
    if output_path.suffix:
        return output_path
    return output_path / DEFAULT_MAP_FILENAME
