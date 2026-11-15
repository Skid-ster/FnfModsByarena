"""
Super Scary Trollge -- shared song layout for all five songs.

Every generator in `tools/` imports this module, so the instrumental audio, the
charts and the event track can never drift apart: the melody is rendered from
the exact note list that ends up in the chart.

The five songs escalate the horror, which is expressed here as a `scare` tier:

    1. "Trolling"              scare  2/10   140 BPM   bouncy, only slightly wrong
    2. "It's Getting Dark"     scare  4/10   150 BPM   minor, distorted, stalked
    3. "Don't Look Back"       scare  6/10   152 BPM   glitched, something follows
    4. "Super Scary Trollge"   scare  8/10   160 BPM   16th-note chaos, screams
    5. "The Incident"          scare 10/10   170 BPM   the origin, nothing resolves

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

#: Instrumental identity per song: same renderer, different kit, bass and lead.
#:   bounce     -- 8-bit pluck lead, clap backbeat, round sub, bouncy
#:   trap       -- half-time 808, rolling hats, FM bell lead, haunted
#:   industrial -- distorted kit, screaming lead, 16th drive, hostile
#:   glitch     -- bitcrushed chip lead, gated stutter hats, 808 kick
#:   finale     -- industrial kit + FM bell doubling, choir pad, maximum chaos
STYLES = ("bounce", "trap", "glitch", "industrial", "finale")

NOTESKIN_PLAIN = None         # song 1 uses images/game/notes/default
NOTESKIN_DARK = "shadow"      # song 2: colour drained out
NOTESKIN_CORRUPT = "corrupt"  # songs 3-4: glitched arrows
NOTESKIN_TORN = "torn"        # song 5: burnt through

SONGS = [
    {
        "id": "trolling",
        "display": "Trolling",
        # Character ids come from data/characters/<id>.xml.
        "bf": "bf_blue",         # art_src/bf/new_blue_boyfriend.* -> tools/make_characters.py
        "trollge": "trollge",    # art_src/trollge/trollge.*  (phase 1, clean)
        "style": STYLES[0],
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
        "bf": "bf_smiler",       # art_src/bf/Smiler_Boyfriend_3.* -> tools/make_characters.py
        "trollge": "trollge",   # starts clean, mutates at 62 s (see events)
        "noteskin": NOTESKIN_DARK,      # images/game/notes/<id> (tools/make_noteskin.py)
        "style": STYLES[1],
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
            (62.0, "trollgeToGlitch"),    # phase 2 arrives
            (66.0, "trollgeScreenShake"),
            (80.0, "trollgeStatic"),
            (92.0, "trollgeJumpScare"),
        ],
    },
    {
        "id": "dont_look_back",
        "display": "Don't Look Back",
        "bf": "bf_glitched",      # blue BF, corrupted (tools/make_characters.py "tint")
        "trollge": "trollge_glitch",  # phase 2 in, phase 3 out (event at 75 s)
        "noteskin": NOTESKIN_CORRUPT,
        "style": STYLES[2],
        "bpm": 152.0,
        "scare": 6,
        "offset": 1.4,
        "count": 32,
        "spacings": [2, 2, 2, 1, 2, 2, 2, 1, 2, 2, 2, 1, 2, 2, 2, 1, 2, 2, 2, 1],
        "tonic": 49,  # C#3
        "progression": [
            (0, [0, 3, 7]),
            (0, [0, 3, 6]),      # the fifth slips to a tritone
            (-2, [-2, 1, 5]),
            (-2, [-2, 1, 5]),
            (4, [4, 7, 11]),
            (4, [4, 7, 11]),
            (-3, [-3, 0, 6]),
            (-3, [-3, 0, 6]),
        ],
        "section_names": [
            "DON'T LOOK BACK", "SOMETHING FOLLOWS", "COUNT THE STEPS", "TOO MANY STEPS",
            "IT IS BEHIND YOU", "DO NOT TURN", "YOU TURNED", "THE GRIN AGAIN",
            "FASTER", "FASTER", "THE HALL BENDS", "IT IS IN FRONT NOW",
            "WHICH ONE IS REAL", "BOTH OF THEM", "STATIC IN THE AIR", "HE IS INSIDE THE SONG",
            "THE PICTURE BREAKS", "DO NOT LOOK BACK", "YOU LOOKED", "TROLLGE",
        ],
        "events": [
            (14.0, "trollgeStatic"),
            (26.0, "trollgeScreenShake"),
            (34.0, "trollgeDistort"),
            (46.0, "trollgeJumpScare"),
            (58.0, "trollgeInvert"),
            (70.0, "trollgeStatic"),
            (75.0, "trollgeToStatic"),    # phase 3 arrives
            (80.0, "trollgeJumpScare"),
            (90.0, "trollgeScreenShake"),
            (102.0, "trollgeJumpScare"),
        ],
    },
    {
        "id": "super_scary",
        "display": "Super Scary Trollge",
        "bf": "bf_super_scary",      # art_src/bf/Boyfriend_crazy2.png -> tools/make_characters.py
        "trollge": "trollge_static",   # art_src/trollge/trollgeStatic1.* (phase 3)
        "noteskin": NOTESKIN_CORRUPT,
        "style": STYLES[3],
        "hands_from": 17,          # last three sections: two-lane chords on the beat
        "bpm": 160.0,
        "scare": 8,
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
            (60.0, "trollgeFinalForm"),   # phase 3 -> red-eyed final form
            (66.0, "trollgeJumpScare"),
            (74.0, "trollgeScreenShake"),
            (82.0, "trollgeDistort"),
            (88.0, "trollgeInvert"),
            (94.0, "trollgeJumpScare"),
            (96.0, "trollgeSad"),         # ...and then he just stands there
            (100.0, "trollgeInvert"),
        ],
    },
    {
        "id": "the_incident",
        "display": "The Incident",
        "bf": "bf_damned",       # bf_super_scary recoloured (tools/make_characters.py "tint")
        "trollge": "trollge_final",   # red-eyed final form from the first beat
        "noteskin": NOTESKIN_TORN,
        "style": STYLES[4],
        "hands_from": 15,
        "bpm": 170.0,
        "scare": 10,
        "offset": 1.6,
        "count": 32,
        "spacings": [1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2],
        "tonic": 45,  # A2 -- the bottom of the register
        "progression": [
            (0, [0, 1, 6]),      # semitone + tritone: nothing resolves
            (0, [0, 1, 6]),
            (-1, [-1, 0, 5]),
            (-1, [-1, 0, 5]),
            (5, [5, 6, 11]),
            (5, [5, 6, 11]),
            (-6, [-6, -5, 0]),
            (-6, [-6, -5, 0]),
        ],
        "section_names": [
            "THE INCIDENT", "IT STARTED HERE", "NOBODY CAME", "THE FIRST SCREAM",
            "HE WAS ALWAYS THERE", "THE FIRST SCREAM", "WE SHOULD HAVE RUN", "THE FIRST SCREAM",
            "EVERYTHING BURNS", "THE FIRST SCREAM", "DO NOT REMEMBER", "THE FIRST SCREAM",
            "HE IS EVERYWHERE", "THE FIRST SCREAM", "THE PICTURE IS GONE", "THE FIRST SCREAM",
            "THERE IS NO ENDING", "THE FIRST SCREAM", "TROLLGE WINS", "THE FIRST SCREAM",
            "GOODBYE", "THE FIRST SCREAM", "I AM SORRY", "THE INCIDENT",
        ],
        "events": [
            (8.0, "trollgeJumpScare"),
            (14.0, "trollgeScreenShake"),
            (20.0, "trollgeDistort"),
            (26.0, "trollgeInvert"),
            (32.0, "trollgeJumpScare"),
            (38.0, "trollgeStatic"),
            (44.0, "trollgeScreenShake"),
            (50.0, "trollgeJumpScare"),
            (56.0, "trollgeInvert"),
            (62.0, "trollgeDistort"),
            (68.0, "trollgeJumpScare"),
            (74.0, "trollgeScreenShake"),
            (79.0, "trollgeInvert"),
            (84.0, "trollgeToSad"),        # he stops fighting. the incident is over.
            (86.0, "trollgeJumpScare"),
            (88.0, "trollgeStatic"),
        ],
    },
]

SONGS_BY_ID = {s["id"]: s for s in SONGS}


def note_types(song):
    """Chart `noteTypes` list: the engine maps note type 0 onto it, so a single
    entry re-skins every arrow of that song (Note.hx -> game/notes/<name>)."""
    skin = song.get("noteskin")
    return [skin] if skin else []


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
SUSTAIN_EVERY = 2
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
    # Finale hands: from `hands_from` onward the player also hits the opposite
    # lane on every beat, which is what pushes the last act to 7/10.
    hands_from = song.get("hands_from")
    if hands_from is not None:
        secs = sections(song)
        beats = beat(song) * 1000.0
        extra = []
        for i, section in enumerate(secs):
            if i < hands_from:
                continue
            for n in section["notes"]:
                if n["side"] != "player":
                    continue
                if abs((n["time"] - measure_time(song, n["measure"])) % beats) > 1.0:
                    continue
                extra.append({"id": (n["id"] + 2) % 4, "side": "player",
                              "time": n["time"], "measure": n["measure"], "sLen": 0.0})
        all_notes.extend(extra)
        all_notes.sort(key=lambda n: (n["time"], n["side"], n["id"]))

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
