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
MIN_SCALE_VALUE = 0.0
MAX_SCALE_VALUE = 4.0
MIN_ROAD_SCALE_VALUE = 0.25
MAX_OBJECT_LIMIT = 512
MAX_PLACES_LIMIT = 64


@dataclass(frozen=True, slots=True)
class GenerationTuningConfig:
    """Content tuning values for base map generation."""

    water_scale: float = 1.0
    ruins_scale: float = 1.0
    openness_scale: float = 1.0
    road_width_scale: float = 1.0
    decoration_scale: float = 1.0

    @classmethod
    def from_raw(cls, raw_value: Any) -> "GenerationTuningConfig":
        """Build tuning config from an untrusted JSON value.

        Args:
            raw_value: Raw JSON value from public config.

        Returns:
            Parsed tuning config with bounded numeric values.
        """
        if not isinstance(raw_value, dict):
            raw_value = {}
        return cls(
            water_scale=_bounded_float(
                raw_value.get("water_scale"),
                default=1.0,
                minimum=MIN_SCALE_VALUE,
                maximum=MAX_SCALE_VALUE,
            ),
            ruins_scale=_bounded_float(
                raw_value.get("ruins_scale"),
                default=1.0,
                minimum=MIN_SCALE_VALUE,
                maximum=MAX_SCALE_VALUE,
            ),
            openness_scale=_bounded_float(
                raw_value.get("openness_scale"),
                default=1.0,
                minimum=MIN_ROAD_SCALE_VALUE,
                maximum=MAX_SCALE_VALUE,
            ),
            road_width_scale=_bounded_float(
                raw_value.get("road_width_scale"),
                default=1.0,
                minimum=MIN_ROAD_SCALE_VALUE,
                maximum=MAX_SCALE_VALUE,
            ),
            decoration_scale=_bounded_float(
                raw_value.get("decoration_scale"),
                default=1.0,
                minimum=MIN_SCALE_VALUE,
                maximum=MAX_SCALE_VALUE,
            ),
        )

    def to_dict(self) -> dict[str, float]:
        """Convert config to a JSON-serializable dictionary.

        Returns:
            Tuning values keyed by public config field name.
        """
        return {
            "water_scale": self.water_scale,
            "ruins_scale": self.ruins_scale,
            "openness_scale": self.openness_scale,
            "road_width_scale": self.road_width_scale,
            "decoration_scale": self.decoration_scale,
        }


@dataclass(frozen=True, slots=True)
class RuntimeObjectsConfig:
    """Runtime object placement tuning values."""

    enabled: bool = True
    global_scale: float = 1.0
    max_objects: int = 128
    type_scales: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw_value: Any) -> "RuntimeObjectsConfig":
        """Build runtime object config from an untrusted JSON value.

        Args:
            raw_value: Raw JSON value from public config.

        Returns:
            Parsed runtime object config.
        """
        if not isinstance(raw_value, dict):
            raw_value = {}
        return cls(
            enabled=bool(raw_value.get("enabled", True)),
            global_scale=_bounded_float(
                raw_value.get("global_scale"),
                default=1.0,
                minimum=MIN_SCALE_VALUE,
                maximum=MAX_SCALE_VALUE,
            ),
            max_objects=_bounded_int(
                raw_value.get("max_objects"),
                default=128,
                minimum=0,
                maximum=MAX_OBJECT_LIMIT,
            ),
            type_scales=_float_map(raw_value.get("type_scales")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to a JSON-serializable dictionary.

        Returns:
            Runtime object tuning values.
        """
        return {
            "enabled": self.enabled,
            "global_scale": self.global_scale,
            "max_objects": self.max_objects,
            "type_scales": dict(sorted(self.type_scales.items())),
        }


@dataclass(frozen=True, slots=True)
class PlacesConfig:
    """Micro-location grouping tuning values."""

    enabled: bool = True
    max_places: int = 12
    min_distance_tiles: int = 6
    radius_tiles: int = 6

    @classmethod
    def from_raw(cls, raw_value: Any) -> "PlacesConfig":
        """Build places config from an untrusted JSON value.

        Args:
            raw_value: Raw JSON value from public config.

        Returns:
            Parsed places config.
        """
        if not isinstance(raw_value, dict):
            raw_value = {}
        return cls(
            enabled=bool(raw_value.get("enabled", True)),
            max_places=_bounded_int(
                raw_value.get("max_places"),
                default=12,
                minimum=0,
                maximum=MAX_PLACES_LIMIT,
            ),
            min_distance_tiles=_bounded_int(
                raw_value.get("min_distance_tiles"),
                default=6,
                minimum=0,
                maximum=64,
            ),
            radius_tiles=_bounded_int(
                raw_value.get("radius_tiles"),
                default=6,
                minimum=1,
                maximum=64,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to a JSON-serializable dictionary.

        Returns:
            Places tuning values.
        """
        return {
            "enabled": self.enabled,
            "max_places": self.max_places,
            "min_distance_tiles": self.min_distance_tiles,
            "radius_tiles": self.radius_tiles,
        }


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
    generation_tuning: GenerationTuningConfig = field(
        default_factory=GenerationTuningConfig,
    )
    runtime_objects: RuntimeObjectsConfig = field(default_factory=RuntimeObjectsConfig)
    places: PlacesConfig = field(default_factory=PlacesConfig)

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
                generation_tuning=GenerationTuningConfig.from_raw(
                    data.get("generation_tuning"),
                ),
                runtime_objects=RuntimeObjectsConfig.from_raw(
                    data.get("runtime_objects"),
                ),
                places=PlacesConfig.from_raw(data.get("places")),
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
                    "runtime_objects": config.runtime_objects.to_dict(),
                    "places": config.places.to_dict(),
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


def _bounded_float(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if result < minimum:
        return minimum
    if result > maximum:
        return maximum
    return result


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if result < minimum:
        return minimum
    if result > maximum:
        return maximum
    return result


def _float_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, float] = {}
    for key, raw_scale in value.items():
        if not isinstance(key, str):
            continue
        output[key] = _bounded_float(
            raw_scale,
            default=1.0,
            minimum=MIN_SCALE_VALUE,
            maximum=MAX_SCALE_VALUE,
        )
    return output
