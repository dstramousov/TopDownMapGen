"""Constants for the deterministic VoX3D runtime container."""

from __future__ import annotations

from enum import IntEnum, IntFlag

MAGIC = b"VXMAPBIN"
FORMAT_NAME = "vxmap-runtime-v1"
FORMAT_MAJOR = 1
FORMAT_MINOR = 1
HEADER_SIZE = 128
SECTION_ENTRY_SIZE = 64
REGION_RECORD_SIZE = 32
REGION_SIZE_TILES = 128
NULL_ID = 0xFFFFFFFF
ENDIAN_MARKER = 0x01020304
GRID_ALIGNMENT = 64
DEFAULT_ALIGNMENT = 8
MAX_SECTION_COUNT = 1_000_000


class HeaderFlags(IntFlag):
    """Flags stored in the fixed container header."""

    ROW_MAJOR = 1 << 0
    ORIGIN_TOP_LEFT = 1 << 1
    Y_AXIS_DOWN = 1 << 2
    HAS_REGION_INDEX = 1 << 3
    HAS_FILE_CRC32 = 1 << 5
    ALL_CORE_SECTIONS_UNCOMPRESSED = 1 << 6


class SectionFlags(IntFlag):
    """Flags stored in a section table entry."""

    REQUIRED = 1 << 0
    SINGLETON = 1 << 1
    REGIONAL = 1 << 2
    MEMORY_MAPPABLE = 1 << 3
    CONTAINS_OFFSETS = 1 << 4
    CRC_REQUIRED = 1 << 5


class Codec(IntEnum):
    """Supported payload codecs."""

    NONE = 0


class SectionType(IntEnum):
    """Published section identifiers for runtime container v1."""

    METADATA = 1
    STRING_TABLE = 2
    STRING_ID_POOL = 3
    REGION_INDEX = 5
    TERRAIN_CATALOG = 10
    TERRAIN_GRID = 20
    ELEVATION_GRID = 21
    MOVEMENT_GRID = 22
    COLLISION_BITS = 23
    PROJECTILE_BLOCK_BITS = 24
    VISION_BLOCK_BITS = 25
    COVER_GRID_U8 = 26
    CONCEALMENT_GRID_U8 = 27
    STRUCTURE_HEIGHT_U8 = 28
    START_GOAL = 30


CORE_HEADER_FLAGS = int(
    HeaderFlags.ROW_MAJOR
    | HeaderFlags.ORIGIN_TOP_LEFT
    | HeaderFlags.Y_AXIS_DOWN
    | HeaderFlags.HAS_REGION_INDEX
    | HeaderFlags.ALL_CORE_SECTIONS_UNCOMPRESSED
)

GLOBAL_REQUIRED_FLAGS = int(
    SectionFlags.REQUIRED | SectionFlags.SINGLETON | SectionFlags.CRC_REQUIRED
)
REGIONAL_GRID_FLAGS = int(
    SectionFlags.REQUIRED
    | SectionFlags.REGIONAL
    | SectionFlags.MEMORY_MAPPABLE
    | SectionFlags.CRC_REQUIRED
)
