from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from .logging_utils import timed_stage


LOGGER = logging.getLogger(__name__)


class LegacyEngineRunner:
    """Runs the legacy core map generator directly."""

    def __init__(self, engine_path: Path) -> None:
        """Initialize runner.

        Args:
            engine_path: Path to legacy engine script.
        """
        self._engine_path = engine_path

    def run(
        self,
        config_path: Path,
        map_out: Path,
        tactical_out: Path,
        log_file: Path | None,
    ) -> None:
        """Run legacy engine once.

        Args:
            config_path: Sanitized engine config path.
            map_out: ASCII map output path.
            tactical_out: Raw tactical JSON output path.
            log_file: Optional engine log path.

        Raises:
            RuntimeError: If engine exits with non-zero status.
        """
        command = [
            sys.executable,
            str(self._engine_path),
            "--config",
            str(config_path),
            "-o",
            str(map_out),
            "--tactical-out",
            str(tactical_out),
            "--no-render",
        ]
        if log_file is not None:
            command.extend(["--log-file", str(log_file)])

        with timed_stage(
            LOGGER,
            "LegacyEngineRunner.run",
            engine_path=self._engine_path,
            config_path=config_path,
            map_out=map_out,
            tactical_out=tactical_out,
        ) as metrics:
            LOGGER.debug("Legacy command: %s", " ".join(command))
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            metrics.update(
                {
                    "returncode": result.returncode,
                    "stdout_chars": len(result.stdout),
                    "stderr_chars": len(result.stderr),
                },
            )
            if result.stdout:
                LOGGER.debug("Legacy stdout:\n%s", result.stdout)
            if result.stderr:
                LOGGER.debug("Legacy stderr:\n%s", result.stderr)
            if result.returncode != 0:
                raise RuntimeError(
                    _format_legacy_failure(
                        returncode=result.returncode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        log_file=log_file,
                    ),
                )


def _format_legacy_failure(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    log_file: Path | None,
) -> str:
    """Format a concise legacy engine failure message."""
    parts = [f"Legacy engine failed returncode={returncode}"]
    stderr_tail = _tail_lines(stderr, limit=20)
    stdout_tail = _tail_lines(stdout, limit=10)
    if stderr_tail:
        parts.append("Last legacy stderr lines:\n" + stderr_tail)
    if stdout_tail:
        parts.append("Last legacy stdout lines:\n" + stdout_tail)
    if log_file is not None:
        parts.append(f"Full legacy log: {log_file}")
    return "\n".join(parts)


def _tail_lines(text: str, *, limit: int) -> str:
    """Return the last non-empty lines from a text block."""
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])
