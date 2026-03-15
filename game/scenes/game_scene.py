"""
game/scenes/game_scene.py

Gameplay scene. Stub — game entities and systems wired up in later milestones.
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.utils.constants import COLOR_BG, COLOR_WHITE, SCENE_MENU
from game.utils.logger import get_logger

log = get_logger(__name__)


class GameplayScene(BaseScene):
    """Main gameplay screen. Hosts entities, systems, and the HUD."""

    def on_enter(self, **kwargs) -> None:
        log.info("Gameplay scene entered.")
        # TODO: initialize entities and systems when game loop milestone begins

    def on_exit(self) -> None:
        log.info("Gameplay scene exited.")
        # TODO: teardown entities and systems

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.manager.switch_to(SCENE_MENU)

    def update(self, dt: float) -> None:
        pass  # TODO: update entities and systems with dt

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        font = pygame.font.SysFont(None, 36)
        label = font.render("GAMEPLAY — stub (ESC = menu)", True, COLOR_WHITE)
        surface.blit(label, label.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2)))
