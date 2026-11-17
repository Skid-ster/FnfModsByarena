#!/usr/bin/env python3
"""Check decoded instrumental + vocals at equal gain (not engine playback).

Peak estimation uses 4x Catmull-Rom interpolation, not an ITU BS.1770 meter.
Run after rendering; individual clean files can still overload when summed.
"""
import os
import sys
import numpy as np
import soundfile as sf
import song_layout as L
from lib_dsp import true_peak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    failed = False
    for song in L.SONGS:
        folder = os.path.join(ROOT, 'mods', 'TrollgeMod', 'songs', song['id'], 'song')
        inst, sr = sf.read(os.path.join(folder, 'Inst.ogg'), always_2d=True)
        voice, vr = sf.read(os.path.join(folder, 'Voices.ogg'), always_2d=True)
        if sr != vr or inst.shape != voice.shape or inst.shape[1] != 2:
            print(song['id'], 'incompatible stem formats')
            failed = True
            continue
        mix = inst + voice
        peak = max(true_peak(mix[:, 0]), true_peak(mix[:, 1]))
        print('%-16s estimated combined peak %6.2f dBFS' %
              (song['id'], 20 * np.log10(max(peak, 1e-12))))
        if not np.isfinite(peak) or peak > 0.95:
            failed = True
    if failed:
        print('Combined stem peak check failed.')
        return 1
    print('All decoded equal-gain sums pass. Actual engine gain and playback need testing.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
