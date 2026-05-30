# Visual boundary — dark_forest

Boundary visual pass добавляет visual-only маркеры по краям карты, чтобы прямоугольный край выглядел как плотная чаща, руины, болото или обрыв.

## Входные данные

```text
output/map_package/
top_down_visualgen/profiles/dark_forest/boundary_visual_rules.json
```

## Выходные данные

```text
output/visual_map/visual_objects.json
output/visual_map/debug/boundary_visual_report.json
```

## Правила

Boundary visual не меняет:

```text
collision
movement
routes
start/goal
gameplay zones
```

Он только добавляет visual objects для чтения края карты.
