"""
tests/test_stuck_detector.py

Unit tests for StuckDetector.
Pure logic — no pygame, no game-world dependencies.
"""

import pytest

from game.utils.stuck_detector import StuckDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fill_window(sd: StuckDetector, x: float, y: float,
                 dt: float = 0.1, steps: int = 7) -> None:
    """Drive the detector through `steps` updates at the given position."""
    for _ in range(steps):
        sd.update(dt, x, y)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStuckDetector:
    def test_not_stuck_when_moving(self):
        """
        Detector reports is_stuck=False when the entity has moved well
        beyond the displacement threshold over the window.
        """
        sd = StuckDetector(window_seconds=0.5, threshold_px=10.0)
        # Entity moves 5px per 0.1s tick → 30px over 6 ticks — clearly not stuck
        for i in range(7):
            sd.update(0.1, float(i * 5), 0.0)
        assert not sd.is_stuck

    def test_is_stuck_when_stationary(self):
        """
        Detector reports is_stuck=True when the entity has not moved
        past the displacement threshold over the full window.
        """
        sd = StuckDetector(window_seconds=0.5, threshold_px=10.0)
        # Entity stays at (100, 100) — zero displacement
        _fill_window(sd, 100.0, 100.0)
        assert sd.is_stuck

    def test_not_stuck_before_window_fills(self):
        """
        Detector must not fire before enough history has accumulated
        (prevents false positives at match start).
        """
        sd = StuckDetector(window_seconds=0.5, threshold_px=10.0)
        # Only one sample — far less than the required window fill
        sd.update(0.05, 0.0, 0.0)
        assert not sd.is_stuck

    def test_reset_clears_stuck_state(self):
        """reset() returns is_stuck to False and clears history."""
        sd = StuckDetector(window_seconds=0.5, threshold_px=10.0)
        _fill_window(sd, 0.0, 0.0)   # force stuck
        assert sd.is_stuck            # confirm it fired

        sd.reset()
        assert not sd.is_stuck

    def test_reset_prevents_immediate_re_fire(self):
        """
        After reset(), a single update at the same position must not
        immediately re-declare stuck (history was cleared).
        """
        sd = StuckDetector(window_seconds=0.5, threshold_px=10.0)
        _fill_window(sd, 0.0, 0.0)
        sd.reset()
        sd.update(0.1, 0.0, 0.0)     # one tick after reset — window not full
        assert not sd.is_stuck

    def test_small_movement_below_threshold_is_stuck(self):
        """Entity that drifts < threshold_px over the window is still considered stuck."""
        sd = StuckDetector(window_seconds=0.5, threshold_px=10.0)
        # Move only 1px total over the window — below the 10px threshold
        for i in range(7):
            sd.update(0.1, float(i) * 0.1, 0.0)   # ~0.6px total displacement
        assert sd.is_stuck
