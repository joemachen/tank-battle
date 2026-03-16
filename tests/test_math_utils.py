"""
tests/test_math_utils.py

Unit tests for game/utils/math_utils.py.

Covers all existing helpers plus the v0.15 addition:
  - draw_rotated_rect helper exists and accepts correct parameters
    (smoke test — no rendering assertion needed)

The pygame stub is installed by conftest.py.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame  # provided by conftest.py stub when pygame is not installed

from game.utils.math_utils import (
    angle_difference,
    angle_to,
    clamp,
    distance,
    draw_rotated_rect,
    heading_to_vec,
    lerp,
    magnitude,
    normalize,
    rotate_point,
)


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_unit_vector_unchanged(self):
        result = normalize((1.0, 0.0))
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.0)

    def test_non_unit_vector(self):
        result = normalize((3.0, 4.0))
        assert math.hypot(*result) == pytest.approx(1.0)

    def test_zero_vector_returns_zero(self):
        assert normalize((0.0, 0.0)) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# magnitude
# ---------------------------------------------------------------------------

class TestMagnitude:
    def test_unit(self):
        assert magnitude((1.0, 0.0)) == pytest.approx(1.0)

    def test_345(self):
        assert magnitude((3.0, 4.0)) == pytest.approx(5.0)

    def test_zero(self):
        assert magnitude((0.0, 0.0)) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# distance
# ---------------------------------------------------------------------------

class TestDistance:
    def test_same_point(self):
        assert distance((5.0, 5.0), (5.0, 5.0)) == pytest.approx(0.0)

    def test_horizontal(self):
        assert distance((0.0, 0.0), (100.0, 0.0)) == pytest.approx(100.0)

    def test_345_triangle(self):
        assert distance((0.0, 0.0), (3.0, 4.0)) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# angle_to
# ---------------------------------------------------------------------------

class TestAngleTo:
    def test_right(self):
        assert angle_to((0.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)

    def test_down(self):
        # pygame coord: +y is down → angle 90°
        assert angle_to((0.0, 0.0), (0.0, 1.0)) == pytest.approx(90.0)

    def test_left(self):
        assert angle_to((0.0, 0.0), (-1.0, 0.0)) == pytest.approx(180.0)

    def test_up(self):
        assert angle_to((0.0, 0.0), (0.0, -1.0)) == pytest.approx(-90.0)


# ---------------------------------------------------------------------------
# angle_difference
# ---------------------------------------------------------------------------

class TestAngleDifference:
    def test_no_difference(self):
        assert angle_difference(45.0, 45.0) == pytest.approx(0.0)

    def test_positive_diff(self):
        assert angle_difference(0.0, 90.0) == pytest.approx(90.0)

    def test_negative_diff(self):
        assert angle_difference(90.0, 0.0) == pytest.approx(-90.0)

    def test_wrap_around(self):
        # Shortest path from 350° to 10° is +20° (not -340°)
        assert angle_difference(350.0, 10.0) == pytest.approx(20.0)

    def test_wrap_around_negative(self):
        # Shortest path from 10° to 350° is -20°
        assert angle_difference(10.0, 350.0) == pytest.approx(-20.0)


# ---------------------------------------------------------------------------
# clamp
# ---------------------------------------------------------------------------

class TestClamp:
    def test_within_range(self):
        assert clamp(5.0, 0.0, 10.0) == pytest.approx(5.0)

    def test_below_min(self):
        assert clamp(-5.0, 0.0, 10.0) == pytest.approx(0.0)

    def test_above_max(self):
        assert clamp(15.0, 0.0, 10.0) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# lerp
# ---------------------------------------------------------------------------

class TestLerp:
    def test_t_zero(self):
        assert lerp(0.0, 100.0, 0.0) == pytest.approx(0.0)

    def test_t_one(self):
        assert lerp(0.0, 100.0, 1.0) == pytest.approx(100.0)

    def test_t_half(self):
        assert lerp(0.0, 100.0, 0.5) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# rotate_point
# ---------------------------------------------------------------------------

class TestRotatePoint:
    def test_identity_rotation(self):
        result = rotate_point((1.0, 0.0), (0.0, 0.0), 0.0)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.0)

    def test_90_degrees(self):
        # Rotating (1, 0) around origin by 90° → (0, 1) in standard math
        # (pygame y-down: result is (0, 1))
        result = rotate_point((1.0, 0.0), (0.0, 0.0), 90.0)
        assert result[0] == pytest.approx(0.0, abs=1e-6)
        assert result[1] == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# heading_to_vec
# ---------------------------------------------------------------------------

class TestHeadingToVec:
    def test_zero_degrees(self):
        dx, dy = heading_to_vec(0.0)
        assert dx == pytest.approx(1.0)
        assert dy == pytest.approx(0.0, abs=1e-6)

    def test_90_degrees(self):
        dx, dy = heading_to_vec(90.0)
        assert dx == pytest.approx(0.0, abs=1e-6)
        assert dy == pytest.approx(1.0)

    def test_unit_length(self):
        for angle in [0, 45, 90, 135, 180, 270]:
            dx, dy = heading_to_vec(float(angle))
            assert math.hypot(dx, dy) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# draw_rotated_rect — smoke tests (v0.15)
# ---------------------------------------------------------------------------

class TestDrawRotatedRect:
    """Smoke tests: verify the function exists, is callable, and does not crash.
    No rendering assertion needed — the stub Surface.blit is a no-op."""

    def _surface(self):
        return pygame.Surface((200, 200))

    def test_function_exists(self):
        assert callable(draw_rotated_rect)

    def test_accepts_correct_parameters(self):
        """Call with valid params — must not raise."""
        surf = self._surface()
        draw_rotated_rect(surf, (255, 0, 0), (100, 100), 30, 6, 0.0)

    def test_angle_zero(self):
        surf = self._surface()
        draw_rotated_rect(surf, (0, 255, 0), (50, 50), 20, 6, 0.0)

    def test_angle_90(self):
        surf = self._surface()
        draw_rotated_rect(surf, (0, 0, 255), (100, 100), 30, 6, 90.0)

    def test_angle_45(self):
        surf = self._surface()
        draw_rotated_rect(surf, (255, 255, 0), (80, 80), 25, 8, 45.0)

    def test_large_angle(self):
        """Angles > 360 should not crash."""
        surf = self._surface()
        draw_rotated_rect(surf, (255, 16, 240), (100, 100), 22, 6, 450.0)

    def test_negative_angle(self):
        surf = self._surface()
        draw_rotated_rect(surf, (255, 16, 240), (100, 100), 22, 6, -45.0)
