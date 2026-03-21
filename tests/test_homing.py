"""
tests/test_homing.py

Unit tests for homing missile tracking behavior (v0.19 fix).
"""

import math

import pytest

from game.entities.bullet import Bullet
from game.utils.constants import COLOR_RED, HOMING_BULLET_COLOR, HOMING_BULLET_RADIUS, BULLET_RADIUS
from game.utils.math_utils import angle_difference


class _MockTank:
    """Minimal tank stub for homing tests."""

    def __init__(self, x=0.0, y=0.0, is_alive=True):
        self.x = x
        self.y = y
        self.is_alive = is_alive

    @property
    def position(self):
        return (self.x, self.y)


_HOMING_CONFIG = {
    "type": "homing_missile",
    "speed": 240,
    "damage": 50,
    "max_bounces": 0,
    "max_range": 2000,
    "tracking_strength": 2.5,
}

_STANDARD_CONFIG = {
    "type": "standard_shell",
    "speed": 420,
    "damage": 25,
    "max_bounces": 0,
    "max_range": 1400,
}


class TestHomingBullet:
    def test_non_homing_bullet_flies_straight(self):
        """Standard shell with _track_target called — direction unchanged."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _STANDARD_CONFIG)
        dx_before, dy_before = bullet._dx, bullet._dy
        target = _MockTank(x=100, y=500)
        bullet.set_targets_getter(lambda: [target])
        bullet._track_target(0.1)
        assert bullet._dx == dx_before
        assert bullet._dy == dy_before

    def test_homing_bullet_turns_toward_target(self):
        """Homing bullet aimed right (0°), target above — angle should shift."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _HOMING_CONFIG)
        target = _MockTank(x=100, y=0)  # above (negative Y = up in pygame)
        bullet.set_targets_getter(lambda: [target])
        bullet._track_target(0.1)
        # Bullet should have turned toward -90° (up)
        assert bullet.angle != 0.0
        # The angle should be closer to the target direction
        desired = math.degrees(math.atan2(0 - 100, 100 - 100))  # -90°
        diff_after = abs(angle_difference(bullet.angle, desired))
        diff_before = abs(angle_difference(0.0, desired))
        assert diff_after < diff_before

    def test_homing_ignores_owner(self):
        """Only owner in targets list — no tracking (no candidates)."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _HOMING_CONFIG)
        bullet.set_targets_getter(lambda: [owner])
        dx_before = bullet._dx
        bullet._track_target(0.1)
        assert bullet._dx == dx_before

    def test_homing_ignores_dead_tanks(self):
        """Dead target — no tracking."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _HOMING_CONFIG)
        dead_target = _MockTank(x=100, y=500, is_alive=False)
        bullet.set_targets_getter(lambda: [dead_target])
        dx_before = bullet._dx
        bullet._track_target(0.1)
        assert bullet._dx == dx_before

    def test_homing_tracks_nearest(self):
        """Two targets — bullet turns toward the closer one."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _HOMING_CONFIG)
        near = _MockTank(x=200, y=100)   # 100px away, same Y
        far = _MockTank(x=100, y=600)    # 500px away, below
        bullet.set_targets_getter(lambda: [near, far])
        bullet._track_target(0.1)
        # Bullet should stay close to 0° (toward near target at same Y)
        desired_near = math.degrees(math.atan2(100 - 100, 200 - 100))  # 0°
        diff = abs(angle_difference(bullet.angle, desired_near))
        assert diff < 20.0  # should be very close to 0°

    def test_homing_no_targets_getter_no_crash(self):
        """_targets_getter is None — no crash."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _HOMING_CONFIG)
        bullet._track_target(0.1)  # should not raise

    def test_homing_empty_targets_no_crash(self):
        """Getter returns [] — no crash, no direction change."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _HOMING_CONFIG)
        bullet.set_targets_getter(lambda: [])
        dx_before = bullet._dx
        bullet._track_target(0.1)
        assert bullet._dx == dx_before

    def test_tracking_strength_zero_no_turn(self):
        """Bullet with tracking_strength=0 — _track_target is no-op."""
        owner = _MockTank(x=0, y=0)
        config = dict(_HOMING_CONFIG)
        config["tracking_strength"] = 0
        bullet = Bullet(100, 100, 0.0, owner, config)
        target = _MockTank(x=100, y=500)
        bullet.set_targets_getter(lambda: [target])
        dx_before = bullet._dx
        bullet._track_target(0.1)
        assert bullet._dx == dx_before

    def test_homing_bullet_color_is_red(self):
        """HOMING_BULLET_COLOR should be COLOR_RED."""
        assert HOMING_BULLET_COLOR == COLOR_RED
        assert HOMING_BULLET_RADIUS == BULLET_RADIUS + 1


class TestHomingIntegration:
    def test_update_calls_tracking(self):
        """Bullet.update() should apply tracking before moving."""
        owner = _MockTank(x=0, y=0)
        bullet = Bullet(100, 100, 0.0, owner, _HOMING_CONFIG)
        target = _MockTank(x=100, y=0)  # directly above
        bullet.set_targets_getter(lambda: [target])
        bullet.update(0.1)
        # After update, angle should have shifted toward target
        assert bullet.angle != 0.0
