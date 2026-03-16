"""
game/scenes/weapon_select_scene.py

WeaponSelectScene — pre-match weapon selection screen.

Flow:
    TankSelectScene (ENTER) → WeaponSelectScene → (confirm) → GameplayScene
                                               → (ESC)     → TankSelectScene

Layout: 4 weapon cards, LEFT/RIGHT to navigate, ENTER/SPACE to confirm.
Locked weapons show "LOCKED" overlay and the level required to unlock them.
Each card animates a bullet dot across a track to convey bullet speed.

Controls:
    LEFT / RIGHT (or A / D) — navigate between weapon cards
    ENTER / SPACE           — confirm selection (ignored if weapon is locked)
    ESC                     — return to TankSelectScene (cursor preserved)
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
    MUSIC_MENU,
    SCENE_GAME,
    SCENE_TANK_SELECT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SFX_UI_CONFIRM,
    SFX_UI_NAVIGATE,
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
_CARD_W: int = 220
_CARD_H: int = 360
_CARD_GAP: int = 30
_CARD_TOP: int = 110
_CARD_RADIUS: int = 10
_SELECTED_BORDER_W: int = 3

_STAT_BAR_H: int = 10
_STAT_ROW_GAP: int = 22
_STATS: list = [
    ("Damage",    "damage"),
    ("Speed",     "speed"),
    ("Fire Rate", "fire_rate"),
    ("Range",     "max_range"),
]

# Weapon display order — left-to-right card layout
_WEAPON_ORDER: list = [
    "standard_shell",
    "spread_shot",
    "bouncing_round",
    "homing_missile",
]

# Animated bullet preview
_BULLET_RADIUS: int = 5
_BULLET_TRACK_Y_OFFSET: int = 64   # pixels below card top for the animation track


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
    """Pre-match weapon selection UI."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._save_manager: SaveManager = SaveManager()
        self._progression: ProgressionManager = ProgressionManager()
        self._weapon_data: list[dict] = []
        self._unlocked: set[str] = set()
        self._cursor: int = 0
        self._tank_type: str = "medium_tank"
        self._ai_count: int = 1
        self._player_level: int = 1
        self._unlock_levels: dict[str, int] = {}
        self._anim_t: float = 0.0   # global animation timer (seconds)

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        self._tank_type = kwargs.get("tank_type", "medium_tank")
        self._ai_count = int(kwargs.get("ai_count", 1))

        all_weapons = load_yaml(WEAPONS_CONFIG)
        self._weapon_data = []
        for w in _WEAPON_ORDER:
            cfg = all_weapons.get(w, {})
            cfg = dict(cfg)
            cfg.setdefault("type", w)
            self._weapon_data.append(cfg)

        profile = self._save_manager.load_profile()
        self._unlocked = set(profile.get("unlocked_weapons", ["standard_shell"]))
        self._player_level = int(profile.get("level", 1))

        # Build unlock-level lookup for locked card display
        self._unlock_levels = {}
        for wd in self._weapon_data:
            w = wd.get("type", "")
            lvl = self._progression.unlock_level_for(w)
            if lvl is not None:
                self._unlock_levels[w] = lvl

        # Cursor on first unlocked weapon
        self._cursor = 0
        for i, wd in enumerate(self._weapon_data):
            if wd["type"] in self._unlocked:
                self._cursor = i
                break

        self._anim_t = 0.0
        get_audio_manager().play_music(MUSIC_MENU)

        log.info(
            "WeaponSelectScene entered. Tank=%s  AI=%d  Unlocked: %s",
            self._tank_type, self._ai_count, sorted(self._unlocked),
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

        left = event.key in (pygame.K_LEFT, pygame.K_a)
        right = event.key in (pygame.K_RIGHT, pygame.K_d)
        if not (left or right):
            return

        delta = -1 if left else 1
        self._cursor = (self._cursor + delta) % len(self._weapon_data)
        get_audio_manager().play_sfx(SFX_UI_NAVIGATE)

    def _confirm_selection(self) -> None:
        selected = self._weapon_data[self._cursor]
        weapon_type = selected.get("type", "standard_shell")
        if weapon_type not in self._unlocked:
            log.debug(
                "WeaponSelectScene: '%s' is locked — ignoring confirm.", weapon_type
            )
            return
        log.info(
            "WeaponSelectScene: confirmed weapon=%s  tank=%s  opponents=%d",
            weapon_type, self._tank_type, self._ai_count,
        )
        get_audio_manager().play_sfx(SFX_UI_CONFIRM)
        self.manager.switch_to(
            SCENE_GAME,
            tank_type=self._tank_type,
            ai_count=self._ai_count,
            weapon_type=weapon_type,
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
        self._draw_cards(surface)
        self._draw_footer(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 52)
        heading = font.render("Select Your Weapon", True, COLOR_WHITE)
        surface.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 55)))

    def _draw_level_badge(self, surface: pygame.Surface) -> None:
        """Small 'Level N' label in the top-right corner."""
        font = pygame.font.SysFont(None, 28)
        label = font.render(f"Level {self._player_level}", True, COLOR_NEON_PINK)
        margin = 18
        surface.blit(label, (SCREEN_WIDTH - label.get_width() - margin, margin))

    def _draw_footer(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 26)
        hint = font.render(
            "◄ ►  Navigate     ENTER  Confirm     ESC  Back",
            True, COLOR_GRAY,
        )
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 26)))

    def _draw_cards(self, surface: pygame.Surface) -> None:
        n = len(self._weapon_data)
        total_w = n * _CARD_W + (n - 1) * _CARD_GAP
        start_x = (SCREEN_WIDTH - total_w) // 2

        for i, wd in enumerate(self._weapon_data):
            card_x = start_x + i * (_CARD_W + _CARD_GAP)
            card_rect = pygame.Rect(card_x, _CARD_TOP, _CARD_W, _CARD_H)
            is_selected = (i == self._cursor)
            weapon_type = wd.get("type", "")
            is_locked = weapon_type not in self._unlocked
            color = WEAPON_CARD_COLORS.get(weapon_type, COLOR_GRAY)

            self._draw_card(surface, card_rect, wd, color, is_selected, is_locked, i)

    def _draw_card(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        wd: dict,
        color: tuple,
        is_selected: bool,
        is_locked: bool,
        card_idx: int,
    ) -> None:
        # Card background
        bg_color = (50, 50, 55) if is_selected else (32, 32, 36)
        pygame.draw.rect(surface, bg_color, rect, border_radius=_CARD_RADIUS)

        # Selected border — neon-pink
        if is_selected:
            pygame.draw.rect(
                surface, COLOR_NEON_PINK, rect,
                width=_SELECTED_BORDER_W, border_radius=_CARD_RADIUS,
            )

        cx = rect.centerx
        y = rect.top + 18

        # Weapon name
        name_font = pygame.font.SysFont(None, 32)
        name_text = wd.get("type", "").replace("_", " ").title()
        name_color = COLOR_WHITE if not is_locked else COLOR_GRAY
        rendered_name = name_font.render(name_text, True, name_color)
        surface.blit(rendered_name, rendered_name.get_rect(center=(cx, y)))
        y += 36

        # Animated bullet preview (takes up ~36px vertical space)
        anim_color = color if not is_locked else COLOR_DARK_GRAY
        self._draw_bullet_preview(surface, rect, wd, anim_color, card_idx)
        y += 36

        # Description
        desc_font = pygame.font.SysFont(None, 22)
        desc = wd.get("description", "")
        self._draw_wrapped(surface, desc_font, desc, COLOR_GRAY, cx, y, _CARD_W - 24)
        y += 46

        # Stat bars
        stat_label_font = pygame.font.SysFont(None, 22)
        bar_left = rect.left + 16
        for label, key in _STATS:
            raw = float(wd.get(key, 0.0))
            ratio = _normalise_weapon(raw, key)
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
            unlock_lvl = self._unlock_levels.get(wd.get("type", ""))
            self._draw_locked_overlay(surface, rect, unlock_lvl)

    def _draw_bullet_preview(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        wd: dict,
        color: tuple,
        card_idx: int,
    ) -> None:
        """
        Animate a bullet dot crossing the card left-to-right.
        Speed scales with the weapon's speed stat normalised against WEAPON_STAT_MAX.
        Cards are phase-staggered so bullets don't all start at the same position.
        """
        track_y = rect.top + _BULLET_TRACK_Y_OFFSET
        track_left = rect.left + 16
        track_right = rect.right - 16
        track_w = track_right - track_left

        # Dim track line
        pygame.draw.line(
            surface, (50, 50, 55), (track_left, track_y), (track_right, track_y), 1
        )

        raw_speed = float(wd.get("speed", 200.0))
        speed_ratio = _normalise_weapon(raw_speed, "speed")
        # Animation cycles per second: faster weapons cycle 0.5–2.0 times per second
        anim_speed = 0.5 + speed_ratio * 1.5
        phase_offset = card_idx * 0.25   # stagger so bullets don't sync
        t = (self._anim_t * anim_speed + phase_offset) % 1.0

        bx = int(track_left + t * track_w)
        pygame.draw.circle(surface, color, (bx, track_y), _BULLET_RADIUS)

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
        if unlock_level is not None:
            surface.blit(
                lock_surf, lock_surf.get_rect(center=(rect.centerx, rect.centery - 14))
            )
            sub_font = pygame.font.SysFont(None, 24)
            sub_surf = sub_font.render(
                f"Unlocks at Level {unlock_level}", True, COLOR_GRAY
            )
            surface.blit(
                sub_surf, sub_surf.get_rect(center=(rect.centerx, rect.centery + 14))
            )
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

    def is_locked(self, weapon_type: str) -> bool:
        return weapon_type not in self._unlocked

    def can_select(self, weapon_type: str) -> bool:
        types = [wd.get("type") for wd in self._weapon_data]
        return weapon_type in types and weapon_type in self._unlocked
