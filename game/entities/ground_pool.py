"""
game/entities/ground_pool.py

GroundPool — a persistent area effect on the map floor.
Created when a glue or lava projectile lands. Affects tanks that drive through it.
Pools are floor hazards: visual overlays + status effects on tanks inside the circle.
"""

from game.utils.logger import get_logger

log = get_logger(__name__)


class GroundPool:
    """
    A timed area effect on the ground.

    Fields:
        x, y: float — world-space center
        radius: float — effect radius in pixels
        pool_type: str — "glue" or "lava"
        duration: float — seconds remaining before pool disappears
        slow_mult: float — speed multiplier for tanks in the pool (< 1.0 = slow)
        dps: float — damage per second to tanks in the pool (0 for non-damaging)
        color: tuple — (R, G, B) for rendering
        owner: object — tank that created this pool (immune to own pool)
        is_alive: bool — False when duration expires
    """

    def __init__(
        self,
        x: float,
        y: float,
        pool_type: str,
        radius: float,
        duration: float,
        slow_mult: float,
        dps: float,
        color: tuple,
        owner=None,
    ) -> None:
        self.x = x
        self.y = y
        self.pool_type = pool_type
        self.radius = radius
        self.duration = duration
        self.max_duration = duration
        self.slow_mult = slow_mult
        self.dps = dps
        self.color = color
        self.owner = owner
        self.is_alive = True
        log.debug(
            "GroundPool spawned: type=%s at (%.0f, %.0f) radius=%.0f duration=%.1fs",
            pool_type, x, y, radius, duration,
        )

    def update(self, dt: float) -> None:
        """Tick duration. Pool dies when time expires."""
        if not self.is_alive:
            return
        self.duration -= dt
        if self.duration <= 0:
            self.is_alive = False
            log.debug("GroundPool expired: type=%s at (%.0f, %.0f)",
                      self.pool_type, self.x, self.y)

    def contains(self, px: float, py: float) -> bool:
        """Check if a point is inside the pool's radius."""
        dist_sq = (px - self.x) ** 2 + (py - self.y) ** 2
        return dist_sq < self.radius * self.radius

    @property
    def age_ratio(self) -> float:
        """0.0 = just spawned, 1.0 = about to expire. Used for fade-out rendering."""
        if self.max_duration <= 0:
            return 1.0
        return 1.0 - (self.duration / self.max_duration)

    @property
    def position(self) -> tuple:
        return (self.x, self.y)
