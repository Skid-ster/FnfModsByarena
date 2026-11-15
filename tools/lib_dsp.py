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
    # In place: `spec *= mag` rebinds when `mag` is a float, which silently
    # skipped the whole filter (this is why the first formant bank did nothing).
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


def resonator(x, centre_hz, bandwidth_hz, gain=1.0, sr=SR):
    """One vocal-tract resonance, as a 2-pole filter's magnitude response.

    ``|H(f)| = gain / sqrt((1 - (f/f0)^2)^2 + (f / (Q f0))^2)`` with
    ``Q = f0 / bandwidth``. Unlike a band-limited bump this is what a real
    formant does: it is roughly unity well below the centre (so the fundamental
    of the voice survives), peaks at ``f0`` with a gain of about ``Q``, and falls
    at 12 dB/octave above it. Summing a few of these is a vowel.
    """
    n = len(x)
    if n == 0:
        return x
    freqs = np.maximum(np.fft.rfftfreq(n, 1.0 / sr), 1e-9)
    ratio = freqs / max(centre_hz, 1.0)
    q = max(centre_hz, 1.0) / max(bandwidth_hz, 1.0)
    mag = gain / np.sqrt((1.0 - ratio ** 2) ** 2 + (ratio / q) ** 2)
    return np.fft.irfft(np.fft.rfft(x) * mag, n)


def formant_bank(x, formants, sr=SR):
    """A parallel formant bank -- one vowel.

    Each formant is a resonant peak that passes the source near its centre and
    rolls everything else off, then the peaks are summed with their gains. The
    sum is the vowel's spectral envelope, so the output sounds like a sung
    syllable rather than a source with echoes bolted on (which is what the
    previous version of this mod shipped, and why its voices buzzed).
    """
    out = np.zeros_like(x)
    for centre, bandwidth, gain in formants:
        out += resonator(x, centre, bandwidth, gain, sr)
    return out / max(1e-9, float(np.max(np.abs(out))))


def smooth_lowpass(x, cutoff_hz, sr=SR, order=2, resonance=0.0):
    """Butterworth lowpass with an optional gentle peak at the cutoff.

    Synths sound "warm" when the filter is not a brick wall and the cutoff
    moves; this is the static half of that (the movement is per note).
    """
    out = lowpass(x, cutoff_hz, sr, order)
    if resonance > 0.0:
        out = out + resonator(x, cutoff_hz, cutoff_hz * 0.9, 1.0 + resonance, sr) * resonance
    return out


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive)


def eq_curve(x, points, sr=SR):
    """Zero-phase graphic EQ from (Hz, dB) breakpoints (log-frequency interpolation).

    Used for the master bus: tame the sub, lift the presence/air band so the
    mix is not a wall of bass, which is exactly what the audit measures.
    """
    freqs_hz = [max(1.0, p[0]) for p in points]
    gains_db = np.array([p[1] for p in points], dtype=np.float64)

    def mag(f):
        db = np.interp(np.log10(np.maximum(f, 1e-9)), np.log10(freqs_hz), gains_db)
        return 10.0 ** (db / 20.0)

    return _fft_shape(x, mag, sr)


def pan(x, position):
    """Constant-power pan: -1 = hard left, 0 = centre, +1 = hard right."""
    angle = (position + 1.0) * np.pi / 4.0
    return x * float(np.cos(angle)), x * float(np.sin(angle))


def haas(x, delay_s=0.012, sr=SR, right=True):
    """Delay one channel slightly: instant, decorrelated width for pads/leads."""
    n = max(1, int(delay_s * sr))
    left = np.concatenate([x, np.zeros(n)])[: len(x)]
    right_ch = np.concatenate([np.zeros(n), x])[: len(x)]
    return (left, right_ch) if not right else (right_ch, left)


def sidechain(target, key, depth=0.45, release_s=0.16, sr=SR):
    """Duck `target` with the envelope of `key` (mono buffers)."""
    hop = int(0.005 * sr)
    frames = max(1, len(key) // hop)
    env = np.array([np.max(np.abs(key[i * hop:(i + 1) * hop])) for i in range(frames)])
    # Release-smoothed envelope, one-pole.
    smoothed = np.zeros_like(env)
    coeff = np.exp(-hop / (release_s * sr))
    value = 0.0
    for i, sample in enumerate(env):
        value = max(sample, value * coeff)
        smoothed[i] = value
    gain = 1.0 - depth * np.clip(smoothed / (smoothed.max() or 1.0), 0.0, 1.0)
    curve = np.repeat(gain, hop)[: len(target)]
    if len(curve) < len(target):
        curve = np.pad(curve, (0, len(target) - len(curve)), constant_values=1.0)
    return target * curve


def limiter(x, ceiling=0.94, sr=SR, block=64, attack_ms=6.0):
    """Block-based peak limiter (memory-cheap: no look-ahead ring buffers)."""
    peak = np.abs(x)
    nb = max(1, len(x) // block)
    blocks = peak[: nb * block].reshape(nb, block).max(axis=1)
    gain = np.minimum(1.0, ceiling / np.maximum(blocks, 1e-6))
    smooth = max(1, int((attack_ms / 1000.0) * sr / block))
    if smooth > 1:
        kernel = np.ones(smooth) / smooth
        gain = np.convolve(gain, kernel, mode="same")
    curve = np.repeat(gain, block)
    if len(curve) < len(x):
        curve = np.pad(curve, (0, len(x) - len(curve)), constant_values=1.0)
    return soft_clip(x * curve[: len(x)], 1.0)


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


def compress(x, threshold_db=-21.0, ratio=2.6, attack_ms=9.0, release_ms=170.0,
             sr=SR, block=128, makeup_db=0.0):
    """Block-RMS compressor: raises perceived loudness without flattening the kick."""
    import math

    nb = max(1, len(x) // block)
    blocks = x[: nb * block].reshape(nb, block)
    level = np.sqrt(np.mean(blocks ** 2, axis=1))
    level_db = 20.0 * np.log10(np.maximum(level, 1e-9))
    over = np.maximum(0.0, level_db - threshold_db)
    target = -over * (1.0 - 1.0 / ratio)

    attack = math.exp(-block / ((attack_ms / 1000.0) * sr))
    release = math.exp(-block / ((release_ms / 1000.0) * sr))
    smoothed = np.zeros_like(target)
    previous = 0.0
    for i, value in enumerate(target):
        coeff = attack if value < previous else release     # more reduction = faster
        previous = value + (previous - value) * coeff
        smoothed[i] = previous

    curve = np.repeat(10.0 ** ((smoothed + makeup_db) / 20.0), block)
    if len(curve) < len(x):
        curve = np.pad(curve, (0, len(x) - len(curve)), constant_values=1.0)
    return x * curve[: len(x)]


def widen(left, right, amount=1.9, crossover=200.0, sr=SR):
    """Mid/side widener with a mono bass: the standard trick that makes a
    centre-heavy drum mix feel stereo without smearing the low end."""
    lo_l, lo_r = lowpass(left, crossover, sr), lowpass(right, crossover, sr)
    hi_l, hi_r = left - lo_l, right - lo_r
    mid = 0.5 * (hi_l + hi_r)
    side = 0.5 * (hi_l - hi_r) * amount
    lo_mid = 0.5 * (lo_l + lo_r)
    return mid + side + lo_mid, mid - side + lo_mid


def true_peak(x):
    """Inter-sample peak via 4x Catmull-Rom interpolation (mono buffer)."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 8:
        return float(np.max(np.abs(x))) if len(x) else 0.0
    p0 = np.concatenate(([x[0]], x[:-2], [x[-1]]))[: len(x)]
    p1 = x
    p2 = np.concatenate((x[1:], [x[-1]]))[: len(x)]
    p3 = np.concatenate((x[2:], [x[-1], x[-1]]))[: len(x)]
    peak = float(np.max(np.abs(x)))
    for t in (0.25, 0.5, 0.75):
        value = 0.5 * (2.0 * p1 + (-p0 + p2) * t
                       + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t * t
                       + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t * t * t)
        peak = max(peak, float(np.max(np.abs(value))))
    return peak


def dc_block(x, cutoff_hz=24.0, sr=SR):
    """Remove DC / sub-rumble that soft clipping introduces."""
    return highpass(x - np.mean(x), cutoff_hz, sr)


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
