"""
tests/test_ai_states.py

Unit tests for AI state machine transition logic.
Uses a mock tank and mock target — no pygame required.
"""

import pytest

from game.systems.ai_controller import AIController, AIState
from game.utils.constants import AI_ATTACK_RANGE, AI_DETECTION_RANGE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(evasion_threshold: float = 0.35) -> dict:
    return {
        "reaction_time": 0.0,
        "accuracy": 0.8,
        "aggression": 0.8,
        "evasion_threshold": evasion_threshold,
    }


class MockTank:
    """Minimal tank stub for AI testing."""
    def __init__(self, x=0.0, y=0.0, health=100, max_health=100):
        self.x = x
        self.y = y
        self.health = health
        self.max_health = max_health
        self.angle = 0.0
        self.is_alive = True

    @property
    def position(self):
        return (self.x, self.y)

    @property
    def health_ratio(self):
        return self.health / self.max_health if self.max_health > 0 else 0.0


# ---------------------------------------------------------------------------
# State transition tests
# ---------------------------------------------------------------------------

class TestAIStateTransitions:
    def _make_controller(self, owner, target, evasion_threshold=0.35):
        ctrl = AIController(_make_config(evasion_threshold), target_getter=lambda: target)
        ctrl.set_owner(owner)
        return ctrl

    def test_patrol_when_target_out_of_range(self):
        owner = MockTank(x=0, y=0)
        target = MockTank(x=AI_DETECTION_RANGE + 100, y=0)
        ctrl = self._make_controller(owner, target)
        ctrl.get_input()
        assert ctrl._state == AIState.PATROL

    def test_pursue_when_target_in_detection_range(self):
        owner = MockTank(x=0, y=0)
        target = MockTank(x=AI_DETECTION_RANGE - 10, y=0)
        ctrl = self._make_controller(owner, target)
        ctrl.get_input()
        assert ctrl._state == AIState.PURSUE

    def test_attack_when_target_in_attack_range(self):
        owner = MockTank(x=0, y=0)
        target = MockTank(x=AI_ATTACK_RANGE - 10, y=0)
        ctrl = self._make_controller(owner, target)
        ctrl.get_input()
        assert ctrl._state == AIState.ATTACK

    def test_evade_when_health_low(self):
        owner = MockTank(x=0, y=0, health=20, max_health=100)
        target = MockTank(x=50, y=0)
        ctrl = self._make_controller(owner, target, evasion_threshold=0.35)
        ctrl.get_input()
        assert ctrl._state == AIState.EVADE

    def test_no_target_stays_patrol(self):
        owner = MockTank(x=0, y=0)
        ctrl = AIController(_make_config(), target_getter=lambda: None)
        ctrl.set_owner(owner)
        ctrl.get_input()
        assert ctrl._state == AIState.PATROL
