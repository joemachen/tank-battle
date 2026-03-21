"""
game/scenes/game_scene.py

GameplayScene — the main in-game screen.

Milestone v0.9 state:
  - Player picks tank type, AI difficulty, and opponent count from TankSelectScene
  - 1–3 AI opponents (all heavy_tank, all target the player)
  - Tank-to-tank collision pushes both apart and deals angle-based damage
  - VICTORY when ALL AI tanks are dead; DEFEAT when player is dead
  - HUD shows per-AI health bars stacked in the bottom-right corner
  - Arena obstacles (materials, destructible, bounce)
  - AI navigation: RECOVERY state, stuck detection, obstacle avoidance

Coordinate systems:
  World space  — all entity positions (x, y) live here. Origin at arena top-left.
  Screen space — what gets drawn to the display surface. Derived by Camera.world_to_screen().
  Never mix the two; always convert explicitly via camera.world_to_screen().
"""

import math
import random
import time

import pygame

from game.entities.bullet import Bullet
from game.entities.tank import Tank, TankInput
from game.scenes.base_scene import BaseScene
from game.systems.ai_controller import AIController
from game.systems.collision import CollisionSystem
from game.systems.debris_system import DebrisSystem
from game.systems.input_handler import InputHandler
from game.systems.pickup_spawner import PickupSpawner
from game.systems.match_calculator import MatchCalculator
from game.systems.physics import PhysicsSystem
from game.ui.audio_manager import get_audio_manager
from game.ui.hud import HUD
from game.utils.camera import Camera
from game.utils.config_loader import get_ai_config, get_tank_config, load_yaml
from game.utils.constants import (
    AI_ATTACK_RANGE,
    AI_DETECTION_RANGE,
    AI_DIFFICULTY_CONFIG,
    AI_SPAWN_POSITIONS,
    ARENA_BORDER_COLOR,
    ARENA_BORDER_THICKNESS,
    ARENA_FLOOR_COLOR,
    BUFF_ICON_FONT_SIZE,
    BUFF_ICON_OFFSET_Y,
    BUFF_ICON_SPACING,
    ARENA_GRID_COLOR,
    ARENA_GRID_STEP,
    ARENA_HEIGHT,
    ARENA_WALL_THICKNESS,
    ARENA_WIDTH,
    BULLET_COLOR,
    BULLET_RADIUS,
    HOMING_BULLET_COLOR,
    HOMING_BULLET_RADIUS,
    COLOR_BG,
    COLOR_NEON_PINK,
    DAMAGE_CRACK_DARKEN,
    DEBRIS_COUNT,
    DEBRIS_COUNT_DEFAULT,
    COLOR_RED,
    COLOR_WHITE,
    DEFAULT_MAP,
    DEFAULT_WEAPON_TYPE,
    KEYBIND_SLOT_1,
    KEYBIND_SLOT_2,
    KEYBIND_SLOT_3,
    MAPS_DIR,
    MUSIC_GAMEPLAY,
    PICKUP_COLLECT_SFX,
    SFX_SHIELD_POP,
    VFX_REGEN_COLOR,
    VFX_SHIELD_COLOR,
    VFX_SHIELD_POP_COLOR,
    VFX_SPEED_COLOR,
    VFX_RELOAD_COLOR,
    OBSTACLE_BORDER_COLOR,
    PICKUP_GLOW_ALPHA,
    PICKUP_GLOW_SCALE,
    PICKUP_PULSE_AMPLITUDE,
    PICKUP_PULSE_SPEED,
    PICKUP_RENDER_RADIUS,
    PICKUPS_CONFIG,
    RETICLE_COLOR,
    RETICLE_LINE_LENGTH,
    RETICLE_RADIUS,
    SCENE_GAME_OVER,
    SCENE_MENU,
    SFX_BULLET_HIT_OBSTACLE,
    SFX_BULLET_HIT_TANK,
    SFX_OBSTACLE_DESTROY,
    SFX_TANK_COLLISION,
    SFX_TANK_EXPLOSION,
    SFX_TANK_FIRE,
    TANK_BARREL_COLOR,
    TANK_BARREL_LENGTH,
    TANK_BARREL_WIDTH,
    TANK_BODY_HEIGHT,
    TANK_BODY_WIDTH,
    TANK_FRONT_STRIPE_BRIGHTEN,
    TANK_FRONT_STRIPE_WIDTH,
    TANK_DEFAULT_TYPE,
    TANK_PLAYER_COLOR,
    TANKS_CONFIG,
    THEME_TINT_BLEND,
    WEAPONS_CONFIG,
)
from game.utils.map_loader import load_map
from game.utils.math_utils import blend_colors
from game.utils.save_manager import SaveManager
from game.utils.logger import get_logger
from game.utils.math_utils import draw_rotated_rect, heading_to_vec

log = get_logger(__name__)

# Player spawn — arena centre
_SPAWN_X: float = ARENA_WIDTH / 2.0
_SPAWN_Y: float = ARENA_HEIGHT / 2.0

# Maximum AI opponents supported
_MAX_AI: int = 3


class GameplayScene(BaseScene):
    """
    Active gameplay screen.  Owns all in-game entities and systems
    for the current match.
    """

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._tank: Tank | None = None
        self._input_handler: InputHandler | None = None
        # Multi-AI support: parallel lists of tanks and their controllers
        self._ai_tanks: list[Tank] = []
        self._ai_controllers: list[AIController] = []
        self._ai_surfs: list[pygame.Surface] = []
        self._physics: PhysicsSystem | None = None
        self._collision: CollisionSystem | None = None
        self._camera: Camera | None = None
        self._hud: HUD | None = None
        self._weapon_configs: dict[str, dict] = {}   # type → config dict (v0.16)
        self._theme: dict = {}                        # active map theme (v0.17)
        self._bullets: list[Bullet] = []
        self._obstacles: list = []
        self._tank_surf: pygame.Surface | None = None
        # Match stats — reset on_enter, read on match end
        self._shots_fired: int = 0
        self._shots_hit: int = 0
        self._kills: int = 0
        self._damage_dealt: int = 0
        self._damage_taken: int = 0
        self._match_start_time: float = 0.0

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self, **kwargs) -> None:
        """
        (Re)initialise all entities and systems.
        Called each time the player enters the gameplay scene, so a
        rematch starts with a clean state without relaunching the game.
        """
        # Apply persisted settings (keybinds + AI difficulty) from settings.json
        _settings = SaveManager().load_settings()
        _keybinds = _settings.get("keybinds", {})

        # Resolve mute key from settings (rebindable as of v0.17.5)
        mute_name = _keybinds.get("mute", "m")
        self._mute_key: int = getattr(pygame, f"K_{mute_name}", pygame.K_m)

        # Resolve player tank type and opponent count from TankSelectScene kwargs
        tank_type = kwargs.get("tank_type", TANK_DEFAULT_TYPE)
        ai_difficulty_key = _settings.get("ai_difficulty", "medium")
        ai_count = max(1, min(_MAX_AI, int(kwargs.get("ai_count", 1))))

        log.info(
            "GameplayScene: tank=%s  difficulty=%s  opponents=%d",
            tank_type, ai_difficulty_key, ai_count,
        )

        # Resolve weapon types from WeaponSelectScene kwargs (fall back to default)
        raw_weapon_types = kwargs.get("weapon_types", DEFAULT_WEAPON_TYPE)
        if isinstance(raw_weapon_types, str):
            weapon_types: list[str] = [raw_weapon_types]
        else:
            weapon_types = list(raw_weapon_types) or [DEFAULT_WEAPON_TYPE]

        # Camera created first so InputHandler can reference it for mouse→world transform
        self._camera = Camera()
        self._camera.snap_to(_SPAWN_X, _SPAWN_Y)

        # InputHandler — passes camera + tank position getter for free-aim turret
        # tank_position_getter is a lambda that reads self._tank at call time (not now),
        # so it is safe to create InputHandler before self._tank exists.
        self._input_handler = InputHandler(
            keybinds=_keybinds if _keybinds else None,
            camera=self._camera,
            tank_position_getter=lambda: self._tank.position,
        )

        # Build weapon config lookup used by _spawn_bullet
        all_weapon_data = load_yaml(WEAPONS_CONFIG)
        self._weapon_configs = {}
        for wtype in weapon_types:
            cfg = dict(all_weapon_data.get(wtype, {}))
            cfg.setdefault("type", wtype)
            self._weapon_configs[wtype] = cfg
        # Ensure standard_shell is always available (AI uses it)
        if "standard_shell" not in self._weapon_configs:
            cfg = dict(all_weapon_data.get("standard_shell", {}))
            cfg.setdefault("type", "standard_shell")
            self._weapon_configs["standard_shell"] = cfg

        # Player tank
        tank_config = get_tank_config(tank_type, TANKS_CONFIG)
        self._tank = Tank(
            x=_SPAWN_X,
            y=_SPAWN_Y,
            config=tank_config,
            controller=self._input_handler,
        )
        # Equip player with selected weapon loadout
        player_weapon_cfgs = [self._weapon_configs[wt] for wt in weapon_types]
        self._tank.load_weapons(player_weapon_cfgs)

        # Obstacles — loaded once per match; map_name resolves to data/maps/{name}.yaml
        map_name = kwargs.get("map_name", DEFAULT_MAP)
        import os as _os
        map_path = _os.path.join(MAPS_DIR, f"{map_name}.yaml")
        map_data = load_map(map_path)
        self._bullets = []
        self._obstacles = map_data["obstacles"]
        self._theme = map_data["theme"]

        # Pre-compute theme-tinted base color on each obstacle
        _tint = tuple(self._theme.get("obstacle_tint", (128, 128, 128)))
        for _obs in self._obstacles:
            _obs.base_color = blend_colors(_obs.color, _tint, THEME_TINT_BLEND)

        # Debris system for destruction effects
        self._debris = DebrisSystem()
        self._destroyed_set: set[int] = set()

        # Pickup spawner
        self._pickup_configs = load_yaml(PICKUPS_CONFIG)
        pickup_spawns = map_data.get("pickup_spawns", [])
        self._pickup_spawner = PickupSpawner(pickup_spawns, self._pickup_configs)

        # AI tanks — all heavy_tank, shared difficulty, independent controllers
        ai_difficulty = get_ai_config(ai_difficulty_key, AI_DIFFICULTY_CONFIG)
        ai_tank_config = get_tank_config("heavy_tank", TANKS_CONFIG)
        self._ai_tanks = []
        self._ai_controllers = []
        self._ai_surfs = []

        live_obstacles = lambda: [o for o in self._obstacles if o.is_alive]  # noqa: E731

        for i in range(ai_count):
            sx, sy = AI_SPAWN_POSITIONS[i % len(AI_SPAWN_POSITIONS)]
            controller = AIController(
                config=ai_difficulty,
                target_getter=lambda t=self._tank: t,
            )
            ai_tank = Tank(
                x=float(sx),
                y=float(sy),
                config=ai_tank_config,
                controller=controller,
            )
            controller.set_owner(ai_tank)
            controller.set_obstacles_getter(live_obstacles)
            controller.set_pickups_getter(lambda: self._pickup_spawner.active_pickups)
            # AI always uses standard_shell
            std_cfg = self._weapon_configs["standard_shell"]
            ai_tank.load_weapons([std_cfg])
            self._ai_tanks.append(ai_tank)
            self._ai_controllers.append(controller)
            self._ai_surfs.append(_build_tank_surface(COLOR_RED))

        # Remaining systems
        self._physics = PhysicsSystem()
        self._collision = CollisionSystem()
        self._hud = HUD()
        self._tank_surf = _build_tank_surface(TANK_PLAYER_COLOR)

        # Hide system cursor — replaced by neon-pink reticle during gameplay
        pygame.mouse.set_visible(False)

        # Reset match stats
        self._shots_fired = 0
        self._shots_hit = 0
        self._kills = 0
        self._damage_dealt = 0
        self._damage_taken = 0
        self._match_start_time = time.monotonic()

        # Shield pop detection — tracks which tanks had shield last frame
        self._had_shield: dict[int, bool] = {}
        # Music intensity state
        self._music_intense: bool = False

        music_track = self._theme.get("music_override") or MUSIC_GAMEPLAY
        get_audio_manager().play_music(music_track)

        log.info(
            "GameplayScene ready. Player: %s  AI count: %d  Difficulty: %s  Weapons: %s",
            tank_type, ai_count, ai_difficulty_key, weapon_types,
        )

    def on_exit(self) -> None:
        log.info("GameplayScene exited.")
        # Restore system cursor for all non-gameplay scenes
        pygame.mouse.set_visible(True)
        self._tank = None
        self._input_handler = None
        self._ai_tanks = []
        self._ai_controllers = []
        self._ai_surfs = []
        self._physics = None
        self._collision = None
        self._camera = None
        self._hud = None
        self._obstacles = []
        self._tank_surf = None
        self._weapon_configs = {}
        self._theme = {}
        self._bullets = []

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.manager.switch_to(SCENE_MENU)
            elif event.key == self._mute_key:
                get_audio_manager().toggle_mute()
            # Number keys — jump directly to weapon slot (no-op if slot doesn't exist)
            elif event.key == KEYBIND_SLOT_1 and self._tank:
                self._tank.set_active_slot(0)
            elif event.key == KEYBIND_SLOT_2 and self._tank:
                self._tank.set_active_slot(1)
            elif event.key == KEYBIND_SLOT_3 and self._tank:
                self._tank.set_active_slot(2)

        # Mouse wheel — cycle through weapon slots
        # scroll down (y < 0) = next weapon; scroll up (y > 0) = previous weapon
        elif event.type == pygame.MOUSEWHEEL and self._tank:
            direction = 1 if event.y < 0 else -1
            self._tank.cycle_weapon(direction)

    def update(self, dt: float) -> None:
        if self._tank is None:
            return

        audio = get_audio_manager()

        # Player tank update
        for event in self._tank.update(dt):
            if event[0] == "fire":
                self._spawn_bullet(event, self._tank)
                self._shots_fired += 1
                audio.play_sfx(SFX_TANK_FIRE)

        # AI tanks update (tick() for stuck detection before tank.update())
        for ai_tank, controller in zip(self._ai_tanks, self._ai_controllers):
            if not ai_tank.is_alive:
                continue
            controller.tick(dt)
            for event in ai_tank.update(dt):
                if event[0] == "fire":
                    self._spawn_bullet(event, ai_tank)
                    audio.play_sfx(SFX_TANK_FIRE)

        # Physics: advance bullets, clamp all tanks to arena bounds
        all_tanks = [self._tank] + self._ai_tanks
        self._physics.update(dt, tanks=all_tanks, bullets=self._bullets)
        self._bullets = [b for b in self._bullets if b.is_alive]

        # Tick pickup spawner
        self._pickup_spawner.update(dt)

        # Snapshot state before collision resolution for stat tracking
        player_hp_before = self._tank.health
        ai_alive_before = {id(t): t.is_alive for t in self._ai_tanks}

        # Collision: bullets, obstacles, tank-to-tank
        audio_events = self._collision.update(
            tanks=all_tanks,
            bullets=self._bullets,
            obstacles=self._obstacles,
            pickups=self._pickup_spawner.active_pickups,
        )
        self._bullets = [b for b in self._bullets if b.is_alive]

        # Accumulate damage taken by player
        self._damage_taken += max(0, player_hp_before - self._tank.health)

        # Count kills (AI tanks that just died this frame)
        for t in self._ai_tanks:
            if ai_alive_before.get(id(t)) and not t.is_alive:
                self._kills += 1

        # Map collision events → SFX and stat tracking
        _COLLISION_SFX = {
            "bullet_hit_tank":     SFX_BULLET_HIT_TANK,
            "tank_explosion":      SFX_TANK_EXPLOSION,
            "bullet_hit_obstacle": SFX_BULLET_HIT_OBSTACLE,
            "obstacle_destroy":    SFX_OBSTACLE_DESTROY,
            "tank_collision":      SFX_TANK_COLLISION,
        }
        played: set[str] = set()
        for ev in audio_events:
            if isinstance(ev, str):
                if ev not in played:
                    sfx_path = _COLLISION_SFX.get(ev)
                    if sfx_path:
                        audio.play_sfx(sfx_path)
                    played.add(ev)
            elif isinstance(ev, tuple) and ev[0] == "bullet_hit_tank_stat":
                _, owner, dmg = ev
                if owner is self._tank:
                    self._shots_hit += 1
                    self._damage_dealt += dmg

        # Win / lose checks — build MatchResult and pass to GameOverScene
        if not self._tank.is_alive:
            self.manager.switch_to(
                SCENE_GAME_OVER,
                result=MatchCalculator.build(
                    won=False,
                    survived=False,
                    kills=self._kills,
                    shots_fired=self._shots_fired,
                    shots_hit=self._shots_hit,
                    time_elapsed=time.monotonic() - self._match_start_time,
                    damage_dealt=self._damage_dealt,
                    damage_taken=self._damage_taken,
                ),
            )
            return

        if all(not t.is_alive for t in self._ai_tanks):
            self.manager.switch_to(
                SCENE_GAME_OVER,
                result=MatchCalculator.build(
                    won=True,
                    survived=True,
                    kills=self._kills,
                    shots_fired=self._shots_fired,
                    shots_hit=self._shots_hit,
                    time_elapsed=time.monotonic() - self._match_start_time,
                    damage_dealt=self._damage_dealt,
                    damage_taken=self._damage_taken,
                ),
            )
            return

        self._camera.update(dt, self._tank.x, self._tank.y)

        # Update obstacle flash timers
        for obs in self._obstacles:
            if obs.is_alive:
                obs.update(dt)

        # Detect newly destroyed obstacles → spawn debris
        for obs in self._obstacles:
            if not obs.is_alive and id(obs) not in self._destroyed_set:
                self._destroyed_set.add(id(obs))
                count = DEBRIS_COUNT.get(obs.material_type, DEBRIS_COUNT_DEFAULT)
                self._debris.spawn_debris(
                    obs.x + obs.width / 2, obs.y + obs.height / 2,
                    obs.width, obs.height, obs.base_color, count,
                )

        # Update debris particles
        self._debris.update(dt)

        # Shield pop detection — spawn debris when shield breaks
        for tank in all_tanks:
            tid = id(tank)
            has_shield = tank.has_status("shield")
            if self._had_shield.get(tid, False) and not has_shield:
                # Shield just broke — spawn blue debris
                self._debris.spawn_debris(
                    tank.x, tank.y, 30, 30, VFX_SHIELD_POP_COLOR, 8,
                )
                audio.play_sfx(SFX_SHIELD_POP)
            self._had_shield[tid] = has_shield

        # Music intensity: switch to intense track when any tank has an active buff
        any_buff = any(
            tank.status_effects
            for tank in all_tanks if tank.is_alive
        )
        if any_buff != self._music_intense:
            self._music_intense = any_buff
            audio.set_music_intensity(any_buff)

    def _spawn_bullet(self, event: tuple, owner: Tank) -> None:
        # event = ("fire", tank_x, tank_y, turret_angle, weapon_type)  [5-tuple, v0.16]
        _, ex, ey, eangle, weapon_type = event
        weapon_cfg = self._weapon_configs.get(weapon_type, {"type": weapon_type})

        spread_count = int(weapon_cfg.get("spread_count", 1))
        spread_angle = float(weapon_cfg.get("spread_angle", 0.0))

        if spread_count > 1 and spread_angle > 0.0:
            # Fan spread_count bullets symmetrically around eangle.
            # half_spread centres the pattern so the middle bullet stays on aim.
            # e.g. count=3, angle=18 → offsets: [-18, 0, +18]
            half_spread = spread_angle * (spread_count - 1) / 2.0
            for i in range(spread_count):
                offset = -half_spread + i * spread_angle
                bullet_angle = eangle + offset
                dx, dy = heading_to_vec(bullet_angle)
                bx = ex + dx * TANK_BARREL_LENGTH
                by = ey + dy * TANK_BARREL_LENGTH
                self._bullets.append(Bullet(bx, by, bullet_angle, owner, weapon_cfg))
        else:
            # Single bullet (standard_shell, bouncing_round, homing_missile)
            dx, dy = heading_to_vec(eangle)
            bx = ex + dx * TANK_BARREL_LENGTH
            by = ey + dy * TANK_BARREL_LENGTH
            bullet = Bullet(bx, by, eangle, owner, weapon_cfg)
            if float(weapon_cfg.get("tracking_strength", 0)) > 0:
                bullet.set_targets_getter(lambda: [self._tank] + self._ai_tanks)
            self._bullets.append(bullet)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        if self._camera is None or self._tank is None:
            return

        _draw_arena(surface, self._camera, self._theme)
        _draw_pickups(surface, self._pickup_spawner.active_pickups, self._camera, self._pickup_configs)
        _draw_obstacles(surface, self._obstacles, self._camera, self._theme)
        self._debris.draw(surface, self._camera)

        # AI tanks drawn before player (player renders on top if overlapping)
        for ai_tank, ai_surf in zip(self._ai_tanks, self._ai_surfs):
            _draw_tank(surface, ai_tank, ai_surf, self._camera)

        _draw_tank(surface, self._tank, self._tank_surf, self._camera)

        # Per-type VFX on tanks
        _draw_tank_effects(surface, self._tank, self._camera)
        for ai_tank in self._ai_tanks:
            _draw_tank_effects(surface, ai_tank, self._camera)

        _draw_bullets(surface, self._bullets, self._camera)

        if self._hud:
            self._hud.draw(
                surface, self._tank, self._ai_tanks,
                weapon_slots=self._tank.weapon_slots,
                active_slot=self._tank.active_slot,
            )

        # Reticle — drawn after entities, before debug; hidden when paused or player dead
        if self._tank.is_alive:
            _draw_reticle(surface)

        # Debug overlay — first AI used for state label
        first_ai = self._ai_tanks[0] if self._ai_tanks else None
        first_ctrl = self._ai_controllers[0] if self._ai_controllers else None
        ai_state = first_ctrl.state_name if first_ctrl else "—"
        _draw_debug(surface, self._tank, self._camera, first_ai, ai_state)
        for ai_tank in self._ai_tanks:
            if ai_tank.is_alive:
                _draw_ai_overlay(surface, ai_tank, self._camera)


# ---------------------------------------------------------------------------
# Module-level drawing helpers
# ---------------------------------------------------------------------------

def _build_tank_surface(body_color: tuple) -> pygame.Surface:
    """Create a hull-only surface (no barrel).  The barrel is drawn separately
    in _draw_tank using the tank's independent turret_angle."""
    surf = pygame.Surface((TANK_BODY_WIDTH, TANK_BODY_HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(surf, body_color, (0, 0, TANK_BODY_WIDTH, TANK_BODY_HEIGHT), border_radius=5)
    return surf


def _draw_arena(surface: pygame.Surface, camera: Camera, theme: dict | None = None) -> None:
    """Draw the arena floor, grid lines, and border using theme colors when available.

    Falls back to the constants (ARENA_FLOOR_COLOR etc.) if no theme is supplied,
    ensuring backward compatibility with any call sites that omit the theme.
    """
    floor_color  = tuple(theme["floor_color"])       if theme and "floor_color"      in theme else ARENA_FLOOR_COLOR
    grid_color   = tuple(theme["floor_grid_color"])  if theme and "floor_grid_color" in theme else ARENA_GRID_COLOR
    border_color = tuple(theme["border_color"])      if theme and "border_color"     in theme else ARENA_BORDER_COLOR
    border_thick = int(theme["border_thickness"])    if theme and "border_thickness" in theme else ARENA_BORDER_THICKNESS

    ax, ay = camera.world_to_screen(0, 0)
    ax_i, ay_i = int(ax), int(ay)
    floor_rect = pygame.Rect(ax_i, ay_i, ARENA_WIDTH, ARENA_HEIGHT)
    pygame.draw.rect(surface, floor_color, floor_rect)
    for wx in range(0, ARENA_WIDTH + 1, ARENA_GRID_STEP):
        sx = ax_i + wx
        pygame.draw.line(surface, grid_color, (sx, ay_i), (sx, ay_i + ARENA_HEIGHT))
    for wy in range(0, ARENA_HEIGHT + 1, ARENA_GRID_STEP):
        sy = ay_i + wy
        pygame.draw.line(surface, grid_color, (ax_i, sy), (ax_i + ARENA_WIDTH, sy))

    # Themed perimeter walls
    wall_color = tuple(theme.get("wall_color", border_color)) if theme else border_color
    wt = ARENA_WALL_THICKNESS
    # Top wall
    pygame.draw.rect(surface, wall_color, (ax_i, ay_i - wt, ARENA_WIDTH, wt))
    # Bottom wall
    pygame.draw.rect(surface, wall_color, (ax_i, ay_i + ARENA_HEIGHT, ARENA_WIDTH, wt))
    # Left wall (spans full height including corners)
    pygame.draw.rect(surface, wall_color, (ax_i - wt, ay_i - wt, wt, ARENA_HEIGHT + 2 * wt))
    # Right wall
    pygame.draw.rect(surface, wall_color, (ax_i + ARENA_WIDTH, ay_i - wt, wt, ARENA_HEIGHT + 2 * wt))

    # 1px inner-edge highlight for 3D wall effect
    bright = tuple(min(255, c + 40) for c in wall_color)
    pygame.draw.line(surface, bright, (ax_i, ay_i), (ax_i + ARENA_WIDTH - 1, ay_i))                         # top inner
    pygame.draw.line(surface, bright, (ax_i, ay_i + ARENA_HEIGHT - 1), (ax_i + ARENA_WIDTH - 1, ay_i + ARENA_HEIGHT - 1))  # bottom inner
    pygame.draw.line(surface, bright, (ax_i, ay_i), (ax_i, ay_i + ARENA_HEIGHT - 1))                         # left inner
    pygame.draw.line(surface, bright, (ax_i + ARENA_WIDTH - 1, ay_i), (ax_i + ARENA_WIDTH - 1, ay_i + ARENA_HEIGHT - 1))   # right inner


_PICKUP_INITIALS = {"health": "H", "rapid_reload": "R", "speed_boost": "S", "shield": "D"}


def _draw_pickups(
    surface: pygame.Surface,
    pickups: list,
    camera: Camera,
    configs: dict,
) -> None:
    """Draw active pickups as pulsing colored circles with glow ring and type initials."""
    font = pygame.font.Font(None, 24)
    for p in pickups:
        if not p.is_alive:
            continue
        cfg = configs.get(p.pickup_type, {})
        color = tuple(cfg.get("color", (200, 200, 200)))
        base_r = PICKUP_RENDER_RADIUS
        scale = 1.0 + PICKUP_PULSE_AMPLITUDE * math.sin(p._pulse_timer * PICKUP_PULSE_SPEED)
        render_r = int(base_r * scale)
        sx, sy = camera.world_to_screen(p.x, p.y)
        cx, cy = int(sx), int(sy)

        # Glow ring
        glow_r = int(render_r * PICKUP_GLOW_SCALE)
        glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*color, PICKUP_GLOW_ALPHA),
                           (glow_r, glow_r), glow_r)
        surface.blit(glow_surf, (cx - glow_r, cy - glow_r))

        # Main circle
        pygame.draw.circle(surface, color, (cx, cy), render_r)
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), render_r, 2)

        # Letter
        letter = _PICKUP_INITIALS.get(p.pickup_type, "?")
        txt = font.render(letter, True, (0, 0, 0))
        surface.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))


def _draw_obstacles(
    surface: pygame.Surface,
    obstacles: list,
    camera: Camera,
    theme: dict | None = None,
) -> None:
    """Draw obstacles with damage-state coloring and crack overlays."""
    for obs in obstacles:
        if not obs.is_alive:
            continue
        sx, sy = camera.world_to_screen(obs.x, obs.y)
        rect = pygame.Rect(int(sx), int(sy), int(obs.width), int(obs.height))

        # current_color handles flash + damage-state darkening
        fill = obs.current_color
        pygame.draw.rect(surface, fill, rect)
        pygame.draw.rect(surface, OBSTACLE_BORDER_COLOR, rect, 2)

        # Crack overlay for damaged destructible obstacles
        if obs.destructible and obs.hp_ratio < 0.66:
            _draw_cracks(surface, obs, rect)


def _draw_cracks(
    surface: pygame.Surface,
    obs,
    rect: pygame.Rect,
) -> None:
    """Draw deterministic crack lines on a damaged obstacle."""
    rng = random.Random(int(obs.x + obs.y * 1000))
    crack_col = blend_colors(obs.base_color, (0, 0, 0), DAMAGE_CRACK_DARKEN)
    critical = obs.hp_ratio < 0.33
    num_cracks = 3 if critical else 2
    line_w = 2 if critical else 1

    for _ in range(num_cracks):
        x1 = rect.x + rng.randint(max(1, int(rect.w * 0.1)), max(2, int(rect.w * 0.9)))
        y1 = rect.y + rng.randint(max(1, int(rect.h * 0.1)), max(2, int(rect.h * 0.9)))
        dx = rng.randint(-max(1, int(rect.w * 0.4)), max(1, int(rect.w * 0.4)))
        dy = rng.randint(-max(1, int(rect.h * 0.4)), max(1, int(rect.h * 0.4)))
        x2 = max(rect.x, min(rect.right, x1 + dx))
        y2 = max(rect.y, min(rect.bottom, y1 + dy))
        pygame.draw.line(surface, crack_col, (x1, y1), (x2, y2), line_w)


def _draw_tank(
    surface: pygame.Surface,
    tank: Tank,
    tank_surf: pygame.Surface,
    camera: Camera,
) -> None:
    """Two-pass tank renderer.

    Pass 1 — Hull: rotated to tank.angle (where the body is pointing).
    Pass 2 — Barrel: a thin rotated rectangle aligned to tank.turret_angle
              (where the gun is aiming).  Drawn on top of the hull so the
              visual separation between hull direction and aim direction is clear.
    """
    if not tank.is_alive:
        return
    sx, sy = camera.world_to_screen(tank.x, tank.y)
    isx, isy = int(sx), int(sy)

    # Pass 1: hull
    rotated_hull = pygame.transform.rotate(tank_surf, -tank.angle)
    hull_rect = rotated_hull.get_rect(center=(isx, isy))
    surface.blit(rotated_hull, hull_rect)

    # Front stripe — bright accent line on leading edge
    rad_hull = math.radians(tank.angle)
    cos_a, sin_a = math.cos(rad_hull), math.sin(rad_hull)
    hw = TANK_BODY_WIDTH / 2
    hh = TANK_BODY_HEIGHT / 2
    fcx = isx + int(cos_a * hw)
    fcy = isy + int(sin_a * hw)
    px, py = -sin_a * hh, cos_a * hh
    p1 = (int(fcx + px), int(fcy + py))
    p2 = (int(fcx - px), int(fcy - py))
    tc = tank_surf.get_at((tank_surf.get_width() // 2, tank_surf.get_height() // 2))[:3]
    bright = tuple(min(255, c + TANK_FRONT_STRIPE_BRIGHTEN) for c in tc)
    pygame.draw.line(surface, bright, p1, p2, TANK_FRONT_STRIPE_WIDTH)

    # Pass 2: barrel — centered TANK_BARREL_LENGTH/2 + 4 pixels ahead of tank center
    # along turret_angle so it extends from center to (TANK_BARREL_LENGTH + 8) px forward.
    barrel_length = TANK_BARREL_LENGTH + 8   # total pixel length of barrel rect
    half_len = barrel_length / 2.0
    rad = math.radians(tank.turret_angle)
    bcx = isx + int(math.cos(rad) * half_len)
    bcy = isy + int(math.sin(rad) * half_len)
    draw_rotated_rect(
        surface,
        TANK_BARREL_COLOR,
        center=(bcx, bcy),
        width=barrel_length,
        height=TANK_BARREL_WIDTH,
        angle_deg=tank.turret_angle,
    )


def _draw_tank_effects(
    surface: pygame.Surface,
    tank: Tank,
    camera: Camera,
) -> None:
    """Draw per-type visual effects around a tank with active status effects."""
    if not tank.is_alive or not tank.status_effects:
        return
    sx, sy = camera.world_to_screen(tank.x, tank.y)
    cx, cy = int(sx), int(sy)
    t = time.monotonic()

    if tank.has_status("regen"):
        # Pulsing heart / cross above tank
        pulse = (math.sin(t * 4.0) + 1.0) / 2.0
        size = int(6 + 3 * pulse)
        hx, hy = cx, cy - BUFF_ICON_OFFSET_Y
        pygame.draw.line(surface, VFX_REGEN_COLOR, (hx - size, hy), (hx + size, hy), 2)
        pygame.draw.line(surface, VFX_REGEN_COLOR, (hx, hy - size), (hx, hy + size), 2)

    if tank.has_status("speed_boost"):
        # Speed lines behind the tank
        for i in range(3):
            offset = int(8 + i * 5)
            alpha = max(60, 180 - i * 50)
            y_off = -6 + i * 6
            line_surf = pygame.Surface((offset, 2), pygame.SRCALPHA)
            line_surf.fill((*VFX_SPEED_COLOR, alpha))
            surface.blit(line_surf, (cx - TANK_BODY_WIDTH // 2 - offset, cy + y_off))

    if tank.has_status("rapid_reload"):
        # Spinning rings around tank
        ring_r = int(TANK_BODY_WIDTH * 0.7 + 3 * math.sin(t * 6.0))
        overlay = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (*VFX_RELOAD_COLOR, 100),
                           (ring_r + 2, ring_r + 2), ring_r, 2)
        surface.blit(overlay, (cx - ring_r - 2, cy - ring_r - 2))

    if tank.has_status("shield"):
        # Soap bubble — translucent circle with shimmer
        shield_data = tank.status_effects.get("shield", {})
        shield_hp = shield_data.get("shield_hp", 0)
        # Bubble radius pulsates gently
        bubble_r = int(TANK_BODY_WIDTH * 0.85 + 2 * math.sin(t * 3.0))
        bubble_surf = pygame.Surface((bubble_r * 2 + 4, bubble_r * 2 + 4), pygame.SRCALPHA)
        alpha = max(40, min(120, int(shield_hp * 2)))
        pygame.draw.circle(bubble_surf, (*VFX_SHIELD_COLOR, alpha),
                           (bubble_r + 2, bubble_r + 2), bubble_r, 3)
        # Shimmer highlight
        highlight_angle = t * 2.0
        hx2 = int(bubble_r + 2 + bubble_r * 0.5 * math.cos(highlight_angle))
        hy2 = int(bubble_r + 2 + bubble_r * 0.5 * math.sin(highlight_angle))
        pygame.draw.circle(bubble_surf, (255, 255, 255, 60), (hx2, hy2), 4)
        surface.blit(bubble_surf, (cx - bubble_r - 2, cy - bubble_r - 2))


def _draw_bullets(surface: pygame.Surface, bullets: list, camera: Camera) -> None:
    for bullet in bullets:
        if not bullet.is_alive:
            continue
        sx, sy = camera.world_to_screen(bullet.x, bullet.y)
        if bullet._tracking_strength > 0:
            pygame.draw.circle(surface, HOMING_BULLET_COLOR, (int(sx), int(sy)), HOMING_BULLET_RADIUS)
        else:
            pygame.draw.circle(surface, BULLET_COLOR, (int(sx), int(sy)), BULLET_RADIUS)


def _draw_reticle(surface: pygame.Surface) -> None:
    """
    Draw a neon-pink crosshair at the current mouse screen position.
    Mouse position is already in screen space — no camera transform needed.
    The system cursor is hidden during gameplay (set in GameplayScene.on_enter).
    """
    mx, my = pygame.mouse.get_pos()
    ll = RETICLE_LINE_LENGTH
    r = RETICLE_RADIUS
    # Horizontal and vertical arms
    pygame.draw.line(surface, RETICLE_COLOR, (mx - ll, my), (mx + ll, my), 1)
    pygame.draw.line(surface, RETICLE_COLOR, (mx, my - ll), (mx, my + ll), 1)
    # Circle
    pygame.draw.circle(surface, RETICLE_COLOR, (mx, my), r, 1)


def _draw_debug(
    surface: pygame.Surface,
    player_tank: Tank,
    camera: Camera,
    ai_tank: Tank | None = None,
    ai_state: str = "—",
) -> None:
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


def _draw_ai_overlay(
    surface: pygame.Surface,
    ai_tank: Tank,
    camera: Camera,
) -> None:
    sx, sy = camera.world_to_screen(ai_tank.x, ai_tank.y)
    cx, cy = int(sx), int(sy)
    det_r = int(AI_DETECTION_RANGE)
    atk_r = int(AI_ATTACK_RANGE)
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(overlay, (255, 220, 0, 55), (cx, cy), det_r, 1)
    pygame.draw.circle(overlay, (220, 50, 47, 55), (cx, cy), atk_r, 1)
    surface.blit(overlay, (0, 0))
    font = pygame.font.SysFont(None, 18)
    lbl_detect = font.render("DETECT", True, (200, 180, 0))
    lbl_attack = font.render("ATTACK", True, (200, 70, 70))
    surface.blit(lbl_detect, (cx - lbl_detect.get_width() // 2, cy - det_r - 14))
    surface.blit(lbl_attack, (cx - lbl_attack.get_width() // 2, cy - atk_r - 14))
