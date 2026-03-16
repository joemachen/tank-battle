"""
game/engine.py

GameEngine — owns the main loop.

Responsibilities:
  - Initialize pygame and the display surface
  - Own the SceneManager
  - Run the event/update/draw loop with delta time
  - Shut down cleanly on exit or unhandled exception
"""

import traceback

import pygame

from game.scenes import SceneManager
from game.scenes.game_over_scene import GameOverScene
from game.scenes.game_scene import GameplayScene
from game.scenes.menu_scene import MainMenuScene
from game.scenes.profile_select_scene import ProfileSelectScene
from game.scenes.settings_scene import SettingsScene
from game.scenes.tank_select_scene import TankSelectScene
from game.scenes.weapon_select_scene import WeaponSelectScene
from game.utils.constants import (
    FPS,
    SCENE_GAME,
    SCENE_GAME_OVER,
    SCENE_MENU,
    SCENE_PROFILE_SELECT,
    SCENE_SETTINGS,
    SCENE_TANK_SELECT,
    SCENE_WEAPON_SELECT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TITLE,
)
from game.utils.logger import get_logger
from game.utils.save_manager import SaveManager

log = get_logger(__name__)


def resolve_start_scene(save: SaveManager) -> str:
    """
    Determine which scene to launch at startup.

    Returns SCENE_MENU when ALL of the following are true:
      1. settings["skip_profile_select"] is True
      2. At least one profile slot exists in the profiles index

    Otherwise returns SCENE_PROFILE_SELECT.
    Module-level so it can be imported and tested without pygame.
    """
    try:
        settings = save.load_settings()
        if settings.get("skip_profile_select", False):
            idx = save.load_profiles_index()
            if idx.get("profiles"):
                return SCENE_MENU
    except Exception:
        log.warning("resolve_start_scene: error reading save data — defaulting to profile select.")
    return SCENE_PROFILE_SELECT


class GameEngine:
    """
    The top-level game object. Instantiated once in main.py.

    Usage:
        engine = GameEngine()
        engine.run()
    """

    def __init__(self) -> None:
        pygame.init()
        self._screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self._clock = pygame.time.Clock()
        self._running: bool = False

        self._scene_manager = SceneManager()
        self._register_scenes()

        log.info("GameEngine initialized. Resolution: %dx%d @ %d FPS", SCREEN_WIDTH, SCREEN_HEIGHT, FPS)

    def _register_scenes(self) -> None:
        sm = self._scene_manager
        sm.register(SCENE_PROFILE_SELECT, ProfileSelectScene(sm))
        sm.register(SCENE_MENU, MainMenuScene(sm))
        sm.register(SCENE_TANK_SELECT, TankSelectScene(sm))
        sm.register(SCENE_WEAPON_SELECT, WeaponSelectScene(sm))
        sm.register(SCENE_GAME, GameplayScene(sm))
        sm.register(SCENE_SETTINGS, SettingsScene(sm))
        sm.register(SCENE_GAME_OVER, GameOverScene(sm))
        start = resolve_start_scene(SaveManager())
        sm.switch_to(start)
        log.info("All scenes registered. Starting at: '%s'", start)

    def run(self) -> None:
        """
        Main game loop. Runs until the window is closed or self._running is False.

        Delta time (dt) is in seconds. All movement/physics must use dt to
        guarantee frame-rate independence.
        """
        self._running = True
        log.info("Game loop started.")

        try:
            while self._running:
                dt = self._clock.tick(FPS) / 1000.0  # convert ms → seconds
                dt = min(dt, 0.05)  # cap at 50ms to prevent spiral-of-death on heavy frames

                # — Event handling —
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self._running = False
                        break
                    self._scene_manager.handle_event(event)

                # — Update —
                self._scene_manager.update(dt)

                # — Draw —
                self._scene_manager.draw(self._screen)
                pygame.display.flip()

        except Exception:
            log.critical("Unhandled exception in game loop:\n%s", traceback.format_exc())
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        log.info("Shutting down.")
        pygame.quit()
