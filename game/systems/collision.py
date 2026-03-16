"""
game/systems/collision.py

CollisionSystem — detects and resolves all entity interactions.

Collision pairs handled:
  - Bullet  ↔ Tank     (damage)
  - Bullet  ↔ Obstacle (bounce or destroy)
  - Tank    ↔ Obstacle (push back)
  - Tank    ↔ Tank     (push back + collision damage)
  - Tank    ↔ Pickup   (apply effect)
"""

import math

from game.utils.constants import (
    COLLISION_DAMAGE_FRONT,
    COLLISION_DAMAGE_REAR,
    COLLISION_DAMAGE_SIDE,
    COLLISION_SPEED_CAP,
    COLLISION_SPEED_SCALE,
)
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
        self._tanks_vs_tanks(tanks)
        self._tanks_vs_pickups(tanks, pickups)

    # ------------------------------------------------------------------
    # Collision pair handlers
    # ------------------------------------------------------------------

    def check_bullet_vs_tank(self, bullet, tank) -> bool:
        """
        Check if a single bullet has hit a single tank and apply damage if so.
        Returns True if a hit occurred (bullet destroyed, tank damaged).

        Signature is v0.4-ready: GameplayScene will call this individually for
        each (player_bullet, ai_tank) and (ai_bullet, player_tank) pair once
        AI opponents exist. Currently invoked in batch via _bullets_vs_tanks().
        """
        if not bullet.is_alive or not tank.is_alive or tank is bullet.owner:
            return False
        if self._circles_overlap(bullet.position, BULLET_RADIUS, tank.position, TANK_RADIUS):
            tank.take_damage(bullet.damage)
            bullet.destroy()
            log.debug("Bullet hit tank. Damage=%d, Tank HP=%d", bullet.damage, tank.health)
            return True
        return False

    def _bullets_vs_tanks(self, bullets: list, tanks: list) -> None:
        for bullet in bullets:
            if not bullet.is_alive:
                continue
            for tank in tanks:
                if self.check_bullet_vs_tank(bullet, tank):
                    break

    def _bullets_vs_obstacles(self, bullets: list, obstacles: list) -> None:
        for bullet in bullets:
            if not bullet.is_alive:
                continue
            for obs in obstacles:
                if not obs.is_alive:
                    continue
                if self._circle_vs_rect(bullet.position, BULLET_RADIUS, obs.rect):
                    if bullet.bounces_remaining > 0:
                        # obs.reflective reserved for future non-reflective surface variant.
                        # Bouncing bullets still transfer kinetic energy to the obstacle.
                        obs.take_damage(bullet.damage, damage_type="standard")
                        self._reflect_bullet(bullet, obs)
                    else:
                        bullet.destroy()
                        obs.take_damage(bullet.damage, damage_type="standard")
                    break

    def _reflect_bullet(self, bullet, obs) -> None:
        """
        Reflect a bouncing bullet off the face of an obstacle it has entered.

        Determines the hit face from the overlap geometry:
          - bullet x inside rect x-range → hit top or bottom face → invert _dy
          - bullet y inside rect y-range → hit left or right face → invert _dx
          - corner overlap → reflect along the axis with smaller penetration
        """
        bx, by = bullet.position
        rx, ry, rw, rh = obs.rect

        closest_x = max(rx, min(bx, rx + rw))
        closest_y = max(ry, min(by, ry + rh))
        dx = bx - closest_x   # 0 when bullet x is inside rect x-range
        dy = by - closest_y   # 0 when bullet y is inside rect y-range

        if dx == 0 and dy == 0:
            # Bullet center fully inside rect — push out along nearest face
            dist_to_left = bx - rx
            dist_to_right = (rx + rw) - bx
            dist_to_top = by - ry
            dist_to_bottom = (ry + rh) - by
            if min(dist_to_left, dist_to_right) < min(dist_to_top, dist_to_bottom):
                bullet.reflect(1.0, 0.0)   # nearest face is vertical (left/right) → invert _dx
            else:
                bullet.reflect(0.0, 1.0)   # nearest face is horizontal (top/bottom) → invert _dy
        elif dx == 0:
            # Bullet x is within rect x-range → approached from top or bottom → invert _dy
            bullet.reflect(0.0, 1.0)
        elif dy == 0:
            # Bullet y is within rect y-range → approached from left or right → invert _dx
            bullet.reflect(1.0, 0.0)
        else:
            # Corner approach — reflect off the axis with the smaller gap (nearer face)
            if abs(dx) < abs(dy):
                bullet.reflect(1.0, 0.0)   # nearer to vertical face (left/right) → invert _dx
            else:
                bullet.reflect(0.0, 1.0)   # nearer to horizontal face (top/bottom) → invert _dy

    def _tanks_vs_obstacles(self, tanks: list, obstacles: list) -> None:
        for tank in tanks:
            if not tank.is_alive:
                continue
            for obs in obstacles:
                if not obs.is_alive:
                    continue
                if self._circle_vs_rect(tank.position, TANK_RADIUS, obs.rect):
                    self._push_tank_out(tank, obs)

    def _push_tank_out(self, tank, obs) -> None:
        """
        Reposition tank so it no longer overlaps the obstacle.

        When the tank center is outside the rect, push along the overlap
        vector (closest-point → center) by the penetration depth.
        When the center is inside the rect, push out along the nearest face.
        """
        tx, ty = tank.x, tank.y
        rx, ry, rw, rh = obs.rect

        closest_x = max(rx, min(tx, rx + rw))
        closest_y = max(ry, min(ty, ry + rh))
        dx = tx - closest_x
        dy = ty - closest_y
        dist_sq = dx * dx + dy * dy

        if dist_sq > 0:
            # Center outside rect — push along overlap vector
            dist = math.sqrt(dist_sq)
            penetration = TANK_RADIUS - dist
            tank.x += (dx / dist) * penetration
            tank.y += (dy / dist) * penetration
        else:
            # Center inside rect — push out to nearest face
            overlap_left = tx - rx
            overlap_right = (rx + rw) - tx
            overlap_top = ty - ry
            overlap_bottom = (ry + rh) - ty
            min_ov = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
            if min_ov == overlap_left:
                tank.x = rx - TANK_RADIUS
            elif min_ov == overlap_right:
                tank.x = rx + rw + TANK_RADIUS
            elif min_ov == overlap_top:
                tank.y = ry - TANK_RADIUS
            else:
                tank.y = ry + rh + TANK_RADIUS

    def _tanks_vs_tanks(self, tanks: list) -> None:
        """
        Check every unique tank pair for overlap, push them apart, and apply
        collision damage to both.

        Only live tanks participate.  Damage is zero if relative speed is
        effectively zero (a slow nudge still scores 1 point via the floor).
        """
        alive = [t for t in tanks if t.is_alive]
        for i in range(len(alive)):
            for j in range(i + 1, len(alive)):
                a, b = alive[i], alive[j]
                dist_sq = (b.x - a.x) ** 2 + (b.y - a.y) ** 2
                combined = TANK_RADIUS * 2
                if dist_sq >= combined * combined:
                    continue  # no overlap
                self._push_tanks_apart(a, b, dist_sq, combined)
                self._apply_tank_collision_damage(a, b)

    def _push_tanks_apart(self, a, b, dist_sq: float, combined_r: float) -> None:
        """Push two overlapping tanks symmetrically along their separation axis."""
        dist = math.sqrt(dist_sq) if dist_sq > 0 else 0.001
        nx = (b.x - a.x) / dist
        ny = (b.y - a.y) / dist
        penetration = combined_r - dist
        half = penetration / 2.0
        a.x -= nx * half
        a.y -= ny * half
        b.x += nx * half
        b.y += ny * half

    def _apply_tank_collision_damage(self, a, b) -> None:
        """
        Calculate and apply bidirectional collision damage.

        For each tank, determine whether the *other* tank is hitting it from
        the front, side, or rear based on the angle between the struck tank's
        facing direction and the vector from the struck tank → striking tank.

        Both tanks take damage: the struck tank takes full base damage, the
        striking tank takes half (ramming costs you too).

        Relative speed scales the damage, capped to prevent one-shot kills.
        """
        # Relative speed = magnitude of velocity difference (px/s)
        rel_vx = a.vx - b.vx
        rel_vy = a.vy - b.vy
        rel_speed = math.hypot(rel_vx, rel_vy)
        speed_factor = min(rel_speed / COLLISION_SPEED_SCALE, COLLISION_SPEED_CAP)

        # Compute base damage for both impact directions
        dmg_on_b = self._impact_damage(a, b)   # a is the striker, b is struck
        dmg_on_a = self._impact_damage(b, a)   # b is the striker, a is struck

        # Apply with speed scaling; floor at 1
        b.take_damage(max(1, int(dmg_on_b * speed_factor)))
        a.take_damage(max(1, int(dmg_on_a * speed_factor)))

        log.debug(
            "Tank collision: speed_factor=%.2f  dmg_on_a=%d  dmg_on_b=%d",
            speed_factor, dmg_on_a, dmg_on_b,
        )

    @staticmethod
    def _impact_damage(striker, struck) -> int:
        """
        Base damage dealt TO struck FROM striker.

        Impact angle = angle between struck's facing vector and the vector
        from struck → striker.  Small angle = head-on front hit (low damage);
        90° = T-bone (high damage); 180° = rear-end (medium damage).
        """
        # Vector from struck → striker
        dx = striker.x - struck.x
        dy = striker.y - struck.y
        bearing = math.degrees(math.atan2(dy, dx))

        # Difference from struck tank's facing angle
        diff = abs((bearing - struck.angle + 180) % 360 - 180)

        if diff <= 45.0:
            return COLLISION_DAMAGE_FRONT
        elif diff <= 135.0:
            return COLLISION_DAMAGE_SIDE
        else:
            return COLLISION_DAMAGE_REAR

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
