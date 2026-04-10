# Tank Battle — Development Roadmap
A living document. Version numbers are targets, not promises — order may
shift based on feel-testing and priorities. Update this file when milestones
are completed or plans change.
---
## ✅ Completed
| Tag     | Milestone                                                                      |
|---------|--------------------------------------------------------------------------------|
| v0.1.0  | Tank + movement + camera + floor grid                                          |
| v0.5.0  | Live AI combat + player death + dual HUD                                       |
| v0.6.0  | Arena obstacles + material system + bullet bounce                              |
| v0.7.0  | AI obstacle navigation + stuck recovery                                        |
| v0.8.0  | Pre-match tank selection + locked tank system                                  |
| v0.9.0  | AI difficulty select + multiple AI opponents + tank collision damage           |
| v0.10.0 | Audio — SFX + synthwave music per scene, M mute, procedural assets            |
| v0.11.0 | Match result + XP persistence — stat screen, level-up, unlock flow            |
| v0.12.0 | Main menu polish — perspective grid, glow title, fade transition               |
| v0.13.0 | Settings screen — audio sliders, keybinds, resolution, AI difficulty          |
| v0.13.5 | Profile selection — multi-save slots, SaveManager refactor, auto-login        |
| v0.14.0 | Weapon selection — pre-match picker, stat bars, animated preview, HUD display |
| v0.15.0 | Decoupled turret aiming + mouse reticle — turret_angle, barrel render, aim reticle |
| v0.16.0 | Secondary + tertiary weapons — 3-slot loadout, per-slot cooldowns, Tab/Q/E/wheel/1-3 |
| v0.17.0 | Multiple maps + environment themes — 3 maps, 6 themes, MapSelectScene |
| v0.17.5 | Unified LoadoutScene + profile auto-create — collapse 3-scene pre-match chain |
| v0.18.0 | Destructible obstacles — damage states, hit flash, debris particles, collision damage removed |
| v0.19.0 | Pickup drops + polish — health HoT, rapid reload, speed boost, SFX, buff icons, AI retreat fire, front stripe |
| v0.20.0 | Shield pickup, per-type VFX/SFX, music layers, AI pickup awareness, homing fix, arena bounce, themed walls |
| v0.21.0 | Damage type enum (STANDARD/EXPLOSIVE/FIRE/ICE/POISON/ELECTRIC), bullet colors, HUD dots, reinforced_steel on map_01, homing wall-hit fix |
| v0.22.0 | AoE explosions, grenade launcher, partial stone destruction, cooldown HUD, pickup spawn validation, retroactive unlock backfill |
| v0.23.0 | Combat status effects — FIRE burn DoT, POISON slow DoT, ICE movement slow, ELECTRIC fire rate reduction, StatusEffect class, VFX/SFX/music layers, HUD labels |
| v0.24.0 | Elemental interactions — Steam Burst (fire+ice AoE), Accelerated Burn (poison+fire instant), Deep Freeze (ice+electric stun), ElementalResolver, combo VFX/SFX/HUD |
| v0.25.0 | Six elemental + combat weapons — cryo round, poison shell, flamethrower, EMP blast, railgun (pierce), laser beam (hitscan + energy bar); raycast system; 18-level progression; WEAPON_STAT_MAX updated |
| v0.25.5 | Random weapon rolls + player-chosen slot 1 — WeaponRoller, weighted random slots 2-3, slot 1 player cycles from unlocked pool, hull-lock flow, re-roll, AI random loadouts + weapon cycling, rarity labels, weapon tips |
| v0.26.0 | Utility weapons — glue gun (area slow pool), lava gun (fire DPS pool), concussion blast (knockback); GroundPool entity, GroundPoolSystem, tank knockback physics, 21-level progression, 14 total weapons |
| v0.28.0 | Ultimate system — UltimateCharge class, 4 abilities (Overdrive/Fortress/Barrage/Phantom), charge from damage/hits/passive, F key activation, AI ultimate usage, shield dome, artillery strike, cloak + homing exclusion, HUD charge bar, 4 SFX; also: HP doubling, passive regen, health float accumulator, ground pool self-damage, laser nerf/audio fix, boundary detonations, DPS weapon guarantee |
| v0.32.0 | AI-vs-AI targeting + Watch Mode | make_nearest_enemy_getter factory, free-for-all targeting, Watch Mode on player death, opponent count selector, low-HP priority + target stickiness, center-seeking patrol, detection range 800px |
| v0.33.0 | Quick fixes — AI hull colors by type, concussive blast knockback, random map option, weapon rerolls 3×, ultimate reroll UI |
| v0.33.5 | Ultimate expansion — Lockdown + Disruptor ultimates, per-match random ult assignment, HUD charge bar polish, 959 tests |
| v0.34.0 | AI weapon awareness — 14 weapon profiles, 5 aim modes (direct/loose/lead/wall_bounce/pool_place), range band management, utility scoring with hysteresis, 1034 tests |
| v0.35.0 | 4-slot category-guaranteed loadout (Basic/Elemental/Heavy/Tactical), WeaponRoller rewrite, ultimate display moved to weapon panel, 1076 tests |
| v0.36.0 | AI elemental awareness — _combo_bonus() + _setup_bonus() in weapon scoring, elemental_awareness per difficulty tier (0/0.5/1.0), 1123 tests |
---
## 🔨 In Progress
| Branch                          | Milestone                                                                      |
|---------------------------------|--------------------------------------------------------------------------------|
| feature/ai-difficulty-tuning    | v0.37 — AI difficulty tuning pass: full review across all modes, maps, and opponent counts |
---
### Phase 3 — Elemental Weapon System
*Requires a new damage pipeline. The material damage_filters field in
materials.yaml was designed for this — this phase fills it in.*
| Version | Milestone                      | Notes                                                                                                                                                                                   |
|---------|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ~~v0.21~~ | ~~Damage type system~~      | ✅ Completed v0.21.0                                                                                                                                                                    |
| ~~v0.22~~ | ~~Area of effect + explosions~~ | ✅ Completed v0.22.0                                                                                                                                                                |
| ~~v0.23~~ | ~~Status effects~~          | ✅ Completed v0.23.0                                                                                                                                                                    |
| ~~v0.24~~ | ~~Elemental interactions~~ | ✅ Completed v0.24.0                                                                                                                                                                     |
| ~~v0.25~~ | ~~Elemental + combat weapons content~~ | ✅ Completed v0.25.0 |
| ~~v0.25.5~~ | ~~Random weapon rolls~~ | ✅ Completed v0.25.5 |
| ~~v0.26~~ | ~~Area denial + utility weapons~~ | ✅ Completed v0.26.0 |
---
### Phase 4 — Ultimates System
*Overwatch-style ultimates that charge over time and interact with
the pickup/powerup system.*
| Version | Milestone                       | Notes                                                                                                                                                                       |
|---------|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ~~v0.28~~ | ~~Ultimate charge system~~    | ✅ Completed v0.28.0 — shipped charge + 4 abilities + VFX + AI activation in one milestone |
| ~~v0.29~~ | ~~Ultimate abilities~~        | ✅ Shipped as part of v0.28.0 |
| ~~v0.30~~ | ~~Ultimate + pickup interactions~~ | Deferred to backlog (charge_boost, ultimate_amp pickups) |
| ~~v0.31~~ | ~~Ultimate visual feedback~~  | ✅ Shipped as part of v0.28.0 (charge bar, dome VFX, warning circles, cloak alpha) |
---
### Phase 5 — AI Upgrade
*Smarter, more varied opponents that use the full game system.*
| Version | Milestone                  | Notes                                                                              |
|---------|---------------------------|------------------------------------------------------------------------------------|
| ~~v0.32~~ | ~~AI-vs-AI targeting~~  | ✅ Completed v0.32.0 — nearest_enemy_getter, Watch Mode, opponent selector, low-HP priority, stickiness, center-seeking patrol |
| ~~v0.34~~ | ~~AI weapon awareness~~ | ✅ Completed v0.34.0 — 14 weapon profiles, 5 aim modes, range management, hysteresis switching |
| ~~v0.35~~ | ~~4-slot category loadout~~ | ✅ Completed v0.35.0 — Basic/Elemental/Heavy/Tactical guaranteed slots, WeaponRoller rewrite (scope shifted from original AI elemental awareness plan) |
| ~~v0.36~~ | ~~AI elemental awareness~~ | ✅ Completed v0.36.0 — _combo_bonus(), _setup_bonus(), elemental_awareness 0/0.5/1.0 per tier |
| ~~v0.36~~ | ~~AI ultimate usage~~   | ✅ Shipped as part of v0.28.0 — offensive ults in ATTACK, defensive in EVADE, cloak detection |
| v0.37   | AI difficulty tuning pass | Full review across all modes, maps, and opponent counts.               |
---
### Phase 6 — Progression & Campaign
*Reason to keep playing. Bosses unlock into sandbox.*
| Version | Milestone                       | Notes                                                                                                                             |
|---------|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| v0.38   | Full progression screen         | (was v0.37) Level, XP bar, visual unlock tree showing what's coming next.                                                         |
| v0.39   | Match history + stats           | (was v0.38) Win/loss record, accuracy, damage dealt/taken per match.                                                              |
| v0.40   | Achievement system              | (was v0.39) Cosmetic milestone achievements (first kill, 10 wins, etc.).                                                          |
| v0.41   | Boss tank encounters            | (was v0.40) Unique high-HP boss tanks with signature ultimates and specialized AI. Defined in data/configs/bosses.yaml. Defeating a boss unlocks it as a playable tank in sandbox mode. |
| v0.42   | Campaign mode                   | (was v0.41) Linear story missions with escalating difficulty and boss fights gated by progression. Narrative text in data/campaign/. |
| v0.43   | Sandbox unlocks from campaign   | (was v0.42) Bosses and campaign-exclusive tanks/weapons available in free play after unlock.                                       |
---
### Phase 7 — Online Multiplayer
*The biggest lift on the roadmap. Significant infrastructure work.*
*See architecture notes below before starting this phase.*
| Version | Milestone                    | Notes                                                                                                                                                                                    |
|---------|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0.44   | Network architecture design  | (was v0.43) Choose model: peer-to-peer vs authoritative server. Recommendation: authoritative server (server owns state, clients send inputs only). Library candidates: python-socketio or Twisted. Write a design doc before any code. |
| v0.45   | Input serialization          | (was v0.44) TankInput is already a clean dataclass — serializes trivially. This is the lucky part of the existing architecture.                                                          |
| v0.46   | Game state sync              | (was v0.45) Server broadcasts world state each tick. Clients render received state. Lag compensation and client-side prediction are the hard parts.                                       |
| v0.47   | Lobby + matchmaking          | (was v0.46) Room creation, join by code, player ready system.                                                                                                                            |
| v0.48   | Online sandbox mode          | (was v0.47) 1v1 and free-for-all online. Campaign and progression stay local.                                                                                                            |
| v0.49   | Online progression sync      | (was v0.48) Cloud save, cross-device profile.                                                                                                                                            |
---
### Phase 8 — Polish & Stretch
| Version | Milestone                        | Notes                                                                                                                                                                                                                                                                      |
|---------|----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0.50   | Particle effects + tank tracks   | (was v0.49) Muzzle flash, bullet impact, explosion, status effect visuals. Tank tracks: emit track mark sprites at fixed intervals behind moving tanks, fade over ~3 seconds using alpha decay, stored in bounded deque. Gives Wii Play Tanks style trail effect.           |
| v0.51   | Sprite art — toy/wooden aesthetic | (was v0.50) Replace placeholder rects with toy tank sprites. Reference: Wii Play Tanks. Chunky plastic tank bodies, wooden/material-appropriate obstacle textures, soft drop shadows under tanks and obstacles to sell "sitting on a table" feel. Material types (wood, brick, stone, steel) visually distinct. Asset-only change — no logic impact. |
| v0.52   | Local multiplayer                | (was v0.51) Second human player on same keyboard or controller.                                                                                                                                                                                                            |
| v0.53   | Controller support               | (was v0.52) Gamepad input via pygame joystick API. InputHandler abstraction makes this clean.                                                                                                                                                                              |
---
## 💡 Backlog
*Unscheduled ideas and deferred feedback. Revisit during relevant phases.*

### Weapons
- Shotgun blast — 6–8 pellets in tight cone, massive close-range damage, useless at distance
- Gravity well — slow-moving orb that pulls nearby bullets and tanks toward it, detonates after 3s
- Mine layer — drops invisible mine at tank position, detonates on enemy contact
- EMP redesign — current EMP deals electric AoE damage; redesign as area-denial: disables all movement and weapons for tanks within radius X for Y seconds (no damage). Needs new status effect type.

### Pickups
- Ghost tank decoy — spawns AI-controlled duplicate of player tank with its own HP (~40); attracts homing missiles as a valid target; moves in random patrol; visual match to player tank
- Invisibility — tank becomes ~20% alpha, removed from AI target lists, homing missiles lose lock; duration-limited with shimmer effect near expiry; triggers stealth music layer (Bond-esque low strings)

### Ultimates
- Expand to 6 total ultimates (currently 4)
- Randomize ultimate assignment per match like weapons (player sees what they got at loadout, no choice)
- Rock/paper/scissors synergy between ultimates — e.g. Phantom cloak counters Barrage (untargetable), Fortress blocks Barrage AoE, Overdrive outruns Fortress, etc. Design needed before implementation.
- Slower charge rate — ultimates currently build too fast; reduce passive charge rate and damage-dealt contribution across all tiers

### Maps
- Expand to 6 total maps (currently 3)
- Map themes to target: castle/medieval, wild west, space, fast food
- Chokepoints and skinny pathways — current maps are too open; new maps should force close-quarters encounters
- Partial destruction on stone walls — stone obstacles transition through damage states (full wall → rubble/half-wall → cleared) instead of binary alive/dead; rubble provides partial cover and opens new sightlines mid-match (Battlefield-style)

### AI
- AI retreat-to-cover — during EVADE, pathfind toward nearest obstacle for cover instead of fleeing in a straight line to a corner
---
## ⚠️ Architecture Notes
### Turret system (v0.15) decouples aim from movement
Tank class will gain a `turret_angle: float` field independent of `self.angle`.
InputHandler will gain mouse position tracking and world-space conversion
via the Camera transform. Bullet spawn direction uses `turret_angle`, not
`self.angle`. Rendering gains a second draw pass for the barrel on top of
the hull. AI controller already aims independently — minimal changes needed
for AIController.
### Multiplayer is the biggest structural risk
The current architecture is single-machine. Before Phase 7, the game loop
needs a clean separation between *input collection* and *state simulation*.
**Already multiplayer-friendly (by design):**
- TankInput as a dataclass — trivially serializable
- Controller injection pattern — server can inject remote inputs
- dt-based physics — deterministic given the same inputs
**Will need network-aware versions:**
- SceneManager (client vs server scene state)
- SaveManager (local vs cloud profile)
- AudioManager (client-only, no changes needed server-side)
Start thinking about this around Phase 5 so Phase 7 isn't a rewrite.
### Elemental interactions need a dedicated StatusSystem
The damage_filters field in materials.yaml was designed for elemental
damage. When implementing Phase 3, introduce a StatusSystem to manage
active effects on tanks — do not add this logic to CollisionSystem.
CollisionSystem handles hit detection only.
### Ultimates must be server-authoritative in multiplayer
Ultimate charge state is a cheat vector if resolved client-side.
Design the UltimateCharge class in Phase 4 with this in mind — keep
charge state as plain data that can be owned by a server later.

*Last updated: v0.36.0 — AI elemental awareness shipped; v0.37 AI difficulty tuning pass next on feature/ai-difficulty-tuning*
