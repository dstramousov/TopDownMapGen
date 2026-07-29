from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import atan2, cos, pi, sin, sqrt
from pathlib import Path
from random import Random
from typing import Any

from PIL import Image


SHORELINE_LEVEL = 0
INTERIOR_LEVEL = 1
CORE_LEVEL = 2
WATER_MAX_LEVEL = -2
MASK_OUTSIDE = 0
MASK_SHORELINE = 1
MASK_INTERIOR = 2
MASK_CORE = 3


@dataclass(frozen=True, slots=True)
class FortressIslandResult:
    """Materialized lake-island fortress site."""

    runtime_data: dict[str, Any]
    site_report: dict[str, Any]
    mask_rows: list[list[int]]
    changed_tiles: int
    island_tiles: int
    shoreline_tiles: int
    core_tiles: int
    entrance_anchor: dict[str, int] | None


def materialize_lake_island(
    *,
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    seed: int,
    elevation_style: str,
) -> FortressIslandResult:
    """Materialize the selected lake-island site in elevation grids.

    Args:
        runtime_data: Tactical runtime data with elevation grids.
        site_report: Fortress site analysis report.
        seed: Resolved world seed.
        elevation_style: Active elevation style.

    Returns:
        Updated runtime data, report, mask, and materialization metrics.
    """
    if site_report.get("status") != "selected":
        return FortressIslandResult(
            runtime_data=runtime_data,
            site_report=site_report,
            mask_rows=[],
            changed_tiles=0,
            island_tiles=0,
            shoreline_tiles=0,
            core_tiles=0,
            entrance_anchor=None,
        )

    selected = site_report.get("selected_site")
    requirements = site_report.get("requirements")
    if not isinstance(selected, dict) or not isinstance(requirements, dict):
        return FortressIslandResult(
            runtime_data=runtime_data,
            site_report=site_report,
            mask_rows=[],
            changed_tiles=0,
            island_tiles=0,
            shoreline_tiles=0,
            core_tiles=0,
            entrance_anchor=None,
        )

    report = runtime_data.get("elevation_generation_report")
    if not isinstance(report, dict):
        raise ValueError("Missing elevation_generation_report")
    geography = report.get("geography")
    grids = geography.get("grids") if isinstance(geography, dict) else None
    if not isinstance(grids, dict):
        raise ValueError("Missing elevation geography grids")

    geographic_rows = _copy_int_rows(grids, "geographic_level_grid")
    runtime_rows = _copy_int_rows(grids, "runtime_level_grid")
    if not geographic_rows or not runtime_rows:
        raise ValueError("Elevation grids must not be empty")
    if len(geographic_rows) != len(runtime_rows):
        raise ValueError("Elevation grid heights do not match")

    height = len(geographic_rows)
    width = len(geographic_rows[0])
    if any(len(row) != width for row in geographic_rows + runtime_rows):
        raise ValueError("Elevation grids must be rectangular")

    center = selected.get("center")
    if not isinstance(center, dict):
        raise ValueError("Selected fortress site has no center")
    center_x = int(center.get("x", -1))
    center_y = int(center.get("y", -1))
    radius = int(requirements.get("island_radius_tiles", 0))
    if not (0 <= center_x < width and 0 <= center_y < height and radius > 0):
        raise ValueError("Invalid fortress island geometry")

    mask_rows = _build_irregular_island_mask(
        width=width,
        height=height,
        center_x=center_x,
        center_y=center_y,
        radius=radius,
        seed=seed,
    )
    entrance_anchor = _choose_entrance_anchor(
        mask_rows=mask_rows,
        original_rows=geographic_rows,
        center_x=center_x,
        center_y=center_y,
    )

    placement = str(site_report.get("resolved_placement", "island"))
    changed_tiles = 0
    island_tiles = 0
    shoreline_tiles = 0
    core_tiles = 0
    for y, mask_row in enumerate(mask_rows):
        for x, mask in enumerate(mask_row):
            if mask == MASK_OUTSIDE:
                continue
            level = (
                _level_for_mask(mask)
                if placement == "island"
                else _terrain_fitted_level(
                    geographic_rows, x=x, y=y, mask=mask
                )
            )
            island_tiles += 1
            if mask == MASK_SHORELINE:
                shoreline_tiles += 1
            elif mask == MASK_CORE:
                core_tiles += 1
            if geographic_rows[y][x] != level or runtime_rows[y][x] != level:
                changed_tiles += 1
            geographic_rows[y][x] = level
            runtime_rows[y][x] = level

    slope_rows = _slope_rows(geographic_rows)
    grids["geographic_level_grid"] = {"rows": geographic_rows}
    grids["runtime_level_grid"] = {"rows": runtime_rows}
    grids["slope_grid"] = {"rows": slope_rows}
    _refresh_mask_grid(grids=grids, levels=geographic_rows, slope_rows=slope_rows)
    _refresh_water_grid(grids=grids, levels=geographic_rows)

    updated_report = dict(report)
    updated_geography = dict(geography)
    updated_geography["grids"] = grids
    updated_geography["slope"] = _slope_report(slope_rows)
    updated_report["geography"] = updated_geography
    updated_report["summary"] = _summary(runtime_rows)

    updated_runtime = dict(runtime_data)
    updated_runtime["elevation_generation_report"] = updated_report
    elevation = dict(updated_runtime.get("elevation", {}))
    elevation["default"] = 0
    elevation["cells"] = _sparse_cells(runtime_rows)
    elevation["summary"] = updated_report["summary"]
    updated_runtime["elevation"] = elevation

    materialization = {
        "status": "materialized",
        "algorithm": "deterministic_irregular_ellipse_v2",
        "resolved_placement": placement,
        "seed": seed,
        "center": {"x": center_x, "y": center_y},
        "radius_tiles": radius,
        "island_tiles": island_tiles,
        "shoreline_tiles": shoreline_tiles,
        "interior_tiles": island_tiles - shoreline_tiles - core_tiles,
        "core_tiles": core_tiles,
        "changed_tiles": changed_tiles,
        "elevation_levels": {
            "shoreline": SHORELINE_LEVEL,
            "interior": INTERIOR_LEVEL,
            "core": CORE_LEVEL,
        },
        "entrance_anchor": entrance_anchor,
    }
    updated_site_report = dict(site_report)
    policy = dict(updated_site_report.get("policy", {}))
    policy["phase"] = "island_materialized"
    updated_site_report["policy"] = policy
    updated_site_report["island_materialization"] = materialization
    updated_runtime["fortress_site"] = updated_site_report

    return FortressIslandResult(
        runtime_data=updated_runtime,
        site_report=updated_site_report,
        mask_rows=mask_rows,
        changed_tiles=changed_tiles,
        island_tiles=island_tiles,
        shoreline_tiles=shoreline_tiles,
        core_tiles=core_tiles,
        entrance_anchor=entrance_anchor,
    )


def render_fortress_island_preview(
    *,
    path: Path,
    elevation_rows: list[list[int]],
    mask_rows: list[list[int]],
) -> None:
    """Render a diagnostic island mask preview.

    Args:
        path: Output PNG path.
        elevation_rows: Final geographic elevation rows.
        mask_rows: Island classification mask.
    """
    height = len(elevation_rows)
    width = len(elevation_rows[0]) if elevation_rows else 0
    if width <= 0 or height <= 0:
        return
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            level = elevation_rows[y][x]
            mask = mask_rows[y][x] if y < len(mask_rows) and x < len(mask_rows[y]) else 0
            if mask == MASK_SHORELINE:
                color = (194, 174, 112)
            elif mask == MASK_INTERIOR:
                color = (98, 145, 73)
            elif mask == MASK_CORE:
                color = (130, 166, 84)
            elif level <= WATER_MAX_LEVEL:
                color = (47, 91, 143)
            elif level == -1:
                color = (74, 119, 129)
            else:
                color = (87, 125, 67)
            pixels[x, y] = color
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _copy_int_rows(grids: dict[str, Any], name: str) -> list[list[int]]:
    grid = grids.get(name)
    rows = grid.get("rows") if isinstance(grid, dict) else None
    if not isinstance(rows, list):
        return []
    return [[int(value) for value in row] for row in rows]


def _build_irregular_island_mask(
    *,
    width: int,
    height: int,
    center_x: int,
    center_y: int,
    radius: int,
    seed: int,
) -> list[list[int]]:
    rng = Random(seed ^ 0x7A31_5EED_91C4)
    phase_a = rng.random() * 2.0 * pi
    phase_b = rng.random() * 2.0 * pi
    phase_c = rng.random() * 2.0 * pi
    x_scale = rng.uniform(0.94, 1.06)
    y_scale = rng.uniform(0.94, 1.06)
    shoreline_width = max(2.0, radius * 0.12)
    core_radius = radius * rng.uniform(0.42, 0.50)
    rows = [[MASK_OUTSIDE for _ in range(width)] for _ in range(height)]
    min_x = max(0, center_x - radius - 3)
    max_x = min(width - 1, center_x + radius + 3)
    min_y = max(0, center_y - radius - 3)
    max_y = min(height - 1, center_y + radius + 3)
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            dx = (x - center_x) / x_scale
            dy = (y - center_y) / y_scale
            angle = atan2(dy, dx)
            radial_noise = (
                0.055 * sin(3.0 * angle + phase_a)
                + 0.035 * sin(5.0 * angle + phase_b)
                + 0.020 * sin(8.0 * angle + phase_c)
            )
            local_radius = radius * (1.0 + radial_noise)
            distance = sqrt(dx * dx + dy * dy)
            if distance > local_radius:
                continue
            if distance >= local_radius - shoreline_width:
                rows[y][x] = MASK_SHORELINE
            elif distance <= core_radius * (1.0 + 0.05 * sin(4.0 * angle + phase_b)):
                rows[y][x] = MASK_CORE
            else:
                rows[y][x] = MASK_INTERIOR
    return rows


def _choose_entrance_anchor(
    *,
    mask_rows: list[list[int]],
    original_rows: list[list[int]],
    center_x: int,
    center_y: int,
) -> dict[str, int] | None:
    height = len(mask_rows)
    width = len(mask_rows[0]) if mask_rows else 0
    best: tuple[int, int, int] | None = None
    for index in range(64):
        angle = 2.0 * pi * index / 64.0
        dx = cos(angle)
        dy = sin(angle)
        anchor: tuple[int, int] | None = None
        water_steps = 0
        for step in range(1, max(width, height) + 1):
            x = round(center_x + dx * step)
            y = round(center_y + dy * step)
            if not (0 <= x < width and 0 <= y < height):
                break
            if mask_rows[y][x] != MASK_OUTSIDE:
                anchor = (x, y)
                continue
            if original_rows[y][x] <= WATER_MAX_LEVEL:
                water_steps += 1
                continue
            if anchor is not None:
                candidate = (water_steps, anchor[0], anchor[1])
                if best is None or candidate < best:
                    best = candidate
            break
    if best is None:
        return None
    return {"x": best[1], "y": best[2]}


def _terrain_fitted_level(
    rows: list[list[int]], *, x: int, y: int, mask: int
) -> int:
    """Return a locally fitted construction level for shore/inland sites."""
    height = len(rows)
    width = len(rows[0]) if rows else 0
    values: list[int] = []
    for ny in range(max(0, y - 1), min(height, y + 2)):
        for nx in range(max(0, x - 1), min(width, x + 2)):
            if rows[ny][nx] >= 0:
                values.append(rows[ny][nx])
    base = round(sum(values) / len(values)) if values else max(0, rows[y][x])
    if mask == MASK_CORE:
        return base + 1
    return base


def _level_for_mask(mask: int) -> int:
    if mask == MASK_SHORELINE:
        return SHORELINE_LEVEL
    if mask == MASK_CORE:
        return CORE_LEVEL
    return INTERIOR_LEVEL


def _slope_rows(levels: list[list[int]]) -> list[list[int]]:
    height = len(levels)
    width = len(levels[0]) if levels else 0
    output = [[0 for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(levels):
        for x, level in enumerate(row):
            maximum = 0
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    maximum = max(maximum, abs(level - levels[ny][nx]))
            output[y][x] = maximum
    return output


def _summary(levels: list[list[int]]) -> dict[str, Any]:
    counts = Counter(level for row in levels for level in row)
    total = sum(counts.values())
    return {
        "min_level": min(counts) if counts else 0,
        "max_level": max(counts) if counts else 0,
        "levels_present": [str(level) for level in sorted(counts)],
        "level_counts": {str(level): counts[level] for level in sorted(counts)},
        "level_zero_percent": _percent(counts.get(0, 0), total),
        "non_zero_percent": _percent(total - counts.get(0, 0), total),
    }


def _sparse_cells(levels: list[list[int]]) -> list[dict[str, int]]:
    return [
        {"x": x, "y": y, "level": level}
        for y, row in enumerate(levels)
        for x, level in enumerate(row)
        if level != 0
    ]


def _refresh_mask_grid(
    *, grids: dict[str, Any], levels: list[list[int]], slope_rows: list[list[int]]
) -> None:
    legend = {
        "B": "basins", "L": "lowlands", "P": "plains", "H": "hills",
        "T": "plateaus", "R": "ridges", "M": "mountains", "K": "peaks",
    }
    rows: list[str] = []
    for y, level_row in enumerate(levels):
        chars: list[str] = []
        for x, level in enumerate(level_row):
            slope = slope_rows[y][x]
            if level < 0:
                chars.append("B" if level <= -2 else "L")
            elif level >= 17:
                chars.append("K")
            elif level >= 11:
                chars.append("R" if slope >= 2 else "M")
            elif level >= 7:
                chars.append("R" if slope >= 2 else "T")
            elif level >= 3:
                chars.append("H")
            else:
                chars.append("P")
        rows.append("".join(chars))
    grids["mask_grid"] = {"legend": legend, "rows": rows}


def _refresh_water_grid(*, grids: dict[str, Any], levels: list[list[int]]) -> None:
    old = grids.get("water_lowland_grid")
    legend = old.get("legend", {}) if isinstance(old, dict) else {}
    rows = [
        "".join("B" if level <= -2 else "L" if level == -1 else "D" for level in row)
        for row in levels
    ]
    grids["water_lowland_grid"] = {"legend": legend, "rows": rows}


def _slope_report(rows: list[list[int]]) -> dict[str, Any]:
    values = [value for row in rows for value in row]
    total = len(values)
    return {
        "max_delta": max(values) if values else 0,
        "bands": {
            "flat": _metric(sum(value == 0 for value in values), total),
            "gentle": _metric(sum(value == 1 for value in values), total),
            "steep": _metric(sum(value == 2 for value in values), total),
            "cliff": _metric(sum(value >= 3 for value in values), total),
        },
    }


def _metric(count: int, total: int) -> dict[str, Any]:
    return {"count": count, "percent": _percent(count, total)}


def _percent(count: int, total: int) -> float:
    return round(count * 100.0 / total, 3) if total > 0 else 0.0
