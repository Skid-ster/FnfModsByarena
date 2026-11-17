#!/usr/bin/env python3
"""
Builds every image asset of the Super Scary Trollge mod.

The *characters* are hand-drawn art imported by `tools/make_characters.py`
(see `art_src/bf/` and `art_src/trollge/`). This script builds everything else
in code: the three stage backdrops (graded up from `art_src/scary_bg.png`), the
VHS overlays used by the story events, the story-menu week banner, and the
documentation previews.

Outputs:
    images/stages/trollge/bg.png              tier 1 (2/10)
    images/stages/trollge/bg_scary.png        tier 2 (4/10)
    images/stages/trollge/bg_nightmare.png    tier 3 (7/10)
    images/trollge_static.png                 CRT static overlay
    images/trollge_distortion.png             glitch bars overlay
    images/trollge_invert.png                 corrupted-frame overlay
    images/menus/storymenu/weeks/trollge_week.png
    docs/stages.png, docs/jumpscare.png       documentation previews

Run with:  python3 tools/make_art.py
"""

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "art_src")
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
IMG = os.path.join(MOD, "images")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BG_W, BG_H = 1280, 720


def out(path):
    full = os.path.join(IMG, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


def save(image, path):
    full = out(path)
    image.save(full, optimize=True)
    print("  -> images/%-42s %s" % (path, image.size))
    return full


# --------------------------------------------------------------------------- #
# Grading helpers
# --------------------------------------------------------------------------- #

def vignette(image, strength=0.7):
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([-w * 0.22, -h * 0.22, w * 1.22, h * 1.22], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w // 7))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(image, Image.blend(image, dark, strength), mask)


def grain(image, amount=0.06, seed=0):
    noise = Image.frombytes("L", image.size, random.Random(seed).randbytes(image.width * image.height))
    noise = noise.point(lambda v: int(abs(v - 128) * amount))
    tinted = Image.merge("RGB", (noise, noise, noise))
    return ImageChops.add(image.convert("RGB"), tinted)


def rgb_split(image, amount=8):
    r, g, b = image.convert("RGB").split()
    return Image.merge(
        "RGB", (ImageChops.offset(r, amount, 0), g, ImageChops.offset(b, -amount, 0))
    )


def scanlines(image, period=4, strength=26):
    w, h = image.size
    lines = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(lines)
    for y in range(0, h, period):
        d.line([(0, y), (w, y)], fill=strength)
    return ImageChops.subtract(image.convert("RGB"), Image.merge("RGB", (lines, lines, lines)))


# --------------------------------------------------------------------------- #
# Trollge art
# --------------------------------------------------------------------------- #

def head_crop(frame, size=150, top=0.01, bottom=0.45):
    """Square crop around the head, so health icons fill their frame."""
    w, h = frame.size
    cx = w // 2
    box_h = int(h * bottom) - int(h * top)
    box = (cx - box_h // 2, int(h * top), cx + box_h // 2, int(h * top) + box_h)
    face = frame.crop(box)
    face.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(face, ((size - face.width) // 2, (size - face.height) // 2))
    return canvas




def build_week_banner(face_image):
    w, h = 359, 89
    banner = Image.new("RGBA", (w, h), (10, 5, 7, 255))
    grad = Image.new("L", (w, h))
    gd = ImageDraw.Draw(grad)
    for yy in range(h):
        gd.line([(0, yy), (w, yy)], fill=int(90 * (1 - yy / h)) + 16)
    banner = Image.composite(Image.new("RGBA", (w, h), (122, 10, 24, 255)), banner, grad)

    face = face_image.convert("RGBA").resize((84, 84), Image.LANCZOS)
    banner.alpha_composite(face, (w - 90, 3))

    draw = ImageDraw.Draw(banner)
    big = ImageFont.truetype(FONT_BOLD, 27)
    small = ImageFont.truetype(FONT_BOLD, 12)
    draw.text((11, 10), "SUPER SCARY", font=small, fill=(255, 196, 196, 255))
    draw.text((12, 26), "TROLLGE", font=big, fill=(196, 16, 30, 255))
    draw.text((11, 25), "TROLLGE", font=big, fill=(255, 255, 255, 255))
    save(banner, "menus/storymenu/weeks/trollge_week.png")



def build_scare_art():
    """VHS overlays used by the story events.

    The jumpscare still itself is built from the imported Trollge art (see
    `tools/make_characters.py`); these three are procedural textures.
    """
    rng = random.Random(20771)

    # --- CRT static: additive, grey noise with faint horizontal tearing -----
    noise = Image.new("L", (BG_W, BG_H))
    px = noise.load()
    for yy in range(BG_H):
        row_shift = int(18 * math.sin(yy / 9.0) + rng.uniform(-6, 6))
        for xx in range(BG_W):
            px[xx, yy] = max(0, min(255, int(rng.gauss(120, 55)) + row_shift))
    noise = noise.filter(ImageFilter.GaussianBlur(0.6))
    static = Image.merge("RGBA", (noise, noise, noise, noise.point(lambda v: int(v * 0.82))))
    save(static, "trollge_static.png")

    # --- Glitch bars: transparent except for hard displacement bands --------
    glitch = Image.new("RGBA", (BG_W, BG_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glitch)
    y = 0
    while y < BG_H:
        band = rng.randint(6, 34)
        if rng.random() < 0.55:
            tint = rng.choice([(255, 40, 70), (40, 220, 255), (255, 255, 255)])
            gd.rectangle([0, y, BG_W, y + band],
                         fill=(tint[0], tint[1], tint[2], rng.randint(24, 96)))
        y += band + rng.randint(4, 26)
    for _ in range(90):
        gy = rng.randrange(BG_H)
        height = rng.randint(1, 5)
        offset = rng.randint(-160, 160)
        strip = glitch.crop((0, gy, BG_W, gy + height))
        glitch.paste(strip, (offset, gy))
    save(glitch, "trollge_distortion.png")

    # --- Inverted reality: a damaged negative of the actual battle room. ----
    # The old near-opaque purple noise hid both the notes and the environment.
    # Retain the negative image as a fleeting, translucent visual interruption.
    room = Image.open(os.path.join(SRC, "scary_bg.png")).convert("RGB").resize(
        (BG_W, BG_H), Image.LANCZOS)
    negative = ImageOps.invert(ImageOps.grayscale(room))
    inv = ImageOps.colorize(negative, black=(12, 5, 20), white=(170, 100, 154))
    inv = ImageEnhance.Contrast(inv).enhance(1.12)
    inv = rgb_split(inv, 5)
    inv = scanlines(inv, 4, 16)
    # Sparse, seeded tracking errors, leaving the middle readable.
    draw = ImageDraw.Draw(inv)
    for _ in range(12):
        y = rng.randrange(BG_H)
        x = rng.randrange(BG_W)
        length = rng.randint(25, 140)
        draw.line((x, y, min(BG_W - 1, x + length), y), fill=(183, 90, 128), width=1)
    inverted = inv.convert("RGBA")
    inverted.putalpha(Image.new("L", (BG_W, BG_H), 192))
    save(inverted, "trollge_invert.png")



def build_backgrounds():
    src = Image.open(os.path.join(SRC, "scary_bg.png")).convert("RGB").resize((BG_W, BG_H), Image.LANCZOS)

    # Tier 1 -- 2/10: dark, quiet, barely wrong.
    tier1 = ImageEnhance.Brightness(src).enhance(0.72)
    tier1 = ImageEnhance.Contrast(tier1).enhance(1.05)
    tier1 = vignette(tier1, 0.55)
    save(tier1.convert("RGBA"), "stages/trollge/bg.png")
    save(tier1.convert("RGB"), "trollge_scary_bg.png")

    # Tier 2 -- 4/10: red light bleeding in, grain, scanlines.
    tier2 = ImageEnhance.Color(src).enhance(1.35)
    red = Image.new("RGB", src.size, (120, 6, 14))
    tier2 = Image.blend(tier2, ImageChops.add(tier2, red), 0.4)
    tier2 = ImageEnhance.Brightness(tier2).enhance(0.85)
    tier2 = scanlines(tier2, 5, 14)
    tier2 = grain(tier2, 0.05, seed=4004)
    tier2 = vignette(tier2, 0.6)
    save(tier2.convert("RGBA"), "stages/trollge/bg_scary.png")

    # Tier 3 -- 6/10: the room starts double-exposing on itself.
    tier3 = ImageEnhance.Color(src).enhance(1.55)
    tier3 = ImageChops.add(tier3, Image.new("RGB", src.size, (0, 60, 70)), scale=1.0, offset=-40)
    shifted = ImageChops.offset(tier3, 22, 0)
    tier3 = Image.blend(tier3, shifted, 0.35)
    # Seeded on purpose: an unseeded `random` here made bg_glitch.png (and every
    # preview that composites it) different on every run, so the shipped art was
    # not reproducible from tools/.
    bands = random.Random(6006)
    for _ in range(26):                     # hard displacement bands
        y0 = bands.randrange(BG_H)
        band = bands.randint(4, 22)
        dx = bands.randint(-90, 90)
        strip = tier3.crop((0, y0, BG_W, min(BG_H, y0 + band)))
        tier3.paste(strip, (dx, y0))
    tier3 = scanlines(tier3, 4, 22)
    tier3 = grain(tier3, 0.08, seed=6006)
    tier3 = vignette(tier3, 0.68)
    save(tier3.convert("RGBA"), "stages/trollge/bg_glitch.png")

    # Tier 4 -- 8/10: corrupted, split, almost unreadable.
    tier3 = ImageEnhance.Color(src).enhance(1.7)
    tier3 = ImageChops.add(tier3, Image.new("RGB", src.size, (140, 0, 10)), scale=1.0, offset=-60)
    tier3 = rgb_split(tier3, 6)
    tier3 = scanlines(tier3, 3, 34)
    tier3 = grain(tier3, 0.11, seed=8008)
    tier3 = ImageEnhance.Contrast(tier3).enhance(1.2)
    tier3 = vignette(tier3, 0.75)
    save(tier3.convert("RGBA"), "stages/trollge/bg_nightmare.png")

    # Tier 5 -- 10/10: keep the room's peeling walls readable instead of
    # crushing almost every detail into an opaque red-black field. A low ember
    # wash leaves the central walls cooler, with the red bleeding from below.
    tier4 = ImageEnhance.Brightness(src).enhance(0.82)
    tier4 = ImageEnhance.Contrast(tier4).enhance(1.08)
    red_mask = Image.new("L", src.size, 0)
    md = ImageDraw.Draw(red_mask)
    for y in range(BG_H):
        md.line((0, y, BG_W, y), fill=int(25 + 62 * y / BG_H))
    tier4 = Image.composite(Image.new("RGB", src.size, (112, 12, 8)), tier4, red_mask)
    tier4 = rgb_split(tier4, 7)
    tier4 = scanlines(tier4, 3, 24)
    # Seeded byte noise: unlike Image.effect_noise this is reproducible.
    speckle = Image.frombytes("L", src.size, random.Random(1010).randbytes(BG_W * BG_H))
    speckle = speckle.point(lambda v: int(v * 0.025))
    tier4 = ImageChops.add(tier4, Image.merge("RGB", (speckle, speckle, speckle)))
    tier4 = vignette(tier4, 0.70)
    save(tier4.convert("RGBA"), "stages/trollge/bg_hell.png")


def build_docs():
    """Repo documentation previews (not shipped with the mod)."""
    docs = os.path.join(ROOT, "docs")
    os.makedirs(docs, exist_ok=True)

    names = ("bg", "bg_scary", "bg_glitch", "bg_nightmare", "bg_hell")
    tiers = [Image.open(os.path.join(IMG, "stages", "trollge", n + ".png")).convert("RGB")
             for n in names]
    tw2, th2 = 384, 216
    strip = Image.new("RGB", (tw2 * len(tiers), th2))
    for i, image in enumerate(tiers):
        strip.paste(image.resize((tw2, th2), Image.LANCZOS), (i * tw2, 0))
    strip.save(os.path.join(docs, "stages.png"), optimize=True)
    print("  -> docs/stages.png (%d scare tiers)" % len(tiers))

    scare_path = os.path.join(IMG, "trollge_jump_scare.png")
    if os.path.isfile(scare_path):
        scare = Image.open(scare_path).convert("RGB")
        scare.resize((640, 360), Image.LANCZOS).save(os.path.join(docs, "jumpscare.png"), optimize=True)
        print("  -> docs/jumpscare.png")


def main():
    print("Building VHS overlays (static / distortion / invert)...")
    build_scare_art()

    print("Building stage backdrops (3 scare tiers)...")
    build_backgrounds()

    print("Building the story-menu week banner...")
    icon = os.path.join(IMG, "icons", "trollge", "icon.png")
    if os.path.isfile(icon):
        face = Image.open(icon).convert("RGBA").crop((0, 0, 150, 150))
        build_week_banner(face)
    else:
        print("  ! images/icons/trollge/icon.png missing -- run tools/make_characters.py first")

    print("Building documentation previews...")
    build_docs()


if __name__ == "__main__":
    main()
