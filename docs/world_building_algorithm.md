# World building algorithm

Этот документ описывает, как внешний проект должен строить runtime-мир из `output/`, не зная внутренних классов генератора.

## Главный принцип

Один запуск генератора создаёт один output root. Внешний consumer получает путь к этой папке и начинает работу с `_manifest.json`.

```text
output/
  _manifest.json
  map_package/
    map.json
    layers/
    gameplay/
    objects/
    catalogs/
    render/
```

Consumer не должен читать внутренние Python-модули генератора и не должен зависеть от `tactical_map.json`, если ему нужен новый runtime-контракт.

## 1. Найти пакет мира

1. Открыть `output/_manifest.json`.
2. Найти artifact с `kind = "map_package:index"`.
3. Открыть указанный файл, обычно `output/map_package/map.json`.
4. Все относительные пути из `map.json` считать относительно папки `map_package/`.

Fallback допустим только для инструментов: если manifest отсутствует, можно открыть `output/map_package/map.json` напрямую.

## 2. Прочитать размеры и координаты

Из `map.json` consumer берёт:

- `dimensions.width_tiles`;
- `dimensions.height_tiles`;
- `dimensions.tile_size_px`;
- координатную модель карты;
- ссылки на слои, объекты, каталоги и render hints.

Координаты тайловые: `x` растёт вправо, `y` растёт вниз, `(0, 0)` — верхний левый угол.

## 3. Построить базовую terrain-сцену

Для визуального и логического основания загрузить:

```text
layers/terrain.json
layers/tile_grid.json
catalogs/tile_types.json
```

`terrain.json` — предпочтительный слой для смыслового типа клетки. `tile_grid.json` остаётся компактным и удобным debug/legacy-представлением. `tile_types.json` объясняет свойства типов: проходимость, теги, стоимость движения и collision-семантику.

## 4. Построить collision grid

Загрузить `layers/collision.json` и построить boolean-сетку размера `width × height`.

```text
0 / false = passable
1 / true  = blocked
```

После этого применить collision runtime-объектов из `objects/runtime_objects.json` и `catalogs/object_types.json`. Итоговая collision scene игры должна учитывать и terrain/blocking tiles, и footprint объектов.

## 5. Построить movement grid

Загрузить `layers/movement_costs.json`.

Movement cost применяется к проходимым клеткам. Заблокированные клетки из collision grid должны считаться недоступными независимо от movement cost.

Рекомендуемый порядок:

1. взять базовую стоимость клетки из `movement_costs`;
2. если collision blocked — пометить клетку как недоступную;
3. применить object modifiers, если игра их поддерживает;
4. передать результат pathfinding-системе.

## 6. Применить elevation

Загрузить `layers/elevation.json`.

Текущий базовый контракт:

```text
-1 = углубление: окоп, яма, низина
 0 = обычная поверхность
```

Consumer должен хранить elevation отдельно от collision. Высота не равна блокировке. Например, траншея может быть проходимой, но должна влиять на укрытие, line of sight, stance rules или render order.

Будущие уровни `1..4` должны добавляться только вместе с правилами movement, shooting, visibility и rendering. Иначе это будет декоративный мусор.

## 7. Поставить start и goal

Загрузить `layers/start_goal.json` или соответствующую секцию `map.json`.

Игра должна проверить:

- старт и цель находятся внутри карты;
- старт и цель не заблокированы итоговой collision scene;
- между ними существует путь, если режим игры этого требует.

## 8. Расставить runtime objects

Загрузить:

```text
objects/runtime_objects.json
catalogs/object_types.json
```

Каждый instance задаёт конкретный объект на карте. Catalog описывает смысл типа: роль, укрытие, высоту, collision profile, projectile/vision blocking, интерактивность и теги.

Рекомендуемый порядок:

1. загрузить все object definitions из `object_types.json`;
2. пройти по instances из `runtime_objects.json`;
3. проверить координаты/footprint;
4. создать runtime entity;
5. применить collision/combat/interaction свойства из catalog;
6. связать entity с place/combat zone, если есть refs.

## 9. Загрузить places и gameplay

`objects/places.json` описывает микролокации: блокпосты, руины, лагеря, завалы и другие смысловые места.

`gameplay/*.json` содержит боевую семантику:

- `combat_zones.json`;
- `cover_points.json`;
- `enemy_spawn_zones.json`;
- `choke_points.json`;
- `flank_routes.json`;
- `fallback_positions.json`.

Игра может игнорировать часть gameplay-слоёв на первом этапе. Обязательны только те данные, которые реально используются её режимом.

## 10. Использовать render hints

`render/*.json` не является игровым runtime-источником. Это подсказки для renderer-а: как визуально трактовать terrain и object types.

Правильная модель:

```text
catalogs/ = что это значит для игры
render/   = как это можно нарисовать
```

Renderer может использовать hints для выбора тайлов, debug colors, object markers, будущих autotile-групп и render order.

## Минимальный consumer pipeline

```text
open output/_manifest.json
open map_package/map.json
load dimensions
load terrain/tile_grid
load collision
load movement_costs
load elevation
load start_goal
load object catalogs
spawn runtime objects
load gameplay layers needed by game mode
optionally load render hints
build runtime scene
```

## Что считается ошибкой

Consumer должен считать пакет непригодным, если:

- нет `_manifest.json` и нет fallback `map_package/map.json`;
- `map.json` ссылается на отсутствующие обязательные файлы;
- размеры любого grid-слоя не совпадают с `width × height`;
- start/goal отсутствуют или находятся вне карты;
- объект имеет неизвестный type;
- object footprint выходит за границы карты;
- catalog отсутствует для типа, который игра обязана интерпретировать.

## Быстрая проверка

Перед передачей пакета игре рекомендуется запускать:

```bash
python3 examples/inspect_world_package.py output
python3 examples/render_world_preview.py output --collision-overlay
```

Inspector проверяет загрузку и базовую целостность. Preview renderer показывает, получается ли из публичного пакета видимый мир.

## Object footprint model v1

Runtime objects must be treated as tile-space entities, not as single points. Each object instance exposes an `anchor`/`position` and three footprint-related fields:

- `footprint`: all map cells occupied by the logical object instance.
- `collision_footprint`: cells where the object's collision profile applies. This may be empty for small passable loot/markers.
- `visual_bounds`: a rectangular tile-space box used by preview/render consumers to estimate sprite coverage.

Consumers should use `footprint` for placement/overlap checks, `collision_footprint` for movement/projectile/vision rules, and `visual_bounds` only for drawing order or coarse sprite placement. Large objects such as tents, carts, wrecks, wells, checkpoints, trenches, pits, logs, berms, big trees, and buried bunkers may occupy multiple tiles. Bunkers additionally expose `firing_ports` on two opposite sides and mark their interior footprint as elevation `-1`.


## Generation tuning

`map_package/map.json` and `_manifest.json` expose the `generation_tuning` block copied from the public config. These values are user-facing knobs for changing the generated world density: water, forests, open spaces, ruins, buildings, road width, decoration, and bunkers. Water has dedicated controls: `water_scale`, `water_patch_count_scale`, `water_patch_size_scale`, and `water_patch_density`. Consumers should treat these values as provenance/diagnostics, not as runtime rules. The generated layers and catalogs remain the source of truth for the final world.

Non-critical quality violations caused by aggressive tuning are reported as warnings in `generation.log`, `_manifest.json`, and `validation_report.json`; they should not be treated as engine crashes unless a required file or structural layer is missing.
