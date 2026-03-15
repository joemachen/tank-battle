"""
game/scenes/base_scene.py

Abstract base class that every Scene must implement.
SceneManager interacts with scenes exclusively through this interface.
"""

from abc import ABC, abstractmethod

import pygame


class BaseScene(ABC):
    """
    All game screens (menu, gameplay, settings, game over) extend this class.

    The SceneManager calls handle_event, update, and draw each frame.
    Scenes must never reference other scenes directly — all transitions
    are requested through the SceneManager.
    """

    def __init__(self, manager: "SceneManager") -> None:  # type: ignore[name-defined]
        self.manager = manager

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        """Process a single pygame event."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Update scene logic. dt is elapsed time in seconds since last frame."""

    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        """Render the scene onto the given surface."""

    def on_enter(self, **kwargs) -> None:
        """
        Called by SceneManager when this scene becomes active.
        Override to reset state or receive transition parameters.
        """

    def on_exit(self) -> None:
        """
        Called by SceneManager just before this scene is deactivated.
        Override to clean up resources.
        """
