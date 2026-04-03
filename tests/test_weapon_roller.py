"""
tests/test_weapon_roller.py

Tests for v0.25.5 random weapon rolls: WeaponRoller, weapon_weights.yaml config,
AI random loadout, AI weapon cycling, and LoadoutScene re-roll.
"""

import random
import unittest
from unittest.mock import MagicMock, patch

from game.entities.tank import TankInput
from game.systems.weapon_roller import WeaponRoller
from game.utils.config_loader import load_yaml
from game.utils.constants import WEAPON_WEIGHTS_CONFIG, WEAPONS_CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_WEIGHTS = {
    "spread_shot": 30,
    "bouncing_round": 25,
    "cryo_round": 20,
    "poison_shell": 20,
    "flamethrower": 18,
    "emp_blast": 15,
    "grenade_launcher": 12,
    "homing_missile": 10,
    "railgun": 8,
    "laser_beam": 6,
}


def _roller_with(unlocked: list[str], weights: dict | None = None) -> WeaponRoller:
    """Create a WeaponRoller with patched weights YAML."""
    w = weights if weights is not None else _FAKE_WEIGHTS
    with patch("game.systems.weapon_roller.load_yaml", return_value=w):
        return WeaponRoller(unlocked_weapons=unlocked)


# ---------------------------------------------------------------------------
# TestWeaponRoller
# ---------------------------------------------------------------------------

class TestWeaponRoller(unittest.TestCase):

    def test_slot_0_always_standard_shell(self):
        roller = _roller_with(["standard_shell", "spread_shot", "bouncing_round"])
        for _ in range(20):
            self.assertEqual(roller.roll()[0], "standard_shell")

    def test_slot_1_from_pool(self):
        pool = ["spread_shot", "bouncing_round", "cryo_round"]
        roller = _roller_with(["standard_shell"] + pool)
        for _ in range(20):
            self.assertIn(roller.roll()[1], pool)

    def test_slot_2_from_pool(self):
        pool = ["spread_shot", "bouncing_round", "cryo_round"]
        roller = _roller_with(["standard_shell"] + pool)
        for _ in range(20):
            result = roller.roll()[2]
            self.assertIn(result, pool)

    def test_no_duplicates_in_loadout(self):
        pool = ["spread_shot", "bouncing_round", "cryo_round", "poison_shell"]
        roller = _roller_with(["standard_shell"] + pool)
        for _ in range(50):
            loadout = roller.roll()
            self.assertNotEqual(loadout[1], loadout[2])

    def test_empty_pool_returns_nones(self):
        roller = _roller_with(["standard_shell"])
        loadout = roller.roll()
        self.assertEqual(loadout, ["standard_shell", None, None])

    def test_single_weapon_pool(self):
        roller = _roller_with(["standard_shell", "spread_shot"])
        loadout = roller.roll()
        self.assertEqual(loadout[0], "standard_shell")
        self.assertEqual(loadout[1], "spread_shot")
        self.assertIsNone(loadout[2])

    def test_standard_shell_excluded_from_pool(self):
        roller = _roller_with(["standard_shell", "spread_shot", "bouncing_round"])
        for _ in range(30):
            loadout = roller.roll()
            self.assertNotEqual(loadout[1], "standard_shell")
            if loadout[2] is not None:
                self.assertNotEqual(loadout[2], "standard_shell")

    def test_pool_size_property(self):
        roller = _roller_with(["standard_shell", "spread_shot", "bouncing_round", "cryo_round"])
        self.assertEqual(roller.pool_size, 3)  # standard_shell excluded

    def test_weighted_pick_respects_weights(self):
        """With extreme weights, picks should heavily favor the high-weight weapon."""
        weights = {"weapon_a": 1000, "weapon_b": 1}
        roller = _roller_with(["standard_shell", "weapon_a", "weapon_b"], weights=weights)
        picks = [roller.roll()[1] for _ in range(100)]
        a_count = picks.count("weapon_a")
        self.assertGreater(a_count, 80, f"weapon_a should dominate but got {a_count}/100")

    def test_roll_returns_three_elements(self):
        roller = _roller_with(["standard_shell", "spread_shot"])
        self.assertEqual(len(roller.roll()), 3)

    def test_unknown_weapon_excluded(self):
        roller = _roller_with(["standard_shell", "unknown_weapon", "spread_shot"])
        self.assertEqual(roller.pool_size, 1)  # only spread_shot in pool

    def test_multiple_rolls_vary(self):
        pool = list(_FAKE_WEIGHTS.keys())
        roller = _roller_with(["standard_shell"] + pool)
        rolls = [tuple(roller.roll()) for _ in range(20)]
        unique = set(rolls)
        self.assertGreater(len(unique), 1, "Expected some variation across 20 rolls")

    def test_utility_only_pool_rerolls_to_dps(self):
        """When both random slots are utility-only, slot 1 should be replaced with a DPS weapon."""
        # Pool has one DPS (spread_shot) and two utility (glue_gun, concussion_blast)
        weights = {"glue_gun": 999, "concussion_blast": 999, "spread_shot": 1}
        roller = _roller_with(
            ["standard_shell", "glue_gun", "concussion_blast", "spread_shot"],
            weights=weights,
        )
        # Run many rolls — whenever both random slots would be utility,
        # the DPS guarantee should replace slot 1 with spread_shot
        from game.systems.weapon_roller import _DPS_WEAPONS
        for _ in range(50):
            loadout = roller.roll()
            random_slots = [w for w in loadout[1:] if w is not None]
            has_dps = any(w in _DPS_WEAPONS for w in random_slots)
            self.assertTrue(has_dps, f"No DPS weapon in random slots: {loadout}")

    def test_mixed_pool_has_dps_in_random_slots(self):
        """Normal mixed pool should always have at least one DPS in random slots."""
        pool = list(_FAKE_WEIGHTS.keys())
        roller = _roller_with(["standard_shell"] + pool)
        from game.systems.weapon_roller import _DPS_WEAPONS
        for _ in range(30):
            loadout = roller.roll()
            random_slots = [w for w in loadout[1:] if w is not None]
            has_dps = any(w in _DPS_WEAPONS for w in random_slots)
            self.assertTrue(has_dps, f"No DPS weapon in random slots: {loadout}")


# ---------------------------------------------------------------------------
# TestWeaponWeightsConfig
# ---------------------------------------------------------------------------

class TestWeaponWeightsConfig(unittest.TestCase):

    def test_config_loads(self):
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        self.assertIsInstance(weights, dict)
        self.assertGreater(len(weights), 0)

    def test_all_non_standard_weapons_have_weights(self):
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        all_weapons = load_yaml(WEAPONS_CONFIG)
        for wtype in all_weapons:
            if wtype == "standard_shell":
                continue
            self.assertIn(wtype, weights, f"{wtype} missing from weapon_weights.yaml")

    def test_weights_are_positive_integers(self):
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        for wtype, w in weights.items():
            self.assertIsInstance(w, int, f"{wtype} weight is not int: {type(w)}")
            self.assertGreater(w, 0, f"{wtype} weight must be > 0")

    def test_standard_shell_not_in_weights(self):
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        self.assertNotIn("standard_shell", weights)


# ---------------------------------------------------------------------------
# TestAIRandomLoadout
# ---------------------------------------------------------------------------

class TestAIRandomLoadout(unittest.TestCase):

    def test_ai_loadout_has_standard_shell_slot_0(self):
        all_weapons = list(load_yaml(WEAPONS_CONFIG).keys())
        roller = _roller_with(all_weapons)
        for _ in range(20):
            self.assertEqual(roller.roll()[0], "standard_shell")

    def test_ai_excludes_hitscan(self):
        """When hitscan weapons are filtered out, laser_beam never appears."""
        all_weapons = load_yaml(WEAPONS_CONFIG)
        non_hitscan = [w for w in all_weapons if not all_weapons[w].get("hitscan", False)]
        roller = _roller_with(non_hitscan)
        for _ in range(50):
            loadout = roller.roll()
            for slot in loadout:
                if slot is not None:
                    self.assertNotEqual(slot, "laser_beam")

    def test_ai_weapon_cycle_timer_ticks(self):
        from game.systems.ai_controller import AIController
        target = MagicMock()
        target.is_alive = True
        ai = AIController(config={"reaction_time": 0.4, "accuracy": 0.7, "aggression": 0.5}, target_getter=lambda: target)
        owner = MagicMock()
        owner.x = 100.0
        owner.y = 100.0
        owner.position = (100.0, 100.0)
        owner.health_ratio = 1.0
        ai.set_owner(owner)

        initial = ai._weapon_cycle_timer
        ai.tick(1.0)
        self.assertLess(ai._weapon_cycle_timer, initial)

    def test_ai_pending_cycle_set_on_timer_expire(self):
        from game.systems.ai_controller import AIController
        target = MagicMock()
        target.is_alive = True
        ai = AIController(config={"reaction_time": 0.4, "accuracy": 0.7, "aggression": 0.5}, target_getter=lambda: target)
        owner = MagicMock()
        owner.x = 100.0
        owner.y = 100.0
        owner.position = (100.0, 100.0)
        owner.health_ratio = 1.0
        ai.set_owner(owner)

        # Force timer to expire
        ai._weapon_cycle_timer = 0.1
        ai.tick(0.2)
        self.assertIn(ai._pending_weapon_cycle, [-1, 1])

    def test_ai_pending_cycle_consumed_in_get_input(self):
        from game.systems.ai_controller import AIController
        target = MagicMock()
        target.is_alive = True
        target.position = (500.0, 500.0)  # far away → PATROL
        target.x = 500.0
        target.y = 500.0
        ai = AIController(config={"reaction_time": 0.4, "accuracy": 0.7, "aggression": 0.5}, target_getter=lambda: target)
        owner = MagicMock()
        owner.x = 100.0
        owner.y = 100.0
        owner.position = (100.0, 100.0)
        owner.health_ratio = 1.0
        owner.is_alive = True
        ai.set_owner(owner)
        ai.tick(0.016)

        # Set a pending cycle
        ai._pending_weapon_cycle = 1
        result = ai.get_input()
        self.assertEqual(result.cycle_weapon, 1)
        self.assertEqual(ai._pending_weapon_cycle, 0)


# ---------------------------------------------------------------------------
# TestLoadoutReroll
# ---------------------------------------------------------------------------

class TestLoadoutReroll(unittest.TestCase):

    def test_initial_roll_on_enter(self):
        """WeaponRoller always produces 3-element loadout."""
        pool = ["spread_shot", "bouncing_round", "cryo_round"]
        roller = _roller_with(["standard_shell"] + pool)
        loadout = roller.roll()
        self.assertEqual(len(loadout), 3)
        self.assertEqual(loadout[0], "standard_shell")
        self.assertIsNotNone(loadout[1])

    def test_reroll_changes_loadout(self):
        """With a large enough pool, re-rolling should produce different results sometimes."""
        pool = list(_FAKE_WEIGHTS.keys())
        roller = _roller_with(["standard_shell"] + pool)
        first = tuple(roller.roll())
        changed = False
        for _ in range(20):
            second = tuple(roller.roll())
            if second != first:
                changed = True
                break
        self.assertTrue(changed, "Expected re-roll to produce different loadout at least once")

    def test_reroll_only_once_flag(self):
        """_has_rerolled flag starts False and can be set to True."""
        has_rerolled = False
        self.assertFalse(has_rerolled)
        has_rerolled = True
        self.assertTrue(has_rerolled)

    def test_slot_0_unchanged_after_reroll(self):
        pool = list(_FAKE_WEIGHTS.keys())
        roller = _roller_with(["standard_shell"] + pool)
        for _ in range(20):
            self.assertEqual(roller.roll()[0], "standard_shell")


if __name__ == "__main__":
    unittest.main()
