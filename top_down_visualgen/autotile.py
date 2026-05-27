from __future__ import annotations

from collections.abc import Sequence
from typing import Any

_CARDINAL_BITS = (
    (0, -1, 1),
    (1, 0, 2),
    (0, 1, 4),
    (-1, 0, 8),
)


def build_cardinal_mask(
    rows: Sequence[Sequence[str]],
    x: int,
    y: int,
    terrain_types: set[str],
) -> int:
    """Build a four-direction autotile bitmask for a terrain group.

    Args:
        rows: Terrain type rows.
        x: Tile x coordinate.
        y: Tile y coordinate.
        terrain_types: Terrain types that belong to the same visual group.

    Returns:
        Cardinal bitmask using N=1, E=2, S=4 and W=8.
    """
    height = len(rows)
    width = len(rows[0]) if rows else 0
    mask = 0
    for dx, dy, bit in _CARDINAL_BITS:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < width and 0 <= ny < height and rows[ny][nx] in terrain_types:
            mask |= bit
    return mask


def resolve_autotile_id(
    *,
    group_id: str,
    mask: int,
    group_rules: dict[str, Any],
    base_tile_id: str,
) -> str:
    """Resolve a visual tile id from an autotile mask.

    Args:
        group_id: Autotile group identifier.
        mask: Cardinal bitmask.
        group_rules: Autotile group rule object.
        base_tile_id: Fallback tile id.

    Returns:
        Visual tile id.
    """
    explicit = group_rules.get("mask_to_tile")
    mask_key = str(mask)
    if isinstance(explicit, dict) and isinstance(explicit.get(mask_key), str):
        return explicit[mask_key]

    pattern = group_rules.get("tile_id_pattern")
    if isinstance(pattern, str) and pattern:
        return pattern.format(group=group_id, mask=mask, mask_hex=f"{mask:02x}")

    return base_tile_id
