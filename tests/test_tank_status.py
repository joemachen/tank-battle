"""
tests/test_tank_status.py

Unit tests for Tank status effects — apply, tick, expire, speed boost (v0.19).
"""

import pytest

from game.entities.tank import Tank
from game.utils.constants import DEFAULT_TANK_SPEED


class _StubController:
    """Minimal controller stub for Tank."""

    class _Intent:
        throttle = 0.0
        rotate = 0.0
        fire = False
        turret_angle = 0.0
        cycle_weapon = 0
        switch_slot = -1

    def get_input(self):
        return self._Intent()


def _make_tank(**overrides):
    config = {
        "type": "light_tank",
        "hp": 100,
        "speed": DEFAULT_TANK_SPEED,
        "turn_rate": 180,
        "fire_rate": 2.0,
    }
    config.update(overrides)
    return Tank(x=400, y=300, config=config, controller=_StubController())


class TestApplyStatus:
    def test_stores_effect(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        assert tank.has_status("speed_boost")
        assert tank._status_effects["speed_boost"]["value"] == 1.6
        assert tank._status_effects["speed_boost"]["timer"] == 5.0

    def test_overwrite_existing(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        tank.apply_status("speed_boost", 2.0, 10.0)
        assert tank._status_effects["speed_boost"]["value"] == 2.0
        assert tank._status_effects["speed_boost"]["timer"] == 10.0


class TestTickStatusEffects:
    def test_decrements_timer(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        tank.tick_status_effects(1.0)
        assert abs(tank._status_effects["speed_boost"]["timer"] - 4.0) < 1e-9

    def test_removes_expired(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 1.0)
        tank.tick_status_effects(1.5)
        assert not tank.has_status("speed_boost")


class TestHasStatus:
    def test_true_when_active(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        assert tank.has_status("speed_boost") is True

    def test_false_when_absent(self):
        tank = _make_tank()
        assert tank.has_status("speed_boost") is False

    def test_false_after_expire(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 0.5)
        tank.tick_status_effects(1.0)
        assert tank.has_status("speed_boost") is False


class TestSpeedBoostInUpdate:
    def test_speed_boost_increases_movement(self):
        """A tank with speed_boost should move faster than one without."""
        tank_normal = _make_tank()
        tank_boosted = _make_tank()
        tank_boosted.apply_status("speed_boost", 1.6, 5.0)

        # Give both tanks forward throttle
        class _ForwardController:
            class _Intent:
                throttle = 1.0
                rotate = 0.0
                fire = False
                turret_angle = 0.0
                cycle_weapon = 0
                switch_slot = -1

            def get_input(self):
                return self._Intent()

        tank_normal.controller = _ForwardController()
        tank_boosted.controller = _ForwardController()

        # Store initial positions
        x_normal_start = tank_normal.x
        x_boosted_start = tank_boosted.x

        tank_normal.update(1.0)
        tank_boosted.update(1.0)

        dx_normal = abs(tank_normal.x - x_normal_start) + abs(tank_normal.y - 300)
        dx_boosted = abs(tank_boosted.x - x_boosted_start) + abs(tank_boosted.y - 300)

        # Boosted tank should move further (1.6x)
        assert dx_boosted > dx_normal

    def test_tick_called_in_update(self):
        """update() should tick status effects — timer should decrease."""
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 2.0)
        tank.update(1.0)
        assert abs(tank._status_effects["speed_boost"]["timer"] - 1.0) < 0.1


class TestRegenStatus:
    def test_regen_heals_over_time(self):
        """Regen status should increase HP across multiple ticks."""
        tank = _make_tank(hp=100)
        tank.health = 60
        # 40 HP over 8 seconds = 5 HP/s
        tank.apply_status("regen", 5.0, 8.0)
        # Tick 20 frames at 0.1s each = 2 seconds → expect ~10 HP healed
        for _ in range(20):
            tank.tick_status_effects(0.1)
        assert tank.health >= 69  # 60 + ~10, conservative bound

    def test_regen_does_not_exceed_max_health(self):
        """Regen should cap healing at max_health."""
        tank = _make_tank(hp=100)
        tank.health = 95
        tank.apply_status("regen", 10.0, 8.0)
        for _ in range(50):
            tank.tick_status_effects(0.1)
        assert tank.health == 100

    def test_regen_expires(self):
        """Regen status should be removed after its timer expires."""
        tank = _make_tank(hp=100)
        tank.health = 60
        tank.apply_status("regen", 5.0, 2.0)
        tank.tick_status_effects(3.0)
        assert not tank.has_status("regen")

    def test_regen_accumulates_fractional_hp(self):
        """Small per-frame heals should accumulate via the _accum float."""
        tank = _make_tank(hp=100)
        tank.health = 50
        # 1 HP/s at small dt means each tick heals 0.016 HP — needs accumulation
        tank.apply_status("regen", 1.0, 10.0)
        for _ in range(60):
            tank.tick_status_effects(1 / 60)
        # After 1 second at 1 HP/s → expect ~1 HP healed
        assert tank.health >= 51
