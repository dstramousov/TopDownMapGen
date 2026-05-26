from __future__ import annotations

from collections import Counter
from typing import Any

PLACES_SCHEMA_VERSION = "places-v2"
MIN_PLACES = 1
MAX_PLACES = 12
MIN_PLACE_DISTANCE_TILES = 6
PLACE_RADIUS_TILES = 6
MAX_PLACE_OBJECT_DISTANCE_TILES = 14
MAX_CONNECTED_PLACES = 3

PLACE_TYPES: tuple[dict[str, Any], ...] = (
    {
        "type": "abandoned_checkpoint",
        "name_ru": "Заброшенный блокпост",
        "role": "roadside_landmark",
        "anchor_type": "old_checkpoint",
        "preferred_types": ["rusted_barrel", "scrap_pile", "ammo_cache"],
        "tags": ["roadside", "checkpoint", "human_trace"],
        "danger_level": 0.45,
        "loot_level": 0.35,
        "story_role": "old_control_point",
        "encounter_type": "roadside_encounter",
        "biome_tags": ["ruins", "abandoned"],
    },
    {
        "type": "broken_radio_site",
        "name_ru": "Разбитая радиоточка",
        "role": "zone_landmark",
        "anchor_type": "broken_radio_mast",
        "preferred_types": ["scrap_pile", "medkit_cache", "ammo_cache"],
        "tags": ["signal", "expedition_trace", "landmark"],
        "danger_level": 0.35,
        "loot_level": 0.45,
        "story_role": "lost_expedition_trace",
        "encounter_type": "landmark_encounter",
        "biome_tags": ["forest", "abandoned"],
    },
    {
        "type": "old_defensive_position",
        "name_ru": "Старая оборонительная позиция",
        "role": "defensive_site",
        "anchor_type": "trench",
        "preferred_types": ["stone_chunk", "fallen_log", "ammo_cache"],
        "tags": ["defense", "trench", "human_trace"],
        "danger_level": 0.65,
        "loot_level": 0.4,
        "story_role": "old_battle_position",
        "encounter_type": "defensive_encounter",
        "biome_tags": ["open_field", "ruins"],
    },
    {
        "type": "bunker_site",
        "name_ru": "Заглублённая бункерная позиция",
        "role": "defensive_site",
        "anchor_type": "buried_bunker_2x3",
        "preferred_types": ["buried_bunker_2x2", "ammo_cache", "rusted_barrel"],
        "min_object_refs": 1,
        "tags": ["bunker", "defense", "below_floor", "human_trace"],
        "danger_level": 0.75,
        "loot_level": 0.45,
        "story_role": "buried_defense_node",
        "encounter_type": "bunker_encounter",
        "biome_tags": ["ruins", "abandoned"],
    },
    {
        "type": "forest_obstruction",
        "name_ru": "Лесной завал",
        "role": "natural_micro_location",
        "anchor_type": "big_dead_tree",
        "preferred_types": ["fallen_log", "bush_thicket"],
        "tags": ["forest", "obstruction", "natural"],
        "danger_level": 0.3,
        "loot_level": 0.15,
        "story_role": "natural_blockage",
        "encounter_type": "traversal_obstacle",
        "biome_tags": ["forest"],
    },
    {
        "type": "small_ruin_site",
        "name_ru": "Малая руинная площадка",
        "role": "ruin_micro_location",
        "anchor_type": "scrap_pile",
        "preferred_types": ["stone_chunk", "rusted_barrel", "medkit_cache"],
        "tags": ["ruin", "scrap", "human_trace"],
        "danger_level": 0.45,
        "loot_level": 0.35,
        "story_role": "minor_ruins",
        "encounter_type": "ruin_encounter",
        "biome_tags": ["ruins", "abandoned"],
    },
)

PLACE_TYPE_NAMES: frozenset[str] = frozenset(item["type"] for item in PLACE_TYPES)
PLACE_TYPE_BY_NAME: dict[str, dict[str, Any]] = {
    str(item["type"]): item for item in PLACE_TYPES
}


def attach_places(tactical_data: dict[str, Any]) -> dict[str, Any]:
    """Attach semantic micro-location places to tactical data.

    Args:
        tactical_data: Runtime tactical JSON object with runtime objects.

    Returns:
        Copy of tactical data with place sections.
    """
    enriched = dict(tactical_data)
    enriched.setdefault("place_schema", _place_schema())

    existing_places = enriched.get("places")
    if isinstance(existing_places, list) and existing_places:
        enriched["places"] = _attach_place_connections(existing_places)
        enriched["places_summary"] = summarize_places(enriched["places"])
        return enriched

    runtime_objects = _runtime_objects(enriched)
    places = PlaceAssembler(runtime_objects).assemble()
    enriched["places"] = _attach_place_connections(places)
    enriched["places_summary"] = summarize_places(enriched["places"])
    return enriched


def summarize_places(places: Any) -> dict[str, Any]:
    """Build a compact places summary.

    Args:
        places: Places value.

    Returns:
        JSON-serializable place summary.
    """
    if not isinstance(places, list):
        return {"total": 0, "by_type": {}, "by_encounter_type": {}}
    type_counts = Counter(
        str(item.get("type"))
        for item in places
        if isinstance(item, dict) and item.get("type") is not None
    )
    encounter_counts = Counter(
        str(item.get("encounter_type"))
        for item in places
        if isinstance(item, dict) and item.get("encounter_type") is not None
    )
    return {
        "total": sum(type_counts.values()),
        "by_type": dict(sorted(type_counts.items())),
        "by_encounter_type": dict(sorted(encounter_counts.items())),
    }


class PlaceAssembler:
    """Builds semantic map scenes from already placed runtime objects."""

    def __init__(self, runtime_objects: list[dict[str, Any]]) -> None:
        """Initialize assembler.

        Args:
            runtime_objects: Runtime objects to group into places.
        """
        self._by_type = _objects_by_type(runtime_objects)
        self._objects_by_id = _objects_by_id(runtime_objects)
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

        min_object_refs = int(spec.get("min_object_refs", 2))
        if len(object_ids) < min_object_refs:
            return None

        objects = [self._objects_by_id[item_id] for item_id in object_ids]
        bounds = _bounds_for_objects(objects, fallback_center=center, radius=PLACE_RADIUS_TILES)
        entrances = _entrances_for_bounds(bounds)
        self._used_centers.append(center)
        tags = sorted(set(_string_list(spec.get("tags"))))
        biome_tags = sorted(set(_string_list(spec.get("biome_tags"))))
        return {
            "schema_version": PLACES_SCHEMA_VERSION,
            "id": f"{spec['type']}_{serial:03d}",
            "type": spec["type"],
            "role": spec["role"],
            "story_role": spec.get("story_role", spec["role"]),
            "encounter_type": spec.get("encounter_type", "generic_place"),
            "danger_level": _float_in_range(spec.get("danger_level"), default=0.0),
            "loot_level": _float_in_range(spec.get("loot_level"), default=0.0),
            "center": {"x": center[0], "y": center[1]},
            "radius": PLACE_RADIUS_TILES,
            "bounds": bounds,
            "entrances": entrances,
            "object_ids": object_ids,
            "object_refs": _object_refs(objects),
            "anchor_object_id": object_ids[0],
            "marker_refs": [],
            "route_refs": [],
            "connected_places": [],
            "tags": tags,
            "biome_tags": biome_tags,
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
            distance = _manhattan(center, point)
            if distance > MAX_PLACE_OBJECT_DISTANCE_TILES:
                continue
            candidates.append((distance, item))
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
        "max_place_object_distance_tiles": MAX_PLACE_OBJECT_DISTANCE_TILES,
        "fields": {
            "bounds": "Inclusive tile-space bounding box for the place.",
            "entrances": "Candidate entry tiles around the place bounds.",
            "danger_level": "Normalized 0..1 gameplay danger hint.",
            "loot_level": "Normalized 0..1 reward density hint.",
            "connected_places": "Nearest semantic places by id.",
        },
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


def _objects_by_id(runtime_objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in runtime_objects:
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            by_id[item_id] = item
    return by_id


def _attach_place_connections(places: list[Any]) -> list[dict[str, Any]]:
    normalized = [dict(item) for item in places if isinstance(item, dict)]
    centers: dict[str, tuple[int, int]] = {}
    for place in normalized:
        place_id = place.get("id")
        center = place.get("center")
        point = _point_from_mapping(center)
        if isinstance(place_id, str) and point is not None:
            centers[place_id] = point
    for place in normalized:
        place_id = place.get("id")
        if not isinstance(place_id, str) or place_id not in centers:
            place.setdefault("connected_places", [])
            continue
        own_center = centers[place_id]
        distances = sorted(
            (_manhattan(own_center, center), other_id)
            for other_id, center in centers.items()
            if other_id != place_id
        )
        place["connected_places"] = [
            other_id for _, other_id in distances[:MAX_CONNECTED_PLACES]
        ]
    return normalized


def _bounds_for_objects(
    objects: list[dict[str, Any]],
    *,
    fallback_center: tuple[int, int],
    radius: int,
) -> dict[str, int]:
    points: list[tuple[int, int]] = []
    for item in objects:
        points.extend(_object_points(item))
    if not points:
        x, y = fallback_center
        return {"min_x": x - radius, "min_y": y - radius, "max_x": x + radius, "max_y": y + radius}
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return {
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
    }


def _entrances_for_bounds(bounds: dict[str, int]) -> list[dict[str, Any]]:
    min_x = int(bounds["min_x"])
    min_y = int(bounds["min_y"])
    max_x = int(bounds["max_x"])
    max_y = int(bounds["max_y"])
    mid_x = round((min_x + max_x) / 2)
    mid_y = round((min_y + max_y) / 2)
    candidates = (
        ("north", mid_x, min_y - 1),
        ("south", mid_x, max_y + 1),
        ("west", min_x - 1, mid_y),
        ("east", max_x + 1, mid_y),
    )
    return [
        {
            "id": f"entrance_{side}",
            "side": side,
            "position": {"x": x, "y": y},
        }
        for side, x, y in candidates
    ]


def _object_refs(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in objects:
        item_id = item.get("id")
        object_type = item.get("type")
        if not isinstance(item_id, str) or not isinstance(object_type, str):
            continue
        center = _object_center(item)
        refs.append(
            {
                "id": item_id,
                "type": object_type,
                "center": {"x": center[0], "y": center[1]} if center is not None else None,
            },
        )
    return refs


def _object_points(item: dict[str, Any]) -> list[tuple[int, int]]:
    points = _point_list(item.get("footprint"))
    if points:
        return points
    point = _object_center(item)
    return [point] if point is not None else []


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


def _point_list(value: Any) -> list[tuple[int, int]]:
    if not isinstance(value, list):
        return []
    points: list[tuple[int, int]] = []
    for item in value:
        point = _point(item)
        if point is not None:
            points.append(point)
    return points


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def _point_from_mapping(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return x, y
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [item for item in value if isinstance(item, str)]


def _float_in_range(value: Any, *, default: float) -> float:
    if isinstance(value, int | float):
        return round(max(0.0, min(float(value), 1.0)), 3)
    return default


def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])
