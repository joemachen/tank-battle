"""
tests/test_pickup_spawner.py

Unit tests for PickupSpawner — spawn timing, caps, and weighted selection (v0.19).
"""

import pytest

from game.systems.pickup_spawner import PickupSpawner
from game.utils.constants import PICKUP_MAX_ACTIVE, PICKUP_SPAWN_INTERVAL

_CONFIGS = {
    "health": {"display_name": "Health Pack", "value": 40, "color": [80, 200, 80], "radius": 14, "spawn_weight": 3},
    "ammo": {"display_name": "Ammo Crate", "value": 1, "color": [200, 180, 60], "radius": 14, "spawn_weight": 2},
    "speed_boost": {"display_name": "Speed Boost", "value": 1.6, "color": [60, 160, 220], "radius": 14, "spawn_weight": 1},
}

_SPAWN_POINTS = [(100, 100), (200, 200), (300, 300), (400, 400), (500, 500)]


class TestPickupSpawnerSpawning:
    def test_spawns_after_interval(self):
        spawner = PickupSpawner(_SPAWN_POINTS, _CONFIGS)
        assert len(spawner.active_pickups) == 0
        spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert len(spawner.active_pickups) == 1

    def test_no_spawn_before_interval(self):
        spawner = PickupSpawner(_SPAWN_POINTS, _CONFIGS)
        spawner.update(PICKUP_SPAWN_INTERVAL - 1.0)
        assert len(spawner.active_pickups) == 0

    def test_does_not_exceed_max_active(self):
        spawner = PickupSpawner(_SPAWN_POINTS, _CONFIGS)
        # Force many spawn cycles
        for _ in range(20):
            spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert len(spawner.active_pickups) <= PICKUP_MAX_ACTIVE

    def test_spawn_timer_resets(self):
        spawner = PickupSpawner(_SPAWN_POINTS, _CONFIGS)
        spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert spawner._spawn_timer == 0.0


class TestPickupSpawnerOccupancy:
    def test_occupied_points_not_reused(self):
        spawner = PickupSpawner([(100, 100)], _CONFIGS)
        spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert len(spawner.active_pickups) == 1
        # Try to spawn again — the only point is occupied
        spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert len(spawner.active_pickups) == 1  # still 1


class TestPickupSpawnerEdgeCases:
    def test_empty_spawn_points(self):
        spawner = PickupSpawner([], _CONFIGS)
        spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert len(spawner.active_pickups) == 0

    def test_empty_configs(self):
        spawner = PickupSpawner(_SPAWN_POINTS, {})
        spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert len(spawner.active_pickups) == 0

    def test_zero_dt_is_safe(self):
        spawner = PickupSpawner(_SPAWN_POINTS, _CONFIGS)
        spawner.update(0.0)
        assert len(spawner.active_pickups) == 0

    def test_collected_pickup_pruned(self):
        spawner = PickupSpawner(_SPAWN_POINTS, _CONFIGS)
        spawner.update(PICKUP_SPAWN_INTERVAL + 0.1)
        assert len(spawner.active_pickups) == 1
        spawner.active_pickups[0].is_alive = False
        spawner.update(0.1)
        assert len(spawner.active_pickups) == 0


class TestWeightedRandomType:
    def test_weighted_distribution(self):
        """Over 1000 samples, health (~50%) should be most common."""
        spawner = PickupSpawner(_SPAWN_POINTS, _CONFIGS)
        counts = {"health": 0, "ammo": 0, "speed_boost": 0}
        for _ in range(1000):
            t = spawner._weighted_random_type()
            counts[t] += 1
        # health weight=3 out of 6 total → ~50%
        assert counts["health"] > counts["ammo"]
        assert counts["ammo"] > counts["speed_boost"]
        # Health should be at least 35% (very conservative)
        assert counts["health"] > 350
