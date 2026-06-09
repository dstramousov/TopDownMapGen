# Output format

Один запуск генератора создаёт один output root. По умолчанию это папка:

```text
output/
```

## Top-level files

| Файл | Назначение |
|---|---|
| `_manifest.json` | Паспорт запуска и список артефактов. Главная точка входа. |
| `generated_map.txt` | ASCII-карта для человека и legacy tools. |
| `tactical_map.json` | Legacy runtime/tactical export. |
| `tactical_map_debug.json` | Debug tactical export. |
| `_raw_tactical_map.json` | Raw output legacy engine. Внутренний debug artifact. |
| `validation_report.json` | Отчёт валидации world package. |
| `world_density_report.json` | Terrain/collision/movement/elevation density report. |
| `metrics.txt` | Текстовые метрики запуска. |
| `object_catalog.md` | Человекочитаемый каталог runtime objects/place types. |
| `generation.log` | Лог генерации legacy/world layer. |
| `logs/` | Stage logs runner-а. |
| `map_package/` | Главный структурированный пакет мира. |
| `visual_map/` | Производный visual output. |

## `map_package/`

```text
map_package/
  map.json
  runtime_grids.json
  markers.json
  routes.json
  world_graph.json
  gameplay_zones.json
  elevation_model.json
  elevation_features.json
  elevation_transitions.json
  layers/
    terrain.json
    tile_grid.json
    collision.json
    movement_costs.json
    elevation.json
    start_goal.json
  objects/
    runtime_objects.json
    places.json
  gameplay/
    combat_zones.json
    cover_points.json
    choke_points.json
    flank_routes.json
    enemy_spawn_zones.json
    fallback_positions.json
  catalogs/
    tile_types.json
    object_types.json
  render/
    render_profile.json
    tile_render_hints.json
    object_render_hints.json
```

`map_package/map.json` содержит размеры, seed, координатную модель и относительные пути к остальным частям пакета.

## Runtime grids

`map_package/runtime_grids.json` содержит grids, нужные игре и tools:

```text
movement_grid
collision_grid
projectile_block_grid
vision_block_grid
cover_grid
concealment_grid
height_grid
```

`height_grid` — numeric integer rows. Compact string rows для elevation запрещены,
потому что диапазон высот поддерживает отрицательные и многозначные значения.
Текущий контракт elevation для ShootAndRun-compatible consumers: `-8..20`.

`elevation_transitions.json` использует тот же диапазон для `from.level` и
`to.level`. Правила движения:

```text
same level: обычное движение по collision/movement grids
down by 1: разрешено, damage = 0
down by 2+: разрешено как падение, damage = max(0, drop_height - 1) * 5
up by 1: нужен Space step-up или explicit transition
up by 2+: запрещено без explicit transition
```

Open pit/trench/cutaway ниже `0` считается открытой проходимой формой рельефа,
если `collision_grid` и `movement_grid` разрешают вход. Underground/bunker зоны должны
быть представлены отдельно через hatch/door/stairs semantics и не считаются open pit.

## Visual output

```text
visual_map/
  visual_map.json
  visual_layers.json
  visual_objects.json
  visual_chunks.json
  preview.png
  final_render.png
  debug/
    visual_density_report.json
    autotile_report.json
    autotile_masks.json
    unmapped_terrain_report.json
    decoration_report.json
    place_treatment_report.json
    elevation_visual_report.json
    boundary_visual_report.json
    final_render_report.json
    asset_registry_report.json
    asset_registry_preview.html
    steps/
      00_world_terrain.png
      01_base_visual_tiles.png
      02_road_autotile.png
      03_water_autotile.png
      04_swamp_autotile.png
      05_forest_autotile.png
      06_autotile_fallbacks.png
      07_objects.png
      08_decoration.png
      09_place_treatment.png
      10_elevation_visual.png
      11_boundary_visual.png
      12_final_preview.png
```

Visual output нужен для просмотра и render pipeline. Gameplay consumer должен читать `map_package/`.
