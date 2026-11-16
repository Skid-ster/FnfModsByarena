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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phrases import PHRASES, SCALES  # noqa: E402  (the music, not the code)

LEFT, DOWN, UP, RIGHT = 0, 1, 2, 3

#: Degrees (in the song's scale) each arrow lane is allowed to sound: tonic,
#: flat third, fifth, flat seventh. The lane is the degree *class*, so a phrase
#: may sing any octave of those four degrees while the four arrows keep one
#: identity for the whole song. `note_pitch()` turns lane + octave into MIDI.
LANE_CLASS = (0, 2, 4, 6)


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

#: Rhythm cells -- one bar written as 16th-note offsets.
HALF = "HALF"
QUARTERS = "QUARTERS"
QUARTERS_SYNC = "QUARTERS_SYNC"
CLAP = "CLAP"
TRAP = "TRAP"
DRIVE = "DRIVE"
SKITTER = "SKITTER"

CELLS = {
    HALF:          [0, 8],
    QUARTERS:      [0, 4, 8, 12],
    QUARTERS_SYNC: [0, 3, 8, 11],       # pushes the "and" of 1 and 3
    CLAP:          [0, 6, 8, 14],       # backbeat with a late pickup
    TRAP:          [0, 4, 8, 10, 12],
    DRIVE:         [0, 2, 4, 8, 10, 12],
    SKITTER:       [0, 3, 6, 8, 11, 14],
}


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
        "scroll": 1.60,   # hard-mode scroll speed (base game: 1.2-2.6)
        "section_measures": [4, 4, 4, 2, 4, 4, 4, 2, 4, 4, 4, 4, 4, 4, 4, 4],   # bars per section (FNF counts sections in 4-bar blocks)
        "cells": [HALF, HALF, QUARTERS, HALF],
        # Form: one phrase per chart block, laid out by `sections()`. The
        # opponent sings the antecedent of each pair, the player the consequent;
        # the chorus is the 8-bar hook you should be able to hum.
        "form": ["intro", "verse_a", "verse_b", "chorus_a", "chorus_b",
                 "verse_c", "verse_d", "chorus_a", "chorus_b", "verse_a",
                 "build", "chorus_a", "break", "verse_d", "finale", "finale"],
        "captions": [
            (14.0, "he isn't even trying"),
            (46.0, "that is the scary part"),
            (74.0, "don't get comfortable"),
        ],
        "cutscene": {
            "frame": "ui/cutscene_frame",
            "tag": "TROLLGE WEEK  //  1 OF 5",
            "lines": [
                ("TROLLGE", "hey. you're the guy from the video.", 1.0),
                ("BF", "beep bop! i'm gonna win.", 0.0),
                ("TROLLGE", "sure you are.", 1.4),
            ],
            "outro": [
                ("", "he only ever wanted a friend.", 0.0),
                ("", "that is the scary part.", 0.0),
            ],
        },
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
        "id": "getting-dark",
        "display": "It's Getting Dark",
        "bf": "bf_smiler",       # art_src/bf/Smiler_Boyfriend_3.* -> tools/make_characters.py
        "trollge": "trollge",   # starts clean, mutates at 62 s (see events)
        "noteskin": NOTESKIN_DARK,      # images/game/notes/<id> (tools/make_noteskin.py)
        "style": STYLES[1],
        "bpm": 150.0,
        "scare": 4,
        "offset": 1.2,
        "scroll": 1.85,   # hard-mode scroll speed (base game: 1.2-2.6)
        "section_measures": [4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4, 2, 2, 2, 4, 2, 4],   # bars per section (FNF counts sections in 4-bar blocks)
        "cells": [CLAP, HALF, QUARTERS, HALF],
        "form": ["intro", "verse_a", "verse_b", "chorus_a", "chorus_b",
                 "verse_a", "verse_b", "verse_c", "verse_d", "break",
                 "break", "chorus_a", "chorus_b", "verse_c", "build",
                 "verse_d", "break", "chorus_a", "finale", "finale"],
        "captions": [
            (18.0, "the lights are going out"),
            (52.0, "eyes on the arrows"),
            (86.0, "he is closer than he was"),
        ],
        "cutscene": {
            "frame": "ui/cutscene_frame",
            "tag": "TROLLGE WEEK  //  2 OF 5",
            "lines": [
                ("TROLLGE", "it's getting dark.", 1.2),
                ("BF", "it's still light out??", 0.0),
                ("TROLLGE", "not for long.", 1.6),
            ],
            "outro": [
                ("", "the light went out on its own.", 0.0),
            ],
        },
        "tonic": 48,  # C3 -- a semitone under the D minor opener
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
        "id": "dont-look-back",
        "display": "Don't Look Back",
        "bf": "bf_glitched",      # blue BF, corrupted (tools/make_characters.py "tint")
        "trollge": "trollge_glitch",  # phase 2 in, phase 3 out (event at 75 s)
        "noteskin": NOTESKIN_CORRUPT,
        "style": STYLES[2],
        "bpm": 152.0,
        "scare": 6,
        "offset": 1.4,
        "scroll": 2.05,   # hard-mode scroll speed (base game: 1.2-2.6)
        "section_measures": [4, 4, 4, 2, 4, 4, 4, 2, 4, 4, 4, 2, 4, 4, 4, 2, 4, 4, 4, 2],   # bars per section (FNF counts sections in 4-bar blocks)
        "cells": [QUARTERS, QUARTERS, QUARTERS_SYNC, TRAP],
        "form": ["intro", "verse_a", "verse_b", "chorus_a", "chorus_b",
                 "verse_a", ("verse_c", 2), "verse_d", "chorus_a", "break",
                 "break", "verse_b", "chorus_b", "verse_c", "build",
                 "verse_d", "break", "chorus_a", "finale", "finale"],
        "captions": [
            (16.0, "don't look back"),
            (48.0, "you looked"),
            (78.0, "it doesn't matter now"),
            (100.0, "he was always behind you"),
        ],
        "cutscene": {
            "frame": "ui/cutscene_frame_dark",
            "tag": "TROLLGE WEEK  //  3 OF 5",
            "lines": [
                ("TROLLGE", "don't look back.", 1.4),
                ("BF", "why not?", 0.0),
                ("TROLLGE", "because i'm already there.", 2.0),
            ],
            "outro": [
                ("", "you looked.", 0.0),
            ],
        },
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
        "id": "super-scary",
        "display": "Super Scary Trollge",
        "bf": "bf_super_scary",      # art_src/bf/Boyfriend_crazy2.png -> tools/make_characters.py
        "trollge": "trollge_static",   # art_src/trollge/trollgeStatic1.* (phase 3)
        "noteskin": NOTESKIN_CORRUPT,
        "style": STYLES[3],
        "hands_from": 17,          # last three sections: two-lane chords on the beat
        "bpm": 160.0,
        "scare": 8,
        "offset": 1.5,
        "scroll": 2.25,   # hard-mode scroll speed (base game: 1.2-2.6)
        "section_measures": [4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4, 2, 4, 4],   # bars per section (FNF counts sections in 4-bar blocks)
        "cells": [QUARTERS, TRAP, DRIVE, QUARTERS],
        "form": ["intro", "verse_a", "verse_b", "chorus_a", "chorus_b",
                 "verse_a", "verse_c", "verse_b", "chorus_a", "break",
                 "break", "verse_b", "chorus_b", "verse_c", "build",
                 "verse_d", "break", "chorus_a", "finale", "finale"],
        "captions": [
            (20.0, "this is what he really looks like"),
            (56.0, "it stopped being a mask"),
            (88.0, "keep going. please."),
        ],
        "cutscene": {
            "frame": "ui/cutscene_frame_dark",
            "tag": "TROLLGE WEEK  //  4 OF 5",
            "lines": [
                ("TROLLGE", "you keep coming back.", 1.6),
                ("BF", "i don't have a choice!", 0.0),
                ("TROLLGE", "neither do i.", 2.2),
            ],
            "outro": [
                ("", "something followed you home.", 0.0),
            ],
        },
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
        "id": "the-incident",
        "display": "The Incident",
        "bf": "bf_damned",       # bf_super_scary recoloured (tools/make_characters.py "tint")
        "trollge": "trollge_final",   # red-eyed final form from the first beat
        "noteskin": NOTESKIN_TORN,
        "style": STYLES[4],
        "hands_from": 15,
        "bpm": 170.0,
        "scare": 10,
        "offset": 1.6,
        "scroll": 2.45,   # hard-mode scroll speed (base game: 1.2-2.6)
        "section_measures": [2, 2, 4, 2, 2, 4, 2, 2, 4, 2, 2, 4, 2, 2, 4, 2, 2, 4, 2, 2, 4, 2, 2, 4, 4, 2, 2, 4],   # bars per section (FNF counts sections in 4-bar blocks)
        "cells": [TRAP, DRIVE, SKITTER, QUARTERS],
        "form": ["intro", "verse_a", "verse_b", "chorus_a", "chorus_b",
                 "verse_a", "verse_b", "verse_c", "verse_d", "chorus_a",
                 "chorus_b", "verse_c", "verse_d", "break", "break",
                 "chorus_a", "chorus_b", "verse_d", "chorus_a", "chorus_b",
                 "verse_b", "break", "break", "chorus_a", ("chorus_b", 2),
                 "finale", "finale", "verse_d"],
        "captions": [
            (12.0, "this is where it started"),
            (40.0, "nobody came"),
            (70.0, "the first scream"),
            (96.0, "don't remember"),
            (104.0, "goodbye"),
        ],
        "cutscene": {
            "frame": "ui/cutscene_frame_dark",
            "tag": "TROLLGE WEEK  //  5 OF 5",
            "lines": [
                ("TROLLGE", "this is where it started.", 1.8),
                ("BF", "...where what started?", 0.6),
                ("TROLLGE", "the incident.", 2.6),
            ],
            "outro": [
                ("", "GOODBYE.", 2.0),
                ("", "he stopped fighting.", 1.0),
                ("", "the incident is over.", 0.0),
                ("", "...or maybe it never ended.", 0.6),
            ],
        },
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
            "HE IS HERE", "NO ONE LEAVES", "I AM SORRY", "GOODBYE",
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
            (94.0, "trollgeInvert"),
            (101.0, "trollgeToSad"),       # he stops fighting. the incident is over.
            (103.0, "trollgeJumpScare"),
            (106.0, "trollgeStatic"),
        ],
    },
]

SONGS_BY_ID = {s["id"]: s for s in SONGS}


def note_types(song):
    """Chart `noteTypes` list: the engine maps note type 0 onto it, so a single
    entry re-skins every arrow of that song (Note.hx -> game/notes/<name>)."""
    skin = song.get("noteskin")
    return [skin] if skin else []


#: Note names for the stated key of each song (base game lists one per track).
NOTE_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")


def key_name(song):
    """Stated key of the song, e.g. "D minor"."""
    return NOTE_NAMES[song["tonic"] % 12] + " minor"


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
    return sum(song["section_measures"])


def length(song):
    return song["offset"] + measures(song) * measure(song)


def measure_time(song, index):
    """Absolute time (ms) of the start of `index`."""
    return (song["offset"] + index * measure(song)) * 1000.0


def section_time(song, index):
    _prepare(song)
    return measure_time(song, song["_block_starts"][index])


# --------------------------------------------------------------------------- #
# Sections & notes
#
# Charting conventions copied from the base game (see docs/charting.md):
#   * a chart section is one bar (16 steps, `lengthInSteps: 16`),
#   * one character sings a whole phrase block (2-4 bars) and the other answers,
#     so every section belongs to exactly one side (`mustHitSection`),
#   * rhythms are 16th-note cells, not a constant stream: week 1 sings halves and
#     quarters, the hardest songs add eighths and short 16th runs.
# --------------------------------------------------------------------------- #

def _prepare(song):
    if "_block_starts" in song:
        return song
    starts, m = [], 0
    for bars in song["section_measures"]:
        starts.append(m)
        m += bars
    song["_block_starts"] = starts
    song["_measures"] = m
    return song


#: How hard each part of the arrangement pushes, by section role.
ROLE_GAIN = {
    "intro": 0.10,
    "verse": 0.70,
    "build": 0.86,
    "drop": 1.04,
    "break": 0.18,
    "finale": 1.12,
}


def section_roles(song):
    """One arrangement role per phrase block, shared by the audio and the chart.

    The audio renderer drops the drums on a "break" block; the chart writes a
    sparse cell there, so the two never disagree about where the song breathes.
    """
    count = len(song["section_measures"])
    roles = []
    for i in range(count):
        position = i / max(1, count - 1)
        density = len(CELLS[song["cells"][i % len(song["cells"])]])
        if i == 0:
            role = "intro"
        elif i >= count - 2:
            role = "finale"
        elif 0.46 <= position <= 0.54:
            role = "break"          # mid-song breakdown
        elif 0.80 <= position <= 0.86:
            role = "break"          # the breath before the last act
        elif density >= 6 and position >= 0.25:
            role = "drop"           # 16th-note sections, but not in the first quarter
        elif i % 4 == 2:
            role = "build"
        else:
            role = "verse"
        roles.append(role)
    return roles


def measure_roles(song):
    """Map absolute chart-bar indices to their section's arrangement role."""
    roles = section_roles(song)
    out = {}
    start = 0
    for bars, role in zip(song["section_measures"], roles):
        for bar in range(start, start + bars):
            out[bar] = role
        start += bars
    return out


def melodic_onsets(song):
    """Hard-chart melody without doubling unison finale hands in the audio."""
    seen = set()
    for note in notes(song, "hard"):
        key = (round(note["time"], 3), note["side"], note.get("semi"))
        if key not in seen:
            seen.add(key)
            yield note


def side_for_block(index):
    """Base-game phrasing: the opponent opens, then the two characters trade
    phrase blocks for the rest of the song (and the player always gets the last
    word)."""
    return "opponent" if index % 2 == 0 else "player"


# ---- melody --------------------------------------------------------------- #

#: Semitone offsets of each song's scale, wrapping upwards for two octaves.
def scale_steps(song):
    return [SCALES[song["id"]][i % len(SCALES[song["id"]])]
            + 12 * (i // len(SCALES[song["id"]]))
            for i in range(len(SCALES[song["id"]]) * 3)]


def degree_to_semitones(song, degree):
    """Scale position (may be negative or above the octave) -> semitones."""
    scale = SCALES[song["id"]]
    octave, index = divmod(degree, len(scale))
    return scale[index] + 12 * octave


def semitones_to_degree(song, semitones):
    """Nearest scale position for a semitone offset (octave-preserving)."""
    scale = SCALES[song["id"]]
    size = len(scale)
    octave, rest = divmod(semitones, 12)
    index = min(range(size), key=lambda i: abs(scale[i] - rest))
    if abs(scale[index] - rest) > 2:
        raise ValueError("%d semitones is not in %s" % (semitones, song["id"]))
    return octave * size + index


def _parse_phrase(song, text, name, bars):
    """Parse one phrase written in the notation documented in `tools/phrases.py`.

    Phrases are written in semitones above the tonic (12 = the octave, 15 = the
    minor third above it); they are converted to scale positions here so the
    lane rules below can talk about degrees."""
    tokens = []
    for line in text.strip().splitlines():
        tokens.extend(line.replace("|", " ").split())
    if len(tokens) != bars * 16:
        raise ValueError("%s: %d bars need %d steps, the text has %d"
                         % (name, bars, bars * 16, len(tokens)))
    events, last = [], None
    for index, token in enumerate(tokens):
        if token == ".":
            last = None
            continue
        if token == "-":
            if last is None:
                raise ValueError("%s: hold at step %d has no note before it" % (name, index))
            step, semis, degree, hold = events[last]
            events[last] = (step, semis, degree, hold + 1)
            continue
        semis = int(token)
        events.append((index, semis, semitones_to_degree(song, semis), 1))
        last = len(events) - 1
    return events


#: How many 16th steps two notes of one phrase must sit apart to be playable
#: (four lanes, two hands: anything closer than an 8th is a jack in disguise).
MIN_GAP_STEPS = 2


def _lanes_for_phrase(song, events):
    """A phrase's scale degrees -> arrow lanes plus the octave each note sings.

    The lane is the note's degree *class* modulo the scale size, so a phrase that
    walks up keeps its four lanes and a phrase that leaps an octave lands on the
    same lane again. Two rules keep the result chartable:

      * a note may not reuse the previous lane inside `MIN_GAP_STEPS` steps (an
        octave leap over one arrow is the one thing a chart cannot express), so
        it takes the nearest free lane and keeps its register,
      * notes that are not lane degrees (the second, the sixth) take the nearest
        lane, which is what a singer does on the way past them.
    """
    size = len(SCALES[song["id"]])
    lane_size = len(LANE_CLASS)
    out = []
    last_lane, last_step = None, -99
    for step, semis, degree, hold in events:
        target = degree % size
        distances = []
        for lane, klass in enumerate(LANE_CLASS):
            gap = min(abs(target - klass), size - abs(target - klass))
            distances.append((gap, lane))
        distances.sort()
        lane = distances[0][1]
        if lane == last_lane and step - last_step < MIN_GAP_STEPS:
            lane = distances[1][1]
        # The lane is what the player hits; the semitone is what the singer
        # sings. Keeping both means a phrase can walk by step (two lanes apart
        # is still a second in the audio) while the chart stays playable.
        out.append({"step": step, "lane": lane, "semi": semis,
                    "sustain_steps": hold - 1})
        last_lane, last_step = lane, step
    return out


def phrases(song):
    """Parsed phrase library for one song: {name: {bars, notes}}."""
    if "_phrases" in song:
        return song["_phrases"]
    library = {}
    for name, text in PHRASES[song["id"]].items():
        bars = len([line for line in text.strip().splitlines() if line.strip()])
        library[name] = {"bars": bars,
                         "notes": _lanes_for_phrase(song, _parse_phrase(
                             song, text, "%s/%s" % (song["id"], name), bars))}
    song["_phrases"] = library
    return library


def _block_phrase(song, block_index, bars):
    """Which phrase (and which window of it) one phrase block sings.

    `song["form"]` names the phrase per block; `offset` picks the starting bar
    inside it. A 4-bar block that names a 2-bar phrase plays it twice, which is
    how the call in a call-and-response gets its repeat without a second
    transcription.
    """
    form = song["form"][block_index] if block_index < len(song["form"]) else "verse_a"
    if isinstance(form, tuple):
        name, offset = form
    else:
        name, offset = form, 0
    library = phrases(song)
    entry = library[name]
    return name, entry, offset % entry["bars"]


def sections(song):
    """Lay the song's phrases out over its phrase blocks.

    Every block belongs to one side (the opponent opens, then they trade) and
    sings a whole phrase; where the phrase is shorter than the block it repeats,
    and every fourth exchange the player's phrase comes back inverted -- the
    call-and-response rule this chart has always followed, now applied to real
    8- and 16-bar material instead of a four-note cell.
    """
    _prepare(song)
    out = []
    roles = section_roles(song)
    for i, (bars, start) in enumerate(zip(song["section_measures"], song["_block_starts"])):
        name, entry, window = _block_phrase(song, i, bars)
        side = side_for_block(i)
        invert = side == "player" and (i // 2) % 4 == 3
        source = entry["notes"]
        length = entry["bars"] * 16

        notes = []
        for bar in range(bars):
            phrase_bar = (window + bar) % entry["bars"]
            for note in source:
                phrase_step = note["step"]
                if not (phrase_bar * 16 <= phrase_step < (phrase_bar + 1) * 16):
                    continue
                lane = note["lane"]
                if invert:
                    lane = 3 - lane
                semi = note["semi"]
                # The build and the last act sit an octave up: same lanes, new
                # register, so the tune goes somewhere instead of looping.
                # The last bar of a build or the finale sits an octave up: same
                # lanes, new register, so the tune goes somewhere instead of
                # looping. Only notes that are still comfortably low are
                # lifted -- otherwise the top of the phrase ends up inaudibly
                # high and the sung range blows past an octave and a half.
                if roles[i] in ("build", "finale") and bar >= bars - 1 and semi <= 14:
                    semi += 12
                notes.append({
                    "id": lane,
                    "semi": semi,
                    "side": side,
                    "time": measure_time(song, start + bar) + (phrase_step % 16) * step(song) * 1000.0,
                    "measure": start + bar,
                    "offset": phrase_step % 16,
                    "sLen": note["sustain_steps"] * step(song) * 1000.0,
                    "phrase": name,
                })
        notes.sort(key=lambda n: (n["time"], n["id"]))
        # De-duplicate: a repeated lane that survived the phrase rules (easy
        # filters, inversion) is dropped rather than stacked.
        cleaned, last_time = [], {}
        for note in notes:
            key = round(note["time"], 3)
            if key in last_time:
                continue
            last_time[key] = note
            cleaned.append(note)
        notes = cleaned

        out.append({
            "index": i,
            "name": song["section_names"][i % len(song["section_names"])],
            "time": measure_time(song, start),
            "measures": bars,
            "role": roles[i],
            "side": side,
            "mustHitSection": side == "player",
            "phrase": name,
            "notes": notes,
        })
    return out


#: Difficulties, easiest first -- the same three the base game ships.
DIFFICULTIES = ("easy", "normal", "hard")

#: How many notes of a phrase block each difficulty keeps (0 = everything).
#: Base-game charts sit at roughly 1 : 2 : 3 notes for easy : normal : hard,
#: so a difficulty is a *stride* through the melody, never a different tune.
#: Hard is the melody; normal keeps three of every four notes (a phrase thinned,
#: never one missing a bar); easy keeps every second note.
DIFFICULTY_STRIDE = {"easy": 2, "normal": 4, "hard": 1}

#: The arrangement thins the early songs out and lets the later ones fill in:
#: song 1 keeps one note in every `spacing` 16ths of a phrase, song 5 keeps them
#: all. This is the "density climbs" axis of the ladder, expressed as musical
#: space rather than as a different chart.
TIER_SPACING = {2: 5, 4: 4, 6: 3, 8: 2, 10: 2}

#: Scroll speed per difficulty, inside the base game's 1.2-2.6 range.
DIFFICULTY_SCROLL = {"easy": -0.35, "normal": -0.15, "hard": 0.0}

#: A phrase block whose index is a multiple of this ends on a held note: the
#: chart breathes where the music breathes, and the sustain is the phrase's own
#: last note rather than an invented one.
SUSTAIN_EVERY = 3
SUSTAIN_MS_FACTOR = 2.0


def _keep(index, stride):
    """True when note `index` of a phrase survives that difficulty's filter."""
    if stride <= 1:
        return True
    if stride == 2:
        return index % 2 == 0
    return index % stride != stride - 1       # drop one note in `stride`


#: Two notes of one side may never be closer than this many 16th steps: an 8th
#: note is the shortest interval a four-lane chart reads as a melody rather than
#: a burst. The phrases are written to respect it, so this only trims what a
#: sustained note or an inversion collides.
MIN_SPACING_STEPS = 2


def _thin(notes, spacing=MIN_SPACING_STEPS):
    """Drop notes that would stack closer than `spacing` 16th steps apart."""
    kept = []
    for note in notes:
        if kept:
            prev = kept[-1]
            gap = (note["measure"] - prev["measure"]) * 16 + note["offset"] - prev["offset"]
            if 0 <= gap < spacing:
                continue
        kept.append(note)
    return kept or list(notes[:1])


def notes(song, difficulty="hard"):
    """Every note of `difficulty`, in time order.

    The audio renderer asks for "hard": the instrumental and both vocal tracks
    are the full melody, and the easier charts are a strided subset of the same
    notes, so the three difficulties can never disagree about timing.
    """
    if difficulty not in DIFFICULTY_STRIDE:
        raise ValueError("unknown difficulty %r" % (difficulty,))
    stride = DIFFICULTY_STRIDE[difficulty]

    secs = sections(song)
    spacing = TIER_SPACING.get(song["scare"], 1)
    all_notes = []
    for i, section in enumerate(secs):
        notes_here = section["notes"]
        if spacing > 1:
            notes_here = _thin(notes_here, spacing)
        kept = _thin(notes_here) if spacing <= MIN_SPACING_STEPS else list(notes_here)
        if stride > 1:
            kept = [n for j, n in enumerate(kept) if _keep(j, stride)]
            kept = _thin(kept) or kept[:1]
            # A strided chart must never leave a bar silent: a bar with no arrow
            # reads as a hole in the song, not as an easier chart. Where the
            # stride emptied a bar, put its *first* note back -- the downbeat is
            # the one the melody leans on.
            have = {n["measure"] for n in kept}
            for n in notes_here:
                if n["measure"] not in have:
                    kept.append(n)
                    have.add(n["measure"])
            kept.sort(key=lambda n: (n["time"], n["id"]))
        # A phrase always lands its last note: that is where the cadence is.
        if notes_here and kept[-1] is not notes_here[-1]:
            kept.append(notes_here[-1])
        section["kept"] = kept
        all_notes.extend(kept)

    all_notes.sort(key=lambda n: (n["time"], n["side"], n["id"]))

    if stride == 1:
        for i, section in enumerate(secs):
            if i % SUSTAIN_EVERY != SUSTAIN_EVERY - 1:
                continue
            last = section["kept"][-1]
            last["sLen"] = max(last.get("sLen", 0.0), beat(song) * 1000.0 * SUSTAIN_MS_FACTOR)

    # Easy charts carry no sustains at all: a hold is a reading test on top of an
    # already-thinned chart, and the base game's easy difficulty does not use them.
    # The phrase's own ties still shorten the last note, so nothing overlaps.
    if difficulty == "easy":
        for n in all_notes:
            n["sLen"] = 0.0

    # Finale hands: from `hands_from` onward the player also hits the opposite
    # lane on every beat, which is what pushes the last act to 10/10. Hard only:
    # doubled lanes are what makes a hard chart hard.
    hands_from = song.get("hands_from")
    if hands_from is not None and stride == 1:
        beats = beat(song) * 1000.0
        extra = []
        for i, section in enumerate(secs):
            if i < hands_from:
                continue
            for n in section["kept"]:
                if n["side"] != "player":
                    continue
                if abs((n["time"] - measure_time(song, n["measure"])) % beats) > 1.0:
                    continue
                extra.append({"id": (n["id"] + 2) % 4, "side": "player",
                              "semi": n.get("semi"),
                              "time": n["time"], "measure": n["measure"], "sLen": 0.0})
        all_notes.extend(extra)
        all_notes.sort(key=lambda n: (n["time"], n["side"], n["id"]))

    _break_jacks(all_notes)
    for n in all_notes:
        n.setdefault("sLen", 0.0)
    return all_notes


def _break_jacks(notes, limit=3):
    """No lane may be hit more than `limit` times in a row.

    A four-note jack is a charting bug in the base game, not a difficulty ramp:
    the arrow shapes and the finale's doubled lanes can both produce one, so the
    notes are nudged to a free lane here -- before the audio is rendered from
    them -- instead of leaving an unplayable streak in the chart.
    """
    by_side = {}
    for note in notes:
        by_side.setdefault(note["side"], []).append(note)
    for side_notes in by_side.values():
        side_notes.sort(key=lambda n: (n["time"], n["id"]))
        run_id, run_len = None, 0
        for note in side_notes:
            if note["id"] == run_id:
                run_len += 1
            else:
                run_id, run_len = note["id"], 1
            if run_len <= limit:
                continue
            taken = {m["id"] for m in side_notes if abs(m["time"] - note["time"]) < 1.0}
            for candidate in (1, 2, 3, 0):
                if candidate != note["id"] and candidate not in taken:
                    note["id"] = candidate
                    break
            run_id, run_len = note["id"], 1


def scroll_speed(song, difficulty):
    song_scroll = song.get("scroll", 1.9)
    return round(max(1.1, song_scroll + DIFFICULTY_SCROLL[difficulty]), 3)


# --------------------------------------------------------------------------- #
# Musical helpers used by the audio renderer
# --------------------------------------------------------------------------- #

def diatonic_triads(song):
    """Every chord the song's scale can build, as (root, [tones from root]).

    Triads come first, then the same roots as seventh chords, then the two sus
    forms. Horror writing lives on sevenths and suspensions -- a bar of Am7 or
    Asus4 under a melody that steps past the third is ordinary practice, and
    it gives the harmoniser an honest way to follow a tune that is not
    arpeggiating a triad. Order matters: the harmoniser takes the earliest
    chord that scores best, so plain triads win ties and the harmony stays
    unhysterical until it has a reason not to be.
    """
    scale = SCALES[song["id"]]
    size = len(scale)

    def deg(i):
        return scale[i % size] + 12 * (i // size)

    out = []
    for i in range(size):                      # plain triads
        root = deg(i)
        out.append((root, sorted({(deg(i + 2 * k) - root) % 12 for k in range(3)})))
    for i in range(size):                      # sevenths
        root = deg(i)
        out.append((root, sorted({(deg(i + 2 * k) - root) % 12 for k in range(4)})))
    for i in range(size):                      # sus2 and sus4
        root = deg(i)
        # Suspensions replace the third, not the fifth: 1-2-5 / 1-4-5.
        # The former 1-2-3 / 1-4-3 voicings created a cluster on almost
        # every bar, often masking the very hook the chord was meant to support.
        out.append((root, sorted({0, (deg(i + 1) - root) % 12,
                                  (deg(i + 4) - root) % 12})))
        out.append((root, sorted({0, (deg(i + 3) - root) % 12,
                                  (deg(i + 4) - root) % 12})))
    return out


#: Weight of a note in the harmoniser: a note on a beat decides the chord, a
#: note off the beat is colour. This is the scoring an arranger does by ear.
_CHORD_WEIGHT_STRONG = 7.0
_CHORD_WEIGHT_WEAK = 1.0
_CHORD_WEIGHT_LEAP = 0.5


def _melody_bars(song):
    """{(block_index, bar_in_block): [(semitone, step), ...]} for hard melody.

    Follow chart thinning rather than discarded notation, and collapse doubled
    hands into one musical onset. Measure indices are absolute bar indices;
    timestamps include a lead-in and must not be rounded to a different bar.
    """
    layout = sections(song)
    starts = [int(round((section["time"] - measure_time(song, 0)) /
                        (measure(song) * 1000.0))) for section in layout]
    out, seen = {}, set()
    for note in notes(song, "hard"):
        if note.get("semi") is None:
            continue
        onset = (round(note["time"], 3), note["side"], note["semi"])
        if onset in seen:
            continue
        seen.add(onset)
        block = next(i for i in range(len(starts) - 1, -1, -1)
                     if note["measure"] >= starts[i])
        bar = note["measure"] - starts[block]
        pos = int(round((note["time"] - measure_time(song, note["measure"])) /
                        (step(song) * 1000.0))) % 16
        out.setdefault((block, bar), []).append((note["semi"], pos))
    return out


def harmonise(song):
    """Choose a chord for every bar from the notes the melody actually sings.

    The progression used to be a fixed loop running off the absolute bar
    number. That is why the tunes never fitted it: the same phrase came back
    over a different chord, and a melody cannot be *written* against harmony
    that moves underneath it. Here the chords are chosen to fit the melody,
    which is the order an arranger works in -- write the tune, then harmonise
    it -- and the song's `progression` is kept only as the tie-breaker that
    decides between equally good chords (so the key still feels like the song's,
    rather than drifting wherever the tune happens to lean).

    Cached on the song dict; invalidated by not existing yet.
    """
    if "_harmony" in song:
        return song["_harmony"]
    _prepare(song)
    triads = diatonic_triads(song)
    prog = song["progression"]
    melody = _melody_bars(song)
    n_blocks = len(song["section_measures"])
    harmony = []
    for block in range(n_blocks):
        bars = song["section_measures"][block]
        # A block's first bar and its last bar carry the most weight in the ear
        # (entry and cadence), and consecutive bars should not fight: give a
        # bar a small bonus for repeating the chord before it, which is what
        # keeps a riff over one harmony instead of changing colour every bar.
        prev_chosen = None
        for bar in range(bars):
            abs_bar = song["_block_starts"][block] + bar
            notes = melody.get((block, bar), [])
            best, best_score = None, -1e9
            for ti, (root, tones) in enumerate(triads):
                pcs = {(root + t) % 12 for t in tones}
                score = 0.0
                for semi, step_in_bar in notes:
                    weight = (_CHORD_WEIGHT_STRONG if step_in_bar in (0, 4, 8, 12)
                              else _CHORD_WEIGHT_WEAK)
                    if semi % 12 in pcs:
                        score += weight
                    elif semi % 12 == root % 12:
                        score += weight * 0.5
                    else:
                        score -= weight
                # Prefer the song's own progression when it is just as good,
                # and prefer the tonic at the top of a section so cadences land.
                pref_root, _ = prog[(abs_bar - song["_block_starts"][block])
                                    % len(prog)]
                if root % 12 == pref_root % 12:
                    score += 0.6
                if prev_chosen is not None and root % 12 == prev_chosen % 12:
                    score += 1.2
                if bar == bars - 1:
                    score += 0.4
                if notes:
                    # The bar's own downbeat is what the ear checks first:
                    # give it extra weight so the harmoniser cannot average it
                    # away against a cluster of weak passing notes.
                    first = min(notes, key=lambda n: n[1])
                    if first[0] % 12 in pcs:
                        score += 2.0
                    weight_root = 1.0 if root % 12 == first[0] % 12 else 0.0
                    score += weight_root
                else:
                    score = 0.5 if root % 12 == pref_root % 12 else 0.0
                if score > best_score + 1e-9:
                    best, best_score = (root, tones), score
            harmony.append(best)
            prev_chosen = best[0]
    song["_harmony"] = harmony
    return harmony


def chord_for_measure(song, index):
    """The chord under one bar, chosen to fit the melody (see `harmonise`)."""
    harmony = harmonise(song)
    if 0 <= index < len(harmony):
        return harmony[index]
    prog = song["progression"]
    return prog[index % len(prog)]


def note_pitch(song, measure_index, strum_id, octave_shift=0, octave=0, semi=None):
    """Return the written pitch, with no automatic chord-tone substitutions.

    A chromatic passing note is part of the tune, not an error to repair. The
    lead and voice use this written pitch class; the opponent vocal is rendered
    an octave lower. The fallback is for notes without a melodic semitone.
    """
    if semi is not None:
        return int(round(song["tonic"] + 12 + semi + 12 * octave_shift))
    size = len(SCALES[song["id"]])
    klass = LANE_CLASS[strum_id]
    return int(round(song["tonic"] + degree_to_semitones(
        song, klass + size * (1 + octave + octave_shift))))


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #

def story_events(song):
    """Scripted story beats (handled by trollge_song_behavior.hx)."""
    events = []
    # Narrative captions during gameplay. "HScript Call" splits params[1] on
    # commas, so a caption with a comma simply arrives as two arguments and the
    # script joins them back together.
    for seconds, text in song.get("captions", []):
        events.append({"name": "HScript Call", "time": round(seconds * 1000.0, 3),
                       "params": ["trollgeCaption", text]})
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
    # Chronological: the engine sorts anyway, but a sorted file diffs cleanly and
    # makes the event list readable next to the chart.
    events.sort(key=lambda e: (e["time"], e["name"], e["params"][0]))
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
