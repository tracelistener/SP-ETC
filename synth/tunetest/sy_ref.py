"""SY synth tests 1 and 2: the engine of sy_fp.c in Python, operation for operation in single precision (fmaf where
the C calls it, one rounding through double), and the tables the builder writes into sy_tables.h.

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
    it wakes; it smooths the beating of strings ringing together and follows a bend. Test 2: a band taking over its
    neighbour's partial takes its phases and its amplitude, so a bend hands the voice on without a gap or a new
    attack;
  - the bands' sum through a resonant state-variable filter whose cutoff follows the playing, a soft clip, to the
    DRY pair.

Test 2: 15 tones (TONES) and OFF, picked on the unit with VALUE held + pad 1-16. A tone sets each band's oscillators
(wave A: saw, pulse, triangle or sine; an optional wave B at a frequency ratio, added or phase-modulating A), the
bands' attack and release, the filter (low-, band- or high-pass, its cutoff range, resonance, a pick envelope), an
LFO (vibrato, tremolo, cutoff), breath noise, a 16-step gate at the SP's tempo, and an output gain. A new tone fades
the output out over 8 blocks, switches, and fades it in again.

Test 3: three knobs per tone, CTRL 1-3 turned with VALUE held: BRIGHT (the cutoff, -2..+2 octaves), one setting of
the tone's own (P2: resonance, pulse width, detune, attack, LFO speed, breath, FM depth, the pick envelope's depth, the
sub's level, the steps' rate) and LEVEL (the output, 0..2 x). Each tone keeps its own three (knob positions 0..127,
64 = the tone as designed); the unit keeps them, with the tone picked, in a file. knob_tone() applies them to a copy
of the tone each block; a setting at 64 leaves the tone's own value untouched.

Test 5: on the unit the tones "do not stand out much from guitar sound": every partial of a note had an oscillator of
its own, at the partial's own level, so the synth kept the guitar's spectrum and its decay. Three settings per tone:
  - FUND (designed per tone): a band whose pitch is a whole multiple, 2 to 8 within 3%, of a lower band's sounding in
    the same block stays silent, so a note sounds from its lowest band only and the tone's wave makes its whole
    spectrum (an octave or a twelfth played on its own string goes too);
  - SUSTAIN 0..100: while a band still sounds, a falling level is followed with a time constant of 40 ms x 2^(8 s/100)
    (s 100: 10 s) instead of the release's, so a note holds as a synth's does until the string has died away;
  - OCTAVE -2..+2: the oscillators' frequencies x 2^OCTAVE.
The output's ceiling goes up 3 dB (OUT_SCALE 23170, -3 dBFS at the clip) and the tones are re-levelled for it.
A band's first SKIP (4) periods after it wakes are counted, not tracked: they span the band-pass's start and read long
(-138, -51, -22, -12 cents on every string). With the overtones gone (FUND) the low E's start was heard 36 cents flat,
coming up over 100 ms; now every open string is within 5 cents from its first sounding block.

Test 6: single notes sounded rough on the unit (chords less so). A band's ownership flickers while a note starts (the
neighbour rule, a band-pass's settling: 1,460 on/off switches in the first 150 ms of seven single notes, and on the
low E and the B string all through the note), and since FUND a note hangs on one band: when that band drops for a
block the note drops, or its harmonics come back. Now:
  - the gate: a band more than 20 dB (GATE) under the loudest owned band does not sound (the pick's ring in empty
    bands, weak partials);
  - the hold: a band that stops owning sounds on for HOLD (4) blocks, 5.3 ms, while its energy keeps HOLD_E (0.8) of
    what it had when it last owned (a pick's ring and a stopped string fall away at once);
  - FUND only from a band at least FUND_REL (-20 dB) of the multiple's energy: a pick's ring an octave below a note
    muted the note (and with the next rule would have taken its level);
  - FUND to the 16th harmonic (the low E's 13th and 14th owned bands of their own);
  - a note's level is its loudest partial's (FUND's fundamental at the level of the strongest band it silenced: a
    pickup's fundamental can be under its harmonics, so the note sounded weaker than the guitar);
  - DYNAMICS 0..100 per tone: how far a note's level follows the band's (100, as designed, all the way; 0: every
    note at DYN_LEV), in dB: L x (L / DYN_LEV)^(d - 1).
"""
import math
from pathlib import Path

import numpy as np

FS, FS12, FRAMES, SUB, NB = 48000, 12000, 64, 16, 49
F32 = np.float32
F_E2 = 440.0 * 2 ** ((40 - 69) / 12)
BLOCK_S = FRAMES / FS

# The engine's constants (sy_tables.h has them as the C sees them).
Q_LO, Q_HI, Q_KNEE = 8.0, 16.0, 24       # band Q: 8 at E2, rising to 16 at E4 (band 24) and above
CASCADE = 0.6436                         # two stages at Q x this have one stage's -3 dB bandwidth (sqrt(sqrt 2 - 1))
LEV_PERIODS, LEV_MIN_S = 1.5, 0.002      # the energy follower: 1.5 periods of the band's centre, at least 2 ms
VALID_CENTS, OWN_CENTS = 300.0, 80.0     # a period counts within 300 cents of the centre; a band owns within 80
DEC_FC = 2000.0                          # the 4th-order Butterworth low-pass before 48 -> 12 kHz
ARM = 0.25                               # a crossing counts after the band went below -0.25 x its level
ALPHA, BETA = 0.2, 0.02                  # the period's alpha-beta tracker
SKIP = 4                                 # test 5: periods after a wake counted, not tracked (the band-pass's start)
FLOOR = 1e-3                             # a band below -60 dBFS is quiet (it measures again when it wakes)
GAIN = 1.2                               # a band's target amplitude: (level - FLOOR) x GAIN
DYN_REF = 0.25                           # the input level (peak follower) that opens the filter fully
ENV_TAU = 0.3                            # the peak follower's fall, as the tracker's
OUT_SCALE = 23170.0                      # test 5: the soft clip's 1.0 -> the DRY stem's 23170 (-3 dBFS; was 16384)
FADE_BLOCKS = 8                          # a stop or a new tone fades the output over this many blocks (10.7 ms)
TL_MIN = -4096.0                         # the last crossing is never kept further back than this (12 kHz samples)
AMP_EPS = 1e-3                           # a released band under this stops (-60 dB at the clip's level)
AGE_MIN = 24                             # a band that sounded fewer blocks than this (32 ms) stops at once
P_MIN, P_RATIO, P_FROM, P_TO, REFRACTORY = 0.0039810717, 2.0, 3, 18, 24   # a pick (as the tracker's test 2 rule)
GATE_K = 0.02                            # the step gate's smoothing per sample (about 1 ms)
FC_MAX = 12000.0                         # the output filter's highest cutoff
X_MIN = -4.0                             # its lowest: fc_lo / 16
EXP2_C = (0.6951786, 0.22657681, 0.07902149)   # 2^f ~ 1 + f (c1 + f (c2 + f c3)), f in [0, 1): error < 1e-4
HARM_MAX, HARM_TOL = 16, 0.03            # FUND: whole multiples 2..16 (test 5: 8) of a lower sounding band, within 3%
GATE = 0.1                               # test 6: a band under 0.1 x the loudest owned band's level (-20 dB) is silent
HOLD = 4                                 # test 6: blocks a band sounds on after it stops owning,
HOLD_E = 0.8                             #   while its energy keeps 0.8 x what it was when it last owned
FUND_REL = 0.01                          # test 6: a lower band mutes a multiple only at 0.01 x its energy (-20 dB) or more
FUND_RISE = 2.0                          # SY test 18: a band at 2 x its energy followed over about 32 blocks (ES_K)
ES_K = 0.03125                           #   is struck, for STRUCK blocks; a struck multiple of lower bands that only
STRUCK = 32                              #   ring is a string of its own (FUND spares it while it owns)
OLD = 32                                 #   a lower band only rings once it has owned 32 blocks (43 ms) or more
DYN_LEV = 0.1                            # test 6: DYNAMICS 0 puts every note at this band level
LOG2_C = (1.4191330077337858, -0.5760056527240476, 0.15687264499026177)   # log2(1 + f) ~ f (c1 + f (c2 + f c3))
SUS_MS0, SUS_STEP = 40.0, 0.08           # test 5, SUSTAIN s: a falling level's time constant 40 ms x 2^(0.08 s)
OCTAVES = (-2, -1, 0, 1, 2)              # test 5: OCTAVE's settings (knob zones)

SAW, PULSE, TRI, SINE = range(4)
LP, BP, HP = range(3)
P_Q, P_PW, P_DETUNE, P_ATT, P_LFO, P_NOISE, P_FM, P_FENV, P_LB, P_SEQ = range(10)   # test 3: what CTRL 2 sets
BLOCK_MS = BLOCK_S * 1000
LOG2E = 1.4426950408889634


def _tc(ms):
    """A one-pole step per block for a time constant in ms (0: at once)."""
    return 1.0 if ms <= 0 else 1 - math.exp(-BLOCK_S * 1000 / ms)


def _dec(ms):
    return 0.0 if ms <= 0 else math.exp(-BLOCK_S * 1000 / ms)


def _steps(bits):
    return sum(1 << i for i, b in enumerate(bits) if b)


# The tones, pads 1-15 (pad 16 is OFF). wa/wb: waves (wb None: none); rb: B's frequency ratio, lb: its level (FM:
# the index), fm_env: the index added at a pick; att/rel: the bands' attack and release (ms); fc_lo/fc_hi: the cutoff
# quiet .. at a hard pick, q, fmode; fenv: octaves a pick adds (decaying over fdec ms); lfo Hz, vib cents, trem 0..1,
# lfo_oct octaves of cutoff; noise: breath; seq: the 16 steps (1 = sound) at 1/16 of the SP's tempo; gain.
# Test 5: fund (1: only each note's lowest band sounds), sus (SUSTAIN 0..100), oct (OCTAVE -2..+2). Every tone but
# STRINGS and PAD plays its notes from their lowest band; the gains are levelled by level_tones() (strummed chord RMS;
# test 6: on single notes, E2, G3 and E4, to test 5's (sy6/level6.py): a note now sounds at its loudest partial's level,
# which lifts chords more (an octave string lifts the note under it): chords 0.7..3.1 dB over test 5, peaks <= 0.71).
TONES = [
    dict(name='SAW LEAD', wa=SAW, fund=1, sus=60, att=3, rel=150, fc_lo=350, fc_hi=4500, fenv=1.2, fdec=300, q=2.6,
         gain=1.276, p2=('RESO', P_Q, 0.0, 2.0)),
    dict(name='SQR LEAD', wa=PULSE, pw=0.0, fund=1, sus=60, att=3, rel=150, fc_lo=500, fc_hi=5000, q=1.6, lfo=5.5,
         vib=6, gain=0.744, p2=('WIDTH', P_PW, 0.0, 0.9)),
    dict(name='SYN BASS', wa=PULSE, pw=0.0, wb=SAW, rb=0.5, lb=0.7, fund=1, oct=-1, sus=40, rel=70, fc_lo=120,
         fc_hi=1400, fenv=2.2, fdec=180, q=3.2, gain=0.691, p2=('ENV', P_FENV, 0.0, 0.0)),
    dict(name='SUPERSAW', wa=SAW, wb=SAW, rb=2 ** (16 / 1200), lb=1.0, fund=1, sus=70, att=12, rel=300, fc_lo=500,
         fc_hi=7000, q=1.0, gain=0.879, p2=('DETUNE', P_DETUNE, 16.0, 2.0)),
    dict(name='PAD', wa=SAW, wb=SAW, rb=2 ** (-9 / 1200), lb=1.0, sus=100, att=400, rel=1500, fc_lo=250, fc_hi=2500,
         q=1.0, lfo=0.25, lfo_oct=0.6, gain=0.882, p2=('ATTACK', P_ATT, 400.0, 2.0)),
    dict(name='STRINGS', wa=SAW, sus=90, att=180, rel=600, fc_lo=500, fc_hi=4000, q=0.9, lfo=5.5, vib=7, gain=0.984,
         p2=('ATTACK', P_ATT, 180.0, 2.0)),
    dict(name='ORGAN', wa=SINE, wb=SINE, rb=2.0, lb=0.5, fund=1, sus=100, att=5, rel=60, fc_lo=3000, fc_hi=10000,
         q=0.7, lfo=6.5, vib=3, trem=0.2, gain=0.887, p2=('ROTARY', P_LFO, 0.0, 2.0)),
    dict(name='FLUTE', wa=SINE, noise=0.25, fund=1, sus=80, att=60, rel=160, fc_lo=900, fc_hi=5000, q=0.8, lfo=5.0,
         vib=7, gain=1.081, p2=('BREATH', P_NOISE, 0.0, 0.0)),
    dict(name='BELL', wa=SINE, wb=SINE, fm=1, rb=3.5, lb=0.15, fm_env=2.0, fdec=450, fund=1, oct=1, rel=1200,
         fc_lo=4000, fc_hi=12000, q=0.7, gain=1.033, p2=('METAL', P_FM, 0.0, 0.0)),
    dict(name='BRASS', wa=SAW, fund=1, sus=70, att=35, rel=150, fc_lo=250, fc_hi=2500, fenv=1.6, fdec=260, q=1.4,
         gain=1.304, p2=('OPEN', P_FENV, 0.0, 0.0)),
    dict(name='SUB BASS', wa=TRI, wb=SINE, rb=0.5, lb=0.8, fund=1, oct=-1, sus=60, rel=90, fc_lo=200, fc_hi=1200,
         q=0.8, gain=0.919, p2=('SUB', P_LB, 0.0, 0.0)),
    dict(name='SWEEP', wa=SAW, fund=1, sus=90, rel=300, fc_lo=200, fc_hi=1600, lfo=0.35, lfo_oct=1.6, q=5.0,
         gain=0.842, p2=('SPEED', P_LFO, 0.0, 3.0)),
    dict(name='WAH', wa=SAW, fmode=BP, fund=1, sus=50, fc_lo=300, fc_hi=3600, fenv=1.0, fdec=150, q=4.0, gain=15.654,
         p2=('RESO', P_Q, 0.0, 1.5)),
    dict(name='SEQ', wa=SAW, wb=TRI, rb=0.5, lb=0.7, fund=1, sus=100, rel=80, fc_lo=400, fc_hi=5000, q=2.5,
         seq=(1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0), gain=1.185, p2=('RATE', P_SEQ, 0.0, 0.0)),
    dict(name='OCT LEAD', wa=SAW, wb=PULSE, rb=1.0, lb=0.5, pw=0.0, fund=1, oct=1, sus=60, att=3, rel=150,
         fc_lo=600, fc_hi=7000, q=1.5, gain=2.519, p2=('RESO', P_Q, 0.0, 2.0)),
]
OFF_PAD = 15                             # pad 16: the synth off (test 5: CTRL 1's lowest zone)
TONE_FIELDS_U = ('wa', 'wb', 'fm', 'fmode', 'seq', 'p2kind', 'seqdiv', 'fund')
TONE_FIELDS_F = ('pw', 'rb', 'lb', 'fm_env', 'att', 'rel', 'fc_lo', 'oct', 'xmax', 'r2', 'fenv', 'fdec', 'lfo_inc',
                 'vib', 'trem', 'lfo_oct', 'noise', 'gain', 'p2base', 'p2span', 'bright', 'octm', 'roct', 'sus',
                 'dyn')


def sus_design(s):
    """Test 5: a tone's designed SUSTAIN (0..100) as its per-block coefficient: x - x^2 / 2 for x = one block over
    40 ms x 2^(0.08 s), as the knob's (knob_sus); 0 leaves a falling level to the release."""
    if s <= 0:
        return 0.0
    x = BLOCK_MS / (SUS_MS0 * 2 ** (SUS_STEP * s))
    return x - x * x / 2


def tone_params(t):
    """A tone as the C's sy_tone_t: integers, and single-precision values per block."""
    u = dict(wa=t['wa'], wb=0 if t.get('wb') is None else 1 + t['wb'], fm=t.get('fm', 0), fmode=t.get('fmode', LP),
             seq=_steps(t['seq']) if t.get('seq') else 0, p2kind=t['p2'][1], seqdiv=4, fund=t.get('fund', 0))
    o = t.get('oct', 0)
    f = dict(pw=t.get('pw', 0.0), rb=t.get('rb', 1.0), lb=t.get('lb', 0.0), fm_env=t.get('fm_env', 0.0),
             att=_tc(t.get('att', 0)), rel=_tc(t.get('rel', 0)), fc_lo=t['fc_lo'],
             oct=math.log2(t['fc_hi'] / t['fc_lo']), xmax=math.log2(FC_MAX / t['fc_lo']), r2=1 / t['q'],
             fenv=t.get('fenv', 0.0), fdec=_dec(t.get('fdec', 0)), lfo_inc=2 * t.get('lfo', 0.0) * BLOCK_S,
             vib=2 ** (t.get('vib', 0.0) / 1200) - 1, trem=t.get('trem', 0.0), lfo_oct=t.get('lfo_oct', 0.0),
             noise=t.get('noise', 0.0), gain=t['gain'], p2base=t['p2'][2], p2span=t['p2'][3], bright=0.0,
             octm=2.0 ** o, roct=2.0 ** -o, sus=sus_design(t.get('sus', 0)), dyn=t.get('dyn', 100) / 100)
    out = {k: int(v) for k, v in u.items()}
    out.update({k: F32(v) for k, v in f.items()})
    out['name'] = t['name']
    out['p2name'] = t['p2'][0]
    out['oct_design'] = o
    out['sus_design'] = t.get('sus', 0)
    out['dyn_design'] = t.get('dyn', 100)
    return out


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
    """Every constant the C reads, as single-precision values: per band, global, and the tones."""
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
             RDYN=1 / DYN_REF, PI_FS=math.pi / FS, ENV_K=math.exp(-FRAMES / FS / ENV_TAU), OUT_SCALE=OUT_SCALE,
             TL_MIN=TL_MIN, IN_SCALE=1 / 32768, C1=EXP2_C[0], C2=EXP2_C[1], C3=EXP2_C[2], T3=1 / 3, T5=2 / 15,
             FADE=1 / (FADE_BLOCKS * FRAMES), AMP_EPS=AMP_EPS, P_MIN=P_MIN, P_RATIO=P_RATIO, GATE_K=GATE_K,
             X_MIN=X_MIN, BEAT=BLOCK_S / 6000, BLOCK_MS=BLOCK_MS, INV1200=1 / 1200, HARM_TOL=HARM_TOL,
             SUS_MS0=SUS_MS0, SUS_STEP=SUS_STEP, GATE2=GATE * GATE, DYN_L2=math.log2(DYN_LEV), L1=LOG2_C[0],
             L2=LOG2_C[1], L3=LOG2_C[2], HOLD_E=HOLD_E, FUND_REL=FUND_REL, RISE=FUND_RISE, ES_K=ES_K)
    g = {n: F32(v) for n, v in g.items()}
    tones = [tone_params(t) for t in TONES]
    return band, dec, g, tones


BAND, DEC, G, TONE = tables()


def exp2(x):
    """2^x for x in (-32, 32): the cubic for the fraction, the power of two from the exponent bits."""
    i = int(F32(x + F32(32))) - 32
    fr = x - F32(i)
    p = fma_s(fr, fma_s(fr, fma_s(fr, G['C3'], G['C2']), G['C1']), F32(1))
    return p * F32(2.0 ** i)


OCT_MUL = [F32(2.0 ** o) for o in OCTAVES]    # test 5: OCTAVE's multipliers (SY_OCTM; 1 / one is the mirror one)


def log2(x):
    """Test 6: log2 of a positive normal x: the exponent bits, and a cubic for the mantissa's (error under 0.0013)."""
    u = int(np.asarray(x, F32).view(np.uint32))
    ex = (u >> 23) - 127
    m = np.asarray(np.uint32((u & 0x7FFFFF) | 0x3F800000)).view(F32)
    f = F32(m) - F32(1)
    return fma_s(f, fma_s(f, fma_s(f, G['L3'], G['L2']), G['L1']), F32(ex))


def dyn_level(lev, d):
    """Test 6: DYNAMICS d (0..1) on a band level: 2^(d (log2 lev - log2 DYN_LEV) + log2 DYN_LEV)."""
    return exp2(fma_s(d, log2(lev) - G['DYN_L2'], G['DYN_L2']))


def knob_sus(s):
    """Test 5: SUSTAIN s (0..100) from the knob as sy_fp.c's sy_sus: 0 none; else x - x^2 / 2, x = one block over
    40 ms x 2^(0.08 s) (the cubic exp2)."""
    if s == 0:
        return F32(0)
    tau = G['SUS_MS0'] * exp2(F32(s) * G['SUS_STEP'])
    x = G['BLOCK_MS'] / tau
    return fma_s(F32(-0.5) * x, x, x)


def knob_tone(T, kd, octave=0, sustain=0, dynamics=0):
    """Test 3: the tone with its three knobs (deltas from 64: kd) applied, as sy_fp.c's sy_knobs. Test 5: octave (0
    as designed, 1..5: OCTAVES[octave - 1]) and sustain (0 as designed, 1..101: 0..100). Test 6: dynamics (0 as
    designed, 1..101: 0..100)."""
    t = dict(T)
    if 1 <= dynamics <= 101:
        t['dyn'] = F32(dynamics - 1) * F32(0.01)
    if 1 <= octave <= len(OCTAVES):
        t['octm'] = OCT_MUL[octave - 1]
        t['roct'] = OCT_MUL[len(OCTAVES) - octave]
    if 1 <= sustain <= 101:
        t['sus'] = knob_sus(sustain - 1)
    c1 = F32(kd[0]) * F32(0.015625)
    t['bright'] = c1 * F32(2)
    t['gain'] = T['gain'] * (F32(64 + kd[2]) * F32(0.015625))
    if kd[1]:
        c2 = F32(kd[1]) * F32(0.015625)
        v2 = F32(64 + kd[1]) * F32(0.015625)
        k = T['p2kind']
        if k == P_Q:
            t['r2'] = T['r2'] * exp2(-c2 * T['p2span'])
        elif k == P_PW:
            t['pw'] = fma_s(c2, T['p2span'], T['pw'])
        elif k == P_DETUNE:
            cents = T['p2base'] * exp2(c2 * T['p2span'])
            t['rb'] = exp2(cents * G['INV1200'])
        elif k == P_ATT:
            tau = T['p2base'] * exp2(c2 * T['p2span'])
            x = G['BLOCK_MS'] / tau                         # 1 - e^-x as x - x^2 / 2 (x <= 0.04: within 0.1%)
            t['att'] = fma_s(F32(-0.5) * x, x, x)
        elif k == P_LFO:
            t['lfo_inc'] = T['lfo_inc'] * exp2(c2 * T['p2span'])
        elif k == P_NOISE:
            t['noise'] = T['noise'] * v2
        elif k == P_FM:
            t['fm_env'] = T['fm_env'] * v2
        elif k == P_FENV:
            t['fenv'] = T['fenv'] * v2
        elif k == P_LB:
            t['lb'] = T['lb'] * v2
        elif k == P_SEQ:
            t['seqdiv'] = 2 if kd[1] < -21 else (4 if kd[1] < 22 else 8)
    return t


def popup_name(pad):
    """The popup a pick shows: 'SY 4 SUPERSAW', 'SY OFF'."""
    return 'SY OFF' if pad == OFF_PAD else f'SY {pad + 1} {TONES[pad]["name"]}'


def c_header(tones=True):
    """sy_tables.h: the tables as C initialisers (every value as its exact single-precision hex float). SY test 11:
    tones=False leaves the tests 1-10 tones out (sy_voices.py's are the module's)."""
    def hx(v):
        return float(F32(v)).hex() + 'f'
    lines = ['/* SY synth tests 1 to 6: generated by the builder from tunetest/sy_ref.py (tables()); do not edit. */',
             '#ifndef SY_TABLES_H', '#define SY_TABLES_H', f'#define SY_NB {NB}', f'#define SY_TONES {len(TONE)}',
             f'#define SY_OFF_PAD {OFF_PAD}u', f'#define SY_P_FROM {P_FROM}u', f'#define SY_P_TO {P_TO}u',
             f'#define SY_REFRACTORY {REFRACTORY}u', f'#define SY_AGE_MIN {AGE_MIN}u',
             f'#define SY_HARM_MAX {HARM_MAX}', f'#define SY_OCTAVES {len(OCTAVES)}u', f'#define SY_SKIP {SKIP}u',
             f'#define SY_HOLD {HOLD}u', f'#define SY_OLD {OLD}u', f'#define SY_STRUCK {STRUCK}u']
    for n, v in G.items():
        lines.append(f'#define SY_{n} {hx(v)}')
    if tones:
        lines.append('static const float SY_OCTM[SY_OCTAVES] = {' + ', '.join(hx(v) for v in OCT_MUL) + '};')
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
    if tones:
        lines.append('/* the tones, pads 1-15: ' + ', '.join(t['name'] for t in TONE) + ' */')
        lines.append('static const sy_tone_t SY_TONE[SY_TONES] = {')
        for t in TONE:                                  # designated: the struct's own order does not matter
            lines.append('    {' + ', '.join(f'.{n} = {t[n]}u' for n in TONE_FIELDS_U) + ', ' +
                         ', '.join(f'.{n} = {hx(t[n])}' for n in TONE_FIELDS_F) + '},')
        lines.append('};')
    lines.append('#endif')
    return '\n'.join(lines) + '\n'


def c_names():
    """sy_names.h (the integer side's): what the guitar synth screen shows (test 5): each tone's name, its own
    setting's name (P2), its designed OCTAVE and SUSTAIN."""
    lines = ['/* SY synth tests 5 and 6: generated by the builder from tunetest/sy_ref.py (c_names); do not edit. */',
             '#ifndef SY_NAMES_H', '#define SY_NAMES_H', f'#define SY_OFF_PAD {OFF_PAD}u',
             f'#define SY_OCT_ZERO {OCTAVES.index(0) + 1}u', f'#define SY_OCTAVES {len(OCTAVES)}u',
             f'static const char *const SY_NAME[{len(TONE)}] = {{' + ', '.join(f'"{t["name"]}"' for t in TONE) + '};',
             f'static const char *const SY_P2_NAMES[{len(TONE)}] = {{' +
             ', '.join(f'"{t["p2name"]}"' for t in TONE) + '};',
             f'static const signed char SY_OCT_DESIGN[{len(TONE)}] = {{' +
             ', '.join(str(t['oct_design']) for t in TONE) + '};',
             f'static const unsigned char SY_SUS_DESIGN[{len(TONE)}] = {{' +
             ', '.join(str(t['sus_design']) for t in TONE) + '};',
             f'static const unsigned char SY_DYN_DESIGN[{len(TONE)}] = {{' +
             ', '.join(str(t['dyn_design']) for t in TONE) + '};', '#endif']
    return '\n'.join(lines) + '\n'


def sine(ph):
    """sin(pi ph) for ph in [-1, 1): a parabola, then one correction (error about 0.001)."""
    s = (ph * (F32(1) - abs(ph))) * F32(4)
    c = s * abs(s)
    return fma_s(F32(0.225), c - s, s)


def _after(x):
    return ((x + x) - x * x) - F32(1)


def _before(x):
    return (x * x + (x + x)) + F32(1)


def wave(kind, ph, pw, inc, rinc, hi):
    """One sample of a wave from its ramp ph (-1..1): the saw and the pulse with a polyBLEP at their jumps."""
    if kind == SAW:
        if abs(ph) > hi:
            return ph - (_after((ph + F32(1)) * rinc) if ph < 0 else _before((ph - F32(1)) * rinc))
        return ph
    if kind == PULSE:
        v = F32(1) if ph < pw else F32(-1)
        if abs(ph) > hi:
            v = v + (_after((ph + F32(1)) * rinc) if ph < 0 else _before((ph - F32(1)) * rinc))
        q = ph - pw
        if abs(q) < inc:
            v = v - (_after(q * rinc) if q >= 0 else _before(q * rinc))
        return v
    if kind == TRI:
        return fma_s(F32(-2), abs(ph), F32(1))
    return sine(ph)


class Engine:
    """sy_fp_step's state and its step, as the C has them (single precision, the same order of operations)."""
    def __init__(self, tone=0):
        z = lambda: np.zeros(NB, F32)  # noqa: E731
        self.dz = np.zeros((2, 2), F32)
        self.xh = np.zeros(2, F32)                      # the last two 12 kHz samples of the block before
        self.ua1, self.ua2, self.yb1, self.yb2, self.e = z(), z(), z(), z(), z()
        self.tl = np.full(NB, F32(TL_MIN), F32)
        self.per = BAND['pc'].copy()
        self.trend, self.ph, self.phb, self.amp = z(), z(), z(), z()
        self.armed = np.zeros(NB, bool)
        self.nper = np.zeros(NB, np.int64)
        self.owned = np.zeros(NB, bool)
        self.age = np.zeros(NB, np.int64)            # blocks a band has sounded (kept while it releases)
        self.env, self.s1, self.s2 = F32(0), F32(0), F32(0)
        self.mg = F32(1)                                # the fade (a stop, a new tone)
        self.peaks = np.zeros(32, F32)
        self.fe, self.lfo_ph, self.seq_ph, self.gate = F32(0), F32(0), F32(0), F32(1)
        self.last_pick = -1000
        self.ns = 0                                     # the noise's LCG
        self.tone = tone
        n = voices().NTONES
        self.knobs = np.zeros((n, 3), np.int64)          # test 3: each tone's knobs (TONE, P2, LEVEL), deltas from 64
        self.octs = np.zeros(n, np.int64)                # test 5: OCTAVE (0 as designed, 1..5)
        self.suss = np.zeros(n, np.int64)                # test 5: SUSTAIN (0 as designed, 1..101)
        self.dyns = np.zeros(n, np.int64)                # test 6: DYNAMICS (0 as designed, 1..101)
        self.trk = [0, 0, 0]                             # SY test 15: the TRACK page: WAIT, SENS, GUARD (every tone);
                                                         # test 18: LAW, SENS, GUARD
        self._host = None                                # SY test 11: the voices (sy_voices.Host)
        self.ykn = (0, 0, 255, 0, 0)                     # SY test 19: the SG tracker's word (ynote, yflag, ysince, ysyn;
                                                         # test 20: yseq, its note-ons' count)
        self.yin = None                                  # SY test 19: the tracker (tune_ref.Tracker) a mono tone's
        self.yan = 0                                     #   notes come from, while it runs (tune_ui); analyses seen
        self.hold = np.zeros(NB, np.int64)               # test 6: blocks a band sounds on after it stopped owning
        self.ehold = np.zeros(NB, F32)
        self.es = np.zeros(NB, F32)                      # SY test 18: each band's energy over about 32 blocks
        self.struck = np.zeros(NB, np.int64)             #   blocks left of a strike
        self.fresh = np.zeros(NB, bool)                  #   a string struck at a multiple of a ringing lower one
        self.oage = np.zeros(NB, np.int64)               #   blocks it has owned in a row (to 255)
        self.fund_cut = 0                                # test 5: band-blocks FUND silenced
        self.blocks = self.crossings = 0
        self.sounding = 0                               # bands sounding in the last block
        self.last = None                                # (own, target, frequency, cutoff) of the last block

    def host(self):
        if self._host is None:
            self._host = voices().Host(host_dll())
        return self._host

    def yin_word(self, ins16):
        """SY test 19: the SG tracker's step (while it runs: self.yin, a tune_ref.Tracker; tune_ui runs it for a mono
        tone) and its word for the voices, as sy_fp.c reads it: tt.res.analyses (a new one: fresh), tt_block's ycode,
        onset_blk and syn_note."""
        y = self.yin
        if y is not None:
            y.step(ins16)
        run = y is not None and bool(voices().VOICES[self.tone].get('mono'))
        an = y.res['analyses'] if y is not None else self.yan
        fresh = run and an != self.yan
        self.yan = an
        if not run:
            self.ykn = (0, 0, 255, 0, 0)
            return
        code = y.ycode
        ys = y.blk - 1 - y.onset_blk
        self.ykn = ((code & 0x7F) + 1 if fresh and (code & 0x100) else 0,
                    0x80 | (1 if fresh else 0) | (2 if fresh and (code & 0x200) else 0),
                    0 if ys < 0 else min(ys, 255),
                    y.syn_note + 1 if 0 <= y.syn_note <= 126 else 0,
                    (y.syn >> 16) & 0xFF)                # SY test 20: its note-ons (a re-pick's too)

    def step(self, ins16, stopping=False, tone_req=None, bpm100=12000):
        """One block: 64 int16 (pair 0, (L + R) >> 1) -> 64 values for the DRY pair (int, truncated), and whether
        the engine is still running (False once a stop has faded). SY test 11: the analysis here, the voices the host
        build of sy_voice.c (the module's C)."""
        if tone_req is None:
            tone_req = self.tone
        self.yin_word(ins16)                            # SY test 19: the tracker's step comes first (tune_rx)
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
        blk = self.blocks                               # SY test 16: a pick (test 10's rule), for GUARD's PICK
        self.peaks[blk & 31] = pk
        if blk >= P_TO:
            ref = F32(0)
            for kk in range(P_FROM, P_TO + 1):
                v = self.peaks[(blk - kk) & 31]
                ref = v if v > ref else ref
            if pk >= G['P_MIN'] and pk >= G['P_RATIO'] * ref and blk - self.last_pick >= REFRACTORY:
                self.last_pick = blk
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
                    # test 5: a band's first SKIP periods after it wakes span the band-pass's start and read long
                    # (-138, -51, -22, -12 cents on every string), so they are counted, not tracked: the tracker sits
                    # at the band's centre (set at the wake) and takes the fifth
                    pg = p[ok]
                    wake = nper[good] == 0
                    fresh = nper[good] < SKIP
                    base = per[good] + trend[good]
                    r = pg - base
                    per[good] = np.where(wake, B['pc'][good], np.where(fresh, per[good], fma(G['ALPHA'], r, base)))
                    trend[good] = np.where(fresh, F32(0), fma(G['BETA'], r, trend[good]))
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
        # test 6: the gate (under GATE x the loudest owned band's level: silent), then the hold (HOLD blocks more)
        emax = F32(0)
        for k in np.nonzero(own)[0]:
            if e[k] > emax:
                emax = e[k]
        gate = emax * G['GATE2']
        own = own & ~(e < gate)
        self.hold[own] = HOLD
        self.ehold[own] = e[own]
        held = ~own & (self.hold > 0)
        fall = held & (e < G['HOLD_E'] * self.ehold)   # falling away: no hold
        self.hold[fall] = 0
        held = held & ~fall
        self.hold[held] -= 1
        own = own | held
        hit = (e >= G['E_FLOOR']) & (e >= G['RISE'] * self.es)   # SY test 18: struck (awake, 2 x its energy over
                                                                  # about 32 blocks)
        self.struck = np.where(hit, STRUCK, np.maximum(self.struck - 1, 0))
        self.es = (self.es + (e - self.es) * G['ES_K']).astype(F32)
        self.fresh[~own] = False
        self.oage = np.where(own, np.minimum(self.oage + 1, 255), 0)
        lmax = np.zeros(NB, F32)                        # test 6: the loudest partial FUND silenced, per fundamental
        if True:                                        # test 5's FUND (SY test 11: always): a whole multiple of a lower sounding band is silent
            idx = np.nonzero(own)[0]
            keep = own.copy()
            for k in idx:
                cut, ringing = -1, True                 # the lowest band it is a multiple of; SY test 18: all of
                for j in idx:                           # those only ringing (owned OLD blocks, not struck, not spared)
                    if j >= k:
                        break
                    r = per[j] / per[k]
                    h = int(F32(r + F32(0.5)))
                    if 2 <= h <= HARM_MAX and abs(r - F32(h)) < G['HARM_TOL'] * F32(h) and \
                            not (e[j] < G['FUND_REL'] * e[k]):
                        if cut < 0:
                            cut = j
                        if self.struck[j] or self.fresh[j] or self.oage[j] < OLD:
                            ringing = False
                if cut < 0:
                    continue
                if ringing and (self.fresh[k] or self.struck[k]):   # SY test 18: struck while those only ring: a
                    self.fresh[k] = True                     # of its own, spared while it owns
                    continue
                keep[k] = False
                self.fresh[k] = False
                if e[k] > lmax[cut]:
                    lmax[cut] = e[k]
                self.fund_cut += 1
            own = keep
        en = np.where(lmax > e, lmax, e).astype(F32)   # test 6: a note at its loudest partial's level
        lev = np.sqrt(en + en).astype(F32)
        tg = np.where(own, (lev - G['FLOOR']) * G['GAIN'], F32(0)).astype(F32)
        tg = np.where(tg > 0, tg, F32(0)).astype(F32)
        self.owned = own
        self.sounding = int(np.count_nonzero(tg > 0))
        self.amp = tg.copy()
        fr = (F32(FS12) / per).astype(F32)
        t = self.tone
        h = self.host()
        law = int(self.trk[0]) if int(self.trk[0]) <= 2 else 0   # SY test 18: TRACK's first setting is LAW (WAIT 0)
        h.set_knobs(*[int(v) for v in self.knobs[t]], int(self.octs[t]), int(self.suss[t]), int(self.dyns[t]),
                    0, int(self.trk[1]), int(self.trk[2]), min(self.blocks - self.last_pick, 255), law, *self.ykn)
        mgt = F32(0) if stopping or tone_req != self.tone else F32(1)
        res, mg = h.block(t, tg, per, e, self.struck, mg=float(self.mg), mgt=float(mgt), fade=float(G['FADE']),
                          scale=float(G['OUT_SCALE']))   # SY test 18: the strikes (tests 12-17: nper, unused)
        self.mg = F32(mg)
        mg = self.mg
        if tone_req != self.tone and mg <= F32(0) and not stopping:   # faded out: the new tone, from rest
            self.tone = tone_req
            h.reset()
        self.blocks += 1
        self.last = (own.copy(), tg.copy(), fr, F32(0))
        return [int(v) for v in res], not (stopping and mg <= F32(0))


_DLL = None


def voices():
    import sy_voices
    return sy_voices


def host_dll():
    """SY test 11: the host build of sy_voice.c (built once, kept by its sources' hash, beside the workspace's out)."""
    global _DLL
    if _DLL is None:
        import hashlib
        import os
        v = voices()
        here = Path(__file__).resolve().parent
        srcs = [here / 'sy_voice.c', here / 'sy_voice.h', here / 'sy_voices.py',
                here.parent / 'ram' / 'waves_v8_ram' / 'waves.c']
        key = hashlib.sha256(b''.join(f.read_bytes() for f in srcs)).hexdigest()[:16]
        root = here.parents[3]
        out = root / 'out' / 'syv_host' / key
        dll = out / 'syv_host.dll'
        if not dll.exists():
            zig = os.environ.get('SYV_ZIG', str(root / '.wave_toolchain' / 'ziglang' / 'zig.exe'))
            v.build_host(out, zig)
        _DLL = dll
    return _DLL


def run(x, noise=0.0, seed=1, tone=0, bpm100=12000):
    """A signal (full scale 1.0) through the engine as the module gets it (int16 blocks): the DRY values, the log."""
    from tune_ref import to_blocks
    eng = Engine(tone)
    out, log = [], []
    for b in to_blocks(x, noise, seed):
        o, _ = eng.step(b, bpm100=bpm100)
        out += o
        log.append(eng.last)
    return np.array(out), log, eng
