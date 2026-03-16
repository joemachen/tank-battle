"""
game/ui/components.py

Reusable UI components shared across scenes.

Components:
  ScrollingGrid   — Perspective outrun/synthwave grid for the main menu background.
  FadeTransition  — Brief fade-to-black overlay wired to a completion callback.

Design rules:
  - No scene-specific logic here — components know nothing about scenes or routing.
  - Each component owns its own state and exposes update(dt) / draw(surface).
  - FadeTransition fires its callback exactly once, then goes silent.
"""

import pygame

from game.utils.constants import (
    COLOR_BLUE,
    MENU_FADE_DURATION,
    MENU_GRID_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


# ---------------------------------------------------------------------------
# ScrollingGrid
# ---------------------------------------------------------------------------

class ScrollingGrid:
    """
    Animated perspective grid — classic outrun/synthwave visual.

    Geometry:
      - Horizon sits at HORIZON_FRAC of the screen height.
      - Horizontal lines fill the space below the horizon and appear to
        recede toward it via a power-curve perspective mapping.
      - Vertical lines radiate from the vanishing point (screen centre at
        the horizon) to evenly-spaced points along the bottom edge.
      - Lines are brightest near the viewer (bottom) and fade toward the
        horizon, creating depth without alpha surfaces.

    Animation:
      - _phase (0–1) advances each frame based on MENU_GRID_SPEED.
      - When phase wraps, a new line appears at the horizon seamlessly.
    """

    # Tunable geometry
    _HORIZON_FRAC: float = 0.44     # horizon as fraction of screen height
    _N_H: int = 14                  # number of horizontal lines in flight
    _N_V: int = 9                   # vertical lines per side (total 2*N_V+1)
    _EXPONENT: float = 1.9          # perspective depth curve — higher = more compression

    def __init__(self) -> None:
        self._phase: float = 0.0

    def update(self, dt: float) -> None:
        # Speed expressed as apparent px/s at the bottom; converted to phase/s.
        # grid_h ≈ 0.56 * SCREEN_HEIGHT.  One phase cycle = one line slot.
        grid_h = SCREEN_HEIGHT * (1.0 - self._HORIZON_FRAC)
        self._phase = (self._phase + dt * MENU_GRID_SPEED / grid_h) % 1.0

    def draw(self, surface: pygame.Surface) -> None:
        sw, sh = surface.get_size()
        cx = sw // 2
        hy = int(sh * self._HORIZON_FRAC)   # horizon y in pixels
        grid_h = sh - hy                     # pixel height of grid area

        # -- Horizontal lines --
        # raw_t in (0, 1]: 0 = at horizon, 1 = at bottom viewer edge
        # t = raw_t ** _EXPONENT compresses lines toward the horizon
        for i in range(self._N_H + 1):
            raw_t = (i + self._phase) / self._N_H
            if raw_t <= 0.0 or raw_t > 1.0:
                continue
            t = raw_t ** self._EXPONENT
            y = int(hy + grid_h * t)
            if y > sh:
                continue
            # Depth gradient: dim at horizon, brighter near viewer
            bright = 0.08 + 0.42 * raw_t   # 8% → 50% of full COLOR_BLUE
            r = int(COLOR_BLUE[0] * bright)
            g = int(COLOR_BLUE[1] * bright)
            b = int(COLOR_BLUE[2] * bright)
            pygame.draw.line(surface, (r, g, b), (0, y), (sw, y))

        # -- Vertical lines converging to vanishing point --
        v_frac = 0.06   # ~6% of full COLOR_BLUE — very subtle
        v_color = (
            int(COLOR_BLUE[0] * v_frac),
            int(COLOR_BLUE[1] * v_frac),
            int(COLOR_BLUE[2] * v_frac),
        )
        total_v = self._N_V * 2 + 1
        for i in range(total_v):
            bx = int(sw * i / (total_v - 1))
            pygame.draw.line(surface, v_color, (cx, hy), (bx, sh))


# ---------------------------------------------------------------------------
# FadeTransition
# ---------------------------------------------------------------------------

class FadeTransition:
    """
    Fades the screen to black over `duration` seconds, then fires a callback.

    Usage:
        fade = FadeTransition(duration=0.3, on_complete=lambda: manager.switch_to(…))
        fade.start()                  # in response to user action
        fade.update(dt)               # each frame
        fade.draw(surface)            # after scene draw — overlays black rect
        if fade.is_active: …          # block input while fading
    """

    def __init__(self, duration: float = MENU_FADE_DURATION, on_complete=None) -> None:
        self._duration: float = max(0.001, duration)
        self._on_complete = on_complete
        self._elapsed: float = 0.0
        self._active: bool = False
        self._fired: bool = False
        self._overlay: pygame.Surface | None = None

    def start(self) -> None:
        """Activate the fade from the beginning."""
        self._elapsed = 0.0
        self._active = True
        self._fired = False

    def reset(self, on_complete=None) -> None:
        """Reset and optionally replace the callback (for re-use across on_enter calls)."""
        self._elapsed = 0.0
        self._active = False
        self._fired = False
        if on_complete is not None:
            self._on_complete = on_complete

    def update(self, dt: float) -> None:
        if not self._active or self._fired:
            return
        self._elapsed = min(self._elapsed + dt, self._duration)
        if self._elapsed >= self._duration:
            self._fired = True
            self._active = False
            if self._on_complete:
                self._on_complete()

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the black overlay.  Call after the scene's own draw()."""
        if not self._active:
            return
        alpha = int(255 * min(1.0, self._elapsed / self._duration))
        if self._overlay is None or self._overlay.get_size() != surface.get_size():
            self._overlay = pygame.Surface(surface.get_size())
            self._overlay.fill((0, 0, 0))
        self._overlay.set_alpha(alpha)
        surface.blit(self._overlay, (0, 0))

    @property
    def is_active(self) -> bool:
        """True while the fade is in progress."""
        return self._active

    @property
    def is_complete(self) -> bool:
        """True after the fade finished and the callback fired."""
        return self._fired
