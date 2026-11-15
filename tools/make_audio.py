#!/usr/bin/env python3
"""
Renders every audio asset of the Super Scary Trollge mod.

Per song (songs/<id>/song/Inst.ogg):
    the instrumental, built FROM the chart notes of that song, with the horror
    dialled up per scare tier (2/10, 4/10, 7/10).

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

#: Loudness the instrumentals are mastered to (RMS, linear). -15.5 dBFS is loud
#: enough for a game mix without squashing the quiet sections.
TARGET_RMS = 10.0 ** (-14.0 / 20.0)


# --------------------------------------------------------------------------- #
# Instruments
# --------------------------------------------------------------------------- #

def kick(dur=0.42, drive=1.0, tune=1.0):
    """A kick with weight, not a click.

    Pitch envelope 90 -> 54 Hz over ~40 ms, a soft attack ramp so the transient
    has no click, and no saturation by default: the sub is already a sine, so
    drive only adds harmonics nobody wants in a 50-90 Hz band.
    """
    n = int(dur * SR)
    t = np.arange(n) / SR
    start_hz, end_hz = 90.0 * tune, 54.0 * tune
    freq = end_hz + (start_hz - end_hz) * np.exp(-t * 26.0)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    # Amplitude: a raised-cosine attack (no discontinuity) into a slow decay.
    attack = int(0.004 * SR)
    env = np.exp(-t * 5.2)
    if attack:
        env[:attack] *= np.linspace(0.0, 1.0, attack) ** 2
    # A little beater: a very short band of noise low in the mids, 60 ms decay.
    beater = bandpass(noise(n, seed=11), 300.0, 1600.0) * np.exp(-t * 130.0) * 0.10
    out = body * env + beater
    return soft_clip(out, drive) if drive != 1.0 else out


def snare(dur=0.34, tune=200.0, seed=12, wet=0.0):
    """A snare with a body, not a noise burst.

    A tuned tone component at 180-220 Hz (the drum's own pitch) sits under
    band-limited noise, and the whole thing can be sent to the plate (`wet`),
    which is where the tail comes from in the mix stage.
    """
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = (np.sin(2 * np.pi * tune * t) * 0.55
            + np.sin(2 * np.pi * tune * 1.62 * t) * 0.22) * np.exp(-t * 26.0)
    rattle = bandpass(noise(n, seed=seed), 900.0, 6200.0) * np.exp(-t * 15.0)
    # Smooth the rattle's onset: a raw noise burst reads as a click.
    onset = int(0.003 * SR)
    rattle[:onset] *= np.linspace(0.0, 1.0, onset)
    return (tone * 0.7 + rattle * 0.62)


def hat(dur=0.07, open_=False, seed=13, tune=1.0):
    """A hat with air, without the 3-8 kHz shard.

    Filtered noise with a gentle high shelf instead of a hard highpass: the
    harshness in the old kit came from a 6.5 kHz brick wall on white noise.
    """
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * (9.0 if open_ else 52.0))
    body = bandpass(noise(n, seed=seed), 5200.0 * tune, 13500.0 * tune)
    body = eq_curve(body, [(2000.0, -3.0), (6000.0, 0.5), (10000.0, 2.5), (14000.0, -1.0)])
    onset = int(0.0015 * SR)
    body[:onset] *= np.linspace(0.0, 1.0, onset)
    return body * env * 0.34


def crash(dur=1.8, seed=14):
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = bandpass(noise(n, seed=seed), 2400.0, 13000.0)
    body = eq_curve(body, [(3000.0, -1.0), (8000.0, 1.0), (14000.0, -2.0)])
    return body * np.exp(-t * 2.2) * 0.42


def sub_drop(dur=2.2, f0=170.0, f1=28.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 2.6)
    env = np.exp(-t * 1.3)
    return soft_clip(np.sin(2 * np.pi * np.cumsum(freq) / SR) * env, 1.4)


def screech(dur=1.4, seed=51):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 1500.0 + 700.0 * np.sin(2 * np.pi * 5.5 * t) + 260.0 * np.sin(2 * np.pi * 0.7 * t)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    tone += np.sin(2 * np.pi * np.cumsum(f * 1.51) / SR) * 0.4
    return soft_clip(tone * exp_decay(n, dur * 0.35), 2.0) * 0.5


def human(index, step_s, swing=0.0):
    """Deterministic micro-timing and velocity for one hit.

    A grid-perfect renderer is the main reason a synth track sounds like a
    metronome instead of a band: every hit lands on the same microsecond with
    the same level. This returns a small timing nudge (plus swing on the odd
    16ths) and a velocity multiplier, both repeatable for a given index.
    """
    rng = (index * 2654435761) % 4294967296
    jitter = ((rng / 4294967296.0) - 0.5) * 0.007 * max(1.0, step_s / 0.1)
    velocity = 0.90 + (((rng >> 11) % 1000) / 1000.0) * 0.10
    shift = swing * step_s if index % 2 else 0.0
    return jitter + shift, velocity


# --------------------------------------------------------------------------- #
# Per-song voices
#
# The three songs share a renderer, not a band: each has its own kit, bass
# voice and lead voice, so they cannot sound like the same track at three tempos.
# --------------------------------------------------------------------------- #

def kick_for(style, tier):
    """One kick per genre, all built on the same warm 90 -> 55 Hz envelope.

    bounce = tight and round · trap = long 808 with a slide · glitch = short and
    broken · industrial = a metal beater on top · finale = double-headed.
    """
    if style == "trap":
        n = int(0.85 * SR)
        t = np.arange(n) / SR
        freq = 52.0 + 38.0 * np.exp(-t * 9.0)
        body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
        attack = int(0.005 * SR)
        env = np.exp(-t * 2.6)
        env[:attack] *= np.linspace(0.0, 1.0, attack) ** 2
        return body * env
    if style == "industrial":
        n = int(0.34 * SR)
        t = np.arange(n) / SR
        freq = 55.0 + 35.0 * np.exp(-t * 30.0)
        body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 7.5)
        metal = bandpass(noise(n, seed=22), 400.0, 2400.0) * np.exp(-t * 40.0) * 0.22
        return soft_clip(body + metal, 1.15)
    if style == "glitch":
        n = int(0.24 * SR)
        t = np.arange(n) / SR
        freq = 58.0 + 32.0 * np.exp(-t * 34.0)
        body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 11.5)
        tick = bandpass(noise(n, seed=31), 1800.0, 5200.0) * np.exp(-t * 150.0) * 0.14
        return body + tick
    if style == "finale":
        n = int(0.50 * SR)
        t = np.arange(n) / SR
        freq = 60.0 + 40.0 * np.exp(-t * 20.0)
        body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 3.8)
        body += np.sin(2 * np.pi * np.cumsum(freq * 1.5) / SR) * np.exp(-t * 6.0) * 0.18
        growl = lowpass(saw(46.0, n), 180.0) * np.exp(-t * 4.0) * 0.24
        return soft_clip(body + growl, 1.25)
    return kick(drive=1.0)


def snare_for(style, seed=12):
    """One snare per genre: all tuned (180-220 Hz body) and smooth-tailed."""
    if style == "trap":
        return snare(dur=0.36, tune=185.0, seed=seed) * 0.9
    if style == "industrial":
        n = int(0.36 * SR)
        t = np.arange(n) / SR
        tone = (np.sin(2 * np.pi * 210.0 * t) * 0.5
                + np.sin(2 * np.pi * 340.0 * t) * 0.2) * np.exp(-t * 24.0)
        metal = bandpass(noise(n, seed=seed), 1100.0, 5000.0) * np.exp(-t * 13.0) * 0.55
        return tone + metal
    if style == "glitch":
        n = int(0.30 * SR)
        t = np.arange(n) / SR
        tone = np.sin(2 * np.pi * 196.0 * t) * 0.55 * np.exp(-t * 22.0)
        gated = bandpass(noise(n, seed=seed), 1400.0, 6000.0) * np.exp(-t * 30.0)
        # Gated, not crushed: a rhythmic hole in the noise, no bitcrusher fizz.
        gate = (np.sin(2 * np.pi * 34.0 * t) > -0.2).astype(float)
        return tone + gated * gate * 0.5
    if style == "finale":
        # Blast-beat snare: a tight body with a second, longer, lower drum under
        # it for weight. Buffers differ in length, so pad before summing.
        hit = snare(dur=0.46, tune=205.0, seed=seed)
        under = snare(dur=0.7, tune=150.0, seed=seed + 1) * 0.4
        out = np.zeros(max(len(hit), len(under)))
        out[:len(hit)] += hit
        out[:len(under)] += under
        return out
    return snare(dur=0.34, tune=200.0, seed=seed)


def hat_for(style, open_=False, seed=13):
    """All four kits share the soft hat; only the length and the shelf differ."""
    if style == "trap":
        # Trap is the darkest kit (808 + half-time), so its hats carry a little
        # more air than the others or the song has no top end at all.
        return hat(dur=0.13 if open_ else 0.045, open_=open_, seed=seed, tune=1.0) * 1.5
    if style == "industrial":
        return hat(dur=0.20 if open_ else 0.06, open_=open_, seed=seed, tune=0.86)
    if style == "glitch":
        return hat(dur=0.15 if open_ else 0.04, open_=open_, seed=seed, tune=1.12)
    if style == "finale":
        return hat(dur=0.17 if open_ else 0.05, open_=open_, seed=seed, tune=0.94)
    return hat(dur=0.07 if not open_ else 0.13, open_=open_, seed=seed)


def _analog_stack(f, n, detune=0.004, octave=0.0, seed=0):
    """Detuned saw stack through a warm, slightly moving low-pass.

    Three saws a few cents apart plus a sub sine: the classic analogue pad/lead
    core. The filter opens with the note (a slow envelope), which is where the
    "warm but not dull" comes from -- a static filter is what makes synth leads
    sound like a buzzer with a shelf on it.
    """
    t = np.arange(n) / SR
    voice = (saw(f * (1.0 - detune), n) * 0.34
             + saw(f, n) * 0.40
             + saw(f * (1.0 + detune), n) * 0.30)
    if octave:
        voice += saw(f * octave, n) * 0.16
    else:
        voice += sine(f * 0.5, n) * 0.18
    # Envelope-modulated cutoff: opens by ~1.6x over the first 120 ms.
    open_amount = np.clip(1.0 - np.exp(-t * 18.0), 0.0, 1.0)
    cutoff = 900.0 * (1.0 + 0.8 * open_amount)
    # Approximate the moving filter with two static filters, crossfaded: cheap
    # and it keeps the attack bright instead of uniformly muffled.
    dark = lowpass(voice, 800.0)
    bright = lowpass(voice, 2400.0)
    return dark * (1.0 - open_amount) + bright * open_amount


def bass_for(style, midi, dur, tier):
    """One bass voice per genre, each warm and each audibly different."""
    n = int(max(dur, 0.06) * SR)
    t = np.arange(n) / SR
    f = midi_to_hz(midi)
    if style == "trap":
        freq = f * (1.0 + 0.30 * np.exp(-t * 26.0))
        body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
        body += np.sin(2 * np.pi * np.cumsum(freq * 2.0) / SR) * 0.10
        env = adsr(n, attack=0.008, decay=0.20, sustain=0.70, release=min(0.30, dur * 0.5))
        return soft_clip(lowpass(body * env, 300.0), 1.0)
    if style == "industrial":
        voice = _analog_stack(f, n, detune=0.006)
        voice += saw(f * 2.0, n) * 0.12
        env = adsr(n, attack=0.004, decay=0.09, sustain=0.60, release=0.06)
        out = lowpass(voice * env, 1300.0)
        return soft_clip(out * 1.1, 1.2)
    if style == "glitch":
        # Sample-and-hold octave corruption, but filtered warm so it cuts
        # rhythmically instead of adding fizz.
        rng = np.random.RandomState(abs(int(midi * 7 + dur * 1000)) % 2 ** 31)
        steps = max(2, int(dur / 0.06))
        holds = np.repeat(rng.choice([0.5, 0.7071, 1.0, 1.0, 1.4142, 2.0], size=steps),
                          int(np.ceil(n / steps)))[:n]
        freq = f * holds
        phase = 2 * np.pi * np.cumsum(freq) / SR
        voice = np.sin(phase) * 0.62 + np.sin(phase * 2.0) * 0.14
        env = adsr(n, attack=0.003, decay=0.06, sustain=0.55, release=0.05)
        return soft_clip(lowpass(voice * env, 1500.0), 1.15)
    if style == "finale":
        sub = sine(f, n) * 0.80 + sine(f * 2.0, n) * 0.12
        grunt = _analog_stack(f * 2.0, n, detune=0.005)
        grunt = soft_clip(grunt * 2.0, 1.5)
        env = adsr(n, attack=0.005, decay=0.11, sustain=0.66, release=0.08)
        return soft_clip(lowpass(sub + grunt * 0.30, 1500.0) * env, 1.15)
    # bounce: round sub with a plucked top, no grit
    voice = _analog_stack(f, n, detune=0.003)
    env = adsr(n, attack=0.005, decay=0.12, sustain=0.58, release=0.07)
    return soft_clip(lowpass(voice * env, 750.0), 1.05)


def lead_for(style, midi, dur, tier, note_id=0):
    """One lead voice per genre, all warm analog rather than shrill digital."""
    n = int(max(dur, 0.10) * SR)
    t = np.arange(n) / SR
    f = midi_to_hz(midi)
    if style == "trap":
        # FM bell: an inharmonic tail, but rolled off warm instead of glassy.
        body = np.zeros(n)
        for mult, amp, decay in ((1.0, 1.0, 2.2), (2.01, 0.30, 3.8), (3.03, 0.12, 6.0)):
            body += np.sin(2 * np.pi * f * mult * t) * amp * np.exp(-t * decay)
        body *= np.minimum(1.0, max(dur, 0.2) / 0.2)
        env = adsr(n, attack=0.006, decay=dur * 0.45, sustain=0.30, release=min(0.40, dur * 0.8))
        return soft_clip(lowpass(body, 3800.0) * env, 1.0) * 0.55
    if style == "industrial":
        voice = _analog_stack(f, n, detune=0.007)
        voice += saw(f * 0.5, n) * 0.16
        if tier >= 3:
            voice += sine(f * 1.5, n) * 0.10
        env = adsr(n, attack=0.005, decay=0.10, sustain=0.45, release=0.12)
        out = lowpass(voice * env, 3600.0)
        return soft_clip(out, 1.05) * 0.5
    if style == "glitch":
        # A vocal-ish square with rhythmic dropouts; no bitcrusher.
        rng = np.random.RandomState(abs(int(midi * 13 + note_id * 7)) % 2 ** 31)
        voice = _analog_stack(f, n, detune=0.009)
        voice += square(f, n, duty=0.30) * 0.14
        env = adsr(n, attack=0.004, decay=0.07, sustain=0.50, release=0.06)
        out = lowpass(voice * env, 2800.0)
        holes = rng.rand(int(n / (SR * 0.03)) + 2) < 0.16
        mask = np.repeat(holes, int(SR * 0.03))[:n]
        out = out.copy()
        out[mask] *= 0.25
        return soft_clip(out, 1.1) * 0.5
    if style == "finale":
        voice = _analog_stack(f, n, detune=0.008)
        voice += saw(f * 1.5, n) * 0.14 + saw(f * 2.0, n) * 0.10
        env = adsr(n, attack=0.014, decay=0.15, sustain=0.58, release=0.15)
        out = lowpass(voice * env, 3400.0 + 500.0 * tier)
        return soft_clip(out, 1.05) * 0.46
    # bounce: a bright pulse chip lead, filtered round
    duty = 0.30 if note_id % 2 else 0.24
    voice = square(f, n, duty=duty) * 0.42 + square(f * 2.0, n, duty=0.5) * 0.10
    voice += sine(f * 3.0, n) * 0.06
    env = adsr(n, attack=0.004, decay=0.11, sustain=0.42, release=0.09)
    return soft_clip(lowpass(voice * env, 5200.0), 1.0) * 0.55


#: Vowel formants, measured from the models singers actually use (Peterson &
#: Barney / Csound's vowel tables), as (centre Hz, bandwidth Hz, gain).
#: The first two formants decide the vowel; the third adds presence, and a
#: little fourth keeps the top from sounding synthetic.
VOWELS = {
    "ah": ((730.0, 90.0, 1.00), (1090.0, 110.0, 0.55), (2440.0, 170.0, 0.22), (3400.0, 250.0, 0.08)),
    "oh": ((570.0, 80.0, 1.00), (840.0, 100.0, 0.60), (2410.0, 170.0, 0.16), (3300.0, 250.0, 0.06)),
    "ee": ((300.0, 60.0, 1.00), (2290.0, 140.0, 0.50), (3010.0, 180.0, 0.28), (3700.0, 260.0, 0.10)),
    "oo": ((370.0, 70.0, 1.00), (950.0, 100.0, 0.42), (2350.0, 170.0, 0.10), (3300.0, 250.0, 0.05)),
}

#: Which vowel each character sings on which scale step -- a singer does not hold
#: one vowel for a whole phrase, and the alternation is most of what makes a
#: synth voice read as "words" rather than as a buzz.
PLAYER_VOWELS = ("ah", "ee", "oh", "ee")
TROLLGE_VOWELS = ("oh", "oo", "oh", "ah")

#: Formant scaling per character. Boyfriend is a brighter, smaller vocal tract
#: (formants up); the Trollge is a much bigger one (formants down) with a wider
#: bandwidth, which is what makes a voice sound huge instead of just low.
PLAYER_SHIFT = 1.10
TROLLGE_SHIFT = 0.82


def _glottal(f0, n, sr=SR, tilt=1.0, breath=0.0, seed=0):
    """A glottal source with a real spectral roll-off.

    Additive harmonics with a 1/h^tilt amplitude law (plus a little even-harmonic
    asymmetry) give a sawtooth-like pulse that filters like a voice; white noise
    is a buzz saw, not a larynx.
    """
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
    """One sung syllable through a parallel formant bank.

    The chain is the one a voice actually has: a glottal source with a spectral
    tilt, a pitch scoop into the note, vibrato that grows through the note, three
    or four resonant formants in parallel, a breath of consonant on the attack,
    and an ADSR whose attack and release are long enough not to click.

    `dark` switches character: Boyfriend (bright formants, clean, ~5.6 Hz
    vibrato) or the Trollge (formants shifted down, sub-harmonic weight, a
    controlled saturation instead of fizz).
    """
    n = max(int(0.16 * SR), int((dur + 0.09) * SR))
    t = np.arange(n) / SR
    f0 = midi_to_hz(midi)

    # Pitch: scoop in from slightly flat, then settle; vibrato grows with length.
    glide = 1.0 - scoop * np.exp(-t * 22.0)
    rate = vibrato_hz if vibrato_hz else (5.1 if dark else 5.6)
    depth = vibrato * (0.55 if dark else 1.0)
    ramp = np.clip((t - 0.11) / 0.30, 0.0, 1.0)
    vibr = 1.0 + depth * np.sin(2 * np.pi * rate * t + 0.4) * ramp

    # The source: a harmonic stack at the moving pitch.
    inst = f0 * glide * vibr
    phase = 2 * np.pi * np.cumsum(inst) / SR
    src = np.zeros(n)
    h = 1
    while f0 * h < min(7600.0 if dark else 9500.0, SR * 0.45):
        amp = (1.0 / (h ** (1.35 if dark else 1.15))) * (1.0 + 0.16 * (h % 2))
        src += np.sin(phase * h + 0.35 * h) * amp
        h += 1

    if dark and growl > 0:
        # Sub-harmonic weight, not fizz: a half-rate component plus a little
        # saturation folds the voice down without the buzz of a bitcrusher.
        src += np.sin(phase * 0.5) * 0.35 * growl
        src = soft_clip(src * (1.0 + 0.5 * growl), 1.35)

    if vowel is None:
        vowel = "oh" if dark else "ah"
    shift = TROLLGE_SHIFT if dark else PLAYER_SHIFT
    formants = tuple((hz * shift, bw * shift, gain) for hz, bw, gain in VOWELS[vowel])
    out = formant_bank(src, formants)

    # A consonant: a very short band of noise, low level -- a "t" not a "shh".
    n_c = int(0.028 * SR)
    out[:n_c] += bandpass(noise(n_c, seed=seed % 251), 2600.0, 7600.0) * (0.16 if dark else 0.22)

    # ADSR with a soft attack and a release that reaches zero, so no click.
    attack = int((0.030 if dark else 0.018) * SR)
    release = int(0.11 * SR)
    sustain_len = max(1, n - attack - release)
    env = np.ones(n)
    env[:attack] = np.linspace(0.0, 1.0, attack) ** 1.4
    env[attack:attack + sustain_len] = 1.0
    env[attack + sustain_len:] = np.linspace(1.0, 0.0, n - attack - sustain_len) ** 1.6
    # A singer lets a long note swell then ease: a shallow arc over the body.
    body = np.ones(n)
    arc = np.clip(np.arange(n) / max(1.0, 0.28 * SR), 0.0, 1.0)
    body *= 0.82 + 0.18 * arc
    out *= env * body

    out = highpass(out, 85.0)
    return out * (0.5 if dark else 0.55)


#: How an analogue pad is voiced. A minor ninth is the sound of the whole mod:
#: it adds one note a ninth above the triad and one a flat seventh below, so the
#: chord breathes without ever becoming a plain triads-and-octaves stack.
def pad_voicing(root_midi, tones, tier):
    """Triad + 9th (+ sus4 above tier 3), voiced low-to-high without mud."""
    chord = [root_midi + t for t in tones]
    top = max(chord)
    ninth = top + (10 if (root_midi + 2) % 12 in (1, 3, 6, 8, 10, 11) else 2)
    voiced = sorted(chord + [ninth])
    if tier >= 3:
        voiced = sorted(voiced + [chord[0] + 5])          # sus4 colour
    if tier >= 4:
        voiced = sorted(voiced + [chord[-1] + 3])          # a sour added fourth
    return voiced


def pad_chord(midis, dur, gain=0.075, cutoff=1500.0, seed=0):
    """A lush pad: detuned saws per voice, warm filter, slow amplitude arc.

    Every voice gets three saws a few cents apart plus a quiet octave, which is
    what makes a pad sound wide and expensive rather than like a synth blast.
    """
    n = int(dur * SR)
    out = np.zeros(n)
    for i, midi in enumerate(midis):
        f = midi_to_hz(midi)
        for mult, amp, phase in ((0.9965, 0.55, 0.3), (1.0, 0.70, 1.1), (1.0035, 0.55, 2.4)):
            out += saw(f * mult, n, phase0=phase + i) * amp
        out += sine(f * 2.0, n) * 0.12
    # Slow filter breathing: two LFO rates, so no two bars of pad are identical.
    t = np.arange(n) / SR
    breathe = 1.0 + 0.22 * np.sin(2 * np.pi * 0.13 * t + seed) + 0.10 * np.sin(2 * np.pi * 0.41 * t)
    dark = lowpass(out, max(300.0, cutoff * 0.55))
    bright = lowpass(out, cutoff * 1.25)
    weight = np.clip(0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * t + seed), 0.0, 1.0)
    out = dark * (1.0 - weight) + bright * weight
    env = adsr(n, attack=dur * 0.30, decay=dur * 0.12, sustain=0.72, release=dur * 0.34)
    out *= env * breathe
    out = highpass(out, 140.0).copy()       # keep the pad out of the kick's way
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
# The instrumentals
# --------------------------------------------------------------------------- #

#: How hard each part of the arrangement pushes, by section role.
ROLE_GAIN = {
    "intro": 0.10,
    "verse": 0.70,
    "build": 0.86,
    "drop": 1.04,
    "break": 0.18,
    "finale": 1.12,
}


def tier_for(scare):
    """Scare rating -> production tier. One step per song, 0-10 -> 1-5."""
    if scare <= 2:
        return 1
    if scare <= 4:
        return 2
    if scare <= 6:
        return 3
    if scare <= 8:
        return 4
    return 5


def section_roles(song):
    """Arrangement roles live in song_layout.py so the chart and the audio can
    never disagree about where a song breathes."""
    return L.section_roles(song)


def render_song(song):
    """Render one instrumental.

    Layout: mono stems -> stereo mix -> master chain. Everything is arranged by
    *section role* (intro / verse / build / drop / break / finale), so each song
    builds, drops into a breakdown and lands on a real ending chord instead of
    looping one drum pattern for 104 seconds.
    """
    total = L.length(song)
    n_total = int(round(total * SR))
    beat = L.beat(song)
    measure = L.measure(song)
    step = L.step(song)
    scare = song["scare"]
    tier = tier_for(scare)
    style = song.get("style", "bounce")

    kick_s, snare_s = empty(total), empty(total)
    hat_l, hat_r = empty(total), empty(total)
    bass_s = empty(total)
    pad_l, pad_r = empty(total), empty(total)
    lead_o, lead_p = empty(total), empty(total)
    fx_s = empty(total)

    secs = L.sections(song)
    roles = section_roles(song)
    measure_role = {}
    for section, role in zip(secs, roles):
        m0 = int(round(section["time"] / 1000.0 / measure))
        for m in range(m0, m0 + section["measures"]):
            measure_role[m] = role
    total_measures = L.measures(song)

    # ---- pads ------------------------------------------------------------- #
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        root, tones = L.chord_for_measure(song, m)
        chord = [song["tonic"] + root + t for t in tones]
        cutoff = {"intro": 1100.0, "verse": 1600.0, "build": 1900.0,
                  "drop": 2400.0, "break": 900.0, "finale": 2700.0}[role]
        # Minor-ninth / sus voicing: the pad is a chord, not a power chord
        # (see pad_voicing). Slow filter movement keeps bar-to-bar fresh.
        chord = pad_voicing(song["tonic"] + root, tones, tier)
        cutoff *= 0.86 + 0.28 * (0.5 + 0.5 * math.sin(m * 0.9 + song["scare"]))
        gain = 0.085 * ROLE_GAIN[role]
        sig = pad_chord(chord, measure * 1.04, gain=gain, cutoff=cutoff, seed=m * 0.7)
        # Wide: one take per side, the right side delayed a few ms.
        add_at(pad_l, sig, t0, 0.62)
        add_at(pad_r, sig, t0 + 0.011, 0.62)

    # ---- bass ------------------------------------------------------------- #
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        root, _tones = L.chord_for_measure(song, m)
        base = song["tonic"] + root
        drive = 1.3 + 0.45 * tier

        # Bass figure: the groove is the song's, the role only scales it.
        if style == "trap":
            # 808: few, long, with slides into the next note.
            if role == "break":
                pattern = [(0.0, -12, beat * 2.2)]
            elif role == "intro":
                pattern = [(0.0, -12, beat * 3.6)]
            else:
                pattern = [(0.0, -12, beat * 1.35), (beat * 1.5, 0, beat * 0.9),
                           (beat * 2.5, -12, beat * 0.75), (beat * 3.25, 0, beat * 0.7)]
        elif style == "glitch":
            # Staccato 16ths that jump octaves: never settles, always in key.
            if role == "break":
                pattern = [(0.0, -12, beat * 1.2)]
            elif role == "intro":
                pattern = [(0.0, -12, beat * 3.0)]
            elif role == "finale" or role == "drop":
                pattern = [(i * beat / 4.0, (-12 if i % 4 == 0 else (12 if i % 8 == 5 else 0)),
                            beat / 4.0 * (1.0 if i % 2 else 0.7)) for i in range(16)]
            else:
                pattern = [(i * beat / 4.0, (-12 if i % 8 == 0 else (12 if i % 8 == 6 else 0)),
                            beat / 4.0 * 0.9) for i in range(8)]
        elif style == "finale":
            # Driving 8ths with a fifth stab on the "and" of 3: metal, not techno.
            if role == "break":
                pattern = [(0.0, -12, beat * 2.0), (beat * 2.0, 0, beat * 1.6)]
            elif role == "intro":
                pattern = [(0.0, -12, beat * 3.6)]
            else:
                pattern = [(i * beat / 2.0, (-12 if i % 4 == 0 else (7 if i == 5 else 0)),
                            beat / 2.0 * (0.95 if i % 2 else 1.06)) for i in range(8)]
        elif style == "industrial":
            if role == "break":
                pattern = [(0.0, -12, beat * 1.4)]
            elif role == "intro":
                pattern = [(0.0, -12, beat * 3.2)]
            else:
                pattern = [(i * beat / 4.0, -12 if i % 8 == 0 else (12 if i % 4 == 3 else 0),
                            beat / 4.0 * 0.85) for i in range(16)]
        else:
            if role == "break":
                pattern = [(0.0, -12, beat * 1.8)]
            elif role == "drop":
                pattern = [(0.0, 0, beat * 0.42), (beat * 0.5, 0, beat * 0.30),
                           (beat * 0.75, 0, beat * 0.20), (beat * 1.0, -12, beat * 0.40),
                           (beat * 1.5, 0, beat * 0.30), (beat * 1.75, 0, beat * 0.20),
                           (beat * 2.0, 0, beat * 0.42), (beat * 2.5, -12, beat * 0.28),
                           (beat * 3.0, 0, beat * 0.42), (beat * 3.5, 0, beat * 0.30)]
            elif role == "intro":
                pattern = [(0.0, -12, beat * 3.4)]
            else:
                pattern = [(i * beat / 2.0, -12 if i % 4 == 0 else 0,
                            beat / 2.0 * (0.92 if i % 2 else 1.05)) for i in range(8)]

        level = 0.46 * (0.5 + 0.5 * ROLE_GAIN[role]) * (0.9 if style == "industrial" else 1.0)
        for offset_s, octave, dur in pattern:
            add_at(bass_s, bass_for(style, base + octave, dur, tier), t0 + offset_s, level)

    # ---- drums ------------------------------------------------------------ #
    def drum_fill(at, length, loudness=1.0, seed=40):
        """Roll into the next section -- style-flavoured."""
        hits = 8
        for i in range(hits):
            when = at + length * i / hits
            if style == "trap":
                add_at(snare_s, snare_for(style, seed=seed + i), when, 0.10 * loudness)
                add_at(hat_r, hat_for(style, True, seed=seed + 30 + i), when, 0.16 * loudness)
            else:
                add_at(snare_s, snare_for(style, seed=seed + i), when,
                       (0.16 + 0.22 * i / hits) * loudness)

    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        intensity = ROLE_GAIN[role]

        if role in ("verse", "build", "drop", "finale"):
            if style == "trap":
                # Half-time: one boom, one rim, rolling hats.
                add_at(kick_s, kick_for(style, tier), t0, 0.95 * intensity)
                add_at(kick_s, kick_for(style, tier), t0 + 2.75 * beat, 0.7 * intensity)
                add_at(snare_s, snare_for(style, 71), t0 + 2 * beat, 0.55 * intensity)
                for step in range(8):
                    at = t0 + step * beat / 2.0
                    add_at(hat_l if step % 2 else hat_r, hat_for(style, False, 40 + step), at,
                           0.30 * intensity)
                    if step % 2 == 1 and (role in ("drop", "finale") or tier >= 2):
                        # 16th eighths + a triplet flick on the last 8th of the bar
                        add_at(hat_r, hat_for(style, False, 60 + step), at + beat / 4.0,
                               0.16 * intensity)
                        add_at(hat_l, hat_for(style, False, 80 + step), at + beat * 0.5,
                               0.14 * intensity)
                        add_at(hat_l, hat_for(style, True, 90 + step), at + beat * 0.66,
                               0.12 * intensity)
            elif style == "glitch":
                # Broken beat: kick on 1 and the "a" of 2, gated snare stutters.
                add_at(kick_s, kick_for(style, tier), t0, 0.95 * intensity)
                add_at(kick_s, kick_for(style, tier), t0 + 1.75 * beat, 0.72 * intensity)
                if role in ("drop", "finale"):
                    add_at(kick_s, kick_for(style, tier), t0 + 2.5 * beat, 0.62 * intensity)
                    add_at(kick_s, kick_for(style, tier), t0 + 3.25 * beat, 0.55 * intensity)
                add_at(snare_s, snare_for(style, 50 + m), t0 + 2 * beat, 0.62 * intensity)
                # 32nd stutter on the 4th beat: the edit that never resolves
                for q in range(4):
                    add_at(snare_s, snare_for(style, 70 + q),
                           t0 + 3 * beat + q * beat / 8.0,
                           (0.34 - 0.05 * q) * intensity)
                for q in range(8):
                    at = t0 + q * beat / 2.0
                    if q % 3 == 2:
                        continue          # holes in the hat pattern
                    add_at(hat_l if q % 2 else hat_r, hat_for(style, q == 7, 120 + q),
                           at, 0.24 * intensity)
                    if q % 2 and role in ("drop", "finale"):
                        add_at(hat_r, hat_for(style, False, 140 + q), at + beat / 4.0,
                               0.13 * intensity)
            elif style == "finale":
                # Double kick throughout, blast-beat snares in the last act.
                for b in range(4):
                    at = t0 + b * beat
                    add_at(kick_s, kick_for(style, tier), at, 0.95 * intensity)
                    add_at(kick_s, kick_for(style, tier), at + beat * 0.75, 0.60 * intensity)
                    if role in ("drop", "finale"):
                        add_at(kick_s, kick_for(style, tier), at + beat * 0.5, 0.52 * intensity)
                        add_at(snare_s, snare_for(style, 150 + b), at + beat * 0.5,
                               0.34 * intensity)
                    if b in (1, 3):
                        add_at(snare_s, snare_for(style, 160 + b), at, 0.68 * intensity)
                    for q in range(2):
                        add_at(hat_l if (q + b) % 2 else hat_r,
                               hat_for(style, q == 1, 170 + q + b * 2),
                               at + q * beat / 2.0, 0.24 * intensity)
                if role == "finale" and m % 2 == 1:
                    # 16th snare roll under the last bar of every other measure
                    for q in range(8):
                        add_at(snare_s, snare_for(style, 180 + q), t0 + 2 * beat + q * beat / 8.0,
                               0.20 * intensity)
            elif style == "industrial":
                # Four on the floor with ghost snares and a 16th ride.
                for b in range(4):
                    at = t0 + b * beat
                    add_at(kick_s, kick_for(style, tier), at, 0.92 * intensity)
                    if b in (1, 3):
                        add_at(snare_s, snare_for(style, 12 + b), at, 0.5 * intensity)
                        add_at(snare_s, snare_for(style, 30 + b), at + beat / 2.0, 0.18 * intensity)
                    for q in range(4):
                        add_at(hat_l if (q + b) % 2 else hat_r,
                               hat_for(style, q == 3, 100 + q + b * 4),
                               at + q * beat / 4.0, 0.19 * intensity)
                if role in ("drop", "finale"):
                    add_at(kick_s, kick_for(style, tier), t0 + 3.5 * beat, 0.55 * intensity)
            else:
                for b in range(4):
                    at = t0 + b * beat
                    if b in (0, 2) or (role in ("drop", "finale") and b == 3 and tier >= 2):
                        add_at(kick_s, kick_for(style, tier), at, 0.95 * intensity)
                    if b in (1, 3):
                        add_at(snare_s, snare_for(style, 12 + b), at, 0.55 * intensity)
                    add_at(hat_l, hat_for(style, False, 13 + b), at, 0.26 * intensity)
                    add_at(hat_r, hat_for(style, True, 14 + b), at + beat / 2.0, 0.20 * intensity)
                    # air band: bright sizzle, one per beat, alternating sides
                    air_n = int(0.05 * SR)
                    air_t = np.arange(air_n) / SR
                    air = bandpass(noise(air_n, seed=90 + b), 9000.0, 16000.0) * np.exp(-air_t * 55.0)
                    add_at(hat_l if b % 2 == 0 else hat_r, air, at, 0.17 * intensity)
                    add_at(hat_r if b % 2 == 0 else hat_l, air, at + beat / 2.0, 0.14 * intensity)
                    if role in ("drop", "finale") or tier >= 3:
                        add_at(hat_l, hat_for(style, False, 15 + b), at + beat / 4.0, 0.12 * intensity)
                        add_at(hat_r, hat_for(style, False, 19 + b), at + 3 * beat / 4.0,
                               0.12 * intensity)
                if role in ("drop", "finale"):
                    add_at(kick_s, kick_for(style, tier), t0 + 3.5 * beat, 0.6 * intensity)
        elif role == "break":
            add_at(kick_s, kick_for(style, tier), t0, 0.7)
            add_at(snare_s, snare_for(style, 61), t0 + 2 * beat, 0.4)
            for b in range(4):
                add_at(hat_r, hat_for(style, True, 20 + b), t0 + b * beat, 0.12)
        else:   # intro
            add_at(kick_s, kick_for(style, tier), t0, 0.6)
            for b in range(4):
                add_at(hat_r, hat_for(style, False, 30 + b), t0 + b * beat + beat / 2.0, 0.12)

        # Air band: a bright sizzle on the off-beats keeps the top end alive in
        # every style (trap hats alone measure far too dark).
        if role in ("verse", "build", "drop", "finale"):
            air_n = int(0.045 * SR)
            air = bandpass(noise(air_n, seed=300 + m), 10000.0, 16500.0) * exp_decay(air_n, 0.03)
            for b in range(2, 5):
                gain = 0.20 if style == "trap" else (0.16 if style == "industrial" else 0.14)
                add_at(hat_l if b % 2 == 0 else hat_r, air, t0 + (b - 1) * beat + beat * 0.5,
                       gain * intensity)

        # Texture the style is known for.
        if style == "glitch" and role in ("verse", "build", "drop", "finale"):
            if m % 2 == 0:
                # tape-stop chunk: a burst of the bar, pitched down and gated
                g_n = int(beat * 0.9 * SR)
                gt = np.arange(g_n) / SR
                chunk = bandpass(noise(g_n, seed=230 + m), 600.0, 5200.0)
                chunk = bitcrush(chunk * np.exp(-gt * 8.0), bits=4, hold=11)
                add_at(fx_s, chunk, t0 + 3 * beat + beat * 0.25, 0.11)
        elif style == "finale" and role in ("drop", "finale"):
            # Low gong hit on the downbeat of the last act.
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
        elif style == "trap" and role in ("build", "drop") and m % 4 == 0:
            # reversed cymbal swell into the next bar
            rev_n = int(beat * 1.2 * SR)
            rev = crash(beat * 1.2, seed=210 + m)[::-1][:rev_n]
            add_at(fx_s, rev, t0 + 4 * beat - beat * 1.2, 0.16)
        elif style == "bounce" and role == "verse" and m % 2 == 1:
            # clave/woodblock answer on the off-beat
            blk_n = int(0.06 * SR)
            blk = np.sin(2 * np.pi * 1180.0 * np.arange(blk_n) / SR) * exp_decay(blk_n, 0.02)
            add_at(hat_r, blk, t0 + 2.5 * beat, 0.10)

        # Transition: fill the last beat, crash + riser into a bigger section.
        if m + 1 < total_measures and measure_role.get(m + 1) != role:
            upcoming = measure_role.get(m + 1, role)
            if ROLE_GAIN[upcoming] >= ROLE_GAIN[role]:
                drum_fill(t0 + 3 * beat, beat, loudness=0.7 + 0.3 * tier)
                crash_at = t0 + 4 * beat
                add_at(fx_s, crash(1.8, seed=80 + m), crash_at, 0.20 + 0.05 * tier)
                riser_n = int(beat * 2.0 * SR)
                rt = np.arange(riser_n) / SR
                riser = bandpass(noise(riser_n, seed=81 + m), 500.0, 9000.0) * (rt / rt[-1]) ** 2
                add_at(fx_s, riser, crash_at - beat * 2.0, 0.10 + 0.04 * tier)

    # ---- groove polish: ghosts, accents and fills -------------------------- #
    # Real drum programming is 20 % notes and 80 % the quiet stuff between them.
    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        if role not in ("verse", "build", "drop", "finale"):
            continue
        intensity = ROLE_GAIN[role]
        nudge, velocity = human(m, beat)
        # Ghost snares on the "e" and "a" of the beat: felt, not heard.
        for beat_index in (1, 3):
            for fraction in (0.25, 0.75):
                if role == "verse" and fraction == 0.25:
                    continue
                add_at(snare_s, snare_for(style, 300 + m * 4 + beat_index),
                       t0 + beat_index * beat + fraction * beat,
                       0.09 * intensity * velocity)
        # Open hat as the bar turns around, every second bar.
        if m % 2 == 1:
            add_at(hat_r, hat_for(style, True, 400 + m), t0 + 3.5 * beat,
                   0.16 * intensity)
        # A fill every eight bars, and always into a new role.
        if (m + 1) % 8 == 0:
            drum_fill(t0 + 3 * beat + nudge, beat, loudness=0.55 + 0.35 * tier, seed=500 + m)

    # ---- lead: literally the chart notes ---------------------------------- #
    lead_index = []
    for note in L.notes(song):
        at = note["time"] / 1000.0
        role = measure_role.get(note["measure"], "verse")
        dur = max(0.16, note["sLen"] / 1000.0 if note["sLen"] else step * 2.4)
        # The lead sings the chart's own note: same phrase, same octave, same
        # pitch the vocal track uses. The last act is lifted an octave by the
        # form (see song_layout.sections), not again here.
        midi = L.note_pitch(song, note["measure"], note["id"], semi=note.get("semi"))
        accent = 1.0 if note["time"] % (beat * 1000.0) < 1.0 else 0.85
        if style == "trap":
            dur *= 1.25        # bells ring, they do not stab
        # Swing the off-16ths and let every note sit a hair off the grid.
        nudge, velocity = human(len(lead_index), step, swing=0.14)
        lead_index.append(at)
        at = max(0.0, at + nudge)
        sig = lead_for(style, midi, dur, tier, note["id"])
        # Sub-oscillator an octave down: the lead gets a chest instead of being
        # a thin chip whistle.
        sub = lead_for(style, midi - 12, dur * 0.92, tier, note["id"])
        sub = np.pad(sub, (0, max(0, len(sig) - len(sub))))[:len(sig)]
        sig = sig + sub * 0.22
        target = lead_p if note["side"] == "player" else lead_o
        add_at(target, sig, at, 0.64 * accent * velocity * (0.75 + 0.35 * ROLE_GAIN[role]))
        # Finale: octave doubling makes the last act feel bigger.
        if role == "finale" and note["side"] == "player":
            add_at(target, lead_for(style, midi + 12, dur * 0.8, tier, note["id"]), at,
                   0.18 * accent)

    # ---- horror layers per tier ------------------------------------------- #
    # The ambient bed follows the arrangement too, or the quiet sections keep a
    # constant drone/hiss under them and lose their contrast.
    ambient = np.ones(n_total)
    for m in range(total_measures):
        start = int(L.measure_time(song, m) / 1000.0 * SR)
        end = min(n_total, int(L.measure_time(song, m + 1) / 1000.0 * SR))
        if end > start:
            ambient[start:end] = 0.35 + 0.65 * ROLE_GAIN.get(measure_role.get(m), 0.7)

    if tier >= 1:
        drone = lowpass(sine(43.0, n_total) * 0.030 * tier + saw(29.0, n_total) * 0.012 * tier, 150.0)
        fx_s += drone * ambient

    if tier >= 2:
        fx_s += highpass(noise(n_total, seed=61), 2600.0) * (0.014 if tier == 2 else 0.024) * ambient

    if tier >= 3:
        swell = bandpass(noise(n_total, seed=63), 400.0, 2600.0)
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)
        fx_s += swell * lfo * 0.035 * ambient

    if tier >= 4:
        # A breath under everything: slow filtered noise "in / out" + a distant
        # tritone drone that only the last two songs get.
        breath = bandpass(noise(n_total, seed=65), 300.0, 1800.0)
        blfo = np.sin(2 * np.pi * 0.19 * np.arange(n_total) / SR)
        fx_s += breath * np.maximum(0.0, blfo) * 0.045 * ambient
        tritone = sine(43.0 * 1.4142, n_total) * 0.020 + sine(43.0, n_total) * 0.018
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * 5.6 * np.arange(n_total) / SR)
        fx_s += lowpass(tritone * trem, 220.0) * ambient

    if tier >= 5:
        # The Incident: a heartbeat, whispers panned hard, and a choir root.
        beat_s = 60.0 / song["bpm"]
        hb_n = int(0.16 * SR)
        hbt = np.arange(hb_n) / SR
        thump = np.sin(2 * np.pi * np.cumsum(58.0 + 40.0 * np.exp(-hbt * 30.0)) / SR)
        thump *= np.exp(-hbt * 16.0)
        bar = 4 * beat_s
        t = 0.0
        while t < total - 0.5:
            add_at(fx_s, thump, t, 0.10 * ambient[min(n_total - 1, int(t * SR))])
            add_at(fx_s, thump * 0.7, t + 0.30, 0.10 * ambient[min(n_total - 1, int(t * SR))])
            t += bar
        whispers = highpass(noise(n_total, seed=67), 1800.0)
        wl = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * np.arange(n_total) / SR)
        fx_s += whispers * wl * 0.018 * ambient
        choir = pad_chord([song["tonic"] - 12, song["tonic"] - 5, song["tonic"]], total,
                          gain=0.030, cutoff=900.0)
        # pad_chord's tail rounds to the nearest sample; fit it to the song.
        choir = np.pad(choir, (0, max(0, n_total - len(choir))))[:n_total]
        fx_s += choir * ambient

    # Scripted stingers, aligned with the chart's story events.
    for seconds, func in song["events"]:
        at = max(0.0, seconds)
        if func == "trollgeJumpScare":
            add_at(fx_s, sub_drop(2.4), at - 0.05, 0.7)
            add_at(fx_s, crash(2.2, seed=71), at, 0.5)
            add_at(fx_s, screech(1.6), at, 0.35)
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
            add_at(fx_s, screech(2.2, seed=76), at, 0.45)
            add_at(fx_s, sub_drop(2.6, 190.0, 24.0), at, 0.6)
        else:  # trollgeStatic
            st_n = int(0.9 * SR)
            st = highpass(noise(st_n, seed=77), 2000.0) * np.exp(-np.arange(st_n) / (0.3 * SR))
            add_at(fx_s, st, at, 0.3)

    # ---- ending: land on a real chord instead of just fading out ---------- #
    end_at = total - 2.0 * beat
    root, tones = L.chord_for_measure(song, total_measures - 1)
    final_chord = [song["tonic"] + root + t + 12 for t in tones] + [song["tonic"] + root - 12]
    sting = pad_chord(final_chord, max(0.4, total - end_at), gain=0.16, cutoff=2600.0)
    add_at(pad_l, sting, end_at, 0.8)
    add_at(pad_r, sting, end_at, 0.8)
    add_at(fx_s, crash(2.0, seed=91), end_at, 0.32)
    add_at(fx_s, sub_drop(1.8, 150.0, 26.0), end_at, 0.42)
    add_at(kick_s, kick(drive=2.0), end_at, 0.8)

    # ---- stereo mix ------------------------------------------------------- #
    # One reverb + one delay pass, both mono sends: wide, cheap and predictable.
    lead_send = 0.5 * (lead_p + lead_o)
    # One reverb serves both the leads and a snare room: the snare stays dry in
    # the centre while its tail spreads across the stereo field (see haas below).
    wet = reverb(lead_send + 0.5 * snare_s, wet=0.34, size=0.95)
    echo = delay(lead_send, beat * 0.75, feedback=0.26, mix=0.20 + 0.04 * tier)
    del lead_send
    wet_l, wet_r = haas(wet, 0.013)
    echo_l = echo
    echo_r = np.roll(echo, int(0.19 * beat * SR))
    del wet, echo

    key = kick_s
    pad_l = sidechain(pad_l, key, depth=0.5)
    pad_r = sidechain(pad_r, key, depth=0.5)
    bass_s = sidechain(bass_s, key, depth=0.35)

    if tier >= 3:
        # Later songs get a slightly narrower hat, not a crushed one: the old
        # bitcrush here was adding most of the 3-8 kHz grit the owner heard.
        cut = int(len(hat_l) * 0.62)
        for channel in (hat_l, hat_r):
            channel[cut:] = lowpass(channel[cut:], 9000.0) * 0.85 + channel[cut:] * 0.15

    def fit(x):
        x = dc_block(np.asarray(x[:n_total], dtype=np.float64))
        tail = int(0.25 * SR)
        x[-tail:] *= np.linspace(1.0, 0.0, tail)
        return x

    # Pan table (left, right). Wide parts differ per side; the kick stays dead centre.
    stems = {
        "kick": (kick_s, 0.66, 0.66),
        "snare": (snare_s, 0.60, 0.60),
        "hat_l": (hat_l, 0.54, 0.18),
        "hat_r": (hat_r, 0.18, 0.54),
        "bass": (bass_s, 0.56, 0.56),
        "pad_l": (pad_l, 0.48, 0.18),
        "pad_r": (pad_r, 0.18, 0.48),
        "lead_o": (lead_o, 0.54, 0.30),
        "lead_p": (lead_p, 0.30, 0.54),
        "fx": (fx_s, 0.50 if tier >= 2 else 0.42, 0.50 if tier >= 2 else 0.42),
        "wet_l": (wet_l, 0.42, 0.05),
        "wet_r": (wet_r, 0.05, 0.42),
        "echo_l": (echo_l, 0.32, 0.05),
        "echo_r": (echo_r, 0.05, 0.32),
    }

    left = np.zeros(n_total)
    right = np.zeros(n_total)
    for name in list(stems):
        signal, gl, gr = stems.pop(name)
        signal = fit(signal)
        left += signal * gl
        right += signal * gr
        del signal

    # Master EQ: the audit target is a mix with a top end, not a sub wall.
    # The 1-4 kHz pocket: a dip through the band the vocal formants occupy, so
    # Voices.ogg sits *on top of* the instrumental instead of competing with it.
    # Everything above 5 kHz is pulled back rather than lifted -- the old 4-6 dB
    # air boost was the main source of the "shrill, fatiguing" top end.
    master_points = [(26.0, -22.0), (40.0, -16.0), (55.0, -12.5), (70.0, -9.5),
                     (90.0, -7.5), (120.0, -5.0), (180.0, -2.5), (250.0, -2.6),
                     (320.0, -3.4), (450.0, -2.8), (650.0, -1.4), (800.0, 0.2),
                     (1400.0, -1.5), (2000.0, -2.2), (3000.0, -1.8), (4000.0, -0.8),
                     (6000.0, 1.6), (8000.0, 3.6), (10000.0, 5.2), (12000.0, 5.4),
                     (15000.0, 4.0), (18000.0, 1.6)]
    left = eq_curve(left, master_points)
    right = eq_curve(right, master_points)
    # Tape: a touch of harmonic grit and a soft top-end, so the stems glue
    # together instead of reading as separate layers.
    left = soft_clip(left * 1.16, 1.02) * 0.88
    right = soft_clip(right * 1.16, 1.02) * 0.88
    # Glue compression (gentle: only the loudest peaks, so the quiet sections
    # keep their space) -> width -> loudness target -> limiter.
    left = compress(left, threshold_db=-15.0, ratio=2.0, makeup_db=2.0)
    right = compress(right, threshold_db=-15.0, ratio=2.0, makeup_db=2.0)
    # Parallel compression: a smashed copy of the mid blended back in, which is
    # what makes drums feel loud without eating the dynamic range.
    crushed = compress(0.5 * (left + right), threshold_db=-28.0, ratio=5.0, makeup_db=7.0)
    left = left + crushed * 0.16
    right = right + crushed * 0.16
    left, right = widen(left, right, amount=2.2 + 0.2 * tier)

    loudness = float(np.sqrt(0.5 * (np.mean(left ** 2) + np.mean(right ** 2))))
    scale = TARGET_RMS / max(loudness, 1e-9)
    left, right = left * scale, right * scale
    # Vorbis overshoots the source peak by up to ~1 dB on dense material, so
    # leave 2 dB of headroom: the decoded peak has to stay below 0 dBFS.
    left, right = limiter(left, 0.84), limiter(right, 0.84)

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    if peak > 0.80:
        trim = 0.80 / peak
        left, right = left * trim, right * trim
    return left, right


def render_vocals(song):
    """The characters' vocal track -- `song/Voices.ogg`.

    Base-game songs ship one Voices track: the opponent sings the opponent's
    phrase blocks and the player sings theirs. Codename only loads it when
    `meta.needsVoices` is true *and* `songs/<song>/song/Voices.ogg` exists
    (PlayState -> Paths.voices), so without this file the characters mouth the
    lyrics in silence.

    Both characters are formant voices (`voice_note`): the player bright and
    clean, the Trollge with shifted-down formants, sub-harmonic weight and a
    controlled growl. The vowel changes note to note, and the two characters use
    different vowel sets, which is most of what makes this read as singing.
    """
    total = L.length(song)
    n_total = int(round(total * SR))
    step = L.step(song)
    player = empty(total)
    opponent = empty(total)

    for index, note in enumerate(L.notes(song)):
        at = note["time"] / 1000.0
        dur = max(0.20, note["sLen"] / 1000.0 if note["sLen"] else step * 2.2)
        midi = L.note_pitch(song, note["measure"], note["id"], semi=note.get("semi"))
        if note["side"] == "player":
            vowel = PLAYER_VOWELS[note["id"] % len(PLAYER_VOWELS)]
            add_at(player, voice_note(midi, dur, dark=False, vowel=vowel,
                                      seed=index, scoop=0.030, vibrato=0.011), at, 1.0)
        else:
            vowel = TROLLGE_VOWELS[note["id"] % len(TROLLGE_VOWELS)]
            add_at(opponent, voice_note(midi - 12, dur * 1.02, dark=True, vowel=vowel,
                                        seed=index + 17, scoop=0.040, vibrato=0.0085,
                                        growl=0.55), at, 1.0)

    # One plate for both singers, spread with a few ms of side delay.
    wet = reverb(0.35 * (player + opponent), wet=0.24, size=0.72)
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
    # The vocal bus is finished with a presence lift and a de-harshed top: the
    # voices have to cut through the 1-4 kHz pocket the instrumental leaves open
    # (see render_song), not fight the cymbals above it.
    vocal_eq = [(90.0, -6.0), (180.0, -1.0), (400.0, 1.5), (1100.0, 2.5),
                (2600.0, 3.0), (4200.0, 1.5), (7000.0, -1.5), (10000.0, -4.0), (16000.0, -6.0)]
    left = eq_curve(left, vocal_eq)
    right = eq_curve(right, vocal_eq)
    # Soft knee: tame the peaks the formant bank leaves, keep the body.
    left = compress(left, threshold_db=-18.0, ratio=2.2, attack_ms=6.0,
                    release_ms=90.0, makeup_db=1.5)
    right = compress(right, threshold_db=-18.0, ratio=2.2, attack_ms=6.0,
                     release_ms=90.0, makeup_db=1.5)
    # -7.5 dBFS RMS against the instrumental's -14: the voice sits clearly on
    # top, which audit_songs.py measures rather than assumes.
    rms = float(np.sqrt(0.5 * (np.mean(left ** 2) + np.mean(right ** 2))))
    target = TARGET_RMS * 10.0 ** (6.5 / 20.0)
    scale = target / max(rms, 1e-9)
    left, right = limiter(left * scale, 0.86), limiter(right * scale, 0.86)
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    if peak > 0.82:
        left, right = left * (0.82 / peak), right * (0.82 / peak)
    return left, right


def render_game_over():
    """The death screen: `music/gameOver.ogg` + its two stingers.

    Codename's GameOverSubstate does exactly this much --
    `CoolUtil.playMusic(Paths.music("gameOver"))`, `Paths.sound("gameOverSFX")` on
    the mic-drop, `Paths.sound("gameOverEnd")` on retry -- so shipping these three
    files reskins every death in the mod. `music/gameOver.ini` carries the BPM the
    engine uses to drive `beatHit` on the game-over state.
    """
    bpm = 76.0
    beat = 60.0 / bpm
    total = 16.0
    n_total = int(total * SR)
    mono = np.zeros(n_total)

    # A held D minor drone with a tritone floating on top: the same "nothing
    # resolves" harmony as The Incident, slowed to a crawl.
    mono += pad_chord([38, 45, 50, 53], total, gain=0.30, cutoff=900.0)[:n_total]
    tritone = sine(38.0 * 1.4142, n_total) * 0.05
    tritone *= 0.55 + 0.45 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)
    mono += lowpass(tritone, 300.0)

    # Heartbeat, one pair per bar.
    hb_n = int(0.18 * SR)
    hbt = np.arange(hb_n) / SR
    thump = np.sin(2 * np.pi * np.cumsum(58.0 + 44.0 * np.exp(-hbt * 26.0)) / SR)
    thump *= np.exp(-hbt * 15.0)
    t = 0.0
    while t < total - 0.4:
        add_at(mono, thump, t, 0.30)
        add_at(mono, thump * 0.65, t + 0.30, 0.30)
        t += 4 * beat

    # A music box picking out the Trollge motif, wrong on purpose (minor 2nd).
    for index, at in enumerate((0.6, 2.4, 4.2, 6.6, 9.0, 11.4, 13.8)):
        midi = (62, 61, 57, 50, 56, 49, 45)[index]
        add_at(mono, music_box(midi, 2.2), at, 0.34)

    # Tape hiss and a breath, so silence never feels digital.
    mono += highpass(noise(n_total, seed=311), 2600.0) * 0.012
    breath = bandpass(noise(n_total, seed=313), 300.0, 1500.0)
    mono += breath * (0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * np.arange(n_total) / SR)) * 0.02

    mono = reverb(mono, wet=0.42, size=1.0)
    mono = mono[:n_total]
    mono = eq_curve(mono, [(60.0, 2.0), (200.0, 1.0), (900.0, 1.5), (3000.0, -1.0),
                           (9000.0, 1.0), (16000.0, 2.5)])
    mono = normalize(mono, 0.86)
    left, right = widen(mono, mono, amount=1.4)

    # Death sting: the mic drop, a sub hit and a burst of static.
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

    # Retry whoosh: a reverse swell that cuts out.
    n = int(0.9 * SR)
    rt = np.arange(n) / SR
    whoosh = bandpass(noise(n, seed=317), 500.0, 11000.0) * (rt / rt[-1]) ** 3
    whoosh += sine(520.0 * np.exp(-rt * 2.2), n) * 0.25 * (rt / rt[-1]) ** 2
    whoosh = normalize(fade(whoosh, 0.01, 0.18), 0.82)
    return (left, right), sting, whoosh


def write_song(path, left, right, ceiling=0.95, attempts=4):
    """Encode, then decode and re-check: Vorbis overshoots, so clipping is only
    proven gone when the *decoded* file measures clean."""
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


# --------------------------------------------------------------------------- #
# Shared music + SFX
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
        buf = reverb(buf, wet=0.55, size=1.0)
        buf = bitcrush(buf, bits=7, hold=2) * 0.7 + buf * 0.3
        warp_n = len(buf)
        warp = 1.0 + 0.012 * np.sin(2 * np.pi * 0.35 * np.arange(warp_n) / SR)
        buf = np.interp(np.cumsum(warp), np.arange(warp_n), buf)
        buf += highpass(noise(len(buf), seed=42), 9000.0) * 0.02
    else:
        buf = reverb(buf, wet=0.4, size=0.8)

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
    """One short vocal syllable per character per arrow.

    The engine plays no sound at all when a note is hit (it only plays miss
    sounds), so the charts would be silent while both sides sing. These are the
    hits: Boyfriend gets a bright nasal syllable, the Trollge a low growling one,
    and the pitch follows the arrow (up is highest, down is lowest) so a stream
    of arrows reads as a melody instead of a click track.
    """
    out = {}
    pitches = {"up": 1.26, "down": 0.79, "left": 0.94, "right": 1.12}

    for name, mult in pitches.items():
        # --- Boyfriend -----------------------------------------------------
        n = int(0.24 * SR)
        t = np.arange(n) / SR
        f0 = 232.0 * mult * (1.0 + 0.05 * np.exp(-t * 34.0))
        src = saw(f0, n) * 0.55 + square(f0, n, duty=0.42) * 0.30
        voice = bandpass(src, 500.0, 980.0) + bandpass(src, 1050.0, 2100.0) * 0.55
        env = adsr(n, attack=0.007, decay=0.045, sustain=0.42, release=0.085)
        out["bf_note_" + name] = normalize(fade(soft_clip(voice * env, 1.15), 0.004, 0.05), 0.62)

        # --- Trollge -------------------------------------------------------
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
    """READY / SET / GO hits. The engine asks for intro3, intro2, intro1, introGo."""
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
    blast[:n] += screech(n / SR, seed=96)[:n] * 0.35
    blast[:n] += bandpass(noise(n, seed=97), 1500.0, 11000.0) * exp_decay(n, 0.3) * 0.5
    out["introGo"] = normalize(fade(soft_clip(blast, 2.4), 0.002, 0.35), 0.93)
    return out


def main():
    os.makedirs(SFX_DIR, exist_ok=True)

    for song in L.SONGS:
        song_dir = os.path.join(MOD, "songs", song["id"], "song")
        os.makedirs(song_dir, exist_ok=True)
        print("Rendering %-14s (%0.1fs, %0.0f BPM, scare %d/10)..."
              % (song["display"], L.length(song), song["bpm"], song["scare"]))
        left, right = render_song(song)
        path = os.path.join(song_dir, "Inst.ogg")
        write_song(path, left, right)
        print("  -> %-44s %6.1f KB" % (os.path.relpath(path, ROOT), os.path.getsize(path) / 1024))
        del left, right
        vleft, vright = render_vocals(song)
        vpath = os.path.join(song_dir, "Voices.ogg")
        write_song(vpath, vleft, vright)
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

    # The same music box loop, in `music/` this time: `CoolUtil.playMenuSong()`
    # plays `Paths.music(Flags.DEFAULT_MENU_MUSIC)`, and modpack.ini points that
    # flag here, so every menu (main, freeplay, story) plays the mod's theme.
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
