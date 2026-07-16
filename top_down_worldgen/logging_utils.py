from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from .performance import active_profiler


LOGGER = logging.getLogger(__name__)


def format_kv(values: Mapping[str, Any]) -> str:
    """Format key-value metrics for compact log output.

    Args:
        values: Metrics to format.

    Returns:
        Space-separated key-value pairs.
    """
    return " ".join(f"{key}={value}" for key, value in values.items())


def count_items(value: Any) -> int:
    """Return a safe item count for common container values.

    Args:
        value: Value to count.

    Returns:
        Item count, or zero for non-container values.
    """
    if isinstance(value, dict | list | tuple | set):
        return len(value)
    return 0


def json_summary(data: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact summary for a JSON-like mapping.

    Args:
        data: JSON-like mapping to summarize.

    Returns:
        Top-level key and collection-size summary.
    """
    summary: dict[str, Any] = {"keys": len(data)}
    for key, value in data.items():
        if isinstance(value, dict | list | tuple | set):
            summary[f"{key}_count"] = len(value)
    return summary


@contextmanager
def timed_stage(
    logger: logging.Logger,
    name: str,
    *,
    level: int = logging.INFO,
    **start_metrics: Any,
) -> Iterator[dict[str, Any]]:
    """Log stage start, completion, duration, and final metrics.

    Args:
        logger: Logger instance.
        name: Stage name.
        level: Logging level.
        **start_metrics: Metrics logged at stage start.

    Yields:
        Mutable metrics dictionary logged at stage completion.
    """
    if start_metrics:
        logger.log(level, "START %s %s", name, format_kv(start_metrics))
    else:
        logger.log(level, "START %s", name)

    started = perf_counter()
    end_metrics: dict[str, Any] = {}
    try:
        yield end_metrics
    except Exception:
        duration_ms = (perf_counter() - started) * 1000.0
        logger.exception("FAIL %s duration_ms=%.2f", name, duration_ms)
        raise
    duration_ms = (perf_counter() - started) * 1000.0
    profiler = active_profiler()
    if profiler is not None:
        profiler.record(name, duration_ms, {**start_metrics, **end_metrics})
    if end_metrics:
        logger.log(level, "DONE %s duration_ms=%.2f %s", name, duration_ms, format_kv(end_metrics))
    else:
        logger.log(level, "DONE %s duration_ms=%.2f", name, duration_ms)
