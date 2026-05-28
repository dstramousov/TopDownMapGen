# Visual Assets Manifest — Dark Forest

Документ фиксирует контракт будущих PNG-ассетов для visual pipeline `dark_forest`.

Важно: `assets_manifest.json` сейчас описывает **логические связи**, а не требует наличия реальных PNG-файлов.

```text
visual_tilesets.json -> какие tile_id / sprite_id существуют
assets_manifest.json -> где эти tile_id / sprite_id будут лежать как ассеты
```

## 1. Зачем нужен assets manifest

Visual pipeline уже создаёт много логических идентификаторов:

```text
road.turn_ne — поворот дороги на северо-восток
swamp.edge_s — южный край болота
decor.reeds_01 — камыш
elevation.lowland_shadow_edge — тёмный край низины
boundary.dense_forest_wall — плотная лесная стена края карты
```

Пока они рисуются placeholder-превью. Для перехода к реальным ассетам нужен стабильный контракт:

```text
tile_id / sprite_id
  -> path
  -> size
  -> pivot
  -> sort_anchor
  -> draw_layer
  -> tags
```

## 2. Где лежит контракт

```text
top_down_visualgen/profiles/dark_forest/assets_manifest.json
```

## 3. Что проверяет валидатор

```bash
python3 bin/validate_assets_manifest.py top_down_visualgen/profiles/dark_forest
```

Проверяется:

```text
- все tile_id из visual_tilesets.json есть в assets_manifest.json
- все sprite_id из visual_tilesets.json есть в assets_manifest.json
- у tile есть path и size
- у sprite есть path, size, pivot, sort_anchor и draw_layer
- fallback missing_tile / missing_sprite указывают на реальные записи manifest-а
```

По умолчанию реальные PNG-файлы **не требуются**.

Чтобы позже проверить уже сами файлы:

```bash
python3 bin/validate_assets_manifest.py top_down_visualgen/profiles/dark_forest --check-files
```

## 4. Пример tile entry

```json
{
  "road.turn_ne": {
    "path": "tiles/road/turn_ne.png",
    "size": [16, 16],
    "tags": ["road", "turn", "ne"],
    "asset_status": "placeholder_contract"
  }
}
```

## 5. Пример sprite entry

```json
{
  "decor.reeds_01": {
    "path": "sprites/decor/reeds_01.png",
    "size": [16, 16],
    "pivot": [8, 12],
    "sort_anchor": [8, 12],
    "draw_layer": "decor",
    "tags": ["decor", "reeds"],
    "asset_status": "placeholder_contract"
  }
}
```

## 6. Слои отрисовки

```text
decor — мелкий декор
object — runtime/object sprites
elevation — маркеры высот и низин
boundary — визуальный край карты
debug — fallback/debug sprites
```

## 7. Текущий статус

```text
asset_status: placeholder_contract
```

Это значит:

```text
контракт уже есть
реального PNG может ещё не быть
путь зарезервирован
валидатор проверяет структуру, но не файл
```

Когда реальные ассеты появятся, `asset_status` можно будет заменить, например:

```text
production
draft
needs_review
```
