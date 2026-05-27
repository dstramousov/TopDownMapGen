from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .pipeline import VisualPipeline

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the visual pipeline CLI parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Build visual tileset output from a TopDownMapGen world package.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output"),
        help="World generator output directory or map_package directory.",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("top_down_visualgen/profiles/dark_forest"),
        help="Visual profile directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/visual_map"),
        help="Visual output directory.",
    )
    parser.add_argument(
        "--preview-tile-size",
        type=int,
        default=None,
        help="Optional preview tile size override in pixels.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=32,
        help="Visual chunk size in tiles.",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Skip preview.png rendering.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the visual pipeline CLI.

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

    pipeline = VisualPipeline()
    result = pipeline.run(
        input_dir=args.input,
        profile_dir=args.profile,
        output_dir=args.output,
        preview=not args.no_preview,
        preview_tile_size_px=args.preview_tile_size,
        chunk_size_tiles=args.chunk_size,
    )
    LOGGER.info("visual_map=%s", result.visual_map_path)
    LOGGER.info("visual_layers=%s", result.visual_layers_path)
    LOGGER.info("visual_objects=%s", result.visual_objects_path)
    LOGGER.info("visual_chunks=%s", result.visual_chunks_path)
    if result.preview_path is not None:
        LOGGER.info("preview=%s", result.preview_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
