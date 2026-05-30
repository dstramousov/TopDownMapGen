# World package file map

Актуальная карта файлов после стандартного запуска:

```bash
./r
```

## Output root

```text
output/
  _manifest.json
  _engine_config.json
  _raw_tactical_map.json
  generated_map.txt
  tactical_map.json
  tactical_map_debug.json
  validation_report.json
  world_density_report.json
  metrics.txt
  object_catalog.md
  generation.log
  logs/
  map_package/
  visual_map/
```

Некоторые PNG world layers появляются только при `WORLD_RENDER=1` и `WORLD_DEBUG_LAYERS=1`.

## Главные entrypoints

| Файл | Для кого | Назначение |
|---|---|---|
| `_manifest.json` | tools/consumers | Паспорт запуска и список артефактов. |
| `map_package/map.json` | game/editor/renderer | Индекс структурированного пакета мира. |
| `visual_map/visual_map.json` | visual tools | Индекс visual output. |
| `visual_map/final_render.png` | человек/render preview | Финальная PNG-картинка. |
| `world_density_report.json` | QA/debug | Итоговая плотность terrain/collision/movement/elevation. |

## `map_package/`

См. `docs/OUTPUT_FORMAT.md` и `docs/map_package_v1.md`.

## `visual_map/`

Visual output создаётся поверх `map_package/`. Он не меняет gameplay contract.

Основные файлы:

```text
visual_map/visual_map.json
visual_map/visual_layers.json
visual_map/visual_objects.json
visual_map/visual_chunks.json
visual_map/preview.png
visual_map/final_render.png
visual_map/debug/
```
