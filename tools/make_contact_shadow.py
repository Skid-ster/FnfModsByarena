#!/usr/bin/env python3
"""Generate the soft, transparent world-space contact shadow used by the stage."""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'mods/TrollgeMod/images/stages/trollge/contact_shadow.png'


def make_shadow():
    w, h = 400, 64
    x = (np.arange(w) + .5 - w / 2) / (w / 2)
    y = (np.arange(h) + .5 - h / 2) / (h / 2)
    # Smooth compact falloff: transparent at edges, dense near the feet.
    radius = (x[None, :] ** 2 + y[:, None] ** 2)
    alpha = np.clip((1 - radius), 0, 1) ** 2 * 125
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = (4, 2, 8)
    rgba[:, :, 3] = alpha.astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA')


if __name__ == '__main__':
    OUT.parent.mkdir(parents=True, exist_ok=True)
    make_shadow().save(OUT, optimize=True)
    print('->', OUT.relative_to(ROOT))
