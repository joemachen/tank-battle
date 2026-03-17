"""
tests/test_turret.py

Unit tests for milestone v0.15: decoupled turret aiming.

Covers:
  - TankInput carries turret_angle correctly
  - Tank.update() applies turret_angle from intent
  - Bullet spawns along turret_angle, not tank body angle
  - Camera.screen_to_world is exact inverse of world_to_screen (round-trip)
  - AIController sets turret_angle in all four states
  - PATROL state: turret_angle == owner.angle
  - ATTACK state: turret_angle points toward target (within jitter tolerance)

The pygame stub is installed by conftest.py before this module is imported.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game.entities.tank import Tank, TankInput
from game.systems.ai_controller import AIController, AIState
from game.utils.camera import Camera
from game.utils.math_utils import angle_to


# ---------------------------------------------------------------------------
# Minimal stub controller — returns a fixed TankInput
# ---------------------------------------------------------------------------

class _FixedController:
    def __init__(self, intent: TankInput):
        self._intent = intent

    def get_input(self) -> TankInput:
        return self._intent


def _make_tank(x=0.0, y=0.0, angle=0.0, turret_angle=0.0,
               throttle=0.0, rotate=0.0, fire=False, intent_turret=None):
    """Create a Tank with a fixed-input controller."""
    if intent_turret is None:
        intent_turret = turret_angle
    intent = TankInput(throttle=throttle, rotate=rotate, fire=fire,
                       turret_angle=intent_turret)
    ctrl = _FixedController(intent)
    tank = Tank(x=x, y=y, config={}, controller=ctrl)
    tank.angle = angle
    return tank


# ---------------------------------------------------------------------------
# 1. TankInput carries turret_angle
# ---------------------------------------------------------------------------

class TestTankInput:
    def test_default_turret_angle_is_zero(self):
        inp = TankInput()
        assert inp.turret_angle == 0.0

    def test_turret_angle_set_correctly(self):
        inp = TankInput(turret_angle=45.0)
        assert inp.turret_angle == pytest.approx(45.0)

    def test_turret_angle_negative(self):
        inp = TankInput(turret_angle=-90.0)
        assert inp.turret_angle == pytest.approx(-90.0)

    def test_all_fields_independent(self):
        inp = TankInput(throttle=1.0, rotate=-1.0, fire=True, turret_angle=135.0)
        assert inp.throttle == 1.0
        assert inp.rotate == -1.0
        assert inp.fire is True
        assert inp.turret_angle == pytest.approx(135.0)


# ---------------------------------------------------------------------------
# 2. Tank.update() applies turret_angle from intent
# ---------------------------------------------------------------------------

class TestTankTurretUpdate:
    def test_turret_angle_applied_from_intent(self):
        """Tank.update() sets tank.turret_angle to intent.turret_angle."""
        tank = _make_tank(intent_turret=90.0)
        tank.update(dt=0.016)
        assert tank.turret_angle == pytest.approx(90.0)

    def test_turret_angle_independent_of_hull(self):
        """turret_angle is set by intent; hull angle rotates via rotate input."""
        # Hull starting at 0, rotating right; turret pointing up-left
        tank = _make_tank(angle=0.0, rotate=1.0, intent_turret=270.0)
        tank.update(dt=0.1)
        # Turret should be exactly 270 (from intent)
        assert tank.turret_angle == pytest.approx(270.0)
        # Hull should have rotated (not zero)
        assert tank.angle != pytest.approx(0.0)

    def test_turret_default_zero(self):
        """Fresh tank has turret_angle = 0.0."""
        tank = _make_tank()
        assert tank.turret_angle == 0.0


# ---------------------------------------------------------------------------
# 3. Bullet spawns along turret_angle, not hull angle
# ---------------------------------------------------------------------------

class TestBulletSpawnAngle:
    def test_fire_event_uses_turret_angle(self):
        """Fire event should carry turret_angle, not tank.angle."""
        # Hull points right (0°), turret points down (90°)
        tank = _make_tank(angle=0.0, intent_turret=90.0, fire=True)
        events = tank.update(dt=0.016)
        fire_events = [e for e in events if e[0] == "fire"]
        assert len(fire_events) == 1
        _, _x, _y, fire_angle, _wtype = fire_events[0]
        assert fire_angle == pytest.approx(90.0)

    def test_fire_event_angle_differs_from_hull_when_turret_rotated(self):
        """Verify fire angle != hull angle when turret is offset."""
        tank = _make_tank(angle=45.0, intent_turret=180.0, fire=True)
        events = tank.update(dt=0.016)
        fire_events = [e for e in events if e[0] == "fire"]
        assert len(fire_events) == 1
        _, _x, _y, fire_angle, _wtype = fire_events[0]
        # Should be 180° (turret), NOT 45° (hull)
        assert fire_angle == pytest.approx(180.0)
        assert fire_angle != pytest.approx(45.0)

    def test_no_fire_event_when_not_firing(self):
        """No fire event when fire=False in intent."""
        tank = _make_tank(fire=False, intent_turret=45.0)
        events = tank.update(dt=0.016)
        assert all(e[0] != "fire" for e in events)


# ---------------------------------------------------------------------------
# 4. Camera.screen_to_world is exact inverse of world_to_screen
# ---------------------------------------------------------------------------

class TestCameraRoundTrip:
    def _camera(self):
        """Camera snapped to arena centre (default construction)."""
        return Camera()

    def test_round_trip_center(self):
        cam = self._camera()
        wx, wy = 800.0, 600.0
        sx, sy = cam.world_to_screen(wx, wy)
        wx2, wy2 = cam.screen_to_world(sx, sy)
        assert wx2 == pytest.approx(wx, abs=1e-6)
        assert wy2 == pytest.approx(wy, abs=1e-6)

    def test_round_trip_corner(self):
        cam = self._camera()
        wx, wy = 100.0, 100.0
        sx, sy = cam.world_to_screen(wx, wy)
        wx2, wy2 = cam.screen_to_world(sx, sy)
        assert wx2 == pytest.approx(wx, abs=1e-6)
        assert wy2 == pytest.approx(wy, abs=1e-6)

    def test_round_trip_far_corner(self):
        cam = self._camera()
        wx, wy = 1500.0, 1100.0
        sx, sy = cam.world_to_screen(wx, wy)
        wx2, wy2 = cam.screen_to_world(sx, sy)
        assert wx2 == pytest.approx(wx, abs=1e-6)
        assert wy2 == pytest.approx(wy, abs=1e-6)

    def test_screen_to_world_inverse_of_world_to_screen(self):
        """screen→world is the exact inverse of world→screen for arbitrary point."""
        cam = Camera()
        cam.snap_to(500.0, 400.0)   # off-centre camera position
        for wx, wy in [(0.0, 0.0), (1600.0, 1200.0), (750.0, 620.0)]:
            sx, sy = cam.world_to_screen(wx, wy)
            wx2, wy2 = cam.screen_to_world(sx, sy)
            assert wx2 == pytest.approx(wx, abs=1e-6), f"X mismatch for ({wx},{wy})"
            assert wy2 == pytest.approx(wy, abs=1e-6), f"Y mismatch for ({wx},{wy})"


# ---------------------------------------------------------------------------
# Helpers shared by AI tests
# ---------------------------------------------------------------------------

def _make_ai_tank(x=0.0, y=0.0, angle=0.0):
    """Create a bare Tank with a placeholder controller (replaced by AI)."""
    class _NullCtrl:
        def get_input(self):
            return TankInput()
    t = Tank(x=x, y=y, config={}, controller=_NullCtrl())
    t.angle = angle
    return t


def _make_controller(state: AIState, owner, target, accuracy=1.0):
    """Build an AIController, set its state, owner and target."""
    cfg = {"reaction_time": 0.0, "accuracy": accuracy,
           "aggression": 1.0, "evasion_threshold": 0.1}
    ctrl = AIController(config=cfg, target_getter=lambda: target)
    ctrl.set_owner(owner)
    # Force state directly (bypasses _update_state evaluation)
    ctrl._state = state
    return ctrl


# ---------------------------------------------------------------------------
# 5. AIController sets turret_angle in all four states
# ---------------------------------------------------------------------------

class TestAITurretAngle:
    def test_patrol_sets_turret_angle(self):
        """PATROL: get_input() must return a TankInput with turret_angle set."""
        owner = _make_ai_tank(x=0.0, y=0.0, angle=30.0)
        target = _make_ai_tank(x=500.0, y=0.0)
        ctrl = _make_controller(AIState.PATROL, owner, target)
        inp = ctrl._patrol_input()
        # turret_angle attribute must exist and be a float
        assert hasattr(inp, "turret_angle")
        assert isinstance(inp.turret_angle, float)

    def test_pursue_sets_turret_angle(self):
        owner = _make_ai_tank(x=0.0, y=0.0)
        target = _make_ai_tank(x=300.0, y=0.0)
        ctrl = _make_controller(AIState.PURSUE, owner, target)
        inp = ctrl._pursue_input(target)
        assert hasattr(inp, "turret_angle")
        assert isinstance(inp.turret_angle, float)

    def test_attack_sets_turret_angle(self):
        owner = _make_ai_tank(x=0.0, y=0.0)
        target = _make_ai_tank(x=150.0, y=0.0)
        ctrl = _make_controller(AIState.ATTACK, owner, target)
        inp = ctrl._attack_input(target)
        assert hasattr(inp, "turret_angle")
        assert isinstance(inp.turret_angle, float)

    def test_evade_sets_turret_angle(self):
        owner = _make_ai_tank(x=0.0, y=0.0)
        target = _make_ai_tank(x=200.0, y=0.0)
        ctrl = _make_controller(AIState.EVADE, owner, target)
        inp = ctrl._evade_input(target)
        assert hasattr(inp, "turret_angle")
        assert isinstance(inp.turret_angle, float)


# ---------------------------------------------------------------------------
# 6. PATROL state: turret_angle == owner.angle
# ---------------------------------------------------------------------------

class TestPatrolTurretAngle:
    def test_turret_tracks_hull_in_patrol(self):
        """In PATROL, the turret should face the same direction as the hull."""
        owner = _make_ai_tank(x=0.0, y=0.0, angle=45.0)
        ctrl = _make_controller(AIState.PATROL, owner, target=None)
        inp = ctrl._patrol_input()
        assert inp.turret_angle == pytest.approx(owner.angle)

    def test_turret_tracks_hull_at_zero(self):
        owner = _make_ai_tank(x=0.0, y=0.0, angle=0.0)
        ctrl = _make_controller(AIState.PATROL, owner, target=None)
        inp = ctrl._patrol_input()
        assert inp.turret_angle == pytest.approx(0.0)

    def test_turret_tracks_hull_at_180(self):
        owner = _make_ai_tank(x=0.0, y=0.0, angle=180.0)
        ctrl = _make_controller(AIState.PATROL, owner, target=None)
        inp = ctrl._patrol_input()
        assert inp.turret_angle == pytest.approx(180.0)


# ---------------------------------------------------------------------------
# 7. ATTACK state: turret_angle points toward target (within jitter tolerance)
# ---------------------------------------------------------------------------

class TestAttackTurretAngle:
    def test_turret_points_at_target_with_perfect_accuracy(self):
        """With accuracy=1.0 (jitter=0), turret_angle == exact bearing to target."""
        owner = _make_ai_tank(x=0.0, y=0.0)
        target = _make_ai_tank(x=100.0, y=0.0)   # exactly to the right → 0°
        ctrl = _make_controller(AIState.ATTACK, owner, target, accuracy=1.0)
        inp = ctrl._attack_input(target)
        # Expected: angle_to((0,0),(100,0)) = 0°; jitter = (1-1.0)*uniform = 0
        assert inp.turret_angle == pytest.approx(0.0, abs=0.01)

    def test_turret_points_roughly_at_target_with_low_accuracy(self):
        """With accuracy=0.5 (30° max jitter), angle should be within ±30° of exact."""
        owner = _make_ai_tank(x=0.0, y=0.0)
        target = _make_ai_tank(x=0.0, y=100.0)   # directly below → 90°
        ctrl = _make_controller(AIState.ATTACK, owner, target, accuracy=0.5)
        for _ in range(30):   # run multiple times to cover random jitter
            inp = ctrl._attack_input(target)
            diff = abs(inp.turret_angle - 90.0)
            # Wrap-around: allow ±30° from 90° (accounting for ±180° wrap)
            diff = min(diff, 360.0 - diff)
            assert diff <= 30.0 + 1e-6, f"turret_angle={inp.turret_angle} too far from 90°"

    def test_turret_angle_toward_target_not_away(self):
        """Turret should be in the correct hemisphere toward the target."""
        owner = _make_ai_tank(x=0.0, y=0.0)
        target = _make_ai_tank(x=0.0, y=-100.0)  # above → -90° (270°)
        ctrl = _make_controller(AIState.ATTACK, owner, target, accuracy=1.0)
        inp = ctrl._attack_input(target)
        # With accuracy=1.0, turret exactly on bearing.  atan2(-100,0) = -90° = 270°
        expected = angle_to((0.0, 0.0), (0.0, -100.0))
        assert inp.turret_angle == pytest.approx(expected, abs=0.01)
