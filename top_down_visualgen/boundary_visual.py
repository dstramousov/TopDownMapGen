from __future__ import annotations

from collections import Counter
from typing import Any

from .models import VisualProfile, WorldPackage


class BoundaryVisualMapper:
    """Build visual-only map boundary markers."""

    def map_boundary_visual(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        visual_layers: dict[str, Any],
    ) -> dict[str, Any]:
        """Build visual-only boundary objects around map edges.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            visual_layers: Visual layer data.

        Returns:
            Boundary visual object items and report data.
        """
        rules = profile.boundary_rules
        if rules.get("enabled", True) is False:
            return _empty_result("disabled")

        terrain_rows = _terrain_rows(world.terrain)
        if not terrain_rows:
            return _empty_result("missing_terrain")
        width = len(terrain_rows[0])
        height = len(terrain_rows)
        border_width = max(1, _int_value(rules.get("border_width_tiles"), 1))
        layer_order = _draw_layer_order(profile)
        salt = _string_value(rules.get("seed_salt"), "boundary-visual-v1")

        items: list[dict[str, Any]] = []
        type_counts: Counter[str] = Counter()
        sprite_counts: Counter[str] = Counter()
        edge_counts: Counter[str] = Counter()
        role_counts: Counter[str] = Counter()
        skipped_counts: Counter[str] = Counter()
        occupied: set[tuple[int, int]] = set()

        for y, row in enumerate(terrain_rows):
            if len(row) != width:
                skipped_counts["non_rectangular_terrain_row"] += 1
                continue
            for x, terrain_type in enumerate(row):
                distance = _border_distance(width=width, height=height, x=x, y=y)
                if distance >= border_width:
                    continue
                edge = _edge_name(width=width, height=height, x=x, y=y)
                boundary_type = _boundary_type_for_terrain(terrain_type, x, y, rules, salt)
                boundary_rule = _boundary_type_rule(rules, boundary_type)
                if not boundary_rule:
                    skipped_counts["missing_boundary_type_rule"] += 1
                    continue
                if not _passes_sampling(
                    boundary_rule=boundary_rule,
                    salt=salt,
                    x=x,
                    y=y,
                    distance=distance,
                    boundary_type=boundary_type,
                ):
                    skipped_counts[f"sampled_{boundary_type}"] += 1
                    continue
                if (x, y) in occupied:
                    skipped_counts["occupied"] += 1
                    continue
                sprite_id = _select_sprite(boundary_rule, x, y, salt)
                if sprite_id is None:
                    skipped_counts["missing_sprite"] += 1
                    continue
                occupied.add((x, y))
                item = _build_boundary_item(
                    x=x,
                    y=y,
                    sprite_id=sprite_id,
                    boundary_type=boundary_type,
                    edge=edge,
                    distance=distance,
                    rule=boundary_rule,
                    layer_order=layer_order,
                    stable_index=len(items),
                )
                items.append(item)
                type_counts[boundary_type] += 1
                sprite_counts[sprite_id] += 1
                edge_counts[edge] += 1
                role_counts[_string_value(item.get("visual_role"), "visual")] += 1

        items.sort(key=lambda item: item["sort_key"])
        blocking_skipped = _blocking_skipped_counts(skipped_counts)
        sampled_skipped = _sampled_skipped_counts(skipped_counts)
        return {
            "items": items,
            "report": {
                "schema_version": "visual-debug-boundary-visual-report-v1",
                "kind": "visual_debug_boundary_visual_report",
                "source_layer": "map_border",
                "rules_enabled": True,
                "summary": {
                    "total": len(items),
                    "map_width": width,
                    "map_height": height,
                    "border_width_tiles": border_width,
                    "by_boundary_type": dict(sorted(type_counts.items())),
                    "by_sprite_id": dict(sorted(sprite_counts.items())),
                    "by_edge": dict(sorted(edge_counts.items())),
                    "by_role": dict(sorted(role_counts.items())),
                    "failed_placements": dict(sorted(blocking_skipped.items())),
                    "sampled_markers": dict(sorted(sampled_skipped.items())),
                },
                "quality": {
                    "status": "ok" if not blocking_skipped else "has_skipped_markers",
                },
            },
        }


def _build_boundary_item(
    *,
    x: int,
    y: int,
    sprite_id: str,
    boundary_type: str,
    edge: str,
    distance: int,
    rule: dict[str, Any],
    layer_order: dict[str, int],
    stable_index: int,
) -> dict[str, Any]:
    draw_layer = _string_value(rule.get("draw_layer"), "above_actor")
    layer_rank = layer_order.get(draw_layer, layer_order.get("above_actor", 50))
    visual_role = _string_value(rule.get("role"), "boundary_hint")
    sort_anchor = {
        "x": x,
        "y": y,
        "elevation": 4 if boundary_type in {"cliff_wall", "dark_tree_wall"} else 0,
        "space": "tile",
        "rule": "y_then_elevation_then_x",
    }
    return {
        "id": f"visual_boundary_{stable_index:05d}",
        "source_object_id": f"boundary_{edge}_{x}_{y}",
        "source_object_type": "visual_boundary",
        "sprite_id": sprite_id,
        "draw_layer": draw_layer,
        "position": {"x": x, "y": y},
        "sort_anchor": sort_anchor,
        "sort_key": [layer_rank, y, sort_anchor["elevation"], x, stable_index],
        "visual_bounds": {"x": x, "y": y, "width": 1, "height": 1},
        "pivot": {"x": 0, "y": 0, "space": "tile_offset"},
        "occlusion_hint": {"blocks_view_beyond_map": True},
        "source_tags": [
            "generated_boundary_visual",
            boundary_type,
            f"edge:{edge}",
            f"border_distance:{distance}",
        ],
        "boundary_visual_type": boundary_type,
        "boundary_edge": edge,
        "visual_role": visual_role,
        "gameplay_affecting": False,
    }


def _passes_sampling(
    *,
    boundary_rule: dict[str, Any],
    salt: str,
    x: int,
    y: int,
    distance: int,
    boundary_type: str,
) -> bool:
    stride = max(1, _int_value(boundary_rule.get("stride"), 2))
    inner_stride = max(stride, _int_value(boundary_rule.get("inner_stride"), stride + 1))
    effective_stride = stride if distance == 0 else inner_stride
    value = _stable_int(salt, boundary_type, x, y, distance)
    if value % effective_stride != 0:
        return False
    chance = _int_value(
        boundary_rule.get("chance_percent" if distance == 0 else "inner_chance_percent"),
        100 if distance == 0 else 35,
    )
    if chance >= 100:
        return True
    return value % 100 < max(0, chance)


def _select_sprite(rule: dict[str, Any], x: int, y: int, salt: str) -> str | None:
    raw = rule.get("sprites")
    sprites = [item for item in raw if isinstance(item, str) and item] if isinstance(raw, list) else []
    if not sprites:
        sprite = rule.get("sprite_id")
        if isinstance(sprite, str) and sprite:
            sprites = [sprite]
    if not sprites:
        return None
    return sprites[_stable_int(salt, "sprite", x, y, len(sprites)) % len(sprites)]


def _boundary_type_for_terrain(
    terrain_type: str,
    x: int,
    y: int,
    rules: dict[str, Any],
    salt: str,
) -> str:
    base_type = _base_boundary_type_for_terrain(terrain_type, x, y, rules)
    return _varied_boundary_type(base_type, x, y, rules, salt)


def _base_boundary_type_for_terrain(
    terrain_type: str,
    x: int,
    y: int,
    rules: dict[str, Any],
) -> str:
    terrain_map = rules.get("terrain_type_to_boundary")
    if isinstance(terrain_map, dict):
        mapped = terrain_map.get(terrain_type)
        if isinstance(mapped, str) and mapped:
            return mapped
    lower = terrain_type.lower()
    if "ruin" in lower or "wall" in lower:
        return "ruin_barrier"
    if "water" in lower or "swamp" in lower:
        return "swamp_barrier"
    if "concrete" in lower or "bunker" in lower:
        return "concrete_barrier"
    if "tree" in lower or "forest" in lower or "bush" in lower:
        return "dense_forest_wall" if (x + y) % 3 else "dark_tree_wall"
    if "road" in lower:
        return "dark_tree_wall"
    return "dense_forest_wall"


def _varied_boundary_type(
    base_type: str,
    x: int,
    y: int,
    rules: dict[str, Any],
    salt: str,
) -> str:
    variation_policy = rules.get("variation_policy")
    if isinstance(variation_policy, dict) and variation_policy.get("enabled") is False:
        return base_type
    variants_by_type = rules.get("boundary_type_variants")
    if not isinstance(variants_by_type, dict):
        return base_type
    raw_variants = variants_by_type.get(base_type)
    if not isinstance(raw_variants, list):
        return base_type
    weighted: list[tuple[str, int]] = []
    for item in raw_variants:
        if not isinstance(item, dict):
            continue
        variant_type = item.get("type")
        weight = item.get("weight")
        if (
            isinstance(variant_type, str)
            and variant_type
            and isinstance(weight, int)
            and weight > 0
        ):
            weighted.append((variant_type, weight))
    if not weighted:
        return base_type
    total_weight = sum(weight for _, weight in weighted)
    roll = _stable_int(salt, "boundary_type_variant", base_type, x, y) % total_weight
    cursor = 0
    for variant_type, weight in weighted:
        cursor += weight
        if roll < cursor:
            return variant_type
    return base_type


def _boundary_type_rule(rules: dict[str, Any], boundary_type: str) -> dict[str, Any]:
    raw_types = rules.get("boundary_types")
    if isinstance(raw_types, dict):
        rule = raw_types.get(boundary_type)
        if isinstance(rule, dict):
            return rule
        fallback = raw_types.get("dense_forest_wall")
        if isinstance(fallback, dict):
            return fallback
    return {}


def _border_distance(*, width: int, height: int, x: int, y: int) -> int:
    return min(x, y, width - 1 - x, height - 1 - y)


def _edge_name(*, width: int, height: int, x: int, y: int) -> str:
    distances = {
        "north": y,
        "south": height - 1 - y,
        "west": x,
        "east": width - 1 - x,
    }
    return min(distances.items(), key=lambda item: item[1])[0]


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list):
        return []
    result: list[list[str]] = []
    for row in rows:
        if isinstance(row, list):
            result.append([str(item) for item in row])
    return result


def _draw_layer_order(profile: VisualProfile) -> dict[str, int]:
    raw_order = profile.profile.get("draw_layer_order", {})
    if not isinstance(raw_order, dict):
        return {"terrain": 0, "terrain_overlay": 10, "objects": 30, "above_actor": 50}
    return {key: value for key, value in raw_order.items() if isinstance(key, str) and isinstance(value, int)}


def _blocking_skipped_counts(skipped_counts: Counter[str]) -> Counter[str]:
    return Counter(
        {
            key: value
            for key, value in skipped_counts.items()
            if not key.startswith("sampled_") and value > 0
        }
    )


def _sampled_skipped_counts(skipped_counts: Counter[str]) -> Counter[str]:
    return Counter(
        {
            key.removeprefix("sampled_"): value
            for key, value in skipped_counts.items()
            if key.startswith("sampled_") and value > 0
        }
    )


def _empty_result(status: str) -> dict[str, Any]:
    return {
        "items": [],
        "report": {
            "schema_version": "visual-debug-boundary-visual-report-v1",
            "kind": "visual_debug_boundary_visual_report",
            "source_layer": "map_border",
            "rules_enabled": status != "disabled",
            "summary": {
                "total": 0,
                "by_boundary_type": {},
                "by_sprite_id": {},
                "by_edge": {},
                "by_role": {},
                "failed_placements": {},
                "sampled_markers": {},
            },
            "quality": {"status": status},
        },
    }


def _stable_int(*parts: Any) -> int:
    value = 2166136261
    for part in parts:
        for char in str(part):
            value ^= ord(char)
            value = (value * 16777619) & 0xFFFFFFFF
    return value


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default
