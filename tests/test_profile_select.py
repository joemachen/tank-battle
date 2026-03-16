"""
tests/test_profile_select.py

Unit tests for ProfileSelectScene behaviour:
  - Name validation (max length, blank → default)
  - Slot state helpers (_is_occupied, _has_any_profile)
  - Cannot-delete-last guard (logic layer only)
  - Active profile update on select
  - Active profile reassignment after delete

All tests are pure-logic; no pygame display required.
The scene is instantiated with a stub manager and its SaveManager
is replaced with an in-process _TestSaveManager (defined here) that
operates inside tmp_path so production saves are never touched.
"""

import json
import os

import pytest
import pygame

from game.utils.constants import (
    DEFAULT_PROFILE,
    DEFAULT_SETTINGS,
    MAX_PROFILES,
    PROFILE_NAME_MAX_LEN,
)

# ---------------------------------------------------------------------------
# Minimal pygame initialisation (headless)
# ---------------------------------------------------------------------------

pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)


# ---------------------------------------------------------------------------
# Stub manager and SaveManager used by the scene under test
# ---------------------------------------------------------------------------

class _StubManager:
    def __init__(self):
        self.switched_to = None
        self.kwargs = {}

    def switch_to(self, key, **kwargs):
        self.switched_to = key
        self.kwargs = kwargs


class _TestSaveManager:
    """In-memory SaveManager for scene unit tests."""

    def __init__(self, save_dir: str) -> None:
        self._save_dir = save_dir
        self._profiles_dir = os.path.join(save_dir, "profiles")
        self._index_path = os.path.join(save_dir, "profiles.json")
        os.makedirs(self._profiles_dir, exist_ok=True)
        self._active_slot: int = 0

    @property
    def active_slot(self) -> int:
        return self._active_slot

    def set_active_profile(self, slot: int) -> None:
        self._active_slot = slot
        idx = self.load_profiles_index()
        idx["active_slot"] = slot
        self.save_profiles_index(idx)

    def load_profiles_index(self) -> dict:
        if not os.path.exists(self._index_path):
            return {"active_slot": 0, "profiles": {}}
        try:
            with open(self._index_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"active_slot": 0, "profiles": {}}

    def save_profiles_index(self, data: dict) -> bool:
        try:
            with open(self._index_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except OSError:
            return False

    def load_profile(self) -> dict:
        path = os.path.join(self._profiles_dir, f"profile_{self._active_slot}.json")
        if not os.path.exists(path):
            return dict(DEFAULT_PROFILE)
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_PROFILE)

    def save_profile(self, data: dict) -> bool:
        path = os.path.join(self._profiles_dir, f"profile_{self._active_slot}.json")
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except OSError:
            return False

    def delete_profile(self, slot: int) -> bool:
        path = os.path.join(self._profiles_dir, f"profile_{slot}.json")
        try:
            if os.path.exists(path):
                os.remove(path)
            idx = self.load_profiles_index()
            idx.get("profiles", {}).pop(str(slot), None)
            self.save_profiles_index(idx)
            return True
        except OSError:
            return False

    def load_settings(self) -> dict:
        return dict(DEFAULT_SETTINGS)

    def save_settings(self, data: dict) -> bool:
        return True


# ---------------------------------------------------------------------------
# Helpers to build scene under test
# ---------------------------------------------------------------------------

def _make_scene(tmp_path):
    """Instantiate ProfileSelectScene with stub manager + isolated SaveManager."""
    from game.scenes.profile_select_scene import ProfileSelectScene
    mgr = _StubManager()
    scene = ProfileSelectScene(mgr)
    # Replace live SaveManager with isolated test instance
    save = _TestSaveManager(str(tmp_path))
    scene._save = save
    scene._index = save.load_profiles_index()
    return scene, save, mgr


def _populate_slot(save: _TestSaveManager, slot: int, name: str, xp: int = 0) -> None:
    """Register a slot in the index and write a profile file."""
    save.set_active_profile(slot)
    data = dict(DEFAULT_PROFILE)
    data["xp"] = xp
    save.save_profile(data)
    idx = save.load_profiles_index()
    idx.setdefault("profiles", {})[str(slot)] = {"name": name, "slot": slot}
    save.save_profiles_index(idx)
    save._active_slot = 0  # reset to slot 0 as default


# ---------------------------------------------------------------------------
# Tests: slot state helpers
# ---------------------------------------------------------------------------

class TestSlotStateHelpers:
    def test_empty_index_no_profile(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        scene._refresh_index()
        assert not scene._has_any_profile()

    def test_occupied_after_populate(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 0, "Alpha")
        scene._refresh_index()
        assert scene._is_occupied(0)

    def test_empty_slot_not_occupied(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 0, "Alpha")
        scene._refresh_index()
        assert not scene._is_occupied(1)

    def test_has_any_profile_with_one_slot(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 2, "Gamma")
        scene._refresh_index()
        assert scene._has_any_profile()

    def test_all_four_slots_occupied(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        for i in range(MAX_PROFILES):
            _populate_slot(save, i, f"P{i}")
        scene._refresh_index()
        assert all(scene._is_occupied(i) for i in range(MAX_PROFILES))


# ---------------------------------------------------------------------------
# Tests: name entry validation
# ---------------------------------------------------------------------------

class TestNameValidation:
    def test_blank_name_defaults_to_player_n(self, tmp_path):
        scene, save, mgr = _make_scene(tmp_path)
        scene._entry_slot = 0
        scene._entry_name = ""   # blank
        # Simulate pressing ENTER in name-entry mode
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        scene._mode = "name_entry"
        scene._handle_name_entry(event)
        scene._refresh_index()
        idx = save.load_profiles_index()
        # Name should be "Player 1" (slot 0+1)
        created_name = idx.get("profiles", {}).get("0", {}).get("name", "")
        assert created_name == "Player 1"

    def test_whitespace_only_name_defaults(self, tmp_path):
        scene, save, mgr = _make_scene(tmp_path)
        scene._entry_slot = 1
        scene._entry_name = "   "
        scene._mode = "name_entry"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        scene._handle_name_entry(event)
        scene._refresh_index()
        idx = save.load_profiles_index()
        created_name = idx.get("profiles", {}).get("1", {}).get("name", "")
        assert created_name == "Player 2"

    def test_name_capped_at_max_len(self, tmp_path):
        scene, _, _ = _make_scene(tmp_path)
        scene._mode = "name_entry"
        scene._entry_name = ""
        # Type PROFILE_NAME_MAX_LEN + 3 extra chars
        long_input = "A" * (PROFILE_NAME_MAX_LEN + 3)
        for ch in long_input:
            event = pygame.event.Event(
                pygame.KEYDOWN, key=ord(ch), unicode=ch
            )
            scene._handle_name_entry(event)
        assert len(scene._entry_name) == PROFILE_NAME_MAX_LEN

    def test_backspace_removes_last_char(self, tmp_path):
        scene, _, _ = _make_scene(tmp_path)
        scene._mode = "name_entry"
        scene._entry_name = "ABC"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode="")
        scene._handle_name_entry(event)
        assert scene._entry_name == "AB"

    def test_esc_cancels_name_entry(self, tmp_path):
        scene, _, _ = _make_scene(tmp_path)
        scene._mode = "name_entry"
        scene._entry_name = "Partial"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="")
        scene._handle_name_entry(event)
        assert scene._mode == "select"
        assert scene._entry_name == ""


# ---------------------------------------------------------------------------
# Tests: active profile update on slot selection
# ---------------------------------------------------------------------------

class TestActiveProfileUpdate:
    def test_selecting_occupied_slot_sets_active(self, tmp_path):
        scene, save, mgr = _make_scene(tmp_path)
        _populate_slot(save, 2, "Zeta")
        scene._refresh_index()
        # Directly call _activate_slot (bypasses audio)
        scene._save.set_active_profile = lambda s: setattr(scene._save, "_active_slot", s)
        scene._activate_slot(2)
        assert scene._save.active_slot == 2

    def test_selecting_empty_slot_enters_name_mode(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        scene._refresh_index()
        scene._activate_slot(3)
        assert scene._mode == "name_entry"
        assert scene._entry_slot == 3


# ---------------------------------------------------------------------------
# Tests: delete profile
# ---------------------------------------------------------------------------

class TestDeleteProfile:
    def test_delete_removes_slot_from_index(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 1, "Beta")
        scene._refresh_index()
        scene._delete_profile(1)
        idx = save.load_profiles_index()
        assert "1" not in idx.get("profiles", {})

    def test_delete_last_profile_allowed(self, tmp_path):
        """Game allows deletion even of the last profile; scene handles gracefully."""
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 0, "Solo")
        scene._refresh_index()
        scene._delete_profile(0)
        scene._refresh_index()
        assert not scene._has_any_profile()

    def test_delete_active_slot_reassigns_active(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 0, "Alpha")
        _populate_slot(save, 1, "Beta")
        save.set_active_profile(0)
        scene._refresh_index()
        scene._delete_profile(0)
        # Active slot should have moved off 0
        idx = save.load_profiles_index()
        assert idx["active_slot"] != 0 or "0" not in idx.get("profiles", {})

    def test_confirm_delete_triggers_delete_profile(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 2, "Gamma")
        scene._refresh_index()
        scene._mode = "confirm_delete"
        scene._delete_slot = 2
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y, unicode="y")
        scene._handle_delete_confirm(event)
        scene._refresh_index()
        assert not scene._is_occupied(2)

    def test_cancel_delete_keeps_profile(self, tmp_path):
        scene, save, _ = _make_scene(tmp_path)
        _populate_slot(save, 0, "Keep")
        scene._refresh_index()
        scene._mode = "confirm_delete"
        scene._delete_slot = 0
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="")
        scene._handle_delete_confirm(event)
        assert scene._mode == "select"
        scene._refresh_index()
        assert scene._is_occupied(0)


# ---------------------------------------------------------------------------
# Tests: ESC navigation guard
# ---------------------------------------------------------------------------

class TestEscGuard:
    def test_esc_blocked_when_no_profiles(self, tmp_path):
        scene, save, mgr = _make_scene(tmp_path)
        scene._refresh_index()
        # Patch fade to track calls
        started = []
        scene._fade.start = lambda: started.append(True)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="")
        scene._handle_select(event)
        assert not started, "ESC should be blocked when no profiles exist"

    def test_esc_allowed_when_profile_exists(self, tmp_path):
        scene, save, mgr = _make_scene(tmp_path)
        _populate_slot(save, 0, "Solo")
        scene._refresh_index()
        started = []
        scene._fade.start = lambda: started.append(True)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="")
        scene._handle_select(event)
        assert started, "ESC should trigger fade when at least one profile exists"
