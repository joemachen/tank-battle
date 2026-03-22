"""
tests/test_arena_bounce.py

Unit tests for arena boundary bullet reflection and destruction.
"""

import math

import pytest

from game.entities.bullet import Bullet
from game.systems.physics import PhysicsSystem
from game.utils.constants import ARENA_HEIGHT, ARENA_WIDTH


class _MockTank:
    def __init__(self, x=400.0, y=300.0):
        self.x = x
        self.y = y
        self.is_alive = True

    @property
    def position(self):
        return (self.x, self.y)


_BOUNCING_CONFIG = {
    "type": "bouncing_round",
    "speed": 400,
    "damage": 20,
    "max_bounces": 3,
    "max_range": 2400,
}

_STANDARD_CONFIG = {
    "type": "standard_shell",
    "speed": 420,
    "damage": 25,
    "max_bounces": 0,
    "max_range": 1400,
}

_HOMING_CONFIG = {
    "type": "homing_missile",
    "speed": 240,
    "damage": 50,
    "max_bounces": 0,
    "max_range": 2000,
    "tracking_strength": 2.5,
}


class TestArenaBounce:
    def _make_physics(self):
        return PhysicsSystem()

    def test_bouncing_bullet_reflects_off_left_wall(self):
        owner = _MockTank()
        bullet = Bullet(2, 100, 180.0, owner, _BOUNCING_CONFIG)
        physics = self._make_physics()
        # Advance so bullet crosses left edge
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        # _dx should now be positive (heading right)
        assert bullet._dx > 0
        assert bullet.bounces_remaining == 2
        assert bullet.is_alive

    def test_bouncing_bullet_reflects_off_right_wall(self):
        owner = _MockTank()
        bullet = Bullet(ARENA_WIDTH - 2, 100, 0.0, owner, _BOUNCING_CONFIG)
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        assert bullet._dx < 0
        assert bullet.bounces_remaining == 2
        assert bullet.is_alive

    def test_bouncing_bullet_reflects_off_top_wall(self):
        owner = _MockTank()
        bullet = Bullet(100, 2, 270.0, owner, _BOUNCING_CONFIG)
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        assert bullet._dy > 0
        assert bullet.bounces_remaining == 2
        assert bullet.is_alive

    def test_bouncing_bullet_reflects_off_bottom_wall(self):
        owner = _MockTank()
        bullet = Bullet(100, ARENA_HEIGHT - 2, 90.0, owner, _BOUNCING_CONFIG)
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        assert bullet._dy < 0
        assert bullet.bounces_remaining == 2
        assert bullet.is_alive

    def test_standard_bullet_destroyed_at_wall(self):
        owner = _MockTank()
        bullet = Bullet(2, 100, 180.0, owner, _STANDARD_CONFIG)
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        assert not bullet.is_alive

    def test_angle_updated_after_arena_reflect(self):
        owner = _MockTank()
        bullet = Bullet(2, 100, 180.0, owner, _BOUNCING_CONFIG)
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        # angle should match _dx/_dy
        expected_angle = math.degrees(math.atan2(bullet._dy, bullet._dx))
        assert abs(bullet.angle - expected_angle) < 0.01

    def test_corner_hit_reflects_both_axes(self):
        owner = _MockTank()
        # Aim toward top-left corner (225° in pygame coords → heading up-left)
        bullet = Bullet(2, 2, 225.0, owner, _BOUNCING_CONFIG)
        dx_before = bullet._dx
        dy_before = bullet._dy
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        # Both axes should have inverted
        assert bullet._dx * dx_before < 0  # sign flipped
        assert bullet._dy * dy_before < 0  # sign flipped
        # Only one bounce consumed for the corner hit
        assert bullet.bounces_remaining == 2
        assert bullet.is_alive

    def test_bullet_clamped_inside_after_reflect(self):
        owner = _MockTank()
        bullet = Bullet(2, 100, 180.0, owner, _BOUNCING_CONFIG)
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        assert 0 <= bullet.x <= ARENA_WIDTH
        assert 0 <= bullet.y <= ARENA_HEIGHT

    def test_homing_bullet_destroyed_at_wall(self):
        owner = _MockTank()
        bullet = Bullet(2, 100, 180.0, owner, _HOMING_CONFIG)
        physics = self._make_physics()
        bullet.update(0.05)
        physics._check_bullet_boundary(bullet)
        assert not bullet.is_alive
