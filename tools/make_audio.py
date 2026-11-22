#!/usr/bin/env python3
"""
Renders every audio asset of the Super Scary Trollge mod.

Per song (songs/<id>/song/Inst.ogg):
    the instrumental, rebuilt as a professional dark electronic piece -- each
    song its own sub-genre (dark bounce / dark trap / dark glitch / industrial
    / dark ambient) with multi-layer supersaw leads, Reese bass, 808 slides,
    cinematic drums and horror layers that scale with the scare tier.

Shared (sounds/):
    trollge_theme.ogg / trollge_theme_scary.ogg   cutscene + menu music
    trollge_jump_scare.ogg   jumpscare stinger
    trollge_distortion.ogg   glitch stinger
    trollge_invert.ogg       inverted-world riser
    trollge_hit.ogg / trollge_miss.ogg            custom note feedback

Run with:  python3 tools/make_audio.py
"""

import math
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L  # noqa: E402
from lib_dsp import (  # noqa: E402
    SR, add_at, adsr, bandpass, bitcrush,
    dc_block, delay, empty, eq_curve, exp_decay, fade, formant_bank, haas,
    highpass, limiter, compress, lowpass, midi_to_hz, noise, normalize, pan,
    reverb, saw, sidechain, sine, smooth_lowpass, soft_clip, square, true_peak,
    widen, write_ogg,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
SFX_DIR = os.path.join(MOD, "sounds")
MUSIC_DIR = os.path.join(MOD, "music")

TARGET_RMS = 10.0 ** (-14.0 / 20.0)

SONG_STYLES = {
    "trolling": "dark_bounce",
    "getting-dark": "dark_trap",
    "dont-look-back": "dark_glitch",
    "super-scary": "industrial",
    "the-incident": "dark_ambient",
}

ROLE_GAIN = {
    "intro": 0.10,
    "verse": 0.70,
    "build": 0.86,
    "drop": 1.04,
    "break": 0.18,
    "finale": 1.12,
}


def tier_for(scare):
    if scare <= 2:
        return 1
    if scare <= 4:
        return 2
    if scare <= 6:
        return 3
    if scare <= 8:
        return 4
    return 5


# --------------------------------------------------------------------------- #
# Dark electronic instrument library — professional sound design
# --------------------------------------------------------------------------- #

def _env(n, attack, decay, sustain, release):
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    s = max(0, n - a - d - r)
    return np.concatenate([
        np.linspace(0.0, 1.0, a, endpoint=False),
        np.linspace(1.0, sustain, d, endpoint=False),
        np.full(s, sustain),
        np.linspace(sustain, 0.0, r),
    ])[:n]


def _rng(seed):
    return np.random.default_rng(seed)


# ---- Supersaw: 9-voice detuned ensemble for rich, wide leads and pads ----

def supersaw(f, n, detune=0.018, spread=9, amp=0.12):
    """Nine saw oscillators detuned around `f` for a thick, lush supersaw."""
    out = np.zeros(n)
    for i in range(spread):
        ratio = 1.0 + (i - spread // 2) * detune
        phase = 0.3 * i  # slight phase offset per voice
        out += saw(f * ratio, n, phase0=phase) * amp
    return out / spread


# ---- Reese bass: detuned saws + LFO filter + drive + sub ----

def reese_bass(f, n, tier, slide_to=None):
    t = np.arange(n) / SR
    detune = 0.030 + 0.012 * tier  # wider detune = more movement
    if slide_to is not None:
        f_curve = f + (slide_to - f) * (1.0 - np.exp(-t * 9.0))
    else:
        f_curve = np.full(n, f)

    # Two saws detuned against each other = classic reese movement
    voice = (
        saw(f_curve * (1.0 - detune), n) * 0.55
        + saw(f_curve * (1.0 + detune), n) * 0.55
    )
    # Sub layer for weight
    sub = sine(f_curve, n) * 0.35
    voice = voice + sub

    # Resonant lowpass with LFO movement
    cutoff = 350.0 + 650.0 * tier
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * (0.7 + 0.15 * tier) * t)
    moving_cut = cutoff * (0.55 + 0.45 * lfo)
    # Apply per-sample by splitting into chunks
    chunk = 512
    filtered = np.zeros(n)
    for start in range(0, n, chunk):
        end = min(start + chunk, n)
        c = moving_cut[start]
        filtered[start:end] = lowpass(voice[start:end], c, order=2)

    env = _env(n, 0.006, 0.10, 0.80, min(0.40, n / SR * 0.5))
    out = filtered * env
    out = highpass(out, 30.0)
    drive = 1.8 + 0.7 * tier
    return soft_clip(out * drive, 1.2 + 0.5 * tier)


def slide_808(f0, f1, n, tier):
    """808 with pitch slide from f0 down to f1 — classic trap bass."""
    t = np.arange(n) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 8.0)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    body += np.sin(2 * np.pi * np.cumsum(freq * 2.0) / SR) * 0.12
    body += np.sin(2 * np.pi * np.cumsum(freq * 0.5) / SR) * 0.06
    env = _env(n, 0.005, 0.22, 0.85, min(0.50, n / SR * 0.5))
    out = body * env
    out = lowpass(out, 280.0 + 220.0 * tier)
    drive = 2.0 + 0.7 * tier
    return soft_clip(out, drive)


def sub_hit(f, n):
    """Clean sub-bass hit with pitch envelope."""
    t = np.arange(n) / SR
    freq = f * np.exp(-t * 6.0)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 8.0)


# ---- Dark saw lead: supersaw with filter envelope + distortion ----

def dark_saw_lead(f, n, tier, detune=0.016):
    """Supersaw lead with resonant lowpass filter envelope and drive."""
    t = np.arange(n) / SR
    # Supersaw: 9 voices for width
    voice = supersaw(f, n, detune=detune, spread=9, amp=0.11)
    # Add a square sub for body
    voice += square(f, n, duty=0.5) * 0.12
    # Add an octave up for presence
    voice += saw(f * 2.0, n) * 0.07

    # Resonant lowpass with filter envelope (opens on attack)
    cutoff = 1400.0 + 750.0 * tier
    lfo_env = np.clip(1.0 - np.exp(-t * 28.0), 0.0, 1.0)
    moving_cut = cutoff * (0.35 + 0.65 * lfo_env)
    chunk = 512
    filtered = np.zeros(n)
    for start in range(0, n, chunk):
        end = min(start + chunk, n)
        c = moving_cut[start]
        filtered[start:end] = lowpass(voice[start:end], c, order=2)

    env = _env(n, 0.003, 0.07, 0.65, 0.09)
    out = filtered * env
    drive = 2.0 + 0.8 * tier
    return soft_clip(out, drive)


def fm_bell(f, n):
    """FM bell sound — metallic, haunting."""
    t = np.arange(n) / SR
    body = np.zeros(n)
    for mult, amp, decay in ((1.0, 1.0, 1.8), (2.01, 0.38, 3.2), (3.03, 0.18, 5.5), (4.11, 0.09, 8.0)):
        body += np.sin(2 * np.pi * f * mult * t) * amp * np.exp(-t * decay)
    return body * 0.60


def dark_pad_voice(f, n, tier):
    """Wide, lush supersaw pad with slow attack and filter movement."""
    t = np.arange(n) / SR
    # Supersaw pad: wide, lush
    voice = supersaw(f, n, detune=0.012, spread=7, amp=0.14)
    voice += saw(f * 2.0, n) * 0.09

    breathe = 1.0 + 0.35 * np.sin(2 * np.pi * 0.06 * t) + 0.18 * np.sin(2 * np.pi * 0.27 * t)
    cutoff = 700.0 + 900.0 * tier
    dark = lowpass(voice, cutoff * 0.40)
    bright = lowpass(voice, cutoff * 1.5)
    weight = np.clip(0.35 + 0.65 * np.sin(2 * np.pi * 0.06 * t), 0.0, 1.0)
    out = dark * (1.0 - weight) + bright * weight
    env = _env(n, n / SR * 0.55, n / SR * 0.10, 0.78, n / SR * 0.45)
    return out * env * breathe * 0.065


# ---- Layered drums ----

def dark_kick(dur, style, tier):
    """Kick: sub sine pitch envelope + click + noise body + saturation."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    start_hz, end_hz = (85.0, 52.0) if style != "trap" else (65.0, 42.0)
    freq = end_hz + (start_hz - end_hz) * np.exp(-t * 28.0)
    sub = np.sin(2 * np.pi * np.cumsum(freq) / SR)

    # Click at attack
    attack = int(0.0025 * SR)
    click = bandpass(noise(n, seed=23), 3500.0, 8000.0) * np.exp(-t * 110.0) * 0.18

    # Body resonance
    body = np.sin(2 * np.pi * np.cumsum(freq * 1.6) / SR) * np.exp(-t * 11.0) * 0.18

    env = np.exp(-t * 8.0)
    env[:attack] *= np.linspace(0.0, 1.0, attack) ** 2

    kick = sub * env + click + body * env
    if style == "industrial":
        metal = bandpass(noise(n, seed=22), 400.0, 2800.0) * np.exp(-t * 42.0) * 0.34
        kick = kick + metal
    elif style == "trap":
        kick = kick * np.exp(-t * 1.2)

    drive = 1.6 + 0.3 * tier
    return soft_clip(kick * drive, 1.35 + 0.2 * tier)


def dark_snare(dur, style, tier, seed=12):
    """Snare: tone + noise rattle + reverb tail."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    tune = 200.0 if style == "trap" else (230.0 if style == "industrial" else 210.0)
    tone = (np.sin(2 * np.pi * tune * t) * 0.50
            + np.sin(2 * np.pi * tune * 1.8 * t) * 0.28) * np.exp(-t * 30.0)

    if style == "industrial":
        rattle = bandpass(noise(n, seed=seed), 1300.0, 8000.0) * np.exp(-t * 11.0) * 0.75
    elif style == "glitch":
        gate = (np.sin(2 * np.pi * 42.0 * t) > -0.1).astype(float)
        rattle = bandpass(noise(n, seed=seed), 1600.0, 8000.0) * np.exp(-t * 32.0) * gate * 0.65
    else:
        rattle = bandpass(noise(n, seed=seed), 1100.0, 7500.0) * np.exp(-t * 13.0) * 0.72

    onset = int(0.0018 * SR)
    rattle[:onset] *= np.linspace(0.0, 1.0, onset)
    return tone * 0.62 + rattle * 0.74


def dark_hat(dur, open_, style, seed=13):
    """Hi-hat: bandpassed noise with EQ curve and velocity variation."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    decay = 7.0 if open_ else 48.0
    env = np.exp(-t * decay)
    tune = 1.0 if style == "trap" else (0.82 if style == "industrial" else 1.0)
    body = bandpass(noise(n, seed=seed), 7000.0 * tune, 16000.0 * tune)
    body = eq_curve(body, [(4000.0, -5.0), (9000.0, 1.5), (13000.0, 2.5), (17000.0, -1.5)])
    onset = int(0.0008 * SR)
    body[:onset] *= np.linspace(0.0, 1.0, onset)
    return body * env * 0.40


def metal_hit(dur, seed=40):
    """Industrial metal hit — clanging, hostile."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    partials = [(290.0, 0.60), (470.0, 0.45), (820.0, 0.35), (1300.0, 0.22), (1900.0, 0.12)]
    out = sum(np.sin(2 * np.pi * h * t) * a * np.exp(-t * (2.2 + i * 0.4))
              for i, (h, a) in enumerate(partials))
    noise_bit = bandpass(noise(n, seed=seed), 3000.0, 11000.0) * np.exp(-t * 20.0) * 0.45
    return soft_clip((out + noise_bit) * 1.6, 1.5)


# ---- Horror layers ----

def dread_drone(root_hz, n, tier):
    """Low, unsettling drone with tritone dissonance at high tiers."""
    t = np.arange(n) / SR
    beat_hz = 0.45 + 0.12 * tier
    drone = (sine(root_hz, n) * 0.52 + sine(root_hz * 1.005, n) * 0.48)
    drone_l = drone * (0.68 + 0.32 * np.sin(2 * np.pi * beat_hz * t))
    drone_r = drone * (0.68 + 0.32 * np.sin(2 * np.pi * beat_hz * t + 2.3))

    if tier >= 4:
        tritone = root_hz * (2 ** (6 / 12.0))
        drone_l = drone_l + sine(tritone, n) * 0.28
        drone_r = drone_r + sine(tritone * 1.004, n) * 0.28

    gain = 0.09 * max(0.0, (tier - 1) / 4.0)
    return (lowpass(drone_l, 100.0) * gain, lowpass(drone_r, 100.0) * gain)


def breath_layer(n, tier):
    """Human breath — unsettling, organic."""
    breath = bandpass(noise(n, seed=9 + tier), 550.0, 3200.0)
    t = np.arange(n) / SR
    swing = 0.5 + 0.5 * np.sin(2 * np.pi * (0.07 + 0.02 * tier) * t - 0.4)
    swing = swing ** 5
    return breath * swing * (0.07 * max(0.0, (tier - 1) / 4.0))


def heartbeat(bpm, total, tier):
    """Thumping heartbeat — gets louder as scare tier rises."""
    beat_s = 60.0 / bpm
    hb_n = int(0.18 * SR)
    hbt = np.arange(hb_n) / SR
    thump = np.sin(2 * np.pi * np.cumsum(52.0 + 48.0 * np.exp(-hbt * 27.0)) / SR)
    thump *= np.exp(-hbt * 13.0)
    buf = empty(total)
    bar = 4 * beat_s
    t = 0.0
    gain = 0.14 * max(0.0, (tier - 3) / 2.0)
    while t < total - 0.5:
        add_at(buf, thump, t, gain)
        add_at(buf, thump * 0.72, t + 0.34, gain * 0.62)
        t += bar
    return buf


def whispers(n, tier):
    """Whispering voices — high-passed noise with amplitude modulation."""
    w = highpass(noise(n, seed=72 + tier), 2200.0)
    t = np.arange(n) / SR
    wl = 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t)
    wl = wl ** 4
    return w * wl * 0.026


def choir_chord(midis, n, tier):
    """Haunting choir pad — stacked pad voices."""
    out = np.zeros(n)
    for midi in midis:
        f = midi_to_hz(midi)
        out += dark_pad_voice(f, n, tier) * 1.4
    return out


# ---- FX ----

def riser(dur, from_hz, to_hz, seed=74):
    """Pitch riser — builds tension before a drop."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = from_hz * (to_hz / from_hz) ** (t / dur)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    noise_env = bandpass(noise(n, seed=seed), 500.0, 10000.0) * (t / dur) ** 2.2
    return soft_clip((tone * 0.42 + noise_env * 0.58) * 1.6, 1.7)


def sub_drop(dur, f0, f1):
    """Sub drop — deep bass plunge."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 2.2)
    env = np.exp(-t * 1.1)
    return soft_clip(np.sin(2 * np.pi * np.cumsum(freq) / SR) * env, 1.6)


def crash(dur, seed=14):
    """Crash cymbal — bright, noisy."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = bandpass(noise(n, seed=seed), 3200.0, 15000.0)
    body = eq_curve(body, [(4000.0, -2.0), (10000.0, 1.5), (16000.0, -3.0)])
    return body * np.exp(-t * 1.8) * 0.48


def screech_fx(dur, seed=51):
    """Screech — high-pitched, unsettling."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 1700.0 + 900.0 * np.sin(2 * np.pi * 6.5 * t) + 340.0 * np.sin(2 * np.pi * 0.9 * t)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    tone += np.sin(2 * np.pi * np.cumsum(f * 1.6) / SR) * 0.40
    return soft_clip(tone * exp_decay(n, dur * 0.30), 2.4) * 0.58


def reverse_signal(x):
    return x[::-1].copy()


def vinyl_crackle(n, seed=99):
    """Vinyl crackle — texture for lo-fi horror."""
    rng = _rng(seed)
    crackle = rng.uniform(-1.0, 1.0, n)
    click_mask = rng.random(n) > 0.996
    crackle[click_mask] *= 3.5
    return bandpass(crackle, 1200.0, 10000.0) * 0.06


# ---- Vocals (ported and improved from previous design) ----

VOWELS = {
    "ah": ((730.0, 90.0, 1.00), (1090.0, 110.0, 0.55), (2440.0, 170.0, 0.22), (3400.0, 250.0, 0.08)),
    "oh": ((570.0, 80.0, 1.00), (840.0, 100.0, 0.60), (2410.0, 170.0, 0.16), (3300.0, 250.0, 0.06)),
    "ee": ((300.0, 60.0, 1.00), (2290.0, 140.0, 0.50), (3010.0, 180.0, 0.28), (3700.0, 260.0, 0.10)),
    "oo": ((370.0, 70.0, 1.00), (950.0, 100.0, 0.42), (2350.0, 170.0, 0.10), (3300.0, 250.0, 0.05)),
}

PLAYER_VOWELS = ("ah", "ee", "oh", "ee")
TROLLGE_VOWELS = ("oh", "oo", "oh", "ah")
PLAYER_SHIFT = 1.10
TROLLGE_SHIFT = 0.82


def _glottal(f0, n, sr=SR, tilt=1.0, breath=0.0, seed=0):
    t = np.arange(n) / sr
    phase = 2 * np.pi * np.cumsum(np.full(n, f0)) / sr
    out = np.zeros(n)
    h = 1
    while f0 * h < min(9000.0, sr * 0.45):
        amp = (1.0 / (h ** tilt)) * (1.0 + 0.18 * (h % 2))
        out += np.sin(phase * h + 0.35 * h) * amp
        h += 1
    if breath > 0:
        out += bandpass(noise(n, seed=seed), 1200.0, 6500.0) * breath
    return out


def voice_note(midi, dur, dark=False, vowel=None, seed=0, scoop=0.028,
               vibrato_hz=None, vibrato=0.010, growl=0.0):
    n = max(int(0.18 * SR), int((dur + 0.11) * SR))
    t = np.arange(n) / SR
    f0 = midi_to_hz(midi)
    glide = 1.0 - scoop * np.exp(-t * 26.0)
    rate = vibrato_hz if vibrato_hz else (4.8 if dark else 5.2)
    depth = vibrato * (0.65 if dark else 1.0)
    ramp = np.clip((t - 0.09) / 0.34, 0.0, 1.0)
    vibr = 1.0 + depth * np.sin(2 * np.pi * rate * t + 0.4) * ramp
    inst = f0 * glide * vibr
    phase = 2 * np.pi * np.cumsum(inst) / SR
    src = np.zeros(n)
    h = 1
    while f0 * h < min(7600.0 if dark else 9500.0, SR * 0.45):
        amp = (1.0 / (h ** (1.45 if dark else 1.25))) * (1.0 + 0.14 * (h % 2))
        src += np.sin(phase * h + 0.35 * h) * amp
        h += 1
    if dark and growl > 0:
        src += np.sin(phase * 0.5) * 0.45 * growl
        src = soft_clip(src * (1.0 + 0.7 * growl), 1.45)
    if vowel is None:
        vowel = "oh" if dark else "ah"
    shift = TROLLGE_SHIFT if dark else PLAYER_SHIFT
    formants = tuple((hz * shift, bw * shift, gain) for hz, bw, gain in VOWELS[vowel])
    out = formant_bank(src, formants)
    n_c = int(0.032 * SR)
    out[:n_c] += bandpass(noise(n_c, seed=seed % 251), 3000.0, 8500.0) * (0.20 if dark else 0.26)
    attack = int((0.034 if dark else 0.022) * SR)
    release = int(0.13 * SR)
    sustain_len = max(1, n - attack - release)
    env = np.ones(n)
    env[:attack] = np.linspace(0.0, 1.0, attack) ** 1.6
    env[attack:attack + sustain_len] = 1.0
    env[attack + sustain_len:] = np.linspace(1.0, 0.0, n - attack - sustain_len) ** 1.8
    body = np.ones(n)
    arc = np.clip(np.arange(n) / max(1.0, 0.32 * SR), 0.0, 1.0)
    body *= 0.78 + 0.22 * arc
    out *= env * body
    out = highpass(out, 95.0)
    return out * (0.54 if dark else 0.60)


def pad_voicing(root_midi, tones, tier, tonic, scale):
    chord = sorted(root_midi + t for t in tones)
    root_pc = (root_midi - tonic) % 12
    if root_pc in scale:
        degree = scale.index(root_pc)
        interval = (scale[(degree + 1) % len(scale)] - root_pc) % 12
        ninth = root_midi + 12 + interval
        if interval not in {t % 12 for t in tones}:
            chord.append(ninth)
    return sorted(chord)


def pad_chord(midis, dur, gain=0.095, cutoff=1350.0, seed=0):
    n = int(dur * SR)
    out = np.zeros(n)
    for i, midi in enumerate(midis):
        f = midi_to_hz(midi)
        for mult, amp, phase in ((0.998, 0.48, 0.5), (1.0, 0.68, 1.3), (1.005, 0.48, 2.6)):
            out += saw(f * mult, n, phase0=phase + i) * amp
        out += sine(f * 2.0, n) * 0.11
    t = np.arange(n) / SR
    breathe = 1.0 + 0.28 * np.sin(2 * np.pi * 0.09 * t + seed) + 0.14 * np.sin(2 * np.pi * 0.37 * t)
    dark = lowpass(out, max(300.0, cutoff * 0.48))
    bright = lowpass(out, cutoff * 1.4)
    weight = np.clip(0.40 + 0.60 * np.sin(2 * np.pi * 0.09 * t + seed), 0.0, 1.0)
    out = dark * (1.0 - weight) + bright * weight
    env = adsr(n, attack=dur * 0.38, decay=dur * 0.09, sustain=0.78, release=dur * 0.44)
    out *= env * breathe
    out = highpass(out, 125.0).copy()
    return out * gain / max(1, len(midis)) * 1.0


def music_box(midi, dur=1.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = midi_to_hz(midi)
    partials = [(1.0, 1.0, 1.9), (2.8, 0.38, 3.6), (4.15, 0.20, 6.5), (5.6, 0.11, 9.5)]
    out = np.zeros(n)
    for mult, amp, decay in partials:
        out += np.sin(2 * np.pi * f * mult * t) * amp * np.exp(-t * decay)
    return out * 0.68


# ---- Piano source (sampled) ----

from functools import lru_cache  # noqa: E402


@lru_cache(maxsize=96)
def _piano_pitch(midi):
    import soundfile as sf
    samples = ((48, 'C3'), (55, 'G3'), (60, 'C4'), (67, 'G4'),
               (72, 'C5'), (79, 'G5'), (84, 'C6'))
    root, name = min(samples, key=lambda item: abs(item[0] - midi))
    path = os.path.join(ROOT, 'audio_src', 'piano', name + '.ogg')
    if not os.path.exists(path):
        n = int(2.0 * SR)
        f = midi_to_hz(midi)
        t = np.arange(n) / SR
        raw = (np.sin(2 * np.pi * f * t) * 0.62
               + np.sin(2 * np.pi * f * 2.0 * t) * 0.28
               + np.sin(2 * np.pi * f * 3.0 * t) * 0.12)
        raw = raw * np.exp(-t * 2.8)
        return raw
    raw, sr = sf.read(path, dtype='float64')
    if raw.ndim != 1:
        raise ValueError('unexpected piano source format')
    if sr != SR:
        ratio = SR / sr
        n_new = int(len(raw) * ratio)
        positions = np.arange(n_new) / ratio
        raw = np.interp(positions, np.arange(len(raw)), raw)
        sr = SR
    level = np.sqrt(np.mean(raw[:sr // 2] ** 2))
    raw = raw / max(level, 1e-8) * 0.10
    ratio = 2.0 ** ((midi - root) / 12.0)
    if ratio > 1:
        raw = lowpass(raw, min(17000., 0.47 * SR / ratio), sr=sr)
    count = min(int(len(raw) / (ratio * sr / SR)), int(3.5 * SR))
    positions = np.arange(count) * ratio * sr / SR
    return np.interp(positions, np.arange(len(raw)), raw)


def piano_note(midi, duration):
    sample = _piano_pitch(int(midi))
    n = min(len(sample), max(1, int((duration + 0.14) * SR)))
    result = sample[:n].copy()
    attack = min(n // 3, int(0.004 * SR))
    release = min(n // 3, int(0.16 * SR))
    if attack:
        result[:attack] *= np.linspace(0.0, 1.0, attack)
    if release:
        result[-release:] *= np.linspace(1.0, 0.0, release)
    return result


PIANO_PATTERNS = {
    'trolling': ((0, 0, 0, 1.8, .82), (1.6, 1, 0, 1.3, .58), (3.2, 2, 0, 1.5, .70)),
    'getting-dark': ((0, 0, 0, 2.2, .80), (2.2, 2, 0, 1.8, .58), (3.8, 1, 0, 1.1, .48)),
    'dont-look-back': ((0, 0, 0, 1.5, .78), (1.4, 2, 0, 1.1, .50), (2.8, 1, 0, 1.3, .62)),
    'super-scary': ((0, 0, 0, 1.6, .80), (1.4, 2, 0, 1.1, .55), (3.0, 1, 0, 1.2, .58)),
    'the-incident': ((0, 0, 0, 2.3, .88), (1.2, 2, 0, 1.8, .56), (2.8, 1, 0, 1.6, .68)),
}

ANSWER_MOTIFS = {
    'trolling': ((0.0, 0), (.5, 4), (1.1, 0)),
    'getting-dark': ((0.0, 0), (.6, -3), (1.2, -5)),
    'dont-look-back': ((0.0, 0), (.42, 6), (1.0, 3)),
    'super-scary': ((0.0, 0), (.4, -5), (1.05, 2)),
    'the-incident': ((0.0, 0), (.66, 3), (1.3, -2)),
}

STORY_ARCS = {
    'trolling': ((0, .48), (3, .67), (6, .88), (7, .45), (8, .38), (11, .83), (12, .42), (14, 1.0), (16, .48)),
    'getting-dark': ((0, .42), (4, .67), (8, .90), (9, .42), (10, .32), (13, .83), (16, .38), (18, 1.0), (20, .46)),
    'dont-look-back': ((0, .48), (4, .70), (8, .93), (9, .40), (10, .34), (14, .91), (16, .40), (18, 1.0), (20, .55)),
    'super-scary': ((0, .55), (4, .76), (8, .95), (9, .42), (10, .35), (14, .93), (16, .43), (18, 1.0), (20, .64)),
    'the-incident': ((0, .43), (6, .77), (10, .97), (13, .42), (14, .34), (19, .94), (22, .38), (25, 1.0), (28, .53)),
}


def story_level(song, fraction):
    starts = [s['time'] / 1000.0 for s in L.sections(song)] + [L.length(song)]
    knots = STORY_ARCS[song['id']]
    positions = [starts[index] / L.length(song) for index, _ in knots]
    return np.interp(np.clip(fraction, 0.0, 1.0), positions, [v for _, v in knots])


def piano_events(song):
    beat = L.beat(song)
    roles = L.measure_roles(song)
    for bar in range(L.measures(song)):
        role = roles.get(bar, 'verse')
        root, tones = L.chord_for_measure(song, bar)
        chord = sorted(song['tonic'] + root + t + 12 for t in tones)
        pattern = PIANO_PATTERNS[song['id']]
        for i, (offset, tone, lift, length, velocity) in enumerate(pattern):
            if role in ('drop', 'finale') and i == 1 and bar % 2:
                continue
            midi = chord[tone % len(chord)] + lift
            if bar % 8 == 7 and i == len(pattern) - 1:
                midi += 12
            variation = 0.9 + 0.1 * ((bar * 3 + i * 7) % 5) / 4.0
            level = velocity * variation * (1.18 if role in ('intro', 'break') else 0.80)
            yield (L.measure_time(song, bar) / 1000.0 + offset * beat,
                   midi, length * beat, level)


def piano_answers(song):
    notes = list(vocal_performance(song))
    beat = L.beat(song)
    motif = ANSWER_MOTIFS[song['id']]
    last_bar = -100
    for (note, at, dur, _), (following, next_at, _, _) in zip(notes, notes[1:]):
        bar = note['measure']
        if bar - last_bar < 2:
            continue
        start = at + dur + 0.05 + 0.12 * beat
        end = next_at - 0.12 * beat
        last_end = start + (motif[-1][0] + 0.34) * beat + 0.16
        if last_end > end:
            continue
        anchor = L.note_pitch(song, bar, note['id'], semi=note.get('semi')) - 12
        anchor = max(55, min(79, anchor))
        previous = None
        result = []
        for index, (offset, interval) in enumerate(motif):
            when = start + offset * beat
            current_bar = min(L.measures(song) - 1, max(0, int((when - song['offset']) / L.measure(song))))
            root, tones = L.chord_for_measure(song, current_bar)
            candidates = [song['tonic'] + root + tone + octave
                          for tone in tones for octave in (0, 12, 24, 36)
                          if 45 <= song['tonic'] + root + tone + octave <= 88]
            target = anchor + interval
            if previous is not None and interval != motif[index - 1][1]:
                direction = 1 if interval > motif[index - 1][1] else -1
                directed = [p for p in candidates if (p - previous) * direction > 0]
                if directed:
                    candidates = directed
            pitch = min(candidates, key=lambda p: abs(p - target))
            result.append((when, pitch, 0.34 * beat, (0.62, 0.48, 0.54)[index]))
            previous = pitch
        yield from result
        last_bar = bar


def rhythm_landmarks(song, part):
    if part not in ('drums', 'bass'):
        raise ValueError('unknown rhythm part')
    sections = L.sections(song)
    measure = L.measure(song)
    beat = L.beat(song)
    total = L.length(song)
    points = [(0.0, 0.88 if part == 'drums' else 0.92)]
    for i, sec in enumerate(sections):
        start = sec['time'] / 1000.0
        for bar in range(sec['measures']):
            shape = (0.80, 0.95, 0.88, 1.0)[bar % 4]
            if sec['role'] in ('drop', 'finale'):
                shape = 0.9 + 0.1 * shape
            if part == 'bass':
                shape = 0.52 + 0.48 * shape
            points.append((start + bar * measure, shape))
        if i + 1 < len(sections):
            nxt = sections[i + 1]
            boundary = nxt['time'] / 1000.0
            if nxt['role'] in ('drop', 'finale') and sec['role'] not in ('intro', 'break'):
                depth = 0.38 if part == 'drums' else 0.70
                points.append((boundary - 0.65 * beat, 1.0))
                points.append((boundary - 0.22 * beat, depth))
    points.append((total, 0.92))
    return sorted(points)


def shape_rhythm(song, signals, part):
    points = rhythm_landmarks(song, part)
    n = len(signals[0])
    curve = np.interp(np.arange(n) / SR,
                      [time for time, _ in points], [level for _, level in points])
    for signal in signals:
        signal *= curve


# --------------------------------------------------------------------------- #
# Bass & drum patterns ----

def bass_pattern(style, role, beat, tier):
    if style == "dark_trap":
        if role == "break":
            return [(0.0, -12, 2.6)]
        if role == "intro":
            return [(0.0, -12, 4.2)]
        return [(0.0, -12, 1.5), (1.6, 0, 1.1), (2.7, -12, 0.9), (3.4, 0, 0.8)]
    if style == "dark_glitch":
        if role == "break":
            return [(0.0, -12, 1.5)]
        if role == "intro":
            return [(0.0, -12, 3.4)]
        if role in ("finale", "drop"):
            return [(i * 0.25, (-12 if i % 4 == 0 else (12 if i % 8 == 5 else 0)),
                     0.25 * (1.0 if i % 2 else 0.7)) for i in range(16)]
        return [(i * 0.25, (-12 if i % 8 == 0 else (12 if i % 8 == 6 else 0)),
                     0.25 * 0.95) for i in range(8)]
    if style == "industrial":
        if role == "break":
            return [(0.0, -12, 2.4), (2.2, 0, 2.0)]
        if role == "intro":
            return [(0.0, -12, 4.2)]
        return [(i * 0.5, (-12 if i % 4 == 0 else (7 if i == 5 else 0)),
                     0.5 * (0.92 if i % 2 else 1.10)) for i in range(8)]
    if style == "dark_ambient":
        if role == "break":
            return [(0.0, -12, 2.2)]
        if role == "intro":
            return [(0.0, -12, 4.0)]
        return [(i * 0.5, -12 if i % 4 == 0 else 0, 0.5 * (0.90 if i % 2 else 1.08)) for i in range(8)]
    if role == "break":
        return [(0.0, -12, 2.2)]
    if role == "drop":
        return [(0.0, 0, 0.48), (0.55, 0, 0.34), (0.82, 0, 0.24), (1.1, -12, 0.45),
                (1.6, 0, 0.34), (1.9, 0, 0.24), (2.2, 0, 0.48), (2.75, -12, 0.32),
                (3.3, 0, 0.48), (3.8, 0, 0.34)]
    if role == "intro":
        return [(0.0, -12, 4.0)]
    return [(i * 0.5, -12 if i % 4 == 0 else 0, 0.5 * (0.90 if i % 2 else 1.08)) for i in range(8)]


def drum_pattern(style, role, t0, beat, tier, kick_s, snare_s, hat_l, hat_r, fx_s, m):
    intensity = ROLE_GAIN[role]
    if role in ("verse", "build", "drop", "finale"):
        if style == "dark_trap":
            add_at(kick_s, dark_kick(0.48, style, tier), t0, 1.0 * intensity)
            add_at(kick_s, dark_kick(0.48, style, tier), t0 + 2.85 * beat, 0.74 * intensity)
            add_at(snare_s, dark_snare(0.40, style, tier, 71), t0 + 2 * beat, 0.60 * intensity)
            for step in range(8):
                at = t0 + step * beat / 2.0
                add_at(hat_l if step % 2 else hat_r, dark_hat(0.055, False, style, 40 + step), at, 0.34 * intensity)
                if step % 2 == 1 and (role in ("drop", "finale") or tier >= 2):
                    add_at(hat_r, dark_hat(0.05, False, style, 60 + step), at + beat / 4.0, 0.20 * intensity)
                    add_at(hat_l, dark_hat(0.05, False, style, 80 + step), at + beat * 0.5, 0.17 * intensity)
                    add_at(hat_l, dark_hat(0.17, True, style, 90 + step), at + beat * 0.70, 0.16 * intensity)
        elif style == "dark_glitch":
            add_at(kick_s, dark_kick(0.28, style, tier), t0, 1.0 * intensity)
            add_at(kick_s, dark_kick(0.28, style, tier), t0 + 1.85 * beat, 0.76 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.28, style, tier), t0 + 2.7 * beat, 0.66 * intensity)
                add_at(kick_s, dark_kick(0.28, style, tier), t0 + 3.45 * beat, 0.60 * intensity)
            add_at(snare_s, dark_snare(0.34, style, tier, 50 + m), t0 + 2 * beat, 0.66 * intensity)
            for q in range(4):
                add_at(snare_s, dark_snare(0.17, style, tier, 70 + q),
                       t0 + 3 * beat + q * beat / 8.0, (0.38 - 0.06 * q) * intensity)
            for q in range(8):
                at = t0 + q * beat / 2.0
                if q % 3 == 2:
                    continue
                add_at(hat_l if q % 2 else hat_r, dark_hat(0.05, q == 7, style, 120 + q), at, 0.28 * intensity)
                if q % 2 and role in ("drop", "finale"):
                    add_at(hat_r, dark_hat(0.05, False, style, 140 + q), at + beat / 4.0, 0.16 * intensity)
        elif style == "industrial":
            for b in range(4):
                at = t0 + b * beat
                add_at(kick_s, dark_kick(0.38, style, tier), at, 0.96 * intensity)
                if b in (1, 3):
                    add_at(snare_s, dark_snare(0.40, style, tier, 12 + b), at, 0.54 * intensity)
                    add_at(snare_s, dark_snare(0.22, style, tier, 30 + b), at + beat / 2.0, 0.22 * intensity)
                for q in range(4):
                    add_at(hat_l if (q + b) % 2 else hat_r, dark_hat(0.075, q == 3, style, 100 + q + b * 4), at + q * beat / 4.0, 0.23 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.38, style, tier), t0 + 3.7 * beat, 0.60 * intensity)
        elif style == "dark_ambient":
            for b in range(4):
                at = t0 + b * beat
                if b in (0, 2) or (role in ("drop", "finale") and b == 3 and tier >= 2):
                    add_at(kick_s, dark_kick(0.48, style, tier), at, 0.98 * intensity)
                if b in (1, 3):
                    add_at(snare_s, dark_snare(0.38, style, tier, 12 + b), at, 0.58 * intensity)
                add_at(hat_l, dark_hat(0.085, False, style, 13 + b), at, 0.30 * intensity)
                add_at(hat_r, dark_hat(0.085, True, style, 14 + b), at + beat / 2.0, 0.24 * intensity)
                air_n = int(0.06 * SR)
                air_t = np.arange(air_n) / SR
                air = bandpass(noise(air_n, seed=90 + b), 10000.0, 17000.0) * np.exp(-air_t * 48.0)
                add_at(hat_l if b % 2 == 0 else hat_r, air, at, 0.20 * intensity)
                add_at(hat_r if b % 2 == 0 else hat_l, air, at + beat / 2.0, 0.16 * intensity)
                if role in ("drop", "finale") or tier >= 3:
                    add_at(hat_l, dark_hat(0.05, False, style, 15 + b), at + beat / 4.0, 0.16 * intensity)
                    add_at(hat_r, dark_hat(0.05, False, style, 19 + b), at + 3 * beat / 4.0, 0.16 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.48, style, tier), t0 + 3.7 * beat, 0.64 * intensity)
        else:  # dark_bounce
            for b in range(4):
                at = t0 + b * beat
                if b in (0, 2) or (role in ("drop", "finale") and b == 3 and tier >= 2):
                    add_at(kick_s, dark_kick(0.48, style, tier), at, 0.98 * intensity)
                if b in (1, 3):
                    add_at(snare_s, dark_snare(0.38, style, tier, 12 + b), at, 0.58 * intensity)
                add_at(hat_l, dark_hat(0.085, False, style, 13 + b), at, 0.30 * intensity)
                add_at(hat_r, dark_hat(0.085, True, style, 14 + b), at + beat / 2.0, 0.24 * intensity)
                air_n = int(0.06 * SR)
                air_t = np.arange(air_n) / SR
                air = bandpass(noise(air_n, seed=90 + b), 10000.0, 17000.0) * np.exp(-air_t * 48.0)
                add_at(hat_l if b % 2 == 0 else hat_r, air, at, 0.20 * intensity)
                add_at(hat_l if b % 2 == 0 else hat_r, air, at + beat / 2.0, 0.16 * intensity)
                if role in ("drop", "finale") or tier >= 3:
                    add_at(hat_l, dark_hat(0.05, False, style, 15 + b), at + beat / 4.0, 0.16 * intensity)
                    add_at(hat_r, dark_hat(0.05, False, style, 19 + b), at + 3 * beat / 4.0, 0.16 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.48, style, tier), t0 + 3.7 * beat, 0.64 * intensity)
    elif role == "break":
        add_at(kick_s, dark_kick(0.48, style, tier), t0, 0.74)
        add_at(snare_s, dark_snare(0.38, style, tier, 61), t0 + 2 * beat, 0.44)
        for b in range(4):
            add_at(hat_r, dark_hat(0.05, True, style, 20 + b), t0 + b * beat, 0.16)
    else:
        add_at(kick_s, dark_kick(0.48, style, tier), t0, 0.64)
        for b in range(4):
            add_at(hat_r, dark_hat(0.05, False, style, 30 + b), t0 + b * beat + beat / 2.0, 0.16)

    if role in ("verse", "build", "drop", "finale"):
        air_n = int(0.055 * SR)
        air = bandpass(noise(air_n, seed=300 + m), 11000.0, 18000.0) * exp_decay(air_n, 0.026)
        for b in range(2, 5):
            gain = 0.24 if style == "dark_trap" else (0.20 if style == "industrial" else 0.18)
            add_at(hat_l if b % 2 == 0 else hat_r, air, t0 + (b - 1) * beat + beat * 0.5, gain * intensity)

    if style == "dark_glitch" and role in ("verse", "build", "drop", "finale") and m % 2 == 0:
        g_n = int(beat * 0.9 * SR)
        gt = np.arange(g_n) / SR
        chunk = bandpass(noise(g_n, seed=230 + m), 800.0, 7000.0)
        chunk = bitcrush(chunk * np.exp(-gt * 10.0), bits=4, hold=9)
        add_at(fx_s, chunk, t0 + 3 * beat + beat * 0.25, 0.14)
    elif style == "dark_ambient" and role in ("drop", "finale"):
        g_n = int(2.0 * SR)
        gt = np.arange(g_n) / SR
        gong = sum(np.sin(2 * np.pi * hz * gt) * amp
                   for hz, amp in ((68.0, 0.34), (102.0, 0.20), (136.0, 0.14),
                                   (204.0, 0.08), (272.0, 0.06)))
        gong *= np.exp(-gt * 2.8)
        add_at(fx_s, gong, t0, 0.20)
    elif style == "industrial" and role in ("drop", "finale"):
        add_at(fx_s, bandpass(noise(int(0.5 * SR), seed=200 + m), 1100.0, 11000.0)
               * exp_decay(int(0.5 * SR), 0.09), t0 + 3.9 * beat, 0.14)
    elif style == "dark_trap" and role in ("build", "drop") and m % 4 == 0:
        rev_n = int(beat * 1.4 * SR)
        rev = crash(beat * 1.4, seed=210 + m)[::-1][:rev_n]
        add_at(fx_s, rev, t0 + 4 * beat - beat * 1.4, 0.20)
    elif style == "dark_bounce" and role == "verse" and m % 2 == 1:
        blk_n = int(0.07 * SR)
        blk = np.sin(2 * np.pi * 1250.0 * np.arange(blk_n) / SR) * exp_decay(blk_n, 0.017)
        add_at(hat_r, blk, t0 + 2.7 * beat, 0.14)


def drum_fill(at, length, style, tier, snare_s, fx_s, seed=40, loudness=1.0):
    hits = 12
    for i in range(hits):
        when = at + length * i / hits
        if style == "dark_trap":
            add_at(snare_s, dark_snare(0.17, style, tier, seed + i), when, 0.14 * loudness)
        else:
            add_at(snare_s, dark_snare(0.24, style, tier, seed + i), when,
                   (0.20 + 0.26 * i / hits) * loudness)
    add_at(fx_s, crash(2.2, seed=80), at + length, 0.24 + 0.07 * tier)


def ghost_snares(style, role, t0, beat, tier, snare_s, hat_r, m, intensity):
    if role not in ("verse", "build", "drop", "finale"):
        return
    for beat_index in (1, 3):
        for fraction in (0.25, 0.75):
            if role == "verse" and fraction == 0.25:
                continue
            add_at(snare_s, dark_snare(0.14, style, tier, 300 + m * 4 + beat_index),
                   t0 + beat_index * beat + fraction * beat,
                   0.11 * intensity * 0.90)
    if m % 2 == 1:
        add_at(hat_r, dark_hat(0.17, True, style, 400 + m), t0 + 3.7 * beat, 0.20 * intensity)


# --------------------------------------------------------------------------- #
# Horror & FX per tier ----

def scripted_stinger(fx_s, func, at, tier, song):
    if func == "trollgeJumpScare":
        add_at(fx_s, sub_drop(2.8, 190.0, 24.0), at - 0.07, 0.80)
        add_at(fx_s, crash(2.6, seed=71), at, 0.60)
        add_at(fx_s, screech_fx(2.0), at, 0.45)
        blast_n = int(1.0 * SR)
        blast = bandpass(noise(blast_n, seed=72), 700.0, 11000.0) * exp_decay(blast_n, 0.24)
        add_at(fx_s, soft_clip(blast, 2.4), at, 0.45)
    elif func == "trollgeScreenShake":
        add_at(fx_s, crash(2.0, seed=73), at, 0.50)
        add_at(fx_s, sub_drop(2.2, 160.0, 28.0), at, 0.50)
    elif func == "trollgeDistort":
        glitch_n = int(1.3 * SR)
        glitch = bitcrush(square(80.0, glitch_n, duty=0.16) * exp_decay(glitch_n, 0.60), bits=3, hold=8)
        add_at(fx_s, glitch, at, 0.26)
    elif func == "trollgeInvert":
        riser_n = int(2.8 * SR)
        rt = np.arange(riser_n) / SR
        riser = bandpass(noise(riser_n, seed=74), 400.0, 10000.0) * (rt / rt[-1]) ** 2.4
        add_at(fx_s, riser, max(0.0, at - 2.8), 0.45)
        add_at(fx_s, sub_drop(2.4, 220.0, 30.0), at, 0.65)
    elif func == "trollgePhase2":
        add_at(fx_s, crash(3.0, seed=75), at, 0.60)
        add_at(fx_s, screech_fx(2.6, seed=76), at, 0.55)
        add_at(fx_s, sub_drop(3.0, 210.0, 20.0), at, 0.70)
    else:
        st_n = int(1.1 * SR)
        st = highpass(noise(st_n, seed=77), 2600.0) * np.exp(-np.arange(st_n) / (0.38 * SR))
        add_at(fx_s, st, at, 0.34)


# --------------------------------------------------------------------------- #
# The instrumental ----

def render_song(song):
    total = L.length(song)
    n_total = int(round(total * SR))
    beat = L.beat(song)
    measure = L.measure(song)
    step = L.step(song)
    scare = song["scare"]
    tier = tier_for(scare)
    style = SONG_STYLES[song["id"]]
    sid = song["id"]

    kick_s, snare_s = empty(total), empty(total)
    hat_l, hat_r = empty(total), empty(total)
    bass_s = empty(total)
    pad_l, pad_r = empty(total), empty(total)
    lead_o, lead_p = empty(total), empty(total)
    fx_s = empty(total)
    piano_l, piano_r = empty(total), empty(total)
    arp_o, arp_p = empty(total), empty(total)

    secs = L.sections(song)
    roles = L.section_roles(song)
    measure_role = L.measure_roles(song)
    total_measures = L.measures(song)

    # ---- pads ----
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        root, tones = L.chord_for_measure(song, m)
        chord = pad_voicing(song["tonic"] + root, tones, tier, song["tonic"], L.SCALES[song["id"]])
        cutoff = {"intro": 700.0, "verse": 1100.0, "build": 1500.0,
                  "drop": 2000.0, "break": 600.0, "finale": 2400.0}[role]
        gain = 0.10 * ROLE_GAIN[role]
        sig = pad_chord(chord, measure * 1.08, gain=gain, cutoff=cutoff, seed=m * 1.5)
        add_at(pad_l, sig, t0, 0.64)
        add_at(pad_r, sig, t0 + 0.016, 0.64)

    # ---- piano ----
    answers = list(piano_answers(song))
    accompaniment = [event for event in piano_events(song)
                     if all(abs(event[0] - answer[0]) > 0.60 * beat for answer in answers)]
    for i, (at, midi, dur, velocity) in enumerate(accompaniment + answers):
        note = piano_note(midi, dur)
        pan_pos = (-0.24 if i % 2 else 0.24)
        l, r = pan(note, pan_pos)
        add_at(piano_l, l, at, velocity * 0.98)
        add_at(piano_r, r, at + 0.010, velocity * 0.98)

    # ---- bass ----
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        root, _tones = L.chord_for_measure(song, m)
        base = song["tonic"] + root
        pattern = bass_pattern(style, role, beat, tier)
        bass_level = {"dark_trap": 0.60, "dark_glitch": 0.26}.get(style, 0.32)
        level = bass_level * (0.5 + 0.5 * ROLE_GAIN[role]) * (0.85 if style == "industrial" else 1.0)
        for offset_b, octave, dur_b in pattern:
            dur_s = dur_b * beat
            pitch = octave + 12 if octave == -12 and style != "dark_trap" else octave
            if style == "dark_trap" and abs(octave) > 0:
                add_at(bass_s, slide_808(midi_to_hz(base + pitch), midi_to_hz(base + pitch - 7),
                                         int(dur_s * SR), tier), t0 + offset_b * beat, level)
            else:
                add_at(bass_s, reese_bass(midi_to_hz(base + pitch), int(dur_s * SR), tier),
                       t0 + offset_b * beat, level)

    # ---- arpeggio (16th note movement for energy) ----
    arp_level = {"dark_glitch": 0.32, "industrial": 0.36, "dark_trap": 0.24}.get(style, 0.20)
    if arp_level > 0:
        for m in range(total_measures):
            t0 = L.measure_time(song, m) / 1000.0
            role = measure_role.get(m, "verse")
            if role not in ("verse", "build", "drop", "finale"):
                continue
            root, tones = L.chord_for_measure(song, m)
            base = song["tonic"] + root
            arp_notes = [0, 4, 7, 10, 12, 10, 7, 4]
            for i, tone in enumerate(arp_notes):
                at = t0 + (i % 8) * step * 2.0
                if at >= total:
                    continue
                midi = base + tone
                dur = step * 1.7
                sig = dark_saw_lead(midi_to_hz(midi), int(dur * SR), tier)
                target = arp_p if (i % 2 == 0) else arp_o
                add_at(target, sig, at, arp_level * ROLE_GAIN[role] * 0.55)

    # ---- drums ----
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        drum_pattern(style, role, t0, beat, tier, kick_s, snare_s, hat_l, hat_r, fx_s, m)
        ghost_snares(style, role, t0, beat, tier, snare_s, hat_r, m, ROLE_GAIN[role])

        if m + 1 < total_measures and measure_role.get(m + 1) != role:
            upcoming = measure_role.get(m + 1, role)
            if ROLE_GAIN[upcoming] >= ROLE_GAIN[role]:
                drum_fill(t0 + 3 * beat, beat, style, tier, snare_s, fx_s, seed=500 + m, loudness=0.80 + 0.40 * tier)
                add_at(fx_s, crash(2.2, seed=80 + m), t0 + 4 * beat, 0.24 + 0.07 * tier)
                riser_n = int(beat * 2.4 * SR)
                rt = np.arange(riser_n) / SR
                riser = bandpass(noise(riser_n, seed=81 + m), 700.0, 11000.0) * (rt / rt[-1]) ** 2.2
                add_at(fx_s, riser, t0 + 4 * beat - beat * 2.4, 0.14 + 0.06 * tier)

    # ---- groove polish ----
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        if role not in ("verse", "build", "drop", "finale"):
            continue
        intensity = ROLE_GAIN[role]
        rng = np.random.default_rng(m * 7919)
        nudge = rng.random() * 0.014 - 0.007
        for beat_index in (1, 3):
            for fraction in (0.25, 0.75):
                if role == "verse" and fraction == 0.25:
                    continue
                add_at(snare_s, dark_snare(0.14, style, tier, 300 + m * 4 + beat_index),
                       t0 + beat_index * beat + fraction * beat + nudge,
                       0.11 * intensity * 0.88)
        if m % 2 == 1:
            add_at(hat_r, dark_hat(0.17, True, style, 400 + m), t0 + 3.7 * beat, 0.20 * intensity)

    shape_rhythm(song, (kick_s, snare_s, hat_l, hat_r), 'drums')
    shape_rhythm(song, (bass_s,), 'bass')

    # ---- lead ----
    lead_index = 0
    for note in L.melodic_onsets(song):
        at = note["time"] / 1000.0
        role = measure_role.get(note["measure"], "verse")
        dur = max(0.20, note["sLen"] / 1000.0 if note["sLen"] else step * 2.4)
        midi = L.note_pitch(song, note["measure"], note["id"], semi=note.get("semi"))
        accent = 1.0 if note["time"] % (beat * 1000.0) < 1.0 else 0.90
        dur *= 1.10
        sig = dark_saw_lead(midi, int(dur * SR), tier)
        sub = dark_saw_lead(midi - 12, int(dur * 0.88 * SR), tier)
        sub = np.pad(sub, (0, max(0, len(sig) - len(sub))))[:len(sig)]
        sig = sig + sub * 0.24
        target = lead_p if note["side"] == "player" else lead_o
        lead_level = 0.60 if style == "dark_glitch" else 0.52
        add_at(target, sig, at, lead_level * accent * (0.70 + 0.42 * ROLE_GAIN[role]))
        if role == "finale" and note["side"] == "player":
            add_at(target, dark_saw_lead(midi + 12, int(dur * 0.76 * SR), tier), at,
                   0.26 * accent)
        lead_index += 1

    # ---- horror layers per tier ----
    ambient = np.ones(n_total)
    for m in range(total_measures):
        start = int(L.measure_time(song, m) / 1000.0 * SR)
        end = min(n_total, int(L.measure_time(song, m + 1) / 1000.0 * SR))
        if end > start:
            ambient[start:end] = 0.34 + 0.66 * ROLE_GAIN.get(measure_role.get(m), 0.7)

    if tier >= 1:
        drone_root = midi_to_hz(song["tonic"] - 12)
        drone_gain = {1: 0.030, 2: 0.20, 3: 0.048}.get(tier, 0.042 * tier)
        drone = lowpass(sine(drone_root, n_total) * drone_gain +
                        sine(drone_root * 0.5, n_total) * 0.44 * drone_gain, 130.0)
        fx_s += drone * ambient

    if tier >= 2:
        fx_s += highpass(noise(n_total, seed=63), 3000.0) * (0.020 if tier == 2 else 0.030) * ambient

    if tier >= 3:
        swell = bandpass(noise(n_total, seed=65), 500.0, 3000.0)
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.085 * np.arange(n_total) / SR)
        fx_s += swell * lfo * 0.050 * ambient

    if tier >= 4:
        breath = bandpass(noise(n_total, seed=67), 400.0, 2200.0)
        blfo = np.sin(2 * np.pi * 0.15 * np.arange(n_total) / SR)
        fx_s += breath * np.maximum(0.0, blfo) * 0.060 * ambient
        tritone = sine(drone_root * 2 ** 0.5, n_total) * 0.028 + sine(drone_root, n_total) * 0.026
        trem = 0.50 + 0.50 * np.sin(2 * np.pi * 6.0 * np.arange(n_total) / SR)
        fx_s += lowpass(tritone * trem, 200.0) * ambient

    if tier >= 5:
        fx_s += heartbeat(song["bpm"], total, tier)
        fx_s += whispers(n_total, tier)
        choir = choir_chord([song["tonic"] - 12, song["tonic"] - 5, song["tonic"]], n_total, tier)
        fx_s += choir * ambient

    # ---- crackle for texture ----
    if tier >= 2:
        fx_s += vinyl_crackle(n_total, seed=900 + tier) * ambient * 0.55

    # ---- scripted stingers ----
    for seconds, func in song["events"]:
        at = max(0.0, seconds)
        scripted_stinger(fx_s, func, at, tier, song)

    # ---- per-song differentiation FX ----
    if sid == "trolling":
        bells = sum(sine(midi_to_hz(72 + i * 7), n_total) * 0.014 for i in range(4))
        fx_s += lowpass(bells, 3400.0) * ambient
    elif sid == "getting-dark":
        growl = soft_clip(saw(midi_to_hz(song["tonic"] - 12), n_total) * 3.0, 1.3)
        fx_s += lowpass(growl, 180.0) * 0.040 * ambient
    elif sid == "dont-look-back":
        for m in range(total_measures):
            if m % 2 == 1:
                t0 = L.measure_time(song, m) / 1000.0
                add_at(fx_s, bitcrush(bandpass(noise(int(0.12 * SR), seed=1000 + m),
                        4000.0, 9000.0) * exp_decay(int(0.12 * SR), 24.0),
                        bits=4, hold=10) * 0.040, t0 + beat)
    elif sid == "super-scary":
        import random as _r
        rng = _r.Random(1234)
        for _ in range(int(total / 1.2)):
            at = rng.uniform(0.5, total - 0.5)
            add_at(fx_s, metal_hit(0.10, seed=int(at * 1000)), at, 0.07)
    elif sid == "the-incident":
        rumble = sine(midi_to_hz(song["tonic"] - 18), n_total) * 0.020
        fx_s += lowpass(rumble, 70.0) * ambient
        hiss = bandpass(noise(n_total, seed=9010), 8000.0, 17000.0)
        hiss_env = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)
        fx_s += hiss * hiss_env * 0.08 * ambient

    # ---- ending ----
    end_at = total - 2.0 * beat
    root, tones = L.chord_for_measure(song, total_measures - 1)
    final_chord = [song["tonic"] + root + t + 12 for t in tones] + [song["tonic"] + root - 12]
    sting = pad_chord(final_chord, max(0.5, total - end_at), gain=0.22, cutoff=2400.0)
    add_at(pad_l, sting, end_at, 0.88)
    add_at(pad_r, sting, end_at, 0.88)
    intensity = 0.30 if tier <= 2 else (0.60 if tier <= 4 else 0.90)
    add_at(fx_s, crash(2.4, seed=91), end_at, 0.38 * intensity)
    add_at(fx_s, sub_drop(2.2, 170.0, 22.0), end_at, 0.50 * intensity)
    add_at(kick_s, dark_kick(0.60, style, tier), end_at, 0.90 * intensity)
    add_at(piano_l, piano_note(final_chord[0], max(0.60, 2.2 * beat)), end_at, 0.60)
    add_at(piano_r, piano_note(final_chord[-2], max(0.60, 2.2 * beat)), end_at + 0.05, 0.50)

    # ---- dread layer ----
    n_all = np.arange(n_total) / SR
    drone_hz = midi_to_hz(song["tonic"] - 12)
    beat_hz = 0.48 + 0.14 * tier
    drone = (sine(drone_hz, n_total) * 0.52 + sine(drone_hz * 1.005, n_total) * 0.48)
    dread_l = drone * (0.68 + 0.32 * np.sin(2 * np.pi * beat_hz * n_all))
    dread_r = drone * (0.68 + 0.32 * np.sin(2 * np.pi * beat_hz * n_all + 2.3))
    if tier >= 4:
        tritone_hz = midi_to_hz(song["tonic"] - 12) * (2 ** (6 / 12.0))
        dread_l = dread_l + sine(tritone_hz, n_total) * 0.30
        dread_r = dread_r + sine(tritone_hz * 1.005, n_total) * 0.30
    dread_amount = max(0.0, (tier - 1) / 4.0)
    if sid == "trolling":
        dread_amount *= 0.5
    elif sid == "getting-dark":
        dread_amount *= 2.4
    elif sid == "dont-look-back":
        dread_amount *= 0.74
    elif sid == "super-scary":
        dread_amount *= 0.74
    elif sid == "the-incident":
        dread_amount *= 2.8
    gain = 0.100 * dread_amount
    dread_l *= dread_amount
    dread_r *= dread_amount
    dread_l += lowpass(dread_l, 100.0) * gain
    dread_r += lowpass(dread_r, 100.0) * gain
    breath = bandpass(noise(n_total, seed=10 + tier), 900.0, 3000.0)
    swing = 0.5 + 0.5 * np.sin(2 * np.pi * (0.085 + 0.03 * tier) * n_all - 0.4)
    swing = swing ** 3
    breath = breath * swing * (0.065 * dread_amount)
    dread_l += breath
    dread_r += np.roll(breath, int(0.025 * SR))

    # ---- air bed ----
    air_bed = bandpass(noise(n_total, seed=9002), 12000.0, 19000.0) * 0.022

    # ---- stereo mix ----
    left = np.zeros(n_total)
    right = np.zeros(n_total)
    lead_send = 0.5 * (lead_p + lead_o)
    wet = reverb(lead_send + 0.60 * snare_s, wet=0.40, size=1.05)
    echo = delay(lead_send, beat * 0.62, feedback=0.32, mix=0.26 + 0.07 * tier)
    del lead_send
    wet_l, wet_r = haas(wet, 0.016)
    echo_l = echo
    echo_r = np.roll(echo, int(0.24 * beat * SR))
    del wet, echo

    key = kick_s
    pad_l = sidechain(pad_l, key, depth=0.62)
    pad_r = sidechain(pad_r, key, depth=0.62)
    bass_s = sidechain(bass_s, key, depth=0.46)

    if tier >= 3:
        cut = int(len(hat_l) * 0.64)
        for channel in (hat_l, hat_r):
            channel[cut:] = lowpass(channel[cut:], 8200.0) * 0.78 + channel[cut:] * 0.22

    def fit(x):
        x = dc_block(np.asarray(x[:n_total], dtype=np.float64))
        tail = int(0.30 * SR)
        x[-tail:] *= np.linspace(1.0, 0.0, tail)
        return x

    bass_s = highpass(bass_s, 110.0)

    stems = {
        "kick": (kick_s, 0.46, 0.46),
        "snare": (snare_s, 0.66, 0.66),
        "hat_l": (hat_l, 0.60, 0.20),
        "hat_r": (hat_r, 0.20, 0.60),
        "bass": (bass_s, 0.34, 0.34),
        "pad_l": (pad_l, 0.54, 0.20),
        "pad_r": (pad_r, 0.20, 0.54),
        "piano_l": (piano_l, 0.92, 0.16),
        "piano_r": (piano_r, 0.16, 0.92),
        "lead_o": (lead_o, 1.10 if style == "dark_ambient" else 0.94, 0.64 if style == "dark_ambient" else 0.56),
        "lead_p": (lead_p, 0.64 if style == "dark_ambient" else 0.56, 1.10 if style == "dark_ambient" else 0.94),
        "arp_o": (arp_o, 0.57, 0.22),
        "arp_p": (arp_p, 0.22, 0.57),
        "fx": (fx_s, 0.34, 0.34),
        "wet_l": (wet_l, 0.48, 0.06),
        "wet_r": (wet_r, 0.06, 0.48),
        "echo_l": (echo_l, 0.38, 0.06),
        "echo_r": (echo_r, 0.06, 0.38),
        "dread_l": (dread_l, 0.46, 0.46),
        "dread_r": (dread_r, 0.46, 0.46),
    }

    for name in list(stems):
        signal, gl, gr = stems.pop(name)
        signal = fit(signal)
        left += signal * gl
        right += signal * gr
        del signal

    left += air_bed
    right += np.roll(air_bed, int(0.013 * SR))
    del air_bed

    if style == "dark_trap":
        hiss = bandpass(noise(n_total, seed=8129), 9500.0, 17000.0) * 0.030
        left += hiss
        right += np.roll(hiss, int(0.015 * SR))
        del hiss

    # ---- per-song master EQ ----
    if sid == "trolling":
        master_points = [(26.0, -30.0), (40.0, -22.0), (55.0, -16.0), (70.0, -12.0),
                         (90.0, -10.0), (120.0, -6.0), (180.0, -4.0), (250.0, -2.0),
                         (320.0, -0.8), (450.0, 0.0), (650.0, 0.4), (800.0, 0.6),
                         (1400.0, 1.2), (2000.0, 1.6), (3000.0, 2.0), (4000.0, 2.4),
                         (6000.0, 2.8), (8000.0, 3.0), (10000.0, 3.2), (12000.0, 2.8),
                         (15000.0, 2.2), (18000.0, 1.6)]
    elif sid == "getting-dark":
        master_points = [(26.0, -46.0), (40.0, -38.0), (55.0, -30.0), (70.0, -22.0),
                         (90.0, -17.0), (120.0, -12.0), (180.0, -7.0), (250.0, -3.5),
                         (320.0, -1.6), (450.0, -0.9), (650.0, -0.4), (800.0, 0.0),
                         (1400.0, -0.2), (2000.0, 0.3), (3000.0, 0.7), (4000.0, 1.0),
                         (6000.0, 1.1), (8000.0, 1.3), (10000.0, 1.5), (12000.0, 1.1),
                         (15000.0, 0.7), (18000.0, 0.2)]
    elif sid == "dont-look-back":
        master_points = [(26.0, -34.0), (40.0, -26.0), (55.0, -20.0), (70.0, -14.0),
                         (90.0, -12.0), (120.0, -8.0), (180.0, -5.0), (250.0, -2.5),
                         (320.0, -1.2), (450.0, -0.4), (650.0, 0.0), (800.0, 0.6),
                         (1400.0, 1.6), (2000.0, 2.2), (3000.0, 2.8), (4000.0, 3.2),
                         (6000.0, 3.6), (8000.0, 3.8), (10000.0, 4.0), (12000.0, 3.6),
                         (15000.0, 3.2), (18000.0, 2.6)]
    elif sid == "super-scary":
        master_points = [(26.0, -38.0), (40.0, -30.0), (55.0, -24.0), (70.0, -17.0),
                         (90.0, -14.0), (120.0, -9.0), (180.0, -6.0), (250.0, -3.0),
                         (320.0, -1.4), (450.0, -0.6), (650.0, 0.0), (800.0, 0.4),
                         (1400.0, 1.2), (2000.0, 1.8), (3000.0, 2.4), (4000.0, 2.9),
                         (6000.0, 3.4), (8000.0, 3.6), (10000.0, 3.8), (12000.0, 3.4),
                         (15000.0, 3.0), (18000.0, 2.4)]
    elif sid == "the-incident":
        master_points = [(26.0, -48.0), (40.0, -40.0), (55.0, -32.0), (70.0, -24.0),
                         (90.0, -19.0), (120.0, -14.0), (180.0, -9.0), (250.0, -4.0),
                         (320.0, -2.2), (450.0, -1.4), (650.0, -0.8), (800.0, 0.0),
                         (1400.0, 0.8), (2000.0, 1.2), (3000.0, 1.8), (4000.0, 2.3),
                         (6000.0, 2.8), (8000.0, 3.1), (10000.0, 3.3), (12000.0, 2.9),
                         (15000.0, 2.5), (18000.0, 1.9)]
    left = eq_curve(left, master_points)
    right = eq_curve(right, master_points)
    left = soft_clip(left * 1.30, 1.08) * 0.82
    right = soft_clip(right * 1.30, 1.08) * 0.82
    left = compress(left, threshold_db=-17.0, ratio=2.6, makeup_db=2.6)
    right = compress(right, threshold_db=-17.0, ratio=2.6, makeup_db=2.6)
    crushed = compress(0.5 * (left + right), threshold_db=-24.0, ratio=6.0, makeup_db=9.0)
    left = left + crushed * 0.22
    right = right + crushed * 0.22
    left, right = widen(left, right, amount=1.50 + 0.10 * tier)

    arc = story_level(song, np.arange(n_total, dtype=np.float64) / max(1, n_total - 1))
    left *= arc
    right *= arc
    del arc

    loudness = float(np.sqrt(0.5 * (np.mean(left ** 2) + np.mean(right ** 2))))
    scale = TARGET_RMS / max(loudness, 1e-9)
    left, right = left * scale, right * scale
    left, right = limiter(left, 0.80), limiter(right, 0.80)
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    if peak > 0.76:
        trim = 0.76 / peak
        left, right = left * trim, right * trim
    return left, right


# --------------------------------------------------------------------------- #
# Vocals ----

def vocal_performance(song):
    notes = sorted(L.melodic_onsets(song), key=lambda n: n['time'])
    sections = L.sections(song)
    bounds = [section['time'] / 1000.0 for section in sections] + [L.length(song)]
    beat, step = L.beat(song), L.step(song)
    from bisect import bisect_right
    for i, note in enumerate(notes):
        at = note['time'] / 1000.0
        section = max(0, min(len(sections) - 1, bisect_right(bounds, at + 1e-6) - 1))
        phase = np.clip((at - bounds[section]) / max(.001, bounds[section + 1] - bounds[section]), 0., 1.)
        next_at = notes[i + 1]['time'] / 1000.0 if i + 1 < len(notes) else L.length(song)
        if note['sLen']:
            dur = max(.11, note['sLen'] / 1000.0)
        else:
            desired = step * (2.0 if note['side'] == 'opponent' else 1.8)
            dur = max(.05, min(desired, next_at - at - .065))
        phrase_shape = 0.82 + 0.18 * math.sin(math.pi * phase) ** 1.0
        local_step = (at - L.measure_time(song, note['measure']) / 1000.0) / beat
        accent = 1.12 if abs(local_step - round(local_step)) < 0.03 else 0.88
        if i and notes[i - 1]['side'] == note['side']:
            diff = (note.get('semi') or 0) - (notes[i - 1].get('semi') or 0)
            accent *= 1.08 if diff >= 4 else (0.90 if diff <= -4 else 1.0)
        expression = float(story_level(song, at / L.length(song))) * phrase_shape * accent
        yield note, at, dur, expression


def render_vocals(song):
    total = L.length(song)
    n_total = int(round(total * SR))
    player = empty(total)
    opponent = empty(total)

    for note, at, dur, expression in vocal_performance(song):
        midi = L.note_pitch(song, note["measure"], note["id"], semi=note.get("semi"))
        if note["side"] == "player":
            add_at(player, voice_note(midi, dur), at, expression)
        else:
            add_at(opponent, voice_note(midi - 12, dur, dark=True), at, expression)

    wet = reverb(0.26 * (player + opponent), wet=0.22, size=0.65)
    wet_l, wet_r = haas(wet, 0.018)
    del wet

    left = player * 0.44 + opponent * 0.50 + wet_l * 0.30
    right = player * 0.50 + opponent * 0.44 + wet_r * 0.30
    del player, opponent, wet_l, wet_r

    def fit(x):
        x = dc_block(np.asarray(x[:n_total], dtype=np.float64))
        tail = int(0.24 * SR)
        x[-tail:] *= np.linspace(1.0, 0.0, tail)
        return x

    left, right = fit(left), fit(right)
    vocal_eq = [(110.0, -8.0), (220.0, -2.0), (400.0, 0.0), (900.0, 0.0),
                (2300.0, -1.4), (4800.0, -2.8), (8000.0, -3.8), (12000.0, -6.0), (17000.0, -9.0)]
    left = eq_curve(left, vocal_eq)
    right = eq_curve(right, vocal_eq)
    left = compress(left, threshold_db=-20.0, ratio=2.6, attack_ms=8.0, release_ms=110.0, makeup_db=2.0)
    right = compress(right, threshold_db=-20.0, ratio=2.6, attack_ms=8.0, release_ms=110.0, makeup_db=2.0)
    rms = float(np.sqrt(0.5 * (np.mean(left ** 2) + np.mean(right ** 2))))
    target = TARGET_RMS * 10.0 ** (-2.0 / 20.0)
    scale = target / max(rms, 1e-9)
    left, right = limiter(left * scale, 0.82), limiter(right * scale, 0.82)
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    if peak > 0.78:
        left, right = left * (0.78 / peak), right * (0.78 / peak)
    return left, right


# --------------------------------------------------------------------------- #
# Game-over theme ----

def render_game_over():
    bpm = 76.0
    beat = 60.0 / bpm
    total = 16.0
    n_total = int(total * SR)
    mono = np.zeros(n_total)

    mono += pad_chord([38, 45, 50, 53], total, gain=0.34, cutoff=800.0)[:n_total]
    tritone = sine(38.0 * 1.4142, n_total) * 0.07
    tritone *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.09 * np.arange(n_total) / SR)
    mono += lowpass(tritone, 260.0)

    hb_n = int(0.20 * SR)
    hbt = np.arange(hb_n) / SR
    thump = np.sin(2 * np.pi * np.cumsum(54.0 + 48.0 * np.exp(-hbt * 24.0)) / SR)
    thump *= np.exp(-hbt * 13.0)
    t = 0.0
    while t < total - 0.4:
        add_at(mono, thump, t, 0.34)
        add_at(mono, thump * 0.72, t + 0.34, 0.34)
        t += 4 * beat

    for index, at in enumerate((0.6, 2.4, 4.2, 6.6, 9.0, 11.4, 13.8)):
        midi = (62, 61, 57, 50, 56, 49, 45)[index]
        add_at(mono, music_box(midi, 2.6), at, 0.38)

    mono += highpass(noise(n_total, seed=313), 3000.0) * 0.016
    breath = bandpass(noise(n_total, seed=315), 400.0, 1700.0)
    mono += breath * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)) * 0.024

    mono = reverb(mono, wet=0.46, size=1.0)
    mono = mono[:n_total]
    mono = eq_curve(mono, [(60.0, 3.0), (200.0, 1.4), (900.0, 2.0), (3000.0, -1.4),
                           (9000.0, 1.4), (16000.0, 3.0)])
    mono = normalize(mono, 0.82)
    left, right = widen(mono, mono, amount=1.6)

    n = int(1.7 * SR)
    st = np.arange(n) / SR
    drop = sub_drop(1.6, 210.0, 24.0)
    static = highpass(noise(n, seed=317), 2200.0) * np.exp(-st * 4.2)
    ring = np.sin(2 * np.pi * 190.0 * st) * np.exp(-st * 3.0) * 0.48
    sting = np.zeros(n)
    for piece in (drop, static, ring):
        m = min(len(piece), n)
        sting[:m] += piece[:m] * 0.90
    sting = soft_clip(sting, 2.0)
    sting = eq_curve(sting, [(40.0, 4.0), (200.0, 2.0), (2500.0, 1.4), (12000.0, 2.4)])
    sting = normalize(fade(sting, 0.002, 0.5), 0.90)

    n = int(1.1 * SR)
    rt = np.arange(n) / SR
    whoosh = bandpass(noise(n, seed=319), 700.0, 13000.0) * (rt / rt[-1]) ** 3.2
    whoosh += sine(480.0 * np.exp(-rt * 1.9), n) * 0.34 * (rt / rt[-1]) ** 2.2
    whoosh = normalize(fade(whoosh, 0.01, 0.22), 0.78)
    return (left, right), sting, whoosh


# --------------------------------------------------------------------------- #
# Shared ambient themes + SFX ----

THEME_MELODY = [
    (0.0, 74), (0.42, 69), (0.84, 65), (1.26, 62),
    (2.1, 74), (2.52, 77), (2.94, 81), (3.36, 74),
    (4.2, 70), (4.62, 74), (5.04, 65), (5.46, 62),
    (6.3, 60), (6.72, 64), (7.14, 67), (7.56, 72),
]


def render_theme(scary=False, length=24.0):
    buf = empty(length)
    bar = 8.4
    t = 0.0
    while t < length - 1.0:
        for offset, midi in THEME_MELODY:
            at = t + offset * (1.0 if not scary else 1.10)
            if at >= length:
                continue
            m = midi - (4 if scary else 0)
            add_at(buf, music_box(m), at, 0.54)
            if offset == 0.0:
                add_at(buf, music_box(m - 24, 2.8), at, 0.36)
        t += bar

    buf += highpass(noise(len(buf), seed=41), 5000.0) * (0.016 if not scary else 0.038)

    if scary:
        buf = reverb(buf, wet=0.62, size=1.0)
        warp_n = len(buf)
        warp = 1.0 + 0.024 * np.sin(2 * np.pi * 0.30 * np.arange(warp_n) / SR)
        buf = np.interp(np.cumsum(warp), np.arange(warp_n), buf)
        buf += highpass(noise(len(buf), seed=42), 10000.0) * 0.028
    else:
        buf = reverb(buf, wet=0.46, size=0.9)

    return normalize(fade(buf, in_s=0.6, out_s=1.6), 0.68)


def render_sfx():
    out = {}
    n = int(3.6 * SR)
    t = np.arange(n) / SR
    scare = np.zeros(n)
    hit = bandpass(noise(n, seed=91), 400.0, 12000.0) * np.exp(-t * 2.6)
    screech_f = 2000.0 + 1100.0 * np.sin(2 * np.pi * 7.0 * t)
    tone = np.sin(2 * np.pi * np.cumsum(screech_f) / SR) * exp_decay(n, 0.42) * 0.44
    scare += soft_clip(hit * 2.0 + tone, 2.4)
    for extra in (sub_drop(n / SR, 220.0, 22.0) * 1.0, crash(n / SR, seed=92) * 0.8):
        m = min(len(extra), n)
        scare[:m] += extra[:m]
    out["trollge_jump_scare"] = normalize(fade(scare, in_s=0.002, out_s=1.0), 0.92)

    n = int(2.0 * SR)
    t = np.arange(n) / SR
    sweep_f = 800.0 * np.exp(-t * 1.2) + 90.0
    dist = square(sweep_f, n, duty=0.26) + saw(sweep_f * 0.5, n) * 0.70
    dist = bitcrush(dist, bits=4, hold=10) * (0.30 + 0.70 * np.sin(2 * np.pi * 11.0 * t) ** 2)
    dist += bandpass(noise(n, seed=93), 1600.0, 11000.0) * exp_decay(n, 0.50) * 0.44
    out["trollge_distortion"] = normalize(fade(soft_clip(dist, 2.2), 0.007, 0.30), 0.86)

    n = int(3.0 * SR)
    t = np.arange(n) / SR
    riser = bandpass(noise(n, seed=94), 350.0, 11000.0) * (t / t[-1]) ** 2.5
    low = sine(110.0 * np.exp(t * 0.45), n) * np.exp(-t * 0.8) * 0.60
    out["trollge_invert"] = normalize(fade(soft_clip(riser * 1.6 + low, 1.8), 0.014, 0.60), 0.88)

    n = int(0.15 * SR)
    t = np.arange(n) / SR
    blip = (sine(1050.0, n) * 0.62 + sine(1575.0, n) * 0.38) * np.exp(-t * 65.0)
    env = np.exp(-t * 42.0)
    out["trollge_hit"] = normalize(fade(soft_clip(blip * env, 1.3), 0.001, 0.03), 0.76)

    n = int(0.36 * SR)
    t = np.arange(n) / SR
    miss = (saw(240.0 * np.exp(-t * 0.7), n) * 0.58 + square(180.0, n, duty=0.34) * 0.48) * np.exp(-t * 8.5)
    out["trollge_miss"] = normalize(fade(soft_clip(miss, 2.0), 0.002, 0.12), 0.80)
    return out


def render_note_voices():
    out = {}
    pitches = {"up": 1.30, "down": 0.82, "left": 0.96, "right": 1.16}
    for name, mult in pitches.items():
        n = int(0.28 * SR)
        t = np.arange(n) / SR
        f0 = 250.0 * mult * (1.0 + 0.07 * np.exp(-t * 38.0))
        src = saw(f0, n) * 0.60 + square(f0, n, duty=0.46) * 0.34
        voice = bandpass(src, 600.0, 11000.0) + bandpass(src, 1150.0, 2300.0) * 0.60
        env = adsr(n, attack=0.009, decay=0.055, sustain=0.46, release=0.105)
        out["bf_note_" + name] = normalize(fade(soft_clip(voice * env, 1.25), 0.004, 0.05), 0.66)

        n = int(0.38 * SR)
        t = np.arange(n) / SR
        g0 = 105.0 * mult
        growl = saw(g0, n) * 0.54 + square(g0 * 0.5, n, duty=0.34) * 0.44
        growl *= 1.0 + 0.55 * np.sin(2 * np.pi * 35.0 * t)
        body = bandpass(growl, 250.0, 840.0) + bandpass(growl, 880.0, 1900.0) * 0.40
        env = adsr(n, attack=0.014, decay=0.105, sustain=0.44, release=0.135)
        out["trollge_note_" + name] = normalize(
            fade(soft_clip(body * env, 2.4), 0.004, 0.10), 0.60)
    return out


def render_countdown():
    out = {}
    for index, (name, freq) in enumerate((("intro3", 108.0), ("intro2", 128.0), ("intro1", 154.0))):
        n = int(0.46 * SR)
        t = np.arange(n) / SR
        f = freq * (1.0 + 0.22 * np.exp(-t * 30.0))
        body = sine(f, n) * np.exp(-t * 8.5)
        body += saw(f * 0.5, n) * np.exp(-t * 13.0) * 0.44
        click = bandpass(noise(n, seed=70 + index), 1100.0, 9000.0) * np.exp(-t * 70.0) * 0.60
        out[name] = normalize(fade(soft_clip(body * 1.0 + click, 1.7), 0.001, 0.14), 0.78)

    n = int(1.3 * SR)
    t = np.arange(n) / SR
    blast = sub_drop(n / SR, 230.0, 28.0) * 1.2
    blast[:n] += crash(n / SR, seed=95)[:n] * 0.65
    blast[:n] += screech_fx(n / SR, seed=96)[:n] * 0.44
    blast[:n] += bandpass(noise(n, seed=97), 1700.0, 13000.0) * exp_decay(n, 0.26) * 0.60
    out["introGo"] = normalize(fade(soft_clip(blast, 2.8), 0.002, 0.40), 0.90)
    return out


# --------------------------------------------------------------------------- #
# Mastering helpers ----

def write_song(path, left, right, ceiling=0.93, attempts=4):
    import soundfile as sf
    scale = 1.0
    for attempt in range(attempts):
        write_ogg(path, (left * scale, right * scale))
        data, sr = sf.read(path, always_2d=True)
        peak = max(true_peak(data[:, 0]), true_peak(data[:, 1]))
        if peak <= ceiling:
            if attempt:
                print("     (trimmed %.1f dB on re-encode)" % (20 * np.log10(scale)))
            return peak
        scale *= (ceiling * 0.97) / peak
    return peak


def linked_mix_gain(inst_l, inst_r, voice_l, voice_r, ceiling=0.85, block_ms=10):
    length = len(inst_l)
    if any(len(x) != length for x in (inst_r, voice_l, voice_r)):
        raise ValueError("stem lengths differ")
    block = max(1, int(SR * block_ms / 1000.0))
    count = (length + block - 1) // block
    peaks = np.zeros(count)
    for i in range(count):
        sl = slice(i * block, min(length, (i + 1) * block))
        peaks[i] = max(np.max(np.abs(inst_l[sl] + voice_l[sl])),
                       np.max(np.abs(inst_r[sl] + voice_r[sl])))
    target = np.minimum(1.0, ceiling / np.maximum(peaks, 1e-12))
    target[:-1] = np.minimum(target[:-1], target[1:])
    gains = np.empty(count)
    current = 1.0
    release = np.exp(-block / (0.14 * SR))
    for i in range(count):
        current = min(target[i], 1.0 - (1.0 - current) * release)
        gains[i] = current
    gain = np.repeat(gains, block)[:length]
    return gain


def write_song_pair(inst_path, voice_path, inst_l, inst_r, voice_l, voice_r):
    import soundfile as sf
    gain = linked_mix_gain(inst_l, inst_r, voice_l, voice_r)
    edge = max(1, int(0.005 * SR))
    block = max(1, int(0.01 * SR))
    for i in range(block, len(gain), block):
        before, after = gain[i - 1], gain[i]
        if after < before:
            n = min(edge, i)
            gain[i - n:i] = np.linspace(before, after, n)
        elif after > before:
            n = min(edge, len(gain) - i)
            gain[i:i + n] = np.linspace(before, after, n)

    inst_l *= gain
    inst_r *= gain
    voice_l *= gain
    voice_r *= gain
    del gain
    scale = 1.0
    for attempt in range(4):
        write_ogg(inst_path, (inst_l * scale, inst_r * scale))
        write_ogg(voice_path, (voice_l * scale, voice_r * scale))
        inst, sr = sf.read(inst_path, always_2d=True)
        voice, vr = sf.read(voice_path, always_2d=True)
        if sr != vr or inst.shape != voice.shape:
            raise ValueError("encoded stem formats do not match")
        mix = inst + voice
        peak = max(true_peak(mix[:, 0]), true_peak(mix[:, 1]))
        if peak <= 0.95:
            print("     combined decoded peak estimate %.2f dBFS" % (20 * np.log10(max(peak, 1e-12))))
            return
        scale *= 0.90 / peak
    raise RuntimeError("encoded stem sum exceeds safe peak after retries")


# --------------------------------------------------------------------------- #
# Compatibility wrappers for legacy test API ----

def bass_for(style, midi, dur, tier):
    """Legacy wrapper: bass_for -> reese_bass."""
    return reese_bass(midi_to_hz(midi), int(max(dur, 0.06) * SR), tier)


def sampled_voice_note(midi, dur, dark=False):
    """Legacy wrapper: sampled_voice_note -> voice_note."""
    x = voice_note(midi, dur, dark=dark)
    x[0] = 0.0
    x[-1] = 0.0
    return x


def main():
    os.makedirs(SFX_DIR, exist_ok=True)

    for song in L.SONGS:
        song_dir = os.path.join(MOD, "songs", song["id"], "song")
        os.makedirs(song_dir, exist_ok=True)
        print("Rendering %-14s (%0.1fs, %0.0f BPM, scare %d/10, %s)..."
              % (song["display"], L.length(song), song["bpm"], song["scare"], SONG_STYLES[song["id"]]))
        left, right = render_song(song)
        path = os.path.join(song_dir, "Inst.ogg")
        vleft, vright = render_vocals(song)
        vpath = os.path.join(song_dir, "Voices.ogg")
        write_song_pair(path, vpath, left, right, vleft, vright)
        print("  -> %-44s %6.1f KB" % (os.path.relpath(path, ROOT), os.path.getsize(path) / 1024))
        del left, right, vleft, vright
        print("  -> %-44s %6.1f KB" % (os.path.relpath(vpath, ROOT), os.path.getsize(vpath) / 1024))

    print("Rendering the game-over theme...")
    os.makedirs(MUSIC_DIR, exist_ok=True)
    (go_l, go_r), sting, whoosh = render_game_over()
    go_path = os.path.join(MUSIC_DIR, "gameOver.ogg")
    write_song(go_path, go_l, go_r)
    print("  -> %-44s %6.1f KB" % (os.path.relpath(go_path, ROOT), os.path.getsize(go_path) / 1024))
    with open(os.path.join(MUSIC_DIR, "gameOver.ini"), "w", encoding="utf-8") as handle:
        handle.write("; SONG INFO such as BPM, etc...\nBPM = 76\n")
    for name, buf in (("gameOverSFX", sting), ("gameOverEnd", whoosh)):
        p = os.path.join(SFX_DIR, name + ".ogg")
        write_ogg(p, (np.clip(buf * 0.9, -1.0, 1.0), np.clip(buf * 0.9, -1.0, 1.0)))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))

    print("Rendering ambient themes...")
    for name, scary in (("trollge_theme", False), ("trollge_theme_scary", True)):
        buf = render_theme(scary=scary)
        p = os.path.join(SFX_DIR, name + ".ogg")
        write_ogg(p, (buf, buf))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))

    menu = os.path.join(MUSIC_DIR, "trollgeMenu.ogg")
    shutil.copyfile(os.path.join(SFX_DIR, "trollge_theme.ogg"), menu)
    print("  -> %-44s %6.1f KB" % (os.path.relpath(menu, ROOT), os.path.getsize(menu) / 1024))

    print("Rendering countdown hits...")
    for name, buf in render_countdown().items():
        p = os.path.join(SFX_DIR, name + ".ogg")
        write_ogg(p, (np.clip(buf * 0.8, -1.0, 1.0), np.clip(buf * 0.8, -1.0, 1.0)))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))

    print("Rendering SFX...")
    for name, buf in render_sfx().items():
        p = os.path.join(SFX_DIR, name + ".ogg")
        buf = np.clip(buf * 0.72, -1.0, 1.0)
        write_ogg(p, (buf, buf))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))

    print("Rendering note-hit voices...")
    for name, buf in render_note_voices().items():
        p = os.path.join(SFX_DIR, name + ".ogg")
        buf = np.clip(buf * 0.72, -1.0, 1.0)
        write_ogg(p, (buf, buf))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))


if __name__ == "__main__":
    main()