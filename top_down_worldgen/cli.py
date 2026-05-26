from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .logging_utils import timed_stage
from .pipeline import WorldgenPipeline


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Generate top-down world map.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "-o",
        "--out",
        required=True,
        type=Path,
        help=(
            "Output directory or generated map .txt path. "
            "Directory targets use generated_map.txt inside that directory."
        ),
    )
    parser.add_argument("--render-tile-size", type=int, choices=[16, 32], default=16)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--include-debug-layers", action="store_true")
    parser.add_argument(
        "--no-debug-images",
        action="store_true",
        help="Deprecated no-op; debug PNG layers are disabled by default.",
    )
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--profile-performance", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(log_file: Path | None, verbose: bool = False) -> None:
    """Configure logging.

    Args:
        log_file: Optional log file path.
        verbose: Whether to enable debug-level logging.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
    logging.getLogger("PIL").setLevel(logging.WARNING)


def main() -> int:
    """Run CLI entrypoint."""
    args = parse_args()
    configure_logging(args.log_file, args.verbose)
    try:
        project_root = Path(__file__).resolve().parent.parent
        debug_layers = bool(args.include_debug_layers)
        if args.no_debug_images:
            LOGGER.warning(
                "--no-debug-images is deprecated and has no effect; "
                "debug PNG layers are disabled by default",
            )
        LOGGER.info(
            "CLI args config=%s out=%s render=%s debug_layers=%s tile_size_px=%s "
            "log_file=%s verbose=%s",
            args.config,
            args.out,
            not args.no_render,
            debug_layers,
            args.render_tile_size,
            args.log_file,
            args.verbose,
        )
        with timed_stage(LOGGER, "cli.main"):
            result = WorldgenPipeline(project_root).run(
                config_path=args.config,
                output_map=args.out,
                tile_size_px=args.render_tile_size,
                render=not args.no_render,
                debug_images=debug_layers,
                log_file=args.log_file,
            )
        LOGGER.info("Output root: %s", result.outputs.output_dir)
        LOGGER.info("Generated map: %s", result.outputs.generated_map)
        LOGGER.info("Runtime tactical map: %s", result.outputs.tactical_map)
        LOGGER.info("Debug tactical map: %s", result.outputs.tactical_map_debug)
        LOGGER.info("Generation manifest: %s", result.outputs.manifest)
        if not args.no_render:
            LOGGER.info("Rendered base PNG layer in: %s", result.outputs.output_dir)
            if debug_layers:
                LOGGER.info("Rendered PNG debug layers in: %s", result.outputs.output_dir)
            else:
                LOGGER.info("PNG debug layers were skipped by default")
        if args.profile_performance:
            LOGGER.info("engine_time_ms=%.2f", result.metrics["engine_time_ms"])
            LOGGER.info("tactical_time_ms=%.2f", result.metrics["tactical_time_ms"])
            LOGGER.info("render_time_ms=%.2f", result.metrics["render_time_ms"])
            LOGGER.info("total_time_ms=%.2f", result.metrics["total_time_ms"])
        return 0
    except Exception as exc:
        LOGGER.error("%s", exc)
        return 1
