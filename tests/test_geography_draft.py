import pytest

from top_down_worldgen.tactical.elevation import (
    build_geography_draft,
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
