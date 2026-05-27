#!/usr/bin/env bash

set -euo pipefail

CMD="${1:-all}"
OUTPUT_DIR="${OUTPUT_DIR:-output}"
CONFIG_PATH="${CONFIG_PATH:-configs/default.json}"
VISUAL_PROFILE="${VISUAL_PROFILE:-top_down_visualgen/profiles/dark_forest}"
VISUAL_OUTPUT="${VISUAL_OUTPUT:-${OUTPUT_DIR}/visual_map}"
VISUAL_STEPS_OUTPUT="${VISUAL_STEPS_OUTPUT:-${VISUAL_OUTPUT}/debug/steps}"
VISUAL_DEBUG_TILE_SIZE="${VISUAL_DEBUG_TILE_SIZE:-4}"

run_world() {
  ./c
  PYTHONPATH=. python3 top_down_generator.py \
    --config "${CONFIG_PATH}" \
    -o "${OUTPUT_DIR}" \
    --include-debug-layers
}

run_preview() {
  python3 examples/render_world_preview.py "${OUTPUT_DIR}" \
    --collision-overlay \
    --elevation-overlay \
    --transition-overlay \
    --places-overlay \
    --gameplay-zones-overlay \
    --routes-overlay \
    --world-graph-overlay \
    --grid \
    --cell-size 16 \
    --output "${OUTPUT_DIR}/full_world_preview.png"
}

run_visual() {
  PYTHONPATH=. python3 -m top_down_visualgen.cli \
    --input "${OUTPUT_DIR}" \
    --profile "${VISUAL_PROFILE}" \
    --output "${VISUAL_OUTPUT}"
}

run_visual_debug() {
  PYTHONPATH=. python3 bin/render_visual_pipeline_steps.py "${OUTPUT_DIR}" \
    --profile "${VISUAL_PROFILE}" \
    --output "${VISUAL_STEPS_OUTPUT}" \
    --tile-size "${VISUAL_DEBUG_TILE_SIZE}"
}

run_inspect() {
  python3 examples/inspect_world_package.py "${OUTPUT_DIR}"
}

run_tests() {
  python3 -m compileall top_down_worldgen top_down_visualgen examples bin
  PYTHONPATH=. pytest -q
}

usage() {
  cat <<'EOF'
Usage: ./r [command]

Commands:
  all      Clean, generate world, render previews and build visual map (default)
  world    Clean and generate world package only
  preview  Render debug world preview from existing output
  visual   Build visual_tileset output from existing output/map_package
  visual-debug
           Render visual pipeline step PNGs from existing output/map_package
  inspect  Inspect existing world package
  test     Run compileall and pytest
  help     Show this help

Environment overrides:
  CONFIG_PATH=...
  OUTPUT_DIR=...
  VISUAL_PROFILE=...
  VISUAL_OUTPUT=...
  VISUAL_STEPS_OUTPUT=...
  VISUAL_DEBUG_TILE_SIZE=...
EOF
}

case "${CMD}" in
  all)
    run_world
    run_preview
    run_visual
    run_visual_debug
    ;;
  world)
    run_world
    ;;
  preview)
    run_preview
    ;;
  visual)
    run_visual
    ;;
  visual-debug)
    run_visual_debug
    ;;
  inspect)
    run_inspect
    ;;
  test)
    run_tests
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: ${CMD}" >&2
    usage >&2
    exit 2
    ;;
esac
