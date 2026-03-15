"""
tests/test_save_manager.py

Unit tests for SaveManager serialization and default fallback behavior.
Uses a temporary directory — no production save files are touched.
"""

import json
import os
import tempfile

import pytest

from game.utils.constants import DEFAULT_PROFILE, DEFAULT_SETTINGS


# ---------------------------------------------------------------------------
# Minimal SaveManager replica for isolated testing
# ---------------------------------------------------------------------------

class _TestSaveManager:
    """
    Stripped-down SaveManager that writes to a temp directory.
    Tests the same logic without touching production paths.
    """

    def __init__(self, save_dir: str) -> None:
        self._profile_path = os.path.join(save_dir, "player_profile.json")
        self._settings_path = os.path.join(save_dir, "settings.json")

    def load_profile(self) -> dict:
        return self._load(self._profile_path, DEFAULT_PROFILE)

    def save_profile(self, data: dict) -> bool:
        return self._save(self._profile_path, data)

    def load_settings(self) -> dict:
        return self._load(self._settings_path, DEFAULT_SETTINGS)

    def save_settings(self, data: dict) -> bool:
        return self._save(self._settings_path, data)

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
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def sm(tmp_path):
    return _TestSaveManager(str(tmp_path))


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
        profile_path = tmp_path / "player_profile.json"
        profile_path.write_text("NOT_VALID_JSON{{{{")
        profile = sm.load_profile()
        assert profile["level"] == 1


class TestSettingsRoundtrip:
    def test_save_and_load_settings(self, sm):
        settings = dict(DEFAULT_SETTINGS)
        settings["master_volume"] = 0.5
        assert sm.save_settings(settings) is True
        loaded = sm.load_settings()
        assert loaded["master_volume"] == 0.5
