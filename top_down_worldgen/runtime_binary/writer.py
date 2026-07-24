"""Deterministic writer for the VoX3D runtime binary container."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import struct
import time
import zlib
from pathlib import Path
from typing import Any

from .constants import (
    CORE_HEADER_FLAGS,
    DEFAULT_ALIGNMENT,
    ENDIAN_MARKER,
    FORMAT_MAJOR,
    FORMAT_MINOR,
    GLOBAL_REQUIRED_FLAGS,
    GRID_ALIGNMENT,
    HEADER_SIZE,
    MAGIC,
    NULL_ID,
    REGION_RECORD_SIZE,
    REGION_SIZE_TILES,
    REGIONAL_GRID_FLAGS,
    SECTION_ENTRY_SIZE,
    Codec,
    SectionFlags,
    SectionType,
)
from .model import RuntimeBinaryResult, RuntimeBinarySource, SectionDescriptor
from .strings import StringTable, build_string_table
from .validator import validate_runtime_binary

LOGGER = logging.getLogger(__name__)
_GLOBAL_SECTION_COUNT = 6
_REGIONAL_SECTION_COUNT = 11


def write_runtime_binary(
    source: RuntimeBinarySource,
    path: Path,
) -> RuntimeBinaryResult:
    """Serialize, independently validate, and atomically publish a container.

    Args:
        source: In-memory runtime source model.
        path: Final output file path.

    Returns:
        Runtime binary generation result.

    Raises:
        ValueError: If source data is inconsistent or cannot be encoded.
        OSError: If the file cannot be written atomically.
    """
    _validate_source(source)
    started = time.perf_counter()
    sections, string_table, terrain_count, region_count_x, region_count_y = (
        _build_sections(source)
    )
    for index, section in enumerate(sections, start=1):
        section.section_id = index
        section.crc32 = zlib.crc32(section.payload) & 0xFFFFFFFF
    table_offset = HEADER_SIZE
    table_size = len(sections) * SECTION_ENTRY_SIZE
    cursor = _align_up(table_offset + table_size, GRID_ALIGNMENT)
    for section in sections:
        cursor = _align_up(cursor, section.alignment)
        section.offset = cursor
        cursor += section.stored_size
    file_size = cursor
    table_bytes = _pack_section_table(sections)
    table_crc32 = zlib.crc32(table_bytes) & 0xFFFFFFFF
    build_id = _build_id(source, sections)
    elevation_values = [value for row in source.elevation_rows for value in row]
    header = _pack_header(
        source=source,
        section_count=len(sections),
        section_table_size=table_size,
        file_size=file_size,
        build_id=build_id,
        section_table_crc32=table_crc32,
        min_elevation=min(elevation_values, default=0),
        max_elevation=max(elevation_values, default=0),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(header)
            stream.write(table_bytes)
            _write_padding(stream, _align_up(stream.tell(), GRID_ALIGNMENT))
            for section in sections:
                _write_padding(stream, section.offset)
                stream.write(section.payload)
            if stream.tell() != file_size:
                raise ValueError("runtime binary layout size mismatch")
            stream.flush()
            os.fsync(stream.fileno())
        write_time_ms = (time.perf_counter() - started) * 1000.0
        validate_started = time.perf_counter()
        validate_runtime_binary(temporary, source)
        validate_time_ms = (time.perf_counter() - validate_started) * 1000.0
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    result = RuntimeBinaryResult(
        path=path,
        build_id=build_id,
        file_size=file_size,
        section_count=len(sections),
        region_count_x=region_count_x,
        region_count_y=region_count_y,
        terrain_count=terrain_count,
        string_count=len(string_table.values),
        write_time_ms=write_time_ms,
        validate_time_ms=validate_time_ms,
    )
    LOGGER.info(
        "Runtime binary path=%s format=vxmap-runtime-v1.2 regions=%sx%s "
        "sections=%s strings=%s terrain_types=%s file_size=%s "
        "write_ms=%.3f validate_ms=%.3f build_id=%s",
        path,
        region_count_x,
        region_count_y,
        result.section_count,
        result.string_count,
        result.terrain_count,
        result.file_size,
        result.write_time_ms,
        result.validate_time_ms,
        result.build_id.hex(),
    )
    return result


def _build_sections(
    source: RuntimeBinarySource,
) -> tuple[list[SectionDescriptor], StringTable, int, int, int]:
    catalog_types = _catalog_types(source)
    terrain_names = sorted(catalog_types, key=lambda value: value.encode("utf-8"))
    strings = {
        source.map_schema,
        source.package_schema,
        source.generator_version,
        source.pipeline_version,
        source.profile,
        str(source.resolved_seed),
        "tile",
        "TopDownMapGen",
        *terrain_names,
    }
    for item in catalog_types.values():
        strings.update(_string_tags(item.get("tags")))
    string_table = build_string_table(strings)
    string_pool, terrain_catalog = _build_terrain_catalog(
        terrain_names,
        catalog_types,
        string_table,
    )
    terrain_ids = {name: index for index, name in enumerate(terrain_names)}
    region_count_x = math.ceil(source.width / REGION_SIZE_TILES)
    region_count_y = math.ceil(source.height / REGION_SIZE_TILES)
    region_count = region_count_x * region_count_y
    sections: list[SectionDescriptor] = [
        _section(
            SectionType.METADATA,
            GLOBAL_REQUIRED_FLAGS,
            _build_metadata(source, string_table),
            1,
            64,
        ),
        _section(
            SectionType.STRING_TABLE,
            GLOBAL_REQUIRED_FLAGS | int(SectionFlags.CONTAINS_OFFSETS),
            string_table.payload,
            len(string_table.values),
            0,
        ),
        _section(
            SectionType.STRING_ID_POOL,
            GLOBAL_REQUIRED_FLAGS,
            string_pool,
            len(string_pool) // 4,
            4,
        ),
        _section(
            SectionType.REGION_INDEX,
            GLOBAL_REQUIRED_FLAGS,
            _build_region_index(source, region_count_x, region_count_y),
            region_count,
            0,
        ),
        _section(
            SectionType.TERRAIN_CATALOG,
            GLOBAL_REQUIRED_FLAGS,
            terrain_catalog,
            len(terrain_names),
            0,
        ),
        _section(
            SectionType.START_GOAL,
            GLOBAL_REQUIRED_FLAGS,
            _build_start_goal(source.start, source.goal),
            1,
            32,
        ),
    ]
    for region_y in range(region_count_y):
        for region_x in range(region_count_x):
            region_id = region_y * region_count_x + region_x
            sections.extend(
                _build_region_sections(
                    source=source,
                    terrain_ids=terrain_ids,
                    region_id=region_id,
                    region_x=region_x,
                    region_y=region_y,
                ),
            )
    return sections, string_table, len(terrain_names), region_count_x, region_count_y


def _build_region_sections(
    *,
    source: RuntimeBinarySource,
    terrain_ids: dict[str, int],
    region_id: int,
    region_x: int,
    region_y: int,
) -> list[SectionDescriptor]:
    origin_x = region_x * REGION_SIZE_TILES
    origin_y = region_y * REGION_SIZE_TILES
    region_width = min(REGION_SIZE_TILES, source.width - origin_x)
    region_height = min(REGION_SIZE_TILES, source.height - origin_y)
    tile_count = region_width * region_height
    terrain_values: list[int] = []
    elevation_values: list[int] = []
    movement_values: list[int] = []
    collision_values: list[bool] = []
    projectile_values: list[bool] = []
    vision_values: list[bool] = []
    cover_values = bytearray()
    concealment_values = bytearray()
    structure_height_values = bytearray()
    vegetation_type_values = bytearray()
    vegetation_height_values = bytearray()
    for y in range(origin_y, origin_y + region_height):
        for x in range(origin_x, origin_x + region_width):
            terrain_name = source.terrain_rows[y][x]
            try:
                terrain_values.append(terrain_ids[terrain_name])
            except KeyError as error:
                raise ValueError(
                    f"terrain type is missing from catalog: {terrain_name}",
                ) from error
            elevation_values.append(source.elevation_rows[y][x])
            movement_values.append(_encode_movement(source.movement_rows[y][x]))
            collision_values.append(source.collision_rows[y][x] == "1")
            projectile_values.append(source.projectile_rows[y][x] == "1")
            vision_values.append(source.vision_rows[y][x] == "1")
            cover_values.append(_quantize_unit(source.cover_rows[y][x]))
            concealment_values.append(_quantize_unit(source.concealment_rows[y][x]))
            structure_height_values.append(source.structure_height_rows[y][x])
            vegetation_type_values.append(source.vegetation_type_rows[y][x])
            vegetation_height_values.append(source.vegetation_height_rows[y][x])
    common = {
        "parent_id": region_id,
        "alignment": GRID_ALIGNMENT,
        "aux_0": region_x,
        "aux_1": region_y,
    }
    return [
        _section(
            SectionType.TERRAIN_GRID,
            REGIONAL_GRID_FLAGS,
            struct.pack(f"<{tile_count}H", *terrain_values),
            tile_count,
            2,
            **common,
        ),
        _section(
            SectionType.ELEVATION_GRID,
            REGIONAL_GRID_FLAGS,
            struct.pack(f"<{tile_count}h", *elevation_values),
            tile_count,
            2,
            **common,
        ),
        _section(
            SectionType.MOVEMENT_GRID,
            REGIONAL_GRID_FLAGS,
            struct.pack(f"<{tile_count}H", *movement_values),
            tile_count,
            2,
            **common,
        ),
        _section(
            SectionType.COLLISION_BITS,
            REGIONAL_GRID_FLAGS,
            _pack_bits(collision_values),
            tile_count,
            0,
            **common,
        ),
        _section(
            SectionType.PROJECTILE_BLOCK_BITS,
            REGIONAL_GRID_FLAGS,
            _pack_bits(projectile_values),
            tile_count,
            0,
            **common,
        ),
        _section(
            SectionType.VISION_BLOCK_BITS,
            REGIONAL_GRID_FLAGS,
            _pack_bits(vision_values),
            tile_count,
            0,
            **common,
        ),
        _section(
            SectionType.COVER_GRID_U8,
            REGIONAL_GRID_FLAGS,
            bytes(cover_values),
            tile_count,
            1,
            **common,
        ),
        _section(
            SectionType.CONCEALMENT_GRID_U8,
            REGIONAL_GRID_FLAGS,
            bytes(concealment_values),
            tile_count,
            1,
            **common,
        ),
        _section(
            SectionType.STRUCTURE_HEIGHT_U8,
            REGIONAL_GRID_FLAGS,
            bytes(structure_height_values),
            tile_count,
            1,
            **common,
        ),
        _section(
            SectionType.VEGETATION_TYPE_U8,
            REGIONAL_GRID_FLAGS,
            bytes(vegetation_type_values),
            tile_count,
            1,
            **common,
        ),
        _section(
            SectionType.VEGETATION_HEIGHT_U8,
            REGIONAL_GRID_FLAGS,
            bytes(vegetation_height_values),
            tile_count,
            1,
            **common,
        ),
    ]


def _section(
    section_type: SectionType,
    flags: int,
    payload: bytes,
    element_count: int,
    element_stride: int,
    *,
    parent_id: int = NULL_ID,
    alignment: int = DEFAULT_ALIGNMENT,
    aux_0: int = 0,
    aux_1: int = 0,
) -> SectionDescriptor:
    return SectionDescriptor(
        section_type=int(section_type),
        section_flags=flags,
        section_id=0,
        parent_id=parent_id,
        payload=payload,
        element_count=element_count,
        element_stride=element_stride,
        alignment=alignment,
        aux_0=aux_0,
        aux_1=aux_1,
    )


def _build_metadata(source: RuntimeBinarySource, strings: StringTable) -> bytes:
    payload = bytearray(64)
    values = (
        source.map_schema,
        source.package_schema,
        source.generator_version,
        source.pipeline_version,
        source.profile,
        str(source.resolved_seed),
        "tile",
        "TopDownMapGen",
    )
    for index, value in enumerate(values):
        struct.pack_into("<I", payload, index * 4, strings.ids[value])
    struct.pack_into("<Q", payload, 32, source.width * source.height)
    return bytes(payload)


def _build_terrain_catalog(
    terrain_names: list[str],
    catalog_types: dict[str, dict[str, Any]],
    strings: StringTable,
) -> tuple[bytes, bytes]:
    pool_ids: list[int] = []
    records = bytearray()
    for name in terrain_names:
        item = catalog_types[name]
        tags = _string_tags(item.get("tags"))
        first_tag_index = len(pool_ids)
        pool_ids.extend(strings.ids[tag] for tag in tags)
        symbol = item.get("symbol")
        symbol_unicode = (
            ord(symbol)
            if isinstance(symbol, str) and len(symbol) == 1
            else 0
        )
        movement = _encode_movement(item.get("movement_cost"))
        flags = _terrain_flags(name, item, tags)
        records.extend(
            struct.pack(
                "<IIHHIHHIII",
                strings.ids[name],
                symbol_unicode,
                movement,
                flags,
                first_tag_index,
                len(tags),
                0,
                NULL_ID,
                NULL_ID,
                0,
            ),
        )
    pool_payload = (
        struct.pack(f"<{len(pool_ids)}I", *pool_ids) if pool_ids else b""
    )
    catalog_payload = struct.pack("<IHH", len(terrain_names), 32, 0) + bytes(records)
    return pool_payload, catalog_payload


def _terrain_flags(
    name: str,
    item: dict[str, Any],
    tags: list[str],
) -> int:
    flags = 0
    if item.get("walkable") is True:
        flags |= 1 << 0
    if item.get("collision") == "blocked":
        flags |= (1 << 1) | (1 << 2) | (1 << 3)
    if "water" in tags or "water" in name:
        flags |= 1 << 4
    if "decor" in tags:
        flags |= 1 << 5
    if "cover" in tags or "vegetation" in tags:
        flags |= 1 << 6
    if "vegetation" in tags or "slow" in tags:
        flags |= 1 << 7
    return flags


def _build_region_index(
    source: RuntimeBinarySource,
    region_count_x: int,
    region_count_y: int,
) -> bytes:
    region_count = region_count_x * region_count_y
    payload = bytearray(
        struct.pack(
            "<IHH",
            region_count,
            REGION_SIZE_TILES,
            REGION_RECORD_SIZE,
        ),
    )
    for region_y in range(region_count_y):
        for region_x in range(region_count_x):
            region_id = region_y * region_count_x + region_x
            origin_x = region_x * REGION_SIZE_TILES
            origin_y = region_y * REGION_SIZE_TILES
            width = min(REGION_SIZE_TILES, source.width - origin_x)
            height = min(REGION_SIZE_TILES, source.height - origin_y)
            first_section_index = (
                _GLOBAL_SECTION_COUNT
                + region_id * _REGIONAL_SECTION_COUNT
            )
            payload.extend(
                struct.pack(
                    "<IHHIIHHIHHI",
                    region_id,
                    region_x,
                    region_y,
                    origin_x,
                    origin_y,
                    width,
                    height,
                    first_section_index,
                    _REGIONAL_SECTION_COUNT,
                    0,
                    width * height,
                ),
            )
    return bytes(payload)


def _build_start_goal(
    start: dict[str, int] | None,
    goal: dict[str, int] | None,
) -> bytes:
    start_x, start_y = _point_coordinates(start)
    goal_x, goal_y = _point_coordinates(goal)
    flags = (1 if start is not None else 0) | (2 if goal is not None else 0)
    return struct.pack("<iiiiIIQ", start_x, start_y, goal_x, goal_y, flags, 0, 0)


def _pack_header(
    *,
    source: RuntimeBinarySource,
    section_count: int,
    section_table_size: int,
    file_size: int,
    build_id: bytes,
    section_table_crc32: int,
    min_elevation: int,
    max_elevation: int,
) -> bytes:
    header = bytearray(HEADER_SIZE)
    header[:8] = MAGIC
    struct.pack_into(
        "<HHHH",
        header,
        8,
        HEADER_SIZE,
        FORMAT_MAJOR,
        FORMAT_MINOR,
        SECTION_ENTRY_SIZE,
    )
    struct.pack_into("<I", header, 16, ENDIAN_MARKER)
    struct.pack_into("<I", header, 20, CORE_HEADER_FLAGS)
    struct.pack_into("<III", header, 24, section_count, source.width, source.height)
    struct.pack_into(
        "<HHhhHH",
        header,
        36,
        source.tile_size_px,
        0,
        min_elevation,
        max_elevation,
        REGION_SIZE_TILES,
        0,
    )
    struct.pack_into("<Q", header, 48, source.resolved_seed)
    struct.pack_into("<QQQ", header, 56, HEADER_SIZE, section_table_size, file_size)
    struct.pack_into("<Q", header, 80, 0)
    header[88:104] = build_id
    struct.pack_into("<I", header, 108, section_table_crc32)
    header_crc32 = zlib.crc32(header) & 0xFFFFFFFF
    struct.pack_into("<I", header, 104, header_crc32)
    return bytes(header)


def _pack_section_table(sections: list[SectionDescriptor]) -> bytes:
    table = bytearray()
    for section in sections:
        table.extend(
            struct.pack(
                "<IIIIQQQIIHHIII",
                section.section_type,
                section.section_flags,
                section.section_id,
                section.parent_id,
                section.offset,
                section.stored_size,
                section.stored_size,
                section.element_count,
                section.element_stride,
                int(Codec.NONE),
                section.alignment,
                section.crc32,
                section.aux_0,
                section.aux_1,
            ),
        )
    return bytes(table)


def _build_id(
    source: RuntimeBinarySource,
    sections: list[SectionDescriptor],
) -> bytes:
    digest = hashlib.sha256()
    digest.update(
        struct.pack(
            "<HHIIQ",
            FORMAT_MAJOR,
            FORMAT_MINOR,
            source.width,
            source.height,
            source.resolved_seed,
        ),
    )
    for section in sections:
        digest.update(
            struct.pack(
                "<IIIIQII",
                section.section_type,
                section.section_flags,
                section.section_id,
                section.parent_id,
                section.stored_size,
                section.element_count,
                section.crc32,
            ),
        )
    return digest.digest()[:16]


def _validate_source(source: RuntimeBinarySource) -> None:
    if source.width <= 0 or source.height <= 0:
        raise ValueError("runtime binary dimensions must be positive")
    if source.width > 0xFFFFFFFF or source.height > 0xFFFFFFFF:
        raise ValueError("runtime binary dimensions exceed u32")
    if not 0 <= source.tile_size_px <= 0xFFFF:
        raise ValueError("runtime tile size exceeds u16")
    if not 0 <= source.resolved_seed <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("runtime seed exceeds u64")
    _validate_matrix(source.terrain_rows, source.width, source.height, "terrain")
    _validate_matrix(source.movement_rows, source.width, source.height, "movement")
    _validate_bit_rows(source.collision_rows, source.width, source.height, "collision")
    _validate_bit_rows(
        source.projectile_rows,
        source.width,
        source.height,
        "projectile",
    )
    _validate_bit_rows(source.vision_rows, source.width, source.height, "vision")
    _validate_matrix(source.cover_rows, source.width, source.height, "cover")
    _validate_matrix(
        source.concealment_rows,
        source.width,
        source.height,
        "concealment",
    )
    _validate_matrix(source.elevation_rows, source.width, source.height, "elevation")
    _validate_matrix(
        source.structure_height_rows,
        source.width,
        source.height,
        "structure height",
    )
    _validate_matrix(
        source.vegetation_type_rows,
        source.width,
        source.height,
        "vegetation type",
    )
    _validate_matrix(
        source.vegetation_height_rows,
        source.width,
        source.height,
        "vegetation height",
    )
    for row in source.elevation_rows:
        if any(value < -32768 or value > 32767 for value in row):
            raise ValueError("runtime elevation exceeds i16")
    for y, row in enumerate(source.structure_height_rows):
        for x, value in enumerate(row):
            if value < 0 or value > 3:
                raise ValueError("runtime structure height exceeds u8 v1 contract")
            terrain = source.terrain_rows[y][x]
            if terrain == "ruin_wall_blocker":
                if value == 0:
                    raise ValueError("runtime ruin wall has zero structure height")
                if source.collision_rows[y][x] != "1":
                    raise ValueError("runtime ruin wall is not collision-blocked")
            elif value != 0:
                raise ValueError("runtime non-ruin tile has structure height")
    for y, row in enumerate(source.vegetation_type_rows):
        for x, vegetation_type in enumerate(row):
            vegetation_height = source.vegetation_height_rows[y][x]
            if vegetation_type < 0 or vegetation_type > 4:
                raise ValueError("runtime vegetation type exceeds u8 v1 contract")
            if vegetation_height < 0 or vegetation_height > 5:
                raise ValueError("runtime vegetation height exceeds u8 v1 contract")
            if vegetation_type == 0 and vegetation_height != 0:
                raise ValueError("runtime none vegetation has non-zero height")
            if vegetation_type == 1 and not 2 <= vegetation_height <= 5:
                raise ValueError("runtime tree height is outside the v1 range")
            if vegetation_type == 2 and not 1 <= vegetation_height <= 2:
                raise ValueError("runtime bush height is outside the v1 range")
            if vegetation_type in {3, 4} and vegetation_height != 1:
                raise ValueError("runtime reed height must equal one")
    _validate_point(source.start, source.width, source.height, "start")
    _validate_point(source.goal, source.width, source.height, "goal")


def _validate_matrix(rows: list[list[Any]], width: int, height: int, name: str) -> None:
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError(f"runtime {name} grid dimensions do not match the map")


def _validate_bit_rows(rows: list[str], width: int, height: int, name: str) -> None:
    if len(rows) != height:
        raise ValueError(f"runtime {name} grid height does not match the map")
    if any(len(row) != width or set(row) - {"0", "1"} for row in rows):
        raise ValueError(f"runtime {name} grid contains invalid rows")


def _validate_point(
    point: dict[str, int] | None,
    width: int,
    height: int,
    name: str,
) -> None:
    if point is None:
        return
    x = point.get("x")
    y = point.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        raise ValueError(f"runtime {name} point is invalid")
    if not 0 <= x < width or not 0 <= y < height:
        raise ValueError(f"runtime {name} point is outside the map")


def _catalog_types(source: RuntimeBinarySource) -> dict[str, dict[str, Any]]:
    raw = source.terrain_catalog.get("types")
    result: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        result.update(
            {
                name: dict(item)
                for name, item in raw.items()
                if isinstance(name, str) and isinstance(item, dict)
            },
        )
    discovered = sorted(
        {name for row in source.terrain_rows for name in row},
        key=lambda value: value.encode("utf-8"),
    )
    for name in discovered:
        if name in result:
            continue
        movement_values: list[int | float] = []
        blocked = False
        for y, row in enumerate(source.terrain_rows):
            for x, terrain_name in enumerate(row):
                if terrain_name != name:
                    continue
                movement = source.movement_rows[y][x]
                if isinstance(movement, int | float) and not isinstance(movement, bool):
                    movement_values.append(movement)
                blocked = blocked or source.collision_rows[y][x] == "1"
        movement_cost = movement_values[0] if movement_values else None
        result[name] = {
            "symbol": None,
            "movement_cost": movement_cost,
            "collision": "blocked" if blocked else "passable",
            "walkable": not blocked,
            "tags": ["terrain"],
        }
    if not result:
        raise ValueError("runtime terrain catalog is empty")
    if len(result) > 0xFFFF:
        raise ValueError("runtime terrain catalog exceeds u16 IDs")
    return result


def _string_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str)})


def _encode_movement(value: Any) -> int:
    if value is None:
        return 0xFFFF
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"invalid movement cost: {value!r}")
    if not math.isfinite(float(value)) or float(value) != int(value):
        raise ValueError(f"movement cost is not an integer: {value!r}")
    encoded = int(value)
    if not 0 <= encoded <= 0xFFFE:
        raise ValueError(f"movement cost exceeds u16 encoding: {value!r}")
    return encoded


def _quantize_unit(value: Any) -> int:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"invalid normalized grid value: {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("normalized grid value is not finite")
    return round(min(1.0, max(0.0, number)) * 255.0)


def _pack_bits(values: list[bool]) -> bytes:
    payload = bytearray((len(values) + 7) // 8)
    for index, value in enumerate(values):
        if value:
            payload[index >> 3] |= 1 << (index & 7)
    return bytes(payload)


def _point_coordinates(point: dict[str, int] | None) -> tuple[int, int]:
    if point is None:
        return (-1, -1)
    return (point["x"], point["y"])


def _align_up(value: int, alignment: int) -> int:
    if alignment <= 0 or alignment & (alignment - 1):
        raise ValueError("alignment must be a positive power of two")
    return (value + alignment - 1) & ~(alignment - 1)


def _write_padding(stream: Any, target_offset: int) -> None:
    current = stream.tell()
    if current > target_offset:
        raise ValueError("runtime binary section offsets overlap")
    stream.write(b"\x00" * (target_offset - current))
