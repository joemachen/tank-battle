"""
tests/test_collision.py

Unit tests for CollisionSystem geometry helpers and bullet-vs-tank logic.
No pygame, no rendering — pure math and stub objects only.
"""

import pytest

from game.systems.collision import CollisionSystem


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
