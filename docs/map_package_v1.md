# Map Package v1

`map_package/` — это стабильный публичный пакет карты для внешней игры, renderer-а или отладочного инструмента. Он лежит внутри `output/map_package/` и не требует читать legacy-файлы напрямую.

Главная точка входа:

```text
output/map_package/map.json
```

`map.json` содержит размеры карты, seed, версию генератора, координатную систему и относительные пути ко всем остальным слоям.

## Координаты

Все координаты в пакете тайловые:

```text
origin: top_left
x: вправо
y: вниз
unit: tile
```

Размер тайла для текущего top-down renderer-а хранится в `map.json -> dimensions.tile_size_px`.

## Основные файлы

| Файл | Назначение |
|---|---|
| `map.json` | Индекс пакета и список путей к слоям. |
| `layers/tile_grid.json` | ASCII-сетка исходных тайлов. |
| `layers/terrain.json` | Сетка terrain type по каждому тайлу. |
| `layers/collision.json` | Terrain-derived collision: `0` passable, `1` blocked. |
| `layers/movement_costs.json` | Стоимость движения по типам тайлов. |
| `layers/elevation.json` | Legacy-compatible elevation block из tactical map. |
| `layers/environment_context.json` | Производный экологический контекст: moisture, macro-region profile, slope и лесная кромка/дистанция. |
| `layers/start_goal.json` | Start/goal в tile coordinates. |
| `runtime_grids.json` | Runtime-ready grids: movement, collision, projectile, vision, cover, concealment, height. |
| `elevation_model.json` | Семантика уровней высоты, правила движения/LOS/projectiles. |
| `elevation_features.json` | Объекты и зоны, имеющие elevation-смысл. |
| `elevation_transitions.json` | Переходы между соседними уровнями. |
| `markers.json` | Start/goal/runtime-object markers. |
| `world_graph.json` | Семантический граф мест и связей. |
| `routes.json` | Main/side/AI/hidden routes, построенные из graph. |
| `gameplay_zones.json` | Обобщённые игровые зоны. |
| `objects/runtime_objects.json` | Runtime-object instances. |
| `objects/places.json` | Семантические места карты. |
| `catalogs/tile_types.json` | Каталог типов тайлов. |
| `catalogs/object_types.json` | Каталог типов runtime-объектов. |
| `render/*.json` | Render hints и render profile. |

## Environment context

`layers/environment_context.json` — публичный производный слой для экологически
осмысленного rendering-а земли и флоры. Он не хранит конкретные asset IDs и не
меняет authoritative terrain/gameplay data.

Schema первой версии:

```text
environment-context-layer-v1
```

Основные grids:

| Grid | Диапазон | Смысл |
|---|---:|---|
| `moisture` | `0..1000` | Непрерывная влажность из natural geography. |
| `region_profile` | dictionary code | Крупный профиль региона: `dense_forest`, `woodland`, `wet_lowland`, `upland`, `open_plateau`, `open_plain`, `alpine`. |
| `slope_band` | `0..3` | `flat`, `gentle`, `steep`, `cliff`. |
| `forest_depth` | `0..4` | Глубина внутри semantic forest; `4` означает четыре тайла и глубже. |
| `forest_distance` | `0..9` | Локальная дистанция до semantic forest; `9` означает девять тайлов и дальше. |

`forest_depth` и `forest_distance` строятся от semantic terrain `tree_blocker`, а
не от прореженного visual tree mask. Поэтому художественное thinning деревьев не
разрушает экологический смысл лесного массива.

Конкретные PNG/спрайты должен выбирать consumer-side `FloraResolver`. Например,
Vox3D может смешивать профиль лесной кромки с влажным профилем возле воды, не
заставляя генератор карты знать названия ассетов.

## Runtime grids

`runtime_grids.json` — основной файл для gameplay-кода. Внутри `grids`:

| Grid | Формат | Как использовать |
|---|---|---|
| `movement_grid` | numeric rows | Стоимость движения по тайлу. |
| `collision_grid` | boolean rows | Terrain collision. `1` значит blocked. |
| `projectile_block_grid` | boolean rows | Блокировка projectile trace с учётом terrain/object hints. |
| `vision_block_grid` | boolean rows | Блокировка line-of-sight. |
| `cover_grid` | numeric rows | Cover value `0.0..1.0`. |
| `concealment_grid` | numeric rows | Concealment value `0.0..1.0`. |
| `height_grid` | integer rows | Runtime elevation level на каждый тайл. |

`collision_grid` не обязан включать все object movement blockers. Для объектов нужно дополнительно читать `objects/runtime_objects.json` и их footprints/collision profiles.

## Elevation model

Текущий публичный диапазон высот:

```text
-5..20
```

Это форматный диапазон. Активный диапазон конкретной карты может быть уже и зависит от размера карты и `elevation.style`.

Поддерживаемые стили elevation:

| Стиль | Активный диапазон | Назначение |
|---|---:|---|
| `super_flatland` | `-1..1` | Почти плоская карта: лёгкие низины, базовая земля и лёгкие повышения. |
| `flatland` | `-5..4` | Низинная мягкая карта с частой волной уровня. |
| `rolling_hills` | `-5..10` | Основной игровой кандидат: мягкие холмы и средняя волна. |
| `normal` | size-aware | Сбалансированный совместимый режим. |
| `rugged` | высокий | Более рваная пересечённая местность. |
| `mountainous` | `-5..20` | Выразительная горная карта. |
| `plateau` | `-5..20` | Крупные плато и длинные склоны. |

Важно:

```text
negative level != water
```

Минусовой уровень означает низкую географию, траншею, яму, bunker interior или другой below-ground смысл. Реальная вода определяется terrain/source-слоями, а не самим фактом `level < 0`.

Базовые правила движения из `elevation_model.json`:

| Случай | Правило |
|---|---|
| Same level | Можно идти, если `collision_grid` разрешает. |
| Delta 1 | Естественный slope разрешён, если collision не блокирует. |
| Delta > 1 | Нужен explicit connector или переход считается blocked/scripted. |

`elevation_transitions.json` содержит соседние переходы и поле `movement_allowed`, которое можно использовать в pathfinding.

## Sources: geography / water / structural

Новая elevation-линия разделяет смысл высоты:

| Source | Значение |
|---|---|
| `geography` | Естественный рельеф: basin, lowland, plain, hill, plateau, ridge, mountain. |
| `water` | Стоячая вода / water terrain. Рек нет. |
| `structural` | Искусственная или объектная глубина/высота: bunker, trench, pit, tower, platform. |

Визуальные preview могут красить низкую географию синим, но consumer должен отличать low ground от actual water по terrain/source данным.

## Связность и repair

Генератор гарантирует, что start-to-goal становится 3D-reachable после traversal repair. Repair — часть production pipeline, а не внешний post-process. Consumer всё равно должен проверять движение по `collision_grid`, object blockers и `height_grid`/`elevation_transitions`.

Минимальная consumer-логика:

```text
1. load map.json
2. load runtime_grids.json
3. use collision_grid + object collision footprints
4. use height_grid for elevation
5. allow natural movement only for delta <= 1
6. use elevation_transitions for explicit connectors and blocked cliffs
```

## Совместимость

`map_package/` является основным контрактом. Legacy-файлы рядом с ним (`generated_map.txt`, `tactical_map.json`, `validation_report.json`) остаются для диагностики и обратной совместимости, но новая игра должна начинать чтение с `map_package/map.json`.
