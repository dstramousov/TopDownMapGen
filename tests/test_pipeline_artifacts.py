from __future__ import annotations

from pathlib import Path

from top_down_worldgen.paths import OutputPaths
from top_down_worldgen.pipeline import WorldgenPipeline


def test_pipeline_artifacts_include_vegetation_geometry(tmp_path: Path) -> None:
    """Ensure manifest artifacts include both vegetation geometry layers."""
    outputs = OutputPaths.from_output_map(tmp_path / "generated_map.txt")

    artifacts = WorldgenPipeline._build_artifacts(
        outputs,
        render=False,
        rendered_layers=[],
    )
    by_kind = {artifact.kind: artifact for artifact in artifacts}

    assert by_kind["map_package:vegetation_type"].path == (
        outputs.map_package_vegetation_type
    )
    assert by_kind["map_package:vegetation_height"].path == (
        outputs.map_package_vegetation_height
    )
    assert by_kind["map_package:vegetation_visual"].schema_version == (
        "vegetation-visual-report-v7"
    )
    assert by_kind["fortress_site_report"].path == outputs.fortress_site_report
    assert by_kind["fortress_site_report"].schema_version == (
        "fortress-site-report-v1"
    )
