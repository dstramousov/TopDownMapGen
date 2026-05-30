from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast


PROFILE_DIR = Path("top_down_visualgen/profiles/dark_forest")


def _load_preview_module() -> ModuleType:
    """Load the asset registry preview CLI module."""
    path = Path("bin/generate_asset_registry_preview.py")
    spec = importlib.util.spec_from_file_location("generate_asset_registry_preview", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_asset_registry_report_counts_manifest_entries() -> None:
    """Asset registry report summarizes all manifest tile and sprite entries."""
    module = _load_preview_module()
    build_registry_report = cast(Any, module).build_registry_report

    report = build_registry_report(PROFILE_DIR)

    assert report["schema_version"] == "asset-registry-report-v1"
    assert report["summary"]["tiles"] == 99
    assert report["summary"]["sprites"] == 184
    assert report["summary"]["total_entries"] == 283
    assert report["by_draw_layer"]["decor"] > 0
    assert report["by_category"]["boundary"] > 0
    file_status_total = sum(report["by_file_status"].values())
    assert file_status_total == 283


def test_asset_registry_preview_writes_json_and_html(tmp_path: Path) -> None:
    """Asset registry preview writes reusable JSON and HTML reports."""
    module = _load_preview_module()
    generate_asset_registry_preview = cast(Any, module).generate_asset_registry_preview

    generated = generate_asset_registry_preview(PROFILE_DIR, tmp_path)

    assert generated["json"].exists()
    assert generated["html"].exists()
    html = generated["html"].read_text(encoding="utf-8")
    assert "Asset Registry Preview" in html
    assert "decor.reeds_01" in html
    assert "<th>Image</th>" in html
