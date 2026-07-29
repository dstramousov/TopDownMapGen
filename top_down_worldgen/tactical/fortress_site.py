from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import ceil, sqrt
from typing import Any

from top_down_worldgen.config import FortressConfig


REPORT_SCHEMA_VERSION = "fortress-site-report-v1"
SUPPORTED_ELEVATION_STYLES = frozenset({
    "super_flatland", "flatland", "rolling_hills", "normal",
    "rugged", "mountainous", "plateau",
})
DEEP_WATER_MAX_LEVEL = -2
SIZE_PROFILES = {
    "small": (0.10, 20, 64),
    "medium": (0.16, 28, 96),
    "huge": (0.24, 40, 136),
}
MIN_ISLAND_MARGIN_TILES = 6
ISLAND_MARGIN_RATIO = 0.15
MIN_WATER_RING_TILES = 6
WATER_RING_RATIO = 0.15
MAX_REPORTED_CANDIDATES = 12


@dataclass(frozen=True, slots=True)
class FortressSiteRequirements:
    """Derived geometry requirements for a lake-island fortress site."""

    fortress_span_tiles: int
    island_margin_tiles: int
    island_span_tiles: int
    island_radius_tiles: int
    water_ring_tiles: int
    required_clearance_tiles: int
    minimum_component_area_tiles: int

    def to_dict(self) -> dict[str, int]:
        """Return JSON-serializable site requirements."""
        return {
            "fortress_span_tiles": self.fortress_span_tiles,
            "island_margin_tiles": self.island_margin_tiles,
            "island_span_tiles": self.island_span_tiles,
            "island_radius_tiles": self.island_radius_tiles,
            "water_ring_tiles": self.water_ring_tiles,
            "required_clearance_tiles": self.required_clearance_tiles,
            "minimum_component_area_tiles": self.minimum_component_area_tiles,
        }


@dataclass(frozen=True, slots=True)
class _LakeComponent:
    component_id: int
    points: tuple[tuple[int, int], ...]
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    touches_map_edge: bool
    minimum_level: int
    maximum_level: int


@dataclass(frozen=True, slots=True)
class _ClearanceResult:
    center_x: int
    center_y: int
    max_clearance_tiles: int


def analyze_lake_island_fortress_site(
    *,
    elevation_rows: list[list[int]],
    elevation_style: str,
    fortress_config: FortressConfig,
) -> dict[str, Any]:
    """Analyze natural water bodies for a future island fortress.

    The function is intentionally read-only. It selects and reports a suitable
    water component but does not alter elevation or terrain yet.

    Args:
        elevation_rows: Natural integer elevation grid.
        elevation_style: Sanitized public elevation style.
        fortress_config: Sanitized public fortress configuration.

    Returns:
        JSON-serializable fortress site analysis report.
    """
    height = len(elevation_rows)
    width = len(elevation_rows[0]) if elevation_rows else 0
    requirements = _requirements(
        width=width, height=height, size=fortress_config.size
    )
    base_report = _base_report(
        width=width,
        height=height,
        elevation_style=elevation_style,
        fortress_config=fortress_config,
        requirements=requirements,
    )

    disabled_reason = _disabled_reason(
        fortress_config=fortress_config,
        elevation_style=elevation_style,
        width=width,
        height=height,
    )
    if disabled_reason is not None:
        base_report["status"] = disabled_reason
        return base_report

    components, water_tiles = _find_lake_components(elevation_rows)
    candidate_reports = [
        _analyze_component(component, requirements=requirements)
        for component in components
    ]
    candidate_reports.sort(key=_candidate_sort_key, reverse=True)
    accepted = [candidate for candidate in candidate_reports if candidate["accepted"]]
    selected = accepted[0] if accepted else None

    resolved_placement = "island"
    fallback_reason = None
    selected_site = (
        _selected_site(selected, requirements=requirements)
        if selected is not None
        else None
    )
    if fortress_config.archetype == "any":
        selected_site = _select_inland_site(
            elevation_rows, requirements=requirements
        )
        resolved_placement = "inland"
    elif selected_site is None:
        selected_site = _select_shore_site(
            elevation_rows, components=components, requirements=requirements
        )
        if selected_site is not None:
            resolved_placement = "shore"
            fallback_reason = "no_suitable_island_water_body"
        else:
            selected_site = _select_inland_site(
                elevation_rows, requirements=requirements
            )
            resolved_placement = "inland"
            fallback_reason = "no_water_body"

    base_report["status"] = "selected" if selected_site is not None else "not_found"
    base_report["requested_archetype"] = fortress_config.archetype
    base_report["resolved_placement"] = (
        resolved_placement if selected_site is not None else None
    )
    base_report["fallback_reason"] = fallback_reason
    base_report["summary"] = {
        "water_tiles": water_tiles,
        "water_percent": _percent(water_tiles, width * height),
        "lake_components": len(components),
        "eligible_components": len(accepted),
        "selected_component_id": (
            selected["component_id"] if selected is not None else None
        ),
    }
    base_report["selected_site"] = selected_site
    base_report["candidates"] = candidate_reports[:MAX_REPORTED_CANDIDATES]
    return base_report


def _requirements(
    *, width: int, height: int, size: str
) -> FortressSiteRequirements:
    short_side = min(width, height)
    ratio, minimum, maximum = SIZE_PROFILES[size]
    fortress_span = _clamp(round(short_side * ratio), minimum, maximum)
    island_margin = max(
        MIN_ISLAND_MARGIN_TILES,
        round(fortress_span * ISLAND_MARGIN_RATIO),
    )
    island_span = fortress_span + island_margin * 2
    island_radius = ceil(island_span / 2)
    water_ring = max(
        MIN_WATER_RING_TILES,
        round(fortress_span * WATER_RING_RATIO),
    )
    required_clearance = island_radius + water_ring
    minimum_area = max(
        1,
        2 * required_clearance * required_clearance
        - 2 * required_clearance
        + 1,
    )
    return FortressSiteRequirements(
        fortress_span_tiles=fortress_span,
        island_margin_tiles=island_margin,
        island_span_tiles=island_span,
        island_radius_tiles=island_radius,
        water_ring_tiles=water_ring,
        required_clearance_tiles=required_clearance,
        minimum_component_area_tiles=minimum_area,
    )


def _base_report(
    *,
    width: int,
    height: int,
    elevation_style: str,
    fortress_config: FortressConfig,
    requirements: FortressSiteRequirements,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "kind": "lake_island_fortress_site_analysis",
        "status": "disabled",
        "source_elevation_style": elevation_style,
        "dimensions": {
            "width": width,
            "height": height,
            "tiles": width * height,
        },
        "config": fortress_config.to_dict(),
        "policy": {
            "phase": "site_selection_only",
            "supported_elevation_styles": sorted(SUPPORTED_ELEVATION_STYLES),
            "placement_priority": ["island", "shore", "inland"],
            "water_levels": [-5, -4, -3, -2],
            "selection": "highest_clearance_then_area",
            "map_edge_components_allowed": True,
            "max_reported_candidates": MAX_REPORTED_CANDIDATES,
        },
        "requirements": requirements.to_dict(),
        "summary": {
            "water_tiles": 0,
            "water_percent": 0.0,
            "lake_components": 0,
            "eligible_components": 0,
            "selected_component_id": None,
        },
        "selected_site": None,
        "candidates": [],
    }


def _disabled_reason(
    *,
    fortress_config: FortressConfig,
    elevation_style: str,
    width: int,
    height: int,
) -> str | None:
    if not fortress_config.enabled:
        return "disabled"
    if fortress_config.archetype not in {"island", "any"}:
        return "archetype_not_requested"
    if elevation_style not in SUPPORTED_ELEVATION_STYLES:
        return "unsupported_elevation_style"
    if width <= 0 or height <= 0:
        return "empty_map"
    return None


def _find_lake_components(
    elevation_rows: list[list[int]],
) -> tuple[list[_LakeComponent], int]:
    height = len(elevation_rows)
    width = len(elevation_rows[0]) if elevation_rows else 0
    visited = [bytearray(width) for _ in range(height)]
    components: list[_LakeComponent] = []
    water_tiles = 0

    for y in range(height):
        row = elevation_rows[y]
        if len(row) != width:
            raise ValueError("Elevation rows must have equal width")
        for x in range(width):
            if visited[y][x] or row[x] > DEEP_WATER_MAX_LEVEL:
                continue
            component = _collect_component(
                elevation_rows,
                visited=visited,
                start_x=x,
                start_y=y,
                component_id=len(components),
            )
            water_tiles += len(component.points)
            components.append(component)
    return components, water_tiles


def _collect_component(
    elevation_rows: list[list[int]],
    *,
    visited: list[bytearray],
    start_x: int,
    start_y: int,
    component_id: int,
) -> _LakeComponent:
    height = len(elevation_rows)
    width = len(elevation_rows[0]) if elevation_rows else 0
    queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
    visited[start_y][start_x] = 1
    points: list[tuple[int, int]] = []
    min_x = max_x = start_x
    min_y = max_y = start_y
    touches_edge = False
    minimum_level = elevation_rows[start_y][start_x]
    maximum_level = minimum_level

    while queue:
        x, y = queue.popleft()
        points.append((x, y))
        level = int(elevation_rows[y][x])
        minimum_level = min(minimum_level, level)
        maximum_level = max(maximum_level, level)
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        touches_edge = touches_edge or x in {0, width - 1} or y in {0, height - 1}

        for nx, ny in _neighbors(x, y):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if visited[ny][nx] or elevation_rows[ny][nx] > DEEP_WATER_MAX_LEVEL:
                continue
            visited[ny][nx] = 1
            queue.append((nx, ny))

    return _LakeComponent(
        component_id=component_id,
        points=tuple(points),
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
        touches_map_edge=touches_edge,
        minimum_level=minimum_level,
        maximum_level=maximum_level,
    )


def _analyze_component(
    component: _LakeComponent,
    *,
    requirements: FortressSiteRequirements,
) -> dict[str, Any]:
    area = len(component.points)
    bbox_width = component.max_x - component.min_x + 1
    bbox_height = component.max_y - component.min_y + 1
    bbox_area = bbox_width * bbox_height
    compactness = area / bbox_area if bbox_area else 0.0
    rejection_reasons: list[str] = []

    if area < requirements.minimum_component_area_tiles:
        rejection_reasons.append("area_below_minimum")
        clearance = _ClearanceResult(
            center_x=(component.min_x + component.max_x) // 2,
            center_y=(component.min_y + component.max_y) // 2,
            max_clearance_tiles=0,
        )
    else:
        clearance = _maximum_clearance(component)
        if clearance.max_clearance_tiles < requirements.required_clearance_tiles:
            rejection_reasons.append("clearance_below_minimum")

    accepted = not rejection_reasons
    available_ring = max(
        0,
        clearance.max_clearance_tiles - requirements.island_radius_tiles,
    )
    estimated_bridge = max(0, available_ring)
    score = _candidate_score(
        area=area,
        max_clearance=clearance.max_clearance_tiles,
        compactness=compactness,
        touches_map_edge=component.touches_map_edge,
        accepted=accepted,
    )
    return {
        "component_id": component.component_id,
        "accepted": accepted,
        "rejection_reasons": rejection_reasons,
        "score": round(score, 3),
        "area_tiles": area,
        "bounding_box": {
            "min_x": component.min_x,
            "min_y": component.min_y,
            "max_x": component.max_x,
            "max_y": component.max_y,
            "width": bbox_width,
            "height": bbox_height,
        },
        "compactness": round(compactness, 4),
        "touches_map_edge": component.touches_map_edge,
        "water_levels": {
            "minimum": component.minimum_level,
            "maximum": component.maximum_level,
        },
        "center": {"x": clearance.center_x, "y": clearance.center_y},
        "max_clearance_tiles": clearance.max_clearance_tiles,
        "available_water_ring_tiles": available_ring,
        "estimated_bridge_length_tiles": estimated_bridge,
    }


def _maximum_clearance(component: _LakeComponent) -> _ClearanceResult:
    points = set(component.points)
    distance: dict[tuple[int, int], int] = {}
    queue: deque[tuple[int, int]] = deque()

    for point in component.points:
        x, y = point
        if any(neighbor not in points for neighbor in _neighbors(x, y)):
            distance[point] = 1
            queue.append(point)

    best_point = component.points[0]
    best_distance = 1
    while queue:
        point = queue.popleft()
        current_distance = distance[point]
        if current_distance > best_distance or (
            current_distance == best_distance and point < best_point
        ):
            best_point = point
            best_distance = current_distance
        x, y = point
        for neighbor in _neighbors(x, y):
            if neighbor not in points or neighbor in distance:
                continue
            distance[neighbor] = current_distance + 1
            queue.append(neighbor)

    return _ClearanceResult(
        center_x=best_point[0],
        center_y=best_point[1],
        max_clearance_tiles=best_distance,
    )


def _candidate_score(
    *,
    area: int,
    max_clearance: int,
    compactness: float,
    touches_map_edge: bool,
    accepted: bool,
) -> float:
    score = max_clearance * 100.0 + sqrt(area) * 4.0 + compactness * 25.0
    if touches_map_edge:
        score -= 20.0
    if accepted:
        score += 1_000_000.0
    return score


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, int, int]:
    return (
        float(candidate["score"]),
        int(candidate["area_tiles"]),
        -int(candidate["component_id"]),
    )


def _selected_site(
    candidate: dict[str, Any],
    *,
    requirements: FortressSiteRequirements,
) -> dict[str, Any]:
    return {
        "archetype": "lake_island",
        "component_id": candidate["component_id"],
        "center": dict(candidate["center"]),
        "lake_area_tiles": candidate["area_tiles"],
        "lake_touches_map_edge": candidate["touches_map_edge"],
        "max_clearance_tiles": candidate["max_clearance_tiles"],
        "available_water_ring_tiles": candidate["available_water_ring_tiles"],
        "estimated_bridge_length_tiles": candidate[
            "estimated_bridge_length_tiles"
        ],
        "planned_fortress_span_tiles": requirements.fortress_span_tiles,
        "planned_island_span_tiles": requirements.island_span_tiles,
        "required_water_ring_tiles": requirements.water_ring_tiles,
    }


def _select_shore_site(
    elevation_rows: list[list[int]],
    *,
    components: list[_LakeComponent],
    requirements: FortressSiteRequirements,
) -> dict[str, Any] | None:
    height = len(elevation_rows)
    width = len(elevation_rows[0]) if elevation_rows else 0
    margin = requirements.island_radius_tiles + 2
    best: tuple[float, int, int, int] | None = None
    for component in components:
        for x, y in component.points:
            for nx, ny in _neighbors(x, y):
                if not (margin <= nx < width - margin and margin <= ny < height - margin):
                    continue
                if elevation_rows[ny][nx] < 0:
                    continue
                slope = _local_relief(elevation_rows, nx, ny, requirements.island_radius_tiles)
                score = slope * 20.0 + abs(elevation_rows[ny][nx])
                candidate = (score, nx, ny, component.component_id)
                if best is None or candidate < best:
                    best = candidate
    if best is None:
        return None
    _, x, y, component_id = best
    return _generic_selected_site(
        x=x, y=y, placement="shore", requirements=requirements,
        component_id=component_id,
    )


def _select_inland_site(
    elevation_rows: list[list[int]],
    *,
    requirements: FortressSiteRequirements,
) -> dict[str, Any] | None:
    height = len(elevation_rows)
    width = len(elevation_rows[0]) if elevation_rows else 0
    margin = requirements.island_radius_tiles + 2
    if width <= margin * 2 or height <= margin * 2:
        return None
    step = max(2, requirements.fortress_span_tiles // 8)
    best: tuple[float, int, int] | None = None
    for y in range(margin, height - margin, step):
        for x in range(margin, width - margin, step):
            if elevation_rows[y][x] < 0:
                continue
            relief = _local_relief(elevation_rows, x, y, requirements.island_radius_tiles)
            level = elevation_rows[y][x]
            score = relief * 12.0 - level * 1.5
            candidate = (score, x, y)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        return None
    _, x, y = best
    return _generic_selected_site(
        x=x, y=y, placement="inland", requirements=requirements, component_id=None
    )


def _local_relief(
    rows: list[list[int]], x: int, y: int, radius: int
) -> int:
    sample_radius = max(2, radius // 2)
    values: list[int] = []
    for sy in range(y - sample_radius, y + sample_radius + 1, max(1, sample_radius // 3)):
        for sx in range(x - sample_radius, x + sample_radius + 1, max(1, sample_radius // 3)):
            values.append(rows[sy][sx])
    return max(values) - min(values) if values else 0


def _generic_selected_site(
    *, x: int, y: int, placement: str,
    requirements: FortressSiteRequirements, component_id: int | None,
) -> dict[str, Any]:
    return {
        "archetype": placement,
        "component_id": component_id,
        "center": {"x": x, "y": y},
        "planned_fortress_span_tiles": requirements.fortress_span_tiles,
        "planned_island_span_tiles": requirements.island_span_tiles,
        "required_water_ring_tiles": requirements.water_ring_tiles,
    }


def _neighbors(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def _percent(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(value * 100.0 / total, 4)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
