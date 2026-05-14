from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OptimizerConfig:
    """Configuration for tactical data optimization."""

    max_global_cover_points: int = 480
    max_cover_points_per_zone: int = 16
    min_cover_quality: float = 0.35
    max_total_flank_routes: int = 32
    max_flank_routes_per_zone: int = 3


class TacticalOptimizer:
    """Optimizes raw tactical metadata for runtime and debug usage."""

    def __init__(self, config: OptimizerConfig | None = None) -> None:
        """Initialize optimizer.

        Args:
            config: Optional optimizer configuration.
        """
        self._config = config or OptimizerConfig()

    def optimize(self, raw_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Optimize raw tactical data.

        Args:
            raw_data: Raw tactical data from legacy engine.

        Returns:
            Runtime and debug tactical maps.
        """
        selected_cover = self._select_cover_points(raw_data)
        selected_cover_ids = {str(point.get("id")) for point in selected_cover}

        debug_data = dict(raw_data)
        debug_data["cover_points"] = selected_cover
        debug_data["combat_zones"] = self._rewrite_combat_zones(
            raw_data.get("combat_zones", []),
            selected_cover_ids,
        )
        debug_data["flank_routes"] = self._limit_flank_routes(raw_data.get("flank_routes", []))
        debug_data["enemy_spawn_zones"] = self._filter_enemy_spawns(
            raw_data.get("enemy_spawn_zones", []),
            selected_cover_ids,
        )
        debug_data["optimization"] = self._summary(raw_data, debug_data, selected_cover)
        debug_data["version"] = "0.19-debug-optimized"

        runtime_data = self._runtime_data(debug_data)
        return runtime_data, debug_data

    def _select_cover_points(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        cover_points = [
            point for point in raw_data.get("cover_points", [])
            if isinstance(point, dict)
            and float(point.get("quality", 0.0)) >= self._config.min_cover_quality
        ]
        cover_by_id = {str(point.get("id")): point for point in cover_points}
        selected: dict[str, dict[str, Any]] = {}

        for zone in raw_data.get("combat_zones", []):
            if not isinstance(zone, dict):
                continue
            zone_points = [
                cover_by_id[cover_id]
                for cover_id in map(str, zone.get("cover_point_ids", []))
                if cover_id in cover_by_id
            ]
            zone_points.sort(key=self._cover_sort_key)
            for point in zone_points[: self._config.max_cover_points_per_zone]:
                selected[str(point.get("id"))] = point

        cover_points.sort(key=self._cover_sort_key)
        for point in cover_points:
            selected[str(point.get("id"))] = point
            if len(selected) >= self._config.max_global_cover_points:
                break

        output = list(selected.values())
        output.sort(key=self._cover_sort_key)
        return output[: self._config.max_global_cover_points]

    def _rewrite_combat_zones(self, zones: Any, selected_cover_ids: set[str]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for zone in zones:
            if not isinstance(zone, dict):
                continue
            rewritten = dict(zone)
            cover_ids = [
                str(cover_id)
                for cover_id in rewritten.get("cover_point_ids", [])
                if str(cover_id) in selected_cover_ids
            ]
            rewritten["cover_point_ids"] = cover_ids[: self._config.max_cover_points_per_zone]
            rewritten["cover_count"] = len(rewritten["cover_point_ids"])
            output.append(rewritten)
        return output

    def _limit_flank_routes(self, routes: Any) -> list[dict[str, Any]]:
        if not isinstance(routes, list):
            return []
        candidates = [route for route in routes if isinstance(route, dict)]
        candidates.sort(
            key=lambda route: (
                float(route.get("risk", 1.0)),
                float(route.get("cost", route.get("length", 999999))),
                -float(route.get("concealment", 0.0)),
            ),
        )

        selected: list[dict[str, Any]] = []
        per_zone_count: defaultdict[str, int] = defaultdict(int)

        for route in candidates:
            from_zone = str(route.get("from_zone", ""))
            to_zone = str(route.get("to_zone", ""))

            if per_zone_count[from_zone] >= self._config.max_flank_routes_per_zone:
                continue
            if per_zone_count[to_zone] >= self._config.max_flank_routes_per_zone:
                continue

            selected.append(route)
            per_zone_count[from_zone] += 1
            per_zone_count[to_zone] += 1

            if len(selected) >= self._config.max_total_flank_routes:
                break

        return selected

    @staticmethod
    def _filter_enemy_spawns(spawns: Any, selected_cover_ids: set[str]) -> list[dict[str, Any]]:
        if not isinstance(spawns, list):
            return []
        return [
            spawn for spawn in spawns
            if isinstance(spawn, dict)
            and str(spawn.get("cover_point_id", "")) in selected_cover_ids
        ]

    def _runtime_data(self, debug_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": "0.19-runtime",
            "map": debug_data.get("map", {}),
            "movement_costs": debug_data.get("movement_costs", {}),
            "combat_zones": [
                {
                    "id": zone.get("id"),
                    "type": zone.get("type"),
                    "center": zone.get("center"),
                    "radius": zone.get("radius"),
                    "difficulty": zone.get("difficulty"),
                    "enemy_spawns_allowed": zone.get("enemy_spawns_allowed"),
                    "cover_point_ids": zone.get("cover_point_ids", []),
                    "estimated_entrances": zone.get("estimated_entrances", []),
                    "openness": zone.get("openness"),
                }
                for zone in debug_data.get("combat_zones", [])
                if isinstance(zone, dict)
            ],
            "cover_points": [
                {
                    "id": point.get("id"),
                    "position": point.get("position"),
                    "quality": point.get("quality"),
                    "cover_type": point.get("cover_type"),
                }
                for point in debug_data.get("cover_points", [])
                if isinstance(point, dict)
            ],
            "choke_points": debug_data.get("choke_points", []),
            "flank_routes": [
                {
                    "id": route.get("id"),
                    "from_zone": route.get("from_zone"),
                    "to_zone": route.get("to_zone"),
                    "entry": route.get("entry"),
                    "exit": route.get("exit"),
                    "cost": route.get("cost"),
                    "risk": route.get("risk"),
                    "concealment": route.get("concealment"),
                    "waypoints": route.get("waypoints", []),
                }
                for route in debug_data.get("flank_routes", [])
                if isinstance(route, dict)
            ],
            "enemy_spawn_zones": debug_data.get("enemy_spawn_zones", []),
            "optimization": debug_data.get("optimization", {}),
        }

    def _summary(
        self,
        raw_data: dict[str, Any],
        debug_data: dict[str, Any],
        selected_cover: list[dict[str, Any]],
    ) -> dict[str, Any]:
        original_cover = len([point for point in raw_data.get("cover_points", []) if isinstance(point, dict)])
        original_routes = len([route for route in raw_data.get("flank_routes", []) if isinstance(route, dict)])
        return {
            "original_cover_points": original_cover,
            "selected_cover_points": len(selected_cover),
            "cover_reduction_ratio": round(1.0 - len(selected_cover) / max(1, original_cover), 3),
            "original_flank_routes": original_routes,
            "selected_flank_routes": len(debug_data.get("flank_routes", [])),
            "max_global_cover_points": self._config.max_global_cover_points,
            "max_cover_points_per_zone": self._config.max_cover_points_per_zone,
        }

    @staticmethod
    def _cover_sort_key(point: dict[str, Any]) -> tuple[float, int, int]:
        position = point.get("position", [999999, 999999])
        if not isinstance(position, list) or len(position) != 2:
            position = [999999, 999999]
        return (-float(point.get("quality", 0.0)), int(position[1]), int(position[0]))
