# World Building Algorithm

Документ фиксирует порядок, в котором внешний consumer может собрать runtime-мир из файлов `output/map_package/`.

## 1. Package index

Сначала читается:

```text
map_package/map.json
```

Из него берутся:

```text
dimensions
coordinates
points
paths to layers/runtime_grids/objects/elevation files
```

Все остальные пути относительны `map_package/`.

## 2. Base terrain

Загрузить:

```text
layers/tile_grid.json
layers/terrain.json
layers/collision.json
layers/movement_costs.json
```

`terrain.json` даёт тип поверхности. `collision.json` даёт terrain-derived блокировку. `movement_costs.json` даёт стоимость движения по типам тайлов.

## 3. Runtime grids

Загрузить `runtime_grids.json` и построить runtime arrays:

```text
movement_grid
collision_grid
projectile_block_grid
vision_block_grid
cover_grid
concealment_grid
height_grid
```

Эти массивы имеют один размер: `width x height`.

## 4. Objects and places

Загрузить:

```text
objects/runtime_objects.json
objects/places.json
```

Runtime objects накладываются поверх terrain. Они могут добавлять cover, concealment, vision/projectile blockers, interaction shapes и gameplay-смысл.

## 5. Elevation

Загрузить:

```text
elevation_model.json
elevation_features.json
elevation_transitions.json
```

`height_grid` даёт уровень каждого тайла. `elevation_model.json` объясняет смысл уровней `-5..20`. `elevation_transitions.json` перечисляет соседние переходы и говорит, разрешён ли movement.

Правило по умолчанию:

```text
same level: allowed if collision allows
delta 1:    natural slope allowed if collision allows
delta > 1:  blocked unless explicit connector/script says otherwise
```

## 6. Semantic graph and routes

Загрузить:

```text
world_graph.json
routes.json
gameplay_zones.json
```

`world_graph.json` — не pathfinding grid. Это смысловая карта мест и связей. `routes.json` — намеренные маршруты между node-ами. Для точного movement всегда пересчитывай путь по runtime grids.

## 7. Gameplay layers

Опционально загрузить:

```text
gameplay/combat_zones.json
gameplay/cover_points.json
gameplay/choke_points.json
gameplay/flank_routes.json
gameplay/enemy_spawn_zones.json
gameplay/fallback_positions.json
```

Эти слои нужны AI, encounter placement и тактической логике.

## 8. Render hints

Опционально загрузить:

```text
catalogs/tile_types.json
catalogs/object_types.json
render/render_profile.json
render/tile_render_hints.json
render/object_render_hints.json
```

Render hints не являются обязательной gameplay-истиной. Они помогают быстро собрать debug/preview render.

## Итоговый порядок

```text
map.json
-> base terrain layers
-> runtime_grids
-> objects/places
-> elevation model/transitions
-> semantic graph/routes
-> gameplay layers
-> render hints
```
