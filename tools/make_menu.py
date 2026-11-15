#!/usr/bin/env python3
"""
The mod's own menus.

Two jobs, both of them art, because art cannot crash:

  * `images/menus/mainmenu/{story mode,freeplay,options,credits}.png|.xml`
    -- the four buttons `MainMenuState` builds from
    `Paths.getFrames('menus/mainmenu/<option>')` with animations
    `<option> basic` (idle) and `<option> white` (selected).
  * `images/menus/menuBG.png` -- the backdrop `MainMenuState` loads as
    `menus/menuBG` (1286x730, single frame; `loadAnimatedGraphic` accepts a
    plain PNG and gives it one frame).

`data/config/modpack.ini` then sends the boot straight here:

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

import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
MENUS = os.path.join(MOD, "images", "menus")
MAINMENU = os.path.join(MENUS, "mainmenu")
STAGES = os.path.join(MOD, "images", "stages", "trollge")
DOCS = os.path.join(ROOT, "docs")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

#: Engine geometry, copied from MainMenuState.hx: items sit at
#: `60 + i * 160`, idle frames are ~122 px tall, selected ones ~172.
BG_W, BG_H = 1286, 730
IDLE_H = 122
SELECTED_H = 172

BONE = (238, 232, 236)
BLOOD = (196, 16, 30)
ASH = (146, 140, 150)
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
# text helpers
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


def glow_pass(text, font, tracking, colour, blur, alpha):
    """Soft bloom behind a label, sized to the text itself."""
    w = int(round(tracked(text, font, tracking))) + blur * 4
    h = font.getbbox(text)[3] + font.getbbox(text)[1] + blur * 4
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_tracked(ImageDraw.Draw(layer), blur * 2, blur * 2, text, font, colour + (alpha,), tracking)
    return layer.filter(ImageFilter.GaussianBlur(blur))


# --------------------------------------------------------------------------- #
# buttons
# --------------------------------------------------------------------------- #

def button_frames(option, label):
    """Idle + selected frames for one menu item, as (name, image) pairs."""
    frames = []

    idle_font = ImageFont.truetype(FONT_BOLD, IDLE_H - 18)
    sel_font = ImageFont.truetype(FONT_BOLD, SELECTED_H - 26)

    for i in range(2):
        # Idle: ash-grey, flat, with the faintest dark edge so it survives a
        # busy backdrop. Two near-identical frames keep the 24 fps animation
        # from looking frozen.
        flick = 0 if i == 0 else 6
        font = idle_font
        tracking = 3
        w = int(round(tracked(label, font, tracking))) + 24
        h = IDLE_H
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        base = tuple(min(255, c + flick) for c in ASH)
        y = (h - font.getbbox(label)[3]) // 2 - 8
        # Dark drop shadow first, then the fill on top of it: an idle item reads
        # as carved into the backdrop instead of floating over it.
        draw_tracked(d, 15, y + 4, label, font, (4, 3, 6, 210), tracking)
        draw_tracked(d, 12, y, label, font, base + (255,), tracking)
        frames.append(("%s basic%04d" % (option, i), img))

    for i in range(2):
        # Selected: bone-white with a blood bloom and a thin underline, twice as
        # loud as idle so the cursor never has to be explained.
        font = sel_font
        tracking = 4
        w = int(round(tracked(label, font, tracking))) + 48
        h = SELECTED_H
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        bloom = glow_pass(label, font, tracking, BLOOD, 7, 150 if i == 0 else 185)
        img.alpha_composite(bloom, (24 - bloom.width // 2 + int(tracked(label, font, tracking)) // 2,
                                    h // 2 - bloom.height // 2))
        d = ImageDraw.Draw(img)
        y = (h - font.getbbox(label)[3]) // 2 - 10
        draw_tracked(d, 24, y, label, font, BONE + (255,), tracking)
        d.rectangle((24, h - 26, 24 + int(tracked(label, font, tracking)), h - 21), fill=BLOOD + (235,))
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

def make_backdrop():
    """menus/menuBG: the scary stage, defocused and graded, sized for the menu."""
    src = Image.open(os.path.join(STAGES, "bg_scary.png")).convert("RGB")
    bg = src.resize((BG_W, BG_H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(3.2))

    # Darken the middle-right, where the buttons land, without flattening the
    # whole frame: a horizontal gradient plus a vignette.
    shade = Image.new("L", (BG_W, BG_H))
    px = shade.load()
    for x in range(BG_W):
        for y in range(0, BG_H, 1):
            px[x, y] = 0
    grad = Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(BG_W):
        alpha = int(90 + 110 * (x / BG_W))
        gd.line((x, 0, x, BG_H), fill=(6, 4, 8, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), grad)

    vign = Image.new("L", (BG_W, BG_H), 0)
    vd = ImageDraw.Draw(vign)
    vd.ellipse((-BG_W * 0.25, -BG_H * 0.30, BG_W * 1.25, BG_H * 1.30), fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", (BG_W, BG_H), (3, 2, 4, 190))
    bg = Image.composite(bg, dark, vign)

    # Scanlines + grain: the same CRT tell the in-game grade uses.
    lines = Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for y in range(0, BG_H, 3):
        ld.line((0, y, BG_W, y), fill=(0, 0, 0, 26))
    bg = Image.alpha_composite(bg, lines)

    out = os.path.join(MENUS, "menuBG.png")
    bg.convert("RGB").save(out)
    return out


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #

def make_preview(frames_by_option):
    """docs/menu_preview.png: the menu as it will look, for the README."""
    bg = Image.open(os.path.join(MENUS, "menuBG.png")).convert("RGBA")
    canvas = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
    canvas.alpha_composite(bg.resize((1280, 720), Image.LANCZOS), (0, 0))

    d = ImageDraw.Draw(canvas)
    for i, (option, label) in enumerate(OPTIONS):
        frames = frames_by_option[option]
        # Mirror MainMenuState: 60 + i * 160, horizontally centred, and the
        # first item is the selected one.
        img = frames[2][1] if i == 0 else frames[0][1]
        x = (1280 - img.width) // 2
        y = 60 + i * 160
        canvas.alpha_composite(img, (x, y))

    foot = ImageFont.truetype(FONT_BOLD, 18)
    draw_tracked(d, 12, 690, "UP / DOWN  CHOOSE        ENTER  SELECT        [MODS]  SWITCH MOD", foot,
                 (168, 162, 172, 255), 2)

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
