# Dark Forest Rendering Model

## Purpose

This document resets the `dark_forest` visual direction after the first asset-backed rendering experiments.

The current pipeline can already generate world data, visual layers, visual objects, debug previews, asset-backed `final_render.png`, and imported draft assets. That part is useful and should be kept.

The problem is artistic, not mechanical: a dark forest map that should look like a cohesive hand-authored top-down scene cannot be achieved by turning every terrain cell into a noisy `16x16` tile and then scattering more sprites on top.

## Current conclusion

The first asset packs and forest overlay pass proved the pipeline works, but also exposed the wrong visual abstraction.

The old mental model was:

```text
terrain cell -> visual tile id -> PNG
forest cell -> forest tile / forest sprite
```

For the target style this is not enough. It creates a tiled carpet, repeated noise, and sticker-like objects.

The new mental model is:

```text
world data -> visual region masks -> painted biome renderer -> sparse objects/details
```

Forest and grass must be treated as region rendering problems, not as simple object placement problems.

## What remains valid

The following systems remain useful:

- `world package` as the source of gameplay meaning;
- `visual_map.json`, `visual_layers.json`, `visual_objects.json`;
- asset manifest and asset-backed final render;
- draft asset importer;
- density/debug reports;
- autotiling for roads, swamp, ruins and hard terrain transitions;
- micro-scene metadata;
- elevation metadata and visual reports.

B01-B07 assets are useful as prototype/test assets. They are not considered final art quality.

B08 large forest clusters are useful as an art direction experiment. They should not be treated as the final forest solution by themselves.

## Target rendering model

### Grass

Grass should be rendered as a calm base layer.

Required behavior:

- low-frequency variation;
- soft patches, not per-pixel noise;
- slightly warmer/lighter open areas;
- darker grass near forest borders;
- sparse overlays for flowers, stones, dry grass and debris.

Avoid:

- noisy `16x16` checker carpets;
- high-frequency pixel glitter;
- every tile trying to be visually interesting.

Recommended structure:

```text
grass base layer
  -> soft noise / regional tint
  -> sparse overlay patches
  -> small detail sprites only where density rules allow
```

### Forest

Forest must be rendered as a visual region.

Required behavior:

- forest ground base under the whole forest region;
- soft organic region edge;
- canopy mass layer;
- large readable conifer clusters;
- depth/shadow layer;
- sparse edge details.

Avoid:

- forest as a repeated `16x16` fill tile;
- dense random scatter of tree sprites;
- uniform boundary walls;
- sticker-like trees that do not merge into a forest mass.

Recommended structure:

```text
forest mask
  -> forest ground base
  -> dual-grid / marching-squares edge layer
  -> canopy mass clusters
  -> depth shadows
  -> sparse readable details
```

### Forest edges

Forest edges are the most important part visually.

They should be based on region masks, not single-cell random placement.

Possible approaches:

- dual-grid edge renderer;
- marching squares edge renderer;
- soft edge patches on top of a terrain mask;
- large edge clusters placed by boundary direction and local curvature.

The edge should hide square grid logic and make the forest feel organic.

### Roads

Roads can remain tile/autotile-based, but need better blending.

Recommended structure:

```text
road centerline/autotile
  -> soft grass edge
  -> dirt variation
  -> sparse road debris
```

Roads in this profile should feel like old overgrown roads, not clean RPG roads.

### Swamp

Swamp is walkable slow terrain, not open water.

Recommended structure:

```text
wet ground base
  -> mud patches
  -> puddles
  -> reeds/sparse swamp details
```

### Ruins

Ruins can use tiles and object clusters.

Recommended structure:

```text
ruin floor/wall autotiles
  -> rubble clusters
  -> moss/dirt overlay
  -> occasional place objects
```

### Objects and micro-scenes

Objects should support the region, not replace the region renderer.

Good examples:

- campfire ash;
- abandoned crate;
- broken plank;
- rubble;
- bones;
- hidden cache marker.

Bad behavior:

- using object scatter to compensate for bad terrain rendering;
- too many tiny objects creating noise.

## Proposed next implementation plan

### v0.0.79 — grass base renderer MVP

Goal: make open ground calmer and closer to the reference before touching forest again.

Tasks:

- add a grass region/base rendering pass;
- reduce dependence on noisy grass tiles;
- generate low-frequency tint/patch overlays;
- report grass rendering density;
- keep gameplay unchanged.

### v0.0.80 — forest region renderer MVP

Goal: replace forest carpet rendering with region-based forest rendering.

Tasks:

- read `forest` / `tree_blocker` mask;
- produce forest ground base;
- detect forest edges;
- place larger canopy masses based on spacing and local density;
- write `forest_region_report.json`;
- add debug step.

### v0.0.81 — forest edge renderer

Goal: make the forest boundary organic.

Tasks:

- implement dual-grid or marching-squares edge layer;
- add edge curvature classification;
- place directional edge clusters;
- reduce visible rectangular grid artifacts.

### v0.0.82 — final render art tuning

Goal: tune visual balance on real generated maps.

Tasks:

- compare `final_render.png` with the reference;
- adjust densities;
- adjust palette/tint;
- reduce noisy overlays;
- improve summary reports.

## Non-goals

Do not solve this by adding more random assets.

Do not continue producing dozens of small `16x16` tiles until the region renderer is defined.

Do not mix gameplay changes into the rendering model.

Do not make forest rendering responsible for collision, movement or routes.

## Practical decision

The current `forest_overlay` work should be treated as an experimental step.

It may stay in the codebase as a prototype if it does not break anything, but the next production direction should be region-based rendering, not more overlay scatter.
