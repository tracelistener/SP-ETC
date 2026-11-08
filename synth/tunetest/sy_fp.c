/* SY synth tests 1 to 11, the FPU side: a polyphonic guitar synth in the way Roland's patent US 9,542,923 describes
 * BOSS's SY pedals. The guitar is split into 49 bands a semitone apart (E2..E6), each band's pitch comes from its zero
 * crossings and its level from its energy. Everything here runs on the audio task through sy_fp_call (the tracker's
 * 2 KB stack, used one after the other; FPSCR and d0-d15 saved, round to nearest, flush to zero, default NaN), after
 * the tracker's step.
 *
 * One step per RX block (sy_rx in tune_test.c decides when), from pair 0's (L + R) / 2 (tt.in):
 *   - a 4th-order Butterworth low-pass at 2 kHz, every 4th sample (12 kHz, 16 a block); the block's peak drives a
 *     peak follower falling with a 0.3 s time constant (the playing's level);
 *   - every band: two band-pass stages at its centre (a 4th-order band-pass, Q 8 at E2 rising to 16 at E4 and above,
 *     the stages at 0.6436 x that so the pair has one stage's bandwidth); its energy (a follower over 1.5 of its
 *     periods, at least 2 ms); its positive zero crossings, each counted once the band has gone below -0.25 x its
 *     level, the crossing's place found by a straight line between its two samples. A period within 300 cents of the
 *     centre goes into an alpha-beta tracker (0.2, 0.02), which starts at the centre when the band wakes (test 5: its
 *     first 4 periods counted, not tracked); a band under -60 dBFS is asleep;
 *   - which bands sound (sy_own): a band whose energy tops both neighbours', which has counted two periods and reads
 *     within 80 cents of its centre owns its partial; test 6: one 20 dB under the loudest owned band is silent, one that
 *     stops owning sounds on for SY_HOLD blocks while its energy keeps SY_HOLD_E of its owned one; test 5's FUND: a
 *     whole multiple (2..16, within 3%) of a lower sounding band is silent (a note sounds from its lowest band only),
 *     unless that band is 20 dB under it (test 6); a band's level is its loudest partial's (sqrt(2 x energy)).
 *
 * SY synth test 11: the voices are sy_voice.c's, a synth voice per note (tests 1-10 gave every sounding band
 * oscillators of its own, through one filter for all). Each block the sounding bands' levels (FUND always on, no
 * DYNAMICS shaping: the note manager and the tone's velocity do that now), frequencies and energies go to syv_block
 * with the tone picked (sy_voices.py's VOICES, syv_tables.h) and the screen's settings for it; it writes the DRY
 * pair's block (the soft clip, the fade, the 16-bit stems' scale) to s->out. A new tone fades the output out over 8
 * blocks, resets the voices and fades in again; a stop fades it out.
 *
 * Single precision throughout, no contraction (the pragma below): every fused multiply-add is an explicit fmaf, so
 * tunetest/sy_ref.py computes the same numbers for the analysis; the voices are the same C on both sides (the
 * module's, and sy_voices.py's host build of it).
 */
#pragma STDC FP_CONTRACT OFF
#include "tune_test.h"
#include "sy_tables.h"     /* from the builder (sy_ref.py's tables): SY_DEC, SY_BAND, the constants */
#include "sy_voice.h"
#include "syv_tables.h"    /* from the builder (sy_voices.py): the tones, SYV_VREF */

#define FMA(a, b, c) __builtin_fmaf((a), (b), (c))
_Static_assert(SYV_TONES == SY_NTONES, "sy_t's settings hold every tone");

/* SY test 11: the voices' state, in a slot of its own (.syvbss: a boot zero row) */
syv_state_t syv_state __attribute__((section(".syvbss")));

/* fn(arg) on the stack that ends at stack_top (8-byte aligned), with FPSCR and d0-d15 saved on it. SY test 21: and the
 * caller's r4-r11, in the same FP_SAVED bytes under the top as tune_fp_call (r4-r12 (its sp), lr; FPSCR, a pad;
 * d0-d15), which sy_recover unwinds to after a fault in the step. */
__attribute__((naked, used)) u32 sy_fp_call(u32 (*fn)(sy_t *), sy_t *arg, void *stack_top) {
    __asm__ volatile(
        "mov r12, sp\n"
        "mov sp, r2\n"
        "push {r4-r12, lr}\n"
        "vmrs r3, fpscr\n"
        "push {r3, r4}\n"
        "vpush {d0-d15}\n"
        "bic r5, r3, #0x00c00000\n"            /* round to nearest */
        "orr r5, r5, #0x03000000\n"            /* default NaN, flush to zero */
        "vmsr fpscr, r5\n"
        "mov r5, r0\n"
        "mov r0, r1\n"
        "blx r5\n"
        "vpop {d0-d15}\n"
        "pop {r3, r4}\n"
        "vmsr fpscr, r3\n"
        "pop {r4-r12, lr}\n"
        "mov sp, r12\n"
        "bx lr\n");
}

/* SY test 21: where a fault in an FPU step goes on (sy_fault_c sets the stacked PC here and r0 to the saved block,
 * stack_top - FP_SAVED): the caller's d0-d15, FPSCR, r4-r11 and sp back, and back to it as from the call with SY_SLOW
 * (sy_rx stops the engine on it; sy_fault_c stops the tracker, whose return tune_rx does not read). */
_Static_assert(SY_SLOW == 2 && FP_SAVED == 176u, "sy_recover's constants");
__attribute__((naked, used)) void sy_recover(void) {
    __asm__ volatile(
        "mov sp, r0\n"
        "vpop {d0-d15}\n"
        "pop {r3, r4}\n"
        "vmsr fpscr, r3\n"
        "pop {r4-r12, lr}\n"
        "mov sp, r12\n"
        "movs r0, #2\n"
        "bx lr\n");
}

static void sy_init(sy_block_t *b, const sy_t *s) {
    for (u32 k = 0; k < SY_BANDS; k++) {
        b->per[k] = SY_BAND[k].pc;
        b->tl[k] = SY_TL_MIN;
    }
    b->mg = 1.0f;
    b->tone = s->tone_req < SYV_TONES ? s->tone_req : 0u;
    b->last_pick = -1000;                               /* SY test 16 */
    b->started = 1;
    syv_reset(&syv_state);
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

/* Which bands sound this block, and each one's level (b->amp; 0 silent). Returns how many sound. */
static u32 sy_own(sy_block_t *b) {
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
    for (u32 k = 0; k < SY_BANDS; k++) {            /* SY test 18: a band struck (awake, its energy at SY_RISE x */
        if (b->e[k] >= SY_E_FLOOR && b->e[k] >= SY_RISE * b->es[k])   /* es, a follower over about 32 blocks) in */
            b->struck[k] = (u8)SY_STRUCK;           /*   the last SY_STRUCK blocks: a string picked there, the pick */
        else if (b->struck[k])                      /*   seen or not */
            b->struck[k]--;
        b->es[k] = b->es[k] + (b->e[k] - b->es[k]) * SY_ES_K;
        if (!own[k]) b->fresh[k] = 0;
        b->oage[k] = own[k] ? (u8)(b->oage[k] < 255u ? b->oage[k] + 1u : 255u) : 0u;
    }
    {                                               /* test 5's FUND: a whole multiple of a lower sounding band */
        u8 keep[SY_BANDS];
        for (u32 k = 0; k < SY_BANDS; k++) {
            keep[k] = own[k];
            if (!own[k]) continue;
            s32 cut = -1;                           /* the lowest band it is a multiple of */
            u32 ringing = 1;                        /* SY test 18: every one of those only ringing (owned SY_OLD */
            for (u32 j = 0; j < k; j++) {           /*   blocks or more, not struck lately, not spared itself) */
                if (!own[j]) continue;
                float r = b->per[j] / b->per[k];
                s32 h = (s32)(r + 0.5f);
                if (h >= 2 && h <= SY_HARM_MAX && __builtin_fabsf(r - (float)h) < SY_HARM_TOL * (float)h &&
                    !(b->e[j] < SY_FUND_REL * b->e[k])) {   /* test 6: not a pick's ring under a note */
                    if (cut < 0) cut = (s32)j;
                    if (b->struck[j] || b->fresh[j] || b->oage[j] < SY_OLD) ringing = 0;
                }
            }
            if (cut < 0) continue;
            if (ringing && (b->fresh[k] || b->struck[k])) {   /* SY test 18: struck while those only ring (a note's */
                b->fresh[k] = 1;                         /*   partials come with it): a string of its own, spared */
                continue;                                /*   while it owns (test 17 muted an open B or E picked */
            }                                            /*   over a ringing low E: its 3rd and 4th partials) */
            keep[k] = 0;
            b->fresh[k] = 0;
            if (b->e[k] > lmax[cut]) lmax[cut] = b->e[k];
            b->fund_cut++;
        }
        for (u32 k = 0; k < SY_BANDS; k++)
            own[k] = keep[k];
    }
    u32 on = 0;
    for (u32 k = 0; k < SY_BANDS; k++) {
        float t = 0.0f;
        if (own[k]) {
            float e = b->e[k];
            if (lmax[k] > e) e = lmax[k];               /* test 6: a note at its loudest partial's level */
            float lev = __builtin_sqrtf(e + e);
            t = (lev - SY_FLOOR) * SY_GAIN;
            if (!(t > 0.0f)) t = 0.0f;
        }
        b->amp[k] = t;
        b->owned[k] = own[k];
        on += t > 0.0f;
    }
    return on;
}

u32 sy_fp_step(sy_t *s) {
    sy_block_t *b = &sy_block;
    float x12[SY_SUB], dx[SY_SUB];
    if (!b->started) sy_init(b, s);
    u32 req = s->tone_req;
    if (req >= SYV_TONES) req = b->tone;
    float pk = sy_input(b, x12, dx);
    {                                                   /* SY test 16: a pick (test 10's rule), for GUARD's PICK */
        u32 blk = b->blocks;
        b->peaks[blk & 31u] = pk;
        if (blk >= SY_P_TO) {
            float ref = 0.0f;
            for (u32 kk = SY_P_FROM; kk <= SY_P_TO; kk++) {
                float v = b->peaks[(blk - kk) & 31u];
                ref = v > ref ? v : ref;
            }
            if (pk >= SY_P_MIN && pk >= SY_P_RATIO * ref && (s32)blk - b->last_pick >= (s32)SY_REFRACTORY)
                b->last_pick = (s32)blk;
        }
    }
    float ev = b->env * SY_ENV_K;
    b->env = pk > ev ? pk : ev;
    b->crossings += sy_bands(b, dx);
    s->sounding = sy_own(b);
    u32 t = b->tone;
    syv_knobs_t kn;
    kn.tone = s->knob[t][0];
    kn.p2 = s->knob[t][1];
    kn.level = s->knob[t][2];
    kn.oct = (u8)s->oct[t];
    kn.sus = s->susk[t];
    kn.dyn = s->dynk[t];
    kn.wait = 0;                                        /* SY test 15: the TRACK page (every tone); test 18: its */
    kn.law = s->trk[0] <= 2u ? s->trk[0] : 0u;          /*   first setting is LAW (WAIT is gone: 0) */
    kn.sens = s->trk[1];
    kn.guard = s->trk[2];
    {
        s32 since = (s32)b->blocks - b->last_pick;      /* SY test 16: blocks since the last pick */
        kn.since = (u8)(since > 255 ? 255 : since);
    }
    {   /* SY test 19: a mono tone's notes from the SG tracker (YIN), while it runs (tune_ui runs it for one); its step
         * came first this wake (diag_rx_c: tune_rx, then sy_rx) */
        const tt_block_t *y = &tt_block;
        const u32 run = SYV_TONE[t].mono && tt.state == TT_RUN && tt.req && y->started;
        const u32 an = tt.res.analyses, fresh = run && an != b->yan, code = y->ycode;
        b->yan = an;
        b->mono = SYV_TONE[t].mono;
        kn.ynote = (u8)(fresh && (code & 0x100u) ? (code & 0x7Fu) + 1u : 0u);
        kn.yflag = (u8)((run ? 0x80u : 0u) | (fresh ? 1u : 0u) | (fresh && (code & 0x200u) ? 2u : 0u));
        s32 ys = (s32)y->blk - 1 - y->onset_blk;
        kn.ysince = (u8)(!run ? 255 : ys < 0 ? 0 : ys > 255 ? 255 : ys);
        kn.ysyn = (u8)(run && y->syn_note >= 0 && y->syn_note <= 126 ? y->syn_note + 1 : 0);
        kn.yseq = (u8)(run ? tt.syn >> 16 : 0u);       /* SY test 20: its note-ons (a re-pick's too) */
    }
    float mgt = (s->stopping || req != b->tone) ? 0.0f : 1.0f;
    float mg = syv_block(&syv_state, &SYV_TONE[t], &kn, b->amp, b->per, b->e, b->struck, SYV_VREF, b->mg, mgt,
                         SY_FADE, SY_OUT_SCALE, s->out);
    b->mg = mg;
    if (req != b->tone && mg <= 0.0f && !s->stopping) {     /* faded out: the new tone, from rest */
        b->tone = req;
        syv_reset(&syv_state);
        s->run_steps = 0;                       /* SY test 11: its first steps not held to SLOW, as a start's (code
                                                   run for the first time: DM-404 timed 1.76 M cycles there) */
    }
    b->blocks++;
    return s->stopping && mg <= 0.0f ? SY_OFF : SY_RUN;
}
