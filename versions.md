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

