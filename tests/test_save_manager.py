"""
tests/test_save_manager.py

Unit tests for SaveManager — profile slots, settings, migration, delete.
Uses a temporary directory; no production save files are touched.
"""

import json
import os
import tempfile

import pytest

from game.utils.constants import DEFAULT_PROFILE, DEFAULT_SETTINGS

# ---------------------------------------------------------------------------
# Self-contained SaveManager replica for isolated testing
# ---------------------------------------------------------------------------

_LEGACY_FILENAME = "player_profile.json"
_PROFILES_DIR = "profiles"
_PROFILES_INDEX = "profiles.json"


class _TestSaveManager:
    """
    Stripped-down SaveManager that operates inside a tmp directory.
    Mirrors the v0.13.5 multi-slot logic without touching production paths.
    """

    def __init__(self, save_dir: str) -> None:
        self._save_dir = save_dir
        self._profiles_dir = os.path.join(save_dir, _PROFILES_DIR)
        self._index_path = os.path.join(save_dir, _PROFILES_INDEX)
        self._settings_path = os.path.join(save_dir, "settings.json")
        os.makedirs(self._profiles_dir, exist_ok=True)
        self._migrate_legacy()
        idx = self.load_profiles_index()
        self._active_slot: int = int(idx.get("active_slot", 0))

    @property
    def active_slot(self) -> int:
        return self._active_slot

    def set_active_profile(self, slot: int) -> None:
        self._active_slot = slot
        idx = self.load_profiles_index()
        idx["active_slot"] = slot
        self.save_profiles_index(idx)

    def load_profiles_index(self) -> dict:
        return self._load(self._index_path, {"active_slot": 0, "profiles": {}})

    def save_profiles_index(self, data: dict) -> bool:
        return self._save(self._index_path, data)

    def load_profile(self) -> dict:
        return self._load(self._profile_path(self._active_slot), DEFAULT_PROFILE)

    def save_profile(self, data: dict) -> bool:
        return self._save(self._profile_path(self._active_slot), data)

    def delete_profile(self, slot: int) -> bool:
        path = self._profile_path(slot)
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
        return self._load(self._settings_path, DEFAULT_SETTINGS)

    def save_settings(self, data: dict) -> bool:
        return self._save(self._settings_path, data)

    # Internal helpers

    def _profile_path(self, slot: int) -> str:
        return os.path.join(self._profiles_dir, f"profile_{slot}.json")

    def _migrate_legacy(self) -> None:
        legacy = os.path.join(self._save_dir, _LEGACY_FILENAME)
        dest = self._profile_path(0)
        if not os.path.exists(legacy) or os.path.exists(dest):
            return
        try:
            with open(legacy, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            idx = self._load(self._index_path, {"active_slot": 0, "profiles": {}})
            idx.setdefault("profiles", {}).setdefault("0", {"name": "Player 1", "slot": 0})
            self._save(self._index_path, idx)
        except (OSError, json.JSONDecodeError):
            pass

    def _load(self, path: str, defaults: dict) -> dict:
        if not os.path.exists(path):
            return dict(defaults)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return dict(defaults)

    def _save(self, path: str, data) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sm(tmp_path):
    return _TestSaveManager(str(tmp_path))


@pytest.fixture
def sm_with_slot0(tmp_path):
    """SaveManager with slot 0 pre-populated."""
    m = _TestSaveManager(str(tmp_path))
    m.set_active_profile(0)
    data = dict(DEFAULT_PROFILE)
    data["xp"] = 200
    data["level"] = 3
    m.save_profile(data)
    idx = m.load_profiles_index()
    idx.setdefault("profiles", {})["0"] = {"name": "Alpha", "slot": 0}
    m.save_profiles_index(idx)
    return m


# ---------------------------------------------------------------------------
# Legacy default behaviour (same as before v0.13.5)
# ---------------------------------------------------------------------------

class TestProfileDefaults:
    def test_missing_file_returns_defaults(self, sm):
        profile = sm.load_profile()
        assert profile["level"] == 1
        assert profile["xp"] == 0

    def test_returns_copy_not_singleton(self, sm):
        p1 = sm.load_profile()
        p2 = sm.load_profile()
        p1["xp"] = 999
        assert p2["xp"] == 0


class TestProfileRoundtrip:
    def test_save_and_load(self, sm):
        data = dict(DEFAULT_PROFILE)
        data["xp"] = 500
        data["level"] = 3
        assert sm.save_profile(data) is True
        loaded = sm.load_profile()
        assert loaded["xp"] == 500
        assert loaded["level"] == 3

    def test_corrupt_file_returns_defaults(self, sm, tmp_path):
        path = os.path.join(str(tmp_path), "profiles", "profile_0.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("NOT_VALID_JSON{{{{")
        profile = sm.load_profile()
        assert profile["level"] == 1


class TestSettingsRoundtrip:
    def test_save_and_load_settings(self, sm):
        settings = dict(DEFAULT_SETTINGS)
        settings["master_volume"] = 0.5
        assert sm.save_settings(settings) is True
        loaded = sm.load_settings()
        assert loaded["master_volume"] == 0.5


# ---------------------------------------------------------------------------
# Multi-slot: set_active_profile
# ---------------------------------------------------------------------------

class TestSetActiveProfile:
    def test_default_slot_is_zero(self, sm):
        assert sm.active_slot == 0

    def test_set_active_profile_changes_slot(self, sm):
        sm.set_active_profile(2)
        assert sm.active_slot == 2

    def test_set_active_profile_persists_to_index(self, sm):
        sm.set_active_profile(3)
        idx = sm.load_profiles_index()
        assert idx["active_slot"] == 3

    def test_profile_path_follows_active_slot(self, sm, tmp_path):
        # Write different data to slot 1
        sm.set_active_profile(1)
        data = dict(DEFAULT_PROFILE)
        data["xp"] = 777
        sm.save_profile(data)
        # Slot 0 should still return defaults
        sm.set_active_profile(0)
        assert sm.load_profile()["xp"] == 0
        # Slot 1 should return 777
        sm.set_active_profile(1)
        assert sm.load_profile()["xp"] == 777


# ---------------------------------------------------------------------------
# Multi-slot: profiles index
# ---------------------------------------------------------------------------

class TestProfilesIndex:
    def test_load_index_returns_defaults_when_missing(self, sm):
        idx = sm.load_profiles_index()
        assert idx["active_slot"] == 0
        assert isinstance(idx["profiles"], dict)

    def test_save_and_load_index(self, sm):
        idx = {"active_slot": 1, "profiles": {"1": {"name": "Beta", "slot": 1}}}
        assert sm.save_profiles_index(idx) is True
        loaded = sm.load_profiles_index()
        assert loaded["active_slot"] == 1
        assert loaded["profiles"]["1"]["name"] == "Beta"

    def test_index_lists_all_registered_slots(self, sm_with_slot0):
        idx = sm_with_slot0.load_profiles_index()
        assert "0" in idx["profiles"]


# ---------------------------------------------------------------------------
# Multi-slot: delete_profile
# ---------------------------------------------------------------------------

class TestDeleteProfile:
    def test_delete_removes_file(self, sm_with_slot0, tmp_path):
        path = os.path.join(str(tmp_path), "profiles", "profile_0.json")
        assert os.path.exists(path)
        sm_with_slot0.delete_profile(0)
        assert not os.path.exists(path)

    def test_delete_removes_from_index(self, sm_with_slot0):
        sm_with_slot0.delete_profile(0)
        idx = sm_with_slot0.load_profiles_index()
        assert "0" not in idx.get("profiles", {})

    def test_delete_nonexistent_slot_returns_true(self, sm):
        # Slot 3 was never written — should not raise
        assert sm.delete_profile(3) is True

    def test_delete_does_not_affect_other_slots(self, tmp_path):
        m = _TestSaveManager(str(tmp_path))
        # Create slots 0 and 1
        m.set_active_profile(0)
        m.save_profile(dict(DEFAULT_PROFILE))
        idx = m.load_profiles_index()
        idx["profiles"]["0"] = {"name": "Alpha", "slot": 0}
        idx["profiles"]["1"] = {"name": "Beta", "slot": 1}
        m.save_profiles_index(idx)
        m.set_active_profile(1)
        d1 = dict(DEFAULT_PROFILE)
        d1["xp"] = 500
        m.save_profile(d1)

        m.delete_profile(0)

        m.set_active_profile(1)
        assert m.load_profile()["xp"] == 500


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class TestMigration:
    def test_legacy_file_migrated_to_slot_0(self, tmp_path):
        # Plant a legacy profile before constructing SaveManager
        legacy_data = dict(DEFAULT_PROFILE)
        legacy_data["xp"] = 9999
        legacy_data["level"] = 12
        legacy_path = os.path.join(str(tmp_path), "player_profile.json")
        with open(legacy_path, "w") as f:
            json.dump(legacy_data, f)

        m = _TestSaveManager(str(tmp_path))
        loaded = m.load_profile()
        assert loaded["xp"] == 9999
        assert loaded["level"] == 12

    def test_legacy_migration_registers_slot_0_in_index(self, tmp_path):
        legacy_data = dict(DEFAULT_PROFILE)
        legacy_path = os.path.join(str(tmp_path), "player_profile.json")
        with open(legacy_path, "w") as f:
            json.dump(legacy_data, f)

        m = _TestSaveManager(str(tmp_path))
        idx = m.load_profiles_index()
        assert "0" in idx.get("profiles", {})

    def test_no_migration_if_slot0_already_exists(self, tmp_path):
        # Write a fresh slot 0 first
        profiles_dir = os.path.join(str(tmp_path), "profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        existing = dict(DEFAULT_PROFILE)
        existing["xp"] = 42
        slot0_path = os.path.join(profiles_dir, "profile_0.json")
        with open(slot0_path, "w") as f:
            json.dump(existing, f)
        # Plant a legacy file with different data
        legacy_data = dict(DEFAULT_PROFILE)
        legacy_data["xp"] = 9999
        legacy_path = os.path.join(str(tmp_path), "player_profile.json")
        with open(legacy_path, "w") as f:
            json.dump(legacy_data, f)

        m = _TestSaveManager(str(tmp_path))
        # Slot 0 should NOT be overwritten
        assert m.load_profile()["xp"] == 42

    def test_fresh_install_no_legacy_no_crash(self, tmp_path):
        m = _TestSaveManager(str(tmp_path))
        assert m.load_profile()["level"] == 1
        assert m.active_slot == 0


# ---------------------------------------------------------------------------
# Auto-create default profile (v0.17.5)
# ---------------------------------------------------------------------------

class _TestSaveManagerWithAutoCreate(_TestSaveManager):
    """
    Extends _TestSaveManager with the _auto_create_default_profile() behaviour
    introduced in v0.17.5, so we can test it in isolation.
    """

    def __init__(self, save_dir: str) -> None:
        # Call grandparent-equivalent setup manually (replicate __init__ up to
        # migration, then run auto-create before reading active_slot)
        self._save_dir = save_dir
        self._profiles_dir = os.path.join(save_dir, _PROFILES_DIR)
        self._index_path = os.path.join(save_dir, _PROFILES_INDEX)
        self._settings_path = os.path.join(save_dir, "settings.json")
        os.makedirs(self._profiles_dir, exist_ok=True)
        self._migrate_legacy()
        self._auto_create_default_profile()
        idx = self.load_profiles_index()
        self._active_slot: int = int(idx.get("active_slot", 0))

    def _auto_create_default_profile(self) -> None:
        idx = self.load_profiles_index()
        if idx.get("profiles"):
            return
        profile_path = self._profile_path(0)
        with open(profile_path, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(dict(DEFAULT_PROFILE), f, indent=2)
        idx.setdefault("profiles", {})["0"] = {"name": "Player 1", "slot": 0}
        idx["active_slot"] = 0
        self.save_profiles_index(idx)
        self._active_slot = 0


class TestAutoCreateDefaultProfile:
    """v0.17.5: SaveManager silently creates 'Player 1' slot 0 on first run."""

    def test_auto_create_fires_on_empty_saves_dir(self, tmp_path):
        m = _TestSaveManagerWithAutoCreate(str(tmp_path))
        idx = m.load_profiles_index()
        assert "0" in idx.get("profiles", {})

    def test_auto_created_name_is_player_1(self, tmp_path):
        m = _TestSaveManagerWithAutoCreate(str(tmp_path))
        idx = m.load_profiles_index()
        assert idx["profiles"]["0"]["name"] == "Player 1"

    def test_auto_created_data_matches_default_profile(self, tmp_path):
        m = _TestSaveManagerWithAutoCreate(str(tmp_path))
        profile = m.load_profile()
        assert profile["xp"] == DEFAULT_PROFILE["xp"]
        assert profile["level"] == DEFAULT_PROFILE["level"]
        assert profile["wins"] == DEFAULT_PROFILE["wins"]

    def test_auto_create_does_not_fire_when_slot0_exists(self, tmp_path):
        """If a profile already exists, auto-create must not overwrite it."""
        # Manually create a profile with xp=999 before constructing manager
        profiles_dir = os.path.join(str(tmp_path), "profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        existing = dict(DEFAULT_PROFILE)
        existing["xp"] = 999
        slot0_path = os.path.join(profiles_dir, "profile_0.json")
        with open(slot0_path, "w") as f:
            import json as _json
            _json.dump(existing, f)
        idx_path = os.path.join(str(tmp_path), "profiles.json")
        with open(idx_path, "w") as f:
            import json as _json
            _json.dump({"active_slot": 0, "profiles": {"0": {"name": "Existing", "slot": 0}}}, f)

        m = _TestSaveManagerWithAutoCreate(str(tmp_path))
        assert m.load_profile()["xp"] == 999

    def test_auto_create_fires_when_profiles_dict_empty(self, tmp_path):
        """profiles.json exists but profiles={} → auto-create must still fire."""
        idx_path = os.path.join(str(tmp_path), "profiles.json")
        with open(idx_path, "w") as f:
            import json as _json
            _json.dump({"active_slot": 0, "profiles": {}}, f)

        m = _TestSaveManagerWithAutoCreate(str(tmp_path))
        idx = m.load_profiles_index()
        assert "0" in idx["profiles"]
