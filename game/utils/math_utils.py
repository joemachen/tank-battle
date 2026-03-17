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


def blend_colors(
    color_a: tuple,
    color_b: tuple,
    t: float,
) -> tuple:
    """
    Linear interpolation between two RGB colors by factor *t*.

    At t=0 returns color_a; at t=1 returns color_b.
    Each channel is clamped to [0, 255] and returned as an int.

    Args:
        color_a: (R, G, B) source color.
        color_b: (R, G, B) target color.
        t:       Blend factor in [0.0, 1.0] (values outside are clamped).

    Returns:
        (R, G, B) integer tuple.
    """
    t = max(0.0, min(1.0, t))
    return (
        int(max(0, min(255, color_a[0] + (color_b[0] - color_a[0]) * t))),
        int(max(0, min(255, color_a[1] + (color_b[1] - color_a[1]) * t))),
        int(max(0, min(255, color_a[2] + (color_b[2] - color_a[2]) * t))),
    )


def heading_to_vec(angle_deg: float) -> Vec2:
    """Convert a heading angle (degrees) to a unit direction vector."""
    rad = math.radians(angle_deg)
    return (math.cos(rad), math.sin(rad))


def draw_rotated_rect(
    surface,
    color: tuple,
    center: tuple,
    width: int,
    height: int,
    angle_deg: float,
) -> None:
    """
    Draw a filled rectangle of (width × height) rotated by angle_deg degrees,
    centered at the given screen-space center point.

    The rectangle's long axis aligns with angle_deg (0 = pointing right, CW positive,
    following pygame's coordinate convention).

    Requires pygame; imported locally so that this module remains importable in
    headless test environments where pygame is stubbed.

    Args:
        surface:   Target pygame.Surface to draw onto.
        color:     RGB or RGBA fill color tuple.
        center:    (x, y) screen-space center of the rectangle.
        width:     Rectangle extent along the angle_deg axis (the "length").
        height:    Rectangle extent perpendicular to angle_deg (the "thickness").
        angle_deg: Rotation angle in degrees (0 = right, increasing CW).
    """
    import pygame  # local import — keeps math_utils importable without pygame

    rect_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(rect_surf, color, (0, 0, width, height))
    rotated = pygame.transform.rotate(rect_surf, -angle_deg)
    blit_rect = rotated.get_rect(center=(int(center[0]), int(center[1])))
    surface.blit(rotated, blit_rect)
