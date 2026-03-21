"""
tests/test_obstacles.py

Unit tests for Obstacle visual damage states: hit flash, current_color,
and damage-state darkening introduced in v0.18.
"""

import pytest

from game.entities.obstacle import Obstacle
from game.utils.constants import (
    DAMAGE_DARKEN_CRITICAL,
    DAMAGE_DARKEN_MEDIUM,
    HIT_FLASH_BLEND,
    HIT_FLASH_DURATION,
)
from game.utils.math_utils import blend_colors


# ---------------------------------------------------------------------------
# Material configs for testing
# ---------------------------------------------------------------------------

_WOOD_CFG = {
    "display_name": "Wood",
    "hp": 75,
    "destructible": True,
    "damage_filters": [],
    "color": [139, 90, 43],
}

_STONE_CFG = {
    "display_name": "Stone",
    "hp": 9999,
    "destructible": False,
    "damage_filters": [],
    "color": [90, 85, 75],
}

_BRICK_CFG = {
    "display_name": "Brick",
    "hp": 150,
    "destructible": True,
    "damage_filters": [],
    "color": [160, 75, 45],
}


def _make_obstacle(cfg, x=100, y=200, w=60, h=40):
    return Obstacle(x, y, w, h, material_type=cfg["display_name"].lower(), material_config=cfg)


# ---------------------------------------------------------------------------
# Hit flash timer
# ---------------------------------------------------------------------------


class TestHitFlash:
    def test_initial_timer_zero(self):
        obs = _make_obstacle(_WOOD_CFG)
        assert obs._hit_flash_timer == 0.0
        assert not obs.is_flashing

    def test_update_decrements_timer(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs._hit_flash_timer = 0.15
        obs.update(0.05)
        assert abs(obs._hit_flash_timer - 0.10) < 1e-9

    def test_timer_clamps_to_zero(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs._hit_flash_timer = 0.01
        obs.update(0.1)
        assert obs._hit_flash_timer == 0.0

    def test_is_flashing_true_when_timer_positive(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs._hit_flash_timer = 0.05
        assert obs.is_flashing

    def test_is_flashing_false_when_timer_zero(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs._hit_flash_timer = 0.0
        assert not obs.is_flashing

    def test_take_damage_sets_flash_on_destructible(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs.take_damage(10, "standard")
        assert obs._hit_flash_timer == HIT_FLASH_DURATION

    def test_take_damage_no_flash_on_indestructible(self):
        obs = _make_obstacle(_STONE_CFG)
        obs.take_damage(10, "standard")
        assert obs._hit_flash_timer == 0.0

    def test_update_noop_when_timer_already_zero(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs.update(0.1)
        assert obs._hit_flash_timer == 0.0


# ---------------------------------------------------------------------------
# base_color defaults
# ---------------------------------------------------------------------------


class TestBaseColor:
    def test_defaults_to_material_color(self):
        obs = _make_obstacle(_WOOD_CFG)
        assert obs.base_color == obs.color

    def test_can_be_overwritten(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs.base_color = (200, 100, 50)
        assert obs.base_color == (200, 100, 50)


# ---------------------------------------------------------------------------
# current_color
# ---------------------------------------------------------------------------


class TestCurrentColor:
    def test_full_hp_returns_base_color(self):
        obs = _make_obstacle(_WOOD_CFG)
        obs.base_color = (139, 90, 43)
        assert obs.current_color == obs.base_color

    def test_damaged_state_darkened(self):
        """hp_ratio ~0.5 → darkened by DAMAGE_DARKEN_MEDIUM."""
        obs = _make_obstacle(_BRICK_CFG)
        obs.base_color = (160, 75, 45)
        obs.hp = int(obs.max_hp * 0.5)  # hp_ratio ~0.5
        expected = blend_colors((160, 75, 45), (0, 0, 0), DAMAGE_DARKEN_MEDIUM)
        assert obs.current_color == expected

    def test_critical_state_darkened(self):
        """hp_ratio ~0.2 → darkened by DAMAGE_DARKEN_CRITICAL."""
        obs = _make_obstacle(_BRICK_CFG)
        obs.base_color = (160, 75, 45)
        obs.hp = int(obs.max_hp * 0.2)  # hp_ratio ~0.2
        expected = blend_colors((160, 75, 45), (0, 0, 0), DAMAGE_DARKEN_CRITICAL)
        assert obs.current_color == expected

    def test_flash_overrides_damage(self):
        """Flashing obstacle blends toward white on top of damage darkening."""
        obs = _make_obstacle(_WOOD_CFG)
        obs.base_color = (139, 90, 43)
        obs.hp = int(obs.max_hp * 0.5)
        obs._hit_flash_timer = 0.1
        damaged = blend_colors((139, 90, 43), (0, 0, 0), DAMAGE_DARKEN_MEDIUM)
        expected = blend_colors(damaged, (255, 255, 255), HIT_FLASH_BLEND)
        assert obs.current_color == expected

    def test_indestructible_no_darkening(self):
        """Stone (indestructible) always returns base_color regardless of HP."""
        obs = _make_obstacle(_STONE_CFG)
        obs.base_color = (90, 85, 75)
        # Even if HP were somehow low, indestructible means hp_ratio=1.0
        assert obs.current_color == obs.base_color

    def test_full_hp_no_flash_returns_exact_base(self):
        obs = _make_obstacle(_BRICK_CFG)
        obs.base_color = (160, 75, 45)
        assert obs.current_color == (160, 75, 45)
