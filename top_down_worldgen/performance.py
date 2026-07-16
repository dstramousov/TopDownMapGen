from __future__ import annotations

import json
import resource
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator


_ACTIVE_PROFILER: ContextVar[PerformanceProfiler | None] = ContextVar(
    "top_down_worldgen_active_profiler",
    default=None,
)


@dataclass(slots=True)
class StageSample:
    """Single measured pipeline stage."""

    name: str
    duration_ms: float
    depth: int
    metrics: dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    """Collect timed-stage measurements for one generation run."""

    def __init__(self) -> None:
        self._samples: list[StageSample] = []
        self._depth = 0
        self._started = 0.0
        self._token: Any = None

    def __enter__(self) -> PerformanceProfiler:
        self._samples.clear()
        self._depth = 0
        self._started = perf_counter()
        self._token = _ACTIVE_PROFILER.set(self)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        _ACTIVE_PROFILER.reset(self._token)

    @contextmanager
    def measure(self, name: str) -> Iterator[dict[str, Any]]:
        depth = self._depth
        self._depth += 1
        started = perf_counter()
        metrics: dict[str, Any] = {}
        try:
            yield metrics
        finally:
            self._depth -= 1
            self._samples.append(
                StageSample(
                    name=name,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    depth=depth,
                    metrics=dict(metrics),
                )
            )

    def record(self, name: str, duration_ms: float, metrics: dict[str, Any]) -> None:
        """Record a stage measured by ``timed_stage``."""
        self._samples.append(
            StageSample(
                name=name,
                duration_ms=duration_ms,
                depth=self._depth,
                metrics=dict(metrics),
            )
        )

    def build_report(self, *, width: int, height: int) -> dict[str, Any]:
        total_ms = (perf_counter() - self._started) * 1000.0
        total_tiles = width * height
        top_level = [sample for sample in self._samples if sample.name != "cli.main"]
        ordered = sorted(top_level, key=lambda item: item.duration_ms, reverse=True)
        million_tile_factor = 1_000_000 / total_tiles if total_tiles > 0 else 0.0
        return {
            "schema_version": "performance-profile-v1",
            "map": {
                "width": width,
                "height": height,
                "tiles": total_tiles,
            },
            "total_time_ms": round(total_ms, 2),
            "milliseconds_per_million_tiles": round(total_ms * million_tile_factor, 2)
            if million_tile_factor
            else 0.0,
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2),
            "stages": [
                {
                    "name": sample.name,
                    "duration_ms": round(sample.duration_ms, 2),
                    "percent": round(sample.duration_ms * 100.0 / total_ms, 2)
                    if total_ms > 0
                    else 0.0,
                    "depth": sample.depth,
                    "metrics": sample.metrics,
                }
                for sample in ordered
            ],
        }

    @staticmethod
    def write_report(report: dict[str, Any], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    @staticmethod
    def format_report(report: dict[str, Any], *, limit: int = 20) -> str:
        stages = report.get("stages", [])
        lines = [
            "",
            "Performance profile:",
            f"  map: {report['map']['width']} × {report['map']['height']} = {report['map']['tiles']} tiles",
            f"  total: {report['total_time_ms'] / 1000.0:.2f}s",
            f"  per 1M tiles: {report['milliseconds_per_million_tiles'] / 1000.0:.2f}s",
            f"  peak RSS: {report['peak_rss_mib']:.1f} MiB",
            "",
            f"  {'stage':<42}{'time':>10}{'%':>8}",
        ]
        for item in stages[:limit]:
            lines.append(
                f"  {str(item['name'])[:42]:<42}"
                f"{item['duration_ms'] / 1000.0:>9.2f}s"
                f"{item['percent']:>7.1f}%"
            )
        return "\n".join(lines)


def active_profiler() -> PerformanceProfiler | None:
    """Return the profiler active in the current context, if any."""
    return _ACTIVE_PROFILER.get()
