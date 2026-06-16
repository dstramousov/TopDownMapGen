# forest_asset_pack_v1

Оригинальный тестовый набор forest sprites для проверки ForestMassOverlay.

`ideal.png` использовался только как визуальный ориентир. Пиксели из него не вырезались.

## Что внутри

- `trees/` — одиночные сосны разных размеров.
- `clusters/` — плотные кластеры крон для заливки лесной массы.
- `edge/` — кусты, молодые сосны, пни для края леса.
- `shadows/` — прозрачные тени под деревья/массы.
- `ground/` — тёмные прозрачные пятна под густой лес.
- `manifest.json` — размеры, anchors, назначение.
- `contact_sheet.png` — быстрый предпросмотр.

## Как пробовать в pipeline

1. Подложить `ground/forest_floor_dark_patch_*` внутри `deep`/`mid` зон.
2. В `edge` зоне ставить `edge/*` и small trees разреженно.
3. В `mid` зоне ставить `trees/pine_mid_*` + `clusters/canopy_cluster_small_*`.
4. В `deep` зоне ставить `clusters/canopy_cluster_large_*` и `clusters/canopy_cluster_deep_*` с overlap.
5. Все деревья сортировать по `anchor_y` / world y.

Это не финальный артпак, а быстрый набор для проверки: даст ли ForestMassOverlay правильное направление.
