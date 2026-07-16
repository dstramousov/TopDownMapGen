from __future__ import annotations

from tools.render_elevation_style_gallery import (
    build_style_config,
    parse_style_list,
    resolve_gallery_seed,
)


def test_parse_style_list_validates_and_deduplicates() -> None:
    """Ensure style list parsing is deterministic and strict."""
    assert parse_style_list("normal, rolling_hills,normal") == [
        "normal",
        "rolling_hills",
    ]


def test_build_style_config_preserves_base_and_sets_style() -> None:
    """Ensure style configs are isolated from the source config."""
    base = {
        "seed": "random",
        "map_width_tiles": 192,
        "map_height_tiles": 192,
        "elevation": {"style": "normal"},
    }

    config = build_style_config(
        base,
        style="flatland",
        seed=123,
        width=64,
        height=96,
    )

    assert base["seed"] == "random"
    assert base["elevation"]["style"] == "normal"
    assert config["seed"] == 123
    assert config["map_width_tiles"] == 64
    assert config["map_height_tiles"] == 96
    assert config["elevation"]["style"] == "flatland"


def test_resolve_gallery_seed_requires_fixed_seed_for_random_config() -> None:
    """Ensure random config seeds do not silently make incomparable galleries."""
    assert resolve_gallery_seed("42", {"seed": "random"}) == 42
    assert resolve_gallery_seed(None, {"seed": 777}) == 777
