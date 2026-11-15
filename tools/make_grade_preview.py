#!/usr/bin/env python3
"""
Offline simulation of shaders/trollge_vhs.frag -> docs/grade.png

The real grade runs on the GPU inside Codename Engine; this reproduces the same
maths in numpy so the look can be reviewed (and regressions spotted) without
launching the game. Intensities match the stage script: 0.35 / 0.62 / 1.0.

Run with:  python3 tools/make_grade_preview.py
"""

import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DOCS = os.path.join(ROOT, "docs")

#: (image, intensity, aberration, scanline, grain, vignette)
STAGES = [
    ("bg", 0.35, 0.7 + 1.3 * 0.35, 0.25 + 0.45 * 0.35, 0.2 + 0.5 * 0.35, 0.35 + 0.45 * 0.35),
    ("bg_scary", 0.62, 0.7 + 1.3 * 0.62, 0.25 + 0.45 * 0.62, 0.2 + 0.5 * 0.62, 0.35 + 0.45 * 0.62),
    ("bg_nightmare", 1.0, 0.7 + 1.3, 0.25 + 0.45, 0.2 + 0.5, 0.35 + 0.45),
]


def grade(image, intensity, aberration, scanline, grain, vignette, seed=0):
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    height, width, _ = rgb.shape

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    uvx = xx / (width - 1)
    uvy = yy / (height - 1)

    # banded VHS wobble
    band = np.floor(uvy * 48.0)
    rng = np.random.default_rng(seed)
    band_shift = rng.uniform(-0.5, 0.5, size=(64,))
    uvx = uvx + band_shift[np.clip(band.astype(int), 0, 63)] * (0.012 * (0.35 + intensity))

    # chromatic aberration (radial), clamped like the GLSL
    dx = (uvx - 0.5)
    dy = (uvy - 0.5)
    offset = aberration / 480.0

    def sample(ox, oy):
        sx = np.clip(np.round((uvx + ox * dx) * (width - 1)), 0, width - 1).astype(int)
        sy = np.clip(np.round((uvy + oy * dy) * (height - 1)), 0, height - 1).astype(int)
        return rgb[sy, sx]

    out = np.zeros_like(rgb)
    out[..., 0] = sample(offset, offset)[..., 0]
    out[..., 1] = sample(0.0, 0.0)[..., 1]
    out[..., 2] = sample(-offset, -offset)[..., 2]

    # halation: 5-tap glow on highlights (mirrors the frag shader)
    glow = np.zeros_like(out)
    for ox, oy in ((3, 0), (-3, 0), (0, 3), (0, -3)):
        shifted = np.roll(np.roll(out, oy, axis=0), ox, axis=1)
        glow += np.maximum(shifted - 0.62, 0.0)
    out += glow * (0.22 + 0.30 * intensity)

    # scanlines
    scan = 0.5 + 0.5 * np.sin(uvy * 720.0)
    out *= (1.0 - scanline) + scanline * (0.88 + 0.12 * scan)[..., None]

    # grain
    noise = rng.random((height, width)).astype(np.float32)
    out += (noise[..., None] - 0.5) * (grain * 0.09)

    # vignette + corner cast
    dist = np.sqrt((uvx - 0.5) ** 2 + (uvy - 0.5) ** 2)
    vig = 1.0 - np.clip((dist - 0.18) / (0.95 - 0.18), 0.0, 1.0)
    vig = vig * vig * (3 - 2 * vig)
    out *= (1.0 - vignette) + vignette * vig[..., None]
    cast = np.array([0.93, 0.97, 1.06], dtype=np.float32)
    out = out * (1.0 - (1.0 - vig)[..., None] * intensity * 0.7) \
        + out * cast * ((1.0 - vig)[..., None] * intensity * 0.7)

    # contrast + saturation lift
    out = (out - 0.5) * (1.0 + 0.12 * intensity) + 0.5
    luma = out @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = luma[..., None] + (out - luma[..., None]) * (1.0 + 0.22 * intensity)

    return Image.fromarray((np.clip(out, 0.0, 1.0) * 255).astype(np.uint8))


def main():
    scale = 0.5
    tiles = []
    for name, intensity, ab, sc, gr, vi in STAGES:
        source = Image.open(os.path.join(MOD, "images", "stages", "trollge", name + ".png"))
        graded = grade(source, intensity, ab, sc, gr, vi, seed=len(name))
        width, height = int(source.width * scale), int(source.height * scale)
        tiles.append((name, source.resize((width, height), Image.LANCZOS),
                      graded.resize((width, height), Image.LANCZOS)))
        print("  graded %-14s intensity %.2f" % (name, intensity))

    pad = 10
    label = 22
    width = tiles[0][1].width
    height = tiles[0][1].height
    canvas = Image.new("RGB", (pad * 5 + width * 2, pad * 4 + (height + label) * 3), (18, 14, 20))
    for row, (name, raw, graded) in enumerate(tiles):
        y = pad + row * (height + label + pad)
        canvas.paste(raw, (pad, y))
        canvas.paste(graded, (pad * 2 + width, y))
    os.makedirs(DOCS, exist_ok=True)
    out = os.path.join(DOCS, "grade.png")
    canvas.save(out, optimize=True)
    print("  -> docs/grade.png (%dx%d)  left: raw backdrop, right: with the shader" % canvas.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
