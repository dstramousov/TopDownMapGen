"""Semantic validation for the VoX3D runtime binary container."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

from .constants import NULL_ID, REGION_RECORD_SIZE, REGION_SIZE_TILES, SectionType
from .model import RuntimeBinarySource
from .reader import RuntimeContainer, RuntimeSection, open_runtime_container


@dataclass(frozen=True, slots=True)
class RegionRecord:
    """Decoded region index record."""

    region_id: int
    region_x: int
    region_y: int
    origin_x: int
    origin_y: int
    width: int
    height: int
    first_section_table_index: int
    section_count: int
    flags: int
    tile_count: int


def validate_runtime_binary(path: Path, source: RuntimeBinarySource) -> None:
    """Validate structure and compare binary core grids with source data.

    Args:
        path: Runtime binary path.
        source: In-memory source model used to build the file.

    Raises:
        ValueError: If any structural or semantic mismatch is found.
    """
    container = open_runtime_container(path)
    header = container.header
    if header.width != source.width or header.height != source.height:
        raise ValueError("runtime binary dimensions differ from source")
    if header.tile_size_px != source.tile_size_px:
        raise ValueError("runtime binary tile size differs from source")
    if header.resolved_seed != source.resolved_seed:
        raise ValueError("runtime binary seed differs from source")
    strings = _decode_string_table(
        container.payload(_singleton(container, SectionType.STRING_TABLE)),
    )
    _validate_metadata(container, strings, source)
    terrain_names = _decode_terrain_names(container, strings)
    regions = _decode_region_index(container, source)
    _validate_start_goal(container, source)
    regional_sections = _regional_section_map(container)
    expected_types = {
        int(SectionType.TERRAIN_GRID),
        int(SectionType.ELEVATION_GRID),
        int(SectionType.MOVEMENT_GRID),
        int(SectionType.COLLISION_BITS),
        int(SectionType.PROJECTILE_BLOCK_BITS),
        int(SectionType.VISION_BLOCK_BITS),
        int(SectionType.COVER_GRID_U8),
        int(SectionType.CONCEALMENT_GRID_U8),
        int(SectionType.STRUCTURE_HEIGHT_U8),
        int(SectionType.STRUCTURE_TYPE_U8),
        int(SectionType.STRUCTURE_MICRO_MASK_U16),
        int(SectionType.STRUCTURE_WALKWAY_MASK_U16),
        int(SectionType.STRUCTURE_PARAPET_MASK_U16),
        int(SectionType.STRUCTURE_CRENELLATION_MASK_U16),
        int(SectionType.VEGETATION_TYPE_U8),
        int(SectionType.VEGETATION_HEIGHT_U8),
    }
    for region in regions:
        by_type = regional_sections.get(region.region_id, {})
        if set(by_type) != expected_types:
            raise ValueError(
                f"region {region.region_id} does not contain all core grids",
            )
        _validate_region_values(
            container=container,
            region=region,
            sections=by_type,
            source=source,
            terrain_names=terrain_names,
        )


def _singleton(
    container: RuntimeContainer,
    section_type: SectionType,
) -> RuntimeSection:
    matches = container.sections_of_type(int(section_type))
    if len(matches) != 1:
        raise ValueError(
            f"runtime binary requires one {section_type.name} section",
        )
    return matches[0]


def _decode_string_table(payload: bytes) -> tuple[str, ...]:
    if len(payload) < 8:
        raise ValueError("runtime string table is truncated")
    string_count, bytes_size = struct.unpack_from("<II", payload, 0)
    offsets_size = (string_count + 1) * 4
    data_offset = 8 + offsets_size
    if data_offset + bytes_size != len(payload):
        raise ValueError("runtime string table size mismatch")
    offsets = struct.unpack_from(f"<{string_count + 1}I", payload, 8)
    if offsets[0] != 0 or offsets[-1] != bytes_size:
        raise ValueError("runtime string table terminal offsets are invalid")
    if any(left > right for left, right in zip(offsets, offsets[1:], strict=False)):
        raise ValueError("runtime string table offsets are not monotonic")
    raw = payload[data_offset:]
    values: list[str] = []
    for start, end in zip(offsets, offsets[1:], strict=False):
        value = raw[start:end]
        if b"\x00" in value:
            raise ValueError("runtime string table contains embedded NUL")
        try:
            values.append(value.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise ValueError("runtime string table contains invalid UTF-8") from error
    return tuple(values)


def _validate_metadata(
    container: RuntimeContainer,
    strings: tuple[str, ...],
    source: RuntimeBinarySource,
) -> None:
    payload = container.payload(_singleton(container, SectionType.METADATA))
    if len(payload) != 64:
        raise ValueError("runtime metadata has invalid size")
    ids = struct.unpack_from("<8I", payload, 0)
    values = tuple(_string_by_id(strings, string_id) for string_id in ids)
    expected = (
        source.map_schema,
        source.package_schema,
        source.generator_version,
        source.pipeline_version,
        source.profile,
        str(source.resolved_seed),
        "tile",
        "TopDownMapGen",
    )
    if values != expected:
        raise ValueError("runtime metadata differs from source")
    tile_count = struct.unpack_from("<Q", payload, 32)[0]
    if tile_count != source.width * source.height:
        raise ValueError("runtime metadata tile count differs from source")


def _decode_terrain_names(
    container: RuntimeContainer,
    strings: tuple[str, ...],
) -> tuple[str, ...]:
    payload = container.payload(_singleton(container, SectionType.TERRAIN_CATALOG))
    if len(payload) < 8:
        raise ValueError("runtime terrain catalog is truncated")
    terrain_count, record_size, reserved = struct.unpack_from("<IHH", payload, 0)
    if record_size != 32 or reserved != 0:
        raise ValueError("runtime terrain catalog header is invalid")
    if len(payload) != 8 + terrain_count * record_size:
        raise ValueError("runtime terrain catalog size mismatch")
    names: list[str] = []
    for index in range(terrain_count):
        offset = 8 + index * record_size
        name_id = struct.unpack_from("<I", payload, offset)[0]
        names.append(_string_by_id(strings, name_id))
    if len(set(names)) != len(names):
        raise ValueError("runtime terrain catalog contains duplicate names")
    return tuple(names)


def _decode_region_index(
    container: RuntimeContainer,
    source: RuntimeBinarySource,
) -> tuple[RegionRecord, ...]:
    payload = container.payload(_singleton(container, SectionType.REGION_INDEX))
    if len(payload) < 8:
        raise ValueError("runtime region index is truncated")
    region_count, region_size, record_size = struct.unpack_from("<IHH", payload, 0)
    if region_size != REGION_SIZE_TILES or record_size != REGION_RECORD_SIZE:
        raise ValueError("runtime region index header is invalid")
    if len(payload) != 8 + region_count * record_size:
        raise ValueError("runtime region index size mismatch")
    expected_x = math.ceil(source.width / REGION_SIZE_TILES)
    expected_y = math.ceil(source.height / REGION_SIZE_TILES)
    if region_count != expected_x * expected_y:
        raise ValueError("runtime region count differs from source dimensions")
    records: list[RegionRecord] = []
    covered = bytearray(source.width * source.height)
    for index in range(region_count):
        values = struct.unpack_from("<IHHIIHHIHHI", payload, 8 + index * record_size)
        record = RegionRecord(*values)
        if record.region_id != index:
            raise ValueError("runtime region IDs are not deterministic row-major IDs")
        if (
            record.region_x != index % expected_x
            or record.region_y != index // expected_x
        ):
            raise ValueError("runtime region coordinates differ from row-major order")
        if record.origin_x + record.width > source.width:
            raise ValueError("runtime region exceeds map width")
        if record.origin_y + record.height > source.height:
            raise ValueError("runtime region exceeds map height")
        if record.tile_count != record.width * record.height:
            raise ValueError("runtime region tile count is invalid")
        if record.section_count != 11:
            raise ValueError("runtime region does not reference eleven core sections")
        if (
            record.first_section_table_index + record.section_count
            > len(container.sections)
        ):
            raise ValueError("runtime region section range is outside the table")
        for y in range(record.origin_y, record.origin_y + record.height):
            base = y * source.width
            for x in range(record.origin_x, record.origin_x + record.width):
                offset = base + x
                if covered[offset]:
                    raise ValueError("runtime regions overlap")
                covered[offset] = 1
        records.append(record)
    if not all(covered):
        raise ValueError("runtime regions do not cover the full map")
    return tuple(records)


def _validate_start_goal(
    container: RuntimeContainer,
    source: RuntimeBinarySource,
) -> None:
    payload = container.payload(_singleton(container, SectionType.START_GOAL))
    if len(payload) != 32:
        raise ValueError("runtime start/goal section has invalid size")
    start_x, start_y, goal_x, goal_y, flags, reserved, reserved64 = struct.unpack(
        "<iiiiIIQ",
        payload,
    )
    if reserved != 0 or reserved64 != 0:
        raise ValueError("runtime start/goal reserved fields are not zero")
    expected_start = _expected_point(source.start)
    expected_goal = _expected_point(source.goal)
    if (
        (start_x, start_y) != expected_start
        or bool(flags & 1) != (source.start is not None)
    ):
        raise ValueError("runtime start point differs from source")
    if (
        (goal_x, goal_y) != expected_goal
        or bool(flags & 2) != (source.goal is not None)
    ):
        raise ValueError("runtime goal point differs from source")


def _regional_section_map(
    container: RuntimeContainer,
) -> dict[int, dict[int, RuntimeSection]]:
    result: dict[int, dict[int, RuntimeSection]] = {}
    for section in container.sections:
        if section.parent_id == NULL_ID:
            continue
        by_type = result.setdefault(section.parent_id, {})
        if section.section_type in by_type:
            raise ValueError(
                f"duplicate regional section type {section.section_type}",
            )
        by_type[section.section_type] = section
    return result


def _validate_region_values(
    *,
    container: RuntimeContainer,
    region: RegionRecord,
    sections: dict[int, RuntimeSection],
    source: RuntimeBinarySource,
    terrain_names: tuple[str, ...],
) -> None:
    tile_count = region.tile_count
    terrain_payload = container.payload(sections[int(SectionType.TERRAIN_GRID)])
    elevation_payload = container.payload(sections[int(SectionType.ELEVATION_GRID)])
    movement_payload = container.payload(sections[int(SectionType.MOVEMENT_GRID)])
    collision_payload = container.payload(sections[int(SectionType.COLLISION_BITS)])
    projectile_payload = container.payload(
        sections[int(SectionType.PROJECTILE_BLOCK_BITS)],
    )
    vision_payload = container.payload(sections[int(SectionType.VISION_BLOCK_BITS)])
    cover_payload = container.payload(sections[int(SectionType.COVER_GRID_U8)])
    concealment_payload = container.payload(
        sections[int(SectionType.CONCEALMENT_GRID_U8)],
    )
    structure_height_payload = container.payload(
        sections[int(SectionType.STRUCTURE_HEIGHT_U8)],
    )
    structure_type_payload = container.payload(
        sections[int(SectionType.STRUCTURE_TYPE_U8)],
    )
    structure_micro_mask_payload = container.payload(
        sections[int(SectionType.STRUCTURE_MICRO_MASK_U16)],
    )
    structure_walkway_mask_payload = container.payload(
        sections[int(SectionType.STRUCTURE_WALKWAY_MASK_U16)],
    )
    structure_parapet_mask_payload = container.payload(
        sections[int(SectionType.STRUCTURE_PARAPET_MASK_U16)],
    )
    structure_crenellation_mask_payload = container.payload(
        sections[int(SectionType.STRUCTURE_CRENELLATION_MASK_U16)],
    )
    vegetation_type_payload = container.payload(
        sections[int(SectionType.VEGETATION_TYPE_U8)],
    )
    vegetation_height_payload = container.payload(
        sections[int(SectionType.VEGETATION_HEIGHT_U8)],
    )
    terrain_values = struct.unpack(f"<{tile_count}H", terrain_payload)
    elevation_values = struct.unpack(f"<{tile_count}h", elevation_payload)
    movement_values = struct.unpack(f"<{tile_count}H", movement_payload)
    if len(collision_payload) != (tile_count + 7) // 8:
        raise ValueError("runtime collision bitset size mismatch")
    if len(projectile_payload) != (tile_count + 7) // 8:
        raise ValueError("runtime projectile bitset size mismatch")
    if len(vision_payload) != (tile_count + 7) // 8:
        raise ValueError("runtime vision bitset size mismatch")
    if len(cover_payload) != tile_count or len(concealment_payload) != tile_count:
        raise ValueError("runtime normalized grid size mismatch")
    if len(structure_height_payload) != tile_count:
        raise ValueError("runtime structure-height grid size mismatch")
    if len(structure_type_payload) != tile_count:
        raise ValueError("runtime structure-type grid size mismatch")
    if len(structure_micro_mask_payload) != tile_count * 2:
        raise ValueError("runtime structure-micro-mask grid size mismatch")
    if len(structure_walkway_mask_payload) != tile_count * 2:
        raise ValueError("runtime structure-walkway-mask grid size mismatch")
    if len(structure_parapet_mask_payload) != tile_count * 2:
        raise ValueError("runtime structure-parapet-mask grid size mismatch")
    if len(structure_crenellation_mask_payload) != tile_count * 2:
        raise ValueError("runtime structure-crenellation-mask grid size mismatch")
    structure_micro_masks = struct.unpack(f"<{tile_count}H", structure_micro_mask_payload)
    structure_walkway_masks = struct.unpack(
        f"<{tile_count}H", structure_walkway_mask_payload
    )
    structure_parapet_masks = struct.unpack(
        f"<{tile_count}H", structure_parapet_mask_payload
    )
    structure_crenellation_masks = struct.unpack(
        f"<{tile_count}H", structure_crenellation_mask_payload
    )
    if len(vegetation_type_payload) != tile_count:
        raise ValueError("runtime vegetation-type grid size mismatch")
    if len(vegetation_height_payload) != tile_count:
        raise ValueError("runtime vegetation-height grid size mismatch")
    local_index = 0
    for y in range(region.origin_y, region.origin_y + region.height):
        for x in range(region.origin_x, region.origin_x + region.width):
            terrain_id = terrain_values[local_index]
            if terrain_id >= len(terrain_names):
                raise ValueError("runtime terrain grid contains invalid terrain ID")
            if terrain_names[terrain_id] != source.terrain_rows[y][x]:
                raise ValueError("runtime terrain grid differs from source")
            if elevation_values[local_index] != source.elevation_rows[y][x]:
                raise ValueError("runtime elevation grid differs from source")
            if movement_values[local_index] != _expected_movement(
                source.movement_rows[y][x],
            ):
                raise ValueError("runtime movement grid differs from source")
            if _bit(collision_payload, local_index) != (
                source.collision_rows[y][x] == "1"
            ):
                raise ValueError("runtime collision grid differs from source")
            if _bit(projectile_payload, local_index) != (
                source.projectile_rows[y][x] == "1"
            ):
                raise ValueError("runtime projectile grid differs from source")
            if _bit(vision_payload, local_index) != (source.vision_rows[y][x] == "1"):
                raise ValueError("runtime vision grid differs from source")
            if (
                abs(
                    cover_payload[local_index] / 255.0
                    - float(source.cover_rows[y][x])
                )
                > 0.002
            ):
                raise ValueError("runtime cover grid differs from source")
            if (
                abs(
                    concealment_payload[local_index] / 255.0
                    - float(source.concealment_rows[y][x])
                )
                > 0.002
            ):
                raise ValueError("runtime concealment grid differs from source")
            if (
                structure_height_payload[local_index]
                != source.structure_height_rows[y][x]
            ):
                raise ValueError("runtime structure-height grid differs from source")
            if structure_type_payload[local_index] != source.structure_type_rows[y][x]:
                raise ValueError("runtime structure-type grid differs from source")
            if structure_micro_masks[local_index] != source.structure_micro_mask_rows[y][x]:
                raise ValueError("runtime structure-micro-mask grid differs from source")
            if (
                structure_walkway_masks[local_index]
                != source.structure_walkway_mask_rows[y][x]
            ):
                raise ValueError("runtime structure-walkway-mask grid differs from source")
            if (
                structure_parapet_masks[local_index]
                != source.structure_parapet_mask_rows[y][x]
            ):
                raise ValueError("runtime structure-parapet-mask grid differs from source")
            if (
                structure_crenellation_masks[local_index]
                != source.structure_crenellation_mask_rows[y][x]
            ):
                raise ValueError(
                    "runtime structure-crenellation-mask grid differs from source"
                )
            if (
                vegetation_type_payload[local_index]
                != source.vegetation_type_rows[y][x]
            ):
                raise ValueError("runtime vegetation-type grid differs from source")
            if (
                vegetation_height_payload[local_index]
                != source.vegetation_height_rows[y][x]
            ):
                raise ValueError("runtime vegetation-height grid differs from source")
            local_index += 1
    _validate_unused_bits(collision_payload, tile_count)
    _validate_unused_bits(projectile_payload, tile_count)
    _validate_unused_bits(vision_payload, tile_count)


def _string_by_id(strings: tuple[str, ...], string_id: int) -> str:
    if string_id >= len(strings):
        raise ValueError(f"runtime string ID is outside the table: {string_id}")
    return strings[string_id]


def _expected_point(point: dict[str, int] | None) -> tuple[int, int]:
    if point is None:
        return (-1, -1)
    return (point["x"], point["y"])


def _expected_movement(value: int | float | None) -> int:
    if value is None:
        return 0xFFFF
    return int(value)


def _bit(payload: bytes, index: int) -> bool:
    return bool(payload[index >> 3] & (1 << (index & 7)))


def _validate_unused_bits(payload: bytes, element_count: int) -> None:
    remaining = element_count & 7
    if remaining == 0 or not payload:
        return
    valid_mask = (1 << remaining) - 1
    if payload[-1] & ~valid_mask:
        raise ValueError("runtime bitset has non-zero unused tail bits")
