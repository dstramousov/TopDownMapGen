from __future__ import annotations

from collections import Counter
from typing import Any

from .models import VisualProfile, WorldPackage


class ForestOverlayMapper:
    """Build large visual-only forest overlay sprites from forest terrain masks."""

    def map_forest_overlays(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        visual_layers: dict[str, Any],
    ) -> dict[str, Any]:
        """Build forest overlay sprites without changing gameplay.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            visual_layers: Generated visual layer data.

        Returns:
            Forest overlay items and debug report data.
        """
        rules = profile.forest_overlay_rules
        if rules.get("enabled", True) is False:
            return _empty_result("disabled")

        terrain_rows = _terrain_rows(world.terrain)
        if not terrain_rows:
            return _empty_result("missing_terrain")
        width = len(terrain_rows[0])
        height = len(terrain_rows)
        terrain_types = _string_set(rules.get("terrain_types")) or {"forest"}
        layer_order = _draw_layer_order(profile)
        salt = _string_value(rules.get("seed_salt"), "forest-overlay-v1")
        cluster_rules = _rule_group(rules.get("clusters"))
        edge_rules = _rule_group(rules.get("edges"))

        items: list[dict[str, Any]] = []
        occupied: set[tuple[int, int]] = set()
        sprite_counts: Counter[str] = Counter()
        kind_counts: Counter[str] = Counter()
        edge_counts: Counter[str] = Counter()
        skipped_counts: Counter[str] = Counter()

        if cluster_rules.get("enabled", True):
            for y, row in enumerate(terrain_rows):
                if len(row) != width:
                    skipped_counts["non_rectangular_terrain_row"] += 1
                    continue
                for x, terrain_type in enumerate(row):
                    if terrain_type not in terrain_types:
                        continue
                    if not _has_forest_neighborhood(
                        rows=terrain_rows,
                        x=x,
                        y=y,
                        terrain_types=terrain_types,
                        radius=max(0, _int_value(cluster_rules.get("min_inner_radius"), 1)),
                    ):
                        skipped_counts["cluster_not_inner_forest"] += 1
                        continue
                    if not _passes_sampling(
                        rule=cluster_rules,
                        salt=salt,
                        x=x,
                        y=y,
                        marker_kind="cluster",
                    ):
                        skipped_counts["sampled_cluster"] += 1
                        continue
                    spacing = max(1, _int_value(cluster_rules.get("min_spacing_tiles"), 4))
                    if _near_occupied(occupied, x=x, y=y, radius=spacing):
                        skipped_counts["cluster_spacing"] += 1
                        continue
                    sprite_id = _select_sprite(cluster_rules, salt, x, y, "cluster")
                    if sprite_id is None:
                        skipped_counts["missing_cluster_sprite"] += 1
                        continue
                    occupied.add((x, y))
                    item = _build_forest_item(
                        x=x,
                        y=y,
                        sprite_id=sprite_id,
                        marker_kind="cluster",
                        edge="inner",
                        rule=cluster_rules,
                        layer_order=layer_order,
                        stable_index=len(items),
                    )
                    items.append(item)
                    sprite_counts[sprite_id] += 1
                    kind_counts["cluster"] += 1

        if edge_rules.get("enabled", True):
            for y, row in enumerate(terrain_rows):
                if len(row) != width:
                    continue
                for x, terrain_type in enumerate(row):
                    if terrain_type not in terrain_types:
                        continue
                    edge = _forest_edge_direction(
                        rows=terrain_rows,
                        x=x,
                        y=y,
                        terrain_types=terrain_types,
                    )
                    if edge is None:
                        skipped_counts["edge_not_boundary"] += 1
                        continue
                    if not _passes_sampling(
                        rule=edge_rules,
                        salt=salt,
                        x=x,
                        y=y,
                        marker_kind=f"edge_{edge}",
                    ):
                        skipped_counts[f"sampled_edge_{edge}"] += 1
                        continue
                    spacing = max(1, _int_value(edge_rules.get("min_spacing_tiles"), 3))
                    if _near_occupied(occupied, x=x, y=y, radius=spacing):
                        skipped_counts["edge_spacing"] += 1
                        continue
                    sprite_id = _select_edge_sprite(edge_rules, edge, salt, x, y)
                    if sprite_id is None:
                        skipped_counts[f"missing_edge_{edge}_sprite"] += 1
                        continue
                    occupied.add((x, y))
                    item = _build_forest_item(
                        x=x,
                        y=y,
                        sprite_id=sprite_id,
                        marker_kind="edge",
                        edge=edge,
                        rule=edge_rules,
                        layer_order=layer_order,
                        stable_index=len(items),
                    )
                    items.append(item)
                    sprite_counts[sprite_id] += 1
                    kind_counts["edge"] += 1
                    edge_counts[edge] += 1

        items.sort(key=lambda item: item["sort_key"])
        blocking_skipped = _blocking_skipped_counts(skipped_counts)
        sampled_skipped = _sampled_skipped_counts(skipped_counts)
        return {
            "items": items,
            "report": {
                "schema_version": "visual-debug-forest-overlay-report-v1",
                "kind": "visual_debug_forest_overlay_report",
                "source_layer": "map_package.layers.terrain",
                "rules_enabled": True,
                "summary": {
                    "total": len(items),
                    "map_width": width,
                    "map_height": height,
                    "by_kind": dict(sorted(kind_counts.items())),
                    "by_edge": dict(sorted(edge_counts.items())),
                    "by_sprite_id": dict(sorted(sprite_counts.items())),
                    "failed_placements": dict(sorted(blocking_skipped.items())),
                    "sampled_markers": dict(sorted(sampled_skipped.items())),
                },
                "quality": {
                    "status": "ok" if not blocking_skipped else "has_skipped_markers",
                },
            },
        }


def _build_forest_item(
    *,
    x: int,
    y: int,
    sprite_id: str,
    marker_kind: str,
    edge: str,
    rule: dict[str, Any],
    layer_order: dict[str, int],
    stable_index: int,
) -> dict[str, Any]:
    draw_layer = _string_value(rule.get("draw_layer"), "above_actor")
    layer_rank = layer_order.get(draw_layer, layer_order.get("above_actor", 50))
    elevation = _int_value(rule.get("sort_elevation"), 2)
    sort_anchor = {
        "x": x,
        "y": y,
        "elevation": elevation,
        "space": "tile",
        "rule": "y_then_elevation_then_x",
    }
    return {
        "id": f"visual_forest_overlay_{stable_index:05d}",
        "source_object_id": f"forest_overlay_{marker_kind}_{edge}_{x}_{y}",
        "source_object_type": "visual_forest_overlay",
        "sprite_id": sprite_id,
        "draw_layer": draw_layer,
        "position": {"x": x, "y": y},
        "sort_anchor": sort_anchor,
        "sort_key": [layer_rank, y, elevation, x, stable_index],
        "visual_bounds": {"x": x, "y": y, "width": 3, "height": 3},
        "pivot": {"x": 0, "y": 0, "space": "tile_offset"},
        "occlusion_hint": {"forest_canopy_overlay": True},
        "source_tags": ["generated_forest_overlay", marker_kind, f"edge:{edge}"],
        "forest_overlay_kind": marker_kind,
        "forest_overlay_edge": edge,
        "visual_role": _string_value(rule.get("role"), "canopy_mass"),
        "gameplay_affecting": False,
    }


def _has_forest_neighborhood(
    *,
    rows: list[list[str]],
    x: int,
    y: int,
    terrain_types: set[str],
    radius: int,
) -> bool:
    if radius <= 0:
        return True
    height = len(rows)
    width = len(rows[0]) if rows else 0
    for ny in range(y - radius, y + radius + 1):
        if ny < 0 or ny >= height:
            return False
        for nx in range(x - radius, x + radius + 1):
            if nx < 0 or nx >= width:
                return False
            if rows[ny][nx] not in terrain_types:
                return False
    return True


def _forest_edge_direction(
    *,
    rows: list[list[str]],
    x: int,
    y: int,
    terrain_types: set[str],
) -> str | None:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    checks = (
        ("n", x, y - 1),
        ("s", x, y + 1),
        ("e", x + 1, y),
        ("w", x - 1, y),
    )
    candidates: list[str] = []
    for edge, nx, ny in checks:
        if nx < 0 or nx >= width or ny < 0 or ny >= height:
            candidates.append(edge)
        elif rows[ny][nx] not in terrain_types:
            candidates.append(edge)
    if not candidates:
        return None
    return candidates[_stable_int("forest-edge", x, y, len(candidates)) % len(candidates)]


def _near_occupied(occupied: set[tuple[int, int]], *, x: int, y: int, radius: int) -> bool:
    for ox, oy in occupied:
        if abs(ox - x) <= radius and abs(oy - y) <= radius:
            return True
    return False


def _passes_sampling(*, rule: dict[str, Any], salt: str, x: int, y: int, marker_kind: str) -> bool:
    stride = max(1, _int_value(rule.get("stride"), 4))
    if _stable_int(salt, marker_kind, "stride", x, y) % stride != 0:
        return False
    chance = _int_value(rule.get("chance_percent"), 100)
    if chance >= 100:
        return True
    return _stable_int(salt, marker_kind, "chance", x, y) % 100 < max(0, chance)


def _select_sprite(rule: dict[str, Any], salt: str, x: int, y: int, marker_kind: str) -> str | None:
    sprites = _string_list(rule.get("sprites"))
    if not sprites:
        return None
    return sprites[_stable_int(salt, marker_kind, "sprite", x, y) % len(sprites)]


def _select_edge_sprite(rule: dict[str, Any], edge: str, salt: str, x: int, y: int) -> str | None:
    by_edge = rule.get("sprites_by_edge")
    sprites: list[str] = []
    if isinstance(by_edge, dict):
        sprites = _string_list(by_edge.get(edge))
    if not sprites:
        sprites = _string_list(rule.get("sprites"))
    if not sprites:
        return None
    return sprites[_stable_int(salt, edge, "sprite", x, y) % len(sprites)]


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list) or not rows:
        return []
    result: list[list[str]] = []
    width: int | None = None
    for row in rows:
        if not isinstance(row, list) or not all(isinstance(item, str) for item in row):
            return []
        if width is None:
            width = len(row)
        elif len(row) != width:
            return []
        result.append(list(row))
    return result


def _rule_group(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _draw_layer_order(profile: VisualProfile) -> dict[str, int]:
    raw = profile.profile.get("draw_layer_order", {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items() if isinstance(value, int)}


def _blocking_skipped_counts(counts: Counter[str]) -> dict[str, int]:
    return {
        key: value
        for key, value in counts.items()
        if value > 0 and not key.startswith("sampled_") and key not in {"cluster_not_inner_forest", "edge_not_boundary", "cluster_spacing", "edge_spacing"}
    }


def _sampled_skipped_counts(counts: Counter[str]) -> dict[str, int]:
    return {key: value for key, value in counts.items() if value > 0 and key.startswith("sampled_")}


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _int_value(value: Any, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _stable_int(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) & 0xFFFFFFFF
    return value


def _empty_result(reason: str) -> dict[str, Any]:
    return {
        "items": [],
        "report": {
            "schema_version": "visual-debug-forest-overlay-report-v1",
            "kind": "visual_debug_forest_overlay_report",
            "source_layer": "map_package.layers.terrain",
            "rules_enabled": reason != "disabled",
            "summary": {
                "total": 0,
                "by_kind": {},
                "by_edge": {},
                "by_sprite_id": {},
                "failed_placements": {reason: 1},
                "sampled_markers": {},
            },
            "quality": {"status": reason},
        },
    }
