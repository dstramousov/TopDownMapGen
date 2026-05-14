from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils.json_io import write_json


MANIFEST_SCHEMA_VERSION = "generation-manifest-v1"
ASCII_MAP_SCHEMA_VERSION = "ascii-map-v1"
TACTICAL_MAP_SCHEMA_VERSION = "tactical-map-v0.20"
TACTICAL_DEBUG_SCHEMA_VERSION = "tactical-debug-v0.19"
METRICS_SCHEMA_VERSION = "metrics-text-v1"
ENGINE_CONFIG_SCHEMA_VERSION = "legacy-engine-config-v1"
PNG_LAYER_SCHEMA_VERSION = "png-layer-v1"


@dataclass(frozen=True, slots=True)
class OutputArtifact:
    """Generated output artifact descriptor."""

    path: Path
    kind: str
    primary: bool
    debug_only: bool
    schema_version: str


def build_manifest(
    *,
    output_dir: Path,
    seed: int | str,
    profile: str,
    width: int,
    height: int,
    tile_size_px: int,
    total_time_ms: float,
    engine_time_ms: float,
    tactical_time_ms: float,
    render_time_ms: float,
    render_enabled: bool,
    debug_images_enabled: bool,
    layers: list[str],
    artifacts: list[OutputArtifact],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Build a machine-readable generation manifest.

    Args:
        output_dir: Directory where generation artifacts were written.
        seed: Generation seed.
        profile: Objective profile name.
        width: Map width in tiles.
        height: Map height in tiles.
        tile_size_px: Render tile size in pixels.
        total_time_ms: Total pipeline duration.
        engine_time_ms: Legacy engine duration.
        tactical_time_ms: Tactical processing duration.
        render_time_ms: Render duration.
        render_enabled: Whether PNG rendering was enabled.
        debug_images_enabled: Whether debug PNG layers were enabled.
        layers: Enabled output layer names.
        artifacts: Generated artifact descriptors.
        metrics: Final pipeline metrics.

    Returns:
        JSON-serializable manifest dictionary.
    """
    files = [
        _artifact_to_dict(output_dir, artifact)
        for artifact in artifacts
        if artifact.path.exists()
    ]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generator_version": "0.0.6",
        "seed": seed,
        "profile": profile,
        "dimensions": {
            "width_tiles": width,
            "height_tiles": height,
            "tile_size_px": tile_size_px,
        },
        "generation_time_ms": round(total_time_ms, 2),
        "timings_ms": {
            "engine": round(engine_time_ms, 2),
            "tactical": round(tactical_time_ms, 2),
            "render": round(render_time_ms, 2),
            "total": round(total_time_ms, 2),
        },
        "render": {
            "enabled": render_enabled,
            "debug_images_enabled": debug_images_enabled,
        },
        "enabled_layers": layers,
        "schema_versions": {
            "manifest": MANIFEST_SCHEMA_VERSION,
            "ascii_map": ASCII_MAP_SCHEMA_VERSION,
            "tactical_map": TACTICAL_MAP_SCHEMA_VERSION,
            "tactical_debug": TACTICAL_DEBUG_SCHEMA_VERSION,
            "metrics": METRICS_SCHEMA_VERSION,
            "engine_config": ENGINE_CONFIG_SCHEMA_VERSION,
            "png_layer": PNG_LAYER_SCHEMA_VERSION,
        },
        "primary_outputs": [file_info for file_info in files if file_info["primary"]],
        "debug_outputs": [file_info for file_info in files if file_info["debug_only"]],
        "files": files,
        "metrics": metrics,
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    """Write generation manifest to disk.

    Args:
        manifest: Manifest JSON object.
        path: Output path.
    """
    write_json(manifest, path)


def _artifact_to_dict(output_dir: Path, artifact: OutputArtifact) -> dict[str, Any]:
    if artifact.path.is_relative_to(output_dir):
        relative_path = artifact.path.relative_to(output_dir)
    else:
        relative_path = artifact.path
    return {
        "path": relative_path.as_posix(),
        "kind": artifact.kind,
        "primary": artifact.primary,
        "debug_only": artifact.debug_only,
        "schema_version": artifact.schema_version,
        "size_bytes": artifact.path.stat().st_size,
    }
