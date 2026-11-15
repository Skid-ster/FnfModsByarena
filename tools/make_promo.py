#!/usr/bin/env python3
"""
The store-page hero image (`docs/banner.jpg`).

Everything in it is real mod art: the blurred cutscene frame behind the type, the
five stage backdrops in scare order along the bottom, the live HUD strip on the
right. No mock gameplay, no invented screenshots.

Run with:  python3 tools/make_promo.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DOCS = os.path.join(ROOT, "docs")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H = 1920, 1080
INK = (8, 6, 10)
BONE = (240, 236, 240)
BLOOD = (214, 24, 38)
DIM = (150, 152, 164)

#: Short labels for the thumbnail strip (the real display names are too long).
SHORT = {
    "trolling": "TROLLING",
    "getting-dark": "GETTING DARK",
    "dont-look-back": "DON'T LOOK BACK",
    "super-scary": "SUPER SCARY",
    "the-incident": "THE INCIDENT",
}

#: One backdrop per song, in scare order.
BACKDROPS = ("bg", "bg_scary", "bg_glitch", "bg_nightmare", "bg_hell")


def tracked_text(draw, xy, text, font, fill, tracking=0, anchor_left=True):
    """PIL has no letter-spacing, so draw the glyphs one at a time."""
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += draw.textlength(char, font=font) + tracking
    return x


def fit(img, size):
    ratio = max(size[0] / img.width, size[1] / img.height)
    resized = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
                         Image.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def main():
    base = Image.new("RGB", (W, H), INK)

    # Background: the song-4 backdrop, blown up and blurred, so the type reads
    # and nothing competes with it.
    backdrop = os.path.join(MOD, "images", "stages", "trollge", "bg_scary.png")
    if os.path.isfile(backdrop):
        bg = fit(Image.open(backdrop).convert("RGB"), (W, H)).filter(
            ImageFilter.GaussianBlur(9))
        bg = Image.blend(bg, Image.new("RGB", (W, H), INK), 0.55)
        base.paste(bg, (0, 0))

    # Vignette + a red core, so the frame looks lit rather than flat.
    glow = Image.new("RGB", (W, H), INK)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-500, -260, W + 500, H - 60), fill=(96, 8, 16))
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    base = Image.blend(base, glow, 0.32)

    draw = ImageDraw.Draw(base)
    title_font = ImageFont.truetype(FONT, 132)
    sub_font = ImageFont.truetype(FONT, 34)
    tag_font = ImageFont.truetype(FONT, 26)
    small_font = ImageFont.truetype(FONT, 24)

    # Title, with a hard shadow 6 px down for the poster look.
    tracked_text(draw, (116, 208 + 6), "SUPER SCARY", title_font, (0, 0, 0), 6)
    tracked_text(draw, (116, 208), "SUPER SCARY", title_font, BONE, 6)
    tracked_text(draw, (120, 352 + 6), "TROLLGE", title_font, (0, 0, 0), 8)
    tracked_text(draw, (120, 352), "TROLLGE", title_font, BLOOD, 8)

    tracked_text(draw, (124, 560), "TROLLGE WEEK  //  5 SONGS  //  3 DIFFICULTIES",
                 sub_font, BONE, 2)
    tracked_text(draw, (124, 610), "CUTSCENES WITH DIALOGUE   ·   AN ENDING   ·   SINGABLE VOCALS",
                 small_font, DIM, 1)
    tracked_text(draw, (124, 650), "CODENAME ENGINE  ·  v%s" % _version(), tag_font, BLOOD, 1)

    # The five stages, in scare order, with their rating under each.
    thumb_w, thumb_h = 316, 178
    gap = 18
    total = len(L.SONGS) * thumb_w + (len(L.SONGS) - 1) * gap
    x = (W - total) // 2
    y = 760
    for song, backdrop in zip(L.SONGS, BACKDROPS):
        path = os.path.join(MOD, "images", "stages", "trollge", backdrop + ".png")
        if not os.path.isfile(path):
            continue
        art = fit(Image.open(path).convert("RGB"), (thumb_w, thumb_h))
        base.paste(art, (x, y))
        draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h - 1), outline=(60, 40, 44), width=2)
        draw.rectangle((x, y + thumb_h - 34, x + thumb_w - 1, y + thumb_h - 1),
                       fill=(0, 0, 0))
        # Name on the left, rating as a pill in the corner: long titles and the
        # score must never collide.
        label = "%d. %s" % (L.SONGS.index(song) + 1, SHORT.get(song["id"], song["display"].upper()))
        while draw.textlength(label, font=small_font) > thumb_w - 24 and len(label) > 4:
            label = label[:-2]
        draw.text((x + 10, y + thumb_h - 29), label, font=small_font, fill=BONE)
        score = "%d/10" % song["scare"]
        pill_w = draw.textlength(score, font=small_font) + 20
        draw.rectangle((x + thumb_w - pill_w - 10, y + 8, x + thumb_w - 10, y + 42),
                       fill=(0, 0, 0))
        draw.rectangle((x + thumb_w - pill_w - 10, y + 8, x + thumb_w - 10, y + 42),
                       outline=BLOOD, width=2)
        draw.text((x + thumb_w - pill_w, y + 12), score, font=small_font, fill=BLOOD)
        x += thumb_w + gap

    draw.rectangle((0, H - 6, W, H), fill=BLOOD)

    out = os.path.join(DOCS, "banner.jpg")
    base.save(out, quality=92)
    print("-> %s" % os.path.relpath(out, ROOT))


def _version():
    import json
    with open(os.path.join(MOD, "mod.json"), encoding="utf-8") as handle:
        return json.load(handle)["version"]


if __name__ == "__main__":
    main()
