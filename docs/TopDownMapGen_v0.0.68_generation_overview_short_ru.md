# TopDownMapGen v0.0.68 — краткое описание генерации карты

Документ описывает, что происходит при запуске генератора и в каком виде получается готовая карта. Это не API-спека до последнего поля, а короткая карта местности: что читать первым, где лежат важные данные и почему итог — это не PNG и не ASCII, а структурированный `map_package/`.

## Главная идея

`TopDownMapGen` генерирует **тайловый runtime-мир**. ASCII-карта и PNG-превью нужны для человека и отладки. Основной машинный результат — каталог `map_package/`, где отдельно лежат поверхность, коллизии, стоимость движения, высоты, объекты, микролокации, маршруты, зоны gameplay и подсказки для рендера.

Базовая единица карты — **tile**. В конфиге по умолчанию карта имеет `192 x 192` тайла, размер тайла для рендера — `16 px`. Координаты тайловые: `(0, 0)` — левый верхний угол, `x` растёт вправо, `y` растёт вниз.

## Коротко по этапам

| Этап                  | Что делает                                                                              | Главный результат                                                 |
| :-------------------- | :-------------------------------------------------------------------------------------- | :---------------------------------------------------------------- |
| 1. Config             | Читает публичный JSON-конфиг: seed, размер, chunk, biome/objective profile, tuning.     | _engine_config.json                                               |
| 2. Legacy world       | Строит базовую ASCII-карту: лес, дороги, руины, вода, старт/цель.                       | generated_map.txt, _raw_tactical_map.json                         |
| 3. Tactical           | Оптимизирует боевые точки, добавляет fallback, spawn policy, tile grid.                 | tactical_map.json                                                 |
| 4. Objects/places     | Размещает runtime-объекты, footprint, collision/combat metadata, собирает микролокации. | objects/runtime_objects.json, objects/places.json                 |
| 5. Elevation          | Создаёт height grid -5..20, рельеф, переходы, features, repair проходимости.            | elevation_model.json, runtime_grids.height_grid                   |
| 6. Package/export     | Пишет публичный контракт карты для игры/рендера/инспектора.                             | map_package/                                                      |
| 7. Reports/validation | Проверяет целостность, связность, размеры слоёв, плотности, качество.                   | _manifest.json, validation_report.json, world_summary_report.json |

## Что получается на выходе

Один запуск создаёт единый output root. Внутри лежат legacy-файлы, отчёты и основной публичный пакет:

```text
output/
  generated_map.txt
  tactical_map.json
  tactical_map_debug.json
  _raw_tactical_map.json
  _manifest.json
  validation_report.json
  world_summary_report.json
  world_density_report.json
  elevation_density_report.json
  object_catalog.md
  map_package/
    map.json
    runtime_grids.json
    markers.json
    world_graph.json
    routes.json
    gameplay_zones.json
    elevation_model.json
    elevation_features.json
    elevation_transitions.json
    layers/
    gameplay/
    objects/
    catalogs/
    render/
```

| Файл/каталог                    | Зачем нужен                                                                                          |
| :------------------------------ | :--------------------------------------------------------------------------------------------------- |
| _manifest.json                  | Точка входа в результат запуска. Показывает версии схем, primary/debug outputs и validation summary. |
| map_package/map.json            | Индекс публичного пакета: размеры, координаты, seed, ссылки на все слои.                             |
| map_package/runtime_grids.json  | Готовые runtime-сетки: движение, collision, projectile/vision block, cover, concealment, height.     |
| map_package/layers/*.json       | Сырые и смысловые слои: tile_grid, terrain, collision, movement_costs, elevation, start_goal.        |
| map_package/objects/*.json      | Конкретные объекты и микролокации. Тут footprint, bounds, entrances, связи.                          |
| map_package/world_graph.json    | Семантический граф мира: nodes, edges, main path, side paths, secret areas.                          |
| map_package/routes.json         | Описание намерения маршрутов: main_road, side_path, patrol_route и т.п.                              |
| map_package/gameplay_zones.json | Зоны смысла: safe, loot, encounter, danger, secret, story, extraction.                               |
| reports/*.json                  | Диагностика плотностей, высот, качества генерации и предупреждений.                                  |

## ASCII-слой — это не контракт игры

Legacy engine сначала строит читаемую сетку символов. Она полезна для debug, но игра не должна хардкодить поведение по символам напрямую. Для runtime нужно читать `terrain.json`, `collision.json`, `movement_costs.json`, `runtime_grids.json` и catalogs.

| Символ | Тип                   | Смысл                                                   |
| :----: | :-------------------- | :------------------------------------------------------ |
| +      | grass                 | Обычная проходимая земля.                               |
| .      | old_overgrown_road    | Дорога/тропа, обычно проходимая.                        |
| T      | tree_blocker          | Дерево/лесной блокер.                                   |
| b      | bush_slow_concealment | Куст: замедление/маскировка.                            |
| w      | water_slow            | Вода/болото: проходимость зависит от правил consumer-а. |
| #      | ruin_wall_blocker     | Стена руин, блокер.                                     |
| R      | ruin_floor            | Пол руин, проходимый terrain.                           |
| S/G    | start/goal            | Старт и цель.                                           |

## Самый важный файл для игры

`map_package/map.json` — индекс пакета. Он говорит, где лежат остальные слои:

```json
{
  "schema_version": "map-package-map-v11",
  "package_schema_version": "map-package-v1",
  "generator_version": "0.0.68",
  "dimensions": {
    "width_tiles": 192,
    "height_tiles": 192,
    "tile_size_px": 16
  },
  "coordinates": {
    "origin": "top_left",
    "unit": "tile",
    "x_axis": "right",
    "y_axis": "down"
  },
  "layers": {
    "terrain": "layers/terrain.json",
    "collision": "layers/collision.json",
    "movement_costs": "layers/movement_costs.json",
    "elevation": "layers/elevation.json",
    "start_goal": "layers/start_goal.json"
  },
  "runtime_grids": "runtime_grids.json"
}
```

## Runtime grids

`runtime_grids.json` — быстрый путь для consumer-а. Он уже содержит готовые сетки одинакового размера:

- `movement_grid` — числовая стоимость движения;
- `collision_grid` — `0/1`, где `1` означает blocked;
- `projectile_block_grid` — что блокирует выстрелы;
- `vision_block_grid` — что блокирует обзор;
- `cover_grid` — сила укрытия;
- `concealment_grid` — сила маскировки;
- `height_grid` — высота/уровень клетки.

Важно: высота **не равна воде** и **не равна collision**. Отрицательный уровень — это низина, траншея, яма, внутренность бункера или другой below-ground участок. Вода описывается terrain/source-моделью отдельно.

## Рекомендуемый порядок загрузки в игре

```text
1. output/_manifest.json
2. map_package/map.json
3. map_package/runtime_grids.json
4. map_package/markers.json
5. map_package/objects/runtime_objects.json
6. map_package/objects/places.json
7. map_package/world_graph.json
8. map_package/routes.json
9. map_package/gameplay_zones.json
10. render/catalog hints — только если нужны renderer-у
```

Минимум для первого runtime-прогона: `map.json`, `runtime_grids.json`, `markers.json`, `runtime_objects.json`. Этого хватит, чтобы поставить игрока, построить движение/коллизии/высоты и расставить объекты.

## Что проверять

После генерации нужно смотреть `validation_report.json` и `world_summary_report.json`. Ошибка структуры — это повод не грузить карту. Предупреждения качества можно анализировать отдельно: например, агрессивный tuning может сделать карту валидной, но неудобной для игры.

Короткая суть: **генератор строит не картинку, а пакет мира**. Картинка — это только визуальная проверка. Игровой клиент должен жить от `map_package/`.
