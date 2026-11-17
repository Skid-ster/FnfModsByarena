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
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DOCS = os.path.join(ROOT, "docs")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

BAR_W, BAR_H = 760, 34
BADGE_W, BADGE_H = 420, 180



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
    """Casing only: the engine's FlxBar covers the inset from (4,4)."""
    image = Image.new("RGBA", (BAR_W, BAR_H), (10, 9, 14, 255))
    d = ImageDraw.Draw(image)
    # Only the outer four pixels are guaranteed to remain visible in PlayState.
    d.rectangle((0, 0, BAR_W - 1, BAR_H - 1), outline=(14, 11, 16, 255), width=1)
    d.rectangle((1, 1, BAR_W - 2, BAR_H - 2), outline=(117, 100, 104, 255), width=1)
    d.line((3, 2, BAR_W - 4, 2), fill=(196, 151, 142, 255))
    d.line((3, BAR_H - 3, BAR_W - 4, BAR_H - 3), fill=(74, 51, 59, 255))
    for x in range(16, BAR_W - 16, 32):
        d.line((x, 1, x + 4, 1), fill=(210, 169, 153, 255))
    return image


def badge_text(word):
    """Readable countdown placard. Distress belongs on the casing, not letters."""
    image = Image.new("RGBA", (BADGE_W, BADGE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    # Identical silhouettes for all three words prevent visual jumps.
    d.polygon([(9, 12), (BADGE_W - 32, 12), (BADGE_W - 9, 35),
               (BADGE_W - 9, BADGE_H - 12), (9, BADGE_H - 12)],
              fill=(12, 11, 16, 247))
    d.line([(9, BADGE_H - 12), (9, 12), (BADGE_W - 32, 12),
            (BADGE_W - 9, 35), (BADGE_W - 9, BADGE_H - 12),
            (9, BADGE_H - 12)], fill=(172, 126, 121, 255), width=2)
    d.rectangle((10, 13, 15, BADGE_H - 13), fill=(206, 73, 69, 255))
    d.text((28, 22), 'INCOMING  /  SIGNAL',
           font=ImageFont.truetype(FONT_MONO, 14), fill=(197, 175, 165, 255))
    d.line((28, 48, BADGE_W - 29, 48), fill=(94, 78, 82, 255), width=1)
    font_size = 94
    font = ImageFont.truetype(FONT_BOLD, font_size)
    while d.textbbox((0, 0), word, font=font, stroke_width=1)[2] > BADGE_W - 80:
        font_size -= 1
        font = ImageFont.truetype(FONT_BOLD, font_size)
    left, top, right, bottom = d.textbbox((0, 0), word, font=font, stroke_width=1)
    x = (BADGE_W - (right - left)) / 2 - left
    y = 54 + (88 - (bottom - top)) / 2 - top
    d.text((x, y), word, font=font, fill=(250, 240, 229, 255),
           stroke_width=1, stroke_fill=(6, 5, 8, 255))
    for x in range(28, 122, 12):
        d.line((x, BADGE_H - 22, x + 6, BADGE_H - 22), fill=(153, 82, 78, 255), width=2)
    return image


def build_countdown():
    badges = [
        ("READY", "ready"),
        ("SET", "set"),
        ("GO", "go"),
    ]
    made = []
    for word, name in badges:
        image = badge_text(word)
        made.append(image)
        save(image, "images/game/%s.png" % name)
    return made


def build_preview(bar, badges):
    """An asset mock, not an engine screenshot; draw the FlxBar over its inset."""
    pad = 18
    canvas = Image.new("RGBA", (BAR_W + pad * 2, 188), (20, 16, 22, 255))
    simulated = bar.copy()
    d = ImageDraw.Draw(simulated)
    d.rectangle((4, 4, BAR_W // 2 - 1, BAR_H - 5), fill=(104, 30, 39, 255))
    d.rectangle((BAR_W // 2, 4, BAR_W - 5, BAR_H - 5), fill=(42, 124, 150, 255))
    canvas.alpha_composite(simulated, (pad, pad))
    for i, badge in enumerate(badges):
        thumb = badge.resize((231, 99), Image.Resampling.LANCZOS)
        canvas.alpha_composite(thumb, (pad + i * 249, 74))
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, "hud.png")
    canvas.convert("RGB").save(path, optimize=True)
    print("  -> docs/hud.png (%dx%d; simulated fill)" % (canvas.width, canvas.height))


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
