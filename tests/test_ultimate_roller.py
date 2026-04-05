"""
tests/test_ultimate_roller.py

Unit tests for UltimateRoller (v0.33.5).

Tests run headless — no pygame or game scene dependencies.
UltimateRoller reads ultimate_weights.yaml via load_yaml; the yaml is patched
to a deterministic in-memory dict for all tests.
"""

import sys
import types
import unittest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Minimal stubs before any game module is imported
# ---------------------------------------------------------------------------

_pygame_stub = types.ModuleType("pygame")
_pygame_stub.error = type("error", (Exception,), {})
sys.modules.setdefault("pygame", _pygame_stub)

# ---------------------------------------------------------------------------
# Actual test weights (deterministic, all 6 keys)
# ---------------------------------------------------------------------------

_TEST_WEIGHTS = {
    "overdrive":  30,
    "fortress":   25,
    "barrage":    20,
    "phantom":    20,
    "lockdown":   15,
    "disruptor":  15,
}

_ALL_KEYS = set(_TEST_WEIGHTS.keys())


def _make_roller():
    from game.systems.ultimate_roller import UltimateRoller
    with patch("game.systems.ultimate_roller.load_yaml", return_value=_TEST_WEIGHTS):
        return UltimateRoller("fake/path.yaml")


# ---------------------------------------------------------------------------
# TestUltimateRoller
# ---------------------------------------------------------------------------

class TestUltimateRoller(unittest.TestCase):

    def test_roll_returns_valid_key(self):
        roller = _make_roller()
        result = roller.roll()
        self.assertIn(result, _ALL_KEYS)

    def test_roll_exclude_prevents_same_result(self):
        """Roll 100 times with exclude='barrage'; 'barrage' must never be returned."""
        roller = _make_roller()
        for _ in range(100):
            result = roller.roll(exclude="barrage")
            self.assertNotEqual(result, "barrage",
                                "roll(exclude='barrage') returned 'barrage'")

    def test_all_six_ultimates_reachable(self):
        """All 6 keys should appear at least once in 500 rolls."""
        roller = _make_roller()
        seen = set()
        for _ in range(500):
            seen.add(roller.roll())
        self.assertEqual(seen, _ALL_KEYS,
                         f"Not all ultimates reachable. Missing: {_ALL_KEYS - seen}")

    def test_weights_affect_distribution(self):
        """overdrive (weight 30) should appear more often than lockdown (weight 15) in 1000 rolls."""
        roller = _make_roller()
        counts = {k: 0 for k in _ALL_KEYS}
        for _ in range(1000):
            counts[roller.roll()] += 1
        self.assertGreater(
            counts["overdrive"], counts["lockdown"],
            f"overdrive ({counts['overdrive']}) not more common than lockdown ({counts['lockdown']})",
        )

    def test_roll_for_tank_returns_valid_key(self):
        roller = _make_roller()
        result = roller.roll_for_tank()
        self.assertIn(result, _ALL_KEYS)

    def test_pool_size_is_six(self):
        roller = _make_roller()
        self.assertEqual(roller.pool_size, 6)

    def test_pool_contains_all_keys(self):
        roller = _make_roller()
        self.assertEqual(set(roller.pool), _ALL_KEYS)

    def test_exclude_unknown_key_still_works(self):
        """Passing an exclude key not in the pool should not raise."""
        roller = _make_roller()
        result = roller.roll(exclude="nonexistent")
        self.assertIn(result, _ALL_KEYS)

    def test_exclude_all_but_one_returns_that_one(self):
        """When pool has only one candidate after exclusion, always return it."""
        # Only one key in pool
        with patch("game.systems.ultimate_roller.load_yaml",
                   return_value={"overdrive": 10, "barrage": 10}):
            from game.systems.ultimate_roller import UltimateRoller
            roller = UltimateRoller("fake.yaml")
        for _ in range(20):
            result = roller.roll(exclude="barrage")
            self.assertEqual(result, "overdrive")


if __name__ == "__main__":
    unittest.main()
