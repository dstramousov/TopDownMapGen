"""Deterministic geometry grids for mass vegetation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import blake2b

NONE_CODE = 0
TREE_CODE = 1
BUSH_CODE = 2
SHORE_REED_CODE = 3
PUDDLE_REED_CODE = 4

VEGETATION_TYPE_NAMES: dict[int, str] = {
    NONE_CODE: "none",
    TREE_CODE: "tree",
    BUSH_CODE: "bush",
    SHORE_REED_CODE: "shore_reed",
    PUDDLE_REED_CODE: "puddle_reed",
}

_VISUAL_TO_TYPE: dict[str, int] = {
    ".": NONE_CODE,
    "T": TREE_CODE,
    "B": BUSH_CODE,
    "R": SHORE_REED_CODE,
    "P": PUDDLE_REED_CODE,
}


@dataclass(frozen=True, slots=True)
class VegetationGeometrySummary:
    """Summary and validation counters for vegetation geometry grids."""

    total_vegetation_tiles: int
    trees: int
    bushes: int
    shore_reeds: int
    puddle_reeds: int
    type_counts: tuple[int, int, int, int, int]
    height_counts: tuple[int, int, int, int, int, int]
    tree_height_counts: tuple[int, int, int, int, int, int]
    bush_height_counts: tuple[int, int, int]
    average_tree_height: float
    average_bush_height: float
    minimum_tree_height: int
    maximum_tree_height: int
    invalid_none_with_height: int
    invalid_vegetation_without_height: int
    visual_type_mismatches: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable summary.

        Returns:
            Summary dictionary with stable string keys.
        """
        return {
            "total_vegetation_tiles": self.total_vegetation_tiles,
            "trees": self.trees,
            "bushes": self.bushes,
            "shore_reeds": self.shore_reeds,
            "puddle_reeds": self.puddle_reeds,
            "type_counts": {
                str(code): count for code, count in enumerate(self.type_counts)
            },
            "height_counts": {
                str(height): count
                for height, count in enumerate(self.height_counts)
            },
            "tree_height_counts": {
                str(height): count
                for height, count in enumerate(self.tree_height_counts)
            },
            "bush_height_counts": {
                str(height): count
                for height, count in enumerate(self.bush_height_counts)
            },
            "average_tree_height": self.average_tree_height,
            "average_bush_height": self.average_bush_height,
            "minimum_tree_height": self.minimum_tree_height,
            "maximum_tree_height": self.maximum_tree_height,
            "invalid_none_with_height": self.invalid_none_with_height,
            "invalid_vegetation_without_height": (
                self.invalid_vegetation_without_height
            ),
            "visual_type_mismatches": self.visual_type_mismatches,
        }


@dataclass(frozen=True, slots=True)
class VegetationGeometryResult:
    """Derived vegetation type and relative height grids."""

    type_rows: list[list[int]]
    height_rows: list[list[int]]
    summary: VegetationGeometrySummary


def build_vegetation_geometry(
    *,
    visual_rows: list[str],
    elevation_rows: list[list[int]],
    resolved_seed: int,
) -> VegetationGeometryResult:
    """Build deterministic mass-vegetation type and height grids.

    Args:
        visual_rows: Final reconciled vegetation symbols per map tile.
        elevation_rows: Final signed elevation levels per map tile.
        resolved_seed: Concrete deterministic world seed.

    Returns:
        Derived vegetation type grid, height grid, and validation summary.

    Raises:
        ValueError: If dimensions, symbols, or generated values are invalid.
    """
    width, height = _validate_dimensions(visual_rows, elevation_rows)
    tree_depths = _tree_edge_depths(visual_rows, width=width, height=height)
    type_rows: list[list[int]] = []
    height_rows: list[list[int]] = []

    for y, visual_row in enumerate(visual_rows):
        type_row: list[int] = []
        height_row: list[int] = []
        for x, symbol in enumerate(visual_row):
            try:
                vegetation_type = _VISUAL_TO_TYPE[symbol]
            except KeyError as error:
                raise ValueError(
                    f"unknown vegetation visual symbol at ({x}, {y}): {symbol!r}",
                ) from error
            vegetation_height = _height_for_tile(
                vegetation_type=vegetation_type,
                edge_depth=tree_depths[y][x],
                elevation=elevation_rows[y][x],
                resolved_seed=resolved_seed,
                x=x,
                y=y,
            )
            type_row.append(vegetation_type)
            height_row.append(vegetation_height)
        type_rows.append(type_row)
        height_rows.append(height_row)

    height_rows = _smooth_tree_heights(type_rows, height_rows)
    summary = _summarize(
        visual_rows=visual_rows,
        type_rows=type_rows,
        height_rows=height_rows,
    )
    _validate_summary(summary)
    return VegetationGeometryResult(
        type_rows=type_rows,
        height_rows=height_rows,
        summary=summary,
    )


def _validate_dimensions(
    visual_rows: list[str],
    elevation_rows: list[list[int]],
) -> tuple[int, int]:
    height = len(visual_rows)
    width = len(visual_rows[0]) if height else 0
    if height == 0 or width == 0:
        raise ValueError("vegetation geometry dimensions must be positive")
    if any(len(row) != width for row in visual_rows):
        raise ValueError("vegetation visual rows have inconsistent widths")
    if len(elevation_rows) != height or any(
        len(row) != width for row in elevation_rows
    ):
        raise ValueError("vegetation elevation dimensions do not match visual rows")
    return width, height


def _tree_edge_depths(
    visual_rows: list[str],
    *,
    width: int,
    height: int,
) -> list[list[int]]:
    depths = [[0 for _ in range(width)] for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()
    for y, row in enumerate(visual_rows):
        for x, symbol in enumerate(row):
            if symbol != "T":
                continue
            if _is_tree_edge(visual_rows, x=x, y=y, width=width, height=height):
                depths[y][x] = 1
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        next_depth = depths[y][x] + 1
        for nx, ny in _neighbors4(x=x, y=y, width=width, height=height):
            if visual_rows[ny][nx] != "T" or depths[ny][nx] != 0:
                continue
            depths[ny][nx] = next_depth
            queue.append((nx, ny))
    return depths


def _is_tree_edge(
    visual_rows: list[str],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> bool:
    if x == 0 or y == 0 or x == width - 1 or y == height - 1:
        return True
    return any(
        visual_rows[ny][nx] != "T"
        for nx, ny in _neighbors4(x=x, y=y, width=width, height=height)
    )


def _neighbors4(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[tuple[int, int], ...]:
    result: list[tuple[int, int]] = []
    if x > 0:
        result.append((x - 1, y))
    if x + 1 < width:
        result.append((x + 1, y))
    if y > 0:
        result.append((x, y - 1))
    if y + 1 < height:
        result.append((x, y + 1))
    return tuple(result)


def _height_for_tile(
    *,
    vegetation_type: int,
    edge_depth: int,
    elevation: int,
    resolved_seed: int,
    x: int,
    y: int,
) -> int:
    if vegetation_type == NONE_CODE:
        return 0
    if vegetation_type == TREE_CODE:
        return _tree_height(
            edge_depth=edge_depth,
            elevation=elevation,
            resolved_seed=resolved_seed,
            x=x,
            y=y,
        )
    if vegetation_type == BUSH_CODE:
        patch_value = _stable_percent(
            resolved_seed=resolved_seed,
            x=x // 4,
            y=y // 4,
            salt="vegetation_bush_height_v1",
        )
        return 2 if patch_value >= 65 else 1
    if vegetation_type in {SHORE_REED_CODE, PUDDLE_REED_CODE}:
        return 1
    raise ValueError(f"unsupported vegetation type code: {vegetation_type}")


def _tree_height(
    *,
    edge_depth: int,
    elevation: int,
    resolved_seed: int,
    x: int,
    y: int,
) -> int:
    if edge_depth <= 1:
        base_height = 2
    elif edge_depth == 2:
        base_height = 3
    else:
        base_height = 4

    patch_value = _stable_percent(
        resolved_seed=resolved_seed,
        x=x // 5,
        y=y // 5,
        salt="vegetation_tree_height_v1",
    )
    if edge_depth >= 3 and patch_value >= 82:
        base_height += 1
    elif edge_depth >= 2 and patch_value < 12:
        base_height -= 1

    if elevation >= 17:
        maximum = 3
    elif elevation >= 14:
        maximum = 4
    else:
        maximum = 5
    return max(2, min(base_height, maximum))


def _smooth_tree_heights(
    type_rows: list[list[int]],
    height_rows: list[list[int]],
) -> list[list[int]]:
    height = len(type_rows)
    width = len(type_rows[0])
    current = [list(row) for row in height_rows]
    for _ in range(4):
        updated = [list(row) for row in current]
        changed = False
        for y in range(height):
            for x in range(width):
                if type_rows[y][x] != TREE_CODE:
                    continue
                neighbor_heights = [
                    current[ny][nx]
                    for nx, ny in _neighbors4(
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                    )
                    if type_rows[ny][nx] == TREE_CODE
                ]
                if not neighbor_heights:
                    continue
                maximum = min(neighbor_heights) + 1
                if current[y][x] > maximum:
                    updated[y][x] = maximum
                    changed = True
        current = updated
        if not changed:
            break
    return current


def _stable_percent(
    *,
    resolved_seed: int,
    x: int,
    y: int,
    salt: str,
) -> int:
    payload = f"{resolved_seed}:{x}:{y}:{salt}".encode("utf-8")
    value = int.from_bytes(blake2b(payload, digest_size=8).digest(), "little")
    return value % 100


def _summarize(
    *,
    visual_rows: list[str],
    type_rows: list[list[int]],
    height_rows: list[list[int]],
) -> VegetationGeometrySummary:
    type_counts = [0, 0, 0, 0, 0]
    height_counts = [0, 0, 0, 0, 0, 0]
    tree_height_counts = [0, 0, 0, 0, 0, 0]
    bush_height_counts = [0, 0, 0]
    tree_height_sum = 0
    bush_height_sum = 0
    tree_minimum = 0
    tree_maximum = 0
    invalid_none_with_height = 0
    invalid_vegetation_without_height = 0
    visual_type_mismatches = 0

    for y, visual_row in enumerate(visual_rows):
        for x, symbol in enumerate(visual_row):
            vegetation_type = type_rows[y][x]
            vegetation_height = height_rows[y][x]
            if not 0 <= vegetation_type < len(type_counts):
                raise ValueError("vegetation type exceeds uint8 v1 contract")
            if not 0 <= vegetation_height < len(height_counts):
                raise ValueError("vegetation height exceeds uint8 v1 contract")
            type_counts[vegetation_type] += 1
            height_counts[vegetation_height] += 1
            if _VISUAL_TO_TYPE[symbol] != vegetation_type:
                visual_type_mismatches += 1
            if vegetation_type == NONE_CODE:
                if vegetation_height != 0:
                    invalid_none_with_height += 1
            elif vegetation_height == 0:
                invalid_vegetation_without_height += 1

            if vegetation_type == TREE_CODE:
                if not 2 <= vegetation_height <= 5:
                    raise ValueError("tree height is outside the v1 range")
                tree_height_counts[vegetation_height] += 1
                tree_height_sum += vegetation_height
                if tree_minimum == 0 or vegetation_height < tree_minimum:
                    tree_minimum = vegetation_height
                tree_maximum = max(tree_maximum, vegetation_height)
            elif vegetation_type == BUSH_CODE:
                if not 1 <= vegetation_height <= 2:
                    raise ValueError("bush height is outside the v1 range")
                bush_height_counts[vegetation_height] += 1
                bush_height_sum += vegetation_height
            elif vegetation_type in {SHORE_REED_CODE, PUDDLE_REED_CODE}:
                if vegetation_height != 1:
                    raise ValueError("reed height must equal one logical level")

    trees = type_counts[TREE_CODE]
    bushes = type_counts[BUSH_CODE]
    shore_reeds = type_counts[SHORE_REED_CODE]
    puddle_reeds = type_counts[PUDDLE_REED_CODE]
    return VegetationGeometrySummary(
        total_vegetation_tiles=trees + bushes + shore_reeds + puddle_reeds,
        trees=trees,
        bushes=bushes,
        shore_reeds=shore_reeds,
        puddle_reeds=puddle_reeds,
        type_counts=tuple(type_counts),
        height_counts=tuple(height_counts),
        tree_height_counts=tuple(tree_height_counts),
        bush_height_counts=tuple(bush_height_counts),
        average_tree_height=(tree_height_sum / trees if trees else 0.0),
        average_bush_height=(bush_height_sum / bushes if bushes else 0.0),
        minimum_tree_height=tree_minimum,
        maximum_tree_height=tree_maximum,
        invalid_none_with_height=invalid_none_with_height,
        invalid_vegetation_without_height=invalid_vegetation_without_height,
        visual_type_mismatches=visual_type_mismatches,
    )


def _validate_summary(summary: VegetationGeometrySummary) -> None:
    if summary.invalid_none_with_height:
        raise ValueError("none vegetation tiles contain non-zero height")
    if summary.invalid_vegetation_without_height:
        raise ValueError("vegetation tiles contain zero height")
    if summary.visual_type_mismatches:
        raise ValueError("vegetation type grid differs from visual symbols")
