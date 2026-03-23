"""
tests/test_progression_manager.py

Unit tests for ProgressionManager.
No file I/O — the XP table is injected directly via _xp_table to keep
tests fast and hermetic.
"""

import pytest

from game.systems.match_calculator import MatchCalculator, MatchResult
from game.systems.progression_manager import ProgressionManager


# ---------------------------------------------------------------------------
# Test XP table (injected — no file I/O)
# ---------------------------------------------------------------------------

_TABLE = [
    {"level": 1, "xp_required": 0,    "unlocks": []},
    {"level": 2, "xp_required": 150,  "unlocks": []},
    {"level": 3, "xp_required": 350,  "unlocks": ["medium_tank"]},
    {"level": 4, "xp_required": 700,  "unlocks": ["spread_shot"]},
    {"level": 5, "xp_required": 1200, "unlocks": ["heavy_tank"]},
]


def _make_pm() -> ProgressionManager:
    pm = ProgressionManager()
    pm._xp_table = list(_TABLE)   # inject table — skips file I/O
    return pm


def _result(xp_earned: int = 50, won: bool = True) -> MatchResult:
    r = MatchCalculator.build(
        won=won, survived=won, kills=0,
        shots_fired=0, shots_hit=0,
        time_elapsed=60.0, damage_dealt=0, damage_taken=0,
    )
    r.xp_earned = xp_earned
    return r


def _profile(**overrides) -> dict:
    base = {
        "xp": 0,
        "level": 1,
        "unlocked_tanks": ["light_tank"],
        "unlocked_weapons": ["standard_shell"],
        "total_matches": 0,
        "wins": 0,
        "losses": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# XP addition
# ---------------------------------------------------------------------------

class TestXpAddition:
    def test_xp_added_correctly(self):
        pm = _make_pm()
        profile = _profile(xp=100)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=75))
        assert new_profile["xp"] == 175

    def test_xp_zero_match_adds_nothing_beyond_earned(self):
        pm = _make_pm()
        profile = _profile(xp=50)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=0))
        assert new_profile["xp"] == 50

    def test_input_profile_not_mutated(self):
        """apply_match_result must return a NEW dict, not modify the input."""
        pm = _make_pm()
        profile = _profile(xp=100)
        original_xp = profile["xp"]
        pm.apply_match_result(profile, _result(xp_earned=99))
        assert profile["xp"] == original_xp


# ---------------------------------------------------------------------------
# Level recalculation
# ---------------------------------------------------------------------------

class TestLevelRecalculation:
    def test_stays_level_1_below_threshold(self):
        pm = _make_pm()
        profile = _profile(xp=0, level=1)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=100))
        assert new_profile["level"] == 1

    def test_level_up_at_exact_threshold(self):
        pm = _make_pm()
        profile = _profile(xp=100, level=1)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=50))
        assert new_profile["level"] == 2    # 100+50 = 150

    def test_level_up_past_threshold(self):
        pm = _make_pm()
        profile = _profile(xp=300, level=2)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=60))
        assert new_profile["level"] == 3    # 300+60 = 360 >= 350

    def test_multi_level_jump(self):
        """A very large XP gain can jump multiple levels at once."""
        pm = _make_pm()
        profile = _profile(xp=0, level=1)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=800))
        assert new_profile["level"] == 4    # 800 >= 700


# ---------------------------------------------------------------------------
# Unlock detection
# ---------------------------------------------------------------------------

class TestUnlockDetection:
    def test_unlock_when_level_crosses_threshold(self):
        pm = _make_pm()
        profile = _profile(xp=300, level=2)
        _, new_unlocks = pm.apply_match_result(profile, _result(xp_earned=60))
        assert "medium_tank" in new_unlocks   # level 3 unlock

    def test_no_unlock_when_level_unchanged(self):
        pm = _make_pm()
        profile = _profile(xp=0, level=1)
        _, new_unlocks = pm.apply_match_result(profile, _result(xp_earned=50))
        assert new_unlocks == []

    def test_unlock_added_to_profile_tanks(self):
        pm = _make_pm()
        profile = _profile(xp=300, level=2)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=60))
        assert "medium_tank" in new_profile["unlocked_tanks"]

    def test_unlock_added_to_profile_weapons(self):
        """spread_shot (a weapon) should land in unlocked_weapons, not tanks."""
        pm = _make_pm()
        profile = _profile(xp=600, level=3)
        new_profile, new_unlocks = pm.apply_match_result(profile, _result(xp_earned=110))
        # 600+110=710 → level 4 → unlocks spread_shot
        assert "spread_shot" in new_unlocks
        assert "spread_shot" in new_profile["unlocked_weapons"]
        assert "spread_shot" not in new_profile["unlocked_tanks"]

    def test_no_duplicate_unlock(self):
        """Items already in the profile are not added again."""
        pm = _make_pm()
        profile = _profile(xp=300, level=2, unlocked_tanks=["light_tank", "medium_tank"])
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=60))
        assert new_profile["unlocked_tanks"].count("medium_tank") == 1


# ---------------------------------------------------------------------------
# Match counters
# ---------------------------------------------------------------------------

class TestMatchCounters:
    def test_total_matches_incremented(self):
        pm = _make_pm()
        profile = _profile(total_matches=5)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=10, won=True))
        assert new_profile["total_matches"] == 6

    def test_wins_incremented_on_win(self):
        pm = _make_pm()
        profile = _profile(wins=2)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=10, won=True))
        assert new_profile["wins"] == 3

    def test_losses_incremented_on_loss(self):
        pm = _make_pm()
        profile = _profile(losses=1)
        new_profile, _ = pm.apply_match_result(profile, _result(xp_earned=10, won=False))
        assert new_profile["losses"] == 2


# ---------------------------------------------------------------------------
# Retroactive backfill
# ---------------------------------------------------------------------------

class TestBackfillUnlocks:
    def test_backfills_missing_weapon(self):
        """Level 4 player missing spread_shot gets it backfilled."""
        pm = _make_pm()
        profile = _profile(level=4, xp=700, unlocked_weapons=["standard_shell"])
        new_profile, backfilled = pm.backfill_unlocks(profile)
        assert "spread_shot" in backfilled
        assert "spread_shot" in new_profile["unlocked_weapons"]

    def test_backfills_missing_tank(self):
        """Level 3 player missing medium_tank gets it backfilled."""
        pm = _make_pm()
        profile = _profile(level=3, xp=350, unlocked_tanks=["light_tank"])
        new_profile, backfilled = pm.backfill_unlocks(profile)
        assert "medium_tank" in backfilled
        assert "medium_tank" in new_profile["unlocked_tanks"]

    def test_no_backfill_when_up_to_date(self):
        """Profile with all expected unlocks returns empty backfill."""
        pm = _make_pm()
        profile = _profile(
            level=4, xp=700,
            unlocked_tanks=["light_tank", "medium_tank"],
            unlocked_weapons=["standard_shell", "spread_shot"],
        )
        _, backfilled = pm.backfill_unlocks(profile)
        assert backfilled == []

    def test_does_not_grant_future_unlocks(self):
        """Level 3 player should NOT receive level 4+ unlocks."""
        pm = _make_pm()
        profile = _profile(level=3, xp=350)
        new_profile, backfilled = pm.backfill_unlocks(profile)
        assert "spread_shot" not in backfilled
        assert "heavy_tank" not in backfilled

    def test_input_not_mutated(self):
        """backfill_unlocks must return a new dict, not modify the input."""
        pm = _make_pm()
        profile = _profile(level=4, xp=700, unlocked_weapons=["standard_shell"])
        original_weapons = list(profile["unlocked_weapons"])
        pm.backfill_unlocks(profile)
        assert profile["unlocked_weapons"] == original_weapons
