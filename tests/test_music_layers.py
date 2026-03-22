"""
tests/test_music_layers.py

Unit tests for the per-pickup music layer system.
"""

import pytest

from game.entities.tank import Tank, TankInput
from game.utils import constants


class _DummyController:
    def get_input(self) -> TankInput:
        return TankInput()


def _make_tank(hp: int = 100) -> Tank:
    config = {"speed": 150, "health": hp, "turn_rate": 120, "fire_rate": 1.0, "type": "test"}
    return Tank(400.0, 300.0, config, _DummyController())


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestMusicLayerConstants:
    def test_all_pickup_types_have_layer_paths(self):
        for key, path in constants.PICKUP_MUSIC_LAYERS.items():
            assert isinstance(path, str) and len(path) > 0, (
                f"PICKUP_MUSIC_LAYERS['{key}'] should be a non-empty string"
            )

    def test_layer_paths_are_distinct(self):
        paths = list(constants.PICKUP_MUSIC_LAYERS.values())
        assert len(paths) == len(set(paths)), "Layer paths must be unique"

    def test_no_intensity_constants_remain(self):
        assert not hasattr(constants, "MUSIC_GAMEPLAY_INTENSE"), (
            "MUSIC_GAMEPLAY_INTENSE should have been removed"
        )

    def test_layer_volume_scale_is_full(self):
        from game.ui.audio_manager import _LAYER_VOLUME_SCALE
        assert _LAYER_VOLUME_SCALE == 1.0, (
            "Layers should play at full music volume; mix via generator amplitude"
        )


# ---------------------------------------------------------------------------
# AudioManager layers (unit-level, no pygame mixer)
# ---------------------------------------------------------------------------

class TestAudioManagerLayers:
    """Test layer tracking logic. AudioManager._initialized is False
    so no actual pygame calls happen, but the dict bookkeeping is tested."""

    def _make_manager(self):
        from game.ui.audio_manager import AudioManager
        mgr = AudioManager.__new__(AudioManager)
        mgr._initialized = False
        mgr._sfx_cache = {}
        mgr._master = 1.0
        mgr._music_vol = 1.0
        mgr._sfx_vol = 1.0
        mgr._current_music = None
        mgr._layer_cache = {}
        mgr._active_layers = {}
        mgr._layer_channels = {}
        return mgr

    def test_start_layer_noop_when_uninitialised(self):
        mgr = self._make_manager()
        mgr.start_music_layer("speed_boost", "fake.wav")
        # With _initialized=False, nothing gets tracked
        assert "speed_boost" not in mgr._active_layers

    def test_stop_nonexistent_layer_no_crash(self):
        mgr = self._make_manager()
        mgr.stop_music_layer("nonexistent")  # should not raise

    def test_stop_all_layers_clears_all(self):
        mgr = self._make_manager()
        mgr._initialized = True  # enable so stop_music_layer processes
        # Manually populate active layers to simulate running state
        mgr._active_layers = {"a": None, "b": None, "c": None}
        mgr._layer_channels = {"a": None, "b": None, "c": None}
        mgr.stop_all_layers()
        assert len(mgr._active_layers) == 0
        assert len(mgr._layer_channels) == 0

    def test_duplicate_start_dict_unchanged(self):
        mgr = self._make_manager()
        # Manually add one layer
        mgr._active_layers["speed_boost"] = "placeholder"
        mgr._layer_channels["speed_boost"] = None
        # start should no-op because name already in _active_layers
        # (even with _initialized=False it hits the early return first)
        mgr._initialized = True  # enable to hit the 'already playing' check
        mgr.start_music_layer("speed_boost", "fake.wav")
        assert mgr._active_layers["speed_boost"] == "placeholder"

    def test_stop_layer_removes_from_dicts(self):
        mgr = self._make_manager()
        mgr._initialized = True  # enable so stop_music_layer processes
        mgr._active_layers["regen"] = "placeholder"
        mgr._layer_channels["regen"] = None
        mgr.stop_music_layer("regen")
        assert "regen" not in mgr._active_layers
        assert "regen" not in mgr._layer_channels


# ---------------------------------------------------------------------------
# Tank.active_status_names
# ---------------------------------------------------------------------------

class TestTankActiveStatusNames:
    def test_no_statuses_returns_empty(self):
        tank = _make_tank()
        assert tank.active_status_names == []

    def test_with_status_returns_name(self):
        tank = _make_tank()
        tank.apply_status("shield", 0.0, duration=10.0, shield_hp=60.0)
        assert "shield" in tank.active_status_names

    def test_expired_status_not_in_list(self):
        tank = _make_tank()
        tank.apply_status("regen", 5.0, duration=2.0)
        assert "regen" in tank.active_status_names
        # Tick past the duration
        tank.tick_status_effects(3.0)
        assert "regen" not in tank.active_status_names
