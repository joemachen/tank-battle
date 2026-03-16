"""
game/utils/save_manager.py

All file I/O for player profiles and settings goes through this class.
No other module should read or write JSON save files directly.

Profile storage layout (v0.13.5+):
  saves/profiles.json              — index: active slot + per-slot metadata
  saves/profiles/profile_0.json   — slot 0 profile data
  saves/profiles/profile_1.json   — slot 1 profile data
  ...

Migration: if the legacy saves/player_profile.json exists and slot 0 is absent,
the legacy file is automatically copied to slot 0 on first run.
"""

import json
import os
import traceback
from typing import Any

from game.utils.constants import (
    DEFAULT_PROFILE,
    DEFAULT_SETTINGS,
    PROFILES_DIR,
    PROFILES_INDEX_FILE,
    SAVES_DIR,
    SETTINGS_FILE,
)
from game.utils.logger import get_logger

log = get_logger(__name__)

# Path of the pre-v0.13.5 single-file profile (migration source only)
_LEGACY_PROFILE_FILE: str = "saves/player_profile.json"

# Default profiles index structure
_DEFAULT_INDEX: dict = {"active_slot": 0, "profiles": {}}


class SaveManager:
    """
    Handles persistence of player profiles (multi-slot) and application settings.

    All methods return a dict.  On read failure, defaults are returned and
    a warning is logged — the game never crashes due to a missing save file.
    """

    def __init__(self) -> None:
        os.makedirs(SAVES_DIR, exist_ok=True)
        os.makedirs(PROFILES_DIR, exist_ok=True)
        self._migrate_legacy()
        idx = self.load_profiles_index()
        self._active_slot: int = int(idx.get("active_slot", 0))
        log.info(
            "SaveManager initialized. Save dir: %s  Active slot: %d",
            SAVES_DIR,
            self._active_slot,
        )

    # ------------------------------------------------------------------
    # Active slot
    # ------------------------------------------------------------------

    @property
    def active_slot(self) -> int:
        """Currently loaded profile slot (0-based)."""
        return self._active_slot

    def set_active_profile(self, slot: int) -> None:
        """Switch active slot and persist the choice to the profiles index."""
        self._active_slot = slot
        idx = self.load_profiles_index()
        idx["active_slot"] = slot
        self.save_profiles_index(idx)
        log.info("Active profile set to slot %d", slot)

    # ------------------------------------------------------------------
    # Profiles index
    # ------------------------------------------------------------------

    def load_profiles_index(self) -> dict:
        """Load the profiles index.  Returns defaults if missing or corrupt."""
        return self._load_json(PROFILES_INDEX_FILE, _DEFAULT_INDEX, "profiles index")

    def save_profiles_index(self, data: dict) -> bool:
        """Persist the profiles index.  Returns True on success."""
        return self._save_json(PROFILES_INDEX_FILE, data, "profiles index")

    # ------------------------------------------------------------------
    # Player Profile (per-slot)
    # ------------------------------------------------------------------

    def load_profile(self) -> dict:
        """Load the active slot's profile.  Returns defaults if missing or corrupt."""
        return self._load_json(
            self._profile_path(self._active_slot),
            DEFAULT_PROFILE,
            f"profile slot {self._active_slot}",
        )

    def save_profile(self, data: dict) -> bool:
        """Persist the active slot's profile.  Returns True on success."""
        return self._save_json(
            self._profile_path(self._active_slot),
            data,
            f"profile slot {self._active_slot}",
        )

    def delete_profile(self, slot: int) -> bool:
        """
        Delete a profile slot's save file and remove it from the index.
        Returns True on success.
        """
        path = self._profile_path(slot)
        try:
            if os.path.exists(path):
                os.remove(path)
            idx = self.load_profiles_index()
            profiles = idx.get("profiles", {})
            profiles.pop(str(slot), None)
            idx["profiles"] = profiles
            self.save_profiles_index(idx)
            log.info("Deleted profile slot %d", slot)
            return True
        except OSError:
            log.error(
                "Failed to delete profile slot %d.\n%s", slot, traceback.format_exc()
            )
            return False

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def load_settings(self) -> dict:
        """Load application settings.  Returns defaults if missing or corrupt."""
        return self._load_json(SETTINGS_FILE, DEFAULT_SETTINGS, "settings")

    def save_settings(self, data: dict) -> bool:
        """Persist application settings.  Returns True on success."""
        return self._save_json(SETTINGS_FILE, data, "settings")

    # ------------------------------------------------------------------
    # Migration (v0.13.5)
    # ------------------------------------------------------------------

    def _migrate_legacy(self) -> None:
        """
        If saves/player_profile.json (pre-v0.13.5) exists and slot 0 is empty,
        copy it into saves/profiles/profile_0.json automatically.
        """
        dest = self._profile_path(0)
        if not os.path.exists(_LEGACY_PROFILE_FILE):
            return
        if os.path.exists(dest):
            return
        try:
            with open(_LEGACY_PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            # Register slot 0 in the index
            idx = self._load_json(PROFILES_INDEX_FILE, _DEFAULT_INDEX, "profiles index")
            idx.setdefault("profiles", {}).setdefault(
                "0", {"name": "Player 1", "slot": 0}
            )
            self._save_json(PROFILES_INDEX_FILE, idx, "profiles index")
            log.info(
                "Migrated legacy profile %s → %s", _LEGACY_PROFILE_FILE, dest
            )
        except (OSError, json.JSONDecodeError):
            log.warning(
                "Legacy profile migration failed.\n%s", traceback.format_exc()
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _profile_path(self, slot: int) -> str:
        return os.path.join(PROFILES_DIR, f"profile_{slot}.json")

    def _load_json(self, path: str, defaults: dict, label: str) -> dict:
        if not os.path.exists(path):
            log.info("%s file not found at %s — using defaults.", label.capitalize(), path)
            return dict(defaults)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            log.debug("Loaded %s from %s", label, path)
            return data
        except (json.JSONDecodeError, OSError):
            log.warning(
                "Failed to load %s from %s — using defaults.\n%s",
                label,
                path,
                traceback.format_exc(),
            )
            return dict(defaults)

    def _save_json(self, path: str, data: Any, label: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            log.debug("Saved %s to %s", label, path)
            return True
        except OSError:
            log.error(
                "Failed to save %s to %s.\n%s",
                label,
                path,
                traceback.format_exc(),
            )
            return False
