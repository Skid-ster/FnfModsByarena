#!/usr/bin/env python3
"""Measure rendered instrumentals, not note choices; --strict is a mix gate.

Frequency bands are energy shares, calculated per channel in non-overlapping
one-second windows. This cannot judge composition or replace listening tests.
"""
import argparse
import math
from pathlib import Path

import numpy as np
import soundfile as sf
import song_layout as layout

ROOT = Path(__file__).resolve().parent.parent
BANDS = ((20, 80), (80, 250), (250, 2000), (2000, 8000), (8000, 16000))


def measure(path):
    with sf.SoundFile(path) as audio:
        sr = audio.samplerate
        energy = np.zeros(len(BANDS))
        sum_squares = 0.0
        count = 0
        peak = 0.0
        while True:
            block = audio.read(sr, dtype='float64', always_2d=True)
            if not len(block):
                break
            count += block.size
            sum_squares += float(np.sum(block * block))
            peak = max(peak, float(np.max(np.abs(block))))
            window = np.hanning(len(block))[:, None]
            spectrum = np.abs(np.fft.rfft(block * window, axis=0)) ** 2
            freq = np.fft.rfftfreq(len(block), 1 / sr)
            for i, (low, high) in enumerate(BANDS):
                energy[i] += float(spectrum[(freq >= low) & (freq < high)].sum())
    total = float(energy.sum())
    if not count or not total or not sum_squares:
        raise ValueError(f'{path}: silent or empty audio')
    shares = energy / total
    crest = 20 * math.log10(peak / math.sqrt(sum_squares / count))
    return shares, crest, peak


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    print('song             sub    bass   melody presence    air mel/bass crest')
    failures = []
    for song in layout.SONGS:
        path = ROOT / 'mods' / 'TrollgeMod' / 'songs' / song['id'] / 'song' / 'Inst.ogg'
        shares, crest, peak = measure(path)
        bass = shares[0] + shares[1]
        ratio = shares[2] / max(bass, 1e-12)
        print(f"{song['id']:16} " + ' '.join(f'{x * 100:6.1f}' for x in shares)
              + f' {ratio:8.2f} {crest:5.1f}')
        if ratio < 1.0:
            failures.append(f"{song['id']}: melody-band energy below bass (ratio {ratio:.2f})")
        if not 8 <= crest <= 22:
            failures.append(f"{song['id']}: crest factor {crest:.1f} dB outside 8–22 dB")
        if peak > 1.01:
            failures.append(f"{song['id']}: decoded peak {peak:.3f} exceeds 1.01")
    if failures:
        print('\n' + '\n'.join('FAIL: ' + failure for failure in failures))
    else:
        print('\nMelody-band energy exceeds bass and crest factors are in range.')
    return 1 if failures and args.strict else 0


if __name__ == '__main__':
    raise SystemExit(main())
