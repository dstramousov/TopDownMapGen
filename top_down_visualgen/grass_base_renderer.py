from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from .models import VisualProfile, WorldPackage


class GrassBaseRenderer:
    """Apply calm grass-base tile variation to visual terrain rows."""

    def render_grass_base(
        self,
        *,
        world: WorldPackage,
        profile: VisualProfile,
        visual_layers: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Render visual-only grass base variation.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.
            visual_layers: Existing visual layers produced by the terrain mapper.

        Returns:
            Updated visual layers and a JSON-compatible debug report.
        """
        rules = profile.grass_render_rules
        if not _bool_value(rules.get("enabled"), True):
            return visual_layers, _disabled_report()

        terrain_rows = _terrain_rows(world.terrain)
        output_layers = deepcopy(visual_layers)
        base_layer = _terrain_base_layer(output_layers)
        visual_rows = _visual_rows(base_layer)

        candidate_terrains = _string_set(
            rules.get("candidate_terrain_types"),
            default={"grass", "empty", "start", "goal"},
        )
        candidate_tiles = _string_set(
            rules.get("candidate_tile_ids"),
            default={"grass.base"},
        )
        base_tiles = _string_list(
            rules.get("base_tiles"),
            default=["grass.clean_base_01", "grass.clean_base_02", "grass.light_base_01"],
        )
        patch_tiles = _string_list(
            rules.get("patch_tiles"),
            default=["grass.soft_patch_01", "grass.soft_patch_02"],
        )
        forest_transition_tiles = _string_list(
            rules.get("forest_transition_tiles"),
            default=["grass.forest_transition_01"],
        )
        forest_terrain_types = _string_set(
            rules.get("forest_terrain_types"),
            default={"forest", "tree_blocker", "bush", "bush_slow_concealment"},
        )
        patch_period = max(1, _int_value(rules.get("patch_period"), 11))
        transition_period = max(1, _int_value(rules.get("forest_transition_period"), 2))
        seed = _seed(world.index)

        counts: Counter[str] = Counter()
        candidates = 0
        base_count = 0
        patch_count = 0
        transition_count = 0
        skipped = 0

        for y, terrain_row in enumerate(terrain_rows):
            if y >= len(visual_rows):
                break
            visual_row = visual_rows[y]
            for x, terrain_type in enumerate(terrain_row):
                if x >= len(visual_row):
                    continue
                current_tile = visual_row[x]
                if terrain_type not in candidate_terrains and current_tile not in candidate_tiles:
                    skipped += 1
                    continue

                candidates += 1
                if _has_neighbor_terrain(terrain_rows, x, y, forest_terrain_types) and (
                    _stable_bucket(seed=seed, x=x, y=y, salt=17) % transition_period == 0
                ):
                    tile_id = _choose_tile(forest_transition_tiles, seed=seed, x=x, y=y, salt=23)
                    transition_count += 1
                elif _stable_bucket(seed=seed, x=x, y=y, salt=31) % patch_period == 0:
                    tile_id = _choose_tile(patch_tiles, seed=seed, x=x, y=y, salt=37)
                    patch_count += 1
                else:
                    tile_id = _choose_tile(base_tiles, seed=seed, x=x, y=y, salt=41)
                    base_count += 1

                visual_row[x] = tile_id
                counts[tile_id] += 1

        base_layer.setdefault("summary", {})["grass_render"] = {
            "total_candidates": candidates,
            "base_tiles": base_count,
            "patch_tiles": patch_count,
            "forest_transitions": transition_count,
        }

        return output_layers, {
            "schema_version": "visual-debug-grass-render-report-v1",
            "kind": "visual_debug_grass_render_report",
            "source_layer": "terrain_base",
            "rules_enabled": True,
            "summary": {
                "total_candidates": candidates,
                "base_tiles": base_count,
                "patch_tiles": patch_count,
                "forest_transitions": transition_count,
                "skipped_tiles": skipped,
                "by_tile_id": dict(sorted(counts.items())),
            },
            "quality": {
                "status": "ok" if candidates > 0 else "no_candidates",
            },
        }


def _disabled_report() -> dict[str, Any]:
    return {
        "schema_version": "visual-debug-grass-render-report-v1",
        "kind": "visual_debug_grass_render_report",
        "source_layer": "terrain_base",
        "rules_enabled": False,
        "summary": {
            "total_candidates": 0,
            "base_tiles": 0,
            "patch_tiles": 0,
            "forest_transitions": 0,
            "skipped_tiles": 0,
            "by_tile_id": {},
        },
        "quality": {"status": "disabled"},
    }


def _terrain_base_layer(visual_layers: dict[str, Any]) -> dict[str, Any]:
    layers = visual_layers.get("layers")
    if not isinstance(layers, list):
        raise ValueError("visual_layers.layers must be a list")
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "terrain_base":
            return layer
    raise ValueError("Missing terrain_base visual layer")


def _visual_rows(layer: dict[str, Any]) -> list[list[str]]:
    rows = layer.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("terrain_base.rows must contain non-empty rows")
    normalized: list[list[str]] = []
    width: int | None = None
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or not all(isinstance(item, str) for item in row):
            raise ValueError(f"Visual row {row_index} must be a list of strings")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("Visual rows must have equal width")
        normalized.append(row)
    return normalized


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Terrain layer must contain non-empty rows")
    normalized: list[list[str]] = []
    width: int | None = None
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or not all(isinstance(item, str) for item in row):
            raise ValueError(f"Terrain row {row_index} must be a list of strings")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("Terrain rows must have equal width")
        normalized.append(row)
    return normalized


def _has_neighbor_terrain(
    rows: list[list[str]],
    x: int,
    y: int,
    terrain_types: set[str],
) -> bool:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0), (1, -1), (1, 1), (-1, 1), (-1, -1)):
        nx = x + dx
        ny = y + dy
        if 0 <= nx < width and 0 <= ny < height and rows[ny][nx] in terrain_types:
            return True
    return False


def _choose_tile(values: list[str], *, seed: int, x: int, y: int, salt: int) -> str:
    if not values:
        return "grass.base"
    return values[_stable_bucket(seed=seed, x=x, y=y, salt=salt) % len(values)]


def _stable_bucket(*, seed: int, x: int, y: int, salt: int) -> int:
    value = seed ^ (x * 0x45D9F3B) ^ (y * 0x119DE1F3) ^ (salt * 0x27D4EB2D)
    value = (value ^ (value >> 16)) * 0x45D9F3B
    value = (value ^ (value >> 16)) * 0x45D9F3B
    value = value ^ (value >> 16)
    return value & 0xFFFFFFFF


def _seed(index: dict[str, Any]) -> int:
    value = index.get("resolved_seed")
    return value if isinstance(value, int) else 0


def _string_set(value: Any, *, default: set[str]) -> set[str]:
    if not isinstance(value, list):
        return set(default)
    result = {item for item in value if isinstance(item, str) and item}
    return result or set(default)


def _string_list(value: Any, *, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    result = [item for item in value if isinstance(item, str) and item]
    return result or list(default)


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default


def _bool_value(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default
