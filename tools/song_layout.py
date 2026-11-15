"""
Super Scary Trollge -- shared song layout for all three songs.

Every generator in `tools/` imports this module, so the instrumental audio, the
charts and the event track can never drift apart: the melody is rendered from
the exact note list that ends up in the chart.

The three songs escalate the horror, which is expressed here as a `scare` tier:

    1. "Trolling"              scare 2/10   140 BPM   bouncy, only slightly wrong
    2. "It's Getting Dark"     scare 4/10   150 BPM   minor, distorted, stalked
    3. "Super Scary Trollge"   scare 7/10   160 BPM   16th-note chaos, screams

Codename Engine chart facts used here (verified against the engine source):
    chartVersion 1.6.0 / codenameChart: true
    strumLines[].notes[] = {time (ms), id (0-3), sLen (ms), type (int)}
    events[]             = {name, time (ms), params[]}
Strum ids: 0 = LEFT, 1 = DOWN, 2 = UP, 3 = RIGHT.
"""

import math

LEFT, DOWN, UP, RIGHT = 0, 1, 2, 3

SCALE = [0, 2, 3, 5, 7, 8, 11]      # natural minor
HARMONIC = [0, 2, 3, 5, 7, 8, 11]   # same degrees, the leading tone lives in the chords
ID_TO_DEGREE = {LEFT: 0, DOWN: 2, UP: 4, RIGHT: 6}


# --------------------------------------------------------------------------- #
# Song definitions
#
# `count`  = notes per section
# `spacings` = distance between notes in 16ths, per section
# A section therefore lasts (count * spacing / 16) measures, so the whole song
# is `sum(count * spacing for spacing in spacings) / 16` measures long.
# --------------------------------------------------------------------------- #

SONGS = [
    {
        "id": "trolling",
        "display": "Trolling",
        # Character ids come from data/characters/<id>.xml.
        "bf": "bf",
        "trollge": "trollge",
        "bpm": 140.0,
        "scare": 2,
        "offset": 1.1428571428571428,
        "count": 16,
        "spacings": [4, 4, 4, 2, 4, 4, 4, 2, 4, 4, 4, 4, 4, 4, 4, 4],
        "tonic": 50,  # D3
        "progression": [
            (0, [0, 3, 7]),
            (0, [0, 3, 7]),
            (-4, [-4, 0, 3]),
            (-4, [-4, 0, 3]),
            (3, [3, 7, 10]),
            (3, [3, 7, 10]),
            (-2, [-2, 2, 5]),
            (-2, [-2, 2, 5]),
        ],
        "section_names": [
            "WAKE UP", "POKE", "GIGGLE", "TROLL FACE",
            "HELLO THERE", "SCRIBBLE", "MISCHIEF", "SNICKER",
            "STARE", "WHY SO SERIOUS", "GIGGLE AGAIN", "TROLL",
            "MORE TROLL", "HEHEHE", "TOO EASY", "NOT SCARY YET",
        ],
        # story events -> (seconds, hscript function)
        "events": [
            (22.0, "trollgeDistort"),
            (58.0, "trollgeStatic"),
            (92.0, "trollgeDistort"),
        ],
    },
    {
        "id": "getting_dark",
        "display": "It's Getting Dark",
        "bf": "bf",          # swap to "bf_getting_dark" once that skin is uploaded
        "trollge": "trollge",
        "bpm": 150.0,
        "scare": 4,
        "offset": 1.2,
        "count": 16,
        "spacings": [4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4, 2, 2, 2, 4, 2, 4],
        "tonic": 50,
        "progression": [
            (0, [0, 3, 7]),
            (0, [0, 3, 7]),
            (-4, [-4, 0, 3]),
            (-4, [-4, 0, 3]),
            (5, [5, 8, 12]),
            (5, [5, 8, 12]),
            (-1, [-1, 3, 6]),
            (-1, [-1, 3, 6]),
        ],
        "section_names": [
            "IT'S GETTING DARK", "FOOTSTEPS", "SOMETHING MOVES", "DON'T LOOK",
            "THE GRIN", "CLOSER", "BEHIND YOU", "HE KNOWS",
            "WHY ARE YOU RUNNING", "TOO LATE", "THE DOOR", "HE'S IN",
            "TROLLGE SMILES", "NO ESCAPE", "SCREAM", "RUN RUN RUN",
            "HE IS EVERYWHERE", "TROLLGED", "THE END", "GOODNIGHT",
        ],
        "events": [
            (26.0, "trollgeStatic"),
            (36.0, "trollgeJumpScare"),
            (52.0, "trollgeDistort"),
            (66.0, "trollgeScreenShake"),
            (80.0, "trollgeStatic"),
            (92.0, "trollgeJumpScare"),
        ],
    },
    {
        "id": "super_scary",
        "display": "Super Scary Trollge",
        "bf": "bf_super_scary",      # art_src/bf/Boyfriend_crazy2.png -> tools/make_bf.py
        "trollge": "trollge",
        "bpm": 160.0,
        "scare": 7,
        "offset": 1.5,
        "count": 32,
        "spacings": [2, 2, 1, 2, 2, 1, 2, 2, 1, 2, 2, 1, 2, 2, 1, 2, 2, 1, 2, 2],
        "tonic": 47,  # B2 -- lower, heavier
        "progression": [
            (0, [0, 3, 6]),      # tritone instead of the fifth
            (0, [0, 3, 6]),
            (-1, [-1, 2, 5]),
            (-1, [-1, 2, 5]),
            (6, [6, 9, 0]),
            (6, [6, 9, 0]),
            (-2, [-2, 1, 4]),
            (-2, [-2, 1, 4]),
        ],
        "section_names": [
            "SUPER SCARY", "TROLLGE HAS YOU", "DON'T BLINK", "THE SCREAM",
            "HE IS EVERYWHERE", "THE SCREAM", "REALITY BREAKS", "THE SCREAM",
            "MORE", "THE SCREAM", "IT NEVER ENDS", "THE SCREAM",
            "ABSOLUTE TERROR", "THE SCREAM", "TROLLGE WINS", "THE SCREAM",
            "GOODBYE", "THE SCREAM", "PLEASE STOP", "THE SCREAM",
        ],
        "events": [
            (12.0, "trollgeJumpScare"),
            (24.0, "trollgeScreenShake"),
            (33.0, "trollgeDistort"),
            (42.0, "trollgeJumpScare"),
            (52.0, "trollgeStatic"),
            (60.0, "trollgePhase2"),
            (66.0, "trollgeJumpScare"),
            (74.0, "trollgeScreenShake"),
            (82.0, "trollgeDistort"),
            (88.0, "trollgeInvert"),
            (94.0, "trollgeJumpScare"),
            (100.0, "trollgeInvert"),
        ],
    },
]

SONGS_BY_ID = {s["id"]: s for s in SONGS}


def characters(song, side="player"):
    """Character id used by the chart strum line ("player" or "opponent")."""
    return song["bf"] if side == "player" else song["trollge"]


# --------------------------------------------------------------------------- #
# Derived values
# --------------------------------------------------------------------------- #

def beat(song):
    return 60.0 / song["bpm"]


def step(song):
    return beat(song) / 4.0


def measure(song):
    return beat(song) * 4.0


def measures(song):
    return sum(song["count"] * sp for sp in song["spacings"]) // 16


def length(song):
    return song["offset"] + measures(song) * measure(song)


def measure_time(song, index):
    """Absolute time (ms) of the start of `index`."""
    return (song["offset"] + index * measure(song)) * 1000.0


def section_time(song, index):
    return measure_time(song, song["_section_measures"][index])


# --------------------------------------------------------------------------- #
# Sections & notes
# --------------------------------------------------------------------------- #

def _prepare(song):
    if "_section_measures" in song:
        return song
    starts, m = [], 0
    for sp in song["spacings"]:
        starts.append(m)
        m += song["count"] * sp // 16
    song["_section_measures"] = starts
    song["_measures"] = m
    return song


#: Rendering "shapes" per section -- keeps the riff moving instead of looping one
#: 16-note cell for three minutes.
SHAPES = [
    "0123321001233210",
    "0123012332103210",
    "3210321012301230",
    "0120212021021201",
    "0123012301230123",
    "3021302130213021",
    "1203120312031203",
    "2103210321032103",
    "0321032103210321",
    "0123012332103210",
    "1230123012301230",
    "3012301230123012",
]

SIDE_PATTERNS = [
    "OOOOPPPPOOOOPPPP",
    "OPOPOPOPPOPOPOPO",
    "OPOPOPOPOPOPOPOP",
    "OOOPPPPOOOPPPPPP",
    "PPPOOOOPPPPOOOO",
]


def sections(song):
    _prepare(song)
    out = []
    for i, (sp, start) in enumerate(zip(song["spacings"], song["_section_measures"])):
        note_count = song["count"]
        shape = SHAPES[i % len(SHAPES)]
        ids = [int(shape[j % len(shape)]) for j in range(note_count)]
        side_pat = SIDE_PATTERNS[i % len(SIDE_PATTERNS)]

        notes = []
        for j in range(note_count):
            steps = j * sp
            # Mirror the riff every other section so it "answers" itself.
            nid = ids[j] if i % 2 == 0 else 3 - ids[j]
            notes.append(
                {
                    "id": nid,
                    "side": "player" if side_pat[j % len(side_pat)] == "P" else "opponent",
                    "time": measure_time(song, start) + steps * step(song) * 1000.0,
                    "measure": start + int(steps // 16),
                }
            )
        name = song["section_names"][i % len(song["section_names"])]
        out.append(
            {
                "index": i,
                "name": name,
                "time": measure_time(song, start),
                "measures": note_count * sp // 16,
                "notes": notes,
            }
        )
    return out


#: Sections that end on a held note (sustains make the chart breathe).
SUSTAIN_EVERY = 4
SUSTAIN_MS_FACTOR = 2.0


def notes(song):
    all_notes = []
    secs = sections(song)
    for section in secs:
        all_notes.extend(section["notes"])

    all_notes.sort(key=lambda n: (n["time"], n["side"]))

    for i, section in enumerate(secs):
        if i % SUSTAIN_EVERY != SUSTAIN_EVERY - 1:
            continue
        last = section["notes"][-1]
        for n in all_notes:
            if n is last:
                n["sLen"] = beat(song) * 1000.0 * SUSTAIN_MS_FACTOR
                break
    for n in all_notes:
        n.setdefault("sLen", 0.0)
    return all_notes


# --------------------------------------------------------------------------- #
# Musical helpers used by the audio renderer
# --------------------------------------------------------------------------- #

def chord_for_measure(song, index):
    prog = song["progression"]
    return prog[index % len(prog)]


def note_pitch(song, measure_index, strum_id, octave_shift=0):
    root, _tones = chord_for_measure(song, measure_index)
    degree = SCALE[ID_TO_DEGREE[strum_id] % len(SCALE)]
    return song["tonic"] + root + degree + 12 * (1 + octave_shift)


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #

def story_events(song):
    """Scripted story beats (handled by trollge_song_behavior.hx)."""
    events = []
    for seconds, func in song["events"]:
        events.append(
            {"name": "HScript Call", "time": round(seconds * 1000.0, 3), "params": [func, "1"]}
        )
        # A flash / zoom on every scripted beat makes them land.
        events.append(
            {"name": "Camera Flash", "time": round(seconds * 1000.0, 3),
             "params": [False, "0xFFFFFFFF", 2, "camGame"]}
        )
        events.append(
            {"name": "Add Camera Zoom", "time": round(seconds * 1000.0, 3),
             "params": [0.04 + 0.02 * (song["scare"] / 10.0), "camGame"]}
        )
    return events


def camera_events(song):
    """Per-chart camera movement, alternating between the two characters."""
    events = []
    for i, section in enumerate(sections(song)):
        cam = i % 2
        events.append(
            {
                "name": "Camera Movement",
                "time": round(section["time"], 3),
                "params": [cam, True, 4, "smoothStep", "InOut", 0, 0],
            }
        )
        if i % 3 == 2:
            events.append(
                {"name": "Add Camera Zoom", "time": round(section["time"], 3),
                 "params": [0.02 * song["scare"] / 2.0, "camGame"]}
            )
    return events
