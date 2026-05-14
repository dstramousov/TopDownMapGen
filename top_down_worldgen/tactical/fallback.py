from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FallbackConfig:
    """Configuration for fallback position generation."""

    max_fallbacks_per_zone: int = 3
    min_cover_quality: float = 0.55
    min_distance_from_zone_center: int = 5
    min_distance_from_start: int = 24
    flank_bonus_distance: int = 8
    entrance_bonus_distance: int = 6


class FallbackPositionBuilder:
    """Builds fallback positions from optimized tactical data."""

    def __init__(self, config: FallbackConfig | None = None) -> None:
        """Initialize fallback builder.

        Args:
            config: Optional fallback config.
        """
        self._config = config or FallbackConfig()

    def add(
        self,
        runtime_data: dict[str, Any],
        debug_data: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Add fallback positions.

        Args:
            runtime_data: Runtime tactical data.
            debug_data: Debug tactical data.

        Returns:
            Updated runtime and debug data.
        """
        fallbacks = self._build(debug_data)
        runtime_updated = dict(runtime_data)
        debug_updated = dict(debug_data)
        runtime_updated["fallback_positions"] = self._runtime_fallbacks(fallbacks)
        debug_updated["fallback_positions"] = fallbacks
        info = {
            "max_fallbacks_per_zone": self._config.max_fallbacks_per_zone,
            "min_cover_quality": self._config.min_cover_quality,
            "fallback_count": len(fallbacks),
        }
        runtime_updated["fallback_generation"] = info
        debug_updated["fallback_generation"] = info
        return runtime_updated, debug_updated

    def _build(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        cover_by_id = {
            str(point.get("id")): point
            for point in data.get("cover_points", [])
            if isinstance(point, dict)
        }
        zones = [
            zone for zone in data.get("combat_zones", [])
            if isinstance(zone, dict)
            and zone.get("enemy_spawns_allowed", False)
            and zone.get("type") != "safe_start"
        ]
        start = self._find_start(data)
        flank_routes = [route for route in data.get("flank_routes", []) if isinstance(route, dict)]
        fallbacks: list[dict[str, Any]] = []
        fallback_id = 0

        for zone in zones:
            zone_id = str(zone.get("id", ""))
            zone_center = self._point(zone.get("center"))
            if zone_center is None:
                continue

            candidates: list[dict[str, Any]] = []
            for cover_id in map(str, zone.get("cover_point_ids", [])):
                cover = cover_by_id.get(cover_id)
                if cover is None:
                    continue
                position = self._point(cover.get("position"))
                if position is None:
                    continue

                quality = float(cover.get("quality", 0.0))
                if quality < self._config.min_cover_quality:
                    continue
                if self._manhattan(position, zone_center) < self._config.min_distance_from_zone_center:
                    continue
                if start is not None and self._manhattan(position, start) < self._config.min_distance_from_start:
                    continue

                score, linked_routes, reason = self._score(position, cover, zone, flank_routes)
                candidates.append(
                    {
                        "position": position,
                        "cover": cover,
                        "score": score,
                        "linked_flank_routes": linked_routes,
                        "reason": reason,
                    },
                )

            candidates.sort(key=lambda item: (-float(item["score"]), item["position"][1], item["position"][0]))
            used: set[tuple[int, int]] = set()
            selected = 0

            for candidate in candidates:
                position = candidate["position"]
                if any(self._manhattan(position, existing) < 5 for existing in used):
                    continue
                cover = candidate["cover"]
                fallbacks.append(
                    {
                        "id": f"fallback_{fallback_id}",
                        "zone_id": zone_id,
                        "zone_type": str(zone.get("type", "unknown")),
                        "position": [position[0], position[1]],
                        "cover_point_id": str(cover.get("id", "")),
                        "quality": round(float(candidate["score"]), 3),
                        "fallback_type": "covered_retreat",
                        "linked_flank_routes": candidate["linked_flank_routes"],
                        "preferred_roles": self._preferred_roles(str(zone.get("type", ""))),
                        "reason": candidate["reason"],
                    },
                )
                fallback_id += 1
                selected += 1
                used.add(position)
                if selected >= self._config.max_fallbacks_per_zone:
                    break

        return fallbacks

    def _score(
        self,
        position: tuple[int, int],
        cover: dict[str, Any],
        zone: dict[str, Any],
        flank_routes: list[dict[str, Any]],
    ) -> tuple[float, list[str], str]:
        score = float(cover.get("quality", 0.0))
        reasons = ["good_cover"]
        if str(cover.get("cover_type", "")) == "hard":
            score += 0.25
            reasons.append("hard_cover")

        route_ids: list[str] = []
        for route in flank_routes:
            waypoints = [self._point(item) for item in route.get("waypoints", [])]
            waypoints = [item for item in waypoints if item is not None]
            if any(self._manhattan(position, waypoint) <= self._config.flank_bonus_distance for waypoint in waypoints):
                route_ids.append(str(route.get("id", "")))
                score += 0.18
                reasons.append("near_flank_route")
                break

        entrances = [self._point(item) for item in zone.get("estimated_entrances", [])]
        entrances = [item for item in entrances if item is not None]
        if any(self._manhattan(position, entrance) <= self._config.entrance_bonus_distance for entrance in entrances):
            score += 0.12
            reasons.append("near_zone_exit")

        return min(1.5, score), route_ids[:3], "_".join(dict.fromkeys(reasons))

    @staticmethod
    def _runtime_fallbacks(fallbacks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": item.get("id"),
                "zone_id": item.get("zone_id"),
                "position": item.get("position"),
                "cover_point_id": item.get("cover_point_id"),
                "quality": item.get("quality"),
                "fallback_type": item.get("fallback_type"),
                "linked_flank_routes": item.get("linked_flank_routes", []),
                "preferred_roles": item.get("preferred_roles", []),
            }
            for item in fallbacks
        ]

    @staticmethod
    def _preferred_roles(zone_type: str) -> list[str]:
        if zone_type == "central_ruins_combat":
            return ["rifleman", "grenadier"]
        if zone_type == "forest_ambush":
            return ["flanker", "scout"]
        if zone_type == "goal_encounter":
            return ["rifleman", "defender"]
        return ["rifleman"]

    @staticmethod
    def _find_start(data: dict[str, Any]) -> tuple[int, int] | None:
        for zone in data.get("combat_zones", []):
            if isinstance(zone, dict) and zone.get("type") == "safe_start":
                return FallbackPositionBuilder._point(zone.get("center"))
        return None

    @staticmethod
    def _point(value: Any) -> tuple[int, int] | None:
        if not isinstance(value, list) or len(value) != 2:
            return None
        return int(value[0]), int(value[1])

    @staticmethod
    def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])
