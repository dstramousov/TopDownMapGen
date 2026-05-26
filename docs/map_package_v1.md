# Map package v1

`map_package/` — это стабильный структурированный экспорт карты для игры, редактора, рендера и тестов. Он создаётся рядом со старым монолитным `tactical_map.json` и не заменяет legacy-файлы. Старый экспорт остаётся полезным для отладки и обратной совместимости, а `map_package/` становится новым контрактом данных.

## Зачем нужен пакет

Генератор строит не картинку, а описание мира: поверхность, движение, коллизии, высоты, объекты, места и тактические слои. Разные потребители читают разные части пакета:

- игра читает `collision`, `movement_costs`, `runtime_objects`, `enemy_spawn_zones`, `points`;
- renderer читает `tile_grid`, `runtime_objects` и позже catalog/render hints;
- validation читает обязательные слои и проверяет связность данных;
- редактор может читать `places`, `combat_zones`, `cover_points` и overlay-слои.

Главное правило: PNG и ASCII — это представления. `map_package/` — это контракт мира.

## Точка входа

Потребитель должен начинать с `_manifest.json`. В нём нужно найти primary output с kind `map_package:index` и открыть указанный файл. Обычно это:

```text
map_package/map.json
```

`map.json` — индекс пакета. Он содержит размеры карты, seed, профиль генерации, систему координат и относительные пути к слоям.


## Единый output root с v0.0.29

Один запуск генератора создаёт один связанный output root. Все legacy-файлы, `map_package/`, validation report, manifest, metrics и PNG-слои одного мира должны лежать в одной папке результата.

CLI `-o/--out` принимает два варианта:

```text
-o output
-o output/generated_map.txt
```

Оба варианта создают один и тот же контракт результата:

```text
output/
  generated_map.txt
  tactical_map.json
  tactical_map_debug.json
  _raw_tactical_map.json
  _manifest.json
  validation_report.json
  metrics.txt
  object_catalog.md
  map_package/
    map.json
    layers/
    gameplay/
    objects/
    catalogs/
    render/
```

Главное правило: потребитель получает путь к output root, открывает `_manifest.json` и дальше читает только файлы, перечисленные в manifest или `map_package/map.json`. Не нужно искать часть результата в `out/`, часть в `output/`, часть рядом с проектом.

## Структура каталогов

```text
map_package/
  map.json
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

## Координаты

Все координаты в `map_package/` используют tile-space:

```text
origin: top_left
x_axis: right
y_axis: down
unit: tile
```

То есть клетка `[0, 0]` находится в левом верхнем углу. `x` увеличивается вправо, `y` увеличивается вниз. Pixel-space вычисляется игрой или renderer-ом через `tile_size_px`.

## map.json

`map.json` содержит общую информацию и ссылки на остальные файлы.

Ключевые поля:

- `schema_version` — версия схемы индекса пакета;
- `package_schema_version` — версия пакета в целом;
- `generator_version` — версия генератора;
- `seed` и `resolved_seed` — исходный и фактический seed;
- `profile` — профиль генерации;
- `dimensions` — ширина, высота и размер тайла;
- `coordinates` — система координат;
- `points` — старт и цель, если они найдены;
- `layers` — относительные пути к слоям;
- `gameplay` — относительные пути к tactical/gameplay слоям;
- `objects` — относительные пути к runtime-объектам и places;
- `legacy_outputs` — ссылки на старые output-файлы;
- `render` — относительные пути к renderer-ready подсказкам.

## layers/tile_grid.json

Базовая сетка карты в формате ASCII rows. Это самый близкий слой к старому `generated_map.txt`, но теперь он лежит в машинном JSON-контракте.

Ключевые поля:

- `width`, `height` — размеры сетки;
- `format` — сейчас `ascii_rows`;
- `tile_legend` — расшифровка символов;
- `tile_counts` — количество символов;
- `rows` — массив строк одинаковой длины.

Этот слой удобен для debug, базового renderer-а и первичной загрузки карты. Игра не должна навечно хардкодить символы как единственный источник истины: для движения и блокировки нужно использовать `movement_costs` и `collision`.

## layers/movement_costs.json

Слой стоимости движения по типам тайлов. Сейчас он хранит `costs_by_tile`, где ключ — символ или тип тайла из grid, а значение — стоимость движения.

Пример смысла:

- `1` — обычная стоимость;
- `2` или `3` — замедление;
- отсутствие тайла в `costs_by_tile` не должно автоматически означать passable. Для passability нужно читать `collision.json`.

## layers/collision.json

Слой базовой проходимости. Сейчас он содержит:

- `blocked_tiles` — символы тайлов, считающихся непроходимыми;
- `passable_tiles` — символы тайлов, считающихся проходимыми;
- `source` — источник построения слоя.

Это минимальная v1-форма. В следующих версиях слой может стать полноценной матрицей collision-классов, чтобы игре не приходилось интерпретировать символы.

## layers/elevation.json

Слой высот и углублений. Сейчас он хранит данные elevation, созданные tactical pipeline, например клетки окопов или ям уровня `-1`.

Игра может игнорировать этот слой на первом этапе, если в ней ещё нет высот, stance logic или баллистики по высоте.

## gameplay/*.json

Gameplay-слои описывают tactical analysis карты:

- `combat_zones.json` — зоны столкновений;
- `cover_points.json` — точки укрытий;
- `choke_points.json` — узкие места;
- `flank_routes.json` — маршруты обхода;
- `enemy_spawn_zones.json` — зоны появления врагов;
- `fallback_positions.json` — позиции отхода.

Каждый файл содержит `items`. Потребитель может читать только нужные слои. Например, первая версия игры может использовать только `enemy_spawn_zones`, а `flank_routes` оставить на потом.

## objects/runtime_objects.json

Runtime-объекты — это сущности поверх tile grid: брёвна, камни, бочки, тайники, палатки, окопы, машины, колодцы и другие игровые объекты.

Этот слой нужен игре и renderer-у. Игра использует его для collision, cover, loot, interaction и danger logic. Renderer использует его для выбора sprite/object visuals.

Важное правило: крупные объекты не надо превращать в terrain tiles. Они должны оставаться объектами.

## objects/places.json

`places` — смысловые микролокации: блокпост, радиоточка, оборонительная позиция, лесной завал, руинная площадка. Это не отдельные тайлы и не обязательно physical objects. Это группировка объектов и зон в маленькую сцену.

Игра может использовать `places` для заданий, интересных точек, narrative events и spawn rules.

## Обязательные файлы v1

Минимальный валидный пакет должен содержать:

```text
map_package/map.json
map_package/layers/tile_grid.json
map_package/layers/terrain.json
map_package/layers/movement_costs.json
map_package/layers/collision.json
map_package/layers/elevation.json
map_package/layers/start_goal.json
map_package/objects/runtime_objects.json
map_package/objects/places.json
map_package/catalogs/tile_types.json
map_package/catalogs/object_types.json
```

Gameplay-слои сейчас тоже генерируются штатно, но игра может игнорировать часть из них.

## Совместимость

`map_package/` не отменяет старые файлы. Пока формат стабилизируется, допускается сравнивать данные с:

```text
generated_map.txt
tactical_map.json
tactical_map_debug.json
```

Но новые потребители должны начинать с `_manifest.json` и `map_package/map.json`.

## Что будет дальше

Ближайшие расширения формата:

- отдельный `terrain.json` вместо зависимости от символов;
- более явный `collision` layer как матрица классов;
- machine-readable catalogs для tile/object types;
- renderer hints для autotile и sprite selection;
- экспорт в Tiled/Godot/собственный runtime format.


## v0.0.26 layer additions

`map_package v1` теперь содержит два дополнительных runtime-friendly слоя:

- `layers/terrain.json` — сетка типов поверхности в формате `type_rows`. Игра может читать `grass`, `old_overgrown_road`, `tree_blocker`, `ruin_wall_blocker` и другие типы без прямой зависимости от ASCII-символов.
- `layers/start_goal.json` — явный слой стартовой и целевой точки. Поле `points` в `map.json` остаётся для совместимости, но новым потребителям лучше читать этот слой.

`layers/collision.json` использует schema `collision-layer-v2` и формат `boolean_rows`:

```json
{
  "format": "boolean_rows",
  "legend": {
    "0": "passable",
    "1": "blocked"
  },
  "rows": ["0010", "1110"]
}
```

Старые поля `legacy_blocked_tiles` и `legacy_passable_tiles` оставлены только для диагностики и переходного периода. Игровой runtime должен использовать `rows`, `blocked_tile_types` и `passable_tile_types`.

`layers/movement_costs.json` дополнен `costs_by_type`. Это позволяет читать стоимость движения по типам поверхности, а не по ASCII-символам.

## v0.0.27 catalogs

`map_package v1` теперь содержит машинные каталоги типов:

```text
map_package/catalogs/
  tile_types.json
  object_types.json
```

`catalogs/tile_types.json` описывает типы поверхности, которые встречаются в `terrain.json`:

- `symbol` — legacy ASCII-символ для диагностики;
- `movement_cost` — стоимость движения, если она известна;
- `collision` — `passable`, `blocked` или `unknown`;
- `walkable` — быстрый boolean-флаг для game loader-а;
- `tags` — простые семантические признаки: `road`, `water`, `blocker`, `vegetation`, `ruin`, `decor`, `marker`.

`catalogs/object_types.json` агрегирует runtime-объекты по типу. Это не список экземпляров, а справочник типов, построенный из фактически сгенерированных объектов текущей карты:

- `role`;
- `cover_type`;
- `height`;
- `elevation`;
- `blocks_movement`;
- `blocks_projectiles`;
- `blocks_vision`;
- `interactive`;
- `collision_profile`;
- `combat_properties`;
- `tags`;
- `instance_count`.

Игра теперь может не хардкодить смысл `tree_blocker`, `water_slow`, `fallen_log`, `stone_chunk`, `trench` и других типов. На первом этапе catalogs можно читать как runtime metadata. Позже их можно будет заменить или дополнить внешними tileset/objectset definition-файлами.

## v0.0.28 render hints

`map_package v1` теперь содержит renderer-ready подсказки. Это не готовый tileset и не привязка к конкретному PNG-атласу. Это промежуточный контракт между семантической картой и будущим renderer-ом.

```text
map_package/render/
  render_profile.json
  tile_render_hints.json
  object_render_hints.json
```

`render/render_profile.json` описывает общий профиль рендера:

- размеры карты и `tile_size_px`;
- рекомендуемый порядок рисования слоёв;
- ссылки на входные слои, каталоги и hint-файлы;
- правило, что hint-ы являются семантическими и могут иметь fallback.

`render/tile_render_hints.json` объясняет, как потенциально рисовать типы поверхности из `layers/terrain.json`:

- `render_mode = single_tile` — обычный одиночный тайл;
- `render_mode = autotile` — renderer должен выбирать вариант по соседям;
- `visual_group` — стабильная семантическая группа будущего tileset-а;
- `draw_layer` — рекомендуемый слой отрисовки;
- `variant_policy` — как выбирать варианты;
- `blend_edges` — можно ли визуально смешивать края с соседями.

Например, `old_overgrown_road`, `water_slow` и `ruin_wall_blocker` получают `autotile`-подсказки, но генератор всё ещё не требует конкретных PNG-файлов.

`render/object_render_hints.json` объясняет, как потенциально рисовать runtime-объекты из `objects/runtime_objects.json`:

- `visual_group` — семантическая группа будущих sprite/object assets;
- `draw_layer` — где рисовать объект относительно terrain/actor/debug;
- `anchor` — базовая точка привязки;
- `orientation_source` — поле экземпляра, из которого renderer может брать ориентацию;
- `footprint_source` — поле экземпляра, из которого renderer может брать footprint.

Игра может полностью игнорировать каталог `render/`. Он нужен renderer-у, редактору и будущему tileset pipeline. Runtime-логика должна продолжать опираться на `layers/`, `objects/`, `gameplay/` и `catalogs/`.

## External inspection since v0.0.30

`examples/inspect_world_package.py` is a small external-consumer smoke checker for `map_package v1`.

It accepts any common public entrypoint:

```bash
python3 examples/inspect_world_package.py output
python3 examples/inspect_world_package.py output/_manifest.json
python3 examples/inspect_world_package.py output/map_package
python3 examples/inspect_world_package.py output/map_package/map.json
```

The inspector verifies that the package can be loaded from public artifacts only. It checks the manifest entrypoint, `map.json`, layer dimensions, collision encoding, movement costs, elevation summary, object counts, gameplay layer counts, catalogs, and render hint counts.

This tool is not the game loader and not a visual renderer. It is a consumer-contract smoke test: if it passes, an external project has enough information to start loading the generated world package without reading generator internals.

## Visual preview smoke test

`examples/render_world_preview.py` is a tiny external preview renderer for `map_package v1`.
It is intentionally not a game renderer and not a final art pipeline. Its job is to prove that
an external consumer can resolve `_manifest.json`, read `map_package/map.json`, load public layers,
and produce a visible world preview without importing generator internals.

Typical usage:

```bash
python3 examples/render_world_preview.py output
```

Alternative entrypoints:

```bash
python3 examples/render_world_preview.py output/_manifest.json
python3 examples/render_world_preview.py output/map_package
python3 examples/render_world_preview.py output/map_package/map.json
```

Useful options:

```bash
python3 examples/render_world_preview.py output --collision-overlay
python3 examples/render_world_preview.py output --cell-size 8 --grid
python3 examples/render_world_preview.py output --no-objects
python3 examples/render_world_preview.py output --output output/debug/world_preview.png
```

By default it writes:

```text
output/world_preview.png
```

The preview is a visual smoke test only. It uses simple semantic colors and object markers instead
of production sprites. A game renderer should still read the same package contract and apply its own
asset pipeline.

## Object footprints

Object instances are no longer guaranteed to be single-tile markers. Consumers must read `footprint`, `collision_footprint`, `visual_bounds`, and `pivot` from `objects/runtime_objects.json` instead of assuming that `x`/`y` is the full object size.

The `x`, `y`, `position`, and `anchor` fields identify the object's anchor tile. The `footprint` field is the logical occupied shape. The `collision_footprint` field is the subset where the object affects movement, projectiles, or vision according to its `collision_profile`. The `visual_bounds` field is a coarse tile-space rectangle for preview/render placement. Bunker-like objects may also expose `firing_ports`, `surface_elevation`, and `interior_elevation`; consumers should treat those as gameplay metadata, not as sprite instructions.


## Generation tuning

`map_package/map.json` and `_manifest.json` expose the `generation_tuning` block copied from the public config. These values are user-facing knobs for changing the generated world density: water, forests, open spaces, ruins, buildings, road width, decoration, and bunkers. Water has dedicated controls: `water_scale`, `water_patch_count_scale`, `water_patch_size_scale`, and `water_patch_density`. Consumers should treat these values as provenance/diagnostics, not as runtime rules. The generated layers and catalogs remain the source of truth for the final world.

Non-critical quality violations caused by aggressive tuning are reported as warnings in `generation.log`, `_manifest.json`, and `validation_report.json`; they should not be treated as engine crashes unless a required file or structural layer is missing.
