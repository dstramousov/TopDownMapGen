# Visual micro scenes — dark_forest

Micro scenes — это небольшие visual-only композиции вокруг semantic places. Текущий world style id: `dark_forest_post_soviet_ruins`.

Примеры:

```text
ruined_camp
blocked_road
swamp_crossing
secret_cache
broken_radio_site
old_defensive_position
```

## Назначение

Micro scenes делают карту визуально богаче и читаемее, но не создают gameplay interaction сами по себе.

## Правила

Visual micro scenes не меняют:

```text
terrain
collision
movement
routes
start/goal
gameplay zones
```

Они могут добавлять:

```text
visual objects
visual-only props
future metadata hints
```

## Output

Результат попадает в:

```text
output/visual_map/visual_objects.json
output/visual_map/debug/place_treatment_report.json
```
