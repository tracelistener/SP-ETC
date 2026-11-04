/* Guitar synth test 1 (note tracker 3), the FPU side: the note the guitar plays, from the input the effects chip
 * hands back (RX pair 0, after the input FX). Everything here runs on the audio task through tune_fp_call: on the
 * module's own 2 KB stack, with FPSCR and d0-d15 saved around it and FPSCR set to round to nearest, flush to zero
 * and default NaN, as cabinet test 2's cab_fp_call.
 *
 * One step per RX block (tune_rx in tune_test.c decides when):
 *   - the block's 64 frames (48 kHz, (L + R) / 2 of pair 0) through a 4th-order Butterworth low-pass at 1.6 kHz,
 *     every 4th sample into a 512-sample ring at 12 kHz;
 *   - the block's peak at 12 kHz for the pluck test: at least -48 dBFS and twice the highest of blocks 3-18 back,
 *     24 blocks (32 ms) after the last pluck. Those 16 blocks (21 ms) are longer than the lowest string's period, so
 *     a ringing string's peaks never jump (test 1 compared energies over a block, a ninth of the low E's period: on
 *     the unit a ringing string kept making new plucks, N51 from six notes);
 *   - one analysis every 4 blocks (5.3 ms), its work spread over them: YIN at 6 kHz on every other sample of the
 *     newest 400 (copied at the first block): the difference function for lags 1..100 (6 kHz..60 Hz) over a
 *     100-sample window, 25 lags a block; at the fourth block its cumulative-mean normalisation, the first dip under
 *     0.2 from lag 4 (1.5 kHz) on (else the deepest), refined at 12 kHz around twice that lag (7 lags over a 200-sample
 *     window, a parabola through the deepest of the middle 5 and its neighbours, its vertex within a lag); above
 *     1 kHz, where a period under 6 samples at 6 kHz falls between the lags and YIN's first dip is twice it, half
 *     that lag wins when it is as deep within 20%;
 *   - the result: voiced when the newest 200 samples reach -54 dBFS RMS and the aperiodicity is under 0.35; the
 *     steady note once two voiced analyses in a row agree, gone after 4 unvoiced ones; after a pluck, the time to
 *     the first voiced analysis and to the steady note. An analysis whose samples were taken before the pluck's
 *     block (it finished under 3 blocks after it) only shows its numbers: the string before may still ring;
 *   - the synth note (tt.syn, played on the Sound Generator by the UI task): on when a pluck goes steady, moved
 *     when the steady note changes while it plays (a slide, a hammer-on: no pluck), off when the steady note
 *     is gone. A note that goes steady without a pluck while nothing plays starts nothing (a string ringing on
 *     after another was stopped).
 *
 * tunetest/tune_ref.py is the same in Python; test_tune_test.py runs both on the same input.
 */
#include "tune_test.h"

#define RING_MASK (TT_RING - 1u)
#define PEAK_MASK (TT_PEAKS - 1u)
#define IN_SCALE (1.0f / 32768.0f)
#define LEVEL_MIN 0.0019952622f          /* -54 dBFS */
#define P_MIN 0.0039810717f              /* a pluck's peak: -48 dBFS */
#define P_RATIO 2.0f                     /* over the peaks P_FROM..P_TO blocks back */
#define P_FROM 3u
#define P_TO 18u
#define THRESHOLD 0.2f                   /* YIN's dip */
#define APER_MAX 0.35f                   /* voiced below this */
#define REFRACTORY 24                    /* blocks between plucks */
#define AGREE 2u                         /* analyses in a row for the steady note */
#define RELEASE 4u                       /* unvoiced analyses that clear it */
#define SEMI_PER_LN 17.312340f           /* 12 / ln 2 */

/* The 4th-order Butterworth low-pass at 1.6 kHz (48 kHz) as two biquads: b0, b1, b2, a1, a2. */
static const float BQ[2][5] = {
    {0.009165618568658829f, 0.018331237137317657f, 0.009165618568658829f, -1.641069769859314f, 0.6777322292327881f},
    {0.010120933875441551f, 0.020241867750883102f, 0.010120933875441551f, -1.8121154308319092f, 0.8525991439819336f},
};

/* fn(arg) on the stack that ends at stack_top (8-byte aligned), with FPSCR and d0-d15 saved on it. */
__attribute__((naked, used)) u32 tune_fp_call(u32 (*fn)(tt_t *), tt_t *arg, void *stack_top) {
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

/* sum over j < n of (x[step j] - x[step (j + tau)])^2 */
static float diff(const float *x, u32 step, u32 tau, u32 n) {
    const float *a = x, *c = x + step * tau;
    float s = 0.0f;
    for (u32 j = 0; j < n; j++, a += step, c += step) {
        float d = *a - *c;
        s += d * d;
    }
    return s;
}

/* ln x for a normal x > 0: its exponent, and 2 atanh((m - 1) / (m + 1)) for the mantissa in [0.707, 1.414). */
static float ln(float x) {
    union {
        float f;
        u32 u;
    } v;
    v.f = x;
    s32 e = (s32)((v.u >> 23) & 0xFFu) - 127;
    v.u = (v.u & 0x007FFFFFu) | 0x3F800000u;
    float m = v.f;
    if (m > 1.41421356f) {
        m *= 0.5f;
        e++;
    }
    float y = (m - 1.0f) / (m + 1.0f), y2 = y * y;
    float s = y * (2.0f + y2 * (0.66666667f + y2 * (0.4f + y2 * (0.28571429f + y2 * 0.22222222f))));
    return s + (float)e * 0.69314718f;
}

static s32 round_s(float x) { return (s32)(x < 0.0f ? x - 0.5f : x + 0.5f); }

static u32 ms(u32 blocks) { return (blocks * 4u + 1u) / 3u; }   /* 64 frames at 48 kHz: 4/3 ms */

/* The synth note for the UI task (tune_test.c's syn_ui plays it on the Sound Generator): one word, so the UI reads
 * it whole; seq << 16 | (note + 1), 0 none. A note-on bumps seq, so a new pluck of the same note starts it again. */
static void syn_send(tt_t *t, tt_block_t *b, s32 note) {
    u32 seq = t->syn >> 16;
    if (note >= 0)
        seq = (seq + 1u) & 0xFFFFu;
    t->syn = seq << 16 | (note >= 0 ? (u32)note + 1u : 0u);
    b->syn_note = note;
    b->syn_sends++;
}

static void begin(tt_t *t) {
    t->rseq++;
    __asm__ volatile("" ::: "memory");
}

static void end(tt_t *t) {
    __asm__ volatile("" ::: "memory");
    t->rseq++;
}

/* The analysis' fourth block: the note, if any, and what it means for the readout. */
static void decide(tt_t *t, tt_block_t *b, u32 blk) {
    const float *x = b->span, *d = b->d6;
    float *dn = b->dn6, cum = 0.0f;
    for (u32 k = 1; k <= TT_T6MAX; k++) {
        cum += d[k];
        dn[k] = cum > 0.0f ? d[k] * (float)k / cum : 1.0f;
    }
    u32 tau = 0;
    for (u32 k = TT_T6MIN; k <= TT_T6MAX; k++) {
        if (dn[k] < THRESHOLD) {
            while (k + 1u <= TT_T6MAX && dn[k + 1u] < dn[k])
                k++;
            tau = k;
            break;
        }
    }
    if (!tau) {
        tau = TT_T6MIN;
        for (u32 k = TT_T6MIN + 1u; k <= TT_T6MAX; k++)
            if (dn[k] < dn[tau])
                tau = k;
    }
    float aper = dn[tau], power = 0.0f;
    for (u32 j = 0; j < TT_W12; j++)
        power += x[j] * x[j];
    power *= 1.0f / (float)TT_W12;
    u32 c = 2u * tau, best = 1;
    float dd[7];
    for (u32 i = 0; i < 7u; i++)
        dd[i] = diff(x, 1u, c - 3u + i, TT_W12);
    for (u32 i = 2; i <= 5u; i++)
        if (dd[i] < dd[best])
            best = i;
    float den = dd[best - 1u] - 2.0f * dd[best] + dd[best + 1u];
    float off = den > 0.0f ? 0.5f * (dd[best - 1u] - dd[best + 1u]) / den : 0.0f;
    off = off > 1.0f ? 1.0f : off < -1.0f ? -1.0f : off;     /* within a lag: noise can put the vertex anywhere */
    float k = (float)(c - 3u + best) + off;
    if (k < 24.5f) {                                    /* an octave up? half the lag at 12 kHz, 8..12 */
        u32 h = (u32)(k * 0.5f + 0.5f), hb = 1;
        float dh[3];
        for (u32 i = 0; i < 3u; i++)
            dh[i] = diff(x, 1u, h - 1u + i, TT_W12);
        for (u32 i = 0; i < 3u; i += 2u)
            if (dh[i] < dh[hb])
                hb = i;
        if (dh[hb] <= 1.2f * dd[best]) {
            float o = 0.0f, dn2 = dh[0] - 2.0f * dh[1] + dh[2];
            if (hb == 1u && dn2 > 0.0f) {
                o = 0.5f * (dh[0] - dh[2]) / dn2;
                o = o > 1.0f ? 1.0f : o < -1.0f ? -1.0f : o;
            }
            k = (float)(h - 1u + hb) + o;
        }
    }
    float freq = 12000.0f / k;
    u32 voiced = power >= LEVEL_MIN * LEVEL_MIN && aper < APER_MAX;
    float midi = 69.0f + SEMI_PER_LN * ln(freq * (1.0f / 440.0f));
    s32 note = round_s(midi);
    tt_result *r = &t->res;
    begin(t);
    r->analyses++;
    r->voiced = voiced;
    r->freq10 = (u32)(freq * 10.0f + 0.5f);
    r->cents = round_s((midi - (float)note) * 100.0f);
    r->quality = aper >= 1.0f ? 0u : (u32)((1.0f - aper) * 100.0f + 0.5f);
    if ((s32)blk - b->onset_blk < 3) {
        end(t);
        return;
    }
    if (voiced) {
        b->unvoiced = 0;
        if (b->first_pending) {
            b->first_pending = 0;
            r->first_ms = ms(blk - (u32)b->onset_blk);
        }
        b->agree = b->agree && b->prev_note == note ? b->agree + 1u : 1u;
        b->prev_note = note;
        if (b->agree >= AGREE) {
            r->note = note;
            if (b->lock_pending) {
                u32 v = ms(blk - (u32)b->onset_blk);
                b->lock_pending = 0;
                r->lock_ms = v;
                r->lock_sum += v;
                if (!r->locks || v < r->lock_min)
                    r->lock_min = v;
                if (v > r->lock_max)
                    r->lock_max = v;
                r->locks++;
                syn_send(t, b, note);                    /* a pluck went steady: the synth plays it */
            } else if (b->syn_note >= 0 && note != b->syn_note) {
                syn_send(t, b, note);                    /* the pitch moved while it plays: a slide, a hammer-on */
            }
        }
    } else {
        b->agree = 0;
        b->prev_note = -1;
        b->unvoiced++;
        if (b->unvoiced >= RELEASE) {
            r->note = -1;
            if (b->syn_note >= 0)
                syn_send(t, b, -1);                      /* the string stopped: let go */
        }
    }
    end(t);
}

u32 tune_fp_step(tt_t *t) {
    tt_block_t *b = &tt_block;
    if (!b->started) {
        b->started = 1;
        b->last_onset = -1000;
        b->prev_note = -1;
        b->unvoiced = 99;
        b->syn_note = -1;
    }
    float z00 = b->z[0][0], z01 = b->z[0][1], z10 = b->z[1][0], z11 = b->z[1][1], pk = 0.0f;
    for (u32 f = 0; f < FRAMES; f++) {
        float v = (float)t->in[f] * IN_SCALE;
        float y = BQ[0][0] * v + z00;
        z00 = BQ[0][1] * v - BQ[0][3] * y + z01;
        z01 = BQ[0][2] * v - BQ[0][4] * y;
        v = y;
        y = BQ[1][0] * v + z10;
        z10 = BQ[1][1] * v - BQ[1][3] * y + z11;
        z11 = BQ[1][2] * v - BQ[1][4] * y;
        if ((f & 3u) == 3u) {
            b->ring[b->w & RING_MASK] = y;
            b->w++;
            float a = __builtin_fabsf(y);
            pk = a > pk ? a : pk;
        }
    }
    b->z[0][0] = z00;
    b->z[0][1] = z01;
    b->z[1][0] = z10;
    b->z[1][1] = z11;
    u32 blk = b->blk;
    b->peaks[blk & PEAK_MASK] = pk;
    if (blk >= P_TO) {
        float ref = 0.0f;
        for (u32 k = P_FROM; k <= P_TO; k++) {
            float v = b->peaks[(blk - k) & PEAK_MASK];
            ref = v > ref ? v : ref;
        }
        if (pk >= P_MIN && pk >= P_RATIO * ref && (s32)blk - b->last_onset >= REFRACTORY) {
            b->last_onset = b->onset_blk = (s32)blk;
            b->first_pending = b->lock_pending = 1;
            b->agree = 0;
            begin(t);
            t->res.onsets++;
            end(t);
        }
    }
    u32 phase = blk & 3u;
    if (phase == 0u)
        for (u32 j = 0; j < TT_SPAN; j++)
            b->span[j] = b->ring[(b->w - 1u - j) & RING_MASK];
    u32 lo = 1u + TT_SLICE * phase;
    for (u32 k = lo; k < lo + TT_SLICE; k++)
        b->d6[k] = diff(b->span, 2u, k, TT_W6);
    if (phase == 3u)
        decide(t, b, blk);
    b->blk = blk + 1u;
    return TT_RUN;
}
