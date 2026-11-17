#!/usr/bin/env python3
"""Build the cinematic main-menu artwork and a static layout approximation.

The user-provided image informed composition, lighting and hierarchy. The scene
in art_src/menu_scene.png is an AI-generated original; buttons and title are
rendered here. Codename's own MainMenuState still handles all input and choice
transitions. The injected LIB_TrollgeMod state script positions these assets;
without that engine feature the stock menu uses a centred, widely spaced layout.
"""
import os
import random
import sys
import xml.etree.ElementTree as ET
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, 'mods', 'TrollgeMod')
MENUS = os.path.join(MOD, 'images', 'menus')
MAINMENU = os.path.join(MENUS, 'mainmenu')
DOCS = os.path.join(ROOT, 'docs')
SCENE = os.path.join(ROOT, 'art_src', 'menu_scene.png')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_SERIF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
BG_W, BG_H = 1286, 730
ROW_W, IDLE_H = 392, 48
SCREEN_W, SCREEN_H = 1280, 720
LOGO_W, LOGO_H = 370, 165
# Must match the postCreate/postUpdate layout in LIB_TrollgeMod.hx.
MENU_X = .065
MENU_Y = .50
ROW_STEP = .070
LOGO_X, LOGO_Y = .072, .205
OPTIONS = [('story mode', 'STORY MODE'), ('freeplay', 'FREEPLAY'),
           ('options', 'OPTIONS'), ('credits', 'CREDITS')]
LABEL = (194, 192, 191, 255)
LABEL_SELECTED = (255, 247, 239, 255)


def button_frames(option, label):
    """The same size for every state: small independent mouse hitboxes."""
    font = ImageFont.truetype(FONT, 25)
    frames = []
    for selected in (False, True):
        for i in range(2):
            img = Image.new('RGBA', (ROW_W, IDLE_H), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            if selected:
                # Shape plus brightness; no looping flicker or colour-only focus.
                d.polygon([(2, 16), (10, 24), (2, 32)], fill=(222, 79, 75, 255))
                d.line((22, 42, 100, 42), fill=(184, 55, 55, 235), width=2)
            x = 22
            for ch in label:
                d.text((x, 6), ch, font=font,
                       fill=LABEL_SELECTED if selected else LABEL,
                       stroke_width=1, stroke_fill=(0, 0, 0, 255))
                x += font.getlength(ch) + 2.5
            prefix = 'white' if selected else 'basic'
            frames.append(('%s %s%04d' % (option, prefix, i), img))
    return frames


def write_atlas(option, frames):
    pad = 2
    width = ROW_W + pad * 2
    height = sum(img.height + pad * 2 for _, img in frames)
    sheet = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    root = ET.Element('TextureAtlas', {'imagePath': option + '.png'})
    y = pad
    for name, img in frames:
        sheet.alpha_composite(img, (pad, y))
        ET.SubElement(root, 'SubTexture', {'name': name, 'x': str(pad), 'y': str(y),
                      'width': str(img.width), 'height': str(img.height)})
        y += img.height + pad * 2
    png, xml = (os.path.join(MAINMENU, option + ext) for ext in ('.png', '.xml'))
    sheet.save(png)
    ET.indent(root, space='\t')
    ET.ElementTree(root).write(xml, encoding='utf-8', xml_declaration=True)
    return png, xml


def make_logo():
    """Original compact wordmark; scratches affect the title, never menu labels."""
    mask = Image.new('L', (LOGO_W, LOGO_H), 0)
    d = ImageDraw.Draw(mask)
    small = ImageFont.truetype(FONT_BOLD, 23)
    title = ImageFont.truetype(FONT_SERIF, 65)
    d.text((6, 0), 'SUPER SCARY', font=small, fill=235, stroke_width=0)
    d.text((1, 24), 'TROLLGE', font=title, fill=248, stroke_width=1)
    d.text((7, 113), 'THE INCIDENT', font=ImageFont.truetype(FONT, 16), fill=185)
    # Sparse deterministic wear through the large word, like a printed poster.
    rng = random.Random(9103)
    damage = Image.new('L', mask.size, 255)
    dd = ImageDraw.Draw(damage)
    for _ in range(110):
        x, y = rng.randrange(7, 350), rng.randrange(45, 96)
        dd.line((x, y, x + rng.randint(1, 9), y + rng.choice([-1, 0, 1])),
                fill=rng.randint(75, 190), width=1)
    mask = ImageChops.multiply(mask, damage)
    image = Image.new('RGBA', mask.size, (244, 239, 230, 0))
    image.putalpha(mask)
    return image


def make_backdrop():
    """Scale generated scene and add a quiet black falloff under the menu."""
    bg = Image.open(SCENE).convert('RGB').resize((BG_W, BG_H), Image.Resampling.LANCZOS).convert('RGBA')
    # Keep the left text area stable across engine background parallax.
    alpha = Image.new('L', (BG_W, 1))
    alpha.putdata([int(155 * max(0, min(1, (0.49 - x / BG_W) / .28))) for x in range(BG_W)])
    shade = Image.new('RGBA', (BG_W, BG_H), (0, 0, 0, 0))
    shade.putalpha(alpha.resize((BG_W, BG_H)))
    bg = Image.alpha_composite(bg, shade)
    path = os.path.join(MENUS, 'menuBG.png')
    bg.convert('RGB').save(path, optimize=True)
    return path


def make_preview(frames_by_option, selected=0, out_name='menu_preview.png'):
    """Approximate the injected layout; camera follow/version text are omitted."""
    bg = Image.open(os.path.join(MENUS, 'menuBG.png')).convert('RGBA')
    bg = bg.resize((round(BG_W * 1.15), round(BG_H * 1.15)), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (SCREEN_W, SCREEN_H), (0, 0, 0, 255))
    canvas.alpha_composite(bg, ((SCREEN_W - bg.width) // 2, (SCREEN_H - bg.height) // 2))
    canvas.alpha_composite(make_logo(), (round(SCREEN_W * LOGO_X), round(SCREEN_H * LOGO_Y)))
    for i, (option, _) in enumerate(OPTIONS):
        img = frames_by_option[option][2 if i == selected else 0][1]
        canvas.alpha_composite(img, (round(SCREEN_W * MENU_X), round(SCREEN_H * (MENU_Y + ROW_STEP * i))))
    path = os.path.join(DOCS, out_name)
    canvas.convert('RGB').save(path, optimize=True)
    return path


def main():
    os.makedirs(MAINMENU, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    frames = {option: button_frames(option, label) for option, label in OPTIONS}
    for option, _ in OPTIONS:
        for path in write_atlas(option, frames[option]):
            print('  ->', os.path.relpath(path, ROOT))
    logo_path = os.path.join(MENUS, 'title_logo.png')
    make_logo().save(logo_path, optimize=True)
    print('  ->', os.path.relpath(logo_path, ROOT))
    for path in (make_backdrop(), make_preview(frames)):
        print('  ->', os.path.relpath(path, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
