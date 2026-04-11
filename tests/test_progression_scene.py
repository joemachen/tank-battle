"""
tests/test_progression_scene.py

Tests for v0.37 ProgressionScene data layer and constants.

No pygame required — all tests target the pure-data helpers and constant
values. The _build_unlock_rows() helper and XP bar math are exercised
directly against the real YAML data files.
"""

import unittest

from game.scenes.progression_scene import _build_unlock_rows
from game.systems.progression_manager import ProgressionManager
from game.utils.config_loader import load_yaml
from game.utils.constants import (
    SCENE_PROGRESSION,
    TANKS_CONFIG,
    WEAPON_CATEGORIES,
    WEAPONS_CONFIG,
    XP_TABLE_CONFIG,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _get_rows() -> list[dict]:
    """Build rows from real YAML data (cached pattern used by each test)."""
    progression = ProgressionManager()
    weapons_cfg = load_yaml(WEAPONS_CONFIG) or {}
    tanks_cfg = load_yaml(TANKS_CONFIG) or {}
    return _build_unlock_rows(progression, weapons_cfg, tanks_cfg)


class TestBuildUnlockRows(unittest.TestCase):
    """Tests for the _build_unlock_rows() module-level helper."""

    def setUp(self) -> None:
        self.rows = _get_rows()

    def test_rows_sorted_by_level(self) -> None:
        levels = [r["level"] for r in self.rows]
        self.assertEqual(levels, sorted(levels), "Rows must be sorted by level ascending")

    def test_standard_shell_is_first(self) -> None:
        self.assertTrue(len(self.rows) > 0, "Row list must not be empty")
        first = self.rows[0]
        self.assertEqual(first["item_id"], "standard_shell")
        self.assertEqual(first["level"], 1)

    def test_all_xp_table_unlocks_present(self) -> None:
        xp_table = load_yaml(XP_TABLE_CONFIG) or {}
        expected_ids: set[str] = {"standard_shell"}
        for entry in xp_table.get("levels", []):
            for item_id in entry.get("unlocks", []):
                expected_ids.add(item_id)

        actual_ids = {r["item_id"] for r in self.rows}
        missing = expected_ids - actual_ids
        self.assertFalse(missing, f"These items from xp_table.yaml are missing: {missing}")

    def test_row_has_required_keys(self) -> None:
        required = {"level", "item_id", "display_name", "item_type", "category"}
        for row in self.rows:
            with self.subTest(item_id=row.get("item_id")):
                self.assertEqual(required, required & row.keys())

    def test_tank_rows_have_tank_category(self) -> None:
        tank_rows = [r for r in self.rows if r["item_id"].endswith("_tank")]
        self.assertTrue(len(tank_rows) > 0, "Expected at least one tank row")
        for row in tank_rows:
            with self.subTest(item_id=row["item_id"]):
                self.assertEqual(row["item_type"], "tank")
                self.assertEqual(row["category"], "tank")

    def test_weapon_rows_have_weapon_category(self) -> None:
        weapon_rows = [r for r in self.rows if r["item_type"] == "weapon"]
        self.assertTrue(len(weapon_rows) > 0, "Expected at least one weapon row")
        for row in weapon_rows:
            with self.subTest(item_id=row["item_id"]):
                self.assertIn(
                    row["category"],
                    WEAPON_CATEGORIES,
                    f"{row['item_id']} has unexpected category '{row['category']}'",
                )


class TestXPBarMath(unittest.TestCase):
    """Tests for the XP bar fill ratio calculation logic."""

    def _compute_fill_ratio(self, current_xp: int, current_level: int):
        """Replicate the fill ratio math from ProgressionScene.on_enter()."""
        progression = ProgressionManager()
        xp_this_level = progression.xp_for_level(current_level)
        next_xp = progression.next_level_xp(current_xp)
        at_max_level = next_xp is None
        xp_next_level = next_xp if next_xp is not None else current_xp

        if at_max_level:
            return 1.0, at_max_level
        span = xp_next_level - xp_this_level
        if span > 0:
            ratio = (current_xp - xp_this_level) / span
        else:
            ratio = 0.0
        return max(0.0, min(1.0, ratio)), at_max_level

    def test_fill_ratio_mid_level(self) -> None:
        # Level 3 requires 350 XP; level 4 requires 700 XP.
        # Midpoint = 525 XP → ratio should be ≈ 0.5
        ratio, at_max = self._compute_fill_ratio(current_xp=525, current_level=3)
        self.assertFalse(at_max)
        self.assertAlmostEqual(ratio, 0.5, places=2)

    def test_fill_ratio_at_level_start(self) -> None:
        # Exactly at the threshold for level 3 (350 XP) → ratio = 0.0
        ratio, at_max = self._compute_fill_ratio(current_xp=350, current_level=3)
        self.assertFalse(at_max)
        self.assertAlmostEqual(ratio, 0.0, places=5)

    def test_fill_ratio_max_level(self) -> None:
        # Level 21 is the max (73 000 XP required); next_level_xp returns None
        progression = ProgressionManager()
        next_xp = progression.next_level_xp(73_000)
        self.assertIsNone(next_xp, "Expected None at max level")
        ratio, at_max = self._compute_fill_ratio(current_xp=73_000, current_level=21)
        self.assertTrue(at_max)
        self.assertAlmostEqual(ratio, 1.0, places=5)


class TestProgressionSceneConstants(unittest.TestCase):
    """Tests for the new SCENE_PROGRESSION constant and menu integration."""

    def test_scene_progression_constant_exists(self) -> None:
        self.assertEqual(SCENE_PROGRESSION, "progression")

    def test_menu_items_include_progression(self) -> None:
        # Import the module-level list directly to verify wiring
        from game.scenes.menu_scene import _ITEMS  # noqa: PLC0415
        self.assertIn("PROGRESSION", _ITEMS)


if __name__ == "__main__":
    unittest.main()
