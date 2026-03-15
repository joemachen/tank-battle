"""
game/entities/bullet.py

Bullet entity. Fired by tanks; consumed by CollisionSystem.
Weapon stats come from weapons.yaml config.
"""

from game.utils.constants import DEFAULT_BULLET_SPEED
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
        self.weapon_type: str = config.get("type", "standard_shell")

        self._dx, self._dy = heading_to_vec(self.angle)
        log.debug("Bullet spawned at (%.0f, %.0f) angle=%.1f type=%s", x, y, angle, self.weapon_type)

    def update(self, dt: float) -> None:
        """Advance bullet position."""
        if not self.is_alive:
            return
        self.x += self._dx * self.speed * dt
        self.y += self._dy * self.speed * dt

    def destroy(self) -> None:
        """Mark bullet for removal by CollisionSystem."""
        self.is_alive = False

    @property
    def position(self) -> tuple:
        return (self.x, self.y)
