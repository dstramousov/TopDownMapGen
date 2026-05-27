./c
PYTHONPATH=. python3 top_down_generator.py \
  --config configs/default.json \
  -o output \
  --include-debug-layers

python3 examples/render_world_preview.py output \
  --collision-overlay \
  --elevation-overlay \
  --transition-overlay \
  --places-overlay \
  --gameplay-zones-overlay \
  --routes-overlay \
  --world-graph-overlay \
  --grid \
  --cell-size 16 \
  --output output/full_world_preview.png

#python3 examples/inspect_world_package.py output
#python3 examples/render_world_preview.py output --collision-overlay
#cat output/validation_report.json
#cat output/map_package/elevation_model.json