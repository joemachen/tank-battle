"""
game/systems/raycast.py

Raycast — finds the first entity a line from (x, y) at angle hits.
Used by the laser beam weapon for instant hitscan damage.
"""

import math

from game.utils.logger import get_logger

log = get_logger(__name__)


def cast_ray(
    origin_x: float,
    origin_y: float,
    angle_deg: float,
    max_range: float,
    tanks: list,
    obstacles: list,
    ignore_tank=None,
) -> dict:
    """
    Cast a ray from origin along angle_deg and find the nearest intersection.

    Args:
        origin_x, origin_y: ray start position (world space)
        angle_deg: direction in degrees (pygame CW convention)
        max_range: maximum ray length in pixels
        tanks: list of Tank entities to test
        obstacles: list of Obstacle entities to test
        ignore_tank: tank to skip (the firer)

    Returns:
        dict with keys:
            "hit":      bool — True if something was hit
            "hit_type": "tank" | "obstacle" | "none"
            "entity":   the hit entity (Tank or Obstacle) or None
            "hit_x", "hit_y": impact point (world space)
            "distance": distance from origin to impact
            "end_x", "end_y": ray endpoint (impact or max-range tip)
    """
    rad = math.radians(angle_deg)
    dx = math.cos(rad)
    dy = math.sin(rad)

    nearest_dist = max_range
    nearest_hit = None
    nearest_type = "none"

    # Test against obstacles (line vs AABB)
    for obs in obstacles:
        if not obs.is_alive:
            continue
        result = _line_vs_aabb(origin_x, origin_y, dx, dy, nearest_dist,
                                obs.x, obs.y, obs.width, obs.height)
        if result is not None and result < nearest_dist:
            nearest_dist = result
            nearest_hit = obs
            nearest_type = "obstacle"

    # Test against tanks (line vs circle)
    # Import here to avoid circular import at module level
    from game.systems.collision import TANK_RADIUS
    for tank in tanks:
        if not tank.is_alive or tank is ignore_tank:
            continue
        result = _line_vs_circle(origin_x, origin_y, dx, dy, nearest_dist,
                                  tank.x, tank.y, TANK_RADIUS)
        if result is not None and result < nearest_dist:
            nearest_dist = result
            nearest_hit = tank
            nearest_type = "tank"

    hit_x = origin_x + dx * nearest_dist
    hit_y = origin_y + dy * nearest_dist

    log.debug(
        "cast_ray from (%.0f,%.0f) angle=%.1f → hit_type=%s dist=%.0f",
        origin_x, origin_y, angle_deg, nearest_type, nearest_dist,
    )

    return {
        "hit": nearest_hit is not None,
        "hit_type": nearest_type,
        "entity": nearest_hit,
        "hit_x": hit_x,
        "hit_y": hit_y,
        "distance": nearest_dist,
        "end_x": hit_x,
        "end_y": hit_y,
    }


def _line_vs_aabb(
    ox: float, oy: float, dx: float, dy: float, max_dist: float,
    rx: float, ry: float, rw: float, rh: float,
) -> float | None:
    """
    Ray vs axis-aligned bounding box using the slab method.
    Returns distance to nearest entry intersection, or None on miss.
    """
    INV_EPS = 1e-10

    if abs(dx) < INV_EPS:
        if ox < rx or ox > rx + rw:
            return None
        t_min_x, t_max_x = -float('inf'), float('inf')
    else:
        t1 = (rx - ox) / dx
        t2 = (rx + rw - ox) / dx
        t_min_x, t_max_x = min(t1, t2), max(t1, t2)

    if abs(dy) < INV_EPS:
        if oy < ry or oy > ry + rh:
            return None
        t_min_y, t_max_y = -float('inf'), float('inf')
    else:
        t1 = (ry - oy) / dy
        t2 = (ry + rh - oy) / dy
        t_min_y, t_max_y = min(t1, t2), max(t1, t2)

    t_enter = max(t_min_x, t_min_y)
    t_exit = min(t_max_x, t_max_y)

    if t_enter > t_exit or t_exit < 0:
        return None

    t = t_enter if t_enter >= 0 else t_exit
    if t > max_dist:
        return None
    return t


def _line_vs_circle(
    ox: float, oy: float, dx: float, dy: float, max_dist: float,
    cx: float, cy: float, radius: float,
) -> float | None:
    """
    Ray vs circle using quadratic formula.
    Returns distance to nearest entry intersection, or None on miss.
    """
    fx = ox - cx
    fy = oy - cy
    a = dx * dx + dy * dy  # ≈ 1.0 for unit direction
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0:
        return None

    sqrt_disc = math.sqrt(discriminant)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    if t1 >= 0 and t1 <= max_dist:
        return t1
    if t2 >= 0 and t2 <= max_dist:
        return t2
    return None
