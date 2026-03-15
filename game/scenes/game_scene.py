"""
game/scenes/game_scene.py

GameplayScene — the main in-game screen.

Milestone v0.5 state:
  - Live AI opponent (medium difficulty): PATROL → PURSUE → ATTACK → EVADE
  - AI moves, aims, and fires; player can die
  - HUD: player health bar (bottom-left) + AI health bar (bottom-right)
  - Player death → GameOverScene (DEFEATED)
  - AI death → GameOverScene (VICTORY)
  - Full bidirectional combat loop validated

Coordinate systems:
  World space  — all entity positions (x, y) live here. Origin at arena top-left.
  Screen space — what gets drawn to the display surface. Derived by Camera.world_to_screen().
  Never mix the two; always convert explicitly via camera.world_to_screen().

Not yet implemented (future milestones):
  - Obstacle walls
  - Match result calculator (score/XP are placeholders this milestone)
  - Multiple player tank types
"""

import pygame

from game.entities.bullet import Bullet
from game.entities.tank import Tank, TankInput
from game.scenes.base_scene import BaseScene
from game.systems.ai_controller import AIController
from game.systems.collision import CollisionSystem
from game.systems.input_handler import InputHandler
from game.systems.physics import PhysicsSystem
from game.ui.hud import HUD
from game.utils.camera import Camera
from game.utils.config_loader import get_ai_config, get_tank_config, get_weapon_config
from game.utils.constants import (
    AI_DIFFICULTY_CONFIG,
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
    COLOR_RED,
    COLOR_WHITE,
    DEFAULT_WEAPON_TYPE,
    SCENE_GAME_OVER,
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
from game.utils.logger import get_logger
from game.utils.math_utils import heading_to_vec

log = get_logger(__name__)

# Spawn positions (world space)
_SPAWN_X: float = ARENA_WIDTH / 2.0       # player — arena center
_SPAWN_Y: float = ARENA_HEIGHT / 2.0
_AI_SPAWN_X: float = ARENA_WIDTH * 0.80   # AI — top-right quadrant
_AI_SPAWN_Y: float = ARENA_HEIGHT * 0.20


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
        self._ai_tank: Tank | None = None
        self._ai_controller: AIController | None = None
        self._physics: PhysicsSystem | None = None
        self._collision: CollisionSystem | None = None
        self._camera: Camera | None = None
        self._hud: HUD | None = None
        self._weapon_config: dict = {}
        self._bullets: list[Bullet] = []

        # Pre-built surfaces (body + barrel); rotated each frame in draw()
        self._tank_surf: pygame.Surface | None = None
        self._ai_tank_surf: pygame.Surface | None = None

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

        # AI tank — heavy_tank config, live medium-difficulty controller
        ai_difficulty = get_ai_config("medium", AI_DIFFICULTY_CONFIG)
        self._ai_controller = AIController(
            config=ai_difficulty,
            target_getter=lambda: self._tank,
        )
        ai_tank_config = get_tank_config("heavy_tank", TANKS_CONFIG)
        self._ai_tank = Tank(
            x=_AI_SPAWN_X,
            y=_AI_SPAWN_Y,
            config=ai_tank_config,
            controller=self._ai_controller,
        )
        self._ai_controller.set_owner(self._ai_tank)

        self._bullets = []
        self._physics = PhysicsSystem()
        self._collision = CollisionSystem()
        self._hud = HUD()

        # Camera starts snapped to the tank so there's no initial lerp pan
        self._camera = Camera()
        self._camera.snap_to(_SPAWN_X, _SPAWN_Y)

        # Build tank surfaces (body + barrel; rotated each frame in draw())
        self._tank_surf = _build_tank_surface(TANK_PLAYER_COLOR)
        self._ai_tank_surf = _build_tank_surface(COLOR_RED)

        log.info(
            "GameplayScene ready. Player: %s  AI: heavy_tank (medium)  Weapon: %s",
            TANK_DEFAULT_TYPE, DEFAULT_WEAPON_TYPE,
        )

    def on_exit(self) -> None:
        log.info("GameplayScene exited.")
        self._tank = None
        self._input_handler = None
        self._ai_tank = None
        self._ai_controller = None
        self._physics = None
        self._collision = None
        self._camera = None
        self._hud = None
        self._tank_surf = None
        self._ai_tank_surf = None
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

        # Player tank update — spawns bullets on fire events
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

        # AI tank update — live controller fires back this milestone
        if self._ai_tank and self._ai_tank.is_alive:
            for event in self._ai_tank.update(dt):
                if event[0] == "fire":
                    _, ex, ey, eangle = event
                    dx, dy = heading_to_vec(eangle)
                    spawn_x = ex + dx * TANK_BARREL_WIDTH
                    spawn_y = ey + dy * TANK_BARREL_WIDTH
                    # TODO: use AI-specific weapon config in a later milestone
                    self._bullets.append(
                        Bullet(spawn_x, spawn_y, eangle, self._ai_tank, self._weapon_config)
                    )

        # PhysicsSystem: advance bullets and clamp all tanks to arena
        all_tanks = [t for t in (self._tank, self._ai_tank) if t is not None]
        self._physics.update(dt, tanks=all_tanks, bullets=self._bullets)

        # Remove bullets destroyed by physics (boundary hit or max_range)
        self._bullets = [b for b in self._bullets if b.is_alive]

        # CollisionSystem: bullet hits, tank hits, etc.
        if self._collision and self._ai_tank:
            self._collision.update(
                tanks=all_tanks,
                bullets=self._bullets,
                obstacles=[],
                pickups=[],
            )
            # Prune bullets destroyed by collision
            self._bullets = [b for b in self._bullets if b.is_alive]

        # Check lose condition: player tank destroyed → game over (defeat)
        if not self._tank.is_alive:
            # TODO: score and XP are placeholders; match result calculator comes in a later milestone
            self.manager.switch_to(SCENE_GAME_OVER, won=False, score=0, xp_earned=10)
            return

        # Check win condition: AI tank destroyed → game over (victory)
        if self._ai_tank and not self._ai_tank.is_alive:
            # TODO: score and XP are placeholders; match result calculator comes in a later milestone
            self.manager.switch_to(SCENE_GAME_OVER, won=True, score=100, xp_earned=50)
            return

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

        # 3. AI tank (drawn before player so player renders on top if overlapping)
        if self._ai_tank and self._ai_tank_surf:
            _draw_tank(surface, self._ai_tank, self._ai_tank_surf, self._camera)

        # 4. Player tank (placeholder geometry, rotated to facing angle)
        _draw_tank(surface, self._tank, self._tank_surf, self._camera)

        # 5. Active bullets
        _draw_bullets(surface, self._bullets, self._camera)

        # 6. HUD — health bars for both tanks
        if self._hud:
            self._hud.draw(surface, self._tank, self._ai_tank)

        # 7. Debug overlay — remove or gate behind a flag in a later milestone
        ai_state = self._ai_controller.state_name if self._ai_controller else "—"
        _draw_debug(surface, self._tank, self._camera, self._ai_tank, ai_state)


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


def _draw_debug(
    surface: pygame.Surface,
    player_tank: Tank,
    camera: Camera,
    ai_tank: Tank | None = None,
    ai_state: str = "—",
) -> None:
    """
    Lightweight debug overlay: positions, health, and AI state.
    TODO(milestone v0.6+): gate behind a DEBUG constant or remove.
    """
    font = pygame.font.SysFont(None, 22)
    lines = [
        f"P  ({player_tank.x:6.1f}, {player_tank.y:6.1f})",
        f"P  angle {player_tank.angle % 360:5.1f}°",
    ]
    if ai_tank is not None:
        hp_pct = int(ai_tank.health / ai_tank.max_health * 100) if ai_tank.max_health else 0
        lines += [
            f"AI ({ai_tank.x:6.1f}, {ai_tank.y:6.1f})",
            f"AI hp {ai_tank.health}/{ai_tank.max_health} ({hp_pct}%)  [{ai_state}]",
        ]
    lines.append(f"cam  ({camera.x:6.1f}, {camera.y:6.1f})")
    x = surface.get_width() - 240
    y = 12
    for line in lines:
        txt = font.render(line, True, COLOR_WHITE)
        surface.blit(txt, (x, y))
        y += 20
