"""
game/ui/hud.py

HUD — renders in-game overlay: health bar, score, ammo, etc.
Stub — full implementation in the UI milestone.
"""

import pygame

from game.utils.constants import (
    COLOR_GREEN,
    COLOR_GRAY,
    COLOR_RED,
    COLOR_WHITE,
    HUD_BAR_HEIGHT,
    HUD_BAR_WIDTH,
    HUD_MARGIN,
)
from game.utils.logger import get_logger

log = get_logger(__name__)


class HUD:
    """
    Draws player status information onto the screen surface.
    Receives tank reference at draw time — does not hold entity references.
    """

    def __init__(self) -> None:
        self._font = None
        log.debug("HUD initialized.")

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont(None, 24)

    def draw(self, surface: pygame.Surface, player_tank) -> None:
        """Render HUD elements. Call after all scene elements are drawn."""
        self._ensure_font()
        self._draw_health_bar(surface, player_tank)

    def _draw_health_bar(self, surface: pygame.Surface, tank) -> None:
        x, y = HUD_MARGIN, HUD_MARGIN

        # Background bar
        bg_rect = (x, y, HUD_BAR_WIDTH, HUD_BAR_HEIGHT)
        pygame.draw.rect(surface, COLOR_GRAY, bg_rect)

        # Fill bar
        fill_w = int(HUD_BAR_WIDTH * tank.health_ratio)
        fill_color = COLOR_GREEN if tank.health_ratio > 0.4 else COLOR_RED
        if fill_w > 0:
            pygame.draw.rect(surface, fill_color, (x, y, fill_w, HUD_BAR_HEIGHT))

        # Label
        label = self._font.render(
            f"HP  {tank.health}/{tank.max_health}", True, COLOR_WHITE
        )
        surface.blit(label, (x + HUD_BAR_WIDTH + 8, y))
