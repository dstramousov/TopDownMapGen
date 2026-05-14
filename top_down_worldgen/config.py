from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import ENGINE_CONFIG_FIELDS, OBJECTIVE_PROFILES
from .utils.json_io import read_json, write_json


@dataclass(frozen=True, slots=True)
class PublicConfig:
    """Public generator configuration."""

    seed: int | str
    map_width_tiles: int
    map_height_tiles: int
    chunk_width_tiles: int
    chunk_height_tiles: int
    biome_profile: str
    objective_profile: str = "clear_map"

    @classmethod
    def from_file(cls, path: Path) -> "PublicConfig":
        """Load public config from a JSON file.

        Args:
            path: Config JSON path.

        Returns:
            PublicConfig instance.
        """
        data = read_json(path)
        objective_profile = str(data.get("objective_profile", "clear_map"))
        if objective_profile not in OBJECTIVE_PROFILES:
            objective_profile = "clear_map"

        return cls(
            seed=data.get("seed", "random"),
            map_width_tiles=int(data["map_width_tiles"]),
            map_height_tiles=int(data["map_height_tiles"]),
            chunk_width_tiles=int(data["chunk_width_tiles"]),
            chunk_height_tiles=int(data["chunk_height_tiles"]),
            biome_profile=str(data["biome_profile"]),
            objective_profile=objective_profile,
        )

    def to_engine_dict(self) -> dict[str, Any]:
        """Convert config to legacy engine-compatible dictionary.

        Returns:
            Dict accepted by the legacy v0.15 engine.
        """
        data = {
            "seed": self.seed,
            "map_width_tiles": self.map_width_tiles,
            "map_height_tiles": self.map_height_tiles,
            "chunk_width_tiles": self.chunk_width_tiles,
            "chunk_height_tiles": self.chunk_height_tiles,
            "biome_profile": self.biome_profile,
        }
        return {key: value for key, value in data.items() if key in ENGINE_CONFIG_FIELDS}

    def write_engine_config(self, path: Path) -> None:
        """Write sanitized legacy-engine config.

        Args:
            path: Output config path.
        """
        write_json(self.to_engine_dict(), path)
