"""
tests/test_tank_select.py

Unit tests for milestone v0.8: TankSelectScene.

Tests are designed to run without a pygame display (no rendering is called).
They exercise:
  - Stat normalisation helper
  - Locked / unlocked logic via can_select() and is_locked()
  - GameplayScene.on_enter() tank_type kwarg handling (medium_tank fallback)
"""

import os
import sys
import types

# ---------------------------------------------------------------------------
# Minimal pygame stub — prevents display initialisation in CI / headless runs.
# Must be installed before any game module is imported.
# ---------------------------------------------------------------------------
_pygame_stub = types.ModuleType("pygame")
_pygame_stub.SRCALPHA = 65536
_pygame_stub.KEYDOWN = 768
_pygame_stub.error = type("error", (Exception,), {})  # AudioManager uses pygame.error
# Navigation / confirm keys
_pygame_stub.K_LEFT = 276
_pygame_stub.K_RIGHT = 275
_pygame_stub.K_a = 97
_pygame_stub.K_d = 100
_pygame_stub.K_RETURN = 13
_pygame_stub.K_SPACE = 32
_pygame_stub.K_ESCAPE = 27
# Keys used by InputHandler at module level
_pygame_stub.K_w = 119
_pygame_stub.K_s = 115
_pygame_stub.K_UP = 273
_pygame_stub.K_DOWN = 274
_pygame_stub.K_LSHIFT = 304
_pygame_stub.K_RSHIFT = 303
# Additional keys used by ProfileSelectScene (v0.13.5)
_pygame_stub.K_DELETE = 127
_pygame_stub.K_F2 = 271
_pygame_stub.K_BACKSPACE = 8
_pygame_stub.K_y = 121
_pygame_stub.K_n = 110

# event stub
_event_mod = types.ModuleType("pygame.event")
class _FakeEventType: pass
_event_mod.Event = _FakeEventType
_pygame_stub.event = _event_mod

# font stub (used in draw paths — not exercised by these tests)
_font_mod = types.ModuleType("pygame.font")
_font_mod.SysFont = lambda *a, **kw: None
_font_mod.Font = lambda *a, **kw: None
_pygame_stub.font = _font_mod

# draw stub
_draw_mod = types.ModuleType("pygame.draw")
_draw_mod.rect = lambda *a, **kw: None
_draw_mod.circle = lambda *a, **kw: None
_pygame_stub.draw = _draw_mod

# Surface / Rect stubs
class _FakeSurface:
    def __init__(self, *a, **kw): pass
    def fill(self, *a, **kw): pass
    def blit(self, *a, **kw): pass
    def get_width(self): return 1280
    def get_height(self): return 720

class _FakeRect:
    def __init__(self, *a, **kw):
        args = a
        if len(args) == 4:
            self.x, self.y, self.width, self.height = args
        elif len(args) == 1 and hasattr(args[0], '__len__'):
            self.x, self.y, self.width, self.height = args[0]
        else:
            self.x = self.y = self.width = self.height = 0
        self.left = self.x
        self.top = self.y
        self.right = self.x + self.width
        self.bottom = self.y + self.height
        self.centerx = self.x + self.width // 2
        self.centery = self.y + self.height // 2
        self.center = (self.centerx, self.centery)
        self.topleft = (self.x, self.y)

_pygame_stub.Surface = _FakeSurface
_pygame_stub.Rect = _FakeRect

# mixer stub — AudioManager calls pygame.mixer.init / music / set_num_channels
_mixer_mod = types.ModuleType("pygame.mixer")
_mixer_mod.init = lambda *a, **kw: None
_mixer_mod.set_num_channels = lambda *a, **kw: None

class _FakeSound:
    def set_volume(self, v): pass
    def play(self): pass

_mixer_mod.Sound = lambda *a, **kw: _FakeSound()
_mixer_music_mod = types.ModuleType("pygame.mixer.music")
_mixer_music_mod.fadeout = lambda *a, **kw: None
_mixer_music_mod.load = lambda *a, **kw: None
_mixer_music_mod.set_volume = lambda *a, **kw: None
_mixer_music_mod.play = lambda *a, **kw: None
_mixer_mod.music = _mixer_music_mod
_pygame_stub.mixer = _mixer_mod

# Only install this stub if conftest.py hasn't already installed the comprehensive one.
# test_weapon_select.py uses the same guard.  Prevents overwriting the full stub
# (which includes transform, mouse, key.name, etc.) with this minimal version.
if "pygame" not in sys.modules:
    sys.modules["pygame"] = _pygame_stub
    sys.modules["pygame.font"] = _font_mod
    sys.modules["pygame.mixer"] = _mixer_mod

# ---------------------------------------------------------------------------
# Now safe to import game modules
# ---------------------------------------------------------------------------
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game.scenes.tank_select_scene import TankSelectScene, _normalise
from game.utils.constants import TANK_STAT_MAX


# ---------------------------------------------------------------------------
# Minimal SceneManager stub
# ---------------------------------------------------------------------------

class _FakeManager:
    def __init__(self):
        self.last_switch = None
        self.last_kwargs = {}

    def switch_to(self, key, **kwargs):
        self.last_switch = key
        self.last_kwargs = kwargs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scene(unlocked=("light_tank", "medium_tank")):
    """
    Return a TankSelectScene with on_enter() called.
    SaveManager is bypassed by monkeypatching load_profile.
    """
    scene = TankSelectScene(_FakeManager())
    # Patch SaveManager.load_profile so no real file I/O occurs
    scene._save_manager.load_profile = lambda: {
        "unlocked_tanks": list(unlocked)
    }
    scene.on_enter()
    return scene


# ---------------------------------------------------------------------------
# 1. Stat normalisation
# ---------------------------------------------------------------------------

class TestStatNormalisation:
    def test_scout_speed_is_one(self):
        """Scout tank speed (260) / max speed (260) should be exactly 1.0."""
        ratio = _normalise(260.0, "speed")
        assert ratio == pytest.approx(1.0)

    def test_heavy_health_is_one(self):
        """Heavy tank health (440) / max health (440) should be exactly 1.0."""
        ratio = _normalise(440.0, "health")
        assert ratio == pytest.approx(1.0)

    def test_light_tank_speed_ratio(self):
        """Light tank speed (200) / 260 ≈ 0.769."""
        ratio = _normalise(200.0, "speed")
        assert ratio == pytest.approx(200 / 260, rel=1e-4)

    def test_medium_tank_health_ratio(self):
        """Medium tank health (240) / 440 ≈ 0.545."""
        ratio = _normalise(240.0, "health")
        assert ratio == pytest.approx(240 / 440, rel=1e-4)

    def test_ratio_clamped_to_zero(self):
        """Values below zero clamp to 0.0."""
        assert _normalise(-5.0, "speed") == pytest.approx(0.0)

    def test_ratio_clamped_to_one(self):
        """Values above the max clamp to 1.0."""
        assert _normalise(9999.0, "health") == pytest.approx(1.0)

    def test_heavy_turn_rate_ratio(self):
        """Heavy tank turn_rate (80) / 220 ≈ 0.364."""
        ratio = _normalise(80.0, "turn_rate")
        assert ratio == pytest.approx(80 / 220, rel=1e-4)

    def test_light_fire_rate_ratio(self):
        """Light tank fire_rate (1.5) / 2.0 = 0.75."""
        ratio = _normalise(1.5, "fire_rate")
        assert ratio == pytest.approx(0.75, rel=1e-4)


# ---------------------------------------------------------------------------
# 2. Locked / unlocked logic
# ---------------------------------------------------------------------------

class TestLockedState:
    def test_medium_tank_is_unlocked_by_default(self):
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        assert scene.can_select("medium_tank") is True

    def test_heavy_tank_is_locked_by_default(self):
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        assert scene.can_select("heavy_tank") is False

    def test_scout_tank_is_locked_by_default(self):
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        assert scene.can_select("scout_tank") is False

    def test_locked_tank_cannot_be_selected(self):
        """Confirm on a locked tank must not switch scene."""
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        # Navigate cursor to heavy_tank (index 2)
        scene._tank_cursor = 2  # heavy_tank position in _TANK_ORDER
        scene._confirm_selection()
        # Manager should NOT have been called
        assert scene.manager.last_switch is None

    def test_unlocked_tank_confirms_correctly(self):
        """Confirm on an unlocked tank switches to SCENE_WEAPON_SELECT with correct kwarg."""
        from game.utils.constants import SCENE_WEAPON_SELECT
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        scene._tank_cursor = 1  # medium_tank
        scene._confirm_selection()
        assert scene.manager.last_switch == SCENE_WEAPON_SELECT
        assert scene.manager.last_kwargs.get("tank_type") == "medium_tank"

    def test_is_locked_returns_true_for_locked_tank(self):
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        assert scene.is_locked("heavy_tank") is True

    def test_is_locked_returns_false_for_unlocked_tank(self):
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        assert scene.is_locked("light_tank") is False

    def test_cursor_starts_on_first_unlocked(self):
        """Cursor should point to first unlocked tank after on_enter."""
        scene = _make_scene(unlocked=["light_tank", "medium_tank"])
        tank_type = scene._tank_data[scene._tank_cursor]["type"]
        assert tank_type in {"light_tank", "medium_tank"}


# ---------------------------------------------------------------------------
# 3. GameplayScene tank_type kwarg fallback
# ---------------------------------------------------------------------------

class TestGameplaySceneTankType:
    """
    Verify that GameplayScene.on_enter() honours the tank_type kwarg
    and falls back to TANK_DEFAULT_TYPE when it is absent.

    We test this by inspecting the tank's config type after on_enter() rather
    than using a mock library — the real config_loader reads tanks.yaml, and
    the real Tank is not constructed (we stub it via monkeypatch).
    """

    def _patch_scene(self, monkeypatch):
        """
        Patch all side-effectful helpers on game.scenes.game_scene so
        on_enter() can run without a display or pygame window.
        """
        import game.scenes.game_scene as gs

        # Track what tank_type was passed to get_tank_config
        self._called_with: list = []

        _orig_get_tank_config = gs.get_tank_config

        def _spy_get_tank_config(tank_type, path):
            self._called_with.append(tank_type)
            return {"type": tank_type, "speed": 150, "health": 120,
                    "turn_rate": 130, "fire_rate": 1.0}

        monkeypatch.setattr(gs, "get_tank_config", _spy_get_tank_config)
        monkeypatch.setattr(gs, "load_yaml",
                            lambda *a, **kw: {
                                "standard_shell": {"type": "standard_shell", "fire_rate": 1.0},
                                "spread_shot":    {"type": "spread_shot",    "fire_rate": 0.8},
                                "bouncing_round": {"type": "bouncing_round", "fire_rate": 0.6},
                                "homing_missile": {"type": "homing_missile", "fire_rate": 0.4},
                            })
        monkeypatch.setattr(gs, "get_ai_config",
                            lambda *a, **kw: {"reaction_time": 0.4,
                                              "accuracy": 0.72,
                                              "aggression": 0.6,
                                              "evasion_threshold": 0.40})
        from game.utils.theme_loader import load_theme
        monkeypatch.setattr(gs, "load_map", lambda *a, **kw: {
            "obstacles": [], "theme": load_theme("default"), "name": "Test Map",
            "pickup_spawns": [],
        })

        class _FakeTank:
            x = y = 0
            is_alive = True
            health_ratio = 1.0
            fire_rate = 1.0
            tank_type = "medium_tank"
            ultimate = None
            position = (0.0, 0.0)
            weapon_slots = [{"type": "standard_shell", "fire_rate": 1.0}]
            active_slot = 0
            def set_controller(self, c): pass
            def update(self, dt): pass
            def load_weapons(self, configs): pass

        class _FakeInput: pass

        class _FakeAI:
            low_hp_priority_weight = 0.5
            def set_owner(self, t): pass
            def set_obstacles_getter(self, g): pass
            def set_pickups_getter(self, g): pass
            def tick(self, dt): pass

        class _FakeCamera:
            def snap_to(self, *a, **kw): pass
            def update(self, *a, **kw): pass
            def world_to_screen(self, x, y): return (x, y)

        monkeypatch.setattr(gs, "Tank",          lambda **kw: _FakeTank())
        monkeypatch.setattr(gs, "InputHandler",  lambda **kw: _FakeInput())
        monkeypatch.setattr(gs, "AIController",  lambda **kw: _FakeAI())
        monkeypatch.setattr(gs, "CollisionSystem", lambda: object())
        monkeypatch.setattr(gs, "PhysicsSystem",   lambda: object())
        monkeypatch.setattr(gs, "Camera",          lambda *a, **kw: _FakeCamera())
        monkeypatch.setattr(gs, "HUD",             lambda *a, **kw: object())

        from game.scenes.game_scene import GameplayScene
        scene = GameplayScene.__new__(GameplayScene)
        scene.manager = _FakeManager()
        return scene

    def test_on_enter_uses_provided_tank_type(self, monkeypatch):
        """tank_type kwarg is forwarded to get_tank_config."""
        scene = self._patch_scene(monkeypatch)
        scene.on_enter(tank_type="heavy_tank")
        assert self._called_with[0] == "heavy_tank"

    def test_on_enter_falls_back_to_medium_tank(self, monkeypatch):
        """When no tank_type kwarg is given, TANK_DEFAULT_TYPE is used."""
        from game.utils.constants import TANK_DEFAULT_TYPE
        scene = self._patch_scene(monkeypatch)
        scene.on_enter()
        assert self._called_with[0] == TANK_DEFAULT_TYPE


# ---------------------------------------------------------------------------
# 4. Opponent-count kwarg
# ---------------------------------------------------------------------------

class TestTankSelectKwargs:
    """
    Verify that TankSelectScene passes ai_count to GameplayScene and that
    ai_difficulty is NOT forwarded (GameplayScene reads it from settings.json).
    """

    def _scene_with_selection(self, tank_cursor, opp_idx=None):
        """Return a scene primed with a specific cursor / opponent selection."""
        from game.scenes.tank_select_scene import TankSelectScene, _DEFAULT_OPPONENT_IDX
        scene = TankSelectScene(_FakeManager())
        scene._save_manager.load_profile = lambda: {
            "unlocked_tanks": ["light_tank", "medium_tank"]
        }
        scene.on_enter()
        scene._tank_cursor = tank_cursor
        if opp_idx is not None:
            scene._opponent_idx = opp_idx
        return scene

    def test_default_opponent_count_is_one(self):
        scene = self._scene_with_selection(tank_cursor=0)
        assert scene.selected_opponent_count == 1

    def test_opponent_count_kwarg_forwarded(self):
        """Opponent count 3 is passed to WeaponSelectScene."""
        from game.scenes.tank_select_scene import _OPPONENT_COUNTS
        from game.utils.constants import SCENE_WEAPON_SELECT
        scene = self._scene_with_selection(
            tank_cursor=1,  # medium_tank (unlocked)
            opp_idx=_OPPONENT_COUNTS.index(3),
        )
        scene._confirm_selection()
        assert scene.manager.last_switch == SCENE_WEAPON_SELECT
        assert scene.manager.last_kwargs.get("ai_count") == 3

    def test_ai_difficulty_not_in_kwargs(self):
        """ai_difficulty must NOT be forwarded — GameplayScene reads settings.json."""
        scene = self._scene_with_selection(tank_cursor=0)
        scene._confirm_selection()
        assert "ai_difficulty" not in scene.manager.last_kwargs

    def test_defaults_sent_when_unchanged(self):
        """Confirming without touching the selector sends 1 opponent."""
        from game.utils.constants import SCENE_GAME
        scene = self._scene_with_selection(tank_cursor=0)
        scene._confirm_selection()
        assert scene.manager.last_kwargs.get("ai_count") == 1
