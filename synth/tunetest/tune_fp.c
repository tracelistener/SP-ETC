/* Guitar synth test 3 (note tracker 3), the FPU side: the note the guitar plays, from the input the effects chip
 * hands back (RX pair 0, after the input FX). Everything here runs on the audio task through tune_fp_call: on the
 * module's own 2 KB stack, with FPSCR and d0-d15 saved around it and FPSCR set to round to nearest, flush to zero
 * and default NaN, as cabinet test 2's cab_fp_call.
 *
 * Test 3 plays like the SY-1000's Dynamic Synth (its controls, read from the SY-1000's own parameter list: PLAY
 * FEEL and DYNAMICS, CHROMATIC OFF, the level following the string): the note starts as hard as it was picked
 * (the velocity is the pick's peak), and while it plays (neither ARP nor drum mode: tt.dyn) its Sound Generator
 * voice follows the string, its pitch bends, vibrato and slides as the string does (no new note for a hammer-on),
 * and its level fades as the string fades. The voice's pitch step (+0x20 cycles a sample, +0x38 radians a
 * sample: the stock code sets them only at a note's start) and level (+0x74, velocity x 100, applied every
 * sample) are written every block.
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
 *     when the steady note is gone. A pluck heard while it plays starts the note again (or the new one) only if
 *     the newest 4 blocks' peak is 1.5 x the pluck's reference by then: else it was a stray pluck (the hand, the
 *     pick near a ringing string; synth test 1 heard extra notes) and the note goes on. Without a pluck it moves
 *     (a slide, a hammer-on) once 3 analyses in a row agree on a note within 30 cents of it, never by an octave
 *     or a harmonic's interval (the tracker's own mistakes), and never in drum mode (each move would be a hit).
 *     It lets go once the steady note is gone and the newest 4 blocks' peak is under 0.3 x what it was at the
 *     last voiced analysis (a hand on the string), else after 12 unvoiced analyses (64 ms): a thump or a scrape
 *     spoils the analyses that span it while the string rings on (synth test 1 let go there, then started the
 *     note again).
 *     A note going steady without a pluck while nothing plays starts nothing.
 *     Test 3: the note's velocity is VEL_K x the square root of the highest block peak from its pluck to its steady
 *     note (127 from 0.4 of full scale, low-passed; half the string's range in dB). With ARP on, moves stay test
 *     2's (the arp needs notes); otherwise there are none: the voice follows instead. It follows every voiced
 *     analysis after the steady note: a step under a semitone at once (a bend, vibrato), a bigger one once 3
 *     analyses in a row agree on its note, never an octave or a harmonic's interval (the tracker's own slips), and
 *     it glides there (0.3 of the way a block). Its level is the same velocity of the string's level now (the
 *     highest peak of the newest 13 blocks, 17 ms: longer than the lowest period), 0.5 of the way a block up and
 *     0.15 down.
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
#define REPICK 1.5f                      /* a pluck while the synth plays: the newest 4 blocks' peak over its reference */
#define MOVE_AGREE 3u                    /* the synth moves without a pluck: analyses in a row on the new note, */
#define MOVE_CENTS 30                    /* each within this many cents of it */
#define SYN_DROP 0.3f                    /* the synth lets go once unvoiced and under this part of the last voiced */
#define SYN_RELEASE_LONG 12u             /* level (a hand on the string), else after this many unvoiced (64 ms) */
#define VEL_K 200.8f                     /* velocity = VEL_K x sqrt(peak): 127 at 0.4 (a hard pick, low-passed) */
#define LEVEL_BLOCKS 13u                 /* the string's level: the highest peak of this many newest blocks */
#define LEV_UP 0.5f                      /* the voice's level, a block: this part of the way up to the string's, */
#define LEV_DOWN 0.15f                   /* this part down */
#define BEND_STEP 1.0f                   /* semitones an analysis may move the followed pitch without agreement */
#define BEND_GLIDE 0.3f                  /* the voice's bend, a block: this part of the way to the followed pitch */
#define SG_VOICE0 0x80249800u            /* the Sound Generator's voice (stock) */
#define SG_CLONES 0x8353A310u            /* v9.4's three more, SG_VOICE_SIZE bytes each */
#define SG_VOICE_SIZE 0x1B0u
#define SG_RATE (1.0f / 48000.0f)

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

/* A level as a velocity, 1..127 (not rounded): VEL_K x its square root. */
static float vel_f(float peak) {
    float v = VEL_K * __builtin_sqrtf(peak);
    return v < 1.0f ? 1.0f : v > 127.0f ? 127.0f : v;
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

/* 2^x for |x| < 100: the exponent from x's floor, the rest as e^r, r = frac(x) ln 2, to r^7 (2e-6 relative). */
static float exp2_(float x) {
    s32 n = (s32)x;
    if ((float)n > x)
        n--;
    float r = (x - (float)n) * 0.69314718f;
    float p = 1.0f + r * (1.0f + r * (0.5f + r * (0.16666667f + r * (0.041666667f + r * (0.0083333333f +
              r * (0.0013888889f + r * 0.00019841270f))))));
    union {
        float f;
        u32 u;
    } s;
    s.u = (u32)(n + 127) << 23;
    return p * s.f;
}

/* A double's two words, low first, from a normal float (this FPU has no double instructions); else nothing. */
static void put_double(volatile u32 *d, float x) {
    union {
        float f;
        u32 u;
    } v;
    v.f = x;
    u32 e = (v.u >> 23) & 0xFFu, m = v.u & 0x007FFFFFu;
    if (e == 0u || e == 0xFFu)
        return;
    d[0] = m << 29;
    d[1] = (v.u & 0x80000000u) | ((e + 896u) << 20) | (m >> 3);
}

/* A note starts: the voice follows from here, at the pick's velocity. */
static void syn_start(tt_block_t *b, float midi, s32 note, u32 vel) {
    b->bend_est = midi;
    b->bend_cur = 100.0f * (midi - (float)note);
    b->lev = (float)vel;
}

/* The pitch the voice follows, from a voiced analysis while the note plays: a step under BEND_STEP at once (a bend,
 * vibrato); a bigger one (a hammer-on, a slide's end, the tracker's own slip) once MOVE_AGREE analyses in a row
 * agree on its note, and never an octave or a harmonic's interval. */
static void follow(tt_block_t *b, float midi, s32 note) {
    float d = midi - b->bend_est;
    if (d < BEND_STEP && d > -BEND_STEP) {
        b->bend_est = midi;
    } else if (b->agree >= MOVE_AGREE && !harmonic_jump(note, round_s(b->bend_est))) {
        b->bend_est = midi;
        b->bend_jumps++;
    }
}

/* Every block while a note plays and neither ARP nor drum mode is on: the voice's bend glides toward the followed
 * pitch and its level toward the string's, and the Sound Generator voice holding our note (sounding, not
 * releasing, its MIDI note at +0x194 the one syn_ui sent; the noise types 13 and 14 keep their own step) takes
 * them: its pitch step from its own pitch (+0x5c) and TUNE (+0x60, Hz x 10) as the stock note-on computes it, bent,
 * and its level. */
static void voice_update(tt_t *t, tt_block_t *b, u32 blk) {
    float target = 100.0f * (b->bend_est - (float)b->syn_note);
    b->bend_cur += (target - b->bend_cur) * BEND_GLIDE;
    float lt = vel_f(level(b, blk));
    b->lev += (lt - b->lev) * (lt > b->lev ? LEV_UP : LEV_DOWN);
    s32 sent = t->sent;
    if (sent < 0)
        return;
    for (u32 i = 0; i < 4u; i++) {
        volatile u8 *v = (volatile u8 *)(i ? SG_CLONES + (i - 1u) * SG_VOICE_SIZE : SG_VOICE0);
        if (!v[0] || v[1] || v[0x194] != (u8)sent || (u32)(v[0x70] - 13u) < 2u)
            continue;
        float x = (float)(*(volatile s32 *)(v + 0x5C) - 33) * (1.0f / 12.0f) + b->bend_cur * (1.0f / 1200.0f);
        float dt = (float)*(volatile s32 *)(v + 0x60) * 0.1f * exp2_(x) * SG_RATE;
        put_double((volatile u32 *)(v + 0x20), dt);
        put_double((volatile u32 *)(v + 0x38), 6.28318531f * dt);
        *(volatile s32 *)(v + 0x74) = (s32)(b->lev * 100.0f + 0.5f);
        b->voice_writes++;
    }
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
        b->voiced_level = recent_peak(b, blk);
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
                if (b->syn_note < 0 || recent_peak(b, blk) >= REPICK * b->pluck_ref) {
                    u32 vel = velocity(b->pick_peak);    /* a pluck went steady: the synth plays it, as hard */
                    syn_send(t, b, note, vel);
                    syn_start(b, midi, note, vel);
                } else {
                    b->syn_strays++;                     /* the level never rose: a stray pluck, the note goes on */
                }
            } else if (b->syn_note >= 0 && note != b->syn_note && !t->drum && !t->dyn && b->agree >= MOVE_AGREE &&
                       r->cents <= MOVE_CENTS && r->cents >= -MOVE_CENTS && !harmonic_jump(note, b->syn_note)) {
                u32 vel = velocity(level(b, blk));       /* ARP: the pitch moved while it plays, a new note */
                syn_send(t, b, note, vel);
                syn_start(b, midi, note, vel);
            }
        }
        if (b->syn_note >= 0 && !b->lock_pending)
            follow(b, midi, note);                       /* the voice follows (tt.dyn: voice_update) */
    } else {
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
    if (t->dyn && b->syn_note >= 0)
        voice_update(t, b, blk);
    b->blk = blk + 1u;
    return TT_RUN;
}
