from __future__ import annotations

from collections import Counter
from typing import Any

from .models import VisualProfile, WorldPackage


class ElevationVisualMapper:
    """Build non-gameplay visual markers for elevation data."""

    def map_elevation_visual(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        visual_layers: dict[str, Any],
    ) -> dict[str, Any]:
        """Build visual-only elevation marker objects.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            visual_layers: Visual layer data.

        Returns:
            Elevation visual object items and report data.
        """
        rules = profile.elevation_rules
        if rules.get("enabled", True) is False:
            return _empty_result("disabled")

        height_rows = _height_rows(world)
        if not height_rows:
            return _empty_result("missing_height_grid")

        terrain_rows = _terrain_rows(world.terrain)
        width = len(height_rows[0]) if height_rows else 0
        height = len(height_rows)
        layer_order = _draw_layer_order(profile)

        items: list[dict[str, Any]] = []
        level_counts: Counter[str] = Counter()
        marker_counts: Counter[str] = Counter()
        role_counts: Counter[str] = Counter()
        sprite_counts: Counter[str] = Counter()
        skipped_counts: Counter[str] = Counter()
        occupied: set[tuple[int, int, str]] = set()

        for y, row in enumerate(height_rows):
            if len(row) != width:
                skipped_counts["non_rectangular_height_row"] += 1
                continue
            for x, level in enumerate(row):
                if not isinstance(level, int):
                    skipped_counts["non_integer_height"] += 1
                    continue
                level_counts[str(level)] += 1
                if level == 0:
                    continue
                terrain_type = _terrain_at(terrain_rows, x, y)
                item = _build_level_marker(
                    x=x,
                    y=y,
                    level=level,
                    terrain_type=terrain_type,
                    rules=rules,
                    layer_order=layer_order,
                    stable_index=len(items),
                )
                if item is None:
                    skipped_counts["missing_level_rule"] += 1
                    continue
                key = (x, y, _string_value(item.get("elevation_visual_kind"), "level"))
                if key in occupied:
                    skipped_counts["occupied"] += 1
                    continue
                occupied.add(key)
                items.append(item)
                marker_counts[_string_value(item.get("elevation_visual_kind"), "level")] += 1
                role_counts[_string_value(item.get("visual_role"), "visual")] += 1
                sprite_counts[_string_value(item.get("sprite_id"), "unknown")] += 1

        transition_items, transition_skipped = _build_transition_markers(
            world=world,
            rules=rules,
            height_rows=height_rows,
            layer_order=layer_order,
            stable_index_start=len(items),
            occupied=occupied,
        )
        items.extend(transition_items)
        skipped_counts.update(transition_skipped)
        for item in transition_items:
            marker_counts[_string_value(item.get("elevation_visual_kind"), "transition")] += 1
            role_counts[_string_value(item.get("visual_role"), "transition_hint")] += 1
            sprite_counts[_string_value(item.get("sprite_id"), "unknown")] += 1

        items.sort(key=lambda item: item["sort_key"])
        return {
            "items": items,
            "report": {
                "schema_version": "visual-debug-elevation-visual-report-v1",
                "kind": "visual_debug_elevation_visual_report",
                "source_layer": "runtime_grids.height_grid",
                "rules_enabled": True,
                "summary": {
                    "total": len(items),
                    "map_width": width,
                    "map_height": height,
                    "level_counts": dict(sorted(level_counts.items(), key=lambda item: int(item[0]))),
                    "lowland_markers": marker_counts.get("lowland", 0),
                    "raised_markers": marker_counts.get("raised", 0),
                    "platform_markers": marker_counts.get("platform", 0),
                    "high_point_markers": marker_counts.get("high_point", 0),
                    "landmark_markers": marker_counts.get("landmark", 0),
                    "transition_markers": marker_counts.get("transition", 0),
                    "by_kind": dict(sorted(marker_counts.items())),
                    "by_role": dict(sorted(role_counts.items())),
                    "by_sprite_id": dict(sorted(sprite_counts.items())),
                    "failed_placements": dict(sorted(skipped_counts.items())),
                },
                "quality": {
                    "status": "ok" if not skipped_counts else "has_skipped_markers",
                },
            },
        }


def _build_level_marker(
    *,
    x: int,
    y: int,
    level: int,
    terrain_type: str,
    rules: dict[str, Any],
    layer_order: dict[str, int],
    stable_index: int,
) -> dict[str, Any] | None:
    level_rules = rules.get("levels")
    if not isinstance(level_rules, dict):
        return None
    rule = level_rules.get(str(level))
    if not isinstance(rule, dict):
        return None

    if level < 0:
        kind = "lowland"
    elif level == 1:
        kind = "raised"
    elif level == 2:
        kind = "platform"
    elif level == 3:
        kind = "high_point"
    else:
        kind = "landmark"

    pool = _object_pool(rule)
    if not pool:
        return None
    selected = _select_level_pool_item(pool, terrain_type, level, x, y)
    return _build_visual_item(
        x=x,
        y=y,
        elevation=level,
        sprite_id=_string_value(selected.get("sprite_id"), "elevation.unknown"),
        visual_role=_string_value(selected.get("role"), "visual"),
        kind=kind,
        source_id=f"level_{level}_{x}_{y}",
        layer_order=layer_order,
        stable_index=stable_index,
        extra_tags=[f"level:{level}", f"terrain:{terrain_type}"],
    )


def _select_level_pool_item(
    pool: list[dict[str, Any]],
    terrain_type: str,
    level: int,
    x: int,
    y: int,
) -> dict[str, Any]:
    if level < 0:
        if "swamp" in terrain_type or "water" in terrain_type:
            preferred = _first_with_sprite(pool, {"elevation.mud_pool", "elevation.water_seep"})
            if preferred is not None:
                return preferred
        if "bunker" in terrain_type:
            preferred = _first_with_sprite(pool, {"elevation.bunker_floor_dark"})
            if preferred is not None:
                return preferred
        if "trench" in terrain_type:
            preferred = _first_with_sprite(pool, {"elevation.trench_wall_edge"})
            if preferred is not None:
                return preferred
    if level >= 2 and ("road" in terrain_type or "bridge" in terrain_type):
        preferred = _first_with_sprite(pool, {"elevation.wooden_bridge_deck", "elevation.old_planks"})
        if preferred is not None:
            return preferred
    index = abs((x * 73856093) ^ (y * 19349663) ^ (level * 83492791)) % len(pool)
    return pool[index]


def _first_with_sprite(pool: list[dict[str, Any]], sprites: set[str]) -> dict[str, Any] | None:
    for item in pool:
        if _string_value(item.get("sprite_id"), "") in sprites:
            return item
    return None


def _build_transition_markers(
    *,
    world: WorldPackage,
    rules: dict[str, Any],
    height_rows: list[list[int]],
    layer_order: dict[str, int],
    stable_index_start: int,
    occupied: set[tuple[int, int, str]],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    transition_rules = rules.get("transitions")
    if not isinstance(transition_rules, dict):
        transition_rules = {}
    items: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for raw_index, raw_item in enumerate(_transition_items(world)):
        if not isinstance(raw_item, dict):
            skipped["malformed_transition"] += 1
            continue
        x, y = _transition_position(raw_item)
        if not _inside(height_rows, x, y):
            skipped["transition_out_of_bounds"] += 1
            continue
        transition_type = _transition_type(raw_item)
        sprite_id = _transition_sprite(transition_rules, transition_type, raw_index)
        if sprite_id is None:
            skipped["missing_transition_rule"] += 1
            continue
        key = (x, y, "transition")
        if key in occupied:
            continue
        occupied.add(key)
        level = height_rows[y][x]
        items.append(
            _build_visual_item(
                x=x,
                y=y,
                elevation=level,
                sprite_id=sprite_id,
                visual_role="transition_hint",
                kind="transition",
                source_id=_string_value(raw_item.get("id"), f"transition_{raw_index}"),
                layer_order=layer_order,
                stable_index=stable_index_start + len(items),
                extra_tags=[f"transition:{transition_type}"],
            )
        )
    return items, skipped


def _transition_items(world: WorldPackage) -> list[Any]:
    items = world.elevation_transitions.get("items")
    if isinstance(items, list):
        return items
    items = world.elevation_model.get("transitions")
    return items if isinstance(items, list) else []


def _transition_position(raw_item: dict[str, Any]) -> tuple[int, int]:
    for key in ("position", "tile", "from", "start", "a"):
        value = raw_item.get(key)
        parsed = _position_from_value(value)
        if parsed is not None:
            return parsed
    parsed = _position_from_value(raw_item)
    return parsed if parsed is not None else (-1, -1)


def _position_from_value(value: Any) -> tuple[int, int] | None:
    if isinstance(value, dict):
        x = value.get("x")
        y = value.get("y")
        if isinstance(x, int) and isinstance(y, int):
            return (x, y)
        col = value.get("col")
        row = value.get("row")
        if isinstance(col, int) and isinstance(row, int):
            return (col, row)
    if isinstance(value, list | tuple) and len(value) >= 2 and isinstance(value[0], int) and isinstance(value[1], int):
        return (value[0], value[1])
    return None


def _transition_type(raw_item: dict[str, Any]) -> str:
    for key in ("type", "transition_type", "kind", "connector_type"):
        value = raw_item.get(key)
        if isinstance(value, str) and value:
            normalized = value.lower()
            if "stair" in normalized:
                return "stairs"
            if "ramp" in normalized:
                return "ramp"
            if "bridge" in normalized:
                return "bridge_entry"
            if "bunker" in normalized or "descent" in normalized:
                return "bunker_descent"
            if "trench" in normalized:
                return "trench_step"
            if "platform" in normalized or "step" in normalized:
                return "platform_step"
            if "ladder" in normalized or "tower" in normalized:
                return "tower_ladder"
            return "slope"
    return "slope"


def _transition_sprite(rules: dict[str, Any], transition_type: str, index: int) -> str | None:
    raw = rules.get(transition_type)
    if not isinstance(raw, list) or not raw:
        raw = rules.get("slope")
    if not isinstance(raw, list) or not raw:
        return None
    candidates = [item for item in raw if isinstance(item, str) and item]
    if not candidates:
        return None
    return candidates[index % len(candidates)]


def _build_visual_item(
    *,
    x: int,
    y: int,
    elevation: int,
    sprite_id: str,
    visual_role: str,
    kind: str,
    source_id: str,
    layer_order: dict[str, int],
    stable_index: int,
    extra_tags: list[str],
) -> dict[str, Any]:
    draw_layer = "terrain_overlay"
    layer_rank = layer_order.get(draw_layer, layer_order.get("terrain_overlay", 10))
    sort_anchor = {
        "x": x,
        "y": y,
        "elevation": elevation,
        "space": "tile",
        "rule": "y_then_elevation_then_x",
    }
    return {
        "id": f"visual_elevation_{stable_index:05d}",
        "source_object_id": source_id,
        "source_object_type": "visual_elevation",
        "sprite_id": sprite_id,
        "draw_layer": draw_layer,
        "position": {"x": x, "y": y},
        "sort_anchor": sort_anchor,
        "sort_key": [layer_rank, y, elevation, x, stable_index],
        "visual_bounds": {"x": x, "y": y, "width": 1, "height": 1},
        "pivot": {"x": 0, "y": 0, "space": "tile_offset"},
        "occlusion_hint": {},
        "source_tags": ["generated_elevation_visual", kind, *extra_tags],
        "elevation_visual_kind": kind,
        "visual_role": visual_role,
        "gameplay_affecting": False,
    }


def _object_pool(rule: dict[str, Any]) -> list[dict[str, Any]]:
    raw = rule.get("object_pool")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _height_rows(world: WorldPackage) -> list[list[int]]:
    grids = world.runtime_grids.get("grids")
    if not isinstance(grids, dict):
        return []
    grid = grids.get("height_grid")
    if not isinstance(grid, dict):
        return []
    raw_rows = grid.get("rows")
    if not isinstance(raw_rows, list):
        return []
    result: list[list[int]] = []
    for row in raw_rows:
        if isinstance(row, list) and all(isinstance(value, int) for value in row):
            result.append(list(row))
    return result


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list):
        return []
    result: list[list[str]] = []
    for row in rows:
        if isinstance(row, list):
            result.append([str(item) for item in row])
    return result


def _terrain_at(rows: list[list[str]], x: int, y: int) -> str:
    if y < 0 or y >= len(rows):
        return "unknown"
    row = rows[y]
    if x < 0 or x >= len(row):
        return "unknown"
    return row[x]


def _inside(rows: list[list[int]], x: int, y: int) -> bool:
    return y >= 0 and y < len(rows) and x >= 0 and x < len(rows[y])


def _draw_layer_order(profile: VisualProfile) -> dict[str, int]:
    raw_order = profile.profile.get("draw_layer_order", {})
    if not isinstance(raw_order, dict):
        return {"terrain": 0, "terrain_overlay": 10, "objects": 20}
    return {key: value for key, value in raw_order.items() if isinstance(key, str) and isinstance(value, int)}


def _empty_result(status: str) -> dict[str, Any]:
    return {
        "items": [],
        "report": {
            "schema_version": "visual-debug-elevation-visual-report-v1",
            "kind": "visual_debug_elevation_visual_report",
            "source_layer": "runtime_grids.height_grid",
            "rules_enabled": status != "disabled",
            "summary": {
                "total": 0,
                "level_counts": {},
                "lowland_markers": 0,
                "raised_markers": 0,
                "platform_markers": 0,
                "high_point_markers": 0,
                "landmark_markers": 0,
                "transition_markers": 0,
                "by_kind": {},
                "by_role": {},
                "by_sprite_id": {},
                "failed_placements": {},
            },
            "quality": {"status": status},
        },
    }


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default
