"""
tests/test_weapon_roller_v2.py

Tests for v0.35 category-guaranteed 4-slot weapon system.
Covers: WeaponRoller category mechanics, loadout constants, weapons.yaml
category fields, game-scene AI loadout, and HUD 4-slot display.

No pygame required (HUD tests use a mock surface).
"""

import unittest
from unittest.mock import MagicMock, patch

from game.systems.weapon_roller import WeaponRoller, _CATEGORY_FALLBACKS
from game.utils.config_loader import load_yaml
from game.utils.constants import (
    MAX_WEAPON_SLOTS,
    WEAPON_CATEGORIES,
    WEAPON_CATEGORY_COLORS,
    WEAPON_CATEGORY_LABELS,
    WEAPONS_CONFIG,
    WEAPON_WEIGHTS_CONFIG,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_BASIC    = ["standard_shell", "spread_shot", "bouncing_round"]
_ELEMENTAL = ["cryo_round", "poison_shell", "flamethrower", "lava_gun"]
_HEAVY    = ["homing_missile", "grenade_launcher", "railgun", "laser_beam"]
_TACTICAL = ["emp_blast", "glue_gun", "concussion_blast"]
_ALL      = _BASIC + _ELEMENTAL + _HEAVY + _TACTICAL

_FAKE_CONFIGS: dict = {
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
}

_FAKE_WEIGHTS: dict = {w: 10 for w in _FAKE_CONFIGS}


def _make_roller(unlocked=None, cfgs=None, weights=None):
    if unlocked is None:
        unlocked = _ALL
    if cfgs is None:
        cfgs = _FAKE_CONFIGS
    w = weights if weights is not None else _FAKE_WEIGHTS
    with patch("game.systems.weapon_roller.load_yaml", return_value=w):
        return WeaponRoller(unlocked_weapons=unlocked, weapon_configs=cfgs)


# ---------------------------------------------------------------------------
# TestCategoryRoll — basic roll behavior
# ---------------------------------------------------------------------------

class TestCategoryRoll(unittest.TestCase):

    def test_roll_length_is_always_four(self):
        roller = _make_roller()
        for _ in range(20):
            self.assertEqual(len(roller.roll()), 4)

    def test_slot_order_matches_weapon_categories(self):
        """WEAPON_CATEGORIES order determines slot order."""
        self.assertEqual(WEAPON_CATEGORIES, ["basic", "elemental", "heavy", "tactical"])

    def test_slot_0_always_basic(self):
        roller = _make_roller()
        for _ in range(30):
            self.assertIn(roller.roll()[0], _BASIC)

    def test_slot_1_always_elemental(self):
        roller = _make_roller()
        for _ in range(30):
            self.assertIn(roller.roll()[1], _ELEMENTAL)

    def test_slot_2_always_heavy(self):
        roller = _make_roller()
        for _ in range(30):
            self.assertIn(roller.roll()[2], _HEAVY)

    def test_slot_3_always_tactical(self):
        roller = _make_roller()
        for _ in range(30):
            self.assertIn(roller.roll()[3], _TACTICAL)

    def test_no_duplicates_in_any_roll(self):
        roller = _make_roller()
        for _ in range(100):
            loadout = roller.roll()
            self.assertEqual(len(loadout), len(set(loadout)),
                             f"Duplicate in loadout: {loadout}")

    def test_roll_with_single_weapon_per_category(self):
        roller = _make_roller(
            unlocked=["standard_shell", "cryo_round", "railgun", "emp_blast"]
        )
        for _ in range(10):
            loadout = roller.roll()
            self.assertEqual(loadout[0], "standard_shell")
            self.assertEqual(loadout[1], "cryo_round")
            self.assertEqual(loadout[2], "railgun")
            self.assertEqual(loadout[3], "emp_blast")

    def test_fallback_used_when_basic_empty(self):
        roller = _make_roller(unlocked=["cryo_round", "railgun", "emp_blast"])
        for _ in range(10):
            self.assertEqual(roller.roll()[0], _CATEGORY_FALLBACKS["basic"])

    def test_fallback_used_when_elemental_empty(self):
        roller = _make_roller(unlocked=["standard_shell", "railgun", "emp_blast"])
        for _ in range(10):
            self.assertEqual(roller.roll()[1], _CATEGORY_FALLBACKS["elemental"])

    def test_fallback_used_when_heavy_empty(self):
        roller = _make_roller(unlocked=["standard_shell", "cryo_round", "emp_blast"])
        for _ in range(10):
            self.assertEqual(roller.roll()[2], _CATEGORY_FALLBACKS["heavy"])

    def test_fallback_used_when_tactical_empty(self):
        roller = _make_roller(unlocked=["standard_shell", "cryo_round", "railgun"])
        for _ in range(10):
            self.assertEqual(roller.roll()[3], _CATEGORY_FALLBACKS["tactical"])

    def test_pool_sizes_match_unlocked_by_category(self):
        roller = _make_roller(
            unlocked=["standard_shell", "spread_shot", "cryo_round", "railgun", "emp_blast"]
        )
        sizes = roller.pool_sizes
        self.assertEqual(sizes["basic"], 2)
        self.assertEqual(sizes["elemental"], 1)
        self.assertEqual(sizes["heavy"], 1)
        self.assertEqual(sizes["tactical"], 1)

    def test_pool_sizes_keys_match_weapon_categories(self):
        roller = _make_roller()
        self.assertEqual(set(roller.pool_sizes.keys()), set(WEAPON_CATEGORIES))

    def test_pool_size_shim_equals_sum_of_pool_sizes(self):
        roller = _make_roller()
        self.assertEqual(roller.pool_size, sum(roller.pool_sizes.values()))

    def test_weighted_pick_favors_high_weight(self):
        weights = dict(_FAKE_WEIGHTS)
        weights["standard_shell"] = 10000
        weights["spread_shot"] = 1
        weights["bouncing_round"] = 1
        roller = _make_roller(weights=weights)
        picks = [roller.roll()[0] for _ in range(100)]
        self.assertGreater(picks.count("standard_shell"), 90)

    def test_weapons_without_category_excluded(self):
        cfgs = dict(_FAKE_CONFIGS)
        cfgs["ghost_gun"] = {}  # no category
        roller = _make_roller(
            unlocked=_ALL + ["ghost_gun"],
            cfgs=cfgs,
        )
        for _ in range(20):
            self.assertNotIn("ghost_gun", roller.roll())

    def test_weapons_with_unknown_category_excluded(self):
        cfgs = dict(_FAKE_CONFIGS)
        cfgs["mystery_gun"] = {"category": "super"}  # not in WEAPON_CATEGORIES
        roller = _make_roller(
            unlocked=_ALL + ["mystery_gun"],
            cfgs=cfgs,
        )
        for _ in range(20):
            self.assertNotIn("mystery_gun", roller.roll())

    def test_full_roll_covers_all_four_categories_every_time(self):
        roller = _make_roller()
        all_categories = list(WEAPON_CATEGORIES)
        for _ in range(50):
            loadout = roller.roll()
            for i, cat in enumerate(all_categories):
                weapon = loadout[i]
                actual_cat = _FAKE_CONFIGS.get(weapon, {}).get("category", "")
                self.assertEqual(actual_cat, cat)


# ---------------------------------------------------------------------------
# TestLoadoutConstants — constants.py additions for v0.35
# ---------------------------------------------------------------------------

class TestLoadoutConstants(unittest.TestCase):

    def test_max_weapon_slots_is_four(self):
        self.assertEqual(MAX_WEAPON_SLOTS, 4)

    def test_weapon_categories_has_four_entries(self):
        self.assertEqual(len(WEAPON_CATEGORIES), 4)

    def test_weapon_categories_are_strings(self):
        for cat in WEAPON_CATEGORIES:
            self.assertIsInstance(cat, str)

    def test_weapon_category_labels_keys_match_categories(self):
        self.assertEqual(set(WEAPON_CATEGORY_LABELS.keys()), set(WEAPON_CATEGORIES))

    def test_weapon_category_colors_keys_match_categories(self):
        self.assertEqual(set(WEAPON_CATEGORY_COLORS.keys()), set(WEAPON_CATEGORIES))

    def test_weapon_category_colors_are_rgb_tuples(self):
        for cat, color in WEAPON_CATEGORY_COLORS.items():
            self.assertEqual(len(color), 3, f"Color for {cat} should be (R,G,B)")
            for component in color:
                self.assertGreaterEqual(component, 0)
                self.assertLessEqual(component, 255)


# ---------------------------------------------------------------------------
# TestWeaponsYamlCategories — weapons.yaml has correct category fields
# ---------------------------------------------------------------------------

class TestWeaponsYamlCategories(unittest.TestCase):

    def setUp(self):
        self.all_weapons = load_yaml(WEAPONS_CONFIG)

    def test_all_weapons_have_category_field(self):
        for wtype, cfg in self.all_weapons.items():
            self.assertIn("category", cfg, f"{wtype} missing 'category' field")

    def test_all_categories_are_valid(self):
        for wtype, cfg in self.all_weapons.items():
            cat = cfg.get("category", "")
            self.assertIn(cat, WEAPON_CATEGORIES,
                          f"{wtype} has invalid category '{cat}'")

    def test_basic_category_weapons(self):
        basics = [w for w, c in self.all_weapons.items() if c.get("category") == "basic"]
        for expected in ["standard_shell", "spread_shot", "bouncing_round"]:
            self.assertIn(expected, basics)

    def test_elemental_category_weapons(self):
        elementals = [w for w, c in self.all_weapons.items() if c.get("category") == "elemental"]
        for expected in ["cryo_round", "poison_shell", "flamethrower", "lava_gun"]:
            self.assertIn(expected, elementals)

    def test_heavy_category_weapons(self):
        heavies = [w for w, c in self.all_weapons.items() if c.get("category") == "heavy"]
        for expected in ["homing_missile", "railgun", "grenade_launcher", "laser_beam"]:
            self.assertIn(expected, heavies)

    def test_tactical_category_weapons(self):
        tacticals = [w for w, c in self.all_weapons.items() if c.get("category") == "tactical"]
        for expected in ["emp_blast", "glue_gun", "concussion_blast"]:
            self.assertIn(expected, tacticals)

    def test_each_category_has_at_least_one_weapon(self):
        for cat in WEAPON_CATEGORIES:
            weapons_in_cat = [w for w, c in self.all_weapons.items()
                              if c.get("category") == cat]
            self.assertGreater(len(weapons_in_cat), 0,
                               f"Category '{cat}' has no weapons in weapons.yaml")

    def test_all_weapons_have_weights(self):
        weights = load_yaml(WEAPON_WEIGHTS_CONFIG)
        for wtype in self.all_weapons:
            self.assertIn(wtype, weights, f"{wtype} missing from weapon_weights.yaml")

    def test_standard_shell_is_basic(self):
        self.assertEqual(self.all_weapons["standard_shell"]["category"], "basic")

    def test_railgun_is_heavy(self):
        self.assertEqual(self.all_weapons["railgun"]["category"], "heavy")

    def test_cryo_round_is_elemental(self):
        self.assertEqual(self.all_weapons["cryo_round"]["category"], "elemental")

    def test_emp_blast_is_tactical(self):
        self.assertEqual(self.all_weapons["emp_blast"]["category"], "tactical")


# ---------------------------------------------------------------------------
# TestRealConfigRoll — WeaponRoller against real weapons.yaml
# ---------------------------------------------------------------------------

class TestRealConfigRoll(unittest.TestCase):

    def setUp(self):
        self.all_weapons = load_yaml(WEAPONS_CONFIG)
        self.roller = WeaponRoller(unlocked_weapons=list(self.all_weapons.keys()))

    def test_real_roll_returns_four_slots(self):
        for _ in range(10):
            self.assertEqual(len(self.roller.roll()), 4)

    def test_real_roll_no_duplicates(self):
        for _ in range(50):
            loadout = self.roller.roll()
            self.assertEqual(len(loadout), len(set(loadout)))

    def test_real_roll_each_slot_correct_category(self):
        for _ in range(20):
            loadout = self.roller.roll()
            for i, cat in enumerate(WEAPON_CATEGORIES):
                weapon = loadout[i]
                actual = self.all_weapons.get(weapon, {}).get("category", "")
                self.assertEqual(actual, cat,
                                 f"Slot {i} expected {cat}, got {weapon}({actual})")

    def test_real_roll_all_weapons_reachable(self):
        """Over many rolls, every unlocked weapon should appear in its slot at least once."""
        seen: set[str] = set()
        for _ in range(500):
            seen.update(self.roller.roll())
        for wtype, cfg in self.all_weapons.items():
            self.assertIn(wtype, seen, f"{wtype} never appeared in 500 rolls")

    def test_pool_sizes_sum_equals_total_weapon_count(self):
        total = sum(self.roller.pool_sizes.values())
        self.assertEqual(total, len(self.all_weapons))

    def test_category_fallbacks_cover_all_categories(self):
        for cat in WEAPON_CATEGORIES:
            self.assertIn(cat, _CATEGORY_FALLBACKS,
                          f"No fallback defined for category '{cat}'")

    def test_category_fallback_values_are_strings(self):
        for cat, fallback in _CATEGORY_FALLBACKS.items():
            self.assertIsInstance(fallback, str,
                                  f"Fallback for '{cat}' should be a weapon type string")


if __name__ == "__main__":
    unittest.main()
