"""The note tracker of tune_fp.c in Python, for test_tune_test.py: the same steps on the same input. Sums run in
double precision here and in float32 (some fused) there, so frequencies agree to float rounding, not bit for bit;
the notes, plucks and times agree.

Also the test signals: a plucked string as a sum of decaying harmonics with a noise burst at the attack, at an exact
frequency (unlike Karplus-Strong's integer delays), clean or overdriven; and a string through a magnetic pickup, rung
long and stopped by hand, as the hardware test plays it (tune-test1's pluck test took its ringing for new plucks)."""
import math

import numpy as np

FRAMES, RING, W6, T6MIN, T6MAX, W12 = 64, 512, 100, 4, 100, 200
SPAN = W12 + 2 * T6MAX + 4
SLICE, PEAKS = 25, 32
LEVEL_MIN = 0.0019952622
P_MIN, P_RATIO, P_FROM, P_TO = 0.0039810717, 2.0, 3, 18   # a pluck: -48 dBFS, twice the peaks 3..18 blocks back
THRESHOLD, APER_MAX = 0.2, 0.35
REFRACTORY, AGREE, RELEASE = 24, 2, 4
BQ = ((0.009165618568658829, 0.018331237137317657, 0.009165618568658829, -1.641069769859314, 0.6777322292327881),
      (0.010120933875441551, 0.020241867750883102, 0.010120933875441551, -1.8121154308319092, 0.8525991439819336))
NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
RESULT = ('note cents freq10 quality voiced first_ms lock_ms onsets locks lock_sum lock_min lock_max '
          'analyses').split()


def name(note):
    return f'{NAMES[note % 12]}{note // 12 - 1}' if note >= 0 else '--'


def ms(blocks):
    return (blocks * 4 + 1) // 3


def round_s(x):
    return int(x - 0.5) if x < 0 else int(x + 0.5)


class Tracker:
    def __init__(self):
        self.ring = np.zeros(RING)
        self.span = np.zeros(SPAN)
        self.d6 = np.zeros(T6MAX + 1)
        self.peaks = np.zeros(PEAKS)
        self.z = [[0.0, 0.0], [0.0, 0.0]]
        self.w = self.blk = 0
        self.last_onset, self.onset_blk, self.prev_note = -1000, 0, -1
        self.first_pending = self.lock_pending = False
        self.agree, self.unvoiced = 0, 99
        self.res = dict.fromkeys(RESULT, 0)
        self.res['note'] = -1
        self.analyses = []          # (block, voiced, freq, aperiodicity, nearest note)
        self.syn, self.syn_note, self.syn_sends = 0, -1, 0      # tt.syn: seq << 16 | (note + 1), 0 none

    def syn_send(self, note):
        seq = self.syn >> 16
        if note >= 0:
            seq = (seq + 1) & 0xFFFF
        self.syn = seq << 16 | (note + 1 if note >= 0 else 0)
        self.syn_note = note
        self.syn_sends += 1

    def step(self, block):
        """block: the 64 int16 values the integer side copies, (L + R) >> 1 of pair 0."""
        z = self.z
        pk = 0.0
        for f, s in enumerate(block):
            v = s / 32768.0
            for k in (0, 1):
                b0, b1, b2, a1, a2 = BQ[k]
                y = b0 * v + z[k][0]
                z[k][0] = b1 * v - a1 * y + z[k][1]
                z[k][1] = b2 * v - a2 * y
                v = y
            if f & 3 == 3:
                self.ring[self.w & (RING - 1)] = v
                self.w += 1
                pk = max(pk, abs(v))
        blk = self.blk
        self.peaks[blk & (PEAKS - 1)] = pk
        if blk >= P_TO:
            ref = max(self.peaks[(blk - k) & (PEAKS - 1)] for k in range(P_FROM, P_TO + 1))
            if pk >= P_MIN and pk >= P_RATIO * ref and blk - self.last_onset >= REFRACTORY:
                self.last_onset = self.onset_blk = blk
                self.first_pending = self.lock_pending = True
                self.agree = 0
                self.res['onsets'] += 1
        phase = blk & 3
        if phase == 0:
            idx = (self.w - 1 - np.arange(SPAN)) & (RING - 1)
            self.span = self.ring[idx].copy()
        lo = 1 + SLICE * phase
        x = self.span
        for k in range(lo, lo + SLICE):
            a = x[0:2 * W6:2] - x[2 * k:2 * k + 2 * W6:2]
            self.d6[k] = float(np.dot(a, a))
        if phase == 3:
            self.decide(blk)
        self.blk = blk + 1

    def decide(self, blk):
        x, d = self.span, self.d6
        dn = np.ones(T6MAX + 1)
        cum = 0.0
        for k in range(1, T6MAX + 1):
            cum += d[k]
            dn[k] = d[k] * k / cum if cum > 0 else 1.0
        tau = 0
        k = T6MIN
        while k <= T6MAX:
            if dn[k] < THRESHOLD:
                while k + 1 <= T6MAX and dn[k + 1] < dn[k]:
                    k += 1
                tau = k
                break
            k += 1
        if not tau:
            tau = T6MIN + int(np.argmin(dn[T6MIN:T6MAX + 1]))
        aper = float(dn[tau])
        power = float(np.dot(x[:W12], x[:W12])) / W12
        c = 2 * tau
        dd = []
        for i in range(7):
            a = x[:W12] - x[c - 3 + i:c - 3 + i + W12]
            dd.append(float(np.dot(a, a)))
        best = 1
        for i in range(2, 6):
            if dd[i] < dd[best]:
                best = i
        den = dd[best - 1] - 2 * dd[best] + dd[best + 1]
        off = 0.5 * (dd[best - 1] - dd[best + 1]) / den if den > 0 else 0.0
        kf = (c - 3 + best) + max(-1.0, min(1.0, off))
        if kf < 24.5:                                       # an octave up? half the lag at 12 kHz, 8..12
            h = int(kf * 0.5 + 0.5)
            dh = []
            for i in range(3):
                a = x[:W12] - x[h - 1 + i:h - 1 + i + W12]
                dh.append(float(np.dot(a, a)))
            hb = 1
            for i in (0, 2):
                if dh[i] < dh[hb]:
                    hb = i
            if dh[hb] <= 1.2 * dd[best]:
                o, dn2 = 0.0, dh[0] - 2 * dh[1] + dh[2]
                if hb == 1 and dn2 > 0:
                    o = max(-1.0, min(1.0, 0.5 * (dh[0] - dh[2]) / dn2))
                kf = (h - 1 + hb) + o
        freq = 12000.0 / kf
        voiced = power >= LEVEL_MIN * LEVEL_MIN and aper < APER_MAX
        midi = 69 + 12 * math.log2(freq / 440.0)
        note = round_s(midi)
        r = self.res
        r['analyses'] += 1
        r['voiced'] = int(voiced)
        r['freq10'] = int(freq * 10 + 0.5)
        r['cents'] = round_s((midi - note) * 100)
        r['quality'] = 0 if aper >= 1 else int((1 - aper) * 100 + 0.5)
        self.analyses.append((blk, voiced, freq, aper, note))
        if blk - self.onset_blk < 3:
            return
        if voiced:
            self.unvoiced = 0
            if self.first_pending:
                self.first_pending = False
                r['first_ms'] = ms(blk - self.onset_blk)
            self.agree = self.agree + 1 if self.agree and self.prev_note == note else 1
            self.prev_note = note
            if self.agree >= AGREE:
                r['note'] = note
                if self.lock_pending:
                    v = ms(blk - self.onset_blk)
                    self.lock_pending = False
                    r['lock_ms'] = v
                    r['lock_sum'] += v
                    if not r['locks'] or v < r['lock_min']:
                        r['lock_min'] = v
                    r['lock_max'] = max(r['lock_max'], v)
                    r['locks'] += 1
                    self.syn_send(note)                     # a pluck went steady: the synth plays it
                elif self.syn_note >= 0 and note != self.syn_note:
                    self.syn_send(note)                     # the pitch moved while it plays
        else:
            self.agree = 0
            self.prev_note = -1
            self.unvoiced += 1
            if self.unvoiced >= RELEASE:
                r['note'] = -1
                if self.syn_note >= 0:
                    self.syn_send(-1)                       # the string stopped: let go


def pluck(freq, secs, amp=0.4, seed=0, fs=48000, drive=0.0):
    """A plucked string: up to 12 harmonics below 8 kHz decaying faster the higher they are, a 1 ms attack ramp and a
    4 ms noise burst; drive > 0 overdrives it (tanh)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(secs * fs)) / fs
    x = np.zeros_like(t)
    for k in range(1, 13):
        if k * freq > 8000:
            break
        a = amp / k ** 1.1 * (1.0 if k == 1 else rng.uniform(0.4, 1.0))
        x += a * np.sin(2 * np.pi * k * freq * t + rng.uniform(0, 2 * np.pi)) * np.exp(-t * (1 + 0.35 * (k - 1)) / 1.2)
    burst = int(0.004 * fs)
    x[:burst] += rng.normal(0, amp * 0.3, burst) * np.linspace(1, 0, burst)
    ramp = int(0.001 * fs)
    x[:ramp] *= np.linspace(0, 1, ramp)
    if drive:
        x = np.tanh(drive * x) / math.tanh(drive) * amp
    return x


def phrase(notes, drive=0.0, seed=0, legato=False, fs=48000):
    """0.1 s of quiet, then the notes: one at a time (0.35 s, damped over the last 30 ms, 0.12 s apart), or legato
    (0.45 s each, the string before still ringing)."""
    parts = [np.zeros(fs // 10)]
    for k, n in enumerate(notes):
        x = pluck(440 * 2 ** ((n - 69) / 12), 0.45 if legato else 0.35, seed=seed + k, drive=drive)
        if not legato:
            d = int(0.03 * fs)
            x[-d:] *= np.linspace(1, 0, d)
            x = np.concatenate([x, np.zeros(int(0.12 * fs))])
        parts.append(x)
    return np.concatenate(parts)


def guitar(freq, secs, amp=0.45, p=0.2, q=0.1, B=1e-4, seed=0, fs=48000, drive=0.0, beat=0.1):
    """A string through a magnetic pickup: released from rest at p of its length, the pickup at q sensing its velocity
    (every harmonic in sine phase: the pulse-like wave of a real pickup, whose blocks swing far within a period),
    stiff-string inharmonicity B, higher harmonics dying faster, the pickup's resonance near 4 kHz, a slow beat of the
    two polarisations; peak `amp` in the first 50 ms; drive > 0 overdrives it (tanh)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(secs * fs)) / fs
    x = np.zeros_like(t)
    tau1 = 3.0 if freq < 150 else (2.0 if freq < 300 else 1.2)
    for n in range(1, 80):
        fn = n * freq * math.sqrt(1 + B * n * n)
        if fn > 7000:
            break
        r = fn / 4000.0
        a = math.sin(n * math.pi * p) * math.sin(n * math.pi * q) / n / math.sqrt((1 - r * r) ** 2 + (r / 1.5) ** 2)
        x += a * np.sin(2 * np.pi * fn * t) * np.exp(-t * (1 + fn / 400.0) / tau1)
    x *= 1 + beat * np.sin(2 * np.pi * rng.uniform(0.5, 2.0) * t + rng.uniform(0, 2 * np.pi))
    x *= amp / np.max(np.abs(x[:int(0.05 * fs)]))
    if drive:
        x = np.tanh(drive * x / amp) / math.tanh(drive) * amp
    return x


def open_strings(notes=(40, 45, 50, 55, 59, 64), ring=1.5, gap=0.4, drive=0.0, seed=0, p=0.2, q=0.1, fs=48000):
    """The hardware test's run: 0.2 s of quiet, then each string rung `ring` seconds and stopped by hand over 50 ms,
    `gap` seconds before the next; over hiss (-74 dBFS) and 60 Hz hum (-66 dBFS)."""
    rng = np.random.default_rng(seed)
    parts = [np.zeros(fs // 5)]
    for k, n in enumerate(notes):
        x = guitar(440 * 2 ** ((n - 69) / 12), ring + 0.05, p=p, q=q, B=1e-4 if n < 55 else 3e-5, seed=seed + k,
                   fs=fs, drive=drive)
        d = int(0.05 * fs)
        x[-d:] *= np.linspace(1, 0, d)
        parts += [x, np.zeros(int(gap * fs))]
    x = np.concatenate(parts)
    t = np.arange(len(x)) / fs
    return x + rng.normal(0, 2e-4, len(x)) + 5e-4 * np.sin(2 * np.pi * 60 * t + rng.uniform(0, 2 * np.pi))


def to_blocks(x, noise=0.0, seed=1):
    """A signal at full scale 1.0 as the integer side's 64-value blocks (int16, as (L + R) >> 1 of equal L and R)."""
    if noise:
        x = x + np.random.default_rng(seed).normal(0, noise, len(x))
    s = np.clip(np.round(x * 32767), -32768, 32767).astype(int)
    n = len(s) // FRAMES
    return [list(map(int, s[i * FRAMES:(i + 1) * FRAMES])) for i in range(n)]
