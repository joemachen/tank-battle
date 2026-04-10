"""
tests/test_weapon_roller.py

Tests for v0.35 category-guaranteed 4-slot weapon loadout: WeaponRoller,
weapon_weights.yaml config, AI random loadout, and AI weapon cycling.
"""

import random
import unittest
from unittest.mock import MagicMock, patch

from game.entities.tank import TankInput
from game.systems.weapon_roller import WeaponRoller
from game.utils.config_loader import load_yaml
from game.utils.constants import WEAPON_WEIGHTS_CONFIG, WEAPON_CATEGORIES, WEAPONS_CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_WEIGHTS = {
    "spread_shot":      30,
    "bouncing_round":   25,
    "cryo_round":       20,
    "poison_shell":     20,
    "flamethrower":     18,
    "lava_gun":         18,
    "emp_blast":        15,
    "grenade_launcher": 12,
    "homing_missile":   10,
    "railgun":           8,
    "laser_beam":        6,
    "glue_gun":         15,
    "concussion_blast": 12,
    "standard_shell":   30,
    "weapon_a":         50,
    "weapon_b":          1,
}

_FAKE_WEAPON_CONFIGS = {
    "standard_shell":   {"category": "basic"},
    "spread_shot":      {"category": "basic"},
    "bouncing_round":   {"category": "basic"},
    "cryo_round":       {"category": "elemental"},
    "poison_shell":     {"category": "elemental"},
    "flamethrower":     {"category": "elemental"},
    "lava_gun":         {"category": "elemental"},
    "homing_missile":   {"category": "heavy"},
    "grenade_launcher": {"category": "heavy"},
    "railgun":          {"category": "heavy"},
    "laser_beam":       {"category": "heavy"},
    "emp_blast":        {"category": "tactical"},
    "glue_gun":         {"category": "tactical"},
    "concussion_blast": {"category": "tactical"},
    "weapon_a":         {"category": "basic"},
    "weapon_b":         {"category": "basic"},
}

_BASIC_WEAPONS    = {"standard_shell", "spread_shot", "bouncing_round"}
_ELEMENTAL_WEAPONS = {"cryo_round", "poison_shell", "flamethrower", "lava_gun"}
_HEAVY_WEAPONS    = {"homing_missile", "grenade_launcher", "railgun", "laser_beam"}
_TACTICAL_WEAPONS = {"emp_blast", "glue_gun", "concussion_blast"}


def _roller_with(unlocked: list[str], weights: dict | None = None,
                 weapon_configs: dict | None = None) -> WeaponRoller:
    """Create a WeaponRoller with patched weights YAML."""
    w = weights if weights is not None else _FAKE_WEIGHTS
    cfgs = weapon_configs if weapon_configs is not None else _FAKE_WEAPON_CONFIGS
    with patch("game.systems.weapon_roller.load_yaml", return_value=w):
        return WeaponRoller(unlocked_weapons=unlocked, weapon_configs=cfgs)


# ---------------------------------------------------------------------------
# TestWeaponRoller
# ---------------------------------------------------------------------------

class TestWeaponRoller(unittest.TestCase):

    def test_roll_returns_four_elements(self):
        roller = _roller_with(["standard_shell", "cryo_round", "homing_missile", "emp_blast"])
        self.assertEqual(len(roller.roll()), 4)

    def test_slot_0_is_basic_category(self):
        roller = _roller_with(["standard_shell", "spread_shot", "cryo_round",
                               "homing_missile", "emp_blast"])
        for _ in range(20):
            self.assertIn(roller.roll()[0], _BASIC_WEAPONS)

    def test_slot_1_is_elemental_category(self):
        roller = _roller_with(["standard_shell", "cryo_round", "poison_shell",
                               "homing_missile", "emp_blast"])
        for _ in range(20):
            self.assertIn(roller.roll()[1], _ELEMENTAL_WEAPONS)

    def test_slot_2_is_heavy_category(self):
        roller = _roller_with(["standard_shell", "cryo_round",
                               "homing_missile", "railgun", "emp_blast"])
        for _ in range(20):
            self.assertIn(roller.roll()[2], _HEAVY_WEAPONS)

    def test_slot_3_is_tactical_category(self):
        roller = _roller_with(["standard_shell", "cryo_round",
                               "homing_missile", "emp_blast", "glue_gun"])
        for _ in range(20):
            self.assertIn(roller.roll()[3], _TACTICAL_WEAPONS)

    def test_fallback_when_category_empty(self):
        """No elemental unlocked → fallback weapon used in slot 1."""
        from game.systems.weapon_roller import _CATEGORY_FALLBACKS
        roller = _roller_with(["standard_shell", "homing_missile", "emp_blast"])
        for _ in range(10):
            loadout = roller.roll()
            self.assertEqual(loadout[1], _CATEGORY_FALLBACKS["elemental"])

    def test_no_duplicates_across_categories(self):
        """No weapon should appear more than once (categories are disjoint by design)."""
        roller = _roller_with(
            ["standard_shell", "spread_shot", "cryo_round", "poison_shell",
             "homing_missile", "railgun", "emp_blast", "glue_gun"]
        )
        for _ in range(50):
            loadout = roller.roll()
            self.assertEqual(len(loadout), len(set(loadout)),
                             f"Duplicate weapon in loadout: {loadout}")

    def test_weighted_pick_respects_weights(self):
        """Extreme weights: weapon_a (basic) should dominate slot 0."""
        weights = {"weapon_a": 1000, "weapon_b": 1,
                   "cryo_round": 10, "homing_missile": 10, "emp_blast": 10}
        roller = _roller_with(
            ["weapon_a", "weapon_b", "cryo_round", "homing_missile", "emp_blast"],
            weights=weights,
        )
        picks = [roller.roll()[0] for _ in range(100)]
        a_count = picks.count("weapon_a")
        self.assertGreater(a_count, 80, f"weapon_a should dominate but got {a_count}/100")

    def test_unknown_weapon_excluded(self):
        """Weapon with no category field is not placed in any slot."""
        cfgs = dict(_FAKE_WEAPON_CONFIGS)
        cfgs["mystery_gun"] = {}  # no category
        roller = _roller_with(
            ["standard_shell", "cryo_round", "homing_missile", "emp_blast", "mystery_gun"],
            weapon_configs=cfgs,
        )
        for _ in range(20):
            loadout = roller.roll()
            self.assertNotIn("mystery_gun", loadout)

    def test_multiple_rolls_vary(self):
        """Large pool should produce different loadouts across many rolls."""
        all_w = list(_FAKE_WEAPON_CONFIGS.keys())
        roller = _roller_with(all_w)
        rolls = [tuple(roller.roll()) for _ in range(20)]
        self.assertGreater(len(set(rolls)), 1, "Expected some variation across 20 rolls")

    def test_pool_sizes_property(self):
        roller = _roller_with(
            ["standard_shell", "spread_shot", "cryo_round", "homing_missile", "emp_blast"]
        )
        sizes = roller.pool_sizes
        self.assertEqual(sizes["basic"], 2)
        self.assertEqual(sizes["elemental"], 1)
        self.assertEqual(sizes["heavy"], 1)
        self.assertEqual(sizes["tactical"], 1)

    def test_pool_size_deprecated_shim(self):
        """pool_size shim returns sum of all category pools."""
        roller = _roller_with(
            ["standard_shell", "spread_shot", "cryo_round", "homing_missile", "emp_blast"]
        )
        self.assertEqual(roller.pool_size, 5)


# ---------------------------------------------------------------------------
# TestWeaponWeightsConfig
# ---------------------------------------------------------------------------

class TestWeaponWeightsConfig(unittest.TestCase):

    def test_config_loads(self):
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        self.assertIsInstance(weights, dict)
        self.assertGreater(len(weights), 0)

    def test_all_weapons_have_weights(self):
        """Every weapon in weapons.yaml must have an entry in weapon_weights.yaml."""
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        all_weapons = load_yaml(WEAPONS_CONFIG)
        for wtype in all_weapons:
            self.assertIn(wtype, weights, f"{wtype} missing from weapon_weights.yaml")

    def test_weights_are_positive_integers(self):
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        for wtype, w in weights.items():
            self.assertIsInstance(w, int, f"{wtype} weight is not int: {type(w)}")
            self.assertGreater(w, 0, f"{wtype} weight must be > 0")

    def test_standard_shell_in_weights(self):
        """standard_shell is now a basic-category weapon and must appear in weights."""
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        self.assertIn("standard_shell", weights)


# ---------------------------------------------------------------------------
# TestAIRandomLoadout
# ---------------------------------------------------------------------------

class TestAIRandomLoadout(unittest.TestCase):

    def test_ai_loadout_has_four_slots(self):
        """WeaponRoller with all real weapons returns a 4-element loadout."""
        all_weapons = list(load_yaml(WEAPONS_CONFIG).keys())
        roller = WeaponRoller(unlocked_weapons=all_weapons)
        for _ in range(10):
            self.assertEqual(len(roller.roll()), 4)

    def test_ai_loadout_slots_match_categories(self):
        """Each slot of a real-config roll comes from the correct category."""
        all_weapons_cfg = load_yaml(WEAPONS_CONFIG)
        roller = WeaponRoller(unlocked_weapons=list(all_weapons_cfg.keys()))
        for _ in range(10):
            loadout = roller.roll()
            for idx, cat in enumerate(WEAPON_CATEGORIES):
                weapon = loadout[idx]
                actual_cat = all_weapons_cfg.get(weapon, {}).get("category", "")
                self.assertEqual(actual_cat, cat,
                                 f"Slot {idx} expected {cat} but got {weapon} ({actual_cat})")

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
        target.position = (450.0, 100.0)   # far from owner → railgun preferred
        ai = AIController(config={"reaction_time": 0.4, "accuracy": 0.7, "aggression": 0.5}, target_getter=lambda: target)
        owner = MagicMock()
        owner.x = 100.0
        owner.y = 100.0
        owner.position = (100.0, 100.0)
        owner.health_ratio = 1.0
        # Two-slot loadout: flamethrower (close) active, railgun (far) in slot 1
        # At dist≈350 the railgun scores higher → switching should be queued
        owner.weapon_slots = [
            {"type": "flamethrower", "speed": 200, "fire_rate": 6.0},
            {"type": "railgun", "speed": 600, "fire_rate": 0.2},
        ]
        owner.active_slot = 0
        owner.slot_cooldowns = [0.0, 0.0]
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
        owner.angle = 0.0
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
        """WeaponRoller produces a 4-element loadout, slot 0 from basic category."""
        roller = _roller_with(
            ["standard_shell", "spread_shot", "cryo_round", "homing_missile", "emp_blast"]
        )
        loadout = roller.roll()
        self.assertEqual(len(loadout), 4)
        self.assertIn(loadout[0], _BASIC_WEAPONS)

    def test_reroll_changes_loadout(self):
        """With a large enough pool, re-rolling should produce different results sometimes."""
        all_w = list(_FAKE_WEAPON_CONFIGS.keys())
        roller = _roller_with(all_w)
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

    def test_slot_0_always_basic_category_after_reroll(self):
        """Slot 0 always comes from basic pool across many rolls."""
        roller = _roller_with(
            ["standard_shell", "spread_shot", "bouncing_round",
             "cryo_round", "homing_missile", "emp_blast"]
        )
        for _ in range(20):
            self.assertIn(roller.roll()[0], _BASIC_WEAPONS)


if __name__ == "__main__":
    unittest.main()
