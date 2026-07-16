from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Any


TREE_TERRAIN = "tree_blocker"
TREE_VISIBLE_CODE = "T"
TREE_HIDDEN_CODE = "."
THINNING_START_LEVEL = 9
TREELESS_LEVEL = 18


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
) -> VegetationVisualResult:
    """Build a visual tree mask without changing gameplay blocking.

    Args:
        terrain_rows: Semantic terrain rows.
        elevation_rows: Final integer elevation rows.
        slope_rows: Final local slope rows.
        seed: Resolved deterministic world seed.

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
    by_level: dict[int, dict[str, int]] = {}

    for y, terrain_row in enumerate(terrain_rows):
        output_row: list[str] = []
        for x, terrain in enumerate(terrain_row):
            if terrain != TREE_TERRAIN:
                output_row.append(TREE_HIDDEN_CODE)
                continue

            tree_before += 1
            level = _grid_value(elevation_rows, x=x, y=y)
            slope = _grid_value(slope_rows, x=x, y=y)
            level_stats = by_level.setdefault(level, {"before": 0, "after": 0, "removed": 0})
            level_stats["before"] += 1

            keep_probability = _tree_keep_probability(level=level, slope=slope)
            keep = _stable_unit(seed=seed, x=x, y=y) < keep_probability
            if keep:
                output_row.append(TREE_VISIBLE_CODE)
                tree_after += 1
                level_stats["after"] += 1
            else:
                output_row.append(TREE_HIDDEN_CODE)
                level_stats["removed"] += 1
                if level >= TREELESS_LEVEL or level > THINNING_START_LEVEL:
                    removed_by_altitude += 1
                elif slope > 1:
                    removed_by_slope += 1
        output_rows.append("".join(output_row))

    report = {
        "schema_version": "vegetation-visual-report-v1",
        "kind": "vegetation_visual",
        "rules": {
            "tree_terrain": TREE_TERRAIN,
            "thinning_start_level": THINNING_START_LEVEL,
            "treeless_level": TREELESS_LEVEL,
            "slope_penalty_per_level": 0.12,
            "gameplay_collision_unchanged": True,
            "deterministic_by_seed_and_coordinate": True,
        },
        "summary": {
            "tree_tiles_before": tree_before,
            "tree_tiles_after": tree_after,
            "tree_tiles_removed": tree_before - tree_after,
            "removed_percent": _percent(tree_before - tree_after, tree_before),
            "removed_by_altitude": removed_by_altitude,
            "removed_by_slope": removed_by_slope,
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
        },
        "rows": output_rows,
    }
    return VegetationVisualResult(rows=output_rows, report=report)


def _tree_keep_probability(*, level: int, slope: int) -> float:
    if level >= TREELESS_LEVEL:
        return 0.0
    if level <= THINNING_START_LEVEL:
        altitude_probability = 1.0
    else:
        span = TREELESS_LEVEL - THINNING_START_LEVEL
        altitude_probability = (TREELESS_LEVEL - level) / span
    slope_penalty = max(0, slope - 1) * 0.12
    return max(0.0, min(1.0, altitude_probability - slope_penalty))


def _stable_unit(*, seed: int, x: int, y: int) -> float:
    payload = f"{seed}:{x}:{y}:visual-tree".encode("ascii")
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
