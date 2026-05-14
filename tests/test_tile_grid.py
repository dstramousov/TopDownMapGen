import pytest

from top_down_worldgen.tactical.grid import TileGridError, attach_tile_grid


def test_attach_tile_grid_makes_tactical_map_self_contained() -> None:
    """Ensure tile grid is embedded into runtime tactical map data."""
    tactical_data = {
        "map": {
            "width": 3,
            "height": 2,
            "tile_legend": {"+": "grass", "T": "tree"},
        },
    }

    enriched = attach_tile_grid(tactical_data, ["+T+", "TT+"])

    assert enriched["map"]["tile_grid_format"] == "ascii_rows"
    assert enriched["map"]["tile_grid"] == ["+T+", "TT+"]
    assert enriched["map"]["tile_counts"] == {"+": 3, "T": 3}
    assert tactical_data["map"].get("tile_grid") is None


def test_attach_tile_grid_rejects_non_rectangular_rows() -> None:
    """Ensure malformed ASCII maps are rejected."""
    with pytest.raises(TileGridError, match="not rectangular"):
        attach_tile_grid({"map": {}}, ["++", "+"])


def test_attach_tile_grid_rejects_metadata_mismatch() -> None:
    """Ensure map metadata must match embedded tile grid dimensions."""
    with pytest.raises(TileGridError, match="width mismatch"):
        attach_tile_grid({"map": {"width": 3, "height": 1}}, ["++"])
