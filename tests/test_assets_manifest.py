from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from top_down_visualgen.io import read_json_object
from top_down_visualgen.profile_loader import VisualProfileLoader


PROFILE_DIR = Path("top_down_visualgen/profiles/dark_forest")


def _load_validator_module() -> ModuleType:
    """Load the assets manifest validator CLI module."""
    path = Path("bin/validate_assets_manifest.py")
    spec = importlib.util.spec_from_file_location("validate_assets_manifest", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_assets_manifest_covers_visual_tilesets_contract() -> None:
    """Assets manifest covers every logical visual tile and sprite id."""
    module = _load_validator_module()
    validate_assets_manifest = cast(Any, module).validate_assets_manifest

    issues = validate_assets_manifest(PROFILE_DIR)

    assert issues == []


def test_assets_manifest_is_loaded_with_visual_profile() -> None:
    """Visual profile loader treats assets manifest as profile data."""
    profile = VisualProfileLoader().load(PROFILE_DIR)

    assert profile.assets_manifest["schema_version"] == "assets-manifest-v1"
    assert profile.assets_manifest["fallbacks"]["missing_tile"] == "debug.missing_tile"
    assert profile.assets_manifest["fallbacks"]["missing_sprite"] == "debug.missing_sprite"


def test_assets_manifest_has_expected_anchor_contracts() -> None:
    """Sprite entries define anchors and draw layers required by renderers."""
    manifest = read_json_object(PROFILE_DIR / "assets_manifest.json")
    sprites = manifest["sprites"]

    assert sprites["decor.reeds_01"]["draw_layer"] == "decor"
    assert sprites["decor.reeds_01"]["pivot"] == [8, 12]
    assert sprites["elevation.lowland_shadow_edge"]["draw_layer"] == "elevation"
    assert sprites["boundary.dense_forest_wall"]["draw_layer"] == "boundary"
    assert sprites["object.bunker"]["sort_anchor"] == [16, 28]
