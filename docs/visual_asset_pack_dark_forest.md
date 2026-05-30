# Visual asset pack — dark_forest

Физический asset pack профиля `dark_forest` лежит в:

```text
assets/dark_forest/
```

Он используется final renderer-ом для создания:

```text
output/visual_map/final_render.png
```

## Генерация placeholder pack

```bash
./r asset-pack
```

Команда читает:

```text
top_down_visualgen/profiles/dark_forest/assets_manifest.json
```

и создаёт отсутствующие placeholder PNG по путям из manifest-а.

## Проверка полного pack

```bash
./r assets-full
```

Команда создаёт placeholder PNG и затем проверяет, что все referenced files существуют.

## Важное ограничение

Asset pack влияет только на визуализацию. Он не меняет collision, movement, routes, world graph, gameplay zones или elevation model.
