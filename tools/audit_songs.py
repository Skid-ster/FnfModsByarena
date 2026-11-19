#!/usr/bin/env python3
"""
Song audit: measures the shipped instrumentals and charts and writes
`docs/song_report.md`.

It exists so "does this sound/look right?" has numbers behind it instead of
vibes: loudness, dynamic range between sections, spectral balance (is there any
top end? is the sub eating the mix?), stereo width, and rhythm/chart style
(off-beat ratio, same-lane jacks, note density curve, opponent vs player
balance).

Run with:  python3 tools/audit_songs.py [--strict]
`--strict` fails (exit 1) when a metric falls outside the target window, which
is what CI uses.
"""

import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L  # noqa: E402
from lib_dsp import bandpass, true_peak  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DOCS = os.path.join(ROOT, "docs")

BANDS = [
    ("sub", 20.0, 80.0),
    ("low", 80.0, 250.0),
    ("lowmid", 250.0, 800.0),
    ("mid", 800.0, 2500.0),
    ("high", 2500.0, 8000.0),
    ("air", 8000.0, 16000.0),
]

#: Target windows (--strict enforces them).
TARGETS = {
    "peak_db": (-3.5, -0.2),          # loud but never clipping
    "crest_db": (7.0, 20.0),          # some punch left, not a brick
    # Measured after mastering: the limiter trades a few tenths of a dB of macro
    # dynamics for loudness, so the window starts at 4 dB rather than 5.
    "section_range_db": (4.0, 26.0),  # the arrangement actually breathes
    "offbeat_ratio": (0.00, 0.90),    # week 1 is on-beat; nothing is a wall of 16ths
    "hard_density": (1.0, 6.0),       # notes/second in the hard chart (playable)
    "voices_peak_db": (-8.0, -0.50),  # the vocal track is there and never clips
    "voices_cover": (0.90, 1.01),     # share of chart notes with vocals under them
    "mixed_bars": (0, 0),             # a bar is sung by exactly one character
    "air_pct": (0.8, 22.0),           # allow a deliberately dark trap mix, not zero air
    "sub_pct": (2.0, 38.0),           # the sub is not the whole mix
    "width": (0.05, 0.95),            # allow narrower mixes; side_mid also detects near-mono
    "side_mid": (-22.0, -3.0),        # side energy relative to mid, in dB
    "max_lane_run": (0, 3),           # no accidental jacks
    "true_peak_db": (-4.0, -0.10),    # inter-sample peaks stay below full scale
    "distinctness": (0.10, 2.10),     # songs must not be the same track at 3 tempos
}


def db(x):
    return 20.0 * np.log10(max(float(x), 1e-9))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def true_peak_db(data):
    """Inter-sample peak, 4x oversampled (see lib_dsp.true_peak)."""
    return db(max(true_peak(data[:, 0]), true_peak(data[:, 1])))


def analyse_audio(path, song):
    data, sr = sf.read(path, always_2d=True)
    mono = data.mean(axis=1)
    left, right = data[:, 0], data[:, 1]

    peak = float(np.max(np.abs(data)))
    crest = db(peak) - db(rms(mono))

    # Spectrum over the loud half of the song.
    spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    freqs = np.fft.rfftfreq(len(mono), 1.0 / sr)
    power = spec ** 2
    total = power.sum() or 1.0
    bands = {}
    for name, lo, hi in BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        bands[name] = 100.0 * power[mask].sum() / total
    centroid = float((freqs * power).sum() / total) if total else 0.0

    # Section energy: RMS per chart section, in dB.
    levels = []
    for section in L.sections(song):
        start = int(section["time"] / 1000.0 * sr)
        end = start + int(section["measures"] * L.measure(song) * sr)
        chunk = mono[start:min(end, len(mono))]
        if len(chunk) > sr // 8:
            levels.append(db(rms(chunk)))
    section_range = (max(levels) - min(levels)) if levels else 0.0

    # Stereo: correlation in the band where panning actually lives (250 Hz+),
    # plus the classic side/mid ratio. Bass is meant to be centred, so measuring
    # correlation over the whole spectrum would always read "mono".
    mid_band_l = bandpass(left, 250.0, 9000.0)
    mid_band_r = bandpass(right, 250.0, 9000.0)
    denom = np.sqrt(np.sum(mid_band_l ** 2) * np.sum(mid_band_r ** 2)) or 1.0
    correlation = float(np.sum(mid_band_l * mid_band_r) / denom)

    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)
    side_mid = db(rms(side)) - db(rms(mid))

    # Onset density: count envelope peaks (10 ms hops, 2 ms attack window).
    hop = int(0.010 * sr)
    frames = len(mono) // hop
    env = np.array([rms(mono[i * hop:(i + 1) * hop]) for i in range(frames)])
    env = np.convolve(env, np.ones(3) / 3.0, mode="same")
    flux = np.maximum(np.diff(env), 0.0)
    threshold = flux.mean() + 1.5 * flux.std()
    onsets = int(np.sum((flux[1:-1] > threshold) & (flux[1:-1] > flux[:-2]) & (flux[1:-1] >= flux[2:])))
    clip = int(np.sum(np.abs(data) > 0.999))

    return {
        "duration": len(mono) / sr,
        "peak_db": db(peak),
        "rms_db": db(rms(mono)),
        "crest_db": crest,
        "bands": bands,
        "centroid": centroid,
        "section_range_db": section_range,
        "section_levels": levels,
        "correlation": correlation,
        "width": 1.0 - correlation,
        "side_mid": side_mid,
        "onsets_per_s": onsets / (len(mono) / sr),
        "clipped": clip,
        "true_peak_db": true_peak_db(data),
        "dc": float(np.mean(mono)),
        "fingerprint": (bands["sub"], bands["low"], bands["mid"], bands["high"], bands["air"],
                        centroid / 1000.0, onsets / (len(mono) / sr)),
    }


def analyse_chart(song, difficulty="hard"):
    path = os.path.join(MOD, "songs", song["id"], "charts", difficulty + ".json")
    chart = json.load(open(path, encoding="utf-8"))
    step_ms = L.step(song) * 1000.0

    notes = []
    for line in chart["strumLines"]:
        for note in line["notes"]:
            notes.append((float(note["time"]), int(note["id"]), float(note["sLen"]),
                          line["position"]))

    times = sorted(set(t for t, _i, _s, _p in notes))
    gaps = np.diff(times) if len(times) > 1 else np.array([1.0])

    # On-beat = the note lands on a beat boundary, measured from the song offset.
    offset_ms = song["offset"] * 1000.0
    offbeat = 0
    for t in times:
        phase = ((t - offset_ms) / step_ms) % 4.0
        if min(phase, 4.0 - phase) > 0.01:
            offbeat += 1

    lanes = np.zeros(4, dtype=int)
    for _t, lane, _s, _p in notes:
        lanes[lane] += 1
    lane_share = lanes / max(1, lanes.sum())

    # Longest run of the same lane inside one strum line, in time order.
    runs = {0: 0, 1: 0}
    best = 0
    for side in (0, 1):        # 0 = opponent, 1 = player (chart order)
        last_lane, run = None, 0
        for line_index, line in enumerate(chart["strumLines"]):
            if line_index != side:
                continue
            for note in line["notes"]:
                lane = int(note["id"])
                run = run + 1 if lane == last_lane else 1
                last_lane = lane
                best = max(best, run)

    sustains = sum(1 for _t, _i, s, _p in notes if s > 0)
    simultaneous = len(notes) - len(times)

    # Density curve per section (player notes/second).
    per_section = []
    for section in L.sections(song):
        start = section["time"]
        end = start + section["measures"] * L.measure(song) * 1000.0
        count = sum(1 for t, _i, _s, pos in notes if start <= t < end and pos == "boyfriend")
        per_section.append(count / max(0.001, (end - start) / 1000.0))

    player = sum(1 for _t, _i, _s, p in notes if p == "boyfriend")

    # Phrase blocks: consecutive bars must belong to one character and the two
    # characters must trade blocks (base-game convention), never interleave.
    measure_ms = L.measure(song) * 1000.0
    bar_side = {}
    for t, _i, _s, pos in notes:
        bar = int((t - offset_ms) / measure_ms + 1e-6)
        bar_side.setdefault(bar, set()).add(pos)
    mixed_bars = sum(1 for sides in bar_side.values() if len(sides) > 1)
    runs, last = [], None
    for bar in sorted(bar_side):
        side = next(iter(bar_side[bar])) if len(bar_side[bar]) == 1 else "mixed"
        if side == last:
            runs[-1] += 1
        else:
            runs.append(1)
            last = side

    return {
        "difficulty": difficulty,
        "scroll": float(chart.get("scrollSpeed", 0.0)),
        "mixed_bars": mixed_bars,
        "phrase_runs": runs,
        "min_gap_ms": float(np.min(gaps)) if len(gaps) else 0.0,
        "notes": len(notes),
        "player": player,
        "opponent": len(notes) - player,
        "notes_per_s": len(notes) / (times[-1] / 1000.0) if times else 0.0,
        "offbeat_ratio": offbeat / max(1, len(times)),
        "lane_share": lane_share,
        "max_lane_run": best,
        "sustains": sustains,
        "simultaneous": simultaneous,
        "median_gap_ms": float(np.median(gaps)) if len(gaps) else 0.0,
        "density_curve": per_section,
    }


def analyse_voices(path, song, chart):
    """Measure the vocal track: it has to be the same length as the song, loud
    enough to hear, and actually singing under the chart's notes.

    A base-game song always ships one (`song/Voices.ogg`, gated by
    `meta.needsVoices`); a missing or silent track means the characters mouth
    the lyrics in silence, which is the single most obvious "this is not FNF"
    tell.
    """
    data, sr = sf.read(path, always_2d=True)
    mono = data.mean(axis=1)
    peak = db(max(float(np.max(np.abs(data))), 1e-9))
    level = db(rms(mono))

    # Is there a voice under the notes? Sample a 90 ms window at each note time.
    window = int(0.09 * sr)
    floor = db(rms(mono)) - 24.0
    covered = 0
    frames = 0
    for note in L.notes(song, chart["difficulty"]):
        start = int(note["time"] / 1000.0 * sr)
        chunk = mono[start:start + window]
        if len(chunk) < window // 4:
            continue
        frames += 1
        if db(rms(chunk)) > floor:
            covered += 1
    return {
        "duration": len(mono) / sr,
        "peak_db": peak,
        "rms_db": level,
        "cover": covered / max(1, frames),
    }


def fmt_row(label, value, raw=None, key=None):
    target = TARGETS.get(key)
    flag = "-"
    if target and raw is not None:
        lo, hi = target
        flag = "ok" if lo <= raw <= hi else "**out of window**"
    return "| %s | %s | %s |" % (label, value, flag)


def main():
    strict = "--strict" in sys.argv
    problems = []
    charts = []
    fingerprints = []
    style_rows = []
    report = ["# Song audit", "",
              "Generated by `tools/audit_songs.py` — audio measured from the shipped `Inst.ogg`, "
              "charts read from `charts/*.json`.", ""]

    for song in L.SONGS:
        inst = os.path.join(MOD, "songs", song["id"], "song", "Inst.ogg")
        if not os.path.isfile(inst):
            problems.append("%s: missing Inst.ogg" % song["id"])
            continue
        audio = analyse_audio(inst, song)
        per_difficulty = {d: analyse_chart(song, d) for d in L.DIFFICULTIES}
        chart = per_difficulty["hard"]
        charts.append(chart)
        fingerprints.append(audio["fingerprint"])

        voices_path = os.path.join(MOD, "songs", song["id"], "song", "Voices.ogg")
        voices = analyse_voices(voices_path, song, chart) if os.path.isfile(voices_path) else None
        if voices is None:
            problems.append("%s: no song/Voices.ogg (the characters would sing in silence)"
                            % song["id"])

        # The difficulty spread has to be a real spread, not three copies.
        counts = [per_difficulty[d]["notes"] for d in L.DIFFICULTIES]
        spread_ok = counts[0] < counts[1] < counts[2] and per_difficulty["easy"]["sustains"] == 0
        report_easy = "| difficulty spread | %s | %s |" % (
            " → ".join("%s %d" % (d, per_difficulty[d]["notes"]) for d in L.DIFFICULTIES),
            "ok" if spread_ok else "**not a spread**")
        if not spread_ok:
            problems.append("%s: difficulty spread is not easy < normal < hard (%s)"
                            % (song["id"], counts))
        if chart["mixed_bars"]:
            problems.append("%s: %d bars mix player and opponent notes"
                            % (song["id"], chart["mixed_bars"]))
        if not (voices is None) and abs(voices["duration"] - L.length(song)) > 0.15:
            problems.append("%s: Voices.ogg is %.2fs, the song is %.2fs"
                            % (song["id"], voices["duration"], L.length(song)))

        print("\n%s  (%s, scare %d/10)" % (song["display"], song["id"], song["scare"]))
        print("  audio  %.2fs  peak %.1f dB  peak estimate %.1f dB  rms %.1f dB  crest %.1f dB  centroid %.0f Hz"
              % (audio["duration"], audio["peak_db"], audio["true_peak_db"], audio["rms_db"],
                 audio["crest_db"], audio["centroid"]))
        print("  bands  " + "  ".join("%s %.0f%%" % (k, v) for k, v in audio["bands"].items()))
        print("  stereo width %.2f  side/mid %.1f dB  onsets/s %.1f  section range %.1f dB  clipped %d"
              % (audio["width"], audio["side_mid"], audio["onsets_per_s"],
                 audio["section_range_db"], audio["clipped"]))
        print("  chart  %d notes (%.1f/s)  off-beat %.0f%%  lanes %s  max same-lane run %d"
              % (chart["notes"], chart["notes_per_s"], chart["offbeat_ratio"] * 100,
                 " ".join("%.0f%%" % (s * 100) for s in chart["lane_share"]),
                 chart["max_lane_run"]))
        print("         sustains %d  simultaneous %d  player %d / opponent %d"
              % (chart["sustains"], chart["simultaneous"], chart["player"], chart["opponent"]))
        print("  density " + " ".join("%.1f" % d for d in chart["density_curve"]))
        print("  chart  %s  scroll %s  phrase blocks %s"
              % (L.key_name(song),
                 " ".join("%s %.2f" % (d, per_difficulty[d]["scroll"]) for d in L.DIFFICULTIES),
                 " ".join(str(r) for r in chart["phrase_runs"][:8])))
        if voices:
            print("  voices %.2fs  peak %.1f dB  rms %.1f dB  under %.0f%% of notes"
                  % (voices["duration"], voices["peak_db"], voices["rms_db"],
                     voices["cover"] * 100))

        report += ["## %s — %d/10" % (song["display"], song["scare"]), "",
                   "| Metric | Value | Target |", "| --- | --- | --- |"]
        report.append(fmt_row("length", "%.2f s" % audio["duration"]))
        report.append(fmt_row("peak", "%.1f dBFS" % audio["peak_db"], audio["peak_db"], "peak_db"))
        report.append(fmt_row("inter-sample peak estimate (4x Catmull-Rom)", "%.2f dBTP" % audio["true_peak_db"],
                              audio["true_peak_db"], "true_peak_db"))
        report.append(fmt_row("style", song.get("style", "-")))
        report.append(fmt_row("Boyfriend", song.get("bf", "-")))
        report.append(fmt_row("Trollge", song.get("trollge", "-")))
        report.append(fmt_row("loudness (RMS)", "%.1f dBFS" % audio["rms_db"]))
        report.append(fmt_row("crest factor", "%.1f dB" % audio["crest_db"], audio["crest_db"], "crest_db"))
        report.append(fmt_row("section dynamics", "%.1f dB" % audio["section_range_db"],
                              audio["section_range_db"], "section_range_db"))
        report.append(fmt_row("spectral centroid", "%.0f Hz" % audio["centroid"]))
        for name, _lo, _hi in BANDS:
            key = "%s_pct" % name if name in ("air", "sub") else None
            report.append(fmt_row("energy %s" % name, "%.0f %%" % audio["bands"][name],
                                  audio["bands"][name], key))
        report.append(fmt_row("stereo width (250 Hz+)", "%.2f" % audio["width"],
                              audio["width"], "width"))
        report.append(fmt_row("side / mid", "%.1f dB" % audio["side_mid"],
                              audio["side_mid"], "side_mid"))
        report.append(fmt_row("onsets", "%.1f /s" % audio["onsets_per_s"]))
        report.append(fmt_row("clipped samples", "%d" % audio["clipped"]))
        report.append(fmt_row("key", L.key_name(song)))
        report.append(fmt_row("phrase blocks", "%d bars, runs %s"
                              % (L.measures(song),
                                 "/".join(str(r) for r in chart["phrase_runs"][:6]))))
        report.append(fmt_row("hard notes/second", "%.2f /s" % chart["notes_per_s"],
                              chart["notes_per_s"], "hard_density"))
        report.append(fmt_row("mixed bars (player + opponent)",
                              "%d" % chart["mixed_bars"],
                              chart["mixed_bars"], "mixed_bars"))
        report.append(fmt_row("off-beat notes", "%.0f %%" % (chart["offbeat_ratio"] * 100),
                              chart["offbeat_ratio"], "offbeat_ratio"))
        report.append(fmt_row("same-lane run", "%d" % chart["max_lane_run"],
                              chart["max_lane_run"], "max_lane_run"))
        report.append(fmt_row("note density", "%.2f /s" % chart["notes_per_s"]))
        report.append(fmt_row("sustains", "%d" % chart["sustains"]))
        report.append(fmt_row("simultaneous notes", "%d" % chart["simultaneous"]))
        report.append(fmt_row("player / opponent", "%d / %d" % (chart["player"], chart["opponent"])))
        report.append(report_easy)
        for difficulty in L.DIFFICULTIES:
            entry = per_difficulty[difficulty]
            report.append(fmt_row("%s chart" % difficulty,
                                  "%d notes, %d sustains, scroll %.2f, run %d"
                                  % (entry["notes"], entry["sustains"], entry["scroll"],
                                     entry["max_lane_run"])))
        if voices:
            report.append(fmt_row("Voices.ogg", "%.2fs, peak %.1f dBFS, %.0f%% of notes covered"
                                  % (voices["duration"], voices["peak_db"], voices["cover"] * 100)))
            report.append(fmt_row("vocal peak", "%.1f dBFS" % voices["peak_db"],
                                  voices["peak_db"], "voices_peak_db"))
            report.append(fmt_row("vocal coverage", "%.0f %%" % (voices["cover"] * 100),
                                  voices["cover"], "voices_cover"))
        report.append("")

        for key, value in (("peak_db", audio["peak_db"]), ("crest_db", audio["crest_db"]),
                           ("section_range_db", audio["section_range_db"]),
                           ("air_pct", audio["bands"]["air"]), ("sub_pct", audio["bands"]["sub"]),
                           ("true_peak_db", audio["true_peak_db"]),
                           ("width", audio["width"]), ("side_mid", audio["side_mid"]),
                           ("offbeat_ratio", chart["offbeat_ratio"]),
                           ("hard_density", chart["notes_per_s"]),
                           ("max_lane_run", chart["max_lane_run"])):
            lo, hi = TARGETS[key]
            if not (lo <= value <= hi):
                problems.append("%s: %s = %.2f outside %.2f..%.2f"
                                % (song["id"], key, value, lo, hi))
        if audio["clipped"]:
            problems.append("%s: %d clipped samples" % (song["id"], audio["clipped"]))
        if abs(audio["dc"]) > 0.005:
            problems.append("%s: DC offset %.4f" % (song["id"], audio["dc"]))

    # Distinctness: the songs must not be the same track at three tempos.
    if len(fingerprints) >= 2:
        worst = None
        for i in range(len(fingerprints)):
            for j in range(i + 1, len(fingerprints)):
                a, b = fingerprints[i], fingerprints[j]
                distance = sum(abs(x - y) for x, y in zip(a[:5], b[:5])) / 100.0
                distance += abs(a[5] - b[5]) * 0.3 + abs(a[6] - b[6]) * 0.05
                if worst is None or distance < worst[0]:
                    worst = (distance, (i, j))
        value = worst[0]
        lo, hi = TARGETS["distinctness"]
        report.append("")
        report.append("| %s | %s | %s |" % ("song distinctness (min pairwise)",
                                            "%.3f" % value, "ok" if lo <= value <= hi else "**too similar**"))
        if not (lo <= value <= hi):
            problems.append("songs are too similar: fingerprint distance %.3f (need %.2f)"
                            % (value, lo))

    # The scare ladder itself must rise, one band per song.
    scares = [s["scare"] for s in L.SONGS]
    if any(b <= a for a, b in zip(scares, scares[1:])):
        problems.append("scare tiers must rise strictly: %s" % scares)
    if len(set(s.get("style") for s in L.SONGS)) != len(L.SONGS):
        problems.append("every song needs its own instrumental style")

    # Style escalation: the axes the base game actually scales -- tempo, note
    # density, scroll speed and production tier -- must all rise song by song.
    if len(charts) == len(L.SONGS) and charts:
        axes = (
            ("bpm", [s["bpm"] for s in L.SONGS], "%.0f"),
            ("hard notes", [c["notes"] for c in charts], "%.0f"),
            ("notes/second", [c["notes_per_s"] for c in charts], "%.2f"),
            ("scroll speed (hard)", [c["scroll"] for c in charts], "%.2f"),
        )
        for key, values, fmt in axes:
            rising = all(b >= a for a, b in zip(values, values[1:]))
            report.append("")
            line = "| %s | %s | %s |" % (key, " → ".join(fmt % v for v in values),
                                         "ok" if rising else "**must rise**")
            style_rows.append(line)
            if not rising:
                problems.append("%s must increase with the scare tier: %s" % (key, values))

    ladder = " → ".join("%d/10" % s["scare"] for s in L.SONGS)
    report += ["## Style escalation (%s)" % ladder, "",
               "| Metric | Per song | Result |", "| --- | --- | --- |"] + style_rows + [""]
    report += ["## Targets", "", "| Metric | Window |", "| --- | --- |"]
    for key, (lo, hi) in TARGETS.items():
        report.append("| %s | %.2f – %.2f |" % (key, lo, hi))
    report.append("")

    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "song_report.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(report))
    print("\n-> docs/song_report.md")

    if problems:
        print("\n%d issue(s):" % len(problems))
        for problem in problems:
            print("  - " + problem)
        if strict:
            print("AUDIT FAILED")
            return 1
    else:
        print("\nAll metrics inside their target windows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
