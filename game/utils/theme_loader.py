"""
game/utils/theme_loader.py

ThemeLoader — loads environment theme configs from data/themes/*.yaml.

A theme defines the visual feel of an arena:
  - Floor color and grid line color
  - Border color and thickness
  - Obstacle tint (blended 50/50 with material base color)
  - Ambient label (short mood descriptor for the map-select UI)
  - Optional music override path (null = use default gameplay music)

Falls back to data/themes/default.yaml on any error so the game
always has valid rendering colors regardless of theme file state.
"""

import os

import yaml

from game.utils.constants import DEFAULT_THEME, THEMES_DIR
from game.utils.logger import get_logger

log = get_logger(__name__)

# Required fields every theme must provide.  Used for fallback validation.
_REQUIRED_KEYS: tuple = (
    "name",
    "floor_color",
    "floor_grid_color",
    "border_color",
    "border_thickness",
    "obstacle_tint",
    "ambient_label",
)

# Hard-coded fallback used when even default.yaml is unreadable.
_HARDCODED_DEFAULT: dict = {
    "name": "Classic",
    "floor_color": [20, 30, 20],
    "floor_grid_color": [30, 45, 30],
    "border_color": [60, 80, 60],
    "border_thickness": 4,
    "obstacle_tint": [100, 100, 100],
    "ambient_label": "Classic",
    "music_override": None,
}


def _theme_path(theme_name: str) -> str:
    return os.path.join(THEMES_DIR, f"{theme_name}.yaml")


def _load_raw(theme_name: str) -> dict | None:
    """
    Load and parse a theme YAML file.  Returns the dict on success,
    None if the file is missing or unparseable.
    """
    path = _theme_path(theme_name)
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        # Normalise music_override: absent key treated as None
        data.setdefault("music_override", None)
        return data
    except FileNotFoundError:
        log.warning("Theme file not found: '%s'", path)
        return None
    except Exception as exc:
        log.warning("Failed to parse theme '%s': %s", path, exc)
        return None


def _is_valid(data: dict) -> bool:
    return all(k in data for k in _REQUIRED_KEYS)


def load_theme(theme_name: str) -> dict:
    """
    Load a theme by name from data/themes/{theme_name}.yaml.

    Falls back to data/themes/default.yaml on any error (missing file,
    parse failure, or missing required fields).  If even default.yaml
    is unreadable, returns a hard-coded default dict so the game never
    crashes due to theme config issues.

    Args:
        theme_name: Stem of the yaml filename (e.g. "desert", "snow").

    Returns:
        Fully populated theme dict with all required keys present.
    """
    data = _load_raw(theme_name)
    if data is not None and _is_valid(data):
        log.debug("Loaded theme '%s'.", theme_name)
        return data

    # Theme was missing or invalid — fall back to default
    if theme_name != DEFAULT_THEME:
        log.warning(
            "Theme '%s' missing or invalid — falling back to '%s'.",
            theme_name, DEFAULT_THEME,
        )
    default_data = _load_raw(DEFAULT_THEME)
    if default_data is not None and _is_valid(default_data):
        return default_data

    log.warning("Default theme file unreadable — using hardcoded defaults.")
    return dict(_HARDCODED_DEFAULT)


def list_themes() -> list[str]:
    """
    Return a sorted list of available selectable theme names.

    Scans THEMES_DIR for .yaml files and returns their stems.
    Excludes "default" — it is the invisible fallback, not a player choice.

    Returns an empty list if THEMES_DIR does not exist or is unreadable.
    """
    try:
        names = [
            os.path.splitext(f)[0]
            for f in os.listdir(THEMES_DIR)
            if f.endswith(".yaml")
        ]
        names = sorted(n for n in names if n != DEFAULT_THEME)
        log.debug("Available themes: %s", names)
        return names
    except FileNotFoundError:
        log.warning("Themes directory not found: '%s'", THEMES_DIR)
        return []
    except Exception as exc:
        log.warning("Failed to list themes: %s", exc)
        return []
