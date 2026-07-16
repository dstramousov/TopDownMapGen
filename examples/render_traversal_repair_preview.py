#!/usr/bin/env python3
"""Render a side-by-side elevation preview before and after traversal repair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from render_world_preview import ELEVATION_OPAQUE_COLORS


def _load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object from disk."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _render_grid(rows: list[list[int]], cell_size: int) -> Image.Image:
    """Render one elevation grid."""
    height = len(rows)
    width = len(rows[0]) if height else 0
    image = Image.new("RGBA", (width * cell_size, height * cell_size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    for y, row in enumerate(rows):
        for x, level in enumerate(row):
            color = ELEVATION_OPAQUE_COLORS.get(int(level), (90, 90, 90, 255))
            draw.rectangle(
                (
                    x * cell_size,
                    y * cell_size,
                    (x + 1) * cell_size - 1,
                    (y + 1) * cell_size - 1,
                ),
                fill=color,
            )
    return image


def render(root: Path, output: Path, cell_size: int) -> None:
    """Render the traversal repair comparison preview."""
    runtime_grids = _load_json(root / "map_package" / "runtime_grids.json")
    tactical_map = _load_json(root / "tactical_map.json")
    grids = runtime_grids.get("grids", {})
    height_grid = grids.get("height_grid", {}) if isinstance(grids, dict) else {}
    final_rows = height_grid.get("rows", []) if isinstance(height_grid, dict) else []
    if not isinstance(final_rows, list) or not final_rows:
        raise ValueError("Missing final height grid")
    after_rows = [[int(value) for value in row] for row in final_rows]
    before_rows = [list(row) for row in after_rows]

    elevation_report = tactical_map.get("elevation_generation_report", {})
    repair = elevation_report.get("traversal_repair", {}) if isinstance(elevation_report, dict) else {}
    changes = repair.get("changes", {}) if isinstance(repair, dict) else {}
    tiles = changes.get("tiles", []) if isinstance(changes, dict) else []
    changed_points: list[tuple[int, int, int, int]] = []
    if isinstance(tiles, list):
        for item in tiles:
            if not isinstance(item, dict):
                continue
            x = item.get("x")
            y = item.get("y")
            before = item.get("before")
            after = item.get("after")
            if not all(isinstance(value, int) for value in (x, y, before, after)):
                continue
            if 0 <= y < len(before_rows) and 0 <= x < len(before_rows[y]):
                before_rows[y][x] = before
                changed_points.append((x, y, before, after))

    before_image = _render_grid(before_rows, cell_size)
    after_image = _render_grid(after_rows, cell_size)
    marker_width = max(1, cell_size // 2)
    for image in (before_image, after_image):
        draw = ImageDraw.Draw(image)
        for x, y, before, after in changed_points:
            color = (255, 70, 70, 255) if after > before else (80, 170, 255, 255)
            draw.rectangle(
                (
                    x * cell_size,
                    y * cell_size,
                    (x + 1) * cell_size - 1,
                    (y + 1) * cell_size - 1,
                ),
                outline=color,
                width=marker_width,
            )

    gap = 12
    canvas = Image.new(
        "RGBA",
        (before_image.width * 2 + gap, before_image.height),
        (24, 24, 24, 255),
    )
    canvas.alpha_composite(before_image, (0, 0))
    canvas.alpha_composite(after_image, (before_image.width + gap, 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output)


def main() -> int:
    """Run the command-line renderer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cell-size", type=int, default=4)
    args = parser.parse_args()
    render(args.root, args.output, max(1, args.cell_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
