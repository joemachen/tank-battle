"""
game/systems/weapon_roller.py

WeaponRoller — assigns one weapon per category to produce a 4-slot loadout:
  Slot 0: Basic
  Slot 1: Elemental
  Slot 2: Heavy
  Slot 3: Tactical

Each slot draws one weapon from its category pool using weighted probability.
No duplicates are possible by design (each weapon has exactly one category).

v0.35 — replaces the 3-slot random system with a 4-slot category-guaranteed
         loadout for both player and AI.
"""

import random

from game.utils.config_loader import load_yaml
from game.utils.constants import WEAPON_CATEGORIES, WEAPON_WEIGHTS_CONFIG
from game.utils.logger import get_logger

log = get_logger(__name__)

# Fallback weapon when a category pool is empty (should only happen in edge-case
# test environments where most weapons are locked).
_CATEGORY_FALLBACKS: dict[str, str] = {
    "basic":     "standard_shell",
    "elemental": "cryo_round",
    "heavy":     "homing_missile",
    "tactical":  "emp_blast",
}


class WeaponRoller:
    """
    Generates random 4-slot weapon loadouts with one weapon per category.

    Usage:
        roller = WeaponRoller(
            unlocked_weapons=["standard_shell", "spread_shot", ...],
            weapon_configs=all_weapon_data,    # dict from weapons.yaml
        )
        loadout = roller.roll()
        # loadout = ["spread_shot", "cryo_round", "railgun", "glue_gun"]
    """

    def __init__(
        self,
        unlocked_weapons: list[str],
        weapon_configs: dict | None = None,
    ) -> None:
        """
        Args:
            unlocked_weapons: list of weapon type strings the player/AI has unlocked.
            weapon_configs:   full dict loaded from weapons.yaml (used to read category).
                              Falls back to loading WEAPONS_CONFIG itself if not provided
                              (backwards-compat for callers that predate v0.35).
        """
        self._weights: dict[str, int] = load_yaml(WEAPON_WEIGHTS_CONFIG) or {}

        # Load weapon_configs if not passed (backwards-compat shim)
        if weapon_configs is None:
            from game.utils.constants import WEAPONS_CONFIG
            weapon_configs = load_yaml(WEAPONS_CONFIG) or {}

        # Build category → [weapon] pools from unlocked weapons
        self._pools: dict[str, list[str]] = {cat: [] for cat in WEAPON_CATEGORIES}
        for wtype in unlocked_weapons:
            cfg = weapon_configs.get(wtype, {})
            cat = cfg.get("category", "")
            if cat in self._pools:
                self._pools[cat].append(wtype)

        log.debug(
            "WeaponRoller initialized. Pool sizes: %s",
            {cat: len(pool) for cat, pool in self._pools.items()},
        )

    def roll(self) -> list[str]:
        """
        Generate a 4-slot category-guaranteed loadout.

        Returns:
            list of 4 weapon type strings in WEAPON_CATEGORIES order:
            [basic, elemental, heavy, tactical]

            If a category pool is empty, the fallback weapon for that category
            is used and a warning is logged.
        """
        loadout: list[str] = []
        for cat in WEAPON_CATEGORIES:
            pool = self._pools[cat]
            if pool:
                loadout.append(self._weighted_pick(pool))
            else:
                fallback = _CATEGORY_FALLBACKS.get(cat, "standard_shell")
                log.warning(
                    "WeaponRoller: no weapons in '%s' pool — using fallback '%s'",
                    cat, fallback,
                )
                loadout.append(fallback)

        log.info("Weapon roll: %s", loadout)
        return loadout

    def _weighted_pick(self, candidates: list[str]) -> str:
        """Pick one weapon from candidates using configured weights."""
        weights = [self._weights.get(w, 1) for w in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def category_pool(self, category: str) -> list[str]:
        """Return the list of unlocked weapons in the given category."""
        return list(self._pools.get(category, []))

    @property
    def pool_sizes(self) -> dict[str, int]:
        """Number of weapons available per category."""
        return {cat: len(pool) for cat, pool in self._pools.items()}

    @property
    def pool_size(self) -> int:
        """Total weapons across all category pools. Deprecated — use pool_sizes."""
        return sum(len(p) for p in self._pools.values())
