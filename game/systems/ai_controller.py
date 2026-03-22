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
            return self._patrol_input()
        elif self._state == AIState.PURSUE:
            return self._pursue_input(target)
        elif self._state == AIState.ATTACK:
            return self._attack_input(target)
        elif self._state == AIState.EVADE:
            return self._evade_input(target)
        return TankInput()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _update_state(self, target) -> None:
        if self._owner is None or target is None or not target.is_alive:
            self._transition(AIState.PATROL)
            return

        dist = distance(self._owner.position, target.position)
        health_ratio = self._owner.health_ratio if self._owner else 1.0

        if health_ratio <= self.evasion_threshold:
            self._transition(AIState.EVADE)
        elif dist <= AI_ATTACK_RANGE:
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
        """Wander by slowly rotating on a timer. Turret faces same direction as hull.
        Opportunistically grabs nearby pickups within AI_PICKUP_OPPORTUNISTIC_RANGE."""
        # Opportunistic pickup grab
        pickup = self._nearest_pickup(AI_PICKUP_OPPORTUNISTIC_RANGE)
        if pickup is not None:
            return self._steer_toward(pickup.position)
        # Stub: just rotate slowly; waypoint patrol implemented later
        turret = self._owner.angle if self._owner is not None else 0.0
        return TankInput(throttle=0.5, rotate=0.3, fire=False, turret_angle=turret)

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
        """Aim and fire; accuracy introduces angular jitter. Turret points at target."""
        if self._owner is None or target is None:
            return TankInput()
        desired_angle = angle_to(self._owner.position, target.position)
        # Accuracy jitter: lower accuracy → larger random offset
        jitter = (1.0 - self.accuracy) * random.uniform(-30, 30)
        desired_angle += jitter
        # Turret snaps to the jittered aim angle
        turret_angle = desired_angle
        diff = angle_difference(self._owner.angle, desired_angle)
        rotate = 1.0 if diff > 2 else (-1.0 if diff < -2 else 0.0)
        fire = abs(diff) < 10 and random.random() < self.aggression
        return TankInput(throttle=0.0, rotate=rotate, fire=fire,
                         turret_angle=turret_angle)

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
