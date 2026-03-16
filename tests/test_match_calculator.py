"""
tests/test_match_calculator.py

Unit tests for MatchCalculator and MatchResult.
Pure math — no pygame, no file I/O.
"""

import pytest

from game.systems.match_calculator import MatchCalculator, MatchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build(
    won=False,
    survived=False,
    kills=0,
    shots_fired=0,
    shots_hit=0,
    time_elapsed=60.0,
    damage_dealt=0,
    damage_taken=0,
) -> MatchResult:
    return MatchCalculator.build(
        won=won,
        survived=survived,
        kills=kills,
        shots_fired=shots_fired,
        shots_hit=shots_hit,
        time_elapsed=time_elapsed,
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
    )


# ---------------------------------------------------------------------------
# MatchCalculator.build — accuracy and xp_earned are auto-computed
# ---------------------------------------------------------------------------

class TestMatchCalculatorBuild:
    def test_accuracy_perfect(self):
        r = _build(shots_fired=10, shots_hit=10)
        assert r.accuracy == pytest.approx(1.0)

    def test_accuracy_half(self):
        r = _build(shots_fired=10, shots_hit=5)
        assert r.accuracy == pytest.approx(0.5)

    def test_accuracy_zero_shots_fired(self):
        """No divide-by-zero — accuracy is 0.0 when nothing was fired."""
        r = _build(shots_fired=0, shots_hit=0)
        assert r.accuracy == 0.0

    def test_accuracy_clamped_to_one(self):
        """shots_hit > shots_fired should not exceed 1.0 (defensive)."""
        r = _build(shots_fired=5, shots_hit=99)
        assert r.accuracy <= 1.0

    def test_xp_earned_is_set(self):
        r = _build(won=True, kills=2)
        assert r.xp_earned > 0

    def test_xp_earned_is_int(self):
        r = _build(won=True, kills=1, shots_fired=4, shots_hit=4)
        assert isinstance(r.xp_earned, int)


# ---------------------------------------------------------------------------
# compute_xp — check each component
# ---------------------------------------------------------------------------

class TestComputeXp:
    def test_participation_only_on_loss(self):
        """A loss with 0 kills and 0 accuracy still earns XP_PARTICIPATION."""
        r = _build(won=False, survived=False, kills=0, shots_fired=0)
        assert r.xp_earned == 10   # XP_PARTICIPATION

    def test_win_bonus_added(self):
        loss_xp = _build(won=False).xp_earned
        win_xp = _build(won=True).xp_earned
        assert win_xp == loss_xp + 100  # XP_WIN

    def test_kill_bonus_per_kill(self):
        base = _build(won=False, kills=0).xp_earned
        two_kills = _build(won=False, kills=2).xp_earned
        assert two_kills == base + 2 * 40   # 2 × XP_KILL

    def test_survival_bonus_added_when_survived(self):
        no_survive = _build(survived=False).xp_earned
        survive = _build(survived=True).xp_earned
        assert survive == no_survive + 25   # XP_SURVIVAL_BONUS

    def test_accuracy_bonus_max_at_perfect(self):
        perfect = _build(shots_fired=1, shots_hit=1).xp_earned
        zero_acc = _build(shots_fired=1, shots_hit=0).xp_earned
        assert perfect == zero_acc + 50   # XP_ACCURACY_BONUS_MAX

    def test_full_win_with_2_kills_perfect_accuracy(self):
        """
        XP_PARTICIPATION(10) + XP_WIN(100) + 2×XP_KILL(80)
        + XP_SURVIVAL_BONUS(25) + accuracy_bonus(50) = 265
        """
        r = _build(won=True, survived=True, kills=2, shots_fired=8, shots_hit=8)
        assert r.xp_earned == 265

    def test_compute_xp_returns_int(self):
        r = _build(won=True, survived=True, kills=1, shots_fired=3, shots_hit=2)
        result = MatchCalculator.compute_xp(r)
        assert isinstance(result, int)
