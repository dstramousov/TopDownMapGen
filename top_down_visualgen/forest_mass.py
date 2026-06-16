from __future__ import annotations

from collections import Counter, deque
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from .models import VisualProfile, WorldPackage




@dataclass(frozen=True, slots=True)
class ForestMassAsset:
    """Loaded forest mass PNG asset."""

    asset_id: str
    category: str
    path: Path
    image: Image.Image
    family: str
    role_hint: str
    zone: str
    anchor_x: int | None = None
    anchor_y: int | None = None


@dataclass(frozen=True, slots=True)
class ForestMassAnchor:
    """Resolved forest mass sprite anchor."""

    x_px: int
    y_px: int
    tile_x: int
    tile_y: int
    band: str
    asset: ForestMassAsset
    role: str
    condition: str


@dataclass(frozen=True, slots=True)
class ForestMassAnchorBuildResult:
    """Resolved forest mass anchors and placement diagnostics."""

    anchors: tuple[ForestMassAnchor, ...]
    rejected_bounds: int
    rejected_footprint: int
    rejected_policy: int
    skipped_missing_asset: int
    condition_counts: dict[str, int]
    selected_family_counts: dict[str, int]
    rejected_counts: dict[str, int]

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
    return _render_forest_mass_overlay_impl(
        result=result,
        world=world,
        profile=profile,
        visual_layers=visual_layers,
        output_path=output_path,
        compare_output_path=compare_output_path,
        tile_size_px=tile_size_px,
        variant="overlay",
    )


def render_forest_mass_overlay_clean(
    *,
    result: ForestMassExperimentResult,
    world: WorldPackage,
    profile: VisualProfile,
    visual_layers: dict[str, Any],
    output_path: Path,
    compare_output_path: Path | None,
    tile_size_px: int,
) -> dict[str, Any]:
    """Render a cleaned condition-driven forest mass overlay preview.

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
    return _render_forest_mass_overlay_impl(
        result=result,
        world=world,
        profile=profile,
        visual_layers=visual_layers,
        output_path=output_path,
        compare_output_path=compare_output_path,
        tile_size_px=tile_size_px,
        variant="clean",
    )


def render_forest_mass_overlay_placement_fix(
    *,
    result: ForestMassExperimentResult,
    world: WorldPackage,
    profile: VisualProfile,
    visual_layers: dict[str, Any],
    output_path: Path,
    compare_output_path: Path | None,
    tile_size_px: int,
) -> dict[str, Any]:
    """Render a placement-policy fixed forest mass overlay preview.

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
    return _render_forest_mass_overlay_impl(
        result=result,
        world=world,
        profile=profile,
        visual_layers=visual_layers,
        output_path=output_path,
        compare_output_path=compare_output_path,
        tile_size_px=tile_size_px,
        variant="placement_fix",
    )


def render_forest_mass_canopy_fill(
    *,
    result: ForestMassExperimentResult,
    world: WorldPackage,
    profile: VisualProfile,
    visual_layers: dict[str, Any],
    output_path: Path,
    compare_output_path: Path | None,
    tile_size_px: int,
) -> dict[str, Any]:
    """Render a canopy-fill forest mass overlay preview.

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
    return _render_forest_mass_overlay_impl(
        result=result,
        world=world,
        profile=profile,
        visual_layers=visual_layers,
        output_path=output_path,
        compare_output_path=compare_output_path,
        tile_size_px=tile_size_px,
        variant="canopy_fill",
    )


def _render_forest_mass_overlay_impl(
    *,
    result: ForestMassExperimentResult,
    world: WorldPackage,
    profile: VisualProfile,
    visual_layers: dict[str, Any],
    output_path: Path,
    compare_output_path: Path | None,
    tile_size_px: int,
    variant: str,
) -> dict[str, Any]:
    base_image, base_source, tile_size = _build_overlay_base_image(
        result=result,
        profile=profile,
        visual_layers=visual_layers,
        fallback_tile_size_px=tile_size_px,
    )
    original_base = base_image.copy()
    terrain_rows = _terrain_rows(world.terrain)
    asset_catalog = _load_forest_mass_assets(profile)
    anchor_result = _build_forest_mass_anchors(
        result=result,
        terrain_rows=terrain_rows,
        asset_catalog=asset_catalog,
        image_size=base_image.size,
        tile_size_px=tile_size,
        variant=variant,
    )

    image = base_image.copy()
    if variant == "canopy_fill":
        _paint_canopy_fill(image=image, result=result, tile_size_px=tile_size)
    elif variant == "placement_fix":
        _paint_soft_forest_floor(image=image, result=result, tile_size_px=tile_size)
    else:
        _paint_forest_floor(image=image, result=result, tile_size_px=tile_size)
        _draw_ground_patches(
            image=image,
            result=result,
            asset_catalog=asset_catalog,
            tile_size_px=tile_size,
        )
    _draw_anchor_shadows(
        image=image,
        anchors=list(anchor_result.anchors),
        asset_catalog=asset_catalog,
        tile_size_px=tile_size,
        variant=variant,
    )
    _draw_anchor_sprites(
        image=image,
        anchors=list(anchor_result.anchors),
        tile_size_px=tile_size,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    compare_path = None
    if compare_output_path is not None:
        compare_path = _save_forest_mass_compare(
            before=original_base,
            after=image,
            output_path=compare_output_path,
            label=_forest_mass_compare_label(variant),
        )

    asset_counts = Counter(anchor.asset.asset_id for anchor in anchor_result.anchors)
    band_counts = Counter(anchor.band for anchor in anchor_result.anchors)
    role_counts = Counter(anchor.role for anchor in anchor_result.anchors)
    family_counts = Counter(anchor.asset.family for anchor in anchor_result.anchors)
    return {
        "schema_version": "visual-debug-forest-mass-overlay-v3",
        "kind": "visual_debug_forest_mass_overlay_report",
        "variant": variant,
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
            "loaded_total": len(asset_catalog.get("all", ())),
            "by_category": _catalog_count_by_key(asset_catalog, prefix="category:"),
            "by_family": _catalog_count_by_key(asset_catalog, prefix="family:", limit=24),
        },
        "summary": {
            "forest_tiles": sum(1 for row in result.forest_mask for item in row if item),
            "tree_anchors": len(anchor_result.anchors),
            "anchors_by_band": dict(sorted(band_counts.items())),
            "anchors_by_role": dict(sorted(role_counts.items())),
            "anchors_by_condition": dict(sorted(anchor_result.condition_counts.items())),
            "unique_assets_used": len(asset_counts),
            "rejected_bounds": anchor_result.rejected_bounds,
            "rejected_footprint": anchor_result.rejected_footprint,
            "rejected_policy": anchor_result.rejected_policy,
            "skipped_missing_asset": anchor_result.skipped_missing_asset,
            "selected_families": dict(sorted(anchor_result.selected_family_counts.items())),
            "rejected_by_reason": dict(sorted(anchor_result.rejected_counts.items())),
        },
        "top_assets": [
            {"asset_id": asset_id, "count": count}
            for asset_id, count in asset_counts.most_common(12)
        ],
        "top_families": [
            {"family": family, "count": count}
            for family, count in family_counts.most_common(12)
        ],
        "quality": {
            "status": "ok" if anchor_result.anchors else "no_forest_anchors",
            "bounds_policy": "reject_full_bounds_outside_canvas",
            "condition_policy": _condition_policy_label(variant),
            "ground_policy": _ground_policy_label(variant),
        },
    }


def _condition_policy_label(variant: str) -> str:
    """Return the condition policy label for a forest mass overlay variant."""
    if variant == "canopy_fill":
        return "dense canopy fill with priority conditions and footprint validation"
    if variant == "placement_fix":
        return "priority condition matrix with sprite bounds and footprint validation"
    return "rule-first condition matrix with zone fallbacks"


def _ground_policy_label(variant: str) -> str:
    """Return the ground policy label for a forest mass overlay variant."""
    if variant == "canopy_fill":
        return "organic canopy underpaint hides deep forest ground holes"
    if variant == "placement_fix":
        return "soft_mask_no_square_ground_patches"
    return "tile_rectangles_and_ground_patches"


def _build_overlay_base_image(
    *,
    result: ForestMassExperimentResult,
    profile: VisualProfile,
    visual_layers: dict[str, Any],
    fallback_tile_size_px: int,
) -> tuple[Image.Image, str, int]:
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


def _paint_forest_floor(
    *,
    image: Image.Image,
    result: ForestMassExperimentResult,
    tile_size_px: int,
) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    colors = {
        "edge": (35, 75, 34, 150),
        "interior": (21, 55, 27, 190),
        "deep": (7, 28, 14, 220),
    }
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            band = _band_for_distance(result.edge_distances[y][x])
            draw.rectangle(_tile_rect(x, y, tile_size_px), fill=colors[band])
    image.alpha_composite(overlay)


def _paint_soft_forest_floor(
    *,
    image: Image.Image,
    result: ForestMassExperimentResult,
    tile_size_px: int,
) -> None:
    """Paint forest floor as a blurred mask instead of tile rectangles."""
    alpha = Image.new("L", image.size, 0)
    alpha_draw = ImageDraw.Draw(alpha)
    color_layer = Image.new("RGBA", image.size, (9, 28, 13, 0))
    color_draw = ImageDraw.Draw(color_layer)
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            band = _band_for_distance(result.edge_distances[y][x])
            cx = int((x + 0.5) * tile_size_px)
            cy = int((y + 0.5) * tile_size_px)
            radius = _soft_floor_radius(tile_size_px=tile_size_px, band=band)
            opacity = _soft_floor_opacity(band=band)
            bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
            alpha_draw.ellipse(bbox, fill=opacity)
            color_draw.ellipse(bbox, fill=_soft_floor_color(band=band))
    blur_radius = max(1.25, tile_size_px * 0.65)
    alpha = alpha.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    color_layer.putalpha(alpha)
    image.alpha_composite(color_layer)


def _soft_floor_radius(*, tile_size_px: int, band: str) -> int:
    if band == "deep":
        return int(tile_size_px * 1.25)
    if band == "interior":
        return int(tile_size_px * 1.05)
    return int(tile_size_px * 0.78)


def _soft_floor_opacity(*, band: str) -> int:
    if band == "deep":
        return 118
    if band == "interior":
        return 86
    return 42


def _soft_floor_color(*, band: str) -> tuple[int, int, int, int]:
    if band == "deep":
        return (5, 22, 10, 255)
    if band == "interior":
        return (17, 50, 22, 255)
    return (38, 78, 35, 255)


def _paint_canopy_fill(
    *,
    image: Image.Image,
    result: ForestMassExperimentResult,
    tile_size_px: int,
) -> None:
    """Paint an organic canopy underlayer that hides square ground gaps."""
    canopy = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canopy, "RGBA")
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            band = _band_for_distance(result.edge_distances[y][x])
            for blob_index in range(_canopy_blob_count(band=band)):
                cx, cy = _canopy_blob_center(
                    x=x,
                    y=y,
                    blob_index=blob_index,
                    seed=result.seed,
                    tile_size_px=tile_size_px,
                )
                rx, ry = _canopy_blob_radius(
                    band=band,
                    blob_index=blob_index,
                    tile_size_px=tile_size_px,
                    x=x,
                    y=y,
                    seed=result.seed,
                )
                draw.ellipse(
                    (cx - rx, cy - ry, cx + rx, cy + ry),
                    fill=_canopy_blob_color(
                        band=band,
                        x=x,
                        y=y,
                        blob_index=blob_index,
                        seed=result.seed,
                    ),
                )
    image.alpha_composite(canopy)


def _canopy_blob_count(*, band: str) -> int:
    if band == "deep":
        return 3
    if band == "interior":
        return 2
    return 1


def _canopy_blob_center(
    *,
    x: int,
    y: int,
    blob_index: int,
    seed: int,
    tile_size_px: int,
) -> tuple[int, int]:
    jitter_x = (_stable_noise(x=x, y=y, salt=701 + blob_index * 7, seed=seed) - 0.5)
    jitter_y = (_stable_noise(x=x, y=y, salt=719 + blob_index * 7, seed=seed) - 0.5)
    return (
        int((x + 0.5 + jitter_x * 0.72) * tile_size_px),
        int((y + 0.5 + jitter_y * 0.56) * tile_size_px),
    )


def _canopy_blob_radius(
    *,
    band: str,
    blob_index: int,
    tile_size_px: int,
    x: int,
    y: int,
    seed: int,
) -> tuple[int, int]:
    noise = _stable_noise(x=x, y=y, salt=743 + blob_index * 11, seed=seed)
    if band == "deep":
        base_x = tile_size_px * (0.92 + noise * 0.35)
        base_y = tile_size_px * (0.66 + noise * 0.22)
    elif band == "interior":
        base_x = tile_size_px * (0.78 + noise * 0.28)
        base_y = tile_size_px * (0.56 + noise * 0.20)
    else:
        base_x = tile_size_px * (0.52 + noise * 0.20)
        base_y = tile_size_px * (0.38 + noise * 0.14)
    return (max(2, int(base_x)), max(2, int(base_y)))


def _canopy_blob_color(*, band: str, x: int, y: int, blob_index: int, seed: int) -> tuple[int, int, int, int]:
    noise = _stable_noise(x=x, y=y, salt=761 + blob_index * 13, seed=seed)
    if band == "deep":
        return (
            12 + int(noise * 12),
            43 + int(noise * 22),
            19 + int(noise * 12),
            218,
        )
    if band == "interior":
        return (
            24 + int(noise * 18),
            70 + int(noise * 24),
            30 + int(noise * 14),
            192,
        )
    return (
        43 + int(noise * 18),
        92 + int(noise * 22),
        42 + int(noise * 14),
        112,
    )


def _draw_ground_patches(
    *,
    image: Image.Image,
    result: ForestMassExperimentResult,
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    tile_size_px: int,
) -> None:
    ground_assets = _catalog_get(
        asset_catalog,
        [
            "family:forest_floor_dark_patch",
            "family:forest_floor_mid_patch",
            "family:wet_forest_floor_patch",
            "category:ground",
            "category:fillers",
        ],
    )
    if not ground_assets:
        return
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            distance = result.edge_distances[y][x]
            band = _band_for_distance(distance)
            threshold = 0.04 if band == "edge" else 0.10 if band == "interior" else 0.16
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
            patch = _with_opacity(patch, 0.45 if band == "edge" else 0.64)
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
    terrain_rows: list[list[str]],
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    image_size: tuple[int, int],
    tile_size_px: int,
    variant: str,
) -> ForestMassAnchorBuildResult:
    anchors: list[ForestMassAnchor] = []
    rejected_bounds = 0
    rejected_footprint = 0
    rejected_policy = 0
    skipped_missing_asset = 0
    condition_counts: Counter[str] = Counter()
    selected_family_counts: Counter[str] = Counter()
    rejected_counts: Counter[str] = Counter()
    region_areas = {region.region_id: region.area_tiles for region in result.regions}
    for y, row in enumerate(result.forest_mask):
        for x, is_forest in enumerate(row):
            if not is_forest:
                continue
            distance = result.edge_distances[y][x]
            band = _band_for_distance(distance)
            condition = _forest_condition_for_tile(
                result=result,
                terrain_rows=terrain_rows,
                region_areas=region_areas,
                x=x,
                y=y,
                band=band,
            )
            density = _overlay_density_for_condition(
                condition=condition,
                band=band,
                variant=variant,
            )
            if _stable_noise(x=x, y=y, salt=211, seed=result.seed) > density:
                continue
            role = _anchor_role_for_condition(condition=condition, band=band, x=x, y=y, seed=result.seed)
            anchor_x, anchor_y = _anchor_pixel_for_condition(
                x=x,
                y=y,
                condition=condition,
                band=band,
                tile_size_px=tile_size_px,
                seed=result.seed,
            )
            candidates = _candidate_assets_for_condition(
                condition=condition,
                role=role,
                band=band,
                asset_catalog=asset_catalog,
                x=x,
                y=y,
                seed=result.seed,
            )
            if not candidates:
                skipped_missing_asset += 1
                rejected_counts["missing_asset"] += 1
                continue
            selected: tuple[ForestMassAsset, Image.Image, int, int] | None = None
            for asset in candidates:
                if not _asset_policy_allowed(asset=asset, condition=condition, band=band):
                    rejected_policy += 1
                    rejected_counts["policy"] += 1
                    continue
                asset_image = _scaled_asset_image(asset.image, tile_size_px=tile_size_px)
                draw_x, draw_y = _asset_draw_position(
                    asset=asset,
                    asset_image=asset_image,
                    x_px=anchor_x,
                    y_px=anchor_y,
                    fallback_mode="sprite",
                )
                if not _sprite_bounds_allowed(
                    x=draw_x,
                    y=draw_y,
                    width=asset_image.width,
                    height=asset_image.height,
                    image_size=image_size,
                    condition=condition,
                ):
                    rejected_bounds += 1
                    rejected_counts["bounds"] += 1
                    continue
                if not _sprite_footprint_allowed(
                    result=result,
                    terrain_rows=terrain_rows,
                    condition=condition,
                    band=band,
                    x=draw_x,
                    y=draw_y,
                    width=asset_image.width,
                    height=asset_image.height,
                    tile_size_px=tile_size_px,
                ):
                    rejected_footprint += 1
                    rejected_counts["footprint"] += 1
                    continue
                selected = (asset, asset_image, draw_x, draw_y)
                break
            if selected is None:
                skipped_missing_asset += 1
                continue
            asset = selected[0]
            anchors.append(
                ForestMassAnchor(
                    x_px=anchor_x,
                    y_px=anchor_y,
                    tile_x=x,
                    tile_y=y,
                    band=band,
                    asset=asset,
                    role=role,
                    condition=condition,
                )
            )
            condition_counts[condition] += 1
            selected_family_counts[asset.family] += 1
    anchors.sort(key=lambda item: (item.y_px, item.x_px, item.asset.asset_id))
    return ForestMassAnchorBuildResult(
        anchors=tuple(anchors),
        rejected_bounds=rejected_bounds,
        rejected_footprint=rejected_footprint,
        rejected_policy=rejected_policy,
        skipped_missing_asset=skipped_missing_asset,
        condition_counts=dict(condition_counts),
        selected_family_counts=dict(selected_family_counts),
        rejected_counts=dict(rejected_counts),
    )


def _forest_condition_for_tile(
    *,
    result: ForestMassExperimentResult,
    terrain_rows: list[list[str]],
    region_areas: dict[int, int],
    x: int,
    y: int,
    band: str,
) -> str:
    width = result.width
    height = result.height
    region_id = result.region_ids[y][x]
    region_area = region_areas.get(region_id, 0)
    outside_n = _outside_forest(result=result, x=x, y=y - 1)
    outside_s = _outside_forest(result=result, x=x, y=y + 1)
    outside_w = _outside_forest(result=result, x=x - 1, y=y)
    outside_e = _outside_forest(result=result, x=x + 1, y=y)
    near = _near_context(terrain_rows=terrain_rows, x=x, y=y, radius=2)

    if _near_map_border(width=width, height=height, x=x, y=y, margin=2):
        return "map_border_guard"
    if region_area <= 1:
        return "forest_isolated_single"
    if region_area <= 12:
        return "small_forest_island"
    if outside_n and outside_s and not outside_w and not outside_e:
        return "forest_thin_strip_ew"
    if outside_w and outside_e and not outside_n and not outside_s:
        return "forest_thin_strip_ns"
    if band == "edge" and near["road"]:
        return "forest_near_road"
    if band == "edge" and near["ruins"]:
        return "forest_near_ruins"
    if band == "edge" and near["water"]:
        return "forest_near_water"
    if outside_e and outside_s:
        return "outer_corner_es"
    if outside_w and outside_s:
        return "outer_corner_sw"
    if outside_e and outside_n:
        return "outer_corner_ne"
    if outside_w and outside_n:
        return "outer_corner_nw"
    if outside_s:
        return "edge_front_south"
    if outside_n:
        return "edge_back_north"
    if outside_w:
        return "edge_side_west"
    if outside_e:
        return "edge_side_east"
    if band == "deep":
        return "deep_forest_mass"
    if band == "interior":
        return "mid_forest_mass"
    return "edge_generic"


def _outside_forest(*, result: ForestMassExperimentResult, x: int, y: int) -> bool:
    if not _inside(width=result.width, height=result.height, x=x, y=y):
        return True
    return not result.forest_mask[y][x]


def _near_map_border(*, width: int, height: int, x: int, y: int, margin: int) -> bool:
    return x < margin or y < margin or x >= width - margin or y >= height - margin


def _near_context(
    *,
    terrain_rows: list[list[str]],
    x: int,
    y: int,
    radius: int,
) -> dict[str, bool]:
    height = len(terrain_rows)
    width = len(terrain_rows[0]) if height else 0
    result = {"road": False, "ruins": False, "water": False}
    for ny in range(max(0, y - radius), min(height, y + radius + 1)):
        for nx in range(max(0, x - radius), min(width, x + radius + 1)):
            terrain = terrain_rows[ny][nx]
            if _is_road_terrain(terrain):
                result["road"] = True
            if _is_ruins_terrain(terrain):
                result["ruins"] = True
            if _is_water_terrain(terrain):
                result["water"] = True
    return result


def _is_road_terrain(value: str) -> bool:
    normalized = value.lower()
    return "road" in normalized or "path" in normalized or normalized == "bridge"


def _is_ruins_terrain(value: str) -> bool:
    normalized = value.lower()
    return "ruin" in normalized or "wall" in normalized


def _is_water_terrain(value: str) -> bool:
    normalized = value.lower()
    return "water" in normalized or "swamp" in normalized or "mud" in normalized


def _overlay_density_for_condition(*, condition: str, band: str, variant: str) -> float:
    if variant == "canopy_fill":
        return _canopy_fill_density_for_condition(condition=condition, band=band)
    if condition == "map_border_guard":
        return 0.22
    if condition in {"forest_isolated_single", "small_forest_island"}:
        return 0.50
    if condition.startswith("forest_thin_strip"):
        return 0.40
    if condition.startswith("forest_near_"):
        return 0.30
    if condition.startswith("outer_corner"):
        return 0.36
    if condition.startswith("edge_"):
        return 0.42
    if band == "deep":
        return 0.20
    if band == "interior":
        return 0.30
    return 0.38


def _canopy_fill_density_for_condition(*, condition: str, band: str) -> float:
    if condition == "map_border_guard":
        return 0.24
    if condition in {"forest_isolated_single", "small_forest_island"}:
        return 0.62
    if condition.startswith("forest_thin_strip"):
        return 0.56
    if condition.startswith("forest_near_"):
        return 0.44
    if condition.startswith("outer_corner"):
        return 0.56
    if condition.startswith("edge_"):
        return 0.58
    if band == "deep":
        return 0.58
    if band == "interior":
        return 0.52
    return 0.46


def _anchor_role_for_condition(*, condition: str, band: str, x: int, y: int, seed: int) -> str:
    value = _stable_noise(x=x, y=y, salt=257, seed=seed)
    if condition == "map_border_guard":
        return "guard_small" if value < 0.72 else "guard_filler"
    if condition in {"forest_isolated_single", "small_forest_island"}:
        return "island_group" if value < 0.55 else "young_tree"
    if condition.startswith("forest_thin_strip"):
        return "thin_strip" if value < 0.70 else "small_filler"
    if condition == "forest_near_road":
        return "roadside" if value < 0.70 else "edge_bush"
    if condition == "forest_near_ruins":
        return "ruin_overgrowth" if value < 0.72 else "young_tree"
    if condition == "forest_near_water":
        return "wet_edge" if value < 0.72 else "edge_bush"
    if condition.startswith("outer_corner"):
        return "corner" if value < 0.62 else "edge_bush"
    if condition.startswith("edge_front"):
        return "front_edge" if value < 0.68 else "edge_bush"
    if condition.startswith("edge_back"):
        return "back_edge" if value < 0.68 else "young_tree"
    if condition.startswith("edge_side"):
        return "side_edge" if value < 0.68 else "edge_bush"
    if band == "deep":
        return "deep_cluster" if value < 0.82 else "tall_tree"
    if band == "interior":
        return "mid_cluster" if value < 0.56 else "mid_tree"
    return "edge_bush" if value < 0.55 else "young_tree"


def _candidate_assets_for_condition(
    *,
    condition: str,
    role: str,
    band: str,
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    x: int,
    y: int,
    seed: int,
) -> tuple[ForestMassAsset, ...]:
    """Build a deterministic candidate list for a forest condition."""
    pools = _asset_pools_for_condition(condition=condition, role=role, band=band)
    candidates: list[ForestMassAsset] = []
    seen: set[str] = set()
    for keys in pools:
        for asset in _catalog_get(asset_catalog, keys):
            if asset.asset_id in seen:
                continue
            seen.add(asset.asset_id)
            candidates.append(asset)
    if not candidates:
        return ()
    return tuple(
        sorted(
            candidates,
            key=lambda asset: _asset_order_key(asset=asset, x=x, y=y, seed=seed),
        )
    )


def _asset_order_key(*, asset: ForestMassAsset, x: int, y: int, seed: int) -> tuple[float, str]:
    salt = 571 + sum(ord(ch) for ch in asset.asset_id)
    return (_stable_noise(x=x, y=y, salt=salt, seed=seed), asset.asset_id)


def _asset_policy_allowed(*, asset: ForestMassAsset, condition: str, band: str) -> bool:
    """Reject visually risky assets before footprint validation."""
    width = asset.image.width
    height = asset.image.height
    if condition == "map_border_guard":
        return width <= 72 and height <= 44 and asset.category not in {"deep", "ground", "shadows"}
    if condition in {"forest_isolated_single", "small_forest_island"}:
        return width <= 76 and height <= 62 and asset.category not in {"deep", "ground", "shadows"}
    if condition.startswith("forest_thin_strip"):
        return width <= 86 and height <= 86 and asset.category not in {"deep", "ground", "shadows"}
    if condition.startswith("forest_near_"):
        return width <= 54 and height <= 44 and asset.category not in {"deep", "ground", "shadows"}
    if condition.startswith("outer_corner"):
        return width <= 64 and height <= 64 and asset.category not in {"deep", "ground", "shadows"}
    if condition.startswith("edge_"):
        return width <= 76 and height <= 76 and asset.category not in {"deep", "ground", "shadows"}
    if band == "interior":
        return width <= 76 and height <= 72 and asset.category not in {"ground", "shadows"}
    return asset.category not in {"ground", "shadows"}


def _sprite_footprint_allowed(
    *,
    result: ForestMassExperimentResult,
    terrain_rows: list[list[str]],
    condition: str,
    band: str,
    x: int,
    y: int,
    width: int,
    height: int,
    tile_size_px: int,
) -> bool:
    """Validate the lower sprite footprint against forest and forbidden terrain."""
    samples = _sprite_footprint_samples(
        x=x,
        y=y,
        width=width,
        height=height,
        tile_size_px=tile_size_px,
    )
    if not samples:
        return True
    forest_count = 0
    forbidden_count = 0
    valid_count = 0
    for tx, ty in samples:
        if not _inside(width=result.width, height=result.height, x=tx, y=ty):
            continue
        valid_count += 1
        if result.forest_mask[ty][tx]:
            forest_count += 1
            continue
        terrain = terrain_rows[ty][tx]
        if _is_road_terrain(terrain) or _is_ruins_terrain(terrain) or _is_water_terrain(terrain):
            forbidden_count += 1
    if valid_count == 0:
        return True
    forest_ratio = forest_count / valid_count
    forbidden_ratio = forbidden_count / valid_count
    return (
        forest_ratio >= _required_footprint_forest_ratio(condition=condition, band=band)
        and forbidden_ratio <= _allowed_footprint_forbidden_ratio(condition=condition)
    )


def _sprite_footprint_samples(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    tile_size_px: int,
) -> tuple[tuple[int, int], ...]:
    left = x + int(width * 0.18)
    right = x + int(width * 0.82)
    top = y + int(height * 0.62)
    bottom = y + int(height * 0.94)
    samples: list[tuple[int, int]] = []
    step = max(1, tile_size_px // 2)
    for py in range(top, max(top + 1, bottom + 1), step):
        for px in range(left, max(left + 1, right + 1), step):
            samples.append((px // tile_size_px, py // tile_size_px))
    if not samples:
        samples.append(((x + width // 2) // tile_size_px, (y + height - 1) // tile_size_px))
    return tuple(dict.fromkeys(samples))


def _required_footprint_forest_ratio(*, condition: str, band: str) -> float:
    if condition == "map_border_guard":
        return 0.20
    if condition.startswith("forest_near_"):
        return 0.35
    if condition.startswith("outer_corner") or condition.startswith("edge_"):
        return 0.42
    if condition.startswith("forest_thin_strip"):
        return 0.38
    if condition in {"forest_isolated_single", "small_forest_island"}:
        return 0.34
    if band == "deep":
        return 0.72
    if band == "interior":
        return 0.58
    return 0.42


def _allowed_footprint_forbidden_ratio(*, condition: str) -> float:
    if condition == "forest_near_road":
        return 0.12
    if condition in {"forest_near_ruins", "forest_near_water"}:
        return 0.08
    if condition.startswith("edge_") or condition.startswith("outer_corner"):
        return 0.05
    return 0.0


def _asset_for_condition(
    *,
    condition: str,
    role: str,
    band: str,
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    x: int,
    y: int,
    seed: int,
) -> ForestMassAsset | None:
    pools = _asset_pools_for_condition(condition=condition, role=role, band=band)
    for salt_offset, keys in enumerate(pools):
        assets = _catalog_get(asset_catalog, keys)
        if assets:
            return _pick_asset(
                assets=assets,
                x=x,
                y=y,
                salt=503 + salt_offset * 17,
                seed=seed,
            )
    return None


def _asset_pools_for_condition(*, condition: str, role: str, band: str) -> tuple[tuple[str, ...], ...]:
    del role
    if condition == "map_border_guard":
        return (
            ("family:edge_cut_safe_small", "family:single_small_pine", "family:small_round_bush"),
            ("category:guards", "category:bushes"),
        )
    if condition == "forest_isolated_single":
        return (
            ("family:single_small_pine", "family:young_pine", "family:round_bush"),
            ("category:trees", "category:bushes"),
        )
    if condition == "small_forest_island":
        return (
            ("family:island_group_small", "family:single_small_pine", "family:young_pine"),
            ("category:islands", "category:trees", "category:bushes"),
        )
    if condition == "forest_thin_strip_ew":
        return (
            ("family:thin_strip_horizontal_pine", "family:front_low_bush", "family:small_canopy_filler"),
            ("category:thin_strips", "category:fillers"),
        )
    if condition == "forest_thin_strip_ns":
        return (
            ("family:thin_strip_vertical_pine", "family:side_bush", "family:small_canopy_filler"),
            ("category:thin_strips", "category:fillers"),
        )
    if condition == "forest_near_road":
        return (
            ("family:roadside_bush", "family:roadside_young_pine", "family:front_low_bush"),
            ("category:context_road", "category:edge_front"),
        )
    if condition == "forest_near_ruins":
        return (
            ("family:overgrown_ruin_bush", "family:young_pine_ruin_edge", "family:small_dark_canopy"),
            ("category:context_ruins", "category:context_ruins"),
        )
    if condition == "forest_near_water":
        return (
            ("family:wet_edge_bush", "family:dark_low_tree", "family:dead_small_tree_optional"),
            ("category:context_water", "category:bushes"),
        )
    if condition == "outer_corner_es":
        return (("family:corner_front_right", "family:front_canopy_low", "family:edge_side_right"), ("category:corners",))
    if condition == "outer_corner_sw":
        return (("family:corner_front_left", "family:front_canopy_low", "family:edge_side_left"), ("category:corners",))
    if condition == "outer_corner_ne":
        return (("family:corner_back_right", "family:back_canopy", "family:edge_side_right"), ("category:corners",))
    if condition == "outer_corner_nw":
        return (("family:corner_back_left", "family:back_canopy", "family:edge_side_left"), ("category:corners",))
    if condition == "edge_front_south":
        return (("family:front_canopy_low", "family:edge_front_low_pine", "family:front_low_bush"), ("category:edge_front",))
    if condition == "edge_back_north":
        return (("family:back_canopy", "family:edge_back_pine", "family:young_pine"), ("category:edge_back", "category:trees"))
    if condition == "edge_side_west":
        return (("family:edge_side_left", "family:edge_side_left_pine", "family:side_left_bush"), ("category:edge_side",))
    if condition == "edge_side_east":
        return (("family:edge_side_right", "family:edge_side_right_pine", "family:side_right_bush"), ("category:edge_side",))
    if band == "deep":
        return (
            ("family:deep_canopy_cluster_64_96", "family:deep_canopy_cluster_128"),
            ("category:deep", "family:occasional_tall_pine"),
        )
    if band == "interior":
        return (
            ("family:mid_canopy_cluster_48_64", "family:mid_pine", "family:low_edge_canopy"),
            ("category:mid", "category:trees"),
        )
    return (
        ("family:edge_bush", "family:young_pine", "family:bush_gap_filler"),
        ("category:bushes", "category:trees", "category:fillers"),
    )


def _anchor_pixel_for_condition(
    *,
    x: int,
    y: int,
    condition: str,
    band: str,
    tile_size_px: int,
    seed: int,
) -> tuple[int, int]:
    jitter_x_scale = 0.52 if condition.startswith("edge_") or condition.startswith("outer_") else 0.78
    jitter_y_scale = 0.34 if condition.startswith("edge_front") else 0.55
    if condition == "map_border_guard":
        jitter_x_scale = 0.28
        jitter_y_scale = 0.22
    jitter_x = (_stable_noise(x=x, y=y, salt=223, seed=seed) - 0.5) * jitter_x_scale
    jitter_y = (_stable_noise(x=x, y=y, salt=227, seed=seed) - 0.5) * jitter_y_scale
    y_bias = 0.94 if band == "edge" else 0.98
    return (
        int((x + 0.5 + jitter_x) * tile_size_px),
        int((y + y_bias + jitter_y) * tile_size_px),
    )


def _sprite_bounds_allowed(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    image_size: tuple[int, int],
    condition: str,
) -> bool:
    image_width, image_height = image_size
    if x < 0 or y < 0 or x + width > image_width or y + height > image_height:
        return False
    if condition == "map_border_guard":
        return width <= 64 and height <= 72
    return True


def _draw_anchor_shadows(
    *,
    image: Image.Image,
    anchors: list[ForestMassAnchor],
    asset_catalog: dict[str, tuple[ForestMassAsset, ...]],
    tile_size_px: int,
    variant: str,
) -> None:
    shadows = _catalog_get(asset_catalog, ["category:shadows", "zone:shadow"])
    if not shadows:
        return
    for index, anchor in enumerate(anchors):
        if anchor.role in {"edge_bush", "guard_small"} and index % 2 == 1:
            continue
        shadow = _shadow_asset_for_anchor(anchor=anchor, shadows=shadows)
        shadow_image = _scaled_asset_image(shadow.image, tile_size_px=tile_size_px)
        opacity = _shadow_opacity_for_anchor(anchor=anchor, variant=variant)
        shadow_image = _with_opacity(shadow_image, opacity)
        draw_x, draw_y = _asset_draw_position(
            asset=shadow,
            asset_image=shadow_image,
            x_px=anchor.x_px,
            y_px=anchor.y_px,
            fallback_mode="center",
        )
        _alpha_composite_clipped(base=image, overlay=shadow_image, x=draw_x, y=draw_y)


def _shadow_opacity_for_anchor(*, anchor: ForestMassAnchor, variant: str) -> float:
    """Resolve shadow opacity for the overlay variant and forest band."""
    if variant == "canopy_fill":
        if anchor.condition.startswith("edge_") or anchor.condition.startswith("outer_corner"):
            return 0.16
        if anchor.condition.startswith("forest_near_"):
            return 0.14
        if anchor.band == "deep":
            return 0.20
        if anchor.band == "interior":
            return 0.17
        return 0.14
    if variant == "placement_fix":
        if anchor.condition.startswith("edge_") or anchor.condition.startswith("outer_corner"):
            return 0.18
        if anchor.condition.startswith("forest_near_"):
            return 0.16
        if anchor.band == "deep":
            return 0.30
        if anchor.band == "interior":
            return 0.23
        return 0.16
    return 0.30 if anchor.band == "edge" else 0.45 if anchor.band == "interior" else 0.58


def _draw_anchor_sprites(
    *,
    image: Image.Image,
    anchors: list[ForestMassAnchor],
    tile_size_px: int,
) -> None:
    for anchor in anchors:
        asset_image = _scaled_asset_image(anchor.asset.image, tile_size_px=tile_size_px)
        draw_x, draw_y = _asset_draw_position(
            asset=anchor.asset,
            asset_image=asset_image,
            x_px=anchor.x_px,
            y_px=anchor.y_px,
            fallback_mode="sprite",
        )
        _alpha_composite_clipped(base=image, overlay=asset_image, x=draw_x, y=draw_y)


def _asset_draw_position(
    *,
    asset: ForestMassAsset,
    asset_image: Image.Image,
    x_px: int,
    y_px: int,
    fallback_mode: str,
) -> tuple[int, int]:
    scale_x = asset_image.width / max(1, asset.image.width)
    scale_y = asset_image.height / max(1, asset.image.height)
    if asset.anchor_x is not None and asset.anchor_y is not None:
        return (
            int(x_px - asset.anchor_x * scale_x),
            int(y_px - asset.anchor_y * scale_y),
        )
    if fallback_mode == "center":
        return (x_px - asset_image.width // 2, y_px - asset_image.height // 2)
    return (x_px - asset_image.width // 2, y_px - asset_image.height)


def _forest_mass_compare_label(variant: str) -> str:
    """Return a short label for the forest mass comparison image."""
    if variant == "canopy_fill":
        return "forest mass canopy fill"
    if variant == "placement_fix":
        return "forest mass placement fix"
    if variant == "clean":
        return "forest mass clean"
    return "forest mass overlay"


def _save_forest_mass_compare(
    *,
    before: Image.Image,
    after: Image.Image,
    output_path: Path,
    label: str,
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
    draw.text((before_preview.width + 6, 4), label, fill=(235, 235, 220, 255))
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
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        return _load_manifest_forest_mass_assets(root=root, manifest_path=manifest_path)
    return _load_legacy_forest_mass_assets(root=root)


def _load_manifest_forest_mass_assets(
    *,
    root: Path,
    manifest_path: Path,
) -> dict[str, tuple[ForestMassAsset, ...]]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raw_assets = []
    catalog: dict[str, list[ForestMassAsset]] = {"all": []}
    for item in raw_assets:
        if not isinstance(item, dict):
            continue
        rel_path_value = item.get("path")
        if not isinstance(rel_path_value, str) or not rel_path_value:
            continue
        path = root / rel_path_value
        if not path.exists() or path.suffix.lower() != ".png":
            continue
        parts = Path(rel_path_value).parts
        category = parts[0] if parts else "misc"
        family = _string_value(item.get("family"), path.stem)
        role_hint = _string_value(item.get("role"), "")
        zone = _string_value(item.get("zone"), category)
        asset = ForestMassAsset(
            asset_id=f"{category}.{path.stem}",
            category=category,
            path=path,
            image=Image.open(path).convert("RGBA"),
            family=family,
            role_hint=role_hint,
            zone=zone,
            anchor_x=_optional_int(item.get("anchor_x")),
            anchor_y=_optional_int(item.get("anchor_y")),
        )
        _catalog_append(catalog, "all", asset)
        _catalog_append(catalog, f"category:{category}", asset)
        _catalog_append(catalog, f"family:{family}", asset)
        _catalog_append(catalog, f"zone:{zone}", asset)
    return {key: tuple(value) for key, value in catalog.items()}


def _load_legacy_forest_mass_assets(root: Path) -> dict[str, tuple[ForestMassAsset, ...]]:
    catalog: dict[str, list[ForestMassAsset]] = {"all": []}
    for category in ("clusters", "trees", "edge", "ground", "shadows"):
        category_dir = root / category
        for path in sorted(category_dir.glob("*.png")):
            asset = ForestMassAsset(
                asset_id=f"{category}.{path.stem}",
                category=category,
                path=path,
                image=Image.open(path).convert("RGBA"),
                family=path.stem,
                role_hint="",
                zone=category,
                anchor_x=None,
                anchor_y=None,
            )
            _catalog_append(catalog, "all", asset)
            _catalog_append(catalog, f"category:{category}", asset)
            _catalog_append(catalog, f"family:{path.stem}", asset)
            _catalog_append(catalog, f"zone:{category}", asset)
    return {key: tuple(value) for key, value in catalog.items()}


def _forest_mass_asset_root(profile: VisualProfile) -> Path:
    asset_root_value = profile.assets_manifest.get("asset_root")
    if isinstance(asset_root_value, str) and asset_root_value:
        asset_root = (profile.root_dir / asset_root_value).resolve()
    else:
        asset_root = profile.root_dir.resolve()
    v2_root = asset_root / "forest_mass_v2"
    if v2_root.exists():
        return v2_root
    return asset_root / "forest_mass"


def _catalog_append(
    catalog: dict[str, list[ForestMassAsset]],
    key: str,
    asset: ForestMassAsset,
) -> None:
    catalog.setdefault(key, []).append(asset)


def _catalog_get(
    catalog: dict[str, tuple[ForestMassAsset, ...]],
    keys: list[str] | tuple[str, ...],
) -> tuple[ForestMassAsset, ...]:
    seen: set[str] = set()
    result: list[ForestMassAsset] = []
    for key in keys:
        for asset in catalog.get(key, ()):
            if asset.asset_id in seen:
                continue
            seen.add(asset.asset_id)
            result.append(asset)
    return tuple(result)


def _catalog_count_by_key(
    catalog: dict[str, tuple[ForestMassAsset, ...]],
    *,
    prefix: str,
    limit: int | None = None,
) -> dict[str, int]:
    items = [
        (key.removeprefix(prefix), len(value))
        for key, value in catalog.items()
        if key.startswith(prefix)
    ]
    items.sort(key=lambda item: (-item[1], item[0]))
    if limit is not None:
        items = items[:limit]
    return dict(items)


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


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
    if anchor.condition == "forest_near_road":
        preferred = _filter_asset_families(shadows, ("roadside_shadow", "contact_shadow_front"))
    elif anchor.condition.startswith("edge_side"):
        preferred = _filter_asset_families(shadows, ("side_shadow",))
    elif anchor.condition.startswith("edge_back"):
        preferred = _filter_asset_families(shadows, ("soft_back_shadow",))
    elif anchor.role in {"deep_cluster", "mid_cluster"}:
        preferred = _filter_asset_families(shadows, ("deep_shadow_blob", "contact_shadow_front"))
    else:
        preferred = _filter_asset_families(shadows, ("contact_shadow_front", "small_contact_shadow"))
    if not preferred:
        preferred = shadows
    index = sum(ord(ch) for ch in anchor.asset.asset_id) % len(preferred)
    return preferred[index]


def _filter_asset_families(
    assets: tuple[ForestMassAsset, ...],
    families: tuple[str, ...],
) -> tuple[ForestMassAsset, ...]:
    return tuple(asset for asset in assets if asset.family in families)


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
