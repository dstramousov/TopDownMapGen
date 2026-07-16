from __future__ import annotations

from pathlib import Path

from top_down_worldgen.logging_utils import timed_stage
from top_down_worldgen.performance import PerformanceProfiler


def test_profiler_collects_timed_stage(tmp_path: Path) -> None:
    import logging

    profiler = PerformanceProfiler()
    with profiler:
        with timed_stage(logging.getLogger(__name__), "test.stage") as metrics:
            metrics["items"] = 3
    report = profiler.build_report(width=10, height=20)
    assert report["map"]["tiles"] == 200
    assert any(stage["name"] == "test.stage" for stage in report["stages"])
    output = tmp_path / "performance_profile.json"
    profiler.write_report(report, output)
    assert output.exists()
