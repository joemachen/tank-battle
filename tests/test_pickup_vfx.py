"""
tests/test_pickup_vfx.py

Unit tests verifying pickup VFX-related state:
  - Shield has correct status data for VFX rendering
  - Per-type SFX lookup resolves correctly
  - Pickup initials include shield
"""

import pytest

from game.entities.pickup import Pickup
from game.entities.tank import Tank, TankInput
from game.utils.constants import (
    PICKUP_COLLECT_SFX,
    SFX_PICKUP_HEALTH,
    SFX_PICKUP_SHIELD,
    SFX_PICKUP_SPEED,
    SFX_PICKUP_RELOAD,
    VFX_SHIELD_COLOR,
    VFX_REGEN_COLOR,
)


class _DummyController:
    def get_input(self) -> TankInput:
        return TankInput()


def _make_tank() -> Tank:
    config = {"speed": 150, "health": 100, "turn_rate": 120, "fire_rate": 1.0, "type": "test"}
    return Tank(400.0, 300.0, config, _DummyController())


class TestPickupVFX:
    def test_shield_status_has_shield_hp_key(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        data = tank.status_effects.get("shield")
        assert data is not None
        assert "shield_hp" in data
        assert data["shield_hp"] == 60.0

    def test_per_type_sfx_lookup_all_types(self):
        assert PICKUP_COLLECT_SFX["health"] == SFX_PICKUP_HEALTH
        assert PICKUP_COLLECT_SFX["speed_boost"] == SFX_PICKUP_SPEED
        assert PICKUP_COLLECT_SFX["rapid_reload"] == SFX_PICKUP_RELOAD
        assert PICKUP_COLLECT_SFX["shield"] == SFX_PICKUP_SHIELD

    def test_vfx_colors_are_rgb_tuples(self):
        for color in (VFX_SHIELD_COLOR, VFX_REGEN_COLOR):
            assert isinstance(color, tuple)
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)

    def test_shield_pickup_sets_status_for_vfx(self):
        tank = _make_tank()
        pickup = Pickup(400, 300, "shield", 60.0)
        pickup.apply(tank)
        assert tank.has_status("shield")
        assert "shield_hp" in tank.status_effects["shield"]

    def test_shield_timer_field_present(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        data = tank.status_effects["shield"]
        assert "timer" in data
        assert data["timer"] == 12.0

    def test_pickup_collect_sfx_has_all_four_types(self):
        assert len(PICKUP_COLLECT_SFX) == 4
        for key in ("health", "rapid_reload", "speed_boost", "shield"):
            assert key in PICKUP_COLLECT_SFX

    def test_regen_status_has_value_for_vfx_check(self):
        tank = _make_tank()
        tank.apply_status("regen", 5.0, 8.0)
        assert tank.has_status("regen")
        assert tank.status_effects["regen"]["value"] == 5.0

    def test_speed_boost_status_has_value(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 8.0)
        assert tank.has_status("speed_boost")
        assert tank.status_effects["speed_boost"]["value"] == 1.6

    def test_shield_hp_decreases_after_damage_for_vfx(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        tank.take_damage(25)
        assert tank.shield_hp == 35.0
