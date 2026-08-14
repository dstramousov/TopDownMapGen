#!/usr/bin/env python3
"""Render diagnostic PNG previews for the public Environment Context layer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFont

DEFAULT_CELL_SIZE_PX = 4
LEGEND_WIDTH_PX = 300
TITLE_HEIGHT_PX = 38
BACKGROUND = (28, 30, 31, 255)
TEXT = (236, 236, 232, 255)
MUTED_TEXT = (176, 180, 178, 255)
FAR_COLOR = (44, 46, 48, 255)
UNKNOWN_COLOR = (255, 0, 255, 255)

REGION_COLORS = {
    "dense_forest": (38, 76, 45, 255),
    "woodland": (73, 116, 67, 255),
    "wet_lowland": (63, 126, 126, 255),
    "upland": (164, 142, 80, 255),
    "open_plateau": (181, 161, 108, 255),
    "open_plain": (126, 158, 88, 255),
    "alpine": (205, 211, 207, 255),
}
FLORA_REGION_COLORS = {
    "dry_grassland": (190, 157, 76, 255),
    "open_meadow": (139, 170, 84, 255),
    "lush_meadow": (91, 153, 74, 255),
    "scrubland": (122, 130, 67, 255),
    "wet_meadow": (76, 146, 111, 255),
    "marshland": (52, 119, 116, 255),
}
SLOPE_COLORS = {
    "flat": (91, 147, 77, 255),
    "gentle": (184, 181, 92, 255),
    "steep": (199, 119, 68, 255),
    "cliff": (139, 62, 59, 255),
}
FOREST_DEPTH_COLORS = {
    0: (197, 197, 190, 255),
    1: (172, 204, 91, 255),
    2: (111, 164, 75, 255),
    3: (62, 122, 62, 255),
    4: (29, 76, 43, 255),
}
FLORA_COLORS = {
    "water_core": (47, 102, 151, 255),
    "road_core": (151, 124, 73, 255),
    "structure_core": (110, 92, 116, 255),
    **FLORA_REGION_COLORS,
    "forest_edge": (94, 143, 67, 255),
    "deep_forest": (35, 79, 46, 255),
    "riparian_wetland": (70, 139, 139, 255),
    "dry_upland": (187, 157, 81, 255),
    "rocky_rugged": (132, 112, 100, 255),
    "disturbed": (154, 122, 93, 255),
}
FLORA_LABELS = {
    "water_core": "water core (non-flora)",
    "road_core": "road core (non-flora)",
    "structure_core": "structure core (non-flora)",
    "dry_grassland": "DRY_GRASSLAND",
    "open_meadow": "OPEN_MEADOW",
    "lush_meadow": "LUSH_MEADOW",
    "scrubland": "SCRUBLAND",
    "wet_meadow": "WET_MEADOW",
    "marshland": "MARSHLAND",
    "forest_edge": "FOREST_EDGE",
    "deep_forest": "DEEP_FOREST",
    "riparian_wetland": "RIPARIAN_WETLAND",
    "dry_upland": "DRY_UPLAND",
    "rocky_rugged": "ROCKY_RUGGED",
    "disturbed": "DISTURBED",
}


def render_environment_previews(
    root: Path,
    *,
    output_dir: Path | None = None,
    cell_size_px: int = DEFAULT_CELL_SIZE_PX,
) -> tuple[Path, ...]:
    """Render all Environment Context diagnostic previews.

    Args:
        root: Generation output directory.
        output_dir: Optional destination directory. Defaults to root.
        cell_size_px: Pixel size of one map tile in the preview.

    Returns:
        Paths of generated PNG files.

    Raises:
        FileNotFoundError: If the Environment Context layer is missing.
        ValueError: If the public layer is malformed.
    """
    if cell_size_px < 1:
        raise ValueError("cell_size_px must be positive")

    root = root.resolve()
    context_path = root / "map_package" / "layers" / "environment_context.json"
    if not context_path.is_file():
        raise FileNotFoundError(f"Environment Context not found: {context_path}")

    context = _load_object(context_path)
    width = _positive_int(context, "width")
    height = _positive_int(context, "height")
    grids = _mapping(context, "grids")
    dictionaries = _mapping(context, "dictionaries")
    target = output_dir or root
    target.mkdir(parents=True, exist_ok=True)

    moisture = _grid(grids, "moisture", width, height)
    region = _grid(grids, "region_profile", width, height)
    flora_region = _grid(grids, "flora_region", width, height)
    slope = _grid(grids, "slope_band", width, height)
    forest_depth = _grid(grids, "forest_depth", width, height)
    forest_distance = _grid(grids, "forest_distance", width, height)
    water_distance = _grid(grids, "water_distance", width, height)
    road_distance = _grid(grids, "road_distance", width, height)
    structure_distance = _grid(grids, "structure_distance", width, height)
    region_names = _code_dictionary(dictionaries, "region_profile")
    flora_region_names = _code_dictionary(dictionaries, "flora_region")
    slope_names = _code_dictionary(dictionaries, "slope_band")

    outputs = [
        _render(
            moisture,
            target / "environment_moisture.png",
            cell_size_px,
            "Environment Context — moisture",
            _moisture_color,
            [
                ("0 dry", _moisture_color(0)),
                ("330 dry/balanced", _moisture_color(330)),
                ("660 balanced/wet", _moisture_color(660)),
                ("1000 wet", _moisture_color(1000)),
            ],
            "Public moisture scale: 0..1000",
        ),
        _render(
            region,
            target / "environment_region_profile.png",
            cell_size_px,
            "Environment Context — region profile",
            lambda value: REGION_COLORS.get(
                region_names.get(value, ""),
                UNKNOWN_COLOR,
            ),
            [
                (
                    region_names[code],
                    REGION_COLORS.get(region_names[code], UNKNOWN_COLOR),
                )
                for code in sorted(region_names)
            ],
            "Macro-region terrain guidance profile",
        ),
        _render(
            flora_region,
            target / "environment_flora_region.png",
            cell_size_px,
            "Environment Context — flora region",
            lambda value: FLORA_REGION_COLORS.get(
                flora_region_names.get(value, ""),
                UNKNOWN_COLOR,
            ),
            [
                (
                    flora_region_names[code],
                    FLORA_REGION_COLORS.get(
                        flora_region_names[code],
                        UNKNOWN_COLOR,
                    ),
                )
                for code in sorted(flora_region_names)
            ],
            (
                "Broad ground ecology from region profile + moisture; "
                "independent from forest occupancy"
            ),
        ),
        _render(
            slope,
            target / "environment_slope.png",
            cell_size_px,
            "Environment Context — slope band",
            lambda value: SLOPE_COLORS.get(slope_names.get(value, ""), UNKNOWN_COLOR),
            [
                (slope_names[code], SLOPE_COLORS.get(slope_names[code], UNKNOWN_COLOR))
                for code in sorted(slope_names)
            ],
            "0 flat, 1 gentle, 2 steep, 3 cliff",
        ),
        _render(
            forest_depth,
            target / "environment_forest_depth.png",
            cell_size_px,
            "Environment Context — forest depth",
            lambda value: FOREST_DEPTH_COLORS.get(value, UNKNOWN_COLOR),
            [
                ("4+" if value == 4 else str(value), color)
                for value, color in FOREST_DEPTH_COLORS.items()
            ],
            "0 non-forest; 1 edge; 4 means deep forest (4+)",
        ),
    ]

    distance_specs = (
        ("forest", forest_distance, (61, 150, 76, 255)),
        ("water", water_distance, (54, 132, 196, 255)),
        ("road", road_distance, (205, 158, 72, 255)),
        ("structure", structure_distance, (159, 105, 177, 255)),
    )
    for name, rows, source_color in distance_specs:
        palette = _distance_palette(source_color)
        outputs.append(
            _render(
                rows,
                target / f"environment_{name}_distance.png",
                cell_size_px,
                f"Environment Context — {name} distance",
                lambda value, current=palette: current.get(value, UNKNOWN_COLOR),
                [
                    ("9+" if value == 9 else str(value), palette[value])
                    for value in range(10)
                ],
                f"Distance to semantic {name}; 9 means 9+ tiles",
            )
        )

    flora = [
        [
            _dominant_flora_label(
                moisture=moisture[y][x],
                region_profile=region_names.get(region[y][x], "open_plain"),
                flora_region=flora_region_names.get(
                    flora_region[y][x],
                    "open_meadow",
                ),
                slope=slope[y][x],
                forest_depth=forest_depth[y][x],
                forest_distance=forest_distance[y][x],
                water_distance=water_distance[y][x],
                road_distance=road_distance[y][x],
                structure_distance=structure_distance[y][x],
            )
            for x in range(width)
        ]
        for y in range(height)
    ]
    outputs.append(
        _render(
            flora,
            target / "environment_flora_context_preview.png",
            cell_size_px,
            "Environment Context — dominant flora influence",
            lambda value: FLORA_COLORS.get(value, UNKNOWN_COLOR),
            [(FLORA_LABELS[key], color) for key, color in FLORA_COLORS.items()],
            "Diagnostic only: not an authoritative biome layer or asset choice",
        )
    )
    return tuple(outputs)


def _dominant_flora_label(
    *,
    moisture: int,
    region_profile: str,
    flora_region: str,
    slope: int,
    forest_depth: int,
    forest_distance: int,
    water_distance: int,
    road_distance: int,
    structure_distance: int,
) -> str:
    """Return the strongest debug-only flora influence for one tile."""
    if water_distance == 0:
        return "water_core"
    if structure_distance == 0:
        return "structure_core"
    if road_distance == 0:
        return "road_core"

    scores = {
        flora_region: 0.55 if forest_depth == 0 else 0.18,
        "forest_edge": max(
            {1: 1.00, 2: 0.82, 3: 0.35}.get(forest_depth, 0.0),
            {1: 0.68, 2: 0.45, 3: 0.22}.get(forest_distance, 0.0),
        ),
        "deep_forest": {3: 0.72, 4: 1.00}.get(forest_depth, 0.0),
        "riparian_wetland": _riparian_score(
            water_distance,
            moisture,
            region_profile,
        ),
        "dry_upland": _dry_upland_score(moisture, region_profile),
        "rocky_rugged": {0: 0.0, 1: 0.10, 2: 0.78, 3: 1.10}.get(
            min(3, max(0, slope)),
            0.0,
        ),
        "disturbed": max(
            {1: 1.00, 2: 0.76, 3: 0.52, 4: 0.30}.get(road_distance, 0.0),
            {1: 1.00, 2: 0.86, 3: 0.68, 4: 0.49, 5: 0.30}.get(
                structure_distance,
                0.0,
            ),
        ),
    }
    priority = (
        "disturbed",
        "rocky_rugged",
        "riparian_wetland",
        "deep_forest",
        "forest_edge",
        "dry_upland",
        flora_region,
    )
    return max(priority, key=lambda name: (scores[name], -priority.index(name)))


def _riparian_score(
    water_distance: int,
    moisture: int,
    region_profile: str,
) -> float:
    """Return a debug riparian/wetland influence score."""
    proximity = {1: 1.00, 2: 0.84, 3: 0.66, 4: 0.48, 5: 0.26}.get(
        water_distance,
        0.0,
    )
    if proximity == 0.0:
        return 0.0
    moisture_factor = 0.75 + min(1.0, max(0.0, moisture / 1000.0)) * 0.35
    bonus = 0.14 if region_profile == "wet_lowland" else 0.0
    return min(1.15, proximity * moisture_factor + bonus)


def _dry_upland_score(moisture: int, region_profile: str) -> float:
    """Return a debug dry-upland influence score."""
    profile_weight = {
        "upland": 0.88,
        "open_plateau": 0.76,
        "alpine": 1.00,
    }.get(region_profile, 0.0)
    if profile_weight == 0.0 or moisture >= 520:
        return 0.0
    dryness = (520 - max(0, moisture)) / 520.0
    return min(1.0, profile_weight * (0.35 + dryness * 0.85))


def _render(
    rows: list[list[Any]],
    output_path: Path,
    cell_size_px: int,
    title: str,
    color_for_value: Callable[[Any], tuple[int, int, int, int]],
    legend: list[tuple[str, tuple[int, int, int, int]]],
    note: str,
) -> Path:
    """Render one pre-colored Environment Context grid and legend."""
    height = len(rows)
    width = len(rows[0]) if height else 0
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("Environment Context preview grid must be rectangular")

    image = Image.new("RGBA", (width, height), UNKNOWN_COLOR)
    image.putdata([color_for_value(value) for row in rows for value in row])
    scaled = image.resize(
        (width * cell_size_px, height * cell_size_px),
        Image.Resampling.NEAREST,
    )
    canvas = Image.new(
        "RGBA",
        (scaled.width + LEGEND_WIDTH_PX, max(scaled.height + TITLE_HEIGHT_PX, 260)),
        BACKGROUND,
    )
    canvas.alpha_composite(scaled, (0, TITLE_HEIGHT_PX))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 10), title, fill=TEXT, font=_font(16))

    panel_x = scaled.width + 16
    draw.text((panel_x, 12), "Legend", fill=TEXT, font=_font(16))
    y = 46
    for label, color in legend:
        draw.rectangle((panel_x, y, panel_x + 18, y + 18), fill=color)
        draw.text((panel_x + 28, y + 2), label, fill=TEXT, font=_font(13))
        y += 25
    y += 8
    for line in _wrap(note, 36):
        draw.text((panel_x, y), line, fill=MUTED_TEXT, font=_font(13))
        y += 18

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path)
    return output_path


def _moisture_color(value: int) -> tuple[int, int, int, int]:
    """Map public moisture 0..1000 to a continuous diagnostic color."""
    value = min(1000, max(0, value))
    if value <= 330:
        return _lerp((161, 119, 75, 255), (173, 176, 91, 255), value / 330)
    if value <= 660:
        return _lerp(
            (173, 176, 91, 255),
            (78, 145, 92, 255),
            (value - 330) / 330,
        )
    return _lerp(
        (78, 145, 92, 255),
        (58, 122, 158, 255),
        (value - 660) / 340,
    )


def _distance_palette(
    source: tuple[int, int, int, int],
) -> dict[int, tuple[int, int, int, int]]:
    """Build a source-to-far palette for proximity diagnostics."""
    pale = (224, 225, 220, 255)
    result = {
        value: _lerp(source, pale, value / 9.0 * 0.88) for value in range(9)
    }
    result[9] = FAR_COLOR
    return result


def _lerp(
    start: tuple[int, int, int, int],
    end: tuple[int, int, int, int],
    amount: float,
) -> tuple[int, int, int, int]:
    """Linearly interpolate two RGBA colors."""
    amount = min(1.0, max(0.0, amount))
    return tuple(
        round(a + (b - a) * amount) for a, b in zip(start, end, strict=True)
    )


def _load_object(path: Path) -> dict[str, Any]:
    """Load one JSON object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a required object field."""
    result = value.get(key)
    if not isinstance(result, dict):
        raise ValueError(f"Expected object field: {key}")
    return result


def _positive_int(value: dict[str, Any], key: str) -> int:
    """Return a required positive integer field."""
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool) or result <= 0:
        raise ValueError(f"Expected positive integer field: {key}")
    return result


def _grid(
    grids: dict[str, Any],
    name: str,
    width: int,
    height: int,
) -> list[list[int]]:
    """Return one validated public integer grid."""
    payload = _mapping(grids, name)
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError(f"Invalid row count for grid: {name}")
    result: list[list[int]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError(f"Invalid row width for grid: {name}")
        if any(not isinstance(item, int) or isinstance(item, bool) for item in row):
            raise ValueError(f"Non-integer value in grid: {name}")
        result.append(list(row))
    return result


def _code_dictionary(dictionaries: dict[str, Any], name: str) -> dict[int, str]:
    """Decode one public string-keyed code dictionary."""
    payload = _mapping(dictionaries, name)
    result: dict[int, str] = {}
    for raw_code, raw_name in payload.items():
        if not isinstance(raw_name, str):
            raise ValueError(f"Invalid dictionary value for: {name}")
        try:
            code = int(raw_code)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid dictionary code for: {name}") from exc
        result[code] = raw_name
    return result


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a portable preview font."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _wrap(text: str, width: int) -> list[str]:
    """Wrap a short note to a fixed character width."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def main() -> int:
    """Run the command-line renderer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--cell-size", type=int, default=DEFAULT_CELL_SIZE_PX)
    args = parser.parse_args()
    try:
        outputs = render_environment_previews(
            args.root,
            output_dir=args.output_dir,
            cell_size_px=args.cell_size,
        )
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"Не удалось создать Environment Context preview: {exc}", file=sys.stderr)
        return 1
    print(
        f"Environment Context preview создан: {len(outputs)} файлов",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
