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
