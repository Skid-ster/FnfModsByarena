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
        # the hook: the four-lane figure this song is built on. The audio
        # renders these lanes as pitches, so the chart follows the melody.
        "hooks": [[0, 2, 1, 3], [3, 1, 2, 0]],
        # In-song captions: the story keeps happening while you play.
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
        # the hook: the four-lane figure this song is built on. The audio
        # renders these lanes as pitches, so the chart follows the melody.
        "hooks": [[0, 1, 0, 2], [3, 2, 1, 2]],
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
        # the hook: the four-lane figure this song is built on. The audio
        # renders these lanes as pitches, so the chart follows the melody.
        "hooks": [[0, 3, 1, 3], [2, 3, 0, 2]],
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
        # the hook: the four-lane figure this song is built on. The audio
        # renders these lanes as pitches, so the chart follows the melody.
        "hooks": [[0, 2, 3, 1], [3, 1, 0, 2]],
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
        # the hook: the four-lane figure this song is built on. The audio
        # renders these lanes as pitches, so the chart follows the melody.
        "hooks": [[0, 1, 3, 2], [2, 0, 1, 3]],
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


#: Arrow shapes per phrase block -- keeps the riff moving instead of looping one
#: 16-note cell for two minutes.
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


def side_for_block(index):
    """Base-game phrasing: the opponent opens, then the two characters trade
    phrase blocks for the rest of the song (and the player always gets the last
    word)."""
    return "opponent" if index % 2 == 0 else "player"


def sections(song):
    _prepare(song)
    out = []
    cells = song["cells"]
    roles = section_roles(song)
    call, answer = song["hooks"][0], song["hooks"][1]
    for i, (bars, start) in enumerate(zip(song["section_measures"], song["_block_starts"])):
        # A breakdown is sparse in the chart exactly where the drums drop out.
        cell = CELLS[HALF if roles[i] == "break" else cells[i % len(cells)]]
        side = side_for_block(i)
        hook = call if side == "opponent" else answer
        # Every fourth exchange the answer comes back inverted: call/response,
        # not a loop. The chords move underneath, so the melody never repeats
        # at the same pitch twice.
        if side == "player" and (i // 2) % 4 == 3:
            hook = [3 - note for note in hook]
        count = bars * len(cell)
        notes = []
        for bar in range(bars):
            for k, offset in enumerate(cell):
                index = bar * len(cell) + k
                nid = hook[index % len(hook)]
                if index == count - 1:
                    nid = 0              # every phrase lands on the root
                notes.append(
                    {
                        "id": nid,
                        "side": side,
                        "time": measure_time(song, start + bar) + offset * step(song) * 1000.0,
                        "measure": start + bar,
                        "offset": offset,
                    }
                )
        out.append(
            {
                "index": i,
                "name": song["section_names"][i % len(song["section_names"])],
                "time": measure_time(song, start),
                "measures": bars,
                "role": roles[i],
                "side": side,
                "mustHitSection": side == "player",
                "notes": notes,
            }
        )
    return out


#: Difficulties, easiest first -- the same three the base game ships.
DIFFICULTIES = ("easy", "normal", "hard")

#: How many notes of a phrase block each difficulty keeps (0 = everything).
#: Base-game charts sit at roughly 1 : 2 : 3 notes for easy : normal : hard.
DIFFICULTY_STRIDE = {"easy": 2, "normal": 3, "hard": 1}

#: Scroll speed per difficulty, inside the base game's 1.2-2.6 range.
DIFFICULTY_SCROLL = {"easy": -0.35, "normal": -0.15, "hard": 0.0}

#: Sections that end on a held note (sustains make the chart breathe).
SUSTAIN_EVERY = 3
SUSTAIN_MS_FACTOR = 2.0


def _keep(index, stride):
    """True when note `index` of a phrase survives that difficulty's filter."""
    if stride <= 1:
        return True
    if stride == 2:
        return index % 2 == 0
    return index % 3 != 2


def notes(song, difficulty="hard"):
    """Every note of `difficulty`, in time order.

    The audio renderer asks for "hard": the instrumental and the vocal track are
    the full melody, and the easier charts are a subset of the same notes.
    """
    if difficulty not in DIFFICULTY_STRIDE:
        raise ValueError("unknown difficulty %r" % (difficulty,))
    stride = DIFFICULTY_STRIDE[difficulty]

    secs = sections(song)
    all_notes = []
    for section in secs:
        kept = [n for i, n in enumerate(section["notes"]) if _keep(i, stride)]
        if not kept:
            kept = [section["notes"][0]]
        # A phrase always lands its last note: that is where the sustain lives.
        if kept[-1] is not section["notes"][-1]:
            kept.append(section["notes"][-1])
        section["kept"] = kept
        all_notes.extend(kept)

    all_notes.sort(key=lambda n: (n["time"], n["side"], n["id"]))

    if stride == 1:
        for i, section in enumerate(secs):
            if i % SUSTAIN_EVERY != SUSTAIN_EVERY - 1:
                continue
            last = section["kept"][-1]
            last["sLen"] = beat(song) * 1000.0 * SUSTAIN_MS_FACTOR

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
