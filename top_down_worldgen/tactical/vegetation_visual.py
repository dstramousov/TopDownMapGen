from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from hashlib import blake2b
from typing import Any

from .environment_context import build_forest_depth_rows
from .traversal import DEFAULT_TRAVERSAL_RULES


TREE_TERRAIN = "tree_blocker"
TREE_VISIBLE_CODE = "T"
TREE_HIDDEN_CODE = "."
SHORE_REED_VISIBLE_CODE = "R"
PUDDLE_REED_VISIBLE_CODE = "P"
RECLAIMED_BUSH_VISIBLE_CODE = "B"
THINNING_START_LEVEL = 9
TREELESS_LEVEL = 18
FOREST_EDGE_DEPTH = 4
FOREST_EDGE_KEEP_PROBABILITY = {1: 0.30, 2: 0.55, 3: 0.80, 4: 1.0}


@dataclass(frozen=True, slots=True)
class VegetationVisualResult:
    """Deterministic visual vegetation mask and diagnostics."""

    rows: list[str]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VegetationCollisionResult:
    """Terrain and visual rows reconciled with final connectivity."""

    rows: list[str]
    visual_rows: list[str]
    report: dict[str, Any]


def build_visual_vegetation(
    *,
    terrain_rows: list[list[str]],
    elevation_rows: list[list[int]],
    slope_rows: list[list[int]],
    seed: int,
    shore_reed_density: float = 0.45,
    puddle_reed_density: float = 0.20,
    reclaimed_edge_bush_density: float = 0.55,
    reclaimed_altitude_bush_density: float = 0.30,
    reclaimed_bush_max_elevation: int = 17,
) -> VegetationVisualResult:
    """Build a visual tree mask without changing gameplay blocking.

    Args:
        terrain_rows: Semantic terrain rows.
        elevation_rows: Final integer elevation rows.
        slope_rows: Final local slope rows.
        seed: Resolved deterministic world seed.
        shore_reed_density: Base probability for shore reeds on level -1.
        puddle_reed_density: Base probability for reeds in legacy puddles.
        reclaimed_edge_bush_density: Probability of bushes on cleared forest edges.
        reclaimed_altitude_bush_density: Probability of bushes after altitude thinning.
        reclaimed_bush_max_elevation: Highest elevation that may contain reclaimed bushes.

    Returns:
        Visual tree mask and thinning diagnostics.
    """
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if height else 0
    output_rows: list[str] = []
    tree_before = 0
    tree_after = 0
    removed_by_altitude = 0
    removed_by_slope = 0
    removed_by_lowland = 0
    removed_by_forest_edge = 0
    shore_reeds_visible = 0
    puddle_reeds_visible = 0
    reclaimed_edge_bushes = 0
    reclaimed_altitude_bushes = 0
    by_level: dict[int, dict[str, int]] = {}
    forest_edge_depths = build_forest_depth_rows(terrain_rows)

    for y, terrain_row in enumerate(terrain_rows):
        output_row: list[str] = []
        for x, terrain in enumerate(terrain_row):
            level = _grid_value(elevation_rows, x=x, y=y)
            slope = _grid_value(slope_rows, x=x, y=y)
            if terrain == "water_slow":
                if level == -1:
                    probability = _reed_probability(
                        elevation_rows=elevation_rows,
                        x=x,
                        y=y,
                        base_density=shore_reed_density,
                    )
                    code = SHORE_REED_VISIBLE_CODE
                    salt = "shore_reed"
                else:
                    probability = puddle_reed_density
                    code = PUDDLE_REED_VISIBLE_CODE
                    salt = "puddle_reed"
                if _stable_unit(seed=seed, x=x, y=y, salt=salt) < probability:
                    output_row.append(code)
                    if code == SHORE_REED_VISIBLE_CODE:
                        shore_reeds_visible += 1
                    else:
                        puddle_reeds_visible += 1
                else:
                    output_row.append(TREE_HIDDEN_CODE)
                continue
            if terrain != TREE_TERRAIN:
                output_row.append(TREE_HIDDEN_CODE)
                continue

            tree_before += 1
            level_stats = by_level.setdefault(level, {"before": 0, "after": 0, "removed": 0})
            level_stats["before"] += 1

            altitude_probability = _tree_keep_probability(level=level, slope=slope)
            edge_depth = forest_edge_depths[y][x]
            edge_probability = _forest_edge_keep_probability(edge_depth)
            keep_probability = min(altitude_probability, edge_probability)
            keep = _stable_unit(seed=seed, x=x, y=y) < keep_probability
            if keep:
                output_row.append(TREE_VISIBLE_CODE)
                tree_after += 1
                level_stats["after"] += 1
            else:
                level_stats["removed"] += 1
                removal_reason = _tree_removal_reason(
                    level=level,
                    slope=slope,
                    altitude_probability=altitude_probability,
                    edge_probability=edge_probability,
                )
                bush_probability = _reclaimed_bush_probability(
                    removal_reason=removal_reason,
                    level=level,
                    slope=slope,
                    edge_density=reclaimed_edge_bush_density,
                    altitude_density=reclaimed_altitude_bush_density,
                    max_elevation=reclaimed_bush_max_elevation,
                )
                if _stable_unit(seed=seed, x=x, y=y, salt="reclaimed_bush") < bush_probability:
                    output_row.append(RECLAIMED_BUSH_VISIBLE_CODE)
                    if removal_reason == "forest_edge":
                        reclaimed_edge_bushes += 1
                    else:
                        reclaimed_altitude_bushes += 1
                else:
                    output_row.append(TREE_HIDDEN_CODE)

                if removal_reason == "lowland":
                    removed_by_lowland += 1
                elif removal_reason == "forest_edge":
                    removed_by_forest_edge += 1
                elif removal_reason == "altitude":
                    removed_by_altitude += 1
                elif removal_reason == "slope":
                    removed_by_slope += 1
        output_rows.append("".join(output_row))

    report = {
        "schema_version": "vegetation-visual-report-v7",
        "kind": "vegetation_visual",
        "rules": {
            "tree_terrain": TREE_TERRAIN,
            "thinning_start_level": THINNING_START_LEVEL,
            "treeless_level": TREELESS_LEVEL,
            "slope_penalty_per_level": 0.12,
            "gameplay_collision_unchanged": True,
            "lowland_tree_levels": [-5, -4, -3, -2, -1],
            "shore_reed_level": -1,
            "shore_reed_density": shore_reed_density,
            "puddle_reed_density": puddle_reed_density,
            "reclaimed_edge_bush_density": reclaimed_edge_bush_density,
            "reclaimed_altitude_bush_density": reclaimed_altitude_bush_density,
            "reclaimed_bush_max_elevation": reclaimed_bush_max_elevation,
            "deterministic_by_seed_and_coordinate": True,
            "forest_edge_depth_tiles": FOREST_EDGE_DEPTH,
            "forest_edge_keep_probability": {
                str(depth): probability
                for depth, probability in FOREST_EDGE_KEEP_PROBABILITY.items()
            },
        },
        "summary": {
            "report_stage": "after_thinning",
            "tree_tiles_before": tree_before,
            "tree_tiles_after_thinning": tree_after,
            "tree_tiles_removed_by_thinning": tree_before - tree_after,
            "removed_by_thinning_percent": _percent(
                tree_before - tree_after, tree_before
            ),
            "tree_tiles_after": tree_after,
            "tree_tiles_removed": tree_before - tree_after,
            "removed_percent": _percent(tree_before - tree_after, tree_before),
            "removed_by_altitude": removed_by_altitude,
            "removed_by_slope": removed_by_slope,
            "removed_by_lowland": removed_by_lowland,
            "removed_by_forest_edge": removed_by_forest_edge,
            "shore_reeds_visible": shore_reeds_visible,
            "puddle_reeds_visible": puddle_reeds_visible,
            "reeds_visible": shore_reeds_visible + puddle_reeds_visible,
            "reclaimed_edge_bushes_visible": reclaimed_edge_bushes,
            "reclaimed_altitude_bushes_visible": reclaimed_altitude_bushes,
            "reclaimed_bushes_visible": reclaimed_edge_bushes + reclaimed_altitude_bushes,
            "trees_at_or_above_treeless_level": 0,
        },
        "by_level": {
            str(level): {
                **stats,
                "retained_percent": _percent(stats["after"], stats["before"]),
            }
            for level, stats in sorted(by_level.items())
        },
        "legend": {
            TREE_VISIBLE_CODE: "visible_tree",
            TREE_HIDDEN_CODE: "no_visual_tree",
            SHORE_REED_VISIBLE_CODE: "shore_reed",
            PUDDLE_REED_VISIBLE_CODE: "puddle_reed",
            RECLAIMED_BUSH_VISIBLE_CODE: "reclaimed_bush",
        },
        "rows": output_rows,
    }
    return VegetationVisualResult(rows=output_rows, report=report)


def finalize_vegetation_visual_report(
    *,
    report: dict[str, Any],
    visual_rows: list[str],
    collision_report: dict[str, Any],
) -> dict[str, Any]:
    """Finalize vegetation diagnostics after collision reconciliation.

    Args:
        report: Thinning-stage vegetation visual report.
        visual_rows: Final visual vegetation rows after collision reconciliation.
        collision_report: Collision reconciliation report for the same rows.

    Returns:
        Finalized vegetation visual report whose summary matches ``visual_rows``.

    Raises:
        ValueError: If report counters disagree with the final visual rows.
    """
    output = deepcopy(report)
    summary = output.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("vegetation visual report does not contain a summary")

    tree_before = _required_non_negative_int(summary, "tree_tiles_before")
    tree_after_thinning = _required_non_negative_int(
        summary,
        "tree_tiles_after_thinning",
        fallback_key="tree_tiles_after",
    )
    collision_summary = collision_report.get("summary")
    if not isinstance(collision_summary, dict):
        raise ValueError("vegetation collision report does not contain a summary")
    restored = _required_non_negative_int(
        collision_summary,
        "rejected_as_visible_tree",
    )

    final_tree_tiles = sum(row.count(TREE_VISIBLE_CODE) for row in visual_rows)
    expected_final_tree_tiles = tree_after_thinning + restored
    if final_tree_tiles != expected_final_tree_tiles:
        raise ValueError(
            "final vegetation tree count does not match thinning plus restored trees"
        )
    if final_tree_tiles > tree_before:
        raise ValueError("final vegetation tree count exceeds original forest tiles")

    removed_by_thinning = tree_before - tree_after_thinning
    removed_final = tree_before - final_tree_tiles
    summary.update(
        {
            "report_stage": "final_after_collision_reconciliation",
            "tree_tiles_after_thinning": tree_after_thinning,
            "tree_tiles_removed_by_thinning": removed_by_thinning,
            "removed_by_thinning_percent": _percent(
                removed_by_thinning,
                tree_before,
            ),
            "tree_tiles_restored_after_collision_reconciliation": restored,
            "tree_tiles_after": final_tree_tiles,
            "tree_tiles_final": final_tree_tiles,
            "tree_tiles_removed": removed_final,
            "tree_tiles_removed_final": removed_final,
            "removed_percent": _percent(removed_final, tree_before),
            "removed_final_percent": _percent(removed_final, tree_before),
        }
    )
    output["schema_version"] = "vegetation-visual-report-v7"
    output["rows"] = list(visual_rows)
    return output


def reconcile_tree_collision(
    *,
    rows: list[str],
    visual_rows: list[str],
    elevation_rows: list[list[int]] | None = None,
) -> VegetationCollisionResult:
    """Open visible clearings and reject isolated gameplay pockets.

    Args:
        rows: Final semantic ASCII terrain after hydrology.
        visual_rows: Visual vegetation mask generated from the same terrain.
        elevation_rows: Final elevation grid. When supplied, opened tree tiles
            outside the largest 3D-traversable component are blocked again.

    Returns:
        Reconciled terrain rows, visual rows, and diagnostics.

    Raises:
        ValueError: If terrain, visual, or elevation dimensions differ.
    """
    width, height = _validate_matching_rows(rows, visual_rows)
    if elevation_rows is not None:
        _validate_elevation_rows(elevation_rows, width=width, height=height)

    opened_rows = [list(row) for row in rows]
    output_visual = [list(row) for row in visual_rows]
    opened_points: set[tuple[int, int]] = set()
    retained_visible_tree_tiles = 0
    retained_non_tree_tiles = 0
    opened_as_grass = 0
    opened_as_reclaimed_bush = 0

    for y, chars in enumerate(opened_rows):
        for x, symbol in enumerate(chars):
            if symbol != "T":
                retained_non_tree_tiles += 1
                continue
            if output_visual[y][x] == TREE_VISIBLE_CODE:
                retained_visible_tree_tiles += 1
                continue
            if output_visual[y][x] == RECLAIMED_BUSH_VISIBLE_CODE:
                chars[x] = "b"
                opened_as_reclaimed_bush += 1
            else:
                chars[x] = "+"
                opened_as_grass += 1
            opened_points.add((x, y))

    reopened_points = set(opened_points)
    rejected_points: set[tuple[int, int]] = set()
    rejected_as_tree = 0
    component_count = 0
    primary_component_tiles = 0

    if elevation_rows is not None and opened_points:
        components = _walkable_components(opened_rows, elevation_rows)
        component_count = len(components)
        primary = components[0] if components else set()
        primary_component_tiles = len(primary)
        rejected_points = opened_points - primary
        reopened_points -= rejected_points

        for x, y in rejected_points:
            opened_rows[y][x] = "T"
            output_visual[y][x] = TREE_VISIBLE_CODE
            rejected_as_tree += 1

    opened_as_reclaimed_bush = sum(
        output_visual[y][x] == RECLAIMED_BUSH_VISIBLE_CODE
        for x, y in reopened_points
    )
    opened_as_grass = len(reopened_points) - opened_as_reclaimed_bush
    output_rows = ["".join(row) for row in opened_rows]
    final_visual_rows = ["".join(row) for row in output_visual]
    report = {
        "schema_version": "vegetation-collision-reconciliation-v3",
        "kind": "vegetation_collision_reconciliation",
        "policy": {
            "hidden_tree_tile_becomes": "grass_or_reclaimed_bush_when_connected",
            "reclaimed_bush_gameplay": "walkable_slow_concealment",
            "isolated_opened_tile_becomes": "visible_tree_blocker",
            "artificial_rock_blockers_created": False,
            "primary_component": "largest_final_3d_traversable_component",
            "visible_tree_tile_remains_blocked": True,
            "non_tree_blockers_unchanged": True,
            "elevation_traversal_rules_unchanged": True,
        },
        "summary": {
            "candidate_opened_tree_tiles": len(opened_points),
            "opened_tree_tiles": len(reopened_points),
            "opened_as_grass": opened_as_grass,
            "opened_as_reclaimed_bush": opened_as_reclaimed_bush,
            "rejected_isolated_tiles": len(rejected_points),
            "rejected_as_visible_tree": rejected_as_tree,
            "rejected_as_rock": 0,
            "artificial_rock_blockers_created": 0,
            "retained_visible_tree_tiles": retained_visible_tree_tiles,
            "retained_non_tree_tiles": retained_non_tree_tiles,
            "component_count_after_candidate_opening": component_count,
            "primary_component_tiles": primary_component_tiles,
        },
    }
    return VegetationCollisionResult(
        rows=output_rows,
        visual_rows=final_visual_rows,
        report=report,
    )


def _tree_removal_reason(
    *,
    level: int,
    slope: int,
    altitude_probability: float,
    edge_probability: float,
) -> str:
    """Return the dominant reason why one visual tree was removed."""
    if level < 0:
        return "lowland"
    if edge_probability < altitude_probability:
        return "forest_edge"
    if level >= TREELESS_LEVEL or level > THINNING_START_LEVEL:
        return "altitude"
    if slope > 1:
        return "slope"
    return "forest_edge"


def _required_non_negative_int(
    values: dict[str, Any],
    key: str,
    *,
    fallback_key: str | None = None,
) -> int:
    """Return one required non-negative integer diagnostic value.

    Args:
        values: Diagnostic mapping.
        key: Preferred key.
        fallback_key: Optional compatibility key.

    Returns:
        Validated integer value.

    Raises:
        ValueError: If the value is missing, boolean, non-integer, or negative.
    """
    actual_key = key
    value = values.get(key)
    if value is None and fallback_key is not None:
        actual_key = fallback_key
        value = values.get(fallback_key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"vegetation diagnostic {actual_key!r} must be a non-negative integer"
        )
    return value


def _reclaimed_bush_probability(
    *,
    removal_reason: str,
    level: int,
    slope: int,
    edge_density: float,
    altitude_density: float,
    max_elevation: int,
) -> float:
    """Return bush probability for one cleared tree tile."""
    if level < 0 or level > max_elevation or slope > 1:
        return 0.0
    if removal_reason == "forest_edge":
        return max(0.0, min(edge_density, 1.0))
    if removal_reason == "altitude":
        return max(0.0, min(altitude_density, 1.0))
    return 0.0


def _validate_matching_rows(rows: list[str], visual_rows: list[str]) -> tuple[int, int]:
    if len(rows) != len(visual_rows):
        raise ValueError("terrain and vegetation rows must have equal height")
    width = len(rows[0]) if rows else 0
    for row, visual_row in zip(rows, visual_rows, strict=True):
        if len(row) != width or len(visual_row) != width:
            raise ValueError("terrain and vegetation rows must have equal width")
    return width, len(rows)


def _validate_elevation_rows(
    elevation_rows: list[list[int]],
    *,
    width: int,
    height: int,
) -> None:
    if len(elevation_rows) != height or any(
        len(row) != width for row in elevation_rows
    ):
        raise ValueError("elevation rows must match terrain dimensions")


def _walkable_components(
    rows: list[list[str]],
    elevation_rows: list[list[int]],
) -> list[set[tuple[int, int]]]:
    walkable_symbols = frozenset("+.bfmwcRSG")
    eligible = {
        (x, y)
        for y, row in enumerate(rows)
        for x, symbol in enumerate(row)
        if symbol in walkable_symbols
    }
    seen: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []

    for start in sorted(eligible, key=lambda point: (point[1], point[0])):
        if start in seen:
            continue
        component = {start}
        queue: deque[tuple[int, int]] = deque([start])
        seen.add(start)
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                point = (nx, ny)
                if point in seen or point not in eligible:
                    continue
                if not DEFAULT_TRAVERSAL_RULES.allows_step(
                    int(elevation_rows[y][x]),
                    int(elevation_rows[ny][nx]),
                ):
                    continue
                seen.add(point)
                component.add(point)
                queue.append(point)
        components.append(component)

    components.sort(
        key=lambda component: (
            -len(component),
            min((y, x) for x, y in component),
        )
    )
    return components


def _forest_edge_keep_probability(depth: int) -> float:
    if depth <= 0 or depth >= FOREST_EDGE_DEPTH:
        return 1.0
    return FOREST_EDGE_KEEP_PROBABILITY.get(depth, 1.0)


def _tree_keep_probability(*, level: int, slope: int) -> float:
    if level < 0:
        return 0.0
    if level >= TREELESS_LEVEL:
        return 0.0
    if level <= THINNING_START_LEVEL:
        altitude_probability = 1.0
    else:
        span = TREELESS_LEVEL - THINNING_START_LEVEL
        altitude_probability = (TREELESS_LEVEL - level) / span
    slope_penalty = max(0, slope - 1) * 0.12
    return max(0.0, min(1.0, altitude_probability - slope_penalty))


def _reed_probability(
    *,
    elevation_rows: list[list[int]],
    x: int,
    y: int,
    base_density: float,
) -> float:
    deepest_nearby = -1
    for ny in range(max(0, y - 2), min(len(elevation_rows), y + 3)):
        for nx in range(max(0, x - 2), min(len(elevation_rows[ny]), x + 3)):
            deepest_nearby = min(deepest_nearby, int(elevation_rows[ny][nx]))
    depth_penalty = max(0, -1 - deepest_nearby) * 0.16
    return max(0.0, min(1.0, base_density - depth_penalty))


def _stable_unit(*, seed: int, x: int, y: int, salt: str = "visual-tree") -> float:
    payload = f"{seed}:{x}:{y}:{salt}".encode("ascii")
    digest = blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") / float(1 << 64)


def _grid_value(rows: list[list[int]], *, x: int, y: int) -> int:
    if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
        return int(rows[y][x])
    return 0


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part * 100.0 / total, 3)
