# Dark Forest Asset Production Manifest

Документ фиксирует производственный план ассетов для визуального профиля `dark_forest`.

Цель: идти небольшими проверяемыми batch-ами, чтобы реальные PNG постепенно заменяли placeholder-ассеты из `assets/dark_forest/`.

## 1. Утверждённый стиль

```text
world_style: dark_forest_post_soviet_ruins
reference: плотный тёмный хвойный лес, приглушённая зелень, старые дороги, болота, руины
base_tile_size: 16x16
acceptance_batch_size: 10-20 assets
```

Основной референс:

```text
- top-down pixel art
- тёмный хвойный лес
- плотная лесная масса
- приглушённые зелёные, коричневые и серые тона
- постсоветские/заброшенные/руинные элементы
- без яркой мультяшности
- без чистого фэнтези и кислотных цветов
```

## 2. Почему начинаем с травы и леса

Трава, земля и лесная масса покрывают большую часть карты. Если они выглядят плохо, остальные ассеты карту не спасут.

Первый production batch должен закрыть примерно 70% визуального восприятия карты:

```text
ground / grass
forest fill
forest edges
forest corners
```

## 3. Статусы ассетов

```text
planned — запланирован
generated — сгенерирован, ждёт ревью
accepted — принят
needs_fix — нужно поправить
rejected — отклонён
replaced — заменён новым вариантом
```

## 4. Где лежит machine-readable план

```text
top_down_visualgen/profiles/dark_forest/asset_batches.json
```

Команда просмотра:

```bash
./r asset-plan
```

Она пишет отчёт:

```text
output/visual_map/debug/asset_production_plan_report.json
```

## 5. Batch B01 — Grass + Forest Base / Базовая трава и лесная масса

### Ground / Grass — земля и трава

```text
terrain.grass_base_01 — базовая трава 1
terrain.grass_base_02 — базовая трава 2
terrain.grass_base_03 — базовая трава 3
terrain.dark_grass_01 — тёмная трава
terrain.wet_grass_01 — мокрая трава
terrain.dry_grass_01 — суховатая трава
terrain.forest_ground_01 — лесная земля
terrain.forest_litter_01 — лесная подстилка
terrain.grass_noise_01 — шум травы
terrain.small_flowers_01 — лёгкие цветочные вкрапления
```

### Forest / Forest Mass — лес и лесная масса

```text
forest.fill_01 — плотный лес 1
forest.fill_02 — плотный лес 2
forest.edge_n — край леса север
forest.edge_s — край леса юг
forest.edge_e — край леса восток
forest.edge_w — край леса запад
forest.outer_corner_ne — внешний угол леса север-восток
forest.outer_corner_wn — внешний угол леса север-запад
forest.outer_corner_es — внешний угол леса юго-восток
forest.outer_corner_sw — внешний угол леса юго-запад
```

## 6. Приёмка Batch B01

Ассеты принимаются не по одному, а как набор.

Проверяем:

```text
- читается ли dark forest стиль
- не выглядит ли трава ярко/мультяшно
- лес выглядит как плотная хвойная масса, а не как отдельные игрушечные ёлки
- края леса скрывают квадратность сетки
- ассеты не спорят с референсом
- 16x16 ground tiles нормально тайлятся
```

Решения после ревью:

```text
accepted — кладём в основной asset pack
needs_fix — правим и повторно показываем
rejected — не используем
```

## 7. Что будет после Batch B01

Предлагаемый порядок следующих batch-ей:

```text
B02 — old roads / старые заросшие дороги
B03 — swamp / болотистая проходимая местность
B04 — ruins / руины
B05 — micro scenes / микросцены
B06 — elevation / высоты и низины
B07 — boundary / край карты
```

Но порядок можно поменять после ревью первого набора.
