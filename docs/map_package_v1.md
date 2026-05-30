# Map package v1

`map_package/` — стабильный структурированный экспорт карты. Это главный контракт проекта для игры, редактора, визуализатора и тестов.

Генератор создаёт не финальную картинку, а описание мира:

- terrain;
- tile grid;
- collision;
- movement costs;
- runtime grids;
- objects and places;
- markers;
- routes;
- world graph;
- gameplay zones;
- elevation model/features/transitions;
- render hints.

PNG и ASCII — представления. `map_package/` — источник истины.

## Точка входа

Обычный путь:

```text
output/_manifest.json
  -> artifact kind = map_package:index
  -> output/map_package/map.json
```

Fallback для tools допустим:

```text
output/map_package/map.json
```

## Индекс `map.json`

`map.json` содержит:

- generator version;
- seed/resolved seed;
- dimensions;
- coordinate model;
- ссылки на layers;
- ссылки на gameplay data;
- ссылки на objects/catalogs/render hints;
- ссылки на legacy outputs.

Все пути внутри `map.json` относительны к папке `map_package/`.

## Основные секции пакета

```text
layers/      базовые карты terrain/collision/movement/elevation
objects/     runtime objects и semantic places
gameplay/    combat/cover/spawn/fallback tactical data
catalogs/    описание tile/object типов
render/      hints для render consumers
```

Отдельные top-level файлы `map_package/`:

```text
runtime_grids.json
markers.json
routes.json
world_graph.json
gameplay_zones.json
elevation_model.json
elevation_features.json
elevation_transitions.json
```

## Координаты

Карта tile-based. Runtime consumers должны считать `x/y` tile coordinates основной системой. Pixel coordinates используются только renderer/tools и зависят от `tile_size_px`.

## Совместимость

Legacy файлы `generated_map.txt`, `tactical_map.json` и `tactical_map_debug.json` пока остаются рядом с `map_package/`, но новый consumer должен начинать с `_manifest.json` и `map_package/map.json`.
