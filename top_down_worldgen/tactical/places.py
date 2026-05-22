from __future__ import annotations

from collections import Counter
from typing import Any

PLACES_SCHEMA_VERSION = "places-v1"
MIN_PLACES = 1
MAX_PLACES = 12
MIN_PLACE_DISTANCE_TILES = 6
PLACE_RADIUS_TILES = 6

PLACE_TYPES: tuple[dict[str, Any], ...] = (
    {
        "type": "abandoned_checkpoint",
        "name_ru": "Заброшенный блокпост",
        "role": "roadside_landmark",
        "anchor_type": "old_checkpoint",
        "preferred_types": ["rusted_barrel", "scrap_pile", "ammo_cache"],
        "tags": ["roadside", "checkpoint", "human_trace"],
    },
    {
        "type": "broken_radio_site",
        "name_ru": "Разбитая радиоточка",
        "role": "zone_landmark",
        "anchor_type": "broken_radio_mast",
        "preferred_types": ["scrap_pile", "medkit_cache", "ammo_cache"],
        "tags": ["signal", "expedition_trace", "landmark"],
    },
    {
        "type": "old_defensive_position",
        "name_ru": "Старая оборонительная позиция",
        "role": "defensive_site",
        "anchor_type": "trench",
        "preferred_types": ["stone_chunk", "fallen_log", "ammo_cache"],
        "tags": ["defense", "trench", "human_trace"],
    },
    {
        "type": "forest_obstruction",
        "name_ru": "Лесной завал",
        "role": "natural_micro_location",
        "anchor_type": "big_dead_tree",
        "preferred_types": ["fallen_log", "bush_thicket"],
        "tags": ["forest", "obstruction", "natural"],
    },
    {
        "type": "small_ruin_site",
        "name_ru": "Малая руинная площадка",
        "role": "ruin_micro_location",
        "anchor_type": "scrap_pile",
        "preferred_types": ["stone_chunk", "rusted_barrel", "medkit_cache"],
        "tags": ["ruin", "scrap", "human_trace"],
    },
)

PLACE_TYPE_NAMES: frozenset[str] = frozenset(item["type"] for item in PLACE_TYPES)
PLACE_TYPE_BY_NAME: dict[str, dict[str, Any]] = {
    str(item["type"]): item for item in PLACE_TYPES
}


def attach_places(tactical_data: dict[str, Any]) -> dict[str, Any]:
    """Attach micro-location places to tactical data.

    Args:
        tactical_data: Runtime tactical JSON object with runtime objects.

    Returns:
        Copy of tactical data with place sections.
    """
    enriched = dict(tactical_data)
    enriched.setdefault("place_schema", _place_schema())

    existing_places = enriched.get("places")
    if isinstance(existing_places, list) and existing_places:
        enriched["places_summary"] = summarize_places(existing_places)
        return enriched

    runtime_objects = _runtime_objects(enriched)
    places = PlaceAssembler(runtime_objects).assemble()
    enriched["places"] = places
    enriched["places_summary"] = summarize_places(places)
    return enriched


def summarize_places(places: Any) -> dict[str, Any]:
    """Build a compact places summary.

    Args:
        places: Places value.

    Returns:
        JSON-serializable place summary.
    """
    if not isinstance(places, list):
        return {"total": 0, "by_type": {}}
    counts = Counter(
        str(item.get("type"))
        for item in places
        if isinstance(item, dict) and item.get("type") is not None
    )
    return {
        "total": sum(counts.values()),
        "by_type": dict(sorted(counts.items())),
    }


class PlaceAssembler:
    """Builds small map scenes from already placed runtime objects."""

    def __init__(self, runtime_objects: list[dict[str, Any]]) -> None:
        """Initialize assembler.

        Args:
            runtime_objects: Runtime objects to group into places.
        """
        self._by_type = _objects_by_type(runtime_objects)
        self._used_object_ids: set[str] = set()
        self._used_centers: list[tuple[int, int]] = []

    def assemble(self) -> list[dict[str, Any]]:
        """Build places from available runtime objects.

        Returns:
            List of place descriptors.
        """
        places: list[dict[str, Any]] = []
        for spec in PLACE_TYPES:
            if len(places) >= MAX_PLACES:
                break
            place = self._build_place(spec, serial=len(places))
            if place is not None:
                places.append(place)
        return places

    def _build_place(
        self,
        spec: dict[str, Any],
        *,
        serial: int,
    ) -> dict[str, Any] | None:
        anchor = self._take_anchor(str(spec["anchor_type"]))
        if anchor is None:
            return None
        center = _object_center(anchor)
        if center is None or self._too_close_to_existing_place(center):
            return None

        object_ids = [str(anchor["id"])]
        for object_type in spec.get("preferred_types", []):
            candidate = self._take_nearest_unused_object(str(object_type), center)
            if candidate is None:
                continue
            object_ids.append(str(candidate["id"]))

        if len(object_ids) < 2:
            return None

        self._used_centers.append(center)
        return {
            "id": f"{spec['type']}_{serial:03d}",
            "type": spec["type"],
            "role": spec["role"],
            "center": {"x": center[0], "y": center[1]},
            "radius": PLACE_RADIUS_TILES,
            "object_ids": object_ids,
            "anchor_object_id": object_ids[0],
            "tags": list(spec.get("tags", [])),
        }

    def _take_anchor(self, object_type: str) -> dict[str, Any] | None:
        for item in self._by_type.get(object_type, []):
            item_id = item.get("id")
            if not isinstance(item_id, str) or item_id in self._used_object_ids:
                continue
            self._used_object_ids.add(item_id)
            return item
        return None

    def _take_nearest_unused_object(
        self,
        object_type: str,
        center: tuple[int, int],
    ) -> dict[str, Any] | None:
        candidates: list[tuple[int, dict[str, Any]]] = []
        for item in self._by_type.get(object_type, []):
            item_id = item.get("id")
            if not isinstance(item_id, str) or item_id in self._used_object_ids:
                continue
            point = _object_center(item)
            if point is None:
                continue
            candidates.append((_manhattan(center, point), item))
        if not candidates:
            return None
        _, selected = min(candidates, key=lambda pair: pair[0])
        self._used_object_ids.add(str(selected["id"]))
        return selected

    def _too_close_to_existing_place(self, center: tuple[int, int]) -> bool:
        return any(
            _manhattan(center, used_center) < MIN_PLACE_DISTANCE_TILES
            for used_center in self._used_centers
        )


def _place_schema() -> dict[str, Any]:
    return {
        "schema_version": PLACES_SCHEMA_VERSION,
        "types": [dict(item) for item in PLACE_TYPES],
        "min_places": MIN_PLACES,
        "max_places": MAX_PLACES,
        "min_place_distance_tiles": MIN_PLACE_DISTANCE_TILES,
    }


def _runtime_objects(tactical_data: dict[str, Any]) -> list[dict[str, Any]]:
    value = tactical_data.get("runtime_objects")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _objects_by_type(
    runtime_objects: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in runtime_objects:
        object_type = item.get("type")
        if isinstance(object_type, str):
            by_type.setdefault(object_type, []).append(item)
    return by_type


def _object_center(item: dict[str, Any]) -> tuple[int, int] | None:
    footprint = item.get("footprint")
    if isinstance(footprint, list) and footprint:
        points = [_point(point) for point in footprint]
        valid_points = [point for point in points if point is not None]
        if valid_points:
            x = round(sum(point[0] for point in valid_points) / len(valid_points))
            y = round(sum(point[1] for point in valid_points) / len(valid_points))
            return x, y
    point = _point(item.get("position"))
    if point is not None:
        return point
    try:
        return int(item["x"]), int(item["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])
