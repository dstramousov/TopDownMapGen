from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .geography_draft import NaturalGeographyModel
from .geography_guidance import terrain_profile_items

MOISTURE_SCALE = 1_000
FOREST_DEPTH_MAX = 4
FOREST_DISTANCE_FAR = 9
TREE_TERRAIN = "tree_blocker"

REGION_PROFILE_NAMES: tuple[str, ...] = (
    "dense_forest",
    "woodland",
    "wet_lowland",
    "upland",
    "open_plateau",
    "open_plain",
    "alpine",
)
REGION_PROFILE_CODES = {
    name: index for index, name in enumerate(REGION_PROFILE_NAMES)
}
SLOPE_BAND_NAMES = {
    0: "flat",
    1: "gentle",
    2: "steep",
    3: "cliff",
}


@dataclass(frozen=True, slots=True)
class EnvironmentContextResult:
    """Derived ecological context for public map-package consumers."""

    width: int
    height: int
    moisture_rows: list[list[int]]
    region_profile_rows: list[list[int]]
    slope_band_rows: list[list[int]]
    forest_depth_rows: list[list[int]]
    forest_distance_rows: list[list[int]]
    summary: dict[str, Any]

    def to_payload(self, *, schema_version: str) -> dict[str, Any]:
        """Build the JSON-serializable public layer payload.

        Args:
            schema_version: Public environment-context schema version.

        Returns:
            JSON-serializable environment-context layer.
        """
        return {
            "schema_version": schema_version,
            "kind": "environment_context",
            "width": self.width,
            "height": self.height,
            "rules": {
                "forest_terrain": TREE_TERRAIN,
                "forest_depth_max": FOREST_DEPTH_MAX,
                "forest_distance_far_value": FOREST_DISTANCE_FAR,
                "forest_distance_metric": "8_neighbor_chamfer_10_14",
            },
            "dictionaries": {
                "region_profile": {
                    str(code): name
                    for name, code in REGION_PROFILE_CODES.items()
                },
                "slope_band": {
                    str(code): name for code, name in SLOPE_BAND_NAMES.items()
                },
            },
            "grids": {
                "moisture": {
                    "format": "uint16_rows",
                    "scale": MOISTURE_SCALE,
                    "range": [0, MOISTURE_SCALE],
                    "rows": self.moisture_rows,
                },
                "region_profile": {
                    "format": "uint8_rows",
                    "rows": self.region_profile_rows,
                },
                "slope_band": {
                    "format": "uint8_rows",
                    "range": [0, 3],
                    "rows": self.slope_band_rows,
                },
                "forest_depth": {
                    "format": "uint8_rows",
                    "range": [0, FOREST_DEPTH_MAX],
                    "value_4_means": "4_or_more",
                    "rows": self.forest_depth_rows,
                },
                "forest_distance": {
                    "format": "uint8_rows",
                    "range": [0, FOREST_DISTANCE_FAR],
                    "far_value": FOREST_DISTANCE_FAR,
                    "rows": self.forest_distance_rows,
                },
            },
            "summary": self.summary,
        }


def build_environment_context(
    *,
    natural_geography: NaturalGeographyModel,
    terrain_rows: list[list[str]],
) -> EnvironmentContextResult:
    """Build deterministic ecological context from existing world semantics.

    Args:
        natural_geography: Natural geography produced before terrain placement.
        terrain_rows: Final semantic terrain rows from the public map package.

    Returns:
        Derived environment-context grids and diagnostics.

    Raises:
        ValueError: If input dimensions are inconsistent or region indices are invalid.
    """
    width = natural_geography.width
    height = natural_geography.height
    _validate_terrain_rows(terrain_rows, width=width, height=height)
    natural_geography.validate_for(
        width=width,
        height=height,
        seed=natural_geography.seed,
        elevation_style=natural_geography.elevation_style,
    )

    moisture_rows = _quantize_moisture_rows(natural_geography.draft.moisture_scores)
    slope_band_rows = [
        [min(3, max(0, int(value))) for value in row]
        for row in natural_geography.slope_rows
    ]
    region_profile_rows = _region_profile_rows(natural_geography)
    forest_depth_rows = build_forest_depth_rows(terrain_rows)
    forest_distance_rows = build_forest_distance_rows(terrain_rows)

    return EnvironmentContextResult(
        width=width,
        height=height,
        moisture_rows=moisture_rows,
        region_profile_rows=region_profile_rows,
        slope_band_rows=slope_band_rows,
        forest_depth_rows=forest_depth_rows,
        forest_distance_rows=forest_distance_rows,
        summary=_build_summary(
            moisture_rows=moisture_rows,
            region_profile_rows=region_profile_rows,
            slope_band_rows=slope_band_rows,
            forest_depth_rows=forest_depth_rows,
        ),
    )


def build_forest_depth_rows(terrain_rows: list[list[str]]) -> list[list[int]]:
    """Return semantic forest depth capped at four tiles.

    Args:
        terrain_rows: Rectangular semantic terrain rows.

    Returns:
        Per-tile forest depth where edge forest has depth one and four means
        four or more tiles from the forest boundary.
    """
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if height else 0
    depths = [[0 for _ in range(width)] for _ in range(height)]
    frontier: list[tuple[int, int]] = []

    for y, row in enumerate(terrain_rows):
        for x, terrain in enumerate(row):
            if terrain != TREE_TERRAIN:
                continue
            if _touches_non_forest(terrain_rows, x=x, y=y):
                depths[y][x] = 1
                frontier.append((x, y))

    index = 0
    while index < len(frontier):
        x, y = frontier[index]
        index += 1
        depth = depths[y][x]
        if depth >= FOREST_DEPTH_MAX:
            continue
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if terrain_rows[ny][nx] != TREE_TERRAIN or depths[ny][nx] != 0:
                continue
            depths[ny][nx] = depth + 1
            frontier.append((nx, ny))
    return depths


def build_forest_distance_rows(terrain_rows: list[list[str]]) -> list[list[int]]:
    """Return approximate distance from every tile to semantic forest.

    Args:
        terrain_rows: Rectangular semantic terrain rows.

    Returns:
        Tile-distance rows where forest is zero and nine means nine or more
        tiles away, using a two-pass 8-neighbor chamfer transform.
    """
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if height else 0
    if width == 0 or height == 0:
        return []

    far_cost = FOREST_DISTANCE_FAR * 10
    distances = [
        [0 if terrain == TREE_TERRAIN else far_cost for terrain in row]
        for row in terrain_rows
    ]

    for y in range(height):
        for x in range(width):
            if distances[y][x] == 0:
                continue
            distances[y][x] = min(
                distances[y][x],
                _chamfer_neighbor_cost(distances, x=x - 1, y=y, extra=10),
                _chamfer_neighbor_cost(distances, x=x, y=y - 1, extra=10),
                _chamfer_neighbor_cost(distances, x=x - 1, y=y - 1, extra=14),
                _chamfer_neighbor_cost(distances, x=x + 1, y=y - 1, extra=14),
            )

    for y in range(height - 1, -1, -1):
        for x in range(width - 1, -1, -1):
            if distances[y][x] == 0:
                continue
            distances[y][x] = min(
                distances[y][x],
                _chamfer_neighbor_cost(distances, x=x + 1, y=y, extra=10),
                _chamfer_neighbor_cost(distances, x=x, y=y + 1, extra=10),
                _chamfer_neighbor_cost(distances, x=x + 1, y=y + 1, extra=14),
                _chamfer_neighbor_cost(distances, x=x - 1, y=y + 1, extra=14),
            )

    return [
        [min(FOREST_DISTANCE_FAR, (cost + 5) // 10) for cost in row]
        for row in distances
    ]


def _region_profile_rows(model: NaturalGeographyModel) -> list[list[int]]:
    items = terrain_profile_items(model)
    codes_by_region: list[int] = []
    for item in items:
        profile = str(item["profile"])
        try:
            codes_by_region.append(REGION_PROFILE_CODES[profile])
        except KeyError as exc:
            raise ValueError(f"Unknown terrain profile: {profile!r}") from exc

    rows: list[list[int]] = []
    for y, source_row in enumerate(model.draft.dominant_region_rows):
        output_row: list[int] = []
        for x, region_index in enumerate(source_row):
            if not 0 <= region_index < len(codes_by_region):
                raise ValueError(
                    "Dominant geography region index is out of range: "
                    f"x={x}, y={y}, region_index={region_index}"
                )
            output_row.append(codes_by_region[region_index])
        rows.append(output_row)
    return rows


def _quantize_moisture_rows(rows: list[list[float]]) -> list[list[int]]:
    return [
        [
            max(0, min(MOISTURE_SCALE, round(float(value) * MOISTURE_SCALE)))
            for value in row
        ]
        for row in rows
    ]


def _build_summary(
    *,
    moisture_rows: list[list[int]],
    region_profile_rows: list[list[int]],
    slope_band_rows: list[list[int]],
    forest_depth_rows: list[list[int]],
) -> dict[str, Any]:
    moisture_counts = Counter(
        "dry" if value < 330 else "balanced" if value < 660 else "wet"
        for row in moisture_rows
        for value in row
    )
    region_counts = Counter(
        REGION_PROFILE_NAMES[value]
        for row in region_profile_rows
        for value in row
    )
    slope_counts = Counter(
        SLOPE_BAND_NAMES[value]
        for row in slope_band_rows
        for value in row
    )
    forest_counts = Counter(value for row in forest_depth_rows for value in row)
    total = sum(len(row) for row in moisture_rows)
    return {
        "tiles": total,
        "moisture_tiles": dict(sorted(moisture_counts.items())),
        "region_profile_tiles": dict(sorted(region_counts.items())),
        "slope_band_tiles": dict(sorted(slope_counts.items())),
        "forest": {
            "tiles": total - forest_counts.get(0, 0),
            "edge_tiles": forest_counts.get(1, 0),
            "deep_tiles": forest_counts.get(FOREST_DEPTH_MAX, 0),
        },
    }


def _touches_non_forest(
    terrain_rows: list[list[str]],
    *,
    x: int,
    y: int,
) -> bool:
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if height else 0
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if not (0 <= nx < width and 0 <= ny < height):
            return True
        if terrain_rows[ny][nx] != TREE_TERRAIN:
            return True
    return False


def _chamfer_neighbor_cost(
    rows: list[list[int]],
    *,
    x: int,
    y: int,
    extra: int,
) -> int:
    if y < 0 or y >= len(rows):
        return FOREST_DISTANCE_FAR * 10
    if x < 0 or x >= len(rows[y]):
        return FOREST_DISTANCE_FAR * 10
    return min(FOREST_DISTANCE_FAR * 10, rows[y][x] + extra)


def _validate_terrain_rows(
    rows: list[list[str]],
    *,
    width: int,
    height: int,
) -> None:
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError(
            "Terrain rows do not match natural geography dimensions: "
            f"expected={width}x{height}"
        )
