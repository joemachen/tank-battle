"""
game/systems/match_calculator.py

MatchResult dataclass + MatchCalculator for computing end-of-match statistics
and XP rewards.

Design notes:
  - MatchResult is a plain data container; all logic lives in MatchCalculator.
  - compute_xp() is a pure function — no I/O, no side effects.
  - build() is the factory that computes accuracy and XP in one call, so
    callers never have to touch xp_earned directly.
"""

from dataclasses import dataclass

from game.utils.constants import (
    XP_ACCURACY_BONUS_MAX,
    XP_KILL,
    XP_PARTICIPATION,
    XP_SURVIVAL_BONUS,
    XP_WIN,
)


@dataclass
class MatchResult:
    """
    Complete record of a single match outcome.
    Passed from GameplayScene → GameOverScene via SceneManager kwargs.
    """

    won: bool
    survived: bool
    kills: int
    shots_fired: int
    shots_hit: int
    accuracy: float          # shots_hit / shots_fired; 0.0 when no shots fired
    time_elapsed: float      # seconds from match start to end
    damage_dealt: int        # total damage dealt by player bullets to tanks
    damage_taken: int        # total damage the player tank received
    xp_earned: int = 0       # filled by MatchCalculator.compute_xp()


class MatchCalculator:
    """
    Stateless helper that computes XP and builds MatchResult instances.
    Instantiation is optional — all methods are static.
    """

    @staticmethod
    def compute_xp(result: MatchResult) -> int:
        """
        Calculate XP earned from a completed match.

        Formula:
          XP_PARTICIPATION       — always awarded, just for playing
          + XP_WIN               — awarded for winning
          + XP_KILL * kills      — per AI tank destroyed
          + XP_SURVIVAL_BONUS    — awarded if player survived to end
          + int(accuracy * XP_ACCURACY_BONUS_MAX)   — 0–50 based on aim
        """
        xp = XP_PARTICIPATION
        if result.won:
            xp += XP_WIN
        xp += XP_KILL * result.kills
        if result.survived:
            xp += XP_SURVIVAL_BONUS
        xp += int(result.accuracy * XP_ACCURACY_BONUS_MAX)
        return int(xp)

    @staticmethod
    def build(
        won: bool,
        survived: bool,
        kills: int,
        shots_fired: int,
        shots_hit: int,
        time_elapsed: float,
        damage_dealt: int,
        damage_taken: int,
    ) -> MatchResult:
        """
        Factory: construct a fully-computed MatchResult.
        Calculates accuracy (safe for zero shots fired) and fills xp_earned.
        """
        accuracy = shots_hit / shots_fired if shots_fired > 0 else 0.0
        accuracy = max(0.0, min(1.0, accuracy))
        result = MatchResult(
            won=won,
            survived=survived,
            kills=kills,
            shots_fired=shots_fired,
            shots_hit=shots_hit,
            accuracy=accuracy,
            time_elapsed=time_elapsed,
            damage_dealt=damage_dealt,
            damage_taken=damage_taken,
            xp_earned=0,
        )
        result.xp_earned = MatchCalculator.compute_xp(result)
        return result
