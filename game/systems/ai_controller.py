"""
game/systems/ai_controller.py

AIController — state machine AI for enemy tanks.

States:
  PATROL   — wanders when player is out of detection range
  PURSUE   — moves toward player when detected
  ATTACK   — fires when in range and has line of sight
  EVADE    — retreats when health is critically low
  RECOVERY — temporary sub-state: reverses + rotates to escape an obstacle

All difficulty parameters (reaction_time, accuracy, aggression,
evasion_threshold) are loaded from ai_difficulty.yaml — nothing
is hardcoded here.

The Tank class calls get_input() identically to InputHandler.
The scene calls tick(dt) once per frame BEFORE tank.update(dt) to advance
stuck detection and the recovery timer without changing Tank's interface.
"""

import math
import random
from enum import Enum, auto
from typing import Optional

from game.entities.tank import TankInput
from game.utils.constants import (
    AI_ATTACK_RANGE,
    AI_DETECTION_RANGE,
    AI_EVASION_HEALTH_RATIO,
    AI_PICKUP_OPPORTUNISTIC_RANGE,
    AI_PICKUP_SEEK_RANGE,
)
from game.utils.logger import get_logger
from game.utils.math_utils import angle_difference, angle_to, distance
from game.utils.stuck_detector import StuckDetector

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Weapon profiles (v0.34) — per-weapon AI behavior overrides
# ---------------------------------------------------------------------------
# preferred_range: "close" | "medium" | "far" — drives engagement distance
# aim_mode:        "direct" | "loose" | "lead" | "wall_bounce" | "pool_place"
# fire_threshold:  max angle error (°) before AI will fire (scaled by accuracy)
# jitter_scale:    multiplier on the base accuracy jitter
_WEAPON_PROFILES: dict[str, dict] = {
    "standard_shell":   {"preferred_range": "medium", "aim_mode": "direct",     "fire_threshold": 10.0, "jitter_scale": 1.0},
    "spread_shot":      {"preferred_range": "close",  "aim_mode": "direct",     "fire_threshold": 12.0, "jitter_scale": 1.2},
    "bouncing_round":   {"preferred_range": "medium", "aim_mode": "wall_bounce","fire_threshold": 15.0, "jitter_scale": 0.8},
    "homing_missile":   {"preferred_range": "far",    "aim_mode": "loose",      "fire_threshold": 30.0, "jitter_scale": 0.5},
    "grenade_launcher": {"preferred_range": "medium", "aim_mode": "lead",       "fire_threshold": 18.0, "jitter_scale": 0.9},
    "cryo_round":       {"preferred_range": "medium", "aim_mode": "direct",     "fire_threshold": 10.0, "jitter_scale": 1.0},
    "poison_shell":     {"preferred_range": "medium", "aim_mode": "direct",     "fire_threshold": 10.0, "jitter_scale": 1.0},
    "flamethrower":     {"preferred_range": "close",  "aim_mode": "direct",     "fire_threshold": 12.0, "jitter_scale": 1.3},
    "emp_blast":        {"preferred_range": "medium", "aim_mode": "lead",       "fire_threshold": 20.0, "jitter_scale": 0.8},
    "railgun":          {"preferred_range": "far",    "aim_mode": "direct",     "fire_threshold":  3.0, "jitter_scale": 0.2},
    "laser_beam":       {"preferred_range": "medium", "aim_mode": "direct",     "fire_threshold":  8.0, "jitter_scale": 0.6},
    "glue_gun":         {"preferred_range": "medium", "aim_mode": "pool_place", "fire_threshold": 20.0, "jitter_scale": 1.0},
    "lava_gun":         {"preferred_range": "medium", "aim_mode": "pool_place", "fire_threshold": 20.0, "jitter_scale": 1.0},
    "concussion_blast": {"preferred_range": "medium", "aim_mode": "direct",     "fire_threshold": 12.0, "jitter_scale": 1.0},
}

# Pixel ranges for each preferred_range band
_RANGE_BOUNDS: dict[str, tuple[float, float]] = {
    "close":  (0.0,   200.0),
    "medium": (180.0, 350.0),
    "far":    (300.0, AI_ATTACK_RANGE),
}

# ---------------------------------------------------------------------------
# Elemental awareness constants (v0.36)
# ---------------------------------------------------------------------------

# Maps weapon type → the elemental effect type it applies on hit
_WEAPON_DAMAGE_TYPES: dict[str, str] = {
    "cryo_round":    "ice",
    "poison_shell":  "poison",
    "flamethrower":  "fire",
    "lava_gun":      "fire",
    "emp_blast":     "electric",
    # all other weapons apply no elemental effect
}

# Combo table: if 'requires' is active on target and we fire 'completes',
# a high-value elemental reaction triggers.
_ELEMENTAL_COMBOS: list[dict] = [
    {"requires": "ice",    "completes": "fire",     "value": 0.60},  # steam_burst
    {"requires": "poison", "completes": "fire",     "value": 0.50},  # accelerated_burn
    {"requires": "ice",    "completes": "electric", "value": 0.70},  # deep_freeze
]


def get_weapon_profile(weapon_type: str) -> dict:
    """Return AI behavior profile for weapon_type; falls back to standard_shell."""
    return _WEAPON_PROFILES.get(weapon_type, _WEAPON_PROFILES["standard_shell"])


def _nearest_arena_wall_point(origin: tuple, target_pos: tuple) -> tuple:
    """Return a world-space point on the arena wall in the general direction of target_pos.

    Used by the wall_bounce aim mode to give bouncing_round a meaningful
    indirect-fire angle.  Finds which of the four walls is most directly
    behind the target relative to the origin and returns a point 60 px
    inside that wall at the target's lateral position.
    """
    from game.utils.constants import ARENA_WIDTH, ARENA_HEIGHT
    ox, oy = origin
    tx, ty = target_pos
    dx = tx - ox
    dy = ty - oy

    # Ratios to each wall (treat zero-delta as very far to avoid division by zero)
    t_left   = (-ox) / dx if dx < 0 else float("inf")
    t_right  = (ARENA_WIDTH - ox) / dx if dx > 0 else float("inf")
    t_top    = (-oy) / dy if dy < 0 else float("inf")
    t_bottom = (ARENA_HEIGHT - oy) / dy if dy > 0 else float("inf")

    t_min = min(t_left, t_right, t_top, t_bottom)

    if t_min == t_left:
        return (60.0, max(60.0, min(oy + dy * t_left, ARENA_HEIGHT - 60.0)))
    if t_min == t_right:
        return (ARENA_WIDTH - 60.0, max(60.0, min(oy + dy * t_right, ARENA_HEIGHT - 60.0)))
    if t_min == t_top:
        return (max(60.0, min(ox + dx * t_top, ARENA_WIDTH - 60.0)), 60.0)
    # bottom wall
    return (max(60.0, min(ox + dx * t_bottom, ARENA_WIDTH - 60.0)), ARENA_HEIGHT - 60.0)


# ---------------------------------------------------------------------------
# Obstacle-avoidance tuning (internal to AI — not exposed as difficulty params)
# ---------------------------------------------------------------------------
_LOOKAHEAD_PX: float = 130.0     # how far ahead to probe for obstacles
_STEER_ANGLE: float = 40.0       # degrees added to desired heading when dodging

# ---------------------------------------------------------------------------
# Recovery tuning
# ---------------------------------------------------------------------------
# Two-phase recovery prevents the reverse→forward→wall oscillation loop:
#   Phase 1: reverse + full rotation  — backs the tank away from the obstacle
#   Phase 2: forward + half rotation  — consolidates the new heading so the
#            tank is pointing away from the wall before the state machine
#            resumes, preventing it from immediately re-hitting the same wall
_RECOVERY_PHASE1: float = 0.55   # seconds: reverse + full rotate
_RECOVERY_PHASE2: float = 0.45   # seconds: forward + half rotate
_RECOVERY_DURATION: float = _RECOVERY_PHASE1 + _RECOVERY_PHASE2  # 1.0s total

# Post-recovery immunity: after recovery completes the stuck check is
# suppressed for this many seconds.  Prevents tight re-trigger while the
# tank still has residual wall proximity after phase 2.
_POST_RECOVERY_IMMUNITY: float = 1.2

# Flee-angle bias injected during post-recovery immunity to break corner symmetry.
# The bias rotates the flee direction in the same direction as the last recovery
# rotation, nudging the AI out of the corner before immunity expires.
_EVADE_BIAS_ANGLE: float = 65.0

_STUCK_WINDOW: float = 0.5       # rolling window for stuck detection (seconds)
_STUCK_THRESHOLD: float = 10.0   # minimum displacement (px) to not be "stuck"


def make_nearest_enemy_getter(owner_ref, all_tanks_getter, low_hp_priority_weight: float = 0.5):
    """
    Factory that returns a zero-arg callable targeting the best living enemy.

    Target selection uses a weighted score:
        effective_dist = real_dist * max(0.1, 1.0 - weight * (1.0 - hp_ratio))

    A weight of 0.0 degrades to pure nearest-distance targeting.
    A weight of 1.2 causes near-dead targets to be strongly preferred
    over healthy targets at any distance.

    Target stickiness: once a target's HP drops below 40%, the getter
    locks onto them until they die or recover above the threshold,
    preventing wounded tanks from escaping by being momentarily out-ranged.

    Args:
        owner_ref:              The Tank this controller belongs to.
        all_tanks_getter:       Zero-arg callable returning current list of all tanks.
        low_hp_priority_weight: Distance discount multiplier for low-HP targets.

    Returns:
        Callable returning the best living non-owner Tank, or None if none exist.
    """
    _cached_target = [None]   # list cell for mutation inside closure

    def _getter():
        all_tanks = all_tanks_getter()
        enemies = [t for t in all_tanks if t is not owner_ref and t.is_alive]
        if not enemies:
            _cached_target[0] = None
            return None

        # Stick with current target while it is still alive and critically low on HP
        current = _cached_target[0]
        if (current is not None
                and current.is_alive
                and getattr(current, "health_ratio", 1.0) < 0.40):
            return current

        def _score(t) -> float:
            dist = math.dist(owner_ref.position, t.position)
            hp_ratio = getattr(t, "health_ratio", 1.0)
            hp_discount = max(0.1, 1.0 - (low_hp_priority_weight * (1.0 - hp_ratio)))
            return dist * hp_discount

        _cached_target[0] = min(enemies, key=_score)
        return _cached_target[0]

    return _getter


class AIState(Enum):
    PATROL = auto()
    PURSUE = auto()
    ATTACK = auto()
    EVADE = auto()
    RECOVERY = auto()


class AIController:
    """
    State-machine AI controller. Injected into a Tank in place of InputHandler.

    Parameters:
        config (dict): difficulty config from ai_difficulty.yaml
        target_getter (callable): zero-arg callable returning the player Tank
    """

    def __init__(self, config: dict, target_getter) -> None:
        self._state: AIState = AIState.PATROL
        self._target_getter = target_getter

        # Difficulty parameters
        self.reaction_time: float = float(config.get("reaction_time", 0.4))
        self.accuracy: float = float(config.get("accuracy", 0.72))
        self.aggression: float = float(config.get("aggression", 0.6))
        self.evasion_threshold: float = float(config.get("evasion_threshold", 0.40))
        self.low_hp_priority_weight: float = float(config.get("low_hp_priority_weight", 0.5))
        self._weapon_switch_interval: float = float(config.get("weapon_switch_interval", 4.0))
        self._elemental_awareness: float = float(config.get("elemental_awareness", 0.0))

        # Internal state
        self._reaction_timer: float = 0.0
        self._patrol_angle: float = random.uniform(0, 360)
        self._patrol_timer: float = 0.0
        self._owner: Optional[object] = None  # set by Tank after construction

        # Stuck detection + recovery
        self._stuck_detector: StuckDetector = StuckDetector(
            window_seconds=_STUCK_WINDOW,
            threshold_px=_STUCK_THRESHOLD,
        )
        self._recovery_timer: float = 0.0
        # Direction alternates each recovery to avoid spinning in place
        self._recovery_direction: float = 1.0
        # Captures the direction *before* the flip so _evade_input can bias the
        # flee angle in the same rotational direction the tank just turned.
        self._post_recovery_direction: float = 1.0
        # Immunity window after recovery — prevents immediate re-trigger
        self._recovery_immunity_timer: float = 0.0

        # Obstacle awareness — injected by the scene as a zero-arg callable
        # returning a list of live Obstacle instances.
        self._obstacles_getter = None

        # Pickup awareness (v0.20) — injected by the scene
        self._pickups_getter = None

        # Weapon cycling timer (v0.25.5) — AI switches weapons periodically
        self._weapon_cycle_timer: float = random.uniform(4.0, 8.0)
        self._pending_weapon_cycle: int = 0

        log.debug(
            "AIController created. Difficulty: reaction=%.2f acc=%.2f agg=%.2f evade_thresh=%.2f",
            self.reaction_time, self.accuracy, self.aggression, self.evasion_threshold,
        )

    # ------------------------------------------------------------------
    # Setup / injection
    # ------------------------------------------------------------------

    def set_owner(self, tank) -> None:
        """Called by the game when the AI tank is created so the controller can read self state."""
        self._owner = tank

    def set_pickups_getter(self, getter) -> None:
        """Inject a zero-arg callable returning live Pickup instances."""
        self._pickups_getter = getter

    def set_obstacles_getter(self, getter) -> None:
        """
        Inject a zero-arg callable that returns the current list of live Obstacle
        instances.  Called by GameplayScene after obstacles are loaded.

        Example:
            ctrl.set_obstacles_getter(lambda: [o for o in self._obstacles if o.is_alive])
        """
        self._obstacles_getter = getter

    # ------------------------------------------------------------------
    # Per-frame tick (called by the scene, not by Tank)
    # ------------------------------------------------------------------

    def tick(self, dt: float) -> None:
        """
        Advance stuck detection and recovery timer.
        Must be called by the scene BEFORE tank.update(dt) each frame.
        Does nothing if no owner is set.
        """
        if self._owner is None:
            return

        # Update stuck detector with the owner's current position
        self._stuck_detector.update(dt, self._owner.x, self._owner.y)

        # Count down post-recovery immunity window
        if self._recovery_immunity_timer > 0.0:
            self._recovery_immunity_timer -= dt

        # Count down recovery timer; resume state machine when it expires
        if self._state == AIState.RECOVERY:
            self._recovery_timer -= dt
            if self._recovery_timer <= 0.0:
                self._recovery_timer = 0.0
                # Remember this direction before flipping so _evade_input can
                # continue biasing the flee heading in the same rotational sense.
                self._post_recovery_direction = self._recovery_direction
                # Alternate direction so the next recovery turns the other way
                self._recovery_direction *= -1.0
                # Reset to PATROL; _update_state will re-evaluate next get_input()
                self._state = AIState.PATROL
                self._stuck_detector.reset()
                # Suppress stuck re-trigger while tank clears residual wall proximity
                self._recovery_immunity_timer = _POST_RECOVERY_IMMUNITY
                log.debug(
                    "AI recovery complete — resuming state machine. "
                    "Next recovery direction: %.0f  immunity=%.1fs",
                    self._recovery_direction, _POST_RECOVERY_IMMUNITY,
                )

        # Weapon switching — evaluate best slot on a configurable interval (v0.34)
        self._weapon_cycle_timer -= dt
        if self._weapon_cycle_timer <= 0:
            self._weapon_cycle_timer = random.uniform(
                self._weapon_switch_interval * 0.6, self._weapon_switch_interval
            )
            slots = getattr(self._owner, "weapon_slots", []) if self._owner else []
            if len(slots) > 1:
                best = self._select_best_weapon_slot()
                current = self._owner.active_slot
                if best != current:
                    n = len(self._owner.weapon_slots)
                    fwd = (best - current) % n
                    bwd = (current - best) % n
                    self._pending_weapon_cycle = 1 if fwd <= bwd else -1

    # ------------------------------------------------------------------
    # Controller interface (called by Tank.update each frame)
    # ------------------------------------------------------------------

    @property
    def state_name(self) -> str:
        """Current AI state as a human-readable string. Use instead of accessing _state directly."""
        return self._state.name

    def get_input(self) -> TankInput:
        """
        Evaluate current state and return control intent for this frame.
        tick(dt) must have been called this frame before get_input().
        """
        # RECOVERY is handled entirely here — skip normal state machine
        if self._state == AIState.RECOVERY:
            return self._recovery_input()

        target = self._target_getter()
        self._update_state(target)

        # Stuck check — only in movement states (not ATTACK — AI deliberately stands
        # still to aim) and not while the post-recovery immunity window is active.
        if (
            self._stuck_detector.is_stuck
            and self._recovery_immunity_timer <= 0.0
            and self._state in (AIState.PATROL, AIState.PURSUE, AIState.EVADE)
        ):
            self._enter_recovery()
            return self._recovery_input()

        if self._state == AIState.PATROL:
            result = self._patrol_input()
        elif self._state == AIState.PURSUE:
            result = self._pursue_input(target)
        elif self._state == AIState.ATTACK:
            result = self._attack_input(target)
        elif self._state == AIState.EVADE:
            result = self._evade_input(target)
        else:
            result = TankInput()

        # Inject pending weapon cycle (v0.25.5)
        if self._pending_weapon_cycle != 0:
            result = TankInput(
                throttle=result.throttle,
                rotate=result.rotate,
                fire=result.fire,
                turret_angle=result.turret_angle,
                cycle_weapon=self._pending_weapon_cycle,
            )
            self._pending_weapon_cycle = 0

        # AI ultimate activation (v0.28)
        # Offensive ultimates (speed_burst, artillery_strike) activate in ATTACK.
        # Defensive ultimates (shield_dome, cloak) activate in EVADE.
        activate_ult = False
        if self._owner is not None and self._owner.ultimate is not None:
            ult = self._owner.ultimate
            if ult.is_ready:
                ult_type = ult.ability_type
                if ult_type in ("speed_burst", "artillery_strike") and self._state == AIState.ATTACK:
                    activate_ult = random.random() < 0.30
                elif ult_type in ("shield_dome", "cloak") and self._state == AIState.EVADE:
                    activate_ult = random.random() < 0.40
        if activate_ult:
            result = TankInput(
                throttle=result.throttle,
                rotate=result.rotate,
                fire=result.fire,
                turret_angle=result.turret_angle,
                cycle_weapon=result.cycle_weapon,
                activate_ultimate=True,
            )

        return result

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _update_state(self, target) -> None:
        if self._owner is None or target is None or not target.is_alive:
            self._transition(AIState.PATROL)
            return

        dist = distance(self._owner.position, target.position)
        health_ratio = self._owner.health_ratio if self._owner else 1.0

        # Cloaked target — treat as invisible, revert to patrol (v0.28)
        if getattr(target, '_cloaked', False):
            self._transition(AIState.PATROL)
            return

        if health_ratio <= self.evasion_threshold:
            self._transition(AIState.EVADE)
        elif dist <= self._effective_attack_range:
            self._transition(AIState.ATTACK)
        elif dist <= AI_DETECTION_RANGE:
            self._transition(AIState.PURSUE)
        else:
            self._transition(AIState.PATROL)

    def _transition(self, new_state: AIState) -> None:
        if new_state != self._state:
            log.debug("AI state: %s → %s", self._state.name, new_state.name)
            self._state = new_state

    def _enter_recovery(self) -> None:
        """Transition into RECOVERY sub-state and arm the recovery timer."""
        log.debug(
            "AI stuck — entering RECOVERY (direction=%.0f, duration=%.1fs).",
            self._recovery_direction, _RECOVERY_DURATION,
        )
        self._state = AIState.RECOVERY
        self._recovery_timer = _RECOVERY_DURATION
        self._stuck_detector.reset()

    # ------------------------------------------------------------------
    # Per-state input producers
    # ------------------------------------------------------------------

    def _patrol_input(self) -> TankInput:
        """
        Move toward arena center while no enemy is in detection range.
        This ensures tanks converge from spawn corners rather than sitting idle.
        Turret tracks hull direction during patrol.
        Opportunistically grabs nearby pickups within AI_PICKUP_OPPORTUNISTIC_RANGE.
        """
        from game.utils.constants import ARENA_WIDTH, ARENA_HEIGHT
        # Opportunistic pickup grab
        pickup = self._nearest_pickup(AI_PICKUP_OPPORTUNISTIC_RANGE)
        if pickup is not None:
            return self._steer_toward(pickup.position)
        if self._owner is None:
            return TankInput()
        center = (ARENA_WIDTH / 2.0, ARENA_HEIGHT / 2.0)
        desired_angle = angle_to(self._owner.position, center)
        diff = angle_difference(self._owner.angle, desired_angle)
        rotate = 1.0 if diff > 5 else (-1.0 if diff < -5 else 0.0)
        throttle = 0.6 if abs(diff) < 60 else 0.2   # slow while turning hard
        turret = self._owner.angle
        return TankInput(throttle=throttle, rotate=rotate, fire=False, turret_angle=turret)

    def _pursue_input(self, target) -> TankInput:
        """Turn and move toward target with lightweight obstacle avoidance.
        Turret independently tracks the player while the hull steers.
        Opportunistically grabs nearby pickups within AI_PICKUP_OPPORTUNISTIC_RANGE."""
        if self._owner is None or target is None:
            return TankInput()
        # Opportunistic pickup grab while pursuing
        pickup = self._nearest_pickup(AI_PICKUP_OPPORTUNISTIC_RANGE)
        if pickup is not None:
            inp = self._steer_toward(pickup.position)
            inp.turret_angle = angle_to(self._owner.position, target.position)
            return inp
        desired_angle = angle_to(self._owner.position, target.position)
        turret_angle = desired_angle   # track player even while steering
        desired_angle += self._obstacle_steer_correction(desired_angle)
        diff = angle_difference(self._owner.angle, desired_angle)
        rotate = 1.0 if diff > 5 else (-1.0 if diff < -5 else 0.0)
        throttle = 1.0 if abs(diff) < 45 else 0.3
        return TankInput(throttle=throttle, rotate=rotate, fire=False,
                         turret_angle=turret_angle)

    def _attack_input(self, target) -> TankInput:
        """Aim and fire with weapon-aware angle, threshold, and range management (v0.34)."""
        if self._owner is None or target is None:
            return TankInput()
        active_wep = getattr(self._owner, "active_weapon", None) or {}
        wtype = active_wep.get("type", "standard_shell") if isinstance(active_wep, dict) else "standard_shell"
        profile = get_weapon_profile(wtype)
        jitter_scale = profile["jitter_scale"]
        # fire_threshold scales with accuracy so difficulty tiers still differentiate
        fire_threshold = profile["fire_threshold"] * self.accuracy

        turret_angle = self._compute_aim_angle(target, profile["aim_mode"], active_wep)
        jitter = (1.0 - self.accuracy) * random.uniform(-30, 30) * jitter_scale
        turret_angle += jitter
        diff = angle_difference(self._owner.angle, turret_angle)
        rotate = 1.0 if diff > 2 else (-1.0 if diff < -2 else 0.0)
        fire = abs(diff) < fire_threshold and random.random() < self.aggression

        # Range management: hold position in the weapon's preferred distance band
        dist = distance(self._owner.position, target.position)
        lo, hi = _RANGE_BOUNDS[profile["preferred_range"]]
        if dist < lo:
            throttle = -0.4   # too close — back off slightly
        elif dist > hi:
            throttle = 0.5    # too far — close in
        else:
            throttle = 0.0    # in the sweet spot — stand still to aim

        return TankInput(throttle=throttle, rotate=rotate, fire=fire,
                         turret_angle=turret_angle)

    def _compute_aim_angle(self, target, aim_mode: str, weapon_cfg: dict) -> float:
        """Return a turret angle (degrees) for the given aim mode.

        Modes:
          direct      — straight line to target (existing behavior)
          loose       — same as direct; wide fire_threshold handles homing tolerance
          lead        — predict target position using vx/vy and weapon speed
          wall_bounce — aim at the nearest arena wall in the target's direction
          pool_place  — aim ahead of target's velocity vector
        """
        if aim_mode == "lead":
            dist = distance(self._owner.position, target.position)
            speed = max(float(weapon_cfg.get("speed", 280)), 1.0)
            travel_time = dist / speed
            lead_x = target.x + getattr(target, "vx", 0.0) * travel_time
            lead_y = target.y + getattr(target, "vy", 0.0) * travel_time
            return angle_to(self._owner.position, (lead_x, lead_y))
        if aim_mode == "wall_bounce":
            wall_pt = _nearest_arena_wall_point(self._owner.position, target.position)
            return angle_to(self._owner.position, wall_pt)
        if aim_mode == "pool_place":
            return self._pool_aim_angle(target)
        # "direct" and "loose" both aim straight at the target
        return angle_to(self._owner.position, target.position)

    def _pool_aim_angle(self, target) -> float:
        """Aim ahead of the target's movement vector for ground pool weapons."""
        spd = math.hypot(getattr(target, "vx", 0.0), getattr(target, "vy", 0.0))
        if spd > 20.0:
            lead_t = 1.5
            aim_x = target.x + (target.vx / spd) * min(spd * lead_t, 180.0)
            aim_y = target.y + (target.vy / spd) * min(spd * lead_t, 180.0)
        else:
            aim_x, aim_y = target.x, target.y
        return angle_to(self._owner.position, (aim_x, aim_y))

    def _evade_input(self, target) -> TankInput:
        """Retreat away from the target. Turret keeps watching the player while fleeing.
        Prioritises health pickups within AI_PICKUP_SEEK_RANGE when low on HP."""
        if self._owner is None or target is None:
            return TankInput(throttle=-1.0, rotate=0.5, fire=False, turret_angle=0.0)

        # Health-seeking: prioritise health pickups when evading
        health_pickup = self._nearest_pickup(AI_PICKUP_SEEK_RANGE, type_filter="health")
        if health_pickup is not None:
            inp = self._steer_toward(health_pickup.position)
            inp.turret_angle = angle_to(self._owner.position, target.position)
            # Still fire at targets in attack range while seeking health
            dist = distance(self._owner.position, target.position)
            inp.fire = dist <= AI_ATTACK_RANGE and random.random() < self.aggression
            return inp

        # Turret faces the player (threatening even while retreating)
        turret_angle = angle_to(self._owner.position, target.position)

        # Flee direction is the opposite of the bearing to the target
        flee_angle = turret_angle + 180.0

        # Post-recovery bias: during the immunity window, nudge the flee angle in
        # the same rotational direction the tank just turned during recovery.  This
        # breaks corner symmetry where two walls produce equal-and-opposite steer
        # corrections that cancel each other out, keeping the flee vector blocked.
        # The bias fades linearly to zero as the immunity timer expires.
        if self._recovery_immunity_timer > 0.0:
            bias_strength = self._recovery_immunity_timer / _POST_RECOVERY_IMMUNITY
            flee_angle += self._post_recovery_direction * _EVADE_BIAS_ANGLE * bias_strength

        flee_angle += self._obstacle_steer_correction(flee_angle)
        diff = angle_difference(self._owner.angle, flee_angle)
        rotate = 1.0 if diff > 5 else (-1.0 if diff < -5 else 0.0)
        # Fighting withdrawal: fire at targets within attack range
        dist = distance(self._owner.position, target.position)
        fire = dist <= AI_ATTACK_RANGE and random.random() < self.aggression
        return TankInput(throttle=1.0, rotate=rotate, fire=fire,
                         turret_angle=turret_angle)

    def _recovery_input(self) -> TankInput:
        """
        Two-phase recovery to prevent the reverse→forward→same-wall oscillation loop.

        Phase 1 (_RECOVERY_PHASE1 seconds): full reverse + full rotation.
            Backs the tank away from the obstacle and begins establishing a new heading.
        Phase 2 (_RECOVERY_PHASE2 seconds): moderate forward + gentle rotation.
            Consolidates the new heading so the tank is genuinely pointed away from the
            wall before the normal state machine resumes.

        Turret stays aligned with hull during recovery — no target tracking needed.
        """
        turret = self._owner.angle if self._owner is not None else 0.0
        if self._recovery_timer > _RECOVERY_PHASE2:
            # Phase 1 — backing out
            return TankInput(throttle=-1.0, rotate=self._recovery_direction, fire=False,
                             turret_angle=turret)
        else:
            # Phase 2 — rolling forward in the new heading
            return TankInput(throttle=0.7, rotate=self._recovery_direction * 0.4, fire=False,
                             turret_angle=turret)

    # ------------------------------------------------------------------
    # Pickup awareness helper (v0.20)
    # ------------------------------------------------------------------

    def _nearest_pickup(self, max_range: float, type_filter: str | None = None):
        """Return the nearest pickup within max_range, or None.

        Args:
            max_range: maximum distance in pixels.
            type_filter: if set, only consider pickups of this type.
        """
        if self._pickups_getter is None or self._owner is None:
            return None
        pickups = self._pickups_getter()
        if not pickups:
            return None
        best = None
        best_dist = max_range
        for p in pickups:
            if not p.is_alive:
                continue
            if type_filter and p.pickup_type != type_filter:
                continue
            d = distance(self._owner.position, p.position)
            if d < best_dist:
                best = p
                best_dist = d
        return best

    def _steer_toward(self, target_pos: tuple) -> TankInput:
        """Produce TankInput that drives toward a world position."""
        desired = angle_to(self._owner.position, target_pos)
        desired += self._obstacle_steer_correction(desired)
        diff = angle_difference(self._owner.angle, desired)
        rotate = 1.0 if diff > 5 else (-1.0 if diff < -5 else 0.0)
        throttle = 1.0 if abs(diff) < 45 else 0.3
        turret = self._owner.angle if self._owner else 0.0
        return TankInput(throttle=throttle, rotate=rotate, fire=False,
                         turret_angle=turret)

    # ------------------------------------------------------------------
    # Weapon awareness helpers (v0.34)
    # ------------------------------------------------------------------

    @property
    def _effective_attack_range(self) -> float:
        """Dynamic ATTACK-state trigger distance based on the equipped weapon.

        Returns the midpoint of the weapon's preferred distance band, clamped
        to AI_ATTACK_RANGE so the original state-machine boundary is never
        exceeded (existing tests stay green).
        """
        if self._owner is None:
            return AI_ATTACK_RANGE
        active_wep = getattr(self._owner, "active_weapon", None)
        if not isinstance(active_wep, dict):
            return AI_ATTACK_RANGE
        wtype = active_wep.get("type", "standard_shell")
        lo, hi = _RANGE_BOUNDS[get_weapon_profile(wtype)["preferred_range"]]
        return min((lo + hi) / 2.0, AI_ATTACK_RANGE)

    def _combo_bonus(self, weapon_type: str, target) -> float:
        """Return a [0, awareness] bonus when weapon_type would complete an elemental combo.

        Reads active combat effects on the target and checks whether firing
        weapon_type (which applies a specific damage type) would trigger any
        of the reactions in _ELEMENTAL_COMBOS.  Scaled by
        self._elemental_awareness so easy AI always returns 0.
        """
        if self._elemental_awareness <= 0.0:
            return 0.0
        dmg_type = _WEAPON_DAMAGE_TYPES.get(weapon_type, "")
        if not dmg_type:
            return 0.0
        active = set(getattr(target, "combat_effects", {}).keys()) if target else set()
        best = 0.0
        for combo in _ELEMENTAL_COMBOS:
            if combo["completes"] == dmg_type and combo["requires"] in active:
                best = max(best, combo["value"])
        return best * self._elemental_awareness

    def _setup_bonus(self, weapon_type: str, target) -> float:
        """Return a small bonus for establishing a first elemental effect on a clean target.

        If the target has no active combat effects and weapon_type applies an
        elemental effect, a setup bonus is granted so the AI prefers to start
        status-effect chains rather than only exploiting existing ones.
        Scaled by self._elemental_awareness.
        """
        if self._elemental_awareness <= 0.0:
            return 0.0
        dmg_type = _WEAPON_DAMAGE_TYPES.get(weapon_type, "")
        if not dmg_type:
            return 0.0
        if target is None:
            return 0.0
        active = set(getattr(target, "combat_effects", {}).keys())
        if dmg_type in active:
            return 0.0  # effect already applied — no setup value
        return 0.15 * self._elemental_awareness

    def _score_weapon_slot(self, slot_index: int, target, dist: float) -> float:
        """Return a utility score for equipping slot_index right now.

        Higher score = better fit for the current combat situation.
        Pure of any random — testable without mocking randomness.
        """
        if self._owner is None:
            return 0.0
        slots = getattr(self._owner, "weapon_slots", [])
        if slot_index >= len(slots):
            return 0.0
        slot = slots[slot_index]
        wtype = slot.get("type", "standard_shell") if isinstance(slot, dict) else "standard_shell"
        profile = get_weapon_profile(wtype)
        lo, hi = _RANGE_BOUNDS[profile["preferred_range"]]

        # Range fitness: 1.0 when dist is inside [lo, hi], decays linearly outside
        range_mid = (lo + hi) / 2.0
        range_half = max((hi - lo) / 2.0, 1.0)
        range_fitness = max(0.0, 1.0 - abs(dist - range_mid) / range_half)

        # Cooldown penalty: weapons on cooldown are less desirable
        cooldowns = getattr(self._owner, "slot_cooldowns", [])
        cd = cooldowns[slot_index] if slot_index < len(cooldowns) else 0.0
        cooldown_penalty = min(1.0, cd / 2.0)  # 2 s+ cooldown = full penalty

        # AoE bonus: prefer area weapons when the AI is healthy enough to stand firm
        aoe_bonus = 0.0
        owner_hp = getattr(self._owner, "health_ratio", 1.0)
        if wtype in ("grenade_launcher", "emp_blast") and owner_hp > 0.5:
            aoe_bonus = 0.15

        # Elemental bonuses (v0.36): combo completion + setup incentive
        combo = self._combo_bonus(wtype, target)
        setup = self._setup_bonus(wtype, target)

        score = range_fitness * (1.0 - cooldown_penalty) + aoe_bonus + combo + setup
        return min(2.0, max(0.0, score))

    def _select_best_weapon_slot(self) -> int:
        """Return the slot index with the highest utility score.

        Hysteresis of 0.05 prevents switching for marginal improvements.
        Returns the current active slot when no slot meaningfully beats it.
        """
        if self._owner is None:
            return 0
        target = self._target_getter()
        dist = distance(self._owner.position, target.position) if target else 400.0
        current = getattr(self._owner, "active_slot", 0)
        best_score = self._score_weapon_slot(current, target, dist)
        best_slot = current
        for i in range(len(getattr(self._owner, "weapon_slots", []))):
            s = self._score_weapon_slot(i, target, dist)
            if s > best_score + 0.05:
                best_score = s
                best_slot = i
        return best_slot

    # ------------------------------------------------------------------
    # Obstacle avoidance helper (Layer 3)
    # ------------------------------------------------------------------

    def _obstacle_steer_correction(self, desired_angle: float) -> float:
        """
        Return an angular correction (degrees) to nudge the desired heading
        away from an obstacle that is roughly in front of the tank.

        Algorithm:
          For each live obstacle within _LOOKAHEAD_PX of the tank:
            1. Find the nearest point on the obstacle rect to the tank center.
            2. Check if the bearing to that point is within ±90° of desired_angle
               (i.e., the obstacle blocks the intended travel direction).
            3. If so, compute a lateral correction that steers away from the
               obstacle center, scaled by proximity (closer → stronger nudge).
          All corrections are accumulated and capped at _STEER_ANGLE * 1.8 so
          that a symmetric corner — where two walls produce equal-and-opposite
          corrections — does not cancel out to zero.

        This is NOT pathfinding — it is a simple repulsion that prevents
        the AI from blindly walking into walls.  The stuck-recovery system
        catches cases this misses.
        """
        if self._obstacles_getter is None or self._owner is None:
            return 0.0

        obstacles = self._obstacles_getter()
        if not obstacles:
            return 0.0

        tx, ty = self._owner.position
        total_correction: float = 0.0
        _MAX_CORRECTION = _STEER_ANGLE * 1.8

        for obs in obstacles:
            if not obs.is_alive:
                continue

            rx, ry, rw, rh = obs.rect
            # Nearest point on the rect to the tank center
            nearest_x = max(rx, min(tx, rx + rw))
            nearest_y = max(ry, min(ty, ry + rh))
            dx = nearest_x - tx
            dy = nearest_y - ty
            dist = math.hypot(dx, dy)

            if dist == 0 or dist >= _LOOKAHEAD_PX:
                continue

            # Is the obstacle within ±90° of the *desired* heading?
            # (was ±70° of self._owner.angle — the wider cone and desired_angle
            # reference ensures corner walls are both detected when fleeing.)
            bearing = math.degrees(math.atan2(dy, dx))
            if abs(angle_difference(desired_angle, bearing)) > 90.0:
                continue

            # Steer away: obstacle to the right of desired_angle → correct left (negative)
            #             obstacle to the left of desired_angle  → correct right (positive)
            side = angle_difference(desired_angle, bearing)
            correction = -_STEER_ANGLE if side > 0 else _STEER_ANGLE

            # Scale by proximity: closer → stronger nudge
            scale = 1.0 - (dist / _LOOKAHEAD_PX)
            total_correction += correction * scale

        # Cap to prevent over-correction while still letting two same-side walls add up
        return max(-_MAX_CORRECTION, min(_MAX_CORRECTION, total_correction))
