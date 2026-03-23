"""
game/entities/explosion.py

Explosion entity — a short-lived AoE damage event. Created when an explosive
bullet detonates (on tank contact, obstacle contact, or at max range).

Lives for one frame of damage resolution + a visual duration for the animation.
Damage scales linearly from full at epicenter to damage_falloff at edge of radius.
"""

import math

from game.utils.damage_types import DamageType
from game.utils.logger import get_logger

log = get_logger(__name__)


class Explosion:
    """
    A short-lived AoE damage event.

    Fields:
        x, y: float — world-space center
        radius: float — damage radius in pixels
        damage: int — max damage at epicenter
        damage_type: DamageType — inherited from the bullet that caused it
        owner: object — tank that fired the explosive (for self-hit immunity + stat tracking)
        damage_falloff: float — multiplier at the edge of radius (0.0–1.0)
        is_alive: bool — True during damage frame, set False after resolution
        visual_timer: float — seconds remaining for explosion visual
    """

    def __init__(
        self,
        x: float,
        y: float,
        radius: float,
        damage: int,
        damage_type: DamageType,
        owner,
        damage_falloff: float = 0.3,
        visual_duration: float = 0.4,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.radius: float = radius
        self.damage: int = damage
        self.damage_type: DamageType = damage_type
        self.owner = owner
        self.damage_falloff: float = damage_falloff
        self.is_alive: bool = True  # damage not yet resolved
        self.visual_timer: float = visual_duration
        self._visual_duration: float = visual_duration
        self._damage_resolved: bool = False

        log.debug(
            "Explosion created at (%.0f, %.0f) radius=%.0f damage=%d type=%s",
            x, y, radius, damage, damage_type.name,
        )

    def resolve_damage(self, tanks: list, obstacles: list) -> list:
        """
        Apply AoE damage to all entities within radius. Called once by CollisionSystem.

        Returns list of audio event strings/tuples (same format as collision events).
        Damage scales linearly from full at center to damage_falloff at edge.
        """
        if self._damage_resolved:
            return []
        self._damage_resolved = True
        events: list = []

        for tank in tanks:
            if not tank.is_alive or tank is self.owner:
                continue
            dist = math.hypot(tank.x - self.x, tank.y - self.y)
            if dist < self.radius:
                scale = 1.0 - (1.0 - self.damage_falloff) * (dist / self.radius)
                actual_damage = max(1, int(self.damage * scale))
                tank.take_damage(actual_damage, damage_type=self.damage_type)
                if tank.is_alive:
                    events.append("bullet_hit_tank")
                else:
                    events.append("tank_explosion")
                events.append(("bullet_hit_tank_stat", self.owner, actual_damage, self.damage_type))
                log.debug(
                    "Explosion hit tank at dist=%.0f scale=%.2f damage=%d",
                    dist, scale, actual_damage,
                )

        for obs in obstacles:
            if not obs.is_alive:
                continue
            # Use center of obstacle for distance check
            obs_cx = obs.x + obs.width / 2
            obs_cy = obs.y + obs.height / 2
            dist = math.hypot(obs_cx - self.x, obs_cy - self.y)
            if dist < self.radius:
                scale = 1.0 - (1.0 - self.damage_falloff) * (dist / self.radius)
                actual_damage = max(1, int(self.damage * scale))
                was_alive = obs.is_alive
                obs.take_damage(actual_damage, damage_type=self.damage_type)
                if was_alive and not obs.is_alive:
                    events.append("obstacle_destroy")
                log.debug(
                    "Explosion hit obstacle at dist=%.0f scale=%.2f damage=%d",
                    dist, scale, actual_damage,
                )

        self.is_alive = False  # damage resolved — keep for visual only
        return events

    def update(self, dt: float) -> None:
        """Tick visual timer. Entity removed when visual_timer <= 0."""
        self.visual_timer -= dt

    @property
    def visual_alive(self) -> bool:
        """True while the explosion animation should still be drawn."""
        return self.visual_timer > 0

    @property
    def visual_progress(self) -> float:
        """Animation progress 0.0 (just created) → 1.0 (fully faded)."""
        if self._visual_duration <= 0:
            return 1.0
        return 1.0 - max(0.0, self.visual_timer / self._visual_duration)

    @property
    def position(self) -> tuple:
        return (self.x, self.y)
