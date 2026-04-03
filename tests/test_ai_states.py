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
        self.ultimate = None
        self._cloaked = False

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

    def test_evade_not_triggered_above_threshold(self):
        """Health just above evasion_threshold must NOT trigger EVADE."""
        # 41% health > 0.35 threshold — should be in ATTACK (target is within attack range)
        owner = MockTank(x=0, y=0, health=41, max_health=100)
        target = MockTank(x=AI_ATTACK_RANGE - 10, y=0)
        ctrl = self._make_controller(owner, target, evasion_threshold=0.35)
        ctrl.get_input()
        assert ctrl._state == AIState.ATTACK

    def test_state_name_property(self):
        """state_name returns the current state as a string without private access."""
        owner = MockTank(x=0, y=0)
        target = MockTank(x=AI_DETECTION_RANGE + 100, y=0)
        ctrl = self._make_controller(owner, target)
        ctrl.get_input()
        assert ctrl.state_name == "PATROL"
        assert ctrl.state_name == ctrl._state.name

    def test_recovery_entered_when_stuck(self):
        """
        AI transitions to RECOVERY when the stuck detector fires.
        Target is in PURSUE range so the AI wants to move; tick() calls
        at the same position fill the window with zero displacement.
        """
        owner = MockTank(x=0, y=0)
        target = MockTank(x=AI_DETECTION_RANGE - 10, y=0)   # in PURSUE range
        ctrl = self._make_controller(owner, target)
        # Fill stuck window: owner stays at (0, 0) — zero displacement
        # window=0.5s, dt=0.1 → 7 ticks gives ~0.7s of history (>= 80% fill)
        for _ in range(7):
            ctrl.tick(0.1)
        ctrl.get_input()
        assert ctrl._state == AIState.RECOVERY

    def test_recovery_produces_reverse_input(self):
        """_recovery_input() returns negative throttle (reversing)."""
        owner = MockTank(x=0, y=0)
        target = MockTank(x=AI_DETECTION_RANGE - 10, y=0)
        ctrl = self._make_controller(owner, target)
        for _ in range(7):
            ctrl.tick(0.1)
        tank_input = ctrl.get_input()
        assert tank_input.throttle < 0.0

    def test_recovery_state_name(self):
        """state_name reports 'RECOVERY' while in the recovery sub-state."""
        owner = MockTank(x=0, y=0)
        target = MockTank(x=AI_DETECTION_RANGE - 10, y=0)
        ctrl = self._make_controller(owner, target)
        for _ in range(7):
            ctrl.tick(0.1)
        ctrl.get_input()
        assert ctrl.state_name == "RECOVERY"

    def test_evade_fires_when_target_in_attack_range(self):
        """AI in EVADE state should fire when the target is within attack range."""
        owner = MockTank(x=0, y=0, health=10, max_health=100)
        target = MockTank(x=AI_ATTACK_RANGE - 10, y=0)
        ctrl = self._make_controller(owner, target, evasion_threshold=0.35)
        # aggression=0.8 so most calls should fire — sample many times
        fired_count = 0
        for _ in range(100):
            ctrl._state = AIState.EVADE  # force state
            inp = ctrl.get_input()
            if inp.fire:
                fired_count += 1
        # With 0.8 aggression, expect ~80 fires out of 100
        assert fired_count > 50

    def test_evade_does_not_fire_when_target_out_of_range(self):
        """AI in EVADE state should NOT fire when the target is beyond attack range."""
        owner = MockTank(x=0, y=0, health=10, max_health=100)
        target = MockTank(x=AI_ATTACK_RANGE + 100, y=0)
        ctrl = self._make_controller(owner, target, evasion_threshold=0.35)
        fired_count = 0
        for _ in range(50):
            ctrl._state = AIState.EVADE
            inp = ctrl.get_input()
            if inp.fire:
                fired_count += 1
        assert fired_count == 0
