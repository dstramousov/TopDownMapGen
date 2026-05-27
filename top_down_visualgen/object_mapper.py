from __future__ import annotations

from typing import Any

from .models import VisualProfile, WorldPackage


class ObjectVisualMapper:
    """Convert runtime objects to visual sprite records."""

    def map_objects(
        self,
        world: WorldPackage,
        profile: VisualProfile,
    ) -> dict[str, Any]:
        """Build visual object records.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.

        Returns:
            Visual objects JSON object.
        """
        raw_items = world.runtime_objects.get("items", [])
        if not isinstance(raw_items, list):
            raw_items = []

        layer_order = _draw_layer_order(profile)
        items: list[dict[str, Any]] = []
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                continue
            visual_item = self._map_single(raw_item, profile, layer_order, index)
            items.append(visual_item)

        items.sort(key=lambda item: item["sort_key"])
        return {
            "schema_version": "visual-objects-v1",
            "kind": "visual_objects",
            "coordinate_space": "tile",
            "items": items,
            "summary": {
                "total": len(items),
                "by_draw_layer": _count_by(items, "draw_layer"),
                "by_sprite_id": _count_by(items, "sprite_id"),
            },
        }

    def _map_single(
        self,
        raw_item: dict[str, Any],
        profile: VisualProfile,
        layer_order: dict[str, int],
        stable_index: int,
    ) -> dict[str, Any]:
        object_id = _string_value(raw_item.get("id"), f"object_{stable_index:04d}")
        object_type = _string_value(raw_item.get("type"), "unknown")
        sprite_id = _sprite_for_type(profile, object_type)
        draw_layer = _string_value(raw_item.get("draw_layer"), "objects")
        sort_anchor = _sort_anchor(raw_item)
        visual_bounds = raw_item.get("visual_bounds")
        if not isinstance(visual_bounds, dict):
            visual_bounds = {
                "x": sort_anchor["x"],
                "y": sort_anchor["y"],
                "width": 1,
                "height": 1,
            }

        layer_rank = layer_order.get(draw_layer, layer_order.get("objects", 100))
        sort_key = [
            layer_rank,
            sort_anchor["y"],
            sort_anchor["elevation"],
            sort_anchor["x"],
            stable_index,
        ]
        return {
            "id": f"visual_{object_id}",
            "source_object_id": object_id,
            "source_object_type": object_type,
            "sprite_id": sprite_id,
            "draw_layer": draw_layer,
            "position": _position(raw_item, sort_anchor),
            "sort_anchor": sort_anchor,
            "sort_key": sort_key,
            "visual_bounds": visual_bounds,
            "pivot": raw_item.get("pivot", {"x": 0, "y": 0, "space": "tile_offset"}),
            "occlusion_hint": raw_item.get("occlusion_hint", {}),
            "source_tags": raw_item.get("tags", []),
        }


def _sprite_for_type(profile: VisualProfile, object_type: str) -> str:
    mapping = profile.object_rules.get("object_to_sprite", {})
    if isinstance(mapping, dict) and isinstance(mapping.get(object_type), str):
        return mapping[object_type]
    fallback = profile.object_rules.get("default_sprite", "object.generic")
    return fallback if isinstance(fallback, str) else "object.generic"


def _sort_anchor(raw_item: dict[str, Any]) -> dict[str, Any]:
    anchor = raw_item.get("sort_anchor")
    if isinstance(anchor, dict):
        x = _int_value(anchor.get("x"), _int_value(raw_item.get("x"), 0))
        y = _int_value(anchor.get("y"), _int_value(raw_item.get("y"), 0))
        elevation = _int_value(anchor.get("elevation"), _int_value(raw_item.get("elevation"), 0))
        rule = _string_value(anchor.get("rule"), "y_then_elevation_then_x")
        space = _string_value(anchor.get("space"), "tile")
    else:
        x = _int_value(raw_item.get("x"), 0)
        y = _int_value(raw_item.get("y"), 0)
        elevation = _int_value(raw_item.get("elevation"), 0)
        rule = "y_then_elevation_then_x"
        space = "tile"
    return {"x": x, "y": y, "elevation": elevation, "space": space, "rule": rule}


def _position(raw_item: dict[str, Any], sort_anchor: dict[str, Any]) -> dict[str, int]:
    position = raw_item.get("position")
    if (
        isinstance(position, list)
        and len(position) >= 2
        and isinstance(position[0], int)
        and isinstance(position[1], int)
    ):
        return {"x": position[0], "y": position[1]}
    return {"x": sort_anchor["x"], "y": sort_anchor["y"]}


def _draw_layer_order(profile: VisualProfile) -> dict[str, int]:
    raw_order = profile.profile.get("draw_layer_order", {})
    if not isinstance(raw_order, dict):
        return {"terrain": 0, "terrain_overlay": 10, "objects": 20}
    result: dict[str, int] = {}
    for key, value in raw_order.items():
        if isinstance(key, str) and isinstance(value, int):
            result[key] = value
    return result


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = item.get(key)
        if isinstance(value, str):
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default
