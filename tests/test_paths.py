from __future__ import annotations

from pathlib import Path

from top_down_worldgen.paths import OutputPaths


def test_output_paths_use_stable_raw_tactical_name(tmp_path: Path) -> None:
    """Ensure raw tactical dump filename does not encode stale schema versions."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")

    assert outputs.raw_tactical_map.name == "_raw_tactical_map.json"
    assert outputs.validation_report.name == "validation_report.json"
    assert outputs.object_catalog.name == "object_catalog.md"


def test_output_paths_include_runtime_objects_layer(tmp_path: Path) -> None:
    """Ensure runtime objects have a dedicated debug PNG path."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")

    assert outputs.layer_runtime_objects.name == "layer_runtime_objects.png"


def test_output_paths_include_map_package_paths(tmp_path: Path) -> None:
    """Ensure structured map package paths are stable."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")

    assert outputs.map_package_map.as_posix().endswith("map_package/map.json")
    assert outputs.map_package_tile_grid.as_posix().endswith(
        "map_package/layers/tile_grid.json",
    )
    assert outputs.map_package_terrain.as_posix().endswith(
        "map_package/layers/terrain.json",
    )
    assert outputs.map_package_start_goal.as_posix().endswith(
        "map_package/layers/start_goal.json",
    )
    assert outputs.map_package_runtime_objects.as_posix().endswith(
        "map_package/objects/runtime_objects.json",
    )


def test_from_cli_output_accepts_output_directory_target(tmp_path: Path) -> None:
    """Ensure directory CLI target writes all artifacts under one output root."""
    outputs = OutputPaths.from_cli_output(tmp_path / "output")

    assert outputs.output_dir == tmp_path / "output"
    assert outputs.generated_map == tmp_path / "output" / "generated_map.txt"
    assert outputs.manifest == tmp_path / "output" / "_manifest.json"
    assert outputs.map_package_map == tmp_path / "output" / "map_package" / "map.json"


def test_from_cli_output_accepts_generated_map_file_target(tmp_path: Path) -> None:
    """Ensure file CLI target keeps legacy and package outputs together."""
    outputs = OutputPaths.from_cli_output(tmp_path / "output" / "custom_map.txt")

    assert outputs.output_dir == tmp_path / "output"
    assert outputs.generated_map == tmp_path / "output" / "custom_map.txt"
    assert outputs.tactical_map == tmp_path / "output" / "tactical_map.json"
    assert outputs.map_package_map == tmp_path / "output" / "map_package" / "map.json"
