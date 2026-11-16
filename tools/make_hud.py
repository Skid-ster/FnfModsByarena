#!/usr/bin/env python3
"""
HUD art: the health bar frame and the READY / SET / GO countdown.

Codename Engine looks these up by fixed names, so shipping them in the mod is
enough to reskin the HUD:

    images/game/healthBar.png   PlayState.hx -> loadAnimatedGraphic('game/healthBar')
                                (a FlxBar is drawn 4 px inside this frame)
    images/game/ready.png       Flags.DEFAULT_INTRO_SPRITES = [null, 'game/ready',
    images/game/set.png                                    'game/set', 'game/go']
    images/game/go.png

Run with:  python3 tools/make_hud.py
"""

import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DOCS = os.path.join(ROOT, "docs")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BAR_W, BAR_H = 760, 34
BADGE_W, BADGE_H = 420, 180

INK = (12, 10, 16)
METAL = (58, 52, 64)
METAL_LIGHT = (104, 96, 116)
BLOOD = (196, 16, 30)
BONE = (238, 232, 236)


def out(path):
    full = os.path.join(MOD, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


def save(image, path):
    full = out(path)
    image.save(full, optimize=True)
    print("  -> %-40s %s" % (path, image.size))
    return full


# --------------------------------------------------------------------------- #

def build_health_bar():
    image = Image.new("RGBA", (BAR_W, BAR_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # steel slab, then the dark interior the FlxBar fill sits in
    draw.rectangle([0, 0, BAR_W - 1, BAR_H - 1], fill=METAL + (255,))
    draw.rectangle([5, 5, BAR_W - 6, BAR_H - 6], fill=INK + (255,))
    for y in range(7, BAR_H - 7, 3):
        draw.line([(7, y), (BAR_W - 8, y)], fill=(20, 18, 26, 255))

    # blood-red inner shadow so the empty part still reads as Trollge
    for inset, alpha in ((6, 110), (7, 70), (8, 40)):
        draw.rectangle([inset, inset, BAR_W - 1 - inset, BAR_H - 1 - inset],
                       outline=(168, 14, 26, alpha), width=1)

    # edges: black outline, light top bevel, dark bottom
    draw.rectangle([0, 0, BAR_W - 1, BAR_H - 1], outline=(12, 10, 14, 255), width=3)
    draw.line([(4, 3), (BAR_W - 5, 3)], fill=METAL_LIGHT + (255,), width=2)
    draw.line([(4, BAR_H - 4), (BAR_W - 5, BAR_H - 4)], fill=(26, 22, 30, 255), width=2)

    # rivets
    for x in (11, BAR_W - 14):
        for y in (10, BAR_H - 13):
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=METAL_LIGHT + (255,),
                         outline=(10, 8, 12, 255))
            draw.ellipse([x - 2, y - 3, x + 1, y], fill=(150, 142, 164, 255))
    return image


def badge_text(word, glitch=0, seed=0):
    """One countdown badge: chunky word, red offset copy, glitch slices."""
    image = Image.new("RGBA", (BADGE_W, BADGE_H), (0, 0, 0, 0))
    text_layer = Image.new("RGBA", (BADGE_W, BADGE_H), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    # Leave room for stroke, shadow and glitch displacement: READY used to
    # exceed the frame width and its first and last letters were clipped.
    font_size = 128
    font = ImageFont.truetype(FONT_BOLD, font_size)
    box = td.textbbox((0, 0), word, font=font)
    while box[2] - box[0] > BADGE_W - 64 and font_size > 24:
        font_size -= 1
        font = ImageFont.truetype(FONT_BOLD, font_size)
        box = td.textbbox((0, 0), word, font=font)
    x = (BADGE_W - (box[2] - box[0])) / 2 - box[0]
    y = (BADGE_H - (box[3] - box[1])) / 2 - box[1]

    # hard shadow, then the word itself with a thick dark outline
    td.text((x + 7, y + 9), word, font=font, fill=(0, 0, 0, 220))
    td.text((x + 3, y + 4), word, font=font, fill=BLOOD + (255,))
    td.text((x, y), word, font=font, fill=BONE + (255,), stroke_width=6, stroke_fill=(14, 12, 18, 255))

    if glitch:
        rng = random.Random(seed)
        for _ in range(glitch):
            band_y = rng.randrange(0, BADGE_H - 4)
            band_h = rng.randint(2, 9)
            shift = rng.randint(-22, 22)
            band = text_layer.crop((0, band_y, BADGE_W, band_y + band_h))
            text_layer.paste(band, (shift, band_y))
        tint = Image.new("RGBA", (BADGE_W, BADGE_H), (0, 0, 0, 0))
        tint_d = ImageDraw.Draw(tint)
        for _ in range(40):
            gy = rng.randrange(BADGE_H)
            tint_d.line([(0, gy), (BADGE_W, gy)], fill=(255, 40, 60, rng.randint(10, 45)))

    image.alpha_composite(text_layer)

    # red halo behind the word
    halo = Image.new("RGBA", (BADGE_W, BADGE_H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.text((x, y), word, font=font, fill=BLOOD + (255,))
    halo = halo.filter(ImageFilter.GaussianBlur(9))
    result = Image.new("RGBA", (BADGE_W, BADGE_H), (0, 0, 0, 0))
    result.alpha_composite(halo)
    result.alpha_composite(image)
    return result


def build_countdown():
    badges = [
        ("READY", 4, 11, "ready"),
        ("SET", 8, 22, "set"),
        ("GO", 14, 33, "go"),
    ]
    made = []
    for word, glitch, seed, name in badges:
        image = badge_text(word, glitch, seed)
        made.append(image)
        save(image, "images/game/%s.png" % name)
    return made


def build_preview(bar, badges):
    scale = 0.55
    pad = 18
    bar_h = bar.height
    badge_h = int(max(b.height for b in badges) * scale)
    width = bar.width + pad * 2
    height = bar_h + badge_h + pad * 3
    canvas = Image.new("RGBA", (int(width), int(height)), (20, 16, 22, 255))
    canvas.alpha_composite(bar, (pad, pad))
    x = pad
    for badge in badges:
        thumb = badge.resize((int(badge.width * scale), int(badge.height * scale)), Image.LANCZOS)
        canvas.alpha_composite(thumb, (int(x), int(pad * 2 + bar_h)))
        x += thumb.width + 4
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, "hud.png")
    canvas.convert("RGB").save(path, optimize=True)
    print("  -> docs/hud.png (%dx%d)" % (canvas.width, canvas.height))


def main():
    print("Drawing the health bar...")
    bar = build_health_bar()
    save(bar, "images/game/healthBar.png")
    print("Drawing the countdown...")
    badges = build_countdown()
    print("Writing docs preview...")
    build_preview(bar, badges)
    return 0


if __name__ == "__main__":
    sys.exit(main())
