# Architecture

TopDownMapGen состоит из двух основных слоёв.

```text
top_down_worldgen  -> генерирует данные мира
top_down_visualgen -> строит визуальное представление поверх данных мира
```

Главный контракт проекта — `output/map_package/`. Визуальные файлы являются производными артефактами.

## World generation core

Пакет `top_down_worldgen/` отвечает за:

- загрузку публичного конфига;
- запуск legacy engine;
- нормализацию tactical data;
- построение terrain, collision, movement, runtime grids;
- построение objects, places, markers, routes и world graph;
- построение gameplay zones;
- построение elevation model/features/transitions;
- экспорт legacy JSON и структурированного `map_package/`;
- validation report, density report, manifest и metrics.

Worldgen не зависит от visual output. Команда для чистой генерации:

```bash
./r world
```

## Visual layer

Пакет `top_down_visualgen/` читает `output/map_package/` и visual profile `dark_forest`.

Он отвечает за:

- mapping terrain -> visual tile ids;
- road/swamp/forest autotiling;
- decorative visual objects;
- place treatment;
- elevation visual overlays;
- boundary visual markers;
- preview PNG;
- asset-backed final render;
- debug reports и step PNG.

Visual layer не должен менять:

```text
terrain
collision
movement
runtime grids
routes
start/goal
gameplay zones
world graph
```

## Runtime data flow

```text
configs/default.json
  -> top_down_generator.py
  -> top_down_worldgen
  -> output/map_package/
  -> top_down_visualgen
  -> output/visual_map/
```

## Runner

`./r` — основной helper для локальной разработки. Он не является отдельной бизнес-логикой, а только запускает существующие Python entrypoints в правильном порядке.

Стандартный режим `./r` сохраняет совместимость: генерирует world data и visual data.

## Stable API для внешней игры

Внешняя игра должна читать:

```text
output/_manifest.json
output/map_package/map.json
```

Внешняя игра не должна импортировать Python-модули генератора и не должна полагаться на visual PNG как источник gameplay-истины.
