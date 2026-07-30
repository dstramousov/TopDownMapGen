from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any

MICRO_DIVISION = 4
FULL_MICRO_MASK = 0xFFFF

STRUCTURE_TYPE_NAMES: dict[int, str] = {
    0: "none",
    1: "ruin_wall",
    2: "ruin_floor",
    10: "fortress_wall",
    11: "fortress_tower",
    12: "fortress_gate",
    13: "fortress_keep",
    14: "fortress_building",
    15: "fortress_floor",
    20: "building_wall",
    21: "building_floor",
}

_NAME_TO_ID = {name: value for value, name in STRUCTURE_TYPE_NAMES.items()}




@dataclass(frozen=True, slots=True)
class _FortressWallPath:
    """One planned fortress wall centerline segment."""

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    bend: float

@dataclass(frozen=True, slots=True)
class StructureGeometry:
    """Logical structure classification and per-tile micro occupancy."""

    type_rows: list[list[int]]
    mask_rows: list[list[int]]
    summary: dict[str, int]


def build_structure_geometry(
    *,
    terrain_rows: list[list[str]],
    fortress_plan: object | None,
    ruin_sites: object | None = None,
) -> StructureGeometry:
    """Build structure type and 4x4 occupancy layers from current map data."""
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if terrain_rows else 0
    if any(len(row) != width for row in terrain_rows):
        raise ValueError("Structure geometry requires rectangular terrain rows")

    type_rows = [[0 for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(terrain_rows):
        for x, terrain in enumerate(row):
            if terrain == "ruin_wall_blocker":
                type_rows[y][x] = _NAME_TO_ID["ruin_wall"]
            elif terrain == "ruin_floor":
                type_rows[y][x] = _NAME_TO_ID["ruin_floor"]

    _overlay_fortress_types(type_rows, fortress_plan)
    _fill_fortress_keep_footprints(type_rows)
    solid_type_ids = {
        _NAME_TO_ID["ruin_wall"],
        _NAME_TO_ID["fortress_wall"],
        _NAME_TO_ID["fortress_tower"],
        _NAME_TO_ID["fortress_keep"],
        _NAME_TO_ID["fortress_building"],
        _NAME_TO_ID["building_wall"],
    }
    mask_rows = [
        [FULL_MICRO_MASK if value in solid_type_ids else 0 for value in row]
        for row in type_rows
    ]
    _overlay_linear_structure_masks(type_rows=type_rows, mask_rows=mask_rows)
    _overlay_ruin_site_masks(
        type_rows=type_rows,
        mask_rows=mask_rows,
        ruin_sites=ruin_sites,
    )
    _overlay_fortress_shell_masks(
        type_rows=type_rows,
        mask_rows=mask_rows,
        fortress_plan=fortress_plan,
    )

    counts: dict[str, int] = {name: 0 for name in STRUCTURE_TYPE_NAMES.values()}
    full_micro_cells = 0
    partial_micro_cells = 0
    for y, row in enumerate(type_rows):
        for x, value in enumerate(row):
            counts[STRUCTURE_TYPE_NAMES[value]] += 1
            mask = mask_rows[y][x]
            if mask == FULL_MICRO_MASK:
                full_micro_cells += 1
            elif mask:
                partial_micro_cells += 1
    counts["micro_cells"] = full_micro_cells + partial_micro_cells
    counts["full_micro_cells"] = full_micro_cells
    counts["partial_micro_cells"] = partial_micro_cells
    return StructureGeometry(type_rows=type_rows, mask_rows=mask_rows, summary=counts)


def sparse_micro_cells(geometry: StructureGeometry) -> list[dict[str, int]]:
    """Return non-empty micro masks in deterministic row-major order."""
    return [
        {"x": x, "y": y, "mask": mask}
        for y, row in enumerate(geometry.mask_rows)
        for x, mask in enumerate(row)
        if mask
    ]


def _overlay_fortress_types(
    type_rows: list[list[int]],
    fortress_plan: object | None,
) -> None:
    if not isinstance(fortress_plan, dict):
        return
    materialization = fortress_plan.get("materialization")
    if not isinstance(materialization, dict):
        return
    entries = materialization.get("structure_types")
    if not isinstance(entries, list):
        return
    height = len(type_rows)
    width = len(type_rows[0]) if type_rows else 0
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 3:
            continue
        x, y, name = entry
        if not isinstance(x, int) or not isinstance(y, int) or not isinstance(name, str):
            continue
        type_id = _NAME_TO_ID.get(name)
        if type_id is None:
            continue
        if 0 <= x < width and 0 <= y < height:
            type_rows[y][x] = type_id



def _fill_fortress_keep_footprints(type_rows: list[list[int]]) -> None:
    """Fill enclosed keep interiors so the citadel is one solid prism."""
    keep_id = _NAME_TO_ID["fortress_keep"]
    keep_tiles = {
        (x, y)
        for y, row in enumerate(type_rows)
        for x, value in enumerate(row)
        if value == keep_id
    }
    if not keep_tiles:
        return
    min_x = min(x for x, _y in keep_tiles)
    max_x = max(x for x, _y in keep_tiles)
    min_y = min(y for _x, y in keep_tiles)
    max_y = max(y for _x, y in keep_tiles)
    exterior: set[tuple[int, int]] = set()
    stack = [
        (x, y)
        for y in range(min_y, max_y + 1)
        for x in range(min_x, max_x + 1)
        if (x in {min_x, max_x} or y in {min_y, max_y})
        and (x, y) not in keep_tiles
    ]
    while stack:
        point = stack.pop()
        if point in exterior or point in keep_tiles:
            continue
        x, y = point
        if not (min_x <= x <= max_x and min_y <= y <= max_y):
            continue
        exterior.add(point)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            if (x, y) not in keep_tiles and (x, y) not in exterior:
                type_rows[y][x] = keep_id


def _overlay_linear_structure_masks(
    *,
    type_rows: list[list[int]],
    mask_rows: list[list[int]],
) -> None:
    """Rasterize non-round walls as thin connected 4x4 micro geometry."""
    linear_type_ids = {
        _NAME_TO_ID["ruin_wall"],
        _NAME_TO_ID["fortress_building"],
        _NAME_TO_ID["building_wall"],
    }
    height = len(type_rows)
    width = len(type_rows[0]) if type_rows else 0
    for y, row in enumerate(type_rows):
        for x, type_id in enumerate(row):
            if type_id not in linear_type_ids:
                continue
            connected = {
                "north": y > 0 and type_rows[y - 1][x] == type_id,
                "south": y + 1 < height and type_rows[y + 1][x] == type_id,
                "west": x > 0 and type_rows[y][x - 1] == type_id,
                "east": x + 1 < width and type_rows[y][x + 1] == type_id,
            }
            mask_rows[y][x] = _connected_wall_mask(connected)


def _connected_wall_mask(connected: dict[str, bool]) -> int:
    """Return a two-subtile-thick connected wall mask for one base tile."""
    occupied: set[tuple[int, int]] = {(1, 1), (2, 1), (1, 2), (2, 2)}
    if connected["north"]:
        occupied.update({(1, 0), (2, 0)})
    if connected["south"]:
        occupied.update({(1, 3), (2, 3)})
    if connected["west"]:
        occupied.update({(0, 1), (0, 2)})
    if connected["east"]:
        occupied.update({(3, 1), (3, 2)})
    mask = 0
    for subtile_x, subtile_y in occupied:
        mask |= 1 << (subtile_y * MICRO_DIVISION + subtile_x)
    return mask


def _overlay_ruin_site_masks(
    *,
    type_rows: list[list[int]],
    mask_rows: list[list[int]],
    ruin_sites: object | None,
) -> None:
    """Rasterize each planned ruin building on one shared micro grid."""
    buildings = _iter_ruin_buildings(ruin_sites)
    if not buildings:
        return

    ruin_wall_id = _NAME_TO_ID["ruin_wall"]
    for building in buildings:
        architecture = building.get("architecture")
        if not isinstance(architecture, dict):
            continue
        runs = _parse_ruin_wall_runs(architecture.get("wall_runs"))
        if not runs:
            continue
        wall_points = {point for run in runs for point in run}
        segments = tuple(
            (float(a[0]), float(a[1]), float(b[0]), float(b[1]))
            for run in runs
            for a, b in zip(run, run[1:])
        )
        endpoints = _ruin_run_endpoints(runs)
        severity = _ruin_damage_severity(architecture)
        building_masks: dict[tuple[int, int], int] = {}
        for x, y in wall_points:
            if not _grid_point_has_type(type_rows, x, y, ruin_wall_id):
                continue
            mask = _ruin_wall_tile_mask(
                x=x,
                y=y,
                segments=segments,
                wall_points=wall_points,
            )
            if mask:
                building_masks[(x, y)] = mask
        _damage_ruin_micro_plan(
            masks=building_masks,
            runs=runs,
            endpoints=endpoints,
            severity=severity,
        )
        for (x, y), mask in building_masks.items():
            if mask:
                mask_rows[y][x] = mask


def _iter_ruin_buildings(ruin_sites: object | None) -> list[dict[str, object]]:
    """Return valid building dictionaries from ruin-site metadata."""
    if not isinstance(ruin_sites, dict):
        return []
    sites = ruin_sites.get("sites")
    if not isinstance(sites, list):
        return []
    result: list[dict[str, object]] = []
    for site in sites:
        if not isinstance(site, dict):
            continue
        buildings = site.get("buildings")
        if not isinstance(buildings, list):
            continue
        result.extend(item for item in buildings if isinstance(item, dict))
    return result


def _parse_ruin_wall_runs(raw_runs: object) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Parse architecture wall runs into deterministic point sequences."""
    if not isinstance(raw_runs, list):
        return ()
    parsed: list[tuple[tuple[int, int], ...]] = []
    for raw_run in raw_runs:
        if not isinstance(raw_run, dict):
            continue
        raw_points = raw_run.get("points")
        if not isinstance(raw_points, list):
            continue
        points: list[tuple[int, int]] = []
        for raw_point in raw_points:
            if (
                isinstance(raw_point, list)
                and len(raw_point) == 2
                and isinstance(raw_point[0], int)
                and isinstance(raw_point[1], int)
            ):
                points.append((raw_point[0], raw_point[1]))
        if points:
            parsed.append(tuple(points))
    return tuple(parsed)


def _ruin_run_endpoints(
    runs: tuple[tuple[tuple[int, int], ...], ...],
) -> set[tuple[int, int]]:
    """Return run endpoints that are not shared with another run."""
    counts: dict[tuple[int, int], int] = {}
    for run in runs:
        for point in {run[0], run[-1]}:
            counts[point] = counts.get(point, 0) + 1
    return {point for point, count in counts.items() if count == 1}


def _grid_point_has_type(
    type_rows: list[list[int]],
    x: int,
    y: int,
    expected_type: int,
) -> bool:
    """Return whether one world point is in bounds and has the expected type."""
    return (
        0 <= y < len(type_rows)
        and 0 <= x < len(type_rows[y])
        and type_rows[y][x] == expected_type
    )


def _ruin_wall_tile_mask(
    *,
    x: int,
    y: int,
    segments: tuple[tuple[float, float, float, float], ...],
    wall_points: set[tuple[int, int]],
) -> int:
    """Rasterize a two-subtile ruin wall using building-wide geometry."""
    half_width = 0.26
    mask = 0
    for subtile_y in range(MICRO_DIVISION):
        for subtile_x in range(MICRO_DIVISION):
            sample_x = x - 0.5 + (subtile_x + 0.5) / MICRO_DIVISION
            sample_y = y - 0.5 + (subtile_y + 0.5) / MICRO_DIVISION
            touches_segment = any(
                _point_segment_distance(sample_x, sample_y, *segment) <= half_width
                for segment in segments
            )
            touches_point = any(
                hypot(sample_x - point_x, sample_y - point_y) <= half_width
                for point_x, point_y in wall_points
                if abs(point_x - x) <= 1 and abs(point_y - y) <= 1
            )
            if touches_segment or touches_point:
                mask |= 1 << (subtile_y * MICRO_DIVISION + subtile_x)
    return mask



def _ruin_damage_severity(architecture: dict[str, object]) -> str:
    """Return a supported micro-damage severity for one ruin building."""
    raw = architecture.get("destruction_severity")
    if isinstance(raw, str) and raw in {"light", "moderate", "heavy"}:
        return raw
    return "moderate"


def _damage_ruin_micro_plan(
    *,
    masks: dict[tuple[int, int], int],
    runs: tuple[tuple[tuple[int, int], ...], ...],
    endpoints: set[tuple[int, int]],
    severity: str,
) -> None:
    """Apply deterministic, connected-looking damage to one ruin micro plan."""
    if not masks:
        return
    endpoint_depth = {"light": 1, "moderate": 2, "heavy": 3}[severity]
    corner_depth = {"light": 0, "moderate": 1, "heavy": 2}[severity]
    breach_count = {"light": 0, "moderate": 1, "heavy": 2}[severity]

    for point in sorted(endpoints):
        mask = masks.get(point)
        if mask is None:
            continue
        masks[point] = _chip_ruin_endpoint(
            mask=mask,
            x=point[0],
            y=point[1],
            depth=endpoint_depth,
        )

    if corner_depth:
        for point in sorted(_ruin_corner_points(runs)):
            mask = masks.get(point)
            if mask is None:
                continue
            masks[point] = _chip_ruin_corner(
                mask=mask,
                x=point[0],
                y=point[1],
                depth=corner_depth,
            )

    candidates = _ruin_breach_candidates(runs)
    if breach_count and candidates:
        seed = sum((x * 73) ^ (y * 151) for x, y in masks)
        ordered = sorted(candidates, key=lambda p: ((p[0] * 97) ^ (p[1] * 193) ^ seed, p))
        for point in ordered[:breach_count]:
            mask = masks.get(point)
            if mask is None:
                continue
            damaged = _cut_ruin_breach(mask=mask, x=point[0], y=point[1])
            if damaged:
                masks[point] = damaged

    _remove_isolated_micro_bits(masks)


def _ruin_corner_points(
    runs: tuple[tuple[tuple[int, int], ...], ...],
) -> set[tuple[int, int]]:
    """Return points where horizontal and vertical wall runs meet."""
    horizontal: set[tuple[int, int]] = set()
    vertical: set[tuple[int, int]] = set()
    for run in runs:
        for a, b in zip(run, run[1:]):
            target = horizontal if a[1] == b[1] else vertical
            target.update((a, b))
    return horizontal & vertical


def _ruin_breach_candidates(
    runs: tuple[tuple[tuple[int, int], ...], ...],
) -> set[tuple[int, int]]:
    """Return interior points of long straight wall runs suitable for breaches."""
    candidates: set[tuple[int, int]] = set()
    for run in runs:
        if len(run) < 5:
            continue
        candidates.update(run[2:-2])
    return candidates


def _chip_ruin_corner(*, mask: int, x: int, y: int, depth: int) -> int:
    """Cut a deterministic staircase from one ruin corner tile."""
    corners = (0, 3, 12, 15)
    corner = corners[((x * 43) ^ (y * 89)) & 3]
    paths = {
        0: (0, 1, 4, 5),
        3: (3, 2, 7, 6),
        12: (12, 13, 8, 9),
        15: (15, 14, 11, 10),
    }
    damaged = mask
    for bit_index in paths[corner][: depth + 1]:
        damaged &= ~(1 << bit_index)
    return damaged or mask


def _cut_ruin_breach(*, mask: int, x: int, y: int) -> int:
    """Cut an asymmetric local breach while retaining part of the wall tile."""
    horizontal = bool(mask & 0x0FF0) and not bool(mask & 0x6666 == 0x6666)
    patterns = (0x0660, 0x0990) if horizontal else (0x0222, 0x4444)
    remove = patterns[((x * 29) ^ (y * 61)) & 1]
    damaged = mask & ~remove
    return damaged if damaged else mask


def _remove_isolated_micro_bits(masks: dict[tuple[int, int], int]) -> None:
    """Remove singleton micro voxels that have no orthogonal neighbour."""
    occupied: set[tuple[int, int]] = set()
    for (tile_x, tile_y), mask in masks.items():
        for sy in range(MICRO_DIVISION):
            for sx in range(MICRO_DIVISION):
                bit = sy * MICRO_DIVISION + sx
                if mask & (1 << bit):
                    occupied.add((tile_x * MICRO_DIVISION + sx, tile_y * MICRO_DIVISION + sy))
    isolated = {
        point
        for point in occupied
        if not any(
            (point[0] + dx, point[1] + dy) in occupied
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    }
    for micro_x, micro_y in isolated:
        tile_x, sx = divmod(micro_x, MICRO_DIVISION)
        tile_y, sy = divmod(micro_y, MICRO_DIVISION)
        key = (tile_x, tile_y)
        masks[key] &= ~(1 << (sy * MICRO_DIVISION + sx))


def _chip_ruin_endpoint(*, mask: int, x: int, y: int, depth: int = 1) -> int:
    """Remove one deterministic edge subtile from a broken wall endpoint."""
    candidates = (
        (0, 1, 4),
        (3, 2, 7),
        (12, 13, 8),
        (15, 14, 11),
    )
    path = candidates[((x * 31) ^ (y * 17)) & 3]
    chipped = mask
    for bit_index in path[: max(1, min(depth, len(path)))]:
        chipped &= ~(1 << bit_index)
    return chipped or mask

def _overlay_fortress_shell_masks(
    *,
    type_rows: list[list[int]],
    mask_rows: list[list[int]],
    fortress_plan: object | None,
) -> None:
    """Rasterize fortress walls and towers from one global micro plan."""
    if not isinstance(fortress_plan, dict):
        return
    raw_segments = fortress_plan.get("segments", [])
    raw_towers = fortress_plan.get("towers", [])
    if not isinstance(raw_segments, list):
        raw_segments = []
    if not isinstance(raw_towers, list):
        raw_towers = []

    wall_paths = _parse_wall_paths(raw_segments)
    towers = _parse_shell_towers(raw_towers)
    if not wall_paths and not towers:
        return

    height = len(type_rows)
    width = len(type_rows[0]) if type_rows else 0
    if width == 0 or height == 0:
        return
    micro_width = width * MICRO_DIVISION
    micro_height = height * MICRO_DIVISION

    sampled_segments = tuple(
        segment
        for path in wall_paths
        for segment in _sample_wall_path(path)
    )
    wall_width_subtiles = _fortress_wall_width_subtiles(towers)
    wall_points = _rasterize_wall_band(
        segments=sampled_segments,
        width_subtiles=wall_width_subtiles,
        micro_width=micro_width,
        micro_height=micro_height,
    )
    tower_points = _rasterize_tower_disks(
        towers=towers,
        width=micro_width,
        height=micro_height,
    )
    wall_points.difference_update(tower_points)

    gate = _parse_gate_opening(fortress_plan, segments=sampled_segments)
    if gate is not None:
        wall_points = {
            point
            for point in wall_points
            if not _inside_gate_opening(
                sample_x=_micro_sample_coordinate(point[0]),
                sample_y=_micro_sample_coordinate(point[1]),
                gate=gate,
            )
        }

    wall_masks = [[0 for _ in range(width)] for _ in range(height)]
    tower_masks = [[0 for _ in range(width)] for _ in range(height)]
    _pack_micro_points(wall_points, wall_masks)
    _pack_micro_points(tower_points, tower_masks)

    wall_id = _NAME_TO_ID["fortress_wall"]
    tower_id = _NAME_TO_ID["fortress_tower"]
    gate_id = _NAME_TO_ID["fortress_gate"]
    shell_ids = {wall_id, tower_id, gate_id}
    for y in range(height):
        for x in range(width):
            original_type = type_rows[y][x]
            if original_type in shell_ids:
                type_rows[y][x] = 0
                mask_rows[y][x] = 0
            tower_mask = tower_masks[y][x]
            wall_mask = wall_masks[y][x]
            if original_type == gate_id and not tower_mask:
                continue
            if tower_mask:
                type_rows[y][x] = tower_id
                mask_rows[y][x] = tower_mask
            elif wall_mask:
                type_rows[y][x] = wall_id
                mask_rows[y][x] = wall_mask


def _sample_wall_path_points(
    path: _FortressWallPath,
) -> tuple[tuple[int, int], ...]:
    """Return a dense ordered micro-grid centerline for one wall path."""
    dx = path.end_x - path.start_x
    dy = path.end_y - path.start_y
    length = max(0.25, hypot(dx, dy))
    steps = max(1, int(length * MICRO_DIVISION * 2))
    midpoint_x = (path.start_x + path.end_x) / 2.0
    midpoint_y = (path.start_y + path.end_y) / 2.0
    normal_x = -dy / length
    normal_y = dx / length
    control_x = midpoint_x + normal_x * length * path.bend
    control_y = midpoint_y + normal_y * length * path.bend
    result: list[tuple[int, int]] = []
    for step in range(steps + 1):
        t = step / steps
        inv = 1.0 - t
        world_x = (
            inv * inv * path.start_x
            + 2.0 * inv * t * control_x
            + t * t * path.end_x
        )
        world_y = (
            inv * inv * path.start_y
            + 2.0 * inv * t * control_y
            + t * t * path.end_y
        )
        point = (_world_to_micro(world_x), _world_to_micro(world_y))
        if not result or result[-1] != point:
            result.append(point)
    return tuple(result)


def _world_to_micro(value: float) -> int:
    """Convert a tile-center world coordinate to a micro-grid index."""
    return round((value + 0.375) * MICRO_DIVISION)


def _micro_sample_coordinate(index: int) -> float:
    """Return the world coordinate of one micro-grid sample center."""
    return index / MICRO_DIVISION - 0.375


def _rasterize_wall_band(
    *,
    segments: tuple[tuple[float, float, float, float], ...],
    width_subtiles: int,
    micro_width: int,
    micro_height: int,
) -> set[tuple[int, int]]:
    """Rasterize a constant-width band around the complete wall centerline.

    Each sampled segment contributes one capsule of the same radius. Their
    union is the exact constant-distance band around the polyline, so bends
    and tower connections cannot widen or narrow the wall.
    """
    if not segments or width_subtiles <= 0:
        return set()
    half_width_tiles = width_subtiles / (2.0 * MICRO_DIVISION)
    tolerance = 1e-9
    occupied: set[tuple[int, int]] = set()
    for segment in segments:
        x0, y0, x1, y1 = segment
        minimum_x = max(
            0,
            _world_to_micro(min(x0, x1) - half_width_tiles) - 2,
        )
        maximum_x = min(
            micro_width - 1,
            _world_to_micro(max(x0, x1) + half_width_tiles) + 2,
        )
        minimum_y = max(
            0,
            _world_to_micro(min(y0, y1) - half_width_tiles) - 2,
        )
        maximum_y = min(
            micro_height - 1,
            _world_to_micro(max(y0, y1) + half_width_tiles) + 2,
        )
        for micro_y in range(minimum_y, maximum_y + 1):
            sample_y = _micro_sample_coordinate(micro_y)
            for micro_x in range(minimum_x, maximum_x + 1):
                sample_x = _micro_sample_coordinate(micro_x)
                if (
                    _point_segment_distance(sample_x, sample_y, *segment)
                    <= half_width_tiles + tolerance
                ):
                    occupied.add((micro_x, micro_y))
    return occupied


def _fortress_wall_width_subtiles(
    towers: tuple[tuple[float, float, float], ...],
) -> int:
    """Return one immutable wall width derived from tower diameter."""
    if not towers:
        return 6
    radii = sorted(radius for _x, _y, radius in towers)
    representative_radius = radii[len(radii) // 2]
    desired_thickness = round(representative_radius * MICRO_DIVISION)
    return min(16, max(6, desired_thickness))


def _rasterize_tower_disks(
    *,
    towers: tuple[tuple[float, float, float], ...],
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    """Rasterize independent circular tower bodies on the global micro grid."""
    occupied: set[tuple[int, int]] = set()
    for center_x, center_y, radius in towers:
        micro_radius = int(radius * MICRO_DIVISION) + 2
        center_micro_x = _world_to_micro(center_x)
        center_micro_y = _world_to_micro(center_y)
        for micro_y in range(center_micro_y - micro_radius, center_micro_y + micro_radius + 1):
            if not 0 <= micro_y < height:
                continue
            sample_y = _micro_sample_coordinate(micro_y)
            for micro_x in range(center_micro_x - micro_radius, center_micro_x + micro_radius + 1):
                if not 0 <= micro_x < width:
                    continue
                sample_x = _micro_sample_coordinate(micro_x)
                if hypot(sample_x - center_x, sample_y - center_y) <= radius:
                    occupied.add((micro_x, micro_y))
    return occupied


def _pack_micro_points(
    points: set[tuple[int, int]],
    rows: list[list[int]],
) -> None:
    """Pack global micro-grid points into per-tile uint16 masks."""
    for micro_x, micro_y in points:
        tile_x, subtile_x = divmod(micro_x, MICRO_DIVISION)
        tile_y, subtile_y = divmod(micro_y, MICRO_DIVISION)
        rows[tile_y][tile_x] |= 1 << (subtile_y * MICRO_DIVISION + subtile_x)


def _parse_shell_towers(
    towers: list[object],
) -> tuple[tuple[float, float, float], ...]:
    """Parse tower centers and exact outer radii in tile coordinates."""
    parsed: list[tuple[float, float, float]] = []
    for item in towers:
        if not isinstance(item, dict):
            continue
        center = item.get("center")
        radius = item.get("radius_tiles")
        if not isinstance(center, dict) or not isinstance(radius, int):
            continue
        center_x = center.get("x")
        center_y = center.get("y")
        if not isinstance(center_x, int) or not isinstance(center_y, int):
            continue
        parsed.append((float(center_x), float(center_y), max(1.0, float(radius))))
    return tuple(parsed)


def _parse_gate_opening(
    fortress_plan: dict[str, object],
    *,
    segments: tuple[tuple[float, float, float, float], ...],
) -> tuple[float, float, float, float, float] | None:
    """Return gate center, tangent, and half width in tile coordinates."""
    center = fortress_plan.get("gate_center")
    width = fortress_plan.get("gate_width_tiles")
    if not isinstance(center, dict) or not isinstance(width, int) or width <= 0:
        return None
    center_x = center.get("x")
    center_y = center.get("y")
    if not isinstance(center_x, int) or not isinstance(center_y, int):
        return None
    if not segments:
        return None
    nearest = min(
        segments,
        key=lambda segment: _point_segment_distance(
            float(center_x), float(center_y), *segment
        ),
    )
    dx = nearest[2] - nearest[0]
    dy = nearest[3] - nearest[1]
    length = hypot(dx, dy)
    if length <= 0.0:
        return None
    return (
        float(center_x),
        float(center_y),
        dx / length,
        dy / length,
        max(0.5, width / 2.0 - 0.25),
    )


def _inside_gate_opening(
    *,
    sample_x: float,
    sample_y: float,
    gate: tuple[float, float, float, float, float] | None,
) -> bool:
    """Return whether a sample belongs to the intentional gate corridor."""
    if gate is None:
        return False
    center_x, center_y, tangent_x, tangent_y, half_width = gate
    offset_x = sample_x - center_x
    offset_y = sample_y - center_y
    along = offset_x * tangent_x + offset_y * tangent_y
    across = -offset_x * tangent_y + offset_y * tangent_x
    return abs(along) <= half_width and abs(across) <= 1.0


def _parse_wall_paths(raw_segments: list[object]) -> tuple[_FortressWallPath, ...]:
    """Parse straight and curved wall centerlines from fortress metadata."""
    parsed: list[_FortressWallPath] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            continue
        values = (start.get("x"), start.get("y"), end.get("x"), end.get("y"))
        if not all(isinstance(value, int) for value in values):
            continue
        bend = item.get("bend", 0.0)
        if not isinstance(bend, (int, float)):
            bend = 0.0
        parsed.append(
            _FortressWallPath(
                start_x=float(values[0]),
                start_y=float(values[1]),
                end_x=float(values[2]),
                end_y=float(values[3]),
                bend=float(bend),
            )
        )
    return tuple(parsed)


def _sample_wall_path(
    path: _FortressWallPath,
) -> tuple[tuple[float, float, float, float], ...]:
    """Approximate one wall centerline with quarter-tile line segments."""
    dx = path.end_x - path.start_x
    dy = path.end_y - path.start_y
    length = max(0.25, hypot(dx, dy))
    steps = max(1, int(length * MICRO_DIVISION * 2))
    midpoint_x = (path.start_x + path.end_x) / 2.0
    midpoint_y = (path.start_y + path.end_y) / 2.0
    normal_x = -dy / length
    normal_y = dx / length
    control_x = midpoint_x + normal_x * length * path.bend
    control_y = midpoint_y + normal_y * length * path.bend
    points: list[tuple[float, float]] = []
    for step in range(steps + 1):
        t = step / steps
        inv = 1.0 - t
        x = (
            inv * inv * path.start_x
            + 2.0 * inv * t * control_x
            + t * t * path.end_x
        )
        y = (
            inv * inv * path.start_y
            + 2.0 * inv * t * control_y
            + t * t * path.end_y
        )
        points.append((x, y))
    return tuple(
        (first[0], first[1], second[0], second[1])
        for first, second in zip(points, points[1:], strict=False)
    )


def _point_segment_distance(
    px: float,
    py: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> float:
    dx = x1 - x0
    dy = y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq <= 0.0:
        return hypot(px - x0, py - y0)
    t = ((px - x0) * dx + (py - y0) * dy) / length_sq
    t = min(1.0, max(0.0, t))
    nearest_x = x0 + t * dx
    nearest_y = y0 + t * dy
    return hypot(px - nearest_x, py - nearest_y)
