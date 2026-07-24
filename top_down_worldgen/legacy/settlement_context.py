from __future__ import annotations

import hashlib
import math
from collections import deque
from dataclasses import dataclass
from enum import StrEnum

try:
    from .terrain_guidance import TerrainGuidance
except ImportError:  # Direct script execution by LegacyEngineRunner.
    from terrain_guidance import TerrainGuidance


class SettlementProfile(StrEnum):
    """Historical settlement patterns selected from elevation context."""

    OPEN_PLAIN = "open_plain"
    RURAL_PLAIN = "rural_plain"
    ROLLING_VALLEYS = "rolling_valleys"
    RUGGED_OUTPOSTS = "rugged_outposts"
    MOUNTAIN_STRONGHOLD = "mountain_stronghold"
    PLATEAU_SETTLEMENT = "plateau_settlement"
    SPARSE_FRONTIER = "sparse_frontier"


@dataclass(frozen=True, slots=True)
class FlatComponent:
    """One exact-level connected buildable terrain component."""

    area: int
    level: int
    center_x: int
    center_y: int
    left: int
    top: int
    right: int
    bottom: int

    def to_dict(self) -> dict[str, int]:
        """Return compact JSON-serializable component metadata."""
        return {
            "area": self.area,
            "level": self.level,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }


@dataclass(frozen=True, slots=True)
class SettlementTerrainContext:
    """Terrain metrics used to select settlement density and archetypes."""

    elevation_style: str
    elevation_min: int
    elevation_max: int
    buildable_tile_ratio: float
    comfortable_tile_ratio: float
    rough_tile_ratio: float
    cliff_tile_ratio: float
    flat_component_count: int
    large_flat_component_count: int
    largest_flat_component_area: int
    valley_candidate_count: int
    high_plateau_candidate_count: int
    pass_candidate_count: int
    flat_components: tuple[FlatComponent, ...]
    high_plateau_components: tuple[FlatComponent, ...]
    valley_components: tuple[FlatComponent, ...]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-serializable terrain diagnostics."""
        return {
            "elevation_style": self.elevation_style,
            "elevation_min": self.elevation_min,
            "elevation_max": self.elevation_max,
            "elevation_range": self.elevation_max - self.elevation_min,
            "buildable_tile_ratio": round(self.buildable_tile_ratio, 6),
            "comfortable_tile_ratio": round(self.comfortable_tile_ratio, 6),
            "rough_tile_ratio": round(self.rough_tile_ratio, 6),
            "cliff_tile_ratio": round(self.cliff_tile_ratio, 6),
            "flat_component_count": self.flat_component_count,
            "large_flat_component_count": self.large_flat_component_count,
            "largest_flat_component_area": self.largest_flat_component_area,
            "valley_candidate_count": self.valley_candidate_count,
            "high_plateau_candidate_count": self.high_plateau_candidate_count,
            "pass_candidate_count": self.pass_candidate_count,
        }


@dataclass(frozen=True, slots=True)
class SettlementBudgets:
    """Upper limits for ordinary sites, buildings, and one landmark."""

    site_budget: int
    building_budget: int
    landmark_budget: int

    def to_dict(self) -> dict[str, int]:
        """Return JSON-serializable budget values."""
        return {
            "site_budget": self.site_budget,
            "building_budget": self.building_budget,
            "landmark_budget": self.landmark_budget,
        }


@dataclass(frozen=True, slots=True)
class SettlementRegionArea:
    """Broad historical settlement area used to cluster ordinary sites."""

    region_id: int
    center_x: int
    center_y: int
    radius: int
    foundation_level: int
    source_component_area: int

    def contains(self, x: int, y: int) -> bool:
        """Return whether one point lies inside this broad area."""
        return math.hypot(x - self.center_x, y - self.center_y) <= self.radius

    def to_dict(self) -> dict[str, int]:
        """Return JSON-serializable area metadata."""
        return {
            "id": self.region_id,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "radius": self.radius,
            "foundation_level": self.foundation_level,
            "source_component_area": self.source_component_area,
        }


@dataclass(frozen=True, slots=True)
class LandmarkReservation:
    """Reserved location for a future elevation-specific landmark."""

    landmark_type: str
    center_x: int
    center_y: int
    elevation: int
    footprint_radius: int
    access_x: int
    access_y: int
    selection_reason: str

    def to_dict(self) -> dict[str, object]:
        """Return JSON-serializable landmark reservation."""
        return {
            "type": self.landmark_type,
            "center": [self.center_x, self.center_y],
            "elevation": self.elevation,
            "footprint_radius": self.footprint_radius,
            "access_anchor": [self.access_x, self.access_y],
            "selection_reason": self.selection_reason,
        }


def analyze_settlement_terrain(
    guidance: TerrainGuidance | None,
    *,
    width: int,
    height: int,
) -> SettlementTerrainContext:
    """Analyze exact-level buildable components and terrain roughness.

    Args:
        guidance: Optional geography guidance.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        Stable settlement terrain context.
    """
    area = max(1, width * height)
    if guidance is None:
        component = FlatComponent(area, 0, width // 2, height // 2, 0, 0, width - 1, height - 1)
        return SettlementTerrainContext(
            elevation_style="normal",
            elevation_min=0,
            elevation_max=0,
            buildable_tile_ratio=1.0,
            comfortable_tile_ratio=1.0,
            rough_tile_ratio=0.0,
            cliff_tile_ratio=0.0,
            flat_component_count=1,
            large_flat_component_count=1,
            largest_flat_component_area=area,
            valley_candidate_count=1,
            high_plateau_candidate_count=0,
            pass_candidate_count=0,
            flat_components=(component,),
            high_plateau_components=(),
            valley_components=(component,),
        )

    levels = _integer_levels(guidance, width=width, height=height)
    deltas = _integer_deltas(guidance, width=width, height=height)
    flat_components = _flat_components(levels, deltas, width=width, height=height)
    sorted_components = tuple(
        sorted(
            flat_components,
            key=lambda item: (
                -item.area,
                item.level,
                item.center_y,
                item.center_x,
            ),
        )
    )

    flat_levels = [level for row in levels for level in row]
    elevation_min = min(flat_levels, default=0)
    elevation_max = max(flat_levels, default=0)
    buildable = sum(
        1
        for y in range(height)
        for x in range(width)
        if levels[y][x] >= 0 and deltas[y][x] <= 1
    )
    comfortable = sum(1 for row in deltas for value in row if value <= 1)
    rough = sum(1 for row in deltas for value in row if value >= 2)
    cliffs = sum(1 for row in deltas for value in row if value > 2)

    large_threshold = max(96, area // 1200)
    large_components = tuple(item for item in sorted_components if item.area >= large_threshold)
    positive_levels = sorted(value for value in flat_levels if value >= 0)
    high_threshold = _percentile(positive_levels, 0.76) if positive_levels else 0
    low_threshold = _percentile(positive_levels, 0.34) if positive_levels else 0
    plateau_threshold = max(128, area // 1400)
    valley_threshold = max(160, area // 1000)
    high_plateaus = tuple(
        item
        for item in sorted_components
        if item.area >= plateau_threshold and item.level >= high_threshold and item.level >= 2
    )
    valleys = tuple(
        item
        for item in sorted_components
        if item.area >= valley_threshold and 0 <= item.level <= low_threshold
    )

    return SettlementTerrainContext(
        elevation_style=guidance.elevation_style,
        elevation_min=elevation_min,
        elevation_max=elevation_max,
        buildable_tile_ratio=buildable / area,
        comfortable_tile_ratio=comfortable / area,
        rough_tile_ratio=rough / area,
        cliff_tile_ratio=cliffs / area,
        flat_component_count=len(sorted_components),
        large_flat_component_count=len(large_components),
        largest_flat_component_area=sorted_components[0].area if sorted_components else 0,
        valley_candidate_count=len(valleys),
        high_plateau_candidate_count=len(high_plateaus),
        pass_candidate_count=_pass_candidate_count(levels, deltas, width=width, height=height),
        flat_components=sorted_components[:32],
        high_plateau_components=high_plateaus[:12],
        valley_components=valleys[:12],
    )


def select_settlement_profile(
    context: SettlementTerrainContext,
    *,
    seed: int,
) -> SettlementProfile:
    """Select one settlement pattern from elevation style and actual terrain."""
    style = context.elevation_style
    if context.buildable_tile_ratio < 0.08 or context.largest_flat_component_area < 80:
        return SettlementProfile.SPARSE_FRONTIER
    if style == "super_flatland":
        return SettlementProfile.OPEN_PLAIN
    if style == "flatland":
        return (
            SettlementProfile.SPARSE_FRONTIER
            if _stable_percent(seed, "flatland_sparse") < 10
            else SettlementProfile.RURAL_PLAIN
        )
    if style == "rolling_hills":
        return (
            SettlementProfile.ROLLING_VALLEYS
            if context.valley_candidate_count > 0
            else SettlementProfile.SPARSE_FRONTIER
        )
    if style == "rugged":
        return SettlementProfile.RUGGED_OUTPOSTS
    if style == "mountainous":
        return (
            SettlementProfile.MOUNTAIN_STRONGHOLD
            if context.high_plateau_candidate_count > 0
            else SettlementProfile.RUGGED_OUTPOSTS
        )
    if style == "plateau":
        return (
            SettlementProfile.PLATEAU_SETTLEMENT
            if context.high_plateau_candidate_count > 0
            else SettlementProfile.SPARSE_FRONTIER
        )
    if context.rough_tile_ratio >= 0.38:
        return SettlementProfile.RUGGED_OUTPOSTS
    if context.valley_candidate_count > 0 and context.rough_tile_ratio >= 0.14:
        return SettlementProfile.ROLLING_VALLEYS
    return SettlementProfile.RURAL_PLAIN


def allocate_settlement_budgets(
    context: SettlementTerrainContext,
    profile: SettlementProfile,
    *,
    width: int,
    height: int,
    ruins_scale: float,
    buildings_scale: float,
    seed: int,
) -> SettlementBudgets:
    """Return nonlinear upper limits for sites, buildings, and landmarks."""
    if ruins_scale <= 0.0 or buildings_scale <= 0.0:
        return SettlementBudgets(0, 0, 0)

    reference = {
        SettlementProfile.OPEN_PLAIN: (7, 24),
        SettlementProfile.RURAL_PLAIN: (6, 20),
        SettlementProfile.ROLLING_VALLEYS: (5, 17),
        SettlementProfile.RUGGED_OUTPOSTS: (4, 12),
        SettlementProfile.MOUNTAIN_STRONGHOLD: (3, 10),
        SettlementProfile.PLATEAU_SETTLEMENT: (4, 14),
        SettlementProfile.SPARSE_FRONTIER: (3, 8),
    }[profile]
    linear_scale = math.sqrt(max(0.01, width * height / float(400 * 400)))
    density_scale = math.sqrt(max(0.0, ruins_scale))
    terrain_factor = max(0.55, min(1.08, 0.72 + context.buildable_tile_ratio * 0.55))
    site_jitter = -1 if _stable_percent(seed, f"{profile.value}:site") < 28 else 0
    site_budget = max(
        1,
        round(reference[0] * linear_scale * density_scale * terrain_factor) + site_jitter,
    )
    building_budget = max(
        site_budget,
        round(
            reference[1]
            * linear_scale
            * max(0.0, ruins_scale)
            * max(0.0, buildings_scale)
            * terrain_factor
        ),
    )
    landmark_budget = int(
        profile in {SettlementProfile.MOUNTAIN_STRONGHOLD, SettlementProfile.PLATEAU_SETTLEMENT}
        and context.high_plateau_candidate_count > 0
    )
    if landmark_budget:
        ordinary_reduction = 0.78 if profile == SettlementProfile.MOUNTAIN_STRONGHOLD else 0.86
        site_budget = max(2, round(site_budget * ordinary_reduction))
        building_budget = max(site_budget, round(building_budget * ordinary_reduction))
    return SettlementBudgets(
        site_budget=min(site_budget, 20),
        building_budget=min(building_budget, 80),
        landmark_budget=landmark_budget,
    )


def site_kind_sequence(
    profile: SettlementProfile,
    *,
    site_budget: int,
    valley_candidates: int,
) -> tuple[str, ...]:
    """Return ordered ordinary site archetypes within one upper limit."""
    if site_budget <= 0:
        return ()
    base: list[str]
    if profile == SettlementProfile.OPEN_PLAIN:
        base = [
            "village",
            "farmstead",
            "farmstead",
            "isolated_building",
            "outpost",
            "isolated_building",
        ]
        if site_budget >= 8:
            base.insert(1, "village")
    elif profile == SettlementProfile.RURAL_PLAIN:
        base = [
            "village",
            "farmstead",
            "isolated_building",
            "farmstead",
            "outpost",
            "isolated_building",
        ]
    elif profile == SettlementProfile.ROLLING_VALLEYS:
        base = (["village"] if valley_candidates > 0 and site_budget >= 4 else []) + [
            "farmstead",
            "outpost",
            "isolated_building",
            "farmstead",
        ]
    elif profile == SettlementProfile.RUGGED_OUTPOSTS:
        base = ["outpost", "farmstead", "isolated_building", "outpost", "isolated_building"]
    elif profile == SettlementProfile.MOUNTAIN_STRONGHOLD:
        base = ["outpost", "farmstead", "isolated_building", "outpost"]
    elif profile == SettlementProfile.PLATEAU_SETTLEMENT:
        base = ["village", "outpost", "farmstead", "isolated_building"]
    else:
        base = ["farmstead", "isolated_building", "outpost", "isolated_building"]

    fallback = ("isolated_building", "farmstead", "outpost")
    cursor = 0
    while len(base) < site_budget:
        base.append(fallback[cursor % len(fallback)])
        cursor += 1
    return tuple(base[:site_budget])


def select_settlement_regions(
    context: SettlementTerrainContext,
    profile: SettlementProfile,
    *,
    width: int,
    height: int,
    seed: int,
) -> tuple[SettlementRegionArea, ...]:
    """Choose one or two broad settlement areas from flat components."""
    dense_profiles = {
        SettlementProfile.OPEN_PLAIN,
        SettlementProfile.RURAL_PLAIN,
        SettlementProfile.ROLLING_VALLEYS,
    }
    max_regions = 2 if profile in dense_profiles and min(width, height) >= 300 else 1
    preferred = _preferred_components(context, profile)
    selected: list[FlatComponent] = []
    minimum_distance = min(width, height) * 0.32
    for component in preferred:
        if any(
            math.hypot(
                component.center_x - other.center_x,
                component.center_y - other.center_y,
            )
            < minimum_distance
            for other in selected
        ):
            continue
        selected.append(component)
        if len(selected) >= max_regions:
            break

    if not selected:
        selected = [
            FlatComponent(
                width * height,
                0,
                width // 2,
                height // 2,
                0,
                0,
                width - 1,
                height - 1,
            )
        ]

    output: list[SettlementRegionArea] = []
    minimum_radius = max(28, round(min(width, height) * 0.15))
    maximum_radius = max(minimum_radius, round(min(width, height) * 0.25))
    for index, component in enumerate(selected):
        center_x, center_y = _component_region_center(
            component,
            width=width,
            height=height,
            seed=seed,
            index=index,
        )
        natural_radius = round(math.sqrt(max(1, component.area) / math.pi) * 0.85)
        radius = max(minimum_radius, min(natural_radius, maximum_radius))
        output.append(
            SettlementRegionArea(
                region_id=index,
                center_x=center_x,
                center_y=center_y,
                radius=radius,
                foundation_level=component.level,
                source_component_area=component.area,
            )
        )
    return tuple(output)


def reserve_landmark(
    context: SettlementTerrainContext,
    profile: SettlementProfile,
    *,
    budget: int,
    width: int,
    height: int,
) -> LandmarkReservation | None:
    """Reserve a future landmark without carving its architecture."""
    if budget <= 0 or not context.high_plateau_components:
        return None
    component = context.high_plateau_components[0]
    landmark_type = (
        "mountain_fortress"
        if profile == SettlementProfile.MOUNTAIN_STRONGHOLD
        else "plateau_fortress"
    )
    radius = max(14, min(30, round(math.sqrt(component.area / math.pi) * 0.55)))
    access_x = component.center_x
    access_y = min(height - 2, component.center_y + radius + 2)
    return LandmarkReservation(
        landmark_type=landmark_type,
        center_x=max(1, min(width - 2, component.center_x)),
        center_y=max(1, min(height - 2, component.center_y)),
        elevation=component.level,
        footprint_radius=radius,
        access_x=max(1, min(width - 2, access_x)),
        access_y=max(1, min(height - 2, access_y)),
        selection_reason="largest_high_flat_component",
    )


def _integer_levels(
    guidance: TerrainGuidance,
    *,
    width: int,
    height: int,
) -> tuple[tuple[int, ...], ...]:
    if guidance.natural_level_rows is not None:
        return guidance.natural_level_rows
    return tuple(
        tuple(round(guidance.elevation_at(x, y) * 10.0) for x in range(width))
        for y in range(height)
    )


def _integer_deltas(
    guidance: TerrainGuidance,
    *,
    width: int,
    height: int,
) -> tuple[tuple[int, ...], ...]:
    if guidance.natural_slope_rows is not None:
        return guidance.natural_slope_rows
    return tuple(
        tuple(guidance.natural_delta_at(x, y) for x in range(width))
        for y in range(height)
    )


def _flat_components(
    levels: tuple[tuple[int, ...], ...],
    deltas: tuple[tuple[int, ...], ...],
    *,
    width: int,
    height: int,
) -> list[FlatComponent]:
    visited = bytearray(width * height)
    output: list[FlatComponent] = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or levels[y][x] < 0 or deltas[y][x] > 1:
                continue
            level = levels[y][x]
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited[index] = 1
            area = 0
            sum_x = 0
            sum_y = 0
            left = right = x
            top = bottom = y
            while queue:
                cx, cy = queue.popleft()
                area += 1
                sum_x += cx
                sum_y += cy
                left = min(left, cx)
                right = max(right, cx)
                top = min(top, cy)
                bottom = max(bottom, cy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx = cx + dx
                    ny = cy + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    neighbor_index = ny * width + nx
                    if visited[neighbor_index]:
                        continue
                    if levels[ny][nx] != level or deltas[ny][nx] > 1:
                        continue
                    visited[neighbor_index] = 1
                    queue.append((nx, ny))
            output.append(
                FlatComponent(
                    area=area,
                    level=level,
                    center_x=round(sum_x / area),
                    center_y=round(sum_y / area),
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                )
            )
    return output


def _pass_candidate_count(
    levels: tuple[tuple[int, ...], ...],
    deltas: tuple[tuple[int, ...], ...],
    *,
    width: int,
    height: int,
) -> int:
    count = 0
    step = max(4, min(width, height) // 80)
    for y in range(step, height - step, step):
        for x in range(step, width - step, step):
            if deltas[y][x] > 1 or levels[y][x] < 0:
                continue
            horizontal_rough = deltas[y][x - step] >= 2 and deltas[y][x + step] >= 2
            vertical_rough = deltas[y - step][x] >= 2 and deltas[y + step][x] >= 2
            if horizontal_rough or vertical_rough:
                count += 1
    return count


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    index = max(0, min(len(values) - 1, round((len(values) - 1) * fraction)))
    return values[index]


def _stable_percent(seed: int, salt: str) -> int:
    digest = hashlib.blake2b(f"{seed}:{salt}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % 100


def _preferred_components(
    context: SettlementTerrainContext,
    profile: SettlementProfile,
) -> tuple[FlatComponent, ...]:
    if profile == SettlementProfile.MOUNTAIN_STRONGHOLD:
        landmark = context.high_plateau_components[:1]
        ordinary = tuple(
            component
            for component in context.flat_components
            if component not in landmark
        )
        if context.valley_components:
            return context.valley_components + ordinary
        return ordinary
    if profile == SettlementProfile.PLATEAU_SETTLEMENT:
        landmark = context.high_plateau_components[:1]
        secondary_plateaus = context.high_plateau_components[1:]
        ordinary = tuple(
            component
            for component in context.flat_components
            if component not in landmark
        )
        return context.valley_components + secondary_plateaus + ordinary
    if profile == SettlementProfile.ROLLING_VALLEYS and context.valley_components:
        return context.valley_components + context.flat_components
    return context.flat_components


def _component_region_center(
    component: FlatComponent,
    *,
    width: int,
    height: int,
    seed: int,
    index: int,
) -> tuple[int, int]:
    if component.area < width * height * 0.55:
        return component.center_x, component.center_y
    x_percent = 30 + _stable_percent(seed, f"settlement_region_x:{index}") % 41
    y_percent = 30 + _stable_percent(seed, f"settlement_region_y:{index}") % 41
    return round(width * x_percent / 100), round(height * y_percent / 100)
