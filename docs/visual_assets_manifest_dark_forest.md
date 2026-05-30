# Visual assets manifest — dark_forest

`top_down_visualgen/profiles/dark_forest/assets_manifest.json` описывает связь между logical visual ids и физическими PNG-ассетами.

Manifest нужен для:

- asset-backed final render;
- проверки, что каждый `tile_id` и `sprite_id` имеет ожидаемый путь;
- генерации placeholder asset pack;
- asset registry preview.

## Где лежит manifest

```text
top_down_visualgen/profiles/dark_forest/assets_manifest.json
```

## Где лежат PNG

```text
assets/dark_forest/
```

Пути внутри manifest относительны к `asset_root`.

## Что описывает entry

```text
id
kind: tile | sprite
path
size
pivot
sort_anchor
draw_layer
tags
fallbacks
```

## Проверки

```bash
./r assets
./r assets-full
```

`./r assets` проверяет contract manifest-а. `./r assets-full` дополнительно генерирует placeholder PNG и проверяет наличие файлов.
