from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from top_down_worldgen.constants import OBJECTIVE_PROFILES
from top_down_worldgen.logging_utils import timed_stage


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SpawnSelectionConfig:
    """Configuration for objective-aware spawn selection."""

    clear_map_default_per_zone: int = 1
    clear_map_central_per_zone: int = 2
    timed_default_per_zone: int = 0
    timed_key_zone_per_zone: int = 1
    survival_default_per_zone: int = 1
    survival_central_per_zone: int = 4
    survival_goal_per_zone: int = 2


class ObjectiveProfileSelector:
    """Selects runtime enemy spawns according to objective profile."""

    def __init__(self, objective_profile: str, config: SpawnSelectionConfig | None = None) -> None:
        """Initialize selector.

        Args:
            objective_profile: Objective profile name.
            config: Optional selection config.

        Raises:
            ValueError: If objective profile is unknown.
        """
        if objective_profile not in OBJECTIVE_PROFILES:
            raise ValueError(
                f"Unknown objective_profile={objective_profile!r}. "
                f"Expected one of: {sorted(OBJECTIVE_PROFILES)}"
            )
        self._objective_profile = objective_profile
        self._config = config or SpawnSelectionConfig()

    def apply(
        self,
        runtime_data: dict[str, Any],
        debug_data: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Apply objective profile to enemy spawns.

        Args:
            runtime_data: Runtime tactical data.
            debug_data: Debug tactical data.

        Returns:
            Updated runtime and debug data.
        """
        with timed_stage(
            LOGGER,
            "ObjectiveProfileSelector.apply",
            objective_profile=self._objective_profile,
        ) as metrics:
            candidates = [
                spawn for spawn in debug_data.get("enemy_spawn_zones", [])
                if isinstance(spawn, dict)
            ]
            selected = self._select_spawns(candidates)
            runtime_updated = dict(runtime_data)
            debug_updated = dict(debug_data)

            debug_updated["enemy_spawn_candidates"] = candidates
            debug_updated["enemy_spawn_zones"] = selected
            runtime_updated["enemy_spawn_zones"] = self._runtime_spawns(selected)

            info = {
                "objective_profile": self._objective_profile,
                "candidate_spawn_count": len(candidates),
                "selected_spawn_count": len(selected),
                "spawn_selection_policy": self._policy_name(),
            }
            runtime_updated["objective"] = info
            debug_updated["objective"] = info
            metrics.update(info)
            return runtime_updated, debug_updated

    def _select_spawns(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for spawn in candidates:
            grouped.setdefault(str(spawn.get("zone_id", "")), []).append(spawn)

        selected: list[dict[str, Any]] = []
        for _, spawns in grouped.items():
            spawns.sort(key=self._spawn_sort_key)
            zone_type = str(spawns[0].get("zone_type", "unknown")) if spawns else "unknown"
            limit = self._limit_for_zone(zone_type)

            for spawn in spawns[:limit]:
                rewritten = dict(spawn)
                rewritten["spawn_type"] = self._spawn_type(zone_type)
                rewritten["respawn_allowed"] = self._objective_profile == "survival"
                rewritten["objective_profile"] = self._objective_profile
                rewritten["recommended_squad_size"] = self._squad_size(zone_type)
                selected.append(rewritten)

        selected.sort(key=lambda item: (str(item.get("zone_id", "")), -float(item.get("quality", 0.0))))
        for index, spawn in enumerate(selected):
            spawn["id"] = f"spawn_{index}"
        return selected

    def _limit_for_zone(self, zone_type: str) -> int:
        if zone_type == "safe_start":
            return 0
        if self._objective_profile == "clear_map":
            if zone_type == "central_ruins_combat":
                return self._config.clear_map_central_per_zone
            return self._config.clear_map_default_per_zone
        if self._objective_profile == "timed_breakthrough":
            if zone_type in {"central_ruins_combat", "goal_encounter"}:
                return self._config.timed_key_zone_per_zone
            if zone_type == "forest_ambush":
                return 1
            return self._config.timed_default_per_zone
        if self._objective_profile == "survival":
            if zone_type == "central_ruins_combat":
                return self._config.survival_central_per_zone
            if zone_type == "goal_encounter":
                return self._config.survival_goal_per_zone
            return self._config.survival_default_per_zone
        return 0

    def _spawn_type(self, zone_type: str) -> str:
        if self._objective_profile == "survival":
            return "wave_entry"
        if self._objective_profile == "timed_breakthrough":
            return "blocking_squad"
        if zone_type == "forest_ambush":
            return "ambush_squad"
        return "initial_squad"

    def _squad_size(self, zone_type: str) -> int:
        if self._objective_profile == "survival":
            return 4 if zone_type == "central_ruins_combat" else 3
        if self._objective_profile == "timed_breakthrough":
            return 2
        return 4 if zone_type == "central_ruins_combat" else 3

    def _policy_name(self) -> str:
        return {
            "clear_map": "one_initial_spawn_per_combat_zone",
            "timed_breakthrough": "key_route_pressure_spawns_only",
            "survival": "wave_spawn_entries",
        }[self._objective_profile]

    @staticmethod
    def _runtime_spawns(spawns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": spawn.get("id"),
                "zone_id": spawn.get("zone_id"),
                "zone_type": spawn.get("zone_type"),
                "position": spawn.get("position"),
                "preferred_roles": spawn.get("preferred_roles", []),
                "spawn_type": spawn.get("spawn_type"),
                "respawn_allowed": spawn.get("respawn_allowed"),
                "recommended_squad_size": spawn.get("recommended_squad_size"),
                "quality": spawn.get("quality"),
            }
            for spawn in spawns
        ]

    @staticmethod
    def _spawn_sort_key(spawn: dict[str, Any]) -> tuple[float, int, int]:
        position = spawn.get("position", [999999, 999999])
        if not isinstance(position, list) or len(position) != 2:
            position = [999999, 999999]
        return (-float(spawn.get("quality", 0.0)), int(position[1]), int(position[0]))
