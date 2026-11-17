#!/usr/bin/env python3
"""
Builds the mod's custom note skin, note splashes and the corrupted song-3 skin.

Everything here is drawn in code (Pillow), so the arrows are reproducible and
there is no borrowed FNF art.

Outputs
    images/game/notes/default.png/.xml     strums + notes + holds (all songs)
    images/game/notes/corrupt.png/.xml     same layout, glitched (song 3 only,
                                           enabled with "noteTypes": ["corrupt"])
    data/splashes/default.xml              splash config (which anim plays per strum)
    images/game/splashes/default.png/.xml  splash atlas
    docs/noteskin.png                      preview

Frame names follow the engine exactly (see StrumLine.createStrum / Note.hx):
    arrowLEFT|DOWN|UP|RIGHT0000     strum, idle
    left|down|up|right press0000..  strum, pressed (4 frames)
    left|down|up|right confirm0000.. strum, confirm flash (4 frames)
    purple|blue|green|red0000       scrolling note
    purple|blue|green|red hold piece0000
    purple|blue|green|red hold end0000
    note impact 1|2 <colour>0000..  splash (4 frames each)

Run with:  python3 tools/make_noteskin.py
"""

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DOCS = os.path.join(ROOT, "docs")

ARROW = 160          # arrow frame size
POP = 200            # press / confirm frame size
HOLD_W, HOLD_PIECE_H, HOLD_END_H = 52, 88, 64
SPLASH_W, SPLASH_H = 260, 298
SUPER = 4            # supersampling factor for smooth edges

#: FNF names the four lanes by colour; the engine looks those names up, so only
#: the RGB changes between skins. Song 1 keeps the brightest palette, song 2 is
#: drained of colour, song 3 is corrupted (see PALETTES / SKINS below).
LANES = [
    # (strum prefix, note colour name, rgb)
    ("left", "purple", (142, 59, 255)),     # LEFT  -- violet
    ("down", "blue", (45, 130, 255)),       # DOWN  -- cold blue
    ("up", "green", (58, 220, 150)),        # UP    -- toxic mint
    ("right", "red", (232, 32, 48)),        # RIGHT -- crimson
]

SHADOW_LANES = [
    ("left", "purple", (108, 118, 156)),    # steel violet
    ("down", "blue", (52, 78, 122)),        # deep water
    ("up", "green", (74, 104, 116)),        # corpse teal
    ("right", "red", (138, 40, 54)),        # dried blood
]

ARROW_UP = [(50, 5), (88, 43), (64, 43), (64, 93), (36, 93), (36, 43), (12, 43)]


# --------------------------------------------------------------------------- #

def out(path):
    full = os.path.join(MOD, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


def save(image, path):
    full = out(path)
    image.save(full, optimize=True)
    print("  -> %-46s %s" % (path, image.size))
    return full


def mask_from_polygon(points, size, scale=1.0, rotate=0):
    """Anti-aliased mask of the arrow polygon."""
    big = size * SUPER
    image = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(image)
    unit = big / 100.0 * scale
    offset = (big - 100 * unit) / 2.0
    poly = [(offset + x * unit, offset + y * unit) for x, y in points]
    draw.polygon(poly, fill=255)
    if rotate:
        image = image.rotate(rotate, resample=Image.BICUBIC, center=(big / 2, big / 2))
    return image.resize((size, size), Image.LANCZOS)


def edge_of(mask, width=3):
    """Ring along the outline of a mask."""
    eroded = mask.filter(ImageFilter.MinFilter(width * 2 + 1))
    return ImageChops.subtract(mask, eroded)


def coloured(mask, rgb, alpha=255):
    layer = Image.new("RGBA", mask.size, rgb + (0,))
    layer.putalpha(mask.point(lambda v: int(v * alpha / 255)))
    return layer


def glow(mask, rgb, radius, alpha=150):
    blurred = mask.filter(ImageFilter.GaussianBlur(radius))
    return coloured(blurred, rgb, alpha)


def scratch(mask, seed, count=9, strength=40):
    """Thin dark scratches, clipped to the mask."""
    rng = random.Random(seed)
    size = mask.size[0]
    marks = Image.new("L", mask.size, 0)
    draw = ImageDraw.Draw(marks)
    for _ in range(count):
        x0 = rng.randrange(size)
        y0 = rng.randrange(size)
        length = rng.randrange(size // 6, size // 2)
        draw.line([(x0, y0), (x0 + rng.randint(-8, 8), y0 - length)],
                  fill=rng.randint(30, strength), width=rng.choice([1, 1, 2]))
    return ImageChops.multiply(mask, marks.point(lambda v: 255 - v))


def erode(mask, amount):
    """Shrink a mask by `amount` pixels (odd MinFilter kernel)."""
    k = max(3, int(amount) * 2 + 1)
    return mask.filter(ImageFilter.MinFilter(k))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hot_core(mask, rgb, size, scale=0.42, alpha=200, blur=0.05):
    """Bright interior for a note: the colour, lifted towards white in the middle.

    Dark stages used to swallow the arrow bodies, because the old fill went almost
    black at the tip. This keeps the silhouette identical and only changes what is
    inside it, so note timing is unaffected.
    """
    inner = erode(mask, max(2.0, size * 0.055 * scale))
    inner = inner.filter(ImageFilter.GaussianBlur(size * blur))
    hot = mix(rgb, (255, 255, 255), 0.62)
    layer = Image.new("RGBA", mask.size, hot + (0,))
    layer.putalpha(inner.point(lambda v: int(v * alpha / 255.0)))
    return layer


def chroma_edge(canvas, dx=2, amount=0.6):
    """Red/cyan misregistration around whatever is already drawn."""
    r, g, b, a = canvas.split()
    red = Image.merge("RGBA", (r.point(lambda v: int(v * amount)), g.point(lambda v: 0),
                               b.point(lambda v: 0), a.point(lambda v: int(v * 0.75))))
    cyan = Image.merge("RGBA", (r.point(lambda v: 0), g, b.point(lambda v: int(v * 0.9)),
                                a.point(lambda v: int(v * 0.75))))
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    out.alpha_composite(cyan, (dx, 0))
    out.alpha_composite(red, (-dx, 0))
    out.alpha_composite(canvas)
    return out


def scanlines(canvas, mask, step=3, strength=64):
    """CRT rows, clipped to the sprite so the atlas stays tight."""
    dark = Image.new("L", canvas.size, 0)
    d = ImageDraw.Draw(dark)
    for y in range(1, canvas.size[1], step):
        d.line((0, y, canvas.size[0], y), fill=strength)
    dark = ImageChops.multiply(dark, mask)
    shade = Image.new("RGBA", canvas.size, (0, 0, 0, 255))
    shade.putalpha(dark)
    return Image.alpha_composite(canvas, shade)


def ink_drips(canvas, mask, colour, seed, count=3, size=1.0):
    """Thin runs of ink hanging inside the shape, never past its own alpha."""
    rng = random.Random(seed)
    w, h = canvas.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    seedable = [(x, y) for y in range(0, h, max(1, int(h / 14)))
                for x in range(int(w * 0.2), int(w * 0.8), max(1, int(w / 12)))
                if mask.getpixel((x, y)) > 180]
    if not seedable:
        return canvas
    for _ in range(count):
        x, y = rng.choice(seedable)
        length = rng.randint(int(size * 6), int(size * 20))
        d.line([(x, y), (x + rng.randint(-1, 1), y + length)],
               fill=colour + (rng.randint(90, 150),), width=rng.choice([1, 2]))
    layer = ImageChops.multiply(layer, coloured(mask, (255, 255, 255), 255))
    out = canvas.copy()
    out.alpha_composite(layer)
    return out


def seeded_noise(size, seed):
    """Stable per-frame texture; Image.effect_noise ignores our RNG seed."""
    return Image.frombytes("L", size, random.Random(seed).randbytes(size[0] * size[1]))


def jagged_edge(mask, width, seed, density=0.55):
    """A broken, static-eaten rim instead of a clean vector outline."""
    ring = edge_of(mask, width)
    noise = seeded_noise(mask.size, seed)
    cut = noise.point(lambda v: 255 if v > int(255 * (1.0 - density)) else 0)
    out = ImageChops.multiply(ring, cut)
    # keep the ring continuous enough to still read as an arrow
    return ImageChops.lighter(out, ring.point(lambda v: int(v * 0.45)))


def dress(image, seed, drips=2):
    """The shared horror pass: chroma fringe, CRT rows, ink runs. Any sprite."""
    mask = image.getchannel("A")
    out = chroma_edge(image, dx=2, amount=0.45)
    out = scanlines(out, mask, step=3, strength=54)
    out = ink_drips(out, mask, (11, 5, 13), seed=seed, count=drips, size=1.0)
    return out


def body_fill(mask, rgb, dark, top_light=70, tint=0.78):
    """Vertical gradient body: dark at the tip, saturated colour towards the tail."""
    size = mask.size[0]
    grad = Image.new("RGB", mask.size)
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / float(size - 1)
        shade = tuple(int(dark[i] + (rgb[i] - dark[i]) * (t ** 0.85) * tint) for i in range(3))
        gd.line([(0, y), (size, y)], fill=shade)
    layer = grad.convert("RGBA")
    layer.putalpha(mask)
    if top_light:
        sheen = Image.new("L", mask.size, 0)
        sd = ImageDraw.Draw(sheen)
        sd.rectangle([0, 0, size, int(size * 0.30)], fill=top_light)
        sheen = sheen.filter(ImageFilter.GaussianBlur(size * 0.05))
        layer.alpha_composite(coloured(ImageChops.multiply(mask, sheen), (255, 255, 255), 255))
    return layer


def arrow_frame(size, rgb, mode, rotate=0, scale=1.0, frame_index=0):
    """One arrow frame. Drawn pointing up, rotated at the end so the gradient
    always runs tip -> tail no matter the direction."""
    mask = mask_from_polygon(ARROW_UP, size, scale=scale)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dark = (10, 10, 16)
    highlight = tuple(min(255, int(c * 0.45 + 255 * 0.55)) for c in rgb)

    if mode in ("note", "press", "confirm"):
        canvas.alpha_composite(glow(mask, rgb, size * 0.055, 190))
        canvas.alpha_composite(glow(mask, rgb, size * 0.14, 80))

    if mode == "strum":
        # Receptor. It used to be near-black with a hairline of colour, which
        # vanished on the dark stages -- so: dark body, hot inner core, a broken
        # static rim and a thin white keyline. Read as "the lane", never as a note.
        canvas.alpha_composite(coloured(mask, (10, 8, 14), 240))
        canvas.alpha_composite(glow(erode(mask, size * 0.05), rgb, size * 0.05, 120))
        inner = erode(mask, size * 0.035)
        canvas.alpha_composite(coloured(inner.filter(ImageFilter.GaussianBlur(size * 0.03)),
                                        mix(rgb, (255, 255, 255), 0.35), 150))
        canvas.alpha_composite(coloured(edge_of(mask, max(2, size // 34)), rgb, 235))
        canvas.alpha_composite(coloured(jagged_edge(mask, max(1, size // 60), seed=7), (255, 90, 90), 120))
        canvas.alpha_composite(coloured(edge_of(mask, max(1, size // 90)), (255, 255, 255), 95))
    elif mode == "note":
        canvas.alpha_composite(body_fill(mask, rgb, dark, top_light=60, tint=1.0))
        # Bright interior core: the whole point of this pass is that a note is
        # readable at 2.4 scroll speed on a black background.
        canvas.alpha_composite(hot_core(mask, rgb, size))
        canvas.alpha_composite(coloured(edge_of(mask, max(2, size // 40)), mix(rgb, (255, 255, 255), 0.25), 255))
        canvas.alpha_composite(coloured(edge_of(mask, max(1, size // 80)), (255, 255, 255), 150))
        # bright spine down the shaft so the note reads at speed
        spine = Image.new("L", mask.size, 0)
        sd = ImageDraw.Draw(spine)
        sd.rectangle([size * 0.478, size * 0.28, size * 0.522, size * 0.84], fill=255)
        spine = spine.filter(ImageFilter.GaussianBlur(size * 0.018))
        canvas.alpha_composite(coloured(ImageChops.multiply(spine, mask), highlight, 180))
    elif mode == "press":
        canvas.alpha_composite(coloured(mask, rgb, 120))
        canvas.alpha_composite(body_fill(mask, rgb, (26, 26, 34), top_light=90, tint=0.55))
        canvas.alpha_composite(coloured(edge_of(mask, max(3, size // 30)), (255, 255, 255), 190))
    elif mode == "confirm":
        # Confirm flash: a white-hot flood inside the arrow plus a ring that
        # expands past the frame. The ring is drawn on a larger canvas and then
        # centred -- drawing it straight into a `size` canvas clipped its wings,
        # which is the "misaligned edge" the purple confirm frame had.
        t = frame_index / 3.0
        ring_size = int(size * 1.7)
        ring = mask_from_polygon(ARROW_UP, ring_size, scale=(1.0 + t * 0.55) / 1.7)
        ring = ring.resize((size, size), Image.LANCZOS)
        canvas.alpha_composite(coloured(edge_of(ring, max(2, size // 40)), (255, 255, 255),
                                        int(210 * (1.0 - t))))
        canvas.alpha_composite(body_fill(mask, rgb, (54, 54, 66), top_light=140, tint=0.5))
        # white-hot inner flash, decaying over the four frames
        flash = erode(mask, size * (0.10 + 0.06 * t))
        flash = flash.filter(ImageFilter.GaussianBlur(size * (0.01 + 0.02 * t)))
        canvas.alpha_composite(coloured(flash, (255, 255, 255), int(235 * (1.0 - t * 0.8))))
        canvas.alpha_composite(coloured(edge_of(mask, max(2, size // 34)),
                                        mix(rgb, (255, 255, 255), 0.35), int(255 * (1 - t * 0.4))))

    # Unified horror details: every note direction and every hold trail gets the
    # same treatment now -- red/cyan fringe, CRT rows and a couple of ink runs --
    # instead of only the two "special" skins at the end of the atlas.
    if mode in ("note", "press"):
        canvas = chroma_edge(canvas, dx=max(1, size // 80), amount=0.5)
        canvas = scanlines(canvas, mask, step=4, strength=36)
        canvas = ink_drips(canvas, mask, (12, 6, 14), seed=size + int(scale * 100) + frame_index,
                           count=3, size=size / 90.0)

    canvas.alpha_composite(coloured(scratch(mask, seed=size + int(scale * 100) + frame_index),
                                    (0, 0, 0), 45))
    if rotate:
        canvas = canvas.rotate(rotate, resample=Image.BICUBIC, center=(size / 2, size / 2))
    return canvas


def hold_piece(rgb, height):
    image = Image.new("RGBA", (HOLD_W, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = 10
    draw.rounded_rectangle([0, 0, HOLD_W - 1, height - 1], radius=radius,
                           fill=(14, 14, 20, 255))
    for y in range(height):
        t = y / float(height - 1)
        colour = tuple(int(20 + (rgb[i] - 20) * (0.35 + 0.65 * (1 - abs(t - 0.5) * 2))) for i in range(3))
        draw.line([(3, y), (HOLD_W - 4, y)], fill=colour + (255,))
    draw.rounded_rectangle([0, 0, HOLD_W - 1, height - 1], radius=radius,
                           outline=rgb + (235,), width=3)
    # arrow chevrons down the strip
    for i in range(height // 22):
        cy = 14 + i * 22
        draw.line([(10, cy), (HOLD_W // 2, cy + 7), (HOLD_W - 10, cy)], fill=(255, 255, 255, 90), width=2)
    # brighter rail than before, so a held note still glows on a black stage
    draw.line([(HOLD_W // 2, 3), (HOLD_W // 2, height - 3)],
              fill=mix(rgb, (255, 255, 255), 0.45) + (110,), width=3)
    return dress(image, seed=int(sum(rgb)) + height, drips=1)


def hold_end(rgb):
    image = Image.new("RGBA", (HOLD_W, HOLD_END_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([0, 0, HOLD_W - 1, HOLD_END_H - 1], radius=18,
                           fill=(16, 16, 24, 255), outline=rgb + (255,), width=3)
    draw.rounded_rectangle([6, HOLD_END_H - 22, HOLD_W - 7, HOLD_END_H - 5], radius=9,
                           fill=rgb + (230,))
    draw.line([(HOLD_W // 2, 10), (HOLD_W // 2, HOLD_END_H - 26)],
              fill=mix(rgb, (255, 255, 255), 0.5) + (120,), width=2)
    return dress(image, seed=int(sum(rgb)) + 41, drips=1)


# --------------------------------------------------------------------------- #
# Glitch pass (song 3 skin)

def corrupt(image, seed):
    rng = random.Random(seed)
    w, h = image.size
    out_img = image.copy()

    # horizontal slice displacement
    for _ in range(6):
        y0 = rng.randrange(h)
        band = rng.randint(2, max(3, h // 14))
        dx = rng.randint(-w // 12, w // 12)
        strip = out_img.crop((0, y0, w, min(h, y0 + band)))
        out_img.paste(strip, (dx, y0))

    # RGB split
    r, g, b, a = out_img.split()
    shifted = Image.merge("RGBA", (r, g, b, a))
    out_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out_img.alpha_composite(Image.merge("RGBA", (r, g, b, a)), (0, 0))
    out_img.alpha_composite(Image.merge("RGBA", (r.point(lambda v: v // 2), g, b.point(lambda v: v // 3), a)),
                            (4, 0))
    out_img.alpha_composite(Image.merge("RGBA", (r, g.point(lambda v: v // 2), b, a)), (-3, 0))

    # static speckle, clipped to the sprite so the atlas stays light
    original_alpha = image.getchannel("A")
    noise = seeded_noise((w, h), seed)
    red = Image.new("RGBA", (w, h), (255, 40, 60))
    red.putalpha(ImageChops.multiply(noise.point(lambda v: int(v * 0.16)), original_alpha))
    out_img.alpha_composite(red)

    r, g, b, a = out_img.split()
    return Image.merge("RGBA", (r, g, b, ImageChops.multiply(a, original_alpha)))


def torn(image, seed):
    """Song 5 skin: burnt through. Ember body, chewed edge, CRT damage.

    The old version ran the corrupt() pass over it, whose fine speckle at this
    size looked like unreadable micro-text inside the arrow. This one uses bold
    marks only: a heavy red/cyan fringe, scanlines, ink runs and a burnt edge.
    """
    # Retain the lane colours: turning every arrow dark red makes fast patterns
    # indistinguishable against the finale's red-black stage. A restrained ember
    # tint and brighter centres keep the distressed look without hiding inputs.
    rgb = image.convert("RGB")
    ember = ImageOps.colorize(rgb.convert("L"), black=(10, 2, 3),
                              mid=(126, 18, 12), white=(245, 104, 82))
    rgb = Image.blend(rgb, ember, 0.28)
    rgb = ImageEnhance.Brightness(rgb).enhance(1.24)
    out_img = rgb.convert("RGBA")
    mask = image.getchannel("A")
    out_img.putalpha(mask)

    out_img = chroma_edge(out_img, dx=max(2, image.size[0] // 54), amount=0.8)
    out_img = scanlines(out_img, mask, step=5, strength=72)
    out_img = ink_drips(out_img, mask, (28, 2, 4), seed=seed, count=5, size=1.8)

    # burnt edge: alpha chewed in horizontal tears, never into detached specks
    noise = seeded_noise(image.size, seed)
    tears = noise.point(lambda v: 255 if v > 96 else 210)
    out_img.putalpha(ImageChops.multiply(out_img.getchannel("A"), tears))
    return out_img


# --------------------------------------------------------------------------- #
# Splashes

def splash_frame(index, rgb, impact):
    image = Image.new("RGBA", (SPLASH_W, SPLASH_H), (0, 0, 0, 0))
    cx, cy = SPLASH_W / 2, SPLASH_H / 2
    t = index / 3.0

    ring = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    radius = (52 if impact == 1 else 74) * (0.45 + t * 1.15)
    width = max(2, int(16 * (1 - t)))
    for k in range(3):
        rr = radius * (1 + k * 0.22)
        rd.ellipse([cx - rr, cy - rr * 0.8, cx + rr, cy + rr * 0.8],
                   outline=rgb + (int((210 - k * 60) * (1 - t)),), width=width)
    image.alpha_composite(ring.filter(ImageFilter.GaussianBlur(2)))

    core = Image.new("RGBA", image.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(core)
    r0 = (34 if impact == 1 else 48) * (1.0 - t * 0.75)
    cd.ellipse([cx - r0, cy - r0, cx + r0, cy + r0],
               fill=(255, 255, 255, int(255 * (1 - t * 0.85))))
    cd.ellipse([cx - r0 * 1.7, cy - r0 * 1.7, cx + r0 * 1.7, cy + r0 * 1.7],
               outline=rgb + (int(180 * (1 - t)),), width=4)
    image.alpha_composite(core.filter(ImageFilter.GaussianBlur(1)))

    # ink flecks
    rng = random.Random(index * 31 + impact * 7)
    flecks = Image.new("RGBA", image.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(flecks)
    for _ in range(26):
        ang = rng.uniform(0, math.tau)
        dist = rng.uniform(30, (110 if impact == 1 else 140)) * (0.4 + t)
        size = rng.uniform(1.5, 5.0) * (1 - t * 0.5)
        x = cx + math.cos(ang) * dist
        y = cy + math.sin(ang) * dist * 0.8
        fd.ellipse([x - size, y - size, x + size, y + size],
                   fill=(255, 255, 255, int(rng.uniform(90, 220) * (1 - t))))
    image.alpha_composite(flecks)
    return image


# --------------------------------------------------------------------------- #
# Atlas writing

def write_atlas(frames, sprite, path, crop=False):
    """frames: [(name, image)] -> shelf-packed PNG + Sparrow XML.

    `crop=False` keeps every frame at its authored size on purpose: the engine
    sizes strums and notes from the frame width, so a cropped atlas would make
    left/right arrows render larger than up/down ones.
    """
    entries = []
    for name, image in frames:
        box = image.getchannel("A").getbbox()
        if box is None:
            continue
        if crop:
            entries.append((name, image.crop(box), box))
        else:
            entries.append((name, image, (0, 0, image.width, image.height)))

    max_w = 2048
    x = y = row_h = 0
    placed = []
    for name, crop, box in entries:
        if x + crop.width > max_w:
            x, y, row_h = 0, y + row_h, 0
        placed.append((name, crop, box, x, y))
        x += crop.width
        row_h = max(row_h, crop.height)

    sheet = Image.new("RGBA", (max(p[3] + p[1].width for p in placed), y + row_h), (0, 0, 0, 0))
    for _n, crop, _b, px, py in placed:
        sheet.paste(crop, (px, py))

    save(sheet, path + ".png")

    lines = ["<?xml version='1.0' encoding='utf-8'?>",
             '<TextureAtlas imagePath="%s.png">' % os.path.basename(path)]
    for name, crop, box, px, py in placed:
        lines.append('    <SubTexture name="%s" x="%d" y="%d" width="%d" height="%d"/>'
                     % (name, px, py, crop.width, crop.height))
    lines.append("</TextureAtlas>")
    full = out(path + ".xml")
    open(full, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("  -> %-46s %d frames" % (path + ".xml", len(placed)))


def build_skin(sprite_path, lanes=None, transform=None):
    lanes = lanes or LANES
    frames = []
    for index, (prefix, colour_name, rgb) in enumerate(lanes):
        rotate = [90, 180, 0, 270][index]      # left, down, up, right
        static = arrow_frame(ARROW, rgb, "strum", rotate=rotate)
        note = arrow_frame(ARROW, rgb, "note", rotate=rotate)
        if transform:
            static, note = transform(static, 100 + index), transform(note, 200 + index)
        frames.append(("arrow%s0000" % prefix.upper(), static))
        frames.append(("%s0000" % colour_name, note))

        for f in range(4):
            press = arrow_frame(POP, rgb, "press", rotate=rotate, scale=0.98)
            confirm = arrow_frame(POP, rgb, "confirm", rotate=rotate, scale=0.98, frame_index=f)
            if transform:
                press, confirm = transform(press, 300 + f * 10 + index), transform(confirm, 400 + f * 10 + index)
            frames.append(("%s press%04d" % (prefix, f), press))
            frames.append(("%s confirm%04d" % (prefix, f), confirm))

        piece = hold_piece(rgb, HOLD_PIECE_H)
        end = hold_end(rgb)
        if transform:
            piece, end = transform(piece, 500 + index), transform(end, 600 + index)
        frames.append(("%s hold piece0000" % colour_name, piece))
        frames.append(("%s hold end0000" % colour_name, end))

    # the engine looks for FNF's "pruple end hold" typo first; give it art too
    frames.append(("pruple end hold0000", frames[[n for n, _ in frames].index("purple hold end0000")][1]))
    write_atlas(frames, sprite_path, sprite_path)


def drained(image, seed):
    """Song 2 skin: colour pulled out, with a cold metallic rim so it is not flat.

    The old version was a straight desaturate, which read as a grey blob on the
    grey stage. Now it keeps a steel keyline, a specular streak and a little
    static, the same way a blank tape still shows its heads.
    """
    rgb = image.convert("RGB")
    grey = rgb.convert("L").convert("RGB")
    mixed = Image.blend(rgb, grey, 0.55)
    mixed = Image.blend(mixed, Image.new("RGB", image.size, (16, 20, 28)), 0.18)
    out_img = mixed.convert("RGBA")
    mask = image.getchannel("A")
    out_img.putalpha(mask)

    # metallic rim + a highlight running down the shaft
    out_img.alpha_composite(coloured(edge_of(mask, 3), (196, 214, 232), 145))
    out_img.alpha_composite(coloured(edge_of(mask, 1), (255, 255, 255), 120))
    spec = Image.new("L", image.size, 0)
    sd = ImageDraw.Draw(spec)
    w, h = image.size
    sd.line([(w * 0.40, h * 0.30), (w * 0.40, h * 0.78)], fill=210, width=max(1, w // 60))
    sd.line([(w * 0.52, h * 0.26), (w * 0.52, h * 0.70)], fill=120, width=max(1, w // 90))
    spec = spec.filter(ImageFilter.GaussianBlur(w * 0.02))
    out_img.alpha_composite(coloured(ImageChops.multiply(spec, mask), (255, 255, 255), 105))

    # static: fine speckle clipped to the sprite
    noise = seeded_noise(image.size, seed)
    speck = coloured(ImageChops.multiply(noise.point(lambda v: int(v * 0.14)), mask), (230, 240, 255), 190)
    out_img.alpha_composite(speck)
    return out_img


def build_splashes():
    frames = []
    for index, (_prefix, colour_name, rgb) in enumerate(LANES):
        for impact in (1, 2):
            for f in range(4):
                frames.append(("note impact %d %s%04d" % (impact, colour_name, f),
                               splash_frame(f, rgb, impact)))
    write_atlas(frames, "images/game/splashes/default", "images/game/splashes/default")

    xml = ['<!DOCTYPE codename-engine-splashes>',
           '<splashes sprite="game/splashes/default" alpha="0.65">']
    for index, (prefix, _colour, _rgb) in enumerate(LANES):
        name = ["left", "down", "up", "right"][index]
        colour = LANES[index][1]
        xml.append('    <strum id="%d"> <!-- %s -->' % (index, name.upper()))
        xml.append('        <anim name="splash%s1" anim="note impact 1 %s" fps="24" x="0" y="0"/>'
                   % (name, colour))
        xml.append('        <anim name="splash%s2" anim="note impact 2 %s" fps="24" x="0" y="0"/>'
                   % (name, colour))
        xml.append('    </strum>')
    xml.append('</splashes>')
    path = os.path.join(MOD, "data", "splashes", "default.xml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(xml) + "\n")
    print("  -> %-46s %d strums" % ("data/splashes/default.xml", len(LANES)))


def build_preview():
    tiles = []
    for index, (prefix, colour_name, rgb) in enumerate(LANES):
        rotate = [90, 180, 0, 270][index]
        tiles.append(arrow_frame(ARROW, rgb, "note", rotate=rotate))
    tiles.append(arrow_frame(ARROW, LANES[3][2], "strum", rotate=270))
    tiles.append(arrow_frame(POP, LANES[0][2], "confirm", rotate=90, frame_index=1).resize((ARROW, ARROW), Image.LANCZOS))
    tiles.append(splash_frame(1, LANES[3][2], 2).resize((ARROW, ARROW), Image.LANCZOS))
    shadow_arrow = drained(arrow_frame(ARROW, SHADOW_LANES[2][2], "note", rotate=0), 3)
    tiles.append(shadow_arrow)
    tiles.append(arrow_frame(ARROW, LANES[1][2], "hold_placeholder") if False else
                 hold_piece(LANES[0][2], HOLD_PIECE_H).resize((int(ARROW * HOLD_W / HOLD_PIECE_H), ARROW), Image.LANCZOS))
    tiles.append(corrupt(arrow_frame(ARROW, LANES[0][2], "note", rotate=90), 7))
    tiles.append(torn(arrow_frame(ARROW, LANES[3][2], "note", rotate=270), 11))

    cell = ARROW + 12
    strip = Image.new("RGBA", (cell * len(tiles), cell), (18, 14, 18, 255))
    for i, tile in enumerate(tiles):
        strip.alpha_composite(tile, (i * cell + 6, 6))
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, "noteskin.png")
    strip.convert("RGB").save(path, optimize=True)
    print("  -> docs/noteskin.png (%d tiles)" % len(tiles))


def main():
    print("Drawing the note skin (arrows, holds)...")
    build_skin("images/game/notes/default")
    print("Drawing the drained song-2 skin...")
    build_skin("images/game/notes/shadow", lanes=SHADOW_LANES, transform=drained)
    print("Drawing the corrupted song-3 skin...")
    build_skin("images/game/notes/corrupt", transform=corrupt)
    print("Drawing the burnt song-5 skin...")
    build_skin("images/game/notes/torn", transform=torn)
    print("Drawing note splashes...")
    build_splashes()
    print("Writing docs preview...")
    build_preview()
    return 0


if __name__ == "__main__":
    sys.exit(main())
