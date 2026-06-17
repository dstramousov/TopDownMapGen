from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import cos, floor, hypot, pi, sin
from random import Random
from typing import Any, Iterable

DEFAULT_ELEVATION_LEVEL = 0
MIN_ELEVATION_LEVEL = -5
MAX_ELEVATION_LEVEL = 20
ROAD_MIN_LEVEL = 0
ROAD_MAX_LEVEL = 0
WATER_MAX_LEVEL = 0
_WALKABLE_SYMBOLS = set("+.bfmwcRSG")

_BAND_RANGES: dict[str, range] = {
    "underground_-5_-1": range(-5, 0),
    "ground_0": range(0, 1),
    "low_raised_1_4": range(1, 5),
    "hills_5_10": range(5, 11),
    "highlands_11_16": range(11, 17),
    "landmarks_17_20": range(17, 21),
}


@dataclass(frozen=True, slots=True)
class ElevationScaleProfile:
    """Size-aware elevation generation parameters."""

    name: str
    active_min_level: int
    active_max_level: int
    rare_min_level: int
    rare_max_level: int
    terrace_min_size_tiles: int
    terrace_max_size_tiles: int
    macro_frequency: float
    detail_frequency: float
    ridge_frequency: float
    warp_frequency: float
    warp_strength: float
    macro_weight: float
    detail_weight: float
    ridge_weight: float
    redistribution_power: float
    score_smoothing_passes: int
    level_relax_passes: int
    max_natural_delta: int
    ground_corridor_radius: int
    band_weights: dict[str, float]
    band_targets: dict[str, tuple[float, float]]


@dataclass(frozen=True, slots=True)
class GeographicMacroRegion:
    """Large deterministic landform region used before noise detail."""

    region_id: str
    kind: str
    center_x: float
    center_y: float
    radius_tiles: float
    strength: float
    angle_degrees: float


@dataclass(frozen=True, slots=True)
class GeographicFieldResult:
    """Continuous geographic fields built before integer terracing."""

    elevation_scores: list[list[float]]
    moisture_scores: list[list[float]]
    macro_regions: tuple[GeographicMacroRegion, ...]


@dataclass(frozen=True, slots=True)
class ElevationGenerationResult:
    """Result of deterministic next-generation elevation generation."""

    rows: list[list[int]]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TraversalRepairResult:
    """Result of the geography-level 3D traversal repair pass."""

    rows: list[list[int]]
    report: dict[str, Any]


def attach_next_gen_elevation(
    tactical_data: dict[str, Any],
    *,
    rows: list[str],
    seed: int,
) -> dict[str, Any]:
    """Attach a full-map procedural elevation layer to tactical data.

    Args:
        tactical_data: Runtime tactical data produced by the tactical pipeline.
        rows: ASCII terrain rows.
        seed: Resolved deterministic world seed.

    Returns:
        Copy of tactical data with a sparse elevation cell list representing
        non-default levels from the generated full height grid.
    """
    result = generate_next_gen_elevation(rows=rows, seed=seed, tactical_data=tactical_data)
    enriched = dict(tactical_data)
    cells: list[dict[str, int]] = []
    for y, row in enumerate(result.rows):
        for x, level in enumerate(row):
            if level != DEFAULT_ELEVATION_LEVEL:
                cells.append({"x": x, "y": y, "level": level})
    enriched["elevation"] = {
        "default": DEFAULT_ELEVATION_LEVEL,
        "cells": cells,
        "generator": result.report["generator"],
        "range": [MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL],
        "summary": result.report["summary"],
        "profile": result.report["profile"],
    }
    enriched["elevation_generation_report"] = result.report
    return enriched


def generate_next_gen_elevation(
    *,
    rows: list[str],
    seed: int,
    tactical_data: dict[str, Any] | None = None,
) -> ElevationGenerationResult:
    """Generate a size-aware Red Blob style terraced height map.

    Args:
        rows: ASCII terrain rows.
        seed: Resolved deterministic world seed.
        tactical_data: Optional runtime tactical data with object-derived elevation cells.

    Returns:
        Generated integer height rows and a JSON-serializable report.
    """
    height = len(rows)
    width = len(rows[0]) if rows else 0
    if width == 0 or height == 0:
        profile = _profile_for_size(width=width, height=height)
        report = _empty_report(width=width, height=height, seed=seed, profile=profile)
        return ElevationGenerationResult(rows=[], report=report)

    profile = _profile_for_size(width=width, height=height)
    geographic_fields = _build_geographic_fields(width=width, height=height, seed=seed, profile=profile)
    scores = _smooth_score_grid(
        geographic_fields.elevation_scores,
        passes=profile.score_smoothing_passes,
    )
    levels = _quantize_scores_to_levels(scores, profile=profile)
    levels = _apply_terrain_bias(levels, rows)
    locked_levels = _locked_terrain_levels(levels, rows)
    levels = _relax_level_deltas(
        levels,
        max_delta=profile.max_natural_delta,
        passes=profile.level_relax_passes,
        locked_levels=locked_levels,
    )
    levels = _apply_terrain_bias(levels, rows)
    locked_levels = _locked_terrain_levels(levels, rows)
    path = _find_walkable_path(rows)
    levels = _apply_ground_corridor(levels, path=path, profile=profile)
    locked_levels.update(_locked_terrain_levels(levels, rows))
    levels = _relax_level_deltas(
        levels,
        max_delta=profile.max_natural_delta,
        passes=max(1, profile.level_relax_passes // 2),
        locked_levels=locked_levels,
    )
    explicit_cells = _explicit_elevation_cells(tactical_data or {})
    traversal_repair = _repair_traversal_consistency(
        levels,
        terrain_rows=rows,
        explicit_cells=explicit_cells,
        profile=profile,
    )
    levels = traversal_repair.rows
    geographic_levels = [list(row) for row in levels]
    levels = _apply_explicit_elevation_cells(
        levels,
        explicit_cells=explicit_cells,
    )
    report = _build_generation_report(
        levels,
        geographic_levels=geographic_levels,
        terrain_rows=rows,
        explicit_cells=explicit_cells,
        seed=seed,
        corridor_path=path,
        profile=profile,
        geographic_fields=geographic_fields,
        traversal_repair_report=traversal_repair.report,
    )
    return ElevationGenerationResult(rows=levels, report=report)


def _empty_report(*, width: int, height: int, seed: int, profile: ElevationScaleProfile) -> dict[str, Any]:
    return {
        "schema_version": "next-gen-elevation-report-v2",
        "generator": _generator_info(seed=seed, profile=profile),
        "dimensions": {"width": width, "height": height, "tiles": width * height},
        "profile": _profile_report(profile),
        "summary": {
            "min_level": 0,
            "max_level": 0,
            "levels_present": [],
            "level_counts": {},
            "level_zero_percent": 0.0,
        },
        "bands": {},
    }


def _profile_for_size(*, width: int, height: int) -> ElevationScaleProfile:
    short_side = min(width, height) if width > 0 and height > 0 else 0
    if short_side <= 64:
        return ElevationScaleProfile(
            name="tiny",
            active_min_level=-1,
            active_max_level=5,
            rare_min_level=-2,
            rare_max_level=7,
            terrace_min_size_tiles=8,
            terrace_max_size_tiles=16,
            macro_frequency=0.85,
            detail_frequency=1.9,
            ridge_frequency=1.6,
            warp_frequency=1.0,
            warp_strength=0.025,
            macro_weight=0.82,
            detail_weight=0.13,
            ridge_weight=0.05,
            redistribution_power=1.08,
            score_smoothing_passes=5,
            level_relax_passes=10,
            max_natural_delta=1,
            ground_corridor_radius=2,
            band_weights={
                "underground_-5_-1": 0.04,
                "ground_0": 0.46,
                "low_raised_1_4": 0.36,
                "hills_5_10": 0.14,
                "highlands_11_16": 0.0,
                "landmarks_17_20": 0.0,
            },
            band_targets={
                "underground_-5_-1": (0.0, 6.0),
                "ground_0": (30.0, 65.0),
                "low_raised_1_4": (20.0, 55.0),
                "hills_5_10": (0.0, 20.0),
                "highlands_11_16": (0.0, 4.0),
                "landmarks_17_20": (0.0, 1.0),
            },
        )
    if short_side <= 96:
        return ElevationScaleProfile(
            name="small",
            active_min_level=-2,
            active_max_level=7,
            rare_min_level=-3,
            rare_max_level=10,
            terrace_min_size_tiles=10,
            terrace_max_size_tiles=24,
            macro_frequency=1.05,
            detail_frequency=2.3,
            ridge_frequency=2.0,
            warp_frequency=1.2,
            warp_strength=0.035,
            macro_weight=0.78,
            detail_weight=0.16,
            ridge_weight=0.06,
            redistribution_power=1.10,
            score_smoothing_passes=4,
            level_relax_passes=10,
            max_natural_delta=1,
            ground_corridor_radius=2,
            band_weights={
                "underground_-5_-1": 0.07,
                "ground_0": 0.42,
                "low_raised_1_4": 0.33,
                "hills_5_10": 0.16,
                "highlands_11_16": 0.02,
                "landmarks_17_20": 0.0,
            },
            band_targets={
                "underground_-5_-1": (1.0, 8.0),
                "ground_0": (28.0, 60.0),
                "low_raised_1_4": (20.0, 50.0),
                "hills_5_10": (4.0, 22.0),
                "highlands_11_16": (0.0, 5.0),
                "landmarks_17_20": (0.0, 1.0),
            },
        )
    if short_side <= 192:
        return ElevationScaleProfile(
            name="medium",
            active_min_level=-4,
            active_max_level=14,
            rare_min_level=-5,
            rare_max_level=20,
            terrace_min_size_tiles=16,
            terrace_max_size_tiles=40,
            macro_frequency=1.45,
            detail_frequency=3.1,
            ridge_frequency=2.6,
            warp_frequency=1.5,
            warp_strength=0.055,
            macro_weight=0.74,
            detail_weight=0.17,
            ridge_weight=0.09,
            redistribution_power=1.12,
            score_smoothing_passes=3,
            level_relax_passes=12,
            max_natural_delta=1,
            ground_corridor_radius=3,
            band_weights={
                "underground_-5_-1": 0.08,
                "ground_0": 0.36,
                "low_raised_1_4": 0.32,
                "hills_5_10": 0.17,
                "highlands_11_16": 0.06,
                "landmarks_17_20": 0.01,
            },
            band_targets={
                "underground_-5_-1": (3.0, 12.0),
                "ground_0": (25.0, 55.0),
                "low_raised_1_4": (20.0, 45.0),
                "hills_5_10": (8.0, 25.0),
                "highlands_11_16": (1.0, 12.0),
                "landmarks_17_20": (0.0, 3.0),
            },
        )
    if short_side <= 384:
        return ElevationScaleProfile(
            name="large",
            active_min_level=-5,
            active_max_level=18,
            rare_min_level=-5,
            rare_max_level=20,
            terrace_min_size_tiles=30,
            terrace_max_size_tiles=80,
            macro_frequency=1.85,
            detail_frequency=4.0,
            ridge_frequency=3.3,
            warp_frequency=1.8,
            warp_strength=0.075,
            macro_weight=0.70,
            detail_weight=0.18,
            ridge_weight=0.12,
            redistribution_power=1.15,
            score_smoothing_passes=2,
            level_relax_passes=8,
            max_natural_delta=2,
            ground_corridor_radius=4,
            band_weights={
                "underground_-5_-1": 0.10,
                "ground_0": 0.30,
                "low_raised_1_4": 0.28,
                "hills_5_10": 0.20,
                "highlands_11_16": 0.09,
                "landmarks_17_20": 0.03,
            },
            band_targets={
                "underground_-5_-1": (4.0, 15.0),
                "ground_0": (18.0, 45.0),
                "low_raised_1_4": (18.0, 42.0),
                "hills_5_10": (10.0, 30.0),
                "highlands_11_16": (3.0, 16.0),
                "landmarks_17_20": (0.5, 6.0),
            },
        )
    return ElevationScaleProfile(
        name="huge",
        active_min_level=-5,
        active_max_level=20,
        rare_min_level=-5,
        rare_max_level=20,
        terrace_min_size_tiles=48,
        terrace_max_size_tiles=128,
        macro_frequency=2.25,
        detail_frequency=5.0,
        ridge_frequency=4.0,
        warp_frequency=2.1,
        warp_strength=0.090,
        macro_weight=0.66,
        detail_weight=0.20,
        ridge_weight=0.14,
        redistribution_power=1.18,
        score_smoothing_passes=2,
        level_relax_passes=6,
        max_natural_delta=2,
        ground_corridor_radius=5,
        band_weights={
            "underground_-5_-1": 0.12,
            "ground_0": 0.24,
            "low_raised_1_4": 0.25,
            "hills_5_10": 0.22,
            "highlands_11_16": 0.12,
            "landmarks_17_20": 0.05,
        },
        band_targets={
            "underground_-5_-1": (5.0, 18.0),
            "ground_0": (12.0, 38.0),
            "low_raised_1_4": (15.0, 40.0),
            "hills_5_10": (12.0, 35.0),
            "highlands_11_16": (5.0, 20.0),
            "landmarks_17_20": (1.0, 9.0),
        },
    )


def _build_geographic_fields(
    *,
    width: int,
    height: int,
    seed: int,
    profile: ElevationScaleProfile,
) -> GeographicFieldResult:
    """Build continuous geographic fields before integer terracing."""
    macro_regions = _build_macro_regions(
        width=width,
        height=height,
        seed=seed,
        profile=profile,
    )
    raw_elevation: list[list[float]] = []
    raw_moisture: list[list[float]] = []
    basin_mask: list[list[float]] = []
    min_value = float("inf")
    max_value = float("-inf")
    moisture_min = float("inf")
    moisture_max = float("-inf")
    for y in range(height):
        elevation_row: list[float] = []
        moisture_row: list[float] = []
        basin_row: list[float] = []
        for x in range(width):
            nx = x / max(1, width - 1)
            ny = y / max(1, height - 1)
            warp_x = _fbm(
                nx + 31.7,
                ny - 17.3,
                seed=seed ^ 0xA11CE,
                base_frequency=profile.warp_frequency,
                octaves=3,
            )
            warp_y = _fbm(
                nx - 13.1,
                ny + 29.9,
                seed=seed ^ 0xB0B,
                base_frequency=profile.warp_frequency,
                octaves=3,
            )
            wx = nx + warp_x * profile.warp_strength
            wy = ny + warp_y * profile.warp_strength
            macro = _fbm(
                wx,
                wy,
                seed=seed ^ 0x5310,
                base_frequency=profile.macro_frequency,
                octaves=4,
            )
            detail = _fbm(
                wx,
                wy,
                seed=seed ^ 0xD37A11,
                base_frequency=profile.detail_frequency,
                octaves=3,
            )
            ridge_source = _fbm(
                wx,
                wy,
                seed=seed ^ 0xBAD5EED,
                base_frequency=profile.ridge_frequency,
                octaves=4,
            )
            ridged = 1.0 - abs(ridge_source)
            region_bias, region_basin = _macro_region_bias(
                x=float(x),
                y=float(y),
                regions=macro_regions,
            )
            value = (
                macro * profile.macro_weight
                + detail * profile.detail_weight
                + ridged * profile.ridge_weight
                + region_bias
            )
            moisture_value = _fbm(
                wx + 19.7,
                wy - 5.4,
                seed=seed ^ 0xC11A7E,
                base_frequency=_moisture_frequency(profile),
                octaves=4,
            )
            elevation_row.append(value)
            moisture_row.append(moisture_value)
            basin_row.append(region_basin)
            min_value = min(min_value, value)
            max_value = max(max_value, value)
            moisture_min = min(moisture_min, moisture_value)
            moisture_max = max(moisture_max, moisture_value)
        raw_elevation.append(elevation_row)
        raw_moisture.append(moisture_row)
        basin_mask.append(basin_row)

    elevation_scores = _normalize_grid(
        raw_elevation,
        minimum=min_value,
        maximum=max_value,
        power=profile.redistribution_power,
    )
    moisture_base = _normalize_grid(
        raw_moisture,
        minimum=moisture_min,
        maximum=moisture_max,
        power=1.0,
    )
    moisture_scores = _blend_moisture_field(
        moisture_base,
        elevation_scores=elevation_scores,
        basin_mask=basin_mask,
    )
    return GeographicFieldResult(
        elevation_scores=elevation_scores,
        moisture_scores=moisture_scores,
        macro_regions=macro_regions,
    )


def _build_macro_regions(
    *,
    width: int,
    height: int,
    seed: int,
    profile: ElevationScaleProfile,
) -> tuple[GeographicMacroRegion, ...]:
    """Create deterministic large landform regions for this map size."""
    short_side = max(1, min(width, height))
    rng = Random((seed ^ 0x6E06_1A9E) & 0xFFFF_FFFF_FFFF_FFFF)
    regions: list[GeographicMacroRegion] = []
    kinds = _macro_region_kinds(profile)
    count = _macro_region_count(profile)
    min_radius = max(profile.terrace_min_size_tiles * 1.6, short_side * 0.10)
    max_radius = max(min_radius + 1.0, min(short_side * 0.52, profile.terrace_max_size_tiles * 2.1))
    margin_x = max(2.0, width * 0.06)
    margin_y = max(2.0, height * 0.06)
    for index in range(count):
        kind = kinds[index % len(kinds)]
        radius = rng.uniform(min_radius, max_radius)
        regions.append(
            GeographicMacroRegion(
                region_id=f"geo_region_{index:03d}",
                kind=kind,
                center_x=rng.uniform(margin_x, max(margin_x, width - 1 - margin_x)),
                center_y=rng.uniform(margin_y, max(margin_y, height - 1 - margin_y)),
                radius_tiles=radius,
                strength=rng.uniform(0.75, 1.15),
                angle_degrees=rng.uniform(0.0, 180.0),
            ),
        )
    return tuple(regions)


def _macro_region_count(profile: ElevationScaleProfile) -> int:
    return {
        "tiny": 2,
        "small": 3,
        "medium": 6,
        "large": 10,
        "huge": 14,
    }.get(profile.name, 6)


def _macro_region_kinds(profile: ElevationScaleProfile) -> tuple[str, ...]:
    if profile.name == "tiny":
        return ("plain", "hill")
    if profile.name == "small":
        return ("plain", "basin", "hill")
    if profile.name == "medium":
        return ("plain", "basin", "hill", "plateau", "ridge", "hill")
    if profile.name == "large":
        return ("plain", "basin", "hill", "plateau", "ridge", "mountain", "basin", "plateau")
    return ("plain", "basin", "hill", "plateau", "ridge", "mountain", "peak", "basin", "ridge")


def _macro_region_bias(
    *,
    x: float,
    y: float,
    regions: tuple[GeographicMacroRegion, ...],
) -> tuple[float, float]:
    elevation_bias = 0.0
    basin_mask = 0.0
    for region in regions:
        influence = _macro_region_influence(x=x, y=y, region=region)
        if influence <= 0.0:
            continue
        kind_weight = _macro_region_height_weight(region.kind)
        elevation_bias += kind_weight * region.strength * influence
        if region.kind == "basin":
            basin_mask = max(basin_mask, influence * region.strength)
    return elevation_bias, min(1.0, basin_mask)


def _macro_region_influence(*, x: float, y: float, region: GeographicMacroRegion) -> float:
    dx = x - region.center_x
    dy = y - region.center_y
    if region.kind == "ridge":
        angle = region.angle_degrees * pi / 180.0
        along = dx * cos(angle) + dy * sin(angle)
        across = -dx * sin(angle) + dy * cos(angle)
        distance = hypot(along / max(1.0, region.radius_tiles * 1.55), across / max(1.0, region.radius_tiles * 0.34))
    else:
        distance = hypot(dx, dy) / max(1.0, region.radius_tiles)
    if distance >= 1.0:
        return 0.0
    if region.kind == "plateau" and distance <= 0.46:
        return 1.0
    return (1.0 - distance) ** 2.0


def _macro_region_height_weight(kind: str) -> float:
    return {
        "basin": -0.34,
        "plain": -0.09,
        "hill": 0.17,
        "plateau": 0.27,
        "ridge": 0.25,
        "mountain": 0.38,
        "peak": 0.48,
    }.get(kind, 0.0)


def _moisture_frequency(profile: ElevationScaleProfile) -> float:
    return max(0.7, profile.macro_frequency * 0.85)


def _normalize_grid(
    values: list[list[float]],
    *,
    minimum: float,
    maximum: float,
    power: float,
) -> list[list[float]]:
    value_range = maximum - minimum
    if value_range <= 1e-9:
        width = len(values[0]) if values else 0
        return [[0.5 for _ in range(width)] for _ in values]
    return [[((value - minimum) / value_range) ** power for value in row] for row in values]


def _blend_moisture_field(
    moisture_base: list[list[float]],
    *,
    elevation_scores: list[list[float]],
    basin_mask: list[list[float]],
) -> list[list[float]]:
    blended: list[list[float]] = []
    min_value = float("inf")
    max_value = float("-inf")
    for y, row in enumerate(moisture_base):
        output_row: list[float] = []
        for x, moisture in enumerate(row):
            lowland_bonus = 1.0 - elevation_scores[y][x]
            value = moisture * 0.66 + lowland_bonus * 0.24 + basin_mask[y][x] * 0.10
            output_row.append(value)
            min_value = min(min_value, value)
            max_value = max(max_value, value)
        blended.append(output_row)
    return _normalize_grid(blended, minimum=min_value, maximum=max_value, power=1.0)

def _smooth_score_grid(scores: list[list[float]], *, passes: int) -> list[list[float]]:
    smoothed = [list(row) for row in scores]
    height = len(smoothed)
    width = len(smoothed[0]) if smoothed else 0
    for _ in range(max(0, passes)):
        next_rows = [list(row) for row in smoothed]
        for y in range(height):
            for x in range(width):
                total = smoothed[y][x] * 4.0
                weight = 4.0
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        total += smoothed[ny][nx]
                        weight += 1.0
                next_rows[y][x] = total / weight
        smoothed = next_rows
    return smoothed


def _fbm(
    x: float,
    y: float,
    *,
    seed: int,
    base_frequency: float,
    octaves: int,
) -> float:
    value = 0.0
    amplitude = 1.0
    amplitude_sum = 0.0
    frequency = base_frequency
    for _ in range(octaves):
        value += _value_noise(x * frequency, y * frequency, seed=seed) * amplitude
        amplitude_sum += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    if amplitude_sum <= 0.0:
        return 0.0
    return value / amplitude_sum


def _value_noise(x: float, y: float, *, seed: int) -> float:
    x0 = floor(x)
    y0 = floor(y)
    x1 = x0 + 1
    y1 = y0 + 1
    sx = _smoothstep(x - x0)
    sy = _smoothstep(y - y0)
    n00 = _lattice_noise(x0, y0, seed)
    n10 = _lattice_noise(x1, y0, seed)
    n01 = _lattice_noise(x0, y1, seed)
    n11 = _lattice_noise(x1, y1, seed)
    ix0 = _lerp(n00, n10, sx)
    ix1 = _lerp(n01, n11, sx)
    return _lerp(ix0, ix1, sy)


def _lattice_noise(x: int, y: int, seed: int) -> float:
    value = (seed & 0xFFFF_FFFF_FFFF_FFFF) ^ ((x * 0x9E37_79B1_85EB_CA87) & 0xFFFF_FFFF_FFFF_FFFF)
    value ^= (y * 0xC2B2_AE3D_27D4_EB4F) & 0xFFFF_FFFF_FFFF_FFFF
    value ^= value >> 33
    value = (value * 0xFF51_AFD7_ED55_8CCD) & 0xFFFF_FFFF_FFFF_FFFF
    value ^= value >> 33
    value = (value * 0xC4CE_B9FE_1A85_EC53) & 0xFFFF_FFFF_FFFF_FFFF
    value ^= value >> 33
    unit = value / 0xFFFF_FFFF_FFFF_FFFF
    return unit * 2.0 - 1.0


def _smoothstep(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _quantize_scores_to_levels(
    scores: list[list[float]],
    *,
    profile: ElevationScaleProfile,
) -> list[list[int]]:
    height = len(scores)
    width = len(scores[0]) if scores else 0
    total = width * height
    if total == 0:
        return []
    flattened = sorted((value, x, y) for y, row in enumerate(scores) for x, value in enumerate(row))
    levels = [[DEFAULT_ELEVATION_LEVEL for _ in range(width)] for _ in range(height)]
    weights = _normalized_level_weights(profile)
    index = 0
    for level_index, (level, weight) in enumerate(weights):
        if level_index == len(weights) - 1:
            target_end = total
        else:
            target_end = min(total, index + int(round(total * weight)))
        for _, x, y in flattened[index:target_end]:
            levels[y][x] = level
        index = target_end
    return levels


def _normalized_level_weights(profile: ElevationScaleProfile) -> tuple[tuple[int, float], ...]:
    weighted_levels: list[tuple[int, float]] = []
    for band_name, level_range in _BAND_RANGES.items():
        band_weight = profile.band_weights.get(band_name, 0.0)
        if band_weight <= 0.0:
            continue
        levels = [level for level in level_range if profile.rare_min_level <= level <= profile.rare_max_level]
        if not levels:
            continue
        shape_weights = [_level_shape_weight(level, band_name) for level in levels]
        shape_total = sum(shape_weights)
        if shape_total <= 0.0:
            continue
        for level, shape_weight in zip(levels, shape_weights, strict=True):
            weighted_levels.append((level, band_weight * shape_weight / shape_total))
    if not weighted_levels:
        return ((DEFAULT_ELEVATION_LEVEL, 1.0),)
    total = sum(weight for _, weight in weighted_levels)
    return tuple((level, weight / total) for level, weight in weighted_levels)


def _level_shape_weight(level: int, band_name: str) -> float:
    if band_name == "underground_-5_-1":
        return 1.0 / (abs(level) ** 1.15)
    if band_name in {"hills_5_10", "highlands_11_16", "landmarks_17_20"}:
        band_start = min(_BAND_RANGES[band_name])
        return 1.0 / ((level - band_start + 1) ** 0.85)
    return 1.0


def _apply_terrain_bias(levels: list[list[int]], rows: list[str]) -> list[list[int]]:
    biased = [list(row) for row in levels]
    for y, terrain_row in enumerate(rows):
        for x, tile in enumerate(terrain_row):
            level = biased[y][x]
            if tile in {"S", "G"}:
                biased[y][x] = DEFAULT_ELEVATION_LEVEL
            elif tile == ".":
                biased[y][x] = DEFAULT_ELEVATION_LEVEL
            elif tile == "w":
                biased[y][x] = min(WATER_MAX_LEVEL, level)
    return biased


def _relax_level_deltas(
    levels: list[list[int]],
    *,
    max_delta: int,
    passes: int,
    locked_levels: dict[tuple[int, int], int] | None = None,
) -> list[list[int]]:
    """Stabilize neighboring height deltas without checkerboard oscillation.

    Earlier versions used a simultaneous min/max clamp. On sharp slopes this could
    make adjacent cells swap high/low values on every pass and produce visible
    checkerboard terraces. This pass updates in-place and moves each cell toward
    the local median envelope, so high and low outliers converge instead of
    ping-ponging.
    """
    relaxed = [list(row) for row in levels]
    height = len(relaxed)
    width = len(relaxed[0]) if relaxed else 0
    locked = locked_levels or {}
    max_delta = max(0, max_delta)

    for _ in range(max(0, passes)):
        changed = False
        for y in range(height):
            for x in range(width):
                locked_level = locked.get((x, y))
                if locked_level is not None:
                    if relaxed[y][x] != locked_level:
                        relaxed[y][x] = locked_level
                        changed = True
                    continue

                neighbors = [
                    relaxed[ny][nx]
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                    if 0 <= nx < width and 0 <= ny < height
                ]
                if not neighbors:
                    continue

                level = relaxed[y][x]
                median = _median_int(neighbors)
                lower = median - max_delta
                upper = median + max_delta
                next_level = _clamp(level, lower, upper)
                if next_level != level:
                    relaxed[y][x] = next_level
                    changed = True
        if not changed:
            break
    return relaxed


def _median_int(values: list[int]) -> int:
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return DEFAULT_ELEVATION_LEVEL
    middle = count // 2
    if count % 2 == 1:
        return ordered[middle]
    return int(round((ordered[middle - 1] + ordered[middle]) / 2.0))


def _locked_terrain_levels(levels: list[list[int]], rows: list[str]) -> dict[tuple[int, int], int]:
    locked: dict[tuple[int, int], int] = {}
    for y, terrain_row in enumerate(rows):
        if y >= len(levels):
            continue
        for x, tile in enumerate(terrain_row):
            if x >= len(levels[y]):
                continue
            if tile in {".", "S", "G", "w"}:
                locked[(x, y)] = levels[y][x]
    return locked


def _find_walkable_path(rows: list[str]) -> list[tuple[int, int]]:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    start = _find_tile(rows, "S")
    goal = _find_tile(rows, "G")
    if start is None or goal is None:
        return []
    queue = [start]
    visited = {start}
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    index = 0
    while index < len(queue):
        x, y = queue[index]
        index += 1
        if (x, y) == goal:
            break
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in visited:
                continue
            if rows[ny][nx] not in _WALKABLE_SYMBOLS:
                continue
            visited.add((nx, ny))
            parent[(nx, ny)] = (x, y)
            queue.append((nx, ny))
    if goal not in visited:
        return []
    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def _find_tile(rows: list[str], tile: str) -> tuple[int, int] | None:
    for y, row in enumerate(rows):
        x = row.find(tile)
        if x >= 0:
            return (x, y)
    return None


def _apply_ground_corridor(
    levels: list[list[int]],
    *,
    path: list[tuple[int, int]],
    profile: ElevationScaleProfile,
) -> list[list[int]]:
    rows = [list(row) for row in levels]
    height = len(rows)
    width = len(rows[0]) if rows else 0
    radius = max(0, profile.ground_corridor_radius)
    for x, y in path:
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                distance = abs(dx) + abs(dy)
                if distance > radius:
                    continue
                nx = x + dx
                ny = y + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                allowed_abs = max(0, distance)
                rows[ny][nx] = _clamp(rows[ny][nx], -allowed_abs, allowed_abs)
    return rows


def _repair_traversal_consistency(
    levels: list[list[int]],
    *,
    terrain_rows: list[str],
    explicit_cells: list[dict[str, int]],
    profile: ElevationScaleProfile,
) -> TraversalRepairResult:
    """Repair 3D traversal mismatches inside the start-connected 2D area.

    The pass does not make blocked terrain walkable. It only adjusts geographic
    levels of tiles that are already passable in the 2D terrain layer but are
    unreachable because neighboring height deltas exceed the natural step limit.
    """
    height = len(levels)
    width = len(levels[0]) if height else 0
    rows = [list(row) for row in levels]
    start = _find_tile(terrain_rows, "S") or _first_walkable_tile(terrain_rows)
    goal = _find_tile(terrain_rows, "G")
    structural_points = _explicit_cell_points(explicit_cells, width=width, height=height)
    if start is None or width == 0 or height == 0:
        return TraversalRepairResult(
            rows=rows,
            report=_traversal_repair_report(
                status="skipped",
                reason="missing_start_or_empty_map",
                passes=0,
                adjusted_tiles=0,
                two_d_reachable=set(),
                reachable_before=set(),
                reachable_after=set(),
                goal=goal,
                max_delta=profile.max_natural_delta,
            ),
        )

    two_d_reachable = _reachable_2d_tiles(
        terrain_rows,
        start=start,
        blocked_points=structural_points,
    )
    reachable_before = _reachable_3d_tiles(
        rows,
        allowed_tiles=two_d_reachable,
        start=start,
        max_delta=profile.max_natural_delta,
    )
    before_missing = two_d_reachable - reachable_before
    adjusted_points: set[tuple[int, int]] = set()
    passes = 0
    max_passes = max(1, min(width + height, profile.terrace_max_size_tiles * 4, 1024))
    status = "ok"
    for passes in range(1, max_passes + 1):
        reachable = _reachable_3d_tiles(
            rows,
            allowed_tiles=two_d_reachable,
            start=start,
            max_delta=profile.max_natural_delta,
        )
        missing = two_d_reachable - reachable
        if not missing:
            status = "ok"
            break
        changes: dict[tuple[int, int], int] = {}
        for x, y in sorted(missing, key=lambda point: (point[1], point[0])):
            repaired_level = _repaired_frontier_level(
                rows,
                x=x,
                y=y,
                reachable=reachable,
                max_delta=profile.max_natural_delta,
            )
            if repaired_level is None or repaired_level == rows[y][x]:
                continue
            changes[(x, y)] = repaired_level
        if not changes:
            status = "partial"
            break
        for (x, y), level in changes.items():
            rows[y][x] = level
            adjusted_points.add((x, y))
    else:
        status = "partial"

    reachable_after = _reachable_3d_tiles(
        rows,
        allowed_tiles=two_d_reachable,
        start=start,
        max_delta=profile.max_natural_delta,
    )
    return TraversalRepairResult(
        rows=rows,
        report=_traversal_repair_report(
            status=status,
            reason=None,
            passes=passes,
            adjusted_tiles=len(adjusted_points),
            two_d_reachable=two_d_reachable,
            reachable_before=reachable_before,
            reachable_after=reachable_after,
            goal=goal,
            max_delta=profile.max_natural_delta,
            unreachable_before_components=_component_sizes(before_missing),
            unreachable_after_components=_component_sizes(two_d_reachable - reachable_after),
        ),
    )


def _first_walkable_tile(rows: list[str]) -> tuple[int, int] | None:
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            if tile in _WALKABLE_SYMBOLS:
                return (x, y)
    return None


def _explicit_cell_points(
    explicit_cells: list[dict[str, int]],
    *,
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    points: set[tuple[int, int]] = set()
    for cell in explicit_cells:
        x = cell.get("x")
        y = cell.get("y")
        if isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height:
            points.add((x, y))
    return points


def _reachable_2d_tiles(
    rows: list[str],
    *,
    start: tuple[int, int],
    blocked_points: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    height = len(rows)
    width = len(rows[0]) if height else 0
    sx, sy = start
    if not (0 <= sx < width and 0 <= sy < height):
        return set()
    if rows[sy][sx] not in _WALKABLE_SYMBOLS or (sx, sy) in blocked_points:
        return set()
    visited = {(sx, sy)}
    queue = [(sx, sy)]
    index = 0
    while index < len(queue):
        x, y = queue[index]
        index += 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in visited or rows[ny][nx] not in _WALKABLE_SYMBOLS or (nx, ny) in blocked_points:
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))
    return visited


def _reachable_3d_tiles(
    levels: list[list[int]],
    *,
    allowed_tiles: set[tuple[int, int]],
    start: tuple[int, int],
    max_delta: int,
) -> set[tuple[int, int]]:
    if start not in allowed_tiles:
        return set()
    width = len(levels[0]) if levels else 0
    height = len(levels)
    visited = {start}
    queue = [start]
    index = 0
    while index < len(queue):
        x, y = queue[index]
        index += 1
        current_level = levels[y][x]
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in visited or (nx, ny) not in allowed_tiles:
                continue
            if abs(levels[ny][nx] - current_level) > max_delta:
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))
    return visited


def _repaired_frontier_level(
    levels: list[list[int]],
    *,
    x: int,
    y: int,
    reachable: set[tuple[int, int]],
    max_delta: int,
) -> int | None:
    current = levels[y][x]
    width = len(levels[0]) if levels else 0
    height = len(levels)
    candidates: list[int] = []
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if not (0 <= nx < width and 0 <= ny < height):
            continue
        if (nx, ny) not in reachable:
            continue
        neighbor = levels[ny][nx]
        candidates.append(_clamp(current, neighbor - max_delta, neighbor + max_delta))
    if not candidates:
        return None
    return min(candidates, key=lambda value: (abs(value - current), abs(value)))


def _component_sizes(points: set[tuple[int, int]]) -> list[int]:
    remaining = set(points)
    sizes: list[int] = []
    while remaining:
        start = remaining.pop()
        size = 1
        queue = [start]
        index = 0
        while index < len(queue):
            x, y = queue[index]
            index += 1
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                queue.append(neighbor)
                size += 1
        sizes.append(size)
    sizes.sort(reverse=True)
    return sizes


def _traversal_repair_report(
    *,
    status: str,
    reason: str | None,
    passes: int,
    adjusted_tiles: int,
    two_d_reachable: set[tuple[int, int]],
    reachable_before: set[tuple[int, int]],
    reachable_after: set[tuple[int, int]],
    goal: tuple[int, int] | None,
    max_delta: int,
    unreachable_before_components: list[int] | None = None,
    unreachable_after_components: list[int] | None = None,
) -> dict[str, Any]:
    unreachable_before = max(0, len(two_d_reachable) - len(reachable_before))
    unreachable_after = max(0, len(two_d_reachable) - len(reachable_after))
    report: dict[str, Any] = {
        "schema_version": "traversal-repair-report-v1",
        "status": status,
        "rules": {
            "scope": "start_connected_2d_walkable_component_only",
            "max_natural_delta": max_delta,
            "blocked_terrain": "preserved",
            "terrain_tiles": "not_reclassified",
        },
        "summary": {
            "two_d_reachable_tiles": len(two_d_reachable),
            "three_d_reachable_before": len(reachable_before),
            "three_d_reachable_after": len(reachable_after),
            "unreachable_before": unreachable_before,
            "unreachable_after": unreachable_after,
            "fixed_tiles": unreachable_before - unreachable_after,
            "adjusted_tiles": adjusted_tiles,
            "passes": passes,
            "goal_reachable_before": goal in reachable_before if goal is not None else False,
            "goal_reachable_after": goal in reachable_after if goal is not None else False,
        },
        "components": {
            "unreachable_before": unreachable_before_components or [],
            "unreachable_after": unreachable_after_components or [],
        },
    }
    if reason:
        report["reason"] = reason
    return report


def _explicit_elevation_cells(tactical_data: dict[str, Any]) -> list[dict[str, int]]:
    elevation = tactical_data.get("elevation")
    if not isinstance(elevation, dict):
        return []
    cells: list[dict[str, int]] = []
    for cell in elevation.get("cells", []):
        if not isinstance(cell, dict):
            continue
        x = cell.get("x")
        y = cell.get("y")
        level = cell.get("level")
        if isinstance(x, int) and isinstance(y, int) and isinstance(level, int):
            cells.append({"x": x, "y": y, "level": _clamp(level, MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL)})
    return cells


def _apply_explicit_elevation_cells(
    levels: list[list[int]],
    *,
    explicit_cells: Iterable[dict[str, int]],
) -> list[list[int]]:
    rows = [list(row) for row in levels]
    height = len(rows)
    width = len(rows[0]) if rows else 0
    for cell in explicit_cells:
        x = cell["x"]
        y = cell["y"]
        if 0 <= x < width and 0 <= y < height:
            rows[y][x] = cell["level"]
    return rows


def _build_generation_report(
    levels: list[list[int]],
    *,
    geographic_levels: list[list[int]],
    terrain_rows: list[str],
    explicit_cells: list[dict[str, int]],
    seed: int,
    corridor_path: list[tuple[int, int]],
    profile: ElevationScaleProfile,
    geographic_fields: GeographicFieldResult,
    traversal_repair_report: dict[str, Any],
) -> dict[str, Any]:
    height = len(levels)
    width = len(levels[0]) if levels else 0
    total = width * height
    counts = Counter(level for row in levels for level in row)
    bands = _band_counts(counts, profile=profile)
    return {
        "schema_version": "next-gen-elevation-report-v2",
        "generator": _generator_info(seed=seed, profile=profile),
        "dimensions": {"width": width, "height": height, "tiles": total},
        "profile": _profile_report(profile),
        "summary": {
            "min_level": min(counts) if counts else 0,
            "max_level": max(counts) if counts else 0,
            "levels_present": [str(level) for level in sorted(counts)],
            "level_counts": {str(level): counts[level] for level in sorted(counts)},
            "level_zero_percent": _percent(counts.get(0, 0), total),
            "non_zero_percent": _percent(total - counts.get(0, 0), total),
        },
        "bands": bands,
        "adjacent_delta": _adjacent_delta_report(levels),
        "traversal_repair": traversal_repair_report,
        "geography": _geography_report(
            geographic_levels,
            runtime_levels=levels,
            terrain_rows=terrain_rows,
            explicit_cells=explicit_cells,
            geographic_fields=geographic_fields,
        ),
        "terrain_bias": {
            "start_goal_forced_to_level": 0,
            "start_goal_ground_corridor_tiles": len(corridor_path),
            "ground_corridor_radius": profile.ground_corridor_radius,
            "road_clamp": [ROAD_MIN_LEVEL, ROAD_MAX_LEVEL],
            "water_max_level": WATER_MAX_LEVEL,
            "road_tiles": sum(row.count(".") for row in terrain_rows),
            "water_tiles": sum(row.count("w") for row in terrain_rows),
        },
    }


def _generator_info(*, seed: int, profile: ElevationScaleProfile) -> dict[str, Any]:
    return {
        "name": "size_aware_red_blob_geography_v3",
        "seed": seed,
        "range": [MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL],
        "algorithm": "size_aware_macro_regions_fbm_moisture_redistribution_terraces_stable_relax_traversal_repair",
        "redistribution": "profile_weighted_percentile_quantization",
        "smoothing_passes": profile.score_smoothing_passes,
        "level_relax_passes": profile.level_relax_passes,
        "max_natural_delta": profile.max_natural_delta,
        "profile": profile.name,
    }


def _profile_report(profile: ElevationScaleProfile) -> dict[str, Any]:
    return {
        "map_class": profile.name,
        "format_range": [MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL],
        "active_range": [profile.active_min_level, profile.active_max_level],
        "rare_range": [profile.rare_min_level, profile.rare_max_level],
        "terrace_target_size_tiles": [profile.terrace_min_size_tiles, profile.terrace_max_size_tiles],
        "macro_frequency": profile.macro_frequency,
        "detail_frequency": profile.detail_frequency,
        "ridge_frequency": profile.ridge_frequency,
        "warp_strength": profile.warp_strength,
        "redistribution_power": profile.redistribution_power,
        "score_smoothing_passes": profile.score_smoothing_passes,
        "level_relax_passes": profile.level_relax_passes,
        "max_natural_delta": profile.max_natural_delta,
        "ground_corridor_radius": profile.ground_corridor_radius,
        "band_targets_percent": {
            key: [target[0], target[1]] for key, target in profile.band_targets.items()
        },
    }


def _band_counts(counts: Counter[int], *, profile: ElevationScaleProfile) -> dict[str, dict[str, Any]]:
    total = sum(counts.values())
    output: dict[str, dict[str, Any]] = {}
    for name, levels in _BAND_RANGES.items():
        count = sum(counts.get(level, 0) for level in levels)
        target = profile.band_targets.get(name)
        item: dict[str, Any] = {
            "count": count,
            "percent": _percent(count, total),
        }
        if target is not None:
            item["target_percent"] = [target[0], target[1]]
            item["status"] = "ok" if target[0] <= item["percent"] <= target[1] else "warn"
        output[name] = item
    return output


def _adjacent_delta_report(levels: list[list[int]]) -> dict[str, Any]:
    delta_counts: Counter[int] = Counter()
    max_delta = 0
    for y, row in enumerate(levels):
        for x, level in enumerate(row):
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if 0 <= ny < len(levels) and 0 <= nx < len(levels[ny]):
                    delta = abs(level - levels[ny][nx])
                    delta_counts[delta] += 1
                    max_delta = max(max_delta, delta)
    total = sum(delta_counts.values())
    return {
        "max_delta": max_delta,
        "delta_counts": {str(delta): delta_counts[delta] for delta in sorted(delta_counts)},
        "delta_0_percent": _percent(delta_counts.get(0, 0), total),
        "delta_1_percent": _percent(delta_counts.get(1, 0), total),
        "delta_gt_1_percent": _percent(sum(count for delta, count in delta_counts.items() if delta > 1), total),
    }



def _geography_report(
    levels: list[list[int]],
    *,
    runtime_levels: list[list[int]],
    terrain_rows: list[str],
    explicit_cells: list[dict[str, int]],
    geographic_fields: GeographicFieldResult,
) -> dict[str, Any]:
    slope_rows = _slope_rows(levels)
    source_rows = _elevation_source_rows(
        terrain_rows=terrain_rows,
        explicit_cells=explicit_cells,
        width=len(levels[0]) if levels else 0,
        height=len(levels),
    )
    mask_rows = _geographic_mask_rows(
        levels,
        moisture_rows=geographic_fields.moisture_scores,
        slope_rows=slope_rows,
    )
    water_lowland_rows = _water_lowland_rows(
        levels,
        runtime_levels=runtime_levels,
        terrain_rows=terrain_rows,
        source_rows=source_rows,
        moisture_rows=geographic_fields.moisture_scores,
        mask_rows=mask_rows,
    )
    mask_counts = Counter(mask for row in mask_rows for mask in row)
    source_counts = Counter(source for row in source_rows for source in row)
    total = sum(mask_counts.values())
    return {
        "schema_version": "geography-report-v1",
        "macro_regions": {
            "count": len(geographic_fields.macro_regions),
            "items": [
                {
                    "id": region.region_id,
                    "kind": region.kind,
                    "center": {
                        "x": round(region.center_x, 3),
                        "y": round(region.center_y, 3),
                    },
                    "radius_tiles": round(region.radius_tiles, 3),
                    "strength": round(region.strength, 3),
                    "angle_degrees": round(region.angle_degrees, 3),
                }
                for region in geographic_fields.macro_regions
            ],
        },
        "masks": {
            name: _metric_count(count, total)
            for name, count in sorted(mask_counts.items())
        },
        "sources": {
            _elevation_source_name(name): _metric_count(count, total)
            for name, count in sorted(source_counts.items())
        },
        "moisture": _moisture_report(geographic_fields.moisture_scores),
        "standing_water": _standing_water_report(water_lowland_rows),
        "slope": _slope_report(slope_rows),
        "grids": {
            "geographic_level_grid": {"rows": levels},
            "runtime_level_grid": {"rows": runtime_levels},
            "source_grid": {
                "legend": _elevation_source_legend(),
                "rows": ["".join(row) for row in source_rows],
            },
            "mask_grid": {
                "legend": _geographic_mask_legend(),
                "rows": ["".join(_geographic_mask_code(mask) for mask in row) for row in mask_rows],
            },
            "moisture_grid": {
                "scale": 1000,
                "rows": [
                    [int(round(value * 1000.0)) for value in row]
                    for row in geographic_fields.moisture_scores
                ],
            },
            "slope_grid": {"rows": slope_rows},
            "water_lowland_grid": {
                "legend": _water_lowland_legend(),
                "rows": ["".join(row) for row in water_lowland_rows],
            },
        },
    }


def _water_lowland_rows(
    levels: list[list[int]],
    *,
    runtime_levels: list[list[int]],
    terrain_rows: list[str],
    source_rows: list[list[str]],
    moisture_rows: list[list[float]],
    mask_rows: list[list[str]],
) -> list[list[str]]:
    rows: list[list[str]] = []
    for y, level_row in enumerate(levels):
        output_row: list[str] = []
        for x, level in enumerate(level_row):
            runtime_level = runtime_levels[y][x] if y < len(runtime_levels) and x < len(runtime_levels[y]) else level
            terrain_tile = terrain_rows[y][x] if y < len(terrain_rows) and x < len(terrain_rows[y]) else ""
            source = source_rows[y][x] if y < len(source_rows) and x < len(source_rows[y]) else "G"
            moisture = moisture_rows[y][x] if y < len(moisture_rows) and x < len(moisture_rows[y]) else 0.5
            mask = mask_rows[y][x] if y < len(mask_rows) and x < len(mask_rows[y]) else "plains"
            output_row.append(
                _water_lowland_code(
                    geographic_level=level,
                    runtime_level=runtime_level,
                    terrain_tile=terrain_tile,
                    source=source,
                    moisture=moisture,
                    geographic_mask=mask,
                ),
            )
        rows.append(output_row)
    return rows


def _water_lowland_code(
    *,
    geographic_level: int,
    runtime_level: int,
    terrain_tile: str,
    source: str,
    moisture: float,
    geographic_mask: str,
) -> str:
    if source == "S":
        return "X"
    if source == "W" or terrain_tile == "w":
        return "B" if min(geographic_level, runtime_level) <= -2 else "S"
    if geographic_level < 0:
        return "W" if moisture >= 0.68 or geographic_mask == "basins" else "L"
    if geographic_level <= 1 and moisture >= 0.82:
        return "W"
    return "D"


def _standing_water_report(rows: list[list[str]]) -> dict[str, Any]:
    counts = Counter(code for row in rows for code in row)
    total = sum(counts.values())
    return {
        "schema_version": "standing-water-report-v1",
        "flow_model": "none",
        "rivers": "disabled",
        "legend": _water_lowland_legend(),
        "categories": {
            _water_lowland_name(code): _metric_count(counts.get(code, 0), total)
            for code in ("B", "S", "W", "L", "D", "X")
        },
        "water_total": _metric_count(counts.get("B", 0) + counts.get("S", 0), total),
        "wet_lowland_total": _metric_count(counts.get("W", 0), total),
        "dry_lowland_total": _metric_count(counts.get("L", 0), total),
        "structural_total": _metric_count(counts.get("X", 0), total),
    }


def _water_lowland_legend() -> dict[str, str]:
    return {
        "B": "deep_water",
        "S": "shallow_water",
        "W": "wet_lowland",
        "L": "dry_lowland",
        "D": "dry_land",
        "X": "structural_depth",
    }


def _water_lowland_name(code: str) -> str:
    return _water_lowland_legend().get(code, "unknown")


def _elevation_source_rows(
    *,
    terrain_rows: list[str],
    explicit_cells: list[dict[str, int]],
    width: int,
    height: int,
) -> list[list[str]]:
    rows = [["G" for _ in range(width)] for _ in range(height)]
    for y, terrain_row in enumerate(terrain_rows[:height]):
        for x, tile in enumerate(terrain_row[:width]):
            if tile == "w":
                rows[y][x] = "W"
    for cell in explicit_cells:
        x = cell.get("x")
        y = cell.get("y")
        if isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height:
            rows[y][x] = "S"
    return rows


def _elevation_source_legend() -> dict[str, str]:
    return {
        "G": "geography",
        "W": "water",
        "S": "structural_depth",
    }


def _elevation_source_name(code: str) -> str:
    return _elevation_source_legend().get(code, "unknown")


def _slope_rows(levels: list[list[int]]) -> list[list[int]]:
    height = len(levels)
    width = len(levels[0]) if levels else 0
    output = [[0 for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(levels):
        for x, level in enumerate(row):
            max_delta = 0
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    max_delta = max(max_delta, abs(level - levels[ny][nx]))
            output[y][x] = max_delta
    return output


def _geographic_mask_rows(
    levels: list[list[int]],
    *,
    moisture_rows: list[list[float]],
    slope_rows: list[list[int]],
) -> list[list[str]]:
    output: list[list[str]] = []
    for y, row in enumerate(levels):
        output_row: list[str] = []
        for x, level in enumerate(row):
            moisture = moisture_rows[y][x] if y < len(moisture_rows) and x < len(moisture_rows[y]) else 0.5
            slope = slope_rows[y][x] if y < len(slope_rows) and x < len(slope_rows[y]) else 0
            output_row.append(_geographic_mask(level=level, moisture=moisture, slope=slope))
        output.append(output_row)
    return output


def _geographic_mask(*, level: int, moisture: float, slope: int) -> str:
    if level >= 17:
        return "peaks"
    if level >= 11:
        return "ridges" if slope >= 2 else "mountains"
    if level >= 7:
        return "ridges" if slope >= 2 else "plateaus"
    if level >= 3:
        return "hills"
    if level < 0:
        return "basins" if level <= -2 or moisture >= 0.68 else "lowlands"
    if moisture >= 0.78 and level <= 1:
        return "basins"
    return "plains"


def _geographic_mask_legend() -> dict[str, str]:
    return {
        "B": "basins",
        "L": "lowlands",
        "P": "plains",
        "H": "hills",
        "T": "plateaus",
        "R": "ridges",
        "M": "mountains",
        "K": "peaks",
    }


def _geographic_mask_code(mask: str) -> str:
    return {
        "basins": "B",
        "lowlands": "L",
        "plains": "P",
        "hills": "H",
        "plateaus": "T",
        "ridges": "R",
        "mountains": "M",
        "peaks": "K",
    }.get(mask, "?")


def _moisture_report(moisture_rows: list[list[float]]) -> dict[str, Any]:
    values = [value for row in moisture_rows for value in row]
    total = len(values)
    dry = sum(1 for value in values if value < 0.33)
    balanced = sum(1 for value in values if 0.33 <= value < 0.66)
    wet = total - dry - balanced
    if not values:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "bands": {}}
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "avg": round(sum(values) / total, 4),
        "bands": {
            "dry": _metric_count(dry, total),
            "balanced": _metric_count(balanced, total),
            "wet": _metric_count(wet, total),
        },
    }


def _slope_report(slope_rows: list[list[int]]) -> dict[str, Any]:
    values = [value for row in slope_rows for value in row]
    total = len(values)
    flat = sum(1 for value in values if value == 0)
    gentle = sum(1 for value in values if value == 1)
    steep = sum(1 for value in values if value == 2)
    cliff = sum(1 for value in values if value >= 3)
    return {
        "max_delta": max(values) if values else 0,
        "bands": {
            "flat": _metric_count(flat, total),
            "gentle": _metric_count(gentle, total),
            "steep": _metric_count(steep, total),
            "cliff": _metric_count(cliff, total),
        },
    }


def _metric_count(count: int, total: int) -> dict[str, Any]:
    return {"count": count, "percent": _percent(count, total)}

def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count * 100.0 / total, 3)
