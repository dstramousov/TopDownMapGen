from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json_object
from .models import WorldPackage


class WorldPackageLoader:
    """Load public map package files produced by the world generator."""

    def load(self, input_dir: Path) -> WorldPackage:
        """Load a world package from an output directory or package directory.

        Args:
            input_dir: Generation output directory or direct map_package path.

        Returns:
            Loaded public world package.

        Raises:
            FileNotFoundError: If required public package files are missing.
        """
        root = input_dir.resolve()
        package_dir = root if root.name == "map_package" else root / "map_package"
        index_path = package_dir / "map.json"
        if not index_path.exists():
            raise FileNotFoundError(f"Map package index not found: {index_path}")

        manifest_path = package_dir.parent / "_manifest.json"
        manifest = read_json_object(manifest_path) if manifest_path.exists() else None
        index = read_json_object(index_path)

        return WorldPackage(
            input_dir=root,
            package_dir=package_dir,
            manifest=manifest,
            index=index,
            terrain=self._read_relative(package_dir, index, "layers", "terrain"),
            runtime_grids=self._read_path(package_dir / "runtime_grids.json"),
            runtime_objects=self._read_relative(
                package_dir, index, "objects", "runtime_objects"
            ),
            places=self._read_relative(package_dir, index, "objects", "places"),
            world_graph=self._read_path(package_dir / "world_graph.json"),
            routes=self._read_path(package_dir / "routes.json"),
            gameplay_zones=self._read_path(package_dir / "gameplay_zones.json"),
            elevation_model=self._read_path(package_dir / "elevation_model.json"),
            elevation_features=self._read_path(package_dir / "elevation_features.json"),
            elevation_transitions=self._read_path(package_dir / "elevation_transitions.json"),
        )

    @staticmethod
    def _read_path(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Required map package file not found: {path}")
        return read_json_object(path)

    def _read_relative(
        self,
        package_dir: Path,
        index: dict[str, Any],
        section: str,
        key: str,
    ) -> dict[str, Any]:
        section_data = index.get(section)
        if not isinstance(section_data, dict):
            raise FileNotFoundError(f"Missing map package index section: {section}")
        relative_path = section_data.get(key)
        if not isinstance(relative_path, str) or not relative_path:
            raise FileNotFoundError(f"Missing map package index path: {section}.{key}")
        return self._read_path(package_dir / relative_path)
