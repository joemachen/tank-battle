"""
game/scenes/menu_scene.py

MainMenuScene — fully polished main menu, v0.12.

Visual design:
  - Dark background + animated perspective grid (outrun/synthwave)
  - Scanline CRT overlay
  - "TANK BATTLE" title with neon glow effect, slides + fades in on enter
  - Neon-pink selected item, dimmed white for unselected items
  - Player level badge + XP progress bar (bottom-left)
  - Version string (bottom-right)

Navigation:
  UP / DOWN (or W / S)  — move cursor
  ENTER / SPACE         — confirm selection
  PLAY           → fade to black → LoadoutScene
  SETTINGS       → SettingsScene
  SWITCH PROFILE → ProfileSelectScene
  QUIT           → pygame.QUIT event (clean exit)
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.systems.progression_manager import ProgressionManager
from game.ui.audio_manager import get_audio_manager
from game.ui.components import FadeTransition, ScrollingGrid
from game.utils.constants import (
    COLOR_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_NEON_PINK,
    GAME_VERSION,
    MENU_FADE_DURATION,
    MENU_TITLE_ANIM_DURATION,
    MUSIC_MENU,
    SCENE_LOADOUT,
    SCENE_PROFILE_SELECT,
    SCENE_PROGRESSION,
    SCENE_SETTINGS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
)
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
_CX: int = SCREEN_WIDTH // 2

_TITLE_Y: int = 155                # title centre y (pixels from top)
_TITLE_FONT_SIZE: int = 112
_TITLE_SLIDE_OFFSET: int = 70      # pixels above final pos at animation start

_ITEMS: list[str] = ["PLAY", "PROGRESSION", "SETTINGS", "SWITCH PROFILE", "QUIT"]
_ITEM_FONT_SIZE: int = 52
_ITEMS_Y_START: int = 320          # centre y of first item
_ITEMS_SPACING: int = 64

_CURSOR_GAP: int = 14              # pixels between ">" right edge and item left edge

_COLOR_ITEM_DIM: tuple = (153, 153, 153)   # unselected items: white at 60%
_COLOR_GLOW: tuple = (51, 3, 48)           # dark neon-pink for glow offset layers

_BADGE_MARGIN: int = 20
_BADGE_BAR_W: int = 110
_BADGE_BAR_H: int = 9
_VERSION_MARGIN: int = 16

_SCANLINE_ALPHA: int = 18


class MainMenuScene(BaseScene):
    """Animated synthwave main menu with perspective grid and title glow."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._grid: ScrollingGrid = ScrollingGrid()
        self._fade: FadeTransition = FadeTransition(MENU_FADE_DURATION)
        self._title_timer: float = 0.0
        self._cursor: int = 0
        self._save_manager: SaveManager = SaveManager()
        self._progression: ProgressionManager = ProgressionManager()
        self._profile: dict = {}
        self._scanline_surf: pygame.Surface | None = None
        self._title_font: pygame.font.Font | None = None
        self._item_font: pygame.font.Font | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        self._title_timer = 0.0
        self._cursor = 0
        self._profile = self._save_manager.load_profile()

        # Load profile name for "Playing as: X" display
        idx = self._save_manager.load_profiles_index()
        slot = str(idx.get("active_slot", 0))
        slot_meta = idx.get("profiles", {}).get(slot, {})
        self._profile_name: str = slot_meta.get("name", "")

        # Rewire fade callback each enter (manager ref is always current)
        # If no profile exists, PLAY routes to profile select instead of loadout
        if self._profile_name:
            self._fade.reset(on_complete=lambda: self.manager.switch_to(SCENE_LOADOUT))
        else:
            self._fade.reset(on_complete=lambda: self.manager.switch_to(SCENE_PROFILE_SELECT))

        # Build scanline overlay once (expensive, never changes)
        if self._scanline_surf is None:
            self._scanline_surf = _build_scanline_surf(
                SCREEN_WIDTH, SCREEN_HEIGHT, _SCANLINE_ALPHA
            )

        # Cache fonts (SysFont allocation is non-trivial on some systems)
        if self._title_font is None:
            self._title_font = pygame.font.SysFont(None, _TITLE_FONT_SIZE)
        if self._item_font is None:
            self._item_font = pygame.font.SysFont(None, _ITEM_FONT_SIZE)

        get_audio_manager().play_music(MUSIC_MENU)
        log.info("MainMenuScene entered.  Level=%d", self._profile.get("level", 1))

    def on_exit(self) -> None:
        log.debug("MainMenuScene exited.")

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._fade.is_active:
            return   # block all input during fade-out

        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self._cursor = (self._cursor - 1) % len(_ITEMS)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self._cursor = (self._cursor + 1) % len(_ITEMS)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate()

    def _activate(self) -> None:
        item = _ITEMS[self._cursor]
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        if item == "PLAY":
            self._fade.start()
        elif item == "PROGRESSION":
            self.manager.switch_to(SCENE_PROGRESSION)
        elif item == "SETTINGS":
            self.manager.switch_to(SCENE_SETTINGS)
        elif item == "SWITCH PROFILE":
            self.manager.switch_to(SCENE_PROFILE_SELECT)
        elif item == "QUIT":
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._grid.update(dt)
        if self._title_timer < MENU_TITLE_ANIM_DURATION:
            self._title_timer = min(self._title_timer + dt, MENU_TITLE_ANIM_DURATION)
        if self._fade.is_active:
            self._fade.update(dt)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        self._grid.draw(surface)
        if self._scanline_surf:
            surface.blit(self._scanline_surf, (0, 0))
        self._draw_title(surface)
        self._draw_items(surface)
        self._draw_level_badge(surface)
        self._draw_version(surface)
        self._fade.draw(surface)   # overlay — must be last

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_title(self, surface: pygame.Surface) -> None:
        font = self._title_font
        text = "TANK BATTLE"

        # Ease-out quad: fast start, smooth arrival
        t = min(1.0, self._title_timer / MENU_TITLE_ANIM_DURATION)
        ease = 1.0 - (1.0 - t) ** 2

        # Colour lerps from black → neon target (gives a natural fade-in feel)
        title_color = tuple(int(c * ease) for c in COLOR_NEON_PINK)
        glow_color  = tuple(int(c * ease) for c in _COLOR_GLOW)

        # Y slides from above the final position downward
        y = int(_TITLE_Y - _TITLE_SLIDE_OFFSET * (1.0 - ease))

        # Glow: draw at 12 offset positions in dim neon-pink, behind clean text
        for dx, dy in (
            (-3, 0), (3, 0), (0, -3), (0, 3),
            (-2, -2), (2, -2), (-2, 2), (2, 2),
            (-1, 0), (1, 0), (0, -1), (0, 1),
        ):
            gs = font.render(text, True, glow_color)
            surface.blit(gs, gs.get_rect(center=(_CX + dx, y + dy)))

        # Clean title on top
        ts = font.render(text, True, title_color)
        surface.blit(ts, ts.get_rect(center=(_CX, y)))

    def _draw_items(self, surface: pygame.Surface) -> None:
        font = self._item_font
        cur_font = pygame.font.SysFont(None, _ITEM_FONT_SIZE)

        for i, label in enumerate(_ITEMS):
            y = _ITEMS_Y_START + i * _ITEMS_SPACING
            color = COLOR_NEON_PINK if i == self._cursor else _COLOR_ITEM_DIM
            item_s = font.render(label, True, color)
            item_r = item_s.get_rect(center=(_CX, y))
            surface.blit(item_s, item_r)

            if i == self._cursor:
                cur_s = cur_font.render(">", True, COLOR_NEON_PINK)
                surface.blit(cur_s, cur_s.get_rect(midright=(item_r.left - _CURSOR_GAP, y)))

    def _draw_level_badge(self, surface: pygame.Surface) -> None:
        """Bottom-left: LVL N  [======>   ]  xxx / yyy XP"""
        level = int(self._profile.get("level", 1))
        xp    = int(self._profile.get("xp", 0))

        next_xp  = self._progression.next_level_xp(xp)
        level_xp = self._progression.xp_for_level(level)

        if next_xp is not None and next_xp > level_xp:
            ratio    = max(0.0, min(1.0, (xp - level_xp) / (next_xp - level_xp)))
            xp_label = f"{xp} / {next_xp} XP"
        else:
            ratio    = 1.0
            xp_label = f"{xp} XP  (MAX)"

        font   = pygame.font.SysFont(None, 22)
        line_h = font.get_linesize()
        bx     = _BADGE_MARGIN
        by     = SCREEN_HEIGHT - _BADGE_MARGIN - line_h

        lvl_s = font.render(f"LVL {level}", True, COLOR_GRAY)
        surface.blit(lvl_s, (bx, by))

        bar_x = bx + lvl_s.get_width() + 8
        bar_y = by + (line_h - _BADGE_BAR_H) // 2
        bar_r = pygame.Rect(bar_x, bar_y, _BADGE_BAR_W, _BADGE_BAR_H)
        pygame.draw.rect(surface, (40, 40, 45), bar_r, border_radius=3)
        if ratio > 0:
            fill_r = pygame.Rect(bar_x, bar_y, int(_BADGE_BAR_W * ratio), _BADGE_BAR_H)
            pygame.draw.rect(surface, COLOR_GREEN, fill_r, border_radius=3)
        pygame.draw.rect(surface, (55, 55, 60), bar_r, 1, border_radius=3)

        xp_s = font.render(xp_label, True, COLOR_GRAY)
        surface.blit(xp_s, (bar_x + _BADGE_BAR_W + 8, by))

        # "Playing as: Name" — subtle, just below the XP bar
        if getattr(self, "_profile_name", ""):
            name_s = font.render(f"Playing as:  {self._profile_name}", True, COLOR_GRAY)
            surface.blit(name_s, (_BADGE_MARGIN, SCREEN_HEIGHT - name_s.get_height() - 4))

    def _draw_version(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 20)
        ver  = font.render(GAME_VERSION, True, COLOR_GRAY)
        surface.blit(
            ver,
            (SCREEN_WIDTH  - ver.get_width()  - _VERSION_MARGIN,
             SCREEN_HEIGHT - ver.get_height() - _VERSION_MARGIN),
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _build_scanline_surf(width: int, height: int, alpha: int) -> pygame.Surface:
    """
    Build a full-screen CRT scanline overlay.  Called once; result is cached.
    Alternating fully-transparent and semi-black horizontal strips.
    """
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    line_color = (0, 0, 0, alpha)
    for y in range(0, height, 2):
        pygame.draw.line(surf, line_color, (0, y), (width, y))
    return surf
