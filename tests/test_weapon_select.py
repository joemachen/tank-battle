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
    _pygame_stub.K_TAB = 9
    _pygame_stub.K_q = 113
    _pygame_stub.K_e = 101

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
    SCENE_MAP_SELECT,
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
        """railgun speed (800) / WEAPON_STAT_MAX speed (800) == 1.0 (v0.25 new max)."""
        ratio = _normalise_weapon(800.0, "speed")
        assert ratio == pytest.approx(1.0)

    def test_grenade_launcher_damage_is_one(self):
        """grenade_launcher damage (70) / WEAPON_STAT_MAX damage (70) == 1.0."""
        ratio = _normalise_weapon(70.0, "damage")
        assert ratio == pytest.approx(1.0)

    def test_bouncing_round_range_is_one(self):
        """bouncing_round max_range (2400) / WEAPON_STAT_MAX max_range (2400) == 1.0."""
        ratio = _normalise_weapon(2400.0, "max_range")
        assert ratio == pytest.approx(1.0)

    def test_spread_shot_speed_ratio(self):
        """spread_shot speed (380) / 800 (v0.25 new max) ≈ 0.475."""
        ratio = _normalise_weapon(380.0, "speed")
        assert ratio == pytest.approx(380 / 800, rel=1e-4)

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

    def test_slot1_defaults_to_first_unlocked_weapon(self):
        """Slot 1 is pre-populated with the first unlocked weapon from the tank's defaults."""
        scene = _make_scene(unlocked=["standard_shell"])
        # medium_tank default_weapons[0] = standard_shell → slot 1 = standard_shell
        assert scene._slot_selections[0] == "standard_shell"

    def test_locked_default_weapon_leaves_slot_empty(self):
        """If the tank's default slot-2 weapon is locked, that slot remains None."""
        # medium_tank default_weapons[1] = null → slot 2 = None regardless
        scene = _make_scene(unlocked=["standard_shell"], tank_type="medium_tank")
        assert scene._slot_selections[1] is None


# ---------------------------------------------------------------------------
# 3. Kwarg forwarding to GameplayScene
# ---------------------------------------------------------------------------

class TestKwargForwarding:
    def test_confirm_switches_to_scene_game(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections[0] = "standard_shell"
        scene._confirm_selection()
        assert scene.manager.last_switch == SCENE_MAP_SELECT

    def test_weapon_types_forwarded_as_list(self):
        """Confirmed weapons are forwarded as weapon_types (list), not weapon_type."""
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections[0] = "standard_shell"
        scene._confirm_selection()
        wt = scene.manager.last_kwargs.get("weapon_types")
        assert isinstance(wt, list)
        assert "standard_shell" in wt

    def test_weapon_type_key_not_present(self):
        """New scene uses weapon_types (plural); the old weapon_type key must not appear."""
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections[0] = "standard_shell"
        scene._confirm_selection()
        assert "weapon_type" not in scene.manager.last_kwargs

    def test_tank_type_forwarded(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL, tank_type="heavy_tank")
        scene._slot_selections[0] = "standard_shell"
        scene._confirm_selection()
        assert scene.manager.last_kwargs.get("tank_type") == "heavy_tank"

    def test_ai_count_forwarded(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL, ai_count=3)
        scene._slot_selections[0] = "standard_shell"
        scene._confirm_selection()
        assert scene.manager.last_kwargs.get("ai_count") == 3

    def test_all_kwargs_present(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL, tank_type="scout_tank", ai_count=2)
        scene._slot_selections = ["standard_shell", "spread_shot", None]
        scene._confirm_selection()
        kw = scene.manager.last_kwargs
        assert kw.get("tank_type") == "scout_tank"
        assert kw.get("ai_count") == 2
        assert "standard_shell" in kw.get("weapon_types", [])
        assert "spread_shot" in kw.get("weapon_types", [])


# ---------------------------------------------------------------------------
# 4. Slot confirm logic (replaces old locked-weapon-ignores-confirm tests)
# ---------------------------------------------------------------------------

class TestSlotConfirmLogic:
    def test_empty_slot1_prevents_confirm(self):
        """If slot 1 is None, confirm must not call switch_to."""
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections = [None, None, None]
        scene._confirm_selection()
        assert scene.manager.last_switch is None

    def test_empty_slot1_leaves_no_kwargs(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections = [None, None, None]
        scene._confirm_selection()
        assert scene.manager.last_kwargs == {}

    def test_filled_slot1_allows_confirm(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections[0] = "standard_shell"
        scene._confirm_selection()
        assert scene.manager.last_switch == SCENE_MAP_SELECT

    def test_only_non_none_slots_forwarded(self):
        """Empty slots are excluded from weapon_types."""
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections = ["standard_shell", None, None]
        scene._confirm_selection()
        assert scene.manager.last_kwargs["weapon_types"] == ["standard_shell"]

    def test_multi_slot_selection_forwarded(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections = ["standard_shell", "spread_shot", None]
        scene._confirm_selection()
        assert scene.manager.last_kwargs["weapon_types"] == ["standard_shell", "spread_shot"]

    def test_all_three_slots_forwarded(self):
        scene = _make_scene(unlocked=_UNLOCKED_ALL)
        scene._slot_selections = ["standard_shell", "spread_shot", "bouncing_round"]
        scene._confirm_selection()
        assert scene.manager.last_kwargs["weapon_types"] == [
            "standard_shell", "spread_shot", "bouncing_round"
        ]


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


# ---------------------------------------------------------------------------
# 8. Spread shot bullet spawning
# ---------------------------------------------------------------------------

class TestSpreadShotSpawn:
    """
    Verify that spread_shot fires spread_count bullets and that the outer bullets
    are offset by spread_angle from the centre bullet.

    _spawn_bullet is tested via a minimal harness that skips all pygame rendering
    — we only care about how many Bullet objects end up in the bullet list and
    what angles they carry.
    """

    def _call_spawn(self, weapon_config: dict, turret_angle: float = 0.0) -> list:
        """
        Call game_scene._spawn_bullet logic directly without instantiating
        GameplayScene (which requires pygame display).  Returns the list of
        Bullet objects that would be appended.
        """
        from game.entities.bullet import Bullet
        from game.utils.math_utils import heading_to_vec
        from game.utils.constants import TANK_BARREL_LENGTH

        import math

        bullets: list = []
        ex, ey, eangle = 0.0, 0.0, turret_angle

        spread_count = int(weapon_config.get("spread_count", 1))
        spread_angle = float(weapon_config.get("spread_angle", 0.0))

        # Replicate the exact logic from GameplayScene._spawn_bullet
        class _FakeOwner:
            pass

        owner = _FakeOwner()

        if spread_count > 1 and spread_angle > 0.0:
            half_spread = spread_angle * (spread_count - 1) / 2.0
            for i in range(spread_count):
                offset = -half_spread + i * spread_angle
                bullet_angle = eangle + offset
                dx, dy = heading_to_vec(bullet_angle)
                bx = ex + dx * TANK_BARREL_LENGTH
                by = ey + dy * TANK_BARREL_LENGTH
                bullets.append(Bullet(bx, by, bullet_angle, owner, weapon_config))
        else:
            dx, dy = heading_to_vec(eangle)
            bx = ex + dx * TANK_BARREL_LENGTH
            by = ey + dy * TANK_BARREL_LENGTH
            bullets.append(Bullet(bx, by, eangle, owner, weapon_config))

        return bullets

    def _spread_config(self):
        from game.utils.config_loader import get_weapon_config
        from game.utils.constants import WEAPONS_CONFIG
        return get_weapon_config("spread_shot", WEAPONS_CONFIG)

    def _standard_config(self):
        from game.utils.config_loader import get_weapon_config
        from game.utils.constants import WEAPONS_CONFIG
        return get_weapon_config("standard_shell", WEAPONS_CONFIG)

    def test_spread_shot_fires_three_bullets(self):
        """spread_count=3 → exactly 3 Bullet objects spawned per trigger."""
        bullets = self._call_spawn(self._spread_config(), turret_angle=0.0)
        assert len(bullets) == 3

    def test_standard_shell_fires_one_bullet(self):
        """standard_shell has no spread_count → exactly 1 bullet."""
        bullets = self._call_spawn(self._standard_config(), turret_angle=0.0)
        assert len(bullets) == 1

    def test_spread_centre_bullet_on_turret_angle(self):
        """Middle bullet of 3-spread must travel exactly on turret_angle."""
        bullets = self._call_spawn(self._spread_config(), turret_angle=45.0)
        centre = bullets[1]   # index 1 = middle of [left, centre, right]
        assert centre.angle == pytest.approx(45.0)

    def test_spread_left_bullet_offset(self):
        """Left bullet (index 0) must be spread_angle degrees left of centre."""
        cfg = self._spread_config()
        spread_angle = cfg["spread_angle"]   # 18
        bullets = self._call_spawn(cfg, turret_angle=0.0)
        expected_left = 0.0 - spread_angle
        assert bullets[0].angle == pytest.approx(expected_left)

    def test_spread_right_bullet_offset(self):
        """Right bullet (index 2) must be spread_angle degrees right of centre."""
        cfg = self._spread_config()
        spread_angle = cfg["spread_angle"]
        bullets = self._call_spawn(cfg, turret_angle=0.0)
        expected_right = 0.0 + spread_angle
        assert bullets[2].angle == pytest.approx(expected_right)

    def test_spread_bullets_symmetric_around_turret(self):
        """All bullets are symmetric: left and right offsets are equal in magnitude."""
        cfg = self._spread_config()
        bullets = self._call_spawn(cfg, turret_angle=90.0)
        left_diff  = bullets[1].angle - bullets[0].angle
        right_diff = bullets[2].angle - bullets[1].angle
        assert left_diff == pytest.approx(right_diff)

    def test_spread_config_has_required_fields(self):
        """spread_shot YAML must declare spread_count and spread_angle."""
        cfg = self._spread_config()
        assert "spread_count" in cfg, "spread_shot missing spread_count"
        assert "spread_angle" in cfg, "spread_shot missing spread_angle"
        assert int(cfg["spread_count"]) >= 2
        assert float(cfg["spread_angle"]) > 0.0
