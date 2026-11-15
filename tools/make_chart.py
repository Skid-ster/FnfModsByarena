#!/usr/bin/env python3
"""
Builds every chart / metadata file for the five Super Scary Trollge songs.

Layout (Codename Engine 1.x, matching how the base game ships a song):

    mods/TrollgeMod/songs/<id>/song/Inst.ogg     instrumental
    mods/TrollgeMod/songs/<id>/song/Voices.ogg   the characters' vocals
    mods/TrollgeMod/songs/<id>/meta.json         display name, BPM, icon, difficulties
    mods/TrollgeMod/songs/<id>/events.json       scripted story beats
    mods/TrollgeMod/songs/<id>/charts/easy.json
    mods/TrollgeMod/songs/<id>/charts/normal.json
    mods/TrollgeMod/songs/<id>/charts/hard.json

Every file is generated from tools/song_layout.py, so the audio that was
rendered and the chart that is played are the same note list.

Run with:  python3 tools/make_chart.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONGS_DIR = os.path.join(ROOT, "mods", "TrollgeMod", "songs")

STAGE = "trollge"
CHART_VERSION = "1.6.0"

#: Icon + health-bar colour per song (gets redder as it gets scarier).
#: The icon must be a folder that exists under images/icons/ -- HealthIcon falls
#: back to the base game's "face" when it is not, which hides a missing phase.
STYLES = {
    "trolling": {"icon": "trollge", "color": "#3F7BD1"},
    "getting-dark": {"icon": "trollge_glitch", "color": "#8A1023"},
    "dont-look-back": {"icon": "trollge_static", "color": "#A8142B"},
    "super-scary": {"icon": "trollge_final", "color": "#C4101E"},
    "the-incident": {"icon": "trollge_sad", "color": "#5C0610"},
}

BOOKMARK_COLORS = ["#6E0D1B", "#8A1023", "#A8142B", "#C4101E"]


def json_dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent="\t", ensure_ascii=False)
        f.write("\n")
    return path


def note_obj(note):
    return {
        "time": round(note["time"], 3),
        "id": int(note["id"]),
        "type": 0,
        "sLen": round(float(note.get("sLen", 0.0)), 3),
    }


def build_chart(song, difficulty):
    """One difficulty chart.

    Chart conventions taken from the base game:
      * a section is one bar (16 steps) and belongs to exactly one side, which
        the bookmark + `mustHitSection` field records for the editor,
      * the opponent's strum line holds the opponent's sections and the player's
        holds the player's, so the two characters alternate phrase blocks,
      * scroll speed rises with the difficulty instead of being flat.
    """
    notes = L.notes(song, difficulty)
    sections = L.sections(song)
    bookmarks = [
        {
            "time": round(sec["time"], 3),
            "name": "%02d - %s%s" % (i + 1, sec["name"],
                                     "" if sec["side"] == "player" else " (dad)"),
            "color": BOOKMARK_COLORS[i % len(BOOKMARK_COLORS)],
        }
        for i, sec in enumerate(sections)
    ]

    opponent = [n for n in notes if n["side"] == "opponent"]
    player = [n for n in notes if n["side"] == "player"]

    return {
        "stage": STAGE,
        "scrollSpeed": L.scroll_speed(song, difficulty),
        "chartVersion": CHART_VERSION,
        "codenameChart": True,
        "noteTypes": L.note_types(song),
        "bookmarks": bookmarks,
        # No `sections` array: Codename charts are strum-line native and the
        # editor derives 16-step sections (and mustHitSection) from which strum
        # line a note sits in -- exactly what the two lists below encode.
        "events": L.camera_events(song),
        "strumLines": [
            {
                "position": "dad",
                "type": 0,
                "characters": [L.characters(song, "opponent")],
                "keyCount": 4,
                "visible": True,
                "strumScale": 1.0,
                "scrollSpeed": L.scroll_speed(song, difficulty),
                "notes": [note_obj(n) for n in opponent],
            },
            {
                "position": "boyfriend",
                "type": 1,
                "characters": [L.characters(song, "player")],
                "keyCount": 4,
                "visible": True,
                "strumScale": 1.0,
                "scrollSpeed": L.scroll_speed(song, difficulty),
                "notes": [note_obj(n) for n in player],
            },
        ],
    }


def count_notes(chart):
    return sum(len(s["notes"]) for s in chart["strumLines"])


def meta_json(song):
    style = STYLES[song["id"]]
    counts = {d: len(L.notes(song, d)) for d in L.DIFFICULTIES}
    return {
        "displayName": song["display"],
        "bpm": song["bpm"],
        "beatsPerMeasure": 4,
        "stepsPerBeat": 4,
        "icon": style["icon"],
        "color": style["color"],
        "coopAllowed": False,
        "opponentModeAllowed": True,
        "needsVoices": True,
        "difficulties": list(L.DIFFICULTIES),
        "customValues": {
            "scareTier": song["scare"],
            "songKey": L.key_name(song),
            "lengthSeconds": round(L.length(song), 3),
            "noteCounts": counts,
        },
    }


def main():
    total_notes = 0
    for song in L.SONGS:
        base = os.path.join(SONGS_DIR, song["id"])
        json_dump(os.path.join(base, "meta.json"), meta_json(song))
        json_dump(os.path.join(base, "events.json"), {"events": L.story_events(song)})

        for difficulty in L.DIFFICULTIES:
            chart = build_chart(song, difficulty)
            json_dump(os.path.join(base, "charts", "%s.json" % difficulty), chart)
            if difficulty == "hard":
                total_notes += count_notes(chart)
            print("  %-14s %-6s %4d notes  scroll %.2f  %6.2fs"
                  % (song["id"], difficulty, count_notes(chart),
                     L.scroll_speed(song, difficulty), L.length(song)))

        print("    meta: %s, scare %d/10, %d bars in %d phrase blocks, %d story beats"
              % (L.key_name(song), song["scare"], L.measures(song),
                 len(L.sections(song)), len(song["events"])))

    print("  total hard-mode notes: %d" % total_notes)


if __name__ == "__main__":
    main()
