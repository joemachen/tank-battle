"""
game/scenes/profile_select_scene.py

ProfileSelectScene — profile slot picker.

Shown at app startup (before the main menu) and reachable via
"SWITCH PROFILE" in the main menu.

Layout:
  Title "SELECT PROFILE" at top.
  4 slot cards listed vertically:
    • Occupied slot — shows name, level, XP; active slot marked with ★
    • Empty slot    — shows "[EMPTY]"

Navigation:
  UP / DOWN (or W / S)  — move cursor
  ENTER / SPACE         — activate selected slot
    • Occupied → set_active_profile + fade → MainMenuScene
    • Empty    → inline name entry modal
  DELETE / F2           — open delete-confirmation modal (occupied slots only)
  ESC                   — return to menu (only if at least one profile exists)

Name entry modal:
  Printable chars   — append (max PROFILE_NAME_MAX_LEN)
  BACKSPACE         — remove last char
  ENTER             — confirm; blank name defaults to "Player N"
  ESC               — cancel

Delete-confirmation modal:
  Y / ENTER  — confirm delete
  N / ESC    — cancel
"""

import json
import os

import pygame

from game.scenes.base_scene import BaseScene
from game.ui.audio_manager import get_audio_manager
from game.ui.components import FadeTransition
from game.utils.constants import (
    COLOR_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_NEON_PINK,
    COLOR_RED,
    COLOR_WHITE,
    DEFAULT_PROFILE,
    GAME_VERSION,
    MAX_PROFILES,
    MENU_FADE_DURATION,
    PROFILE_NAME_MAX_LEN,
    PROFILES_DIR,
    SCENE_MENU,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
)
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
_CX: int = SCREEN_WIDTH // 2

_TITLE_Y: int = 75
_TITLE_FONT_SIZE: int = 68

_HINT_FONT_SIZE: int = 22

_SLOT_Y_START: int = 195
_SLOT_SPACING: int = 108
_SLOT_W: int = 580
_SLOT_H: int = 86
_SLOT_FONT_SIZE: int = 36
_SUB_FONT_SIZE: int = 23

_MODAL_FONT_SIZE: int = 32

# Colours
_COLOR_EMPTY: tuple = (80, 80, 90)
_COLOR_SLOT_BG: tuple = (28, 30, 38)
_COLOR_SLOT_SEL: tuple = (38, 44, 62)
_COLOR_BORDER_DIM: tuple = (55, 55, 68)


class ProfileSelectScene(BaseScene):
    """Profile slot selection — shown at startup and via SWITCH PROFILE."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._save: SaveManager = SaveManager()
        self._cursor: int = 0
        self._index: dict = {}

        # Mode: "select" | "name_entry" | "confirm_delete"
        self._mode: str = "select"
        self._entry_name: str = ""
        self._entry_slot: int = 0
        self._delete_slot: int = 0

        self._fade: FadeTransition = FadeTransition(MENU_FADE_DURATION)

        # Font cache
        self._slot_font: pygame.font.Font | None = None
        self._sub_font: pygame.font.Font | None = None
        self._hint_font: pygame.font.Font | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        self._cursor = 0
        self._mode = "select"
        self._entry_name = ""
        self._refresh_index()
        self._fade.reset(on_complete=lambda: self.manager.switch_to(SCENE_MENU))

        if self._slot_font is None:
            self._slot_font = pygame.font.SysFont(None, _SLOT_FONT_SIZE)
        if self._sub_font is None:
            self._sub_font = pygame.font.SysFont(None, _SUB_FONT_SIZE)
        if self._hint_font is None:
            self._hint_font = pygame.font.SysFont(None, _HINT_FONT_SIZE)

        log.info("ProfileSelectScene entered. Profiles: %s", list(self._index.get("profiles", {}).keys()))

    def on_exit(self) -> None:
        log.debug("ProfileSelectScene exited.")

    # ------------------------------------------------------------------
    # Input dispatch
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._fade.is_active:
            return
        if event.type != pygame.KEYDOWN:
            return

        if self._mode == "name_entry":
            self._handle_name_entry(event)
        elif self._mode == "confirm_delete":
            self._handle_delete_confirm(event)
        else:
            self._handle_select(event)

    # ------------------------------------------------------------------
    # Input handlers
    # ------------------------------------------------------------------

    def _handle_select(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_UP, pygame.K_w):
            self._cursor = (self._cursor - 1) % MAX_PROFILES
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self._cursor = (self._cursor + 1) % MAX_PROFILES
            get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate_slot(self._cursor)

        elif event.key in (pygame.K_DELETE, pygame.K_F2):
            if self._is_occupied(self._cursor):
                self._delete_slot = self._cursor
                self._mode = "confirm_delete"

        elif event.key == pygame.K_ESCAPE:
            # Only navigate back if at least one profile already exists
            if self._has_any_profile():
                self._fade.start()

    def _handle_name_entry(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_RETURN:
            name = self._entry_name.strip() or f"Player {self._entry_slot + 1}"
            self._create_profile(self._entry_slot, name)
            get_audio_manager().play_sfx(SFX_UI_CONFIRM)
            self._fade.start()

        elif event.key == pygame.K_ESCAPE:
            self._mode = "select"
            self._entry_name = ""

        elif event.key == pygame.K_BACKSPACE:
            self._entry_name = self._entry_name[:-1]

        else:
            ch = event.unicode
            if ch and ch.isprintable() and len(self._entry_name) < PROFILE_NAME_MAX_LEN:
                self._entry_name += ch

    def _handle_delete_confirm(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_y, pygame.K_RETURN):
            self._delete_profile(self._delete_slot)
            self._mode = "select"
            get_audio_manager().play_sfx(SFX_UI_CONFIRM)

        elif event.key in (pygame.K_n, pygame.K_ESCAPE):
            self._mode = "select"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _activate_slot(self, slot: int) -> None:
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        if self._is_occupied(slot):
            self._save.set_active_profile(slot)
            self._fade.start()
        else:
            # Begin inline name entry for this empty slot
            self._entry_slot = slot
            self._entry_name = ""
            self._mode = "name_entry"

    def _create_profile(self, slot: int, name: str) -> None:
        """Write a fresh profile to slot and register it in the index."""
        self._save.set_active_profile(slot)
        self._save.save_profile(dict(DEFAULT_PROFILE))
        idx = self.load_profiles_index_safe()
        idx.setdefault("profiles", {})[str(slot)] = {"name": name, "slot": slot}
        self._save.save_profiles_index(idx)
        self._refresh_index()
        log.info("Created profile slot %d  name=%r", slot, name)

    def _delete_profile(self, slot: int) -> None:
        """Delete a profile slot; if active, switch active to another slot."""
        self._save.delete_profile(slot)
        # If the deleted slot was active, reassign active slot
        idx = self.load_profiles_index_safe()
        profiles = idx.get("profiles", {})
        if self._save.active_slot == slot:
            remaining = sorted(int(k) for k in profiles)
            new_slot = remaining[0] if remaining else 0
            self._save.set_active_profile(new_slot)
        self._refresh_index()
        log.info("Deleted profile slot %d", slot)

    def load_profiles_index_safe(self) -> dict:
        """Reload the index from disk (bypasses stale in-memory cache)."""
        return self._save.load_profiles_index()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_index(self) -> None:
        self._index = self._save.load_profiles_index()

    def _is_occupied(self, slot: int) -> bool:
        return str(slot) in self._index.get("profiles", {})

    def _has_any_profile(self) -> bool:
        return bool(self._index.get("profiles", {}))

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self._fade.is_active:
            self._fade.update(dt)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        self._draw_title(surface)
        self._draw_slots(surface)
        self._draw_version(surface)

        if self._mode == "name_entry":
            self._draw_name_entry_modal(surface)
        elif self._mode == "confirm_delete":
            self._draw_delete_confirm_modal(surface)

        self._fade.draw(surface)

    def _draw_title(self, surface: pygame.Surface) -> None:
        title_font = pygame.font.SysFont(None, _TITLE_FONT_SIZE)
        title = title_font.render("SELECT PROFILE", True, COLOR_NEON_PINK)
        surface.blit(title, title.get_rect(center=(_CX, _TITLE_Y)))

        hint_text = "ENTER to select  ·  DELETE to remove  ·  ESC to return (if profile exists)"
        hint = self._hint_font.render(hint_text, True, COLOR_GRAY)
        surface.blit(hint, hint.get_rect(center=(_CX, _TITLE_Y + 40)))

    def _draw_slots(self, surface: pygame.Surface) -> None:
        for i in range(MAX_PROFILES):
            y = _SLOT_Y_START + i * _SLOT_SPACING
            rect = pygame.Rect(_CX - _SLOT_W // 2, y - _SLOT_H // 2, _SLOT_W, _SLOT_H)
            is_sel = (i == self._cursor and self._mode == "select")

            bg = _COLOR_SLOT_SEL if is_sel else _COLOR_SLOT_BG
            border = COLOR_NEON_PINK if is_sel else _COLOR_BORDER_DIM
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            pygame.draw.rect(surface, border, rect, 2, border_radius=8)

            if self._is_occupied(i):
                self._draw_occupied_slot(surface, i, rect)
            else:
                self._draw_empty_slot(surface, i, rect)

            if is_sel:
                cur = self._slot_font.render(">", True, COLOR_NEON_PINK)
                surface.blit(cur, cur.get_rect(midright=(rect.left - 12, rect.centery)))

    def _draw_occupied_slot(self, surface: pygame.Surface, slot: int, rect: pygame.Rect) -> None:
        meta = self._index.get("profiles", {}).get(str(slot), {})
        name = meta.get("name", f"Player {slot + 1}")

        # Read profile data directly for level/xp display
        path = os.path.join(PROFILES_DIR, f"profile_{slot}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                prof = json.load(f)
        except (OSError, json.JSONDecodeError):
            prof = dict(DEFAULT_PROFILE)

        level = prof.get("level", 1)
        xp = prof.get("xp", 0)

        active_mark = "★ " if slot == self._save.active_slot else "   "
        label = f"{active_mark}SLOT {slot + 1}  {name}"
        ls = self._slot_font.render(label, True, COLOR_WHITE)
        surface.blit(ls, ls.get_rect(midleft=(rect.left + 20, rect.centery - 12)))

        stats = self._sub_font.render(f"Level {level}  ·  {xp} XP", True, COLOR_GRAY)
        surface.blit(stats, stats.get_rect(midleft=(rect.left + 20, rect.centery + 16)))

    def _draw_empty_slot(self, surface: pygame.Surface, slot: int, rect: pygame.Rect) -> None:
        label = f"SLOT {slot + 1}  —  [EMPTY]"
        ls = self._slot_font.render(label, True, _COLOR_EMPTY)
        surface.blit(ls, ls.get_rect(center=rect.center))

    def _draw_version(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 20)
        ver = font.render(GAME_VERSION, True, COLOR_GRAY)
        surface.blit(
            ver,
            (SCREEN_WIDTH - ver.get_width() - 16, SCREEN_HEIGHT - ver.get_height() - 14),
        )

    def _draw_name_entry_modal(self, surface: pygame.Surface) -> None:
        self._draw_modal_overlay(surface)

        box_w, box_h = 480, 158
        box = pygame.Rect(_CX - box_w // 2, SCREEN_HEIGHT // 2 - box_h // 2, box_w, box_h)
        pygame.draw.rect(surface, (24, 26, 44), box, border_radius=10)
        pygame.draw.rect(surface, COLOR_NEON_PINK, box, 2, border_radius=10)

        font = pygame.font.SysFont(None, _MODAL_FONT_SIZE)

        prompt = font.render("Enter profile name:", True, COLOR_WHITE)
        surface.blit(prompt, prompt.get_rect(center=(_CX, box.top + 38)))

        # Blinking cursor
        cursor_on = (pygame.time.get_ticks() // 500) % 2 == 0
        display = self._entry_name + ("|" if cursor_on else " ")
        name_surf = font.render(display if display.strip() else "|", True, COLOR_NEON_PINK)
        surface.blit(name_surf, name_surf.get_rect(center=(_CX, box.top + 90)))

        hint = self._hint_font.render(
            "ENTER to confirm  ·  ESC to cancel", True, COLOR_GRAY
        )
        surface.blit(hint, hint.get_rect(center=(_CX, box.top + 132)))

    def _draw_delete_confirm_modal(self, surface: pygame.Surface) -> None:
        self._draw_modal_overlay(surface)

        box_w, box_h = 520, 148
        box = pygame.Rect(_CX - box_w // 2, SCREEN_HEIGHT // 2 - box_h // 2, box_w, box_h)
        pygame.draw.rect(surface, (40, 18, 18), box, border_radius=10)
        pygame.draw.rect(surface, COLOR_RED, box, 2, border_radius=10)

        font = pygame.font.SysFont(None, _MODAL_FONT_SIZE)

        meta = self._index.get("profiles", {}).get(str(self._delete_slot), {})
        name = meta.get("name", f"Player {self._delete_slot + 1}")
        warn = font.render(f"Delete '{name}'?  Cannot be undone.", True, COLOR_WHITE)
        surface.blit(warn, warn.get_rect(center=(_CX, box.top + 46)))

        hint = self._hint_font.render(
            "Y / ENTER to confirm  ·  N / ESC to cancel", True, COLOR_GRAY
        )
        surface.blit(hint, hint.get_rect(center=(_CX, box.top + 100)))

    @staticmethod
    def _draw_modal_overlay(surface: pygame.Surface) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        surface.blit(overlay, (0, 0))
