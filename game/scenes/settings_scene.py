"""
game/scenes/settings_scene.py

SettingsScene — full implementation, v0.13.

Four sections, each navigable by UP/DOWN with LEFT/RIGHT adjusting values:

  [ AUDIO ]      Master / Music / SFX volume sliders
  [ DISPLAY ]    Resolution + Fullscreen cycle selectors
  [ CONTROLS ]   Four rebindable movement keys; Fire + Mute shown as read-only
  [ GAMEPLAY ]   Default AI difficulty cycle
  BACK           Fades back to main menu

Persistence:
  - Settings loaded from SaveManager on every on_enter().
  - Saved immediately on every value change (no explicit Save button).
  - Audio changes take effect instantly via AudioManager.set_volume().
  - Keybind changes take effect on the next match start.
  - Resolution / fullscreen changes are flagged "requires restart".

Conflict detection:
  - find_keybind_conflict() is a module-level function importable by tests.
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.ui.audio_manager import get_audio_manager
from game.ui.components import (
    CycleComponent,
    FadeTransition,
    KeybindComponent,
    ScrollingGrid,
    SliderComponent,
)
from game.utils.constants import (
    COLOR_BG,
    COLOR_GRAY,
    COLOR_NEON_PINK,
    DEFAULT_SETTINGS,
    MASTER_VOLUME_DEFAULT,
    MENU_FADE_DURATION,
    MENU_TITLE_ANIM_DURATION,
    MUSIC_MENU,
    MUSIC_VOLUME_DEFAULT,
    SCENE_MENU,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SETTINGS_SECTION_COLOR,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
    SFX_VOLUME_DEFAULT,
    SUPPORTED_RESOLUTIONS,
)
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
_CX: int = SCREEN_WIDTH // 2

_TITLE_Y: int = 44
_TITLE_FONT_SIZE: int = 72
_TITLE_SLIDE_OFFSET: int = 50
_TITLE_GLOW_COLOR: tuple = tuple(int(c * 0.18) for c in SETTINGS_SECTION_COLOR)

_CONTENT_Y: int = 90
_ROW_H: int = 30        # content row height (matches _COMP_ROW_H in components.py)
_SECTION_H: int = 28    # section header height
_SECTION_GAP: int = 8   # extra space prepended before each section except the first
_BACK_EXTRA_GAP: int = 14
_BACK_H: int = 40

_LABEL_X: int = 290
_CTRL_END: int = 980
_SCANLINE_ALPHA: int = 14

_SECTION_DIM: tuple = tuple(int(c * 0.28) for c in SETTINGS_SECTION_COLOR)
_WARNING_DURATION: float = 2.0

_FIRE_LMB_SUFFIX: str = " / LMB"  # always appended to Fire display (not editable)
_VOLUME_CHANNEL: dict = {
    "master_volume": "master",
    "music_volume":  "music",
    "sfx_volume":    "sfx",
}


# ---------------------------------------------------------------------------
# Row model
# ---------------------------------------------------------------------------

class _Row:
    __slots__ = ("kind", "label", "component", "settings_key", "focusable")

    def __init__(
        self,
        kind: str,
        label: str,
        component=None,
        settings_key: str = "",
        focusable: bool = True,
    ) -> None:
        self.kind = kind
        self.label = label
        self.component = component
        self.settings_key = settings_key
        self.focusable = focusable


# ---------------------------------------------------------------------------
# Module-level helpers (importable for tests)
# ---------------------------------------------------------------------------

def find_keybind_conflict(rows: list, key_name: str, current_action: str) -> str | None:
    """
    Return the display label of the first keybind row that already uses
    `key_name`, excluding the row for `current_action`.
    Returns None if no conflict exists.
    """
    for row in rows:
        if row.kind != "keybind":
            continue
        if row.settings_key == current_action:
            continue
        if isinstance(row.component, KeybindComponent) and row.component.value == key_name:
            return row.label
    return None


# ---------------------------------------------------------------------------
# SettingsScene
# ---------------------------------------------------------------------------

class SettingsScene(BaseScene):
    """Fully interactive settings screen with four sections."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._grid: ScrollingGrid = ScrollingGrid()
        self._fade: FadeTransition = FadeTransition(MENU_FADE_DURATION)
        self._title_timer: float = 0.0
        self._save_manager: SaveManager = SaveManager()
        self._settings: dict = {}
        self._rows: list[_Row] = []
        self._focusable: list[int] = []
        self._focus: int = 0
        self._warning: str = ""
        self._warning_timer: float = 0.0
        self._restart_needed: bool = False
        self._scanline_surf: pygame.Surface | None = None
        self._title_font: pygame.font.Font | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        self._settings = self._save_manager.load_settings()
        self._rows = self._build_rows(self._settings)
        self._focusable = [i for i, r in enumerate(self._rows) if r.focusable]
        self._focus = 0
        self._warning = ""
        self._warning_timer = 0.0
        self._restart_needed = False
        self._title_timer = 0.0
        self._fade.reset(on_complete=lambda: self.manager.switch_to(SCENE_MENU))

        if self._scanline_surf is None:
            self._scanline_surf = _build_scanline_surf(
                SCREEN_WIDTH, SCREEN_HEIGHT, _SCANLINE_ALPHA
            )
        if self._title_font is None:
            self._title_font = pygame.font.SysFont(None, _TITLE_FONT_SIZE)

        get_audio_manager().play_music(MUSIC_MENU)
        log.info("SettingsScene entered.")

    def on_exit(self) -> None:
        log.debug("SettingsScene exited.")

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._fade.is_active:
            return
        if event.type != pygame.KEYDOWN:
            return

        active = self._active_row

        # -- Keybind listen mode intercepts all keys --
        if (
            active
            and active.kind == "keybind"
            and isinstance(active.component, KeybindComponent)
            and active.component.is_listening
        ):
            if event.key == pygame.K_ESCAPE:
                active.component.cancel_listen()
                return
            proposed = active.component.try_bind(event.key)
            if proposed is not None:
                conflict = find_keybind_conflict(
                    self._rows, proposed, active.settings_key
                )
                if conflict:
                    self._set_warning(f"Already bound to {conflict.upper()}")
                else:
                    active.component.commit(proposed)
                    self._on_keybind_committed(active)
            return

        # -- ESC always exits --
        if event.key == pygame.K_ESCAPE:
            self._go_back()
            return

        # -- Navigation --
        if event.key in (pygame.K_UP, pygame.K_w):
            self._move_focus(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self._move_focus(+1)

        # -- Value adjustment --
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._adjust(event.key)

        # -- Confirm / activate --
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if active:
                if active.kind == "back":
                    self._go_back()
                elif active.kind == "keybind" and isinstance(
                    active.component, KeybindComponent
                ):
                    active.component.activate_listen()
                    get_audio_manager().play_sfx(SFX_UI_CONFIRM)

    def _move_focus(self, delta: int) -> None:
        if not self._focusable:
            return
        self._focus = (self._focus + delta) % len(self._focusable)
        get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

    def _adjust(self, key: int) -> None:
        row = self._active_row
        if row is None or row.component is None:
            return
        if not hasattr(row.component, "handle_input"):
            return
        if row.component.handle_input(key):
            self._on_value_change(row)
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

    def _go_back(self) -> None:
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        self._fade.start()

    # ------------------------------------------------------------------
    # Value change handlers
    # ------------------------------------------------------------------

    def _on_value_change(self, row: _Row) -> None:
        if row.kind == "slider":
            val = row.component.value
            channel = _VOLUME_CHANNEL.get(row.settings_key)
            if channel:
                get_audio_manager().set_volume(channel, val)
            self._settings[row.settings_key] = round(val, 4)

        elif row.kind == "cycle":
            val = row.component.value
            if row.settings_key == "resolution":
                w, h = val.split("x")
                self._settings["resolution"] = [int(w), int(h)]
                self._restart_needed = True
            elif row.settings_key == "fullscreen":
                self._settings["fullscreen"] = (val == "ON")
                self._restart_needed = True
            elif row.settings_key == "ai_difficulty":
                self._settings["ai_difficulty"] = val.lower()

        self._save_manager.save_settings(self._settings)

    def _on_keybind_committed(self, row: _Row) -> None:
        self._settings.setdefault("keybinds", {})[row.settings_key] = (
            row.component.value
        )
        self._save_manager.save_settings(self._settings)
        log.info("Keybind '%s' → '%s'", row.settings_key, row.component.value)

    def _set_warning(self, msg: str) -> None:
        self._warning = msg
        self._warning_timer = _WARNING_DURATION
        log.warning("Settings conflict: %s", msg)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._grid.update(dt)
        if self._title_timer < MENU_TITLE_ANIM_DURATION:
            self._title_timer = min(self._title_timer + dt, MENU_TITLE_ANIM_DURATION)
        if self._fade.is_active:
            self._fade.update(dt)
        if self._warning_timer > 0.0:
            self._warning_timer = max(0.0, self._warning_timer - dt)
            if self._warning_timer == 0.0:
                self._warning = ""

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        self._grid.draw(surface)
        if self._scanline_surf:
            surface.blit(self._scanline_surf, (0, 0))
        self._draw_title(surface)
        self._draw_all_rows(surface)
        self._draw_footer(surface)
        if self._warning:
            self._draw_warning(surface)
        self._fade.draw(surface)

    def _draw_title(self, surface: pygame.Surface) -> None:
        font = self._title_font or pygame.font.SysFont(None, _TITLE_FONT_SIZE)
        text = "SETTINGS"
        t = min(1.0, self._title_timer / MENU_TITLE_ANIM_DURATION)
        ease = 1.0 - (1.0 - t) ** 2
        title_color = tuple(int(c * ease) for c in SETTINGS_SECTION_COLOR)
        glow_color  = tuple(int(c * ease) for c in _TITLE_GLOW_COLOR)
        y = int(_TITLE_Y - _TITLE_SLIDE_OFFSET * (1.0 - ease))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            gs = font.render(text, True, glow_color)
            surface.blit(gs, gs.get_rect(center=(_CX + dx, y + dy)))
        ts = font.render(text, True, title_color)
        surface.blit(ts, ts.get_rect(center=(_CX, y)))

    def _draw_all_rows(self, surface: pygame.Surface) -> None:
        active = self._active_row
        y = _CONTENT_Y
        first_section = True

        f_sect = pygame.font.SysFont(None, 22)
        f_back = pygame.font.SysFont(None, 44)
        f_info = pygame.font.SysFont(None, 24)

        for row in self._rows:
            is_sel = (row is active and row.focusable)

            if row.kind == "section":
                if not first_section:
                    y += _SECTION_GAP
                first_section = False
                hdr = f_sect.render(f"[ {row.label} ]", True, SETTINGS_SECTION_COLOR)
                surface.blit(hdr, (_LABEL_X, y + (_SECTION_H - hdr.get_height()) // 2))
                pygame.draw.line(surface, _SECTION_DIM,
                                 (_LABEL_X, y + _SECTION_H - 2), (_CTRL_END, y + _SECTION_H - 2))
                y += _SECTION_H

            elif row.kind == "back":
                y += _BACK_EXTRA_GAP
                clr = COLOR_NEON_PINK if is_sel else (153, 153, 153)
                back_s = f_back.render("BACK", True, clr)
                back_r = back_s.get_rect(center=(_CX, y + _BACK_H // 2))
                surface.blit(back_s, back_r)
                if is_sel:
                    cur = f_back.render(">", True, COLOR_NEON_PINK)
                    surface.blit(cur, cur.get_rect(midright=(back_r.left - 12, back_r.centery)))
                y += _BACK_H

            else:
                # slider / cycle / keybind
                row.component.draw(surface, _LABEL_X, y, is_sel)
                # Fire row: append non-editable "/ LMB" suffix
                if row.settings_key == "fire":
                    suffix = f_info.render(_FIRE_LMB_SUFFIX, True, COLOR_GRAY)
                    surface.blit(suffix, (_LABEL_X + 360 + 80, y + (_ROW_H - f_info.get_linesize()) // 2))
                y += _ROW_H

    def _draw_footer(self, surface: pygame.Surface) -> None:
        f = pygame.font.SysFont(None, 19)
        parts = ["Keybind changes take effect on next match"]
        if self._restart_needed:
            parts.append("Resolution & fullscreen require restart")
        note = f.render("  •  ".join(parts), True, (65, 65, 70))
        surface.blit(note, note.get_rect(center=(_CX, SCREEN_HEIGHT - 18)))

    def _draw_warning(self, surface: pygame.Surface) -> None:
        f = pygame.font.SysFont(None, 24)
        warn = f.render(f"! {self._warning}", True, (220, 80, 60))
        surface.blit(warn, warn.get_rect(center=(_CX, SCREEN_HEIGHT - 44)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _active_row(self) -> _Row | None:
        if not self._focusable:
            return None
        return self._rows[self._focusable[self._focus]]

    def _build_rows(self, s: dict) -> list[_Row]:
        rows: list[_Row] = []
        kb = s.get("keybinds", DEFAULT_SETTINGS["keybinds"])

        # AUDIO
        rows.append(_Row("section", "AUDIO", focusable=False))
        rows.append(_Row("slider", "Master Volume",
            SliderComponent("Master Volume", 0.0, 1.0,
                            s.get("master_volume", MASTER_VOLUME_DEFAULT)),
            "master_volume"))
        rows.append(_Row("slider", "Music Volume",
            SliderComponent("Music Volume", 0.0, 1.0,
                            s.get("music_volume", MUSIC_VOLUME_DEFAULT)),
            "music_volume"))
        rows.append(_Row("slider", "SFX Volume",
            SliderComponent("SFX Volume", 0.0, 1.0,
                            s.get("sfx_volume", SFX_VOLUME_DEFAULT)),
            "sfx_volume"))

        # DISPLAY
        rows.append(_Row("section", "DISPLAY", focusable=False))
        res_opts = [f"{w}x{h}" for w, h in SUPPORTED_RESOLUTIONS]
        cur_res = s.get("resolution", [SCREEN_WIDTH, SCREEN_HEIGHT])
        cur_res_str = f"{cur_res[0]}x{cur_res[1]}"
        cur_res_idx = next(
            (i for i, o in enumerate(res_opts) if o == cur_res_str), 0
        )
        rows.append(_Row("cycle", "Resolution",
            CycleComponent("Resolution", res_opts, cur_res_idx),
            "resolution"))
        fs_idx = 1 if s.get("fullscreen", False) else 0
        rows.append(_Row("cycle", "Fullscreen",
            CycleComponent("Fullscreen", ["OFF", "ON"], fs_idx),
            "fullscreen"))

        # CONTROLS
        rows.append(_Row("section", "CONTROLS", focusable=False))
        for action, label in (
            ("move_forward",  "Move Forward"),
            ("move_backward", "Move Backward"),
            ("rotate_left",   "Rotate Left"),
            ("rotate_right",  "Rotate Right"),
            ("fire",          "Fire"),
            ("mute",          "Mute"),
        ):
            default_key = DEFAULT_SETTINGS["keybinds"].get(action, action[0])
            rows.append(_Row("keybind", label,
                KeybindComponent(label, action, kb.get(action, default_key)),
                action))

        # GAMEPLAY
        rows.append(_Row("section", "GAMEPLAY", focusable=False))
        diff_opts = ["EASY", "MEDIUM", "HARD"]
        cur_diff  = s.get("ai_difficulty", "medium").upper()
        diff_idx  = diff_opts.index(cur_diff) if cur_diff in diff_opts else 1
        rows.append(_Row("cycle", "AI Difficulty",
            CycleComponent("AI Difficulty", diff_opts, diff_idx),
            "ai_difficulty"))

        # BACK
        rows.append(_Row("back", "BACK", focusable=True))

        return rows


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _build_scanline_surf(width: int, height: int, alpha: int) -> pygame.Surface:
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(0, height, 2):
        pygame.draw.line(surf, (0, 0, 0, alpha), (0, y), (width, y))
    return surf
