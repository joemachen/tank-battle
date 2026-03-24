"""
game/systems/status_effect.py

StatusEffect — a timed combat debuff applied to a tank by elemental damage.

Pickup buffs (regen, speed_boost, shield, rapid_reload) remain in Tank's
_status_effects dict as plain dicts. Combat effects use this class for
richer tick behavior (DoT, movement/fire-rate multipliers).
"""

from game.utils.logger import get_logger

log = get_logger(__name__)


class StatusEffect:
    """
    A single active combat status effect on a tank.

    Fields:
        effect_type: str — matches key in status_effects.yaml
        duration: float — seconds remaining
        tick_interval: float — seconds between ticks (0 = continuous modifier only)
        tick_damage: int — HP removed per tick
        speed_mult: float — multiplier on tank.speed
        turn_mult: float — multiplier on tank.turn_rate
        fire_rate_mult: float — multiplier on weapon fire_rate
        color: tuple — (R, G, B) tint for visual feedback
    """

    def __init__(self, effect_type: str, config: dict) -> None:
        self.effect_type: str = effect_type
        self.duration: float = float(config.get("duration", 3.0))
        self.tick_interval: float = float(config.get("tick_interval", 0))
        self.tick_damage: int = int(config.get("tick_damage", 0))
        self.speed_mult: float = float(config.get("speed_mult", 1.0))
        self.turn_mult: float = float(config.get("turn_mult", 1.0))
        self.fire_rate_mult: float = float(config.get("fire_rate_mult", 1.0))
        raw_color = config.get("color", [255, 255, 255])
        self.color: tuple = (int(raw_color[0]), int(raw_color[1]), int(raw_color[2]))
        self._tick_timer: float = self.tick_interval if self.tick_interval > 0 else 0

    def update(self, dt: float) -> int:
        """
        Advance timers by dt seconds.
        Returns total tick damage dealt this frame (may be 0 or multiple ticks).
        """
        self.duration -= dt
        if self.tick_interval <= 0 or self.tick_damage <= 0:
            return 0

        damage = 0
        self._tick_timer -= dt
        while self._tick_timer <= 0 and self.duration > -dt:
            damage += self.tick_damage
            self._tick_timer += self.tick_interval
        return damage

    @property
    def is_expired(self) -> bool:
        return self.duration <= 0

    def refresh(self, config: dict) -> None:
        """Reset duration from config. Called when the same effect is re-applied."""
        self.duration = float(config.get("duration", self.duration))
