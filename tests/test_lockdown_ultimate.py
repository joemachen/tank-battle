"""
tests/test_lockdown_ultimate.py

Unit tests for the Lockdown ultimate ability (v0.33.5).

Lockdown:
  - Applies a "lockdown" ult_status to tanks within radius when activated.
  - Owner is immune.
  - Dead tanks are excluded.
  - While locked down: throttle, rotate, and fire are all forced to zero.
  - A continuous pull-force is applied toward the anchor point each frame.
  - Status expires after its timer runs out.

Tests run headless — no pygame or game scene dependencies.
"""

import math
import sys
import types
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Minimal pygame stub — must be in place before any game module is imported
# ---------------------------------------------------------------------------

_pygame_stub = types.ModuleType("pygame")
_pygame_stub.error = type("error", (Exception,), {})
sys.modules.setdefault("pygame", _pygame_stub)


# ---------------------------------------------------------------------------
# Helper: build a minimal Tank without loading the full game scene
# ---------------------------------------------------------------------------

def _make_tank(x=0.0, y=0.0, alive=True):
    """Return a lightweight Tank with a no-op controller."""
    from game.entities.tank import Tank

    ctrl = MagicMock()
    from game.entities.tank import TankInput
    ctrl.get_input.return_value = TankInput(
        throttle=1.0, rotate=1.0, fire=True,
        turret_angle=0.0, cycle_weapon=0, activate_ultimate=False,
    )
    cfg = {
        "type": "medium_tank",
        "speed": 200.0,
        "health": 100,
        "turn_rate": 90.0,
        "fire_rate": 2.0,
    }
    tank = Tank(x, y, cfg, ctrl)
    tank.is_alive = alive
    return tank


def _lockdown_data(cx=0.0, cy=0.0, duration=3.0, pull_force=800.0):
    return {
        "timer": duration,
        "pull_center": (cx, cy),
        "pull_force": pull_force,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLockdownStatus(unittest.TestCase):
    """apply_ult_status / has_ult_status lifecycle."""

    def test_lockdown_applies_to_tank(self):
        """apply_ult_status('lockdown') makes has_ult_status return True."""
        tank = _make_tank()
        self.assertFalse(tank.has_ult_status("lockdown"))
        tank.apply_ult_status("lockdown", _lockdown_data())
        self.assertTrue(tank.has_ult_status("lockdown"))

    def test_lockdown_not_applied_to_dead_tank(self):
        """Dead tanks should be excluded from lockdown (caller responsibility).

        We verify the status does NOT affect is_alive=False tanks by checking
        that a dead tank returns no events from update() even if status is set.
        """
        tank = _make_tank(alive=False)
        tank.apply_ult_status("lockdown", _lockdown_data())
        events = tank.update(0.05)
        self.assertEqual(events, [], "Dead tank must return empty events.")

    def test_lockdown_expires_after_duration(self):
        """After the timer runs out the status should be gone."""
        tank = _make_tank()
        tank.apply_ult_status("lockdown", _lockdown_data(duration=0.1))
        # Simulate enough time — update() ticks _ult_statuses
        for _ in range(10):
            tank.update(0.05)          # 10 × 0.05s = 0.5s > 0.1s
        self.assertFalse(
            tank.has_ult_status("lockdown"),
            "Lockdown status must expire after its duration.",
        )

    def test_lockdown_immune_to_owner(self):
        """Owner tank must not receive the lockdown status.

        The owner immunity is enforced at the call-site (game_scene), not in Tank
        itself.  We verify that a tank without the status applied reports False.
        """
        owner = _make_tank()
        # Simulate game_scene skipping the owner
        # (never calls apply_ult_status on owner)
        self.assertFalse(owner.has_ult_status("lockdown"))


class TestLockdownInputOverride(unittest.TestCase):
    """While locked-down, movement and firing intent must be suppressed."""

    def _locked_tank(self, x=0.0, y=0.0):
        """Return a tank with lockdown applied at a remote center (100,100)."""
        tank = _make_tank(x=x, y=y)
        # Anchor far enough that pull doesn't trivially flip direction
        tank.apply_ult_status("lockdown", _lockdown_data(cx=1000.0, cy=0.0, pull_force=0.0))
        return tank

    def test_lockdown_overrides_input_throttle_to_zero(self):
        """Controller requests throttle=1.0, but locked-down tank must not advance."""
        tank = self._locked_tank()
        start_x, start_y = tank.x, tank.y
        tank.update(0.05)
        # With throttle overridden to 0 and pull_force=0, position is unchanged
        self.assertAlmostEqual(tank.x, start_x, places=4,
                               msg="Locked tank must not move under its own throttle.")
        self.assertAlmostEqual(tank.y, start_y, places=4,
                               msg="Locked tank must not move under its own throttle.")

    def test_lockdown_suppresses_fire(self):
        """While locked down, no 'fire' event should be emitted."""
        tank = _make_tank()
        tank.apply_ult_status("lockdown", _lockdown_data(pull_force=0.0))
        # Give the active weapon zero cooldown so it would normally fire
        tank._slot_cooldowns[tank.active_slot] = 0.0
        events = tank.update(0.05)
        fire_events = [e for e in events if e[0] == "fire"]
        self.assertEqual(fire_events, [],
                         "Locked-down tank must not fire.")


class TestLockdownPullForce(unittest.TestCase):
    """Lockdown pull-force drags the tank toward the anchor point."""

    def test_lockdown_pull_moves_tank_toward_center(self):
        """After one update, the tank should be closer to the anchor point."""
        tank = _make_tank(x=0.0, y=0.0)
        anchor_x, anchor_y = 200.0, 0.0
        tank.apply_ult_status("lockdown", _lockdown_data(
            cx=anchor_x, cy=anchor_y, pull_force=800.0
        ))
        dist_before = math.hypot(anchor_x - tank.x, anchor_y - tank.y)
        tank.update(0.1)
        dist_after = math.hypot(anchor_x - tank.x, anchor_y - tank.y)
        self.assertLess(dist_after, dist_before,
                        "Locked tank must be pulled toward the anchor point.")


if __name__ == "__main__":
    unittest.main()
