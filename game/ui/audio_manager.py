"""
game/ui/audio_manager.py

AudioManager — singleton that owns ALL audio playback.

Rules:
  - No module other than this one may call pygame.mixer directly.
  - Music crossfade, channel pooling, and volume hierarchy are managed here.
  - SFX are loaded lazily and cached.
"""

import os
import traceback

import pygame

from game.utils.constants import (
    AUDIO_CHANNELS,
    MASTER_VOLUME_DEFAULT,
    MUSIC_FADEOUT_MS,
    MUSIC_VOLUME_DEFAULT,
    SFX_VOLUME_DEFAULT,
)
from game.utils.logger import get_logger

log = get_logger(__name__)

_instance: "AudioManager | None" = None

# Layers at same volume as base music; mix via generator amplitude
_LAYER_VOLUME_SCALE: float = 1.0


def get_audio_manager() -> "AudioManager":
    """Return the singleton AudioManager instance. Creates it on first call."""
    global _instance
    if _instance is None:
        _instance = AudioManager()
    return _instance


class AudioManager:
    """
    Centralized audio controller.

    Volume hierarchy:
        effective_volume = master_volume * channel_volume
    where channel is "music" or "sfx".
    """

    def __init__(self) -> None:
        self._initialized: bool = False
        self._sfx_cache: dict = {}
        self._master: float = MASTER_VOLUME_DEFAULT
        self._music_vol: float = MUSIC_VOLUME_DEFAULT
        self._sfx_vol: float = SFX_VOLUME_DEFAULT
        self._current_music: str | None = None

        # Music layers — per-pickup looping audio overlays
        self._layer_cache: dict[str, "pygame.mixer.Sound"] = {}
        self._active_layers: dict[str, "pygame.mixer.Sound"] = {}
        self._layer_channels: dict[str, "pygame.mixer.Channel"] = {}

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(AUDIO_CHANNELS)
            self._initialized = True
            log.info("AudioManager initialized. Channels: %d", AUDIO_CHANNELS)
        except pygame.error:
            log.warning("pygame.mixer failed to initialize — audio disabled.\n%s", traceback.format_exc())

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    def play_music(self, path: str, loop: bool = True) -> None:
        """Start playing background music. Crossfades if music is already playing."""
        if not self._initialized:
            return
        if self._current_music == path:
            return
        try:
            self.stop_all_layers()
            pygame.mixer.music.fadeout(MUSIC_FADEOUT_MS)
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self._master * self._music_vol)
            pygame.mixer.music.play(-1 if loop else 0)
            self._current_music = path
            log.info("Music playing: %s (loop=%s)", path, loop)
        except (pygame.error, FileNotFoundError):
            log.warning("Failed to play music: %s\n%s", path, traceback.format_exc())

    def stop_music(self) -> None:
        if not self._initialized:
            return
        pygame.mixer.music.fadeout(MUSIC_FADEOUT_MS)
        self._current_music = None
        self.stop_all_layers()
        log.debug("Music stopped.")

    # ------------------------------------------------------------------
    # Music layers
    # ------------------------------------------------------------------

    def start_music_layer(self, name: str, path: str, fade_ms: int = 500) -> None:
        """Start a looping audio layer on a dedicated channel.

        Args:
            name: unique layer identifier (e.g. "speed_boost", "regen")
            path: .wav file path for the loop
            fade_ms: fade-in duration in milliseconds
        """
        if not self._initialized:
            return
        if name in self._active_layers:
            return  # already playing

        # Kill any leftover channel still fading out from a recent stop
        old_ch = self._layer_channels.pop(name, None)
        if old_ch is not None:
            old_ch.stop()

        sound = self._layer_cache.get(path)
        if sound is None:
            try:
                sound = pygame.mixer.Sound(path)
                self._layer_cache[path] = sound
            except (pygame.error, FileNotFoundError):
                log.warning("Failed to load music layer: %s", path)
                return

        channel = pygame.mixer.find_channel()
        if channel is None:
            log.warning("No free channel for music layer '%s'", name)
            return

        sound.set_volume(self._master * self._music_vol * _LAYER_VOLUME_SCALE)
        channel.play(sound, loops=-1, fade_ms=fade_ms)
        self._active_layers[name] = sound
        self._layer_channels[name] = channel
        log.debug("Music layer started: %s", name)

    def stop_music_layer(self, name: str, fade_ms: int = 800) -> None:
        """Stop a playing music layer with fade-out.

        The channel reference is kept in _layer_channels so that
        start_music_layer can hard-stop it if the layer is restarted
        before the fade completes (prevents overlapping hum copies).

        Args:
            name: layer identifier passed to start_music_layer
            fade_ms: fade-out duration in milliseconds
        """
        if not self._initialized:
            return
        self._active_layers.pop(name, None)
        channel = self._layer_channels.get(name)
        if channel is not None:
            channel.fadeout(fade_ms)
        log.debug("Music layer stopped: %s", name)

    def stop_all_layers(self, fade_ms: int = 500) -> None:
        """Stop all active music layers (including fading ones). Called on scene exit."""
        for name in list(self._layer_channels.keys()):
            channel = self._layer_channels[name]
            channel.fadeout(fade_ms)
        self._layer_channels.clear()
        self._active_layers.clear()

    # ------------------------------------------------------------------
    # SFX
    # ------------------------------------------------------------------

    def play_sfx(self, path: str) -> None:
        """Play a one-shot sound effect. Sounds are lazily loaded and cached."""
        if not self._initialized:
            return
        sound = self._get_sound(path)
        if sound:
            sound.set_volume(self._master * self._sfx_vol)
            sound.play()

    def _get_sound(self, path: str) -> "pygame.mixer.Sound | None":
        if path not in self._sfx_cache:
            try:
                self._sfx_cache[path] = pygame.mixer.Sound(path)
                log.debug("SFX loaded: %s", path)
            except (pygame.error, FileNotFoundError):
                log.warning("Failed to load SFX: %s\n%s", path, traceback.format_exc())
                self._sfx_cache[path] = None
        return self._sfx_cache[path]

    # ------------------------------------------------------------------
    # Volume control
    # ------------------------------------------------------------------

    def set_volume(self, channel: str, value: float) -> None:
        """
        Set volume for a channel. channel = "master" | "music" | "sfx".
        value is clamped to [0.0, 1.0].
        """
        value = max(0.0, min(1.0, value))
        if channel == "master":
            self._master = value
        elif channel == "music":
            self._music_vol = value
        elif channel == "sfx":
            self._sfx_vol = value
        else:
            log.warning("Unknown audio channel: '%s'", channel)
            return

        # Apply music volume change immediately
        if self._initialized:
            pygame.mixer.music.set_volume(self._master * self._music_vol)
            layer_vol = self._master * self._music_vol * _LAYER_VOLUME_SCALE
            for sound in self._active_layers.values():
                sound.set_volume(layer_vol)
        log.debug("Volume set: %s = %.2f", channel, value)

    # ------------------------------------------------------------------
    # Mute toggle
    # ------------------------------------------------------------------

    def toggle_mute(self) -> bool:
        """
        Toggle master mute on/off.

        When muting, stores the current master volume and sets it to 0.
        When unmuting, restores the previous master volume.

        Returns:
            True  — audio is now muted
            False — audio is now unmuted
        """
        if getattr(self, "_muted", False):
            # Restore previous volume
            self._master = getattr(self, "_pre_mute_volume", MASTER_VOLUME_DEFAULT)
            self._muted = False
        else:
            self._pre_mute_volume = self._master
            self._master = 0.0
            self._muted = True

        if self._initialized:
            pygame.mixer.music.set_volume(self._master * self._music_vol)
            layer_vol = self._master * self._music_vol * _LAYER_VOLUME_SCALE
            for sound in self._active_layers.values():
                sound.set_volume(layer_vol)
        log.info("Audio %s.", "muted" if self._muted else "unmuted")
        return self._muted

    @property
    def is_muted(self) -> bool:
        """Return True if master mute is currently active."""
        return getattr(self, "_muted", False)
