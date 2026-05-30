# Visual Forest Overlay — Dark Forest

`v0.0.77` adds a visual-only forest overlay pass for the `dark_forest` profile.

## Goal

The previous 16x16 forest tile approach was useful for pipeline testing, but on a full map it could look like a flat repeated pixel pattern. The new pass keeps the semantic forest mask from the world package and adds larger conifer canopy sprites over it.

## Contract

The pass is visual-only:

```text
- does not change terrain
- does not change height_grid
- does not change collision
- does not change movement
- does not move start/goal
- does not change routes or gameplay zones
```

## Inputs

```text
map_package/layers/terrain.json
top_down_visualgen/profiles/dark_forest/forest_overlay_rules.json
top_down_visualgen/profiles/dark_forest/assets_manifest.json
```

## Output

```text
output/visual_map/debug/forest_overlay_report.json
output/visual_map/debug/steps/12_forest_overlay.png
```

Final preview step moves to:

```text
output/visual_map/debug/steps/13_final_preview.png
```

## Asset IDs

The pass uses the B08-style large forest overlay sprites:

```text
forest.cluster_32x32_01
forest.cluster_32x32_02
forest.cluster_48x48_01
forest.cluster_48x48_02
forest.wall_32x48_01
forest.wall_32x48_02
forest.edge_cluster_n_32x32
forest.edge_cluster_s_32x32
forest.edge_cluster_e_32x32
forest.edge_cluster_w_32x32
```

## Why this exists

The target art direction needs dense readable conifer masses, not only small 16x16 forest fill tiles. Large clusters make the forest read as a canopy layer and reduce the visual “pixel carpet” effect.
