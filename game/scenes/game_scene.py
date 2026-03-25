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
from game.entities.explosion import Explosion
from game.entities.obstacle import Obstacle
from game.entities.tank import Tank, TankInput
from game.scenes.base_scene import BaseScene
from game.systems.ai_controller import AIController
from game.systems.collision import CollisionSystem
from game.systems.debris_system import DebrisSystem
from game.systems.elemental_resolver import ElementalResolver
from game.systems.input_handler import InputHandler
from game.systems.pickup_spawner import PickupSpawner
from game.systems.match_calculator import MatchCalculator
from game.systems.physics import PhysicsSystem
from game.ui.audio_manager import get_audio_manager
from game.ui.hud import HUD
from game.utils.camera import Camera
from game.utils.damage_types import DamageType
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
    DAMAGE_TYPE_BULLET_COLORS,
    EXPLOSION_COLOR,
    EXPLOSION_RING_COLOR,
    EXPLOSION_VISUAL_DURATION,
    GRENADE_BULLET_RADIUS,
    HOMING_BULLET_COLOR,
    HOMING_BULLET_RADIUS,
    MAX_RUBBLE_PIECES,
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
    COMBAT_EFFECT_SFX,
    COMBO_SFX,
    STATUS_MUSIC_LAYERS,
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
    SFX_EXPLOSION,
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
from game.utils.map_loader import load_map, _load_materials
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
        self._explosions: list[Explosion] = []
        self._obstacles = map_data["obstacles"]
        self._theme = map_data["theme"]
        self._materials: dict = _load_materials()

        # Pre-compute theme-tinted base color on each obstacle
        _tint = tuple(self._theme.get("obstacle_tint", (128, 128, 128)))
        self._theme_tint = _tint
        for _obs in self._obstacles:
            _obs.base_color = blend_colors(_obs.color, _tint, THEME_TINT_BLEND)

        # Debris system for destruction effects
        self._debris = DebrisSystem()
        self._destroyed_set: set[int] = set()

        # Shared getter — used by both PickupSpawner and AI controllers
        live_obstacles = lambda: [o for o in self._obstacles if o.is_alive]  # noqa: E731

        # Pickup spawner
        self._pickup_configs = load_yaml(PICKUPS_CONFIG)
        pickup_spawns = map_data.get("pickup_spawns", [])
        self._pickup_spawner = PickupSpawner(pickup_spawns, self._pickup_configs)
        self._pickup_spawner.set_obstacles_getter(live_obstacles)

        # AI tanks — all heavy_tank, shared difficulty, independent controllers
        ai_difficulty = get_ai_config(ai_difficulty_key, AI_DIFFICULTY_CONFIG)
        ai_tank_config = get_tank_config("heavy_tank", TANKS_CONFIG)
        self._ai_tanks = []
        self._ai_controllers = []
        self._ai_surfs = []

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
        # Per-pickup music layers — tracks which layers are currently playing
        self._active_buff_layers: set[str] = set()
        # Combat effect SFX — tracks which effects have already played their onset SFX
        self._active_combat_sfx: set[str] = set()
        # Elemental interaction resolver (v0.24)
        self._elemental_resolver = ElementalResolver()
        self._combo_visuals: list[dict] = []
        self._player_combo_text: str = ""
        self._player_combo_timer: float = 0.0
        self._player_combo_color: tuple = (255, 255, 255)
        # Speed boost trail history — position samples for physics-based speed lines
        self._speed_trail_history: dict[int, list[tuple[float, float]]] = {}
        self._trail_timer: float = 0.0

        music_track = self._theme.get("music_override") or MUSIC_GAMEPLAY
        audio = get_audio_manager()
        audio.play_music(music_track)

        log.info(
            "GameplayScene ready. Player: %s  AI count: %d  Difficulty: %s  Weapons: %s",
            tank_type, ai_count, ai_difficulty_key, weapon_types,
        )

    def on_exit(self) -> None:
        log.info("GameplayScene exited.")
        get_audio_manager().stop_all_layers()
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
        self._explosions = []
        self._combo_visuals = []

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

        # Check for max-range grenade detonations before pruning dead bullets
        for bullet in self._bullets:
            if getattr(bullet, '_detonated', False) and getattr(bullet, 'is_explosive', False):
                self._explosions.append(
                    Explosion(bullet.x, bullet.y, bullet.aoe_radius, bullet.damage,
                              bullet.damage_type, bullet.owner, bullet.aoe_falloff)
                )
        self._bullets = [b for b in self._bullets if b.is_alive]

        # Record speed trail positions for physics-based speed lines
        _TRAIL_MAX_POINTS = 6
        _TRAIL_RECORD_INTERVAL = 0.03
        self._trail_timer += dt
        if self._trail_timer >= _TRAIL_RECORD_INTERVAL:
            self._trail_timer = 0.0
            for tank in all_tanks:
                if not tank.is_alive or not tank.has_status("speed_boost"):
                    self._speed_trail_history.pop(id(tank), None)
                    continue
                if math.hypot(tank.vx, tank.vy) < 20.0:
                    continue
                history = self._speed_trail_history.setdefault(id(tank), [])
                history.append((tank.x, tank.y))
                if len(history) > _TRAIL_MAX_POINTS:
                    history.pop(0)

        # Tick pickup spawner
        self._pickup_spawner.update(dt)

        # Snapshot state before collision resolution for stat tracking
        player_hp_before = self._tank.health
        ai_alive_before = {id(t): t.is_alive for t in self._ai_tanks}

        # Collision: bullets, obstacles, tank-to-tank, explosions
        audio_events, new_explosions = self._collision.update(
            tanks=all_tanks,
            bullets=self._bullets,
            obstacles=self._obstacles,
            pickups=self._pickup_spawner.active_pickups,
            explosions=self._explosions,
        )
        self._explosions.extend(new_explosions)
        self._bullets = [b for b in self._bullets if b.is_alive]

        # Elemental interaction check (v0.24)
        combo_events = self._elemental_resolver.resolve(all_tanks)
        for combo in combo_events:
            self._process_elemental_combo(combo)

        # Tick combo visual timers
        for cv in self._combo_visuals:
            cv["timer"] -= dt
        self._combo_visuals = [cv for cv in self._combo_visuals if cv["timer"] > 0]
        if self._player_combo_timer > 0:
            self._player_combo_timer -= dt

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
            "explosion":           SFX_EXPLOSION,
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
                _, owner, dmg, *_ = ev
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

        # Detect newly destroyed obstacles → spawn debris + rubble
        for obs in list(self._obstacles):
            if not obs.is_alive and id(obs) not in self._destroyed_set:
                self._destroyed_set.add(id(obs))
                count = DEBRIS_COUNT.get(obs.material_type, DEBRIS_COUNT_DEFAULT)
                self._debris.spawn_debris(
                    obs.x + obs.width / 2, obs.y + obs.height / 2,
                    obs.width, obs.height, obs.base_color, count,
                )
                # Partial destruction → spawn rubble pieces (v0.22)
                if obs.partial_destruction:
                    rubble_count = sum(1 for o in self._obstacles
                                       if o.is_alive and o.material_type == "rubble")
                    if rubble_count < MAX_RUBBLE_PIECES:
                        for piece in obs.get_rubble_pieces(self._materials):
                            piece.base_color = blend_colors(
                                piece.color, self._theme_tint, THEME_TINT_BLEND)
                            self._obstacles.append(piece)

        # Update debris particles
        self._debris.update(dt)

        # Tick explosion visual timers and prune expired
        for exp in self._explosions:
            exp.update(dt)
        self._explosions = [e for e in self._explosions if e.visual_alive]

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

        # Combat effect SFX — play onset sound when a new combat effect appears
        current_combat: set[str] = set()
        for tank in all_tanks:
            if tank.is_alive:
                for name in tank.combat_effects:
                    current_combat.add(name)
        for eff in current_combat - self._active_combat_sfx:
            sfx_path = COMBAT_EFFECT_SFX.get(eff)
            if sfx_path:
                audio.play_sfx(sfx_path)
        self._active_combat_sfx = current_combat

        # Music layers: start/stop per-pickup audio layers based on active buffs
        current_buffs: set[str] = set()
        for tank in all_tanks:
            if tank.is_alive:
                for name in tank.active_status_names:
                    current_buffs.add(name)
        for buff in current_buffs - self._active_buff_layers:
            path = STATUS_MUSIC_LAYERS.get(buff)
            if path:
                audio.start_music_layer(buff, path)
        for buff in self._active_buff_layers - current_buffs:
            path = STATUS_MUSIC_LAYERS.get(buff)
            if path:
                audio.stop_music_layer(buff)
        self._active_buff_layers = current_buffs

    def _process_elemental_combo(self, combo: dict) -> None:
        """Handle an elemental combo event (v0.24)."""
        tank = combo["tank"]
        cfg = combo["config"]
        name = combo["name"]
        result_type = cfg.get("result_type", "")
        audio = get_audio_manager()

        # Direct damage to the affected tank
        direct_damage = int(cfg.get("damage", 0))
        if direct_damage > 0 and tank.is_alive:
            tank.take_damage(direct_damage, damage_type=DamageType.STANDARD)

        # AoE burst — spawn an explosion at the tank's position
        if result_type == "aoe_burst":
            aoe_radius = float(cfg.get("aoe_radius", 0))
            aoe_damage = int(cfg.get("aoe_damage", 0))
            if aoe_radius > 0 and aoe_damage > 0:
                exp = Explosion(
                    tank.x, tank.y, aoe_radius, aoe_damage,
                    DamageType.STANDARD, owner=None,
                    damage_falloff=0.3, visual_duration=0.5,
                )
                self._explosions.append(exp)

        # Stun
        if result_type == "stun":
            stun_dur = float(cfg.get("stun_duration", 0))
            if stun_dur > 0:
                tank.apply_stun(stun_dur)

        # SFX
        sfx_key = cfg.get("sfx_key", "")
        sfx_path = COMBO_SFX.get(sfx_key)
        if sfx_path:
            audio.play_sfx(sfx_path)

        # Visual event — stored for rendering
        color = tuple(cfg.get("color", [255, 255, 255]))
        self._combo_visuals.append({
            "x": tank.x,
            "y": tank.y,
            "color": color,
            "timer": 0.6,
            "radius": float(cfg.get("aoe_radius", 60)) if result_type == "aoe_burst" else 40.0,
            "name": name,
        })

        # Player combo notification
        if tank is self._tank:
            self._player_combo_text = cfg.get("description", name)
            self._player_combo_timer = 2.0
            self._player_combo_color = color

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
        _draw_tank_effects(surface, self._tank, self._camera,
                           self._speed_trail_history.get(id(self._tank)))
        for ai_tank in self._ai_tanks:
            _draw_tank_effects(surface, ai_tank, self._camera,
                               self._speed_trail_history.get(id(ai_tank)))

        _draw_bullets(surface, self._bullets, self._camera)
        _draw_explosions(surface, self._explosions, self._camera)
        _draw_combo_visuals(surface, self._combo_visuals, self._camera)

        # Player combo notification text (v0.24)
        if self._player_combo_timer > 0:
            alpha = min(255, int(255 * (self._player_combo_timer / 2.0)))
            combo_font = pygame.font.SysFont(None, 32)
            combo_text = combo_font.render(self._player_combo_text, True, self._player_combo_color)
            combo_text.set_alpha(alpha)
            cx = surface.get_width() // 2 - combo_text.get_width() // 2
            cy = surface.get_height() // 3
            surface.blit(combo_text, (cx, cy))

        if self._hud:
            self._hud.draw(
                surface, self._tank, self._ai_tanks,
                weapon_slots=self._tank.weapon_slots,
                active_slot=self._tank.active_slot,
                slot_cooldowns=self._tank.slot_cooldowns,
                combat_effects=self._tank.combat_effects,
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
    speed_trail: list[tuple[float, float]] | None = None,
) -> None:
    """Draw per-type visual effects around a tank with active status effects."""
    if not tank.is_alive:
        return
    if not tank.status_effects and not tank.has_any_combat_effect:
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

    if tank.has_status("speed_boost") and speed_trail and len(speed_trail) >= 2:
        # Physics-based speed lines — connect recent position history for organic curves
        for i in range(len(speed_trail) - 1):
            sx1, sy1 = camera.world_to_screen(*speed_trail[i])
            sx2, sy2 = camera.world_to_screen(*speed_trail[i + 1])
            # Alpha fades — older points are more transparent
            alpha = int(60 + (i / len(speed_trail)) * 100)  # 60 → 160
            width = 1 + (i // 2)  # thickens toward the tank
            angle = math.atan2(sy2 - sy1, sx2 - sx1)
            perp_x = math.cos(angle + math.pi / 2)
            perp_y = math.sin(angle + math.pi / 2)
            # 3 parallel trails with perpendicular spread
            for offset in [-4, 0, 4]:
                pygame.draw.line(
                    surface, (*VFX_SPEED_COLOR, alpha),
                    (int(sx1 + perp_x * offset), int(sy1 + perp_y * offset)),
                    (int(sx2 + perp_x * offset), int(sy2 + perp_y * offset)), width)

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

    # Stun indicator — spinning stars above tank (v0.24)
    if tank.is_stunned:
        num_stars = 3
        orbit_r = 14
        star_y_offset = -BUFF_ICON_OFFSET_Y - 8
        for i in range(num_stars):
            star_angle = t * 4.0 + (2 * math.pi / num_stars) * i
            star_x = cx + int(orbit_r * math.cos(star_angle))
            star_y = cy + star_y_offset + int(4 * math.sin(star_angle * 2))
            # 4-point star shape
            pts = []
            for p in range(4):
                a = (math.pi / 2) * p + t * 3
                r_outer = 4
                pts.append((star_x + int(r_outer * math.cos(a)),
                            star_y + int(r_outer * math.sin(a))))
            pygame.draw.polygon(surface, (255, 255, 100), pts)
            pygame.draw.polygon(surface, (255, 200, 0), pts, 1)

    # Combat effects VFX (v0.23)
    combat = tank.combat_effects
    if combat:
        for name, effect in combat.items():
            if name == "fire":
                # Flickering orange-red particles above tank
                for j in range(3):
                    offset_x = int(8 * math.sin(t * 10 + j * 2.1))
                    offset_y = -int(10 + 6 * math.sin(t * 8 + j * 1.7))
                    alpha = int(120 + 60 * math.sin(t * 12 + j))
                    fire_surf = pygame.Surface((8, 8), pygame.SRCALPHA)
                    pygame.draw.circle(fire_surf, (*effect.color, alpha), (4, 4), 4)
                    surface.blit(fire_surf, (cx + offset_x - 4, cy + offset_y - 4))
            elif name == "poison":
                # Green bubbles rising
                for j in range(2):
                    bub_x = cx + int(10 * math.sin(t * 3 + j * 3.14))
                    bub_y = cy - int((t * 20 + j * 12) % 30)
                    alpha = int(100 + 40 * math.sin(t * 5 + j))
                    bub_surf = pygame.Surface((6, 6), pygame.SRCALPHA)
                    pygame.draw.circle(bub_surf, (*effect.color, alpha), (3, 3), 3)
                    surface.blit(bub_surf, (bub_x - 3, bub_y - 3))
            elif name == "ice":
                # Blue frost ring
                frost_r = int(TANK_BODY_WIDTH * 0.8 + 2 * math.sin(t * 2.0))
                frost_surf = pygame.Surface((frost_r * 2 + 4, frost_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(frost_surf, (*effect.color, 80),
                                   (frost_r + 2, frost_r + 2), frost_r, 2)
                surface.blit(frost_surf, (cx - frost_r - 2, cy - frost_r - 2))
            elif name == "electric":
                # Purple spark lines
                for j in range(2):
                    angle = t * 8 + j * math.pi
                    sx1 = cx + int(12 * math.cos(angle))
                    sy1 = cy + int(12 * math.sin(angle))
                    sx2 = cx + int(18 * math.cos(angle + 0.5))
                    sy2 = cy + int(18 * math.sin(angle + 0.5))
                    pygame.draw.line(surface, effect.color, (sx1, sy1), (sx2, sy2), 2)


def _draw_bullets(surface: pygame.Surface, bullets: list, camera: Camera) -> None:
    for bullet in bullets:
        if not bullet.is_alive:
            continue
        sx, sy = camera.world_to_screen(bullet.x, bullet.y)
        if getattr(bullet, 'is_explosive', False):
            # Grenade projectile — larger, orange with dark outline
            pygame.draw.circle(surface, (80, 40, 10), (int(sx), int(sy)), GRENADE_BULLET_RADIUS + 1)
            pygame.draw.circle(surface, EXPLOSION_COLOR, (int(sx), int(sy)), GRENADE_BULLET_RADIUS)
        elif bullet._tracking_strength > 0:
            pygame.draw.circle(surface, HOMING_BULLET_COLOR, (int(sx), int(sy)), HOMING_BULLET_RADIUS)
        else:
            # Color by damage type (v0.21) — falls back to BULLET_COLOR for unknown types
            dtype_name = bullet.damage_type.name if hasattr(bullet.damage_type, 'name') else "STANDARD"
            color = DAMAGE_TYPE_BULLET_COLORS.get(dtype_name, BULLET_COLOR)
            pygame.draw.circle(surface, color, (int(sx), int(sy)), BULLET_RADIUS)


def _draw_explosions(surface: pygame.Surface, explosions: list, camera: Camera) -> None:
    """Draw expanding ring + flash animation for each active explosion."""
    for exp in explosions:
        if not exp.visual_alive:
            continue
        sx, sy = camera.world_to_screen(exp.x, exp.y)
        cx, cy = int(sx), int(sy)
        progress = exp.visual_progress  # 0.0 → 1.0

        # Expanding ring — grows from 0 to full radius
        ring_radius = max(1, int(exp.radius * progress))
        ring_alpha = max(0, int(220 * (1.0 - progress)))
        ring_width = max(1, int(4 * (1.0 - progress)))

        ring_surf = pygame.Surface((ring_radius * 2 + 4, ring_radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (*EXPLOSION_RING_COLOR, ring_alpha),
                           (ring_radius + 2, ring_radius + 2), ring_radius, ring_width)
        surface.blit(ring_surf, (cx - ring_radius - 2, cy - ring_radius - 2))

        # Inner flash — bright at start, shrinks and fades
        if progress < 0.6:
            flash_ratio = 1.0 - (progress / 0.6)
            flash_radius = max(1, int(exp.radius * 0.5 * flash_ratio))
            flash_alpha = max(0, int(180 * flash_ratio))
            flash_surf = pygame.Surface((flash_radius * 2 + 4, flash_radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (*EXPLOSION_COLOR, flash_alpha),
                               (flash_radius + 2, flash_radius + 2), flash_radius)
            surface.blit(flash_surf, (cx - flash_radius - 2, cy - flash_radius - 2))


def _draw_combo_visuals(
    surface: pygame.Surface,
    combo_visuals: list[dict],
    camera: Camera,
) -> None:
    """Draw elemental combo VFX (v0.24)."""
    t = time.monotonic()
    for cv in combo_visuals:
        sx, sy = camera.world_to_screen(cv["x"], cv["y"])
        cx, cy = int(sx), int(sy)
        progress = 1.0 - (cv["timer"] / 0.6)  # 0→1 over lifetime
        color = cv["color"]
        name = cv["name"]

        if name == "steam_burst":
            # Expanding white-gray cloud with multiple rings + center flash
            for i in range(3):
                ring_r = max(1, int(cv["radius"] * (0.3 + 0.7 * progress) * (0.6 + 0.2 * i)))
                alpha = max(0, int(160 * (1.0 - progress) / (1 + i * 0.5)))
                ring_w = max(1, int(3 * (1.0 - progress)))
                ring_surf = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring_surf, (*color, alpha),
                                   (ring_r + 2, ring_r + 2), ring_r, ring_w)
                surface.blit(ring_surf, (cx - ring_r - 2, cy - ring_r - 2))
            # Center flash — bright white, fades quickly
            if progress < 0.4:
                flash_alpha = max(0, int(200 * (1.0 - progress / 0.4)))
                flash_r = max(1, int(20 * (1.0 - progress / 0.4)))
                flash_surf = pygame.Surface((flash_r * 2 + 4, flash_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(flash_surf, (255, 255, 255, flash_alpha),
                                   (flash_r + 2, flash_r + 2), flash_r)
                surface.blit(flash_surf, (cx - flash_r - 2, cy - flash_r - 2))

        elif name == "accelerated_burn":
            # Orange flash + radial spark lines
            flash_r = max(1, int(40 * (1.0 - progress * 0.5)))
            alpha = max(0, int(180 * (1.0 - progress)))
            flash_surf = pygame.Surface((flash_r * 2 + 4, flash_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (*color, alpha),
                               (flash_r + 2, flash_r + 2), flash_r)
            surface.blit(flash_surf, (cx - flash_r - 2, cy - flash_r - 2))
            # Radial spark lines
            num_sparks = 8
            for i in range(num_sparks):
                angle = (2 * math.pi / num_sparks) * i + t * 3
                inner_r = int(15 + 25 * progress)
                outer_r = int(30 + 40 * progress)
                spark_alpha = max(0, int(200 * (1.0 - progress)))
                sx1 = cx + int(inner_r * math.cos(angle))
                sy1 = cy + int(inner_r * math.sin(angle))
                sx2 = cx + int(outer_r * math.cos(angle))
                sy2 = cy + int(outer_r * math.sin(angle))
                spark_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                pygame.draw.line(spark_surf, (*color, spark_alpha), (sx1, sy1), (sx2, sy2), 2)
                surface.blit(spark_surf, (0, 0))

        elif name == "deep_freeze":
            # Hexagonal ice crystal pattern with rotating lines + diamond tips
            hex_r = int(30 + 15 * progress)
            alpha = max(0, int(200 * (1.0 - progress)))
            rotation = t * 2.0
            for i in range(6):
                angle = rotation + (math.pi / 3) * i
                lx = cx + int(hex_r * math.cos(angle))
                ly = cy + int(hex_r * math.sin(angle))
                # Crystal lines from center
                line_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                pygame.draw.line(line_surf, (*color, alpha), (cx, cy), (lx, ly), 2)
                surface.blit(line_surf, (0, 0))
                # Diamond tip at each endpoint
                tip_size = max(1, int(4 * (1.0 - progress)))
                diamond = [
                    (lx, ly - tip_size),
                    (lx + tip_size, ly),
                    (lx, ly + tip_size),
                    (lx - tip_size, ly),
                ]
                tip_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(tip_surf, (*color, alpha), diamond)
                surface.blit(tip_surf, (0, 0))


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
