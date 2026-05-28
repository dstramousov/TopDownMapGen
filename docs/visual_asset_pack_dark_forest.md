# Visual Asset Pack — Dark Forest

Документ описывает первый физический asset pack для профиля `dark_forest`.

Цель `v0.0.73`: не нарисовать финальный арт, а создать рабочий scaffold, чтобы каждый `tile_id` и `sprite_id` из `assets_manifest.json` имел PNG-файл-заглушку.

## 1. Что уже есть

Контракт ассетов лежит здесь:

```text
top_down_visualgen/profiles/dark_forest/assets_manifest.json
```

В нём описаны:

```text
tile_id / sprite_id
path
size
pivot
sort_anchor
draw_layer
tags
fallbacks
```

## 2. Где лежат физические ассеты

Физический asset pack генерируется сюда:

```text
assets/dark_forest/
```

Пути внутри `assets_manifest.json` остаются короткими:

```text
tiles/dirt/base.png
sprites/decor/swamp/reeds_01.png
```

А корень задаётся полем:

```json
"asset_root": "../../../assets/dark_forest"
```

Это значит: manifest живёт в профиле, а PNG лежат в общей папке `assets/dark_forest`.

## 3. Генерация placeholder PNG

Команда:

```bash
./r asset-pack
```

Она создаёт PNG-заглушки для всех записей из manifest.

Заглушки нужны, чтобы:

```text
- проверить файловый контракт
- увидеть весь asset vocabulary
- постепенно заменять placeholder на реальные PNG
- не блокировать visual pipeline отсутствием финального арта
```

## 4. Проверка файлов

Обычная проверка manifest:

```bash
./r assets
```

Проверка manifest + наличия PNG-файлов:

```bash
./r assets-full
```

Или вручную:

```bash
python3 bin/generate_asset_pack.py top_down_visualgen/profiles/dark_forest
python3 bin/validate_assets_manifest.py top_down_visualgen/profiles/dark_forest --check-files
```

## 5. Asset registry preview

Команда:

```bash
./r asset-preview
```

Создаёт:

```text
output/visual_map/debug/asset_registry_report.json
output/visual_map/debug/asset_registry_preview.html
```

После генерации placeholder pack HTML показывает не только таблицу ID, но и маленькие preview-картинки.

## 6. Что важно

Placeholder PNG — это не финальный арт.

Их нельзя воспринимать как стиль. Это технические заглушки, чтобы pipeline уже работал с файловыми ассетами.

Дальше реальные PNG можно заменять постепенно, не меняя `sprite_id`, `tile_id` и правила visual pipeline.

## 7. Следующий шаг

После scaffold-а логичный следующий patch:

```text
v0.0.74 — asset-backed preview renderer MVP
```

То есть visual preview начнёт использовать реальные PNG из `assets/dark_forest`, а не только debug-цвета.
