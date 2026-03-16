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
# Obstacles
# ---------------------------------------------------------------------------
OBSTACLE_COLOR = (72, 68, 50)            # fallback fill; normally overridden by material color
OBSTACLE_BORDER_COLOR = (110, 105, 80)   # 2px border drawn on top of material fill
OBSTACLE_DAMAGED_COLOR = (28, 26, 22)    # lerp target when obstacle hp reaches 0

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
DATA_DIR: str = "data"
CONFIG_DIR: str = "data/configs"
MAP_01: str = "data/maps/map_01.yaml"
MATERIALS_CONFIG: str = "data/configs/materials.yaml"
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

import os as _os
_ASSET_ROOT = _os.path.join(_os.path.dirname(__file__), "..", "..", "assets")

# SFX asset paths
SFX_TANK_FIRE:           str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_tank_fire.wav")
SFX_BULLET_HIT_TANK:     str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_bullet_hit_tank.wav")
SFX_BULLET_HIT_OBSTACLE: str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_bullet_hit_obstacle.wav")
SFX_OBSTACLE_DESTROY:    str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_obstacle_destroy.wav")
SFX_TANK_EXPLOSION:      str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_tank_explosion.wav")
SFX_TANK_COLLISION:      str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_tank_collision.wav")
SFX_UI_NAVIGATE:         str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_ui_navigate.wav")
SFX_UI_CONFIRM:          str = _os.path.join(_ASSET_ROOT, "sounds", "sfx_ui_confirm.wav")

# Music asset paths
MUSIC_MENU:      str = _os.path.join(_ASSET_ROOT, "music", "music_menu.wav")
MUSIC_GAMEPLAY:  str = _os.path.join(_ASSET_ROOT, "music", "music_gameplay.wav")
MUSIC_GAME_OVER: str = _os.path.join(_ASSET_ROOT, "music", "music_game_over.wav")

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
HUD_MARGIN: int = 12
HUD_BAR_WIDTH: int = 160
HUD_BAR_HEIGHT: int = 16

# ---------------------------------------------------------------------------
# Tank Selection screen
# ---------------------------------------------------------------------------
# Per-tank card fill colors (must differ from TANK_PLAYER_COLOR)
TANK_COLOR_LIGHT:  tuple = COLOR_BLUE    # light_tank
TANK_COLOR_MEDIUM: tuple = COLOR_GREEN   # medium_tank
TANK_COLOR_HEAVY:  tuple = COLOR_YELLOW  # heavy_tank
TANK_COLOR_SCOUT:  tuple = COLOR_WHITE   # scout_tank

# Tank type → card color lookup used by TankSelectScene
TANK_SELECT_COLORS: dict = {
    "light_tank":  COLOR_BLUE,
    "medium_tank": COLOR_GREEN,
    "heavy_tank":  COLOR_YELLOW,
    "scout_tank":  COLOR_WHITE,
}

# Stat bar max width in pixels (normalized 0.0–1.0 × this value)
MAX_BAR_WIDTH: int = 120

# Reference maxima used for normalization (derived from tanks.yaml peak values)
TANK_STAT_MAX: dict = {
    "speed":     260.0,   # scout_tank
    "health":    220.0,   # heavy_tank
    "turn_rate": 220.0,   # scout_tank
    "fire_rate": 2.0,     # scout_tank
}

# ---------------------------------------------------------------------------
# Scene names (registered with SceneManager by these keys)
# ---------------------------------------------------------------------------
SCENE_MENU: str = "menu"
SCENE_TANK_SELECT: str = "tank_select"
SCENE_GAME: str = "game"
SCENE_SETTINGS: str = "settings"
SCENE_GAME_OVER: str = "game_over"

# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------
AI_DETECTION_RANGE: float = 550.0        # pixels — triggers PURSUE state
AI_ATTACK_RANGE: float = 250.0           # pixels — triggers ATTACK state
AI_EVASION_HEALTH_RATIO: float = 0.30    # fraction — triggers EVADE state

# Predefined AI spawn positions in world space — all far from arena center
AI_SPAWN_POSITIONS: list = [
    (ARENA_WIDTH - 200, 200),            # top-right
    (200, 200),                          # top-left
    (ARENA_WIDTH - 200, ARENA_HEIGHT - 200),  # bottom-right
]

# ---------------------------------------------------------------------------
# Tank-to-Tank Collision Damage
# ---------------------------------------------------------------------------
# Base damage by impact geometry (angle between struck tank's facing and
# the vector from struck tank → striking tank)
COLLISION_DAMAGE_FRONT: int = 5          # 0–45°  — nose-to-nose nudge
COLLISION_DAMAGE_SIDE: int = 20          # 45–135° — T-bone
COLLISION_DAMAGE_REAR: int = 12          # 135–180° — rear-end

# Speed scaling: relative speed / COLLISION_SPEED_SCALE, capped at
# COLLISION_SPEED_CAP so a head-on charge doesn't one-shot anything.
COLLISION_SPEED_SCALE: float = 150.0
COLLISION_SPEED_CAP: float = 1.5

# ---------------------------------------------------------------------------
# XP and Progression
# ---------------------------------------------------------------------------
XP_PARTICIPATION: int = 10        # awarded even on a loss — just for playing
XP_WIN: int = 100                  # bonus for winning the match
XP_KILL: int = 40                  # per AI tank destroyed
XP_SURVIVAL_BONUS: int = 25        # bonus for surviving to end of match
XP_ACCURACY_BONUS_MAX: int = 50    # max bonus for perfect shot accuracy

# ---------------------------------------------------------------------------
# Persistence defaults
# ---------------------------------------------------------------------------
DEFAULT_PROFILE: dict = {
    "xp": 0,
    "level": 1,
    "unlocked_tanks": ["light_tank", "medium_tank"],
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
