"""SY synth test 1: the engine of sy_fp.c in Python, operation for operation in single precision (fmaf where the C
calls it, one rounding through double), and the tables the builder writes into sy_tables.h.

The method is the one Roland's patent US 9,542,923 describes for BOSS's SY pedals: no notes are found. The guitar
is split into 49 bands a semitone apart (E2..E6, 12 kHz); each band's pitch comes from its zero crossings and its
level from its energy, and drives an oscillator of its own. What this engine adds, from the model guitar
(sy_ref.py's checks, tune_ref.py's strings):
  - each band is two band-pass stages (a fourth-order band-pass): a chord's strings 3-5 semitones apart leak half as
    much into each other's bands as through one stage, so the pitches hold (with the rest as here, one stage: 96.2%
    of the sound on the chord's partials, 10 cents RMS off; two: 99.5%, 6 cents). One stage is faster: the low E
    at half its level 18 ms after the pick, against 30;
  - a band plays only when its level is the highest of its two neighbours' and its pitch within 80 cents of its
    centre: a partial then plays from one band (its neighbours read the same pitch weaker), and the bands between
    two partials, whose zero crossings follow neither, stay silent (without the rule: 84% on the partials, twice the
    bands sounding);
  - the pitch: an alpha-beta tracker on the zero-crossing periods (0.2, 0.02), starting from the band's centre when
    it wakes; it smooths the beating of strings ringing together and follows a bend (no gap as a bend hands its
    partial from band to band: the new band takes the old one's phase);
  - each oscillator is a saw (with a polyBLEP at its wrap), its level following the band's (above -60 dBFS);
  - the bands' sum through a resonant low-pass (a state-variable filter, Q 2) whose cutoff follows the playing
    (300 Hz quiet .. 5 kHz at a hard pick), a soft clip, to the DRY pair.
"""
import math

import numpy as np

FS, FS12, FRAMES, SUB, NB = 48000, 12000, 64, 16, 49
F32 = np.float32
F_E2 = 440.0 * 2 ** ((40 - 69) / 12)

# The patch and the engine's constants (sy_tables.h has them as the C sees them).
Q_LO, Q_HI, Q_KNEE = 8.0, 16.0, 24       # band Q: 8 at E2, rising to 16 at E4 (band 24) and above
CASCADE = 0.6436                         # two stages at Q x this have one stage's -3 dB bandwidth (sqrt(sqrt 2 - 1))
LEV_PERIODS, LEV_MIN_S = 1.5, 0.002      # the energy follower: 1.5 periods of the band's centre, at least 2 ms
VALID_CENTS, OWN_CENTS = 300.0, 80.0     # a period counts within 300 cents of the centre; a band owns within 80
DEC_FC = 2000.0                          # the 4th-order Butterworth low-pass before 48 -> 12 kHz
ARM = 0.25                               # a crossing counts after the band went below -0.25 x its level
ALPHA, BETA = 0.2, 0.02                  # the period's alpha-beta tracker
FLOOR = 1e-3                             # a band below -60 dBFS is quiet (it measures again when it wakes)
GAIN = 1.2                               # an oscillator's amplitude: (level - FLOOR) x GAIN
FC_LO, FC_HI = 300.0, 5000.0             # the output filter's cutoff: quiet .. a hard pick
DYN_REF = 0.25                           # the input level (peak follower) that opens it fully
RES_Q = 2.0
ENV_TAU = 0.3                            # the peak follower's fall, as the tracker's
OUT_SCALE = 16384.0                      # the soft clip's 1.0 -> the DRY stem's 16384 (-6 dBFS, as the cabinet)
FADE_BLOCKS = 8                          # a stop fades the output over this many blocks (10.7 ms)
TL_MIN = -4096.0                         # the last crossing is never kept further back than this (12 kHz samples)

EXP2_C = (0.6951786, 0.22657681, 0.07902149)   # 2^f ~ 1 + f (c1 + f (c2 + f c3)), f in [0, 1): error < 1e-4


def f32(x):
    return F32(x)


def fma(a, b, c):
    """fmaf: the product exact in double, the sum rounded to double then to single (a second rounding differs from
    one only when the double lands on a single-precision tie: about once in 2^29)."""
    return (np.asarray(a, np.float64) * np.asarray(b, np.float64) + np.asarray(c, np.float64)).astype(F32)


def fma_s(a, b, c):
    return F32(float(a) * float(b) + float(c))


def _lp_sections(fc, fs):
    """A 4th-order Butterworth low-pass as two biquads (the bilinear transform prewarped at fc): b0 b1 b2 a1 a2."""
    out = []
    for q in (1 / (2 * math.cos(math.pi / 8)), 1 / (2 * math.cos(3 * math.pi / 8))):
        w0 = 2 * math.pi * fc / fs
        al = math.sin(w0) / (2 * q)
        a0 = 1 + al
        c = math.cos(w0)
        out.append(((1 - c) / 2 / a0, (1 - c) / a0, (1 - c) / 2 / a0, -2 * c / a0, (1 - al) / a0))
    return out


def tables():
    """Every constant the C reads, as single-precision values: per band and global."""
    k = np.arange(NB)
    fc = F_E2 * 2.0 ** (k / 12.0)
    q = np.where(k < Q_KNEE, Q_LO + (Q_HI - Q_LO) * k / Q_KNEE, Q_HI)
    w0 = 2 * np.pi * fc / FS12
    al = np.sin(w0) / (2 * q * CASCADE)
    a0 = 1 + al
    tau = np.maximum(LEV_PERIODS / fc, LEV_MIN_S)
    pc = FS12 / fc
    band = dict(b0=al / a0, na1=2 * np.cos(w0) / a0, na2=-(1 - al) / a0, lc=1 - np.exp(-1 / (tau * FS12)), pc=pc,
                plo=pc * 2 ** (-VALID_CENTS / 1200), phi=pc * 2 ** (VALID_CENTS / 1200),
                olo=pc * 2 ** (-OWN_CENTS / 1200), ohi=pc * 2 ** (OWN_CENTS / 1200))
    band = {n: v.astype(F32) for n, v in band.items()}
    dec = [tuple(F32(v) for v in s) for s in _lp_sections(DEC_FC, FS)]
    g = dict(ARM2=2 * ARM * ARM, ALPHA=ALPHA, BETA=BETA, E_FLOOR=FLOOR * FLOOR / 2, FLOOR=FLOOR, GAIN=GAIN,
             FC_LO=FC_LO, OCT=math.log2(FC_HI / FC_LO), RDYN=1 / DYN_REF, PI_FS=math.pi / FS, R2=1 / RES_Q,
             ENV_K=math.exp(-FRAMES / FS / ENV_TAU), OUT_SCALE=OUT_SCALE, TL_MIN=TL_MIN, IN_SCALE=1 / 32768,
             C1=EXP2_C[0], C2=EXP2_C[1], C3=EXP2_C[2], T3=1 / 3, T5=2 / 15, FADE=1 / (FADE_BLOCKS * FRAMES))
    g = {n: F32(v) for n, v in g.items()}
    return band, dec, g


BAND, DEC, G = tables()


def c_header():
    """sy_tables.h: the tables as C initialisers (every value as its exact single-precision hex float)."""
    def hx(v):
        return float(F32(v)).hex() + 'f'
    lines = ['/* SY synth test 1: generated by the builder from tunetest/sy_ref.py (tables()); do not edit. */',
             '#ifndef SY_TABLES_H', '#define SY_TABLES_H', f'#define SY_NB {NB}']
    for n, v in G.items():
        lines.append(f'#define SY_{n} {hx(v)}')
    lines.append('static const float SY_DEC[2][5] = {')
    for s in DEC:
        lines.append('    {' + ', '.join(hx(v) for v in s) + '},')
    lines.append('};')
    lines.append('/* per band: b0, -a1, -a2 (both stages), the energy follower, the centre period and the valid and')
    lines.append(' * owned period ranges (12 kHz samples) */')
    lines.append('static const sy_band_t SY_BAND[SY_NB] = {')
    for k in range(NB):
        lines.append('    {' + ', '.join(hx(BAND[n][k]) for n in ('b0', 'na1', 'na2', 'lc', 'pc', 'plo', 'phi', 'olo',
                                                                     'ohi')) + '},')
    lines.append('};')
    lines.append('static const float SY_POW2[5] = {1.0f, 2.0f, 4.0f, 8.0f, 16.0f};')
    lines.append('#endif')
    return '\n'.join(lines) + '\n'


class Engine:
    """sy_fp_step's state and its step, as the C has them (single precision, the same order of operations)."""
    def __init__(self):
        z = lambda: np.zeros(NB, F32)  # noqa: E731
        self.dz = np.zeros((2, 2), F32)
        self.xh = np.zeros(2, F32)                      # the last two 12 kHz samples of the block before
        self.ua1, self.ua2, self.yb1, self.yb2, self.e = z(), z(), z(), z(), z()
        self.tl = np.full(NB, F32(TL_MIN), F32)
        self.per = BAND['pc'].copy()
        self.trend, self.ph, self.amp = z(), z(), z()
        self.armed = np.zeros(NB, bool)
        self.nper = np.zeros(NB, np.int64)
        self.owned = np.zeros(NB, bool)
        self.env, self.s1, self.s2 = F32(0), F32(0), F32(0)
        self.mg = F32(1)                                # the stop's fade
        self.blocks = self.crossings = 0
        self.sounding = 0                               # bands sounding in the last block
        self.last = None                                # (own, target, frequency) of the last block, for the tests

    def step(self, ins16, stopping=False):
        """One block: 64 int16 (pair 0, (L + R) >> 1) -> 64 values for the DRY pair (int, truncated), and whether
        the engine is still running (False once a stop has faded)."""
        x48 = np.asarray(ins16, np.int64).astype(F32) * G['IN_SCALE']
        z = self.dz
        x12 = np.zeros(SUB, F32)
        pk = F32(0)
        for f in range(FRAMES):
            v = x48[f]
            for s in range(2):
                b0, b1, b2, a1, a2 = DEC[s]
                y = fma_s(b0, v, z[s, 0])
                z[s, 0] = fma_s(b1, v, fma_s(-a1, y, z[s, 1]))
                z[s, 1] = fma_s(b2, v, F32(-a2) * y)
                v = y
            if (f & 3) == 3:
                x12[f >> 2] = v
                a = abs(v)
                pk = a if a > pk else pk
        ev = self.env * G['ENV_K']
        self.env = pk if pk > ev else ev
        dx = np.empty(SUB, F32)
        dx[0] = x12[0] - self.xh[0]
        dx[1] = x12[1] - self.xh[1]
        dx[2:] = x12[2:] - x12[:-2]
        self.xh[0], self.xh[1] = x12[SUB - 2], x12[SUB - 1]
        B = BAND
        ua1, ua2, yb1, yb2, e = self.ua1, self.ua2, self.yb1, self.yb2, self.e
        tl, per, trend, nper, armed = self.tl, self.per, self.trend, self.nper, self.armed
        for j in range(SUB):
            t = B['na2'] * ua2
            t = fma(B['na1'], ua1, t)
            u = fma(B['b0'], dx[j], t)
            du = u - ua2
            t = B['na2'] * yb2
            t = fma(B['na1'], yb1, t)
            y = fma(B['b0'], du, t)
            ua2, ua1 = ua1, u
            yprev = yb1
            yb2, yb1 = yb1, y
            yy = y * y
            t = yy - e
            e = fma(B['lc'], t, e)
            neg = y < 0
            armed = armed | (neg & (yy > G['ARM2'] * e))
            cross = armed & ~neg
            if cross.any():
                idx = np.nonzero(cross)[0]
                self.crossings += len(idx)
                d = yprev[idx] - y[idx]
                frac = yprev[idx] / d
                tc = F32(j - 1) + frac
                p = tc - tl[idx]
                tl[idx] = tc
                armed[idx] = False
                ok = (p > B['plo'][idx]) & (p < B['phi'][idx])
                good, bad = idx[ok], idx[~ok]
                nper[bad] = 0
                if len(good):
                    pg = p[ok]
                    fresh = nper[good] == 0
                    base = np.where(fresh, B['pc'][good], per[good] + trend[good])
                    tr = np.where(fresh, F32(0), trend[good])
                    r = pg - base
                    per[good] = fma(G['ALPHA'], r, base)
                    trend[good] = fma(G['BETA'], r, tr)
                    nper[good] = np.minimum(nper[good] + 1, 255)
        tl = tl - F32(SUB)
        tl = np.where(tl < G['TL_MIN'], G['TL_MIN'], tl)
        quiet = e < G['E_FLOOR']
        nper[quiet] = 0
        self.ua1, self.ua2, self.yb1, self.yb2, self.e = ua1, ua2, yb1, yb2, e
        self.tl, self.armed = tl, armed
        # a band plays when its level tops both neighbours' and its pitch is within 80 cents of its centre
        el = np.concatenate([[F32(0)], e[:-1]]).astype(F32)
        er = np.concatenate([e[1:], [F32(0)]]).astype(F32)
        own = ~quiet & (nper >= 2) & (e >= el) & (e >= er) & (per > B['olo']) & (per < B['ohi'])
        for k in np.nonzero(own & ~self.owned)[0]:        # a partial moving on: the new band takes its phase
            for nb in (k - 1, k + 1):
                if 0 <= nb < NB and self.owned[nb] and abs(per[nb] - per[k]) < F32(0.01) * per[k]:
                    self.ph[k] = self.ph[nb]
                    break
        lev = np.sqrt(e + e)
        tg = np.where(own, (lev - G['FLOOR']) * G['GAIN'], F32(0)).astype(F32)
        tg = np.where(tg > 0, tg, F32(0)).astype(F32)
        out = np.zeros(FRAMES, F32)
        n_on = 0
        for k in range(NB):
            if not (tg[k] > 0 or self.amp[k] > 0):
                continue
            n_on += tg[k] > 0
            inc = F32(0.5) / per[k]
            rinc = per[k] + per[k]
            lo_e, hi_e = inc - F32(1), F32(1) - inc
            da = (tg[k] - self.amp[k]) * F32(1 / 64)
            a, ph = self.amp[k], self.ph[k]
            w = np.empty(FRAMES, F32)
            av = np.empty(FRAMES, F32)
            for n in range(FRAMES):
                ph = ph + inc
                if ph >= F32(1):
                    ph = ph - F32(2)
                a = a + da
                if ph < lo_e:
                    x = (ph + F32(1)) * rinc
                    b = (x + x) - x * x
                    wv = ph - (b - F32(1))
                elif ph > hi_e:
                    x = (ph - F32(1)) * rinc
                    b = x * x + (x + x)
                    wv = ph - (b + F32(1))
                else:
                    wv = ph
                w[n] = wv
                av[n] = a
            out = fma(av, w, out)
            self.amp[k] = tg[k]
            self.ph[k] = ph
        self.owned = own
        self.sounding = int(n_on)
        # the output filter: a TPT state-variable low-pass, its cutoff by the input's level
        d = self.env * G['RDYN']
        if d > F32(1):
            d = F32(1)
        s = np.sqrt(d)
        xo = s * G['OCT']
        i = int(xo)
        fr = xo - F32(i)
        p2 = fma_s(fr, fma_s(fr, fma_s(fr, G['C3'], G['C2']), G['C1']), F32(1))
        fc = G['FC_LO'] * p2 * F32(2 ** i)
        wv = fc * G['PI_FS']
        w2 = wv * wv
        g = wv * fma_s(w2, fma_s(w2, G['T5'], G['T3']), F32(1))
        nk1 = -(G['R2'] + g)
        hh = F32(1) / fma_s(g, G['R2'] + g, F32(1))
        s1, s2, mg = self.s1, self.s2, self.mg
        res = np.empty(FRAMES, np.int64)
        for n in range(FRAMES):
            v = fma_s(nk1, s1, out[n])
            v = v - s2
            hp = v * hh
            bp = fma_s(g, hp, s1)
            s1 = fma_s(g, hp, bp)
            lp = fma_s(g, bp, s2)
            s2 = fma_s(g, bp, lp)
            yv = lp
            if yv > F32(1):
                yv = F32(1)
            elif yv < F32(-1):
                yv = F32(-1)
            else:
                yv = yv * fma_s(F32(-0.5), yv * yv, F32(1.5))
            if stopping:
                mg = mg - G['FADE']
                if mg < F32(0):
                    mg = F32(0)
            yv = yv * mg
            res[n] = int(np.trunc(np.float64(yv * G['OUT_SCALE'])))
        self.s1, self.s2, self.mg = s1, s2, mg
        self.blocks += 1
        self.last = (own.copy(), tg.copy(), (F32(FS12) / per).astype(F32), fc)
        return [int(v) for v in res], not (stopping and mg <= F32(0))


def run(x, noise=0.0, seed=1):
    """A signal (full scale 1.0) through the engine as the module gets it (int16 blocks): the DRY values, the log."""
    from tune_ref import to_blocks
    eng = Engine()
    out, log = [], []
    for b in to_blocks(x, noise, seed):
        o, _ = eng.step(b)
        out += o
        log.append(eng.last)
    return np.array(out), log, eng
