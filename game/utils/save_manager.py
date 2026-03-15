"""
game/utils/save_manager.py

All file I/O for player profiles and settings goes through this class.
No other module should read or write JSON save files directly.
"""

import json
import os
import traceback
from typing import Any

from game.utils.constants import (
    DEFAULT_PROFILE,
    DEFAULT_SETTINGS,
    PROFILE_FILE,
    SAVES_DIR,
    SETTINGS_FILE,
)
from game.utils.logger import get_logger

log = get_logger(__name__)


class SaveManager:
    """
    Handles persistence of player profile and application settings.

    All methods return a dict. On read failure, defaults are returned and
    a warning is logged — the game never crashes due to a missing save file.
    """

    def __init__(self) -> None:
        os.makedirs(SAVES_DIR, exist_ok=True)
        log.info("SaveManager initialized. Save dir: %s", SAVES_DIR)

    # ------------------------------------------------------------------
    # Player Profile
    # ------------------------------------------------------------------

    def load_profile(self) -> dict:
        """Load player profile. Returns defaults if file is missing or corrupt."""
        return self._load_json(PROFILE_FILE, DEFAULT_PROFILE, "player profile")

    def save_profile(self, data: dict) -> bool:
        """Persist player profile. Returns True on success."""
        return self._save_json(PROFILE_FILE, data, "player profile")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def load_settings(self) -> dict:
        """Load application settings. Returns defaults if file is missing or corrupt."""
        return self._load_json(SETTINGS_FILE, DEFAULT_SETTINGS, "settings")

    def save_settings(self, data: dict) -> bool:
        """Persist application settings. Returns True on success."""
        return self._save_json(SETTINGS_FILE, data, "settings")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
