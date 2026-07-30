from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from top_down_worldgen.runtime_binary.constants import SectionType
from top_down_worldgen.runtime_binary.model import RuntimeBinarySource
from top_down_worldgen.runtime_binary.reader import open_runtime_container
from top_down_worldgen.runtime_binary.writer import write_runtime_binary


def test_runtime_binary_roundtrip_and_determinism(tmp_path: Path) -> None:
    """Ensure the runtime container round-trips and is byte deterministic."""
    source = _source(width=3, height=2)
    first = tmp_path / "first.vxmap"
    second = tmp_path / "second.vxmap"

    first_result = write_runtime_binary(source, first)
    second_result = write_runtime_binary(source, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_result.build_id == second_result.build_id
    container = open_runtime_container(first)
    assert container.header.width == 3
    assert container.header.height == 2
    assert container.header.build_id == first_result.build_id
    assert len(container.sections_of_type(int(SectionType.TERRAIN_GRID))) == 1
    assert len(container.sections_of_type(int(SectionType.ELEVATION_GRID))) == 1
    assert len(
        container.sections_of_type(int(SectionType.STRUCTURE_HEIGHT_U8))
    ) == 1
    assert container.header.format_minor == 5
    assert len(
        container.sections_of_type(int(SectionType.VEGETATION_TYPE_U8))
    ) == 1
    assert len(
        container.sections_of_type(int(SectionType.VEGETATION_HEIGHT_U8))
    ) == 1


def test_runtime_binary_splits_edge_regions(tmp_path: Path) -> None:
    """Ensure non-multiple map sizes produce correctly clipped edge regions."""
    source = _source(width=129, height=130)
    path = tmp_path / "edge.vxmap"

    result = write_runtime_binary(source, path)
    container = open_runtime_container(path)

    assert result.region_count_x == 2
    assert result.region_count_y == 2
    assert len(container.sections_of_type(int(SectionType.TERRAIN_GRID))) == 4
    assert len(
        container.sections_of_type(int(SectionType.STRUCTURE_HEIGHT_U8))
    ) == 4
    assert len(
        container.sections_of_type(int(SectionType.STRUCTURE_WALKWAY_MASK_U16))
    ) == 4
    assert len(
        container.sections_of_type(int(SectionType.STRUCTURE_PARAPET_MASK_U16))
    ) == 4
    assert len(
        container.sections_of_type(int(SectionType.STRUCTURE_CRENELLATION_MASK_U16))
    ) == 4
    assert len(
        container.sections_of_type(int(SectionType.VEGETATION_TYPE_U8))
    ) == 4
    assert len(
        container.sections_of_type(int(SectionType.VEGETATION_HEIGHT_U8))
    ) == 4
    assert result.file_size < 360_000


def test_runtime_binary_reader_accepts_legacy_minor_zero(tmp_path: Path) -> None:
    """Ensure the structural reader accepts older v1.0 containers."""
    path = tmp_path / "legacy-minor.vxmap"
    write_runtime_binary(_source(width=3, height=2), path)
    data = bytearray(path.read_bytes())
    struct.pack_into("<H", data, 12, 0)
    struct.pack_into("<I", data, 104, 0)
    struct.pack_into("<I", data, 104, zlib.crc32(data[:128]) & 0xFFFFFFFF)
    path.write_bytes(data)

    container = open_runtime_container(path)

    assert container.header.format_major == 1
    assert container.header.format_minor == 0


def test_runtime_binary_reader_accepts_legacy_minor_one(tmp_path: Path) -> None:
    """Ensure the structural reader accepts older v1.1 containers."""
    path = tmp_path / "legacy-minor-one.vxmap"
    write_runtime_binary(_source(width=3, height=2), path)
    data = bytearray(path.read_bytes())
    struct.pack_into("<H", data, 12, 1)
    struct.pack_into("<I", data, 104, 0)
    struct.pack_into("<I", data, 104, zlib.crc32(data[:128]) & 0xFFFFFFFF)
    path.write_bytes(data)

    container = open_runtime_container(path)

    assert container.header.format_major == 1
    assert container.header.format_minor == 1


def test_runtime_binary_rejects_corrupted_payload(tmp_path: Path) -> None:
    """Ensure a modified payload is rejected by section CRC validation."""
    path = tmp_path / "corrupt.vxmap"
    write_runtime_binary(_source(width=3, height=2), path)
    data = bytearray(path.read_bytes())
    data[-1] ^= 0x80
    path.write_bytes(data)

    with pytest.raises(ValueError, match="bad CRC"):
        open_runtime_container(path)


def test_runtime_binary_rejects_bad_magic(tmp_path: Path) -> None:
    """Ensure a file with an unknown magic is rejected safely."""
    path = tmp_path / "bad-magic.vxmap"
    write_runtime_binary(_source(width=3, height=2), path)
    data = bytearray(path.read_bytes())
    data[0] = 0
    path.write_bytes(data)

    with pytest.raises(ValueError, match="magic"):
        open_runtime_container(path)



def test_runtime_binary_accepts_fortress_height_on_non_ruin_terrain(
    tmp_path: Path,
) -> None:
    """Ensure fortress micro geometry may carry height over ordinary terrain."""
    source = _source(width=3, height=2)
    source.structure_type_rows[0][0] = 10
    source.structure_micro_mask_rows[0][0] = 0x0FF0
    source.structure_height_rows[0][0] = 6

    result = write_runtime_binary(source, tmp_path / "fortress-wall.vxmap")

    assert result.file_size > 0


def test_runtime_binary_rejects_height_without_solid_structure(
    tmp_path: Path,
) -> None:
    """Ensure a height cannot exist without a solid semantic structure type."""
    source = _source(width=3, height=2)
    source.structure_height_rows[0][0] = 6

    with pytest.raises(ValueError, match="non-solid structure has height"):
        write_runtime_binary(source, tmp_path / "invalid-height.vxmap")

def _source(*, width: int, height: int) -> RuntimeBinarySource:
    terrain_types = ("grass", "tree_blocker", "ruin_wall_blocker")
    terrain_rows = [
        [terrain_types[(x + y) % len(terrain_types)] for x in range(width)]
        for y in range(height)
    ]
    movement_rows = [
        [1 if terrain_rows[y][x] == "grass" else None for x in range(width)]
        for y in range(height)
    ]
    collision_rows = [
        "".join("0" if value == "grass" else "1" for value in row)
        for row in terrain_rows
    ]
    projectile_rows = list(collision_rows)
    vision_rows = list(collision_rows)
    cover_rows = [
        [0.0 if terrain_rows[y][x] == "grass" else 0.75 for x in range(width)]
        for y in range(height)
    ]
    concealment_rows = [
        [0.0 if terrain_rows[y][x] == "grass" else 0.5 for x in range(width)]
        for y in range(height)
    ]
    elevation_rows = [[(x + y) % 4 - 1 for x in range(width)] for y in range(height)]
    return RuntimeBinarySource(
        width=width,
        height=height,
        tile_size_px=16,
        resolved_seed=123456789,
        generator_version="0.0.113",
        pipeline_version="pipeline-v1",
        profile="test",
        map_schema="map-package-map-v14",
        package_schema="map-package-v1",
        terrain_rows=terrain_rows,
        movement_rows=movement_rows,
        collision_rows=collision_rows,
        projectile_rows=projectile_rows,
        vision_rows=vision_rows,
        cover_rows=cover_rows,
        concealment_rows=concealment_rows,
        elevation_rows=elevation_rows,
        structure_height_rows=[
            [
                2 if terrain_rows[y][x] == "ruin_wall_blocker" else 0
                for x in range(width)
            ]
            for y in range(height)
        ],
        structure_type_rows=[
            [1 if terrain_rows[y][x] == "ruin_wall_blocker" else 0 for x in range(width)]
            for y in range(height)
        ],
        structure_walkway_mask_rows=[[0 for _ in range(width)] for _ in range(height)],
        structure_parapet_mask_rows=[[0 for _ in range(width)] for _ in range(height)],
        structure_crenellation_mask_rows=[
            [0 for _ in range(width)] for _ in range(height)
        ],
        structure_micro_mask_rows=[
            [65535 if terrain_rows[y][x] == "ruin_wall_blocker" else 0 for x in range(width)]
            for y in range(height)
        ],
        vegetation_type_rows=[
            [(x + y) % 5 for x in range(width)]
            for y in range(height)
        ],
        vegetation_height_rows=[
            [
                {0: 0, 1: 3, 2: 2, 3: 1, 4: 1}[(x + y) % 5]
                for x in range(width)
            ]
            for y in range(height)
        ],
        start={"x": 0, "y": 0},
        goal={"x": width - 1, "y": height - 1},
        terrain_catalog={
            "types": {
                "grass": {
                    "symbol": "+",
                    "movement_cost": 1,
                    "collision": "passable",
                    "walkable": True,
                    "tags": ["terrain"],
                },
                "tree_blocker": {
                    "symbol": "T",
                    "movement_cost": None,
                    "collision": "blocked",
                    "walkable": False,
                    "tags": ["blocker", "vegetation"],
                },
                "ruin_wall_blocker": {
                    "symbol": "#",
                    "movement_cost": None,
                    "collision": "blocked",
                    "walkable": False,
                    "tags": ["blocker", "ruin"],
                },
            },
        },
    )
