"""
tests/conftest.py

Shared pytest configuration.

Installs a headless pygame stub once before any test module is imported.
This prevents both:
  - "No module named pygame" errors in environments without pygame
  - Real pygame display initialisation in CI / headless runners

The stub is minimal but covers every symbol used across the test suite.
When pygame is already installed (e.g. developer machine with the venv
active), the guard skips installation so real pygame is used instead.
"""

import sys
import types


def _install_pygame_stub() -> None:
    """Build and register a comprehensive pygame stub in sys.modules."""

    stub = types.ModuleType("pygame")

    # ---------------------------------------------------------------------------
    # Constants
    # ---------------------------------------------------------------------------
    stub.SRCALPHA = 65536
    stub.KEYDOWN  = 768
    stub.NOFRAME  = 0

    # Error type — AudioManager catches pygame.error
    stub.error = type("error", (Exception,), {})

    # Lifecycle
    stub.init = lambda: (6, 0)
    stub.quit = lambda: None

    # Key constants (union of all keys used across the test suite)
    stub.K_RETURN   = 13
    stub.K_SPACE    = 32
    stub.K_ESCAPE   = 27
    stub.K_BACKSPACE = 8
    stub.K_DELETE   = 127
    stub.K_F2       = 271
    stub.K_y        = 121
    stub.K_n        = 110
    stub.K_LEFT     = 276
    stub.K_RIGHT    = 275
    stub.K_UP       = 273
    stub.K_DOWN     = 274
    stub.K_a        = 97
    stub.K_d        = 100
    stub.K_w        = 119
    stub.K_s        = 115
    stub.K_LSHIFT   = 304
    stub.K_RSHIFT   = 303
    stub.K_LCTRL    = 306
    stub.K_RCTRL    = 305
    stub.K_LALT     = 308
    stub.K_RALT     = 307
    stub.K_LMETA    = 310
    stub.K_RMETA    = 309
    stub.K_CAPSLOCK = 301
    stub.K_NUMLOCK  = 300

    # ---------------------------------------------------------------------------
    # Key sub-module
    # ---------------------------------------------------------------------------
    key_mod = types.ModuleType("pygame.key")

    _KEY_NAMES_MAP = {
        8: "backspace", 9: "tab", 13: "return", 27: "escape", 32: "space",
        273: "up", 274: "down", 275: "right", 276: "left",
        300: "numlock", 301: "caps lock", 303: "right shift", 304: "left shift",
        305: "right ctrl", 306: "left ctrl", 307: "right alt", 308: "left alt",
        309: "right meta", 310: "left meta",
    }

    def _key_name(k: int) -> str:
        if k in _KEY_NAMES_MAP:
            return _KEY_NAMES_MAP[k]
        # Printable ASCII (a-z, 0-9, punctuation)
        if 32 < k < 127:
            return chr(k)
        return f"key_{k}"

    key_mod.name = _key_name
    stub.key = key_mod

    # ---------------------------------------------------------------------------
    # Event sub-module
    # ---------------------------------------------------------------------------
    event_mod = types.ModuleType("pygame.event")

    class _Event:
        """Minimal pygame.event.Event replacement that accepts positional type + kwargs."""
        def __init__(self, etype=0, **kw):
            self.type = etype
            for k, v in kw.items():
                setattr(self, k, v)

    event_mod.Event = _Event
    stub.event = event_mod

    # ---------------------------------------------------------------------------
    # Font sub-module
    # ---------------------------------------------------------------------------
    font_mod = types.ModuleType("pygame.font")
    font_mod.SysFont = lambda *a, **kw: None
    font_mod.Font    = lambda *a, **kw: None
    stub.font = font_mod

    # ---------------------------------------------------------------------------
    # Draw sub-module
    # ---------------------------------------------------------------------------
    draw_mod = types.ModuleType("pygame.draw")
    draw_mod.rect   = lambda *a, **kw: None
    draw_mod.circle = lambda *a, **kw: None
    draw_mod.line   = lambda *a, **kw: None
    stub.draw = draw_mod

    # ---------------------------------------------------------------------------
    # Surface / Rect stubs
    # ---------------------------------------------------------------------------
    class _Surface:
        def __init__(self, *a, **kw):
            # Capture optional size tuple so get_width/get_height return sensible values
            if a and hasattr(a[0], '__len__') and len(a[0]) >= 2:
                self._w, self._h = int(a[0][0]), int(a[0][1])
            else:
                self._w, self._h = 1280, 720
        def fill(self, *a, **kw): pass
        def blit(self, *a, **kw): pass
        def get_width(self):  return self._w
        def get_height(self): return self._h
        def get_rect(self, **kwargs):
            """Return a _Rect for this surface, optionally repositioned to 'center'."""
            r = _Rect(0, 0, self._w, self._h)
            if 'center' in kwargs:
                cx, cy = kwargs['center']
                r.x = cx - self._w // 2
                r.y = cy - self._h // 2
            return r

    class _Rect:
        def __init__(self, *a, **kw):
            args = a
            if len(args) == 4:
                self.x, self.y, self.width, self.height = args
            elif len(args) == 1 and hasattr(args[0], "__len__"):
                self.x, self.y, self.width, self.height = args[0]
            else:
                self.x = self.y = self.width = self.height = 0
            self.left    = self.x
            self.top     = self.y
            self.right   = self.x + self.width
            self.bottom  = self.y + self.height
            self.centerx = self.x + self.width // 2
            self.centery = self.y + self.height // 2
            self.center  = (self.centerx, self.centery)
            self.topleft = (self.x, self.y)

    stub.Surface = _Surface
    stub.Rect    = _Rect

    # ---------------------------------------------------------------------------
    # Display sub-module
    # ---------------------------------------------------------------------------
    display_mod = types.ModuleType("pygame.display")
    display_mod.set_mode    = lambda *a, **kw: _Surface()
    display_mod.set_caption = lambda *a, **kw: None
    display_mod.flip        = lambda: None
    stub.display = display_mod

    # ---------------------------------------------------------------------------
    # Mixer sub-module
    # ---------------------------------------------------------------------------
    mixer_mod = types.ModuleType("pygame.mixer")
    mixer_mod.init             = lambda *a, **kw: None
    mixer_mod.set_num_channels = lambda *a, **kw: None

    class _Sound:
        def set_volume(self, v): pass
        def play(self): pass

    mixer_mod.Sound = lambda *a, **kw: _Sound()

    music_mod = types.ModuleType("pygame.mixer.music")
    music_mod.fadeout   = lambda *a, **kw: None
    music_mod.load      = lambda *a, **kw: None
    music_mod.set_volume = lambda *a, **kw: None
    music_mod.play      = lambda *a, **kw: None
    mixer_mod.music = music_mod
    stub.mixer = mixer_mod

    # ---------------------------------------------------------------------------
    # Transform sub-module (needed by draw_rotated_rect and _draw_tank)
    # ---------------------------------------------------------------------------
    transform_mod = types.ModuleType("pygame.transform")
    # Stub rotate: return the same surface unchanged (no actual rotation in tests)
    transform_mod.rotate = lambda surf, angle: surf
    stub.transform = transform_mod

    # ---------------------------------------------------------------------------
    # Mouse sub-module (needed by InputHandler and reticle rendering)
    # ---------------------------------------------------------------------------
    mouse_mod = types.ModuleType("pygame.mouse")
    mouse_mod.get_pos       = lambda: (0, 0)
    mouse_mod.get_pressed   = lambda: (False, False, False)
    mouse_mod.set_visible   = lambda v: None
    stub.mouse = mouse_mod

    # ---------------------------------------------------------------------------
    # Register everything
    # ---------------------------------------------------------------------------
    sys.modules["pygame"]             = stub
    sys.modules["pygame.event"]       = event_mod
    sys.modules["pygame.font"]        = font_mod
    sys.modules["pygame.draw"]        = draw_mod
    sys.modules["pygame.display"]     = display_mod
    sys.modules["pygame.key"]         = key_mod
    sys.modules["pygame.mixer"]       = mixer_mod
    sys.modules["pygame.mixer.music"] = music_mod
    sys.modules["pygame.transform"]   = transform_mod
    sys.modules["pygame.mouse"]       = mouse_mod


# Only install the stub when pygame is not available in this environment.
# On a developer machine with the venv active (pip install -r requirements.txt),
# real pygame is used and the stub is skipped.
if "pygame" not in sys.modules:
    try:
        import pygame  # noqa: F401 — real pygame present, nothing to do
    except ImportError:
        _install_pygame_stub()
