# Visual Elevation — Dark Forest

Документ описывает, как `visual_tileset_pipeline` должен показывать высоты и низины в стиле `dark_forest_post_soviet_ruins`.

Цель: заранее договориться о визуальном языке `Elevation`, прежде чем писать `elevation visual pass`.

Важно:

```text
Elevation не меняет gameplay.
Elevation visual pass только показывает уже существующие данные world package.
```

Visual pipeline не должен:

```text
- менять height_grid
- менять collision
- менять movement
- двигать start/goal
- ломать routes
- менять zones
```

Visual pipeline может:

```text
- добавлять overlay tiles
- добавлять visual markers
- добавлять небоевые visual objects
- показывать края высот
- показывать спуски/подъёмы
- усиливать читаемость low/high areas
```

---

## 1. Общая идея

В world package уже есть уровни:

```text
-1  низины, ямы, окопы, внутренности бункеров
 0  обычная земля
 1  холмы, насыпи, бермы
 2  мосты, платформы, приподнятые руины
 3  вышки, башни, высокие наблюдательные точки
 4  visual-only landmark / beacon / непроходимая визуальная доминанта
```

Для visual pipeline нужно сделать так, чтобы игрок глазами понимал:

```text
- где ниже
- где выше
- где край высоты
- где можно подняться/спуститься
- где высокая тактическая точка
- где особый landmark
- где край мира визуально закрыт естественной преградой
```

Принятое решение по стилю:

```text
height_emphasis: readable — заметно, но не комиксово
lowlands_wetness: contextual — зависит от terrain/place/elevation feature
level_4_policy: visual_only_landmark — непроходимая визуальная доминанта
boundary_treatment: separate_boundary_visual_system — отдельная система края карты
```

---

## 2. Level -1 — низины / углубления

### Смысл

```text
lowland — низина
pit — яма
trench — окоп
bunker_interior — внутренняя часть бункера
swamp_depression — болотная впадина
washed_ground — размытая земля
```

Это места, которые должны ощущаться ниже обычной земли.

### Визуальные признаки

```text
darker_ground — более тёмная земля
wet_mud — мокрая грязь
shadowed_edge — затенённый край
recessed_floor — вдавленная поверхность
lowland_rim — край низины
water_seep — просачивающаяся вода
```

### Возможные visual objects

```text
elevation.mud_pool — грязевая лужа
elevation.wet_grass_dark — тёмная мокрая трава
elevation.trench_wall_edge — край окопа
elevation.pit_edge — край ямы
elevation.root_hanging — свисающие корни
elevation.broken_drain_pipe — сломанная труба
elevation.bunker_floor_dark — тёмный пол бункера
elevation.water_seep — просачивающаяся вода
elevation.dark_leaf_litter — тёмная мокрая листва
elevation.lowland_stones — камни в низине
```

### Возможные transition objects

```text
elevation.trench_step — ступень в окоп
elevation.mud_slope_down — грязный спуск вниз
elevation.bunker_descent — спуск в бункер
elevation.pit_ramp — пологий спуск в яму
elevation.root_step — корни как ступени
```

### Тактический смысл

```text
- может визуально показывать укрытие
- может намекать на замедление
- может быть опасной зоной
- может быть скрытым проходом
- может быть внутренней частью бункера
```

### Осторожно

Не делать все низины одинаково болотными.
`level -1` не всегда болото. Это может быть окоп, яма, бункер или просто просадка земли.

---

## 3. Level 0 — обычная земля

### Смысл

```text
normal_ground — базовый уровень
grass — трава
old_road — старая дорога
ruin_floor — пол руин
forest_ground — лесная земля
```

Это baseline.

### Визуальные признаки

```text
base_ground — базовая земля
neutral_grass — обычная трава
normal_shadow — обычная тень
```

### Возможные visual objects

Здесь живут обычные слои:

```text
grass_tuft — пучок травы
small_stone — маленький камень
road_grass_tuft — трава на дороге
ruin_rubble — руинный щебень
forest_litter — лесная подстилка
```

### Тактический смысл

```text
- основной проходимый уровень
- точка сравнения для высот и низин
```

---

## 4. Level 1 — небольшие возвышения

### Смысл

```text
raised_ground — приподнятая земля
hill — холм
raised_berm — насыпь / берма
earthwork — земляное укрепление
dry_ridge — сухая гряда
```

Это не высокая платформа, а небольшое преимущество по высоте.

### Визуальные признаки

```text
slightly_lighter_ground — чуть более светлая земля
dry_grass — суховатая трава
raised_edge — край подъёма
hill_shoulder — плечо холма
berm_rim — кромка насыпи
```

### Возможные visual objects

```text
elevation.raised_berm_edge — край насыпи
elevation.hill_grass_edge — травяной склон
elevation.dry_stone_patch — сухой каменный участок
elevation.exposed_roots — открытые корни
elevation.slope_grass — трава на склоне
elevation.old_earthwork — старая земляная насыпь
elevation.ridge_stones — камни на гряде
elevation.dry_leaf_patch — сухие листья
```

### Возможные transition objects

```text
elevation.dirt_slope_up — земляной подъём
elevation.grass_slope_up — травяной подъём
elevation.low_berm_cut — проход через насыпь
elevation.root_slope — склон с корнями
```

### Тактический смысл

```text
- лёгкое преимущество позиции
- хорошая точка обзора
- естественная граница поляны
- место для укрытий и засад
```

### Осторожно

Level 1 не должен выглядеть как бетонная платформа.
Это скорее земляной рельеф: холм, вал, насыпь.

---

## 5. Level 2 — платформы / мосты / поднятые руины

### Смысл

```text
platform — платформа
wooden_bridge — деревянный мост
stone_platform — каменная платформа
raised_ruin_floor — приподнятый пол руин
walkway — настил / проход
```

Это уже явная конструкция или сильно читаемая высота.

### Визуальные признаки

```text
platform_edge — край платформы
strong_outline — сильнее обозначенный край
wooden_deck — деревянный настил
stone_floor — каменный пол
support_hint — намёк на опоры
```

### Возможные visual objects

```text
elevation.wooden_bridge_deck — деревянный настил моста
elevation.stone_platform_edge — край каменной платформы
elevation.broken_stairs_base — основание сломанной лестницы
elevation.ruin_platform_floor — пол приподнятых руин
elevation.bridge_support_post — опора моста
elevation.collapsed_platform_gap — провал в платформе
elevation.stone_guard_edge — каменный бортик
elevation.old_planks — старые доски
```

### Возможные transition objects

```text
elevation.stone_stairs — каменная лестница
elevation.wooden_ramp — деревянная рампа
elevation.dirt_ramp — земляной подъём
elevation.broken_stairs — сломанная лестница
elevation.bridge_entry — вход на мост
elevation.platform_step — ступень на платформу
```

### Тактический смысл

```text
- сильная позиция
- узкий проход
- мост через опасную зону
- место для обороны
- явный ориентир
```

### Осторожно

Если level 2 есть, переходы должны быть читаемыми.
Иначе игрок видит платформу, но не понимает, как туда попасть.

---

## 6. Level 3 — высокая точка

### Смысл

```text
watchtower — вышка
tower — башня
lookout — наблюдательная точка
high_platform — высокая площадка
```

Это редкая и заметная высокая позиция.

### Визуальные признаки

```text
tower_base — основание башни
high_shadow — сильная тень
vertical_marker — вертикальный ориентир
lookout_floor — площадка наблюдения
ladder_marker — лестница / подъём
```

### Возможные visual objects

```text
elevation.watchtower_base — основание вышки
elevation.watchtower_ladder — лестница вышки
elevation.high_platform_edge — край высокой площадки
elevation.lookout_planks — доски наблюдательной площадки
elevation.old_flag_pole — старый флагшток
elevation.signal_tripod — сигнальная тренога
elevation.broken_railing — сломанные перила
elevation.watch_post_debris — мусор сторожевого поста
```

### Возможные transition objects

```text
elevation.tower_ladder — лестница на вышку
elevation.wooden_stairs_high — высокая деревянная лестница
elevation.stone_steps_high — высокие каменные ступени
elevation.platform_ladder_entry — вход на площадку
```

### Тактический смысл

```text
- сильная обзорная точка
- снайперская/наблюдательная позиция
- landmark внутри локальной области
- место, к которому игрок может стремиться
```

### Осторожно

Level 3 должен быть редким.
Если высоких точек слишком много, они перестают быть важными.

---

## 7. Level 4 — visual-only landmark / beacon

### Смысл

```text
ancient_beacon — древний маяк / beacon
special_high_landmark — особая высокая визуальная доминанта
ritual_high_point — ритуальная высокая точка
signal_monolith — сигнальный монолит
```

Это не traversable high-ground. Это визуальная доминанта.

Принятое решение:

```text
Level 4 — чисто визуальная фигня.
Подняться нельзя.
Стоит красиво.
Помогает ориентироваться.
Может стать будущей story point, но сейчас gameplay не меняет.
```

### Визуальные признаки

```text
unique_marker — уникальный маркер
strong_silhouette — сильный силуэт
special_ground — особая земля вокруг
landmark_ring — кольцо/основание вокруг landmark
non_walkable_base — непроходимое основание
```

### Возможные visual objects

```text
elevation.ancient_beacon_base — основание древнего маяка
elevation.signal_stone — сигнальный камень
elevation.ritual_marker — ритуальный маркер
elevation.collapsed_monolith — рухнувший монолит
elevation.high_landmark_marker — маркер высокого ориентира
elevation.old_signal_device — старое сигнальное устройство
elevation.strange_stone_ring — странное каменное кольцо
elevation.beacon_debris — обломки маяка
```

### Подходы и окружение, но не переходы

Для level 4 не используем явные traversable transitions вроде лестницы наверх.

Допустимо:

```text
elevation.stone_approach — каменный подход
elevation.landmark_ring_edge — край основания landmark
elevation.beacon_debris — обломки маяка
elevation.strange_stone_ring — странное каменное кольцо
```

Не использовать как обычный проход:

```text
landmark_stairs — лестница к landmark
spiral_ramp_hint — намёк на спиральный подъём
ritual_steps — ритуальные ступени
```

Эти элементы могут появиться позже только как `non_walkable_visual_only`, если будет понятно, что игрок не ожидает туда подняться.

### Тактический смысл

```text
- главный ориентир
- визуальная доминанта
- потенциальная сюжетная точка
- точка навигации на карте
```

### Осторожно

Level 4 должен быть очень редким.
На обычной карте может быть 0–1 таких зон.

---

## 8. Boundary treatment — визуальный край карты

Boundary treatment — это отдельная будущая система, не равная level 4.

### Смысл

Край карты не должен выглядеть как тупой прямоугольный обрыв массива. Он должен быть закрыт естественной или рукотворной преградой.

Варианты:

```text
boundary.dense_forest_wall — плотная лесная стена
boundary.cliff_wall — высокий обрыв
boundary.ruin_barrier — руинный барьер
boundary.swamp_barrier — непроходимая болотная кромка
boundary.concrete_barrier — старый бетонный завал / ограждение
boundary.dark_tree_wall — тёмная стена деревьев
```

### Правило

```text
Level 4 = редкая внутренняя визуальная доминанта.
Boundary treatment = внешний визуальный непроходимый край мира.
```

Их нельзя смешивать в одну категорию.

### Осторожно

Не делать одинаковую рамку по всему периметру.
Иначе это будет выглядеть как обводка в Paint.

Лучше:

```text
60% dense forest wall — плотная лесная стена
15% cliff/raised edge — обрыв / высокий край
10% ruin barrier — руинный барьер
10% swamp barrier — болотный барьер
5% special blocked hint — заваленная тропа / сломанный мост / странный объект
```

---

## 9. Переходы высот

Переходы важнее самих цифр высоты.
Если переходы не видны, elevation не читается.

### Основные transition types

```text
slope — склон
ramp — рампа / подъём
stairs — лестница
bridge_entry — вход на мост
bunker_descent — спуск в бункер
trench_step — ступень в окоп
platform_step — ступень на платформу
tower_ladder — лестница на вышку
```

### Visual objects для переходов

```text
elevation.slope_grass — травяной склон
elevation.mud_slope_down — грязный спуск вниз
elevation.dirt_ramp — земляная рампа
elevation.wooden_ramp — деревянная рампа
elevation.stone_stairs — каменная лестница
elevation.broken_stairs — сломанная лестница
elevation.bridge_entry — вход на мост
elevation.bunker_descent — спуск в бункер
elevation.trench_step — ступень в окоп
elevation.tower_ladder — лестница на вышку
```

### Что нужно проверять

```text
- переход не должен перекрывать route
- переход должен визуально совпадать с реальным transition
- опасный край должен быть виден
- вход на мост/платформу должен быть читаем
```

---

## 10. Edge markers

Края высот должны читаться.

### Lowland edges

```text
elevation.lowland_shadow_edge — тёмный край низины
elevation.mud_rim — грязная кромка
elevation.pit_rim — край ямы
elevation.trench_wall_edge — край окопа
elevation.bunker_floor_edge — край пола бункера
```

### Raised edges

```text
elevation.raised_berm_edge — край насыпи
elevation.hill_shoulder — плечо холма
elevation.dry_ridge_edge — сухая кромка гряды
elevation.rooted_slope_edge — склон с корнями
```

### Platform edges

```text
elevation.stone_platform_edge — край каменной платформы
elevation.wooden_platform_edge — край деревянной платформы
elevation.ruin_platform_edge — край руинной платформы
elevation.bridge_side_edge — боковой край моста
```

### High point edges

```text
elevation.high_platform_edge — край высокой площадки
elevation.tower_base_edge — край основания башни
elevation.landmark_ring_edge — край основания landmark
```

---

## 11. Роли elevation-объектов

Пока интерактивности нет, но роли можно заложить:

```text
visual — просто визуальный объект
height_edge — показывает край высоты
transition_hint — показывает проход вверх/вниз
danger_hint — показывает опасный край/падение/низину
cover_hint — намекает на укрытие
landmark_hint — показывает важный ориентир
story_candidate — потенциальный сюжетный объект
boundary_hint — показывает непроходимый край карты
```

---

## 12. Предлагаемая структура правил

Будущий файл:

```text
top_down_visualgen/profiles/dark_forest/elevation_visual_rules.json
```

Примерно:

```json
{
  "schema_version": "elevation-visual-rules-v1",
  "profile": "dark_forest",
  "world_style": "dark_forest_post_soviet_ruins",
  "style_decisions": {
    "height_emphasis": "readable",
    "lowlands_wetness": "contextual",
    "level_4_policy": "visual_only_landmark",
    "boundary_treatment": "separate_boundary_visual_system"
  }
}
```

---

## 13. Debug output

Когда elevation visual pass будет реализован, он должен писать:

```text
output/visual_map/debug/elevation_visual_report.json
output/visual_map/debug/steps/XX_elevation_visual.png
```

Report должен показывать:

```text
level_counts
lowland_visual_objects
raised_visual_objects
transition_markers
edge_markers
landmark_markers
boundary_markers
failed_placements
```

---

## 14. Summary output

В `./r` summary нужно показывать:

```text
Visual elevation:
  lowland overlays:    812 [ok]
  raised edge markers: 490 [ok]
  transition markers:   64 [ok]
  landmark markers:      5 [ok]
```

Позже можно расширить:

```text
Visual elevation:
  lowland overlays:      812 / 812 [ok]
  raised edge markers:   490
  transition markers:     64 / 64 [ok]
  landmark markers:        5 / 5 [ok]
  failed placements:       0 [ok]
```

---

## 15. Зафиксированные решения

```text
height emphasis:
  readable — заметно, но не комиксово

lowlands wetness:
  contextual — зависит от terrain/place/elevation feature

level 4:
  visual_only_landmark — непроходимая визуальная доминанта

boundary treatment:
  отдельная будущая система визуального края карты
```

---

## 16. Следующий patch после каталога

После этого документа следующий технический шаг:

```text
v0.0.67 — elevation visual pass MVP
```

Он должен реализовать:

```text
- lowland overlays
- raised overlays
- height edge markers
- transition markers
- landmark markers
- elevation_visual_report.json
- debug step elevation_visual.png
```

Boundary treatment лучше делать отдельным patch после elevation pass:

```text
v0.0.68 — map boundary visual treatment
```
