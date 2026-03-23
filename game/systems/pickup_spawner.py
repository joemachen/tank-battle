"""
game/systems/pickup_spawner.py

Manages pickup spawn timing, point selection, and active pickup lifecycle.
"""

from __future__ import annotations

import random

from game.entities.pickup import Pickup
from game.utils.constants import (
    PICKUP_LIFETIME,
    PICKUP_MAX_ACTIVE,
    PICKUP_RENDER_RADIUS,
    PICKUP_SPAWN_INTERVAL,
    SFX_PICKUP_EXPIRE,
    SFX_PICKUP_SPAWN,
)
from game.utils.logger import get_logger

log = get_logger(__name__)


def _is_position_clear(x: float, y: float, obstacles: list) -> bool:
    """Return True if (x, y) doesn't overlap any live obstacle rect."""
    margin = PICKUP_RENDER_RADIUS + 4  # 4px clearance
    margin_sq = margin * margin
    for obs in obstacles:
        if not obs.is_alive:
            continue
        ox, oy, ow, oh = obs.rect
        closest_x = max(ox, min(x, ox + ow))
        closest_y = max(oy, min(y, oy + oh))
        dist_sq = (x - closest_x) ** 2 + (y - closest_y) ** 2
        if dist_sq < margin_sq:
            return False
    return True


def _play_sfx(path: str) -> None:
    """Play SFX if audio manager is available."""
    try:
        from game.ui.audio_manager import get_audio_manager
        get_audio_manager().play_sfx(path)
    except Exception:
        pass


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
        self._obstacles_getter = None

    def set_obstacles_getter(self, getter) -> None:
        """Inject a callable that returns the current live obstacles list."""
        self._obstacles_getter = getter

    @property
    def active_pickups(self) -> list[Pickup]:
        return self._active_pickups

    def update(self, dt: float) -> list[Pickup]:
        """Tick pickups, expire old ones, prune collected, and attempt spawns."""
        # Tick active pickups (pulse timer + age)
        for p in self._active_pickups:
            p.update(dt)

        # Expire old pickups
        for p in self._active_pickups:
            if p.is_alive and p.age >= PICKUP_LIFETIME:
                p.is_alive = False
                _play_sfx(SFX_PICKUP_EXPIRE)

        # Prune collected/expired pickups
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
        # Filter out positions blocked by obstacles
        if self._obstacles_getter is not None:
            obstacles = self._obstacles_getter()
            available = [pt for pt in available
                         if _is_position_clear(pt[0], pt[1], obstacles)]
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
        _play_sfx(SFX_PICKUP_SPAWN)
        log.debug("Pickup spawned: %s at %s", pickup_type, point)

    def _weighted_random_type(self) -> str:
        """Select a pickup type using spawn_weight from config."""
        types = list(self._configs.keys())
        weights = [self._configs[t].get("spawn_weight", 1) for t in types]
        return random.choices(types, weights=weights, k=1)[0]
