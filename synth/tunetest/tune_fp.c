/* Guitar synth test 4 (note tracker 3), the FPU side: the note the guitar plays, from the input the effects chip
 * hands back (RX pair 0, after the input FX). Everything here runs on the audio task through tune_fp_call: on the
 * module's own 2 KB stack, with FPSCR and d0-d15 saved around it and FPSCR set to round to nearest, flush to zero
 * and default NaN, as cabinet test 2's cab_fp_call.
 *
 * Test 4, after synth test 3 on the unit ("stuck notes. bad tracking. worse than before"): test 3's voice
 * following is gone (a pick the tracker missed became a glide of the note before, so a melody played as one
 * sliding note). Picks at an even strength were missed because the peak test wants twice the ringing level; a
 * pick's click (the energy over 2 kHz jumping twice the most of the 20 ms before) now counts too. Only clean
 * readings count (strings ringing together read murky and made wrong low notes); a murky one counts as nothing
 * heard, so the synth lets go rather than hold or guess. A pluck going steady on another note always plays it;
 * on the note playing, only if it clicked and the level kept half of what it was, or rose 1.2 x (a thump has
 * no click). Moves stay test 2's (not in drum mode). Velocity 50..127 from the pick.
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
 *   - the synth note (tt.syn, played on the Sound Generator by the UI task): on when a pluck goes steady, off
 *     when the steady note is gone. A pluck heard while it plays and going steady on the same note starts it
 *     again only if the level shows a pick (below): else it was a stray pluck (the hand, the pick near a ringing
 *     string; synth test 1 heard extra notes) and the note goes on (test 2 asked this of any note, and missed
 *     new notes picked while the one before rang: synth test 3 on the unit). Without a pluck it moves
 *     (a slide, a hammer-on) once 3 analyses in a row agree on a note within 30 cents of it, never by an octave
 *     or a harmonic's interval (the tracker's own mistakes), and never in drum mode (each move would be a hit).
 *     It lets go once the steady note is gone and the newest 4 blocks' peak is under 0.3 x what it was at the
 *     last voiced analysis (a hand on the string), else after 12 unvoiced analyses (64 ms): a thump or a scrape
 *     spoils the analyses that span it while the string rings on (synth test 1 let go there, then started the
 *     note again).
 *     A note going steady without a pluck while nothing plays starts nothing.
 *     Test 4: a pluck is also a click: the block's energy over 2 kHz (a 2nd-order Butterworth high-pass on the
 *     input) at least 1e-4 and twice the most of blocks 2-16 back (20 ms, over the lowest period: a low string's
 *     wave sends its highs once a period), with the block's peak at least -48 dBFS. A ringing string's highs die
 *     fast, so a pick at its level clicks where the peak does not double. Only analyses whose dip, its bottom
 *     found by a parabola through it and its neighbours, is under 0.15 count toward the steady note (one string,
 *     B1 to E6, reads under 0.08; strings ringing together up to 0.33, their wrong low "common" notes 0.23-0.33); a
 *     murkier one counts as unvoiced. A pluck going steady on the
 *     note playing starts it again only if the highest peak since 4 blocks after the pluck is 0.5 x its reference
 *     (the pick clicked) or 1.2 x (it did not: a thump's level never rises). The velocity is 50 + 77 x the square
 *     root of the pick's peak over 0.4 (127 there), a move's the string's level now (13 blocks' peak).
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
#define REPICK 1.2f                      /* a pluck on the note playing without a click: the level must rise this */
#define CLICK_KEEP 0.5f                  /* with one: keep this part of the reference */
#define CLEAN_APER 0.15f                 /* only analyses this clean count; murkier ones count as unvoiced */
#define MOVE_AGREE 3u                    /* the synth moves without a pluck: analyses in a row on the new note, */
#define MOVE_CENTS 30                    /* each within this many cents of it */
#define SYN_DROP 0.3f                    /* the synth lets go once unvoiced and under this part of the last voiced */
#define SYN_RELEASE_LONG 12u             /* level (a hand on the string), else after this many unvoiced (64 ms) */
#define VEL_FLOOR 50.0f                  /* velocity = VEL_FLOOR + (127 - VEL_FLOOR) x sqrt(peak / VEL_FULL) */
#define VEL_FULL 0.4f                    /* (a hard pick, low-passed) */
#define LEVEL_BLOCKS 13u                 /* the string's level: the highest peak of this many newest blocks */
#define HF_RATIO 2.0f                    /* a click: the block's energy over 2 kHz this many times */
#define HF_MIN 1e-4f                     /* (and at least this) */
#define HF_FROM 2u                       /* the most of blocks HF_FROM..HF_TO back */
#define HF_TO 16u

/* The click's 2nd-order Butterworth high-pass at 2 kHz (48 kHz): b0, b1, b2, a1, a2. */
static const float HP[5] = {0.8308980464935303f, -1.6617960929870605f, 0.8308980464935303f, -1.632993221282959f,
                            0.6905989050865173f};

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

/* The highest peak of the newest 4 blocks (5.3 ms). */
static float recent_peak(const tt_block_t *b, u32 blk) {
    float m = 0.0f;
    for (u32 k = 0; k < 4u; k++) {
        float v = b->peaks[(blk - k) & PEAK_MASK];
        m = v > m ? v : m;
    }
    return m;
}

/* A jump the tracker makes by mistake rather than a player: an octave, an octave and a fifth, two octaves... */
static int harmonic_jump(s32 a, s32 b) {
    s32 d = a > b ? a - b : b - a;
    return d == 12 || d == 19 || d == 24 || d == 28 || d == 31;
}

/* The synth note for the UI task (tune_test.c's syn_ui plays it on the Sound Generator): one word, so the UI reads
 * it whole; seq << 16 | velocity << 8 | (note + 1), 0 none. A note-on bumps seq, so a new pluck of the same note
 * starts it again. */
static void syn_send(tt_t *t, tt_block_t *b, s32 note, u32 vel) {
    u32 seq = t->syn >> 16;
    if (note >= 0)
        seq = (seq + 1u) & 0xFFFFu;
    t->syn = seq << 16 | (note >= 0 ? vel << 8 | ((u32)note + 1u) : 0u);
    b->syn_note = note;
    b->syn_sends++;
}

/* A pick's peak as a velocity, VEL_FLOOR..127 (not rounded): a gentle curve, so a soft pick stays audible. */
static float vel_f(float peak) {
    float v = VEL_FLOOR + (127.0f - VEL_FLOOR) * __builtin_sqrtf(peak * (1.0f / VEL_FULL));
    return v > 127.0f ? 127.0f : v;
}

static u32 velocity(float peak) { return (u32)round_s(vel_f(peak)); }

/* The string's level now: the highest peak of the newest LEVEL_BLOCKS blocks (17 ms, over the lowest period, so a
 * low string's peaks between blocks do not ripple it). */
static float level(const tt_block_t *b, u32 blk) {
    float m = 0.0f;
    for (u32 k = 0; k < LEVEL_BLOCKS; k++) {
        float v = b->peaks[(blk - k) & PEAK_MASK];
        m = v > m ? v : m;
    }
    return m;
}

/* The highest peak since 4 blocks after the last pluck (past a thump's own blocks; by the time a note goes steady
 * a low string's period fits in it), at most the newest TT_PEAKS - 4 blocks. */
static float after_peak(const tt_block_t *b, u32 blk) {
    s32 n = (s32)blk - (b->onset_blk + 4) + 1;
    if (n > (s32)TT_PEAKS - 4)
        n = (s32)TT_PEAKS - 4;
    float m = 0.0f;
    for (s32 k = 0; k < n; k++) {
        float v = b->peaks[(blk - (u32)k) & PEAK_MASK];
        m = v > m ? v : m;
    }
    return m;
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
    float aper = dn[tau], power = 0.0f, clean = aper;
    if (tau > 1u && tau < TT_T6MAX) {                    /* test 4: the dip's own bottom (YIN's step 5): at whole */
        float den = dn[tau - 1u] - 2.0f * dn[tau] + dn[tau + 1u];   /* lags a period between two (E6: 4.55) */
        if (den > 0.0f) {                                /* reads up to 0.2 on one clean string */
            float dd = dn[tau - 1u] - dn[tau + 1u], v = aper - dd * dd / (8.0f * den);
            clean = v < 0.0f ? 0.0f : v > aper ? aper : v;
        }
    }
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
    if (voiced && clean <= CLEAN_APER) {                 /* clean: one string */
        b->unvoiced = 0;
        b->voiced_level = recent_peak(b, blk);
        if (b->first_pending) {
            b->first_pending = 0;
            r->first_ms = ms(blk - (u32)b->onset_blk);
        }
        b->agree = b->agree && b->prev_note == note ? b->agree + 1u : 1u;
        b->prev_note = note;
        u32 same = b->syn_note >= 0 && note == b->syn_note;
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
                float keep = b->pluck_click ? CLICK_KEEP : REPICK;
                if (!same || after_peak(b, blk) >= keep * b->pluck_ref)
                    syn_send(t, b, note, velocity(b->pick_peak));   /* a pluck went steady: the synth plays it */
                else
                    b->syn_strays++;                     /* its own note, no pick's level: a stray pluck */
            } else if (b->syn_note >= 0 && !same && !t->drum && b->agree >= MOVE_AGREE && r->cents <= MOVE_CENTS &&
                       r->cents >= -MOVE_CENTS && !harmonic_jump(note, b->syn_note)) {
                syn_send(t, b, note, velocity(level(b, blk)));      /* the pitch moved while it plays */
            }
        }
    } else {
        if (voiced)
            b->murky++;                                  /* strings ringing together: counts as nothing heard */
        b->agree = 0;
        b->prev_note = -1;
        b->unvoiced++;
        if (b->unvoiced >= RELEASE) {
            r->note = -1;
            if (b->syn_note >= 0) {
                if (b->unvoiced >= SYN_RELEASE_LONG || recent_peak(b, blk) < SYN_DROP * b->voiced_level)
                    syn_send(t, b, -1, 0u);              /* the string stopped: let go */
                else
                    b->syn_holds++;                      /* as loud as before: a thump, a scrape; hold on */
            }
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
    float h0 = b->zh[0], h1 = b->zh[1], e = 0.0f;
    for (u32 f = 0; f < FRAMES; f++) {
        float v = (float)t->in[f] * IN_SCALE;
        float y = HP[0] * v + h0;                        /* the click's high-pass, on the input itself */
        h0 = HP[1] * v - HP[3] * y + h1;
        h1 = HP[2] * v - HP[4] * y;
        e += y * y;
        y = BQ[0][0] * v + z00;
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
    b->zh[0] = h0;
    b->zh[1] = h1;
    u32 blk = b->blk;
    b->peaks[blk & PEAK_MASK] = pk;
    b->hfe[blk & PEAK_MASK] = e;
    if (blk >= P_TO) {
        float ref = 0.0f, href = 0.0f;
        for (u32 k = P_FROM; k <= P_TO; k++) {
            float v = b->peaks[(blk - k) & PEAK_MASK];
            ref = v > ref ? v : ref;
        }
        for (u32 k = HF_FROM; k <= HF_TO; k++) {
            float v = b->hfe[(blk - k) & PEAK_MASK];
            href = v > href ? v : href;
        }
        u32 jump = pk >= P_MIN && pk >= P_RATIO * ref;
        u32 click = e >= HF_MIN && e >= HF_RATIO * href && pk >= P_MIN;
        if ((jump || click) && (s32)blk - b->last_onset >= REFRACTORY) {
            b->clicks += !jump;
            b->pluck_click = click;
            b->pluck_ref = ref;
            b->pick_peak = pk;
            b->last_onset = b->onset_blk = (s32)blk;
            b->first_pending = b->lock_pending = 1;
            b->agree = 0;
            begin(t);
            t->res.onsets++;
            end(t);
        } else if (b->lock_pending && pk > b->pick_peak) {
            b->pick_peak = pk;                           /* the pick's peak, up to its steady note */
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
