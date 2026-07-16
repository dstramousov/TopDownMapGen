from __future__ import annotations

import argparse
import json
import logging
import math
import random
import secrets
from time import perf_counter
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Iterable

try:
    from .terrain_guidance import TerrainGuidance, TerrainGuidanceError
except ImportError:  # Direct script execution by LegacyEngineRunner.
    from terrain_guidance import TerrainGuidance, TerrainGuidanceError


LOGGER = logging.getLogger(__name__)


class ConfigError(ValueError):
    """Raised when generator configuration is invalid."""


class GenerationError(RuntimeError):
    """Raised when map generation fails."""


class TileType(StrEnum):
    """Tile types used by the ASCII generator."""

    GRASS = "+"
    PATH = "."
    TREE = "T"
    BUSH = "b"
    FLOWER = "f"
    MUSHROOM = "m"
    WATER = "w"
    CRACKED_GROUND = "c"
    RUIN_WALL = "#"
    RUIN_FLOOR = "R"
    START = "S"
    GOAL = "G"


class RegionKind(StrEnum):
    """High-level region kinds."""

    FOREST = "forest"
    SMALL_RUIN = "small_ruin"
    MEDIUM_RUIN = "medium_ruin"
    CENTRAL_RUIN_CLEARING = "central_ruin_clearing"
    START = "start"
    GOAL = "goal"



MIN_TUNING_SCALE = 0.0
MAX_TUNING_SCALE = 10.0


@dataclass(frozen=True, slots=True)
class GenerationTuning:
    """User-facing world density tuning scales."""

    water_scale: float = 1.0
    water_patch_count_scale: float = 1.0
    water_patch_size_scale: float = 1.0
    water_patch_density: float = 0.62
    forest_scale: float = 1.0
    open_space_scale: float = 1.0
    ruins_scale: float = 1.0
    buildings_scale: float = 1.0
    road_width_scale: float = 1.0
    decoration_scale: float = 1.0
    bunker_scale: float = 1.0
    bush_density: float = 0.30
    bush_thicket_count: int = 14

    @classmethod
    def from_raw(cls, value: object) -> "GenerationTuning":
        """Build tuning from an optional config object."""
        if not isinstance(value, dict):
            return cls()
        defaults = cls()
        return cls(
            water_scale=_sanitize_scale(value.get("water_scale", defaults.water_scale), "water_scale"),
            water_patch_count_scale=_sanitize_scale(
                value.get("water_patch_count_scale", defaults.water_patch_count_scale),
                "water_patch_count_scale",
            ),
            water_patch_size_scale=_sanitize_scale(
                value.get("water_patch_size_scale", defaults.water_patch_size_scale),
                "water_patch_size_scale",
            ),
            water_patch_density=_sanitize_ratio(
                value.get("water_patch_density", defaults.water_patch_density),
                "water_patch_density",
            ),
            forest_scale=_sanitize_scale(value.get("forest_scale", defaults.forest_scale), "forest_scale"),
            open_space_scale=_sanitize_scale(
                value.get("open_space_scale", defaults.open_space_scale),
                "open_space_scale",
            ),
            ruins_scale=_sanitize_scale(value.get("ruins_scale", defaults.ruins_scale), "ruins_scale"),
            buildings_scale=_sanitize_scale(
                value.get("buildings_scale", defaults.buildings_scale),
                "buildings_scale",
            ),
            road_width_scale=_sanitize_scale(
                value.get("road_width_scale", defaults.road_width_scale),
                "road_width_scale",
            ),
            decoration_scale=_sanitize_scale(
                value.get("decoration_scale", defaults.decoration_scale),
                "decoration_scale",
            ),
            bunker_scale=_sanitize_scale(value.get("bunker_scale", defaults.bunker_scale), "bunker_scale"),
            bush_density=_sanitize_ratio(value.get("bush_density", defaults.bush_density), "bush_density"),
            bush_thicket_count=_sanitize_nonnegative_int(
                value.get("bush_thicket_count", defaults.bush_thicket_count),
                "bush_thicket_count",
                defaults.bush_thicket_count,
            ),
        )

    def to_dict(self) -> dict[str, float]:
        """Return JSON-serializable tuning values."""
        return {
            "water_scale": self.water_scale,
            "water_patch_count_scale": self.water_patch_count_scale,
            "water_patch_size_scale": self.water_patch_size_scale,
            "water_patch_density": self.water_patch_density,
            "forest_scale": self.forest_scale,
            "open_space_scale": self.open_space_scale,
            "ruins_scale": self.ruins_scale,
            "buildings_scale": self.buildings_scale,
            "road_width_scale": self.road_width_scale,
            "decoration_scale": self.decoration_scale,
            "bunker_scale": self.bunker_scale,
            "bush_density": self.bush_density,
            "bush_thicket_count": self.bush_thicket_count,
        }


def _sanitize_float(value: object, key: str, default: float) -> float:
    """Convert a user-provided tuning value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid generation_tuning.%s=%r; using %.2f", key, value, default)
        return default


def _sanitize_scale(value: object, key: str) -> float:
    """Clamp a user-provided scale to a safe range."""
    scale = _sanitize_float(value, key, 1.0)
    if scale < MIN_TUNING_SCALE or scale > MAX_TUNING_SCALE:
        LOGGER.warning(
            "generation_tuning.%s=%s is outside %.1f..%.1f; clamping",
            key,
            scale,
            MIN_TUNING_SCALE,
            MAX_TUNING_SCALE,
        )
    return max(MIN_TUNING_SCALE, min(scale, MAX_TUNING_SCALE))



def _sanitize_nonnegative_int(value: object, key: str, default: int) -> int:
    """Return a non-negative integer tuning value."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid generation_tuning.%s=%r; using %s", key, value, default)
        return default
    if parsed < 0:
        LOGGER.warning("generation_tuning.%s=%s is negative; clamping", key, parsed)
    return max(0, parsed)


def _sanitize_ratio(value: object, key: str) -> float:
    """Clamp a user-provided ratio to the inclusive 0..1 range."""
    ratio = _sanitize_float(value, key, 0.62)
    if ratio < 0.0 or ratio > 1.0:
        LOGGER.warning(
            "generation_tuning.%s=%s is outside 0.0..1.0; clamping",
            key,
            ratio,
        )
    return max(0.0, min(ratio, 1.0))


@dataclass(frozen=True, slots=True)
class Point:
    """A 2D integer point on the tile grid."""

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Edge:
    """Undirected region graph edge."""

    a: int
    b: int
    is_loop: bool = False


@dataclass(frozen=True, slots=True)
class Rect:
    """A rectangular tile area."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> Point:
        """Return rectangle center point."""
        return Point((self.left + self.right) // 2, (self.top + self.bottom) // 2)


@dataclass(slots=True)
class Region:
    """A high-level map region."""

    region_id: int
    center: Point
    kind: RegionKind = RegionKind.FOREST
    entrances: list[Point] = field(default_factory=list)
    entrance_cursor: int = 0

    def connection_point(self) -> Point:
        """Return a connection point for path carving.

        Returns:
            Region center or a rotating ruin entrance.
        """
        if not self.entrances:
            return self.center

        point = self.entrances[self.entrance_cursor % len(self.entrances)]
        self.entrance_cursor += 1
        return point


@dataclass(frozen=True, slots=True)
class PublicConfig:
    """Small public generator configuration."""

    seed: int | str
    map_width_tiles: int
    map_height_tiles: int
    chunk_width_tiles: int
    chunk_height_tiles: int
    biome_profile: str
    generation_tuning: GenerationTuning = field(default_factory=GenerationTuning)

    @classmethod
    def from_json_file(cls, path: Path) -> PublicConfig:
        """Load public configuration from JSON file.

        Args:
            path: JSON configuration path.

        Returns:
            Parsed public configuration.

        Raises:
            ConfigError: If configuration is invalid.
        """
        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigError(f"Failed to read config: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON config: {path}") from exc

        try:
            tuning = GenerationTuning.from_raw(raw_data.pop("generation_tuning", None))
            config = cls(**raw_data, generation_tuning=tuning)
        except TypeError as exc:
            raise ConfigError(f"Invalid config fields: {exc}") from exc

        config.validate()
        return config

    def validate(self) -> None:
        """Validate public configuration.

        Raises:
            ConfigError: If configuration values are invalid.
        """
        if not (isinstance(self.seed, int) or self.seed == "random"):
            raise ConfigError('Seed must be an integer or the string "random"')

        if self.map_width_tiles <= 0 or self.map_height_tiles <= 0:
            raise ConfigError("Map dimensions must be positive")

        if self.chunk_width_tiles <= 0 or self.chunk_height_tiles <= 0:
            raise ConfigError("Chunk dimensions must be positive")

        if self.map_width_tiles % self.chunk_width_tiles != 0:
            raise ConfigError("Map width must be divisible by chunk width")

        if self.map_height_tiles % self.chunk_height_tiles != 0:
            raise ConfigError("Map height must be divisible by chunk height")

        if self.map_width_tiles < 96 or self.map_height_tiles < 80:
            raise ConfigError("Map is too small for forest_ruins profile")

        if self.biome_profile != "forest_ruins":
            raise ConfigError('Only "forest_ruins" biome profile is supported in v0.15')

    def resolve_seed(self) -> int:
        """Resolve configured seed.

        Returns:
            Effective integer seed.
        """
        if isinstance(self.seed, int):
            return self.seed

        return secrets.randbits(64)


@dataclass(frozen=True, slots=True)
class DerivedConfig:
    """Internal derived generator configuration."""

    chunk_cols: int
    chunk_rows: int
    chunk_count: int
    area_tiles: int
    region_count: int
    small_ruin_count: int
    medium_ruin_count: int
    central_ruin_count: int
    loop_target_count: int
    nearest_neighbor_links: int
    connected_pocket_count: int
    tree_cluster_count: int
    flower_patch_count: int
    mushroom_patch_count: int
    water_patch_count: int
    water_patch_min_radius: int
    water_patch_max_radius: int
    water_patch_density: float
    cracked_ground_patch_count: int
    clearing_min_radius: int
    clearing_max_radius: int
    central_clearing_radius: int
    old_road_corridor_min_width: int
    old_road_corridor_max_width: int
    old_road_spine_width: int
    old_road_overgrowth_chance: float
    old_road_side_grass_chance: float
    small_ruin_min_width: int
    small_ruin_max_width: int
    small_ruin_min_height: int
    small_ruin_max_height: int
    medium_ruin_min_width: int
    medium_ruin_max_width: int
    medium_ruin_min_height: int
    medium_ruin_max_height: int
    settlement_min_buildings: int
    settlement_max_buildings: int
    tree_cluster_min_radius: int
    tree_cluster_max_radius: int
    bush_ring_thickness: int
    scattered_bush_count: int
    connected_pocket_min_radius: int
    connected_pocket_max_radius: int
    cleanup_small_component_max_size: int
    min_walkable_ratio: float
    max_walkable_ratio: float
    max_dead_end_ratio: float
    min_grass_to_path_ratio: float
    max_generation_attempts: int
    max_hidden_clearings: int
    big_forest_component_min_size: int
    hidden_clearing_min_radius: int
    hidden_clearing_max_radius: int

    @classmethod
    def from_public(cls, public: PublicConfig) -> DerivedConfig:
        """Derive internal settings from public configuration.

        Args:
            public: Public configuration.

        Returns:
            Derived internal configuration.
        """
        chunk_cols = public.map_width_tiles // public.chunk_width_tiles
        chunk_rows = public.map_height_tiles // public.chunk_height_tiles
        chunk_count = chunk_cols * chunk_rows
        area_tiles = public.map_width_tiles * public.map_height_tiles

        # Content density scales by map area/chunk count, while individual object sizes
        # stay within profile-specific bounds. Larger maps get more regions, not giant ruins.
        tuning = public.generation_tuning
        region_count = cls._clamp(round(chunk_count / 4.2), 18, 140)
        small_ruin_count = cls._clamp(round(region_count * 0.34 * tuning.ruins_scale), 0, 64)
        medium_ruin_count = cls._clamp(round(region_count * 0.22 * tuning.ruins_scale), 0, 36)
        loop_target_count = cls._clamp(round(region_count * 0.55), 8, 70)
        connected_pocket_count = cls._clamp(
            round(region_count * 1.75 * tuning.open_space_scale),
            0,
            260,
        )
        tree_cluster_count = cls._clamp(round(area_tiles / 560 * tuning.forest_scale), 0, 800)
        flower_patch_count = cls._clamp(round(area_tiles / 850 * tuning.decoration_scale), 0, 320)
        mushroom_patch_count = cls._clamp(round(area_tiles / 1250 * tuning.decoration_scale), 0, 220)
        water_count_scale = tuning.water_scale * tuning.water_patch_count_scale
        water_patch_count = cls._clamp(round(area_tiles / 3200 * water_count_scale), 0, 280)
        water_size_scale = tuning.water_patch_size_scale
        water_patch_min_radius = cls._clamp(round(1 * water_size_scale), 1, 8)
        water_patch_max_radius = cls._clamp(round(3 * water_size_scale), water_patch_min_radius, 12)
        water_patch_density = tuning.water_patch_density
        cracked_ground_patch_count = cls._clamp(
            round(region_count * 0.85 * tuning.decoration_scale),
            0,
            180,
        )

        sqrt_factor = math.sqrt(area_tiles / (160 * 96))
        central_clearing_radius = cls._clamp(
            round((16 + sqrt_factor * 2.8) * max(0.6, tuning.open_space_scale)),
            8,
            36,
        )
        road_width_bonus = max(-2, min(4, round(tuning.road_width_scale - 1.0)))
        road_min_width = cls._clamp(4 + road_width_bonus, 1, 10)
        road_max_width = cls._clamp(6 + road_width_bonus, road_min_width, 12)
        settlement_min_buildings = cls._clamp(round(7 * tuning.buildings_scale), 0, 18)
        settlement_max_buildings = cls._clamp(round(11 * tuning.buildings_scale), settlement_min_buildings, 24)

        return cls(
            chunk_cols=chunk_cols,
            chunk_rows=chunk_rows,
            chunk_count=chunk_count,
            area_tiles=area_tiles,
            region_count=region_count,
            small_ruin_count=small_ruin_count,
            medium_ruin_count=medium_ruin_count,
            central_ruin_count=1,
            loop_target_count=loop_target_count,
            nearest_neighbor_links=4,
            connected_pocket_count=connected_pocket_count,
            tree_cluster_count=tree_cluster_count,
            flower_patch_count=flower_patch_count,
            mushroom_patch_count=mushroom_patch_count,
            water_patch_count=water_patch_count,
            water_patch_min_radius=water_patch_min_radius,
            water_patch_max_radius=water_patch_max_radius,
            water_patch_density=water_patch_density,
            cracked_ground_patch_count=cracked_ground_patch_count,
            clearing_min_radius=7,
            clearing_max_radius=13,
            central_clearing_radius=central_clearing_radius,
            old_road_corridor_min_width=road_min_width,
            old_road_corridor_max_width=road_max_width,
            old_road_spine_width=1,
            old_road_overgrowth_chance=0.13,
            old_road_side_grass_chance=0.76,
            small_ruin_min_width=8,
            small_ruin_max_width=13,
            small_ruin_min_height=6,
            small_ruin_max_height=10,
            medium_ruin_min_width=14,
            medium_ruin_max_width=24,
            medium_ruin_min_height=10,
            medium_ruin_max_height=17,
            settlement_min_buildings=settlement_min_buildings,
            settlement_max_buildings=settlement_max_buildings,
            tree_cluster_min_radius=1,
            tree_cluster_max_radius=3,
            bush_ring_thickness=1,
            scattered_bush_count=cls._clamp(round(area_tiles * tuning.bush_density * 0.02), 0, 2000),
            connected_pocket_min_radius=3,
            connected_pocket_max_radius=7,
            cleanup_small_component_max_size=32,
            min_walkable_ratio=0.34,
            max_walkable_ratio=0.72,
            max_dead_end_ratio=0.22,
            min_grass_to_path_ratio=1.80,
            max_generation_attempts=25,
            max_hidden_clearings=cls._clamp(round(chunk_count / 32), 1, 8),
            big_forest_component_min_size=cls._clamp(round(area_tiles / 70), 140, 1400),
            hidden_clearing_min_radius=4,
            hidden_clearing_max_radius=7,
        )

    @staticmethod
    def _clamp(value: int, minimum: int, maximum: int) -> int:
        return max(minimum, min(value, maximum))


class MapGrid:
    """Mutable 2D tile grid."""

    def __init__(self, width: int, height: int, fill: TileType) -> None:
        """Initialize the grid.

        Args:
            width: Grid width.
            height: Grid height.
            fill: Initial tile.
        """
        self.width = width
        self.height = height
        self._tiles = [[fill for _ in range(width)] for _ in range(height)]

    def is_inside(self, point: Point) -> bool:
        """Check whether point is inside the grid."""
        return 0 <= point.x < self.width and 0 <= point.y < self.height

    def get_tile(self, point: Point) -> TileType:
        """Get tile at point."""
        return self._tiles[point.y][point.x]

    def set_tile(self, point: Point, tile_type: TileType) -> None:
        """Set tile at point."""
        if self.is_inside(point):
            self._tiles[point.y][point.x] = tile_type

    def rows_as_text(self) -> list[str]:
        """Convert grid to ASCII rows."""
        return ["".join(tile.value for tile in row) for row in self._tiles]

    def neighbors_4(self, point: Point) -> Iterable[Point]:
        """Yield 4-directional neighbor points."""
        for candidate in (
            Point(point.x + 1, point.y),
            Point(point.x - 1, point.y),
            Point(point.x, point.y + 1),
            Point(point.x, point.y - 1),
        ):
            if self.is_inside(candidate):
                yield candidate


class MapValidator:
    """Validation and metrics for generated maps."""

    WALKABLE_TILES = {
        TileType.GRASS,
        TileType.PATH,
        TileType.BUSH,
        TileType.FLOWER,
        TileType.MUSHROOM,
        TileType.WATER,
        TileType.CRACKED_GROUND,
        TileType.RUIN_FLOOR,
        TileType.START,
        TileType.GOAL,
    }

    PATH_NETWORK_TILES = {
        TileType.PATH,
        TileType.CRACKED_GROUND,
        TileType.RUIN_FLOOR,
        TileType.START,
        TileType.GOAL,
    }

    def __init__(self, grid: MapGrid) -> None:
        """Initialize validator."""
        self._grid = grid

    def is_walkable(self, point: Point) -> bool:
        """Check whether point is walkable."""
        return self._grid.get_tile(point) in self.WALKABLE_TILES

    def is_path_network(self, point: Point) -> bool:
        """Check whether point belongs to path network."""
        return self._grid.get_tile(point) in self.PATH_NETWORK_TILES

    def reachable_distances(self, start: Point) -> dict[Point, int]:
        """Find reachable walkable tiles and distances."""
        return self._distances(start, self.is_walkable)

    def path_network_distances(self, start: Point) -> dict[Point, int]:
        """Find reachable path-network tiles and distances."""
        return self._distances(start, self.is_path_network)

    def walkable_ratio(self) -> float:
        """Calculate walkable ratio."""
        walkable_count = 0
        for y in range(self._grid.height):
            for x in range(self._grid.width):
                if self.is_walkable(Point(x, y)):
                    walkable_count += 1
        return walkable_count / (self._grid.width * self._grid.height)

    def dead_end_ratio(self) -> float:
        """Calculate dead-end ratio among walkable tiles."""
        walkable_count = 0
        dead_end_count = 0

        for y in range(self._grid.height):
            for x in range(self._grid.width):
                point = Point(x, y)
                if not self.is_walkable(point):
                    continue

                walkable_count += 1
                open_neighbors = sum(
                    1
                    for neighbor in self._grid.neighbors_4(point)
                    if self.is_walkable(neighbor)
                )
                if open_neighbors <= 1:
                    dead_end_count += 1

        return dead_end_count / max(1, walkable_count)

    def components(self) -> list[set[Point]]:
        """Find all walkable components."""
        return self._components(self.is_walkable)

    def path_network_components(self) -> list[set[Point]]:
        """Find all path-network components."""
        return self._components(self.is_path_network)

    def _distances(self, start: Point, predicate) -> dict[Point, int]:
        if not predicate(start):
            return {}

        distances = {start: 0}
        queue: deque[Point] = deque([start])

        while queue:
            current = queue.popleft()
            for neighbor in self._grid.neighbors_4(current):
                if neighbor in distances or not predicate(neighbor):
                    continue
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)

        return distances

    def _components(self, predicate) -> list[set[Point]]:
        remaining = {
            Point(x, y)
            for y in range(self._grid.height)
            for x in range(self._grid.width)
            if predicate(Point(x, y))
        }
        components: list[set[Point]] = []

        while remaining:
            start = next(iter(remaining))
            component = set(self._distances(start, predicate))
            components.append(component)
            remaining -= component

        components.sort(key=len, reverse=True)
        return components


class MapGenerator:
    """Top-down forest and ruins map generator."""

    def __init__(
        self,
        public_config: PublicConfig,
        terrain_guidance: TerrainGuidance | None = None,
    ) -> None:
        """Initialize generator.

        Args:
            public_config: Public generator configuration.
            terrain_guidance: Optional precomputed geography context.
        """
        self._public = public_config
        self._derived = DerivedConfig.from_public(public_config)
        self._effective_seed = public_config.resolve_seed()
        self._rng = random.Random(self._effective_seed)
        self._guidance = terrain_guidance
        self._grid = MapGrid(
            public_config.map_width_tiles,
            public_config.map_height_tiles,
            TileType.TREE,
        )
        self._regions: list[Region] = []
        self._edges: list[Edge] = []
        self._start_region_id = 0
        self._goal_region_id = 0
        self._central_region_id = 0
        self._protected_path: set[Point] = set()
        self._connectivity_repair_metrics: dict[str, int] = {
            "components_before": 0,
            "components_after": 0,
            "filled_components": 0,
            "connected_components": 0,
            "failed_repairs": 0,
            "tiles_changed": 0,
        }
        self._terrain_guidance_metrics: dict[str, int | float | bool | str] = {
            "enabled": terrain_guidance is not None,
            "elevation_style": terrain_guidance.elevation_style if terrain_guidance else "disabled",
            "region_candidates_evaluated": 0,
            "region_candidates_rejected_steep": 0,
            "region_steep_fallbacks": 0,
            "ruin_regions_relocated": 0,
            "guided_road_routes": 0,
            "fallback_road_routes": 0,
            "road_sample_tiles": 0,
            "road_slope_sum": 0.0,
            "road_steep_tiles": 0,
            "road_cliff_tiles": 0,
            "open_ground_barrier_tiles_skipped": 0,
            "path_barrier_tiles_skipped": 0,
            "wetland_candidates_rejected": 0,
            "forest_candidates_rejected": 0,
            "ruin_bad_footprints": 0,
        }

    def effective_seed(self) -> int:
        """Return effective seed."""
        return self._effective_seed

    def connectivity_repair_metrics(self) -> dict[str, int]:
        """Return final walkable connectivity repair metrics."""
        return dict(self._connectivity_repair_metrics)

    def terrain_guidance_metrics(self) -> dict[str, int | float | bool | str]:
        """Return terrain adaptation diagnostics."""
        metrics = dict(self._terrain_guidance_metrics)
        metrics["schema_version"] = "terrain-guidance-report-v3"
        sample_tiles = int(metrics.pop("road_sample_tiles", 0))
        slope_sum = float(metrics.pop("road_slope_sum", 0.0))
        metrics["road_tiles_sampled"] = sample_tiles
        metrics["average_road_slope"] = round(slope_sum / max(1, sample_tiles), 6)
        return metrics

    def derived_config(self) -> DerivedConfig:
        """Return derived configuration."""
        return self._derived

    def start_point(self) -> Point:
        """Return start point."""
        return self._regions[self._start_region_id].center

    def goal_point(self) -> Point:
        """Return goal point."""
        return self._regions[self._goal_region_id].center

    def central_point(self) -> Point:
        """Return central ruin clearing point."""
        return self._regions[self._central_region_id].center

    def regions(self) -> list[Region]:
        """Return generated regions.

        Returns:
            Copy of generated high-level regions.
        """
        return list(self._regions)

    def edges(self) -> list[Edge]:
        """Return generated region graph edges.

        Returns:
            Copy of generated graph edges.
        """
        return list(self._edges)

    def generate(self) -> MapGrid:
        """Generate map.

        Returns:
            Generated grid.

        Raises:
            GenerationError: If validation fails.
        """
        LOGGER.info("GENERATION START")
        LOGGER.info("Effective seed: %s", self._effective_seed)
        LOGGER.info(
            "Public config: size=%sx%s chunk=%sx%s biome=%s",
            self._public.map_width_tiles,
            self._public.map_height_tiles,
            self._public.chunk_width_tiles,
            self._public.chunk_height_tiles,
            self._public.biome_profile,
        )
        LOGGER.info("Generation tuning: %s", self._public.generation_tuning.to_dict())
        LOGGER.info("Derived config: %s", self._derived)

        stages = (
            ("fill_forest", self._fill_forest),
            ("place_regions", self._place_regions_evenly),
            ("assign_region_kinds", self._assign_region_kinds),
            ("relocate_ruins", self._relocate_ruin_regions_to_flat_ground),
            ("build_region_graph", self._build_region_graph),
            ("carve_regions", self._carve_regions),
            ("carve_roads", self._carve_graph_roads),
            ("connected_pockets", self._add_connected_pockets),
            ("cracked_ground", self._add_cracked_ground_patches),
            ("water_patches", self._add_water_patches),
            ("tree_clusters", self._add_tree_clusters_with_bushes),
            ("scattered_bushes", self._add_scattered_bushes),
            ("flower_patches", self._add_flower_patches),
            ("mushroom_patches", self._add_mushroom_patches),
            ("cleanup_components", self._cleanup_small_components),
            ("place_start_goal_1", self._place_start_goal),
            ("open_dead_forest", self._open_dead_forest_masses),
            ("repair_critical", self._repair_critical_connectivity),
            ("repair_walkable", self._repair_walkable_connectivity),
            ("place_start_goal_2", self._place_start_goal),
            ("validate", self._validate),
        )
        for stage_name, stage_function in stages:
            stage_started = perf_counter()
            stage_function()
            LOGGER.warning(
                "PERF_STAGE %s %.2f",
                stage_name,
                (perf_counter() - stage_started) * 1000.0,
            )

        LOGGER.info("GENERATION FINISHED")
        return self._grid

    def _fill_forest(self) -> None:
        LOGGER.info("Stage 1: fill map with TREE")
        for y in range(self._grid.height):
            for x in range(self._grid.width):
                self._grid.set_tile(Point(x, y), TileType.TREE)

    def _place_regions_evenly(self) -> None:
        LOGGER.info("Stage 2: place regions evenly using spatial buckets")
        bucket_count = self._derived.region_count
        aspect = self._grid.width / self._grid.height
        bucket_cols = max(3, round(math.sqrt(bucket_count * aspect)))
        bucket_rows = max(3, math.ceil(bucket_count / bucket_cols))
        bucket_width = self._grid.width / bucket_cols
        bucket_height = self._grid.height / bucket_rows

        central_origin = Point(self._grid.width // 2, self._grid.height // 2)
        central = self._best_guided_candidate(
            left=max(10, central_origin.x - self._public.chunk_width_tiles),
            right=min(self._grid.width - 11, central_origin.x + self._public.chunk_width_tiles),
            top=max(10, central_origin.y - self._public.chunk_height_tiles),
            bottom=min(self._grid.height - 11, central_origin.y + self._public.chunk_height_tiles),
            radius=min(12, self._derived.central_clearing_radius),
            attempts=36,
            existing=(),
            minimum_distance=0,
        )
        if central is None:
            central = Point(
                central_origin.x + self._rng.randint(-self._public.chunk_width_tiles, self._public.chunk_width_tiles),
                central_origin.y
                + self._rng.randint(
                    -self._public.chunk_height_tiles,
                    self._public.chunk_height_tiles,
                ),
            )
        central_region = Region(0, central, RegionKind.CENTRAL_RUIN_CLEARING)
        self._regions.append(central_region)
        self._central_region_id = central_region.region_id

        LOGGER.info(
            "  Central ruin clearing region=%02d center=(%03d,%03d)",
            central_region.region_id,
            central.x,
            central.y,
        )

        candidate_cells = [
            (col, row)
            for row in range(bucket_rows)
            for col in range(bucket_cols)
        ]
        self._rng.shuffle(candidate_cells)

        for col, row in candidate_cells:
            if len(self._regions) >= self._derived.region_count:
                break

            left = int(col * bucket_width)
            right = int((col + 1) * bucket_width) - 1
            top = int(row * bucket_height)
            bottom = int((row + 1) * bucket_height) - 1
            margin = 8
            minimum_x = max(margin, left + margin)
            maximum_x = min(self._grid.width - margin - 1, right - margin)
            minimum_y = max(margin, top + margin)
            maximum_y = min(self._grid.height - margin - 1, bottom - margin)
            if minimum_x > maximum_x or minimum_y > maximum_y:
                continue

            point = self._best_guided_candidate(
                left=minimum_x,
                right=maximum_x,
                top=minimum_y,
                bottom=maximum_y,
                radius=8,
                attempts=18,
                existing=tuple(region.center for region in self._regions),
                minimum_distance=12,
            )
            if point is None or self._manhattan(point, central) < 18:
                continue

            region = Region(len(self._regions), point)
            self._regions.append(region)
            LOGGER.info(
                "  Region %02d bucket=(%02d,%02d) center=(%03d,%03d)",
                region.region_id,
                col,
                row,
                point.x,
                point.y,
            )

        attempts = self._derived.region_count * 80
        while len(self._regions) < self._derived.region_count and attempts > 0:
            attempts -= 1
            point = self._best_guided_candidate(
                left=10,
                right=self._grid.width - 11,
                top=10,
                bottom=self._grid.height - 11,
                radius=7,
                attempts=4,
                existing=tuple(region.center for region in self._regions),
                minimum_distance=12,
            )
            if point is None:
                continue
            self._regions.append(Region(len(self._regions), point))

        if len(self._regions) < self._derived.region_count:
            raise GenerationError("Failed to place derived region count")

        LOGGER.info("Stage 2 complete: regions=%s", len(self._regions))

    def _best_guided_candidate(
        self,
        *,
        left: int,
        right: int,
        top: int,
        bottom: int,
        radius: int,
        attempts: int,
        existing: tuple[Point, ...],
        minimum_distance: int,
    ) -> Point | None:
        """Choose the flattest valid random candidate inside one area."""
        if left > right or top > bottom:
            return None
        best: Point | None = None
        best_score = -1.0
        steep_fallback: Point | None = None
        steep_fallback_score = -1.0
        for _ in range(max(1, attempts)):
            point = Point(self._rng.randint(left, right), self._rng.randint(top, bottom))
            if any(self._manhattan(point, other) < minimum_distance for other in existing):
                continue
            if self._guidance is None:
                return point
            self._terrain_guidance_metrics["region_candidates_evaluated"] = (
                int(self._terrain_guidance_metrics["region_candidates_evaluated"]) + 1
            )
            score = self._guidance.footprint_score(point.x, point.y, radius)
            if self._guidance.is_steep(point.x, point.y):
                self._terrain_guidance_metrics["region_candidates_rejected_steep"] = (
                    int(self._terrain_guidance_metrics["region_candidates_rejected_steep"]) + 1
                )
                if score > steep_fallback_score:
                    steep_fallback = point
                    steep_fallback_score = score
                continue
            if score > best_score:
                best = point
                best_score = score
        if best is not None:
            return best
        if steep_fallback is not None:
            self._terrain_guidance_metrics["region_steep_fallbacks"] = (
                int(self._terrain_guidance_metrics["region_steep_fallbacks"]) + 1
            )
        return steep_fallback

    def _assign_region_kinds(self) -> None:
        LOGGER.info("Stage 3: assign region kinds")
        farthest = self._find_farthest_pair_excluding({self._central_region_id})
        self._start_region_id = farthest.a
        self._goal_region_id = farthest.b

        self._regions[self._start_region_id].kind = RegionKind.START
        self._regions[self._goal_region_id].kind = RegionKind.GOAL
        self._regions[self._central_region_id].kind = RegionKind.CENTRAL_RUIN_CLEARING

        free_ids = [
            region.region_id
            for region in self._regions
            if region.region_id not in {
                self._start_region_id,
                self._goal_region_id,
                self._central_region_id,
            }
        ]
        self._rng.shuffle(free_ids)

        cursor = 0
        medium_ids = free_ids[cursor: cursor + self._derived.medium_ruin_count]
        cursor += self._derived.medium_ruin_count
        small_ids = free_ids[cursor: cursor + self._derived.small_ruin_count]

        for region_id in medium_ids:
            self._regions[region_id].kind = RegionKind.MEDIUM_RUIN

        for region_id in small_ids:
            self._regions[region_id].kind = RegionKind.SMALL_RUIN

        for region in self._regions:
            LOGGER.info(
                "  Region %02d kind=%s center=(%03d,%03d)",
                region.region_id,
                region.kind.value,
                region.center.x,
                region.center.y,
            )

    def _relocate_ruin_regions_to_flat_ground(self) -> None:
        """Move ruin regions locally when a significantly flatter footprint exists."""
        if self._guidance is None:
            return
        for region in self._regions:
            if region.kind not in {
                RegionKind.SMALL_RUIN,
                RegionKind.MEDIUM_RUIN,
                RegionKind.CENTRAL_RUIN_CLEARING,
            }:
                continue
            radius = {
                RegionKind.SMALL_RUIN: 7,
                RegionKind.MEDIUM_RUIN: 11,
                RegionKind.CENTRAL_RUIN_CLEARING: min(14, self._derived.central_clearing_radius),
            }[region.kind]
            current_score = self._guidance.footprint_score(region.center.x, region.center.y, radius)
            search_radius = 16 if region.kind != RegionKind.CENTRAL_RUIN_CLEARING else 24
            other_centers = tuple(
                other.center for other in self._regions if other.region_id != region.region_id
            )
            candidate = self._best_guided_candidate(
                left=max(10, region.center.x - search_radius),
                right=min(self._grid.width - 11, region.center.x + search_radius),
                top=max(10, region.center.y - search_radius),
                bottom=min(self._grid.height - 11, region.center.y + search_radius),
                radius=radius,
                attempts=36,
                existing=other_centers,
                minimum_distance=10,
            )
            if candidate is None:
                continue
            candidate_score = self._guidance.footprint_score(candidate.x, candidate.y, radius)
            if candidate_score < current_score + 0.06:
                continue
            region.center = candidate
            self._terrain_guidance_metrics["ruin_regions_relocated"] = (
                int(self._terrain_guidance_metrics["ruin_regions_relocated"]) + 1
            )

    def _build_region_graph(self) -> None:
        LOGGER.info("Stage 4: build connected region graph")
        candidates = self._candidate_edges()
        mst = self._minimum_spanning_tree(candidates)
        self._edges = [Edge(edge.a, edge.b, False) for edge in mst]

        central_edges = [
            Edge(self._central_region_id, region.region_id, False)
            for region in sorted(
                self._regions,
                key=lambda item: self._manhattan(self._regions[self._central_region_id].center, item.center),
            )
            if region.region_id != self._central_region_id
        ][:4]

        existing = {self._edge_key(edge.a, edge.b) for edge in self._edges}
        for edge in central_edges:
            key = self._edge_key(edge.a, edge.b)
            if key not in existing:
                self._edges.append(edge)
                existing.add(key)
                LOGGER.info("  Forced central edge %02d -- %02d", edge.a, edge.b)

        loop_candidates = [
            edge for edge in candidates
            if self._edge_key(edge.a, edge.b) not in existing
        ]
        self._rng.shuffle(loop_candidates)

        loops = 0
        for edge in loop_candidates:
            if loops >= self._derived.loop_target_count:
                break
            self._edges.append(Edge(edge.a, edge.b, True))
            existing.add(self._edge_key(edge.a, edge.b))
            loops += 1

        for edge in self._edges:
            LOGGER.info(
                "  Edge %02d -- %02d type=%s",
                edge.a,
                edge.b,
                "loop" if edge.is_loop else "main",
            )

        LOGGER.info("Stage 4 complete: edges=%s loops=%s", len(self._edges), loops)

    def _carve_regions(self) -> None:
        LOGGER.info("Stage 5: carve region contents")
        for region in self._regions:
            if region.kind == RegionKind.CENTRAL_RUIN_CLEARING:
                self._carve_central_ruin_clearing(region)
            elif region.kind == RegionKind.SMALL_RUIN:
                self._carve_small_ruin(region)
            elif region.kind == RegionKind.MEDIUM_RUIN:
                self._carve_medium_ruin(region)
            else:
                self._carve_forest_clearing(region)

    def _carve_forest_clearing(self, region: Region) -> None:
        radius = self._rng.randint(
            self._derived.clearing_min_radius,
            self._derived.clearing_max_radius,
        )
        LOGGER.info("  Forest clearing region=%02d radius=%s", region.region_id, radius)
        self._carve_circle(region.center, radius, TileType.GRASS)

    def _carve_small_ruin(self, region: Region) -> None:
        radius = self._rng.randint(4, 7)
        self._carve_circle(region.center, radius, TileType.GRASS)
        rect = self._rect_around(
            region.center,
            self._rng.randint(self._derived.small_ruin_min_width, self._derived.small_ruin_max_width),
            self._rng.randint(self._derived.small_ruin_min_height, self._derived.small_ruin_max_height),
        )
        LOGGER.info("  Small ruin region=%02d rect=%s", region.region_id, rect)
        if self._guidance is not None and self._guidance.footprint_level_delta(region.center.x, region.center.y, 7) > 2:
            self._terrain_guidance_metrics["ruin_bad_footprints"] = int(self._terrain_guidance_metrics["ruin_bad_footprints"]) + 1
        self._carve_ruin_building(rect, region, self._rng.randint(1, 2))

    def _carve_medium_ruin(self, region: Region) -> None:
        radius = self._rng.randint(8, 12)
        self._carve_circle(region.center, radius, TileType.GRASS)
        rect = self._rect_around(
            region.center,
            self._rng.randint(self._derived.medium_ruin_min_width, self._derived.medium_ruin_max_width),
            self._rng.randint(self._derived.medium_ruin_min_height, self._derived.medium_ruin_max_height),
        )
        LOGGER.info("  Medium ruin region=%02d rect=%s", region.region_id, rect)
        if self._guidance is not None and self._guidance.footprint_level_delta(region.center.x, region.center.y, 11) > 2:
            self._terrain_guidance_metrics["ruin_bad_footprints"] = int(self._terrain_guidance_metrics["ruin_bad_footprints"]) + 1
        self._carve_ruin_building(rect, region, self._rng.randint(2, 4))
        self._add_internal_ruin_walls(rect)

    def _carve_central_ruin_clearing(self, region: Region) -> None:
        radius = self._derived.central_clearing_radius
        building_count = self._rng.randint(
            self._derived.settlement_min_buildings,
            self._derived.settlement_max_buildings,
        )
        LOGGER.info(
            "  Central ruin clearing region=%02d radius=%s buildings=%s",
            region.region_id,
            radius,
            building_count,
        )
        self._carve_circle(region.center, radius, TileType.GRASS)

        building_centers = [region.center]
        for _ in range(building_count - 1):
            for _attempt in range(50):
                dx = self._rng.randint(-radius + 4, radius - 4)
                dy = self._rng.randint(-radius + 4, radius - 4)
                if dx * dx + dy * dy <= (radius - 3) * (radius - 3):
                    candidate = Point(region.center.x + dx, region.center.y + dy)
                    if (
                        self._guidance is not None
                        and self._guidance.footprint_score(candidate.x, candidate.y, 6) < 0.42
                    ):
                        continue
                    building_centers.append(candidate)
                    break

        all_entrances: list[Point] = []
        for index, center in enumerate(building_centers):
            rect = self._rect_around(
                center,
                self._rng.randint(8, 15),
                self._rng.randint(7, 12),
            )
            LOGGER.info("    Central building %02d rect=%s", index, rect)
            temp_region = Region(region.region_id, center)
            self._carve_ruin_building(rect, temp_region, self._rng.randint(1, 3))
            all_entrances.extend(temp_region.entrances)

        region.entrances = all_entrances or [region.center]

        for first, second in zip(building_centers, building_centers[1:]):
            self._carve_old_road(first, second, is_loop=False)

    def _carve_ruin_building(self, rect: Rect, region: Region, entrance_count: int) -> None:
        for y in range(rect.top, rect.bottom + 1):
            for x in range(rect.left, rect.right + 1):
                point = Point(x, y)
                is_wall = x in {rect.left, rect.right} or y in {rect.top, rect.bottom}
                self._set_tile(point, TileType.RUIN_WALL if is_wall else TileType.RUIN_FLOOR)

        self._damage_ruin_edges(rect)
        entrances = self._ruin_entrances(rect, entrance_count)
        region.entrances.extend(entrances)

        for entrance in entrances:
            self._carve_circle(entrance, 1, TileType.RUIN_FLOOR)
            self._carve_winding_line(entrance, rect.center, 1, TileType.RUIN_FLOOR, protect_path=False)

    def _damage_ruin_edges(self, rect: Rect) -> None:
        for x in range(rect.left, rect.right + 1):
            for y in (rect.top, rect.bottom):
                if self._rng.random() < 0.14:
                    self._set_tile(Point(x, y), TileType.RUIN_FLOOR)

        for y in range(rect.top, rect.bottom + 1):
            for x in (rect.left, rect.right):
                if self._rng.random() < 0.14:
                    self._set_tile(Point(x, y), TileType.RUIN_FLOOR)

        for corner in (
            Point(rect.left, rect.top),
            Point(rect.right, rect.top),
            Point(rect.left, rect.bottom),
            Point(rect.right, rect.bottom),
        ):
            if self._rng.random() < 0.45:
                self._carve_circle(corner, 1, TileType.RUIN_FLOOR)

    def _add_internal_ruin_walls(self, rect: Rect) -> None:
        if rect.right - rect.left < 8 or rect.bottom - rect.top < 7:
            return

        for _ in range(self._rng.randint(1, 3)):
            if self._rng.random() < 0.5:
                x = self._rng.randint(rect.left + 3, rect.right - 3)
                for y in range(rect.top + 1, rect.bottom):
                    if self._rng.random() < 0.25:
                        continue
                    self._set_tile(Point(x, y), TileType.RUIN_WALL)
                self._set_tile(
                    Point(x, self._rng.randint(rect.top + 2, rect.bottom - 2)),
                    TileType.RUIN_FLOOR,
                )
            else:
                y = self._rng.randint(rect.top + 3, rect.bottom - 3)
                for x in range(rect.left + 1, rect.right):
                    if self._rng.random() < 0.25:
                        continue
                    self._set_tile(Point(x, y), TileType.RUIN_WALL)
                self._set_tile(
                    Point(self._rng.randint(rect.left + 2, rect.right - 2), y),
                    TileType.RUIN_FLOOR,
                )

    def _ruin_entrances(self, rect: Rect, entrance_count: int) -> list[Point]:
        candidates = [
            Point((rect.left + rect.right) // 2, rect.top),
            Point((rect.left + rect.right) // 2, rect.bottom),
            Point(rect.left, (rect.top + rect.bottom) // 2),
            Point(rect.right, (rect.top + rect.bottom) // 2),
            Point(rect.left + 1, rect.top),
            Point(rect.right - 1, rect.bottom),
            Point(rect.left, rect.bottom - 1),
            Point(rect.right, rect.top + 1),
        ]
        self._rng.shuffle(candidates)
        return candidates[:entrance_count]

    def _carve_graph_roads(self) -> None:
        LOGGER.info("Stage 6: carve old overgrown road network")
        for edge in self._edges:
            start = self._regions[edge.a].connection_point()
            end = self._regions[edge.b].connection_point()
            LOGGER.info(
                "  Old road %02d -- %02d type=%s",
                edge.a,
                edge.b,
                "loop" if edge.is_loop else "main",
            )
            self._carve_old_road(start, end, edge.is_loop)

    def _carve_old_road(self, start: Point, end: Point, is_loop: bool) -> None:
        points = self._terrain_aware_road_points(start, end)
        corridor_width = self._rng.randint(
            self._derived.old_road_corridor_min_width,
            self._derived.old_road_corridor_max_width,
        )
        if is_loop:
            corridor_width = max(2, corridor_width - 1)

        for point in points:
            self._carve_circle(point, corridor_width, TileType.GRASS)

        previous = None
        for index, point in enumerate(points):
            force = index == 0 or index == len(points) - 1
            should_overgrow = (
                not force
                and self._rng.random() < self._derived.old_road_overgrowth_chance
                and previous is not None
            )
            if should_overgrow:
                self._set_tile(point, TileType.GRASS)
                continue

            self._set_tile(point, TileType.PATH)
            self._protected_path.add(point)

            if self._rng.random() > self._derived.old_road_side_grass_chance:
                for neighbor in self._grid.neighbors_4(point):
                    if self._grid.get_tile(neighbor) == TileType.GRASS and self._rng.random() < 0.28:
                        self._set_tile(neighbor, TileType.PATH)
                        self._protected_path.add(neighbor)

            previous = point

    def _terrain_aware_road_points(self, start: Point, end: Point) -> list[Point]:
        """Return a geography-aware tile route or a legacy fallback path."""
        if self._guidance is None:
            return self._winding_points(start, end)
        waypoints = self._guidance.road_path((start.x, start.y), (end.x, end.y))
        if not waypoints:
            self._terrain_guidance_metrics["fallback_road_routes"] = (
                int(self._terrain_guidance_metrics["fallback_road_routes"]) + 1
            )
            points = self._winding_points(start, end)
            self._record_road_guidance_metrics(points)
            return points

        points: list[Point] = []
        for first, second in zip(waypoints, waypoints[1:]):
            segment = self._line_points(Point(*first), Point(*second))
            if points and segment and points[-1] == segment[0]:
                segment = segment[1:]
            points.extend(segment)
        if not points:
            points = [start, end]
        self._terrain_guidance_metrics["guided_road_routes"] = (
            int(self._terrain_guidance_metrics["guided_road_routes"]) + 1
        )
        self._record_road_guidance_metrics(points)
        return points

    def _record_road_guidance_metrics(self, points: list[Point]) -> None:
        """Accumulate slope diagnostics for one road route."""
        if self._guidance is None:
            return
        for point in points:
            slope = self._guidance.slope_at(point.x, point.y)
            self._terrain_guidance_metrics["road_sample_tiles"] = (
                int(self._terrain_guidance_metrics["road_sample_tiles"]) + 1
            )
            self._terrain_guidance_metrics["road_slope_sum"] = (
                float(self._terrain_guidance_metrics["road_slope_sum"]) + slope
            )
            natural_delta = self._guidance.natural_delta_at(point.x, point.y)
            if natural_delta == 2:
                self._terrain_guidance_metrics["road_steep_tiles"] = (
                    int(self._terrain_guidance_metrics["road_steep_tiles"]) + 1
                )
            elif natural_delta > 2:
                self._terrain_guidance_metrics["road_cliff_tiles"] = (
                    int(self._terrain_guidance_metrics["road_cliff_tiles"]) + 1
                )

    @staticmethod
    def _line_points(start: Point, end: Point) -> list[Point]:
        """Rasterize a continuous integer line between two points."""
        points: list[Point] = []
        x0, y0 = start.x, start.y
        x1, y1 = end.x, end.y
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            points.append(Point(x0, y0))
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += step_x
            if doubled <= dx:
                error += dx
                y0 += step_y
        return points

    def _add_connected_pockets(self) -> None:
        LOGGER.info("Stage 7: add connected grass pockets")
        for index in range(self._derived.connected_pocket_count):
            anchor = self._rng.choice(self._regions).connection_point()
            radius = self._rng.randint(
                self._derived.connected_pocket_min_radius,
                self._derived.connected_pocket_max_radius,
            )
            pocket = self._best_guided_candidate(
                left=max(6, anchor.x - 20),
                right=min(self._grid.width - 7, anchor.x + 20),
                top=max(6, anchor.y - 14),
                bottom=min(self._grid.height - 7, anchor.y + 14),
                radius=radius,
                attempts=10,
                existing=(),
                minimum_distance=0,
            )
            if pocket is None:
                pocket = Point(
                    min(max(anchor.x + self._rng.randint(-20, 20), 6), self._grid.width - 7),
                    min(max(anchor.y + self._rng.randint(-14, 14), 6), self._grid.height - 7),
                )
            LOGGER.info(
                "  Pocket %02d center=(%03d,%03d) radius=%s",
                index,
                pocket.x,
                pocket.y,
                radius,
            )
            self._carve_circle(pocket, radius, TileType.GRASS)
            self._carve_old_road(anchor, pocket, is_loop=True)

    def _add_tree_clusters_with_bushes(self) -> None:
        LOGGER.info("Stage 8: add small tree clusters with bush rings")
        placed = 0
        attempts = self._derived.tree_cluster_count * 30

        while placed < self._derived.tree_cluster_count and attempts > 0:
            attempts -= 1
            center = Point(
                self._rng.randint(6, self._grid.width - 7),
                self._rng.randint(6, self._grid.height - 7),
            )
            if self._grid.get_tile(center) != TileType.GRASS:
                continue
            if self._guidance is not None and self._guidance.forest_suitability(center.x, center.y) < 0.48:
                self._terrain_guidance_metrics["forest_candidates_rejected"] = (
                    int(self._terrain_guidance_metrics["forest_candidates_rejected"]) + 1
                )
                continue

            radius = self._rng.randint(
                self._derived.tree_cluster_min_radius,
                self._derived.tree_cluster_max_radius,
            )
            if not self._can_place_tree_cluster(center, radius):
                continue

            self._paint_tree_cluster(center, radius)
            placed += 1

        LOGGER.info("  Tree clusters placed: %s/%s", placed, self._derived.tree_cluster_count)


    def _add_scattered_bushes(self) -> None:
        """Add configurable scattered bushes near forest terrain."""
        target_count = self._derived.scattered_bush_count
        LOGGER.info("Stage 8a: add scattered bushes target=%s", target_count)
        placed = 0
        attempts = target_count * 20
        while placed < target_count and attempts > 0:
            attempts -= 1
            point = Point(
                self._rng.randint(2, self._grid.width - 3),
                self._rng.randint(2, self._grid.height - 3),
            )
            if self._grid.get_tile(point) != TileType.GRASS:
                continue
            if point in self._protected_path:
                continue
            if not self._has_nearby_tile(point, {TileType.TREE, TileType.BUSH}, radius=4):
                continue
            if self._guidance is not None and self._guidance.forest_suitability(point.x, point.y) < 0.35:
                continue
            self._grid.set_tile(point, TileType.BUSH)
            placed += 1
        LOGGER.info("  Scattered bushes placed: %s/%s", placed, target_count)

    def _add_cracked_ground_patches(self) -> None:
        """Add old stone and cracked ground patches near ruins and old roads."""
        LOGGER.info("Stage 8a: add cracked ground patches near ruins and roads")
        placed = 0
        attempts = self._derived.cracked_ground_patch_count * 12
        ruin_regions = [
            region for region in self._regions
            if region.kind in {
                RegionKind.SMALL_RUIN,
                RegionKind.MEDIUM_RUIN,
                RegionKind.CENTRAL_RUIN_CLEARING,
            }
        ]

        while placed < self._derived.cracked_ground_patch_count and attempts > 0:
            attempts -= 1
            anchor_region = self._rng.choice(ruin_regions or self._regions)
            anchor = anchor_region.connection_point()
            center = Point(
                min(max(anchor.x + self._rng.randint(-10, 10), 4), self._grid.width - 5),
                min(max(anchor.y + self._rng.randint(-8, 8), 4), self._grid.height - 5),
            )
            radius = self._rng.randint(2, 5)

            if self._grid.get_tile(center) not in {
                TileType.GRASS,
                TileType.PATH,
                TileType.RUIN_FLOOR,
            }:
                continue

            self._paint_patch(
                center=center,
                radius=radius,
                tile_type=TileType.CRACKED_GROUND,
                allowed_sources={TileType.GRASS, TileType.PATH},
                density=0.72,
            )
            placed += 1

        LOGGER.info("  Cracked ground patches placed: %s/%s", placed, self._derived.cracked_ground_patch_count)

    def _add_water_patches(self) -> None:
        """Add small walkable puddles in low grass pockets."""
        LOGGER.info("Stage 8b: add small water/puddle patches")
        placed = 0
        attempts = self._derived.water_patch_count * 28

        while placed < self._derived.water_patch_count and attempts > 0:
            attempts -= 1
            center = Point(
                self._rng.randint(5, self._grid.width - 6),
                self._rng.randint(5, self._grid.height - 6),
            )
            if self._grid.get_tile(center) != TileType.GRASS:
                continue
            if self._guidance is not None and self._guidance.wetland_score(center.x, center.y) < 0.58:
                self._terrain_guidance_metrics["wetland_candidates_rejected"] = (
                    int(self._terrain_guidance_metrics["wetland_candidates_rejected"]) + 1
                )
                continue

            if not self._has_nearby_tile(center, {TileType.TREE, TileType.BUSH, TileType.MUSHROOM}, radius=5):
                if self._rng.random() < 0.65:
                    continue

            radius = self._rng.randint(
                self._derived.water_patch_min_radius,
                self._derived.water_patch_max_radius,
            )
            self._paint_patch(
                center=center,
                radius=radius,
                tile_type=TileType.WATER,
                allowed_sources={TileType.GRASS},
                density=self._derived.water_patch_density,
            )
            placed += 1

        LOGGER.info(
            "  Water patches placed: %s/%s, radius=%s..%s, density=%.2f",
            placed,
            self._derived.water_patch_count,
            self._derived.water_patch_min_radius,
            self._derived.water_patch_max_radius,
            self._derived.water_patch_density,
        )

    def _add_flower_patches(self) -> None:
        """Add flower patches in open grass areas and near old roads."""
        LOGGER.info("Stage 8c: add flower patches")
        placed = 0
        attempts = self._derived.flower_patch_count * 16

        while placed < self._derived.flower_patch_count and attempts > 0:
            attempts -= 1
            center = Point(
                self._rng.randint(4, self._grid.width - 5),
                self._rng.randint(4, self._grid.height - 5),
            )
            if self._grid.get_tile(center) != TileType.GRASS:
                continue

            if self._has_nearby_tile(center, {TileType.TREE}, radius=2):
                continue

            if not self._has_nearby_tile(center, {TileType.PATH, TileType.CRACKED_GROUND, TileType.RUIN_FLOOR}, radius=5):
                if self._rng.random() < 0.45:
                    continue

            radius = self._rng.randint(1, 3)
            self._paint_patch(
                center=center,
                radius=radius,
                tile_type=TileType.FLOWER,
                allowed_sources={TileType.GRASS},
                density=0.58,
            )
            placed += 1

        LOGGER.info("  Flower patches placed: %s/%s", placed, self._derived.flower_patch_count)

    def _add_mushroom_patches(self) -> None:
        """Add mushroom patches near trees, bushes, walls, and puddles."""
        LOGGER.info("Stage 8d: add mushroom patches")
        placed = 0
        attempts = self._derived.mushroom_patch_count * 24

        while placed < self._derived.mushroom_patch_count and attempts > 0:
            attempts -= 1
            center = Point(
                self._rng.randint(4, self._grid.width - 5),
                self._rng.randint(4, self._grid.height - 5),
            )
            if self._grid.get_tile(center) != TileType.GRASS:
                continue

            if not self._has_nearby_tile(
                center,
                {TileType.TREE, TileType.BUSH, TileType.RUIN_WALL, TileType.WATER},
                radius=3,
            ):
                continue

            radius = self._rng.randint(1, 2)
            self._paint_patch(
                center=center,
                radius=radius,
                tile_type=TileType.MUSHROOM,
                allowed_sources={TileType.GRASS},
                density=0.64,
            )
            placed += 1

        LOGGER.info("  Mushroom patches placed: %s/%s", placed, self._derived.mushroom_patch_count)

    def _paint_patch(
        self,
        center: Point,
        radius: int,
        tile_type: TileType,
        allowed_sources: set[TileType],
        density: float,
    ) -> None:
        """Paint an irregular decorative patch."""
        radius_squared = radius * radius

        for y in range(center.y - radius, center.y + radius + 1):
            for x in range(center.x - radius, center.x + radius + 1):
                point = Point(x, y)
                if not self._grid.is_inside(point):
                    continue

                dx = x - center.x
                dy = y - center.y
                if dx * dx + dy * dy > radius_squared:
                    continue

                if self._grid.get_tile(point) not in allowed_sources:
                    continue

                if self._rng.random() <= density:
                    self._set_tile(point, tile_type)

    def _has_nearby_tile(
        self,
        center: Point,
        tile_types: set[TileType],
        radius: int,
    ) -> bool:
        """Check if any selected tile type exists nearby."""
        for y in range(center.y - radius, center.y + radius + 1):
            for x in range(center.x - radius, center.x + radius + 1):
                point = Point(x, y)
                if not self._grid.is_inside(point):
                    continue
                if self._grid.get_tile(point) in tile_types:
                    return True
        return False

    def _cleanup_small_components(self) -> None:
        LOGGER.info("Stage 9: clean small isolated walkable components")
        validator = MapValidator(self._grid)
        components = validator.components()

        removed_components = 0
        removed_tiles = 0
        for component in components[1:]:
            if len(component) > self._derived.cleanup_small_component_max_size:
                LOGGER.info("  Keeping large isolated component size=%s", len(component))
                continue
            for point in component:
                self._set_tile(point, TileType.TREE)
            removed_components += 1
            removed_tiles += len(component)

        LOGGER.info(
            "  Removed components=%s removed_tiles=%s",
            removed_components,
            removed_tiles,
        )

    def _place_start_goal(self) -> None:
        LOGGER.info("Stage 10: place START and GOAL")
        start = self.start_point()
        goal = self.goal_point()

        self._carve_circle(start, 2, TileType.PATH)
        self._set_tile(start, TileType.START)
        self._protected_path.add(start)

        self._carve_circle(goal, 2, TileType.PATH)
        self._set_tile(goal, TileType.GOAL)
        self._protected_path.add(goal)

        LOGGER.info("  START=(%03d,%03d)", start.x, start.y)
        LOGGER.info("  GOAL=(%03d,%03d)", goal.x, goal.y)



    def _open_dead_forest_masses(self) -> None:
        """Open oversized low-content forest masses with hidden clearings."""
        LOGGER.info("Stage 10a: analyze oversized forest masses")
        forest_components = self._find_components({TileType.TREE})
        candidates = self._rank_dead_forest_candidates(forest_components)
        selected = candidates[: self._derived.max_hidden_clearings]

        LOGGER.info(
            "  Forest components=%s candidates=%s selected=%s threshold=%s",
            len(forest_components),
            len(candidates),
            len(selected),
            self._derived.big_forest_component_min_size,
        )

        for index, component in enumerate(selected):
            center = self._choose_hidden_clearing_center(component)
            radius = self._rng.randint(
                self._derived.hidden_clearing_min_radius,
                self._derived.hidden_clearing_max_radius,
            )
            LOGGER.info(
                "  Hidden clearing %02d center=(%03d,%03d) radius=%s component_size=%s",
                index,
                center.x,
                center.y,
                radius,
                len(component),
            )

            self._carve_circle(center, radius, TileType.GRASS)
            self._decorate_hidden_clearing(center, radius)
            anchor = self._nearest_walkable_point(center)
            if anchor is not None:
                LOGGER.info(
                    "    Connecting hidden clearing to nearest walkable point=(%03d,%03d)",
                    anchor.x,
                    anchor.y,
                )
                self._carve_forest_trail(anchor, center)

    def _rank_dead_forest_candidates(
        self,
        components: list[set[Point]],
    ) -> list[set[Point]]:
        """Rank forest components that look like unused dead masses."""
        ranked: list[tuple[float, set[Point]]] = []

        for component in components:
            if len(component) < self._derived.big_forest_component_min_size:
                continue

            center = self._component_center(component)
            content_score = self._nearby_content_score(center, radius=12)
            edge_penalty = self._edge_penalty(center)
            size_score = len(component) / max(1, self._derived.big_forest_component_min_size)
            score = size_score * 2.0 - content_score - edge_penalty

            if score <= 0.8:
                continue

            ranked.append((score, component))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [component for _, component in ranked]

    def _choose_hidden_clearing_center(self, component: set[Point]) -> Point:
        """Choose a stable inner point for hidden clearing carving."""
        center = self._component_center(component)
        best = center
        best_score = -1
        sample = list(component)
        self._rng.shuffle(sample)

        for point in sample[: min(160, len(sample))]:
            if not self._is_good_hidden_clearing_center(point):
                continue

            distance_to_edge = min(
                point.x,
                point.y,
                self._grid.width - 1 - point.x,
                self._grid.height - 1 - point.y,
            )
            distance_to_center = self._manhattan(point, center)
            score = distance_to_edge * 2 - distance_to_center

            if score > best_score:
                best = point
                best_score = score

        return best

    def _is_good_hidden_clearing_center(self, point: Point) -> bool:
        """Check whether point has enough tree area around it."""
        radius = self._derived.hidden_clearing_max_radius + 1
        tree_count = 0
        total = 0

        for y in range(point.y - radius, point.y + radius + 1):
            for x in range(point.x - radius, point.x + radius + 1):
                candidate = Point(x, y)
                if not self._grid.is_inside(candidate):
                    return False
                total += 1
                if self._grid.get_tile(candidate) == TileType.TREE:
                    tree_count += 1

        return tree_count / max(1, total) > 0.72

    def _decorate_hidden_clearing(self, center: Point, radius: int) -> None:
        """Decorate a hidden clearing with small thematic content."""
        roll = self._rng.random()

        if roll < 0.35:
            self._paint_patch(
                center=center,
                radius=max(1, radius // 2),
                tile_type=TileType.FLOWER,
                allowed_sources={TileType.GRASS},
                density=0.45,
            )
        elif roll < 0.65:
            water_center = Point(
                min(max(center.x + self._rng.randint(-2, 2), 2), self._grid.width - 3),
                min(max(center.y + self._rng.randint(-2, 2), 2), self._grid.height - 3),
            )
            self._paint_patch(
                center=water_center,
                radius=max(1, radius // 3),
                tile_type=TileType.WATER,
                allowed_sources={TileType.GRASS},
                density=0.55,
            )
            self._paint_patch(
                center=center,
                radius=max(1, radius // 2),
                tile_type=TileType.MUSHROOM,
                allowed_sources={TileType.GRASS},
                density=0.28,
            )
        else:
            self._paint_patch(
                center=center,
                radius=max(1, radius // 2),
                tile_type=TileType.CRACKED_GROUND,
                allowed_sources={TileType.GRASS},
                density=0.50,
            )
            if self._rng.random() < 0.55:
                for x in range(max(2, center.x - 2), min(self._grid.width - 3, center.x + 2) + 1):
                    self._set_tile(Point(x, center.y), TileType.RUIN_WALL)

    def _nearest_walkable_point(self, point: Point) -> Point | None:
        """Find nearest walkable point using BFS over the full map."""
        walkable_tiles = {
            TileType.GRASS,
            TileType.PATH,
            TileType.BUSH,
            TileType.FLOWER,
            TileType.MUSHROOM,
            TileType.WATER,
            TileType.CRACKED_GROUND,
            TileType.RUIN_FLOOR,
            TileType.START,
            TileType.GOAL,
        }
        visited = {point}
        queue: deque[Point] = deque([point])

        while queue:
            current = queue.popleft()
            if current != point and self._grid.get_tile(current) in walkable_tiles:
                return current

            for neighbor in self._grid.neighbors_4(current):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)

        return None

    def _carve_forest_trail(self, start: Point, end: Point) -> None:
        """Carve a narrow forest trail to a hidden clearing."""
        points = self._winding_points(start, end)

        for point in points:
            self._carve_circle(point, 2, TileType.GRASS)

        for index, point in enumerate(points):
            if index in {0, len(points) - 1} or self._rng.random() > 0.35:
                self._set_tile(point, TileType.PATH)
                self._protected_path.add(point)

    def _find_components(self, tile_types: set[TileType]) -> list[set[Point]]:
        """Find connected components for selected tile types."""
        remaining = {
            Point(x, y)
            for y in range(self._grid.height)
            for x in range(self._grid.width)
            if self._grid.get_tile(Point(x, y)) in tile_types
        }
        components: list[set[Point]] = []

        while remaining:
            start = next(iter(remaining))
            component = self._flood_component(start, tile_types)
            components.append(component)
            remaining -= component

        components.sort(key=len, reverse=True)
        return components

    def _flood_component(
        self,
        start: Point,
        tile_types: set[TileType],
    ) -> set[Point]:
        """Flood-fill one component of selected tile types."""
        visited = {start}
        queue: deque[Point] = deque([start])

        while queue:
            current = queue.popleft()
            for neighbor in self._grid.neighbors_4(current):
                if neighbor in visited:
                    continue
                if self._grid.get_tile(neighbor) not in tile_types:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)

        return visited

    def _component_center(self, component: set[Point]) -> Point:
        """Return approximate center of a component."""
        x_sum = sum(point.x for point in component)
        y_sum = sum(point.y for point in component)
        return Point(round(x_sum / len(component)), round(y_sum / len(component)))

    def _nearby_content_score(self, center: Point, radius: int) -> float:
        """Estimate how much meaningful content is near a point."""
        score = 0.0
        content_weights = {
            TileType.PATH: 1.5,
            TileType.CRACKED_GROUND: 1.2,
            TileType.RUIN_WALL: 2.0,
            TileType.RUIN_FLOOR: 2.0,
            TileType.WATER: 1.0,
            TileType.FLOWER: 0.4,
            TileType.MUSHROOM: 0.5,
            TileType.START: 3.0,
            TileType.GOAL: 3.0,
        }

        for y in range(center.y - radius, center.y + radius + 1):
            for x in range(center.x - radius, center.x + radius + 1):
                point = Point(x, y)
                if not self._grid.is_inside(point):
                    continue
                score += content_weights.get(self._grid.get_tile(point), 0.0)

        return min(3.5, score / 12.0)

    def _edge_penalty(self, point: Point) -> float:
        """Return penalty for points too close to map edge."""
        distance = min(
            point.x,
            point.y,
            self._grid.width - 1 - point.x,
            self._grid.height - 1 - point.y,
        )
        if distance < 8:
            return 2.0
        if distance < 14:
            return 0.9
        return 0.0

    def _repair_critical_connectivity(self) -> None:
        """Repair critical route connectivity after decoration and cleanup."""
        LOGGER.info("Stage 10b: repair critical connectivity")
        validator = MapValidator(self._grid)
        start = self.start_point()
        central = self.central_point()
        goal = self.goal_point()

        self._ensure_walkable_area(start, TileType.PATH)
        self._ensure_walkable_area(central, TileType.GRASS)
        self._ensure_walkable_area(goal, TileType.PATH)

        distances = validator.reachable_distances(start)
        repairs = 0

        if central not in distances:
            LOGGER.info("  Central ruin clearing is unreachable; carving repair road S -> central")
            self._carve_old_road(start, central, is_loop=False)
            repairs += 1

        validator = MapValidator(self._grid)
        distances = validator.reachable_distances(start)

        if goal not in distances:
            LOGGER.info("  Goal is unreachable; carving repair road central -> G")
            self._carve_old_road(central, goal, is_loop=False)
            repairs += 1

        validator = MapValidator(self._grid)
        distances = validator.reachable_distances(start)

        disconnected_regions = []
        for region in self._regions:
            points = [region.center, *region.entrances]
            if not any(point in distances for point in points):
                disconnected_regions.append(region)

        for region in disconnected_regions:
            target = region.connection_point()
            LOGGER.info(
                "  Region %02d is unreachable; carving repair road central -> (%03d,%03d)",
                region.region_id,
                target.x,
                target.y,
            )
            self._carve_old_road(central, target, is_loop=True)
            repairs += 1

        LOGGER.info("Stage 10b complete: repairs=%s", repairs)

    def _repair_walkable_connectivity(self) -> None:
        """Repair disconnected walkable components before final validation."""
        LOGGER.info("Stage 10c: repair final walkable connectivity")
        metrics = {
            "components_before": 0,
            "components_after": 0,
            "filled_components": 0,
            "connected_components": 0,
            "failed_repairs": 0,
            "tiles_changed": 0,
        }
        critical_points = {self.start_point(), self.goal_point(), self.central_point()}
        small_component_limit = self._small_isolated_component_limit()
        max_repair_passes = 16

        for pass_index in range(max_repair_passes):
            components = MapValidator(self._grid).components()
            if pass_index == 0:
                metrics["components_before"] = len(components)
            if len(components) <= 1:
                break

            main_component = self._main_walkable_component(components)
            isolated_components = [
                component for component in components if component is not main_component
            ]
            component = min(isolated_components, key=len)
            before_count = len(components)

            if len(component) <= small_component_limit and component.isdisjoint(critical_points):
                LOGGER.info(
                    "  Filling small isolated component size=%s limit=%s",
                    len(component),
                    small_component_limit,
                )
                changed = self._fill_isolated_component(component)
                action_key = "filled_components"
            else:
                source = self._nearest_component_point(
                    component,
                    self._component_center(component),
                )
                LOGGER.info(
                    "  Connecting isolated component size=%s from=(%03d,%03d)",
                    len(component),
                    source.x,
                    source.y,
                )
                changed = self._connect_component_to_main(component, main_component)
                action_key = "connected_components"

            after_count = len(MapValidator(self._grid).components())
            metrics["tiles_changed"] += changed
            if changed > 0 and after_count < before_count:
                metrics[action_key] += 1
                continue

            metrics["failed_repairs"] += 1
            LOGGER.warning(
                "  Connectivity repair made no progress: action=%s changed=%s "
                "components_before=%s components_after=%s",
                action_key,
                changed,
                before_count,
                after_count,
            )

        metrics["components_after"] = len(MapValidator(self._grid).components())
        self._connectivity_repair_metrics = metrics
        LOGGER.info(
            "Stage 10c complete: components_before=%s components_after=%s "
            "filled_components=%s connected_components=%s failed_repairs=%s "
            "tiles_changed=%s",
            metrics["components_before"],
            metrics["components_after"],
            metrics["filled_components"],
            metrics["connected_components"],
            metrics["failed_repairs"],
            metrics["tiles_changed"],
        )

    def _small_isolated_component_limit(self) -> int:
        """Return the size limit for isolated walkable components to remove."""
        return max(32, self._derived.cleanup_small_component_max_size)

    def _main_walkable_component(self, components: list[set[Point]]) -> set[Point]:
        """Return the component that should remain the main walkable area."""
        start = self.start_point()
        for component in components:
            if start in component:
                return component
        return components[0]

    def _fill_isolated_component(self, component: set[Point]) -> int:
        """Fill a small isolated walkable component with blocking forest."""
        changed = 0
        for point in component:
            if self._grid.get_tile(point) == TileType.TREE:
                continue
            self._grid.set_tile(point, TileType.TREE)
            self._protected_path.discard(point)
            changed += 1
        return changed

    @staticmethod
    def _nearest_component_point(component: set[Point], target: Point) -> Point:
        """Return component point nearest to target by Manhattan distance."""
        return min(
            component,
            key=lambda point: abs(point.x - target.x) + abs(point.y - target.y),
        )

    def _connect_component_to_main(
        self,
        component: set[Point],
        main_component: set[Point],
    ) -> int:
        """Carve the shortest connector from an isolated component to the main one."""
        connector = self._shortest_connector_path(component, main_component)
        if not connector:
            return 0

        changed = 0
        for point in connector:
            current = self._grid.get_tile(point)
            if current == TileType.PATH:
                self._protected_path.add(point)
                continue
            if current == TileType.START or current == TileType.GOAL:
                self._protected_path.add(point)
                continue
            self._grid.set_tile(point, TileType.PATH)
            self._protected_path.add(point)
            if current != TileType.PATH:
                changed += 1

        return changed

    def _shortest_connector_path(
        self,
        component: set[Point],
        main_component: set[Point],
    ) -> list[Point]:
        """Return a shortest grid path connecting two walkable components."""
        parents: dict[Point, Point | None] = {}
        queue: deque[Point] = deque()

        for point in component:
            parents[point] = None
            queue.append(point)

        end: Point | None = None
        while queue:
            current = queue.popleft()
            if current in main_component:
                end = current
                break

            for neighbor in self._grid.neighbors_4(current):
                if neighbor in parents:
                    continue
                parents[neighbor] = current
                queue.append(neighbor)

        if end is None:
            return []

        path: list[Point] = []
        current: Point | None = end
        while current is not None:
            path.append(current)
            current = parents[current]
        path.reverse()
        return path

    def _ensure_walkable_area(self, center: Point, tile_type: TileType) -> None:
        """Ensure a small walkable patch around a critical point."""
        self._carve_circle(center, 2, tile_type)

    def _validate(self) -> None:
        LOGGER.info("Stage 11: validate map")
        validator = MapValidator(self._grid)
        start = self.start_point()
        goal = self.goal_point()
        central = self.central_point()
        distances = validator.reachable_distances(start)

        if goal not in distances:
            LOGGER.warning("Validation warning: Goal is not reachable from start")

        if central not in distances:
            LOGGER.warning("Validation warning: Central ruin clearing is not reachable from start")

        for region in self._regions:
            if region.center not in distances and not any(point in distances for point in region.entrances):
                LOGGER.warning("Validation warning: Region %s is not reachable", region.region_id)

        components = validator.components()
        path_components = validator.path_network_components()
        walkable_ratio = validator.walkable_ratio()
        dead_end_ratio = validator.dead_end_ratio()
        path_length = distances.get(goal, -1)
        manhattan = max(1, self._manhattan(start, goal))
        tortuosity = path_length / manhattan
        counts = self._tile_counts()
        grass_to_path = counts[TileType.GRASS] / max(1, counts[TileType.PATH])

        LOGGER.info("  Walkable ratio=%.3f", walkable_ratio)
        LOGGER.info("  Dead-end ratio=%.3f", dead_end_ratio)
        LOGGER.info("  Walkable components=%s", len(components))
        LOGGER.info("  Path network components=%s", len(path_components))
        LOGGER.info("  S-G path length=%s", path_length)
        LOGGER.info("  S-G Manhattan=%s", manhattan)
        LOGGER.info("  S-G tortuosity=%.3f", tortuosity)
        LOGGER.info("  Grass/path ratio=%.3f", grass_to_path)
        LOGGER.info("  Tile counts=%s", {tile.value: value for tile, value in counts.items()})

        if len(components) != 1:
            LOGGER.warning("Validation warning: Walkable map has %s components", len(components))

        if walkable_ratio < self._derived.min_walkable_ratio:
            LOGGER.warning("Validation warning: Walkable ratio is too low: %.3f", walkable_ratio)

        if walkable_ratio > self._derived.max_walkable_ratio:
            LOGGER.warning("Validation warning: Walkable ratio is too high: %.3f", walkable_ratio)

        if dead_end_ratio > self._derived.max_dead_end_ratio:
            LOGGER.warning("Validation warning: Dead-end ratio is too high: %.3f", dead_end_ratio)

        if grass_to_path < self._derived.min_grass_to_path_ratio:
            LOGGER.warning("Validation warning: Roads are too wide: grass/path ratio=%.3f", grass_to_path)

    def _winding_points(self, start: Point, end: Point) -> list[Point]:
        current = start
        points = [current]
        safety_limit = self._grid.width * self._grid.height

        while current != end and safety_limit > 0:
            safety_limit -= 1
            dx = end.x - current.x
            dy = end.y - current.y
            move_x = abs(dx) >= abs(dy)

            if self._rng.random() < 0.34:
                move_x = not move_x

            if move_x and dx != 0:
                current = Point(current.x + (1 if dx > 0 else -1), current.y)
            elif dy != 0:
                current = Point(current.x, current.y + (1 if dy > 0 else -1))
            elif dx != 0:
                current = Point(current.x + (1 if dx > 0 else -1), current.y)

            points.append(current)

        if current != end:
            raise GenerationError("Failed to build winding path")

        return points

    def _carve_winding_line(
        self,
        start: Point,
        end: Point,
        width: int,
        tile_type: TileType,
        protect_path: bool,
    ) -> None:
        for point in self._winding_points(start, end):
            self._carve_circle(point, width, tile_type)
            if protect_path:
                self._protected_path.add(point)

    def _carve_circle(self, center: Point, radius: int, tile_type: TileType) -> None:
        radius_squared = radius * radius

        for y in range(center.y - radius, center.y + radius + 1):
            for x in range(center.x - radius, center.x + radius + 1):
                point = Point(x, y)
                if not self._grid.is_inside(point):
                    continue

                dx = x - center.x
                dy = y - center.y
                if dx * dx + dy * dy <= radius_squared:
                    self._set_tile(point, tile_type)

    def _set_tile(self, point: Point, tile_type: TileType) -> None:
        current = self._grid.get_tile(point)

        if self._guidance is not None and tile_type in {TileType.GRASS, TileType.PATH, TileType.WATER}:
            if self._guidance.is_natural_barrier(point.x, point.y):
                key = "path_barrier_tiles_skipped" if tile_type == TileType.PATH else "open_ground_barrier_tiles_skipped"
                self._terrain_guidance_metrics[key] = int(self._terrain_guidance_metrics[key]) + 1
                return
            if tile_type == TileType.WATER and self._guidance.wetland_score(point.x, point.y) < 0.42:
                return

        if current == TileType.RUIN_WALL and tile_type in {
            TileType.GRASS,
            TileType.PATH,
            TileType.BUSH,
        }:
            return

        if tile_type == TileType.PATH and current == TileType.RUIN_WALL:
            self._grid.set_tile(point, TileType.RUIN_FLOOR)
        else:
            self._grid.set_tile(point, tile_type)

    def _can_place_tree_cluster(self, center: Point, radius: int) -> bool:
        expanded = radius + self._derived.bush_ring_thickness
        for y in range(center.y - expanded, center.y + expanded + 1):
            for x in range(center.x - expanded, center.x + expanded + 1):
                point = Point(x, y)
                if not self._grid.is_inside(point):
                    return False
                if point in self._protected_path:
                    return False
                if self._grid.get_tile(point) in {
                    TileType.PATH,
                    TileType.WATER,
                    TileType.CRACKED_GROUND,
                    TileType.RUIN_FLOOR,
                    TileType.RUIN_WALL,
                    TileType.START,
                    TileType.GOAL,
                }:
                    return False
        return True

    def _paint_tree_cluster(self, center: Point, radius: int) -> None:
        bush_radius = radius + self._derived.bush_ring_thickness

        for y in range(center.y - bush_radius, center.y + bush_radius + 1):
            for x in range(center.x - bush_radius, center.x + bush_radius + 1):
                point = Point(x, y)
                if not self._grid.is_inside(point):
                    continue

                dx = x - center.x
                dy = y - center.y
                dist2 = dx * dx + dy * dy

                if dist2 <= radius * radius:
                    if self._rng.random() < 0.86:
                        self._grid.set_tile(point, TileType.TREE)
                elif dist2 <= bush_radius * bush_radius:
                    if self._grid.get_tile(point) == TileType.GRASS:
                        self._grid.set_tile(point, TileType.BUSH)

    def _candidate_edges(self) -> list[Edge]:
        edges: dict[tuple[int, int], Edge] = {}

        for region in self._regions:
            neighbors = sorted(
                (other for other in self._regions if other.region_id != region.region_id),
                key=lambda other: self._manhattan(region.center, other.center),
            )
            for neighbor in neighbors[: self._derived.nearest_neighbor_links]:
                key = self._edge_key(region.region_id, neighbor.region_id)
                edges[key] = Edge(*key)

        result = list(edges.values())
        result.sort(
            key=lambda edge: self._manhattan(
                self._regions[edge.a].center,
                self._regions[edge.b].center,
            ),
        )
        return result

    def _minimum_spanning_tree(self, edges: list[Edge]) -> list[Edge]:
        parent = list(range(len(self._regions)))

        def find(value: int) -> int:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        def union(left: int, right: int) -> bool:
            left_root = find(left)
            right_root = find(right)
            if left_root == right_root:
                return False
            parent[right_root] = left_root
            return True

        result: list[Edge] = []
        for edge in edges:
            if union(edge.a, edge.b):
                result.append(edge)
                if len(result) == len(self._regions) - 1:
                    return result

        all_edges = [
            Edge(a.region_id, b.region_id)
            for index, a in enumerate(self._regions)
            for b in self._regions[index + 1:]
        ]
        all_edges.sort(
            key=lambda edge: self._manhattan(
                self._regions[edge.a].center,
                self._regions[edge.b].center,
            ),
        )

        for edge in all_edges:
            if union(edge.a, edge.b):
                result.append(edge)
                if len(result) == len(self._regions) - 1:
                    return result

        raise GenerationError("Failed to build minimum spanning tree")

    def _find_farthest_pair_excluding(self, excluded_ids: set[int]) -> Edge:
        available = [
            region for region in self._regions
            if region.region_id not in excluded_ids
        ]
        best = Edge(available[0].region_id, available[1].region_id)
        best_distance = -1

        for index, first in enumerate(available):
            for second in available[index + 1:]:
                distance = self._manhattan(first.center, second.center)
                if distance > best_distance:
                    best = Edge(first.region_id, second.region_id)
                    best_distance = distance

        return best

    def _rect_around(self, center: Point, width: int, height: int) -> Rect:
        half_width = width // 2
        half_height = height // 2
        return Rect(
            left=max(4, center.x - half_width),
            top=max(4, center.y - half_height),
            right=min(self._grid.width - 5, center.x + half_width),
            bottom=min(self._grid.height - 5, center.y + half_height),
        )

    def _tile_counts(self) -> dict[TileType, int]:
        counts = {tile: 0 for tile in TileType}
        for y in range(self._grid.height):
            for x in range(self._grid.width):
                counts[self._grid.get_tile(Point(x, y))] += 1
        return counts

    @staticmethod
    def _edge_key(left: int, right: int) -> tuple[int, int]:
        return (left, right) if left < right else (right, left)

    @staticmethod
    def _manhattan(first: Point, second: Point) -> int:
        return abs(first.x - second.x) + abs(first.y - second.y)



@dataclass(frozen=True, slots=True)
class TacticalConfig:
    """Configuration for tactical annotation."""

    cover_scan_radius: int = 1
    combat_zone_radius: int = 11
    central_zone_radius: int = 20
    max_cover_points_per_zone: int = 16
    min_cover_points_per_combat_zone: int = 4


class TacticalAnalyzer:
    """Build tactical metadata from the final generated map."""

    MOVEMENT_COSTS = {
        TileType.GRASS.value: 1,
        TileType.PATH.value: 1,
        TileType.BUSH.value: 2,
        TileType.FLOWER.value: 1,
        TileType.MUSHROOM.value: 1,
        TileType.WATER.value: 3,
        TileType.CRACKED_GROUND.value: 1,
        TileType.RUIN_FLOOR.value: 1,
        TileType.START.value: 1,
        TileType.GOAL.value: 1,
    }

    BLOCKING_TILES = {
        TileType.TREE,
        TileType.RUIN_WALL,
    }

    SOFT_COVER_TILES = {
        TileType.BUSH,
        TileType.TREE,
    }

    HARD_COVER_TILES = {
        TileType.RUIN_WALL,
        TileType.TREE,
    }

    WALKABLE_TILES = {
        TileType.GRASS,
        TileType.PATH,
        TileType.BUSH,
        TileType.FLOWER,
        TileType.MUSHROOM,
        TileType.WATER,
        TileType.CRACKED_GROUND,
        TileType.RUIN_FLOOR,
        TileType.START,
        TileType.GOAL,
    }

    def __init__(
        self,
        grid: MapGrid,
        regions: list[Region],
        start: Point,
        goal: Point,
        central: Point,
        config: TacticalConfig | None = None,
    ) -> None:
        """Initialize tactical analyzer.

        Args:
            grid: Final generated grid.
            regions: Generated high-level regions.
            start: Start point.
            goal: Goal point.
            central: Central ruin clearing point.
            config: Optional tactical analyzer configuration.
        """
        self._grid = grid
        self._regions = regions
        self._start = start
        self._goal = goal
        self._central = central
        self._config = config or TacticalConfig()

    def build(self) -> dict[str, object]:
        """Build tactical metadata.

        Returns:
            JSON-serializable tactical metadata.
        """
        cover_points = self._find_cover_points()
        combat_zones = self._build_combat_zones(cover_points)

        return {
            "version": "0.11",
            "map": {
                "width": self._grid.width,
                "height": self._grid.height,
                "tile_legend": {
                    TileType.GRASS.value: "grass",
                    TileType.PATH.value: "old_overgrown_road",
                    TileType.TREE.value: "tree_blocker",
                    TileType.BUSH.value: "bush_slow_concealment",
                    TileType.FLOWER.value: "flower_decor",
                    TileType.MUSHROOM.value: "mushroom_decor",
                    TileType.WATER.value: "water_slow",
                    TileType.CRACKED_GROUND.value: "cracked_ground",
                    TileType.RUIN_WALL.value: "ruin_wall_blocker",
                    TileType.RUIN_FLOOR.value: "ruin_floor",
                    TileType.START.value: "start",
                    TileType.GOAL.value: "goal",
                },
            },
            "movement_costs": self.MOVEMENT_COSTS,
            "combat_zones": combat_zones,
            "cover_points": cover_points,
            "notes": [
                "v0.15 exports first-pass tactical metadata.",
                "Cover points are walkable cells adjacent to hard or soft blockers.",
                "Combat zones are generated from start, goal, central ruins, and ruin/forest regions.",
                "Flank routes, choke points, spawn zones, and grenade zones are planned for later versions.",
            ],
        }

    def _build_combat_zones(
        self,
        cover_points: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        zones: list[dict[str, object]] = []

        zones.append(
            self._make_zone(
                zone_id="safe_start_0",
                zone_type="safe_start",
                center=self._start,
                radius=10,
                difficulty="none",
                cover_points=cover_points,
                enemy_spawns_allowed=False,
            ),
        )
        zones.append(
            self._make_zone(
                zone_id="goal_encounter_0",
                zone_type="goal_encounter",
                center=self._goal,
                radius=12,
                difficulty="high",
                cover_points=cover_points,
                enemy_spawns_allowed=True,
            ),
        )
        zones.append(
            self._make_zone(
                zone_id="central_ruins_combat_0",
                zone_type="central_ruins_combat",
                center=self._central,
                radius=self._config.central_zone_radius,
                difficulty="high",
                cover_points=cover_points,
                enemy_spawns_allowed=True,
            ),
        )

        side_index = 0
        ambush_index = 0
        for region in self._regions:
            if region.center in {self._start, self._goal, self._central}:
                continue

            if region.kind in {RegionKind.SMALL_RUIN, RegionKind.MEDIUM_RUIN}:
                zones.append(
                    self._make_zone(
                        zone_id=f"side_ruin_encounter_{side_index}",
                        zone_type="side_ruin_encounter",
                        center=region.center,
                        radius=self._config.combat_zone_radius,
                        difficulty="medium",
                        cover_points=cover_points,
                        enemy_spawns_allowed=True,
                    ),
                )
                side_index += 1
                continue

            if region.kind == RegionKind.FOREST and ambush_index < 5:
                local_cover = self._cover_points_in_radius(
                    cover_points,
                    region.center,
                    self._config.combat_zone_radius,
                )
                if len(local_cover) >= self._config.min_cover_points_per_combat_zone:
                    zones.append(
                        self._make_zone(
                            zone_id=f"forest_ambush_{ambush_index}",
                            zone_type="forest_ambush",
                            center=region.center,
                            radius=9,
                            difficulty="medium",
                            cover_points=cover_points,
                            enemy_spawns_allowed=True,
                        ),
                    )
                    ambush_index += 1

        return zones

    def _make_zone(
        self,
        zone_id: str,
        zone_type: str,
        center: Point,
        radius: int,
        difficulty: str,
        cover_points: list[dict[str, object]],
        enemy_spawns_allowed: bool,
    ) -> dict[str, object]:
        local_cover = self._cover_points_in_radius(cover_points, center, radius)
        entrances = self._estimate_zone_entrances(center, radius)
        openness = self._estimate_openness(center, radius)

        return {
            "id": zone_id,
            "type": zone_type,
            "center": [center.x, center.y],
            "radius": radius,
            "difficulty": difficulty,
            "enemy_spawns_allowed": enemy_spawns_allowed,
            "cover_point_ids": [
                str(point["id"])
                for point in local_cover[: self._config.max_cover_points_per_zone]
            ],
            "cover_count": len(local_cover),
            "estimated_entrances": [[point.x, point.y] for point in entrances],
            "openness": round(openness, 3),
        }

    def _find_cover_points(self) -> list[dict[str, object]]:
        cover_points: list[dict[str, object]] = []
        cover_id = 0

        for y in range(self._grid.height):
            for x in range(self._grid.width):
                point = Point(x, y)
                tile = self._grid.get_tile(point)

                if tile not in self.WALKABLE_TILES:
                    continue

                adjacent_cover = self._adjacent_cover_sources(point)
                if not adjacent_cover:
                    continue

                quality = self._cover_quality(adjacent_cover)
                cover_type = "hard" if any(item in self.HARD_COVER_TILES for item in adjacent_cover) else "soft"

                cover_points.append(
                    {
                        "id": f"cover_{cover_id}",
                        "position": [x, y],
                        "quality": quality,
                        "cover_type": cover_type,
                        "source_tiles": sorted({item.value for item in adjacent_cover}),
                        "exposed_directions": self._exposed_directions(point),
                    },
                )
                cover_id += 1

        cover_points.sort(
            key=lambda item: (
                -float(item["quality"]),
                int(item["position"][1]),
                int(item["position"][0]),
            ),
        )
        return cover_points

    def _adjacent_cover_sources(self, point: Point) -> list[TileType]:
        sources: list[TileType] = []
        for neighbor in self._grid.neighbors_4(point):
            tile = self._grid.get_tile(neighbor)
            if tile in self.HARD_COVER_TILES or tile == TileType.BUSH:
                sources.append(tile)
        return sources

    def _cover_quality(self, sources: list[TileType]) -> float:
        quality = 0.0
        for source in sources:
            if source == TileType.RUIN_WALL:
                quality += 0.55
            elif source == TileType.TREE:
                quality += 0.35
            elif source == TileType.BUSH:
                quality += 0.20

        return round(min(1.0, quality), 3)

    def _exposed_directions(self, point: Point) -> list[str]:
        directions = {
            "east": Point(point.x + 1, point.y),
            "west": Point(point.x - 1, point.y),
            "south": Point(point.x, point.y + 1),
            "north": Point(point.x, point.y - 1),
        }
        exposed: list[str] = []

        for name, candidate in directions.items():
            if not self._grid.is_inside(candidate):
                continue
            if self._grid.get_tile(candidate) in self.WALKABLE_TILES:
                exposed.append(name)

        return exposed

    def _cover_points_in_radius(
        self,
        cover_points: list[dict[str, object]],
        center: Point,
        radius: int,
    ) -> list[dict[str, object]]:
        output: list[dict[str, object]] = []
        for cover_point in cover_points:
            x, y = cover_point["position"]
            if abs(int(x) - center.x) + abs(int(y) - center.y) <= radius:
                output.append(cover_point)
        return output

    def _estimate_zone_entrances(self, center: Point, radius: int) -> list[Point]:
        candidates: list[Point] = []

        for angle_point in (
            Point(center.x + radius, center.y),
            Point(center.x - radius, center.y),
            Point(center.x, center.y + radius),
            Point(center.x, center.y - radius),
            Point(center.x + radius, center.y + radius),
            Point(center.x - radius, center.y - radius),
            Point(center.x + radius, center.y - radius),
            Point(center.x - radius, center.y + radius),
        ):
            nearest = self._nearest_walkable(angle_point, max_search=6)
            if nearest is not None:
                candidates.append(nearest)

        unique: list[Point] = []
        seen: set[tuple[int, int]] = set()
        for point in candidates:
            key = (point.x, point.y)
            if key in seen:
                continue
            seen.add(key)
            unique.append(point)

        return unique[:6]

    def _nearest_walkable(self, start: Point, max_search: int) -> Point | None:
        if not self._grid.is_inside(start):
            start = Point(
                min(max(start.x, 0), self._grid.width - 1),
                min(max(start.y, 0), self._grid.height - 1),
            )

        visited = {start}
        queue: deque[tuple[Point, int]] = deque([(start, 0)])

        while queue:
            current, distance = queue.popleft()
            if self._grid.get_tile(current) in self.WALKABLE_TILES:
                return current

            if distance >= max_search:
                continue

            for neighbor in self._grid.neighbors_4(current):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))

        return None

    def _estimate_openness(self, center: Point, radius: int) -> float:
        walkable_count = 0
        total_count = 0

        for y in range(center.y - radius, center.y + radius + 1):
            for x in range(center.x - radius, center.x + radius + 1):
                point = Point(x, y)
                if not self._grid.is_inside(point):
                    continue
                if abs(point.x - center.x) + abs(point.y - center.y) > radius:
                    continue

                total_count += 1
                if self._grid.get_tile(point) in self.WALKABLE_TILES:
                    walkable_count += 1

        return walkable_count / max(1, total_count)


class TacticalExporter:
    """Exports tactical metadata to JSON files."""

    @staticmethod
    def export(data: dict[str, object], path: Path) -> None:
        """Export tactical metadata to a JSON file.

        Args:
            data: Tactical metadata.
            path: Output JSON file path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )



@dataclass(frozen=True, slots=True)
class RenderConfig:
    """Configuration for debug rendering."""

    tile_size_px: int = 16
    cover_point_stride: int = 4
    max_cover_points_per_zone_overlay: int = 16


class TileMapRenderer:
    """Renders an ASCII tile map into a PNG image."""

    TILE_FILES = {
        TileType.GRASS.value: "grass_plus.png",
        TileType.PATH.value: "old_road_dot.png",
        TileType.TREE.value: "tree_T.png",
        TileType.BUSH.value: "bush_b.png",
        TileType.FLOWER.value: "flower_f.png",
        TileType.MUSHROOM.value: "mushroom_m.png",
        TileType.WATER.value: "water_w.png",
        TileType.CRACKED_GROUND.value: "cracked_ground_c.png",
        TileType.RUIN_WALL.value: "ruin_wall_hash.png",
        TileType.RUIN_FLOOR.value: "ruin_floor_R.png",
        TileType.START.value: "start_S.png",
        TileType.GOAL.value: "goal_G.png",
    }

    def __init__(self, asset_root: Path, tile_size_px: int) -> None:
        """Initialize renderer.

        Args:
            asset_root: Asset directory containing tiles_16 and tiles_32.
            tile_size_px: Tile size in pixels.

        Raises:
            ValueError: If tile size is unsupported.
        """
        if tile_size_px not in {16, 32}:
            raise ValueError("Only 16 and 32 pixel tiles are supported")

        self._asset_root = asset_root
        self._tile_size_px = tile_size_px
        self._tiles_dir = asset_root / f"tiles_{tile_size_px}"
        self._tile_images = self._load_tiles()

    def render_map_file(self, map_path: Path, output_path: Path) -> None:
        """Render an ASCII map file.

        Args:
            map_path: Path to generated ASCII map.
            output_path: Output PNG path.
        """
        rows = self._read_map_rows(map_path)
        image = Image.new(
            "RGBA",
            (len(rows[0]) * self._tile_size_px, len(rows) * self._tile_size_px),
            (0, 0, 0, 255),
        )

        for y, row in enumerate(rows):
            for x, symbol in enumerate(row):
                tile = self._tile_images.get(symbol)
                if tile is None:
                    tile = self._tile_images[TileType.GRASS.value]
                image.alpha_composite(tile, (x * self._tile_size_px, y * self._tile_size_px))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)

    def render_debug_overlay(
        self,
        map_path: Path,
        tactical_path: Path,
        output_path: Path,
    ) -> None:
        """Render map with tactical AI debug overlay.

        Args:
            map_path: Path to generated ASCII map.
            tactical_path: Path to tactical JSON.
            output_path: Output PNG path.
        """
        rows = self._read_map_rows(map_path)
        base = self._render_base_image(rows)
        tactical_data = json.loads(tactical_path.read_text(encoding="utf-8"))
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = self._font(max(8, self._tile_size_px // 2))

        self._draw_combat_zones(draw, tactical_data, font)
        self._draw_cover_points(draw, tactical_data)

        result = Image.alpha_composite(base, overlay)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)

    def render_combat_zones_layer(
        self,
        map_path: Path,
        tactical_path: Path,
        output_path: Path,
    ) -> None:
        """Render combat zones as a separate debug layer.

        Args:
            map_path: Path to generated ASCII map.
            tactical_path: Path to tactical JSON.
            output_path: Output PNG path.
        """
        rows = self._read_map_rows(map_path)
        base = self._render_dimmed_base_image(rows)
        tactical_data = json.loads(tactical_path.read_text(encoding="utf-8"))

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = self._font(max(8, self._tile_size_px // 2))

        self._draw_combat_zones(draw, tactical_data, font)

        result = Image.alpha_composite(base, overlay)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)

    def render_cover_points_layer(
        self,
        map_path: Path,
        tactical_path: Path,
        output_path: Path,
    ) -> None:
        """Render cover points as a separate debug layer.

        Args:
            map_path: Path to generated ASCII map.
            tactical_path: Path to tactical JSON.
            output_path: Output PNG path.
        """
        rows = self._read_map_rows(map_path)
        base = self._render_dimmed_base_image(rows)
        tactical_data = json.loads(tactical_path.read_text(encoding="utf-8"))

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        self._draw_cover_points(draw, tactical_data, stride=2)

        result = Image.alpha_composite(base, overlay)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)

    def _render_base_image(self, rows: list[str]) -> Image.Image:
        """Render ASCII rows into a base tile image.

        Args:
            rows: ASCII map rows.

        Returns:
            Rendered base image.
        """
        image = Image.new(
            "RGBA",
            (len(rows[0]) * self._tile_size_px, len(rows) * self._tile_size_px),
            (0, 0, 0, 255),
        )

        for y, row in enumerate(rows):
            for x, symbol in enumerate(row):
                tile = self._tile_images.get(symbol)
                if tile is None:
                    tile = self._tile_images[TileType.GRASS.value]
                image.alpha_composite(tile, (x * self._tile_size_px, y * self._tile_size_px))

        return image

    def _render_dimmed_base_image(self, rows: list[str]) -> Image.Image:
        """Render a dimmed base image for debug layers.

        Args:
            rows: ASCII map rows.

        Returns:
            Dimmed rendered image.
        """
        image = self._render_base_image(rows)
        dim = Image.new("RGBA", image.size, (0, 0, 0, 105))
        return Image.alpha_composite(image, dim)

    def _load_tiles(self) -> dict[str, Image.Image]:
        if not self._tiles_dir.exists():
            raise FileNotFoundError(f"Tiles directory does not exist: {self._tiles_dir}")

        images: dict[str, Image.Image] = {}
        for symbol, filename in self.TILE_FILES.items():
            path = self._tiles_dir / filename
            if not path.exists():
                raise FileNotFoundError(f"Missing tile image: {path}")

            image = Image.open(path).convert("RGBA")
            if image.size != (self._tile_size_px, self._tile_size_px):
                image = image.resize(
                    (self._tile_size_px, self._tile_size_px),
                    Image.Resampling.NEAREST,
                )
            images[symbol] = image

        return images

    @staticmethod
    def _read_map_rows(map_path: Path) -> list[str]:
        rows = [
            line.rstrip("\n")
            for line in map_path.read_text(encoding="utf-8").splitlines()
            if line.rstrip("\n")
        ]
        if not rows:
            raise ValueError(f"Map file is empty: {map_path}")

        width = len(rows[0])
        if any(len(row) != width for row in rows):
            raise ValueError("Map rows must have the same width")

        return rows

    def _draw_combat_zones(
        self,
        draw: ImageDraw.ImageDraw,
        tactical_data: dict[str, object],
        font: ImageFont.ImageFont,
    ) -> None:
        zone_colors = {
            "safe_start": (80, 230, 120, 60),
            "goal_encounter": (190, 80, 230, 70),
            "central_ruins_combat": (235, 65, 65, 75),
            "side_ruin_encounter": (255, 155, 55, 65),
            "forest_ambush": (240, 220, 80, 60),
        }
        outline_colors = {
            "safe_start": (80, 255, 120, 210),
            "goal_encounter": (210, 100, 255, 220),
            "central_ruins_combat": (255, 60, 60, 230),
            "side_ruin_encounter": (255, 160, 55, 220),
            "forest_ambush": (255, 235, 85, 220),
        }

        for zone in tactical_data.get("combat_zones", []):
            if not isinstance(zone, dict):
                continue

            zone_type = str(zone.get("type", "unknown"))
            center = zone.get("center", [0, 0])
            radius = int(zone.get("radius", 1))
            if not isinstance(center, list) or len(center) != 2:
                continue

            cx = int(center[0]) * self._tile_size_px + self._tile_size_px // 2
            cy = int(center[1]) * self._tile_size_px + self._tile_size_px // 2
            pr = radius * self._tile_size_px

            fill = zone_colors.get(zone_type, (255, 255, 255, 45))
            outline = outline_colors.get(zone_type, (255, 255, 255, 190))
            draw.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=fill, outline=outline, width=2)

            label = str(zone.get("id", zone_type))
            draw.text(
                (cx + 4, cy + 4),
                label,
                font=font,
                fill=(255, 255, 255, 235),
                stroke_width=1,
                stroke_fill=(0, 0, 0, 200),
            )

    def _draw_cover_points(
        self,
        draw: ImageDraw.ImageDraw,
        tactical_data: dict[str, object],
        stride: int = 4,
    ) -> None:
        for index, cover in enumerate(tactical_data.get("cover_points", [])):
            if not isinstance(cover, dict):
                continue
            if index % stride != 0:
                continue

            position = cover.get("position", [0, 0])
            if not isinstance(position, list) or len(position) != 2:
                continue

            cover_type = str(cover.get("cover_type", "soft"))
            x = int(position[0]) * self._tile_size_px + self._tile_size_px // 2
            y = int(position[1]) * self._tile_size_px + self._tile_size_px // 2

            if cover_type == "hard":
                fill = (55, 120, 255, 210)
                radius = max(2, self._tile_size_px // 5)
            else:
                fill = (60, 230, 210, 180)
                radius = max(1, self._tile_size_px // 6)

            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)

    def _draw_start_goal(
        self,
        draw: ImageDraw.ImageDraw,
        tactical_data: dict[str, object],
        rows: list[str],
        font: ImageFont.ImageFont,
    ) -> None:
        markers = {"S": (60, 255, 110, 255), "G": (255, 235, 85, 255)}
        for symbol, color in markers.items():
            for y, row in enumerate(rows):
                x = row.find(symbol)
                if x < 0:
                    continue

                cx = x * self._tile_size_px + self._tile_size_px // 2
                cy = y * self._tile_size_px + self._tile_size_px // 2
                radius = max(5, self._tile_size_px // 2)
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=color, width=3)
                draw.text(
                    (cx + radius + 2, cy - radius),
                    symbol,
                    font=font,
                    fill=color,
                    stroke_width=1,
                    stroke_fill=(0, 0, 0, 220),
                )
                break

    @staticmethod
    def _font(size: int) -> ImageFont.ImageFont:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                return ImageFont.truetype(str(path), size)
        return ImageFont.load_default()


class RenderPipeline:
    """Runs PNG rendering after map and tactical metadata generation."""

    @staticmethod
    def render_outputs(
        map_path: Path,
        tactical_path: Path,
        asset_root: Path,
        tile_size_px: int,
        render_out: Path,
        debug_render_out: Path,
        combat_zones_out: Path,
        cover_points_out: Path,
    ) -> None:
        """Render base and separate AI debug PNG files.

        Args:
            map_path: ASCII map path.
            tactical_path: Tactical JSON path.
            asset_root: Asset directory.
            tile_size_px: Tile size in pixels.
            render_out: Base map PNG path.
            debug_render_out: Combined AI debug PNG path.
            combat_zones_out: Combat zones layer PNG path.
            cover_points_out: Cover points layer PNG path.
        """
        renderer = TileMapRenderer(asset_root=asset_root, tile_size_px=tile_size_px)
        renderer.render_map_file(map_path, render_out)
        renderer.render_combat_zones_layer(map_path, tactical_path, combat_zones_out)
        renderer.render_cover_points_layer(map_path, tactical_path, cover_points_out)
        renderer.render_debug_overlay(map_path, tactical_path, debug_render_out)



class AdvancedTacticalAnalyzer:
    """Adds second-pass tactical metadata used by AI debug layers."""

    WALKABLE_TILES = {
        TileType.GRASS,
        TileType.PATH,
        TileType.BUSH,
        TileType.FLOWER,
        TileType.MUSHROOM,
        TileType.WATER,
        TileType.CRACKED_GROUND,
        TileType.RUIN_FLOOR,
        TileType.START,
        TileType.GOAL,
    }

    BLOCKER_TILES = {
        TileType.TREE,
        TileType.RUIN_WALL,
    }

    MOVEMENT_COST_BY_TILE = {
        TileType.GRASS: 1.0,
        TileType.PATH: 1.0,
        TileType.FLOWER: 1.0,
        TileType.MUSHROOM: 1.0,
        TileType.CRACKED_GROUND: 1.0,
        TileType.RUIN_FLOOR: 1.0,
        TileType.START: 1.0,
        TileType.GOAL: 1.0,
        TileType.BUSH: 2.0,
        TileType.WATER: 3.0,
    }

    def __init__(
        self,
        grid: MapGrid,
        start: Point,
        tactical_data: dict[str, object],
    ) -> None:
        """Initialize advanced tactical analyzer.

        Args:
            grid: Final generated map grid.
            start: Player start point.
            tactical_data: First-pass tactical metadata.
        """
        self._grid = grid
        self._start = start
        self._tactical_data = tactical_data

    def build(self) -> dict[str, object]:
        """Build enriched tactical metadata.

        Returns:
            Enriched tactical metadata.
        """
        enriched = dict(self._tactical_data)
        raw_chokes = self._find_raw_choke_points()
        enriched["choke_points"] = self._cluster_choke_points(raw_chokes)
        enriched["flank_routes"] = self._build_flank_routes(enriched)
        enriched["enemy_spawn_zones"] = self._build_enemy_spawn_zones(enriched)
        enriched["notes"] = [
            *list(enriched.get("notes", [])),
            "v0.15 clusters choke points and uses A* waypoints for flank routes.",
            "Flank route length is based on actual path cost, not a straight line.",
        ]
        return enriched

    def _find_raw_choke_points(self) -> list[dict[str, object]]:
        raw_points: list[dict[str, object]] = []

        for y in range(2, self._grid.height - 2):
            for x in range(2, self._grid.width - 2):
                point = Point(x, y)
                if not self._is_walkable(point):
                    continue

                if self._manhattan(point, self._start) < 12:
                    continue

                open_neighbors = sum(
                    1 for neighbor in self._grid.neighbors_4(point)
                    if self._is_walkable(neighbor)
                )
                blocker_score = self._nearby_blocker_count(point, radius=2)

                if open_neighbors <= 2 and blocker_score >= 5:
                    raw_points.append(
                        {
                            "position": [point.x, point.y],
                            "width_estimate": open_neighbors,
                            "blocker_score": blocker_score,
                            "priority": round(min(1.0, blocker_score / 12.0), 3),
                        },
                    )

        return raw_points

    def _cluster_choke_points(
        self,
        raw_points: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Cluster noisy raw choke cells into fewer tactical choke points."""
        remaining = list(raw_points)
        clusters: list[list[dict[str, object]]] = []
        cluster_radius = 7

        while remaining:
            seed = max(
                remaining,
                key=lambda item: (
                    float(item.get("priority", 0.0)),
                    int(item.get("blocker_score", 0)),
                ),
            )
            seed_point = self._point_from_json(seed.get("position"))
            if seed_point is None:
                remaining.remove(seed)
                continue

            cluster: list[dict[str, object]] = []
            next_remaining: list[dict[str, object]] = []

            for item in remaining:
                item_point = self._point_from_json(item.get("position"))
                if item_point is None:
                    continue
                if self._manhattan(seed_point, item_point) <= cluster_radius:
                    cluster.append(item)
                else:
                    next_remaining.append(item)

            remaining = next_remaining
            clusters.append(cluster)

        ranked: list[dict[str, object]] = []
        for cluster in clusters:
            if not cluster:
                continue

            best = max(
                cluster,
                key=lambda item: (
                    float(item.get("priority", 0.0)),
                    int(item.get("blocker_score", 0)),
                ),
            )
            best_point = self._point_from_json(best.get("position"))
            if best_point is None:
                continue

            avg_blocker = sum(int(item.get("blocker_score", 0)) for item in cluster) / len(cluster)
            avg_width = sum(int(item.get("width_estimate", 0)) for item in cluster) / len(cluster)
            priority = min(1.0, (avg_blocker / 12.0) + min(0.25, len(cluster) / 80.0))

            ranked.append(
                {
                    "id": f"choke_{len(ranked)}",
                    "position": [best_point.x, best_point.y],
                    "width_estimate": round(avg_width, 2),
                    "blocker_score": round(avg_blocker, 2),
                    "priority": round(priority, 3),
                    "cluster_size": len(cluster),
                },
            )

        ranked.sort(
            key=lambda item: (
                -float(item.get("priority", 0.0)),
                -int(item.get("cluster_size", 0)),
            ),
        )

        output = ranked[:32]
        for index, item in enumerate(output):
            item["id"] = f"choke_{index}"
        return output

    def _build_flank_routes(
        self,
        tactical_data: dict[str, object],
    ) -> list[dict[str, object]]:
        zones = [
            zone for zone in tactical_data.get("combat_zones", [])
            if isinstance(zone, dict)
            and zone.get("type") != "safe_start"
            and zone.get("enemy_spawns_allowed", False)
        ]

        routes: list[dict[str, object]] = []
        route_id = 0

        for index, first in enumerate(zones):
            for second in zones[index + 1:]:
                first_center = self._point_from_json(first.get("center"))
                second_center = self._point_from_json(second.get("center"))
                if first_center is None or second_center is None:
                    continue

                straight_distance = self._manhattan(first_center, second_center)
                if straight_distance < 16 or straight_distance > 70:
                    continue

                first_entry = self._first_entrance_or_center(first)
                second_entry = self._first_entrance_or_center(second)
                if first_entry is None or second_entry is None:
                    continue

                path = self._find_weighted_path(first_entry, second_entry, max_expansions=4500)
                if not path:
                    continue

                waypoints = self._simplify_path_to_waypoints(path, max_waypoints=10)
                concealment = self._path_concealment(path)
                path_cost = self._path_cost(path)
                risk = round(max(0.1, 1.0 - concealment + min(0.25, path_cost / 200.0)), 3)

                routes.append(
                    {
                        "id": f"flank_route_{route_id}",
                        "from_zone": str(first.get("id", "")),
                        "to_zone": str(second.get("id", "")),
                        "entry": [first_entry.x, first_entry.y],
                        "exit": [second_entry.x, second_entry.y],
                        "length": len(path),
                        "cost": round(path_cost, 2),
                        "risk": min(1.0, risk),
                        "concealment": concealment,
                        "waypoints": [[point.x, point.y] for point in waypoints],
                    },
                )
                route_id += 1

                if len(routes) >= 36:
                    return routes

        return routes

    def _find_weighted_path(
        self,
        start: Point,
        goal: Point,
        max_expansions: int,
    ) -> list[Point]:
        """Find a weighted path using A*.

        Args:
            start: Path start.
            goal: Path goal.
            max_expansions: Maximum node expansions.

        Returns:
            Path points from start to goal, or an empty list.
        """
        import heapq

        if not self._is_walkable(start) or not self._is_walkable(goal):
            return []

        open_heap: list[tuple[float, int, Point]] = []
        heapq.heappush(open_heap, (0.0, 0, start))

        came_from: dict[Point, Point] = {}
        g_score: dict[Point, float] = {start: 0.0}
        counter = 1
        expansions = 0

        while open_heap and expansions < max_expansions:
            _, _, current = heapq.heappop(open_heap)
            expansions += 1

            if current == goal:
                return self._reconstruct_path(came_from, current)

            for neighbor in self._grid.neighbors_4(current):
                if not self._is_walkable(neighbor):
                    continue

                tentative = g_score[current] + self._movement_cost(neighbor)
                if tentative >= g_score.get(neighbor, float("inf")):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative
                priority = tentative + self._manhattan(neighbor, goal) * 1.05
                heapq.heappush(open_heap, (priority, counter, neighbor))
                counter += 1

        return []

    def _reconstruct_path(
        self,
        came_from: dict[Point, Point],
        current: Point,
    ) -> list[Point]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _movement_cost(self, point: Point) -> float:
        tile = self._grid.get_tile(point)
        return self.MOVEMENT_COST_BY_TILE.get(tile, float("inf"))

    def _path_cost(self, path: list[Point]) -> float:
        return sum(self._movement_cost(point) for point in path)

    def _simplify_path_to_waypoints(
        self,
        path: list[Point],
        max_waypoints: int,
    ) -> list[Point]:
        """Simplify a full path to turning points and sampled waypoints."""
        if len(path) <= 2:
            return path

        waypoints = [path[0]]
        previous_direction: tuple[int, int] | None = None

        for first, second in zip(path, path[1:]):
            direction = (
                0 if second.x == first.x else (1 if second.x > first.x else -1),
                0 if second.y == first.y else (1 if second.y > first.y else -1),
            )
            if previous_direction is not None and direction != previous_direction:
                waypoints.append(first)
            previous_direction = direction

        waypoints.append(path[-1])

        if len(waypoints) <= max_waypoints:
            return waypoints

        sampled = [waypoints[0]]
        step = max(1, (len(waypoints) - 2) // max(1, max_waypoints - 2))
        sampled.extend(waypoints[1:-1:step])
        sampled.append(waypoints[-1])
        return sampled[:max_waypoints]

    def _path_concealment(self, path: list[Point]) -> float:
        if not path:
            return 0.0

        concealment_hits = 0
        for point in path:
            if self._nearby_blocker_count(point, radius=2) >= 3:
                concealment_hits += 1

        return round(concealment_hits / len(path), 3)

    def _build_enemy_spawn_zones(
        self,
        tactical_data: dict[str, object],
    ) -> list[dict[str, object]]:
        cover_by_id = {
            str(point.get("id")): point
            for point in tactical_data.get("cover_points", [])
            if isinstance(point, dict)
        }
        spawn_zones: list[dict[str, object]] = []
        spawn_id = 0

        for zone in tactical_data.get("combat_zones", []):
            if not isinstance(zone, dict):
                continue

            if not zone.get("enemy_spawns_allowed", False):
                continue

            zone_id = str(zone.get("id", ""))
            zone_type = str(zone.get("type", "unknown"))
            cover_ids = list(zone.get("cover_point_ids", []))
            selected = 0

            for cover_id in cover_ids:
                cover = cover_by_id.get(str(cover_id))
                if cover is None:
                    continue

                position = self._point_from_json(cover.get("position"))
                if position is None:
                    continue

                if self._manhattan(position, self._start) < 22:
                    continue

                quality = float(cover.get("quality", 0.0))
                if quality < 0.35:
                    continue

                spawn_zones.append(
                    {
                        "id": f"spawn_{spawn_id}",
                        "zone_id": zone_id,
                        "zone_type": zone_type,
                        "position": [position.x, position.y],
                        "preferred_roles": self._roles_for_zone(zone_type),
                        "cover_point_id": str(cover_id),
                        "quality": round(quality, 3),
                    },
                )
                spawn_id += 1
                selected += 1

                if selected >= 3:
                    break

        return spawn_zones

    def _roles_for_zone(self, zone_type: str) -> list[str]:
        if zone_type == "central_ruins_combat":
            return ["rifleman", "flanker", "grenadier"]
        if zone_type == "goal_encounter":
            return ["rifleman", "defender"]
        if zone_type == "forest_ambush":
            return ["flanker", "scout"]
        if zone_type == "side_ruin_encounter":
            return ["rifleman", "defender"]
        return ["rifleman"]

    def _is_walkable(self, point: Point) -> bool:
        return self._grid.get_tile(point) in self.WALKABLE_TILES

    def _nearby_blocker_count(self, point: Point, radius: int) -> int:
        count = 0
        for y in range(point.y - radius, point.y + radius + 1):
            for x in range(point.x - radius, point.x + radius + 1):
                candidate = Point(x, y)
                if not self._grid.is_inside(candidate):
                    continue
                if self._grid.get_tile(candidate) in self.BLOCKER_TILES:
                    count += 1
        return count

    @staticmethod
    def _point_from_json(value: object) -> Point | None:
        if not isinstance(value, list) or len(value) != 2:
            return None
        return Point(int(value[0]), int(value[1]))

    def _first_entrance_or_center(self, zone: dict[str, object]) -> Point | None:
        entrances = zone.get("estimated_entrances", [])
        if isinstance(entrances, list) and entrances:
            entrance = self._point_from_json(entrances[0])
            if entrance is not None:
                return entrance
        return self._point_from_json(zone.get("center"))

    @staticmethod
    def _manhattan(first: Point, second: Point) -> int:
        return abs(first.x - second.x) + abs(first.y - second.y)


class AdvancedTacticalLayerRenderer:
    """Renders second-pass tactical debug layers."""

    def __init__(self, asset_root: Path, tile_size_px: int) -> None:
        """Initialize renderer.

        Args:
            asset_root: Asset directory.
            tile_size_px: Tile size in pixels.
        """
        self._tile_renderer = TileMapRenderer(asset_root=asset_root, tile_size_px=tile_size_px)
        self._tile_size_px = tile_size_px

    def render_choke_points_layer(
        self,
        map_path: Path,
        tactical_path: Path,
        output_path: Path,
    ) -> None:
        """Render choke points layer.

        Args:
            map_path: ASCII map path.
            tactical_path: Tactical JSON path.
            output_path: Output PNG path.
        """
        rows = self._tile_renderer._read_map_rows(map_path)
        base = self._tile_renderer._render_dimmed_base_image(rows)
        data = json.loads(tactical_path.read_text(encoding="utf-8"))

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = self._tile_renderer._font(max(8, self._tile_size_px // 2))

        for point in data.get("choke_points", []):
            if not isinstance(point, dict):
                continue
            position = point.get("position", [0, 0])
            if not isinstance(position, list) or len(position) != 2:
                continue

            x = int(position[0]) * self._tile_size_px + self._tile_size_px // 2
            y = int(position[1]) * self._tile_size_px + self._tile_size_px // 2
            radius = max(4, self._tile_size_px // 3)
            cluster_size = int(point.get("cluster_size", 1))

            draw.line((x - radius, y, x + radius, y), fill=(255, 40, 40, 235), width=2)
            draw.line((x, y - radius, x, y + radius), fill=(255, 40, 40, 235), width=2)
            if cluster_size >= 8:
                draw.ellipse(
                    (x - radius - 3, y - radius - 3, x + radius + 3, y + radius + 3),
                    outline=(255, 160, 80, 190),
                    width=1,
                )

        result = Image.alpha_composite(base, overlay)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)

    def render_flank_routes_layer(
        self,
        map_path: Path,
        tactical_path: Path,
        output_path: Path,
    ) -> None:
        """Render flank routes layer using real A* waypoints.

        Args:
            map_path: ASCII map path.
            tactical_path: Tactical JSON path.
            output_path: Output PNG path.
        """
        rows = self._tile_renderer._read_map_rows(map_path)
        base = self._tile_renderer._render_dimmed_base_image(rows)
        data = json.loads(tactical_path.read_text(encoding="utf-8"))

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for route in data.get("flank_routes", []):
            if not isinstance(route, dict):
                continue

            raw_waypoints = route.get("waypoints", [])
            if not isinstance(raw_waypoints, list) or len(raw_waypoints) < 2:
                continue

            points: list[tuple[int, int]] = []
            for waypoint in raw_waypoints:
                if not isinstance(waypoint, list) or len(waypoint) != 2:
                    continue
                points.append(
                    (
                        int(waypoint[0]) * self._tile_size_px + self._tile_size_px // 2,
                        int(waypoint[1]) * self._tile_size_px + self._tile_size_px // 2,
                    ),
                )

            if len(points) < 2:
                continue

            concealment = float(route.get("concealment", 0.0))
            color = (
                255,
                230,
                70,
                int(120 + min(110, concealment * 110)),
            )
            draw.line(points, fill=color, width=max(2, self._tile_size_px // 5), joint="curve")

            first = points[0]
            last = points[-1]
            draw.ellipse((first[0] - 4, first[1] - 4, first[0] + 4, first[1] + 4), fill=(255, 245, 90, 235))
            draw.ellipse((last[0] - 4, last[1] - 4, last[0] + 4, last[1] + 4), fill=(255, 150, 45, 235))

        result = Image.alpha_composite(base, overlay)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)

    def render_enemy_spawn_zones_layer(
        self,
        map_path: Path,
        tactical_path: Path,
        output_path: Path,
    ) -> None:
        """Render enemy spawn zones layer.

        Args:
            map_path: ASCII map path.
            tactical_path: Tactical JSON path.
            output_path: Output PNG path.
        """
        rows = self._tile_renderer._read_map_rows(map_path)
        base = self._tile_renderer._render_dimmed_base_image(rows)
        data = json.loads(tactical_path.read_text(encoding="utf-8"))

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for spawn in data.get("enemy_spawn_zones", []):
            if not isinstance(spawn, dict):
                continue

            position = spawn.get("position", [0, 0])
            if not isinstance(position, list) or len(position) != 2:
                continue

            x = int(position[0]) * self._tile_size_px + self._tile_size_px // 2
            y = int(position[1]) * self._tile_size_px + self._tile_size_px // 2
            radius = max(4, self._tile_size_px // 3)

            draw.rectangle(
                (x - radius, y - radius, x + radius, y + radius),
                outline=(255, 90, 255, 240),
                fill=(255, 90, 255, 95),
                width=2,
            )

        result = Image.alpha_composite(base, overlay)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)


class AsciiExporter:
    """Exports maps to ASCII files."""

    @staticmethod
    def export(grid: MapGrid, path: Path) -> None:
        """Export grid to ASCII file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(grid.rows_as_text()) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate a top-down ASCII map.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("-o", "--out", required=True, type=Path)
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument(
        "--geography-guidance",
        type=Path,
        default=None,
        help="Optional internal geography guidance JSON.",
    )
    parser.add_argument(
        "--tactical-out",
        type=Path,
        default=None,
        help="Optional path to tactical JSON output.",
    )
    parser.add_argument(
        "--render-out",
        type=Path,
        default=None,
        help="Optional path to base rendered map PNG.",
    )
    parser.add_argument(
        "--debug-render-out",
        type=Path,
        default=None,
        help="Optional path to combined AI debug overlay PNG.",
    )
    parser.add_argument(
        "--combat-zones-render-out",
        type=Path,
        default=None,
        help="Optional path to combat zones debug layer PNG.",
    )
    parser.add_argument(
        "--cover-points-render-out",
        type=Path,
        default=None,
        help="Optional path to cover points debug layer PNG.",
    )
    parser.add_argument(
        "--choke-points-render-out",
        type=Path,
        default=None,
        help="Optional path to choke points debug layer PNG.",
    )
    parser.add_argument(
        "--flank-routes-render-out",
        type=Path,
        default=None,
        help="Optional path to flank routes debug layer PNG.",
    )
    parser.add_argument(
        "--enemy-spawn-zones-render-out",
        type=Path,
        default=None,
        help="Optional path to enemy spawn zones debug layer PNG.",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=None,
        help="Optional path to tile assets directory.",
    )
    parser.add_argument(
        "--render-tile-size",
        type=int,
        choices=[16, 32],
        default=16,
        help="Tile size for PNG rendering.",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Disable PNG rendering.",
    )
    return parser.parse_args()


def configure_logging(verbose: bool, log_file: Path | None) -> None:
    """Configure logging.

    Args:
        verbose: Whether verbose logging is enabled.
        log_file: Optional log file path.
    """
    level = logging.INFO if verbose else logging.WARNING
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    """Run generator CLI with retry attempts for random seeds."""
    args = parse_args()

    try:
        public_config = PublicConfig.from_json_file(args.config)
        configure_logging(True, args.log_file)
        max_attempts = DerivedConfig.from_public(public_config).max_generation_attempts
        tactical_out = args.tactical_out or args.out.with_name("tactical_map.json")
        render_out = args.render_out or args.out.with_name("layer_base_map.png")
        debug_render_out = args.debug_render_out or args.out.with_name("layer_all_debug.png")
        combat_zones_render_out = (
            args.combat_zones_render_out
            or args.out.with_name("layer_combat_zones.png")
        )
        cover_points_render_out = (
            args.cover_points_render_out
            or args.out.with_name("layer_cover_points.png")
        )
        choke_points_render_out = (
            args.choke_points_render_out
            or args.out.with_name("layer_choke_points.png")
        )
        flank_routes_render_out = (
            args.flank_routes_render_out
            or args.out.with_name("layer_flank_routes.png")
        )
        enemy_spawn_zones_render_out = (
            args.enemy_spawn_zones_render_out
            or args.out.with_name("layer_enemy_spawn_zones.png")
        )
        assets_dir = args.assets_dir or Path(__file__).resolve().parent / "assets"
        terrain_guidance = None
        if args.geography_guidance is not None:
            terrain_guidance = TerrainGuidance.from_json_file(
                args.geography_guidance,
                expected_width=public_config.map_width_tiles,
                expected_height=public_config.map_height_tiles,
                expected_seed=public_config.resolve_seed(),
            )
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            LOGGER.info("GENERATION ATTEMPT %s/%s", attempt, max_attempts)
            try:
                generator = MapGenerator(public_config, terrain_guidance=terrain_guidance)
                grid = generator.generate()
                AsciiExporter.export(grid, args.out)

                tactical_data = TacticalAnalyzer(
                    grid=grid,
                    regions=generator.regions(),
                    start=generator.start_point(),
                    goal=generator.goal_point(),
                    central=generator.central_point(),
                ).build()
                tactical_data = AdvancedTacticalAnalyzer(
                    grid=grid,
                    start=generator.start_point(),
                    tactical_data=tactical_data,
                ).build()
                tactical_data["connectivity_repair"] = generator.connectivity_repair_metrics()
                tactical_data["terrain_guidance"] = generator.terrain_guidance_metrics()
                TacticalExporter.export(tactical_data, tactical_out)

                if not args.no_render:
                    RenderPipeline.render_outputs(
                        map_path=args.out,
                        tactical_path=tactical_out,
                        asset_root=assets_dir,
                        tile_size_px=args.render_tile_size,
                        render_out=render_out,
                        debug_render_out=debug_render_out,
                        combat_zones_out=combat_zones_render_out,
                        cover_points_out=cover_points_render_out,
                    )
                    advanced_renderer = AdvancedTacticalLayerRenderer(
                        asset_root=assets_dir,
                        tile_size_px=args.render_tile_size,
                    )
                    advanced_renderer.render_choke_points_layer(
                        args.out,
                        tactical_out,
                        choke_points_render_out,
                    )
                    advanced_renderer.render_flank_routes_layer(
                        args.out,
                        tactical_out,
                        flank_routes_render_out,
                    )
                    advanced_renderer.render_enemy_spawn_zones_layer(
                        args.out,
                        tactical_out,
                        enemy_spawn_zones_render_out,
                    )

                LOGGER.info("Generation attempt %s succeeded", attempt)
                LOGGER.info("Generated map saved to: %s", args.out)
                LOGGER.info("Tactical map saved to: %s", tactical_out)
                if not args.no_render:
                    LOGGER.info("Base map layer saved to: %s", render_out)
                    LOGGER.info("Combat zones layer saved to: %s", combat_zones_render_out)
                    LOGGER.info("Cover points layer saved to: %s", cover_points_render_out)
                    LOGGER.info("Choke points layer saved to: %s", choke_points_render_out)
                    LOGGER.info("Flank routes layer saved to: %s", flank_routes_render_out)
                    LOGGER.info("Enemy spawn zones layer saved to: %s", enemy_spawn_zones_render_out)
                    LOGGER.info("Combined AI debug layer saved to: %s", debug_render_out)
                return 0
            except GenerationError as exc:
                last_error = exc
                LOGGER.warning("Generation attempt %s failed: %s", attempt, exc)

        LOGGER.error("All generation attempts failed. Last error: %s", last_error)
        return 1

    except (ConfigError, TerrainGuidanceError, OSError) as exc:
        if not logging.getLogger().handlers:
            configure_logging(True, None)
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
