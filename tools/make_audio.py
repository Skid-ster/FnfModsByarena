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

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L  # noqa: E402
from lib_dsp import (  # noqa: E402
    SR, add_at, adsr, bandpass, bitcrush, delay, empty, exp_decay, fade, highpass,
    lowpass, midi_to_hz, noise, normalize, reverb, saw, sine, soft_clip, square,
    write_ogg,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
SFX_DIR = os.path.join(MOD, "sounds")


# --------------------------------------------------------------------------- #
# Instruments
# --------------------------------------------------------------------------- #

def kick(dur=0.38, drive=1.7):
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = 46.0 + 110.0 * np.exp(-t * 26.0)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 6.5)
    click = noise(n, seed=11) * np.exp(-t * 320.0) * 0.35
    return soft_clip(body + click, drive)


def snare(dur=0.26, seed=12):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 186.0 * t) * np.exp(-t * 34.0) * 0.5
    rattle = bandpass(noise(n, seed=seed) * np.exp(-t * 17.0), 850.0, 7200.0)
    return soft_clip((tone + rattle) * 1.25, 1.1)


def hat(dur=0.07, open_=False, seed=13):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * (9.0 if open_ else 60.0))
    return highpass(noise(n, seed=seed) * env, 6500.0) * 0.45


def crash(dur=1.8, seed=14):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return highpass(noise(n, seed=seed), 3200.0) * np.exp(-t * 2.4) * 0.5


def sub_drop(dur=2.2, f0=170.0, f1=28.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 2.6)
    return soft_clip(np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 1.3), 1.4)


def screech(dur=1.4, seed=51):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 1500.0 + 700.0 * np.sin(2 * np.pi * 5.5 * t) + 260.0 * np.sin(2 * np.pi * 0.7 * t)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    tone += np.sin(2 * np.pi * np.cumsum(f * 1.51) / SR) * 0.4
    return soft_clip(tone * exp_decay(n, dur * 0.35), 2.0) * 0.5


def bass_note(midi, dur, drive=1.5):
    n = int(max(dur, 0.05) * SR)
    f = midi_to_hz(midi)
    body = saw(f, n) * 0.55 + sine(f, n) * 0.75 + sine(f / 2.0, n) * 0.3
    env = adsr(n, attack=0.004, decay=0.09, sustain=0.72, release=0.05)
    return soft_clip(lowpass(body * env, 480.0), drive)


def lead_note(midi, dur, bright=True, drive=1.25, detune=1.0038, grit=0.0):
    n = int(max(dur, 0.08) * SR)
    f = midi_to_hz(midi)
    voice = (
        saw(f, n) * 0.42
        + saw(f * detune, n, phase0=1.1) * 0.34
        + square(f * 0.5, n, duty=0.35) * 0.22
        + sine(f * 2.0, n) * 0.12
    )
    if grit > 0:
        # Tritone + fifth -> instantly unpleasant on purpose.
        voice += saw(f * 1.4142, n) * 0.18 * grit
        voice += square(f * 1.5, n, duty=0.2) * 0.12 * grit
    env = adsr(n, attack=0.004, decay=0.11, sustain=0.42, release=0.12)
    out = lowpass(voice * env, 4600.0 if bright else 2300.0)
    return soft_clip(out, drive) * 0.5


def pad_chord(midis, dur, gain=0.075, cutoff=1500.0):
    n = int(dur * SR)
    out = np.zeros(n)
    for midi in midis:
        f = midi_to_hz(midi)
        for mult, amp in ((1.0, 1.0), (1.005, 0.7), (0.995, 0.7), (2.0, 0.25)):
            out += saw(f * mult, n, phase0=f) * amp
    env = adsr(n, attack=dur * 0.35, decay=dur * 0.15, sustain=0.55, release=dur * 0.35)
    return lowpass(out * env, cutoff) * gain / max(1, len(midis))


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

def render_song(song):
    total = L.length(song)
    n_total = int(round(total * SR))
    beat = L.beat(song)
    measure = L.measure(song)
    scare = song["scare"]
    tier = 1 if scare <= 2 else (2 if scare <= 4 else 3)
    grit = {1: 0.0, 2: 0.35, 3: 1.0}[tier]

    drums = empty(total)
    bass = empty(total)
    lead_o = empty(total)
    lead_p = empty(total)
    pads = empty(total)
    fx = empty(total)

    secs = L.sections(song)
    dense_measures = set()
    for s in secs:
        if s["measures"] <= 2:
            dense_measures.update(range(s["_measure_start"] if "_measure_start" in s
                                        else int(s["time"] / 1000.0 / measure), 0))

    # Work out dense measures directly from the measure index instead.
    dense_measures = set()
    for sec in secs:
        m0 = int(round(sec["time"] / 1000.0 / measure))
        if sec["measures"] <= 2:
            dense_measures.update(range(m0, m0 + sec["measures"]))

    # ---- pads + bass + drums ---------------------------------------------- #
    for m in range(L.measures(song)):
        t0 = L.measure_time(song, m) / 1000.0
        root, tones = L.chord_for_measure(song, m)
        is_dense = m in dense_measures

        chord = [song["tonic"] + root + t for t in tones]
        add_at(pads, pad_chord(chord, measure * 1.02, gain=0.085 if tier < 3 else 0.1,
                               cutoff=1300.0), t0)

        # Bass.
        for i in range(8):
            at = t0 + i * beat / 2.0
            octave = 0 if i % 4 else -12
            dur = beat / 2.0 * (0.92 if i % 2 else 1.1)
            add_at(bass, bass_note(song["tonic"] + root + octave, dur, drive=1.4 + 0.5 * tier),
                   at, 0.5)

        # Drums.
        for b in range(4):
            at = t0 + b * beat
            if b in (0, 2):
                add_at(drums, kick(drive=1.5 + 0.4 * tier), at, 1.0)
            else:
                add_at(drums, snare(seed=12 + b), at, 0.5 + 0.1 * tier)
            add_at(drums, hat(), at, 0.45)
            add_at(drums, hat(open_=True), at + beat / 2.0, 0.3 + 0.1 * tier)
            if is_dense or tier >= 3:
                add_at(drums, hat(seed=15 + b), at + beat / 4.0, 0.18 + 0.05 * tier)
                add_at(drums, hat(seed=19 + b), at + 3 * beat / 4.0, 0.18 + 0.05 * tier)
        if is_dense or tier == 3:
            add_at(drums, kick(drive=2.0), t0 + 3 * beat / 2.0, 0.65)
        if tier == 3:
            add_at(drums, snare(seed=31), t0 + 7 * beat / 2.0, 0.35)
            add_at(drums, crash(0.6, seed=32), t0, 0.08)

    # ---- lead: literally the chart notes ---------------------------------- #
    for note in L.notes(song):
        at = note["time"] / 1000.0
        dur = max(0.15, note["sLen"] / 1000.0 if note["sLen"] else L.step(song) * 2.2)
        section_octave = 1 if note["measure"] >= L.measures(song) * 0.72 else 0
        midi = L.note_pitch(song, note["measure"], note["id"], section_octave)
        sig = lead_note(
            midi,
            dur,
            bright=tier < 3,
            drive=1.2 + 0.35 * tier,
            detune=1.0038 + 0.004 * (tier - 1) * (1 if note["id"] % 2 else -1),
            grit=grit,
        )
        if note["side"] == "player":
            add_at(lead_p, sig, at, 0.85)
        else:
            add_at(lead_o, sig, at, 0.72)

    # ---- horror layers per tier ------------------------------------------- #
    # Low dread drone.
    drone = sine(43.0, n_total) * 0.05 * tier + saw(29.0, n_total) * 0.02 * tier
    drone = lowpass(drone, 160.0)
    fx += drone

    if tier >= 2:
        # Constant tape hiss, louder the scarier it gets.
        hiss = highpass(noise(n_total, seed=61), 3000.0)
        fx += hiss * (0.012 if tier == 2 else 0.026)

    if tier >= 3:
        # Whispery noise swells scrolling under the whole song.
        swell = bandpass(noise(n_total, seed=62), 400.0, 2600.0)
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)
        fx += swell * lfo * 0.05

    # Scripted stingers, aligned with the chart's story events.
    for seconds, func in song["events"]:
        at = max(0.0, seconds)
        if func == "trollgeJumpScare":
            add_at(fx, sub_drop(2.4), at - 0.05, 0.85)
            add_at(fx, crash(2.2, seed=71), at, 0.65)
            add_at(fx, screech(1.6), at, 0.5)
            blast_n = int(0.8 * SR)
            blast = bandpass(noise(blast_n, seed=72), 500.0, 9000.0) * exp_decay(blast_n, 0.2)
            add_at(fx, soft_clip(blast, 2.0), at, 0.5)
        elif func == "trollgeScreenShake":
            add_at(fx, crash(1.6, seed=73), at, 0.55)
            add_at(fx, sub_drop(1.8, 140.0, 32.0), at, 0.5)
        elif func == "trollgeDistort":
            glitch_n = int(1.1 * SR)
            glitch = bitcrush(square(60.0, glitch_n, duty=0.2) * exp_decay(glitch_n, 0.5), bits=4, hold=6)
            add_at(fx, glitch * 0.3, at, 0.8)
        elif func == "trollgeInvert":
            riser_n = int(2.4 * SR)
            rt = np.arange(riser_n) / SR
            riser = bandpass(noise(riser_n, seed=74), 300.0, 8000.0) * (rt / rt[-1]) ** 2
            add_at(fx, riser * 0.45, max(0.0, at - 2.4), 0.85)
            add_at(fx, sub_drop(2.0, 200.0, 35.0), at, 0.7)
        elif func == "trollgePhase2":
            add_at(fx, crash(2.6, seed=75), at, 0.7)
            add_at(fx, screech(2.2, seed=76), at, 0.65)
            add_at(fx, sub_drop(2.6, 190.0, 24.0), at, 0.8)
        else:  # trollgeStatic
            st_n = int(0.9 * SR)
            st = highpass(noise(st_n, seed=77), 2000.0) * np.exp(-np.arange(st_n) / (0.3 * SR))
            add_at(fx, st * 0.4, at, 0.7)

    # Intro + outro punctuation.
    intro_n = int(song["offset"] * SR) + SR
    intro = bandpass(noise(intro_n, seed=78), 200.0, 5000.0) * np.linspace(0, 1, intro_n) ** 3
    add_at(fx, intro * (0.18 + 0.05 * tier), 0.0, 1.0)
    add_at(fx, crash(2.0, seed=79), 0.0, 0.3)

    # ---- mixing ----------------------------------------------------------- #
    lead_o = reverb(lead_o, wet=0.28 + 0.05 * tier, size=0.9)
    lead_p = reverb(lead_p, wet=0.28 + 0.05 * tier, size=0.9)
    lead_o = delay(lead_o, beat * 0.75, feedback=0.28, mix=0.2 + 0.05 * tier)
    lead_p = delay(lead_p, beat * 0.75, feedback=0.28, mix=0.2 + 0.05 * tier)
    pads = reverb(pads, wet=0.35, size=1.0)

    if tier == 3:
        # The drums themselves start to break down halfway through.
        cut = int(len(drums) * 0.45)
        drums[cut:] = bitcrush(drums[cut:], bits=7, hold=2) * 0.8 + drums[cut:] * 0.2

    left = drums * 0.9 + bass * 0.95 + pads * 0.75 + lead_o * 0.9 + lead_p * 1.0 + fx * 0.9
    right = drums * 0.9 + bass * 0.95 + pads * 0.75 + lead_o * 1.0 + lead_p * 0.9 + fx * 0.9

    left = soft_clip(left * (0.6 + 0.03 * tier), 1.05)
    right = soft_clip(right * (0.6 + 0.03 * tier), 1.05)

    def fit(x):
        x = x[:n_total]
        if len(x) < n_total:
            x = np.pad(x, (0, n_total - len(x)))
        fade_n = int(0.9 * SR)
        x[-fade_n:] *= np.linspace(1.0, 0.0, fade_n) ** 1.5
        return x

    left, right = fit(left), fit(right)
    peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
    gain = 0.84 / peak if peak else 1.0
    return left * gain, right * gain


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


def main():
    os.makedirs(SFX_DIR, exist_ok=True)

    for song in L.SONGS:
        song_dir = os.path.join(MOD, "songs", song["id"], "song")
        os.makedirs(song_dir, exist_ok=True)
        print("Rendering %-14s (%0.1fs, %0.0f BPM, scare %d/10)..."
              % (song["display"], L.length(song), song["bpm"], song["scare"]))
        left, right = render_song(song)
        path = os.path.join(song_dir, "Inst.ogg")
        write_ogg(path, (left, right))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(path, ROOT), os.path.getsize(path) / 1024))

    print("Rendering ambient themes...")
    for name, scary in (("trollge_theme", False), ("trollge_theme_scary", True)):
        buf = render_theme(scary=scary)
        p = os.path.join(SFX_DIR, name + ".ogg")
        write_ogg(p, (buf, buf))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))

    print("Rendering SFX...")
    for name, buf in render_sfx().items():
        p = os.path.join(SFX_DIR, name + ".ogg")
        buf = np.clip(buf * 0.72, -1.0, 1.0)
        write_ogg(p, (buf, buf))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))


if __name__ == "__main__":
    main()
