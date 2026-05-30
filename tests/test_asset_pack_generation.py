from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast


PROFILE_DIR = Path("top_down_visualgen/profiles/dark_forest")


def _load_asset_pack_module() -> ModuleType:
    """Load the asset pack generator CLI module."""
    path = Path("bin/generate_asset_pack.py")
    spec = importlib.util.spec_from_file_location("generate_asset_pack", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_asset_pack_generation_creates_placeholder_pngs(tmp_path: Path) -> None:
    """Placeholder asset pack generation creates files for every manifest entry."""
    module = _load_asset_pack_module()
    generate_asset_pack = cast(Any, module).generate_asset_pack

    report = generate_asset_pack(PROFILE_DIR, asset_root=tmp_path)

    assert report["entries_total"] == 276
    assert report["written"] == 276
    assert (tmp_path / "asset_pack_report.json").exists()
    assert (tmp_path / "sprites/decor/reeds_01.png").exists()
    assert (tmp_path / "tiles/dirt/base.png").exists()


def test_generated_asset_pack_passes_file_validation(tmp_path: Path) -> None:
    """Generated placeholder assets satisfy --check-files validation."""
    pack_module = _load_asset_pack_module()
    validate_module = _load_validator_module()
    generate_asset_pack = cast(Any, pack_module).generate_asset_pack
    validate_assets_manifest = cast(Any, validate_module).validate_assets_manifest

    generate_asset_pack(PROFILE_DIR, asset_root=tmp_path)
    issues = validate_assets_manifest(PROFILE_DIR, check_files=True, asset_root=tmp_path)

    assert issues == []
