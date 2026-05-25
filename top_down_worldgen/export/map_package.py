from __future__ import annotations

from pathlib import Path
from typing import Any

from top_down_worldgen import __version__
from top_down_worldgen.manifest import (
    COLLISION_LAYER_SCHEMA_VERSION,
    ELEVATION_LAYER_SCHEMA_VERSION,
    GAMEPLAY_LAYER_SCHEMA_VERSION,
    MAP_PACKAGE_MAP_SCHEMA_VERSION,
    MAP_PACKAGE_SCHEMA_VERSION,
    MOVEMENT_LAYER_SCHEMA_VERSION,
    OBJECT_INSTANCES_SCHEMA_VERSION,
    PLACES_SCHEMA_VERSION,
    START_GOAL_LAYER_SCHEMA_VERSION,
    TERRAIN_LAYER_SCHEMA_VERSION,
    TILE_GRID_LAYER_SCHEMA_VERSION,
)
from top_down_worldgen.paths import OutputPaths
from top_down_worldgen.utils.json_io import write_json

_GAMEPLAY_FILES: tuple[tuple[str, str], ...] = (
    ("combat_zones", "combat_zones.json"),
    ("cover_points", "cover_points.json"),
    ("choke_points", "choke_points.json"),
    ("flank_routes", "flank_routes.json"),
    ("enemy_spawn_zones", "enemy_spawn_zones.json"),
    ("fallback_positions", "fallback_positions.json"),
)


def write_map_package(
    *,
    outputs: OutputPaths,
    runtime_data: dict[str, Any],
    rows: list[str],
    width: int,
    height: int,
    tile_size_px: int,
    seed: Any,
    resolved_seed: int,
    profile: str,
) -> None:
    """Write the structured map package next to legacy outputs.

    Args:
        outputs: Output path bundle.
        runtime_data: Runtime tactical map data.
        rows: ASCII map rows.
        width: Map width in tiles.
        height: Map height in tiles.
        tile_size_px: Tile size in pixels.
        seed: Raw seed value from public config.
        resolved_seed: Concrete uint64 seed used for the run.
        profile: Objective profile name.
    """
    outputs.map_package_dir.mkdir(parents=True, exist_ok=True)
    outputs.map_package_layers_dir.mkdir(parents=True, exist_ok=True)
    outputs.map_package_gameplay_dir.mkdir(parents=True, exist_ok=True)
    outputs.map_package_objects_dir.mkdir(parents=True, exist_ok=True)

    map_data = _dict(runtime_data.get("map"))
    tile_grid = _string_rows(map_data.get("tile_grid"), rows)
    movement_costs = _dict(runtime_data.get("movement_costs"))
    if not movement_costs:
        movement_costs = _dict(map_data.get("movement_costs"))
    tile_legend = _dict(map_data.get("tile_legend"))
    terrain_rows = _terrain_rows(tile_grid, tile_legend)
    points = _extract_points(tile_grid)
    collision = _build_collision_layer(
        tile_grid=tile_grid,
        tile_legend=tile_legend,
        width=width,
        height=height,
    )

    write_json(
        {
            "schema_version": TILE_GRID_LAYER_SCHEMA_VERSION,
            "kind": "tile_grid",
            "width": width,
            "height": height,
            "format": "ascii_rows",
            "tile_legend": tile_legend,
            "tile_counts": _dict(map_data.get("tile_counts")),
            "rows": tile_grid,
        },
        outputs.map_package_tile_grid,
    )
    write_json(
        {
            "schema_version": TERRAIN_LAYER_SCHEMA_VERSION,
            "kind": "terrain",
            "width": width,
            "height": height,
            "format": "type_rows",
            "type_by_tile": tile_legend,
            "rows": terrain_rows,
        },
        outputs.map_package_terrain,
    )
    write_json(
        {
            "schema_version": MOVEMENT_LAYER_SCHEMA_VERSION,
            "kind": "movement_costs",
            "width": width,
            "height": height,
            "costs_by_tile": movement_costs,
            "costs_by_type": _movement_costs_by_type(movement_costs, tile_legend),
        },
        outputs.map_package_movement_costs,
    )
    write_json(collision, outputs.map_package_collision)
    write_json(
        {
            "schema_version": ELEVATION_LAYER_SCHEMA_VERSION,
            "kind": "elevation",
            "width": width,
            "height": height,
            "elevation": _dict(runtime_data.get("elevation")),
        },
        outputs.map_package_elevation,
    )
    write_json(
        {
            "schema_version": START_GOAL_LAYER_SCHEMA_VERSION,
            "kind": "start_goal",
            "width": width,
            "height": height,
            "start": points["start"],
            "goal": points["goal"],
            "source_layer": "tile_grid",
        },
        outputs.map_package_start_goal,
    )

    for key, filename in _GAMEPLAY_FILES:
        write_json(
            {
                "schema_version": GAMEPLAY_LAYER_SCHEMA_VERSION,
                "kind": key,
                "items": _list(runtime_data.get(key)),
            },
            outputs.map_package_gameplay_dir / filename,
        )

    write_json(
        {
            "schema_version": OBJECT_INSTANCES_SCHEMA_VERSION,
            "kind": "runtime_objects",
            "items": _list(runtime_data.get("runtime_objects")),
            "summary": _dict(runtime_data.get("runtime_objects_summary")),
        },
        outputs.map_package_runtime_objects,
    )
    write_json(
        {
            "schema_version": PLACES_SCHEMA_VERSION,
            "kind": "places",
            "items": _list(runtime_data.get("places")),
            "summary": _dict(runtime_data.get("places_summary")),
        },
        outputs.map_package_places,
    )

    write_json(
        {
            "schema_version": MAP_PACKAGE_MAP_SCHEMA_VERSION,
            "package_schema_version": MAP_PACKAGE_SCHEMA_VERSION,
            "generator_version": __version__,
            "pipeline_version": "pipeline-v1",
            "seed": seed,
            "resolved_seed": resolved_seed,
            "profile": profile,
            "dimensions": {
                "width_tiles": width,
                "height_tiles": height,
                "tile_size_px": tile_size_px,
            },
            "coordinates": {
                "origin": "top_left",
                "unit": "tile",
                "x_axis": "right",
                "y_axis": "down",
            },
            "points": points,
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "terrain": "layers/terrain.json",
                "movement_costs": "layers/movement_costs.json",
                "collision": "layers/collision.json",
                "elevation": "layers/elevation.json",
                "start_goal": "layers/start_goal.json",
            },
            "gameplay": {
                key: f"gameplay/{filename}" for key, filename in _GAMEPLAY_FILES
            },
            "objects": {
                "runtime_objects": "objects/runtime_objects.json",
                "places": "objects/places.json",
            },
            "legacy_outputs": {
                "ascii_map": "../generated_map.txt",
                "tactical_map": "../tactical_map.json",
                "tactical_debug": "../tactical_map_debug.json",
            },
        },
        outputs.map_package_map,
    )


def map_package_artifact_paths(outputs: OutputPaths) -> list[Path]:
    """Return stable map package artifact paths.

    Args:
        outputs: Output path bundle.

    Returns:
        Ordered map package paths.
    """
    return [
        outputs.map_package_map,
        outputs.map_package_tile_grid,
        outputs.map_package_terrain,
        outputs.map_package_movement_costs,
        outputs.map_package_collision,
        outputs.map_package_elevation,
        outputs.map_package_start_goal,
        outputs.map_package_combat_zones,
        outputs.map_package_cover_points,
        outputs.map_package_choke_points,
        outputs.map_package_flank_routes,
        outputs.map_package_enemy_spawn_zones,
        outputs.map_package_fallback_positions,
        outputs.map_package_runtime_objects,
        outputs.map_package_places,
    ]



def _terrain_rows(
    tile_grid: list[str],
    tile_legend: dict[str, Any],
) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in tile_grid:
        rows.append([str(tile_legend.get(tile, "unknown")) for tile in row])
    return rows


def _movement_costs_by_type(
    movement_costs: dict[str, Any],
    tile_legend: dict[str, Any],
) -> dict[str, Any]:
    costs_by_type: dict[str, Any] = {}
    for symbol, cost in movement_costs.items():
        terrain_type = tile_legend.get(symbol)
        if isinstance(terrain_type, str) and terrain_type:
            costs_by_type[terrain_type] = cost
    return costs_by_type


def _build_collision_layer(
    *,
    tile_grid: list[str],
    tile_legend: dict[str, Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    blocked_tiles = _blocked_tile_symbols(tile_legend)
    present_tiles = set("".join(tile_grid))
    passable_tiles = sorted(present_tiles - blocked_tiles)
    blocked_types = sorted(
        str(tile_legend.get(tile, "unknown"))
        for tile in blocked_tiles
        if tile in present_tiles
    )
    passable_types = sorted(
        {
            str(tile_legend.get(tile, "unknown"))
            for tile in passable_tiles
        },
    )
    return {
        "schema_version": COLLISION_LAYER_SCHEMA_VERSION,
        "kind": "collision",
        "width": width,
        "height": height,
        "format": "boolean_rows",
        "legend": {
            "0": "passable",
            "1": "blocked",
        },
        "rows": [
            "".join("1" if tile in blocked_tiles else "0" for tile in row)
            for row in tile_grid
        ],
        "blocked_tile_types": blocked_types,
        "passable_tile_types": passable_types,
        "legacy_blocked_tiles": sorted(blocked_tiles),
        "legacy_passable_tiles": passable_tiles,
        "source_layer": "terrain",
    }


def _blocked_tile_symbols(tile_legend: dict[str, Any]) -> set[str]:
    blocked_tiles = {
        symbol
        for symbol, tile_type in tile_legend.items()
        if isinstance(symbol, str)
        and isinstance(tile_type, str)
        and "blocker" in tile_type
    }
    blocked_tiles.update({"T", "#"})
    return blocked_tiles


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _string_rows(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return list(fallback)


def _extract_points(rows: list[str]) -> dict[str, dict[str, int] | None]:
    points: dict[str, dict[str, int] | None] = {"start": None, "goal": None}
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            if tile == "S" and points["start"] is None:
                points["start"] = {"x": x, "y": y}
            elif tile == "G" and points["goal"] is None:
                points["goal"] = {"x": x, "y": y}
    return points
