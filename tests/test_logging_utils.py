import logging

from top_down_worldgen.logging_utils import format_kv, timed_stage


def test_format_kv() -> None:
    """Ensure key-value metrics are formatted compactly."""
    assert format_kv({"created": 2, "duration_ms": 1.5}) == "created=2 duration_ms=1.5"


def test_timed_stage_logs_done(caplog) -> None:  # type: ignore[no-untyped-def]
    """Ensure timed stage writes final metrics."""
    logger = logging.getLogger("tests.logging_utils")

    with caplog.at_level(logging.INFO):
        with timed_stage(logger, "unit.stage") as metrics:
            metrics["items"] = 3

    assert "START unit.stage" in caplog.text
    assert "DONE unit.stage" in caplog.text
    assert "items=3" in caplog.text
