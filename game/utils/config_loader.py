"""
game/utils/config_loader.py

Thin wrapper around PyYAML for loading data config files.
All config reads in the game go through load_yaml() so error handling
and logging are consistent everywhere.
"""

import traceback

import yaml

from game.utils.logger import get_logger

log = get_logger(__name__)


def load_yaml(path: str) -> dict:
    """
    Load and parse a YAML file. Returns an empty dict on any error.

    All callers receive a guaranteed dict — never raises.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            log.warning("YAML file is empty: %s", path)
            return {}
        log.debug("Loaded config: %s", path)
        return data
    except FileNotFoundError:
        log.error("Config file not found: %s", path)
        return {}
    except yaml.YAMLError:
        log.error("YAML parse error in %s:\n%s", path, traceback.format_exc())
        return {}
    except OSError:
        log.error("Failed to read config file %s:\n%s", path, traceback.format_exc())
        return {}


def get_tank_config(tank_type: str, tanks_path: str) -> dict:
    """
    Load tanks.yaml and return the config dict for the given tank type.
    Merges in the 'type' key so entities always have it available.
    Returns an empty dict if the type is not found.
    """
    all_tanks = load_yaml(tanks_path)
    config = all_tanks.get(tank_type, {})
    if not config:
        log.warning("Tank type '%s' not found in %s", tank_type, tanks_path)
        return {}
    config = dict(config)
    config.setdefault("type", tank_type)
    return config


def get_weapon_config(weapon_type: str, weapons_path: str) -> dict:
    """
    Load weapons.yaml and return the config dict for the given weapon type.
    """
    all_weapons = load_yaml(weapons_path)
    config = all_weapons.get(weapon_type, {})
    if not config:
        log.warning("Weapon type '%s' not found in %s", weapon_type, weapons_path)
        return {}
    config = dict(config)
    config.setdefault("type", weapon_type)
    return config


def get_ai_config(difficulty: str, ai_path: str) -> dict:
    """
    Load ai_difficulty.yaml and return the config dict for the given difficulty tier.
    """
    all_difficulties = load_yaml(ai_path)
    config = all_difficulties.get(difficulty, {})
    if not config:
        log.warning("AI difficulty '%s' not found in %s", difficulty, ai_path)
        return {}
    return dict(config)
