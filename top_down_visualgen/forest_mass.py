from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .models import VisualProfile, WorldPackage




@dataclass(frozen=True, slots=True)
class ForestMassAsset:
    """Loaded forest mass PNG asset."""

    asset_id: str
    category: str
    path: Path
    image: Image.Image


@dataclass(frozen=True, slots=True)
class ForestMassAnchor:
    """Resolved forest mass sprite anchor."""

    x_px: int
    y_px: int
    band: str
    asset: ForestMassAsset
    role: str

@dataclass(frozen=True, slots=True)
class ForestRegion:
    """Connected forest region diagnostics."""

    region_id: int
    area_tiles: int
    bounds: dict[str, int]
    edge_tiles: int
    interior_tiles: int
    deep_tiles: int


@dataclass(frozen=True, slots=True)
class ForestMassExperimentResult:
    """Field-based forest mass experiment result."""

    width: int
    height: int
    forest_terrain_types: tuple[str, ...]
    forest_mask: tuple[tuple[bool, ...], ...]
    edge_distances: tuple[tuple[int, ...], ...]
    region_ids: tuple[tuple[int, ...], ...]
    regions: tuple[ForestRegion, ...]
    seed: int

    def to_report(self) -> dict[str, Any]:
        """Build a JSON-serializable forest mass experiment report.

        Returns:
            Forest mass experiment diagnostics.
        """
        band_counts = self._band_counts()
        forest_tiles = sum(band_counts.values())
        anchor_counts = _estimate_anchor_counts(
            forest_mask=self.forest_mask,
            edge_distances=self.edge_distances,
            seed=self.seed,
        )
        return {
            "schema_version": "visual-debug-forest-mass-experiment-v1",
            "kind": "visual_debug_forest_mass_experiment_report",
            "source_layer": "terrain",
            "coordinate_space": "tile",
            "policy": {
                "experimental": True,
                "changes_final_render": False,
                "changes_gameplay": False,
                "changes_collision": False,
            },
            "forest_terrain_types": list(self.forest_terrain_types),
            "summary": {
                "width_tiles": self.width,
                "height_tiles": self.height,
                "forest_tiles": forest_tiles,
                "forest_regions": len(self.regions),
                "edge_tiles": band_counts["edge"],
                "interior_tiles": band_counts["interior"],
                "deep_tiles": band_counts["deep"],
                "estimated_tree_anchors": anchor_counts["total"],
                "estimated_tree_anchors_by_band": anchor_counts["by_band"],
                "largest_region_tiles": max(
                    (region.area_tiles for region in self.regions),
                    default=0,
                ),
            },
            "bands": {
                "edge": "distance_to_non_forest <= 1 tile",
                "interior": "distance_to_non_forest is 2..3 tiles",
                "deep": "distance_to_non_forest >= 4 tiles",
            },
            "regions": [
                {
                    "id": f"forest_region_{region.region_id:03d}",
                    "area_tiles": region.area_tiles,
                    "bounds": region.bounds,
                    "edge_tiles": region.edge_tiles,
                    "interior_tiles": region.interior_tiles,
                    "deep_tiles": region.deep_tiles,
                }
                for region in self.regions
            ],
            "quality": {
                "status": "ok" if forest_tiles > 0 else "no_forest_tiles",
            },
        }

    def _band_counts(self) -> dict[str, int]:
        counts = {"edge": 0, "interior": 0, "deep": 0}
        for y, row in enumerate(self.forest_mask):
            for x, is_forest in enumerate(row):
                if not is_forest:
                    continue
                counts[_band_for_distance(self.edge_distances[y][x])] += 1
        return counts


class ForestMassExperimentBuilder:
    """Build diagnostics for a field-based forest mass visual experiment."""

    def build(self, *, world: WorldPackage, profile: VisualProfile) -> ForestMassExperimentResult:
        """Build forest masks, regions, and distance fields.

        Args:
            world: Loaded world package.
            profile: Loaded visual profile.

        Returns:
            Forest mass experiment result.

        Raises:
            ValueError: If the terrain layer is malformed.
        """
        terrain_rows = _terrain_rows(world.terrain)
        forest_terrain_types = _forest_terrain_types(profile)
        forest_mask = _build_forest_mask(
            terrain_rows=terrain_rows,
            forest_terrain_types=forest_terrain_types,
        )
        edge_distances = _build_edge_distances(forest_mask)
        region_ids, regions = _extract_regions(
            forest_mask=forest_mask,
            edge_distances=edge_distances,
        )
        return ForestMassExperimentResult(
            width=len(terrain_rows[0]),
            height=len(terrain_rows),
            forest_terrain_types=tuple(sorted(forest_terrain_types)),
            forest_mask=tuple(tuple(row) for row in forest_mask),
            edge_distances=tuple(tuple(row) for row in edge_distances),
            region_ids=tuple(tuple(row) for row in region_ids),
            regions=tuple(regions),
            seed=_resolved_seed(world.index),
        )


def render_forest_mass_experiment(
    *,
    result: ForestMassExperimentResult,
    world: WorldPackage,
    profile: VisualProfile,
    output_path: Path,
    tile_size_px: int,
) -> Path:
    """Render a diagnostic forest mass experiment PNG.

    Args:
        result: Forest mass experiment data.
        world: Loaded world package.
        profile: Loaded visual profile.
        output_path: Output PNG path.
        tile_size_px: Debug tile size in pixels.

    Returns:
        Output PNG path.
    """
    terrain_rows = _terrain_rows(world.terrain)
    tile_size = max(1, tile_size_px)
    image = Image.new(
        "RGB",
        (result.width * tile_size, result.height * tile_size),
        "#111111",
    )
    draw = ImageDraw.Draw(image)
    _draw_muted_terrain(
        draw=draw,
        terrain_rows=terrain_rows,
        profile=profile,
        tile_size_px=tile_size,
    )
    _draw_forest_bands(draw=draw, result=result, tile_size_px=tile_size)
    _draw_tree_crowns(draw=draw, result=result, tile_size_px=tile_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def _terrain_rows(terrain: dict[str, Any]) -> list[list[str]]:
    rows = terrain.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Terrain layer must contain non-empty rows")
    result: list[list[str]] = []
    width: int | None = None
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or not all(isinstance(item, str) for item in row):
            raise ValueError(f"Terrain row {row_index} must be a list of strings")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("Terrain rows must have equal width")
        result.append(list(row))
    return result


def _forest_terrain_types(profile: VisualProfile) -> set[str]:
    mapping = profile.terrain_rules.get("terrain_to_tile", {})
    if not isinstance(mapping, dict):
        return set()
    result: set[str] = set()
    for terrain_type, tile_id in mapping.items():
        if not isinstance(terrain_type, str) or not isinstance(tile_id, str):
            continue
        if tile_id.startswith("forest."):
            result.add(terrain_type)
    return result


def _build_forest_mask(
    *,
    terrain_rows: list[list[str]],
    forest_terrain_types: set[str],
) -> list[list[bool]]:
    return [
        [terrain_type in forest_terrain_types for terrain_type in row]
        for row in terrain_rows
    ]


def _build_edge_distances(forest_mask: list[list[bool]]) -> list[list[int]]:
    height = len(forest_mask)
    width = len(forest_mask[0]) if height else 0
    distances = [[-1 for _ in range(width)] for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()
    for y, row in enumerate(forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            if _touches_non_forest(forest_mask=forest_mask, x=x, y=y):
                distances[y][x] = 0
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        next_distance = distances[y][x] + 1
        for nx, ny in _neighbors4(x, y):
            if not _inside(width=width, height=height, x=nx, y=ny):
                continue
            if not forest_mask[ny][nx] or distances[ny][nx] >= 0:
                continue
            distances[ny][nx] = next_distance
            queue.append((nx, ny))
    return distances


def _extract_regions(
    *,
    forest_mask: list[list[bool]],
    edge_distances: list[list[int]],
) -> tuple[list[list[int]], list[ForestRegion]]:
    height = len(forest_mask)
    width = len(forest_mask[0]) if height else 0
    region_ids = [[0 for _ in range(width)] for _ in range(height)]
    regions: list[ForestRegion] = []
    next_region_id = 1
    for y in range(height):
        for x in range(width):
            if not forest_mask[y][x] or region_ids[y][x] != 0:
                continue
            region = _flood_region(
                forest_mask=forest_mask,
                edge_distances=edge_distances,
                region_ids=region_ids,
                start_x=x,
                start_y=y,
                region_id=next_region_id,
            )
            regions.append(region)
            next_region_id += 1
    return region_ids, regions


def _flood_region(
    *,
    forest_mask: list[list[bool]],
    edge_distances: list[list[int]],
    region_ids: list[list[int]],
    start_x: int,
    start_y: int,
    region_id: int,
) -> ForestRegion:
    height = len(forest_mask)
    width = len(forest_mask[0]) if height else 0
    queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
    region_ids[start_y][start_x] = region_id
    area = 0
    min_x = max_x = start_x
    min_y = max_y = start_y
    band_counts = {"edge": 0, "interior": 0, "deep": 0}
    while queue:
        x, y = queue.popleft()
        area += 1
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        band_counts[_band_for_distance(edge_distances[y][x])] += 1
        for nx, ny in _neighbors4(x, y):
            if not _inside(width=width, height=height, x=nx, y=ny):
                continue
            if not forest_mask[ny][nx] or region_ids[ny][nx] != 0:
                continue
            region_ids[ny][nx] = region_id
            queue.append((nx, ny))
    return ForestRegion(
        region_id=region_id,
        area_tiles=area,
        bounds={
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x + 1,
            "height": max_y - min_y + 1,
        },
        edge_tiles=band_counts["edge"],
        interior_tiles=band_counts["interior"],
        deep_tiles=band_counts["deep"],
    )


def _draw_muted_terrain(
    *,
    draw: ImageDraw.ImageDraw,
    terrain_rows: list[list[str]],
    profile: VisualProfile,
    tile_size_px: int,
) -> None:
    terrain_to_tile = _terrain_to_tile(profile)
    tile_colors = _tile_colors(profile)
    default_tile = _string_value(profile.terrain_rules.get("default_tile"), "grass.base")
    for y, row in enumerate(terrain_rows):
        for x, terrain_type in enumerate(row):
            tile_id = terrain_to_tile.get(terrain_type, default_tile)
            color = _dim_color(tile_colors.get(tile_id, "#2e4028"), 0.38)
            draw.rectangle(_tile_rect(x, y, tile_size_px), fill=color)


def _draw_forest_bands(
    *,
    draw: ImageDraw.ImageDraw,
    result: ForestMassExperimentResult,
    tile_size_px: int,
) -> None:
    colors = {
        "edge": "#2f6f37",
        "interior": "#1f512b",
        "deep": "#12351f",
    }
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            band = _band_for_distance(result.edge_distances[y][x])
            draw.rectangle(_tile_rect(x, y, tile_size_px), fill=colors[band])


def _draw_tree_crowns(
    *,
    draw: ImageDraw.ImageDraw,
    result: ForestMassExperimentResult,
    tile_size_px: int,
) -> None:
    crown_colors = {
        "edge": ("#3f8a3f", "#163b1f"),
        "interior": ("#2a6d31", "#0d2c17"),
        "deep": ("#184b25", "#071b0d"),
    }
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            distance = result.edge_distances[y][x]
            band = _band_for_distance(distance)
            if _stable_noise(x=x, y=y, salt=11, seed=result.seed) > _density_for_band(band):
                continue
            center_x = (x + 0.5) * tile_size_px
            center_y = (y + 0.5) * tile_size_px
            jitter_x = (_stable_noise(x=x, y=y, salt=23, seed=result.seed) - 0.5) * tile_size_px
            jitter_y = (_stable_noise(x=x, y=y, salt=37, seed=result.seed) - 0.5) * tile_size_px
            radius = _crown_radius(tile_size_px=tile_size_px, band=band)
            fill, outline = crown_colors[band]
            draw.ellipse(
                (
                    center_x + jitter_x - radius,
                    center_y + jitter_y - radius,
                    center_x + jitter_x + radius,
                    center_y + jitter_y + radius,
                ),
                fill=fill,
                outline=outline,
            )


def _estimate_anchor_counts(
    *,
    forest_mask: tuple[tuple[bool, ...], ...],
    edge_distances: tuple[tuple[int, ...], ...],
    seed: int,
) -> dict[str, Any]:
    by_band = {"edge": 0, "interior": 0, "deep": 0}
    for y, row in enumerate(forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            band = _band_for_distance(edge_distances[y][x])
            if _stable_noise(x=x, y=y, salt=11, seed=seed) <= _density_for_band(band):
                by_band[band] += 1
    return {"total": sum(by_band.values()), "by_band": by_band}


def _touches_non_forest(*, forest_mask: list[list[bool]], x: int, y: int) -> bool:
    height = len(forest_mask)
    width = len(forest_mask[0]) if height else 0
    for nx, ny in _neighbors8(x, y):
        if not _inside(width=width, height=height, x=nx, y=ny):
            return True
        if not forest_mask[ny][nx]:
            return True
    return False


def _neighbors4(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def _neighbors8(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return (
        (x - 1, y - 1),
        (x, y - 1),
        (x + 1, y - 1),
        (x - 1, y),
        (x + 1, y),
        (x - 1, y + 1),
        (x, y + 1),
        (x + 1, y + 1),
    )


def _inside(*, width: int, height: int, x: int, y: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def _band_for_distance(distance: int) -> str:
    if distance <= 1:
        return "edge"
    if distance <= 3:
        return "interior"
    return "deep"


def _density_for_band(band: str) -> float:
    if band == "deep":
        return 0.96
    if band == "interior":
        return 0.78
    return 0.48


def _crown_radius(*, tile_size_px: int, band: str) -> float:
    base = max(1.5, tile_size_px * 0.42)
    if band == "deep":
        return base * 1.45
    if band == "interior":
        return base * 1.2
    return base


def _stable_noise(*, x: int, y: int, salt: int, seed: int) -> float:
    value = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791) ^ seed
    value &= 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xFFFFFFFF
    value ^= value >> 15
    value = (value * 0x846CA68B) & 0xFFFFFFFF
    value ^= value >> 16
    return value / 0xFFFFFFFF


def _resolved_seed(index: dict[str, Any]) -> int:
    seed = index.get("resolved_seed")
    if isinstance(seed, int):
        return seed
    return 0


def _terrain_to_tile(profile: VisualProfile) -> dict[str, str]:
    raw_mapping = profile.terrain_rules.get("terrain_to_tile", {})
    if not isinstance(raw_mapping, dict):
        return {}
    return {
        key: value
        for key, value in raw_mapping.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _tile_colors(profile: VisualProfile) -> dict[str, str]:
    tiles = profile.tilesets.get("tiles", {})
    if not isinstance(tiles, dict):
        return {}
    result: dict[str, str] = {}
    for tile_id, item in tiles.items():
        if not isinstance(tile_id, str) or not isinstance(item, dict):
            continue
        color = item.get("debug_color")
        if isinstance(color, str) and color.startswith("#"):
            result[tile_id] = color
    return result


def _tile_rect(x: int, y: int, tile_size_px: int) -> tuple[int, int, int, int]:
    return (
        x * tile_size_px,
        y * tile_size_px,
        (x + 1) * tile_size_px - 1,
        (y + 1) * tile_size_px - 1,
    )


def _dim_color(color: str, factor: float) -> str:
    if len(color) != 7 or not color.startswith("#"):
        return color
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f"#{int(red * factor):02x}{int(green * factor):02x}{int(blue * factor):02x}"


def _string_value(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default



def render_forest_mass_overlay(
    *,
    result: ForestMassExperimentResult,
    world: WorldPackage,
    profile: VisualProfile,
    visual_layers: dict[str, Any],
    output_path: Path,
    compare_output_path: Path | None,
    tile_size_px: int,
) -> dict[str, Any]:
    """Render an asset-backed forest mass overlay over the current final map.

    Args:
        result: Forest mass experiment data.
        world: Loaded world package.
        profile: Loaded visual profile.
        visual_layers: Current visual layers for fallback base rendering.
        output_path: Output overlay PNG path.
        compare_output_path: Optional A/B compare PNG path.
        tile_size_px: Fallback tile size in pixels.

    Returns:
        JSON-compatible overlay diagnostics.
    """
    del world
    base_image, base_source, tile_size = _build_overlay_base_image(
        result=result,
        profile=profile,
        visual_layers=visual_layers,
        output_path=output_path,
        fallback_tile_size_px=tile_size_px,
    )
    original_base = base_image.copy()
    asset_catalog = _load_forest_mass_assets(profile)
    anchors = _build_forest_mass_anchors(
        result=result,
        asset_catalog=asset_catalog,
        tile_size_px=tile_size,
    )

    image = base_image.copy()
    _paint_forest_floor(image=image, result=result, tile_size_px=tile_size)
    _draw_ground_patches(
        image=image,
        result=result,
        asset_catalog=asset_catalog,
        tile_size_px=tile_size,
    )
    _draw_anchor_shadows(
        image=image,
        anchors=anchors,
        asset_catalog=asset_catalog,
        tile_size_px=tile_size,
    )
    _draw_anchor_sprites(image=image, anchors=anchors, tile_size_px=tile_size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    compare_path = None
    if compare_output_path is not None:
        compare_path = _save_forest_mass_compare(
            before=original_base,
            after=image,
            output_path=compare_output_path,
        )

    asset_counts = Counter(anchor.asset.asset_id for anchor in anchors)
    band_counts = Counter(anchor.band for anchor in anchors)
    role_counts = Counter(anchor.role for anchor in anchors)
    return {
        "schema_version": "visual-debug-forest-mass-overlay-v1",
        "kind": "visual_debug_forest_mass_overlay_report",
        "source_layer": "terrain",
        "coordinate_space": "pixel",
        "policy": {
            "experimental": True,
            "changes_final_render": False,
            "changes_gameplay": False,
            "changes_collision": False,
            "changes_routes": False,
            "purpose": "Render a separate forest-only overlay preview over the existing final map.",
        },
        "outputs": {
            "overlay": output_path.as_posix(),
            "compare": compare_path.as_posix() if compare_path is not None else None,
        },
        "base": {
            "source": base_source,
            "tile_size_px": tile_size,
            "width_px": image.width,
            "height_px": image.height,
        },
        "assets": {
            "root": _forest_mass_asset_root(profile).as_posix(),
            "loaded_total": sum(len(items) for items in asset_catalog.values()),
            "by_category": {
                category: len(items)
                for category, items in sorted(asset_catalog.items())
            },
        },
        "summary": {
            "forest_tiles": sum(1 for row in result.forest_mask for item in row if item),
            "tree_anchors": len(anchors),
            "anchors_by_band": dict(sorted(band_counts.items())),
            "anchors_by_role": dict(sorted(role_counts.items())),
            "unique_assets_used": len(asset_counts),
        },
        "top_assets": [
            {"asset_id": asset_id, "count": count}
            for asset_id, count in asset_counts.most_common(12)
        ],
        "quality": {
            "status": "ok" if anchors else "no_forest_anchors",
        },
    }


def _build_overlay_base_image(
    *,
    result: ForestMassExperimentResult,
    profile: VisualProfile,
    visual_layers: dict[str, Any],
    output_path: Path,
    fallback_tile_size_px: int,
) -> tuple[Image.Image, str, int]:
    del output_path
    tile_size = max(1, _profile_tile_size(profile), fallback_tile_size_px)
    rows = _visual_layer_rows(visual_layers)
    image = Image.new(
        "RGBA",
        (result.width * tile_size, result.height * tile_size),
        (0, 0, 0, 255),
    )
    draw = ImageDraw.Draw(image)
    colors = _tile_colors(profile)
    for y, row in enumerate(rows):
        for x, tile_id in enumerate(row):
            draw.rectangle(
                _tile_rect(x, y, tile_size),
                fill=_hex_to_rgba(colors.get(tile_id, "#20351f"), 255),
            )
    return image, "visual_layers_clean_base", tile_size


def _profile_tile_size(profile: VisualProfile) -> int:
    tile_size = profile.profile.get("tile_size_px")
    if isinstance(tile_size, int) and tile_size > 0:
        return tile_size
    manifest_tile_size = profile.assets_manifest.get("tile_size")
    if (
        isinstance(manifest_tile_size, list)
        and manifest_tile_size
        and isinstance(manifest_tile_size[0], int)
        and manifest_tile_size[0] > 0
    ):
        return manifest_tile_size[0]
    return 16


def _image_tile_size(*, image: Image.Image, width_tiles: int, height_tiles: int) -> int | None:
    if width_tiles <= 0 or height_tiles <= 0:
        return None
    if image.width % width_tiles != 0 or image.height % height_tiles != 0:
        return None
    tile_width = image.width // width_tiles
    tile_height = image.height // height_tiles
    if tile_width != tile_height or tile_width <= 0:
        return None
    return tile_width


def _paint_forest_floor(
    *,
    image: Image.Image,
    result: ForestMassExperimentResult,
    tile_size_px: int,
) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    colors = {
        "edge": (36, 76, 35, 190),
        "interior": (24, 58, 29, 215),
        "deep": (9, 32, 17, 232),
    }
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            band = _band_for_distance(result.edge_distances[y][x])
            draw.rectangle(_tile_rect(x, y, tile_size_px), fill=colors[band])
    image.alpha_composite(overlay)


def _draw_ground_patches(
    *,
    image: Image.Image,
    result: ForestMassExperimentResult,
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    tile_size_px: int,
) -> None:
    ground_assets = asset_catalog.get("ground", ())
    if not ground_assets:
        return
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            distance = result.edge_distances[y][x]
            band = _band_for_distance(distance)
            threshold = 0.06 if band == "edge" else 0.12 if band == "interior" else 0.18
            if _stable_noise(x=x, y=y, salt=181, seed=result.seed) > threshold:
                continue
            asset = _pick_asset(
                assets=ground_assets,
                x=x,
                y=y,
                salt=191,
                seed=result.seed,
            )
            patch = _scaled_asset_image(asset.image, tile_size_px=tile_size_px)
            patch = _with_opacity(patch, 0.55 if band == "edge" else 0.72)
            center_x = int((x + 0.5) * tile_size_px)
            center_y = int((y + 0.5) * tile_size_px)
            _alpha_composite_clipped(
                base=image,
                overlay=patch,
                x=center_x - patch.width // 2,
                y=center_y - patch.height // 2,
            )


def _build_forest_mass_anchors(
    *,
    result: ForestMassExperimentResult,
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    tile_size_px: int,
) -> list[ForestMassAnchor]:
    anchors: list[ForestMassAnchor] = []
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            distance = result.edge_distances[y][x]
            band = _band_for_distance(distance)
            if _stable_noise(x=x, y=y, salt=211, seed=result.seed) > _overlay_density_for_band(band):
                continue
            role = _anchor_role_for_band(band=band, x=x, y=y, seed=result.seed)
            asset = _asset_for_role(
                role=role,
                band=band,
                asset_catalog=asset_catalog,
                x=x,
                y=y,
                seed=result.seed,
            )
            if asset is None:
                continue
            jitter_x = (_stable_noise(x=x, y=y, salt=223, seed=result.seed) - 0.5) * 1.25
            jitter_y = (_stable_noise(x=x, y=y, salt=227, seed=result.seed) - 0.5) * 0.85
            anchor_x = int((x + 0.5 + jitter_x) * tile_size_px)
            anchor_y = int((y + 1.0 + jitter_y) * tile_size_px)
            anchors.append(
                ForestMassAnchor(
                    x_px=anchor_x,
                    y_px=anchor_y,
                    band=band,
                    asset=asset,
                    role=role,
                )
            )
    anchors.sort(key=lambda item: (item.y_px, item.x_px, item.asset.asset_id))
    return anchors


def _draw_anchor_shadows(
    *,
    image: Image.Image,
    anchors: list[ForestMassAnchor],
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    tile_size_px: int,
) -> None:
    shadows = asset_catalog.get("shadows", ())
    if not shadows:
        return
    for index, anchor in enumerate(anchors):
        if anchor.role in {"edge_bush", "edge_stump"} and index % 2 == 1:
            continue
        shadow = _shadow_asset_for_anchor(anchor=anchor, shadows=shadows)
        shadow_image = _scaled_asset_image(shadow.image, tile_size_px=tile_size_px)
        opacity = 0.38 if anchor.band == "edge" else 0.52 if anchor.band == "interior" else 0.68
        shadow_image = _with_opacity(shadow_image, opacity)
        _alpha_composite_clipped(
            base=image,
            overlay=shadow_image,
            x=anchor.x_px - shadow_image.width // 2,
            y=anchor.y_px - shadow_image.height // 2,
        )


def _draw_anchor_sprites(
    *,
    image: Image.Image,
    anchors: list[ForestMassAnchor],
    tile_size_px: int,
) -> None:
    for anchor in anchors:
        asset_image = _scaled_asset_image(anchor.asset.image, tile_size_px=tile_size_px)
        _alpha_composite_clipped(
            base=image,
            overlay=asset_image,
            x=anchor.x_px - asset_image.width // 2,
            y=anchor.y_px - asset_image.height,
        )


def _save_forest_mass_compare(
    *,
    before: Image.Image,
    after: Image.Image,
    output_path: Path,
) -> Path:
    before_preview = _fit_compare_preview(before)
    after_preview = _fit_compare_preview(after)
    width = before_preview.width + after_preview.width
    height = max(before_preview.height, after_preview.height)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    image.alpha_composite(before_preview, (0, 0))
    image.alpha_composite(after_preview, (before_preview.width, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, before_preview.width - 1, 18), fill=(0, 0, 0, 170))
    draw.rectangle((before_preview.width, 0, width - 1, 18), fill=(0, 0, 0, 170))
    draw.text((6, 4), "before", fill=(235, 235, 220, 255))
    draw.text((before_preview.width + 6, 4), "forest mass overlay", fill=(235, 235, 220, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def _fit_compare_preview(image: Image.Image, max_width: int = 1536) -> Image.Image:
    if image.width <= max_width:
        return image.copy()
    scale = max_width / image.width
    size = (max_width, max(1, int(image.height * scale)))
    return image.resize(size, Image.Resampling.BILINEAR)


def _load_forest_mass_assets(profile: VisualProfile) -> dict[str, tuple[ForestMassAsset, ...]]:
    root = _forest_mass_asset_root(profile)
    result: dict[str, tuple[ForestMassAsset, ...]] = {}
    for category in ("clusters", "trees", "edge", "ground", "shadows"):
        category_dir = root / category
        assets: list[ForestMassAsset] = []
        for path in sorted(category_dir.glob("*.png")):
            assets.append(
                ForestMassAsset(
                    asset_id=f"{category}.{path.stem}",
                    category=category,
                    path=path,
                    image=Image.open(path).convert("RGBA"),
                )
            )
        result[category] = tuple(assets)
    return result


def _forest_mass_asset_root(profile: VisualProfile) -> Path:
    asset_root_value = profile.assets_manifest.get("asset_root")
    if isinstance(asset_root_value, str) and asset_root_value:
        asset_root = (profile.root_dir / asset_root_value).resolve()
    else:
        asset_root = profile.root_dir.resolve()
    return asset_root / "forest_mass"


def _asset_for_role(
    *,
    role: str,
    band: str,
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    x: int,
    y: int,
    seed: int,
) -> ForestMassAsset | None:
    pools = _asset_pools_for_role(role=role, band=band, asset_catalog=asset_catalog)
    for salt, assets in pools:
        if assets:
            return _pick_asset(assets=assets, x=x, y=y, salt=salt, seed=seed)
    return None


def _asset_pools_for_role(
    *,
    role: str,
    band: str,
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
) -> tuple[tuple[int, tuple[ForestMassAsset, ...]], ...]:
    clusters = asset_catalog.get("clusters", ())
    trees = asset_catalog.get("trees", ())
    edge = asset_catalog.get("edge", ())
    if role == "deep_cluster":
        return (
            (311, _filter_assets(clusters, ("deep",))),
            (313, _filter_assets(clusters, ("large",))),
            (317, clusters),
        )
    if role == "mid_cluster":
        return (
            (331, _filter_assets(clusters, ("mid", "large"))),
            (337, clusters),
        )
    if role == "edge_cluster":
        return (
            (347, _filter_assets(clusters, ("small", "mid"))),
            (349, clusters),
        )
    if role == "edge_bush":
        return (
            (353, _filter_assets(edge, ("bush", "young"))),
            (359, edge),
        )
    if role == "edge_stump":
        return (
            (367, _filter_assets(edge, ("stump",))),
            (373, edge),
        )
    if band == "deep":
        return (
            (379, _filter_assets(trees, ("large", "tall"))),
            (383, trees),
        )
    if band == "interior":
        return (
            (389, _filter_assets(trees, ("mid", "large"))),
            (397, trees),
        )
    return (
        (401, _filter_assets(trees, ("small", "mid"))),
        (409, trees),
    )


def _anchor_role_for_band(*, band: str, x: int, y: int, seed: int) -> str:
    value = _stable_noise(x=x, y=y, salt=257, seed=seed)
    if band == "deep":
        if value < 0.72:
            return "deep_cluster"
        return "deep_tree"
    if band == "interior":
        if value < 0.46:
            return "mid_cluster"
        return "mid_tree"
    if value < 0.18:
        return "edge_cluster"
    if value < 0.68:
        return "edge_tree"
    if value < 0.9:
        return "edge_bush"
    return "edge_stump"


def _overlay_density_for_band(band: str) -> float:
    if band == "deep":
        return 0.28
    if band == "interior":
        return 0.34
    return 0.46


def _filter_assets(
    assets: tuple[ForestMassAsset, ...],
    needles: tuple[str, ...],
) -> tuple[ForestMassAsset, ...]:
    return tuple(
        asset
        for asset in assets
        if any(needle in asset.asset_id for needle in needles)
    )


def _pick_asset(
    *,
    assets: tuple[ForestMassAsset, ...],
    x: int,
    y: int,
    salt: int,
    seed: int,
) -> ForestMassAsset:
    index = int(_stable_noise(x=x, y=y, salt=salt, seed=seed) * len(assets))
    return assets[min(index, len(assets) - 1)]


def _shadow_asset_for_anchor(
    *,
    anchor: ForestMassAnchor,
    shadows: tuple[ForestMassAsset, ...],
) -> ForestMassAsset:
    if anchor.role in {"deep_cluster", "mid_cluster"}:
        preferred = _filter_assets(shadows, ("mass", "large"))
    elif anchor.band == "edge":
        preferred = _filter_assets(shadows, ("small", "mid"))
    else:
        preferred = _filter_assets(shadows, ("mid", "large"))
    if not preferred:
        preferred = shadows
    index = sum(ord(ch) for ch in anchor.asset.asset_id) % len(preferred)
    return preferred[index]


def _scaled_asset_image(image: Image.Image, *, tile_size_px: int) -> Image.Image:
    scale = tile_size_px / _asset_base_tile_size()
    if abs(scale - 1.0) < 0.001:
        return image
    size = (
        max(1, int(image.width * scale)),
        max(1, int(image.height * scale)),
    )
    return image.resize(size, Image.Resampling.BILINEAR)


def _asset_base_tile_size() -> int:
    return 16


def _with_opacity(image: Image.Image, opacity: float) -> Image.Image:
    clamped = max(0.0, min(1.0, opacity))
    result = image.copy()
    alpha = result.getchannel("A").point(lambda value: int(value * clamped))
    result.putalpha(alpha)
    return result


def _visual_layer_rows(visual_layers: dict[str, Any]) -> list[list[str]]:
    layers = visual_layers.get("layers")
    if not isinstance(layers, list):
        raise ValueError("visual_layers.layers must be a list")
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "terrain_base":
            rows = layer.get("rows")
            if isinstance(rows, list) and rows:
                return [[str(item) for item in row] for row in rows if isinstance(row, list)]
    raise ValueError("Missing terrain_base visual layer")


def _hex_to_rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    if len(color) != 7 or not color.startswith("#"):
        return (32, 53, 31, alpha)
    return (
        int(color[1:3], 16),
        int(color[3:5], 16),
        int(color[5:7], 16),
        alpha,
    )


def _alpha_composite_clipped(base: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(base.width, x + overlay.width)
    bottom = min(base.height, y + overlay.height)
    if right <= left or bottom <= top:
        return
    crop_left = left - x
    crop_top = top - y
    crop_right = crop_left + (right - left)
    crop_bottom = crop_top + (bottom - top)
    cropped = overlay.crop((crop_left, crop_top, crop_right, crop_bottom))
    base.alpha_composite(cropped, (left, top))
