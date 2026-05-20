from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Any

RUNTIME_OBJECT_SCHEMA_VERSION = "runtime-objects-v5"
DEFAULT_ELEVATION_LEVEL = 0
MIN_ELEVATION_LEVEL = -1
MAX_ELEVATION_LEVEL = 10
MIN_OBJECT_HEIGHT = 0
MAX_OBJECT_HEIGHT = 10
MAX_RUNTIME_OBJECTS = 128
MIN_TRENCHES = 1
MAX_TRENCHES = 8
TRENCH_MIN_LENGTH_TILES = 3
TRENCH_MAX_LENGTH_TILES = 7
L_SHAPED_TRENCH_CHANCE = 0.35
TRENCH_ELEVATION_LEVEL = -1
MIN_AMMO_CACHES = 1
MAX_AMMO_CACHES = 8
MIN_MEDKIT_CACHES = 1
MAX_MEDKIT_CACHES = 6
INTEREST_POINT_TYPES: frozenset[str] = frozenset({"ammo_cache", "medkit_cache"})
MIN_OBJECT_DISTANCE_TILES = 3
PROTECTED_TILE_DISTANCE_TILES = 5

PASSABLE_OBJECT_TILES: frozenset[str] = frozenset({"+", ".", "R", "c"})
BLOCKED_OBJECT_TILES: frozenset[str] = frozenset({"T", "b", "w", "#", "S", "G"})
GENERATED_RUNTIME_OBJECT_TYPES: tuple[str, ...] = (
    "fallen_log",
    "stone_chunk",
    "bush_thicket",
    "scrap_pile",
    "rusted_barrel",
    "ammo_cache",
    "medkit_cache",
    "trench",
)

RUNTIME_OBJECT_TYPES: tuple[dict[str, Any], ...] = (
    {
        "type": "fallen_log",
        "name_ru": "Поваленное бревно",
        "role": "hard_cover",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "low",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["cover", "natural"],
    },
    {
        "type": "stone_chunk",
        "name_ru": "Каменная глыба",
        "role": "hard_cover",
        "default_height": 2,
        "default_elevation": 0,
        "cover_type": "full",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": True,
        "interactive": False,
        "tags": ["cover", "stone"],
    },
    {
        "type": "bush_thicket",
        "name_ru": "Густой кустарник",
        "role": "soft_cover",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "soft",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": True,
        "interactive": False,
        "tags": ["cover", "concealment", "vegetation"],
    },
    {
        "type": "rusted_barrel",
        "name_ru": "Ржавая бочка",
        "role": "risky_cover",
        "default_height": 2,
        "default_elevation": 0,
        "cover_type": "full",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": True,
        "tags": ["cover", "explosive_candidate", "metal"],
    },
    {
        "type": "scrap_pile",
        "name_ru": "Куча металлолома",
        "role": "partial_cover",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "low",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["cover", "scrap", "ruins"],
    },
    {
        "type": "ammo_cache",
        "name_ru": "Тайник с патронами",
        "role": "interest_point",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": True,
        "tags": ["loot", "ammo"],
    },
    {
        "type": "medkit_cache",
        "name_ru": "Аптечный тайник",
        "role": "interest_point",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": True,
        "tags": ["loot", "healing"],
    },
    {
        "type": "trench",
        "name_ru": "Окоп / траншея",
        "role": "defensive_position",
        "default_height": 0,
        "default_elevation": -1,
        "cover_type": "trench",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "cover", "below_floor"],
    },
)

COVER_TYPES: frozenset[str] = frozenset(
    {"none", "soft", "low", "full", "trench"},
)
RUNTIME_OBJECT_TYPE_NAMES: frozenset[str] = frozenset(
    item["type"] for item in RUNTIME_OBJECT_TYPES
)
RUNTIME_OBJECT_TYPE_BY_NAME: dict[str, dict[str, Any]] = {
    str(item["type"]): item for item in RUNTIME_OBJECT_TYPES
}


@dataclass(frozen=True, slots=True)
class RuntimeObjectQuota:
    """Runtime object target quota for one object type."""

    object_type: str
    base_count: int
    preferred_tiles: frozenset[str]


def attach_runtime_layers(
    tactical_data: dict[str, Any],
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    """Attach runtime object and elevation layers to tactical data.

    Args:
        tactical_data: Runtime tactical JSON object.
        seed: Optional deterministic seed for runtime object placement.

    Returns:
        Copy of tactical data with map-level sections.
    """
    enriched = dict(tactical_data)
    enriched.setdefault(
        "runtime_object_schema",
        {
            "schema_version": RUNTIME_OBJECT_SCHEMA_VERSION,
            "types": [dict(item) for item in RUNTIME_OBJECT_TYPES],
            "cover_types": sorted(COVER_TYPES),
            "height_range": [MIN_OBJECT_HEIGHT, MAX_OBJECT_HEIGHT],
            "elevation_range": [MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL],
            "generated_types": list(GENERATED_RUNTIME_OBJECT_TYPES),
            "max_runtime_objects": MAX_RUNTIME_OBJECTS,
        },
    )
    enriched.setdefault(
        "elevation",
        {
            "default": DEFAULT_ELEVATION_LEVEL,
            "cells": [],
        },
    )

    existing_objects = enriched.get("runtime_objects")
    if isinstance(existing_objects, list) and existing_objects:
        enriched["runtime_objects_summary"] = summarize_runtime_objects(existing_objects)
        return enriched

    if seed is None:
        enriched.setdefault("runtime_objects", [])
        enriched["runtime_objects_summary"] = summarize_runtime_objects(
            enriched["runtime_objects"],
        )
        return enriched

    objects = RuntimeObjectPlacer(seed).place(enriched)
    enriched["runtime_objects"] = objects
    _attach_trench_elevation(enriched, objects)
    enriched["runtime_objects_summary"] = summarize_runtime_objects(objects)
    return enriched


def summarize_runtime_objects(objects: Any) -> dict[str, Any]:
    """Build a compact runtime object summary.

    Args:
        objects: Runtime objects value.

    Returns:
        JSON-serializable summary.
    """
    if not isinstance(objects, list):
        return {"total": 0, "by_type": {}}
    counts = Counter(
        str(item.get("type"))
        for item in objects
        if isinstance(item, dict) and item.get("type") is not None
    )
    trench_shapes = Counter(
        str(item.get("shape", "line"))
        for item in objects
        if isinstance(item, dict) and item.get("type") == "trench"
    )
    summary: dict[str, Any] = {
        "total": sum(counts.values()),
        "by_type": dict(sorted(counts.items())),
    }
    if trench_shapes:
        summary["trench_shapes"] = dict(sorted(trench_shapes.items()))
    return summary


class RuntimeObjectPlacer:
    """Places deterministic gameplay objects on an existing tactical map."""

    def __init__(self, seed: int) -> None:
        """Initialize placer.

        Args:
            seed: Resolved uint64 map seed.
        """
        self._rng = random.Random(seed ^ 0x5EED_0B1E_C7)

    def place(self, tactical_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Place runtime objects on passable map cells.

        Args:
            tactical_data: Runtime tactical JSON object with embedded tile grid.

        Returns:
            Runtime object descriptors.
        """
        rows = _tile_grid(tactical_data)
        if not rows:
            return []

        width = len(rows[0])
        height = len(rows)
        protected = _protected_positions(rows)
        occupied: set[tuple[int, int]] = set(protected)
        candidates = _candidate_positions(rows, protected)
        if not candidates:
            return []

        scale = max(0.5, min(1.5, (width * height) / 15360.0))
        objects: list[dict[str, Any]] = []
        quotas = _placement_quotas()
        anchors = _anchors(tactical_data)

        for quota in quotas:
            target_count = max(1, round(quota.base_count * scale))
            placed = 0
            for _ in range(target_count):
                desired_shape = self._desired_shape(
                    object_type=quota.object_type,
                    placed=placed,
                    target_count=target_count,
                )
                placement = self._pick_position(
                    rows=rows,
                    candidates=candidates,
                    occupied=occupied,
                    preferred_tiles=quota.preferred_tiles,
                    anchors=anchors,
                    object_type=quota.object_type,
                    desired_shape=desired_shape,
                )
                if placement is None:
                    break
                footprint, orientation, shape = placement
                object_id = f"{quota.object_type}_{placed:03d}"
                objects.append(
                    _build_runtime_object(
                        object_id=object_id,
                        object_type=quota.object_type,
                        footprint=footprint,
                        orientation=orientation,
                        shape=shape,
                    ),
                )
                occupied.update(footprint)
                placed += 1
                if len(objects) >= MAX_RUNTIME_OBJECTS:
                    return objects
        return objects

    def _desired_shape(
        self,
        *,
        object_type: str,
        placed: int,
        target_count: int,
    ) -> str | None:
        if object_type != "trench":
            return None
        if placed == 0:
            _ = target_count
            return "l_shape"
        if self._rng.random() < L_SHAPED_TRENCH_CHANCE:
            return "l_shape"
        return "line"

    def _pick_position(
        self,
        *,
        rows: list[str],
        candidates: list[tuple[int, int]],
        occupied: set[tuple[int, int]],
        preferred_tiles: frozenset[str],
        anchors: list[tuple[int, int]],
        object_type: str,
        desired_shape: str | None,
    ) -> tuple[list[tuple[int, int]], str, str] | None:
        shuffled = list(candidates)
        self._rng.shuffle(shuffled)
        shuffled.sort(
            key=lambda point: _placement_score(
                point,
                rows=rows,
                preferred_tiles=preferred_tiles,
                anchors=anchors,
                rng=self._rng,
            ),
        )
        for point in shuffled:
            footprints = _footprints_for_point(
                rows,
                point,
                self._rng,
                object_type=object_type,
                desired_shape=desired_shape,
            )
            for footprint, orientation, shape in footprints:
                if _footprint_is_available(footprint, rows=rows, occupied=occupied):
                    return footprint, orientation, shape
        return None


def _placement_quotas() -> tuple[RuntimeObjectQuota, ...]:
    return (
        RuntimeObjectQuota("trench", 4, frozenset({"+", ".", "c"})),
        RuntimeObjectQuota("stone_chunk", 10, frozenset({"+", ".", "c"})),
        RuntimeObjectQuota("bush_thicket", 14, frozenset({"+"})),
        RuntimeObjectQuota("fallen_log", 8, frozenset({"+", "."})),
        RuntimeObjectQuota("scrap_pile", 7, frozenset({"R", "c", "."})),
        RuntimeObjectQuota("rusted_barrel", 5, frozenset({"R", ".", "c"})),
        RuntimeObjectQuota("ammo_cache", 3, frozenset({"R", "c", "."})),
        RuntimeObjectQuota("medkit_cache", 2, frozenset({"R", "c", ".", "+"})),
    )


def _tile_grid(tactical_data: dict[str, Any]) -> list[str]:
    map_data = tactical_data.get("map", {})
    if not isinstance(map_data, dict):
        return []
    tile_grid = map_data.get("tile_grid")
    if not isinstance(tile_grid, list):
        return []
    rows = [row for row in tile_grid if isinstance(row, str)]
    if not rows:
        return []
    width = len(rows[0])
    if width <= 0 or any(len(row) != width for row in rows):
        return []
    return rows


def _protected_positions(rows: list[str]) -> set[tuple[int, int]]:
    protected: set[tuple[int, int]] = set()
    start_goal: list[tuple[int, int]] = []
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            if tile in {"S", "G"}:
                start_goal.append((x, y))
    for point in start_goal:
        protected.update(_points_within_distance(point, PROTECTED_TILE_DISTANCE_TILES))
    return protected


def _candidate_positions(
    rows: list[str],
    protected: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            point = (x, y)
            if tile in PASSABLE_OBJECT_TILES and point not in protected:
                candidates.append(point)
    return candidates


def _anchors(tactical_data: dict[str, Any]) -> list[tuple[int, int]]:
    anchors: list[tuple[int, int]] = []
    for zone in _dict_items(tactical_data.get("combat_zones")):
        point = _point(zone.get("center"))
        if point is not None:
            anchors.append(point)
    for choke in _dict_items(tactical_data.get("choke_points")):
        point = _point(choke.get("position"))
        if point is not None:
            anchors.append(point)
    return anchors


def _placement_score(
    point: tuple[int, int],
    *,
    rows: list[str],
    preferred_tiles: frozenset[str],
    anchors: list[tuple[int, int]],
    rng: random.Random,
) -> tuple[int, int, float]:
    x, y = point
    tile_penalty = 0 if rows[y][x] in preferred_tiles else 3
    anchor_distance = min(
        (_manhattan(point, anchor) for anchor in anchors),
        default=0,
    )
    return tile_penalty, anchor_distance, rng.random()


def _footprints_for_point(
    rows: list[str],
    point: tuple[int, int],
    rng: random.Random,
    *,
    object_type: str,
    desired_shape: str | None,
) -> list[tuple[list[tuple[int, int]], str, str]]:
    if object_type == "trench":
        return _trench_footprints_for_point(rows, point, rng, desired_shape)
    # Fallen-log-shaped footprints are deliberately avoided here because this
    # patch keeps non-trench runtime objects as one-cell descriptors.
    _ = rows
    _ = rng
    _ = desired_shape
    return [([point], "point", "point")]


def _trench_footprints_for_point(
    rows: list[str],
    point: tuple[int, int],
    rng: random.Random,
    desired_shape: str | None,
) -> list[tuple[list[tuple[int, int]], str, str]]:
    primary_shape = desired_shape or "line"
    if primary_shape == "l_shape":
        line = _line_trench_footprint_for_point(rows, point, rng)
        return [_l_shaped_trench_footprint_for_point(point, rng), line]
    return [_line_trench_footprint_for_point(rows, point, rng)]


def _line_trench_footprint_for_point(
    rows: list[str],
    point: tuple[int, int],
    rng: random.Random,
) -> tuple[list[tuple[int, int]], str, str]:
    orientation = rng.choice(["horizontal", "vertical"])
    length = rng.randint(TRENCH_MIN_LENGTH_TILES, TRENCH_MAX_LENGTH_TILES)
    if orientation == "horizontal":
        max_length = min(length, len(rows[0]))
        start_x = point[0] - max_length // 2
        y = point[1]
        footprint = [(start_x + offset, y) for offset in range(max_length)]
    else:
        max_length = min(length, len(rows))
        x = point[0]
        start_y = point[1] - max_length // 2
        footprint = [(x, start_y + offset) for offset in range(max_length)]
    return footprint, orientation, "line"


def _l_shaped_trench_footprint_for_point(
    point: tuple[int, int],
    rng: random.Random,
) -> tuple[list[tuple[int, int]], str, str]:
    horizontal_dir = rng.choice([-1, 1])
    vertical_dir = rng.choice([-1, 1])
    horizontal_length = rng.randint(2, 4)
    vertical_length = rng.randint(2, 4)
    x, y = point
    points = [(x + horizontal_dir * offset, y) for offset in range(horizontal_length)]
    points.extend((x, y + vertical_dir * offset) for offset in range(1, vertical_length))
    orientation = (
        f"l_shape_{'east' if horizontal_dir > 0 else 'west'}_"
        f"{'south' if vertical_dir > 0 else 'north'}"
    )
    return points, orientation, "l_shape"


def _footprint_is_available(
    footprint: list[tuple[int, int]],
    *,
    rows: list[str],
    occupied: set[tuple[int, int]],
) -> bool:
    if not footprint:
        return False
    for point in footprint:
        x, y = point
        if y < 0 or y >= len(rows) or x < 0 or x >= len(rows[y]):
            return False
        if point in occupied:
            return False
        if rows[y][x] not in PASSABLE_OBJECT_TILES:
            return False
        if _is_too_close_to_occupied(point, occupied):
            return False
    return True


def _is_too_close_to_occupied(
    point: tuple[int, int],
    occupied: set[tuple[int, int]],
) -> bool:
    for occupied_point in occupied:
        if _manhattan(point, occupied_point) < MIN_OBJECT_DISTANCE_TILES:
            return True
    return False


def _build_runtime_object(
    *,
    object_id: str,
    object_type: str,
    footprint: list[tuple[int, int]],
    orientation: str,
    shape: str,
) -> dict[str, Any]:
    spec = RUNTIME_OBJECT_TYPE_BY_NAME[object_type]
    x, y = footprint[0]
    item: dict[str, Any] = {
        "id": object_id,
        "type": object_type,
        "role": spec["role"],
        "x": x,
        "y": y,
        "position": [x, y],
        "elevation": spec["default_elevation"],
        "height": spec["default_height"],
        "cover_type": spec["cover_type"],
        "blocks_movement": spec["blocks_movement"],
        "blocks_projectiles": spec["blocks_projectiles"],
        "blocks_vision": spec["blocks_vision"],
        "interactive": spec["interactive"],
        "orientation": orientation,
        "shape": shape,
        "tags": list(spec["tags"]),
    }
    if len(footprint) > 1:
        item["footprint"] = [[point_x, point_y] for point_x, point_y in footprint]
    return item


def _attach_trench_elevation(
    tactical_data: dict[str, Any],
    objects: list[dict[str, Any]],
) -> None:
    elevation = tactical_data.setdefault(
        "elevation",
        {"default": DEFAULT_ELEVATION_LEVEL, "cells": []},
    )
    if not isinstance(elevation, dict):
        elevation = {"default": DEFAULT_ELEVATION_LEVEL, "cells": []}
        tactical_data["elevation"] = elevation
    cells = elevation.setdefault("cells", [])
    if not isinstance(cells, list):
        cells = []
        elevation["cells"] = cells
    existing: set[tuple[int, int]] = set()
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        try:
            existing.add((int(cell.get("x")), int(cell.get("y"))))
        except (TypeError, ValueError):
            continue
    for item in objects:
        if item.get("type") != "trench":
            continue
        for x, y in _object_footprint_points(item):
            if (x, y) in existing:
                continue
            cells.append({"x": x, "y": y, "level": TRENCH_ELEVATION_LEVEL})
            existing.add((x, y))


def _object_footprint_points(item: dict[str, Any]) -> list[tuple[int, int]]:
    footprint = item.get("footprint")
    if isinstance(footprint, list):
        points: list[tuple[int, int]] = []
        for point in footprint:
            if isinstance(point, list) and len(point) == 2:
                try:
                    points.append((int(point[0]), int(point[1])))
                except (TypeError, ValueError):
                    continue
        if points:
            return points
    point = _point(item.get("position"))
    if point is not None:
        return [point]
    try:
        return [(int(item["x"]), int(item["y"]))]
    except (KeyError, TypeError, ValueError):
        return []


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def _points_within_distance(
    center: tuple[int, int],
    distance: int,
) -> set[tuple[int, int]]:
    cx, cy = center
    points: set[tuple[int, int]] = set()
    for dy in range(-distance, distance + 1):
        remaining = distance - abs(dy)
        for dx in range(-remaining, remaining + 1):
            points.add((cx + dx, cy + dy))
    return points


def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])
