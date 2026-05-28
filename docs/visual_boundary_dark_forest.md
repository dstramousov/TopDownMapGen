# Visual Boundary — Dark Forest

Документ фиксирует MVP-идею `map boundary visual treatment` для профиля `dark_forest_post_soviet_ruins`.

Важно:

```text
Boundary visual не меняет gameplay.
Boundary visual pass только показывает непроходимый край карты.
```

Visual pipeline не должен:

```text
- менять collision
- менять movement
- менять routes
- двигать start/goal
- создавать реальные проходы
```

Visual pipeline может:

```text
- добавлять visual-only boundary objects
- скрывать прямоугольность карты
- показывать, почему за край нельзя идти
- усиливать атмосферу тёмного леса
```

## 1. Основная идея

Край карты не должен выглядеть как обрезанный прямоугольник.

Вместо этого по внешнему краю добавляются visual-only маркеры:

```text
dense_forest_wall — плотная лесная стена
dark_tree_wall — тёмная чаща
cliff_wall — обрыв / высокий край
ruin_barrier — руинный завал
swamp_barrier — непроходимая болотная кромка
concrete_barrier — старые бетонные остатки / стена
```

## 2. Отличие от Level 4

`Level 4` внутри карты — это редкая визуальная доминанта / landmark.

`Boundary treatment` — это внешний край мира.

```text
Level 4 = ориентир внутри карты
Boundary = объяснение, почему карта заканчивается
```

Обе системы visual-only, но у них разный смысл.

## 3. Правила MVP

```text
- boundary markers ставятся только у внешнего края карты
- boundary markers не должны быть одинаковой рамкой Paint-style
- тип boundary выбирается по terrain context
- лесной край чаще становится dense_forest_wall / dark_tree_wall
- болотный край чаще становится swamp_barrier
- руинный край чаще становится ruin_barrier / concrete_barrier
- дорога, уходящая за край, визуально перекрывается чащей
```

## 4. Debug/report

Visual pipeline пишет:

```text
output/visual_map/debug/boundary_visual_report.json
output/visual_map/debug/steps/11_boundary_visual.png
```

Report показывает:

```text
total
by_boundary_type
by_sprite_id
by_edge
by_role
failed_placements
sampled_markers
```

## 5. Summary

`./r summary` показывает:

```text
Boundary visual:
  markers:             312 [ok]
  failed placements:     0 [ok]
  sampled markers:      89 [ok]
  by type:
    dense forest:      180
    dark trees:         72
    ruins:              24
    swamp:              19
    concrete:           17
    cliff:               0
```
