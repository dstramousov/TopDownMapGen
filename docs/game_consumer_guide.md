# Game consumer guide

Этот документ описывает, как игре читать `output/map_package/` без знания внутренних Python-модулей генератора.

## Правильная точка входа

Игра получает путь к output root конкретного запуска:

```text
output/
```

Дальше порядок такой:

1. открыть `output/_manifest.json`;
2. найти artifact с `kind = "map_package:index"`;
3. открыть `output/map_package/map.json`;
4. читать остальные файлы по относительным путям из `map.json`.

Если manifest отсутствует, tool может открыть `output/map_package/map.json` напрямую. Для игры это fallback, не основной сценарий.

## Минимальный набор для runtime scene

Обычно игре нужны:

```text
map_package/layers/tile_grid.json
map_package/layers/terrain.json
map_package/layers/collision.json
map_package/layers/movement_costs.json
map_package/runtime_grids.json
map_package/objects/runtime_objects.json
map_package/objects/places.json
map_package/markers.json
map_package/routes.json
map_package/world_graph.json
map_package/gameplay_zones.json
map_package/elevation_model.json
```

Для tactical gameplay также нужны:

```text
map_package/gameplay/combat_zones.json
map_package/gameplay/cover_points.json
map_package/gameplay/choke_points.json
map_package/gameplay/flank_routes.json
map_package/gameplay/enemy_spawn_zones.json
map_package/gameplay/fallback_positions.json
```

## Что не считать gameplay contract

Игра не должна использовать как источник gameplay-истины:

```text
output/visual_map/*.png
output/visual_map/visual_*.json
output/generated_map.txt
```

Visual output нужен renderer/debug layer. ASCII нужен человеку и legacy tools.

## Проверки consumer-а

Перед загрузкой сцены consumer должен проверить:

- размеры grid совпадают с `dimensions`;
- start/goal существуют;
- collision/movement grids прямоугольные;
- runtime objects имеют координаты внутри карты;
- routes/markers ссылаются на допустимые координаты;
- версия схемы поддерживается consumer-ом.
