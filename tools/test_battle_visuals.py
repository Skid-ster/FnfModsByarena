#!/usr/bin/env python3
"""Asset and integration regressions; these do not render HScript or a GPU."""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
import make_noteskin

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / 'mods/TrollgeMod'
COLORS = ('purple', 'blue', 'green', 'red')
DIRECTIONS = ('LEFT', 'DOWN', 'UP', 'RIGHT')


def atlas(skin):
    path = MOD / 'images/game/notes' / skin
    image = Image.open(str(path) + '.png').convert('RGBA')
    nodes = {n.get('name'): n for n in ET.parse(str(path) + '.xml').getroot()}
    def get(name):
        n = nodes[name]
        x, y, w, h = (int(n.get(k)) for k in ('x', 'y', 'width', 'height'))
        return np.asarray(image.crop((x, y, x + w, y + h)))
    return nodes, get


def mean(frame):
    return frame[:, :, :3][frame[:, :, 3] > 166].mean(axis=0)


class BattleVisuals(unittest.TestCase):
    def test_scratch_is_sparse_not_whole_arrow(self):
        mask = Image.new('L', (160, 160), 255)
        a = np.asarray(make_noteskin.scratch(mask, 23))
        self.assertGreater(np.count_nonzero(a), 0)
        self.assertLess(np.count_nonzero(a), a.size * .1)

    def test_note_contrast_colour_and_safe_frame(self):
        for skin in ('default', 'shadow', 'corrupt', 'torn'):
            nodes, get = atlas(skin)
            means = []
            for color, direction in zip(COLORS, DIRECTIONS):
                note = get(color + '0000')
                rec = get('arrow' + direction + '0000')
                means.append(mean(note))
                self.assertGreater((mean(note) - mean(rec)) @ [0.2126, .7152, .0722], 25, skin + color)
            # Even the deliberately muted shadow skin has distinguishable lane hues.
            self.assertGreater(min(np.linalg.norm(means[i] - means[j])
                                   for i in range(4) for j in range(i)), 14, skin)
            for name in nodes:
                if name.startswith('arrow') or ' press' in name or ' confirm' in name or name in [c + '0000' for c in COLORS]:
                    f = get(name)
                    edge = max(f[0, :, 3].max(), f[-1, :, 3].max(), f[:, 0, 3].max(), f[:, -1, 3].max())
                    self.assertLess(edge, 50, (skin, name))

    def test_hold_tile_and_cap_edges_match(self):
        for skin in ('default', 'shadow', 'corrupt', 'torn'):
            _, get = atlas(skin)
            for color in COLORS:
                body = get(color + ' hold piece0000')
                cap = get(color + ' hold end0000')
                np.testing.assert_array_equal(body[0], body[-1], err_msg=skin + color)
                np.testing.assert_array_equal(body[0], cap[0], err_msg=skin + color)

    def test_hud_geometry_and_effect_layers(self):
        stage = (MOD / 'data/stages/trollge.hx').read_text()
        for uniform in ('uAberration', 'uStatic', 'uCurvature', 'uVignette', 'uGlitch'):
            self.assertRegex(stage, r"setFloatOn\(crtHud, '" + uniform + r"', 0\.0\)")
        script = (MOD / 'data/scripts/trollge_song_behavior.hx').read_text()
        for sprite in ('spr', 'staticSpr', 'invertSpr'):
            self.assertIn(sprite + '.cameras = [ps.camGame]', script)
        self.assertNotIn('camHUD.flash(', script)
        self.assertIn('caption.cameras = [ps.camHUD]', script)
        self.assertIn('staticSpr.cameras = [PlayState.instance.camGame]', stage)

    def test_skins_follow_chart_tiers_and_notes_use_engine_prefixes(self):
        import song_layout
        stage = (MOD / 'data/stages/trollge.hx').read_text()
        self.assertIn("event.sprite = path", stage)
        for skin in ('default', 'shadow', 'corrupt', 'torn'):
            nodes, _ = atlas(skin)
            for color, direction in zip(COLORS, DIRECTIONS):
                for name in (color + '0000', color + ' hold piece0000', color + ' hold end0000', 'arrow' + direction + '0000'):
                    self.assertIn(name, nodes)
        for song in song_layout.SONGS:
            # Every custom chart note type must have a corresponding atlas.
            for skin in song_layout.note_types(song):
                self.assertTrue((MOD / 'images/game/notes' / (skin + '.png')).is_file(), skin)


if __name__ == '__main__':
    unittest.main()
