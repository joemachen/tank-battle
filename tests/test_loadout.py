"""
tests/test_loadout.py

Unit tests for LoadoutScene (v0.17.5).

Tests run headless — pygame is stubbed before any game module is imported.
SaveManager, load_yaml, load_map, and get_audio_manager are patched so no
real file I/O or display initialisation occurs.
"""

import os
import sys
import types

# ---------------------------------------------------------------------------
# pygame stub — must be installed before any game module is imported.
# ---------------------------------------------------------------------------

_pygame_stub = types.ModuleType("pygame")
_pygame_stub.SRCALPHA = 65536
_pygame_stub.KEYDOWN = 768
_pygame_stub.error = type("error", (Exception,), {})

# Navigation keys
_pygame_stub.K_UP = 273
_pygame_stub.K_DOWN = 274
_pygame_stub.K_LEFT = 276
_pygame_stub.K_RIGHT = 275
_pygame_stub.K_w = 119
_pygame_stub.K_s = 115
_pygame_stub.K_a = 97
_pygame_stub.K_d = 100
_pygame_stub.K_TAB = 9
_pygame_stub.K_RETURN = 13
_pygame_stub.K_SPACE = 32
_pygame_stub.K_ESCAPE = 27
_pygame_stub.K_LSHIFT = 304
_pygame_stub.K_RSHIFT = 303
_pygame_stub.K_DELETE = 127
_pygame_stub.K_F2 = 271
_pygame_stub.K_BACKSPACE = 8
_pygame_stub.K_y = 121
_pygame_stub.K_n = 110
_pygame_stub.KMOD_SHIFT = 1

_event_mod = types.ModuleType("pygame.event")
_event_mod.Event = type("Event", (), {})
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

if "pygame" not in sys.modules:
    sys.modules["pygame"] = _pygame_stub
    sys.modules["pygame.font"] = _font_mod
    sys.modules["pygame.mixer"] = _mixer_mod

# ---------------------------------------------------------------------------
# Now safe to import game modules
# ---------------------------------------------------------------------------

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import game.scenes.loadout_scene as ls_module
from game.scenes.loadout_scene import LoadoutScene, _norm_tank, _norm_weapon
from game.utils.constants import (
    LOADOUT_PANEL_HULL,
    LOADOUT_PANEL_MAP,
    LOADOUT_PANEL_WEAPONS,
    SCENE_GAME,
    SCENE_MENU,
    TANK_STAT_MAX,
    WEAPON_STAT_MAX,
)


# ---------------------------------------------------------------------------
# Stubs / fixtures
# ---------------------------------------------------------------------------


class _FakeManager:
    def __init__(self):
        self.last_switch = None
        self.last_kwargs = {}

    def switch_to(self, key, **kwargs):
        self.last_switch = key
        self.last_kwargs = kwargs


_FAKE_TANK_CONFIGS = {
    "light_tank": {
        "speed": 200.0, "health": 80.0, "turn_rate": 160.0, "fire_rate": 1.5,
        "default_weapons": ["standard_shell", None, None],
    },
    "medium_tank": {
        "speed": 150.0, "health": 120.0, "turn_rate": 120.0, "fire_rate": 1.0,
        "default_weapons": ["standard_shell", "spread_shot", None],
    },
    "heavy_tank": {
        "speed": 80.0, "health": 220.0, "turn_rate": 80.0, "fire_rate": 0.7,
        "default_weapons": ["standard_shell", None, None],
    },
    "scout_tank": {
        "speed": 260.0, "health": 60.0, "turn_rate": 220.0, "fire_rate": 2.0,
        "default_weapons": ["spread_shot", None, None],
    },
}

_FAKE_WEAPON_CONFIGS = {
    "standard_shell": {"damage": 25.0, "speed": 420.0, "fire_rate": 1.0, "max_range": 1400.0},
    "spread_shot":    {"damage": 15.0, "speed": 300.0, "fire_rate": 0.8, "max_range": 800.0},
    "bouncing_round": {"damage": 20.0, "speed": 350.0, "fire_rate": 0.6, "max_range": 2400.0},
    "homing_missile": {"damage": 50.0, "speed": 250.0, "fire_rate": 0.4, "max_range": 1800.0},
}


class _FakeObstacle:
    def __init__(self):
        self.x = 100; self.y = 100; self.width = 80; self.height = 60
        self.color = (80, 80, 50)


_FAKE_MAP_DATA = {
    "obstacles": [_FakeObstacle()],
    "theme": {
        "floor_color": [20, 30, 20],
        "border_color": [60, 80, 60],
        "obstacle_tint": [100, 100, 80],
        "name": "Default",
        "ambient_label": "Classic",
    },
    "name": "Headquarters",
    "pickup_spawns": [],
}


def _make_scene(
    monkeypatch,
    unlocked_tanks=("light_tank", "medium_tank"),
    unlocked_weapons=("standard_shell",),
    level=1,
    xp=0,
):
    """
    Build a LoadoutScene with on_enter() called.
    All I/O is patched away.
    """
    scene = LoadoutScene(_FakeManager())

    # Patch SaveManager.load_profile
    scene._save_manager.load_profile = lambda: {
        "unlocked_tanks": list(unlocked_tanks),
        "unlocked_weapons": list(unlocked_weapons),
        "level": level,
        "xp": xp,
    }

    # Patch load_yaml (tanks.yaml + weapons.yaml + xp_table)
    def _fake_load_yaml(path):
        if "tanks" in path:
            return _FAKE_TANK_CONFIGS
        if "weapons" in path:
            return _FAKE_WEAPON_CONFIGS
        return {}  # xp_table → empty dict

    monkeypatch.setattr(ls_module, "load_yaml", _fake_load_yaml)

    # Patch load_map
    monkeypatch.setattr(ls_module, "load_map", lambda *a, **kw: dict(_FAKE_MAP_DATA))

    # Patch _build_map_preview (returns a FakeSurface — avoids pygame.draw calls)
    monkeypatch.setattr(ls_module, "_build_map_preview", lambda *a, **kw: _FakeSurface())

    # Patch ProgressionManager.unlock_level_for
    scene._progression.unlock_level_for = lambda item: None

    # Patch audio
    monkeypatch.setattr(ls_module, "get_audio_manager", lambda: _FakeAudioManager())

    scene.on_enter()
    return scene


class _FakeAudioManager:
    def play_music(self, *a, **kw): pass
    def play_sfx(self, *a, **kw): pass


# ---------------------------------------------------------------------------
# 1. Stat normalisers
# ---------------------------------------------------------------------------


class TestStatNormalisers:
    def test_tank_speed_at_max(self):
        assert _norm_tank(260.0, "speed") == pytest.approx(1.0)

    def test_tank_speed_half(self):
        assert _norm_tank(130.0, "speed") == pytest.approx(130 / 260, rel=1e-4)

    def test_tank_stat_clamped_low(self):
        assert _norm_tank(-1.0, "speed") == pytest.approx(0.0)

    def test_tank_stat_clamped_high(self):
        assert _norm_tank(9999.0, "health") == pytest.approx(1.0)

    def test_weapon_damage_at_max(self):
        assert _norm_weapon(50.0, "damage") == pytest.approx(1.0)

    def test_weapon_speed_half(self):
        assert _norm_weapon(210.0, "speed") == pytest.approx(210 / 420, rel=1e-4)

    def test_weapon_unknown_key_returns_zero(self):
        assert _norm_weapon(100.0, "nonexistent_key") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2. Panel navigation: TAB
# ---------------------------------------------------------------------------


class TestPanelNavigation:
    def test_tab_cycles_hull_to_weapons(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        assert scene._panel == LOADOUT_PANEL_HULL
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_TAB, mod=0)
        scene.handle_event(ev)
        assert scene._panel == LOADOUT_PANEL_WEAPONS

    def test_tab_cycles_weapons_to_map(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_WEAPONS
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_TAB, mod=0)
        scene.handle_event(ev)
        assert scene._panel == LOADOUT_PANEL_MAP

    def test_tab_wraps_map_to_hull(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_MAP
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_TAB, mod=0)
        scene.handle_event(ev)
        assert scene._panel == LOADOUT_PANEL_HULL

    def test_shift_tab_cycles_backward(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_WEAPONS
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_TAB, mod=_pygame_stub.KMOD_SHIFT)
        scene.handle_event(ev)
        assert scene._panel == LOADOUT_PANEL_HULL

    def test_shift_tab_wraps_hull_to_map(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_HULL
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_TAB, mod=_pygame_stub.KMOD_SHIFT)
        scene.handle_event(ev)
        assert scene._panel == LOADOUT_PANEL_MAP

    def test_left_right_in_hull_do_nothing(self, monkeypatch):
        """LEFT/RIGHT in hull panel no longer switch panels."""
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_HULL
        tank_before = scene._tank_cursor
        ev_right = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_RIGHT)
        scene.handle_event(ev_right)
        assert scene._panel == LOADOUT_PANEL_HULL
        assert scene._tank_cursor == tank_before
        ev_left = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_LEFT)
        scene.handle_event(ev_left)
        assert scene._panel == LOADOUT_PANEL_HULL
        assert scene._tank_cursor == tank_before

    def test_left_right_in_map_do_nothing(self, monkeypatch):
        """LEFT/RIGHT in map panel no longer switch panels."""
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_MAP
        map_before = scene._map_cursor
        ev_right = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_RIGHT)
        scene.handle_event(ev_right)
        assert scene._panel == LOADOUT_PANEL_MAP
        assert scene._map_cursor == map_before
        ev_left = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_LEFT)
        scene.handle_event(ev_left)
        assert scene._panel == LOADOUT_PANEL_MAP
        assert scene._map_cursor == map_before

    def test_left_right_in_weapons_cycle_not_switch(self, monkeypatch):
        """In the weapons panel LEFT/RIGHT cycles weapons, not panels."""
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_WEAPONS
        ev_right = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_RIGHT)
        scene.handle_event(ev_right)
        assert scene._panel == LOADOUT_PANEL_WEAPONS
        ev_left = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_LEFT)
        scene.handle_event(ev_left)
        assert scene._panel == LOADOUT_PANEL_WEAPONS


# ---------------------------------------------------------------------------
# 3. Hull selection
# ---------------------------------------------------------------------------


class TestHullSelection:
    def test_default_tank_is_first_unlocked(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_tanks=["light_tank", "medium_tank"])
        # light_tank is index 0 in _TANK_ORDER
        assert scene._selected_tank == "light_tank"

    def test_down_advances_to_next_unlocked_tank(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_tanks=["light_tank", "medium_tank"])
        scene._panel = LOADOUT_PANEL_HULL
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev)
        assert scene._selected_tank == "medium_tank"

    def test_up_wraps_to_last_unlocked(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_tanks=["light_tank", "medium_tank"])
        scene._panel = LOADOUT_PANEL_HULL
        # cursor starts at light_tank, UP should wrap to medium_tank (last unlocked)
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_UP)
        scene.handle_event(ev)
        assert scene._selected_tank == "medium_tank"

    def test_locked_tank_is_reported_as_locked(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_tanks=["light_tank", "medium_tank"])
        assert scene.is_tank_locked("heavy_tank") is True
        assert scene.is_tank_locked("scout_tank") is True

    def test_unlocked_tank_is_not_locked(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_tanks=["light_tank", "medium_tank"])
        assert scene.is_tank_locked("light_tank") is False

    def test_hull_nav_skips_locked_tanks(self, monkeypatch):
        """DOWN from light_tank with heavy+scout locked should go straight to medium_tank."""
        scene = _make_scene(monkeypatch, unlocked_tanks=["light_tank", "medium_tank"])
        scene._panel = LOADOUT_PANEL_HULL
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev)
        # Should land on medium_tank, not heavy_tank (which is locked)
        assert scene._selected_tank == "medium_tank"

    def test_all_tanks_unlocked_cycles_through_all_four(self, monkeypatch):
        all_tanks = ["light_tank", "medium_tank", "heavy_tank", "scout_tank"]
        scene = _make_scene(monkeypatch, unlocked_tanks=all_tanks)
        scene._panel = LOADOUT_PANEL_HULL
        ev_down = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        seen = {scene._selected_tank}
        for _ in range(4):
            scene.handle_event(ev_down)
            seen.add(scene._selected_tank)
        assert seen == set(all_tanks)


# ---------------------------------------------------------------------------
# 4. Weapon slots
# ---------------------------------------------------------------------------


class TestWeaponSlots:
    def test_slot_0_is_never_none_after_enter(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_weapons=["standard_shell"])
        assert scene._slot_selections[0] is not None

    def test_slot_0_defaults_to_standard_shell(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_weapons=["standard_shell"])
        assert scene._slot_selections[0] == "standard_shell"

    def test_slot_1_can_be_none(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_weapons=["standard_shell"])
        # With only one weapon, slots 1 and 2 should be None
        assert scene._slot_selections[1] is None
        assert scene._slot_selections[2] is None

    def test_locked_weapon_not_in_slot(self, monkeypatch):
        scene = _make_scene(
            monkeypatch,
            unlocked_tanks=["medium_tank"],
            unlocked_weapons=["standard_shell"],
        )
        # medium_tank default_weapons includes spread_shot, but it's locked
        assert scene._slot_selections[1] is None

    def test_cycle_slot0_right_advances_weapon(self, monkeypatch):
        scene = _make_scene(
            monkeypatch,
            unlocked_weapons=["standard_shell", "spread_shot"],
        )
        scene._panel = LOADOUT_PANEL_WEAPONS
        scene._slot_focus = 0
        initial = scene._slot_selections[0]
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_RIGHT)
        scene.handle_event(ev)
        assert scene._slot_selections[0] != initial

    def test_cycle_slot0_cannot_be_set_to_none(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_weapons=["standard_shell"])
        scene._panel = LOADOUT_PANEL_WEAPONS
        scene._slot_focus = 0
        # Cycle many times — slot 0 must never become None
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_RIGHT)
        for _ in range(10):
            scene.handle_event(ev)
            assert scene._slot_selections[0] is not None

    def test_slot_focus_moves_down(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_WEAPONS
        scene._slot_focus = 0
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev)
        assert scene._slot_focus == 1

    def test_slot_focus_wraps_at_bottom(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_WEAPONS
        scene._slot_focus = 2
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev)
        assert scene._slot_focus == 0

    def test_same_weapon_not_in_two_slots(self, monkeypatch):
        """Cycling should never place the same weapon in two slots simultaneously."""
        scene = _make_scene(
            monkeypatch,
            unlocked_weapons=["standard_shell", "spread_shot"],
        )
        scene._panel = LOADOUT_PANEL_WEAPONS
        # Cycle slot 1 until it's not None
        scene._slot_focus = 1
        ev_right = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_RIGHT)
        for _ in range(4):
            scene.handle_event(ev_right)
        filled = [w for w in scene._slot_selections if w is not None]
        assert len(filled) == len(set(filled)), "Duplicate weapon in slots"


# ---------------------------------------------------------------------------
# 5. Map selection
# ---------------------------------------------------------------------------


class TestMapSelection:
    def test_default_map_cursor_is_zero(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        assert scene._map_cursor == 0

    def test_down_advances_map_cursor(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_MAP
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev)
        assert scene._map_cursor == 1

    def test_map_cursor_wraps_at_end(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_MAP
        scene._map_cursor = 2  # last map (map_03)
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev)
        assert scene._map_cursor == 0

    def test_up_wraps_from_zero_to_last(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._panel = LOADOUT_PANEL_MAP
        scene._map_cursor = 0
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_UP)
        scene.handle_event(ev)
        assert scene._map_cursor == 2  # len(_MAP_NAMES) - 1


# ---------------------------------------------------------------------------
# 6. Hull change updates weapon defaults
# ---------------------------------------------------------------------------


class TestHullChangeUpdatesWeapons:
    def test_changing_tank_reloads_weapon_defaults(self, monkeypatch):
        """
        light_tank defaults to [standard_shell, None, None].
        medium_tank defaults to [standard_shell, spread_shot, None].
        After navigating to medium_tank, slot 1 should pick up spread_shot
        if it's unlocked.
        """
        scene = _make_scene(
            monkeypatch,
            unlocked_tanks=["light_tank", "medium_tank"],
            unlocked_weapons=["standard_shell", "spread_shot"],
        )
        # Start at light_tank — slot 1 should be None (light_tank has no slot1 default)
        assert scene._selected_tank == "light_tank"
        # Move DOWN to medium_tank
        scene._panel = LOADOUT_PANEL_HULL
        ev_down = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev_down)
        assert scene._selected_tank == "medium_tank"
        # medium_tank default_weapons = ["standard_shell", "spread_shot", None]
        assert scene._slot_selections[1] == "spread_shot"

    def test_defaults_filtered_to_unlocked(self, monkeypatch):
        """medium_tank wants spread_shot in slot 1, but it's locked → slot 1 stays None."""
        scene = _make_scene(
            monkeypatch,
            unlocked_tanks=["light_tank", "medium_tank"],
            unlocked_weapons=["standard_shell"],  # spread_shot NOT unlocked
        )
        scene._panel = LOADOUT_PANEL_HULL
        ev_down = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_DOWN)
        scene.handle_event(ev_down)
        assert scene._selected_tank == "medium_tank"
        assert scene._slot_selections[1] is None


# ---------------------------------------------------------------------------
# 7. Confirm kwargs
# ---------------------------------------------------------------------------


class TestConfirmKwargs:
    def test_confirm_sends_correct_tank_type(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_tanks=["light_tank", "medium_tank"])
        scene._confirm()
        assert scene.manager.last_kwargs["tank_type"] == "light_tank"

    def test_confirm_sends_weapon_types_list(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_weapons=["standard_shell"])
        scene._confirm()
        wt = scene.manager.last_kwargs["weapon_types"]
        assert isinstance(wt, list)
        assert "standard_shell" in wt

    def test_confirm_excludes_none_slots(self, monkeypatch):
        scene = _make_scene(monkeypatch, unlocked_weapons=["standard_shell"])
        # Slots 1 and 2 are None — weapon_types must not contain None
        scene._confirm()
        assert None not in scene.manager.last_kwargs["weapon_types"]

    def test_confirm_sends_correct_map_name(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._map_cursor = 1  # map_02
        scene._confirm()
        assert scene.manager.last_kwargs["map_name"] == "map_02"

    def test_confirm_switches_to_scene_game(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._confirm()
        assert scene.manager.last_switch == SCENE_GAME

    def test_confirm_blocked_when_slot0_empty(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        scene._slot_selections[0] = None  # force invalid state
        scene._confirm()
        # Should NOT switch scene
        assert scene.manager.last_switch is None


# ---------------------------------------------------------------------------
# 8. Defaults on enter
# ---------------------------------------------------------------------------


class TestDefaultsOnEnter:
    def test_default_panel_is_hull(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        assert scene._panel == LOADOUT_PANEL_HULL

    def test_default_map_is_map_01(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        from game.scenes.loadout_scene import _MAP_NAMES
        assert _MAP_NAMES[scene._map_cursor] == "map_01"

    def test_default_slot_focus_is_zero(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        assert scene._slot_focus == 0

    def test_default_tank_is_first_unlocked_in_order(self, monkeypatch):
        # medium_tank before light_tank → but _TANK_ORDER is [light, medium, heavy, scout]
        # light_tank unlocked → should be first
        scene = _make_scene(monkeypatch, unlocked_tanks=["medium_tank", "heavy_tank"])
        assert scene._selected_tank == "medium_tank"


# ---------------------------------------------------------------------------
# 9. ESC navigation
# ---------------------------------------------------------------------------


class TestEscapeNavigation:
    def test_esc_switches_to_menu(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_ESCAPE)
        scene.handle_event(ev)
        assert scene.manager.last_switch == SCENE_MENU

    def test_enter_triggers_confirm(self, monkeypatch):
        scene = _make_scene(monkeypatch)
        ev = types.SimpleNamespace(type=_pygame_stub.KEYDOWN, key=_pygame_stub.K_RETURN)
        scene.handle_event(ev)
        assert scene.manager.last_switch == SCENE_GAME
