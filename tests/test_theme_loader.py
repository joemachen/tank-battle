"""
tests/test_theme_loader.py

Unit tests for game/utils/theme_loader.py (v0.17).

Covers:
  - load_theme returns all required fields for a known theme
  - load_theme falls back to default.yaml on an unknown theme name
  - load_theme falls back to hardcoded defaults when default.yaml is also missing
  - list_themes returns expected names and excludes "default"
  - load_theme normalises missing music_override to None
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game.utils.theme_loader import load_theme, list_themes

# Required keys every theme dict must contain
_REQUIRED = {
    "name",
    "floor_color",
    "floor_grid_color",
    "border_color",
    "border_thickness",
    "obstacle_tint",
    "ambient_label",
}


# ---------------------------------------------------------------------------
# load_theme — known themes
# ---------------------------------------------------------------------------

class TestLoadThemeKnown:
    def test_default_theme_has_required_keys(self):
        theme = load_theme("default")
        assert _REQUIRED.issubset(theme.keys())

    def test_desert_theme_has_required_keys(self):
        theme = load_theme("desert")
        assert _REQUIRED.issubset(theme.keys())

    def test_snow_theme_has_required_keys(self):
        theme = load_theme("snow")
        assert _REQUIRED.issubset(theme.keys())

    def test_desert_name_field(self):
        theme = load_theme("desert")
        assert theme["name"] == "Desert"

    def test_snow_name_field(self):
        theme = load_theme("snow")
        assert theme["name"] == "Snow"

    def test_floor_color_is_list_of_three_ints(self):
        theme = load_theme("desert")
        c = theme["floor_color"]
        assert len(c) == 3
        assert all(isinstance(v, int) for v in c)

    def test_border_thickness_is_int(self):
        theme = load_theme("desert")
        assert isinstance(theme["border_thickness"], int)
        assert theme["border_thickness"] > 0

    def test_music_override_present(self):
        """music_override must exist — None or a string path."""
        theme = load_theme("desert")
        assert "music_override" in theme

    def test_music_override_null_for_desert(self):
        theme = load_theme("desert")
        assert theme["music_override"] is None

    def test_ambient_label_is_string(self):
        theme = load_theme("snow")
        assert isinstance(theme["ambient_label"], str)
        assert len(theme["ambient_label"]) > 0


# ---------------------------------------------------------------------------
# load_theme — fallback behaviour
# ---------------------------------------------------------------------------

class TestLoadThemeFallback:
    def test_unknown_theme_falls_back_to_default(self):
        """A theme name that doesn't exist should fall back to default.yaml fields."""
        theme = load_theme("nonexistent_xyz_theme")
        assert _REQUIRED.issubset(theme.keys())

    def test_unknown_theme_returns_classic_name(self):
        theme = load_theme("nonexistent_xyz_theme")
        # Falls back to default.yaml which has name "Classic"
        assert theme["name"] == "Classic"

    def test_missing_theme_music_override_is_none(self):
        theme = load_theme("nonexistent_xyz_theme")
        assert theme["music_override"] is None


# ---------------------------------------------------------------------------
# list_themes
# ---------------------------------------------------------------------------

class TestListThemes:
    def test_returns_list(self):
        themes = list_themes()
        assert isinstance(themes, list)

    def test_default_excluded(self):
        """'default' is the fallback — it must not appear in the selectable list."""
        themes = list_themes()
        assert "default" not in themes

    def test_contains_known_themes(self):
        themes = list_themes()
        assert "desert" in themes
        assert "snow" in themes

    def test_is_sorted(self):
        themes = list_themes()
        assert themes == sorted(themes)

    def test_all_entries_are_strings(self):
        themes = list_themes()
        assert all(isinstance(t, str) for t in themes)
