"""
game/scenes/tank_select_scene.py

TankSelectScene — pre-match tank selection screen.

Flow:
    MainMenuScene (ENTER) → TankSelectScene → (confirm) → GameplayScene

Layout:
    Four cards displayed horizontally, centred on screen.
    LEFT / RIGHT (or A / D) navigate between cards.
    ENTER or SPACE confirms and starts the match.
    ESC cancels and returns to the main menu.

Each card shows:
    - Tank type name
    - Single-sentence description
    - A small placeholder sprite (rect + barrel indicator)
    - Four stat bars: Speed, Health, Turn, Fire Rate
      (normalised relative to the per-stat maximum across all tank types)
    - LOCKED overlay (padlock label + reduced opacity) for unavailable tanks

Locked state is determined by SaveManager — no writes happen here.
Selection is passed to GameplayScene via switch_to(SCENE_GAME, tank_type=…).
"""

import math

import pygame

from game.scenes.base_scene import BaseScene
from game.utils.config_loader import load_yaml
from game.utils.constants import (
    COLOR_BG,
    COLOR_DARK_GRAY,
    COLOR_GRAY,
    COLOR_RED,
    COLOR_WHITE,
    MAX_BAR_WIDTH,
    SCENE_GAME,
    SCENE_MENU,
    SCENE_TANK_SELECT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TANK_BARREL_COLOR,
    TANK_BARREL_HEIGHT,
    TANK_BARREL_WIDTH,
    TANK_BODY_HEIGHT,
    TANK_BODY_WIDTH,
    TANK_SELECT_COLORS,
    TANK_STAT_MAX,
    TANKS_CONFIG,
)
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layout constants (all in screen pixels, not exported to constants.py —
# they are internal to this scene only)
# ---------------------------------------------------------------------------
_CARD_W: int = 220
_CARD_H: int = 360
_CARD_GAP: int = 30          # horizontal gap between cards
_CARD_TOP: int = 130         # y position of card top edge
_CARD_RADIUS: int = 10       # rounded-corner radius

_SELECTED_BORDER_W: int = 3  # border thickness for the active card
_LOCKED_ALPHA: int = 80      # surface alpha for locked card content overlay

_STAT_BAR_H: int = 10        # height of each stat bar
_STAT_ROW_GAP: int = 22      # vertical distance between stat rows
_STATS: list = [             # (display label, tanks.yaml key)
    ("Speed",     "speed"),
    ("Health",    "health"),
    ("Turn",      "turn_rate"),
    ("Fire Rate", "fire_rate"),
]

# Display order of tank types — matches the 4-card layout left-to-right
_TANK_ORDER: list = ["light_tank", "medium_tank", "heavy_tank", "scout_tank"]

# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def _normalise(value: float, stat_key: str) -> float:
    """Return value / max_stat, clamped to [0.0, 1.0]."""
    maximum = TANK_STAT_MAX.get(stat_key, 1.0)
    if maximum <= 0:
        return 0.0
    return max(0.0, min(1.0, value / maximum))


class TankSelectScene(BaseScene):
    """Pre-match tank selection UI."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._save_manager: SaveManager = SaveManager()
        self._tank_data: list[dict] = []      # ordered list of tank config dicts
        self._unlocked: set[str] = set()
        self._cursor: int = 0                 # index into _tank_data

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        # Reload data every entry so unlocks gained mid-session are reflected.
        all_tanks = load_yaml(TANKS_CONFIG)
        self._tank_data = []
        for t in _TANK_ORDER:
            cfg = all_tanks.get(t, {})
            cfg = dict(cfg)
            cfg.setdefault("type", t)
            self._tank_data.append(cfg)

        profile = self._save_manager.load_profile()
        self._unlocked = set(profile.get("unlocked_tanks", []))

        # Start cursor on the first unlocked tank
        self._cursor = 0
        for i, td in enumerate(self._tank_data):
            if td["type"] in self._unlocked:
                self._cursor = i
                break

        log.info(
            "TankSelectScene entered. Unlocked: %s  cursor=%d",
            sorted(self._unlocked), self._cursor,
        )

    def on_exit(self) -> None:
        log.debug("TankSelectScene exited.")

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_LEFT, pygame.K_a):
            self._cursor = (self._cursor - 1) % len(self._tank_data)

        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._cursor = (self._cursor + 1) % len(self._tank_data)

        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm_selection()

        elif event.key == pygame.K_ESCAPE:
            log.info("TankSelectScene: ESC — returning to main menu.")
            self.manager.switch_to(SCENE_MENU)

    def _confirm_selection(self) -> None:
        """Validate that the current card is unlocked, then start the match."""
        selected = self._tank_data[self._cursor]
        tank_type = selected.get("type", "medium_tank")
        if tank_type not in self._unlocked:
            log.debug("TankSelectScene: '%s' is locked — ignoring confirm.", tank_type)
            return
        log.info("TankSelectScene: confirmed '%s' — switching to game.", tank_type)
        self.manager.switch_to(SCENE_GAME, tank_type=tank_type)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        pass  # No animations this milestone

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        self._draw_header(surface)
        self._draw_cards(surface)
        self._draw_footer(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 52)
        heading = font.render("Select Your Tank", True, COLOR_WHITE)
        surface.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 60)))

    def _draw_footer(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 28)
        hint = font.render(
            "◄ ► / A D  Navigate     ENTER / SPACE  Confirm     ESC  Back",
            True, COLOR_GRAY,
        )
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 36)))

    def _draw_cards(self, surface: pygame.Surface) -> None:
        n = len(self._tank_data)
        total_w = n * _CARD_W + (n - 1) * _CARD_GAP
        start_x = (SCREEN_WIDTH - total_w) // 2

        for i, td in enumerate(self._tank_data):
            card_x = start_x + i * (_CARD_W + _CARD_GAP)
            card_rect = pygame.Rect(card_x, _CARD_TOP, _CARD_W, _CARD_H)
            is_selected = (i == self._cursor)
            tank_type = td.get("type", "")
            is_locked = tank_type not in self._unlocked
            color = TANK_SELECT_COLORS.get(tank_type, COLOR_GRAY)

            self._draw_card(surface, card_rect, td, color, is_selected, is_locked)

    def _draw_card(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        td: dict,
        color: tuple,
        is_selected: bool,
        is_locked: bool,
    ) -> None:
        # --- Background ---
        bg_color = (50, 50, 55) if is_selected else (32, 32, 36)
        pygame.draw.rect(surface, bg_color, rect, border_radius=_CARD_RADIUS)

        # --- Selected border ---
        if is_selected:
            pygame.draw.rect(surface, color, rect, width=_SELECTED_BORDER_W,
                             border_radius=_CARD_RADIUS)

        cx = rect.centerx
        y = rect.top + 18

        # --- Tank name ---
        name_font = pygame.font.SysFont(None, 32)
        name_text = td.get("type", "").replace("_", " ").title()
        rendered_name = name_font.render(name_text, True, COLOR_WHITE if not is_locked else COLOR_GRAY)
        surface.blit(rendered_name, rendered_name.get_rect(center=(cx, y)))
        y += 36

        # --- Mini sprite ---
        sprite_color = color if not is_locked else COLOR_DARK_GRAY
        sprite_cy = y + TANK_BODY_HEIGHT // 2 + 10
        self._draw_mini_sprite(surface, cx, sprite_cy, sprite_color)
        y = sprite_cy + TANK_BODY_HEIGHT // 2 + 20

        # --- Description ---
        desc_font = pygame.font.SysFont(None, 22)
        desc = td.get("description", "")
        self._draw_wrapped(surface, desc_font, desc, COLOR_GRAY, cx, y, _CARD_W - 24)
        y += 46

        # --- Stat bars ---
        stat_label_font = pygame.font.SysFont(None, 22)
        bar_left = rect.left + 16
        for label, key in _STATS:
            raw = float(td.get(key, 0.0))
            ratio = _normalise(raw, key)
            bar_w = int(ratio * MAX_BAR_WIDTH)

            lbl = stat_label_font.render(label, True, COLOR_GRAY)
            surface.blit(lbl, (bar_left, y))

            bar_y = y + 14
            # Track (background)
            track_rect = pygame.Rect(bar_left, bar_y, MAX_BAR_WIDTH, _STAT_BAR_H)
            pygame.draw.rect(surface, (55, 55, 60), track_rect, border_radius=3)
            # Fill
            if bar_w > 0:
                fill_color = color if not is_locked else COLOR_DARK_GRAY
                fill_rect = pygame.Rect(bar_left, bar_y, bar_w, _STAT_BAR_H)
                pygame.draw.rect(surface, fill_color, fill_rect, border_radius=3)

            y += _STAT_ROW_GAP

        # --- Locked overlay ---
        if is_locked:
            self._draw_locked_overlay(surface, rect)

    def _draw_mini_sprite(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        color: tuple,
    ) -> None:
        """Render the same rect+barrel placeholder used in gameplay."""
        body_rect = pygame.Rect(0, 0, TANK_BODY_WIDTH, TANK_BODY_HEIGHT)
        body_rect.center = (cx, cy)
        pygame.draw.rect(surface, color, body_rect, border_radius=4)

        # Barrel pointing right (angle = 0) — same convention as game world
        barrel_rect = pygame.Rect(
            cx,
            cy - TANK_BARREL_HEIGHT // 2,
            TANK_BARREL_WIDTH,
            TANK_BARREL_HEIGHT,
        )
        pygame.draw.rect(surface, TANK_BARREL_COLOR, barrel_rect)

    def _draw_locked_overlay(
        self, surface: pygame.Surface, rect: pygame.Rect
    ) -> None:
        """Darken the card and stamp a LOCKED label."""
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, rect.topleft)

        lock_font = pygame.font.SysFont(None, 36)
        lock_surf = lock_font.render("LOCKED", True, COLOR_RED)
        surface.blit(lock_surf, lock_surf.get_rect(center=rect.center))

    @staticmethod
    def _draw_wrapped(
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        color: tuple,
        cx: int,
        y: int,
        max_width: int,
    ) -> None:
        """Render text word-wrapped to max_width, centred at cx."""
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        line_h = font.get_linesize()
        for line in lines:
            rendered = font.render(line, True, color)
            surface.blit(rendered, rendered.get_rect(center=(cx, y)))
            y += line_h

    # ------------------------------------------------------------------
    # Public helpers (used by tests without pygame display)
    # ------------------------------------------------------------------

    def is_locked(self, tank_type: str) -> bool:
        """Return True if tank_type is not in the current unlocked set."""
        return tank_type not in self._unlocked

    def can_select(self, tank_type: str) -> bool:
        """Return True if tank_type exists in tank_data and is unlocked."""
        types = [td.get("type") for td in self._tank_data]
        return tank_type in types and tank_type in self._unlocked
