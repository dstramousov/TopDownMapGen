from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TraversalRules:
    """Shared movement rules for elevation-aware traversal."""

    max_natural_delta: int = 1
    cardinal_movement_only: bool = True

    def allows_step(
        self,
        current_level: int,
        next_level: int,
        *,
        transition_allowed: bool = False,
    ) -> bool:
        """Return whether one elevation step is traversable.

        Args:
            current_level: Elevation at the source tile.
            next_level: Elevation at the target tile.
            transition_allowed: Whether an explicit structural transition exists.

        Returns:
            True when movement is allowed by natural or structural rules.
        """
        delta = abs(next_level - current_level)
        return delta <= self.max_natural_delta or transition_allowed

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the rules."""
        return {
            "max_natural_delta": self.max_natural_delta,
            "cardinal_movement_only": self.cardinal_movement_only,
            "structural_transition": "allows_delta_above_natural_limit",
        }


DEFAULT_TRAVERSAL_RULES = TraversalRules()
