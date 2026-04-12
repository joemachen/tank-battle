"""
game/scenes/progression_scene.py

ProgressionScene — full progression screen, v0.39.

Three-tab layout:
  UNLOCKS      — scrollable unlock tree (tanks + weapons in level order)
  HISTORY      — last 20 matches, newest first
  ACHIEVEMENTS — all 10 achievements, earned in gold / locked dimmed

Navigation:
  LEFT / RIGHT   — switch tabs
  UP / DOWN      — scroll active tab one row at a time
  Mouse wheel    — scroll active tab
  ESC            — return to main menu
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.systems.progression_manager import ProgressionManager
from game.ui.audio_manager import get_audio_manager
from game.utils.config_loader import load_yaml
from game.systems.achievement_system import AchievementSystem
from game.utils.constants import (
    COLOR_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_NEON_PINK,
    COLOR_RED,
    COLOR_WHITE,
    COLOR_YELLOW,
    GAME_VERSION,
    MATCH_HISTORY_MAX_DISPLAY,
    MUSIC_MENU,
    SCENE_MENU,
    SCENE_PROGRESSION,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_NAVIGATE,
    TANK_SELECT_COLORS,
    TANKS_CONFIG,
    WEAPON_CATEGORY_COLORS,
    WEAPONS_CONFIG,
    XP_TABLE_CONFIG,
)
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
_MARGIN_X: int = 80
_TITLE_FONT_SIZE: int = 54
_TITLE_Y: int = 28

_PROFILE_BAR_H: int = 48
_PROFILE_BAR_GAP: int = 20
_PROFILE_BAR_BG: tuple = (30, 32, 40)
_PROFILE_BAR_RADIUS: int = 6

_XP_BAR_W: int = 400
_XP_BAR_H: int = 14
_XP_BAR_BG: tuple = (50, 52, 60)

_TAB_BAR_H: int = 36
_TAB_ACTIVE_BG: tuple = (40, 42, 55)
_TAB_INACTIVE_BG: tuple = (25, 27, 35)
_TAB_INACTIVE_LABEL: tuple = (100, 100, 110)
_TAB_FONT_SIZE: int = 20
_TABS: list[str] = ["UNLOCKS", "HISTORY", "ACHIEVEMENTS"]

_ACHIEVEMENT_ROW_H: int = 56
_ACHIEVEMENT_ACCENT_W: int = 4
_COLOR_ACHIEVEMENT_GOLD: tuple = (220, 180, 50)
_COLOR_ACHIEVEMENT_LOCKED_NAME: tuple = (80, 80, 90)
_COLOR_ACHIEVEMENT_LOCKED_DESC: tuple = (60, 60, 70)
_COLOR_ACHIEVEMENT_DESC: tuple = (130, 130, 140)
_COLOR_SUMMARY: tuple = (130, 130, 140)

_ROW_H: int = 38
_ROW_BG_A: tuple = (22, 24, 30)
_ROW_BG_B: tuple = (26, 28, 36)
_ROW_ACCENT_W: int = 3
_LEVEL_COL_W: int = 70

_HISTORY_ROW_H: int = 52
_HISTORY_ACCENT_W: int = 4
_COLOR_HISTORY_EMPTY: tuple = (100, 100, 110)
_COLOR_DMG_DEALT: tuple = (100, 200, 120)
_COLOR_DMG_TAKEN: tuple = (200, 100, 100)

_COLOR_LEVEL_TAG: tuple = (160, 160, 165)
_COLOR_LOCKED_NAME: tuple = (100, 100, 108)
_COLOR_LOCKED_STATUS: tuple = COLOR_GRAY
_COLOR_NEXT_NAME: tuple = (200, 180, 255)
_COLOR_TAG_TANK_FALLBACK: tuple = (180, 160, 80)
_COLOR_PROFILE_STATS: tuple = (150, 150, 160)

_LIST_FONT_SIZE: int = 22
_TAG_FONT_SIZE: int = 16

_HINT_MARGIN: int = 30
_HINT_FONT_SIZE: int = 18
_HINT_COLOR: tuple = (90, 90, 100)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _build_unlock_rows(
    progression: ProgressionManager,
    weapons_cfg: dict,
    tanks_cfg: dict,
) -> list[dict]:
    """Return rows sorted by unlock level, one per unlockable item."""
    rows: list[dict] = []

    weapon_data = weapons_cfg.get("standard_shell", {})
    rows.append({
        "level": 1,
        "item_id": "standard_shell",
        "display_name": _weapon_display_name("standard_shell", weapon_data),
        "item_type": "weapon",
        "category": weapon_data.get("category", "basic"),
    })

    xp_table = load_yaml(XP_TABLE_CONFIG) or {}
    for entry in xp_table.get("levels", []):
        level = int(entry.get("level", 0))
        for item_id in entry.get("unlocks", []):
            if item_id == "standard_shell":
                continue
            if item_id.endswith("_tank"):
                rows.append({
                    "level": level,
                    "item_id": item_id,
                    "display_name": _tank_display_name(item_id),
                    "item_type": "tank",
                    "category": "tank",
                })
            else:
                wdata = weapons_cfg.get(item_id, {})
                rows.append({
                    "level": level,
                    "item_id": item_id,
                    "display_name": _weapon_display_name(item_id, wdata),
                    "item_type": "weapon",
                    "category": wdata.get("category", "basic"),
                })

    rows.sort(key=lambda r: r["level"])
    return rows


def _weapon_display_name(item_id: str, weapon_data: dict) -> str:
    desc = weapon_data.get("description", "")
    if desc:
        return desc.split(".")[0].strip()
    return item_id.replace("_", " ").title()


def _tank_display_name(item_id: str) -> str:
    return item_id.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class ProgressionScene(BaseScene):
    """Progression screen: level/XP bar, unlock tree, and match history."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._title_font: pygame.font.Font | None = None
        self._list_font: pygame.font.Font | None = None
        self._tag_font: pygame.font.Font | None = None
        self._hint_font: pygame.font.Font | None = None
        self._level_font: pygame.font.Font | None = None
        self._tab_font: pygame.font.Font | None = None
        self._stats_font: pygame.font.Font | None = None

        self._rows: list[dict] = []
        self._scroll_offset: int = 0
        self._max_scroll: int = 0

        self._active_tab: int = 0
        self._history_scroll: int = 0
        self._history_max_scroll: int = 0
        self._match_history: list[dict] = []
        self._achievements_scroll: int = 0
        self._achievements_max_scroll: int = 0
        self._earned_achievements: set[str] = set()
        self._achievement_defs: list[dict] = []
        self._total_matches: int = 0
        self._wins: int = 0
        self._losses: int = 0

        self._current_xp: int = 0
        self._current_level: int = 1
        self._unlocked_tanks: set[str] = set()
        self._unlocked_weapons: set[str] = set()
        self._xp_this_level: int = 0
        self._xp_next_level: int = 0
        self._at_max_level: bool = False
        self._fill_ratio: float = 0.0

        self._profile_bar_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._tab_bar_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._viewport_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        if self._title_font is None:
            self._title_font = pygame.font.SysFont(None, _TITLE_FONT_SIZE)
        if self._list_font is None:
            self._list_font = pygame.font.SysFont(None, _LIST_FONT_SIZE)
        if self._tag_font is None:
            self._tag_font = pygame.font.SysFont(None, _TAG_FONT_SIZE)
        if self._hint_font is None:
            self._hint_font = pygame.font.SysFont(None, _HINT_FONT_SIZE)
        if self._level_font is None:
            self._level_font = pygame.font.SysFont(None, 32)
        if self._tab_font is None:
            self._tab_font = pygame.font.SysFont(None, _TAB_FONT_SIZE)
        if self._stats_font is None:
            self._stats_font = pygame.font.SysFont(None, 20)

        save_manager = SaveManager()
        progression = ProgressionManager()
        profile = save_manager.load_profile()

        self._current_xp = int(profile.get("xp", 0))
        self._current_level = int(profile.get("level", 1))
        self._unlocked_tanks = set(profile.get("unlocked_tanks", []))
        self._unlocked_weapons = set(profile.get("unlocked_weapons", []))
        self._match_history = list(profile.get("match_history", []))
        self._total_matches = int(profile.get("total_matches", 0))
        self._wins = int(profile.get("wins", 0))
        self._losses = int(profile.get("losses", 0))

        # XP bar math
        self._xp_this_level = progression.xp_for_level(self._current_level)
        next_xp = progression.next_level_xp(self._current_xp)
        self._at_max_level = next_xp is None
        self._xp_next_level = next_xp if next_xp is not None else self._current_xp

        if self._at_max_level:
            self._fill_ratio = 1.0
        else:
            span = self._xp_next_level - self._xp_this_level
            self._fill_ratio = (self._current_xp - self._xp_this_level) / span if span > 0 else 0.0
        self._fill_ratio = max(0.0, min(1.0, self._fill_ratio))

        # Build unlock rows
        weapons_cfg = load_yaml(WEAPONS_CONFIG) or {}
        tanks_cfg = load_yaml(TANKS_CONFIG) or {}
        self._rows = _build_unlock_rows(progression, weapons_cfg, tanks_cfg)

        # Compute layout rects
        title_surf = self._title_font.render("PROGRESSION", True, COLOR_WHITE)
        title_h = title_surf.get_height()

        bar_x = _MARGIN_X
        bar_y = _TITLE_Y + title_h + _PROFILE_BAR_GAP
        bar_w = SCREEN_WIDTH - 2 * _MARGIN_X
        self._profile_bar_rect = pygame.Rect(bar_x, bar_y, bar_w, _PROFILE_BAR_H)

        tab_top = bar_y + _PROFILE_BAR_H + _PROFILE_BAR_GAP
        self._tab_bar_rect = pygame.Rect(bar_x, tab_top, bar_w, _TAB_BAR_H)

        hint_surf = self._hint_font.render("ESC", True, _HINT_COLOR)
        hint_h = hint_surf.get_height()
        hint_y = SCREEN_HEIGHT - _HINT_MARGIN - hint_h

        viewport_top = tab_top + _TAB_BAR_H
        viewport_h = hint_y - _PROFILE_BAR_GAP - viewport_top
        self._viewport_rect = pygame.Rect(
            _MARGIN_X, viewport_top, SCREEN_WIDTH - 2 * _MARGIN_X, viewport_h
        )

        # Achievements
        _ach_sys = AchievementSystem()
        self._achievement_defs = _ach_sys.all_definitions()
        self._earned_achievements = set(profile.get("achievements", []))

        # Scroll limits
        total_unlock_h = len(self._rows) * _ROW_H
        self._max_scroll = max(0, total_unlock_h - viewport_h)

        display_count = min(MATCH_HISTORY_MAX_DISPLAY, len(self._match_history))
        total_history_h = display_count * _HISTORY_ROW_H
        self._history_max_scroll = max(0, total_history_h - viewport_h)

        total_ach_h = len(self._achievement_defs) * _ACHIEVEMENT_ROW_H
        self._achievements_max_scroll = max(0, total_ach_h - viewport_h)

        # Reset state on re-enter
        self._active_tab = 0
        self._scroll_offset = 0
        self._history_scroll = 0
        self._achievements_scroll = 0

        # Auto-scroll unlocks so first locked row is near top
        first_locked = self._first_locked_index()
        if first_locked is not None:
            target = first_locked * _ROW_H - _ROW_H
            self._scroll_offset = max(0, min(target, self._max_scroll))

        get_audio_manager().play_music(MUSIC_MENU)
        log.info(
            "ProgressionScene entered. Level=%d XP=%d history=%d",
            self._current_level, self._current_xp, len(self._match_history),
        )

    def on_exit(self) -> None:
        log.debug("ProgressionScene exited.")

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.manager.switch_to(SCENE_MENU)
            elif event.key in (pygame.K_LEFT,):
                if self._active_tab > 0:
                    self._active_tab -= 1
                    get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
            elif event.key in (pygame.K_RIGHT,):
                if self._active_tab < len(_TABS) - 1:
                    self._active_tab += 1
                    get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._scroll_active(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._scroll_active(1)
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_active(-event.y)

    def _scroll_active(self, direction: int) -> None:
        """Scroll the active tab by ±1 row in direction (+1 = down, -1 = up)."""
        if self._active_tab == 0:
            step = _ROW_H * direction
            self._scroll_offset = max(0, min(self._max_scroll, self._scroll_offset + step))
        elif self._active_tab == 1:
            step = _HISTORY_ROW_H * direction
            self._history_scroll = max(0, min(self._history_max_scroll, self._history_scroll + step))
        else:
            step = _ACHIEVEMENT_ROW_H * direction
            self._achievements_scroll = max(0, min(self._achievements_max_scroll, self._achievements_scroll + step))

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
        self._draw_title(surface)
        self._draw_profile_bar(surface)
        self._draw_tab_bar(surface)
        if self._active_tab == 0:
            self._draw_unlock_tree(surface)
        elif self._active_tab == 1:
            self._draw_history_tab(surface)
        else:
            self._draw_achievements_tab(surface)
        self._draw_hint_bar(surface)

    # ------------------------------------------------------------------
    # Draw helpers
    # ------------------------------------------------------------------

    def _draw_title(self, surface: pygame.Surface) -> None:
        title_surf = self._title_font.render("PROGRESSION", True, COLOR_WHITE)
        cx = SCREEN_WIDTH // 2
        surface.blit(title_surf, (cx - title_surf.get_width() // 2, _TITLE_Y))
        ver_surf = self._tag_font.render(GAME_VERSION, True, _COLOR_LEVEL_TAG)
        surface.blit(ver_surf, (SCREEN_WIDTH - _MARGIN_X - ver_surf.get_width(), _TITLE_Y + 4))

    def _draw_profile_bar(self, surface: pygame.Surface) -> None:
        r = self._profile_bar_rect
        pygame.draw.rect(surface, _PROFILE_BAR_BG, r, border_radius=_PROFILE_BAR_RADIUS)

        cy = r.centery
        pad = 16

        # LVL N
        lvl_surf = self._level_font.render(f"LVL {self._current_level}", True, COLOR_NEON_PINK)
        surface.blit(lvl_surf, lvl_surf.get_rect(midleft=(r.x + pad, cy)))

        # XP fill bar — centred
        bar_x = r.centerx - _XP_BAR_W // 2
        bar_y = cy - _XP_BAR_H // 2
        bar_rect = pygame.Rect(bar_x, bar_y, _XP_BAR_W, _XP_BAR_H)
        pygame.draw.rect(surface, _XP_BAR_BG, bar_rect, border_radius=3)
        fill_w = int(_XP_BAR_W * self._fill_ratio)
        if fill_w > 0:
            fill_color = COLOR_NEON_PINK if self._at_max_level else COLOR_GREEN
            pygame.draw.rect(surface, fill_color, pygame.Rect(bar_x, bar_y, fill_w, _XP_BAR_H), border_radius=3)

        # XP label
        xp_text = f"{self._current_xp} XP (MAX)" if self._at_max_level else f"{self._current_xp} XP"
        xp_surf = self._hint_font.render(xp_text, True, _COLOR_LEVEL_TAG)
        surface.blit(xp_surf, xp_surf.get_rect(midleft=(bar_x + _XP_BAR_W + 12, cy)))

        # Right-aligned W/L/Matches
        stats_text = f"W:{self._wins}  L:{self._losses}  Matches:{self._total_matches}"
        stats_surf = self._stats_font.render(stats_text, True, _COLOR_PROFILE_STATS)
        surface.blit(stats_surf, stats_surf.get_rect(midright=(r.right - 16, cy)))

    def _draw_tab_bar(self, surface: pygame.Surface) -> None:
        r = self._tab_bar_rect
        tab_w = r.width // len(_TABS)
        for i, label in enumerate(_TABS):
            tab_rect = pygame.Rect(r.x + i * tab_w, r.y, tab_w, _TAB_BAR_H)
            is_active = (i == self._active_tab)
            bg = _TAB_ACTIVE_BG if is_active else _TAB_INACTIVE_BG
            pygame.draw.rect(surface, bg, tab_rect)

            label_color = COLOR_WHITE if is_active else _TAB_INACTIVE_LABEL
            label_surf = self._tab_font.render(label, True, label_color)
            surface.blit(label_surf, label_surf.get_rect(center=tab_rect.center))

            if is_active:
                pygame.draw.rect(
                    surface, COLOR_NEON_PINK,
                    pygame.Rect(tab_rect.x, tab_rect.bottom - 2, tab_rect.width, 2),
                )

    def _draw_unlock_tree(self, surface: pygame.Surface) -> None:
        vp = self._viewport_rect
        first_locked_idx = self._first_locked_index()
        surface.set_clip(vp)

        for i, row in enumerate(self._rows):
            row_y = vp.top + i * _ROW_H - self._scroll_offset
            if row_y + _ROW_H < vp.top or row_y > vp.bottom:
                continue

            is_unlocked = self._is_unlocked(row)
            is_next = (first_locked_idx is not None and i == first_locked_idx)

            if is_next:
                bg_color = (40, 38, 55)
            elif i % 2 == 0:
                bg_color = _ROW_BG_A
            else:
                bg_color = _ROW_BG_B
            pygame.draw.rect(surface, bg_color, pygame.Rect(vp.left, row_y, vp.width, _ROW_H))

            if is_unlocked:
                pygame.draw.rect(surface, COLOR_GREEN, pygame.Rect(vp.left, row_y, _ROW_ACCENT_W, _ROW_H))

            x = vp.left + _ROW_ACCENT_W + 8
            mid_y = row_y + _ROW_H // 2

            icon = "\u2713" if is_unlocked else "\u00b7"
            icon_color = COLOR_GREEN if is_unlocked else _COLOR_LOCKED_STATUS
            icon_surf = self._list_font.render(icon, True, icon_color)
            icon_rect = icon_surf.get_rect(midleft=(x, mid_y))
            surface.blit(icon_surf, icon_rect)
            x += icon_rect.width + 8

            lvl_surf = self._tag_font.render(f"LVL {row['level']}", True, _COLOR_LEVEL_TAG)
            surface.blit(lvl_surf, lvl_surf.get_rect(midleft=(x, mid_y)))
            x += _LEVEL_COL_W

            if is_next:
                name_color = _COLOR_NEXT_NAME
            elif is_unlocked:
                name_color = COLOR_WHITE
            else:
                name_color = _COLOR_LOCKED_NAME
            name_surf = self._list_font.render(row["display_name"], True, name_color)
            surface.blit(name_surf, name_surf.get_rect(midleft=(x, mid_y)))

            tag_text, tag_color = self._category_tag(row)
            tag_surf = self._tag_font.render(tag_text, True, tag_color)
            surface.blit(tag_surf, tag_surf.get_rect(midright=(vp.right - 8, mid_y)))

        surface.set_clip(None)

    def _draw_history_tab(self, surface: pygame.Surface) -> None:
        vp = self._viewport_rect

        if not self._match_history:
            empty_surf = self._list_font.render("No matches recorded yet.", True, _COLOR_HISTORY_EMPTY)
            surface.blit(empty_surf, empty_surf.get_rect(center=vp.center))
            return

        display_entries = list(reversed(self._match_history))[:MATCH_HISTORY_MAX_DISPLAY]
        surface.set_clip(vp)

        for i, entry in enumerate(display_entries):
            row_y = vp.top + i * _HISTORY_ROW_H - self._history_scroll
            if row_y + _HISTORY_ROW_H < vp.top or row_y > vp.bottom:
                continue

            bg_color = _ROW_BG_A if i % 2 == 0 else _ROW_BG_B
            pygame.draw.rect(surface, bg_color, pygame.Rect(vp.left, row_y, vp.width, _HISTORY_ROW_H))

            accent_color = COLOR_GREEN if entry.get("won") else COLOR_RED
            pygame.draw.rect(surface, accent_color, pygame.Rect(vp.left, row_y, _HISTORY_ACCENT_W, _HISTORY_ROW_H))

            x = vp.left + _HISTORY_ACCENT_W + 10
            mid_y = row_y + _HISTORY_ROW_H // 2

            # WIN / LOSS
            result_label = "WIN" if entry.get("won") else "LOSS"
            result_color = COLOR_GREEN if entry.get("won") else COLOR_RED
            res_surf = self._list_font.render(result_label, True, result_color)
            surface.blit(res_surf, res_surf.get_rect(midleft=(x, mid_y)))
            x += 56

            stat_font = self._hint_font
            stat_color = _COLOR_LEVEL_TAG

            # K:N
            k_surf = stat_font.render(f"K:{entry.get('kills', 0)}", True, stat_color)
            surface.blit(k_surf, k_surf.get_rect(midleft=(x, mid_y)))
            x += 44

            # ACC:NN%
            acc = int(entry.get("accuracy", 0) * 100)
            acc_surf = stat_font.render(f"ACC:{acc}%", True, stat_color)
            surface.blit(acc_surf, acc_surf.get_rect(midleft=(x, mid_y)))
            x += 76

            # DMG dealt ↑
            dealt_surf = stat_font.render(f"DMG:{entry.get('damage_dealt', 0)}\u2191", True, _COLOR_DMG_DEALT)
            surface.blit(dealt_surf, dealt_surf.get_rect(midleft=(x, mid_y)))
            x += 94

            # DMG taken ↓
            taken_surf = stat_font.render(f"{entry.get('damage_taken', 0)}\u2193", True, _COLOR_DMG_TAKEN)
            surface.blit(taken_surf, taken_surf.get_rect(midleft=(x, mid_y)))
            x += 74

            # Time
            t_surf = stat_font.render(f"{int(entry.get('time_elapsed', 0))}s", True, stat_color)
            surface.blit(t_surf, t_surf.get_rect(midleft=(x, mid_y)))
            x += 60

            # +XP
            xp_surf = stat_font.render(f"+{entry.get('xp_earned', 0)} XP", True, COLOR_YELLOW)
            surface.blit(xp_surf, xp_surf.get_rect(midleft=(x, mid_y)))

            # LVL N — right-aligned
            lvl_surf = stat_font.render(f"LVL {entry.get('level_after', 1)}", True, stat_color)
            surface.blit(lvl_surf, lvl_surf.get_rect(midright=(vp.right - 8, mid_y)))

        surface.set_clip(None)

    def _draw_achievements_tab(self, surface: pygame.Surface) -> None:
        vp = self._viewport_rect
        earned_count = len(self._earned_achievements)
        total_count = len(self._achievement_defs)

        # Non-scrolling summary line
        summary_font = self._hint_font
        prefix = summary_font.render(f"{earned_count} / {total_count} ", True, COLOR_WHITE)
        suffix_text = "achievements earned"
        suffix = summary_font.render(suffix_text, True, _COLOR_SUMMARY)
        summary_y = vp.top
        surface.blit(prefix, (vp.left, summary_y))
        surface.blit(suffix, (vp.left + prefix.get_width(), summary_y))
        summary_h = prefix.get_height() + 6

        # Scrollable area starts below summary line
        vp_scroll = pygame.Rect(vp.left, vp.top + summary_h, vp.width, vp.height - summary_h)
        surface.set_clip(vp_scroll)

        for i, defn in enumerate(self._achievement_defs):
            row_y = vp_scroll.top + i * _ACHIEVEMENT_ROW_H - self._achievements_scroll
            if row_y + _ACHIEVEMENT_ROW_H < vp_scroll.top or row_y > vp_scroll.bottom:
                continue

            is_earned = defn["id"] in self._earned_achievements
            bg_color = _ROW_BG_A if i % 2 == 0 else _ROW_BG_B
            pygame.draw.rect(surface, bg_color, pygame.Rect(vp.left, row_y, vp.width, _ACHIEVEMENT_ROW_H))

            x = vp.left
            if is_earned:
                pygame.draw.rect(surface, _COLOR_ACHIEVEMENT_GOLD,
                                 pygame.Rect(x, row_y, _ACHIEVEMENT_ACCENT_W, _ACHIEVEMENT_ROW_H))
                icon_color = _COLOR_ACHIEVEMENT_GOLD
                icon = "\u2605"  # ★
                name_color = COLOR_WHITE
                desc_color = _COLOR_ACHIEVEMENT_DESC
            else:
                icon_color = (70, 70, 80)
                icon = "\u00b7"  # ·
                name_color = _COLOR_ACHIEVEMENT_LOCKED_NAME
                desc_color = _COLOR_ACHIEVEMENT_LOCKED_DESC

            x = vp.left + _ACHIEVEMENT_ACCENT_W + 10
            icon_surf = self._list_font.render(icon, True, icon_color)
            surface.blit(icon_surf, icon_surf.get_rect(midleft=(x, row_y + 10 + self._list_font.get_height() // 2)))
            x += icon_surf.get_width() + 8

            name_surf = self._list_font.render(defn["name"], True, name_color)
            surface.blit(name_surf, (x, row_y + 10))

            desc_surf = self._tag_font.render(defn["description"], True, desc_color)
            surface.blit(desc_surf, (x, row_y + 32))

        surface.set_clip(None)

    def _draw_hint_bar(self, surface: pygame.Surface) -> None:
        esc_surf = self._hint_font.render("ESC \u2014 Back", True, _HINT_COLOR)
        scroll_surf = self._hint_font.render("\u2191\u2193 / Scroll \u2014 Navigate", True, _HINT_COLOR)
        tab_surf = self._hint_font.render("\u25c4\u25ba Switch Tab", True, _HINT_COLOR)
        y = SCREEN_HEIGHT - _HINT_MARGIN - esc_surf.get_height()
        surface.blit(esc_surf, (_MARGIN_X, y))
        surface.blit(tab_surf, tab_surf.get_rect(centerx=SCREEN_WIDTH // 2, top=y))
        surface.blit(scroll_surf, (SCREEN_WIDTH - _MARGIN_X - scroll_surf.get_width(), y))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_unlocked(self, row: dict) -> bool:
        if row["item_type"] == "tank":
            return row["item_id"] in self._unlocked_tanks
        return row["item_id"] in self._unlocked_weapons

    def _first_locked_index(self) -> int | None:
        for i, row in enumerate(self._rows):
            if not self._is_unlocked(row):
                return i
        return None

    def _category_tag(self, row: dict) -> tuple[str, tuple]:
        if row["item_type"] == "tank":
            color = TANK_SELECT_COLORS.get(row["item_id"], _COLOR_TAG_TANK_FALLBACK)
            return "[Tank]", color
        cat = row["category"]
        color = WEAPON_CATEGORY_COLORS.get(cat, _COLOR_LEVEL_TAG)
        return f"[{cat.capitalize()}]", color
