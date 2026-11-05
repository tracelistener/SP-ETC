/* SY synth tests 1 and 2, the FPU side: a polyphonic guitar synth in the way Roland's patent US 9,542,923 describes
 * BOSS's SY pedals. No notes are found: the guitar is split into 49 bands a semitone apart (E2..E6), each band's pitch
 * comes from its zero crossings and its level from its energy, and each drives oscillators of its own, so the
 * strings of a chord play together. Everything here runs on the audio task through sy_fp_call (the tracker's 2 KB
 * stack, used one after the other; FPSCR and d0-d15 saved, round to nearest, flush to zero, default NaN), after the
 * tracker's step.
 *
 * One step per RX block (sy_rx in tune_test.c decides when), from pair 0's (L + R) / 2 (tt.in):
 *   - a 4th-order Butterworth low-pass at 2 kHz, every 4th sample (12 kHz, 16 a block); the block's peak drives a
 *     peak follower falling with a 0.3 s time constant (the playing's level);
 *   - every band: two band-pass stages at its centre (a 4th-order band-pass, Q 8 at E2 rising to 16 at E4 and above,
 *     the stages at 0.6436 x that so the pair has one stage's bandwidth: half the leak of one stage from strings 3-5
 *     semitones away); its energy (a follower over 1.5 of its periods, at least 2 ms); its positive zero crossings,
 *     each counted once the band has gone below -0.25 x its level (sqrt(2 x energy)), the crossing's place found by a
 *     straight line between its two samples. A period within 300 cents of the centre goes into an alpha-beta tracker
 *     (0.2, 0.02: it smooths the beating of strings ringing together and follows a bend), which starts at the
 *     centre when the band wakes; a band under -60 dBFS is asleep;
 *   - a band sounds when it has counted two periods, its energy tops both neighbours' and its period is within 80
 *     cents of its centre: a partial sounds from one band (its neighbours read the same pitch weaker), and the bands
 *     between two partials, whose crossings follow neither, stay silent. A band that starts to sound while its
 *     neighbour stops, on the same pitch within 1%, takes the neighbour's phases and amplitude (test 2: and the
 *     neighbour stops at once), so a bend hands its voice on without a gap or a new attack;
 *   - the sum through a resonant state-variable filter, a soft clip (1.5x - 0.5x^3, +-1 beyond), x 16384 for the DRY
 *     pair (-6 dBFS at the clip, as the cabinet's). A stop (sy.stopping) fades it out over 8 blocks.
 *
 * Test 2: the tone (SY_TONE, from sy_ref.py; sy.tone_req, picked on the unit) sets
 *   - each sounding band's oscillators: wave A (a saw or a pulse with a polyBLEP at each jump, a triangle, a sine) at
 *     the band's pitch, and optionally wave B at a ratio of it, added at a level or phase-modulating A (FM, its index
 *     raised at a pick); the band's amplitude (level - floor) x 1.2 reached through the tone's attack and release. A
 *     band that sounded under 32 ms (ownership flickering between neighbours, not a note) stops at once: with every
 *     such flicker releasing, a chord kept 18-26 bands running instead of 9-12. Each wave is its own loop (one pass
 *     for A, one for B), so no sample tests which wave it is;
 *   - breath noise, at a part of the bands' summed amplitude;
 *   - the filter: low-, band- or high-pass, its cutoff from the level (an exponential sweep over the tone's range),
 *     a pick envelope (a pick: the block's peak twice the highest of blocks 3-18 back, as the tracker's test 2 rule)
 *     and an LFO, its resonance;
 *   - the LFO's vibrato and tremolo, a 16-step gate at 1/16 of the SP's tempo (sy.bpm100), the output gain.
 *   A new tone fades the output out over 8 blocks, switches (the filter, LFO, pick envelope and gate from rest), and
 *   fades it in again.
 *
 * Test 3: each block, the tone playing with its three knobs (sy.knob[tone], knob positions - 64, set on the unit with
 * VALUE + CTRL 1-3; sy_knobs): BRIGHT adds -2..+2 octaves to the cutoff, LEVEL scales the output 0..2 x, and CTRL 2
 * sets the tone's own P2 (sy_ref.TONES p2). A knob at 64 leaves the tone's value as designed.
 *
 * Test 5 (the tones stood out too little from the guitar: each partial had its own oscillator at its own level), per
 * tone: FUND (a band whose pitch is a whole multiple 2..8, within 3%, of a lower band sounding in the same block stays
 * silent: a note sounds from its lowest band only), SUSTAIN (while a band still sounds, a falling level is followed at
 * the tone's rate instead of the release's) and OCTAVE (the oscillators x 2^-2..2^2). sy.oct / sy.susk hold the guitar
 * synth screen's settings (0: as designed). And a band's first 4 periods after it wakes are counted, not tracked (they
 * span the band-pass's start and read long: FUND left the note's start audibly flat).
 *
 * Test 6 (single notes sounded rough: a band's ownership flickers while a note starts, and FUND hangs a note on one
 * band): a band 20 dB under the loudest owned band is silent, one that stops owning sounds on for SY_HOLD blocks while
 * its energy keeps SY_HOLD_E of its owned one, FUND goes to the 16th harmonic and needs the lower band at SY_FUND_REL of
 * the multiple's energy, a note sounds at its loudest partial's level, and DYNAMICS (sy.dynk) pulls the levels toward
 * one (sy_dyn).
 *
 * Single precision throughout, no contraction (the pragma below): every fused multiply-add is an explicit fmaf, so
 * tunetest/sy_ref.py computes the same numbers; test_tune_test.py runs both on the same input.
 */
#pragma STDC FP_CONTRACT OFF
#include "tune_test.h"
#include "sy_tables.h"     /* from the builder (sy_ref.py's tables): SY_DEC, SY_BAND, SY_TONE, the constants */

#define FMA(a, b, c) __builtin_fmaf((a), (b), (c))
_Static_assert(SY_TONES == 15, "sy_t's knob table holds 15 tones");

/* fn(arg) on the stack that ends at stack_top (8-byte aligned), with FPSCR and d0-d15 saved on it. */
__attribute__((naked, used)) u32 sy_fp_call(u32 (*fn)(sy_t *), sy_t *arg, void *stack_top) {
    __asm__ volatile(
        "mov r12, sp\n"
        "mov sp, r2\n"
        "push {r4, r5, r12, lr}\n"
        "vmrs r4, fpscr\n"
        "vpush {d0-d15}\n"
        "bic r5, r4, #0x00c00000\n"            /* round to nearest */
        "orr r5, r5, #0x03000000\n"            /* default NaN, flush to zero */
        "vmsr fpscr, r5\n"
        "mov r5, r0\n"
        "mov r0, r1\n"
        "blx r5\n"
        "vpop {d0-d15}\n"
        "vmsr fpscr, r4\n"
        "pop {r4, r5, r12, lr}\n"
        "mov sp, r12\n"
        "bx lr\n");
}

static void sy_init(sy_block_t *b, const sy_t *s) {
    for (u32 k = 0; k < SY_BANDS; k++) {
        b->per[k] = SY_BAND[k].pc;
        b->tl[k] = SY_TL_MIN;
    }
    b->mg = 1.0f;
    b->gate = 1.0f;
    b->last_pick = -1000;
    b->tone = s->tone_req < SY_TONES ? s->tone_req : 0u;
    b->started = 1;
}

/* The input to 12 kHz (x12), the differences two samples apart the band-passes take (dx); returns the peak. */
static float sy_input(sy_block_t *b, float *x12, float *dx) {
    float z00 = b->dz[0][0], z01 = b->dz[0][1], z10 = b->dz[1][0], z11 = b->dz[1][1], pk = 0.0f;
    for (u32 f = 0; f < FRAMES; f++) {
        float v = (float)tt.in[f] * SY_IN_SCALE;
        float y = FMA(SY_DEC[0][0], v, z00);
        z00 = FMA(SY_DEC[0][1], v, FMA(-SY_DEC[0][3], y, z01));
        z01 = FMA(SY_DEC[0][2], v, -SY_DEC[0][4] * y);
        v = y;
        y = FMA(SY_DEC[1][0], v, z10);
        z10 = FMA(SY_DEC[1][1], v, FMA(-SY_DEC[1][3], y, z11));
        z11 = FMA(SY_DEC[1][2], v, -SY_DEC[1][4] * y);
        if ((f & 3u) == 3u) {
            x12[f >> 2] = y;
            float a = __builtin_fabsf(y);
            pk = a > pk ? a : pk;
        }
    }
    b->dz[0][0] = z00;
    b->dz[0][1] = z01;
    b->dz[1][0] = z10;
    b->dz[1][1] = z11;
    dx[0] = x12[0] - b->xh[0];
    dx[1] = x12[1] - b->xh[1];
    for (u32 j = 2; j < SY_SUB; j++)
        dx[j] = x12[j] - x12[j - 2];
    b->xh[0] = x12[SY_SUB - 2];
    b->xh[1] = x12[SY_SUB - 1];
    return pk;
}

/* A crossing's period into the band's tracker (or, outside 300 cents, the band measures again). Test 5: the first
 * SY_SKIP (4) periods after a wake span the band-pass's start and read long (-138, -51, -22, -12 cents on every string:
 * the tracker began up to 36 cents flat and took 100 ms to come up on the low E, which FUND left audible), so they are
 * counted, not tracked: the tracker sits at the band's centre (set at the wake) and takes the fifth. */
static void sy_period(sy_block_t *b, u32 k, const sy_band_t *c, float p) {
    if (!(p > c->plo && p < c->phi)) {
        b->nper[k] = 0;
        return;
    }
    u32 np = b->nper[k];
    if (np >= SY_SKIP) {
        float base = b->per[k] + b->trend[k], tr = b->trend[k];
        float r = p - base;
        b->per[k] = FMA(SY_ALPHA, r, base);
        b->trend[k] = FMA(SY_BETA, r, tr);
    } else if (np == 0) {
        b->per[k] = c->pc;
        b->trend[k] = 0.0f;
    }
    b->nper[k] = (u8)(np < 255u ? np + 1u : 255u);
}

/* One 12 kHz sample J of a band: both stages (U1/Y1 the newest outputs, U2/Y2 the ones before; the new outputs go
 * into U2/Y2, so the next sample swaps the roles and no register is copied), the energy, the crossing test. */
#define SY_SAMPLE(J, U1, U2, Y1, Y2)                                                                           \
    do {                                                                                                       \
        float u_ = FMA(b0, dx[J], FMA(na1, U1, na2 * U2));                                                     \
        float y_ = FMA(b0, u_ - U2, FMA(na1, Y1, na2 * Y2));                                                   \
        float yprev_ = Y1;                                                                                     \
        U2 = u_;                                                                                               \
        Y2 = y_;                                                                                               \
        float yy_ = y_ * y_;                                                                                   \
        e = FMA(lc, yy_ - e, e);                                                                               \
        if (y_ < 0.0f) {                                                                                       \
            if (yy_ > SY_ARM2 * e) armed = 1;                                                                  \
        } else if (armed) {                                                                                    \
            armed = 0;                                                                                         \
            float tc_ = (float)((s32)(J) - 1) + yprev_ / (yprev_ - y_);                                         \
            float p_ = tc_ - tl;                                                                               \
            tl = tc_;                                                                                          \
            crossings++;                                                                                       \
            sy_period(b, k, c, p_);                                                                            \
        }                                                                                                      \
    } while (0)

/* Every band through its two band-pass stages, its energy and its crossings. Returns the crossings. */
static u32 sy_bands(sy_block_t *b, const float *dx) {
    u32 crossings = 0;
    for (u32 k = 0; k < SY_BANDS; k++) {
        const sy_band_t *c = &SY_BAND[k];
        float b0 = c->b0, na1 = c->na1, na2 = c->na2, lc = c->lc;
        float ua1 = b->ua1[k], ua2 = b->ua2[k], yb1 = b->yb1[k], yb2 = b->yb2[k], e = b->e[k], tl = b->tl[k];
        u32 armed = b->armed[k];
        for (u32 j = 0; j < SY_SUB; j += 2) {
            SY_SAMPLE(j, ua1, ua2, yb1, yb2);                /* the newest now in ua2/yb2 */
            SY_SAMPLE(j + 1, ua2, ua1, yb2, yb1);            /* and back in ua1/yb1 */
        }
        tl = tl - (float)SY_SUB;
        if (tl < SY_TL_MIN) tl = SY_TL_MIN;
        b->ua1[k] = ua1;
        b->ua2[k] = ua2;
        b->yb1[k] = yb1;
        b->yb2[k] = yb2;
        b->e[k] = e;
        b->tl[k] = tl;
        b->armed[k] = (u8)armed;
        if (e < SY_E_FLOOR) b->nper[k] = 0;
    }
    return crossings;
}

/* 2^x for x in (-32, 32): the cubic for the fraction, the power of two from the exponent bits (test 3). */
static float sy_exp2(float x) {
    s32 i = (s32)(x + 32.0f) - 32;
    float fr = x - (float)i;
    float p = FMA(fr, FMA(fr, FMA(fr, SY_C3, SY_C2), SY_C1), 1.0f);
    union {
        u32 u;
        float f;
    } q;
    q.u = (u32)(i + 127) << 23;
    return p * q.f;
}

/* Test 6: log2 of a positive normal x: the exponent bits, a cubic for the mantissa's (error under 0.0013). */
static float sy_log2(float x) {
    union {
        u32 u;
        float f;
    } q;
    q.f = x;
    s32 ex = (s32)(q.u >> 23) - 127;
    q.u = (q.u & 0x7FFFFFu) | 0x3F800000u;
    float f = q.f - 1.0f;
    return FMA(f, FMA(f, FMA(f, SY_L3, SY_L2), SY_L1), (float)ex);
}

/* Test 6: DYNAMICS d (0..1) on a band's level: 2^(d (log2 lev - log2 DYN_LEV) + log2 DYN_LEV); d 1 leaves it. */
static float sy_dyn(float lev, float d) { return sy_exp2(FMA(d, sy_log2(lev) - SY_DYN_L2, SY_DYN_L2)); }

/* Test 5: SUSTAIN s (0..100) as a per-block rate: 0 none; else x - x^2 / 2 for x = one block over 40 ms x 2^(0.08 s). */
static float sy_sus(u32 s) {
    if (!s) return 0.0f;
    float tau = SY_SUS_MS0 * sy_exp2((float)s * SY_SUS_STEP);
    float x = SY_BLOCK_MS / tau;
    return FMA(-0.5f * x, x, x);
}

/* Test 3: the tone with its knobs (kd: CTRL 1-3 as knob position - 64). CTRL 2 is left alone at 64, so the tone's
 * value stays exactly as designed (the exp2 above is a close approximation, not the table's). Test 5: OCTAVE (0 as
 * designed, 1..5: x 2^-2..2^2) and SUSTAIN (0 as designed, 1..101: 0..100). Test 6: DYNAMICS (0 as designed,
 * 1..101: 0..100). */
static void sy_knobs(sy_tone_t *t, const sy_t *s, u32 tone) {
    const volatile s8 *kd = s->knob[tone];
    u32 o = (u32)s->oct[tone], su = s->susk[tone], dk = s->dynk[tone];
    if (dk - 1u <= 100u) t->dyn = (float)(dk - 1u) * 0.01f;
    if (o - 1u < SY_OCTAVES) {
        t->octm = SY_OCTM[o - 1u];
        t->roct = SY_OCTM[SY_OCTAVES - o];
    }
    if (su - 1u <= 100u) t->sus = sy_sus(su - 1u);
    s32 k1 = kd[0], k2 = kd[1], k3 = kd[2];
    t->bright = ((float)k1 * 0.015625f) * 2.0f;
    t->gain = t->gain * ((float)(64 + k3) * 0.015625f);
    if (!k2) return;
    float c2 = (float)k2 * 0.015625f, v2 = (float)(64 + k2) * 0.015625f;
    switch (t->p2kind) {
    case 0:                                             /* resonance: Q x 2^(c span) */
        t->r2 = t->r2 * sy_exp2(-c2 * t->p2span);
        break;
    case 1:                                             /* pulse width */
        t->pw = FMA(c2, t->p2span, t->pw);
        break;
    case 2: {                                           /* detune: cents x 2^(c span) */
        float cents = t->p2base * sy_exp2(c2 * t->p2span);
        t->rb = sy_exp2(cents * SY_INV1200);
        break;
    }
    case 3: {                                           /* attack: ms x 2^(c span); 1 - e^-x as x - x^2 / 2 */
        float tau = t->p2base * sy_exp2(c2 * t->p2span);
        float x = SY_BLOCK_MS / tau;
        t->att = FMA(-0.5f * x, x, x);
        break;
    }
    case 4:                                             /* LFO speed */
        t->lfo_inc = t->lfo_inc * sy_exp2(c2 * t->p2span);
        break;
    case 5:                                             /* breath */
        t->noise = t->noise * v2;
        break;
    case 6:                                             /* FM depth at a pick */
        t->fm_env = t->fm_env * v2;
        break;
    case 7:                                             /* the pick envelope's octaves */
        t->fenv = t->fenv * v2;
        break;
    case 8:                                             /* wave B's level (the sub) */
        t->lb = t->lb * v2;
        break;
    default:                                            /* the steps a beat: 2, 4, 8 */
        t->seqdiv = k2 < -21 ? 2u : k2 < 22 ? 4u : 8u;
        break;
    }
}

/* sin(pi ph) for ph in [-1, 1): a parabola, then one correction (error about 0.001). */
static inline __attribute__((always_inline)) float sy_sine(float ph) {
    float s = (ph * (1.0f - __builtin_fabsf(ph))) * 4.0f;
    float c = s * __builtin_fabsf(s);
    return FMA(0.225f, c - s, s);
}

/* The polyBLEP's two halves: x in [0, 1) just after a jump, in (-1, 0) just before. */
static inline __attribute__((always_inline)) float sy_after(float x) { return ((x + x) - x * x) - 1.0f; }
static inline __attribute__((always_inline)) float sy_before(float x) { return (x * x + (x + x)) + 1.0f; }

/* One sample of a wave from its ramp ph (-1..1): 0 saw, 1 pulse (high below pw), 2 triangle, 3 sine. The saw falls
 * and the pulse rises at the wrap (|ph| > 1 - inc: within a sample of it), the pulse falls at pw (|ph - pw| < inc). */
static inline __attribute__((always_inline)) float sy_wave(u32 kind, float ph, float pw, float inc, float rinc,
                                                           float hi) {
    if (kind == 0u) {
        if (__builtin_fabsf(ph) > hi)
            return ph - (ph < 0.0f ? sy_after((ph + 1.0f) * rinc) : sy_before((ph - 1.0f) * rinc));
        return ph;
    }
    if (kind == 1u) {
        float v = ph < pw ? 1.0f : -1.0f;
        if (__builtin_fabsf(ph) > hi)
            v = v + (ph < 0.0f ? sy_after((ph + 1.0f) * rinc) : sy_before((ph - 1.0f) * rinc));
        float q = ph - pw;
        if (__builtin_fabsf(q) < inc)
            v = v - (q >= 0.0f ? sy_after(q * rinc) : sy_before(q * rinc));
        return v;
    }
    if (kind == 2u)
        return FMA(-2.0f, __builtin_fabsf(ph), 1.0f);
    return sy_sine(ph);
}

/* One wave over a block into acc: its ramp from *php by inc a sample, the amplitude from a by da. One loop per wave,
 * so no sample tests which wave it is. */
#define SY_PASS(NAME, KIND)                                                                                    \
    static __attribute__((noinline)) void NAME(float *acc, float *php, float pw, float inc, float rinc, float a, \
                                               float da) {                                                     \
        float ph = *php, hi = 1.0f - inc;                                                                      \
        for (u32 n = 0; n < FRAMES; n++) {                                                                     \
            ph = ph + inc;                                                                                     \
            if (ph >= 1.0f) ph = ph - 2.0f;                                                                    \
            a = a + da;                                                                                        \
            acc[n] = FMA(a, sy_wave(KIND, ph, pw, inc, rinc, hi), acc[n]);                                     \
        }                                                                                                      \
        *php = ph;                                                                                             \
    }
SY_PASS(sy_pass_saw, 0u)
SY_PASS(sy_pass_pulse, 1u)
SY_PASS(sy_pass_tri, 2u)
SY_PASS(sy_pass_sine, 3u)

static void sy_pass(u32 kind, float *acc, float *php, float pw, float inc, float rinc, float a, float da) {
    if (kind == 0u)
        sy_pass_saw(acc, php, pw, inc, rinc, a, da);
    else if (kind == 1u)
        sy_pass_pulse(acc, php, pw, inc, rinc, a, da);
    else if (kind == 2u)
        sy_pass_tri(acc, php, pw, inc, rinc, a, da);
    else
        sy_pass_sine(acc, php, pw, inc, rinc, a, da);
}

/* FM: B (a sine at incb) moves A's phase by fmi x its value; A a sine. */
static __attribute__((noinline)) void sy_pass_fm(float *acc, float *php, float *phbp, float inc, float incb, float fmi,
                                                float a, float da) {
    float ph = *php, phb = *phbp;
    for (u32 n = 0; n < FRAMES; n++) {
        ph = ph + inc;
        if (ph >= 1.0f) ph = ph - 2.0f;
        a = a + da;
        phb = phb + incb;
        if (phb >= 1.0f) phb = phb - 2.0f;
        float x = FMA(fmi, sy_sine(phb), ph);
        while (x >= 1.0f)
            x = x - 2.0f;
        while (x < -1.0f)
            x = x + 2.0f;
        acc[n] = FMA(a, sy_sine(x), acc[n]);
    }
    *php = ph;
    *phbp = phb;
}

/* A band's oscillators over a block, into acc: wave A at the band's pitch (x the vibrato), then wave B at rb x it at
 * lb x the amplitude (or, for FM, B phase-modulating A with the index fmi), the amplitude ramped from a0 to a1. */
static void sy_osc(sy_block_t *b, u32 k, const sy_tone_t *t, float a0, float a1, float vibr, float fmi, float *acc) {
    float per = b->per[k];
    float inc = ((0.5f / per) * vibr) * t->octm, rinc = ((per + per) / vibr) * t->roct;   /* test 5: OCTAVE */
    float da = (a1 - a0) * (1.0f / 64.0f);
    float ph = b->ph[k], phb = b->phb[k];
    if (t->fm) {
        sy_pass_fm(acc, &ph, &phb, inc, inc * t->rb, fmi, a0, da);
    } else {
        sy_pass(t->wa, acc, &ph, t->pw, inc, rinc, a0, da);
        if (t->wb) sy_pass(t->wb - 1u, acc, &phb, t->pw, inc * t->rb, rinc / t->rb, a0 * t->lb, da * t->lb);
    }
    b->amp[k] = a1;
    b->ph[k] = ph;
    b->phb[k] = phb;
}

/* The bands that sound, the voice a band taking over a neighbour's pitch takes, and every sounding (or releasing)
 * band's oscillators added into acc. Returns the bands sounding; *namp the bands' summed amplitude. */
static u32 sy_voices(sy_block_t *b, const sy_tone_t *t, float vibr, float *acc, float *namp) {
    u8 own[SY_BANDS];
    float lmax[SY_BANDS];                           /* test 6: the loudest partial FUND silenced, per fundamental */
    float emax = 0.0f;
    for (u32 k = 0; k < SY_BANDS; k++) {
        float e = b->e[k], p = b->per[k];
        float el = k ? b->e[k - 1] : 0.0f, er = k + 1u < SY_BANDS ? b->e[k + 1] : 0.0f;
        own[k] = (u8)(e >= SY_E_FLOOR && b->nper[k] >= 2u && e >= el && e >= er && p > SY_BAND[k].olo &&
                      p < SY_BAND[k].ohi);
        if (own[k] && e > emax) emax = e;
        lmax[k] = 0.0f;
    }
    /* test 6: a band 20 dB under the loudest owned band is silent (a pick's ring in an empty band, a weak partial);
     * one that stops owning sounds on for SY_HOLD blocks (the rule flickers while a note starts), while its energy keeps
     * SY_HOLD_E of what it had owning (a pick's ring, a string stopped: no hold) */
    float gate = emax * SY_GATE2;
    for (u32 k = 0; k < SY_BANDS; k++) {
        if (own[k] && b->e[k] < gate) own[k] = 0;
        if (own[k]) {
            b->hold[k] = (u8)SY_HOLD;
            b->ehold[k] = b->e[k];
        } else if (b->hold[k]) {
            if (b->e[k] < SY_HOLD_E * b->ehold[k]) {
                b->hold[k] = 0;
            } else {
                b->hold[k]--;
                own[k] = 1;
            }
        }
    }
    if (t->fund) {                                  /* test 5: a whole multiple of a lower sounding band is silent */
        u8 keep[SY_BANDS];
        for (u32 k = 0; k < SY_BANDS; k++) {
            keep[k] = own[k];
            if (!own[k]) continue;
            for (u32 j = 0; j < k; j++) {
                if (!own[j]) continue;
                float r = b->per[j] / b->per[k];
                s32 h = (s32)(r + 0.5f);
                if (h >= 2 && h <= SY_HARM_MAX && __builtin_fabsf(r - (float)h) < SY_HARM_TOL * (float)h &&
                    !(b->e[j] < SY_FUND_REL * b->e[k])) {   /* test 6: not a pick's ring under a note */
                    keep[k] = 0;
                    if (b->e[k] > lmax[j]) lmax[j] = b->e[k];
                    b->fund_cut++;
                    break;
                }
            }
        }
        for (u32 k = 0; k < SY_BANDS; k++)
            own[k] = keep[k];
    }
    for (u32 k = 0; k < SY_BANDS; k++) {
        if (!own[k] || b->owned[k]) continue;
        b->age[k] = 0;
        for (u32 side = 0; side < 2u; side++) {
            s32 nb = side ? (s32)k + 1 : (s32)k - 1;
            if (nb < 0 || nb >= (s32)SY_BANDS || !b->owned[nb]) continue;
            if (__builtin_fabsf(b->per[nb] - b->per[k]) < 0.01f * b->per[k]) {
                b->ph[k] = b->ph[nb];
                b->phb[k] = b->phb[nb];
                b->amp[k] = b->amp[nb];
                b->age[k] = b->age[nb];
                b->amp[nb] = 0.0f;
                break;
            }
        }
    }
    for (u32 k = 0; k < SY_BANDS; k++)              /* test 2: a band's age; kept while it releases */
        if (own[k] && b->age[k] < 255u) b->age[k]++;
    float fmi = FMA(t->fm_env, b->fe, t->lb);
    u32 on = 0;
    float sum = 0.0f;
    for (u32 k = 0; k < SY_BANDS; k++) {
        float tg = 0.0f;
        if (own[k]) {
            float e = b->e[k];
            if (lmax[k] > e) e = lmax[k];               /* test 6: a note at its loudest partial's level */
            float lev = __builtin_sqrtf(e + e);
            if (t->dyn < 1.0f) lev = sy_dyn(lev, t->dyn);   /* test 6: DYNAMICS */
            tg = (lev - SY_FLOOR) * SY_GAIN;
            if (!(tg > 0.0f)) tg = 0.0f;
        }
        float a0 = b->amp[k];
        /* a band that sounded under 32 ms (a neighbour's flicker, not a note) stops at once, never releasing; test 5:
         * while it still sounds, SUSTAIN's rate for a falling level */
        float coef = tg > a0 ? t->att : (own[k] && t->sus > 0.0f) ? t->sus : b->age[k] >= SY_AGE_MIN ? t->rel : 1.0f;
        float a1 = coef >= 1.0f ? tg : FMA(tg - a0, coef, a0);
        if (!(tg > 0.0f) && a1 < SY_AMP_EPS) a1 = 0.0f;
        if (!(a0 > 0.0f || a1 > 0.0f)) continue;
        on += tg > 0.0f;
        sum = sum + a1;
        sy_osc(b, k, t, a0, a1, vibr, fmi, acc);
    }
    for (u32 k = 0; k < SY_BANDS; k++)
        b->owned[k] = own[k];
    *namp = sum;
    return on;
}

/* The output: the filter (cutoff from the level, the pick envelope, the LFO), the gain, the tremolo and the step gate,
 * the soft clip, the fade (a stop, or a tone req not yet the block's), to s->out. Returns the fade. */
static float sy_output(sy_t *s, sy_block_t *b, const sy_tone_t *t, float lfo, u32 req, const float *acc) {
    float d = b->env * SY_RDYN;
    if (d > 1.0f) d = 1.0f;
    float xo = FMA(t->fenv, b->fe, t->lfo_oct * lfo);
    xo = FMA(t->oct, __builtin_sqrtf(d), xo);
    xo = xo + t->bright;                                /* test 3: CTRL 1 */
    if (xo > t->xmax) xo = t->xmax;
    if (xo < SY_X_MIN) xo = SY_X_MIN;
    s32 i = (s32)(xo + 8.0f) - 8;
    float fr = xo - (float)i;
    float p2 = FMA(fr, FMA(fr, FMA(fr, SY_C3, SY_C2), SY_C1), 1.0f);
    union {
        u32 u;
        float f;
    } q;
    q.u = (u32)(i + 127) << 23;                         /* 2^i */
    float fc = t->fc_lo * p2 * q.f;
    float wv = fc * SY_PI_FS;
    float w2 = wv * wv;
    float g = wv * FMA(w2, FMA(w2, SY_T5, SY_T3), 1.0f);
    float k2 = t->r2;
    float nk1 = -(k2 + g);
    float hh = 1.0f / FMA(g, k2 + g, 1.0f);
    float tm = FMA(-t->trem, FMA(0.5f, lfo, 0.5f), 1.0f);
    float gb = t->gain * tm;
    float gt = 1.0f;
    if (t->seq) {
        u32 div = t->seqdiv;                            /* test 3: 2, 4 or 8 a beat; the 16 steps then wrap */
        float wrap = (float)(16u / div);
        float sp = b->seq_ph + (float)s->bpm100 * SY_BEAT;
        if (sp >= wrap) sp = sp - wrap;
        b->seq_ph = sp;
        gt = (t->seq >> ((u32)(s32)(sp * (float)div) & 15u)) & 1u ? 1.0f : 0.0f;
    }
    float mgt = (s->stopping || req != b->tone) ? 0.0f : 1.0f;
    float s1 = b->s1, s2 = b->s2, mg = b->mg, gate = b->gate;
    u32 mode = t->fmode;
    for (u32 n = 0; n < FRAMES; n++) {
        float v = FMA(nk1, s1, acc[n]);
        v = v - s2;
        float hp = v * hh;
        float bp = FMA(g, hp, s1);
        s1 = FMA(g, hp, bp);
        float lp = FMA(g, bp, s2);
        s2 = FMA(g, bp, lp);
        float yv = mode == 0u ? lp : mode == 1u ? bp * k2 : hp;
        yv = yv * gb;
        gate = FMA(gt - gate, SY_GATE_K, gate);
        yv = yv * gate;
        if (yv > 1.0f) {
            yv = 1.0f;
        } else if (yv < -1.0f) {
            yv = -1.0f;
        } else {
            yv = yv * FMA(-0.5f, yv * yv, 1.5f);
        }
        if (mg < mgt) {
            mg = mg + SY_FADE;
            if (mg > mgt) mg = mgt;
        } else if (mg > mgt) {
            mg = mg - SY_FADE;
            if (mg < mgt) mg = mgt;
        }
        yv = yv * mg;
        s->out[n] = (s32)(yv * SY_OUT_SCALE);
    }
    b->s1 = s1;
    b->s2 = s2;
    b->mg = mg;
    b->gate = gate;
    return mg;
}

u32 sy_fp_step(sy_t *s) {
    sy_block_t *b = &sy_block;
    float x12[SY_SUB], dx[SY_SUB], acc[FRAMES];
    if (!b->started) sy_init(b, s);
    u32 req = s->tone_req;
    if (req >= SY_TONES) req = b->tone;
    sy_tone_t tone = SY_TONE[b->tone];                  /* test 3: with its knobs (test 5: OCTAVE, SUSTAIN) */
    sy_knobs(&tone, s, b->tone);
    const sy_tone_t *t = &tone;
    float pk = sy_input(b, x12, dx);
    float ev = b->env * SY_ENV_K;
    b->env = pk > ev ? pk : ev;
    /* test 2: a pick restarts the pick envelope (the filter's, FM's index) */
    u32 blk = b->blocks, picked = 0;
    b->peaks[blk & 31u] = pk;
    if (blk >= SY_P_TO) {
        float ref = 0.0f;
        for (u32 kk = SY_P_FROM; kk <= SY_P_TO; kk++) {
            float v = b->peaks[(blk - kk) & 31u];
            ref = v > ref ? v : ref;
        }
        picked = pk >= SY_P_MIN && pk >= SY_P_RATIO * ref && (s32)blk - b->last_pick >= (s32)SY_REFRACTORY;
    }
    if (picked) {
        b->fe = 1.0f;
        b->last_pick = (s32)blk;
    } else {
        b->fe = b->fe * t->fdec;
    }
    float lph = b->lfo_ph + t->lfo_inc;
    if (lph >= 1.0f) lph = lph - 2.0f;
    b->lfo_ph = lph;
    float lfo = sy_sine(lph);
    float vibr = FMA(t->vib, lfo, 1.0f);
    b->crossings += sy_bands(b, dx);
    for (u32 n = 0; n < FRAMES; n++)
        acc[n] = 0.0f;
    float namp;
    s->sounding = sy_voices(b, t, vibr, acc, &namp);
    if (t->noise > 0.0f) {
        float nl = namp * t->noise;
        u32 ns = b->ns;
        for (u32 n = 0; n < FRAMES; n++) {
            ns = ns * 1664525u + 1013904223u;
            acc[n] = FMA(nl, (float)(s32)ns * 0x1p-31f, acc[n]);
        }
        b->ns = ns;
    }
    float mg = sy_output(s, b, t, lfo, req, acc);
    if (req != b->tone && mg <= 0.0f && !s->stopping) {     /* faded out: the new tone, from rest */
        b->tone = req;
        b->fe = 0.0f;
        b->lfo_ph = 0.0f;
        b->seq_ph = 0.0f;
        b->gate = 1.0f;
        b->s1 = 0.0f;
        b->s2 = 0.0f;
    }
    b->blocks++;
    return s->stopping && mg <= 0.0f ? SY_OFF : SY_RUN;
}
