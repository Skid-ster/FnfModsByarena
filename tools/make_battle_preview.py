#!/usr/bin/env python3
"""Offline atlas composite at approximate 0.7 note scale; not an engine/GPU capture."""
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / 'mods/TrollgeMod'
LANES = [('purple', 'LEFT'), ('blue', 'DOWN'), ('green', 'UP'), ('red', 'RIGHT')]
PANELS = [('default', 'bg'), ('shadow', 'bg_scary'),
          ('corrupt', 'bg_glitch'), ('torn', 'bg_hell')]


def frames(path):
    image = Image.open(str(path) + '.png').convert('RGBA')
    nodes = {node.get('name'): node for node in ET.parse(str(path) + '.xml').getroot()}
    def get(name):
        node = nodes[name]
        x, y, w, h = (int(node.get(k)) for k in ('x', 'y', 'width', 'height'))
        frame = image.crop((x, y, x + w, y + h))
        return frame.resize((round(w * .7), round(h * .7)), Image.Resampling.LANCZOS)
    return get


def main():
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    font = ImageFont.truetype(font_path, 19) if Path(font_path).exists() else ImageFont.load_default()
    result = Image.new('RGB', (1280, 4 * 360))
    for index, (skin, background) in enumerate(PANELS):
        bg = Image.open(MOD / 'images/stages/trollge' / (background + '.png')).convert('RGB')
        panel = ImageOps.fit(bg, (1280, 360), method=Image.Resampling.LANCZOS).convert('RGBA')
        d = ImageDraw.Draw(panel)
        d.rectangle((0, 0, 350, 55), fill=(10, 10, 17, 210))
        d.text((18, 16), skin.upper() + '  /  offline composite', font=font, fill=(240, 240, 245))
        get = frames(MOD / 'images/game/notes' / skin)
        for lane, (color, direction) in enumerate(LANES):
            cx = 760 + lane * 112
            receptor = get('arrow' + direction + '0000')
            panel.alpha_composite(receptor, (cx - receptor.width // 2, 40))
            if lane in (1, 3):
                body = get(color + ' hold piece0000')
                end = get(color + ' hold end0000')
                panel.alpha_composite(body, (cx - body.width // 2, 244))
                panel.alpha_composite(end, (cx - end.width // 2, 244 + body.height))
            note = get(color + '0000')
            panel.alpha_composite(note, (cx - note.width // 2, 175 if lane % 2 == 0 else 220))
        result.paste(panel.convert('RGB'), (0, index * 360))
    result.save(ROOT / 'docs/battle_preview.png', optimize=True)
    print('docs/battle_preview.png: approximate 0.7-scale atlas composite; shaders not rendered')


if __name__ == '__main__':
    main()
