from top_down_worldgen.config import GenerationTuning


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
