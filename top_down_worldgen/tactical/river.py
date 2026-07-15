from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from random import Random
from typing import Any

from PIL import Image

WATER_SYMBOL = "w"
_NEIGHBORS_8 = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),           (1, 0),
    (-1, 1),  (0, 1),  (1, 1),
)
_NEIGHBORS_4 = ((0, -1), (-1, 0), (1, 0), (0, 1))


@dataclass(frozen=True, slots=True)
class RiverConfig:
    """Configuration for the optional post-elevation river generator."""

    enabled: bool = False
    channel_width_min: int = 3
    channel_width_max: int = 9
    allow_basin_flooding: bool = True
    max_flood_area_ratio: float = 0.08
    max_flood_distance: int = 24
    require_map_exit: bool = True

    @classmethod
    def from_raw(cls, value: Any) -> "RiverConfig":
        """Build a sanitized river configuration.

        Args:
            value: Raw JSON-compatible config value.

        Returns:
            Sanitized river configuration.
        """
        if not isinstance(value, dict):
            return cls()

        minimum = _clamp_int(value.get("channel_width_min", 3), 1, 31, 3)
        maximum = _clamp_int(value.get("channel_width_max", 9), minimum, 63, 9)
        return cls(
            enabled=bool(value.get("enabled", False)),
            channel_width_min=minimum,
            channel_width_max=maximum,
            allow_basin_flooding=bool(value.get("allow_basin_flooding", True)),
            max_flood_area_ratio=_clamp_float(
                value.get("max_flood_area_ratio", 0.08), 0.0, 0.5, 0.08,
            ),
            max_flood_distance=_clamp_int(
                value.get("max_flood_distance", 24), 1, 256, 24,
            ),
            require_map_exit=bool(value.get("require_map_exit", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "enabled": self.enabled,
            "channel_width_min": self.channel_width_min,
            "channel_width_max": self.channel_width_max,
            "allow_basin_flooding": self.allow_basin_flooding,
            "max_flood_area_ratio": self.max_flood_area_ratio,
            "max_flood_distance": self.max_flood_distance,
            "require_map_exit": self.require_map_exit,
        }


@dataclass(frozen=True, slots=True)
class GridPoint:
    """Integer map coordinate."""

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class RiverGenerationResult:
    """Result returned by the isolated river generator."""

    terrain_rows: list[str]
    centerline: tuple[GridPoint, ...]
    river_mask: list[list[bool]]
    channel_mask: list[list[bool]]
    flooded_mask: list[list[bool]]
    water_depth_grid: list[list[int]]
    report: dict[str, Any]


class RiverGenerator:
    """Generate one bounded river over an already completed elevation map."""

    def generate(
        self,
        *,
        rows: list[str],
        elevation_grid: list[list[int]],
        seed: int,
        config: RiverConfig,
    ) -> RiverGenerationResult:
        """Generate a deterministic river and optional local basin flooding.

        Args:
            rows: Final ASCII terrain before river application.
            elevation_grid: Final integer elevation grid.
            seed: Resolved world seed.
            config: River generation configuration.

        Returns:
            River generation result without mutating input values.

        Raises:
            ValueError: If terrain and elevation dimensions do not match.
        """
        width, height = _validate_inputs(rows, elevation_grid)
        if not config.enabled or width == 0 or height == 0:
            return _empty_result(rows, width, height, config, seed)

        rng = Random(seed ^ 0x52495645525F5631)
        source, target = self._select_endpoints(elevation_grid, rng)
        centerline = self._find_flow_path(
            elevation_grid=elevation_grid,
            source=source,
            target=target,
            seed=seed,
        )
        channel_mask = self._build_channel_mask(
            width=width,
            height=height,
            centerline=centerline,
            config=config,
            rng=rng,
        )
        flooded_mask = self._build_flooded_mask(
            elevation_grid=elevation_grid,
            centerline=centerline,
            channel_mask=channel_mask,
            config=config,
        )
        river_mask = [
            [channel_mask[y][x] or flooded_mask[y][x] for x in range(width)]
            for y in range(height)
        ]
        terrain_rows = _apply_water(rows, river_mask)
        water_depth_grid = _water_depths(elevation_grid, river_mask, centerline)
        river_tiles = sum(sum(row) for row in river_mask)
        channel_tiles = sum(sum(row) for row in channel_mask)
        flooded_tiles = sum(sum(row) for row in flooded_mask)
        report = {
            "schema_version": "river-generation-report-v1",
            "generator": "post_elevation_bounded_river_v1",
            "seed": seed,
            "config": config.to_dict(),
            "source": {"x": source.x, "y": source.y, "level": elevation_grid[source.y][source.x]},
            "target": {"x": target.x, "y": target.y, "level": elevation_grid[target.y][target.x]},
            "summary": {
                "centerline_tiles": len(centerline),
                "channel_tiles": channel_tiles,
                "flooded_tiles": flooded_tiles,
                "river_tiles": river_tiles,
                "river_area_ratio": river_tiles / float(width * height),
                "touches_map_edge": any(
                    point.x in {0, width - 1} or point.y in {0, height - 1}
                    for point in centerline
                ),
            },
        }
        return RiverGenerationResult(
            terrain_rows=terrain_rows,
            centerline=tuple(centerline),
            river_mask=river_mask,
            channel_mask=channel_mask,
            flooded_mask=flooded_mask,
            water_depth_grid=water_depth_grid,
            report=report,
        )

    @staticmethod
    def _select_endpoints(
        elevation_grid: list[list[int]],
        rng: Random,
    ) -> tuple[GridPoint, GridPoint]:
        height = len(elevation_grid)
        width = len(elevation_grid[0])
        horizontal = rng.random() < 0.5
        margin = max(2, min(width, height) // 12)

        if horizontal:
            source_candidates = [GridPoint(0, y) for y in range(margin, height - margin)]
            target_candidates = [GridPoint(width - 1, y) for y in range(margin, height - margin)]
        else:
            source_candidates = [GridPoint(x, 0) for x in range(margin, width - margin)]
            target_candidates = [GridPoint(x, height - 1) for x in range(margin, width - margin)]

        source = max(
            source_candidates,
            key=lambda point: (elevation_grid[point.y][point.x], rng.random()),
        )
        target = min(
            target_candidates,
            key=lambda point: (elevation_grid[point.y][point.x], rng.random()),
        )
        if rng.random() < 0.5:
            source, target = target, source
        return source, target

    @staticmethod
    def _find_flow_path(
        *,
        elevation_grid: list[list[int]],
        source: GridPoint,
        target: GridPoint,
        seed: int,
    ) -> list[GridPoint]:
        height = len(elevation_grid)
        width = len(elevation_grid[0])
        queue: list[tuple[float, int, int]] = [(0.0, source.x, source.y)]
        costs = {(source.x, source.y): 0.0}
        previous: dict[tuple[int, int], tuple[int, int]] = {}

        while queue:
            cost, x, y = heapq.heappop(queue)
            if cost != costs.get((x, y)):
                continue
            if (x, y) == (target.x, target.y):
                break

            current_level = elevation_grid[y][x]
            for dx, dy in _NEIGHBORS_8:
                nx = x + dx
                ny = y + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                next_level = elevation_grid[ny][nx]
                delta = next_level - current_level
                uphill_penalty = max(0, delta) ** 2 * 12.0
                downhill_bonus = min(3.0, max(0, -delta) * 0.65)
                diagonal = 1.41421356237 if dx and dy else 1.0
                deterministic_noise = _cell_noise(nx, ny, seed) * 0.9
                heuristic_bias = hypot(target.x - nx, target.y - ny) * 0.002
                step_cost = max(
                    0.05,
                    diagonal + uphill_penalty - downhill_bonus + deterministic_noise + heuristic_bias,
                )
                new_cost = cost + step_cost
                if new_cost >= costs.get((nx, ny), float("inf")):
                    continue
                costs[(nx, ny)] = new_cost
                previous[(nx, ny)] = (x, y)
                heapq.heappush(queue, (new_cost, nx, ny))

        target_key = (target.x, target.y)
        if target_key not in costs:
            return [source, target]
        path = [target_key]
        while path[-1] != (source.x, source.y):
            path.append(previous[path[-1]])
        path.reverse()
        return [GridPoint(x, y) for x, y in path]

    @staticmethod
    def _build_channel_mask(
        *,
        width: int,
        height: int,
        centerline: list[GridPoint],
        config: RiverConfig,
        rng: Random,
    ) -> list[list[bool]]:
        mask = [[False for _ in range(width)] for _ in range(height)]
        current_width = rng.randint(config.channel_width_min, config.channel_width_max)
        for index, point in enumerate(centerline):
            if index % max(5, current_width * 2) == 0:
                current_width += rng.choice((-1, 0, 0, 1))
                current_width = max(
                    config.channel_width_min,
                    min(config.channel_width_max, current_width),
                )
            radius = max(0.5, current_width / 2.0)
            min_x = max(0, int(point.x - radius - 1))
            max_x = min(width - 1, int(point.x + radius + 1))
            min_y = max(0, int(point.y - radius - 1))
            max_y = min(height - 1, int(point.y + radius + 1))
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    if hypot(x - point.x, y - point.y) <= radius:
                        mask[y][x] = True
        return mask

    @staticmethod
    def _build_flooded_mask(
        *,
        elevation_grid: list[list[int]],
        centerline: list[GridPoint],
        channel_mask: list[list[bool]],
        config: RiverConfig,
    ) -> list[list[bool]]:
        height = len(elevation_grid)
        width = len(elevation_grid[0])
        flooded = [[False for _ in range(width)] for _ in range(height)]
        if not config.allow_basin_flooding:
            return flooded

        max_area = max(1, int(width * height * config.max_flood_area_ratio))
        visited: set[tuple[int, int]] = set()
        for point in centerline:
            water_level = elevation_grid[point.y][point.x]
            for dx, dy in _NEIGHBORS_4:
                start = (point.x + dx, point.y + dy)
                if start in visited:
                    continue
                sx, sy = start
                if not (0 <= sx < width and 0 <= sy < height):
                    continue
                if channel_mask[sy][sx] or elevation_grid[sy][sx] > water_level:
                    continue
                basin = _collect_basin(
                    start=start,
                    elevation_grid=elevation_grid,
                    channel_mask=channel_mask,
                    water_level=water_level,
                    origin=point,
                    max_distance=config.max_flood_distance,
                    hard_limit=max_area + 1,
                )
                visited.update(basin)
                if len(basin) > max_area:
                    continue
                for x, y in basin:
                    flooded[y][x] = True
        return flooded


def elevation_grid_from_tactical_data(
    tactical_data: dict[str, Any],
    *,
    width: int,
    height: int,
) -> list[list[int]]:
    """Reconstruct the full elevation grid from sparse tactical data.

    Args:
        tactical_data: Runtime tactical map with an elevation section.
        width: Expected grid width.
        height: Expected grid height.

    Returns:
        Full integer elevation grid.
    """
    elevation = tactical_data.get("elevation", {})
    default = int(elevation.get("default", 0)) if isinstance(elevation, dict) else 0
    grid = [[default for _ in range(width)] for _ in range(height)]
    cells = elevation.get("cells", []) if isinstance(elevation, dict) else []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        try:
            x = int(cell["x"])
            y = int(cell["y"])
            level = int(cell["level"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = level
    return grid



def mark_flooded_runtime_objects(
    tactical_data: dict[str, Any],
    *,
    river_mask: list[list[bool]],
    water_depth_grid: list[list[int]],
) -> dict[str, Any]:
    """Mark runtime objects touched by generated water as flooded.

    Args:
        tactical_data: Runtime tactical map.
        river_mask: Full river water mask.
        water_depth_grid: Estimated water depth for each map tile.

    Returns:
        Copy of tactical data with flooded object metadata.
    """
    enriched = dict(tactical_data)
    objects = tactical_data.get("runtime_objects")
    if not isinstance(objects, list):
        return enriched

    updated: list[Any] = []
    for item in objects:
        if not isinstance(item, dict):
            updated.append(item)
            continue
        points = _object_points(item)
        flooded_points = [
            (x, y)
            for x, y in points
            if 0 <= y < len(river_mask)
            and 0 <= x < len(river_mask[y])
            and river_mask[y][x]
        ]
        if not flooded_points:
            updated.append(dict(item))
            continue
        copy = dict(item)
        copy["flooded"] = True
        copy["water_depth"] = max(water_depth_grid[y][x] for x, y in flooded_points)
        updated.append(copy)
    enriched["runtime_objects"] = updated
    return enriched

def write_river_preview(result: RiverGenerationResult, path: Path, *, scale: int = 4) -> None:
    """Write a compact diagnostic PNG for a river result.

    Args:
        result: Generated river result.
        path: Destination PNG path.
        scale: Integer pixel scale per tile.
    """
    height = len(result.river_mask)
    width = len(result.river_mask[0]) if height else 0
    if width == 0 or height == 0:
        return
    image = Image.new("RGB", (width, height), (235, 232, 214))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            if result.flooded_mask[y][x]:
                pixels[x, y] = (64, 132, 171)
            elif result.channel_mask[y][x]:
                pixels[x, y] = (30, 91, 145)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((width * scale, height * scale), Image.Resampling.NEAREST).save(path)



def _object_points(item: dict[str, Any]) -> list[tuple[int, int]]:
    footprint = item.get("footprint")
    if isinstance(footprint, list):
        points: list[tuple[int, int]] = []
        for point in footprint:
            if not isinstance(point, dict):
                continue
            try:
                points.append((int(point["x"]), int(point["y"])))
            except (KeyError, TypeError, ValueError):
                continue
        if points:
            return points
    try:
        return [(int(item["x"]), int(item["y"]))]
    except (KeyError, TypeError, ValueError):
        return []

def _collect_basin(
    *,
    start: tuple[int, int],
    elevation_grid: list[list[int]],
    channel_mask: list[list[bool]],
    water_level: int,
    origin: GridPoint,
    max_distance: int,
    hard_limit: int,
) -> set[tuple[int, int]]:
    height = len(elevation_grid)
    width = len(elevation_grid[0])
    queue = deque([start])
    basin: set[tuple[int, int]] = set()
    while queue and len(basin) < hard_limit:
        x, y = queue.popleft()
        if (x, y) in basin or channel_mask[y][x]:
            continue
        if elevation_grid[y][x] > water_level:
            continue
        if hypot(x - origin.x, y - origin.y) > max_distance:
            continue
        basin.add((x, y))
        for dx, dy in _NEIGHBORS_4:
            nx = x + dx
            ny = y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in basin:
                queue.append((nx, ny))
    return basin


def _apply_water(rows: list[str], river_mask: list[list[bool]]) -> list[str]:
    output: list[str] = []
    for y, row in enumerate(rows):
        cells = list(row)
        for x, is_water in enumerate(river_mask[y]):
            if is_water:
                cells[x] = WATER_SYMBOL
        output.append("".join(cells))
    return output


def _water_depths(
    elevation_grid: list[list[int]],
    river_mask: list[list[bool]],
    centerline: list[GridPoint],
) -> list[list[int]]:
    height = len(elevation_grid)
    width = len(elevation_grid[0])
    levels = [elevation_grid[point.y][point.x] for point in centerline]
    reference_level = max(levels) if levels else 0
    return [
        [max(0, reference_level - elevation_grid[y][x] + 1) if river_mask[y][x] else 0 for x in range(width)]
        for y in range(height)
    ]


def _empty_result(
    rows: list[str],
    width: int,
    height: int,
    config: RiverConfig,
    seed: int,
) -> RiverGenerationResult:
    empty_mask = [[False for _ in range(width)] for _ in range(height)]
    return RiverGenerationResult(
        terrain_rows=list(rows),
        centerline=(),
        river_mask=[row[:] for row in empty_mask],
        channel_mask=[row[:] for row in empty_mask],
        flooded_mask=[row[:] for row in empty_mask],
        water_depth_grid=[[0 for _ in range(width)] for _ in range(height)],
        report={
            "schema_version": "river-generation-report-v1",
            "generator": "post_elevation_bounded_river_v1",
            "seed": seed,
            "config": config.to_dict(),
            "summary": {
                "centerline_tiles": 0,
                "channel_tiles": 0,
                "flooded_tiles": 0,
                "river_tiles": 0,
                "river_area_ratio": 0.0,
                "touches_map_edge": False,
            },
        },
    )


def _validate_inputs(rows: list[str], elevation_grid: list[list[int]]) -> tuple[int, int]:
    if not rows:
        return 0, 0
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("terrain rows must be rectangular")
    if len(elevation_grid) != len(rows) or any(len(row) != width for row in elevation_grid):
        raise ValueError("elevation grid dimensions must match terrain rows")
    return width, len(rows)


def _cell_noise(x: int, y: int, seed: int) -> float:
    value = (x * 0x1F123BB5) ^ (y * 0x5F356495) ^ seed
    value = (value ^ (value >> 16)) * 0x45D9F3B
    value ^= value >> 16
    return (value & 0xFFFF) / 65535.0


def _clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _clamp_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))
