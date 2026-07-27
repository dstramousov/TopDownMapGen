from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from random import Random
from typing import Any

from .fortress_plan import PLAN_COURTYARD

INTERIOR_NONE = 0
INTERIOR_PATH = 1
INTERIOR_KEEP_WALL = 2
INTERIOR_KEEP_FLOOR = 3
INTERIOR_HOUSE_WALL = 4
INTERIOR_HOUSE_FLOOR = 5
INTERIOR_TREE = 6


@dataclass(frozen=True, slots=True)
class FortressInteriorPlanResult:
    """Generated deterministic fortress interior plan."""

    runtime_data: dict[str, Any]
    site_report: dict[str, Any]
    interior_rows: list[list[int]]
    keep_tiles: int
    house_count: int
    tree_count: int
    path_tiles: int


@dataclass(frozen=True, slots=True)
class _House:
    """Planned rectangular courtyard house."""

    x0: int
    y0: int
    width: int
    height: int
    door: tuple[int, int]



def build_fortress_interior_plan(
    *,
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
    plan_rows: list[list[int]],
    seed: int,
) -> FortressInteriorPlanResult:
    """Build a keep, small houses, paths, and trees inside a fortress.

    Args:
        runtime_data: Tactical runtime data.
        site_report: Fortress site report containing shell metadata.
        plan_rows: Fortress shell classification grid.
        seed: Resolved world seed.

    Returns:
        Interior plan and updated runtime metadata.

    Raises:
        ValueError: If the plan grid or required metadata is invalid.
    """
    if not plan_rows:
        return _empty_result(runtime_data=runtime_data, site_report=site_report)

    height = len(plan_rows)
    width = len(plan_rows[0])
    if width == 0 or any(len(row) != width for row in plan_rows):
        raise ValueError("Fortress interior requires a rectangular shell plan")

    plan_report = site_report.get("fortress_plan")
    if not isinstance(plan_report, dict):
        return _empty_result(runtime_data=runtime_data, site_report=site_report)
    center_raw = plan_report.get("center")
    gate_raw = plan_report.get("gate_center")
    if not isinstance(center_raw, dict) or not isinstance(gate_raw, dict):
        raise ValueError("Fortress interior requires center and gate metadata")

    center = (int(center_raw["x"]), int(center_raw["y"]))
    gate = (int(gate_raw["x"]), int(gate_raw["y"]))
    fortress_span = int(plan_report.get("fortress_span_tiles", 0))
    if fortress_span < 24:
        raise ValueError("Fortress interior requires a fortress span of at least 24")

    rng = Random(seed ^ 0x1A7E_1260_5EED)
    interior_rows = [[INTERIOR_NONE for _ in range(width)] for _ in range(height)]

    keep_radius = _clamp(round(fortress_span * 0.115), 5, 7)
    keep_center = _find_keep_center(
        plan_rows=plan_rows,
        center=center,
        gate=gate,
        radius=keep_radius,
        fortress_span=fortress_span,
    )
    keep_door = _draw_keep(
        interior_rows=interior_rows,
        center=keep_center,
        radius=keep_radius,
        gate=gate,
    )

    house_target = rng.randint(2, 3)
    houses = _place_houses(
        plan_rows=plan_rows,
        interior_rows=interior_rows,
        keep_center=keep_center,
        keep_radius=keep_radius,
        fortress_center=center,
        target_count=house_target,
        rng=rng,
    )

    path_width = _clamp(round(fortress_span * 0.045), 2, 3)
    _draw_path(
        interior_rows=interior_rows,
        plan_rows=plan_rows,
        start=gate,
        end=keep_door,
        radius=max(0, path_width // 2),
    )
    for house in houses:
        _draw_path(
            interior_rows=interior_rows,
            plan_rows=plan_rows,
            start=house.door,
            end=_nearest_path_point(interior_rows, house.door),
            radius=0,
        )

    tree_target = rng.randint(4, 10)
    tree_count = _place_trees(
        plan_rows=plan_rows,
        interior_rows=interior_rows,
        keep_center=keep_center,
        keep_radius=keep_radius,
        target_count=tree_target,
        rng=rng,
    )

    counts = _count_values(interior_rows)
    report = {
        "status": "planned",
        "algorithm": "courtyard_keep_houses_trees_v1",
        "seed": seed,
        "keep": {
            "shape": "round",
            "center": {"x": keep_center[0], "y": keep_center[1]},
            "radius_tiles": keep_radius,
            "diameter_tiles": keep_radius * 2 + 1,
            "height_levels_above_ground": 16,
            "door": {"x": keep_door[0], "y": keep_door[1]},
            "wall_tiles": counts[INTERIOR_KEEP_WALL],
            "floor_tiles": counts[INTERIOR_KEEP_FLOOR],
        },
        "houses": [
            {
                "bounds": {
                    "x": house.x0,
                    "y": house.y0,
                    "width": house.width,
                    "height": house.height,
                },
                "height_levels_above_ground": 5,
                "door": {"x": house.door[0], "y": house.door[1]},
            }
            for house in houses
        ],
        "house_count": len(houses),
        "requested_house_count": house_target,
        "tree_count": tree_count,
        "requested_tree_count": tree_target,
        "path_width_tiles": path_width,
        "path_tiles": counts[INTERIOR_PATH],
        "materialized_to_terrain": False,
    }

    updated_site_report = dict(site_report)
    policy = dict(updated_site_report.get("policy", {}))
    policy["phase"] = "fortress_interior_planned"
    updated_site_report["policy"] = policy
    updated_site_report["fortress_interior_plan"] = report

    updated_runtime = dict(runtime_data)
    updated_runtime["fortress_site"] = updated_site_report
    updated_runtime["fortress_interior_plan"] = report

    return FortressInteriorPlanResult(
        runtime_data=updated_runtime,
        site_report=updated_site_report,
        interior_rows=interior_rows,
        keep_tiles=counts[INTERIOR_KEEP_WALL] + counts[INTERIOR_KEEP_FLOOR],
        house_count=len(houses),
        tree_count=tree_count,
        path_tiles=counts[INTERIOR_PATH],
    )


def _empty_result(
    *,
    runtime_data: dict[str, Any],
    site_report: dict[str, Any],
) -> FortressInteriorPlanResult:
    return FortressInteriorPlanResult(
        runtime_data=runtime_data,
        site_report=site_report,
        interior_rows=[],
        keep_tiles=0,
        house_count=0,
        tree_count=0,
        path_tiles=0,
    )


def _find_keep_center(
    *,
    plan_rows: list[list[int]],
    center: tuple[int, int],
    gate: tuple[int, int],
    radius: int,
    fortress_span: int,
) -> tuple[int, int]:
    dx = center[0] - gate[0]
    dy = center[1] - gate[1]
    length = hypot(dx, dy) or 1.0
    offset = fortress_span * 0.08
    target = (
        round(center[0] + dx / length * offset),
        round(center[1] + dy / length * offset),
    )
    candidates: list[tuple[float, tuple[int, int]]] = []
    search_radius = max(4, round(fortress_span * 0.16))
    for y in range(target[1] - search_radius, target[1] + search_radius + 1):
        for x in range(target[0] - search_radius, target[0] + search_radius + 1):
            if not _disk_fits_courtyard(
                plan_rows=plan_rows,
                center=(x, y),
                radius=radius + 2,
            ):
                continue
            score = hypot(x - target[0], y - target[1])
            candidates.append((score, (x, y)))
    if not candidates:
        raise ValueError("No valid courtyard location for the central keep")
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _draw_keep(
    *,
    interior_rows: list[list[int]],
    center: tuple[int, int],
    radius: int,
    gate: tuple[int, int],
) -> tuple[int, int]:
    cx, cy = center
    inner_radius = max(2, radius - 2)
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            distance_sq = (x - cx) ** 2 + (y - cy) ** 2
            if distance_sq <= inner_radius**2:
                interior_rows[y][x] = INTERIOR_KEEP_FLOOR
            elif distance_sq <= radius**2:
                interior_rows[y][x] = INTERIOR_KEEP_WALL

    dx = gate[0] - cx
    dy = gate[1] - cy
    length = hypot(dx, dy) or 1.0
    door = (
        round(cx + dx / length * radius),
        round(cy + dy / length * radius),
    )
    interior_rows[door[1]][door[0]] = INTERIOR_PATH
    return door


def _place_houses(
    *,
    plan_rows: list[list[int]],
    interior_rows: list[list[int]],
    keep_center: tuple[int, int],
    keep_radius: int,
    fortress_center: tuple[int, int],
    target_count: int,
    rng: Random,
) -> list[_House]:
    height = len(plan_rows)
    width = len(plan_rows[0])
    dimensions = [(5, 7), (6, 8), (7, 9), (7, 5), (8, 6), (9, 7)]
    candidates = [
        (x, y)
        for y in range(2, height - 2)
        for x in range(2, width - 2)
        if plan_rows[y][x] == PLAN_COURTYARD
    ]
    rng.shuffle(candidates)
    houses: list[_House] = []
    for x0, y0 in candidates:
        if len(houses) >= target_count:
            break
        house_width, house_height = rng.choice(dimensions)
        x1 = x0 + house_width - 1
        y1 = y0 + house_height - 1
        if x1 >= width - 1 or y1 >= height - 1:
            continue
        if not _rectangle_fits(
            plan_rows=plan_rows,
            interior_rows=interior_rows,
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
        ):
            continue
        house_center = ((x0 + x1) // 2, (y0 + y1) // 2)
        if hypot(
            house_center[0] - keep_center[0],
            house_center[1] - keep_center[1],
        ) < keep_radius + 5:
            continue
        if not _near_shell(plan_rows=plan_rows, x0=x0, y0=y0, x1=x1, y1=y1):
            continue
        door = _house_door(
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            target=fortress_center,
        )
        _draw_house(
            interior_rows=interior_rows,
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            door=door,
        )
        houses.append(
            _House(
                x0=x0,
                y0=y0,
                width=house_width,
                height=house_height,
                door=door,
            )
        )
    if len(houses) < 2:
        raise ValueError("Fortress interior could not place at least two houses")
    return houses


def _rectangle_fits(
    *,
    plan_rows: list[list[int]],
    interior_rows: list[list[int]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> bool:
    for y in range(y0 - 1, y1 + 2):
        for x in range(x0 - 1, x1 + 2):
            if y < 0 or x < 0 or y >= len(plan_rows) or x >= len(plan_rows[0]):
                return False
            if plan_rows[y][x] != PLAN_COURTYARD:
                return False
            if interior_rows[y][x] in {
                INTERIOR_KEEP_WALL,
                INTERIOR_KEEP_FLOOR,
                INTERIOR_HOUSE_WALL,
                INTERIOR_HOUSE_FLOOR,
            }:
                return False
    return True


def _near_shell(
    *,
    plan_rows: list[list[int]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> bool:
    margin = 8
    for y in range(max(0, y0 - margin), min(len(plan_rows), y1 + margin + 1)):
        for x in range(max(0, x0 - margin), min(len(plan_rows[0]), x1 + margin + 1)):
            if plan_rows[y][x] != PLAN_COURTYARD:
                return True
    return False


def _house_door(
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    target: tuple[int, int],
) -> tuple[int, int]:
    candidates = (
        ((x0 + x1) // 2, y0),
        ((x0 + x1) // 2, y1),
        (x0, (y0 + y1) // 2),
        (x1, (y0 + y1) // 2),
    )
    return min(candidates, key=lambda point: hypot(point[0] - target[0], point[1] - target[1]))


def _draw_house(
    *,
    interior_rows: list[list[int]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    door: tuple[int, int],
) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            value = (
                INTERIOR_HOUSE_WALL
                if x in {x0, x1} or y in {y0, y1}
                else INTERIOR_HOUSE_FLOOR
            )
            interior_rows[y][x] = value
    interior_rows[door[1]][door[0]] = INTERIOR_PATH


def _draw_path(
    *,
    interior_rows: list[list[int]],
    plan_rows: list[list[int]],
    start: tuple[int, int],
    end: tuple[int, int],
    radius: int,
) -> None:
    for x, y in _line_points(start=start, end=end):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                px = x + dx
                py = y + dy
                if not (0 <= py < len(plan_rows) and 0 <= px < len(plan_rows[0])):
                    continue
                if plan_rows[py][px] not in {PLAN_COURTYARD}:
                    continue
                if interior_rows[py][px] in {INTERIOR_NONE, INTERIOR_TREE}:
                    interior_rows[py][px] = INTERIOR_PATH


def _nearest_path_point(
    interior_rows: list[list[int]],
    start: tuple[int, int],
) -> tuple[int, int]:
    points: list[tuple[float, tuple[int, int]]] = []
    for y, row in enumerate(interior_rows):
        for x, value in enumerate(row):
            if value == INTERIOR_PATH:
                points.append((hypot(x - start[0], y - start[1]), (x, y)))
    if not points:
        return start
    points.sort(key=lambda item: item[0])
    return points[0][1]


def _place_trees(
    *,
    plan_rows: list[list[int]],
    interior_rows: list[list[int]],
    keep_center: tuple[int, int],
    keep_radius: int,
    target_count: int,
    rng: Random,
) -> int:
    candidates: list[tuple[int, int]] = []
    for y, row in enumerate(plan_rows):
        for x, value in enumerate(row):
            if value != PLAN_COURTYARD or interior_rows[y][x] != INTERIOR_NONE:
                continue
            if hypot(x - keep_center[0], y - keep_center[1]) < keep_radius + 4:
                continue
            if _has_interior_neighbor(interior_rows, x=x, y=y, radius=2):
                continue
            candidates.append((x, y))
    rng.shuffle(candidates)
    selected: list[tuple[int, int]] = []
    for point in candidates:
        if len(selected) >= target_count:
            break
        if any(hypot(point[0] - x, point[1] - y) < 3 for x, y in selected):
            continue
        interior_rows[point[1]][point[0]] = INTERIOR_TREE
        selected.append(point)
    return len(selected)


def _has_interior_neighbor(
    rows: list[list[int]],
    *,
    x: int,
    y: int,
    radius: int,
) -> bool:
    for py in range(max(0, y - radius), min(len(rows), y + radius + 1)):
        for px in range(max(0, x - radius), min(len(rows[0]), x + radius + 1)):
            if rows[py][px] != INTERIOR_NONE:
                return True
    return False


def _disk_fits_courtyard(
    *,
    plan_rows: list[list[int]],
    center: tuple[int, int],
    radius: int,
) -> bool:
    cx, cy = center
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 > radius**2:
                continue
            if y < 0 or x < 0 or y >= len(plan_rows) or x >= len(plan_rows[0]):
                return False
            if plan_rows[y][x] != PLAN_COURTYARD:
                return False
    return True


def _line_points(
    *,
    start: tuple[int, int],
    end: tuple[int, int],
) -> list[tuple[int, int]]:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    points: list[tuple[int, int]] = []
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        twice_error = 2 * error
        if twice_error >= dy:
            error += dy
            x0 += sx
        if twice_error <= dx:
            error += dx
            y0 += sy
    return points


def _count_values(rows: list[list[int]]) -> dict[int, int]:
    counts = {value: 0 for value in range(INTERIOR_TREE + 1)}
    for row in rows:
        for value in row:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
