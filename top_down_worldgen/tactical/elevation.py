from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from math import cos, floor, hypot, pi, sin
from random import Random
from typing import Any, Iterable

from .geography_draft import (
    GeographyDraft,
    GeographyDraftRegion,
    NaturalGeographyModel,
)

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
    style_name: str = "normal"


@dataclass(frozen=True, slots=True)
class PolygonalRegionSample:
    """Soft sample from polygon-inspired macro region control map."""

    dominant_index: int
    secondary_index: int | None
    dominant_kind: str
    elevation_score: float
    moisture_bias: float
    roughness: float
    basin_mask: float
    boundary_softness: float


@dataclass(frozen=True, slots=True)
class ElevationGenerationResult:
    """Result of deterministic next-generation elevation generation."""

    rows: list[list[int]]
    report: dict[str, Any]




@dataclass(frozen=True, slots=True)
class RegionTransitionShapingResult:
    """Result of macro-region boundary elevation shaping."""

    rows: list[list[int]]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MainRouteAlignmentResult:
    """Result of semantic main-route elevation alignment."""

    rows: list[list[int]]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TraversalRepairResult:
    """Result of the geography-level 3D traversal repair pass."""

    rows: list[list[int]]
    report: dict[str, Any]


def build_geography_draft(
    *,
    width: int,
    height: int,
    seed: int,
    elevation_style: str = "normal",
) -> GeographyDraft:
    """Build deterministic geography context before terrain generation.

    Args:
        width: Map width in tiles.
        height: Map height in tiles.
        seed: Resolved deterministic world seed.
        elevation_style: User-facing elevation style preset name.

    Returns:
        Continuous elevation, moisture, and macro-region fields.

    Raises:
        ValueError: If either map dimension is negative.
    """
    if width < 0 or height < 0:
        raise ValueError("Map dimensions must be non-negative")
    profile = _profile_for_size(
        width=width,
        height=height,
        elevation_style=elevation_style,
    )
    if width == 0 or height == 0:
        return GeographyDraft(
            width=width,
            height=height,
            seed=seed,
            elevation_style=profile.style_name,
            elevation_scores=[],
            moisture_scores=[],
            macro_regions=(),
            dominant_region_rows=[],
            region_edges=(),
        )
    return _build_geographic_fields(
        width=width,
        height=height,
        seed=seed,
        profile=profile,
    )


def build_natural_geography_model(
    *,
    width: int,
    height: int,
    seed: int,
    elevation_style: str = "normal",
    geography_draft: GeographyDraft | None = None,
) -> NaturalGeographyModel:
    """Build final natural elevation before terrain generation.

    Args:
        width: Map width in tiles.
        height: Map height in tiles.
        seed: Resolved deterministic world seed.
        elevation_style: User-facing elevation style preset name.
        geography_draft: Optional prebuilt continuous geography context.

    Returns:
        Natural integer elevation and slope grids for terrain consumers.
    """
    if width < 0 or height < 0:
        raise ValueError("Map dimensions must be non-negative")
    profile = _profile_for_size(
        width=width,
        height=height,
        elevation_style=elevation_style,
    )
    draft = geography_draft or build_geography_draft(
        width=width,
        height=height,
        seed=seed,
        elevation_style=profile.style_name,
    )
    draft.validate_for(
        width=width,
        height=height,
        seed=seed,
        elevation_style=profile.style_name,
    )
    levels = _build_natural_level_rows(draft, profile=profile)
    return NaturalGeographyModel(
        width=width,
        height=height,
        seed=seed,
        elevation_style=profile.style_name,
        elevation_rows=levels,
        slope_rows=_integer_slope_rows(levels),
        draft=draft,
    )


def attach_next_gen_elevation(
    tactical_data: dict[str, Any],
    *,
    rows: list[str],
    seed: int,
    elevation_style: str = "normal",
    geography_draft: GeographyDraft | None = None,
    natural_geography: NaturalGeographyModel | None = None,
) -> dict[str, Any]:
    """Attach a full-map procedural elevation layer to tactical data.

    Args:
        tactical_data: Runtime tactical data produced by the tactical pipeline.
        rows: ASCII terrain rows.
        seed: Resolved deterministic world seed.
        elevation_style: User-facing elevation style preset name.
        geography_draft: Optional prebuilt geography context for this map.
        natural_geography: Optional final natural geography built before terrain.

    Returns:
        Copy of tactical data with a sparse elevation cell list representing
        non-default levels from the generated full height grid.
    """
    result = generate_next_gen_elevation(
        rows=rows,
        seed=seed,
        tactical_data=tactical_data,
        elevation_style=elevation_style,
        geography_draft=geography_draft,
        natural_geography=natural_geography,
    )
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
    elevation_style: str = "normal",
    geography_draft: GeographyDraft | None = None,
    natural_geography: NaturalGeographyModel | None = None,
) -> ElevationGenerationResult:
    """Generate a size-aware Red Blob style terraced height map.

    Args:
        rows: ASCII terrain rows.
        seed: Resolved deterministic world seed.
        tactical_data: Optional runtime tactical data with object-derived elevation cells.
        elevation_style: User-facing elevation style preset name.
        geography_draft: Optional prebuilt geography context for this map.
        natural_geography: Optional final natural geography built before terrain.

    Returns:
        Generated integer height rows and a JSON-serializable report.
    """
    height = len(rows)
    width = len(rows[0]) if rows else 0
    if width == 0 or height == 0:
        profile = _profile_for_size(width=width, height=height, elevation_style=elevation_style)
        report = _empty_report(width=width, height=height, seed=seed, profile=profile)
        return ElevationGenerationResult(rows=[], report=report)

    profile = _profile_for_size(width=width, height=height, elevation_style=elevation_style)
    if natural_geography is not None:
        natural_geography.validate_for(
            width=width,
            height=height,
            seed=seed,
            elevation_style=profile.style_name,
        )
        geographic_fields = natural_geography.draft
        levels = [list(row) for row in natural_geography.elevation_rows]
        verification_rows = _build_natural_level_rows(geographic_fields, profile=profile)
        if verification_rows != levels:
            raise RuntimeError("Early natural geography verification failed")
        early_geography_verification = {
            "enabled": True,
            "matched": True,
            "tiles_checked": width * height,
        }
    else:
        if geography_draft is None:
            geographic_fields = _build_geographic_fields(
                width=width,
                height=height,
                seed=seed,
                profile=profile,
            )
        else:
            geography_draft.validate_for(
                width=width,
                height=height,
                seed=seed,
                elevation_style=profile.style_name,
            )
            geographic_fields = geography_draft
        levels = _build_natural_level_rows(geographic_fields, profile=profile)
        early_geography_verification = {
            "enabled": False,
            "matched": None,
            "tiles_checked": 0,
        }
    levels = _apply_terrain_bias(levels, rows)
    locked_levels = _locked_terrain_levels(levels, rows)
    levels = _relax_level_deltas(
        levels,
        max_delta=profile.max_natural_delta,
        passes=profile.level_relax_passes,
        locked_levels=locked_levels,
    )
    levels = _apply_terrain_bias(levels, rows)
    explicit_cells = _explicit_elevation_cells(tactical_data or {})
    transition_result = _shape_region_transition_belts(
        levels,
        region_rows=geographic_fields.dominant_region_rows,
        terrain_rows=rows,
        profile=profile,
    )
    levels = transition_result.rows
    locked_levels = _locked_terrain_levels(levels, rows)
    path = _find_walkable_path(rows)
    route_result = _align_main_route_elevation(
        levels,
        terrain_rows=rows,
        tactical_data=tactical_data or {},
        explicit_cells=explicit_cells,
        profile=profile,
        fallback_path=path,
    )
    levels = route_result.rows
    locked_levels.update(_locked_terrain_levels(levels, rows))
    levels = _relax_level_deltas(
        levels,
        max_delta=profile.max_natural_delta,
        passes=max(1, profile.level_relax_passes // 2),
        locked_levels=locked_levels,
    )
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
    runtime_route_result = _align_main_route_elevation(
        levels,
        terrain_rows=rows,
        tactical_data=tactical_data or {},
        explicit_cells=explicit_cells,
        profile=profile,
        fallback_path=path,
    )
    levels = runtime_route_result.rows
    levels = _clamp_levels_to_profile_range(levels, profile=profile)
    report = _build_generation_report(
        levels,
        geographic_levels=geographic_levels,
        terrain_rows=rows,
        explicit_cells=explicit_cells,
        seed=seed,
        corridor_path=path,
        profile=profile,
        geographic_fields=geographic_fields,
        transition_report=transition_result.report,
        route_alignment_report=runtime_route_result.report,
        traversal_repair_report=traversal_repair.report,
    )
    report["early_geography_verification"] = early_geography_verification
    return ElevationGenerationResult(rows=levels, report=report)


def _build_natural_level_rows(
    geography: GeographyDraft,
    *,
    profile: ElevationScaleProfile,
) -> list[list[int]]:
    """Build terrain-independent integer natural elevation rows."""
    scores = _smooth_score_grid(
        geography.elevation_scores,
        passes=profile.score_smoothing_passes,
    )
    levels = _quantize_scores_to_levels(scores, profile=profile)
    return _relax_level_deltas(
        levels,
        max_delta=profile.max_natural_delta,
        passes=profile.level_relax_passes,
        locked_levels={},
    )


def _integer_slope_rows(rows: list[list[int]]) -> list[list[int]]:
    """Return maximum cardinal elevation delta for each tile."""
    height = len(rows)
    width = len(rows[0]) if rows else 0
    output = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            current = rows[y][x]
            maximum = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx = x + dx
                ny = y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    maximum = max(maximum, abs(current - rows[ny][nx]))
            output[y][x] = maximum
    return output


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


def _profile_for_size(
    *,
    width: int,
    height: int,
    elevation_style: str = "normal",
) -> ElevationScaleProfile:
    """Return a size profile adjusted by the requested elevation style."""
    base_profile = _base_profile_for_size(width=width, height=height)
    return _apply_elevation_style(base_profile, style=elevation_style)


def _apply_elevation_style(profile: ElevationScaleProfile, *, style: str) -> ElevationScaleProfile:
    """Apply user-facing terrain style parameters to a size profile."""
    style_name = _sanitize_elevation_style(style)
    if style_name == "normal":
        return replace(profile, style_name=style_name)
    if style_name == "super_flatland":
        return replace(
            profile,
            style_name=style_name,
            active_min_level=-1,
            active_max_level=1,
            rare_min_level=-1,
            rare_max_level=1,
            terrace_min_size_tiles=10,
            terrace_max_size_tiles=24,
            macro_frequency=profile.macro_frequency * 0.98,
            detail_frequency=profile.detail_frequency * 0.74,
            ridge_frequency=profile.ridge_frequency * 0.20,
            warp_strength=profile.warp_strength * 0.28,
            macro_weight=max(0.64, profile.macro_weight + 0.02),
            detail_weight=profile.detail_weight * 0.42,
            ridge_weight=profile.ridge_weight * 0.04,
            redistribution_power=max(0.82, profile.redistribution_power * 0.70),
            score_smoothing_passes=profile.score_smoothing_passes + 3,
            level_relax_passes=profile.level_relax_passes + 8,
            ground_corridor_radius=profile.ground_corridor_radius + 3,
            band_weights={
                "underground_-5_-1": 0.30,
                "ground_0": 0.46,
                "low_raised_1_4": 0.24,
                "hills_5_10": 0.0,
                "highlands_11_16": 0.0,
                "landmarks_17_20": 0.0,
            },
            band_targets={
                "underground_-5_-1": (20.0, 42.0),
                "ground_0": (34.0, 58.0),
                "low_raised_1_4": (12.0, 32.0),
                "hills_5_10": (0.0, 0.0),
                "highlands_11_16": (0.0, 0.0),
                "landmarks_17_20": (0.0, 0.0),
            },
        )
    if style_name == "flatland":
        return replace(
            profile,
            style_name=style_name,
            active_min_level=MIN_ELEVATION_LEVEL,
            active_max_level=4,
            rare_min_level=MIN_ELEVATION_LEVEL,
            rare_max_level=4,
            terrace_min_size_tiles=8,
            terrace_max_size_tiles=22,
            macro_frequency=profile.macro_frequency * 1.18,
            detail_frequency=profile.detail_frequency * 1.38,
            ridge_frequency=profile.ridge_frequency * 0.58,
            warp_strength=profile.warp_strength * 0.62,
            macro_weight=max(0.56, profile.macro_weight - 0.08),
            detail_weight=profile.detail_weight * 0.82,
            ridge_weight=profile.ridge_weight * 0.18,
            redistribution_power=max(0.82, profile.redistribution_power * 0.78),
            score_smoothing_passes=profile.score_smoothing_passes + 1,
            level_relax_passes=profile.level_relax_passes + 5,
            ground_corridor_radius=profile.ground_corridor_radius + 2,
            band_weights={
                "underground_-5_-1": 0.28,
                "ground_0": 0.34,
                "low_raised_1_4": 0.38,
                "hills_5_10": 0.0,
                "highlands_11_16": 0.0,
                "landmarks_17_20": 0.0,
            },
            band_targets={
                "underground_-5_-1": (14.0, 36.0),
                "ground_0": (22.0, 48.0),
                "low_raised_1_4": (22.0, 48.0),
                "hills_5_10": (0.0, 0.0),
                "highlands_11_16": (0.0, 0.0),
                "landmarks_17_20": (0.0, 0.0),
            },
        )
    if style_name == "rolling_hills":
        return replace(
            profile,
            style_name=style_name,
            active_min_level=MIN_ELEVATION_LEVEL,
            active_max_level=10,
            rare_min_level=MIN_ELEVATION_LEVEL,
            rare_max_level=10,
            terrace_min_size_tiles=max(profile.terrace_min_size_tiles, 18),
            terrace_max_size_tiles=max(profile.terrace_max_size_tiles, 44),
            macro_frequency=profile.macro_frequency * 0.96,
            detail_frequency=profile.detail_frequency * 0.92,
            ridge_frequency=profile.ridge_frequency * 0.72,
            warp_strength=profile.warp_strength * 0.82,
            macro_weight=profile.macro_weight + 0.02,
            detail_weight=profile.detail_weight * 0.86,
            ridge_weight=profile.ridge_weight * 0.58,
            redistribution_power=max(0.95, profile.redistribution_power * 0.94),
            score_smoothing_passes=profile.score_smoothing_passes + 1,
            level_relax_passes=profile.level_relax_passes + 3,
            ground_corridor_radius=profile.ground_corridor_radius + 1,
            band_weights={
                "underground_-5_-1": 0.12,
                "ground_0": 0.30,
                "low_raised_1_4": 0.33,
                "hills_5_10": 0.25,
                "highlands_11_16": 0.0,
                "landmarks_17_20": 0.0,
            },
            band_targets={
                "underground_-5_-1": (4.0, 16.0),
                "ground_0": (20.0, 44.0),
                "low_raised_1_4": (22.0, 46.0),
                "hills_5_10": (12.0, 32.0),
                "highlands_11_16": (0.0, 0.0),
                "landmarks_17_20": (0.0, 0.0),
            },
        )
    if style_name == "rugged":
        return replace(
            profile,
            style_name=style_name,
            active_min_level=-5,
            active_max_level=18,
            rare_min_level=MIN_ELEVATION_LEVEL,
            rare_max_level=MAX_ELEVATION_LEVEL,
            terrace_min_size_tiles=max(8, min(profile.terrace_min_size_tiles, 12)),
            terrace_max_size_tiles=max(24, min(profile.terrace_max_size_tiles, 32)),
            macro_frequency=profile.macro_frequency * 1.08,
            detail_frequency=profile.detail_frequency * 1.20,
            ridge_frequency=profile.ridge_frequency * 1.22,
            warp_strength=profile.warp_strength * 1.18,
            macro_weight=max(0.50, profile.macro_weight - 0.04),
            detail_weight=profile.detail_weight * 1.25,
            ridge_weight=profile.ridge_weight * 1.45,
            redistribution_power=profile.redistribution_power * 1.05,
            score_smoothing_passes=max(1, profile.score_smoothing_passes - 1),
            level_relax_passes=max(4, profile.level_relax_passes - 2),
            band_weights={
                "underground_-5_-1": 0.10,
                "ground_0": 0.28,
                "low_raised_1_4": 0.27,
                "hills_5_10": 0.22,
                "highlands_11_16": 0.10,
                "landmarks_17_20": 0.03,
            },
            band_targets={
                "underground_-5_-1": (4.0, 15.0),
                "ground_0": (18.0, 45.0),
                "low_raised_1_4": (16.0, 40.0),
                "hills_5_10": (10.0, 30.0),
                "highlands_11_16": (3.0, 16.0),
                "landmarks_17_20": (0.5, 6.0),
            },
        )
    if style_name == "mountainous":
        return replace(
            profile,
            style_name=style_name,
            active_min_level=MIN_ELEVATION_LEVEL,
            active_max_level=MAX_ELEVATION_LEVEL,
            rare_min_level=MIN_ELEVATION_LEVEL,
            rare_max_level=MAX_ELEVATION_LEVEL,
            terrace_min_size_tiles=8,
            terrace_max_size_tiles=26,
            macro_frequency=profile.macro_frequency * 1.20,
            detail_frequency=profile.detail_frequency * 1.36,
            ridge_frequency=profile.ridge_frequency * 1.62,
            warp_strength=profile.warp_strength * 1.16,
            macro_weight=max(0.58, profile.macro_weight - 0.05),
            detail_weight=profile.detail_weight * 1.22,
            ridge_weight=profile.ridge_weight * 1.88,
            redistribution_power=profile.redistribution_power * 1.08,
            score_smoothing_passes=max(1, profile.score_smoothing_passes - 1),
            level_relax_passes=profile.level_relax_passes + 2,
            ground_corridor_radius=profile.ground_corridor_radius + 1,
            band_weights={
                "underground_-5_-1": 0.09,
                "ground_0": 0.16,
                "low_raised_1_4": 0.18,
                "hills_5_10": 0.26,
                "highlands_11_16": 0.22,
                "landmarks_17_20": 0.09,
            },
            band_targets={
                "underground_-5_-1": (3.0, 15.0),
                "ground_0": (8.0, 30.0),
                "low_raised_1_4": (10.0, 32.0),
                "hills_5_10": (14.0, 38.0),
                "highlands_11_16": (8.0, 28.0),
                "landmarks_17_20": (2.0, 14.0),
            },
        )
    return replace(
        profile,
        style_name=style_name,
        active_min_level=MIN_ELEVATION_LEVEL,
        active_max_level=MAX_ELEVATION_LEVEL,
        rare_min_level=MIN_ELEVATION_LEVEL,
        rare_max_level=MAX_ELEVATION_LEVEL,
        terrace_min_size_tiles=max(profile.terrace_max_size_tiles, 44),
        terrace_max_size_tiles=max(profile.terrace_max_size_tiles * 2, 96),
        macro_frequency=max(0.45, profile.macro_frequency * 0.56),
        detail_frequency=max(0.90, profile.detail_frequency * 0.42),
        ridge_frequency=max(0.85, profile.ridge_frequency * 0.52),
        warp_strength=profile.warp_strength * 0.58,
        macro_weight=profile.macro_weight + 0.12,
        detail_weight=profile.detail_weight * 0.36,
        ridge_weight=profile.ridge_weight * 0.62,
        redistribution_power=profile.redistribution_power * 1.02,
        score_smoothing_passes=profile.score_smoothing_passes + 3,
        level_relax_passes=profile.level_relax_passes + 4,
        ground_corridor_radius=profile.ground_corridor_radius + 2,
        band_weights={
            "underground_-5_-1": 0.08,
            "ground_0": 0.20,
            "low_raised_1_4": 0.21,
            "hills_5_10": 0.20,
            "highlands_11_16": 0.20,
            "landmarks_17_20": 0.11,
        },
        band_targets={
            "underground_-5_-1": (3.0, 13.0),
            "ground_0": (12.0, 34.0),
            "low_raised_1_4": (12.0, 34.0),
            "hills_5_10": (10.0, 32.0),
            "highlands_11_16": (8.0, 28.0),
            "landmarks_17_20": (2.0, 14.0),
        },
    )


def _style_wave_frequency(profile: ElevationScaleProfile) -> str:
    """Return a user-facing style wave frequency class."""
    return {
        "super_flatland": "soft",
        "flatland": "frequent",
        "rolling_hills": "medium",
        "rugged": "frequent",
        "mountainous": "frequent",
        "plateau": "rare",
    }.get(profile.style_name, "medium")


def _style_character(profile: ElevationScaleProfile) -> str:
    """Return a short user-facing style character string."""
    return {
        "super_flatland": "nearly flat -1..1 micro relief",
        "flatland": "low soft frequent undulation",
        "rolling_hills": "main playable medium hills",
        "rugged": "rough broken terrain",
        "mountainous": "frequent playable mountains",
        "plateau": "large plateaus and long slopes",
    }.get(profile.style_name, "balanced terrain")

def _sanitize_elevation_style(style: str) -> str:
    """Return a supported elevation style name."""
    value = str(style or "normal").strip().lower()
    if value in {"super_flatland", "flatland", "rolling_hills", "normal", "rugged", "mountainous", "plateau"}:
        return value
    return "normal"


def _base_profile_for_size(*, width: int, height: int) -> ElevationScaleProfile:
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
) -> GeographyDraft:
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
    dominant_region_rows: list[list[int]] = []
    min_value = float("inf")
    max_value = float("-inf")
    moisture_min = float("inf")
    moisture_max = float("-inf")
    for y in range(height):
        elevation_row: list[float] = []
        moisture_row: list[float] = []
        basin_row: list[float] = []
        dominant_row: list[int] = []
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
            sx = _clamp_float(wx, 0.0, 1.0) * max(1, width - 1)
            sy = _clamp_float(wy, 0.0, 1.0) * max(1, height - 1)
            region_sample = _polygonal_region_sample(
                x=sx,
                y=sy,
                regions=macro_regions,
            )
            macro = _fbm(
                wx,
                wy,
                seed=seed ^ 0x5310,
                base_frequency=profile.macro_frequency,
                octaves=3,
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
            ridge_affinity = _macro_region_ridge_affinity(region_sample.dominant_kind)
            value = (
                region_sample.elevation_score
                + macro * profile.macro_weight * 0.16
                + detail * profile.detail_weight * region_sample.roughness
                + ridged * profile.ridge_weight * ridge_affinity
                + region_sample.boundary_softness * 0.018
            )
            moisture_value = _fbm(
                wx + 19.7,
                wy - 5.4,
                seed=seed ^ 0xC11A7E,
                base_frequency=_moisture_frequency(profile),
                octaves=4,
            )
            moisture_value = moisture_value + region_sample.moisture_bias
            elevation_row.append(value)
            moisture_row.append(moisture_value)
            basin_row.append(region_sample.basin_mask)
            dominant_row.append(region_sample.dominant_index)
            min_value = min(min_value, value)
            max_value = max(max_value, value)
            moisture_min = min(moisture_min, moisture_value)
            moisture_max = max(moisture_max, moisture_value)
        raw_elevation.append(elevation_row)
        raw_moisture.append(moisture_row)
        basin_mask.append(basin_row)
        dominant_region_rows.append(dominant_row)

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
    return GeographyDraft(
        width=width,
        height=height,
        seed=seed,
        elevation_style=profile.style_name,
        elevation_scores=elevation_scores,
        moisture_scores=moisture_scores,
        macro_regions=macro_regions,
        dominant_region_rows=dominant_region_rows,
        region_edges=_region_edges(dominant_region_rows),
    )

def _build_macro_regions(
    *,
    width: int,
    height: int,
    seed: int,
    profile: ElevationScaleProfile,
) -> tuple[GeographyDraftRegion, ...]:
    """Create deterministic large landform regions for this map size."""
    short_side = max(1, min(width, height))
    rng = Random((seed ^ 0x6E06_1A9E) & 0xFFFF_FFFF_FFFF_FFFF)
    regions: list[GeographyDraftRegion] = []
    kinds = _macro_region_kinds(profile)
    count = _macro_region_count(profile)
    min_radius = max(profile.terrace_min_size_tiles * 1.6, short_side * 0.10)
    max_radius = max(min_radius + 1.0, min(short_side * 0.52, profile.terrace_max_size_tiles * 2.1))
    margin_x = max(2.0, width * 0.06)
    margin_y = max(2.0, height * 0.06)
    for index in range(count):
        kind = kinds[index % len(kinds)]
        radius = rng.uniform(min_radius, max_radius)
        base_score, moisture_bias, roughness = _macro_region_config(kind=kind, rng=rng)
        regions.append(
            GeographyDraftRegion(
                region_id=f"geo_region_{index:03d}",
                kind=kind,
                center_x=rng.uniform(margin_x, max(margin_x, width - 1 - margin_x)),
                center_y=rng.uniform(margin_y, max(margin_y, height - 1 - margin_y)),
                radius_tiles=radius,
                strength=rng.uniform(0.75, 1.15),
                angle_degrees=rng.uniform(0.0, 180.0),
                base_elevation_score=base_score,
                moisture_bias=moisture_bias,
                roughness=roughness,
                priority=rng.uniform(0.88, 1.12),
            ),
        )
    return tuple(regions)



def _macro_region_config(*, kind: str, rng: Random) -> tuple[float, float, float]:
    """Return base elevation, moisture bias, and roughness for region kind."""
    base = {
        "basin": 0.13,
        "plain": 0.41,
        "hill": 0.60,
        "plateau": 0.70,
        "ridge": 0.76,
        "mountain": 0.86,
        "peak": 0.95,
    }.get(kind, 0.45)
    moisture = {
        "basin": 0.24,
        "plain": 0.04,
        "hill": -0.02,
        "plateau": -0.05,
        "ridge": -0.08,
        "mountain": -0.10,
        "peak": -0.12,
    }.get(kind, 0.0)
    roughness = {
        "basin": 0.22,
        "plain": 0.24,
        "hill": 0.46,
        "plateau": 0.32,
        "ridge": 0.74,
        "mountain": 0.82,
        "peak": 0.92,
    }.get(kind, 0.40)
    return (
        _clamp_float(base + rng.uniform(-0.035, 0.035), 0.02, 0.98),
        moisture + rng.uniform(-0.035, 0.035),
        _clamp_float(roughness + rng.uniform(-0.04, 0.04), 0.10, 1.0),
    )


def _polygonal_region_sample(
    *,
    x: float,
    y: float,
    regions: tuple[GeographyDraftRegion, ...],
) -> PolygonalRegionSample:
    """Sample a soft Voronoi-like macro region control map."""
    if not regions:
        return PolygonalRegionSample(
            dominant_index=0,
            secondary_index=None,
            dominant_kind="plain",
            elevation_score=0.5,
            moisture_bias=0.0,
            roughness=0.3,
            basin_mask=0.0,
            boundary_softness=0.0,
        )
    ordered = sorted(
        (
            _macro_region_distance(x=x, y=y, region=region) / max(0.1, region.priority),
            index,
            region,
        )
        for index, region in enumerate(regions)
    )
    selected = ordered[: min(3, len(ordered))]
    weight_total = 0.0
    elevation_score = 0.0
    moisture_bias = 0.0
    roughness = 0.0
    basin_mask = 0.0
    for distance, _, region in selected:
        weight = 1.0 / ((distance + 0.18) ** 2.0)
        weight_total += weight
        elevation_score += region.base_elevation_score * region.strength * weight
        moisture_bias += region.moisture_bias * weight
        roughness += region.roughness * weight
        if region.kind == "basin":
            basin_mask = max(basin_mask, _macro_region_local_influence(x=x, y=y, region=region) * region.strength)
    if weight_total <= 0.0:
        dominant = ordered[0][2]
        return PolygonalRegionSample(
            dominant_index=ordered[0][1],
            secondary_index=ordered[1][1] if len(ordered) > 1 else None,
            dominant_kind=dominant.kind,
            elevation_score=dominant.base_elevation_score,
            moisture_bias=dominant.moisture_bias,
            roughness=dominant.roughness,
            basin_mask=1.0 if dominant.kind == "basin" else 0.0,
            boundary_softness=0.0,
        )
    dominant_distance, dominant_index, dominant = ordered[0]
    secondary_index = ordered[1][1] if len(ordered) > 1 else None
    distance_gap = (ordered[1][0] - dominant_distance) if len(ordered) > 1 else 1.0
    boundary_softness = 1.0 - _clamp_float(distance_gap / 0.34, 0.0, 1.0)
    return PolygonalRegionSample(
        dominant_index=dominant_index,
        secondary_index=secondary_index,
        dominant_kind=dominant.kind,
        elevation_score=elevation_score / weight_total,
        moisture_bias=moisture_bias / weight_total,
        roughness=roughness / weight_total,
        basin_mask=_clamp_float(basin_mask, 0.0, 1.0),
        boundary_softness=boundary_softness,
    )


def _macro_region_distance(*, x: float, y: float, region: GeographyDraftRegion) -> float:
    """Return normalized distance to a macro region site."""
    dx = x - region.center_x
    dy = y - region.center_y
    if region.kind == "ridge":
        angle = region.angle_degrees * pi / 180.0
        along = dx * cos(angle) + dy * sin(angle)
        across = -dx * sin(angle) + dy * cos(angle)
        return hypot(
            along / max(1.0, region.radius_tiles * 1.75),
            across / max(1.0, region.radius_tiles * 0.36),
        )
    if region.kind == "plateau":
        angle = region.angle_degrees * pi / 180.0
        along = dx * cos(angle) + dy * sin(angle)
        across = -dx * sin(angle) + dy * cos(angle)
        return hypot(
            along / max(1.0, region.radius_tiles * 1.18),
            across / max(1.0, region.radius_tiles * 0.84),
        )
    return hypot(dx, dy) / max(1.0, region.radius_tiles)


def _macro_region_local_influence(*, x: float, y: float, region: GeographyDraftRegion) -> float:
    """Return local influence inside a macro region footprint."""
    distance = _macro_region_distance(x=x, y=y, region=region)
    if distance >= 1.0:
        return 0.0
    if region.kind == "plateau" and distance <= 0.46:
        return 1.0
    return (1.0 - distance) ** 2.0


def _macro_region_ridge_affinity(kind: str) -> float:
    return {
        "basin": 0.0,
        "plain": 0.05,
        "hill": 0.22,
        "plateau": 0.12,
        "ridge": 1.0,
        "mountain": 0.62,
        "peak": 0.74,
    }.get(kind, 0.0)


def _region_edges(rows: list[list[int]]) -> tuple[tuple[int, int], ...]:
    """Build adjacency edges between dominant macro regions."""
    edges: set[tuple[int, int]] = set()
    height = len(rows)
    width = len(rows[0]) if rows else 0
    for y, row in enumerate(rows):
        for x, region_index in enumerate(row):
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                other = rows[ny][nx]
                if other == region_index:
                    continue
                edges.add(tuple(sorted((region_index, other))))
    return tuple(sorted(edges))


def _region_edge_items(
    edges: tuple[tuple[int, int], ...],
    regions: tuple[GeographyDraftRegion, ...],
) -> list[dict[str, str]]:
    """Serialize macro region graph edges."""
    items: list[dict[str, str]] = []
    for first, second in edges:
        if not (0 <= first < len(regions) and 0 <= second < len(regions)):
            continue
        items.append(
            {
                "from": regions[first].region_id,
                "to": regions[second].region_id,
            },
        )
    return items


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))

def _macro_region_count(profile: ElevationScaleProfile) -> int:
    base_count = {
        "tiny": 2,
        "small": 3,
        "medium": 6,
        "large": 10,
        "huge": 14,
    }.get(profile.name, 6)
    if profile.style_name == "super_flatland":
        return base_count + 1
    if profile.style_name == "flatland":
        return base_count + 2
    if profile.style_name == "rolling_hills":
        return base_count + 1
    if profile.style_name == "plateau":
        return max(3, base_count - 2)
    if profile.style_name in {"rugged", "mountainous"}:
        return base_count + 3
    return base_count


def _macro_region_kinds(profile: ElevationScaleProfile) -> tuple[str, ...]:
    if profile.style_name == "super_flatland":
        return ("plain", "basin", "plain", "plain", "basin")
    if profile.style_name == "flatland":
        return ("basin", "plain", "plain", "basin", "hill", "plain")
    if profile.style_name == "rolling_hills":
        return ("plain", "basin", "hill", "hill", "plateau", "plain")
    if profile.style_name == "rugged":
        return ("plain", "basin", "hill", "plateau", "ridge", "mountain", "hill")
    if profile.style_name == "mountainous":
        return ("plain", "hill", "ridge", "mountain", "plateau", "mountain", "peak", "ridge", "basin")
    if profile.style_name == "plateau":
        return ("plateau", "plain", "plateau", "basin", "ridge", "plateau")
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
    regions: tuple[GeographyDraftRegion, ...],
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


def _macro_region_influence(*, x: float, y: float, region: GeographyDraftRegion) -> float:
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


def _clamp_levels_to_profile_range(
    levels: list[list[int]],
    *,
    profile: ElevationScaleProfile,
) -> list[list[int]]:
    """Clamp final runtime levels for styles with a strict public range."""
    if profile.style_name != "super_flatland":
        return levels
    return [
        [_clamp(level, profile.active_min_level, profile.active_max_level) for level in row]
        for row in levels
    ]


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



def _shape_region_transition_belts(
    levels: list[list[int]],
    *,
    region_rows: list[list[int]],
    terrain_rows: list[str],
    profile: ElevationScaleProfile,
) -> RegionTransitionShapingResult:
    """Soften walkable cliffs that appear exactly on macro-region borders."""
    rows = [list(row) for row in levels]
    height = len(rows)
    width = len(rows[0]) if rows else 0
    if width == 0 or height == 0 or not region_rows:
        return RegionTransitionShapingResult(
            rows=rows,
            report=_region_transition_report(
                status="skipped",
                reason="missing_grid",
                boundary_tiles=0,
                cliff_edges_before=0,
                cliff_edges_after=0,
                adjusted_tiles=0,
                passes=0,
                max_delta=profile.max_natural_delta,
            ),
        )

    boundary_tiles = _region_boundary_walkable_tiles(region_rows, terrain_rows)
    cliff_edges_before = _region_boundary_cliff_edges(
        rows,
        region_rows=region_rows,
        terrain_rows=terrain_rows,
        max_delta=profile.max_natural_delta,
    )
    locked = _locked_terrain_levels(rows, terrain_rows)
    adjusted: set[tuple[int, int]] = set()
    passes = max(1, min(4, profile.level_relax_passes // 3))
    for _ in range(passes):
        changes: dict[tuple[int, int], int] = {}
        for x, y in sorted(boundary_tiles, key=lambda point: (point[1], point[0])):
            if (x, y) in locked:
                continue
            next_level = _boundary_smoothed_level(
                rows,
                region_rows=region_rows,
                terrain_rows=terrain_rows,
                x=x,
                y=y,
                max_delta=profile.max_natural_delta,
            )
            if next_level is None or next_level == rows[y][x]:
                continue
            changes[(x, y)] = next_level
        if not changes:
            break
        for (x, y), level in changes.items():
            rows[y][x] = level
            adjusted.add((x, y))
    cliff_edges_after = _region_boundary_cliff_edges(
        rows,
        region_rows=region_rows,
        terrain_rows=terrain_rows,
        max_delta=profile.max_natural_delta,
    )
    return RegionTransitionShapingResult(
        rows=rows,
        report=_region_transition_report(
            status="ok",
            reason=None,
            boundary_tiles=len(boundary_tiles),
            cliff_edges_before=cliff_edges_before,
            cliff_edges_after=cliff_edges_after,
            adjusted_tiles=len(adjusted),
            passes=passes,
            max_delta=profile.max_natural_delta,
        ),
    )


def _region_boundary_walkable_tiles(
    region_rows: list[list[int]],
    terrain_rows: list[str],
) -> set[tuple[int, int]]:
    height = len(region_rows)
    width = len(region_rows[0]) if height else 0
    points: set[tuple[int, int]] = set()
    for y in range(height):
        for x in range(width):
            if not _terrain_walkable(terrain_rows, x, y):
                continue
            region = region_rows[y][x]
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < width and 0 <= ny < height and region_rows[ny][nx] != region:
                    points.add((x, y))
                    break
    return points


def _region_boundary_cliff_edges(
    levels: list[list[int]],
    *,
    region_rows: list[list[int]],
    terrain_rows: list[str],
    max_delta: int,
) -> int:
    height = len(levels)
    width = len(levels[0]) if height else 0
    count = 0
    for y in range(height):
        for x in range(width):
            if not _terrain_walkable(terrain_rows, x, y):
                continue
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if not _terrain_walkable(terrain_rows, nx, ny):
                    continue
                if region_rows[y][x] == region_rows[ny][nx]:
                    continue
                if abs(levels[y][x] - levels[ny][nx]) > max_delta:
                    count += 1
    return count


def _boundary_smoothed_level(
    levels: list[list[int]],
    *,
    region_rows: list[list[int]],
    terrain_rows: list[str],
    x: int,
    y: int,
    max_delta: int,
) -> int | None:
    current = levels[y][x]
    height = len(levels)
    width = len(levels[0]) if height else 0
    neighbor_levels: list[int] = []
    current_region = region_rows[y][x]
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if not (0 <= nx < width and 0 <= ny < height):
            continue
        if not _terrain_walkable(terrain_rows, nx, ny):
            continue
        if region_rows[ny][nx] == current_region and abs(levels[ny][nx] - current) <= max_delta:
            continue
        neighbor_levels.append(levels[ny][nx])
    if not neighbor_levels:
        return None
    target = _median_int(neighbor_levels)
    return _clamp(current, target - max_delta, target + max_delta)


def _region_transition_report(
    *,
    status: str,
    reason: str | None,
    boundary_tiles: int,
    cliff_edges_before: int,
    cliff_edges_after: int,
    adjusted_tiles: int,
    passes: int,
    max_delta: int,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": "region-transition-shaping-report-v1",
        "status": status,
        "rules": {
            "scope": "walkable_macro_region_boundaries",
            "max_natural_delta": max_delta,
            "moisture": "preserved",
            "terrain_tiles": "not_reclassified",
        },
        "summary": {
            "boundary_tiles": boundary_tiles,
            "cliff_edges_before": cliff_edges_before,
            "cliff_edges_after": cliff_edges_after,
            "fixed_cliff_edges": max(0, cliff_edges_before - cliff_edges_after),
            "adjusted_tiles": adjusted_tiles,
            "passes": passes,
        },
    }
    if reason:
        report["reason"] = reason
    return report


def _align_main_route_elevation(
    levels: list[list[int]],
    *,
    terrain_rows: list[str],
    tactical_data: dict[str, Any],
    explicit_cells: list[dict[str, int]],
    profile: ElevationScaleProfile,
    fallback_path: list[tuple[int, int]],
) -> MainRouteAlignmentResult:
    """Make the intended semantic main route traversable by natural deltas."""
    rows = [list(row) for row in levels]
    height = len(rows)
    width = len(rows[0]) if height else 0
    locked_points = _explicit_cell_points(explicit_cells, width=width, height=height)
    blocked_points: set[tuple[int, int]] = set()
    route_points = _semantic_main_route_points(terrain_rows, tactical_data)
    segment_paths: list[list[tuple[int, int]]] = []
    anchors: list[tuple[int, int]] = []
    failed_segments = 0
    if len(route_points) >= 2:
        anchors = [
            anchor
            for point in route_points
            if (anchor := _nearest_walkable_anchor(terrain_rows, point, blocked_points=blocked_points)) is not None
        ]
    if len(anchors) >= 2:
        for source, target in zip(anchors, anchors[1:], strict=False):
            path = _find_walkable_path_between(
                terrain_rows,
                start=source,
                goal=target,
                blocked_points=blocked_points,
            )
            if path:
                segment_paths.append(path)
            else:
                failed_segments += 1
    if not segment_paths and fallback_path:
        segment_paths = [fallback_path]
        anchors = [fallback_path[0], fallback_path[-1]] if len(fallback_path) >= 2 else []

    route_path = _merged_route_path(segment_paths)
    before_violations = _path_delta_violations(rows, route_path, max_delta=profile.max_natural_delta)
    adjusted: set[tuple[int, int]] = set()
    if route_path:
        rows, adjusted = _apply_slope_corridor(
            rows,
            path=route_path,
            radius=profile.ground_corridor_radius,
            max_delta=profile.max_natural_delta,
            locked_points=locked_points,
        )
    after_violations = _path_delta_violations(rows, route_path, max_delta=profile.max_natural_delta)
    status = "ok" if route_path and after_violations == 0 else "partial" if route_path else "skipped"
    return MainRouteAlignmentResult(
        rows=rows,
        report={
            "schema_version": "main-route-elevation-alignment-report-v1",
            "status": status,
            "rules": {
                "scope": "semantic_main_path_when_places_available_else_start_goal",
                "max_natural_delta": profile.max_natural_delta,
                "blocked_terrain": "preserved",
                "moisture": "preserved",
                "terrain_tiles": "not_reclassified",
            },
            "summary": {
                "semantic_points": len(route_points),
                "anchors": len(anchors),
                "segments": len(segment_paths),
                "failed_segments": failed_segments,
                "route_tiles": len(route_path),
                "delta_violations_before": before_violations,
                "delta_violations_after": after_violations,
                "adjusted_tiles": len(adjusted),
            },
            "anchors": [{"x": x, "y": y} for x, y in anchors],
        },
    )


def _semantic_main_route_points(
    terrain_rows: list[str],
    tactical_data: dict[str, Any],
) -> list[tuple[int, int]]:
    start = _find_tile(terrain_rows, "S")
    goal = _find_tile(terrain_rows, "G")
    if start is None or goal is None:
        return []
    places: list[dict[str, Any]] = []
    for item in tactical_data.get("places", []):
        if not isinstance(item, dict):
            continue
        center = _mapping_point(item.get("center"))
        if center is None:
            continue
        places.append(item)
    if not places:
        return [start, goal]
    max_count = min(5, max(3, len(places) // 3))
    selected = sorted(
        places,
        key=lambda place: (
            _route_place_score(start=start, goal=goal, place=place),
            -_safe_float(place.get("danger_level")),
            -_safe_float(place.get("loot_level")),
            str(place.get("id")),
        ),
    )[:max_count]
    selected.sort(key=lambda place: _point_projection(start=start, goal=goal, point=_mapping_point(place.get("center")) or start))
    points = [start]
    for place in selected:
        center = _mapping_point(place.get("center"))
        if center is not None:
            points.append(center)
    points.append(goal)
    return points


def _route_place_score(
    *,
    start: tuple[int, int],
    goal: tuple[int, int],
    place: dict[str, Any],
) -> float:
    center = _mapping_point(place.get("center")) or start
    direct = max(1, _manhattan(start, goal))
    detour = _manhattan(start, center) + _manhattan(center, goal) - direct
    projection = _point_projection(start=start, goal=goal, point=center)
    corridor_penalty = 0.0 if 0.0 <= projection <= 1.0 else direct * 0.5
    interest_bonus = (_safe_float(place.get("danger_level")) + _safe_float(place.get("loot_level"))) * 6.0
    return float(detour) + corridor_penalty - interest_bonus


def _point_projection(
    *,
    start: tuple[int, int],
    goal: tuple[int, int],
    point: tuple[int, int],
) -> float:
    dx = goal[0] - start[0]
    dy = goal[1] - start[1]
    denom = dx * dx + dy * dy
    if denom <= 0:
        return 0.0
    return ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / denom


def _nearest_walkable_anchor(
    rows: list[str],
    point: tuple[int, int],
    *,
    blocked_points: set[tuple[int, int]],
    max_radius: int = 8,
) -> tuple[int, int] | None:
    x, y = point
    if _terrain_walkable(rows, x, y) and (x, y) not in blocked_points:
        return (x, y)
    candidates: list[tuple[int, int, int]] = []
    height = len(rows)
    width = len(rows[0]) if height else 0
    for radius in range(1, max_radius + 1):
        for cy in range(y - radius, y + radius + 1):
            for cx in range(x - radius, x + radius + 1):
                if abs(cx - x) + abs(cy - y) > radius:
                    continue
                if not (0 <= cx < width and 0 <= cy < height):
                    continue
                if not _terrain_walkable(rows, cx, cy) or (cx, cy) in blocked_points:
                    continue
                candidates.append((abs(cx - x) + abs(cy - y), cx, cy))
        if candidates:
            _, best_x, best_y = min(candidates)
            return (best_x, best_y)
    return None


def _find_walkable_path_between(
    rows: list[str],
    *,
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked_points: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    height = len(rows)
    width = len(rows[0]) if height else 0
    if start == goal:
        return [start]
    if not _terrain_walkable(rows, *start) or not _terrain_walkable(rows, *goal):
        return []
    if start in blocked_points or goal in blocked_points:
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
            if (nx, ny) in visited or (nx, ny) in blocked_points:
                continue
            if not _terrain_walkable(rows, nx, ny):
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


def _merged_route_path(paths: list[list[tuple[int, int]]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for path in paths:
        if not path:
            continue
        if merged and merged[-1] == path[0]:
            merged.extend(path[1:])
        else:
            merged.extend(path)
    return merged


def _path_delta_violations(
    levels: list[list[int]],
    path: list[tuple[int, int]],
    *,
    max_delta: int,
) -> int:
    violations = 0
    for source, target in zip(path, path[1:], strict=False):
        sx, sy = source
        tx, ty = target
        if abs(levels[sy][sx] - levels[ty][tx]) > max_delta:
            violations += 1
    return violations


def _apply_slope_corridor(
    levels: list[list[int]],
    *,
    path: list[tuple[int, int]],
    radius: int,
    max_delta: int,
    locked_points: set[tuple[int, int]],
) -> tuple[list[list[int]], set[tuple[int, int]]]:
    rows = [list(row) for row in levels]
    adjusted: set[tuple[int, int]] = set()
    if not path:
        return rows, adjusted
    max_delta = max(1, max_delta)
    reverse_path = list(reversed(path))
    for _ in range(2):
        for source, target in zip(path, path[1:], strict=False):
            sx, sy = source
            tx, ty = target
            current = rows[sy][sx]
            if (tx, ty) in locked_points:
                continue
            before = rows[ty][tx]
            after = _clamp(before, current - max_delta, current + max_delta)
            if after != before:
                rows[ty][tx] = after
                adjusted.add((tx, ty))
        for source, target in zip(reverse_path, reverse_path[1:], strict=False):
            sx, sy = source
            tx, ty = target
            current = rows[sy][sx]
            if (tx, ty) in locked_points:
                continue
            before = rows[ty][tx]
            after = _clamp(before, current - max_delta, current + max_delta)
            if after != before:
                rows[ty][tx] = after
                adjusted.add((tx, ty))
    height = len(rows)
    width = len(rows[0]) if height else 0
    radius = max(0, radius)
    for x, y in path:
        anchor_level = rows[y][x]
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                distance = abs(dx) + abs(dy)
                if distance == 0 or distance > radius:
                    continue
                nx = x + dx
                ny = y + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if (nx, ny) in locked_points:
                    continue
                before = rows[ny][nx]
                after = _clamp(before, anchor_level - distance * max_delta, anchor_level + distance * max_delta)
                if after != before:
                    rows[ny][nx] = after
                    adjusted.add((nx, ny))
    return rows, adjusted


def _terrain_walkable(rows: list[str], x: int, y: int) -> bool:
    return 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] in _WALKABLE_SYMBOLS


def _mapping_point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return (x, y)
    return None


def _safe_float(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


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
    adjustment_history: dict[tuple[int, int], tuple[int, int]] = {}
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
            original_level = adjustment_history.get((x, y), (rows[y][x], rows[y][x]))[0]
            rows[y][x] = level
            adjustment_history[(x, y)] = (original_level, level)
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
            change_diagnostics=_repair_change_diagnostics(
                adjustment_history,
                terrain_rows=terrain_rows,
                total_tiles=width * height,
                two_d_reachable_tiles=len(two_d_reachable),
            ),
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


def _repair_change_diagnostics(
    adjustments: dict[tuple[int, int], tuple[int, int]],
    *,
    terrain_rows: list[str],
    total_tiles: int,
    two_d_reachable_tiles: int,
) -> dict[str, Any]:
    """Summarize why and how traversal repair changed elevation tiles."""
    by_terrain: Counter[str] = Counter()
    magnitude_histogram: Counter[str] = Counter()
    raised = 0
    lowered = 0
    total_abs_delta = 0
    maximum_abs_delta = 0

    for (x, y), (before, after) in adjustments.items():
        by_terrain[_repair_terrain_category(terrain_rows[y][x])] += 1
        delta = after - before
        if delta > 0:
            raised += 1
        elif delta < 0:
            lowered += 1
        magnitude = abs(delta)
        total_abs_delta += magnitude
        maximum_abs_delta = max(maximum_abs_delta, magnitude)
        magnitude_histogram[str(magnitude)] += 1

    adjusted = len(adjustments)
    return {
        "adjusted_by_terrain": dict(sorted(by_terrain.items())),
        "direction": {
            "raised": raised,
            "lowered": lowered,
        },
        "magnitude": {
            "average_abs_delta": round(total_abs_delta / max(1, adjusted), 3),
            "maximum_abs_delta": maximum_abs_delta,
            "histogram": dict(sorted(magnitude_histogram.items(), key=lambda item: int(item[0]))),
        },
        "coverage": {
            "percent_of_map": round(adjusted * 100.0 / max(1, total_tiles), 3),
            "percent_of_2d_reachable": round(
                adjusted * 100.0 / max(1, two_d_reachable_tiles),
                3,
            ),
        },
    }


def _empty_repair_change_diagnostics() -> dict[str, Any]:
    """Return an empty traversal repair change summary."""
    return {
        "adjusted_by_terrain": {},
        "direction": {"raised": 0, "lowered": 0},
        "magnitude": {
            "average_abs_delta": 0.0,
            "maximum_abs_delta": 0,
            "histogram": {},
        },
        "coverage": {
            "percent_of_map": 0.0,
            "percent_of_2d_reachable": 0.0,
        },
    }


def _repair_terrain_category(symbol: str) -> str:
    """Return a stable terrain category for traversal repair diagnostics."""
    if symbol == ".":
        return "road"
    if symbol == "R":
        return "ruin_floor"
    if symbol == "w":
        return "water"
    if symbol in {"b", "f", "m"}:
        return "vegetation_slow"
    if symbol in {"+", "c"}:
        return "open_ground"
    if symbol in {"S", "G"}:
        return "scenario_marker"
    return "other"


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
    change_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unreachable_before = max(0, len(two_d_reachable) - len(reachable_before))
    unreachable_after = max(0, len(two_d_reachable) - len(reachable_after))
    report: dict[str, Any] = {
        "schema_version": "traversal-repair-report-v2",
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
        "changes": change_diagnostics or _empty_repair_change_diagnostics(),
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
    geographic_fields: GeographyDraft,
    transition_report: dict[str, Any],
    route_alignment_report: dict[str, Any],
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
        "region_transition_shaping": transition_report,
        "main_route_alignment": route_alignment_report,
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
        "name": "size_aware_polygonal_macro_geography_v5",
        "seed": seed,
        "range": [MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL],
        "algorithm": "elevation_style_presets_polygon_inspired_macro_region_graph_region_transition_belts_main_route_alignment_traversal_repair",
        "redistribution": "profile_weighted_percentile_quantization",
        "smoothing_passes": profile.score_smoothing_passes,
        "level_relax_passes": profile.level_relax_passes,
        "max_natural_delta": profile.max_natural_delta,
        "profile": profile.name,
        "style": profile.style_name,
        "wave_frequency": _style_wave_frequency(profile),
    }


def _profile_report(profile: ElevationScaleProfile) -> dict[str, Any]:
    return {
        "map_class": profile.name,
        "style": profile.style_name,
        "wave_frequency": _style_wave_frequency(profile),
        "character": _style_character(profile),
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
    geographic_fields: GeographyDraft,
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
            "graph": {
                "edge_count": len(geographic_fields.region_edges),
                "edges": _region_edge_items(
                    geographic_fields.region_edges,
                    geographic_fields.macro_regions,
                ),
            },
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
                    "base_elevation_score": round(region.base_elevation_score, 4),
                    "moisture_bias": round(region.moisture_bias, 4),
                    "roughness": round(region.roughness, 4),
                    "priority": round(region.priority, 4),
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
            "region_grid": {
                "region_ids": [region.region_id for region in geographic_fields.macro_regions],
                "rows": geographic_fields.dominant_region_rows,
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
