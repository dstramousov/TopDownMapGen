# Visual final render — dark_forest

Final renderer создаёт asset-backed PNG:

```text
output/visual_map/final_render.png
```

## Входные данные

```text
output/visual_map/visual_layers.json
output/visual_map/visual_objects.json
top_down_visualgen/profiles/dark_forest/assets_manifest.json
assets/dark_forest/**/*.png
```

## Выходные данные

```text
output/visual_map/final_render.png
output/visual_map/debug/final_render_report.json
```

## Команды

```bash
./r
./r final-render
```

## Правила

Final render не меняет gameplay. Это только изображение текущего visual output.
