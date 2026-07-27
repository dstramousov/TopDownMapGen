from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin
from pathlib import Path
from random import Random
from typing import Any

from PIL import Image

PLAN_OUTSIDE = 0
PLAN_COURTYARD = 1
PLAN_WALL = 2
PLAN_TOWER = 3
PLAN_GATE = 4


@dataclass(frozen=True, slots=True)
class FortressPlanResult:
    """Generated deterministic outer fortress shell plan."""

    runtime_data: dict[str, Any]
    site_report: dict[str, Any]
    plan_rows: list[list[int]]
    wall_tiles: int
    tower_tiles: int
    gate_tiles: int
    tower_count: int


@dataclass(frozen=True, slots=True)
class _Tower:
    """Planned round tower."""

    center: tuple[int, int]
    radius: int
    kind: str


@dataclass(frozen=True, slots=True)
class _Segment:
    """Planned wall segment."""

    start: tuple[int, int]
    end: tuple[int, int]
    kind: str
    bend: float


def build_lake_island_fortress_plan(
    *,
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    island_mask_rows: list[list[int]],
    seed: int,
) -> FortressPlanResult:
    """Build a mixed straight/curved fortress shell with round towers.

    Args:
        runtime_data: Tactical runtime data.
        site_report: Fortress site report with island materialization data.
        island_mask_rows: Materialized island mask.
        seed: Resolved world seed.

    Returns:
        Fortress shell plan and updated reports.
    """
    materialization = site_report.get("island_materialization")
    requirements = site_report.get("requirements")
    selected_site = site_report.get("selected_site")
    if (
        not isinstance(materialization, dict)
        or materialization.get("status") != "materialized"
        or not isinstance(requirements, dict)
        or not isinstance(selected_site, dict)
        or not island_mask_rows
    ):
        return FortressPlanResult(
            runtime_data=runtime_data,
            site_report=site_report,
            plan_rows=[],
            wall_tiles=0,
            tower_tiles=0,
            gate_tiles=0,
            tower_count=0,
        )

    center = selected_site.get("center")
    entrance_anchor = materialization.get("entrance_anchor")
    if not isinstance(center, dict) or not isinstance(entrance_anchor, dict):
        raise ValueError("Fortress plan requires center and entrance anchor")

    height = len(island_mask_rows)
    width = len(island_mask_rows[0])
    if width == 0 or any(len(row) != width for row in island_mask_rows):
        raise ValueError("Island mask must be rectangular")

    center_x = int(center["x"])
    center_y = int(center["y"])
    gate_x = int(entrance_anchor["x"])
    gate_y = int(entrance_anchor["y"])
    fortress_span = int(requirements.get("fortress_span_tiles", 0))
    if fortress_span < 16:
        raise ValueError("Fortress span is too small")

    rng = Random(seed ^ 0xF047_1240_91A7)
    composition = rng.choice(("compact_mixed", "curved_courtyard"))
    gate_angle = atan2(gate_y - center_y, gate_x - center_x)
    anchors = _build_architectural_anchors(
        center=(center_x, center_y),
        fortress_span=fortress_span,
        gate_angle=gate_angle,
        composition=composition,
        rng=rng,
    )
    anchors = [
        _pull_inside_island(
            point=point,
            center=(center_x, center_y),
            island_mask_rows=island_mask_rows,
            minimum_mask=2,
        )
        for point in anchors
    ]

    segments = _build_segments(
        anchors=anchors,
        center=(center_x, center_y),
        composition=composition,
        rng=rng,
    )
    perimeter = _sample_perimeter(segments)
    plan_rows = [[PLAN_OUTSIDE for _ in range(width)] for _ in range(height)]
    _fill_polygon(plan_rows=plan_rows, vertices=perimeter, value=PLAN_COURTYARD)

    wall_radius = max(1, round(fortress_span * 0.035))
    for segment in segments:
        _draw_segment(
            plan_rows=plan_rows,
            segment=segment,
            center=(center_x, center_y),
            radius=wall_radius,
        )

    gate_center, gate_tangent = _nearest_segment_point(
        segments=segments,
        target=(gate_x, gate_y),
        center=(center_x, center_y),
    )
    gate_half_width = max(1, round(fortress_span * 0.045))
    gate_radius = _clamp(round(fortress_span * 0.075), 3, 5)
    gate_towers = _make_gate_towers(
        gate_center=gate_center,
        tangent=gate_tangent,
        radius=gate_radius,
        half_width=gate_half_width,
    )

    towers = _select_architectural_towers(
        anchors=anchors,
        center=(center_x, center_y),
        fortress_span=fortress_span,
        gate_center=gate_center,
        gate_towers=gate_towers,
        composition=composition,
        rng=rng,
    )
    towers.extend(gate_towers)

    for tower in towers:
        _draw_round_tower(
            plan_rows=plan_rows,
            center=tower.center,
            outer_radius=tower.radius,
            wall_thickness=max(1, wall_radius),
        )

    _cut_gate(
        plan_rows=plan_rows,
        gate_center=gate_center,
        tangent=gate_tangent,
        half_width=gate_half_width,
    )

    _validate_plan(
        plan_rows=plan_rows,
        island_mask_rows=island_mask_rows,
        towers=towers,
    )
    counts = _count_plan(plan_rows)
    plan_report = {
        "status": "planned",
        "algorithm": "architectural_nodes_mixed_walls_v2",
        "composition": composition,
        "seed": seed,
        "center": {"x": center_x, "y": center_y},
        "fortress_span_tiles": fortress_span,
        "anchor_count": len(anchors),
        "wall_thickness_tiles": wall_radius * 2 + 1,
        "segments": [
            {
                "start": {"x": segment.start[0], "y": segment.start[1]},
                "end": {"x": segment.end[0], "y": segment.end[1]},
                "kind": segment.kind,
                "bend": round(segment.bend, 3),
            }
            for segment in segments
        ],
        "tower_count": len(towers),
        "towers": [
            {
                "center": {"x": tower.center[0], "y": tower.center[1]},
                "radius_tiles": tower.radius,
                "kind": tower.kind,
            }
            for tower in towers
        ],
        "gate_center": {"x": gate_center[0], "y": gate_center[1]},
        "gate_width_tiles": gate_half_width * 2 + 1,
        "gate_tower_centers": [
            {"x": tower.center[0], "y": tower.center[1], "radius_tiles": tower.radius}
            for tower in gate_towers
        ],
        "wall_tiles": counts[PLAN_WALL],
        "tower_tiles": counts[PLAN_TOWER],
        "gate_tiles": counts[PLAN_GATE],
        "courtyard_tiles": counts[PLAN_COURTYARD],
        "materialized_to_terrain": False,
    }
    updated_site_report = dict(site_report)
    policy = dict(updated_site_report.get("policy", {}))
    policy["phase"] = "fortress_shell_planned"
    updated_site_report["policy"] = policy
    updated_site_report["fortress_plan"] = plan_report

    updated_runtime = dict(runtime_data)
    updated_runtime["fortress_site"] = updated_site_report
    updated_runtime["fortress_plan"] = plan_report

    return FortressPlanResult(
        runtime_data=updated_runtime,
        site_report=updated_site_report,
        plan_rows=plan_rows,
        wall_tiles=counts[PLAN_WALL],
        tower_tiles=counts[PLAN_TOWER],
        gate_tiles=counts[PLAN_GATE],
        tower_count=len(towers),
    )


def render_fortress_plan_preview(
    *,
    path: Path,
    elevation_rows: list[list[int]],
    island_mask_rows: list[list[int]],
    plan_rows: list[list[int]],
    approach_rows: list[list[int]] | None = None,
    interior_rows: list[list[int]] | None = None,
) -> None:
    """Render island and fortress shell plan preview.

    Args:
        path: Output PNG path.
        elevation_rows: Final geographic elevation rows.
        island_mask_rows: Island classification mask.
        plan_rows: Fortress plan classification grid.
        approach_rows: Optional shallow-approach classification grid.
        interior_rows: Optional fortress interior classification grid.
    """
    height = len(elevation_rows)
    width = len(elevation_rows[0]) if elevation_rows else 0
    if width <= 0 or height <= 0:
        return
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            plan = plan_rows[y][x]
            approach = (
                approach_rows[y][x]
                if approach_rows is not None
                and y < len(approach_rows)
                and x < len(approach_rows[y])
                else 0
            )
            interior = (
                interior_rows[y][x]
                if interior_rows is not None
                and y < len(interior_rows)
                and x < len(interior_rows[y])
                else 0
            )
            mask = island_mask_rows[y][x]
            level = elevation_rows[y][x]
            if interior == 2:
                color = (75, 70, 66)
            elif interior == 3:
                color = (151, 143, 126)
            elif interior == 4:
                color = (112, 82, 62)
            elif interior == 5:
                color = (176, 139, 94)
            elif interior == 6:
                color = (47, 91, 43)
            elif interior == 1:
                color = (188, 165, 111)
            elif plan == PLAN_GATE:
                color = (184, 145, 210)
            elif plan == PLAN_TOWER:
                color = (72, 38, 96)
            elif plan == PLAN_WALL:
                color = (104, 58, 135)
            elif plan == PLAN_COURTYARD:
                color = (205, 180, 222)
            elif approach == 2:
                color = (173, 150, 100)
            elif approach == 1:
                color = (74, 119, 129)
            elif mask == 1:
                color = (194, 174, 112)
            elif mask in {2, 3}:
                color = (87, 135, 69)
            elif level <= -2:
                color = (47, 91, 143)
            elif level == -1:
                color = (74, 119, 129)
            else:
                color = (87, 125, 67)
            pixels[x, y] = color
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _build_architectural_anchors(
    *,
    center: tuple[int, int],
    fortress_span: int,
    gate_angle: float,
    composition: str,
    rng: Random,
) -> list[tuple[int, int]]:
    count = rng.randint(5, 7) if composition == "compact_mixed" else rng.randint(6, 8)
    gaps = [rng.uniform(0.72, 1.28) for _ in range(count)]
    scale = 2.0 * pi / sum(gaps)
    angles: list[float] = []
    angle = gate_angle + pi + rng.uniform(-0.18, 0.18)
    for gap in gaps:
        angles.append(angle)
        angle += gap * scale

    base = fortress_span * 0.40
    x_stretch = rng.uniform(0.92, 1.12)
    y_stretch = rng.uniform(0.88, 1.08)
    anchors: list[tuple[int, int]] = []
    for index, angle in enumerate(angles):
        radius = base * rng.uniform(0.82, 1.10)
        if composition == "compact_mixed" and index % 3 == 0:
            radius *= rng.uniform(0.88, 0.96)
        anchors.append(
            (
                round(center[0] + cos(angle) * radius * x_stretch),
                round(center[1] + sin(angle) * radius * y_stretch),
            )
        )
    return anchors


def _build_segments(
    *,
    anchors: list[tuple[int, int]],
    center: tuple[int, int],
    composition: str,
    rng: Random,
) -> list[_Segment]:
    curve_probability = 0.30 if composition == "compact_mixed" else 0.52
    segments: list[_Segment] = []
    for start, end in zip(anchors, anchors[1:] + anchors[:1], strict=True):
        length = hypot(end[0] - start[0], end[1] - start[1])
        if length >= 11 and rng.random() < curve_probability:
            kind = "gentle_curve"
            bend = rng.uniform(0.10, 0.22) * (-1.0 if rng.random() < 0.25 else 1.0)
        else:
            kind = "straight"
            bend = 0.0
        segments.append(_Segment(start=start, end=end, kind=kind, bend=bend))
    if all(segment.kind == "straight" for segment in segments):
        longest = max(range(len(segments)), key=lambda i: hypot(
            segments[i].end[0] - segments[i].start[0],
            segments[i].end[1] - segments[i].start[1],
        ))
        old = segments[longest]
        segments[longest] = _Segment(old.start, old.end, "gentle_curve", 0.14)
    return segments


def _sample_perimeter(segments: list[_Segment]) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for segment in segments:
        sampled = _sample_segment(segment)
        if points and sampled and sampled[0] == points[-1]:
            sampled = sampled[1:]
        points.extend(sampled)
    return points


def _sample_segment(segment: _Segment) -> list[tuple[int, int]]:
    x1, y1 = segment.start
    x2, y2 = segment.end
    length = max(1.0, hypot(x2 - x1, y2 - y1))
    steps = max(2, round(length * 1.5))
    if segment.kind == "straight":
        return [
            (round(x1 + (x2 - x1) * t / steps), round(y1 + (y2 - y1) * t / steps))
            for t in range(steps + 1)
        ]
    midpoint_x = (x1 + x2) / 2.0
    midpoint_y = (y1 + y2) / 2.0
    normal_x = -(y2 - y1) / length
    normal_y = (x2 - x1) / length
    control_x = midpoint_x + normal_x * length * segment.bend
    control_y = midpoint_y + normal_y * length * segment.bend
    points: list[tuple[int, int]] = []
    for step in range(steps + 1):
        t = step / steps
        inv = 1.0 - t
        x = inv * inv * x1 + 2.0 * inv * t * control_x + t * t * x2
        y = inv * inv * y1 + 2.0 * inv * t * control_y + t * t * y2
        point = (round(x), round(y))
        if not points or points[-1] != point:
            points.append(point)
    return points


def _draw_segment(
    *,
    plan_rows: list[list[int]],
    segment: _Segment,
    center: tuple[int, int],
    radius: int,
) -> None:
    del center
    for point in _sample_segment(segment):
        _fill_disk(plan_rows=plan_rows, center=point, radius=radius, value=PLAN_WALL)


def _nearest_segment_point(
    *,
    segments: list[_Segment],
    target: tuple[int, int],
    center: tuple[int, int],
) -> tuple[tuple[int, int], tuple[float, float]]:
    best_point = segments[0].start
    best_tangent = (1.0, 0.0)
    best_distance = float("inf")
    for segment in segments:
        points = _sample_segment(segment)
        for first, second in zip(points, points[1:], strict=False):
            point = _project_to_segment(target=target, start=first, end=second)
            distance = hypot(point[0] - target[0], point[1] - target[1])
            outward = (point[0] - center[0], point[1] - center[1])
            if distance < best_distance and outward != (0, 0):
                best_distance = distance
                best_point = point
                tangent_length = hypot(second[0] - first[0], second[1] - first[1]) or 1.0
                best_tangent = (
                    (second[0] - first[0]) / tangent_length,
                    (second[1] - first[1]) / tangent_length,
                )
    return best_point, best_tangent


def _make_gate_towers(
    *,
    gate_center: tuple[int, int],
    tangent: tuple[float, float],
    radius: int,
    half_width: int,
) -> list[_Tower]:
    offset = radius + half_width + 1
    return [
        _Tower(
            center=(
                round(gate_center[0] + tangent[0] * offset),
                round(gate_center[1] + tangent[1] * offset),
            ),
            radius=radius,
            kind="gate_round",
        ),
        _Tower(
            center=(
                round(gate_center[0] - tangent[0] * offset),
                round(gate_center[1] - tangent[1] * offset),
            ),
            radius=radius,
            kind="gate_round",
        ),
    ]


def _select_architectural_towers(
    *,
    anchors: list[tuple[int, int]],
    center: tuple[int, int],
    fortress_span: int,
    gate_center: tuple[int, int],
    gate_towers: list[_Tower],
    composition: str,
    rng: Random,
) -> list[_Tower]:
    target_total = rng.randint(4, 6) if composition == "compact_mixed" else rng.randint(3, 5)
    target_regular = max(2, target_total - len(gate_towers))
    candidates: list[tuple[float, int]] = []
    for index, current in enumerate(anchors):
        previous = anchors[index - 1]
        following = anchors[(index + 1) % len(anchors)]
        turn = abs(_turn_angle(previous, current, following))
        distance_from_gate = hypot(current[0] - gate_center[0], current[1] - gate_center[1])
        score = turn * 3.0 + distance_from_gate / max(1.0, fortress_span)
        candidates.append((score + rng.uniform(-0.15, 0.15), index))
    candidates.sort(reverse=True)

    towers: list[_Tower] = []
    for _, index in candidates:
        if len(towers) >= target_regular:
            break
        center_point = anchors[index]
        radius = _clamp(round(fortress_span * rng.uniform(0.075, 0.105)), 3, 5)
        tower = _Tower(center=center_point, radius=radius, kind="corner_round")
        if _tower_conflicts(tower, towers + gate_towers, clearance=1):
            continue
        towers.append(tower)

    if len(towers) < 2:
        for point in anchors:
            tower = _Tower(center=point, radius=3, kind="corner_round")
            if not _tower_conflicts(tower, towers + gate_towers, clearance=1):
                towers.append(tower)
            if len(towers) >= 2:
                break
    return towers


def _turn_angle(
    previous: tuple[int, int],
    current: tuple[int, int],
    following: tuple[int, int],
) -> float:
    first = atan2(previous[1] - current[1], previous[0] - current[0])
    second = atan2(following[1] - current[1], following[0] - current[0])
    return abs((second - first + pi) % (2.0 * pi) - pi)


def _tower_conflicts(tower: _Tower, existing: list[_Tower], clearance: int) -> bool:
    return any(
        hypot(tower.center[0] - other.center[0], tower.center[1] - other.center[1])
        < tower.radius + other.radius + clearance
        for other in existing
    )


def _pull_inside_island(
    *,
    point: tuple[int, int],
    center: tuple[int, int],
    island_mask_rows: list[list[int]],
    minimum_mask: int,
) -> tuple[int, int]:
    x, y = point
    center_x, center_y = center
    for _ in range(64):
        if (
            0 <= y < len(island_mask_rows)
            and 0 <= x < len(island_mask_rows[0])
            and island_mask_rows[y][x] >= minimum_mask
        ):
            return x, y
        x = round((x * 3 + center_x) / 4)
        y = round((y * 3 + center_y) / 4)
    raise ValueError("Unable to place fortress anchor inside island")


def _fill_polygon(
    *,
    plan_rows: list[list[int]],
    vertices: list[tuple[int, int]],
    value: int,
) -> None:
    min_y = max(0, min(y for _, y in vertices))
    max_y = min(len(plan_rows) - 1, max(y for _, y in vertices))
    for y in range(min_y, max_y + 1):
        intersections: list[float] = []
        previous = vertices[-1]
        for current in vertices:
            x1, y1 = previous
            x2, y2 = current
            previous = current
            if (y1 <= y < y2) or (y2 <= y < y1):
                intersections.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        intersections.sort()
        for left, right in zip(intersections[0::2], intersections[1::2], strict=False):
            start_x = max(0, round(left))
            end_x = min(len(plan_rows[0]) - 1, round(right))
            for x in range(start_x, end_x + 1):
                plan_rows[y][x] = value


def _draw_round_tower(
    *,
    plan_rows: list[list[int]],
    center: tuple[int, int],
    outer_radius: int,
    wall_thickness: int,
) -> None:
    center_x, center_y = center
    inner_radius = max(1, outer_radius - wall_thickness - 1)
    for y in range(center_y - outer_radius, center_y + outer_radius + 1):
        for x in range(center_x - outer_radius, center_x + outer_radius + 1):
            if not (0 <= y < len(plan_rows) and 0 <= x < len(plan_rows[0])):
                continue
            distance = hypot(x - center_x, y - center_y)
            if inner_radius < distance <= outer_radius + 0.35:
                plan_rows[y][x] = PLAN_TOWER
            elif distance <= inner_radius:
                plan_rows[y][x] = PLAN_COURTYARD


def _cut_gate(
    *,
    plan_rows: list[list[int]],
    gate_center: tuple[int, int],
    tangent: tuple[float, float],
    half_width: int,
) -> None:
    normal = (-tangent[1], tangent[0])
    for lateral in range(-half_width, half_width + 1):
        for depth in range(-4, 5):
            x = round(gate_center[0] + tangent[0] * lateral + normal[0] * depth)
            y = round(gate_center[1] + tangent[1] * lateral + normal[1] * depth)
            if 0 <= y < len(plan_rows) and 0 <= x < len(plan_rows[0]):
                plan_rows[y][x] = PLAN_GATE


def _project_to_segment(
    *,
    target: tuple[int, int],
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[int, int]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    denominator = dx * dx + dy * dy
    if denominator == 0:
        return start
    ratio = ((target[0] - start[0]) * dx + (target[1] - start[1]) * dy) / denominator
    ratio = max(0.0, min(1.0, ratio))
    return round(start[0] + ratio * dx), round(start[1] + ratio * dy)


def _fill_disk(
    *,
    plan_rows: list[list[int]],
    center: tuple[int, int],
    radius: int,
    value: int,
) -> None:
    center_x, center_y = center
    radius_squared = radius * radius
    for y in range(center_y - radius, center_y + radius + 1):
        for x in range(center_x - radius, center_x + radius + 1):
            if not (0 <= y < len(plan_rows) and 0 <= x < len(plan_rows[0])):
                continue
            if (x - center_x) ** 2 + (y - center_y) ** 2 <= radius_squared:
                plan_rows[y][x] = value


def _validate_plan(
    *,
    plan_rows: list[list[int]],
    island_mask_rows: list[list[int]],
    towers: list[_Tower],
) -> None:
    gate_tiles = 0
    wall_or_tower_tiles = 0
    for y, row in enumerate(plan_rows):
        for x, value in enumerate(row):
            if value in {PLAN_WALL, PLAN_TOWER, PLAN_GATE}:
                if island_mask_rows[y][x] == 0:
                    raise ValueError("Fortress shell extends outside the island")
                wall_or_tower_tiles += 1
            if value == PLAN_GATE:
                gate_tiles += 1
    if gate_tiles == 0:
        raise ValueError("Fortress plan has no main gate")
    if wall_or_tower_tiles < 32:
        raise ValueError("Fortress shell is unexpectedly small")
    for index, tower in enumerate(towers):
        if _tower_conflicts(tower, towers[:index], clearance=0):
            raise ValueError("Fortress tower footprints overlap")


def _count_plan(plan_rows: list[list[int]]) -> dict[int, int]:
    counts = {value: 0 for value in range(PLAN_GATE + 1)}
    for row in plan_rows:
        for value in row:
            counts[value] += 1
    return counts


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
