from __future__ import annotations

from pathlib import Path

from top_down_worldgen.paths import OutputPaths


def test_output_paths_use_stable_raw_tactical_name(tmp_path: Path) -> None:
    """Ensure raw tactical dump filename does not encode stale schema versions."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")

    assert outputs.raw_tactical_map.name == "_raw_tactical_map.json"
    assert outputs.validation_report.name == "validation_report.json"
