"""Deterministic architecture and connected destruction for ruin buildings."""

from __future__ import annotations

import hashlib
import random
from collections import deque
from dataclasses import dataclass
from enum import StrEnum

PointTuple = tuple[int, int]
RectTuple = tuple[int, int, int, int]
_HEIGHT_MIN = 1
_HEIGHT_MAX = 3
_NEIGHBORS: tuple[PointTuple, ...] = ((0, -1), (-1, 0), (1, 0), (0, 1))
_SEVERITY_TARGETS: dict[str, tuple[float, float]] = {
    "light": (0.14, 0.86),
    "moderate": (0.23, 0.76),
    "heavy": (0.34, 0.66),
}
_SEVERITY_LIMITS: dict[str, tuple[float, float, float, float, int, float, float]] = {
    "light": (0.08, 0.24, 0.72, 0.98, 5, 0.40, 0.50),
    "moderate": (0.14, 0.34, 0.57, 0.92, 5, 0.38, 0.35),
    "heavy": (0.24, 0.46, 0.40, 0.85, 6, 0.35, 0.20),
}


class BuildingArchetype(StrEnum):
    """Supported first-generation building archetypes."""

    SMALL_HOUSE = "small_house"
    LONG_HOUSE = "long_house"
    BARN = "barn"
    WAREHOUSE = "warehouse"
    OUTPOST_BUILDING = "outpost_building"


class DamagePattern(StrEnum):
    """Connected destruction patterns applied to intact architecture."""

    COLLAPSED_CORNER = "collapsed_corner"
    DAMAGED_FACADE = "damaged_facade"
    SIDE_COLLAPSE = "side_collapse"
    CENTRAL_BREACH = "central_breach"
    WEATHERED_DECAY = "weathered_decay"


@dataclass(frozen=True, slots=True)
class RoomPlan:
    """One approximate room rectangle inside a building."""

    room_id: int
    rect: RectTuple

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible room metadata."""
        left, top, right, bottom = self.rect
        return {
            "id": self.room_id,
            "rect": {
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
            },
        }


@dataclass(frozen=True, slots=True)
class WallRun:
    """One surviving straight wall segment."""

    run_id: int
    role: str
    orientation: str
    points: tuple[PointTuple, ...]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible wall-run metadata."""
        return {
            "id": self.run_id,
            "role": self.role,
            "orientation": self.orientation,
            "points": [[x, y] for x, y in self.points],
        }


@dataclass(frozen=True, slots=True)
class ArchitectureMetrics:
    """Quality metrics for one destroyed architecture candidate."""

    intact_wall_tiles: int
    surviving_wall_tiles: int
    wall_destroyed_ratio: float
    outer_wall_retained_ratio: float
    connected_wall_components: int
    isolated_wall_tiles: int
    retained_corners: int
    longest_straight_run: int
    entrance_or_breach_count: int
    accessible_floor_ratio: float
    maximum_adjacent_height_delta: int
    largest_component_ratio: float
    surviving_inner_wall_ratio: float
    window_sill_hint_count: int
    planned_floor_tiles: int
    score: float

    def to_dict(self) -> dict[str, int | float]:
        """Return JSON-compatible quality metrics."""
        return {
            "intact_wall_tiles": self.intact_wall_tiles,
            "surviving_wall_tiles": self.surviving_wall_tiles,
            "wall_destroyed_ratio": round(self.wall_destroyed_ratio, 6),
            "outer_wall_retained_ratio": round(
                self.outer_wall_retained_ratio,
                6,
            ),
            "connected_wall_components": self.connected_wall_components,
            "isolated_wall_tiles": self.isolated_wall_tiles,
            "retained_corners": self.retained_corners,
            "longest_straight_run": self.longest_straight_run,
            "entrance_or_breach_count": self.entrance_or_breach_count,
            "accessible_floor_ratio": round(self.accessible_floor_ratio, 6),
            "maximum_adjacent_height_delta": (
                self.maximum_adjacent_height_delta
            ),
            "largest_component_ratio": round(
                self.largest_component_ratio,
                6,
            ),
            "surviving_inner_wall_ratio": round(
                self.surviving_inner_wall_ratio,
                6,
            ),
            "window_sill_hint_count": self.window_sill_hint_count,
            "planned_floor_tiles": self.planned_floor_tiles,
            "score": round(self.score, 6),
        }


@dataclass(frozen=True, slots=True)
class RuinArchitecturePlan:
    """Complete destroyed architecture plan for one building footprint."""

    archetype: BuildingArchetype
    damage_pattern: DamagePattern
    destruction_direction: str
    destruction_severity: str
    rooms: tuple[RoomPlan, ...]
    external_door: PointTuple
    internal_doors: tuple[PointTuple, ...]
    window_sill_hints: tuple[PointTuple, ...]
    wall_runs: tuple[WallRun, ...]
    wall_heights: tuple[tuple[int, int, int], ...]
    metrics: ArchitectureMetrics

    @property
    def wall_points(self) -> frozenset[PointTuple]:
        """Return all surviving wall coordinates."""
        return frozenset((x, y) for x, y, _height in self.wall_heights)

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible architecture metadata."""
        return {
            "schema_version": "ruin-building-architecture-v2",
            "archetype": self.archetype.value,
            "damage_pattern": self.damage_pattern.value,
            "destruction_direction": self.destruction_direction,
            "destruction_severity": self.destruction_severity,
            "external_door": [self.external_door[0], self.external_door[1]],
            "internal_doors": [[x, y] for x, y in self.internal_doors],
            "window_sill_hints": [
                [x, y] for x, y in self.window_sill_hints
            ],
            "rooms": [room.to_dict() for room in self.rooms],
            "wall_runs": [run.to_dict() for run in self.wall_runs],
            "wall_heights": [
                [x, y, height] for x, y, height in self.wall_heights
            ],
            "metrics": self.metrics.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class _IntactPlan:
    archetype: BuildingArchetype
    wall_roles: dict[PointTuple, str]
    rooms: tuple[RoomPlan, ...]
    internal_doors: tuple[PointTuple, ...]
    outer_points: frozenset[PointTuple]
    corners: frozenset[PointTuple]


@dataclass(frozen=True, slots=True)
class _Candidate:
    plan: RuinArchitecturePlan
    valid: bool


def generate_ruin_architecture(
    *,
    rect: RectTuple,
    entrance: PointTuple,
    site_kind: str,
    building_id: int,
    is_main: bool,
    orientation: str,
    destruction_direction: str,
    destruction_severity: str,
    resolved_seed: int,
    site_id: int,
) -> RuinArchitecturePlan:
    """Generate the best deterministic architecture and destruction candidate.

    Args:
        rect: Inclusive building rectangle.
        entrance: Planned external door on the rectangle boundary.
        site_kind: Semantic ruin-site kind.
        building_id: Building identifier within the site.
        is_main: Whether this is the main site building.
        orientation: Shared site orientation.
        destruction_direction: Shared site destruction direction.
        destruction_severity: Shared site destruction severity.
        resolved_seed: Concrete world seed.
        site_id: Semantic site identifier.

    Returns:
        Best valid deterministic architecture plan.
    """
    archetype = _select_archetype(
        rect=rect,
        site_kind=site_kind,
        building_id=building_id,
        is_main=is_main,
        resolved_seed=resolved_seed,
        site_id=site_id,
    )
    intact = _build_intact_plan(
        rect=rect,
        entrance=entrance,
        archetype=archetype,
        orientation=orientation,
    )
    patterns = tuple(DamagePattern)
    candidates: list[_Candidate] = []
    for variant in range(6):
        rng = random.Random(
            _stable_seed(
                resolved_seed,
                site_id,
                building_id,
                variant,
                "ruin_architecture",
            )
        )
        pattern = patterns[
            (_stable_seed(
                resolved_seed,
                site_id,
                building_id,
                0,
                "damage_pattern",
            ) + variant)
            % len(patterns)
        ]
        candidates.append(
            _build_candidate(
                rect=rect,
                entrance=entrance,
                intact=intact,
                pattern=pattern,
                direction=destruction_direction,
                severity=destruction_severity,
                rng=rng,
            )
        )

    valid = [candidate for candidate in candidates if candidate.valid]
    if valid:
        return max(valid, key=lambda candidate: candidate.plan.metrics.score).plan
    fallback = _build_fallback_candidate(
        rect=rect,
        entrance=entrance,
        intact=intact,
        direction=destruction_direction,
        severity=destruction_severity,
    )
    return fallback.plan


def architecture_plan_is_valid(plan: RuinArchitecturePlan) -> bool:
    """Return whether a generated architecture plan meets hard invariants."""
    metrics = plan.metrics
    limits = _SEVERITY_LIMITS.get(plan.destruction_severity)
    if limits is None:
        return False
    (
        destroyed_min,
        destroyed_max,
        outer_min,
        outer_max,
        component_max,
        largest_component_min,
        inner_retained_min,
    ) = limits
    return (
        metrics.surviving_wall_tiles >= 6
        and metrics.isolated_wall_tiles == 0
        and metrics.retained_corners >= 2
        and metrics.longest_straight_run >= 3
        and metrics.entrance_or_breach_count >= 1
        and metrics.accessible_floor_ratio >= 0.78
        and metrics.maximum_adjacent_height_delta <= 1
        and destroyed_min
        <= metrics.wall_destroyed_ratio
        <= destroyed_max
        and outer_min
        <= metrics.outer_wall_retained_ratio
        <= outer_max
        and metrics.connected_wall_components <= component_max
        and metrics.largest_component_ratio >= largest_component_min
        and metrics.surviving_inner_wall_ratio >= inner_retained_min
        and metrics.planned_floor_tiles > 0
    )


def _select_archetype(
    *,
    rect: RectTuple,
    site_kind: str,
    building_id: int,
    is_main: bool,
    resolved_seed: int,
    site_id: int,
) -> BuildingArchetype:
    left, top, right, bottom = rect
    width = right - left + 1
    height = bottom - top + 1
    roll = _stable_seed(
        resolved_seed,
        site_id,
        building_id,
        0,
        "building_archetype",
    ) % 100
    if site_kind == "outpost":
        return BuildingArchetype.OUTPOST_BUILDING
    if site_kind == "farmstead":
        if is_main:
            return (
                BuildingArchetype.LONG_HOUSE
                if max(width, height) >= 11
                else BuildingArchetype.SMALL_HOUSE
            )
        return BuildingArchetype.BARN
    if site_kind == "village":
        if is_main and min(width, height) >= 8:
            return BuildingArchetype.WAREHOUSE if roll < 45 else BuildingArchetype.LONG_HOUSE
        if roll < 68:
            return BuildingArchetype.SMALL_HOUSE
        if roll < 88:
            return BuildingArchetype.LONG_HOUSE
        return BuildingArchetype.BARN
    if max(width, height) >= 11 and roll < 55:
        return BuildingArchetype.LONG_HOUSE
    return BuildingArchetype.SMALL_HOUSE


def _build_intact_plan(
    *,
    rect: RectTuple,
    entrance: PointTuple,
    archetype: BuildingArchetype,
    orientation: str,
) -> _IntactPlan:
    left, top, right, bottom = rect
    wall_roles: dict[PointTuple, str] = {}
    outer_points: set[PointTuple] = set()
    for x in range(left, right + 1):
        for y in (top, bottom):
            point = (x, y)
            wall_roles[point] = "outer_wall"
            outer_points.add(point)
    for y in range(top, bottom + 1):
        for x in (left, right):
            point = (x, y)
            wall_roles[point] = "outer_wall"
            outer_points.add(point)
    corners = frozenset(
        {
            (left, top),
            (right, top),
            (left, bottom),
            (right, bottom),
        }
    )
    for corner in corners:
        wall_roles[corner] = "corner"
    wall_roles.pop(entrance, None)

    internal_doors: list[PointTuple] = []
    rooms: list[RoomPlan] = []
    partitions = _partition_lines(
        rect=rect,
        archetype=archetype,
        orientation=orientation,
    )
    for partition_id, points in enumerate(partitions):
        if len(points) < 3:
            continue
        if len(partitions) > 1:
            fraction = 1 if partition_id % 2 == 0 else 2
            door = points[max(1, min(len(points) - 2, len(points) * fraction // 3))]
        else:
            door = points[len(points) // 2]
        internal_doors.append(door)
        for point in points:
            if point in {door, entrance}:
                continue
            wall_roles.setdefault(point, "inner_wall")
    inside_entrance = _inside_boundary_neighbor(rect, entrance)
    if inside_entrance is not None:
        wall_roles.pop(inside_entrance, None)
        if inside_entrance not in internal_doors:
            internal_doors.append(inside_entrance)
    rooms.extend(_approximate_rooms(rect, partitions))
    if not rooms:
        rooms.append(RoomPlan(0, (left + 1, top + 1, right - 1, bottom - 1)))
    return _IntactPlan(
        archetype=archetype,
        wall_roles=wall_roles,
        rooms=tuple(rooms),
        internal_doors=tuple(internal_doors),
        outer_points=frozenset(outer_points - {entrance}),
        corners=corners,
    )


def _partition_lines(
    *,
    rect: RectTuple,
    archetype: BuildingArchetype,
    orientation: str,
) -> list[list[PointTuple]]:
    left, top, right, bottom = rect
    inner_width = right - left - 1
    inner_height = bottom - top - 1
    partitions: list[list[PointTuple]] = []
    if inner_width < 4 or inner_height < 3:
        return partitions

    long_horizontal = orientation == "east_west"
    if archetype == BuildingArchetype.SMALL_HOUSE:
        if inner_width >= 6 and inner_height >= 4:
            if long_horizontal:
                x = left + 1 + inner_width * 2 // 3
                partitions.append([(x, y) for y in range(top, bottom + 1)])
            else:
                y = top + 1 + inner_height * 2 // 3
                partitions.append([(x, y) for x in range(left, right + 1)])
    elif archetype == BuildingArchetype.LONG_HOUSE:
        count = 2 if max(inner_width, inner_height) >= 9 else 1
        for index in range(1, count + 1):
            if long_horizontal:
                x = left + 1 + inner_width * index // (count + 1)
                partitions.append([(x, y) for y in range(top, bottom + 1)])
            else:
                y = top + 1 + inner_height * index // (count + 1)
                partitions.append([(x, y) for x in range(left, right + 1)])
    elif archetype == BuildingArchetype.BARN:
        if min(inner_width, inner_height) >= 5:
            if long_horizontal:
                x = left + 1 + inner_width * 3 // 4
                start = top + 1
                end = min(bottom, start + max(3, inner_height // 2))
                partitions.append([(x, y) for y in range(start, end)])
            else:
                y = top + 1 + inner_height * 3 // 4
                start = left + 1
                end = min(right, start + max(3, inner_width // 2))
                partitions.append([(x, y) for x in range(start, end)])
    elif archetype == BuildingArchetype.WAREHOUSE:
        if long_horizontal:
            x = left + 1 + inner_width * 2 // 3
            partitions.append([(x, y) for y in range(top, bottom + 1)])
        else:
            y = top + 1 + inner_height * 2 // 3
            partitions.append([(x, y) for x in range(left, right + 1)])
    else:
        x = (left + right) // 2
        y = (top + bottom) // 2
        if inner_height >= 5:
            partitions.append([(x, item_y) for item_y in range(top, bottom + 1)])
        if inner_width >= 6:
            partitions.append([(item_x, y) for item_x in range(left, right + 1)])
    return partitions


def _approximate_rooms(
    rect: RectTuple,
    partitions: list[list[PointTuple]],
) -> list[RoomPlan]:
    left, top, right, bottom = rect
    verticals = sorted(
        {points[0][0] for points in partitions if points and len({x for x, _y in points}) == 1}
    )
    horizontals = sorted(
        {points[0][1] for points in partitions if points and len({_y for _x, _y in points}) == 1}
    )
    x_boundaries = [left + 1, *verticals, right]
    y_boundaries = [top + 1, *horizontals, bottom]
    rooms: list[RoomPlan] = []
    room_id = 0
    for y_index in range(len(y_boundaries) - 1):
        room_top = y_boundaries[y_index]
        room_bottom = y_boundaries[y_index + 1] - 1
        if y_index == len(y_boundaries) - 2:
            room_bottom = bottom - 1
        for x_index in range(len(x_boundaries) - 1):
            room_left = x_boundaries[x_index]
            room_right = x_boundaries[x_index + 1] - 1
            if x_index == len(x_boundaries) - 2:
                room_right = right - 1
            if room_left <= room_right and room_top <= room_bottom:
                rooms.append(
                    RoomPlan(
                        room_id,
                        (room_left, room_top, room_right, room_bottom),
                    )
                )
                room_id += 1
    return rooms


def _build_candidate(
    *,
    rect: RectTuple,
    entrance: PointTuple,
    intact: _IntactPlan,
    pattern: DamagePattern,
    direction: str,
    severity: str,
    rng: random.Random,
) -> _Candidate:
    walls = set(intact.wall_roles)
    removed: set[PointTuple] = set()
    _apply_damage(
        rect=rect,
        entrance=entrance,
        walls=walls,
        removed=removed,
        pattern=pattern,
        direction=direction,
        severity=severity,
        rng=rng,
    )
    _ensure_damage_targets(
        rect=rect,
        walls=walls,
        removed=removed,
        intact=intact,
        direction=direction,
        severity=severity,
        rng=rng,
    )
    walls = _remove_isolated_walls(walls)
    removed.update(set(intact.wall_roles) - walls)
    heights = _assign_heights(walls, removed)
    window_sill_hints = _apply_window_sill_hints(
        intact=intact,
        walls=walls,
        heights=heights,
        removed=removed,
        entrance=entrance,
        rng=rng,
    )
    wall_runs = _build_wall_runs(walls, intact.wall_roles)
    metrics = _build_metrics(
        rect=rect,
        entrance=entrance,
        intact=intact,
        walls=walls,
        heights=heights,
        removed=removed,
        wall_runs=wall_runs,
        window_sill_hints=window_sill_hints,
        severity=severity,
    )
    plan = RuinArchitecturePlan(
        archetype=intact.archetype,
        damage_pattern=pattern,
        destruction_direction=direction,
        destruction_severity=severity,
        rooms=intact.rooms,
        external_door=entrance,
        internal_doors=intact.internal_doors,
        window_sill_hints=window_sill_hints,
        wall_runs=wall_runs,
        wall_heights=tuple(
            sorted((x, y, height) for (x, y), height in heights.items())
        ),
        metrics=metrics,
    )
    return _Candidate(plan=plan, valid=architecture_plan_is_valid(plan))


def _build_fallback_candidate(
    *,
    rect: RectTuple,
    entrance: PointTuple,
    intact: _IntactPlan,
    direction: str,
    severity: str,
) -> _Candidate:
    walls = set(intact.wall_roles)
    removed: set[PointTuple] = set()
    side = (
        direction
        if direction in {"north", "east", "south", "west"}
        else _side_for_point(rect, entrance)
    )
    sequence = _side_points(rect, side, include_corners=False)
    if sequence:
        length = max(2, min(4, len(sequence) // 2))
        start = max(0, (len(sequence) - length) // 2)
        _remove_points(walls, removed, sequence[start : start + length])
    _ensure_damage_targets(
        rect=rect,
        walls=walls,
        removed=removed,
        intact=intact,
        direction=direction,
        severity=severity,
        rng=random.Random(0),
    )
    walls = _remove_isolated_walls(walls)
    removed.update(set(intact.wall_roles) - walls)
    heights = _assign_heights(walls, removed)
    window_sill_hints = _apply_window_sill_hints(
        intact=intact,
        walls=walls,
        heights=heights,
        removed=removed,
        entrance=entrance,
        rng=random.Random(1),
    )
    wall_runs = _build_wall_runs(walls, intact.wall_roles)
    metrics = _build_metrics(
        rect=rect,
        entrance=entrance,
        intact=intact,
        walls=walls,
        heights=heights,
        removed=removed,
        wall_runs=wall_runs,
        window_sill_hints=window_sill_hints,
        severity=severity,
    )
    plan = RuinArchitecturePlan(
        archetype=intact.archetype,
        damage_pattern=DamagePattern.DAMAGED_FACADE,
        destruction_direction=direction,
        destruction_severity=severity,
        rooms=intact.rooms,
        external_door=entrance,
        internal_doors=intact.internal_doors,
        window_sill_hints=window_sill_hints,
        wall_runs=wall_runs,
        wall_heights=tuple(
            sorted((x, y, height) for (x, y), height in heights.items())
        ),
        metrics=metrics,
    )
    return _Candidate(plan=plan, valid=architecture_plan_is_valid(plan))


def _apply_damage(
    *,
    rect: RectTuple,
    entrance: PointTuple,
    walls: set[PointTuple],
    removed: set[PointTuple],
    pattern: DamagePattern,
    direction: str,
    severity: str,
    rng: random.Random,
) -> None:
    side = direction if direction in {"north", "east", "south", "west"} else "north"
    intensity = {
        "light": 0.55,
        "moderate": 0.78,
        "heavy": 1.0,
    }.get(severity, 0.78)
    if pattern == DamagePattern.COLLAPSED_CORNER:
        corner = _corner_for_direction(side)
        _damage_corner(rect, walls, removed, corner, intensity=intensity)
    elif pattern == DamagePattern.DAMAGED_FACADE:
        _damage_side_interval(
            rect,
            walls,
            removed,
            side,
            fraction=0.28 * intensity,
            rng=rng,
        )
    elif pattern == DamagePattern.SIDE_COLLAPSE:
        _damage_side_interval(
            rect,
            walls,
            removed,
            side,
            fraction=0.38 * intensity,
            rng=rng,
        )
    elif pattern == DamagePattern.CENTRAL_BREACH:
        _damage_side_interval(
            rect,
            walls,
            removed,
            side,
            fraction=0.24 * intensity,
            rng=rng,
            center_bias=True,
        )
    else:
        _damage_side_interval(
            rect,
            walls,
            removed,
            side,
            fraction=0.18 * intensity,
            rng=rng,
        )
        if severity == "heavy":
            second = _rotate_side(side, 1 if rng.random() < 0.5 else -1)
            _damage_side_interval(
                rect,
                walls,
                removed,
                second,
                fraction=0.12,
                rng=rng,
            )
    walls.discard(entrance)
    removed.add(entrance)


def _ensure_damage_targets(
    *,
    rect: RectTuple,
    walls: set[PointTuple],
    removed: set[PointTuple],
    intact: _IntactPlan,
    direction: str,
    severity: str,
    rng: random.Random,
) -> None:
    """Extend existing exterior breaches without scattering wall damage."""
    target_destroyed, target_outer_retained = _SEVERITY_TARGETS.get(
        severity,
        _SEVERITY_TARGETS["moderate"],
    )
    target_removed = max(2, round(len(intact.wall_roles) * target_destroyed))
    target_outer_count = round(len(intact.outer_points) * target_outer_retained)
    primary = direction if direction in {"north", "east", "south", "west"} else "north"
    side_step = 1 if rng.random() < 0.5 else -1
    sides = (
        primary,
        _rotate_side(primary, side_step),
        _rotate_side(primary, -side_step),
        _opposite_side(primary),
    )

    attempts = 0
    while len(removed) < target_removed and attempts < 32:
        side = sides[min(attempts // 8, len(sides) - 1)]
        sequence = [
            point
            for point in _side_points(rect, side, include_corners=False)
            if point in walls
        ]
        if not sequence:
            attempts += 1
            continue
        boundary_removed = set(_side_points(rect, side, include_corners=False)) & removed
        adjacent = [
            point
            for point in sequence
            if any(neighbor in boundary_removed for neighbor in _neighbors(point))
        ]
        candidates = adjacent or sequence
        point = candidates[rng.randrange(len(candidates))]
        walls.remove(point)
        removed.add(point)
        attempts += 1

    attempts = 0
    while (
        len(walls & set(intact.outer_points)) > target_outer_count
        and attempts < 24
    ):
        side = sides[min(attempts // 6, len(sides) - 1)]
        sequence = [
            point
            for point in _side_points(rect, side, include_corners=False)
            if point in walls
        ]
        if not sequence:
            attempts += 1
            continue
        boundary_removed = set(_side_points(rect, side, include_corners=False)) & removed
        adjacent = [
            point
            for point in sequence
            if any(neighbor in boundary_removed for neighbor in _neighbors(point))
        ]
        point = (adjacent or sequence)[rng.randrange(len(adjacent or sequence))]
        walls.remove(point)
        removed.add(point)
        attempts += 1


def _longest_line(points: set[PointTuple]) -> list[PointTuple]:
    """Return the longest horizontal or vertical contiguous point sequence."""
    best: list[PointTuple] = []
    for orientation in ("horizontal", "vertical"):
        ordered = sorted(points, key=lambda point: (point[1], point[0]))
        for start in ordered:
            sequence = [start]
            delta = (1, 0) if orientation == "horizontal" else (0, 1)
            current = start
            while True:
                candidate = (current[0] + delta[0], current[1] + delta[1])
                if candidate not in points:
                    break
                sequence.append(candidate)
                current = candidate
            if len(sequence) > len(best):
                best = sequence
    return best


def _damage_corner(
    rect: RectTuple,
    walls: set[PointTuple],
    removed: set[PointTuple],
    corner: str,
    *,
    intensity: float,
) -> None:
    left, top, right, bottom = rect
    if intensity < 0.70:
        length = 1
    elif intensity < 0.90:
        length = 2
    else:
        length = 3
    if corner == "north_west":
        points = [(left + offset, top) for offset in range(length)]
        points += [(left, top + offset) for offset in range(1, length)]
    elif corner == "north_east":
        points = [(right - offset, top) for offset in range(length)]
        points += [(right, top + offset) for offset in range(1, length)]
    elif corner == "south_west":
        points = [(left + offset, bottom) for offset in range(length)]
        points += [(left, bottom - offset) for offset in range(1, length)]
    else:
        points = [(right - offset, bottom) for offset in range(length)]
        points += [(right, bottom - offset) for offset in range(1, length)]
    _remove_points(walls, removed, points)


def _damage_side_interval(
    rect: RectTuple,
    walls: set[PointTuple],
    removed: set[PointTuple],
    side: str,
    *,
    fraction: float,
    rng: random.Random,
    center_bias: bool = False,
) -> None:
    sequence = _side_points(rect, side, include_corners=False)
    if not sequence:
        return
    length = max(2, min(len(sequence) - 1, round(len(sequence) * fraction)))
    if length <= 0:
        return
    if center_bias:
        start = max(0, (len(sequence) - length) // 2)
    else:
        start = rng.randint(0, max(0, len(sequence) - length))
    _remove_points(walls, removed, sequence[start : start + length])


def _damage_inner_run(
    walls: set[PointTuple],
    removed: set[PointTuple],
    rng: random.Random,
    *,
    fraction: float,
) -> None:
    inner = sorted(point for point in walls if _neighbor_count(walls, point) >= 2)
    if not inner:
        return
    start_point = inner[rng.randrange(len(inner))]
    same_x = [point for point in inner if point[0] == start_point[0]]
    same_y = [point for point in inner if point[1] == start_point[1]]
    sequence = max((same_x, same_y), key=len)
    if len(sequence) < 3:
        return
    sequence.sort(key=lambda point: (point[1], point[0]))
    length = max(1, min(len(sequence) - 1, round(len(sequence) * fraction)))
    start = rng.randint(0, max(0, len(sequence) - length))
    _remove_points(walls, removed, sequence[start : start + length])


def _remove_points(
    walls: set[PointTuple],
    removed: set[PointTuple],
    points: list[PointTuple],
) -> None:
    for point in points:
        if point in walls:
            walls.remove(point)
            removed.add(point)


def _remove_isolated_walls(walls: set[PointTuple]) -> set[PointTuple]:
    cleaned = set(walls)
    changed = True
    while changed:
        changed = False
        isolated = [point for point in cleaned if _neighbor_count(cleaned, point) == 0]
        if isolated:
            cleaned.difference_update(isolated)
            changed = True
    return cleaned


def _assign_heights(
    walls: set[PointTuple],
    removed: set[PointTuple],
) -> dict[PointTuple, int]:
    heights: dict[PointTuple, int] = {}
    for point in walls:
        distance = _distance_to_points(point, removed, maximum=3)
        if distance <= 1:
            value = 1
        elif distance == 2:
            value = 2
        else:
            value = 3
        if _neighbor_count(walls, point) <= 1:
            value = min(value, 2)
        heights[point] = value
    for _ in range(3):
        updated = dict(heights)
        for point, value in heights.items():
            neighbor_values = [
                heights[neighbor]
                for neighbor in _neighbors(point)
                if neighbor in heights
            ]
            if not neighbor_values:
                continue
            lower = min(neighbor_values)
            upper = max(neighbor_values)
            if value > lower + 1:
                value = lower + 1
            elif value < upper - 1:
                value = upper - 1
            updated[point] = max(_HEIGHT_MIN, min(_HEIGHT_MAX, value))
        heights = updated
    return heights


def _apply_window_sill_hints(
    *,
    intact: _IntactPlan,
    walls: set[PointTuple],
    heights: dict[PointTuple, int],
    removed: set[PointTuple],
    entrance: PointTuple,
    rng: random.Random,
) -> tuple[PointTuple, ...]:
    """Lower selected preserved facade cells to suggest window sills.

    The current vertical format stores one solid height per wall tile, so these
    hints are intentionally not true openings. They preserve a low wall cell
    between taller facade cells and can later be upgraded by a voxel occupancy
    layer without changing the building plan.
    """
    maximum = {
        BuildingArchetype.SMALL_HOUSE: 1,
        BuildingArchetype.LONG_HOUSE: 2,
        BuildingArchetype.BARN: 0,
        BuildingArchetype.WAREHOUSE: 1,
        BuildingArchetype.OUTPOST_BUILDING: 1,
    }[intact.archetype]
    if maximum <= 0:
        return ()

    candidates: list[PointTuple] = []
    for point in sorted(walls & set(intact.outer_points)):
        if point in intact.corners or point == entrance:
            continue
        if _distance_to_points(point, removed, maximum=3) <= 2:
            continue
        if abs(point[0] - entrance[0]) + abs(point[1] - entrance[1]) <= 2:
            continue
        x, y = point
        horizontal = (x - 1, y) in walls and (x + 1, y) in walls
        vertical = (x, y - 1) in walls and (x, y + 1) in walls
        if not horizontal and not vertical:
            continue
        if heights.get(point, 0) < 2:
            continue
        candidates.append(point)

    if not candidates:
        return ()
    rng.shuffle(candidates)
    selected: list[PointTuple] = []
    for point in candidates:
        if any(
            abs(point[0] - existing[0]) + abs(point[1] - existing[1]) < 4
            for existing in selected
        ):
            continue
        selected.append(point)
        if len(selected) >= maximum:
            break

    for point in selected:
        heights[point] = 1
        for neighbor in _neighbors(point):
            if neighbor in heights:
                heights[neighbor] = min(heights[neighbor], 2)
    return tuple(sorted(selected))


def _build_wall_runs(
    walls: set[PointTuple],
    roles: dict[PointTuple, str],
) -> tuple[WallRun, ...]:
    runs: list[WallRun] = []
    used_horizontal: set[PointTuple] = set()
    used_vertical: set[PointTuple] = set()
    for orientation, used in (("horizontal", used_horizontal), ("vertical", used_vertical)):
        ordered = sorted(walls, key=lambda point: (point[1], point[0]))
        for point in ordered:
            if point in used:
                continue
            role = roles.get(point, "outer_wall")
            sequence = [point]
            current = point
            delta = (1, 0) if orientation == "horizontal" else (0, 1)
            while True:
                candidate = (current[0] + delta[0], current[1] + delta[1])
                if candidate not in walls or roles.get(candidate, "outer_wall") != role:
                    break
                sequence.append(candidate)
                current = candidate
            if len(sequence) < 2:
                continue
            used.update(sequence)
            runs.append(
                WallRun(
                    run_id=len(runs),
                    role=role,
                    orientation=orientation,
                    points=tuple(sequence),
                )
            )
    return tuple(runs)


def _build_metrics(
    *,
    rect: RectTuple,
    entrance: PointTuple,
    intact: _IntactPlan,
    walls: set[PointTuple],
    heights: dict[PointTuple, int],
    removed: set[PointTuple],
    wall_runs: tuple[WallRun, ...],
    window_sill_hints: tuple[PointTuple, ...],
    severity: str,
) -> ArchitectureMetrics:
    intact_count = len(intact.wall_roles)
    outer_intact = len(intact.outer_points)
    surviving_outer = len(walls & set(intact.outer_points))
    inner_points = {
        point
        for point, role in intact.wall_roles.items()
        if role == "inner_wall"
    }
    surviving_inner = len(walls & inner_points)
    destroyed_ratio = 1.0 - len(walls) / max(1, intact_count)
    outer_retained = surviving_outer / max(1, outer_intact)
    inner_retained = (
        surviving_inner / len(inner_points)
        if len(inner_points) >= 4
        else 1.0
    )
    components = _components(walls)
    largest_component_ratio = (
        max((len(component) for component in components), default=0)
        / max(1, len(walls))
    )
    isolated = sum(1 for component in components if len(component) == 1)
    retained_corners = len(walls & set(intact.corners))
    longest = max((len(run.points) for run in wall_runs), default=1)
    breaches = _outer_gap_count(rect, walls)
    accessible = _accessible_floor_ratio(rect, walls, entrance)
    max_delta = max(
        (
            abs(height - heights[neighbor])
            for point, height in heights.items()
            for neighbor in _neighbors(point)
            if neighbor in heights
        ),
        default=0,
    )
    target_destroyed, target_outer = _SEVERITY_TARGETS.get(
        severity,
        _SEVERITY_TARGETS["moderate"],
    )
    left, top, right, bottom = rect
    footprint_area = (right - left + 1) * (bottom - top + 1)
    planned_floor_tiles = footprint_area - len(walls)
    score = 100.0
    score -= abs(destroyed_ratio - target_destroyed) * 110.0
    score -= abs(outer_retained - target_outer) * 90.0
    score += min(longest, 10) * 3.5
    score += retained_corners * 5.0
    score += min(breaches, 2) * 1.5
    score += accessible * 20.0
    score += largest_component_ratio * 32.0
    score += inner_retained * 18.0
    score -= max(0, len(components) - 1) * 8.0
    score -= isolated * 40.0
    score += len(window_sill_hints) * 2.0
    if removed:
        score += min(len(removed), 8) * 0.15
    return ArchitectureMetrics(
        intact_wall_tiles=intact_count,
        surviving_wall_tiles=len(walls),
        wall_destroyed_ratio=destroyed_ratio,
        outer_wall_retained_ratio=outer_retained,
        connected_wall_components=len(components),
        isolated_wall_tiles=isolated,
        retained_corners=retained_corners,
        longest_straight_run=longest,
        entrance_or_breach_count=breaches,
        accessible_floor_ratio=accessible,
        maximum_adjacent_height_delta=max_delta,
        largest_component_ratio=largest_component_ratio,
        surviving_inner_wall_ratio=inner_retained,
        window_sill_hint_count=len(window_sill_hints),
        planned_floor_tiles=planned_floor_tiles,
        score=score,
    )


def _components(points: set[PointTuple]) -> list[set[PointTuple]]:
    remaining = set(points)
    output: list[set[PointTuple]] = []
    while remaining:
        start = next(iter(remaining))
        component = {start}
        queue: deque[PointTuple] = deque([start])
        remaining.remove(start)
        while queue:
            current = queue.popleft()
            for neighbor in _neighbors(current):
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                component.add(neighbor)
                queue.append(neighbor)
        output.append(component)
    return output


def _accessible_floor_ratio(
    rect: RectTuple,
    walls: set[PointTuple],
    entrance: PointTuple,
) -> float:
    left, top, right, bottom = rect
    floor = {
        (x, y)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
        if (x, y) not in walls
    }
    if not floor:
        return 0.0
    start = entrance if entrance in floor else min(floor)
    reachable = {start}
    queue: deque[PointTuple] = deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in _neighbors(current):
            if neighbor not in floor or neighbor in reachable:
                continue
            reachable.add(neighbor)
            queue.append(neighbor)
    return len(reachable) / len(floor)


def _outer_gap_count(rect: RectTuple, walls: set[PointTuple]) -> int:
    boundary = set()
    left, top, right, bottom = rect
    for x in range(left, right + 1):
        boundary.add((x, top))
        boundary.add((x, bottom))
    for y in range(top, bottom + 1):
        boundary.add((left, y))
        boundary.add((right, y))
    gaps = boundary - walls
    return len(_components(gaps)) if gaps else 0


def _side_points(
    rect: RectTuple,
    side: str,
    *,
    include_corners: bool,
) -> list[PointTuple]:
    left, top, right, bottom = rect
    offset = 0 if include_corners else 1
    if side == "north":
        return [(x, top) for x in range(left + offset, right - offset + 1)]
    if side == "south":
        return [(x, bottom) for x in range(left + offset, right - offset + 1)]
    if side == "west":
        return [(left, y) for y in range(top + offset, bottom - offset + 1)]
    return [(right, y) for y in range(top + offset, bottom - offset + 1)]


def _side_for_point(rect: RectTuple, point: PointTuple) -> str:
    left, top, right, bottom = rect
    x, y = point
    if y == top:
        return "north"
    if y == bottom:
        return "south"
    if x == left:
        return "west"
    if x == right:
        return "east"
    return "north"


def _inside_boundary_neighbor(
    rect: RectTuple,
    point: PointTuple,
) -> PointTuple | None:
    """Return the footprint cell immediately inside a boundary point."""
    left, top, right, bottom = rect
    x, y = point
    if y == top and top < bottom:
        return (x, y + 1)
    if y == bottom and top < bottom:
        return (x, y - 1)
    if x == left and left < right:
        return (x + 1, y)
    if x == right and left < right:
        return (x - 1, y)
    return None


def _opposite_side(side: str) -> str:
    return {
        "north": "south",
        "south": "north",
        "east": "west",
        "west": "east",
    }[side]


def _rotate_side(side: str, step: int) -> str:
    sides = ("north", "east", "south", "west")
    return sides[(sides.index(side) + step) % len(sides)]


def _corner_for_direction(side: str) -> str:
    return {
        "north": "north_west",
        "east": "north_east",
        "south": "south_east",
        "west": "south_west",
    }[side]


def _distance_to_points(
    point: PointTuple,
    targets: set[PointTuple],
    *,
    maximum: int,
) -> int:
    if not targets:
        return maximum + 1
    return min(
        maximum + 1,
        min(abs(point[0] - x) + abs(point[1] - y) for x, y in targets),
    )


def _neighbor_count(points: set[PointTuple], point: PointTuple) -> int:
    return sum(neighbor in points for neighbor in _neighbors(point))


def _neighbors(point: PointTuple) -> tuple[PointTuple, ...]:
    x, y = point
    return tuple((x + dx, y + dy) for dx, dy in _NEIGHBORS)


def _stable_seed(
    resolved_seed: int,
    site_id: int,
    building_id: int,
    variant: int,
    salt: str,
) -> int:
    payload = (
        f"{resolved_seed}:{site_id}:{building_id}:{variant}:{salt}".encode(
            "utf-8"
        )
    )
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "little")
