from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Any


TREE_TERRAIN = "tree_blocker"
TREE_VISIBLE_CODE = "T"
TREE_HIDDEN_CODE = "."
REED_VISIBLE_CODE = "R"
THINNING_START_LEVEL = 9
TREELESS_LEVEL = 18
FOREST_EDGE_DEPTH = 4
FOREST_EDGE_KEEP_PROBABILITY = {1: 0.30, 2: 0.55, 3: 0.80, 4: 1.0}


@dataclass(frozen=True, slots=True)
class VegetationVisualResult:
    """Deterministic visual vegetation mask and diagnostics."""

    rows: list[str]
    report: dict[str, Any]


def build_visual_vegetation(
    *,
    terrain_rows: list[list[str]],
    elevation_rows: list[list[int]],
    slope_rows: list[list[int]],
    seed: int,
    reed_density: float = 0.45,
) -> VegetationVisualResult:
    """Build a visual tree mask without changing gameplay blocking.

    Args:
        terrain_rows: Semantic terrain rows.
        elevation_rows: Final integer elevation rows.
        slope_rows: Final local slope rows.
        seed: Resolved deterministic world seed.
        reed_density: Base probability for reeds on level -1.

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
    reeds_visible = 0
    by_level: dict[int, dict[str, int]] = {}
    forest_edge_depths = _forest_edge_depths(terrain_rows)

    for y, terrain_row in enumerate(terrain_rows):
        output_row: list[str] = []
        for x, terrain in enumerate(terrain_row):
            level = _grid_value(elevation_rows, x=x, y=y)
            slope = _grid_value(slope_rows, x=x, y=y)
            if level == -1 and terrain == "water_slow":
                probability = _reed_probability(
                    elevation_rows=elevation_rows,
                    x=x,
                    y=y,
                    base_density=reed_density,
                )
                if _stable_unit(seed=seed, x=x, y=y, salt="reed") < probability:
                    output_row.append(REED_VISIBLE_CODE)
                    reeds_visible += 1
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
                output_row.append(TREE_HIDDEN_CODE)
                level_stats["removed"] += 1
                if level < 0:
                    removed_by_lowland += 1
                elif edge_probability < altitude_probability:
                    removed_by_forest_edge += 1
                elif level >= TREELESS_LEVEL or level > THINNING_START_LEVEL:
                    removed_by_altitude += 1
                elif slope > 1:
                    removed_by_slope += 1
        output_rows.append("".join(output_row))

    report = {
        "schema_version": "vegetation-visual-report-v3",
        "kind": "vegetation_visual",
        "rules": {
            "tree_terrain": TREE_TERRAIN,
            "thinning_start_level": THINNING_START_LEVEL,
            "treeless_level": TREELESS_LEVEL,
            "slope_penalty_per_level": 0.12,
            "gameplay_collision_unchanged": True,
            "lowland_tree_levels": [-5, -4, -3, -2, -1],
            "reed_level": -1,
            "reed_density": reed_density,
            "deterministic_by_seed_and_coordinate": True,
            "forest_edge_depth_tiles": FOREST_EDGE_DEPTH,
            "forest_edge_keep_probability": {
                str(depth): probability
                for depth, probability in FOREST_EDGE_KEEP_PROBABILITY.items()
            },
        },
        "summary": {
            "tree_tiles_before": tree_before,
            "tree_tiles_after": tree_after,
            "tree_tiles_removed": tree_before - tree_after,
            "removed_percent": _percent(tree_before - tree_after, tree_before),
            "removed_by_altitude": removed_by_altitude,
            "removed_by_slope": removed_by_slope,
            "removed_by_lowland": removed_by_lowland,
            "removed_by_forest_edge": removed_by_forest_edge,
            "reeds_visible": reeds_visible,
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
            REED_VISIBLE_CODE: "visible_reed",
        },
        "rows": output_rows,
    }
    return VegetationVisualResult(rows=output_rows, report=report)



def _forest_edge_depths(terrain_rows: list[list[str]]) -> list[list[int]]:
    """Return tree depth from the original forest boundary.

    Args:
        terrain_rows: Semantic terrain rows before visual thinning.

    Returns:
        Per-tile forest depth where edge trees have depth one.
    """
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if height else 0
    depths = [[0 for _ in range(width)] for _ in range(height)]
    frontier: list[tuple[int, int]] = []

    for y, row in enumerate(terrain_rows):
        for x, terrain in enumerate(row):
            if terrain != TREE_TERRAIN:
                continue
            if _touches_non_tree(terrain_rows, x=x, y=y):
                depths[y][x] = 1
                frontier.append((x, y))

    index = 0
    while index < len(frontier):
        x, y = frontier[index]
        index += 1
        depth = depths[y][x]
        if depth >= FOREST_EDGE_DEPTH:
            continue
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= ny < height and 0 <= nx < len(terrain_rows[ny])):
                continue
            if terrain_rows[ny][nx] != TREE_TERRAIN or depths[ny][nx] != 0:
                continue
            depths[ny][nx] = depth + 1
            frontier.append((nx, ny))
    return depths


def _touches_non_tree(terrain_rows: list[list[str]], *, x: int, y: int) -> bool:
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if ny < 0 or ny >= len(terrain_rows):
            return True
        if nx < 0 or nx >= len(terrain_rows[ny]):
            return True
        if terrain_rows[ny][nx] != TREE_TERRAIN:
            return True
    return False


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
