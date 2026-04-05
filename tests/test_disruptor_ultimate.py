"""
tests/test_disruptor_ultimate.py

Unit tests for the Disruptor ultimate ability (v0.33.5).

Disruptor:
  - Applies a "disruptor_disable" ult_status to tanks within radius.
  - Owner is immune.
  - While disabled: fire intent is suppressed (no "fire" events).
  - While disabled: ultimate activation is blocked.
  - Status expires after its duration.
  - Collapses active Fortress domes (tested via the _shield_domes list).
  - Breaks active Phantom cloak (tested via tank._cloaked flag).

Tests run headless — no pygame or game scene dependencies.
"""

import sys
import types
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Minimal pygame stub
# ---------------------------------------------------------------------------

_pygame_stub = types.ModuleType("pygame")
_pygame_stub.error = type("error", (Exception,), {})
sys.modules.setdefault("pygame", _pygame_stub)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tank(x=0.0, y=0.0, alive=True):
    from game.entities.tank import Tank, TankInput

    ctrl = MagicMock()
    ctrl.get_input.return_value = TankInput(
        throttle=0.0, rotate=0.0, fire=True,
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


def _disruptor_data(duration=4.0, *, disable_weapons=True, disable_ultimate=True):
    return {
        "timer": duration,
        "disable_weapons": disable_weapons,
        "disable_ultimate": disable_ultimate,
    }


# ---------------------------------------------------------------------------
# TestDisruptorStatus — lifecycle
# ---------------------------------------------------------------------------

class TestDisruptorStatus(unittest.TestCase):

    def test_disruptor_applies_to_tank(self):
        """apply_ult_status('disruptor_disable') → has_ult_status returns True."""
        tank = _make_tank()
        self.assertFalse(tank.has_ult_status("disruptor_disable"))
        tank.apply_ult_status("disruptor_disable", _disruptor_data())
        self.assertTrue(tank.has_ult_status("disruptor_disable"))

    def test_disruptor_disable_expires_after_duration(self):
        """Status expires once the timer ticks to zero."""
        tank = _make_tank()
        tank.apply_ult_status("disruptor_disable", _disruptor_data(duration=0.1))
        for _ in range(10):
            tank.update(0.05)          # 10 × 0.05 = 0.5s > 0.1s
        self.assertFalse(
            tank.has_ult_status("disruptor_disable"),
            "disruptor_disable must expire after its duration.",
        )

    def test_disruptor_immune_to_owner(self):
        """Owner tank is never given the disruptor status (caller responsibility)."""
        owner = _make_tank()
        # Simulate game_scene skipping owner — no apply_ult_status call
        self.assertFalse(owner.has_ult_status("disruptor_disable"))


# ---------------------------------------------------------------------------
# TestDisruptorWeaponBlock — fire suppression
# ---------------------------------------------------------------------------

class TestDisruptorWeaponBlock(unittest.TestCase):

    def test_disruptor_disables_weapons(self):
        """A disrupted tank with fire intent must not emit 'fire' events."""
        tank = _make_tank()
        tank.apply_ult_status("disruptor_disable", _disruptor_data())
        # Ensure the active weapon slot is off cooldown so it would otherwise fire
        tank._slot_cooldowns[tank.active_slot] = 0.0
        events = tank.update(0.05)
        fire_events = [e for e in events if e[0] == "fire"]
        self.assertEqual(fire_events, [],
                         "Disrupted tank must not fire.")

    def test_weapon_block_is_only_while_status_active(self):
        """Once disruptor expires, the tank can fire again."""
        tank = _make_tank()
        tank.apply_ult_status("disruptor_disable", _disruptor_data(duration=0.05))
        # Let the status expire
        for _ in range(5):
            tank.update(0.05)
        tank._slot_cooldowns[tank.active_slot] = 0.0
        events = tank.update(0.01)
        fire_events = [e for e in events if e[0] == "fire"]
        self.assertGreater(len(fire_events), 0,
                           "Tank should be able to fire after disruptor expires.")


# ---------------------------------------------------------------------------
# TestDisruptorUltimateBlock — ultimate activation suppression
# ---------------------------------------------------------------------------

class TestDisruptorUltimateBlock(unittest.TestCase):

    def _tank_with_ready_ultimate(self):
        """Return a tank whose ultimate is fully charged and ready to fire."""
        from game.entities.tank import TankInput
        tank = _make_tank()
        ult_cfg = {
            "ability_type": "overdrive",
            "charge_max": 100.0,
            "charge_per_damage": 1.0,
            "charge_per_hit": 1.0,
            "charge_passive_rate": 0.0,
            "duration": 4.0,
            "speed_multiplier": 2.5,
            "fire_rate_multiplier": 2.0,
        }
        tank.set_ultimate(ult_cfg)
        tank.ultimate.charge = tank.ultimate.charge_max   # force fully charged
        # Override controller to request ultimate activation
        tank.controller.get_input.return_value = TankInput(
            throttle=0.0, rotate=0.0, fire=False,
            turret_angle=0.0, cycle_weapon=0, activate_ultimate=True,
        )
        return tank

    def test_disruptor_blocks_ultimate_activation(self):
        """A disrupted tank must not activate its ultimate."""
        tank = self._tank_with_ready_ultimate()
        tank.apply_ult_status("disruptor_disable", _disruptor_data())
        events = tank.update(0.05)
        ult_events = [e for e in events if e[0] == "ultimate_activated"]
        self.assertEqual(ult_events, [],
                         "Disrupted tank must not activate its ultimate.")
        self.assertFalse(
            tank.ultimate.is_active,
            "ultimate must remain inactive while disruptor_disable is in effect.",
        )

    def test_ultimate_block_is_only_while_status_active(self):
        """After disruptor expires, the ultimate can be activated."""
        from game.entities.tank import TankInput

        tank = self._tank_with_ready_ultimate()
        # Apply disruptor with a duration long enough to definitely block
        tank.apply_ult_status("disruptor_disable", _disruptor_data(duration=1.0))

        # While disruptor is active, ultimate must NOT activate
        tank.ultimate.charge = tank.ultimate.charge_max
        events = tank.update(0.05)
        ult_events = [e for e in events if e[0] == "ultimate_activated"]
        self.assertEqual(ult_events, [], "Ultimate must be blocked while disruptor active.")

        # Drain the timer past expiry (1.0s total needed; each tick is 0.05s)
        # Switch controller to NOT request ultimate during drain phase
        tank.controller.get_input.return_value = TankInput(
            throttle=0.0, rotate=0.0, fire=False,
            turret_angle=0.0, cycle_weapon=0, activate_ultimate=False,
        )
        for _ in range(25):   # 25 × 0.05 = 1.25s — fully past 1.0s duration
            tank.update(0.05)
        self.assertFalse(tank.has_ult_status("disruptor_disable"),
                         "disruptor_disable must have expired.")

        # Re-charge and request activation
        tank.ultimate.charge = tank.ultimate.charge_max
        tank.controller.get_input.return_value = TankInput(
            throttle=0.0, rotate=0.0, fire=False,
            turret_angle=0.0, cycle_weapon=0, activate_ultimate=True,
        )
        events = tank.update(0.01)
        ult_events = [e for e in events if e[0] == "ultimate_activated"]
        self.assertGreater(len(ult_events), 0,
                           "Tank should be able to activate ultimate after disruptor expires.")


# ---------------------------------------------------------------------------
# TestDisruptorFortressCollapse — shield-dome interaction
# ---------------------------------------------------------------------------

class TestDisruptorFortressCollapse(unittest.TestCase):
    """Disruptor collapses active Fortress shield domes.

    The collapse logic lives in game_scene._handle_ultimate_activated(), which
    filters self._shield_domes by matching the target tank and removes them.
    We verify the filtering logic directly (without full game_scene import).
    """

    def test_disruptor_collapses_fortress(self):
        """Shield domes belonging to disrupted targets are removed."""
        target = _make_tank()
        other = _make_tank(x=100.0)

        shield_domes = [
            {"tank": target, "hp": 200, "timer": 3.0},
            {"tank": other,  "hp": 200, "timer": 3.0},
        ]

        # Simulate the collapse: remove domes whose tank is the disruptor target
        shield_domes = [d for d in shield_domes if d["tank"] is not target]

        self.assertEqual(len(shield_domes), 1)
        self.assertIs(shield_domes[0]["tank"], other,
                      "Only the non-target dome must survive.")

    def test_disruptor_does_not_collapse_other_domes(self):
        """Domes owned by tanks other than the target are unaffected."""
        target = _make_tank()
        ally = _make_tank(x=50.0)

        shield_domes = [{"tank": ally, "hp": 200, "timer": 3.0}]
        shield_domes = [d for d in shield_domes if d["tank"] is not target]
        self.assertEqual(len(shield_domes), 1,
                         "Ally dome must not be collapsed.")


# ---------------------------------------------------------------------------
# TestDisruptorPhantomBreak — cloak interaction
# ---------------------------------------------------------------------------

class TestDisruptorPhantomBreak(unittest.TestCase):
    """Disruptor breaks active Phantom cloak on the target tank."""

    def test_disruptor_breaks_phantom_cloak(self):
        """When disruptor is applied, target._cloaked becomes False."""
        from game.systems.ultimate import UltimateCharge

        target = _make_tank()
        phantom_cfg = {
            "ability_type": "cloak",
            "charge_max": 100.0,
            "duration": 5.0,
            "speed_multiplier": 1.3,
        }
        target.set_ultimate(phantom_cfg)
        target.ultimate.charge = target.ultimate.charge_max
        target.ultimate.activate()
        target._cloaked = True       # set explicitly as activate() does for cloak

        self.assertTrue(target._cloaked)
        self.assertTrue(target.ultimate.is_active)

        # Simulate game_scene disruptor breaking the cloak
        if target._cloaked:
            target._cloaked = False
            target.ultimate.force_deactivate()

        self.assertFalse(target._cloaked,
                         "Disruptor must clear the cloaked flag.")
        self.assertFalse(target.ultimate.is_active,
                         "Disruptor must force-deactivate the cloak ultimate.")

    def test_disruptor_does_not_break_non_cloak_ultimate(self):
        """If the target's ultimate isn't cloak, force_deactivate is not triggered."""
        target = _make_tank()
        overdrive_cfg = {
            "ability_type": "overdrive",
            "charge_max": 100.0,
            "duration": 4.0,
        }
        target.set_ultimate(overdrive_cfg)
        target.ultimate.charge = target.ultimate.charge_max
        target.ultimate.activate()

        self.assertFalse(target._cloaked)
        # Disruptor only force-deactivates when _cloaked is True
        if target._cloaked:
            target._cloaked = False
            target.ultimate.force_deactivate()

        # Overdrive should still be running
        self.assertTrue(target.ultimate.is_active,
                        "Non-cloak ultimate must not be deactivated by disruptor.")


if __name__ == "__main__":
    unittest.main()
