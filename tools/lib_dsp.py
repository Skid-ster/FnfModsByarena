"""
Tiny dependency-light DSP helpers (numpy only) used to synthesise the
Super Scary Trollge soundtrack and SFX.

Everything is deterministic: same seed -> same bytes, so CI can rebuild the
audio assets and get the same OGG files.
"""

import numpy as np

SR = 44100


# --------------------------------------------------------------------------- #
# Oscillators
# --------------------------------------------------------------------------- #

def _phase(freq, n, sr=SR, phase0=0.0):
    if np.isscalar(freq):
        return phase0 + 2 * np.pi * freq * np.arange(n) / sr
    return phase0 + 2 * np.pi * np.cumsum(freq) / sr


def sine(freq, n, sr=SR, phase0=0.0):
    return np.sin(_phase(freq, n, sr, phase0))


def saw(freq, n, sr=SR, phase0=0.0):
    return 2.0 * ((_phase(freq, n, sr, phase0) / (2 * np.pi)) % 1.0) - 1.0


def square(freq, n, sr=SR, phase0=0.0, duty=0.5):
    return np.where(((_phase(freq, n, sr, phase0) / (2 * np.pi)) % 1.0) < duty, 1.0, -1.0)


def noise(n, seed=0):
    return np.random.default_rng(seed).uniform(-1.0, 1.0, n)


def midi_to_hz(midi):
    if np.isscalar(midi):
        return 440.0 * 2.0 ** ((midi - 69) / 12.0)
    return 440.0 * 2.0 ** ((np.asarray(midi, dtype=np.float64) - 69) / 12.0)


# --------------------------------------------------------------------------- #
# Envelopes & filters
# --------------------------------------------------------------------------- #

def adsr(n, attack=0.005, decay=0.08, sustain=0.6, release=0.2, sr=SR):
    a = max(1, int(attack * sr))
    d = max(1, int(decay * sr))
    r = max(1, int(release * sr))
    s = max(0, n - a - d - r)
    env = np.concatenate(
        [
            np.linspace(0.0, 1.0, a, endpoint=False),
            np.linspace(1.0, sustain, d, endpoint=False),
            np.full(s, sustain),
            np.linspace(sustain, 0.0, r),
        ]
    )
    return env[:n] if len(env) >= n else np.pad(env, (0, n - len(env)))


def exp_decay(n, tau=0.2, sr=SR):
    return np.exp(-np.arange(n) / (tau * sr))


def _fft_shape(x, magnitude_fn, sr=SR):
    """Apply a zero-phase magnitude response to `x` via FFT (fast + clean)."""
    n = len(x)
    if n == 0:
        return x
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    spec *= magnitude_fn(np.maximum(freqs, 1e-9))
    return np.fft.irfft(spec, n)


def lowpass(x, cutoff_hz, sr=SR, order=2):
    """Butterworth-magnitude lowpass."""
    def mag(f):
        return 1.0 / np.sqrt(1.0 + (f / cutoff_hz) ** (2 * order))

    return _fft_shape(x, mag, sr)


def highpass(x, cutoff_hz, sr=SR, order=2):
    def mag(f):
        return 1.0 / np.sqrt(1.0 + (cutoff_hz / f) ** (2 * order))

    return _fft_shape(x, mag, sr)


def bandpass(x, low_hz, high_hz, sr=SR):
    return lowpass(highpass(x, low_hz, sr), high_hz, sr)


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive)


def bitcrush(x, bits=6, hold=4):
    step = 2.0 ** (bits - 1)
    y = np.round(x * step) / step
    if hold > 1:
        n = len(y)
        y = np.repeat(y[::hold], hold)[:n]
    return y


# --------------------------------------------------------------------------- #
# Space
# --------------------------------------------------------------------------- #

def _comb(x, delay_s, feedback, damp=0.3, sr=SR):
    d = max(1, int(delay_s * sr))
    y = np.zeros_like(x)
    # y[n] = x[n] + feedback * lowpassed(y[n-d])
    for start in range(0, len(x), d):
        end = min(start + d, len(x))
        shifted = y[start - d:end - d] if start >= d else np.zeros(end - start)
        y[start:end] = x[start:end] + feedback * shifted * (1.0 - damp)
    return y


def _allpass(x, delay_s, gain=0.5, sr=SR):
    d = max(1, int(delay_s * sr))
    y = np.zeros_like(x)
    for start in range(0, len(x), d):
        end = min(start + d, len(x))
        xd = x[start - d:end - d] if start >= d else np.zeros(end - start)
        yd = y[start - d:end - d] if start >= d else np.zeros(end - start)
        y[start:end] = -gain * x[start:end] + xd + gain * yd
    return y


def reverb(x, wet=0.25, size=0.8, damp=0.35, sr=SR):
    """Small Schroeder reverb -- cheap, plenty for a mod soundtrack."""
    combs = [_comb(x, d, 0.72 + 0.12 * size, damp, sr) for d in (0.0297, 0.0371, 0.0411, 0.0437)]
    mix = sum(combs) / len(combs)
    mix = _allpass(mix, 0.005, 0.7, sr)
    mix = _allpass(mix, 0.0017, 0.7, sr)
    return (1.0 - wet) * x + wet * mix


def delay(x, delay_s, feedback=0.3, mix=0.3, sr=SR):
    d = max(1, int(delay_s * sr))
    out = np.zeros_like(x)
    tap = np.zeros_like(x)
    for start in range(0, len(x), d):
        end = min(start + d, len(x))
        prev = out[start - d:end - d] if start >= d else np.zeros(end - start)
        out[start:end] = x[start:end] + feedback * prev
        tap[start:end] = prev
    return (1.0 - mix) * x + mix * out


# --------------------------------------------------------------------------- #
# Buffer helpers
# --------------------------------------------------------------------------- #

def empty(seconds, sr=SR):
    return np.zeros(int(round(seconds * sr)), dtype=np.float64)


def add_at(buf, signal, at_seconds, gain=1.0, sr=SR):
    start = int(round(at_seconds * sr))
    if start >= len(buf):
        return buf
    end = min(len(buf), start + len(signal))
    buf[start:end] += gain * signal[: end - start]
    return buf


def normalize(x, peak=0.89):
    m = np.max(np.abs(x)) if len(x) else 0.0
    return x if m == 0 else x * (peak / m)


def fade(x, in_s=0.01, out_s=0.02, sr=SR):
    y = x.copy()
    a = min(len(y) // 2, int(in_s * sr))
    b = min(len(y) // 2, int(out_s * sr))
    if a:
        y[:a] *= np.linspace(0, 1, a)
    if b:
        y[-b:] *= np.linspace(1, 0, b)
    return y


def write_ogg(path, stereo, sr=SR):
    """Write a float stereo buffer (-1..1) as OGG/Vorbis.

    The buffer is streamed in chunks on purpose: libsndfile's Vorbis encoder
    segfaults on very large single-shot writes (e.g. a full 104 s track).
    """
    import soundfile as sf

    data = np.stack([stereo[0], stereo[1]], axis=1)
    data = np.clip(np.nan_to_num(data), -1.0, 1.0).astype(np.float32)
    with sf.SoundFile(path, "w", samplerate=sr, channels=2, format="OGG", subtype="VORBIS") as f:
        step = 32768
        for start in range(0, len(data), step):
            f.write(data[start:start + step])
    return path
