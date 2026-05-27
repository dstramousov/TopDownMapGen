from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class WorldPackage:
    """Loaded public world package data."""

    input_dir: Path
    package_dir: Path
    manifest: dict[str, Any] | None
    index: dict[str, Any]
    terrain: dict[str, Any]
    runtime_grids: dict[str, Any]
    runtime_objects: dict[str, Any]
    places: dict[str, Any]
    world_graph: dict[str, Any]
    routes: dict[str, Any]
    gameplay_zones: dict[str, Any]
    elevation_model: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VisualProfile:
    """Loaded visual profile and mapping rules."""

    root_dir: Path
    profile: dict[str, Any]
    tilesets: dict[str, Any]
    terrain_rules: dict[str, Any]
    object_rules: dict[str, Any]
    autotile_rules: dict[str, Any]
    decoration_rules: dict[str, Any]
    prefab_rules: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VisualPipelineResult:
    """Paths produced by the visual pipeline."""

    output_dir: Path
    visual_map_path: Path
    visual_layers_path: Path
    visual_objects_path: Path
    visual_chunks_path: Path
    preview_path: Path | None
    debug_autotile_masks_path: Path
