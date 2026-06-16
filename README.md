# TopDownMapGen

TopDownMapGen is a procedural top-down **world package generator**.

<img width="1491" height="1055" alt="ideal" src="https://github.com/user-attachments/assets/48c272b5-740f-4d4a-b93a-c287290d1150" />


The core goal of the project is to generate a machine-readable map package that can be consumed by a game, simulator, editor, AI tool, or renderer. Visual rendering is supported, but it is an optional layer on top of the generated world data.

## What this project produces

The generator writes a stable output directory, usually `output/`, with files such as:

- `generated_map.txt` — human-readable ASCII overview.
- `map_package/terrain.json` — semantic terrain grid.
- `map_package/runtime_grids.json` — movement, collision, vision, projectile, cover, concealment and height grids.
- `map_package/markers.json` — start, goal and important marker points.
- `map_package/objects/runtime_objects.json` — generated gameplay/runtime objects.
- `map_package/objects/places.json` — named generated places.
- `map_package/world_graph.json` — high-level graph of meaningful locations.
- `map_package/routes.json` — paths and route metadata.
- `map_package/gameplay_zones.json` — gameplay-oriented zones.
- `map_package/elevation_model.json` — elevation levels, transitions and related data.
- `_manifest.json` — generation metadata, schema versions and validation summary.
- `validation_report.json` — validation diagnostics.
- `world_density_report.json` — terrain/collision/movement density report.

See [`docs/OUTPUT_FORMAT.md`](docs/OUTPUT_FORMAT.md) for the current output contract.

## Core vs optional layers

The project is intentionally split into two responsibilities:

1. **World generation**: authoritative data. This is the project core.
2. **Visual generation/rendering**: optional preview, debug and asset-backed rendering.

Do not treat visual output as the source of truth. Visual output must be derived from the world package, not the other way around.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Generate the core world package:

```bash
./r
```

Equivalent explicit command:

```bash
./r world
```

Inspect generated output:

```bash
./r inspect
./r summary
```

Run checks:

```bash
./r test
```

## Optional visual commands

Visual commands are intentionally separate from the default run:

```bash
./r preview       # render debug world preview from existing output
./r visual        # build visual map from existing world package
./r visual-debug  # render visual pipeline step images
./r visual-all    # world + visual + visual debug + asset preview + summary
```

The default `./r` command should stay focused on the generated world package. If visual rendering fails, the world generation contract should still remain testable and usable.

## Useful environment overrides

```bash
CONFIG_PATH=configs/default.json ./r world
OUTPUT_DIR=output_test ./r world
RUN_WORLD_PREVIEW=1 ./r world
WORLD_RENDER=1 ./r world
QUIET=0 ./r test
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — project structure and pipeline boundaries.
- [`docs/OUTPUT_FORMAT.md`](docs/OUTPUT_FORMAT.md) — generated world package format.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — what is done, deferred and out of scope.
- [`docs/game_consumer_guide.md`](docs/game_consumer_guide.md) — how a game can consume generated data.
- [`docs/world_building_algorithm.md`](docs/world_building_algorithm.md) — world generation notes.

## Development rules

- One patch must solve one connected task.
- Every patch must increase the patch version by exactly one.
- Every patch must update `versions.md`.
- The world package is the stable contract; preview and render files are derived artifacts.
- Unknown local helper files should not be removed without review.

## Current status

The generator already has semantic terrain, runtime grids, places, routes, world graph, gameplay zones, runtime objects, validation, density reporting and elevation data. Visual rendering exists as a separate optional layer and should not drive core architecture decisions.
