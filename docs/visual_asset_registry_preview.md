# Visual Asset Registry Preview — Dark Forest

Документ описывает dev-утилиту предпросмотра asset registry для `dark_forest` profile.

Цель: перед подключением реальных PNG видеть полный список логических `tile_id` и `sprite_id`, их категории, размеры, слои отрисовки и будущие пути ассетов.

Важно:

```text
Asset registry preview не проверяет художественное качество.
Asset registry preview показывает контракт ассетов и помогает понять, что надо рисовать/резать.
```

## Команда

```bash
python3 bin/generate_asset_registry_preview.py top_down_visualgen/profiles/dark_forest \
  --output output/visual_map/debug
```

Через helper:

```bash
./r asset-preview
```

В полном pipeline:

```bash
./r
```

## Выходные файлы

```text
output/visual_map/debug/asset_registry_report.json
output/visual_map/debug/asset_registry_preview.html
```

## Что показывает JSON report

```text
summary.total_entries
summary.tiles
summary.sprites
by_kind
by_category
by_draw_layer
by_asset_status
top_tags
entries[]
```

Каждая запись содержит:

```text
id
kind
category
path
size
pivot
sort_anchor
draw_layer
tags
asset_status
```

## Что показывает HTML preview

HTML-файл нужен для ручного просмотра текущего визуального словаря:

```text
- сколько всего tile/sprite ids
- какие категории самые большие
- какие draw layers есть
- какие asset_status используются
- полный список entries с path/size/pivot/sort_anchor/tags
```

## Чего утилита пока не делает

```text
- не грузит реальные PNG
- не строит sprite atlas
- не проверяет художественный стиль
- не рендерит реальные ассеты на карте
```

Для проверки наличия файлов уже есть отдельный режим валидатора:

```bash
python3 bin/validate_assets_manifest.py top_down_visualgen/profiles/dark_forest --check-files
```

Но пока реальные PNG не требуются: текущий этап фиксирует контракт.
