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

## v0.0.33 -> v0.0.34

- Добавлены два тестовых типа заглублённых бункеров: `buried_bunker_2x2` и `buried_bunker_2x3`.
- Бункеры размещаются как multi-tile runtime objects с footprint, collision footprint, visual bounds и firing ports.
- Бункерные footprint-клетки помечаются как внутренний уровень `-1` для будущей модели уровней.
- Обновлены object catalogs, render hints, validation checks и документация по package-файлам.
- Версия проекта поднята до `0.0.34`.


## v0.0.34 -> v0.0.35

- Добавлен пользовательский блок `generation_tuning` для управления водой, лесами, открытыми местами, руинами, строениями, дорогами, декором и бункерами.
- Legacy engine теперь применяет tuning-масштабы и пишет quality-проблемы как warnings вместо падения на пользовательских настройках.
- `output/generation.log` теперь создаётся по умолчанию и попадает в manifest как debug artifact.
- Preview/debug renderers выделяют бункеры крупными `B`-клетками и показывают бойницы, чтобы их было видно на PNG.
- Документация и configs обновлены под новый tuning-контракт.
- Версия проекта поднята до `0.0.35`.

## v0.0.35 -> v0.0.36

- Вода получила отдельные настройки `water_patch_count_scale`, `water_patch_size_scale` и `water_patch_density`.
- `water_scale` теперь работает как общий множитель количества water patches вместе с `water_patch_count_scale`.
- Максимальный безопасный scale-диапазон поднят до `0.0..10.0`, а `water_patch_density` зажимается отдельно в `0.0..1.0`.
- Формула размещения water patches теперь влияет не только на количество, но и на радиус/плотность луж.
- README, docs, configs и тесты обновлены под новый tuning-контракт воды.
- Версия проекта поднята до `0.0.36`.

## v0.0.36 -> v0.0.37

- Добавлен `map_package/markers.json` для стартовой точки, цели и игровых маркеров без смешивания с terrain.
- Добавлен `map_package/runtime_grids.json` с готовыми runtime-сетками для движения, коллизии, снарядов, видимости, укрытий, маскировки и высоты.
- `_manifest.json` и `map_package/map.json` обновлены до новых схем и теперь явно ссылаются на markers/runtime_grids.
- Inspector выводит количество markers и runtime grids.
- Validation проверяет наличие новых package-файлов.
- Версия проекта поднята до `0.0.37`.

## v0.0.37 -> v0.0.38

- `places.json` обновлён до `places-v2`: места теперь имеют `bounds`, `entrances`, `danger_level`, `loot_level`, `story_role`, `encounter_type`, `connected_places`, `object_refs`, `marker_refs`, `route_refs` и `biome_tags`.
- Добавлен новый тип `bunker_site`, который группирует заглублённые бункеры и ближайшие defensive/runtime objects в осмысленную локацию.
- Генератор теперь связывает места между собой через ближайшие `connected_places`, чтобы подготовить основу для будущего `world_graph.json`.
- Validation расширена проверками v2-полей places: bounds, entrances, metadata и связей между местами.
- Документация world package и алгоритма построения мира обновлена под places v2.
- Версия проекта поднята до `0.0.38`.

## v0.0.38 -> v0.0.39

- Добавлен `map_package/world_graph.json` как семантический граф мира.
- `map.json`, manifest, inspector и validation знают про world graph.
- Документация world package обновлена под новый файл графа.
- Версия проекта поднята до `0.0.39`.

## v0.0.39 -> v0.0.40

- Добавлен `map_package/routes.json` с семантическими типами маршрутов: `main_road`, `side_path`, `hidden_path`, `patrol_route` и `escape_route`.
- `map_package/map.json`, `_manifest.json`, validation и inspector теперь знают про routes.
- Route records строятся из `world_graph.json` и содержат `node_ids`, `edge_ids`, `waypoints`, `cost_tiles`, `bidirectional` и `tags`.
- Документация world package обновлена: routes описывают смысл маршрутов, а не заменяют tile pathfinding.
- Версия проекта поднята до `0.0.40`.

## v0.0.40 -> v0.0.41

- Усилена package validation для `markers`, `runtime_grids`, `places`, `world_graph` и `routes`.
- Validation теперь проверяет ссылки между package-файлами, совпадение размеров runtime-сеток и валидность start/goal относительно collision grid.
- Schema versions обновлены до `generation-manifest-v28` и `validation-report-v24`.
- Версия проекта поднята до `0.0.41`.

## v0.0.41 -> v0.0.42

- Добавлен `map_package/elevation_model.json` как публичный контракт уровней высоты `-1..4`.
- `elevation_model.json` описывает значения уровней, типы переходов, правила movement, line-of-sight, projectiles и render order.
- `map_package/map.json`, `_manifest.json`, validation и inspector теперь знают про elevation model.
- Validation проверяет, что `height_grid` использует уровни, описанные в elevation model.
- Документация world package обновлена под elevation model v1.
- Версия проекта поднята до `0.0.42`.

## v0.0.42 -> v0.0.43

- Добавлены отдельные `map_package/elevation_features.json` и `map_package/elevation_transitions.json`.
- `elevation_model.json` поднят до v2 и теперь связан с явными feature/transition пакетами.
- `earth_berm` стал реальной raised-ground feature уровня `+1`.
- Усилены inspector, validation, manifest и документация для elevation features/transitions.
- Версия проекта поднята до `0.0.43`.

## v0.0.43 -> v0.0.44

- Добавлены реальные elevation features для полного диапазона уровней `-1..4`: `hill`, `wooden_bridge`, `stone_ramp`, `stone_stairs`, `ruin_platform`, `watchtower` и `ancient_beacon`.
- Runtime height grid теперь получает положительные уровни от generated runtime objects, а не только `-1` от ям/траншей/бункеров.
- `elevation_model.json`, `elevation_features.json` и `elevation_transitions.json` подняты до новых схем и описывают новые feature/transition типы.
- Inspector и validation продолжают проверять package после расширения elevation-слоя.
- Документация обновлена под elevation movement features v1.
- Версия проекта поднята до `0.0.44`.

## v0.0.44 -> v0.0.45

- Усилена elevation-aware validation: проверяются уровни `height_grid`, соответствие transition records фактической сетке высот и наличие movement rules.
- Validation теперь проверяет достижимость start/goal и main_path с учётом `elevation_transitions`.
- `elevation_transitions.json` поднят до `elevation-transitions-v3` и содержит `movement_allowed`, `movement_rule`, `abs_delta` и `feature_refs`.
- `elevation_model.json` поднят до `elevation-model-v4`.
- Версия проекта поднята до `0.0.45`.


## v0.0.45 -> v0.0.46

- Preview renderer получил elevation overlay для уровней `-1..4`.
- Preview renderer получил transition overlay для `ramp`, `stairs`, `bridge`, `slope` и steep elevation edges.
- Консольная сводка preview показывает найденные elevation levels и число elevation transitions.
- Документация обновлена командами проверки elevation/debug preview.
- Версия проекта поднята до `0.0.46`.

## v0.0.46 -> v0.0.47

- Зафиксирован финальный публичный контракт `elevation v1` в `docs/elevation_v1.md`.
- `elevation_model.json` поднят до `elevation-model-v5` и теперь содержит `v1_completion` с уровнями `-1..4`, required feature families и consumer-ready файлами.
- `elevation_features.json` и `elevation_transitions.json` получили v1 completion metadata для внешних consumer-ов.
- Inspector показывает статус elevation v1 и предупреждает о недостающих уровнях/features.
- Добавлен smoke-test, который проверяет полный elevation v1 contract: уровни `-1..4` и основные feature families.
- Версия проекта поднята до `0.0.47`.

## v0.0.47 -> v0.0.48

- Добавлен `map_package/gameplay_zones.json` с нейтральными gameplay-зонами: `safe_area`, `encounter_area`, `loot_area`, `danger_area`, `story_area`, `extraction_area` и другими типами.
- `map_package/map.json`, `_manifest.json`, inspector и validation теперь знают про gameplay zones.
- `world_graph.main_path` теперь обязан иметь edge для каждой соседней пары `node_ids`; validation ловит логически разорванный main path.
- Генератор добавляет недостающие main-path edges, чтобы `node_ids` и `edge_ids` согласованно описывали маршрут.
- Версия проекта поднята до `0.0.48`.


## v0.0.48 -> v0.0.49

- `places.json` поднят до `places-v3` и теперь генерирует более плотный набор смысловых мест.
- Добавлены новые типы places: `blocked_road`, `swamp_crossing`, `ruined_camp`, `small_loot_pocket`, `ambush_clearing`, `watchtower_area`, `bunker_outer_area`, `bunker_inner_area`, `secret_cache`, `dangerous_lowland` и `raised_platform_site`.
- Целевое количество meaningful places для больших карт поднято до диапазона 8–15, без жёсткого падения на маленьких/бедных тестовых картах.
- World graph, routes и gameplay zones теперь получают более богатую базу places и строят больше side paths/route links.
- Версия проекта поднята до `0.0.49`.

## v0.0.49 -> v0.0.50

- `world_graph.json` поднят до `world-graph-v2` и теперь строит более плотный смысловой граф на основе meaningful places.
- Добавлены proximity edges между близкими places, чтобы граф меньше походил на формальный список точек.
- `side_paths` теперь имеют anchor node, edge ids и cost, а не просто одиночный target place.
- `dead_ends` теперь считаются только для meaningful places, а не для всех markers, поэтому статистика больше не заваливается мусорными marker leafs.
- `secret_areas` теперь строятся из secret/cache/high-loot places и релевантных marker nodes.
- `world_graph.summary` получил показатели meaningful place coverage и quality status для внешних consumer-ов.
- Версия проекта поднята до `0.0.50`.

## v0.0.50 -> v0.0.51

- Preview renderer получил semantic overlays для `places`, `gameplay_zones`, `routes` и `world_graph`.
- Добавлен общий флаг `--semantic-overlays`, который включает все смысловые overlay-слои сразу.
- Консольная сводка preview теперь показывает количество places, gameplay zones, routes и world graph edges.
- Документация обновлена командами визуальной проверки graph/zones/routes/places.
- Версия проекта поднята до `0.0.51`.

## v0.0.51 -> v0.0.52

- Runtime objects получили `interaction_shape`, `sort_anchor`, `draw_layer` и `occlusion_hint`.
- Runtime object schema поднята до `runtime-objects-v13`, object instances — до `object-instances-v4`, object types catalog — до `object-types-catalog-v5`, object render hints — до `object-render-hints-v5`.
- Validation теперь проверяет interaction shapes, sort anchors, draw layers и occlusion hints у всех runtime objects.
- Object catalogs и render hints экспортируют новые поля для внешнего движка и top-down renderer-а.
- Документация обновлена object interaction/sort model.
- Версия проекта поднята до `0.0.52`.

## v0.0.52 -> v0.0.53

- Добавлен next-generation elevation MVP на базе FBM/value noise, domain warp, ridged component и террасирования уровней.
- Диапазон высот расширен до `-5..20`, а `height_grid` теперь заполняется как полноценный слой карты, а не только редкими object-derived cells.
- Terrain-aware коррекция удерживает дороги около уровня земли, воду в низинах, а start/goal на базовом уровне `0`.
- Экспорт `elevation_model.json` теперь описывает все уровни `-5..20`, а natural slope-переходы с delta=1 считаются допустимыми для движения.
- Добавлены JSON-отчёты `world_density_report.json`, `elevation_density_report.json` и `world_summary_report.json`.
- CLI выводит итоговую человекочитаемую summary-сводку после генерации.
- Helper `./r` получил явные стадии `cleanup output`, `world generation` и `world preview`.
- Версия проекта поднята до `0.0.53`.

## v0.0.53 -> v0.0.54

- Обычный CLI-запуск больше не печатает подробные INFO-логи в консоль; детальный лог пишется в `output/generation.log`.
- Добавлен CLI-флаг `--summary-file`, чтобы helper `./r` мог вывести summary последним блоком после preview.
- Helper `./r` теперь показывает только стадии, world preview и финальную summary-сводку; технический cleanup-вывод скрыт.
- В summary исправлено выравнивание блока Debug files и добавлен путь к `generation.log`.
- Версия проекта поднята до `0.0.54`.

## v0.0.54 -> v0.0.55

- Elevation generator переведён на size-aware Red Blob-подход: сначала выбирается профиль размера карты, потом строится FBM/redistribution/terraced heightmap.
- Формат высот остаётся `-5..20`, но активный диапазон, редкие уровни, размер террас, smoothing и max natural delta теперь зависят от размера карты.
- Для маленьких карт генератор автоматически сужает диапазон высот, чтобы не создавать резкие скачки и микротеррасы в один-два тайла.
- Ground corridor вокруг маршрута `start -> goal` теперь сглаживается радиусом профиля, а не просто прорезает одиночную линию уровня `0`.
- В elevation reports и console summary добавлен блок `elevation profile` с map class, active/rare range, terrace target, smoothing passes и max natural delta.
- Версия проекта поднята до `0.0.55`.

## v0.0.55 -> v0.0.56

- Preview renderer получил географическую hypsometric-палитру высот для всего диапазона `-5..20`.
- `full_world_preview.png` теперь может выводить правую legend-панель с профилем elevation, bands, counts и процентами по каждому уровню.
- Добавлен отдельный `output/elevation_preview.png`: чистая карта высот без terrain/object overlays, с контурами и легендой.
- Helper `./r` теперь строит оба preview-файла перед финальной summary.
- В Debug files summary добавлены пути к `full_world_preview.png` и `elevation_preview.png`.
- Версия проекта поднята до `0.0.56`.

## v0.0.56 -> v0.0.57

- Elevation generator получил отдельный geographic pass: macro regions, moisture field и geographic masks перед финальным террасированием.
- Red Blob-подход уточнён как geography-first: крупные формы мира строятся до visual/object placement и не зависят от руин, бункеров, дорог или других gameplay-фич.
- В elevation reports добавлены macro regions, moisture stats, slope bands и маски `basins`, `lowlands`, `plains`, `hills`, `plateaus`, `ridges`, `mountains`, `peaks`.
- Preview renderer получил standalone-режимы `--geography-only`, `--moisture-only` и `--slope-only`.
- Helper `./r` теперь дополнительно создаёт `geography_preview.png`, `moisture_preview.png` и `slope_preview.png`.
- Версия проекта поднята до `0.0.57`.

## v0.0.57 -> v0.0.58

- Разделён preview смыслов высоты: география, вода и структурная глубина больше не смешиваются в один "синий низ".
- `elevation_preview.png` теперь красит воду только по terrain/hydrology source, а bunker/trench/pit depth показывает отдельной структурной палитрой.
- `geography_preview.png` теперь использует чистую географическую высоту до object-derived elevation overrides.
- Добавлен `output/elevation_source_preview.png` для контроля источников высоты: geography/water/structural.
- В geography/elevation reports добавлены `source_grid`, `geographic_level_grid`, `runtime_level_grid` и source summary.
- Версия проекта поднята до `0.0.58`.

## v0.0.58 -> v0.0.59

- Добавлен standing-water / lowland слой диагностики без рек и flow-map.
- География теперь отдельно классифицирует deep/shallow water, wet lowlands, dry lowlands, dry land и structural depth.
- В отчёты добавлены standing-water summary и `water_lowland_grid`.
- Добавлен debug preview `output/water_lowland_preview.png` и CLI-режим `--water-lowlands-only`.
- Summary теперь показывает, что water model работает без рек и не смешивает структурную глубину с водой.
- Версия проекта поднята до `0.0.59`.


## v0.0.59 -> v0.0.60

- Исправлен источник шахматных elevation-артефактов: старый simultaneous min/max relax мог заставлять соседние клетки обмениваться высокими/низкими уровнями и создавать checkerboard-террасы.
- Relax высот переведён на stable median-envelope pass с in-place обновлением, чтобы резкие перепады сходились к локальной форме вместо ping-pong oscillation.
- Имя elevation generator обновлено до `size_aware_red_blob_geography_v2`.
- Географические preview должны давать плавные террасы без ряби из чередующихся уровней.
- Версия проекта поднята до `0.0.60`.

## v0.0.60 -> v0.0.61

- Добавлен pseudo-3D preview чистой географической высоты из четырёх углов карты: NW, NE, SE, SW.
- Новый renderer `examples/render_geography_3d_preview.py` строит PNG 2560×1440 в `output/geography_3d_preview/`.
- `./r` теперь добавляет стадию `3d geography preview` и генерирует четыре 3D diagnostic PNG после обычных 2D geography/slope preview.
- Summary/debug files теперь перечисляет новые 3D preview-файлы.
- Версия проекта поднята до `0.0.61`.

## v0.0.61 -> v0.0.62

- 3D preview renderer получил режим `--overlay walkability`, который накладывает проходимость поверх чистой географической высоты.
- Добавлены четыре PNG `walkability_nw/ne/se/sw.png` в `output/geography_3d_preview/` с разрешением 2560×1440.
- Walkability overlay показывает reachable, slow terrain, blocked, water, structural depth, unreachable walkable, start и goal.
- Renderer дополнительно пишет `output/geography_3d_preview/walkability_report.json` с количеством тайлов по категориям.
- Helper `./r` теперь добавляет стадию `3d walkability preview` после чистой 3D-географии.
- Summary/debug files теперь перечисляет новые 3D walkability preview-файлы и отчёт.
- Версия проекта поднята до `0.0.62`.


## v0.0.62 -> v0.0.63

- Добавлен 3D traversal overlay, который проверяет проходимость с учётом географической высоты и запрещает естественные переходы с перепадом больше одного уровня.
- В `geography_3d_preview` добавлены четыре PNG `traversal_nw/ne/se/sw.png` и `traversal_report.json` с 2D/3D reachability, слишком крутыми тайлами и passable cliff edges.
- Structural depth в 3D overlay больше не красит всю колонну в фиолетовый: бункеры/ямы/траншеи показываются маркером на поверхности географии.
- Helper `./r` теперь добавляет стадию `3d traversal preview`, а summary/debug files перечисляет новые traversal-артефакты.
- Версия проекта поднята до `0.0.63`.

## v0.0.63 -> v0.0.64

- Добавлен repair-pass 3D traversal consistency для start-connected walkable области.
- Географические уровни теперь мягко чинятся там, где 2D-проходимость ломалась перепадом высоты больше допустимого `max_natural_delta`.
- `traversal_report.json` теперь различает 3D-недостижимые тайлы и отдельные 2D terrain islands.
- Summary расширен строкой `traversal repair` с количеством исправленных недостижимых тайлов.
- Версия проекта поднята до `0.0.64`.

## v0.0.64 -> v0.0.65

- Добавлена policy-очистка tiny 2D terrain islands перед построением runtime layers.
- Малые isolated walkable-компоненты, не связанные со стартовой областью, теперь переводятся в ближайший blocker terrain и перестают выглядеть как ложные playable-острова.
- Крупные isolated-регионы не соединяются и не удаляются: они сохраняются, но явно попадают в `terrain_island_report.json`.
- Summary и `elevation_density_report.json` теперь показывают, сколько малых островов удалено и сколько крупных сохранено.
- Версия проекта поднята до `0.0.65`.


## v0.0.65 -> v0.0.66

- Добавлен отсутствующий модуль `top_down_worldgen.tactical.terrain_islands`, который был подключён в pipeline в `v0.0.65`.
- Реализованы `elevation_cell_points()` и `repair_terrain_islands()` для удаления мелких 2D walkable-островов и отчёта `terrain_island_report.json`.
- Версия проекта поднята до `0.0.66`.

## v0.0.66 -> v0.0.67

- Elevation pipeline переведён на polygon-inspired macro geography: высота теперь строится от мягкой карты крупных регионов, а не только от FBM-шумов.
- Macro regions получили базовую высоту, влажность, roughness, priority и граф соседства регионов для диагностики формы мира.
- В `elevation_generation_report` добавлен `region_grid` и serializable region graph, чтобы видеть, какой регион управляет каждым тайлом.
- Консольный summary теперь показывает количество macro region graph edges.
- Имя elevation generator обновлено до `size_aware_polygonal_macro_geography_v1`.
- Smoke-тест default config обновлён под текущий размер карты 192x192.
- Версия проекта поднята до `0.0.67`.

## v0.0.67 -> v0.0.68

- Добавлен проход сглаживания walkable-стыков macro-регионов без изменения moisture/wet-lowland/water model.
- Main route теперь выравнивается по 3D-рельефу до финального traversal repair: semantic places собираются до elevation pass, затем маршрут получает естественный slope corridor с `delta <= max_natural_delta`.
- В elevation report и console summary добавлены `region_transition_shaping` и `main_route_alignment`.
- Генератор переименован в `size_aware_polygonal_macro_geography_v2`.
- Версия проекта поднята до `0.0.68`.

## v0.0.68 -> v0.0.69

- Добавлены пользовательские elevation style presets для управления характером рельефа из public config.
- Поддержаны стили `flatland`, `rolling_hills`, `normal`, `rugged`, `mountainous`, `plateau`.
- `configs/default.json` получил блок `elevation.style`, по умолчанию `normal`.
- Pipeline передаёт выбранный стиль в elevation generator; summary/report теперь показывают активный стиль рельефа.
- Генератор переименован в `size_aware_polygonal_macro_geography_v3`.
- Версия проекта поднята до `0.0.69`.

## v0.0.69 -> v0.0.70

- Восстановлены документы публичного контракта `map_package/`, которые уже указаны в README и проверяются тестом документации.
- Добавлены `docs/map_package_v1.md`, `docs/game_consumer_guide.md`, `docs/world_building_algorithm.md`, `docs/world_package_file_map.md`.
- Документация фиксирует текущую elevation-модель `-5..20`, отличие low ground от actual water, runtime grids, semantic world graph, routes и порядок чтения пакета внешней игрой.
- Версия проекта поднята до `0.0.70`.

## v0.0.70 -> v0.0.71

- Добавлен инструмент `tools/render_elevation_style_gallery.py` для сравнения elevation style presets на одном seed.
- Gallery-режим генерирует отдельные output-папки для `flatland`, `rolling_hills`, `normal`, `rugged`, `mountainous`, `plateau` без изменения алгоритма генерации.
- Для каждого стиля создаются `geography_preview.png`, `elevation_preview.png`, `slope_preview.png`, а также общий `style_gallery.png`, `style_comparison_report.json` и `style_comparison_summary.md`.
- Версия проекта поднята до `0.0.71`.

## v0.0.71 -> v0.0.72

- Подкручены elevation style presets по новой пользовательской спецификации диапазонов и частоты уровня.
- `flatland` теперь использует диапазон `-5..4`, частую мягкую волну и больше нижних уровней.
- `rolling_hills` теперь использует диапазон `-5..10`, среднюю волну и настроен как основной игровой кандидат.
- `mountainous` и `plateau` используют полный диапазон `-5..20`, но различаются частотой: частые горные изменения против редких крупных плато.
- В профиль elevation добавлены `wave_frequency` и `character`, summary теперь печатает эти поля.
- Генератор переименован в `size_aware_polygonal_macro_geography_v4`.
- Версия проекта поднята до `0.0.72`.

## v0.0.72 -> v0.0.73

- Добавлен стиль elevation `super_flatland`.
- Стиль `super_flatland` ограничивает активный и редкий диапазон высот до `-1..1`.
- `super_flatland` добавлен в публичный config validation и в elevation style gallery.
- В отчёте профиля стиль отображается как `nearly flat -1..1 micro relief` с частотой `soft`.
- Обновлена документация `docs/map_package_v1.md`.
- Версия проекта поднята до `0.0.73`.

## v0.0.73 -> v0.0.74

- Добавлен изолированный post-elevation `RiverGenerator` с ограниченной шириной русла.
- Добавлено локальное затопление связанных низин с лимитами площади и расстояния.
- Добавлены river config, `river_report.json`, `river_preview.png` и диагностические данные в tactical map.


## v0.0.74 -> v0.0.75

- Добавлен пропущенный модуль `top_down_worldgen/tactical/river.py`, необходимый для запуска river pipeline.
- Добавлены unit-тесты изолированного генератора реки.
- Исправлена поставка патча: новые файлы теперь включены в diff.

## v0.0.75 -> v0.0.76

- Полностью удалён экспериментальный post-elevation `RiverGenerator`.
- Удалены river config, pipeline hook, river preview/report и river diagnostics.
- Удалены тесты экспериментального генератора реки; генерация возвращена к состоянию без рек.
- Версия проекта поднята до `0.0.76`.

## v0.0.76 -> v0.0.77

- Консольный вывод `./r` полностью переведён на русский язык и сокращён до читаемого поэтапного отчёта.
- Удалены многократно повторявшиеся блоки `World preview / Rendered`; каждый этап теперь печатает одну строку и время выполнения.
- Итоговый summary сокращён до ключевых показателей карты, проходимости, структуры мира и предупреждений validation.
- Добавлено общее время выполнения и компактная сводка созданных preview-файлов.
- Версия проекта поднята до `0.0.77`.

## v0.0.77 -> v0.0.78

- Переведено название этапа `3D-traversal` в консольном выводе на `3D-связность`.
- Технический warning `quality.map_package_main_path_elevation_reachable` заменён понятным русским описанием.
- Показатель `болота / вода` переименован в `болотная местность`, чтобы не дублировать отдельную статистику стоячей воды.
- Версия проекта поднята до `0.0.78`.

## v0.0.78 -> v0.0.79

- Выделен публичный ранний `GeographyDraft` с непрерывными полями высоты, влажности и макрорегионов.
- Черновая география теперь строится до legacy terrain-генератора и повторно используется финальным elevation без изменения карты.
- Добавлена строгая проверка соответствия draft размеру, seed и elevation style.
- Добавлены тесты детерминированности и идентичности результата с прежним расчётом.
- Версия проекта поднята до `0.0.79`.

## v0.0.79 -> v0.0.80

- Ранний `GeographyDraft` сериализуется в компактный guidance-файл и передаётся из pipeline в legacy terrain-генератор.
- Добавлен изолированный `TerrainGuidance`: центры регионов, руины, поляны и дороги теперь предпочитают ровные участки и обходят крутые склоны/обрывы.
- Добавлен geography-aware coarse A* для дорожной сети с безопасным fallback на прежний winding path.
- Добавлены `terrain_guidance_report.json`, консольная диагностика адаптации terrain и manifest-описания новых служебных артефактов.
- Версия проекта поднята до `0.0.80`.

## v0.0.80 -> v0.0.81

- Финальная природная сетка высот теперь формируется до legacy terrain-генератора.
- В terrain guidance добавлены натуральные integer elevation/slope grids; поздний elevation-проход повторно использует раннюю географию.
- Добавлена контрольная проверка эквивалентности ранней природной географии перед terrain-зависимыми адаптациями.
- Версия проекта поднята до `0.0.81`.

## v0.0.81 -> v0.0.82

- Открытая земля, дороги и локальная вода теперь учитывают natural barrier и wetland suitability.
- Лесные кластеры учитывают влажность, высоту и уклон; добавлена диагностика отклонённых кандидатов.
- Добавлена проверка перепада высот внутри footprint руин и расширен terrain guidance report.
- Версия проекта поднята до `0.0.82`.

## v0.0.82 -> v0.0.83

- Исправлена диагностика дорожных склонов: трудные участки (`delta == 2`) и природные обрывы (`delta > 2`) теперь считаются раздельно по integer elevation.
- `traversal repair` получил отчёт о доле изменённой карты, направлениях и величине коррекции высот, а также разбивку изменений по типам terrain.
- Консольный итог теперь показывает процент карты и основные категории terrain, затронутые repair.
- Версия проекта поднята до `0.0.83`.

## v0.0.83 -> v0.0.84

- Дороги и маркеры сценария больше не принудительно выравниваются к уровню `0`; они сохраняют природную высоту географии.
- Устранён главный источник массового traversal repair на дорогах и соседней открытой земле.
- В traversal repair report добавлен список изменённых тайлов и отдельный preview сравнения высот до/после repair.
- Версия проекта поднята до `0.0.84`.

## v0.0.84 -> v0.0.85

- Добавлен единый контракт `TraversalRules` для естественных перепадов высот.
- Traversal repair, 3D-preview и validation используют общий лимит `max_natural_delta = 1`.
- Проверка маршрутов разрешает естественные переходы в пределах лимита без обязательного structural connector.
- Публичный `elevation_model.json` теперь явно экспортирует числовой лимит естественного перепада.
- Версия проекта поднята до `0.0.85`.

## v0.0.85 -> v0.0.86

- Исправлен запуск `render_geography_3d_preview.py` как самостоятельного скрипта: корень проекта добавляется в путь импорта до загрузки `top_down_worldgen`.
- Восстановлена генерация 3D-preview без необходимости вручную задавать `PYTHONPATH`.
- Добавлен smoke-тест запуска 3D-renderer из внешнего рабочего каталога.
- Версия проекта поднята до `0.0.86`.


## v0.0.86 -> v0.0.87

- Добавлен комбинированный комплект 3D-preview из четырёх камер: elevation, semantic terrain и проходимость на одной карте.
- Тайлы леса отображаются небольшими объёмными деревьями на фактической высоте, а заблокированные, медленные, водные и структурные области получают отдельную диагностику.
- Команда `./r` создаёт `terrain_traversal_{nw,ne,se,sw}.png` и `terrain_traversal_report.json`; количество preview увеличено до 24.
- Версия проекта поднята до `0.0.87`.

## v0.0.87 -> v0.0.88

- Добавлено позднее детерминированное прореживание визуальных деревьев по высоте и уклону.
- На уровнях 18..20 визуальные деревья полностью удаляются, collision и walkability не меняются.
- В map package добавлен `render/vegetation_visual.json`, комбинированный 3D-preview использует эту маску.
- Версия проекта поднята до `0.0.88`.


## v0.0.88 -> v0.0.89

- Отрицательные уровни получили гидрологическую семантику: -5..-2 являются непроходимой водой, -1 — медленной влажной кромкой.
- Обычные деревья удаляются на уровнях -5..-1; на -1 детерминированно размещается камыш с настраиваемой густотой.
- Вероятность камыша уменьшается рядом с более глубокими уровнями воды; terrain, collision, movement grids и 3D-preview используют общую модель.
- Версия проекта поднята до `0.0.89`.


## v0.0.89 -> v0.0.90

- START и GOAL теперь выбираются после финальной гидрологии внутри одной крупнейшей 3D-проходимой сухой компоненты.
- Старые маркеры корректно возвращаются в итоговый terrain, а новые точки выбираются детерминированно, вдали друг от друга и вне runtime-объектов.
- Камыш в комбинированном 3D-preview отображается простой контрастной оранжевой точкой.
- Версия проекта поднята до `0.0.90`.

## v0.0.90 -> v0.0.91

- Добавлен отсутствовавший модуль позднего выбора START/GOAL, из-за которого v0.0.90 не запускался.
- Восстановлены детерминированный выбор точек в крупнейшей сухой 3D-проходимой компоненте и маркировка затопленных runtime-объектов.
- Добавлены тесты позднего выбора START/GOAL и обработки runtime-объектов после гидрологии.
- Версия проекта поднята до `0.0.91`.


## v0.0.91 -> v0.0.92

- Добавлено детерминированное визуальное прореживание лесной кромки на глубину до четырёх тайлов без изменения collision и проходимости.
- Вероятность видимого дерева плавно растёт от внешнего края к плотному лесному ядру; расчёт выполняется по исходной маске леса.
- Кусты в комбинированном 3D-preview получили отдельный контрастный бирюзово-зелёный маркер.
- Версия проекта поднята до `0.0.92`.


## v0.0.92 -> v0.0.93

- Финальная визуальная маска леса теперь согласуется с collision: скрытый `tree_blocker` открывается как обычная проходимая земля.
- Другие причины блокировки не меняются: вода, стены, структуры и ограничения traversal по высоте сохраняются.
- START/GOAL и итоговая связность пересчитываются после согласования растительности с проходимостью.
- Версия проекта поднята до `0.0.93`.

## v0.0.93 -> v0.0.94

- После открытия визуально очищенных лесных тайлов выполняется финальная проверка 3D-связности.
- Проходимыми остаются только очищенные тайлы крупнейшей итоговой компоненты; изолированные карманы снова получают явную причину блокировки.
- Низинные изолированные карманы восстанавливаются как видимый лес, а высокогорные — как безлесные скальные блокеры.
- START/GOAL, маршруты и validation по-прежнему строятся после окончательного согласования проходимости.
- Версия проекта поднята до `0.0.94`.


## v0.0.94 -> v0.0.95

- Добавлена финальная очистка 3D-проходимости после позднего выбора START/GOAL.
- Все проходимые, но недостижимые от START тайлы получают явную блокирующую семантику: вода для отрицательных уровней и скала для суши.
- В tactical/debug-данные добавлен отчёт `final_3d_traversal_cleanup`; итоговый preview больше не должен содержать красные недостижимые карманы.
- Версия проекта поднята до `0.0.95`.

## v0.0.95 -> v0.0.96

- Береговой камыш уровня `-1` и камыш старых луж разделены в визуальной маске, отчётах и комбинированном 3D-preview.
- В `generation_tuning` добавлены параметры `bush_density` для дополнительных terrain-кустов и `bush_thicket_count` для runtime-зарослей.
- Старый параметр `hydrology.reed_density` сохраняется как совместимый alias для `shore_reed_density`.
- Версия проекта поднята до `0.0.96`.


## v0.0.96 -> v0.0.97

- Часть тайлов, освобождённых после прореживания лесной кромки и высотного леса, теперь получает проходимые кусты вместо пустой земли.
- В `generation_tuning` добавлены отдельные плотности кустов для лесной кромки и высотного прореживания, а также максимальная высота их роста.
- Кусты не размещаются в низинах, на обрывах и выше заданной границы; в map package они отмечаются как отдельный визуальный тип `reclaimed_bush`.
- Версия проекта поднята до `0.0.97`.

## v0.0.97 -> v0.0.98

- Профиль `mountainous` переведён с набора разрозненных круглых гор на две детерминированные цепи связанных высокогорных регионов.
- Горные и пиковые macro-регионы получили направленную вытянутую форму; уменьшены мелкий шум и количество независимых highland-регионов.
- В geography-отчёт добавлен коэффициент вытянутости macro-региона для диагностики формы хребтов.
- После финальной 3D-очистки повторно синхронизируется признак `flooded` у runtime-объектов; влажная кромка `w` теперь также считается неподходящей для их footprint.
- Остальные elevation-профили и стадии hydrology/vegetation не изменялись.
- Версия проекта поднята до `0.0.98`.


## v0.0.98 -> v0.0.99

- Профиль `plateau` переведён на один доминирующий массив и связанную вторичную полку вместо независимых круглых возвышенностей.
- Плато получили увеличенную вытянутость, перекрывающиеся macro-регионы и более широкое плоское ядро с выраженной бровкой.
- В `configs/default.json` выбран профиль `plateau` для проверки следующей серии карт.
- Версия проекта поднята до `0.0.99`.


## v0.0.99 -> v0.0.100

- Доработан профиль `plateau`: крупноволновое искажение бровки убирает правильную овальность массива.
- Площадь уровней `17..20` уменьшена, чтобы вершина не превращалась в огромную белую шапку.
- На верхней площадке добавлены мягкие крупные полки и впадины без мелкого шумового рельефа.
- Маршрутизация дорог для `plateau` сильнее штрафует естественные обрывы и в основном ищет пологие входы.
- Версия проекта поднята до `0.0.100`.


## v0.0.100 -> v0.0.101

- В географические 3D-preview добавлен отдельный полупрозрачный объём воды для озёр на уровнях `-2..-5`.
- Поверхность воды выравнивается на уровне `-1`, а дно и стенки низины остаются видны сквозь прозрачный синий слой.
- Внутренние боковые грани соседних водных тайлов не рисуются, поэтому озеро выглядит единым объёмом, а не стопкой кубиков.
- Генерация карты, hydrology и gameplay-семантика воды не изменялись.
- Версия проекта поднята до `0.0.101`.


## v0.0.101 -> v0.0.102

- Исправлена визуализация воды в 3D-preview: водный объём теперь определяется напрямую по высотам `-5..-2`, без жёсткой зависимости от `water_lowland_grid`.
- Полупрозрачная вода рисуется во всех четырёх наборах 3D-изображений: geography, walkability, traversal и terrain_traversal.
- Поверхность воды сделана заметнее, при этом боковые стенки остаются более прозрачными и дно продолжает просвечивать.
- Версия проекта поднята до `0.0.102`.

## v0.0.102 -> v0.0.103

- Удалены попавшие в исходный архив служебные каталоги `__pycache__`, `.pytest_cache` и пустой `output/`; рабочая генерация и формат выходного пакета не изменялись.
- Добавлен `.gitignore` для Python-кэшей, виртуальных окружений, generated output, логов и локальных release-архивов/patch-файлов.
- Скрипт `./c` переписан на безопасную адресную очистку: он больше не удаляет по всему репозиторию любые файлы `html` и `js`, а очищает только generated output, кэши и известные временные файлы.
- Скрипт `./a` больше не упаковывает `output/`, вложенные `__pycache__`, `.pytest_cache` и ранее созданные ZIP/patch-артефакты.
- Проверены связи модулей и assets: `legacy/` и `old_road_dot.png` используются текущим pipeline и намеренно сохранены.
- Версия проекта поднята до `0.0.103`.


## v0.0.103 -> v0.0.104

- Флаг `--profile-performance` теперь собирает длительности всех стадий, уже размеченных через `timed_stage`, без изменения алгоритмов генерации.
- После генерации выводится таблица самых дорогих стадий с абсолютным временем и долей общего времени.
- В output записывается `performance_profile.json` с размером карты, временем на миллион тайлов, пиковым RSS процесса и полным списком замеров.
- Обычный запуск без `--profile-performance` не создаёт профиль и не несёт заметных накладных расходов.
- Версия проекта поднята до `0.0.104`.


## v0.0.104 -> v0.0.105

- Исправлена вложенность `timed_stage`: внутренние стадии больше не считаются независимыми верхнеуровневыми затратами.
- В performance profile добавлен отдельный список `top_level_stages` без дублирования родительских и дочерних таймеров.
- `build_geography_draft` разбит на построение макрорегионов, растеризацию полей, нормализацию elevation/moisture и смешивание влажности.
- Legacy engine теперь сообщает длительности 21 внутренней стадии обратно в общий `performance_profile.json`.
- Tactical processing разбит на загрузку raw data, оптимизацию, runtime layers, elevation, hydrology, vegetation, traversal cleanup и сериализацию.
- Алгоритмы генерации не изменены; патч предназначен только для точного поиска узких мест.
- Версия проекта поднята до `0.0.105`.


## v0.0.105 -> v0.0.106

- В `./r` восемь внутренних debug-overlay PNG больше не строятся по умолчанию; для полного набора используется `RENDER_DEBUG_LAYERS=1 ./r`. Основной base layer сохраняется.
- Горячая функция lattice noise получила ограниченный LRU-кэш, переиспользующий одинаковые узловые значения между соседними тайлами без изменения результата для того же seed.
- В растеризации geography заранее вычисляются нормализованные координаты строк и столбцов и постоянные масштабы карты, чтобы убрать повторные деления и `max()` из внутреннего цикла.
- Версия проекта поднята до `0.0.106`.


## v0.0.106 -> v0.0.107

- Ускорено размещение runtime-объектов без изменения результата для того же seed.
- Расстояние каждого кандидата до tactical anchors вычисляется один раз и переиспользуется для всех квот объектов.
- Проверка минимальной дистанции до уже занятых клеток переведена с линейного перебора occupied на инкрементально обновляемое множество недоступных координат.
- На контрольной карте 256x256 стадия `attach_runtime_layers` ускорилась примерно с 3.11 с до 1.27 с; SHA-256 списка из 149 runtime-объектов совпал.
- Версия проекта поднята до `0.0.107`.


## v0.0.107 -> v0.0.108

- Ускорен финальный repair walkable connectivity: убран повторный полный поиск компонент после каждого успешного ремонта.
- Сохранены прежние выбор компоненты, порядок ремонта и итоговая карта для одинакового seed.
- В метрики connectivity repair добавлен счётчик `component_scans`.
- Версия проекта поднята до `0.0.108`.


## v0.0.108 -> v0.0.109

- Бюджет географических макрорегионов теперь рассчитывается из площади карты с сохранением прежнего профильного минимума, а не фиксируется профилем `huge`.
- Характерный радиус макрорегионов на больших картах рассчитывается от средней дистанции между регионами и больше не растягивается как доля всей карты.
- Горные цепи и массивы плато на больших картах распределяются между несколькими самостоятельными группами вместо накопления вокруг двух растянутых опорных точек.
- Noise-поля elevation, moisture, ridges и warp получили тайлово-стабильный масштаб: большая карта содержит больше локальных форм, а не увеличенную копию поля 192x192.
- Для поиска трёх влияющих макрорегионов добавлен пространственный индекс с предвычисленными кандидатами по центру и углам bucket-ячеек; полная сортировка всех регионов на каждом тайле больше не требуется.
- В geography report добавлены метрики площади региона, плотности регионов, радиусов и масштаба noise-domain.
- Версия проекта поднята до `0.0.109`.


## v0.0.109 -> v0.0.110

- Добавлены детерминированные terrain-профили макрорегионов для карт крупнее 192 тайлов по меньшей стороне.
- Базовая поверхность больших карт теперь формируется связными лесными, равнинными, низинными, платообразными и высокогорными областями вместо сплошной лесной заливки.
- Границы terrain-профилей плавно смешиваются, а локальная форма лесов создаётся tile-stable coherent noise с постоянным масштабом в тайлах.
- Малые карты сохраняют прежнюю сплошную стартовую лесную заливку и прежнее поведение генератора.
- Guidance schema поднята до `terrain-guidance-v3`, report schema — до `terrain-guidance-report-v4`; добавлены признаки регионального terrain, количество профилей и начальная доля леса.
- Версия проекта поднята до `0.0.110`.


## v0.0.110 -> v0.0.111

- Добавлен финальный runtime-binary export layer, создающий `map_package/map_runtime.vxmap` из уже готовых in-memory grids без повторного чтения JSON.
- Контейнер `vxmap-runtime-v1` содержит фиксированный header, таблицу секций, terrain catalog, start/goal и региональные core grids размером 128x128 тайлов.
- Terrain, elevation и movement сохраняются как фиксированные числовые массивы; collision, projectile и vision — как bitset; cover и concealment — как u8.
- Добавлены детерминированный build ID, CRC32 каждой секции, атомарная запись, независимый reader и полная semantic validation по исходной runtime-модели.
- `map.json` публикует блок `runtime_binary`; обычный JSON package сохраняется без изменения существующих путей и остаётся fallback-контрактом.
- Обычные elevation transitions, source JSON digests, compression и optional gameplay sections намеренно не включены в первую бинарную версию.
- Версия проекта поднята до `0.0.111`.

## v0.0.111 -> v0.0.112

- Добавлен отдельный deterministic derived-layer `structure_height`, вычисляемый по финальному terrain после формирования runtime grids без изменения terrain, проходов или collision.
- `ruin_wall_blocker` получает связную относительную высоту `1..3` логических уровня над поверхностью земли; остальные тайлы получают `0`, а основание 3D-геометрии определяется как `elevation + 1`.
- Добавлен обязательный JSON-слой `map_package/layers/structure_height.json` со схемой `structure-height-layer-v1`, статистикой и проверкой инвариантов.
- Схема карты обновлена до `map-package-map-v12`, manifest schema — до `generation-manifest-v41`.
- VXMAP обновлён до format minor `1`; добавлена required regional section type `28` (`STRUCTURE_HEIGHT_U8`) и девятая core grid-секция каждого региона.
- Один и тот же in-memory grid передаётся JSON- и VXMAP-сериализаторам; independent binary validator выполняет tile-by-tile parity check.
- Добавлены тесты связности, детерминизма, существующих проходов, карты без руин, collision-инварианта, edge-регионов, CRC и чтения legacy VXMAP minor `0`.
- Версия проекта поднята до `0.0.112`.

## v0.0.112 -> v0.0.113

- Добавлены два deterministic derived-layer для массовой растительности: `vegetation_type` и `vegetation_height`, построенные по финальной reconciled-маске `vegetation_visual`.
- Типы `none/tree/bush/shore_reed/puddle_reed` кодируются значениями `0..4`; высоты хранятся как логические уровни над поверхностью `elevation + 1`.
- Деревья получают связные высоты `2..5` с учётом глубины леса и высоты местности, кусты — локально согласованные значения `1..2`, камыш — высоту `1`.
- Добавлены обязательные JSON-слои `layers/vegetation_type.json` и `layers/vegetation_height.json` со статистикой и проверками type/height consistency.
- Схема карты обновлена до `map-package-map-v13`, manifest schema — до `generation-manifest-v42`.
- VXMAP обновлён до format minor `2`; добавлены required regional sections type `31` (`VEGETATION_TYPE_U8`) и type `32` (`VEGETATION_HEIGHT_U8`), число core grid-секций региона увеличено до одиннадцати.
- Один и тот же in-memory результат передаётся JSON- и VXMAP-сериализаторам; binary validator выполняет tile-by-tile parity check для обоих vegetation grids.
- Добавлены тесты детерминизма, диапазонов, высоты опушки и середины леса, высокогорного ограничения, карты без растительности, reconciled-маски, edge-регионов, CRC и чтения legacy VXMAP minor `0`/`1`.
- Версия проекта поднята до `0.0.113`.

## v0.0.113 -> v0.0.114

- Старое независимое размещение прямоугольных руин заменено первым этапом semantic ruin-site planner: карта получает деревни, хутора, посты и отдельно стоящие здания с area-scaled бюджетом по размеру карты.
- Здания группируются внутри site, получают общий архитектурный профиль и ориентацию, а каждый site публикует один semantic road anchor для последующей интеграции основной дорожной сети.
- Каждый корпус сначала планируется точным footprint и размещается только на естественно ровной площадке: все клетки пола и стен имеют один `foundation_elevation >= 0`, окружающий пояс не содержит воды, природных барьеров или перепада больше одного уровня.
- Неподходящие кандидаты полностью отклоняются; здания разных sites не пересекаются, а отдельные корпуса одного site сохраняют зазор между footprint.
- План фундаментов передаётся в tactical data как `ruin-site-plan-v1`, а явные elevation cells блокируют последующие smoothing и traversal repair от повреждения ровного пола.
- Runtime-object placement резервирует footprint и внешний подход каждого здания, чтобы траншеи и другие объекты не перезаписывали фундамент.
- Добавлены hard validation для структуры ruin-site metadata и проверки итоговой плоскости каждого фундамента, расширены отчёт и диагностические счётчики отказов кандидатов.
- На контрольных картах с фиксированным seed доля руин составила 2.2% для 192x192, 2.0% для 320x320 и 2.1% для 400x400; ошибок foundation validation нет.
- Форматы map package, manifest и VXMAP остаются без изменения: `map-package-map-v13`, `generation-manifest-v42`, VXMAP `1.2`.
- Версия проекта поднята до `0.0.114`.

## v0.0.114 -> v0.0.115

- Добавлен elevation-aware settlement planner: тип исторического заселения выбирается по elevation style и фактической геометрии конкретной карты, включая долю пригодных площадок, rough/cliff terrain и связные плоские компоненты.
- Введены профили `open_plain`, `rural_plain`, `rolling_valleys`, `rugged_outposts`, `mountain_stronghold`, `plateau_settlement` и `sparse_frontier`; центральная деревня больше не является обязательной.
- Линейное area-scaled заполнение заменено отдельными верхними бюджетами sites, обычных зданий и landmark; рост плотности зависит от линейного размера карты, а не прямо от площади, и неиспользованный бюджет больше не заполняется принудительно.
- Ёмкость архетипов снижена: деревня содержит 6..9 зданий, хутор 2..3, пост 1..2, отдельно стоящий объект ровно один корпус.
- Ordinary sites группируются в одном или двух settlement regions, независимые sites соблюдают map-scaled exclusion radius, а landmark reservation дополнительно освобождает вокруг себя крупную незастроенную область.
- Для `mountainous` и `plateau` при наличии достаточно крупной высокой плоской компоненты резервируется будущий `mountain_fortress` или `plateau_fortress`; архитектура landmark пока не создаётся старым генератором стен.
- Metadata ruin-site planner обновлена до `ruin-site-plan-v2`: добавлены settlement profile, terrain context, бюджеты и их фактическое использование, settlement regions, landmark reservation и статистика расстояний; чтение legacy `ruin-site-plan-v1` сохранено.
- Terrain guidance report обновлён до `terrain-guidance-report-v5`, расширены консольный отчёт, validation и тесты всех ключевых elevation-aware сценариев.
- Форматы map package, manifest и VXMAP остаются без изменения: `map-package-map-v13`, `generation-manifest-v42`, VXMAP `1.2`.
- Версия проекта поднята до `0.0.115`.

## v0.0.115 -> v0.0.116

- Символ `#` закреплён исключительно за `ruin_wall_blocker`; vegetation reconciliation и финальная traversal cleanup больше не создают искусственные руинные стены или «rock blocker» через тот же символ.
- Изолированные highland-кандидаты после прореживания растительности теперь восстанавливаются как видимые деревья, а не превращаются в коричневые блоки высотой `1..3`.
- Глобальные critical/walkable connectivity stages переведены в диагностический режим: они считают компоненты и доступность, но не заполняют островки, не прорезают соединительные дороги и не меняют terrain ради START/GOAL.
- START и GOAL размещаются один раз на уже существующих проходимых тайлах без расчистки кругов и без защиты или расширения маршрута; поздняя relocation остаётся только выбором финальных маркеров.
- Elevation main-route alignment больше не использует START/GOAL как концы или fallback: маршрут строится только по semantic places, а при их отсутствии этап пропускается.
- Финальная 3D traversal cleanup обновлена до `final-3d-traversal-cleanup-v2`: disconnected areas сохраняются, а отчёт фиксирует число компонентов и нулевое количество искусственных blockers.
- Удалена декоративная запись блокирующей стены в hidden forest clearing, чтобы одиночные `#` не появлялись вне запланированных зданий.
- Добавлен отчёт `ruin-wall-provenance-v1` и hard validation `ruin_walls_belong_to_planned_buildings`; итоговая карта обязана иметь `outside_planned_buildings = 0` и `artificial_connectivity_blockers_created = 0`.
- Форматы map package, manifest и VXMAP остаются без изменения: `map-package-map-v13`, `generation-manifest-v42`, VXMAP `1.2`.
- Версия проекта поднята до `0.0.116`.

## v0.0.116 -> v0.0.117

- Старый случайный генератор обломков заменён архитектурным pipeline: сначала строится цельный план здания с внешним контуром, помещениями, внутренними перегородками и дверями, затем применяется связное разрушение крупными сегментами.
- Добавлены архетипы `small_house`, `long_house`, `barn`, `warehouse` и `outpost_building`; тип корпуса зависит от semantic ruin site и роли здания внутри деревни, хутора или поста.
- Для каждого site выбираются общие направление и тяжесть разрушения, а для каждого здания детерминированно оцениваются несколько сценариев: collapsed corner, damaged facade, side collapse, central breach и weathered decay.
- Одиночные стеновые тайлы запрещены; результат проверяется по сохранённым углам, длинным стеновым сегментам, доступности пола, доле разрушения, числу проломов и максимальному перепаду соседних высот.
- Высота стен `1..3` теперь вычисляется самим архитектурным damage-plan и публикуется в `ruin-site-plan-v3`; `structure_height` использует эти значения напрямую, сохраняя legacy fallback только для старых metadata.
- Схема слоя высот обновлена до `structure-height-layer-v2`; бинарный формат VXMAP и набор секций не изменены, поскольку физическое представление остаётся прежним `uint8`.
- Стены и пол запланированных зданий защищены от последующего перезаписывания дорогами, водой и декоративными этапами, а hard validation сверяет архитектурный план с финальным tactical grid.
- Расширены отчёт и тесты: добавлены показатели wall components, isolated tiles, accessibility, damage ratio, planned/fallback structure heights и детерминизм архитектуры.
- Форматы map package, generation manifest и VXMAP остаются `map-package-map-v13`, `generation-manifest-v42`, VXMAP `1.2`.
- Версия проекта поднята до `0.0.117`.


## v0.0.117 -> v0.0.118

- Разрушение стало индивидуальным для каждого здания: основным состоянием является `light`, `moderate` встречается реже, а `heavy` оставлен как редкое исключение; общий для site вектор повреждения сохранён.
- Целевые диапазоны разрушения снижены до 8..24% для `light`, 14..34% для `moderate` и 24..46% для `heavy`; scoring теперь выбирает более цельные фасады и крупные связные компоненты.
- Внутренние перегородки соединены с внешним контуром и больше не разрушаются отдельным случайным проходом, благодаря чему комнаты остаются заметными после повреждения.
- Добавлены `window_sill_hints`: низкие секции сохранившегося фасада, создающие визуальный намёк на оконные проёмы в рамках существующего слоя `structure_height`.
- Metadata обновлена до `ruin-site-plan-v4` и `ruin-building-architecture-v2`; для каждого site публикуется распределение severity, а для здания — оконные намёки и расширенные показатели качества.
- Для каждого footprint публикуются и валидируются `floor.expected_tiles`, `floor.actual_tiles` и `floor.missing_tiles`; финальная карта обязана содержать только `ruin_wall_blocker` и `ruin_floor` внутри корпуса, без затёртого пола.
- Исправлена итоговая статистика зданий: `planned_buildings` и `skipped_buildings` теперь вычисляются по фактически принятым sites после exclusion-проверок.
- Terrain guidance report обновлён до `terrain-guidance-report-v6`; добавлены средняя доля крупнейшего стенового компонента, сохранность внутренних стен, оконные намёки и покрытие пола.
- Форматы map package, generation manifest и VXMAP остаются `map-package-map-v13`, `generation-manifest-v42`, VXMAP `1.2`.
- Версия проекта поднята до `0.0.118`.

## v0.0.118 -> v0.0.119

- Добавлена публичная конфигурация `fortress` с первым архетипом `lake_island`, ограничением до одной крепости и отдельным выключателем островного варианта.
- Добавлен детерминированный read-only анализатор крупных связных водных областей для `flatland`: он рассчитывает размер будущей крепости и острова от меньшей стороны карты, необходимое водное кольцо, внутренний clearance и выбирает лучший участок.
- Новый `fortress_site_report.json` публикует требования, все значимые озёрные кандидаты, причины отказа и выбранный центр; результат также добавлен в tactical/debug data и краткий консольный отчёт.
- Для контрольной отладки `configs/default.json` переведён на `flatland` 440x400; chunk задан 8x8, поскольку legacy engine требует, чтобы размеры карты делились на размеры chunk без остатка.
- `super_flatland` пока явно не принимается анализатором: его текущий диапазон -1..1 не содержит непроходимой воды уровней -5..-2, поэтому имитация озера из проходимой низины -1 запрещена.
- Обновлены схемы generation manifest до `generation-manifest-v43`, tactical map/debug до `tactical-map-v0.34` / `tactical-debug-v0.22` и world summary до `world-summary-report-v2`; форматы map package и VXMAP остаются без изменений.
- Добавлены тесты конфигурации, выбора большого озера, отказа для малого водоёма, детерминизма, ограничения профиля и регистрации нового артефакта.
- Версия проекта поднята до `0.0.119`.


## v0.0.119 -> v0.0.120

- Выбранный `lake_island` site теперь материализуется в финальном elevation-слое как детерминированный неровный остров, а не остаётся только диагностической точкой.
- Для `flatland` остров получает берег уровня 0, основную площадь уровня +1 и небольшое внутреннее ядро уровня +2; размер сохраняет рассчитанное водное кольцо вокруг крепости.
- После формирования острова пересобираются geographic/runtime elevation grids, sparse elevation cells, slope grid и итоговая статистика высот до применения hydrology.
- В `fortress_site_report.json` добавлен раздел `island_materialization` с площадью острова, количеством изменённых тайлов, уровнями и зарезервированной точкой будущего входа.
- Добавлен диагностический `fortress_island_preview.png`, показывающий берег, внутреннюю площадь и возвышенное ядро острова на фоне воды.
- Версия проекта поднята до `0.0.120`.


## v0.0.120 -> v0.0.121

- Исправлена поставка модуля `top_down_worldgen.tactical.fortress_island`, который отсутствовал в предыдущем patch и приводил к `ModuleNotFoundError` при запуске.
- Восстановлена материализация детерминированного острова, обновление elevation grids и создание `fortress_island_preview.png`.
- Добавлена проверка импорта и выполнения материализации в составе существующих targeted tests.
- Версия проекта поднята до `0.0.121`.


## v0.0.121 -> v0.0.122

- Добавлен детерминированный план внешнего контура островной крепости.
- Добавлены круглые угловые и воротные башни, а также единственные главные ворота.
- Добавлен диагностический preview `fortress_plan_preview.png`; план пока не материализуется в terrain.
- Версия проекта поднята до `0.0.122`.


## v0.0.122 -> v0.0.123

- Внешний контур островной крепости материализуется в реальную тайловую карту: стены и круглые башни блокируют движение, главный воротный проход остаётся проходимым.
- Зафиксированы высоты над локальной землёй: стены 6 уровней, обычные башни 10 уровней, воротные башни 11 уровней.
- Явные высоты крепости передаются в слой `structure_height`; его контракт расширен до uint8 0..255 и схема поднята до `structure-height-layer-v3`.
- Метаданные `fortress_plan` теперь содержат фактические tile counts, height policy и список явных высот для сериализации JSON/VXMAP.
- Версия проекта поднята до `0.0.123`.


## v0.0.123 -> v0.0.124

- Заменён равномерный многоугольный контур крепости на композиционный генератор `architectural_nodes_mixed_walls_v2`.
- Стены теперь состоят из смеси длинных прямых и плавно изогнутых сегментов; композиция выбирается детерминированно между `compact_mixed` и `curved_courtyard`.
- Башни размещаются по архитектурной значимости углов, получают разные радиусы и больше не создаются равномерно на каждой вершине.
- Воротные башни интегрированы в общий план, а пересечения и слипание башен запрещены валидацией.
- В отчёт крепости добавлены типы сегментов, координаты и радиусы башен.
- Версия проекта поднята до `0.0.124`.


## v0.0.124 -> v0.0.125

- Линейный размер островной крепости увеличен на 25%: коэффициент от меньшей стороны карты поднят с `0.10` до `0.125`; остров масштабируется вместе с крепостью.
- Добавлен первый способ связи острова с материком: широкая неровная мелководная коса уровня `-1`.
- Внутри мелководной косы прокладывается проходимый путь шириной, равной фактической ширине ворот.
- Выход на материк выбирается по направлению ворот с учётом длины перехода и глубины воды.
- Диагностический preview плана крепости теперь показывает мелководную косу и основной путь.
- Версия проекта поднята до `0.0.125`.

## v0.0.125 -> v0.0.126

- Добавлен детерминированный план внутреннего двора островной крепости без материализации в terrain.
- В центральной трети двора размещается крупная круглая башня диаметром 11..15 тайлов и плановой высотой 16 уровней над локальной землёй.
- Вдоль внутренних стен размещаются 2..3 небольших дома с дверями, обращёнными во двор; размеры и положение выбираются детерминированно с проверкой зазоров.
- От главных ворот к центральной башне прокладывается основной путь, к домам добавляются отдельные ответвления.
- В свободных участках двора размещаются 4..10 деревьев без перекрытия зданий, дверей и обязательных путей.
- `fortress_plan_preview.png` расширен отображением центральной башни, домов, путей и деревьев; в `fortress_site_report.json` добавлен раздел `fortress_interior_plan`.
- Версия проекта поднята до `0.0.126`.

## v0.0.126 -> v0.0.127

- Внутренняя планировка крепости больше не прерывает генерацию карты, если в компактном дворе не помещаются минимум два дома.
- Размещение домов стало best-effort: крепость сохраняется с фактически размещённым количеством домов, включая один или ноль.
- В `fortress_interior_plan` добавлены статус `degraded` и причина `insufficient_courtyard_space`, когда запрошенное количество домов разместить невозможно.
- Добавлен регрессионный тест компактной крепости для проблемного seed `9069957925987520693`.
- Версия проекта поднята до `0.0.127`.


## v0.0.127 -> v0.0.128

- Весь внутренний двор островной крепости материализуется существующим проходимым тайлом `ruin_floor` (`R`).
- Случайные terrain-тайлы внутри маски двора заменяются каменным полом; стены, башни и ворота сохраняют приоритет.
- В отчёт материализации добавлены `courtyard_floor_tiles`, `courtyard_replaced_tiles` и `courtyard_foreign_tiles_remaining`.
- Диагностический preview крепости переведён на фиолетовую архитектурную палитру: отдельные оттенки для стен, башен, ворот и пола двора.
- Добавлен тест полной очистки и материализации двора.
- Версия проекта поднята до `0.0.128`.

## v0.0.128 -> v0.0.129

- Размещение центральной башни крепости стало адаптивным: радиус последовательно уменьшается до 3 тайлов, а поиск расширяется от предпочтительной зоны до всего двора.
- Защитный отступ вокруг центральной башни при необходимости уменьшается с 2 до 0 тайлов.
- Невозможность разместить центральную башню больше не прерывает генерацию карты: внутренний план сохраняется со статусом `degraded`, а башня помечается как `skipped`.
- В отчёт добавлены запрошенный и фактический радиусы башни, область поиска, фактический отступ и список причин деградации.
- Добавлены тесты уменьшения центральной башни и безопасного пропуска башни в слишком тесном дворе.
- Версия проекта поднята до `0.0.129`.


## v0.0.129 -> v0.0.130

- Добавлены слои `structure_type` и `structure_micro_geometry` для архитектуры.
- Подтайловое деление зафиксировано как `4x4`; один базовый тайл хранит 16-битную маску занятости.
- Существующие руины и крепость классифицируются отдельными типами; текущая геометрия экспортируется полной маской `0xFFFF`.
- JSON map package расширен файлами `layers/structure_type.json` и `layers/structure_micro_geometry.json`.
- VXMAP обновлён до minor 3 и содержит региональные секции типов строений и micro-mask.
- Версия проекта поднята до `0.0.130`.


## v0.0.130 -> v0.0.131

- Круглые башни крепости получили реальные частичные micro-mask в сетке `4x4`.
- Маски башенных стен рассчитываются по кольцевой геометрии башни; обычные стены, полы и руины пока сохраняют `0xFFFF`.
- Контракт micro-geometry теперь явно задаёт порядок битов `row_major_top_left_lsb` и правило занятости.
- В статистику добавлены количества полных и частичных micro-ячеек.
- Схемы manifest, map-package-map и structure-micro-geometry обновлены.
- Версия проекта поднята до `0.0.131`.


## v0.0.131 -> v0.0.132

- Стены крепости получили реальные micro-mask в сетке `4x4`; круглые башни сохраняют кольцевые маски.
- Micro-mask теперь описывает только вертикально твёрдую геометрию: полы двора, ворот, зданий и руин имеют маску `0`.
- План внутреннего двора материализуется в terrain и structure metadata: центральная башня, дома, дорожки и контролируемые деревья теперь доступны потребителям карты.
- Дорога от материка к воротам поднята на уровень `0`; окружающее мелководье остаётся на уровне `-1`.
- Обновлены схемы map-package, manifest и structure micro geometry.
- Версия проекта поднята до `0.0.132`.


## v0.0.132 -> v0.0.133

- Стены обычных руин, центральной крепостной башни и внутренних построек переведены с полного `0xFFFF` на связанную микрогеометрию `4x4`.
- Толщина линейных стен теперь составляет два подтайла, а соединения соседних клеток формируют аккуратные прямые участки, углы и окончания.
- Геометрическая толщина внешних стен крепости уменьшена до подтайлового масштаба; круглые башни продолжают использовать кольцевую растеризацию.
- Схемы manifest, map-package-map и structure-micro-geometry обновлены.
- Версия проекта поднята до `0.0.133`.


## v0.0.133 -> v0.0.134

- Обычные руины теперь растеризуются на общей микросетке каждого здания по семантическим `wall_runs`, а не независимо внутри каждого базового тайла.
- Прямые участки и углы стен получают непрерывную толщину в два подтайла; повреждённые окончания получают детерминированный скол.
- Старый connected-mask остаётся fallback для legacy-руин без архитектурных метаданных.
- Схемы manifest, map-package-map и structure-micro-geometry обновлены.
- Версия проекта поднята до `0.0.134`.
