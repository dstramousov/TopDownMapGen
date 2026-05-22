from __future__ import annotations

from pathlib import Path

from top_down_worldgen.object_catalog import build_object_catalog_markdown, write_object_catalog


def test_object_catalog_includes_counts_and_symbols(tmp_path: Path) -> None:
    """Ensure human-readable object catalog includes generated counts."""
    runtime_data = {
        "map": {
            "tile_counts": {"+": 3, "S": 1, "G": 1},
        },
        "runtime_objects_summary": {
            "total": 2,
            "by_type": {"stone_chunk": 1, "trench": 1},
        },
        "places_summary": {
            "total": 1,
            "by_type": {"old_defensive_position": 1},
        },
    }

    content = build_object_catalog_markdown(
        rows=["S+G", "++"],
        runtime_data=runtime_data,
    )

    assert "# Object Catalog" in content
    assert "`stone_chunk`" in content
    assert "`car_wreck`" in content
    assert "`old_well`" in content
    assert "| K      | `stone_chunk`" in content
    assert "| V      | `car_wreck`" in content
    assert "| M      | `old_well`" in content
    assert "| U      | `trench`" in content
    assert "| `+`    | `grass`" in content
    assert "| `old_defensive_position`" in content
    assert "| Count" in content
    assert "---:" in content


def test_write_object_catalog_creates_markdown_file(tmp_path: Path) -> None:
    """Ensure object catalog writer creates a Markdown file."""
    path = tmp_path / "object_catalog.md"

    write_object_catalog(
        path=path,
        rows=["SG"],
        runtime_data={"runtime_objects_summary": {"by_type": {}}},
    )

    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("# Object Catalog")
