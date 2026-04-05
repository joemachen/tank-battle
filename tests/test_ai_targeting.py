"""
tests/test_ai_targeting.py

Tests for make_nearest_enemy_getter (v0.32) and Watch Mode integration.
"""

import pytest

from game.systems.ai_controller import make_nearest_enemy_getter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Tank:
    """Minimal tank stub."""
    def __init__(self, x=0.0, y=0.0, is_alive=True, health_ratio=1.0):
        self.x = x
        self.y = y
        self.is_alive = is_alive
        self.health_ratio = health_ratio

    @property
    def position(self):
        return (self.x, self.y)


# ---------------------------------------------------------------------------
# TestNearestEnemyGetter
# ---------------------------------------------------------------------------

class TestNearestEnemyGetter:

    def test_returns_nearest_living_tank(self):
        owner = _Tank(x=0, y=0)
        near  = _Tank(x=100, y=0)
        mid   = _Tank(x=200, y=0)
        far   = _Tank(x=300, y=0)
        roster = [owner, near, mid, far]
        getter = make_nearest_enemy_getter(owner, lambda: roster)
        assert getter() is near

    def test_excludes_owner(self):
        owner  = _Tank(x=0, y=0)
        enemy  = _Tank(x=50, y=0)
        # owner is "closer" at distance 0, but must be excluded
        roster = [owner, enemy]
        getter = make_nearest_enemy_getter(owner, lambda: roster)
        assert getter() is enemy

    def test_excludes_dead_tanks(self):
        owner = _Tank(x=0, y=0)
        dead  = _Tank(x=10, y=0, is_alive=False)
        alive = _Tank(x=200, y=0, is_alive=True)
        roster = [owner, dead, alive]
        getter = make_nearest_enemy_getter(owner, lambda: roster)
        assert getter() is alive

    def test_returns_none_when_no_living_enemies(self):
        owner = _Tank(x=0, y=0)
        dead1 = _Tank(x=50, y=0, is_alive=False)
        dead2 = _Tank(x=100, y=0, is_alive=False)
        roster = [owner, dead1, dead2]
        getter = make_nearest_enemy_getter(owner, lambda: roster)
        assert getter() is None

    def test_returns_none_when_roster_only_owner(self):
        owner = _Tank(x=0, y=0)
        getter = make_nearest_enemy_getter(owner, lambda: [owner])
        assert getter() is None

    def test_returns_none_when_roster_empty(self):
        owner = _Tank(x=0, y=0)
        getter = make_nearest_enemy_getter(owner, lambda: [])
        assert getter() is None

    def test_updates_dynamically(self):
        """Killing the nearest tank causes the next call to return the next-nearest."""
        owner  = _Tank(x=0, y=0)
        near   = _Tank(x=50, y=0, is_alive=True)
        far    = _Tank(x=400, y=0, is_alive=True)
        roster = [owner, near, far]
        getter = make_nearest_enemy_getter(owner, lambda: roster)

        assert getter() is near

        # Kill the nearest
        near.is_alive = False
        assert getter() is far

    def test_single_living_enemy(self):
        owner  = _Tank(x=0, y=0)
        enemy  = _Tank(x=999, y=0)
        getter = make_nearest_enemy_getter(owner, lambda: [owner, enemy])
        assert getter() is enemy

    def test_nearest_by_euclidean_distance(self):
        """Diagonal distance, not axis-aligned."""
        owner  = _Tank(x=0, y=0)
        # both at same x-distance but different y
        a = _Tank(x=100, y=100)   # dist = ~141
        b = _Tank(x=150, y=0)     # dist = 150
        getter = make_nearest_enemy_getter(owner, lambda: [owner, a, b])
        assert getter() is a

    def test_all_tanks_getter_called_fresh_each_invocation(self):
        """Roster changes between calls are reflected."""
        owner  = _Tank(x=0, y=0)
        initial_enemy = _Tank(x=100, y=0)
        roster = [owner, initial_enemy]
        getter = make_nearest_enemy_getter(owner, lambda: roster)

        assert getter() is initial_enemy

        # Add a closer tank dynamically
        closer = _Tank(x=10, y=0)
        roster.append(closer)
        assert getter() is closer

    def test_owner_in_roster_at_same_position_not_returned(self):
        """Owner at (0,0) and enemy also at (0,0) — owner must be excluded."""
        owner = _Tank(x=0, y=0)
        same_pos = _Tank(x=0, y=0)
        getter = make_nearest_enemy_getter(owner, lambda: [owner, same_pos])
        assert getter() is same_pos

    def test_multiple_dead_skipped_returns_nearest_alive(self):
        owner  = _Tank(x=0, y=0)
        dead1  = _Tank(x=10, y=0, is_alive=False)
        dead2  = _Tank(x=20, y=0, is_alive=False)
        alive  = _Tank(x=50, y=0, is_alive=True)
        getter = make_nearest_enemy_getter(owner, lambda: [owner, dead1, dead2, alive])
        assert getter() is alive


# ---------------------------------------------------------------------------
# TestLowHpPriority
# ---------------------------------------------------------------------------

class TestLowHpPriority:

    def test_low_hp_target_preferred_over_closer_healthy_target(self):
        """High weight causes a far but near-dead tank to beat a closer healthy one."""
        owner  = _Tank(x=0, y=0)
        a      = _Tank(x=200, y=0, health_ratio=1.0)   # closer, full HP
        b      = _Tank(x=400, y=0, health_ratio=0.1)   # farther, near-dead
        getter = make_nearest_enemy_getter(owner, lambda: [owner, a, b], low_hp_priority_weight=1.2)
        assert getter() is b

    def test_zero_weight_returns_nearest_regardless_of_hp(self):
        """weight=0.0 disables HP discount — pure distance selection."""
        owner  = _Tank(x=0, y=0)
        a      = _Tank(x=200, y=0, health_ratio=1.0)
        b      = _Tank(x=400, y=0, health_ratio=0.1)
        getter = make_nearest_enemy_getter(owner, lambda: [owner, a, b], low_hp_priority_weight=0.0)
        assert getter() is a

    def test_sticky_target_not_dropped_while_low_hp(self):
        """Once a target is below 40% HP it is locked in even if a closer tank appears."""
        owner  = _Tank(x=0, y=0)
        b      = _Tank(x=400, y=0, health_ratio=0.1)
        roster = [owner, b]
        getter = make_nearest_enemy_getter(owner, lambda: roster, low_hp_priority_weight=1.2)

        # First call: selects b
        assert getter() is b

        # Add a closer full-HP tank — stickiness should keep b
        c = _Tank(x=50, y=0, health_ratio=1.0)
        roster.append(c)
        assert getter() is b

    def test_sticky_target_released_when_dead(self):
        """Cached low-HP target dying causes re-evaluation on next call."""
        owner  = _Tank(x=0, y=0)
        near   = _Tank(x=100, y=0, health_ratio=1.0)
        dying  = _Tank(x=400, y=0, health_ratio=0.1)
        roster = [owner, near, dying]
        getter = make_nearest_enemy_getter(owner, lambda: roster, low_hp_priority_weight=1.2)

        assert getter() is dying   # dying is selected and cached

        dying.is_alive = False     # it dies
        result = getter()
        assert result is near      # re-evaluates to nearest living enemy

    def test_sticky_target_released_when_hp_recovers_above_threshold(self):
        """Cached target healing above 40% HP releases the sticky lock."""
        owner  = _Tank(x=0, y=0)
        near   = _Tank(x=100, y=0, health_ratio=1.0)
        target = _Tank(x=400, y=0, health_ratio=0.1)
        roster = [owner, near, target]
        getter = make_nearest_enemy_getter(owner, lambda: roster, low_hp_priority_weight=1.2)

        assert getter() is target  # locked onto target

        target.health_ratio = 0.80  # healed above threshold
        result = getter()
        assert result is near       # re-evaluates; near wins on distance


# ---------------------------------------------------------------------------
# TestWatchMode — integration-style with minimal stubs
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _MockManager:
    """Records the last switch_to call."""
    def __init__(self):
        self.last_scene = None
        self.last_kwargs = {}

    def switch_to(self, scene, **kwargs):
        self.last_scene = scene
        self.last_kwargs = kwargs


class _MinimalWatchScene:
    """
    Stripped-down stand-in for GameplayScene that only exercises
    the watch mode logic without pygame or real Tank dependencies.
    """
    def __init__(self):
        self.manager = _MockManager()
        self._tank = _Tank(x=400, y=300, is_alive=True)
        self._ai_tanks = [_Tank(x=100, y=100), _Tank(x=700, y=500)]
        self._watch_mode = False
        # match stats
        self._kills = 0
        self._shots_fired = 0
        self._shots_hit = 0
        self._damage_dealt = 0
        self._damage_taken = 0
        self._match_start_time = 0.0

    def _end_match(self, won: bool):
        self.manager.switch_to(
            "game_over",
            won=won,
            survived=self._tank.is_alive,
        )

    def _check_win_condition(self):
        """Mirrors the watch-mode logic added in game_scene.py."""
        if not self._tank.is_alive and not self._watch_mode:
            self._watch_mode = True

        living_ai = [t for t in self._ai_tanks if t.is_alive]

        if self._watch_mode and len(living_ai) <= 1:
            self._end_match(won=False)
            return "ended"

        if not self._watch_mode and not living_ai:
            self._end_match(won=True)
            return "ended"

        return "continue"


class TestWatchMode:

    def test_watch_mode_not_active_while_player_alive(self):
        scene = _MinimalWatchScene()
        result = scene._check_win_condition()
        assert result == "continue"
        assert scene._watch_mode is False

    def test_watch_mode_activates_on_player_death(self):
        scene = _MinimalWatchScene()
        scene._tank.is_alive = False
        result = scene._check_win_condition()
        assert scene._watch_mode is True
        # Two AI alive → match continues
        assert result == "continue"

    def test_watch_mode_match_ends_when_one_ai_remains(self):
        scene = _MinimalWatchScene()
        scene._tank.is_alive = False
        scene._ai_tanks[0].is_alive = False  # kill first AI
        scene._check_win_condition()  # activates watch mode with 1 AI alive → ends
        assert scene.manager.last_scene == "game_over"
        assert scene.manager.last_kwargs["won"] is False

    def test_watch_mode_match_ends_when_all_ai_dead(self):
        scene = _MinimalWatchScene()
        scene._tank.is_alive = False
        for t in scene._ai_tanks:
            t.is_alive = False
        scene._check_win_condition()
        assert scene.manager.last_scene == "game_over"
        assert scene.manager.last_kwargs["won"] is False

    def test_watch_mode_continues_while_two_ai_fight(self):
        """Two AI still alive → watch mode active but match not yet ended."""
        scene = _MinimalWatchScene()
        scene._tank.is_alive = False
        result = scene._check_win_condition()
        assert scene._watch_mode is True
        assert result == "continue"
        assert scene.manager.last_scene is None

    def test_player_wins_when_all_ai_die_while_alive(self):
        scene = _MinimalWatchScene()
        for t in scene._ai_tanks:
            t.is_alive = False
        scene._check_win_condition()
        assert scene.manager.last_scene == "game_over"
        assert scene.manager.last_kwargs["won"] is True
        assert scene.manager.last_kwargs["survived"] is True

    def test_watch_mode_loss_marks_survived_false(self):
        scene = _MinimalWatchScene()
        scene._tank.is_alive = False
        for t in scene._ai_tanks:
            t.is_alive = False
        scene._check_win_condition()
        assert scene.manager.last_kwargs["survived"] is False

    def test_simultaneous_player_and_last_ai_death_is_loss(self):
        """Both player and last AI die in same frame → loss (not win)."""
        scene = _MinimalWatchScene()
        scene._tank.is_alive = False
        scene._ai_tanks[0].is_alive = False
        scene._ai_tanks[1].is_alive = False
        scene._check_win_condition()
        assert scene.manager.last_kwargs["won"] is False
