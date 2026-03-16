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
    COLOR_GREEN,
    COLOR_NEON_PINK,
    MENU_FADE_DURATION,
    MENU_GRID_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SETTINGS_SLIDER_WIDTH,
    SETTINGS_STEP_VOLUME,
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


# ---------------------------------------------------------------------------
# Settings-screen components (shared layout constants)
# ---------------------------------------------------------------------------

# All setting components assume their draw() is called with the same x
# (the left edge of the label column).  Controls begin _CTRL_OFFSET_PX
# pixels to the right, giving a consistent two-column layout.
_CTRL_OFFSET_PX: int = 360   # label column width in pixels
_COMP_ROW_H: int = 30        # assumed row height — used for vertical centering
_BAR_H: int = 10             # slider track height

_COLOR_SEL: tuple = COLOR_NEON_PINK         # selected label / value
_COLOR_DIM: tuple = (153, 153, 153)         # unselected label
_COLOR_VAL: tuple = (210, 210, 210)         # unselected value (brighter than label)
_COLOR_ARROW_OFF: tuple = (70, 70, 75)      # dimmed < > arrows

# Module-level font cache — avoids repeated SysFont calls at draw time
_font_cache: dict = {}


def _get_font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        _font_cache[size] = pygame.font.SysFont(None, size)
    return _font_cache[size]


# ---------------------------------------------------------------------------
# SliderComponent
# ---------------------------------------------------------------------------

class SliderComponent:
    """
    Horizontal percentage slider.

    draw(surface, x, y, selected):
        Renders label at (x, y) and a filled bar + percentage at
        (x + _CTRL_OFFSET_PX, y), vertically centred within _COMP_ROW_H.

    LEFT / RIGHT:   decrement / increment value by SETTINGS_STEP_VOLUME.
    """

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        current_val: float,
        width: int = SETTINGS_SLIDER_WIDTH,
    ) -> None:
        self._label = label
        self._min = float(min_val)
        self._max = float(max_val)
        self._value = max(self._min, min(self._max, float(current_val)))
        self._width = width

    # -- Input --

    def handle_input(self, key: int) -> bool:
        """Adjust value on LEFT/RIGHT.  Returns True if value changed."""
        if key == pygame.K_LEFT:
            new = max(self._min, self._value - SETTINGS_STEP_VOLUME)
            if new != self._value:
                self._value = round(new, 10)
                return True
        elif key == pygame.K_RIGHT:
            new = min(self._max, self._value + SETTINGS_STEP_VOLUME)
            if new != self._value:
                self._value = round(new, 10)
                return True
        return False

    # -- Draw --

    def draw(self, surface: pygame.Surface, x: int, y: int, selected: bool) -> None:
        font = _get_font(24)
        lbl_color = _COLOR_SEL if selected else _COLOR_DIM
        val_color = _COLOR_SEL if selected else _COLOR_VAL

        ty = y + (_COMP_ROW_H - font.get_linesize()) // 2   # vertically centred

        # Label
        lbl = font.render(self._label, True, lbl_color)
        surface.blit(lbl, (x, ty))

        # Bar
        bx = x + _CTRL_OFFSET_PX
        bar_y = y + (_COMP_ROW_H - _BAR_H) // 2
        ratio = (
            (self._value - self._min) / (self._max - self._min)
            if self._max > self._min else 0.0
        )
        track = pygame.Rect(bx, bar_y, self._width, _BAR_H)
        pygame.draw.rect(surface, (45, 45, 50), track, border_radius=3)
        fill_w = int(self._width * ratio)
        if fill_w > 0:
            fill_color = _COLOR_SEL if selected else COLOR_GREEN
            pygame.draw.rect(surface, fill_color,
                             pygame.Rect(bx, bar_y, fill_w, _BAR_H), border_radius=3)
        pygame.draw.rect(surface, (70, 70, 75), track, 1, border_radius=3)

        # Percentage
        pct = font.render(f"{int(round(self._value * 100))}%", True, val_color)
        surface.blit(pct, (bx + self._width + 10, ty))

    # -- Property --

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = max(self._min, min(self._max, float(v)))


# ---------------------------------------------------------------------------
# CycleComponent
# ---------------------------------------------------------------------------

class CycleComponent:
    """
    Left/right cycling selector: < OPTION >.

    draw(surface, x, y, selected):
        Renders label at (x, y) and  < VALUE >  in the control column.

    LEFT / RIGHT:   cycle backward / forward through options list (wraps).
    """

    def __init__(self, label: str, options: list, current_index: int = 0) -> None:
        self._label = label
        self._options = list(options)
        self._index = max(0, min(len(self._options) - 1, current_index))

    # -- Input --

    def handle_input(self, key: int) -> bool:
        if key == pygame.K_LEFT:
            self._index = (self._index - 1) % len(self._options)
            return True
        elif key == pygame.K_RIGHT:
            self._index = (self._index + 1) % len(self._options)
            return True
        return False

    # -- Draw --

    def draw(self, surface: pygame.Surface, x: int, y: int, selected: bool) -> None:
        font = _get_font(24)
        lbl_color   = _COLOR_SEL if selected else _COLOR_DIM
        arrow_color = _COLOR_SEL if selected else _COLOR_ARROW_OFF
        val_color   = _COLOR_SEL if selected else _COLOR_VAL

        ty = y + (_COMP_ROW_H - font.get_linesize()) // 2

        # Label
        lbl = font.render(self._label, True, lbl_color)
        surface.blit(lbl, (x, ty))

        # < VALUE > — centred in a 180px control slot
        cx = x + _CTRL_OFFSET_PX
        slot_w = 180

        left_s  = font.render("<", True, arrow_color)
        right_s = font.render(">", True, arrow_color)
        val_s   = font.render(str(self._options[self._index]), True, val_color)

        surface.blit(left_s, (cx, ty))
        vx = cx + left_s.get_width() + 8 + (slot_w - val_s.get_width()) // 2
        surface.blit(val_s, (vx, ty))
        surface.blit(right_s, (cx + left_s.get_width() + 8 + slot_w + 4, ty))

    # -- Properties --

    @property
    def value(self) -> str:
        return str(self._options[self._index])

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, i: int) -> None:
        self._index = max(0, min(len(self._options) - 1, i))


# ---------------------------------------------------------------------------
# KeybindComponent
# ---------------------------------------------------------------------------

class KeybindComponent:
    """
    Interactive key-rebind row.

    Normal state : shows current key name (e.g. "W").
    Listening state : shows "Press any key…" after ENTER is pressed.
    ESC while listening : cancels without changing the bind.

    The parent scene is responsible for conflict checking.  After
    try_bind() returns a key name, call commit() to apply it, or do
    nothing to discard.
    """

    # Keys that cannot be used as binds (modifier-only presses)
    _IGNORE_KEYS: frozenset = frozenset((
        pygame.K_LSHIFT, pygame.K_RSHIFT,
        pygame.K_LCTRL,  pygame.K_RCTRL,
        pygame.K_LALT,   pygame.K_RALT,
        pygame.K_LMETA,  pygame.K_RMETA,
        pygame.K_CAPSLOCK, pygame.K_NUMLOCK,
    ))

    def __init__(self, label: str, action: str, current_key: str) -> None:
        self._label = label
        self._action = action
        self._key_name = current_key   # stored as pygame.key.name() string (lowercase)
        self._listening = False

    # -- Lifecycle --

    def activate_listen(self) -> None:
        self._listening = True

    def cancel_listen(self) -> None:
        self._listening = False

    def try_bind(self, key: int) -> str | None:
        """
        Called by the scene when a key is pressed while this component is
        listening.  Returns the proposed key-name string, or None if the
        key should be ignored (ESC, modifier-only).  Does NOT commit.
        """
        if key == pygame.K_ESCAPE:
            self._listening = False
            return None
        if key in self._IGNORE_KEYS:
            return None
        self._listening = False
        return pygame.key.name(key)

    def commit(self, key_name: str) -> None:
        """Apply an accepted key name (after conflict check passed)."""
        self._key_name = key_name

    # -- Draw --

    def draw(self, surface: pygame.Surface, x: int, y: int, selected: bool) -> None:
        font = _get_font(24)
        lbl_color = _COLOR_SEL if selected else _COLOR_DIM
        ty = y + (_COMP_ROW_H - font.get_linesize()) // 2

        # Label
        lbl = font.render(self._label, True, lbl_color)
        surface.blit(lbl, (x, ty))

        # Value or listening prompt
        cx = x + _CTRL_OFFSET_PX
        if self._listening:
            val_s = font.render("Press any key…", True, COLOR_NEON_PINK)
        else:
            display = self._key_name.upper() if len(self._key_name) == 1 else self._key_name.capitalize()
            val_color = _COLOR_SEL if selected else _COLOR_VAL
            val_s = font.render(display, True, val_color)
        surface.blit(val_s, (cx, ty))

    # -- Properties --

    @property
    def value(self) -> str:
        """Current key name as stored in settings (lowercase)."""
        return self._key_name

    @property
    def action(self) -> str:
        return self._action

    @property
    def is_listening(self) -> bool:
        return self._listening
