from __future__ import annotations

from typing import Any

RUIN_WALL_SYMBOL = "#"


def analyze_ruin_wall_provenance(
    *,
    rows: list[str],
    ruin_sites: Any,
    fortress_plan: Any = None,
) -> dict[str, Any]:
    """Report whether ruin-wall tiles belong to planned building footprints.

    Args:
        rows: Final semantic terrain rows.
        ruin_sites: Optional ruin-site planner metadata.
        fortress_plan: Optional fortress materialization metadata.

    Returns:
        JSON-serializable provenance report.
    """
    planned_points = _planned_building_points(ruin_sites)
    ruin_wall_points = {
        (x, y)
        for y, row in enumerate(rows)
        for x, symbol in enumerate(row)
        if symbol == RUIN_WALL_SYMBOL
    }
    fortress_points = _fortress_wall_points(fortress_plan)
    ruin_wall_points -= fortress_points
    outside = sorted(
        ruin_wall_points - planned_points,
        key=lambda point: (point[1], point[0]),
    )
    inside_count = len(ruin_wall_points) - len(outside)
    return {
        "schema_version": "ruin-wall-provenance-v1",
        "kind": "ruin_wall_provenance",
        "policy": {
            "ruin_wall_symbol": RUIN_WALL_SYMBOL,
            "allowed_source": "planned_ruin_building_footprint",
            "connectivity_repairs_may_create_ruin_walls": False,
            "vegetation_reconciliation_may_create_ruin_walls": False,
        },
        "summary": {
            "total_ruin_wall_tiles": len(ruin_wall_points),
            "inside_planned_buildings": inside_count,
            "outside_planned_buildings": len(outside),
            "fortress_wall_tiles_excluded": len(fortress_points),
            "artificial_connectivity_blockers_created": 0,
        },
        "outside_points": [
            {"x": x, "y": y}
            for x, y in outside[:128]
        ],
        "outside_points_truncated": len(outside) > 128,
    }


def _planned_building_points(ruin_sites: Any) -> set[tuple[int, int]]:
    if not isinstance(ruin_sites, dict):
        return set()
    sites = ruin_sites.get("sites")
    if not isinstance(sites, list):
        return set()

    points: set[tuple[int, int]] = set()
    for site in sites:
        if not isinstance(site, dict):
            continue
        buildings = site.get("buildings")
        if not isinstance(buildings, list):
            continue
        for building in buildings:
            if not isinstance(building, dict):
                continue
            rect = building.get("rect")
            if not isinstance(rect, dict):
                continue
            try:
                left = int(rect["left"])
                top = int(rect["top"])
                right = int(rect["right"])
                bottom = int(rect["bottom"])
            except (KeyError, TypeError, ValueError):
                continue
            if left > right or top > bottom:
                continue
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    points.add((x, y))
    return points


def _fortress_wall_points(fortress_plan: Any) -> set[tuple[int, int]]:
    if not isinstance(fortress_plan, dict):
        return set()
    materialization = fortress_plan.get("materialization")
    if not isinstance(materialization, dict):
        return set()
    entries = materialization.get("structure_heights")
    if not isinstance(entries, list):
        return set()
    points: set[tuple[int, int]] = set()
    for item in entries:
        if (
            isinstance(item, list)
            and len(item) == 3
            and isinstance(item[0], int)
            and isinstance(item[1], int)
        ):
            points.add((item[0], item[1]))
    return points
