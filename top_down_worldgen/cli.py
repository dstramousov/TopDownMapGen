from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .logging_utils import timed_stage
from .performance import PerformanceProfiler
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
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=(
            "Detailed generation log path. Defaults to generation.log inside "
            "the selected output directory."
        ),
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="Write the human-readable summary to a file instead of stdout.",
    )
    parser.add_argument("--profile-performance", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also mirror detailed pipeline logs to the console.",
    )
    return parser.parse_args()


def configure_logging(log_file: Path | None, verbose: bool = False) -> None:
    """Configure logging.

    Args:
        log_file: Optional log file path.
        verbose: Whether to also mirror detailed logs to stderr.
    """
    handlers: list[logging.Handler] = []
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    if verbose:
        handlers.append(logging.StreamHandler())
    if not handlers:
        handlers.append(logging.NullHandler())

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("PIL").setLevel(logging.WARNING)


def default_log_file(output_target: Path) -> Path:
    """Return the default detailed log file for an output target.

    Args:
        output_target: CLI output directory or generated map file path.

    Returns:
        Path to the default generation log file.
    """
    output_dir = output_target.parent if output_target.suffix == ".txt" else output_target
    return output_dir / "generation.log"


def main() -> int:
    """Run CLI entrypoint."""
    args = parse_args()
    log_file = args.log_file or default_log_file(args.out)
    configure_logging(log_file, args.verbose)
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
            "log_file=%s summary_file=%s verbose=%s",
            args.config,
            args.out,
            not args.no_render,
            debug_layers,
            args.render_tile_size,
            log_file,
            args.summary_file,
            args.verbose,
        )
        profiler = PerformanceProfiler() if args.profile_performance else None
        if profiler is not None:
            with profiler:
                with timed_stage(LOGGER, "cli.main"):
                    result = WorldgenPipeline(project_root).run(
                        config_path=args.config,
                        output_map=args.out,
                        tile_size_px=args.render_tile_size,
                        render=not args.no_render,
                        debug_images=debug_layers,
                        log_file=log_file,
                    )
        else:
            with timed_stage(LOGGER, "cli.main"):
                result = WorldgenPipeline(project_root).run(
                    config_path=args.config,
                    output_map=args.out,
                    tile_size_px=args.render_tile_size,
                    render=not args.no_render,
                    debug_images=debug_layers,
                    log_file=log_file,
                )
        LOGGER.info("Output root: %s", result.outputs.output_dir)
        LOGGER.info("Generated map: %s", result.outputs.generated_map)
        LOGGER.info("Runtime tactical map: %s", result.outputs.tactical_map)
        LOGGER.info("Debug tactical map: %s", result.outputs.tactical_map_debug)
        LOGGER.info("Generation manifest: %s", result.outputs.manifest)
        if result.console_summary:
            if args.summary_file is not None:
                args.summary_file.parent.mkdir(parents=True, exist_ok=True)
                args.summary_file.write_text(result.console_summary + "\n", encoding="utf-8")
                LOGGER.info("Console summary: %s", args.summary_file)
            else:
                print(result.console_summary)
        if not args.no_render:
            LOGGER.info("Rendered base PNG layer in: %s", result.outputs.output_dir)
            if debug_layers:
                LOGGER.info("Rendered PNG debug layers in: %s", result.outputs.output_dir)
            else:
                LOGGER.info("PNG debug layers were skipped by default")
        if profiler is not None:
            width = int(result.metrics.get("map_width_tiles", 0))
            height = int(result.metrics.get("map_height_tiles", 0))
            report = profiler.build_report(width=width, height=height)
            profile_path = result.outputs.output_dir / "performance_profile.json"
            profiler.write_report(report, profile_path)
            print(profiler.format_report(report))
            print(f"  report: {profile_path}")
            LOGGER.info("Performance profile: %s", profile_path)
        return 0
    except Exception as exc:
        LOGGER.error("%s", exc)
        if not args.verbose:
            print(f"Generation failed: {exc}")
            print(f"Detailed log: {log_file}")
        return 1
