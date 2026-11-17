#!/usr/bin/env python3
"""Approximate camera framing of every exported battle animation frame.

This models fixed camera targets and the generated, unscaled atlas frames. It
is not an engine screenshot, and cannot cover dynamic zooms/shakes or user HUD
settings. The existing stage preview checks backdrop coverage and idle feet.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import make_stage_preview as P

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS = ROOT / 'mods/TrollgeMod/data/characters'
SIDES = {
    'opponent': ('trollge', 'trollge_glitch', 'trollge_static', 'trollge_final', 'trollge_sad'),
    'player': ('bf_blue', 'bf_smiler', 'bf_glitched', 'bf_super_scary', 'bf_damned'),
}


def main():
    stage = P.read_stage()
    atlases = {}
    for side, names in SIDES.items():
        for name in names:
            root = ET.parse(CHARACTERS / (name + '.xml')).getroot()
            sprite, anims, frames = P.read_character(name)
            first = next(iter(frames.values()))
            size = (int(first['frameWidth']), int(first['frameHeight']))
            # This model is intentionally conservative: if someone adds scale,
            # nonzero anim offsets or nonuniform canvases, it must be updated.
            if root.get('scale', '1') not in ('1', '1.0'):
                raise ValueError('%s: stage bounds model does not cover character scale' % name)
            if any(float(n.get('x', '0')) or float(n.get('y', '0')) for n in root.findall('anim')):
                raise ValueError('%s: stage bounds model does not cover animation offsets' % name)
            if any((int(f['frameWidth']), int(f['frameHeight'])) != size for f in frames.values()):
                raise ValueError('%s: inconsistent frame canvas' % name)
            stage['chars'][side]['frameW'], stage['chars'][side]['frameH'] = size
            atlases[name] = (frames, set(anims.values()))

    worst = (9999, '')
    count = 0
    for camera_side in SIDES:
        for zoom in (stage['zoom'], P.MAX_TIER_ZOOM):
            camera = dict(P.camera_for(stage, camera_side), zoom=zoom)
            for side, names in SIDES.items():
                char = stage['chars'][side]
                for name in names:
                    frames, prefixes = atlases[name]
                    for frame_name, f in frames.items():
                        if not any(frame_name.startswith(prefix) for prefix in prefixes):
                            continue
                        fw = int(f['frameWidth'])
                        w, h = int(f['width']), int(f['height'])
                        ox, oy = -int(f['frameX']), -int(f['frameY'])
                        if side == 'player':
                            ox = fw - ox - w
                        left = (char['x'] + ox - camera['scrollX']) * zoom + P.SCREEN_W * (1 - zoom) / 2
                        top = (char['y'] + oy - camera['scrollY']) * zoom + P.SCREEN_H * (1 - zoom) / 2
                        margin = min(left, top, P.SCREEN_W - left - w * zoom, P.SCREEN_H - top - h * zoom)
                        label = '%s / %s / %s camera / zoom %.2f' % (name, frame_name, camera_side, zoom)
                        worst = min(worst, (margin, label))
                        count += 1
    print('%d projected animation frames checked; worst margin %.1f px: %s' % (count, *worst))
    if worst[0] < P.MIN_MARGIN:
        print('FAIL: minimum expected %d px' % P.MIN_MARGIN)
        return 1
    print('Approximate static framing passed; actual camera motion needs engine testing.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
