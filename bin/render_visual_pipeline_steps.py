#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from top_down_visualgen.package_loader import WorldPackageLoader
from top_down_visualgen.profile_loader import VisualProfileLoader
from top_down_visualgen.step_renderer import VisualPipelineStepRenderer

LOGGER = logging.getLogger(__name__)
DEFAULT_PROFILE_DIR = Path("top_down_visualgen/profiles/dark_forest")


def build_parser() -> argparse.ArgumentParser:
    """Build the visual step renderer CLI parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Render diagnostic PNGs for visual pipeline stages.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("output"),
        help="World generator output directory or map_package directory.",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_DIR,
        help="Visual profile directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/visual_map/debug/steps"),
        help="Directory where step PNG files should be written.",
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=None,
        help="Optional debug tile size override in pixels.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the visual step renderer CLI.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    world = WorldPackageLoader().load(args.input)
    profile = VisualProfileLoader().load(args.profile)
    paths = VisualPipelineStepRenderer().render_steps(
        world=world,
        profile=profile,
        output_dir=args.output,
        tile_size_px=args.tile_size,
    )
    for path in paths:
        LOGGER.info("step=%s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
