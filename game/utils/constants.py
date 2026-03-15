"""
game/utils/constants.py

Single source of truth for all numeric and string constants.
No magic numbers are permitted anywhere else in the codebase.
"""

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
SCREEN_WIDTH: int = 1280
SCREEN_HEIGHT: int = 720
FPS: int = 60
TITLE: str = "Tank Battle"

# ---------------------------------------------------------------------------
# Colors  (R, G, B)
# ---------------------------------------------------------------------------
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_RED = (220, 50, 47)
COLOR_GREEN = (133, 153, 0)
COLOR_BLUE = (38, 139, 210)
COLOR_YELLOW = (181, 137, 0)
COLOR_GRAY = (88, 110, 117)
COLOR_DARK_GRAY = (40, 40, 40)
COLOR_BG = (20, 20, 20)

# ---------------------------------------------------------------------------
# Physics / Movement defaults (overridden by tank config where applicable)
# ---------------------------------------------------------------------------
DEFAULT_TANK_SPEED: float = 150.0        # pixels per second
DEFAULT_TANK_TURN_RATE: float = 120.0    # degrees per second
DEFAULT_BULLET_SPEED: float = 400.0      # pixels per second
DEFAULT_FIRE_RATE: float = 1.0           # shots per second

# ---------------------------------------------------------------------------
# Arena (world space — larger than the viewport)
# ---------------------------------------------------------------------------
ARENA_WIDTH: int = 1600                  # logical world units (pixels)
ARENA_HEIGHT: int = 1200
ARENA_FLOOR_COLOR = (28, 35, 28)         # dark muted green — ground
ARENA_BORDER_COLOR = (70, 90, 70)        # lighter green border
ARENA_BORDER_THICKNESS: int = 4
ARENA_GRID_STEP: int = 100               # world units between grid lines
ARENA_GRID_COLOR = (38, 48, 38)          # slightly lighter than floor; makes scrolling visible

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
CAMERA_LERP_SPEED: float = 6.0           # higher = snappier follow; lower = more lag

# ---------------------------------------------------------------------------
# Tank rendering (placeholder geometry — replaced by sprites later)
# ---------------------------------------------------------------------------
TANK_BODY_WIDTH: int = 40                # pixels
TANK_BODY_HEIGHT: int = 30
TANK_BARREL_WIDTH: int = 22              # extends right from center (angle=0)
TANK_BARREL_HEIGHT: int = 8
TANK_BARREL_COLOR = (55, 55, 55)
TANK_PLAYER_COLOR = (100, 160, 80)       # player tank fill color (placeholder)

# Default tank type loaded at game start
TANK_DEFAULT_TYPE: str = "medium_tank"

# ---------------------------------------------------------------------------
# Game rules
# ---------------------------------------------------------------------------
DEFAULT_TANK_HEALTH: int = 100
ARENA_PADDING: int = 32                  # min distance from arena edge for spawning

# ---------------------------------------------------------------------------
# Weapons / Bullets
# ---------------------------------------------------------------------------
DEFAULT_WEAPON_TYPE: str = "standard_shell"
BULLET_RADIUS: int = 5                   # pixels — rendering and collision approximation
BULLET_COLOR = (255, 220, 50)            # bright yellow; distinct from all tank colors
BULLET_DEFAULT_MAX_RANGE: float = 1400.0 # fallback travel limit when not set in weapons.yaml
# half-diagonal of tank body (25px) + border thickness (4px)
# TECH DEBT: when tanks have different hull sizes, this must become per-tank (read from config)
TANK_MOVEMENT_MARGIN: int = 29

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
DATA_DIR: str = "data"
CONFIG_DIR: str = "data/configs"
SAVES_DIR: str = "saves"
LOGS_DIR: str = "logs"
LOG_FILE: str = "logs/tank_battle.log"
PROFILE_FILE: str = "saves/player_profile.json"
SETTINGS_FILE: str = "saves/settings.json"
TANKS_CONFIG: str = "data/configs/tanks.yaml"
WEAPONS_CONFIG: str = "data/configs/weapons.yaml"
AI_DIFFICULTY_CONFIG: str = "data/configs/ai_difficulty.yaml"
XP_TABLE_CONFIG: str = "data/progression/xp_table.yaml"

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
MUSIC_VOLUME_DEFAULT: float = 0.7
SFX_VOLUME_DEFAULT: float = 0.8
MASTER_VOLUME_DEFAULT: float = 1.0
AUDIO_CHANNELS: int = 16
MUSIC_FADEOUT_MS: int = 1000

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
HUD_MARGIN: int = 12
HUD_BAR_WIDTH: int = 160
HUD_BAR_HEIGHT: int = 16

# ---------------------------------------------------------------------------
# Scene names (registered with SceneManager by these keys)
# ---------------------------------------------------------------------------
SCENE_MENU: str = "menu"
SCENE_GAME: str = "game"
SCENE_SETTINGS: str = "settings"
SCENE_GAME_OVER: str = "game_over"

# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------
AI_DETECTION_RANGE: float = 550.0        # pixels — triggers PURSUE state
AI_ATTACK_RANGE: float = 250.0           # pixels — triggers ATTACK state
AI_EVASION_HEALTH_RATIO: float = 0.30    # fraction — triggers EVADE state

# ---------------------------------------------------------------------------
# Persistence defaults
# ---------------------------------------------------------------------------
DEFAULT_PROFILE: dict = {
    "xp": 0,
    "level": 1,
    "unlocked_tanks": ["light_tank"],
    "unlocked_weapons": ["standard_shell"],
    "total_matches": 0,
    "wins": 0,
    "losses": 0,
    "match_history": [],
}

DEFAULT_SETTINGS: dict = {
    "resolution": [SCREEN_WIDTH, SCREEN_HEIGHT],
    "master_volume": MASTER_VOLUME_DEFAULT,
    "music_volume": MUSIC_VOLUME_DEFAULT,
    "sfx_volume": SFX_VOLUME_DEFAULT,
    "keybinds": {
        "move_forward": "w",
        "move_backward": "s",
        "rotate_left": "a",
        "rotate_right": "d",
        "fire": "space",
        "pause": "escape",
    },
    "ai_difficulty": "medium",
    "fullscreen": False,
}
