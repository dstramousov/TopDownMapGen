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
    """Build a compact graph of semantic world locations.

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

    marker_items = _list(markers.get("items"))
    for marker in marker_items:
        if not isinstance(marker, dict):
            continue
        node = _world_graph_marker_node(marker)
        if node is None:
            continue
        nodes.append(node)
        marker_nodes[node["id"]] = node

    edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str]] = set()
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

    all_place_nodes = list(place_nodes.values())
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
    if start_id is not None and all_place_nodes:
        nearest = _nearest_node(marker_nodes[start_id], all_place_nodes)
        if nearest is not None:
            _append_world_graph_edge(
                edges=edges,
                edge_keys=edge_keys,
                source=start_id,
                target=nearest["id"],
                edge_type="start_connection",
                nodes_by_id={**place_nodes, **marker_nodes},
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
                nodes_by_id={**place_nodes, **marker_nodes},
            )

    node_ids = [node["id"] for node in nodes]
    main_path = _build_main_path(
        start_id=start_id,
        goal_id=goal_id,
        place_nodes=place_nodes,
        marker_nodes=marker_nodes,
        edges=edges,
    )
    main_path_nodes = set(_string_list(main_path.get("node_ids")))
    side_paths = _build_side_paths(place_nodes=place_nodes, main_path_nodes=main_path_nodes)
    dead_ends = _build_dead_ends(edges=edges, node_ids=node_ids, main_path_nodes=main_path_nodes)
    secret_areas = _build_secret_areas(place_nodes=place_nodes)

    return {
        "schema_version": WORLD_GRAPH_SCHEMA_VERSION,
        "kind": "world_graph",
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
            "side_path_count": len(side_paths),
            "dead_end_count": len(dead_ends),
            "secret_area_count": len(secret_areas),
        },
        "notes": [
            "This graph is a semantic world/navigation contract, not a pathfinding grid.",
            "Edges describe intended location connectivity; use runtime grids for exact movement.",
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


def _build_main_path(
    *,
    start_id: str | None,
    goal_id: str | None,
    place_nodes: dict[str, dict[str, Any]],
    marker_nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes_by_id = {**place_nodes, **marker_nodes}
    if start_id is None or goal_id is None:
        return {"node_ids": [], "edge_ids": [], "complete": False}
    ordered_places = sorted(
        place_nodes.values(),
        key=lambda node: _node_distance(nodes_by_id[start_id], node),
    )
    if ordered_places:
        midpoint_goal = nodes_by_id[goal_id]
        ordered_places = sorted(
            ordered_places,
            key=lambda node: (
                _node_distance(nodes_by_id[start_id], node)
                + _node_distance(node, midpoint_goal)
            ),
        )
        # Keep the path compact: start, up to three semantic places, goal.
        node_ids = [start_id, *[node["id"] for node in ordered_places[:3]], goal_id]
    else:
        node_ids = [start_id, goal_id]
    edge_ids = _edge_ids_for_node_sequence(edges=edges, node_ids=node_ids)
    return {
        "node_ids": node_ids,
        "edge_ids": edge_ids,
        "complete": bool(node_ids and node_ids[0] == start_id and node_ids[-1] == goal_id),
        "description": "Approximate intended semantic route through key places.",
    }


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
    main_path_nodes: set[str],
) -> list[dict[str, Any]]:
    side_paths: list[dict[str, Any]] = []
    for node_id, node in sorted(place_nodes.items()):
        if node_id in main_path_nodes:
            continue
        path_type = "side_path"
        tags = set(_string_list(node.get("tags")))
        if node.get("loot_level", 0.0) and float(node.get("loot_level", 0.0)) >= 0.6:
            path_type = "loot_side_path"
        if "hidden" in tags or "secret" in tags:
            path_type = "hidden_path"
        side_paths.append(
            {
                "id": f"side_path_{len(side_paths):03d}",
                "type": path_type,
                "node_ids": [node_id],
                "target_place": node_id,
            },
        )
    return side_paths


def _build_dead_ends(
    *,
    edges: list[dict[str, Any]],
    node_ids: list[str],
    main_path_nodes: set[str],
) -> list[dict[str, Any]]:
    degree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if isinstance(source, str) and source in degree:
            degree[source] += 1
        if isinstance(target, str) and target in degree:
            degree[target] += 1
    return [
        {
            "id": f"dead_end_{index:03d}",
            "node_id": node_id,
            "reason": "single_connection_non_main_path",
        }
        for index, node_id in enumerate(sorted(node_ids))
        if degree.get(node_id, 0) <= 1 and node_id not in main_path_nodes
    ]


def _build_secret_areas(place_nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    secret_areas: list[dict[str, Any]] = []
    for node_id, node in sorted(place_nodes.items()):
        tags = set(_string_list(node.get("tags")))
        story_role = node.get("story_role")
        loot_level = node.get("loot_level")
        if "secret" not in tags and story_role != "secret" and not (
            isinstance(loot_level, int | float) and loot_level >= 0.75
        ):
            continue
        secret_areas.append(
            {
                "id": f"secret_area_{len(secret_areas):03d}",
                "node_id": node_id,
                "reason": "secret_tag_or_high_loot",
            },
        )
    return secret_areas


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
