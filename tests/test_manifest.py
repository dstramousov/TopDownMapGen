from pathlib import Path

from top_down_worldgen.manifest import OutputArtifact, build_manifest


def test_build_manifest_marks_primary_and_debug_outputs(tmp_path: Path) -> None:
    """Ensure manifest separates primary and debug artifacts."""
    ascii_map = tmp_path / "generated_map.txt"
    debug_map = tmp_path / "tactical_map_debug.json"
    ascii_map.write_text("++\n++\n", encoding="utf-8")
    debug_map.write_text("{}\n", encoding="utf-8")

    manifest = build_manifest(
        output_dir=tmp_path,
        seed=42,
        profile="clear_map",
        width=2,
        height=2,
        tile_size_px=16,
        total_time_ms=10.0,
        engine_time_ms=4.0,
        tactical_time_ms=3.0,
        render_time_ms=2.0,
        render_enabled=True,
        debug_images_enabled=False,
        layers=["base"],
        artifacts=[
            OutputArtifact(ascii_map, "ascii_map", True, False, "ascii-map-v1"),
            OutputArtifact(debug_map, "tactical_debug", False, True, "debug-v1"),
        ],
        metrics={"combat_zones": 1},
    )

    assert manifest["schema_version"] == "generation-manifest-v1"
    assert manifest["seed"] == 42
    assert manifest["dimensions"]["width_tiles"] == 2
    assert manifest["render"]["debug_images_enabled"] is False
    assert manifest["primary_outputs"][0]["path"] == "generated_map.txt"
    assert manifest["debug_outputs"][0]["path"] == "tactical_map_debug.json"
    assert len(manifest["files"]) == 2
