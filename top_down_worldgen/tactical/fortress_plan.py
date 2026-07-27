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


def build_lake_island_fortress_plan(
    *,
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    island_mask_rows: list[list[int]],
    seed: int,
) -> FortressPlanResult:
    """Build an outer fortress wall, round towers, and one main gate.

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

    rng = Random(seed ^ 0xF047_1220_91A7)
    gate_angle = atan2(gate_y - center_y, gate_x - center_x)
    vertex_count = _clamp(round(fortress_span / 6), 6, 10)
    base_radius = fortress_span * 0.43
    vertices = _build_vertices(
        center_x=center_x,
        center_y=center_y,
        base_radius=base_radius,
        vertex_count=vertex_count,
        gate_angle=gate_angle,
        rng=rng,
    )
    vertices = [
        _pull_inside_island(
            point=point,
            center=(center_x, center_y),
            island_mask_rows=island_mask_rows,
            minimum_mask=2,
        )
        for point in vertices
    ]

    plan_rows = [[PLAN_OUTSIDE for _ in range(width)] for _ in range(height)]
    _fill_polygon(plan_rows=plan_rows, vertices=vertices, value=PLAN_COURTYARD)
    wall_thickness = max(1, round(fortress_span * 0.045))
    for start, end in zip(vertices, vertices[1:] + vertices[:1], strict=True):
        _draw_thick_line(
            plan_rows=plan_rows,
            start=start,
            end=end,
            radius=wall_thickness,
            value=PLAN_WALL,
        )

    tower_radius = _clamp(round(fortress_span * 0.085), 3, 7)
    tower_indices = _select_tower_vertices(vertices=vertices, gate_angle=gate_angle, center=(center_x, center_y))
    for index in tower_indices:
        _draw_round_tower(
            plan_rows=plan_rows,
            center=vertices[index],
            outer_radius=tower_radius,
            wall_thickness=max(1, wall_thickness),
        )

    gate_center = _nearest_wall_point(
        vertices=vertices,
        target=(gate_x, gate_y),
    )
    gate_half_width = max(1, round(fortress_span * 0.045))
    _cut_gate(
        plan_rows=plan_rows,
        gate_center=gate_center,
        fortress_center=(center_x, center_y),
        half_width=gate_half_width,
    )

    gate_tower_radius = max(3, tower_radius - 1)
    gate_towers = _gate_tower_centers(
        gate_center=gate_center,
        fortress_center=(center_x, center_y),
        offset=gate_half_width + gate_tower_radius,
    )
    for tower_center in gate_towers:
        _draw_round_tower(
            plan_rows=plan_rows,
            center=tower_center,
            outer_radius=gate_tower_radius,
            wall_thickness=max(1, wall_thickness),
        )

    _validate_plan(plan_rows=plan_rows, island_mask_rows=island_mask_rows)
    counts = _count_plan(plan_rows)
    tower_count = len(tower_indices) + 2
    plan_report = {
        "status": "planned",
        "algorithm": "irregular_polygon_round_towers_v1",
        "seed": seed,
        "center": {"x": center_x, "y": center_y},
        "fortress_span_tiles": fortress_span,
        "vertex_count": vertex_count,
        "wall_thickness_tiles": wall_thickness * 2 + 1,
        "tower_radius_tiles": tower_radius,
        "tower_count": tower_count,
        "gate_center": {"x": gate_center[0], "y": gate_center[1]},
        "gate_width_tiles": gate_half_width * 2 + 1,
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
        tower_count=tower_count,
    )


def render_fortress_plan_preview(
    *,
    path: Path,
    elevation_rows: list[list[int]],
    island_mask_rows: list[list[int]],
    plan_rows: list[list[int]],
) -> None:
    """Render island and fortress shell plan preview.

    Args:
        path: Output PNG path.
        elevation_rows: Final geographic elevation rows.
        island_mask_rows: Island classification mask.
        plan_rows: Fortress plan classification grid.
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
            mask = island_mask_rows[y][x]
            level = elevation_rows[y][x]
            if plan == PLAN_GATE:
                color = (208, 153, 64)
            elif plan == PLAN_TOWER:
                color = (105, 99, 92)
            elif plan == PLAN_WALL:
                color = (129, 122, 111)
            elif plan == PLAN_COURTYARD:
                color = (116, 151, 83)
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


def _build_vertices(
    *,
    center_x: int,
    center_y: int,
    base_radius: float,
    vertex_count: int,
    gate_angle: float,
    rng: Random,
) -> list[tuple[int, int]]:
    phase = gate_angle + pi
    vertices: list[tuple[int, int]] = []
    for index in range(vertex_count):
        angle = phase + 2.0 * pi * index / vertex_count
        radius = base_radius * rng.uniform(0.88, 1.08)
        x_scale = rng.uniform(0.92, 1.06)
        y_scale = rng.uniform(0.92, 1.06)
        vertices.append(
            (
                round(center_x + cos(angle) * radius * x_scale),
                round(center_y + sin(angle) * radius * y_scale),
            )
        )
    return vertices


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
    raise ValueError("Unable to place fortress vertex inside island")


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


def _draw_thick_line(
    *,
    plan_rows: list[list[int]],
    start: tuple[int, int],
    end: tuple[int, int],
    radius: int,
    value: int,
) -> None:
    x1, y1 = start
    x2, y2 = end
    steps = max(abs(x2 - x1), abs(y2 - y1), 1)
    for step in range(steps + 1):
        x = round(x1 + (x2 - x1) * step / steps)
        y = round(y1 + (y2 - y1) * step / steps)
        _fill_disk(plan_rows=plan_rows, center=(x, y), radius=radius, value=value)


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


def _select_tower_vertices(
    *,
    vertices: list[tuple[int, int]],
    gate_angle: float,
    center: tuple[int, int],
) -> list[int]:
    selected: list[int] = []
    for index, (x, y) in enumerate(vertices):
        angle = atan2(y - center[1], x - center[0])
        delta = abs(_angle_delta(angle, gate_angle))
        if delta > 0.42:
            selected.append(index)
    return selected


def _nearest_wall_point(
    *,
    vertices: list[tuple[int, int]],
    target: tuple[int, int],
) -> tuple[int, int]:
    best_point = vertices[0]
    best_distance = float("inf")
    for start, end in zip(vertices, vertices[1:] + vertices[:1], strict=True):
        point = _project_to_segment(target=target, start=start, end=end)
        distance = hypot(point[0] - target[0], point[1] - target[1])
        if distance < best_distance:
            best_distance = distance
            best_point = point
    return best_point


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


def _cut_gate(
    *,
    plan_rows: list[list[int]],
    gate_center: tuple[int, int],
    fortress_center: tuple[int, int],
    half_width: int,
) -> None:
    outward_x = gate_center[0] - fortress_center[0]
    outward_y = gate_center[1] - fortress_center[1]
    length = hypot(outward_x, outward_y) or 1.0
    tangent_x = -outward_y / length
    tangent_y = outward_x / length
    normal_x = outward_x / length
    normal_y = outward_y / length
    for lateral in range(-half_width, half_width + 1):
        for depth in range(-3, 4):
            x = round(gate_center[0] + tangent_x * lateral + normal_x * depth)
            y = round(gate_center[1] + tangent_y * lateral + normal_y * depth)
            if 0 <= y < len(plan_rows) and 0 <= x < len(plan_rows[0]):
                plan_rows[y][x] = PLAN_GATE


def _gate_tower_centers(
    *,
    gate_center: tuple[int, int],
    fortress_center: tuple[int, int],
    offset: int,
) -> tuple[tuple[int, int], tuple[int, int]]:
    outward_x = gate_center[0] - fortress_center[0]
    outward_y = gate_center[1] - fortress_center[1]
    length = hypot(outward_x, outward_y) or 1.0
    tangent_x = -outward_y / length
    tangent_y = outward_x / length
    return (
        (round(gate_center[0] + tangent_x * offset), round(gate_center[1] + tangent_y * offset)),
        (round(gate_center[0] - tangent_x * offset), round(gate_center[1] - tangent_y * offset)),
    )


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


def _count_plan(plan_rows: list[list[int]]) -> dict[int, int]:
    counts = {value: 0 for value in range(PLAN_GATE + 1)}
    for row in plan_rows:
        for value in row:
            counts[value] += 1
    return counts


def _angle_delta(first: float, second: float) -> float:
    return (first - second + pi) % (2.0 * pi) - pi


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
