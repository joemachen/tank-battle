"""
game/scenes/game_over_scene.py

Game over screen. Stub — stats display and progression update implemented later.
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.ui.audio_manager import get_audio_manager
from game.utils.constants import COLOR_BG, COLOR_WHITE, MUSIC_GAME_OVER, SCENE_MENU
from game.utils.logger import get_logger

log = get_logger(__name__)


class GameOverScene(BaseScene):
    """
    Displayed when a match ends. Receives match result via on_enter kwargs.
    Expected kwargs: won (bool), score (int), xp_earned (int)
    """

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._won: bool = False
        self._score: int = 0
        self._xp_earned: int = 0

    def on_enter(self, won: bool = False, score: int = 0, xp_earned: int = 0, **kwargs) -> None:
        self._won = won
        self._score = score
        self._xp_earned = xp_earned
        get_audio_manager().play_music(MUSIC_GAME_OVER, loop=False)
        log.info("Game over. Won=%s, Score=%d, XP=%d", won, score, xp_earned)
        # TODO: trigger SaveManager to record result and update profile

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.manager.switch_to(SCENE_MENU)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        font = pygame.font.SysFont(None, 64)
        result_text = "VICTORY!" if self._won else "DEFEATED"
        label = font.render(result_text, True, COLOR_WHITE)
        surface.blit(label, label.get_rect(center=(surface.get_width() // 2, 220)))

        hint_font = pygame.font.SysFont(None, 32)
        hint = hint_font.render("Press ENTER or ESC to return to menu", True, (150, 150, 150))
        surface.blit(hint, hint.get_rect(center=(surface.get_width() // 2, 420)))
