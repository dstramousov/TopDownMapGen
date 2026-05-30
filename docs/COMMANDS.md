# Commands

Этот документ описывает актуальные команды запуска проекта.

## Основная команда

```bash
./r
```

Полный стандартный pipeline:

```text
cleanup -> world generation -> visual pipeline -> visual debug steps -> asset pack -> asset registry preview -> summary
```

Команда должна завершаться самостоятельно и печатать итоговый summary.

## Команды `./r`

| Команда | Назначение |
|---|---|
| `./r` или `./r all` | Полный стандартный pipeline. |
| `./r world` | Очистить output и сгенерировать только world package. |
| `./r preview` | Построить debug world preview из существующего `output/`. |
| `./r visual` | Построить visual output из существующего `output/map_package/`. |
| `./r visual-debug` | Построить PNG-шаги visual pipeline. |
| `./r final-render` | Пересобрать `output/visual_map/final_render.png`. |
| `./r asset-pack` | Сгенерировать placeholder PNG asset pack. |
| `./r asset-preview` | Сгенерировать JSON/HTML preview asset registry. |
| `./r assets` | Проверить visual assets manifest contract. |
| `./r assets-full` | Сгенерировать asset pack и проверить наличие PNG. |
| `./r summary` | Напечатать summary по текущему `output/`. |
| `./r inspect` | Инспектировать текущий world package. |
| `./r test` | Запустить compileall, проверку assets manifest и pytest. |
| `./r help` | Показать справку. |

## Переменные окружения

| Переменная | Значение по умолчанию | Назначение |
|---|---:|---|
| `CONFIG_PATH` | `configs/default.json` | Конфиг генерации мира. |
| `OUTPUT_DIR` | `output` | Output root текущего запуска. |
| `VISUAL_PROFILE` | `top_down_visualgen/profiles/dark_forest` | Visual profile. |
| `VISUAL_OUTPUT` | `output/visual_map` | Папка visual output. |
| `VISUAL_STEPS_OUTPUT` | `output/visual_map/debug/steps` | Папка PNG-шагов visual pipeline. |
| `VISUAL_DEBUG_TILE_SIZE` | `4` | Размер tile для PNG-шагов. |
| `VISUAL_PREVIEW_TILE_SIZE` | `4` | Размер tile для visual preview. |
| `WORLD_PREVIEW_CELL_SIZE` | `4` | Размер cell для world preview. |
| `RUN_WORLD_PREVIEW` | `0` | Если `1`, `./r all` также строит `output/full_world_preview.png`. |
| `WORLD_RENDER` | `0` | Если `1`, world generator пишет PNG render layers. |
| `WORLD_DEBUG_LAYERS` | `0` | Если `1`, включает debug PNG layers при `WORLD_RENDER=1`. |
| `LOG_DIR` | `output/logs` | Папка stage logs. |
| `QUIET` | `1` | Если `0`, команды печатают raw output в терминал. |

## Примеры

Только world package:

```bash
./r world
```

Полный pipeline с world preview:

```bash
RUN_WORLD_PREVIEW=1 ./r
```

Запуск с другим output root:

```bash
OUTPUT_DIR=out/run_001 ./r
```
