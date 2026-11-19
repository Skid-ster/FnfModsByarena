#!/usr/bin/env python3
"""Export equal-gain stem-sum excerpts around each song's first breakdown.

These are listening aids, not an engine mix; no loudness matching is applied.
Run after rendering the final songs: python3 tools/make_music_previews.py
"""
from pathlib import Path
import numpy as np
import soundfile as sf
import song_layout as L
from lib_dsp import write_ogg, true_peak

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / 'mods/TrollgeMod/songs'
OUT = ROOT / 'previews/music'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for song in L.SONGS:
        folder = MOD / song['id'] / 'song'
        inst, sr = sf.read(folder / 'Inst.ogg', always_2d=True)
        voice, vr = sf.read(folder / 'Voices.ogg', always_2d=True)
        if inst.shape != voice.shape or sr != vr:
            raise ValueError('incompatible stems: ' + song['id'])
        midpoint = next(sec['time'] / 1000 for sec in L.sections(song) if sec['role'] == 'break')
        start = max(0., midpoint - 7.)
        end = min(start + 32., len(inst) / sr)
        excerpt = inst[int(start * sr):int(end * sr)] + voice[int(start * sr):int(end * sr)]
        # Even small Vorbis conversion overshoots should not clip this preview.
        excerpt *= .94
        ramp = min(int(.12 * sr), len(excerpt) // 2)
        excerpt[:ramp] *= np.linspace(0, 1, ramp)[:, None]
        excerpt[-ramp:] *= np.linspace(1, 0, ramp)[:, None]
        path = OUT / (song['id'] + '.ogg')
        write_ogg(str(path), (excerpt[:, 0], excerpt[:, 1]), sr=sr)
        decoded, _ = sf.read(path, always_2d=True)
        peak = max(true_peak(decoded[:, 0]), true_peak(decoded[:, 1]))
        if peak > 1.0:
            raise ValueError('decoded preview peak exceeds full scale: ' + song['id'])
        print('%-16s %.1f–%.1fs | decoded peak %.2f dBFS' %
              (song['id'], start, end, 20 * np.log10(max(peak, 1e-12))))


if __name__ == '__main__':
    main()
