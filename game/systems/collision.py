"""
game/systems/collision.py

CollisionSystem — detects and resolves all entity interactions.

Collision pairs handled:
  - Bullet  ↔ Tank     (damage)
  - Bullet  ↔ Obstacle (bounce or destroy)
  - Tank    ↔ Obstacle (push back)
  - Tank    ↔ Pickup   (apply effect)
"""

import math

from game.utils.logger import get_logger

log = get_logger(__name__)

# Radii used for circle-based collision approximations
TANK_RADIUS: float = 22.0
BULLET_RADIUS: float = 5.0
PICKUP_RADIUS: float = 14.0


class CollisionSystem:
    """
    Pure-logic collision detection and response.
    No rendering code. Operates on entity position attributes directly.
    """

    def __init__(self) -> None:
        log.debug("CollisionSystem initialized.")

    def update(self, tanks: list, bullets: list, obstacles: list, pickups: list) -> None:
        """
        Run all collision checks for the current frame.
        Called once per frame from GameplayScene.update().
        """
        self._bullets_vs_tanks(bullets, tanks)
        self._bullets_vs_obstacles(bullets, obstacles)
        self._tanks_vs_obstacles(tanks, obstacles)
        self._tanks_vs_pickups(tanks, pickups)

    # ------------------------------------------------------------------
    # Collision pair handlers
    # ------------------------------------------------------------------

    def _bullets_vs_tanks(self, bullets: list, tanks: list) -> None:
        for bullet in bullets:
            if not bullet.is_alive:
                continue
            for tank in tanks:
                if not tank.is_alive or tank is bullet.owner:
                    continue
                if self._circles_overlap(bullet.position, BULLET_RADIUS, tank.position, TANK_RADIUS):
                    tank.take_damage(bullet.damage)
                    bullet.destroy()
                    log.debug(
                        "Bullet hit tank. Damage=%d, Tank HP=%d",
                        bullet.damage, tank.health,
                    )
                    break

    def _bullets_vs_obstacles(self, bullets: list, obstacles: list) -> None:
        for bullet in bullets:
            if not bullet.is_alive:
                continue
            for obs in obstacles:
                if not obs.is_alive:
                    continue
                if self._circle_vs_rect(bullet.position, BULLET_RADIUS, obs.rect):
                    if obs.reflective and bullet.bounces_remaining > 0:
                        # TODO: calculate reflection vector in a later milestone
                        bullet.bounces_remaining -= 1
                        log.debug("Bullet reflected by obstacle.")
                    else:
                        bullet.destroy()
                        if obs.destructible:
                            obs.destroy()
                    break

    def _tanks_vs_obstacles(self, tanks: list, obstacles: list) -> None:
        for tank in tanks:
            if not tank.is_alive:
                continue
            for obs in obstacles:
                if not obs.is_alive:
                    continue
                if self._circle_vs_rect(tank.position, TANK_RADIUS, obs.rect):
                    # TODO: push tank out of obstacle in a later milestone
                    pass

    def _tanks_vs_pickups(self, tanks: list, pickups: list) -> None:
        for tank in tanks:
            if not tank.is_alive:
                continue
            for pickup in pickups:
                if not pickup.is_alive:
                    continue
                if self._circles_overlap(tank.position, TANK_RADIUS, pickup.position, PICKUP_RADIUS):
                    pickup.apply(tank)

    # ------------------------------------------------------------------
    # Geometry helpers (pure math — testable in isolation)
    # ------------------------------------------------------------------

    @staticmethod
    def circles_overlap(pos_a: tuple, r_a: float, pos_b: tuple, r_b: float) -> bool:
        """Return True if two circles overlap. Public alias for tests."""
        return CollisionSystem._circles_overlap(pos_a, r_a, pos_b, r_b)

    @staticmethod
    def _circles_overlap(pos_a: tuple, r_a: float, pos_b: tuple, r_b: float) -> bool:
        dx = pos_b[0] - pos_a[0]
        dy = pos_b[1] - pos_a[1]
        dist_sq = dx * dx + dy * dy
        return dist_sq < (r_a + r_b) ** 2

    @staticmethod
    def circle_vs_rect(circle_pos: tuple, radius: float, rect: tuple) -> bool:
        """Return True if a circle overlaps an axis-aligned rectangle. Public alias for tests."""
        return CollisionSystem._circle_vs_rect(circle_pos, radius, rect)

    @staticmethod
    def _circle_vs_rect(circle_pos: tuple, radius: float, rect: tuple) -> bool:
        cx, cy = circle_pos
        rx, ry, rw, rh = rect
        # Find closest point on rect to circle center
        closest_x = max(rx, min(cx, rx + rw))
        closest_y = max(ry, min(cy, ry + rh))
        dx = cx - closest_x
        dy = cy - closest_y
        return (dx * dx + dy * dy) < (radius * radius)
