from __future__ import annotations

from collections import Counter
from typing import Any

from .models import VisualProfile, WorldPackage


class PlaceTreatmentMapper:
    """Build non-gameplay visual scene accents from semantic places."""

    def map_place_treatments(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        visual_layers: dict[str, Any],
    ) -> dict[str, Any]:
        """Build deterministic place treatment visual objects.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            visual_layers: Visual layer data.

        Returns:
            Place treatment object items and report data.
        """
        rules = profile.place_rules
        if rules.get("enabled") is not True:
            return _empty_result()

        terrain_rows = _terrain_rows(world.terrain)
        visual_rows = _visual_rows(visual_layers)
        rule_items = _rule_items(rules)
        blocked_terrain = _string_set(rules.get("blocked_terrain"))
        layer_order = _draw_layer_order(profile)
        salt = _string_value(rules.get("seed_salt"), "visual-place-treatment-v1")
        places = _place_items(world.places)

        items: list[dict[str, Any]] = []
        occupied: set[tuple[int, int]] = set()
        rule_counts: Counter[str] = Counter()
        place_type_counts: Counter[str] = Counter()
        sprite_counts: Counter[str] = Counter()
        skipped_counts: Counter[str] = Counter()

        for place in places:
            place_type = _string_value(place.get("type"), "")
            place_id = _string_value(place.get("id"), place_type)
            if not place_type:
                skipped_counts["missing_place_type"] += 1
                continue

            for rule in rule_items:
                if not _rule_matches_place(rule=rule, place_type=place_type):
                    continue
                rule_id = _string_value(rule.get("id"), "place_treatment")
                max_items = _positive_int_value(rule.get("max_items_per_place"), 1)
                chance = _int_value(rule.get("chance_percent"), 100)
                if chance <= 0:
                    skipped_counts["chance_zero"] += 1
                    continue

                accepted_for_rule = 0
                candidates = _candidate_positions(
                    place=place,
                    mode=_string_value(rule.get("placement"), "within_bounds"),
                    terrain_rows=terrain_rows,
                    salt=salt,
                    rule_id=rule_id,
                )
                if not candidates:
                    skipped_counts["no_candidates"] += 1
                    continue

                allowed_terrain = _string_set(rule.get("terrain_types"))
                allowed_visual_tiles = _string_set(rule.get("visual_tiles"))
                for index, (x, y) in enumerate(candidates):
                    if accepted_for_rule >= max_items:
                        break
                    terrain_type = _terrain_at(terrain_rows, x, y)
                    if terrain_type is None:
                        skipped_counts["out_of_bounds"] += 1
                        continue
                    if terrain_type in blocked_terrain:
                        skipped_counts["blocked_terrain"] += 1
                        continue
                    if allowed_terrain and terrain_type not in allowed_terrain:
                        skipped_counts["terrain_mismatch"] += 1
                        continue
                    visual_tile = _visual_at(visual_rows, x, y)
                    if allowed_visual_tiles and visual_tile not in allowed_visual_tiles:
                        skipped_counts["visual_tile_mismatch"] += 1
                        continue
                    if (x, y) in occupied:
                        skipped_counts["occupied"] += 1
                        continue
                    roll = _stable_percent(salt, place_id, rule_id, x, y, index)
                    if roll >= min(chance, 100):
                        skipped_counts["chance_miss"] += 1
                        continue
                    sprite_id = _choose_sprite(rule, salt, place_id, x, y, index)
                    if sprite_id is None:
                        skipped_counts["missing_sprite"] += 1
                        continue
                    item = _build_place_treatment_item(
                        x=x,
                        y=y,
                        sprite_id=sprite_id,
                        rule=rule,
                        place=place,
                        layer_order=layer_order,
                        stable_index=len(items),
                    )
                    items.append(item)
                    occupied.add((x, y))
                    accepted_for_rule += 1
                    rule_counts[rule_id] += 1
                    place_type_counts[place_type] += 1
                    sprite_counts[sprite_id] += 1

        items.sort(key=lambda item: item["sort_key"])
        return {
            "items": items,
            "report": {
                "schema_version": "visual-debug-place-treatment-report-v1",
                "kind": "visual_debug_place_treatment_report",
                "source_layer": "objects.places",
                "rules_enabled": True,
                "summary": {
                    "total": len(items),
                    "by_rule": dict(sorted(rule_counts.items())),
                    "by_place_type": dict(sorted(place_type_counts.items())),
                    "by_sprite_id": dict(sorted(sprite_counts.items())),
                    "skipped": dict(sorted(skipped_counts.items())),
                },
                "quality": {
                    "status": "ok",
                },
            },
        }


def _empty_result() -> dict[str, Any]:
    return {
        "items": [],
        "report": {
            "schema_version": "visual-debug-place-treatment-report-v1",
            "kind": "visual_debug_place_treatment_report",
            "source_layer": "objects.places",
            "rules_enabled": False,
            "summary": {
                "total": 0,
                "by_rule": {},
                "by_place_type": {},
                "by_sprite_id": {},
                "skipped": {},
            },
            "quality": {"status": "disabled"},
        },
    }


def _build_place_treatment_item(
    *,
    x: int,
    y: int,
    sprite_id: str,
    rule: dict[str, Any],
    place: dict[str, Any],
    layer_order: dict[str, int],
    stable_index: int,
) -> dict[str, Any]:
    rule_id = _string_value(rule.get("id"), "place_treatment")
    draw_layer = _string_value(rule.get("draw_layer"), "terrain_overlay")
    layer_rank = layer_order.get(draw_layer, layer_order.get("terrain_overlay", 10))
    place_id = _string_value(place.get("id"), "unknown_place")
    place_type = _string_value(place.get("type"), "unknown_place")
    sort_anchor = {
        "x": x,
        "y": y,
        "elevation": 0,
        "space": "tile",
        "rule": "y_then_elevation_then_x",
    }
    return {
        "id": f"visual_place_{stable_index:05d}",
        "source_object_id": place_id,
        "source_object_type": "visual_place_treatment",
        "source_place_id": place_id,
        "source_place_type": place_type,
        "sprite_id": sprite_id,
        "draw_layer": draw_layer,
        "position": {"x": x, "y": y},
        "sort_anchor": sort_anchor,
        "sort_key": [layer_rank, y, 0, x, stable_index],
        "visual_bounds": {"x": x, "y": y, "width": 1, "height": 1},
        "pivot": {"x": 0, "y": 0, "space": "tile_offset"},
        "occlusion_hint": {},
        "source_tags": ["generated_place_treatment", place_type, rule_id],
        "place_treatment_rule_id": rule_id,
        "gameplay_affecting": False,
    }


def _rule_matches_place(*, rule: dict[str, Any], place_type: str) -> bool:
    place_types = _string_set(rule.get("place_types"))
    return not place_types or place_type in place_types


def _candidate_positions(
    *,
    place: dict[str, Any],
    mode: str,
    terrain_rows: list[list[str]],
    salt: str,
    rule_id: str,
) -> list[tuple[int, int]]:
    if mode == "center":
        center = _point(place.get("center"))
        return [center] if center is not None else []
    if mode == "entrances":
        return _entrance_positions(place)

    bounds = _bounds(place.get("bounds"), terrain_rows=terrain_rows)
    if bounds is None:
        center = _point(place.get("center"))
        return [center] if center is not None else []

    min_x, min_y, max_x, max_y = bounds
    candidates = [(x, y) for y in range(min_y, max_y + 1) for x in range(min_x, max_x + 1)]
    if mode == "around_center":
        center = _point(place.get("center"))
        if center is not None:
            cx, cy = center
            candidates.sort(
                key=lambda pos: (
                    abs(pos[0] - cx) + abs(pos[1] - cy),
                    _stable_number(salt, rule_id, place.get("id"), pos[0], pos[1]),
                )
            )
            return candidates
    candidates.sort(
        key=lambda pos: _stable_number(salt, rule_id, place.get("id"), pos[0], pos[1])
    )
    return candidates


def _bounds(value: Any, *, terrain_rows: list[list[str]]) -> tuple[int, int, int, int] | None:
    if not isinstance(value, dict):
        return None
    min_x = _int_or_none(value.get("min_x"))
    min_y = _int_or_none(value.get("min_y"))
    max_x = _int_or_none(value.get("max_x"))
    max_y = _int_or_none(value.get("max_y"))
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return None
    if not terrain_rows:
        return None
    width = len(terrain_rows[0])
    height = len(terrain_rows)
    return (
        max(0, min(min_x, width - 1)),
        max(0, min(min_y, height - 1)),
        max(0, min(max_x, width - 1)),
        max(0, min(max_y, height - 1)),
    )


def _entrance_positions(place: dict[str, Any]) -> list[tuple[int, int]]:
    entrances = place.get("entrances")
    if not isinstance(entrances, list):
        return []
    result: list[tuple[int, int]] = []
    for entrance in entrances:
        if not isinstance(entrance, dict):
            continue
        point = _point(entrance.get("position"))
        if point is not None:
            result.append(point)
    return result


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x = _int_or_none(value.get("x"))
    y = _int_or_none(value.get("y"))
    if x is None or y is None:
        return None
    return x, y


def _terrain_at(rows: list[list[str]], x: int, y: int) -> str | None:
    if y < 0 or y >= len(rows):
        return None
    row = rows[y]
    if x < 0 or x >= len(row):
        return None
    return row[x]


def _visual_at(rows: list[list[str]], x: int, y: int) -> str | None:
    if y < 0 or y >= len(rows):
        return None
    row = rows[y]
    if x < 0 or x >= len(row):
        return None
    return row[x]


def _choose_sprite(
    rule: dict[str, Any],
    salt: str,
    place_id: str,
    x: int,
    y: int,
    index: int,
) -> str | None:
    sprites = _string_list(rule.get("sprites"))
    if not sprites:
        sprite = rule.get("sprite_id")
        return sprite if isinstance(sprite, str) and sprite else None
    number = _stable_number(salt, place_id, _string_value(rule.get("id"), "rule"), x, y, index)
    return sprites[number % len(sprites)]


def _place_items(places: dict[str, Any]) -> list[dict[str, Any]]:
    items = places.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Terrain layer must contain non-empty rows")
    result: list[list[str]] = []
    width: int | None = None
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or not all(isinstance(item, str) for item in row):
            raise ValueError(f"Terrain row {row_index} must be a list of strings")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("Terrain rows must have equal width")
        result.append(list(row))
    return result


def _visual_rows(visual_layers: dict[str, Any]) -> list[list[str]]:
    layers = visual_layers.get("layers")
    if not isinstance(layers, list):
        return []
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "terrain_base":
            rows = layer.get("rows")
            if isinstance(rows, list):
                return [[str(item) for item in row] for row in rows if isinstance(row, list)]
    return []


def _rule_items(rules: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = rules.get("rules", [])
    if not isinstance(raw_items, list):
        return []
    result = [item for item in raw_items if isinstance(item, dict)]
    result.sort(key=lambda item: _int_value(item.get("priority"), 100))
    return result


def _draw_layer_order(profile: VisualProfile) -> dict[str, int]:
    raw_order = profile.profile.get("draw_layer_order", {})
    if not isinstance(raw_order, dict):
        return {"terrain": 0, "terrain_overlay": 10, "objects": 20}
    result: dict[str, int] = {}
    for key, value in raw_order.items():
        if isinstance(key, str) and isinstance(value, int):
            result[key] = value
    return result



def _stable_number(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    value = 2166136261
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    return value


def _stable_percent(*parts: object) -> int:
    return _stable_number(*parts) % 100


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _string_set(value: Any) -> set[str]:
    return set(_string_list(value))


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default


def _positive_int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) and value > 0 else default


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default
