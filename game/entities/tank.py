"""
game/entities/tank.py

Tank entity. Fully controller-agnostic — has zero awareness of whether it is
driven by a human (InputHandler) or an AI (AIController).

A controller is injected at instantiation and must implement:
    get_input() -> TankInput
"""

from dataclasses import dataclass, field
from typing import Protocol

from game.utils.constants import (
    DEFAULT_FIRE_RATE,
    DEFAULT_TANK_HEALTH,
    DEFAULT_TANK_SPEED,
    DEFAULT_TANK_TURN_RATE,
)
from game.utils.logger import get_logger
from game.utils.math_utils import clamp, heading_to_vec

log = get_logger(__name__)


@dataclass
class TankInput:
    """
    Normalized control intent produced by any controller.
    Values are in [-1, 1] for axes; booleans for discrete actions.
    turret_angle is set by the controller each frame — the tank applies it
    directly so the controller fully owns where the gun is pointing.
    """
    throttle: float = 0.0       # -1 = full reverse, +1 = full forward
    rotate: float = 0.0         # -1 = rotate left, +1 = rotate right
    fire: bool = False
    turret_angle: float = 0.0   # desired turret facing (degrees, pygame CW convention)


class ControllerProtocol(Protocol):
    """Interface that all tank controllers must satisfy."""

    def get_input(self) -> TankInput:
        """Return the current control intent for one frame."""
        ...


class Tank:
    """
    Represents a tank entity.

    Config (from tanks.yaml) is passed as a dict at construction.
    The controller is assigned externally and can be swapped at runtime.
    """

    def __init__(
        self,
        x: float,
        y: float,
        config: dict,
        controller: ControllerProtocol,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.angle: float = 0.0          # hull facing angle in degrees (0 = right)
        self.turret_angle: float = 0.0   # turret/gun facing — independent of hull
        self.controller = controller

        # Stats from config — fall back to defaults if key missing
        self.speed: float = float(config.get("speed", DEFAULT_TANK_SPEED))
        self.max_health: int = int(config.get("health", DEFAULT_TANK_HEALTH))
        self.health: int = self.max_health
        self.turn_rate: float = float(config.get("turn_rate", DEFAULT_TANK_TURN_RATE))
        self.fire_rate: float = float(config.get("fire_rate", DEFAULT_FIRE_RATE))

        self._fire_cooldown: float = 0.0
        self.is_alive: bool = True
        self.tank_type: str = config.get("type", "unknown")

        # World-space velocity vector (pixels/second).
        # Computed at the end of update() from the movement delta this frame.
        self.vx: float = 0.0
        self.vy: float = 0.0

        log.debug(
            "Tank created at (%.0f, %.0f) type=%s hp=%d spd=%.0f",
            x, y, self.tank_type, self.max_health, self.speed,
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> list:
        """
        Advance tank state by dt seconds. Returns a list of events
        (e.g., [("fire", x, y, angle)]) for systems to consume.

        Caller is responsible for collision response after this call.
        """
        if not self.is_alive:
            return []

        events = []
        intent = self.controller.get_input()

        # Turret tracks whatever the controller requests (instant snap for now)
        self.turret_angle = intent.turret_angle

        # Hull rotation
        self.angle += intent.rotate * self.turn_rate * dt

        # Movement along facing direction
        prev_x, prev_y = self.x, self.y
        dx, dy = heading_to_vec(self.angle)
        self.x += dx * intent.throttle * self.speed * dt
        self.y += dy * intent.throttle * self.speed * dt

        # Velocity (world-space px/s) — used by CollisionSystem for damage scaling
        if dt > 0:
            self.vx = (self.x - prev_x) / dt
            self.vy = (self.y - prev_y) / dt

        # Fire cooldown
        if self._fire_cooldown > 0:
            self._fire_cooldown -= dt

        if intent.fire and self._fire_cooldown <= 0:
            self._fire_cooldown = 1.0 / self.fire_rate
            events.append(("fire", self.x, self.y, self.turret_angle))
            log.debug("Tank fired at turret_angle %.1f", self.turret_angle)

        return events

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------

    def take_damage(self, amount: int) -> None:
        """Apply damage. Sets is_alive=False when health reaches 0."""
        if not self.is_alive:
            return
        self.health = clamp(self.health - amount, 0, self.max_health)
        log.debug("Tank took %d damage, hp=%d/%d", amount, self.health, self.max_health)
        if self.health <= 0:
            self.is_alive = False
            log.info("Tank destroyed (type=%s)", self.tank_type)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def position(self) -> tuple:
        return (self.x, self.y)

    @property
    def health_ratio(self) -> float:
        return self.health / self.max_health if self.max_health > 0 else 0.0
