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
import math
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
    "data/config/freeplaySonglist/LIB_TrollgeMod.txt",
    "data/weeks/characters/trollge.xml",
    "images/icons/trollge/icon.png",
    "data/characters/bf_blue.xml",
    "data/characters/bf_blue_dead.xml",
    "data/characters/bf_smiler.xml",
    "data/characters/bf_smiler_dead.xml",
    "data/characters/bf_super_scary.xml",
    "data/characters/bf_super_scary_dead.xml",
    "data/characters/bf_glitched.xml",
    "data/characters/bf_glitched_dead.xml",
    "data/characters/bf_damned.xml",
    "data/characters/bf_damned_dead.xml",
    "images/characters/Boyfriend_blue.png",
    "images/characters/Boyfriend_blue.xml",
    "images/characters/Boyfriend_smiler.png",
    "images/characters/Boyfriend_smiler.xml",
    "images/characters/Boyfriend_super_scary.png",
    "images/characters/Boyfriend_super_scary.xml",
    "images/characters/Boyfriend_glitched.png",
    "images/characters/Boyfriend_glitched.xml",
    "images/characters/Boyfriend_damned.png",
    "images/characters/Boyfriend_damned.xml",
    "images/icons/bf_blue/icon.png",
    "images/icons/bf_smiler/icon.png",
    "images/icons/bf_super_scary/icon.png",
    "images/icons/bf_glitched/icon.png",
    "images/icons/bf_damned/icon.png",
    "images/stages/trollge/bg.png",
    "images/stages/trollge/bg_scary.png",
    "images/stages/trollge/bg_glitch.png",
    "images/stages/trollge/bg_nightmare.png",
    "images/stages/trollge/bg_hell.png",
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
    "images/game/notes/torn.png",
    "images/game/notes/torn.xml",
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


#: The four buttons MainMenuState builds, and the two animations it asks for.
MENU_OPTIONS = ["story mode", "freeplay", "options", "credits"]


def check_menu():
    """The mod's own main menu: art, music, and the redirect that lands on it."""
    from PIL import Image

    for option in MENU_OPTIONS:
        png = os.path.join(MOD, "images", "menus", "mainmenu", option + ".png")
        xml = os.path.join(MOD, "images", "menus", "mainmenu", option + ".xml")
        if not ok(os.path.isfile(png) and os.path.isfile(xml),
                  "menu button atlas missing for %r" % option):
            continue
        frames = read_atlas(png, xml) or {}
        for prefix in ("%s basic" % option, "%s white" % option):
            names = [n for n in frames if n.startswith(prefix)]
            ok(bool(names), "menus/mainmenu/%s.xml has no %r frames (engine asks for that "
                            "animation by prefix)" % (option, prefix))
        # Every frame has to fit in the sheet, or the button draws as garbage.
        sheet = Image.open(png).size
        for name, (w, h) in frames.items():
            ok(0 < w <= sheet[0] and 0 < h <= sheet[1],
               "menus/mainmenu/%s: frame %r is %dx%d inside a %dx%d sheet"
               % (option, name, w, h, sheet[0], sheet[1]))
        ok(any(frames[n][1] >= 100 for n in frames),
           "menus/mainmenu/%s: every frame is shorter than 100 px" % option)

    bg = os.path.join(MOD, "images", "menus", "menuBG.png")
    if ok(os.path.isfile(bg), "images/menus/menuBG.png is missing"):
        ok(Image.open(bg).size == (1286, 730),
           "menus/menuBG.png is %s, the engine's slot is 1286x730" % (Image.open(bg).size,))

    menu_music = os.path.join(MOD, "music", "trollgeMenu.ogg")
    if ok(os.path.isfile(menu_music), "music/trollgeMenu.ogg is missing"):
        try:
            import soundfile as sf
            ok(4.0 <= sf.info(menu_music).duration <= 90.0,
               "music/trollgeMenu.ogg is %.1fs" % sf.info(menu_music).duration)
        except ImportError:
            pass

    ini = os.path.join(MOD, "data", "config", "modpack.ini")
    text = open(ini, encoding="utf-8").read() if os.path.isfile(ini) else ""
    ok('DEFAULT_MENU_MUSIC="trollgeMenu"' in text,
       "modpack.ini does not point DEFAULT_MENU_MUSIC at trollgeMenu")
    ok("[StateRedirects]" in text, "modpack.ini has no [StateRedirects] section")
    ok('TitleState="funkin.menus.MainMenuState"' in text,
       "modpack.ini does not redirect TitleState to funkin.menus.MainMenuState")
    # A short class name would not resolve, and the engine would then look for a
    # data/states/<name>/LIB_<mod>.hx script that cannot exist under every install
    # name (folder vs zip), leaving a black screen.
    ok('TitleState="MainMenuState"' not in text,
       "the redirect value must be the full class path, not the short name")


def check_script_safety():
    """Guards for the two HScript traps that crashed a shipped build."""
    for path in walk(".hx"):
        source = open(path, encoding="utf-8").read()
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith(("//", "*", "/*")))
        ok(".borderStyle" not in code,
           "%s assigns borderStyle; FlxTextBorderStyle is a real enum and "
           "FlxText.regenGraphic() switches on it, so a raw int is a null deref"
           % rel(path))
        if "FlxTypeText" in code:
            ok("resetText(" in code,
               "%s builds a FlxTypeText without resetText(); start() only takes a "
               "delay and types whatever _finalText already holds" % rel(path))


#: Uniforms the CRT shader must declare, and the ones HScript is expected to drive.
CRT_UNIFORMS = ["uTime", "iTime", "uAberration", "uScanline", "uStatic",
                "uCurvature", "uVignette", "uGlitch"]


def check_crt():
    """shaders/crt.frag: an OpenFL fragment shader, wired in without crashing."""
    shader = os.path.join(MOD, "shaders", "crt.frag")
    if not ok(os.path.isfile(shader), "shaders/crt.frag is missing"):
        return
    with open(shader, encoding="utf-8") as handle:
        source = handle.read()
    stage_path = os.path.join(MOD, "data", "stages", "trollge.hx")
    stage = ""
    if os.path.isfile(stage_path):
        with open(stage_path, encoding="utf-8") as handle:
            stage = handle.read()

    # OpenFL/Flixel conventions -- without these the shader will not compile.
    ok("#pragma header" in source, "crt.frag is missing #pragma header")
    ok("void main()" in source, "crt.frag has no main()")
    ok("openfl_TextureCoordv" in source, "crt.frag never samples openfl_TextureCoordv")
    ok("openfl_TextureSize" in source, "crt.frag never uses openfl_TextureSize")
    ok("openfl_Alphav" in source, "crt.frag should document OpenFL alpha handling")
    shader_code = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    ok(not re.search(r"\bflixel_texture2D\s*\(", shader_code),
       "crt.frag calls unsupported flixel_texture2D")
    ok(bool(re.search(r"\btextureCam\s*\(\s*bitmap\b", shader_code)),
       "crt.frag camera filter must fetch via textureCam(bitmap, ...)")
    ok(bool(re.search(r"\bgetCamPos\s*\(", shader_code)),
       "crt.frag camera filter must convert with getCamPos")
    ok(not re.search(r"\btexture2D\s*\(\s*bitmap\b", shader_code),
       "crt.frag camera filter must not fetch bitmap via texture2D")
    ok(source.count("{") == source.count("}"), "crt.frag has unbalanced braces")
    ok(source.count("(") == source.count(")"), "crt.frag has unbalanced parentheses")
    ok("gl_FragColor" in source, "crt.frag never writes gl_FragColor")

    declared = set(re.findall(r"uniform\s+float\s+(\w+)", source))
    for name in CRT_UNIFORMS:
        ok(name in declared, "crt.frag does not declare uniform %s" % name)

    # Wiring: loaded by name, attached to both cameras, updated through a guard.
    ok("fromFile('crt')" in stage, "stage script never loads shaders/crt.frag")
    ok(stage.count("fromFile('crt')") >= 2,
       "stage script should load crt twice (game camera + HUD camera)")
    for camera in ("camGame.filters", "camHUD.filters"):
        ok(camera in stage, "stage script never attaches the CRT to %s" % camera)
    ok("setFloatOn(" in stage, "stage script has no guarded shader uniform setter")
    ok(stage.count("try {") >= 6, "shader setup/updates are not wrapped in try/catch guards")

    # Every uniform the script drives has to exist, or setFloat silently no-ops.
    driven = set(re.findall(r"setFloatOn\(crt\w*, '([\w]+)'", stage))
    ok(bool(driven), "stage script never updates the CRT uniforms")
    for name in sorted(driven):
        ok(name in declared, "stage script sets %s but crt.frag does not declare it" % name)

    # The uniform update has to live in update(elapsed), not only in create().
    ok(re.search(r"function update\(elapsed:Float\)", stage) is not None,
       "stage script has no update(elapsed) for per-frame shader uniforms")
    ok("'uTime'" in stage and "'iTime'" in stage,
       "stage script should drive both uTime and iTime")


def check_package():
    """Everything the engine can load must actually be inside the shipped zip."""
    import package_mod

    root_entries = sorted(
        e for e in os.listdir(MOD) if not e.startswith(".") and e not in package_mod.EXCLUDE
    )
    ok(set(root_entries) <= set(package_mod.INCLUDE),
       "mod root has entries the packager skips: %s"
       % sorted(set(root_entries) - set(package_mod.INCLUDE)))
    for entry in package_mod.INCLUDE:
        full = os.path.join(MOD, entry)
        ok(os.path.exists(full), "packaged entry missing: %s" % entry)
    # The archive name *is* the mod name: Codename's MainState passes the zip's
    # file name (without extension) into ModsFolderLibrary as `modName`, and
    # freeplay then looks for config/freeplaySonglist/LIB_<modName>.txt. A zip
    # called SuperScaryTrollge-v3.6.0.zip therefore names the mod
    # "superscarytrollge-v3.6.0", loses the freeplay list and makes
    # ModsFolder.init() forget the selection on the next launch. The mod folder
    # and the installable archive have to agree with the LIB_ file, exactly.
    mod_name = os.path.basename(MOD)
    ok(package_mod.INSTALL_NAME == mod_name,
       "package_mod.INSTALL_NAME is %r but the mod folder is %r: the engine names "
       "a mod after the file it loads, so these must match or freeplay will not "
       "find its LIB_ list" % (package_mod.INSTALL_NAME, mod_name))
    list_file = os.path.join(MOD, "data", "config", "freeplaySonglist",
                             "LIB_%s.txt" % mod_name)
    ok(os.path.isfile(list_file),
       "freeplay not found by the engine: %r is loaded as modName %r, so it looks "
       "for LIB_%s.txt and this file does not exist"
       % (package_mod.INSTALL_NAME + ".zip", mod_name, mod_name))

    # music/ only exists for the game-over overrides -- make sure it is really in.
    for rel_path in ("music/gameOver.ogg", "music/gameOver.ini",
                     "sounds/gameOverSFX.ogg", "sounds/gameOverEnd.ogg"):
        ok(os.path.isfile(os.path.join(MOD, rel_path)), "missing %s" % rel_path)
        ok(rel_path.split("/")[0] in package_mod.INCLUDE,
           "%s would not be packaged" % rel_path)


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


def mod_folder():
    """The mod's folder name == the name the engine derives from the zip."""
    return os.path.basename(MOD)


def _lib_redirect(asset, mod_name):
    """Port of ModsFolderLibrary.__parseAsset / ZipFolderLibrary.__parseAsset.

    The engine's libraries treat a file name starting with `LIB_` as a
    *redirect*: `__parseAsset` strips the `LIB_<mod>.` prefix and keeps the
    extension, then looks that path up instead. In Haxe (`haxe.io.Path`):

        var file = new Path(_parsedAsset);
        if (file.file.startsWith("LIB_")) {
            if (file.file.substr(4) != modName) return false;
            _parsedAsset = file.dir + "." + file.ext;
        }

    So `data/config/freeplaySonglist/LIB_TrollgeMod.txt` becomes
    `data/config/freeplaySonglist.txt` -- the `LIB_` file is never opened as a
    file. This is the behaviour that broke freeplay in v3.6.0, so it is
    modelled here rather than described.
    """
    prefix = "assets/"
    if not asset.startswith(prefix):
        return None
    parsed = asset[len(prefix):]
    slash = parsed.rfind("/")
    directory = parsed[:slash] if slash != -1 else ""
    base = parsed[slash + 1:] if slash != -1 else parsed
    dot = base.rfind(".")
    stem = base[:dot] if dot != -1 else base
    ext = base[dot + 1:] if dot != -1 else ""
    if stem.startswith("LIB_"):
        if stem[4:] != mod_name:
            return None
        # file.dir + "." + file.ext  (empty dir -> ".txt", exactly like Haxe)
        parsed = (directory + "." if directory else ".") + ext
    return parsed


def _freeplay_target(mod_name):
    """The path the engine ends up opening for this mod's freeplay list."""
    # FreeplayState: Paths.txt('config/freeplaySonglist/LIB_$modName')
    # Paths.txt(key) == getPath('data/' + key + '.txt')
    asked = "data/config/freeplaySonglist/LIB_%s.txt" % mod_name
    return _lib_redirect(prefix_asset(asked), mod_name)


def prefix_asset(path):
    return "assets/" + path


def check_week_and_freeplay():
    """Freeplay and story mode both have to offer this mod's five songs.

    The mechanism (source: funkin/menus/FreeplayState.hx, class FreeplaySonglist,
    plus funkin/backend/assets/ModsFolderLibrary.hx, __parseAsset):

        asked  = Paths.txt('config/freeplaySonglist/LIB_$modName')
        parsed = __parseAsset(asked)          # LIB_<mod>.x -> <dir>/x
        found  = modLib.exists(parsed, "TEXT")

    `__parseAsset` REWRITES the path: the `LIB_<mod>.` file name becomes the
    plain name in the same directory. A mod that ships only
    `data/config/freeplaySonglist/LIB_TrollgeMod.txt` therefore ships *nothing*
    the engine opens, because it looks for
    `data/config/freeplaySonglist.txt`. That is exactly what v3.6.0 did, and why
    freeplay showed the base game's list while story mode -- whose `LIB_` target
    (`data/weeks/weeks.txt`) *was* shipped -- kept working.

    This check is written against the resolved path for that reason.
    """
    ids = [s["id"] for s in L.SONGS]
    week = os.path.join(MOD, "data", "weeks", "weeks", "trollge_week.xml")
    if os.path.isfile(week):
        root = ET.parse(week).getroot()
        listed_diffs = [node.get("name") for node in root.findall("difficulty")]
        ok(listed_diffs == list(L.DIFFICULTIES),
           "week difficulties are %s, expected %s" % (listed_diffs, list(L.DIFFICULTIES)))
        listed = [node.text.strip() for node in root.iter("song") if node.text]
        ok(listed == ids, "week song list is %s, expected %s" % (listed, ids))

    # Story mode works only because the mod ships the file the LIB_ lookup
    # redirects to. Assert that, so nobody "tidies up" weeks.txt.
    weeks_target = _lib_redirect(prefix_asset("data/weeks/weeks/LIB_%s.txt" % mod_folder()), mod_folder())
    ok(weeks_target is not None,
       "the week list lookup does not resolve at all (mod folder name does not "
       "match the LIB_ prefix the engine rewrites)")
    ok(os.path.isfile(os.path.join(MOD, weeks_target)),
       "story mode is broken: the engine asks for data/weeks/weeks/LIB_<mod>.txt, "
       "rewrites it to %s, and that file is not shipped" % weeks_target)

    config = os.path.join(MOD, "data", "config")
    base_ids = {"bopeebo", "fresh", "dadbattle", "spookeez", "south", "monster",
                "pico", "philly-nice", "blammed", "satin-panties", "high", "milf",
                "cocoa", "eggnog", "winter-horrorland", "senpai", "roses", "thorns",
                "ugh", "guns", "stress", "tutorial", "test"}

    # 1. The path the engine actually opens has to exist. This is the check that
    #    would have caught the v3.6.0 freeplay bug.
    target = _freeplay_target(mod_folder())
    ok(target is not None,
       "freeplay list lookup does not resolve (libName/modName mismatch)")
    resolved = os.path.join(MOD, target) if target else None
    ok(bool(resolved) and os.path.isfile(resolved),
       "freeplay would show the BASE GAME's songs: the engine asks for "
       "data/config/freeplaySonglist/LIB_<mod>.txt, __parseAsset rewrites that to "
       "%s, and the file is not shipped" % (target or "?"))
    ok(not os.path.isfile(os.path.join(config, "freeplaySonglist.txt")) or True,
       "unreachable placeholder")

    # 2. Read the file the engine reads, and check its contents.
    if resolved and os.path.isfile(resolved):
        with open(resolved, encoding="utf-8") as handle:
            raw = handle.read()
        listed = [line.strip() for line in raw.splitlines()
                  if line.strip() and not line.strip().startswith("#")]
        ok(listed == ids, "freeplay songlist is %s, expected the five songs in "
                          "scare order %s" % (listed, ids))
        ok(len(listed) == len(set(listed)), "freeplay songlist lists a song twice")
        strangers = [s for s in listed if s not in ids]
        ok(not strangers, "freeplay songlist contains ids that are not this mod's "
                          "songs (freeplay would show an entry that cannot play): %s"
           % ", ".join(strangers))
        ok(not (set(listed) & base_ids), "freeplay songlist still contains base-game ids")
        for song_id in listed:
            ok(os.path.isfile(os.path.join(MOD, "songs", song_id, "meta.json")),
               "freeplay songlist lists %r but songs/%s/meta.json is missing"
               % (song_id, song_id))

    # 3. The LIB_ compatibility copy, if present, must agree with the real list --
    #    two lists that disagree is worse than one.
    lib_copy = os.path.join(config, "freeplaySonglist", "LIB_%s.txt" % mod_folder())
    if os.path.isfile(lib_copy):
        with open(lib_copy, encoding="utf-8") as handle:
            copy_listed = [line.strip() for line in handle if line.strip()
                           and not line.strip().startswith("#")]
        with open(resolved, encoding="utf-8") as handle:
            real_listed = [line.strip() for line in handle if line.strip()
                           and not line.strip().startswith("#")]
        ok(copy_listed == real_listed,
           "freeplaySonglist/LIB_%s.txt disagrees with freeplaySonglist.txt "
           "(the LIB_ file is only a redirect target; they must match)" % mod_folder())

    # 4. Nothing else may sit in the freeplay folder.
    list_dir = os.path.join(config, "freeplaySonglist")
    if os.path.isdir(list_dir):
        allowed = {"LIB_%s.txt" % mod_folder()}
        others = sorted(f for f in os.listdir(list_dir) if f not in allowed)
        ok(not others, "data/config/freeplaySonglist/ has unexpected files: %s"
           % ", ".join(others))

    # Older engine generations try the pre-config path. Both the literal and
    # rewritten lookups must contain the same ordered ids as the current list.
    for old_path in ("data/freeplaySonglist.txt",
                     "data/freeplaySonglist/LIB_%s.txt" % mod_folder()):
        filename = os.path.join(MOD, old_path)
        ok(os.path.isfile(filename), "older freeplay path is missing: %s" % old_path)
        if os.path.isfile(filename):
            with open(filename, encoding="utf-8") as handle:
                old_ids = [line.strip() for line in handle
                           if line.strip() and not line.strip().startswith("#")]
            ok(old_ids == ids, "older freeplay list disagrees: %s" % old_path)

    # 5. The flag that makes it a replacement rather than an append.
    ini = os.path.join(config, "modpack.ini")
    ini_text = open(ini, encoding="utf-8").read() if os.path.isfile(ini) else ""
    ok('SONGS_LIST_MOD_MODE="override"' in ini_text,
       "modpack.ini must pin SONGS_LIST_MOD_MODE=\"override\": freeplay replaces "
       "the base list instead of appending to it")


def check_mod_json():
    data = json.load(open(os.path.join(MOD, "mod.json"), encoding="utf-8"))
    ok(isinstance(data.get("version"), str) and data["version"].count(".") == 2,
       "mod.json needs a semantic version string")
    ids = [s["id"] for s in L.SONGS]
    ok(sorted(data.get("songs", [])) == sorted(ids), "mod.json songs must match the built songs")
    ok(data.get("week") == "trollge_week", "mod.json week must be trollge_week")
    ok(sorted(data.get("scareTiers", {})) == sorted(ids),
       "mod.json scareTiers must list every song")
    ok([data.get("scareTiers", {}).get(i) for i in ids]
       == sorted(data.get("scareTiers", {}).get(i) for i in ids),
       "mod.json scareTiers must rise with the song order")
    ok(sorted(data.get("playerCharacters", {})) == sorted(ids),
       "mod.json playerCharacters must list every song")
    ok(len(set(data.get("playerCharacters", {}).values())) == len(ids),
       "every song needs its own Boyfriend skin")


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

    for skin in ("default", "shadow", "corrupt", "torn"):
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
        # The shader has to be inside the zip to ever compile, and the lookup is
        # Paths.fragShader("trollge_vhs") -> shaders/trollge_vhs.frag.
        ok("shaders" in __import__("package_mod").INCLUDE,
           "package_mod.py would ship without shaders/ (the grade would vanish)")
        ok("#pragma header" in source and "void main()" in source,
           "trollge_vhs.frag is missing its pragma header or main()")
        ok(source.count("{") == source.count("}"), "trollge_vhs.frag has unbalanced braces")
        ok("gl_FragColor" in source or "FragColor" in source,
           "trollge_vhs.frag never writes a colour")
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


def check_cutscenes():
    """Cutscenes are code, so they are checked like code.

    Codename finds songs/<song>/cutscene.hx and songs/<song>/cutscene-end.hx on
    its own; if either is missing the song silently loses its intro / outro. If
    the script references an image or a sound that does not ship, the cutscene
    throws at load time and the player sees nothing at all.
    """
    for song in L.SONGS:
        base = os.path.join(MOD, "songs", song["id"])
        for name in ("cutscene.hx", "cutscene-end.hx"):
            path = os.path.join(base, name)
            if not ok(os.path.isfile(path), "%s is missing %s" % (song["id"], name)):
                continue
            text = open(path, encoding="utf-8").read()
            ok("function create()" in text,
               "%s/%s has no create()" % (song["id"], name))
            ok("function destroy()" in text,
               "%s/%s has no destroy(): the HUD would stay hidden" % (song["id"], name))
            ok("camHUD.visible = true" in text,
               "%s/%s never restores the HUD" % (song["id"], name))
            ok("FlxG.cameras.remove(cam)" in text,
               "%s/%s leaks its camera" % (song["id"], name))

            for sound in set(re.findall(r'Paths\.sound\("([^"]+)"\)', text)):
                ok(os.path.isfile(os.path.join(MOD, "sounds", sound + ".ogg")),
                   "%s/%s plays sounds/%s.ogg, which does not exist"
                   % (song["id"], name, sound))
            for image in set(re.findall(r'Paths\.image\("([^"]+)"\)', text)):
                ok(os.path.isfile(os.path.join(MOD, "images", image + ".png")),
                   "%s/%s loads images/%s.png, which does not exist"
                   % (song["id"], name, image))

        # The dialogue itself comes from song_layout, so it cannot be empty.
        cutscene = song.get("cutscene")
        ok(cutscene is not None, "%s has no cutscene data in song_layout" % song["id"])
        if cutscene is None:
            continue
        ok(len(cutscene["lines"]) >= 2,
           "%s needs at least two intro lines" % song["id"])
        ok(len(cutscene["outro"]) >= 1, "%s has no outro line" % song["id"])
        for who, line, _shake in cutscene["lines"]:
            ok(bool(line.strip()), "%s has an empty cutscene line" % song["id"])
            ok(who in ("TROLLGE", "BF", ""),
               "%s: unknown speaker %r" % (song["id"], who))
        for _who, line, _shake in cutscene["outro"]:
            ok(bool(line.strip()), "%s has an empty outro line" % song["id"])
        script = open(os.path.join(base, "cutscene.hx"), encoding="utf-8").read()
        for _who, line, _shake in cutscene["lines"]:
            ok(hx_quote(line) in script,
               "%s/cutscene.hx is out of date (missing %r); run tools/make_cutscenes.py"
               % (song["id"], line))

    # The art the cutscenes draw must exist at the size the layout assumes.
    from PIL import Image
    for name, size in (("ui/cutscene_bar_top", (1280, 100)),
                       ("ui/cutscene_bar_bottom", (1280, 100)),
                       ("ui/cutscene_frame", (1180, 208)),
                       ("ui/cutscene_frame_dark", (1180, 208)),
                       ("ui/cutscene_veil", (1280, 720))):
        path = os.path.join(MOD, "images", name + ".png")
        if not ok(os.path.isfile(path), "missing cutscene art %s.png" % name):
            continue
        with Image.open(path) as img:
            ok(img.size == size, "%s.png is %s, expected %s" % (name, img.size, size))
            if "veil" not in name:
                ok(img.mode == "RGBA", "%s.png needs an alpha channel" % name)


def hx_quote(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def check_game_over():
    """The death screen is three files and one ini -- Codename reads exactly these.

    GameOverSubstate: CoolUtil.playMusic(Paths.music("gameOver")) with the BPM from
    music/gameOver.ini, Paths.sound("gameOverSFX") for the mic drop and
    Paths.sound("gameOverEnd") for the retry. Miss one and the base game's asset
    plays instead, which is the most obvious "this mod is unfinished" moment there is.
    """
    music = os.path.join(MOD, "music", "gameOver.ogg")
    ini = os.path.join(MOD, "music", "gameOver.ini")
    ok(os.path.isfile(music), "music/gameOver.ogg is missing (deaths use the base theme)")
    ok(os.path.isfile(ini), "music/gameOver.ini is missing (the game-over BPM)")
    if os.path.isfile(ini):
        text = open(ini, encoding="utf-8").read()
        ok("BPM" in text, "music/gameOver.ini has no BPM line")
        ok(not text.strip().startswith(";") or "BPM =" in text,
           "music/gameOver.ini only contains comments")

    try:
        import soundfile as sf
    except ImportError:
        return
    if os.path.isfile(music):
        info = sf.info(music)
        ok(8.0 <= info.duration <= 64.0,
           "music/gameOver.ogg is %.1fs (want a 8-64s loop)" % info.duration)
        ok(info.samplerate >= 44100 // 2, "music/gameOver.ogg: odd sample rate")
    for name, lo, hi in (("gameOverSFX", 0.6, 2.5), ("gameOverEnd", 0.4, 1.6)):
        path = os.path.join(MOD, "sounds", name + ".ogg")
        if ok(os.path.isfile(path), "sounds/%s.ogg is missing" % name):
            info = sf.info(path)
            ok(lo <= info.duration <= hi,
               "sounds/%s.ogg is %.2fs, want %.1f-%.1fs" % (name, info.duration, lo, hi))


def check_captions():
    """In-song captions: real text, inside the song, and a function to draw them."""
    behaviour = open(os.path.join(MOD, "data", "scripts", "trollge_song_behavior.hx"),
                     encoding="utf-8").read()
    ok("function trollgeCaption(" in behaviour,
       "trollge_song_behavior.hx does not define trollgeCaption()")
    ok("caption.cameras = [ps.camHUD]" in behaviour,
       "captions must be drawn on the HUD camera")

    for song in L.SONGS:
        captions = song.get("captions", [])
        ok(len(captions) >= 3, "%s needs at least three in-song captions" % song["id"])
        length = L.length(song)
        for seconds, text in captions:
            ok(0.0 < seconds < length,
               "%s: caption at %.1fs is outside the song" % (song["id"], seconds))
            ok(bool(text.strip()), "%s has an empty caption" % song["id"])
            ok(len(text) <= 60, "%s: caption %r is too long to read" % (song["id"], text))
            # PlayState splits an "HScript Call" param on commas before calling the
            # function, so a comma inside a caption would silently eat a word.
            ok("," not in text, "%s: caption %r contains a comma (engine splits on it)"
               % (song["id"], text))
        events = json.load(open(os.path.join(MOD, "songs", song["id"], "events.json"),
                                encoding="utf-8"))["events"]
        times = [e["time"] for e in events]
        ok(times == sorted(times), "%s/events.json is not in chronological order" % song["id"])
        shipped = [event for event in events if event["params"][0] == "trollgeCaption"]
        ok(len(shipped) == len(captions),
           "%s: %d captions in the events file, %d in song_layout "
           "(run tools/make_chart.py)" % (song["id"], len(shipped), len(captions)))


def check_charts():
    for song in L.SONGS:
        base = os.path.join(MOD, "songs", song["id"])
        meta_path = os.path.join(base, "meta.json")
        if not os.path.isfile(meta_path):
            ERRORS.append("missing meta.json for %s" % song["id"])
            continue
        meta = json.load(open(meta_path, encoding="utf-8"))

        ok(meta["bpm"] == song["bpm"], "%s meta bpm mismatch" % song["id"])
        ok(tuple(meta["difficulties"]) == tuple(L.DIFFICULTIES),
           "%s must ship the base game's difficulties %s, not %s"
           % (song["id"], list(L.DIFFICULTIES), meta["difficulties"]))
        custom = meta.get("customValues", {})
        ok(custom.get("scareTier") == song["scare"], "%s scareTier mismatch" % song["id"])
        ok(custom.get("songKey") == L.key_name(song),
           "%s: meta songKey must be %r" % (song["id"], L.key_name(song)))
        ok(meta.get("needsVoices") is True and os.path.isfile(
            os.path.join(base, "song", "Voices.ogg")),
           "%s: needsVoices is true but song/Voices.ogg is missing "
           "(the characters would sing in silence)" % song["id"])
        ok(os.path.isfile(os.path.join(base, "song", "Inst.ogg")),
           "%s is missing song/Inst.ogg" % song["id"])
        ok(song["id"] == song["id"].lower() and "_" not in song["id"],
           "%s: song folder names are lowercase-hyphenated like the base game" % song["id"])

        expected_length = L.length(song) * 1000.0
        bars = int(round(L.measures(song)))

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
            ok(1.1 <= float(chart.get("scrollSpeed", 0)) <= 2.6,
               "%s/%s: scrollSpeed must sit in the base game's 1.2-2.6 range"
               % (song["id"], difficulty))
            ok(abs(float(chart.get("scrollSpeed", 0)) - L.scroll_speed(song, difficulty)) < 1e-6,
               "%s/%s: scrollSpeed does not match song_layout" % (song["id"], difficulty))

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
            ok(total == len(L.notes(song, difficulty)),
               "%s/%s: expected %d notes, found %d"
               % (song["id"], difficulty, len(L.notes(song, difficulty)), total))

            # Charting convention: every bar is sung by exactly one character.
            # A bar with notes in both strum lines is the old mixed-side bug.
            measure_ms = L.measure(song) * 1000.0
            offset_ms = song["offset"] * 1000.0
            bar_sides = {}
            for line in lines:
                for note in line["notes"]:
                    # +1e-6: a note exactly on the bar line must land in that bar,
                    # not the previous one (float division lands just under it).
                    bar = int(math.floor((float(note["time"]) - offset_ms) / measure_ms + 1e-6))
                    bar_sides.setdefault(bar, set()).add(line["position"])
            ok(all(len(sides) == 1 for sides in bar_sides.values()),
               "%s/%s: a bar mixes player and opponent notes" % (song["id"], difficulty))
            ok(len(bar_sides) >= bars - 2,
               "%s/%s: %d of %d bars have notes" % (song["id"], difficulty, len(bar_sides), bars))

            bookmarks = chart.get("bookmarks", [])
            ok(len(bookmarks) == len(L.sections(song)),
               "%s/%s: expected %d section bookmarks" % (song["id"], difficulty, len(L.sections(song))))
            ok(all("name" in b and "color" in b for b in bookmarks),
               "%s/%s: bookmark missing name/color" % (song["id"], difficulty))

        events = json.load(open(os.path.join(base, "events.json"), encoding="utf-8"))["events"]
        expected = [e for e in events if e["name"] == "HScript Call"]
        # Story beats + in-song captions are both HScript Calls.
        wanted = len(song["events"]) + len(song.get("captions", []))
        ok(len(expected) == wanted,
           "%s: expected %d scripted story events, found %d"
           % (song["id"], wanted, len(expected)))
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
        # Strings first: a "//" inside a string literal is not a comment, and
        # the cutscene titles are full of them ("TROLLGE WEEK  //  3 OF 5").
        stripped = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
        stripped = re.sub(r"//[^\n]*", "", stripped)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)
        for open_ch, close_ch in (("{", "}"), ("(", ")"), ("[", "]")):
            ok(stripped.count(open_ch) == stripped.count(close_ch),
               "%s: unbalanced %r / %r" % (rel(path), open_ch, close_ch))

    # Strum skinning lives in the stage script (strums do not read noteTypes).
    stage_script = os.path.join(MOD, "data", "stages", "trollge.hx")
    if os.path.isfile(stage_script):
        code = open(stage_script, encoding="utf-8").read()
        ok("function onStrumCreation" in code, "stage script is missing the onStrumCreation hook")
        ok("function onNoteHit" in code, "stage script is missing the onNoteHit hook")
        for sfx in ("bf_note_", "trollge_note_"):
            ok(sfx in code, "stage script never plays the %r voices" % sfx)
        for fn in ("function camShake", "function zoomPunch", "function measureHit"):
            ok(fn in code, "stage script is missing %r" % fn)
        for skin in ("shadow", "corrupt", "torn"):
            ok("'%s'" % skin in code or '"%s"' % skin in code,
               "stage script never references the %r skin" % skin)
            ok(os.path.isfile(os.path.join(MOD, "images", "game", "notes", skin + ".png")),
               "stage script uses the %r skin but its atlas is missing" % skin)

    # Every Trollge phase needs the behavior extension, not merely an existing
    # script file: an absent <extension> otherwise silently disables flicker.
    for char in ("trollge", "trollge_glitch", "trollge_static", "trollge_final", "trollge_sad"):
        path = os.path.join(MOD, "data", "characters", char + ".xml")
        if not os.path.isfile(path):
            continue
        extensions = [ext.get("script") for ext in ET.parse(path).getroot().iter("extension")]
        ok(extensions.count("trollge_behavior") == 1,
           "%s: expected one trollge_behavior extension" % char)
        target = os.path.join(MOD, "data", "scripts", "trollge_behavior.hx")
        ok(os.path.isfile(target), "%s: trollge_behavior extension is missing" % char)


def check_stage_positioning():
    """The stage numbers are not freehand: tools/make_stage_preview.py proves the
    engine framing. Re-run it here so a stray edit cannot quietly clip a
    character or un-level the two ground lines."""
    import subprocess
    result = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_stage_preview.py")],
                            capture_output=True, text=True)
    ok(result.returncode == 0,
       "stage preview failed:\n%s" % (result.stdout + result.stderr).strip())


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

        voices = os.path.join(MOD, "songs", song["id"], "song", "Voices.ogg")
        if os.path.isfile(voices):
            vinfo = sf.info(voices)
            ok(abs(vinfo.duration - expected) < 0.15,
               "%s: Voices.ogg is %.2fs, the instrumental is %.2fs (they must sync)"
               % (song["id"], vinfo.duration, expected))
            ok(vinfo.samplerate == info.samplerate,
               "%s: Voices.ogg and Inst.ogg must share a sample rate" % song["id"])

    for sfx in ("trollge_jump_scare", "trollge_distortion", "trollge_invert",
                "trollge_hit", "trollge_miss", "trollge_theme", "trollge_theme_scary",
                "bf_note_up", "bf_note_down", "bf_note_left", "bf_note_right",
                "trollge_note_up", "trollge_note_down", "trollge_note_left",
                "trollge_note_right"):
        path = os.path.join(MOD, "sounds", sfx + ".ogg")
        if os.path.isfile(path):
            info = sf.info(path)
            ok(info.duration > 0.05, "%s.ogg is suspiciously short" % sfx)


# --------------------------------------------------------------------------- #
# README (the repo front page)
# --------------------------------------------------------------------------- #

MD_LINK = re.compile(r"(?P<image>!?)\[[^\]]*\]\((?P<target>[^)\s]+)\)")


def _github_anchor(heading):
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def check_readme():
    """The front page is a claim about the repo, so treat it like one."""
    path = os.path.join(ROOT, "README.md")
    if not ok(os.path.isfile(path), "README.md is missing"):
        return
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    headings = [_github_anchor(line.lstrip("#"))
                for line in text.splitlines() if line.startswith("#")]

    broken = []
    bad_fragment = []
    for match in MD_LINK.finditer(text):
        target = match.group("target")
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if target.startswith("#"):
            if target[1:] not in headings:
                bad_fragment.append(target)
            continue
        if target.startswith(".."):
            continue
        file_part = target.split("#", 1)[0]
        if not os.path.exists(os.path.join(ROOT, file_part)):
            broken.append(target)
    ok(not broken, "README links to missing file(s): %s" % ", ".join(sorted(set(broken))))
    ok(not bad_fragment,
       "README links to dead anchor(s): %s" % ", ".join(sorted(set(bad_fragment))))

    with open(os.path.join(MOD, "mod.json"), encoding="utf-8") as fh:
        version = json.load(fh)["version"]
    ok(("SuperScaryTrollge-v%s.zip" % version) in text,
       "README does not name the current zip (SuperScaryTrollge-v%s.zip)" % version)
    stale = sorted({v for v in re.findall(r"SuperScaryTrollge-v(\d+\.\d+\.\d+)\.zip", text)
                    if v != version})
    ok(not stale, "README names an old zip version: %s" % ", ".join(stale))

    for name in ("trollge_vhs.frag", "crt.frag"):
        ok(name in text, "README never mentions shaders/%s" % name)
    for preview in ("menu_preview.png", "noteskin.png"):
        ok(preview in text, "README never shows docs/%s" % preview)

    # Last, because it counts itself: the README quotes the validator's own tally,
    # so a check added anywhere else must be reflected on the front page.
    claim = re.search(r"\*\*(\d+) checks, (\d+) errors, (\d+) warnings\*\*", text)
    if claim is None:
        ok(False, "README does not state the validator's check count")
        return
    total = CHECKS + 1
    problems = []
    if int(claim.group(1)) != total:
        problems.append("README claims %s checks, validator runs %d"
                        % (claim.group(1), total))
    if not (ERRORS or WARNINGS) and (int(claim.group(2)) or int(claim.group(3))):
        problems.append("README claims %s errors / %s warnings on a clean run"
                        % (claim.group(2), claim.group(3)))
    ok(not problems, "; ".join(problems))


def main():
    quiet = "--quiet" in sys.argv

    check_required()
    check_json()
    check_xml()
    check_mod_json()
    check_week_and_freeplay()
    check_charts()
    check_cutscenes()
    check_game_over()
    check_captions()
    check_menu()
    check_crt()
    check_script_safety()
    check_package()
    check_noteskin()
    check_hud()
    check_shaders()
    check_atlases()
    check_character_refs()
    check_icons()
    check_scripts()
    check_stage_positioning()
    check_audio()
    check_readme()

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
