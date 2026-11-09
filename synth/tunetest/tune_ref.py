"""The note tracker of tune_fp.c in Python, for test_tune_test.py: the same steps on the same input. Sums run in
double precision here and in float32 (some fused) there, so frequencies agree to float rounding, not bit for bit;
the notes, plucks and times agree.

Also the test signals: a plucked string as a sum of decaying harmonics with a noise burst at the attack, at an exact
frequency (unlike Karplus-Strong's integer delays), clean or overdriven; a string through a magnetic pickup, rung
long and stopped by hand, as the hardware test plays it (tune-test1's pluck test took its ringing for new plucks);
test 6's: a fretted note let go right after the pick (the open string or a touch harmonic rings briefly), and a chord
held while its strings are picked one by one."""
import math

import numpy as np

FRAMES, RING, W6, T6MIN, T6MAX, W12 = 64, 512, 100, 4, 100, 200
SPAN = W12 + 2 * T6MAX + 4
PEAKS = 32
EVERY = 2                                          # SY test 24: an analysis every 2 blocks, on the newest samples
LEVEL_MIN = 0.0019952622
P_MIN, P_RATIO, P_FROM, P_TO = 0.0039810717, 2.0, 3, 18   # a pluck: -48 dBFS, twice the peaks 3..18 blocks back
THRESHOLD, APER_MAX = 0.2, 0.35
REFRACTORY, AGREE, RELEASE = 24, 3, 7             # SY test 24: 2n - 1 analyses for test 23's n (2, 4)
REPICK, MOVE_AGREE, MOVE_CENTS = 1.2, 5, 30       # the synth: a pluck on its own note; a move without a pluck
CLEAN_APER = 0.15                                 # test 4: only readings this clean count (strings ringing together
                                                  # read murkier); a murky one counts as nothing heard
CLICK_KEEP = 0.5                                  # a pluck going steady on the note playing: the level it keeps
                                                  # when the pick clicked (else it must rise REPICK)
LOCK_SAME = 7                                     # SY test 24: a pick's lock on the note sounding waits this many
                                                  # blocks after the pluck (test 23's earliest lock; tune_fp.c)
SYN_DROP, SYN_RELEASE_LONG = 0.3, 23              # the synth lets go: quieter than the last voiced level, or late
HARMONIC_JUMPS = (12, 19, 24, 28, 31)
VEL_FLOOR, VEL_FULL, LEVEL_BLOCKS = 50, 0.4, 13   # test 4: velocity 50..127 by sqrt(peak / VEL_FULL); level window
HF_FC, HF_RATIO, HF_MIN, HF_FROM, HF_TO = 2000.0, 2.0, 1e-4, 2, 16   # the click: energy over 2 kHz in a block,
                                                  # HF_RATIO x the most of blocks HF_FROM..HF_TO back, over HF_MIN
# SY test 25, a soft click (the user: test 24 "misses some quiet notes"; on the user's take 29 of its 61 missed picks
# came while a note sounded, as loud as it, the 2 kHz click +0.9 dB over its reference): while the synth plays a note,
# the energy over 6 kHz of the newest 2 blocks at HF6_RATIO (4.5 dB) x the mean of blocks HF6_FROM..HF6_TO back (a
# block's gap), the newest 2 blocks' peak over P_MIN, is a pluck too (a click's: CLICK_KEEP on its own note). On the
# take, SYNC LEAD: picks played 257 -> 269 of 318, the first note right 243 -> 248, 29 more attacks on softer onsets
# (semitone steps, soft repeats) and 2 on none; in held notes about one false click a minute.
HF6_FC, HF6_RATIO, HF6_FROM, HF6_TO = 6000.0, 2.8183829, 3, 18
# SY test 27 (the user on test 26's lead: those glides were picked notes): a move whose readings left the note
# sounding (its last reading within MOVE_STEADY cents of it) at most MOVE_QUICK blocks before is a fret change (picked
# or hammered: YIN's window makes the jump 14-24 blocks; on the user's take the moves near picks 15-34, median 20),
# not a bend or a slide (a semitone bent in 60 ms 28 blocks, a tone in 170 ms 38, in 300 ms 62): move_quick, for the
# SY voices (a retriggering tone attacks it)
MOVE_STEADY, MOVE_QUICK = 15, 24
SOFT_LEVEL, SOFT_HOLD = 0.7, 0.7                 # the 2 blocks' peak at least SOFT_LEVEL x the pluck reference (no
                                                  # click while a pick's attack falls away: an overdriven low E 140 ms
                                                  # after its pick, 0.51); a soft-only pluck plays only with the level
                                                  # now at SOFT_HOLD x its reference (a let-go's falls: nothing)
# SY test 30 (the user on tests 27-29: lead tones "either missing notes or extra notes sometimes"):
# - a quick move counts only when the level held over it: the level now at least QUICK_HOLD x the highest peak
#   QUICK_BACK..QUICK_BACK + QUICK_WIN - 1 blocks back (32-43 ms). On the user's take (every note let go before the
#   next pick, the fretting finger sliding on as it lets go) test 27's quick moves were mostly that slide, the level
#   falling 1.3-8.8 dB: 17 extra short notes; a picked fret change brings a pick's energy;
# - a pick from quiet, softer than the note before, is heard: the jump test wanted JUMP_ENV x the envelope, which the
#   note before leaves high for half a second (every other note of the take played 12 dB softer: 44 of 120 lost, 8 dB
#   softer 12, no click to save them on the neck pickup). It is waived when the 21 ms before the block were at most
#   QUIET_REF x the envelope (the note before has stopped) and the block is QUIET_RATIO x them and QUIET_ENV x the
#   envelope (44 -> 9, 12 -> 4), and the envelope restarts from the pick (its moves and let-go by its own level).
# The soft click stays: on a version of the take picked note to note at even strength (each pick over the note before,
# its fret first) it hears most of the picks the jump and click tests miss (101 of 233 attacked; 59 without it).
QUICK_HOLD, QUICK_BACK, QUICK_WIN = 1.0, 24, 8
QUIET_REF, QUIET_RATIO, QUIET_ENV = 0.35, 3.0, 0.2
# Test 6. The level: a peak follower falling with a 0.3 s time constant (env). Letting a fretted note go (synth
# test 5 on the unit: "a second note on release") leaves the open string or a touch harmonic far quieter than the
# note: a move needs the level now (a period's peak) at MOVE_HOLD x env, a pluck's lock PLUCK_HOLD x the level
# before it (else it was a stop: let go), and the note is let go once the newest 13 blocks' peak falls under
# DROP x env. A jump is a pluck only over JUMP_ENV x env (strings ringing together beat; a fading chord's peaks can
# double). Strings ringing together (test 5: "hold a chord and play the notes, they sometimes don't sound"): after
# a pluck heard while the strings rang (its reference at least RING_MIN x its peak), the difference function of the
# analysis before the pluck is taken off (what the pick added: a new string, a re-picked one); it counts if what is
# left is at least SUB_MIN of the whole, never under -SUB_NEG x its mean, read only at lags the analysis has had
# since the pluck, its first dip under THR_SUB, refined at 12 kHz on the newest samples less the ones before the
# pluck. It is used when the plain reading is murky, or clean on a common period (2..6 times its own: strings a
# fifth apart read an octave below the lower). A note found so is held through murky readings while there is
# signal, and does not move.
ENV_TAU = 0.3
ENV_K = float(np.float32(math.exp(-FRAMES / 48000.0 / ENV_TAU)))
JUMP_ENV, MOVE_HOLD, PLUCK_HOLD, DROP = 1.3, 0.4, 0.25, 0.2
RING_MIN, SUB_MIN, SUB_NEG, THR_SUB, COMMON_TOL = 0.08, 0.2, 0.5, 0.3, 0.03
BASE = W12 + 2 * T6MAX + 8                         # the samples before a pluck kept for the refinement


def _hp2(fc, fs=48000):
    """A 2nd-order Butterworth high-pass (bilinear): b0, b1, b2, a1, a2, rounded to float32 as tune_fp.c has them."""
    k = math.tan(math.pi * fc / fs)
    n = 1 / (1 + k * math.sqrt(2) + k * k)
    return tuple(float(np.float32(c)) for c in (n, -2 * n, n, 2 * (k * k - 1) * n, (1 - k * math.sqrt(2) + k * k) * n))


HP = _hp2(HF_FC)
HP6 = _hp2(HF6_FC)                                 # SY test 25
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


def vel_f(peak):
    """A pick's peak as a velocity, VEL_FLOOR..127, not rounded (test 4: a gentle curve, soft picks stay audible)."""
    return min(127.0, VEL_FLOOR + (127 - VEL_FLOOR) * math.sqrt(peak / VEL_FULL))


def velocity(peak):
    return round_s(vel_f(peak))


def period_blocks(freq):
    """Blocks a period at freq spans, plus one, at least 4 (the level 'now' over a period: a low string's peaks
    ripple within one)."""
    q = 750.0 / max(freq, 30.0)
    c = int(q)
    if c < q:
        c += 1
    return max(4, c + 1)


class Tracker:
    def __init__(self, drum=False, click=True, hf_ratio=HF_RATIO, hf_min=HF_MIN, repick=REPICK, test6=True):
        self.drum = drum            # tt.drum: the kits' drum mode, only plucks play notes
        self.click, self.hf_ratio, self.hf_min, self.repick = click, hf_ratio, hf_min, repick
        self.test6 = test6          # False: test 5's rules (for the checks' before/after)
        self.ring = np.zeros(RING)
        self.span = np.zeros(SPAN)
        self.d6 = np.zeros(T6MAX + 1)
        self.peaks = np.zeros(PEAKS)
        self.hfe = np.zeros(PEAKS)
        self.z = [[0.0, 0.0], [0.0, 0.0]]
        self.zh = [0.0, 0.0]
        self.zh6 = [0.0, 0.0]                                   # SY test 25: the soft click's 6 kHz high-pass
        self.hf6 = np.zeros(PEAKS)
        self.softs = 0                                          # plucks only the soft click heard
        self.quiets = 0                                         # SY test 30: plucks the jump test heard from quiet
        self.w = self.blk = 0
        self.last_onset, self.onset_blk, self.prev_note = -1000, 0, -1
        self.first_pending = self.lock_pending = False
        self.agree, self.unvoiced = 0, 99
        self.res = dict.fromkeys(RESULT, 0)
        self.res['note'] = -1
        self.analyses = []          # (block, voiced, freq, aperiodicity, nearest note, clean, from the subtraction)
        self.syn, self.syn_note, self.syn_sends = 0, -1, 0      # tt.syn: seq << 16 | vel << 8 | (note + 1), 0 none
        self.ycode = 0                                          # SY test 19: the newest analysis, for the SY engine
        self.pluck_ref, self.syn_strays = 0.0, 0
        self.voiced_level, self.syn_holds = 0.0, 0
        self.pick_peak, self.clicks = 0.0, 0                    # clicks: plucks only the click test heard
        self.pluck_click = False                                # the last pluck clicked (a pick, not a thump)
        self.murky = 0
        # test 6
        self.env = 0.0
        self.d_last = np.zeros(T6MAX + 1)                       # the last analysis' difference function
        self.d_base = np.zeros(T6MAX + 1)                       # the last one before the pending pluck
        self.base_x = np.zeros(BASE)                            # the samples before the pluck, newest first
        self.sub_lock = False                                   # the synth's note came from the subtraction
        self.stops = self.drops = self.sub_locks = self.blocked = 0
        self.old_at = -1000                                     # SY test 27: the synth's note last read steady
        self.move_quick = 0                                     # the last note-on a quick move (a fret change)

    def recent_peak(self, blk):
        return max(self.peaks[(blk - k) & (PEAKS - 1)] for k in range(4))

    def level(self, blk):
        return max(self.peaks[(blk - k) & (PEAKS - 1)] for k in range(LEVEL_BLOCKS))

    def win_peak(self, blk, n, since=None):
        """The highest peak of the newest n blocks, not before block `since`."""
        lo = blk - n + 1
        if since is not None and lo < since:
            lo = since
        return max((self.peaks[k & (PEAKS - 1)] for k in range(lo, blk + 1)), default=0.0)

    def after_peak(self, blk):
        """The highest peak since 4 blocks after the last pluck (past a thump's own blocks; a low string's period
        fits in it by the time a note on it goes steady), at most the newest PEAKS - 4 blocks."""
        n = min(blk - (self.onset_blk + 4) + 1, PEAKS - 4)
        return max((self.peaks[(blk - k) & (PEAKS - 1)] for k in range(n)), default=0.0)

    def syn_send(self, note, vel=0):
        seq = self.syn >> 16
        if note >= 0:
            seq = (seq + 1) & 0xFFFF
        self.syn = seq << 16 | (vel << 8 | (note + 1) if note >= 0 else 0)
        self.syn_note = note
        self.syn_sends += 1
        self.move_quick = 0                                     # SY test 27 (the move sets it after)

    def step(self, block):
        """block: the 64 int16 values the integer side copies, (L + R) >> 1 of pair 0."""
        z, zh, zh6 = self.z, self.zh, self.zh6
        h0, h1, h2, g1, g2 = HP
        k0, k1, k2, q1, q2 = HP6
        pk = e = e6 = 0.0
        for f, s in enumerate(block):
            v = s / 32768.0
            y = h0 * v + zh[0]                              # the click's high-pass, on the input itself
            zh[0] = h1 * v - g1 * y + zh[1]
            zh[1] = h2 * v - g2 * y
            e += y * y
            y = k0 * v + zh6[0]                             # SY test 25: the soft click's, at 6 kHz
            zh6[0] = k1 * v - q1 * y + zh6[1]
            zh6[1] = k2 * v - q2 * y
            e6 += y * y
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
        self.hfe[blk & (PEAKS - 1)] = e
        self.hf6[blk & (PEAKS - 1)] = e6
        env_prev = self.env
        self.env = max(pk, self.env * ENV_K)
        if blk >= P_TO:
            ref = max(self.peaks[(blk - k) & (PEAKS - 1)] for k in range(P_FROM, P_TO + 1))
            href = max(self.hfe[(blk - k) & (PEAKS - 1)] for k in range(HF_FROM, HF_TO + 1))
            loud = pk >= JUMP_ENV * env_prev or not self.test6
            quiet = (not loud and ref <= QUIET_REF * env_prev and pk >= QUIET_RATIO * ref and
                     pk >= QUIET_ENV * env_prev)            # SY test 30: a pick from quiet, softer than the note before
            jump = pk >= P_MIN and pk >= P_RATIO * ref and (loud or quiet)
            click = self.click and e >= self.hf_min and e >= self.hf_ratio * href and pk >= P_MIN
            soft = False
            if self.click and self.syn_note >= 0:           # SY test 25: the soft click, while a note plays
                m6 = sum(self.hf6[(blk - k) & (PEAKS - 1)] for k in range(HF6_FROM, HF6_TO + 1))
                pk2 = max(pk, self.peaks[(blk - 1) & (PEAKS - 1)])
                soft = ((e6 + self.hf6[(blk - 1) & (PEAKS - 1)]) * 0.5 >= HF6_RATIO * m6 * (1 / 16) and
                        pk2 >= P_MIN and pk2 >= SOFT_LEVEL * ref)
            if (jump or click or soft) and blk - self.last_onset >= REFRACTORY:
                self.clicks += not jump
                self.softs += not (jump or click)
                self.pluck_click = 2 if not (jump or click) else int(click)   # SY test 25: 2, the soft click only
                self.pluck_ref = ref
                self.pick_peak = pk
                if jump and quiet:
                    self.quiets += 1
                    self.env = pk                           # SY test 30: the level starts again from this pick
                self.last_onset = self.onset_blk = blk
                self.first_pending = self.lock_pending = True
                self.agree = 0
                self.res['onsets'] += 1
                self.d_base = self.d_last.copy()            # test 6: what rang before it
                idx = (self.w - FRAMES // 4 - 1 - np.arange(BASE)) & (RING - 1)
                self.base_x = self.ring[idx].copy()
            elif self.lock_pending and pk > self.pick_peak:
                self.pick_peak = pk                         # the pick's peak, up to its steady note
        if blk % EVERY == EVERY - 1:                        # SY test 24: every 2 blocks, on the newest samples
            idx = (self.w - 1 - np.arange(SPAN)) & (RING - 1)
            self.span = self.ring[idx].copy()
            x = self.span
            for k in range(1, T6MAX + 1):
                a = x[0:2 * W6:2] - x[2 * k:2 * k + 2 * W6:2]
                self.d6[k] = float(np.dot(a, a))
            self.decide(blk)
        self.blk = blk + 1

    def yin(self, d, x, base=None, tmax=T6MAX, thr=THRESHOLD):
        """YIN on the difference function d (6 kHz, lags 1..tmax), refined at 12 kHz on x (less the same on base):
        (aperiodicity, clean, frequency)."""
        dn = np.ones(T6MAX + 1)
        cum = 0.0
        for k in range(1, tmax + 1):
            cum += d[k]
            dn[k] = d[k] * k / cum if cum > 0 else 1.0
        tau = 0
        k = T6MIN
        while k <= tmax:
            if dn[k] < thr:
                while k + 1 <= tmax and dn[k + 1] < dn[k]:
                    k += 1
                tau = k
                break
            k += 1
        if not tau:
            tau = T6MIN + int(np.argmin(dn[T6MIN:tmax + 1]))
        aper = float(dn[tau])
        # test 4: the dip's own bottom, a parabola through it and its neighbours (YIN's step 5): at whole lags a
        # period between two of them (high notes: E6 is 4.55 lags) reads up to 0.2 on one clean string
        clean = aper
        if 1 < tau < tmax:
            den = dn[tau - 1] - 2 * dn[tau] + dn[tau + 1]
            if den > 0:
                clean = max(0.0, min(aper, aper - (dn[tau - 1] - dn[tau + 1]) ** 2 / (8 * den)))

        def d12(lag):
            a = x[:W12] - x[lag:lag + W12]
            v = float(np.dot(a, a))
            if base is not None:
                c_ = base[:W12] - base[lag:lag + W12]
                v -= float(np.dot(c_, c_))
            return v
        c = 2 * tau
        dd = [d12(c - 3 + i) for i in range(7)]
        best = 1
        for i in range(2, 6):
            if dd[i] < dd[best]:
                best = i
        den = dd[best - 1] - 2 * dd[best] + dd[best + 1]
        off = 0.5 * (dd[best - 1] - dd[best + 1]) / den if den > 0 else 0.0
        kf = (c - 3 + best) + max(-1.0, min(1.0, off))
        if kf < 24.5:                                       # an octave up? half the lag at 12 kHz, 8..12
            h = int(kf * 0.5 + 0.5)
            dh = [d12(h - 1 + i) for i in range(3)]
            hb = 1
            for i in (0, 2):
                if dh[i] < dh[hb]:
                    hb = i
            if dh[hb] <= 1.2 * dd[best]:
                o, dn2 = 0.0, dh[0] - 2 * dh[1] + dh[2]
                if hb == 1 and dn2 > 0:
                    o = max(-1.0, min(1.0, 0.5 * (dh[0] - dh[2]) / dn2))
                kf = (h - 1 + hb) + o
        return aper, clean, 12000.0 / kf

    def decide(self, blk):
        x, d = self.span, self.d6
        aper, clean, freq = self.yin(d, x)
        power = float(np.dot(x[:W12], x[:W12])) / W12
        voiced = power >= LEVEL_MIN * LEVEL_MIN and aper < APER_MAX
        age = blk - self.onset_blk
        pre = age < 0                                       # its samples were taken before the last pluck (SY test 24:
                                                            # none, the span is this block's; test 23: age < 3)
        if pre and self.lock_pending:
            self.d_base = d.copy()
        self.d_last = d.copy()
        sub = False
        if self.test6 and not pre and self.lock_pending and self.pluck_ref >= RING_MIN * self.pick_peak:
            dnew = d - self.d_base                          # what the pick added
            e_new, e_all = float(np.mean(dnew[50:])), float(np.mean(d[50:]))
            mabs, mn = float(np.mean(np.abs(dnew[1:]))), float(np.min(dnew[1:]))
            tmax = (age + 1) * 8 - W6                       # lags whose samples all came after the pluck (test 24)
            if e_new >= SUB_MIN * e_all and e_new > 0 and mn >= -SUB_NEG * mabs and tmax >= T6MIN + 2:
                a2, c2, f2 = self.yin(np.maximum(dnew, 0.0), x, self.base_x, min(tmax, T6MAX), THR_SUB)
                v2 = power >= LEVEL_MIN * LEVEL_MIN and a2 < APER_MAX
                ratio = f2 / freq
                k = int(ratio + 0.5)
                common = 2 <= k <= 6 and abs(ratio / k - 1) < COMMON_TOL
                if v2 and c2 <= CLEAN_APER and (not (voiced and clean <= CLEAN_APER) or common):
                    aper, clean, freq, voiced, sub = a2, c2, f2, v2, True
        midi = 69 + 12 * math.log2(freq / 440.0)
        note = round_s(midi)
        r = self.res
        r['analyses'] += 1
        r['voiced'] = int(voiced)
        r['freq10'] = int(freq * 10 + 0.5)
        r['cents'] = round_s((midi - note) * 100)
        r['quality'] = 0 if aper >= 1 else int((1 - aper) * 100 + 0.5)
        self.ycode = ((0x100 if voiced else 0) | (0x200 if clean <= CLEAN_APER else 0) |   # SY test 19: for the SY
                      min(max(note, 0), 126))                                            # engine's mono tones
        self.analyses.append((blk, voiced, freq, aper, note, clean, sub))
        if pre:
            return
        now = self.win_peak(blk, period_blocks(freq), self.onset_blk + 4)   # test 6: the level now, over a period
        if voiced and clean <= CLEAN_APER:                  # test 4: clean (one string; strings ringing together
            self.unvoiced = 0                               # read murky, and murky counts as nothing heard)
            self.voiced_level = self.recent_peak(blk)
            if self.first_pending:
                self.first_pending = False
                r['first_ms'] = ms(age)
            self.agree = self.agree + 1 if self.agree and self.prev_note == note else 1
            self.prev_note = note
            same = self.syn_note >= 0 and note == self.syn_note
            if same and abs(r['cents']) <= MOVE_STEADY:
                self.old_at = blk                           # SY test 27: the synth's note, read steady
            if self.agree >= AGREE and not (self.lock_pending and same and age < LOCK_SAME):   # SY test 24
                r['note'] = note
                if self.lock_pending:
                    v = ms(age)
                    self.lock_pending = False
                    r['lock_ms'] = v
                    r['lock_sum'] += v
                    if not r['locks'] or v < r['lock_min']:
                        r['lock_min'] = v
                    r['lock_max'] = max(r['lock_max'], v)
                    r['locks'] += 1
                    keep = CLICK_KEEP if self.pluck_click else self.repick
                    if self.test6 and now < PLUCK_HOLD * self.pluck_ref:
                        self.stops += 1                     # the level fell after it: a let-go, not a pick
                        if self.syn_note >= 0:
                            self.syn_send(-1)
                    elif self.pluck_click == 2 and now < SOFT_HOLD * self.pluck_ref:
                        self.syn_strays += 1                # SY test 25: a soft click whose level fell (a let-go's
                                                            # finger leaving the fret): nothing
                    elif not same or self.after_peak(blk) >= keep * self.pluck_ref:
                        self.syn_send(note, velocity(self.pick_peak))   # a pluck went steady: the synth plays it
                        self.sub_lock = sub
                        self.sub_locks += sub
                    else:
                        self.syn_strays += 1                # its own note, no pick's level: a stray pluck
                elif (self.syn_note >= 0 and not same and not self.drum and not self.sub_lock and
                      self.agree >= MOVE_AGREE and abs(r['cents']) <= MOVE_CENTS and
                      abs(note - self.syn_note) not in HARMONIC_JUMPS):
                    if self.test6 and now < MOVE_HOLD * self.env:
                        self.blocked += 1                   # far quieter than the note: a let-go, not a slide
                    else:
                        quick = (blk - self.old_at <= MOVE_QUICK and   # SY test 27: a fret change, not a bend or
                                 now >= QUICK_HOLD * self.win_peak(blk - QUICK_BACK, QUICK_WIN))   # slide; SY test
                        self.syn_send(note, velocity(self.level(blk)))  # 30: the level held. The pitch moved while
                        self.move_quick = int(quick)                    # it plays
        else:
            if voiced:
                self.murky += 1                             # strings ringing together: counts as nothing heard
            self.agree = 0
            self.prev_note = -1
            if not (self.sub_lock and power >= LEVEL_MIN * LEVEL_MIN):   # test 6: a chord's note holds while heard
                self.unvoiced += 1
            if self.unvoiced >= RELEASE:
                r['note'] = -1
                if self.syn_note >= 0:
                    if self.unvoiced >= SYN_RELEASE_LONG or self.recent_peak(blk) < SYN_DROP * self.voiced_level:
                        self.syn_send(-1)                   # the string stopped: let go
                    else:
                        self.syn_holds += 1                 # as loud as before: hold on
        if self.test6 and self.syn_note >= 0 and not self.lock_pending and \
                self.win_peak(blk, LEVEL_BLOCKS) < DROP * self.env:
            self.drops += 1
            self.syn_send(-1)                               # the level fell fast: a hand stopped the string
        if self.syn_note < 0:
            self.sub_lock = False


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


def guitar(freq, secs, amp=0.45, p=0.2, q=0.1, B=1e-4, seed=0, fs=48000, drive=0.0, beat=0.1, cents=0.0,
           vibrato=(0.0, 5.5), bend=None):
    """A string through a magnetic pickup: released from rest at p of its length, the pickup at q sensing its velocity
    (every harmonic in sine phase: the pulse-like wave of a real pickup, whose blocks swing far within a period),
    stiff-string inharmonicity B, higher harmonics dying faster, the pickup's resonance near 4 kHz, a slow beat of the
    two polarisations; peak `amp` in the first 50 ms; drive > 0 overdrives it (tanh). `cents` detunes it,
    `vibrato` = (depth in cents, rate in Hz) wobbles it and `bend` = (start s, end s, cents) bends it up evenly
    between start and end, held after."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(secs * fs)) / fs
    x = np.zeros_like(t)
    tau1 = 3.0 if freq < 150 else (2.0 if freq < 300 else 1.2)
    if cents or vibrato[0] or bend:
        c = cents + vibrato[0] * np.sin(2 * np.pi * vibrato[1] * t)
        if bend:
            c = c + bend[2] * np.clip((t - bend[0]) / (bend[1] - bend[0]), 0, 1)
        ph = 2 * np.pi * np.cumsum(freq * 2 ** (c / 1200)) / fs
    else:
        ph = 2 * np.pi * freq * t
    for n in range(1, 80):
        fn = n * freq * math.sqrt(1 + B * n * n)
        if fn > 7000:
            break
        r = fn / 4000.0
        a = math.sin(n * math.pi * p) * math.sin(n * math.pi * q) / n / math.sqrt((1 - r * r) ** 2 + (r / 1.5) ** 2)
        x += a * np.sin(n * math.sqrt(1 + B * n * n) * ph) * np.exp(-t * (1 + fn / 400.0) / tau1)
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


OPEN = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}       # string -> its open note (standard tuning)


def _hz(n):
    return 440 * 2 ** ((n - 69) / 12)


def _stiff(n):
    return 1e-4 if n < 55 else 3e-5


def hiss(x, seed, fs=48000):
    """Hiss (-74 dBFS) and 60 Hz hum (-66 dBFS), as open_strings has them."""
    r = np.random.default_rng(seed)
    t = np.arange(len(x)) / fs
    return x + r.normal(0, 2e-4, len(x)) + 5e-4 * np.sin(2 * np.pi * 60 * t + r.uniform(0, 2 * np.pi))


def let_go(string, fret, hold=0.15, kind='open', td=0.005, t_new=0.04, a_new=0.3, a_click=0.08, seed=0, tail=0.5,
           fs=48000):
    """Test 6: `string` fretted at `fret`, picked, and let go `hold` s later: the note is damped (time constant td);
    kind 'open': the open string sounds at a_new of the note's level and dies away (t_new), 'harm': the touch
    harmonic nearest the finger (k - 1 times the note), 'none': only the damping; the string leaving the fret clicks
    (a 3 ms burst of highs, a_click of the level). 0.2 s of quiet before, 0.25 s after; returns (signal, note)."""
    n_open = OPEN[string]
    note = n_open + fret
    x = guitar(_hz(note), hold + tail, seed=seed, B=_stiff(note))
    t = np.arange(len(x)) / fs
    r0 = int(hold * fs)
    level = np.max(np.abs(x[r0 - int(0.02 * fs):r0]))
    x[r0:] *= np.exp(-(t[r0:] - hold) / td)
    if kind in ('open', 'harm'):
        if kind == 'open':
            f = _hz(n_open)
        else:
            k = max(2, round(1 / (1 - 2 ** (-fret / 12))))
            f = (k - 1) * _hz(note)
        g = guitar(f, tail, amp=1.0, seed=seed + 100, B=_stiff(n_open))
        g *= np.exp(-np.arange(len(g)) / fs / t_new)
        g *= a_new * level / np.max(np.abs(g[:int(0.02 * fs)]))
        x[r0:r0 + len(g)] += g[:len(x) - r0]
    nc = int(0.003 * fs)
    rng = np.random.default_rng(seed + 7)
    c = np.diff(np.concatenate([[0], rng.normal(0, 1, nc) * np.exp(-np.arange(nc) / (0.0007 * fs))]))
    x[r0:r0 + nc] += a_click * level * c / np.max(np.abs(c))
    return hiss(np.concatenate([np.zeros(fs // 5), x, np.zeros(fs // 4)]), seed), note


def arpeggio(shape, gap=0.3, seed=0, extra=1.0, fs=48000):
    """Test 6: a chord held and its strings picked one by one, `gap` s apart (shape: (string, fret) pairs in the order
    picked), every string ringing on, all stopped by hand `extra` s after the last; returns (signal, notes)."""
    notes = [OPEN[s] + f for s, f in shape]
    total = gap * len(notes) + extra
    x = np.zeros(int(total * fs))
    for k, n in enumerate(notes):
        at = int(k * gap * fs)
        s = guitar(_hz(n), total - k * gap, seed=seed + k, B=_stiff(n))
        x[at:at + len(s)] += s[:len(x) - at]
    d = int(0.05 * fs)
    x[-d:] *= np.linspace(1, 0, d)
    return hiss(np.concatenate([np.zeros(fs // 5), x, np.zeros(fs // 2)]), seed), notes


CHORDS = {   # (string, fret) low to high
    'C': [(5, 3), (4, 2), (3, 0), (2, 1), (1, 0)],              # C3 E3 G3 C4 E4
    'G': [(6, 3), (5, 2), (4, 0), (3, 0), (2, 0), (1, 3)],      # G2 B2 D3 G3 B3 G4
    'D': [(4, 0), (3, 2), (2, 3), (1, 2)],                      # D3 A3 D4 F#4
    'Am': [(5, 0), (4, 2), (3, 2), (2, 1), (1, 0)],             # A2 E3 A3 C4 E4
    'E': [(6, 0), (5, 2), (4, 2), (3, 1), (2, 0), (1, 0)],      # E2 B2 E3 G#3 B3 E4
    'Em7': [(4, 2), (3, 0), (2, 3), (1, 0)],                    # E3 G3 D4 E4
}


def to_blocks(x, noise=0.0, seed=1):
    """A signal at full scale 1.0 as the integer side's 64-value blocks (int16, as (L + R) >> 1 of equal L and R)."""
    if noise:
        x = x + np.random.default_rng(seed).normal(0, noise, len(x))
    s = np.clip(np.round(x * 32767), -32768, 32767).astype(int)
    n = len(s) // FRAMES
    return [list(map(int, s[i * FRAMES:(i + 1) * FRAMES])) for i in range(n)]
