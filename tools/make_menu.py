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

import numpy as np
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
#: The engine's own geometry: four slots, 160 px apart, first at y=60, in a
#: 1280x720 frame. The button art keeps that geometry so `MainMenuState` can go
#: on placing items where it always has.
SLOT_TOP = 60
SLOT_PITCH = 160
PREVIEW_H = 720

#: Bone white for the selected item, ash for the idle ones. The contrast ratio
#: between these two is what makes the cursor findable in a dark room.
BONE = (242, 238, 240)
BLOOD = (196, 16, 30)
CONGEALED = (108, 10, 20)
ASH = (150, 144, 154)
DIM = (96, 92, 100)
INK = (8, 6, 10)

#: The four buttons step a little further right as they go down, and the
#: selected one steps further still: a ragged stack reads as a composition,
#: a centred list reads as a form.
INDENT = [0, 18, 36, 54]
SELECTED_BUMP = 22

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


CONDENSE = 0.84      # horizontal squeeze: DejaVu is wide; a poster face is not


def text_layer(label, font, tracking):
    """The label on its own transparent canvas, plus its ink box."""
    ascent, descent = font.getmetrics()
    w = int(math.ceil(tracked(label, font, tracking))) + 8
    h = ascent + descent + 8
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_tracked(ImageDraw.Draw(img), 4, 4, label, font, (255, 255, 255, 255), tracking)
    narrow = max(1, int(round(w * CONDENSE)))
    return img.resize((narrow, h), Image.LANCZOS)


def graded_fill(layer, top, bottom):
    """Paint a vertical gradient through a glyph mask (bone fading to ash)."""
    w, h = layer.size
    column = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = np.zeros((h, w, 4), dtype=np.uint8)
    for i, (a, b) in enumerate(zip(top, bottom)):
        px[:, :, i] = np.clip(a + (b - a) * column, 0, 255).astype(np.uint8)
    px[:, :, 3] = 255
    out = Image.fromarray(px, "RGBA")
    out.putalpha(layer.getchannel("A"))
    return out


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

    mask = chewed_alpha(ink, seed)
    body = graded_fill(ink, fill, tuple(int(c * 0.62) for c in fill))
    body.putalpha(mask)

    out = chroma(body, red=fringe, cyan=-fringe)
    out.putalpha(out.getchannel("A").point(lambda v: int(v * 0.55)))
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

    idle_font = ImageFont.truetype(FONT_BOLD, IDLE_H - 40)
    sel_font = ImageFont.truetype(FONT_BOLD, SELECTED_H - 48)

    for i in range(2):
        # Idle: ash-grey, chewed edges, faint fringing. Two near-identical frames
        # so the engine's 24 fps loop does not look frozen.
        flick = 0 if i == 0 else 7
        w = int(math.ceil(tracked(label, idle_font, 3) * CONDENSE)) + 28
        h = IDLE_H
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        base = tuple(min(255, c + flick) for c in ASH)
        ink = render_label(label, idle_font, 3, base, seed=17 + i, edge=(6, 5, 8), fringe=1)
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
        w = int(math.ceil(tracked(label, sel_font, 4) * CONDENSE)) + 60
        h = SELECTED_H
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

        ink = render_label(label, sel_font, 4, BONE, seed=41 + i, drips_on=True, fringe=1)
        # A one-pixel dark keyline: the difference between "bone type on a dark
        # hallway" and "bone type that vanishes whenever the backdrop brightens".
        key = ink.getchannel("A").filter(ImageFilter.MaxFilter(3))
        dark = Image.new("RGBA", ink.size, (10, 6, 9, 255))
        dark.putalpha(key.point(lambda v: int(v * 0.85)))
        keyed = Image.new("RGBA", ink.size, (0, 0, 0, 0))
        keyed.alpha_composite(dark)
        keyed.alpha_composite(ink)
        ink = keyed
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


def _ink(alpha, grey):
    """The drawn *line*, as a mask.

    The Trollge atlases are black ink on a white card with an opaque alpha, so
    the alpha channel is just a rectangle -- the drawing lives in the luminance.
    Ink is therefore "dark pixels", which is the opposite of what the generic
    sprite pipeline assumes.
    """
    ink = grey.point(lambda v: 255 if v < 140 else 0)
    ink = ImageChops.multiply(ink, alpha.point(lambda v: 255 if v > 32 else 0))
    # The atlases carry a thin black border around the card: left in, it grows
    # into a rectangle that frames the figure like a portrait, which is exactly
    # the artefact the first solid-mask attempt produced.
    w, h = ink.size
    inset = Image.new("L", ink.size, 0)
    ImageDraw.Draw(inset).rectangle([4, 4, w - 5, h - 5], fill=255)
    return ImageChops.multiply(ink, inset)


def _fill_silhouette(alpha):
    """Turn an outline sprite into a solid silhouette.

    The Trollge art is drawn as strokes with a hollow interior, so using its
    alpha directly as a silhouette gives a stick figure. This closes the stroke
    gaps and then floods the enclosed areas: what comes back is the *body*.
    """
    binary = alpha.point(lambda v: 255 if v > 40 else 0)
    binary = binary.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
    # Flood the outside; whatever is still unreached and was not ink is interior.
    outside = binary.copy()
    ImageDraw.floodfill(outside, (0, 0), 128)
    interior = outside.point(lambda v: 255 if v == 0 else 0)
    return ImageChops.lighter(binary, interior)


def lurker(target_h):
    """The Trollge, standing in the dark.

    Built from three passes so it reads as a *figure* and not a smudge:
      1. a solid silhouette (`_fill_silhouette`), tinted nearly black -- the mass,
      2. a rim light on the stroke edges, so the shape catches a cold light from
         the doorway on the left,
      3. the eyes and grin as the only emissive parts, bloomed.
    """
    frame = atlas_frame(os.path.join(CHARS, "Trollge_final"), "TrollgeF idle0000")
    w = int(frame.width * (target_h / frame.height))
    frame = frame.resize((w, target_h), Image.LANCZOS)
    alpha = frame.getchannel("A")
    grey = frame.convert("L")
    ink = _ink(alpha, grey)
    body_mask = _fill_silhouette(ink)

    out = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    # 1. Mass: near-black with a hint of cold violet so it is not a hole.
    mass = Image.new("RGBA", frame.size, (11, 9, 13, 255))
    mass.putalpha(body_mask)
    out.alpha_composite(mass)

    # 2. Rim light: the ink strokes themselves, lifted to a cold grey-violet so
    #    the drawing's own linework defines the shape.
    rim = Image.new("RGBA", frame.size, (150, 104, 126, 255))
    rim.putalpha(ink.filter(ImageFilter.GaussianBlur(0.7)).point(lambda v: int(v * 0.16)))
    out.alpha_composite(rim)

    # 3. Emissive: the brightest ink (eyes, teeth) only, bloomed red.
    #    The face is the only bright area of the drawing, so "bright" is the
    #    eyes and the grin inside the ink.
    #    Only the face glows: the brightest ink, restricted to the top third of
    #    the figure so a highlight on a hand cannot light up like an eye.
    head = Image.new("L", frame.size, 0)
    ImageDraw.Draw(head).rectangle([0, 0, frame.size[0], int(frame.size[1] * 0.38)], fill=255)
    face = ImageChops.multiply(ink.point(lambda v: 255 if v else 0), head)
    hot = ImageChops.multiply(grey.point(lambda v: 0 if v < 150 else min(255, (v - 150) * 3)),
                              face)
    bloom = Image.new("RGBA", frame.size, (176, 24, 30, 0))
    bloom.putalpha(hot.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.75)))
    glow = Image.new("RGBA", frame.size, (236, 76, 52, 255))
    glow.putalpha(hot.point(lambda v: min(255, int(v * 1.25))))
    out.alpha_composite(bloom)
    out.alpha_composite(glow)
    # Knock the whole figure back: it is scenery, not the subject.
    shade = Image.new("RGBA", frame.size, (0, 0, 0, 40))
    out = Image.alpha_composite(out, shade)
    out.putalpha(body_mask)
    return out


def _horizontal_fade(size, stops):
    """A per-column alpha ramp from (position, alpha) stops -- 0..1 in, 0..255 out."""
    w, h = size
    xs = np.arange(w, dtype=np.float32) / max(1.0, w - 1.0)
    positions = [p for p, _a in stops]
    alphas = [a for _p, a in stops]
    ramp = np.interp(xs, positions, alphas).astype(np.uint8)
    return Image.fromarray(np.tile(ramp, (h, 1)), "L")


def make_backdrop():
    """menus/menuBG: the scary stage, defocused, with something standing in it.

    Composition rules this follows, because the previous version broke all three:
      * the left 45% is quiet and dark, because that is where the type sits,
      * the figure is small and far down the frame, so it reads as depth rather
        than as a character waiting to sing,
      * light comes from one direction (the doorway on the left), and everything
        else is graded down, so the eye has somewhere to go.
    """
    src = Image.open(os.path.join(STAGES, "bg_scary.png")).convert("RGB")
    bg = src.resize((BG_W, BG_H), Image.LANCZOS)

    # Deeper defocus than before, and desaturated: a menu backdrop should not
    # compete with the type. Keep a little of the red hallway glow.
    bg = bg.filter(ImageFilter.GaussianBlur(5.0))
    bg = ImageOps.autocontrast(bg, cutoff=1)
    bg = Image.blend(bg, ImageOps.grayscale(bg).convert("RGB"), 0.45)
    bg = Image.new("RGB", bg.size, (10, 4, 8)).convert("RGB") if False else bg

    # Grade: cold shadows, warm/red highlights.
    r, g, b = bg.split()
    r = r.point(lambda v: int(min(255, v * 0.92 + 8)))
    g = g.point(lambda v: int(v * 0.52))
    b = b.point(lambda v: int(v * 0.62 + 6))
    bg = Image.merge("RGB", (r, g, b)).convert("RGBA")

    # The figure: small, in the far room, low in the frame, barely lit.
    figure = lurker(int(BG_H * 0.52))
    figure = figure.filter(ImageFilter.GaussianBlur(0.9))
    fx = int(BG_W * 0.735)
    fy = int(BG_H * 0.50)
    shadow = Image.new("RGBA", figure.size, (0, 0, 0, 0))
    shadow.putalpha(figure.getchannel("A").point(lambda v: int(v * 0.55)))
    bg.alpha_composite(shadow, (fx + 10, fy + 14))
    bg.alpha_composite(figure, (fx, fy))

    # Left-to-right shade: the type column goes almost black, the figure stays
    # legible. This is a straight alpha ramp rather than a blurred ellipse so the
    # falloff is predictable at every resolution.
    shade = Image.new("RGBA", (BG_W, BG_H), (4, 3, 6, 255))
    shade.putalpha(_horizontal_fade((BG_W, BG_H),
                                    [(0.00, 236), (0.34, 210), (0.55, 150),
                                     (0.78, 96), (1.00, 82)]))
    bg = Image.alpha_composite(bg, shade)

    # Vignette, elliptical, soft.
    vign = Image.new("L", (BG_W, BG_H), 0)
    vd = ImageDraw.Draw(vign)
    vd.ellipse((-BG_W * 0.24, -BG_H * 0.30, BG_W * 1.24, BG_H * 1.30), fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(120))
    bg = Image.composite(bg, Image.new("RGBA", (BG_W, BG_H), (2, 1, 3, 255)), vign)

    # A cold doorway glow behind the type side, so the left is not just a void.
    glow = Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-BG_W * 0.10, BG_H * 0.10, BG_W * 0.30, BG_H * 0.92],
               fill=(120, 30, 40, 46))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    bg = Image.alpha_composite(bg, glow)

    # CRT scanlines, subtle; the shader does the rest at runtime.
    lines = Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for y in range(0, BG_H, 3):
        ld.line((0, y, BG_W, y), fill=(0, 0, 0, 26))
    bg = Image.alpha_composite(bg, lines)

    # Grain: fine, low amplitude. This is incompressible, so keep it honest
    # rather than heavy -- the shader adds the live grain.
    grain = Image.effect_noise((BG_W, BG_H), 18).convert("L")
    grain = grain.filter(ImageFilter.GaussianBlur(0.4))
    grain_layer = Image.new("RGBA", (BG_W, BG_H), (255, 255, 255, 255))
    grain_layer.putalpha(grain.point(lambda v: int(abs(v - 128) * 0.40)))
    bg = Image.alpha_composite(bg, grain_layer)

    out = os.path.join(MENUS, "menuBG.png")
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
        # Mirror MainMenuState's slots (60 + i * 160) plus the ragged indent the
        # button art itself carries, so the preview matches what the engine draws.
        img = frames[2][1] if i == 0 else frames[0][1]
        bump = SELECTED_BUMP if i == 0 else 0
        x = (1280 - img.width) // 2 + INDENT[i] + bump
        canvas.alpha_composite(img, (x, 60 + i * 160))

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
