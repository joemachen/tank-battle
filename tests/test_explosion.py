"""
tests/test_explosion.py

Tests for v0.22 AoE explosions, grenade launcher, stone destruction,
and cooldown HUD indicator.

~28 tests across 4 classes:
  TestExplosion        — damage at center/edge/outside, owner immunity, multi-tank,
                         obstacle damage, damage filters, resolve-once, visual timer
  TestGrenadeBullet    — is_explosive flag, aoe_radius from config, detonated at max_range
  TestStoneDestruction — destructible, HP, partial_destruction, rubble pieces
  TestCooldownIndicator — property exists, length matches, cooldown decrements
"""

import math

import pytest

from game.entities.explosion import Explosion
from game.entities.bullet import Bullet
from game.entities.obstacle import Obstacle
from game.entities.tank import Tank, TankInput
from game.utils.damage_types import DamageType


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _StubController:
    """Minimal controller for Tank construction."""
    def get_input(self) -> TankInput:
        return TankInput()


def _make_tank(x=0.0, y=0.0, health=100) -> Tank:
    config = {"type": "test_tank", "health": health, "speed": 100, "turn_rate": 90, "fire_rate": 1.0}
    return Tank(x, y, config, _StubController())


def _make_obstacle(x=0.0, y=0.0, w=50, h=50, hp=200, destructible=True, **extra) -> Obstacle:
    cfg = {"hp": hp, "destructible": destructible, "color": [100, 100, 100]}
    cfg.update(extra)
    return Obstacle(x, y, w, h, material_type="stone", material_config=cfg)


# ---------------------------------------------------------------------------
# TestExplosion — AoE damage entity
# ---------------------------------------------------------------------------

class TestExplosion:
    """Core explosion damage and visual timer tests."""

    def test_full_damage_at_center(self):
        owner = _make_tank(x=0, y=0)
        target = _make_tank(x=50, y=0, health=200)  # inside radius, near center
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        events = exp.resolve_damage([target], [])
        # Tank at epicenter (dist=0) should take full damage
        assert target.health == 200 - 70

    def test_reduced_damage_at_edge(self):
        owner = _make_tank(x=0, y=0)
        # Place target near the edge of the 120px radius
        target = _make_tank(x=150, y=0, health=200)  # dist=100 from (50,0)
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner,
                        damage_falloff=0.25)
        exp.resolve_damage([target], [])
        # dist=100, radius=120 → scale = 1.0 - (1-0.25)*(100/120) = 1.0 - 0.625 = 0.375
        expected = max(1, int(70 * 0.375))
        assert target.health == 200 - expected

    def test_no_damage_outside_radius(self):
        owner = _make_tank(x=0, y=0)
        target = _make_tank(x=200, y=0, health=100)
        exp = Explosion(0, 0, radius=50, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        exp.resolve_damage([target], [])
        assert target.health == 100  # untouched

    def test_owner_immune(self):
        owner = _make_tank(x=50, y=0, health=100)
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        exp.resolve_damage([owner], [])
        assert owner.health == 100  # no self-damage

    def test_multi_tank_damage(self):
        owner = _make_tank(x=0, y=0)
        t1 = _make_tank(x=50, y=0, health=200)
        t2 = _make_tank(x=60, y=0, health=200)
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        events = exp.resolve_damage([t1, t2], [])
        assert t1.health < 200
        assert t2.health < 200
        # Both tanks should generate events
        assert any(isinstance(e, tuple) and e[0] == "bullet_hit_tank_stat" for e in events)

    def test_obstacle_damage(self):
        owner = _make_tank(x=0, y=0)
        obs = _make_obstacle(x=40, y=0, w=50, h=50, hp=200, destructible=True)
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        exp.resolve_damage([], [obs])
        assert obs.hp < 200

    def test_obstacle_destroy_event(self):
        owner = _make_tank(x=0, y=0)
        obs = _make_obstacle(x=40, y=0, w=50, h=50, hp=10, destructible=True)
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        events = exp.resolve_damage([], [obs])
        assert "obstacle_destroy" in events
        assert not obs.is_alive

    def test_resolve_once(self):
        owner = _make_tank(x=0, y=0)
        target = _make_tank(x=50, y=0, health=200)
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        exp.resolve_damage([target], [])
        hp_after_first = target.health
        # Second call should be no-op
        events = exp.resolve_damage([target], [])
        assert events == []
        assert target.health == hp_after_first

    def test_is_alive_false_after_resolve(self):
        owner = _make_tank(x=0, y=0)
        exp = Explosion(0, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        assert exp.is_alive is True
        exp.resolve_damage([], [])
        assert exp.is_alive is False

    def test_visual_timer_ticks(self):
        owner = _make_tank(x=0, y=0)
        exp = Explosion(0, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner,
                        visual_duration=0.4)
        assert exp.visual_alive is True
        exp.update(0.2)
        assert exp.visual_alive is True
        exp.update(0.3)
        assert exp.visual_alive is False

    def test_visual_progress(self):
        owner = _make_tank(x=0, y=0)
        exp = Explosion(0, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner,
                        visual_duration=1.0)
        assert exp.visual_progress == pytest.approx(0.0)
        exp.update(0.5)
        assert exp.visual_progress == pytest.approx(0.5)

    def test_dead_tank_skipped(self):
        owner = _make_tank(x=0, y=0)
        target = _make_tank(x=50, y=0, health=100)
        target.is_alive = False
        exp = Explosion(50, 0, radius=120, damage=70,
                        damage_type=DamageType.EXPLOSIVE, owner=owner)
        events = exp.resolve_damage([target], [])
        assert events == []


# ---------------------------------------------------------------------------
# TestGrenadeBullet — explosive bullet properties
# ---------------------------------------------------------------------------

class TestGrenadeBullet:
    """Verify bullet AoE fields from config."""

    def _make_grenade_config(self) -> dict:
        return {
            "type": "grenade_launcher",
            "damage": 70,
            "speed": 280,
            "fire_rate": 0.25,
            "max_bounces": 0,
            "max_range": 600,
            "damage_type": "explosive",
            "aoe_radius": 120,
            "aoe_falloff": 0.25,
        }

    def test_is_explosive_flag(self):
        owner = _make_tank()
        b = Bullet(100, 100, 0, owner, self._make_grenade_config())
        assert b.is_explosive is True

    def test_aoe_radius_from_config(self):
        owner = _make_tank()
        b = Bullet(100, 100, 0, owner, self._make_grenade_config())
        assert b.aoe_radius == 120

    def test_aoe_falloff_from_config(self):
        owner = _make_tank()
        b = Bullet(100, 100, 0, owner, self._make_grenade_config())
        assert b.aoe_falloff == 0.25

    def test_standard_bullet_not_explosive(self):
        owner = _make_tank()
        cfg = {"type": "standard_shell", "damage": 20, "speed": 500}
        b = Bullet(100, 100, 0, owner, cfg)
        assert b.is_explosive is False
        assert b.aoe_radius == 0

    def test_detonated_at_max_range(self):
        owner = _make_tank()
        cfg = self._make_grenade_config()
        cfg["max_range"] = 50  # short range for test
        b = Bullet(100, 100, 0, owner, cfg)
        # Simulate enough updates to exceed max_range
        for _ in range(20):
            b.update(0.05)
        assert not b.is_alive
        assert b._detonated is True


# ---------------------------------------------------------------------------
# TestStoneDestruction — partial destruction and rubble generation
# ---------------------------------------------------------------------------

class TestStoneDestruction:
    """Verify stone wall material and rubble generation."""

    def _stone_config(self) -> dict:
        return {
            "hp": 400,
            "destructible": True,
            "color": [90, 85, 75],
            "damage_filters": [],
            "partial_destruction": True,
            "rubble_material": "rubble",
        }

    def _rubble_config(self) -> dict:
        return {
            "hp": 80,
            "destructible": True,
            "color": [70, 65, 58],
            "damage_filters": [],
            "partial_destruction": False,
        }

    def test_stone_is_destructible(self):
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=self._stone_config())
        assert obs.destructible is True

    def test_stone_hp(self):
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=self._stone_config())
        assert obs.max_hp == 400

    def test_partial_destruction_flag(self):
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=self._stone_config())
        assert obs.partial_destruction is True

    def test_rubble_pieces_generated(self):
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=self._stone_config())
        materials = {"rubble": self._rubble_config()}
        pieces = obs.get_rubble_pieces(materials)
        assert len(pieces) >= 2

    def test_rubble_material_type(self):
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=self._stone_config())
        materials = {"rubble": self._rubble_config()}
        pieces = obs.get_rubble_pieces(materials)
        for piece in pieces:
            assert piece.material_type == "rubble"

    def test_rubble_pieces_smaller(self):
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=self._stone_config())
        materials = {"rubble": self._rubble_config()}
        pieces = obs.get_rubble_pieces(materials)
        for piece in pieces:
            assert piece.width < obs.width or piece.height < obs.height

    def test_rubble_hp(self):
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=self._stone_config())
        materials = {"rubble": self._rubble_config()}
        pieces = obs.get_rubble_pieces(materials)
        for piece in pieces:
            assert piece.max_hp == 80

    def test_no_rubble_when_flag_false(self):
        cfg = self._stone_config()
        cfg["partial_destruction"] = False
        obs = Obstacle(0, 0, 200, 50, material_type="stone",
                       material_config=cfg)
        materials = {"rubble": self._rubble_config()}
        pieces = obs.get_rubble_pieces(materials)
        assert pieces == []


# ---------------------------------------------------------------------------
# TestCooldownIndicator — tank slot_cooldowns property
# ---------------------------------------------------------------------------

class TestCooldownIndicator:
    """Verify cooldown timer reporting for HUD overlay."""

    def test_slot_cooldowns_property_exists(self):
        tank = _make_tank()
        assert hasattr(tank, "slot_cooldowns")

    def test_cooldown_length_matches_slots(self):
        tank = _make_tank()
        tank.load_weapons([
            {"type": "standard_shell", "fire_rate": 2.0},
            {"type": "spread_shot", "fire_rate": 1.5},
        ])
        assert len(tank.slot_cooldowns) == 2

    def test_cooldown_decrements(self):
        tank = _make_tank()
        tank.load_weapons([{"type": "standard_shell", "fire_rate": 1.0}])
        # Force a fire to start cooldown
        tank.controller = type("C", (), {
            "get_input": lambda self: TankInput(fire=True)
        })()
        tank.update(0.016)
        cd_before = tank.slot_cooldowns[0]
        assert cd_before > 0
        tank.controller = type("C", (), {
            "get_input": lambda self: TankInput(fire=False)
        })()
        tank.update(0.1)
        cd_after = tank.slot_cooldowns[0]
        assert cd_after < cd_before

    def test_cooldown_zero_when_ready(self):
        tank = _make_tank()
        tank.load_weapons([{"type": "standard_shell", "fire_rate": 1.0}])
        # No firing → cooldown should be 0
        assert tank.slot_cooldowns[0] <= 0.0
