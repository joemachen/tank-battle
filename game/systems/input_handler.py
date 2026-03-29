"""
game/systems/input_handler.py

InputHandler — player controller. Reads pygame keyboard and mouse state and
produces a TankInput each frame.

Mouse aim (v0.15):
  The mouse controls where the player tank fires — not which direction the
  hull faces.  get_input() converts the screen-space mouse position to a
  world-space position using the Camera, then computes the angle from the
  tank's world position to that point.  This angle is returned as
  TankInput.turret_angle.

  The Camera dependency is intentional and correct: mouse-aimed gameplay
  fundamentally requires a screen→world coordinate transform.  Passing the
  camera and a position getter as constructor arguments keeps InputHandler
  decoupled from the Tank entity itself.

Weapon cycling (v0.16):
  TAB or E → cycle_weapon = +1 (next slot)
  Q        → cycle_weapon = -1 (previous slot)
  Edge-detected: only fires on the frame the key transitions from up to down,
  so holding a key doesn't spin through all slots every frame.
"""

import math

import pygame

from game.entities.tank import TankInput
from game.utils.logger import get_logger

log = get_logger(__name__)

# Default key bindings — overridden at runtime from settings.json
_DEFAULT_KEYS: dict = {
    "move_forward":    pygame.K_w,
    "move_backward":   pygame.K_s,
    "rotate_left":     pygame.K_a,
    "rotate_right":    pygame.K_d,
    "fire":            pygame.K_SPACE,
    "mute":            pygame.K_m,
    "cycle_next":      pygame.K_TAB,
    "cycle_prev":      pygame.K_q,
    "cycle_next_alt":  pygame.K_e,
    "ultimate":        pygame.K_f,
}


class InputHandler:
    """
    Reads keyboard and mouse state each frame and produces a TankInput.

    Args:
        keybinds:              Optional key binding overrides (from settings.json).
        camera:                Camera instance used to convert mouse screen position
                               to world position.  If None, turret_angle defaults
                               to 0.0 (useful in headless / test contexts).
        tank_position_getter:  Zero-arg callable returning (x, y) world position
                               of the player tank.  Used to compute turret angle
                               from tank center → mouse world position.
    """

    def __init__(
        self,
        keybinds: dict | None = None,
        camera=None,
        tank_position_getter=None,
    ) -> None:
        self._keys = dict(_DEFAULT_KEYS)
        if keybinds:
            self._apply_keybinds(keybinds)
        self._camera = camera
        self._position_getter = tank_position_getter

        # Edge-detection state for weapon cycle keys
        self._prev_cycle_next: bool = False
        self._prev_cycle_prev: bool = False
        self._prev_ult_key: bool = False

        log.debug("InputHandler initialized (camera=%s).", "yes" if camera else "no")

    def get_input(self) -> TankInput:
        """Sample current keyboard/mouse state and return a TankInput."""
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

        # Turret angle: mouse world position → angle from tank center
        turret_angle = self._compute_turret_angle()

        # Weapon cycling: edge-detect so one keypress = one slot advance
        next_held = (
            bool(keys[self._keys["cycle_next"]])
            or bool(keys[self._keys["cycle_next_alt"]])
        )
        prev_held = bool(keys[self._keys["cycle_prev"]])

        cycle = 0
        if next_held and not self._prev_cycle_next:
            cycle = 1
        elif prev_held and not self._prev_cycle_prev:
            cycle = -1

        self._prev_cycle_next = next_held
        self._prev_cycle_prev = prev_held

        # Ultimate activation — edge-detected F key (v0.28)
        ult_key = bool(keys[self._keys["ultimate"]])
        activate_ult = ult_key and not self._prev_ult_key
        self._prev_ult_key = ult_key

        return TankInput(
            throttle=throttle,
            rotate=rotate,
            fire=fire,
            turret_angle=turret_angle,
            cycle_weapon=cycle,
            activate_ultimate=activate_ult,
        )

    def update_keybinds(self, keybinds: dict) -> None:
        """Apply new keybinds from settings at runtime."""
        self._apply_keybinds(keybinds)
        log.info("InputHandler keybinds updated.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_turret_angle(self) -> float:
        """
        Convert mouse screen position to world position using the Camera,
        then return the angle (degrees) from the tank's world position toward
        that world point.

        Returns 0.0 if camera or position_getter are not set — allows the class
        to be used in headless test contexts without a display.
        """
        if self._camera is None or self._position_getter is None:
            return 0.0
        mx, my = pygame.mouse.get_pos()
        wx, wy = self._camera.screen_to_world(mx, my)
        tx, ty = self._position_getter()
        return math.degrees(math.atan2(wy - ty, wx - tx))

    def _apply_keybinds(self, keybinds: dict) -> None:
        key_map = {
            "move_forward":  "move_forward",
            "move_backward": "move_backward",
            "rotate_left":   "rotate_left",
            "rotate_right":  "rotate_right",
            "fire":          "fire",
            "mute":          "mute",
        }
        for action, key_name in keybinds.items():
            if action in key_map:
                key_const = getattr(pygame, f"K_{key_name}", None)
                if key_const is not None:
                    self._keys[action] = key_const
                else:
                    log.warning("Unknown key name in keybinds: '%s'", key_name)
