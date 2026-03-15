"""
game/entities/pickup.py

Collectible pickup entity (health pack, ammo, shield, etc.).
Effect type and value defined in pickup config passed at spawn.
"""

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
        self.pickup_type: str = pickup_type   # e.g. "health", "ammo", "shield"
        self.value: float = value
        self.is_alive: bool = True
        log.debug("Pickup spawned: type=%s value=%.1f at (%.0f, %.0f)", pickup_type, value, x, y)

    def apply(self, tank) -> None:
        """
        Apply this pickup's effect to a tank.
        Called by CollisionSystem when a tank overlaps this pickup.
        """
        if not self.is_alive:
            return
        # TODO: dispatch effect based on pickup_type when entity systems are live
        log.info("Pickup '%s' applied to tank at (%.0f, %.0f)", self.pickup_type, tank.x, tank.y)
        self.is_alive = False

    @property
    def position(self) -> tuple:
        return (self.x, self.y)
