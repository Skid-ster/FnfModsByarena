#!/usr/bin/env python3
"""
Renders every audio asset of the Super Scary Trollge mod.

Per song (songs/<id>/song/Inst.ogg):
    the instrumental, rebuilt as a real dark electronic piece -- each song its
    own sub-genre (dark bounce / dark trap / dark glitch / industrial / dark
    ambient industrial) with Reese bass, distorted saw leads, 808 slides,
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
from functools import lru_cache
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
# Dark electronic instrument library
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


def reese_bass(f, n, tier, slide_to=None):
    t = np.arange(n) / SR
    detune = 0.012 + 0.006 * tier
    if slide_to is not None:
        f_curve = f + (slide_to - f) * (1.0 - np.exp(-t * 12.0))
    else:
        f_curve = np.full(n, f)
    voice = (
        saw(f_curve * (1.0 - detune), n) * 0.45
        + saw(f_curve * (1.0 + detune), n) * 0.45
    )
    voice += sine(f_curve, n) * 0.10
    cutoff = 550.0 + 900.0 * tier
    dark = lowpass(voice, cutoff * 0.55)
    bright = lowpass(voice, cutoff * 1.6)
    open_env = np.clip(1.0 - np.exp(-t * 20.0), 0.0, 1.0)
    out = dark * (1.0 - open_env) + bright * open_env
    env = _env(n, 0.010, 0.15, 0.70, min(0.30, n / SR * 0.5))
    out = out * env
    out = highpass(out, 40.0)
    drive = 1.0 + 0.35 * tier
    return soft_clip(out * drive, 1.0 + 0.5 * tier)


def slide_808(f0, f1, n, tier):
    t = np.arange(n) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 10.0)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    body += np.sin(2 * np.pi * np.cumsum(freq * 2.0) / SR) * 0.12
    env = _env(n, 0.008, 0.25, 0.75, min(0.40, n / SR * 0.5))
    out = body * env
    drive = 1.2 + 0.5 * tier
    return soft_clip(lowpass(out, 350.0 + 300.0 * tier), drive)


def sub_hit(f, n):
    t = np.arange(n) / SR
    freq = f * np.exp(-t * 8.0)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 10.0)


def dark_saw_lead(f, n, tier, detune=0.012):
    t = np.arange(n) / SR
    voice = (
        saw(f * (1.0 - detune), n) * 0.40
        + saw(f, n) * 0.50
        + saw(f * (1.0 + detune), n) * 0.35
        + saw(f * 0.5, n) * 0.14
    )
    cutoff = 1800.0 + 900.0 * tier
    dark = lowpass(voice, cutoff * 0.55)
    bright = lowpass(voice, cutoff * 1.9)
    open_env = np.clip(1.0 - np.exp(-t * 24.0), 0.0, 1.0)
    out = dark * (1.0 - open_env) + bright * open_env
    env = _env(n, 0.006, 0.10, 0.55, 0.12)
    out = out * env
    drive = 1.5 + 0.6 * tier
    return soft_clip(out, drive)


def fm_bell(f, n):
    t = np.arange(n) / SR
    body = np.zeros(n)
    for mult, amp, decay in ((1.0, 1.0, 2.5), (2.01, 0.32, 4.5), (3.03, 0.14, 7.0)):
        body += np.sin(2 * np.pi * f * mult * t) * amp * np.exp(-t * decay)
    return body * 0.55


def dark_pad_voice(f, n, tier):
    t = np.arange(n) / SR
    voice = (
        saw(f * 0.995, n) * 0.50
        + saw(f, n) * 0.65
        + saw(f * 1.005, n) * 0.50
        + saw(f * 2.0, n) * 0.12
    )
    breathe = 1.0 + 0.25 * np.sin(2 * np.pi * 0.10 * t) + 0.12 * np.sin(2 * np.pi * 0.31 * t)
    cutoff = 900.0 + 1100.0 * tier
    dark = lowpass(voice, cutoff * 0.5)
    bright = lowpass(voice, cutoff * 1.3)
    weight = np.clip(0.45 + 0.45 * np.sin(2 * np.pi * 0.10 * t), 0.0, 1.0)
    out = dark * (1.0 - weight) + bright * weight
    env = _env(n, n / SR * 0.35, n / SR * 0.15, 0.72, n / SR * 0.30)
    return out * env * breathe * 0.08


def dark_kick(dur, style, tier):
    n = int(dur * SR)
    t = np.arange(n) / SR
    start_hz, end_hz = (70.0, 48.0) if style != "trap" else (55.0, 40.0)
    freq = end_hz + (start_hz - end_hz) * np.exp(-t * 24.0)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    attack = int(0.004 * SR)
    env = np.exp(-t * 6.0)
    env[:attack] *= np.linspace(0.0, 1.0, attack) ** 2
    click = bandpass(noise(n, seed=23), 2500.0, 6000.0) * np.exp(-t * 80.0) * 0.10
    kick = body * env + click
    if style == "industrial":
        metal = bandpass(noise(n, seed=22), 400.0, 2600.0) * np.exp(-t * 45.0) * 0.28
        kick = kick + metal
    elif style == "trap":
        kick = kick * np.exp(-t * 2.0)
    elif style == "finale":
        kick += np.sin(2 * np.pi * np.cumsum(freq * 1.5) / SR) * np.exp(-t * 8.0) * 0.20
    return soft_clip(kick * (1.0 + 0.25 * tier), 1.15 + 0.2 * tier)


def dark_snare(dur, style, tier, seed=12):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tune = 185.0 if style == "trap" else (210.0 if style == "industrial" else 200.0)
    tone = (np.sin(2 * np.pi * tune * t) * 0.55
            + np.sin(2 * np.pi * tune * 1.62 * t) * 0.22) * np.exp(-t * 26.0)
    if style == "industrial":
        rattle = bandpass(noise(n, seed=seed), 1100.0, 6000.0) * np.exp(-t * 14.0) * 0.65
    elif style == "glitch":
        gate = (np.sin(2 * np.pi * 34.0 * t) > -0.2).astype(float)
        rattle = bandpass(noise(n, seed=seed), 1400.0, 6000.0) * np.exp(-t * 30.0) * gate * 0.55
    else:
        rattle = bandpass(noise(n, seed=seed), 900.0, 6200.0) * np.exp(-t * 15.0) * 0.62
    onset = int(0.003 * SR)
    rattle[:onset] *= np.linspace(0.0, 1.0, onset)
    return tone * 0.7 + rattle * 0.66


def dark_hat(dur, open_, style, seed=13):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * (8.0 if open_ else 50.0))
    tune = 1.0 if style == "trap" else (0.86 if style == "industrial" else 1.0)
    body = bandpass(noise(n, seed=seed), 5200.0 * tune, 13500.0 * tune)
    body = eq_curve(body, [(2000.0, -3.0), (6000.0, 0.5), (10000.0, 2.5), (14000.0, -1.0)])
    onset = int(0.0015 * SR)
    body[:onset] *= np.linspace(0.0, 1.0, onset)
    return body * env * 0.34


def metal_hit(dur, seed=40):
    n = int(dur * SR)
    t = np.arange(n) / SR
    partials = [(320.0, 0.5), (510.0, 0.35), (890.0, 0.25), (1400.0, 0.14), (2100.0, 0.08)]
    out = sum(np.sin(2 * np.pi * h * t) * a * np.exp(-t * (3.0 + i)) for i, (h, a) in enumerate(partials))
    noise_bit = bandpass(noise(n, seed=seed), 2000.0, 9000.0) * np.exp(-t * 25.0) * 0.35
    return soft_clip((out + noise_bit) * 1.4, 1.3)


def dread_drone(root_hz, n, tier):
    t = np.arange(n) / SR
    beat_hz = 0.55 + 0.18 * tier
    drone = (sine(root_hz, n) * 0.55 + sine(root_hz * 1.0035, n) * 0.45)
    drone_l = drone * (0.72 + 0.28 * np.sin(2 * np.pi * beat_hz * t))
    drone_r = drone * (0.72 + 0.28 * np.sin(2 * np.pi * beat_hz * t + 1.9))
    if tier >= 4:
        tritone = root_hz * (2 ** (6 / 12.0))
        drone_l = drone_l + sine(tritone, n) * 0.22
        drone_r = drone_r + sine(tritone * 1.002, n) * 0.22
    gain = 0.075 * max(0.0, (tier - 1) / 4.0)
    return (lowpass(drone_l, 120.0) * gain, lowpass(drone_r, 120.0) * gain)


def breath_layer(n, tier):
    breath = bandpass(noise(n, seed=7 + tier), 700.0, 2600.0)
    t = np.arange(n) / SR
    swing = 0.5 + 0.5 * np.sin(2 * np.pi * (0.11 + 0.03 * tier) * t - 0.6)
    swing = swing ** 3
    return breath * swing * (0.05 * max(0.0, (tier - 1) / 4.0))


def heartbeat(bpm, total, tier):
    beat_s = 60.0 / bpm
    hb_n = int(0.16 * SR)
    hbt = np.arange(hb_n) / SR
    thump = np.sin(2 * np.pi * np.cumsum(58.0 + 40.0 * np.exp(-hbt * 30.0)) / SR)
    thump *= np.exp(-hbt * 16.0)
    buf = empty(total)
    bar = 4 * beat_s
    t = 0.0
    gain = 0.10 * max(0.0, (tier - 3) / 2.0)
    while t < total - 0.5:
        add_at(buf, thump, t, gain)
        add_at(buf, thump * 0.7, t + 0.30, gain)
        t += bar
    return buf


def whispers(n, tier):
    w = highpass(noise(n, seed=67), 1800.0)
    t = np.arange(n) / SR
    wl = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t)
    return w * wl * 0.018


def choir_chord(midis, n, tier):
    out = np.zeros(n)
    for midi in midis:
        f = midi_to_hz(midi)
        out += dark_pad_voice(f, n, tier) * 1.4
    return out


# --------------------------------------------------------------------------- #
# FX
# --------------------------------------------------------------------------- #

def riser(dur, from_hz, to_hz, seed=74):
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = from_hz * (to_hz / from_hz) ** (t / dur)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    noise_env = bandpass(noise(n, seed=seed), 300.0, 8000.0) * (t / dur) ** 2
    return soft_clip((tone * 0.5 + noise_env * 0.5) * 1.4, 1.5)


def sub_drop(dur, f0, f1):
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 2.6)
    env = np.exp(-t * 1.3)
    return soft_clip(np.sin(2 * np.pi * np.cumsum(freq) / SR) * env, 1.4)


def crash(dur, seed=14):
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = bandpass(noise(n, seed=seed), 2400.0, 13000.0)
    body = eq_curve(body, [(3000.0, -1.0), (8000.0, 1.0), (14000.0, -2.0)])
    return body * np.exp(-t * 2.2) * 0.42


def screech_fx(dur, seed=51):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 1500.0 + 700.0 * np.sin(2 * np.pi * 5.5 * t) + 260.0 * np.sin(2 * np.pi * 0.7 * t)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    tone += np.sin(2 * np.pi * np.cumsum(f * 1.51) / SR) * 0.4
    return soft_clip(tone * exp_decay(n, dur * 0.35), 2.0) * 0.5


def reverse_signal(x):
    return x[::-1].copy()


# --------------------------------------------------------------------------- #
# Vocals (ported from previous design)
# --------------------------------------------------------------------------- #

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
    n = max(int(0.16 * SR), int((dur + 0.09) * SR))
    t = np.arange(n) / SR
    f0 = midi_to_hz(midi)
    glide = 1.0 - scoop * np.exp(-t * 22.0)
    rate = vibrato_hz if vibrato_hz else (5.1 if dark else 5.6)
    depth = vibrato * (0.55 if dark else 1.0)
    ramp = np.clip((t - 0.11) / 0.30, 0.0, 1.0)
    vibr = 1.0 + depth * np.sin(2 * np.pi * rate * t + 0.4) * ramp
    inst = f0 * glide * vibr
    phase = 2 * np.pi * np.cumsum(inst) / SR
    src = np.zeros(n)
    h = 1
    while f0 * h < min(7600.0 if dark else 9500.0, SR * 0.45):
        amp = (1.0 / (h ** (1.35 if dark else 1.15))) * (1.0 + 0.16 * (h % 2))
        src += np.sin(phase * h + 0.35 * h) * amp
        h += 1
    if dark and growl > 0:
        src += np.sin(phase * 0.5) * 0.35 * growl
        src = soft_clip(src * (1.0 + 0.5 * growl), 1.35)
    if vowel is None:
        vowel = "oh" if dark else "ah"
    shift = TROLLGE_SHIFT if dark else PLAYER_SHIFT
    formants = tuple((hz * shift, bw * shift, gain) for hz, bw, gain in VOWELS[vowel])
    out = formant_bank(src, formants)
    n_c = int(0.028 * SR)
    out[:n_c] += bandpass(noise(n_c, seed=seed % 251), 2600.0, 7600.0) * (0.16 if dark else 0.22)
    attack = int((0.030 if dark else 0.018) * SR)
    release = int(0.11 * SR)
    sustain_len = max(1, n - attack - release)
    env = np.ones(n)
    env[:attack] = np.linspace(0.0, 1.0, attack) ** 1.4
    env[attack:attack + sustain_len] = 1.0
    env[attack + sustain_len:] = np.linspace(1.0, 0.0, n - attack - sustain_len) ** 1.6
    body = np.ones(n)
    arc = np.clip(np.arange(n) / max(1.0, 0.28 * SR), 0.0, 1.0)
    body *= 0.82 + 0.18 * arc
    out *= env * body
    out = highpass(out, 85.0)
    return out * (0.5 if dark else 0.55)


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


def pad_chord(midis, dur, gain=0.075, cutoff=1500.0, seed=0):
    n = int(dur * SR)
    out = np.zeros(n)
    for i, midi in enumerate(midis):
        f = midi_to_hz(midi)
        for mult, amp, phase in ((0.9965, 0.55, 0.3), (1.0, 0.70, 1.1), (1.0035, 0.55, 2.4)):
            out += saw(f * mult, n, phase0=phase + i) * amp
        out += sine(f * 2.0, n) * 0.12
    t = np.arange(n) / SR
    breathe = 1.0 + 0.22 * np.sin(2 * np.pi * 0.13 * t + seed) + 0.10 * np.sin(2 * np.pi * 0.41 * t)
    dark = lowpass(out, max(300.0, cutoff * 0.55))
    bright = lowpass(out, cutoff * 1.25)
    weight = np.clip(0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * t + seed), 0.0, 1.0)
    out = dark * (1.0 - weight) + bright * weight
    env = adsr(n, attack=dur * 0.30, decay=dur * 0.12, sustain=0.72, release=dur * 0.34)
    out *= env * breathe
    out = highpass(out, 140.0).copy()
    return out * gain / max(1, len(midis)) * 0.9


def music_box(midi, dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = midi_to_hz(midi)
    partials = [(1.0, 1.0, 2.1), (2.76, 0.34, 4.0), (4.07, 0.16, 7.0), (5.43, 0.09, 11.0)]
    out = np.zeros(n)
    for mult, amp, decay in partials:
        out += np.sin(2 * np.pi * f * mult * t) * amp * np.exp(-t * decay)
    return out * 0.6


# --------------------------------------------------------------------------- #
# Piano + patterns
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=96)
def _piano_pitch(midi):
    import soundfile as sf
    samples = ((48, 'C3'), (55, 'G3'), (60, 'C4'), (67, 'G4'),
               (72, 'C5'), (79, 'G5'), (84, 'C6'))
    root, name = min(samples, key=lambda item: abs(item[0] - midi))
    raw, sr = sf.read(os.path.join(ROOT, 'audio_src', 'piano', name + '.ogg'), dtype='float64')
    if sr != 48000 or raw.ndim != 1:
        raise ValueError('unexpected piano source format')
    level = np.sqrt(np.mean(raw[:sr // 2] ** 2))
    raw = raw / max(level, 1e-8) * .10
    ratio = 2.0 ** ((midi - root) / 12.0)
    if ratio > 1:
        raw = lowpass(raw, min(17000., .43 * SR / ratio), sr=sr)
    count = min(int(len(raw) / (ratio * sr / SR)), int(3.5 * SR))
    positions = np.arange(count) * ratio * sr / SR
    return np.interp(positions, np.arange(len(raw)), raw)


def piano_note(midi, duration):
    sample = _piano_pitch(int(midi))
    n = min(len(sample), max(1, int((duration + .15) * SR)))
    result = sample[:n].copy()
    attack = min(n // 3, int(.004 * SR))
    release = min(n // 3, int(.15 * SR))
    if attack:
        result[:attack] *= np.linspace(0., 1., attack)
    if release:
        result[-release:] *= np.linspace(1., 0., release)
    return result


PIANO_PATTERNS = {
    'trolling': ((0, 0, 0, 1.7, .80), (1.5, 1, 0, 1.2, .55), (3, 2, 0, 1.4, .66)),
    'getting-dark': ((0, 0, 0, 2.0, .78), (2, 2, 0, 1.7, .55), (3.5, 1, 0, 1.0, .45)),
    'dont-look-back': ((0, 0, 0, 1.4, .75), (1.25, 2, 0, 1.0, .46), (2.5, 1, 0, 1.2, .58)),
    'super-scary': ((0, 0, 0, 1.5, .78), (1.25, 2, 0, 1.0, .52), (2.75, 1, 0, 1.1, .53)),
    'the-incident': ((0, 0, 0, 2.1, .86), (1, 2, 0, 1.7, .53), (2.5, 1, 0, 1.5, .65)),
}

ANSWER_MOTIFS = {
    'trolling': ((0.0, 0), (.45, 4), (1.0, 0)),
    'getting-dark': ((0.0, 0), (.55, -3), (1.05, -5)),
    'dont-look-back': ((0.0, 0), (.38, 6), (.90, 3)),
    'super-scary': ((0.0, 0), (.35, -5), (.95, 2)),
    'the-incident': ((0.0, 0), (.60, 3), (1.15, -2)),
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
            variation = .9 + .1 * ((bar * 3 + i * 7) % 5) / 4.0
            level = velocity * variation * (1.15 if role in ('intro', 'break') else .78)
            yield (L.measure_time(song, bar) / 1000.0 + offset * beat,
                   midi, length * beat, level)


def piano_answers(song):
    notes = list(vocal_performance(song))
    beat = L.beat(song)
    motif = ANSWER_MOTIFS[song['id']]
    last_bar = -100
    for (note, at, dur, _), (following, next_at, _, _) in zip(notes, notes[1:]):
        bar = note['measure']
        if bar - last_bar < 4:
            continue
        start = at + dur + .05 + .12 * beat
        end = next_at - .12 * beat
        last_end = start + (motif[-1][0] + .32) * beat + .15
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
            result.append((when, pitch, .32 * beat, (.60, .46, .52)[index]))
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
    points = [(0.0, .88 if part == 'drums' else .92)]
    for i, sec in enumerate(sections):
        start = sec['time'] / 1000.0
        for bar in range(sec['measures']):
            shape = (.82, .96, .89, 1.0)[bar % 4]
            if sec['role'] in ('drop', 'finale'):
                shape = .9 + .1 * shape
            if part == 'bass':
                shape = .55 + .45 * shape
            points.append((start + bar * measure, shape))
        if i + 1 < len(sections):
            nxt = sections[i + 1]
            boundary = nxt['time'] / 1000.0
            if nxt['role'] in ('drop', 'finale') and sec['role'] not in ('intro', 'break'):
                depth = .40 if part == 'drums' else .72
                points.append((boundary - .65 * beat, 1.0))
                points.append((boundary - .22 * beat, depth))
    points.append((total, .92))
    return sorted(points)


def shape_rhythm(song, signals, part):
    points = rhythm_landmarks(song, part)
    n = len(signals[0])
    curve = np.interp(np.arange(n) / SR,
                      [time for time, _ in points], [level for _, level in points])
    for signal in signals:
        signal *= curve


# --------------------------------------------------------------------------- #
# Bass & drum patterns
# --------------------------------------------------------------------------- #

def bass_pattern(style, role, beat, tier):
    if style == "dark_trap":
        if role == "break":
            return [(0.0, -12, 2.2)]
        if role == "intro":
            return [(0.0, -12, 3.6)]
        return [(0.0, -12, 1.35), (1.5, 0, 0.9), (2.5, -12, 0.75), (3.25, 0, 0.7)]
    if style == "dark_glitch":
        if role == "break":
            return [(0.0, -12, 1.2)]
        if role == "intro":
            return [(0.0, -12, 3.0)]
        if role in ("finale", "drop"):
            return [(i * 0.25, (-12 if i % 4 == 0 else (12 if i % 8 == 5 else 0)), 0.25 * (1.0 if i % 2 else 0.7)) for i in range(16)]
        return [(i * 0.25, (-12 if i % 8 == 0 else (12 if i % 8 == 6 else 0)), 0.25 * 0.9) for i in range(8)]
    if style == "industrial":
        if role == "break":
            return [(0.0, -12, 2.0), (2.0, 0, 1.6)]
        if role == "intro":
            return [(0.0, -12, 3.6)]
        return [(i * 0.5, (-12 if i % 4 == 0 else (7 if i == 5 else 0)), 0.5 * (0.95 if i % 2 else 1.06)) for i in range(8)]
    if style == "dark_ambient":
        if role == "break":
            return [(0.0, -12, 1.8)]
        if role == "intro":
            return [(0.0, -12, 3.4)]
        return [(i * 0.5, -12 if i % 4 == 0 else 0, 0.5 * (0.92 if i % 2 else 1.05)) for i in range(8)]
    if role == "break":
        return [(0.0, -12, 1.8)]
    if role == "drop":
        return [(0.0, 0, 0.42), (0.5, 0, 0.30), (0.75, 0, 0.20), (1.0, -12, 0.40),
                (1.5, 0, 0.30), (1.75, 0, 0.20), (2.0, 0, 0.42), (2.5, -12, 0.28),
                (3.0, 0, 0.42), (3.5, 0, 0.30)]
    if role == "intro":
        return [(0.0, -12, 3.4)]
    return [(i * 0.5, -12 if i % 4 == 0 else 0, 0.5 * (0.92 if i % 2 else 1.05)) for i in range(8)]


def drum_pattern(style, role, t0, beat, tier, kick_s, snare_s, hat_l, hat_r, fx_s, m):
    intensity = ROLE_GAIN[role]
    if role in ("verse", "build", "drop", "finale"):
        if style == "dark_trap":
            add_at(kick_s, dark_kick(0.42, style, tier), t0, 0.95 * intensity)
            add_at(kick_s, dark_kick(0.42, style, tier), t0 + 2.75 * beat, 0.7 * intensity)
            add_at(snare_s, dark_snare(0.36, style, tier, 71), t0 + 2 * beat, 0.55 * intensity)
            for step in range(8):
                at = t0 + step * beat / 2.0
                add_at(hat_l if step % 2 else hat_r, dark_hat(0.045, False, style, 40 + step), at, 0.30 * intensity)
                if step % 2 == 1 and (role in ("drop", "finale") or tier >= 2):
                    add_at(hat_r, dark_hat(0.04, False, style, 60 + step), at + beat / 4.0, 0.16 * intensity)
                    add_at(hat_l, dark_hat(0.04, False, style, 80 + step), at + beat * 0.5, 0.14 * intensity)
                    add_at(hat_l, dark_hat(0.13, True, style, 90 + step), at + beat * 0.66, 0.12 * intensity)
        elif style == "dark_glitch":
            add_at(kick_s, dark_kick(0.24, style, tier), t0, 0.95 * intensity)
            add_at(kick_s, dark_kick(0.24, style, tier), t0 + 1.75 * beat, 0.72 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.24, style, tier), t0 + 2.5 * beat, 0.62 * intensity)
                add_at(kick_s, dark_kick(0.24, style, tier), t0 + 3.25 * beat, 0.55 * intensity)
            add_at(snare_s, dark_snare(0.30, style, tier, 50 + m), t0 + 2 * beat, 0.62 * intensity)
            for q in range(4):
                add_at(snare_s, dark_snare(0.15, style, tier, 70 + q),
                       t0 + 3 * beat + q * beat / 8.0, (0.34 - 0.05 * q) * intensity)
            for q in range(8):
                at = t0 + q * beat / 2.0
                if q % 3 == 2:
                    continue
                add_at(hat_l if q % 2 else hat_r, dark_hat(0.04, q == 7, style, 120 + q), at, 0.24 * intensity)
                if q % 2 and role in ("drop", "finale"):
                    add_at(hat_r, dark_hat(0.04, False, style, 140 + q), at + beat / 4.0, 0.13 * intensity)
        elif style == "industrial":
            for b in range(4):
                at = t0 + b * beat
                add_at(kick_s, dark_kick(0.34, style, tier), at, 0.92 * intensity)
                if b in (1, 3):
                    add_at(snare_s, dark_snare(0.36, style, tier, 12 + b), at, 0.5 * intensity)
                    add_at(snare_s, dark_snare(0.18, style, tier, 30 + b), at + beat / 2.0, 0.18 * intensity)
                for q in range(4):
                    add_at(hat_l if (q + b) % 2 else hat_r, dark_hat(0.06, q == 3, style, 100 + q + b * 4), at + q * beat / 4.0, 0.19 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.34, style, tier), t0 + 3.5 * beat, 0.55 * intensity)
        elif style == "dark_ambient":
            for b in range(4):
                at = t0 + b * beat
                if b in (0, 2) or (role in ("drop", "finale") and b == 3 and tier >= 2):
                    add_at(kick_s, dark_kick(0.42, style, tier), at, 0.95 * intensity)
                if b in (1, 3):
                    add_at(snare_s, dark_snare(0.34, style, tier, 12 + b), at, 0.55 * intensity)
                add_at(hat_l, dark_hat(0.07, False, style, 13 + b), at, 0.26 * intensity)
                add_at(hat_r, dark_hat(0.07, True, style, 14 + b), at + beat / 2.0, 0.20 * intensity)
                air_n = int(0.05 * SR)
                air_t = np.arange(air_n) / SR
                air = bandpass(noise(air_n, seed=90 + b), 9000.0, 16000.0) * np.exp(-air_t * 55.0)
                add_at(hat_l if b % 2 == 0 else hat_r, air, at, 0.17 * intensity)
                add_at(hat_r if b % 2 == 0 else hat_l, air, at + beat / 2.0, 0.14 * intensity)
                if role in ("drop", "finale") or tier >= 3:
                    add_at(hat_l, dark_hat(0.04, False, style, 15 + b), at + beat / 4.0, 0.12 * intensity)
                    add_at(hat_r, dark_hat(0.04, False, style, 19 + b), at + 3 * beat / 4.0, 0.12 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.42, style, tier), t0 + 3.5 * beat, 0.6 * intensity)
        else:  # dark_bounce
            for b in range(4):
                at = t0 + b * beat
                if b in (0, 2) or (role in ("drop", "finale") and b == 3 and tier >= 2):
                    add_at(kick_s, dark_kick(0.42, style, tier), at, 0.95 * intensity)
                if b in (1, 3):
                    add_at(snare_s, dark_snare(0.34, style, tier, 12 + b), at, 0.55 * intensity)
                add_at(hat_l, dark_hat(0.07, False, style, 13 + b), at, 0.26 * intensity)
                add_at(hat_r, dark_hat(0.07, True, style, 14 + b), at + beat / 2.0, 0.20 * intensity)
                air_n = int(0.05 * SR)
                air_t = np.arange(air_n) / SR
                air = bandpass(noise(air_n, seed=90 + b), 9000.0, 16000.0) * np.exp(-air_t * 55.0)
                add_at(hat_l if b % 2 == 0 else hat_r, air, at, 0.17 * intensity)
                add_at(hat_r if b % 2 == 0 else hat_l, air, at + beat / 2.0, 0.14 * intensity)
                if role in ("drop", "finale") or tier >= 3:
                    add_at(hat_l, dark_hat(0.04, False, style, 15 + b), at + beat / 4.0, 0.12 * intensity)
                    add_at(hat_r, dark_hat(0.04, False, style, 19 + b), at + 3 * beat / 4.0, 0.12 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, dark_kick(0.42, style, tier), t0 + 3.5 * beat, 0.6 * intensity)
    elif role == "break":
        add_at(kick_s, dark_kick(0.42, style, tier), t0, 0.7)
        add_at(snare_s, dark_snare(0.34, style, tier, 61), t0 + 2 * beat, 0.4)
        for b in range(4):
            add_at(hat_r, dark_hat(0.04, True, style, 20 + b), t0 + b * beat, 0.12)
    else:
        add_at(kick_s, dark_kick(0.42, style, tier), t0, 0.6)
        for b in range(4):
            add_at(hat_r, dark_hat(0.04, False, style, 30 + b), t0 + b * beat + beat / 2.0, 0.12)

    if role in ("verse", "build", "drop", "finale"):
        air_n = int(0.045 * SR)
        air = bandpass(noise(air_n, seed=300 + m), 10000.0, 16500.0) * exp_decay(air_n, 0.03)
        for b in range(2, 5):
            gain = 0.20 if style == "dark_trap" else (0.16 if style == "industrial" else 0.14)
            add_at(hat_l if b % 2 == 0 else hat_r, air, t0 + (b - 1) * beat + beat * 0.5, gain * intensity)

    if style == "dark_glitch" and role in ("verse", "build", "drop", "finale") and m % 2 == 0:
        g_n = int(beat * 0.9 * SR)
        gt = np.arange(g_n) / SR
        chunk = bandpass(noise(g_n, seed=230 + m), 600.0, 5200.0)
        chunk = bitcrush(chunk * np.exp(-gt * 8.0), bits=4, hold=11)
        add_at(fx_s, chunk, t0 + 3 * beat + beat * 0.25, 0.11)
    elif style == "dark_ambient" and role in ("drop", "finale"):
        g_n = int(1.6 * SR)
        gt = np.arange(g_n) / SR
        gong = sum(np.sin(2 * np.pi * hz * gt) * amp
                   for hz, amp in ((73.4, 0.30), (110.0, 0.16), (146.8, 0.10),
                                   (221.0, 0.06), (293.6, 0.04)))
        gong *= np.exp(-gt * 3.2)
        add_at(fx_s, gong, t0, 0.16)
    elif style == "industrial" and role in ("drop", "finale"):
        add_at(fx_s, bandpass(noise(int(0.4 * SR), seed=200 + m), 900.0, 9000.0)
               * exp_decay(int(0.4 * SR), 0.12), t0 + 3.75 * beat, 0.10)
    elif style == "dark_trap" and role in ("build", "drop") and m % 4 == 0:
        rev_n = int(beat * 1.2 * SR)
        rev = crash(beat * 1.2, seed=210 + m)[::-1][:rev_n]
        add_at(fx_s, rev, t0 + 4 * beat - beat * 1.2, 0.16)
    elif style == "dark_bounce" and role == "verse" and m % 2 == 1:
        blk_n = int(0.06 * SR)
        blk = np.sin(2 * np.pi * 1180.0 * np.arange(blk_n) / SR) * exp_decay(blk_n, 0.02)
        add_at(hat_r, blk, t0 + 2.5 * beat, 0.10)


def drum_fill(at, length, style, tier, snare_s, fx_s, seed=40, loudness=1.0):
    hits = 8
    for i in range(hits):
        when = at + length * i / hits
        if style == "dark_trap":
            add_at(snare_s, dark_snare(0.15, style, tier, seed + i), when, 0.10 * loudness)
        else:
            add_at(snare_s, dark_snare(0.20, style, tier, seed + i), when,
                   (0.16 + 0.22 * i / hits) * loudness)
    add_at(fx_s, crash(1.8, seed=80), at + length, 0.20 + 0.05 * tier)


def ghost_snares(style, role, t0, beat, tier, snare_s, hat_r, m, intensity):
    if role not in ("verse", "build", "drop", "finale"):
        return
    for beat_index in (1, 3):
        for fraction in (0.25, 0.75):
            if role == "verse" and fraction == 0.25:
                continue
            add_at(snare_s, dark_snare(0.12, style, tier, 300 + m * 4 + beat_index),
                   t0 + beat_index * beat + fraction * beat,
                   0.09 * intensity * 0.95)
    if m % 2 == 1:
        add_at(hat_r, dark_hat(0.13, True, style, 400 + m), t0 + 3.5 * beat, 0.16 * intensity)


# --------------------------------------------------------------------------- #
# Horror & FX per tier
# --------------------------------------------------------------------------- #

def scripted_stinger(fx_s, func, at, tier, song):
    if func == "trollgeJumpScare":
        add_at(fx_s, sub_drop(2.4, 170.0, 28.0), at - 0.05, 0.7)
        add_at(fx_s, crash(2.2, seed=71), at, 0.5)
        add_at(fx_s, screech_fx(1.6), at, 0.35)
        blast_n = int(0.8 * SR)
        blast = bandpass(noise(blast_n, seed=72), 500.0, 9000.0) * exp_decay(blast_n, 0.2)
        add_at(fx_s, soft_clip(blast, 2.0), at, 0.35)
    elif func == "trollgeScreenShake":
        add_at(fx_s, crash(1.6, seed=73), at, 0.4)
        add_at(fx_s, sub_drop(1.8, 140.0, 32.0), at, 0.4)
    elif func == "trollgeDistort":
        glitch_n = int(1.1 * SR)
        glitch = bitcrush(square(60.0, glitch_n, duty=0.2) * exp_decay(glitch_n, 0.5), bits=4, hold=6)
        add_at(fx_s, glitch, at, 0.22)
    elif func == "trollgeInvert":
        riser_n = int(2.4 * SR)
        rt = np.arange(riser_n) / SR
        riser = bandpass(noise(riser_n, seed=74), 300.0, 8000.0) * (rt / rt[-1]) ** 2
        add_at(fx_s, riser, max(0.0, at - 2.4), 0.35)
        add_at(fx_s, sub_drop(2.0, 200.0, 35.0), at, 0.55)
    elif func == "trollgePhase2":
        add_at(fx_s, crash(2.6, seed=75), at, 0.5)
        add_at(fx_s, screech_fx(2.2, seed=76), at, 0.45)
        add_at(fx_s, sub_drop(2.6, 190.0, 24.0), at, 0.6)
    else:
        st_n = int(0.9 * SR)
        st = highpass(noise(st_n, seed=77), 2000.0) * np.exp(-np.arange(st_n) / (0.3 * SR))
        add_at(fx_s, st, at, 0.3)


# --------------------------------------------------------------------------- #
# The instrumental
# --------------------------------------------------------------------------- #

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
        cutoff = {"intro": 900.0, "verse": 1300.0, "build": 1700.0,
                  "drop": 2200.0, "break": 700.0, "finale": 2600.0}[role]
        gain = 0.08 * ROLE_GAIN[role]
        sig = pad_chord(chord, measure * 1.04, gain=gain, cutoff=cutoff, seed=m * 0.7)
        add_at(pad_l, sig, t0, 0.60)
        add_at(pad_r, sig, t0 + 0.012, 0.60)

    # ---- piano ----
    answers = list(piano_answers(song))
    accompaniment = [event for event in piano_events(song)
                     if all(abs(event[0] - answer[0]) > 0.55 * beat for answer in answers)]
    for i, (at, midi, dur, velocity) in enumerate(accompaniment + answers):
        note = piano_note(midi, dur)
        pan_pos = (-0.20 if i % 2 else 0.20)
        l, r = pan(note, pan_pos)
        add_at(piano_l, l, at, velocity * 0.95)
        add_at(piano_r, r, at + 0.008, velocity * 0.95)

    # ---- bass ----
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        root, _tones = L.chord_for_measure(song, m)
        base = song["tonic"] + root
        pattern = bass_pattern(style, role, beat, tier)
        bass_level = {"dark_trap": 0.50, "dark_glitch": 0.20}.get(style, 0.28)
        level = bass_level * (0.5 + 0.5 * ROLE_GAIN[role]) * (0.9 if style == "industrial" else 1.0)
        for offset_b, octave, dur_b in pattern:
            dur_s = dur_b * beat
            pitch = octave + 12 if octave == -12 and style != "dark_trap" else octave
            if style == "dark_trap" and abs(octave) > 0:
                add_at(bass_s, slide_808(midi_to_hz(base + pitch), midi_to_hz(base + pitch - 7), int(dur_s * SR), tier), t0 + offset_b * beat, level)
            else:
                add_at(bass_s, reese_bass(midi_to_hz(base + pitch), int(dur_s * SR), tier), t0 + offset_b * beat, level)

    # ---- drums ----
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        drum_pattern(style, role, t0, beat, tier, kick_s, snare_s, hat_l, hat_r, fx_s, m)
        ghost_snares(style, role, t0, beat, tier, snare_s, hat_r, m, ROLE_GAIN[role])

        if m + 1 < total_measures and measure_role.get(m + 1) != role:
            upcoming = measure_role.get(m + 1, role)
            if ROLE_GAIN[upcoming] >= ROLE_GAIN[role]:
                drum_fill(t0 + 3 * beat, beat, style, tier, snare_s, fx_s, seed=500 + m, loudness=0.7 + 0.3 * tier)
                add_at(fx_s, crash(1.8, seed=80 + m), t0 + 4 * beat, 0.20 + 0.05 * tier)
                riser_n = int(beat * 2.0 * SR)
                rt = np.arange(riser_n) / SR
                riser = bandpass(noise(riser_n, seed=81 + m), 500.0, 9000.0) * (rt / rt[-1]) ** 2
                add_at(fx_s, riser, t0 + 4 * beat - beat * 2.0, 0.10 + 0.04 * tier)

    # ---- groove polish ----
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        if role not in ("verse", "build", "drop", "finale"):
            continue
        intensity = ROLE_GAIN[role]
        nudge, velocity = __import__('random').Random(m * 7919).random() * 0.014 - 0.007, 0.92
        for beat_index in (1, 3):
            for fraction in (0.25, 0.75):
                if role == "verse" and fraction == 0.25:
                    continue
                add_at(snare_s, dark_snare(0.12, style, tier, 300 + m * 4 + beat_index),
                       t0 + beat_index * beat + fraction * beat,
                       0.09 * intensity * velocity)
        if m % 2 == 1:
            add_at(hat_r, dark_hat(0.13, True, style, 400 + m), t0 + 3.5 * beat, 0.16 * intensity)

    shape_rhythm(song, (kick_s, snare_s, hat_l, hat_r), 'drums')
    shape_rhythm(song, (bass_s,), 'bass')

    # ---- lead ----
    lead_index = 0
    for note in L.melodic_onsets(song):
        at = note["time"] / 1000.0
        role = measure_role.get(note["measure"], "verse")
        dur = max(0.16, note["sLen"] / 1000.0 if note["sLen"] else step * 2.4)
        midi = L.note_pitch(song, note["measure"], note["id"], semi=note.get("semi"))
        accent = 1.0 if note["time"] % (beat * 1000.0) < 1.0 else 0.85
        dur *= 1.15
        nudge, velocity = 0.0, 0.92
        at = max(0.0, at + nudge)
        sig = dark_saw_lead(midi, int(dur * SR), tier)
        sub = dark_saw_lead(midi - 12, int(dur * 0.92 * SR), tier)
        sub = np.pad(sub, (0, max(0, len(sig) - len(sub))))[:len(sig)]
        sig = sig + sub * 0.25
        target = lead_p if note["side"] == "player" else lead_o
        lead_level = 0.55 if style == "dark_glitch" else 0.48
        add_at(target, sig, at, lead_level * accent * velocity * (0.75 + 0.35 * ROLE_GAIN[role]))
        if role == "finale" and note["side"] == "player":
            add_at(target, dark_saw_lead(midi + 12, int(dur * 0.8 * SR), tier), at,
                   0.20 * accent)
        lead_index += 1

    # ---- horror layers per tier ----
    ambient = np.ones(n_total)
    for m in range(total_measures):
        start = int(L.measure_time(song, m) / 1000.0 * SR)
        end = min(n_total, int(L.measure_time(song, m + 1) / 1000.0 * SR))
        if end > start:
            ambient[start:end] = 0.30 + 0.70 * ROLE_GAIN.get(measure_role.get(m), 0.7)

    if tier >= 1:
        drone_root = midi_to_hz(song["tonic"] - 12)
        drone_gain = {1: 0.025, 2: 0.17, 3: 0.040}.get(tier, 0.035 * tier)
        drone = lowpass(sine(drone_root, n_total) * drone_gain +
                        sine(drone_root * 0.5, n_total) * 0.4 * drone_gain, 150.0)
        fx_s += drone * ambient

    if tier >= 2:
        fx_s += highpass(noise(n_total, seed=61), 2600.0) * (0.016 if tier == 2 else 0.026) * ambient

    if tier >= 3:
        swell = bandpass(noise(n_total, seed=63), 400.0, 2600.0)
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)
        fx_s += swell * lfo * 0.040 * ambient

    if tier >= 4:
        breath = bandpass(noise(n_total, seed=65), 300.0, 1800.0)
        blfo = np.sin(2 * np.pi * 0.19 * np.arange(n_total) / SR)
        fx_s += breath * np.maximum(0.0, blfo) * 0.050 * ambient
        tritone = sine(drone_root * 2 ** 0.5, n_total) * 0.022 + sine(drone_root, n_total) * 0.020
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * 5.6 * np.arange(n_total) / SR)
        fx_s += lowpass(tritone * trem, 220.0) * ambient

    if tier >= 5:
        fx_s += heartbeat(song["bpm"], total, tier)
        fx_s += whispers(n_total, tier)
        choir = choir_chord([song["tonic"] - 12, song["tonic"] - 5, song["tonic"]], n_total, tier)
        fx_s += choir * ambient

    # ---- scripted stingers ----
    for seconds, func in song["events"]:
        at = max(0.0, seconds)
        scripted_stinger(fx_s, func, at, tier, song)

    # ---- per-song differentiation FX ----
    if sid == "trolling":
        bells = sum(sine(midi_to_hz(72 + i * 7), n_total) * 0.010 for i in range(4))
        fx_s += lowpass(bells, 3000.0) * ambient
    elif sid == "getting-dark":
        growl = soft_clip(saw(midi_to_hz(song["tonic"] - 12), n_total) * 2.5, 1.1)
        fx_s += lowpass(growl, 200.0) * 0.03 * ambient
    elif sid == "dont-look-back":
        for m in range(total_measures):
            if m % 2 == 1:
                t0 = L.measure_time(song, m) / 1000.0
                add_at(fx_s, bitcrush(bandpass(noise(int(0.1 * SR), seed=1000 + m),
                        3000.0, 7000.0) * exp_decay(int(0.1 * SR), 20.0),
                        bits=4, hold=8) * 0.03, t0 + beat)
    elif sid == "super-scary":
        import random as _r
        rng = _r.Random(1234)
        for _ in range(int(total / 1.5)):
            at = rng.uniform(0.5, total - 0.5)
            add_at(fx_s, metal_hit(0.08, seed=int(at * 1000)), at, 0.05)
    elif sid == "the-incident":
        rumble = sine(midi_to_hz(song["tonic"] - 18), n_total) * 0.015
        fx_s += lowpass(rumble, 80.0) * ambient

    # ---- ending ----
    end_at = total - 2.0 * beat
    root, tones = L.chord_for_measure(song, total_measures - 1)
    final_chord = [song["tonic"] + root + t + 12 for t in tones] + [song["tonic"] + root - 12]
    sting = pad_chord(final_chord, max(0.4, total - end_at), gain=0.18, cutoff=2600.0)
    add_at(pad_l, sting, end_at, 0.8)
    add_at(pad_r, sting, end_at, 0.8)
    intensity = 0.26 if tier <= 2 else (0.55 if tier <= 4 else 0.82)
    add_at(fx_s, crash(2.0, seed=91), end_at, 0.32 * intensity)
    add_at(fx_s, sub_drop(1.8, 150.0, 26.0), end_at, 0.45 * intensity)
    add_at(kick_s, dark_kick(0.5, style, tier), end_at, 0.85 * intensity)
    add_at(piano_l, piano_note(final_chord[0], max(0.5, 1.8 * beat)), end_at, 0.55)
    add_at(piano_r, piano_note(final_chord[-2], max(0.5, 1.8 * beat)), end_at + 0.04, 0.45)

    # ---- dread layer ----
    n_all = np.arange(n_total) / SR
    drone_hz = midi_to_hz(song["tonic"] - 12)
    beat_hz = 0.55 + 0.18 * tier
    drone = (sine(drone_hz, n_total) * 0.55 + sine(drone_hz * 1.0035, n_total) * 0.45)
    dread_l = drone * (0.72 + 0.28 * np.sin(2 * np.pi * beat_hz * n_all))
    dread_r = drone * (0.72 + 0.28 * np.sin(2 * np.pi * beat_hz * n_all + 1.9))
    if tier >= 4:
        tritone_hz = midi_to_hz(song["tonic"] - 12) * (2 ** (6 / 12.0))
        dread_l = dread_l + sine(tritone_hz, n_total) * 0.24
        dread_r = dread_r + sine(tritone_hz * 1.002, n_total) * 0.24
    dread_amount = max(0.0, (tier - 1) / 4.0)
    if sid == "trolling":
        dread_amount *= 0.5
    elif sid == "getting-dark":
        dread_amount *= 2.0
    elif sid == "dont-look-back":
        dread_amount *= 0.70
    elif sid == "super-scary":
        dread_amount *= 0.7
    elif sid == "the-incident":
        pass  # full dread, EQ controls sub
    gain = 0.085 * dread_amount
    dread_l *= dread_amount
    dread_r *= dread_amount
    dread_l += lowpass(dread_l, 120.0) * gain
    dread_r += lowpass(dread_r, 120.0) * gain
    breath = bandpass(noise(n_total, seed=7 + tier), 700.0, 2600.0)
    swing = 0.5 + 0.5 * np.sin(2 * np.pi * (0.11 + 0.03 * tier) * n_all - 0.6)
    swing = swing ** 3
    breath = breath * swing * (0.055 * dread_amount)
    dread_l += breath
    dread_r += np.roll(breath, int(0.021 * SR))

    # ---- air bed ----
    air_bed = bandpass(noise(n_total, seed=9001), 10000.0, 17000.0) * 0.018

    # ---- stereo mix ----
    left = np.zeros(n_total)
    right = np.zeros(n_total)
    lead_send = 0.5 * (lead_p + lead_o)
    wet = reverb(lead_send + 0.5 * snare_s, wet=0.36, size=0.95)
    echo = delay(lead_send, beat * 0.75, feedback=0.28, mix=0.22 + 0.05 * tier)
    del lead_send
    wet_l, wet_r = haas(wet, 0.014)
    echo_l = echo
    echo_r = np.roll(echo, int(0.20 * beat * SR))
    del wet, echo

    key = kick_s
    pad_l = sidechain(pad_l, key, depth=0.52)
    pad_r = sidechain(pad_r, key, depth=0.52)
    bass_s = sidechain(bass_s, key, depth=0.38)

    if tier >= 3:
        cut = int(len(hat_l) * 0.60)
        for channel in (hat_l, hat_r):
            channel[cut:] = lowpass(channel[cut:], 8800.0) * 0.82 + channel[cut:] * 0.18

    def fit(x):
        x = dc_block(np.asarray(x[:n_total], dtype=np.float64))
        tail = int(0.25 * SR)
        x[-tail:] *= np.linspace(1.0, 0.0, tail)
        return x

    bass_s = highpass(bass_s, 120.0)

    stems = {
        "kick": (kick_s, 0.42, 0.42),
        "snare": (snare_s, 0.62, 0.62),
        "hat_l": (hat_l, 0.56, 0.16),
        "hat_r": (hat_r, 0.16, 0.56),
        "bass": (bass_s, 0.30, 0.30),
        "pad_l": (pad_l, 0.50, 0.16),
        "pad_r": (pad_r, 0.16, 0.50),
        "piano_l": (piano_l, 0.88, 0.12),
        "piano_r": (piano_r, 0.12, 0.88),
        "lead_o": (lead_o, 1.05 if style == "dark_ambient" else 0.90, 0.60 if style == "dark_ambient" else 0.52),
        "lead_p": (lead_p, 0.60 if style == "dark_ambient" else 0.52, 1.05 if style == "dark_ambient" else 0.90),
        "fx": (fx_s, 0.30, 0.30),
        "wet_l": (wet_l, 0.44, 0.04),
        "wet_r": (wet_r, 0.04, 0.44),
        "echo_l": (echo_l, 0.34, 0.04),
        "echo_r": (echo_r, 0.04, 0.34),
        "dread_l": (dread_l, 0.42, 0.42),
        "dread_r": (dread_r, 0.42, 0.42),
    }

    for name in list(stems):
        signal, gl, gr = stems.pop(name)
        signal = fit(signal)
        left += signal * gl
        right += signal * gr
        del signal

    left += air_bed
    right += np.roll(air_bed, int(0.011 * SR))
    del air_bed

    if style == "dark_trap":
        hiss = bandpass(noise(n_total, seed=8127), 8500.0, 15500.0) * 0.026
        left += hiss
        right += np.roll(hiss, int(0.013 * SR))
        del hiss

    # ---- per-song master EQ ----
    if sid == "trolling":
        master_points = [(26.0, -26.0), (40.0, -18.0), (55.0, -12.0), (70.0, -9.0),
                         (90.0, -7.0), (120.0, -4.0), (180.0, -2.0), (250.0, -1.0),
                         (320.0, -0.3), (450.0, 0.0), (650.0, 0.2), (800.0, 0.4),
                         (1400.0, 0.8), (2000.0, 1.2), (3000.0, 1.6), (4000.0, 2.0),
                         (6000.0, 2.4), (8000.0, 2.6), (10000.0, 2.8), (12000.0, 2.4),
                         (15000.0, 1.8), (18000.0, 1.2)]
    elif sid == "getting-dark":
        master_points = [(26.0, -42.0), (40.0, -34.0), (55.0, -26.0), (70.0, -18.0),
                         (90.0, -14.0), (120.0, -9.0), (180.0, -5.0), (250.0, -2.5),
                         (320.0, -1.2), (450.0, -0.5), (650.0, -0.1), (800.0, 0.0),
                         (1400.0, -0.2), (2000.0, 0.0), (3000.0, 0.3), (4000.0, 0.5),
                         (6000.0, 0.7), (8000.0, 0.9), (10000.0, 1.1), (12000.0, 0.7),
                         (15000.0, 0.4), (18000.0, 0.0)]
    elif sid == "dont-look-back":
        master_points = [(26.0, -30.0), (40.0, -22.0), (55.0, -16.0), (70.0, -11.0),
                         (90.0, -9.0), (120.0, -6.0), (180.0, -3.0), (250.0, -1.5),
                         (320.0, -0.8), (450.0, -0.2), (650.0, 0.0), (800.0, 0.4),
                         (1400.0, 1.2), (2000.0, 1.8), (3000.0, 2.4), (4000.0, 2.8),
                         (6000.0, 3.2), (8000.0, 3.4), (10000.0, 3.6), (12000.0, 3.2),
                         (15000.0, 2.8), (18000.0, 2.2)]
    elif sid == "super-scary":
        master_points = [(26.0, -34.0), (40.0, -26.0), (55.0, -20.0), (70.0, -14.0),
                         (90.0, -11.0), (120.0, -7.0), (180.0, -4.0), (250.0, -2.0),
                         (320.0, -1.0), (450.0, -0.4), (650.0, 0.0), (800.0, 0.2),
                         (1400.0, 0.8), (2000.0, 1.4), (3000.0, 2.0), (4000.0, 2.5),
                         (6000.0, 3.0), (8000.0, 3.2), (10000.0, 3.4), (12000.0, 3.0),
                         (15000.0, 2.6), (18000.0, 2.0)]
    elif sid == "the-incident":
        master_points = [(26.0, -44.0), (40.0, -36.0), (55.0, -28.0), (70.0, -20.0),
                         (90.0, -16.0), (120.0, -11.0), (180.0, -6.0), (250.0, -3.0),
                         (320.0, -1.8), (450.0, -1.0), (650.0, -0.4), (800.0, 0.0),
                         (1400.0, 0.5), (2000.0, 0.9), (3000.0, 1.5), (4000.0, 2.0),
                         (6000.0, 2.5), (8000.0, 2.8), (10000.0, 3.0), (12000.0, 2.6),
                         (15000.0, 2.2), (18000.0, 1.6)]
    left = eq_curve(left, master_points)
    right = eq_curve(right, master_points)
    left = soft_clip(left * 1.20, 1.04) * 0.86
    right = soft_clip(right * 1.20, 1.04) * 0.86
    left = compress(left, threshold_db=-15.0, ratio=2.2, makeup_db=2.2)
    right = compress(right, threshold_db=-15.0, ratio=2.2, makeup_db=2.2)
    crushed = compress(0.5 * (left + right), threshold_db=-28.0, ratio=5.0, makeup_db=7.0)
    left = left + crushed * 0.18
    right = right + crushed * 0.18
    left, right = widen(left, right, amount=1.40 + 0.06 * tier)

    arc = story_level(song, np.arange(n_total, dtype=np.float64) / max(1, n_total - 1))
    left *= arc
    right *= arc
    del arc

    loudness = float(np.sqrt(0.5 * (np.mean(left ** 2) + np.mean(right ** 2))))
    scale = TARGET_RMS / max(loudness, 1e-9)
    left, right = left * scale, right * scale
    left, right = limiter(left, 0.84), limiter(right, 0.84)
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    if peak > 0.80:
        trim = 0.80 / peak
        left, right = left * trim, right * trim
    return left, right


# --------------------------------------------------------------------------- #
# Vocals
# --------------------------------------------------------------------------- #

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
            dur = max(.10, note['sLen'] / 1000.0)
        else:
            desired = step * (2.4 if note['side'] == 'opponent' else 2.0)
            dur = max(.045, min(desired, next_at - at - .055))
        phrase_shape = .77 + .23 * math.sin(math.pi * phase) ** .8
        local_step = (at - L.measure_time(song, note['measure']) / 1000.0) / beat
        accent = 1.08 if abs(local_step - round(local_step)) < .03 else .92
        if i and notes[i - 1]['side'] == note['side']:
            diff = (note.get('semi') or 0) - (notes[i - 1].get('semi') or 0)
            accent *= 1.05 if diff >= 4 else (.94 if diff <= -4 else 1.0)
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

    wet = reverb(0.22 * (player + opponent), wet=0.18, size=0.55)
    wet_l, wet_r = haas(wet, 0.016)
    del wet

    left = player * 0.40 + opponent * 0.46 + wet_l * 0.26
    right = player * 0.46 + opponent * 0.40 + wet_r * 0.26
    del player, opponent, wet_l, wet_r

    def fit(x):
        x = dc_block(np.asarray(x[:n_total], dtype=np.float64))
        tail = int(0.20 * SR)
        x[-tail:] *= np.linspace(1.0, 0.0, tail)
        return x

    left, right = fit(left), fit(right)
    vocal_eq = [(90.0, -6.0), (180.0, -1.0), (400.0, 0.0), (1100.0, 0.0),
                (2600.0, -1.0), (4200.0, -2.0), (7000.0, -3.0), (10000.0, -5.0), (16000.0, -7.0)]
    left = eq_curve(left, vocal_eq)
    right = eq_curve(right, vocal_eq)
    left = compress(left, threshold_db=-18.0, ratio=2.2, attack_ms=6.0, release_ms=90.0, makeup_db=1.5)
    right = compress(right, threshold_db=-18.0, ratio=2.2, attack_ms=6.0, release_ms=90.0, makeup_db=1.5)
    rms = float(np.sqrt(0.5 * (np.mean(left ** 2) + np.mean(right ** 2))))
    target = TARGET_RMS * 10.0 ** (-2.0 / 20.0)
    scale = target / max(rms, 1e-9)
    left, right = limiter(left * scale, 0.86), limiter(right * scale, 0.86)
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    if peak > 0.82:
        left, right = left * (0.82 / peak), right * (0.82 / peak)
    return left, right


# --------------------------------------------------------------------------- #
# Game-over theme
# --------------------------------------------------------------------------- #

def render_game_over():
    bpm = 76.0
    beat = 60.0 / bpm
    total = 16.0
    n_total = int(total * SR)
    mono = np.zeros(n_total)

    mono += pad_chord([38, 45, 50, 53], total, gain=0.30, cutoff=900.0)[:n_total]
    tritone = sine(38.0 * 1.4142, n_total) * 0.05
    tritone *= 0.55 + 0.45 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)
    mono += lowpass(tritone, 300.0)

    hb_n = int(0.18 * SR)
    hbt = np.arange(hb_n) / SR
    thump = np.sin(2 * np.pi * np.cumsum(58.0 + 44.0 * np.exp(-hbt * 26.0)) / SR)
    thump *= np.exp(-hbt * 15.0)
    t = 0.0
    while t < total - 0.4:
        add_at(mono, thump, t, 0.30)
        add_at(mono, thump * 0.65, t + 0.30, 0.30)
        t += 4 * beat

    for index, at in enumerate((0.6, 2.4, 4.2, 6.6, 9.0, 11.4, 13.8)):
        midi = (62, 61, 57, 50, 56, 49, 45)[index]
        add_at(mono, music_box(midi, 2.2), at, 0.34)

    mono += highpass(noise(n_total, seed=311), 2600.0) * 0.012
    breath = bandpass(noise(n_total, seed=313), 300.0, 1500.0)
    mono += breath * (0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * np.arange(n_total) / SR)) * 0.02

    mono = reverb(mono, wet=0.42, size=1.0)
    mono = mono[:n_total]
    mono = eq_curve(mono, [(60.0, 2.0), (200.0, 1.0), (900.0, 1.5), (3000.0, -1.0),
                           (9000.0, 1.0), (16000.0, 2.5)])
    mono = normalize(mono, 0.86)
    left, right = widen(mono, mono, amount=1.4)

    n = int(1.5 * SR)
    st = np.arange(n) / SR
    drop = sub_drop(1.4, 190.0, 28.0)
    static = highpass(noise(n, seed=315), 1800.0) * np.exp(-st * 5.0)
    ring = np.sin(2 * np.pi * 210.0 * st) * np.exp(-st * 3.4) * 0.4
    sting = np.zeros(n)
    for piece in (drop, static, ring):
        m = min(len(piece), n)
        sting[:m] += piece[:m] * 0.8
    sting = soft_clip(sting, 1.7)
    sting = eq_curve(sting, [(40.0, 3.0), (200.0, 1.5), (2500.0, 1.0), (12000.0, 2.0)])
    sting = normalize(fade(sting, 0.002, 0.4), 0.93)

    n = int(0.9 * SR)
    rt = np.arange(n) / SR
    whoosh = bandpass(noise(n, seed=317), 500.0, 11000.0) * (rt / rt[-1]) ** 3
    whoosh += sine(520.0 * np.exp(-rt * 2.2), n) * 0.25 * (rt / rt[-1]) ** 2
    whoosh = normalize(fade(whoosh, 0.01, 0.18), 0.82)
    return (left, right), sting, whoosh


# --------------------------------------------------------------------------- #
# Shared ambient themes + SFX
# --------------------------------------------------------------------------- #

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
            at = t + offset * (1.0 if not scary else 1.06)
            if at >= length:
                continue
            m = midi - (2 if scary else 0)
            add_at(buf, music_box(m), at, 0.5)
            if offset == 0.0:
                add_at(buf, music_box(m - 24, 2.4), at, 0.32)
        t += bar

    buf += highpass(noise(len(buf), seed=41), 4000.0) * (0.012 if not scary else 0.03)

    if scary:
        buf = reverb(buf, wet=0.58, size=1.0)
        warp_n = len(buf)
        warp = 1.0 + 0.015 * np.sin(2 * np.pi * 0.35 * np.arange(warp_n) / SR)
        buf = np.interp(np.cumsum(warp), np.arange(warp_n), buf)
        buf += highpass(noise(len(buf), seed=42), 9000.0) * 0.022
    else:
        buf = reverb(buf, wet=0.42, size=0.8)

    return normalize(fade(buf, in_s=0.4, out_s=1.2), 0.72)


def render_sfx():
    out = {}
    n = int(3.2 * SR)
    t = np.arange(n) / SR
    scare = np.zeros(n)
    hit = bandpass(noise(n, seed=91), 300.0, 10000.0) * np.exp(-t * 3.0)
    screech_f = 1800.0 + 900.0 * np.sin(2 * np.pi * 6.0 * t)
    tone = np.sin(2 * np.pi * np.cumsum(screech_f) / SR) * exp_decay(n, 0.35) * 0.4
    scare += soft_clip(hit * 1.6 + tone, 2.0)
    for extra in (sub_drop(n / SR, 200.0, 26.0) * 0.9, crash(n / SR, seed=92) * 0.6):
        m = min(len(extra), n)
        scare[:m] += extra[:m]
    out["trollge_jump_scare"] = normalize(fade(scare, in_s=0.002, out_s=0.8), 0.95)

    n = int(1.6 * SR)
    t = np.arange(n) / SR
    sweep_f = 700.0 * np.exp(-t * 1.4) + 70.0
    dist = square(sweep_f, n, duty=0.3) + saw(sweep_f * 0.5, n) * 0.6
    dist = bitcrush(dist, bits=4, hold=8) * (0.4 + 0.6 * np.sin(2 * np.pi * 9.0 * t) ** 2)
    dist += bandpass(noise(n, seed=93), 1200.0, 9000.0) * exp_decay(n, 0.6) * 0.35
    out["trollge_distortion"] = normalize(fade(soft_clip(dist, 1.8), 0.005, 0.25), 0.9)

    n = int(2.6 * SR)
    t = np.arange(n) / SR
    riser = bandpass(noise(n, seed=94), 250.0, 9000.0) * (t / t[-1]) ** 2
    low = sine(120.0 * np.exp(t * 0.55), n) * np.exp(-t * 0.9) * 0.5
    out["trollge_invert"] = normalize(fade(soft_clip(riser * 1.4 + low, 1.5), 0.01, 0.5), 0.92)

    n = int(0.13 * SR)
    t = np.arange(n) / SR
    blip = (sine(980.0, n) * 0.6 + sine(1470.0, n) * 0.3) * np.exp(-t * 55.0)
    out["trollge_hit"] = normalize(fade(blip, 0.001, 0.03), 0.8)

    n = int(0.32 * SR)
    t = np.arange(n) / SR
    miss = (saw(220.0 * np.exp(-t * 0.8), n) * 0.5 + square(160.0, n, duty=0.3) * 0.4) * np.exp(-t * 8.0)
    out["trollge_miss"] = normalize(fade(soft_clip(miss, 1.6), 0.002, 0.1), 0.85)
    return out


def render_note_voices():
    out = {}
    pitches = {"up": 1.26, "down": .79, "left": 0.94, "right": 1.12}
    for name, mult in pitches.items():
        n = int(0.24 * SR)
        t = np.arange(n) / SR
        f0 = 232.0 * mult * (1.0 + 0.05 * np.exp(-t * 34.0))
        src = saw(f0, n) * 0.55 + square(f0, n, duty=0.42) * 0.30
        voice = bandpass(src, 500.0, 980.0) + bandpass(src, 1050.0, 2100.0) * 0.55
        env = adsr(n, attack=0.007, decay=0.045, sustain=0.42, release=0.085)
        out["bf_note_" + name] = normalize(fade(soft_clip(voice * env, 1.15), 0.004, 0.05), 0.62)

        n = int(0.34 * SR)
        t = np.arange(n) / SR
        g0 = 96.0 * mult
        growl = saw(g0, n) * 0.50 + square(g0 * 0.5, n, duty=0.30) * 0.40
        growl *= 1.0 + 0.45 * np.sin(2 * np.pi * 31.0 * t)
        body = bandpass(growl, 210.0, 720.0) + bandpass(growl, 780.0, 1700.0) * 0.35
        env = adsr(n, attack=0.010, decay=0.085, sustain=0.40, release=0.115)
        out["trollge_note_" + name] = normalize(
            fade(soft_clip(body * env, 2.1), 0.004, 0.08), 0.56)
    return out


def render_countdown():
    out = {}
    for index, (name, freq) in enumerate((("intro3", 104.0), ("intro2", 124.0), ("intro1", 150.0))):
        n = int(0.42 * SR)
        t = np.arange(n) / SR
        f = freq * (1.0 + 0.18 * np.exp(-t * 26.0))
        body = sine(f, n) * np.exp(-t * 7.5)
        body += saw(f * 0.5, n) * np.exp(-t * 11.0) * 0.35
        click = bandpass(noise(n, seed=70 + index), 900.0, 7000.0) * np.exp(-t * 60.0) * 0.5
        out[name] = normalize(fade(soft_clip(body * 0.9 + click, 1.5), 0.001, 0.12), 0.82)

    n = int(1.1 * SR)
    t = np.arange(n) / SR
    blast = sub_drop(n / SR, 210.0, 32.0) * 1.0
    blast[:n] += crash(n / SR, seed=95)[:n] * 0.55
    blast[:n] += screech_fx(n / SR, seed=96)[:n] * 0.35
    blast[:n] += bandpass(noise(n, seed=97), 1500.0, 11000.0) * exp_decay(n, 0.3) * 0.5
    out["introGo"] = normalize(fade(soft_clip(blast, 2.4), 0.002, 0.35), 0.93)
    return out


# --------------------------------------------------------------------------- #
# Mastering helpers
# --------------------------------------------------------------------------- #

def write_song(path, left, right, ceiling=0.95, attempts=4):
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
        scale *= (ceiling * 0.99) / peak
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
    release = np.exp(-block / (0.12 * SR))
    for i in range(count):
        current = min(target[i], 1.0 - (1.0 - current) * release)
        gains[i] = current
    gain = np.repeat(gains, block)[:length]
    return gain


def write_song_pair(inst_path, voice_path, inst_l, inst_r, voice_l, voice_r):
    import soundfile as sf
    gain = linked_mix_gain(inst_l, inst_r, voice_l, voice_r)
    edge = max(1, int(0.005 * SR))
    block = max(1, int(.01 * SR))
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
        scale *= 0.94 / peak
    raise RuntimeError("encoded stem sum exceeds safe peak after retries")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Compatibility wrappers for legacy test API
# --------------------------------------------------------------------------- #

def bass_for(style, midi, dur, tier):
    """Legacy wrapper: bass_for -> reese_bass."""
    return reese_bass(midi_to_hz(midi), int(max(dur, 0.06) * SR), tier)


def sampled_voice_note(midi, dur, dark=False):
    """Legacy wrapper: sampled_voice_note -> voice_note."""
    x = voice_note(midi, dur, dark=dark)
    x[0] = 0.0
    x[-1] = 0.0
    return x
    """Legacy wrapper: sampled_voice_note -> voice_note."""
    return voice_note(midi, dur, dark=dark)

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
