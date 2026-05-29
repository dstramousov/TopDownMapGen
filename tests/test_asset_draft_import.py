from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from PIL import Image


def _load_import_module() -> ModuleType:
    """Load the asset draft import CLI module."""
    path = Path("bin/import_asset_drafts.py")
    spec = importlib.util.spec_from_file_location("import_asset_drafts", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_png(path: Path) -> None:
    """Write a tiny PNG fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (16, 16), (12, 34, 56, 255))
    image.save(path)


def _create_profile(tmp_path: Path) -> Path:
    """Create a minimal visual profile with an import alias."""
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "assets_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "assets-manifest-v1",
                "profile": "test_profile",
                "asset_root": "../assets",
                "fallbacks": {
                    "missing_tile": "debug.missing_tile",
                    "missing_sprite": "debug.missing_sprite",
                },
                "tiles": {
                    "forest.fill": {"path": "tiles/forest/fill.png", "size": [16, 16]},
                    "debug.missing_tile": {"path": "tiles/debug/missing.png", "size": [16, 16]},
                },
                "sprites": {
                    "decor.reeds_01": {
                        "path": "sprites/decor/reeds_01.png",
                        "size": [16, 16],
                        "pivot": [8, 8],
                        "sort_anchor": [8, 8],
                        "draw_layer": "decor",
                    },
                    "debug.missing_sprite": {
                        "path": "sprites/debug/missing.png",
                        "size": [16, 16],
                        "pivot": [8, 8],
                        "sort_anchor": [8, 8],
                        "draw_layer": "debug",
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (profile / "asset_import_aliases.json").write_text(
        json.dumps(
            {
                "schema_version": "asset-import-aliases-v1",
                "profile": "test_profile",
                "mappings": {"forest_fill_01": "forest.fill"},
            }
        ),
        encoding="utf-8",
    )
    return profile


def _create_draft_zip(tmp_path: Path) -> Path:
    """Create a draft ZIP with one explicit alias and one automatic sprite mapping."""
    draft_root = tmp_path / "draft"
    png_dir = draft_root / "png"
    manifest_dir = draft_root / "manifest"
    _write_png(png_dir / "forest_fill_01.png")
    _write_png(png_dir / "decor_reeds_01.png")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "asset_registry.json").write_text(
        json.dumps(
            {
                "registry_version": "asset-production-registry-v1",
                "batch": {"batch_id": "B01", "version": "v001"},
                "assets": [
                    {"asset_id": "forest_fill_01", "file": "png/forest_fill_01.png"},
                    {"asset_id": "decor_reeds_01", "file": "png/decor_reeds_01.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    zip_path = tmp_path / "draft.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(draft_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(draft_root))
    return zip_path


def test_import_asset_drafts_copies_mapped_pngs(tmp_path: Path) -> None:
    """Accepted draft archives are copied to manifest-defined target paths."""
    module = _load_import_module()
    import_asset_drafts = cast(Any, module).import_asset_drafts
    profile = _create_profile(tmp_path)
    draft_zip = _create_draft_zip(tmp_path)

    report = import_asset_drafts(profile, [draft_zip], output_dir=tmp_path / "report")

    assert report["schema_version"] == "asset-draft-import-report-v1"
    assert report["imported"] == 2
    assert report["by_kind"] == {"tile": 1, "sprite": 1}
    assert not report["skipped_unmapped"]
    assert (tmp_path / "assets" / "tiles" / "forest" / "fill.png").exists()
    assert (tmp_path / "assets" / "sprites" / "decor" / "reeds_01.png").exists()
    assert (tmp_path / "report" / "asset_draft_import_report.json").exists()


def test_import_asset_drafts_dry_run_does_not_write_pngs(tmp_path: Path) -> None:
    """Dry-run mode writes the report but does not copy asset files."""
    module = _load_import_module()
    import_asset_drafts = cast(Any, module).import_asset_drafts
    profile = _create_profile(tmp_path)
    draft_zip = _create_draft_zip(tmp_path)

    report = import_asset_drafts(profile, [draft_zip], output_dir=tmp_path / "report", dry_run=True)

    assert report["dry_run"] is True
    assert report["imported"] == 2
    assert not (tmp_path / "assets" / "tiles" / "forest" / "fill.png").exists()
    assert (tmp_path / "report" / "asset_draft_import_report.json").exists()
