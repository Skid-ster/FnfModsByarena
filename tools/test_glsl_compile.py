#!/usr/bin/env python3
"""Compile both fragment shaders against a minimal Flixel-compatible preamble.

This catches GLSL syntax/type errors on desktop GLSL 330/410 and ES 300. It does
not implement OpenFL's entire source assembler or exercise a GPU/HScript.
Pass a glslangValidator path as the first argument, or put it on PATH.
"""
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SHADERS = ROOT / 'mods' / 'TrollgeMod' / 'shaders'

# Minimal equivalents of the interface and camera helper signatures supplied by
# cne-flixel's FlxGraphicsShader. The engine also supplies colour transforms;
# those are deliberately not claimed to be reproduced by this compile check.
HEADER = '''
in float openfl_Alphav;
in vec2 openfl_TextureCoordv;
uniform vec2 openfl_TextureSize;
uniform sampler2D bitmap;
uniform vec4 _camSize;
out vec4 checkedFragColor;
#define gl_FragColor checkedFragColor
vec2 getCamPos(vec2 p) {
    vec4 s = _camSize / openfl_TextureSize.xyxy;
    return (p - s.xy) / s.zw;
}
vec2 camToOg(vec2 p) {
    vec4 s = _camSize / openfl_TextureSize.xyxy;
    return s.xy + p * s.zw;
}
vec4 checkedTextureCam(sampler2D tex, vec2 pos) {
    return texture(tex, camToOg(pos)) * openfl_Alphav;
}
#define textureCam(bitmap, pos) checkedTextureCam(bitmap, pos)
'''


def assembled(source, profile):
    version = ('#version 300 es\nprecision highp float;\nprecision highp int;\n'
               if profile == 'es300' else '#version ' + ('410' if profile == 'desktop410' else '330') + ' core\n')
    source, count = re.subn(r'^\s*#pragma\s+header\s*$', HEADER, source,
                            count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError('expected an OpenFL header pragma')
    return version + source


def main():
    compiler = sys.argv[1] if len(sys.argv) > 1 else shutil.which('glslangValidator')
    if not compiler or not os.path.isfile(compiler):
        print('glslangValidator missing: provide its path', file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as temp:
        for name in ('crt.frag', 'trollge_vhs.frag'):
            source = (SHADERS / name).read_text(encoding='utf-8')
            for profile in ('desktop330', 'desktop410', 'es300'):
                path = Path(temp) / (name + '.' + profile + '.frag')
                path.write_text(assembled(source, profile), encoding='utf-8')
                result = subprocess.run([compiler, '-S', 'frag', str(path)],
                                        text=True, capture_output=True)
                if result.returncode:
                    print('%s %s FAILED\n%s%s' % (name, profile, result.stdout, result.stderr))
                    return 1
                print('%s %s: compiled' % (name, profile))
    print('Minimal preamble only: test in the actual engine and GPU as well.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
