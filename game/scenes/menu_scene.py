"""
game/scenes/menu_scene.py

Main menu screen. Stub — full UI implemented in a later milestone.
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.utils.constants import (
    COLOR_BG,
    COLOR_WHITE,
    SCENE_SETTINGS,
    SCENE_TANK_SELECT,
    TITLE,
)
from game.utils.logger import get_logger

log = get_logger(__name__)


class MainMenuScene(BaseScene):
    """Displays the main menu and routes to tank selection or settings."""

    def on_enter(self, **kwargs) -> None:
        log.info("Main menu entered.")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.manager.switch_to(SCENE_TANK_SELECT)
            elif event.key == pygame.K_s:
                self.manager.switch_to(SCENE_SETTINGS)

    def update(self, dt: float) -> None:
        pass  # No animated elements yet

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        font = pygame.font.SysFont(None, 72)
        title = font.render(TITLE, True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(surface.get_width() // 2, 200)))

        hint_font = pygame.font.SysFont(None, 32)
        hint = hint_font.render("Press ENTER to play  |  S for Settings", True, (150, 150, 150))
        surface.blit(hint, hint.get_rect(center=(surface.get_width() // 2, 400)))
