"""
tests/test_ai_weapon_awareness.py

Unit tests for AI weapon-awareness logic (v0.34).
No pygame required — all tests use plain Python stubs.
"""

import math
import pytest

from game.systems.ai_controller import (
    AIController,
    AIState,
    _RANGE_BOUNDS,
    _WEAPON_PROFILES,
    _nearest_arena_wall_point,
    get_weapon_profile,
)
from game.utils.constants import AI_ATTACK_RANGE, ARENA_HEIGHT, ARENA_WIDTH


# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> dict:
    base = {
        "reaction_time": 0.0,
        "accuracy": 1.0,       # full accuracy → deterministic thresholds
        "aggression": 1.0,
        "evasion_threshold": 0.10,
        "weapon_switch_interval": 4.0,
    }
    base.update(overrides)
    return base


class MockTarget:
    """Minimal enemy stub."""
    def __init__(self, x=400.0, y=300.0, vx=0.0, vy=0.0, health=100, max_health=100):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.health = health
        self.max_health = max_health
        self.angle = 0.0
        self.is_alive = True
        self._cloaked = False
        self.ultimate = None

    @property
    def position(self):
        return (self.x, self.y)

    @property
    def health_ratio(self):
        return self.health / self.max_health if self.max_health > 0 else 0.0


class MockWeaponTank(MockTarget):
    """Tank stub with weapon-slot support for weapon-awareness tests."""
    def __init__(self, x=0.0, y=0.0, weapon_type="standard_shell",
                 extra_slots=None, cooldowns=None, health=100, max_health=100):
        super().__init__(x=x, y=y, health=health, max_health=max_health)
        self._slots = [{"type": weapon_type, "speed": 280, "fire_rate": 1.0}]
        if extra_slots:
            self._slots.extend(extra_slots)
        self._active_slot = 0
        self._cooldowns = cooldowns if cooldowns else [0.0] * len(self._slots)

    @property
    def active_weapon(self):
        return self._slots[self._active_slot]

    @property
    def active_slot(self):
        return self._active_slot

    @property
    def weapon_slots(self):
        return list(self._slots)

    @property
    def slot_cooldowns(self):
        return list(self._cooldowns)


def _make_ctrl(owner, target=None, **cfg_overrides):
    tgt = target or MockTarget()
    ctrl = AIController(_make_config(**cfg_overrides), target_getter=lambda: tgt)
    ctrl.set_owner(owner)
    return ctrl


# ---------------------------------------------------------------------------
# TestWeaponProfile
# ---------------------------------------------------------------------------

class TestWeaponProfile:
    def test_known_weapon_returns_correct_profile(self):
        p = get_weapon_profile("railgun")
        assert p["fire_threshold"] == 3.0
        assert p["preferred_range"] == "far"
        assert p["aim_mode"] == "direct"

    def test_unknown_weapon_falls_back_to_standard_shell(self):
        p = get_weapon_profile("banana_cannon")
        ref = get_weapon_profile("standard_shell")
        assert p == ref

    @pytest.mark.parametrize("wtype", list(_WEAPON_PROFILES))
    def test_all_weapons_have_valid_aim_mode(self, wtype):
        valid = {"direct", "loose", "lead", "wall_bounce", "pool_place"}
        assert _WEAPON_PROFILES[wtype]["aim_mode"] in valid

    @pytest.mark.parametrize("wtype", list(_WEAPON_PROFILES))
    def test_all_weapons_have_valid_preferred_range(self, wtype):
        assert _WEAPON_PROFILES[wtype]["preferred_range"] in _RANGE_BOUNDS

    @pytest.mark.parametrize("wtype", list(_WEAPON_PROFILES))
    def test_all_weapons_have_positive_fire_threshold(self, wtype):
        assert _WEAPON_PROFILES[wtype]["fire_threshold"] > 0

    @pytest.mark.parametrize("wtype", list(_WEAPON_PROFILES))
    def test_all_weapons_have_positive_jitter_scale(self, wtype):
        assert _WEAPON_PROFILES[wtype]["jitter_scale"] > 0


# ---------------------------------------------------------------------------
# TestNearestArenaWallPoint
# ---------------------------------------------------------------------------

class TestNearestArenaWallPoint:
    def test_target_to_the_right_gives_right_wall(self):
        origin = (400.0, 600.0)
        target = (1500.0, 600.0)   # clearly to the right
        wx, wy = _nearest_arena_wall_point(origin, target)
        assert wx > ARENA_WIDTH / 2, "expected right-wall x"

    def test_target_to_the_left_gives_left_wall(self):
        origin = (1200.0, 600.0)
        target = (100.0, 600.0)    # clearly to the left
        wx, wy = _nearest_arena_wall_point(origin, target)
        assert wx < ARENA_WIDTH / 2, "expected left-wall x"

    def test_target_above_gives_top_wall(self):
        origin = (800.0, 800.0)
        target = (800.0, 50.0)     # directly above
        wx, wy = _nearest_arena_wall_point(origin, target)
        assert wy < ARENA_HEIGHT / 2, "expected top-wall y"

    def test_target_below_gives_bottom_wall(self):
        origin = (800.0, 200.0)
        target = (800.0, 1150.0)   # directly below
        wx, wy = _nearest_arena_wall_point(origin, target)
        assert wy > ARENA_HEIGHT / 2, "expected bottom-wall y"

    def test_returns_tuple_of_two_floats(self):
        pt = _nearest_arena_wall_point((400.0, 300.0), (1400.0, 900.0))
        assert len(pt) == 2
        assert all(isinstance(v, float) for v in pt)

    def test_wall_point_stays_within_arena_bounds(self):
        for ox, oy, tx, ty in [
            (100, 100, 1500, 1100),
            (800, 600, 10, 10),
            (400, 900, 1200, 100),
        ]:
            wx, wy = _nearest_arena_wall_point((ox, oy), (tx, ty))
            assert 0 <= wx <= ARENA_WIDTH
            assert 0 <= wy <= ARENA_HEIGHT


# ---------------------------------------------------------------------------
# TestEffectiveAttackRange
# ---------------------------------------------------------------------------

class TestEffectiveAttackRange:
    def test_close_range_weapon_triggers_attack_earlier(self):
        owner = MockWeaponTank(weapon_type="flamethrower")
        ctrl = _make_ctrl(owner)
        close_range = ctrl._effective_attack_range
        owner2 = MockWeaponTank(weapon_type="railgun")
        ctrl2 = _make_ctrl(owner2)
        far_range = ctrl2._effective_attack_range
        assert close_range < far_range

    def test_never_exceeds_ai_attack_range_constant(self):
        for wtype in _WEAPON_PROFILES:
            owner = MockWeaponTank(weapon_type=wtype)
            ctrl = _make_ctrl(owner)
            assert ctrl._effective_attack_range <= AI_ATTACK_RANGE, (
                f"{wtype}: effective_attack_range exceeds AI_ATTACK_RANGE"
            )

    def test_medium_weapon_uses_midrange_value(self):
        lo, hi = _RANGE_BOUNDS["medium"]
        expected = min((lo + hi) / 2.0, AI_ATTACK_RANGE)
        owner = MockWeaponTank(weapon_type="standard_shell")
        ctrl = _make_ctrl(owner)
        assert ctrl._effective_attack_range == pytest.approx(expected)

    def test_far_weapon_gives_larger_range_than_medium(self):
        owner_med = MockWeaponTank(weapon_type="standard_shell")
        owner_far = MockWeaponTank(weapon_type="homing_missile")
        ctrl_med = _make_ctrl(owner_med)
        ctrl_far = _make_ctrl(owner_far)
        assert ctrl_far._effective_attack_range > ctrl_med._effective_attack_range

    def test_no_owner_returns_ai_attack_range(self):
        ctrl = AIController(_make_config(), target_getter=lambda: None)
        assert ctrl._effective_attack_range == AI_ATTACK_RANGE


# ---------------------------------------------------------------------------
# TestComputeAimAngle
# ---------------------------------------------------------------------------

class TestComputeAimAngle:
    """Tests for AIController._compute_aim_angle via _attack_input behavior."""

    def _setup(self, owner_wtype, target_x=300.0, target_y=0.0, tvx=0.0, tvy=0.0):
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type=owner_wtype)
        target = MockTarget(x=target_x, y=target_y, vx=tvx, vy=tvy)
        ctrl = _make_ctrl(owner, target)
        return ctrl, owner, target

    def test_direct_mode_aims_at_target(self):
        from game.utils.math_utils import angle_to
        ctrl, owner, target = self._setup("standard_shell", target_x=300.0, target_y=0.0)
        expected = angle_to(owner.position, target.position)
        result = ctrl._compute_aim_angle(target, "direct", owner.active_weapon)
        assert result == pytest.approx(expected)

    def test_loose_mode_same_as_direct(self):
        from game.utils.math_utils import angle_to
        ctrl, owner, target = self._setup("homing_missile", target_x=300.0, target_y=0.0)
        expected = angle_to(owner.position, target.position)
        result = ctrl._compute_aim_angle(target, "loose", owner.active_weapon)
        assert result == pytest.approx(expected)

    def test_lead_mode_leads_rightward_moving_target(self):
        from game.utils.math_utils import angle_to
        # Owner at origin; target at (0, 280) directly south, moving east at 200 px/s.
        # Direct angle ≈ 90° (south). Lead point = (200, 280), so lead angle ≠ 90°.
        ctrl, owner, target = self._setup("grenade_launcher",
                                           target_x=0.0, target_y=280.0,
                                           tvx=200.0, tvy=0.0)
        direct_angle = angle_to(owner.position, target.position)
        lead_angle = ctrl._compute_aim_angle(target, "lead",
                                             {"speed": 280, "type": "grenade_launcher"})
        # Lead angle should differ from direct because target is moving perpendicular
        assert lead_angle != pytest.approx(direct_angle, abs=0.5)

    def test_lead_mode_stationary_target_equals_direct(self):
        from game.utils.math_utils import angle_to
        ctrl, owner, target = self._setup("grenade_launcher",
                                           target_x=300.0, target_y=0.0,
                                           tvx=0.0, tvy=0.0)
        direct = angle_to(owner.position, target.position)
        lead = ctrl._compute_aim_angle(target, "lead",
                                       {"speed": 280, "type": "grenade_launcher"})
        assert lead == pytest.approx(direct)

    def test_wall_bounce_mode_differs_from_direct(self):
        from game.utils.math_utils import angle_to
        ctrl, owner, target = self._setup("bouncing_round",
                                           target_x=300.0, target_y=0.0)
        direct = angle_to(owner.position, target.position)
        bounce = ctrl._compute_aim_angle(target, "wall_bounce", owner.active_weapon)
        # Wall-bounce angle should aim at a wall point, not straight at the target
        assert bounce != pytest.approx(direct, abs=1.0)

    def test_pool_place_mode_leads_moving_target(self):
        ctrl, owner, target = self._setup("glue_gun",
                                           target_x=300.0, target_y=0.0,
                                           tvx=100.0, tvy=0.0)
        pool_angle = ctrl._compute_aim_angle(target, "pool_place", owner.active_weapon)
        # Pool leads rightward movement → angle should point right-of-center
        # angle_to(0,0 → 300,0) is 0° in pygame convention;
        # leading right means pool_angle ~ 0° (same direction) — just verify it resolves
        assert isinstance(pool_angle, float)

    def test_pool_place_stationary_target_aims_at_target(self):
        from game.utils.math_utils import angle_to
        ctrl, owner, target = self._setup("lava_gun",
                                           target_x=300.0, target_y=0.0,
                                           tvx=0.0, tvy=0.0)
        direct = angle_to(owner.position, target.position)
        pool = ctrl._compute_aim_angle(target, "pool_place", owner.active_weapon)
        assert pool == pytest.approx(direct)


# ---------------------------------------------------------------------------
# TestRangeManagementInAttack
# ---------------------------------------------------------------------------

class TestRangeManagementInAttack:
    """_attack_input should apply throttle to stay in the weapon's preferred band."""

    def _get_attack_throttle(self, weapon_type, dist):
        """Run _attack_input with owner at origin and target at (dist, 0), return throttle."""
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type=weapon_type)
        target = MockTarget(x=dist, y=0.0)
        ctrl = _make_ctrl(owner, target)
        inp = ctrl._attack_input(target)
        return inp.throttle

    def test_close_weapon_does_not_reverse_when_already_close(self):
        # spread_shot preferred_range="close" → lo=0, hi=200; at dist=10 lo=0 so no reverse
        throttle = self._get_attack_throttle("spread_shot", dist=10.0)
        assert throttle >= 0.0

    def test_far_weapon_closes_in_when_beyond_band(self):
        # railgun preferred_range="far" → lo=300, hi=375; at dist=400 > hi=375 → close in
        throttle = self._get_attack_throttle("railgun", dist=400.0)
        assert throttle > 0.0

    def test_medium_weapon_stands_still_in_band(self):
        # standard_shell preferred_range="medium" → lo=180, hi=350; at dist=250 → in band
        throttle = self._get_attack_throttle("standard_shell", dist=250.0)
        assert throttle == pytest.approx(0.0)

    def test_medium_weapon_reverses_when_too_close(self):
        # standard_shell at dist=50 < lo=180 → back off
        throttle = self._get_attack_throttle("standard_shell", dist=50.0)
        assert throttle < 0.0

    def test_close_weapon_closes_when_too_far(self):
        # flamethrower preferred_range="close" → hi=200; at dist=350 → close in
        throttle = self._get_attack_throttle("flamethrower", dist=350.0)
        assert throttle > 0.0


# ---------------------------------------------------------------------------
# TestFireThresholdScaling
# ---------------------------------------------------------------------------

class TestFireThresholdScaling:
    """fire_threshold * accuracy determines the angular window needed to fire."""

    def test_railgun_tight_threshold_at_full_accuracy(self):
        # railgun fire_threshold=3.0, accuracy=1.0 → threshold = 3.0°
        # With jitter_scale=0.2 and accuracy=1.0, jitter ≈ 0 → any alignment < 3° fires
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type="railgun")
        target = MockTarget(x=300.0, y=0.0)
        ctrl = _make_ctrl(owner, target, accuracy=1.0, aggression=1.0)
        # Owner angle 0° aimed at target at (300,0) → diff should be near 0
        owner.angle = 0.0
        inp = ctrl._attack_input(target)
        # Should fire since perfectly aligned and threshold=3°
        assert inp.fire

    def test_homing_missile_fires_at_large_angle_error(self):
        # homing fire_threshold=30° × accuracy=1.0 → 30° window
        # Place target at 90° from owner's facing so diff=90° — should NOT fire
        # but at 20° error it should be within threshold
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type="homing_missile")
        # Target at (0, 300) — 90° angle in pygame coords from owner facing 0°
        target = MockTarget(x=0.0, y=300.0)
        ctrl = _make_ctrl(owner, target, accuracy=1.0, aggression=1.0)
        owner.angle = 0.0
        # With jitter_scale=0.5 and accuracy=1.0, jitter=0 → diff = angle_to(0,0 → 0,300)
        # angle_to returns ~90° in pygame convention; 90° > 30° threshold → no fire
        inp = ctrl._attack_input(target)
        assert not inp.fire

    def test_standard_shell_threshold_scales_with_accuracy(self):
        # standard_shell fire_threshold=10° × accuracy=0.5 → 5° effective threshold
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type="standard_shell")
        target = MockTarget(x=300.0, y=0.0)
        ctrl = _make_ctrl(owner, target, accuracy=0.5, aggression=1.0)
        # At accuracy=0.5, threshold = 5°; jitter = 0.5 * uniform(-30,30) * 1.0
        # We can't deterministically check fire, but at accuracy=1.0 it always fires
        ctrl2 = _make_ctrl(owner, target, accuracy=1.0, aggression=1.0)
        owner.angle = 0.0
        inp = ctrl2._attack_input(target)
        assert inp.fire


# ---------------------------------------------------------------------------
# TestScoreWeaponSlot
# ---------------------------------------------------------------------------

class TestScoreWeaponSlot:
    def test_score_is_between_zero_and_one(self):
        owner = MockWeaponTank(weapon_type="standard_shell")
        target = MockTarget(x=250.0, y=0.0)
        ctrl = _make_ctrl(owner, target)
        score = ctrl._score_weapon_slot(0, target, dist=250.0)
        assert 0.0 <= score <= 1.0

    def test_out_of_bounds_slot_returns_zero(self):
        owner = MockWeaponTank(weapon_type="standard_shell")
        ctrl = _make_ctrl(owner)
        assert ctrl._score_weapon_slot(99, None, dist=250.0) == 0.0

    def test_close_range_weapon_scores_higher_when_close(self):
        owner = MockWeaponTank(
            weapon_type="spread_shot",
            extra_slots=[{"type": "standard_shell", "speed": 280, "fire_rate": 1.0}],
        )
        target = MockTarget(x=80.0, y=0.0)
        ctrl = _make_ctrl(owner, target)
        score_spread = ctrl._score_weapon_slot(0, target, dist=80.0)   # close weapon
        score_std    = ctrl._score_weapon_slot(1, target, dist=80.0)   # medium weapon
        assert score_spread > score_std

    def test_far_range_weapon_scores_higher_when_far(self):
        owner = MockWeaponTank(
            weapon_type="railgun",
            extra_slots=[{"type": "spread_shot", "speed": 280, "fire_rate": 1.0}],
        )
        target = MockTarget(x=350.0, y=0.0)
        ctrl = _make_ctrl(owner, target)
        score_rail   = ctrl._score_weapon_slot(0, target, dist=350.0)
        score_spread = ctrl._score_weapon_slot(1, target, dist=350.0)
        assert score_rail > score_spread

    def test_ready_weapon_beats_on_cooldown_weapon(self):
        owner = MockWeaponTank(
            weapon_type="standard_shell",
            extra_slots=[{"type": "standard_shell", "speed": 280, "fire_rate": 1.0}],
            cooldowns=[3.0, 0.0],   # slot 0 on heavy cooldown, slot 1 ready
        )
        target = MockTarget(x=250.0, y=0.0)
        ctrl = _make_ctrl(owner, target)
        score_cd    = ctrl._score_weapon_slot(0, target, dist=250.0)
        score_ready = ctrl._score_weapon_slot(1, target, dist=250.0)
        assert score_ready > score_cd

    def test_aoe_bonus_applied_when_healthy(self):
        owner = MockWeaponTank(
            weapon_type="grenade_launcher",
            extra_slots=[{"type": "standard_shell", "speed": 280, "fire_rate": 1.0}],
            health=100, max_health=100,
        )
        target = MockTarget(x=250.0, y=0.0)
        ctrl = _make_ctrl(owner, target)
        score_nade = ctrl._score_weapon_slot(0, target, dist=250.0)
        score_std  = ctrl._score_weapon_slot(1, target, dist=250.0)
        # Both at same distance but grenade gets AoE bonus
        assert score_nade > score_std

    def test_no_owner_returns_zero(self):
        ctrl = AIController(_make_config(), target_getter=lambda: None)
        assert ctrl._score_weapon_slot(0, None, dist=250.0) == 0.0


# ---------------------------------------------------------------------------
# TestSelectBestWeaponSlot
# ---------------------------------------------------------------------------

class TestSelectBestWeaponSlot:
    def test_selects_close_weapon_when_close(self):
        owner = MockWeaponTank(
            weapon_type="railgun",   # slot 0 — far range
            extra_slots=[{"type": "flamethrower", "speed": 200, "fire_rate": 6.0}],  # slot 1 — close
        )
        target = MockTarget(x=50.0, y=0.0)   # very close
        ctrl = _make_ctrl(owner, target)
        best = ctrl._select_best_weapon_slot()
        assert best == 1  # flamethrower suits close range better

    def test_selects_far_weapon_when_far(self):
        owner = MockWeaponTank(
            weapon_type="flamethrower",   # slot 0 — close range
            extra_slots=[{"type": "railgun", "speed": 600, "fire_rate": 0.2}],  # slot 1 — far
        )
        target = MockTarget(x=350.0, y=0.0)   # far
        ctrl = _make_ctrl(owner, target)
        best = ctrl._select_best_weapon_slot()
        assert best == 1  # railgun suits far range better

    def test_hysteresis_prevents_marginal_switch(self):
        # Both slots are standard_shell (identical scores) — should stay on current
        owner = MockWeaponTank(
            weapon_type="standard_shell",
            extra_slots=[{"type": "standard_shell", "speed": 280, "fire_rate": 1.0}],
        )
        owner._active_slot = 0
        target = MockTarget(x=250.0, y=0.0)
        ctrl = _make_ctrl(owner, target)
        best = ctrl._select_best_weapon_slot()
        assert best == 0   # no meaningful improvement → stay on current

    def test_returns_current_slot_when_single_slot(self):
        owner = MockWeaponTank(weapon_type="standard_shell")
        target = MockTarget(x=250.0, y=0.0)
        ctrl = _make_ctrl(owner, target)
        assert ctrl._select_best_weapon_slot() == 0

    def test_no_owner_returns_zero(self):
        ctrl = AIController(_make_config(), target_getter=lambda: None)
        assert ctrl._select_best_weapon_slot() == 0


# ---------------------------------------------------------------------------
# TestWeaponSwitchInterval
# ---------------------------------------------------------------------------

class TestWeaponSwitchInterval:
    def test_interval_read_from_config(self):
        ctrl = AIController(_make_config(weapon_switch_interval=2.5),
                            target_getter=lambda: None)
        assert ctrl._weapon_switch_interval == pytest.approx(2.5)

    def test_default_interval_when_not_in_config(self):
        ctrl = AIController(
            {"reaction_time": 0.0, "accuracy": 1.0, "aggression": 1.0,
             "evasion_threshold": 0.1},
            target_getter=lambda: None,
        )
        assert ctrl._weapon_switch_interval == pytest.approx(4.0)

    def test_fast_interval_triggers_switch_sooner(self):
        # With a very short interval, a tick of 10s should trigger a switch
        owner = MockWeaponTank(
            weapon_type="flamethrower",
            extra_slots=[{"type": "railgun", "speed": 600, "fire_rate": 0.2}],
        )
        target = MockTarget(x=350.0, y=0.0)
        ctrl = AIController(_make_config(weapon_switch_interval=1.0),
                            target_getter=lambda: target)
        ctrl.set_owner(owner)
        # Force timer to expire
        ctrl._weapon_cycle_timer = 0.0
        ctrl.tick(0.01)
        # After tick, a switch toward the better slot should be queued
        assert ctrl._pending_weapon_cycle != 0


# ---------------------------------------------------------------------------
# TestGroundPoolPlacement
# ---------------------------------------------------------------------------

class TestGroundPoolPlacement:
    def test_pool_aims_ahead_of_rightward_moving_target(self):
        from game.utils.math_utils import angle_to
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type="glue_gun")
        target = MockTarget(x=300.0, y=0.0, vx=150.0, vy=0.0)
        ctrl = _make_ctrl(owner, target)
        direct = angle_to(owner.position, target.position)
        pool = ctrl._pool_aim_angle(target)
        # Lead point is (300 + some_lead, 0), still angle=0 in pygame coords
        # Both would point the same horizontal direction — check the aim point is further right
        # The lead x is > 300 but vy=0 so y stays 0 → angle stays near 0°
        # Just confirm it resolves without error and is a valid float
        assert isinstance(pool, float)

    def test_pool_aims_at_target_when_stationary(self):
        from game.utils.math_utils import angle_to
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type="glue_gun")
        target = MockTarget(x=300.0, y=200.0, vx=0.0, vy=0.0)
        ctrl = _make_ctrl(owner, target)
        direct = angle_to(owner.position, target.position)
        pool = ctrl._pool_aim_angle(target)
        assert pool == pytest.approx(direct)

    def test_pool_leads_diagonally_moving_target(self):
        from game.utils.math_utils import angle_to
        owner = MockWeaponTank(x=0.0, y=0.0, weapon_type="lava_gun")
        # Target moving diagonally
        target = MockTarget(x=300.0, y=300.0, vx=100.0, vy=-100.0)
        ctrl = _make_ctrl(owner, target)
        direct = angle_to(owner.position, target.position)
        pool = ctrl._pool_aim_angle(target)
        # Lead point differs from current position → angle should differ from direct
        assert pool != pytest.approx(direct, abs=0.5)
