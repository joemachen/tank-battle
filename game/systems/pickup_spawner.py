"""
game/systems/pickup_spawner.py

Manages pickup spawn timing, point selection, and active pickup lifecycle.
"""

from __future__ import annotations

import random

from game.entities.pickup import Pickup
from game.utils.constants import PICKUP_MAX_ACTIVE, PICKUP_SPAWN_INTERVAL
from game.utils.logger import get_logger

log = get_logger(__name__)


class PickupSpawner:
    """Spawns pickups at configured map points on a timed interval."""

    def __init__(
        self,
        spawn_points: list[tuple],
        pickup_configs: dict,
    ) -> None:
        self._spawn_points: list[tuple] = list(spawn_points)
        self._configs: dict = pickup_configs
        self._active_pickups: list[Pickup] = []
        self._spawn_timer: float = 0.0
        self._spawn_interval: float = PICKUP_SPAWN_INTERVAL
        self._max_active: int = PICKUP_MAX_ACTIVE

    @property
    def active_pickups(self) -> list[Pickup]:
        return self._active_pickups

    def update(self, dt: float) -> list[Pickup]:
        """Tick pickups, prune collected, and attempt spawns."""
        # Tick active pickups (pulse timer)
        for p in self._active_pickups:
            p.update(dt)

        # Prune collected pickups
        self._active_pickups = [p for p in self._active_pickups if p.is_alive]

        # Spawn timer
        self._spawn_timer += dt
        if (self._spawn_timer >= self._spawn_interval
                and len(self._active_pickups) < self._max_active):
            self._try_spawn()
            self._spawn_timer = 0.0

        return self._active_pickups

    def _try_spawn(self) -> None:
        """Spawn a pickup at a random unoccupied spawn point."""
        if not self._spawn_points or not self._configs:
            return

        occupied = {(p.x, p.y) for p in self._active_pickups}
        available = [pt for pt in self._spawn_points if pt not in occupied]
        if not available:
            return

        point = random.choice(available)
        pickup_type = self._weighted_random_type()
        config = self._configs[pickup_type]
        pickup = Pickup(
            x=point[0],
            y=point[1],
            pickup_type=pickup_type,
            value=float(config.get("value", 1)),
        )
        self._active_pickups.append(pickup)
        log.debug("Pickup spawned: %s at %s", pickup_type, point)

    def _weighted_random_type(self) -> str:
        """Select a pickup type using spawn_weight from config."""
        types = list(self._configs.keys())
        weights = [self._configs[t].get("spawn_weight", 1) for t in types]
        return random.choices(types, weights=weights, k=1)[0]
