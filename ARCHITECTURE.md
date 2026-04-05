# Architecture Reference

Living reference for prompt authors. Derived from source code — not comments,
not memory. If this file disagrees with the code, the code wins.

*Last updated: v0.32.0*

---

## 1. Project Structure

```
game/
  __init__.py                       Package root
  engine.py                         Main loop, scene registration, pygame init
  entities/
    __init__.py
    bullet.py                       Projectile entity with bounce + range + AoE detonation + pierce + pool spawn + knockback + cloak exclusion (v0.28)
    explosion.py                    AoE damage event with linear falloff + visual timer
    ground_pool.py                  Persistent floor hazard — slow and/or DPS area effect (v0.26)
    obstacle.py                     Destructible/indestructible arena wall + partial destruction
    pickup.py                       Collectible pickup with pulse animation
    tank.py                         Tank entity, TankInput dataclass, status effects, energy system, knockback physics, ultimate integration (v0.28)
  scenes/
    __init__.py                     SceneManager — scene registry + transitions
    base_scene.py                   Abstract base scene interface
    game_over_scene.py              Match result + XP progression display
    game_scene.py                   Main gameplay arena orchestrator + ultimate systems (shield dome, artillery, cloak rendering) (v0.28); Watch Mode + AI tank type rotation + multi-AI targeting wire-up (v0.32)
    loadout_scene.py                Unified hull/weapon/map selection; hull-lock → weapon reveal → slot 1 choice → reroll → map; ultimate description (v0.28); opponent count selector in hull panel (v0.32)
    map_select_scene.py             Deprecated v0.17.5 — merged into loadout
    menu_scene.py                   Main menu with synthwave grid background
    profile_select_scene.py         Four-slot profile picker
    settings_scene.py               Audio/display/controls/gameplay settings
    tank_select_scene.py            Deprecated v0.17.5 — merged into loadout
    weapon_select_scene.py          Deprecated v0.17.5 — merged into loadout; _WEAPON_ORDER 11 entries (v0.25)
  systems/
    __init__.py
    ai_controller.py                State machine AI with stuck recovery + weapon cycling timer + ultimate activation + cloak detection (v0.28); make_nearest_enemy_getter factory + low-HP priority targeting + target stickiness (v0.32)
    collision.py                    All entity collision detection + resolution; 3-tuple return (v0.26)
    debris_system.py                Particle burst on obstacle destruction
    input_handler.py                Keyboard/mouse input → TankInput; F key ultimate activation (v0.28)
    match_calculator.py             MatchResult factory + XP formula
    physics.py                      Bullet movement + arena boundary clamping
    pickup_spawner.py               Timed pickup spawn + lifetime management
    status_effect.py                StatusEffect class — tick damage, multipliers, expiry
    elemental_resolver.py           Elemental combo detector — scans tanks for effect pairs, triggers combos
    raycast.py                      Hitscan raycast — line-vs-AABB + line-vs-circle; used by laser beam (v0.25)
    ground_pool_system.py           Applies ground pool effects (slow, fire DPS) to tanks each frame (v0.26)
    ultimate.py                     UltimateCharge data class — charge accumulation, activation, expiry (v0.28)
    weapon_roller.py                Weighted random weapon selection for loadout slots (v0.25.5)
    progression_manager.py          XP/level/unlock progression logic
  ui/
    __init__.py
    audio_manager.py                Singleton audio: SFX, music, volume control
    components.py                   ScrollingGrid, FadeTransition UI widgets
    hud.py                          In-game health bars + weapon slot display + cooldown overlay + combat effect labels + energy bar + ultimate charge bar (v0.28); AI bar labels "AI N" + draw_watch_overlay (v0.32)
  utils/
    __init__.py
    camera.py                       World-to-screen transform with lerp tracking
    config_loader.py                YAML loader + typed config getters
    constants.py                    All numeric/string constants — single source
    damage_types.py                 DamageType enum + parse_damage_type() helper
    logger.py                       Rotating file + console logger factory
    map_loader.py                   Map YAML → obstacles + theme + spawn points
    math_utils.py                   Geometry: distance, angles, lerp, rotation
    save_manager.py                 Profile + settings JSON persistence
    stuck_detector.py               Rolling-window displacement detector for AI
    theme_loader.py                 Theme YAML loader with fallback chain

data/
  configs/
    ai_difficulty.yaml              Three AI difficulty tiers
    materials.yaml                  Six obstacle material definitions (incl. rubble)
    pickups.yaml                    Three pickup type definitions
    status_effects.yaml             Four combat status effect definitions (fire, poison, ice, electric)
    elemental_interactions.yaml     Three elemental combo definitions (steam_burst, accelerated_burn, deep_freeze)
    tanks.yaml                      Four tank type definitions
    ultimates.yaml                  Four ultimate ability definitions per tank type (v0.28)
    weapons.yaml                    Fourteen weapon type definitions + tips field (v0.26)
    weapon_weights.yaml             Probability weights for random weapon rolls; 13 entries (v0.26)
  maps/
    map_01.yaml                     "Headquarters" — default theme, 8 obstacles (incl. 2 reinforced_steel)
    map_02.yaml                     "Dunes" — desert theme, 7 obstacles
    map_03.yaml                     "Tundra" — snow theme, 12 obstacles
  progression/
    xp_table.yaml                   21-level XP thresholds + unlock schedule (v0.26)
  themes/
    default.yaml                    Classic green arena
    desert.yaml                     Sandy tan arena
    island.yaml                     Coastal beach arena
    jungle.yaml                     Dense green arena
    snow.yaml                       Frozen pale blue arena
    urban.yaml                      Asphalt grey arena

scripts/
  generate_audio.py                 Procedural WAV generator for all SFX + music

tests/
  __init__.py
  conftest.py                       Shared pytest fixtures
  test_ai_states.py                 AI state machine transitions + recovery
  test_collision.py                 Collision detection + resolution
  test_damage_types.py              DamageType enum, bullet/collision/obstacle routing, color dict
  test_debris.py                    Debris particle lifecycle + cap
  test_loadout.py                   Loadout scene selection logic + hull-lock flow + slot 0 cycling (v0.25.5)
  test_map_loader.py                Map YAML parsing
  test_match_calculator.py          XP formula + MatchResult factory
  test_math_utils.py                Geometry utility functions
  test_music_layers.py              Music layer system + constants
  test_obstacles.py                 Obstacle damage states + hit flash
  test_pickup.py                    Pickup apply effects + pulse animation
  test_explosion.py                 AoE damage, grenade bullet, stone destruction, cooldown
  test_status_effects.py            StatusEffect class, Tank combat effects, collision integration, HUD
  test_elemental_interactions.py    ElementalResolver, tank stun, remove_combat_effect, combo effects
  test_elemental_weapons.py         Cryo, poison, flamethrower, EMP, railgun pierce, raycast, laser beam energy (v0.25)
  test_ground_pool.py               GroundPool entity, GroundPoolSystem, knockback, pool fields, weapon configs (v0.26)
  test_pickup_spawner.py            Spawn timing + caps + lifetime + obstacle blocking
  test_profile_select.py            Profile slot management
  test_progression.py               XP table progression
  test_progression_manager.py       Level-up + unlock logic
  test_save_manager.py              JSON persistence
  test_settings.py                  Settings load/save
  test_stuck_detector.py            Stuck detection window logic
  test_tank_select.py               Tank selection (legacy)
  test_tank_status.py               Status effects: apply, tick, regen
  test_ultimate.py                  UltimateCharge class, activation, tank integration, cloak, AI detection, config (v0.28)
  test_ai_targeting.py              make_nearest_enemy_getter factory, low-HP priority, target stickiness, Watch Mode integration (v0.32)
  test_theme_loader.py              Theme loading + fallback
  test_turret.py                    Independent turret aiming
  test_weapon_roller.py             WeaponRoller unit tests (v0.25.5)
  test_weapon_select.py             Weapon selection (legacy)
  test_weapon_slots.py              Multi-slot weapon cycling

assets/
  CREDITS.txt
  music/
    music_game_over.wav             Melancholic 70 BPM, 4 bars
    music_gameplay.wav              Driving 120 BPM, 8 bars
    music_menu.wav                  Atmospheric 80 BPM, 8 bars
  sounds/
    sfx_bullet_hit_obstacle.wav     Dull thud, 0.18s
    sfx_bullet_hit_tank.wav         Metallic clang, 0.25s
    sfx_obstacle_destroy.wav        Crunch/rubble, 0.45s
    sfx_pickup_collect.wav          Bright ding, 0.2s
    sfx_pickup_expire.wav           Soft descending tone, 0.4s
    sfx_pickup_spawn.wav            Rising arpeggio, 0.3s
    sfx_tank_collision.wav          Heavy clunk, 0.3s
    sfx_tank_explosion.wav          Big explosion, 1.2s
    sfx_explosion.wav                AoE explosion, 0.6s (v0.22)
    sfx_railgun_fire.wav            Deep electromagnetic thump + crack, 0.4s (v0.25)
    sfx_reroll.wav                  Ascending arpeggio C5→E5→G5→C6 + ding, 0.4s (v0.25.5)
    sfx_glue_splat.wav              Wet sticky impact + descending sine + squelch, 0.25s (v0.26)
    sfx_lava_sizzle.wav             Crackling noise + low hiss + bubble pop, 0.4s (v0.26)
    sfx_concussion_hit.wav          Sharp crack + deep bass thump + whooshy air, 0.35s (v0.26)
    sfx_laser_hum.wav               Sustained 220+330 Hz hum, 2s loopable layer (v0.25)
    sfx_ult_speed_burst.wav         Rising whine + square harmonics, 0.5s (v0.28)
    sfx_ult_shield_dome.wav         Resonant hum + chime shimmer, 0.6s (v0.28)
    sfx_ult_artillery.wav           Falling whistle + deep boom, 0.8s (v0.28)
    sfx_ult_cloak.wav               Shimmer + whoosh, 0.5s (v0.28)
    sfx_tank_fire.wav               Sharp crack, 0.35s
    sfx_ui_confirm.wav              Two-tone chime, 0.22s
    sfx_ui_navigate.wav             Short blip, 0.08s
  sprites/
    .gitkeep                        Reserved for future sprite assets
```

---

## 2. Entity Interfaces

### TankInput (game/entities/tank.py)

Frozen dataclass — normalized control intent produced by any controller.

```
TankInput(
    throttle: float = 0.0,       # -1 = full reverse, +1 = full forward
    rotate: float = 0.0,         # -1 = rotate left, +1 = rotate right
    fire: bool = False,
    turret_angle: float = 0.0,   # desired turret facing (degrees, CW from right)
    cycle_weapon: int = 0,       # +1 = next slot, -1 = prev, 0 = no change
    switch_slot: int = -1,       # direct slot index (-1 = no change)
    activate_ultimate: bool = False,  # F key edge-detected (v0.28)
)
```

### ControllerProtocol (game/entities/tank.py)

```
Protocol:
    get_input() -> TankInput
```

Both InputHandler and AIController implement this protocol.

---

### Tank (game/entities/tank.py)

#### Construction

```python
Tank(x: float, y: float, config: dict, controller: ControllerProtocol)
```

`config` keys: `type`, `speed`, `health` (alias `hp`), `turn_rate`, `fire_rate`,
`default_weapons`. All have fallback defaults in constants.py.

#### Public Fields

| Field | Type | Description |
|-------|------|-------------|
| x | float | World-space X position |
| y | float | World-space Y position |
| angle | float | Hull rotation in degrees (0 = right, CW) |
| turret_angle | float | Independent turret aim in degrees |
| health | int | Current HP |
| max_health | int | Maximum HP (from config) |
| is_alive | bool | False when health reaches 0 |
| speed | float | Movement speed in px/s (from config) |
| turn_rate | float | Hull rotation speed in deg/s |
| fire_rate | float | Shots per second |
| tank_type | str | Type identifier from config |
| controller | ControllerProtocol | Assigned input controller |
| vx | float | Current velocity X (px/s, inferred) |
| vy | float | Current velocity Y (px/s, inferred) |
| ultimate | UltimateCharge \| None | Ultimate ability state (v0.28) |

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt: float)` | `list` | Advance state; returns event list: `[("fire", x, y, angle, weapon_type)]` for projectiles, `[("beam", x, y, angle, weapon_type)]` for hitscan (v0.25), `[("ultimate_activated", self, type)]`, `[("ultimate_expired", self, type)]`, `[("cloak_break", x, y)]` (v0.28) |
| `take_damage(amount: int, damage_type: DamageType = DamageType.STANDARD)` | `None` | Apply damage (shield absorbs first); sets is_alive=False at 0 HP |
| `load_weapons(configs: list[dict])` | `None` | Equip up to MAX_WEAPON_SLOTS weapons; rejects empty/duplicates |
| `cycle_weapon(direction: int)` | `None` | Cycle active slot (+1 next, -1 prev) with wrapping |
| `set_active_slot(index: int)` | `None` | Jump to slot by index; no-op if out of range |
| `load_ultimate(config: dict)` | `None` | Create UltimateCharge from config dict (v0.28) |
| `apply_status(name: str, value: float, duration: float)` | `None` | Apply or refresh a named status effect |
| `tick_status_effects(dt: float)` | `None` | Decrement timers, accumulate regen, remove expired |
| `has_status(name: str)` | `bool` | True if named effect is active |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| position | tuple[float, float] | (x, y) |
| health_ratio | float | health / max_health (0.0 if max_health <= 0) |
| active_weapon | dict | Config dict of currently active weapon slot |
| active_slot | int | Index into weapon_slots |
| weapon_slots | list[dict] | Shallow copy of weapon slot configs |
| slot_cooldowns | list[float] | Per-slot cooldown timers in seconds remaining (v0.22) |
| energy | float | Current energy level (v0.25) |
| energy_ratio | float | energy / energy_max; 0 when no hitscan weapon equipped (v0.25) |
| is_firing_beam | bool | True when actively firing a hitscan beam this frame (v0.25) |
| is_cloaked | bool | True when cloak ultimate is active (v0.28) |
| status_effects | dict | Read-only access to _status_effects |

#### Status Effect System

Storage: `_status_effects: dict[str, dict]` mapping effect name to `{"value": float, "timer": float}`.

Supported effects:
- `"speed_boost"` — multiplies movement speed by `value` during `update()`
- `"regen"` — heals `value` HP/s; fractional HP accumulated via `_accum` float key
- `"rapid_reload"` — no ongoing effect; `apply()` resets all `_slot_cooldowns` to 0.0
- `"shield"` — absorbs damage before health; dict includes `shield_hp` key. `take_damage()` reduces `shield_hp` first; if shield_hp <= 0, shield is removed and remaining damage hits health. Expires by timer even with HP remaining.

`tick_status_effects(dt)`:
1. If `"regen"` active: accumulate `value * dt` into `_accum`, apply whole-number HP (capped at max_health)
2. Decrement all timers by dt
3. Remove effects with timer <= 0

`apply_status(name, value, duration, **kwargs)` overwrites existing effect of same name (refresh, no stack). Shield uses `shield_hp=float` kwarg.

Properties: `shield_hp -> float` (current shield HP or 0.0), `active_status_names -> list[str]` (names of active effects — includes both pickup and combat effect keys).

#### Combat Status Effects (v0.23)

Separate from pickup buffs. Storage: `_combat_effects: dict[str, StatusEffect]` where `StatusEffect` is from `game/systems/status_effect.py`.

| Method / Property | Returns | Description |
|-------------------|---------|-------------|
| `apply_combat_effect(effect_type, config)` | `None` | Apply or refresh a combat StatusEffect |
| `_combat_speed_mult()` | `float` | Product of all active `effect.speed_mult` values |
| `_combat_turn_mult()` | `float` | Product of all active `effect.turn_mult` values |
| `_combat_fire_rate_mult()` | `float` | Product of all active `effect.fire_rate_mult` values |
| `combat_effects` | `dict` | Shallow copy of `_combat_effects` |
| `has_any_combat_effect` | `bool` | True if any combat effect is active |
| `remove_combat_effect(effect_type)` | `None` | Delete a combat effect by key (used by ElementalResolver to consume sources) |
| `apply_stun(duration)` | `None` | Set stun timer to `max(_stun_timer, duration)` — shorter stun never overrides longer |
| `apply_knockback(force, angle_deg)` | `None` | Apply impulse: adds to `_knockback_vx/_vy` via cos/sin; decays exponentially in `update()` (v0.26) |
| `is_stunned` | `bool` | True when `_stun_timer > 0` |

Combat effects are ticked in `update()` after `tick_status_effects(dt)`. DoT damage is applied directly to health (bypasses shield). Effects expire when `duration <= 0`.

#### Tank Stun System (v0.24)

`_stun_timer: float` — when >0, `update()` early-returns with `[]` (no fire events, zero velocity), but still ticks cooldowns, combat effects (DoT still hurts), and pickup effects. Stun block is placed at top of `update()` after `is_alive` check, before any input processing.

Multiplier stacking: combat speed/turn/fire_rate multipliers are products of all active effects. Pickup speed_boost stacks multiplicatively on top of combat speed mult.

#### Tank Knockback System (v0.26)

Impulse-based displacement via `_knockback_vx`, `_knockback_vy` (pixels/sec). Applied by
`apply_knockback(force, angle_deg)` — converts polar impulse to cartesian and adds to
velocity (stacks with existing knockback).

In `update()`, knockback displacement runs **after** normal movement, **before** velocity
computation. Exponential decay: `v *= math.exp(-8.0 * dt)` each frame. Snaps to zero when
`abs(vx) < 0.5 and abs(vy) < 0.5`. Tanks under knockback can still drive and fire — it is
additive, not a stun.

`pool_slow` status: applied by `GroundPoolSystem` with 0.15 s duration (self-clears shortly
after leaving pool). Checked in `update()` alongside `speed_boost`: multiplies
`effective_speed` by the status value (< 1.0 = slow).

#### Tank Energy System (v0.25)

Powers hitscan weapons (laser beam). Initialized by `load_weapons()` when any slot has
`hitscan: true`. Fields: `_energy`, `_energy_max`, `_energy_drain_rate`,
`_energy_recharge_rate`, `_energy_min_to_fire`, `_beam_dps`, `_is_firing_beam`.

`update()` fire block splits on `active_weapon.get("hitscan", False)`:
- **Hitscan branch**: drains `_energy_drain_rate * dt` per frame while `intent.fire` and
  energy ≥ `_energy_min_to_fire`; emits `("beam", x, y, angle, type)` event; recharges
  at `_energy_recharge_rate * dt` when not firing.
- **Projectile branch**: existing cooldown-timer fire logic; passively recharges energy
  if max > 0.

#### Health Float Accumulator (v0.28)

`_health_float: float` backing field stores fractional HP. The `health` property returns
`int(self._health_float)`. Setting `health = N` updates `_health_float = float(N)`.
This enables smooth sub-integer healing from passive regen without rounding loss.

#### Passive HP Regen (v0.28)

`regen_rate: float` from tank config (HP/sec). Applied in `update()` each frame via
`_health_float += regen_rate * dt`, capped at `max_health`. Suppressed when any active
combat effect has `tick_damage > 0` (fire, poison) — checked via `_has_dot_active()`.
Resumes automatically when all DoTs expire.

#### HP Doubling (v0.28)

All tank HP values in `tanks.yaml` doubled (light 160, medium 240, heavy 440, scout 120).
`TANK_STAT_MAX["health"]` updated to 440.0. Compensates for increased damage sources
(ultimates, ground pools, elemental combos).

#### Ground Pool Self-Damage (v0.28)

`GroundPoolSystem` no longer exempts the pool owner from damage. All tanks standing in a
lava pool take fire DPS, including the tank that created it.

#### Tank Ultimate System (v0.28)

`load_ultimate(config)` creates an `UltimateCharge` instance from `ultimates.yaml`.

Charge sources (all no-op while ability is active):
- `add_hit_charge(amount)` — called in `take_damage()` when `amount > 0`
- `add_damage_charge(amount)` — called by GameScene when player/AI deals damage
- `tick_passive(dt)` — called in `update()` each frame

Activation: when `intent.activate_ultimate` and `ultimate.is_ready`, calls `ultimate.activate()`,
emits `("ultimate_activated", self, ability_type)` event. Cloak sets `_cloaked = True`.

Expiry: `ultimate.update(dt)` returns True when timer expires. Cloak clears `_cloaked`.
Emits `("ultimate_expired", self, ability_type)`.

Cloak break: after any fire event (projectile or hitscan), if `_cloaked` is True, clears
cloak and calls `ultimate.force_deactivate()`. Emits `("cloak_break", x, y)`.

Speed modifier: `speed_burst` and `cloak` multiply `effective_speed` by `config["speed_multiplier"]`.
Fire rate modifier: `speed_burst` multiplies fire rate by `config["fire_rate_multiplier"]`.

Death cleanup: `_cloaked = False` in the `is_alive` early-return block.

### UltimateCharge (game/systems/ultimate.py) (v0.28)

Plain data class — no pygame dependency. Designed for future server-authoritative multiplayer.

```python
UltimateCharge(config: dict)
```

Fields: `charge`, `charge_max`, `charge_per_damage`, `charge_per_hit`, `charge_passive_rate`,
`ability_type`, `duration`, `config` (full dict), `_active_timer`, `_is_active`.

| Method | Returns | Description |
|--------|---------|-------------|
| `add_damage_charge(amount)` | `None` | Add `amount * charge_per_damage` to charge (no-op while active) |
| `add_hit_charge(amount)` | `None` | Add `amount * charge_per_hit` to charge (no-op while active) |
| `tick_passive(dt)` | `None` | Add `charge_passive_rate * dt` to charge (no-op while active) |
| `activate()` | `bool` | Returns True if charge was full; resets charge to 0, starts active timer |
| `update(dt)` | `bool` | Ticks active timer; returns True when ability expires |
| `force_deactivate()` | `None` | Immediately end active ability (cloak break on fire) |

| Property | Type | Description |
|----------|------|-------------|
| `is_ready` | `bool` | True when `charge >= charge_max` and not active |
| `is_active` | `bool` | True when ability timer is running |
| `charge_ratio` | `float` | `charge / charge_max` (0.0–1.0) |
| `active_remaining` | `float` | Seconds left on active ability (0 if not active) |

Instant abilities (`duration=0`, e.g. artillery_strike): `update()` returns True and sets
`_is_active = False` on the first call after activation.

---

### StatusEffect (game/systems/status_effect.py)

```python
StatusEffect(effect_type: str, config: dict)
```

Fields: `effect_type`, `duration`, `tick_interval`, `tick_damage`, `speed_mult`, `turn_mult`, `fire_rate_mult`, `color: tuple`, `_tick_timer`.

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt)` | `int` | Decrement duration, fire DoT ticks, return total damage dealt |
| `refresh(config)` | `None` | Reset duration only (ongoing ticks uninterrupted) |
| `is_expired` | `bool` | True when `duration <= 0` |

Config schema (`data/configs/status_effects.yaml`):
```yaml
fire:
  duration: 3.0        # seconds
  tick_interval: 0.5   # seconds between damage ticks (0 = no ticking)
  tick_damage: 8       # HP per tick
  speed_mult: 1.0      # 1.0 = no change
  turn_mult: 1.0
  fire_rate_mult: 1.0
  color: [255, 80, 20] # VFX/HUD tint
  description: "..."
```

Four effects defined: `fire` (burn DoT), `poison` (slow DoT), `ice` (movement slow), `electric` (fire rate reduction).

### ElementalResolver (game/systems/elemental_resolver.py) (v0.24)

Scans all alive tanks each frame for matching pairs of active combat effects. When a pair matches a defined elemental interaction, both source effects are consumed and a combo event dict is returned.

```python
ElementalResolver()  # loads elemental_interactions.yaml on init
resolver.resolve(tanks: list) -> list[dict]  # returns combo event dicts
```

Interactions stored with `frozenset(elements)` for order-independent matching via `issubset()`. One combo per tank per frame (first match wins via `break`).

Config schema (`data/configs/elemental_interactions.yaml`):
```yaml
steam_burst:
  elements: ["fire", "ice"]
  result_type: aoe_burst       # aoe_burst | instant_damage | stun
  damage: 25                   # direct damage to target
  aoe_radius: 100              # explosion radius (aoe_burst only)
  aoe_damage: 35               # max AoE damage
  stun_duration: 0             # stun seconds (stun type only)
  color: [200, 200, 220]       # VFX tint
  sfx_key: steam_burst         # maps to COMBO_SFX dict
  description: "..."
```

Three combos defined:
- **Steam Burst** (fire+ice): `aoe_burst` — 25 direct + AoE explosion (owner=None, all tanks take damage)
- **Accelerated Burn** (poison+fire): `instant_damage` — 60 direct damage
- **Deep Freeze** (ice+electric): `stun` — 10 damage + 3.0s full input suppression

Resolver timing: called AFTER collision resolution (so new effects from this frame's bullets are applied) but BEFORE camera update.

#### Combo Visuals (GameScene)

Tracked as `_combo_visuals: list[dict]` with timer, rendered as separate draw pass after explosions:
- **steam_burst**: expanding white-gray cloud with multiple rings + center flash
- **accelerated_burn**: orange flash + radial spark lines
- **deep_freeze**: hexagonal ice crystal pattern with rotating lines + diamond tips

#### Combo HUD Notification

Player combo text: fading notification in upper third of screen, 2s duration. Tracked via `_player_combo_text`, `_player_combo_timer`, `_player_combo_color`. Timer ticked in `update()`, rendered in `draw()`.

#### Combo SFX

`COMBO_SFX` dict in constants.py maps combo names to WAV paths. Three generated sounds: `sfx_steam_burst.wav`, `sfx_accelerated_burn.wav`, `sfx_deep_freeze.wav`.

---

### Bullet (game/entities/bullet.py)

#### Construction

```python
Bullet(x: float, y: float, angle: float, owner: Tank, config: dict)
```

`config` keys: `speed`, `damage`, `max_bounces`, `max_range`, `type` (weapon_type), `damage_type`, `tracking_strength`, `aoe_radius`, `aoe_falloff`, `pierce_count`, `hitscan`.

#### Public Fields

| Field | Type | Description |
|-------|------|-------------|
| x | float | World-space X |
| y | float | World-space Y |
| angle | float | Heading in degrees |
| owner | Tank | Firing tank (used to avoid self-hit) |
| is_alive | bool | False when destroyed or out of range |
| speed | float | Px/s (from config or DEFAULT_BULLET_SPEED) |
| damage | int | HP per hit (from config or 20) |
| max_bounces | int | Max wall bounces (from config or 0) |
| bounces_remaining | int | Decremented on each bounce |
| max_range | float | Max travel distance before despawn |
| weapon_type | str | Weapon identifier from config |
| damage_type | DamageType | Enum from config via parse_damage_type() (v0.21) |
| aoe_radius | float | AoE blast radius in px (0 = non-explosive) (v0.22) |
| aoe_falloff | float | Damage multiplier at edge of radius (v0.22) |
| is_explosive | bool | True if aoe_radius > 0 (v0.22) |
| pierce_count | int | Remaining pierce-throughs (0 = destroyed on first hit) (v0.25) |
| _pierced_tanks | set | ids of tanks already hit — prevents double-hit on same pierce (v0.25) |

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt: float)` | `None` | Advance position first, then track target (if homing); despawn if max_range exceeded |
| `reflect(normal_x: float, normal_y: float)` | `None` | Reflect velocity off surface normal; decrement bounces |
| `destroy()` | `None` | Mark for removal |
| `set_targets_getter(getter)` | `None` | Inject callable returning list of alive tanks for homing |

#### Homing Tracking (`_track_target`)

Called automatically by `update()`. No-op when `_tracking_strength == 0` or no targets getter.
Finds nearest alive non-owner non-cloaked tank, computes desired angle, rotates heading by
`tracking_strength * dt` radians/sec toward target. Updates `_dx`, `_dy`, `angle`.

Cloaked tanks are excluded via `not getattr(t, '_cloaked', False)` (v0.28).

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| position | tuple[float, float] | (x, y) |

---

### DamageType (game/utils/damage_types.py)

Enum introduced in v0.21. Flows from weapon config → Bullet → CollisionSystem → Tank/Obstacle.

```python
class DamageType(Enum):
    STANDARD = auto()   # kinetic/ballistic — most weapons
    EXPLOSIVE = auto()  # splash damage, AoE — homing_missile
    FIRE = auto()       # burn DoT — future
    ICE = auto()        # movement slow — future
    POISON = auto()     # damage over time — future
    ELECTRIC = auto()   # fire rate slow — future
```

`parse_damage_type(value: str) -> DamageType` — case-insensitive, returns STANDARD on unknown/None.

Pipeline: `weapons.yaml damage_type:` → `Bullet.damage_type` (enum) → `CollisionSystem` passes to `tank.take_damage(damage_type=)` and `obs.take_damage(damage_type=.name.lower())` → Obstacle normalizes enum or string to lowercase for `damage_filters` comparison.

Rendering: `DAMAGE_TYPE_BULLET_COLORS` dict maps enum name → RGB. HUD weapon slots show 4px colored dot per slot.

---

### Explosion (game/entities/explosion.py)

Short-lived AoE damage event created when an explosive bullet detonates (v0.22).

#### Construction

```python
Explosion(x: float, y: float, radius: float, damage: int,
          damage_type: DamageType, owner: Tank,
          damage_falloff: float = 0.3, visual_duration: float = 0.4)
```

#### Public Fields

| Field | Type | Description |
|-------|------|-------------|
| x, y | float | World-space center |
| radius | float | Damage radius in px |
| damage | int | Max damage at epicenter |
| damage_type | DamageType | Inherited from bullet |
| owner | object | Firing tank (immune to own explosion) |
| damage_falloff | float | Multiplier at edge (0.0–1.0) |
| is_alive | bool | True until damage resolved |
| visual_timer | float | Seconds remaining for animation |

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `resolve_damage(tanks, obstacles)` | `list` | Apply AoE damage; returns collision-compatible events. Called once — idempotent. Sets `is_alive = False`. |
| `update(dt)` | `None` | Tick visual timer |

Damage scales linearly: `scale = 1.0 - (1.0 - falloff) * (dist / radius)`.
Owner immune. Dead entities skipped. Obstacle uses center for distance.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| visual_alive | bool | True while animation should render |
| visual_progress | float | 0.0 (just created) → 1.0 (fully faded) |
| position | tuple | (x, y) |

---

### Obstacle (game/entities/obstacle.py)

#### Construction

```python
Obstacle(x: float, y: float, width: float, height: float,
         material_type: str = "stone", material_config: dict | None = None,
         reflective: bool = False)
```

`material_config` keys: `hp`, `destructible`, `damage_filters`, `color`, `partial_destruction`, `rubble_material`.

#### Public Fields

| Field | Type | Description |
|-------|------|-------------|
| x | float | Top-left corner X |
| y | float | Top-left corner Y |
| width | float | Rect width |
| height | float | Rect height |
| material_type | str | Material identifier |
| reflective | bool | Surface reflects bullets (reserved) |
| is_alive | bool | False when destroyed |
| destructible | bool | Whether it can take damage |
| max_hp | int | Maximum HP (from material config or 9999) |
| hp | int | Current HP |
| damage_filters | list[str] | Damage types that apply (empty = all) |
| color | tuple[int, int, int] | Current RGB (tinted by theme) |
| base_color | tuple[int, int, int] | RGB before theme tinting |
| partial_destruction | bool | Crumbles into rubble on destroy (v0.22) |
| rubble_material | str | Material key for rubble pieces (v0.22) |

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt: float)` | `None` | Decrement hit-flash timer |
| `take_damage(amount: int, damage_type: DamageType \| str = "standard")` | `None` | Apply damage (guarded by destructible + damage_filters); accepts enum or string, normalizes to lowercase for filter comparison (v0.21) |
| `destroy()` | `None` | Force-destroy if destructible |
| `get_rubble_pieces(materials: dict)` | `list[Obstacle]` | Generate 2-3 smaller rubble obstacles (v0.22); splits wide walls horizontally, tall walls vertically |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| rect | tuple[float, float, float, float] | (x, y, width, height) |
| hp_ratio | float | hp / max_hp; 1.0 if indestructible |
| is_flashing | bool | True while hit flash timer > 0 |
| current_color | tuple[int, int, int] | Render color with damage darkening + flash blend |

---

### Pickup (game/entities/pickup.py)

#### Construction

```python
Pickup(x: float, y: float, pickup_type: str, value: float)
```

#### Public Fields

| Field | Type | Description |
|-------|------|-------------|
| x | float | World-space X |
| y | float | World-space Y |
| pickup_type | str | Effect type: "health", "rapid_reload", "speed_boost" |
| value | float | Effect magnitude |
| is_alive | bool | False after collection or expiry |
| radius | float | Collision radius (14.0) |

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `apply(tank: Tank)` | `None` | Apply effect to tank and mark as consumed; plays SFX_PICKUP_COLLECT |
| `update(dt: float)` | `None` | Increment pulse timer and age |

`apply()` logic by type:
- `"health"`: If tank at full HP, returns without consuming. Otherwise applies `"regen"` status with `value / PICKUP_EFFECT_DURATION` HP/s.
- `"rapid_reload"`: Resets all `tank._slot_cooldowns` to 0.0.
- `"speed_boost"`: Applies `"speed_boost"` status with `value` multiplier for PICKUP_EFFECT_DURATION seconds.
- `"shield"`: Applies `"shield"` status with `shield_hp=value` (or `SHIELD_DEFAULT_HP`) for SHIELD_DEFAULT_DURATION seconds.
- Unknown type: consumes pickup, applies no effect.

Per-type SFX: `PICKUP_COLLECT_SFX` dict maps pickup type → SFX path (health, speed, reload, shield).

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| position | tuple[float, float] | (x, y) |
| age | float | Seconds since spawn |
| pulse | float | 0.0-1.0 oscillation: `(sin(timer * PICKUP_PULSE_SPEED) + 1) / 2` |

---

### GroundPool (game/entities/ground_pool.py) (v0.26)

Persistent floor hazard created when a glue or lava projectile impacts.

#### Construction

```python
GroundPool(x: float, y: float, pool_type: str, radius: float,
           duration: float, slow_mult: float, dps: float,
           color: tuple, owner=None)
```

#### Public Fields

| Field | Type | Description |
|-------|------|-------------|
| x, y | float | World-space center |
| radius | float | Effect radius in px |
| pool_type | str | "glue" or "lava" |
| duration | float | Seconds remaining |
| max_duration | float | Initial duration (for fade calc) |
| slow_mult | float | Speed multiplier for tanks in pool (< 1.0 = slow) |
| dps | float | Damage per second (0 for glue) |
| color | tuple | (R, G, B) for rendering |
| owner | object | Firing tank (immune to own pool) |
| is_alive | bool | False when duration expires |

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt)` | `None` | Decrement duration; set `is_alive = False` when expired |
| `contains(px, py)` | `bool` | True if point within radius (strict `<`) |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| age_ratio | float | 0.0 = new, 1.0 = expired (for fade-out rendering) |
| position | tuple | (x, y) |

Pool types:
- **glue**: `slow_mult=0.35`, `dps=0`, `duration=25s`, `radius=60px` — pure area denial
- **lava**: `slow_mult=0.6`, `dps=20`, `duration=15s`, `radius=50px` — fire damage + slow; applies fire combat effect

Rendering: drawn after arena floor, before pickups/obstacles. Glue = yellow-green circle with darker center + bubble dots. Lava = orange circle with pulsing glow + bright core. Both fade as `age_ratio` → 1.0.

Cap: `MAX_GROUND_POOLS = 15`. Oldest pools pruned when cap exceeded.

---

## 3. Systems

### AIController (game/systems/ai_controller.py)

#### AIState Enum

| State | Meaning |
|-------|---------|
| PATROL | Wander when player out of detection range |
| PURSUE | Move toward detected player |
| ATTACK | Fire when in range with line of sight |
| EVADE | Retreat when health critically low |
| RECOVERY | Temporary sub-state: escape stuck position |

#### State Transition Table (`_update_state`)

Evaluated every `get_input()` call (skipped during RECOVERY):

| Condition | Result |
|-----------|--------|
| owner/target is None or target dead | PATROL |
| target is cloaked (v0.28) | PATROL |
| health_ratio <= evasion_threshold | EVADE |
| dist <= AI_ATTACK_RANGE (375) | ATTACK |
| dist <= AI_DETECTION_RANGE (800) | PURSUE |
| else | PATROL |

Priority: cloak check > EVADE > ATTACK > PURSUE > PATROL (evaluated top-to-bottom).

#### Per-State Input Methods

| Method | throttle | rotate | fire | turret_angle |
|--------|----------|--------|------|--------------|
| `_patrol_input()` | 0.2–0.6 (center-seeking) | ±1.0 toward center | False | hull angle |
| `_pursue_input(target)` | 0.3-1.0 (heading-dependent) | ±1.0 toward target | False | tracks target |
| `_attack_input(target)` | 0.0 | ±1.0 toward target | accuracy-jittered aim + aggression roll | jittered aim |
| `_evade_input(target)` | 1.0 (forward = away) | ±1.0 toward flee angle | True if dist <= ATTACK_RANGE and aggression roll | tracks target |
| `_recovery_input()` | Phase 1: -1.0, Phase 2: 0.7 | alternating direction | False | hull angle |

`_patrol_input()` drives toward arena center `(ARENA_WIDTH/2, ARENA_HEIGHT/2)`: throttle 0.6 when heading within 60 degrees of center, 0.2 while turning hard. Ensures tanks converge from spawn corners (v0.32).

#### RECOVERY Sub-State

Triggered when `StuckDetector.is_stuck` fires during PATROL, PURSUE, or EVADE
(not ATTACK — AI deliberately stands still to aim), and post-recovery immunity
has expired.

Two-phase timing:
- Phase 1 (0.55s): Full reverse + full rotation — backs away from obstacle
- Phase 2 (0.45s): Moderate forward + gentle rotation — consolidates new heading

Post-recovery immunity (1.2s): Suppresses stuck re-trigger. During immunity,
EVADE applies a 65-degree bias to the flee angle in the recovery rotation
direction to break corner symmetry.

Recovery direction alternates each time (+1.0 → -1.0 → +1.0) to avoid spinning in place.

#### Obstacle Avoidance (`_obstacle_steer_correction`)

```python
_obstacle_steer_correction(desired_angle: float) -> float
```

For each live obstacle within 130px (_LOOKAHEAD_PX):
1. Find nearest point on obstacle rect to tank center
2. Check if bearing to that point is within ±90 degrees of desired_angle
3. If so, apply angular correction (±40 degrees) scaled by proximity

Corrections are accumulated and capped at ±72 degrees (1.8 * _STEER_ANGLE).
This is repulsion, not pathfinding — stuck recovery catches what it misses.

#### Injection Points

| Method | Called By | Purpose |
|--------|-----------|---------|
| `set_owner(tank)` | GameplayScene | Link controller to its tank |
| `set_obstacles_getter(getter)` | GameplayScene | Inject `() -> list[Obstacle]` for avoidance |
| `set_pickups_getter(getter)` | GameplayScene | Inject `() -> list[Pickup]` for pickup awareness |
| `tick(dt)` | GameplayScene (before tank.update) | Advance stuck detector + recovery timer |

#### Weapon Cycling Timer (v0.25.5)

`_weapon_cycle_timer: float` — counts down from a random 4.0-8.0s interval. When
expired, sets `_pending_weapon_cycle = True`. `get_input()` injects `cycle_weapon=+1`
into the returned TankInput and resets the timer to a new random interval.

#### Ultimate Activation (v0.28)

After weapon cycle injection in `get_input()`, AI checks if `owner.ultimate.is_ready`:
- **Offensive** (`speed_burst`, `artillery_strike`): activates in ATTACK state with 30% chance per frame
- **Defensive** (`shield_dome`, `cloak`): activates in EVADE state with 40% chance per frame

Sets `activate_ultimate=True` on the returned TankInput.

#### Cloak Detection (v0.28)

In `_update_state()`, if `target._cloaked` is True, AI transitions to PATROL (loses tracking).
Checked before distance-based state transitions.

#### make_nearest_enemy_getter (v0.32)

Module-level factory — not a method. Returns a zero-arg callable that selects the best
living non-owner enemy each frame using a weighted distance score.

```python
make_nearest_enemy_getter(owner_ref, all_tanks_getter, low_hp_priority_weight=0.5) -> callable
```

**Scoring formula:**
```python
effective_dist = real_dist * max(0.1, 1.0 - (weight * (1.0 - hp_ratio)))
```

`weight=0.0` → pure nearest-distance. `weight=1.2` → near-dead tanks effectively appear
10× closer. A target at 600px with 20% HP has effective distance ≈ 24px at weight=1.2.

**Target stickiness:** Once a target's `health_ratio < 0.40`, the getter locks onto them
(via `_cached_target[0]` closure cell) until they die or recover above 0.40. Prevents
wounded tanks from escaping by temporarily being out-ranged.

`all_tanks_getter` is evaluated fresh on every call — dead tanks are excluded dynamically
via the `is_alive` check, not by rebuilding the list.

#### low_hp_priority_weight (v0.32)

Difficulty parameter read from `ai_difficulty.yaml`:
- **easy** = 0.0 — pure distance targeting, ignores HP
- **medium** = 0.5 — mild preference for wounded targets
- **hard** = 1.2 — aggressively hunts near-dead tanks

Stored as `AIController.low_hp_priority_weight` and passed to `make_nearest_enemy_getter`
during the post-loop wiring pass in `GameplayScene.on_enter()`.

---

#### Pickup Awareness (v0.20)

AI seeks pickups based on state:
- **EVADE**: Health-seeking within `AI_PICKUP_SEEK_RANGE` (550px) — only `"health"` type
- **PATROL/PURSUE**: Opportunistic grab within `AI_PICKUP_OPPORTUNISTIC_RANGE` (150px) — any type
- **ATTACK**: Ignores pickups

`_nearest_pickup(max_range, type_filter=None)` scans live pickups from the injected getter.

---

### CollisionSystem (game/systems/collision.py)

#### Constants

```
TANK_RADIUS: float = 22.0
BULLET_RADIUS: float = 5.0
PICKUP_RADIUS: float = 14.0
```

#### Main Entry Point

```python
update(tanks: list, bullets: list, obstacles: list, pickups: list,
       explosions: list = None) -> tuple[list, list, list]
```

Returns `(events, new_explosions, new_pools)` — events is a list of audio event strings and
stat-tracking tuples; new_explosions is a list of Explosion entities created by
explosive bullet detonations (v0.22); new_pools is a list of GroundPool entities
created by pool-spawning bullet impacts (v0.26).

#### Dispatch Methods

| Method | What It Checks | Side Effects |
|--------|---------------|--------------|
| `_bullets_vs_tanks(bullets, tanks)` | Circle-circle: bullet vs each tank (skips owner) | Calls `tank.take_damage()`, `bullet.destroy()` (or pierce: decrement pierce_count, skip destroy) (v0.25) |
| `_bullets_vs_obstacles(bullets, obstacles)` | Circle-rect: bullet vs each obstacle | Calls `obs.take_damage()`, `bullet.destroy()` or `_reflect_bullet()` |
| `_tanks_vs_obstacles(tanks, obstacles)` | Circle-rect: tank vs each obstacle | Calls `_push_tank_out()` — repositioning only, no damage |
| `_tanks_vs_tanks(tanks)` | Circle-circle: all unique tank pairs | Calls `_push_tanks_apart()` — repositioning only, no damage |
| `_tanks_vs_pickups(tanks, pickups)` | Circle-circle: tank vs each pickup | Calls `pickup.apply(tank)` |

#### Audio Events Emitted

| Event | Type | Emitted When |
|-------|------|-------------|
| `"bullet_hit_tank"` | str | Bullet hits tank (tank survives) |
| `"tank_explosion"` | str | Bullet kills tank |
| `"bullet_hit_obstacle"` | str | Bullet hits obstacle (not destroyed) |
| `"obstacle_destroy"` | str | Bullet destroys obstacle |
| `"tank_collision"` | str | Two tanks overlap |
| `"explosion"` | str | Explosive bullet detonates (v0.22) |
| `"concussion_hit"` | str | Concussion blast knockback applied to tank (v0.26) |
| `("bullet_hit_tank_stat", owner, damage, damage_type)` | tuple | Every bullet-tank hit (for stat tracking); damage_type is DamageType enum (v0.21) |

Note: `_tanks_vs_obstacles` and `_tanks_vs_pickups` emit no audio events.

Explosive bullets (`is_explosive=True`) create Explosion entities instead of dealing
direct damage. Three detonation triggers: tank contact, obstacle contact, max_range reached.
Explosions are resolved via `explosion.resolve_damage()` which returns additional events.

#### Pool Spawning (v0.26)

Pool-spawning bullets (`spawns_pool=True`) create GroundPool entities on impact (tank or obstacle hit)
or at max range (`_pool_detonated` flag). Pools are added to `_pending_pools` and returned
in the 3-tuple. Pool fields on Bullet: `pool_type`, `pool_radius`, `pool_duration`, `pool_slow`,
`pool_dps`, `pool_color`.

#### Knockback Application (v0.26)

After damage and combat effects, bullets with `knockback_force > 0` apply impulse to surviving
tanks via `tank.apply_knockback(force, angle)`. Direction: atan2 from bullet→tank (pushes away).

#### Combat Effect Application (v0.23)

Module-level mapping `_DAMAGE_TYPE_TO_EFFECT` maps `DamageType.FIRE → "fire"`, `ICE → "ice"`,
`POISON → "poison"`, `ELECTRIC → "electric"`. STANDARD and EXPLOSIVE have no mapping.

`_apply_combat_effect(tank, damage_type)` — called after `tank.take_damage()` in both
`check_bullet_vs_tank()` and `Explosion.resolve_damage()`. Only applied if tank is still alive.
Loads status effect configs lazily from `data/configs/status_effects.yaml` via `_get_status_configs()`.

#### Bullet Reflection (`_reflect_bullet`)

When a bullet with `bounces_remaining > 0` hits an obstacle:
1. Determine penetration axis (horizontal vs vertical) from overlap geometry
2. Compute surface normal from penetration direction
3. Call `bullet.reflect(nx, ny)` which applies `v' = v - 2(v*n)n`
4. Nudge bullet out of obstacle to prevent re-collision

If `bounces_remaining == 0`, bullet is destroyed instead.

#### Static Helpers

```python
circles_overlap(pos_a, r_a, pos_b, r_b) -> bool
circle_vs_rect(circle_pos, radius, rect) -> bool
```

---

### RaycastSystem (game/systems/raycast.py) (v0.25)

Standalone module — no class, three functions.

```python
cast_ray(origin_x, origin_y, angle_deg, max_range, tanks, obstacles,
         ignore_tank=None) -> dict
```

Returns `{"hit": bool, "hit_type": "tank"|"obstacle"|"none", "entity": ...,
"hit_x": ..., "hit_y": ..., "distance": ..., "end_x": ..., "end_y": ...}`.

Tests obstacles first (line-vs-AABB slab method via `_line_vs_aabb`), then tanks
(line-vs-circle quadratic via `_line_vs_circle`). Returns nearest hit within
`max_range`. Dead entities and `ignore_tank` are skipped.

Used by `GameplayScene._resolve_beam()` every frame the laser beam is active.
`TANK_RADIUS` imported locally from `game.systems.collision` to avoid circular import.

---

### GroundPoolSystem (game/systems/ground_pool_system.py) (v0.26)

Applies ground pool effects to tanks each frame. Separate from CollisionSystem because pools are floor effects, not solid objects.

```python
GroundPoolSystem()
system.update(pools: list, tanks: list, dt: float) -> list[str]  # returns audio events
```

Per-frame logic for each alive pool × alive tank (owner immune):
- If `pool.slow_mult < 1.0`: `tank.apply_status("pool_slow", slow_mult, 0.15)` — expires 0.15s after leaving pool
- If `pool.dps > 0`: `tank.take_damage(max(1, int(dps * dt)), DamageType.FIRE)` + `tank.apply_combat_effect("fire", config)` — fire status loads lazily from `status_effects.yaml`

Tank integration: `pool_slow` checked in `Tank.update()` alongside `speed_boost`:
```python
if self.has_status("pool_slow"):
    effective_speed *= self._status_effects["pool_slow"]["value"]
```

---

### WeaponRoller (game/systems/weapon_roller.py) (v0.25.5)

Weighted random weapon selection for loadout slots 1-2 (indices 1-2). Slot 0 defaults to
`standard_shell` from the roller but is player-editable in LoadoutScene via LEFT/RIGHT cycling.

#### Construction

```python
WeaponRoller(unlocked_weapons: list[str])
```

Loads weights from `data/configs/weapon_weights.yaml`. Pool = unlocked weapons that have
a weight entry (standard_shell excluded — it's the slot 0 default, not a random candidate).

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `roll()` | `list[str\|None]` | 3-element loadout: `["standard_shell", <random>, <random>]`. No duplicates in slots 1-2. Falls back to None if pool exhausted. |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `pool_size` | `int` | Number of weapons in the random pool |

#### Weight Schema (`data/configs/weapon_weights.yaml`)

```yaml
spread_shot: 30        # COMMON (≥25)
bouncing_round: 25     # COMMON
cryo_round: 20         # UNCOMMON (≥18)
poison_shell: 20       # UNCOMMON
flamethrower: 18       # UNCOMMON
emp_blast: 15          # RARE (≥12)
grenade_launcher: 12   # RARE
homing_missile: 10     # EPIC (≥8)
railgun: 8             # EPIC
laser_beam: 6          # LEGENDARY (<8)
```

Rarity thresholds (display only, in `_get_rarity()` in loadout_scene.py):
≥25=COMMON, ≥18=UNCOMMON, ≥12=RARE, ≥8=EPIC, else=LEGENDARY.

#### LoadoutScene Integration

Two-step loadout flow (v0.25.5):
1. **Hull panel** — player navigates hulls with UP/DOWN. ENTER/TAB locks hull.
2. **Weapon panel** — weapons revealed with roll animation. Slot 0 cycles via LEFT/RIGHT
   (`_cycle_slot(0, ±1)` — reuses existing method with duplicate prevention). Slots 1-2
   are view-only random assignments. One re-roll via R key. Rarity labels on slots 1-2 only.
3. **Map panel** — standard map selection. ENTER confirms and starts match.

State fields: `_hull_locked`, `_weapons_revealed`. ESC when locked resets to hull.
ESC when unlocked exits to menu. Weapon tips from `weapons.yaml` displayed below stat bars.

#### Opponent Count Selector (v0.32)

Hull panel has two sub-rows controlled by `_hull_row: int` (0 = tank list, 1 = opponent count):

- **Navigation**: DOWN from last tank → opponent row; UP from first tank → opponent row (wrap);
  DOWN from opponent row → first tank; UP from opponent row → last tank.
- **LEFT/RIGHT** on opponent row cycles `_opponent_idx` through `_OPPONENT_COUNTS = [1, 2, 3]` with wrap.
- `_confirm()` passes `ai_count=_OPPONENT_COUNTS[self._opponent_idx]` to `SCENE_GAME`.
- Rendered as `Opponents: < N >` below the ultimate description; highlighted in neon pink when focused.

#### AI Random Loadouts

GameScene creates `WeaponRoller` for AI tanks, excluding hitscan weapons (`laser_beam`)
from the pool. AI tanks cycle weapons every 4-8 seconds via `_weapon_cycle_timer` in
AIController (injects `cycle_weapon` into TankInput when timer expires).

---

### InputHandler (game/systems/input_handler.py)

#### Construction

```python
InputHandler(keybinds: dict | None = None, camera=None, tank_position_getter=None)
```

#### Key Mappings (defaults)

| Action | Key | TankInput Field |
|--------|-----|-----------------|
| move_forward | W | throttle = +1.0 |
| move_backward | S | throttle = -1.0 |
| rotate_left | A | rotate = -1.0 |
| rotate_right | D | rotate = +1.0 |
| fire | SPACE | fire = True |
| ultimate | F | activate_ultimate = True (edge-detected) (v0.28) |
| cycle_next | TAB | cycle_weapon = +1 (edge-detected) |
| cycle_prev | Q | cycle_weapon = -1 (edge-detected) |
| cycle_next_alt | E | cycle_weapon = +1 (edge-detected) |
| mute | M | (handled by AudioManager, not TankInput) |

Additional weapon slot keys (hardcoded, not rebindable):
- `1` / `2` / `3` — direct slot selection via cycle_weapon

Mouse wheel: +1/-1 for weapon cycling (edge-detected per frame).

#### Turret Tracking

`_compute_turret_angle()`: Converts mouse screen position to world position via
`camera.screen_to_world()`, returns angle from tank center to that point.
Returns 0.0 if camera or position_getter not set.

#### Runtime Update

`update_keybinds(keybinds: dict)`: Apply new keybinds at runtime (from settings).

---

### PhysicsSystem (game/systems/physics.py)

```python
update(dt: float, tanks: list, bullets: list) -> None
```

1. Advance each bullet: calls `bullet.update(dt)`
2. Clamp each tank to arena bounds: `_clamp_tank(tank)` uses TANK_MOVEMENT_MARGIN (29px)
3. Check each bullet against arena boundary: `_check_bullet_boundary(bullet)` — destroys out-of-bounds bullets

**TODO** in `_check_bullet_boundary`: reflect logic for bouncing bullets at arena walls is not yet implemented.

---

### DebrisSystem (game/systems/debris_system.py)

#### DebrisParticle

```
__init__(x, y, vx, vy, size: int, color: tuple, lifetime: float)
```

Fields: `x, y, vx, vy, size, color, lifetime, age, rotation, rotation_speed`
Properties: `alpha -> int` (fade by remaining lifetime), `is_alive -> bool`

#### DebrisSystem

```python
spawn_debris(cx, cy, width, height, color, count) -> None
```

- Clamps count to MAX_DEBRIS_PARTICLES (200)
- Creates particles at center with random outward velocity (DEBRIS_SPEED_MIN to DEBRIS_SPEED_MAX)
- Prunes oldest particles if pool exceeds cap

```python
update(dt: float) -> None
```

Advances position, applies DEBRIS_GRAVITY (150 px/s^2), increments age, rotates, removes dead.

```python
draw(surface, camera) -> None
```

Renders all live particles via camera transform with alpha fade.

Property: `particle_count -> int`

---

### MatchCalculator (game/systems/match_calculator.py)

#### MatchResult (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| won | bool | Player won the match |
| survived | bool | Player tank alive at end |
| kills | int | AI tanks destroyed |
| shots_fired | int | Total bullets fired |
| shots_hit | int | Bullets that hit a tank |
| accuracy | float | shots_hit / shots_fired (0.0 if none fired) |
| time_elapsed | float | Seconds from match start to end |
| damage_dealt | int | Total damage dealt by player |
| damage_taken | int | Total damage player received |
| xp_earned | int | Filled by compute_xp() (default 0) |

#### Methods

```python
@staticmethod build(won, survived, kills, shots_fired, shots_hit,
                    time_elapsed, damage_dealt, damage_taken) -> MatchResult
```

Factory: calculates accuracy (safe for zero shots), fills xp_earned in one call.

```python
@staticmethod compute_xp(result: MatchResult) -> int
```

Formula: `XP_PARTICIPATION(10) + XP_WIN(100 if won) + XP_KILL(40) * kills + XP_SURVIVAL_BONUS(25 if survived) + int(accuracy * XP_ACCURACY_BONUS_MAX(50))`

---

### PickupSpawner (game/systems/pickup_spawner.py)

#### Construction

```python
PickupSpawner(spawn_points: list[tuple], pickup_configs: dict)
```

#### Methods

```python
update(dt: float) -> list[Pickup]
```

Each frame:
1. Tick active pickups (`pickup.update(dt)`)
2. Expire pickups where `age >= PICKUP_LIFETIME` (30s) — plays SFX_PICKUP_EXPIRE
3. Prune collected/expired pickups (`is_alive == False`)
4. Increment spawn timer; if `>= PICKUP_SPAWN_INTERVAL` (8s) and count < `PICKUP_MAX_ACTIVE` (4): call `_try_spawn()`
5. Return active pickups list

```python
_try_spawn() -> None
```

Selects a random unoccupied spawn point, filters out positions blocked by obstacles
(if `set_obstacles_getter()` was called), picks type via `_weighted_random_type()`,
creates Pickup instance, plays SFX_PICKUP_SPAWN. Skips spawn if no clear points remain (v0.22).

```python
_weighted_random_type() -> str
```

Uses `random.choices()` with `spawn_weight` from each pickup config.

Property: `active_pickups -> list[Pickup]`

#### Injection Points (v0.22)

| Method | Called By | Purpose |
|--------|-----------|---------|
| `set_obstacles_getter(getter)` | GameplayScene | Inject `() -> list[Obstacle]` for spawn validation |

---

### ProgressionManager (game/systems/progression_manager.py)

Stateless helper with lazy-loaded xp_table.

#### Construction

```python
ProgressionManager(xp_table_path: str = XP_TABLE_CONFIG)
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `apply_match_result(profile: dict, result: MatchResult)` | `tuple[dict, list[str]]` | Returns (new_profile, new_unlocks); never mutates input |
| `backfill_unlocks(profile: dict)` | `tuple[dict, list[str]]` | Scan xp_table for all unlocks ≤ player level, add missing ones; returns (new_profile, backfilled). Called by LoadoutScene on profile load (v0.22) |
| `compute_level(xp: int)` | `int` | Level for given cumulative XP |
| `xp_for_level(level: int)` | `int` | Cumulative XP required to reach level |
| `next_level_xp(xp: int)` | `int \| None` | XP for next level, None if max |
| `unlock_level_for(item_id: str)` | `int \| None` | Level at which item unlocks, None if not in table |

`apply_match_result` updates: xp, level, unlocked_tanks, unlocked_weapons,
total_matches, wins/losses. Item IDs ending in `_tank` go to unlocked_tanks;
all others to unlocked_weapons.

---

## 4. Scene Lifecycle

### BaseScene Interface (game/scenes/base_scene.py)

```python
__init__(manager: SceneManager)
on_enter(**kwargs) -> None      # Called when scene becomes active
on_exit() -> None               # Called before deactivation
handle_event(event) -> None     # Process pygame event
update(dt: float) -> None       # Update logic each frame
draw(surface) -> None           # Render to surface
```

### SceneManager (game/scenes/__init__.py)

```python
register(key: str, scene: BaseScene) -> None
switch_to(key: str, **kwargs) -> None    # Calls current.on_exit(), new.on_enter(**kwargs)
handle_event(event) -> None              # Routes to active scene
update(dt: float) -> None                # Routes to active scene
draw(surface) -> None                    # Routes to active scene
```

### Scene Registration (game/engine.py)

```python
SCENE_PROFILE_SELECT  → ProfileSelectScene
SCENE_MENU            → MainMenuScene
SCENE_LOADOUT         → LoadoutScene
SCENE_GAME            → GameplayScene
SCENE_SETTINGS        → SettingsScene
SCENE_GAME_OVER       → GameOverScene
```

Initial scene: `SCENE_MENU`. SaveManager auto-creates default profile on first run.

Main loop: `dt = min(clock.tick(FPS) / 1000.0, 0.05)` — capped at 50ms.

### Scene Flow Diagram

```
ProfileSelectScene()
  ← "SWITCH PROFILE" from MenuScene
  loads: profiles index from disk
  → select/create profile → MenuScene()

MenuScene()
  loads: active profile from SaveManager
  → "PLAY"             → LoadoutScene()
  → "SETTINGS"         → SettingsScene()
  → "SWITCH PROFILE"   → ProfileSelectScene()

LoadoutScene()
  loads: tanks.yaml, weapons.yaml, weapon_weights.yaml, xp_table.yaml, all map YAMLs via MapLoader
  flow: HULL (lock) → WEAPONS (reveal + slot 1 choice + optional reroll) → MAP → confirm
  → "START" → GameplayScene(
      tank_type: str,
      weapon_types: list[str],
      map_name: str,
      ai_count: int   # from opponent selector, default 1 (v0.32)
    )
  → ESC (hull locked) → reset to hull
  → ESC (hull unlocked) → MenuScene()

GameplayScene(tank_type, weapon_types, map_name, ai_count=1)
  loads: tanks.yaml, weapons.yaml, pickups.yaml, ai_difficulty.yaml, ultimates.yaml
         map YAML via MapLoader, theme via ThemeLoader, settings (keybinds, AI difficulty)
  creates: Camera, InputHandler, Tank (player + 1-3 AI), PhysicsSystem,
           CollisionSystem, DebrisSystem, PickupSpawner, HUD
  AI hull types: _AI_TANK_TYPES[i % 3] rotation (light/medium/heavy) (v0.32)

#### Speed Trail History (v0.20)

`_speed_trail_history: dict[int, list[tuple[float, float]]]` — keyed by `id(tank)`,
stores recent world positions sampled every 30ms while speed-boosted. Max 6 points.
Used by `_draw_tank_effects()` to render physics-based speed lines that curve
organically during turns. Trail auto-clears when speed boost expires or tank stops.

#### Shield Pop Detection (v0.20)

`_had_shield: dict[int, bool]` — tracks which tanks had shield last frame. When a
tank transitions from shield → no-shield, spawns debris particles and plays `SFX_SHIELD_POP`.

#### Watch Mode (v0.32)

`_watch_mode: bool` — set True when the player tank dies. While active:
- Camera follows the living AI tank nearest to arena center rather than the player.
- Match ends (→ GAME_OVER with `won=False`) when `len(living_ai) <= 1`.
- ESC or ENTER in `handle_event()` call `_end_match(won=False)` to skip.
- `draw()` calls `hud.draw_watch_overlay(surface)` to render the "WATCHING" banner.

When player is alive and all AI die, `_end_match(won=True)` is called normally.

`_end_match(won: bool)` is a centralized helper that calls
`switch_to(SCENE_GAME_OVER, result=MatchCalculator.build(...))`, replacing the duplicate
win/lose switch_to calls that existed before v0.32.

#### AI Tank Type Rotation (v0.32)

```python
_AI_TANK_TYPES: list[str] = ["light_tank", "medium_tank", "heavy_tank"]
```

AI tanks are assigned hull type by `_AI_TANK_TYPES[i % len(_AI_TANK_TYPES)]` in the spawn
loop, giving visual and behavioral variety in multi-opponent matches. AI health bars in HUD
are labeled "AI 1", "AI 2", "AI 3" (1-indexed).

#### Multi-AI Targeting Wire-Up (v0.32)

After the AI spawn loop, a two-pass wiring step assigns each AI controller its own
`make_nearest_enemy_getter` targeting all tanks (player + all AI):

```python
_all_tanks_getter = lambda: [self._tank] + self._ai_tanks
for _ctrl, _ai_tank in zip(self._ai_controllers, self._ai_tanks):
    _ctrl._target_getter = make_nearest_enemy_getter(
        _ai_tank, _all_tanks_getter,
        low_hp_priority_weight=_ctrl.low_hp_priority_weight,
    )
```

The lambda captures `self._ai_tanks` by reference — dynamically-dead tanks are excluded
per call via the `is_alive` filter inside `_getter`. The two-pass approach avoids the
chicken-and-egg problem of needing all tanks to exist before wiring any getter.

#### Ultimate Systems (v0.28)

**Shield Dome** (`_shield_domes: list[dict]`): Created when medium_tank activates ultimate.
Dict keys: `tank`, `x`, `y`, `radius`, `hp`, `max_hp`, `timer`, `color`. Dome follows tank
each frame. Intercepts bullets before collision system — bullets within dome radius from
non-owner tanks are destroyed and dome HP reduced. Dome expires when timer or HP reach 0.
Rendered as translucent circle with HP-based alpha + border.

**Artillery Strike** (`_pending_artillery: list[dict]`): Created when heavy_tank activates
ultimate. `count` entries (default 5) staggered by `stagger_delay` (0.3s). If player → target
is reticle world position; if AI → target is nearest enemy position. Random scatter within
`strike_area` (250px). Each entry spawns an `Explosion(DamageType.STANDARD)` when delay reaches 0.
`_artillery_warnings`: parallel list for red warning circle VFX with shrinking inner dot.

**Cloak Rendering**: In `_draw_tank()`, cloaked tanks render with `set_alpha(40)` (near-invisible).
Player's own cloak uses same alpha. AI loses target tracking on cloaked tanks (→PATROL).

**Activation Flash** (`_ult_flash_timer`, `_ult_flash_color`): 0.3s screen-wide color overlay
triggered on any ultimate activation.

**Charge from Damage**: After damage tracking, calls `owner.ultimate.add_damage_charge(dmg)` for
both bullet hits and beam damage.

  ai_count: from LoadoutScene opponent selector (1-3), capped at _MAX_AI
  → all AI dead while player alive → GameOverScene(result: MatchResult, won=True)
  → player dies     → Watch Mode (camera follows remaining AI) (v0.32)
  → last AI dies / ENTER / ESC in watch mode → GameOverScene(won=False) (v0.32)

GameOverScene(result: MatchResult)
  loads: active profile, applies progression via ProgressionManager
  saves: updated profile
  → ENTER or ESC → MenuScene()

SettingsScene()
  loads: settings from SaveManager
  sections: AUDIO / DISPLAY / CONTROLS / GAMEPLAY
  saves: settings on change
  → ESC or BACK → MenuScene()
```

---

## 5. Audio System

### AudioManager (game/ui/audio_manager.py)

Singleton: `get_audio_manager() -> AudioManager`

Initializes pygame.mixer: 44100 Hz, 16-bit, stereo, 512 buffer, 16 channels.

#### Methods

| Method | Description |
|--------|-------------|
| `play_music(path: str, loop: bool = True)` | Crossfade (1000ms fadeout) + load + play |
| `stop_music()` | Fadeout 1000ms; also calls `stop_all_layers()` |
| `play_sfx(path: str)` | Lazy-load, cache, play at master * sfx volume |
| `set_volume(channel: str, value: float)` | channel = "master" / "music" / "sfx"; clamped [0, 1]; updates layer volumes |
| `toggle_mute() -> bool` | Store/restore pre-mute volumes; returns True if now muted |
| `start_music_layer(name, path, fade_ms=500)` | Start looping audio layer on dedicated channel |
| `stop_music_layer(name, fade_ms=800)` | Fade out and remove named layer |
| `stop_all_layers(fade_ms=500)` | Stop all active music layers (scene exit cleanup) |

Property: `is_muted -> bool`

Volume hierarchy: effective volume = master_volume * channel_volume.

#### Music Layer System (v0.20)

Per-pickup looping audio overlays that play on dedicated `pygame.mixer.Sound` channels
alongside the base music stream (`pygame.mixer.music`). Multiple layers can play simultaneously.

Layer volume: `master * music_vol * _LAYER_VOLUME_SCALE` (1.0 — mixing via generator amplitude).

Layers are cached in `_layer_cache` (path → Sound), tracked in `_active_layers` (name → Sound)
and `_layer_channels` (name → Channel). `STATUS_MUSIC_LAYERS` dict (renamed from `PICKUP_MUSIC_LAYERS` in v0.23) maps status type → WAV path.

| Layer | Status Type | Audio Character |
|-------|-------------|-----------------|
| `layer_speed.wav` | speed_boost | Buzzy double-time arpeggio |
| `layer_heartbeat.wav` | regen | Heavy lub-DUB heartbeat with click transients |
| `layer_underwater.wav` | shield | Dreamy underwater warble |
| `layer_rapid_reload.wav` | rapid_reload | Mechanical tick loop with drone |
| `layer_burning.wav` | fire | Crackling fire loop with low rumble (v0.23) |
| `layer_frozen.wav` | ice | Crystalline wind shimmer with breathy noise (v0.23) |

GameplayScene tracks `_active_buff_layers: set[str]` — each frame computes active statuses
(both pickup and combat) via set difference, starts new layers, stops expired ones. `on_exit()` calls `stop_all_layers()`.

#### Combat Effect SFX (v0.23)

`COMBAT_EFFECT_SFX` dict maps effect type → WAV path. Onset SFX plays once when a new combat effect first appears. Tracked via `_active_combat_sfx: set[str]` in GameplayScene.

| SFX | Effect | Audio Character |
|-----|--------|-----------------|
| `sfx_effect_fire.wav` | fire | Whoosh ignition |
| `sfx_effect_poison.wav` | poison | Bubbling hiss |
| `sfx_effect_ice.wav` | ice | Crystal crack + ring |
| `sfx_effect_electric.wav` | electric | Buzzy zap |

Mute toggle: M key (handled in InputHandler key mapping, routed by GameplayScene).

### Procedural Audio Generation (scripts/generate_audio.py)

Standalone script — run manually: `python scripts/generate_audio.py`

#### Oscillators

```python
sine(t: float, freq: float) -> float
square(t: float, freq: float, duty: float = 0.5) -> float
sawtooth(t: float, freq: float) -> float
triangle(t: float, freq: float) -> float
noise() -> float                                      # uniform [-1, 1]
```

#### Envelope

```python
adsr(t, duration, attack=0.01, decay=0.05, sustain_level=0.7, release=0.1) -> float
```

#### Output

```python
_write_wav(path: str, samples: list[float]) -> None   # floats [-1, 1] → 16-bit mono WAV
```

#### Music Builder

```python
_note_freq(semitones_from_a4: int) -> float            # A4 = 440 Hz
_PENTA_AM = [0, 3, 5, 7, 10, 12, 15, 17]              # A minor pentatonic offsets

_arpeggio(sr, bpm, bars, bass_pattern, arp_pattern, pad_chords, beat_dur) -> list[float]
```

Builds synthwave pattern: kick + snare + bass line + arpeggio + pad chords. Normalizes to peak.

#### Generator Functions

| Function | Duration | Description |
|----------|----------|-------------|
| `gen_tank_fire(sr)` | 0.35s | Noise burst + low thump |
| `gen_bullet_hit_tank(sr)` | 0.25s | Metallic clang |
| `gen_bullet_hit_obstacle(sr)` | 0.18s | Dull thud |
| `gen_obstacle_destroy(sr)` | 0.45s | Crunch/rubble |
| `gen_tank_explosion(sr)` | 1.2s | Big explosion |
| `gen_tank_collision(sr)` | 0.3s | Heavy clunk |
| `gen_explosion(sr)` | 0.6s | AoE explosion: bass thump + pressure wave + crackle (v0.22) |
| `gen_ui_navigate(sr)` | 0.08s | Short blip up |
| `gen_ui_confirm(sr)` | 0.22s | Two-tone chime |
| `gen_pickup_spawn(sr)` | 0.3s | Rising C5-E5-G5 arpeggio |
| `gen_pickup_collect(sr)` | 0.2s | Bright G5-C6 ding |
| `gen_pickup_expire(sr)` | 0.4s | Soft E5-C5 descending |
| `gen_sfx_ult_speed_burst(sr)` | 0.5s | Rising sine sweep + square harmonics + noise (v0.28) |
| `gen_sfx_ult_shield_dome(sr)` | 0.6s | Expanding sine sweep + shimmer resonance (v0.28) |
| `gen_sfx_ult_artillery(sr)` | 0.8s | Descending whistle + deep boom (v0.28) |
| `gen_sfx_ult_cloak(sr)` | 0.5s | Descending filtered noise + quiet hum (v0.28) |
| `gen_music_menu(sr)` | 8 bars | 80 BPM atmospheric Am |
| `gen_music_gameplay(sr)` | 8 bars | 120 BPM driving Am |
| `gen_music_game_over(sr)` | 4 bars | 70 BPM melancholic descending |

Output paths: `assets/sounds/sfx_*.wav`, `assets/music/music_*.wav`

All path constants defined in `constants.py` as `SFX_*` and `MUSIC_*`.

---

## 6. YAML Config Schemas

### data/configs/tanks.yaml

Top-level: `dict[str, TankConfig]`

```yaml
TankConfig:
  type: str              # Must match key
  speed: float           # Px/s movement speed
  health: int            # Hit points
  turn_rate: float       # Degrees/s hull rotation
  fire_rate: float       # Shots per second
  description: str       # UI display text
  default_weapons: list  # Weapon type IDs or null per slot
```

Example:
```yaml
light_tank:
  type: light_tank
  speed: 200
  health: 80
  turn_rate: 180
  fire_rate: 1.5
  description: "Fast and agile, but fragile."
  default_weapons: [standard_shell, spread_shot, null]
```

All defined: light_tank (200/80/1.5), medium_tank (150/120/1.0),
heavy_tank (90/220/0.6), scout_tank (260/60/2.0).

---

### data/configs/weapons.yaml

Top-level: `dict[str, WeaponConfig]`

```yaml
WeaponConfig:
  type: str              # Must match key
  damage: int            # HP per hit
  speed: int             # Bullet px/s
  fire_rate: float       # Shots per second (drives per-slot cooldown)
  max_bounces: int       # Wall bounces (0 = none)
  max_range: int         # Px before auto-despawn
  description: str       # UI display text
  spread_count: int      # (spread_shot only) Number of projectiles
  spread_angle: int      # (spread_shot only) Degrees between bullets
  tracking_strength: float  # (homing_missile only) Turn rate multiplier
  damage_type: str       # DamageType name: standard/fire/ice/poison/electric/explosive
  aoe_radius: int        # (emp_blast, grenade_launcher) Blast radius in px
  aoe_falloff: float     # (aoe weapons) Damage multiplier at edge
  pierce_count: int      # (railgun) Remaining tank pierces (bullet survives first N hits)
  hitscan: bool          # (laser_beam) Uses raycast instead of projectile
  energy_max: float      # (hitscan) Energy pool capacity
  energy_drain_rate: float    # (hitscan) Energy drained per second while firing
  energy_recharge_rate: float # (hitscan) Energy recharged per second while idle
  energy_min_to_fire: float   # (hitscan) Minimum energy required to start firing
  dps: float             # (hitscan) Damage per second applied on hit
```

Example:
```yaml
standard_shell:
  type: standard_shell
  damage: 25
  speed: 420
  fire_rate: 1.0
  max_bounces: 0
  max_range: 1400
  description: "Reliable all-purpose round."
```

All defined: standard_shell (25/420/1.0), spread_shot (15/380/0.8, 3 at 12deg),
bouncing_round (20/400/0.9, 3 bounces), homing_missile (50/240/0.4, tracking 2.5),
grenade_launcher (70/280/0.25, 120px AoE) (v0.22),
cryo_round (20/360/0.7, ice), poison_shell (12/350/0.8, poison),
flamethrower (6/300/6.0, fire, 3-spread 12deg, 250px range),
emp_blast (30/300/0.3, electric, 140px AoE),
railgun (65/800/0.2, pierce_count=1),
laser_beam (hitscan=true, dps=45, energy_max=100, drain=30/s, recharge=15/s) (v0.25).

---

### data/configs/ultimates.yaml (v0.28)

Top-level: `dict[str, UltimateConfig]` — keyed by tank type.

```yaml
UltimateConfig:
  charge_max: float           # Charge required to activate (100.0 for all)
  charge_per_damage: float    # Charge per point of damage dealt
  charge_per_hit: float       # Charge per point of damage received
  charge_passive_rate: float  # Charge per second (passive)
  ability_type: str           # speed_burst | shield_dome | artillery_strike | cloak
  duration: float             # Seconds active (0 = instant, e.g. artillery)
  color: [int, int, int]      # VFX / HUD tint
  description: str            # UI display text
  sfx_key: str                # Key into ULTIMATE_SFX dict
  # Type-specific fields:
  speed_multiplier: float     # (speed_burst, cloak) Speed mult while active
  fire_rate_multiplier: float # (speed_burst) Fire rate mult while active
  dome_radius: float          # (shield_dome) Dome radius in px
  dome_hp: float              # (shield_dome) Dome hit points
  explosion_count: int        # (artillery_strike) Number of explosions
  explosion_radius: float     # (artillery_strike) Per-explosion radius
  explosion_damage: int       # (artillery_strike) Per-explosion damage
  strike_area: float          # (artillery_strike) Scatter radius
  stagger_delay: float        # (artillery_strike) Seconds between explosions
```

All defined:
- **light_tank** → `speed_burst` (Overdrive): 4s, 2.5× speed, 2× fire rate
- **medium_tank** → `shield_dome` (Fortress): 5s, 120px radius, 200 HP dome
- **heavy_tank** → `artillery_strike` (Barrage): instant, 5 explosions in 250px area, 80 dmg each
- **scout_tank** → `cloak` (Phantom): 5s, 1.3× speed, invisible, firing breaks cloak

---

### data/configs/materials.yaml

Top-level: `dict[str, MaterialConfig]`

```yaml
MaterialConfig:
  display_name: str       # UI label
  hp: int                 # Hit points (9999 = indestructible)
  destructible: bool      # Can take damage
  damage_filters: list    # Damage types that apply (empty = all)
  color: [int, int, int]  # Base RGB
```

Example:
```yaml
brick:
  display_name: "Brick"
  hp: 150
  destructible: true
  damage_filters: []
  color: [160, 75, 45]
```

All defined: stone (400, destructible, partial_destruction→rubble), brick (150), wood (60),
reinforced_steel (250, explosive-only), crate (40), rubble (80) (v0.22).

---

### data/configs/ai_difficulty.yaml

Top-level: `dict[str, DifficultyConfig]`

```yaml
DifficultyConfig:
  reaction_time: float          # Seconds before AI reacts (lower = sharper)
  accuracy: float               # [0.0, 1.0] shot accuracy
  aggression: float             # [0.0, 1.0] fire probability per frame
  evasion_threshold: float      # Health ratio to enter EVADE state
  low_hp_priority_weight: float # Distance discount for low-HP targets (v0.32)
```

Example:
```yaml
medium:
  reaction_time: 0.40
  accuracy: 0.72
  aggression: 0.55
  evasion_threshold: 0.35
  low_hp_priority_weight: 0.5
```

All defined: easy (0.80/0.45/0.25/0.20/0.0), medium (0.40/0.72/0.55/0.35/0.5),
hard (0.15/0.92/0.85/0.55/1.2).

---

### data/configs/pickups.yaml

Top-level: `dict[str, PickupConfig]`

```yaml
PickupConfig:
  display_name: str       # UI label
  value: float            # Effect magnitude
  color: [int, int, int]  # RGB for rendering
  radius: int             # Collision radius
  spawn_weight: int       # Relative spawn probability
```

Example:
```yaml
health:
  display_name: "Health Pack"
  value: 40
  color: [80, 200, 80]
  radius: 18
  spawn_weight: 3
```

All defined: health (40 HP, weight 3), rapid_reload (1, weight 2),
speed_boost (1.6x, weight 1).

---

### data/progression/xp_table.yaml

Top-level: `{ levels: list[LevelEntry] }`

```yaml
LevelEntry:
  level: int              # Level number
  xp_required: int        # Cumulative XP threshold
  unlocks: list[str]      # Item IDs unlocked at this level
```

Example:
```yaml
- level: 5
  xp_required: 1200
  unlocks:
    - heavy_tank
```

All levels: 1(0), 2(150), 3(350, medium_tank), 4(700, spread_shot),
5(1200, heavy_tank), 6(2000, bouncing_round), 7(3000, scout_tank),
8(4500, homing_missile), 9(6500, grenade_launcher), 10(9000, cryo_round),
11(12000, poison_shell), 12(15500, flamethrower), 13(19500), 14(23000, emp_blast),
15(28000), 16(33000, railgun), 17(39500), 18(46000, laser_beam) (v0.25).

---

### data/maps/map_*.yaml

Top-level: `{ name, theme, obstacles, pickup_spawns }`

```yaml
name: str                           # Display name
theme: str                          # Theme ID (key into data/themes/)
obstacles:
  - x: int                          # Top-left X
    y: int                          # Top-left Y
    width: int                      # Width px
    height: int                     # Height px
    material_type: str              # Key into materials.yaml
    reflective: bool                # Reserved for future use
pickup_spawns:
  - {x: int, y: int}               # World-space spawn locations
```

| Map | Name | Theme | Obstacles | Pickups |
|-----|------|-------|-----------|---------|
| map_01 | Headquarters | default | 8 (incl. 2 reinforced_steel) | 5 |
| map_02 | Dunes | desert | 7 | 5 |
| map_03 | Tundra | snow | 12 | 5 |

Arena size is always 1600x1200 (from ARENA_WIDTH/ARENA_HEIGHT constants).

---

### data/themes/*.yaml

Top-level: `ThemeConfig`

```yaml
ThemeConfig:
  name: str                         # Display name
  floor_color: [int, int, int]      # Arena floor RGB
  floor_grid_color: [int, int, int] # Grid overlay RGB
  border_color: [int, int, int]     # Arena border RGB
  border_thickness: int             # Border width px
  obstacle_tint: [int, int, int]    # Blended 50/50 with material base_color
  ambient_label: str                # Short mood descriptor for UI
  music_override: str | null        # Music file path override (null = default)
```

| Theme | Floor | Tint | Label |
|-------|-------|------|-------|
| default | [20, 30, 20] | [100, 100, 100] | Classic |
| desert | [194, 154, 108] | [200, 160, 100] | Arid |
| island | [194, 178, 128] | [160, 140, 100] | Coastal |
| jungle | [45, 80, 40] | [60, 100, 50] | Dense |
| snow | [220, 230, 240] | [200, 210, 225] | Frozen |
| urban | [80, 80, 85] | [90, 90, 95] | Downtown |

ThemeLoader falls back: requested theme → default.yaml → hardcoded defaults.

---

## 7. Constants Reference

All constants in `game/utils/constants.py`. Grouped by domain.

### Display & Camera

| Constant | Value | Note |
|----------|-------|------|
| SCREEN_WIDTH | 1280 | |
| SCREEN_HEIGHT | 720 | |
| FPS | 60 | |
| TITLE | "Tank Battle" | |
| GAME_VERSION | "v0.32.0" | |
| CAMERA_LERP_SPEED | 6.0 | Smooth follow rate |
| SUPPORTED_RESOLUTIONS | [(1280,720), (1600,900), (1920,1080)] | |

### Arena & Physics

| Constant | Value | Note |
|----------|-------|------|
| ARENA_WIDTH | 1600 | World-space px |
| ARENA_HEIGHT | 1200 | |
| ARENA_FLOOR_COLOR | (28, 35, 28) | |
| ARENA_BORDER_COLOR | (70, 90, 70) | |
| ARENA_BORDER_THICKNESS | 4 | |
| ARENA_GRID_STEP | 100 | |
| ARENA_GRID_COLOR | (38, 48, 38) | |
| ARENA_PADDING | 32 | |
| DEFAULT_TANK_SPEED | 150.0 | Px/s |
| DEFAULT_TANK_TURN_RATE | 120.0 | Deg/s |
| DEFAULT_TANK_HEALTH | 100 | |
| DEFAULT_BULLET_SPEED | 400.0 | Px/s |
| DEFAULT_FIRE_RATE | 1.0 | Shots/s |
| TANK_MOVEMENT_MARGIN | 29 | Arena clamp margin |

### Tank Rendering

| Constant | Value | Note |
|----------|-------|------|
| TANK_BODY_WIDTH | 40 | |
| TANK_BODY_HEIGHT | 30 | |
| TANK_BARREL_LENGTH | 22 | |
| TANK_BARREL_WIDTH | 6 | |
| TANK_BARREL_HEIGHT | 8 | |
| TANK_BARREL_COLOR | (55, 55, 55) | |
| TANK_PLAYER_COLOR | (100, 160, 80) | |
| TANK_DEFAULT_TYPE | "medium_tank" | |
| TANK_FRONT_STRIPE_WIDTH | 2 | |
| TANK_FRONT_STRIPE_BRIGHTEN | 60 | Added to base color |
| TANK_SELECT_COLORS | dict | Per-type RGB mapping |

### Weapons & Bullets

| Constant | Value | Note |
|----------|-------|------|
| DEFAULT_WEAPON_TYPE | "standard_shell" | |
| MAX_WEAPON_SLOTS | 3 | |
| BULLET_RADIUS | 5 | |
| BULLET_COLOR | (255, 220, 50) | Fallback; prefer DAMAGE_TYPE_BULLET_COLORS |
| BULLET_DEFAULT_MAX_RANGE | 1400.0 | |
| DAMAGE_TYPE_BULLET_COLORS | dict | Per-DamageType RGB: STANDARD yellow, EXPLOSIVE orange, FIRE red, ICE blue, POISON green, ELECTRIC purple (v0.21) |
| WEAPON_CARD_COLORS | dict | Per-weapon RGB — 11 weapons (v0.25) |
| WEAPON_STAT_MAX | dict | damage:70, speed:800, fire_rate:6.0, max_range:2400 (v0.25) |
| MAX_BAR_WIDTH | 120 | UI stat bar width |
| TANK_STAT_MAX | dict | Tank stat bar max values |

### AI Behavior

| Constant | Value | Note |
|----------|-------|------|
| AI_DETECTION_RANGE | 800.0 | PATROL → PURSUE (raised from 550 in v0.32) |
| AI_ATTACK_RANGE | 375.0 | PURSUE → ATTACK |
| AI_EVASION_HEALTH_RATIO | 0.30 | Default evasion threshold |
| AI_PICKUP_SEEK_RANGE | 550.0 | EVADE health-seek range (matches detection range) |
| AI_PICKUP_OPPORTUNISTIC_RANGE | 150.0 | PATROL/PURSUE grab-if-nearby range |
| AI_SPAWN_POSITIONS | list of 3 tuples | Fixed spawn locations |

### Pickups

| Constant | Value | Note |
|----------|-------|------|
| PICKUP_SPAWN_INTERVAL | 8.0 | Seconds between spawns |
| PICKUP_MAX_ACTIVE | 4 | |
| PICKUP_EFFECT_DURATION | 8.0 | Shared: HoT, speed boost |
| PICKUP_LIFETIME | 30.0 | Seconds before expiry |
| PICKUP_RENDER_RADIUS | 26 | |
| PICKUP_PULSE_SPEED | 4.0 | Oscillation rate |
| PICKUP_PULSE_AMPLITUDE | 0.15 | |
| PICKUP_GLOW_ALPHA | 40 | |
| PICKUP_GLOW_SCALE | 1.5 | |
| SHIELD_DEFAULT_DURATION | 12.0 | Shield buff duration |
| SHIELD_DEFAULT_HP | 60.0 | Default shield hit points |
| SPEED_BOOST_DURATION | 5.0 | **DEPRECATED v0.19** — use PICKUP_EFFECT_DURATION |

### Audio

| Constant | Value | Note |
|----------|-------|------|
| MUSIC_VOLUME_DEFAULT | 0.5 | |
| SFX_VOLUME_DEFAULT | 0.5 | |
| MASTER_VOLUME_DEFAULT | 0.5 | |
| AUDIO_CHANNELS | 16 | Mixer channels |
| MUSIC_FADEOUT_MS | 1000 | Crossfade duration |
| SFX_TANK_FIRE | assets/sounds/sfx_tank_fire.wav | |
| SFX_BULLET_HIT_TANK | assets/sounds/sfx_bullet_hit_tank.wav | |
| SFX_BULLET_HIT_OBSTACLE | assets/sounds/sfx_bullet_hit_obstacle.wav | |
| SFX_OBSTACLE_DESTROY | assets/sounds/sfx_obstacle_destroy.wav | |
| SFX_TANK_EXPLOSION | assets/sounds/sfx_tank_explosion.wav | |
| SFX_TANK_COLLISION | assets/sounds/sfx_tank_collision.wav | |
| SFX_UI_NAVIGATE | assets/sounds/sfx_ui_navigate.wav | |
| SFX_UI_CONFIRM | assets/sounds/sfx_ui_confirm.wav | |
| SFX_PICKUP_SPAWN | assets/sounds/sfx_pickup_spawn.wav | |
| SFX_PICKUP_COLLECT | assets/sounds/sfx_pickup_collect.wav | |
| SFX_PICKUP_EXPIRE | assets/sounds/sfx_pickup_expire.wav | |
| MUSIC_MENU | assets/music/music_menu.wav | |
| MUSIC_GAMEPLAY | assets/music/music_gameplay.wav | |
| MUSIC_GAME_OVER | assets/music/music_game_over.wav | |
| MUSIC_LAYER_SPEED | assets/music/layer_speed.wav | Speed boost layer |
| MUSIC_LAYER_HEARTBEAT | assets/music/layer_heartbeat.wav | Regen layer |
| MUSIC_LAYER_UNDERWATER | assets/music/layer_underwater.wav | Shield layer |
| MUSIC_LAYER_RAPID_RELOAD | assets/music/layer_rapid_reload.wav | Reload layer |
| STATUS_MUSIC_LAYERS | dict | Maps status type → layer WAV path (renamed from PICKUP_MUSIC_LAYERS in v0.23) |
| PICKUP_MUSIC_LAYERS | dict | Backwards compat alias for STATUS_MUSIC_LAYERS |
| SFX_PICKUP_HEALTH | assets/sounds/sfx_pickup_health.wav | |
| SFX_PICKUP_SPEED | assets/sounds/sfx_pickup_speed.wav | |
| SFX_PICKUP_RELOAD | assets/sounds/sfx_pickup_reload.wav | |
| SFX_PICKUP_SHIELD | assets/sounds/sfx_pickup_shield.wav | |
| SFX_EXPLOSION | assets/sounds/sfx_explosion.wav | AoE explosion SFX (v0.22) |
| SFX_SHIELD_POP | assets/sounds/sfx_shield_pop.wav | Shield break SFX |
| MUSIC_LAYER_BURNING | assets/music/layer_burning.wav | Fire combat effect layer (v0.23) |
| MUSIC_LAYER_FROZEN | assets/music/layer_frozen.wav | Ice combat effect layer (v0.23) |
| SFX_EFFECT_FIRE | assets/sounds/sfx_effect_fire.wav | Fire effect onset SFX (v0.23) |
| SFX_EFFECT_POISON | assets/sounds/sfx_effect_poison.wav | Poison effect onset SFX (v0.23) |
| SFX_EFFECT_ICE | assets/sounds/sfx_effect_ice.wav | Ice effect onset SFX (v0.23) |
| SFX_EFFECT_ELECTRIC | assets/sounds/sfx_effect_electric.wav | Electric effect onset SFX (v0.23) |
| COMBAT_EFFECT_SFX | dict | Maps effect type → onset SFX path (v0.23) |
| STATUS_EFFECTS_CONFIG | data/configs/status_effects.yaml | Combat effect config path (v0.23) |
| ELEMENTAL_INTERACTIONS_CONFIG | data/configs/elemental_interactions.yaml | Elemental combo config path (v0.24) |
| SFX_STEAM_BURST | assets/sounds/sfx_steam_burst.wav | Steam burst combo SFX (v0.24) |
| SFX_ACCELERATED_BURN | assets/sounds/sfx_accelerated_burn.wav | Accelerated burn combo SFX (v0.24) |
| SFX_DEEP_FREEZE | assets/sounds/sfx_deep_freeze.wav | Deep freeze combo SFX (v0.24) |
| COMBO_SFX | dict | Maps combo name → SFX WAV path (v0.24) |
| PICKUP_COLLECT_SFX | dict | Maps pickup type → collect SFX path |
| SFX_RAILGUN_FIRE | str | assets/sounds/sfx_railgun_fire.wav (v0.25) |
| SFX_LASER_HUM | str | assets/sounds/sfx_laser_hum.wav — looping layer (v0.25) |
| SFX_ULT_SPEED_BURST | str | assets/sounds/sfx_ult_speed_burst.wav (v0.28) |
| SFX_ULT_SHIELD_DOME | str | assets/sounds/sfx_ult_shield_dome.wav (v0.28) |
| SFX_ULT_ARTILLERY | str | assets/sounds/sfx_ult_artillery.wav (v0.28) |
| SFX_ULT_CLOAK | str | assets/sounds/sfx_ult_cloak.wav (v0.28) |
| ULTIMATE_SFX | dict | Maps sfx_key → ultimate SFX WAV path (v0.28) |

### UI / HUD

| Constant | Value | Note |
|----------|-------|------|
| HUD_MARGIN | 12 | |
| HUD_BOTTOM_MARGIN | 12 | |
| HUD_BAR_WIDTH | 160 | |
| HUD_BAR_HEIGHT | 16 | |
| RETICLE_RADIUS | 8 | |
| RETICLE_LINE_LENGTH | 12 | |
| RETICLE_COLOR | COLOR_NEON_PINK | |
| BUFF_ICON_OFFSET_Y | 20 | Above tank |
| BUFF_ICON_FONT_SIZE | 14 | |
| BUFF_ICON_SPACING | 16 | |
| WATCH_MODE_OVERLAY_COLOR | (220, 220, 80) | "WATCHING" banner text color (v0.32) |
| WATCH_MODE_OVERLAY_ALPHA | 160 | Background box alpha (v0.32) |
| WATCH_MODE_OVERLAY_PADDING | 12 | Box padding px (v0.32) |
| WATCH_MODE_OVERLAY_Y | 60 | Banner Y position from top (v0.32) |
| MENU_GRID_SPEED | 60 | Perspective grid scroll |
| MENU_TITLE_ANIM_DURATION | 0.8 | |
| MENU_FADE_DURATION | 0.3 | |
| SETTINGS_SLIDER_WIDTH | 200 | |
| SETTINGS_STEP_VOLUME | 0.05 | |
| SETTINGS_SECTION_COLOR | (181, 137, 0) | |

### Scene Names

| Constant | Value | Note |
|----------|-------|------|
| SCENE_PROFILE_SELECT | "profile_select" | |
| SCENE_MENU | "menu" | |
| SCENE_LOADOUT | "loadout" | |
| SCENE_GAME | "game" | |
| SCENE_SETTINGS | "settings" | |
| SCENE_GAME_OVER | "game_over" | |
| SCENE_TANK_SELECT | "tank_select" | **DEPRECATED v0.17.5** |
| SCENE_WEAPON_SELECT | "weapon_select" | **DEPRECATED v0.17.5** |
| SCENE_MAP_SELECT | "map_select" | **DEPRECATED v0.17.5** |
| LOADOUT_PANEL_HULL | 0 | |
| LOADOUT_PANEL_WEAPONS | 1 | |
| LOADOUT_PANEL_MAP | 2 | |
| LOADOUT_PANEL_COUNT | 3 | |

### File Paths

| Constant | Value |
|----------|-------|
| DATA_DIR | "data" |
| CONFIG_DIR | "data/configs" |
| MAPS_DIR | "data/maps" |
| THEMES_DIR | "data/themes" |
| DEFAULT_MAP | "map_01" |
| DEFAULT_THEME | "default" |
| SAVES_DIR | "saves" |
| LOGS_DIR | "logs" |
| LOG_FILE | "logs/tank_battle.log" |
| PROFILES_INDEX_FILE | "saves/profiles.json" |
| PROFILES_DIR | "saves/profiles" |
| SETTINGS_FILE | "saves/settings.json" |
| TANKS_CONFIG | "data/configs/tanks.yaml" |
| ULTIMATES_CONFIG | "data/configs/ultimates.yaml" |
| WEAPONS_CONFIG | "data/configs/weapons.yaml" |
| MATERIALS_CONFIG | "data/configs/materials.yaml" |
| PICKUPS_CONFIG | "data/configs/pickups.yaml" |
| AI_DIFFICULTY_CONFIG | "data/configs/ai_difficulty.yaml" |
| XP_TABLE_CONFIG | "data/progression/xp_table.yaml" |
| THEME_TINT_BLEND | 0.5 |

### XP & Progression

| Constant | Value | Note |
|----------|-------|------|
| XP_PARTICIPATION | 10 | Base XP per match |
| XP_WIN | 100 | Bonus for winning |
| XP_KILL | 40 | Per AI kill |
| XP_SURVIVAL_BONUS | 25 | If player survived |
| XP_ACCURACY_BONUS_MAX | 50 | Scaled by accuracy |
| PROFILE_NAME_MAX_LEN | 12 | |
| MAX_PROFILES | 4 | |

### Keybinds

| Constant | Value | Note |
|----------|-------|------|
| KEYBIND_CYCLE_NEXT | 9 | pygame.K_TAB |
| KEYBIND_CYCLE_PREV | 113 | pygame.K_q |
| KEYBIND_CYCLE_NEXT_ALT | 101 | pygame.K_e |
| KEYBIND_SLOT_1 | 49 | pygame.K_1 |
| KEYBIND_SLOT_2 | 50 | pygame.K_2 |
| KEYBIND_SLOT_3 | 51 | pygame.K_3 |

### Colors

| Constant | Value |
|----------|-------|
| COLOR_BLACK | (0, 0, 0) |
| COLOR_WHITE | (255, 255, 255) |
| COLOR_RED | (220, 50, 47) |
| COLOR_GREEN | (133, 153, 0) |
| COLOR_BLUE | (38, 139, 210) |
| COLOR_YELLOW | (181, 137, 0) |
| COLOR_GRAY | (88, 110, 117) |
| COLOR_DARK_GRAY | (40, 40, 40) |
| COLOR_BG | (20, 20, 20) |
| COLOR_NEON_PINK | (255, 16, 240) |

### Obstacles & Debris

| Constant | Value | Note |
|----------|-------|------|
| OBSTACLE_COLOR | (72, 68, 50) | Default obstacle RGB |
| OBSTACLE_BORDER_COLOR | (110, 105, 80) | |
| OBSTACLE_DAMAGED_COLOR | (28, 26, 22) | |
| MAX_DEBRIS_PARTICLES | 200 | Pool cap |
| DEBRIS_GRAVITY | 150.0 | Px/s^2 |
| DEBRIS_FADE_MIN | 0.4 | Lifetime range min |
| DEBRIS_FADE_MAX | 0.7 | Lifetime range max |
| DEBRIS_SPEED_MIN | 80.0 | Px/s |
| DEBRIS_SPEED_MAX | 200.0 | Px/s |
| DEBRIS_COUNT | dict | Per-material particle counts |
| DEBRIS_COUNT_DEFAULT | 6 | |
| HIT_FLASH_DURATION | 0.15 | Seconds |
| HIT_FLASH_BLEND | 0.6 | White blend factor |
| DAMAGE_DARKEN_MEDIUM | 0.25 | Color darken at 33-66% HP |
| DAMAGE_DARKEN_CRITICAL | 0.50 | Color darken below 33% HP |
| DAMAGE_CRACK_DARKEN | 0.7 | Crack overlay darken factor |

### Deprecated

| Constant | Value | Deprecated In | Replacement |
|----------|-------|---------------|-------------|
| SPEED_BOOST_DURATION | 5.0 | v0.19 | PICKUP_EFFECT_DURATION |
| COLLISION_DAMAGE_FRONT | 5 | v0.18 | Removed — no collision damage |
| COLLISION_DAMAGE_SIDE | 20 | v0.18 | Removed |
| COLLISION_DAMAGE_REAR | 12 | v0.18 | Removed |
| COLLISION_SPEED_SCALE | 150.0 | v0.18 | Removed |
| COLLISION_SPEED_CAP | 1.5 | v0.18 | Removed |
| SCENE_TANK_SELECT | "tank_select" | v0.17.5 | SCENE_LOADOUT |
| SCENE_WEAPON_SELECT | "weapon_select" | v0.17.5 | SCENE_LOADOUT |
| SCENE_MAP_SELECT | "map_select" | v0.17.5 | SCENE_LOADOUT |

### Persistence Defaults

```python
DEFAULT_PROFILE = {
    "xp": 0, "level": 1,
    "unlocked_tanks": ["light_tank", "medium_tank"],
    "unlocked_weapons": ["standard_shell"],
    "total_matches": 0, "wins": 0, "losses": 0,
    "match_history": [],
}

DEFAULT_SETTINGS = {
    "resolution": [1280, 720],
    "master_volume": 0.5, "music_volume": 0.5, "sfx_volume": 0.5,
    "keybinds": {
        "move_forward": "w", "move_backward": "s",
        "rotate_left": "a", "rotate_right": "d",
        "fire": "space", "mute": "m", "pause": "escape",
    },
    "ai_difficulty": "medium",
    "fullscreen": False,
}
```

### Utility Functions (game/utils/math_utils.py)

```python
normalize(v: Vec2) -> Vec2
magnitude(v: Vec2) -> float
distance(a: Vec2, b: Vec2) -> float
angle_to(origin: Vec2, target: Vec2) -> float        # degrees, 0 = right, CW
angle_difference(a: float, b: float) -> float         # [-180, 180]
clamp(value, min_val, max_val) -> float
lerp(a, b, t) -> float
rotate_point(point, origin, angle_deg) -> Vec2
blend_colors(color_a, color_b, t) -> tuple[int, int, int]
heading_to_vec(angle_deg) -> Vec2
draw_rotated_rect(surface, color, center, width, height, angle_deg)
```

### Config Loader (game/utils/config_loader.py)

```python
load_yaml(path: str) -> dict                           # Never raises; returns {} on error
get_tank_config(tank_type: str, tanks_path: str) -> dict
get_weapon_config(weapon_type: str, weapons_path: str) -> dict
get_ai_config(difficulty: str, ai_path: str) -> dict
```
