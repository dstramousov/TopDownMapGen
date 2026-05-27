from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from .autotile import build_cardinal_mask, resolve_autotile_id
from .models import VisualProfile, WorldPackage


class TerrainVisualMapper:
    """Convert semantic terrain types to visual tile ids."""

    def map_terrain(
        self,
        world: WorldPackage,
        profile: VisualProfile,
    ) -> dict[str, Any]:
        """Build visual terrain layers from a world package.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.

        Returns:
            Visual layers JSON object.

        Raises:
            ValueError: If terrain rows are malformed.
        """
        rows = _terrain_rows(world.terrain)
        height = len(rows)
        width = len(rows[0]) if rows else 0
        tile_rows: list[list[str]] = []
        autotile_rows: list[list[dict[str, Any] | None]] = []
        tile_counts: Counter[str] = Counter()
        terrain_counts: Counter[str] = Counter()

        for y, terrain_row in enumerate(rows):
            visual_row: list[str] = []
            autotile_row: list[dict[str, Any] | None] = []
            for x, terrain_type in enumerate(terrain_row):
                tile_id, autotile_info = self._resolve_tile_id(
                    rows=rows,
                    x=x,
                    y=y,
                    terrain_type=terrain_type,
                    profile=profile,
                )
                visual_row.append(tile_id)
                autotile_row.append(autotile_info)
                tile_counts[tile_id] += 1
                terrain_counts[terrain_type] += 1
            tile_rows.append(visual_row)
            autotile_rows.append(autotile_row)

        tile_size_px = _tile_size_px(world.index, profile)
        return {
            "schema_version": "visual-layers-v1",
            "kind": "visual_layers",
            "width": width,
            "height": height,
            "coordinate_space": "tile",
            "tile_size_px": tile_size_px,
            "layers": [
                {
                    "id": "terrain_base",
                    "role": "terrain",
                    "source": "map_package.layers.terrain",
                    "sort_mode": "grid",
                    "width": width,
                    "height": height,
                    "rows": tile_rows,
                    "summary": {
                        "unique_tile_ids": len(tile_counts),
                        "tile_counts": dict(sorted(tile_counts.items())),
                        "terrain_counts": dict(sorted(terrain_counts.items())),
                    },
                }
            ],
            "debug": {
                "autotile_masks": autotile_rows,
            },
        }

    def _resolve_tile_id(
        self,
        *,
        rows: Sequence[Sequence[str]],
        x: int,
        y: int,
        terrain_type: str,
        profile: VisualProfile,
    ) -> tuple[str, dict[str, Any] | None]:
        terrain_rules = profile.terrain_rules
        terrain_to_tile = terrain_rules.get("terrain_to_tile", {})
        if not isinstance(terrain_to_tile, dict):
            terrain_to_tile = {}
        default_tile = terrain_rules.get("default_tile", "terrain.unknown")
        base_tile_id = terrain_to_tile.get(terrain_type, default_tile)
        if not isinstance(base_tile_id, str):
            base_tile_id = "terrain.unknown"

        group = _find_autotile_group(terrain_type, profile.autotile_rules)
        if group is None:
            return base_tile_id, None

        group_id, group_rules, terrain_types = group
        mask = build_cardinal_mask(rows, x, y, terrain_types)
        tile_id = resolve_autotile_id(
            group_id=group_id,
            mask=mask,
            group_rules=group_rules,
            base_tile_id=base_tile_id,
        )
        return tile_id, {
            "x": x,
            "y": y,
            "group": group_id,
            "mask": mask,
            "tile_id": tile_id,
        }


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
        normalized.append(list(row))
    return normalized


def _find_autotile_group(
    terrain_type: str,
    autotile_rules: dict[str, Any],
) -> tuple[str, dict[str, Any], set[str]] | None:
    groups = autotile_rules.get("groups", {})
    if not isinstance(groups, dict):
        return None
    for group_id, raw_group in groups.items():
        if not isinstance(group_id, str) or not isinstance(raw_group, dict):
            continue
        raw_types = raw_group.get("terrain_types", [])
        if not isinstance(raw_types, list):
            continue
        terrain_types = {item for item in raw_types if isinstance(item, str)}
        if terrain_type in terrain_types:
            return group_id, raw_group, terrain_types
    return None


def _tile_size_px(index: dict[str, Any], profile: VisualProfile) -> int:
    profile_tile_size = profile.profile.get("tile_size_px")
    if isinstance(profile_tile_size, int) and profile_tile_size > 0:
        return profile_tile_size

    dimensions = index.get("dimensions")
    if isinstance(dimensions, dict):
        tile_size = dimensions.get("tile_size_px")
        if isinstance(tile_size, int) and tile_size > 0:
            return tile_size
    return 16
