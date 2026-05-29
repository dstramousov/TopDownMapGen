#!/usr/bin/env bash

set -euo pipefail

CMD="${1:-all}"
OUTPUT_DIR="${OUTPUT_DIR:-output}"
CONFIG_PATH="${CONFIG_PATH:-configs/default.json}"
VISUAL_PROFILE="${VISUAL_PROFILE:-top_down_visualgen/profiles/dark_forest}"
VISUAL_OUTPUT="${VISUAL_OUTPUT:-${OUTPUT_DIR}/visual_map}"
VISUAL_STEPS_OUTPUT="${VISUAL_STEPS_OUTPUT:-${VISUAL_OUTPUT}/debug/steps}"
VISUAL_DEBUG_TILE_SIZE="${VISUAL_DEBUG_TILE_SIZE:-4}"
VISUAL_PREVIEW_TILE_SIZE="${VISUAL_PREVIEW_TILE_SIZE:-4}"
WORLD_PREVIEW_CELL_SIZE="${WORLD_PREVIEW_CELL_SIZE:-4}"
RUN_WORLD_PREVIEW="${RUN_WORLD_PREVIEW:-0}"
WORLD_RENDER="${WORLD_RENDER:-0}"
WORLD_DEBUG_LAYERS="${WORLD_DEBUG_LAYERS:-0}"
LOG_DIR="${LOG_DIR:-${OUTPUT_DIR}/logs}"
QUIET="${QUIET:-1}"

ensure_log_dir() {
  mkdir -p "${LOG_DIR}"
}

run_logged() {
  local name="$1"
  shift
  ensure_log_dir
  local log_file="${LOG_DIR}/${name}.log"
  if "${@}" >"${log_file}" 2>&1; then
    return 0
  fi
  echo "FAILED: ${name}" >&2
  echo "log: ${log_file}" >&2
  tail -40 "${log_file}" >&2 || true
  return 1
}

run_maybe_logged() {
  local name="$1"
  shift
  if [[ "${QUIET}" == "1" ]]; then
    run_logged "${name}" "${@}"
  else
    "${@}"
  fi
}

run_cleanup() {
  run_maybe_logged cleanup ./c
  ensure_log_dir
  rm -f -- "${OUTPUT_DIR}/generation.log"
  rm -f -- "${OUTPUT_DIR}/world_density_report.json"
  rm -f -- "${LOG_DIR}/world_generation.log"
  rm -f -- "${LOG_DIR}/world_preview.log"
  rm -f -- "${LOG_DIR}/visual_pipeline.log"
  rm -f -- "${LOG_DIR}/visual_debug.log"
  rm -f -- "${LOG_DIR}/pipeline_summary.log"
  rm -f -- "${LOG_DIR}/asset_registry_preview.log"
  rm -f -- "${LOG_DIR}/asset_pack.log"
  rm -f -- "${LOG_DIR}/final_render.log"
  rm -f -- "${LOG_DIR}/asset_plan.log"
}

run_world() {
  run_cleanup
  local world_args=(
    env PYTHONPATH=. python3 top_down_generator.py
    --config "${CONFIG_PATH}"
    -o "${OUTPUT_DIR}"
  )
  if [[ "${WORLD_RENDER}" == "1" ]]; then
    if [[ "${WORLD_DEBUG_LAYERS}" == "1" ]]; then
      world_args+=(--include-debug-layers)
    fi
  else
    world_args+=(--no-render)
  fi
  run_maybe_logged world_generation "${world_args[@]}"
}

run_preview() {
  run_maybe_logged world_preview python3 examples/render_world_preview.py "${OUTPUT_DIR}" \
    --collision-overlay \
    --elevation-overlay \
    --transition-overlay \
    --places-overlay \
    --gameplay-zones-overlay \
    --routes-overlay \
    --world-graph-overlay \
    --grid \
    --cell-size "${WORLD_PREVIEW_CELL_SIZE}" \
    --output "${OUTPUT_DIR}/full_world_preview.png"
}

run_visual() {
  run_maybe_logged visual_pipeline env PYTHONPATH=. python3 -m top_down_visualgen.cli \
    --input "${OUTPUT_DIR}" \
    --profile "${VISUAL_PROFILE}" \
    --output "${VISUAL_OUTPUT}" \
    --preview-tile-size "${VISUAL_PREVIEW_TILE_SIZE}"
}

run_visual_debug() {
  run_maybe_logged visual_debug env PYTHONPATH=. python3 bin/render_visual_pipeline_steps.py "${OUTPUT_DIR}" \
    --profile "${VISUAL_PROFILE}" \
    --output "${VISUAL_STEPS_OUTPUT}" \
    --tile-size "${VISUAL_DEBUG_TILE_SIZE}"
}

run_final_render() {
  run_maybe_logged final_render env PYTHONPATH=. python3 bin/render_final_asset_map.py "${VISUAL_OUTPUT}" \
    --profile "${VISUAL_PROFILE}" \
    --output "${VISUAL_OUTPUT}/final_render.png"
}

run_asset_preview() {
  run_maybe_logged asset_registry_preview env PYTHONPATH=. python3 bin/generate_asset_registry_preview.py "${VISUAL_PROFILE}" \
    --output "${VISUAL_OUTPUT}/debug"
}

run_asset_pack() {
  run_maybe_logged asset_pack env PYTHONPATH=. python3 bin/generate_asset_pack.py "${VISUAL_PROFILE}"
}

run_asset_plan() {
  run_maybe_logged asset_plan env PYTHONPATH=. python3 bin/print_asset_plan.py "${VISUAL_PROFILE}" \
    --output "${VISUAL_OUTPUT}/debug"
}

run_summary() {
  env PYTHONPATH=. python3 bin/print_pipeline_summary.py "${OUTPUT_DIR}" \
    --project-root . \
    --profile "${VISUAL_PROFILE}"
}

run_assets() {
  run_maybe_logged assets_manifest env PYTHONPATH=. python3 bin/validate_assets_manifest.py "${VISUAL_PROFILE}"
}

run_assets_full() {
  run_asset_pack
  run_maybe_logged assets_manifest_full env PYTHONPATH=. python3 bin/validate_assets_manifest.py "${VISUAL_PROFILE}" --check-files
}

run_inspect() {
  python3 examples/inspect_world_package.py "${OUTPUT_DIR}"
}

run_tests() {
  python3 -m compileall top_down_worldgen top_down_visualgen examples bin
  env PYTHONPATH=. python3 bin/validate_assets_manifest.py "${VISUAL_PROFILE}"
  env PYTHONPATH=. python3 bin/print_asset_plan.py "${VISUAL_PROFILE}" --output /tmp/topdown_asset_plan_check --json-only
  PYTHONPATH=. pytest -q
}

usage() {
  cat <<'EOF'
Usage: ./r [command]

Commands:
  all      Clean, generate world, build visual map/debug and print summary (default)
  world    Clean and generate world package only
  preview  Render debug world preview from existing output
  visual   Build visual_tileset output from existing output/map_package
  visual-debug
           Render visual pipeline step PNGs from existing output/map_package
  summary  Print final world/visual pipeline summary from existing output
  assets   Validate visual profile assets manifest
  assets-full
           Generate placeholder asset pack and validate referenced PNG files
  asset-pack
           Generate placeholder PNG files under the configured asset root
  asset-plan
           Print the asset production batch plan and write its JSON report
  asset-preview
           Generate asset registry JSON/HTML preview from the visual profile
  final-render
           Render output/visual_map/final_render.png from asset PNG files
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
  VISUAL_PREVIEW_TILE_SIZE=...
  WORLD_PREVIEW_CELL_SIZE=...
  RUN_WORLD_PREVIEW=1   Also render output/full_world_preview.png during ./r all
  WORLD_RENDER=1        Render world PNG layers during generation
  WORLD_DEBUG_LAYERS=1  Include world debug PNG layers when WORLD_RENDER=1
  LOG_DIR=...
  QUIET=0   Show raw command output instead of writing stage logs to output/logs/
EOF
}

case "${CMD}" in
  all)
    run_world
    if [[ "${RUN_WORLD_PREVIEW}" == "1" ]]; then
      run_preview
    fi
    run_visual
    run_visual_debug
    run_asset_pack
    run_asset_preview
    run_summary
    ;;
  world)
    run_world
    ;;
  preview)
    run_preview
    ;;
  visual)
    run_visual
    run_summary
    ;;
  visual-debug)
    run_visual_debug
    ;;
  summary)
    run_summary
    ;;
  assets)
    run_assets
    ;;
  assets-full)
    run_assets_full
    ;;
  asset-pack)
    run_asset_pack
    ;;
  asset-plan)
    run_asset_plan
    ;;
  asset-preview)
    run_asset_preview
    ;;
  final-render)
    run_final_render
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
