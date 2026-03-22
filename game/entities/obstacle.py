"""
game/entities/obstacle.py

Static map obstacle. Blocks tank movement and interacts with bullets.
Material type drives hp, destructibility, damage filtering, and render color.
"""

from game.utils.constants import (
    DAMAGE_DARKEN_CRITICAL,
    DAMAGE_DARKEN_MEDIUM,
    HIT_FLASH_BLEND,
    HIT_FLASH_DURATION,
)
from game.utils.damage_types import DamageType
from game.utils.logger import get_logger
from game.utils.math_utils import blend_colors

log = get_logger(__name__)

# Used when no material config is supplied (should not happen in practice).
_FALLBACK_MATERIAL = {
    "display_name": "Stone",
    "hp": 9999,
    "destructible": False,
    "damage_filters": [],
    "color": [90, 85, 75],
}


class Obstacle:
    """
    A rectangular static obstacle on the map.

    Geometry (x, y, width, height) is in world space.
    CollisionSystem uses .rect for circle/rect intersection tests.

    Material config is injected by MapLoader from materials.yaml.
    The material determines hp, destructible flag, damage_filters, and color.
    """

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        material_type: str = "stone",
        material_config: dict | None = None,
        reflective: bool = False,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.width: float = width
        self.height: float = height
        self.material_type: str = material_type
        self.reflective: bool = reflective
        self.is_alive: bool = True

        cfg = material_config if material_config is not None else _FALLBACK_MATERIAL
        self.destructible: bool = bool(cfg.get("destructible", False))
        self.max_hp: int = int(cfg.get("hp", 9999))
        self.hp: int = self.max_hp
        # damage_filters: empty list = all damage types apply
        self.damage_filters: list = list(cfg.get("damage_filters", []))
        raw_color = cfg.get("color", [90, 85, 75])
        self.color: tuple = (int(raw_color[0]), int(raw_color[1]), int(raw_color[2]))
        self.base_color: tuple = self.color  # overwritten by GameplayScene with theme-tinted value
        self._hit_flash_timer: float = 0.0

        log.debug(
            "Obstacle created: type=%s material=%s hp=%d destructible=%s",
            "rect", material_type, self.hp, self.destructible,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def rect(self) -> tuple:
        """(x, y, width, height) in world space — used by CollisionSystem."""
        return (self.x, self.y, self.width, self.height)

    @property
    def hp_ratio(self) -> float:
        """Current HP as a fraction [0.0, 1.0]. Indestructible obstacles always return 1.0."""
        if not self.destructible or self.max_hp <= 0:
            return 1.0
        return max(0.0, self.hp / self.max_hp)

    @property
    def is_flashing(self) -> bool:
        """True while the hit-flash effect is active."""
        return self._hit_flash_timer > 0

    @property
    def current_color(self) -> tuple:
        """Render color incorporating damage state and hit flash."""
        color = self.base_color
        if self.destructible:
            ratio = self.hp_ratio
            if ratio < 0.33:
                color = blend_colors(color, (0, 0, 0), DAMAGE_DARKEN_CRITICAL)
            elif ratio < 0.66:
                color = blend_colors(color, (0, 0, 0), DAMAGE_DARKEN_MEDIUM)
        if self.is_flashing:
            color = blend_colors(color, (255, 255, 255), HIT_FLASH_BLEND)
        return color

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance per-frame timers (hit flash)."""
        if self._hit_flash_timer > 0:
            self._hit_flash_timer = max(0.0, self._hit_flash_timer - dt)

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------

    def take_damage(self, amount: int, damage_type: DamageType | str = "standard") -> None:
        """
        Apply damage from a bullet or explosion.

        Args:
            amount: raw damage points
            damage_type: DamageType enum or lowercase string — normalized internally

        Guards:
          - Not destructible → no-op
          - damage_filters non-empty and damage_type not in filters → no-op
            (e.g. reinforced_steel only takes "explosive" damage)
        """
        if not self.destructible:
            return
        # Normalize to lowercase string for filter comparison
        if isinstance(damage_type, DamageType):
            dtype_str = damage_type.name.lower()
        else:
            dtype_str = str(damage_type).lower()
        if self.damage_filters and dtype_str not in self.damage_filters:
            log.debug(
                "Obstacle at (%.0f, %.0f) immune to damage_type='%s' (filters=%s).",
                self.x, self.y, dtype_str, self.damage_filters,
            )
            return
        self.hp = max(0, self.hp - amount)
        self._hit_flash_timer = HIT_FLASH_DURATION
        log.debug(
            "Obstacle at (%.0f, %.0f) took %d %s damage — hp=%d/%d.",
            self.x, self.y, amount, dtype_str, self.hp, self.max_hp,
        )
        if self.hp == 0:
            self.is_alive = False
            log.info(
                "Obstacle destroyed at (%.0f, %.0f) [material=%s].",
                self.x, self.y, self.material_type,
            )

    def destroy(self) -> None:
        """
        Force-destroy this obstacle regardless of material rules.
        Kept for compatibility; prefer take_damage() for normal gameplay.
        """
        if self.destructible:
            self.is_alive = False
            log.debug("Obstacle force-destroyed at (%.0f, %.0f).", self.x, self.y)
