"""
game/scenes/settings_scene.py

Settings screen. Stub — full UI implemented in a later milestone.
"""

import pygame

from game.scenes.base_scene import BaseScene
from game.utils.constants import COLOR_BG, COLOR_WHITE, SCENE_MENU
from game.utils.logger import get_logger

log = get_logger(__name__)


class SettingsScene(BaseScene):
    """Displays configurable settings and persists changes via SaveManager."""

    def on_enter(self, **kwargs) -> None:
        log.info("Settings scene entered.")
        # TODO: load current settings from SaveManager on enter

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.manager.switch_to(SCENE_MENU)

    def update(self, dt: float) -> None:
        pass  # TODO: handle input for sliders, dropdowns, etc.

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        font = pygame.font.SysFont(None, 48)
        label = font.render("SETTINGS — stub (ESC = back)", True, COLOR_WHITE)
        surface.blit(label, label.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2)))
