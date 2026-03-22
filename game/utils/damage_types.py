"""
game/utils/damage_types.py

Canonical damage type enum. Every bullet, explosion, and status effect
references one of these values. Used by CollisionSystem to route damage
and by Obstacle.take_damage() to filter.
"""

from enum import Enum, auto


class DamageType(Enum):
    STANDARD = auto()   # kinetic/ballistic — all current weapons
    EXPLOSIVE = auto()  # splash damage, AoE — v0.22
    FIRE = auto()       # burn DoT — v0.23
    ICE = auto()        # movement slow — v0.23
    POISON = auto()     # damage over time (slower) — v0.23
    ELECTRIC = auto()   # fire rate slow — v0.23


def parse_damage_type(value: str) -> DamageType:
    """Convert a string from YAML config to a DamageType enum value.

    Case-insensitive. Returns STANDARD if the string is unrecognized.

    Args:
        value: string from weapons.yaml or materials.yaml
               (e.g. "standard", "explosive", "fire")

    Returns:
        DamageType enum member
    """
    try:
        return DamageType[value.upper()]
    except (KeyError, AttributeError):
        return DamageType.STANDARD
