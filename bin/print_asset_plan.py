#!/usr/bin/env python3
"""Print the dark forest asset production plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_PLAN_NAME = "asset_batches.json"


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If the root value is not an object.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _iter_assets(plan: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for batch in plan.get("batches", []):
        if not isinstance(batch, dict):
            continue
        for item in batch.get("assets", []):
            if isinstance(item, dict):
                asset = dict(item)
                asset["batch_id"] = batch.get("batch_id", "unknown")
                assets.append(asset)
    return assets


def build_asset_plan_report(profile_dir: Path) -> dict[str, Any]:
    """Build an asset production plan report.

    Args:
        profile_dir: Visual profile directory containing asset_batches.json.

    Returns:
        Report with counters and batch summaries.
    """
    plan_path = profile_dir / DEFAULT_PLAN_NAME
    plan = read_json(plan_path)
    assets = _iter_assets(plan)
    ids = [str(asset.get("asset_id", "")) for asset in assets]
    duplicate_ids = sorted(asset_id for asset_id, count in Counter(ids).items() if count > 1)

    by_status = Counter(str(asset.get("status", "unknown")) for asset in assets)
    by_type = Counter(str(asset.get("type", "unknown")) for asset in assets)
    by_category = Counter(str(asset.get("category", "unknown")) for asset in assets)
    by_priority = Counter(str(asset.get("priority", "unknown")) for asset in assets)

    batches: list[dict[str, Any]] = []
    for batch in plan.get("batches", []):
        if not isinstance(batch, dict):
            continue
        batch_assets = [asset for asset in assets if asset.get("batch_id") == batch.get("batch_id")]
        batches.append(
            {
                "batch_id": batch.get("batch_id"),
                "title": batch.get("title"),
                "title_ru": batch.get("title_ru"),
                "status": batch.get("status"),
                "priority": batch.get("priority"),
                "asset_count": len(batch_assets),
                "assets": batch_assets,
            }
        )

    return {
        "schema_version": "asset-production-plan-report-v1",
        "profile": plan.get("profile"),
        "world_style": plan.get("world_style"),
        "plan_path": str(plan_path),
        "summary": {
            "batches": len(batches),
            "assets": len(assets),
            "duplicate_ids": duplicate_ids,
            "status": "ok" if not duplicate_ids else "error",
        },
        "by_status": dict(sorted(by_status.items())),
        "by_type": dict(sorted(by_type.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_priority": dict(sorted(by_priority.items())),
        "batches": batches,
    }


def write_asset_plan_report(report: dict[str, Any], output_dir: Path) -> Path:
    """Write the asset plan report JSON.

    Args:
        report: Report data.
        output_dir: Output directory.

    Returns:
        Path to the written report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "asset_production_plan_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def print_asset_plan_summary(report: dict[str, Any]) -> None:
    """Print a compact asset production plan summary."""
    summary = report["summary"]
    print("Asset production plan:")
    print(f"  profile: {report.get('profile')}")
    print(f"  world style: {report.get('world_style')}")
    print(f"  batches: {summary['batches']}")
    print(f"  assets: {summary['assets']}")
    print(f"  status: {summary['status']}")
    print()
    print("By status:")
    for key, value in report["by_status"].items():
        print(f"  {key}: {value}")
    print()
    print("By category:")
    for key, value in report["by_category"].items():
        print(f"  {key}: {value}")
    print()
    print("Batches:")
    for batch in report["batches"]:
        print(
            f"  {batch['batch_id']}: {batch['title']} / {batch['title_ru']} "
            f"({batch['asset_count']} assets, {batch['status']})"
        )
        for asset in batch["assets"]:
            print(
                "    - "
                f"{asset.get('asset_id')} — {asset.get('name_ru')} "
                f"[{asset.get('type')}, {asset.get('category')}, {asset.get('status')}]"
            )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile_dir",
        nargs="?",
        default="top_down_visualgen/profiles/dark_forest",
        type=Path,
        help="Visual profile directory containing asset_batches.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/visual_map/debug"),
        help="Directory for asset_production_plan_report.json.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Write JSON without printing the summary.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the asset plan CLI."""
    args = parse_args()
    report = build_asset_plan_report(args.profile_dir)
    report_path = write_asset_plan_report(report, args.output)
    if not args.json_only:
        print_asset_plan_summary(report)
        print()
        print(f"Report: {report_path}")
    if report["summary"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
