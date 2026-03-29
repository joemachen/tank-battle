"""
game/systems/ultimate.py

UltimateCharge — tracks charge accumulation and active-ability state for
a tank's signature ultimate ability (v0.28).

No pygame dependency — pure data class.
"""


class UltimateCharge:
    """Per-tank ultimate charge tracker and ability timer.

    Charge sources (all no-op while ability is active):
      - damage dealt   → add_damage_charge(amount)
      - damage received → add_hit_charge(amount)
      - passive per-sec → tick_passive(dt)

    Lifecycle:
      1. Charge accumulates to charge_max.
      2. Player presses F → activate() resets charge, starts timer.
      3. update(dt) ticks timer; returns True on expiry.
      4. force_deactivate() for early cancellation (e.g. cloak break).
    """

    def __init__(self, config: dict) -> None:
        self.charge_max: float = float(config.get("charge_max", 100.0))
        self.charge_per_damage: float = float(config.get("charge_per_damage", 0.5))
        self.charge_per_hit: float = float(config.get("charge_per_hit", 0.5))
        self.charge_passive_rate: float = float(config.get("charge_passive_rate", 1.0))
        self.ability_type: str = config.get("ability_type", "")
        self.duration: float = float(config.get("duration", 0))
        self.config: dict = config

        self.charge: float = 0.0
        self._active_timer: float = 0.0
        self._is_active: bool = False

    # ------------------------------------------------------------------
    # Charge accumulation (no-op while active)
    # ------------------------------------------------------------------

    def add_damage_charge(self, damage_dealt: float) -> None:
        """Add charge from damage the owning tank dealt."""
        if self._is_active:
            return
        self.charge = min(self.charge_max, self.charge + damage_dealt * self.charge_per_damage)

    def add_hit_charge(self, damage_received: float) -> None:
        """Add charge from damage the owning tank received."""
        if self._is_active:
            return
        self.charge = min(self.charge_max, self.charge + damage_received * self.charge_per_hit)

    def tick_passive(self, dt: float) -> None:
        """Add passive charge over time."""
        if self._is_active:
            return
        self.charge = min(self.charge_max, self.charge + self.charge_passive_rate * dt)

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self) -> bool:
        """Attempt to activate the ultimate.

        Returns True if activation succeeded (charge was full).
        Resets charge to 0 and starts the active timer.
        """
        if not self.is_ready:
            return False
        self.charge = 0.0
        self._is_active = True
        self._active_timer = self.duration
        return True

    def update(self, dt: float) -> bool:
        """Tick the active ability timer.

        Returns True when the ability expires this frame.
        For instant abilities (duration=0), expires on the first update.
        """
        if not self._is_active:
            return False
        self._active_timer -= dt
        if self._active_timer <= 0:
            self._is_active = False
            self._active_timer = 0.0
            return True
        return False

    def force_deactivate(self) -> None:
        """Immediately end the active ability (e.g. cloak broken by firing)."""
        self._is_active = False
        self._active_timer = 0.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        """True when charge is full and ability is not active."""
        return self.charge >= self.charge_max and not self._is_active

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def charge_ratio(self) -> float:
        """Charge progress as 0.0–1.0."""
        if self.charge_max <= 0:
            return 0.0
        return min(1.0, self.charge / self.charge_max)

    @property
    def active_remaining(self) -> float:
        """Seconds remaining on active ability."""
        return self._active_timer
