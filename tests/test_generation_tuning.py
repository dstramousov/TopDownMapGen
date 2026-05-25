import json
from pathlib import Path

from top_down_worldgen.config import (
    PlacesConfig,
    PublicConfig,
    RuntimeObjectsConfig,
)
from top_down_worldgen.legacy.engine import DerivedConfig, PublicConfig as EngineConfig
from top_down_worldgen.tactical.places import attach_places
from top_down_worldgen.tactical.runtime_objects import attach_runtime_layers


def _write_public_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "seed": 7,
                "map_width_tiles": 160,
                "map_height_tiles": 96,
                "chunk_width_tiles": 16,
                "chunk_height_tiles": 16,
                "biome_profile": "forest_ruins",
                "generation_tuning": {
                    "water_scale": 2.0,
                    "ruins_scale": 1.5,
                    "openness_scale": 1.25,
                    "road_width_scale": 1.5,
                    "decoration_scale": 0.5,
                },
                "runtime_objects": {
                    "enabled": True,
                    "global_scale": 1.2,
                    "max_objects": 64,
                    "type_scales": {"rusted_barrel": 2.0},
                },
                "places": {
                    "enabled": True,
                    "max_places": 3,
                    "min_distance_tiles": 9,
                    "radius_tiles": 8,
                },
            },
        ),
        encoding="utf-8",
    )


def test_public_config_exposes_generation_tuning_blocks(tmp_path: Path) -> None:
    """Ensure public config parses all user-facing tuning sections."""
    config_path = tmp_path / "config.json"
    _write_public_config(config_path)

    config = PublicConfig.from_file(config_path)
    engine_config = config.to_engine_dict()

    assert config.generation_tuning.water_scale == 2.0
    assert config.generation_tuning.ruins_scale == 1.5
    assert config.runtime_objects.max_objects == 64
    assert config.runtime_objects.type_scales["rusted_barrel"] == 2.0
    assert config.places.max_places == 3
    assert engine_config["generation_tuning"]["road_width_scale"] == 1.5
    assert "runtime_objects" not in engine_config
    assert "places" not in engine_config


def test_legacy_derived_config_uses_generation_tuning() -> None:
    """Ensure legacy-derived map content reacts to public tuning scales."""
    default_config = EngineConfig(
        seed=1,
        map_width_tiles=160,
        map_height_tiles=96,
        chunk_width_tiles=16,
        chunk_height_tiles=16,
        biome_profile="forest_ruins",
    )
    tuned_config = EngineConfig(
        seed=1,
        map_width_tiles=160,
        map_height_tiles=96,
        chunk_width_tiles=16,
        chunk_height_tiles=16,
        biome_profile="forest_ruins",
        generation_tuning={
            "water_scale": 2.0,
            "ruins_scale": 2.0,
            "openness_scale": 1.5,
            "road_width_scale": 2.0,
            "decoration_scale": 0.5,
        },
    )

    default = DerivedConfig.from_public(default_config)
    tuned = DerivedConfig.from_public(tuned_config)

    assert tuned.water_patch_count > default.water_patch_count
    assert tuned.water_patch_max_radius >= default.water_patch_max_radius
    assert tuned.small_ruin_count > default.small_ruin_count
    assert tuned.connected_pocket_count > default.connected_pocket_count
    assert tuned.old_road_corridor_max_width > default.old_road_corridor_max_width
    assert tuned.flower_patch_count < default.flower_patch_count


def test_runtime_object_type_scale_can_disable_one_type() -> None:
    """Ensure per-type runtime object scales override the global placement quota."""
    rows = ["+" * 40 for _ in range(24)]
    runtime_data = attach_runtime_layers(
        {
            "map": {
                "width": 40,
                "height": 24,
                "tile_grid": rows,
                "tile_counts": {"+": 40 * 24},
            },
            "combat_zones": [{"id": "zone_0", "center": [20, 12]}],
            "choke_points": [{"position": [18, 12]}],
        },
        seed=1,
        config=RuntimeObjectsConfig(type_scales={"ammo_cache": 0.0}),
    )

    object_types = {item["type"] for item in runtime_data["runtime_objects"]}

    assert "ammo_cache" not in object_types
    assert "medkit_cache" in object_types
    assert runtime_data["runtime_object_schema"]["tuning"]["type_scales"]["ammo_cache"] == 0.0


def test_places_config_can_limit_and_resize_places() -> None:
    """Ensure places config controls grouping limits and output radius."""
    runtime_data = attach_places(
        {
            "runtime_objects": [
                {"id": "checkpoint_0", "type": "old_checkpoint", "position": [10, 10]},
                {"id": "barrel_0", "type": "rusted_barrel", "position": [11, 10]},
                {"id": "scrap_0", "type": "scrap_pile", "position": [12, 10]},
            ],
        },
        config=PlacesConfig(max_places=1, min_distance_tiles=0, radius_tiles=9),
    )

    assert len(runtime_data["places"]) == 1
    assert runtime_data["places"][0]["radius"] == 9
    assert runtime_data["place_schema"]["tuning"]["radius_tiles"] == 9


def test_legacy_quality_limits_warn_without_aborting() -> None:
    """Ensure extreme openness is reported as a warning, not a failed generation."""
    config = EngineConfig(
        seed=123,
        map_width_tiles=96,
        map_height_tiles=80,
        chunk_width_tiles=16,
        chunk_height_tiles=16,
        biome_profile="forest_ruins",
        generation_tuning={"openness_scale": 4.0, "road_width_scale": 4.0},
    )
    from top_down_worldgen.legacy.engine import MapGenerator

    generator = MapGenerator(config)
    generator.generate()
    diagnostics = generator.generation_diagnostics()

    assert diagnostics["status"] == "generated_with_warnings"
    assert diagnostics["warnings"]
    assert diagnostics["warnings"][0]["code"] == "quality.walkable_ratio_high"
