import json
from pathlib import Path

from top_down_worldgen.config import GenerationTuning, PublicConfig
from top_down_worldgen.tactical.elevation import generate_next_gen_elevation


def test_water_tuning_fields_are_loaded_and_clamped() -> None:
    """Ensure water tuning fields expose count, size, and density controls."""
    tuning = GenerationTuning.from_raw(
        {
            "water_scale": 5.0,
            "water_patch_count_scale": 3.0,
            "water_patch_size_scale": 2.0,
            "water_patch_density": 0.85,
            "bunker_scale": 12.0,
        },
    )

    assert tuning.water_scale == 5.0
    assert tuning.water_patch_count_scale == 3.0
    assert tuning.water_patch_size_scale == 2.0
    assert tuning.water_patch_density == 0.85
    assert tuning.bunker_scale == 10.0


def test_water_patch_density_is_a_ratio() -> None:
    """Ensure water density is clamped independently from scale fields."""
    tuning = GenerationTuning.from_raw({"water_patch_density": 3.0})

    assert tuning.water_patch_density == 1.0


def test_public_config_reads_nested_elevation_style(tmp_path: Path) -> None:
    """Ensure elevation style can be selected from public config."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "seed": 42,
                "map_width_tiles": 64,
                "map_height_tiles": 64,
                "chunk_width_tiles": 16,
                "chunk_height_tiles": 16,
                "biome_profile": "forest_ruins",
                "elevation": {"style": "rolling_hills"},
            },
        ),
        encoding="utf-8",
    )

    config = PublicConfig.from_file(config_path)

    assert config.elevation_style == "rolling_hills"


def test_invalid_elevation_style_falls_back_to_normal(tmp_path: Path) -> None:
    """Ensure invalid elevation styles do not escape config loading."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "seed": 42,
                "map_width_tiles": 64,
                "map_height_tiles": 64,
                "chunk_width_tiles": 16,
                "chunk_height_tiles": 16,
                "biome_profile": "forest_ruins",
                "elevation_style": "nonsense",
            },
        ),
        encoding="utf-8",
    )

    config = PublicConfig.from_file(config_path)

    assert config.elevation_style == "normal"


def test_elevation_style_changes_profile_report() -> None:
    """Ensure style presets change the reported elevation profile."""
    rows = ["S" + "+" * 14 + "G"] + ["+" * 16 for _ in range(15)]

    flatland = generate_next_gen_elevation(rows=rows, seed=7, elevation_style="flatland")
    mountainous = generate_next_gen_elevation(rows=rows, seed=7, elevation_style="mountainous")

    assert flatland.report["profile"]["style"] == "flatland"
    assert flatland.report["profile"]["active_range"] == [-1, 4]
    assert flatland.report["profile"]["rare_range"] == [-2, 6]
    assert mountainous.report["profile"]["style"] == "mountainous"
    assert mountainous.report["profile"]["active_range"] == [-5, 20]
    assert mountainous.report["profile"]["rare_range"] == [-5, 20]
