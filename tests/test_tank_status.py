"""
tests/test_tank_status.py

Unit tests for Tank status effects — apply, tick, expire, speed boost (v0.19).
Passive regen + health float accumulator tests (v0.26).
"""

import pytest

from game.entities.tank import Tank
from game.systems.status_effect import StatusEffect
from game.utils.constants import DEFAULT_TANK_SPEED, TANK_STAT_MAX


class _StubController:
    """Minimal controller stub for Tank."""

    class _Intent:
        throttle = 0.0
        rotate = 0.0
        fire = False
        turret_angle = 0.0
        cycle_weapon = 0
        switch_slot = -1

    def get_input(self):
        return self._Intent()


def _make_tank(**overrides):
    config = {
        "type": "light_tank",
        "hp": 100,
        "speed": DEFAULT_TANK_SPEED,
        "turn_rate": 180,
        "fire_rate": 2.0,
    }
    config.update(overrides)
    return Tank(x=400, y=300, config=config, controller=_StubController())


class TestApplyStatus:
    def test_stores_effect(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        assert tank.has_status("speed_boost")
        assert tank._status_effects["speed_boost"]["value"] == 1.6
        assert tank._status_effects["speed_boost"]["timer"] == 5.0

    def test_overwrite_existing(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        tank.apply_status("speed_boost", 2.0, 10.0)
        assert tank._status_effects["speed_boost"]["value"] == 2.0
        assert tank._status_effects["speed_boost"]["timer"] == 10.0


class TestTickStatusEffects:
    def test_decrements_timer(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        tank.tick_status_effects(1.0)
        assert abs(tank._status_effects["speed_boost"]["timer"] - 4.0) < 1e-9

    def test_removes_expired(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 1.0)
        tank.tick_status_effects(1.5)
        assert not tank.has_status("speed_boost")


class TestHasStatus:
    def test_true_when_active(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 5.0)
        assert tank.has_status("speed_boost") is True

    def test_false_when_absent(self):
        tank = _make_tank()
        assert tank.has_status("speed_boost") is False

    def test_false_after_expire(self):
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 0.5)
        tank.tick_status_effects(1.0)
        assert tank.has_status("speed_boost") is False


class TestSpeedBoostInUpdate:
    def test_speed_boost_increases_movement(self):
        """A tank with speed_boost should move faster than one without."""
        tank_normal = _make_tank()
        tank_boosted = _make_tank()
        tank_boosted.apply_status("speed_boost", 1.6, 5.0)

        # Give both tanks forward throttle
        class _ForwardController:
            class _Intent:
                throttle = 1.0
                rotate = 0.0
                fire = False
                turret_angle = 0.0
                cycle_weapon = 0
                switch_slot = -1

            def get_input(self):
                return self._Intent()

        tank_normal.controller = _ForwardController()
        tank_boosted.controller = _ForwardController()

        # Store initial positions
        x_normal_start = tank_normal.x
        x_boosted_start = tank_boosted.x

        tank_normal.update(1.0)
        tank_boosted.update(1.0)

        dx_normal = abs(tank_normal.x - x_normal_start) + abs(tank_normal.y - 300)
        dx_boosted = abs(tank_boosted.x - x_boosted_start) + abs(tank_boosted.y - 300)

        # Boosted tank should move further (1.6x)
        assert dx_boosted > dx_normal

    def test_tick_called_in_update(self):
        """update() should tick status effects — timer should decrease."""
        tank = _make_tank()
        tank.apply_status("speed_boost", 1.6, 2.0)
        tank.update(1.0)
        assert abs(tank._status_effects["speed_boost"]["timer"] - 1.0) < 0.1


class TestRegenStatus:
    def test_regen_heals_over_time(self):
        """Regen status should increase HP across multiple ticks."""
        tank = _make_tank(hp=100)
        tank.health = 60
        # 40 HP over 8 seconds = 5 HP/s
        tank.apply_status("regen", 5.0, 8.0)
        # Tick 20 frames at 0.1s each = 2 seconds → expect ~10 HP healed
        for _ in range(20):
            tank.tick_status_effects(0.1)
        assert tank.health >= 69  # 60 + ~10, conservative bound

    def test_regen_does_not_exceed_max_health(self):
        """Regen should cap healing at max_health."""
        tank = _make_tank(hp=100)
        tank.health = 95
        tank.apply_status("regen", 10.0, 8.0)
        for _ in range(50):
            tank.tick_status_effects(0.1)
        assert tank.health == 100

    def test_regen_expires(self):
        """Regen status should be removed after its timer expires."""
        tank = _make_tank(hp=100)
        tank.health = 60
        tank.apply_status("regen", 5.0, 2.0)
        tank.tick_status_effects(3.0)
        assert not tank.has_status("regen")

    def test_regen_accumulates_fractional_hp(self):
        """Small per-frame heals should accumulate via the _accum float."""
        tank = _make_tank(hp=100)
        tank.health = 50
        # 1 HP/s at small dt means each tick heals 0.016 HP — needs accumulation
        tank.apply_status("regen", 1.0, 10.0)
        for _ in range(60):
            tank.tick_status_effects(1 / 60)
        # After 1 second at 1 HP/s → expect ~1 HP healed
        assert tank.health >= 51


# -----------------------------------------------------------------------
# Health float accumulator (v0.26)
# -----------------------------------------------------------------------

class TestHealthFloatAccumulator:
    """health property returns int; _health_float stores float."""

    def test_health_returns_int(self):
        tank = _make_tank(health=100)
        assert isinstance(tank.health, int)

    def test_health_float_stores_float(self):
        tank = _make_tank(health=100)
        assert isinstance(tank._health_float, float)

    def test_health_setter_updates_float(self):
        tank = _make_tank(health=100)
        tank.health = 75
        assert tank._health_float == 75.0
        assert tank.health == 75

    def test_health_truncates_to_int(self):
        tank = _make_tank(health=100)
        tank._health_float = 99.7
        assert tank.health == 99

    def test_tank_stat_max_health(self):
        assert TANK_STAT_MAX["health"] == 440.0


# -----------------------------------------------------------------------
# Passive HP regen (v0.26)
# -----------------------------------------------------------------------

class TestPassiveRegen:
    """Passive regen heals every frame via float accumulator, suppressed by DoT."""

    def test_regen_heals_over_time(self):
        tank = _make_tank(health=200, regen_rate=5.0)
        tank.health = 150
        # Simulate 2 seconds at 60fps
        for _ in range(120):
            tank.update(1 / 60)
        # 5 HP/s * 2s = 10 HP → health should be ~160
        assert tank.health >= 159
        assert tank.health <= 161

    def test_regen_does_not_exceed_max(self):
        tank = _make_tank(health=100, regen_rate=50.0)
        tank.health = 95
        # Large regen over 1 second should cap at max
        for _ in range(60):
            tank.update(1 / 60)
        assert tank.health == 100

    def test_regen_suppressed_by_fire_dot(self):
        tank = _make_tank(health=200, regen_rate=10.0)
        tank.health = 150
        # Apply fire effect (tick_damage > 0)
        fire_cfg = {
            "duration": 5.0, "tick_interval": 0.5, "tick_damage": 8,
            "speed_mult": 1.0, "turn_mult": 1.0, "fire_rate_mult": 1.0,
            "color": [255, 80, 20],
        }
        tank.apply_combat_effect("fire", fire_cfg)
        hp_before = tank.health
        # Regen should NOT run — DoT is active
        # Run for 1.5s so fire ticks at least twice (tick_interval=0.5)
        for _ in range(90):
            tank.update(1 / 60)
        # Health should be LOWER (DoT damage), not higher (regen)
        assert tank.health < hp_before

    def test_regen_suppressed_by_poison_dot(self):
        tank = _make_tank(health=200, regen_rate=10.0)
        tank.health = 150
        poison_cfg = {
            "duration": 6.0, "tick_interval": 1.0, "tick_damage": 5,
            "speed_mult": 1.0, "turn_mult": 1.0, "fire_rate_mult": 1.0,
            "color": [80, 220, 80],
        }
        tank.apply_combat_effect("poison", poison_cfg)
        hp_before = tank.health
        for _ in range(30):
            tank.update(1 / 60)
        assert tank.health <= hp_before

    def test_regen_not_suppressed_by_ice(self):
        """ICE has tick_damage=0, so regen should still work."""
        tank = _make_tank(health=200, regen_rate=10.0)
        tank.health = 150
        ice_cfg = {
            "duration": 4.0, "tick_interval": 0, "tick_damage": 0,
            "speed_mult": 0.4, "turn_mult": 0.5, "fire_rate_mult": 1.0,
            "color": [100, 200, 255],
        }
        tank.apply_combat_effect("ice", ice_cfg)
        for _ in range(60):
            tank.update(1 / 60)
        # 10 HP/s * 1s = 10 HP → should have healed despite ice
        assert tank.health >= 159

    def test_regen_resumes_after_dot_expires(self):
        tank = _make_tank(health=300, regen_rate=10.0)
        tank.health = 200
        fire_cfg = {
            "duration": 0.5, "tick_interval": 0.5, "tick_damage": 8,
            "speed_mult": 1.0, "turn_mult": 1.0, "fire_rate_mult": 1.0,
            "color": [255, 80, 20],
        }
        tank.apply_combat_effect("fire", fire_cfg)
        # Run for 1 second — fire expires at 0.5s, regen kicks in for remaining 0.5s
        for _ in range(60):
            tank.update(1 / 60)
        hp_after = tank.health
        # Continue for another 2 seconds — regen should be active
        for _ in range(120):
            tank.update(1 / 60)
        assert tank.health > hp_after

    def test_zero_regen_rate_no_healing(self):
        tank = _make_tank(health=100, regen_rate=0.0)
        tank.health = 50
        for _ in range(60):
            tank.update(1 / 60)
        assert tank.health == 50

    def test_regen_fractional_accumulation(self):
        """2.5 HP/s at 60fps = 0.0417 HP/frame — must accumulate via float."""
        tank = _make_tank(health=200, regen_rate=2.5)
        tank.health = 100
        # Run for 4 seconds → expect ~10 HP healed
        for _ in range(240):
            tank.update(1 / 60)
        assert tank.health >= 109
        assert tank.health <= 111


# -----------------------------------------------------------------------
# Laser beam state clearing (v0.26)
# -----------------------------------------------------------------------

class TestBeamStateClearing:
    """is_firing_beam must be cleared on death and stun."""

    def test_beam_cleared_on_death(self):
        tank = _make_tank(health=100)
        # Simulate mid-beam state
        tank._is_firing_beam = True
        tank.is_alive = False
        tank.update(1 / 60)
        assert tank.is_firing_beam is False

    def test_beam_cleared_on_stun(self):
        tank = _make_tank(health=100)
        tank._is_firing_beam = True
        tank.apply_stun(2.0)
        tank.update(1 / 60)
        assert tank.is_firing_beam is False
