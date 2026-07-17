from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TerrainGuidanceError(ValueError):
    """Raised when a terrain guidance file is invalid."""


@dataclass(frozen=True, slots=True)
class TerrainGuidance:
    """Read-only geography context used by the legacy terrain generator."""

    width: int
    height: int
    seed: int
    elevation_style: str
    elevation_rows: tuple[tuple[float, ...], ...]
    moisture_rows: tuple[tuple[float, ...], ...]
    slope_rows: tuple[tuple[float, ...], ...]
    natural_level_rows: tuple[tuple[int, ...], ...] | None = None
    natural_slope_rows: tuple[tuple[int, ...], ...] | None = None
    initial_terrain_rows: tuple[str, ...] | None = None
    terrain_profile_count: int = 0

    STEEP_SLOPE = 0.085
    CLIFF_SLOPE = 0.18

    @classmethod
    def from_json_file(
        cls,
        path: Path,
        *,
        expected_width: int,
        expected_height: int,
        expected_seed: int,
    ) -> "TerrainGuidance":
        """Load and validate a geography guidance file.

        Args:
            path: Guidance JSON path.
            expected_width: Expected map width.
            expected_height: Expected map height.
            expected_seed: Expected resolved seed.

        Returns:
            Validated terrain guidance.

        Raises:
            TerrainGuidanceError: If the payload is malformed or incompatible.
        """
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise TerrainGuidanceError(f"Failed to read terrain guidance: {path}") from exc
        except json.JSONDecodeError as exc:
            raise TerrainGuidanceError(f"Invalid terrain guidance JSON: {path}") from exc
        if not isinstance(raw, dict):
            raise TerrainGuidanceError("Terrain guidance root must be an object")
        supported_schemas = {
            "terrain-guidance-v1",
            "terrain-guidance-v2",
            "terrain-guidance-v3",
        }
        if raw.get("schema_version") not in supported_schemas:
            raise TerrainGuidanceError("Unsupported terrain guidance schema")

        width = _required_int(raw, "width")
        height = _required_int(raw, "height")
        seed = _required_int(raw, "seed")
        scale = _required_int(raw, "scale")
        if scale <= 0:
            raise TerrainGuidanceError("Terrain guidance scale must be positive")
        if (width, height, seed) != (expected_width, expected_height, expected_seed):
            raise TerrainGuidanceError(
                "Terrain guidance does not match generation request: "
                f"expected={(expected_width, expected_height, expected_seed)!r}, "
                f"actual={(width, height, seed)!r}"
            )

        return cls(
            width=width,
            height=height,
            seed=seed,
            elevation_style=str(raw.get("elevation_style", "normal")),
            elevation_rows=_decode_rows(raw.get("elevation_rows"), width, height, scale, "elevation_rows"),
            moisture_rows=_decode_rows(raw.get("moisture_rows"), width, height, scale, "moisture_rows"),
            slope_rows=_decode_rows(raw.get("slope_rows"), width, height, scale, "slope_rows"),
            natural_level_rows=_decode_integer_rows_optional(
                raw.get("natural_level_rows"), width, height, "natural_level_rows"
            ),
            natural_slope_rows=_decode_integer_rows_optional(
                raw.get("natural_slope_rows"), width, height, "natural_slope_rows"
            ),
            initial_terrain_rows=_decode_initial_terrain_rows_optional(
                raw.get("initial_terrain_rows"), width, height
            ),
            terrain_profile_count=_terrain_profile_count(raw.get("terrain_profiles")),
        )

    def elevation_at(self, x: int, y: int) -> float:
        """Return normalized draft elevation at one tile."""
        return self.elevation_rows[y][x]

    def moisture_at(self, x: int, y: int) -> float:
        """Return normalized draft moisture at one tile."""
        return self.moisture_rows[y][x]

    def slope_at(self, x: int, y: int) -> float:
        """Return local draft slope magnitude at one tile."""
        return self.slope_rows[y][x]

    def natural_level_at(self, x: int, y: int) -> int | None:
        """Return final natural integer elevation when available."""
        if self.natural_level_rows is None:
            return None
        return self.natural_level_rows[y][x]

    def natural_slope_at(self, x: int, y: int) -> int | None:
        """Return final natural cardinal slope delta when available."""
        if self.natural_slope_rows is None:
            return None
        return self.natural_slope_rows[y][x]

    def initial_terrain_at(self, x: int, y: int) -> str | None:
        """Return the regional base terrain symbol when available."""
        if self.initial_terrain_rows is None:
            return None
        return self.initial_terrain_rows[y][x]


    def natural_delta_at(self, x: int, y: int) -> int:
        """Return final natural cardinal elevation delta at one tile."""
        slope = self.natural_slope_at(x, y)
        if slope is not None:
            return slope
        return 3 if self.slope_at(x, y) >= self.CLIFF_SLOPE else (2 if self.is_steep(x, y) else 0)

    def is_natural_barrier(self, x: int, y: int) -> bool:
        """Return whether natural geography should block ordinary terrain carving."""
        return self.natural_delta_at(x, y) > 2

    def is_comfortable_walk(self, x: int, y: int) -> bool:
        """Return whether one tile is naturally comfortable for open ground."""
        return self.natural_delta_at(x, y) <= 1

    def is_difficult_walk(self, x: int, y: int) -> bool:
        """Return whether one tile is a difficult but usable natural slope."""
        return self.natural_delta_at(x, y) == 2

    def wetland_score(self, x: int, y: int) -> float:
        """Return suitability score for puddles and wetland terrain."""
        moisture = self.moisture_at(x, y)
        elevation = self.elevation_at(x, y)
        slope_penalty = min(1.0, self.natural_delta_at(x, y) / 2.0)
        lowland = max(0.0, 1.0 - elevation / 0.58)
        return max(0.0, moisture * 0.62 + lowland * 0.38 - slope_penalty * 0.55)

    def forest_suitability(self, x: int, y: int) -> float:
        """Return natural suitability score for dense forest terrain."""
        if self.is_natural_barrier(x, y):
            return 0.0
        moisture = self.moisture_at(x, y)
        elevation = self.elevation_at(x, y)
        slope_factor = 1.0 if self.is_comfortable_walk(x, y) else 0.55
        elevation_factor = max(0.20, 1.0 - max(0.0, elevation - 0.68) * 1.8)
        return max(0.0, min(1.0, (0.35 + moisture * 0.65) * slope_factor * elevation_factor))

    def footprint_level_delta(self, x: int, y: int, radius: int) -> int:
        """Return integer elevation range inside a circular footprint."""
        if self.natural_level_rows is None:
            return 0 if self.footprint_score(x, y, radius) >= 0.55 else 3
        values: list[int] = []
        for sy in range(max(0, y - radius), min(self.height, y + radius + 1)):
            for sx in range(max(0, x - radius), min(self.width, x + radius + 1)):
                if (sx - x) ** 2 + (sy - y) ** 2 <= radius * radius:
                    values.append(self.natural_level_rows[sy][sx])
        return max(values) - min(values) if values else 0

    def footprint_score(self, x: int, y: int, radius: int) -> float:
        """Return a placement score for a circular terrain footprint.

        Args:
            x: Center tile x coordinate.
            y: Center tile y coordinate.
            radius: Approximate footprint radius.

        Returns:
            Higher score for flatter, non-extreme terrain.
        """
        radius = max(0, radius)
        step = max(1, radius // 3)
        maximum_slope = 0.0
        total_elevation = 0.0
        samples = 0
        for sy in range(max(0, y - radius), min(self.height, y + radius + 1), step):
            for sx in range(max(0, x - radius), min(self.width, x + radius + 1), step):
                if (sx - x) ** 2 + (sy - y) ** 2 > radius * radius:
                    continue
                maximum_slope = max(maximum_slope, self.slope_at(sx, sy))
                total_elevation += self.elevation_at(sx, sy)
                samples += 1
        if samples == 0:
            return 0.0
        average_elevation = total_elevation / samples
        flatness = max(0.0, 1.0 - maximum_slope / self.STEEP_SLOPE)
        moderate_elevation = max(0.0, 1.0 - abs(average_elevation - 0.50) * 1.15)
        return flatness * 0.86 + moderate_elevation * 0.14

    def is_steep(self, x: int, y: int) -> bool:
        """Return whether one tile is steep for terrain placement."""
        return self.slope_at(x, y) >= self.STEEP_SLOPE

    def road_path(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        *,
        step: int = 4,
    ) -> list[tuple[int, int]]:
        """Find a coarse geography-aware path between two tile points.

        Args:
            start: Start tile coordinates.
            end: End tile coordinates.
            step: Coarse routing cell size.

        Returns:
            Tile-space route waypoints, or an empty list when no route exists.
        """
        if start == end:
            return [start]
        step = max(2, step)
        coarse_width = math.ceil(self.width / step)
        coarse_height = math.ceil(self.height / step)
        start_node = (min(coarse_width - 1, start[0] // step), min(coarse_height - 1, start[1] // step))
        end_node = (min(coarse_width - 1, end[0] // step), min(coarse_height - 1, end[1] // step))

        route = self._a_star(start_node, end_node, step, coarse_width, coarse_height, self.CLIFF_SLOPE)
        if not route:
            route = self._a_star(start_node, end_node, step, coarse_width, coarse_height, 0.32)
        if not route:
            return []

        points = [start]
        for node in route[1:-1]:
            points.append(self._node_center(node, step))
        points.append(end)
        return points

    def _a_star(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        step: int,
        coarse_width: int,
        coarse_height: int,
        maximum_slope: float,
    ) -> list[tuple[int, int]]:
        frontier: list[tuple[float, int, tuple[int, int]]] = []
        counter = 0
        heapq.heappush(frontier, (0.0, counter, start))
        parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        costs: dict[tuple[int, int], float] = {start: 0.0}

        while frontier:
            _priority, _counter, current = heapq.heappop(frontier)
            if current == end:
                return _reconstruct_nodes(parents, end)

            cx, cy = current
            current_x, current_y = self._node_center(current, step)
            current_elevation = self.elevation_at(current_x, current_y)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                neighbor = (cx + dx, cy + dy)
                if not (0 <= neighbor[0] < coarse_width and 0 <= neighbor[1] < coarse_height):
                    continue
                nx, ny = self._node_center(neighbor, step)
                slope = self.slope_at(nx, ny)
                natural_delta = self.natural_delta_at(nx, ny)
                if slope > maximum_slope and neighbor not in {start, end}:
                    continue
                if (
                    self.elevation_style == "plateau"
                    and natural_delta > 2
                    and maximum_slope <= self.CLIFF_SLOPE
                    and neighbor not in {start, end}
                ):
                    continue
                elevation = self.elevation_at(nx, ny)
                distance = math.sqrt(2.0) if dx and dy else 1.0
                uphill = max(0.0, elevation - current_elevation)
                move_cost = distance * (
                    1.0
                    + slope * 42.0
                    + abs(elevation - current_elevation) * 15.0
                    + uphill * 7.0
                    + elevation * 0.25
                    + natural_delta * natural_delta * (18.0 if self.elevation_style == "plateau" else 8.0)
                )
                new_cost = costs[current] + move_cost
                if new_cost >= costs.get(neighbor, float("inf")):
                    continue
                costs[neighbor] = new_cost
                parents[neighbor] = current
                counter += 1
                heuristic = math.hypot(end[0] - neighbor[0], end[1] - neighbor[1])
                heapq.heappush(frontier, (new_cost + heuristic, counter, neighbor))
        return []

    def _node_center(self, node: tuple[int, int], step: int) -> tuple[int, int]:
        return (
            min(self.width - 1, node[0] * step + step // 2),
            min(self.height - 1, node[1] * step + step // 2),
        )


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise TerrainGuidanceError(f"Terrain guidance field {key!r} must be an integer")
    return value


def _decode_rows(
    value: object,
    width: int,
    height: int,
    scale: int,
    field_name: str,
) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, list) or len(value) != height:
        raise TerrainGuidanceError(f"Terrain guidance {field_name} height mismatch")
    output: list[tuple[float, ...]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != width:
            raise TerrainGuidanceError(f"Terrain guidance {field_name} width mismatch")
        decoded: list[float] = []
        for item in row:
            if not isinstance(item, int):
                raise TerrainGuidanceError(f"Terrain guidance {field_name} must contain integers")
            decoded.append(item / scale)
        output.append(tuple(decoded))
    return tuple(output)


def _decode_integer_rows_optional(
    value: object,
    width: int,
    height: int,
    field_name: str,
) -> tuple[tuple[int, ...], ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != height:
        raise TerrainGuidanceError(f"Terrain guidance {field_name} height mismatch")
    output: list[tuple[int, ...]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != width:
            raise TerrainGuidanceError(f"Terrain guidance {field_name} width mismatch")
        decoded: list[int] = []
        for item in row:
            if not isinstance(item, int):
                raise TerrainGuidanceError(f"Terrain guidance {field_name} must contain integers")
            decoded.append(item)
        output.append(tuple(decoded))
    return tuple(output)


def _reconstruct_nodes(
    parents: dict[tuple[int, int], tuple[int, int] | None],
    end: tuple[int, int],
) -> list[tuple[int, int]]:
    output: list[tuple[int, int]] = []
    current: tuple[int, int] | None = end
    while current is not None:
        output.append(current)
        current = parents[current]
    output.reverse()
    return output


def _decode_initial_terrain_rows_optional(
    raw: object,
    width: int,
    height: int,
) -> tuple[str, ...] | None:
    """Validate optional compact TREE/GRASS terrain rows."""
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != height:
        raise TerrainGuidanceError("Terrain guidance initial_terrain_rows height mismatch")
    rows: list[str] = []
    for row in raw:
        if not isinstance(row, str) or len(row) != width:
            raise TerrainGuidanceError("Terrain guidance initial_terrain_rows width mismatch")
        if set(row) - {"T", "+"}:
            raise TerrainGuidanceError(
                "Terrain guidance initial_terrain_rows contains invalid symbols"
            )
        rows.append(row)
    return tuple(rows)


def _terrain_profile_count(raw: object) -> int:
    """Return the number of valid regional terrain profile records."""
    if raw is None:
        return 0
    if not isinstance(raw, list):
        raise TerrainGuidanceError("Terrain guidance terrain_profiles must be a list")
    return len(raw)
