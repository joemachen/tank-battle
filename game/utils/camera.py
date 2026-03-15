"""
game/utils/camera.py

Camera — manages the world-space to screen-space transform.

Coordinate systems
------------------
World space  : absolute 2D positions of all entities, origin at arena top-left.
               Range: (0, 0) → (ARENA_WIDTH, ARENA_HEIGHT)
Screen space : pixel coordinates on the display surface.
               Range: (0, 0) → (SCREEN_WIDTH, SCREEN_HEIGHT)

The camera tracks a target (the player tank) using smooth lerp so sudden
direction changes feel natural rather than snappy. It clamps to the arena
boundary so the viewport never shows empty space outside the arena.

Usage
-----
    cam = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, ARENA_WIDTH, ARENA_HEIGHT)

    # Each frame:
    cam.update(dt, player_tank.x, player_tank.y)

    # Convert any world position to screen position for rendering:
    sx, sy = cam.world_to_screen(entity.x, entity.y)
"""

from game.utils.constants import (
    ARENA_HEIGHT,
    ARENA_WIDTH,
    CAMERA_LERP_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from game.utils.math_utils import clamp, lerp
from game.utils.logger import get_logger

log = get_logger(__name__)


class Camera:
    """
    Smooth-following camera with arena-boundary clamping.

    The camera position (self._x, self._y) is the world-space coordinate
    of the viewport CENTER — not the top-left corner.
    """

    def __init__(
        self,
        viewport_w: int = SCREEN_WIDTH,
        viewport_h: int = SCREEN_HEIGHT,
        world_w: int = ARENA_WIDTH,
        world_h: int = ARENA_HEIGHT,
    ) -> None:
        self._vp_w: int = viewport_w
        self._vp_h: int = viewport_h
        self._world_w: int = world_w
        self._world_h: int = world_h

        # Camera starts centered on the arena
        self._x: float = world_w / 2.0
        self._y: float = world_h / 2.0
        self._clamp_position()

        log.debug(
            "Camera created. Viewport: %dx%d  World: %dx%d",
            viewport_w, viewport_h, world_w, world_h,
        )

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self, dt: float, target_x: float, target_y: float) -> None:
        """
        Lerp the camera center toward (target_x, target_y) and clamp to bounds.
        Call once per frame before any draw calls.
        """
        # t = 1 means instant snap; approaching 0 adds lag
        t = min(1.0, CAMERA_LERP_SPEED * dt)
        self._x = lerp(self._x, target_x, t)
        self._y = lerp(self._y, target_y, t)
        self._clamp_position()

    def snap_to(self, world_x: float, world_y: float) -> None:
        """Immediately jump the camera center to a world position (no lerp)."""
        self._x = world_x
        self._y = world_y
        self._clamp_position()

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------

    def world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
        """
        Convert a world-space position to screen-space pixel coordinates.

        Screen center corresponds to the camera's world position.
        Entities outside the viewport will have coordinates outside
        [0, viewport_w] × [0, viewport_h] — callers may cull these.
        """
        sx = world_x - self._x + self._vp_w * 0.5
        sy = world_y - self._y + self._vp_h * 0.5
        return (sx, sy)

    def screen_to_world(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        """
        Convert screen-space coordinates back to world space.
        Useful for mouse-aimed weapons and click-to-move in future.
        """
        wx = screen_x + self._x - self._vp_w * 0.5
        wy = screen_y + self._y - self._vp_h * 0.5
        return (wx, wy)

    def is_visible(self, world_x: float, world_y: float, margin: float = 64.0) -> bool:
        """
        Return True if a world position is within the viewport (plus a margin).
        Use for culling off-screen entities before drawing.
        """
        sx, sy = self.world_to_screen(world_x, world_y)
        return (
            -margin <= sx <= self._vp_w + margin
            and -margin <= sy <= self._vp_h + margin
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def x(self) -> float:
        """World-space X of the viewport center."""
        return self._x

    @property
    def y(self) -> float:
        """World-space Y of the viewport center."""
        return self._y

    @property
    def offset_x(self) -> float:
        """Screen-space X offset (top-left of viewport in world coords)."""
        return self._x - self._vp_w * 0.5

    @property
    def offset_y(self) -> float:
        """Screen-space Y offset (top-left of viewport in world coords)."""
        return self._y - self._vp_h * 0.5

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clamp_position(self) -> None:
        """Prevent the camera from showing outside the arena."""
        half_w = self._vp_w * 0.5
        half_h = self._vp_h * 0.5
        self._x = clamp(self._x, half_w, self._world_w - half_w)
        self._y = clamp(self._y, half_h, self._world_h - half_h)
