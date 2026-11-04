/* SY synth test 1, the FPU side: a polyphonic guitar synth in the way Roland's patent US 9,542,923 describes BOSS's
 * SY pedals. No notes are found: the guitar is split into 49 bands a semitone apart (E2..E6), each band's pitch
 * comes from its zero crossings and its level from its energy, and each drives an oscillator of its own, so the
 * strings of a chord play together. Everything here runs on the audio task through sy_fp_call (the module's own
 * 2 KB stack, FPSCR and d0-d15 saved, round to nearest, flush to zero, default NaN), after the tracker's step.
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
 *     neighbour stops, on the same pitch within 1%, takes the neighbour's phase (a bend moving on: no gap);
 *   - each sounding band's oscillator: a saw at its pitch (a ramp -1..1, a polyBLEP at the wrap), its amplitude
 *     (level - floor) x 1.2, ramped over the block;
 *   - the sum through a resonant state-variable low-pass (Q 2) whose cutoff follows the level, 300 Hz quiet to 5 kHz
 *     at a hard pick (the square root of the level over 0.25, an exponential sweep), a soft clip (1.5x - 0.5x^3,
 *     +-1 beyond), x 16384 for the DRY pair (-6 dBFS at the clip, as the cabinet's). A stop (sy.stopping) fades it out
 *     over 8 blocks.
 *
 * Single precision throughout, no contraction (the pragma below): every fused multiply-add is an explicit fmaf, so
 * tunetest/sy_ref.py computes the same numbers; test_tune_test.py runs both on the same input.
 */
#pragma STDC FP_CONTRACT OFF
#include "tune_test.h"
#include "sy_tables.h"     /* from the builder (sy_ref.py's tables): SY_DEC, SY_BAND, the constants */

#define FMA(a, b, c) __builtin_fmaf((a), (b), (c))

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

static void sy_init(sy_block_t *b) {
    for (u32 k = 0; k < SY_BANDS; k++) {
        b->per[k] = SY_BAND[k].pc;
        b->tl[k] = SY_TL_MIN;
    }
    b->mg = 1.0f;
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

/* A crossing's period into the band's tracker (or, outside 300 cents, the band measures again). */
static void sy_period(sy_block_t *b, u32 k, const sy_band_t *c, float p) {
    if (!(p > c->plo && p < c->phi)) {
        b->nper[k] = 0;
        return;
    }
    u32 np = b->nper[k];
    float base, tr;
    if (np == 0) {
        base = c->pc;
        tr = 0.0f;
    } else {
        base = b->per[k] + b->trend[k];
        tr = b->trend[k];
    }
    float r = p - base;
    b->per[k] = FMA(SY_ALPHA, r, base);
    b->trend[k] = FMA(SY_BETA, r, tr);
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

/* A band's oscillator over a block: a saw (a ramp -1..1) at its pitch, the polyBLEP within a sample of the wrap
 * (|ph| > 1 - inc: its two sides, ph < inc - 1 and ph > 1 - inc), the amplitude ramped to the band's target. */
typedef struct {
    float ph, a, da, inc, rinc, hi;
} sy_osc_t;

static inline __attribute__((always_inline)) void sy_osc_begin(const sy_block_t *b, u32 k, float tg, sy_osc_t *o) {
    float per = b->per[k];
    o->ph = b->ph[k];
    o->a = b->amp[k];
    o->inc = 0.5f / per;
    o->rinc = per + per;
    o->hi = 1.0f - o->inc;
    o->da = (tg - o->a) * (1.0f / 64.0f);
}

static inline __attribute__((always_inline)) float sy_osc_next(sy_osc_t *o) {
    float ph = o->ph + o->inc;
    if (ph >= 1.0f) ph = ph - 2.0f;
    o->ph = ph;
    o->a = o->a + o->da;
    if (__builtin_fabsf(ph) > o->hi) {
        if (ph < 0.0f) {
            float x = (ph + 1.0f) * o->rinc;
            float bl = (x + x) - x * x;
            return ph - (bl - 1.0f);
        }
        float x = (ph - 1.0f) * o->rinc;
        float bl = x * x + (x + x);
        return ph - (bl + 1.0f);
    }
    return ph;
}

static void sy_osc1(sy_block_t *b, u32 k, float tg, float *acc) {
    sy_osc_t o;
    sy_osc_begin(b, k, tg, &o);
    for (u32 n = 0; n < FRAMES; n++) {
        float w = sy_osc_next(&o);
        acc[n] = FMA(o.a, w, acc[n]);
    }
    b->amp[k] = tg;
    b->ph[k] = o.ph;
}

/* Two bands, k1 < k2, each added into acc in that order (as one band after the other would). */
static void sy_osc2(sy_block_t *b, u32 k1, float tg1, u32 k2, float tg2, float *acc) {
    sy_osc_t o1, o2;
    sy_osc_begin(b, k1, tg1, &o1);
    sy_osc_begin(b, k2, tg2, &o2);
    for (u32 n = 0; n < FRAMES; n++) {
        float w1 = sy_osc_next(&o1);
        float w2 = sy_osc_next(&o2);
        float v = FMA(o1.a, w1, acc[n]);
        acc[n] = FMA(o2.a, w2, v);
    }
    b->amp[k1] = tg1;
    b->ph[k1] = o1.ph;
    b->amp[k2] = tg2;
    b->ph[k2] = o2.ph;
}

/* The bands that sound, the phase a band taking over a neighbour's pitch takes, and every sounding (or fading)
 * band's oscillator added into acc. Returns the bands sounding. */
static u32 sy_voices(sy_block_t *b, float *acc) {
    u8 own[SY_BANDS];
    for (u32 k = 0; k < SY_BANDS; k++) {
        float e = b->e[k], p = b->per[k];
        float el = k ? b->e[k - 1] : 0.0f, er = k + 1u < SY_BANDS ? b->e[k + 1] : 0.0f;
        own[k] = (u8)(e >= SY_E_FLOOR && b->nper[k] >= 2u && e >= el && e >= er && p > SY_BAND[k].olo &&
                      p < SY_BAND[k].ohi);
    }
    for (u32 k = 0; k < SY_BANDS; k++) {
        if (!own[k] || b->owned[k]) continue;
        for (u32 side = 0; side < 2u; side++) {
            s32 nb = side ? (s32)k + 1 : (s32)k - 1;
            if (nb < 0 || nb >= (s32)SY_BANDS || !b->owned[nb]) continue;
            if (__builtin_fabsf(b->per[nb] - b->per[k]) < 0.01f * b->per[k]) {
                b->ph[k] = b->ph[nb];
                break;
            }
        }
    }
    u32 on = 0, pend = 0, have = 0;
    float tgp = 0.0f;
    for (u32 k = 0; k < SY_BANDS; k++) {
        float tg = 0.0f;
        if (own[k]) {
            float lev = __builtin_sqrtf(b->e[k] + b->e[k]);
            tg = (lev - SY_FLOOR) * SY_GAIN;
            if (!(tg > 0.0f)) tg = 0.0f;
        }
        if (!(tg > 0.0f || b->amp[k] > 0.0f)) continue;
        on += tg > 0.0f;
        if (!have) {                                    /* two oscillators a pass: acc is read and written once */
            pend = k;
            tgp = tg;
            have = 1;
            continue;
        }
        sy_osc2(b, pend, tgp, k, tg, acc);
        have = 0;
    }
    if (have) sy_osc1(b, pend, tgp, acc);
    for (u32 k = 0; k < SY_BANDS; k++)
        b->owned[k] = own[k];
    return on;
}

/* The output: the low-pass (cutoff from the level), the soft clip, the stop's fade, to s->out. Returns the fade. */
static float sy_output(sy_t *s, sy_block_t *b, const float *acc) {
    float d = b->env * SY_RDYN;
    if (d > 1.0f) d = 1.0f;
    float xo = __builtin_sqrtf(d) * SY_OCT;
    s32 i = (s32)xo;
    float fr = xo - (float)i;
    float p2 = FMA(fr, FMA(fr, FMA(fr, SY_C3, SY_C2), SY_C1), 1.0f);
    float fc = SY_FC_LO * p2 * SY_POW2[i];
    float wv = fc * SY_PI_FS;
    float w2 = wv * wv;
    float g = wv * FMA(w2, FMA(w2, SY_T5, SY_T3), 1.0f);
    float nk1 = -(SY_R2 + g);
    float hh = 1.0f / FMA(g, SY_R2 + g, 1.0f);
    float s1 = b->s1, s2 = b->s2, mg = b->mg;
    u32 stopping = s->stopping;
    for (u32 n = 0; n < FRAMES; n++) {
        float v = FMA(nk1, s1, acc[n]);
        v = v - s2;
        float hp = v * hh;
        float bp = FMA(g, hp, s1);
        s1 = FMA(g, hp, bp);
        float lp = FMA(g, bp, s2);
        s2 = FMA(g, bp, lp);
        float yv = lp;
        if (yv > 1.0f) {
            yv = 1.0f;
        } else if (yv < -1.0f) {
            yv = -1.0f;
        } else {
            yv = yv * FMA(-0.5f, yv * yv, 1.5f);
        }
        if (stopping) {
            mg = mg - SY_FADE;
            if (mg < 0.0f) mg = 0.0f;
        }
        yv = yv * mg;
        s->out[n] = (s32)(yv * SY_OUT_SCALE);
    }
    b->s1 = s1;
    b->s2 = s2;
    b->mg = mg;
    return mg;
}

u32 sy_fp_step(sy_t *s) {
    sy_block_t *b = &sy_block;
    float x12[SY_SUB], dx[SY_SUB], acc[FRAMES];
    if (!b->started) sy_init(b);
    float pk = sy_input(b, x12, dx);
    float ev = b->env * SY_ENV_K;
    b->env = pk > ev ? pk : ev;
    b->crossings += sy_bands(b, dx);
    for (u32 n = 0; n < FRAMES; n++)
        acc[n] = 0.0f;
    s->sounding = sy_voices(b, acc);
    float mg = sy_output(s, b, acc);
    b->blocks++;
    return s->stopping && mg <= 0.0f ? SY_OFF : SY_RUN;
}
