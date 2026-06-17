from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import floor
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
class ElevationGenerationResult:
    """Result of deterministic next-generation elevation generation."""

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
    scores = _build_score_grid(width=width, height=height, seed=seed, profile=profile)
    scores = _smooth_score_grid(scores, passes=profile.score_smoothing_passes)
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
    levels = _apply_explicit_elevation_cells(
        levels,
        explicit_cells=_explicit_elevation_cells(tactical_data or {}),
    )
    report = _build_generation_report(
        levels,
        rows=rows,
        seed=seed,
        corridor_path=path,
        profile=profile,
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
                "landmarks_17_20": (0.1, 3.0),
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


def _build_score_grid(
    *,
    width: int,
    height: int,
    seed: int,
    profile: ElevationScaleProfile,
) -> list[list[float]]:
    raw: list[list[float]] = []
    min_value = float("inf")
    max_value = float("-inf")
    for y in range(height):
        row: list[float] = []
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
            basin = _fbm(
                wx + 7.3,
                wy - 11.1,
                seed=seed ^ 0xB451,
                base_frequency=max(0.5, profile.macro_frequency * 0.55),
                octaves=2,
            )
            value = (
                macro * profile.macro_weight
                + detail * profile.detail_weight
                + ridged * profile.ridge_weight
                + basin * 0.06
            )
            row.append(value)
            min_value = min(min_value, value)
            max_value = max(max_value, value)
        raw.append(row)

    value_range = max_value - min_value
    if value_range <= 1e-9:
        return [[0.5 for _ in range(width)] for _ in range(height)]
    normalized: list[list[float]] = []
    for row in raw:
        normalized.append(
            [((value - min_value) / value_range) ** profile.redistribution_power for value in row],
        )
    return normalized


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
    relaxed = [list(row) for row in levels]
    height = len(relaxed)
    width = len(relaxed[0]) if relaxed else 0
    locked = locked_levels or {}
    for _ in range(max(0, passes)):
        next_rows = [list(row) for row in relaxed]
        for y in range(height):
            for x in range(width):
                if (x, y) in locked:
                    next_rows[y][x] = locked[(x, y)]
                    continue
                neighbors = [
                    relaxed[ny][nx]
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                    if 0 <= nx < width and 0 <= ny < height
                ]
                if not neighbors:
                    continue
                level = relaxed[y][x]
                neighbor_min = min(neighbors)
                neighbor_max = max(neighbors)
                if level > neighbor_min + max_delta:
                    next_rows[y][x] = neighbor_min + max_delta
                elif level < neighbor_max - max_delta:
                    next_rows[y][x] = neighbor_max - max_delta
        relaxed = next_rows
    return relaxed


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
    rows: list[str],
    seed: int,
    corridor_path: list[tuple[int, int]],
    profile: ElevationScaleProfile,
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
        "terrain_bias": {
            "start_goal_forced_to_level": 0,
            "start_goal_ground_corridor_tiles": len(corridor_path),
            "ground_corridor_radius": profile.ground_corridor_radius,
            "road_clamp": [ROAD_MIN_LEVEL, ROAD_MAX_LEVEL],
            "water_max_level": WATER_MAX_LEVEL,
            "road_tiles": sum(row.count(".") for row in rows),
            "water_tiles": sum(row.count("w") for row in rows),
        },
    }


def _generator_info(*, seed: int, profile: ElevationScaleProfile) -> dict[str, Any]:
    return {
        "name": "size_aware_red_blob_elevation_v1",
        "seed": seed,
        "range": [MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL],
        "algorithm": "size_aware_fbm_value_noise_domain_warp_redistribution_terraces",
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


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count * 100.0 / total, 3)
