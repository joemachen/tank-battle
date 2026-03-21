"""
game/utils/map_loader.py

MapLoader — parses a map YAML file and returns a map data dict containing
obstacles, theme config, and map display name.

Also loads materials.yaml so each Obstacle receives the correct material
config (hp, destructible, damage_filters, color) at instantiation time.

Returns a dict with three keys:
    "obstacles" — list[Obstacle]  (may be empty on load failure)
    "theme"     — dict            (fully populated theme config, falls back to default)
    "name"      — str             (map display name, falls back to map filename stem)

Falls back gracefully on any file-level error so the game still runs
without a valid map file present.
"""

import os

import yaml

from game.entities.obstacle import Obstacle
from game.utils.constants import DEFAULT_THEME, MATERIALS_CONFIG
from game.utils.logger import get_logger
from game.utils.theme_loader import load_theme

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


def load_map(path: str) -> dict:
    """
    Parse a map YAML file and return a map data dict.

    Each obstacle entry must have: x, y, width, height, material_type.
    Optional obstacle field: reflective (default false).

    The map yaml may optionally specify:
        name:  str   — display name shown in MapSelectScene
        theme: str   — theme name key (e.g. "desert"); falls back to DEFAULT_THEME

    Args:
        path: Filesystem path to the map YAML file.

    Returns:
        dict with keys:
            "obstacles" — list[Obstacle]
            "theme"     — dict (fully populated theme config)
            "name"      — str (map display name)
    """
    materials = _load_materials()

    # Derive a fallback display name from the file stem (e.g. "map_01")
    stem = os.path.splitext(os.path.basename(path))[0]
    fallback_name = stem.replace("_", " ").title()

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        log.warning("Map file not found: '%s' — proceeding with no obstacles.", path)
        return {"obstacles": [], "theme": load_theme(DEFAULT_THEME), "name": fallback_name}
    except Exception as exc:
        log.warning("Failed to parse map file '%s': %s", path, exc)
        return {"obstacles": [], "theme": load_theme(DEFAULT_THEME), "name": fallback_name}

    # Resolve map display name
    map_name = str(data.get("name", fallback_name))

    # Resolve theme — missing or unknown theme falls back gracefully inside load_theme()
    theme_key = str(data.get("theme", DEFAULT_THEME))
    theme = load_theme(theme_key)

    # Build obstacle list
    obstacles: list[Obstacle] = []
    for entry in data.get("obstacles", []):
        try:
            # Support both "material" (new shorthand) and "material_type" (legacy)
            material_type = entry.get("material") or entry.get("material_type", "stone")
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

    # Parse pickup spawn points
    raw_spawns = data.get("pickup_spawns", [])
    pickup_spawns = []
    for s in raw_spawns:
        try:
            pickup_spawns.append((float(s["x"]), float(s["y"])))
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("Skipping malformed pickup_spawn entry %s: %s", s, exc)

    log.info("Loaded %d obstacle(s) from '%s' (theme: %s).", len(obstacles), path, theme_key)
    return {"obstacles": obstacles, "theme": theme, "name": map_name, "pickup_spawns": pickup_spawns}
