./c
PYTHONPATH=. python3 top_down_generator.py \
  --config configs/default.json \
  -o output \
  --include-debug-layers

python3 examples/inspect_world_package.py output
python3 examples/render_world_preview.py output --collision-overlay