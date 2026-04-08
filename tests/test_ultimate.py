"""
tests/test_ultimate.py

Comprehensive tests for the v0.28 Ultimate System:
  - UltimateCharge data class
  - Tank integration (fields, events, cloak, speed/fire mods)
  - InputHandler ultimate key
  - AI ultimate activation + cloak detection
  - Bullet homing exclusion for cloaked tanks
  - Config loading
"""

import math
import pytest
from unittest.mock import MagicMock, patch

from game.systems.ultimate import UltimateCharge
from game.entities.tank import Tank, TankInput
from game.utils.config_loader import load_yaml
from game.utils.constants import ULTIMATES_CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _speed_burst_config() -> dict:
    return {
        "charge_max": 100.0,
        "charge_per_damage": 0.8,
        "charge_per_hit": 0.5,
        "charge_passive_rate": 2.0,
        "ability_type": "speed_burst",
        "duration": 4.0,
        "speed_multiplier": 2.5,
        "fire_rate_multiplier": 2.0,
        "color": [255, 200, 60],
        "sfx_key": "ult_speed_burst",
    }


def _cloak_config() -> dict:
    return {
        "charge_max": 100.0,
        "charge_per_damage": 0.9,
        "charge_per_hit": 0.6,
        "charge_passive_rate": 2.2,
        "ability_type": "cloak",
        "duration": 5.0,
        "speed_multiplier": 1.3,
        "color": [160, 100, 220],
        "sfx_key": "ult_cloak",
    }


def _artillery_config() -> dict:
    return {
        "charge_max": 100.0,
        "charge_per_damage": 0.7,
        "charge_per_hit": 0.4,
        "charge_passive_rate": 1.5,
        "ability_type": "artillery_strike",
        "duration": 0,
        "explosion_count": 5,
        "explosion_radius": 80.0,
        "explosion_damage": 80,
        "strike_area": 250.0,
        "stagger_delay": 0.3,
        "color": [255, 80, 40],
        "sfx_key": "ult_artillery",
    }


def _shield_dome_config() -> dict:
    return {
        "charge_max": 100.0,
        "charge_per_damage": 0.6,
        "charge_per_hit": 0.7,
        "charge_passive_rate": 1.8,
        "ability_type": "shield_dome",
        "duration": 5.0,
        "dome_radius": 120.0,
        "dome_hp": 200.0,
        "color": [100, 180, 255],
        "sfx_key": "ult_shield_dome",
    }


def _make_tank(tank_type="light_tank", ultimate_config=None):
    """Create a tank with a stub controller and optional ultimate."""
    from game.utils.config_loader import get_tank_config
    from game.utils.constants import TANKS_CONFIG
    config = get_tank_config(tank_type, TANKS_CONFIG)

    class StubController:
        def __init__(self):
            self.intent = TankInput()
        def get_input(self):
            return self.intent

    ctrl = StubController()
    tank = Tank(x=400.0, y=300.0, config=config, controller=ctrl)
    if ultimate_config:
        tank.ultimate = UltimateCharge(ultimate_config)
    return tank, ctrl


# ===========================================================================
# TestUltimateCharge — pure data class tests
# ===========================================================================

class TestUltimateChargeInit:
    def test_defaults(self):
        uc = UltimateCharge(_speed_burst_config())
        assert uc.charge == 0.0
        assert uc.charge_max == 100.0
        assert uc.is_active is False
        assert uc.is_ready is False
        assert uc.charge_ratio == 0.0
        assert uc.active_remaining == 0.0

    def test_config_stored(self):
        cfg = _speed_burst_config()
        uc = UltimateCharge(cfg)
        assert uc.ability_type == "speed_burst"
        assert uc.duration == 4.0
        assert uc.config is cfg


class TestUltimateChargeDamageCharge:
    def test_add_damage_charge(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.add_damage_charge(50.0)  # 50 * 0.8 = 40
        assert uc.charge == pytest.approx(40.0)

    def test_add_hit_charge(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.add_hit_charge(60.0)  # 60 * 0.5 = 30
        assert uc.charge == pytest.approx(30.0)

    def test_charge_capped_at_max(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.add_damage_charge(9999.0)
        assert uc.charge == 100.0

    def test_passive_tick(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.tick_passive(10.0)  # 10s * 2.0/s = 20
        assert uc.charge == pytest.approx(20.0)

    def test_passive_capped(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.tick_passive(999.0)
        assert uc.charge == 100.0

    def test_no_charge_while_active(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 100.0
        uc.activate()
        uc.add_damage_charge(50.0)
        uc.add_hit_charge(50.0)
        uc.tick_passive(5.0)
        assert uc.charge == 0.0  # stays at 0 while active


class TestUltimateChargeActivation:
    def test_activate_when_ready(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 100.0
        assert uc.is_ready is True
        result = uc.activate()
        assert result is True
        assert uc.is_active is True
        assert uc.charge == 0.0

    def test_activate_fails_when_not_ready(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 50.0
        result = uc.activate()
        assert result is False
        assert uc.is_active is False
        assert uc.charge == 50.0

    def test_activate_fails_while_active(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 100.0
        uc.activate()
        uc.charge = 100.0  # cheat charge back
        result = uc.activate()
        assert result is False  # can't reactivate

    def test_update_ticks_timer(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 100.0
        uc.activate()
        expired = uc.update(1.0)
        assert expired is False
        assert uc.active_remaining == pytest.approx(3.0)

    def test_update_expires(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 100.0
        uc.activate()
        expired = uc.update(5.0)
        assert expired is True
        assert uc.is_active is False

    def test_instant_ability_expires_immediately(self):
        uc = UltimateCharge(_artillery_config())
        uc.charge = 100.0
        uc.activate()
        expired = uc.update(0.016)
        assert expired is True

    def test_force_deactivate(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 100.0
        uc.activate()
        uc.force_deactivate()
        assert uc.is_active is False

    def test_update_noop_when_inactive(self):
        uc = UltimateCharge(_speed_burst_config())
        expired = uc.update(1.0)
        assert expired is False


class TestUltimateChargeProperties:
    def test_charge_ratio_zero(self):
        uc = UltimateCharge(_speed_burst_config())
        assert uc.charge_ratio == 0.0

    def test_charge_ratio_half(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 50.0
        assert uc.charge_ratio == pytest.approx(0.5)

    def test_charge_ratio_full(self):
        uc = UltimateCharge(_speed_burst_config())
        uc.charge = 100.0
        assert uc.charge_ratio == pytest.approx(1.0)

    def test_charge_ratio_zero_max(self):
        uc = UltimateCharge({"charge_max": 0})
        assert uc.charge_ratio == 0.0


# ===========================================================================
# TestTankUltimateIntegration
# ===========================================================================

class TestTankUltimateFields:
    def test_tank_starts_without_ultimate(self):
        tank, _ = _make_tank()
        assert tank.ultimate is None
        assert tank._cloaked is False

    def test_tank_with_ultimate(self):
        tank, _ = _make_tank(ultimate_config=_speed_burst_config())
        assert tank.ultimate is not None
        assert tank.ultimate.ability_type == "speed_burst"


class TestTankUltimatePassiveCharge:
    def test_passive_charge_during_update(self):
        tank, ctrl = _make_tank(ultimate_config=_speed_burst_config())
        tank.update(1.0)  # 1s → 2.0 passive charge
        assert tank.ultimate.charge == pytest.approx(2.0)

    def test_no_passive_charge_while_dead(self):
        tank, ctrl = _make_tank(ultimate_config=_speed_burst_config())
        tank.is_alive = False
        tank.update(1.0)
        assert tank.ultimate.charge == 0.0


class TestTankUltimateActivation:
    def test_activation_event(self):
        tank, ctrl = _make_tank(ultimate_config=_speed_burst_config())
        tank.ultimate.charge = 100.0
        ctrl.intent = TankInput(activate_ultimate=True)
        events = tank.update(0.016)
        ult_events = [e for e in events if e[0] == "ultimate_activated"]
        assert len(ult_events) == 1
        assert ult_events[0][1] is tank
        assert ult_events[0][2] == "speed_burst"

    def test_cloak_sets_cloaked_flag(self):
        tank, ctrl = _make_tank(
            tank_type="scout_tank",
            ultimate_config=_cloak_config(),
        )
        tank.ultimate.charge = 100.0
        ctrl.intent = TankInput(activate_ultimate=True)
        tank.update(0.016)
        assert tank._cloaked is True

    def test_cloak_break_on_fire(self):
        tank, ctrl = _make_tank(
            tank_type="scout_tank",
            ultimate_config=_cloak_config(),
        )
        tank.ultimate.charge = 100.0
        ctrl.intent = TankInput(activate_ultimate=True)
        tank.update(0.016)
        assert tank._cloaked is True
        # Now fire
        ctrl.intent = TankInput(fire=True)
        events = tank.update(0.016)
        cloak_breaks = [e for e in events if e[0] == "cloak_break"]
        assert len(cloak_breaks) == 1
        assert tank._cloaked is False
        assert tank.ultimate.is_active is False

    def test_cloak_clears_on_death(self):
        tank, ctrl = _make_tank(
            tank_type="scout_tank",
            ultimate_config=_cloak_config(),
        )
        tank.ultimate.charge = 100.0
        ctrl.intent = TankInput(activate_ultimate=True)
        tank.update(0.016)
        assert tank._cloaked is True
        tank.is_alive = False
        tank.update(0.016)
        assert tank._cloaked is False


class TestTankUltimateExpiry:
    def test_expiry_event(self):
        tank, ctrl = _make_tank(ultimate_config=_speed_burst_config())
        tank.ultimate.charge = 100.0
        ctrl.intent = TankInput(activate_ultimate=True)
        tank.update(0.016)  # activate
        ctrl.intent = TankInput()
        events = tank.update(5.0)  # expire (4s duration)
        expire_events = [e for e in events if e[0] == "ultimate_expired"]
        assert len(expire_events) == 1


class TestTankUltimateSpeedMod:
    def test_speed_multiplier_applied(self):
        tank, ctrl = _make_tank(ultimate_config=_speed_burst_config())
        base_speed = tank.speed
        # Activate ultimate
        tank.ultimate.charge = 100.0
        ctrl.intent = TankInput(activate_ultimate=True, throttle=1.0)
        events = tank.update(0.016)
        x_after_activate = tank.x
        # Move with ultimate active
        ctrl.intent = TankInput(throttle=1.0)
        tank.update(1.0)
        dist_with_ult = tank.x - x_after_activate
        # Reset and move without ultimate
        tank2, ctrl2 = _make_tank()
        ctrl2.intent = TankInput(throttle=1.0)
        x_before = tank2.x
        tank2.update(1.0)
        dist_without_ult = tank2.x - x_before
        # With ult should be ~2.5x faster
        assert dist_with_ult > dist_without_ult * 2.0


class TestTankUltimateHitCharge:
    def test_take_damage_charges_ultimate(self):
        tank, ctrl = _make_tank(ultimate_config=_speed_burst_config())
        tank.take_damage(40)  # 40 * 0.5 = 20
        assert tank.ultimate.charge == pytest.approx(20.0)


# ===========================================================================
# TestBulletHomingExclusion
# ===========================================================================

class TestBulletCloakExclusion:
    def test_homing_ignores_cloaked(self):
        from game.entities.bullet import Bullet
        from game.utils.constants import WEAPONS_CONFIG

        weapons = load_yaml(WEAPONS_CONFIG)
        homing_cfg = weapons.get("homing_missile", {})
        if not homing_cfg:
            pytest.skip("homing_missile not in weapons config")

        owner_tank, _ = _make_tank()
        bullet = Bullet(
            x=200, y=200, angle=0,
            owner=owner_tank,
            config=homing_cfg,
        )

        # Create target that is cloaked
        target, _ = _make_tank()
        target._cloaked = True
        target.x = 300
        target.y = 200

        bullet.set_targets_getter(lambda: [target])
        angle_before = math.atan2(bullet._dy, bullet._dx)
        bullet.update(0.1)
        angle_after = math.atan2(bullet._dy, bullet._dx)
        # Angle should not change since the only target is cloaked
        assert abs(angle_after - angle_before) < 0.01


# ===========================================================================
# TestAIUltimate
# ===========================================================================

class TestAICloakDetection:
    def test_ai_patrols_when_target_cloaked(self):
        from game.systems.ai_controller import AIController, AIState
        from game.utils.constants import AI_DIFFICULTY_CONFIG
        from game.utils.config_loader import get_ai_config

        target, _ = _make_tank()
        target._cloaked = True
        target.x = 450  # within detection range

        ai_cfg = get_ai_config("medium", AI_DIFFICULTY_CONFIG)
        controller = AIController(config=ai_cfg, target_getter=lambda: target)
        ai_tank, _ = _make_tank(tank_type="heavy_tank")
        ai_tank.x = 400
        ai_tank.y = 300
        controller.set_owner(ai_tank)
        controller.tick(0.016)
        controller.get_input()

        assert controller._state == AIState.PATROL


# ===========================================================================
# TestConfigLoading
# ===========================================================================

class TestUltimatesConfig:
    def test_all_tank_types_present(self):
        cfg = load_yaml(ULTIMATES_CONFIG)
        for tank_type in ("light_tank", "medium_tank", "heavy_tank", "scout_tank"):
            assert tank_type in cfg, f"{tank_type} missing from ultimates.yaml"

    def test_all_ability_types_valid(self):
        cfg = load_yaml(ULTIMATES_CONFIG)
        valid = {
            "speed_burst", "shield_dome", "artillery_strike", "cloak",
            "lockdown", "disruptor",   # v0.33.5 additions
        }
        for tank_type, data in cfg.items():
            assert data["ability_type"] in valid, f"{tank_type} has invalid ability type"

    def test_charge_max_positive(self):
        cfg = load_yaml(ULTIMATES_CONFIG)
        for tank_type, data in cfg.items():
            assert data["charge_max"] > 0

    def test_sfx_keys_present(self):
        from game.utils.constants import ULTIMATE_SFX
        cfg = load_yaml(ULTIMATES_CONFIG)
        for tank_type, data in cfg.items():
            key = data.get("sfx_key")
            assert key in ULTIMATE_SFX, f"{tank_type} sfx_key '{key}' not in ULTIMATE_SFX"


# ===========================================================================
# TestInputHandler
# ===========================================================================

class TestInputHandlerUltimate:
    @patch("pygame.key.get_pressed", create=True)
    @patch("pygame.mouse.get_pressed", create=True, return_value=(False, False, False))
    def test_f_key_triggers_ultimate(self, mock_mouse, mock_keys):
        import pygame
        from game.systems.input_handler import InputHandler

        # First frame: F not pressed
        keys_array = [False] * 512
        mock_keys.return_value = keys_array
        handler = InputHandler()
        inp = handler.get_input()
        assert inp.activate_ultimate is False

        # Second frame: F pressed
        keys_array[pygame.K_f] = True
        mock_keys.return_value = keys_array
        inp = handler.get_input()
        assert inp.activate_ultimate is True

        # Third frame: F still held — no re-trigger
        inp = handler.get_input()
        assert inp.activate_ultimate is False

    @patch("pygame.key.get_pressed", create=True)
    @patch("pygame.mouse.get_pressed", create=True, return_value=(False, False, False))
    def test_f_key_edge_detect_release(self, mock_mouse, mock_keys):
        import pygame
        from game.systems.input_handler import InputHandler

        handler = InputHandler()
        keys_array = [False] * 512

        # Press F
        keys_array[pygame.K_f] = True
        mock_keys.return_value = keys_array
        handler.get_input()

        # Release F
        keys_array[pygame.K_f] = False
        mock_keys.return_value = keys_array
        handler.get_input()

        # Press F again — should trigger
        keys_array[pygame.K_f] = True
        mock_keys.return_value = keys_array
        inp = handler.get_input()
        assert inp.activate_ultimate is True
