from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the JSON root is not an object.
        json.JSONDecodeError: If JSON parsing fails.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def write_json_object(data: dict[str, Any], path: Path) -> None:
    """Write a JSON object to disk.

    Args:
        data: JSON-serializable object.
        path: Output JSON file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
