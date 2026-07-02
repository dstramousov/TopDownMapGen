#!/usr/bin/env python3
"""Render a compact comparison gallery for elevation style presets."""

from __future__ import annotations

import argparse
import copy
import json
import logging
import shutil
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from examples.render_world_preview import render_preview
from top_down_worldgen.config import (
    DEFAULT_ELEVATION_STYLE,
    SUPPORTED_ELEVATION_STYLES,
    is_uint64_seed,
)
from top_down_worldgen.pipeline import WorldgenPipeline
from top_down_worldgen.utils.json_io import read_json, write_json

LOGGER = logging.getLogger(__name__)

DEFAULT_STYLES = (
    "flatland",
    "rolling_hills",
    "normal",
    "rugged",
    "mountainous",
    "plateau",
)
DEFAULT_OUTPUT_DIR = Path("output/elevation_style_gallery")
DEFAULT_CONFIG = Path("configs/default.json")
DEFAULT_CELL_SIZE_PX = 4
GALLERY_SCHEMA_VERSION = "elevation-style-gallery-v1"
THUMBNAIL_SIZE = (320, 320)
STYLE_LABEL_WIDTH_PX = 260
THUMBNAIL_GAP_PX = 18
ROW_GAP_PX = 24
HEADER_HEIGHT_PX = 74
ROW_HEIGHT_PX = 392
BACKGROUND_COLOR = (26, 27, 25, 255)
PANEL_COLOR = (37, 38, 34, 255)
TEXT_COLOR = (232, 229, 212, 255)
MUTED_TEXT_COLOR = (180, 174, 150, 255)
BORDER_COLOR = (78, 74, 63, 255)
COLUMN_TITLES = (
    ("geography_preview.png", "geography"),
    ("elevation_preview.png", "elevation"),
    ("slope_preview.png", "slope"),
)


@dataclass(frozen=True, slots=True)
class StyleRunResult:
    """Generated artifacts and metrics for one elevation style.

    Attributes:
        style: Elevation style name.
        output_dir: Style-specific output directory.
        summary_path: Path to world summary report.
        status: Run status.
        metrics: Flattened comparison metrics.
    """

    style: str
    output_dir: Path
    summary_path: Path
    status: str
    metrics: dict[str, Any]


def parse_style_list(raw_styles: str | Iterable[str]) -> list[str]:
    """Parse, validate, and de-duplicate elevation style names.

    Args:
        raw_styles: Comma-separated style string or iterable of style names.

    Returns:
        Ordered list of supported elevation style names.

    Raises:
        ValueError: If an unknown style is requested or no styles remain.
    """
    if isinstance(raw_styles, str):
        candidates = raw_styles.split(",")
    else:
        candidates = list(raw_styles)

    styles: list[str] = []
    for raw_style in candidates:
        style = str(raw_style).strip().lower()
        if not style:
            continue
        if style not in SUPPORTED_ELEVATION_STYLES:
            supported = ", ".join(sorted(SUPPORTED_ELEVATION_STYLES))
            raise ValueError(f"Unknown elevation style '{style}'. Supported: {supported}")
        if style not in styles:
            styles.append(style)

    if not styles:
        raise ValueError("At least one elevation style must be selected")
    return styles


def build_style_config(
    base_config: dict[str, Any],
    *,
    style: str,
    seed: int,
    width: int | None,
    height: int | None,
) -> dict[str, Any]:
    """Build a style-specific public config dictionary.

    Args:
        base_config: Base public config dictionary.
        style: Elevation style to set.
        seed: Shared uint64 seed used for all compared styles.
        width: Optional map width override.
        height: Optional map height override.

    Returns:
        New JSON-serializable config dictionary.
    """
    config = copy.deepcopy(base_config)
    config["seed"] = seed
    if width is not None:
        config["map_width_tiles"] = width
    if height is not None:
        config["map_height_tiles"] = height

    elevation_config = config.get("elevation")
    if not isinstance(elevation_config, dict):
        elevation_config = {}
    elevation_config["style"] = style
    config["elevation"] = elevation_config

    # Keep backward-compatible flat key in sync for older local configs.
    if "elevation_style" in config:
        config["elevation_style"] = style
    return config


def resolve_gallery_seed(raw_seed: Any, base_config: dict[str, Any]) -> int:
    """Resolve one shared seed for the whole style comparison.

    Args:
        raw_seed: Optional CLI seed value.
        base_config: Base public config dictionary.

    Returns:
        Concrete uint64 seed.

    Raises:
        ValueError: If neither CLI nor base config contains a fixed uint64 seed.
    """
    if raw_seed is not None:
        try:
            seed = int(raw_seed)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid --seed value: {raw_seed!r}") from exc
        if not is_uint64_seed(seed):
            raise ValueError("--seed must be an unsigned 64-bit integer")
        return seed

    config_seed = base_config.get("seed")
    if is_uint64_seed(config_seed):
        return int(config_seed)
    raise ValueError(
        "Base config uses a random seed. Pass --seed to make all styles comparable."
    )


def run_style_gallery(
    *,
    project_root: Path,
    config_path: Path,
    output_dir: Path,
    styles: list[str],
    seed: int,
    width: int | None,
    height: int | None,
    cell_size_px: int,
    clean: bool,
) -> dict[str, Any]:
    """Generate all selected elevation styles and write gallery outputs.

    Args:
        project_root: Repository root.
        config_path: Base public config path.
        output_dir: Gallery output directory.
        styles: Elevation styles to generate.
        seed: Shared generation seed.
        width: Optional width override.
        height: Optional height override.
        cell_size_px: 2D preview cell size in pixels.
        clean: Whether to remove an existing gallery directory first.

    Returns:
        Machine-readable gallery report.
    """
    base_config = read_json(config_path)
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[StyleRunResult] = []
    for style in styles:
        LOGGER.info("Generating elevation style: %s", style)
        style_dir = output_dir / style
        style_dir.mkdir(parents=True, exist_ok=True)
        style_config = build_style_config(
            base_config,
            style=style,
            seed=seed,
            width=width,
            height=height,
        )
        style_config_path = style_dir / "config.json"
        write_json(style_config, style_config_path)

        pipeline_result = WorldgenPipeline(project_root).run(
            config_path=style_config_path,
            output_map=style_dir,
            tile_size_px=16,
            render=False,
            debug_images=False,
            log_file=style_dir / "generation.log",
        )
        _render_style_previews(style_dir, cell_size_px=cell_size_px)
        metrics = _extract_style_metrics(pipeline_result.summary)
        results.append(
            StyleRunResult(
                style=style,
                output_dir=style_dir,
                summary_path=style_dir / "world_summary_report.json",
                status=str(pipeline_result.summary.get("status", "unknown")),
                metrics=metrics,
            ),
        )

    report = _build_gallery_report(
        config_path=config_path,
        output_dir=output_dir,
        seed=seed,
        width=width,
        height=height,
        cell_size_px=cell_size_px,
        results=results,
    )
    write_json(report, output_dir / "style_comparison_report.json")
    (output_dir / "style_comparison_summary.md").write_text(
        _format_markdown_summary(report),
        encoding="utf-8",
    )
    render_style_gallery_image(
        results,
        output_path=output_dir / "style_gallery.png",
        seed=seed,
    )
    return report


def _render_style_previews(style_dir: Path, *, cell_size_px: int) -> None:
    """Render the compact 2D preview set for one style."""
    render_preview(
        style_dir,
        output_path=style_dir / "geography_preview.png",
        cell_size_px=cell_size_px,
        draw_objects=False,
        draw_geography_only=True,
    )
    render_preview(
        style_dir,
        output_path=style_dir / "elevation_preview.png",
        cell_size_px=cell_size_px,
        draw_objects=False,
        draw_elevation_only=True,
        draw_elevation_legend=True,
        draw_elevation_contours=True,
    )
    render_preview(
        style_dir,
        output_path=style_dir / "slope_preview.png",
        cell_size_px=cell_size_px,
        draw_objects=False,
        draw_slope_only=True,
    )


def _extract_style_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    """Extract stable comparison metrics from a world summary report."""
    elevation = _as_dict(summary.get("elevation_density"))
    geography = _as_dict(elevation.get("geography"))
    slope_bands = _as_dict(_as_dict(geography.get("slope")).get("bands"))
    profile = _as_dict(elevation.get("profile"))
    elevation_summary = _as_dict(elevation.get("summary"))
    standing_water = _as_dict(geography.get("standing_water"))
    repair_summary = _as_dict(_as_dict(elevation.get("traversal_repair")).get("summary"))
    route_summary = _as_dict(_as_dict(elevation.get("main_route_alignment")).get("summary"))
    region_summary = _as_dict(
        _as_dict(elevation.get("region_transition_shaping")).get("summary"),
    )
    island_summary = _as_dict(_as_dict(elevation.get("terrain_island_repair")).get("summary"))
    overall = _as_dict(summary.get("overall"))

    return {
        "style": profile.get("style", DEFAULT_ELEVATION_STYLE),
        "status": summary.get("status", "unknown"),
        "overall_status": overall.get("status", "unknown"),
        "min_level": elevation_summary.get("min_level"),
        "max_level": elevation_summary.get("max_level"),
        "flat_percent": _metric_percent(slope_bands, "flat"),
        "gentle_percent": _metric_percent(slope_bands, "gentle"),
        "steep_percent": _metric_percent(slope_bands, "steep"),
        "cliff_percent": _metric_percent(slope_bands, "cliff"),
        "water_percent": _metric_percent(standing_water, "water_total"),
        "wet_lowland_percent": _metric_percent(standing_water, "wet_lowland_total"),
        "traversal_unreachable_before": repair_summary.get("unreachable_before", 0),
        "traversal_repair_adjusted_tiles": repair_summary.get("adjusted_tiles", 0),
        "goal_reachable_after": bool(repair_summary.get("goal_reachable_after", False)),
        "main_route_delta_violations_after": route_summary.get("delta_violations_after", 0),
        "main_route_adjusted_tiles": route_summary.get("adjusted_tiles", 0),
        "region_boundary_cliffs_after": region_summary.get("cliff_edges_after", 0),
        "region_transition_adjusted_tiles": region_summary.get("adjusted_tiles", 0),
        "small_island_tiles_removed": island_summary.get("small_island_tiles_removed", 0),
        "large_islands_preserved": island_summary.get("large_islands_preserved", 0),
    }


def _build_gallery_report(
    *,
    config_path: Path,
    output_dir: Path,
    seed: int,
    width: int | None,
    height: int | None,
    cell_size_px: int,
    results: list[StyleRunResult],
) -> dict[str, Any]:
    """Build the machine-readable style gallery report."""
    return {
        "schema_version": GALLERY_SCHEMA_VERSION,
        "config_path": str(config_path),
        "output_dir": str(output_dir),
        "seed": seed,
        "width_override": width,
        "height_override": height,
        "cell_size_px": cell_size_px,
        "styles": [result.style for result in results],
        "results": [
            {
                "style": result.style,
                "status": result.status,
                "output_dir": str(result.output_dir),
                "world_summary_report": str(result.summary_path),
                "previews": {
                    "geography": str(result.output_dir / "geography_preview.png"),
                    "elevation": str(result.output_dir / "elevation_preview.png"),
                    "slope": str(result.output_dir / "slope_preview.png"),
                },
                "metrics": result.metrics,
            }
            for result in results
        ],
    }


def _format_markdown_summary(report: dict[str, Any]) -> str:
    """Format the gallery report as a compact Markdown table."""
    rows = []
    for result in report.get("results", []):
        metrics = _as_dict(_as_dict(result).get("metrics"))
        rows.append(
            [
                str(result.get("style", "unknown")),
                _format_percent(metrics.get("flat_percent")),
                _format_percent(metrics.get("gentle_percent")),
                _format_percent(metrics.get("steep_percent")),
                _format_percent(metrics.get("cliff_percent")),
                str(metrics.get("traversal_repair_adjusted_tiles", 0)),
                str(metrics.get("main_route_delta_violations_after", 0)),
                "yes" if metrics.get("goal_reachable_after") else "no",
            ],
        )

    header = [
        "style",
        "flat",
        "gentle",
        "steep",
        "cliff",
        "repair tiles",
        "route violations",
        "goal 3D",
    ]
    lines = [
        "# Elevation style comparison",
        "",
        f"Seed: `{report.get('seed')}`",
        "",
        _markdown_row(header),
        _markdown_row(["---"] * len(header)),
    ]
    lines.extend(_markdown_row(row) for row in rows)
    lines.append("")
    lines.append("Generated previews per style: `geography_preview.png`, `elevation_preview.png`, `slope_preview.png`.")
    return "\n".join(lines) + "\n"


def render_style_gallery_image(
    results: list[StyleRunResult],
    *,
    output_path: Path,
    seed: int,
) -> None:
    """Render a single contact-sheet PNG from generated style previews."""
    width = (
        STYLE_LABEL_WIDTH_PX
        + len(COLUMN_TITLES) * THUMBNAIL_SIZE[0]
        + (len(COLUMN_TITLES) + 1) * THUMBNAIL_GAP_PX
    )
    height = HEADER_HEIGHT_PX + len(results) * ROW_HEIGHT_PX + ROW_GAP_PX
    image = Image.new("RGBA", (width, height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.text((24, 18), "Elevation style gallery", fill=TEXT_COLOR, font=font)
    draw.text((24, 38), f"seed: {seed}", fill=MUTED_TEXT_COLOR, font=font)
    for index, (_filename, title) in enumerate(COLUMN_TITLES):
        x = STYLE_LABEL_WIDTH_PX + THUMBNAIL_GAP_PX + index * (THUMBNAIL_SIZE[0] + THUMBNAIL_GAP_PX)
        draw.text((x, 48), title, fill=MUTED_TEXT_COLOR, font=font)

    y = HEADER_HEIGHT_PX
    for result in results:
        _draw_style_row(image, draw, font, result, y)
        y += ROW_HEIGHT_PX

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _draw_style_row(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    result: StyleRunResult,
    y: int,
) -> None:
    """Draw one style row on the contact-sheet image."""
    draw.rectangle((12, y + 6, image.width - 12, y + ROW_HEIGHT_PX - 10), fill=PANEL_COLOR, outline=BORDER_COLOR)
    metrics = result.metrics
    label_lines = [
        result.style,
        f"levels: {metrics.get('min_level')}..{metrics.get('max_level')}",
        f"flat/gentle: {_format_percent(metrics.get('flat_percent'))} / {_format_percent(metrics.get('gentle_percent'))}",
        f"steep/cliff: {_format_percent(metrics.get('steep_percent'))} / {_format_percent(metrics.get('cliff_percent'))}",
        f"repair: {metrics.get('traversal_repair_adjusted_tiles', 0)} tiles",
        f"goal 3D: {'yes' if metrics.get('goal_reachable_after') else 'no'}",
    ]
    draw.multiline_text((24, y + 24), "\n".join(label_lines), fill=TEXT_COLOR, font=font, spacing=5)

    for index, (filename, _title) in enumerate(COLUMN_TITLES):
        preview_path = result.output_dir / filename
        x = STYLE_LABEL_WIDTH_PX + THUMBNAIL_GAP_PX + index * (THUMBNAIL_SIZE[0] + THUMBNAIL_GAP_PX)
        if preview_path.exists():
            thumb = _thumbnail(preview_path, THUMBNAIL_SIZE)
            image.alpha_composite(thumb, (x, y + 42))
            draw.rectangle((x, y + 42, x + THUMBNAIL_SIZE[0], y + 42 + THUMBNAIL_SIZE[1]), outline=BORDER_COLOR)
        else:
            draw.rectangle((x, y + 42, x + THUMBNAIL_SIZE[0], y + 42 + THUMBNAIL_SIZE[1]), outline=BORDER_COLOR)
            draw.text((x + 20, y + 180), "missing preview", fill=MUTED_TEXT_COLOR, font=font)


def _thumbnail(path: Path, size: tuple[int, int]) -> Image.Image:
    """Load a PNG and fit it into a padded thumbnail canvas."""
    with Image.open(path) as source:
        source = source.convert("RGBA")
        source.thumbnail(size)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        offset = ((size[0] - source.width) // 2, (size[1] - source.height) // 2)
        canvas.alpha_composite(source, offset)
        return canvas


def _metric_percent(container: dict[str, Any], key: str) -> float:
    """Return a metric percent value from a nested metric dictionary."""
    return float(_as_dict(container.get(key)).get("percent", 0.0))


def _format_percent(value: Any) -> str:
    """Format a percent-like value with one decimal place."""
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _markdown_row(values: list[str]) -> str:
    """Return one Markdown table row."""
    return "| " + " | ".join(values) + " |"


def _as_dict(value: Any) -> dict[str, Any]:
    """Return value if it is a dictionary, otherwise an empty dictionary."""
    return value if isinstance(value, dict) else {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate 2D preview gallery for elevation style presets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python3 tools/render_elevation_style_gallery.py --seed 17103622893603560793
              python3 tools/render_elevation_style_gallery.py --styles flatland,normal,mountainous --width 192 --height 192
            """,
        ),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Base public config JSON path.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR, help="Gallery output directory.")
    parser.add_argument(
        "--styles",
        default=",".join(DEFAULT_STYLES),
        help="Comma-separated elevation styles to compare.",
    )
    parser.add_argument("--seed", default=None, help="Shared uint64 seed. Required if config seed is random.")
    parser.add_argument("--width", type=int, default=None, help="Optional map width override.")
    parser.add_argument("--height", type=int, default=None, help="Optional map height override.")
    parser.add_argument("--cell-size", type=int, default=DEFAULT_CELL_SIZE_PX, help="2D preview cell size in pixels.")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove an existing gallery directory first.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed tool logs.")
    return parser.parse_args()


def main() -> int:
    """Run the elevation style gallery CLI."""
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(message)s",
    )
    try:
        project_root = PROJECT_ROOT
        if args.cell_size < 3:
            raise ValueError("--cell-size must be at least 3 pixels")
        styles = parse_style_list(args.styles)
        base_config = read_json(args.config)
        seed = resolve_gallery_seed(args.seed, base_config)
        report = run_style_gallery(
            project_root=project_root,
            config_path=args.config,
            output_dir=args.out,
            styles=styles,
            seed=seed,
            width=args.width,
            height=args.height,
            cell_size_px=args.cell_size,
            clean=not args.no_clean,
        )
    except (FileNotFoundError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        LOGGER.error("Elevation style gallery: FAILED")
        LOGGER.error("- %s", exc)
        return 1

    output_root = Path(str(report.get("output_dir")))
    print("Elevation style gallery: OK")
    print(f"Output: {output_root}")
    print(f"Report: {output_root / 'style_comparison_report.json'}")
    print(f"Summary: {output_root / 'style_comparison_summary.md'}")
    print(f"Gallery: {output_root / 'style_gallery.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
