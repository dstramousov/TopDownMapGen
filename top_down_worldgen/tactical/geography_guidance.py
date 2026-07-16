from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geography_draft import NaturalGeographyModel

GUIDANCE_SCHEMA_VERSION = "terrain-guidance-v2"
GUIDANCE_SCALE = 10_000


def build_geography_guidance_payload(model: NaturalGeographyModel) -> dict[str, Any]:
    """Build a compact JSON payload for the legacy terrain generator.

    Args:
        model: Final natural geography built before terrain generation.

    Returns:
        Quantized elevation, moisture, and local slope grids.
    """
    profile_min = min((min(row) for row in model.elevation_rows), default=0)
    profile_max = max((max(row) for row in model.elevation_rows), default=0)
    span = max(1, profile_max - profile_min)
    normalized_levels = [
        [(level - profile_min) / span for level in row]
        for row in model.elevation_rows
    ]
    max_slope = max((max(row) for row in model.slope_rows), default=0)
    normalized_slopes = [
        [delta / max(1, max_slope) for delta in row]
        for row in model.slope_rows
    ]
    return {
        "schema_version": GUIDANCE_SCHEMA_VERSION,
        "width": model.width,
        "height": model.height,
        "seed": model.seed,
        "elevation_style": model.elevation_style,
        "scale": GUIDANCE_SCALE,
        "natural_min_level": profile_min,
        "natural_max_level": profile_max,
        "natural_level_rows": model.elevation_rows,
        "natural_slope_rows": model.slope_rows,
        "elevation_rows": _quantize_rows(normalized_levels),
        "moisture_rows": _quantize_rows(model.draft.moisture_scores),
        "slope_rows": _quantize_rows(normalized_slopes),
    }


def write_geography_guidance(model: NaturalGeographyModel, path: Path) -> None:
    """Write geography guidance without pretty-printing large grids.

    Args:
        model: Final natural geography built before terrain generation.
        path: Internal guidance JSON path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_geography_guidance_payload(model)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _quantize_rows(rows: list[list[float]]) -> list[list[int]]:
    return [
        [max(0, min(GUIDANCE_SCALE, round(value * GUIDANCE_SCALE))) for value in row]
        for row in rows
    ]
