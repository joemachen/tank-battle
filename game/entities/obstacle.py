"""
game/entities/obstacle.py

Static map obstacle. Blocks movement and (optionally) reflects bullets.
"""

from game.utils.logger import get_logger

log = get_logger(__name__)


class Obstacle:
    """
    A rectangular static obstacle on the map.
    CollisionSystem uses rect for intersection tests.
    """

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        destructible: bool = False,
        reflective: bool = False,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.width: float = width
        self.height: float = height
        self.destructible: bool = destructible
        self.reflective: bool = reflective
        self.is_alive: bool = True

    @property
    def rect(self) -> tuple:
        """(x, y, width, height) — used by CollisionSystem."""
        return (self.x, self.y, self.width, self.height)

    def destroy(self) -> None:
        if self.destructible:
            self.is_alive = False
            log.debug("Obstacle destroyed at (%.0f, %.0f)", self.x, self.y)
