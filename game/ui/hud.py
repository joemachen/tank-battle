"""
game/ui/hud.py

HUD — renders in-game overlay: health bars for player and AI tank(s),
plus a weapon slot display showing all 3 loadout slots.

Layout:
  Player bar — bottom-left corner
  Weapon slots — row just below the player health bar
  AI bars    — bottom-right corner, stacked vertically (one per live AI tank)
  Each bar has the tank's type label drawn above it.

HUD pulls all data at draw time — no entity references are stored here.
"""

import pygame

from game.utils.constants import (
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_NEON_PINK,
    COLOR_RED,
    COLOR_WHITE,
    HUD_BAR_HEIGHT,
    HUD_BAR_WIDTH,
    HUD_MARGIN,
    MAX_WEAPON_SLOTS,
)
from game.utils.logger import get_logger

log = get_logger(__name__)

_LABEL_HEIGHT: int = 20    # pixels above each bar for the type label
_HP_TEXT_HEIGHT: int = 18  # pixels below each bar for HP numbers
# Vertical stride between stacked AI bars (bar + label + gap)
_AI_BAR_STRIDE: int = HUD_BAR_HEIGHT + _LABEL_HEIGHT + 8


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

    def draw(
        self,
        surface: pygame.Surface,
        player_tank,
        ai_tanks=None,
        weapon_slots: list | None = None,
        active_slot: int = 0,
    ) -> None:
        """
        Render HUD health bars and weapon slot display.

        Args:
            surface:      target display surface
            player_tank:  player Tank entity (always drawn)
            ai_tanks:     a single Tank, a list of Tanks, or None
            weapon_slots: list of weapon config dicts from tank.weapon_slots
            active_slot:  index of the currently active weapon slot
        """
        self._ensure_fonts()

        sw = surface.get_width()
        sh = surface.get_height()

        # Player bar — bottom-left
        bar_y = sh - HUD_MARGIN - HUD_BAR_HEIGHT
        label_y = bar_y - _LABEL_HEIGHT
        self._draw_health_bar(surface, player_tank, HUD_MARGIN, bar_y, label_y)

        # Weapon slot row — just below the player health bar
        if weapon_slots:
            self._draw_weapon_slots(
                surface, weapon_slots, active_slot,
                x=HUD_MARGIN, y=bar_y + HUD_BAR_HEIGHT + 4,
            )

        # Normalise ai_tanks to a list (supports single Tank for backwards compat)
        if ai_tanks is None:
            tanks = []
        elif hasattr(ai_tanks, "is_alive"):
            tanks = [ai_tanks]
        else:
            tanks = [t for t in ai_tanks if t is not None]

        # Stack AI bars from the bottom-right upward; dead tanks are omitted
        ai_x = sw - HUD_MARGIN - HUD_BAR_WIDTH
        row = 0
        for tank in tanks:
            if not tank.is_alive:
                continue
            t_bar_y = sh - HUD_MARGIN - HUD_BAR_HEIGHT - row * _AI_BAR_STRIDE
            t_label_y = t_bar_y - _LABEL_HEIGHT
            if t_label_y < 0:
                break  # no vertical space left
            self._draw_health_bar(surface, tank, ai_x, t_bar_y, t_label_y)
            row += 1

    def _draw_weapon_slots(
        self,
        surface: pygame.Surface,
        weapon_slots: list,
        active_slot: int,
        x: int,
        y: int,
    ) -> None:
        """
        Render up to MAX_WEAPON_SLOTS weapon labels in a horizontal row.
        Active slot is neon-pink; inactive slots are gray; empty slots show '---'.
        Format:  [1: Standard Shell]  [2: Spread Shot]  [3: ---]
        """
        font = self._small_font
        if font is None:
            return

        # Pad to MAX_WEAPON_SLOTS with None entries
        padded: list = list(weapon_slots) + [None] * (MAX_WEAPON_SLOTS - len(weapon_slots))

        cx = x
        for i, slot in enumerate(padded):
            if slot is not None:
                wname = slot.get("type", "---").replace("_", " ").title()
            else:
                wname = "---"

            color = COLOR_NEON_PINK if i == active_slot else COLOR_GRAY
            label = f"[{i + 1}: {wname}]"
            rendered = font.render(label, True, color)
            surface.blit(rendered, (cx, y))
            cx += rendered.get_width() + 8

    def _draw_health_bar(
        self,
        surface: pygame.Surface,
        tank,
        x: int,
        y: int,
        label_y: int,
    ) -> None:
        """Draw a single health bar with a type label above it."""
        label = self._font.render(tank.tank_type, True, COLOR_WHITE)
        surface.blit(label, (x, label_y))

        pygame.draw.rect(surface, COLOR_GRAY, (x, y, HUD_BAR_WIDTH, HUD_BAR_HEIGHT))

        fill_w = int(HUD_BAR_WIDTH * tank.health_ratio)
        fill_color = COLOR_GREEN if tank.health_ratio > 0.4 else COLOR_RED
        if fill_w > 0:
            pygame.draw.rect(surface, fill_color, (x, y, fill_w, HUD_BAR_HEIGHT))

        hp_text = self._small_font.render(
            f"{tank.health}/{tank.max_health}", True, COLOR_WHITE
        )
        surface.blit(hp_text, (x + HUD_BAR_WIDTH + 6, y + 1))
