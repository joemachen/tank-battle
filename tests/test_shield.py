"""
tests/test_shield.py

Unit tests for the shield pickup — damage absorption, expiry, and interaction.
"""

import pytest

from game.entities.pickup import Pickup
from game.entities.tank import Tank, TankInput


class _DummyController:
    def get_input(self) -> TankInput:
        return TankInput()


def _make_tank(hp: int = 100) -> Tank:
    config = {"speed": 150, "health": hp, "turn_rate": 120, "fire_rate": 1.0, "type": "test"}
    return Tank(400.0, 300.0, config, _DummyController())


class TestShield:
    def test_shield_applied_via_pickup(self):
        tank = _make_tank()
        pickup = Pickup(400, 300, "shield", 60.0)
        pickup.apply(tank)
        assert tank.has_status("shield")
        assert tank.shield_hp == 60.0

    def test_shield_absorbs_partial_damage(self):
        tank = _make_tank(100)
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        tank.take_damage(30)
        assert tank.shield_hp == 30.0
        assert tank.health == 100

    def test_shield_absorbs_all_then_remainder_hits_health(self):
        tank = _make_tank(100)
        tank.apply_status("shield", 0.0, 12.0, shield_hp=20.0)
        tank.take_damage(50)
        assert tank.shield_hp == 0.0
        assert not tank.has_status("shield")
        assert tank.health == 70

    def test_shield_breaks_on_exact_damage(self):
        tank = _make_tank(100)
        tank.apply_status("shield", 0.0, 12.0, shield_hp=40.0)
        tank.take_damage(40)
        assert not tank.has_status("shield")
        assert tank.health == 100

    def test_shield_expires_by_timer(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 2.0, shield_hp=60.0)
        tank.tick_status_effects(2.5)
        assert not tank.has_status("shield")
        assert tank.shield_hp == 0.0

    def test_shield_hp_property_zero_when_no_shield(self):
        tank = _make_tank()
        assert tank.shield_hp == 0.0

    def test_shield_does_not_prevent_death(self):
        tank = _make_tank(50)
        tank.apply_status("shield", 0.0, 12.0, shield_hp=10.0)
        tank.take_damage(80)
        # Shield absorbs 10, remaining 70 vs 50 hp → dead
        assert not tank.is_alive

    def test_multiple_damage_ticks_deplete_shield_then_health(self):
        tank = _make_tank(100)
        tank.apply_status("shield", 0.0, 12.0, shield_hp=30.0)
        tank.take_damage(20)
        assert tank.shield_hp == 10.0
        assert tank.health == 100
        tank.take_damage(20)
        assert not tank.has_status("shield")
        assert tank.health == 90

    def test_shield_refreshed_by_second_pickup(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        tank.take_damage(40)
        assert tank.shield_hp == 20.0
        # Second shield pickup refreshes
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        assert tank.shield_hp == 60.0

    def test_shield_coexists_with_regen(self):
        tank = _make_tank(80)
        tank.health = 60
        tank.apply_status("shield", 0.0, 10.0, shield_hp=40.0)
        tank.apply_status("regen", 5.0, 8.0)
        assert tank.has_status("shield")
        assert tank.has_status("regen")
        # Tick should heal and maintain shield
        tank.tick_status_effects(1.0)
        assert tank.has_status("shield")
        assert tank.health == 65  # 5 hp/s * 1s = 5 healed

    def test_shield_zero_damage_no_effect(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        tank.take_damage(0)
        assert tank.shield_hp == 60.0
        assert tank.health == 100

    def test_shield_survives_partial_timer(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 10.0, shield_hp=50.0)
        tank.tick_status_effects(5.0)
        assert tank.has_status("shield")
        assert tank.shield_hp == 50.0

    def test_shield_coexists_with_speed_boost(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, 10.0, shield_hp=40.0)
        tank.apply_status("speed_boost", 1.6, 8.0)
        assert tank.has_status("shield")
        assert tank.has_status("speed_boost")

    def test_dead_tank_ignores_shield_damage(self):
        tank = _make_tank(50)
        tank.is_alive = False
        tank.apply_status("shield", 0.0, 12.0, shield_hp=60.0)
        tank.take_damage(100)
        # take_damage returns early for dead tanks
        assert tank.shield_hp == 60.0

    def test_pickup_not_consumed_when_already_dead(self):
        tank = _make_tank()
        pickup = Pickup(400, 300, "shield", 60.0)
        pickup.is_alive = False
        pickup.apply(tank)
        assert not tank.has_status("shield")
