"""
tests/test_damage_types.py

Tests for the v0.21 damage type system.
Covers the DamageType enum, bullet damage_type field, collision routing,
obstacle backward compatibility, and damage-type bullet color mapping.
"""

import pytest

from game.utils.damage_types import DamageType, parse_damage_type


# ===================================================================
# TestDamageTypeEnum — enum members and parse function
# ===================================================================

class TestDamageTypeEnum:
    """Verify enum members exist and parse_damage_type handles all cases."""

    def test_standard_exists(self):
        assert DamageType.STANDARD is not None

    def test_explosive_exists(self):
        assert DamageType.EXPLOSIVE is not None

    def test_fire_exists(self):
        assert DamageType.FIRE is not None

    def test_ice_exists(self):
        assert DamageType.ICE is not None

    def test_poison_exists(self):
        assert DamageType.POISON is not None

    def test_electric_exists(self):
        assert DamageType.ELECTRIC is not None

    def test_parse_lowercase(self):
        assert parse_damage_type("standard") == DamageType.STANDARD

    def test_parse_uppercase(self):
        assert parse_damage_type("EXPLOSIVE") == DamageType.EXPLOSIVE

    def test_parse_mixed_case(self):
        assert parse_damage_type("Fire") == DamageType.FIRE

    def test_parse_unknown_returns_standard(self):
        assert parse_damage_type("plasma") == DamageType.STANDARD

    def test_parse_empty_returns_standard(self):
        assert parse_damage_type("") == DamageType.STANDARD


# ===================================================================
# TestBulletDamageType — bullet reads config correctly
# ===================================================================

class TestBulletDamageType:
    """Verify Bullet entity reads damage_type from weapon config."""

    def _make_bullet(self, config: dict):
        from game.entities.bullet import Bullet
        return Bullet(x=100, y=100, angle=0, owner=None, config=config)

    def test_default_is_standard(self):
        b = self._make_bullet({})
        assert b.damage_type == DamageType.STANDARD

    def test_explicit_standard(self):
        b = self._make_bullet({"damage_type": "standard"})
        assert b.damage_type == DamageType.STANDARD

    def test_explosive_from_config(self):
        b = self._make_bullet({"damage_type": "explosive"})
        assert b.damage_type == DamageType.EXPLOSIVE

    def test_fire_from_config(self):
        b = self._make_bullet({"damage_type": "fire"})
        assert b.damage_type == DamageType.FIRE

    def test_unknown_config_falls_back(self):
        b = self._make_bullet({"damage_type": "antimatter"})
        assert b.damage_type == DamageType.STANDARD


# ===================================================================
# TestCollisionDamageTypeRouting — damage type flows through collision
# ===================================================================

class TestCollisionDamageTypeRouting:
    """Verify CollisionSystem passes damage_type from bullet to tank."""

    def _make_tank(self, x=0, y=0):
        from game.entities.tank import Tank, TankInput

        class DummyController:
            def get_input(self):
                return TankInput()

        return Tank(x=x, y=y, config={"health": 100}, controller=DummyController())

    def _make_bullet(self, x, y, owner=None, damage_type="standard"):
        from game.entities.bullet import Bullet
        return Bullet(x=x, y=y, angle=0, owner=owner,
                      config={"damage": 10, "damage_type": damage_type})

    def test_bullet_hit_tank_passes_damage_type(self):
        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()
        tank = self._make_tank(x=100, y=100)
        bullet = self._make_bullet(x=100, y=100, damage_type="explosive")
        assert bullet.damage_type == DamageType.EXPLOSIVE
        cs.check_bullet_vs_tank(bullet, tank)
        # Tank took damage (no exception from DamageType param)
        assert tank.health < 100

    def test_stat_tuple_includes_damage_type(self):
        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()
        owner_tank = self._make_tank(x=0, y=0)
        target_tank = self._make_tank(x=100, y=100)
        bullet = self._make_bullet(x=100, y=100, owner=owner_tank, damage_type="fire")
        events = cs._bullets_vs_tanks([bullet], [target_tank])
        stat_events = [e for e in events if isinstance(e, tuple) and e[0] == "bullet_hit_tank_stat"]
        assert len(stat_events) == 1
        assert len(stat_events[0]) == 4  # (tag, owner, damage, damage_type)
        assert stat_events[0][3] == DamageType.FIRE

    def test_no_self_hit(self):
        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()
        tank = self._make_tank(x=100, y=100)
        bullet = self._make_bullet(x=100, y=100, owner=tank)
        result = cs.check_bullet_vs_tank(bullet, tank)
        assert result is False

    def test_dead_tank_not_hit(self):
        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()
        tank = self._make_tank(x=100, y=100)
        tank.is_alive = False
        bullet = self._make_bullet(x=100, y=100)
        result = cs.check_bullet_vs_tank(bullet, tank)
        assert result is False

    def test_dead_bullet_not_processed(self):
        from game.systems.collision import CollisionSystem
        cs = CollisionSystem()
        tank = self._make_tank(x=100, y=100)
        bullet = self._make_bullet(x=100, y=100)
        bullet.is_alive = False
        result = cs.check_bullet_vs_tank(bullet, tank)
        assert result is False


# ===================================================================
# TestObstacleDamageTypeCompat — accepts enum and string
# ===================================================================

class TestObstacleDamageTypeCompat:
    """Verify Obstacle.take_damage() handles both DamageType enum and string."""

    def _make_obstacle(self, destructible=True, damage_filters=None):
        from game.entities.obstacle import Obstacle
        cfg = {
            "destructible": destructible,
            "hp": 100,
            "damage_filters": damage_filters or [],
            "color": [100, 100, 100],
        }
        return Obstacle(x=0, y=0, width=40, height=40, material_config=cfg)

    def test_accepts_string(self):
        obs = self._make_obstacle()
        obs.take_damage(10, damage_type="standard")
        assert obs.hp == 90

    def test_accepts_enum(self):
        obs = self._make_obstacle()
        obs.take_damage(10, damage_type=DamageType.EXPLOSIVE)
        assert obs.hp == 90

    def test_filter_blocks_wrong_enum(self):
        obs = self._make_obstacle(damage_filters=["explosive"])
        obs.take_damage(50, damage_type=DamageType.STANDARD)
        assert obs.hp == 100  # blocked

    def test_filter_allows_matching_enum(self):
        obs = self._make_obstacle(damage_filters=["explosive"])
        obs.take_damage(50, damage_type=DamageType.EXPLOSIVE)
        assert obs.hp == 50  # allowed


# ===================================================================
# TestTankDamageType — Tank.take_damage() accepts DamageType
# ===================================================================

class TestTankDamageType:
    """Verify Tank.take_damage() accepts DamageType parameter."""

    def _make_tank(self):
        from game.entities.tank import Tank, TankInput

        class DummyController:
            def get_input(self):
                return TankInput()

        return Tank(x=0, y=0, config={"health": 100}, controller=DummyController())

    def test_default_damage_type(self):
        tank = self._make_tank()
        tank.take_damage(10)  # no damage_type arg — should default to STANDARD
        assert tank.health == 90

    def test_explicit_damage_type(self):
        tank = self._make_tank()
        tank.take_damage(10, damage_type=DamageType.FIRE)
        assert tank.health == 90

    def test_explosive_damage_type(self):
        tank = self._make_tank()
        tank.take_damage(25, damage_type=DamageType.EXPLOSIVE)
        assert tank.health == 75


# ===================================================================
# TestDamageTypeBulletColors — color dict completeness
# ===================================================================

class TestDamageTypeBulletColors:
    """Verify DAMAGE_TYPE_BULLET_COLORS covers all DamageType members."""

    def test_all_types_have_colors(self):
        from game.utils.constants import DAMAGE_TYPE_BULLET_COLORS
        for dt in DamageType:
            assert dt.name in DAMAGE_TYPE_BULLET_COLORS, f"Missing color for {dt.name}"

    def test_colors_are_rgb_tuples(self):
        from game.utils.constants import DAMAGE_TYPE_BULLET_COLORS
        for name, color in DAMAGE_TYPE_BULLET_COLORS.items():
            assert isinstance(color, tuple), f"{name} color is not a tuple"
            assert len(color) == 3, f"{name} color does not have 3 components"
            assert all(0 <= c <= 255 for c in color), f"{name} color out of range"
