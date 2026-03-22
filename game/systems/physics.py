"""
game/systems/physics.py

PhysicsSystem — applies movement updates and enforces arena bounds.
Does NOT handle collision response between entities; that belongs to CollisionSystem.
"""

import math

from game.utils.constants import ARENA_HEIGHT, ARENA_WIDTH, TANK_MOVEMENT_MARGIN
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
        """Reflect or destroy bullet when it leaves the arena.

        Bouncing bullets reflect off arena edges (invert _dx/_dy as needed).
        Corner hits (both axes out) reflect both in a single bounce.
        Non-bouncing bullets are destroyed on contact.
        """
        out_left = bullet.x < 0
        out_right = bullet.x > ARENA_WIDTH
        out_top = bullet.y < 0
        out_bottom = bullet.y > ARENA_HEIGHT

        if not (out_left or out_right or out_top or out_bottom):
            return

        if bullet.bounces_remaining > 0:
            if out_left or out_right:
                bullet._dx = -bullet._dx
            if out_top or out_bottom:
                bullet._dy = -bullet._dy
            bullet.angle = math.degrees(math.atan2(bullet._dy, bullet._dx))
            bullet.bounces_remaining -= 1
            bullet.x = max(0, min(ARENA_WIDTH, bullet.x))
            bullet.y = max(0, min(ARENA_HEIGHT, bullet.y))
            log.debug("Bullet reflected off arena wall. Remaining: %d", bullet.bounces_remaining)
        else:
            bullet.destroy()
