"""
Intentional chart design for Super Scary Trollge.

Charts feel good because of *natural lane flow* (not forced hand alternation),
*scare-scaled density*, and *section identity* (chorus differs from verse,
build differs from finale). Every chart is built in layers:

    1. Melody layer — filtered phrase notes (hard = all, normal = half,
       easy = anchors). Lanes come straight from the phrase's natural lane
       assignment; only jacks of 4+ same-lane are nudged to a free lane.
    2. Rhythm layer — section-specific groove pattern scaled by scare tier:
       half notes in intro, quarters in verses, eighths in chorus/build/finale,
       gallop bursts in the last act.
    3. Polish — jack protection (max 3 same lane), sustains on section ends
       (hard), finale hands (double-lane chords on downbeats in the last act).

No strict hand alternation: quarter-note patterns stay natural, and the chart
flows like a real FNF chart instead of crossing-hand calisthenics.
"""

from song_layout import (
    LEFT, DOWN, UP, RIGHT,
    step, beat, measure_time,
    sections,
)

#: Maximum consecutive hits on the same lane before we force a lane change.
MAX_SAME_LANE_RUN = 3

#: Lanes per hand, used only for picking a free lane when nudging a jack.
HAND_LANES = {0: (LEFT, DOWN), 1: (UP, RIGHT)}


# --------------------------------------------------------------------------- #
# Per-section rhythm templates.
#
# Each template maps a section role to a list of (offset_16ths, kind) where
# kind is "single" (one note) or "jump" (two-hand chord). Templates repeat
# across the measures of a section, with every 4th repetition varied.
# --------------------------------------------------------------------------- #

SECTION_TEMPLATES = {
    "intro": {
        2:  [(0, "single")],                                              # sparse
        4:  [(0, "single"), (8, "single")],                               # half notes
        6:  [(0, "single"), (4, "single"), (8, "single"), (12, "single")],# quarters
        8:  [(0, "single"), (8, "single")],                               # half notes
        10: [(0, "single"), (4, "single"), (8, "single"), (12, "single")],
    },
    "verse": {
        2:  [(0, "single"), (8, "single")],
        4:  [(0, "single"), (4, "single"), (8, "single"), (12, "single")],
        6:  [(0, "single"), (4, "jump"), (8, "single"), (12, "jump")],    # jumps on 4 & 12
        8:  [(0, "single"), (2, "single"), (4, "single"), (6, "single"),
             (8, "single"), (10, "single"), (12, "single"), (14, "single")],  # eighths
        10: [(0, "single"), (4, "single"), (8, "single"), (12, "single")],
    },
    "chorus": {
        2:  [(0, "single"), (8, "single")],
        4:  [(0, "jump"), (4, "single"), (8, "jump"), (12, "single")],    # jumps on downbeats
        6:  [(0, "jump"), (3, "single"), (6, "single"), (8, "jump"),
             (11, "single"), (14, "single")],                             # syncopated jumps
        8:  [(0, "single"), (2, "single"), (4, "single"), (6, "single"),
             (8, "jump"), (10, "single"), (12, "single"), (14, "single")], # eighths + jump
        10: [(0, "jump"), (4, "single"), (8, "jump"), (12, "single")],
    },
    "build": {
        2:  [(0, "single"), (4, "single"), (8, "single"), (12, "single")],
        4:  [(0, "jump"), (2, "single"), (4, "jump"), (6, "single"),
             (8, "jump"), (10, "single"), (12, "jump"), (14, "single")],   # gallop
        6:  [(0, "single"), (1, "single"), (2, "single"), (3, "single"),   # stutter burst
             (4, "jump"), (5, "single"), (6, "single"), (7, "single"),
             (8, "jump"), (9, "single"), (10, "single"), (11, "single"),
             (12, "jump"), (13, "single"), (14, "single"), (15, "single")],
        8:  [(0, "jump"), (2, "single"), (4, "jump"), (6, "single"),
             (8, "jump"), (10, "single"), (12, "jump"), (14, "single")],
        10: [(0, "single"), (2, "single"), (4, "single"), (6, "single"),
             (8, "single"), (10, "single"), (12, "single"), (14, "single")],
    },
    "break": {
        2:  [(0, "single")],                                              # long holds
        4:  [(0, "single"), (8, "single")],
        6:  [(0, "single"), (8, "single")],
        8:  [(0, "single"), (8, "single")],
        10: [(0, "single"), (8, "single")],
    },
    "finale": {
        2:  [(0, "jump"), (4, "single"), (8, "jump"), (12, "single")],
        4:  [(0, "jump"), (2, "single"), (4, "jump"), (6, "single"),
             (8, "jump"), (10, "single"), (12, "jump"), (14, "single")],   # gallop
        6:  [(0, "single"), (1, "single"), (2, "single"), (3, "single"),   # max stutter
             (4, "jump"), (5, "single"), (6, "single"), (7, "single"),
             (8, "jump"), (9, "single"), (10, "single"), (11, "single"),
             (12, "jump"), (13, "single"), (14, "single"), (15, "single")],
        8:  [(0, "jump"), (1, "single"), (2, "single"), (3, "single"),
             (4, "jump"), (5, "single"), (6, "single"), (7, "single"),
             (8, "jump"), (9, "single"), (10, "single"), (11, "single"),
             (12, "jump"), (13, "single"), (14, "single"), (15, "single")],
        10: [(0, "jump"), (2, "single"), (4, "jump"), (6, "single"),
             (8, "jump"), (10, "single"), (12, "jump"), (14, "single")],
    },
}


def _template_for(song, role, repeat_index):
    """Pick the rhythm template for a section role and scare tier.

    Higher scare = denser template. Every 4th repetition is varied so the
    pattern doesn't feel like a loop.
    """
    scare = song["scare"]
    table = SECTION_TEMPLATES.get(role, SECTION_TEMPLATES["verse"])

    # Pick the closest density tier at or below the scare tier.
    tiers = sorted(table.keys())
    tier = max(t for t in tiers if t <= scare)
    base = table[tier]

    # Every 4th repetition: swap jumps to singles or add off-beat hits.
    if repeat_index % 4 == 3 and role in ("chorus", "build", "finale"):
        varied = []
        for off16, kind in base:
            if kind == "jump":
                varied.append((off16, "single"))
            else:
                varied.append((off16, "single"))
            # Add an off-beat anticipation hit before the next downbeat.
            if off16 in (0, 8):
                varied.append(((off16 + 14) % 16, "single"))
        base = varied

    return base


# --------------------------------------------------------------------------- #
# Per-difficulty melody filtering.
# --------------------------------------------------------------------------- #

def _melody_notes_for_difficulty(song, difficulty, section_notes):
    """Return the melody notes that survive this difficulty's filter.

    HARD:     all melody notes
    NORM:     downbeats + every other offbeat note (driving, syncopated)
    EASY:     downbeats + every 4th offbeat (readable 8th-note anchors)
    """
    if difficulty == "hard":
        return list(section_notes)

    out = []
    offbeat_toggle = False
    for n in section_notes:
        is_downbeat = n["offset"] == 0
        if difficulty == "easy":
            if is_downbeat or n["offset"] % 4 == 0:
                out.append(n)
        else:  # normal
            if is_downbeat:
                out.append(n)
                offbeat_toggle = False
            else:
                offbeat_toggle = not offbeat_toggle
                if offbeat_toggle:
                    out.append(n)
    return out


# --------------------------------------------------------------------------- #
# Main entry: designed notes for one difficulty.
# --------------------------------------------------------------------------- #

def notes(song, difficulty="hard"):
    """Designed chart notes for `difficulty`.

    Layers: melody + rhythm + jumps, then jack protection (max 3 same lane),
    sustains, finale hands.
    """
    secs = sections(song)
    all_notes = []

    for i, sec in enumerate(secs):
        role = sec["role"]

        # ── 1. Melody layer ──────────────────────────────────────────
        melody = _melody_notes_for_difficulty(song, difficulty, sec["notes"])
        for n in melody:
            all_notes.append(dict(n))

        # ── 2. Rhythm layer — scare-scaled groove pattern ──────────────
        bars = sec["measures"]
        start_measure = sum(secs[j]["measures"] for j in range(i))
        role = sec["role"]
        scare = song["scare"]

        # Base offsets by scare tier and section role.
        if scare >= 10:
            # The Incident: eighths in chorus/build/finale, quarters in verse.
            # Finale gets gallop bursts on the "and" of each beat, with
            # extra 16th-note pickups to keep hard-mode density climbing.
            if role in ("chorus_a", "chorus_b", "build"):
                offsets = [0, 2, 4, 6, 8, 10, 12, 14]
            elif role == "finale":
                offsets = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14]
            elif role in ("intro", "break"):
                offsets = [0, 8]
            else:
                offsets = [0, 4, 8, 12]
        elif scare >= 8:
            # Super Scary: eighths in chorus/build/finale, quarters elsewhere.
            if role in ("chorus_a", "chorus_b", "build", "finale"):
                offsets = [0, 2, 4, 6, 8, 10, 12, 14]
            else:
                offsets = [0, 4, 8, 12]
        elif scare >= 6:
            # Don't Look Back: eighths in build/finale, quarters elsewhere.
            if role in ("build", "finale"):
                offsets = [0, 2, 4, 6, 8, 10, 12, 14]
            else:
                offsets = [0, 4, 8, 12]
        elif scare >= 4:
            # Getting Dark: quarters everywhere.
            offsets = [0, 4, 8, 12]
        else:
            # Trolling: half notes.
            offsets = [0, 8]

        # Density scaling by difficulty.
        if difficulty == "easy":
            # Easy: downbeat hits only, as singles.
            rhythm_offsets = [o for o in offsets if o == 0] or [0]
        elif difficulty == "normal":
            # Normal: half the offsets, singles only.
            rhythm_offsets = offsets[::2] or [0]
        else:
            rhythm_offsets = offsets

        rhythm = []
        for bar in range(bars):
            m = start_measure + bar
            base_t = measure_time(song, m)
            for off16 in rhythm_offsets:
                t = base_t + off16 * step(song) * 1000.0
                rhythm.append({
                    "id": 0, "semi": None, "side": sec["side"],
                    "time": t, "measure": m, "offset": off16,
                    "sLen": 0.0, "phrase": "rhythm",
                })
        all_notes.extend(rhythm)

        if difficulty == "hard":
            continue

    # Sort by time before lane reassignment
    all_notes.sort(key=lambda n: (n["time"], n["id"]))

    # ── 3. Jack protection: max 3 same lane in a row ─────────────────
    _protect_jacks(all_notes)

    # ── 4. De-dupe collisions from lane reassignment ─────────────────
    all_notes = _dedupe_by_time(all_notes)

    # ── 5. Sustains: every section ends on a held note (hard only) ────
    if difficulty == "hard":
        for i, sec in enumerate(secs):
            kept = [n for n in all_notes
                    if sec["index"] <= n["measure"] < sec["index"] + sec["measures"]]
            if kept:
                last = max(kept, key=lambda n: n["time"])
                hold_ms = beat(song) * 1000.0 * (
                    2.0 if sec["role"] in ("build", "finale") else 1.0
                )
                last["sLen"] = max(last.get("sLen", 0.0), hold_ms)

    # ── 6. Easy charts: no sustains ──────────────────────────────────
    if difficulty == "easy":
        for n in all_notes:
            n["sLen"] = 0.0

    # ── 7. Finale two-lane chords (hard only) ────────────────────────
    hands_from = song.get("hands_from")
    if hands_from is not None and difficulty == "hard":
        beats = beat(song) * 1000.0
        extra = []
        for i, sec in enumerate(secs):
            if i < hands_from:
                continue
            for n in sec["notes"]:
                if n["side"] != "player":
                    continue
                if abs((n["time"] - measure_time(song, n["measure"])) % beats) > 1.0:
                    continue
                extra.append({"id": (n["id"] + 2) % 4, "side": "player",
                              "semi": n.get("semi"), "time": n["time"],
                              "measure": n["measure"], "sLen": 0.0,
                              "phrase": "finale_hands"})
        all_notes.extend(extra)

    all_notes.sort(key=lambda n: (n["time"], n["side"], n["id"]))
    for n in all_notes:
        n.setdefault("sLen", 0.0)
    return all_notes


# --------------------------------------------------------------------------- #
# Helpers used by notes() but defined below for readability.
# --------------------------------------------------------------------------- #

def _protect_jacks(notes):
    """No lane may be hit more than MAX_SAME_LANE_RUN times in a row.

    Nudges offending notes to a free lane. Keeps natural lanes wherever they
    are playable — no forced hand alternation. Iterates until convergence
    because nudging one note to a new lane can create a fresh run on that
    lane with the notes that follow.
    """
    by_side = {}
    for n in notes:
        by_side.setdefault(n["side"], []).append(n)

    for _ in range(10):  # iterate until no run exceeds the limit
        nudges = 0
        for side_notes in by_side.values():
            side_notes.sort(key=lambda n: (n["time"], n["id"]))
            last_lane = None
            run = 0
            for n in side_notes:
                if n["id"] == last_lane:
                    run += 1
                else:
                    run = 1
                if run > MAX_SAME_LANE_RUN:
                    taken = {m["id"] for m in side_notes
                             if abs(m["time"] - n["time"]) < 1.0}
                    for candidate in (0, 1, 2, 3):
                        if candidate != n["id"] and candidate not in taken:
                            n["id"] = candidate
                            nudges += 1
                            break
                    last_lane = n["id"]
                    run = 1
                else:
                    last_lane = n["id"]
        if nudges == 0:
            break


def _dedupe_by_time(notes):
    """Drop duplicate notes at the same time+lane. Keep the first."""
    seen = set()
    out = []
    for n in sorted(notes, key=lambda x: (x["time"], x["id"])):
        key = (round(n["time"], 3), n["id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out
