"""
game/scenes/tank_select_scene.py

TankSelectScene — pre-match tank selection screen.

Flow:
    MainMenuScene (ENTER) → TankSelectScene → (confirm) → GameplayScene

Layout (two interactive rows, navigated separately):
    Row 0 — Tank cards  (LEFT/RIGHT or A/D)
    Row 1 — Opponents   (LEFT/RIGHT when row focused; UP/DOWN switches row)

Controls:
    UP / DOWN   — switch focus between rows
    LEFT / RIGHT (or A / D on tank row) — navigate within focused row
    ENTER / SPACE — confirm and start match
    ESC — return to main menu

AI difficulty is read from settings.json by GameplayScene on on_enter().

Selection is passed to GameplayScene via:
    switch_to(SCENE_GAME, tank_type=…, ai_count=…)
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.systems.progression_manager import ProgressionManager
from game.ui.audio_manager import get_audio_manager
from game.utils.config_loader import load_yaml
from game.utils.constants import (
    COLOR_BG,
    COLOR_DARK_GRAY,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_WHITE,
    MAX_BAR_WIDTH,
    MUSIC_MENU,
    SCENE_GAME,
    SCENE_MENU,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
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
# Layout constants (internal to this scene)
# ---------------------------------------------------------------------------
_CARD_W: int = 220
_CARD_H: int = 360
_CARD_GAP: int = 30
_CARD_TOP: int = 110
_CARD_RADIUS: int = 10
_SELECTED_BORDER_W: int = 3

_STAT_BAR_H: int = 10
_STAT_ROW_GAP: int = 22
_STATS: list = [
    ("Speed",     "speed"),
    ("Health",    "health"),
    ("Turn",      "turn_rate"),
    ("Fire Rate", "fire_rate"),
]

# Selector rows (below the cards)
_ROW_Y: int = _CARD_TOP + _CARD_H + 22   # top of first selector row
_ROW_H: int = 42                          # height of each selector row

# Row indices
_ROW_TANKS: int = 0
_ROW_OPPONENTS: int = 1

_OPPONENT_COUNTS: list = [1, 2, 3]
_DEFAULT_OPPONENT_IDX: int = 0   # 1 opponent by default

# Display order of tank types — matches the 4-card layout left-to-right
_TANK_ORDER: list = ["light_tank", "medium_tank", "heavy_tank", "scout_tank"]

# ---------------------------------------------------------------------------
# Module-level helper (exported for tests)
# ---------------------------------------------------------------------------

def _normalise(value: float, stat_key: str) -> float:
    """Return value / max_stat, clamped to [0.0, 1.0]."""
    maximum = TANK_STAT_MAX.get(stat_key, 1.0)
    if maximum <= 0:
        return 0.0
    return max(0.0, min(1.0, value / maximum))


class TankSelectScene(BaseScene):
    """Pre-match tank and match-settings selection UI."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._save_manager: SaveManager = SaveManager()
        self._progression: ProgressionManager = ProgressionManager()
        self._tank_data: list[dict] = []
        self._unlocked: set[str] = set()
        self._tank_cursor: int = 0          # index into _tank_data
        self._opponent_idx: int = _DEFAULT_OPPONENT_IDX
        self._focused_row: int = _ROW_TANKS  # which row has keyboard focus
        self._player_level: int = 1          # loaded from profile on on_enter
        self._unlock_levels: dict[str, int] = {}  # tank_type → unlock level

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        all_tanks = load_yaml(TANKS_CONFIG)
        self._tank_data = []
        for t in _TANK_ORDER:
            cfg = all_tanks.get(t, {})
            cfg = dict(cfg)
            cfg.setdefault("type", t)
            self._tank_data.append(cfg)

        profile = self._save_manager.load_profile()
        self._unlocked = set(profile.get("unlocked_tanks", []))
        self._player_level = int(profile.get("level", 1))
        # Build unlock level lookup for locked card display
        self._unlock_levels = {}
        for td in self._tank_data:
            t = td.get("type", "")
            lvl = self._progression.unlock_level_for(t)
            if lvl is not None:
                self._unlock_levels[t] = lvl

        # Cursor on first unlocked tank
        self._tank_cursor = 0
        for i, td in enumerate(self._tank_data):
            if td["type"] in self._unlocked:
                self._tank_cursor = i
                break

        # Reset selector row
        self._opponent_idx = _DEFAULT_OPPONENT_IDX
        self._focused_row = _ROW_TANKS

        get_audio_manager().play_music(MUSIC_MENU)

        log.info(
            "TankSelectScene entered. Unlocked: %s  cursor=%d",
            sorted(self._unlocked), self._tank_cursor,
        )

    def on_exit(self) -> None:
        log.debug("TankSelectScene exited.")

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_ESCAPE:
            log.info("TankSelectScene: ESC — returning to main menu.")
            self.manager.switch_to(SCENE_MENU)
            return

        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm_selection()
            return

        # UP / DOWN switches which row has focus
        if event.key == pygame.K_UP:
            self._focused_row = max(0, self._focused_row - 1)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
            return
        if event.key == pygame.K_DOWN:
            self._focused_row = min(_ROW_OPPONENTS, self._focused_row + 1)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
            return

        # LEFT / RIGHT navigate within the focused row
        left = event.key in (pygame.K_LEFT, pygame.K_a)
        right = event.key in (pygame.K_RIGHT, pygame.K_d)
        if not (left or right):
            return

        delta = -1 if left else 1
        if self._focused_row == _ROW_TANKS:
            self._tank_cursor = (self._tank_cursor + delta) % len(self._tank_data)
        elif self._focused_row == _ROW_OPPONENTS:
            self._opponent_idx = (self._opponent_idx + delta) % len(_OPPONENT_COUNTS)
        get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

    def _confirm_selection(self) -> None:
        selected = self._tank_data[self._tank_cursor]
        tank_type = selected.get("type", "medium_tank")
        if tank_type not in self._unlocked:
            log.debug("TankSelectScene: '%s' is locked — ignoring confirm.", tank_type)
            return
        ai_count = _OPPONENT_COUNTS[self._opponent_idx]
        log.info(
            "TankSelectScene: confirmed tank=%s  opponents=%d",
            tank_type, ai_count,
        )
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        self.manager.switch_to(
            SCENE_GAME,
            tank_type=tank_type,
            ai_count=ai_count,
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        pass

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        self._draw_header(surface)
        self._draw_level_badge(surface)
        self._draw_cards(surface)
        self._draw_opponent_row(surface)
        self._draw_footer(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 52)
        heading = font.render("Select Your Tank", True, COLOR_WHITE)
        surface.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 55)))

    def _draw_level_badge(self, surface: pygame.Surface) -> None:
        """Small 'Level N' label in the top-right corner."""
        font = pygame.font.SysFont(None, 28)
        label = font.render(f"Level {self._player_level}", True, COLOR_GREEN)
        margin = 18
        surface.blit(label, (SCREEN_WIDTH - label.get_width() - margin, margin))

    def _draw_footer(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 26)
        hint = font.render(
            "▲ ▼  Switch Row     ◄ ►  Navigate     ENTER  Confirm     ESC  Back",
            True, COLOR_GRAY,
        )
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 26)))

    def _draw_cards(self, surface: pygame.Surface) -> None:
        n = len(self._tank_data)
        total_w = n * _CARD_W + (n - 1) * _CARD_GAP
        start_x = (SCREEN_WIDTH - total_w) // 2

        for i, td in enumerate(self._tank_data):
            card_x = start_x + i * (_CARD_W + _CARD_GAP)
            card_rect = pygame.Rect(card_x, _CARD_TOP, _CARD_W, _CARD_H)
            is_selected = (i == self._tank_cursor) and (self._focused_row == _ROW_TANKS)
            is_focused_row = (self._focused_row == _ROW_TANKS)
            tank_type = td.get("type", "")
            is_locked = tank_type not in self._unlocked
            color = TANK_SELECT_COLORS.get(tank_type, COLOR_GRAY)

            # Dim cards when a different row has focus
            if not is_focused_row:
                color = _dim_color(color)

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
        bg_color = (50, 50, 55) if is_selected else (32, 32, 36)
        pygame.draw.rect(surface, bg_color, rect, border_radius=_CARD_RADIUS)

        if is_selected:
            pygame.draw.rect(surface, color, rect, width=_SELECTED_BORDER_W,
                             border_radius=_CARD_RADIUS)

        cx = rect.centerx
        y = rect.top + 18

        name_font = pygame.font.SysFont(None, 32)
        name_text = td.get("type", "").replace("_", " ").title()
        rendered_name = name_font.render(
            name_text, True, COLOR_WHITE if not is_locked else COLOR_GRAY
        )
        surface.blit(rendered_name, rendered_name.get_rect(center=(cx, y)))
        y += 36

        sprite_color = color if not is_locked else COLOR_DARK_GRAY
        sprite_cy = y + TANK_BODY_HEIGHT // 2 + 10
        self._draw_mini_sprite(surface, cx, sprite_cy, sprite_color)
        y = sprite_cy + TANK_BODY_HEIGHT // 2 + 20

        desc_font = pygame.font.SysFont(None, 22)
        desc = td.get("description", "")
        self._draw_wrapped(surface, desc_font, desc, COLOR_GRAY, cx, y, _CARD_W - 24)
        y += 46

        stat_label_font = pygame.font.SysFont(None, 22)
        bar_left = rect.left + 16
        for label, key in _STATS:
            raw = float(td.get(key, 0.0))
            ratio = _normalise(raw, key)
            bar_w = int(ratio * MAX_BAR_WIDTH)

            lbl = stat_label_font.render(label, True, COLOR_GRAY)
            surface.blit(lbl, (bar_left, y))

            bar_y = y + 14
            track_rect = pygame.Rect(bar_left, bar_y, MAX_BAR_WIDTH, _STAT_BAR_H)
            pygame.draw.rect(surface, (55, 55, 60), track_rect, border_radius=3)
            if bar_w > 0:
                fill_color = color if not is_locked else COLOR_DARK_GRAY
                fill_rect = pygame.Rect(bar_left, bar_y, bar_w, _STAT_BAR_H)
                pygame.draw.rect(surface, fill_color, fill_rect, border_radius=3)

            y += _STAT_ROW_GAP

        if is_locked:
            unlock_lvl = self._unlock_levels.get(td.get("type", ""))
            self._draw_locked_overlay(surface, rect, unlock_lvl)

    def _draw_opponent_row(self, surface: pygame.Surface) -> None:
        """Opponent count selector row."""
        row_y = _ROW_Y
        is_focused = (self._focused_row == _ROW_OPPONENTS)
        self._draw_selector_row(
            surface,
            label="Opponents",
            options=[str(n) for n in _OPPONENT_COUNTS],
            selected_idx=self._opponent_idx,
            row_y=row_y,
            is_focused=is_focused,
            active_color=COLOR_GREEN,
        )

    def _draw_selector_row(
        self,
        surface: pygame.Surface,
        label: str,
        options: list,
        selected_idx: int,
        row_y: int,
        is_focused: bool,
        active_color: tuple,
    ) -> None:
        """Generic horizontal selector row: Label  [ opt ]  [ OPT ]  [ opt ]"""
        label_font = pygame.font.SysFont(None, 28)
        opt_font = pygame.font.SysFont(None, 26)

        total_w = 600
        row_x = (SCREEN_WIDTH - total_w) // 2
        cx = SCREEN_WIDTH // 2

        # Row background
        bg_alpha = 60 if is_focused else 30
        bg_surf = pygame.Surface((total_w, _ROW_H), pygame.SRCALPHA)
        bg_surf.fill((255, 255, 255, bg_alpha))
        surface.blit(bg_surf, (row_x, row_y))

        if is_focused:
            pygame.draw.rect(surface, active_color,
                             pygame.Rect(row_x, row_y, total_w, _ROW_H),
                             width=2, border_radius=6)

        # Row label (left-aligned inside the bg)
        lbl_color = COLOR_WHITE if is_focused else COLOR_GRAY
        lbl_surf = label_font.render(label + ":", True, lbl_color)
        surface.blit(lbl_surf, (row_x + 16, row_y + (_ROW_H - lbl_surf.get_height()) // 2))

        # Option pills — centred in the row
        pill_w = 90
        pill_h = 28
        pill_gap = 16
        n = len(options)
        pills_total = n * pill_w + (n - 1) * pill_gap
        pill_start = cx - pills_total // 2

        for i, opt_text in enumerate(options):
            px = pill_start + i * (pill_w + pill_gap)
            py = row_y + (_ROW_H - pill_h) // 2
            pill_rect = pygame.Rect(px, py, pill_w, pill_h)

            if i == selected_idx:
                pill_color = active_color if is_focused else _dim_color(active_color)
                pygame.draw.rect(surface, pill_color, pill_rect, border_radius=6)
                text_color = COLOR_BG
            else:
                pygame.draw.rect(surface, (60, 60, 65), pill_rect, border_radius=6)
                text_color = COLOR_GRAY

            rendered = opt_font.render(opt_text, True, text_color)
            surface.blit(rendered, rendered.get_rect(center=pill_rect.center))

    def _draw_mini_sprite(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        color: tuple,
    ) -> None:
        body_rect = pygame.Rect(0, 0, TANK_BODY_WIDTH, TANK_BODY_HEIGHT)
        body_rect.center = (cx, cy)
        pygame.draw.rect(surface, color, body_rect, border_radius=4)
        barrel_rect = pygame.Rect(
            cx,
            cy - TANK_BARREL_HEIGHT // 2,
            TANK_BARREL_WIDTH,
            TANK_BARREL_HEIGHT,
        )
        pygame.draw.rect(surface, TANK_BARREL_COLOR, barrel_rect)

    def _draw_locked_overlay(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        unlock_level: int | None = None,
    ) -> None:
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, rect.topleft)
        lock_font = pygame.font.SysFont(None, 36)
        lock_surf = lock_font.render("LOCKED", True, COLOR_RED)
        # If we know the unlock level, shift LOCKED up and add the sub-label
        if unlock_level is not None:
            surface.blit(lock_surf, lock_surf.get_rect(center=(rect.centerx, rect.centery - 14)))
            sub_font = pygame.font.SysFont(None, 24)
            sub_surf = sub_font.render(f"Unlocks at Level {unlock_level}", True, COLOR_GRAY)
            surface.blit(sub_surf, sub_surf.get_rect(center=(rect.centerx, rect.centery + 14)))
        else:
            surface.blit(lock_surf, lock_surf.get_rect(center=rect.center))

    @staticmethod
    def _draw_wrapped(
        surface: pygame.Surface,
        font,
        text: str,
        color: tuple,
        cx: int,
        y: int,
        max_width: int,
    ) -> None:
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
        return tank_type not in self._unlocked

    def can_select(self, tank_type: str) -> bool:
        types = [td.get("type") for td in self._tank_data]
        return tank_type in types and tank_type in self._unlocked

    @property
    def selected_opponent_count(self) -> int:
        return _OPPONENT_COUNTS[self._opponent_idx]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _dim_color(color: tuple, factor: float = 0.45) -> tuple:
    """Return a darkened version of color for unfocused rows."""
    return tuple(int(c * factor) for c in color)
