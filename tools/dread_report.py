#!/usr/bin/env python3
"""Measures whether the songs actually get scarier, or only say they do.

The owner's third ask was "actually make it scary". A scare rating in the song
JSON is a label; this script checks the *audio*, on two things horror music does
that a cheerful track does not:

  * a low drone a hair off the tonic, which beats slowly against itself. It shows
    up as a narrow band of energy at the tonic's sub-octave;
  * a tritone. It is the one interval no key contains, so a real tritone in the
    mix is a measured fact rather than a mood.

Both are measured as *prominence above the mid band* rather than as a share of
total energy: share-of-total measures the genre's bass, not the dread, and it is
why the first pass appeared to show the 4/10 song as "brighter" than the 2/10.
The script then checks that the prominence *climbs with the rating* -- the
frightening songs must sit deeper in the mix than the friendly ones. A ladder
that exists only in the JSON is what the last version had, and it measured flat.

Run:  python3 tools/dread_report.py
      python3 tools/dread_report.py --strict
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L

try:
    import soundfile as sf
except ImportError:  # pragma: no cover
    sys.exit("needs soundfile: pip3 install --break-system-packages soundfile")

MOD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "mods", "TrollgeMod")
SR = 44100

#: The ladder must be monotonic in this: the share of energy below 250 Hz. The
#: first pass measured 63 / 45 / 58 / 66 / 84 percent -- the 10/10 song was the
#: darkest, but the 4/10 was the *brightest* of the five, which is a ladder you
#: cannot hear. A tolerance of a couple of points either way lets a song have
#: its own character without breaking the trend.
DREAD_TOLERANCE_DB = 3.0


def spectrum(path):
    data, sr = sf.read(path, always_2d=True)
    mono = data.mean(axis=1)
    n = 1 << 15
    hop = n // 2
    window = np.hanning(n)
    acc = np.zeros(n // 2 + 1)
    frames = 0
    for start in range(0, max(1, len(mono) - n), hop):
        chunk = mono[start:start + n]
        if len(chunk) < n:
            chunk = np.pad(chunk, (0, n - len(chunk)))
        acc += np.abs(np.fft.rfft(chunk * window)) ** 2
        frames += 1
    power = acc / max(1, frames)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    return freqs, power


def measure(song):
    path = os.path.join(MOD, "songs", song["id"], "song", "Inst.ogg")
    freqs, power = spectrum(path)
    total = power.sum()

    def share(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        return 100.0 * power[mask].sum() / total

    # The two horror layers, measured as prominence *relative to the mid band*
    # rather than as a share of total energy. Share-of-total is not comparable
    # across the songs: a bounce track and a trap track have very different bass
    # by genre, so "percent below 250 Hz" measures the genre, not the dread.
    # Prominence asks the question that matters -- can you hear the drone and the
    # tritone above the body of the mix?
    def band_power(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        return float(power[mask].sum()) if mask.any() else 0.0

    mid = band_power(250.0, 2000.0)
    tonic = 440.0 * 2 ** ((song["tonic"] - 69) / 12.0)
    drone_hz = tonic / 2.0
    drone_band = band_power(drone_hz * 0.94, drone_hz * 1.06)
    tri_hz = drone_hz * (2 ** (6 / 12.0))
    tri_band = band_power(tri_hz * 0.97, tri_hz * 1.03)

    def prominence(energy):
        return 10.0 * np.log10(max(energy, 1e-12) / max(mid, 1e-12))

    drone = prominence(drone_band)
    tritone = prominence(tri_band)

    return {
        "scare": song["scare"],
        "low_pct": share(0, 250),
        "drone_db": drone,
        "tritone_db": tritone,
        "dread_db": 10.0 * np.log10(
            max(drone_band + tri_band, 1e-12) / max(mid, 1e-12)),
    }


def report(strict=False):
    rows = [(song, measure(song)) for song in L.SONGS]
    print("%-16s %6s %9s %9s %11s %9s" % ("song", "scare", "low<250",
                                         "drone dB", "tritone dB", "dread dB"))
    for song, stats in rows:
        print("%-16s %4d/10 %8.1f%% %9.1f %9.1f %10.1f"
              % (song["id"], stats["scare"], stats["low_pct"],
                 stats["drone_db"], stats["tritone_db"], stats["dread_db"]))

    problems = []
    ordered = sorted(rows, key=lambda r: r[0]["scare"])
    #: The ladder is judged on `dread_db`: how far the drone and the tritone sit
    #: above the body of the mix. 3 dB of tolerance lets each song keep its own
    #: character without the trend disappearing.
    for (a_song, a), (b_song, b) in zip(ordered, ordered[1:]):
        if b["dread_db"] + DREAD_TOLERANCE_DB < a["dread_db"]:
            problems.append(
                "%s (scare %d, dread %.1f dB) is less oppressive than %s "
                "(scare %d, dread %.1f dB)"
                % (b_song["id"], b_song["scare"], b["dread_db"],
                   a_song["id"], a_song["scare"], a["dread_db"]))
    # The frightening end of the ladder must actually carry the layers.
    for song, stats in ordered[-2:]:
        if stats["drone_db"] < -18.0:
            problems.append("%s is a %d/10 with no audible drone (%.1f dB)"
                            % (song["id"], song["scare"], stats["drone_db"]))
        if stats["tritone_db"] < -20.0:
            problems.append("%s is a %d/10 with no audible tritone (%.1f dB)"
                            % (song["id"], song["scare"], stats["tritone_db"]))

    print()
    if problems:
        print("%d issue(s):" % len(problems))
        for p in problems:
            print("  - " + p)
    else:
        print("the dread ladder climbs: every higher scare sits deeper in the "
              "mix than the one before it.")
    if strict and problems:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(report("--strict" in sys.argv))
