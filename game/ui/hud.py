"""
game/ui/hud.py

HUD — renders in-game overlay: health bars for player and AI tank(s),
plus a weapon slot display showing all 3 loadout slots.

Layout (bottom-left, measured upward from screen bottom):
  HUD_BOTTOM_MARGIN              ← gap from screen edge
  Weapon slot row  (_WEAPON_ROW_H)
  _BAR_WEAPON_GAP                ← gap between weapon row and bar
  Player health bar (HUD_BAR_HEIGHT)
  _LABEL_HEIGHT                  ← gap + label above bar

AI health bars mirror the same y-anchor in the bottom-right corner
(no weapon row; they start at the same bar_y as the player).

HUD pulls all data at draw time — no entity references are stored here.
"""

import pygame

from game.utils.constants import (
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_NEON_PINK,
    COLOR_RED,
    COLOR_WHITE,
    DAMAGE_TYPE_BULLET_COLORS,
    HUD_BAR_HEIGHT,
    HUD_BAR_WIDTH,
    HUD_BOTTOM_MARGIN,
    HUD_MARGIN,
    MAX_WEAPON_SLOTS,
)
from game.utils.logger import get_logger

log = get_logger(__name__)

_LABEL_HEIGHT: int = 20     # pixels above each bar for the type label
_HP_TEXT_HEIGHT: int = 18   # pixels below each bar for HP numbers
_WEAPON_ROW_H: int = 18     # estimated pixel height of one small-font text row
_BAR_WEAPON_GAP: int = 4    # gap between the top of the weapon row and the bottom of the bar

# Vertical stride between stacked AI bars (bar + label + gap)
_AI_BAR_STRIDE: int = HUD_BAR_HEIGHT + _LABEL_HEIGHT + 8


def _compute_bar_y(sh: int) -> int:
    """
    Return the y-coordinate for a health bar so that the weapon slot row
    and the bar itself are both fully visible at the bottom of the screen.

    Stack from bottom up:
      HUD_BOTTOM_MARGIN → weapon row → _BAR_WEAPON_GAP → health bar → label
    """
    weapon_y = sh - HUD_BOTTOM_MARGIN - _WEAPON_ROW_H
    return weapon_y - _BAR_WEAPON_GAP - HUD_BAR_HEIGHT


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
        slot_cooldowns: list | None = None,
        combat_effects: dict | None = None,
    ) -> None:
        """
        Render HUD health bars and weapon slot display.

        Args:
            surface:        target display surface
            player_tank:    player Tank entity (always drawn)
            ai_tanks:       a single Tank, a list of Tanks, or None
            weapon_slots:   list of weapon config dicts from tank.weapon_slots
            active_slot:    index of the currently active weapon slot
            slot_cooldowns: list of per-slot cooldown timers (seconds remaining)
            combat_effects: dict of active combat StatusEffects (from tank.combat_effects)
        """
        self._ensure_fonts()

        sw = surface.get_width()
        sh = surface.get_height()

        # Compute anchors — everything derived from _compute_bar_y so
        # the weapon row is never clipped at the bottom of the screen.
        bar_y = _compute_bar_y(sh)
        label_y = bar_y - _LABEL_HEIGHT
        weapon_y = bar_y + HUD_BAR_HEIGHT + _BAR_WEAPON_GAP

        # Player bar — bottom-left
        self._draw_health_bar(surface, player_tank, HUD_MARGIN, bar_y, label_y)

        # Weapon slot row — below the player health bar
        if weapon_slots:
            self._draw_weapon_slots(
                surface, weapon_slots, active_slot,
                x=HUD_MARGIN, y=weapon_y,
                slot_cooldowns=slot_cooldowns,
            )

        # Combat effect indicators — between health bar and weapon slots
        if combat_effects:
            self._draw_combat_effects(surface, combat_effects, HUD_MARGIN, label_y - 16)

        # Energy bar — shown when a hitscan weapon is equipped (v0.25)
        energy_max = getattr(player_tank, '_energy_max', 0)
        if isinstance(energy_max, (int, float)) and energy_max > 0:
            energy_y = weapon_y + 20
            # Background bar
            pygame.draw.rect(surface, COLOR_GRAY, (HUD_MARGIN, energy_y, HUD_BAR_WIDTH, 8))
            # Fill bar — cyan when healthy, red when critically low
            fill_w = int(HUD_BAR_WIDTH * player_tank.energy_ratio)
            fill_color = (60, 200, 255) if player_tank.energy_ratio > 0.25 else COLOR_RED
            if fill_w > 0:
                pygame.draw.rect(surface, fill_color, (HUD_MARGIN, energy_y, fill_w, 8))
            # Label
            energy_label = self._small_font.render("ENERGY", True, (60, 200, 255))
            surface.blit(energy_label, (HUD_MARGIN + HUD_BAR_WIDTH + 6, energy_y - 2))

        # Normalise ai_tanks to a list (supports single Tank for backwards compat)
        if ai_tanks is None:
            tanks = []
        elif hasattr(ai_tanks, "is_alive"):
            tanks = [ai_tanks]
        else:
            tanks = [t for t in ai_tanks if t is not None]

        # Stack AI bars from the same bar_y upward in the bottom-right corner;
        # dead tanks are omitted.
        ai_x = sw - HUD_MARGIN - HUD_BAR_WIDTH
        row = 0
        for tank in tanks:
            if not tank.is_alive:
                continue
            t_bar_y = bar_y - row * _AI_BAR_STRIDE
            t_label_y = t_bar_y - _LABEL_HEIGHT
            if t_label_y < 0:
                break  # no vertical space left
            self._draw_health_bar(surface, tank, ai_x, t_bar_y, t_label_y, right_aligned=True)
            row += 1

    def _draw_weapon_slots(
        self,
        surface: pygame.Surface,
        weapon_slots: list,
        active_slot: int,
        x: int,
        y: int,
        slot_cooldowns: list | None = None,
    ) -> None:
        """
        Render up to MAX_WEAPON_SLOTS weapon labels in a horizontal row.
        Active slot is neon-pink; inactive slots are gray; empty slots show '---'.
        Format:  [1: Standard Shell]  [2: Spread Shot]  [3: ---]
        Cooldown overlay darkens the label while weapon is recharging (v0.22).
        """
        font = self._small_font
        if font is None:
            return

        # Pad to MAX_WEAPON_SLOTS with None entries
        padded: list = list(weapon_slots) + [None] * (MAX_WEAPON_SLOTS - len(weapon_slots))
        cooldowns = slot_cooldowns or [0.0] * MAX_WEAPON_SLOTS

        cx = x
        for i, slot in enumerate(padded):
            if slot is not None:
                wname = slot.get("type", "---").replace("_", " ").title()
                fire_rate = float(slot.get("fire_rate", 1.0))
            else:
                wname = "---"
                fire_rate = 1.0

            color = COLOR_NEON_PINK if i == active_slot else COLOR_GRAY
            label = f"[{i + 1}: {wname}]"
            rendered = font.render(label, True, color)
            label_w = rendered.get_width()
            label_h = rendered.get_height()
            surface.blit(rendered, (cx, y))

            # Cooldown overlay — dark sweep that reveals weapon name as cooldown expires (v0.22)
            cd = cooldowns[i] if i < len(cooldowns) else 0.0
            if cd > 0 and slot is not None:
                max_cd = 1.0 / fire_rate if fire_rate > 0 else 1.0
                cd_ratio = min(1.0, cd / max_cd)
                overlay_w = int(label_w * cd_ratio)
                if overlay_w > 0:
                    overlay = pygame.Surface((overlay_w, label_h), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 140))
                    surface.blit(overlay, (cx + label_w - overlay_w, y))

            # Colored dot indicating damage type (v0.21)
            if slot is not None:
                dtype = slot.get("damage_type", "standard").upper()
                dot_color = DAMAGE_TYPE_BULLET_COLORS.get(dtype, DAMAGE_TYPE_BULLET_COLORS["STANDARD"])
                dot_x = cx + label_w + 2
                dot_y = y + label_h // 2
                pygame.draw.circle(surface, dot_color, (dot_x, dot_y), 4)
                cx = dot_x + 6
            else:
                cx += rendered.get_width() + 8

    def _draw_combat_effects(
        self,
        surface: pygame.Surface,
        combat_effects: dict,
        x: int,
        y: int,
    ) -> None:
        """Draw small colored labels for active combat status effects."""
        font = self._small_font
        if font is None:
            return
        cx = x
        for name, effect in combat_effects.items():
            remaining = max(0, effect.duration)
            color = effect.color
            label = f"{name.upper()} {remaining:.1f}s"
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
        right_aligned: bool = False,
    ) -> None:
        """Draw a single health bar with a type label above it.

        Args:
            right_aligned: When True (AI bars), the label is right-aligned to the
                           bar's right edge and HP text is placed to the LEFT of the
                           bar so neither element overflows the screen edge.
        """
        label = self._font.render(tank.tank_type, True, COLOR_WHITE)
        if right_aligned:
            label_x = x + HUD_BAR_WIDTH - label.get_width()
        else:
            label_x = x
        surface.blit(label, (label_x, label_y))

        pygame.draw.rect(surface, COLOR_GRAY, (x, y, HUD_BAR_WIDTH, HUD_BAR_HEIGHT))

        fill_w = int(HUD_BAR_WIDTH * tank.health_ratio)
        fill_color = COLOR_GREEN if tank.health_ratio > 0.4 else COLOR_RED
        if fill_w > 0:
            pygame.draw.rect(surface, fill_color, (x, y, fill_w, HUD_BAR_HEIGHT))

        hp_text = self._small_font.render(
            f"{tank.health}/{tank.max_health}", True, COLOR_WHITE
        )
        if right_aligned:
            hp_text_x = x - hp_text.get_width() - 8
        else:
            hp_text_x = x + HUD_BAR_WIDTH + 6
        surface.blit(hp_text, (hp_text_x, y + 1))
