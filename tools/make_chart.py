#!/usr/bin/env python3
"""
Builds every chart / metadata file for the three Super Scary Trollge songs.

Per song (all in Codename Engine 1.x layout):

    mods/TrollgeMod/songs/<id>/meta.json      display name, BPM, icon, difficulties
    mods/TrollgeMod/songs/<id>/events.json    scripted story beats
    mods/TrollgeMod/songs/<id>/charts/normal.json
    mods/TrollgeMod/songs/<id>/charts/easy.json

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
SCROLL_SPEED = 1.0
CHART_VERSION = "1.6.0"

#: Icon + health-bar colour per song (gets redder as it gets scarier).
#: The icon must be a folder that exists under images/icons/ -- HealthIcon falls
#: back to the base game's "face" when it is not, which hides a missing phase.
STYLES = {
    "trolling": {"icon": "trollge", "color": "#3F7BD1"},
    "getting_dark": {"icon": "trollge_glitch", "color": "#8A1023"},
    "dont_look_back": {"icon": "trollge_static", "color": "#A8142B"},
    "super_scary": {"icon": "trollge_final", "color": "#C4101E"},
    "the_incident": {"icon": "trollge_sad", "color": "#5C0610"},
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


def make_easy(notes):
    """Half density, no sustains: keeps the rhythm but never overwhelms."""
    return [dict(n, sLen=0.0) for i, n in enumerate(notes) if i % 2 == 0]


def build_chart(song, notes, with_camera=True):
    bookmarks = [
        {
            "time": round(sec["time"], 3),
            "name": "%02d - %s" % (i + 1, sec["name"]),
            "color": BOOKMARK_COLORS[i % len(BOOKMARK_COLORS)],
        }
        for i, sec in enumerate(L.sections(song))
    ]

    opponent = [n for n in notes if n["side"] == "opponent"]
    player = [n for n in notes if n["side"] == "player"]

    return {
        "stage": STAGE,
        "scrollSpeed": SCROLL_SPEED,
        "chartVersion": CHART_VERSION,
        "codenameChart": True,
        "noteTypes": L.note_types(song),
        "bookmarks": bookmarks,
        "events": L.camera_events(song) if with_camera else [],
        "strumLines": [
            {
                "position": "dad",
                "type": 0,
                "characters": [L.characters(song, "opponent")],
                "keyCount": 4,
                "visible": True,
                "strumScale": 1.0,
                "notes": [note_obj(n) for n in opponent],
            },
            {
                "position": "boyfriend",
                "type": 1,
                "characters": [L.characters(song, "player")],
                "keyCount": 4,
                "visible": True,
                "strumScale": 1.0,
                "notes": [note_obj(n) for n in player],
            },
        ],
    }


def count_notes(chart):
    return sum(len(s["notes"]) for s in chart["strumLines"])


def meta_json(song):
    style = STYLES[song["id"]]
    return {
        "displayName": song["display"],
        "bpm": song["bpm"],
        "beatsPerMeasure": 4,
        "stepsPerBeat": 4,
        "icon": style["icon"],
        "color": style["color"],
        "coopAllowed": False,
        "opponentModeAllowed": True,
        "needsVoices": False,
        "difficulties": ["easy", "normal"],
        "customValues": {
            "scareTier": song["scare"],
            "lengthSeconds": round(L.length(song), 3),
        },
    }


def main():
    total_notes = 0
    for song in L.SONGS:
        base = os.path.join(SONGS_DIR, song["id"])
        notes = L.notes(song)
        json_dump(os.path.join(base, "meta.json"), meta_json(song))
        json_dump(os.path.join(base, "events.json"), {"events": L.story_events(song)})

        variants = {"normal": notes, "easy": make_easy(notes)}
        for name, variant in variants.items():
            chart = build_chart(song, variant)
            json_dump(os.path.join(base, "charts", "%s.json" % name), chart)
            if name == "normal":
                total_notes += count_notes(chart)
            print("  %-14s %-6s %4d notes  %6.2fs  %2d sections  cv:%.0f"
                  % (song["id"], name, count_notes(chart), L.length(song),
                     len(L.sections(song)), song["bpm"]))

        print("    meta: scare %d/10, %d scripted story beats"
              % (song["scare"], len(song["events"])))

    print("  total normal-mode notes: %d" % total_notes)


if __name__ == "__main__":
    main()
