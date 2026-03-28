"""
game/systems/weapon_roller.py

WeaponRoller — randomly assigns weapons to slots 2 and 3 from
the player's unlocked pool using weighted probability.

Slot 1 is always standard_shell. Slots 2-3 are independent random
draws (no duplicates within a single loadout).
"""

import random

from game.utils.config_loader import load_yaml
from game.utils.constants import WEAPON_WEIGHTS_CONFIG
from game.utils.logger import get_logger

log = get_logger(__name__)


class WeaponRoller:
    """
    Generates random weapon loadouts from the unlocked pool.

    Usage:
        roller = WeaponRoller(unlocked_weapons=["spread_shot", "bouncing_round", ...])
        loadout = roller.roll()
        # loadout = ["standard_shell", "bouncing_round", "cryo_round"]
    """

    def __init__(self, unlocked_weapons: list[str]) -> None:
        """
        Args:
            unlocked_weapons: list of weapon type strings the player has unlocked.
                              "standard_shell" is filtered out — it's always slot 1.
        """
        self._weights: dict[str, int] = load_yaml(WEAPON_WEIGHTS_CONFIG) or {}

        # Filter to only weapons the player has unlocked AND that have weights defined
        # Exclude standard_shell — it's always slot 1
        self._pool: list[str] = [
            w for w in unlocked_weapons
            if w != "standard_shell" and w in self._weights
        ]

        log.debug(
            "WeaponRoller initialized. Pool: %s (%d weapons)",
            self._pool, len(self._pool),
        )

    def roll(self) -> list[str | None]:
        """
        Generate a 3-slot loadout.

        Returns:
            list of 3 weapon type strings:
            - Slot 0: always "standard_shell"
            - Slot 1: random from pool (weighted)
            - Slot 2: random from pool (weighted, no duplicate with slot 1)

            If pool has 0 weapons: ["standard_shell", None, None]
            If pool has 1 weapon:  ["standard_shell", <weapon>, None]
        """
        loadout: list[str | None] = ["standard_shell", None, None]

        if not self._pool:
            return loadout

        # Slot 1 — weighted random
        slot1 = self._weighted_pick(self._pool)
        loadout[1] = slot1

        # Slot 2 — weighted random, excluding slot 1's weapon
        remaining = [w for w in self._pool if w != slot1]
        if remaining:
            loadout[2] = self._weighted_pick(remaining)

        log.info("Weapon roll: %s", loadout)
        return loadout

    def _weighted_pick(self, candidates: list[str]) -> str:
        """Pick one weapon from candidates using configured weights."""
        weights = [self._weights.get(w, 1) for w in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    @property
    def pool_size(self) -> int:
        """Number of weapons available for random assignment."""
        return len(self._pool)
