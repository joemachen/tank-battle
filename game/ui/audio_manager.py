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
    MUSIC_GAMEPLAY,
    MUSIC_GAMEPLAY_INTENSE,
    MUSIC_VOLUME_DEFAULT,
    SFX_VOLUME_DEFAULT,
)
from game.utils.logger import get_logger

log = get_logger(__name__)

_instance: "AudioManager | None" = None

# Intensity track plays at 50% of normal music volume to avoid being too loud
_INTENSITY_VOLUME_SCALE: float = 0.5


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

        # Pre-loaded intensity tracks (Sound objects held in memory)
        self._intensity_sounds: dict[str, "pygame.mixer.Sound"] = {}
        self._intensity_channel: "pygame.mixer.Channel | None" = None
        self._intensity_active: str | None = None

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
            self._stop_intensity()
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
        self._stop_intensity()
        log.debug("Music stopped.")

    def _stop_intensity(self) -> None:
        """Fade out and clear the intensity channel."""
        if self._intensity_channel is not None:
            self._intensity_channel.fadeout(MUSIC_FADEOUT_MS)
            self._intensity_channel = None
        self._intensity_active = None

    def preload_intensity_tracks(self, normal_path: str, intense_path: str) -> None:
        """Pre-load both gameplay music tracks as Sound objects (in-memory).

        Call once at scene start so that set_music_intensity() can switch
        between them without any disk I/O.
        """
        if not self._initialized:
            return
        for path in (normal_path, intense_path):
            if path not in self._intensity_sounds:
                try:
                    self._intensity_sounds[path] = pygame.mixer.Sound(path)
                    log.debug("Intensity track pre-loaded: %s", path)
                except (pygame.error, FileNotFoundError):
                    log.warning("Failed to pre-load intensity track: %s", path)

    def set_music_intensity(self, intense: bool) -> None:
        """Switch between pre-loaded intensity tracks with no disk I/O.

        Falls back to stream-based play_music() if tracks were not pre-loaded.
        """
        target = MUSIC_GAMEPLAY_INTENSE if intense else MUSIC_GAMEPLAY
        sound = self._intensity_sounds.get(target)
        if sound is None:
            # Fallback: stream from disk (causes hitch but still works)
            self.play_music(target)
            return
        if self._intensity_active == target:
            return
        if not self._initialized:
            return
        # Stop stream-based music if it's playing (first transition)
        if self._current_music is not None:
            pygame.mixer.music.fadeout(500)
            self._current_music = None
        # Fade out current intensity channel
        if self._intensity_channel is not None:
            self._intensity_channel.fadeout(500)
        ch = sound.play(loops=-1, fade_ms=500)
        if ch:
            vol = self._master * self._music_vol
            if intense:
                vol *= _INTENSITY_VOLUME_SCALE
            ch.set_volume(vol)
            self._intensity_channel = ch
        self._intensity_active = target
        log.debug("Music intensity → %s", "intense" if intense else "normal")

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
            if self._intensity_channel is not None:
                vol = self._master * self._music_vol
                if self._intensity_active == MUSIC_GAMEPLAY_INTENSE:
                    vol *= _INTENSITY_VOLUME_SCALE
                self._intensity_channel.set_volume(vol)
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
            if self._intensity_channel is not None:
                vol = self._master * self._music_vol
                if self._intensity_active == MUSIC_GAMEPLAY_INTENSE:
                    vol *= _INTENSITY_VOLUME_SCALE
                self._intensity_channel.set_volume(vol)
        log.info("Audio %s.", "muted" if self._muted else "unmuted")
        return self._muted

    @property
    def is_muted(self) -> bool:
        """Return True if master mute is currently active."""
        return getattr(self, "_muted", False)
