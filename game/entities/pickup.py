"""
game/entities/pickup.py

Collectible pickup entity (health pack, rapid reload, speed boost).
Effect type and value defined in pickup config passed at spawn.
"""

import math

from game.utils.constants import (
    PICKUP_COLLECT_SFX,
    PICKUP_EFFECT_DURATION,
    PICKUP_PULSE_SPEED,
    SHIELD_DEFAULT_DURATION,
    SHIELD_DEFAULT_HP,
    SFX_PICKUP_COLLECT,
)
from game.utils.logger import get_logger

log = get_logger(__name__)


class Pickup:
    """
    A collectable item on the map. The CollisionSystem detects tank overlap
    and calls apply() to grant the effect.
    """

    def __init__(
        self,
        x: float,
        y: float,
        pickup_type: str,
        value: float,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.pickup_type: str = pickup_type
        self.value: float = value
        self.is_alive: bool = True
        self.radius: float = 14.0
        self._pulse_timer: float = 0.0
        self._age: float = 0.0
        log.debug("Pickup spawned: type=%s value=%.1f at (%.0f, %.0f)", pickup_type, value, x, y)

    def apply(self, tank) -> None:
        """
        Apply this pickup's effect to a tank.
        Called by CollisionSystem when a tank overlaps this pickup.
        """
        if not self.is_alive:
            return
        if self.pickup_type == "health":
            if tank.health >= tank.max_health:
                log.debug("Tank at full HP — health pickup not consumed.")
                return
            heal_per_tick = self.value / PICKUP_EFFECT_DURATION
            tank.apply_status("regen", heal_per_tick, duration=PICKUP_EFFECT_DURATION)
        elif self.pickup_type == "rapid_reload":
            tank._slot_cooldowns = [0.0] * len(tank._slot_cooldowns)
        elif self.pickup_type == "speed_boost":
            tank.apply_status("speed_boost", self.value, duration=PICKUP_EFFECT_DURATION)
        elif self.pickup_type == "shield":
            tank.apply_status(
                "shield", 0.0, duration=SHIELD_DEFAULT_DURATION,
                shield_hp=self.value or SHIELD_DEFAULT_HP,
            )
        self.is_alive = False
        try:
            from game.ui.audio_manager import get_audio_manager
            sfx = PICKUP_COLLECT_SFX.get(self.pickup_type, SFX_PICKUP_COLLECT)
            get_audio_manager().play_sfx(sfx)
        except Exception:
            pass
        log.info("Pickup '%s' applied to %s", self.pickup_type, tank.tank_type)

    def update(self, dt: float) -> None:
        """Advance pulse animation timer and age."""
        self._pulse_timer += dt
        self._age += dt

    @property
    def age(self) -> float:
        """Time in seconds since this pickup was spawned."""
        return self._age

    @property
    def pulse(self) -> float:
        """Smooth 0.0–1.0 oscillation for visual pulse effect."""
        return (math.sin(self._pulse_timer * PICKUP_PULSE_SPEED) + 1.0) / 2.0

    @property
    def position(self) -> tuple:
        return (self.x, self.y)
