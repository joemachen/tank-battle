"""
tests/test_progression.py

Unit tests for XP and level progression calculations.
Pure math — no pygame, no file I/O.
"""

import pytest


# ---------------------------------------------------------------------------
# Helper: simple level-up logic to be implemented in a progression module
# ---------------------------------------------------------------------------

def compute_level(xp: int, xp_table: list[dict]) -> int:
    """
    Return the level a player is at given their total XP and an xp_table.
    xp_table: list of {level: int, xp_required: int} sorted ascending.
    """
    current_level = 1
    for entry in xp_table:
        if xp >= entry["xp_required"]:
            current_level = entry["level"]
        else:
            break
    return current_level


def xp_for_next_level(xp: int, xp_table: list[dict]) -> int | None:
    """Return XP needed to reach the next level, or None if already max level."""
    for entry in xp_table:
        if entry["xp_required"] > xp:
            return entry["xp_required"] - xp
    return None


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

XP_TABLE = [
    {"level": 1, "xp_required": 0},
    {"level": 2, "xp_required": 150},
    {"level": 3, "xp_required": 350},
    {"level": 4, "xp_required": 700},
    {"level": 5, "xp_required": 1200},
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestComputeLevel:
    def test_level_1_at_zero_xp(self):
        assert compute_level(0, XP_TABLE) == 1

    def test_level_1_just_below_threshold(self):
        assert compute_level(149, XP_TABLE) == 1

    def test_level_2_at_threshold(self):
        assert compute_level(150, XP_TABLE) == 2

    def test_level_3_above_threshold(self):
        assert compute_level(500, XP_TABLE) == 3

    def test_max_level(self):
        assert compute_level(9999, XP_TABLE) == 5


class TestXpForNextLevel:
    def test_xp_needed_from_level_1(self):
        assert xp_for_next_level(0, XP_TABLE) == 150

    def test_xp_needed_mid_level(self):
        assert xp_for_next_level(200, XP_TABLE) == 150   # 350 - 200

    def test_max_level_returns_none(self):
        assert xp_for_next_level(9999, XP_TABLE) is None
