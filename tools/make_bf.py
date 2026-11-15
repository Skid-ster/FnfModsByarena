#!/usr/bin/env python3
"""
Imports a hand-drawn Boyfriend skin into the mod.

You drop a Sparrow atlas (`.png` + `.xml`) into `art_src/bf/`, list it in `SKINS`
below, and this tool:

  1. re-anchors every animation so the character always stands on the same
     ground line (the Trollge's feet: y=539 of a 460x560 frame),
  2. re-centres every animation horizontally, so switching between idle and a
     sing pose cannot make him slide around,
  3. re-packs everything into a clean Sparrow atlas where *all* frames share one
     frame size -- which means the character XML needs no offsets at all and the
     stage can place every skin at the same x/y,
  4. writes `data/characters/<character>.xml` (+ a game-over variant built from
     the atlas' death frame),
  5. builds the 300x150 two-frame health icon from the head of the idle frame and
     the head of the "hurt" frame.

Run with:  python3 tools/make_bf.py            (all skins)
           python3 tools/make_bf.py super_scary  (one skin)
"""

import os
import re
import sys

from PIL import Image

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
# anims: (engine anim name, Sparrow prefix, fps, loop)
#   The prefixes must exist in the uploaded atlas; anything the atlas does not
#   have is silently skipped, and the engine falls back to `idle`.
# --------------------------------------------------------------------------- #

SKINS = [
    {
        "song": "super_scary",
        "source": ("Boyfriend_crazy2.png", "Boyfriend_crazy2.xml"),
        "sprite": "Boyfriend_super_scary",
        "character": "bf_super_scary",
        "dead_character": "bf_super_scary_dead",
        "icon": "bf_super_scary",
        "color": "#31B0D1",
        "icon_frames": ("BF idle dance0000", "BF NOTE UP MISS0000"),
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
    # Song 2's skin gets added here once it is uploaded:
    # {
    #     "song": "getting_dark",
    #     "source": ("Boyfriend_<name>.png", "Boyfriend_<name>.xml"),
    #     "sprite": "Boyfriend_getting_dark",
    #     "character": "bf_getting_dark",
    #     ...
    # },
]


# --------------------------------------------------------------------------- #

def read_atlas(png_path, xml_path):
    """-> {frame name: (image, frameWidth, frameHeight, frameX, frameY)}"""
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
        frames[d["name"]] = (canvas, fw, fh, fx, fy)
    return frames


def group_anims(frames):
    """Sparrow names -> {prefix: [(index, name)]} keeping the numeric suffix order."""
    groups = {}
    for name in frames:
        m = re.match(r"^(.*?)(\d+)$", name)
        prefix, index = (m.group(1), int(m.group(2))) if m else (name, 0)
        groups.setdefault(prefix, []).append((index, name))
    return {p: [n for _, n in sorted(v)] for p, v in groups.items()}


def anchor_of(frames, name):
    """Feet y and body centre x of a single frame, in its own frame space."""
    image = frames[name][0]
    box = image.getchannel("A").getbbox()
    if box is None:
        return None
    return box[3], (box[0] + box[2]) / 2.0


def normalise(frames, prefixes):
    """Re-anchor every prefix onto the shared canvas. -> [PIL image] in order."""
    out = []
    for prefix in prefixes:
        names = group_anims(frames).get(prefix)
        if not names:
            continue
        first = anchor_of(frames, names[0])
        if first is None:
            continue
        foot, centre = first
        dx = CENTER_X - centre
        dy = BASELINE - foot
        for name in names:
            canvas, fw, fh, fx, fy = frames[name]
            target = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
            # keep the frame's own trim offset (that is what makes a pose line up
            # with its neighbours), then apply the animation anchor
            target.alpha_composite(canvas, (int(round(dx - fx)), int(round(dy - fy))))
            out.append((name, target))
    return out


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


def head_icon(image, frac=0.82, dx=20):
    """Bust crop (head + shoulders) of a normalised frame, 150x150.

    A bust rather than a face crop: the uploaded Boyfriend art has a small head
    on a big body, and a tight face crop reads as an accidental zoom.
    """
    box = image.getchannel("A").getbbox()
    art_h = box[3] - box[1]
    size = int(art_h * frac)
    cx = (box[0] + box[2]) // 2 + dx
    top = box[1]
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile.paste(image.crop((cx - size // 2, top, cx + size // 2, top + size)), (0, 0))
    return tile.resize((150, 150), Image.LANCZOS)


def build_icon(skin, frames):
    tiles = [head_icon(frames[name], *skin.get("icon_crop", (0.82, 20)))
                 for name in skin["icon_frames"]]
    icon = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        icon.alpha_composite(tile, (i * 150, 0))
    out_dir = os.path.join(ICONS, skin["icon"])
    os.makedirs(out_dir, exist_ok=True)
    icon.save(os.path.join(out_dir, "icon.png"), optimize=True)
    return os.path.join(out_dir, "icon.png")


def character_xml(skin, anims, dead=False):
    head = [
        "<!DOCTYPE codename-engine-character>",
        '<character sprite="%s" flipX="true" isPlayer="true" icon="%s" color="%s"%s>'
        % (skin["sprite"], skin["icon"], skin["color"],
           ' gameOverChar="%s"' % skin["dead_character"] if not dead else ""),
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
    available = group_anims(frames)

    used, missing = [], []
    for name, prefix, fps, loop in skin["anims"]:
        if prefix in available:
            used.append((name, prefix, fps, loop))
        else:
            missing.append("%s (%r)" % (name, prefix))

    prefixes = []
    for _name, prefix, _fps, _loop in used:
        if prefix not in prefixes:
            prefixes.append(prefix)

    dead_prefix, dead_fps = skin["dead"]
    if dead_prefix in available and dead_prefix not in prefixes:
        prefixes.append(dead_prefix)

    normalised = normalise(frames, prefixes)
    normalised_map = dict(normalised)

    os.makedirs(IMAGES, exist_ok=True)
    png_path, count = pack(normalised, skin["sprite"], IMAGES)
    print("  -> %s (%d frames, %d anims)" % (os.path.relpath(png_path, ROOT), count, len(used)))
    if missing:
        print("     ! not in the uploaded atlas, engine falls back to idle: " + ", ".join(missing))

    os.makedirs(CHARS, exist_ok=True)
    char_path = os.path.join(CHARS, skin["character"] + ".xml")
    open(char_path, "w", encoding="utf-8").write(character_xml(skin, used))
    print("  -> %s" % os.path.relpath(char_path, ROOT))

    if dead_prefix in available:
        dead_anims = [
            ("firstDeath", dead_prefix, dead_fps, False),
            ("deathLoop", dead_prefix, dead_fps, False),
            ("deathConfirm", dead_prefix, dead_fps, False),
        ]
        dead_path = os.path.join(CHARS, skin["dead_character"] + ".xml")
        open(dead_path, "w", encoding="utf-8").write(
            character_xml(skin, dead_anims, dead=True)
        )
        print("  -> %s" % os.path.relpath(dead_path, ROOT))

    build_preview(normalised, skin)

    icon_path = build_icon(skin, normalised_map)
    print("  -> %s" % os.path.relpath(icon_path, ROOT))


def build_preview(normalised, skin):
    """docs/<character>.png -- pose strip for the README / pull requests."""
    picks = []
    for want in ("idle", "singUP", "singLEFT", "singRIGHT", "singDOWN",
                 "singUPmiss", "singRIGHTmiss"):
        frames = [img for name, img in normalised if name.startswith(_prefix_of(skin, want))]
        if frames:
            picks.append(frames[min(1, len(frames) - 1)])
    if not picks:
        return
    scale = 0.42
    tw, th = int(CANVAS_W * scale), int(CANVAS_H * scale)
    strip = Image.new("RGBA", (tw * len(picks), th), (18, 14, 18, 255))
    for i, frame in enumerate(picks):
        strip.alpha_composite(frame.resize((tw, th), Image.LANCZOS), (i * tw, 0))
    docs = os.path.join(ROOT, "docs")
    os.makedirs(docs, exist_ok=True)
    path = os.path.join(docs, skin["character"] + ".png")
    strip.convert("RGB").save(path, optimize=True)
    print("  -> %s" % os.path.relpath(path, ROOT))


def _prefix_of(skin, anim_name):
    for name, prefix, _fps, _loop in skin["anims"]:
        if name == anim_name:
            return prefix
    return anim_name


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
