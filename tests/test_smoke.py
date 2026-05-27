from pathlib import Path

from top_down_worldgen import __version__
from top_down_worldgen.config import PublicConfig


def test_package_version() -> None:
    """Ensure package exposes the current version."""
    assert __version__ == "0.0.56"


def test_default_config_can_be_loaded() -> None:
    """Ensure the default config remains loadable."""
    config = PublicConfig.from_file(Path("configs/default.json"))

    assert config.map_width_tiles == 192
    assert config.map_height_tiles == 176
    assert config.objective_profile == "clear_map"
    assert isinstance(config.resolved_seed, int)
