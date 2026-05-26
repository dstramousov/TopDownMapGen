# Game consumer guide

Этот документ описывает, как игре читать `map_package/` без знания внутренних деталей генератора.

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
