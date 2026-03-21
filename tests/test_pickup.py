"""
tests/test_pickup.py

Unit tests for Pickup entity — apply effects and pulse animation (v0.19).
"""

import math

import pytest

from game.entities.pickup import Pickup
from game.utils.constants import PICKUP_EFFECT_DURATION


class _StubTank:
    """Minimal tank stub for pickup tests."""

    def __init__(self, health=80, max_health=100):
        self.health = health
        self.max_health = max_health
        self.tank_type = "light_tank"
        self._slot_cooldowns = [0.5, 0.3, 0.8]
        self._status_effects: dict = {}

    def apply_status(self, name, value, duration):
        self._status_effects[name] = {"value": value, "timer": duration}

    def has_status(self, name):
        return name in self._status_effects


class TestPickupApplyHealth:
    def test_applies_regen_status(self):
        tank = _StubTank(health=60, max_health=100)
        p = Pickup(0, 0, "health", 40)
        p.apply(tank)
        assert "regen" in tank._status_effects
        assert not p.is_alive

    def test_regen_value_is_heal_per_second(self):
        tank = _StubTank(health=60, max_health=100)
        p = Pickup(0, 0, "health", 40)
        p.apply(tank)
        expected_hps = 40.0 / PICKUP_EFFECT_DURATION
        assert abs(tank._status_effects["regen"]["value"] - expected_hps) < 0.01

    def test_regen_duration_matches_constant(self):
        tank = _StubTank(health=60, max_health=100)
        p = Pickup(0, 0, "health", 40)
        p.apply(tank)
        assert tank._status_effects["regen"]["timer"] == PICKUP_EFFECT_DURATION

    def test_full_hp_not_consumed(self):
        tank = _StubTank(health=100, max_health=100)
        p = Pickup(0, 0, "health", 40)
        p.apply(tank)
        assert p.is_alive  # pickup stays on ground
        assert "regen" not in tank._status_effects

    def test_partial_hp_consumed(self):
        tank = _StubTank(health=99, max_health=100)
        p = Pickup(0, 0, "health", 40)
        p.apply(tank)
        assert not p.is_alive
        assert "regen" in tank._status_effects


class TestPickupApplyRapidReload:
    def test_resets_all_cooldowns(self):
        tank = _StubTank()
        p = Pickup(0, 0, "rapid_reload", 1)
        p.apply(tank)
        assert tank._slot_cooldowns == [0.0, 0.0, 0.0]
        assert not p.is_alive


class TestPickupApplySpeedBoost:
    def test_applies_status(self):
        tank = _StubTank()
        p = Pickup(0, 0, "speed_boost", 1.6)
        p.apply(tank)
        assert "speed_boost" in tank._status_effects
        assert tank._status_effects["speed_boost"]["value"] == 1.6
        assert tank._status_effects["speed_boost"]["timer"] == PICKUP_EFFECT_DURATION
        assert not p.is_alive

    def test_refresh_does_not_stack(self):
        tank = _StubTank()
        p1 = Pickup(0, 0, "speed_boost", 1.6)
        p1.apply(tank)
        # Simulate some time passing
        tank._status_effects["speed_boost"]["timer"] = 3.0
        p2 = Pickup(0, 0, "speed_boost", 1.6)
        p2.apply(tank)
        # Timer should be refreshed, not stacked
        assert tank._status_effects["speed_boost"]["timer"] == PICKUP_EFFECT_DURATION
        assert tank._status_effects["speed_boost"]["value"] == 1.6


class TestPickupApplyGuards:
    def test_dead_pickup_is_noop(self):
        tank = _StubTank(health=60, max_health=100)
        p = Pickup(0, 0, "health", 40)
        p.is_alive = False
        p.apply(tank)
        assert "regen" not in tank._status_effects

    def test_unknown_type_still_collects(self):
        """Unknown pickup type marks as collected but applies no effect."""
        tank = _StubTank(health=60, max_health=100)
        p = Pickup(0, 0, "unknown_type", 99)
        p.apply(tank)
        assert not p.is_alive
        assert tank.health == 60  # no health change


class TestPickupPulse:
    def test_pulse_initial_value(self):
        p = Pickup(0, 0, "health", 40)
        # sin(0) = 0 → pulse = 0.5
        assert abs(p.pulse - 0.5) < 0.01

    def test_pulse_in_range(self):
        p = Pickup(0, 0, "health", 40)
        for dt in [0.1, 0.5, 1.0, 2.0, 5.0]:
            p.update(dt)
            assert 0.0 <= p.pulse <= 1.0

    def test_update_increments_timer(self):
        p = Pickup(0, 0, "health", 40)
        p.update(0.5)
        assert abs(p._pulse_timer - 0.5) < 1e-9


class TestPickupAge:
    def test_age_starts_at_zero(self):
        p = Pickup(0, 0, "health", 40)
        assert p.age == 0.0

    def test_age_increments(self):
        p = Pickup(0, 0, "health", 40)
        p.update(1.5)
        assert abs(p.age - 1.5) < 1e-9


class TestPickupPosition:
    def test_position_property(self):
        p = Pickup(100.0, 200.0, "health", 40)
        assert p.position == (100.0, 200.0)
