"""
tests/test_match_history.py

Tests for v0.38 match history persistence, entry values, and progression
scene tab state.

No pygame display required for data-layer tests.  Tab-state tests
instantiate ProgressionScene with a mock manager and use pygame key events.
"""

import types
import unittest
from unittest.mock import MagicMock, patch

import pygame

from game.scenes.game_over_scene import _append_history_entry
from game.scenes.progression_scene import ProgressionScene
from game.systems.match_calculator import MatchCalculator
from game.utils.constants import DEFAULT_PROFILE, MATCH_HISTORY_MAX_STORED


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_result(**overrides):
    """Return a MatchResult via the real factory with sensible defaults."""
    defaults = dict(
        won=True,
        survived=True,
        kills=2,
        shots_fired=10,
        shots_hit=7,
        time_elapsed=90.0,
        damage_dealt=300,
        damage_taken=120,
    )
    defaults.update(overrides)
    return MatchCalculator.build(**defaults)


def _fresh_profile(**overrides) -> dict:
    """Return a copy of DEFAULT_PROFILE with optional field overrides."""
    p = dict(DEFAULT_PROFILE)
    p["match_history"] = []
    p.update(overrides)
    return p


# ---------------------------------------------------------------------------
# TestMatchHistoryPersistence
# ---------------------------------------------------------------------------

class TestMatchHistoryPersistence(unittest.TestCase):
    """Tests for _append_history_entry() — the module-level write helper."""

    def test_entry_appended_after_match(self) -> None:
        profile = _fresh_profile()
        _append_history_entry(profile, _make_result())
        self.assertEqual(len(profile["match_history"]), 1)

    def test_entry_fields_present(self) -> None:
        profile = _fresh_profile()
        _append_history_entry(profile, _make_result())
        entry = profile["match_history"][0]
        required = {"won", "kills", "accuracy", "damage_dealt", "damage_taken",
                    "time_elapsed", "xp_earned", "level_after"}
        self.assertEqual(required, required & entry.keys())

    def test_accuracy_rounded_to_3dp(self) -> None:
        # 7/10 shots hit → accuracy = 0.7 exactly
        profile = _fresh_profile()
        _append_history_entry(profile, _make_result(shots_fired=10, shots_hit=7))
        entry = profile["match_history"][0]
        # Verify stored value has at most 3 decimal places
        self.assertEqual(entry["accuracy"], round(entry["accuracy"], 3))

    def test_time_rounded_to_1dp(self) -> None:
        profile = _fresh_profile()
        _append_history_entry(profile, _make_result(time_elapsed=90.123456))
        entry = profile["match_history"][0]
        self.assertEqual(entry["time_elapsed"], round(entry["time_elapsed"], 1))

    def test_cap_at_50_entries(self) -> None:
        profile = _fresh_profile()
        for _ in range(51):
            _append_history_entry(profile, _make_result())
        self.assertEqual(len(profile["match_history"]), MATCH_HISTORY_MAX_STORED)

    def test_oldest_dropped_when_capped(self) -> None:
        profile = _fresh_profile()
        # First entry with kills=0 (sentinel)
        _append_history_entry(profile, _make_result(kills=0))
        for _ in range(MATCH_HISTORY_MAX_STORED):
            _append_history_entry(profile, _make_result(kills=99))
        # The sentinel (kills=0) should have been dropped
        first = profile["match_history"][0]
        self.assertNotEqual(first["kills"], 0)

    def test_newest_first_ordering(self) -> None:
        profile = _fresh_profile()
        _append_history_entry(profile, _make_result(kills=1))
        _append_history_entry(profile, _make_result(kills=2))
        # history[-1] is the most recently appended
        self.assertEqual(profile["match_history"][-1]["kills"], 2)
        # Display reversal gives newest at index 0
        self.assertEqual(list(reversed(profile["match_history"]))[0]["kills"], 2)

    def test_empty_history_on_fresh_profile(self) -> None:
        self.assertEqual(DEFAULT_PROFILE["match_history"], [])


# ---------------------------------------------------------------------------
# TestHistoryEntryValues
# ---------------------------------------------------------------------------

class TestHistoryEntryValues(unittest.TestCase):
    """Tests that individual entry fields correctly mirror MatchResult data."""

    def _entry_for(self, **overrides) -> dict:
        profile = _fresh_profile(level=5)
        result = _make_result(**overrides)
        _append_history_entry(profile, result)
        return profile["match_history"][0]

    def test_won_field_matches_result(self) -> None:
        entry = self._entry_for(won=True)
        self.assertTrue(entry["won"])
        entry = self._entry_for(won=False, survived=False)
        self.assertFalse(entry["won"])

    def test_kills_field_matches_result(self) -> None:
        entry = self._entry_for(kills=3)
        self.assertEqual(entry["kills"], 3)

    def test_xp_earned_field_matches_result(self) -> None:
        result = _make_result(won=True, kills=2)
        profile = _fresh_profile()
        _append_history_entry(profile, result)
        entry = profile["match_history"][0]
        self.assertEqual(entry["xp_earned"], result.xp_earned)

    def test_level_after_field(self) -> None:
        # level_after should reflect the level stored in the profile at the time
        # of the call (i.e. post-apply_match_result level)
        profile = _fresh_profile(level=8)
        _append_history_entry(profile, _make_result())
        self.assertEqual(profile["match_history"][0]["level_after"], 8)


# ---------------------------------------------------------------------------
# TestProgressionSceneTabState
# ---------------------------------------------------------------------------

class TestProgressionSceneTabState(unittest.TestCase):
    """Tests for LEFT/RIGHT tab navigation in ProgressionScene.

    Instantiates the scene with a mock manager — no on_enter() call needed
    for tab state tests since _active_tab is set in __init__.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # pygame must be initialized for K_LEFT / K_RIGHT constants
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def _make_scene(self) -> ProgressionScene:
        mock_manager = MagicMock()
        with patch("game.scenes.progression_scene.get_audio_manager"):
            return ProgressionScene(mock_manager)

    def _keydown(self, key: int) -> object:
        return types.SimpleNamespace(type=pygame.KEYDOWN, key=key)

    def test_default_tab_is_unlocks(self) -> None:
        scene = self._make_scene()
        self.assertEqual(scene._active_tab, 0)

    def test_right_key_switches_to_history(self) -> None:
        scene = self._make_scene()
        with patch("game.scenes.progression_scene.get_audio_manager"):
            scene.handle_event(self._keydown(pygame.K_RIGHT))
        self.assertEqual(scene._active_tab, 1)

    def test_left_key_switches_back(self) -> None:
        scene = self._make_scene()
        with patch("game.scenes.progression_scene.get_audio_manager"):
            scene.handle_event(self._keydown(pygame.K_RIGHT))
            scene.handle_event(self._keydown(pygame.K_LEFT))
        self.assertEqual(scene._active_tab, 0)

    def test_tab_wrap_left_from_unlocks(self) -> None:
        scene = self._make_scene()
        with patch("game.scenes.progression_scene.get_audio_manager"):
            scene.handle_event(self._keydown(pygame.K_LEFT))
        self.assertEqual(scene._active_tab, 0)

    def test_tab_wrap_right_from_history(self) -> None:
        scene = self._make_scene()
        with patch("game.scenes.progression_scene.get_audio_manager"):
            scene.handle_event(self._keydown(pygame.K_RIGHT))
            scene.handle_event(self._keydown(pygame.K_RIGHT))
        self.assertEqual(scene._active_tab, 1)


if __name__ == "__main__":
    unittest.main()
