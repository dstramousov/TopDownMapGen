from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

_CARDINAL_BITS = (
    (0, -1, 1, "n"),
    (1, 0, 2, "e"),
    (0, 1, 4, "s"),
    (-1, 0, 8, "w"),
)

_DIAGONAL_BITS = (
    (1, -1, 16, "ne"),
    (1, 1, 32, "es"),
    (-1, 1, 64, "sw"),
    (-1, -1, 128, "wn"),
)

_SUPPORTED_MASK_MODES = {"cardinal_4", "blob_8"}


@dataclass(frozen=True, slots=True)
class AutotileDecision:
    """Resolved autotile variant for a single terrain cell."""

    group_id: str
    mask_mode: str
    mask: int
    cardinal_mask: int
    variant: str
    tile_id: str
    fallback_used: bool


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
    return build_neighbor_mask(
        rows=rows,
        x=x,
        y=y,
        terrain_types=terrain_types,
        mask_mode="cardinal_4",
    )


def build_neighbor_mask(
    *,
    rows: Sequence[Sequence[str]],
    x: int,
    y: int,
    terrain_types: set[str],
    mask_mode: str,
) -> int:
    """Build a neighbor bitmask for an autotile group.

    Args:
        rows: Terrain type rows.
        x: Tile x coordinate.
        y: Tile y coordinate.
        terrain_types: Terrain types that belong to the same visual group.
        mask_mode: Mask mode, either ``cardinal_4`` or ``blob_8``.

    Returns:
        Neighbor bitmask. ``cardinal_4`` uses N=1, E=2, S=4, W=8.
        ``blob_8`` also uses NE=16, ES=32, SW=64, WN=128.

    Raises:
        ValueError: If mask mode is unsupported.
    """
    if mask_mode not in _SUPPORTED_MASK_MODES:
        raise ValueError(f"Unsupported autotile mask mode: {mask_mode}")

    mask = _build_mask_for_bits(rows, x, y, terrain_types, _CARDINAL_BITS)
    if mask_mode == "blob_8":
        mask |= _build_mask_for_bits(rows, x, y, terrain_types, _DIAGONAL_BITS)
    return mask


def resolve_autotile_decision(
    *,
    group_id: str,
    mask: int,
    group_rules: dict[str, Any],
    base_tile_id: str,
) -> AutotileDecision:
    """Resolve a visual tile id and debug metadata from an autotile mask.

    Args:
        group_id: Autotile group identifier.
        mask: Neighbor bitmask.
        group_rules: Autotile group rule object.
        base_tile_id: Fallback tile id.

    Returns:
        Autotile decision.
    """
    mask_mode = _string_value(group_rules.get("mask_mode"), "cardinal_4")
    cardinal_mask = mask & 0x0F
    variant = _resolve_variant(mask=mask, mask_mode=mask_mode, group_rules=group_rules)
    tile_id, fallback_used = _resolve_tile_id(
        group_id=group_id,
        mask=mask,
        variant=variant,
        group_rules=group_rules,
        base_tile_id=base_tile_id,
    )
    return AutotileDecision(
        group_id=group_id,
        mask_mode=mask_mode,
        mask=mask,
        cardinal_mask=cardinal_mask,
        variant=variant,
        tile_id=tile_id,
        fallback_used=fallback_used,
    )


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
        mask: Neighbor bitmask.
        group_rules: Autotile group rule object.
        base_tile_id: Fallback tile id.

    Returns:
        Visual tile id.
    """
    return resolve_autotile_decision(
        group_id=group_id,
        mask=mask,
        group_rules=group_rules,
        base_tile_id=base_tile_id,
    ).tile_id


def _build_mask_for_bits(
    rows: Sequence[Sequence[str]],
    x: int,
    y: int,
    terrain_types: set[str],
    bit_specs: Sequence[tuple[int, int, int, str]],
) -> int:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    mask = 0
    for dx, dy, bit, _name in bit_specs:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < width and 0 <= ny < height and rows[ny][nx] in terrain_types:
            mask |= bit
    return mask


def _resolve_variant(
    *,
    mask: int,
    mask_mode: str,
    group_rules: dict[str, Any],
) -> str:
    explicit_variants = group_rules.get("mask_to_variant")
    if isinstance(explicit_variants, dict):
        value = explicit_variants.get(str(mask))
        if isinstance(value, str) and value:
            return value

    if mask_mode == "blob_8":
        return _blob_8_variant(mask)
    return _cardinal_4_variant(mask & 0x0F)


def _resolve_tile_id(
    *,
    group_id: str,
    mask: int,
    variant: str,
    group_rules: dict[str, Any],
    base_tile_id: str,
) -> tuple[str, bool]:
    variant_to_tile = group_rules.get("variant_to_tile")
    if isinstance(variant_to_tile, dict):
        value = variant_to_tile.get(variant)
        if isinstance(value, str) and value:
            return value, False

    mask_to_tile = group_rules.get("mask_to_tile")
    if isinstance(mask_to_tile, dict):
        value = mask_to_tile.get(str(mask))
        if isinstance(value, str) and value:
            return value, False

    pattern = group_rules.get("tile_id_pattern")
    if isinstance(pattern, str) and pattern:
        return pattern.format(
            group=group_id,
            mask=mask,
            mask_hex=f"{mask:02x}",
            variant=variant,
        ), False

    fallback_tile = group_rules.get("fallback_tile")
    if isinstance(fallback_tile, str) and fallback_tile:
        return fallback_tile, True
    return base_tile_id, True


def _cardinal_4_variant(mask: int) -> str:
    mapping = {
        0: "isolated",
        1: "end_n",
        2: "end_e",
        3: "turn_ne",
        4: "end_s",
        5: "straight_ns",
        6: "turn_es",
        7: "t_nes",
        8: "end_w",
        9: "turn_wn",
        10: "straight_ew",
        11: "t_new",
        12: "turn_sw",
        13: "t_nsw",
        14: "t_esw",
        15: "cross",
    }
    return mapping.get(mask, f"mask_{mask}")


def _blob_8_variant(mask: int) -> str:
    cardinal = mask & 0x0F
    if cardinal == 0:
        return "isolated"

    if cardinal == 15:
        missing_diagonals = [
            name
            for bit, name in ((16, "ne"), (32, "es"), (64, "sw"), (128, "wn"))
            if not mask & bit
        ]
        if not missing_diagonals:
            return "fill"
        if len(missing_diagonals) == 1:
            return f"inner_corner_{missing_diagonals[0]}"
        return "inner_corner_complex"

    mapping = {
        1: "cap_s",
        2: "cap_w",
        3: "outer_corner_sw",
        4: "cap_n",
        5: "thin_ns",
        6: "outer_corner_wn",
        7: "edge_w",
        8: "cap_e",
        9: "outer_corner_es",
        10: "thin_ew",
        11: "edge_s",
        12: "outer_corner_ne",
        13: "edge_e",
        14: "edge_n",
    }
    return mapping.get(cardinal, f"mask_{cardinal}")


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default
