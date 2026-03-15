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
_RECOVERY_DURATION: float = 0.8  # seconds spent in reverse before resuming
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

        # Obstacle awareness — injected by the scene as a zero-arg callable
        # returning a list of live Obstacle instances.
        self._obstacles_getter = None

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

        # Count down recovery timer; resume state machine when it expires
        if self._state == AIState.RECOVERY:
            self._recovery_timer -= dt
            if self._recovery_timer <= 0.0:
                self._recovery_timer = 0.0
                # Alternate direction so the next recovery turns the other way
                self._recovery_direction *= -1.0
                # Reset to PATROL; _update_state will re-evaluate next get_input()
                self._state = AIState.PATROL
                self._stuck_detector.reset()
                log.debug(
                    "AI recovery complete — resuming state machine. "
                    "Next recovery direction: %.0f",
                    self._recovery_direction,
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

        # Stuck check — only in states where the AI is actively trying to move.
        # ATTACK deliberately stands still, so we exclude it to avoid false positives.
        if (
            self._stuck_detector.is_stuck
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
        """Wander by slowly rotating on a timer."""
        # Stub: just rotate slowly; waypoint patrol implemented later
        return TankInput(throttle=0.5, rotate=0.3, fire=False)

    def _pursue_input(self, target) -> TankInput:
        """Turn and move toward target with lightweight obstacle avoidance."""
        if self._owner is None or target is None:
            return TankInput()
        desired_angle = angle_to(self._owner.position, target.position)
        desired_angle += self._obstacle_steer_correction(desired_angle)
        diff = angle_difference(self._owner.angle, desired_angle)
        rotate = 1.0 if diff > 5 else (-1.0 if diff < -5 else 0.0)
        throttle = 1.0 if abs(diff) < 45 else 0.3
        return TankInput(throttle=throttle, rotate=rotate, fire=False)

    def _attack_input(self, target) -> TankInput:
        """Aim and fire; accuracy introduces angular jitter."""
        if self._owner is None or target is None:
            return TankInput()
        desired_angle = angle_to(self._owner.position, target.position)
        # Accuracy jitter: lower accuracy → larger random offset
        jitter = (1.0 - self.accuracy) * random.uniform(-30, 30)
        desired_angle += jitter
        diff = angle_difference(self._owner.angle, desired_angle)
        rotate = 1.0 if diff > 2 else (-1.0 if diff < -2 else 0.0)
        fire = abs(diff) < 10 and random.random() < self.aggression
        return TankInput(throttle=0.0, rotate=rotate, fire=fire)

    def _evade_input(self, target) -> TankInput:
        """Retreat away from the target with lightweight obstacle avoidance."""
        if self._owner is None or target is None:
            return TankInput(throttle=-1.0, rotate=0.5, fire=False)
        # Flee direction is the opposite of the bearing to the target
        flee_angle = angle_to(self._owner.position, target.position) + 180.0
        flee_angle += self._obstacle_steer_correction(flee_angle)
        diff = angle_difference(self._owner.angle, flee_angle)
        rotate = 1.0 if diff > 5 else (-1.0 if diff < -5 else 0.0)
        return TankInput(throttle=1.0, rotate=rotate, fire=False)

    def _recovery_input(self) -> TankInput:
        """Reverse + rotate to break free from whatever the tank is stuck against."""
        return TankInput(throttle=-1.0, rotate=self._recovery_direction, fire=False)

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
            2. Check if the bearing to that point is within ±70° of the tank's
               current heading (i.e., the obstacle is ahead of us).
            3. If so, compute a lateral correction that steers away from the
               obstacle center, scaled by proximity (closer → stronger nudge).
          Returns the first significant correction found; 0.0 if none.

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

            # Is the obstacle in the forward arc? (within ±70° of current heading)
            bearing = math.degrees(math.atan2(dy, dx))
            if abs(angle_difference(self._owner.angle, bearing)) > 70.0:
                continue

            # Steer away: obstacle to the right of desired_angle → correct left (negative)
            #             obstacle to the left of desired_angle  → correct right (positive)
            side = angle_difference(desired_angle, bearing)
            correction = -_STEER_ANGLE if side > 0 else _STEER_ANGLE

            # Scale by proximity: closer → stronger nudge
            scale = 1.0 - (dist / _LOOKAHEAD_PX)
            return correction * scale

        return 0.0
