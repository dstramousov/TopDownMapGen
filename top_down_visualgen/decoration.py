from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from .models import VisualProfile, WorldPackage


class DecorationMapper:
    """Build non-gameplay visual decorations from terrain context."""

    def map_decorations(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        visual_layers: dict[str, Any],
        visual_debug: dict[str, Any],
    ) -> dict[str, Any]:
        """Build deterministic visual decoration objects.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            visual_layers: Visual layer data.
            visual_debug: Visual debug data extracted from terrain mapping.

        Returns:
            Decoration object items and report data.
        """
        rules = profile.decoration_rules
        if rules.get("enabled") is not True:
            return _empty_result()

        terrain_rows = _terrain_rows(world.terrain)
        visual_rows = _visual_rows(visual_layers)
        autotile_rows = _autotile_rows(visual_debug.get("autotile_masks"))
        blocked_terrain = _string_set(rules.get("blocked_terrain"))
        rule_items = _rule_items(rules)
        layer_order = _draw_layer_order(profile)
        salt = _string_value(rules.get("seed_salt"), "visual-decoration-v1")

        items: list[dict[str, Any]] = []
        rule_counts: Counter[str] = Counter()
        sprite_counts: Counter[str] = Counter()
        skipped_counts: Counter[str] = Counter()
        height = len(terrain_rows)
        width = len(terrain_rows[0]) if terrain_rows else 0

        for y in range(height):
            for x in range(width):
                terrain_type = terrain_rows[y][x]
                if terrain_type in blocked_terrain:
                    skipped_counts["blocked_terrain"] += 1
                    continue
                autotile_info = _autotile_info_at(autotile_rows, x, y)
                visual_tile = visual_rows[y][x] if y < len(visual_rows) and x < len(visual_rows[y]) else ""
                for rule in rule_items:
                    if not _rule_matches(
                        rule=rule,
                        terrain_type=terrain_type,
                        visual_tile=visual_tile,
                        autotile_info=autotile_info,
                        autotile_rows=autotile_rows,
                        x=x,
                        y=y,
                    ):
                        continue
                    chance = _int_value(rule.get("chance_percent"), 0)
                    if chance <= 0:
                        skipped_counts["chance_zero"] += 1
                        continue
                    roll = _stable_percent(salt, x, y, _string_value(rule.get("id"), "rule"))
                    if roll >= min(chance, 100):
                        skipped_counts["chance_miss"] += 1
                        continue
                    sprite_id = _choose_sprite(rule, salt, x, y)
                    if sprite_id is None:
                        skipped_counts["missing_sprite"] += 1
                        continue
                    item = _build_decoration_item(
                        x=x,
                        y=y,
                        sprite_id=sprite_id,
                        rule=rule,
                        layer_order=layer_order,
                        stable_index=len(items),
                    )
                    items.append(item)
                    rule_counts[_string_value(rule.get("id"), "unknown")] += 1
                    sprite_counts[sprite_id] += 1
                    break

        items.sort(key=lambda item: item["sort_key"])
        return {
            "items": items,
            "report": {
                "schema_version": "visual-debug-decoration-report-v1",
                "kind": "visual_debug_decoration_report",
                "source_layer": "terrain_base",
                "rules_enabled": True,
                "summary": {
                    "total": len(items),
                    "by_rule": dict(sorted(rule_counts.items())),
                    "by_sprite_id": dict(sorted(sprite_counts.items())),
                    "skipped": dict(sorted(skipped_counts.items())),
                },
                "quality": {
                    "status": "ok",
                },
            },
        }


def merge_visual_objects(
    *,
    runtime_visual_objects: dict[str, Any],
    decoration_result: dict[str, Any],
) -> dict[str, Any]:
    """Merge runtime visual objects with generated decorations.

    Args:
        runtime_visual_objects: Object records from runtime world objects.
        decoration_result: Decoration mapper output.

    Returns:
        Combined visual objects JSON object.
    """
    runtime_items = runtime_visual_objects.get("items", [])
    if not isinstance(runtime_items, list):
        runtime_items = []
    decoration_items = decoration_result.get("items", [])
    if not isinstance(decoration_items, list):
        decoration_items = []
    items = [item for item in [*runtime_items, *decoration_items] if isinstance(item, dict)]
    items.sort(key=lambda item: item.get("sort_key", []))
    return {
        "schema_version": "visual-objects-v2",
        "kind": "visual_objects",
        "coordinate_space": "tile",
        "items": items,
        "summary": {
            "total": len(items),
            "runtime_total": len(runtime_items),
            "decoration_total": len(decoration_items),
            "by_draw_layer": _count_by(items, "draw_layer"),
            "by_sprite_id": _count_by(items, "sprite_id"),
        },
    }


def _empty_result() -> dict[str, Any]:
    return {
        "items": [],
        "report": {
            "schema_version": "visual-debug-decoration-report-v1",
            "kind": "visual_debug_decoration_report",
            "source_layer": "terrain_base",
            "rules_enabled": False,
            "summary": {
                "total": 0,
                "by_rule": {},
                "by_sprite_id": {},
                "skipped": {},
            },
            "quality": {"status": "disabled"},
        },
    }


def _build_decoration_item(
    *,
    x: int,
    y: int,
    sprite_id: str,
    rule: dict[str, Any],
    layer_order: dict[str, int],
    stable_index: int,
) -> dict[str, Any]:
    rule_id = _string_value(rule.get("id"), "decoration")
    draw_layer = _string_value(rule.get("draw_layer"), "terrain_overlay")
    layer_rank = layer_order.get(draw_layer, layer_order.get("terrain_overlay", 10))
    sort_anchor = {
        "x": x,
        "y": y,
        "elevation": 0,
        "space": "tile",
        "rule": "y_then_elevation_then_x",
    }
    return {
        "id": f"visual_decor_{stable_index:05d}",
        "source_object_id": None,
        "source_object_type": "visual_decoration",
        "sprite_id": sprite_id,
        "draw_layer": draw_layer,
        "position": {"x": x, "y": y},
        "sort_anchor": sort_anchor,
        "sort_key": [layer_rank, y, 0, x, stable_index],
        "visual_bounds": {"x": x, "y": y, "width": 1, "height": 1},
        "pivot": {"x": 0, "y": 0, "space": "tile_offset"},
        "occlusion_hint": {},
        "source_tags": ["generated_decoration", rule_id],
        "decoration_rule_id": rule_id,
        "gameplay_affecting": False,
    }


def _rule_matches(
    *,
    rule: dict[str, Any],
    terrain_type: str,
    visual_tile: str,
    autotile_info: dict[str, Any] | None,
    autotile_rows: Sequence[Sequence[dict[str, Any] | None]],
    x: int,
    y: int,
) -> bool:
    terrain_types = _string_set(rule.get("terrain_types"))
    if terrain_types and terrain_type not in terrain_types:
        return False

    visual_tiles = _string_set(rule.get("visual_tiles"))
    if visual_tiles and visual_tile not in visual_tiles:
        return False

    groups = _string_set(rule.get("autotile_groups"))
    if groups:
        if autotile_info is None or autotile_info.get("group") not in groups:
            return False

    variants = _string_set(rule.get("variants"))
    if variants:
        if autotile_info is None or autotile_info.get("variant") not in variants:
            return False

    variant_prefixes = _string_list(rule.get("variant_prefixes"))
    if variant_prefixes:
        variant = "" if autotile_info is None else _string_value(autotile_info.get("variant"), "")
        if not any(variant.startswith(prefix) for prefix in variant_prefixes):
            return False

    nearby_groups = _string_set(rule.get("nearby_autotile_groups"))
    if nearby_groups:
        radius = _positive_int_value(rule.get("nearby_radius"), 1)
        if not _has_nearby_autotile_group(
            rows=autotile_rows,
            x=x,
            y=y,
            radius=radius,
            groups=nearby_groups,
        ):
            return False

    return True


def _has_nearby_autotile_group(
    *,
    rows: Sequence[Sequence[dict[str, Any] | None]],
    x: int,
    y: int,
    radius: int,
    groups: set[str],
) -> bool:
    if radius <= 0:
        return False
    y_min = max(0, y - radius)
    y_max = min(len(rows) - 1, y + radius)
    for ny in range(y_min, y_max + 1):
        row = rows[ny]
        x_min = max(0, x - radius)
        x_max = min(len(row) - 1, x + radius)
        for nx in range(x_min, x_max + 1):
            if nx == x and ny == y:
                continue
            info = row[nx]
            if isinstance(info, dict) and info.get("group") in groups:
                return True
    return False


def _choose_sprite(rule: dict[str, Any], salt: str, x: int, y: int) -> str | None:
    sprites = _string_list(rule.get("sprites"))
    if not sprites:
        sprite = rule.get("sprite_id")
        return sprite if isinstance(sprite, str) and sprite else None
    index = _stable_number(salt, x, y, _string_value(rule.get("id"), "rule"), "sprite")
    return sprites[index % len(sprites)]


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


def _autotile_rows(value: Any) -> list[list[dict[str, Any] | None]]:
    if not isinstance(value, list):
        return []
    result: list[list[dict[str, Any] | None]] = []
    for row in value:
        if not isinstance(row, list):
            continue
        result.append([item if isinstance(item, dict) else None for item in row])
    return result


def _autotile_info_at(
    rows: Sequence[Sequence[dict[str, Any] | None]],
    x: int,
    y: int,
) -> dict[str, Any] | None:
    if y < 0 or y >= len(rows):
        return None
    row = rows[y]
    if x < 0 or x >= len(row):
        return None
    value = row[x]
    return value if isinstance(value, dict) else None


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


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        value = item.get(key)
        if isinstance(value, str):
            counts[value] += 1
    return dict(sorted(counts.items()))


def _stable_percent(*parts: object) -> int:
    return _stable_number(*parts) % 100


def _stable_number(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    value = 2166136261
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    return value


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


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default
