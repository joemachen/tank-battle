"""
game/entities/bullet.py

Bullet entity. Fired by tanks; consumed by CollisionSystem.
Weapon stats come from weapons.yaml config.
"""

import math

from game.utils.constants import BULLET_DEFAULT_MAX_RANGE, DEFAULT_BULLET_SPEED
from game.utils.logger import get_logger
from game.utils.math_utils import heading_to_vec

log = get_logger(__name__)


class Bullet:
    """
    A projectile in motion. Moves along a fixed heading each frame.
    The CollisionSystem is responsible for hit detection and destruction.
    """

    def __init__(
        self,
        x: float,
        y: float,
        angle: float,
        owner,                     # Tank reference — used to avoid self-hit
        config: dict,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.angle: float = angle
        self.owner = owner
        self.is_alive: bool = True

        # Stats from weapon config
        self.speed: float = float(config.get("speed", DEFAULT_BULLET_SPEED))
        self.damage: int = int(config.get("damage", 20))
        self.max_bounces: int = int(config.get("max_bounces", 0))
        self.bounces_remaining: int = self.max_bounces
        self.max_range: float = float(config.get("max_range", BULLET_DEFAULT_MAX_RANGE))
        self.weapon_type: str = config.get("type", "standard_shell")

        self._dx, self._dy = heading_to_vec(self.angle)
        self._distance_traveled: float = 0.0
        log.debug("Bullet spawned at (%.0f, %.0f) angle=%.1f type=%s", x, y, angle, self.weapon_type)

    def update(self, dt: float) -> None:
        """Advance bullet position; despawn if max_range exceeded."""
        if not self.is_alive:
            return
        step = self.speed * dt
        self.x += self._dx * step
        self.y += self._dy * step
        self._distance_traveled += step
        if self._distance_traveled >= self.max_range:
            self.destroy()

    def reflect(self, normal_x: float, normal_y: float) -> None:
        """
        Reflect velocity off a surface with the given unit normal.
        Uses standard reflection formula: v' = v - 2(v·n)n.
        Decrements bounces_remaining and updates heading angle.

        normal_x, normal_y represent the axis to reflect over:
          (1, 0) → invert _dx  (vertical surface: left/right face)
          (0, 1) → invert _dy  (horizontal surface: top/bottom face)
        """
        dot = self._dx * normal_x + self._dy * normal_y
        self._dx -= 2.0 * dot * normal_x
        self._dy -= 2.0 * dot * normal_y
        self.angle = math.degrees(math.atan2(self._dy, self._dx))
        self.bounces_remaining -= 1
        log.debug(
            "Bullet reflected. bounces_remaining=%d new_angle=%.1f",
            self.bounces_remaining, self.angle,
        )

    def destroy(self) -> None:
        """Mark bullet for removal by CollisionSystem."""
        self.is_alive = False

    @property
    def position(self) -> tuple:
        return (self.x, self.y)
