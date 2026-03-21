"""
game/entities/pickup.py

Collectible pickup entity (health pack, ammo crate, speed boost).
Effect type and value defined in pickup config passed at spawn.
"""

import math

from game.utils.constants import SPEED_BOOST_DURATION
from game.utils.logger import get_logger

log = get_logger(__name__)


class Pickup:
    """
    A collectable item on the map. The CollisionSystem detects tank overlap
    and calls apply() to grant the effect.
    """

    def __init__(
        self,
        x: float,
        y: float,
        pickup_type: str,
        value: float,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.pickup_type: str = pickup_type   # e.g. "health", "ammo", "speed_boost"
        self.value: float = value
        self.is_alive: bool = True
        self.radius: float = 14.0
        self._pulse_timer: float = 0.0
        log.debug("Pickup spawned: type=%s value=%.1f at (%.0f, %.0f)", pickup_type, value, x, y)

    def apply(self, tank) -> None:
        """
        Apply this pickup's effect to a tank.
        Called by CollisionSystem when a tank overlaps this pickup.
        """
        if not self.is_alive:
            return
        if self.pickup_type == "health":
            tank.health = min(tank.health + self.value, tank.max_health)
        elif self.pickup_type == "ammo":
            tank._slot_cooldowns = [0.0] * len(tank._slot_cooldowns)
        elif self.pickup_type == "speed_boost":
            tank.apply_status("speed_boost", self.value, duration=SPEED_BOOST_DURATION)
        self.is_alive = False
        log.info("Pickup '%s' applied to %s", self.pickup_type, tank.tank_type)

    def update(self, dt: float) -> None:
        """Advance pulse animation timer."""
        self._pulse_timer += dt

    @property
    def pulse(self) -> float:
        """Smooth 0.0–1.0 oscillation for visual pulse effect."""
        return (math.sin(self._pulse_timer * 3.0) + 1.0) / 2.0

    @property
    def position(self) -> tuple:
        return (self.x, self.y)
