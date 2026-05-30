# Visual asset registry preview — dark_forest

Asset registry preview показывает полный список logical visual assets профиля `dark_forest`.

## Команда

```bash
./r asset-preview
```

В полном pipeline preview создаётся автоматически через:

```bash
./r
```

## Выходные файлы

```text
output/visual_map/debug/asset_registry_report.json
output/visual_map/debug/asset_registry_preview.html
```

## Назначение

Preview помогает увидеть:

- все `tile_id` и `sprite_id`;
- категории;
- draw layers;
- размеры;
- pivot/sort anchor;
- наличие PNG-файлов;
- thumbnails существующих assets.

Это инструмент контроля asset contract, а не проверка художественного качества.
