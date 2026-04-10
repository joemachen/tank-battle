"""
tests/test_ai_elemental_awareness.py

Tests for v0.36 AI Elemental Awareness:
  - _WEAPON_DAMAGE_TYPES mapping
  - _ELEMENTAL_COMBOS table
  - _combo_bonus() method
  - _setup_bonus() method
  - _score_weapon_slot() integration with elemental terms
  - elemental_awareness scaling by difficulty
  - ai_difficulty.yaml config values
  - end-to-end: hard AI scores combo-completing weapon highest

No pygame required. AIController is instantiated with minimal MockTank stubs.
"""

import unittest
from unittest.mock import MagicMock

from game.systems.ai_controller import (
    AIController,
    _ELEMENTAL_COMBOS,
    _WEAPON_DAMAGE_TYPES,
)
from game.utils.config_loader import load_yaml
from game.utils.constants import AI_DIFFICULTY_CONFIG


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _MockEffect:
    """Minimal stand-in for StatusEffect — only needs to exist as a dict key value."""
    def __init__(self, effect_type: str):
        self.effect_type = effect_type


def _make_target(effects: dict | None = None):
    """Build a mock target tank with optional active combat_effects."""
    t = MagicMock()
    t.combat_effects = effects or {}
    t.position = (300.0, 300.0)
    t.is_alive = True
    return t


def _make_owner(wtype: str = "standard_shell", dist: float = 250.0):
    """Build a minimal mock AI owner with a single weapon slot."""
    owner = MagicMock()
    owner.x = 100.0
    owner.y = 100.0
    owner.position = (100.0, 100.0)
    owner.health_ratio = 1.0
    owner.weapon_slots = [{"type": wtype}]
    owner.active_slot = 0
    owner.slot_cooldowns = [0.0]
    return owner


def _make_ai(elemental_awareness: float = 1.0) -> AIController:
    target = _make_target()
    ai = AIController(
        config={
            "reaction_time": 0.4,
            "accuracy": 0.7,
            "aggression": 0.5,
            "elemental_awareness": elemental_awareness,
        },
        target_getter=lambda: target,
    )
    return ai


# ---------------------------------------------------------------------------
# 1. TestWeaponDamageTypes
# ---------------------------------------------------------------------------

class TestWeaponDamageTypes(unittest.TestCase):

    def test_cryo_round_maps_to_ice(self):
        self.assertEqual(_WEAPON_DAMAGE_TYPES["cryo_round"], "ice")

    def test_poison_shell_maps_to_poison(self):
        self.assertEqual(_WEAPON_DAMAGE_TYPES["poison_shell"], "poison")

    def test_flamethrower_maps_to_fire(self):
        self.assertEqual(_WEAPON_DAMAGE_TYPES["flamethrower"], "fire")

    def test_lava_gun_maps_to_fire(self):
        self.assertEqual(_WEAPON_DAMAGE_TYPES["lava_gun"], "fire")

    def test_emp_blast_maps_to_electric(self):
        self.assertEqual(_WEAPON_DAMAGE_TYPES["emp_blast"], "electric")

    def test_standard_shell_absent(self):
        self.assertNotIn("standard_shell", _WEAPON_DAMAGE_TYPES)

    def test_railgun_absent(self):
        self.assertNotIn("railgun", _WEAPON_DAMAGE_TYPES)

    def test_homing_missile_absent(self):
        self.assertNotIn("homing_missile", _WEAPON_DAMAGE_TYPES)

    def test_all_values_are_strings(self):
        for wtype, dmg in _WEAPON_DAMAGE_TYPES.items():
            self.assertIsInstance(dmg, str, f"{wtype} should map to a string")

    def test_all_values_are_valid_effect_types(self):
        valid = {"ice", "fire", "poison", "electric"}
        for wtype, dmg in _WEAPON_DAMAGE_TYPES.items():
            self.assertIn(dmg, valid, f"{wtype} → {dmg} is not a valid effect type")


# ---------------------------------------------------------------------------
# 2. TestElementalCombosTable
# ---------------------------------------------------------------------------

class TestElementalCombosTable(unittest.TestCase):

    def test_has_three_combos(self):
        self.assertEqual(len(_ELEMENTAL_COMBOS), 3)

    def test_steam_burst_present(self):
        combos = [(c["requires"], c["completes"]) for c in _ELEMENTAL_COMBOS]
        self.assertIn(("ice", "fire"), combos)

    def test_accelerated_burn_present(self):
        combos = [(c["requires"], c["completes"]) for c in _ELEMENTAL_COMBOS]
        self.assertIn(("poison", "fire"), combos)

    def test_deep_freeze_present(self):
        combos = [(c["requires"], c["completes"]) for c in _ELEMENTAL_COMBOS]
        self.assertIn(("ice", "electric"), combos)

    def test_all_combos_have_value(self):
        for combo in _ELEMENTAL_COMBOS:
            self.assertIn("value", combo)
            self.assertGreater(combo["value"], 0.0)

    def test_deep_freeze_highest_value(self):
        deep_freeze = next(c for c in _ELEMENTAL_COMBOS
                           if c["requires"] == "ice" and c["completes"] == "electric")
        other_values = [c["value"] for c in _ELEMENTAL_COMBOS if c is not deep_freeze]
        self.assertGreater(deep_freeze["value"], max(other_values))


# ---------------------------------------------------------------------------
# 3. TestComboBonus
# ---------------------------------------------------------------------------

class TestComboBonus(unittest.TestCase):

    def setUp(self):
        self.ai = _make_ai(elemental_awareness=1.0)
        owner = _make_owner()
        self.ai.set_owner(owner)

    def test_fire_on_ice_target_gives_steam_burst_bonus(self):
        target = _make_target({"ice": _MockEffect("ice")})
        bonus = self.ai._combo_bonus("flamethrower", target)
        self.assertAlmostEqual(bonus, 0.60, places=5)

    def test_fire_on_poison_target_gives_accelerated_burn_bonus(self):
        target = _make_target({"poison": _MockEffect("poison")})
        bonus = self.ai._combo_bonus("flamethrower", target)
        self.assertAlmostEqual(bonus, 0.50, places=5)

    def test_electric_on_ice_target_gives_deep_freeze_bonus(self):
        target = _make_target({"ice": _MockEffect("ice")})
        bonus = self.ai._combo_bonus("emp_blast", target)
        self.assertAlmostEqual(bonus, 0.70, places=5)

    def test_no_bonus_when_prereq_missing(self):
        target = _make_target({})   # no active effects
        bonus = self.ai._combo_bonus("emp_blast", target)
        self.assertAlmostEqual(bonus, 0.0, places=5)

    def test_no_bonus_for_non_elemental_weapon(self):
        target = _make_target({"ice": _MockEffect("ice")})
        bonus = self.ai._combo_bonus("railgun", target)
        self.assertAlmostEqual(bonus, 0.0, places=5)

    def test_no_bonus_when_target_is_none(self):
        bonus = self.ai._combo_bonus("flamethrower", None)
        self.assertAlmostEqual(bonus, 0.0, places=5)

    def test_best_combo_selected_when_multiple_effects_active(self):
        """ice + poison active — flamethrower can complete both combos, takes higher value."""
        target = _make_target({
            "ice":    _MockEffect("ice"),
            "poison": _MockEffect("poison"),
        })
        bonus = self.ai._combo_bonus("flamethrower", target)
        # steam_burst (0.60) vs accelerated_burn (0.50) — should pick 0.60
        self.assertAlmostEqual(bonus, 0.60, places=5)


# ---------------------------------------------------------------------------
# 4. TestElementalAwarenessScaling
# ---------------------------------------------------------------------------

class TestElementalAwarenessScaling(unittest.TestCase):

    def _bonus_for(self, awareness: float) -> float:
        ai = _make_ai(elemental_awareness=awareness)
        ai.set_owner(_make_owner("emp_blast"))
        target = _make_target({"ice": _MockEffect("ice")})
        return ai._combo_bonus("emp_blast", target)

    def test_easy_awareness_zero_gives_no_bonus(self):
        self.assertAlmostEqual(self._bonus_for(0.0), 0.0, places=5)

    def test_medium_awareness_half_scales_bonus(self):
        full = self._bonus_for(1.0)
        half = self._bonus_for(0.5)
        self.assertAlmostEqual(half, full * 0.5, places=5)

    def test_hard_awareness_full_gives_max_bonus(self):
        bonus = self._bonus_for(1.0)
        self.assertAlmostEqual(bonus, 0.70, places=5)

    def test_awareness_zero_gives_zero_setup_bonus(self):
        ai = _make_ai(elemental_awareness=0.0)
        ai.set_owner(_make_owner())
        target = _make_target({})
        self.assertAlmostEqual(ai._setup_bonus("cryo_round", target), 0.0, places=5)


# ---------------------------------------------------------------------------
# 5. TestSetupBonus
# ---------------------------------------------------------------------------

class TestSetupBonus(unittest.TestCase):

    def setUp(self):
        self.ai = _make_ai(elemental_awareness=1.0)
        self.ai.set_owner(_make_owner())

    def test_setup_bonus_for_clean_target(self):
        target = _make_target({})   # no active effects
        bonus = self.ai._setup_bonus("cryo_round", target)
        self.assertAlmostEqual(bonus, 0.15, places=5)

    def test_no_setup_bonus_when_effect_already_active(self):
        target = _make_target({"ice": _MockEffect("ice")})
        bonus = self.ai._setup_bonus("cryo_round", target)
        self.assertAlmostEqual(bonus, 0.0, places=5)

    def test_no_setup_bonus_for_non_elemental_weapon(self):
        target = _make_target({})
        bonus = self.ai._setup_bonus("standard_shell", target)
        self.assertAlmostEqual(bonus, 0.0, places=5)

    def test_no_setup_bonus_when_target_is_none(self):
        bonus = self.ai._setup_bonus("cryo_round", None)
        self.assertAlmostEqual(bonus, 0.0, places=5)

    def test_setup_bonus_scales_with_awareness(self):
        ai_half = _make_ai(elemental_awareness=0.5)
        ai_half.set_owner(_make_owner())
        target = _make_target({})
        bonus = ai_half._setup_bonus("flamethrower", target)
        self.assertAlmostEqual(bonus, 0.075, places=5)

    def test_lava_gun_setup_bonus_clean_target(self):
        target = _make_target({})
        bonus = self.ai._setup_bonus("lava_gun", target)
        self.assertAlmostEqual(bonus, 0.15, places=5)

    def test_poison_shell_setup_bonus_clean_target(self):
        target = _make_target({})
        bonus = self.ai._setup_bonus("poison_shell", target)
        self.assertAlmostEqual(bonus, 0.15, places=5)


# ---------------------------------------------------------------------------
# 6. TestScoreWithComboBias
# ---------------------------------------------------------------------------

class TestScoreWithComboBias(unittest.TestCase):

    def _score(self, ai, wtype, target, dist=250.0):
        owner = _make_owner(wtype, dist)
        ai.set_owner(owner)
        return ai._score_weapon_slot(0, target, dist)

    def test_combo_weapon_scores_higher_than_plain_at_same_range(self):
        """Hard AI: flamethrower vs railgun vs ice-slowed target at medium range."""
        ai_hard = _make_ai(elemental_awareness=1.0)

        target = _make_target({"ice": _MockEffect("ice")})

        # Both medium range, no cooldown — only difference is combo bonus
        score_flame = self._score(ai_hard, "flamethrower", target, dist=150.0)
        score_rail  = self._score(ai_hard, "railgun",      target, dist=150.0)

        # flamethrower completes steam_burst (+0.60 at awareness=1.0)
        self.assertGreater(score_flame, score_rail)

    def test_easy_ai_scores_ignoring_combo(self):
        """Easy AI (awareness=0): no elemental bonus — same score for elemental vs plain (same range band)."""
        ai_easy = _make_ai(elemental_awareness=0.0)

        target = _make_target({"ice": _MockEffect("ice")})

        # Both cryo_round and standard_shell are medium-range weapons at dist=250 (inside band)
        score_cryo  = self._score(ai_easy, "cryo_round",      target, dist=250.0)
        score_shell = self._score(ai_easy, "standard_shell",  target, dist=250.0)

        # No elemental awareness → combo bonus = 0 → scores are equal
        self.assertAlmostEqual(score_cryo, score_shell, places=4)

    def test_score_capped_at_two(self):
        """Score never exceeds 2.0 even with all bonuses stacking."""
        ai = _make_ai(elemental_awareness=1.0)
        target = _make_target({"ice": _MockEffect("ice"), "poison": _MockEffect("poison")})
        score = self._score(ai, "flamethrower", target, dist=150.0)
        self.assertLessEqual(score, 2.0)

    def test_score_non_negative(self):
        ai = _make_ai(elemental_awareness=1.0)
        target = _make_target({})
        score = self._score(ai, "railgun", target, dist=50.0)
        self.assertGreaterEqual(score, 0.0)

    def test_deep_freeze_setup_scores_emp_highest_on_ice_target(self):
        """Hard AI: emp_blast should outscore flamethrower against ice-slowed target."""
        ai = _make_ai(elemental_awareness=1.0)
        target = _make_target({"ice": _MockEffect("ice")})
        score_emp   = self._score(ai, "emp_blast",    target, dist=250.0)
        score_flame = self._score(ai, "flamethrower", target, dist=250.0)
        # deep_freeze (0.70) > steam_burst (0.60)
        self.assertGreater(score_emp, score_flame)


# ---------------------------------------------------------------------------
# 7. TestDifficultyConfig
# ---------------------------------------------------------------------------

class TestDifficultyConfig(unittest.TestCase):

    def setUp(self):
        self.cfg = load_yaml(AI_DIFFICULTY_CONFIG)

    def test_config_has_three_tiers(self):
        for tier in ("easy", "medium", "hard"):
            self.assertIn(tier, self.cfg)

    def test_easy_elemental_awareness_is_zero(self):
        self.assertAlmostEqual(float(self.cfg["easy"]["elemental_awareness"]), 0.0)

    def test_medium_elemental_awareness_is_half(self):
        self.assertAlmostEqual(float(self.cfg["medium"]["elemental_awareness"]), 0.5)

    def test_hard_elemental_awareness_is_one(self):
        self.assertAlmostEqual(float(self.cfg["hard"]["elemental_awareness"]), 1.0)

    def test_awareness_values_increase_with_difficulty(self):
        easy   = float(self.cfg["easy"]["elemental_awareness"])
        medium = float(self.cfg["medium"]["elemental_awareness"])
        hard   = float(self.cfg["hard"]["elemental_awareness"])
        self.assertLess(easy, medium)
        self.assertLess(medium, hard)


# ---------------------------------------------------------------------------
# 8. TestAIElementalIntegration
# ---------------------------------------------------------------------------

class TestAIElementalIntegration(unittest.TestCase):

    def test_hard_ai_prefers_combo_completer_over_non_elemental(self):
        """Hard AI with emp_blast and railgun: prefers emp_blast against ice target."""
        target = _make_target({"ice": _MockEffect("ice")})
        ai = AIController(
            config={
                "reaction_time": 0.15,
                "accuracy": 0.92,
                "aggression": 0.85,
                "weapon_switch_interval": 1.5,
                "elemental_awareness": 1.0,
            },
            target_getter=lambda: target,
        )
        owner = MagicMock()
        owner.position = (100.0, 100.0)
        owner.health_ratio = 1.0
        owner.weapon_slots = [
            {"type": "railgun"},    # slot 0 — no elemental effect
            {"type": "emp_blast"},  # slot 1 — electric → deep_freeze on ice target
        ]
        owner.active_slot = 0
        owner.slot_cooldowns = [0.0, 0.0]
        ai.set_owner(owner)

        dist = 250.0
        score_rail = ai._score_weapon_slot(0, target, dist)
        score_emp  = ai._score_weapon_slot(1, target, dist)
        self.assertGreater(score_emp, score_rail,
                           f"emp_blast ({score_emp:.3f}) should beat railgun ({score_rail:.3f}) "
                           f"against ice-slowed target on hard difficulty")

    def test_easy_ai_ignores_combo_opportunity(self):
        """Easy AI (awareness=0): combo-completing weapon has no advantage over plain same-range weapon."""
        target = _make_target({"ice": _MockEffect("ice")})
        ai = AIController(
            config={
                "reaction_time": 0.80,
                "accuracy": 0.45,
                "aggression": 0.25,
                "weapon_switch_interval": 6.0,
                "elemental_awareness": 0.0,
            },
            target_getter=lambda: target,
        )
        owner = MagicMock()
        owner.position = (100.0, 100.0)
        owner.health_ratio = 1.0
        # Use cryo_round (elemental, medium range) vs standard_shell (plain, medium range)
        # Neither is an AoE weapon so AoE bonus doesn't apply to either
        owner.weapon_slots = [
            {"type": "standard_shell"},  # slot 0 — plain, medium range
            {"type": "cryo_round"},      # slot 1 — elemental (ice), medium range; would setup combo
        ]
        owner.active_slot = 0
        owner.slot_cooldowns = [0.0, 0.0]
        ai.set_owner(owner)

        dist = 250.0
        score_shell = ai._score_weapon_slot(0, target, dist)
        score_cryo  = ai._score_weapon_slot(1, target, dist)
        # Both are medium range at dist=250 — without elemental awareness, scores equal
        self.assertAlmostEqual(score_shell, score_cryo, places=4,
                               msg="Easy AI should not differentiate based on combo potential")

    def test_medium_ai_partial_combo_bias(self):
        """Medium AI (awareness=0.5): combo bonus is half the hard-AI value."""
        target = _make_target({"ice": _MockEffect("ice")})
        ai = AIController(
            config={
                "reaction_time": 0.40,
                "accuracy": 0.72,
                "aggression": 0.55,
                "weapon_switch_interval": 3.0,
                "elemental_awareness": 0.5,
            },
            target_getter=lambda: target,
        )
        owner = MagicMock()
        owner.position = (100.0, 100.0)
        owner.health_ratio = 1.0
        owner.weapon_slots = [{"type": "emp_blast"}]
        owner.active_slot = 0
        owner.slot_cooldowns = [0.0]
        ai.set_owner(owner)

        # Medium AI bonus for deep_freeze = 0.70 * 0.5 = 0.35
        bonus = ai._combo_bonus("emp_blast", target)
        self.assertAlmostEqual(bonus, 0.35, places=5)


if __name__ == "__main__":
    unittest.main()
