from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .utils.json_io import write_json


MANIFEST_SCHEMA_VERSION = "generation-manifest-v7"
PIPELINE_VERSION = "pipeline-v1"
ASCII_MAP_SCHEMA_VERSION = "ascii-map-v1"
TACTICAL_MAP_SCHEMA_VERSION = "tactical-map-v0.26"
TACTICAL_DEBUG_SCHEMA_VERSION = "tactical-debug-v0.20"
RAW_TACTICAL_MAP_SCHEMA_VERSION = "raw-tactical-map-v1"
VALIDATION_REPORT_SCHEMA_VERSION = "validation-report-v4"
METRICS_SCHEMA_VERSION = "metrics-text-v1"
ENGINE_CONFIG_SCHEMA_VERSION = "legacy-engine-config-v1"
PNG_LAYER_SCHEMA_VERSION = "png-layer-v1"
DEBUG_LAYERS_VERSION = "debug-layers-v2"
RUNTIME_OBJECTS_SCHEMA_VERSION = "runtime-objects-v3"


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
    seed: Any,
    resolved_seed: int,
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
    available_debug_layers: list[str],
    generated_debug_layers: list[str],
    layers: list[str],
    artifacts: list[OutputArtifact],
    validation_summary: dict[str, Any],
    metrics: dict[str, Any],
    validation_report_path: Path | None = None,
) -> dict[str, Any]:
    """Build a machine-readable generation manifest.

    Args:
        output_dir: Directory where generation artifacts were written.
        seed: Raw seed value from config.
        resolved_seed: Concrete uint64 seed used by this generation run.
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
        available_debug_layers: Debug layer names supported by the renderer.
        generated_debug_layers: Debug layer names generated in this run.
        layers: Enabled output layer names.
        artifacts: Generated artifact descriptors.
        validation_summary: Compact output validation summary.
        metrics: Final pipeline metrics.
        validation_report_path: Optional detailed validation report path.

    Returns:
        JSON-serializable manifest dictionary.
    """
    files = [
        _artifact_to_dict(output_dir, artifact)
        for artifact in artifacts
        if artifact.path.exists()
    ]
    schema_versions = {
        "manifest": MANIFEST_SCHEMA_VERSION,
        "ascii_map": ASCII_MAP_SCHEMA_VERSION,
        "tactical_map": TACTICAL_MAP_SCHEMA_VERSION,
        "tactical_debug": TACTICAL_DEBUG_SCHEMA_VERSION,
        "raw_tactical_map": RAW_TACTICAL_MAP_SCHEMA_VERSION,
        "validation_report": VALIDATION_REPORT_SCHEMA_VERSION,
        "runtime_objects": RUNTIME_OBJECTS_SCHEMA_VERSION,
        "metrics": METRICS_SCHEMA_VERSION,
        "engine_config": ENGINE_CONFIG_SCHEMA_VERSION,
        "png_layer": PNG_LAYER_SCHEMA_VERSION,
    }
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "versions": {
            "generator": __version__,
            "pipeline": PIPELINE_VERSION,
            "schemas": schema_versions,
            "debug": DEBUG_LAYERS_VERSION,
        },
        "seed": seed,
        "resolved_seed": resolved_seed,
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
        "debug_layers": {
            "enabled": debug_images_enabled,
            "available": available_debug_layers,
            "generated": generated_debug_layers,
        },
        "enabled_layers": layers,
        "validation_summary": validation_summary,
        "validation_report": _relative_path(output_dir, validation_report_path),
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
    return {
        "path": _relative_path(output_dir, artifact.path),
        "kind": artifact.kind,
        "primary": artifact.primary,
        "debug_only": artifact.debug_only,
        "schema_version": artifact.schema_version,
        "size_bytes": artifact.path.stat().st_size,
    }


def _relative_path(output_dir: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    if path.is_relative_to(output_dir):
        return path.relative_to(output_dir).as_posix()
    return path.as_posix()
