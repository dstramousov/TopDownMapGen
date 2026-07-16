#!/usr/bin/env bash
set -euo pipefail

SUMMARY_FILE="output/_console_summary.txt"
TOTAL_STARTED=$SECONDS

run_stage() {
  local title="$1"
  shift
  local log_file
  local started=$SECONDS
  log_file="$(mktemp)"
  printf '==> %s... ' "$title"
  if "$@" >"$log_file" 2>&1; then
    printf 'готово (%d с)\n' "$((SECONDS - started))"
    rm -f "$log_file"
    return 0
  fi
  printf 'ОШИБКА\n' >&2
  cat "$log_file" >&2
  rm -f "$log_file"
  return 1
}

print_summary() {
  if [[ -f "$SUMMARY_FILE" ]]; then
    printf '\n'
    cat "$SUMMARY_FILE"
  else
    echo "Не найден итоговый отчёт: $SUMMARY_FILE" >&2
    return 1
  fi
}

printf '==> очистка output... '
rm -rf output
./c >/dev/null
printf 'готово\n'

run_stage "генерация мира" \
  env PYTHONPATH=. python3 top_down_generator.py \
    --config configs/default.json \
    -o output \
    --include-debug-layers \
    --summary-file "$SUMMARY_FILE"

run_stage "основная карта" \
  python3 examples/render_world_preview.py output \
    --collision-overlay \
    --elevation-overlay \
    --elevation-legend \
    --transition-overlay \
    --places-overlay \
    --gameplay-zones-overlay \
    --routes-overlay \
    --world-graph-overlay \
    --grid \
    --cell-size 16 \
    --output output/full_world_preview.png

run_stage "карта высот" \
  python3 examples/render_world_preview.py output \
    --elevation-only --elevation-legend --grid --cell-size 16 \
    --output output/elevation_preview.png

run_stage "источники высот" \
  python3 examples/render_world_preview.py output \
    --source-only --grid --cell-size 16 \
    --output output/elevation_source_preview.png

run_stage "география" \
  python3 examples/render_world_preview.py output \
    --geography-only --grid --cell-size 16 \
    --output output/geography_preview.png

run_stage "влажность" \
  python3 examples/render_world_preview.py output \
    --moisture-only --grid --cell-size 16 \
    --output output/moisture_preview.png

run_stage "вода и низины" \
  python3 examples/render_world_preview.py output \
    --water-lowlands-only --grid --cell-size 16 \
    --output output/water_lowland_preview.png

run_stage "уклоны" \
  python3 examples/render_world_preview.py output \
    --slope-only --grid --cell-size 16 \
    --output output/slope_preview.png

run_stage "изменения traversal repair" \
  python3 examples/render_traversal_repair_preview.py output \
    --cell-size 4 \
    --output output/traversal_repair_preview.png

run_stage "3D-география" \
  python3 examples/render_geography_3d_preview.py output \
    --overlay geography --width 2560 --height 1440 --views nw ne se sw

run_stage "3D-проходимость" \
  python3 examples/render_geography_3d_preview.py output \
    --overlay walkability --width 2560 --height 1440 --views nw ne se sw

run_stage "3D-связность" \
  python3 examples/render_geography_3d_preview.py output \
    --overlay traversal --width 2560 --height 1440 --views nw ne se sw

run_stage "3D-местность и проходимость" \
  python3 examples/render_geography_3d_preview.py output \
    --overlay terrain_traversal --width 2560 --height 1440 --views nw ne se sw

print_summary
printf '  общее время: %d с\n' "$((SECONDS - TOTAL_STARTED))"
printf '  preview: 24 файла в output/ и output/geography_3d_preview/\n'

open output/
