#!/usr/bin/env python3
"""Regression checks for the battle presentation; does not run HScript."""
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import make_art
import make_menu
import make_hud
import make_contact_shadow
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

    def test_menu_frames_have_stable_engine_geometry(self):
        for option, label in make_menu.OPTIONS:
            generated = make_menu.button_frames(option, label)
            self.assertEqual([name for name, _ in generated], [
                option + ' basic0000', option + ' basic0001',
                option + ' white0000', option + ' white0001'])
            self.assertTrue(all(image.size == (392, 48) for _, image in generated))
            self.assertEqual(generated[0][1].tobytes(), generated[1][1].tobytes())
            self.assertEqual(generated[2][1].tobytes(), generated[3][1].tobytes())
            self.assertNotEqual(generated[0][1].tobytes(), generated[2][1].tobytes())
            atlas = MOD / 'images/menus/mainmenu' / (option + '.png')
            nodes = {n.attrib['name']: n.attrib for n in
                     ET.parse(atlas.with_suffix('.xml')).getroot()}
            with Image.open(atlas) as sheet:
                sheet = sheet.convert('RGBA')
                for name, expected in generated:
                    frame = atlas_frame(sheet, nodes, name)
                    self.assertEqual((frame.shape[1], frame.shape[0]), expected.size)
                    self.assertGreater(frame[:, :, 3].max(), 0)
            # Selected marker exists even without relying on colour alone.
            self.assertEqual(generated[0][1].getpixel((4, 24))[3], 0)
            self.assertGreater(generated[2][1].getpixel((4, 24))[3], 0)
        self.assertLess(make_menu.IDLE_H, make_menu.SCREEN_H * make_menu.ROW_STEP)
        script = (MOD / 'data/states/MainMenuState/LIB_TrollgeMod.hx').read_text()
        for expected in ('0.065', '0.50 + i * 0.070', '0.072', '0.205',
                         "Reflect.field(state, 'menuItems')", 'function postUpdate'):
            self.assertIn(expected, script)
        self.assertEqual((MOD / 'data/config/menuItems.txt').read_text().splitlines(),
                         [name for name, _ in make_menu.OPTIONS])
        with Image.open(MOD / 'images/menus/title_logo.png') as logo:
            self.assertEqual(logo.size, (370, 165))
        self.assertLess(make_menu.LOGO_Y * 720 + make_menu.LOGO_H, make_menu.MENU_Y * 720)
        self.assertLess((make_menu.MENU_Y + 3 * make_menu.ROW_STEP) * 720 + 48, 660)

    def test_menu_text_contrast_and_countdown_casing(self):
        # Verify solid label colours against a conservative sample of the
        # scaled backdrop around every row. Not a test of GPU rendering,
        # antialiasing, engine parallax or accessibility compliance.
        bg = Image.open(MOD / 'images/menus/menuBG.png').convert('RGB')
        bg = bg.resize((round(1286 * 1.15), round(730 * 1.15)))
        x, y = (bg.width - 1280) // 2, (bg.height - 720) // 2
        pixels = np.asarray(bg.crop((x + 100, y + 320, x + 390, y + 610))) / 255.0
        linear = np.where(pixels <= .04045, pixels / 12.92, ((pixels + .055) / 1.055) ** 2.4)
        peak = (linear[:, :, 0] * .2126 + linear[:, :, 1] * .7152 + linear[:, :, 2] * .0722).max()
        for text in (make_menu.LABEL, make_menu.LABEL_SELECTED):
            rgb = np.asarray(text[:3]) / 255.0
            lin = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
            lum = float(lin @ np.array([.2126, .7152, .0722]))
            self.assertGreaterEqual((lum + .05) / (peak + .05), 4.5)
        self.assertEqual(make_hud.build_health_bar().size, (760, 34))
        for name in ('ready', 'set', 'go'):
            with Image.open(MOD / 'images/game' / (name + '.png')) as img:
                self.assertEqual(img.size, (420, 180))
                self.assertEqual(img.getpixel((20, 20))[3], 247)
                self.assertEqual(img.getpixel((0, 0))[3], 0)

    def test_contact_shadows_and_bounded_camera_response(self):
        with Image.open(MOD / 'images/stages/trollge/contact_shadow.png') as shadow:
            self.assertEqual(shadow.convert('RGBA').tobytes(), make_contact_shadow.make_shadow().tobytes())
            alpha = shadow.getchannel('A')
            self.assertEqual(alpha.getpixel((0, 0)), 0)
            self.assertGreater(alpha.getpixel((200, 32)), 100)
        root = ET.parse(MOD / 'data/stages/trollge.xml').getroot()
        nodes = list(root)
        shadows = [n for n in nodes if n.get('sprite') == 'contact_shadow']
        self.assertEqual(len(shadows), 2)
        self.assertLess(max(nodes.index(n) for n in shadows),
                        min(nodes.index(n) for n in nodes if n.tag in ('dad', 'boyfriend')))
        stage = (MOD / 'data/stages/trollge.hx').read_text()
        self.assertIn('defaultCamZoom + 0.018', stage)
        self.assertIn('if (cam.zoom < ceiling)', stage)
        self.assertIn('meta != null && !meta.needsVoices', stage)
        self.assertIn('curBeat % 4 == 0', stage)
        script = (MOD / 'data/scripts/trollge_song_behavior.hx').read_text()
        self.assertNotIn('ps.camHUD.shake(', script)

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
