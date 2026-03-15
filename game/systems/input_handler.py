"""
game/systems/input_handler.py

InputHandler — player controller. Reads pygame keyboard state and
produces a TankInput each frame.

The Tank class calls get_input() — it has no knowledge of whether the
controller is human or AI.
"""

import pygame

from game.entities.tank import TankInput
from game.utils.logger import get_logger

log = get_logger(__name__)

# Default key bindings — overridden at runtime from settings.json
_DEFAULT_KEYS: dict = {
    "move_forward": pygame.K_w,
    "move_backward": pygame.K_s,
    "rotate_left": pygame.K_a,
    "rotate_right": pygame.K_d,
    "fire": pygame.K_SPACE,
}


class InputHandler:
    """
    Reads keyboard state each frame and produces a TankInput.

    Instantiate once per human-controlled tank. Key bindings can be
    updated at runtime (e.g., after loading settings.json).
    """

    def __init__(self, keybinds: dict | None = None) -> None:
        self._keys = dict(_DEFAULT_KEYS)
        if keybinds:
            self._apply_keybinds(keybinds)
        log.debug("InputHandler initialized.")

    def get_input(self) -> TankInput:
        """Sample current keyboard state and return a TankInput."""
        keys = pygame.key.get_pressed()

        throttle = 0.0
        if keys[self._keys["move_forward"]]:
            throttle += 1.0
        if keys[self._keys["move_backward"]]:
            throttle -= 1.0

        rotate = 0.0
        if keys[self._keys["rotate_right"]]:
            rotate += 1.0
        if keys[self._keys["rotate_left"]]:
            rotate -= 1.0

        # Left mouse button is a permanent secondary fire binding (not user-configurable)
        fire = bool(keys[self._keys["fire"]]) or pygame.mouse.get_pressed()[0]

        return TankInput(throttle=throttle, rotate=rotate, fire=fire)

    def update_keybinds(self, keybinds: dict) -> None:
        """Apply new keybinds from settings at runtime."""
        self._apply_keybinds(keybinds)
        log.info("InputHandler keybinds updated.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_keybinds(self, keybinds: dict) -> None:
        key_map = {
            "move_forward": "move_forward",
            "move_backward": "move_backward",
            "rotate_left": "rotate_left",
            "rotate_right": "rotate_right",
            "fire": "fire",
        }
        for action, key_name in keybinds.items():
            if action in key_map:
                key_const = getattr(pygame, f"K_{key_name}", None)
                if key_const is not None:
                    self._keys[action] = key_const
                else:
                    log.warning("Unknown key name in keybinds: '%s'", key_name)
