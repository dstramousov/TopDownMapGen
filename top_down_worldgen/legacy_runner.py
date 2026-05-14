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
                    "Legacy engine failed\n"
                    f"STDOUT:\n{result.stdout}\n"
                    f"STDERR:\n{result.stderr}"
                )
