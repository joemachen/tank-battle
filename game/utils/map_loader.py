"""
game/utils/map_loader.py

MapLoader — parses a map YAML file and returns a list of Obstacle instances.

Also loads materials.yaml so each Obstacle receives the correct material
config (hp, destructible, damage_filters, color) at instantiation time.

Falls back gracefully to an empty list if either file is missing or malformed,
logging a warning so the game still runs without a map file present.
"""

import yaml

from game.entities.obstacle import Obstacle
from game.utils.constants import MATERIALS_CONFIG
from game.utils.logger import get_logger

log = get_logger(__name__)


def _load_materials(path: str = MATERIALS_CONFIG) -> dict:
    """
    Load materials.yaml and return the raw dict keyed by material name.
    Returns {} on any error so callers get the Obstacle fallback material.
    """
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        log.debug("Loaded %d material(s) from '%s'.", len(data), path)
        return data
    except FileNotFoundError:
        log.warning("Materials file not found: '%s' — obstacles use fallback material.", path)
        return {}
    except Exception as exc:
        log.warning("Failed to parse materials file '%s': %s", path, exc)
        return {}


def load_map(path: str) -> list:
    """
    Parse a map YAML file and return a list of Obstacle instances.

    Each obstacle entry must have: x, y, width, height, material_type.
    Optional fields: reflective (default false).

    Material config (hp, destructible, damage_filters, color) is looked up
    from materials.yaml by material_type and injected into each Obstacle.

    Returns an empty list with a logged warning if the map file is missing,
    unreadable, or contains no valid obstacle entries.
    """
    materials = _load_materials()

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
            material_type = entry.get("material_type", "stone")
            material_config = materials.get(material_type)
            if material_config is None:
                log.warning(
                    "Unknown material_type '%s' in map '%s' — using fallback.",
                    material_type, path,
                )
            obs = Obstacle(
                x=float(entry["x"]),
                y=float(entry["y"]),
                width=float(entry["width"]),
                height=float(entry["height"]),
                material_type=material_type,
                material_config=material_config,
                reflective=bool(entry.get("reflective", False)),
            )
            obstacles.append(obs)
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("Skipping malformed obstacle entry %s: %s", entry, exc)

    log.info("Loaded %d obstacle(s) from '%s'.", len(obstacles), path)
    return obstacles
