"""
game/scenes/weapon_select_scene.py

WeaponSelectScene — pre-match loadout selection screen.

Flow:
    TankSelectScene (ENTER) → WeaponSelectScene → (confirm) → GameplayScene
                                               → (ESC)     → TankSelectScene

Layout: Left column = 3 slot rows + confirm button.
        Right column = stat preview for the focused slot's weapon.

Slot 1 is mandatory (can't leave empty).
Slots 2 and 3 are optional; choosing "--- empty ---" leaves them unfilled.
No duplicate weapon types across slots.

Controls:
    UP / DOWN           — navigate between rows (3 slots + confirm)
    LEFT / RIGHT        — cycle weapon choice within the focused slot row
    ENTER / SPACE       — confirm loadout (requires slot 1 filled)
    ESC                 — return to TankSelectScene (cursor preserved)
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
    COLOR_NEON_PINK,
    COLOR_RED,
    COLOR_WHITE,
    MAX_BAR_WIDTH,
    MAX_WEAPON_SLOTS,
    MUSIC_MENU,
    SCENE_MAP_SELECT,
    SCENE_TANK_SELECT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
    TANKS_CONFIG,
    WEAPON_CARD_COLORS,
    WEAPON_STAT_MAX,
    WEAPONS_CONFIG,
)
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layout constants (internal to this scene)
# ---------------------------------------------------------------------------

# Left panel (slot rows + confirm)
_LEFT_PANEL_X: int = 60
_LEFT_PANEL_W: int = 520

# Row layout
_ROW_H: int = 72           # height of each slot row
_ROW_GAP: int = 16         # vertical gap between rows
_ROW_TOP: int = 140        # y of first slot row
_ROW_RADIUS: int = 8
_SELECTED_BORDER_W: int = 3

# Confirm button row
_CONFIRM_ROW_IDX: int = MAX_WEAPON_SLOTS   # 3 — below the 3 slot rows
_CONFIRM_Y: int = _ROW_TOP + MAX_WEAPON_SLOTS * (_ROW_H + _ROW_GAP) + 8

# Right panel (preview)
_PREVIEW_X: int = 640
_PREVIEW_Y: int = 110
_PREVIEW_W: int = 570
_PREVIEW_H: int = 400
_PREVIEW_RADIUS: int = 10

# Stat bar
_STAT_BAR_H: int = 10
_STAT_ROW_GAP: int = 26
_STATS: list = [
    ("Damage",    "damage"),
    ("Speed",     "speed"),
    ("Fire Rate", "fire_rate"),
    ("Range",     "max_range"),
]

# Animated bullet preview on the right panel
_BULLET_RADIUS: int = 5

# Weapon display order
_WEAPON_ORDER: list = [
    "standard_shell",
    "spread_shot",
    "bouncing_round",
    "homing_missile",
]


# ---------------------------------------------------------------------------
# Module-level helper (exported for tests)
# ---------------------------------------------------------------------------

def _normalise_weapon(value: float, stat_key: str) -> float:
    """Return value / WEAPON_STAT_MAX[stat_key], clamped to [0.0, 1.0].
    Returns 0.0 for stat keys not present in WEAPON_STAT_MAX."""
    maximum = WEAPON_STAT_MAX.get(stat_key)
    if maximum is None or maximum <= 0:
        return 0.0
    return max(0.0, min(1.0, value / maximum))


class WeaponSelectScene(BaseScene):
    """Pre-match 3-slot loadout selection UI."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._save_manager: SaveManager = SaveManager()
        self._progression: ProgressionManager = ProgressionManager()
        self._weapon_data: dict[str, dict] = {}   # type → config dict
        self._unlocked: set[str] = set()
        self._tank_type: str = "medium_tank"
        self._ai_count: int = 1
        self._player_level: int = 1
        self._unlock_levels: dict[str, int] = {}

        # Slot state
        self._slot_selections: list[str | None] = [None] * MAX_WEAPON_SLOTS
        self._focused_row: int = 0   # 0-2 = slot rows, 3 = confirm button

        self._anim_t: float = 0.0   # animation timer (seconds)

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        self._tank_type = kwargs.get("tank_type", "medium_tank")
        self._ai_count = int(kwargs.get("ai_count", 1))

        # Load all weapon configs
        all_weapons = load_yaml(WEAPONS_CONFIG)
        self._weapon_data = {}
        for w in _WEAPON_ORDER:
            cfg = dict(all_weapons.get(w, {}))
            cfg.setdefault("type", w)
            self._weapon_data[w] = cfg

        # Load profile
        profile = self._save_manager.load_profile()
        self._unlocked = set(profile.get("unlocked_weapons", ["standard_shell"]))
        self._player_level = int(profile.get("level", 1))

        # Build unlock-level lookup
        self._unlock_levels = {}
        for w in _WEAPON_ORDER:
            lvl = self._progression.unlock_level_for(w)
            if lvl is not None:
                self._unlock_levels[w] = lvl

        # Read tank's default loadout from tanks.yaml
        tank_cfg = load_yaml(TANKS_CONFIG).get(self._tank_type, {})
        defaults = tank_cfg.get("default_weapons", ["standard_shell", None, None])

        # Populate slot selections from defaults (only if weapon is unlocked)
        self._slot_selections = [None] * MAX_WEAPON_SLOTS
        for i, wname in enumerate(defaults[:MAX_WEAPON_SLOTS]):
            if wname and wname in self._unlocked:
                self._slot_selections[i] = wname

        # If slot 1 is still empty, pick the first unlocked weapon available
        if self._slot_selections[0] is None:
            for w in _WEAPON_ORDER:
                if w in self._unlocked:
                    self._slot_selections[0] = w
                    break

        self._focused_row = 0
        self._anim_t = 0.0
        get_audio_manager().play_music(MUSIC_MENU)

        log.info(
            "WeaponSelectScene entered. Tank=%s  AI=%d  Unlocked: %s  Defaults: %s",
            self._tank_type, self._ai_count,
            sorted(self._unlocked), self._slot_selections,
        )

    def on_exit(self) -> None:
        log.debug("WeaponSelectScene exited.")

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_ESCAPE:
            log.info("WeaponSelectScene: ESC — returning to tank select.")
            self.manager.switch_to(SCENE_TANK_SELECT, from_weapon_select=True)
            return

        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm_selection()
            return

        up = event.key in (pygame.K_UP,)
        down = event.key in (pygame.K_DOWN,)
        left = event.key in (pygame.K_LEFT, pygame.K_a)
        right = event.key in (pygame.K_RIGHT, pygame.K_d)

        total_rows = MAX_WEAPON_SLOTS + 1  # 3 slots + confirm

        if up:
            self._focused_row = (self._focused_row - 1) % total_rows
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif down:
            self._focused_row = (self._focused_row + 1) % total_rows
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif left and self._focused_row < MAX_WEAPON_SLOTS:
            self._cycle_slot(self._focused_row, -1)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)
        elif right and self._focused_row < MAX_WEAPON_SLOTS:
            self._cycle_slot(self._focused_row, +1)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

    def _cycle_slot(self, slot_idx: int, direction: int) -> None:
        """Advance the weapon choice for one slot by direction (+1 / -1).

        Slot 0 cannot be set to None (always requires a weapon).
        Slots 1-2 allow None ("empty").
        Already-selected weapons are skipped to prevent duplicates.
        """
        can_empty = slot_idx > 0

        choices: list[str | None] = []
        if can_empty:
            choices.append(None)
        for wname in _WEAPON_ORDER:
            if wname not in self._unlocked:
                continue
            # Skip if this weapon is already selected in a different slot
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

        idx = (idx + direction) % len(choices)
        self._slot_selections[slot_idx] = choices[idx]

    def _confirm_selection(self) -> None:
        """Confirm the loadout if slot 1 is filled."""
        if self._slot_selections[0] is None:
            log.debug("WeaponSelectScene: slot 1 empty — ignoring confirm.")
            return

        weapon_types = [w for w in self._slot_selections if w is not None]

        log.info(
            "WeaponSelectScene: confirmed weapons=%s  tank=%s  opponents=%d",
            weapon_types, self._tank_type, self._ai_count,
        )
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        self.manager.switch_to(
            SCENE_MAP_SELECT,
            tank_type=self._tank_type,
            ai_count=self._ai_count,
            weapon_types=weapon_types,
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._anim_t += dt

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        self._draw_header(surface)
        self._draw_level_badge(surface)
        self._draw_slot_rows(surface)
        self._draw_confirm_button(surface)
        self._draw_preview_panel(surface)
        self._draw_footer(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 52)
        heading = font.render("Select Your Loadout", True, COLOR_WHITE)
        surface.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 55)))

    def _draw_level_badge(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 28)
        label = font.render(f"Level {self._player_level}", True, COLOR_NEON_PINK)
        margin = 18
        surface.blit(label, (SCREEN_WIDTH - label.get_width() - margin, margin))

    def _draw_footer(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 26)
        hint = font.render(
            "▲ ▼  Navigate     ◄ ►  Choose Weapon     ENTER  Confirm     ESC  Back",
            True, COLOR_GRAY,
        )
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 26)))

    def _draw_slot_rows(self, surface: pygame.Surface) -> None:
        for i in range(MAX_WEAPON_SLOTS):
            self._draw_slot_row(surface, i)

    def _draw_slot_row(self, surface: pygame.Surface, slot_idx: int) -> None:
        row_y = _ROW_TOP + slot_idx * (_ROW_H + _ROW_GAP)
        row_rect = pygame.Rect(_LEFT_PANEL_X, row_y, _LEFT_PANEL_W, _ROW_H)
        is_focused = (self._focused_row == slot_idx)

        # Background
        bg = (50, 50, 55) if is_focused else (32, 32, 36)
        pygame.draw.rect(surface, bg, row_rect, border_radius=_ROW_RADIUS)
        if is_focused:
            pygame.draw.rect(
                surface, COLOR_NEON_PINK, row_rect,
                width=_SELECTED_BORDER_W, border_radius=_ROW_RADIUS,
            )

        cy = row_rect.centery
        label_font = pygame.font.SysFont(None, 26)
        name_font = pygame.font.SysFont(None, 34)

        # "Slot N" label on the left
        slot_label = label_font.render(f"Slot {slot_idx + 1}", True, COLOR_GRAY)
        surface.blit(slot_label, (row_rect.left + 16, cy - slot_label.get_height() // 2))

        # Weapon name (centred in row)
        selection = self._slot_selections[slot_idx]
        if selection:
            wname = selection.replace("_", " ").title()
            wcolor = COLOR_NEON_PINK if is_focused else COLOR_WHITE
        else:
            wname = "--- empty ---"
            wcolor = COLOR_GRAY

        name_surf = name_font.render(wname, True, wcolor)
        surface.blit(name_surf, name_surf.get_rect(center=(row_rect.centerx + 40, cy)))

        # Navigation arrows on the right (only on focused row)
        if is_focused:
            arrow_font = pygame.font.SysFont(None, 30)
            lbl = arrow_font.render("◄  ►", True, COLOR_NEON_PINK)
            surface.blit(lbl, (row_rect.right - lbl.get_width() - 16, cy - lbl.get_height() // 2))

    def _draw_confirm_button(self, surface: pygame.Surface) -> None:
        is_focused = (self._focused_row == _CONFIRM_ROW_IDX)
        can_confirm = (self._slot_selections[0] is not None)

        btn_rect = pygame.Rect(_LEFT_PANEL_X, _CONFIRM_Y, _LEFT_PANEL_W, 50)
        if can_confirm:
            bg = (60, 60, 30) if is_focused else (40, 40, 20)
            border = COLOR_NEON_PINK if is_focused else (120, 120, 60)
            txt_color = COLOR_WHITE if is_focused else (200, 200, 120)
        else:
            bg = (35, 35, 35)
            border = COLOR_DARK_GRAY
            txt_color = COLOR_GRAY

        pygame.draw.rect(surface, bg, btn_rect, border_radius=_ROW_RADIUS)
        pygame.draw.rect(surface, border, btn_rect, width=2, border_radius=_ROW_RADIUS)

        font = pygame.font.SysFont(None, 34)
        label = "CONFIRM LOADOUT" if can_confirm else "CONFIRM  (fill Slot 1 first)"
        lbl_surf = font.render(label, True, txt_color)
        surface.blit(lbl_surf, lbl_surf.get_rect(center=btn_rect.center))

    def _draw_preview_panel(self, surface: pygame.Surface) -> None:
        """Show stats for the weapon in the currently focused slot (if any)."""
        # Determine which weapon to preview
        if self._focused_row < MAX_WEAPON_SLOTS:
            preview_type = self._slot_selections[self._focused_row]
        else:
            # Confirm row: preview slot 1's weapon
            preview_type = self._slot_selections[0]

        panel_rect = pygame.Rect(_PREVIEW_X, _PREVIEW_Y, _PREVIEW_W, _PREVIEW_H)
        pygame.draw.rect(surface, (28, 28, 32), panel_rect, border_radius=_PREVIEW_RADIUS)
        pygame.draw.rect(surface, (60, 60, 70), panel_rect,
                         width=2, border_radius=_PREVIEW_RADIUS)

        if not preview_type:
            # No weapon selected — placeholder text
            font = pygame.font.SysFont(None, 32)
            msg = font.render("No weapon selected", True, COLOR_GRAY)
            surface.blit(msg, msg.get_rect(center=panel_rect.center))
            return

        wd = self._weapon_data.get(preview_type, {})
        color = WEAPON_CARD_COLORS.get(preview_type, COLOR_GRAY)
        cx = panel_rect.centerx
        y = panel_rect.top + 24

        # Weapon name
        name_font = pygame.font.SysFont(None, 42)
        name_text = preview_type.replace("_", " ").title()
        name_surf = name_font.render(name_text, True, color)
        surface.blit(name_surf, name_surf.get_rect(center=(cx, y)))
        y += 46

        # Animated bullet preview
        self._draw_bullet_preview(surface, panel_rect, wd, color)
        y += 28

        # Description
        desc_font = pygame.font.SysFont(None, 24)
        desc = wd.get("description", "")
        self._draw_wrapped(surface, desc_font, desc, COLOR_GRAY, cx, y, _PREVIEW_W - 48)
        y += 56

        # Stat bars
        bar_left = panel_rect.left + 32
        stat_label_font = pygame.font.SysFont(None, 24)

        for label, key in _STATS:
            raw = float(wd.get(key, 0.0))
            ratio = _normalise_weapon(raw, key)
            bar_w = int(ratio * MAX_BAR_WIDTH)

            lbl = stat_label_font.render(label, True, COLOR_GRAY)
            surface.blit(lbl, (bar_left, y))

            bar_y = y + 16
            track_rect = pygame.Rect(bar_left, bar_y, MAX_BAR_WIDTH, _STAT_BAR_H)
            pygame.draw.rect(surface, (55, 55, 60), track_rect, border_radius=3)
            if bar_w > 0:
                fill_rect = pygame.Rect(bar_left, bar_y, bar_w, _STAT_BAR_H)
                pygame.draw.rect(surface, color, fill_rect, border_radius=3)

            # Value label to the right of the bar
            val_lbl = stat_label_font.render(f"{raw:.0f}", True, COLOR_WHITE)
            surface.blit(val_lbl, (bar_left + MAX_BAR_WIDTH + 8, bar_y - 2))

            y += _STAT_ROW_GAP

    def _draw_bullet_preview(
        self,
        surface: pygame.Surface,
        panel_rect: pygame.Rect,
        wd: dict,
        color: tuple,
    ) -> None:
        """Animated bullet dot scrolling left-to-right inside the preview panel."""
        track_y = panel_rect.top + 100
        track_left = panel_rect.left + 32
        track_right = panel_rect.right - 32
        track_w = track_right - track_left

        pygame.draw.line(
            surface, (50, 50, 55), (track_left, track_y), (track_right, track_y), 1
        )

        raw_speed = float(wd.get("speed", 200.0))
        speed_ratio = _normalise_weapon(raw_speed, "speed")
        anim_speed = 0.5 + speed_ratio * 1.5
        t = (self._anim_t * anim_speed) % 1.0

        bx = int(track_left + t * track_w)
        pygame.draw.circle(surface, color, (bx, track_y), _BULLET_RADIUS)

    # ------------------------------------------------------------------
    # Public helpers (used by tests without pygame display)
    # ------------------------------------------------------------------

    def is_locked(self, weapon_type: str) -> bool:
        return weapon_type not in self._unlocked

    def can_select(self, weapon_type: str) -> bool:
        return weapon_type in _WEAPON_ORDER and weapon_type in self._unlocked

    # ------------------------------------------------------------------
    # Static drawing helper
    # ------------------------------------------------------------------

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
