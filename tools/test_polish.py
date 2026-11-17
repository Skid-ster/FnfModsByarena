#!/usr/bin/env python3
"""Regression checks for the battle presentation; does not run HScript."""
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import make_art
import make_noteskin

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / 'mods' / 'TrollgeMod'


def atlas_frame(image, nodes, name):
    node = nodes[name]
    x, y, width, height = (int(node[key]) for key in ('x', 'y', 'width', 'height'))
    return np.asarray(image.crop((x, y, x + width, y + height)))


def mean_rgb(frame):
    visible = frame[:, :, 3] > 166
    if not np.any(visible):
        raise AssertionError('frame has no visible pixels')
    return frame[:, :, :3][visible].mean(axis=0)


class BattlePolishTests(unittest.TestCase):
    def test_character_extensions_and_chart_clock(self):
        for name in ('trollge', 'trollge_glitch', 'trollge_static', 'trollge_final', 'trollge_sad'):
            root = ET.parse(MOD / 'data' / 'characters' / (name + '.xml')).getroot()
            self.assertEqual([x.get('script') for x in root.findall('extension')].count('trollge_behavior'), 1, name)
        stage = (MOD / 'data/stages/trollge.hx').read_text()
        self.assertIn('songSeconds - t', stage)
        self.assertNotIn('songClock - t', stage)
        self.assertIn('Conductor.songPosition % Conductor.crochet', stage)
        self.assertIn('30.0 : (scareTier >= 6 ? 16.0 : 6.0)', stage)
        behavior = (MOD / 'data/scripts/trollge_behavior.hx').read_text()
        self.assertIn('FlxG.random.bool(18.0)', behavior)
        self.assertIn('event.cancel()', behavior)
        song_script = (MOD / 'data/scripts/trollge_song_behavior.hx').read_text()
        self.assertIn('newChar.cameraOffset.set(old.cameraOffset.x, old.cameraOffset.y)', song_script)
        self.assertIn('FlxTween.cancelTweensOf(invertSpr)', song_script)

    def test_finale_notes_are_brighter_and_distinct(self):
        atlas = MOD / 'images/game/notes/torn'
        with Image.open(str(atlas) + '.png') as image:
            image = image.convert('RGBA')
            nodes = {n.attrib['name']: n.attrib for n in ET.parse(str(atlas) + '.xml').getroot()}
            means = []
            for colour, direction in zip(('purple', 'blue', 'green', 'red'), ('LEFT', 'DOWN', 'UP', 'RIGHT')):
                note = mean_rgb(atlas_frame(image, nodes, colour + '0000'))
                receptor = mean_rgb(atlas_frame(image, nodes, 'arrow' + direction + '0000'))
                luminance = np.array([0.2126, 0.7152, 0.0722])
                self.assertGreater(np.dot(note - receptor, luminance), 15, colour)
                means.append(note)
            # The previous all-red skin erased lane colour. Require the lanes to
            # remain distinguishable in colour as well as by arrow direction.
            for i in range(4):
                for j in range(i):
                    self.assertGreater(np.linalg.norm(means[i] - means[j]), 25)

    def test_countdown_fits_canvas(self):
        for name in ('ready', 'set', 'go'):
            with Image.open(MOD / 'images/game' / (name + '.png')) as image:
                left, top, right, bottom = image.getchannel('A').getbbox()
                self.assertGreaterEqual(left, 5, name)
                self.assertGreaterEqual(top, 5, name)
                self.assertLessEqual(right, image.width - 5, name)
                self.assertLessEqual(bottom, image.height - 5, name)

    def test_seeded_textures_repeat(self):
        source = make_noteskin.arrow_frame(160, (142, 59, 255), 'note', rotate=90)
        for transform in (make_noteskin.drained, make_noteskin.corrupt, make_noteskin.torn):
            self.assertEqual(transform(source, 47).tobytes(), transform(source, 47).tobytes())
        mask = Image.new('L', (160, 160), 255)
        self.assertEqual(make_noteskin.jagged_edge(mask, 3, 5).tobytes(),
                         make_noteskin.jagged_edge(mask, 3, 5).tobytes())
        image = Image.new('RGB', (100, 90), (30, 15, 20))
        self.assertEqual(make_art.grain(image, .1, seed=8008).tobytes(),
                         make_art.grain(image, .1, seed=8008).tobytes())
        self.assertNotEqual(make_art.grain(image, .1, seed=8008).tobytes(),
                            make_art.grain(image, .1, seed=8009).tobytes())


if __name__ == '__main__':
    unittest.main()
