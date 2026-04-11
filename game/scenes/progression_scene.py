"""
game/scenes/progression_scene.py

ProgressionScene — full progression screen, v0.37.

Displays the player's current level, XP bar, and a vertically scrollable
unlock tree showing every tank and weapon in unlock order. Read-only; no
new progression logic — pure UI surface over ProgressionManager data.

Navigation:
  UP / DOWN      — scroll the unlock tree one row at a time
  Mouse wheel    — scroll the unlock tree
  ESC            — return to main menu
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.systems.progression_manager import ProgressionManager
from game.ui.audio_manager import get_audio_manager
from game.utils.config_loader import load_yaml
from game.utils.constants import (
    COLOR_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_NEON_PINK,
    COLOR_WHITE,
    GAME_VERSION,
    MUSIC_MENU,
    SCENE_MENU,
    SCENE_PROGRESSION,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
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
_TITLE_Y: int = 28                 # top of title text

_PROFILE_BAR_H: int = 48
_PROFILE_BAR_GAP: int = 20        # gap between title bottom and profile bar top
_PROFILE_BAR_BG: tuple = (30, 32, 40)
_PROFILE_BAR_RADIUS: int = 6

_XP_BAR_W: int = 400
_XP_BAR_H: int = 14
_XP_BAR_BG: tuple = (50, 52, 60)

_ROW_H: int = 38
_ROW_BG_A: tuple = (22, 24, 30)
_ROW_BG_B: tuple = (26, 28, 36)
_ROW_BG_NEXT: tuple = (40, 38, 55)   # "next unlock" highlight
_ROW_ACCENT_W: int = 3

_COLOR_LEVEL_TAG: tuple = (160, 160, 165)
_COLOR_LOCKED_NAME: tuple = (100, 100, 108)
_COLOR_LOCKED_STATUS: tuple = COLOR_GRAY
_COLOR_NEXT_NAME: tuple = (200, 180, 255)
_COLOR_TAG_TANK_FALLBACK: tuple = (180, 160, 80)

_LIST_FONT_SIZE: int = 22
_TAG_FONT_SIZE: int = 16
_LEVEL_COL_W: int = 70

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
    """
    Return a list of row dicts sorted by unlock level, one per unlockable item.

    Row dict keys:
      level:        int
      item_id:      str
      display_name: str   — weapon description (first sentence) or title-case tank name
      item_type:    str   — "tank" or "weapon"
      category:     str   — weapon category or "tank"
    """
    rows: list[dict] = []

    # Level 1: standard_shell is always unlocked from the start
    weapon_data = weapons_cfg.get("standard_shell", {})
    rows.append({
        "level": 1,
        "item_id": "standard_shell",
        "display_name": _weapon_display_name("standard_shell", weapon_data),
        "item_type": "weapon",
        "category": weapon_data.get("category", "basic"),
    })

    # Remaining levels from the XP table
    xp_table = load_yaml(XP_TABLE_CONFIG) or {}
    for entry in xp_table.get("levels", []):
        level = int(entry.get("level", 0))
        for item_id in entry.get("unlocks", []):
            if item_id == "standard_shell":
                continue  # already added above
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
    """Read-only progression screen showing level, XP bar, and unlock tree."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._title_font: pygame.font.Font | None = None
        self._list_font: pygame.font.Font | None = None
        self._tag_font: pygame.font.Font | None = None
        self._hint_font: pygame.font.Font | None = None
        self._level_font: pygame.font.Font | None = None

        self._rows: list[dict] = []
        self._scroll_offset: int = 0

        self._current_xp: int = 0
        self._current_level: int = 1
        self._unlocked_tanks: set[str] = set()
        self._unlocked_weapons: set[str] = set()
        self._xp_this_level: int = 0
        self._xp_next_level: int = 0
        self._at_max_level: bool = False
        self._fill_ratio: float = 0.0

        # Layout rects computed once in on_enter
        self._profile_bar_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._viewport_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._max_scroll: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        # Load fonts once
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

        # Load profile data
        save_manager = SaveManager()
        progression = ProgressionManager()
        profile = save_manager.load_profile()

        self._current_xp = int(profile.get("xp", 0))
        self._current_level = int(profile.get("level", 1))
        self._unlocked_tanks = set(profile.get("unlocked_tanks", []))
        self._unlocked_weapons = set(profile.get("unlocked_weapons", []))

        # XP bar math
        self._xp_this_level = progression.xp_for_level(self._current_level)
        next_xp = progression.next_level_xp(self._current_xp)
        self._at_max_level = next_xp is None
        self._xp_next_level = next_xp if next_xp is not None else self._current_xp

        if self._at_max_level:
            self._fill_ratio = 1.0
        else:
            span = self._xp_next_level - self._xp_this_level
            if span > 0:
                self._fill_ratio = (self._current_xp - self._xp_this_level) / span
            else:
                self._fill_ratio = 0.0
        self._fill_ratio = max(0.0, min(1.0, self._fill_ratio))

        # Build rows
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

        hint_surf = self._hint_font.render("ESC", True, _HINT_COLOR)
        hint_h = hint_surf.get_height()
        hint_y = SCREEN_HEIGHT - _HINT_MARGIN - hint_h

        viewport_top = bar_y + _PROFILE_BAR_H + _PROFILE_BAR_GAP
        viewport_h = hint_y - _PROFILE_BAR_GAP - viewport_top
        self._viewport_rect = pygame.Rect(
            _MARGIN_X, viewport_top, SCREEN_WIDTH - 2 * _MARGIN_X, viewport_h
        )

        total_list_h = len(self._rows) * _ROW_H
        self._max_scroll = max(0, total_list_h - viewport_h)

        # Auto-scroll so the first locked row is near the top of the viewport
        first_locked_idx = self._first_locked_index()
        if first_locked_idx is not None:
            target = first_locked_idx * _ROW_H - _ROW_H  # one row above it
            self._scroll_offset = max(0, min(target, self._max_scroll))
        else:
            self._scroll_offset = 0

        get_audio_manager().play_music(MUSIC_MENU)
        log.info(
            "ProgressionScene entered. Level=%d XP=%d rows=%d",
            self._current_level, self._current_xp, len(self._rows),
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
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._scroll_offset = max(0, self._scroll_offset - _ROW_H)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._scroll_offset = min(self._max_scroll, self._scroll_offset + _ROW_H)
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_offset -= event.y * _ROW_H
            self._scroll_offset = max(0, min(self._max_scroll, self._scroll_offset))

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
        self._draw_unlock_tree(surface)
        self._draw_hint_bar(surface)

    # ------------------------------------------------------------------
    # Draw helpers
    # ------------------------------------------------------------------

    def _draw_title(self, surface: pygame.Surface) -> None:
        title_surf = self._title_font.render("PROGRESSION", True, COLOR_WHITE)
        cx = SCREEN_WIDTH // 2
        surface.blit(title_surf, (cx - title_surf.get_width() // 2, _TITLE_Y))

        # Version tag — small, top-right
        ver_surf = self._tag_font.render(GAME_VERSION, True, _COLOR_LEVEL_TAG)
        surface.blit(
            ver_surf,
            (SCREEN_WIDTH - _MARGIN_X - ver_surf.get_width(), _TITLE_Y + 4),
        )

    def _draw_profile_bar(self, surface: pygame.Surface) -> None:
        r = self._profile_bar_rect
        pygame.draw.rect(surface, _PROFILE_BAR_BG, r, border_radius=_PROFILE_BAR_RADIUS)

        cx = r.x
        cy = r.centery
        pad = 16

        # LVL N label
        lvl_surf = self._level_font.render(f"LVL {self._current_level}", True, COLOR_NEON_PINK)
        lvl_rect = lvl_surf.get_rect(midleft=(cx + pad, cy))
        surface.blit(lvl_surf, lvl_rect)

        # XP fill bar — centred in the bar panel
        bar_x = r.centerx - _XP_BAR_W // 2
        bar_y = cy - _XP_BAR_H // 2
        bar_rect = pygame.Rect(bar_x, bar_y, _XP_BAR_W, _XP_BAR_H)
        pygame.draw.rect(surface, _XP_BAR_BG, bar_rect, border_radius=3)
        fill_w = int(_XP_BAR_W * self._fill_ratio)
        if fill_w > 0:
            fill_color = COLOR_NEON_PINK if self._at_max_level else COLOR_GREEN
            fill_rect = pygame.Rect(bar_x, bar_y, fill_w, _XP_BAR_H)
            pygame.draw.rect(surface, fill_color, fill_rect, border_radius=3)

        # XP label right of fill bar
        if self._at_max_level:
            xp_text = f"{self._current_xp} XP (MAX)"
        else:
            xp_text = f"{self._current_xp} XP"
        xp_surf = self._hint_font.render(xp_text, True, _COLOR_LEVEL_TAG)
        xp_rect = xp_surf.get_rect(midleft=(bar_x + _XP_BAR_W + 12, cy))
        surface.blit(xp_surf, xp_rect)

    def _draw_unlock_tree(self, surface: pygame.Surface) -> None:
        vp = self._viewport_rect
        first_locked_idx = self._first_locked_index()

        # Clip to viewport
        surface.set_clip(vp)

        for i, row in enumerate(self._rows):
            row_y = vp.top + i * _ROW_H - self._scroll_offset
            if row_y + _ROW_H < vp.top or row_y > vp.bottom:
                continue

            is_unlocked = self._is_unlocked(row)
            is_next = (first_locked_idx is not None and i == first_locked_idx)

            # Row background
            if is_next:
                bg_color = _ROW_BG_NEXT
            elif i % 2 == 0:
                bg_color = _ROW_BG_A
            else:
                bg_color = _ROW_BG_B
            row_rect = pygame.Rect(vp.left, row_y, vp.width, _ROW_H)
            pygame.draw.rect(surface, bg_color, row_rect)

            # Left accent bar for unlocked rows
            if is_unlocked:
                accent_rect = pygame.Rect(vp.left, row_y, _ROW_ACCENT_W, _ROW_H)
                pygame.draw.rect(surface, COLOR_GREEN, accent_rect)

            x = vp.left + _ROW_ACCENT_W + 8
            mid_y = row_y + _ROW_H // 2

            # Status icon
            if is_unlocked:
                icon_color = COLOR_GREEN
                icon = "\u2713"  # ✓
            else:
                icon_color = _COLOR_LOCKED_STATUS
                icon = "\u00b7"  # ·
            icon_surf = self._list_font.render(icon, True, icon_color)
            icon_rect = icon_surf.get_rect(midleft=(x, mid_y))
            surface.blit(icon_surf, icon_rect)
            x += icon_rect.width + 8

            # LVL N
            lvl_surf = self._tag_font.render(f"LVL {row['level']}", True, _COLOR_LEVEL_TAG)
            lvl_rect = lvl_surf.get_rect(midleft=(x, mid_y))
            surface.blit(lvl_surf, lvl_rect)
            x += _LEVEL_COL_W

            # Item name
            if is_next:
                name_color = _COLOR_NEXT_NAME
            elif is_unlocked:
                name_color = COLOR_WHITE
            else:
                name_color = _COLOR_LOCKED_NAME
            name_surf = self._list_font.render(row["display_name"], True, name_color)
            name_rect = name_surf.get_rect(midleft=(x, mid_y))
            surface.blit(name_surf, name_rect)

            # Category tag — right-aligned within the row
            tag_text, tag_color = self._category_tag(row)
            tag_surf = self._tag_font.render(tag_text, True, tag_color)
            tag_rect = tag_surf.get_rect(midright=(vp.right - 8, mid_y))
            surface.blit(tag_surf, tag_rect)

        surface.set_clip(None)

    def _draw_hint_bar(self, surface: pygame.Surface) -> None:
        esc_surf = self._hint_font.render("ESC \u2014 Back", True, _HINT_COLOR)
        scroll_surf = self._hint_font.render("\u2191\u2193 / Scroll \u2014 Navigate", True, _HINT_COLOR)
        y = SCREEN_HEIGHT - _HINT_MARGIN - esc_surf.get_height()
        surface.blit(esc_surf, (_MARGIN_X, y))
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
