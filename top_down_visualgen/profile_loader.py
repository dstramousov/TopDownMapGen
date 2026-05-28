from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json_object
from .models import VisualProfile


class VisualProfileLoader:
    """Load visual profile files from a profile directory."""

    REQUIRED_FILES = {
        "profile": "visual_profile.json",
        "tilesets": "visual_tilesets.json",
        "terrain_rules": "terrain_visual_rules.json",
        "object_rules": "object_visual_rules.json",
        "autotile_rules": "autotile_rules.json",
        "decoration_rules": "decoration_rules.json",
        "prefab_rules": "prefab_rules.json",
        "place_rules": "place_visual_rules.json",
        "elevation_rules": "elevation_visual_rules.json",
    }

    def load(self, profile_dir: Path) -> VisualProfile:
        """Load a visual profile.

        Args:
            profile_dir: Directory containing visual rule JSON files.

        Returns:
            Loaded visual profile.

        Raises:
            FileNotFoundError: If a required visual profile file is missing.
        """
        root = profile_dir.resolve()
        data: dict[str, dict[str, Any]] = {}
        for key, filename in self.REQUIRED_FILES.items():
            path = root / filename
            if not path.exists():
                raise FileNotFoundError(f"Required visual profile file not found: {path}")
            data[key] = read_json_object(path)

        return VisualProfile(
            root_dir=root,
            profile=data["profile"],
            tilesets=data["tilesets"],
            terrain_rules=data["terrain_rules"],
            object_rules=data["object_rules"],
            autotile_rules=data["autotile_rules"],
            decoration_rules=data["decoration_rules"],
            prefab_rules=data["prefab_rules"],
            place_rules=data["place_rules"],
            elevation_rules=data["elevation_rules"],
        )
