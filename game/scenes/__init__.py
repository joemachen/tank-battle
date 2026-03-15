"""
game/scenes/__init__.py

SceneManager — central controller for all screen transitions.

Rules:
  - Scenes are registered by string key.
  - All transitions go through switch_to(). No direct scene-to-scene calls.
  - The active scene receives all events, updates, and draw calls.
"""

from typing import Any

import pygame

from game.utils.logger import get_logger

log = get_logger(__name__)


class SceneManager:
    """
    Manages all game scenes and routes events, updates, and draw calls
    to the currently active scene.
    """

    def __init__(self) -> None:
        self._scenes: dict = {}
        self._active_key: str | None = None
        self._active_scene = None

    def register(self, key: str, scene) -> None:
        """Register a scene instance under the given key."""
        self._scenes[key] = scene
        log.debug("Scene registered: '%s'", key)

    def switch_to(self, key: str, **kwargs: Any) -> None:
        """
        Deactivate the current scene and activate the one registered as key.
        Extra keyword arguments are forwarded to the new scene's on_enter().
        """
        if key not in self._scenes:
            log.error("Attempted to switch to unknown scene: '%s'", key)
            return

        if self._active_scene is not None:
            self._active_scene.on_exit()
            log.info("Scene exit: '%s'", self._active_key)

        self._active_key = key
        self._active_scene = self._scenes[key]
        self._active_scene.on_enter(**kwargs)
        log.info("Scene enter: '%s'", key)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._active_scene:
            self._active_scene.handle_event(event)

    def update(self, dt: float) -> None:
        if self._active_scene:
            self._active_scene.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if self._active_scene:
            self._active_scene.draw(surface)
