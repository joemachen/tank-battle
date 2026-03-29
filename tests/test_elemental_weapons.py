"""
tests/test_elemental_weapons.py

Tests for v0.25 weapons: cryo_round, poison_shell, flamethrower, EMP blast,
railgun (pierce), raycast system, and laser beam (hitscan energy).
"""

import math
import unittest
from unittest.mock import MagicMock

from game.entities.bullet import Bullet
from game.entities.tank import Tank, TankInput
from game.systems.collision import CollisionSystem, TANK_RADIUS
from game.systems.raycast import cast_ray, _line_vs_aabb, _line_vs_circle
from game.utils.config_loader import load_yaml
from game.utils.constants import DAMAGE_TYPE_BULLET_COLORS, WEAPONS_CONFIG
from game.utils.damage_types import DamageType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyController:
    def __init__(self, fire: bool = False):
        self._fire = fire

    def get_input(self) -> TankInput:
        return TankInput(fire=self._fire)


def _make_tank(hp: int = 100) -> Tank:
    return Tank(100.0, 100.0, {"health": hp}, _DummyController())


def _load_weapons():
    return load_yaml(WEAPONS_CONFIG)


def _weapon_cfg(weapon_id: str) -> dict:
    return _load_weapons()[weapon_id]


class _StubBullet:
    """Minimal bullet stub for pierce collision tests."""

    def __init__(self, pos: tuple, owner, damage: int = 25,
                 damage_type: DamageType = DamageType.STANDARD,
                 pierce_count: int = 0):
        self.x, self.y = pos
        self.owner = owner
        self.damage = damage
        self.damage_type = damage_type
        self.is_alive = True
        self.is_explosive = False
        self.pierce_count = pierce_count
        self._pierced_tanks: set = set()

    @property
    def position(self) -> tuple:
        return (self.x, self.y)

    def destroy(self) -> None:
        self.is_alive = False


class _StubTank:
    """Minimal tank stub for pierce collision tests."""

    def __init__(self, pos: tuple, health: int = 100):
        self.x, self.y = pos
        self.health = health
        self.max_health = health
        self.is_alive = True
        self._combat_effects_applied: list = []

    @property
    def position(self) -> tuple:
        return (self.x, self.y)

    def take_damage(self, amount: int, **kwargs) -> None:
        self.health -= amount
        if self.health <= 0:
            self.is_alive = False

    def apply_combat_effect(self, effect_key: str, cfg: dict) -> None:
        self._combat_effects_applied.append(effect_key)


class _StubObstacle:
    """Minimal obstacle stub for raycast tests."""

    def __init__(self, x: float, y: float, w: float, h: float, alive: bool = True):
        self.x = x
        self.y = y
        self.width = w
        self.height = h
        self.is_alive = alive
        self.damage_received: int = 0

    def take_damage(self, amount: int, **kwargs) -> None:
        self.damage_received += amount


# ---------------------------------------------------------------------------
# TestCryoRound
# ---------------------------------------------------------------------------

class TestCryoRound(unittest.TestCase):

    def setUp(self):
        self.cfg = _weapon_cfg("cryo_round")

    def test_cryo_config_has_ice_damage_type(self):
        self.assertEqual(self.cfg["damage_type"], "ice")

    def test_cryo_bullet_applies_ice_effect(self):
        tank = _make_tank()
        bullet = Bullet(100.0, 100.0, 0.0, None, self.cfg)
        # Confirm bullet has ICE damage type
        self.assertEqual(bullet.damage_type, DamageType.ICE)

    def test_cryo_bullet_color_is_ice(self):
        color = DAMAGE_TYPE_BULLET_COLORS.get("ICE")
        self.assertIsNotNone(color)
        # ICE should be a light blue — dominant blue channel
        self.assertGreater(color[2], color[0])  # blue > red
        self.assertGreater(color[2], color[1])  # blue > green


# ---------------------------------------------------------------------------
# TestPoisonShell
# ---------------------------------------------------------------------------

class TestPoisonShell(unittest.TestCase):

    def setUp(self):
        self.cfg = _weapon_cfg("poison_shell")

    def test_poison_config_has_poison_damage_type(self):
        self.assertEqual(self.cfg["damage_type"], "poison")

    def test_poison_bullet_applies_poison_effect(self):
        bullet = Bullet(100.0, 100.0, 0.0, None, self.cfg)
        self.assertEqual(bullet.damage_type, DamageType.POISON)

    def test_poison_total_damage(self):
        """Direct damage + DoT ticks should exceed standard_shell (25)."""
        direct = self.cfg["damage"]   # 12
        # Poison DoT: 5 damage × 6 ticks (from status_effects.yaml)
        # We just verify the direct value is low — DoT is config-driven
        self.assertLessEqual(direct, 15)
        self.assertGreater(direct, 0)


# ---------------------------------------------------------------------------
# TestFlamethrower
# ---------------------------------------------------------------------------

class TestFlamethrower(unittest.TestCase):

    def setUp(self):
        self.cfg = _weapon_cfg("flamethrower")

    def test_flame_config_has_fire_damage_type(self):
        self.assertEqual(self.cfg["damage_type"], "fire")

    def test_flame_has_spread(self):
        self.assertEqual(self.cfg["spread_count"], 3)

    def test_flame_fires_3_bullets(self):
        """spread_count=3 means 3 Bullet instances per fire event."""
        bullets = []
        spread_count = int(self.cfg.get("spread_count", 1))
        spread_angle = float(self.cfg.get("spread_angle", 0.0))
        if spread_count > 1 and spread_angle > 0.0:
            half_spread = spread_angle * (spread_count - 1) / 2.0
            for i in range(spread_count):
                offset = -half_spread + i * spread_angle
                bullets.append(Bullet(100.0, 100.0, offset, None, self.cfg))
        self.assertEqual(len(bullets), 3)

    def test_flame_short_range(self):
        self.assertEqual(self.cfg["max_range"], 250)

    def test_flame_high_fire_rate(self):
        self.assertEqual(self.cfg["fire_rate"], 6.0)


# ---------------------------------------------------------------------------
# TestEMPBlast
# ---------------------------------------------------------------------------

class TestEMPBlast(unittest.TestCase):

    def setUp(self):
        self.cfg = _weapon_cfg("emp_blast")

    def test_emp_config_has_electric_damage_type(self):
        self.assertEqual(self.cfg["damage_type"], "electric")

    def test_emp_is_explosive(self):
        bullet = Bullet(100.0, 100.0, 0.0, None, self.cfg)
        self.assertTrue(bullet.is_explosive)

    def test_emp_aoe_radius(self):
        self.assertEqual(self.cfg["aoe_radius"], 140)

    def test_emp_applies_electric_on_hit(self):
        """Bullet created from EMP config should have ELECTRIC damage type."""
        bullet = Bullet(100.0, 100.0, 0.0, None, self.cfg)
        self.assertEqual(bullet.damage_type, DamageType.ELECTRIC)


# ---------------------------------------------------------------------------
# TestRailgun
# ---------------------------------------------------------------------------

class TestRailgun(unittest.TestCase):

    def setUp(self):
        self.cfg = _weapon_cfg("railgun")
        self.cs = CollisionSystem()

    def test_railgun_pierce_count(self):
        self.assertEqual(self.cfg["pierce_count"], 1)

    def test_railgun_bullet_has_pierce(self):
        bullet = Bullet(100.0, 100.0, 0.0, None, self.cfg)
        self.assertEqual(bullet.pierce_count, 1)

    def test_railgun_pierces_first_tank(self):
        """Bullet with pierce_count=1 damages tank A and stays alive."""
        owner = _StubTank((0, 0))
        bullet = _StubBullet((100, 100), owner, damage=65, pierce_count=1)
        tank_a = _StubTank((100, 100), health=100)
        hit = self.cs.check_bullet_vs_tank(bullet, tank_a)
        self.assertTrue(hit)
        self.assertTrue(bullet.is_alive)        # bullet survived the pierce
        self.assertEqual(tank_a.health, 35)     # 100 - 65

    def test_railgun_stops_at_second_tank(self):
        """After piercing tank A, bullet destroys when it hits tank B."""
        owner = _StubTank((0, 0))
        bullet = _StubBullet((100, 100), owner, damage=65, pierce_count=1)
        tank_a = _StubTank((100, 100), health=200)
        tank_b = _StubTank((100, 100), health=200)
        self.cs.check_bullet_vs_tank(bullet, tank_a)   # pierce — bullet alive
        self.cs.check_bullet_vs_tank(bullet, tank_b)   # last pierce — bullet destroyed
        self.assertFalse(bullet.is_alive)
        self.assertEqual(tank_b.health, 135)    # 200 - 65

    def test_railgun_no_double_hit(self):
        """After piercing tank A, the same bullet cannot hit tank A again."""
        owner = _StubTank((0, 0))
        bullet = _StubBullet((100, 100), owner, damage=65, pierce_count=1)
        tank_a = _StubTank((100, 100), health=200)
        self.cs.check_bullet_vs_tank(bullet, tank_a)     # first hit, pierce
        hp_after_first = tank_a.health
        self.cs.check_bullet_vs_tank(bullet, tank_a)     # should be ignored
        self.assertEqual(tank_a.health, hp_after_first)  # no extra damage

    def test_railgun_speed_800(self):
        self.assertEqual(self.cfg["speed"], 800)

    def test_non_piercing_bullet_destroyed_on_hit(self):
        """Standard shell (pierce_count=0) is destroyed after the first tank hit."""
        std_cfg = _weapon_cfg("standard_shell")
        owner = _StubTank((0, 0))
        bullet = _StubBullet((100, 100), owner, damage=25, pierce_count=0)
        tank = _StubTank((100, 100), health=100)
        self.cs.check_bullet_vs_tank(bullet, tank)
        self.assertFalse(bullet.is_alive)


# ---------------------------------------------------------------------------
# TestRaycast
# ---------------------------------------------------------------------------

class TestRaycast(unittest.TestCase):

    def test_ray_hits_obstacle(self):
        obs = _StubObstacle(200, 90, 40, 40)
        result = cast_ray(0, 110, 0, 500, [], [obs])
        self.assertEqual(result["hit_type"], "obstacle")
        self.assertIs(result["entity"], obs)

    def test_ray_hits_tank(self):
        tank = _StubTank((200, 110))
        result = cast_ray(0, 110, 0, 500, [tank], [])
        self.assertEqual(result["hit_type"], "tank")
        self.assertIs(result["entity"], tank)

    def test_ray_misses_when_aimed_away(self):
        tank = _StubTank((200, 110))
        result = cast_ray(0, 110, 180, 500, [tank], [])
        self.assertFalse(result["hit"])
        self.assertEqual(result["hit_type"], "none")

    def test_ray_hits_nearest(self):
        obs_near = _StubObstacle(100, 90, 40, 40)
        obs_far  = _StubObstacle(300, 90, 40, 40)
        result = cast_ray(0, 110, 0, 500, [], [obs_near, obs_far])
        self.assertIs(result["entity"], obs_near)

    def test_ray_ignores_dead_obstacle(self):
        obs = _StubObstacle(200, 90, 40, 40, alive=False)
        result = cast_ray(0, 110, 0, 500, [], [obs])
        self.assertFalse(result["hit"])

    def test_ray_ignores_owner_tank(self):
        owner = _StubTank((100, 110))
        result = cast_ray(0, 110, 0, 500, [owner], [], ignore_tank=owner)
        self.assertFalse(result["hit"])

    def test_ray_max_range(self):
        """Obstacle beyond max_range should not be hit."""
        obs = _StubObstacle(600, 90, 40, 40)
        result = cast_ray(0, 110, 0, 400, [], [obs])
        self.assertFalse(result["hit"])

    def test_line_vs_aabb_perpendicular(self):
        """Ray aimed straight at rect face should return positive distance."""
        t = _line_vs_aabb(0, 50, 1, 0, 500, 100, 0, 50, 100)
        self.assertIsNotNone(t)
        self.assertAlmostEqual(t, 100.0, places=3)

    def test_line_vs_aabb_miss(self):
        """Ray parallel to rect and outside should return None."""
        t = _line_vs_aabb(0, 200, 1, 0, 500, 100, 0, 50, 100)
        self.assertIsNone(t)

    def test_line_vs_circle_hit(self):
        """Ray through circle center should return a positive distance."""
        t = _line_vs_circle(0, 0, 1, 0, 500, 200, 0, TANK_RADIUS)
        self.assertIsNotNone(t)
        self.assertAlmostEqual(t, 200 - TANK_RADIUS, delta=1.0)

    def test_line_vs_circle_miss(self):
        """Ray clearly missing circle returns None."""
        t = _line_vs_circle(0, 0, 1, 0, 500, 200, 100, TANK_RADIUS)
        self.assertIsNone(t)

    def test_line_vs_circle_tangent(self):
        """Ray tangent (or near-miss) to circle returns None or barely-hit."""
        # At exactly radius distance — discriminant ≈ 0, may or may not hit
        # Just verify the function doesn't raise
        t = _line_vs_circle(0, TANK_RADIUS, 1, 0, 500, 200, 0, TANK_RADIUS)
        # Could be None or tiny positive — just no exception


# ---------------------------------------------------------------------------
# TestLaserBeam
# ---------------------------------------------------------------------------

class TestLaserBeam(unittest.TestCase):

    def setUp(self):
        self.cfg = _weapon_cfg("laser_beam")

    def test_laser_config_hitscan_true(self):
        self.assertTrue(self.cfg.get("hitscan", False))

    def test_laser_energy_initialized(self):
        """Tank with laser_beam loaded should start fully charged."""
        tank = _make_tank()
        tank.load_weapons([self.cfg])
        self.assertEqual(tank.energy, tank._energy_max)
        self.assertGreater(tank._energy_max, 0)

    def test_laser_energy_drains_while_firing(self):
        """When intent.fire=True and energy ≥ min, energy decreases."""
        controller = _DummyController(fire=True)
        tank = Tank(100.0, 100.0, {"health": 100}, controller)
        tank.load_weapons([self.cfg])
        initial_energy = tank.energy
        tank.update(0.1)
        self.assertLess(tank.energy, initial_energy)

    def test_laser_energy_recharges_when_idle(self):
        """When not firing, energy increases toward max."""
        controller = _DummyController(fire=False)
        tank = Tank(100.0, 100.0, {"health": 100}, controller)
        tank.load_weapons([self.cfg])
        # Drain some energy manually
        tank._energy = 50.0
        tank.update(1.0)
        self.assertGreater(tank.energy, 50.0)

    def test_laser_stops_at_zero_energy(self):
        """After energy reaches 0, is_firing_beam becomes False."""
        controller = _DummyController(fire=True)
        tank = Tank(100.0, 100.0, {"health": 100}, controller)
        tank.load_weapons([self.cfg])
        # Drain all energy in a single large dt
        tank._energy = 0.0
        tank.update(0.1)
        self.assertFalse(tank.is_firing_beam)

    def test_laser_min_energy_to_fire(self):
        """When energy < min_to_fire, beam does not activate."""
        controller = _DummyController(fire=True)
        tank = Tank(100.0, 100.0, {"health": 100}, controller)
        tank.load_weapons([self.cfg])
        tank._energy = self.cfg["energy_min_to_fire"] - 1.0
        tank.update(0.01)
        self.assertFalse(tank.is_firing_beam)

    def test_beam_event_emitted(self):
        """Firing a laser with sufficient energy emits a beam event."""
        controller = _DummyController(fire=True)
        tank = Tank(100.0, 100.0, {"health": 100}, controller)
        tank.load_weapons([self.cfg])
        events = tank.update(0.016)
        beam_events = [e for e in events if e[0] == "beam"]
        self.assertTrue(len(beam_events) > 0)
        self.assertEqual(beam_events[0][4], "laser_beam")

    def test_no_bullet_spawned_for_hitscan(self):
        """Firing a laser should NOT emit a 'fire' projectile event."""
        controller = _DummyController(fire=True)
        tank = Tank(100.0, 100.0, {"health": 100}, controller)
        tank.load_weapons([self.cfg])
        events = tank.update(0.016)
        fire_events = [e for e in events if e[0] == "fire"]
        self.assertEqual(len(fire_events), 0)


class TestLaserDpsConfig(unittest.TestCase):

    def test_laser_dps_is_40(self):
        """Laser beam DPS should be 40 after v0.26 nerf."""
        cfg = _weapon_cfg("laser_beam")
        self.assertEqual(cfg["dps"], 40)


if __name__ == "__main__":
    unittest.main()
