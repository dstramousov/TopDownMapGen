from pathlib import Path

from top_down_worldgen import __version__
from top_down_worldgen.config import PublicConfig, SUPPORTED_ELEVATION_STYLES


def test_package_version() -> None:
    """Ensure package exposes the current version."""
    assert __version__ == "0.0.155"


def test_default_config_can_be_loaded() -> None:
    """Ensure the default config remains loadable."""
    config = PublicConfig.from_file(Path("configs/default.json"))

    assert config.map_width_tiles > 0
    assert config.map_height_tiles > 0
    assert config.map_width_tiles % config.chunk_width_tiles == 0
    assert config.map_height_tiles % config.chunk_height_tiles == 0
    assert config.objective_profile == "clear_map"
    assert config.elevation_style in SUPPORTED_ELEVATION_STYLES
    assert isinstance(config.resolved_seed, int)
