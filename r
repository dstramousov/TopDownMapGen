#!/usr/bin/env bash
set -euo pipefail

SUMMARY_FILE="output/_console_summary.txt"

print_summary() {
  if [[ -f "$SUMMARY_FILE" ]]; then
    cat "$SUMMARY_FILE"
  else
    echo "summary file not found: $SUMMARY_FILE" >&2
    return 1
  fi
}

echo "==> cleanup output"
rm -rf output
./c >/dev/null

echo "==> world generation"
PYTHONPATH=. python3 top_down_generator.py \
  --config configs/default.json \
  -o output \
  --include-debug-layers \
  --summary-file "$SUMMARY_FILE"

echo "==> world preview"
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
  --output output/full_world_preview.png 2>&1

echo "==> elevation preview"
python3 examples/render_world_preview.py output \
  --elevation-only \
  --elevation-legend \
  --grid \
  --cell-size 16 \
  --output output/elevation_preview.png 2>&1

echo "==> elevation source preview"
python3 examples/render_world_preview.py output \
  --source-only \
  --grid \
  --cell-size 16 \
  --output output/elevation_source_preview.png 2>&1

echo "==> geography preview"
python3 examples/render_world_preview.py output \
  --geography-only \
  --grid \
  --cell-size 16 \
  --output output/geography_preview.png 2>&1

echo "==> moisture preview"
python3 examples/render_world_preview.py output \
  --moisture-only \
  --grid \
  --cell-size 16 \
  --output output/moisture_preview.png 2>&1

echo "==> water / lowland preview"
python3 examples/render_world_preview.py output \
  --water-lowlands-only \
  --grid \
  --cell-size 16 \
  --output output/water_lowland_preview.png 2>&1

echo "==> slope preview"
python3 examples/render_world_preview.py output \
  --slope-only \
  --grid \
  --cell-size 16 \
  --output output/slope_preview.png 2>&1

echo "==> 3d geography preview"
python3 examples/render_geography_3d_preview.py output \
  --overlay geography \
  --width 2560 \
  --height 1440 \
  --views nw ne se sw 2>&1

echo "==> 3d walkability preview"
python3 examples/render_geography_3d_preview.py output \
  --overlay walkability \
  --width 2560 \
  --height 1440 \
  --views nw ne se sw 2>&1

echo "==> 3d traversal preview"
python3 examples/render_geography_3d_preview.py output \
  --overlay traversal \
  --width 2560 \
  --height 1440 \
  --views nw ne se sw 2>&1

print_summary

#python3 examples/inspect_world_package.py output
#python3 examples/render_world_preview.py output --collision-overlay
#cat output/validation_report.json
#cat output/map_package/elevation_model.json
