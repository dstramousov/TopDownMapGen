from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from top_down_worldgen.logging_utils import json_summary, timed_stage


LOGGER = logging.getLogger(__name__)


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If the file does not contain a JSON object.
    """
    with timed_stage(LOGGER, "read_json", path=path) as metrics:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in {path}")
        metrics.update(json_summary(data))
        return data


def write_json(data: dict[str, Any], path: Path) -> None:
    """Write a JSON object to disk.

    Args:
        data: JSON object.
        path: Output file path.
    """
    with timed_stage(LOGGER, "write_json", path=path) as metrics:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        path.write_text(serialized, encoding="utf-8")
        metrics.update(json_summary(data) | {"bytes": len(serialized.encode("utf-8"))})


def write_json_atomic(data: dict[str, Any], path: Path) -> None:
    """Atomically write a JSON object to disk.

    Args:
        data: JSON object.
        path: Final output file path.
    """
    with timed_stage(LOGGER, "write_json_atomic", path=path) as metrics:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        metrics.update(
            json_summary(data) | {"bytes": len(serialized.encode("utf-8"))},
        )
