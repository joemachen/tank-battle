"""
game/scenes/game_over_scene.py

GameOverScene — full match result screen with XP progression.

Layout (top to bottom, centered):
  - VICTORY / DEFEATED header
  - Stat block: Kills, Accuracy, Damage dealt/taken, Time
  - XP earned (animated count-up over 1.5 s)
  - Level progress bar  [===>    ]  Level N  or  LEVEL UP! → Level N
  - Unlock notification (only when a new item unlocked this match)
  - Press ENTER / ESC to continue

Receives:
  result: MatchResult  — via on_enter() kwargs from GameplayScene

Applies progression (SaveManager + ProgressionManager) immediately on enter
so the UI can display updated level/unlocks from first frame.
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.systems.match_calculator import MatchResult
from game.systems.progression_manager import ProgressionManager
from game.ui.audio_manager import get_audio_manager
from game.systems.achievement_system import AchievementSystem
from game.utils.constants import (
    COLOR_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_WHITE,
    COLOR_YELLOW,
    MATCH_HISTORY_MAX_STORED,
    MUSIC_GAME_OVER,
    SCENE_MENU,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

_achievement_system = AchievementSystem()
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)

# --------------------------------------------------------------------------
# Layout / animation constants
# --------------------------------------------------------------------------
_XP_ANIM_DURATION: float = 1.5       # seconds for the XP count-up
_CX: int = SCREEN_WIDTH // 2         # horizontal centre of the screen

_HEADER_Y: int = 80
_STAT_TOP_Y: int = 170
_STAT_LINE_H: int = 30
_XP_Y: int = _STAT_TOP_Y + 5 * _STAT_LINE_H + 18
_BAR_Y: int = _XP_Y + 52
_UNLOCK_Y: int = _BAR_Y + 60
_HINT_Y: int = SCREEN_HEIGHT - 40

_BAR_W: int = 360
_BAR_H: int = 18
_BAR_BORDER: int = 2

_COLOR_VICTORY = (100, 220, 100)
_COLOR_DEFEAT = (220, 80, 80)
_COLOR_XP = COLOR_YELLOW
_COLOR_BAR_BG = (50, 50, 55)
_COLOR_BAR_FILL = COLOR_GREEN
_COLOR_LEVELUP = (255, 210, 60)
_COLOR_ACHIEVEMENT = (255, 200, 60)   # warm gold for toast


# ---------------------------------------------------------------------------
# Module-level helper — extracted for testability
# ---------------------------------------------------------------------------

def _append_history_entry(profile: dict, result: MatchResult) -> None:
    """Append a history record for *result* to *profile* (mutates in-place).

    Caps stored entries at MATCH_HISTORY_MAX_STORED, dropping the oldest.
    """
    entry = {
        "won":          result.won,
        "kills":        result.kills,
        "accuracy":     round(result.accuracy, 3),
        "damage_dealt": result.damage_dealt,
        "damage_taken": result.damage_taken,
        "time_elapsed": round(result.time_elapsed, 1),
        "xp_earned":    result.xp_earned,
        "level_after":  int(profile.get("level", 1)),
    }
    history = list(profile.get("match_history", []))
    history.append(entry)
    profile["match_history"] = history[-MATCH_HISTORY_MAX_STORED:]


class GameOverScene(BaseScene):
    """Match result and XP progression screen."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._result: MatchResult | None = None
        self._save_manager = SaveManager()
        self._progression = ProgressionManager()
        # Post-progression state
        self._old_level: int = 1
        self._new_level: int = 1
        self._old_xp: int = 0
        self._new_xp: int = 0
        self._new_unlocks: list[str] = []
        self._new_achievements: list[str] = []
        # XP count-up animation
        self._xp_timer: float = 0.0

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, result: MatchResult | None = None, **kwargs) -> None:
        # Legacy callers may still pass won/xp_earned kwargs; build a stub result.
        if result is None:
            from game.systems.match_calculator import MatchCalculator
            result = MatchCalculator.build(
                won=kwargs.get("won", False),
                survived=kwargs.get("won", False),
                kills=0,
                shots_fired=0,
                shots_hit=0,
                time_elapsed=0.0,
                damage_dealt=0,
                damage_taken=kwargs.get("damage_taken", 0),
            )
        self._result = result
        self._xp_timer = 0.0

        # Apply progression: update XP, level, unlocks, counters
        profile = self._save_manager.load_profile()
        self._old_level = int(profile.get("level", 1))
        self._old_xp = int(profile.get("xp", 0))

        new_profile, new_unlocks = self._progression.apply_match_result(profile, result)
        _append_history_entry(new_profile, result)
        self._save_manager.save_profile(new_profile)

        self._new_level = int(new_profile.get("level", 1))
        self._new_xp = int(new_profile.get("xp", 0))
        self._new_unlocks = new_unlocks

        new_profile, self._new_achievements = _achievement_system.apply_to_profile(new_profile)
        if self._new_achievements:
            self._save_manager.save_profile(new_profile)

        get_audio_manager().play_music(MUSIC_GAME_OVER, loop=False)
        log.info(
            "GameOverScene: won=%s  xp_earned=%d  level %d→%d  unlocks=%s",
            result.won, result.xp_earned, self._old_level, self._new_level, new_unlocks,
        )

    def on_exit(self) -> None:
        self._result = None

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.manager.switch_to(SCENE_MENU)

    # ------------------------------------------------------------------
    # Update — drives the XP count-up animation
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self._xp_timer < _XP_ANIM_DURATION:
            self._xp_timer = min(self._xp_timer + dt, _XP_ANIM_DURATION)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        if self._result is None:
            return

        r = self._result
        self._draw_header(surface, r.won)
        self._draw_stats(surface, r)
        self._draw_xp(surface, r.xp_earned)
        self._draw_level_bar(surface)
        if self._new_unlocks:
            self._draw_unlock(surface)
        if self._new_achievements:
            self._draw_achievements_toast(surface)
        self._draw_hint(surface)

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_header(self, surface: pygame.Surface, won: bool) -> None:
        font = pygame.font.SysFont(None, 80)
        text = "VICTORY!" if won else "DEFEATED"
        color = _COLOR_VICTORY if won else _COLOR_DEFEAT
        label = font.render(text, True, color)
        surface.blit(label, label.get_rect(center=(_CX, _HEADER_Y)))

    def _draw_stats(self, surface: pygame.Surface, r: MatchResult) -> None:
        label_font = pygame.font.SysFont(None, 32)
        value_font = pygame.font.SysFont(None, 32)
        minutes = int(r.time_elapsed) // 60
        seconds = int(r.time_elapsed) % 60
        rows = [
            ("Kills",         str(r.kills)),
            ("Accuracy",      f"{r.accuracy * 100:.0f}%"),
            ("Damage Dealt",  str(r.damage_dealt)),
            ("Damage Taken",  str(r.damage_taken)),
            ("Time",          f"{minutes}:{seconds:02d}"),
        ]
        col_gap = 20
        y = _STAT_TOP_Y
        for label, value in rows:
            lbl = label_font.render(label + ":", True, COLOR_GRAY)
            val = value_font.render(value, True, COLOR_WHITE)
            lbl_rect = lbl.get_rect(midright=(_CX - col_gap, y + lbl.get_height() // 2))
            val_rect = val.get_rect(midleft=(_CX + col_gap, y + val.get_height() // 2))
            surface.blit(lbl, lbl_rect)
            surface.blit(val, val_rect)
            y += _STAT_LINE_H

    def _draw_xp(self, surface: pygame.Surface, xp_earned: int) -> None:
        t = self._xp_timer / _XP_ANIM_DURATION if _XP_ANIM_DURATION > 0 else 1.0
        displayed = int(xp_earned * t)
        font = pygame.font.SysFont(None, 44)
        label = font.render(f"XP Earned:  +{displayed}", True, _COLOR_XP)
        surface.blit(label, label.get_rect(center=(_CX, _XP_Y)))

    def _draw_level_bar(self, surface: pygame.Surface) -> None:
        level_up = self._new_level > self._old_level

        header_font = pygame.font.SysFont(None, 30)
        if level_up:
            header_text = f"LEVEL UP!   Level {self._old_level}  →  Level {self._new_level}"
            header_color = _COLOR_LEVELUP
        else:
            header_text = f"Level {self._new_level}"
            header_color = COLOR_WHITE

        lbl = header_font.render(header_text, True, header_color)
        surface.blit(lbl, lbl.get_rect(center=(_CX, _BAR_Y - 20)))

        # Progress bar within current level XP bracket
        bar_x = _CX - _BAR_W // 2
        bar_rect = pygame.Rect(bar_x, _BAR_Y, _BAR_W, _BAR_H)
        pygame.draw.rect(surface, _COLOR_BAR_BG, bar_rect, border_radius=4)

        level_xp = self._progression.xp_for_level(self._new_level)
        next_xp = self._progression.next_level_xp(self._new_xp)
        if next_xp is not None:
            bracket = next_xp - level_xp
            progress = self._new_xp - level_xp
            ratio = max(0.0, min(1.0, progress / bracket)) if bracket > 0 else 0.0
        else:
            ratio = 1.0   # max level — fill bar

        fill_w = int(_BAR_W * ratio)
        if fill_w > 0:
            fill_rect = pygame.Rect(bar_x, _BAR_Y, fill_w, _BAR_H)
            pygame.draw.rect(surface, _COLOR_BAR_FILL, fill_rect, border_radius=4)
        pygame.draw.rect(surface, COLOR_GRAY, bar_rect, _BAR_BORDER, border_radius=4)

        # XP fraction beneath bar
        small = pygame.font.SysFont(None, 22)
        if next_xp is not None:
            xp_text = f"{self._new_xp} / {next_xp} XP"
        else:
            xp_text = f"{self._new_xp} XP  (MAX LEVEL)"
        xp_surf = small.render(xp_text, True, COLOR_GRAY)
        surface.blit(xp_surf, xp_surf.get_rect(center=(_CX, _BAR_Y + _BAR_H + 12)))

    def _draw_unlock(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 32)
        names = ",  ".join(uid.replace("_", " ").title() for uid in self._new_unlocks)
        label = font.render(f"UNLOCKED:  {names}", True, _COLOR_VICTORY)
        surface.blit(label, label.get_rect(center=(_CX, _UNLOCK_Y)))

    def _draw_achievements_toast(self, surface: pygame.Surface) -> None:
        name_font = pygame.font.SysFont(None, 24)
        desc_font = pygame.font.SysFont(None, 18)
        y = _UNLOCK_Y + 30 if self._new_unlocks else _UNLOCK_Y
        for aid in self._new_achievements:
            defn = _achievement_system.get_definition(aid)
            if defn is None:
                continue
            label = name_font.render(f"\u2605 Achievement Unlocked: {defn['name']}", True, _COLOR_ACHIEVEMENT)
            surface.blit(label, label.get_rect(center=(_CX, y)))
            desc = desc_font.render(defn["description"], True, (150, 150, 158))
            surface.blit(desc, desc.get_rect(center=(_CX, y + 20)))
            y += 52

    def _draw_hint(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont(None, 26)
        hint = font.render("Press ENTER or ESC to continue", True, COLOR_GRAY)
        surface.blit(hint, hint.get_rect(center=(_CX, _HINT_Y)))
