"""
game/systems/achievement_system.py

AchievementSystem — stateless evaluator for achievement conditions, v0.39.

Loads achievement definitions from achievements.yaml on first use.
Mirrors the ProgressionManager pattern: lazy-load YAML, never mutate input.

Public API:
  evaluate(profile)          → list of earned achievement IDs (condition met)
  apply_to_profile(profile)  → (new_profile, newly_earned_ids)
  get_definition(id)         → definition dict or None
  all_definitions()          → list of all definitions in config order
"""

from game.utils.config_loader import load_yaml
from game.utils.constants import ACHIEVEMENTS_CONFIG
from game.utils.logger import get_logger

log = get_logger(__name__)


class AchievementSystem:
    """Stateless achievement evaluator.  Instantiate once; reuse freely."""

    def __init__(self, config_path: str = ACHIEVEMENTS_CONFIG) -> None:
        self._config_path = config_path
        self._definitions: list[dict] = []   # lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, profile: dict) -> list[str]:
        """Return IDs of all achievements whose condition is currently met.

        Does not check whether already earned — purely condition-based.
        Does not mutate *profile*.
        """
        self._ensure_loaded()
        return [
            defn["id"]
            for defn in self._definitions
            if self._check_condition(defn, profile)
        ]

    def apply_to_profile(self, profile: dict) -> tuple[dict, list[str]]:
        """Evaluate conditions, append newly earned IDs to a copy of *profile*.

        Returns (new_profile, newly_earned_ids).
        *profile* is never mutated.
        """
        earned_now = self.evaluate(profile)
        already_earned: set[str] = set(profile.get("achievements", []))
        newly_earned = [aid for aid in earned_now if aid not in already_earned]

        new_profile = dict(profile)
        if newly_earned:
            new_profile["achievements"] = list(already_earned) + newly_earned
            log.info("New achievements earned: %s", newly_earned)

        return new_profile, newly_earned

    def get_definition(self, achievement_id: str) -> dict | None:
        """Return the full definition dict for *achievement_id*, or None."""
        self._ensure_loaded()
        for defn in self._definitions:
            if defn["id"] == achievement_id:
                return defn
        return None

    def all_definitions(self) -> list[dict]:
        """Return all achievement definitions in config file order."""
        self._ensure_loaded()
        return list(self._definitions)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._definitions:
            raw = load_yaml(self._config_path) or {}
            self._definitions = raw.get("achievements", [])
            if not self._definitions:
                log.warning("Achievement config empty or missing: %s", self._config_path)

    def _check_condition(self, defn: dict, profile: dict) -> bool:
        """Evaluate a single achievement condition against *profile*.

        Returns True if the condition is met, False otherwise.
        Unknown condition_type logs a warning and returns False.
        """
        ctype: str = defn.get("condition_type", "")
        value = defn.get("condition_value", 0)
        history: list[dict] = profile.get("match_history", [])

        if ctype == "wins_gte":
            return int(profile.get("wins", 0)) >= value

        if ctype == "matches_gte":
            return int(profile.get("total_matches", 0)) >= value

        if ctype == "level_gte":
            return int(profile.get("level", 1)) >= value

        if ctype == "accuracy_gte_in_any_match":
            return any(float(e.get("accuracy", 0)) >= value for e in history)

        if ctype == "damage_dealt_gte_in_any_match":
            return any(int(e.get("damage_dealt", 0)) >= value for e in history)

        if ctype == "kills_gte_in_any_match":
            return any(int(e.get("kills", 0)) >= value for e in history)

        if ctype == "win_with_damage_taken_lte":
            return any(
                e.get("won") and int(e.get("damage_taken", 0)) <= value
                for e in history
            )

        log.warning("Unknown achievement condition_type '%s' for id '%s'", ctype, defn.get("id"))
        return False
