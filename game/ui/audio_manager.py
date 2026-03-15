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
        log.debug("Music stopped.")

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
        log.debug("Volume set: %s = %.2f", channel, value)
