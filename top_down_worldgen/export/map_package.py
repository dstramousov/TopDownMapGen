from __future__ import annotations

from pathlib import Path
from typing import Any

from top_down_worldgen import __version__
from top_down_worldgen.manifest import (
    COLLISION_LAYER_SCHEMA_VERSION,
    ELEVATION_LAYER_SCHEMA_VERSION,
    ELEVATION_MODEL_SCHEMA_VERSION,
    ELEVATION_FEATURES_SCHEMA_VERSION,
    ELEVATION_TRANSITIONS_SCHEMA_VERSION,
    GAMEPLAY_LAYER_SCHEMA_VERSION,
    GAMEPLAY_ZONES_SCHEMA_VERSION,
    MAP_PACKAGE_MAP_SCHEMA_VERSION,
    MAP_PACKAGE_SCHEMA_VERSION,
    MARKERS_SCHEMA_VERSION,
    MOVEMENT_LAYER_SCHEMA_VERSION,
    OBJECT_INSTANCES_SCHEMA_VERSION,
    OBJECT_TYPES_CATALOG_SCHEMA_VERSION,
    OBJECT_RENDER_HINTS_SCHEMA_VERSION,
    RENDER_PROFILE_SCHEMA_VERSION,
    RUNTIME_GRIDS_SCHEMA_VERSION,
    WORLD_GRAPH_SCHEMA_VERSION,
    ROUTES_SCHEMA_VERSION,
    TILE_RENDER_HINTS_SCHEMA_VERSION,
    PLACES_SCHEMA_VERSION,
    START_GOAL_LAYER_SCHEMA_VERSION,
    TERRAIN_LAYER_SCHEMA_VERSION,
    TILE_GRID_LAYER_SCHEMA_VERSION,
    TILE_TYPES_CATALOG_SCHEMA_VERSION,
)
from top_down_worldgen.paths import OutputPaths
from top_down_worldgen.tactical.runtime_objects import (
    MAX_ELEVATION_LEVEL,
    MIN_ELEVATION_LEVEL,
)
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
    generation_tuning: dict[str, Any] | None = None,
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
        generation_tuning: Optional user-facing world density tuning scales.
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

    runtime_objects = _list(runtime_data.get("runtime_objects"))
    markers = _build_markers(
        points=points,
        runtime_objects=runtime_objects,
        width=width,
        height=height,
    )
    runtime_grids = _build_runtime_grids(
        tile_grid=tile_grid,
        movement_costs=movement_costs,
        collision=collision,
        elevation=_dict(runtime_data.get("elevation")),
        runtime_objects=runtime_objects,
        width=width,
        height=height,
    )
    write_json(markers, outputs.map_package_markers)
    write_json(runtime_grids, outputs.map_package_runtime_grids)

    places_items = _list(runtime_data.get("places"))
    world_graph = _build_world_graph(
        points=points,
        markers=markers,
        places=places_items,
        width=width,
        height=height,
    )
    write_json(world_graph, outputs.map_package_world_graph)
    routes = _build_routes(world_graph)
    write_json(routes, outputs.map_package_routes)
    gameplay_zones = _build_gameplay_zones(
        markers=markers,
        places=places_items,
        routes=routes,
        world_graph=world_graph,
        width=width,
        height=height,
    )
    write_json(gameplay_zones, outputs.map_package_gameplay_zones)
    height_grid = _dict(runtime_grids.get("grids")).get("height_grid")
    elevation_model = _build_elevation_model(
        height_grid=height_grid,
        runtime_objects=runtime_objects,
        width=width,
        height=height,
    )
    write_json(elevation_model, outputs.map_package_elevation_model)
    elevation_features = _build_elevation_features_package(
        elevation_model=elevation_model,
        width=width,
        height=height,
    )
    elevation_transitions = _build_elevation_transitions_package(
        elevation_model=elevation_model,
        width=width,
        height=height,
    )
    write_json(elevation_features, outputs.map_package_elevation_features)
    write_json(elevation_transitions, outputs.map_package_elevation_transitions)

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
            "items": runtime_objects,
            "summary": _dict(runtime_data.get("runtime_objects_summary")),
        },
        outputs.map_package_runtime_objects,
    )
    write_json(
        {
            "schema_version": PLACES_SCHEMA_VERSION,
            "kind": "places",
            "items": places_items,
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
    object_types_catalog = _build_object_types_catalog(runtime_objects)
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
            "generation_tuning": generation_tuning or {},
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
            "markers": "markers.json",
            "runtime_grids": "runtime_grids.json",
            "world_graph": "world_graph.json",
            "routes": "routes.json",
            "gameplay_zones": "gameplay_zones.json",
            "elevation_model": "elevation_model.json",
            "elevation_features": "elevation_features.json",
            "elevation_transitions": "elevation_transitions.json",
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
        outputs.map_package_markers,
        outputs.map_package_runtime_grids,
        outputs.map_package_world_graph,
        outputs.map_package_routes,
        outputs.map_package_gameplay_zones,
        outputs.map_package_elevation_model,
        outputs.map_package_elevation_features,
        outputs.map_package_elevation_transitions,
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



def _build_world_graph(
    *,
    points: dict[str, dict[str, int] | None],
    markers: dict[str, Any],
    places: list[Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    """Build a semantic world graph from places and markers.

    Args:
        points: Primary map points extracted from the tile grid.
        markers: Marker package object.
        places: Semantic place objects.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        World graph JSON object.
    """
    nodes: list[dict[str, Any]] = []
    place_nodes: dict[str, dict[str, Any]] = {}
    marker_nodes: dict[str, dict[str, Any]] = {}

    for place in places:
        if not isinstance(place, dict):
            continue
        node = _world_graph_place_node(place)
        if node is None:
            continue
        nodes.append(node)
        place_nodes[node["id"]] = node

    for marker in _list(markers.get("items")):
        if not isinstance(marker, dict):
            continue
        node = _world_graph_marker_node(marker)
        if node is None:
            continue
        nodes.append(node)
        marker_nodes[node["id"]] = node

    edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str]] = set()
    nodes_by_id = {**place_nodes, **marker_nodes}

    _append_declared_place_edges(
        edges=edges,
        edge_keys=edge_keys,
        places=places,
        place_nodes=place_nodes,
    )
    _append_proximity_place_edges(
        edges=edges,
        edge_keys=edge_keys,
        place_nodes=place_nodes,
        width=width,
        height=height,
    )

    start_id = _nearest_marker_node_id(
        marker_nodes,
        marker_type="start",
        fallback=points.get("start"),
    )
    goal_id = _nearest_marker_node_id(
        marker_nodes,
        marker_type="goal",
        fallback=points.get("goal"),
    )
    _append_endpoint_edges(
        edges=edges,
        edge_keys=edge_keys,
        place_nodes=place_nodes,
        marker_nodes=marker_nodes,
        start_id=start_id,
        goal_id=goal_id,
    )

    main_path = _build_main_path(
        start_id=start_id,
        goal_id=goal_id,
        place_nodes=place_nodes,
        marker_nodes=marker_nodes,
        edges=edges,
        edge_keys=edge_keys,
    )
    main_path_nodes = set(_string_list(main_path.get("node_ids")))
    side_paths = _build_side_paths(
        place_nodes=place_nodes,
        marker_nodes=marker_nodes,
        main_path_nodes=main_path_nodes,
        edges=edges,
        edge_keys=edge_keys,
    )
    dead_ends = _build_dead_ends(
        edges=edges,
        place_nodes=place_nodes,
        main_path_nodes=main_path_nodes,
    )
    secret_areas = _build_secret_areas(place_nodes=place_nodes, marker_nodes=marker_nodes)

    return {
        "schema_version": WORLD_GRAPH_SCHEMA_VERSION,
        "kind": "world_graph",
        "graph_version": "v2",
        "coordinate_space": "tile",
        "width": width,
        "height": height,
        "nodes": nodes,
        "edges": edges,
        "main_path": main_path,
        "side_paths": side_paths,
        "dead_ends": dead_ends,
        "secret_areas": secret_areas,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "place_node_count": len(place_nodes),
            "marker_node_count": len(marker_nodes),
            "meaningful_place_count": len(place_nodes),
            "main_path_node_count": len(_string_list(main_path.get("node_ids"))),
            "side_path_count": len(side_paths),
            "dead_end_count": len(dead_ends),
            "secret_area_count": len(secret_areas),
        },
        "quality": _world_graph_quality_summary(
            place_nodes=place_nodes,
            edges=edges,
            side_paths=side_paths,
            dead_ends=dead_ends,
            secret_areas=secret_areas,
            main_path=main_path,
        ),
        "notes": [
            "This graph is a semantic world/navigation contract, not a pathfinding grid.",
            "Edges describe intended location connectivity; use runtime grids for exact movement.",
            "World graph v2 derives proximity and branch edges from meaningful places.",
        ],
    }


def _build_routes(world_graph: dict[str, Any]) -> dict[str, Any]:
    """Build route records from the semantic world graph.

    Args:
        world_graph: World graph package object.

    Returns:
        Route package object.
    """
    nodes_by_id = {
        node["id"]: node
        for node in _list(world_graph.get("nodes"))
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    edges_by_id = {
        edge["id"]: edge
        for edge in _list(world_graph.get("edges"))
        if isinstance(edge, dict) and isinstance(edge.get("id"), str)
    }
    routes: list[dict[str, Any]] = []

    main_path = _dict(world_graph.get("main_path"))
    main_node_ids = _string_list(main_path.get("node_ids"))
    if len(main_node_ids) >= 2:
        routes.append(
            _route_from_nodes(
                route_id="main_road_000",
                route_type="main_road",
                node_ids=main_node_ids,
                edge_ids=_string_list(main_path.get("edge_ids")),
                nodes_by_id=nodes_by_id,
                edges_by_id=edges_by_id,
                source="world_graph.main_path",
                tags=["primary", "guidance"],
            ),
        )

    for index, side_path in enumerate(_list(world_graph.get("side_paths"))):
        if not isinstance(side_path, dict):
            continue
        node_ids = _string_list(side_path.get("node_ids"))
        if not node_ids:
            target = side_path.get("target_place")
            if isinstance(target, str):
                node_ids = [target]
        if not node_ids:
            continue
        requested_type = side_path.get("type")
        route_type = "hidden_path" if requested_type == "hidden_path" else "side_path"
        routes.append(
            _route_from_nodes(
                route_id=f"{route_type}_{index:03d}",
                route_type=route_type,
                node_ids=node_ids,
                edge_ids=[],
                nodes_by_id=nodes_by_id,
                edges_by_id=edges_by_id,
                source="world_graph.side_paths",
                tags=["optional"],
            ),
        )

    for index, edge in enumerate(_list(world_graph.get("edges"))):
        if not isinstance(edge, dict):
            continue
        edge_type = edge.get("type")
        if edge_type not in {"place_connection", "start_connection", "goal_connection"}:
            continue
        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        source_node = nodes_by_id.get(source, {})
        target_node = nodes_by_id.get(target, {})
        danger = max(
            _safe_float(source_node.get("danger_level")),
            _safe_float(target_node.get("danger_level")),
        )
        if danger < 0.45 and edge_type == "place_connection":
            continue
        edge_id = edge.get("id")
        route_type = "patrol_route" if edge_type == "place_connection" else "escape_route"
        routes.append(
            _route_from_nodes(
                route_id=f"{route_type}_{index:03d}",
                route_type=route_type,
                node_ids=[source, target],
                edge_ids=[edge_id] if isinstance(edge_id, str) else [],
                nodes_by_id=nodes_by_id,
                edges_by_id=edges_by_id,
                source="world_graph.edges",
                tags=["ai", "derived"],
            ),
        )

    for index, secret in enumerate(_list(world_graph.get("secret_areas"))):
        if not isinstance(secret, dict):
            continue
        node_id = secret.get("node_id")
        if not isinstance(node_id, str):
            continue
        routes.append(
            _route_from_nodes(
                route_id=f"hidden_path_secret_{index:03d}",
                route_type="hidden_path",
                node_ids=[node_id],
                edge_ids=[],
                nodes_by_id=nodes_by_id,
                edges_by_id=edges_by_id,
                source="world_graph.secret_areas",
                tags=["secret", "optional"],
            ),
        )

    return {
        "schema_version": ROUTES_SCHEMA_VERSION,
        "kind": "routes",
        "coordinate_space": "tile",
        "items": routes,
        "route_types": {
            "main_road": "Primary intended route from start toward goal.",
            "side_path": "Optional branch route to a secondary place.",
            "hidden_path": "Secret or hard-to-notice optional route.",
            "patrol_route": "AI/NPC route derived from risky place connections.",
            "escape_route": "Retreat or exit route derived from start/goal connections.",
        },
        "summary": {
            "total": len(routes),
            "by_type": _count_by_key(routes, "type"),
        },
        "notes": [
            "Routes describe semantic intent, not exact tile-by-tile paths.",
            "Use runtime_grids for exact pathfinding and collision checks.",
        ],
    }


def _build_gameplay_zones(
    *,
    markers: dict[str, Any],
    places: list[Any],
    routes: dict[str, Any],
    world_graph: dict[str, Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    """Build neutral gameplay zones from public world semantics.

    Args:
        markers: Marker package object.
        places: Semantic places.
        routes: Route package object.
        world_graph: World graph package object.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        Gameplay zones package object.
    """
    route_refs_by_node = _route_refs_by_node(routes)
    marker_refs_by_position = _marker_refs_by_position(markers)
    zones: list[dict[str, Any]] = []

    for marker in _list(markers.get("items")):
        if not isinstance(marker, dict):
            continue
        zone = _gameplay_zone_from_marker(
            marker=marker,
            serial=len(zones),
            width=width,
            height=height,
        )
        if zone is not None:
            zones.append(zone)

    graph_node_ids = {
        str(node.get("id"))
        for node in _list(world_graph.get("nodes"))
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    for place in places:
        if not isinstance(place, dict):
            continue
        zone = _gameplay_zone_from_place(
            place=place,
            route_refs_by_node=route_refs_by_node,
            marker_refs_by_position=marker_refs_by_position,
            graph_node_ids=graph_node_ids,
            serial=len(zones),
            width=width,
            height=height,
        )
        if zone is not None:
            zones.append(zone)

    return {
        "schema_version": GAMEPLAY_ZONES_SCHEMA_VERSION,
        "kind": "gameplay_zones",
        "coordinate_space": "tile",
        "width": width,
        "height": height,
        "items": zones,
        "zone_types": {
            "safe_area": "Low-risk player-safe or start area.",
            "encounter_area": "General encounter location.",
            "ambush_area": "Likely surprise or flank encounter location.",
            "loot_area": "Reward-focused area.",
            "boss_area": "High-danger set-piece encounter area.",
            "stealth_area": "Area suited for concealment or bypass gameplay.",
            "traversal_area": "Movement, crossing, obstruction, or route puzzle area.",
            "secret_area": "Optional hidden or high-reward area.",
            "danger_area": "High-risk area without necessarily being a boss fight.",
            "story_area": "Narrative landmark or lore area.",
            "extraction_area": "Goal, exit, or extraction area.",
        },
        "summary": {
            "total": len(zones),
            "by_type": _count_by_key(zones, "type"),
            "linked_place_count": sum(bool(zone.get("linked_places")) for zone in zones),
            "linked_marker_count": sum(bool(zone.get("linked_markers")) for zone in zones),
            "linked_route_count": sum(bool(zone.get("linked_routes")) for zone in zones),
        },
        "notes": [
            "Gameplay zones describe intended gameplay usage of map areas.",
            "Use runtime grids for exact movement, collision, visibility, and cover.",
        ],
    }


def _gameplay_zone_from_marker(
    *,
    marker: dict[str, Any],
    serial: int,
    width: int,
    height: int,
) -> dict[str, Any] | None:
    marker_type = marker.get("type")
    marker_id = marker.get("id")
    position = _mapping_point(marker.get("position"))
    if not isinstance(marker_type, str) or not isinstance(marker_id, str) or position is None:
        return None
    if marker_type == "start":
        zone_type = "safe_area"
        danger_level = 0.0
        loot_level = 0.0
        encounter = "none"
    elif marker_type == "goal":
        zone_type = "extraction_area"
        danger_level = 0.35
        loot_level = 0.0
        encounter = "extraction"
    elif marker_type in {"ammo_cache", "medkit_cache", "loot", "interest_point"}:
        zone_type = "loot_area"
        danger_level = 0.25
        loot_level = 0.75
        encounter = "reward_pickup"
    else:
        return None
    bounds = _bounds_around_point(position, radius=3, width=width, height=height)
    return _gameplay_zone_record(
        zone_id=f"zone_{serial:03d}",
        zone_type=zone_type,
        bounds=bounds,
        entry_points=[{"id": "entry_center", "position": {"x": position[0], "y": position[1]}}],
        exit_points=[{"id": "exit_center", "position": {"x": position[0], "y": position[1]}}],
        linked_places=[],
        linked_routes=[],
        linked_markers=[marker_id],
        danger_level=danger_level,
        loot_level=loot_level,
        recommended_enemy_types=[],
        recommended_encounter=encounter,
        elevation_usage="normal_ground",
        tags=sorted(set(_string_list(marker.get("tags"))) | {marker_type, zone_type}),
    )


def _gameplay_zone_from_place(
    *,
    place: dict[str, Any],
    route_refs_by_node: dict[str, list[str]],
    marker_refs_by_position: dict[tuple[int, int], list[str]],
    graph_node_ids: set[str],
    serial: int,
    width: int,
    height: int,
) -> dict[str, Any] | None:
    place_id = place.get("id")
    if not isinstance(place_id, str):
        return None
    bounds = _normalize_bounds(place.get("bounds"), width=width, height=height)
    if bounds is None:
        center = _mapping_point(place.get("center"))
        if center is None:
            return None
        bounds = _bounds_around_point(center, radius=6, width=width, height=height)
    entrances = _normalize_place_points(place.get("entrances"), key="position")
    if not entrances:
        entrances = _fallback_entry_points(bounds)
    exit_points = entrances[:]
    route_refs = list(route_refs_by_node.get(place_id, [])) if place_id in graph_node_ids else []
    marker_refs = _marker_refs_in_bounds(bounds, marker_refs_by_position)
    zone_type = _gameplay_zone_type_for_place(place)
    danger_level = _clamp01(_safe_float(place.get("danger_level")))
    loot_level = _clamp01(_safe_float(place.get("loot_level")))
    return _gameplay_zone_record(
        zone_id=f"zone_{serial:03d}",
        zone_type=zone_type,
        bounds=bounds,
        entry_points=entrances,
        exit_points=exit_points,
        linked_places=[place_id],
        linked_routes=route_refs,
        linked_markers=marker_refs,
        danger_level=danger_level,
        loot_level=loot_level,
        recommended_enemy_types=_recommended_enemy_types(place, zone_type),
        recommended_encounter=_recommended_encounter(place, zone_type),
        elevation_usage=_elevation_usage_for_place(place, zone_type),
        tags=sorted(
            set(_string_list(place.get("tags")))
            | set(_string_list(place.get("biome_tags")))
            | {zone_type}
        ),
    )


def _gameplay_zone_record(
    *,
    zone_id: str,
    zone_type: str,
    bounds: dict[str, int],
    entry_points: list[dict[str, Any]],
    exit_points: list[dict[str, Any]],
    linked_places: list[str],
    linked_routes: list[str],
    linked_markers: list[str],
    danger_level: float,
    loot_level: float,
    recommended_enemy_types: list[str],
    recommended_encounter: str,
    elevation_usage: str,
    tags: list[str],
) -> dict[str, Any]:
    return {
        "id": zone_id,
        "type": zone_type,
        "bounds": bounds,
        "polygon": _bounds_polygon(bounds),
        "entry_points": entry_points,
        "exit_points": exit_points,
        "linked_places": linked_places,
        "linked_routes": linked_routes,
        "linked_markers": linked_markers,
        "danger_level": danger_level,
        "loot_level": loot_level,
        "recommended_enemy_types": recommended_enemy_types,
        "recommended_encounter": recommended_encounter,
        "elevation_usage": elevation_usage,
        "tags": tags,
    }


def _gameplay_zone_type_for_place(place: dict[str, Any]) -> str:
    place_type = str(place.get("type", ""))
    encounter_type = str(place.get("encounter_type", ""))
    story_role = str(place.get("story_role", ""))
    tags = set(_string_list(place.get("tags"))) | set(_string_list(place.get("biome_tags")))
    danger = _safe_float(place.get("danger_level"))
    loot = _safe_float(place.get("loot_level"))
    if "secret" in tags or story_role == "secret" or loot >= 0.75:
        return "secret_area"
    if loot >= 0.6:
        return "loot_area"
    if danger >= 0.85 or "boss" in tags:
        return "boss_area"
    if place_type in {"forest_obstruction", "swamp_crossing", "blocked_road"}:
        return "traversal_area"
    if place_type in {"bunker_site", "old_defensive_position"}:
        return "encounter_area"
    if "ambush" in encounter_type or "clearing" in place_type:
        return "ambush_area"
    if danger >= 0.7:
        return "danger_area"
    if "story" in tags or story_role not in {"", "None"}:
        return "story_area"
    return "encounter_area"


def _recommended_enemy_types(place: dict[str, Any], zone_type: str) -> list[str]:
    tags = set(_string_list(place.get("tags"))) | set(_string_list(place.get("biome_tags")))
    if zone_type == "safe_area":
        return []
    if "bunker" in tags or "defense" in tags:
        return ["guard", "ranged"]
    if "forest" in tags:
        return ["ambusher", "beast"]
    if "ruins" in tags:
        return ["scavenger", "ranged"]
    if zone_type == "loot_area":
        return ["guard"]
    return []


def _recommended_encounter(place: dict[str, Any], zone_type: str) -> str:
    encounter = place.get("encounter_type")
    if isinstance(encounter, str) and encounter:
        return encounter
    defaults = {
        "ambush_area": "flank_attack",
        "boss_area": "boss_encounter",
        "danger_area": "hazard_encounter",
        "loot_area": "guarded_loot",
        "stealth_area": "avoid_patrol",
        "traversal_area": "navigation_obstacle",
        "secret_area": "secret_discovery",
        "story_area": "story_discovery",
    }
    return defaults.get(zone_type, "generic_encounter")


def _elevation_usage_for_place(place: dict[str, Any], zone_type: str) -> str:
    tags = set(_string_list(place.get("tags"))) | set(_string_list(place.get("biome_tags")))
    place_type = str(place.get("type", ""))
    if "below_floor" in tags or "bunker" in tags:
        return "below_ground_interior"
    if "trench" in tags:
        return "low_ground_cover"
    if place_type in {"watchtower_area", "bunker_site"}:
        return "high_ground_advantage"
    if zone_type in {"ambush_area", "encounter_area"}:
        return "mixed_cover"
    return "normal_ground"


def _route_refs_by_node(routes: dict[str, Any]) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for route in _list(routes.get("items")):
        if not isinstance(route, dict):
            continue
        route_id = route.get("id")
        if not isinstance(route_id, str):
            continue
        for node_id in _string_list(route.get("node_ids")):
            refs.setdefault(node_id, []).append(route_id)
    return refs


def _marker_refs_by_position(markers: dict[str, Any]) -> dict[tuple[int, int], list[str]]:
    refs: dict[tuple[int, int], list[str]] = {}
    for marker in _list(markers.get("items")):
        if not isinstance(marker, dict):
            continue
        marker_id = marker.get("id")
        position = _mapping_point(marker.get("position"))
        if isinstance(marker_id, str) and position is not None:
            refs.setdefault(position, []).append(marker_id)
    return refs


def _marker_refs_in_bounds(
    bounds: dict[str, int],
    marker_refs_by_position: dict[tuple[int, int], list[str]],
) -> list[str]:
    refs: list[str] = []
    min_x = bounds["min_x"]
    min_y = bounds["min_y"]
    max_x = bounds["max_x"]
    max_y = bounds["max_y"]
    for (x, y), marker_refs in marker_refs_by_position.items():
        if min_x <= x <= max_x and min_y <= y <= max_y:
            refs.extend(marker_refs)
    return sorted(set(refs))


def _normalize_place_points(value: Any, *, key: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, item in enumerate(_list(value)):
        if not isinstance(item, dict):
            continue
        position = _mapping_point(item.get(key)) or _mapping_point(item)
        if position is None:
            continue
        point_id = item.get("id") if isinstance(item.get("id"), str) else f"point_{index:03d}"
        points.append({"id": point_id, "position": {"x": position[0], "y": position[1]}})
    return points


def _normalize_bounds(value: Any, *, width: int, height: int) -> dict[str, int] | None:
    bounds = _dict(value)
    try:
        min_x = max(0, min(width - 1, int(bounds["min_x"])))
        min_y = max(0, min(height - 1, int(bounds["min_y"])))
        max_x = max(0, min(width - 1, int(bounds["max_x"])))
        max_y = max(0, min(height - 1, int(bounds["max_y"])))
    except (KeyError, TypeError, ValueError):
        return None
    if min_x > max_x:
        min_x, max_x = max_x, min_x
    if min_y > max_y:
        min_y, max_y = max_y, min_y
    return {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y}


def _bounds_around_point(
    point: tuple[int, int],
    *,
    radius: int,
    width: int,
    height: int,
) -> dict[str, int]:
    x, y = point
    return {
        "min_x": max(0, x - radius),
        "min_y": max(0, y - radius),
        "max_x": min(width - 1, x + radius),
        "max_y": min(height - 1, y + radius),
    }


def _fallback_entry_points(bounds: dict[str, int]) -> list[dict[str, Any]]:
    center_x = round((bounds["min_x"] + bounds["max_x"]) / 2)
    center_y = round((bounds["min_y"] + bounds["max_y"]) / 2)
    return [
        {"id": "entry_north", "position": {"x": center_x, "y": bounds["min_y"]}},
        {"id": "entry_south", "position": {"x": center_x, "y": bounds["max_y"]}},
        {"id": "entry_west", "position": {"x": bounds["min_x"], "y": center_y}},
        {"id": "entry_east", "position": {"x": bounds["max_x"], "y": center_y}},
    ]


def _bounds_polygon(bounds: dict[str, int]) -> list[dict[str, int]]:
    return [
        {"x": bounds["min_x"], "y": bounds["min_y"]},
        {"x": bounds["max_x"], "y": bounds["min_y"]},
        {"x": bounds["max_x"], "y": bounds["max_y"]},
        {"x": bounds["min_x"], "y": bounds["max_y"]},
    ]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


def _route_from_nodes(
    *,
    route_id: str,
    route_type: str,
    node_ids: list[str],
    edge_ids: list[str],
    nodes_by_id: dict[str, dict[str, Any]],
    edges_by_id: dict[str, dict[str, Any]],
    source: str,
    tags: list[str],
) -> dict[str, Any]:
    waypoints = [
        {"x": pos[0], "y": pos[1]}
        for node_id in node_ids
        if (pos := _mapping_point(nodes_by_id.get(node_id, {}).get("position"))) is not None
    ]
    cost_tiles = sum(
        int(edges_by_id[edge_id].get("cost_tiles", 0))
        for edge_id in edge_ids
        if edge_id in edges_by_id and isinstance(edges_by_id[edge_id].get("cost_tiles"), int)
    )
    if cost_tiles <= 0 and len(waypoints) >= 2:
        cost_tiles = sum(
            abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])
            for a, b in zip(waypoints, waypoints[1:], strict=False)
        )
    return {
        "id": route_id,
        "type": route_type,
        "source": source,
        "node_ids": node_ids,
        "edge_ids": edge_ids,
        "waypoints": waypoints,
        "cost_tiles": cost_tiles,
        "bidirectional": route_type != "escape_route",
        "tags": sorted(set(tags + [route_type])),
    }


def _safe_float(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _world_graph_place_node(place: dict[str, Any]) -> dict[str, Any] | None:
    place_id = place.get("id")
    place_type = place.get("type")
    if not isinstance(place_id, str) or not isinstance(place_type, str):
        return None
    position = _mapping_point(place.get("center")) or _bounds_center(place.get("bounds"))
    if position is None:
        return None
    return {
        "id": place_id,
        "type": place_type,
        "node_type": "place",
        "source": "places",
        "place_ref": place_id,
        "position": {"x": position[0], "y": position[1]},
        "bounds": _dict(place.get("bounds")),
        "entrances": _list(place.get("entrances")),
        "danger_level": place.get("danger_level", 0.0),
        "loot_level": place.get("loot_level", 0.0),
        "story_role": place.get("story_role"),
        "encounter_type": place.get("encounter_type"),
        "tags": sorted(set(_string_list(place.get("tags"))) | set(_string_list(place.get("biome_tags")))),
    }


def _world_graph_marker_node(marker: dict[str, Any]) -> dict[str, Any] | None:
    marker_id = marker.get("id")
    marker_type = marker.get("type")
    position = _mapping_point(marker.get("position"))
    if not isinstance(marker_id, str) or not isinstance(marker_type, str) or position is None:
        return None
    node_id = f"marker:{marker_id}"
    return {
        "id": node_id,
        "type": marker_type,
        "node_type": "marker",
        "source": "markers",
        "marker_ref": marker_id,
        "object_ref": marker.get("object_ref"),
        "position": {"x": position[0], "y": position[1]},
        "tags": sorted(set(_string_list(marker.get("tags"))) | {marker_type}),
    }


def _append_world_graph_edge(
    *,
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
    source: str,
    target: str,
    edge_type: str,
    nodes_by_id: dict[str, dict[str, Any]],
) -> None:
    if source == target:
        return
    ordered = tuple(sorted((source, target)))
    key = (ordered[0], ordered[1], edge_type)
    if key in edge_keys:
        return
    source_node = nodes_by_id.get(source)
    target_node = nodes_by_id.get(target)
    if source_node is None or target_node is None:
        return
    distance = _node_distance(source_node, target_node)
    edge_id = f"edge_{len(edges):03d}"
    edges.append(
        {
            "id": edge_id,
            "source": source,
            "target": target,
            "type": edge_type,
            "bidirectional": True,
            "cost_tiles": distance,
        },
    )
    edge_keys.add(key)


def _nearest_marker_node_id(
    marker_nodes: dict[str, dict[str, Any]],
    *,
    marker_type: str,
    fallback: dict[str, int] | None,
) -> str | None:
    for node_id, node in marker_nodes.items():
        if node.get("type") == marker_type:
            return node_id
    if fallback is None:
        return None
    return None


def _nearest_node(
    source: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not candidates:
        return None
    return min(candidates, key=lambda node: _node_distance(source, node))


def _append_declared_place_edges(
    *,
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
    places: list[Any],
    place_nodes: dict[str, dict[str, Any]],
) -> None:
    """Append edges explicitly declared by places."""
    for place in places:
        if not isinstance(place, dict):
            continue
        source = place.get("id")
        if not isinstance(source, str) or source not in place_nodes:
            continue
        for target in _string_list(place.get("connected_places")):
            if target not in place_nodes:
                continue
            _append_world_graph_edge(
                edges=edges,
                edge_keys=edge_keys,
                source=source,
                target=target,
                edge_type="place_connection",
                nodes_by_id=place_nodes,
            )


def _append_proximity_place_edges(
    *,
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
    place_nodes: dict[str, dict[str, Any]],
    width: int,
    height: int,
) -> None:
    """Append semantic place edges based on nearest-neighbour proximity."""
    nodes_by_id = dict(place_nodes)
    nodes = list(place_nodes.values())
    if len(nodes) < 2:
        return
    distance_limit = max(24, (width + height) // 4)
    target_degree = 2 if len(nodes) >= 6 else 1
    degree: dict[str, int] = {node["id"]: 0 for node in nodes if isinstance(node.get("id"), str)}

    for node in sorted(nodes, key=lambda item: str(item.get("id"))):
        node_id = node.get("id")
        if not isinstance(node_id, str):
            continue
        candidates = sorted(
            (
                candidate
                for candidate in nodes
                if candidate is not node and isinstance(candidate.get("id"), str)
            ),
            key=lambda candidate: _node_distance(node, candidate),
        )
        for candidate in candidates:
            target_id = candidate.get("id")
            if not isinstance(target_id, str):
                continue
            if degree.get(node_id, 0) >= target_degree:
                break
            if degree.get(target_id, 0) >= target_degree + 1:
                continue
            distance = _node_distance(node, candidate)
            if distance > distance_limit and degree.get(node_id, 0) > 0:
                continue
            before = len(edges)
            _append_world_graph_edge(
                edges=edges,
                edge_keys=edge_keys,
                source=node_id,
                target=target_id,
                edge_type="proximity_connection",
                nodes_by_id=nodes_by_id,
            )
            if len(edges) > before:
                degree[node_id] = degree.get(node_id, 0) + 1
                degree[target_id] = degree.get(target_id, 0) + 1


def _append_endpoint_edges(
    *,
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
    place_nodes: dict[str, dict[str, Any]],
    marker_nodes: dict[str, dict[str, Any]],
    start_id: str | None,
    goal_id: str | None,
) -> None:
    """Connect start and goal markers to nearby semantic places."""
    all_place_nodes = list(place_nodes.values())
    nodes_by_id = {**place_nodes, **marker_nodes}
    if start_id is not None and all_place_nodes:
        nearest = _nearest_node(marker_nodes[start_id], all_place_nodes)
        if nearest is not None:
            _append_world_graph_edge(
                edges=edges,
                edge_keys=edge_keys,
                source=start_id,
                target=nearest["id"],
                edge_type="start_connection",
                nodes_by_id=nodes_by_id,
            )
    if goal_id is not None and all_place_nodes:
        nearest = _nearest_node(marker_nodes[goal_id], all_place_nodes)
        if nearest is not None:
            _append_world_graph_edge(
                edges=edges,
                edge_keys=edge_keys,
                source=nearest["id"],
                target=goal_id,
                edge_type="goal_connection",
                nodes_by_id=nodes_by_id,
            )
    if start_id is not None and goal_id is not None and not all_place_nodes:
        _append_world_graph_edge(
            edges=edges,
            edge_keys=edge_keys,
            source=start_id,
            target=goal_id,
            edge_type="direct_start_goal_connection",
            nodes_by_id=nodes_by_id,
        )


def _build_main_path(
    *,
    start_id: str | None,
    goal_id: str | None,
    place_nodes: dict[str, dict[str, Any]],
    marker_nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
) -> dict[str, Any]:
    """Build a complete semantic main path and ensure its edges exist."""
    nodes_by_id = {**place_nodes, **marker_nodes}
    if start_id is None or goal_id is None:
        return {"node_ids": [], "edge_ids": [], "complete": False}

    start_node = nodes_by_id[start_id]
    goal_node = nodes_by_id[goal_id]
    main_places = _main_path_place_nodes(
        start_node=start_node,
        goal_node=goal_node,
        place_nodes=place_nodes,
    )
    node_ids = [start_id, *[node["id"] for node in main_places], goal_id]

    for source, target in zip(node_ids, node_ids[1:], strict=False):
        if _find_edge_id(edges=edges, source=source, target=target) is not None:
            continue
        _append_world_graph_edge(
            edges=edges,
            edge_keys=edge_keys,
            source=source,
            target=target,
            edge_type="main_path_connection",
            nodes_by_id=nodes_by_id,
        )
    edge_ids = _edge_ids_for_node_sequence(edges=edges, node_ids=node_ids)
    return {
        "node_ids": node_ids,
        "edge_ids": edge_ids,
        "complete": bool(
            node_ids
            and node_ids[0] == start_id
            and node_ids[-1] == goal_id
            and len(edge_ids) == max(0, len(node_ids) - 1)
        ),
        "description": "Approximate intended semantic route through key places.",
    }


def _main_path_place_nodes(
    *,
    start_node: dict[str, Any],
    goal_node: dict[str, Any],
    place_nodes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select meaningful places ordered along the start-goal corridor."""
    places = list(place_nodes.values())
    if not places:
        return []
    max_count = min(5, max(3, len(places) // 3))
    scored = sorted(
        places,
        key=lambda node: (
            _main_path_place_score(start_node=start_node, goal_node=goal_node, node=node),
            -_safe_float(node.get("danger_level")),
            -_safe_float(node.get("loot_level")),
            str(node.get("id")),
        ),
    )
    selected = scored[:max_count]
    return sorted(
        selected,
        key=lambda node: _node_projection(start_node=start_node, goal_node=goal_node, node=node),
    )


def _main_path_place_score(
    *,
    start_node: dict[str, Any],
    goal_node: dict[str, Any],
    node: dict[str, Any],
) -> float:
    direct = max(1, _node_distance(start_node, goal_node))
    detour = _node_distance(start_node, node) + _node_distance(node, goal_node) - direct
    projection = _node_projection(start_node=start_node, goal_node=goal_node, node=node)
    corridor_penalty = 0.0 if 0.0 <= projection <= 1.0 else direct * 0.5
    interest_bonus = (_safe_float(node.get("danger_level")) + _safe_float(node.get("loot_level"))) * 6.0
    return float(detour) + corridor_penalty - interest_bonus


def _node_projection(
    *,
    start_node: dict[str, Any],
    goal_node: dict[str, Any],
    node: dict[str, Any],
) -> float:
    start_pos = _mapping_point(start_node.get("position")) or (0, 0)
    goal_pos = _mapping_point(goal_node.get("position")) or start_pos
    node_pos = _mapping_point(node.get("position")) or start_pos
    dx = goal_pos[0] - start_pos[0]
    dy = goal_pos[1] - start_pos[1]
    denom = dx * dx + dy * dy
    if denom <= 0:
        return 0.0
    return ((node_pos[0] - start_pos[0]) * dx + (node_pos[1] - start_pos[1]) * dy) / denom


def _edge_ids_for_node_sequence(*, edges: list[dict[str, Any]], node_ids: list[str]) -> list[str]:
    edge_ids: list[str] = []
    for source, target in zip(node_ids, node_ids[1:], strict=False):
        edge_id = _find_edge_id(edges=edges, source=source, target=target)
        if edge_id is not None:
            edge_ids.append(edge_id)
    return edge_ids


def _find_edge_id(*, edges: list[dict[str, Any]], source: str, target: str) -> str | None:
    pair = {source, target}
    for edge in edges:
        if {edge.get("source"), edge.get("target")} == pair:
            edge_id = edge.get("id")
            return edge_id if isinstance(edge_id, str) else None
    return None


def _build_side_paths(
    *,
    place_nodes: dict[str, dict[str, Any]],
    marker_nodes: dict[str, dict[str, Any]],
    main_path_nodes: set[str],
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    """Build branch paths from main-path nodes to optional places."""
    side_paths: list[dict[str, Any]] = []
    nodes_by_id = {**place_nodes, **marker_nodes}
    anchors = [nodes_by_id[node_id] for node_id in main_path_nodes if node_id in nodes_by_id]
    if not anchors:
        anchors = list(marker_nodes.values())
    for node_id, node in sorted(place_nodes.items()):
        if node_id in main_path_nodes:
            continue
        anchor = _nearest_node(node, anchors)
        if anchor is None or not isinstance(anchor.get("id"), str):
            continue
        before = len(edges)
        _append_world_graph_edge(
            edges=edges,
            edge_keys=edge_keys,
            source=anchor["id"],
            target=node_id,
            edge_type="side_path_connection",
            nodes_by_id=nodes_by_id,
        )
        edge_id = _find_edge_id(edges=edges, source=anchor["id"], target=node_id)
        path_type = _side_path_type(node)
        side_paths.append(
            {
                "id": f"side_path_{len(side_paths):03d}",
                "type": path_type,
                "node_ids": [anchor["id"], node_id],
                "edge_ids": [edge_id] if isinstance(edge_id, str) else [],
                "anchor_node": anchor["id"],
                "target_place": node_id,
                "cost_tiles": _node_distance(anchor, node),
                "created_edge": len(edges) > before,
            },
        )
    return side_paths


def _side_path_type(node: dict[str, Any]) -> str:
    tags = set(_string_list(node.get("tags")))
    place_type = node.get("type")
    story_role = node.get("story_role")
    loot_level = _safe_float(node.get("loot_level"))
    danger_level = _safe_float(node.get("danger_level"))
    if place_type == "secret_cache" or story_role == "secret" or "secret" in tags:
        return "hidden_path"
    if loot_level >= 0.65:
        return "loot_side_path"
    if danger_level >= 0.7:
        return "danger_side_path"
    return "side_path"


def _build_dead_ends(
    *,
    edges: list[dict[str, Any]],
    place_nodes: dict[str, dict[str, Any]],
    main_path_nodes: set[str],
) -> list[dict[str, Any]]:
    """Build dead-end descriptors for meaningful place leaves only."""
    degree = {node_id: 0 for node_id in place_nodes}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if isinstance(source, str) and source in degree:
            degree[source] += 1
        if isinstance(target, str) and target in degree:
            degree[target] += 1
    dead_ends: list[dict[str, Any]] = []
    for node_id, node in sorted(place_nodes.items()):
        if node_id in main_path_nodes or degree.get(node_id, 0) > 1:
            continue
        dead_ends.append(
            {
                "id": f"dead_end_{len(dead_ends):03d}",
                "node_id": node_id,
                "degree": degree.get(node_id, 0),
                "reason": _dead_end_reason(node),
            },
        )
    return dead_ends


def _dead_end_reason(node: dict[str, Any]) -> str:
    if _safe_float(node.get("loot_level")) >= 0.65:
        return "reward_leaf_place"
    if node.get("story_role") in {"secret", "story", "landmark"}:
        return "story_leaf_place"
    return "low_connectivity_place"


def _build_secret_areas(
    *,
    place_nodes: dict[str, dict[str, Any]],
    marker_nodes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build secret/reward area records from places and marker nodes."""
    secret_areas: list[dict[str, Any]] = []
    for node_id, node in sorted(place_nodes.items()):
        reason = _secret_area_reason(node)
        if reason is None:
            continue
        secret_areas.append(
            {
                "id": f"secret_area_{len(secret_areas):03d}",
                "node_id": node_id,
                "reason": reason,
            },
        )
    for node_id, node in sorted(marker_nodes.items()):
        tags = set(_string_list(node.get("tags")))
        if not ({"secret", "loot", "cache"} & tags):
            continue
        secret_areas.append(
            {
                "id": f"secret_area_{len(secret_areas):03d}",
                "node_id": node_id,
                "reason": "secret_or_loot_marker",
            },
        )
    return secret_areas


def _secret_area_reason(node: dict[str, Any]) -> str | None:
    tags = set(_string_list(node.get("tags")))
    story_role = node.get("story_role")
    place_type = node.get("type")
    loot_level = _safe_float(node.get("loot_level"))
    if place_type == "secret_cache":
        return "secret_cache_place"
    if "secret" in tags or story_role == "secret":
        return "secret_tag_or_story_role"
    if loot_level >= 0.75:
        return "high_loot_place"
    return None


def _world_graph_quality_summary(
    *,
    place_nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    side_paths: list[dict[str, Any]],
    dead_ends: list[dict[str, Any]],
    secret_areas: list[dict[str, Any]],
    main_path: dict[str, Any],
) -> dict[str, Any]:
    """Return a compact quality summary for graph consumers."""
    place_count = len(place_nodes)
    connected_place_ids: set[str] = set()
    for edge in edges:
        for key in ("source", "target"):
            node_id = edge.get(key)
            if isinstance(node_id, str) and node_id in place_nodes:
                connected_place_ids.add(node_id)
    return {
        "meaningful_places": place_count,
        "connected_meaningful_places": len(connected_place_ids),
        "meaningful_place_coverage": round(
            len(connected_place_ids) / place_count,
            3,
        ) if place_count else 1.0,
        "side_paths": len(side_paths),
        "dead_ends": len(dead_ends),
        "secret_areas": len(secret_areas),
        "main_path_complete": bool(main_path.get("complete")),
        "status": "ok" if bool(main_path.get("complete")) and place_count >= 1 else "warning",
    }


def _node_distance(source: dict[str, Any], target: dict[str, Any]) -> int:
    source_pos = _mapping_point(source.get("position")) or (0, 0)
    target_pos = _mapping_point(target.get("position")) or (0, 0)
    return abs(source_pos[0] - target_pos[0]) + abs(source_pos[1] - target_pos[1])


def _mapping_point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return x, y
    return None


def _bounds_center(value: Any) -> tuple[int, int] | None:
    bounds = _dict(value)
    try:
        min_x = int(bounds["min_x"])
        min_y = int(bounds["min_y"])
        max_x = int(bounds["max_x"])
        max_y = int(bounds["max_y"])
    except (KeyError, TypeError, ValueError):
        return None
    return round((min_x + max_x) / 2), round((min_y + max_y) / 2)


def _build_markers(
    *,
    points: dict[str, dict[str, int] | None],
    runtime_objects: list[Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for marker_type in ("start", "goal"):
        point = points.get(marker_type)
        if point is None:
            continue
        items.append(
            {
                "id": marker_type,
                "type": marker_type,
                "position": point,
                "source": "tile_grid",
                "tags": ["primary", marker_type],
            },
        )
    for item in runtime_objects:
        if not isinstance(item, dict):
            continue
        marker = _marker_from_runtime_object(item, width=width, height=height)
        if marker is not None:
            items.append(marker)
    return {
        "schema_version": MARKERS_SCHEMA_VERSION,
        "kind": "markers",
        "coordinate_space": "tile",
        "items": items,
        "summary": {
            "total": len(items),
            "by_type": _count_by_key(items, "type"),
        },
    }


def _marker_from_runtime_object(
    item: dict[str, Any],
    *,
    width: int,
    height: int,
) -> dict[str, Any] | None:
    marker_type = _runtime_marker_type(item)
    if marker_type is None:
        return None
    point = _runtime_object_anchor(item, width=width, height=height)
    if point is None:
        return None
    object_id = item.get("id")
    tags = sorted(set(_string_list(item.get("tags"))) | {marker_type})
    return {
        "id": f"marker_{object_id}" if isinstance(object_id, str) else marker_type,
        "type": marker_type,
        "position": {"x": point[0], "y": point[1]},
        "source": "runtime_objects",
        "object_ref": object_id,
        "tags": tags,
    }


def _runtime_marker_type(item: dict[str, Any]) -> str | None:
    object_type = item.get("type")
    tags = set(_string_list(item.get("tags")))
    role = item.get("role")
    if object_type in {"ammo_cache", "medkit_cache", "abandoned_backpack"}:
        return "loot"
    if "loot" in tags:
        return "loot"
    if "story_marker" in tags or role in {"story_marker", "story_landmark"}:
        return "story"
    if "landmark" in tags or isinstance(role, str) and "landmark" in role:
        return "point_of_interest"
    if "bunker" in tags:
        return "defensive_point"
    return None


def _build_runtime_grids(
    *,
    tile_grid: list[str],
    movement_costs: dict[str, Any],
    collision: dict[str, Any],
    elevation: dict[str, Any],
    runtime_objects: list[Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    collision_rows = _string_rows(collision.get("rows"), ["0" * width for _ in range(height)])
    movement_grid = _movement_grid_rows(
        tile_grid=tile_grid,
        movement_costs=movement_costs,
        width=width,
        height=height,
    )
    projectile_grid = [list(row) for row in collision_rows]
    vision_grid = [list(row) for row in collision_rows]
    cover_grid = [[0.0 for _ in range(width)] for _ in range(height)]
    concealment_grid = [[0.0 for _ in range(width)] for _ in range(height)]
    height_grid = _height_grid_rows(elevation=elevation, width=width, height=height)

    for item in runtime_objects:
        if not isinstance(item, dict):
            continue
        points = _point_list(item.get("collision_footprint")) or _point_list(item.get("footprint"))
        profile = _dict(item.get("collision_profile"))
        combat = _dict(item.get("combat_properties"))
        for x, y in points:
            if not (0 <= x < width and 0 <= y < height):
                continue
            if profile.get("movement") == "blocked":
                # Collision grid is terrain-derived. Keep object blockers in projectile/vision
                # grids and expose object movement blockers through runtime object footprints.
                pass
            if profile.get("projectiles") == "blocked":
                projectile_grid[y][x] = "1"
            if profile.get("vision") in {"blocked", "soft_blocked"}:
                vision_grid[y][x] = "1"
            cover_grid[y][x] = max(cover_grid[y][x], _float_value(combat.get("cover_value")))
            concealment_grid[y][x] = max(
                concealment_grid[y][x],
                _float_value(combat.get("concealment_value")),
            )
            elevation_level = item.get("interior_elevation", item.get("elevation"))
            if isinstance(elevation_level, int):
                height_grid[y][x] = elevation_level
    return {
        "schema_version": RUNTIME_GRIDS_SCHEMA_VERSION,
        "kind": "runtime_grids",
        "width": width,
        "height": height,
        "coordinate_space": "tile",
        "grids": {
            "movement_grid": {
                "format": "numeric_rows",
                "rows": movement_grid,
            },
            "collision_grid": {
                "format": "boolean_rows",
                "legend": {"0": "passable", "1": "blocked"},
                "rows": collision_rows,
            },
            "projectile_block_grid": {
                "format": "boolean_rows",
                "legend": {"0": "passable", "1": "blocked"},
                "rows": ["".join(row) for row in projectile_grid],
            },
            "vision_block_grid": {
                "format": "boolean_rows",
                "legend": {"0": "passable", "1": "blocked"},
                "rows": ["".join(row) for row in vision_grid],
            },
            "cover_grid": {
                "format": "numeric_rows",
                "rows": _rounded_grid(cover_grid),
            },
            "concealment_grid": {
                "format": "numeric_rows",
                "rows": _rounded_grid(concealment_grid),
            },
            "height_grid": {
                "format": "integer_rows",
                "rows": height_grid,
            },
        },
    }



def _build_elevation_model(
    *,
    height_grid: Any,
    runtime_objects: list[Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    """Build the public elevation model contract.

    Args:
        height_grid: Runtime height grid object or rows.
        runtime_objects: Runtime object instances.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        Elevation model JSON object.
    """
    rows = _height_rows_from_grid(height_grid=height_grid, width=width, height=height)
    level_counts = _count_height_levels(rows)
    features = _elevation_features(runtime_objects)
    transitions = _elevation_transitions(
        rows=rows,
        features=features,
        width=width,
        height=height,
    )
    feature_types = _count_by_key(features, "type")
    transition_connectors = _count_by_key(transitions, "suggested_connector")
    required_feature_types = _required_elevation_feature_types()
    required_levels = set(range(MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL + 1))
    return {
        "schema_version": ELEVATION_MODEL_SCHEMA_VERSION,
        "kind": "elevation_model",
        "coordinate_space": "tile",
        "width": width,
        "height": height,
        "elevation_range": [MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL],
        "levels": _elevation_level_definitions(),
        "transition_types": {
            "ramp": "Smooth walkable elevation transition.",
            "stairs": "Discrete walkable constructed transition.",
            "ladder": "Actor-only vertical transition.",
            "bridge": "Walkable platform crossing over another level.",
            "drop": "One-way or risky descent transition.",
        },
        "v1_completion": {
            "status": "ready_for_consumer_integration",
            "required_levels": [str(level) for level in sorted(required_levels)],
            "levels_present": [str(level) for level in sorted(level_counts)],
            "missing_levels": [
                str(level) for level in sorted(required_levels.difference(level_counts))
            ],
            "required_feature_types": sorted(required_feature_types),
            "feature_types_present": sorted(feature_types),
            "missing_feature_types": sorted(required_feature_types.difference(feature_types)),
            "transition_connectors_present": sorted(transition_connectors),
            "consumer_ready_files": [
                "runtime_grids.height_grid",
                "elevation_model.json",
                "elevation_features.json",
                "elevation_transitions.json",
            ],
        },
        "rules": {
            "movement": {
                "same_level": "allowed_if_collision_grid_allows",
                "down_by_1": "allowed_as_step_down_or_fall_without_damage",
                "down_by_2_or_more": "allowed_as_fall_with_damage",
                "up_by_1": "requires_space_step_up_or_explicit_transition",
                "up_by_2_or_more": "blocked_without_explicit_transition",
                "fall_damage": "max(0, drop_height - 1) * 5",
            },
            "line_of_sight": {
                "same_level": "use_vision_block_grid",
                "higher_to_lower": "allow_if_not_blocked_by_vision_grid",
                "lower_to_higher": "allow_if_target_edge_visible_and_not_blocked",
                "large_delta": "consumer_should_apply_game_specific_rule",
            },
            "projectiles": {
                "same_level": "use_projectile_block_grid",
                "higher_to_lower": "allow_if_projectile_grid_clear",
                "lower_to_higher": "allow_if_projectile_grid_clear_and_cover_rule_allows",
                "through_bridge_or_platform": "consumer_specific",
            },
            "render_order": {
                "primary_sort": "sort_anchor_y_then_elevation_level",
                "below_ground": "draw_as_overlay_or_cutaway",
                "platforms": "draw_after_base_terrain_before_tall_objects",
            },
        },
        "features": features,
        "transitions": transitions,
        "summary": {
            "min_level": min(level_counts) if level_counts else 0,
            "max_level": max(level_counts) if level_counts else 0,
            "levels_present": [str(level) for level in sorted(level_counts)],
            "level_counts": {str(level): count for level, count in sorted(level_counts.items())},
            "feature_count": len(features),
            "transition_count": len(transitions),
            "required_feature_type_count": len(required_feature_types),
            "missing_required_feature_type_count": len(required_feature_types.difference(feature_types)),
            "missing_level_count": len(required_levels.difference(level_counts)),
        },
        "notes": [
            "This model defines elevation semantics for consumers; it is not a physics engine.",
            "Use runtime_grids.height_grid for per-tile heights and this file for meanings/rules.",
            "runtime_grids.height_grid is always written as numeric integer rows, not compact strings.",
            "Open pits/trenches are below-ground walkable cutaways; bunker/underground areas need explicit hatch/door/stairs semantics.",
        ],
    }



def _elevation_level_definitions() -> dict[str, dict[str, str]]:
    """Return public elevation level metadata for the supported range."""
    levels: dict[str, dict[str, str]] = {}
    for level in range(MIN_ELEVATION_LEVEL, MAX_ELEVATION_LEVEL + 1):
        if level <= -2:
            levels[str(level)] = {
                "name": "deep_open_pit",
                "meaning": "Deep open pit, trench, cutaway, or lower outdoor terrain.",
                "movement": "walkable_if_collision_grid_allows; reachable by falling down",
                "visibility": "lower_than_surface",
                "projectiles": "consumer_should_apply_vertical_los_rule",
                "render_role": "deep_cutaway_overlay",
            }
        elif level == -1:
            levels[str(level)] = {
                "name": "below_ground",
                "meaning": "Shallow pit, trench, cutaway, or explicit bunker interior.",
                "movement": "walkable_if_collision_grid_allows; bunker areas require hatch semantics",
                "visibility": "reduced_against_surface",
                "projectiles": "requires_line_of_sight_transition",
                "render_role": "below_floor_overlay",
            }
        elif level == 0:
            levels[str(level)] = {
                "name": "ground",
                "meaning": "Default outdoor ground level.",
                "movement": "normal",
                "visibility": "baseline",
                "projectiles": "baseline",
                "render_role": "terrain_base",
            }
        elif level <= 4:
            levels[str(level)] = {
                "name": "raised_ground",
                "meaning": "Hills, berms, ledges, platforms, and ordinary high ground.",
                "movement": "upward_movement_requires_step_up_or_explicit_transition",
                "visibility": "high_ground",
                "projectiles": "high_ground",
                "render_role": "raised_terrain_overlay",
            }
        else:
            levels[str(level)] = {
                "name": "high_elevation",
                "meaning": "High cliff, mountain, tower, or debug/playground elevation level.",
                "movement": "upward_movement_requires_explicit_transition",
                "visibility": "strong_high_ground",
                "projectiles": "strong_high_ground_or_special_case",
                "render_role": "high_elevation_layer",
            }
    return levels


def _required_elevation_feature_types() -> set[str]:
    return {
        "pit",
        "trench",
        "bunker_interior",
        "raised_berm",
        "hill",
        "bridge",
        "ramp",
        "stairs",
        "platform",
        "tower",
        "special_high_landmark",
    }


def _build_elevation_features_package(
    *,
    elevation_model: dict[str, Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    """Build public elevation feature records.

    Args:
        elevation_model: Elevation model object produced for the package.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        Elevation features package object.
    """
    features = _dict_list(elevation_model.get("features"))
    feature_types = _count_by_key(features, "type")
    required_feature_types = set(_string_list(_dict(elevation_model.get("v1_completion")).get("required_feature_types")))
    return {
        "schema_version": ELEVATION_FEATURES_SCHEMA_VERSION,
        "kind": "elevation_features",
        "coordinate_space": "tile",
        "width": width,
        "height": height,
        "items": features,
        "feature_types": {
            "pit": "Below-ground depression, usually level -1.",
            "trench": "Below-ground defensive or traversal structure, usually level -1.",
            "bunker_interior": "Surface structure with an interior level below ground.",
            "raised_berm": "Raised earthwork or hill-like local feature, usually level +1.",
            "hill": "Raised natural high ground, usually level +1.",
            "bridge": "Raised walkable span crossing an obstacle or lower area, usually level +2.",
            "ramp": "Smooth traversal connector between nearby levels.",
            "stairs": "Discrete traversal connector between nearby levels.",
            "platform": "Constructed or ruin deck high ground, usually level +2.",
            "tower": "Tall landmark or vantage point, usually level +3.",
            "special_high_landmark": "Exceptional high point or scripted landmark, usually level +4.",
            "object_elevation_feature": "Generic object-derived elevation feature.",
        },
        "v1_completion": {
            "required_feature_types": sorted(required_feature_types),
            "feature_types_present": sorted(feature_types),
            "missing_feature_types": sorted(required_feature_types.difference(feature_types)),
        },
        "summary": {
            "total": len(features),
            "by_type": feature_types,
            "below_ground_count": sum(
                1
                for feature in features
                if _feature_level(feature, "interior_elevation") < 0
                or _feature_level(feature, "elevation") < 0
            ),
            "raised_count": sum(
                1
                for feature in features
                if _feature_level(feature, "surface_elevation") > 0
                or _feature_level(feature, "elevation") > 0
            ),
        },
    }


def _build_elevation_transitions_package(
    *,
    elevation_model: dict[str, Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    """Build public elevation transition records.

    Args:
        elevation_model: Elevation model object produced for the package.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        Elevation transitions package object.
    """
    transitions = _dict_list(elevation_model.get("transitions"))
    transition_types = _count_by_key(transitions, "type")
    connector_types = _count_by_key(transitions, "suggested_connector")
    return {
        "schema_version": ELEVATION_TRANSITIONS_SCHEMA_VERSION,
        "kind": "elevation_transitions",
        "coordinate_space": "tile",
        "width": width,
        "height": height,
        "items": transitions,
        "transition_types": {
            "step_down": "Adjacent cells descend to a lower level.",
            "step_up": "Adjacent cells ascend to a higher level.",
            "steep_transition": "Large height delta that needs an explicit connector.",
            "bridge_edge": "Transition involving bridge/platform semantics.",
            "connector_edge": "Transition involving an explicit ramp or stairs connector.",
        },
        "connector_types": {
            "slope": "Natural or earthwork connector for a one-level transition.",
            "ramp": "Explicit ramp connector for a one-level transition.",
            "stairs": "Explicit stairs connector for a one-level transition.",
            "bridge": "Bridge or platform connector for elevated walkable traversal.",
            "ladder_or_scripted": "Recommended connector for larger transitions.",
            "none": "No explicit connector required.",
        },
        "v1_completion": {
            "connectors_present": sorted(connector_types),
            "movement_allowed_count": sum(
                1 for transition in transitions if transition.get("movement_allowed") is True
            ),
            "movement_blocked_count": sum(
                1 for transition in transitions if transition.get("movement_allowed") is False
            ),
            "notes": [
                "Allowed transitions are directly consumable by movement/pathfinding code.",
                "Blocked transitions mark cliffs, drops, or missing connectors for game-specific handling.",
            ],
        },
        "summary": {
            "total": len(transitions),
            "by_type": transition_types,
            "by_connector": connector_types,
            "movement_allowed": sum(
                1 for transition in transitions if transition.get("movement_allowed") is True
            ),
            "movement_blocked": sum(
                1 for transition in transitions if transition.get("movement_allowed") is False
            ),
        },
    }


def _feature_level(feature: dict[str, Any], key: str) -> int:
    value = feature.get(key)
    return value if isinstance(value, int) else 0

def _height_rows_from_grid(*, height_grid: Any, width: int, height: int) -> list[list[int]]:
    grid = _dict(height_grid)
    rows_value = grid.get("rows") if grid else height_grid
    rows: list[list[int]] = []
    if isinstance(rows_value, list):
        for y in range(height):
            source_row = rows_value[y] if y < len(rows_value) else []
            row: list[int] = []
            if isinstance(source_row, list):
                for x in range(width):
                    value = source_row[x] if x < len(source_row) else 0
                    row.append(value if isinstance(value, int) else 0)
            else:
                row = [0 for _ in range(width)]
            rows.append(row)
    if not rows:
        rows = [[0 for _ in range(width)] for _ in range(height)]
    return rows


def _count_height_levels(rows: list[list[int]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in rows:
        for level in row:
            counts[level] = counts.get(level, 0) + 1
    return counts


def _elevation_features(runtime_objects: list[Any]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for item in runtime_objects:
        if not isinstance(item, dict):
            continue
        object_id = item.get("id")
        object_type = item.get("type")
        if not isinstance(object_id, str) or not isinstance(object_type, str):
            continue
        feature_type = _elevation_feature_type(item)
        if feature_type is None:
            continue
        surface = item.get("surface_elevation", item.get("elevation"))
        interior = item.get("interior_elevation")
        elevation = item.get("elevation")
        feature: dict[str, Any] = {
            "id": f"elevation_feature_{len(features):03d}",
            "type": feature_type,
            "object_ref": object_id,
            "object_type": object_type,
            "surface_elevation": surface if isinstance(surface, int) else None,
            "interior_elevation": interior if isinstance(interior, int) else None,
            "elevation": elevation if isinstance(elevation, int) else None,
            "footprint": item.get("footprint", []),
            "transition_hint": _elevation_transition_hint(item),
        }
        if feature_type in {"raised_berm", "hill"}:
            feature["recommended_transition"] = "ramp_or_slope"
        if feature_type in {"bridge", "platform"}:
            feature["recommended_transition"] = "ramp_stairs_or_edge_connector"
        if feature_type in {"ramp", "stairs"}:
            feature["recommended_transition"] = feature_type
        if feature_type == "tower":
            feature["recommended_transition"] = "stairs_ladder_or_scripted"
        if feature_type == "special_high_landmark":
            feature["recommended_transition"] = "scripted_or_blocked"
        if feature_type in {"pit", "trench", "bunker_interior"}:
            feature["recommended_transition"] = "stairs_ramp_or_drop"
        features.append(feature)
    return features


def _elevation_feature_type(item: dict[str, Any]) -> str | None:
    object_type = item.get("type")
    tags = set(_string_list(item.get("tags")))
    elevation = item.get("elevation")
    interior = item.get("interior_elevation")
    surface = item.get("surface_elevation")
    if "bunker" in tags:
        return "bunker_interior"
    if object_type == "trench":
        return "trench"
    if object_type == "pit":
        return "pit"
    if object_type == "earth_berm" or "earthwork" in tags:
        return "raised_berm"
    if object_type == "hill" or "hill" in tags or "raised_ground" in tags:
        return "hill"
    if "bridge" in tags:
        return "bridge"
    if "ramp" in tags:
        return "ramp"
    if "stairs" in tags:
        return "stairs"
    if "platform" in tags:
        return "platform"
    if "special_high_landmark" in tags:
        return "special_high_landmark"
    if "tower" in tags or "high_platform" in tags:
        return "tower"
    if "ladder" in tags:
        return "ladder"
    if isinstance(interior, int) and interior != 0:
        return "object_elevation_feature"
    if isinstance(surface, int) and surface != 0:
        return "object_elevation_feature"
    if isinstance(elevation, int) and elevation != 0:
        return "object_elevation_feature"
    if tags.intersection({"elevation", "below_floor"}):
        return "object_elevation_feature"
    return None


def _elevation_transition_hint(item: dict[str, Any]) -> str | None:
    object_type = item.get("type")
    tags = set(_string_list(item.get("tags")))
    if object_type in {"trench", "pit"}:
        return "drop_or_step_down"
    if "bunker" in tags:
        return "entrance_or_stairs_required"
    if "bridge" in tags:
        return "bridge"
    if "ramp" in tags:
        return "ramp"
    if "stairs" in tags:
        return "stairs"
    if "platform" in tags:
        return "platform"
    if "special_high_landmark" in tags:
        return "special_high_landmark"
    if "tower" in tags or "high_platform" in tags:
        return "tower"
    if "ladder" in tags:
        return "ladder"
    return None


def _elevation_transitions(
    *,
    rows: list[list[int]],
    features: list[dict[str, Any]],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    point_features = _elevation_features_by_point(features)
    for y in range(height):
        for x in range(width):
            level = rows[y][x]
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx >= width or ny >= height:
                    continue
                other = rows[ny][nx]
                if other == level:
                    continue
                _append_elevation_transition(
                    transitions=transitions,
                    source=(x, y),
                    source_level=level,
                    target=(nx, ny),
                    target_level=other,
                    point_features=point_features,
                )
                _append_elevation_transition(
                    transitions=transitions,
                    source=(nx, ny),
                    source_level=other,
                    target=(x, y),
                    target_level=level,
                    point_features=point_features,
                )
    return transitions[:256]


def _append_elevation_transition(
    *,
    transitions: list[dict[str, Any]],
    source: tuple[int, int],
    source_level: int,
    target: tuple[int, int],
    target_level: int,
    point_features: dict[tuple[int, int], list[dict[str, Any]]],
) -> None:
    delta = target_level - source_level
    connector = _elevation_transition_connector(
        source=source,
        target=target,
        delta=delta,
        point_features=point_features,
    )
    transition_type = _elevation_transition_type(delta=delta, connector=connector)
    movement_allowed = _elevation_transition_movement_allowed(
        delta=delta,
        connector=connector,
    )
    drop_height = max(0, -delta)
    requires_step_up = delta == 1
    requires_explicit_transition = delta >= 2
    transitions.append(
        {
            "id": f"elevation_transition_{len(transitions):03d}",
            "type": transition_type,
            "from": {"x": source[0], "y": source[1], "level": source_level},
            "to": {"x": target[0], "y": target[1], "level": target_level},
            "delta": delta,
            "abs_delta": abs(delta),
            "drop_height": drop_height,
            "fall_damage": max(0, drop_height - 1) * 5,
            "requires_step_up": requires_step_up,
            "requires_explicit_transition": requires_explicit_transition,
            "requires_explicit_connector": requires_explicit_transition,
            "suggested_connector": connector,
            "movement_allowed": movement_allowed,
            "movement_rule": _elevation_transition_movement_rule(
                delta=delta,
                connector=connector,
                movement_allowed=movement_allowed,
            ),
            "feature_refs": _transition_feature_refs(
                source=source,
                target=target,
                point_features=point_features,
            ),
        },
    )


def _elevation_features_by_point(
    features: list[dict[str, Any]],
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    by_point: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for feature in features:
        for point in _point_list(feature.get("footprint")):
            point_key = (point[0], point[1])
            by_point.setdefault(point_key, []).append(feature)
    return by_point


def _elevation_transition_connector(
    *,
    source: tuple[int, int],
    target: tuple[int, int],
    delta: int,
    point_features: dict[tuple[int, int], list[dict[str, Any]]],
) -> str:
    feature_types = {
        str(feature.get("type"))
        for feature in point_features.get(source, []) + point_features.get(target, [])
        if isinstance(feature.get("type"), str)
    }
    if "stairs" in feature_types:
        return "stairs"
    if "ramp" in feature_types:
        return "ramp"
    if feature_types.intersection({"bridge", "platform"}):
        return "bridge"
    if feature_types.intersection({"hill", "raised_berm"}) and abs(delta) == 1:
        return "slope"
    if abs(delta) > 1:
        return "ladder_or_scripted"
    return "none"


def _elevation_transition_type(*, delta: int, connector: str) -> str:
    if connector in {"ramp", "stairs"}:
        return "connector_edge"
    if connector == "bridge":
        return "bridge_edge"
    if abs(delta) > 1:
        return "steep_transition"
    return "step_up" if delta > 0 else "step_down"


def _elevation_transition_movement_allowed(*, delta: int, connector: str) -> bool:
    explicit_connectors = {"ramp", "stairs", "bridge"}
    if delta <= 0:
        return True
    if delta == 1:
        return True
    return connector in explicit_connectors


def _elevation_transition_movement_rule(
    *,
    delta: int,
    connector: str,
    movement_allowed: bool,
) -> str:
    if delta < 0:
        drop_height = -delta
        damage = max(0, drop_height - 1) * 5
        return f"allowed_drop_fall_damage_{damage}"
    if delta == 1:
        if connector in {"ramp", "stairs", "bridge"}:
            return f"allowed_up_1_via_{connector}"
        return "allowed_up_1_requires_space_step_up"
    if movement_allowed:
        return f"allowed_up_{delta}_via_explicit_{connector}"
    return "blocked_up_2_or_more_without_explicit_transition"


def _transition_feature_refs(
    *,
    source: tuple[int, int],
    target: tuple[int, int],
    point_features: dict[tuple[int, int], list[dict[str, Any]]],
) -> list[str]:
    refs = {
        str(feature.get("id"))
        for feature in point_features.get(source, []) + point_features.get(target, [])
        if isinstance(feature.get("id"), str)
    }
    return sorted(refs)

def _movement_grid_rows(
    *,
    tile_grid: list[str],
    movement_costs: dict[str, Any],
    width: int,
    height: int,
) -> list[list[int | float | None]]:
    rows: list[list[int | float | None]] = []
    for y in range(height):
        source_row = tile_grid[y] if y < len(tile_grid) else ""
        row: list[int | float | None] = []
        for x in range(width):
            tile = source_row[x] if x < len(source_row) else ""
            value = movement_costs.get(tile)
            row.append(value if isinstance(value, int | float) else None)
        rows.append(row)
    return rows


def _height_grid_rows(
    *,
    elevation: dict[str, Any],
    width: int,
    height: int,
) -> list[list[int]]:
    default_level = elevation.get("default", 0)
    if not isinstance(default_level, int):
        default_level = 0
    rows = [[default_level for _ in range(width)] for _ in range(height)]
    for cell in _list(elevation.get("cells")):
        if not isinstance(cell, dict):
            continue
        x = cell.get("x")
        y = cell.get("y")
        level = cell.get("level")
        if isinstance(x, int) and isinstance(y, int) and isinstance(level, int):
            if 0 <= x < width and 0 <= y < height:
                rows[y][x] = level
    return rows


def _runtime_object_anchor(
    item: dict[str, Any],
    *,
    width: int,
    height: int,
) -> tuple[int, int] | None:
    anchor = item.get("anchor")
    if isinstance(anchor, list) and len(anchor) == 2:
        x, y = anchor
        if isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height:
            return (x, y)
    x = item.get("x")
    y = item.get("y")
    if isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height:
        return (x, y)
    points = _point_list(item.get("footprint"))
    for point_x, point_y in points:
        if 0 <= point_x < width and 0 <= point_y < height:
            return (point_x, point_y)
    return None


def _rounded_grid(rows: list[list[float]]) -> list[list[float]]:
    return [[round(value, 3) for value in row] for row in rows]


def _float_value(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _count_by_key(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = item.get(key)
        if isinstance(value, str):
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


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

    if "bunker" in tags:
        draw_layer = "objects_above_actor"
        anchor = "center"
    elif "below_floor" in tags or definition.get("elevation") == -1:
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
        "collision_footprint_source": "collision_footprint",
        "visual_bounds_source": "visual_bounds",
        "interaction_shape_source": "interaction_shape",
        "sort_anchor_source": "sort_anchor",
        "draw_layer_source": "draw_layer",
        "occlusion_hint_source": "occlusion_hint",
        "firing_ports_source": "firing_ports" if "firing_ports" in tags else None,
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
                "default_footprint": item.get("footprint"),
                "default_collision_footprint": item.get("collision_footprint"),
                "default_visual_bounds": item.get("visual_bounds"),
                "default_pivot": item.get("pivot"),
                "default_interaction_shape": item.get("interaction_shape"),
                "default_sort_anchor": item.get("sort_anchor"),
                "draw_layer": item.get("draw_layer"),
                "occlusion_hint": item.get("occlusion_hint"),
                "default_firing_ports": item.get("firing_ports"),
                "surface_elevation": item.get("surface_elevation"),
                "interior_elevation": item.get("interior_elevation"),
                "tags": sorted(_object_tags(item)),
                "instance_count": 0,
                "max_footprint_tiles": 0,
                "max_collision_footprint_tiles": 0,
            },
        )
        entry["instance_count"] = int(entry["instance_count"]) + 1
        entry["tags"] = sorted(set(_string_list(entry.get("tags"))) | _object_tags(item))
        entry["max_footprint_tiles"] = max(
            int(entry.get("max_footprint_tiles", 0)),
            len(_point_list(item.get("footprint"))),
        )
        entry["max_collision_footprint_tiles"] = max(
            int(entry.get("max_collision_footprint_tiles", 0)),
            len(_point_list(item.get("collision_footprint"))),
        )
    return {
        "schema_version": OBJECT_TYPES_CATALOG_SCHEMA_VERSION,
        "kind": "object_types",
        "types": dict(sorted(type_map.items())),
    }


def _point_list(value: Any) -> list[list[int]]:
    if not isinstance(value, list):
        return []
    points: list[list[int]] = []
    for point in value:
        if (
            isinstance(point, list)
            and len(point) == 2
            and isinstance(point[0], int)
            and isinstance(point[1], int)
        ):
            points.append([point[0], point[1]])
    return points


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


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


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
