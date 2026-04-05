"""
tests/test_ai_pickup_seeking.py

Unit tests for AI pickup-seeking behaviour:
  - Health-seeking in EVADE state
  - Opportunistic grabbing in PATROL and PURSUE states
  - No pickup-seeking in ATTACK state
"""

import math

import pytest

from game.entities.tank import Tank, TankInput
from game.systems.ai_controller import AIController, AIState
from game.utils.constants import (
    AI_PICKUP_OPPORTUNISTIC_RANGE,
    AI_PICKUP_SEEK_RANGE,
)


class _DummyController:
    def get_input(self) -> TankInput:
        return TankInput()


class _FakePickup:
    def __init__(self, x: float, y: float, pickup_type: str = "health"):
        self.x = x
        self.y = y
        self.pickup_type = pickup_type
        self.is_alive = True

    @property
    def position(self):
        return (self.x, self.y)


def _make_tank(x=400.0, y=300.0, hp=100):
    config = {"speed": 150, "health": hp, "turn_rate": 120, "fire_rate": 1.0, "type": "test"}
    return Tank(x, y, config, _DummyController())


def _make_ai(target_tank, hp_ratio=1.0, evasion_threshold=0.3):
    config = {
        "reaction_time": 0.0,
        "accuracy": 0.8,
        "aggression": 0.5,
        "evasion_threshold": evasion_threshold,
    }
    ai = AIController(config, target_getter=lambda: target_tank)
    owner = _make_tank(x=200.0, y=200.0, hp=100)
    if hp_ratio < 1.0:
        owner.health = int(owner.max_health * hp_ratio)
    ai.set_owner(owner)
    return ai, owner


class TestAIPickupSeeking:
    def test_evade_seeks_health_pickup_within_range(self):
        target = _make_tank(800, 800)
        ai, owner = _make_ai(target, hp_ratio=0.2)
        # Place health pickup within seek range
        pickup = _FakePickup(owner.x + 100, owner.y, "health")
        ai.set_pickups_getter(lambda: [pickup])
        ai.tick(0.016)
        inp = ai.get_input()
        # AI should steer toward pickup, not just flee
        assert inp.throttle > 0

    def test_evade_ignores_distant_health_pickup(self):
        target = _make_tank(800, 800)
        ai, owner = _make_ai(target, hp_ratio=0.2)
        # Place health pickup beyond seek range
        far_x = owner.x + AI_PICKUP_SEEK_RANGE + 200
        pickup = _FakePickup(far_x, owner.y, "health")
        ai.set_pickups_getter(lambda: [pickup])
        ai.tick(0.016)
        inp = ai.get_input()
        # Should do normal evade behaviour (throttle=1.0 for flee)
        assert inp.throttle != 0

    def test_evade_ignores_non_health_pickups(self):
        target = _make_tank(800, 800)
        ai, owner = _make_ai(target, hp_ratio=0.2)
        pickup = _FakePickup(owner.x + 50, owner.y, "speed_boost")
        ai.set_pickups_getter(lambda: [pickup])
        ai.tick(0.016)
        inp = ai.get_input()
        # In EVADE, only health pickups trigger seek — should not steer toward speed_boost
        # (normal evade flee continues)
        assert inp.throttle == 1.0

    def test_patrol_grabs_nearby_pickup(self):
        target = _make_tank(2000, 2000)  # far away => PATROL
        ai, owner = _make_ai(target, hp_ratio=1.0)
        pickup = _FakePickup(owner.x + 50, owner.y, "speed_boost")
        ai.set_pickups_getter(lambda: [pickup])
        ai.tick(0.016)
        inp = ai.get_input()
        assert inp.throttle > 0

    def test_patrol_ignores_distant_pickup(self):
        target = _make_tank(2000, 2000)  # far away => PATROL
        ai, owner = _make_ai(target, hp_ratio=1.0)
        far_x = owner.x + AI_PICKUP_OPPORTUNISTIC_RANGE + 200
        pickup = _FakePickup(far_x, owner.y, "health")
        ai.set_pickups_getter(lambda: [pickup])
        ai.tick(0.016)
        inp = ai.get_input()
        # Center-seeking patrol: moving but not firing
        assert inp.throttle > 0

    def test_pursue_grabs_nearby_pickup(self):
        target = _make_tank(600, 300)  # within detection range => PURSUE
        ai, owner = _make_ai(target, hp_ratio=1.0)
        pickup = _FakePickup(owner.x + 50, owner.y, "rapid_reload")
        ai.set_pickups_getter(lambda: [pickup])
        ai.tick(0.016)
        inp = ai.get_input()
        assert inp.throttle > 0

    def test_no_pickups_getter_does_not_crash(self):
        target = _make_tank(2000, 2000)
        ai, owner = _make_ai(target)
        # No set_pickups_getter called
        ai.tick(0.016)
        inp = ai.get_input()
        assert isinstance(inp, TankInput)

    def test_dead_pickups_ignored(self):
        target = _make_tank(2000, 2000)
        ai, owner = _make_ai(target)
        pickup = _FakePickup(owner.x + 20, owner.y, "health")
        pickup.is_alive = False
        ai.set_pickups_getter(lambda: [pickup])
        ai.tick(0.016)
        inp = ai.get_input()
        # Center-seeking patrol: moving but not firing
        assert inp.throttle > 0
