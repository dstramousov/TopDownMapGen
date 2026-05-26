# TopDownMapGen versions

## v0.0.0 -> v0.0.1

- Init repo

## v0.0.1 -> v0.0.2

- Добавлена пакетная версия `0.0.2`.
- Конфиги перенесены в каталог `configs/`.
- README.md дополнен командами запуска под новую структуру.
- Добавлен минимальный smoke-тест загрузки пакета и базового конфига.

## v0.0.2 -> v0.0.3

- Упрощён `pyproject.toml`: оставлены только рабочие настройки сборки, CLI, `pytest` и `ruff`.
- Удалены преждевременные настройки `mypy`, `coverage`, расширенные classifiers/keywords и неиспользуемый блок `tool.top_down_worldgen`.
- Версия проекта поднята до `0.0.3`.
- Smoke-тест версии обновлён под новую patch-version.

## v0.0.3 -> v0.0.4

- Добавлен общий `timed_stage` для логирования старта, завершения и времени выполнения процедур.
- Добавлен флаг `--verbose` для подробного DEBUG-логирования.
- Расширено логирование CLI, pipeline, legacy runner, JSON I/O, tactical optimizer, fallback builder, objective selector и renderer.
- Версия проекта поднята до `0.0.4`.

## v0.0.4 -> v0.0.5

- Добавлен `_manifest.json` с паспортом генерации: seed, profile, размеры, timing, схемы и список файлов.
- Добавлен CLI-флаг `--no-debug-images` для отключения тяжёлых PNG debug-слоёв без отключения базового render.
- Manifest помечает primary outputs и debug-only artifacts для автоматической обработки результата.
- Версия проекта поднята до `0.0.5`.

## v0.0.5 -> v0.0.6

- `tactical_map.json` стал самодостаточным: в секцию `map` добавлены `tile_grid`, `tile_grid_format` и `tile_counts`.
- Добавлена валидация прямоугольности ASCII-карты и соответствия размеров tactical metadata.
- Версия схемы runtime tactical map обновлена до `tactical-map-v0.20`.
- Версия проекта поднята до `0.0.6`.

## v0.0.6 -> v0.0.7

- Добавлен `resolved_seed` в `_manifest.json`; фактический seed всегда является `uint64`.
- Недопустимый `seed` в конфиге больше не валит генерацию: генератор создаёт новый `uint64` seed.
- Manifest получил разделённый блок версий: generator, pipeline, schemas и debug.
- В manifest добавлен `validation_summary` для машинной проверки результата.
- PNG debug-слои выключены по умолчанию; добавлен флаг `--include-debug-layers`.
- Manifest явно перечисляет доступные и сгенерированные debug layers.

## v0.0.7 -> v0.0.8

- Нормализовано поле типа для `enemy_spawn_zones`: вместо `zone_type` теперь используется единое поле `type`.
- Версия runtime tactical schema обновлена до `tactical-map-v0.21`, debug tactical schema — до `tactical-debug-v0.20`.
- В `validation_summary` manifest-а добавлен диагностический warning `tactical_points_near_map_edge` со счётчиками near-edge tactical points.
- Warning по edge-точкам не валит генерацию и используется только как наблюдение для диагностики качества карты.
- Версия проекта поднята до `0.0.8`.

## v0.0.8 -> v0.0.9

- Добавлен final repair связности walkable-карты перед финальной validation: мелкие изолированные компоненты заливаются лесом, крупные соединяются с основной компонентой.
- `_raw_tactical_map_v015.json` переименован в стабильный `_raw_tactical_map.json`; версия схемы теперь хранится внутри файла и manifest-а.
- В raw tactical dump добавлены `schema_version`, `generator_version` и `pipeline_version`.
- Добавлен отдельный `validation_report.json` и сохранён встроенный `validation_summary` в `_manifest.json`.
- Расширены validation checks по содержимому tactical output: старт/цель, tile grid, tile counts, combat zones, spawn/fallback refs, flank route waypoints и cover refs.
- Runtime tactical schema обновлена до `tactical-map-v0.22`, manifest schema — до `generation-manifest-v3`.
- Версия проекта поднята до `0.0.9`.

## v0.0.9 -> v0.0.10

- Усилен final repair связности walkable-карты.
- Маленькие изолированные walkable-компоненты теперь удаляются до строгой валидации.
- Крупные изолированные компоненты соединяются кратчайшим carved connector path.
- Repair-метрики теперь честно учитывают failed repairs и не считают соединение успешным без уменьшения числа компонент.
- Версия проекта поднята до `0.0.10`.

## v0.0.10 -> v0.0.11

- Добавлена foundation-схема для `runtime_objects`: типы объектов, роли, высота, elevation, cover-семантика и базовые gameplay-флаги.
- В `tactical_map.json` добавлены пустые слои `runtime_objects` и `elevation`, чтобы подготовить карту к объектам поверх базового tile grid.
- Объявлены первые типы runtime-объектов: `fallen_log`, `stone_chunk`, `bush_thicket`, `rusted_barrel`, `scrap_pile`, `ammo_cache`, `medkit_cache`, `trench`.
- В validation report добавлены проверки runtime-объектов и elevation-слоя.
- Runtime tactical schema обновлена до `tactical-map-v0.23`, manifest schema — до `generation-manifest-v4`, validation report schema — до `validation-report-v2`.
- Версия проекта поднята до `0.0.11`.

## v0.0.11 -> v0.0.12

- Добавлено MVP-размещение первых runtime-объектов поверх базовой tile grid.
- Генератор теперь детерминированно размещает `fallen_log`, `stone_chunk`, `bush_thicket`, `scrap_pile` и `rusted_barrel` по `resolved_seed`.
- В `tactical_map.json` добавлен `runtime_objects_summary` со счётчиками по типам объектов.
- Расширены validation checks для runtime-объектов: непустой слой, отсутствие пересечений, запрет на blocked tiles и лимит количества объектов.
- Runtime tactical schema обновлена до `tactical-map-v0.24`, manifest schema — до `generation-manifest-v5`, validation report schema — до `validation-report-v3`.
- Версия проекта поднята до `0.0.12`.

## v0.0.12 -> v0.0.13

- Добавлен отдельный PNG debug-слой `layer_runtime_objects.png` для runtime/gameplay объектов.
- Runtime objects теперь отображаются в общем `layer_all_debug.png`.
- `runtime_objects` добавлен в список доступных debug layers manifest-а.
- Manifest schema обновлена до `generation-manifest-v6`, runtime tactical schema — до `tactical-map-v0.25`, debug layers version — до `debug-layers-v2`.
- Версия проекта поднята до `0.0.13`.

## v0.0.13 -> v0.0.14

- Добавлена генерация interest-point runtime-объектов `ammo_cache` и `medkit_cache`.
- Тайники с патронами и аптечные тайники размещаются детерминированно по `resolved_seed` и не пересекаются с уже созданными runtime-объектами.
- Расширены validation checks для interest points: наличие, лимиты количества, размещение внутри карты, отсутствие пересечений и запрет на START/GOAL.
- Runtime tactical schema обновлена до `tactical-map-v0.26`, manifest schema — до `generation-manifest-v7`, validation report schema — до `validation-report-v4`, runtime objects schema — до `runtime-objects-v3`.
- Версия проекта поднята до `0.0.14`.

## v0.0.14 -> v0.0.15

- Добавлен MVP генерации окопов (`trench`) как multi-tile runtime-объектов.
- Окопы записывают footprint в `runtime_objects` и соответствующие клетки `elevation.level = -1`.
- Runtime objects debug render уже отображает окопы в `layer_runtime_objects.png` и `layer_all_debug.png`.
- Расширены validation checks для trench/elevation: наличие окопов, лимиты количества, отрицательная elevation, footprint внутри карты, запрет на START/GOAL и blocked tiles.
- Runtime tactical schema обновлена до `tactical-map-v0.27`, manifest schema — до `generation-manifest-v8`, validation report schema — до `validation-report-v5`, runtime objects schema — до `runtime-objects-v4`.
- Версия проекта поднята до `0.0.15`.

## v0.0.15 -> v0.0.16

- Частота появления окопов немного увеличена: базовая квота `trench` поднята с 3 до 4, а допустимый верхний лимит — до 8.
- Окопы теперь размещаются раньше части вторичных runtime-объектов, чтобы реже проигрывать место декоративному заполнению.
- Добавлена поддержка Г-образных окопов (`shape = "l_shape"`) с connected footprint и угловой формой.
- В `runtime_objects_summary` добавлена статистика `trench_shapes` по формам окопов.
- В validation report добавлены проверки формы окопов: валидные shape-значения, связность footprint и наличие угла у Г-образных окопов.
- Runtime tactical schema обновлена до `tactical-map-v0.28`, manifest schema — до `generation-manifest-v9`, validation report schema — до `validation-report-v6`, runtime objects schema — до `runtime-objects-v5`.
- Версия проекта поднята до `0.0.16`.

## v0.0.16 -> v0.0.17

- Добавлены landmark runtime-объекты: `big_dead_tree`, `broken_radio_mast`, `old_checkpoint`.
- Landmark-объекты размещаются детерминированно от `resolved_seed`, редко и с минимальной дистанцией друг от друга.
- Новые ориентиры попадают в `runtime_objects`, `runtime_objects_summary`, `layer_runtime_objects.png` и `layer_all_debug.png`.
- Расширены validation checks для landmark-объектов: лимиты количества, размещение внутри карты, отсутствие пересечений, защита START/GOAL и минимальная дистанция.
- Runtime tactical schema обновлена до `tactical-map-v0.29`, manifest schema — до `generation-manifest-v10`, validation report schema — до `validation-report-v7`, runtime objects schema — до `runtime-objects-v6`.
- Версия проекта поднята до `0.0.17`.

## v0.0.17 -> v0.0.18

- Runtime-объекты получили явные `collision_profile` и `combat_properties` для будущей игровой логики движения, обзора, пуль, укрытий, лута и взрываемых объектов.
- Для окопов (`trench`) добавлены `stance_hints`: стоя персонаж считается открытым, присевший — защищённым от плоского огня.
- В validation report добавлены проверки gameplay-семантики runtime-объектов: collision profiles, combat properties, диапазоны cover/concealment, stance hints, explosive/loot tags.
- Уточнены debug-маркеры runtime-объектов, чтобы убрать конфликтующие буквы на PNG-слоях.
- Runtime tactical schema обновлена до `tactical-map-v0.30`, manifest schema — до `generation-manifest-v11`, validation report schema — до `validation-report-v8`, runtime objects schema — до `runtime-objects-v7`.
- Версия проекта поднята до `0.0.18`.

## v0.0.18 -> v0.0.19

- Добавлен слой микролокаций `places`, который группирует runtime-объекты в маленькие сцены карты.
- Добавлена схема `place_schema` и сводка `places_summary` в `tactical_map.json`.
- Первые типы сцен: `abandoned_checkpoint`, `broken_radio_site`, `old_defensive_position`, `forest_obstruction`, `small_ruin_site`.
- Manifest schema обновлена до `generation-manifest-v12`, runtime tactical schema — до `tactical-map-v0.31`, validation report schema — до `validation-report-v9`, runtime objects schema — до `runtime-objects-v8`, places schema — до `places-v1`.
- В validation report добавлены проверки `places`: наличие, уникальные id, допустимые типы, валидные ссылки на runtime-объекты, положение внутри карты, лимиты количества и минимальная дистанция.
- Версия проекта поднята до `0.0.19`.

## v0.0.19 -> v0.0.20

- Исправлен блокирующий импорт `top_down_worldgen.tactical.places`: добавлен отсутствующий модуль сборки микролокаций.
- `places` теперь корректно собираются из существующих `runtime_objects`, получают `place_schema` и `places_summary`.
- Версия проекта поднята до `0.0.20`.

## v0.0.20 -> v0.0.21

- Добавлен человекочитаемый `object_catalog.md` рядом с output-файлами генерации.
- В каталог добавлены базовые тайлы, runtime-объекты, places и фактические количества сущностей текущего прогона.
- `object_catalog.md` добавлен в manifest как `object_catalog` со схемой `object-catalog-v1`.
- В `validation_report.json` добавлен check `object_catalog_exists`.
- Версия проекта поднята до `0.0.21`.

## v0.0.21 -> v0.0.22

- Таблицы в `object_catalog.md` теперь генерируются выровненными по ширине колонок.
- Числовые колонки `Count` выравниваются вправо для лучшей читаемости в терминале.
- Schema versions подняты до `generation-manifest-v14`, `validation-report-v11`, `object-catalog-v2`.
- Версия проекта поднята до `0.0.22`.

## v0.0.22 -> v0.0.23

- Добавлены 12 новых runtime-объектов для более насыщенного наполнения карты: `car_wreck`, `abandoned_backpack`, `field_tent`, `dead_campfire`, `broken_generator`, `cable_spool`, `warning_sign`, `old_grave_marker`, `pit`, `earth_berm`, `old_well`, `abandoned_cart`.
- Новые объекты получили роли, русские имена, gameplay-семантику, `collision_profile`, `combat_properties`, debug-символы и описания в `object_catalog.md`.
- Новые объекты размещаются детерминированно от `resolved_seed` с низкими квотами, чтобы не превращать карту в свалку.
- `pit` теперь добавляет клетки уровня `-1` в слой `elevation`, как небольшая яма/провал.
- `layer_runtime_objects.png` и `layer_all_debug.png` отображают новые runtime-объекты.
- Schema versions подняты до `generation-manifest-v15`, `validation-report-v12`, `object-catalog-v3`, `runtime-objects-v9`, `tactical-map-v0.32`.
- Версия проекта поднята до `0.0.23`.

## v0.0.23 -> v0.0.24

- Добавлен структурированный экспорт `map_package/` рядом с существующими output-файлами.
- Новый пакет содержит `map.json`, слои `tile_grid`, `movement_costs`, `collision`, `elevation`, gameplay-слои и object-слои.
- `_manifest.json` теперь включает файлы `map_package` как primary outputs и описывает новые schema versions.
- `validation_report.json` проверяет наличие базовых файлов нового `map_package`.
- Schema versions подняты до `generation-manifest-v16`, `validation-report-v13`, `map-package-v1`.
- Версия проекта поднята до `0.0.24`.

## v0.0.24 -> v0.0.25

- Добавлена документация `docs/map_package_v1.md` с описанием структуры `map_package/`, обязательных файлов, координат и назначения слоёв.
- Добавлена инструкция `docs/game_consumer_guide.md` для первой интеграции пакета карты в игру.
- Добавлен пример `examples/read_map_package.py`, который находит `map_package/map.json` через `_manifest.json` и строит краткую сводку карты.
- Добавлены тесты, проверяющие наличие документации и работоспособность примера загрузчика на минимальном пакете.
- Версия проекта поднята до `0.0.25`.

## v0.0.25 -> v0.0.26

- Добавлены явные игровые слои `terrain.json` и `start_goal.json` в `map_package/`.
- `collision.json` переведён на runtime-ready формат с boolean rows и типами terrain, а не только ASCII-символами.
- `movement_costs.json` дополнен `costs_by_type`, чтобы игра могла работать с типами тайлов.
- `_manifest.json` и validation расширены новыми слоями пакета карты.
- Документация и пример загрузчика обновлены под новые слои.
- Версия проекта поднята до `0.0.26`.

## v0.0.26 -> v0.0.27

- Добавлены machine-readable catalogs для `map_package`: `catalogs/tile_types.json` и `catalogs/object_types.json`.
- `map_package/map.json`, `_manifest.json`, validation и пример загрузчика обновлены под новые catalogs.
- Документация формата и game consumer guide дополнены разделами про type catalogs.
- Версия проекта поднята до `0.0.27`.

## v0.0.27 -> v0.0.28

- Добавлен renderer-ready каталог `map_package/render/` с `render_profile.json`, `tile_render_hints.json` и `object_render_hints.json`.
- `map_package/map.json` теперь содержит секцию `render` со ссылками на render hint-файлы.
- `_manifest.json` и validation расширены новыми schema version и проверками render hint outputs.
- Документация и пример загрузчика обновлены для render hints.
- Версия проекта поднята до `0.0.28`.

## v0.0.28 -> v0.0.29

- Унифицирован CLI output contract: `-o output` теперь создаёт `output/generated_map.txt` и все остальные артефакты в этой же папке.
- `-o output/generated_map.txt` сохраняет прежнее поведение, но явно подтверждает единый output root для legacy-файлов и `map_package/`.
- Pipeline теперь нормализует output target через `OutputPaths.from_cli_output`, чтобы manifest, legacy outputs и structured package всегда относились к одному root.
- Документация формата и game consumer guide дополнены правилом “один запуск = одна output-папка = один manifest”.
- Добавлены тесты для directory/file CLI output targets.
- Версия проекта поднята до `0.0.29`.


## v0.0.29 -> v0.0.30

- Добавлен внешний инспектор `examples/inspect_world_package.py`, который проверяет `output/` как независимый consumer через `_manifest.json` и `map_package/map.json`.
- Инспектор выводит краткую консольную сводку по размерам карты, слоям, collision, movement, elevation, объектам, gameplay, catalogs и render hints.
- Ошибки загрузки пакета теперь дают понятный `World package: FAILED` и ненулевой exit code для smoke-check сценариев.
- Документация формата и game consumer guide дополнены использованием инспектора перед передачей пакета в игру или renderer.
- Добавлены тесты для успешной проверки минимального пакета и ошибки на отсутствующем пакете.
- Версия проекта поднята до `0.0.30`.

## v0.0.30 -> v0.0.31

- Добавлен внешний preview renderer `examples/render_world_preview.py`, который строит простую PNG-картинку только из публичного `output/_manifest.json` и `map_package/`.
- Preview renderer выводит краткую консольную сводку по карте, terrain, collision, runtime objects, start/goal и пути к PNG.
- Renderer поддерживает разные входные пути: output root, `_manifest.json`, `map_package/` или `map_package/map.json`.
- Документация формата и game consumer guide дополнены визуальным smoke-test сценарием после инспектора.
- Добавлены тесты для успешного PNG preview и понятной ошибки на отсутствующем пакете.
- Версия проекта поднята до `0.0.31`.

## v0.0.31 -> v0.0.32

- Добавлен `docs/world_building_algorithm.md` с пошаговым алгоритмом построения runtime-мира из `output/_manifest.json` и `map_package/`.
- Добавлен `docs/world_package_file_map.md` с картой файлов output root, назначением слоёв, catalogs, render hints и проверочных tools.
- `README.md` дополнен быстрым запуском, проверкой world package и ссылками на основные документы интеграции.
- `docs/game_consumer_guide.md` теперь ссылается на новые документы для внешних consumers.
- Тест документации расширен проверкой новых файлов.
- Версия проекта поднята до `0.0.32`.


## v0.0.32 -> v0.0.33

- Добавлена footprint model v1 для runtime objects: `footprint`, `collision_footprint`, `visual_bounds`, `pivot` и `anchor` теперь доступны на объектных instances.
- Крупные объекты вроде палаток, машин, колодцев, блокпостов, ям, брёвен, насыпей и траншей теперь могут занимать несколько тайлов.
- `object_types.json`, inspector и preview renderer дополнены footprint/collision/visual metadata.
- Validation расширена проверками footprint, collision footprint, visual bounds и pivot у runtime objects.
- Документация world package и алгоритма построения мира дополнена правилами чтения multi-tile объектов.
- Версия проекта поднята до `0.0.33`.
