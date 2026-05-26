# World package file map

Этот документ кратко описывает, что лежит в output root после одного запуска генератора.

## Output root

```text
output/
  generated_map.txt
  tactical_map.json
  tactical_map_debug.json
  _raw_tactical_map.json
  _manifest.json
  validation_report.json
  metrics.txt
  object_catalog.md
  layer_base_map.png
  layer_*.png
  world_preview.png
  map_package/
```

Не каждый файл появляется при любом запуске. PNG debug-слои зависят от render/debug flags.

## Главные entrypoints

| Файл | Для кого | Назначение |
|---|---|---|
| `_manifest.json` | все внешние tools/consumers | Паспорт одного запуска и список артефактов. |
| `map_package/map.json` | игра, renderer, tools | Индекс нового структурированного пакета мира. |
| `generated_map.txt` | человек, legacy tools | Простая ASCII-карта. |
| `tactical_map.json` | legacy/diagnostics | Старый монолитный tactical export. |
| `validation_report.json` | CI/debug | Подробный отчёт валидации. |
| `object_catalog.md` | человек | Человекочитаемый каталог созданных типов и количеств. |

## map_package

```text
map_package/
  map.json
  layers/
  gameplay/
  objects/
  catalogs/
  render/
```

`map_package/` — основной контракт для будущей игры. Он должен быть достаточен, чтобы внешний проект построил runtime-мир без доступа к внутренностям генератора.

## layers

| Файл | Назначение |
|---|---|
| `tile_grid.json` | Компактная сетка исходных tile symbols. |
| `terrain.json` | Смысловые terrain-типы по клеткам. |
| `collision.json` | Runtime-ready passable/blocked grid. |
| `movement_costs.json` | Стоимости движения по тайлам/типам. |
| `elevation.json` | Уровни высоты/углубления. |
| `start_goal.json` | Стартовая и целевая точки. |

## gameplay

| Файл | Назначение |
|---|---|
| `combat_zones.json` | Боевые зоны и encounter-семантика. |
| `cover_points.json` | Точки укрытий. |
| `enemy_spawn_zones.json` | Зоны появления врагов. |
| `choke_points.json` | Узкие места маршрутов. |
| `flank_routes.json` | Фланговые маршруты. |
| `fallback_positions.json` | Возможные позиции отхода. |

## objects

| Файл | Назначение |
|---|---|
| `runtime_objects.json` | Конкретные объекты на карте. |
| `places.json` | Микролокации и смысловые сцены с bounds, entrances, danger/loot/story metadata и connected places. |

## catalogs

| Файл | Назначение |
|---|---|
| `tile_types.json` | Машинные свойства terrain/tile типов. |
| `object_types.json` | Машинные свойства object types. |

Catalogs нужны, чтобы игра не хардкодила смысл `tree_blocker`, `water_slow`, `fallen_log`, `trench` и других типов.

## render

| Файл | Назначение |
|---|---|
| `render_profile.json` | Общий render-profile пакета. |
| `tile_render_hints.json` | Подсказки для отрисовки terrain/tile типов. |
| `object_render_hints.json` | Подсказки для отрисовки object types. |

Render hints не являются обязательной игровой логикой. Они нужны preview/external renderer-ам.

## Проверочные tools

| Команда | Назначение |
|---|---|
| `python3 examples/inspect_world_package.py output` | Проверить, что пакет читается внешним consumer-ом. |
| `python3 examples/render_world_preview.py output` | Построить простой PNG preview из публичных файлов. |
| `python3 examples/read_map_package.py output` | Вывести краткую сводку пакета. |

## Рекомендуемый порядок чтения

```text
_manifest.json
map_package/map.json
layers/terrain.json
layers/collision.json
layers/movement_costs.json
layers/elevation.json
layers/start_goal.json
objects/runtime_objects.json
catalogs/tile_types.json
catalogs/object_types.json
gameplay/*.json as needed
render/*.json as needed
```

## Runtime object footprints

`map_package/objects/runtime_objects.json` uses `object-instances-v3` and includes footprint-aware object instances. Object-related catalogs in `map_package/catalogs/object_types.json` use `object-types-catalog-v3` and expose default footprint metadata derived from generated instances.

Important fields:

- `anchor`: tile-space placement point for the object instance.
- `footprint`: logical occupied cells.
- `collision_footprint`: cells affected by collision profile.
- `visual_bounds`: coarse tile-space visual rectangle.
- `pivot`: tile-space pivot hint for renderers.
- `firing_ports`: optional directional firing/interaction edges for bunker-like objects.

`buried_bunker_2x2` and `buried_bunker_2x3` are the first explicit bunker test objects. They use multi-tile footprints, full collision footprints, `interior_elevation = -1`, and firing ports on two opposite sides.


## Generation tuning

`map_package/map.json` and `_manifest.json` expose the `generation_tuning` block copied from the public config. These values are user-facing knobs for changing the generated world density: water, forests, open spaces, ruins, buildings, road width, decoration, and bunkers. Water has dedicated controls: `water_scale`, `water_patch_count_scale`, `water_patch_size_scale`, and `water_patch_density`. Consumers should treat these values as provenance/diagnostics, not as runtime rules. The generated layers and catalogs remain the source of truth for the final world.

Non-critical quality violations caused by aggressive tuning are reported as warnings in `generation.log`, `_manifest.json`, and `validation_report.json`; they should not be treated as engine crashes unless a required file or structural layer is missing.

## v0.0.37: markers and runtime grids

`map_package/markers.json` contains gameplay markers that must not be mixed into terrain data. It currently includes `start`, `goal`, and marker projections for notable runtime objects such as loot, story markers, landmarks, and defensive points.

`map_package/runtime_grids.json` contains ready-to-use grids for runtime consumers:

- `movement_grid`
- `collision_grid`
- `projectile_block_grid`
- `vision_block_grid`
- `cover_grid`
- `concealment_grid`
- `height_grid`

A game may load these grids directly instead of deriving them from terrain, objects, and catalogs on startup. Source layers are still exported for debugging, validation, and editor use.

## `map_package/world_graph.json`

`map_package/world_graph.json` contains the semantic graph of the generated world.
It is a higher-level navigation and pacing contract built from places and markers.
It contains:

- `nodes`: semantic places and important markers such as start/goal.
- `edges`: intended links between nodes.
- `main_path`: approximate start-to-goal semantic route.
- `side_paths`: optional branches through non-main places.
- `dead_ends`: low-degree nodes that can become loot/story branches.
- `secret_areas`: places marked or inferred as high-reward/secret areas.

Use `runtime_grids.json` for exact movement/pathfinding and `world_graph.json` for world structure.

## `routes.json`

`routes.json` contains semantic route records derived from `world_graph.json`. It does not replace tile pathfinding and it is not an exact step-by-step movement path. It tells a consumer what a route means in gameplay terms.

Current route types:

- `main_road` — primary intended route from start toward goal.
- `side_path` — optional branch route to a secondary place.
- `hidden_path` — secret or hard-to-notice optional route.
- `patrol_route` — AI/NPC route derived from risky place connections.
- `escape_route` — retreat or exit route derived from start/goal connections.

Each route may contain `node_ids`, `edge_ids`, `waypoints`, `cost_tiles`, `bidirectional`, and `tags`. Use `runtime_grids.json` for exact movement/collision checks and `routes.json` for route intent.

