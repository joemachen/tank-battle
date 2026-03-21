"""
game/systems/debris_system.py

Particle-based debris burst spawned when destructible obstacles are destroyed.
Each particle is a small colored square that flies outward, arcs under gravity,
and fades out over a short lifetime.
"""

from __future__ import annotations

import math
import random

from game.utils.constants import (
    DEBRIS_FADE_MAX,
    DEBRIS_FADE_MIN,
    DEBRIS_GRAVITY,
    DEBRIS_SPEED_MAX,
    DEBRIS_SPEED_MIN,
    MAX_DEBRIS_PARTICLES,
)
from game.utils.logger import get_logger

log = get_logger(__name__)


class DebrisParticle:
    """A single debris fragment with position, velocity, and fade."""

    __slots__ = (
        "x", "y", "vx", "vy", "size", "color",
        "lifetime", "age", "rotation", "rotation_speed",
    )

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        size: int,
        color: tuple,
        lifetime: float,
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.color = color
        self.lifetime = lifetime
        self.age: float = 0.0
        self.rotation: float = random.uniform(0, 360)
        self.rotation_speed: float = random.uniform(-360, 360)

    @property
    def alpha(self) -> int:
        """Current alpha [0, 255] based on remaining lifetime."""
        if self.lifetime <= 0:
            return 0
        t = max(0.0, 1.0 - self.age / self.lifetime)
        return int(t * 255)

    @property
    def is_alive(self) -> bool:
        return self.age < self.lifetime


class DebrisSystem:
    """Manages all active debris particles."""

    def __init__(self) -> None:
        self._particles: list[DebrisParticle] = []

    @property
    def particle_count(self) -> int:
        return len(self._particles)

    def spawn_debris(
        self,
        cx: float,
        cy: float,
        width: float,
        height: float,
        color: tuple,
        count: int,
    ) -> None:
        """Create *count* debris particles at (cx, cy) with random outward velocity."""
        if count <= 0:
            return

        # Clamp count so we never exceed the cap
        count = min(count, MAX_DEBRIS_PARTICLES)

        # Prune oldest if we'd exceed the cap
        space = MAX_DEBRIS_PARTICLES - len(self._particles)
        if count > space:
            prune = count - space
            self._particles = self._particles[prune:]

        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(DEBRIS_SPEED_MIN, DEBRIS_SPEED_MAX)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            size = random.randint(4, 8)
            lifetime = random.uniform(DEBRIS_FADE_MIN, DEBRIS_FADE_MAX)
            self._particles.append(
                DebrisParticle(cx, cy, vx, vy, size, color, lifetime)
            )

    def update(self, dt: float) -> None:
        """Advance all particles and remove dead ones."""
        for p in self._particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += DEBRIS_GRAVITY * dt
            p.age += dt
            p.rotation += p.rotation_speed * dt

        self._particles = [p for p in self._particles if p.is_alive]

    def draw(self, surface, camera) -> None:
        """Render all live particles to *surface* via *camera* transform."""
        try:
            import pygame
        except ImportError:
            return

        for p in self._particles:
            a = p.alpha
            if a <= 0:
                continue
            sx, sy = camera.world_to_screen(p.x, p.y)
            particle_surf = pygame.Surface((p.size, p.size), pygame.SRCALPHA)
            particle_surf.fill((*p.color[:3], a))
            surface.blit(particle_surf, (int(sx - p.size / 2), int(sy - p.size / 2)))
