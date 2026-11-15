#!/usr/bin/env python3
"""
Validates the Super Scary Trollge mod before it ships.

Checks (no engine required -- this is what CI runs):

  * every JSON file parses and charts match Codename Engine's 1.6.0 schema
  * every XML file is well formed
  * Sparrow atlases: every SubTexture lives inside the PNG
  * character XMLs only reference animation frames that exist in the atlas
  * charts: note times sorted / inside the song, strum lines sane
  * events: every HScript function called from a chart exists in the scripts
  * audio: every Inst.ogg matches its meta.json BPM/length expectations
  * required files from the mod spec are present

Usage:  python3 tools/validate_mod.py [--quiet]
Exit code 1 on any error.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import song_layout as L  # noqa: E402

ERRORS = []
WARNINGS = []
CHECKS = 0


def ok(condition, message, soft=False):
    global CHECKS
    CHECKS += 1
    if not condition:
        (WARNINGS if soft else ERRORS).append(message)
    return condition


def rel(path):
    return os.path.relpath(path, MOD)


def walk(*exts):
    for base, _dirs, files in os.walk(MOD):
        for f in files:
            if f.lower().endswith(exts):
                yield os.path.join(base, f)


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #

REQUIRED_FILES = [
    "mod.json",
    "data/config/modpack.ini",
    "data/characters/trollge.xml",
    "data/characters/trollge_scary.xml",
    "data/scripts/trollge_behavior.hx",
    "data/scripts/trollge_song_behavior.hx",
    "data/stages/trollge.xml",
    "data/stages/trollge.hx",
    "data/weeks/weeks/trollge_week.xml",
    "data/weeks/characters/trollge.xml",
    "images/characters/Trollge.png",
    "images/characters/Trollge.xml",
    "images/characters/TrollgeScary.png",
    "images/characters/TrollgeScary.xml",
    "images/icons/trollge/icon.png",
    "images/icons/trollge_scary/icon.png",
    "images/stages/trollge/bg.png",
    "images/stages/trollge/bg_scary.png",
    "images/stages/trollge/bg_nightmare.png",
    "images/menus/storymenu/weeks/trollge_week.png",
    "images/menus/storymenu/characters/trollge.png",
    "images/trollge_idle.png",
    "images/trollge_sing.png",
    "images/trollge_scary_bg.png",
    "images/trollge_jump_scare.png",
    "images/trollge_distortion.png",
    "images/trollge_invert.png",
    "sounds/trollge_theme.ogg",
    "sounds/trollge_theme_scary.ogg",
    "sounds/trollge_jump_scare.ogg",
    "sounds/trollge_distortion.ogg",
    "sounds/trollge_invert.ogg",
    "sounds/trollge_hit.ogg",
    "sounds/trollge_miss.ogg",
]


def check_required():
    for f in REQUIRED_FILES:
        path = os.path.join(MOD, f)
        ok(os.path.isfile(path) and os.path.getsize(path) > 0, "missing or empty file: %s" % f)


def check_json():
    global CHECKS
    for path in walk(".json"):
        try:
            with open(path, encoding="utf-8") as fh:
                json.load(fh)
        except Exception as exc:  # noqa: BLE001
            ERRORS.append("invalid JSON %s: %s" % (rel(path), exc))
            continue
        CHECKS += 1


def check_xml():
    global CHECKS
    for path in walk(".xml"):
        try:
            ET.parse(path)
            CHECKS += 1
        except Exception as exc:  # noqa: BLE001
            ERRORS.append("invalid XML %s: %s" % (rel(path), exc))


def check_mod_json():
    data = json.load(open(os.path.join(MOD, "mod.json"), encoding="utf-8"))
    ok(data.get("version") == "2.0.0", "mod.json version should be 2.0.0")
    ids = [s["id"] for s in L.SONGS]
    ok(sorted(data.get("songs", [])) == sorted(ids), "mod.json songs must match the built songs")
    ok(data.get("week") == "trollge_week", "mod.json week must be trollge_week")


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #

STRUM_POSITIONS = {"dad", "boyfriend", "girlfriend"}


def check_charts():
    for song in L.SONGS:
        base = os.path.join(MOD, "songs", song["id"])
        meta_path = os.path.join(base, "meta.json")
        if not os.path.isfile(meta_path):
            ERRORS.append("missing meta.json for %s" % song["id"])
            continue
        meta = json.load(open(meta_path, encoding="utf-8"))

        ok(meta["bpm"] == song["bpm"], "%s meta bpm mismatch" % song["id"])
        ok(sorted(meta["difficulties"]) == ["easy", "normal"],
           "%s must ship easy + normal difficulties" % song["id"])
        ok(meta.get("customValues", {}).get("scareTier") == song["scare"],
           "%s scareTier mismatch" % song["id"])
        ok(os.path.isfile(os.path.join(base, "song", "Inst.ogg")),
           "%s is missing song/Inst.ogg" % song["id"])

        expected_length = L.length(song) * 1000.0

        for difficulty in meta["difficulties"]:
            chart_path = os.path.join(base, "charts", "%s.json" % difficulty)
            if not ok(os.path.isfile(chart_path), "%s/%s chart missing" % (song["id"], difficulty)):
                continue
            chart = json.load(open(chart_path, encoding="utf-8"))

            ok(chart.get("codenameChart") is True, "%s/%s: codenameChart must be true" % (song["id"], difficulty))
            ok(chart.get("chartVersion") == "1.6.0", "%s/%s: chartVersion must be 1.6.0" % (song["id"], difficulty))
            ok(chart.get("stage") == "trollge", "%s/%s: stage must be trollge" % (song["id"], difficulty))
            ok(1 <= float(chart.get("scrollSpeed", 0)) <= 3, "%s/%s: odd scrollSpeed" % (song["id"], difficulty))

            lines = chart.get("strumLines", [])
            ok(len(lines) == 2, "%s/%s: expected 2 strum lines" % (song["id"], difficulty))

            total = 0
            for idx, line in enumerate(lines):
                ok(line.get("position") in STRUM_POSITIONS,
                   "%s/%s: unknown strum position %r" % (song["id"], difficulty, line.get("position")))
                ok(line.get("keyCount") == 4, "%s/%s: keyCount must be 4" % (song["id"], difficulty))
                ok(isinstance(line.get("characters"), list) and line["characters"],
                   "%s/%s: strum line %d has no characters" % (song["id"], difficulty, idx))

                notes = line.get("notes", [])
                total += len(notes)
                times = [n["time"] for n in notes]
                ok(times == sorted(times), "%s/%s: notes not sorted" % (song["id"], difficulty))
                ok(all(0 <= t <= expected_length for t in times),
                   "%s/%s: note outside of the song" % (song["id"], difficulty))
                ok(all(0 <= n["id"] <= 3 for n in notes),
                   "%s/%s: bad note id" % (song["id"], difficulty))
                ok(all(n["sLen"] >= 0 for n in notes),
                   "%s/%s: negative sustain" % (song["id"], difficulty))

            ok(total > 0, "%s/%s: chart has no notes" % (song["id"], difficulty))
            if difficulty == "normal":
                ok(total == len(L.notes(song)),
                   "%s/normal: expected %d notes, found %d" % (song["id"], len(L.notes(song)), total))

            bookmarks = chart.get("bookmarks", [])
            ok(len(bookmarks) == len(L.sections(song)),
               "%s/%s: expected %d section bookmarks" % (song["id"], difficulty, len(L.sections(song))))
            ok(all("name" in b and "color" in b for b in bookmarks),
               "%s/%s: bookmark missing name/color" % (song["id"], difficulty))

        events = json.load(open(os.path.join(base, "events.json"), encoding="utf-8"))["events"]
        expected = [e for e in events if e["name"] == "HScript Call"]
        ok(len(expected) == len(song["events"]),
           "%s: expected %d scripted story events" % (song["id"], len(song["events"])))
        ok(all(0 <= e["time"] <= expected_length for e in events),
           "%s: event outside of the song" % song["id"])


# --------------------------------------------------------------------------- #
# Art
# --------------------------------------------------------------------------- #

def check_atlases():
    try:
        from PIL import Image
    except ImportError:
        WARNINGS.append("Pillow not installed, skipped pixel-level atlas checks")
        return

    for name in ("Trollge", "TrollgeScary"):
        png = os.path.join(MOD, "images", "characters", name + ".png")
        xml = os.path.join(MOD, "images", "characters", name + ".xml")
        if not (os.path.isfile(png) and os.path.isfile(xml)):
            ERRORS.append("missing atlas %s" % name)
            continue
        image = Image.open(png)
        root = ET.parse(xml).getroot()
        frames = [el for el in root if el.tag == "SubTexture"]
        ok(len(frames) > 0, "%s atlas has no frames" % name)
        for el in frames:
            x, y = int(el.get("x")), int(el.get("y"))
            w, h = int(el.get("width")), int(el.get("height"))
            ok(x >= 0 and y >= 0 and x + w <= image.width and y + h <= image.height,
               "%s: frame %s outside of the sheet" % (name, el.get("name")))
        names = {el.get("name") for el in frames}
        ok(len(names) == len(frames), "%s: duplicate frame names" % name)

        # Character XML -> every <anim anim="..."> prefix must exist.
        for char in (name.lower(), name.lower().replace("trollge", "trollge")):
            char_xml = os.path.join(MOD, "data", "characters", char + ".xml")
            if not os.path.isfile(char_xml):
                continue
            for anim in ET.parse(char_xml).getroot().iter("anim"):
                prefix = anim.get("anim")
                ok(any(n.startswith(prefix) for n in names),
                   "%s: anim %r references missing frames %r" % (rel(char_xml), anim.get("name"), prefix))

        # Prefix collision check (Flixel resolves animations with addByPrefix).
        prefixes = sorted({re.sub(r"\d+$", "", n) for n in names})
        for a in prefixes:
            for b in prefixes:
                if a != b and b.startswith(a):
                    ERRORS.append("%s: animation prefix %r shadows %r" % (name, a, b))


def check_icons():
    try:
        from PIL import Image
    except ImportError:
        return
    for icon in ("trollge", "trollge_scary"):
        path = os.path.join(MOD, "images", "icons", icon, "icon.png")
        if not os.path.isfile(path):
            continue
        size = Image.open(path).size
        ok(size[0] % size[1] == 0 and size[1] > 0,
           "%s icon must be a horizontal strip of square frames (got %s)" % (icon, size))
        ok(size[0] // size[1] == 2, "%s icon should hold 2 frames (got %s)" % (icon, size))


# --------------------------------------------------------------------------- #
# Scripts
# --------------------------------------------------------------------------- #

def check_scripts():
    song_script = os.path.join(MOD, "data", "scripts", "trollge_song_behavior.hx")
    if not os.path.isfile(song_script):
        return
    src = open(song_script, encoding="utf-8").read()
    defined = {line.split("(")[0].replace("function", "").strip()
               for line in src.splitlines() if line.strip().startswith("function ")}

    called = set()
    for song in L.SONGS:
        events = json.load(open(os.path.join(MOD, "songs", song["id"], "events.json"), encoding="utf-8"))
        for event in events["events"]:
            if event["name"] == "HScript Call":
                called.add(event["params"][0])
    for func in sorted(called):
        ok(func in defined, "chart calls %r but no script defines it" % func)

    # Every song folder must load the shared behaviour.
    for song in L.SONGS:
        loader = os.path.join(MOD, "songs", song["id"], "scripts", "song_behavior.hx")
        ok(os.path.isfile(loader), "%s is missing scripts/song_behavior.hx" % song["id"])
        if os.path.isfile(loader):
            ok("importScript" in open(loader, encoding="utf-8").read(),
               "%s song script does not import the shared behaviour" % song["id"])

    # Character XML extensions must point at a real script.
    for char in ("trollge", "trollge_scary"):
        path = os.path.join(MOD, "data", "characters", char + ".xml")
        if not os.path.isfile(path):
            continue
        for ext in ET.parse(path).getroot().iter("extension"):
            target = os.path.join(MOD, "data", "scripts", ext.get("script") + ".hx")
            ok(os.path.isfile(target), "%s: extension script %r missing" % (char, ext.get("script")))


def check_audio():
    try:
        import soundfile as sf
    except ImportError:
        WARNINGS.append("soundfile not installed, skipped audio duration checks")
        return

    for song in L.SONGS:
        path = os.path.join(MOD, "songs", song["id"], "song", "Inst.ogg")
        if not os.path.isfile(path):
            continue
        info = sf.info(path)
        expected = L.length(song)
        ok(abs(info.duration - expected) < 0.15,
           "%s: Inst.ogg is %.2fs, chart expects %.2fs" % (song["id"], info.duration, expected))
        ok(info.samplerate >= 44100 // 2, "%s: unexpected sample rate" % song["id"])

    for sfx in ("trollge_jump_scare", "trollge_distortion", "trollge_invert",
                "trollge_hit", "trollge_miss", "trollge_theme", "trollge_theme_scary"):
        path = os.path.join(MOD, "sounds", sfx + ".ogg")
        if os.path.isfile(path):
            info = sf.info(path)
            ok(info.duration > 0.05, "%s.ogg is suspiciously short" % sfx)


def main():
    quiet = "--quiet" in sys.argv

    check_required()
    check_json()
    check_xml()
    check_mod_json()
    check_charts()
    check_atlases()
    check_icons()
    check_scripts()
    check_audio()

    for warning in WARNINGS:
        print("  WARN  %s" % warning)
    for error in ERRORS:
        print("  FAIL  %s" % error)

    if not quiet:
        print("\n%d checks, %d errors, %d warnings" % (CHECKS, len(ERRORS), len(WARNINGS)))

    if ERRORS:
        print("VALIDATION FAILED")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
