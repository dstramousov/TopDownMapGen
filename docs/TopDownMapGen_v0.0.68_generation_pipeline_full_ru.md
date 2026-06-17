# TopDownMapGen v0.0.68 — подробное описание генерации и формата готовой карты

## 0. Назначение документа

Документ описывает состояние проекта `TopDownMapGen` по архиву `TopDownMapGen_v0.0.68_current.zip`: как запускается генерация, какие этапы проходит карта, какие файлы получаются на выходе и как внешний игровой проект должен читать результат.

Главная мысль: **генератор производит не картинку, а структурированный пакет мира**. `generated_map.txt` и PNG-превью полезны человеку, но основной контракт для игры — `map_package/`.

## 1. Базовые понятия

**Tile** — базовая клетка карты. В конфиге по умолчанию карта `192 x 192` тайла, render tile size — `16 px`.

**Tile-space координаты**:

```text
origin: top_left
unit:   tile
x_axis: right
y_axis: down
```

То есть `(0, 0)` — левый верхний угол, `x` растёт вправо, `y` вниз. Pixel/world-space должен вычислять consumer.

**ASCII map** — строковое представление карты символами (`+`, `T`, `#`, `S`, `G` и т.д.). Это debug/legacy-форма.

**Terrain layer** — смысловая поверхность клетки: `grass`, `tree_blocker`, `water_slow`, `ruin_wall_blocker`.

**Runtime grids** — готовые сетки для игры: collision, movement, projectile block, vision block, cover, concealment, height.

**Runtime object** — конкретный объект на карте: бревно, камень, окоп, бункер, башня, тайник. У объекта есть footprint, collision footprint, combat properties и render hints.

**Place** — микролокация, собранная из объектов: блокпост, тайник, бункерная зона, опасная низина, watchtower area.

**World graph/routes/gameplay zones** — не pathfinding по тайлам, а семантический слой: где основной путь, где боковые ветки, где loot/story/danger/secret зоны.

## 2. Как запускается генератор

CLI находится в `top_down_worldgen/cli.py`. Он принимает публичный конфиг и output target:

```python
parser.add_argument("--config", required=True, type=Path)
parser.add_argument(
    "-o",
    "--out",
    required=True,
    type=Path,
    help=(
        "Output directory or generated map .txt path. "
        "Directory targets use generated_map.txt inside that directory."
    ),
)
parser.add_argument("--render-tile-size", type=int, choices=[16, 32], default=16)
parser.add_argument("--no-render", action="store_true")
parser.add_argument("--include-debug-layers", action="store_true")
```

Пример запуска:

```bash
PYTHONPATH=. python3 top_down_generator.py \
  --config configs/default.json \
  -o output \
  --no-render
```

Если `-o` указывает на каталог, итоговая ASCII-карта будет `output/generated_map.txt`. Если `-o` указывает на `.txt`, результат будет рядом с этим файлом.

## 3. Публичный конфиг

В `configs/default.json` задаётся размер мира, seed, chunks, biome profile, objective profile и tuning:

```json
{
  "seed": "random",
  "map_width_tiles": 192,
  "map_height_tiles": 192,
  "chunk_width_tiles": 16,
  "chunk_height_tiles": 16,
  "biome_profile": "forest_ruins",
  "objective_profile": "clear_map",
  "generation_tuning": {
    "water_scale": 5.0,
    "forest_scale": 1.0,
    "open_space_scale": 1.0,
    "ruins_scale": 1.0,
    "buildings_scale": 1.0,
    "road_width_scale": 1.0,
    "decoration_scale": 1.0,
    "bunker_scale": 1.0,
    "water_patch_count_scale": 1.0,
    "water_patch_size_scale": 2.0,
    "water_patch_density": 0.62
  }
}
```

`tuning` — это не runtime-правила. Это параметры происхождения мира. После генерации source of truth — сами слои и catalogs.

## 4. Общий pipeline

| №  | Стадия                | Модуль/функция                                               | Что добавляет                                                                                        |
| --: | :-------------------- | :----------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- |
| 1  | Load config           | PublicConfig.from_file                                       | Seed, размеры, chunks, biome profile, objective profile, generation_tuning.                          |
| 2  | Prepare outputs       | OutputPaths.from_cli_output                                  | Единый output root и все стандартные пути результата.                                                |
| 3  | Legacy engine         | LegacyEngineRunner -> legacy/engine.py                       | ASCII-карту, region graph, дороги, руины, воду, декор, старт/цель, raw tactical.                     |
| 4  | Tactical optimizer    | TacticalOptimizer.optimize                                   | Урезает/нормализует tactical data: cover, zones, flank, spawn.                                       |
| 5  | Fallback positions    | FallbackPositionBuilder.add                                  | Позиции отхода вокруг зон боя.                                                                       |
| 6  | Objective policy      | ObjectiveProfileSelector.apply                               | Политику enemy spawn под clear_map/survival/timed_breakthrough.                                      |
| 7  | Tile grid attach      | attach_tile_grid                                             | Встраивает ASCII rows и проверяет размеры.                                                           |
| 8  | Runtime objects       | attach_runtime_layers                                        | Объекты, footprints, collision/combat profiles, elevation cells.                                     |
| 9  | Terrain island repair | repair_terrain_islands                                       | Удаляет маленькие оторванные walkable-острова.                                                       |
| 10 | Places                | attach_places                                                | Микролокации: bounds, entrances, story/loot/danger, connections.                                     |
| 11 | Elevation             | attach_next_gen_elevation                                    | Height grid -5..20, рельеф, макрорегионы, transitions, traversal repair.                             |
| 12 | Package export        | write_map_package                                            | Публичный map_package: layers, runtime grids, graph, routes, gameplay zones, catalogs, render hints. |
| 13 | Render optional       | LayerRenderer.render_all                                     | PNG base/debug layers, если render включён.                                                          |
| 14 | Validation/reports    | build_validation_report, build_world_reports, build_manifest | Validation, density/elevation reports, manifest, console summary.                                    |

Ключевой кусок из `WorldgenPipeline.run`: сначала legacy engine, потом tactical processing, потом package export.

```python
LegacyEngineRunner(engine_path).run(
    config_path=outputs.engine_config,
    map_out=outputs.generated_map,
    tactical_out=outputs.raw_tactical_map,
    log_file=log_file or outputs.log_file,
)

runtime_data, debug_data = TacticalOptimizer().optimize(raw_data)
runtime_data, debug_data = FallbackPositionBuilder().add(runtime_data, debug_data)
runtime_data, debug_data = ObjectiveProfileSelector(config.objective_profile).apply(
    runtime_data,
    debug_data,
)
runtime_data = attach_tile_grid(runtime_data, rows)
runtime_data = attach_runtime_layers(
    runtime_data,
    seed=config.resolved_seed,
    generation_tuning=config.generation_tuning.to_dict(),
)
```

И затем:

```python
runtime_data = attach_places(runtime_data)
runtime_data = attach_next_gen_elevation(
    runtime_data,
    rows=rows,
    seed=config.resolved_seed,
)

write_map_package(
    outputs=outputs,
    runtime_data=runtime_data,
    rows=rows,
    width=config.map_width_tiles,
    height=config.map_height_tiles,
    tile_size_px=tile_size_px,
    seed=config.seed,
    resolved_seed=config.resolved_seed,
    profile=config.objective_profile,
    generation_tuning=config.generation_tuning.to_dict(),
)
```

## 5. Legacy world generation

Первый большой блок — старый генератор `top_down_worldgen/legacy/engine.py`. Он строит ASCII-карту и первичную tactical metadata.

Основной порядок внутри `generate()`:

```python
self._fill_forest()
self._place_regions_evenly()
self._assign_region_kinds()
self._build_region_graph()
self._carve_regions()
self._carve_graph_roads()
self._add_connected_pockets()
self._add_cracked_ground_patches()
self._add_water_patches()
self._add_tree_clusters_with_bushes()
self._add_flower_patches()
self._add_mushroom_patches()
self._cleanup_small_components()
self._place_start_goal()
self._open_dead_forest_masses()
self._repair_critical_connectivity()
self._repair_walkable_connectivity()
self._place_start_goal()
self._validate()
```

Смысл этапов:

1. вся карта сначала заполняется деревьями;
2. по карте расставляются смысловые регионы;
3. выбираются стартовый и целевой регионы, центральная руина, малые/средние руины;
4. строится connected region graph;
5. регионы прорезаются в terrain;
6. дороги соединяют граф;
7. добавляются карманы, трещины, вода, кусты, цветы, грибы;
8. маленькие оторванные компоненты чистятся;
9. старт/цель ставятся и защищаются;
10. огромные мёртвые лесные массы прорезаются скрытыми clearing-ами;
11. connectivity repair исправляет критические разрывы;
12. validate проверяет карту.

### 5.1. Символы ASCII-карты

| Символ | TileType       | Terrain type          | Логика                                                                |
| :----: | :------------- | :-------------------- | :-------------------------------------------------------------------- |
| +      | GRASS          | grass                 | Обычная земля, базовая проходимая клетка.                             |
| .      | PATH           | old_overgrown_road    | Дорога/тропа, обычно дешёвое движение.                                |
| T      | TREE           | tree_blocker          | Лесной блокер. Обычно блокирует движение/обзор.                       |
| b      | BUSH           | bush_slow_concealment | Куст: замедление и/или маскировка.                                    |
| f      | FLOWER         | flower_decor          | Декор, обычно не должен ломать движение.                              |
| m      | MUSHROOM       | mushroom_decor        | Декор.                                                                |
| w      | WATER          | water_slow            | Вода/болото/низкое мокрое место; не путать с отрицательной elevation. |
| c      | CRACKED_GROUND | cracked_ground        | Разбитая земля, смысловой terrain.                                    |
| #      | RUIN_WALL      | ruin_wall_blocker     | Стена руин, жёсткий блокер.                                           |
| R      | RUIN_FLOOR     | ruin_floor            | Пол руин, проходимая область.                                         |
| S      | START          | start                 | Старт игрока.                                                         |
| G      | GOAL           | goal                  | Цель/выход.                                                           |

Нельзя строить игру только по этой таблице. Символы — исторический компактный слой. Новый consumer должен смотреть `terrain.json`, `collision.json`, `movement_costs.json`, `runtime_grids.json` и catalogs.

## 6. Tactical processing

После legacy engine генератор читает `_raw_tactical_map.json` и превращает его в более чистый runtime layer.

### 6.1. TacticalOptimizer

`TacticalOptimizer` выбирает и нормализует tactical-сущности: cover points, combat zones, flank routes, enemy spawns. Его задача — не допустить бесконтрольной каши из точек и зон.

### 6.2. FallbackPositionBuilder

Добавляет fallback positions — точки, куда AI или encounter logic могут отступать/перестраиваться.

### 6.3. ObjectiveProfileSelector

Профиль цели (`clear_map`, `survival`, `timed_breakthrough`) влияет на выбор enemy spawns и spawn policy. То есть карта может быть физически похожа, но gameplay-слой будет настроен под другой режим.

### 6.4. attach_tile_grid

Встраивает ASCII rows в runtime data и проверяет, что размеры совпадают с metadata. Это важный мост между legacy grid и публичным пакетом.

## 7. Runtime objects

`attach_runtime_layers()` размещает объекты поверх terrain. В v0.0.68 объектная система уже footprint-aware.

Из `runtime_objects.py`:

```python
MIN_ELEVATION_LEVEL = -5
MAX_ELEVATION_LEVEL = 20
MAX_RUNTIME_OBJECTS = 160
PASSABLE_OBJECT_TILES = frozenset({"+", ".", "R", "c"})
BLOCKED_OBJECT_TILES = frozenset({"T", "b", "w", "#", "S", "G"})
```

Это значит: runtime objects размещаются на ограниченном наборе passable terrain, не должны забивать старт/цель и не должны превращать карту в свалку.

Типы объектов включают:

- природные/декор: `fallen_log`, `stone_chunk`, `bush_thicket`;
- лут/интерес: `ammo_cache`, `medkit_cache`, `abandoned_backpack`;
- препятствия/укрытия: `car_wreck`, `earth_berm`, `scrap_pile`, `rusted_barrel`;
- elevation-объекты: `trench`, `pit`, `hill`, `stone_ramp`, `stone_stairs`, `wooden_bridge`;
- крупные landmark/structure: `watchtower`, `ancient_beacon`, `buried_bunker_2x2`, `buried_bunker_2x3`.

### 7.1. Footprint model

У runtime object есть несколько разных геометрий:

| Поле                 | Смысл                                                                 |
| :------------------- | :-------------------------------------------------------------------- |
| `anchor`             | Точка постановки объекта в tile-space.                                |
| `footprint`          | Все клетки, логически занятые объектом.                               |
| `collision_footprint`| Клетки, где действует collision profile.                              |
| `visual_bounds`      | Примерная область для рендера.                                        |
| `interaction_shape`  | Точки/форма взаимодействия.                                           |
| `sort_anchor`        | Подсказка сортировки отрисовки.                                       |
| `draw_layer`         | Слой отрисовки: terrain overlay, object, tall object и т.п.           |
| `occlusion_hint`     | Подсказка, может ли объект перекрывать актёра.                        |

Пример объекта `trench` из одного тестового запуска:

```json
{
  "id": "trench_000",
  "type": "trench",
  "role": "defensive_position",
  "anchor": [54, 170],
  "elevation": -1,
  "shape": "l_shape",
  "footprint": [[54, 170], [53, 170], [52, 170], [51, 170]],
  "collision_profile": {
    "movement": "passable",
    "projectiles": "passable",
    "vision": "passable"
  },
  "combat_properties": {
    "cover_value": 0.8,
    "concealment_value": 0.25,
    "stance_dependent": true
  }
}
```

Смысл: объект может занимать несколько тайлов, давать укрытие, менять height grid, но не обязательно блокировать движение.

## 8. Places — микролокации

`attach_places()` группирует runtime objects в смысловые сцены. Это уже уровень не “тайл/объект”, а “место на карте”.

Примеры типов:

- `abandoned_checkpoint`;
- `old_defensive_position`;
- `forest_obstruction`;
- `small_loot_pocket`;
- `secret_cache`;
- `bunker_outer_area`;
- `bunker_inner_area`;
- `dangerous_lowland`;
- `watchtower_area`.

Place содержит:

| Поле               | Назначение                                                        |
| :----------------- | :---------------------------------------------------------------- |
| `id/type/role`     | Идентичность и роль места.                                        |
| `story_role`       | Сюжетная роль: secret, landmark, old control point и т.п.         |
| `encounter_type`   | Тип потенциальной встречи.                                        |
| `danger_level`     | Риск зоны.                                                        |
| `loot_level`       | Потенциальная награда.                                            |
| `center/radius`    | Центр и радиус в tile-space.                                      |
| `bounds`           | Прямоугольные границы.                                            |
| `entrances`        | Входные точки со сторон bounds.                                   |
| `object_refs`      | Ссылки на объекты, из которых место собрано.                      |
| `connected_places` | Ближайшие смысловые связи с другими places.                       |
| `tags/biome_tags`  | Метки для AI director, renderer-а, сценариев.                     |

Это хороший слой для будущего квестового/сюжетного/AI-поведения. Не надо восстанавливать такие смыслы из отдельных камней и кустов — они уже собраны.

## 9. Elevation model

В v0.0.68 рельеф — это не один декоративный слой, а полноценная модель высот. Контракт диапазона: **-5..20**.

| Уровни | Имя в модели    | Смысл                                                | Правило                                   |
| :----: | :-------------- | :--------------------------------------------------- | :---------------------------------------- |
| < -1   | deep_lowland    | Глубокие низины, овраги, подземные подходы, впадины. | Обычно нужен явный переход или путь.      |
| -1     | below_ground    | Траншеи, ямы, внутренности бункеров, мелкая низина.  | Может быть walkable, если connected.      |
| 0      | ground          | Базовая поверхность.                                 | Обычное движение.                         |
| 1..4   | raised_ground   | Небольшие холмы, бермы, террасы.                     | Естественный slope или connector.         |
| 5..10  | hills           | Холмы, гряды, плато.                                 | Нужны slope/ramp/stairs или blocked edge. |
| 11..16 | highlands       | Высокие гряды, верхние руины, сильная позиция.       | Чаще нужен явный переход.                 |
| 17..20 | landmark_height | Редкие башни, пики, scripted vertical points.        | Обычно special case.                      |

Из `elevation_model.json` consumer получает:

- определения уровней;
- правила движения между уровнями;
- line-of-sight/projectile/render-order подсказки;
- список features;
- список transitions;
- summary по min/max/level_counts.

`height_grid` лежит в `runtime_grids.json`, а `elevation_model.json` объясняет, что эти числа значат.

### 9.1. Важное про воду и отрицательные уровни

Отрицательный height — **не обязательно вода**. Это глубина/низина/below-ground. Вода отдельно моделируется terrain/source-слоями и отчётами: `water_slow`, standing water, wet lowland и т.п.

То есть синяя/низкая зона в preview может означать “низкий уровень”, но gameplay water должен определяться не цветом preview, а terrain/elevation source/runtime rules.

### 9.2. Traversal repair

Elevation generator строит высоты, потом чинит 3D-проходимость. В отчёте одного запуска было:

```text
traversal repair: 1741 -> 0 unreachable, adjusted 1211 tiles, goal ok
```

Это значит, что рельеф не просто нарисовали — после него проверили достижимость и поправили проблемные клетки.

## 10. Terrain island repair

После runtime objects и до places/elevation запускается `repair_terrain_islands()`. Он удаляет маленькие walkable-острова, которые оторваны от основной проходимой компоненты, но учитывает structural/elevation points, чтобы не стереть важные места.

Результат пишется в:

```text
terrain_island_report.json
```

В одном default-прогоне:

```text
terrain islands: removed 7 small (13 tiles), preserved 0 large
```

Это хороший пример полезной “грязной” инженерии: генератор может породить мелкий мусор, repair его вычищает.

## 11. Map package export

`write_map_package()` создаёт публичный пакет. Упрощённо:

```python
write_json({"kind": "tile_grid", "rows": tile_grid}, outputs.map_package_tile_grid)
write_json({"kind": "terrain", "rows": terrain_rows}, outputs.map_package_terrain)
write_json({"kind": "movement_costs", "costs_by_tile": movement_costs}, outputs.map_package_movement_costs)
write_json(collision, outputs.map_package_collision)
write_json(markers, outputs.map_package_markers)
write_json(runtime_grids, outputs.map_package_runtime_grids)
write_json(world_graph, outputs.map_package_world_graph)
write_json(routes, outputs.map_package_routes)
write_json(gameplay_zones, outputs.map_package_gameplay_zones)
write_json(elevation_model, outputs.map_package_elevation_model)
```

Реальный код длиннее, но смысл именно такой: из runtime data строятся отдельные стабильные JSON-файлы, чтобы consumer не зависел от внутренних Python-классов.

## 12. Output root

| Путь                          | Тип     | Обязателен | Назначение                                                                     |
| :---------------------------- | :------ | :--------: | :----------------------------------------------------------------------------- |
| generated_map.txt             | ASCII   | Да         | Человеко-читаемая карта символов. Debug/legacy.                                |
| _raw_tactical_map.json        | JSON    | Debug      | Raw tactical output legacy engine до нормализации.                             |
| tactical_map.json             | JSON    | Да/legacy  | Монолитный runtime tactical слой старого формата.                              |
| tactical_map_debug.json       | JSON    | Debug      | Расширенный debug tactical слой.                                               |
| _manifest.json                | JSON    | Да         | Главная точка входа: версии, файлы, primary/debug outputs, validation summary. |
| validation_report.json        | JSON    | Да         | Структурная проверка результата и soft warnings.                               |
| world_density_report.json     | JSON    | Да         | Плотности terrain/collision/movement.                                          |
| elevation_density_report.json | JSON    | Да         | Плотности высот, география, transition stats.                                  |
| world_summary_report.json     | JSON    | Да         | Сводка для человека и внешних инструментов.                                    |
| object_catalog.md             | MD      | Нет        | Человекочитаемый каталог объектов/тайлов текущего запуска.                     |
| map_package/                  | каталог | Да         | Основной публичный контракт карты для игры/рендера.                            |
| layer_*.png                   | PNG     | Нет        | Preview/debug-слои, если render включён.                                       |

Структура `map_package/`:

```text
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
    tile_grid.json
    terrain.json
    movement_costs.json
    collision.json
    elevation.json
    start_goal.json
  gameplay/
    combat_zones.json
    cover_points.json
    choke_points.json
    flank_routes.json
    enemy_spawn_zones.json
    fallback_positions.json
  objects/
    runtime_objects.json
    places.json
  catalogs/
    tile_types.json
    object_types.json
  render/
    render_profile.json
    tile_render_hints.json
    object_render_hints.json
```

| Файл                       | Что содержит                                                                  | Кому нужен                              |
| :------------------------- | :---------------------------------------------------------------------------- | :-------------------------------------- |
| map.json                   | Индекс пакета: размеры, seed, координаты, ссылки на слои.                     | Любому consumer-у.                      |
| runtime_grids.json         | Movement/collision/projectile/vision/cover/concealment/height grids.          | Игре, AI, pathfinding, 3D renderer-у.   |
| markers.json               | Start/goal и markers из runtime-объектов: loot/story/POI/defensive point.     | Gameplay, spawn, quest/POI logic.       |
| world_graph.json           | Семантические nodes/edges/main_path/side_paths/dead_ends/secret areas.        | AI director, pacing, world reasoning.   |
| routes.json                | Маршруты как намерение: main_road, side_path, patrol_route, escape_route.     | AI, сценарии, encounter logic.          |
| gameplay_zones.json        | Safe/loot/encounter/danger/secret/story/extraction zones.                     | Игровые режимы и баланс.                |
| elevation_model.json       | Семантика уровней -5..20, правила движения/LoS/render order.                  | 3D/2.5D consumer, физика, видимость.    |
| elevation_features.json    | Конкретные elevation features: pits, trenches, hills, bridges, ramps, stairs. | Renderer, editor, navigation.           |
| elevation_transitions.json | Соседние переходы высот и suggested connectors.                               | Movement validation, 3D traversal.      |
| layers/*.json              | Базовые слои: tile_grid, terrain, movement, collision, elevation, start_goal. | Loader, debug, editor.                  |
| objects/*.json             | Runtime objects и places.                                                     | Scene builder, gameplay logic.          |
| catalogs/*.json            | Типы terrain/object и их свойства.                                            | Чтобы не хардкодить поведение в игре.   |
| render/*.json              | Render profile и hints.                                                       | Renderer/preview, но не gameplay logic. |

## 13. `map.json` — индекс пакета

`map.json` — первый файл внутри `map_package/`. Он содержит размеры, координаты, seed, профиль и относительные пути.

Пример:

```json
{
  "schema_version": "map-package-map-v11",
  "package_schema_version": "map-package-v1",
  "generator_version": "0.0.68",
  "pipeline_version": "pipeline-v1",
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
  "runtime_grids": "runtime_grids.json",
  "objects": {
    "runtime_objects": "objects/runtime_objects.json",
    "places": "objects/places.json"
  }
}
```

Все relative paths считаются относительно папки `map_package/`.

## 14. Layers

| Layer               | Формат                   | Смысл                                                                         |
| :------------------ | :----------------------- | :---------------------------------------------------------------------------- |
| tile_grid.json      | ascii_rows               | Компактная исходная сетка символов. Нужна для debug и обратной совместимости. |
| terrain.json        | type_rows                | Смысловые terrain-типы: grass, tree_blocker, water_slow и т.д.                |
| movement_costs.json | dict                     | Стоимость движения по symbol/type.                                            |
| collision.json      | boolean rows             | Готовая terrain collision grid: 0 passable, 1 blocked.                        |
| elevation.json      | explicit cells + default | Слой высот из tactical runtime data.                                          |
| start_goal.json     | points                   | Старт и цель из tile_grid.                                                    |

### 14.1. Почему есть и `tile_grid`, и `terrain`

`tile_grid` удобен человеку и legacy-инструментам. `terrain` удобен игре: там уже типы вроде `tree_blocker`, `water_slow`, `ruin_floor`, а не символы `T`, `w`, `R`.

Правильно:

```text
runtime logic -> terrain/collision/movement/runtime_grids/catalogs
ASCII/debug    -> tile_grid/generated_map.txt
```

Неправильно:

```text
if tile == "T": block_actor()
```

Почему неправильно: типы и свойства могут развиваться, а catalogs уже дают machine-readable контракт.

## 15. Runtime grids

| Grid                  | Формат       | Использование                                                                              |
| :-------------------- | :----------- | :----------------------------------------------------------------------------------------- |
| movement_grid         | numeric_rows | Pathfinding cost. Нельзя использовать вместо collision.                                    |
| collision_grid        | boolean_rows | Terrain blocked/passable. Object movement blockers читаются из runtime_objects footprints. |
| projectile_block_grid | boolean_rows | Блокировка снарядов terrain + object projectile blockers.                                  |
| vision_block_grid     | boolean_rows | Блокировка обзора terrain + object vision blockers.                                        |
| cover_grid            | numeric_rows | Максимальная сила укрытия на клетке.                                                       |
| concealment_grid      | numeric_rows | Максимальная сила маскировки на клетке.                                                    |
| height_grid           | integer_rows | Высота/глубина клетки. Диапазон контракта -5..20.                                          |

Код построения показывает важный нюанс: terrain collision остаётся в `collision_grid`, а object blockers дополнительно отражаются в projectile/vision grids и самих object footprints.

```python
if profile.get("movement") == "blocked":
    # Collision grid is terrain-derived. Keep object blockers in projectile/vision
    # grids and expose object movement blockers through runtime object footprints.
    pass
if profile.get("projectiles") == "blocked":
    projectile_grid[y][x] = "1"
if profile.get("vision") in {"blocked", "soft_blocked"}:
    vision_grid[y][x] = "1"
cover_grid[y][x] = max(cover_grid[y][x], _float_value(combat.get("cover_value")))
concealment_grid[y][x] = max(
    concealment_grid[y][x],
    _float_value(combat.get("concealment_value")),
)
```

Следствие для игры: итоговая collision scene должна учитывать **и** `collision_grid`, **и** `runtime_objects.collision_footprint` с `collision_profile.movement`.

## 16. Markers

`markers.json` содержит gameplay markers:

- `start`;
- `goal`;
- `loot`;
- `story`;
- `point_of_interest`;
- `defensive_point`.

Marker может быть создан из `tile_grid` или из runtime object. Например, `ammo_cache` и `medkit_cache` становятся `loot`, landmark-объекты — `point_of_interest`, bunker — `defensive_point`.

Не надо искать start/goal в ASCII, если уже загружен пакет. Читайте `markers.json` или `layers/start_goal.json`.

## 17. World graph

`world_graph.json` — семантический граф карты. Это не tile pathfinding.

Он содержит:

| Поле           | Смысл                                                               |
| :------------- | :------------------------------------------------------------------ |
| `nodes`        | Places и важные markers: start, goal, loot, story, POI.             |
| `edges`        | Смысловые связи между nodes.                                        |
| `main_path`    | Примерный основной маршрут start → goal через важные места.         |
| `side_paths`   | Боковые ветки: loot/danger/hidden/side paths.                       |
| `dead_ends`    | Осмысленные тупики, если они есть.                                  |
| `secret_areas` | Секретные/высоконаградные места.                                    |
| `quality`      | Краткая оценка покрытия и связности графа.                          |

Использовать так:

```text
runtime_grids = точное движение по тайлам
world_graph   = смысловая структура мира
routes        = намерение маршрутов
```

## 18. Routes

`routes.json` строится из `world_graph.json`. Он отвечает не на вопрос “как пройти по каждой клетке?”, а на вопрос “какая роль у этого маршрута?”.

Возможные route types:

- `main_road` — основной intended route;
- `side_path` — боковая ветка;
- `hidden_path` — скрытый путь;
- `patrol_route` — маршрут патруля;
- `escape_route` — путь отхода/выхода.

Для реального движения всё равно нужен pathfinding по `runtime_grids`.

## 19. Gameplay zones

`gameplay_zones.json` — слой назначения областей. Он не заменяет `combat_zones.json`, а обобщает смысл зон.

Типы зон:

| Тип              | Смысл                                                   |
| :--------------- | :------------------------------------------------------ |
| `safe_area`      | Безопасная зона, обычно вокруг старта.                  |
| `encounter_area` | Общая зона столкновения.                                |
| `ambush_area`    | Засада/опасный контакт.                                 |
| `loot_area`      | Награда/тайник/ресурсы.                                 |
| `boss_area`      | Сильное столкновение, если режим игры это использует.   |
| `stealth_area`   | Зона скрытного прохождения.                             |
| `traversal_area` | Зона прохода/перепада/препятствия.                      |
| `secret_area`    | Секрет или награда за исследование.                     |
| `danger_area`    | Повышенный риск.                                        |
| `story_area`     | Сюжетная/landmark зона.                                 |
| `extraction_area`| Выход/цель.                                             |

Каждая зона может иметь bounds, polygon, entry/exit points, linked_places/routes/markers, danger/loot levels, recommended enemy types и elevation usage.

## 20. Catalogs

`catalogs/tile_types.json` и `catalogs/object_types.json` нужны, чтобы игра не держала таблицу “магических строк”.

Например, вместо:

```text
если terrain_type == "tree_blocker" -> blocked
```

лучше:

```text
tile_def = tile_types[terrain_type]
walkable = tile_def.walkable
movement_cost = tile_def.movement_cost
```

Catalog — это слой machine-readable смысла. Render hints — это слой визуализации.

## 21. Render hints

`render/*.json` не является gameplay source of truth.

| Каталог render | Назначение                                        |
| :------------- | :------------------------------------------------ |
| `render_profile.json` | Общие настройки рендера пакета.             |
| `tile_render_hints.json` | Подсказки по terrain/tile типам.        |
| `object_render_hints.json` | Подсказки по object types.             |

Правило:

```text
catalogs/ = что это значит для игры
render/   = как это можно нарисовать
```

## 22. Validation и reports

После генерации пишутся:

| Файл                         | Что проверяет/описывает                                      |
| :--------------------------- | :------------------------------------------------------------ |
| `validation_report.json`     | Наличие файлов, схемы, размеры, ссылки, start/goal, objects, places, graph/routes/elevation consistency. |
| `world_density_report.json`  | Плотность forest/road/swamp/ruins/open ground, collision, movement. |
| `elevation_density_report.json` | Распределение уровней, география, transitions, traversal repair. |
| `world_summary_report.json`  | Общий человекочитаемый summary текущего мира.                 |
| `terrain_island_report.json` | Что сделал terrain island repair.                            |
| `_manifest.json`             | Версии схем, список файлов, primary/debug outputs, timings, validation summary. |

Пример summary одного default-прогона v0.0.68:

```text
map:    192 x 192 = 36864 tiles
status: ok
forest: 15902 tiles = 43.1%
blocked: 16753 tiles = 45.4%
underground -5..-1: 2872 tiles = 7.8%
ground 0: 14278 tiles = 38.7%
raised 1..4: 11641 tiles = 31.6%
runtime objects: 140
places: 11
routes: 42
markers: 32
```

Эти числа не фиксированные: seed random. Но структура отчёта и смысл метрик стабильны для версии.

## 23. `_manifest.json`

Manifest — лучшая точка входа для внешнего инструмента. Он содержит:

- `schema_version`;
- `versions.generator`;
- `versions.schemas`;
- seed/resolved_seed/profile;
- dimensions;
- timings;
- render flags;
- validation summary;
- списки `primary_outputs`, `debug_outputs`, `files`.

Consumer должен начинать с `_manifest.json`, находить `kind = "map_package:index"`, потом открывать `map_package/map.json`.

## 24. Рекомендуемый consumer pipeline

| Шаг | Файл                         | Действие                                                                              |
| --: | :--------------------------- | :------------------------------------------------------------------------------------ |
| 1   | _manifest.json               | Проверить версию генератора, schema versions, найти primary output map_package:index. |
| 2   | map_package/map.json         | Прочитать размеры, координатную модель, relative paths.                               |
| 3   | runtime_grids.json           | Создать movement/collision/projectile/vision/cover/concealment/height scene grids.    |
| 4   | markers.json                 | Поставить start/goal, POI, loot/story markers.                                        |
| 5   | catalogs/*.json              | Загрузить свойства terrain/object types.                                              |
| 6   | objects/runtime_objects.json | Создать объекты с footprint/collision/combat/interaction/render hints.                |
| 7   | objects/places.json          | Собрать микролокации и связи между ними.                                              |
| 8   | world_graph.json/routes.json | Подключить семантическую структуру мира и intent маршрутов.                           |
| 9   | gameplay_zones.json          | Настроить encounters, danger/loot/story/secret areas.                                 |
| 10  | render/*.json                | Использовать только для визуального слоя, не как gameplay source of truth.            |

Минимальный loader для первого запуска игры:

```text
open output/_manifest.json
open map_package/map.json
load runtime_grids.json
load markers.json
load objects/runtime_objects.json
spawn player at marker:start
build terrain collision from collision_grid + object movement blockers
build height scene from height_grid
spawn objects from runtime_objects
```

## 25. Что считать hard error

Consumer должен отказаться грузить пакет, если:

- нет `_manifest.json` и нет fallback `map_package/map.json`;
- `map.json` ссылается на отсутствующие обязательные файлы;
- размеры grid-слоя не совпадают с `width x height`;
- нет start/goal, если режим игры их требует;
- start/goal вне карты или заблокированы итоговой collision scene;
- runtime object имеет неизвестный type;
- footprint объекта выходит за границы;
- `world_graph` или `routes` ссылаются на несуществующие nodes/edges, если consumer использует эти слои.

Soft warnings из validation можно логировать и показывать в debug UI, но не всегда надо падать. Например, карта может быть структурно валидной, но иметь warning по качеству main path elevation reachability.

## 26. Типовые ошибки понимания

### Ошибка 1: “Синее/низкое = вода”

Нет. Цвет preview может показывать высоту. Отрицательный height — это низина/below-ground. Вода — terrain/source/standing water. Для gameplay воды нужно читать terrain/runtime rules, не цвет.

### Ошибка 2: “ASCII достаточно для игры”

Не-а. ASCII удобен, но он слишком бедный. Он не содержит object footprints, cover values, concealment, semantic graph, routes, gameplay zones, elevation transitions.

### Ошибка 3: “world_graph заменяет pathfinding”

Нет. `world_graph` показывает смысловые связи. Точный путь строится по `runtime_grids`.

### Ошибка 4: “collision_grid уже содержит все object blockers”

В v0.0.68 terrain collision и object collision разделены. Object blockers нужно учитывать через `runtime_objects.collision_footprint` и `collision_profile`.

### Ошибка 5: “render hints можно использовать как gameplay”

Не надо. Render hints — визуальный слой. Gameplay-логика должна идти из runtime grids, catalogs, objects, places, zones.

## 27. Быстрые команды для проверки

```bash
# Сгенерировать без PNG
PYTHONPATH=. python3 top_down_generator.py \
  --config configs/default.json \
  -o output \
  --no-render

# Сгенерировать и вывести summary в файл
PYTHONPATH=. python3 top_down_generator.py \
  --config configs/default.json \
  -o output \
  --no-render \
  --summary-file output/summary.txt

# Прочитать пакет как внешний consumer
PYTHONPATH=. python3 examples/read_map_package.py output

# Проверить world package
PYTHONPATH=. python3 examples/inspect_world_package.py output

# Сделать preview из публичных файлов
PYTHONPATH=. python3 examples/render_world_preview.py output --semantic-overlays --grid --cell-size 8
```

## 28. Практический вывод

Для дальнейшей интеграции в игру/3D-клиент нужно относиться к результату так:

```text
output root      = один запуск генератора
_manifest.json   = точка входа и список артефактов
map_package/     = публичный контракт мира
generated_map.txt = debug/legacy представление
PNG              = preview, не gameplay source
```

Нормальный внешний loader не должен импортировать Python-модули генератора и не должен угадывать смысл по цветам preview. Он должен читать `map_package/`, проверять schema versions, строить runtime scene из grids/catalogs/objects и уже поверх этого добавлять renderer, AI, физику, разрушение и gameplay.

Коротко: **TopDownMapGen v0.0.68 уже выдаёт карту как данные для игры, а не как картинку.**
