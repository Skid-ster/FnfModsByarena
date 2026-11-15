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
    SR, add_at, adsr, bandpass, bitcrush,
    dc_block, delay, empty, eq_curve, exp_decay, fade, haas, highpass, limiter,
    compress, lowpass, midi_to_hz, noise, normalize, pan, reverb, saw, sidechain,
    sine, soft_clip, square, widen, write_ogg,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
SFX_DIR = os.path.join(MOD, "sounds")

#: Loudness the instrumentals are mastered to (RMS, linear). -15.5 dBFS is loud
#: enough for a game mix without squashing the quiet sections.
TARGET_RMS = 10.0 ** (-14.0 / 20.0)


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

#: How hard each part of the arrangement pushes, by section role.
ROLE_GAIN = {
    "intro": 0.26,
    "verse": 0.70,
    "build": 0.86,
    "drop": 1.00,
    "break": 0.36,
    "finale": 1.08,
}


def section_roles(song):
    """Label every chart section so the arrangement builds, drops and breathes.

    Derived from the layout (section count + note spacing) so editing
    `song_layout.py` re-arranges the music for free: an intro, a mid-song
    breakdown, a breath before the finale, and drops wherever the chart gets dense.
    """
    count = len(song["spacings"])
    roles = []
    for i, spacing in enumerate(song["spacings"]):
        position = i / max(1, count - 1)
        if i == 0:
            role = "intro"
        elif i >= count - 2:
            role = "finale"
        elif 0.46 <= position <= 0.54:
            role = "break"          # mid-song breakdown
        elif 0.84 <= position <= 0.90:
            role = "break"          # the breath before the last act
        elif spacing <= 2:
            role = "drop"
        elif i % 4 == 2:
            role = "build"
        else:
            role = "verse"
        roles.append(role)
    return roles


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
    tier = 1 if scare <= 2 else (2 if scare <= 4 else 3)

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
        gain = 0.075 * ROLE_GAIN[role]
        sig = pad_chord(chord, measure * 1.04, gain=gain, cutoff=cutoff)
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

        level = 0.46 * (0.5 + 0.5 * ROLE_GAIN[role])
        for offset_s, octave, dur in pattern:
            add_at(bass_s, bass_note(base + octave, dur, drive=drive), t0 + offset_s, level)

    # ---- drums ------------------------------------------------------------ #
    def drum_fill(at, length, loudness=1.0, seed=40):
        hits = 8
        for i in range(hits):
            add_at(snare_s, snare(seed=seed + i), at + length * i / hits,
                   (0.16 + 0.22 * i / hits) * loudness)

    for m in range(total_measures):
        t0 = L.measure_time(song, m) / 1000.0
        role = measure_role.get(m, "verse")
        intensity = ROLE_GAIN[role]

        if role in ("verse", "build", "drop", "finale"):
            for b in range(4):
                at = t0 + b * beat
                if b in (0, 2) or (role in ("drop", "finale") and b == 3 and tier >= 2):
                    add_at(kick_s, kick(drive=1.4 + 0.4 * tier), at, 0.95 * intensity)
                if b in (1, 3):
                    add_at(snare_s, snare(seed=12 + b), at, 0.52 * intensity)
                add_at(hat_l, hat(seed=13 + b), at, 0.30 * intensity)
                add_at(hat_r, hat(open_=True, seed=14 + b), at + beat / 2.0, 0.22 * intensity)
                # air band: bright sizzle, one per 8th, alternating sides
                air_n = int(0.05 * SR)
                air_t = np.arange(air_n) / SR
                air = bandpass(noise(air_n, seed=90 + b), 9000.0, 16000.0) * np.exp(-air_t * 55.0)
                add_at(hat_l if b % 2 == 0 else hat_r, air, at, 0.17 * intensity)
                add_at(hat_r if b % 2 == 0 else hat_l, air, at + beat / 2.0, 0.14 * intensity)
                if role in ("drop", "finale") or tier >= 3:
                    add_at(hat_l, hat(seed=15 + b), at + beat / 4.0, 0.12 * intensity)
                    add_at(hat_r, hat(seed=19 + b), at + 3 * beat / 4.0, 0.12 * intensity)
            if role in ("drop", "finale"):
                add_at(kick_s, kick(drive=2.0), t0 + 3.5 * beat, 0.6 * intensity)
        elif role == "break":
            # Half-time heartbeat: one kick, one snare, lots of space.
            add_at(kick_s, kick(drive=2.2), t0, 0.7)
            add_at(snare_s, snare(seed=61), t0 + 2 * beat, 0.4)
            for b in range(4):
                add_at(hat_r, hat(open_=True, seed=20 + b), t0 + b * beat, 0.12)
        else:   # intro
            add_at(kick_s, kick(drive=1.2), t0, 0.6)
            for b in range(4):
                add_at(hat_r, hat(seed=30 + b), t0 + b * beat + beat / 2.0, 0.12)

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

    # ---- lead: literally the chart notes ---------------------------------- #
    for note in L.notes(song):
        at = note["time"] / 1000.0
        role = measure_role.get(note["measure"], "verse")
        dur = max(0.16, note["sLen"] / 1000.0 if note["sLen"] else step * 2.4)
        octave_shift = 1 if note["measure"] >= total_measures * 0.72 else 0
        midi = L.note_pitch(song, note["measure"], note["id"], octave_shift)
        accent = 1.0 if note["time"] % (beat * 1000.0) < 1.0 else 0.85
        sig = lead_note(
            midi,
            dur,
            bright=tier < 3,
            drive=1.15 + 0.30 * tier,
            detune=1.0038 + 0.004 * (tier - 1) * (1 if note["id"] % 2 else -1),
            grit={1: 0.0, 2: 0.3, 3: 0.9}[tier],
        )
        target = lead_p if note["side"] == "player" else lead_o
        add_at(target, sig, at, 0.64 * accent * (0.75 + 0.35 * ROLE_GAIN[role]))
        # Finale: octave doubling makes the last act feel bigger.
        if role == "finale" and note["side"] == "player":
            add_at(target, lead_note(midi + 12, dur * 0.8, bright=True, drive=1.0, grit=0.2),
                   at, 0.16 * accent)

    # ---- horror layers per tier ------------------------------------------- #
    if tier >= 1:
        drone = lowpass(sine(43.0, n_total) * 0.030 * tier + saw(29.0, n_total) * 0.012 * tier, 150.0)
        fx_s += drone

    if tier >= 2:
        fx_s += highpass(noise(n_total, seed=61), 2600.0) * (0.014 if tier == 2 else 0.024)

    if tier >= 3:
        swell = bandpass(noise(n_total, seed=63), 400.0, 2600.0)
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * np.arange(n_total) / SR)
        fx_s += swell * lfo * 0.035

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

    if tier == 3:
        cut = int(len(hat_l) * 0.62)
        hat_l[cut:] = bitcrush(hat_l[cut:], bits=7, hold=2) * 0.6 + hat_l[cut:] * 0.4
        hat_r[cut:] = bitcrush(hat_r[cut:], bits=7, hold=2) * 0.6 + hat_r[cut:] * 0.4

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
    master_points = [(26.0, -18.0), (40.0, -9.0), (60.0, -6.0), (90.0, -5.5),
                     (140.0, -4.5), (250.0, -2.0), (400.0, 0.5), (900.0, 2.0),
                     (2000.0, 3.8), (4000.0, 3.8), (8000.0, 4.2), (12000.0, 5.0),
                     (16000.0, 6.0), (20000.0, 2.0)]
    left = eq_curve(left, master_points)
    right = eq_curve(right, master_points)
    # Glue compression (gentle: only the loudest peaks, so the quiet sections
    # keep their space) -> width -> loudness target -> limiter.
    left = compress(left, threshold_db=-15.0, ratio=2.0, makeup_db=2.0)
    right = compress(right, threshold_db=-15.0, ratio=2.0, makeup_db=2.0)
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
        write_ogg(path, (left, right))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(path, ROOT), os.path.getsize(path) / 1024))

    print("Rendering ambient themes...")
    for name, scary in (("trollge_theme", False), ("trollge_theme_scary", True)):
        buf = render_theme(scary=scary)
        p = os.path.join(SFX_DIR, name + ".ogg")
        write_ogg(p, (buf, buf))
        print("  -> %-44s %6.1f KB" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1024))

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


if __name__ == "__main__":
    main()
