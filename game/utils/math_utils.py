"""
game/utils/math_utils.py

Reusable math helpers for 2D game logic.
All functions are pure (no side effects, no pygame dependency).
"""

import math
from typing import Tuple

Vec2 = Tuple[float, float]


def normalize(v: Vec2) -> Vec2:
    """Return a unit vector in the same direction as v. Returns (0, 0) for zero vector."""
    x, y = v
    mag = math.hypot(x, y)
    if mag == 0.0:
        return (0.0, 0.0)
    return (x / mag, y / mag)


def magnitude(v: Vec2) -> float:
    """Return the length of vector v."""
    return math.hypot(v[0], v[1])


def distance(a: Vec2, b: Vec2) -> float:
    """Return Euclidean distance between two points."""
    return math.hypot(b[0] - a[0], b[1] - a[1])


def angle_to(origin: Vec2, target: Vec2) -> float:
    """
    Return angle in degrees from origin pointing toward target.
    0 = right (+x), 90 = down (+y), following pygame's coordinate system.
    """
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    return math.degrees(math.atan2(dy, dx))


def angle_difference(a: float, b: float) -> float:
    """
    Return the shortest signed difference between angles a and b (degrees).
    Result is in [-180, 180].
    """
    diff = (b - a + 180) % 360 - 180
    return diff


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by factor t in [0, 1]."""
    return a + (b - a) * t


def rotate_point(point: Vec2, origin: Vec2, angle_deg: float) -> Vec2:
    """Rotate a point around an origin by angle_deg degrees."""
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    ox, oy = origin
    px, py = point[0] - ox, point[1] - oy
    return (
        ox + px * cos_a - py * sin_a,
        oy + px * sin_a + py * cos_a,
    )


def heading_to_vec(angle_deg: float) -> Vec2:
    """Convert a heading angle (degrees) to a unit direction vector."""
    rad = math.radians(angle_deg)
    return (math.cos(rad), math.sin(rad))
