# World building algorithm

Документ описывает практический порядок построения runtime-мира во внешнем проекте.

## 1. Открыть output root

Consumer получает путь:

```text
output/
```

Он не должен импортировать `top_down_worldgen` или читать внутренние Python-классы.

## 2. Найти package index

Основной путь:

```text
output/_manifest.json -> map_package/map.json
```

Fallback для tools:

```text
output/map_package/map.json
```

## 3. Прочитать размеры

Из `map_package/map.json` взять:

- width tiles;
- height tiles;
- tile size px;
- coordinate model;
- seed/resolved seed.

## 4. Загрузить базовые grids

Минимально:

```text
layers/tile_grid.json
layers/terrain.json
layers/collision.json
layers/movement_costs.json
runtime_grids.json
```

`runtime_grids.json` содержит gameplay-ready grids, включая `height_grid`, `vision_block_grid`, `projectile_block_grid`, `cover_grid` и `concealment_grid`.

## 5. Загрузить semantic data

```text
objects/runtime_objects.json
objects/places.json
markers.json
routes.json
world_graph.json
gameplay_zones.json
```

## 6. Загрузить tactical data

```text
gameplay/combat_zones.json
gameplay/cover_points.json
gameplay/choke_points.json
gameplay/flank_routes.json
gameplay/enemy_spawn_zones.json
gameplay/fallback_positions.json
```

## 7. Загрузить elevation

```text
elevation_model.json
elevation_features.json
elevation_transitions.json
layers/elevation.json
```

Elevation в текущем проекте уже присутствует в world package. Visual layer только показывает эти данные.

## 8. Построить сцену

Рекомендуемый порядок:

1. создать tile map;
2. применить collision/movement;
3. создать navigation/runtime grids;
4. создать semantic places;
5. создать runtime objects;
6. применить routes/markers/world graph;
7. применить gameplay zones;
8. применить elevation;
9. подключить renderer/visual layer, если нужен.
