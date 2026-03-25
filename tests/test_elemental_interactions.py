"""
tests/test_elemental_interactions.py

Tests for v0.24 elemental interactions: ElementalResolver, Tank stun system,
remove_combat_effect, combo effects, and combo config validation.
"""

import unittest
from unittest.mock import MagicMock, patch

from game.entities.tank import Tank
from game.systems.elemental_resolver import ElementalResolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyController:
    def get_input(self, tank):
        return MagicMock(forward=0, backward=0, turn_left=False,
                         turn_right=False, fire=False, turret_angle=0.0,
                         active_slot=0)


def _make_tank(hp=100):
    return Tank(100.0, 100.0, {"health": hp}, _DummyController())


def _fire_config():
    return {
        "duration": 3.0, "tick_interval": 0.5, "tick_damage": 8,
        "speed_mult": 1.0, "turn_mult": 1.0, "fire_rate_mult": 1.0,
        "color": [255, 80, 20],
    }


def _ice_config():
    return {
        "duration": 4.0, "tick_interval": 0, "tick_damage": 0,
        "speed_mult": 0.4, "turn_mult": 0.5, "fire_rate_mult": 1.0,
        "color": [100, 200, 255],
    }


def _poison_config():
    return {
        "duration": 6.0, "tick_interval": 1.0, "tick_damage": 5,
        "speed_mult": 1.0, "turn_mult": 1.0, "fire_rate_mult": 1.0,
        "color": [80, 220, 80],
    }


def _electric_config():
    return {
        "duration": 3.5, "tick_interval": 0, "tick_damage": 0,
        "speed_mult": 1.0, "turn_mult": 1.0, "fire_rate_mult": 0.4,
        "color": [180, 130, 255],
    }


# ---------------------------------------------------------------------------
# TestElementalResolver
# ---------------------------------------------------------------------------

class TestElementalResolver(unittest.TestCase):
    """Tests for the ElementalResolver system."""

    def setUp(self):
        self.resolver = ElementalResolver()

    def test_config_loads_three_interactions(self):
        self.assertEqual(len(self.resolver._interactions), 3)

    def test_steam_burst_triggers(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        events = self.resolver.resolve([tank])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "steam_burst")

    def test_source_effects_consumed(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        self.resolver.resolve([tank])
        self.assertNotIn("fire", tank.combat_effects)
        self.assertNotIn("ice", tank.combat_effects)

    def test_no_combo_single_element(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        events = self.resolver.resolve([tank])
        self.assertEqual(len(events), 0)

    def test_no_combo_non_matching(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("poison", _poison_config())
        # fire+poison = accelerated_burn, this SHOULD trigger
        events = self.resolver.resolve([tank])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "accelerated_burn")

    def test_dead_tank_skipped(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        tank.is_alive = False
        events = self.resolver.resolve([tank])
        self.assertEqual(len(events), 0)

    def test_one_combo_per_tank_per_frame(self):
        """If a tank has fire+ice+electric, only one combo triggers."""
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        tank.apply_combat_effect("electric", _electric_config())
        events = self.resolver.resolve([tank])
        self.assertEqual(len(events), 1)

    def test_order_independent(self):
        """ice then fire should still trigger steam_burst."""
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        tank.apply_combat_effect("fire", _fire_config())
        events = self.resolver.resolve([tank])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "steam_burst")

    def test_empty_list(self):
        events = self.resolver.resolve([])
        self.assertEqual(events, [])

    def test_event_contains_tank_ref(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        events = self.resolver.resolve([tank])
        self.assertIs(events[0]["tank"], tank)

    def test_event_contains_config(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        events = self.resolver.resolve([tank])
        cfg = events[0]["config"]
        self.assertEqual(cfg["result_type"], "aoe_burst")
        self.assertEqual(cfg["aoe_radius"], 100)

    def test_deep_freeze_triggers(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        tank.apply_combat_effect("electric", _electric_config())
        events = self.resolver.resolve([tank])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "deep_freeze")


# ---------------------------------------------------------------------------
# TestTankStun
# ---------------------------------------------------------------------------

class TestTankStun(unittest.TestCase):
    """Tests for the Tank stun system."""

    def test_apply_stun(self):
        tank = _make_tank()
        tank.apply_stun(2.0)
        self.assertTrue(tank.is_stunned)

    def test_stun_prevents_movement(self):
        tank = _make_tank()
        tank.apply_stun(1.0)
        tank.update(0.1)
        self.assertEqual(tank.vx, 0.0)
        self.assertEqual(tank.vy, 0.0)

    def test_stun_ticks_down(self):
        tank = _make_tank()
        tank.apply_stun(0.5)
        tank.update(0.3)
        self.assertTrue(tank.is_stunned)
        tank.update(0.3)
        self.assertFalse(tank.is_stunned)

    def test_stun_expires(self):
        tank = _make_tank()
        tank.apply_stun(0.1)
        tank.update(0.2)
        self.assertFalse(tank.is_stunned)

    def test_dot_during_stun(self):
        """DoT from combat effects should still hurt during stun."""
        tank = _make_tank(hp=100)
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_stun(5.0)
        # Fire ticks every 0.5s for 8 damage
        tank.update(0.5)
        self.assertLess(tank.health, 100)

    def test_cooldowns_tick_during_stun(self):
        tank = _make_tank()
        tank.apply_stun(2.0)
        # Set a cooldown manually
        if tank._slot_cooldowns:
            tank._slot_cooldowns[0] = 1.0
            tank.update(0.5)
            self.assertLessEqual(tank._slot_cooldowns[0], 0.5 + 0.01)

    def test_longer_stun_not_shortened(self):
        tank = _make_tank()
        tank.apply_stun(5.0)
        tank.apply_stun(2.0)  # shorter — should NOT override
        self.assertGreaterEqual(tank._stun_timer, 4.99)


# ---------------------------------------------------------------------------
# TestTankRemoveCombatEffect
# ---------------------------------------------------------------------------

class TestTankRemoveCombatEffect(unittest.TestCase):
    """Tests for Tank.remove_combat_effect()."""

    def test_remove_existing(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        self.assertIn("fire", tank.combat_effects)
        tank.remove_combat_effect("fire")
        self.assertNotIn("fire", tank.combat_effects)

    def test_remove_nonexistent_no_error(self):
        tank = _make_tank()
        tank.remove_combat_effect("fire")  # should not raise

    def test_remove_one_leaves_other(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        tank.remove_combat_effect("fire")
        self.assertNotIn("fire", tank.combat_effects)
        self.assertIn("ice", tank.combat_effects)


# ---------------------------------------------------------------------------
# TestComboEffects
# ---------------------------------------------------------------------------

class TestComboEffects(unittest.TestCase):
    """Tests that combo configs produce the expected effect types."""

    def setUp(self):
        self.resolver = ElementalResolver()

    def test_steam_burst_deals_direct_damage(self):
        tank = _make_tank(hp=100)
        tank.apply_combat_effect("fire", _fire_config())
        tank.apply_combat_effect("ice", _ice_config())
        events = self.resolver.resolve([tank])
        cfg = events[0]["config"]
        self.assertEqual(cfg["damage"], 25)

    def test_accelerated_burn_sixty_damage(self):
        tank = _make_tank(hp=100)
        tank.apply_combat_effect("poison", _poison_config())
        tank.apply_combat_effect("fire", _fire_config())
        events = self.resolver.resolve([tank])
        cfg = events[0]["config"]
        self.assertEqual(cfg["damage"], 60)

    def test_deep_freeze_stun(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        tank.apply_combat_effect("electric", _electric_config())
        events = self.resolver.resolve([tank])
        cfg = events[0]["config"]
        self.assertEqual(cfg["result_type"], "stun")

    def test_deep_freeze_stun_duration(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        tank.apply_combat_effect("electric", _electric_config())
        events = self.resolver.resolve([tank])
        cfg = events[0]["config"]
        self.assertEqual(cfg["stun_duration"], 3.0)


# ---------------------------------------------------------------------------
# TestComboConfig
# ---------------------------------------------------------------------------

class TestComboConfig(unittest.TestCase):
    """Tests for the elemental_interactions.yaml config validity."""

    def setUp(self):
        self.resolver = ElementalResolver()

    def test_three_entries(self):
        self.assertEqual(len(self.resolver._interactions), 3)

    def test_steam_burst_elements(self):
        cfg = next(i for i in self.resolver._interactions if i["name"] == "steam_burst")
        self.assertEqual(set(cfg["elements"]), {"fire", "ice"})

    def test_accelerated_burn_elements(self):
        cfg = next(i for i in self.resolver._interactions if i["name"] == "accelerated_burn")
        self.assertEqual(set(cfg["elements"]), {"poison", "fire"})

    def test_deep_freeze_elements(self):
        cfg = next(i for i in self.resolver._interactions if i["name"] == "deep_freeze")
        self.assertEqual(set(cfg["elements"]), {"ice", "electric"})

    def test_sfx_keys_present(self):
        for interaction in self.resolver._interactions:
            self.assertIn("sfx_key", interaction)
            self.assertTrue(len(interaction["sfx_key"]) > 0)


if __name__ == "__main__":
    unittest.main()
