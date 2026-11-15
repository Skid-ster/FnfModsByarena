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
    "data/characters/trollge_glitch.xml",
    "data/characters/trollge_static.xml",
    "data/characters/trollge_final.xml",
    "data/characters/trollge_sad.xml",
    "images/characters/Trollge_phase1.png",
    "images/characters/Trollge_phase1.xml",
    "images/characters/Trollge_phase2.png",
    "images/characters/Trollge_phase2.xml",
    "images/characters/Trollge_phase3.png",
    "images/characters/Trollge_phase3.xml",
    "images/characters/Trollge_final.png",
    "images/characters/Trollge_final.xml",
    "images/characters/Trollge_sad.png",
    "images/characters/Trollge_sad.xml",
    "images/icons/trollge_glitch/icon.png",
    "images/icons/trollge_static/icon.png",
    "images/icons/trollge_final/icon.png",
    "images/icons/trollge_sad/icon.png",
    "data/scripts/trollge_behavior.hx",
    "data/scripts/trollge_song_behavior.hx",
    "data/stages/trollge.xml",
    "data/stages/trollge.hx",
    "data/weeks/weeks/trollge_week.xml",
    "data/weeks/characters/trollge.xml",
    "images/icons/trollge/icon.png",
    "data/characters/bf_blue.xml",
    "data/characters/bf_blue_dead.xml",
    "data/characters/bf_smiler.xml",
    "data/characters/bf_smiler_dead.xml",
    "data/characters/bf_super_scary.xml",
    "data/characters/bf_super_scary_dead.xml",
    "images/characters/Boyfriend_blue.png",
    "images/characters/Boyfriend_blue.xml",
    "images/characters/Boyfriend_smiler.png",
    "images/characters/Boyfriend_smiler.xml",
    "images/characters/Boyfriend_super_scary.png",
    "images/characters/Boyfriend_super_scary.xml",
    "images/icons/bf_blue/icon.png",
    "images/icons/bf_smiler/icon.png",
    "images/icons/bf_super_scary/icon.png",
    "images/stages/trollge/bg.png",
    "images/stages/trollge/bg_scary.png",
    "images/stages/trollge/bg_nightmare.png",
    "images/menus/storymenu/weeks/trollge_week.png",
    "images/menus/storymenu/characters/trollge.png",
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
    "images/game/notes/default.png",
    "images/game/notes/default.xml",
    "images/game/notes/shadow.png",
    "images/game/notes/shadow.xml",
    "images/game/notes/corrupt.png",
    "images/game/notes/corrupt.xml",
    "images/game/splashes/default.png",
    "images/game/splashes/default.xml",
    "data/splashes/default.xml",
    "shaders/trollge_vhs.frag",
    "images/game/healthBar.png",
    "images/game/ready.png",
    "images/game/set.png",
    "images/game/go.png",
    "sounds/intro3.ogg",
    "sounds/intro2.ogg",
    "sounds/intro1.ogg",
    "sounds/introGo.ogg",
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
    ok(isinstance(data.get("version"), str) and data["version"].count(".") == 2,
       "mod.json needs a semantic version string")
    ids = [s["id"] for s in L.SONGS]
    ok(sorted(data.get("songs", [])) == sorted(ids), "mod.json songs must match the built songs")
    ok(data.get("week") == "trollge_week", "mod.json week must be trollge_week")


# --------------------------------------------------------------------------- #
# Note skin + splashes
# --------------------------------------------------------------------------- #

SKIN_SIZES = {
    "arrow": (160, 160),
    "press": (200, 200),
    "confirm": (200, 200),
    "note": (160, 160),
    "hold piece": (52, 88),
    "hold end": (52, 64),
}
SKIN_NAMES = ["purple", "blue", "green", "red"]
STRUM_DIRS = ["left", "down", "up", "right"]


def skin_required_frames():
    frames = {}
    for direction in STRUM_DIRS:
        frames["arrow%s0000" % direction.upper()] = "arrow"
        for name in ("press", "confirm"):
            for i in range(4):
                frames["%s %s%04d" % (direction, name, i)] = name
    for colour in SKIN_NAMES:
        frames["%s0000" % colour] = "note"
        frames["%s hold piece0000" % colour] = "hold piece"
        frames["%s hold end0000" % colour] = "hold end"
    frames["pruple end hold0000"] = "hold end"   # FNF typo, checked first by the engine
    return frames


def read_atlas(png, xml):
    """-> {frame name: (width, height)} without decoding the PNG."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(xml).getroot()
    except Exception as error:                                  # noqa: BLE001
        ERRORS.append("cannot parse %s: %s" % (rel(xml), error))
        return None
    frames = {}
    for node in root.iter():
        if node.tag.lower() != "subtexture":
            continue
        frames[node.get("name")] = (int(node.get("width")), int(node.get("height")))
    ok(os.path.isfile(png), "%s is missing" % rel(png))
    return frames


def check_noteskin():
    required = skin_required_frames()
    reference = None

    for skin in ("default", "shadow", "corrupt"):
        png = os.path.join(MOD, "images", "game", "notes", skin + ".png")
        xml = os.path.join(MOD, "images", "game", "notes", skin + ".xml")
        frames = read_atlas(png, xml)
        if frames is None:
            continue
        for name, group in required.items():
            if not ok(name in frames, "%s skin is missing frame %r" % (skin, name)):
                continue
            width, height = frames[name]
            limit_w, limit_h = SKIN_SIZES[group]
            ok(width <= limit_w and height <= limit_h and width > 0 and height > 0,
               "%s skin frame %r is %dx%d, larger than %dx%d"
               % (skin, name, width, height, limit_w, limit_h))
        if reference is None:
            reference = sorted(frames)
        else:
            ok(sorted(frames) == reference,
               "%s skin has a different frame set than default (layouts must match)" % skin)

    splash_png = os.path.join(MOD, "images", "game", "splashes", "default.png")
    splash_xml = os.path.join(MOD, "images", "game", "splashes", "default.xml")
    atlas = read_atlas(splash_png, splash_xml)
    config_path = os.path.join(MOD, "data", "splashes", "default.xml")
    if atlas and os.path.isfile(config_path):
        import xml.etree.ElementTree as ET
        root = ET.parse(config_path).getroot()
        ok(root.tag.lower() == "splashes", "data/splashes/default.xml must use <splashes>")
        ok(root.get("sprite") == "game/splashes/default",
           "splash config must point at game/splashes/default")
        strums = root.findall("strum")
        ok(len(strums) == 4, "splash config needs 4 strums, found %d" % len(strums))
        for strum in strums:
            sid = int(strum.get("id", -1))
            ok(0 <= sid <= 3, "splash config has a bad strum id %r" % strum.get("id"))
            anims = strum.findall("anim")
            ok(len(anims) == 2, "splash strum %d needs impact 1 + 2, found %d" % (sid, len(anims)))
            for anim in anims:
                target = anim.get("anim")
                matches = [n for n in atlas if n.startswith(target)]
                ok(len(matches) == 4, "splash anim %r has %d frames in the atlas (want 4)"
                   % (target, len(matches)))
                ok(int(anim.get("fps", 0)) > 0, "splash anim %r needs a positive fps" % target)
                ok(all(atlas[m][0] <= 260 and atlas[m][1] <= 298 for m in matches),
                   "splash anim %r has a frame larger than 260x298" % target)


# --------------------------------------------------------------------------- #
# Shaders
# --------------------------------------------------------------------------- #

def check_shaders():
    stage_script = os.path.join(MOD, "data", "stages", "trollge.hx")
    script = open(stage_script, encoding="utf-8").read() if os.path.isfile(stage_script) else ""

    for path in walk(".frag"):
        source = open(path, encoding="utf-8").read()
        ok("#pragma header" in source, "%s is missing #pragma header" % rel(path))
        ok("void main(" in source, "%s has no main()" % rel(path))
        ok("getCamPos" in source or "openfl_TextureCoordv" in source,
           "%s never touches the texture coordinates" % rel(path))
        # Codename's compat guide: reversed smoothstep edges and switch cases are
        # undefined on some drivers, so they must not creep in.
        ok("switch" not in source, "%s uses switch (unsupported on macOS)" % rel(path))
        for reverse in re.findall(r"smoothstep\(\s*([0-9.]+)\s*,\s*([0-9.]+)", source):
            ok(float(reverse[0]) < float(reverse[1]),
               "%s has a reversed smoothstep(%s, %s)" % (rel(path), reverse[0], reverse[1]))

    shader = os.path.join(MOD, "shaders", "trollge_vhs.frag")
    if os.path.isfile(shader) and script:
        source = open(shader, encoding="utf-8").read()
        uniforms = set(re.findall(r"uniform\s+float\s+(\w+)", source))
        ok(bool(uniforms), "trollge_vhs.frag declares no float uniforms")
        ok("trollge_vhs" in script, "stage script never loads the trollge_vhs shader")
        ok("camGame.filters" in script, "stage script never attaches the shader to camGame")
        for name in sorted(uniforms):
            ok("'%s'" % name in script or '"%s"' % name in script,
               "uniform %s is never set by the stage script" % name)


# --------------------------------------------------------------------------- #
# HUD
# --------------------------------------------------------------------------- #

def check_hud():
    from PIL import Image

    bar_path = os.path.join(MOD, "images", "game", "healthBar.png")
    if ok(os.path.isfile(bar_path), "images/game/healthBar.png is missing"):
        bar = Image.open(bar_path).convert("RGBA")
        ok(400 <= bar.width <= 1600, "healthBar.png is %d px wide (want 400-1600)" % bar.width)
        ok(8 <= bar.height <= 80, "healthBar.png is %d px tall (want 8-80)" % bar.height)
        # The FlxBar is drawn 4 px inside, so the middle must be the dark "empty" area.
        mid = bar.getpixel((bar.width // 2, bar.height // 2))
        ok(max(mid[:3]) < 70, "healthBar.png centre is too bright for a health bar (%r)" % (mid,))
        ok(min(mid[:3]) >= 0 and mid[3] == 255, "healthBar.png centre must be opaque")

    for name in ("ready", "set", "go"):
        path = os.path.join(MOD, "images", "game", "%s.png" % name)
        if not ok(os.path.isfile(path), "images/game/%s.png is missing" % name):
            continue
        image = Image.open(path).convert("RGBA")
        ok(image.width <= 900 and image.height <= 400,
           "%s.png is %dx%d, too large for the countdown" % (name, image.width, image.height))
        bbox = image.getchannel("A").getbbox()
        ok(bbox is not None, "%s.png is fully transparent" % name)
        if bbox:
            ok((bbox[2] - bbox[0]) > image.width * 0.25 and (bbox[3] - bbox[1]) > image.height * 0.25,
               "%s.png has almost no visible pixels" % name)


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
            ok(chart.get("noteTypes") == L.note_types(song),
               "%s/%s: noteTypes must be %r" % (song["id"], difficulty, L.note_types(song)))
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

#: Characters that ship with the engine itself and do not need a mod XML.
BASE_CHARACTERS = {"bf", "gf", "dad", "mom", "monster", "pico", "spooky",
                   "bf-dead", "gf-dead", "dad-dead"}

#: Animations the engine needs on a playable character.
REQUIRED_CHARACTER_ANIMS = ["idle", "singUP", "singDOWN", "singLEFT", "singRIGHT",
                            "singUPmiss", "singDOWNmiss", "singLEFTmiss", "singRIGHTmiss"]


def load_frames(png, xml):
    """-> (image size, {frame name: (x, y, w, h, frameWidth, frameHeight)})"""
    root = ET.parse(xml).getroot()
    frames = {}
    for el in root:
        if el.tag != "SubTexture":
            continue
        w, h = int(el.get("width")), int(el.get("height"))
        frames[el.get("name")] = (
            int(el.get("x")), int(el.get("y")), w, h,
            int(el.get("frameWidth", w)), int(el.get("frameHeight", h)),
        )
    return frames


def check_atlases():
    try:
        from PIL import Image
    except ImportError:
        WARNINGS.append("Pillow not installed, skipped pixel-level atlas checks")
        return

    char_dir = os.path.join(MOD, "data", "characters")
    for entry in sorted(os.listdir(char_dir)):
        if not entry.endswith(".xml"):
            continue
        char_path = os.path.join(char_dir, entry)
        root = ET.parse(char_path).getroot()
        sprite = root.get("sprite") or entry[:-4]
        png = os.path.join(MOD, "images", "characters", sprite + ".png")
        xml = os.path.join(MOD, "images", "characters", sprite + ".xml")
        ok(os.path.isfile(png) and os.path.isfile(xml),
           "%s: missing atlas %s.png/.xml" % (rel(char_path), sprite))
        if not (os.path.isfile(png) and os.path.isfile(xml)):
            continue

        image = Image.open(png)
        frames = load_frames(png, xml)
        names = set(frames)
        ok(len(frames) > 0, "%s: atlas %s has no frames" % (rel(char_path), sprite))
        for name, (x, y, w, h, _fw, _fh) in frames.items():
            ok(x >= 0 and y >= 0 and x + w <= image.width and y + h <= image.height,
               "%s: frame %r outside of the sheet" % (sprite, name))
        ok(len(set(frames)) == len(frames), "%s: duplicate frame names" % sprite)

        # all frames must share one frame size -- the mod's characters are
        # normalised onto a common canvas so no per-anim offsets are needed
        sizes = {(fw, fh) for (_x, _y, _w, _h, fw, fh) in frames.values()}
        ok(len(sizes) == 1,
           "%s: frames use %d different frame sizes %s" % (sprite, len(sizes), sorted(sizes)))

        anims = {a.get("name"): a.get("anim") for a in root.iter("anim")}
        for name, prefix in anims.items():
            ok(any(n.startswith(prefix) for n in names),
               "%s: anim %r references missing frames %r" % (rel(char_path), name, prefix))

        # a game-over character only needs its death animation
        is_gameover_char = "firstDeath" in anims and "idle" not in anims
        if root.get("isPlayer") == "true" and not is_gameover_char:
            for needed in REQUIRED_CHARACTER_ANIMS:
                ok(needed in anims, "%s: playable character has no %r animation"
                   % (rel(char_path), needed))

        icon = root.get("icon")
        if icon:
            icon_path = os.path.join(MOD, "images", "icons", icon, "icon.png")
            flat = os.path.join(MOD, "images", "icons", "icon-" + icon + ".png")
            ok(os.path.isfile(icon_path) or os.path.isfile(flat),
               "%s: health icon %r not found" % (rel(char_path), icon))

        if is_gameover_char:
            for needed in ("firstDeath", "deathLoop", "deathConfirm"):
                ok(needed in anims, "%s: game-over character has no %r animation"
                   % (rel(char_path), needed))

        dead = root.get("gameOverChar")
        if dead:
            ok(os.path.isfile(os.path.join(char_dir, dead + ".xml")),
               "%s: gameOverChar %r has no character XML" % (rel(char_path), dead))

        # Prefix collision check (Flixel resolves animations with addByPrefix).
        prefixes = sorted({re.sub(r"\d+$", "", n) for n in names})
        for a in prefixes:
            for b in prefixes:
                if a != b and b.startswith(a):
                    ERRORS.append("%s: animation prefix %r shadows %r" % (sprite, a, b))


def check_character_refs():
    """Every character a chart asks for must exist (or be a base-game one)."""
    for song in L.SONGS:
        charts_dir = os.path.join(MOD, "songs", song["id"], "charts")
        if not os.path.isdir(charts_dir):
            continue
        for chart in sorted(os.listdir(charts_dir)):
            data = json.load(open(os.path.join(charts_dir, chart), encoding="utf-8"))
            for line in data.get("strumLines", []):
                for char in line.get("characters") or []:
                    if char in BASE_CHARACTERS:
                        continue
                    path = os.path.join(MOD, "data", "characters", char + ".xml")
                    ok(os.path.isfile(path),
                       "%s/%s: character %r has no data/characters/%s.xml"
                       % (song["id"], chart, char, char))


def check_icons():
    try:
        from PIL import Image
    except ImportError:
        return
    for icon in ("trollge", "trollge_glitch", "trollge_static", "trollge_final",
                 "trollge_sad", "bf_blue", "bf_smiler", "bf_super_scary"):
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

    # Cheap syntax safety net for every HScript file (no engine needed).
    for path in walk(".hx"):
        src = open(path, encoding="utf-8").read()
        stripped = re.sub(r"//[^\n]*", "", src)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)
        stripped = re.sub(r'"(?:\\.|[^"\\])*"', '""', stripped)
        for open_ch, close_ch in (("{", "}"), ("(", ")"), ("[", "]")):
            ok(stripped.count(open_ch) == stripped.count(close_ch),
               "%s: unbalanced %r / %r" % (rel(path), open_ch, close_ch))

    # Strum skinning lives in the stage script (strums do not read noteTypes).
    stage_script = os.path.join(MOD, "data", "stages", "trollge.hx")
    if os.path.isfile(stage_script):
        code = open(stage_script, encoding="utf-8").read()
        ok("function onStrumCreation" in code, "stage script is missing the onStrumCreation hook")
        for skin in ("shadow", "corrupt"):
            ok("'%s'" % skin in code or '"%s"' % skin in code,
               "stage script never references the %r skin" % skin)
            ok(os.path.isfile(os.path.join(MOD, "images", "game", "notes", skin + ".png")),
               "stage script uses the %r skin but its atlas is missing" % skin)

    # Character XML extensions must point at a real script.
    for char in ("trollge", "trollge_scary"):
        path = os.path.join(MOD, "data", "characters", char + ".xml")
        if not os.path.isfile(path):
            continue
        for ext in ET.parse(path).getroot().iter("extension"):
            target = os.path.join(MOD, "data", "scripts", ext.get("script") + ".hx")
            ok(os.path.isfile(target), "%s: extension script %r missing" % (char, ext.get("script")))


def check_audio():
    import soundfile as sf
    for name in ("intro1", "intro2", "intro3", "introGo"):
        path = os.path.join(MOD, "sounds", name + ".ogg")
        if ok(os.path.isfile(path), "sounds/%s.ogg is missing" % name):
            duration = sf.info(path).duration
            ok(0.2 <= duration <= 2.0, "sounds/%s.ogg is %.2fs (want 0.2-2.0s)" % (name, duration))
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
    check_noteskin()
    check_hud()
    check_shaders()
    check_atlases()
    check_character_refs()
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
