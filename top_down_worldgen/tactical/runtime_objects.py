from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Any

RUNTIME_OBJECT_SCHEMA_VERSION = "runtime-objects-v13"
DEFAULT_ELEVATION_LEVEL = 0
MIN_ELEVATION_LEVEL = -5
MAX_ELEVATION_LEVEL = 20
MIN_OBJECT_HEIGHT = 0
MAX_OBJECT_HEIGHT = 10
MAX_RUNTIME_OBJECTS = 160
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
LANDMARK_TYPES: frozenset[str] = frozenset(
    {"big_dead_tree", "broken_radio_mast", "old_checkpoint"},
)
BUNKER_TYPES: frozenset[str] = frozenset(
    {"buried_bunker_2x2", "buried_bunker_2x3"},
)
MIN_LANDMARKS = 1
MAX_LANDMARKS = 6
LANDMARK_MIN_DISTANCE_TILES = 8
MIN_OBJECT_DISTANCE_TILES = 3
PROTECTED_TILE_DISTANCE_TILES = 5
MAX_PLACEMENT_CANDIDATE_SAMPLE = 3000

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
    "big_dead_tree",
    "broken_radio_mast",
    "old_checkpoint",
    "buried_bunker_2x2",
    "buried_bunker_2x3",
    "car_wreck",
    "abandoned_backpack",
    "field_tent",
    "dead_campfire",
    "broken_generator",
    "cable_spool",
    "warning_sign",
    "old_grave_marker",
    "pit",
    "earth_berm",
    "hill",
    "wooden_bridge",
    "stone_ramp",
    "stone_stairs",
    "ruin_platform",
    "watchtower",
    "ancient_beacon",
    "old_well",
    "abandoned_cart",
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
        "type": "big_dead_tree",
        "name_ru": "Большое мёртвое дерево",
        "role": "landmark",
        "default_height": 10,
        "default_elevation": 0,
        "cover_type": "full",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": True,
        "interactive": False,
        "tags": ["landmark", "natural", "high_cover"],
    },
    {
        "type": "broken_radio_mast",
        "name_ru": "Сломанная радиомачта",
        "role": "landmark",
        "default_height": 10,
        "default_elevation": 0,
        "cover_type": "low",
        "blocks_movement": True,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["landmark", "signal", "navigation_landmark"],
    },
    {
        "type": "old_checkpoint",
        "name_ru": "Старый бетонный блокпост",
        "role": "defensive_landmark",
        "default_height": 4,
        "default_elevation": 0,
        "cover_type": "full",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": True,
        "interactive": False,
        "tags": ["landmark", "cover", "checkpoint", "ruin"],
    },

    {
        "type": "buried_bunker_2x2",
        "name_ru": "Заглублённый бункер 2x2",
        "role": "defensive_position",
        "default_height": 2,
        "default_elevation": 0,
        "surface_elevation": 0,
        "interior_elevation": -1,
        "cover_type": "full",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": True,
        "interactive": False,
        "tags": [
            "bunker",
            "cover",
            "defensive",
            "below_floor",
            "firing_ports",
        ],
    },
    {
        "type": "buried_bunker_2x3",
        "name_ru": "Заглублённый бункер 2x3",
        "role": "defensive_position",
        "default_height": 2,
        "default_elevation": 0,
        "surface_elevation": 0,
        "interior_elevation": -1,
        "cover_type": "full",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": True,
        "interactive": False,
        "tags": [
            "bunker",
            "cover",
            "defensive",
            "below_floor",
            "firing_ports",
        ],
    },

    {
        "type": "car_wreck",
        "name_ru": "Остов автомобиля",
        "role": "roadside_debris",
        "default_height": 2,
        "default_elevation": 0,
        "cover_type": "partial",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["debris", "roadside", "vehicle", "human_trace"],
    },
    {
        "type": "abandoned_backpack",
        "name_ru": "Брошенный рюкзак",
        "role": "interest_point",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": True,
        "tags": ["loot", "human_trace", "camp"],
    },
    {
        "type": "field_tent",
        "name_ru": "Полевая палатка",
        "role": "camp_object",
        "default_height": 2,
        "default_elevation": 0,
        "cover_type": "soft",
        "blocks_movement": True,
        "blocks_projectiles": False,
        "blocks_vision": True,
        "interactive": False,
        "tags": ["camp", "shelter", "human_trace"],
    },
    {
        "type": "dead_campfire",
        "name_ru": "Потухший костёр",
        "role": "camp_object",
        "default_height": 0,
        "default_elevation": 0,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["camp", "human_trace", "story_marker"],
    },
    {
        "type": "broken_generator",
        "name_ru": "Сломанный генератор",
        "role": "tech_debris",
        "default_height": 2,
        "default_elevation": 0,
        "cover_type": "partial",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["tech", "debris", "human_trace"],
    },
    {
        "type": "cable_spool",
        "name_ru": "Кабельная катушка",
        "role": "tech_debris",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "low",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["tech", "cover", "human_trace"],
    },
    {
        "type": "warning_sign",
        "name_ru": "Предупреждающий знак",
        "role": "marker",
        "default_height": 2,
        "default_elevation": 0,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["marker", "warning", "human_trace"],
    },
    {
        "type": "old_grave_marker",
        "name_ru": "Старая могила / крест",
        "role": "story_marker",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["story_marker", "grave", "human_trace"],
    },
    {
        "type": "pit",
        "name_ru": "Провал / яма",
        "role": "depression",
        "default_height": 0,
        "default_elevation": -1,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "below_floor", "terrain_feature"],
    },
    {
        "type": "earth_berm",
        "name_ru": "Земляная насыпь",
        "role": "terrain_cover",
        "default_height": 1,
        "default_elevation": 1,
        "cover_type": "low",
        "blocks_movement": False,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "raised_ground", "terrain_feature", "cover", "earthwork"],
    },
    {
        "type": "hill",
        "name_ru": "Небольшой холм",
        "role": "raised_ground",
        "default_height": 1,
        "default_elevation": 1,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "hill", "raised_ground", "terrain_feature"],
    },
    {
        "type": "wooden_bridge",
        "name_ru": "Деревянный мост",
        "role": "traversal_structure",
        "default_height": 1,
        "default_elevation": 2,
        "surface_elevation": 2,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "bridge", "platform", "traversal"],
    },
    {
        "type": "stone_ramp",
        "name_ru": "Каменный пандус",
        "role": "elevation_transition",
        "default_height": 0,
        "default_elevation": 1,
        "surface_elevation": 1,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "ramp", "transition", "traversal"],
    },
    {
        "type": "stone_stairs",
        "name_ru": "Каменные ступени",
        "role": "elevation_transition",
        "default_height": 0,
        "default_elevation": 1,
        "surface_elevation": 1,
        "cover_type": "none",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "stairs", "transition", "traversal"],
    },
    {
        "type": "ruin_platform",
        "name_ru": "Приподнятая руинная платформа",
        "role": "high_ground",
        "default_height": 1,
        "default_elevation": 2,
        "surface_elevation": 2,
        "cover_type": "partial",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "platform", "ruins", "high_ground"],
    },
    {
        "type": "watchtower",
        "name_ru": "Наблюдательная вышка",
        "role": "high_landmark",
        "default_height": 4,
        "default_elevation": 3,
        "surface_elevation": 3,
        "cover_type": "partial",
        "blocks_movement": True,
        "blocks_projectiles": False,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["elevation", "tower", "high_platform", "landmark", "high_ground"],
    },
    {
        "type": "ancient_beacon",
        "name_ru": "Древний верхний маяк",
        "role": "special_high_landmark",
        "default_height": 5,
        "default_elevation": 4,
        "surface_elevation": 4,
        "cover_type": "none",
        "blocks_movement": True,
        "blocks_projectiles": False,
        "blocks_vision": True,
        "interactive": True,
        "tags": ["elevation", "special_high_landmark", "landmark", "high_ground", "story_marker"],
    },
    {
        "type": "old_well",
        "name_ru": "Колодец",
        "role": "story_landmark",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "partial",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["landmark", "story_marker", "human_trace"],
    },
    {
        "type": "abandoned_cart",
        "name_ru": "Брошенная тележка",
        "role": "roadside_debris",
        "default_height": 1,
        "default_elevation": 0,
        "cover_type": "partial",
        "blocks_movement": True,
        "blocks_projectiles": True,
        "blocks_vision": False,
        "interactive": False,
        "tags": ["debris", "roadside", "human_trace"],
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



def _rect_offsets(width: int, height: int) -> tuple[tuple[int, int], ...]:
    return tuple((x, y) for y in range(height) for x in range(width))


def _footprint_defaults_for_type(object_type: str) -> dict[str, Any]:
    defaults: dict[str, dict[str, Any]] = {
        "fallen_log": _footprint_default(width=2, height=1, rotatable=True),
        "stone_chunk": _footprint_default(width=1, height=1),
        "bush_thicket": _footprint_default(width=1, height=1),
        "rusted_barrel": _footprint_default(width=1, height=1),
        "scrap_pile": _footprint_default(width=2, height=1, rotatable=True),
        "ammo_cache": _footprint_default(width=1, height=1, blocks_movement=False),
        "medkit_cache": _footprint_default(width=1, height=1, blocks_movement=False),
        "big_dead_tree": _footprint_default(width=2, height=2, visual_width=2, visual_height=3),
        "broken_radio_mast": _footprint_default(width=1, height=1, visual_width=1, visual_height=3),
        "old_checkpoint": _footprint_default(width=3, height=2, rotatable=True),
        "buried_bunker_2x2": _footprint_default(width=2, height=2),
        "buried_bunker_2x3": _footprint_default(width=2, height=3, rotatable=True),
        "car_wreck": _footprint_default(width=2, height=1, rotatable=True),
        "abandoned_backpack": _footprint_default(width=1, height=1, blocks_movement=False),
        "field_tent": _footprint_default(width=2, height=2),
        "dead_campfire": _footprint_default(width=1, height=1, blocks_movement=False),
        "broken_generator": _footprint_default(width=2, height=1, rotatable=True),
        "cable_spool": _footprint_default(width=1, height=1),
        "warning_sign": _footprint_default(width=1, height=1, blocks_movement=False),
        "old_grave_marker": _footprint_default(width=1, height=1, blocks_movement=False),
        "pit": _footprint_default(width=2, height=2, blocks_movement=False),
        "earth_berm": _footprint_default(width=2, height=1, rotatable=True, blocks_movement=False),
        "hill": _footprint_default(width=3, height=3, blocks_movement=False),
        "wooden_bridge": _footprint_default(width=4, height=1, rotatable=True, blocks_movement=False),
        "stone_ramp": _footprint_default(width=2, height=1, rotatable=True, blocks_movement=False),
        "stone_stairs": _footprint_default(width=2, height=1, rotatable=True, blocks_movement=False),
        "ruin_platform": _footprint_default(width=3, height=2, rotatable=True, blocks_movement=False),
        "watchtower": _footprint_default(width=2, height=2, visual_width=2, visual_height=4),
        "ancient_beacon": _footprint_default(width=1, height=1, visual_width=1, visual_height=5),
        "old_well": _footprint_default(width=2, height=2),
        "abandoned_cart": _footprint_default(width=2, height=1, rotatable=True),
        "trench": _footprint_default(width=1, height=1, blocks_movement=False),
    }
    return dict(defaults.get(object_type, _footprint_default(width=1, height=1)))


def _footprint_default(
    *,
    width: int,
    height: int,
    rotatable: bool = False,
    blocks_movement: bool = True,
    visual_width: int | None = None,
    visual_height: int | None = None,
) -> dict[str, Any]:
    footprint = _rect_offsets(width, height)
    collision_footprint = footprint if blocks_movement else ()
    return {
        "default_footprint": [[x, y] for x, y in footprint],
        "default_collision_footprint": [[x, y] for x, y in collision_footprint],
        "default_visual_bounds": {
            "offset_x": 0,
            "offset_y": 0,
            "width": visual_width or width,
            "height": visual_height or height,
        },
        "default_pivot": {
            "x": max(0, width // 2),
            "y": height - 1,
            "space": "tile_offset",
        },
        "rotatable_footprint": rotatable,
    }


def _runtime_type_with_gameplay(spec: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(spec)
    enriched.update(_footprint_defaults_for_type(str(spec["type"])))
    enriched["collision_profile"] = _collision_profile_for_spec(spec)
    enriched["combat_properties"] = _combat_properties_for_type(str(spec["type"]))
    if spec["type"] == "trench":
        enriched["stance_hints"] = {
            "standing": "exposed",
            "crouching": "protected_from_flat_fire",
        }
    return enriched


def _collision_profile_for_spec(spec: dict[str, Any]) -> dict[str, str]:
    cover_type = str(spec.get("cover_type", "none"))
    if spec.get("blocks_vision") is True and cover_type == "soft":
        vision = "soft_blocked"
    elif spec.get("blocks_vision") is True:
        vision = "blocked"
    else:
        vision = "passable"
    return {
        "movement": "blocked" if spec.get("blocks_movement") is True else "passable",
        "projectiles": "blocked" if spec.get("blocks_projectiles") is True else "passable",
        "vision": vision,
    }


def _combat_properties_for_type(object_type: str) -> dict[str, Any]:
    properties_by_type: dict[str, dict[str, Any]] = {
        "fallen_log": {"cover_value": 0.55, "concealment_value": 0.0},
        "stone_chunk": {"cover_value": 0.9, "concealment_value": 0.0},
        "bush_thicket": {"cover_value": 0.15, "concealment_value": 0.7},
        "rusted_barrel": {
            "cover_value": 0.5,
            "concealment_value": 0.0,
            "explosive": True,
        },
        "scrap_pile": {"cover_value": 0.45, "concealment_value": 0.0},
        "ammo_cache": {"cover_value": 0.0, "concealment_value": 0.0, "loot": True},
        "medkit_cache": {"cover_value": 0.0, "concealment_value": 0.0, "loot": True},
        "trench": {
            "cover_value": 0.8,
            "concealment_value": 0.25,
            "stance_dependent": True,
        },
        "big_dead_tree": {"cover_value": 0.8, "concealment_value": 0.25},
        "broken_radio_mast": {"cover_value": 0.2, "concealment_value": 0.0},
        "old_checkpoint": {"cover_value": 0.85, "concealment_value": 0.0},
        "buried_bunker_2x2": {
            "cover_value": 0.95,
            "concealment_value": 0.35,
            "firing_ports": True,
        },
        "buried_bunker_2x3": {
            "cover_value": 0.95,
            "concealment_value": 0.35,
            "firing_ports": True,
        },
        "car_wreck": {"cover_value": 0.6, "concealment_value": 0.0},
        "abandoned_backpack": {"cover_value": 0.0, "concealment_value": 0.0, "loot": True},
        "field_tent": {"cover_value": 0.1, "concealment_value": 0.45},
        "dead_campfire": {"cover_value": 0.0, "concealment_value": 0.0},
        "broken_generator": {"cover_value": 0.55, "concealment_value": 0.0},
        "cable_spool": {"cover_value": 0.35, "concealment_value": 0.0},
        "warning_sign": {"cover_value": 0.0, "concealment_value": 0.0},
        "old_grave_marker": {"cover_value": 0.0, "concealment_value": 0.0},
        "pit": {"cover_value": 0.25, "concealment_value": 0.15},
        "earth_berm": {"cover_value": 0.45, "concealment_value": 0.0},
        "hill": {"cover_value": 0.1, "concealment_value": 0.0},
        "wooden_bridge": {"cover_value": 0.0, "concealment_value": 0.0},
        "stone_ramp": {"cover_value": 0.0, "concealment_value": 0.0},
        "stone_stairs": {"cover_value": 0.0, "concealment_value": 0.0},
        "ruin_platform": {"cover_value": 0.35, "concealment_value": 0.0},
        "watchtower": {"cover_value": 0.65, "concealment_value": 0.0},
        "ancient_beacon": {"cover_value": 0.1, "concealment_value": 0.0},
        "old_well": {"cover_value": 0.5, "concealment_value": 0.0},
        "abandoned_cart": {"cover_value": 0.4, "concealment_value": 0.0},
    }
    result = {
        "cover_value": 0.0,
        "concealment_value": 0.0,
        "explosive": False,
        "loot": False,
    }
    result.update(properties_by_type.get(object_type, {}))
    return result


RUNTIME_OBJECT_TYPES = tuple(
    _runtime_type_with_gameplay(item) for item in RUNTIME_OBJECT_TYPES
)
COVER_TYPES: frozenset[str] = frozenset(
    {"none", "soft", "low", "partial", "full", "trench"},
)
COLLISION_MOVEMENT_VALUES: frozenset[str] = frozenset({"passable", "blocked"})
COLLISION_PROJECTILE_VALUES: frozenset[str] = frozenset({"passable", "blocked"})
COLLISION_VISION_VALUES: frozenset[str] = frozenset(
    {"passable", "soft_blocked", "blocked"},
)
COMBAT_PROPERTY_VALUE_MIN = 0.0
COMBAT_PROPERTY_VALUE_MAX = 1.0
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
    generation_tuning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach runtime object and elevation layers to tactical data.

    Args:
        tactical_data: Runtime tactical JSON object.
        seed: Optional deterministic seed for runtime object placement.
        generation_tuning: Optional user-facing world density tuning scales.

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

    objects = RuntimeObjectPlacer(seed, generation_tuning=generation_tuning).place(enriched)
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
    landmark_counts = {
        object_type: counts[object_type]
        for object_type in sorted(LANDMARK_TYPES)
        if counts[object_type] > 0
    }
    if landmark_counts:
        summary["landmarks"] = {
            "total": sum(landmark_counts.values()),
            "by_type": landmark_counts,
        }
    return summary


class RuntimeObjectPlacer:
    """Places deterministic gameplay objects on an existing tactical map."""

    def __init__(self, seed: int, *, generation_tuning: dict[str, Any] | None = None) -> None:
        """Initialize placer.

        Args:
            seed: Resolved uint64 map seed.
            generation_tuning: Optional user-facing world density tuning scales.
        """
        self._rng = random.Random(seed ^ 0x5EED_0B1E_C7)
        self._generation_tuning = generation_tuning or {}

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
        protected.update(_ruin_site_reserved_positions(tactical_data))
        occupied: set[tuple[int, int]] = set(protected)
        candidates = _candidate_positions(rows, protected)
        if not candidates:
            return []

        scale = max(0.5, min(1.5, (width * height) / 15360.0))
        objects: list[dict[str, Any]] = []
        quotas = _placement_quotas()
        anchors = _anchors(tactical_data)
        anchor_distance_by_point = _anchor_distances(candidates, anchors)
        unavailable = _points_too_close_to_occupied(occupied)

        for quota in quotas:
            target_count = self._target_count(quota, area_scale=scale)
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
                    unavailable=unavailable,
                    preferred_tiles=quota.preferred_tiles,
                    anchor_distance_by_point=anchor_distance_by_point,
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
                _mark_points_too_close(unavailable, footprint)
                placed += 1
                if len(objects) >= MAX_RUNTIME_OBJECTS:
                    return objects
        return objects

    def _target_count(self, quota: RuntimeObjectQuota, *, area_scale: float) -> int:
        """Return tuned target count for a runtime object quota."""
        if quota.object_type in BUNKER_TYPES:
            return max(0, round(quota.base_count * _tuning_scale(self._generation_tuning, "bunker_scale")))
        if quota.object_type in LANDMARK_TYPES:
            return quota.base_count
        if quota.object_type == "bush_thicket":
            return max(0, int(self._generation_tuning.get("bush_thicket_count", quota.base_count)))
        return max(1, round(quota.base_count * area_scale))

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
        unavailable: set[tuple[int, int]],
        preferred_tiles: frozenset[str],
        anchor_distance_by_point: dict[tuple[int, int], int],
        object_type: str,
        desired_shape: str | None,
    ) -> tuple[list[tuple[int, int]], str, str] | None:
        sample_size = min(len(candidates), MAX_PLACEMENT_CANDIDATE_SAMPLE)
        shuffled = self._rng.sample(candidates, sample_size)
        shuffled.sort(
            key=lambda point: _placement_score(
                point,
                rows=rows,
                preferred_tiles=preferred_tiles,
                anchor_distance_by_point=anchor_distance_by_point,
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
                if _footprint_is_available(
                    footprint,
                    rows=rows,
                    occupied=occupied,
                    unavailable=unavailable,
                ):
                    return footprint, orientation, shape
        return None


def _tuning_scale(tuning: dict[str, Any], key: str) -> float:
    """Return a sanitized tuning scale from a runtime tuning dictionary."""
    try:
        return max(0.0, min(4.0, float(tuning.get(key, 1.0))))
    except (TypeError, ValueError):
        return 1.0


def _placement_quotas() -> tuple[RuntimeObjectQuota, ...]:
    return (
        RuntimeObjectQuota("trench", 4, frozenset({"+", ".", "c"})),
        RuntimeObjectQuota("big_dead_tree", 2, frozenset({"+"})),
        RuntimeObjectQuota("broken_radio_mast", 1, frozenset({"R", "c", "."})),
        RuntimeObjectQuota("old_checkpoint", 1, frozenset({"R", "c", "."})),
        RuntimeObjectQuota("buried_bunker_2x2", 2, frozenset({"R", "c", ".", "+"})),
        RuntimeObjectQuota("buried_bunker_2x3", 2, frozenset({"R", "c", ".", "+"})),
        RuntimeObjectQuota("old_well", 1, frozenset({"+", "R", "c"})),
        RuntimeObjectQuota("car_wreck", 2, frozenset({".", "c", "R"})),
        RuntimeObjectQuota("field_tent", 2, frozenset({"+", ".", "R"})),
        RuntimeObjectQuota("broken_generator", 1, frozenset({"R", "c", "."})),
        RuntimeObjectQuota("cable_spool", 2, frozenset({"R", "c", "."})),
        RuntimeObjectQuota("warning_sign", 2, frozenset({".", "c", "+"})),
        RuntimeObjectQuota("old_grave_marker", 1, frozenset({"+", "c"})),
        RuntimeObjectQuota("pit", 2, frozenset({"+", "c"})),
        RuntimeObjectQuota("earth_berm", 3, frozenset({"+", ".", "c"})),
        RuntimeObjectQuota("hill", 3, frozenset({"+", "c"})),
        RuntimeObjectQuota("wooden_bridge", 1, frozenset({".", "R", "c", "+"})),
        RuntimeObjectQuota("stone_ramp", 2, frozenset({"R", "c", ".", "+"})),
        RuntimeObjectQuota("stone_stairs", 2, frozenset({"R", "c", ".", "+"})),
        RuntimeObjectQuota("ruin_platform", 1, frozenset({"R", "c"})),
        RuntimeObjectQuota("watchtower", 1, frozenset({"R", "c", "+"})),
        RuntimeObjectQuota("ancient_beacon", 1, frozenset({"R", "c", "+"})),
        RuntimeObjectQuota("abandoned_cart", 2, frozenset({".", "c", "+"})),
        RuntimeObjectQuota("abandoned_backpack", 3, frozenset({"+", ".", "R", "c"})),
        RuntimeObjectQuota("dead_campfire", 2, frozenset({"+", ".", "R"})),
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


def _ruin_site_reserved_positions(tactical_data: dict[str, Any]) -> set[tuple[int, int]]:
    """Return planned building footprints reserved from runtime object placement."""
    payload = tactical_data.get("ruin_sites")
    if not isinstance(payload, dict):
        return set()
    reserved: set[tuple[int, int]] = set()
    sites = payload.get("sites")
    if not isinstance(sites, list):
        return reserved
    for site in sites:
        if not isinstance(site, dict):
            continue
        buildings = site.get("buildings")
        if not isinstance(buildings, list):
            continue
        for building in buildings:
            if not isinstance(building, dict):
                continue
            rect = building.get("rect")
            if not isinstance(rect, dict):
                continue
            try:
                left = int(rect["left"])
                top = int(rect["top"])
                right = int(rect["right"])
                bottom = int(rect["bottom"])
            except (KeyError, TypeError, ValueError):
                continue
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    reserved.add((x, y))
            approach = building.get("outside_approach")
            if (
                isinstance(approach, list)
                and len(approach) == 2
                and all(isinstance(value, int) for value in approach)
            ):
                reserved.add((approach[0], approach[1]))
    return reserved


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


def _anchor_distances(
    candidates: list[tuple[int, int]],
    anchors: list[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    if not anchors:
        return {}
    return {
        point: min(_manhattan(point, anchor) for anchor in anchors)
        for point in candidates
    }


def _placement_score(
    point: tuple[int, int],
    *,
    rows: list[str],
    preferred_tiles: frozenset[str],
    anchor_distance_by_point: dict[tuple[int, int], int],
    rng: random.Random,
) -> tuple[int, int, float]:
    x, y = point
    tile_penalty = 0 if rows[y][x] in preferred_tiles else 3
    anchor_distance = anchor_distance_by_point.get(point, 0)
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
    _ = rows
    _ = desired_shape
    spec = RUNTIME_OBJECT_TYPE_BY_NAME[object_type]
    offsets = _offset_points(spec.get("default_footprint"))
    if not offsets:
        offsets = [(0, 0)]
    variants = _oriented_offset_variants(
        offsets,
        rotatable=spec.get("rotatable_footprint") is True,
    )
    rng.shuffle(variants)
    return [
        (
            [(point[0] + offset_x, point[1] + offset_y) for offset_x, offset_y in variant],
            orientation,
            _shape_name(variant),
        )
        for variant, orientation in variants
    ]


def _offset_points(value: Any) -> list[tuple[int, int]]:
    if not isinstance(value, list):
        return []
    points: list[tuple[int, int]] = []
    for point in value:
        parsed = _point(point)
        if parsed is not None:
            points.append(parsed)
    return points


def _oriented_offset_variants(
    offsets: list[tuple[int, int]],
    *,
    rotatable: bool,
) -> list[tuple[list[tuple[int, int]], str]]:
    normalized = _normalize_offsets(offsets)
    variants: list[tuple[list[tuple[int, int]], str]] = [(normalized, "east_west")]
    if rotatable:
        rotated = _normalize_offsets([(y, x) for x, y in normalized])
        if rotated != normalized:
            variants.append((rotated, "north_south"))
    return variants


def _normalize_offsets(offsets: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not offsets:
        return []
    min_x = min(x for x, _ in offsets)
    min_y = min(y for _, y in offsets)
    return sorted({(x - min_x, y - min_y) for x, y in offsets})


def _shape_name(offsets: list[tuple[int, int]]) -> str:
    if not offsets:
        return "empty"
    width = max(x for x, _ in offsets) + 1
    height = max(y for _, y in offsets) + 1
    if len(offsets) == 1:
        return "single"
    if len(offsets) == width * height:
        return f"rect_{width}x{height}"
    return "multi_cell"


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
    unavailable: set[tuple[int, int]],
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
        if point in unavailable:
            return False
    return True


def _points_too_close_to_occupied(
    occupied: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    unavailable: set[tuple[int, int]] = set()
    _mark_points_too_close(unavailable, occupied)
    return unavailable


def _mark_points_too_close(
    unavailable: set[tuple[int, int]],
    points: Any,
) -> None:
    radius = MIN_OBJECT_DISTANCE_TILES - 1
    for point_x, point_y in points:
        for delta_y in range(-radius, radius + 1):
            remaining = radius - abs(delta_y)
            for delta_x in range(-remaining, remaining + 1):
                unavailable.add((point_x + delta_x, point_y + delta_y))


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
    collision_footprint = _world_collision_footprint(
        anchor=(x, y),
        footprint=footprint,
        spec=spec,
        orientation=orientation,
    )
    visual_bounds = _world_visual_bounds(anchor=(x, y), spec=spec, orientation=orientation)
    item: dict[str, Any] = {
        "id": object_id,
        "type": object_type,
        "role": spec["role"],
        "x": x,
        "y": y,
        "position": [x, y],
        "anchor": [x, y],
        "elevation": spec["default_elevation"],
        "height": spec["default_height"],
        "cover_type": spec["cover_type"],
        "blocks_movement": spec["blocks_movement"],
        "blocks_projectiles": spec["blocks_projectiles"],
        "blocks_vision": spec["blocks_vision"],
        "interactive": spec["interactive"],
        "orientation": orientation,
        "shape": shape,
        "footprint": [[point_x, point_y] for point_x, point_y in footprint],
        "collision_footprint": [
            [point_x, point_y] for point_x, point_y in collision_footprint
        ],
        "visual_bounds": visual_bounds,
        "pivot": dict(spec["default_pivot"]),
        "interaction_shape": _world_interaction_shape(
            footprint=footprint,
            spec=spec,
        ),
        "sort_anchor": _world_sort_anchor(
            visual_bounds=visual_bounds,
            elevation=int(spec.get("default_elevation", DEFAULT_ELEVATION_LEVEL)),
        ),
        "draw_layer": _world_draw_layer(spec),
        "occlusion_hint": _world_occlusion_hint(spec),
        "tags": list(spec["tags"]),
        "collision_profile": dict(spec["collision_profile"]),
        "combat_properties": dict(spec["combat_properties"]),
    }
    if "surface_elevation" in spec:
        item["surface_elevation"] = spec["surface_elevation"]
    if "interior_elevation" in spec:
        item["interior_elevation"] = spec["interior_elevation"]
    firing_ports = _world_firing_ports(
        anchor=(x, y),
        spec=spec,
        orientation=orientation,
        visual_bounds=visual_bounds,
    )
    if firing_ports:
        item["firing_ports"] = firing_ports
    if "stance_hints" in spec:
        item["stance_hints"] = dict(spec["stance_hints"])
    return item


def _world_firing_ports(
    *,
    anchor: tuple[int, int],
    spec: dict[str, Any],
    orientation: str,
    visual_bounds: dict[str, int],
) -> list[dict[str, Any]]:
    if spec.get("type") not in BUNKER_TYPES:
        _ = anchor
        return []
    try:
        x = int(visual_bounds["x"])
        y = int(visual_bounds["y"])
        width = int(visual_bounds["width"])
        height = int(visual_bounds["height"])
    except (KeyError, TypeError, ValueError):
        return []
    sides = _bunker_firing_port_sides(
        object_type=str(spec.get("type")),
        orientation=orientation,
        width=width,
        height=height,
    )
    elevation = int(spec.get("interior_elevation", TRENCH_ELEVATION_LEVEL))
    ports: list[dict[str, Any]] = []
    for side in sides:
        positions = _edge_positions(x=x, y=y, width=width, height=height, side=side)
        ports.append(
            {
                "side": side,
                "positions": [[point_x, point_y] for point_x, point_y in positions],
                "elevation": elevation,
                "arc": "outward",
            },
        )
    return ports


def _bunker_firing_port_sides(
    *,
    object_type: str,
    orientation: str,
    width: int,
    height: int,
) -> list[str]:
    if object_type == "buried_bunker_2x2":
        return ["north", "south"] if orientation != "north_south" else ["east", "west"]
    if width > height:
        return ["north", "south"]
    return ["west", "east"]


def _edge_positions(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    side: str,
) -> list[tuple[int, int]]:
    if side == "north":
        return [(x + offset, y) for offset in range(width)]
    if side == "south":
        return [(x + offset, y + height - 1) for offset in range(width)]
    if side == "west":
        return [(x, y + offset) for offset in range(height)]
    if side == "east":
        return [(x + width - 1, y + offset) for offset in range(height)]
    return []


def _world_collision_footprint(
    *,
    anchor: tuple[int, int],
    footprint: list[tuple[int, int]],
    spec: dict[str, Any],
    orientation: str,
) -> list[tuple[int, int]]:
    if spec.get("type") == "trench":
        return list(footprint)
    offsets = _offset_points(spec.get("default_collision_footprint"))
    if not offsets:
        return []
    variants = {
        variant_orientation: variant_offsets
        for variant_offsets, variant_orientation in _oriented_offset_variants(
            offsets,
            rotatable=spec.get("rotatable_footprint") is True,
        )
    }
    selected_offsets = variants.get(orientation, offsets)
    return [(anchor[0] + offset_x, anchor[1] + offset_y) for offset_x, offset_y in selected_offsets]


def _world_visual_bounds(
    *,
    anchor: tuple[int, int],
    spec: dict[str, Any],
    orientation: str,
) -> dict[str, int]:
    bounds = spec.get("default_visual_bounds")
    if not isinstance(bounds, dict):
        bounds = {"offset_x": 0, "offset_y": 0, "width": 1, "height": 1}
    try:
        offset_x = int(bounds.get("offset_x", 0))
        offset_y = int(bounds.get("offset_y", 0))
        width = max(1, int(bounds.get("width", 1)))
        height = max(1, int(bounds.get("height", 1)))
    except (TypeError, ValueError):
        offset_x = 0
        offset_y = 0
        width = 1
        height = 1
    if orientation == "north_south" and spec.get("rotatable_footprint") is True:
        width, height = height, width
    return {
        "x": anchor[0] + offset_x,
        "y": anchor[1] + offset_y,
        "width": width,
        "height": height,
    }



def _interaction_points_around(
    footprint: list[tuple[int, int]],
) -> list[list[int]]:
    occupied = set(footprint)
    points: set[tuple[int, int]] = set()
    for x, y in occupied:
        for candidate in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if candidate not in occupied:
                points.add(candidate)
    return [[x, y] for x, y in sorted(points, key=lambda point: (point[1], point[0]))]


def _world_interaction_shape(
    *,
    footprint: list[tuple[int, int]],
    spec: dict[str, Any],
) -> dict[str, Any]:
    if spec.get("interactive") is True or "loot" in set(spec.get("tags", [])):
        return {
            "type": "adjacent_tiles",
            "points": _interaction_points_around(footprint),
            "source": "footprint_perimeter",
        }
    if spec.get("type") in BUNKER_TYPES:
        return {
            "type": "firing_ports",
            "points": [],
            "source": "firing_ports",
        }
    return {"type": "none", "points": [], "source": "none"}


def _world_sort_anchor(
    *,
    visual_bounds: dict[str, int],
    elevation: int,
) -> dict[str, Any]:
    try:
        x = int(visual_bounds["x"])
        y = int(visual_bounds["y"])
        width = int(visual_bounds["width"])
        height = int(visual_bounds["height"])
    except (KeyError, TypeError, ValueError):
        x = 0
        y = 0
        width = 1
        height = 1
    return {
        "x": x + max(0, width // 2),
        "y": y + max(0, height - 1),
        "elevation": elevation,
        "space": "tile",
        "rule": "y_then_elevation_then_x",
    }


def _world_draw_layer(spec: dict[str, Any]) -> str:
    tags = set(spec.get("tags", []))
    object_type = str(spec.get("type", ""))
    height = int(spec.get("default_height", 0))
    if object_type in {"pit", "trench", "earth_berm", "hill", "wooden_bridge", "stone_ramp", "stone_stairs"}:
        return "terrain_overlay"
    if "below_floor" in tags:
        return "structure"
    if "landmark" in tags or height >= 4:
        return "tall_object"
    return "object"


def _world_occlusion_hint(spec: dict[str, Any]) -> dict[str, Any]:
    blocks_vision = spec.get("blocks_vision") is True
    height = int(spec.get("default_height", 0))
    if blocks_vision and height >= 3:
        mode = "solid"
    elif blocks_vision:
        mode = "partial"
    elif height >= 3:
        mode = "visual_only"
    else:
        mode = "none"
    return {
        "occludes_actor": mode in {"solid", "partial", "visual_only"},
        "mode": mode,
        "source": "object_height_and_vision_profile",
    }

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
        level = _object_elevation_level(item)
        if level is None or level == DEFAULT_ELEVATION_LEVEL:
            continue
        for x, y in _object_footprint_points(item):
            if (x, y) in existing:
                continue
            cells.append({"x": x, "y": y, "level": level})
            existing.add((x, y))


def _object_elevation_level(item: dict[str, Any]) -> int | None:
    object_type = item.get("type")
    if object_type in {"trench", "pit"} | BUNKER_TYPES:
        return TRENCH_ELEVATION_LEVEL
    for key in ("surface_elevation", "elevation"):
        value = item.get(key)
        if isinstance(value, int):
            return value
    return None


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
