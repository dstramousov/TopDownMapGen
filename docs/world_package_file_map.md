# World Package File Map

Краткая карта файлов после генерации.

## Output root

| Файл | Назначение |
|---|---|
| `_manifest.json` | Паспорт генерации, версии схем, список созданных артефактов. |
| `generated_map.txt` | Legacy ASCII-карта. |
| `tactical_map.json` | Legacy/full tactical data. |
| `tactical_map_debug.json` | Debug tactical data. |
| `validation_report.json` | Подробный отчёт валидации. |
| `metrics.txt` | Legacy metrics. |
| `generation.log` | Подробный лог генерации. |
| `world_density_report.json` | Плотности terrain/collision/movement. |
| `elevation_density_report.json` | Плотности elevation/geography/slope/repair. |
| `world_summary_report.json` | Summary для консольного отчёта. |
| `terrain_island_report.json` | Результаты terrain island repair. |
| `object_catalog.md` | Человекочитаемый каталог тайлов/объектов. |

## Map package

| Файл | Назначение |
|---|---|
| `map_package/map.json` | Главный индекс пакета. |
| `map_package/markers.json` | Start/goal/object markers. |
| `map_package/runtime_grids.json` | Runtime-ready grids. |
| `map_package/world_graph.json` | Семантический граф мира. |
| `map_package/routes.json` | Main/side/AI/hidden routes. |
| `map_package/gameplay_zones.json` | Обобщённые gameplay zones. |
| `map_package/elevation_model.json` | Семантика elevation levels `-5..20`. |
| `map_package/elevation_features.json` | Elevation features. |
| `map_package/elevation_transitions.json` | Соседние elevation transitions. |

## Map package layers

| Файл | Назначение |
|---|---|
| `map_package/layers/tile_grid.json` | ASCII rows + legend. |
| `map_package/layers/terrain.json` | Terrain type rows. |
| `map_package/layers/collision.json` | Terrain collision rows. |
| `map_package/layers/movement_costs.json` | Movement costs by tile/type. |
| `map_package/layers/elevation.json` | Legacy elevation block. |
| `map_package/layers/start_goal.json` | Start/goal layer. |

## Gameplay files

| Файл | Назначение |
|---|---|
| `map_package/gameplay/combat_zones.json` | Combat zones. |
| `map_package/gameplay/cover_points.json` | Cover points. |
| `map_package/gameplay/choke_points.json` | Choke points. |
| `map_package/gameplay/flank_routes.json` | Flank routes. |
| `map_package/gameplay/enemy_spawn_zones.json` | Enemy spawn candidates. |
| `map_package/gameplay/fallback_positions.json` | Fallback positions. |

## Objects and catalogs

| Файл | Назначение |
|---|---|
| `map_package/objects/runtime_objects.json` | Runtime objects. |
| `map_package/objects/places.json` | Semantic places. |
| `map_package/catalogs/tile_types.json` | Tile type catalog. |
| `map_package/catalogs/object_types.json` | Object type catalog. |

## Render files

| Файл | Назначение |
|---|---|
| `map_package/render/render_profile.json` | Render size/profile. |
| `map_package/render/tile_render_hints.json` | Tile render hints. |
| `map_package/render/object_render_hints.json` | Object render hints. |

## Preview PNG

Preview-картинки не являются gameplay-контрактом. Они нужны для человека:

```text
full_world_preview.png
elevation_preview.png
elevation_source_preview.png
geography_preview.png
moisture_preview.png
water_lowland_preview.png
slope_preview.png
geography_3d_preview/*.png
```
