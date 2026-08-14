from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .geography_draft import NaturalGeographyModel
from .geography_guidance import terrain_profile_items

MOISTURE_SCALE = 1_000
FOREST_DEPTH_MAX = 4
PROXIMITY_DISTANCE_FAR = 9
PROXIMITY_MAX_EXACT = PROXIMITY_DISTANCE_FAR - 1
TREE_TERRAIN = "tree_blocker"
ROAD_TERRAINS = frozenset(
    {
        "old_overgrown_road",
        "road",
        "path",
        "dirt_road",
        "overgrown_road",
    }
)
WATER_TERRAINS = frozenset(
    {
        "water",
        "water_slow",
        "shallow_water",
        "deep_water",
        "deep_water_blocker",
        "standing_water",
        "swamp",
    }
)

_CHAMFER_ORTHOGONAL_COST = 10
_CHAMFER_DIAGONAL_COST = 14
_CHAMFER_FAR_COST = PROXIMITY_DISTANCE_FAR * _CHAMFER_ORTHOGONAL_COST

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
FLORA_REGION_NAMES: tuple[str, ...] = (
    "dry_grassland",
    "open_meadow",
    "lush_meadow",
    "scrubland",
    "wet_meadow",
    "marshland",
)
FLORA_REGION_CODES = {
    name: index for index, name in enumerate(FLORA_REGION_NAMES)
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
    flora_region_rows: list[list[int]]
    slope_band_rows: list[list[int]]
    forest_depth_rows: list[list[int]]
    forest_distance_rows: list[list[int]]
    water_distance_rows: list[list[int]]
    road_distance_rows: list[list[int]]
    structure_distance_rows: list[list[int]]
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
                "road_terrains": sorted(ROAD_TERRAINS),
                "water_terrains": sorted(WATER_TERRAINS),
                "structure_source": "structure_type_nonzero",
                "forest_depth_max": FOREST_DEPTH_MAX,
                "proximity_max_exact_tiles": PROXIMITY_MAX_EXACT,
                "proximity_far_value": PROXIMITY_DISTANCE_FAR,
                "proximity_metric": "8_neighbor_chamfer_10_14",
                "flora_region_derivation": "region_profile_plus_moisture_v1",
            },
            "dictionaries": {
                "region_profile": {
                    str(code): name
                    for name, code in REGION_PROFILE_CODES.items()
                },
                "flora_region": {
                    str(code): name
                    for name, code in FLORA_REGION_CODES.items()
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
                "flora_region": {
                    "format": "uint8_rows",
                    "rows": self.flora_region_rows,
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
                "forest_distance": _distance_grid_payload(
                    self.forest_distance_rows,
                ),
                "water_distance": _distance_grid_payload(
                    self.water_distance_rows,
                ),
                "road_distance": _distance_grid_payload(
                    self.road_distance_rows,
                ),
                "structure_distance": _distance_grid_payload(
                    self.structure_distance_rows,
                ),
            },
            "summary": self.summary,
        }


def build_environment_context(
    *,
    natural_geography: NaturalGeographyModel,
    terrain_rows: list[list[str]],
    structure_type_rows: list[list[int]],
) -> EnvironmentContextResult:
    """Build deterministic ecological context from existing world semantics.

    Args:
        natural_geography: Natural geography produced before terrain placement.
        terrain_rows: Final semantic terrain rows from the public map package.
        structure_type_rows: Final semantic structure-type grid where zero means
            no structure.

    Returns:
        Derived environment-context grids and diagnostics.

    Raises:
        ValueError: If input dimensions are inconsistent or region indices are invalid.
    """
    width = natural_geography.width
    height = natural_geography.height
    _validate_terrain_rows(terrain_rows, width=width, height=height)
    _validate_integer_rows(
        structure_type_rows,
        width=width,
        height=height,
        name="structure_type",
    )
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
    flora_region_rows = build_flora_region_rows(
        moisture_rows=moisture_rows,
        region_profile_rows=region_profile_rows,
    )
    forest_depth_rows = build_forest_depth_rows(terrain_rows)
    forest_distance_rows = build_forest_distance_rows(terrain_rows)
    water_distance_rows = build_water_distance_rows(terrain_rows)
    road_distance_rows = build_road_distance_rows(terrain_rows)
    structure_distance_rows = build_structure_distance_rows(structure_type_rows)

    return EnvironmentContextResult(
        width=width,
        height=height,
        moisture_rows=moisture_rows,
        region_profile_rows=region_profile_rows,
        flora_region_rows=flora_region_rows,
        slope_band_rows=slope_band_rows,
        forest_depth_rows=forest_depth_rows,
        forest_distance_rows=forest_distance_rows,
        water_distance_rows=water_distance_rows,
        road_distance_rows=road_distance_rows,
        structure_distance_rows=structure_distance_rows,
        summary=_build_summary(
            moisture_rows=moisture_rows,
            region_profile_rows=region_profile_rows,
            flora_region_rows=flora_region_rows,
            slope_band_rows=slope_band_rows,
            forest_depth_rows=forest_depth_rows,
            water_distance_rows=water_distance_rows,
            road_distance_rows=road_distance_rows,
            structure_distance_rows=structure_distance_rows,
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
        next_depth = min(FOREST_DEPTH_MAX, depth + 1)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if terrain_rows[ny][nx] != TREE_TERRAIN or depths[ny][nx] != 0:
                continue
            depths[ny][nx] = next_depth
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
    return _build_proximity_distance_rows(
        [[terrain == TREE_TERRAIN for terrain in row] for row in terrain_rows]
    )


def build_water_distance_rows(terrain_rows: list[list[str]]) -> list[list[int]]:
    """Return approximate distance from every tile to semantic water.

    Args:
        terrain_rows: Rectangular semantic terrain rows.

    Returns:
        Tile-distance rows where water is zero and nine means nine or more
        tiles away.
    """
    return _build_proximity_distance_rows(
        [[is_water_terrain(terrain) for terrain in row] for row in terrain_rows]
    )


def build_road_distance_rows(terrain_rows: list[list[str]]) -> list[list[int]]:
    """Return approximate distance from every tile to semantic roads.

    Args:
        terrain_rows: Rectangular semantic terrain rows.

    Returns:
        Tile-distance rows where road is zero and nine means nine or more
        tiles away.
    """
    return _build_proximity_distance_rows(
        [[is_road_terrain(terrain) for terrain in row] for row in terrain_rows]
    )


def build_structure_distance_rows(
    structure_type_rows: list[list[int]],
) -> list[list[int]]:
    """Return approximate distance to semantic structural occupancy.

    Args:
        structure_type_rows: Rectangular structure-type rows where zero means
            no structural tile.

    Returns:
        Tile-distance rows where structural tiles are zero and nine means nine
        or more tiles away.
    """
    return _build_proximity_distance_rows(
        [[value != 0 for value in row] for row in structure_type_rows]
    )


def is_road_terrain(terrain: object) -> bool:
    """Return whether a semantic terrain type represents a road.

    Args:
        terrain: Semantic terrain value.

    Returns:
        True when the value belongs to the public road terrain family.
    """
    return isinstance(terrain, str) and terrain in ROAD_TERRAINS


def is_water_terrain(terrain: object) -> bool:
    """Return whether a semantic terrain type represents standing water.

    Args:
        terrain: Semantic terrain value.

    Returns:
        True when the value belongs to the public water terrain family.
    """
    return isinstance(terrain, str) and terrain in WATER_TERRAINS


def _distance_grid_payload(rows: list[list[int]]) -> dict[str, Any]:
    return {
        "format": "uint8_rows",
        "range": [0, PROXIMITY_DISTANCE_FAR],
        "far_value": PROXIMITY_DISTANCE_FAR,
        "rows": rows,
    }


def _build_proximity_distance_rows(
    source_rows: list[list[bool]],
) -> list[list[int]]:
    height = len(source_rows)
    width = len(source_rows[0]) if height else 0
    if width == 0 or height == 0:
        return []
    if any(len(row) != width for row in source_rows):
        raise ValueError("Proximity source rows must be rectangular")

    distances = [
        [0 if is_source else _CHAMFER_FAR_COST for is_source in row]
        for row in source_rows
    ]

    for y in range(height):
        for x in range(width):
            if distances[y][x] == 0:
                continue
            distances[y][x] = min(
                distances[y][x],
                _chamfer_neighbor_cost(
                    distances,
                    x=x - 1,
                    y=y,
                    extra=_CHAMFER_ORTHOGONAL_COST,
                ),
                _chamfer_neighbor_cost(
                    distances,
                    x=x,
                    y=y - 1,
                    extra=_CHAMFER_ORTHOGONAL_COST,
                ),
                _chamfer_neighbor_cost(
                    distances,
                    x=x - 1,
                    y=y - 1,
                    extra=_CHAMFER_DIAGONAL_COST,
                ),
                _chamfer_neighbor_cost(
                    distances,
                    x=x + 1,
                    y=y - 1,
                    extra=_CHAMFER_DIAGONAL_COST,
                ),
            )

    for y in range(height - 1, -1, -1):
        for x in range(width - 1, -1, -1):
            if distances[y][x] == 0:
                continue
            distances[y][x] = min(
                distances[y][x],
                _chamfer_neighbor_cost(
                    distances,
                    x=x + 1,
                    y=y,
                    extra=_CHAMFER_ORTHOGONAL_COST,
                ),
                _chamfer_neighbor_cost(
                    distances,
                    x=x,
                    y=y + 1,
                    extra=_CHAMFER_ORTHOGONAL_COST,
                ),
                _chamfer_neighbor_cost(
                    distances,
                    x=x + 1,
                    y=y + 1,
                    extra=_CHAMFER_DIAGONAL_COST,
                ),
                _chamfer_neighbor_cost(
                    distances,
                    x=x - 1,
                    y=y + 1,
                    extra=_CHAMFER_DIAGONAL_COST,
                ),
            )

    return [
        [
            min(
                PROXIMITY_DISTANCE_FAR,
                (cost + (_CHAMFER_ORTHOGONAL_COST // 2))
                // _CHAMFER_ORTHOGONAL_COST,
            )
            for cost in row
        ]
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


def build_flora_region_rows(
    *,
    moisture_rows: list[list[int]],
    region_profile_rows: list[list[int]],
) -> list[list[int]]:
    """Build broad flora regions without reading the elevation grid directly.

    The field intentionally describes the ecological character of the ground,
    not whether a tile is forest, water, road, or structure. Those semantics
    remain independent Environment Context signals and may be layered on top
    by consumers such as a FloraResolver.

    Args:
        moisture_rows: Quantized public moisture values in the 0..1000 range.
        region_profile_rows: Public terrain-guidance profile codes.

    Returns:
        Flora-region codes aligned with the source grids.

    Raises:
        ValueError: If source grids are malformed or contain unsupported codes.
    """
    height = len(moisture_rows)
    width = len(moisture_rows[0]) if height else 0
    _validate_integer_rows(
        moisture_rows,
        width=width,
        height=height,
        name="moisture",
    )
    _validate_integer_rows(
        region_profile_rows,
        width=width,
        height=height,
        name="region_profile",
    )

    rows: list[list[int]] = []
    for y in range(height):
        output_row: list[int] = []
        for x in range(width):
            moisture = moisture_rows[y][x]
            if not 0 <= moisture <= MOISTURE_SCALE:
                raise ValueError(
                    "Moisture value is outside public 0..1000 range: "
                    f"x={x}, y={y}, value={moisture}"
                )
            profile_code = region_profile_rows[y][x]
            if not 0 <= profile_code < len(REGION_PROFILE_NAMES):
                raise ValueError(
                    "Region profile code is out of range while building flora region: "
                    f"x={x}, y={y}, code={profile_code}"
                )
            profile = REGION_PROFILE_NAMES[profile_code]
            output_row.append(_flora_region_code(profile, moisture))
        rows.append(output_row)
    return rows


def _flora_region_code(region_profile: str, moisture: int) -> int:
    """Return one broad flora-region code for a profile and moisture value."""
    if region_profile == "wet_lowland":
        if moisture >= 720:
            return FLORA_REGION_CODES["marshland"]
        if moisture >= 430:
            return FLORA_REGION_CODES["wet_meadow"]
        return FLORA_REGION_CODES["lush_meadow"]

    if region_profile in {"dense_forest", "woodland"}:
        if moisture < 260:
            return FLORA_REGION_CODES["scrubland"]
        if moisture >= 660:
            return FLORA_REGION_CODES["wet_meadow"]
        return FLORA_REGION_CODES["lush_meadow"]

    if region_profile in {"upland", "open_plateau", "alpine"}:
        if moisture < 300:
            return FLORA_REGION_CODES["dry_grassland"]
        if moisture < 560:
            return FLORA_REGION_CODES["open_meadow"]
        return FLORA_REGION_CODES["lush_meadow"]

    if region_profile == "open_plain":
        if moisture < 240:
            return FLORA_REGION_CODES["dry_grassland"]
        if moisture < 480:
            return FLORA_REGION_CODES["open_meadow"]
        if moisture < 680:
            return FLORA_REGION_CODES["lush_meadow"]
        return FLORA_REGION_CODES["wet_meadow"]

    raise ValueError(f"Unsupported region profile for flora region: {region_profile!r}")


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
    flora_region_rows: list[list[int]],
    slope_band_rows: list[list[int]],
    forest_depth_rows: list[list[int]],
    water_distance_rows: list[list[int]],
    road_distance_rows: list[list[int]],
    structure_distance_rows: list[list[int]],
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
    flora_region_counts = Counter(
        FLORA_REGION_NAMES[value]
        for row in flora_region_rows
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
        "flora_region_tiles": dict(sorted(flora_region_counts.items())),
        "slope_band_tiles": dict(sorted(slope_counts.items())),
        "forest": {
            "tiles": total - forest_counts.get(0, 0),
            "edge_tiles": forest_counts.get(1, 0),
            "deep_tiles": forest_counts.get(FOREST_DEPTH_MAX, 0),
        },
        "proximity": {
            "tiles_near_water_4": _count_within(water_distance_rows, 4),
            "tiles_near_roads_4": _count_within(road_distance_rows, 4),
            "tiles_near_structures_5": _count_within(
                structure_distance_rows,
                5,
            ),
        },
    }


def _count_within(rows: list[list[int]], maximum: int) -> int:
    return sum(value <= maximum for row in rows for value in row)


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
        return _CHAMFER_FAR_COST
    if x < 0 or x >= len(rows[y]):
        return _CHAMFER_FAR_COST
    return min(_CHAMFER_FAR_COST, rows[y][x] + extra)


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


def _validate_integer_rows(
    rows: list[list[int]],
    *,
    width: int,
    height: int,
    name: str,
) -> None:
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError(
            f"{name} rows do not match natural geography dimensions: "
            f"expected={width}x{height}"
        )
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for row in rows
        for value in row
    ):
        raise ValueError(f"{name} rows must contain integer values")
