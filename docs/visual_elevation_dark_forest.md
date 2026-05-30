# Visual elevation — dark_forest

Elevation visual pass показывает уже существующие elevation данные из world package.

## Входные данные

```text
output/map_package/elevation_model.json
output/map_package/elevation_features.json
output/map_package/elevation_transitions.json
output/map_package/layers/elevation.json
top_down_visualgen/profiles/dark_forest/elevation_visual_rules.json
```

## Выходные данные

```text
output/visual_map/visual_objects.json
output/visual_map/debug/elevation_visual_report.json
```

## Правила

Visual elevation не меняет gameplay elevation. Он только добавляет overlays/markers для читаемости низин, высот и переходов.

## Текущие правила профиля

В `elevation_visual_rules.json` сейчас зафиксировано:

```text
style_decisions.level_4_policy = visual_only_landmark
boundary_treatment.status = separate_boundary_visual_system
```

То есть level 4 показывается как visual-only landmark, а boundary обрабатывается отдельной boundary visual system.
