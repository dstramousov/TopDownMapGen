"""Deterministic string table construction."""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StringTable:
    """Deterministic UTF-8 string table and reverse mapping."""

    values: tuple[str, ...]
    ids: dict[str, int]
    payload: bytes


def build_string_table(values: set[str]) -> StringTable:
    """Build a deterministic UTF-8 string table.

    Args:
        values: Unique logical strings required by binary sections.

    Returns:
        Serialized string table and string-to-ID mapping.

    Raises:
        ValueError: If a value contains an embedded NUL.
    """
    ordered = tuple(sorted(values, key=lambda value: value.encode("utf-8")))
    encoded_values: list[bytes] = []
    offsets = [0]
    cursor = 0
    for value in ordered:
        if "\x00" in value:
            raise ValueError("runtime binary strings cannot contain NUL")
        encoded = value.encode("utf-8")
        encoded_values.append(encoded)
        cursor += len(encoded)
        offsets.append(cursor)
    payload = bytearray()
    payload.extend(struct.pack("<II", len(ordered), cursor))
    payload.extend(struct.pack(f"<{len(offsets)}I", *offsets))
    payload.extend(b"".join(encoded_values))
    return StringTable(
        values=ordered,
        ids={value: index for index, value in enumerate(ordered)},
        payload=bytes(payload),
    )
