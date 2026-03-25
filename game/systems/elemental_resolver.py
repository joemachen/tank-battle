"""
game/systems/elemental_resolver.py

ElementalResolver — detects and triggers combo reactions when two matching
elemental status effects are active on the same tank.

Called once per frame from GameplayScene.update() AFTER combat effects have
been applied by CollisionSystem and BEFORE Tank.update() ticks effect
durations. This ordering ensures that a bullet applying fire to an
ice-affected tank triggers the combo the same frame.
"""

from game.utils.config_loader import load_yaml
from game.utils.constants import ELEMENTAL_INTERACTIONS_CONFIG
from game.utils.logger import get_logger

log = get_logger(__name__)


class ElementalResolver:
    """
    Scans all tanks each frame for elemental combo conditions.
    When a combo is detected:
      1. Both source effects are removed from the tank
      2. The combo result is returned as an event for the scene to process
    """

    def __init__(self) -> None:
        raw = load_yaml(ELEMENTAL_INTERACTIONS_CONFIG) or {}
        self._interactions: list[dict] = []
        for name, cfg in raw.items():
            elements = cfg.get("elements", [])
            if len(elements) == 2:
                cfg["name"] = name
                cfg["_element_set"] = frozenset(elements)
                self._interactions.append(cfg)
        log.info("ElementalResolver loaded %d interactions.", len(self._interactions))

    def resolve(self, tanks: list) -> list:
        """
        Check all tanks for active elemental combos. Returns a list of
        combo event dicts for the scene to process:

        [
            {
                "name": "steam_burst",
                "tank": <Tank>,
                "config": <interaction config dict>,
            },
            ...
        ]

        Source effects are removed from the tank immediately.
        """
        events = []
        for tank in tanks:
            if not tank.is_alive:
                continue
            active = frozenset(tank.combat_effects.keys())
            for interaction in self._interactions:
                if interaction["_element_set"].issubset(active):
                    # Remove both source effects
                    for element in interaction["elements"]:
                        tank.remove_combat_effect(element)
                    events.append({
                        "name": interaction["name"],
                        "tank": tank,
                        "config": interaction,
                    })
                    log.info(
                        "Elemental combo: %s on tank at (%.0f, %.0f)",
                        interaction["name"], tank.x, tank.y,
                    )
                    # Only one combo per tank per frame to prevent cascade
                    break
        return events
