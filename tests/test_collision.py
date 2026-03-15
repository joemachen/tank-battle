"""
tests/test_collision.py

Unit tests for CollisionSystem geometry helpers.
No pygame, no rendering — pure math only.
"""

import pytest

from game.systems.collision import CollisionSystem


class TestCirclesOverlap:
    def test_overlapping_circles(self):
        assert CollisionSystem.circles_overlap((0, 0), 10, (5, 0), 10) is True

    def test_touching_circles(self):
        # Exactly touching — should NOT count as overlap (strict <)
        assert CollisionSystem.circles_overlap((0, 0), 5, (10, 0), 5) is False

    def test_non_overlapping_circles(self):
        assert CollisionSystem.circles_overlap((0, 0), 5, (20, 0), 5) is False

    def test_same_position(self):
        assert CollisionSystem.circles_overlap((3, 3), 1, (3, 3), 1) is True


class TestCircleVsRect:
    def test_circle_inside_rect(self):
        assert CollisionSystem.circle_vs_rect((50, 50), 5, (10, 10, 100, 100)) is True

    def test_circle_overlapping_corner(self):
        # Circle centered at (0, 0) with radius 10 — corner of rect at (7, 7)
        assert CollisionSystem.circle_vs_rect((0, 0), 10, (7, 7, 50, 50)) is True

    def test_circle_far_from_rect(self):
        assert CollisionSystem.circle_vs_rect((200, 200), 5, (0, 0, 50, 50)) is False

    def test_circle_touching_edge(self):
        # Circle just touching left edge of rect — should NOT overlap (strict <)
        assert CollisionSystem.circle_vs_rect((-5, 25), 5, (0, 0, 50, 50)) is False
