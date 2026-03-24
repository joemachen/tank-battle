"""
tests/test_status_effects.py

Tests for v0.23 combat status effects: StatusEffect class, Tank combat effect
integration, collision integration, and HUD combat labels.
"""

import unittest
from unittest.mock import MagicMock, patch

from game.systems.status_effect import StatusEffect
from game.utils.damage_types import DamageType


def _fire_config():
    return {
        "duration": 3.0,
        "tick_interval": 0.5,
        "tick_damage": 8,
        "speed_mult": 1.0,
        "turn_mult": 1.0,
        "fire_rate_mult": 1.0,
        "color": [255, 80, 20],
    }


def _ice_config():
    return {
        "duration": 4.0,
        "tick_interval": 0,
        "tick_damage": 0,
        "speed_mult": 0.4,
        "turn_mult": 0.5,
        "fire_rate_mult": 1.0,
        "color": [100, 200, 255],
    }


def _poison_config():
    return {
        "duration": 6.0,
        "tick_interval": 1.0,
        "tick_damage": 5,
        "speed_mult": 1.0,
        "turn_mult": 1.0,
        "fire_rate_mult": 1.0,
        "color": [80, 220, 80],
    }


def _electric_config():
    return {
        "duration": 3.5,
        "tick_interval": 0,
        "tick_damage": 0,
        "speed_mult": 1.0,
        "turn_mult": 1.0,
        "fire_rate_mult": 0.4,
        "color": [180, 130, 255],
    }


# ---------------------------------------------------------------------------
# StatusEffect class tests
# ---------------------------------------------------------------------------


class TestStatusEffect(unittest.TestCase):
    """Tests for the StatusEffect data class."""

    def test_init_fire(self):
        e = StatusEffect("fire", _fire_config())
        self.assertEqual(e.effect_type, "fire")
        self.assertAlmostEqual(e.duration, 3.0)
        self.assertAlmostEqual(e.tick_interval, 0.5)
        self.assertEqual(e.tick_damage, 8)
        self.assertAlmostEqual(e.speed_mult, 1.0)
        self.assertEqual(e.color, (255, 80, 20))

    def test_init_ice_no_tick(self):
        e = StatusEffect("ice", _ice_config())
        self.assertAlmostEqual(e.speed_mult, 0.4)
        self.assertAlmostEqual(e.turn_mult, 0.5)
        self.assertEqual(e.tick_damage, 0)

    def test_update_ticks_damage(self):
        e = StatusEffect("fire", _fire_config())
        # First 0.5s: should fire one tick
        damage = e.update(0.5)
        self.assertEqual(damage, 8)

    def test_update_no_tick_for_ice(self):
        e = StatusEffect("ice", _ice_config())
        damage = e.update(1.0)
        self.assertEqual(damage, 0)

    def test_update_multiple_ticks_in_large_dt(self):
        e = StatusEffect("fire", _fire_config())
        # 1.5s dt on 0.5s interval → 3 ticks
        damage = e.update(1.5)
        self.assertEqual(damage, 24)

    def test_is_expired(self):
        e = StatusEffect("fire", _fire_config())
        self.assertFalse(e.is_expired)
        e.update(3.0)
        self.assertTrue(e.is_expired)

    def test_refresh_resets_duration(self):
        e = StatusEffect("fire", _fire_config())
        e.update(2.0)
        self.assertAlmostEqual(e.duration, 1.0)
        e.refresh(_fire_config())
        self.assertAlmostEqual(e.duration, 3.0)

    def test_poison_slow_ticks(self):
        e = StatusEffect("poison", _poison_config())
        damage = e.update(1.0)
        self.assertEqual(damage, 5)

    def test_electric_fire_rate_mult(self):
        e = StatusEffect("electric", _electric_config())
        self.assertAlmostEqual(e.fire_rate_mult, 0.4)


# ---------------------------------------------------------------------------
# Tank combat effect integration tests
# ---------------------------------------------------------------------------


def _make_tank(**overrides):
    """Create a Tank with minimal config for testing."""
    from game.entities.tank import Tank

    config = {
        "type": "medium_tank",
        "speed": 150,
        "turn_rate": 120,
        "health": 100,
        "fire_rate": 1.0,
        "color": [100, 160, 80],
    }
    config.update(overrides)
    controller = MagicMock()
    controller.get_input.return_value = MagicMock(
        forward=0, backward=0, turn_left=0, turn_right=0, fire=False,
        turret_angle=None
    )
    return Tank(x=400, y=300, config=config, controller=controller)


class TestTankCombatEffects(unittest.TestCase):
    """Tests for Tank.apply_combat_effect and multiplier helpers."""

    def test_apply_combat_effect_creates_effect(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        self.assertIn("fire", tank.combat_effects)

    def test_apply_combat_effect_refresh(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        tank.update(1.0)  # burns 1s
        remaining = tank.combat_effects["fire"].duration
        self.assertAlmostEqual(remaining, 2.0, places=1)
        tank.apply_combat_effect("fire", _fire_config())
        self.assertAlmostEqual(tank.combat_effects["fire"].duration, 3.0)

    def test_has_any_combat_effect(self):
        tank = _make_tank()
        self.assertFalse(tank.has_any_combat_effect)
        tank.apply_combat_effect("ice", _ice_config())
        self.assertTrue(tank.has_any_combat_effect)

    def test_combat_speed_mult(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        self.assertAlmostEqual(tank._combat_speed_mult(), 0.4)

    def test_combat_turn_mult(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        self.assertAlmostEqual(tank._combat_turn_mult(), 0.5)

    def test_combat_fire_rate_mult(self):
        tank = _make_tank()
        tank.apply_combat_effect("electric", _electric_config())
        self.assertAlmostEqual(tank._combat_fire_rate_mult(), 0.4)

    def test_multiple_effects_stack_multiplicatively(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        # Add a custom effect with speed_mult=0.5
        tank.apply_combat_effect("poison", {"duration": 3.0, "speed_mult": 0.5,
                                             "turn_mult": 1.0, "fire_rate_mult": 1.0,
                                             "color": [0, 255, 0]})
        self.assertAlmostEqual(tank._combat_speed_mult(), 0.2)  # 0.4 * 0.5

    def test_dot_reduces_health(self):
        tank = _make_tank(health=100)
        tank.apply_combat_effect("fire", _fire_config())
        tank.update(0.5)  # one fire tick = 8 damage
        self.assertEqual(tank.health, 92)

    def test_dot_can_kill_tank(self):
        tank = _make_tank(health=5)
        tank.apply_combat_effect("fire", _fire_config())
        tank.update(0.5)  # 8 damage on 5 HP tank
        self.assertFalse(tank.is_alive)

    def test_effects_expire(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        # Ice lasts 4s
        tank.update(4.1)
        self.assertFalse(tank.has_any_combat_effect)

    def test_active_status_names_includes_combat(self):
        tank = _make_tank()
        tank.apply_combat_effect("fire", _fire_config())
        self.assertIn("fire", tank.active_status_names)

    def test_combat_effects_returns_shallow_copy(self):
        tank = _make_tank()
        tank.apply_combat_effect("ice", _ice_config())
        copy = tank.combat_effects
        copy.clear()
        # Original should still have the effect
        self.assertTrue(tank.has_any_combat_effect)


# ---------------------------------------------------------------------------
# Collision integration tests
# ---------------------------------------------------------------------------


class TestCollisionCombatEffect(unittest.TestCase):
    """Tests that collision system applies combat effects on hit."""

    @patch("game.systems.collision.load_yaml")
    def test_bullet_applies_fire_effect(self, mock_load):
        mock_load.return_value = {
            "fire": _fire_config(),
            "ice": _ice_config(),
            "poison": _poison_config(),
            "electric": _electric_config(),
        }
        # Reset cached configs
        import game.systems.collision as col_mod
        col_mod._status_configs = None

        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()

        tank = _make_tank(health=100)
        bullet = MagicMock()
        bullet.is_alive = True
        bullet.is_explosive = False
        bullet.position = (400, 300)
        bullet.x = 400
        bullet.y = 300
        bullet.damage = 10
        bullet.damage_type = DamageType.FIRE
        bullet.bounces_remaining = 0

        owner = _make_tank()

        bullet.owner = owner

        hit = cs.check_bullet_vs_tank(bullet, tank)
        self.assertTrue(hit)
        self.assertIn("fire", tank.combat_effects)

    @patch("game.systems.collision.load_yaml")
    def test_standard_bullet_no_combat_effect(self, mock_load):
        mock_load.return_value = {
            "fire": _fire_config(),
        }
        import game.systems.collision as col_mod
        col_mod._status_configs = None

        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()

        tank = _make_tank(health=100)
        bullet = MagicMock()
        bullet.is_alive = True
        bullet.is_explosive = False
        bullet.position = (400, 300)
        bullet.x = 400
        bullet.y = 300
        bullet.damage = 10
        bullet.damage_type = DamageType.STANDARD
        bullet.bounces_remaining = 0
        bullet.owner = _make_tank()

        cs.check_bullet_vs_tank(bullet, tank)
        self.assertEqual(len(tank.combat_effects), 0)

    @patch("game.systems.collision.load_yaml")
    def test_lethal_bullet_no_combat_effect(self, mock_load):
        """Dead tanks don't get combat effects applied."""
        mock_load.return_value = {"fire": _fire_config()}
        import game.systems.collision as col_mod
        col_mod._status_configs = None

        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()

        tank = _make_tank(health=5)
        bullet = MagicMock()
        bullet.is_alive = True
        bullet.is_explosive = False
        bullet.position = (400, 300)
        bullet.x = 400
        bullet.y = 300
        bullet.damage = 100
        bullet.damage_type = DamageType.FIRE
        bullet.bounces_remaining = 0
        bullet.owner = _make_tank()

        cs.check_bullet_vs_tank(bullet, tank)
        self.assertFalse(tank.is_alive)
        self.assertEqual(len(tank.combat_effects), 0)


# ---------------------------------------------------------------------------
# HUD combat effect display tests
# ---------------------------------------------------------------------------


class TestHUDCombatEffects(unittest.TestCase):
    """Tests that HUD accepts and displays combat effects."""

    @patch("pygame.font.SysFont")
    @patch("pygame.font.Font")
    def test_hud_draw_accepts_combat_effects(self, mock_font_cls, mock_sysfont):
        """HUD.draw() should not raise when passed combat_effects."""
        mock_font = MagicMock()
        mock_rendered = MagicMock()
        mock_rendered.get_width.return_value = 60
        mock_rendered.get_height.return_value = 16
        mock_font.render.return_value = mock_rendered
        mock_sysfont.return_value = mock_font

        from game.ui.hud import HUD
        hud = HUD()

        surface = MagicMock()
        surface.get_width.return_value = 1280
        surface.get_height.return_value = 720

        tank = MagicMock()
        tank.health_ratio = 0.8
        tank.health = 80
        tank.max_health = 100
        tank.tank_type = "medium_tank"
        tank.is_alive = True
        tank.combat_effects = {"fire": StatusEffect("fire", _fire_config())}
        tank.weapon_slots = []
        tank.active_slot = 0
        tank.slot_cooldowns = []

        # Should not raise
        hud.draw(surface, tank, combat_effects=tank.combat_effects)


if __name__ == "__main__":
    unittest.main()
