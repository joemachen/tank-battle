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

import math
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
from game.systems.status_effect import StatusEffect
from game.utils.damage_types import DamageType
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
        # Combat status effects (v0.23) — {name: StatusEffect}
        self._combat_effects: dict[str, StatusEffect] = {}
        # Stun timer (v0.24) — when > 0, all input is suppressed
        self._stun_timer: float = 0.0
        # Knockback (v0.26) — impulse velocity, decays exponentially
        self._knockback_vx: float = 0.0
        self._knockback_vy: float = 0.0

        # Energy system (v0.25) — for hitscan weapons (laser beam)
        self._energy: float = 0.0
        self._energy_max: float = 0.0
        self._energy_drain_rate: float = 0.0
        self._energy_recharge_rate: float = 0.0
        self._energy_min_to_fire: float = 0.0
        self._is_firing_beam: bool = False
        self._beam_dps: float = 0.0

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

        # Initialize energy pool if any hitscan weapon is loaded (v0.25)
        self._energy = 0.0
        self._energy_max = 0.0
        self._energy_drain_rate = 0.0
        self._energy_recharge_rate = 0.0
        self._energy_min_to_fire = 0.0
        self._beam_dps = 0.0
        for slot in self._weapon_slots:
            if slot.get("hitscan", False):
                self._energy_max = float(slot.get("energy_max", 100.0))
                self._energy = self._energy_max  # start fully charged
                self._energy_drain_rate = float(slot.get("energy_drain_rate", 30.0))
                self._energy_recharge_rate = float(slot.get("energy_recharge_rate", 15.0))
                self._energy_min_to_fire = float(slot.get("energy_min_to_fire", 20.0))
                self._beam_dps = float(slot.get("dps", 45.0))
                break  # only one energy pool

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

    @property
    def slot_cooldowns(self) -> list[float]:
        """Current cooldown timers for all weapon slots (seconds remaining)."""
        return list(self._slot_cooldowns)

    # Energy properties (v0.25)

    @property
    def energy(self) -> float:
        """Current energy level."""
        return self._energy

    @property
    def energy_ratio(self) -> float:
        """Energy as a 0–1 fraction; 0 when no hitscan weapon equipped."""
        if self._energy_max <= 0:
            return 0.0
        return self._energy / self._energy_max

    @property
    def is_firing_beam(self) -> bool:
        """True when this tank is actively firing a hitscan beam this frame."""
        return self._is_firing_beam

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

        # Stun — suppress all input but still tick effects (v0.24)
        if self._stun_timer > 0:
            self._stun_timer -= dt
            # Tick cooldowns so weapons are ready when stun ends
            for i in range(len(self._slot_cooldowns)):
                if self._slot_cooldowns[i] > 0:
                    self._slot_cooldowns[i] -= dt
            # Tick pickup status effects
            self.tick_status_effects(dt)
            # Tick combat effects (DoT still hurts during stun)
            dot_damage = 0
            expired_combat = []
            for name, effect in self._combat_effects.items():
                dot_damage += effect.update(dt)
                if effect.is_expired:
                    expired_combat.append(name)
            for name in expired_combat:
                del self._combat_effects[name]
            if dot_damage > 0 and self.is_alive:
                self.health = max(0, self.health - dot_damage)
                if self.health <= 0:
                    self.is_alive = False
            # Zero velocity — tank is frozen in place
            self.vx = 0.0
            self.vy = 0.0
            return []

        self.tick_status_effects(dt)

        # Tick combat status effects (v0.23) — DoT, expiry
        dot_damage = 0
        expired_combat = []
        for name, effect in self._combat_effects.items():
            dot_damage += effect.update(dt)
            if effect.is_expired:
                expired_combat.append(name)
        for name in expired_combat:
            del self._combat_effects[name]
            log.debug("Combat effect expired: %s", name)
        if dot_damage > 0 and self.is_alive:
            self.health = max(0, self.health - dot_damage)
            if self.health <= 0:
                self.is_alive = False
            log.debug("DoT damage: %d — hp=%d/%d", dot_damage, self.health, self.max_health)

        if not self.is_alive:
            return []

        events = []
        intent = self.controller.get_input()

        # Turret tracks whatever the controller requests (instant snap)
        self.turret_angle = intent.turret_angle

        # Weapon cycling
        if intent.cycle_weapon != 0:
            self.cycle_weapon(intent.cycle_weapon)

        # Hull rotation — apply combat turn multiplier (v0.23)
        effective_turn = self.turn_rate * self._combat_turn_mult()
        self.angle += intent.rotate * effective_turn * dt

        # Movement along facing direction — apply combat speed multiplier (v0.23)
        prev_x, prev_y = self.x, self.y
        dx, dy = heading_to_vec(self.angle)
        effective_speed = self.speed * self._combat_speed_mult()
        if self.has_status("speed_boost"):
            effective_speed *= self._status_effects["speed_boost"]["value"]
        if self.has_status("pool_slow"):
            effective_speed *= self._status_effects["pool_slow"]["value"]
        self.x += dx * intent.throttle * effective_speed * dt
        self.y += dy * intent.throttle * effective_speed * dt

        # Knockback displacement (v0.26) — external impulse, decays exponentially
        if abs(self._knockback_vx) > 0.5 or abs(self._knockback_vy) > 0.5:
            self.x += self._knockback_vx * dt
            self.y += self._knockback_vy * dt
            decay = math.exp(-8.0 * dt)
            self._knockback_vx *= decay
            self._knockback_vy *= decay
        else:
            self._knockback_vx = 0.0
            self._knockback_vy = 0.0

        # Velocity (world-space px/s) — used by CollisionSystem for damage scaling
        if dt > 0:
            self.vx = (self.x - prev_x) / dt
            self.vy = (self.y - prev_y) / dt

        # Tick ALL slot cooldowns every frame (preserves state across slot switches)
        for i in range(len(self._slot_cooldowns)):
            if self._slot_cooldowns[i] > 0:
                self._slot_cooldowns[i] -= dt

        # Fire — split into hitscan vs. projectile branches (v0.25)
        active_wep = self.active_weapon
        is_hitscan = active_wep.get("hitscan", False)

        if is_hitscan:
            # Hitscan weapon — energy-based sustained fire
            if intent.fire and self._energy >= self._energy_min_to_fire:
                self._is_firing_beam = True
                self._energy = max(0.0, self._energy - self._energy_drain_rate * dt)
                weapon_type = active_wep.get("type", DEFAULT_WEAPON_TYPE)
                events.append(("beam", self.x, self.y, self.turret_angle, weapon_type))
                log.debug("Tank firing beam weapon=%s energy=%.1f", weapon_type, self._energy)
                if self._energy <= 0:
                    self._is_firing_beam = False  # ran out of energy
            else:
                self._is_firing_beam = False
                # Recharge when not firing
                if self._energy < self._energy_max:
                    self._energy = min(self._energy_max, self._energy + self._energy_recharge_rate * dt)
        else:
            self._is_firing_beam = False
            # Existing projectile fire logic
            active_fire_rate = float(active_wep.get("fire_rate", self.fire_rate)) * self._combat_fire_rate_mult()
            if intent.fire and self._slot_cooldowns[self._active_slot] <= 0:
                self._slot_cooldowns[self._active_slot] = 1.0 / active_fire_rate
                weapon_type = active_wep.get("type", DEFAULT_WEAPON_TYPE)
                events.append(("fire", self.x, self.y, self.turret_angle, weapon_type))
                log.debug(
                    "Tank fired weapon=%s at turret_angle %.1f", weapon_type, self.turret_angle
                )
            # Passive recharge for non-hitscan (e.g. player switches away from laser)
            if self._energy < self._energy_max and self._energy_max > 0:
                self._energy = min(self._energy_max, self._energy + self._energy_recharge_rate * dt)

        return events

    # ------------------------------------------------------------------
    # Status effects (v0.19)
    # ------------------------------------------------------------------

    def apply_status(self, name: str, value: float, duration: float, **kwargs) -> None:
        """Apply or refresh a named status effect.

        For shield: pass shield_hp=float via kwargs. The shield absorbs damage
        and expires when either its HP or timer reaches zero.
        """
        data = {"value": value, "timer": duration}
        if name == "shield" and "shield_hp" in kwargs:
            data["shield_hp"] = float(kwargs["shield_hp"])
        self._status_effects[name] = data
        log.debug("Status applied: %s value=%.1f duration=%.1f", name, value, duration)

    def tick_status_effects(self, dt: float) -> None:
        """Decrement all status timers, apply regen healing, and remove expired effects."""
        # Regen: heal each frame (accumulate fractional HP)
        if "regen" in self._status_effects:
            regen = self._status_effects["regen"]
            regen.setdefault("_accum", 0.0)
            regen["_accum"] += regen["value"] * dt
            whole = int(regen["_accum"])
            if whole > 0:
                self.health = min(self.max_health, self.health + whole)
                regen["_accum"] -= whole

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

    @property
    def status_effects(self) -> dict:
        """Read-only access to active status effects for rendering."""
        return self._status_effects

    @property
    def active_status_names(self) -> list[str]:
        """Return list of active status effect names (pickup + combat)."""
        return list(self._status_effects.keys()) + list(self._combat_effects.keys())

    # ------------------------------------------------------------------
    # Combat effects (burn, poison, ice, electric)
    # ------------------------------------------------------------------

    def apply_combat_effect(self, effect_type: str, config: dict) -> None:
        """Apply or refresh a combat status effect."""
        if effect_type in self._combat_effects:
            self._combat_effects[effect_type].refresh(config)
        else:
            self._combat_effects[effect_type] = StatusEffect(effect_type, config)

    @property
    def combat_effects(self) -> dict[str, "StatusEffect"]:
        """Shallow copy of active combat effects for external reads."""
        return dict(self._combat_effects)

    @property
    def has_any_combat_effect(self) -> bool:
        return len(self._combat_effects) > 0

    def _combat_speed_mult(self) -> float:
        m = 1.0
        for eff in self._combat_effects.values():
            m *= eff.speed_mult
        return m

    def _combat_turn_mult(self) -> float:
        m = 1.0
        for eff in self._combat_effects.values():
            m *= eff.turn_mult
        return m

    def _combat_fire_rate_mult(self) -> float:
        m = 1.0
        for eff in self._combat_effects.values():
            m *= eff.fire_rate_mult
        return m

    def remove_combat_effect(self, effect_type: str) -> None:
        """Remove a combat effect by name. No-op if not present."""
        if effect_type in self._combat_effects:
            del self._combat_effects[effect_type]
            log.debug("Combat effect removed: %s", effect_type)

    # ------------------------------------------------------------------
    # Stun (v0.24 — elemental combos)
    # ------------------------------------------------------------------

    def apply_stun(self, duration: float) -> None:
        """Stun the tank — no movement, turning, or firing for duration seconds."""
        self._stun_timer = max(self._stun_timer, duration)
        log.debug("Tank stunned for %.1fs at (%.0f, %.0f)", duration, self.x, self.y)

    def apply_knockback(self, force: float, angle_deg: float) -> None:
        """Apply an impulse that displaces the tank. Decays exponentially in update()."""
        rad = math.radians(angle_deg)
        self._knockback_vx += math.cos(rad) * force
        self._knockback_vy += math.sin(rad) * force
        log.debug("Knockback applied: force=%.0f angle=%.1f at (%.0f, %.0f)",
                  force, angle_deg, self.x, self.y)

    @property
    def is_stunned(self) -> bool:
        return self._stun_timer > 0

    @property
    def shield_hp(self) -> float:
        """Current shield hit-points, or 0.0 if no shield active."""
        if "shield" in self._status_effects:
            return self._status_effects["shield"].get("shield_hp", 0.0)
        return 0.0

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------

    def take_damage(self, amount: int, damage_type: DamageType = DamageType.STANDARD) -> None:
        """Apply damage. Shield absorbs first; remainder hits health.
        Sets is_alive=False when health reaches 0.

        Args:
            amount: raw damage points
            damage_type: DamageType enum — stored for future type-specific
                         reactions (burn, slow, etc.) but not acted on yet.
        """
        if not self.is_alive:
            return
        remaining = amount
        if "shield" in self._status_effects:
            shield = self._status_effects["shield"]
            absorbed = min(remaining, shield["shield_hp"])
            shield["shield_hp"] -= absorbed
            remaining -= int(absorbed)
            if shield["shield_hp"] <= 0:
                del self._status_effects["shield"]
                log.debug("Shield broken by damage")
        if remaining > 0:
            self.health = clamp(self.health - remaining, 0, self.max_health)
        log.debug("Tank took %d %s damage (absorbed=%d), hp=%d/%d",
                  amount, damage_type.name, amount - remaining, self.health, self.max_health)
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
