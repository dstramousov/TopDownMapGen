from __future__ import annotations

from collections import Counter
from typing import Any


class TileGridError(ValueError):
    """Raised when an ASCII tile grid is invalid."""


def attach_tile_grid(tactical_data: dict[str, Any], rows: list[str]) -> dict[str, Any]:
    """Attach a validated ASCII tile grid to tactical map data.

    Args:
        tactical_data: Runtime tactical JSON object.
        rows: ASCII map rows produced by the map generator.

    Returns:
        Copy of tactical data with a self-contained tile grid in the ``map`` section.

    Raises:
        TileGridError: If rows are empty, non-rectangular, or conflict with metadata.
    """
    width, height = _validate_rows(rows)
    map_info = dict(tactical_data.get("map", {}))
    _validate_metadata(map_info, width, height)

    enriched = dict(tactical_data)
    map_info.update(
        {
            "width": width,
            "height": height,
            "tile_grid_format": "ascii_rows",
            "tile_grid": list(rows),
            "tile_counts": dict(sorted(Counter("".join(rows)).items())),
        },
    )
    enriched["map"] = map_info
    return enriched


def _validate_rows(rows: list[str]) -> tuple[int, int]:
    if not rows:
        raise TileGridError("tile grid is empty")

    width = len(rows[0])
    if width == 0:
        raise TileGridError("tile grid contains an empty first row")

    for row_index, row in enumerate(rows):
        if len(row) != width:
            raise TileGridError(
                f"tile grid is not rectangular: row={row_index} "
                f"width={len(row)} expected={width}",
            )

    return width, len(rows)


def _validate_metadata(map_info: dict[str, Any], width: int, height: int) -> None:
    metadata_width = map_info.get("width")
    metadata_height = map_info.get("height")

    if metadata_width is not None and int(metadata_width) != width:
        raise TileGridError(
            f"tile grid width mismatch: metadata={metadata_width} actual={width}",
        )
    if metadata_height is not None and int(metadata_height) != height:
        raise TileGridError(
            f"tile grid height mismatch: metadata={metadata_height} actual={height}",
        )
