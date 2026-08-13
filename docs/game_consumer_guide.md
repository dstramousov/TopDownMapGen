# Game Consumer Guide

Этот документ описывает минимальный порядок чтения `output/map_package/` игровым клиентом.

## Минимальная загрузка

1. Открыть `output/map_package/map.json`.
2. Прочитать `dimensions`, `coordinates`, `points`.
3. Загрузить `runtime_grids.json`.
4. Загрузить `objects/runtime_objects.json`.
5. Загрузить `elevation_model.json` и `elevation_transitions.json`, если игра использует 3D/elevation movement.

Пример основного набора:

```text
map_package/map.json
map_package/runtime_grids.json
map_package/objects/runtime_objects.json
map_package/elevation_model.json
map_package/elevation_transitions.json
```

## Movement

Для движения используй несколько слоёв сразу:

| Источник | Роль |
|---|---|
| `runtime_grids.collision_grid` | Базовая terrain-проходимость. |
| `runtime_grids.movement_grid` | Стоимость движения. |
| `objects/runtime_objects.items[*].collision_profile` | Object blockers и object footprints. |
| `runtime_grids.height_grid` | Высота тайлов. |
| `elevation_transitions.items` | Явные переходы, cliffs, ramps, stairs, bridge edges. |

Натуральный переход между соседними тайлами разрешай только при `abs(delta_height) <= 1`, если collision и object blockers не запрещают движение.

## Rendering

Для простого render-а достаточно:

```text
layers/terrain.json
runtime_grids.height_grid
objects/runtime_objects.json
render/render_profile.json
render/tile_render_hints.json
render/object_render_hints.json
```

Если renderer должен выбирать землю/флору по окружению, дополнительно загружай:

```text
layers/environment_context.json
```

Этот слой даёт moisture, крупный region profile, slope, глубину внутри леса и
локальные proximity grids до леса, воды, дорог и structural geometry. Значение `0`
означает нахождение на semantic source, `9` — расстояние `9+` тайлов. Он не содержит
конкретных texture/sprite IDs: сопоставление environmental signals с арт-каталогом
остаётся задачей renderer-а.

`height_grid` не обязан означать настоящую 3D-геометрию. Это gameplay elevation contract. Renderer может использовать его как высоту колонны, как tint, как shadow layer или как сортировочный bias.

## Water and low ground

Не считай `level < 0` водой. Вода — это terrain/source-смысл, а не просто отрицательная высота.

Практическое правило:

```text
height_grid[y][x] < 0  -> low ground / below ground / structural depth
terrain == water       -> actual standing water
```

## Start and goal

`map.json -> points` и `layers/start_goal.json` дают основные точки. Генератор проверяет start-to-goal связность, но gameplay-код всё равно должен строить путь по своим правилам движения.

## Validation

Перед загрузкой в игру полезно читать `output/validation_report.json`. Ошибки должны блокировать интеграцию. Warning можно показывать разработчику и решать по смыслу конкретной игры.
