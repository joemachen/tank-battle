"""
tests/test_weapon_select.py

Unit tests for milestone v0.14: WeaponSelectScene.

Tests run without a pygame display.  They exercise:
  - Stat normalisation helper (_normalise_weapon)
  - Locked / unlocked logic via can_select() and is_locked()
  - Kwarg forwarding to GameplayScene (weapon_type, tank_type, ai_count)
  - Locked weapon ignores confirm
  - weapons.yaml field validation (all 4 weapons have required fields)
  - Back-navigation passes from_weapon_select=True to TankSelectScene
  - TankSelectScene cursor preserved on from_weapon_select re-entry
"""

import os
import sys
import types

# ---------------------------------------------------------------------------
# Minimal pygame stub — identical strategy as test_tank_select.py.
# Must be installed before any game module is imported.
# test_tank_select.py installs the same stub at module level; because both
# files are collected in the same pytest session, the stub may already be
# present.  We guard with setdefault so we don't double-install.
# ---------------------------------------------------------------------------
if "pygame" not in sys.modules:
    _pygame_stub = types.ModuleType("pygame")
    _pygame_stub.SRCALPHA = 65536
    _pygame_stub.KEYDOWN = 768
    _pygame_stub.error = type("error", (Exception,), {})

    _pygame_stub.K_LEFT = 276
    _pygame_stub.K_RIGHT = 275
    _pygame_stub.K_a = 97
    _pygame_stub.K_d = 100
    _pygame_stub.K_RETURN = 13
    _pygame_stub.K_SPACE = 32
    _pygame_stub.K_ESCAPE = 27
    _pygame_stub.K_w = 119
    _pygame_stub.K_s = 115
    _pygame_stub.K_UP = 273
    _pygame_stub.K_DOWN = 274
    _pygame_stub.K_LSHIFT = 304
    _pygame_stub.K_RSHIFT = 303
    _pygame_stub.K_DELETE = 127
    _pygame_stub.K_F2 = 271
    _pygame_stub.K_BACKSPACE = 8
    _pygame_stub.K_y = 121
    _pygame_stub.K_n = 110

    _event_mod = types.ModuleType("pygame.event")
    class _FakeEventType: pass
    _event_mod.Event = _FakeEventType
    _pygame_stub.event = _event_mod

    _font_mod = types.ModuleType("pygame.font")
    _font_mod.SysFont = lambda *a, **kw: None
    _font_mod.Font = lambda *a, **kw: None
    _pygame_stub.font = _font_mod

    _draw_mod = types.ModuleType("pygame.draw")
    _draw_mod.rect = lambda *a, **kw: None
    _draw_mod.circle = lambda *a, **kw: None
    _draw_mod.line = lambda *a, **kw: None
    _pygame_stub.draw = _draw_mod

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
            elif len(args) == 1 and hasattr(args[0], "__len__"):
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

    sys.modules["pygame"] = _pygame_stub
    sys.modules["pygame.font"] = _font_mod
    sys.modules["pygame.mixer"] = _mixer_mod

# ---------------------------------------------------------------------------
# Now safe to import game modules
# ---------------------------------------------------------------------------
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game.scenes.weapon_select_scene import WeaponSelectScene, _normalise_weapon
from game.utils.config_loader import load_yaml
from game.utils.constants import (
    SCENE_GAME,
    SCENE_TANK_SELECT,
    SCENE_WEAPON_SELECT,
    WEAPON_STAT_MAX,
    WEAPONS_CONFIG,
)


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

_UNLOCKED_DEFAULT = ("standard_shell",)
_UNLOCKED_ALL = ("standard_shell", "spread_shot", "bouncing_round", "homing_missile")


def _make_scene(
    unlocked=_UNLOCKED_DEFAULT,
    tank_type="medium_tank",
    ai_count=1,
):
    """
    Return a WeaponSelectScene with on_enter() called.
    SaveManager is bypassed by monkeypatching load_profile.
    """
    scene = WeaponSelectScene(_FakeManager())
    scene._save_manager.load_profile = lambda: {
        "unlocked_weapons": list(unlocked),
        "level": 1,
    }
    scene.on_enter(tank_type=tank_type, ai_count=ai_count)
    return scene


# ---------------------------------------------------------------------------
# 1. Stat normalisation
# ---------------------------------------------------------------------------

class TestStatNormalisation:
    def test_standard_shell_speed_is_one(self):
        """standard_shell speed (420) / WEAPON_STAT_MAX speed (420) == 1.0."""
        ratio = _normalise_weapon(420.0, "speed")
        assert ratio == pytest.approx(1.0)

    def test_homing_missile_damage_is_one(self):
        """homing_missile damage (50) / WEAPON_STAT_MAX damage (50) == 1.0."""
        ratio = _normalise_weapon(50.0, "damage")
        assert ratio == pytest.approx(1.0)

    def test_bouncing_round_range_is_one(self):
        """bouncing_round max_range (2400) / WEAPON_STAT_MAX max_range (2400) == 1.0."""
        ratio = _normalise_weapon(2400.0, "max_range")
        assert ratio == pytest.approx(1.0)

    def test_spread_shot_speed_ratio(self):
        """spread_shot speed (380) / 420 ≈ 0.905."""
        ratio = _normalise_weapon(380.0, "speed")
        assert ratio == pytest.approx(380 / 420, rel=1e-4)

    def test_value_below_zero_clamps_to_zero(self):
        assert _normalise_weapon(-10.0, "damage") == pytest.approx(0.0)

    def test_value_above_max_clamps_to_one(self):
        assert _normalise_weapon(9999.0, "max_range") == pytest.approx(1.0)

    def test_unknown_stat_key_does_not_raise(self):
        """An unknown stat key should return 0.0 gracefully."""
        ratio = _normalise_weapon(100.0, "nonexistent_stat")
        assert ratio == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2. Lock / unlock logic
# ---------------------------------------------------------------------------

class TestLockUnlock:
    def test_standard_shell_unlocked_by_default(self):
        scene = _make_scene(unlocked=["standard_shell"])
        assert scene.can_select("standard_shell") is True

    def test_spread_shot_locked_by_default(self):
        scene = _make_scene(unlocked=["standard_shell"])
        assert scene.can_select("spread_shot") is False

    def test_bouncing_round_locked_by_default(self):
        scene = _make_scene(unlocked=["standard_shell"])
        assert scene.can_select("bouncing_round") is False

    def test_homing_missile_locked_by_default(self):
        scene = _make_scene(unlocked=["standard_shell"])
        assert scene.can_select("homing_missile") is False

    def test_is_locked_true_for_locked_weapon(self):
        scene = _make_scene(unlocked=["standard_shell"])
        assert scene.is_locked("homing_missile") is True

    def test_is_locked_false_for_unlocked_weapon(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        assert scene.is_locked("homing_missile") is False

    def test_cursor_starts_on_first_unlocked(self):
        scene = _make_scene(unlocked=["standard_shell"])
        weapon_type = scene._weapon_data[scene._cursor]["type"]
        assert weapon_type == "standard_shell"

    def test_cursor_skips_locked_to_first_unlocked(self):
        """With only spread_shot unlocked, cursor should start on spread_shot (idx 1)."""
        scene = _make_scene(unlocked=["spread_shot"])
        weapon_type = scene._weapon_data[scene._cursor]["type"]
        assert weapon_type == "spread_shot"


# ---------------------------------------------------------------------------
# 3. Kwarg forwarding to GameplayScene
# ---------------------------------------------------------------------------

class TestKwargForwarding:
    def test_confirm_switches_to_scene_game(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._cursor = 0  # standard_shell
        scene._confirm_selection()
        assert scene.manager.last_switch == SCENE_GAME

    def test_weapon_type_forwarded(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._cursor = 0  # standard_shell
        scene._confirm_selection()
        assert scene.manager.last_kwargs.get("weapon_type") == "standard_shell"

    def test_tank_type_forwarded(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL, tank_type="heavy_tank")
        scene._cursor = 0
        scene._confirm_selection()
        assert scene.manager.last_kwargs.get("tank_type") == "heavy_tank"

    def test_ai_count_forwarded(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL, ai_count=3)
        scene._cursor = 0
        scene._confirm_selection()
        assert scene.manager.last_kwargs.get("ai_count") == 3

    def test_all_three_kwargs_present(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL, tank_type="scout_tank", ai_count=2)
        scene._cursor = 3  # homing_missile
        scene._confirm_selection()
        kw = scene.manager.last_kwargs
        assert kw.get("weapon_type") == "homing_missile"
        assert kw.get("tank_type") == "scout_tank"
        assert kw.get("ai_count") == 2


# ---------------------------------------------------------------------------
# 4. Locked weapon ignores confirm
# ---------------------------------------------------------------------------

class TestLockedWeaponIgnoresConfirm:
    def test_locked_weapon_does_not_switch_scene(self):
        """Confirming a locked weapon must not call switch_to."""
        scene = _make_scene(unlocked=["standard_shell"])
        scene._cursor = 3  # homing_missile (locked)
        scene._confirm_selection()
        assert scene.manager.last_switch is None

    def test_locked_weapon_leaves_no_kwargs(self):
        scene = _make_scene(unlocked=["standard_shell"])
        scene._cursor = 1  # spread_shot (locked)
        scene._confirm_selection()
        assert scene.manager.last_kwargs == {}


# ---------------------------------------------------------------------------
# 5. weapons.yaml field validation
# ---------------------------------------------------------------------------

class TestWeaponYamlFields:
    """All 4 weapons in weapons.yaml must have the fields the scene depends on."""

    _REQUIRED = ("damage", "speed", "fire_rate", "max_range", "description", "type")
    _WEAPON_KEYS = ("standard_shell", "spread_shot", "bouncing_round", "homing_missile")

    def _load(self):
        return load_yaml(WEAPONS_CONFIG)

    def test_all_four_weapons_present(self):
        data = self._load()
        for key in self._WEAPON_KEYS:
            assert key in data, f"Missing weapon: {key}"

    def test_standard_shell_has_required_fields(self):
        data = self._load()
        for field in self._REQUIRED:
            if field == "type":
                continue  # type is set by the scene, not yaml
            assert field in data["standard_shell"], f"standard_shell missing: {field}"

    def test_spread_shot_has_required_fields(self):
        data = self._load()
        for field in self._REQUIRED:
            if field == "type":
                continue
            assert field in data["spread_shot"], f"spread_shot missing: {field}"

    def test_bouncing_round_has_required_fields(self):
        data = self._load()
        for field in self._REQUIRED:
            if field == "type":
                continue
            assert field in data["bouncing_round"], f"bouncing_round missing: {field}"

    def test_homing_missile_has_required_fields(self):
        data = self._load()
        for field in self._REQUIRED:
            if field == "type":
                continue
            assert field in data["homing_missile"], f"homing_missile missing: {field}"

    def test_max_range_values_are_positive(self):
        data = self._load()
        for key in self._WEAPON_KEYS:
            assert data[key]["max_range"] > 0, f"{key} max_range must be > 0"

    def test_fire_rate_values_are_positive(self):
        data = self._load()
        for key in self._WEAPON_KEYS:
            assert data[key]["fire_rate"] > 0, f"{key} fire_rate must be > 0"


# ---------------------------------------------------------------------------
# 6. Back-navigation
# ---------------------------------------------------------------------------

class TestBackNavigation:
    def test_esc_switches_to_tank_select(self):
        scene = _make_scene()
        import pygame
        event = type("Event", (), {
            "type": pygame.KEYDOWN,
            "key": pygame.K_ESCAPE,
        })()
        scene.handle_event(event)
        assert scene.manager.last_switch == SCENE_TANK_SELECT

    def test_esc_passes_from_weapon_select_flag(self):
        scene = _make_scene()
        import pygame
        event = type("Event", (), {
            "type": pygame.KEYDOWN,
            "key": pygame.K_ESCAPE,
        })()
        scene.handle_event(event)
        assert scene.manager.last_kwargs.get("from_weapon_select") is True


# ---------------------------------------------------------------------------
# 7. TankSelectScene cursor preservation
# ---------------------------------------------------------------------------

class TestTankSelectCursorPreservation:
    """
    Verify that TankSelectScene.on_enter() resets cursor on fresh entry
    but preserves it when returning from weapon select.
    """

    def _make_tank_scene(self, unlocked=("light_tank", "medium_tank")):
        from game.scenes.tank_select_scene import TankSelectScene
        scene = TankSelectScene(_FakeManager())
        scene._save_manager.load_profile = lambda: {
            "unlocked_tanks": list(unlocked),
        }
        return scene

    def test_fresh_entry_resets_cursor(self):
        """Without from_weapon_select, cursor is reset to first unlocked."""
        scene = self._make_tank_scene()
        scene.on_enter()
        initial_cursor = scene._tank_cursor
        # Force cursor to a different position
        scene._tank_cursor = 1
        scene.on_enter()   # fresh entry — should reset
        assert scene._tank_cursor == initial_cursor

    def test_from_weapon_select_preserves_cursor(self):
        """With from_weapon_select=True, cursor stays at its current value."""
        scene = self._make_tank_scene()
        scene.on_enter()
        scene._tank_cursor = 1   # user had moved to medium_tank
        scene.on_enter(from_weapon_select=True)
        assert scene._tank_cursor == 1

    def test_from_weapon_select_preserves_opponent_idx(self):
        """With from_weapon_select=True, opponent_idx is also preserved."""
        scene = self._make_tank_scene()
        scene.on_enter()
        scene._opponent_idx = 2   # user had selected 3 opponents
        scene.on_enter(from_weapon_select=True)
        assert scene._opponent_idx == 2
