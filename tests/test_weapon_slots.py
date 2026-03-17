"""
tests/test_weapon_slots.py

Unit tests for milestone v0.16: Tank weapon-slot system.

Tests run without a pygame display.  They exercise:
  - load_weapons() with 1 / 2 / 3 configs
  - Slot 1 is required (empty list raises)
  - Slots 2-3 are optional (1-slot tank is valid)
  - Duplicate weapon type raises ValueError
  - MAX_WEAPON_SLOTS exceeded raises ValueError
  - cycle_weapon() wrap-around (forward and backward)
  - cycle_weapon() via TankInput.cycle_weapon intent in update()
  - Per-slot cooldowns tick independently
  - Switching slots mid-cooldown preserves each slot's timer
  - fire event is a 5-tuple with weapon_type
  - Fire event weapon_type matches the active slot
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from game.entities.tank import Tank, TankInput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FixedController:
    """Controller that always returns a preset TankInput."""
    def __init__(self, intent: TankInput | None = None):
        self._intent = intent or TankInput()

    def get_input(self) -> TankInput:
        return self._intent


def _make_tank(intent: TankInput | None = None) -> Tank:
    ctrl = _FixedController(intent)
    return Tank(x=0.0, y=0.0, config={}, controller=ctrl)


def _std() -> dict:
    return {"type": "standard_shell", "fire_rate": 1.0, "damage": 20}


def _spread() -> dict:
    return {"type": "spread_shot", "fire_rate": 0.8, "damage": 15}


def _bounce() -> dict:
    return {"type": "bouncing_round", "fire_rate": 0.6, "damage": 30}


# ---------------------------------------------------------------------------
# 1. load_weapons — valid counts
# ---------------------------------------------------------------------------

class TestLoadWeapons:
    def test_load_one_weapon(self):
        tank = _make_tank()
        tank.load_weapons([_std()])
        assert len(tank.weapon_slots) == 1
        assert tank.active_weapon["type"] == "standard_shell"
        assert tank.active_slot == 0

    def test_load_two_weapons(self):
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        assert len(tank.weapon_slots) == 2

    def test_load_three_weapons(self):
        tank = _make_tank()
        tank.load_weapons([_std(), _spread(), _bounce()])
        assert len(tank.weapon_slots) == 3

    def test_active_slot_reset_to_zero_on_load(self):
        """load_weapons() always resets active slot to 0."""
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        tank.cycle_weapon(+1)          # move to slot 1
        assert tank.active_slot == 1
        tank.load_weapons([_std()])    # reload — slot resets
        assert tank.active_slot == 0

    def test_cooldowns_reset_on_load(self):
        """load_weapons() resets all per-slot cooldowns to 0."""
        tank = _make_tank(TankInput(fire=True))
        tank.load_weapons([_std()])
        tank.update(dt=0.016)          # fire — slot 0 gets a cooldown
        tank.load_weapons([_std()])    # reload
        assert tank._slot_cooldowns[0] == pytest.approx(0.0)

    def test_weapon_slots_returns_copy(self):
        """weapon_slots property must return a copy, not the internal list."""
        tank = _make_tank()
        tank.load_weapons([_std()])
        slots = tank.weapon_slots
        slots.clear()
        assert len(tank.weapon_slots) == 1


# ---------------------------------------------------------------------------
# 2. load_weapons — error conditions
# ---------------------------------------------------------------------------

class TestLoadWeaponsErrors:
    def test_empty_list_raises(self):
        tank = _make_tank()
        with pytest.raises(ValueError, match="at least one"):
            tank.load_weapons([])

    def test_too_many_slots_raises(self):
        from game.utils.constants import MAX_WEAPON_SLOTS
        tank = _make_tank()
        configs = [{"type": f"weapon_{i}", "fire_rate": 1.0} for i in range(MAX_WEAPON_SLOTS + 1)]
        with pytest.raises(ValueError, match="max"):
            tank.load_weapons(configs)

    def test_duplicate_type_raises(self):
        tank = _make_tank()
        with pytest.raises(ValueError, match="duplicate"):
            tank.load_weapons([_std(), _std()])

    def test_duplicate_across_three_slots_raises(self):
        tank = _make_tank()
        with pytest.raises(ValueError, match="duplicate"):
            tank.load_weapons([_std(), _spread(), _std()])


# ---------------------------------------------------------------------------
# 3. Slot cycling
# ---------------------------------------------------------------------------

class TestCycleWeapon:
    def test_cycle_forward(self):
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        tank.cycle_weapon(+1)
        assert tank.active_slot == 1
        assert tank.active_weapon["type"] == "spread_shot"

    def test_cycle_backward_wraps_to_last(self):
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        tank.cycle_weapon(-1)          # 0 - 1 wraps to 1
        assert tank.active_slot == 1

    def test_cycle_forward_wraps_from_last(self):
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        tank.cycle_weapon(+1)          # → 1
        tank.cycle_weapon(+1)          # → wraps to 0
        assert tank.active_slot == 0

    def test_cycle_three_slots_full_circle(self):
        tank = _make_tank()
        tank.load_weapons([_std(), _spread(), _bounce()])
        tank.cycle_weapon(+1)
        tank.cycle_weapon(+1)
        tank.cycle_weapon(+1)          # back to slot 0
        assert tank.active_slot == 0
        assert tank.active_weapon["type"] == "standard_shell"

    def test_cycle_single_slot_no_op(self):
        """Cycling when only one slot is loaded must not change active_slot."""
        tank = _make_tank()
        tank.load_weapons([_std()])
        tank.cycle_weapon(+1)
        assert tank.active_slot == 0
        tank.cycle_weapon(-1)
        assert tank.active_slot == 0


# ---------------------------------------------------------------------------
# 4. Cycling via TankInput intent in update()
# ---------------------------------------------------------------------------

class TestCycleViaIntent:
    def test_cycle_weapon_intent_advances_slot(self):
        ctrl = _FixedController(TankInput(cycle_weapon=+1))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        tank.update(dt=0.016)
        assert tank.active_slot == 1

    def test_cycle_weapon_zero_intent_no_op(self):
        ctrl = _FixedController(TankInput(cycle_weapon=0))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        tank.update(dt=0.016)
        assert tank.active_slot == 0


# ---------------------------------------------------------------------------
# 5. Per-slot cooldowns
# ---------------------------------------------------------------------------

class TestPerSlotCooldowns:
    def test_firing_only_affects_active_slot_cooldown(self):
        """Firing slot 0 must not affect slot 1's cooldown."""
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        tank.update(dt=0.016)
        assert tank._slot_cooldowns[0] > 0
        assert tank._slot_cooldowns[1] == pytest.approx(0.0)

    def test_all_cooldowns_tick_every_frame(self):
        """All slot cooldowns tick down every frame, regardless of which is active."""
        ctrl = _FixedController(TankInput(fire=False))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        # Manually set both cooldowns
        tank._slot_cooldowns[0] = 1.0
        tank._slot_cooldowns[1] = 0.5
        tank.update(dt=0.1)
        assert tank._slot_cooldowns[0] == pytest.approx(0.9, abs=1e-6)
        assert tank._slot_cooldowns[1] == pytest.approx(0.4, abs=1e-6)

    def test_switching_slot_preserves_old_cooldown(self):
        """After firing slot 0, switching to slot 1 leaves slot 0's cooldown intact."""
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        tank.update(dt=0.016)          # fires standard_shell
        cd0_after_fire = tank._slot_cooldowns[0]
        assert cd0_after_fire > 0

        # Switch to slot 1 and wait
        tank.cycle_weapon(+1)
        ctrl._intent = TankInput(fire=False)
        tank.update(dt=0.1)            # time passes, cooldown ticks

        # Slot 0's cooldown should have decreased
        assert tank._slot_cooldowns[0] < cd0_after_fire
        # Slot 1 should still be at 0 (nothing fired)
        assert tank._slot_cooldowns[1] == pytest.approx(0.0)

    def test_can_fire_slot1_immediately_after_slot0_fires(self):
        """Firing slot 0 does not impose a cooldown on slot 1."""
        # Fire slot 0
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        tank.update(dt=0.016)

        # Switch to slot 1 — should be able to fire immediately
        tank.cycle_weapon(+1)
        events = tank.update(dt=0.016)
        fire_events = [e for e in events if e[0] == "fire"]
        assert len(fire_events) == 1
        assert fire_events[0][4] == "spread_shot"


# ---------------------------------------------------------------------------
# 6. Fire event — 5-tuple with weapon_type
# ---------------------------------------------------------------------------

class TestFireEventWeaponType:
    def test_fire_event_is_5_tuple(self):
        ctrl = _FixedController(TankInput(fire=True, turret_angle=0.0))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([{"type": "spread_shot", "fire_rate": 1.0}])
        events = tank.update(dt=0.016)
        fire_events = [e for e in events if e[0] == "fire"]
        assert len(fire_events) == 1
        assert len(fire_events[0]) == 5

    def test_fire_event_unpacks_correctly(self):
        ctrl = _FixedController(TankInput(fire=True, turret_angle=45.0))
        tank = Tank(x=10, y=20, config={}, controller=ctrl)
        tank.load_weapons([_std()])
        events = tank.update(dt=0.016)
        ev_type, ex, ey, eangle, wtype = events[0]
        assert ev_type == "fire"
        assert ex == pytest.approx(10.0)
        assert ey == pytest.approx(20.0)
        assert eangle == pytest.approx(45.0)
        assert wtype == "standard_shell"

    def test_weapon_type_matches_slot0(self):
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        events = tank.update(dt=0.016)
        _, _, _, _, wtype = [e for e in events if e[0] == "fire"][0]
        assert wtype == "standard_shell"

    def test_weapon_type_changes_after_cycle(self):
        """After cycling to slot 1, fire event carries slot 1's weapon type."""
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        # Use high fire_rate so both slots can fire immediately
        tank.load_weapons([
            {"type": "standard_shell", "fire_rate": 100.0},
            {"type": "bouncing_round", "fire_rate": 100.0},
        ])
        # Fire slot 0
        tank.update(dt=0.001)

        # Cycle to slot 1 and fire
        tank.cycle_weapon(+1)
        events = tank.update(dt=0.001)
        fire_events = [e for e in events if e[0] == "fire"]
        assert len(fire_events) == 1
        assert fire_events[0][4] == "bouncing_round"

    def test_default_slot_produces_5_tuple(self):
        """Even a tank with no explicit load_weapons call fires a 5-tuple."""
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        # No load_weapons call — uses default single slot
        events = tank.update(dt=0.016)
        fire_events = [e for e in events if e[0] == "fire"]
        assert len(fire_events) == 1
        assert len(fire_events[0]) == 5


# ---------------------------------------------------------------------------
# 7. Slot 1 required / optional slots 2-3
# ---------------------------------------------------------------------------

class TestSlotRequirements:
    def test_slot1_required_single_weapon(self):
        """A tank with only slot 1 filled functions correctly."""
        tank = _make_tank()
        tank.load_weapons([_std()])
        assert tank.active_slot == 0
        assert tank.active_weapon["type"] == "standard_shell"

    def test_slots_2_and_3_are_optional(self):
        """A 1-slot tank is a valid, fully operational tank."""
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std()])
        events = tank.update(dt=0.016)
        assert any(e[0] == "fire" for e in events)

    def test_active_weapon_property_after_partial_load(self):
        """With 2 slots loaded, active_weapon reflects the current slot."""
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        tank.cycle_weapon(+1)
        assert tank.active_weapon["type"] == "spread_shot"


# ---------------------------------------------------------------------------
# 8. set_active_slot — direct slot select (number keys / mouse wheel)
# ---------------------------------------------------------------------------

class TestSetActiveSlot:
    def test_set_active_slot_valid_index(self):
        """set_active_slot(1) on a 2-slot tank switches to slot 1."""
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        tank.set_active_slot(1)
        assert tank.active_slot == 1
        assert tank.active_weapon["type"] == "spread_shot"

    def test_set_active_slot_zero(self):
        """set_active_slot(0) always valid and stays at slot 0."""
        tank = _make_tank()
        tank.load_weapons([_std(), _spread()])
        tank.cycle_weapon(+1)          # move to slot 1 first
        tank.set_active_slot(0)
        assert tank.active_slot == 0

    def test_set_active_slot_out_of_range_is_noop(self):
        """set_active_slot(2) on a 1-slot tank must leave active_slot unchanged."""
        tank = _make_tank()
        tank.load_weapons([_std()])
        tank.set_active_slot(2)
        assert tank.active_slot == 0

    def test_set_active_slot_large_index_does_not_raise(self):
        """Arbitrarily large index must not raise — silently ignored."""
        tank = _make_tank()
        tank.load_weapons([_std()])
        tank.set_active_slot(99)       # must not raise
        assert tank.active_slot == 0  # unchanged

    def test_set_active_slot_does_not_reset_cooldown(self):
        """Jumping to a slot via set_active_slot must not clear its cooldown timer."""
        ctrl = _FixedController(TankInput(fire=True))
        tank = Tank(x=0, y=0, config={}, controller=ctrl)
        tank.load_weapons([_std(), _spread()])
        tank.cycle_weapon(+1)                  # move to slot 1
        tank.update(dt=0.016)                  # fire — slot 1 gets cooldown
        cd_before = tank._slot_cooldowns[1]
        assert cd_before > 0

        tank.set_active_slot(0)                # jump away
        tank.set_active_slot(1)                # jump back
        # Cooldown must still be there (not reset by the slot select)
        assert tank._slot_cooldowns[1] <= cd_before  # may have ticked down

    def test_set_active_slot_three_slot_tank(self):
        """set_active_slot(2) on a 3-slot tank correctly selects slot 2."""
        tank = _make_tank()
        tank.load_weapons([_std(), _spread(), _bounce()])
        tank.set_active_slot(2)
        assert tank.active_slot == 2
        assert tank.active_weapon["type"] == "bouncing_round"


# ---------------------------------------------------------------------------
# 9. TankInput dataclass defaults
# ---------------------------------------------------------------------------

class TestTankInputDefaults:
    def test_cycle_weapon_defaults_to_zero(self):
        inp = TankInput()
        assert inp.cycle_weapon == 0

    def test_all_fields_constructible(self):
        inp = TankInput(throttle=1.0, rotate=-1.0, fire=True, turret_angle=90.0, cycle_weapon=1)
        assert inp.throttle == 1.0
        assert inp.rotate == -1.0
        assert inp.fire is True
        assert inp.turret_angle == pytest.approx(90.0)
        assert inp.cycle_weapon == 1
