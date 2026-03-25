"""
scripts/generate_audio.py

Synthesises all placeholder audio assets for TankBattle v0.10.
Uses Python stdlib only (wave, struct, math, random) — no numpy required.

Run from project root:
    python scripts/generate_audio.py

Outputs:
    assets/sounds/sfx_tank_fire.wav
    assets/sounds/sfx_bullet_hit_tank.wav
    assets/sounds/sfx_bullet_hit_obstacle.wav
    assets/sounds/sfx_obstacle_destroy.wav
    assets/sounds/sfx_tank_explosion.wav
    assets/sounds/sfx_tank_collision.wav
    assets/sounds/sfx_ui_navigate.wav
    assets/sounds/sfx_ui_confirm.wav
    assets/music/music_menu.wav
    assets/music/music_gameplay.wav
    assets/music/music_game_over.wav
"""

import math
import os
import random
import struct
import wave

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SAMPLE_RATE: int = 44100
CHANNELS: int = 1   # Mono for SFX; music also mono (pygame mixes fine)
SAMPLE_WIDTH: int = 2  # 16-bit

OUTPUT_DIR_SFX = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")
OUTPUT_DIR_MUSIC = os.path.join(os.path.dirname(__file__), "..", "assets", "music")


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _write_wav(path: str, samples: list[float]) -> None:
    """Write a list of floats (−1.0 … 1.0) to a 16-bit mono WAV file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    max_val = 32767
    packed = struct.pack(f"<{len(samples)}h",
                         *(max(min(int(s * max_val), max_val), -max_val) for s in samples))
    with wave.open(path, "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(packed)
    print(f"  wrote {os.path.relpath(path)}")


def _seconds(s: float) -> int:
    return int(SAMPLE_RATE * s)


# ---------------------------------------------------------------------------
# Oscillators
# ---------------------------------------------------------------------------

def sine(t: float, freq: float) -> float:
    return math.sin(2 * math.pi * freq * t)


def square(t: float, freq: float, duty: float = 0.5) -> float:
    phase = (freq * t) % 1.0
    return 1.0 if phase < duty else -1.0


def sawtooth(t: float, freq: float) -> float:
    return 2.0 * ((freq * t) % 1.0) - 1.0


def triangle(t: float, freq: float) -> float:
    phase = (freq * t) % 1.0
    return 4.0 * abs(phase - 0.5) - 1.0


def noise() -> float:
    return random.uniform(-1.0, 1.0)


# ---------------------------------------------------------------------------
# Envelope (ADSR) — returns amplitude multiplier at sample t
# ---------------------------------------------------------------------------

def adsr(t: float, duration: float,
         attack: float = 0.01, decay: float = 0.05,
         sustain_level: float = 0.7, release: float = 0.1) -> float:
    sustain_start = attack + decay
    sustain_end = duration - release
    if t < attack:
        return t / attack if attack > 0 else 1.0
    elif t < sustain_start:
        frac = (t - attack) / decay if decay > 0 else 1.0
        return 1.0 - frac * (1.0 - sustain_level)
    elif t < sustain_end:
        return sustain_level
    else:
        frac = (t - sustain_end) / release if release > 0 else 0.0
        return sustain_level * (1.0 - frac)


# ---------------------------------------------------------------------------
# SFX generators
# ---------------------------------------------------------------------------

def gen_tank_fire(sr: int) -> list[float]:
    """Sharp crack: noise burst + low thump."""
    dur = 0.35
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.002, decay=0.12, sustain_level=0.0, release=0.23)
        # Low thump
        thump = sine(t, 80) * 0.7
        # Noise crack
        crack = noise() * 0.5
        # Pitch-falling tone
        freq = 200 * math.exp(-t * 12)
        tone = sine(t, freq) * 0.4
        out.append(env * (thump + crack + tone) * 0.6)
    return out


def gen_bullet_hit_tank(sr: int) -> list[float]:
    """Metallic clang: high transient + ring."""
    dur = 0.25
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.001, decay=0.05, sustain_level=0.15, release=0.2)
        clang = sine(t, 900 * math.exp(-t * 8)) * 0.5
        ring = sine(t, 1400) * 0.3 * math.exp(-t * 18)
        hit_noise = noise() * 0.4 * math.exp(-t * 40)
        out.append(env * (clang + ring + hit_noise) * 0.8)
    return out


def gen_bullet_hit_obstacle(sr: int) -> list[float]:
    """Dull thud: lower, shorter than metal hit."""
    dur = 0.18
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.001, decay=0.05, sustain_level=0.0, release=0.13)
        thud = sine(t, 200 * math.exp(-t * 15)) * 0.6
        n_layer = noise() * 0.35 * math.exp(-t * 30)
        out.append(env * (thud + n_layer) * 0.75)
    return out


def gen_obstacle_destroy(sr: int) -> list[float]:
    """Crunch/rubble: noise sweep + low crack."""
    dur = 0.45
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.005, decay=0.15, sustain_level=0.1, release=0.3)
        crunch = noise() * 0.6 * (1 - t / dur)
        boom = sine(t, 60 * math.exp(-t * 5)) * 0.5
        crack = sine(t, 300 * math.exp(-t * 20)) * 0.3
        out.append(env * (crunch + boom + crack) * 0.7)
    return out


def gen_tank_explosion(sr: int) -> list[float]:
    """Big explosion: rumble + noise layers."""
    dur = 1.2
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.008, decay=0.25, sustain_level=0.15, release=0.7)
        rumble = sine(t, 40 + 20 * math.exp(-t * 3)) * 0.6
        mid = noise() * 0.5 * math.exp(-t * 4)
        high = noise() * 0.2 * math.exp(-t * 12)
        boom = sine(t, 80 * math.exp(-t * 6)) * 0.5
        out.append(env * (rumble + mid + high + boom) * 0.55)
    return out


def gen_tank_collision(sr: int) -> list[float]:
    """Heavy clunk: metallic low-mid impact."""
    dur = 0.3
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.002, decay=0.08, sustain_level=0.1, release=0.22)
        clunk = sine(t, 150 * math.exp(-t * 10)) * 0.6
        metal = sine(t, 500 * math.exp(-t * 15)) * 0.3
        n_layer = noise() * 0.3 * math.exp(-t * 25)
        out.append(env * (clunk + metal + n_layer) * 0.75)
    return out


def gen_ui_navigate(sr: int) -> list[float]:
    """Short blip up."""
    dur = 0.08
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.005, decay=0.02, sustain_level=0.6, release=0.05)
        tone = square(t, 660, duty=0.5) * 0.5
        tone2 = square(t, 880, duty=0.5) * 0.3
        out.append(env * (tone + tone2) * 0.55)
    return out


def gen_ui_confirm(sr: int) -> list[float]:
    """Two-tone confirm chime."""
    dur = 0.22
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.01, decay=0.06, sustain_level=0.5, release=0.15)
        freq = 880.0 if t < 0.1 else 1320.0
        tone = square(t, freq, duty=0.5) * 0.4
        harm = sine(t, freq * 1.5) * 0.25
        out.append(env * (tone + harm) * 0.6)
    return out


def gen_pickup_spawn(sr: int) -> list[float]:
    """Rising three-note arpeggio chime: C5→E5→G5."""
    dur = 0.3
    n = _seconds(dur)
    out = []
    note_dur = dur / 3.0
    freqs = [523.0, 659.0, 784.0]  # C5, E5, G5
    for i in range(n):
        t = i / sr
        note_idx = min(int(t / note_dur), 2)
        note_t = t - note_idx * note_dur
        env = adsr(note_t, note_dur, attack=0.005, decay=0.03, sustain_level=0.5, release=0.06)
        tone = sine(t, freqs[note_idx]) * 0.5
        harm = sine(t, freqs[note_idx] * 2) * 0.15
        out.append(env * (tone + harm) * 0.5)
    return out


def gen_pickup_collect(sr: int) -> list[float]:
    """Bright two-note ding: G5→C6."""
    dur = 0.2
    n = _seconds(dur)
    out = []
    freqs = [784.0, 1047.0]  # G5, C6
    for i in range(n):
        t = i / sr
        note_idx = 0 if t < 0.1 else 1
        note_t = t if note_idx == 0 else t - 0.1
        env = adsr(note_t, 0.1, attack=0.003, decay=0.02, sustain_level=0.4, release=0.07)
        tone = sine(t, freqs[note_idx]) * 0.6
        harm = sine(t, freqs[note_idx] * 1.5) * 0.2
        out.append(env * (tone + harm) * 0.7)
    return out


def gen_pickup_expire(sr: int) -> list[float]:
    """Soft descending tone: E5→C5."""
    dur = 0.4
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.02, decay=0.1, sustain_level=0.2, release=0.28)
        freq = 659.0 - (659.0 - 523.0) * (t / dur)  # E5 glide to C5
        tone = sine(t, freq) * 0.4
        out.append(env * tone * 0.3)
    return out


def gen_pickup_health(sr: int) -> list[float]:
    """Warm ascending chime: C5→E5→G5 with soft harmonics."""
    dur = 0.25
    n = _seconds(dur)
    out = []
    freqs = [523.0, 659.0, 784.0]
    note_dur = dur / 3.0
    for i in range(n):
        t = i / sr
        idx = min(int(t / note_dur), 2)
        nt = t - idx * note_dur
        env = adsr(nt, note_dur, attack=0.005, decay=0.03, sustain_level=0.5, release=0.05)
        tone = sine(t, freqs[idx]) * 0.5 + sine(t, freqs[idx] * 2) * 0.1
        out.append(env * tone * 0.6)
    return out


def gen_pickup_speed(sr: int) -> list[float]:
    """Quick rising sweep — whoosh feel."""
    dur = 0.2
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.005, decay=0.05, sustain_level=0.4, release=0.14)
        freq = 400 + 1200 * (t / dur)
        tone = sawtooth(t, freq) * 0.3 + noise() * 0.15 * math.exp(-t * 20)
        out.append(env * tone * 0.5)
    return out


def gen_pickup_reload(sr: int) -> list[float]:
    """Mechanical click-clack: two sharp transients."""
    dur = 0.18
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        click1 = sine(t, 1200) * math.exp(-t * 60) * 0.5 if t < 0.08 else 0.0
        click2 = sine(t - 0.09, 900) * math.exp(-(t - 0.09) * 50) * 0.4 if t >= 0.09 else 0.0
        env = adsr(t, dur, attack=0.001, decay=0.03, sustain_level=0.1, release=0.14)
        out.append(env * (click1 + click2) * 0.7)
    return out


def gen_pickup_shield(sr: int) -> list[float]:
    """Crystalline shimmer: high sine with chorus detune."""
    dur = 0.35
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.02, decay=0.08, sustain_level=0.4, release=0.25)
        tone = sine(t, 1047.0) * 0.35
        chorus = sine(t, 1055.0) * 0.2 + sine(t, 1570.0) * 0.15
        shimmer = sine(t, 2093.0) * 0.1 * math.exp(-t * 8)
        out.append(env * (tone + chorus + shimmer) * 0.55)
    return out


def gen_shield_pop(sr: int) -> list[float]:
    """Bubble pop: quick noise burst + falling tone."""
    dur = 0.25
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.001, decay=0.04, sustain_level=0.1, release=0.2)
        pop = noise() * 0.5 * math.exp(-t * 40)
        fall = sine(t, 800 * math.exp(-t * 12)) * 0.4
        out.append(env * (pop + fall) * 0.6)
    return out


def gen_explosion(sr: int) -> list[float]:
    """Heavy AoE explosion: bass thump + pressure wave + crackle + sub-rumble."""
    dur = 0.6
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        # Bass thump — 35 Hz sine
        thump = sine(t, 35) * 0.8 * math.exp(-t * 8)
        # Pressure wave — noise burst
        pressure = noise() * 0.6 * math.exp(-t * 5)
        # Crackle — high-freq noise
        crackle = noise() * 0.3 * math.exp(-t * 20)
        # Sub-rumble — 20 Hz sine
        rumble = sine(t, 20) * 0.4 * math.exp(-t * 3)
        out.append(thump + pressure + crackle + rumble)
    # Normalize to 0.85 peak
    peak = max(abs(s) for s in out) or 1.0
    out = [s / peak * 0.85 for s in out]
    return out


# ---------------------------------------------------------------------------
# Music generators — Outrun/Synthwave style
# ---------------------------------------------------------------------------

def _note_freq(semitones_from_a4: int) -> float:
    """Return Hz for note offset in semitones from A4 (440 Hz)."""
    return 440.0 * (2 ** (semitones_from_a4 / 12.0))


# Scale: A minor pentatonic offsets from A4
_PENTA_AM = [0, 3, 5, 7, 10, 12, 15, 17]  # A C D E G A' C' D'


def _arpeggio(sr: int, bpm: float, bars: int,
              bass_pattern: list[float],
              arp_pattern: list[float],
              pad_chords: list[list[float]],
              beat_dur: float) -> list[float]:
    """
    Build a looped synthwave pattern.
    bass_pattern:  list of (semitone, beats_held) for bass line
    arp_pattern:   list of (semitone, subdivision) cycling over one bar
    pad_chords:    list of chord (list of semitones) cycling over bars
    """
    spb = (60.0 / bpm)  # seconds per beat
    bar_secs = spb * 4
    total_secs = bar_secs * bars
    n = int(sr * total_secs)
    out = [0.0] * n

    # --- Kick drum (every beat)
    kick_env_len = int(sr * 0.25)
    for beat in range(bars * 4):
        start = int(beat * spb * sr)
        for k in range(min(kick_env_len, n - start)):
            t = k / sr
            kick = sine(t, 55 * math.exp(-t * 20)) * math.exp(-t * 18) * 0.7
            if start + k < n:
                out[start + k] += kick

    # --- Snare / clap (beats 2 & 4)
    snare_env_len = int(sr * 0.12)
    for beat in range(bars * 4):
        if beat % 4 in (1, 3):
            start = int(beat * spb * sr)
            for k in range(min(snare_env_len, n - start)):
                t = k / sr
                snare = noise() * math.exp(-t * 30) * 0.45
                if start + k < n:
                    out[start + k] += snare

    # --- Bass line (square wave, cycle through bass_pattern)
    cur_time = 0.0
    p_idx = 0
    while cur_time < total_secs:
        semi, beats = bass_pattern[p_idx % len(bass_pattern)]
        dur = beats * spb
        freq = _note_freq(semi - 24)  # two octaves below A4
        p_len = int(dur * sr)
        start = int(cur_time * sr)
        for k in range(p_len):
            if start + k >= n:
                break
            t = k / sr
            env = max(0.0, 1.0 - t / dur * 1.1)
            out[start + k] += square(t, freq, duty=0.5) * env * 0.35
        cur_time += dur
        p_idx += 1

    # --- Arpeggiated lead (square/saw)
    sub_dur = spb / 2  # 8th-note arpeggios
    arp_steps = bars * 8  # 8th notes per bar
    for step in range(arp_steps):
        semi = arp_pattern[step % len(arp_pattern)]
        freq = _note_freq(semi)
        start = int(step * sub_dur * sr)
        slen = int(sub_dur * sr)
        for k in range(slen):
            if start + k >= n:
                break
            t = k / sr
            env = adsr(t, sub_dur, attack=0.01, decay=0.05,
                       sustain_level=0.6, release=0.03)
            out[start + k] += (sawtooth(t, freq) * 0.5 +
                               sawtooth(t, freq * 1.005) * 0.15) * env * 0.25

    # --- Pad chords (whole-bar held pads)
    for bar in range(bars):
        chord = pad_chords[bar % len(pad_chords)]
        bar_start = int(bar * bar_secs * sr)
        bar_end = int((bar + 1) * bar_secs * sr)
        for k in range(bar_start, min(bar_end, n)):
            t = (k - bar_start) / sr
            env = adsr(t, bar_secs, attack=0.15, decay=0.1,
                       sustain_level=0.7, release=0.3)
            for semi in chord:
                freq = _note_freq(semi - 12)
                out[k] += sine(k / sr, freq) * env * 0.12

    # Normalise
    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.88 for s in out]


def gen_music_menu(sr: int) -> list[float]:
    """
    Slow atmospheric synthwave intro.
    Tempo: 80 BPM, 8 bars, A minor mood.
    """
    bpm = 80.0
    bars = 8
    bass = [(-12, 2), (-10, 2), (-8, 2), (-7, 2)]  # Am - C - D - E
    arp = [0, 3, 7, 10, 7, 3, 0, -5]  # Am arpeggio descending
    pads = [
        [0, 3, 7],    # Am
        [-3, 0, 3],   # F (relative major)
        [-5, -2, 0],  # G
        [-12, -9, -5],
    ]
    return _arpeggio(sr, bpm, bars, bass, arp, pads, beat_dur=60 / bpm)


def gen_music_gameplay(sr: int) -> list[float]:
    """
    Driving synthwave — 120 BPM, 8 bars, energetic A minor.
    """
    bpm = 120.0
    bars = 8
    bass = [(-12, 1), (-12, 1), (-10, 1), (-8, 1)]
    arp = [0, 7, 12, 7, 3, 10, 12, 10,
           0, 5, 7, 10, 7, 5, 3, 0]
    pads = [
        [0, 7, 3],
        [-5, 0, 3],
        [-7, -3, 0],
        [-8, -5, 0],
    ]
    return _arpeggio(sr, bpm, bars, bass, arp, pads, beat_dur=60 / bpm)


# ---------------------------------------------------------------------------
# Per-pickup music layers (short seamless loops, ~4 seconds each)
# ---------------------------------------------------------------------------

def gen_layer_speed(sr: int) -> list[float]:
    """Tempo-doubled buzzy arpeggio — energetic overlay for speed boost."""
    duration = 4.0
    n = int(sr * duration)
    out = [0.0] * n

    # Fast 16th-note arpeggio using pentatonic scale
    bpm = 240.0  # double-time
    note_dur = 60.0 / bpm
    arp_notes = [0, 3, 5, 7, 10, 12, 10, 7, 5, 3]  # Am pentatonic cycle
    step = 0
    t_note = 0.0
    while t_note < duration:
        semi = arp_notes[step % len(arp_notes)]
        freq = _note_freq(semi)
        start = int(t_note * sr)
        slen = int(note_dur * sr)
        for k in range(slen):
            if start + k >= n:
                break
            t = k / sr
            env = adsr(t, note_dur, attack=0.005, decay=0.03,
                       sustain_level=0.5, release=0.02)
            out[start + k] += sawtooth(t, freq) * env * 0.3
        t_note += note_dur
        step += 1

    # Subtle hi-hat noise bursts on every other 16th
    hat_interval = note_dur
    t_hat = hat_interval
    while t_hat < duration:
        start = int(t_hat * sr)
        hat_len = int(0.015 * sr)
        for k in range(hat_len):
            if start + k >= n:
                break
            t = k / sr
            out[start + k] += noise() * math.exp(-t * 200) * 0.12
        t_hat += hat_interval * 2

    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.35 for s in out]


def gen_layer_heartbeat(sr: int) -> list[float]:
    """Heavy heartbeat — lub-DUB pattern at 72 BPM.

    Uses 80-120Hz fundamentals with square wave harmonics for speaker
    audibility. Each beat has a percussive click transient that cuts
    through the mix even on laptop speakers.
    """
    bpm = 72.0
    beat_dur = 60.0 / bpm  # ~0.833s per beat
    cycles = 5
    total = beat_dur * cycles
    n = int(sr * total)
    out = [0.0] * n

    for cycle in range(cycles):
        cycle_start = int(cycle * beat_dur * sr)

        # LUB — heavy thump at t=0 within cycle
        lub_dur = 0.18
        lub_samples = int(lub_dur * sr)
        for k in range(min(lub_samples, n - cycle_start)):
            t = k / sr
            # Fast exponential envelope — punchy attack
            env = math.exp(-t * 12.0)
            # 80Hz fundamental (square wave for odd harmonics)
            fund = square(t, 80, duty=0.5) * 0.5
            # 160Hz second harmonic (laptop speakers reproduce this)
            harm2 = sine(t, 160) * 0.4
            # 240Hz third harmonic — adds "thock" character
            harm3 = sine(t, 240) * 0.2
            # Click transient — sharp noise burst for attack
            click = noise() * 0.6 * math.exp(-t * 80.0)
            out[cycle_start + k] += env * (fund + harm2 + harm3 + click)

        # DUB — slightly higher, slightly softer, 0.25s after lub starts
        dub_offset = int(0.25 * sr)
        dub_dur = 0.12
        dub_samples = int(dub_dur * sr)
        dub_start = cycle_start + dub_offset
        for k in range(min(dub_samples, max(0, n - dub_start))):
            if dub_start + k >= n:
                break
            t = k / sr
            env = math.exp(-t * 16.0)
            fund = square(t, 100, duty=0.5) * 0.35
            harm2 = sine(t, 200) * 0.3
            harm3 = sine(t, 300) * 0.15
            click = noise() * 0.4 * math.exp(-t * 100.0)
            out[dub_start + k] += env * (fund + harm2 + harm3 + click)

    # Normalize to 0.9 peak — playback volume handles final mix
    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.9 for s in out]


def gen_layer_underwater(sr: int) -> list[float]:
    """Dreamy underwater warble — atmospheric overlay for shield."""
    duration = 4.0
    n = int(sr * duration)
    out = [0.0] * n

    base_freq_root = 220.0
    base_freq_fifth = 330.0

    for i in range(n):
        t = i / sr
        # Slow pitch wobble ±3%
        wobble = 1.0 + 0.03 * math.sin(2 * math.pi * 0.8 * t)
        # Slow amplitude pulsing
        amp_mod = 0.5 + 0.5 * math.sin(2 * math.pi * 1.5 * t)
        # Chord: root + fifth
        sample = (sine(t, base_freq_root * wobble) +
                  sine(t, base_freq_fifth * wobble) * 0.7)
        sample *= amp_mod * 0.35
        # Subtle noise floor
        sample += noise() * 0.05
        out[i] = sample

    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.25 for s in out]


def gen_layer_rapid_reload(sr: int) -> list[float]:
    """Mechanical tick loop — metronomic overlay for rapid reload."""
    duration = 4.0
    n = int(sr * duration)
    out = [0.0] * n

    tick_rate = 8.0  # 8 ticks per second
    tick_interval = 1.0 / tick_rate
    tick_count = int(duration * tick_rate)

    for i in range(tick_count):
        t_start = i * tick_interval
        start = int(t_start * sr)
        tick_dur = 0.01
        tick_len = int(tick_dur * sr)
        # Every 4th tick is accented
        amp = 0.5 if (i % 4 == 0) else 0.3
        for k in range(tick_len):
            if start + k >= n:
                break
            t = k / sr
            env = math.exp(-t * 300)
            out[start + k] += square(t, 1200) * env * amp

    # Low constant drone
    for i in range(n):
        t = i / sr
        out[i] += sine(t, 80) * 0.15

    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.3 for s in out]


def gen_layer_burning(sr: int) -> list[float]:
    """Crackling fire loop — warm noise bursts + low rumble for burn effect."""
    duration = 4.0
    n = int(sr * duration)
    out = [0.0] * n

    # Crackling: random short noise bursts
    crackle_rate = 12.0  # bursts per second
    crackle_interval = 1.0 / crackle_rate
    t_crackle = 0.0
    rng = random.Random(42)
    while t_crackle < duration:
        start = int(t_crackle * sr)
        burst_dur = 0.02 + rng.random() * 0.02
        burst_len = int(burst_dur * sr)
        amp = 0.2 + rng.random() * 0.3
        for k in range(min(burst_len, n - start)):
            t = k / sr
            out[start + k] += noise() * amp * math.exp(-t * 60)
        t_crackle += crackle_interval + rng.random() * 0.04

    # Low warm rumble
    for i in range(n):
        t = i / sr
        out[i] += sine(t, 60) * 0.15
        out[i] += sine(t, 120) * 0.08

    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.3 for s in out]


def gen_layer_frozen(sr: int) -> list[float]:
    """Crystalline wind loop — high shimmering tones + breathy noise for ice effect."""
    duration = 4.0
    n = int(sr * duration)
    out = [0.0] * n

    for i in range(n):
        t = i / sr
        # High shimmering tone with slow wobble
        wobble = 1.0 + 0.02 * math.sin(2 * math.pi * 0.6 * t)
        shimmer = sine(t, 1200 * wobble) * 0.15
        shimmer += sine(t, 1800 * wobble) * 0.08
        # Breathy wind noise
        wind = noise() * 0.08 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.4 * t))
        out[i] = shimmer + wind

    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.25 for s in out]


def gen_sfx_effect_fire(sr: int) -> list[float]:
    """Whoosh ignition — rising noise sweep for fire application."""
    dur = 0.3
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.01, decay=0.08, sustain_level=0.3, release=0.2)
        freq = 200 + 800 * (t / dur)
        tone = sawtooth(t, freq) * 0.3 + noise() * 0.4 * math.exp(-t * 8)
        out.append(env * tone * 0.6)
    return out


def gen_sfx_effect_poison(sr: int) -> list[float]:
    """Bubbling hiss — gurgling noise for poison application."""
    dur = 0.35
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.02, decay=0.1, sustain_level=0.25, release=0.2)
        bubble = sine(t, 300 + 200 * math.sin(t * 30)) * 0.3
        hiss = noise() * 0.3 * math.exp(-t * 6)
        out.append(env * (bubble + hiss) * 0.5)
    return out


def gen_sfx_effect_ice(sr: int) -> list[float]:
    """Crystal crack — sharp high transient + ringing for ice application."""
    dur = 0.25
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.002, decay=0.04, sustain_level=0.15, release=0.2)
        crack = noise() * 0.5 * math.exp(-t * 40)
        ring = sine(t, 2000) * 0.3 * math.exp(-t * 12)
        ring2 = sine(t, 3000) * 0.15 * math.exp(-t * 15)
        out.append(env * (crack + ring + ring2) * 0.7)
    return out


def gen_sfx_effect_electric(sr: int) -> list[float]:
    """Electric zap — buzzy square wave burst for electric application."""
    dur = 0.2
    n = _seconds(dur)
    out = []
    for i in range(n):
        t = i / sr
        env = adsr(t, dur, attack=0.003, decay=0.05, sustain_level=0.2, release=0.14)
        zap = square(t, 800 + 400 * math.sin(t * 50), duty=0.3) * 0.4
        buzz = noise() * 0.3 * math.exp(-t * 20)
        out.append(env * (zap + buzz) * 0.6)
    return out


def gen_music_game_over(sr: int) -> list[float]:
    """
    Short melancholic sting — 70 BPM, 4 bars, descending minor motif.
    """
    bpm = 70.0
    bars = 4
    bass = [(-12, 2), (-15, 2), (-17, 2), (-19, 2)]  # descending
    arp = [-12, -9, -7, -5, -7, -9, -12, -14]
    pads = [
        [0, 3, 7],
        [-2, 0, 3],
        [-5, -3, 0],
        [-7, -5, -2],
    ]
    return _arpeggio(sr, bpm, bars, bass, arp, pads, beat_dur=60 / bpm)


def gen_sfx_steam_burst(sr: int) -> list[float]:
    """White noise whoosh + sine sweep 100→800Hz, 0.4s."""
    dur = 0.4
    n = int(sr * dur)
    out = [0.0] * n
    for i in range(n):
        t = i / sr
        progress = t / dur
        # White noise whoosh with envelope
        env = math.sin(math.pi * progress)  # rise-fall envelope
        noise = (random.random() * 2 - 1) * 0.5 * env
        # Sine sweep 100→800Hz
        freq = 100 + 700 * progress
        sweep = math.sin(2 * math.pi * freq * t) * 0.4 * env
        out[i] = max(-1.0, min(1.0, noise + sweep))
    return out


def gen_sfx_accelerated_burn(sr: int) -> list[float]:
    """Crack + deep boom + sizzle, 0.35s."""
    dur = 0.35
    n = int(sr * dur)
    out = [0.0] * n
    for i in range(n):
        t = i / sr
        progress = t / dur
        val = 0.0
        # Initial crack — short burst of noise
        if t < 0.03:
            val += (random.random() * 2 - 1) * 0.8 * (1.0 - t / 0.03)
        # Deep boom — low sine with decay
        boom_env = math.exp(-t * 12)
        val += math.sin(2 * math.pi * 60 * t) * 0.6 * boom_env
        # Sizzle — filtered noise in tail
        if t > 0.05:
            sizzle_env = math.exp(-(t - 0.05) * 8)
            val += (random.random() * 2 - 1) * 0.3 * sizzle_env
        out[i] = max(-1.0, min(1.0, val))
    return out


def gen_sfx_deep_freeze(sr: int) -> list[float]:
    """Click transient + crystalline ring + ice crack, 0.5s."""
    dur = 0.5
    n = int(sr * dur)
    out = [0.0] * n
    for i in range(n):
        t = i / sr
        val = 0.0
        # Click transient
        if t < 0.01:
            val += (random.random() * 2 - 1) * 0.7 * (1.0 - t / 0.01)
        # Crystalline ring — high sine with slow decay
        ring_env = math.exp(-t * 4)
        val += math.sin(2 * math.pi * 2400 * t) * 0.35 * ring_env
        val += math.sin(2 * math.pi * 3600 * t) * 0.2 * ring_env
        # Ice crack — mid-frequency burst at ~0.15s
        if 0.12 < t < 0.2:
            crack_env = math.sin(math.pi * (t - 0.12) / 0.08)
            val += (random.random() * 2 - 1) * 0.5 * crack_env
        out[i] = max(-1.0, min(1.0, val))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("TankBattle audio generator — pure stdlib (wave + struct + math)")
    print(f"  Sample rate: {SAMPLE_RATE} Hz  |  16-bit mono\n")

    sfx_jobs = [
        ("sfx_tank_fire.wav",           gen_tank_fire),
        ("sfx_bullet_hit_tank.wav",     gen_bullet_hit_tank),
        ("sfx_bullet_hit_obstacle.wav", gen_bullet_hit_obstacle),
        ("sfx_obstacle_destroy.wav",    gen_obstacle_destroy),
        ("sfx_tank_explosion.wav",      gen_tank_explosion),
        ("sfx_tank_collision.wav",      gen_tank_collision),
        ("sfx_ui_navigate.wav",         gen_ui_navigate),
        ("sfx_ui_confirm.wav",          gen_ui_confirm),
        ("sfx_pickup_spawn.wav",        gen_pickup_spawn),
        ("sfx_pickup_collect.wav",      gen_pickup_collect),
        ("sfx_pickup_expire.wav",       gen_pickup_expire),
        ("sfx_pickup_health.wav",       gen_pickup_health),
        ("sfx_pickup_speed.wav",        gen_pickup_speed),
        ("sfx_pickup_reload.wav",       gen_pickup_reload),
        ("sfx_pickup_shield.wav",       gen_pickup_shield),
        ("sfx_shield_pop.wav",          gen_shield_pop),
        ("sfx_explosion.wav",           gen_explosion),
        ("sfx_effect_fire.wav",         gen_sfx_effect_fire),
        ("sfx_effect_poison.wav",       gen_sfx_effect_poison),
        ("sfx_effect_ice.wav",          gen_sfx_effect_ice),
        ("sfx_effect_electric.wav",     gen_sfx_effect_electric),
        ("sfx_steam_burst.wav",         gen_sfx_steam_burst),
        ("sfx_accelerated_burn.wav",    gen_sfx_accelerated_burn),
        ("sfx_deep_freeze.wav",         gen_sfx_deep_freeze),
    ]

    print("--- SFX ---")
    for filename, gen_fn in sfx_jobs:
        path = os.path.join(OUTPUT_DIR_SFX, filename)
        samples = gen_fn(SAMPLE_RATE)
        _write_wav(path, samples)

    music_jobs = [
        ("music_menu.wav",              gen_music_menu),
        ("music_gameplay.wav",          gen_music_gameplay),
        ("music_game_over.wav",         gen_music_game_over),
        ("layer_speed.wav",             gen_layer_speed),
        ("layer_heartbeat.wav",         gen_layer_heartbeat),
        ("layer_underwater.wav",        gen_layer_underwater),
        ("layer_rapid_reload.wav",      gen_layer_rapid_reload),
        ("layer_burning.wav",           gen_layer_burning),
        ("layer_frozen.wav",            gen_layer_frozen),
    ]

    print("\n--- Music ---")
    for filename, gen_fn in music_jobs:
        path = os.path.join(OUTPUT_DIR_MUSIC, filename)
        samples = gen_fn(SAMPLE_RATE)
        _write_wav(path, samples)

    print("\nDone. All assets written.")


if __name__ == "__main__":
    main()
