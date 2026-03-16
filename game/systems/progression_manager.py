"""
game/systems/progression_manager.py

ProgressionManager — pure progression logic.

Responsibilities:
  - Add XP from a completed match to a player profile
  - Recalculate level from cumulative XP using xp_table.yaml thresholds
  - Detect newly unlocked items (tanks and weapons)
  - Update win/loss/match counters
  - Return a new profile dict (never mutates the input)

SaveManager handles all file I/O; ProgressionManager handles all logic.
The separation keeps both classes unit-testable in isolation.
"""

from game.systems.match_calculator import MatchResult
from game.utils.config_loader import load_yaml
from game.utils.constants import XP_TABLE_CONFIG
from game.utils.logger import get_logger

log = get_logger(__name__)


class ProgressionManager:
    """
    Stateless helper.  Instantiate once; reuse across matches.
    """

    def __init__(self, xp_table_path: str = XP_TABLE_CONFIG) -> None:
        self._xp_table_path = xp_table_path
        self._xp_table: list[dict] = []   # lazy-loaded on first use

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_match_result(
        self, profile: dict, result: MatchResult
    ) -> tuple[dict, list[str]]:
        """
        Apply a match result to a player profile.

        Args:
            profile:  Current player profile dict (read from SaveManager).
            result:   Completed MatchResult from MatchCalculator.

        Returns:
            (new_profile, new_unlocks) where:
              - new_profile is a **new** dict (input is not mutated)
              - new_unlocks is a list of item IDs newly unlocked at the
                resulting level (may be empty)
        """
        self._ensure_xp_table()

        new_profile = dict(profile)

        # --- XP and level ---
        old_xp = int(new_profile.get("xp", 0))
        new_xp = old_xp + result.xp_earned
        new_profile["xp"] = new_xp

        old_level = int(new_profile.get("level", 1))
        new_level = self._compute_level(new_xp)
        new_profile["level"] = new_level

        # --- Discover new unlocks between old_level+1 and new_level ---
        new_unlocks = self._collect_unlocks(old_level, new_level)

        # Apply new unlocks to profile lists
        unlocked_tanks = list(new_profile.get("unlocked_tanks", []))
        unlocked_weapons = list(new_profile.get("unlocked_weapons", []))
        for item_id in new_unlocks:
            if item_id.endswith("_tank"):
                if item_id not in unlocked_tanks:
                    unlocked_tanks.append(item_id)
            else:
                if item_id not in unlocked_weapons:
                    unlocked_weapons.append(item_id)
        new_profile["unlocked_tanks"] = unlocked_tanks
        new_profile["unlocked_weapons"] = unlocked_weapons

        # --- Match counters ---
        new_profile["total_matches"] = int(new_profile.get("total_matches", 0)) + 1
        if result.won:
            new_profile["wins"] = int(new_profile.get("wins", 0)) + 1
        else:
            new_profile["losses"] = int(new_profile.get("losses", 0)) + 1

        log.info(
            "Progression: XP %d → %d  level %d → %d  new_unlocks=%s",
            old_xp, new_xp, old_level, new_level, new_unlocks,
        )
        return new_profile, new_unlocks

    # ------------------------------------------------------------------
    # Level helpers (also used by UI for displaying progress bars)
    # ------------------------------------------------------------------

    def compute_level(self, xp: int) -> int:
        """Public alias — returns the level for a given cumulative XP value."""
        self._ensure_xp_table()
        return self._compute_level(xp)

    def xp_for_level(self, level: int) -> int:
        """Return the cumulative XP required to reach *level* (0 if not found)."""
        self._ensure_xp_table()
        for entry in self._xp_table:
            if entry["level"] == level:
                return int(entry["xp_required"])
        return 0

    def next_level_xp(self, xp: int) -> int | None:
        """
        Return the XP required to reach the next level from current XP,
        or None if already at max level.
        """
        self._ensure_xp_table()
        for entry in self._xp_table:
            if entry["xp_required"] > xp:
                return int(entry["xp_required"])
        return None

    def unlock_level_for(self, item_id: str) -> int | None:
        """
        Return the level at which item_id is unlocked, or None if not in table.
        Used by TankSelectScene to show 'Unlocks at Level N'.
        """
        self._ensure_xp_table()
        for entry in self._xp_table:
            if item_id in entry.get("unlocks", []):
                return int(entry["level"])
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_xp_table(self) -> None:
        if not self._xp_table:
            raw = load_yaml(self._xp_table_path)
            self._xp_table = raw.get("levels", [])
            if not self._xp_table:
                log.warning("XP table empty or missing — progression will be flat.")

    def _compute_level(self, xp: int) -> int:
        """Return the level corresponding to cumulative XP."""
        current = 1
        for entry in self._xp_table:
            if xp >= int(entry["xp_required"]):
                current = int(entry["level"])
            else:
                break
        return current

    def _collect_unlocks(self, old_level: int, new_level: int) -> list[str]:
        """Return all item IDs unlocked by moving from old_level → new_level."""
        unlocks: list[str] = []
        if new_level <= old_level:
            return unlocks
        for entry in self._xp_table:
            lvl = int(entry["level"])
            if old_level < lvl <= new_level:
                for item in entry.get("unlocks", []):
                    unlocks.append(item)
        return unlocks
