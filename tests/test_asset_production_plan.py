from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast


PROFILE_DIR = Path("top_down_visualgen/profiles/dark_forest")


def _load_asset_plan_module() -> ModuleType:
    """Load the asset production plan CLI module."""
    path = Path("bin/print_asset_plan.py")
    spec = importlib.util.spec_from_file_location("print_asset_plan", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_asset_production_plan_has_first_grass_forest_batch() -> None:
    """Asset plan exposes the approved first grass and forest batch."""
    module = _load_asset_plan_module()
    build_asset_plan_report = cast(Any, module).build_asset_plan_report

    report = build_asset_plan_report(PROFILE_DIR)

    assert report["schema_version"] == "asset-production-plan-report-v1"
    assert report["summary"]["status"] == "ok"
    assert report["summary"]["batches"] == 1
    assert report["summary"]["assets"] == 20
    assert report["by_category"]["ground"] == 10
    assert report["by_category"]["forest"] == 10
    assert report["by_status"]["planned"] == 20

    batch = report["batches"][0]
    assert batch["batch_id"] == "B01"
    assert batch["title"] == "Grass + Forest Base"
    asset_ids = {asset["asset_id"] for asset in batch["assets"]}
    assert "terrain.grass_base_01" in asset_ids
    assert "forest.fill_01" in asset_ids
    assert "forest.edge_n" in asset_ids


def test_asset_production_plan_writes_report(tmp_path: Path) -> None:
    """Asset plan report is written as reusable JSON."""
    module = _load_asset_plan_module()
    build_asset_plan_report = cast(Any, module).build_asset_plan_report
    write_asset_plan_report = cast(Any, module).write_asset_plan_report

    report = build_asset_plan_report(PROFILE_DIR)
    report_path = write_asset_plan_report(report, tmp_path)

    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "asset-production-plan-report-v1" in text
    assert "terrain.grass_base_01" in text
    assert "Базовая трава и лесная масса" in text
