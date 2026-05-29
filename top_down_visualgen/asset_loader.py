from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .models import VisualProfile


@dataclass(frozen=True, slots=True)
class AssetImage:
    """Loaded asset image with resolved manifest metadata."""

    item_id: str
    image: Image.Image
    path: Path
    manifest: dict[str, Any]
    missing: bool


class VisualAssetLoader:
    """Load PNG assets referenced by a visual profile asset manifest."""

    def __init__(self) -> None:
        """Initialize an empty image cache."""
        self._cache: dict[tuple[str, str], AssetImage] = {}

    def load_tile(self, profile: VisualProfile, tile_id: str) -> AssetImage:
        """Load a tile image by tile ID.

        Args:
            profile: Loaded visual profile.
            tile_id: Tile ID from visual layers.

        Returns:
            Loaded tile image and manifest metadata.
        """
        return self._load(
            profile=profile,
            section="tiles",
            item_id=tile_id,
            fallback_id=_fallback_id(profile, "missing_tile", "debug.missing_tile"),
        )

    def load_sprite(self, profile: VisualProfile, sprite_id: str) -> AssetImage:
        """Load a sprite image by sprite ID.

        Args:
            profile: Loaded visual profile.
            sprite_id: Sprite ID from visual objects.

        Returns:
            Loaded sprite image and manifest metadata.
        """
        return self._load(
            profile=profile,
            section="sprites",
            item_id=sprite_id,
            fallback_id=_fallback_id(profile, "missing_sprite", "debug.missing_sprite"),
        )

    def _load(
        self,
        *,
        profile: VisualProfile,
        section: str,
        item_id: str,
        fallback_id: str,
    ) -> AssetImage:
        cache_key = (section, item_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        entries = profile.assets_manifest.get(section, {})
        if not isinstance(entries, dict):
            entries = {}
        manifest = entries.get(item_id)
        missing = False
        resolved_id = item_id
        if not isinstance(manifest, dict):
            manifest = entries.get(fallback_id)
            resolved_id = fallback_id
            missing = True
        if not isinstance(manifest, dict):
            raise FileNotFoundError(f"Missing asset manifest entry for {section}.{item_id}")

        path = _asset_path(profile, manifest)
        if not path.exists():
            fallback_manifest = entries.get(fallback_id)
            if isinstance(fallback_manifest, dict):
                fallback_path = _asset_path(profile, fallback_manifest)
                if fallback_path.exists():
                    manifest = fallback_manifest
                    path = fallback_path
                    resolved_id = fallback_id
                    missing = True
        if not path.exists():
            raise FileNotFoundError(f"Asset file not found for {section}.{item_id}: {path}")

        image = Image.open(path).convert("RGBA")
        result = AssetImage(
            item_id=resolved_id,
            image=image,
            path=path,
            manifest=manifest,
            missing=missing,
        )
        self._cache[cache_key] = result
        return result


def _asset_path(profile: VisualProfile, manifest: dict[str, Any]) -> Path:
    path_value = manifest.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("Asset manifest entry must include a non-empty path")
    asset_root_value = profile.assets_manifest.get("asset_root")
    if isinstance(asset_root_value, str) and asset_root_value:
        asset_root = (profile.root_dir / asset_root_value).resolve()
    else:
        asset_root = profile.root_dir
    return (asset_root / path_value).resolve()


def _fallback_id(profile: VisualProfile, key: str, default: str) -> str:
    fallbacks = profile.assets_manifest.get("fallbacks", {})
    if isinstance(fallbacks, dict):
        value = fallbacks.get(key)
        if isinstance(value, str) and value:
            return value
    return default
