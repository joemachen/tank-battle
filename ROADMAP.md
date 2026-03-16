# Tank Battle — Development Roadmap
A living document. Version numbers are targets, not promises — order may
shift based on feel-testing and priorities. Update this file when milestones
are completed or plans change.
---
## ✅ Completed
| Tag     | Milestone                                                             |
|---------|-----------------------------------------------------------------------|
| v0.1.0  | Tank + movement + camera + floor grid                                 |
| v0.5.0  | Live AI combat + player death + dual HUD                              |
| v0.6.0  | Arena obstacles + material system + bullet bounce                     |
| v0.7.0  | AI obstacle navigation + stuck recovery                               |
| v0.8.0  | Pre-match tank selection + locked tank system                         |
| v0.9.0  | AI difficulty select + multiple AI opponents + tank collision damage  |
| v0.10.0 | Audio — SFX + synthwave music per scene, M mute, procedural assets   |
---
## 🔨 In Progress
| Branch                   | Milestone                                              |
|--------------------------|--------------------------------------------------------|
| feature/xp-persistence   | v0.11 — Match result + XP persistence                 |
---
## 🗺️ Planned
### Phase 1 — Core Loop Polish
*Get the base game feeling complete before expanding content.*
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.11   | Match result + XP persistence | Score calculator, XP award on match end, level-up notification, SaveManager writes after every match. Unlocks become meaningful here. |
| v0.12   | Main menu polish       | Styled menu, animated transitions, game feels shippable from the front door. |
| v0.13   | Settings screen        | Volume sliders, keybind config, resolution, difficulty default.       |
---
### Phase 2 — Content Expansion
*More things to do and unlock.*
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.14   | Weapon selection       | Pre-match weapon picker, same pattern as tank select. All 4 weapons already in weapons.yaml. Primary slot only. |
| v0.15   | Secondary + tertiary weapons | Each tank has up to 3 weapon slots. Tab or Q/E to cycle. Weapon slots defined per tank type in tanks.yaml. |
| v0.16   | Multiple maps          | Map select screen, 2–3 maps with distinct layouts in data/maps/. MapLoader already handles this. |
| v0.17   | Destructible obstacles | Material system already supports it — needs visual destruction feedback (flash, crumble). |
| v0.18   | Pickup drops           | Health packs, ammo, speed boost. Pickup entity already exists in entities/pickup.py. |
| v0.19   | Defensive pickups      | Shields (absorb X damage), repair kits (regen over time), decoys (confuse AI targeting), EMP (brief area slow). All defined in pickup config. |
---
### Phase 3 — Elemental Weapon System
*Requires a new damage pipeline. The material damage_filters field in
materials.yaml was designed for this — this phase fills it in.*
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.20   | Damage type system     | Formalize damage types as an enum: STANDARD, EXPLOSIVE, FIRE, ICE, POISON, ELECTRIC. Bullet carries damage_type. CollisionSystem routes accordingly. |
| v0.21   | Area of effect + explosions | Explosive damage deals splash in a radius. New AoE resolver in CollisionSystem. Obstacles take AoE damage based on material filter. |
| v0.22   | Status effects         | Damage-over-time system: FIRE (burn ticks), POISON (slower ticks), ICE (movement slow), ELECTRIC (fire rate slow). StatusEffect class on Tank, resolved each frame. |
| v0.23   | Elemental interactions | Fire + Ice = steam burst (brief vision obscure). Poison + Fire = accelerated burn. Ice + Electric = freeze. Interactions defined in data/configs/elemental_interactions.yaml — fully data-driven. |
| v0.24   | Elemental weapons content | Wire new damage types into weapons.yaml: Flamethrower (fire, short range, AoE cone), Cryo round (ice, slows), Poison shell (DoT), EMP blast (electric, AoE). |
---
### Phase 4 — Ultimates System
*Overwatch-style ultimates that charge over time and interact with
the pickup/powerup system.*
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.25   | Ultimate charge system | UltimateCharge class on Tank. Charges by: dealing damage, taking damage, time elapsed. Charge rate and ultimate type defined per tank in tanks.yaml. HUD shows charge bar. |
| v0.26   | Ultimate abilities (first pass) | One unique ultimate per tank type: Light = speed burst, Medium = shield dome, Heavy = artillery strike (AoE), Scout = cloak + speed. |
| v0.27   | Ultimate + pickup interactions | Pickups can modify ultimate: charge_boost (fill % instantly), ultimate_amp (1.5× effect on next use), charge_rate_up (temporary multiplier). Defined in pickup config. |
| v0.28   | Ultimate visual feedback | Charge bar animation, activation VFX, screen flash on use.           |
---
### Phase 5 — AI Upgrade
*Smarter, more varied opponents that use the full game system.*
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.29   | AI-vs-AI targeting     | Replace player-only target_getter with nearest_enemy_getter. Free-for-all mode enabled. |
| v0.30   | AI weapon awareness    | AI behavior adapts to its equipped weapon type (e.g. bouncing round = indirect fire angles). |
| v0.31   | AI elemental awareness | AI prioritizes targets with active status effects it can combo.       |
| v0.32   | AI ultimate usage      | AI activates ultimate when charge is full and combat conditions are met. |
| v0.33   | AI difficulty tuning pass | Full review across all modes, maps, and opponent counts.            |
---
### Phase 6 — Progression & Campaign
*Reason to keep playing. Bosses unlock into sandbox.*
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.34   | Full progression screen | Level, XP bar, visual unlock tree showing what's coming next.       |
| v0.35   | Match history + stats  | Win/loss record, accuracy, damage dealt/taken per match.             |
| v0.36   | Achievement system     | Cosmetic milestone achievements (first kill, 10 wins, etc.).         |
| v0.37   | Boss tank encounters   | Unique high-HP boss tanks with signature ultimates and specialized AI. Defined in data/configs/bosses.yaml. Defeating a boss unlocks it as a playable tank in sandbox mode. |
| v0.38   | Campaign mode          | Linear story missions with escalating difficulty and boss fights gated by progression. Narrative text in data/campaign/. |
| v0.39   | Sandbox unlocks from campaign | Bosses and campaign-exclusive tanks/weapons available in free play after unlock. |
---
### Phase 7 — Online Multiplayer
*The biggest lift on the roadmap. Significant infrastructure work.*
*See architecture notes below before starting this phase.*
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.40   | Network architecture design | Choose model: peer-to-peer vs authoritative server. Recommendation: authoritative server (server owns state, clients send inputs only). Library candidates: python-socketio or Twisted. Write a design doc before any code. |
| v0.41   | Input serialization    | TankInput is already a clean dataclass — serializes trivially. This is the lucky part of the existing architecture. |
| v0.42   | Game state sync        | Server broadcasts world state each tick. Clients render received state. Lag compensation and client-side prediction are the hard parts. |
| v0.43   | Lobby + matchmaking    | Room creation, join by code, player ready system.                    |
| v0.44   | Online sandbox mode    | 1v1 and free-for-all online. Campaign and progression stay local.    |
| v0.45   | Online progression sync | Cloud save, cross-device profile.                                   |
---
### Phase 8 — Polish & Stretch
| Version | Milestone              | Notes                                                                 |
|---------|------------------------|-----------------------------------------------------------------------|
| v0.46   | Particle effects       | Muzzle flash, bullet impact, explosion, status effect visuals.       |
| v0.47   | Sprite art             | Replace placeholder rects with actual tank sprites. Asset-only change — no logic impact. |
| v0.48   | Local multiplayer      | Second human player on same keyboard or controller.                  |
| v0.49   | Controller support     | Gamepad input via pygame joystick API. InputHandler abstraction makes this clean. |
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
