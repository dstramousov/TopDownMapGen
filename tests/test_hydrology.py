from top_down_worldgen.tactical.hydrology import apply_elevation_hydrology


def test_hydrology_maps_negative_levels_to_water_semantics() -> None:
    result = apply_elevation_hydrology(
        rows=["TTTTTSG"],
        elevation_rows=[[-5, -4, -3, -2, -1, -3, -1]],
    )

    assert result.rows == ["~~~~wSG"]
    assert result.report["summary"]["deep_water"] == 4
    assert result.report["summary"]["wet_shore"] == 1
    assert result.report["summary"]["protected"] == 2
