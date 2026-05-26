# Game consumer guide

Этот документ описывает, как игре читать `map_package/` без знания внутренних деталей генератора.

См. также `docs/world_building_algorithm.md` для пошагового алгоритма построения runtime-мира и `docs/world_package_file_map.md` для карты файлов output-пакета.


## Единый output root

Начиная с v0.0.29 игра должна получать один путь — output root конкретного запуска. В этой папке лежат и legacy-файлы, и новый `map_package/`, и `_manifest.json`.

Допустимые команды генерации:

```bash
PYTHONPATH=. python3 top_down_generator.py --config configs/default.json -o output --no-render
PYTHONPATH=. python3 top_down_generator.py --config configs/default.json -o output/generated_map.txt --no-render
```

Для consumer-а оба запуска эквивалентны: entrypoint остаётся `output/_manifest.json`, а основной пакет мира — `output/map_package/map.json`.

Consumer не должен знать про `out/`, `old/`, `new` или другие папки. Если manifest ссылается на файл, путь считается относительным к тому же output root.

## Минимальный сценарий загрузки

Игра должна читать карту в таком порядке:

1. открыть `_manifest.json`;
2. найти artifact с `kind = "map_package:index"`;
3. открыть указанный `map_package/map.json`;
4. прочитать `dimensions` и `coordinates`;
5. загрузить `layers/tile_grid.json`;
6. загрузить `layers/collision.json`;
7. загрузить `layers/movement_costs.json`;
8. загрузить `objects/runtime_objects.json`;
9. загрузить нужные `gameplay/*.json`;
10. построить runtime scene.

Если `_manifest.json` недоступен, можно напрямую открыть `map_package/map.json`, но это fallback, а не основной путь.

## Что игре нужно в первую очередь

Для первой интеграции достаточно:

```text
map.json
layers/tile_grid.json
layers/collision.json
layers/movement_costs.json
objects/runtime_objects.json
```

Этого хватит, чтобы получить размеры карты, старт/цель, базовую проходимость, стоимость движения и список объектов.

## Построение collision grid

В v1 collision строится из `tile_grid.rows` и `collision.blocked_tiles`.

Алгоритм:

```text
blocked = set(collision.blocked_tiles)
for each y,row in tile_grid.rows:
  for each x,tile in row:
    collision_grid[y][x] = tile in blocked
```

`true` означает blocked. `false` означает passable.

Важно: runtime-объекты могут добавлять собственные коллизии. Поэтому итоговая collision scene игры должна учитывать и tile collision, и `runtime_objects`.

## Построение movement grid

Movement grid строится из `tile_grid.rows` и `movement_costs.costs_by_tile`.

Алгоритм:

```text
costs = movement_costs.costs_by_tile
for each tile:
  movement_cost = costs.get(tile, 1)
```

Если клетка blocked по collision, игра может игнорировать movement cost или выставить бесконечную стоимость.

## Старт и цель

Старт и цель лежат в `map.json`:

```text
points.start
points.goal
```

Если значение `null`, значит точка не найдена. Валидная генерация должна иметь один старт и одну цель, но game loader всё равно должен проверять `null`, чтобы не падать на повреждённых пакетах.

## Runtime-объекты

`objects/runtime_objects.json` содержит `items`. Каждый item — конкретный объект на карте. Игра должна воспринимать эти объекты как сущности поверх terrain layer.

На первом этапе можно использовать только:

```text
id
type
position / x,y fields if present
collision_profile
combat_properties
```

Точная структура объекта зависит от версии tactical pipeline, поэтому loader игры должен быть терпим к дополнительным полям.

## Enemy spawn zones

Для врагов читать:

```text
gameplay/enemy_spawn_zones.json
```

На первом этапе можно брать центр/позиции зон и не использовать весь tactical analysis.

## Какие слои можно игнорировать сначала

Игра может временно игнорировать:

```text
cover_points.json
choke_points.json
flank_routes.json
fallback_positions.json
places.json
elevation.json
```

Но эти слои уже есть для будущего AI, баланса, тактического поведения и narrative logic.

## Ошибки загрузки

Game loader не должен молча продолжать работу, если отсутствуют:

```text
map.json
tile_grid.json
collision.json
movement_costs.json
```

Это hard error. Отсутствие optional gameplay-слоя можно трактовать как пустой список.

## Версионирование

Игра должна проверять:

```text
map.json.package_schema_version
map.json.schema_version
_manifest.json.versions.schemas
```

Если major/version family неизвестна, лучше отказать в загрузке, чем неправильно интерпретировать карту.

## Минимальный результат интеграции

После загрузки `map_package/` игра должна уметь:

```text
- создать карту нужного размера;
- поставить игрока в points.start;
- знать points.goal;
- построить blocked/passable grid;
- построить movement-cost grid;
- создать runtime-объекты;
- выбрать enemy spawn zones.
```

Этого достаточно для первой проверки карты в игровом runtime без renderer-specific логики.


## Runtime-friendly loading since v0.0.26

Для новой интеграции лучше использовать такие файлы:

1. `_manifest.json` — найти `map_package:index`;
2. `map_package/map.json` — получить размеры и ссылки на слои;
3. `layers/terrain.json` — получить типы поверхности;
4. `layers/collision.json` — построить boolean collision grid из `rows`;
5. `layers/movement_costs.json` — читать `costs_by_type`;
6. `layers/start_goal.json` — получить `start` и `goal`;
7. `objects/runtime_objects.json` — расставить объекты;
8. `gameplay/enemy_spawn_zones.json` — подключить спавны врагов, если они нужны.

`tile_grid.json` остаётся полезным для отладки и legacy-инструментов, но игра не должна строить логику напрямую на символах `+`, `T`, `#` и других ASCII-тайлах.

## Type catalogs since v0.0.27

После загрузки `map.json` игра может открыть:

```text
catalogs/tile_types.json
catalogs/object_types.json
```

Рекомендуемый порядок:

1. загрузить `terrain.json`;
2. загрузить `collision.json`;
3. загрузить `movement_costs.json`;
4. загрузить `catalogs/tile_types.json`;
5. загрузить `objects/runtime_objects.json`;
6. загрузить `catalogs/object_types.json`.

`tile_types.json` нужен, чтобы не держать в игре таблицу вида “`tree_blocker` значит blocked, `water_slow` значит slow”. `object_types.json` нужен, чтобы игра понимала свойства типов объектов без ручного хардкода по каждому экземпляру.

Для первой интеграции catalogs можно использовать так:

```text
for terrain_type in terrain row:
  tile_def = tile_types[terrain_type]
  walkable = tile_def.walkable
  movement_cost = tile_def.movement_cost
```

Для объектов:

```text
for object in runtime_objects:
  object_def = object_types[object.type]
  blocks_movement = object_def.blocks_movement
  cover_type = object_def.cover_type
```

Если catalog отсутствует, loader может fallback-нуться на поля самого объекта или на `collision.json`, но для новых интеграций это уже нежелательно.

## Render hints для клиента

Папка `map_package/render/` не обязательна для первой игровой интеграции. Она нужна тем клиентам, которые хотят построить preview, редактор или собственный renderer без знания внутренних эвристик генератора.

Рекомендуемый порядок чтения для renderer-а:

```text
1. открыть map_package/map.json;
2. прочитать map_json.render.profile;
3. открыть render/render_profile.json;
4. открыть layers/terrain.json;
5. открыть objects/runtime_objects.json;
6. открыть render/tile_render_hints.json;
7. открыть render/object_render_hints.json;
8. применить fallback для неизвестных visual_group.
```

Важно: `visual_group` — это не путь к PNG. Это стабильное семантическое имя, например `terrain/grass`, `terrain/road/old_overgrown`, `objects/cover/stone_chunk`. Конкретный движок или renderer сам решает, какой tileset/objectset соответствует этой группе.

Игровой runtime не должен принимать решения о проходимости по render hints. Для этого есть `collision.json`, `movement_costs.json`, `tile_types.json` и `object_types.json`.

## Проверка пакета внешним consumer-ом since v0.0.30

Для быстрой проверки результата генерации добавлен пример-инспектор:

```bash
python3 examples/inspect_world_package.py output
```

Он намеренно читает только публичные файлы результата:

```text
output/_manifest.json
output/map_package/map.json
output/map_package/layers/*
output/map_package/objects/*
output/map_package/gameplay/*
output/map_package/catalogs/*
output/map_package/render/*
```

Инспектор не импортирует pipeline генератора и не использует внутренние runtime-классы. Его задача — вести себя как внешний клиент: открыть output root, найти `map_package:index` через manifest, загрузить `map_package/map.json`, проверить базовые размеры слоёв и вывести короткую сводку.

Нормальный результат выглядит так:

```text
World package: OK
Map: 160x160 tiles, tile size 16 px
Layers:
- collision: OK, passable=..., blocked=..., blocked_ratio=...
Objects:
- runtime objects: ... total, ... types
Result:
- package is loadable by an external consumer
```

Если пакет неполный или сломан, команда завершается с ненулевым кодом и выводит `World package: FAILED`. Это удобно использовать как smoke-check перед передачей output-папки в игру или отдельный renderer.

## Визуальная smoke-проверка пакета

После `examples/inspect_world_package.py` можно запустить внешний preview renderer:

```bash
python3 examples/render_world_preview.py output
```

Он читает только публичный контракт:

```text
output/_manifest.json
output/map_package/map.json
output/map_package/layers/*
output/map_package/objects/*
```

и создаёт:

```text
output/world_preview.png
```

Это не игровой renderer и не финальная графика. Это проверка, что из файлов пакета реально можно
собрать видимое представление мира: terrain, collision overlay, runtime object markers, start и goal.

Полезные варианты:

```bash
python3 examples/render_world_preview.py output --collision-overlay
python3 examples/render_world_preview.py output --cell-size 8 --grid
python3 examples/render_world_preview.py output --no-objects
python3 examples/render_world_preview.py output --output output/debug/world_preview.png
```

Если preview выглядит как каша, но инспектор говорит `World package: OK`, значит пакет формально
валиден, но семантические слои или render hints требуют отдельной настройки. Это нормальная роль
preview: быстро показать глазами, что данные дают осмысленный мир.

## Multi-tile object handling

A game consumer must not treat runtime objects as single-tile markers. Read `footprint` for occupied cells, `collision_footprint` for gameplay collision, `visual_bounds` for coarse sprite placement, and `pivot` for renderer anchoring. The object's `x`, `y`, `position`, and `anchor` fields describe the anchor tile, not the full occupied size. Bunkers can also provide `firing_ports`, `surface_elevation`, and `interior_elevation` for directional interaction/line-of-fire rules.


## Generation tuning

`map_package/map.json` and `_manifest.json` expose the `generation_tuning` block copied from the public config. These values are user-facing knobs for changing the generated world density: water, forests, open spaces, ruins, buildings, road width, decoration, and bunkers. Water has dedicated controls: `water_scale`, `water_patch_count_scale`, `water_patch_size_scale`, and `water_patch_density`. Consumers should treat these values as provenance/diagnostics, not as runtime rules. The generated layers and catalogs remain the source of truth for the final world.


## Package consistency validation

Начиная с `v0.0.41`, validation проверяет не только наличие файлов, но и согласованность публичного пакета: `markers` должны совпадать со `start_goal`, `runtime_grids` должны иметь ожидаемые размеры, `world_graph` должен ссылаться на реальные places/markers, а `routes` — на реальные nodes/edges. Start и goal также проверяются против `collision_grid`, чтобы внешний consumer не получал заблокированную стартовую или целевую клетку.

Non-critical quality violations caused by aggressive tuning are reported as warnings in `generation.log`, `_manifest.json`, and `validation_report.json`; they should not be treated as engine crashes unless a required file or structural layer is missing.

## Markers and runtime grids

Since v0.0.37, consumers should prefer `map_package/markers.json` for start/goal and gameplay points, and `map_package/runtime_grids.json` for immediate runtime grids. This avoids rebuilding common grids from lower-level layers during game startup.

## `routes.json`

`routes.json` contains semantic route records derived from `world_graph.json`. It does not replace tile pathfinding and it is not an exact step-by-step movement path. It tells a consumer what a route means in gameplay terms.

Current route types:

- `main_road` — primary intended route from start toward goal.
- `side_path` — optional branch route to a secondary place.
- `hidden_path` — secret or hard-to-notice optional route.
- `patrol_route` — AI/NPC route derived from risky place connections.
- `escape_route` — retreat or exit route derived from start/goal connections.

Each route may contain `node_ids`, `edge_ids`, `waypoints`, `cost_tiles`, `bidirectional`, and `tags`. Use `runtime_grids.json` for exact movement/collision checks and `routes.json` for route intent.

