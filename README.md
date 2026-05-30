# TopDownMapGen

TopDownMapGen — процедурный генератор top-down карты для игры. Главный результат проекта — не картинка, а структурированный `world package`: terrain, runtime grids, collision, movement, objects, places, routes, world graph, gameplay zones and elevation data.

Визуальный pipeline в проекте есть и запускается штатно, но он является слоем отображения поверх уже сгенерированных данных карты. Он не должен менять gameplay, collision, routes, start/goal или семантику мира.

## Быстрый запуск

```bash
./r
```

Стандартный запуск делает полный pipeline:

1. очищает старый `output/`;
2. генерирует world package;
3. строит visual map для профиля `dark_forest`;
4. генерирует debug step PNG для visual pipeline;
5. генерирует placeholder asset pack при необходимости;
6. генерирует asset registry preview;
7. печатает итоговый summary;
8. завершает работу.

Основные результаты появляются в `output/`.

## Частые команды

```bash
./r              # полный стандартный pipeline
./r world        # только world package
./r visual       # visual map из уже существующего output/map_package
./r visual-debug # PNG-шаги visual pipeline из уже существующего output/map_package
./r summary      # итоговый отчёт по текущему output/
./r inspect      # инспекция world package
./r test         # compileall + asset manifest validation + pytest
./r help         # список команд и переменных окружения
```

## Основные директории проекта

```text
top_down_worldgen/      ядро генерации мира
top_down_visualgen/     визуальный слой поверх world package
configs/                публичные конфиги генерации
assets/dark_forest/     PNG-ассеты visual profile dark_forest
bin/                    dev/runtime утилиты
examples/               примеры чтения и отладки output package
docs/                   актуальная документация по проекту
tests/                  pytest-тесты
output/                 результат текущего запуска, не исходники проекта
```

## Главный output

Стабильная точка входа для внешних consumers:

```text
output/_manifest.json
output/map_package/map.json
```

`_manifest.json` описывает один запуск генератора и список артефактов. `map_package/map.json` — индекс структурированного пакета мира.

Важные файлы внутри `output/map_package/`:

```text
layers/terrain.json
layers/tile_grid.json
layers/collision.json
layers/movement_costs.json
layers/elevation.json
runtime_grids.json
objects/runtime_objects.json
objects/places.json
markers.json
routes.json
world_graph.json
gameplay_zones.json
elevation_model.json
elevation_transitions.json
```

## Visual output

Visual pipeline пишет результаты сюда:

```text
output/visual_map/
```

Основные visual-файлы:

```text
output/visual_map/visual_map.json
output/visual_map/visual_layers.json
output/visual_map/visual_objects.json
output/visual_map/visual_chunks.json
output/visual_map/preview.png
output/visual_map/final_render.png
output/visual_map/debug/
```

`preview.png` и `final_render.png` — это изображения, а не gameplay contract. Внешняя игра или редактор должны опираться на `map_package/`, если им нужны правила мира.

## Документация

- `docs/COMMANDS.md` — команды запуска и переменные окружения.
- `docs/ARCHITECTURE.md` — границы worldgen и visualgen.
- `docs/OUTPUT_FORMAT.md` — актуальная структура `output/`.
- `docs/map_package_v1.md` — контракт `map_package/`.
- `docs/game_consumer_guide.md` — как игре читать package.
- `docs/world_building_algorithm.md` — порядок построения runtime-мира во внешнем проекте.
- `docs/world_package_file_map.md` — карта файлов output root.
- `docs/visual_*.md` — актуальные документы visual layer `dark_forest`.

## Правило проекта

World generation — ядро. Visual generation — потребитель и слой отображения. Если visual layer падает или меняется, это не должно менять смысл данных в `output/map_package/`.
