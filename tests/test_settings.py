"""
tests/test_settings.py

Unit tests for v0.13 settings screen components and logic.
Pure logic — no pygame display, no file I/O (SaveManager calls are mocked
where needed via tmp_path fixtures).

Coverage:
  - SliderComponent: clamp, step increment/decrement
  - CycleComponent: wrap-around behaviour
  - KeybindComponent: try_bind, commit, listen state
  - find_keybind_conflict: conflict detection and no-false-positive
  - SaveManager round-trip: save settings dict, reload, values match
"""

import json
import os
import sys

import pygame
import pytest

# Minimal pygame init required for key constants used in components
pygame.init()


# ---------------------------------------------------------------------------
# SliderComponent
# ---------------------------------------------------------------------------

class TestSliderComponent:
    from game.ui.components import SliderComponent

    def _make(self, current=0.5, min_val=0.0, max_val=1.0):
        from game.ui.components import SliderComponent
        return SliderComponent("Vol", min_val, max_val, current)

    def test_clamp_below_min(self):
        s = self._make(current=-0.5)
        assert s.value == 0.0

    def test_clamp_above_max(self):
        s = self._make(current=1.8)
        assert s.value == 1.0

    def test_initial_value_preserved(self):
        s = self._make(current=0.7)
        assert abs(s.value - 0.7) < 1e-9

    def test_right_increments_by_step(self):
        s = self._make(current=0.5)
        changed = s.handle_input(pygame.K_RIGHT)
        assert changed is True
        assert abs(s.value - 0.55) < 1e-6

    def test_left_decrements_by_step(self):
        s = self._make(current=0.5)
        s.handle_input(pygame.K_LEFT)
        assert abs(s.value - 0.45) < 1e-6

    def test_clamps_at_max_on_increment(self):
        s = self._make(current=0.98)
        s.handle_input(pygame.K_RIGHT)
        s.handle_input(pygame.K_RIGHT)
        assert s.value <= 1.0

    def test_clamps_at_min_on_decrement(self):
        s = self._make(current=0.02)
        s.handle_input(pygame.K_LEFT)
        s.handle_input(pygame.K_LEFT)
        assert s.value >= 0.0

    def test_no_change_at_min_returns_false(self):
        s = self._make(current=0.0)
        changed = s.handle_input(pygame.K_LEFT)
        assert changed is False

    def test_no_change_at_max_returns_false(self):
        s = self._make(current=1.0)
        changed = s.handle_input(pygame.K_RIGHT)
        assert changed is False

    def test_value_setter_clamps(self):
        s = self._make()
        s.value = 2.5
        assert s.value == 1.0
        s.value = -1.0
        assert s.value == 0.0


# ---------------------------------------------------------------------------
# CycleComponent
# ---------------------------------------------------------------------------

class TestCycleComponent:
    def _make(self, options=None, index=0):
        from game.ui.components import CycleComponent
        opts = options or ["A", "B", "C"]
        return CycleComponent("Label", opts, index)

    def test_initial_value(self):
        c = self._make(index=1)
        assert c.value == "B"

    def test_right_advances(self):
        c = self._make(index=0)
        c.handle_input(pygame.K_RIGHT)
        assert c.value == "B"

    def test_left_retreats(self):
        c = self._make(index=1)
        c.handle_input(pygame.K_LEFT)
        assert c.value == "A"

    def test_wraps_forward_at_end(self):
        c = self._make(index=2)   # last item "C"
        c.handle_input(pygame.K_RIGHT)
        assert c.value == "A"    # wraps back to first

    def test_wraps_backward_at_start(self):
        c = self._make(index=0)
        c.handle_input(pygame.K_LEFT)
        assert c.value == "C"    # wraps to last

    def test_handle_input_returns_true_on_change(self):
        c = self._make()
        assert c.handle_input(pygame.K_RIGHT) is True
        assert c.handle_input(pygame.K_LEFT) is True

    def test_index_setter(self):
        c = self._make()
        c.index = 2
        assert c.value == "C"

    def test_index_setter_clamps(self):
        c = self._make()
        c.index = 99
        assert c.index == 2   # clamped to last

    def test_single_option_no_crash(self):
        from game.ui.components import CycleComponent
        c = CycleComponent("L", ["ONLY"], 0)
        c.handle_input(pygame.K_RIGHT)
        assert c.value == "ONLY"


# ---------------------------------------------------------------------------
# KeybindComponent
# ---------------------------------------------------------------------------

class TestKeybindComponent:
    def _make(self, key="w"):
        from game.ui.components import KeybindComponent
        return KeybindComponent("Move Forward", "move_forward", key)

    def test_initial_value(self):
        k = self._make("s")
        assert k.value == "s"

    def test_not_listening_initially(self):
        k = self._make()
        assert k.is_listening is False

    def test_activate_listen(self):
        k = self._make()
        k.activate_listen()
        assert k.is_listening is True

    def test_cancel_listen(self):
        k = self._make()
        k.activate_listen()
        k.cancel_listen()
        assert k.is_listening is False

    def test_try_bind_esc_cancels_without_return(self):
        k = self._make()
        k.activate_listen()
        result = k.try_bind(pygame.K_ESCAPE)
        assert result is None
        assert k.is_listening is False

    def test_try_bind_returns_key_name(self):
        k = self._make()
        k.activate_listen()
        result = k.try_bind(pygame.K_a)
        assert result == "a"
        assert k.is_listening is False   # exits listen after valid key

    def test_commit_applies_key(self):
        k = self._make("w")
        k.commit("d")
        assert k.value == "d"

    def test_try_bind_ignores_modifier_keys(self):
        k = self._make()
        k.activate_listen()
        result = k.try_bind(pygame.K_LSHIFT)
        assert result is None
        assert k.is_listening is True   # still listening — modifier ignored


# ---------------------------------------------------------------------------
# find_keybind_conflict
# ---------------------------------------------------------------------------

class TestFindKeybindConflict:
    def _build_rows(self, binds: dict):
        """Build a minimal row list matching settings_scene structure."""
        from game.ui.components import KeybindComponent
        from game.scenes.settings_scene import _Row

        rows = []
        for action, key in binds.items():
            label = action.replace("_", " ").title()
            rows.append(_Row("keybind", label,
                             KeybindComponent(label, action, key), action))
        return rows

    def test_no_conflict_returns_none(self):
        from game.scenes.settings_scene import find_keybind_conflict
        rows = self._build_rows({"move_forward": "w", "move_backward": "s"})
        assert find_keybind_conflict(rows, "a", "move_forward") is None

    def test_conflict_returns_label(self):
        from game.scenes.settings_scene import find_keybind_conflict
        rows = self._build_rows({"move_forward": "w", "move_backward": "s"})
        # Try to bind "s" to move_forward — "s" is already on move_backward
        result = find_keybind_conflict(rows, "s", "move_forward")
        assert result == "Move Backward"

    def test_same_action_excluded_from_conflict(self):
        from game.scenes.settings_scene import find_keybind_conflict
        rows = self._build_rows({"move_forward": "w"})
        # Binding "w" to move_forward itself should NOT conflict
        assert find_keybind_conflict(rows, "w", "move_forward") is None

    def test_conflict_skips_non_keybind_rows(self):
        from game.scenes.settings_scene import find_keybind_conflict, _Row
        rows = self._build_rows({"move_forward": "w"})
        rows.append(_Row("section", "AUDIO", focusable=False))  # non-keybind
        assert find_keybind_conflict(rows, "x", "move_forward") is None

    def test_fire_participates_in_conflict_detection(self):
        from game.scenes.settings_scene import find_keybind_conflict
        rows = self._build_rows({"fire": "space", "move_forward": "w"})
        result = find_keybind_conflict(rows, "space", "move_forward")
        assert result == "Fire"

    def test_mute_participates_in_conflict_detection(self):
        from game.scenes.settings_scene import find_keybind_conflict
        rows = self._build_rows({"mute": "m", "move_forward": "w"})
        result = find_keybind_conflict(rows, "m", "move_forward")
        assert result == "Mute"


# ---------------------------------------------------------------------------
# Fire and Mute rebindable (v0.17.5)
# ---------------------------------------------------------------------------

class TestFireAndMuteRebindable:
    """Fire and Mute rows are full KeybindComponent rows, not static/read-only."""

    def _build_settings_rows(self):
        from game.utils.constants import DEFAULT_SETTINGS
        from game.scenes.settings_scene import SettingsScene

        class _FakeManager:
            def switch_to(self, *a, **kw): pass

        scene = SettingsScene(_FakeManager())
        return scene._build_rows(dict(DEFAULT_SETTINGS))

    def test_fire_row_is_keybind(self):
        rows = self._build_settings_rows()
        fire_rows = [r for r in rows if r.settings_key == "fire"]
        assert len(fire_rows) == 1
        assert fire_rows[0].kind == "keybind"
        assert fire_rows[0].focusable is True

    def test_mute_row_is_keybind(self):
        rows = self._build_settings_rows()
        mute_rows = [r for r in rows if r.settings_key == "mute"]
        assert len(mute_rows) == 1
        assert mute_rows[0].kind == "keybind"
        assert mute_rows[0].focusable is True

    def test_fire_row_default_value_is_space(self):
        rows = self._build_settings_rows()
        fire = [r for r in rows if r.settings_key == "fire"][0]
        assert fire.component.value == "space"

    def test_mute_row_default_value_is_m(self):
        rows = self._build_settings_rows()
        mute = [r for r in rows if r.settings_key == "mute"][0]
        assert mute.component.value == "m"

    def test_fire_row_is_rebindable(self):
        rows = self._build_settings_rows()
        fire = [r for r in rows if r.settings_key == "fire"][0]
        fire.component.activate_listen()
        result = fire.component.try_bind(pygame.K_x)
        assert result == "x"
        fire.component.commit(result)
        assert fire.component.value == "x"

    def test_mute_row_is_rebindable(self):
        rows = self._build_settings_rows()
        mute = [r for r in rows if r.settings_key == "mute"][0]
        mute.component.activate_listen()
        result = mute.component.try_bind(pygame.K_n)
        assert result == "n"
        mute.component.commit(result)
        assert mute.component.value == "n"

    def test_no_static_rows_remain(self):
        rows = self._build_settings_rows()
        static_rows = [r for r in rows if r.kind == "static"]
        assert len(static_rows) == 0


# ---------------------------------------------------------------------------
# SaveManager round-trip for settings
# ---------------------------------------------------------------------------

class TestSettingsRoundTrip:
    def test_save_and_reload_preserves_values(self, tmp_path):
        """Settings written to disk can be read back identically."""
        from game.utils.save_manager import SaveManager

        # Patch SAVES_DIR and SETTINGS_FILE to use tmp_path
        import game.utils.constants as consts
        orig_dir  = consts.SAVES_DIR
        orig_file = consts.SETTINGS_FILE
        consts.SAVES_DIR    = str(tmp_path)
        consts.SETTINGS_FILE = str(tmp_path / "settings.json")

        try:
            sm = SaveManager()
            payload = {
                "master_volume": 0.75,
                "music_volume":  0.5,
                "sfx_volume":    0.9,
                "ai_difficulty": "hard",
                "fullscreen":    False,
                "resolution":    [1280, 720],
                "keybinds": {"move_forward": "w", "move_backward": "s"},
            }
            sm.save_settings(payload)
            loaded = sm.load_settings()
            assert loaded["master_volume"] == 0.75
            assert loaded["ai_difficulty"] == "hard"
            assert loaded["keybinds"]["move_forward"] == "w"
        finally:
            consts.SAVES_DIR    = orig_dir
            consts.SETTINGS_FILE = orig_file

    def test_missing_file_returns_defaults(self, tmp_path):
        from game.utils.save_manager import SaveManager
        import game.utils.constants as consts
        orig_dir  = consts.SAVES_DIR
        orig_file = consts.SETTINGS_FILE
        consts.SAVES_DIR     = str(tmp_path)
        consts.SETTINGS_FILE = str(tmp_path / "no_file.json")
        try:
            sm = SaveManager()
            loaded = sm.load_settings()
            # Should return DEFAULT_SETTINGS values, not crash
            assert "master_volume" in loaded
            assert "keybinds" in loaded
        finally:
            consts.SAVES_DIR    = orig_dir
            consts.SETTINGS_FILE = orig_file
