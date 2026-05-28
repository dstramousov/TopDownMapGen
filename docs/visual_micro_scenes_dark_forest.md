# Visual micro scenes — dark_forest_post_soviet_ruins

## 1. Цель документа

Этот документ фиксирует контентный каталог микросцен для visual pipeline профиля `dark_forest`.

Микросцена — это небольшая смысловая композиция внутри `place`:

```text
ruined_camp — разрушенный лагерь
blocked_road — заваленная дорога
swamp_crossing — болотный переход
secret_cache — скрытый тайник
```

Задача микросцен — сделать карту визуально богаче и тактически читаемее, но не менять gameplay-данные world package.

Visual pipeline не должен:

```text
менять terrain
менять collision
менять movement
двигать start/goal
перекрывать routes
создавать реальный loot/gameplay interaction
```

Он может:

```text
добавлять небоевые visual objects
добавлять metadata на будущее
раскладывать визуальные акценты вокруг смысловых мест
```

---

## 2. Стиль мира

Выбранный стиль:

```text
dark_forest_post_soviet_ruins — тёмный лес, постсоветские заброшенные объекты, старые дороги, бункеры, бетон, древние/непонятные руины
```

Основа:

```text
abandoned_dark_forest — заброшенный тёмный лес
overgrown_roads — заросшие старые дороги
post_soviet_remains — постсоветские остатки / бетон / бункеры / оборонительные точки
ancient_unknown_ruins — древние непонятные руины
swamp_lowlands — болота и низины
rare_landmarks — редкие странные ориентиры
```

Не делаем основой:

```text
pure_fantasy — чистое фэнтези
pure_horror — чистый хоррор
fairy_forest — сказочный яркий лес
modern_military_range — современный военный полигон
```

---

## 3. Роли объектов на будущее

Интерактивность сейчас не реализуется. Роли нужны только как metadata и как подготовка на будущее.

Целевое распределение:

```text
visual — просто визуальный предмет: 75–85%
inspectable_candidate — потенциально можно осмотреть: 10–15%
loot_candidate — потенциальный лут: 3–6%
story_candidate — потенциальный сюжетный объект: 1–2%
cover_hint — визуальная подсказка укрытия: context-based / зависит от места
```

Роли:

```text
visual — просто визуальный предмет
inspectable_candidate — потенциально можно осмотреть
loot_candidate — потенциальный лут
story_candidate — потенциальный сюжетный объект
cover_hint — визуальная подсказка укрытия
danger_hint — подсказка опасности
path_hint — подсказка прохода / направления
```

---

## 4. Микросцены, которые уже есть

```text
ruined_camp — разрушенный лагерь
swamp_crossing — болотный переход
blocked_road — заваленная дорога
small_loot_pocket — маленькая зона лута / небольшая находка
secret_cache — скрытый тайник
bunker_outer_area — внешняя зона бункера
bunker_inner_area — внутренняя зона бункера
dangerous_lowland — опасная низина
old_defensive_position — старая оборонительная позиция
ambush_clearing — поляна для засады
forest_obstruction — лесной завал / преграда
small_ruin_site — маленькие руины
ruined_structure — разрушенная структура
raised_platform_site — приподнятая руинная площадка
```

---

## 5. Предметы, которые уже есть

### 5.1. Болото

```text
reeds — камыш
mud_patch — пятно грязи
wet_grass — мокрая трава
dead_branch — сухая ветка / мёртвая ветка
swamp_log — бревно в болоте
```

### 5.2. Старые дороги

```text
road_grass_tuft — пучок травы на дороге
road_dirt_noise — грязный шум / пятно земли на дороге
small_stone — маленький камень
broken_plank — сломанная доска
roadblock_debris — мусор от дорожного завала
```

### 5.3. Руины

```text
ruin_rubble — руинный щебень / обломки
cracked_stone — треснувший камень
fallen_bricks — упавшие кирпичи
broken_block — сломанный каменный блок
mossy_stone — камень со мхом
concrete_debris — бетонные обломки
```

### 5.4. Лагерь / человеческие следы

```text
campfire_ash — пепелище / остатки костра
abandoned_crate — брошенный ящик
firewood_stack — стопка дров
```

### 5.5. Опасность / оборона

```text
warning_bones — предупреждающие кости / останки
sandbag_remnant — остатки мешков с песком
fallen_log — упавшее бревно
hidden_cache_marker — скрытый маркер тайника
```

---

## 6. Предметы, которые предлагается добавить

### 6.1. Лагерь / следы людей

```text
torn_cloth — рваная ткань
old_backpack — старый рюкзак
empty_bottle — пустая бутылка
rusty_pot — ржавая кастрюля / котелок
broken_lantern — сломанный фонарь
rope_piece — кусок верёвки
sack — мешок
collapsed_tent_piece — кусок рухнувшей палатки
burned_log — обгоревшее бревно
old_bedroll — старый спальник / подстилка
```

### 6.2. Дорога / завалы

```text
wagon_wheel_broken — сломанное колесо телеги
signpost_broken — сломанный указатель
barricade_stake — колышек баррикады
tire_rut_mud — грязная колея
branch_pile — куча веток
plank_stack — стопка досок
broken_cart_piece — кусок сломанной телеги
roadside_marker_stone — придорожный камень-метка
```

### 6.3. Руины

```text
broken_column — сломанная колонна
stone_slab — каменная плита
cracked_floor_piece — кусок треснувшего пола
half_wall_debris — обломки полустены
old_tile_fragment — фрагмент старой плитки
root_over_stone — корень поверх камня
collapsed_arch_piece — кусок рухнувшей арки
stone_dust_patch — пятно каменной пыли
```

### 6.4. Болото

```text
reeds_cluster — группа камыша
black_mud — чёрная грязь
rotten_log — гнилое бревно
water_puddle — лужа
moss_patch — пятно мха
bog_bubbles — болотные пузыри
dead_tree_root — мёртвый корень дерева
swamp_stones — болотные камни
```

### 6.5. Оборона / бой

```text
sandbag_broken — разорванный мешок с песком
ammo_crate_empty — пустой ящик от боеприпасов
spent_shells — стреляные гильзы
wooden_cover_piece — деревянный кусок укрытия
old_tripod — старая тренога
broken_shield_panel — сломанный защитный щит
rusty_barbed_wire — ржавая колючая проволока
foxhole_debris — мусор в стрелковой ячейке / окопе
```

### 6.6. Лес

```text
stump_large — большой пень
fallen_tree — упавшее дерево
root_cluster — скопление корней
mushroom_cluster — группа грибов
thorn_bush — колючий куст
animal_bones — кости животного
dry_leaves_patch — пятно сухих листьев
forest_litter — лесной мусор / подстилка
```

---

## 7. Пулы по микросценам

### 7.1. ruined_camp — разрушенный лагерь

Частые:

```text
campfire_ash — пепелище
abandoned_crate — брошенный ящик
firewood_stack — стопка дров
empty_bottle — пустая бутылка
torn_cloth — рваная ткань
burned_log — обгоревшее бревно
```

Нечастые:

```text
broken_lantern — сломанный фонарь
old_backpack — старый рюкзак
rusty_pot — ржавая кастрюля / котелок
collapsed_tent_piece — кусок рухнувшей палатки
old_bedroll — старый спальник / подстилка
```

Редкие:

```text
hidden_cache_marker — скрытый маркер тайника
warning_bones — предупреждающие кости
```

Тактический смысл:

```text
ориентир
небольшая зона интереса
потенциальное место укрытий вокруг лагеря
```

---

### 7.2. swamp_crossing — болотный переход

Частые:

```text
swamp_log — бревно в болоте
reeds — камыш
mud_patch — пятно грязи
wet_grass — мокрая трава
reeds_cluster — группа камыша
```

Нечастые:

```text
rotten_log — гнилое бревно
water_puddle — лужа
moss_patch — пятно мха
swamp_stones — болотные камни
```

Редкие:

```text
bog_bubbles — болотные пузыри
dead_tree_root — мёртвый корень дерева
```

Тактический смысл:

```text
замедленная зона
узкий проход
визуальная подсказка опасной/мокрой местности
```

---

### 7.3. blocked_road — заваленная дорога

Частые:

```text
roadblock_debris — мусор от дорожного завала
broken_plank — сломанная доска
small_stone — маленький камень
branch_pile — куча веток
```

Нечастые:

```text
wagon_wheel_broken — сломанное колесо телеги
signpost_broken — сломанный указатель
barricade_stake — колышек баррикады
plank_stack — стопка досок
broken_cart_piece — кусок сломанной телеги
```

Редкие:

```text
roadside_marker_stone — придорожный камень-метка
```

Тактический смысл:

```text
завал
читаемое препятствие
место потенциальной засады
```

---

### 7.4. small_loot_pocket — маленькая находка

Частые:

```text
abandoned_crate — брошенный ящик
sack — мешок
small_stone — маленький камень
torn_cloth — рваная ткань
```

Нечастые:

```text
old_backpack — старый рюкзак
rope_piece — кусок верёвки
empty_bottle — пустая бутылка
```

Редкие:

```text
hidden_cache_marker — скрытый маркер тайника
```

Тактический смысл:

```text
маленький визуальный интерес
не должен быть слишком очевидным
```

---

### 7.5. secret_cache — скрытый тайник

Частые:

```text
hidden_cache_marker — скрытый маркер тайника
moss_patch — пятно мха
root_cluster — скопление корней
small_stone — маленький камень
```

Нечастые:

```text
old_backpack — старый рюкзак
sack — мешок
rope_piece — кусок верёвки
```

Редкие:

```text
old_tile_fragment — фрагмент старой плитки
story_candidate_marker — потенциальный сюжетный маркер
```

Тактический смысл:

```text
визуально скрытая точка интереса
не должна кричать игроку “тут тайник”
```

---

### 7.6. bunker_outer_area — внешняя зона бункера

Частые:

```text
concrete_debris — бетонные обломки
broken_block — сломанный каменный блок
mossy_stone — камень со мхом
sandbag_remnant — остатки мешков с песком
```

Нечастые:

```text
rusty_barbed_wire — ржавая колючая проволока
ammo_crate_empty — пустой ящик от боеприпасов
old_tripod — старая тренога
broken_shield_panel — сломанный защитный щит
```

Редкие:

```text
warning_bones — предупреждающие кости
```

Тактический смысл:

```text
переход к опасной зоне
бетон/оборона/старый объект
```

---

### 7.7. bunker_inner_area — внутренняя зона бункера

Частые:

```text
concrete_debris — бетонные обломки
broken_block — сломанный каменный блок
stone_dust_patch — пятно каменной пыли
```

Нечастые:

```text
ammo_crate_empty — пустой ящик от боеприпасов
broken_lantern — сломанный фонарь
rusty_pot — ржавая кастрюля / котелок
```

Редкие:

```text
hidden_cache_marker — скрытый маркер тайника
story_candidate_marker — потенциальный сюжетный маркер
```

Тактический смысл:

```text
замкнутая опасная зона
подземность / бетон / старая оборона
```

---

### 7.8. dangerous_lowland — опасная низина

Частые:

```text
dead_branch — сухая ветка
mud_patch — пятно грязи
wet_grass — мокрая трава
warning_bones — предупреждающие кости
```

Нечастые:

```text
black_mud — чёрная грязь
water_puddle — лужа
animal_bones — кости животного
dead_tree_root — мёртвый корень дерева
```

Редкие:

```text
bog_bubbles — болотные пузыри
```

Тактический смысл:

```text
предупреждение об опасной или неудобной зоне
может быть медленно / плохо для боя
```

---

### 7.9. old_defensive_position — старая оборонительная позиция

Частые:

```text
sandbag_remnant — остатки мешков с песком
broken_plank — сломанная доска
small_stone — маленький камень
wooden_cover_piece — деревянный кусок укрытия
```

Нечастые:

```text
ammo_crate_empty — пустой ящик от боеприпасов
spent_shells — стреляные гильзы
sandbag_broken — разорванный мешок с песком
old_tripod — старая тренога
```

Редкие:

```text
broken_shield_panel — сломанный защитный щит
rusty_barbed_wire — ржавая колючая проволока
```

Тактический смысл:

```text
визуальная подсказка укрытия
место для перестрелки
```

---

### 7.10. ambush_clearing — поляна для засады

Частые:

```text
fallen_log — упавшее бревно
thorn_bush — колючий куст
branch_pile — куча веток
road_grass_tuft — пучок травы
```

Нечастые:

```text
wooden_cover_piece — деревянный кусок укрытия
animal_bones — кости животного
root_cluster — скопление корней
```

Редкие:

```text
warning_bones — предупреждающие кости
```

Тактический смысл:

```text
читаемое место засады
часть объектов может быть cover_hint
```

---

### 7.11. forest_obstruction — лесной завал / преграда

Частые:

```text
fallen_log — упавшее бревно
dead_branch — сухая ветка
branch_pile — куча веток
root_cluster — скопление корней
```

Нечастые:

```text
stump_large — большой пень
thorn_bush — колючий куст
mushroom_cluster — группа грибов
```

Редкие:

```text
animal_bones — кости животного
```

Тактический смысл:

```text
визуальное сужение прохода
естественное укрытие / препятствие
```

---

### 7.12. small_ruin_site / ruined_structure — маленькие руины

Частые:

```text
ruin_rubble — руинный щебень
cracked_stone — треснувший камень
broken_block — сломанный каменный блок
mossy_stone — камень со мхом
```

Нечастые:

```text
broken_column — сломанная колонна
stone_slab — каменная плита
cracked_floor_piece — кусок треснувшего пола
half_wall_debris — обломки полустены
old_tile_fragment — фрагмент старой плитки
root_over_stone — корень поверх камня
```

Редкие:

```text
collapsed_arch_piece — кусок рухнувшей арки
story_candidate_marker — потенциальный сюжетный маркер
```

Тактический смысл:

```text
ориентир
частичное укрытие
визуально значимое место
```

---

### 7.13. raised_platform_site — приподнятая руинная площадка

Частые:

```text
stone_slab — каменная плита
cracked_floor_piece — кусок треснувшего пола
mossy_stone — камень со мхом
ruin_rubble — руинный щебень
```

Нечастые:

```text
broken_column — сломанная колонна
old_tile_fragment — фрагмент старой плитки
root_over_stone — корень поверх камня
```

Редкие:

```text
collapsed_arch_piece — кусок рухнувшей арки
```

Тактический смысл:

```text
визуальная подсказка возвышенности
переход к будущему elevation visual pass
```

---

## 8. Правила раскладки микросцены

Для будущего алгоритма `varied micro scene placement`:

```text
1. выбрать place type
2. выбрать scene variant
3. выбрать anchor внутри bounds
4. выбрать 2–6 предметов из weighted pool
5. разложить предметы рядом с anchor
6. не ставить на blocked terrain
7. не ставить на start/goal
8. не перекрывать route centerline
9. не повторять одинаковый sprite слишком часто рядом
10. не делать каждый place одинаковым
```

Рекомендуемые размеры:

```text
small scene — 1–2 объекта
medium scene — 3–5 объектов
large scene — 5–8 объектов
```

---

## 9. Что делать следующим patch

`v0.0.64 — visual micro scene catalog`:

```text
- добавить этот документ в docs/
- зафиксировать world_style
- зафиксировать object role distribution
- расширить place_visual_rules.json до scene variants / weighted pools metadata
- добавить placeholder sprite ids в visual_tilesets.json
- не менять gameplay
- не реализовывать реальную интерактивность
```

`v0.0.65 — varied micro scene placement`:

```text
- реализовать выбор scene variant
- реализовать weighted pools
- реализовать role metadata на visual objects
- улучшить place_treatment_report
- оставить все gameplay grids неизменными
```
