#!/usr/bin/env python3
"""
Imports hand-drawn Boyfriend skins into the mod.

You drop a Sparrow atlas (`.png` + `.xml`) into `art_src/bf/`, list it in `SKINS`
below, and this tool:

  1. renames every frame to a collision-free code (`BFblue sUP0000`, `mUP0000`, ...)
     so `addByPrefix` can never mix a sing pose up with its miss pose,
  2. re-anchors every animation so the character always stands on the same ground
     line (the Trollge's feet: y=539 of a 460x560 frame) and is centred on x=229,
  3. re-packs everything so *all* frames share one frame size -- the character XML
     needs no offsets and every skin sits at the same stage position,
  4. fills gaps the uploaded art does not have: miss poses are graded from the sing
     poses (desaturated, blood-tinted), and a game-over frame is derived from idle,
  5. writes `data/characters/<character>.xml` (+ `<character>_dead`), a 300x150
     two-frame health icon, and `docs/<character>.png` for review.

Run with:  python3 tools/make_bf.py               (all skins)
           python3 tools/make_bf.py trolling      (one skin, by song id)
"""

import os
import re
import sys

from PIL import Image, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
SRC = os.path.join(ROOT, "art_src", "bf")
CHARS = os.path.join(MOD, "data", "characters")
IMAGES = os.path.join(MOD, "images", "characters")
ICONS = os.path.join(MOD, "images", "icons")

# The Trollge atlas is 460x560 with his feet on y=539 and his body centred on
# x=229, so every imported skin is normalised to exactly that geometry.
CANVAS_W, CANVAS_H = 460, 560
BASELINE, CENTER_X = 539, 229

ICON_W, ICON_H = 300, 150


# --------------------------------------------------------------------------- #
# Skins
#
# anims: (engine anim name, Sparrow prefix in the uploaded atlas, fps, loop)
#   Missing prefixes are either derived (miss poses, game-over) or aliased to a
#   pose that does exist -- the tool prints what it did.
# icon_frames: (engine anim name, frame number) used for the two icon states.
# --------------------------------------------------------------------------- #

SKINS = [
    {
        # song 1 -- "Trolling" (2/10)
        "song": "trolling",
        "source": ("new_blue_boyfriend.png", "new_blue_boyfriend.xml"),
        "short": "BFblue",
        "sprite": "Boyfriend_blue",
        "character": "bf_blue",
        "dead_character": "bf_blue_dead",
        "icon": "bf_blue",
        "color": "#31B0D1",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "derive_miss": True,
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "BF NOTE UP", 24, False),
            ("singDOWN", "BF NOTE DOWN", 24, False),
            ("singLEFT", "BF NOTE LEFT", 24, False),
            ("singRIGHT", "BF NOTE RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "BF HEY", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "BF NOTE DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },
    {
        # song 2 -- "It's Getting Dark" (4/10)
        "song": "getting_dark",
        "source": ("Smiler_Boyfriend_3.png", "Smiler_Boyfriend_3.xml"),
        "short": "BFsmiler",
        "sprite": "Boyfriend_smiler",
        "character": "bf_smiler",
        "dead_character": "bf_smiler_dead",
        "icon": "bf_smiler",
        "color": "#5C6BC0",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "derive_miss": False,       # the smiler atlas has its own corrupt miss poses
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "BF NOTE UP", 24, False),
            ("singDOWN", "BF NOTE DOWN", 24, False),
            ("singLEFT", "BF NOTE LEFT", 24, False),
            ("singRIGHT", "BF NOTE RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "BF NOTE UP", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "BF NOTE DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },
    {
        # song 3 -- "Super Scary Trollge" (7/10)
        "song": "super_scary",
        "source": ("Boyfriend_crazy2.png", "Boyfriend_crazy2.xml"),
        "short": "BFscary",
        "sprite": "Boyfriend_super_scary",
        "character": "bf_super_scary",
        "dead_character": "bf_super_scary_dead",
        "icon": "bf_super_scary",
        "color": "#C4101E",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "derive_miss": False,
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "UP", 24, False),
            ("singDOWN", "DOWN", 24, False),
            ("singLEFT", "LEFT", 24, False),
            ("singRIGHT", "RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "UP", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },
]

SING_DIRS = ("UP", "DOWN", "LEFT", "RIGHT")


# --------------------------------------------------------------------------- #
# Naming
# --------------------------------------------------------------------------- #

def anim_code(engine_name):
    """singUP -> sUP, singLEFTmiss -> mLEFT, idle -> idle, hey -> hey."""
    if engine_name == "idle":
        return "idle"
    if engine_name.startswith("sing") and engine_name.endswith("miss"):
        return "m" + engine_name[4:-4]
    if engine_name.startswith("sing"):
        return "s" + engine_name[4:]
    return engine_name


# --------------------------------------------------------------------------- #
# Atlas reading
# --------------------------------------------------------------------------- #

def read_atlas(png_path, xml_path):
    """-> {frame name: composed RGBA frame (own frame size)}"""
    sheet = Image.open(png_path).convert("RGBA")
    text = open(xml_path, encoding="utf-8", errors="replace").read()

    frames = {}
    for raw in re.findall(r"<SubTexture ([^/>]+)/?>", text):
        d = dict(re.findall(r'(\w+)="([^"]*)"', raw))
        x, y = int(d["x"]), int(d["y"])
        w, h = int(d["width"]), int(d["height"])
        fw = int(d.get("frameWidth", w))
        fh = int(d.get("frameHeight", h))
        fx = int(d.get("frameX", 0))
        fy = int(d.get("frameY", 0))
        canvas = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        canvas.paste(sheet.crop((x, y, x + w, y + h)), (-fx, -fy))
        frames[d["name"]] = canvas
    return frames


def group_anims(frames):
    """Sparrow names -> {prefix: [names in numeric order]}"""
    groups = {}
    for name in frames:
        m = re.match(r"^(.*?)(\d+)$", name)
        prefix, index = (m.group(1), int(m.group(2))) if m else (name, 0)
        groups.setdefault(prefix, []).append((index, name))
    return {p: [n for _, n in sorted(v)] for p, v in groups.items()}


def anchor_of(image):
    """Feet y and horizontal centre of the visible art."""
    box = image.getchannel("A").getbbox()
    if box is None:
        return None
    return box[3], (box[0] + box[2]) / 2.0


def place(image, dx, dy, used_flip=False):
    target = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    target.alpha_composite(image, (int(round(dx)), int(round(dy))))
    return target


# --------------------------------------------------------------------------- #
# Grading (used when the upload has no miss / death art)
# --------------------------------------------------------------------------- #

def grade_miss(image):
    """Desaturated, darkened, blood-tinted version of a sing pose."""
    rgb = image.convert("RGB")
    grey = ImageEnhance.Color(rgb).enhance(0.30)
    grey = ImageEnhance.Brightness(grey).enhance(0.78)
    red = Image.new("RGB", image.size, (168, 8, 26))
    hurt = Image.blend(grey, red, 0.34)
    out = hurt.convert("RGBA")
    out.putalpha(image.getchannel("A"))
    return out


def grade_dead(image):
    """Near-black silhouette with a red cast, for the game-over screen."""
    rgb = image.convert("RGB")
    dark = ImageEnhance.Color(rgb).enhance(0.10)
    dark = ImageEnhance.Brightness(dark).enhance(0.42)
    red = Image.new("RGB", image.size, (90, 0, 8))
    out = Image.blend(dark, red, 0.28).convert("RGBA")
    out.putalpha(image.getchannel("A"))
    return out


# --------------------------------------------------------------------------- #
# Building
# --------------------------------------------------------------------------- #

def build_frames(skin, frames, groups):
    """-> (ordered [(new frame name, image)], {engine anim: prefix})"""
    built = []              # (name, image)
    anim_prefix = {}        # engine anim -> generated prefix
    by_engine = {}          # engine anim -> [new frame names]

    planned = []            # (source prefix, code)
    seen = {}
    for engine_name, prefix, _fps, _loop in skin["anims"]:
        if prefix not in groups:
            continue
        if prefix in seen:
            anim_prefix[engine_name] = seen[prefix]
            continue
        code = anim_code(engine_name)
        new_prefix = "%s %s" % (skin["short"], code)
        seen[prefix] = new_prefix
        anim_prefix[engine_name] = new_prefix
        planned.append((prefix, new_prefix))

    for prefix, new_prefix in planned:
        names = groups[prefix]
        first = anchor_of(frames[names[0]])
        if first is None:
            continue
        foot, centre = first
        dx = CENTER_X - centre
        dy = BASELINE - foot
        made = []
        for i, name in enumerate(names):
            out_name = "%s%04d" % (new_prefix, i)
            built.append((out_name, place(frames[name], dx, dy)))
            made.append(out_name)
        for engine_name, pfx, _fps, _loop in skin["anims"]:
            if pfx == prefix:
                by_engine[engine_name] = made

    # --- miss poses the upload does not have ------------------------------
    for direction in SING_DIRS:
        engine_name = "sing" + direction + "miss"
        if engine_name in by_engine or not skin.get("derive_miss"):
            continue
        source = by_engine.get("sing" + direction)
        if not source:
            continue
        new_prefix = "%s m%s" % (skin["short"], direction)
        made = []
        for i, new_name in enumerate(source):
            image = dict(built)[new_name]
            out_name = "%s%04d" % (new_prefix, i)
            built.append((out_name, grade_miss(image)))
            made.append(out_name)
        by_engine[engine_name] = made
        anim_prefix[engine_name] = new_prefix
        print("     + derived %s from %s" % (engine_name, "sing" + direction))

    # --- anything else the upload does not have --------------------------
    # Aliasing keeps `hey`/`scared`/`hit` (cutscenes, game events) working on
    # skins that only ship idles and sing poses.
    fallbacks = [
        ("hey", ["singUP", "idle"]),
        ("scared", ["singUPmiss", "singUP", "idle"]),
        ("hit", ["singDOWNmiss", "singDOWN", "idle"]),
        ("pre-attack", ["singRIGHT", "idle"]),
        ("attack", ["singLEFT", "idle"]),
        ("dodge", ["singDOWN", "idle"]),
    ]
    for engine_name, sources in fallbacks:
        if engine_name in by_engine:
            continue
        for source in sources:
            if source in by_engine:
                by_engine[engine_name] = by_engine[source]
                anim_prefix[engine_name] = anim_prefix[source]
                print("     = %s aliased to %s" % (engine_name, source))
                break

    # --- game-over art ----------------------------------------------------
    dead_prefix = skin["dead"][0]
    if dead_prefix in groups:
        names = groups[dead_prefix]
        first = anchor_of(frames[names[0]])
        dx = CENTER_X - first[1]
        dy = BASELINE - first[0]
        new_prefix = "%s die" % skin["short"]
        made = []
        for i, name in enumerate(names):
            out_name = "%s%04d" % (new_prefix, i)
            built.append((out_name, place(frames[name], dx, dy)))
            made.append(out_name)
    else:
        idle = by_engine.get("idle") or []
        if not idle:
            raise SystemExit("%s: no idle frames, cannot build a game-over sprite" % skin["sprite"])
        new_prefix = "%s die" % skin["short"]
        image = grade_dead(dict(built)[idle[0]])
        out_name = "%s0000" % new_prefix
        built.append((out_name, image))
        made = [out_name]
        print("     + derived game-over frame from idle")
    skin["_dead_prefix"] = new_prefix
    skin["_dead_frames"] = made
    return built, anim_prefix, by_engine


def pack(frames, sprite, dest_dir):
    """Shelf-pack the normalised frames into one PNG + Sparrow XML."""
    entries = []
    for name, image in frames:
        box = image.getchannel("A").getbbox()
        if box is None:
            continue
        entries.append((name, image.crop(box), box))

    max_w = 2048
    x = y = row_h = 0
    placed = []
    for name, crop, box in entries:
        if x + crop.width > max_w:
            x, y, row_h = 0, y + row_h, 0
        placed.append((name, crop, box, x, y))
        x += crop.width
        row_h = max(row_h, crop.height)

    total_w = max(p[3] + p[1].width for p in placed)
    total_h = y + row_h
    sheet = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    for _name, crop, _box, px, py in placed:
        sheet.paste(crop, (px, py))

    png_path = os.path.join(dest_dir, sprite + ".png")
    sheet.save(png_path, optimize=True)

    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<TextureAtlas imagePath="%s.png">' % sprite,
    ]
    for name, crop, box, px, py in placed:
        lines.append(
            '    <SubTexture name="%s" x="%d" y="%d" width="%d" height="%d" '
            'frameX="%d" frameY="%d" frameWidth="%d" frameHeight="%d"/>'
            % (name, px, py, crop.width, crop.height,
               -box[0], -box[1], CANVAS_W, CANVAS_H)
        )
    lines.append("</TextureAtlas>")
    open(os.path.join(dest_dir, sprite + ".xml"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return png_path, len(placed)


# --------------------------------------------------------------------------- #
# Icons and previews
# --------------------------------------------------------------------------- #

def head_icon(image, frac=0.82, dx=20):
    """Bust crop (head + shoulders) of a normalised frame, 150x150.

    A bust rather than a face crop: the uploaded art has a small head on a big
    body, and a tight face crop reads as an accidental zoom.
    """
    box = image.getchannel("A").getbbox()
    art_h = box[3] - box[1]
    size = int(art_h * frac)
    cx = (box[0] + box[2]) // 2 + dx
    top = box[1]
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile.paste(image.crop((cx - size // 2, top, cx + size // 2, top + size)), (0, 0))
    return tile.resize((150, 150), Image.LANCZOS)


def build_icon(skin, built_map, by_engine):
    tiles = []
    for engine_name, index in skin["icon_frames"]:
        names = by_engine.get(engine_name) or []
        if not names:
            continue
        name = names[min(index, len(names) - 1)]
        tiles.append(head_icon(built_map[name]))
    if not tiles:
        return None
    icon = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    for i, tile in enumerate(tiles[:2]):
        icon.alpha_composite(tile, (i * 150, 0))
    out_dir = os.path.join(ICONS, skin["icon"])
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "icon.png")
    icon.save(path, optimize=True)
    return path


def build_preview(built_map, by_engine, skin):
    """docs/<character>.png -- pose strip for the README / pull requests."""
    picks = []
    for engine_name, index in (("idle", 1), ("singUP", 0), ("singLEFT", 0),
                               ("singRIGHT", 0), ("singDOWN", 0),
                               ("singUPmiss", 0)):
        names = by_engine.get(engine_name) or []
        if names:
            picks.append(built_map[names[min(index, len(names) - 1)]])
    if not picks:
        return None
    scale = 0.42
    tw, th = int(CANVAS_W * scale), int(CANVAS_H * scale)
    strip = Image.new("RGBA", (tw * len(picks), th), (18, 14, 18, 255))
    for i, frame in enumerate(picks):
        strip.alpha_composite(frame.resize((tw, th), Image.LANCZOS), (i * tw, 0))
    docs = os.path.join(ROOT, "docs")
    os.makedirs(docs, exist_ok=True)
    path = os.path.join(docs, skin["character"] + ".png")
    strip.convert("RGB").save(path, optimize=True)
    return path


# --------------------------------------------------------------------------- #
# Character XML
# --------------------------------------------------------------------------- #

def character_xml(skin, anims, dead=False):
    head = [
        "<!DOCTYPE codename-engine-character>",
        '<character sprite="%s" flipX="true" isPlayer="true" icon="%s" color="%s"%s>'
        % (skin["sprite"], skin["icon"], skin["color"],
           "" if dead else ' gameOverChar="%s"' % skin["dead_character"]),
    ]
    body = [
        '    <anim name="%s" anim="%s" x="0" y="0" fps="%d" loop="%s"/>'
        % (name, prefix, fps, "true" if loop else "false")
        for name, prefix, fps, loop in anims
    ]
    return "\n".join(head + body + ["</character>", ""])


def build_skin(skin):
    png_src, xml_src = skin["source"]
    frames = read_atlas(os.path.join(SRC, png_src), os.path.join(SRC, xml_src))
    groups = group_anims(frames)

    built, anim_prefix, by_engine = build_frames(skin, frames, groups)
    built_map = dict(built)

    missing = [e for e, _p, _f, _l in skin["anims"] if e not in by_engine]
    if missing:
        print("     ! no frames for: %s (the engine falls back to idle)"
              % ", ".join(missing))

    os.makedirs(IMAGES, exist_ok=True)
    png_path, count = pack(built, skin["sprite"], IMAGES)
    print("  -> %s (%d frames, %d anims)"
          % (os.path.relpath(png_path, ROOT), count, len(by_engine)))

    os.makedirs(CHARS, exist_ok=True)
    anims = [(name, anim_prefix[name], fps, loop)
             for name, _prefix, fps, loop in skin["anims"] if name in anim_prefix]
    char_path = os.path.join(CHARS, skin["character"] + ".xml")
    open(char_path, "w", encoding="utf-8").write(character_xml(skin, anims))
    print("  -> %s" % os.path.relpath(char_path, ROOT))

    dead_anims = [
        ("firstDeath", skin["_dead_prefix"], skin["dead"][1], False),
        ("deathLoop", skin["_dead_prefix"], skin["dead"][1], True),
        ("deathConfirm", skin["_dead_prefix"], skin["dead"][1], False),
    ]
    dead_path = os.path.join(CHARS, skin["dead_character"] + ".xml")
    open(dead_path, "w", encoding="utf-8").write(character_xml(skin, dead_anims, dead=True))
    print("  -> %s" % os.path.relpath(dead_path, ROOT))

    preview = build_preview(built_map, by_engine, skin)
    if preview:
        print("  -> %s" % os.path.relpath(preview, ROOT))

    icon = build_icon(skin, built_map, by_engine)
    if icon:
        print("  -> %s" % os.path.relpath(icon, ROOT))


def main(argv):
    wanted = argv[1:]
    skins = [s for s in SKINS if not wanted or s["song"] in wanted]
    if not skins:
        print("No matching skin. Known: " + ", ".join(s["song"] for s in SKINS))
        return 1
    for skin in skins:
        print("Importing %s skin (%s)..." % (skin["song"], skin["character"]))
        build_skin(skin)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
