import pytest

from top_down_worldgen.tactical.elevation import (
    build_geography_draft,
    build_natural_geography_model,
    generate_next_gen_elevation,
)


def test_geography_draft_is_deterministic() -> None:
    """Ensure the same map request produces identical draft fields."""
    first = build_geography_draft(
        width=24,
        height=20,
        seed=12345,
        elevation_style="plateau",
    )
    second = build_geography_draft(
        width=24,
        height=20,
        seed=12345,
        elevation_style="plateau",
    )

    assert first == second
    assert first.width == 24
    assert first.height == 20
    assert first.elevation_style == "plateau"
    assert len(first.elevation_scores) == 20
    assert len(first.elevation_scores[0]) == 24
    assert len(first.macro_regions) > 0


def test_prebuilt_geography_draft_preserves_elevation_output() -> None:
    """Ensure reusing the early draft does not alter elevation generation."""
    rows = ["S" + "+" * 22 + "G"] + ["+" * 24 for _ in range(19)]
    draft = build_geography_draft(
        width=24,
        height=20,
        seed=54321,
        elevation_style="rolling_hills",
    )

    direct = generate_next_gen_elevation(
        rows=rows,
        seed=54321,
        elevation_style="rolling_hills",
    )
    reused = generate_next_gen_elevation(
        rows=rows,
        seed=54321,
        elevation_style="rolling_hills",
        geography_draft=draft,
    )

    assert reused.rows == direct.rows
    assert reused.report == direct.report


def test_geography_draft_rejects_another_generation_request() -> None:
    """Ensure a draft cannot be silently reused for another map."""
    rows = ["S" + "+" * 14 + "G"] + ["+" * 16 for _ in range(15)]
    draft = build_geography_draft(
        width=16,
        height=16,
        seed=7,
        elevation_style="normal",
    )

    with pytest.raises(ValueError, match="does not match generation request"):
        generate_next_gen_elevation(
            rows=rows,
            seed=8,
            elevation_style="normal",
            geography_draft=draft,
        )


def test_early_natural_geography_preserves_late_elevation_output() -> None:
    """Ensure the pre-terrain natural model preserves final generation."""
    rows = ["S" + "+" * 22 + "G"] + ["+" * 24 for _ in range(19)]
    draft = build_geography_draft(
        width=24,
        height=20,
        seed=777,
        elevation_style="plateau",
    )
    model = build_natural_geography_model(
        width=24,
        height=20,
        seed=777,
        elevation_style="plateau",
        geography_draft=draft,
    )

    direct = generate_next_gen_elevation(
        rows=rows,
        seed=777,
        elevation_style="plateau",
        geography_draft=draft,
    )
    early = generate_next_gen_elevation(
        rows=rows,
        seed=777,
        elevation_style="plateau",
        geography_draft=draft,
        natural_geography=model,
    )

    assert early.rows == direct.rows
    assert early.report["summary"] == direct.report["summary"]
    assert early.report["early_geography_verification"] == {
        "enabled": True,
        "matched": True,
        "tiles_checked": 480,
    }


def test_large_map_macro_regions_scale_with_area() -> None:
    """Ensure a large map adds regions instead of stretching a fixed set."""
    from top_down_worldgen.tactical.elevation import (
        _build_macro_regions,
        _profile_for_size,
    )

    medium_profile = _profile_for_size(
        width=192,
        height=192,
        elevation_style="mountainous",
    )
    huge_profile = _profile_for_size(
        width=992,
        height=992,
        elevation_style="mountainous",
    )
    medium_regions = _build_macro_regions(
        width=192,
        height=192,
        seed=123,
        profile=medium_profile,
    )
    huge_regions = _build_macro_regions(
        width=992,
        height=992,
        seed=123,
        profile=huge_profile,
    )

    assert len(medium_regions) == 8
    assert len(huge_regions) == 62
    assert max(region.radius_tiles for region in huge_regions) < 170.0


def test_large_map_noise_domain_preserves_tile_scale() -> None:
    """Ensure noise domains expand when map dimensions exceed 192 tiles."""
    from top_down_worldgen.tactical.elevation import _geography_noise_domain_scale

    assert _geography_noise_domain_scale(width=192, height=192) == (1.0, 1.0)
    scale_x, scale_y = _geography_noise_domain_scale(width=992, height=512)

    assert scale_x == pytest.approx(991 / 191)
    assert scale_y == pytest.approx(511 / 191)


def test_large_map_spatial_index_matches_direct_nearest_regions() -> None:
    """Ensure indexed candidates preserve direct nearest-region results."""
    from random import Random

    from top_down_worldgen.tactical.elevation import (
        _build_macro_region_spatial_index,
        _build_macro_regions,
        _nearest_macro_regions,
        _profile_for_size,
    )

    profile = _profile_for_size(
        width=992,
        height=992,
        elevation_style="mountainous",
    )
    regions = _build_macro_regions(
        width=992,
        height=992,
        seed=321,
        profile=profile,
    )
    spatial_index = _build_macro_region_spatial_index(
        width=992,
        height=992,
        regions=regions,
    )
    assert spatial_index is not None

    rng = Random(777)
    for _ in range(250):
        x = rng.uniform(0.0, 991.0)
        y = rng.uniform(0.0, 991.0)
        indexed = _nearest_macro_regions(
            x=x,
            y=y,
            regions=regions,
            spatial_index=spatial_index,
            limit=3,
        )
        direct = _nearest_macro_regions(
            x=x,
            y=y,
            regions=regions,
            spatial_index=None,
            limit=3,
        )

        assert [(distance, index) for distance, index, _ in indexed] == [
            (distance, index) for distance, index, _ in direct
        ]
