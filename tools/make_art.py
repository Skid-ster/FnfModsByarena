#!/usr/bin/env python3
"""
Builds every image asset of the Super Scary Trollge mod.

Every piece of Trollge art is *drawn in code* by `tools/trollge_art.py` (wobbly
polylines, per-pose skeletons -> real animation frames), so the character is
100% reproducible and has no external art dependencies. The three stage
backdrops start from `art_src/scary_bg.png` and are graded up per scare tier.

Outputs:
    images/characters/Trollge.png/.xml        phase 1 atlas (songs 1-2)
    images/characters/TrollgeScary.png/.xml   phase 2 atlas (song 3)
    images/icons/trollge/icon.png             health icon (300x150)
    images/icons/trollge_scary/icon.png       phase 2 health icon
    images/stages/trollge/bg.png              tier 1 (2/10)
    images/stages/trollge/bg_scary.png        tier 2 (4/10)
    images/stages/trollge/bg_nightmare.png    tier 3 (7/10)
    images/menus/storymenu/weeks/trollge_week.png
    images/trollge_idle.png                     standalone sprites
    images/trollge_sing.png
    images/trollge_scary_bg.png
    images/trollge_jump_scare.png
    images/trollge_distortion.png
    images/trollge_invert.png
    images/trollge_static.png

Run with:  python3 tools/make_art.py
"""

import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trollge_art as T  # noqa: E402

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
    noise = Image.effect_noise(image.size, 90).convert("L")
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


def build_character(name, poses, sheet_name):
    frames, _counters = T.render_atlas(
        poses,
        out("characters/%s.png" % name),
        out("characters/%s.xml" % name),
        sheet_name=name,
    )
    print("  -> images/characters/%-22s %s (%d frames)"
          % (name + ".png", frames[0].size, len(frames)))
    return frames


def build_icons(frames, frames_scary):
    for name, poses in (("trollge", frames), ("trollge_scary", frames_scary)):
        normal = head_crop(poses[0])
        losing = head_crop(poses[-1])
        losing = ImageEnhance.Color(losing).enhance(0.35)
        losing = ImageEnhance.Brightness(losing).enhance(0.85)
        glow = Image.new("RGBA", losing.size, (150, 12, 24, 255))
        losing = Image.alpha_composite(losing, Image.composite(glow, Image.new("RGBA", losing.size), losing.getchannel("A").point(lambda v: int(v * 0.55))))
        losing = ImageEnhance.Contrast(losing).enhance(1.1)
        icon = Image.new("RGBA", (300, 150), (0, 0, 0, 0))
        icon.alpha_composite(normal, (0, 0))
        icon.alpha_composite(losing, (150, 0))
        save(icon, "icons/%s/icon.png" % name)


def build_week_banner(face_frame):
    w, h = 359, 89
    banner = Image.new("RGBA", (w, h), (10, 5, 7, 255))
    grad = Image.new("L", (w, h))
    gd = ImageDraw.Draw(grad)
    for yy in range(h):
        gd.line([(0, yy), (w, yy)], fill=int(90 * (1 - yy / h)) + 16)
    banner = Image.composite(Image.new("RGBA", (w, h), (122, 10, 24, 255)), banner, grad)

    face = head_crop(face_frame, 150, 0.02, 0.5).resize((84, 84), Image.LANCZOS)
    banner.alpha_composite(face, (w - 90, 3))

    draw = ImageDraw.Draw(banner)
    big = ImageFont.truetype(FONT_BOLD, 27)
    small = ImageFont.truetype(FONT_BOLD, 12)
    draw.text((11, 10), "SUPER SCARY", font=small, fill=(255, 196, 196, 255))
    draw.text((12, 26), "TROLLGE", font=big, fill=(196, 16, 30, 255))
    draw.text((11, 25), "TROLLGE", font=big, fill=(255, 255, 255, 255))
    save(banner, "menus/storymenu/weeks/trollge_week.png")


def build_week_characters(frames):
    """Story-menu character sprite (the trollge standing next to the week banner)."""
    frame = frames[0]
    box = frame.getbbox()
    body = frame.crop(box)
    height = 460
    width = max(1, int(body.width * height / body.height))
    body = body.resize((width, height), Image.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(body, (0, 0))
    save(canvas, "menus/storymenu/characters/trollge.png")


def build_scare_art():
    """The jump-scare, drawn big, then pushed through VHS treatment."""
    scare = T.draw_trollge(
        BG_W,
        BG_H,
        head_scale=3.05,
        head_dy=150,
        head_tilt=-3,
        mouth="scream",
        eyes="bloodshot",
        veins=True,
        drips=True,
        horns=True,
        static=0.16,
        jitter=3.4,
        lean=-4,
        seed=777,
    )
    # Backdrop: pulsing red radial glow behind the head so the silhouette pops.
    backdrop = Image.new("RGB", scare.size, (6, 2, 4))
    glow = Image.new("L", scare.size, 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([BG_W * 0.18, BG_H * 0.02, BG_W * 0.82, BG_H * 0.98], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    backdrop = Image.composite(Image.new("RGB", scare.size, (128, 8, 16)), backdrop, glow)
    flat = Image.new("RGBA", scare.size, (0, 0, 0, 0))
    flat.alpha_composite(scare)
    rgb = Image.alpha_composite(backdrop.convert("RGBA"), flat).convert("RGB")

    # Rim glow: blurred, brightened copy of the character screen-added on top.
    rim = flat.filter(ImageFilter.GaussianBlur(7))
    rim = ImageEnhance.Brightness(rim).enhance(2.4)
    rgb = ImageChops.add(rgb, rim.convert("RGB"), scale=1.0, offset=-40)

    rgb = ImageEnhance.Brightness(rgb).enhance(1.25)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.2)
    rgb = rgb_split(rgb, 10)
    rgb = scanlines(rgb, 4, 30)
    rgb = grain(rgb, 0.10)
    rgb = vignette(rgb, 0.72)
    # Blood haze.
    haze = Image.new("RGB", rgb.size, (86, 0, 6))
    rgb = Image.blend(rgb, ImageChops.add(rgb, haze), 0.35)

    scare_img = rgb.convert("RGBA")
    save(scare_img, "trollge_jump_scare.png")

    inverted = ImageOps.invert(rgb)
    inverted = ImageEnhance.Color(inverted).enhance(1.35)
    save(inverted.convert("RGBA"), "trollge_invert.png")

    # Distortion overlay: transparent, only the RGB-split glitch streaks show.
    glitch = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    shifted = rgb_split(rgb, 14).convert("RGBA")
    mask = Image.new("L", rgb.size, 0)
    md = ImageDraw.Draw(mask)
    rnd = random.Random(4321)
    y = 0
    while y < BG_H:
        band = rnd.randint(5, 30)
        if rnd.random() < 0.6:
            md.rectangle([0, y, BG_W, y + band], fill=rnd.randint(80, 210))
        y += band + rnd.randint(8, 44)
    mask = mask.filter(ImageFilter.GaussianBlur(0.7))
    visible = shifted.convert("L").point(lambda v: min(255, int(v * 2.2)))
    glitch.paste(shifted, (0, 0), ImageChops.multiply(mask, visible))
    save(glitch, "trollge_distortion.png")

    # Full-screen static.
    static = Image.effect_noise((BG_W, BG_H), 110).convert("L")
    static = static.point(lambda v: max(0, int((v - 90) * 3)))
    save(Image.merge("RGBA", (static, static, static, static.point(lambda v: int(v * 0.8)))),
         "trollge_static.png")

    return scare_img


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
    tier2 = grain(tier2, 0.05)
    tier2 = vignette(tier2, 0.6)
    save(tier2.convert("RGBA"), "stages/trollge/bg_scary.png")

    # Tier 3 -- 7/10: corrupted, split, almost unreadable.
    tier3 = ImageEnhance.Color(src).enhance(1.7)
    tier3 = ImageChops.add(tier3, Image.new("RGB", src.size, (140, 0, 10)), scale=1.0, offset=-60)
    tier3 = rgb_split(tier3, 6)
    tier3 = scanlines(tier3, 3, 34)
    tier3 = grain(tier3, 0.11)
    tier3 = ImageEnhance.Contrast(tier3).enhance(1.2)
    tier3 = vignette(tier3, 0.75)
    save(tier3.convert("RGBA"), "stages/trollge/bg_nightmare.png")


def build_previews(normal_frames, scary_frames):
    """Repo documentation previews (not shipped with the mod)."""
    docs = os.path.join(ROOT, "docs")
    os.makedirs(docs, exist_ok=True)

    picks = [normal_frames[0], normal_frames[2], normal_frames[3],
             normal_frames[4], normal_frames[5], normal_frames[6],
             normal_frames[18], scary_frames[0], scary_frames[2], scary_frames[14]]
    scale = 0.42
    tw, th = int(T.FRAME_W * scale), int(T.FRAME_H * scale)
    sheet = Image.new("RGBA", (tw * len(picks), th), (18, 14, 18, 255))
    for i, frame in enumerate(picks):
        sheet.alpha_composite(frame.resize((tw, th), Image.LANCZOS), (i * tw, 0))
    sheet.convert("RGB").save(os.path.join(docs, "preview.png"), optimize=True)
    print("  -> docs/preview.png (%d poses)" % len(picks))

    tiers = []
    for name in ("bg", "bg_scary", "bg_nightmare"):
        tiers.append(Image.open(os.path.join(IMG, "stages", "trollge", name + ".png")).convert("RGB"))
    tw2, th2 = 480, 270
    strip = Image.new("RGB", (tw2 * 3, th2))
    for i, image in enumerate(tiers):
        strip.paste(image.resize((tw2, th2), Image.LANCZOS), (i * tw2, 0))
    strip.save(os.path.join(docs, "stages.png"), optimize=True)
    print("  -> docs/stages.png (3 scare tiers)")

    scare = Image.open(os.path.join(IMG, "trollge_jump_scare.png")).convert("RGB")
    scare.resize((640, 360), Image.LANCZOS).save(os.path.join(docs, "jumpscare.png"), optimize=True)
    print("  -> docs/jumpscare.png")


def main():
    print("Drawing the Trollge atlases in code...")
    normal_frames = build_character("Trollge", T.POSES, "Trollge")
    scary_frames = build_character("TrollgeScary", T.SCARY_POSES, "TrollgeScary")

    # Standalone sprites (also handy as previews / other engines).
    save(normal_frames[0], "trollge_idle.png")
    save(normal_frames[3], "trollge_sing.png")

    print("Building icons + week banner...")
    build_icons(normal_frames, scary_frames)
    build_week_banner(normal_frames[0])
    build_week_characters(normal_frames)

    print("Building scare art...")
    build_scare_art()

    print("Building stage backdrops (3 scare tiers)...")
    build_backgrounds()

    print("Building documentation previews...")
    build_previews(normal_frames, scary_frames)


if __name__ == "__main__":
    main()
