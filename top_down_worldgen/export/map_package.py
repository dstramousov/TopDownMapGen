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
    OBJECT_TYPES_CATALOG_SCHEMA_VERSION,
    OBJECT_RENDER_HINTS_SCHEMA_VERSION,
    RENDER_PROFILE_SCHEMA_VERSION,
    TILE_RENDER_HINTS_SCHEMA_VERSION,
    PLACES_SCHEMA_VERSION,
    START_GOAL_LAYER_SCHEMA_VERSION,
    TERRAIN_LAYER_SCHEMA_VERSION,
    TILE_GRID_LAYER_SCHEMA_VERSION,
    TILE_TYPES_CATALOG_SCHEMA_VERSION,
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
    outputs.map_package_catalogs_dir.mkdir(parents=True, exist_ok=True)
    outputs.map_package_render_dir.mkdir(parents=True, exist_ok=True)

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
        _build_tile_types_catalog(
            tile_legend=tile_legend,
            movement_costs=movement_costs,
            collision=collision,
        ),
        outputs.map_package_tile_types,
    )
    object_types_catalog = _build_object_types_catalog(
        _list(runtime_data.get("runtime_objects")),
    )
    write_json(object_types_catalog, outputs.map_package_object_types)

    tile_render_hints = _build_tile_render_hints(tile_legend=tile_legend)
    object_render_hints = _build_object_render_hints(object_types_catalog)
    render_profile = _build_render_profile(
        width=width,
        height=height,
        tile_size_px=tile_size_px,
    )
    write_json(render_profile, outputs.map_package_render_profile)
    write_json(tile_render_hints, outputs.map_package_tile_render_hints)
    write_json(object_render_hints, outputs.map_package_object_render_hints)

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
            "catalogs": {
                "tile_types": "catalogs/tile_types.json",
                "object_types": "catalogs/object_types.json",
            },
            "render": {
                "profile": "render/render_profile.json",
                "tile_render_hints": "render/tile_render_hints.json",
                "object_render_hints": "render/object_render_hints.json",
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
        outputs.map_package_tile_types,
        outputs.map_package_object_types,
        outputs.map_package_render_profile,
        outputs.map_package_tile_render_hints,
        outputs.map_package_object_render_hints,
    ]




def _build_render_profile(*, width: int, height: int, tile_size_px: int) -> dict[str, Any]:
    return {
        "schema_version": RENDER_PROFILE_SCHEMA_VERSION,
        "kind": "render_profile",
        "purpose": "renderer_ready_semantic_hints",
        "dimensions": {
            "width_tiles": width,
            "height_tiles": height,
            "tile_size_px": tile_size_px,
        },
        "coordinate_space": "tile",
        "draw_order": [
            "terrain",
            "terrain_overlays",
            "objects_below_actor",
            "actors",
            "objects_above_actor",
            "debug_overlays",
        ],
        "inputs": {
            "terrain": "../layers/terrain.json",
            "tile_types": "../catalogs/tile_types.json",
            "runtime_objects": "../objects/runtime_objects.json",
            "object_types": "../catalogs/object_types.json",
            "tile_render_hints": "tile_render_hints.json",
            "object_render_hints": "object_render_hints.json",
        },
        "notes": [
            "Hints are semantic and renderer-ready, not bound to a concrete PNG atlas.",
            "A renderer may ignore unknown hints and use fallback groups.",
        ],
    }


def _build_tile_render_hints(*, tile_legend: dict[str, Any]) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    for raw_type in sorted({
        item for item in tile_legend.values() if isinstance(item, str) and item
    }):
        hints[raw_type] = _tile_render_hint(raw_type)
    return {
        "schema_version": TILE_RENDER_HINTS_SCHEMA_VERSION,
        "kind": "tile_render_hints",
        "hints": hints,
        "fallback": {
            "render_mode": "single_tile",
            "visual_group": "terrain/unknown",
            "variant_policy": "stable_by_coordinate",
        },
    }


def _tile_render_hint(tile_type: str) -> dict[str, Any]:
    render_mode = "single_tile"
    visual_group = f"terrain/{tile_type}"
    layer = "terrain"
    variant_policy = "stable_by_coordinate"
    blend_edges = False
    autotile_group: str | None = None

    if "road" in tile_type:
        render_mode = "autotile"
        autotile_group = "old_overgrown_road"
        visual_group = "terrain/road/old_overgrown"
        blend_edges = True
    elif "water" in tile_type:
        render_mode = "autotile"
        autotile_group = "water_puddle"
        visual_group = "terrain/water/puddle"
        blend_edges = True
    elif "ruin_wall" in tile_type:
        render_mode = "autotile"
        autotile_group = "ruin_wall"
        visual_group = "structure/ruin_wall"
        layer = "terrain_overlays"
    elif "ruin_floor" in tile_type:
        visual_group = "terrain/ruin_floor"
        blend_edges = True
    elif "tree" in tile_type:
        visual_group = "vegetation/tree_blocker"
        layer = "objects_above_actor"
    elif "bush" in tile_type:
        visual_group = "vegetation/bush"
        layer = "objects_below_actor"
    elif "flower" in tile_type or "mushroom" in tile_type:
        visual_group = "terrain/decor"
        layer = "terrain_overlays"
    elif tile_type in {"start", "goal"}:
        visual_group = f"marker/{tile_type}"
        layer = "debug_overlays"
        variant_policy = "fixed"
    elif "cracked" in tile_type:
        visual_group = "terrain/cracked_ground"
        blend_edges = True
    elif tile_type == "grass":
        visual_group = "terrain/grass"
        blend_edges = True

    hint: dict[str, Any] = {
        "render_mode": render_mode,
        "visual_group": visual_group,
        "draw_layer": layer,
        "variant_policy": variant_policy,
        "blend_edges": blend_edges,
    }
    if autotile_group is not None:
        hint["autotile_group"] = autotile_group
        hint["autotile_neighbors"] = "same_terrain_type"
    return hint


def _build_object_render_hints(object_types_catalog: dict[str, Any]) -> dict[str, Any]:
    object_types = _dict(object_types_catalog.get("types"))
    hints = {
        object_type: _object_render_hint(object_type, _dict(definition))
        for object_type, definition in sorted(object_types.items())
        if isinstance(object_type, str)
    }
    return {
        "schema_version": OBJECT_RENDER_HINTS_SCHEMA_VERSION,
        "kind": "object_render_hints",
        "hints": hints,
        "fallback": {
            "render_mode": "sprite",
            "visual_group": "objects/unknown",
            "draw_layer": "objects_below_actor",
            "anchor": "bottom_center",
            "variant_policy": "stable_by_instance_id",
        },
    }


def _object_render_hint(object_type: str, definition: dict[str, Any]) -> dict[str, Any]:
    tags = set(_string_list(definition.get("tags")))
    height = definition.get("height")
    role = definition.get("role")
    visual_group = f"objects/{object_type}"
    draw_layer = "objects_below_actor"
    anchor = "bottom_center"
    render_mode = "sprite"

    if "below_floor" in tags or definition.get("elevation") == -1:
        draw_layer = "terrain_overlays"
        anchor = "center"
    elif height in {2, 3} or "landmark" in tags:
        draw_layer = "objects_above_actor"
    elif "loot" in tags or "interactive" in tags:
        draw_layer = "objects_below_actor"
    elif role == "soft_cover":
        draw_layer = "objects_below_actor"

    if "explosive" in tags:
        visual_group = f"objects/hazard/{object_type}"
    elif "loot" in tags:
        visual_group = f"objects/loot/{object_type}"
    elif "cover" in tags:
        visual_group = f"objects/cover/{object_type}"

    return {
        "render_mode": render_mode,
        "visual_group": visual_group,
        "draw_layer": draw_layer,
        "anchor": anchor,
        "variant_policy": "stable_by_instance_id",
        "orientation_source": "orientation",
        "footprint_source": "footprint",
    }

def _build_tile_types_catalog(
    *,
    tile_legend: dict[str, Any],
    movement_costs: dict[str, Any],
    collision: dict[str, Any],
) -> dict[str, Any]:
    blocked_types = set(_string_list(collision.get("blocked_tile_types")))
    passable_types = set(_string_list(collision.get("passable_tile_types")))
    costs_by_type = _movement_costs_by_type(movement_costs, tile_legend)
    types: dict[str, Any] = {}
    for symbol, raw_type in sorted(tile_legend.items()):
        if not isinstance(symbol, str) or not isinstance(raw_type, str):
            continue
        collision_value = "blocked" if raw_type in blocked_types else "passable"
        if raw_type not in passable_types and raw_type not in blocked_types:
            collision_value = "unknown"
        types[raw_type] = {
            "symbol": symbol,
            "movement_cost": costs_by_type.get(raw_type),
            "collision": collision_value,
            "walkable": collision_value == "passable",
            "tags": _tile_type_tags(raw_type),
        }
    return {
        "schema_version": TILE_TYPES_CATALOG_SCHEMA_VERSION,
        "kind": "tile_types",
        "types": types,
    }


def _tile_type_tags(tile_type: str) -> list[str]:
    tags: set[str] = set()
    if "blocker" in tile_type:
        tags.add("blocker")
    if "slow" in tile_type:
        tags.add("slow")
    if "road" in tile_type:
        tags.add("road")
    if "water" in tile_type:
        tags.add("water")
    if "ruin" in tile_type:
        tags.add("ruin")
    if "decor" in tile_type or "flower" in tile_type or "mushroom" in tile_type:
        tags.add("decor")
    if "tree" in tile_type or "bush" in tile_type:
        tags.add("vegetation")
    if tile_type in {"start", "goal"}:
        tags.add("marker")
    if not tags:
        tags.add("terrain")
    return sorted(tags)


def _build_object_types_catalog(objects: list[Any]) -> dict[str, Any]:
    type_map: dict[str, dict[str, Any]] = {}
    for item in objects:
        if not isinstance(item, dict):
            continue
        object_type = item.get("type")
        if not isinstance(object_type, str) or not object_type:
            continue
        entry = type_map.setdefault(
            object_type,
            {
                "role": item.get("role"),
                "cover_type": item.get("cover_type"),
                "height": item.get("height"),
                "elevation": item.get("elevation"),
                "blocks_movement": item.get("blocks_movement"),
                "blocks_projectiles": item.get("blocks_projectiles"),
                "blocks_vision": item.get("blocks_vision"),
                "interactive": item.get("interactive"),
                "collision_profile": item.get("collision_profile"),
                "combat_properties": item.get("combat_properties"),
                "tags": sorted(_object_tags(item)),
                "instance_count": 0,
            },
        )
        entry["instance_count"] = int(entry["instance_count"]) + 1
        entry["tags"] = sorted(set(_string_list(entry.get("tags"))) | _object_tags(item))
    return {
        "schema_version": OBJECT_TYPES_CATALOG_SCHEMA_VERSION,
        "kind": "object_types",
        "types": dict(sorted(type_map.items())),
    }


def _object_tags(item: dict[str, Any]) -> set[str]:
    tags = set(_string_list(item.get("tags")))
    role = item.get("role")
    if isinstance(role, str) and role:
        tags.add(role)
    cover_type = item.get("cover_type")
    if isinstance(cover_type, str) and cover_type and cover_type != "none":
        tags.add("cover")
    combat_properties = _dict(item.get("combat_properties"))
    if combat_properties.get("explosive") is True:
        tags.add("explosive")
    if combat_properties.get("loot") is True:
        tags.add("loot")
    if item.get("interactive") is True:
        tags.add("interactive")
    if item.get("blocks_movement") is True:
        tags.add("movement_blocker")
    return tags

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


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
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
