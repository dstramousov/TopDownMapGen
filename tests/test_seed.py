import json
from pathlib import Path

from top_down_worldgen.config import UINT64_MAX, PublicConfig, is_uint64_seed


def _write_config(path: Path, seed: object) -> None:
    path.write_text(
        json.dumps(
            {
                "seed": seed,
                "map_width_tiles": 160,
                "map_height_tiles": 96,
                "chunk_width_tiles": 16,
                "chunk_height_tiles": 16,
                "biome_profile": "forest_ruins",
            },
        ),
        encoding="utf-8",
    )


def test_uint64_seed_boundaries_are_valid() -> None:
    """Ensure uint64 seed boundaries are accepted."""
    assert is_uint64_seed(0)
    assert is_uint64_seed(UINT64_MAX)


def test_bool_and_out_of_range_seed_are_invalid() -> None:
    """Ensure bool and out-of-range values are not accepted as uint64 seeds."""
    assert not is_uint64_seed(True)
    assert not is_uint64_seed(-1)
    assert not is_uint64_seed(UINT64_MAX + 1)
    assert not is_uint64_seed("123")


def test_valid_config_seed_is_resolved_as_itself(tmp_path: Path) -> None:
    """Ensure valid config seed is used directly."""
    config_path = tmp_path / "config.json"
    _write_config(config_path, 42)

    config = PublicConfig.from_file(config_path)

    assert config.seed == 42
    assert config.resolved_seed == 42


def test_invalid_config_seed_generates_uint64(tmp_path: Path) -> None:
    """Ensure invalid config seed is replaced with generated uint64."""
    config_path = tmp_path / "config.json"
    _write_config(config_path, -1)

    config = PublicConfig.from_file(config_path)

    assert config.seed == -1
    assert is_uint64_seed(config.resolved_seed)
    assert config.resolved_seed != -1
