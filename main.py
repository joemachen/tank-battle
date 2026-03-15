"""
main.py — Entry point. Do not add game logic here.

Responsibilities:
  1. Configure logging
  2. Instantiate and run GameEngine
  3. Handle any top-level uncaught exceptions
"""

import sys
import traceback

from game.utils.logger import configure, get_logger

# Logging must be configured before any other import triggers a logger
configure(dev_mode=True)
log = get_logger(__name__)


def main() -> int:
    """Launch the game. Returns an exit code (0 = clean exit)."""
    try:
        from game.engine import GameEngine
        engine = GameEngine()
        engine.run()
        return 0
    except Exception:
        log.critical("Fatal error during startup:\n%s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
