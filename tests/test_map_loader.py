"""
tests/test_map_loader.py

Unit tests for game/utils/map_loader.py (v0.17 extended).

Covers:
  - load_map returns a dict with obstacles, theme, and name keys
  - load_map loads real map files (map_01, map_02, map_03)
  - Theme dict inside map data has required theme keys
  - map_01 uses default theme, map_02 uses desert, map_03 uses snow
  - Missing map file returns empty obstacles and falls back to default theme
  - Map yaml without a theme field falls back to default theme
  - Map yaml without a name field falls back to stem-derived name
  - Obstacle objects have correct geometry from the yaml
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game.utils.map_loader import load_map

# Required keys the returned dict must always contain
_MAP_KEYS = {"obstacles", "theme", "name", "pickup_spawns"}

# Required theme keys every theme dict must contain
_THEME_KEYS = {
    "name", "floor_color", "floor_grid_color",
    "border_color", "border_thickness", "obstacle_tint", "ambient_label",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _real_map_path(stem: str) -> str:
    return os.path.join("data", "maps", f"{stem}.yaml")


# ---------------------------------------------------------------------------
# Return-shape tests
# ---------------------------------------------------------------------------

class TestLoadMapReturnShape:
    def test_returns_dict(self):
        result = load_map(_real_map_path("map_01"))
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = load_map(_real_map_path("map_01"))
        assert _MAP_KEYS.issubset(result.keys())

    def test_obstacles_is_list(self):
        result = load_map(_real_map_path("map_01"))
        assert isinstance(result["obstacles"], list)

    def test_theme_is_dict(self):
        result = load_map(_real_map_path("map_01"))
        assert isinstance(result["theme"], dict)

    def test_theme_has_required_keys(self):
        result = load_map(_real_map_path("map_01"))
        assert _THEME_KEYS.issubset(result["theme"].keys())

    def test_name_is_string(self):
        result = load_map(_real_map_path("map_01"))
        assert isinstance(result["name"], str)
        assert len(result["name"]) > 0


# ---------------------------------------------------------------------------
# map_01 — Headquarters / default theme
# ---------------------------------------------------------------------------

class TestMap01:
    def test_obstacle_count(self):
        result = load_map(_real_map_path("map_01"))
        assert len(result["obstacles"]) == 8

    def test_theme_name_is_classic(self):
        result = load_map(_real_map_path("map_01"))
        assert result["theme"]["name"] == "Classic"

    def test_map_display_name(self):
        result = load_map(_real_map_path("map_01"))
        assert result["name"] == "Headquarters"


# ---------------------------------------------------------------------------
# map_02 — Dunes / desert theme
# ---------------------------------------------------------------------------

class TestMap02:
    def test_obstacle_count(self):
        result = load_map(_real_map_path("map_02"))
        assert len(result["obstacles"]) == 7

    def test_theme_name_is_desert(self):
        result = load_map(_real_map_path("map_02"))
        assert result["theme"]["name"] == "Desert"

    def test_map_display_name(self):
        result = load_map(_real_map_path("map_02"))
        assert result["name"] == "Dunes"

    def test_floor_color_is_warm(self):
        """Desert floor should have a higher red channel than green/blue."""
        c = result = load_map(_real_map_path("map_02"))["theme"]["floor_color"]
        assert c[0] > c[2]  # more red than blue = warm


# ---------------------------------------------------------------------------
# map_03 — Tundra / snow theme
# ---------------------------------------------------------------------------

class TestMap03:
    def test_obstacle_count(self):
        result = load_map(_real_map_path("map_03"))
        assert len(result["obstacles"]) == 12

    def test_theme_name_is_snow(self):
        result = load_map(_real_map_path("map_03"))
        assert result["theme"]["name"] == "Snow"

    def test_map_display_name(self):
        result = load_map(_real_map_path("map_03"))
        assert result["name"] == "Tundra"

    def test_floor_color_is_cool(self):
        """Snow floor should have a high blue channel."""
        c = load_map(_real_map_path("map_03"))["theme"]["floor_color"]
        assert c[2] > 200  # very blue


# ---------------------------------------------------------------------------
# Obstacle geometry spot-checks
# ---------------------------------------------------------------------------

class TestObstacleGeometry:
    def test_obstacle_has_position(self):
        obs = load_map(_real_map_path("map_01"))["obstacles"][0]
        assert hasattr(obs, "x") and hasattr(obs, "y")

    def test_obstacle_has_dimensions(self):
        obs = load_map(_real_map_path("map_01"))["obstacles"][0]
        assert hasattr(obs, "width") and hasattr(obs, "height")
        assert obs.width > 0
        assert obs.height > 0

    def test_obstacle_has_material_type(self):
        obs = load_map(_real_map_path("map_01"))["obstacles"][0]
        assert hasattr(obs, "material_type")
        assert isinstance(obs.material_type, str)


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------

class TestLoadMapFallback:
    def test_missing_file_returns_empty_obstacles(self):
        result = load_map("data/maps/does_not_exist.yaml")
        assert result["obstacles"] == []

    def test_missing_file_has_theme(self):
        result = load_map("data/maps/does_not_exist.yaml")
        assert _THEME_KEYS.issubset(result["theme"].keys())

    def test_missing_file_has_name(self):
        result = load_map("data/maps/does_not_exist.yaml")
        assert isinstance(result["name"], str)

    def test_yaml_without_theme_falls_back_to_default(self):
        """A map yaml missing a theme field should resolve to the Classic (default) theme."""
        yaml_content = "name: 'NoThemeMap'\nobstacles: []\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, dir="data/maps"
        ) as f:
            f.write(yaml_content)
            path = f.name
        try:
            result = load_map(path)
            assert result["theme"]["name"] == "Classic"
            assert result["name"] == "NoThemeMap"
        finally:
            os.unlink(path)

    def test_yaml_without_name_uses_stem(self):
        """A map yaml missing a name field should fall back to the file stem."""
        yaml_content = "theme: default\nobstacles: []\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, dir="data/maps",
            prefix="stemtest_"
        ) as f:
            f.write(yaml_content)
            path = f.name
            stem = os.path.splitext(os.path.basename(path))[0]
        try:
            result = load_map(path)
            expected = stem.replace("_", " ").title()
            assert result["name"] == expected
        finally:
            os.unlink(path)
