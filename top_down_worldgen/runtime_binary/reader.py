"""Independent reader for the VoX3D runtime binary container."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from .constants import (
    ENDIAN_MARKER,
    FORMAT_MAJOR,
    FORMAT_MINOR,
    HEADER_SIZE,
    MAGIC,
    MAX_SECTION_COUNT,
    SECTION_ENTRY_SIZE,
    Codec,
    SectionFlags,
)


@dataclass(frozen=True, slots=True)
class RuntimeHeader:
    """Decoded fixed runtime container header."""

    format_major: int
    format_minor: int
    header_flags: int
    section_count: int
    width: int
    height: int
    tile_size_px: int
    min_elevation: int
    max_elevation: int
    region_size_tiles: int
    resolved_seed: int
    section_table_offset: int
    section_table_size: int
    file_size: int
    build_id: bytes
    section_table_crc32: int


@dataclass(frozen=True, slots=True)
class RuntimeSection:
    """Decoded section table entry."""

    section_type: int
    section_flags: int
    section_id: int
    parent_id: int
    offset: int
    stored_size: int
    unpacked_size: int
    element_count: int
    element_stride: int
    codec: int
    alignment: int
    crc32: int
    aux_0: int
    aux_1: int


@dataclass(frozen=True, slots=True)
class RuntimeContainer:
    """Validated runtime container index."""

    path: Path
    header: RuntimeHeader
    sections: tuple[RuntimeSection, ...]

    def payload(self, section: RuntimeSection) -> bytes:
        """Read and CRC-check one section payload.

        Args:
            section: Section table entry.

        Returns:
            Raw section bytes.

        Raises:
            ValueError: If the payload is truncated or has a bad CRC.
        """
        with self.path.open("rb") as stream:
            stream.seek(section.offset)
            payload = stream.read(section.stored_size)
        if len(payload) != section.stored_size:
            raise ValueError(f"truncated section {section.section_id}")
        if zlib.crc32(payload) & 0xFFFFFFFF != section.crc32:
            raise ValueError(f"bad CRC for section {section.section_id}")
        return payload

    def sections_of_type(self, section_type: int) -> tuple[RuntimeSection, ...]:
        """Return all sections matching a type.

        Args:
            section_type: Numeric section type.

        Returns:
            Matching sections in table order.
        """
        return tuple(
            section
            for section in self.sections
            if section.section_type == section_type
        )


def open_runtime_container(path: Path) -> RuntimeContainer:
    """Open and structurally validate a runtime container.

    Args:
        path: Binary container path.

    Returns:
        Validated container index.

    Raises:
        ValueError: If the file is malformed or unsupported.
    """
    file_size = path.stat().st_size
    if file_size < HEADER_SIZE:
        raise ValueError("runtime binary is smaller than the fixed header")
    with path.open("rb") as stream:
        header_bytes = stream.read(HEADER_SIZE)
    header = _decode_header(header_bytes, file_size)
    with path.open("rb") as stream:
        stream.seek(header.section_table_offset)
        table_bytes = stream.read(header.section_table_size)
    if len(table_bytes) != header.section_table_size:
        raise ValueError("truncated runtime section table")
    if zlib.crc32(table_bytes) & 0xFFFFFFFF != header.section_table_crc32:
        raise ValueError("runtime section table CRC mismatch")
    sections = _decode_sections(table_bytes, header)
    _validate_section_layout(sections, header)
    container = RuntimeContainer(path=path, header=header, sections=sections)
    for section in sections:
        if section.section_flags & int(SectionFlags.CRC_REQUIRED):
            container.payload(section)
    return container


def _decode_header(data: bytes, actual_file_size: int) -> RuntimeHeader:
    if data[:8] != MAGIC:
        raise ValueError("invalid runtime binary magic")
    header_size = struct.unpack_from("<H", data, 8)[0]
    format_major = struct.unpack_from("<H", data, 10)[0]
    format_minor = struct.unpack_from("<H", data, 12)[0]
    entry_size = struct.unpack_from("<H", data, 14)[0]
    endian_marker = struct.unpack_from("<I", data, 16)[0]
    if header_size != HEADER_SIZE:
        raise ValueError(f"unsupported header size: {header_size}")
    if format_major != FORMAT_MAJOR:
        raise ValueError(f"unsupported runtime format major: {format_major}")
    if format_minor > FORMAT_MINOR:
        raise ValueError(f"unsupported runtime format minor: {format_minor}")
    if entry_size != SECTION_ENTRY_SIZE:
        raise ValueError(f"unsupported section entry size: {entry_size}")
    if endian_marker != ENDIAN_MARKER:
        raise ValueError("runtime endian marker mismatch")
    header_copy = bytearray(data)
    stored_header_crc = struct.unpack_from("<I", data, 104)[0]
    struct.pack_into("<I", header_copy, 104, 0)
    if zlib.crc32(header_copy) & 0xFFFFFFFF != stored_header_crc:
        raise ValueError("runtime header CRC mismatch")
    section_count = struct.unpack_from("<I", data, 24)[0]
    if section_count == 0 or section_count > MAX_SECTION_COUNT:
        raise ValueError(f"invalid section count: {section_count}")
    section_table_offset = struct.unpack_from("<Q", data, 56)[0]
    section_table_size = struct.unpack_from("<Q", data, 64)[0]
    declared_file_size = struct.unpack_from("<Q", data, 72)[0]
    expected_table_size = section_count * SECTION_ENTRY_SIZE
    if section_table_size != expected_table_size:
        raise ValueError("runtime section table size does not match section count")
    if declared_file_size != actual_file_size:
        raise ValueError("runtime file size does not match the header")
    if section_table_offset + section_table_size > actual_file_size:
        raise ValueError("runtime section table is outside the file")
    return RuntimeHeader(
        format_major=format_major,
        format_minor=format_minor,
        header_flags=struct.unpack_from("<I", data, 20)[0],
        section_count=section_count,
        width=struct.unpack_from("<I", data, 28)[0],
        height=struct.unpack_from("<I", data, 32)[0],
        tile_size_px=struct.unpack_from("<H", data, 36)[0],
        min_elevation=struct.unpack_from("<h", data, 40)[0],
        max_elevation=struct.unpack_from("<h", data, 42)[0],
        region_size_tiles=struct.unpack_from("<H", data, 44)[0],
        resolved_seed=struct.unpack_from("<Q", data, 48)[0],
        section_table_offset=section_table_offset,
        section_table_size=section_table_size,
        file_size=declared_file_size,
        build_id=data[88:104],
        section_table_crc32=struct.unpack_from("<I", data, 108)[0],
    )


def _decode_sections(
    table: bytes,
    header: RuntimeHeader,
) -> tuple[RuntimeSection, ...]:
    sections: list[RuntimeSection] = []
    for index in range(header.section_count):
        offset = index * SECTION_ENTRY_SIZE
        values = struct.unpack_from("<IIIIQQQIIHHIII", table, offset)
        sections.append(RuntimeSection(*values))
    return tuple(sections)


def _validate_section_layout(
    sections: tuple[RuntimeSection, ...],
    header: RuntimeHeader,
) -> None:
    section_ids: set[int] = set()
    spans: list[tuple[int, int, int]] = []
    for section in sections:
        if section.section_id in section_ids:
            raise ValueError(f"duplicate section ID: {section.section_id}")
        section_ids.add(section.section_id)
        if section.codec != int(Codec.NONE):
            raise ValueError(f"unsupported codec in section {section.section_id}")
        if section.stored_size != section.unpacked_size:
            raise ValueError(
                f"compressed size mismatch in section {section.section_id}",
            )
        if section.alignment == 0 or section.alignment & (section.alignment - 1):
            raise ValueError(f"invalid alignment in section {section.section_id}")
        if section.offset % section.alignment:
            raise ValueError(f"misaligned section {section.section_id}")
        end = section.offset + section.stored_size
        if end < section.offset or end > header.file_size:
            raise ValueError(f"section {section.section_id} is outside the file")
        if section.element_stride:
            expected = section.element_count * section.element_stride
            if expected != section.unpacked_size:
                raise ValueError(
                    f"section {section.section_id} element size mismatch",
                )
        spans.append((section.offset, end, section.section_id))
    spans.sort()
    for previous, current in zip(spans, spans[1:], strict=False):
        if current[0] < previous[1]:
            raise ValueError(
                f"sections {previous[2]} and {current[2]} overlap",
            )
