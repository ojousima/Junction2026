"""Physics-informed audio features for an air-source heat pump outdoor unit.

An outdoor unit makes two kinds of sound we know in advance:
- the inverter compressor: tonal lines whose frequency follows compressor speed
  (this is also our best estimate of the operating point),
- the fan: broadband airflow noise, modulated at the fan rotation rate, plus a
  blade-pass tone. Imbalance or a loose mount shows up as stronger modulation or
  as clicks once per revolution, a worn bearing as high-frequency whine/impulses,
  a blocked coil as a faster, louder fan.

So instead of a generic spectrum we compute a small set of features that each map to
one of those mechanisms. Few features means a per-unit healthy model can be learned
from minutes of data, and every alarm can be explained.

numpy only, so the same code runs on the UNO Q and on a laptop.
"""
import numpy as np

SR = 16000
# Physical bands: compressor/fan tones, airflow, structure-borne, bearing whine
BANDS_HZ = [(30, 100), (100, 200), (200, 400), (400, 800),
            (800, 1600), (1600, 3200), (3200, 6400)]
FEATURE_NAMES = (
    [f"band_{lo}_{hi}_db" for lo, hi in BANDS_HZ]
    + ["level_db", "comp_f0_hz", "comb_db", "inharm_db", "tone_prom_db", "tonality_db", "n_tones", "flatness",
       "centroid_hz", "mod_air", "mod_air_peak_db", "mod_high", "mod_high_peak_db",
       "kurt_high", "crest"]
)


def _psd(x, nfft=4096):
    """Welch power spectrum, Hann window, 50 % overlap (~3.9 Hz bins at 16 kHz)."""
    hop = nfft // 2
    w = np.hanning(nfft)
    frames = [x[i:i + nfft] * w for i in range(0, len(x) - nfft + 1, hop)] or [np.resize(x, nfft) * w]
    p = np.mean([np.abs(np.fft.rfft(fr)) ** 2 for fr in frames], axis=0) / (w ** 2).sum()
    return np.fft.rfftfreq(nfft, 1 / SR), p


def _bandpass(x, lo, hi):
    """Zero-phase FFT band-pass (fine for 1 s blocks)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def _envelope(x):
    """Analytic-signal magnitude (Hilbert transform via FFT)."""
    n = len(x)
    X = np.fft.fft(x)
    h = np.zeros(n)
    h[0] = 1
    h[1:(n + 1) // 2] = 2
    if n % 2 == 0:
        h[n // 2] = 1
    return np.abs(np.fft.ifft(X * h))


def _modulation(x, lo, hi):
    """How strongly a band is amplitude-modulated at 3-40 Hz (fan rotation rates).

    Returns (modulation index, modulation peakiness in dB). A rotating fault modulates
    at one steady rate, so it makes a narrow peak in the envelope spectrum; speech and
    traffic modulate the envelope too, but spread over many rates. Peakiness = the
    strongest envelope-spectrum line over the median of the 3-40 Hz range.
    """
    env = _envelope(_bandpass(x, lo, hi))
    mean = env.mean() + 1e-12
    w = np.hanning(len(env))
    E = np.abs(np.fft.rfft((env - mean) * w)) ** 2
    f = np.fft.rfftfreq(len(env), 1 / SR)
    m = (f >= 3) & (f <= 40)
    # RMS of the 3-40 Hz envelope fluctuation, relative to the mean envelope
    index = np.sqrt(2 * E[m].sum() / (w ** 2).sum() / len(env)) / mean
    peaky = 10 * np.log10(E[m].max() / (np.median(E[m]) + 1e-20) + 1e-12)
    return float(index), float(peaky)


def _comb_f0(x, lo=25.0, hi=120.0, n_harm=8):
    """Compressor speed from its harmonic series (a comb), not from one peak.

    An inverter compressor makes lines at f0, 2 f0, 3 f0, ... and which harmonic is
    loudest differs from unit to unit, so we score every candidate f0 by the summed
    prominence at its first harmonics. Uses a fine (~1 Hz) spectrum of the whole block.
    Returns (f0 in Hz, comb strength in dB per harmonic).
    """
    nfft = 1 << int(np.ceil(np.log2(len(x) * 2)))
    P = np.abs(np.fft.rfft(x * np.hanning(len(x)), nfft)) ** 2
    f = np.fft.rfftfreq(nfft, 1 / SR)
    keep = f <= hi * n_harm + 50
    f, db = f[keep], 10 * np.log10(P[keep] + 1e-14)
    df = f[1] - f[0]
    pos = np.maximum(db - _median_filter(db, int(40 / df) | 1), 0)
    best, best_s = lo, -1.0
    for f0 in np.arange(lo, hi, 0.25):
        idx = np.rint(f0 * np.arange(1, n_harm + 1) / df).astype(int)
        idx = idx[idx < len(f) - 1]
        s = np.maximum(np.maximum(pos[idx - 1], pos[idx]), pos[idx + 1]).sum()
        if s > best_s * 1.05:  # prefer the lower f0 on near-ties (avoids octave errors upward)
            best, best_s = f0, s
    return float(best), float(best_s / n_harm)


def _median_filter(v, k):
    vp = np.pad(v, k // 2, mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(vp, k), axis=1)


def features(x):
    """Feature vector (see FEATURE_NAMES) for one block of audio at 16 kHz (~1 s)."""
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    f, p = _psd(x)
    db = 10 * np.log10(p + 1e-14)

    bands = [10 * np.log10(p[(f >= lo) & (f < hi)].sum() + 1e-14) for lo, hi in BANDS_HZ]
    level = 10 * np.log10(p[f >= 30].sum() + 1e-14)

    # Tonal lines: peaks standing out from a ~100 Hz median floor
    floor = _median_filter(db, 25)
    prom = db - floor
    low = (f >= 40) & (f <= 600)  # compressor / blade-pass range
    i0 = np.flatnonzero(low)[np.argmax(prom[low])]
    tone_prom = float(prom[i0])
    comp_f0, comb = _comb_f0(x)
    mid = (f >= 40) & (f <= 2000)
    tonal = mid & (prom > 6)
    tonality = 10 * np.log10(p[tonal].sum() / (p[mid].sum() + 1e-14) + 1e-6)
    # Number of distinct tonal lines: a compressor defect adds new sub/inter-harmonics
    pk = mid[1:-1] & (prom[1:-1] > 10) & (db[1:-1] >= db[:-2]) & (db[1:-1] >= db[2:])
    n_tones = float(pk.sum())
    # Tonal energy that is NOT on the compressor comb: new lines from bearings,
    # rubbing or electrical faults. Measured in orders of comp_f0, so it does not
    # care which unit or which compressor speed we are at.
    order = f / comp_f0
    on_comb = np.abs(order - np.rint(order)) < 0.04
    off = tonal & ~on_comb
    inharm = 10 * np.log10(p[off].sum() / (p[mid].sum() + 1e-14) + 1e-6)

    sel = (f >= 100) & (f <= 4000)
    flatness = float(np.exp(np.mean(np.log(p[sel] + 1e-14))) / (np.mean(p[sel]) + 1e-14))
    centroid = float((f * p).sum() / (p.sum() + 1e-14))

    mod_air, mod_air_peak = _modulation(x, 200, 2000)     # fan airflow noise
    mod_high, mod_high_peak = _modulation(x, 2000, 6000)  # rattles, bearings

    hb = _bandpass(x, 2000, 6000)
    kurt = float(np.mean((hb - hb.mean()) ** 4) / (np.var(hb) ** 2 + 1e-14))
    crest = float(np.max(np.abs(x)) / (np.sqrt(np.mean(x ** 2)) + 1e-12))

    return np.array(bands + [level, comp_f0, comb, inharm, tone_prom, tonality, n_tones, flatness, centroid,
                             mod_air, mod_air_peak, mod_high, mod_high_peak, kurt, crest])


def windows(x, win=SR, hop=SR // 2):
    """Split a recording into 1 s blocks with 50 % overlap."""
    return [x[i:i + win] for i in range(0, len(x) - win + 1, hop)]
