from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geography_draft import GeographyDraft

GUIDANCE_SCHEMA_VERSION = "terrain-guidance-v1"
GUIDANCE_SCALE = 10_000


def build_geography_guidance_payload(draft: GeographyDraft) -> dict[str, Any]:
    """Build a compact JSON payload for the legacy terrain generator.

    Args:
        draft: Prebuilt continuous geography context.

    Returns:
        Quantized elevation, moisture, and local slope grids.
    """
    slope_rows = _local_slope_rows(draft.elevation_scores)
    return {
        "schema_version": GUIDANCE_SCHEMA_VERSION,
        "width": draft.width,
        "height": draft.height,
        "seed": draft.seed,
        "elevation_style": draft.elevation_style,
        "scale": GUIDANCE_SCALE,
        "elevation_rows": _quantize_rows(draft.elevation_scores),
        "moisture_rows": _quantize_rows(draft.moisture_scores),
        "slope_rows": _quantize_rows(slope_rows),
    }


def write_geography_guidance(draft: GeographyDraft, path: Path) -> None:
    """Write geography guidance without pretty-printing large grids.

    Args:
        draft: Prebuilt continuous geography context.
        path: Internal guidance JSON path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_geography_guidance_payload(draft)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _quantize_rows(rows: list[list[float]]) -> list[list[int]]:
    return [
        [max(0, min(GUIDANCE_SCALE, round(value * GUIDANCE_SCALE))) for value in row]
        for row in rows
    ]


def _local_slope_rows(rows: list[list[float]]) -> list[list[float]]:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    output = [[0.0 for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            current = rows[y][x]
            maximum = 0.0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx = x + dx
                ny = y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    maximum = max(maximum, abs(current - rows[ny][nx]))
            output[y][x] = maximum
    return output
