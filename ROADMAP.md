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
---
## 🔨 In Progress
| Branch                    | Milestone                                            |
|---------------------------|------------------------------------------------------|
| feature/defensive-pickups | v0.20 — Defensive pickups                            |
---
## 🗺️ Planned
### Phase 2 — Content Expansion
*More things to do and unlock.*
| Version | Milestone                          | Notes                                                                                                                                                                                                                                                                                                    |
|---------|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0.20   | Defensive pickups                 | Shields (absorb X damage), repair kits (regen over time), decoys (confuse AI targeting), EMP (brief area slow). All defined in pickup config.                                                                                                                                                            |
---
### Phase 3 — Elemental Weapon System
*Requires a new damage pipeline. The material damage_filters field in
materials.yaml was designed for this — this phase fills it in.*
| Version | Milestone                      | Notes                                                                                                                                                                                   |
|---------|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0.21   | Damage type system            | (was v0.20) Formalize damage types as an enum: STANDARD, EXPLOSIVE, FIRE, ICE, POISON, ELECTRIC. Bullet carries damage_type. CollisionSystem routes accordingly.                       |
| v0.22   | Area of effect + explosions   | (was v0.21) Explosive damage deals splash in a radius. New AoE resolver in CollisionSystem. Obstacles take AoE damage based on material filter.                                         |
| v0.23   | Status effects                | (was v0.22) Damage-over-time system: FIRE (burn ticks), POISON (slower ticks), ICE (movement slow), ELECTRIC (fire rate slow). StatusEffect class on Tank, resolved each frame.         |
| v0.24   | Elemental interactions        | (was v0.23) Fire + Ice = steam burst. Poison + Fire = accelerated burn. Ice + Electric = freeze. Defined in data/configs/elemental_interactions.yaml.                                   |
| v0.25   | Elemental weapons content     | (was v0.24) Flamethrower (fire, AoE cone), Cryo round (ice, slows), Poison shell (DoT), EMP blast (electric, AoE).                                                                     |
---
### Phase 4 — Ultimates System
*Overwatch-style ultimates that charge over time and interact with
the pickup/powerup system.*
| Version | Milestone                       | Notes                                                                                                                                                                       |
|---------|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0.26   | Ultimate charge system          | (was v0.25) UltimateCharge class on Tank. Charges by: dealing damage, taking damage, time elapsed. Charge rate and ultimate type defined per tank in tanks.yaml. HUD shows charge bar. |
| v0.27   | Ultimate abilities (first pass) | (was v0.26) Light = speed burst, Medium = shield dome, Heavy = artillery strike (AoE), Scout = cloak + speed.                                                               |
| v0.28   | Ultimate + pickup interactions  | (was v0.27) charge_boost, ultimate_amp, charge_rate_up pickups.                                                                                                             |
| v0.29   | Ultimate visual feedback        | (was v0.28) Charge bar animation, activation VFX, screen flash.                                                                                                             |
---
### Phase 5 — AI Upgrade
*Smarter, more varied opponents that use the full game system.*
| Version | Milestone                  | Notes                                                                              |
|---------|---------------------------|------------------------------------------------------------------------------------|
| v0.30   | AI-vs-AI targeting        | (was v0.29) Replace player-only target_getter with nearest_enemy_getter. Free-for-all mode enabled. |
| v0.31   | AI weapon awareness       | (was v0.30) AI behavior adapts to its equipped weapon type (e.g. bouncing round = indirect fire angles). |
| v0.32   | AI elemental awareness    | (was v0.31) AI prioritizes targets with active status effects it can combo.        |
| v0.33   | AI ultimate usage         | (was v0.32) AI activates ultimate when charge is full and combat conditions are met. |
| v0.34   | AI difficulty tuning pass | (was v0.33) Full review across all modes, maps, and opponent counts.               |
---
### Phase 6 — Progression & Campaign
*Reason to keep playing. Bosses unlock into sandbox.*
| Version | Milestone                       | Notes                                                                                                                             |
|---------|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| v0.35   | Full progression screen         | (was v0.34) Level, XP bar, visual unlock tree showing what's coming next.                                                         |
| v0.36   | Match history + stats           | (was v0.35) Win/loss record, accuracy, damage dealt/taken per match.                                                              |
| v0.37   | Achievement system              | (was v0.36) Cosmetic milestone achievements (first kill, 10 wins, etc.).                                                          |
| v0.38   | Boss tank encounters            | (was v0.37) Unique high-HP boss tanks with signature ultimates and specialized AI. Defined in data/configs/bosses.yaml. Defeating a boss unlocks it as a playable tank in sandbox mode. |
| v0.39   | Campaign mode                   | (was v0.38) Linear story missions with escalating difficulty and boss fights gated by progression. Narrative text in data/campaign/. |
| v0.40   | Sandbox unlocks from campaign   | (was v0.39) Bosses and campaign-exclusive tanks/weapons available in free play after unlock.                                       |
---
### Phase 7 — Online Multiplayer
*The biggest lift on the roadmap. Significant infrastructure work.*
*See architecture notes below before starting this phase.*
| Version | Milestone                    | Notes                                                                                                                                                                                    |
|---------|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0.41   | Network architecture design  | (was v0.40) Choose model: peer-to-peer vs authoritative server. Recommendation: authoritative server (server owns state, clients send inputs only). Library candidates: python-socketio or Twisted. Write a design doc before any code. |
| v0.42   | Input serialization          | (was v0.41) TankInput is already a clean dataclass — serializes trivially. This is the lucky part of the existing architecture.                                                          |
| v0.43   | Game state sync              | (was v0.42) Server broadcasts world state each tick. Clients render received state. Lag compensation and client-side prediction are the hard parts.                                       |
| v0.44   | Lobby + matchmaking          | (was v0.43) Room creation, join by code, player ready system.                                                                                                                            |
| v0.45   | Online sandbox mode          | (was v0.44) 1v1 and free-for-all online. Campaign and progression stay local.                                                                                                            |
| v0.46   | Online progression sync      | (was v0.45) Cloud save, cross-device profile.                                                                                                                                            |
---
### Phase 8 — Polish & Stretch
| Version | Milestone                        | Notes                                                                                                                                                                                                                                                                      |
|---------|----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0.47   | Particle effects + tank tracks   | (was v0.46) Muzzle flash, bullet impact, explosion, status effect visuals. Tank tracks: emit track mark sprites at fixed intervals behind moving tanks, fade over ~3 seconds using alpha decay, stored in bounded deque. Gives Wii Play Tanks style trail effect.           |
| v0.48   | Sprite art — toy/wooden aesthetic | (was v0.47) Replace placeholder rects with toy tank sprites. Reference: Wii Play Tanks. Chunky plastic tank bodies, wooden/material-appropriate obstacle textures, soft drop shadows under tanks and obstacles to sell "sitting on a table" feel. Material types (wood, brick, stone, steel) visually distinct. Asset-only change — no logic impact. |
| v0.49   | Local multiplayer                | (was v0.48) Second human player on same keyboard or controller.                                                                                                                                                                                                            |
| v0.50   | Controller support               | (was v0.49) Gamepad input via pygame joystick API. InputHandler abstraction makes this clean.                                                                                                                                                                              |
---
## 💡 Backlog
*Unscheduled. Revisit after Phase 4.*
- Fog of war / limited visibility
- Terrain deformation (craters from explosions that slow movement)
- Replay system
- Leaderboard
- Boss rush mode
- Custom tank builder (mix stats within a point budget)
- Destructible terrain that changes map layout mid-match
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

*Last updated: v0.19.0 — v0.19 pickup drops + polish completed;
v0.20 defensive pickups in progress*
