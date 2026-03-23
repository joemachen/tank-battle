"""
game/scenes/loadout_scene.py

LoadoutScene — unified pre-match loadout screen (v0.17.5).

Replaces the 3-scene chain (TankSelectScene → WeaponSelectScene →
MapSelectScene) with a single screen containing three side-by-side panels:

  ┌──────────────┬──────────────────┬───────────────────────┐
  │   HULL       │    WEAPONS       │       MAP              │
  │  (tank pick) │  (3 weapon slots)│  (map pick + preview)  │
  └──────────────┴──────────────────┴───────────────────────┘

Flow:
  MainMenuScene (PLAY) → LoadoutScene → (ENTER) → GameplayScene
                                     → (ESC)    → MainMenuScene

Panel navigation:
  TAB              — cycle focus to next panel (wrapping)
  Hull / Map panel: LEFT/RIGHT also switch panels
  Weapons panel:    LEFT/RIGHT cycle weapon for the focused slot

Within Hull panel:   UP/DOWN selects tank (only unlocked tanks)
Within Weapons panel: UP/DOWN moves between slots, LEFT/RIGHT cycles weapon
Within Map panel:    UP/DOWN selects map
ENTER / SPACE — confirm and start match (always, regardless of focused panel)
ESC — return to MainMenuScene
"""

import os

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
    COLOR_NEON_PINK,
    COLOR_RED,
    COLOR_WHITE,
    DEFAULT_PROFILE,
    LOADOUT_PANEL_COUNT,
    LOADOUT_PANEL_HULL,
    LOADOUT_PANEL_MAP,
    LOADOUT_PANEL_WEAPONS,
    MAPS_DIR,
    MAX_BAR_WIDTH,
    MAX_WEAPON_SLOTS,
    MUSIC_MENU,
    SCENE_GAME,
    SCENE_MENU,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
    TANK_BARREL_COLOR,
    TANK_BARREL_HEIGHT,
    TANK_BARREL_LENGTH,
    TANK_BODY_HEIGHT,
    TANK_BODY_WIDTH,
    TANK_SELECT_COLORS,
    TANKS_CONFIG,
    TANK_STAT_MAX,
    WEAPON_CARD_COLORS,
    WEAPON_STAT_MAX,
    WEAPONS_CONFIG,
    XP_TABLE_CONFIG,
)
from game.utils.logger import get_logger
from game.utils.map_loader import load_map
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

_TANK_ORDER: list[str] = ["light_tank", "medium_tank", "heavy_tank", "scout_tank"]
_WEAPON_ORDER: list[str] = ["standard_shell", "spread_shot", "bouncing_round", "homing_missile", "grenade_launcher"]
_MAP_NAMES: list[str] = ["map_01", "map_02", "map_03"]

_TANK_STATS: list[tuple[str, str]] = [
    ("Speed",    "speed"),
    ("Health",   "health"),
    ("Turn",     "turn_rate"),
    ("Fire Rt",  "fire_rate"),
]
_WEAPON_STATS: list[tuple[str, str]] = [
    ("Damage",   "damage"),
    ("Speed",    "speed"),
    ("Fire Rt",  "fire_rate"),
    ("Range",    "max_range"),
]

# ---------------------------------------------------------------------------
# Layout (1280 × 720)
# ---------------------------------------------------------------------------

_PANEL_W: int = 360
_PANEL_H: int = 485
_PANEL_GAP: int = 25
_PANEL_LEFT: int = (SCREEN_WIDTH - 3 * _PANEL_W - 2 * _PANEL_GAP) // 2  # 70
_PANEL_TOP: int = 72
_PANEL_RADIUS: int = 8

_PANEL_XS: list[int] = [
    _PANEL_LEFT,
    _PANEL_LEFT + _PANEL_W + _PANEL_GAP,
    _PANEL_LEFT + 2 * (_PANEL_W + _PANEL_GAP),
]

_XP_BAR_Y: int = _PANEL_TOP + _PANEL_H + 18
_XP_BAR_W: int = 340
_XP_BAR_H: int = 10
_XP_BAR_X: int = (SCREEN_WIDTH - _XP_BAR_W) // 2

_CONFIRM_Y: int = _XP_BAR_Y + 38
_CONFIRM_W: int = 210
_CONFIRM_H: int = 36

_STAT_BAR_H: int = 9
_STAT_ROW_H: int = 26
_MAX_STAT_W: int = min(MAX_BAR_WIDTH, 140)  # stat bar fill width in panels

_PREVIEW_W: int = 320
_PREVIEW_H: int = 180

_COLOR_DIM: tuple = (80, 80, 85)
_COLOR_LOCKED_OVERLAY: tuple = (0, 0, 0, 150)


# ---------------------------------------------------------------------------
# Stat normalisers (ported from tank_select_scene / weapon_select_scene)
# ---------------------------------------------------------------------------

def _norm_tank(value: float, key: str) -> float:
    mx = TANK_STAT_MAX.get(key, 1.0)
    return max(0.0, min(1.0, value / mx)) if mx > 0 else 0.0


def _norm_weapon(value: float, key: str) -> float:
    mx = WEAPON_STAT_MAX.get(key)
    if mx is None or mx <= 0:
        return 0.0
    return max(0.0, min(1.0, value / mx))


# ---------------------------------------------------------------------------
# Map preview helper (port of map_select_scene._build_preview)
# ---------------------------------------------------------------------------

def _build_map_preview(map_data: dict, w: int, h: int) -> pygame.Surface:
    surf = pygame.Surface((w, h))
    theme = map_data.get("theme", {})
    floor_col = tuple(theme.get("floor_color", [20, 30, 20]))
    tint = tuple(theme.get("obstacle_tint", [100, 100, 100]))
    surf.fill(floor_col)
    scale_x = w / 1600
    scale_y = h / 1200
    for obs in map_data.get("obstacles", []):
        rx = int(obs.x * scale_x)
        ry = int(obs.y * scale_y)
        rw = max(2, int(obs.width * scale_x))
        rh = max(2, int(obs.height * scale_y))
        obs_col = tuple(max(0, min(255, (c + t) // 2)) for c, t in zip(obs.color, tint))
        pygame.draw.rect(surf, obs_col, (rx, ry, rw, rh))
    border_col = tuple(theme.get("border_color", [60, 80, 60]))
    pygame.draw.rect(surf, border_col, (0, 0, w, h), 2)
    return surf


class LoadoutScene(BaseScene):
    """
    Unified pre-match loadout screen: hull / weapons / map in one view.
    """

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._save_manager: SaveManager = SaveManager()
        self._progression: ProgressionManager = ProgressionManager()

        # Panel focus
        self._panel: int = LOADOUT_PANEL_HULL

        # Hull panel state
        self._tank_cursor: int = 0          # index into unlocked tank list
        self._unlocked_tanks: list[str] = []
        self._tank_configs: dict = {}        # type → config dict

        # Weapons panel state
        self._slot_focus: int = 0
        self._slot_selections: list[str | None] = [None] * MAX_WEAPON_SLOTS
        self._unlocked_weapons: set = set()
        self._weapon_configs: dict = {}

        # Map panel state
        self._map_cursor: int = 0
        self._map_data: list[dict] = []
        self._map_previews: list[pygame.Surface] = []

        # Profile / XP
        self._level: int = 1
        self._xp: int = 0
        self._unlock_levels: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        # --- Profile ---
        profile = self._save_manager.load_profile()

        # Retroactive unlock check — backfill rewards added after player leveled (v0.22)
        profile, backfilled = self._progression.backfill_unlocks(profile)
        if backfilled:
            self._save_manager.save_profile(profile)

        self._unlocked_tanks = list(profile.get("unlocked_tanks", ["light_tank"]))
        self._unlocked_weapons = set(profile.get("unlocked_weapons", ["standard_shell"]))
        self._level = int(profile.get("level", 1))
        self._xp = int(profile.get("xp", 0))

        # Build unlock-level lookup for locked-item display
        self._unlock_levels = {}
        for item in list(_TANK_ORDER) + list(_WEAPON_ORDER):
            lvl = self._progression.unlock_level_for(item)
            if lvl is not None:
                self._unlock_levels[item] = lvl

        # --- Tank configs ---
        all_tanks = load_yaml(TANKS_CONFIG)
        self._tank_configs = {}
        for t in _TANK_ORDER:
            cfg = dict(all_tanks.get(t, {}))
            cfg.setdefault("type", t)
            self._tank_configs[t] = cfg

        # --- Weapon configs ---
        all_weapons = load_yaml(WEAPONS_CONFIG)
        self._weapon_configs = {}
        for w in _WEAPON_ORDER:
            cfg = dict(all_weapons.get(w, {}))
            cfg.setdefault("type", w)
            self._weapon_configs[w] = cfg

        # --- Map data ---
        self._map_data = [
            load_map(os.path.join(MAPS_DIR, f"{n}.yaml"))
            for n in _MAP_NAMES
        ]
        self._map_previews = [
            _build_map_preview(md, _PREVIEW_W, _PREVIEW_H)
            for md in self._map_data
        ]

        # --- Defaults ---
        self._panel = LOADOUT_PANEL_HULL
        self._map_cursor = 0
        self._slot_focus = 0

        # Default tank cursor: first unlocked tank
        self._tank_cursor = 0
        for i, t in enumerate(_TANK_ORDER):
            if t in self._unlocked_tanks:
                self._tank_cursor = i
                break

        self._load_weapon_defaults()

        get_audio_manager().play_music(MUSIC_MENU)
        log.info(
            "LoadoutScene entered. tank=%s  weapons=%s  map=%s",
            self._selected_tank, self._slot_selections, _MAP_NAMES[self._map_cursor],
        )

    def on_exit(self) -> None:
        self._map_data = []
        self._map_previews = []
        log.debug("LoadoutScene exited.")

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        key = event.key

        if key == pygame.K_ESCAPE:
            self.manager.switch_to(SCENE_MENU)
            return

        if key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm()
            return

        if key == pygame.K_TAB:
            if event.mod & pygame.KMOD_SHIFT:
                self._panel = (self._panel - 1) % LOADOUT_PANEL_COUNT
            else:
                self._panel = (self._panel + 1) % LOADOUT_PANEL_COUNT
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
            return

        if self._panel == LOADOUT_PANEL_HULL:
            self._handle_hull(key)
        elif self._panel == LOADOUT_PANEL_WEAPONS:
            self._handle_weapons(key)
        elif self._panel == LOADOUT_PANEL_MAP:
            self._handle_map(key)

    def _handle_hull(self, key: int) -> None:
        unlocked = [t for t in _TANK_ORDER if t in self._unlocked_tanks]
        if not unlocked:
            return
        if key in (pygame.K_UP, pygame.K_w):
            # Move to previous unlocked tank
            cur = _TANK_ORDER[self._tank_cursor] if self._tank_cursor < len(_TANK_ORDER) else unlocked[0]
            try:
                ui = unlocked.index(cur)
            except ValueError:
                ui = 0
            ui = (ui - 1) % len(unlocked)
            self._tank_cursor = _TANK_ORDER.index(unlocked[ui])
            self._load_weapon_defaults()
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif key in (pygame.K_DOWN, pygame.K_s):
            cur = _TANK_ORDER[self._tank_cursor] if self._tank_cursor < len(_TANK_ORDER) else unlocked[0]
            try:
                ui = unlocked.index(cur)
            except ValueError:
                ui = 0
            ui = (ui + 1) % len(unlocked)
            self._tank_cursor = _TANK_ORDER.index(unlocked[ui])
            self._load_weapon_defaults()
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

    def _handle_weapons(self, key: int) -> None:
        if key in (pygame.K_UP, pygame.K_w):
            self._slot_focus = (self._slot_focus - 1) % MAX_WEAPON_SLOTS
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self._slot_focus = (self._slot_focus + 1) % MAX_WEAPON_SLOTS
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self._cycle_slot(self._slot_focus, -1)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._cycle_slot(self._slot_focus, +1)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

    def _handle_map(self, key: int) -> None:
        if key in (pygame.K_UP, pygame.K_w):
            self._map_cursor = (self._map_cursor - 1) % len(_MAP_NAMES)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self._map_cursor = (self._map_cursor + 1) % len(_MAP_NAMES)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

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

        # Title
        font_title = pygame.font.SysFont(None, 46)
        title = font_title.render("LOADOUT", True, COLOR_WHITE)
        surface.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 18))

        # Panels
        self._draw_hull_panel(surface, _PANEL_XS[0], _PANEL_TOP)
        self._draw_weapons_panel(surface, _PANEL_XS[1], _PANEL_TOP)
        self._draw_map_panel(surface, _PANEL_XS[2], _PANEL_TOP)

        # XP bar + confirm
        self._draw_xp_bar(surface)
        self._draw_confirm_button(surface)

        # Hint
        font_hint = pygame.font.SysFont(None, 20)
        hint = font_hint.render(
            "TAB  Switch Panel     \u2191\u2193  Select     \u2190\u2192  Cycle (Weapons)     ENTER  Start     ESC  Back",
            True, _COLOR_DIM,
        )
        surface.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2, SCREEN_HEIGHT - 20))

    # ------------------------------------------------------------------
    # Panel renderers
    # ------------------------------------------------------------------

    def _panel_rect(self, cx: int, cy: int) -> pygame.Rect:
        return pygame.Rect(cx, cy, _PANEL_W, _PANEL_H)

    def _draw_panel_chrome(
        self, surface: pygame.Surface, cx: int, cy: int, focused: bool, title: str
    ) -> None:
        """Draw panel background, border, and header label."""
        rect = self._panel_rect(cx, cy)
        pygame.draw.rect(surface, COLOR_DARK_GRAY, rect, border_radius=_PANEL_RADIUS)
        border_col = COLOR_NEON_PINK if focused else (55, 55, 60)
        border_w = 3 if focused else 1
        pygame.draw.rect(surface, border_col, rect, border_w, border_radius=_PANEL_RADIUS)

        font = pygame.font.SysFont(None, 28)
        lbl = font.render(title, True, COLOR_NEON_PINK if focused else COLOR_GRAY)
        surface.blit(lbl, (cx + 12, cy + 10))

    def _draw_hull_panel(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        focused = self._panel == LOADOUT_PANEL_HULL
        self._draw_panel_chrome(surface, cx, cy, focused, "HULL")

        font_name = pygame.font.SysFont(None, 26)
        font_lock = pygame.font.SysFont(None, 20)

        row_y = cy + 40
        row_h = 44

        for i, tank_type in enumerate(_TANK_ORDER):
            is_sel = (i == self._tank_cursor)
            is_locked = tank_type not in self._unlocked_tanks
            cfg = self._tank_configs.get(tank_type, {})
            label = tank_type.replace("_", " ").title()
            color = TANK_SELECT_COLORS.get(tank_type, COLOR_GRAY)

            if is_sel and focused:
                hl_rect = pygame.Rect(cx + 6, row_y - 2, _PANEL_W - 12, row_h)
                pygame.draw.rect(surface, (50, 50, 55), hl_rect, border_radius=4)
                pygame.draw.rect(surface, COLOR_NEON_PINK, hl_rect, 1, border_radius=4)
            elif is_sel:
                hl_rect = pygame.Rect(cx + 6, row_y - 2, _PANEL_W - 12, row_h)
                pygame.draw.rect(surface, (40, 40, 44), hl_rect, border_radius=4)

            # Colour dot
            dot_col = _COLOR_DIM if is_locked else color
            pygame.draw.circle(surface, dot_col, (cx + 22, row_y + row_h // 2), 7)

            # Name
            text_col = COLOR_GRAY if is_locked else (COLOR_WHITE if is_sel else (180, 180, 185))
            name_surf = font_name.render(label, True, text_col)
            surface.blit(name_surf, (cx + 38, row_y + (row_h - name_surf.get_height()) // 2))

            if is_locked:
                unlock_lvl = self._unlock_levels.get(tank_type)
                lock_label = f"Lv {unlock_lvl}" if unlock_lvl else "LOCKED"
                lock_surf = font_lock.render(lock_label, True, (150, 80, 80))
                surface.blit(lock_surf, (cx + _PANEL_W - lock_surf.get_width() - 12, row_y + (row_h - lock_surf.get_height()) // 2))

            row_y += row_h

        # Divider
        div_y = row_y + 4
        pygame.draw.line(surface, (55, 55, 60), (cx + 12, div_y), (cx + _PANEL_W - 12, div_y))

        # Stat bars for selected tank
        sel_cfg = self._tank_configs.get(self._selected_tank, {})
        bar_color = TANK_SELECT_COLORS.get(self._selected_tank, COLOR_GREEN)
        stat_y = div_y + 10
        self._draw_stat_bars(surface, cx + 12, stat_y, sel_cfg, _TANK_STATS, _norm_tank, bar_color)

    def _draw_weapons_panel(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        focused = self._panel == LOADOUT_PANEL_WEAPONS
        self._draw_panel_chrome(surface, cx, cy, focused, "WEAPONS")

        font_slot = pygame.font.SysFont(None, 24)
        font_wep = pygame.font.SysFont(None, 26)

        slot_row_y = cy + 40
        slot_row_h = 52

        for i in range(MAX_WEAPON_SLOTS):
            is_focused_slot = focused and (i == self._slot_focus)
            wtype = self._slot_selections[i]
            slot_num = f"{i + 1}"

            if is_focused_slot:
                hl_rect = pygame.Rect(cx + 6, slot_row_y - 2, _PANEL_W - 12, slot_row_h)
                pygame.draw.rect(surface, (50, 50, 55), hl_rect, border_radius=4)
                pygame.draw.rect(surface, COLOR_NEON_PINK, hl_rect, 1, border_radius=4)

            # Slot number badge
            badge_col = COLOR_NEON_PINK if is_focused_slot else (80, 80, 85)
            num_surf = font_slot.render(slot_num, True, badge_col)
            surface.blit(num_surf, (cx + 14, slot_row_y + (slot_row_h - num_surf.get_height()) // 2))

            # Weapon name (or "— empty —")
            if wtype:
                wlabel = wtype.replace("_", " ").title()
                wcolor = WEAPON_CARD_COLORS.get(wtype, COLOR_WHITE)
                wname_col = COLOR_WHITE if is_focused_slot else (170, 170, 175)
            else:
                wlabel = "— empty —"
                wcolor = _COLOR_DIM
                wname_col = (80, 80, 85)

            wname_surf = font_wep.render(wlabel, True, wname_col)
            surface.blit(wname_surf, (cx + 34, slot_row_y + (slot_row_h - wname_surf.get_height()) // 2))

            # Colored dot — neon pink when focused, weapon color otherwise
            if wtype or is_focused_slot:
                dot_col = COLOR_NEON_PINK if is_focused_slot else wcolor
                pygame.draw.circle(
                    surface, dot_col,
                    (cx + _PANEL_W - 24, slot_row_y + slot_row_h // 2), 5,
                )

            slot_row_y += slot_row_h

        # Divider
        div_y = slot_row_y + 4
        pygame.draw.line(surface, (55, 55, 60), (cx + 12, div_y), (cx + _PANEL_W - 12, div_y))

        # Stat bars for focused slot's weapon
        focused_wtype = self._slot_selections[self._slot_focus] if focused else self._slot_selections[0]
        stat_y = div_y + 10
        if focused_wtype:
            wcfg = self._weapon_configs.get(focused_wtype, {})
            bar_col = WEAPON_CARD_COLORS.get(focused_wtype, COLOR_GREEN)
            self._draw_stat_bars(surface, cx + 12, stat_y, wcfg, _WEAPON_STATS, _norm_weapon, bar_col)
        else:
            ph_font = pygame.font.SysFont(None, 22)
            ph = ph_font.render("No weapon selected", True, _COLOR_DIM)
            surface.blit(ph, (cx + 12, stat_y + 8))

    def _draw_map_panel(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        focused = self._panel == LOADOUT_PANEL_MAP
        self._draw_panel_chrome(surface, cx, cy, focused, "MAP")

        font_name = pygame.font.SysFont(None, 26)
        font_small = pygame.font.SysFont(None, 21)

        row_y = cy + 40
        row_h = 38

        for i, (map_name, map_data) in enumerate(zip(_MAP_NAMES, self._map_data)):
            is_sel = (i == self._map_cursor)
            disp = map_data.get("name", map_name)

            if is_sel and focused:
                hl = pygame.Rect(cx + 6, row_y - 2, _PANEL_W - 12, row_h)
                pygame.draw.rect(surface, (50, 50, 55), hl, border_radius=4)
                pygame.draw.rect(surface, COLOR_NEON_PINK, hl, 1, border_radius=4)
            elif is_sel:
                hl = pygame.Rect(cx + 6, row_y - 2, _PANEL_W - 12, row_h)
                pygame.draw.rect(surface, (40, 40, 44), hl, border_radius=4)

            col = COLOR_WHITE if is_sel else (150, 150, 155)
            n_surf = font_name.render(disp, True, col)
            surface.blit(n_surf, (cx + 16, row_y + (row_h - n_surf.get_height()) // 2))

            # Theme accent on right
            theme = map_data.get("theme", {})
            border_col = tuple(theme.get("border_color", [60, 80, 60]))
            dot_col = COLOR_NEON_PINK if is_sel else border_col
            pygame.draw.circle(surface, dot_col, (cx + _PANEL_W - 18, row_y + row_h // 2), 5)

            row_y += row_h

        # Thumbnail for selected map
        thumb_x = cx + (_PANEL_W - _PREVIEW_W) // 2
        thumb_y = row_y + 6
        if self._map_previews and self._map_cursor < len(self._map_previews):
            surface.blit(self._map_previews[self._map_cursor], (thumb_x, thumb_y))

        # Theme label below thumbnail
        label_y = thumb_y + _PREVIEW_H + 6
        if self._map_cursor < len(self._map_data):
            theme = self._map_data[self._map_cursor].get("theme", {})
            theme_name = theme.get("name", "")
            ambient = theme.get("ambient_label", "")
            theme_line = f"{theme_name}  ·  {ambient}" if ambient else theme_name
            accent = tuple(theme.get("border_color", [60, 80, 60]))
            t_surf = font_small.render(theme_line, True, accent if not focused else COLOR_NEON_PINK)
            surface.blit(t_surf, (cx + (_PANEL_W - t_surf.get_width()) // 2, label_y))

    # ------------------------------------------------------------------
    # XP bar + confirm button
    # ------------------------------------------------------------------

    def _draw_xp_bar(self, surface: pygame.Surface) -> None:
        """Level badge + XP progress bar centred below the three panels."""
        try:
            xp_table = load_yaml(XP_TABLE_CONFIG)
        except Exception:
            xp_table = {}

        level = self._level
        xp = self._xp

        # Determine xp thresholds from the table (keys are string level numbers)
        level_xp = int(xp_table.get(str(level), {}).get("xp_required", 0)) if xp_table else 0
        next_entry = xp_table.get(str(level + 1)) if xp_table else None
        next_xp = int(next_entry.get("xp_required", 0)) if next_entry else None

        if next_xp and next_xp > level_xp:
            ratio = max(0.0, min(1.0, (xp - level_xp) / (next_xp - level_xp)))
            xp_label = f"{xp} / {next_xp} XP"
        else:
            ratio = 1.0
            xp_label = f"{xp} XP  (MAX)"

        font = pygame.font.SysFont(None, 22)
        lh = font.get_linesize()

        cx = SCREEN_WIDTH // 2
        total_w = 60 + 8 + _XP_BAR_W + 8 + font.size(xp_label)[0]
        bx = cx - total_w // 2
        by = _XP_BAR_Y

        lvl_s = font.render(f"LVL {level}", True, COLOR_GRAY)
        surface.blit(lvl_s, (bx, by))

        bar_x = bx + lvl_s.get_width() + 8
        bar_y = by + (lh - 10) // 2
        bar_rect = pygame.Rect(bar_x, bar_y, _XP_BAR_W, 10)
        pygame.draw.rect(surface, (40, 40, 45), bar_rect, border_radius=3)
        if ratio > 0:
            fill = pygame.Rect(bar_x, bar_y, int(_XP_BAR_W * ratio), 10)
            pygame.draw.rect(surface, COLOR_GREEN, fill, border_radius=3)
        pygame.draw.rect(surface, (55, 55, 60), bar_rect, 1, border_radius=3)

        xp_s = font.render(xp_label, True, COLOR_GRAY)
        surface.blit(xp_s, (bar_x + _XP_BAR_W + 8, by))

    def _draw_confirm_button(self, surface: pygame.Surface) -> None:
        valid = self._slot_selections[0] is not None
        bg_col = (40, 90, 40) if valid else (50, 50, 55)
        border_col = COLOR_GREEN if valid else (80, 80, 85)

        bx = (SCREEN_WIDTH - _CONFIRM_W) // 2
        btn_rect = pygame.Rect(bx, _CONFIRM_Y, _CONFIRM_W, _CONFIRM_H)
        pygame.draw.rect(surface, bg_col, btn_rect, border_radius=6)
        pygame.draw.rect(surface, border_col, btn_rect, 1, border_radius=6)

        font = pygame.font.SysFont(None, 26)
        label = "CONFIRM   [ ENTER ]"
        lbl = font.render(label, True, COLOR_WHITE if valid else COLOR_GRAY)
        surface.blit(lbl, lbl.get_rect(center=btn_rect.center))

    # ------------------------------------------------------------------
    # Shared drawing helper
    # ------------------------------------------------------------------

    def _draw_stat_bars(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        cfg: dict,
        stats: list[tuple[str, str]],
        norm_fn,
        bar_color: tuple,
    ) -> None:
        font = pygame.font.SysFont(None, 20)
        for label, key in stats:
            raw = float(cfg.get(key, 0.0))
            ratio = norm_fn(raw, key)
            fill_w = int(ratio * _MAX_STAT_W)

            lbl_surf = font.render(label, True, (130, 130, 135))
            surface.blit(lbl_surf, (x, y))

            bar_y = y + 14
            track = pygame.Rect(x, bar_y, _MAX_STAT_W, _STAT_BAR_H)
            pygame.draw.rect(surface, (55, 55, 60), track, border_radius=3)
            if fill_w > 0:
                fill = pygame.Rect(x, bar_y, fill_w, _STAT_BAR_H)
                pygame.draw.rect(surface, bar_color, fill, border_radius=3)

            y += _STAT_ROW_H

    # ------------------------------------------------------------------
    # Slot cycling (weapon panel)
    # ------------------------------------------------------------------

    def _cycle_slot(self, slot_idx: int, direction: int) -> None:
        """Advance weapon choice for one slot (port of WeaponSelectScene._cycle_slot)."""
        can_empty = slot_idx > 0
        choices: list[str | None] = []
        if can_empty:
            choices.append(None)
        for wname in _WEAPON_ORDER:
            if wname not in self._unlocked_weapons:
                continue
            already_used = any(
                self._slot_selections[j] == wname
                for j in range(MAX_WEAPON_SLOTS)
                if j != slot_idx
            )
            if already_used:
                continue
            choices.append(wname)

        if not choices:
            return

        current = self._slot_selections[slot_idx]
        try:
            idx = choices.index(current)
        except ValueError:
            idx = 0

        self._slot_selections[slot_idx] = choices[(idx + direction) % len(choices)]

    # ------------------------------------------------------------------
    # Weapon defaults (called on enter + on tank change)
    # ------------------------------------------------------------------

    def _load_weapon_defaults(self) -> None:
        """Load slot defaults from the selected tank's default_weapons yaml field."""
        tank_cfg = self._tank_configs.get(self._selected_tank, {})
        defaults = tank_cfg.get("default_weapons", ["standard_shell", None, None])
        self._slot_selections = [None] * MAX_WEAPON_SLOTS
        for i, wname in enumerate(defaults[:MAX_WEAPON_SLOTS]):
            if wname and wname in self._unlocked_weapons:
                self._slot_selections[i] = wname
        # Slot 0 fallback
        if self._slot_selections[0] is None:
            for w in _WEAPON_ORDER:
                if w in self._unlocked_weapons:
                    self._slot_selections[0] = w
                    break

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------

    def _confirm(self) -> None:
        if self._slot_selections[0] is None:
            log.debug("LoadoutScene: slot 0 empty — cannot confirm.")
            return
        weapon_types = [w for w in self._slot_selections if w is not None]
        map_name = _MAP_NAMES[self._map_cursor]
        tank_type = self._selected_tank
        log.info(
            "LoadoutScene: confirmed tank=%s  weapons=%s  map=%s",
            tank_type, weapon_types, map_name,
        )
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        self.manager.switch_to(
            SCENE_GAME,
            tank_type=tank_type,
            weapon_types=weapon_types,
            map_name=map_name,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def _selected_tank(self) -> str:
        if 0 <= self._tank_cursor < len(_TANK_ORDER):
            return _TANK_ORDER[self._tank_cursor]
        unlocked = [t for t in _TANK_ORDER if t in self._unlocked_tanks]
        return unlocked[0] if unlocked else "light_tank"

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def is_tank_locked(self, tank_type: str) -> bool:
        return tank_type not in self._unlocked_tanks

    def is_weapon_locked(self, weapon_type: str) -> bool:
        return weapon_type not in self._unlocked_weapons
