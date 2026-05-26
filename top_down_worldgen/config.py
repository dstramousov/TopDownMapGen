from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import ENGINE_CONFIG_FIELDS, OBJECTIVE_PROFILES
from .logging_utils import timed_stage
from .utils.json_io import read_json, write_json


LOGGER = logging.getLogger(__name__)
UINT64_MAX = (1 << 64) - 1
MIN_TUNING_SCALE = 0.0
MAX_TUNING_SCALE = 4.0


@dataclass(frozen=True, slots=True)
class GenerationTuning:
    """User-facing world density tuning scales."""

    water_scale: float = 1.0
    forest_scale: float = 1.0
    open_space_scale: float = 1.0
    ruins_scale: float = 1.0
    buildings_scale: float = 1.0
    road_width_scale: float = 1.0
    decoration_scale: float = 1.0
    bunker_scale: float = 1.0

    @classmethod
    def from_raw(cls, value: Any) -> "GenerationTuning":
        """Build tuning from an optional config object.

        Args:
            value: Raw generation_tuning config value.

        Returns:
            Sanitized tuning instance.
        """
        if not isinstance(value, dict):
            return cls()
        defaults = cls()
        fields = defaults.to_dict()
        sanitized: dict[str, float] = {}
        for key, default in fields.items():
            sanitized[key] = _sanitize_scale(value.get(key, default), key=key)
        return cls(**sanitized)

    def to_dict(self) -> dict[str, float]:
        """Return JSON-serializable tuning values."""
        return {
            "water_scale": self.water_scale,
            "forest_scale": self.forest_scale,
            "open_space_scale": self.open_space_scale,
            "ruins_scale": self.ruins_scale,
            "buildings_scale": self.buildings_scale,
            "road_width_scale": self.road_width_scale,
            "decoration_scale": self.decoration_scale,
            "bunker_scale": self.bunker_scale,
        }


def _sanitize_scale(value: Any, *, key: str) -> float:
    """Clamp a user-provided scale to a safe range."""
    try:
        scale = float(value)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid generation_tuning.%s=%r; using 1.0", key, value)
        return 1.0
    if scale < MIN_TUNING_SCALE or scale > MAX_TUNING_SCALE:
        LOGGER.warning(
            "generation_tuning.%s=%s is outside %.1f..%.1f; clamping",
            key,
            scale,
            MIN_TUNING_SCALE,
            MAX_TUNING_SCALE,
        )
    return max(MIN_TUNING_SCALE, min(scale, MAX_TUNING_SCALE))


@dataclass(frozen=True, slots=True)
class PublicConfig:
    """Public generator configuration."""

    seed: Any
    resolved_seed: int
    map_width_tiles: int
    map_height_tiles: int
    chunk_width_tiles: int
    chunk_height_tiles: int
    biome_profile: str
    objective_profile: str = "clear_map"
    generation_tuning: GenerationTuning = field(default_factory=GenerationTuning)

    @classmethod
    def from_file(cls, path: Path) -> "PublicConfig":
        """Load public config from a JSON file.

        Args:
            path: Config JSON path.

        Returns:
            PublicConfig instance.
        """
        with timed_stage(LOGGER, "PublicConfig.from_file", path=path) as metrics:
            data = read_json(path)
            objective_profile = str(data.get("objective_profile", "clear_map"))
            if objective_profile not in OBJECTIVE_PROFILES:
                LOGGER.warning(
                    "Unknown objective_profile=%s, falling back to clear_map",
                    objective_profile,
                )
                objective_profile = "clear_map"

            raw_seed = data.get("seed", "random")
            resolved_seed = resolve_seed(raw_seed)
            config = cls(
                seed=raw_seed,
                resolved_seed=resolved_seed,
                map_width_tiles=int(data["map_width_tiles"]),
                map_height_tiles=int(data["map_height_tiles"]),
                chunk_width_tiles=int(data["chunk_width_tiles"]),
                chunk_height_tiles=int(data["chunk_height_tiles"]),
                biome_profile=str(data["biome_profile"]),
                objective_profile=objective_profile,
                generation_tuning=GenerationTuning.from_raw(data.get("generation_tuning")),
            )
            metrics.update(
                {
                    "seed": config.seed,
                    "resolved_seed": config.resolved_seed,
                    "map_width_tiles": config.map_width_tiles,
                    "map_height_tiles": config.map_height_tiles,
                    "chunk_width_tiles": config.chunk_width_tiles,
                    "chunk_height_tiles": config.chunk_height_tiles,
                    "biome_profile": config.biome_profile,
                    "objective_profile": config.objective_profile,
                    "generation_tuning": config.generation_tuning.to_dict(),
                },
            )
            return config

    def to_engine_dict(self) -> dict[str, Any]:
        """Convert config to legacy engine-compatible dictionary.

        Returns:
            Dict accepted by the legacy v0.15 engine.
        """
        data = {
            "seed": self.resolved_seed,
            "map_width_tiles": self.map_width_tiles,
            "map_height_tiles": self.map_height_tiles,
            "chunk_width_tiles": self.chunk_width_tiles,
            "chunk_height_tiles": self.chunk_height_tiles,
            "biome_profile": self.biome_profile,
            "generation_tuning": self.generation_tuning.to_dict(),
        }
        output = {key: value for key, value in data.items() if key in ENGINE_CONFIG_FIELDS}
        LOGGER.debug("Engine config fields created count=%s", len(output))
        return output

    def write_engine_config(self, path: Path) -> None:
        """Write sanitized legacy-engine config.

        Args:
            path: Output config path.
        """
        with timed_stage(LOGGER, "PublicConfig.write_engine_config", path=path) as metrics:
            engine_config = self.to_engine_dict()
            write_json(engine_config, path)
            metrics.update({"field_count": len(engine_config)})


def resolve_seed(seed: Any) -> int:
    """Resolve a config seed into a concrete uint64 value.

    Args:
        seed: Raw seed value from public config.

    Returns:
        Concrete uint64 seed used by the generator.
    """
    if is_uint64_seed(seed):
        return int(seed)

    resolved_seed = secrets.randbits(64)
    if seed != "random":
        LOGGER.warning("Invalid seed in config; generated a random uint64 seed")
    return resolved_seed


def is_uint64_seed(seed: Any) -> bool:
    """Return whether a raw value is a valid uint64 seed.

    Args:
        seed: Raw seed value.

    Returns:
        True if the value is an integer in uint64 range.
    """
    return not isinstance(seed, bool) and isinstance(seed, int) and 0 <= seed <= UINT64_MAX
