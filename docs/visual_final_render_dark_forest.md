# Visual Final Render — Dark Forest

`final_render.png` is the asset-backed final PNG produced at the end of the visual pipeline.

The renderer reads:

```text
output/visual_map/visual_layers.json
output/visual_map/visual_objects.json
top_down_visualgen/profiles/dark_forest/assets_manifest.json
assets/dark_forest/**/*.png
```

It writes:

```text
output/visual_map/final_render.png
output/visual_map/debug/final_render_report.json
```

Important rules:

```text
- final render does not change gameplay
- final render does not change collision
- final render does not move routes, start, or goal
- missing assets use manifest fallbacks when possible
```

For a `192 x 176` map with `16 px` tiles, the normal final PNG size is:

```text
3072 x 2816 px
```

Commands:

```bash
./r
./r final-render
```

`./r` runs the full pipeline and includes `final_render.png` in the final summary.

`./r final-render` rerenders only the final PNG from existing visual JSON files.
