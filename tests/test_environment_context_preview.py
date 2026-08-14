from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = ROOT / "examples" / "render_environment_context_previews.py"


def test_environment_context_preview_writes_all_debug_images(tmp_path: Path) -> None:
    """Ensure the Environment Context renderer writes every diagnostic PNG."""
    output_dir = _write_minimal_environment_package(tmp_path)
    module = _load_renderer_module()
    render_environment_previews = cast(Any, module).render_environment_previews

    outputs = render_environment_previews(output_dir, cell_size_px=3)

    assert len(outputs) == 10
    assert {path.name for path in outputs} == {
        "environment_moisture.png",
        "environment_region_profile.png",
        "environment_flora_region.png",
        "environment_slope.png",
        "environment_forest_depth.png",
        "environment_forest_distance.png",
        "environment_water_distance.png",
        "environment_road_distance.png",
        "environment_structure_distance.png",
        "environment_flora_context_preview.png",
    }
    for path in outputs:
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_dominant_flora_preview_exposes_expected_contexts() -> None:
    """Ensure the diagnostic classifier exposes the intended visual contexts."""
    module = _load_renderer_module()
    dominant = cast(Any, module)._dominant_flora_label

    common = {
        "moisture": 500,
        "region_profile": "open_plain",
        "flora_region": "open_meadow",
        "slope": 0,
        "forest_depth": 0,
        "forest_distance": 9,
        "water_distance": 9,
        "road_distance": 9,
        "structure_distance": 9,
    }

    assert dominant(**common) == "open_meadow"
    assert dominant(**{**common, "flora_region": "dry_grassland"}) == (
        "dry_grassland"
    )
    assert dominant(**{**common, "forest_depth": 1, "forest_distance": 0}) == (
        "forest_edge"
    )
    assert dominant(**{**common, "forest_depth": 4, "forest_distance": 0}) == (
        "deep_forest"
    )
    assert dominant(**{**common, "moisture": 820, "water_distance": 1}) == (
        "riparian_wetland"
    )
    assert dominant(
        **{
            **common,
            "moisture": 120,
            "region_profile": "upland",
        }
    ) == "dry_upland"
    assert dominant(**{**common, "slope": 3}) == "rocky_rugged"
    assert dominant(**{**common, "road_distance": 1}) == "disturbed"
    assert dominant(**{**common, "water_distance": 0}) == "water_core"
    assert dominant(**{**common, "structure_distance": 0}) == "structure_core"
    assert dominant(**{**common, "road_distance": 0}) == "road_core"


def test_environment_context_preview_cli_reports_success(tmp_path: Path) -> None:
    """Ensure the CLI renders the standard debug preview set."""
    output_dir = _write_minimal_environment_package(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(RENDERER_PATH),
            str(output_dir),
            "--cell-size",
            "2",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Environment Context preview создан: 10 файлов" in result.stderr
    assert (output_dir / "environment_flora_context_preview.png").is_file()


def _load_renderer_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "render_environment_context_previews_test",
        RENDERER_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_minimal_environment_package(tmp_path: Path) -> Path:
    output_dir = tmp_path / "output"
    package_dir = output_dir / "map_package"
    layers_dir = package_dir / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        package_dir / "map.json",
        {
            "layers": {
                "environment_context": "layers/environment_context.json",
            }
        },
    )
    _write_json(
        layers_dir / "environment_context.json",
        {
            "schema_version": "environment-context-layer-v3",
            "kind": "environment_context",
            "width": 4,
            "height": 3,
            "dictionaries": {
                "region_profile": {
                    "0": "dense_forest",
                    "1": "woodland",
                    "2": "wet_lowland",
                    "3": "upland",
                    "4": "open_plateau",
                    "5": "open_plain",
                    "6": "alpine",
                },
                "flora_region": {
                    "0": "dry_grassland",
                    "1": "open_meadow",
                    "2": "lush_meadow",
                    "3": "scrubland",
                    "4": "wet_meadow",
                    "5": "marshland",
                },
                "slope_band": {
                    "0": "flat",
                    "1": "gentle",
                    "2": "steep",
                    "3": "cliff",
                },
            },
            "grids": {
                "moisture": {
                    "rows": [
                        [200, 500, 820, 500],
                        [500, 500, 500, 500],
                        [500, 500, 500, 500],
                    ]
                },
                "region_profile": {
                    "rows": [
                        [3, 5, 2, 5],
                        [1, 0, 5, 5],
                        [5, 5, 5, 5],
                    ]
                },
                "flora_region": {
                    "rows": [
                        [0, 1, 4, 4],
                        [3, 2, 1, 1],
                        [1, 1, 1, 1],
                    ]
                },
                "slope_band": {
                    "rows": [
                        [0, 0, 0, 0],
                        [0, 0, 3, 0],
                        [0, 0, 0, 0],
                    ]
                },
                "forest_depth": {
                    "rows": [
                        [0, 0, 0, 0],
                        [1, 4, 0, 0],
                        [0, 0, 0, 0],
                    ]
                },
                "forest_distance": {
                    "rows": [
                        [2, 3, 4, 5],
                        [0, 0, 1, 2],
                        [1, 1, 2, 3],
                    ]
                },
                "water_distance": {
                    "rows": [
                        [9, 2, 1, 0],
                        [9, 9, 9, 1],
                        [9, 9, 9, 2],
                    ]
                },
                "road_distance": {
                    "rows": [
                        [9, 9, 9, 9],
                        [9, 9, 9, 9],
                        [0, 1, 2, 3],
                    ]
                },
                "structure_distance": {
                    "rows": [
                        [9, 9, 9, 9],
                        [9, 9, 9, 9],
                        [3, 2, 1, 0],
                    ]
                },
            },
        },
    )
    return output_dir


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
