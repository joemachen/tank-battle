"""
game/systems/ai_controller.py

AIController — state machine AI for enemy tanks.

States:
  PATROL  — wanders when player is out of detection range
  PURSUE  — moves toward player when detected
  ATTACK  — fires when in range and has line of sight
  EVADE   — retreats when health is critically low

All difficulty parameters (reaction_time, accuracy, aggression,
evasion_threshold) are loaded from ai_difficulty.yaml — nothing
is hardcoded here.

The Tank class calls get_input() identically to InputHandler.
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

log = get_logger(__name__)


class AIState(Enum):
    PATROL = auto()
    PURSUE = auto()
    ATTACK = auto()
    EVADE = auto()


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

        log.debug(
            "AIController created. Difficulty: reaction=%.2f acc=%.2f agg=%.2f evade_thresh=%.2f",
            self.reaction_time, self.accuracy, self.aggression, self.evasion_threshold,
        )

    def set_owner(self, tank) -> None:
        """Called by the game when the AI tank is created so the controller can read self state."""
        self._owner = tank

    def get_input(self) -> TankInput:
        """
        Evaluate current state and return control intent for this frame.
        The reaction_time delay means the AI does not respond instantly.
        """
        # Reaction delay — AI input is only re-evaluated after reaction_time seconds
        # For now, always re-evaluate (timer tracked but state always computed)
        # TODO: gate state transitions behind reaction_timer in a later milestone

        target = self._target_getter()
        self._update_state(target)

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

        prev_state = self._state

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

    # ------------------------------------------------------------------
    # Per-state input producers
    # ------------------------------------------------------------------

    def _patrol_input(self) -> TankInput:
        """Wander by slowly rotating on a timer."""
        # Stub: just rotate slowly; waypoint patrol implemented later
        return TankInput(throttle=0.5, rotate=0.3, fire=False)

    def _pursue_input(self, target) -> TankInput:
        """Turn and move toward target."""
        if self._owner is None or target is None:
            return TankInput()
        desired_angle = angle_to(self._owner.position, target.position)
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
        """Retreat away from the target."""
        if self._owner is None or target is None:
            return TankInput(throttle=-1.0, rotate=0.5, fire=False)
        # Move away — reverse direction toward target
        desired_angle = angle_to(self._owner.position, target.position) + 180
        diff = angle_difference(self._owner.angle, desired_angle)
        rotate = 1.0 if diff > 5 else (-1.0 if diff < -5 else 0.0)
        return TankInput(throttle=1.0, rotate=rotate, fire=False)
