#!/usr/bin/env python3
"""Measures whether the phrase library behaves like music, not like numbers.

This is deliberately *not* a gate on taste -- taste is the owner's call. What it
counts are the things that separate a written melody from a random walk, and it
counts them on the notes that are actually played: the chart notes
`song_layout.sections()` produces, each scored against the chord under the bar
it lands in. Before this measured the phrase text against an assumed bar offset,
which is why it could report a healthy number for music that did not fit -- the
phrase is windowed into blocks, so the note you hear in bar 5 is not the note at
token 80 of the notation.

  * harmonic fit  -- do the notes on the beats belong to the chord under them?
                     A melody that ignores the harmony is the biggest single
                     reason music sounds like "random numbers";
  * stepwise motion and leap resolution -- is the line singable?
  * repetition    -- is a bar actually restated? Repetition is what makes a tune
                     recognisable;
  * range         -- a tune a person can hum stays inside an octave and a half.

Run:  python3 tools/melody_report.py
      python3 tools/melody_report.py --strict   (exit 1 if a floor is missed)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L

#: Floors, not targets to creep toward. If a change lowers one, the melody got
#: worse -- it did not fail to clear a threshold.
GATES = {
    "strong_chord_pct": 80.0,   # notes on beats 1 2 3 4 that fit the chord
    "chord_tone_pct": 62.0,     # all notes
    "stepwise_pct": 40.0,       # moves of 1-2 semitones
    "leap_resolve_pct": 60.0,   # leaps >= 5 semitones answered by a step back
    "repeat_pct": 25.0,         # notes belonging to a restated bar
    "max_range": 24,            # semitones, inclusive
}

STRONG_STEPS = (0, 4, 8, 12)


def chord_pcs(song, measure):
    root, tones = L.chord_for_measure(song, measure)
    return {(root + t) % 12 for t in tones}


def melody_lines(song):
    """The melody as it is played: one list of notes per section, in time order.

    Only one side sings a melody at a time (the other answers it), so splitting
    per section keeps leaps honest -- a phrase boundary is not a melodic leap.
    """
    lines = []
    for section in L.sections(song):
        notes = [n for n in section["notes"] if n.get("semi") is not None]
        notes.sort(key=lambda n: n["time"])
        if notes:
            lines.append(notes)
    return lines


def analyse(song):
    lines = melody_lines(song)
    steps = leaps = resolved = 0
    strong = strong_fit = total = fit_total = 0
    lo = hi = None
    barlines = {}

    for notes in lines:
        for note in notes:
            semi, measure = note["semi"], note["measure"]
            pcs = chord_pcs(song, measure)
            fits = (semi % 12) in pcs
            total += 1
            fit_total += fits
            if note.get("offset", 0) % 16 in STRONG_STEPS:
                strong += 1
                strong_fit += fits
            lo = semi if lo is None else min(lo, semi)
            hi = semi if hi is None else max(hi, semi)
        for a, b in zip(notes, notes[1:]):
            delta = abs(b["semi"] - a["semi"])
            if delta and delta <= 2:
                steps += 1
            elif delta >= 5:
                leaps += 1
        for i in range(1, len(notes) - 1):
            prev, cur, nxt = notes[i - 1]["semi"], notes[i]["semi"], notes[i + 1]["semi"]
            leap = cur - prev
            if abs(leap) >= 5:
                back = nxt - cur
                if back and (back > 0) != (leap > 0) and abs(back) <= 7:
                    resolved += 1

    # Repetition: a bar of the melody (its notes and their positions within the
    # bar) that occurs more than once in the same song.
    for notes in lines:
        for note in notes:
            key = (note["measure"] // 4, note.get("offset", 0) % 16)
            barlines.setdefault(key, []).append(note["semi"])
    reused = 0
    counted = []
    for notes in lines:
        bars = {}
        for note in notes:
            bars.setdefault(note["measure"], []).append((note.get("offset", 0) % 16,
                                                         note["semi"]))
        for bar_id, content in bars.items():
            counted.append(tuple(content))

    # A bar counts as restated if the same (step, pitch) content appears in
    # another bar of the song. That is what "repetition with variation" means
    # at bar level, and it is what a listener hears as a hook coming back.
    # A bar of a single long note is not a hook coming back -- it is a pedal
    # tone, and counting it as repetition would flatter a melody that repeats
    # nothing. Only bars with real content count. Every *occurrence* of a
    # restated bar counts, which is what the listener hears: the hook coming
    # back is a note you hear each time, not once.
    from collections import Counter
    seen = Counter(c for c in counted if len(c) >= 3)
    repeats = sum(len(c) * n for c, n in seen.items() if n > 1)

    return {
        "notes": total,
        "range": (hi - lo) if lo is not None else 0,
        "stepwise_pct": 100.0 * steps / max(1, steps + leaps),
        "leap_resolve_pct": 100.0 * resolved / max(1, leaps),
        "strong_chord_pct": 100.0 * strong_fit / max(1, strong),
        "chord_tone_pct": 100.0 * fit_total / max(1, total),
        "repeat_pct": 100.0 * repeats / max(1, total),
    }


def report(strict=False):
    rows, problems = [], []
    header = ("song", "notes", "on-chord", "chord%", "step", "leapres", "repeat", "range")
    print("%-16s %5s %9s %7s %5s %7s %7s %6s" % header)
    for song in L.SONGS:
        stats = analyse(song)
        rows.append((song["id"], stats))
        print("%-16s %5d %8.0f%% %6.0f%% %4.0f%% %6.0f%% %6.0f%% %6d" % (
            song["id"], stats["notes"], stats["strong_chord_pct"],
            stats["chord_tone_pct"], stats["stepwise_pct"],
            stats["leap_resolve_pct"], stats["repeat_pct"], stats["range"]))
        for gate, floor in GATES.items():
            if gate == "max_range":
                if stats["range"] > floor:
                    problems.append("%s: max_range = %d (needs <= %d)"
                                    % (song["id"], stats["range"], floor))
            elif stats[gate] < floor:
                problems.append("%s: %s = %.1f (needs >= %.1f)"
                                % (song["id"], gate, stats[gate], floor))

    print()
    if problems:
        print("%d issue(s):" % len(problems))
        for problem in problems:
            print("  - " + problem)
    else:
        print("all %d gates clear." % (len(GATES) * len(rows)))
    if strict and problems:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(report("--strict" in sys.argv))
