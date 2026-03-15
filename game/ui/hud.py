"""
game/ui/hud.py

HUD — renders in-game overlay: health bars for player and AI tank.

Layout:
  Player bar — bottom-left corner
  AI bar     — bottom-right corner (mirrored)
  Each bar has the tank's type label drawn above it.

HUD pulls all data at draw time — no entity references are stored here.
"""

import pygame

from game.utils.constants import (
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_WHITE,
    HUD_BAR_HEIGHT,
    HUD_BAR_WIDTH,
    HUD_MARGIN,
)
from game.utils.logger import get_logger

log = get_logger(__name__)

_LABEL_HEIGHT: int = 20    # pixels reserved above each bar for the type label
_HP_TEXT_HEIGHT: int = 18  # pixels reserved below each bar for HP numbers


class HUD:
    """
    Draws player and AI status information onto the screen surface.
    Receives tank references at draw time — does not hold entity references.
    """

    def __init__(self) -> None:
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None
        log.debug("HUD initialized.")

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont(None, 22)
        if self._small_font is None:
            self._small_font = pygame.font.SysFont(None, 18)

    def draw(self, surface: pygame.Surface, player_tank, ai_tank=None) -> None:
        """
        Render HUD health bars. Call after all scene elements are drawn.

        Args:
            surface:     target display surface
            player_tank: player Tank entity (always drawn)
            ai_tank:     AI Tank entity or None (drawn when present)
        """
        self._ensure_fonts()

        sw = surface.get_width()
        sh = surface.get_height()

        # Vertical position: bar sits HUD_MARGIN above screen bottom,
        # label sits above the bar
        bar_y = sh - HUD_MARGIN - HUD_BAR_HEIGHT
        label_y = bar_y - _LABEL_HEIGHT

        # Player bar — bottom-left
        self._draw_health_bar(surface, player_tank, HUD_MARGIN, bar_y, label_y)

        # AI bar — bottom-right (x anchored so bar right edge = screen right - margin)
        if ai_tank is not None:
            ai_x = sw - HUD_MARGIN - HUD_BAR_WIDTH
            self._draw_health_bar(surface, ai_tank, ai_x, bar_y, label_y)

    def _draw_health_bar(
        self,
        surface: pygame.Surface,
        tank,
        x: int,
        y: int,
        label_y: int,
    ) -> None:
        """Draw a single health bar with a type label above it."""
        # Tank type label above bar
        label = self._font.render(tank.tank_type, True, COLOR_WHITE)
        surface.blit(label, (x, label_y))

        # Background bar
        pygame.draw.rect(surface, COLOR_GRAY, (x, y, HUD_BAR_WIDTH, HUD_BAR_HEIGHT))

        # Fill bar — color shifts to red when health is critical
        fill_w = int(HUD_BAR_WIDTH * tank.health_ratio)
        fill_color = COLOR_GREEN if tank.health_ratio > 0.4 else COLOR_RED
        if fill_w > 0:
            pygame.draw.rect(surface, fill_color, (x, y, fill_w, HUD_BAR_HEIGHT))

        # HP numbers to the right of the bar
        hp_text = self._small_font.render(
            f"{tank.health}/{tank.max_health}", True, COLOR_WHITE
        )
        surface.blit(hp_text, (x + HUD_BAR_WIDTH + 6, y + 1))
