"""
game/scenes/game_scene.py

GameplayScene — the main in-game screen.

Milestone v0.3 state:
  - Single player-controlled tank loaded from tanks.yaml config
  - Top-down arena (world space 1600x1200) rendered with camera offset
  - Smooth camera follow with arena-boundary clamping
  - WASD movement and rotation using InputHandler → Tank controller interface
  - PhysicsSystem enforces arena bounds (world space)
  - SPACEBAR fires bullets; fire_rate and stats from weapons.yaml
  - Bullets travel, render, and despawn at arena boundary or max_range
  - ESC returns to main menu

Coordinate systems:
  World space  — all entity positions (x, y) live here. Origin at arena top-left.
  Screen space — what gets drawn to the display surface. Derived by Camera.world_to_screen().
  Never mix the two; always convert explicitly via camera.world_to_screen().

Not yet implemented (future milestones):
  - AI opponent
  - Collision with obstacles
  - Damage / health system
  - HUD overlay
"""

import pygame

from game.entities.bullet import Bullet
from game.entities.tank import Tank
from game.scenes.base_scene import BaseScene
from game.systems.input_handler import InputHandler
from game.systems.physics import PhysicsSystem
from game.utils.camera import Camera
from game.utils.config_loader import get_tank_config, get_weapon_config
from game.utils.constants import (
    ARENA_BORDER_COLOR,
    ARENA_BORDER_THICKNESS,
    ARENA_FLOOR_COLOR,
    ARENA_GRID_COLOR,
    ARENA_GRID_STEP,
    ARENA_HEIGHT,
    ARENA_WIDTH,
    BULLET_COLOR,
    BULLET_RADIUS,
    COLOR_BG,
    COLOR_WHITE,
    DEFAULT_WEAPON_TYPE,
    SCENE_MENU,
    TANK_BARREL_COLOR,
    TANK_BARREL_HEIGHT,
    TANK_BARREL_WIDTH,
    TANK_BODY_HEIGHT,
    TANK_BODY_WIDTH,
    TANK_DEFAULT_TYPE,
    TANK_PLAYER_COLOR,
    TANKS_CONFIG,
    WEAPONS_CONFIG,
)
from game.utils.math_utils import heading_to_vec
from game.utils.logger import get_logger

log = get_logger(__name__)

# Player spawn position — center of the arena (world space)
_SPAWN_X: float = ARENA_WIDTH / 2.0
_SPAWN_Y: float = ARENA_HEIGHT / 2.0


class GameplayScene(BaseScene):
    """
    Active gameplay screen. Owns all in-game entities and systems
    for the current match.
    """

    def __init__(self, manager) -> None:
        super().__init__(manager)

        # These are (re)created in on_enter so each new match starts fresh.
        self._tank: Tank | None = None
        self._input_handler: InputHandler | None = None
        self._physics: PhysicsSystem | None = None
        self._camera: Camera | None = None
        self._weapon_config: dict = {}
        self._bullets: list[Bullet] = []

        # Pre-build the tank surface once; rotated each frame in draw()
        self._tank_surf: pygame.Surface | None = None

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        """
        (Re)initialize all entities and systems.
        Called each time the player enters the gameplay scene, so a
        rematch starts with a clean state without relaunching the game.
        """
        self._input_handler = InputHandler()

        # Load tank stats from data/configs/tanks.yaml
        tank_config = get_tank_config(TANK_DEFAULT_TYPE, TANKS_CONFIG)
        self._tank = Tank(
            x=_SPAWN_X,
            y=_SPAWN_Y,
            config=tank_config,
            controller=self._input_handler,
        )

        # Load weapon config and override tank's fire_rate with weapon's
        self._weapon_config = get_weapon_config(DEFAULT_WEAPON_TYPE, WEAPONS_CONFIG)
        self._tank.fire_rate = float(
            self._weapon_config.get("fire_rate", self._tank.fire_rate)
        )

        self._bullets = []
        self._physics = PhysicsSystem()

        # Camera starts snapped to the tank so there's no initial lerp pan
        self._camera = Camera()
        self._camera.snap_to(_SPAWN_X, _SPAWN_Y)

        # Build the static tank surface (body + barrel; rotated each frame)
        self._tank_surf = _build_tank_surface(TANK_PLAYER_COLOR)

        log.info(
            "GameplayScene ready. Tank: %s  Weapon: %s  Spawn: (%.0f, %.0f)",
            TANK_DEFAULT_TYPE, DEFAULT_WEAPON_TYPE, _SPAWN_X, _SPAWN_Y,
        )

    def on_exit(self) -> None:
        log.info("GameplayScene exited.")
        self._tank = None
        self._input_handler = None
        self._physics = None
        self._camera = None
        self._tank_surf = None
        self._weapon_config = {}
        self._bullets = []

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.manager.switch_to(SCENE_MENU)

    def update(self, dt: float) -> None:
        if self._tank is None:
            return

        # Tank.update() returns fire events; spawn a bullet for each
        for event in self._tank.update(dt):
            if event[0] == "fire":
                _, ex, ey, eangle = event
                dx, dy = heading_to_vec(eangle)
                # Spawn at barrel tip (TANK_BARREL_WIDTH px forward of tank center)
                spawn_x = ex + dx * TANK_BARREL_WIDTH
                spawn_y = ey + dy * TANK_BARREL_WIDTH
                self._bullets.append(
                    Bullet(spawn_x, spawn_y, eangle, self._tank, self._weapon_config)
                )

        # PhysicsSystem: advance bullets and clamp tank to arena
        self._physics.update(dt, tanks=[self._tank], bullets=self._bullets)

        # Remove bullets destroyed by physics (boundary hit or max_range)
        self._bullets = [b for b in self._bullets if b.is_alive]

        # Camera follows the player tank each frame
        self._camera.update(dt, self._tank.x, self._tank.y)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        # 1. Clear display with out-of-arena background color
        surface.fill(COLOR_BG)

        if self._camera is None or self._tank is None:
            return

        # 2. Arena floor and border (world rect projected through camera)
        _draw_arena(surface, self._camera)

        # 3. Player tank (placeholder geometry, rotated to facing angle)
        _draw_tank(surface, self._tank, self._tank_surf, self._camera)

        # 4. Active bullets
        _draw_bullets(surface, self._bullets, self._camera)

        # 5. Debug overlay — remove or gate behind a flag in a later milestone
        _draw_debug(surface, self._tank, self._camera)


# ---------------------------------------------------------------------------
# Module-level drawing helpers
# (pure draw functions — no scene state, easily moved to a renderer later)
# ---------------------------------------------------------------------------

def _build_tank_surface(body_color: tuple) -> pygame.Surface:
    """
    Build a canonical tank surface facing right (angle = 0).
    The surface is centered on the tank pivot so pygame.transform.rotate
    rotates around the correct point.

    Layout (TANK_BODY_WIDTH × TANK_BODY_HEIGHT surface):
      - Body:   full surface rect, rounded corners
      - Barrel: right half of surface, vertically centered, dark gray
    """
    surf = pygame.Surface((TANK_BODY_WIDTH, TANK_BODY_HEIGHT), pygame.SRCALPHA)

    # Body
    pygame.draw.rect(surf, body_color, (0, 0, TANK_BODY_WIDTH, TANK_BODY_HEIGHT), border_radius=5)

    # Barrel — extends right from the center pivot (angle=0 = facing right)
    barrel_x = TANK_BODY_WIDTH // 2
    barrel_y = (TANK_BODY_HEIGHT - TANK_BARREL_HEIGHT) // 2
    pygame.draw.rect(surf, TANK_BARREL_COLOR, (barrel_x, barrel_y, TANK_BARREL_WIDTH, TANK_BARREL_HEIGHT))

    return surf


def _draw_arena(surface: pygame.Surface, camera: Camera) -> None:
    """Draw the arena floor, reference grid, and border in screen space."""
    # Top-left corner of the arena in screen space (world origin = 0, 0)
    ax, ay = camera.world_to_screen(0, 0)
    ax_i, ay_i = int(ax), int(ay)

    floor_rect = pygame.Rect(ax_i, ay_i, ARENA_WIDTH, ARENA_HEIGHT)
    pygame.draw.rect(surface, ARENA_FLOOR_COLOR, floor_rect)

    # Reference grid — gives the player a scrolling visual reference so
    # camera-follow movement doesn't look like an invisible wall
    for wx in range(0, ARENA_WIDTH + 1, ARENA_GRID_STEP):
        sx = ax_i + wx
        pygame.draw.line(surface, ARENA_GRID_COLOR, (sx, ay_i), (sx, ay_i + ARENA_HEIGHT))
    for wy in range(0, ARENA_HEIGHT + 1, ARENA_GRID_STEP):
        sy = ay_i + wy
        pygame.draw.line(surface, ARENA_GRID_COLOR, (ax_i, sy), (ax_i + ARENA_WIDTH, sy))

    pygame.draw.rect(surface, ARENA_BORDER_COLOR, floor_rect, ARENA_BORDER_THICKNESS)


def _draw_tank(
    surface: pygame.Surface,
    tank: Tank,
    tank_surf: pygame.Surface,
    camera: Camera,
) -> None:
    """
    Rotate the tank surface to its current facing angle and blit at its
    screen-space position.

    Angle convention:
      World:  0° = facing right (+x), clockwise positive (y-down coordinate system)
      pygame: transform.rotate() is counter-clockwise for positive angles
      Therefore: pygame_angle = -tank.angle
    """
    if not tank.is_alive:
        return

    sx, sy = camera.world_to_screen(tank.x, tank.y)

    # Rotate canonical (angle=0, facing right) surface to match tank heading
    rotated = pygame.transform.rotate(tank_surf, -tank.angle)
    # Blit centered on the tank's screen-space position
    blit_rect = rotated.get_rect(center=(int(sx), int(sy)))
    surface.blit(rotated, blit_rect)


def _draw_bullets(surface: pygame.Surface, bullets: list, camera: Camera) -> None:
    """Render all active bullets as small filled circles in screen space."""
    for bullet in bullets:
        if not bullet.is_alive:
            continue
        sx, sy = camera.world_to_screen(bullet.x, bullet.y)
        pygame.draw.circle(surface, BULLET_COLOR, (int(sx), int(sy)), BULLET_RADIUS)


def _draw_debug(surface: pygame.Surface, tank: Tank, camera: Camera) -> None:
    """
    Lightweight debug overlay: world position and angle in the top-right corner.
    TODO(milestone v0.4+): gate behind a DEBUG constant or remove.
    """
    font = pygame.font.SysFont(None, 22)
    lines = [
        f"world  ({tank.x:6.1f}, {tank.y:6.1f})",
        f"angle  {tank.angle % 360:5.1f}°",
        f"cam    ({camera.x:6.1f}, {camera.y:6.1f})",
    ]
    x = surface.get_width() - 210
    y = 12
    for line in lines:
        txt = font.render(line, True, COLOR_WHITE)
        surface.blit(txt, (x, y))
        y += 20
