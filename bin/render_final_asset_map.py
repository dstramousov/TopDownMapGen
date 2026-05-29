#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from top_down_visualgen.final_renderer import FinalAssetRenderer
from top_down_visualgen.io import read_json_object, write_json_object
from top_down_visualgen.profile_loader import VisualProfileLoader


def main() -> int:
    """Render final asset-backed PNG from existing visual map outputs."""
    parser = argparse.ArgumentParser(description="Render final asset-backed visual map PNG.")
    parser.add_argument("visual_output", nargs="?", type=Path, default=Path("output/visual_map"))
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("top_down_visualgen/profiles/dark_forest"),
        help="Visual profile directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="PNG output path. Defaults to <visual_output>/final_render.png.",
    )
    args = parser.parse_args()
    output_path = args.output or (args.visual_output / "final_render.png")
    report_path = args.visual_output / "debug" / "final_render_report.json"
    render_final_asset_map(
        visual_output=args.visual_output,
        profile_dir=args.profile,
        output_path=output_path,
        report_path=report_path,
    )
    print(f"final_render={output_path}")
    print(f"final_render_report={report_path}")
    return 0


def render_final_asset_map(
    *,
    visual_output: Path,
    profile_dir: Path,
    output_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Render final asset-backed PNG from existing visual JSON files.

    Args:
        visual_output: Directory containing visual_layers.json and visual_objects.json.
        profile_dir: Visual profile directory.
        output_path: Destination PNG path.
        report_path: Destination report path.

    Returns:
        Final render report object.
    """
    profile = VisualProfileLoader().load(profile_dir)
    visual_layers = read_json_object(visual_output / "visual_layers.json")
    visual_objects = read_json_object(visual_output / "visual_objects.json")
    report = FinalAssetRenderer().render(
        visual_layers=visual_layers,
        visual_objects=visual_objects,
        profile=profile,
        output_path=output_path,
    )
    write_json_object(report, report_path)
    return report


if __name__ == "__main__":
    raise SystemExit(main())
