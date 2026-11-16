"""
The melody of Super Scary Trollge -- hand-written phrases, one library per song.

This module holds *music*, not code: `tools/song_layout.py` parses it, lays the
phrases out over the song's phrase blocks and derives both the chart and the
audio from the result. Nothing here is generated, so editing it is how the songs
are written.

Notation
--------

One line is one bar of sixteen 16th-note steps. Tokens are separated by spaces
(``|`` is ignored, so bars can be written out in groups):

    ``12``   a note on the chord's tonic, one octave up (degrees are semitones
             measured from the song's tonic, in the song's scale)
    ``.``    a rest -- the groove breathes here
    ``-``    hold the previous note for another 16th (a tied sustain)

Every phrase must be an exact whole number of bars; the parser rejects anything
else, and `tools/validate_mod.py` re-checks the shipped charts for it.

Why phrases and not loops
-------------------------

The previous version of this mod had two four-note hooks per song and tiled them
for two minutes, which is why it sounded like a scale exercise. Each song now
has a proper phrase set:

===============  =====  ====================================================
phrase           bars   role
===============  =====  ====================================================
``intro``           2    the riff alone, sparse -- sets the key
``verse_a``         4    antecedent of the first 8-bar period (half cadence)
``verse_b``         4    consequent of that period (resolves)
``verse_c``         4    the B section: new register, same key
``verse_d``         4    consequent of the B section
``chorus_a``        4    the hook -- the phrase you should be able to hum
``chorus_b``        4    its answer, cadencing on the tonic
``build``           2    eight rising notes; the ramp into a drop
``break``           2    two long notes and a lot of air
``finale``          4    the last act: same material, highest register
===============  =====  ====================================================

Opponent blocks sing the *antecedent* phrases, player blocks sing the
*consequent* ones, so call-and-response is built into the material rather than
being one loop transposed. Inversion every fourth exchange (a rule the chart has
always followed) is applied on top by `tools/song_layout.py`.
"""

#: Scale degrees (semitones from the tonic) each song is written in. The ladder
#: darkens as the scare tier rises: aeolian -> aeolian with a flattened fifth ->
#: phrygian (b2, the "wrong note") -> harmonic minor (leading tone, no resolution).
SCALES = {
    "trolling":        [0, 2, 3, 5, 7, 8, 10],   # natural minor
    "getting-dark":    [0, 2, 3, 5, 7, 8, 10],   # natural minor
    "dont-look-back":  [0, 2, 3, 5, 6, 8, 10],   # minor with a flattened fifth
    "super-scary":     [0, 1, 3, 5, 7, 8, 10],   # phrygian
    "the-incident":    [0, 2, 3, 5, 7, 8, 11],   # harmonic minor
}


PHRASES = {}

PHRASES['trolling'] = {
    "intro": """
        12 . . . . . . . 15 . . . . . . .
        . . . . 17 . . . . . 15 . . . . .
    """,

    "verse_a": """
        12 . . . 15 . . . 17 . . . 15 . . .
        . . 14 . . . . . 12 . . . 12 . . .
        12 . . . 15 . . . 17 . . . 19 . . .
        . . 17 . . . . . 15 . . . 14 . . .
    """,

    "verse_b": """
        15 . . . 17 . . . 19 . . . 17 . . .
        . . 15 . . . . . 14 . . . 12 . . .
        15 . . . 17 . . . 19 . . . 17 . . .
        . . 15 . . . . . 17 . . . 19 . . .
    """,

    "verse_c": """
        17 . . . 20 . . . 19 . . . 17 . . .
        . . 15 . . . . . 17 . . . 15 . . .
        17 . . . 20 . . . 19 . . . 17 . . .
        . . 20 . . . . . 19 . . . 17 . . .
    """,

    "verse_d": """
        20 . . . 19 . . . 17 . . . 15 . . .
        . . 14 . . . . . 12 . . . 14 . . .
        20 . . . 19 . . . 17 . . . 15 . . .
        . . 14 . . . . . 12 - - - - - . .
    """,

    "chorus_a": """
        12 . . 12 . . . . 15 . . 12 . . . .
        . . 17 . . . . . 15 . . . 12 . . .
        12 . . 12 . . . . 15 . . 12 . . . .
        . . 19 . . . . . 17 . . . 15 . . .
    """,

    "chorus_b": """
        12 . . 12 . . . . 15 . . 12 . . . .
        . . 19 . . . . . 17 . . . 15 . . .
        17 . . . . . . . 15 . . . 12 . . .
        . . 14 . . . . . 12 - - - - - . .
    """,

    "build": """
        12 . 12 . 15 . 15 . 17 . 17 . 19 . . .
        . 19 . 20 . 19 . 17 . 15 . 12 . . . .
    """,

    "break": """
        12 - - - - - - - . . . . . . . .
        . . . . . . . . 7 - - - - - - -
    """,

    "finale": """
        24 . . . 22 . . . 20 . . . 19 . . .
        . . 17 . . . . . 15 . . . 17 . . .
        24 . . . 22 . . . 20 . . . 19 . . .
        . . 17 . . . . . 15 - - - - - . .
    """,

}

PHRASES['getting-dark'] = {
    "intro": """
        12 . . . . . . . . . . . 15 . . .
        . . . . . . . . 14 . . . . . . .
    """,

    "verse_a": """
        12 . . . . . . . . 15 . . . 17 . .
        . . . . 15 . . . . . 14 . . . 12 .
        12 . . . . . . . . 15 . . . 17 . .
        . . . . 15 . . . . . 14 . . . 12 .
    """,

    "verse_b": """
        17 . . . . . . . . 15 . . . 12 . .
        . . . . 14 . . . . . . . 12 . . .
        17 . . . . . . . . 15 . . . 12 . .
        . . . . 14 . . . . . . . 12 . . .
    """,

    "verse_c": """
        19 . . . . . . . . 20 . . . 19 . .
        . . . . 17 . . . . . 15 . . . 17 .
        19 . . . . . . . . 20 . . . 19 . .
        . . . . 17 . . . . . 15 . . . 17 .
    """,

    "verse_d": """
        22 . . . . . . . . 20 . . . 19 . .
        . . . . 17 . . . . . 19 . . . 17 .
        22 . . . . . . . . 20 . . . 19 . .
        . . . . 17 . . . . . 19 . . . 17 .
    """,

    "chorus_a": """
        12 . . . . 12 . . . . 15 . . . 12 .
        . . 17 . . . . . . 15 . . . 12 . .
        12 . . . . 12 . . . . 15 . . . 12 .
        . . 19 . . . . . . 17 . . . 15 . .
    """,

    "chorus_b": """
        12 . . . . 12 . . . . 15 . . . 12 .
        . . 19 . . . . . . 17 . . . 15 . .
        17 . . . . . . . . 15 . . . 12 . .
        . . . . 14 . . . . . 12 - - - - -
    """,

    "build": """
        12 . . 12 . . 15 . . 12 . . 15 . 17 .
        . 12 . . 15 . . 12 . . 17 . . 19 . 20
    """,

    "break": """
        12 - - - - - - - . . . . . . . .
        . . . . . . . . 7 - - - - - - -
    """,

    "finale": """
        24 . . . . . . . . 22 . . . 20 . .
        . . . . 19 . . . . . 20 . . . 22 .
        24 . . . . . . . . 20 . . . 19 . .
        . . . . 17 . . . . . 12 - - - - -
    """,

}

PHRASES['dont-look-back'] = {
    "intro": """
        12 . . . . . . . 18 . . . 15 . . .
        . . . . . . . . 17 . . . . . . .
    """,

    "verse_a": """
        12 . . . . . . . 18 . . . 17 . . .
        . . 15 . . . . . 17 . . . 15 . . .
        12 . . . . . . . 18 . . . 18 . . .
        . . 17 . . . . . 15 . . . 12 . . .
    """,

    "verse_b": """
        20 . . . . . . . 18 . . . 12 . . .
        . . 15 . . . . . 17 . . . 15 . . .
        20 . . . . . . . 18 . . . 17 . . .
        . . 15 . . . . . 14 . . . 12 . . .
    """,

    "verse_c": """
        22 . . . . . . . 24 . . . 22 . . .
        . . 20 . . . . . 18 . . . 17 . . .
        22 . . . . . . . 24 . . . 22 . . .
        . . 22 . . . . . 20 . . . 18 . . .
    """,

    "verse_d": """
        24 . . . . . . . 22 . . . 20 . . .
        . . 18 . . . . . 17 . . . 18 . . .
        24 . . . . . . . 22 . . . 20 . . .
        . . 18 . . . . . 17 . . . 14 . . .
    """,

    "chorus_a": """
        12 . . 12 . . . . 15 . . 12 . . . .
        . . 18 . . . . . 15 . . . 12 . . .
        12 . . 12 . . . . 15 . . 12 . . . .
        . . 22 . . . . . 18 . . . 17 . . .
    """,

    "chorus_b": """
        12 . . 12 . . . . 15 . . 12 . . . .
        . . 22 . . . . . 18 . . . 17 . . .
        18 . . . . . . . 17 . . . 12 . . .
        . . 15 . . . . . 12 - - - - - . .
    """,

    "build": """
        12 . 12 . 12 . 15 . 12 . 12 . 15 . 18 .
        . 12 . 12 . 15 . 12 . 18 . 22 . 24 . .
    """,

    "break": """
        12 - - - - - - - . . . . . . . .
        . . . . . . . . 6 - - - - - - -
    """,

    "finale": """
        24 . . . . . . . 24 . . . 22 . . .
        . . 20 . . . . . 18 . . . 20 . . .
        24 . . . . . . . 24 . . . 22 . . .
        . . 18 . . . . . 17 . . . 12 . . .
    """,

}

PHRASES['super-scary'] = {
    "intro": """
        12 . . . 13 . . . 12 . . . . . . .
        . . . . 10 . . . . . . . . . . .
    """,

    "verse_a": """
        12 . . . 13 . . . 12 . . . 15 . . .
        . . 13 . . . . . 12 . . . 10 . . .
        12 . . . 13 . . . 12 . . . 15 . . .
        . . 15 . . . . . 13 . . . 12 . . .
    """,

    "verse_b": """
        15 . . . 13 . . . 12 . . . 15 . . .
        . . 13 . . . . . 12 . . . 10 . . .
        13 . . . 17 . . . 19 . . . 18 . . .
        . . 15 . . . . . 13 . . . 12 . . .
    """,

    "verse_c": """
        19 . . . 20 . . . 19 . . . 15 . . .
        . . 18 . . . . . 17 . . . 15 . . .
        19 . . . 20 . . . 19 . . . 17 . . .
        . . 15 . . . . . 13 . . . 12 . . .
    """,

    "verse_d": """
        20 . . . 19 . . . 18 . . . 15 . . .
        . . 13 . . . . . 12 . . . 13 . . .
        20 . . . 19 . . . 18 . . . 15 . . .
        . . 13 . . . . . 12 . . . 12 . . .
    """,

    "chorus_a": """
        12 . . 12 13 . . . 12 . . 12 . . . .
        . . 15 . . . . . 19 . . . 18 . . .
        12 . . 12 13 . . . 12 . . 12 . . . .
        . . 19 . . . . . 17 . . . 15 . . .
    """,

    "chorus_b": """
        12 . . 12 13 . . . 12 . . 12 . . . .
        . . 17 . . . . . 18 . . . 15 . . .
        17 . . . . . . . 15 . . . 13 . . .
        . . 12 . . . . . 10 - - - - - . .
    """,

    "build": """
        12 . 12 . 13 . 12 . 12 . 13 . 15 . 13 .
        . 12 . 12 . 15 . 17 . 15 . 13 . 12 . .
    """,

    "break": """
        12 - - - - - - - . . . . . . . .
        . . . . . . . . 10 - - - - - - -
    """,

    "finale": """
        24 . . . 25 . . . 24 . . . 22 . . .
        . . 19 . . . . . 18 . . . 19 . . .
        24 . . . 22 . . . 24 . . . 22 . . .
        . . 19 . . . . . 17 . . . 15 . . .
    """,

}

PHRASES['the-incident'] = {
    "intro": """
        12 . . . 11 . . . 12 . . . . . . .
        . . . . 8 . . . . . . . . . . .
    """,

    "verse_a": """
        12 . . . 11 . . . 12 . . . 15 . . .
        . . 14 . . . . . 12 . . . 11 . . .
        12 . . . 11 . . . 12 . . . 15 . . .
        . . 14 . . . . . 11 . . . 12 . . .
    """,

    "verse_b": """
        15 . . . 14 . . . 12 . . . 11 . . .
        . . 12 . . . . . 14 . . . 12 . . .
        19 . . . 18 . . . 19 . . . 17 . . .
        . . 15 . . . . . 17 . . . 19 . . .
    """,

    "verse_c": """
        19 . . . 20 . . . 19 . . . 17 . . .
        . . 15 . . . . . 17 . . . 19 . . .
        19 . . . 20 . . . 19 . . . 17 . . .
        . . 15 . . . . . 17 . . . 19 . . .
    """,

    "verse_d": """
        20 . . . 19 . . . 17 . . . 15 . . .
        . . 14 . . . . . 15 . . . 17 . . .
        20 . . . 19 . . . 17 . . . 15 . . .
        . . 14 . . . . . 11 . . . 12 . . .
    """,

    "chorus_a": """
        12 . . 12 11 . . . 12 . . 12 . . . .
        . . 15 . . . . . 19 . . . 17 . . .
        12 . . 12 11 . . . 12 . . 12 . . . .
        . . 17 . . . . . 19 . . . 17 . . .
    """,

    "chorus_b": """
        12 . . 12 11 . . . 12 . . 12 . . . .
        . . 20 . . . . . 19 . . . 17 . . .
        19 . . . . . . . 17 . . . 15 . . .
        . . 14 . . . . . 11 . . . 12 . . .
    """,

    "build": """
        12 . 12 . 11 . 12 . 12 . 11 . 12 . 14 .
        . 15 . . 17 . . 19 . . 20 . . 19 . .
    """,

    "break": """
        12 - - - - - - - . . . . . . . .
        . . . . . . . . 8 - - - - - - -
    """,

    "finale": """
        24 . . . 23 . . . 24 . . . 20 . . .
        . . 19 . . . . . 20 . . . 20 . . .
        24 . . . 23 . . . 20 . . . 19 . . .
        . . 17 . . . . . 15 . . . 12 . . .
    """,

}
