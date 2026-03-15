# Tank Battle

A 2D top-down tank battle game built with Python and Pygame. Data-driven, architecturally clean, and designed for iterative expansion.

---

## Setup

```bash
# Clone
git clone https://github.com/joemachen/tank-battle.git
cd tank-battle

# Virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

---

## Controls

| Action       | Key            |
|--------------|----------------|
| Move Forward | W / Up Arrow   |
| Move Back    | S / Down Arrow |
| Rotate Left  | A / Left Arrow |
| Rotate Right | D / Right Arrow|
| Fire         | Space          |
| Pause        | Escape         |

---

## Project Structure

```
tank_battle/
├── main.py                  # Entry point only
├── game/
│   ├── engine.py            # Game loop (delta-time based)
│   ├── scenes/              # SceneManager + all screen classes
│   ├── entities/            # Tank, Bullet, Obstacle, Pickup
│   ├── systems/             # Physics, collision, input, AI
│   ├── ui/                  # HUD, AudioManager
│   └── utils/               # constants.py, logger.py, save_manager.py
├── assets/                  # sprites/, sounds/, music/
├── data/
│   ├── configs/             # tanks.yaml, weapons.yaml, ai_difficulty.yaml
│   └── progression/         # xp_table.yaml
├── logs/                    # Rotating log files (gitignored)
├── saves/                   # Player profile + settings (gitignored)
└── tests/                   # pytest unit tests
```

---

## Adding a New Tank Type

No Python code changes required. Open `data/configs/tanks.yaml` and add an entry:

```yaml
my_new_tank:
  speed: 160
  health: 120
  turn_rate: 140
  fire_rate: 1.2
  description: "A balanced mid-tier tank"
```

The tank will be available to both the player and the AI controller automatically.

---

## Adding a New Weapon

Open `data/configs/weapons.yaml` and add an entry:

```yaml
bouncing_round:
  damage: 25
  speed: 400
  max_bounces: 3
  fire_rate: 0.8
  description: "Ricochets off walls up to 3 times"
```

Implement the bounce logic in `game/entities/bullet.py` by checking the weapon type — all other systems (fire rate, damage application) pick up the config automatically.

---

## Branching & Commit Conventions

- `main` — stable, tagged releases only. Never commit directly.
- `feature/<name>` — all development work. One feature per branch.
- `fix/<name>` — bug fixes.
- `chore/<name>` — tooling, config, non-gameplay changes.

**Commit message format:**
```
<type>: <short description>

[optional body explaining why, not what]
```

Types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`

**Tags:**
- `v0.0.1` — Project scaffold
- `v0.1.0` — Game loop + one tank on screen
- `v0.2.0` — Shooting + collision
- `v0.3.0` — AI opponent
- `v1.0.0` — Full single-player loop with progression

---

## Architecture Principles

- **No magic numbers** — All constants live in `game/utils/constants.py`
- **Data-driven** — Tank types, weapons, AI difficulty defined in `data/configs/`
- **Scene Manager** — All screen transitions go through `SceneManager`
- **Decoupled AI** — `Tank` class is controller-agnostic; control injected via interface
- **Audio abstraction** — All audio through `AudioManager` singleton only
- **Delta time everywhere** — All movement/physics use `dt` for FPS independence
- **Fail gracefully** — All I/O is wrapped; errors logged, never crash
