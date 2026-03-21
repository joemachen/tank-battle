"""
tests/test_debris.py

Unit tests for the DebrisSystem particle manager introduced in v0.18.
"""

import pytest

from game.systems.debris_system import DebrisParticle, DebrisSystem
from game.utils.constants import (
    DEBRIS_FADE_MAX,
    DEBRIS_GRAVITY,
    MAX_DEBRIS_PARTICLES,
)


# ---------------------------------------------------------------------------
# DebrisParticle
# ---------------------------------------------------------------------------


class TestDebrisParticle:
    def test_initial_alpha_is_255(self):
        p = DebrisParticle(0, 0, 10, 10, 6, (255, 0, 0), 0.5)
        assert p.alpha == 255

    def test_alpha_decays_over_lifetime(self):
        p = DebrisParticle(0, 0, 10, 10, 6, (255, 0, 0), 1.0)
        p.age = 0.5
        assert p.alpha == 127 or p.alpha == 128  # half-life

    def test_alpha_zero_at_end(self):
        p = DebrisParticle(0, 0, 10, 10, 6, (255, 0, 0), 0.5)
        p.age = 0.5
        assert p.alpha == 0

    def test_is_alive_true_initially(self):
        p = DebrisParticle(0, 0, 10, 10, 6, (255, 0, 0), 0.5)
        assert p.is_alive

    def test_is_alive_false_after_lifetime(self):
        p = DebrisParticle(0, 0, 10, 10, 6, (255, 0, 0), 0.5)
        p.age = 0.6
        assert not p.is_alive


# ---------------------------------------------------------------------------
# DebrisSystem — spawn
# ---------------------------------------------------------------------------


class TestDebrisSpawn:
    def test_spawn_creates_correct_count(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (200, 100, 50), 5)
        assert ds.particle_count == 5

    def test_spawn_zero_is_noop(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (200, 100, 50), 0)
        assert ds.particle_count == 0

    def test_spawn_negative_is_noop(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (200, 100, 50), -3)
        assert ds.particle_count == 0

    def test_spawn_caps_at_max(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (200, 100, 50), MAX_DEBRIS_PARTICLES + 50)
        assert ds.particle_count == MAX_DEBRIS_PARTICLES

    def test_oldest_pruned_first_on_cap(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (255, 0, 0), 150)
        # Mark the first batch so we can tell them apart
        for p in ds._particles:
            p.color = (255, 0, 0)
        ds.spawn_debris(200, 200, 60, 40, (0, 255, 0), 100)
        assert ds.particle_count == MAX_DEBRIS_PARTICLES
        # Oldest (red) particles should have been pruned; newest (green) kept
        green_count = sum(1 for p in ds._particles if p.color == (0, 255, 0))
        assert green_count == 100


# ---------------------------------------------------------------------------
# DebrisSystem — update
# ---------------------------------------------------------------------------


class TestDebrisUpdate:
    def test_particles_pruned_after_lifetime(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (200, 100, 50), 5)
        # Advance past max possible lifetime
        ds.update(DEBRIS_FADE_MAX + 0.5)
        assert ds.particle_count == 0

    def test_gravity_affects_vy(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (200, 100, 50), 1)
        initial_vy = ds._particles[0].vy
        ds.update(0.1)
        # vy should have increased by DEBRIS_GRAVITY * dt
        expected_vy = initial_vy + DEBRIS_GRAVITY * 0.1
        assert abs(ds._particles[0].vy - expected_vy) < 0.01

    def test_position_advances(self):
        ds = DebrisSystem()
        ds.spawn_debris(100, 100, 60, 40, (200, 100, 50), 1)
        p = ds._particles[0]
        old_x, old_y = p.x, p.y
        vx, vy = p.vx, p.vy
        ds.update(0.05)
        assert abs(p.x - (old_x + vx * 0.05)) < 0.01
        # y has gravity component too
        assert abs(p.y - (old_y + vy * 0.05)) < 0.5

    def test_empty_update_is_safe(self):
        ds = DebrisSystem()
        ds.update(0.1)  # no crash
        assert ds.particle_count == 0
