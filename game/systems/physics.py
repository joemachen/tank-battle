"""
game/systems/physics.py

PhysicsSystem — applies movement updates and enforces arena bounds.
Does NOT handle collision response between entities; that belongs to CollisionSystem.
"""

from game.utils.constants import ARENA_HEIGHT, ARENA_PADDING, ARENA_WIDTH, TANK_MOVEMENT_MARGIN
from game.utils.logger import get_logger

log = get_logger(__name__)


class PhysicsSystem:
    """
    Responsible for:
      - Advancing bullet positions
      - Clamping tanks to arena bounds
      - Arena boundary interaction (reflect bullets, block tanks)
    """

    def __init__(self) -> None:
        log.debug("PhysicsSystem initialized.")

    def update(self, dt: float, tanks: list, bullets: list) -> None:
        """
        Advance all movable entities by dt seconds and apply boundary rules.
        Called once per frame from GameplayScene.update().
        """
        for bullet in bullets:
            if bullet.is_alive:
                bullet.update(dt)
                self._check_bullet_boundary(bullet)

        for tank in tanks:
            if tank.is_alive:
                self._clamp_tank(tank)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clamp_tank(self, tank) -> None:
        """Keep tank within the playable arena (world space).

        TANK_MOVEMENT_MARGIN = tank bounding-circle radius (25px) + border thickness (4px).
        This stops the tank's visible hull at the visual wall rather than ARENA_PADDING (32px)
        inside it, which caused the invisible-wall bug.
        ARENA_PADDING is intentionally left unchanged — it is the spawn margin, not this.
        """
        tank.x = max(TANK_MOVEMENT_MARGIN, min(ARENA_WIDTH - TANK_MOVEMENT_MARGIN, tank.x))
        tank.y = max(TANK_MOVEMENT_MARGIN, min(ARENA_HEIGHT - TANK_MOVEMENT_MARGIN, tank.y))

    def _check_bullet_boundary(self, bullet) -> None:
        """Destroy bullet (or bounce, if supported) when it leaves the arena."""
        out_x = bullet.x < 0 or bullet.x > ARENA_WIDTH
        out_y = bullet.y < 0 or bullet.y > ARENA_HEIGHT

        if out_x or out_y:
            if bullet.bounces_remaining > 0:
                # TODO: implement reflect logic in a later milestone
                bullet.bounces_remaining -= 1
                log.debug("Bullet bounced off boundary. Remaining: %d", bullet.bounces_remaining)
            else:
                bullet.destroy()
