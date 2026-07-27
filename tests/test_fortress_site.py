from __future__ import annotations

from top_down_worldgen.config import FortressConfig
from top_down_worldgen.tactical.fortress_site import (
    analyze_lake_island_fortress_site,
)


def _enabled_config() -> FortressConfig:
    return FortressConfig.from_raw(
        {
            "enabled": True,
            "archetype": "lake_island",
            "max_count": 1,
            "lake_island": {"enabled": True},
        },
    )


def _lake_grid(*, width: int, height: int, margin: int) -> list[list[int]]:
    rows = [[0 for _ in range(width)] for _ in range(height)]
    for y in range(margin, height - margin):
        for x in range(margin, width - margin):
            rows[y][x] = -3
    return rows


def test_lake_island_site_selects_large_flatland_lake() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=20)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "selected"
    assert report["summary"]["lake_components"] == 1
    assert report["summary"]["eligible_components"] == 1
    selected = report["selected_site"]
    assert selected is not None
    assert selected["planned_fortress_span_tiles"] == 24
    assert selected["planned_island_span_tiles"] == 36
    assert selected["available_water_ring_tiles"] >= 6


def test_lake_island_site_rejects_small_water_component() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=65)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "not_found"
    assert report["summary"]["eligible_components"] == 0
    assert report["selected_site"] is None
    assert report["candidates"][0]["rejection_reasons"] == [
        "area_below_minimum",
    ]


def test_lake_island_site_is_disabled_for_super_flatland() -> None:
    elevation_rows = _lake_grid(width=160, height=160, margin=20)

    report = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="super_flatland",
        fortress_config=_enabled_config(),
    )

    assert report["status"] == "unsupported_elevation_style"
    assert report["summary"]["lake_components"] == 0


def test_lake_island_site_is_deterministic() -> None:
    elevation_rows = _lake_grid(width=180, height=160, margin=20)

    first = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )
    second = analyze_lake_island_fortress_site(
        elevation_rows=elevation_rows,
        elevation_style="flatland",
        fortress_config=_enabled_config(),
    )

    assert first == second
