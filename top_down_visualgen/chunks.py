from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from typing import Any


def build_visual_chunks(
    *,
    width: int,
    height: int,
    visual_objects: dict[str, Any],
    chunk_size_tiles: int,
) -> dict[str, Any]:
    """Build lightweight visual chunk metadata.

    Args:
        width: Map width in tiles.
        height: Map height in tiles.
        visual_objects: Visual objects JSON object.
        chunk_size_tiles: Chunk size in tiles.

    Returns:
        Visual chunks JSON object.
    """
    size = max(1, chunk_size_tiles)
    items = visual_objects.get("items", [])
    object_items = items if isinstance(items, list) else []
    chunks: list[dict[str, Any]] = []
    for chunk_y in range(ceil(height / size)):
        for chunk_x in range(ceil(width / size)):
            min_x = chunk_x * size
            min_y = chunk_y * size
            max_x = min(width - 1, min_x + size - 1)
            max_y = min(height - 1, min_y + size - 1)
            object_ids = _object_ids_in_bounds(object_items, min_x, min_y, max_x, max_y)
            chunks.append(
                {
                    "id": f"chunk_{chunk_x:03d}_{chunk_y:03d}",
                    "x": chunk_x,
                    "y": chunk_y,
                    "bounds": {
                        "min_x": min_x,
                        "min_y": min_y,
                        "max_x": max_x,
                        "max_y": max_y,
                    },
                    "width": max_x - min_x + 1,
                    "height": max_y - min_y + 1,
                    "visual_layer_refs": ["terrain_base"],
                    "visual_object_ids": object_ids,
                    "object_count": len(object_ids),
                }
            )

    return {
        "schema_version": "visual-chunks-v1",
        "kind": "visual_chunks",
        "coordinate_space": "tile",
        "chunk_size_tiles": size,
        "width": width,
        "height": height,
        "items": chunks,
        "summary": {
            "total": len(chunks),
            "chunk_columns": ceil(width / size),
            "chunk_rows": ceil(height / size),
        },
    }


def _object_ids_in_bounds(
    objects: Sequence[Any],
    min_x: int,
    min_y: int,
    max_x: int,
    max_y: int,
) -> list[str]:
    result: list[str] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        position = item.get("position")
        if not isinstance(position, dict):
            continue
        x = position.get("x")
        y = position.get("y")
        object_id = item.get("id")
        if (
            isinstance(x, int)
            and isinstance(y, int)
            and isinstance(object_id, str)
            and min_x <= x <= max_x
            and min_y <= y <= max_y
        ):
            result.append(object_id)
    return result
