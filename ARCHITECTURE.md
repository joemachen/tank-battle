# Architecture Reference

Living reference for prompt authors. Derived from source code — not comments,
not memory. If this file disagrees with the code, the code wins.

*Last updated: v0.19.0*

---

## 1. Project Structure

```
game/
  __init__.py                       Package root
  engine.py                         Main loop, scene registration, pygame init
  entities/
    __init__.py
    bullet.py                       Projectile entity with bounce + range
    obstacle.py                     Destructible/indestructible arena wall
    pickup.py                       Collectible pickup with pulse animation
    tank.py                         Tank entity, TankInput dataclass, status effects
  scenes/
    __init__.py                     SceneManager — scene registry + transitions
    base_scene.py                   Abstract base scene interface
    game_over_scene.py              Match result + XP progression display
    game_scene.py                   Main gameplay arena orchestrator
    loadout_scene.py                Unified hull/weapon/map selection screen
    map_select_scene.py             Deprecated v0.17.5 — merged into loadout
    menu_scene.py                   Main menu with synthwave grid background
    profile_select_scene.py         Four-slot profile picker
    settings_scene.py               Audio/display/controls/gameplay settings
    tank_select_scene.py            Deprecated v0.17.5 — merged into loadout
    weapon_select_scene.py          Deprecated v0.17.5 — merged into loadout
  systems/
    __init__.py
    ai_controller.py                State machine AI with stuck recovery
    collision.py                    All entity collision detection + resolution
    debris_system.py                Particle burst on obstacle destruction
    input_handler.py                Keyboard/mouse input → TankInput
    match_calculator.py             MatchResult factory + XP formula
    physics.py                      Bullet movement + arena boundary clamping
    pickup_spawner.py               Timed pickup spawn + lifetime management
    progression_manager.py          XP/level/unlock progression logic
  ui/
    __init__.py
    audio_manager.py                Singleton audio: SFX, music, volume control
    components.py                   ScrollingGrid, FadeTransition UI widgets
    hud.py                          In-game health bars + weapon slot display
  utils/
    __init__.py
    camera.py                       World-to-screen transform with lerp tracking
    config_loader.py                YAML loader + typed config getters
    constants.py                    All numeric/string constants — single source
    logger.py                       Rotating file + console logger factory
    map_loader.py                   Map YAML → obstacles + theme + spawn points
    math_utils.py                   Geometry: distance, angles, lerp, rotation
    save_manager.py                 Profile + settings JSON persistence
    stuck_detector.py               Rolling-window displacement detector for AI
    theme_loader.py                 Theme YAML loader with fallback chain

data/
  configs/
    ai_difficulty.yaml              Three AI difficulty tiers
    materials.yaml                  Five obstacle material definitions
    pickups.yaml                    Three pickup type definitions
    tanks.yaml                      Four tank type definitions
    weapons.yaml                    Four weapon type definitions
  maps/
    map_01.yaml                     "Headquarters" — default theme, 6 obstacles
    map_02.yaml                     "Dunes" — desert theme, 7 obstacles
    map_03.yaml                     "Tundra" — snow theme, 12 obstacles
  progression/
    xp_table.yaml                   10-level XP thresholds + unlock schedule
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
  test_debris.py                    Debris particle lifecycle + cap
  test_loadout.py                   Loadout scene selection logic
  test_map_loader.py                Map YAML parsing
  test_match_calculator.py          XP formula + MatchResult factory
  test_math_utils.py                Geometry utility functions
  test_obstacles.py                 Obstacle damage states + hit flash
  test_pickup.py                    Pickup apply effects + pulse animation
  test_pickup_spawner.py            Spawn timing + caps + lifetime
  test_profile_select.py            Profile slot management
  test_progression.py               XP table progression
  test_progression_manager.py       Level-up + unlock logic
  test_save_manager.py              JSON persistence
  test_settings.py                  Settings load/save
  test_stuck_detector.py            Stuck detection window logic
  test_tank_select.py               Tank selection (legacy)
  test_tank_status.py               Status effects: apply, tick, regen
  test_theme_loader.py              Theme loading + fallback
  test_turret.py                    Independent turret aiming
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

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt: float)` | `list` | Advance state; returns fire event list `[("fire", x, y, angle, weapon_config)]` |
| `take_damage(amount: int)` | `None` | Apply damage; sets is_alive=False at 0 HP |
| `load_weapons(configs: list[dict])` | `None` | Equip up to MAX_WEAPON_SLOTS weapons; rejects empty/duplicates |
| `cycle_weapon(direction: int)` | `None` | Cycle active slot (+1 next, -1 prev) with wrapping |
| `set_active_slot(index: int)` | `None` | Jump to slot by index; no-op if out of range |
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

Properties: `shield_hp -> float` (current shield HP or 0.0), `active_status_names -> list[str]` (names of active effects).

---

### Bullet (game/entities/bullet.py)

#### Construction

```python
Bullet(x: float, y: float, angle: float, owner: Tank, config: dict)
```

`config` keys: `speed`, `damage`, `max_bounces`, `max_range`, `type` (weapon_type).

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

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt: float)` | `None` | Track target (if homing), advance position, despawn if max_range exceeded |
| `reflect(normal_x: float, normal_y: float)` | `None` | Reflect velocity off surface normal; decrement bounces |
| `destroy()` | `None` | Mark for removal |
| `set_targets_getter(getter)` | `None` | Inject callable returning list of alive tanks for homing |

#### Homing Tracking (`_track_target`)

Called automatically by `update()`. No-op when `_tracking_strength == 0` or no targets getter.
Finds nearest alive non-owner tank, computes desired angle, rotates heading by
`tracking_strength * dt` radians/sec toward target. Updates `_dx`, `_dy`, `angle`.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| position | tuple[float, float] | (x, y) |

---

### Obstacle (game/entities/obstacle.py)

#### Construction

```python
Obstacle(x: float, y: float, width: float, height: float,
         material_type: str = "stone", material_config: dict | None = None,
         reflective: bool = False)
```

`material_config` keys: `hp`, `destructible`, `damage_filters`, `color`.

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

#### Public Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update(dt: float)` | `None` | Decrement hit-flash timer |
| `take_damage(amount: int, damage_type: str = "standard")` | `None` | Apply damage (guarded by destructible + damage_filters); triggers hit flash |
| `destroy()` | `None` | Force-destroy if destructible |

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
| health_ratio <= evasion_threshold | EVADE |
| dist <= AI_ATTACK_RANGE (375) | ATTACK |
| dist <= AI_DETECTION_RANGE (550) | PURSUE |
| else | PATROL |

Priority: EVADE > ATTACK > PURSUE > PATROL (evaluated top-to-bottom).

#### Per-State Input Methods

| Method | throttle | rotate | fire | turret_angle |
|--------|----------|--------|------|--------------|
| `_patrol_input()` | 0.5 | 0.3 | False | hull angle |
| `_pursue_input(target)` | 0.3-1.0 (heading-dependent) | ±1.0 toward target | False | tracks player |
| `_attack_input(target)` | 0.0 | ±1.0 toward target | accuracy-jittered aim + aggression roll | jittered aim |
| `_evade_input(target)` | 1.0 (forward = away) | ±1.0 toward flee angle | True if dist <= ATTACK_RANGE and aggression roll | tracks player |
| `_recovery_input()` | Phase 1: -1.0, Phase 2: 0.7 | alternating direction | False | hull angle |

**Stub:** `_patrol_input()` is a simple rotation stub — waypoint patrol planned for later.

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
update(tanks: list, bullets: list, obstacles: list, pickups: list) -> list
```

Returns a list of audio event strings and stat-tracking tuples.

#### Dispatch Methods

| Method | What It Checks | Side Effects |
|--------|---------------|--------------|
| `_bullets_vs_tanks(bullets, tanks)` | Circle-circle: bullet vs each tank (skips owner) | Calls `tank.take_damage()`, `bullet.destroy()` |
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
| `("bullet_hit_tank_stat", owner, damage)` | tuple | Every bullet-tank hit (for stat tracking) |

Note: `_tanks_vs_obstacles` and `_tanks_vs_pickups` emit no audio events.

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

Selects a random unoccupied spawn point, picks type via `_weighted_random_type()`,
creates Pickup instance, plays SFX_PICKUP_SPAWN.

```python
_weighted_random_type() -> str
```

Uses `random.choices()` with `spawn_weight` from each pickup config.

Property: `active_pickups -> list[Pickup]`

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
  loads: tanks.yaml, weapons.yaml, xp_table.yaml, all map YAMLs via MapLoader
  → "START" → GameplayScene(
      tank_type: str,
      weapon_types: list[str],
      map_name: str
    )
  → ESC → MenuScene()

GameplayScene(tank_type, weapon_types, map_name, ai_count)
  loads: tanks.yaml, weapons.yaml, pickups.yaml, ai_difficulty.yaml,
         map YAML via MapLoader, theme via ThemeLoader, settings (keybinds, AI difficulty)
  creates: Camera, InputHandler, Tank (player + AI), PhysicsSystem,
           CollisionSystem, DebrisSystem, PickupSpawner, HUD

#### Speed Trail History (v0.20)

`_speed_trail_history: dict[int, list[tuple[float, float]]]` — keyed by `id(tank)`,
stores recent world positions sampled every 30ms while speed-boosted. Max 6 points.
Used by `_draw_tank_effects()` to render physics-based speed lines that curve
organically during turns. Trail auto-clears when speed boost expires or tank stops.

#### Shield Pop Detection (v0.20)

`_had_shield: dict[int, bool]` — tracks which tanks had shield last frame. When a
tank transitions from shield → no-shield, spawns debris particles and plays `SFX_SHIELD_POP`.
  ai_count: from settings or default, capped at 3
  → player dies     → GameOverScene(result: MatchResult)
  → all AI dead     → GameOverScene(result: MatchResult)

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
and `_layer_channels` (name → Channel). `PICKUP_MUSIC_LAYERS` dict maps pickup type → WAV path.

| Layer | Pickup Type | Audio Character |
|-------|-------------|-----------------|
| `layer_speed.wav` | speed_boost | Buzzy double-time arpeggio |
| `layer_heartbeat.wav` | regen | Heavy lub-DUB heartbeat with click transients |
| `layer_underwater.wav` | shield | Dreamy underwater warble |
| `layer_rapid_reload.wav` | rapid_reload | Mechanical tick loop with drone |

GameplayScene tracks `_active_buff_layers: set[str]` — each frame computes active buffs
via set difference, starts new layers, stops expired ones. `on_exit()` calls `stop_all_layers()`.

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
| `gen_ui_navigate(sr)` | 0.08s | Short blip up |
| `gen_ui_confirm(sr)` | 0.22s | Two-tone chime |
| `gen_pickup_spawn(sr)` | 0.3s | Rising C5-E5-G5 arpeggio |
| `gen_pickup_collect(sr)` | 0.2s | Bright G5-C6 ding |
| `gen_pickup_expire(sr)` | 0.4s | Soft E5-C5 descending |
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

All defined: standard_shell (25/420/1.0), spread_shot (15/380/0.8, 3 at 18deg),
bouncing_round (20/400/0.9, 3 bounces), homing_missile (50/240/0.4, tracking 2.5).

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

All defined: stone (9999, indestructible), brick (150), wood (60),
reinforced_steel (500, explosive-only), crate (40).

---

### data/configs/ai_difficulty.yaml

Top-level: `dict[str, DifficultyConfig]`

```yaml
DifficultyConfig:
  reaction_time: float     # Seconds before AI reacts (lower = sharper)
  accuracy: float          # [0.0, 1.0] shot accuracy
  aggression: float        # [0.0, 1.0] fire probability per frame
  evasion_threshold: float # Health ratio to enter EVADE state
```

Example:
```yaml
medium:
  reaction_time: 0.40
  accuracy: 0.72
  aggression: 0.55
  evasion_threshold: 0.35
```

All defined: easy (0.80/0.45/0.25/0.20), medium (0.40/0.72/0.55/0.35),
hard (0.15/0.92/0.85/0.55).

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
8(4500, homing_missile), 9(6500), 10(9000).

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
| map_01 | Headquarters | default | 6 | 5 |
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
| GAME_VERSION | "v0.19.0" | |
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
| BULLET_COLOR | (255, 220, 50) | |
| BULLET_DEFAULT_MAX_RANGE | 1400.0 | |
| WEAPON_CARD_COLORS | dict | Per-weapon RGB for UI |
| WEAPON_STAT_MAX | dict | Stat bar max values |
| MAX_BAR_WIDTH | 120 | UI stat bar width |
| TANK_STAT_MAX | dict | Tank stat bar max values |

### AI Behavior

| Constant | Value | Note |
|----------|-------|------|
| AI_DETECTION_RANGE | 550.0 | PATROL → PURSUE |
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
| PICKUP_MUSIC_LAYERS | dict | Maps pickup type → layer WAV path |
| SFX_PICKUP_HEALTH | assets/sounds/sfx_pickup_health.wav | |
| SFX_PICKUP_SPEED | assets/sounds/sfx_pickup_speed.wav | |
| SFX_PICKUP_RELOAD | assets/sounds/sfx_pickup_reload.wav | |
| SFX_PICKUP_SHIELD | assets/sounds/sfx_pickup_shield.wav | |
| SFX_SHIELD_POP | assets/sounds/sfx_shield_pop.wav | Shield break SFX |
| PICKUP_COLLECT_SFX | dict | Maps pickup type → collect SFX path |

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
