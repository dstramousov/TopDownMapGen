from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geography_draft import NaturalGeographyModel

GUIDANCE_SCHEMA_VERSION = "terrain-guidance-v3"
GUIDANCE_SCALE = 10_000
REGIONAL_TERRAIN_MIN_SIDE = 193

_TERRAIN_PROFILE_TREE_COVER = {
    "dense_forest": 0.995,
    "woodland": 0.96,
    "wet_lowland": 0.92,
    "upland": 0.87,
    "open_plateau": 0.80,
    "open_plain": 0.76,
    "alpine": 0.64,
}


def build_geography_guidance_payload(model: NaturalGeographyModel) -> dict[str, Any]:
    """Build a compact JSON payload for the legacy terrain generator.

    Args:
        model: Final natural geography built before terrain generation.

    Returns:
        Quantized geography grids and optional regional base terrain.
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
    terrain_profiles = _terrain_profile_items(model)
    initial_terrain_rows = _initial_terrain_rows(
        model,
        terrain_profiles=terrain_profiles,
    )
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
        "terrain_profiles": terrain_profiles,
        "initial_terrain_rows": initial_terrain_rows,
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


def _terrain_profile_items(model: NaturalGeographyModel) -> list[dict[str, Any]]:
    """Assign one deterministic terrain profile to every macro region."""
    items: list[dict[str, Any]] = []
    for index, region in enumerate(model.draft.macro_regions):
        variant = _hash_unit(model.seed ^ 0x51A7E, index, index * 17)
        if region.kind == "basin":
            profile = "wet_lowland"
        elif region.kind == "plain":
            if region.moisture_bias >= 0.08 or variant < 0.22:
                profile = "dense_forest"
            elif variant < 0.52:
                profile = "woodland"
            else:
                profile = "open_plain"
        elif region.kind == "hill":
            profile = (
                "dense_forest"
                if region.moisture_bias > 0.10 and variant < 0.45
                else "woodland"
            )
        elif region.kind == "plateau":
            profile = "open_plateau"
        elif region.kind == "ridge":
            profile = "upland" if region.base_elevation_score < 0.72 else "alpine"
        elif region.kind in {"mountain", "peak"}:
            profile = "alpine" if region.base_elevation_score >= 0.68 else "upland"
        else:
            profile = "woodland"
        items.append(
            {
                "region_index": index,
                "region_id": region.region_id,
                "geography_kind": region.kind,
                "profile": profile,
                "tree_cover": _TERRAIN_PROFILE_TREE_COVER[profile],
            }
        )
    return items


def _initial_terrain_rows(
    model: NaturalGeographyModel,
    *,
    terrain_profiles: list[dict[str, Any]],
) -> list[str] | None:
    """Build a coherent regional TREE/GRASS base mask for large maps."""
    if min(model.width, model.height) < REGIONAL_TERRAIN_MIN_SIDE:
        return None

    profile_cover = [float(item["tree_cover"]) for item in terrain_profiles]
    dominant_rows = model.draft.dominant_region_rows
    elevation_rows = model.draft.elevation_scores
    moisture_rows = model.draft.moisture_scores
    blend_offset = max(6, min(18, round(min(model.width, model.height) / 72)))
    broad_noise = _NoiseRows(
        width=model.width,
        height=model.height,
        scale=72.0,
        seed=model.seed ^ 0xB04D,
    )
    local_noise = _NoiseRows(
        width=model.width,
        height=model.height,
        scale=26.0,
        seed=model.seed ^ 0x10CA1,
    )
    output: list[str] = []

    for y in range(model.height):
        chars: list[str] = []
        y0 = max(0, y - blend_offset)
        y1 = min(model.height - 1, y + blend_offset)
        dominant_row = dominant_rows[y]
        broad_row = broad_noise.row(y)
        local_row = local_noise.row(y)
        for x in range(model.width):
            x0 = max(0, x - blend_offset)
            x1 = min(model.width - 1, x + blend_offset)
            center_index = dominant_row[x]
            cover = (
                profile_cover[center_index] * 4.0
                + profile_cover[dominant_row[x0]]
                + profile_cover[dominant_row[x1]]
                + profile_cover[dominant_rows[y0][x]]
                + profile_cover[dominant_rows[y1][x]]
            ) / 8.0
            moisture = moisture_rows[y][x]
            elevation = elevation_rows[y][x]
            cover += (moisture - 0.5) * 0.16
            cover -= max(0.0, elevation - 0.66) * 0.34
            cover = max(0.42, min(0.995, cover))

            forest_noise = broad_row[x] * 0.68 + local_row[x] * 0.32
            chars.append("T" if forest_noise <= cover else "+")
        output.append("".join(chars))
    return output


class _NoiseRows:
    """Generate deterministic coherent value-noise rows efficiently."""

    def __init__(self, *, width: int, height: int, scale: float, seed: int) -> None:
        self._scale = scale
        self._x_samples = [_noise_coordinate(x / scale) for x in range(width)]
        lattice_width = int((max(0, width - 1) / scale)) + 2
        lattice_height = int((max(0, height - 1) / scale)) + 2
        self._lattice = [
            [_hash_unit(seed, x, y) for x in range(lattice_width)]
            for y in range(lattice_height)
        ]

    def row(self, y: int) -> list[float]:
        """Return one interpolated noise row."""
        y0, ty = _noise_coordinate(y / self._scale)
        top = self._lattice[y0]
        bottom = self._lattice[y0 + 1]
        output: list[float] = []
        for x0, tx in self._x_samples:
            top_value = _lerp(top[x0], top[x0 + 1], tx)
            bottom_value = _lerp(bottom[x0], bottom[x0 + 1], tx)
            output.append(_lerp(top_value, bottom_value, ty))
        return output


def _noise_coordinate(value: float) -> tuple[int, float]:
    """Return lattice index and smooth interpolation amount."""
    lower = int(value)
    amount = value - lower
    return lower, amount * amount * (3.0 - 2.0 * amount)


def _hash_unit(seed: int, x: int, y: int) -> float:
    """Return a stable pseudo-random value in the inclusive 0..1 range."""
    value = (
        seed ^ (x * 0x9E3779B185EBCA87) ^ (y * 0xC2B2AE3D27D4EB4F)
    ) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 31
    return value / 0xFFFFFFFFFFFFFFFF


def _lerp(first: float, second: float, amount: float) -> float:
    return first + (second - first) * amount
