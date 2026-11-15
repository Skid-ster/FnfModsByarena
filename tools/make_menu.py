#!/usr/bin/env python3
"""
The mod's own menus.

Three jobs, all of them art, because art cannot crash:

  * `images/menus/mainmenu/{story mode,freeplay,options,credits}.png|.xml`
    -- the four buttons `MainMenuState` builds from
    `Paths.getFrames('menus/mainmenu/<option>')` with animations
    `<option> basic` (idle) and `<option> white` (selected).
  * `images/menus/menuBG.png` -- the backdrop `MainMenuState` loads as
    `menus/menuBG` (1286x730, single frame; `loadAnimatedGraphic` accepts a
    plain PNG and gives it one frame).
  * `docs/menu_preview.png` -- the menu as it will look, for the README.

The look: a defocused hallway with the Trollge standing in the dark of it (its
eyes are the only thing still lit), bone typography that has been through a tape
deck -- chromatic fringing, chewed edges, blood running off the descenders --
and a jagged crimson slash under whichever option is selected.

`data/config/modpack.ini` sends the boot straight here:

    [StateRedirects]
    TitleState="funkin.menus.MainMenuState"

which is a *documented* codename redirect (`Flags.MOD_REDIRECT_STATES`, resolved
in `GlobalScript`'s `preStateSwitch` hook with `Type.resolveClass`, so the value
has to be the full class path, not the short name). No custom state script: a
`ModState` would look for `data/states/<name>/LIB_<mod>.hx`, and that file name
depends on what the mod folder or zip is called, so it is not something a
download can rely on.

Run with:  python3 tools/make_menu.py
"""

import math
import os
import random
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
MENUS = os.path.join(MOD, "images", "menus")
MAINMENU = os.path.join(MENUS, "mainmenu")
STAGES = os.path.join(MOD, "images", "stages", "trollge")
CHARS = os.path.join(MOD, "images", "characters")
DOCS = os.path.join(ROOT, "docs")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

#: Engine geometry, copied from MainMenuState.hx: items sit at
#: `60 + i * 160`, idle frames are ~122 px tall, selected ones ~172.
BG_W, BG_H = 1286, 730
IDLE_H = 122
SELECTED_H = 172

BONE = (238, 232, 236)
BLOOD = (196, 16, 30)
CONGEALED = (96, 8, 18)
ASH = (150, 144, 154)
INK = (10, 8, 12)

#: option -> label. The engine reads these from `config/menuItems.txt`; the mod
#: keeps the base order so nothing about navigation changes.
OPTIONS = [
    ("story mode", "STORY MODE"),
    ("freeplay", "FREEPLAY"),
    ("options", "OPTIONS"),
    ("credits", "CREDITS"),
]


# --------------------------------------------------------------------------- #
# text measuring
# --------------------------------------------------------------------------- #

def tracked(text, font, tracking):
    """Width of `text` with `tracking` extra pixels between glyphs."""
    width = 0.0
    for ch in text:
        width += font.getlength(ch) + tracking
    return width - tracking


def draw_tracked(draw, x, y, text, font, fill, tracking):
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking


def text_layer(label, font, tracking):
    """The label on its own transparent canvas, plus its ink box."""
    ascent, descent = font.getmetrics()
    w = int(math.ceil(tracked(label, font, tracking))) + 8
    h = ascent + descent + 8
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_tracked(ImageDraw.Draw(img), 4, 4, label, font, (255, 255, 255, 255), tracking)
    return img


# --------------------------------------------------------------------------- #
# text damage
# --------------------------------------------------------------------------- #

def chewed_alpha(layer, seed, keep=0.62):
    """Eat holes out of the glyph edges, the way a bad tape drop-out does."""
    rng = random.Random(seed)
    mask = layer.getchannel("A")
    w, h = layer.size
    noise = Image.effect_noise((w, h), 42).convert("L")
    noise = noise.filter(ImageFilter.GaussianBlur(0.6))
    # Threshold at random per-band heights so the damage comes in horizontal
    # tears rather than an even dither.
    torn = Image.new("L", (w, h), 0)
    td = ImageDraw.Draw(torn)
    y = 0
    while y < h:
        band = rng.randint(2, 9)
        cut = rng.uniform(0.35, 0.75)
        td.rectangle([0, y, w, y + band], fill=int(255 * cut))
        y += band
    eaten = ImageChops.multiply(noise, torn)
    # Anything under the cut line loses most of its opacity.
    eaten = eaten.point(lambda v: 255 if v > 150 else int(255 * keep))
    return ImageChops.multiply(mask, eaten)


def chroma(layer, red=2, cyan=-2):
    """Red/cyan fringing: the classic tape-deck misregistration."""
    r, g, b, a = layer.split()
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    left = Image.merge("RGBA", (r, g.point(lambda v: int(v * 0.25)), b, a))
    right = Image.merge("RGBA", (r.point(lambda v: int(v * 0.25)), g, b, a))
    out.alpha_composite(left, (-red, 0))
    out.alpha_composite(right, (-cyan, 0))
    return out


def drips(size, mask, seed, colour, count=5):
    """Thin runs of blood hanging off the glyphs, clipped to the ink column."""
    rng = random.Random(seed)
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    columns = [x for x in range(6, w - 6, 3) if mask.getpixel((x, int(h * 0.62))) > 40]
    if not columns:
        return layer
    for _ in range(count):
        x = rng.choice(columns)
        length = rng.randint(int(h * 0.10), int(h * 0.34))
        y0 = int(h * 0.58)
        width = rng.choice([1, 2, 2, 3])
        draw.line([(x, y0), (x + rng.randint(-1, 1), y0 + length)],
                  fill=colour + (rng.randint(120, 200),), width=width)
        r = width
        draw.ellipse([x - r, y0 + length - r, x + r, y0 + length + r],
                     fill=colour + (rng.randint(150, 210),))
    return layer.filter(ImageFilter.GaussianBlur(0.5))


def render_label(label, font, tracking, fill, seed, edge=None, drips_on=False, fringe=2):
    """A finished label: fringed, chewed, optionally bleeding, optionally slashed."""
    ink = text_layer(label, font, tracking)
    w, h = ink.size

    body = Image.new("RGBA", (w, h), fill + (0,))
    body.putalpha(ink.getchannel("A"))
    body.putalpha(chewed_alpha(ink, seed))

    out = chroma(body, red=fringe, cyan=-fringe)
    out.alpha_composite(body)

    if edge:
        ring = ImageChops.subtract(ink.getchannel("A"), ink.getchannel("A").filter(ImageFilter.MinFilter(3)))
        line = Image.new("RGBA", (w, h), edge + (0,))
        line.putalpha(ring.point(lambda v: int(v * 0.75)))
        out.alpha_composite(line)

    if drips_on:
        out.alpha_composite(drips((w, h), ink.getchannel("A"), seed + 91, CONGEALED))
    return out


def slash(width, seed, height=10):
    """A jagged crimson scratch, the way a nail would take the paint off."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    points = []
    x = 0
    y = height // 2
    while x < width:
        points.append((x, y + rng.randint(-3, 3)))
        x += rng.randint(6, 22)
        y = max(2, min(height - 3, y + rng.randint(-4, 4)))
    points.append((width - 1, height // 2))
    draw.line(points, fill=BLOOD + (250,), width=4, joint="curve")
    # a second, finer scratch riding just above it
    fine = [(px, py - 3) for px, py in points]
    draw.line(fine, fill=(255, 120, 120, 140), width=1, joint="curve")
    # spatter
    for _ in range(int(width / 26)):
        sx = rng.randrange(width)
        sr = rng.choice([1, 2, 3])
        sy = rng.choice([1, height - 2])
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=BLOOD + (rng.randint(120, 220),))
    return layer


# --------------------------------------------------------------------------- #
# buttons
# --------------------------------------------------------------------------- #

def button_frames(option, label):
    """Idle + selected frames for one menu item, as (name, image) pairs."""
    frames = []

    idle_font = ImageFont.truetype(FONT_BOLD, IDLE_H - 18)
    sel_font = ImageFont.truetype(FONT_BOLD, SELECTED_H - 26)

    for i in range(2):
        # Idle: ash-grey, chewed edges, faint fringing. Two near-identical frames
        # so the engine's 24 fps loop does not look frozen.
        flick = 0 if i == 0 else 7
        w = int(math.ceil(tracked(label, idle_font, 3))) + 28
        h = IDLE_H
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        base = tuple(min(255, c + flick) for c in ASH)
        ink = render_label(label, idle_font, 3, base, seed=17 + i, edge=(8, 6, 10), fringe=1)
        # Drop shadow first, then the ink, so idle items sit *in* the backdrop.
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow.alpha_composite(ink, (17, (h - ink.height) // 2 + 4))
        shadow.putalpha(shadow.getchannel("A").point(lambda v: int(v * 0.85)))
        black = Image.new("RGBA", (w, h), (2, 2, 4, 255))
        black.putalpha(shadow.getchannel("A"))
        img.alpha_composite(black)
        img.alpha_composite(ink, (12, (h - ink.height) // 2))
        frames.append(("%s basic%04d" % (option, i), img))

    for i in range(2):
        # Selected: bone, heavier fringe, blood off the descenders and a jagged
        # crimson slash underneath. Twice as loud as idle.
        w = int(math.ceil(tracked(label, sel_font, 4))) + 52
        h = SELECTED_H
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

        ink = render_label(label, sel_font, 4, BONE, seed=41 + i, drips_on=True, fringe=3)
        # Blood bloom behind the glyphs: the same ink, blurred, colourised.
        soft = ink.getchannel("A").filter(ImageFilter.GaussianBlur(7))
        tint = ImageOps.colorize(soft, black=(0, 0, 0), white=BLOOD).convert("RGBA")
        tint.putalpha(soft.point(lambda v: int(v * 0.85)))
        img.alpha_composite(tint, (26, (h - ink.height) // 2 + 2))
        img.alpha_composite(ink, (26, (h - ink.height) // 2))

        cut = slash(int(w - 52), seed=63 + i)
        img.alpha_composite(cut, (26, h - 30 - (2 if i else 0)))
        frames.append(("%s white%04d" % (option, i), img))

    return frames


def write_atlas(option, frames):
    """Sparrow atlas: frames packed into a vertical strip, one XML to describe it."""
    pad = 2
    width = max(f.width for _, f in frames) + pad * 2
    height = sum(f.height for _, f in frames) + pad * 2 * len(frames)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    y = pad
    entries = []
    for name, img in frames:
        sheet.alpha_composite(img, (pad, y))
        entries.append((name, pad, y, img.width, img.height))
        y += img.height + pad * 2

    png = os.path.join(MAINMENU, option + ".png")
    xml = os.path.join(MAINMENU, option + ".xml")
    sheet.save(png)
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<TextureAtlas imagePath="%s.png">' % option]
    for name, x, fy, w, h in entries:
        lines.append('\t<SubTexture name="%s" x="%d" y="%d" width="%d" height="%d"/>'
                     % (name, x, fy, w, h))
    lines.append("</TextureAtlas>")
    with open(xml, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return png, xml


# --------------------------------------------------------------------------- #
# backdrop
# --------------------------------------------------------------------------- #

def atlas_frame(path, prefix):
    """Pull one character frame out of a Sparrow atlas by animation prefix."""
    sheet = Image.open(path + ".png").convert("RGBA")
    root = ET.parse(path + ".xml").getroot()
    for node in root.iter("SubTexture"):
        name = node.get("name") or ""
        if not name.startswith(prefix):
            continue
        x, y = int(node.get("x")), int(node.get("y"))
        w, h = int(node.get("width")), int(node.get("height"))
        return sheet.crop((x, y, x + w, y + h))
    raise SystemExit("no %r frame in %s.xml" % (prefix, path))


def lurker(target_h):
    """The Trollge, standing in the dark: silhouette plus the only lit pixels.

    The dark parts are flattened to almost nothing; whatever the sprite still
    emits (eyes, mouth, the shine of the mask) survives as a dim red glow, so
    the figure reads as *watching* rather than as a character standing around.
    """
    frame = atlas_frame(os.path.join(CHARS, "Trollge_final"), "TrollgeF idle0000")
    w = int(frame.width * (target_h / frame.height))
    frame = frame.resize((w, target_h), Image.LANCZOS)
    alpha = frame.getchannel("A")

    # Silhouette: keep the shape, throw away the light.
    silhouette = Image.new("RGBA", frame.size, (3, 2, 5, 0))
    silhouette.putalpha(alpha.point(lambda v: int(v * 0.97)))

    # Emissive: brightest pixels only, tinted blood and bloomed.
    grey = frame.convert("L")
    hot = grey.point(lambda v: 0 if v < 122 else min(255, (v - 122) * 3))
    hot = ImageChops.multiply(hot, alpha)
    eyes = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    eyes.putalpha(hot.point(lambda v: int(v * 0.82)))
    tinted = Image.new("RGBA", frame.size, (206, 48, 42, 255))
    tinted.putalpha(eyes.getchannel("A"))
    bloom = Image.new("RGBA", frame.size, (150, 16, 24, 0))
    bloom.putalpha(hot.filter(ImageFilter.GaussianBlur(11)).point(lambda v: int(v * 0.62)))

    out = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    out.alpha_composite(bloom)
    out.alpha_composite(silhouette)
    out.alpha_composite(tinted)
    return out


def make_backdrop():
    """menus/menuBG: the scary stage, defocused, gritted up, with something in it."""
    src = Image.open(os.path.join(STAGES, "bg_scary.png")).convert("RGB")
    bg = src.resize((BG_W, BG_H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3.2))

    # A figure standing in the dark of the hallway, bottom-right, out of focus so
    # it reads as depth rather than as a menu sprite.
    figure = lurker(int(BG_H * 0.82))
    figure = figure.filter(ImageFilter.GaussianBlur(1.3))
    figure.putalpha(figure.getchannel("A").point(lambda v: int(v * 0.9)))
    bg = bg.convert("RGBA")
    bg.alpha_composite(figure, (BG_W - figure.width - 36, BG_H - figure.height + 26))

    # Horizontal shade: heavy on the left where the type sits, lighter right.
    grad = Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(BG_W):
        t = x / float(BG_W)
        gd.line((x, 0, x, BG_H), fill=(4, 3, 6, int(150 - 70 * t)))
    bg = Image.alpha_composite(bg, grad)

    # Deeper vignette than before: the corners are where the dread lives.
    vign = Image.new("L", (BG_W, BG_H), 0)
    vd = ImageDraw.Draw(vign)
    vd.ellipse((-BG_W * 0.18, -BG_H * 0.22, BG_W * 1.18, BG_H * 1.22), fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(110))
    dark = Image.new("RGBA", (BG_W, BG_H), (2, 1, 3, 235))
    bg = Image.composite(bg, dark, vign)

    # CRT scanlines, every other row, plus a slow rolling band.
    lines = Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for y in range(0, BG_H, 3):
        ld.line((0, y, BG_W, y), fill=(0, 0, 0, 34))
    ld.rectangle([0, int(BG_H * 0.42), BG_W, int(BG_H * 0.42) + 54], fill=(255, 255, 255, 5))
    bg = Image.alpha_composite(bg, lines)

    # Analog grain: fine noise, then a second, coarser pass so it survives JPEG.
    grain = Image.effect_noise((BG_W, BG_H), 26).convert("L")
    grain = grain.filter(ImageFilter.GaussianBlur(0.35))
    grain_layer = Image.new("RGBA", (BG_W, BG_H), (255, 255, 255, 255))
    grain_layer.putalpha(grain.point(lambda v: int(abs(v - 128) * 0.55)))
    bg = Image.alpha_composite(bg, grain_layer)

    # A last dark pass over the grain: keeps the noise from lifting the blacks.
    bg = Image.alpha_composite(bg, Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 26)))

    out = os.path.join(MENUS, "menuBG.png")
    # Grain is incompressible, so spend the cycles: level 9 keeps the file around
    # a third of the default size without touching the look.
    bg.convert("RGB").save(out, optimize=True, compress_level=9)
    return out


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #

def make_preview(frames_by_option):
    """docs/menu_preview.png: the menu as it will look, for the README."""
    bg = Image.open(os.path.join(MENUS, "menuBG.png")).convert("RGBA")
    canvas = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
    canvas.alpha_composite(bg.resize((1280, 720), Image.LANCZOS), (0, 0))

    for i, (option, label) in enumerate(OPTIONS):
        frames = frames_by_option[option]
        # Mirror MainMenuState: 60 + i * 160, horizontally centred, first selected.
        img = frames[2][1] if i == 0 else frames[0][1]
        canvas.alpha_composite(img, ((1280 - img.width) // 2, 60 + i * 160))

    d = ImageDraw.Draw(canvas)
    foot = ImageFont.truetype(FONT_BOLD, 18)
    draw_tracked(d, 12, 690, "UP / DOWN  CHOOSE        ENTER  SELECT        [MODS]  SWITCH MOD",
                 foot, (168, 162, 172, 255), 2)

    out = os.path.join(DOCS, "menu_preview.png")
    canvas.convert("RGB").save(out)
    return out


def make():
    os.makedirs(MAINMENU, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    wrote = []

    frames_by_option = {}
    for option, label in OPTIONS:
        frames = button_frames(option, label)
        frames_by_option[option] = frames
        png, xml = write_atlas(option, frames)
        wrote += [png, xml]

    wrote.append(make_backdrop())
    wrote.append(make_preview(frames_by_option))
    return wrote


def main():
    for path in make():
        print("  -> %s" % os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
