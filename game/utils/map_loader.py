"""
game/utils/map_loader.py

MapLoader — parses a map YAML file and returns a list of Obstacle instances.

Falls back gracefully to an empty list if the file is missing or malformed,
logging a warning so the game still runs without a map file present.
"""

import yaml

from game.entities.obstacle import Obstacle
from game.utils.logger import get_logger

log = get_logger(__name__)


def load_map(path: str) -> list:
    """
    Parse a map YAML file and return a list of Obstacle instances.

    Expected YAML structure:
        obstacles:
          - x: 350
            y: 430
            width: 90
            height: 240
            destructible: false
            reflective: false

    Returns an empty list with a logged warning if the file is missing,
    unreadable, or contains no valid obstacle entries.
    """
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        log.warning("Map file not found: '%s' — proceeding with no obstacles.", path)
        return []
    except Exception as exc:
        log.warning("Failed to parse map file '%s': %s", path, exc)
        return []

    obstacles = []
    for entry in data.get("obstacles", []):
        try:
            obs = Obstacle(
                x=float(entry["x"]),
                y=float(entry["y"]),
                width=float(entry["width"]),
                height=float(entry["height"]),
                destructible=bool(entry.get("destructible", False)),
                reflective=bool(entry.get("reflective", False)),
            )
            obstacles.append(obs)
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("Skipping malformed obstacle entry %s: %s", entry, exc)

    log.info("Loaded %d obstacle(s) from '%s'.", len(obstacles), path)
    return obstacles
