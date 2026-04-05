"""
game/systems/ultimate_roller.py

UltimateRoller — draws a single ultimate from the shared 6-ability pool
using weighted probability (v0.33.5).

Modelled after WeaponRoller. Weights are defined in
data/configs/ultimate_weights.yaml.

Usage:
    roller = UltimateRoller("data/configs/ultimate_weights.yaml")
    key = roller.roll()                     # any of the 6 ability keys
    key = roller.roll(exclude="barrage")    # never returns "barrage"
"""

import random

from game.utils.config_loader import load_yaml
from game.utils.logger import get_logger

log = get_logger(__name__)


class UltimateRoller:
    """
    Draws a single ultimate key from the weighted pool.

    The pool is fixed to all keys defined in ultimate_weights.yaml.
    No concept of player-specific "unlocked" ultimates — all 6 are always
    available to roll.
    """

    def __init__(self, weights_path: str) -> None:
        raw: dict = load_yaml(weights_path) or {}
        # Pool is the ordered list of keys with positive weight
        self._pool: list[str] = [k for k, w in raw.items() if int(w) > 0]
        self._weights: dict[str, int] = {k: int(w) for k, w in raw.items() if int(w) > 0}
        log.debug(
            "UltimateRoller initialized. Pool: %s (%d ultimates)",
            self._pool, len(self._pool),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def roll(self, exclude: str | None = None) -> str:
        """Return a random ultimate key drawn from the weighted pool.

        Args:
            exclude: If provided, this key is removed from the candidate
                     pool for this draw, preventing the same result twice
                     in a row (e.g. during rerolls). Ignored if the pool
                     would become empty after exclusion.

        Returns:
            One of the ultimate keys (e.g. "barrage", "lockdown").
        """
        candidates = self._pool
        if exclude and exclude in candidates and len(candidates) > 1:
            candidates = [k for k in candidates if k != exclude]
        if not candidates:
            # Fallback — should never happen with a correctly configured yaml
            return self._pool[0] if self._pool else "overdrive"
        weights = [self._weights.get(k, 1) for k in candidates]
        result = random.choices(candidates, weights=weights, k=1)[0]
        log.debug("UltimateRoller.roll(exclude=%r) → %r", exclude, result)
        return result

    def roll_for_tank(self) -> str:
        """Convenience wrapper: roll with no exclusion."""
        return self.roll()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pool(self) -> list[str]:
        """All ultimate keys available in this roller's pool."""
        return list(self._pool)

    @property
    def pool_size(self) -> int:
        """Number of ultimates in the pool."""
        return len(self._pool)
