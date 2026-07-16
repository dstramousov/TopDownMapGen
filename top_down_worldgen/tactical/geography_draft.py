from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GeographyDraftRegion:
    """Large deterministic landform region available before terrain generation."""

    region_id: str
    kind: str
    center_x: float
    center_y: float
    radius_tiles: float
    strength: float
    angle_degrees: float
    base_elevation_score: float
    moisture_bias: float
    roughness: float
    priority: float


@dataclass(frozen=True, slots=True)
class GeographyDraft:
    """Continuous geography context built before terrain generation.

    The nested grids are treated as read-only pipeline data. They intentionally
    keep list storage because the elevation pipeline processes large maps and
    copying them into immutable tuples would add substantial memory overhead.
    """

    width: int
    height: int
    seed: int
    elevation_style: str
    elevation_scores: list[list[float]]
    moisture_scores: list[list[float]]
    macro_regions: tuple[GeographyDraftRegion, ...]
    dominant_region_rows: list[list[int]]
    region_edges: tuple[tuple[int, int], ...]

    def validate_for(
        self,
        *,
        width: int,
        height: int,
        seed: int,
        elevation_style: str,
    ) -> None:
        """Validate that the draft matches a requested generation run.

        Args:
            width: Requested map width in tiles.
            height: Requested map height in tiles.
            seed: Resolved deterministic world seed.
            elevation_style: Sanitized elevation style name.

        Raises:
            ValueError: If the draft was built for another map or profile.
        """
        expected = (width, height, seed, elevation_style)
        actual = (self.width, self.height, self.seed, self.elevation_style)
        if actual != expected:
            raise ValueError(
                "GeographyDraft does not match generation request: "
                f"expected={expected!r}, actual={actual!r}"
            )


@dataclass(frozen=True, slots=True)
class NaturalGeographyModel:
    """Final natural geography generated before terrain placement.

    The model contains the integer natural elevation grid and its local slope
    grid before terrain-specific bias, route alignment, structural elevation,
    and traversal repair are applied.
    """

    width: int
    height: int
    seed: int
    elevation_style: str
    elevation_rows: list[list[int]]
    slope_rows: list[list[int]]
    draft: GeographyDraft

    def validate_for(
        self,
        *,
        width: int,
        height: int,
        seed: int,
        elevation_style: str,
    ) -> None:
        """Validate that the model matches a requested generation run.

        Args:
            width: Requested map width in tiles.
            height: Requested map height in tiles.
            seed: Resolved deterministic world seed.
            elevation_style: Sanitized elevation style name.

        Raises:
            ValueError: If the model was built for another map or profile.
        """
        expected = (width, height, seed, elevation_style)
        actual = (self.width, self.height, self.seed, self.elevation_style)
        if actual != expected:
            raise ValueError(
                "NaturalGeographyModel does not match generation request: "
                f"expected={expected!r}, actual={actual!r}"
            )
        self.draft.validate_for(
            width=width,
            height=height,
            seed=seed,
            elevation_style=elevation_style,
        )
