"""
game/scenes/map_select_scene.py

MapSelectScene — pre-match map selection screen (v0.17).

Flow:
    WeaponSelectScene (ENTER) → MapSelectScene → (ENTER) → GameplayScene
                                              → (ESC)    → WeaponSelectScene

Layout:
    Three map cards displayed horizontally across the screen.
    Each card shows:
        - Map name (large)
        - Theme name + ambient label
        - Obstacle count
        - Mini-preview thumbnail (obstacle rects at small scale on theme floor color)
        - Theme accent color as card border highlight

Controls:
    LEFT / RIGHT    — cycle between map cards
    ENTER / SPACE   — confirm selection and start match
    ESC             — return to WeaponSelectScene (preserves tank_type / weapon_types)
"""

import os

import pygame

from game.scenes.base_scene import BaseScene
from game.ui.audio_manager import get_audio_manager
from game.utils.constants import (
    COLOR_BG,
    COLOR_DARK_GRAY,
    COLOR_GRAY,
    COLOR_WHITE,
    DEFAULT_MAP,
    MAPS_DIR,
    SCENE_GAME,
    SCENE_WEAPON_SELECT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
)
from game.utils.logger import get_logger
from game.utils.map_loader import load_map

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

_CARD_W: int = 340
_CARD_H: int = 460
_CARD_GAP: int = 40
_CARDS_TOTAL_W: int = 3 * _CARD_W + 2 * _CARD_GAP
_CARDS_LEFT: int = (SCREEN_WIDTH - _CARDS_TOTAL_W) // 2
_CARDS_TOP: int = 90

_PREVIEW_W: int = 300
_PREVIEW_H: int = 200
_PREVIEW_ARENA_W: int = 1600
_PREVIEW_ARENA_H: int = 1200

_TITLE_Y: int = 26
_HINT_Y: int = SCREEN_HEIGHT - 30

# Neon-pink highlight for the selected card border
_COLOR_SELECTED: tuple = (255, 16, 240)

# Map registry — ordered list of map stems (filenames without .yaml)
_MAP_NAMES: list[str] = ["map_01", "map_02", "map_03"]


def _map_path(map_name: str) -> str:
    return os.path.join(MAPS_DIR, f"{map_name}.yaml")


def _build_preview(map_data: dict, w: int, h: int) -> pygame.Surface:
    """
    Render a top-down mini-preview of the map layout.

    Obstacles are drawn as tinted colored rects at the same proportional
    position they occupy in the 1600×1200 arena.
    """
    surf = pygame.Surface((w, h))
    theme = map_data.get("theme", {})
    floor_col = tuple(theme.get("floor_color", [20, 30, 20]))
    tint = tuple(theme.get("obstacle_tint", [100, 100, 100]))
    surf.fill(floor_col)

    scale_x = w / _PREVIEW_ARENA_W
    scale_y = h / _PREVIEW_ARENA_H

    for obs in map_data.get("obstacles", []):
        rx = int(obs.x * scale_x)
        ry = int(obs.y * scale_y)
        rw = max(2, int(obs.width * scale_x))
        rh = max(2, int(obs.height * scale_y))
        # Blend obstacle's material color with the theme tint for a cohesive preview
        obs_col = tuple(
            max(0, min(255, (c + t) // 2))
            for c, t in zip(obs.color, tint)
        )
        pygame.draw.rect(surf, obs_col, (rx, ry, rw, rh))

    # Thin border around preview surface
    border_col = tuple(theme.get("border_color", [60, 80, 60]))
    pygame.draw.rect(surf, border_col, (0, 0, w, h), 2)
    return surf


class MapSelectScene(BaseScene):
    """
    Horizontal card picker for selecting the match arena.
    Receives tank_type, ai_count, weapon_types from WeaponSelectScene
    and passes them forward to GameplayScene on confirm.
    """

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._cursor: int = 0          # index into _MAP_NAMES
        self._map_data: list[dict] = []
        self._previews: list[pygame.Surface] = []
        # Forwarded kwargs from WeaponSelectScene
        self._tank_type: str = ""
        self._ai_count: int = 1
        self._weapon_types: list[str] = []

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        self._tank_type   = kwargs.get("tank_type", "medium_tank")
        self._ai_count    = int(kwargs.get("ai_count", 1))
        raw_wt = kwargs.get("weapon_types", ["standard_shell"])
        self._weapon_types = list(raw_wt) if not isinstance(raw_wt, str) else [raw_wt]

        # Preserve cursor position if the player came back via ESC
        if not (0 <= self._cursor < len(_MAP_NAMES)):
            self._cursor = 0

        # Load all map data and build previews
        self._map_data = [load_map(_map_path(n)) for n in _MAP_NAMES]
        self._previews = [
            _build_preview(md, _PREVIEW_W, _PREVIEW_H)
            for md in self._map_data
        ]
        log.info(
            "MapSelectScene entered. tank=%s  weapons=%s  maps=%s",
            self._tank_type, self._weapon_types, _MAP_NAMES,
        )

    def on_exit(self) -> None:
        self._map_data = []
        self._previews = []

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_LEFT, pygame.K_a):
            self._cursor = (self._cursor - 1) % len(_MAP_NAMES)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._cursor = (self._cursor + 1) % len(_MAP_NAMES)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm()

        elif event.key == pygame.K_ESCAPE:
            # Return to WeaponSelectScene preserving loadout context
            self.manager.switch_to(
                SCENE_WEAPON_SELECT,
                tank_type=self._tank_type,
                ai_count=self._ai_count,
                weapon_types=self._weapon_types,
            )

    # ------------------------------------------------------------------
    # Update (no-op — UI scene)
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        pass

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        font_title = pygame.font.SysFont(None, 46)
        font_large = pygame.font.SysFont(None, 34)
        font_small = pygame.font.SysFont(None, 24)
        font_hint  = pygame.font.SysFont(None, 22)

        # Screen title
        title = font_title.render("SELECT MAP", True, COLOR_WHITE)
        surface.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, _TITLE_Y))

        # Cards
        for i, (map_name, map_data, preview) in enumerate(
            zip(_MAP_NAMES, self._map_data, self._previews)
        ):
            cx = _CARDS_LEFT + i * (_CARD_W + _CARD_GAP)
            cy = _CARDS_TOP
            is_sel = i == self._cursor
            self._draw_card(
                surface, cx, cy, map_name, map_data, preview,
                is_sel, font_large, font_small,
            )

        # Bottom hint bar
        hint = font_hint.render(
            "← → Navigate    ENTER Confirm    ESC Back",
            True, COLOR_GRAY,
        )
        surface.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2, _HINT_Y))

    def _draw_card(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        map_name: str,
        map_data: dict,
        preview: pygame.Surface,
        selected: bool,
        font_large: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        theme     = map_data.get("theme", {})
        disp_name = map_data.get("name", map_name)
        theme_name    = theme.get("name", "—")
        ambient   = theme.get("ambient_label", "")
        obs_count = len(map_data.get("obstacles", []))
        accent    = tuple(theme.get("border_color", [60, 80, 60]))

        # Card background
        card_rect = pygame.Rect(cx, cy, _CARD_W, _CARD_H)
        pygame.draw.rect(surface, COLOR_DARK_GRAY, card_rect, border_radius=8)

        # Border: thick neon-pink when selected, thin accent otherwise
        border_col   = _COLOR_SELECTED if selected else accent
        border_thick = 3 if selected else 1
        pygame.draw.rect(surface, border_col, card_rect, border_thick, border_radius=8)

        # Mini-preview thumbnail
        px = cx + (_CARD_W - _PREVIEW_W) // 2
        py = cy + 16
        surface.blit(preview, (px, py))

        # Map name
        name_surf = font_large.render(disp_name, True, COLOR_WHITE)
        surface.blit(name_surf, (cx + (_CARD_W - name_surf.get_width()) // 2, py + _PREVIEW_H + 14))

        # Theme label line
        theme_line = f"{theme_name}  ·  {ambient}" if ambient else theme_name
        theme_surf = font_small.render(theme_line, True, accent if not selected else _COLOR_SELECTED)
        surface.blit(theme_surf, (cx + (_CARD_W - theme_surf.get_width()) // 2, py + _PREVIEW_H + 46))

        # Obstacle count
        obs_surf = font_small.render(f"{obs_count} obstacles", True, COLOR_GRAY)
        surface.blit(obs_surf, (cx + (_CARD_W - obs_surf.get_width()) // 2, py + _PREVIEW_H + 70))

        # "SELECTED" label on active card
        if selected:
            sel_surf = font_small.render("▶  SELECTED  ◀", True, _COLOR_SELECTED)
            surface.blit(sel_surf, (cx + (_CARD_W - sel_surf.get_width()) // 2, cy + _CARD_H - 36))

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------

    def _confirm(self) -> None:
        map_name = _MAP_NAMES[self._cursor]
        log.info(
            "MapSelectScene: confirmed map=%s  tank=%s  weapons=%s",
            map_name, self._tank_type, self._weapon_types,
        )
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        self.manager.switch_to(
            SCENE_GAME,
            tank_type=self._tank_type,
            ai_count=self._ai_count,
            weapon_types=self._weapon_types,
            map_name=map_name,
        )
