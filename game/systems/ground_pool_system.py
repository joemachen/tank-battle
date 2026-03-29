"""
game/systems/ground_pool_system.py

GroundPoolSystem — applies ground pool effects to tanks each frame.
Separate from CollisionSystem because pools are floor effects, not solid objects.
"""

from game.utils.config_loader import load_yaml
from game.utils.constants import STATUS_EFFECTS_CONFIG
from game.utils.damage_types import DamageType
from game.utils.logger import get_logger

log = get_logger(__name__)

# Lazy-loaded fire effect config (same pattern as collision.py)
_status_configs: dict | None = None


def _get_status_configs() -> dict:
    global _status_configs
    if _status_configs is None:
        _status_configs = load_yaml(STATUS_EFFECTS_CONFIG)
    return _status_configs


class GroundPoolSystem:
    """
    Each frame, checks all tanks against all active ground pools.
    Applies slow and/or damage to tanks standing in pools.
    """

    def update(self, pools: list, tanks: list, dt: float) -> list:
        """
        Apply pool effects to tanks. Returns audio event strings.

        Args:
            pools: all alive ground pools
            tanks: all alive tanks
            dt: frame delta time

        Returns:
            list of event strings for SFX
        """
        events: list = []

        for pool in pools:
            if not pool.is_alive:
                continue
            for tank in tanks:
                if not tank.is_alive:
                    continue
                if not pool.contains(tank.x, tank.y):
                    continue

                # Slow effect — refreshed each frame while in pool
                if pool.slow_mult < 1.0:
                    tank.apply_status("pool_slow", pool.slow_mult, 0.15)

                # Damage (lava pools)
                if pool.dps > 0:
                    frame_damage = max(1, int(pool.dps * dt))
                    tank.take_damage(frame_damage, damage_type=DamageType.FIRE)
                    # Apply fire combat effect through existing pipeline
                    if tank.is_alive:
                        cfgs = _get_status_configs()
                        fire_cfg = cfgs.get("fire")
                        if fire_cfg:
                            tank.apply_combat_effect("fire", fire_cfg)
                    events.append("pool_damage")

        return events
