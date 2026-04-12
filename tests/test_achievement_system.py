"""
tests/test_achievement_system.py

Tests for v0.39 AchievementSystem: condition evaluation, apply_to_profile,
and definition loading from the real achievements.yaml.

No pygame required.
"""

import unittest

from game.systems.achievement_system import AchievementSystem
from game.utils.constants import DEFAULT_PROFILE


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _profile(**overrides) -> dict:
    """Return a minimal profile dict with sane defaults."""
    base = {
        "wins": 0,
        "losses": 0,
        "total_matches": 0,
        "level": 1,
        "match_history": [],
        "achievements": [],
    }
    base.update(overrides)
    return base


def _history_entry(**overrides) -> dict:
    """Return a minimal match history entry."""
    base = {
        "won": True,
        "kills": 0,
        "accuracy": 0.0,
        "damage_dealt": 0,
        "damage_taken": 0,
        "time_elapsed": 30.0,
        "xp_earned": 50,
        "level_after": 1,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestConditionEvaluation
# ---------------------------------------------------------------------------

class TestConditionEvaluation(unittest.TestCase):
    """Direct condition evaluation via _check_condition()."""

    def setUp(self) -> None:
        self.sys = AchievementSystem()

    def _defn(self, ctype: str, value) -> dict:
        return {"id": "test", "name": "Test", "description": "",
                "condition_type": ctype, "condition_value": value}

    # wins_gte
    def test_wins_gte_true(self) -> None:
        self.assertTrue(self.sys._check_condition(self._defn("wins_gte", 3), _profile(wins=5)))

    def test_wins_gte_false(self) -> None:
        self.assertFalse(self.sys._check_condition(self._defn("wins_gte", 3), _profile(wins=1)))

    def test_wins_gte_exact(self) -> None:
        self.assertTrue(self.sys._check_condition(self._defn("wins_gte", 3), _profile(wins=3)))

    # matches_gte
    def test_matches_gte_true(self) -> None:
        self.assertTrue(self.sys._check_condition(
            self._defn("matches_gte", 50), _profile(total_matches=50)))

    # level_gte
    def test_level_gte_true(self) -> None:
        self.assertTrue(self.sys._check_condition(self._defn("level_gte", 21), _profile(level=21)))

    def test_level_gte_false(self) -> None:
        self.assertFalse(self.sys._check_condition(self._defn("level_gte", 21), _profile(level=10)))

    # accuracy_gte_in_any_match
    def test_accuracy_in_any_match_true(self) -> None:
        profile = _profile(match_history=[_history_entry(accuracy=0.85)])
        self.assertTrue(self.sys._check_condition(
            self._defn("accuracy_gte_in_any_match", 0.80), profile))

    def test_accuracy_in_any_match_false(self) -> None:
        profile = _profile(match_history=[_history_entry(accuracy=0.5)])
        self.assertFalse(self.sys._check_condition(
            self._defn("accuracy_gte_in_any_match", 0.80), profile))

    def test_accuracy_empty_history(self) -> None:
        self.assertFalse(self.sys._check_condition(
            self._defn("accuracy_gte_in_any_match", 0.80), _profile()))

    # damage_dealt_gte_in_any_match
    def test_damage_dealt_in_any_match_true(self) -> None:
        profile = _profile(match_history=[_history_entry(damage_dealt=1200)])
        self.assertTrue(self.sys._check_condition(
            self._defn("damage_dealt_gte_in_any_match", 1000), profile))

    # kills_gte_in_any_match
    def test_kills_in_any_match_true(self) -> None:
        profile = _profile(match_history=[_history_entry(kills=3)])
        self.assertTrue(self.sys._check_condition(
            self._defn("kills_gte_in_any_match", 3), profile))

    # win_with_damage_taken_lte
    def test_win_with_no_damage_taken(self) -> None:
        profile = _profile(match_history=[_history_entry(won=True, damage_taken=0)])
        self.assertTrue(self.sys._check_condition(
            self._defn("win_with_damage_taken_lte", 0), profile))

    def test_win_with_no_damage_taken_lost(self) -> None:
        profile = _profile(match_history=[_history_entry(won=False, damage_taken=0)])
        self.assertFalse(self.sys._check_condition(
            self._defn("win_with_damage_taken_lte", 0), profile))

    # unknown condition
    def test_unknown_condition_type_returns_false(self) -> None:
        self.assertFalse(self.sys._check_condition(
            self._defn("nonexistent_condition", 1), _profile()))


# ---------------------------------------------------------------------------
# TestApplyToProfile
# ---------------------------------------------------------------------------

class TestApplyToProfile(unittest.TestCase):
    """Tests for apply_to_profile() using the real achievements.yaml."""

    def setUp(self) -> None:
        self.sys = AchievementSystem()

    def _winning_profile(self, **overrides) -> dict:
        """Profile that satisfies first_blood (wins >= 1)."""
        base = _profile(wins=1, total_matches=1,
                        match_history=[_history_entry(won=True)])
        base.update(overrides)
        return base

    def test_newly_earned_returned(self) -> None:
        profile = self._winning_profile()
        _, newly = self.sys.apply_to_profile(profile)
        self.assertIn("first_blood", newly)

    def test_already_earned_not_duplicated(self) -> None:
        profile = self._winning_profile(achievements=["first_blood"])
        _, newly = self.sys.apply_to_profile(profile)
        self.assertNotIn("first_blood", newly)

    def test_profile_not_mutated(self) -> None:
        profile = self._winning_profile()
        original_achievements = list(profile["achievements"])
        self.sys.apply_to_profile(profile)
        self.assertEqual(profile["achievements"], original_achievements)

    def test_new_profile_has_achievement(self) -> None:
        profile = self._winning_profile()
        new_profile, _ = self.sys.apply_to_profile(profile)
        self.assertIn("first_blood", new_profile["achievements"])

    def test_multiple_earned_in_one_apply(self) -> None:
        # Profile that satisfies first_blood (wins>=1), exterminator (kills>=3 in match),
        # and untouchable (win with 0 damage taken)
        profile = _profile(
            wins=1,
            total_matches=1,
            match_history=[_history_entry(won=True, kills=3, damage_taken=0)],
        )
        _, newly = self.sys.apply_to_profile(profile)
        self.assertIn("first_blood", newly)
        self.assertIn("exterminator", newly)
        self.assertIn("untouchable", newly)
        self.assertGreaterEqual(len(newly), 3)


# ---------------------------------------------------------------------------
# TestAchievementDefinitions
# ---------------------------------------------------------------------------

class TestAchievementDefinitions(unittest.TestCase):
    """Tests for definition loading from the real achievements.yaml."""

    def setUp(self) -> None:
        self.sys = AchievementSystem()

    def test_all_definitions_returns_list(self) -> None:
        defs = self.sys.all_definitions()
        self.assertIsInstance(defs, list)
        self.assertGreater(len(defs), 0)

    def test_ten_achievements_defined(self) -> None:
        self.assertEqual(len(self.sys.all_definitions()), 10)

    def test_each_definition_has_required_keys(self) -> None:
        required = {"id", "name", "description", "condition_type", "condition_value"}
        for defn in self.sys.all_definitions():
            with self.subTest(id=defn.get("id")):
                self.assertEqual(required, required & defn.keys())

    def test_get_definition_by_id(self) -> None:
        defn = self.sys.get_definition("first_blood")
        self.assertIsNotNone(defn)
        self.assertEqual(defn["name"], "First Blood")

    def test_get_definition_unknown_returns_none(self) -> None:
        self.assertIsNone(self.sys.get_definition("nonexistent_id"))


if __name__ == "__main__":
    unittest.main()
