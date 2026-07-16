from top_down_worldgen.reports import _format_validation_warning_ru


def test_main_path_warning_is_translated() -> None:
    """Ensure the main-path warning is readable in Russian console output."""
    warning = {
        "code": "quality.map_package_main_path_elevation_reachable",
    }

    assert _format_validation_warning_ru(warning) == (
        "главный маршрут map package не подтверждён как проходимый по высотам"
    )
