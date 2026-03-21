"""
game/entities/tank.py

Tank entity. Fully controller-agnostic — has zero awareness of whether it is
driven by a human (InputHandler) or an AI (AIController).

A controller is injected at instantiation and must implement:
    get_input() -> TankInput

v0.16 additions:
  - TankInput.cycle_weapon: int — intent to cycle weapon slots
  - Tank weapon-slot system: up to MAX_WEAPON_SLOTS weapons, each with its own
    cooldown so switching mid-combat never resets a partially-cooled weapon.
  - fire event is now a 5-tuple: ("fire", x, y, turret_angle, weapon_type)
"""

from dataclasses import dataclass, field
from typing import Protocol

from game.utils.constants import (
    DEFAULT_FIRE_RATE,
    DEFAULT_TANK_HEALTH,
    DEFAULT_TANK_SPEED,
    DEFAULT_TANK_TURN_RATE,
    DEFAULT_WEAPON_TYPE,
    MAX_WEAPON_SLOTS,
)
from game.utils.logger import get_logger
from game.utils.math_utils import clamp, heading_to_vec

log = get_logger(__name__)


@dataclass
class TankInput:
    """
    Normalized control intent produced by any controller.
    Values are in [-1, 1] for axes; booleans for discrete actions.
    turret_angle is set by the controller each frame — the tank applies it
    directly so the controller fully owns where the gun is pointing.
    cycle_weapon is +1 (next slot), -1 (previous slot), or 0 (no change).
    """
    throttle: float = 0.0       # -1 = full reverse, +1 = full forward
    rotate: float = 0.0         # -1 = rotate left, +1 = rotate right
    fire: bool = False
    turret_angle: float = 0.0   # desired turret facing (degrees, pygame CW convention)
    cycle_weapon: int = 0       # +1 = next slot, -1 = prev slot, 0 = no change (v0.16)


class ControllerProtocol(Protocol):
    """Interface that all tank controllers must satisfy."""

    def get_input(self) -> TankInput:
        """Return the current control intent for one frame."""
        ...


class Tank:
    """
    Represents a tank entity.

    Config (from tanks.yaml) is passed as a dict at construction.
    The controller is assigned externally and can be swapped at runtime.

    Weapon slots (v0.16):
      After construction the tank has one default slot. Call load_weapons()
      to equip up to MAX_WEAPON_SLOTS weapons. Each slot keeps its own
      cooldown; switching slots mid-combat preserves cooldown state.
    """

    def __init__(
        self,
        x: float,
        y: float,
        config: dict,
        controller: ControllerProtocol,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.angle: float = 0.0          # hull facing angle in degrees (0 = right)
        self.turret_angle: float = 0.0   # turret/gun facing — independent of hull
        self.controller = controller

        # Stats from config — fall back to defaults if key missing
        self.speed: float = float(config.get("speed", DEFAULT_TANK_SPEED))
        self.max_health: int = int(config.get("health", DEFAULT_TANK_HEALTH))
        self.health: int = self.max_health
        self.turn_rate: float = float(config.get("turn_rate", DEFAULT_TANK_TURN_RATE))
        self.fire_rate: float = float(config.get("fire_rate", DEFAULT_FIRE_RATE))

        self.is_alive: bool = True
        self.tank_type: str = config.get("type", "unknown")

        # World-space velocity vector (pixels/second).
        # Computed at the end of update() from the movement delta this frame.
        self.vx: float = 0.0
        self.vy: float = 0.0

        # Weapon slot system (v0.16) ----------------------------------------
        # Default single slot — replaced when load_weapons() is called.
        self._weapon_slots: list[dict] = [
            {"type": DEFAULT_WEAPON_TYPE, "fire_rate": self.fire_rate}
        ]
        self._active_slot: int = 0
        # Per-slot cooldown timers (seconds remaining until each weapon can fire)
        self._slot_cooldowns: list[float] = [0.0]

        # Status effects (v0.19) — {name: {value, timer}}
        self._status_effects: dict = {}

        log.debug(
            "Tank created at (%.0f, %.0f) type=%s hp=%d spd=%.0f",
            x, y, self.tank_type, self.max_health, self.speed,
        )

    # ------------------------------------------------------------------
    # Weapon slot management (v0.16)
    # ------------------------------------------------------------------

    def load_weapons(self, configs: list[dict]) -> None:
        """
        Equip this tank with up to MAX_WEAPON_SLOTS weapons.

        Args:
            configs: List of weapon config dicts (from weapons.yaml).
                     Must have at least 1 entry and at most MAX_WEAPON_SLOTS.
                     Duplicate weapon types are rejected.

        Raises:
            ValueError: if configs is empty, exceeds MAX_WEAPON_SLOTS, or
                        contains duplicate weapon types.
        """
        if not configs:
            raise ValueError("load_weapons: at least one weapon config is required")
        if len(configs) > MAX_WEAPON_SLOTS:
            raise ValueError(
                f"load_weapons: max {MAX_WEAPON_SLOTS} slots, got {len(configs)}"
            )
        # Reject duplicates
        seen: set[str] = set()
        for cfg in configs:
            wtype = cfg.get("type", "")
            if wtype in seen:
                raise ValueError(
                    f"load_weapons: duplicate weapon type '{wtype}'"
                )
            seen.add(wtype)

        self._weapon_slots = list(configs)
        self._active_slot = 0
        self._slot_cooldowns = [0.0] * len(configs)
        # Sync fire_rate to active weapon for legacy compatibility
        self.fire_rate = float(self._weapon_slots[0].get("fire_rate", self.fire_rate))
        log.debug(
            "Tank loaded %d weapon(s): %s",
            len(configs), [c.get("type") for c in configs],
        )

    def cycle_weapon(self, direction: int) -> None:
        """
        Cycle to the next (+1) or previous (-1) weapon slot (wraps around).
        No-op when only one slot is loaded.
        """
        if len(self._weapon_slots) <= 1:
            return
        self._active_slot = (self._active_slot + direction) % len(self._weapon_slots)
        log.debug(
            "Tank weapon slot → %d (%s)",
            self._active_slot,
            self._weapon_slots[self._active_slot].get("type"),
        )

    def set_active_slot(self, index: int) -> None:
        """
        Jump directly to a specific weapon slot by zero-based index.
        No-op (and no exception) if index is out of range — handles tanks
        that carry fewer slots than the key binding assumes.
        Does NOT reset the target slot's cooldown.
        """
        if 0 <= index < len(self._weapon_slots):
            self._active_slot = index
            log.debug(
                "Tank weapon slot set to %d (%s)",
                index, self._weapon_slots[index].get("type"),
            )

    # ------------------------------------------------------------------
    # Weapon slot properties
    # ------------------------------------------------------------------

    @property
    def active_weapon(self) -> dict:
        """Config dict of the currently active weapon slot."""
        return self._weapon_slots[self._active_slot]

    @property
    def active_slot(self) -> int:
        """Index of the currently active weapon slot."""
        return self._active_slot

    @property
    def weapon_slots(self) -> list:
        """Shallow copy of the weapon slot config list."""
        return list(self._weapon_slots)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> list:
        """
        Advance tank state by dt seconds. Returns a list of events
        (e.g., [("fire", x, y, turret_angle, weapon_type)]) for systems to consume.

        Caller is responsible for collision response after this call.
        """
        if not self.is_alive:
            return []

        self.tick_status_effects(dt)

        events = []
        intent = self.controller.get_input()

        # Turret tracks whatever the controller requests (instant snap)
        self.turret_angle = intent.turret_angle

        # Weapon cycling
        if intent.cycle_weapon != 0:
            self.cycle_weapon(intent.cycle_weapon)

        # Hull rotation
        self.angle += intent.rotate * self.turn_rate * dt

        # Movement along facing direction
        prev_x, prev_y = self.x, self.y
        dx, dy = heading_to_vec(self.angle)
        effective_speed = self.speed
        if self.has_status("speed_boost"):
            effective_speed *= self._status_effects["speed_boost"]["value"]
        self.x += dx * intent.throttle * effective_speed * dt
        self.y += dy * intent.throttle * effective_speed * dt

        # Velocity (world-space px/s) — used by CollisionSystem for damage scaling
        if dt > 0:
            self.vx = (self.x - prev_x) / dt
            self.vy = (self.y - prev_y) / dt

        # Tick ALL slot cooldowns every frame (preserves state across slot switches)
        for i in range(len(self._slot_cooldowns)):
            if self._slot_cooldowns[i] > 0:
                self._slot_cooldowns[i] -= dt

        # Fire — uses active slot's cooldown and config
        active_wep = self.active_weapon
        active_fire_rate = float(active_wep.get("fire_rate", self.fire_rate))

        if intent.fire and self._slot_cooldowns[self._active_slot] <= 0:
            self._slot_cooldowns[self._active_slot] = 1.0 / active_fire_rate
            weapon_type = active_wep.get("type", DEFAULT_WEAPON_TYPE)
            events.append(("fire", self.x, self.y, self.turret_angle, weapon_type))
            log.debug(
                "Tank fired weapon=%s at turret_angle %.1f", weapon_type, self.turret_angle
            )

        return events

    # ------------------------------------------------------------------
    # Status effects (v0.19)
    # ------------------------------------------------------------------

    def apply_status(self, name: str, value: float, duration: float) -> None:
        """Apply or refresh a named status effect."""
        self._status_effects[name] = {"value": value, "timer": duration}
        log.debug("Status applied: %s value=%.1f duration=%.1f", name, value, duration)

    def tick_status_effects(self, dt: float) -> None:
        """Decrement all status timers and remove expired effects."""
        expired = []
        for name, data in self._status_effects.items():
            data["timer"] -= dt
            if data["timer"] <= 0:
                expired.append(name)
        for name in expired:
            del self._status_effects[name]
            log.debug("Status expired: %s", name)

    def has_status(self, name: str) -> bool:
        """Check whether a named status effect is currently active."""
        return name in self._status_effects

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------

    def take_damage(self, amount: int) -> None:
        """Apply damage. Sets is_alive=False when health reaches 0."""
        if not self.is_alive:
            return
        self.health = clamp(self.health - amount, 0, self.max_health)
        log.debug("Tank took %d damage, hp=%d/%d", amount, self.health, self.max_health)
        if self.health <= 0:
            self.is_alive = False
            log.info("Tank destroyed (type=%s)", self.tank_type)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def position(self) -> tuple:
        return (self.x, self.y)

    @property
    def health_ratio(self) -> float:
        return self.health / self.max_health if self.max_health > 0 else 0.0
