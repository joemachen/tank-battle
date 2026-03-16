"""
tests/test_collision.py

Unit tests for CollisionSystem geometry helpers, bullet-vs-tank logic,
tank obstacle push-back, and bullet reflection.
No pygame, no rendering — pure math and stub objects only.
"""

import math

import pytest

from game.entities.bullet import Bullet
from game.entities.obstacle import Obstacle
from game.systems.collision import TANK_RADIUS, CollisionSystem


# ---------------------------------------------------------------------------
# Minimal stubs for check_bullet_vs_tank tests
# (avoid pulling in pygame or full entity constructors)
# ---------------------------------------------------------------------------

class _StubBullet:
    def __init__(self, pos: tuple, owner, damage: int = 25):
        self.x, self.y = pos
        self.owner = owner
        self.damage = damage
        self.is_alive = True

    @property
    def position(self) -> tuple:
        return (self.x, self.y)

    def destroy(self) -> None:
        self.is_alive = False


class _StubTank:
    def __init__(self, pos: tuple, health: int = 100):
        self.x, self.y = pos
        self.health = health
        self.max_health = health
        self.is_alive = True

    @property
    def position(self) -> tuple:
        return (self.x, self.y)

    def take_damage(self, amount: int) -> None:
        self.health -= amount
        if self.health <= 0:
            self.is_alive = False


class TestCirclesOverlap:
    def test_overlapping_circles(self):
        assert CollisionSystem.circles_overlap((0, 0), 10, (5, 0), 10) is True

    def test_touching_circles(self):
        # Exactly touching — should NOT count as overlap (strict <)
        assert CollisionSystem.circles_overlap((0, 0), 5, (10, 0), 5) is False

    def test_non_overlapping_circles(self):
        assert CollisionSystem.circles_overlap((0, 0), 5, (20, 0), 5) is False

    def test_same_position(self):
        assert CollisionSystem.circles_overlap((3, 3), 1, (3, 3), 1) is True


class TestCircleVsRect:
    def test_circle_inside_rect(self):
        assert CollisionSystem.circle_vs_rect((50, 50), 5, (10, 10, 100, 100)) is True

    def test_circle_overlapping_corner(self):
        # Circle centered at (0, 0) with radius 10 — corner of rect at (7, 7)
        assert CollisionSystem.circle_vs_rect((0, 0), 10, (7, 7, 50, 50)) is True

    def test_circle_far_from_rect(self):
        assert CollisionSystem.circle_vs_rect((200, 200), 5, (0, 0, 50, 50)) is False

    def test_circle_touching_edge(self):
        # Circle just touching left edge of rect — should NOT overlap (strict <)
        assert CollisionSystem.circle_vs_rect((-5, 25), 5, (0, 0, 50, 50)) is False


class TestCheckBulletVsTank:
    def test_hit_applies_damage_and_destroys_bullet(self):
        """Bullet overlapping a non-owner tank: damage applied, bullet destroyed."""
        cs = CollisionSystem()
        tank = _StubTank((100, 100), health=100)
        bullet = _StubBullet((100, 100), owner=object(), damage=25)  # owner ≠ tank

        result = cs.check_bullet_vs_tank(bullet, tank)

        assert result is True
        assert not bullet.is_alive
        assert tank.health == 75

    def test_self_hit_immunity(self):
        """Bullet whose owner IS the target tank must not deal damage."""
        cs = CollisionSystem()
        tank = _StubTank((100, 100), health=100)
        bullet = _StubBullet((100, 100), owner=tank, damage=25)  # owner == tank

        result = cs.check_bullet_vs_tank(bullet, tank)

        assert result is False
        assert bullet.is_alive          # bullet not destroyed
        assert tank.health == 100       # no damage

    def test_ai_bullet_damages_player_not_ai(self):
        """AI-owned bullet: immune to the AI tank, must damage the player tank."""
        cs = CollisionSystem()
        player_tank = _StubTank((100, 100), health=100)
        ai_tank = _StubTank((100, 100), health=200)
        bullet = _StubBullet((100, 100), owner=ai_tank, damage=25)

        # Self-hit immunity: AI bullet must NOT hit the AI tank
        result_self = cs.check_bullet_vs_tank(bullet, ai_tank)
        assert result_self is False
        assert bullet.is_alive
        assert ai_tank.health == 200

        # Cross-ownership: AI bullet MUST hit the player tank
        result_cross = cs.check_bullet_vs_tank(bullet, player_tank)
        assert result_cross is True
        assert not bullet.is_alive
        assert player_tank.health == 75


# ---------------------------------------------------------------------------
# Tank push-back from obstacles
# ---------------------------------------------------------------------------

class TestTankObstaclePushback:
    def _make_cs(self):
        return CollisionSystem()

    def test_tank_pushed_out_from_left(self):
        """Tank overlapping obstacle from the left is repositioned outside it."""
        cs = self._make_cs()
        # Tank center at (185, 150), TANK_RADIUS=22 → left edge at 163, inside obs left at 200
        tank = _StubTank((185, 150))
        obs = Obstacle(200, 100, 200, 100)  # x=[200,400], y=[100,200]
        cs._tanks_vs_obstacles([tank], [obs])
        assert not cs._circle_vs_rect(tank.position, TANK_RADIUS, obs.rect)

    def test_tank_pushed_out_from_above(self):
        """Tank overlapping obstacle from above is repositioned outside it."""
        cs = self._make_cs()
        # Tank center at (250, 185), TANK_RADIUS=22 → bottom edge at 207, inside obs top at 200
        tank = _StubTank((250, 185))
        obs = Obstacle(200, 200, 200, 100)  # x=[200,400], y=[200,300]
        cs._tanks_vs_obstacles([tank], [obs])
        assert not cs._circle_vs_rect(tank.position, TANK_RADIUS, obs.rect)

    def test_dead_tank_not_pushed(self):
        """A dead tank is not repositioned."""
        cs = self._make_cs()
        tank = _StubTank((185, 150))
        tank.is_alive = False
        obs = Obstacle(200, 100, 200, 100)
        original_x = tank.x
        cs._tanks_vs_obstacles([tank], [obs])
        assert tank.x == original_x


# ---------------------------------------------------------------------------
# Bullet reflection off obstacles
# ---------------------------------------------------------------------------

def _make_bouncing_bullet(x: float, y: float, angle: float) -> Bullet:
    """Construct a bouncing_round bullet for reflection tests (no pygame needed)."""
    config = {
        "type": "bouncing_round",
        "speed": 400,
        "damage": 20,
        "max_bounces": 3,
        "max_range": 2400,
    }
    return Bullet(x, y, angle, object(), config)


class TestBulletReflection:
    def test_reflect_off_horizontal_surface(self):
        """Bullet traveling downward hitting top face of obstacle → _dy inverts."""
        # Bullet at (50, 97) heading down (angle=90°); obs top face at y=100
        bullet = _make_bouncing_bullet(50, 97, 90.0)
        obs = Obstacle(0, 100, 200, 100)
        cs = CollisionSystem()
        original_dy = bullet._dy

        cs._reflect_bullet(bullet, obs)

        assert bullet._dy == pytest.approx(-original_dy)
        assert bullet.bounces_remaining == 2

    def test_reflect_off_vertical_surface(self):
        """Bullet traveling right hitting left face of obstacle → _dx inverts."""
        # Bullet at (97, 50) heading right (angle=0°); obs left face at x=100
        bullet = _make_bouncing_bullet(97, 50, 0.0)
        obs = Obstacle(100, 0, 100, 100)
        cs = CollisionSystem()
        original_dx = bullet._dx

        cs._reflect_bullet(bullet, obs)

        assert bullet._dx == pytest.approx(-original_dx)
        assert bullet.bounces_remaining == 2

    def test_reflect_updates_angle(self):
        """After reflection, bullet.angle matches the new _dx/_dy direction."""
        bullet = _make_bouncing_bullet(50, 97, 90.0)   # heading straight down
        obs = Obstacle(0, 100, 200, 100)
        CollisionSystem()._reflect_bullet(bullet, obs)
        expected_angle = math.degrees(math.atan2(bullet._dy, bullet._dx))
        assert bullet.angle == pytest.approx(expected_angle)

    def test_no_bounce_remaining_destroys_bullet(self):
        """Standard bullet (max_bounces=0) touching obstacle is destroyed, not reflected."""
        config = {"type": "standard_shell", "speed": 420, "damage": 25,
                  "max_bounces": 0, "max_range": 1400}
        bullet = Bullet(50, 97, 90.0, object(), config)
        obs = Obstacle(0, 100, 200, 100)
        cs = CollisionSystem()
        cs._bullets_vs_obstacles([bullet], [obs])
        assert not bullet.is_alive

    def test_bouncing_round_survives_first_hit(self):
        """bouncing_round bullet survives its first obstacle hit (has bounces remaining)."""
        bullet = _make_bouncing_bullet(50, 97, 90.0)
        obs = Obstacle(0, 100, 200, 100)
        cs = CollisionSystem()
        cs._bullets_vs_obstacles([bullet], [obs])
        assert bullet.is_alive
        assert bullet.bounces_remaining == 2


# ---------------------------------------------------------------------------
# Material system — take_damage() behaviour
# ---------------------------------------------------------------------------

_BRICK_CFG = {"display_name": "Brick", "hp": 150, "destructible": True,
              "damage_filters": [], "color": [160, 75, 45]}

_STONE_CFG = {"display_name": "Stone", "hp": 9999, "destructible": False,
              "damage_filters": [], "color": [90, 85, 75]}

_STEEL_CFG = {"display_name": "Reinforced Steel", "hp": 500, "destructible": True,
              "damage_filters": ["explosive"], "color": [65, 80, 95]}

_CRATE_CFG = {"display_name": "Crate", "hp": 40, "destructible": True,
              "damage_filters": [], "color": [140, 110, 55]}


class TestObstacleMaterials:
    def test_bullet_damages_destructible_obstacle(self):
        """Standard bullet reduces hp on a brick obstacle."""
        obs = Obstacle(0, 100, 200, 100, material_type="brick", material_config=_BRICK_CFG)
        obs.take_damage(25, damage_type="standard")
        assert obs.hp == 125
        assert obs.is_alive

    def test_bullet_does_not_damage_indestructible_obstacle(self):
        """Stone obstacle ignores all damage (destructible=False)."""
        obs = Obstacle(0, 100, 200, 100, material_type="stone", material_config=_STONE_CFG)
        obs.take_damage(25, damage_type="standard")
        assert obs.hp == 9999
        assert obs.is_alive

    def test_damage_filter_blocks_wrong_damage_type(self):
        """reinforced_steel only accepts 'explosive' — standard damage is blocked."""
        obs = Obstacle(0, 100, 200, 100, material_type="reinforced_steel",
                       material_config=_STEEL_CFG)
        obs.take_damage(25, damage_type="standard")
        assert obs.hp == 500   # unchanged
        assert obs.is_alive

    def test_obstacle_dies_when_hp_reaches_zero(self):
        """Crate (hp=40) is destroyed after receiving enough standard damage."""
        obs = Obstacle(0, 100, 200, 100, material_type="crate", material_config=_CRATE_CFG)
        obs.take_damage(25, damage_type="standard")
        assert obs.is_alive          # 40 - 25 = 15 hp remaining
        obs.take_damage(25, damage_type="standard")
        assert not obs.is_alive      # 15 - 25 → 0 hp → destroyed
        assert obs.hp == 0


# ---------------------------------------------------------------------------
# Tank-to-Tank Collision Damage
# ---------------------------------------------------------------------------

class _StubTank2:
    """Extended stub with vx/vy and angle for collision damage tests."""
    def __init__(self, x: float, y: float, angle: float = 0.0,
                 health: int = 100, vx: float = 0.0, vy: float = 0.0):
        self.x = x
        self.y = y
        self.angle = angle
        self.health = health
        self.max_health = health
        self.is_alive = True
        self.vx = vx
        self.vy = vy

    @property
    def position(self):
        return (self.x, self.y)

    def take_damage(self, amount: int) -> None:
        self.health -= amount
        if self.health <= 0:
            self.is_alive = False


class TestTankToTankCollisionDamage:
    """Verify _impact_damage returns the correct base value for each zone."""

    def test_front_hit_returns_front_damage(self):
        """Striker directly in front of struck (diff ≈ 0°) → COLLISION_DAMAGE_FRONT."""
        from game.utils.constants import COLLISION_DAMAGE_FRONT
        # Struck faces right (angle=0); striker is to the right → bearing=0° → diff=0°
        struck = _StubTank2(x=0, y=0, angle=0.0)
        striker = _StubTank2(x=50, y=0, angle=0.0)
        dmg = CollisionSystem._impact_damage(striker, struck)
        assert dmg == COLLISION_DAMAGE_FRONT

    def test_side_hit_returns_side_damage(self):
        """Striker perpendicular to struck (diff ≈ 90°) → COLLISION_DAMAGE_SIDE."""
        from game.utils.constants import COLLISION_DAMAGE_SIDE
        # Struck faces right (angle=0); striker is directly above → bearing=270° → diff≈90°
        struck = _StubTank2(x=0, y=0, angle=0.0)
        striker = _StubTank2(x=0, y=-50, angle=0.0)   # y-up = bearing -90° = 270° → diff 90°
        dmg = CollisionSystem._impact_damage(striker, struck)
        assert dmg == COLLISION_DAMAGE_SIDE

    def test_rear_hit_returns_rear_damage(self):
        """Striker directly behind struck (diff ≈ 180°) → COLLISION_DAMAGE_REAR."""
        from game.utils.constants import COLLISION_DAMAGE_REAR
        # Struck faces right (angle=0); striker is to the left → bearing=180° → diff=180°
        struck = _StubTank2(x=0, y=0, angle=0.0)
        striker = _StubTank2(x=-50, y=0, angle=0.0)
        dmg = CollisionSystem._impact_damage(striker, struck)
        assert dmg == COLLISION_DAMAGE_REAR

    def test_dead_tank_skipped_in_tank_vs_tank(self):
        """A dead tank must not participate in tank-vs-tank collision."""
        cs = CollisionSystem()
        a = _StubTank2(x=0, y=0, angle=0.0, health=100)
        b = _StubTank2(x=10, y=0, angle=0.0, health=100)  # overlapping
        b.is_alive = False
        a_health_before = a.health
        cs._tanks_vs_tanks([a, b])
        assert a.health == a_health_before  # a must not be damaged

    def test_push_back_separates_overlapping_tanks(self):
        """After push-back, two overlapping tanks must not overlap."""
        import math
        cs = CollisionSystem()
        from game.systems.collision import TANK_RADIUS
        # Place them 5px apart (combined radius = 44px) so they definitely overlap
        a = _StubTank2(x=0, y=0, angle=0.0, vx=100, vy=0)
        b = _StubTank2(x=5, y=0, angle=0.0, vx=-100, vy=0)
        cs._tanks_vs_tanks([a, b])
        dist = math.hypot(b.x - a.x, b.y - a.y)
        assert dist >= TANK_RADIUS * 2 - 0.01   # allow tiny float tolerance

    def test_side_hit_deals_more_damage_than_front(self):
        """COLLISION_DAMAGE_SIDE must exceed COLLISION_DAMAGE_FRONT."""
        from game.utils.constants import COLLISION_DAMAGE_FRONT, COLLISION_DAMAGE_SIDE
        assert COLLISION_DAMAGE_SIDE > COLLISION_DAMAGE_FRONT
