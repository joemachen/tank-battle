"""
game/utils/stuck_detector.py

StuckDetector — rolling-window displacement monitor.

Tracks an entity's position over a configurable time window and reports
whether the entity is stuck (net displacement below threshold_px).

Design notes:
  - Pure logic; no pygame, no game-world dependencies.
  - Uses net displacement (oldest-to-current straight-line distance),
    not total path length, so a tank spinning in place is correctly
    detected as stuck.
  - Only fires after a full 80% of the window has elapsed so the detector
    doesn't false-positive on startup.
  - reset() is called by AIController whenever recovery begins, so the
    detector doesn't re-fire immediately after recovery ends.
"""

import math
from collections import deque

from game.utils.logger import get_logger

log = get_logger(__name__)

# Fraction of the window that must be covered before is_stuck can be True.
# Prevents false positives during the very first frames of a match.
_MIN_WINDOW_FILL = 0.8


class StuckDetector:
    """
    Reports whether a moving entity has been displaced less than
    threshold_px over the last window_seconds seconds.

    Usage:
        sd = StuckDetector(window_seconds=0.5, threshold_px=10.0)
        # each frame:
        sd.update(dt, entity.x, entity.y)
        if sd.is_stuck:
            ...trigger recovery...
            sd.reset()
    """

    def __init__(
        self,
        window_seconds: float = 0.5,
        threshold_px: float = 10.0,
    ) -> None:
        self._window = window_seconds
        self._threshold = threshold_px
        self._samples: deque = deque()   # deque of (elapsed_time, x, y)
        self._elapsed: float = 0.0
        self._is_stuck: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, dt: float, x: float, y: float) -> None:
        """
        Advance the detector by dt seconds, recording position (x, y).
        Call once per frame before reading is_stuck.
        """
        self._elapsed += dt
        self._samples.append((self._elapsed, x, y))

        # Purge samples that have aged out of the window
        cutoff = self._elapsed - self._window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

        if len(self._samples) < 2:
            self._is_stuck = False
            return

        oldest_t, ox, oy = self._samples[0]
        span = self._elapsed - oldest_t

        # Require at least _MIN_WINDOW_FILL of the window before declaring stuck
        if span < self._window * _MIN_WINDOW_FILL:
            self._is_stuck = False
            return

        displacement = math.hypot(x - ox, y - oy)
        self._is_stuck = displacement < self._threshold

    @property
    def is_stuck(self) -> bool:
        """True when the entity has moved less than threshold_px in the last window."""
        return self._is_stuck

    def reset(self) -> None:
        """Clear all history. Call when recovery starts so stuck is not re-fired instantly."""
        self._samples.clear()
        self._is_stuck = False
        log.debug("StuckDetector reset.")
