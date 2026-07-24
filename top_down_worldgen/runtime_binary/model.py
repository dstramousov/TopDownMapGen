"""Data models used by the runtime binary writer and validator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import FORMAT_MAJOR, FORMAT_MINOR, FORMAT_NAME, REGION_SIZE_TILES


@dataclass(frozen=True, slots=True)
class RuntimeBinarySource:
    """In-memory source data for one runtime container.

    Args:
        width: Map width in tiles.
        height: Map height in tiles.
        tile_size_px: Render tile size in pixels.
        resolved_seed: Concrete seed used for generation.
        generator_version: Generator semantic version.
        pipeline_version: Pipeline contract version.
        profile: Active generation profile.
        map_schema: Public map index schema.
        package_schema: Public package schema.
        terrain_rows: Terrain type name per tile.
        movement_rows: Movement cost per tile or None for blocked tiles.
        collision_rows: Terrain collision rows encoded as zero/one strings.
        projectile_rows: Projectile block rows encoded as zero/one strings.
        vision_rows: Vision block rows encoded as zero/one strings.
        cover_rows: Cover values in the inclusive range zero to one.
        concealment_rows: Concealment values in the inclusive range zero to one.
        elevation_rows: Signed elevation level per tile.
        structure_height_rows: Logical height levels above ground per tile.
        start: Optional start point.
        goal: Optional goal point.
        terrain_catalog: Public terrain catalog object.
    """

    width: int
    height: int
    tile_size_px: int
    resolved_seed: int
    generator_version: str
    pipeline_version: str
    profile: str
    map_schema: str
    package_schema: str
    terrain_rows: list[list[str]]
    movement_rows: list[list[int | float | None]]
    collision_rows: list[str]
    projectile_rows: list[str]
    vision_rows: list[str]
    cover_rows: list[list[int | float]]
    concealment_rows: list[list[int | float]]
    elevation_rows: list[list[int]]
    structure_height_rows: list[list[int]]
    start: dict[str, int] | None
    goal: dict[str, int] | None
    terrain_catalog: dict[str, Any]


@dataclass(slots=True)
class SectionDescriptor:
    """Mutable section layout descriptor."""

    section_type: int
    section_flags: int
    section_id: int
    parent_id: int
    payload: bytes
    element_count: int
    element_stride: int
    alignment: int
    aux_0: int = 0
    aux_1: int = 0
    offset: int = 0
    crc32: int = 0

    @property
    def stored_size(self) -> int:
        """Return the stored payload size."""
        return len(self.payload)


@dataclass(frozen=True, slots=True)
class RuntimeBinaryResult:
    """Result returned after successful binary generation."""

    path: Path
    build_id: bytes
    file_size: int
    section_count: int
    region_count_x: int
    region_count_y: int
    terrain_count: int
    string_count: int
    write_time_ms: float
    validate_time_ms: float

    def map_index_entry(self, package_dir: Path) -> dict[str, Any]:
        """Build the public map.json runtime_binary object.

        Args:
            package_dir: Directory containing the runtime file.

        Returns:
            JSON-compatible metadata object.
        """
        return {
            "path": self.path.relative_to(package_dir).as_posix(),
            "format": FORMAT_NAME,
            "format_major": FORMAT_MAJOR,
            "format_minor": FORMAT_MINOR,
            "build_id": self.build_id.hex(),
            "file_size": self.file_size,
            "section_count": self.section_count,
            "region_size_tiles": REGION_SIZE_TILES,
            "regions": {
                "x": self.region_count_x,
                "y": self.region_count_y,
                "total": self.region_count_x * self.region_count_y,
            },
        }
