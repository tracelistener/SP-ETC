/* SY synth test 11: a synth voice per note. See sy_voice.h. Ported from the offline prototype (session scratchpad
 * sy10/proto: notes.py v3, engine.py) that rendered sy-voice-demos1.
 *
 * Notes from the bands. The SY engine gives each partial one owned band per block. At a pick a partial's first
 * periods read flat, so its ownership can start one band low and move up as its reading settles; a pick also rings
 * short blips in other bands (in the demo's lead phrase 281 band segments for about 25 notes: the notes all lasted
 * 129 ms or more, the blips mostly under 27 ms, fading from the start). A voice follows a partial: when its band
 * stops, a neighbouring band reading the same pitch (within 60 cents of the voice's last reading) takes it over.
 *  - Poly: a band that appears gets a young voice at once, at the band's absolute level (as test 1-10's engine plays
 *    every band, so blips stay quiet and short) and at the band's reading. Once it has sounded PROB blocks holding
 *    half its peak with a settled reading (under STABLE cents over 4 blocks) it is a note: its level then the tone's
 *    envelope at the peak's velocity, its pitch steady unless it moves far (a bend). A young voice that stops fades
 *    in 3 ms; a note releases as the tone says. A note picked again (its level x 1.6 within 8 blocks, after decaying)
 *    attacks again.
 *  - Mono: a band becomes the note once confirmed (CONFIRM blocks at 60% of its peak, its reading settled and within
 *    NEAR cents of its band's centre), waiting while a lower band that could be its fundamental (an octave, an octave
 *    and a fifth, two octaves ... below) is building up; the loudest confirmable band wins, a weaker one does not take
 *    a note younger than 60 ms, and a correction to the neighbouring band within 20 ms retunes without an attack.
 *
 * Voices. Oscillators at the note's frequency x their ratio (x OCTAVE): band-limited saw and pulse (polyBLEP), a
 * triangle, a sine, a seven-saw supersaw (the published JP-8000 detune curve and mix law), two-modulator FM (decaying
 * indices), or one of the Sound Generator's 32 waves (types 15-31 its own wave_eval, in the firmware at 0x83f80401;
 * the 15 stock ones as traced in the firmware, naive as the SG plays them); hard sync of oscillator 2, ring
 * modulation, a sub an octave down, noise. Filters: a 12 dB state-variable (LP/BP/HP), a 24 or 18 dB ladder with a
 * soft input, or the Sound Generator's ENV preset (its envelopes and SVF, as env.c). Envelopes per sample (attack
 * towards 1.3, decay and release exponential), an LFO (vibrato, cutoff, pulse width, tremolo, a vector crossfade of
 * oscillators 2 and 3) fading in after a delay, glide. The mix: a DC blocker, the tone's gain, the output stage. No
 * effects (the user: the SP's bus effects, chorus and the rest, on the synth's bus).
 *
 * The screen's settings (knobs()), per block: TONE moves the cutoff +-2 octaves (the SG presets' filter the same;
 * without one, DUTY), or FM's brightness; LEVEL the gain 0..2x; CTRL 1 (P2) the tone's own setting (the SG tones: the
 * ENV preset itself); OCTAVE x 2^-2..2^2; SUSTAIN the decay and release times x 2^((s - 50) / 25); DYNAMICS how far the
 * level follows the pick. */
#pragma STDC FP_CONTRACT OFF
#include "sy_voice.h"
#include "syv_tables.h"         /* from the builder (sy_voices.py): SYV_CENTRE[], the ENV presets, the tones */

typedef syv_u32 u32;
typedef syv_s32 s32;
typedef syv_u8 u8;

#ifdef SYV_HOST
float wave_eval(u32 type, float p, float d, float dt, float r);
#define WAVE_EVAL wave_eval
#define SYV_TEXT
#define SYV_NOTES
#define SYV_DATA
#else
#define WAVE_EVAL ((float (*)(u32, float, float, float, float))0x83F80401u)
#define SYV_TEXT __attribute__((section(".syvtext"), noinline))
#define SYV_NOTES __attribute__((section(".syvnotes"), noinline))   /* each in its own slot: not inlined */
#define SYV_DATA __attribute__((section(".syvdata"), noinline))
#endif

#define FS 48000.0f
#define PROB 24
#define PROB_HOLD 0.5f
#define CONFIRM 10
#define CONFIRM_MAX 40
#define HOLD_LEVEL 0.6f
#define STABLE 15.0f
#define NEAR 45.0f
#define REPICK 1.6f
/* SY test 15, GUARD (test 13's): */
#define G_HAND 17.0f                /* a band beginning next to a note's, reading its pitch within this: takes it on */
#define G_RESUME 20                 /* a note's band back within this many blocks of its end, */
#define G_BACK 1.6f                 /*   no louder than this x its last level: it goes on */
#define G_STEAL 1.5f                /* a new note takes a note in full's voice only at this x its level */
#define G_FIX 20                    /* mono: a band taking over a note this young moves it (no second attack) */
#define PKH_DK 0.995f               /* SY test 16: SENS's held peak falls this much a block (-20 dB in 0.6 s) */
#define P_WIN 45                    /* SY test 16, PICK: a new note within this many blocks of a pick (60 ms: a low
                                       string sounds 20-30 ms after its pick); mono within P_WIN_M + CONFIRM */
#define P_WIN_M 45
#define G_RIDE 20                   /* SY test 16, GUARD on a mono tone: a note rides its band's gaps this long, */
#define G_END 0.1f                  /*   unless the band's energy falls under this x its last (the string stopped) */

static const s32 SUBS[5] = {12, 19, 24, 28, 31};
static const float OCT_MUL[5] = {0.25f, 0.5f, 1.0f, 2.0f, 4.0f};

static inline float absf(float x) { return x < 0.0f ? -x : x; }
static inline float minf(float a, float b) { return a < b ? a : b; }
static inline float maxf(float a, float b) { return a > b ? a : b; }
static inline float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

/* floor for |x| < 2^31 */
static inline float floorf_(float x) {
    float t = (float)(s32)x;
    return t > x ? t - 1.0f : t;
}

/* 2^x: round to the nearest integer, a degree-6 polynomial on [-0.5, 0.5] (relative error under 1e-7) */
SYV_DATA static float syv_exp2(float x) {
    if (x < -125.0f) return 0.0f;
    if (x > 125.0f) x = 125.0f;
    float n = floorf_(x + 0.5f);
    float f = x - n;
    float p = 1.0f + f * (0.693147181f + f * (0.240226507f + f * (0.0555041087f + f * (0.00961812911f +
                     f * (0.00133335581f + f * 0.000154035304f)))));
    union {
        u32 u;
        float v;
    } q;
    q.u = (u32)((s32)n + 127) << 23;
    return p * q.v;
}

/* log2(x), x > 0: the exponent, and log2 of the mantissa m in [1, 2) through t = (m - 1) / (m + 1) (error ~2e-5) */
SYV_DATA static float syv_log2(float x) {
    union {
        float v;
        u32 u;
    } q;
    q.v = x;
    s32 e = (s32)((q.u >> 23) & 0xFFu) - 127;
    q.u = (q.u & 0x007FFFFFu) | 0x3F800000u;
    float m = q.v;
    float t = (m - 1.0f) / (m + 1.0f);
    float t2 = t * t;
    float l = t * (2.88539008f + t2 * (0.961796694f + t2 * (0.577078016f + t2 * 0.412198583f)));
    return (float)e + l;
}

/* a^inv for a retention factor 0 < a < 1: near 1 through ln(1 - d) and e^y as series (exact enough for the long
 * times SUSTAIN scales), else through log2 */
SYV_NOTES static float pow_k(float a, float inv) {
    float d = 1.0f - a;
    if (d <= 0.0f) return 1.0f;
    if (d < 0.05f) {
        float l = -(d + d * d * (0.5f + d * (1.0f / 3.0f)));
        float y = l * inv;
        return 1.0f + y * (1.0f + y * (0.5f + y * (1.0f / 6.0f)));
    }
    return syv_exp2(syv_log2(a) * inv);
}

/* sin(2 pi p) for any p (odd polynomial on [-pi/2, pi/2]) */
static inline __attribute__((always_inline)) float syv_sin(float p) {
    p = p - floorf_(p);
    if (p >= 0.5f) p = p - 1.0f;
    if (p > 0.25f) p = 0.5f - p;
    else if (p < -0.25f) p = -0.5f - p;
    float x = p * 6.28318531f;
    float x2 = x * x;
    return x * (1.0f + x2 * (-0.166666667f + x2 * (0.00833333310f + x2 * (-0.000198408738f + x2 * 2.75255616e-6f))));
}

/* a tanh-like saturation without a division: 1.5z - 0.5z^3 of z = x / 1.5 (x - x^3 / 6.75), +-1 from |x| = 1.5 */
static inline __attribute__((always_inline)) float sat(float x) {
    float z = x * (2.0f / 3.0f);
    if (z >= 1.0f) return 1.0f;
    if (z <= -1.0f) return -1.0f;
    return z * (1.5f - 0.5f * (z * z));
}

/* tan(w), 0 <= w <= 0.45 pi (Pade [5/4], as env.c) */
static inline float syv_tan(float w) {
    float w2 = w * w;
    return w * (945.0f - 105.0f * w2 + w2 * w2) / (945.0f - 420.0f * w2 + 15.0f * w2 * w2);
}

static inline __attribute__((always_inline)) float blep(float t, float dt, float idt) {
    if (t < dt) {
        t = t * idt;
        return t + t - t * t - 1.0f;
    }
    if (t > 1.0f - dt) {
        t = (t - 1.0f) * idt;
        return t * t + t + t + 1.0f;
    }
    return 0.0f;
}

/* The Sound Generator's stock types 0-14 (naive, as the firmware's oscillator), its own 15-31 through wave_eval. */
SYV_DATA static float sg_wave(u32 type, float p, float d, float dt, float r, float wn) {
    if (type >= 15u) return WAVE_EVAL(type, p, d, dt, r);
    if (p < 0.0f) p = 0.0f;
    if (p > 0.99999994f) p = 0.99999994f;
    float y;
    if (type <= 5u) {
        y = syv_sin(type <= 2u ? p : p + 0.25f);
        if (type == 1u || type == 4u) return floorf_(y * 128.0f) * (1.0f / 128.0f);
        if (type == 2u || type == 5u) return floorf_(y * 8.0f) * 0.125f;
        return y;
    }
    if (type == 6u) return 2.0f * p - 1.0f;
    if (type == 7u) return p;
    if (type == 8u) {
        if (p >= 0.75f) return 2.0f * p - 1.0f;
        float u = p + 0.25f;
        float v = u < 0.5f ? u : 1.0f - u;
        return 4.0f * v - 1.0f;
    }
    if (type == 9u || type == 10u) {
        float u = p + 0.25f;
        if (u > 1.0f) u = u - 1.0f;
        float v = u < 0.5f ? u : 1.0f - u;
        return 4.0f * v - 1.0f;
    }
    if (type == 11u) return p <= d ? 1.0f : -1.0f;
    if (type == 12u) return p <= d ? 1.0f : 0.0f;
    return p <= maxf(d, 0.02f) ? wn : 0.0f;
}

static const float UNI_DET[7] = {-0.11002313f, -0.06288439f, -0.01952356f, 0.0f, 0.01991221f, 0.06216538f,
                                 0.10745242f};

SYV_DATA void syv_reset(syv_state_t *s) {
    u8 *b = (u8 *)s;
    for (u32 i = 0; i < sizeof(*s); i++)
        b[i] = 0;
    for (u32 v = 0; v < SYV_NV; v++) {
        s->n[v].band = -1;
        s->n[v].start = -1000000;
        s->n[v].rel = -1000000;
        s->n[v].rp = -1000000;
        s->v[v].ns = 12345u + 7919u * v;
        for (u32 u = 0; u < 7u; u++) {
            float x = (float)u * 0.1371f + (float)v * 0.31f;
            s->v[v].uph[u] = x - floorf_(x);
        }
    }
    for (u32 k = 0; k < SYV_BANDS; k++)
        s->pend_b0[k] = -1;
    s->started = 1;
}

/* ---- the screen's settings ---- */

SYV_DATA static void knobs(syv_state_t *s, const syv_patch_t *t, const syv_knobs_t *k) {
    syv_patch_t *p = &s->eff;
    const u32 *src = (const u32 *)t;
    u32 *dst = (u32 *)p;
    for (u32 i = 0; i < sizeof(*p) / 4u; i++)
        dst[i] = src[i];
    u32 preset = t->preset;
    float ct = (float)k->tone * (1.0f / 64.0f), c2 = (float)k->p2 * (1.0f / 64.0f);
    if (t->p2kind == SYV_P_ENVSEL && k->p2) {           /* the ENV preset itself: ten zones over the knob */
        s32 z = ((64 + (s32)k->p2) * 10) >> 7;
        preset = (u32)(z < 0 ? 0 : z > 9 ? 9 : z);
    }
    if (preset >= SYV_PRESETS) preset = 0;
    p->preset = (u8)preset;
    for (u32 i = 0; i < 14u; i++)
        s->pre[i] = SYV_PRESET[preset][i];
    if (k->tone) {
        if (p->flt >= 1u && p->flt <= 5u) {
            p->cut = p->cut * syv_exp2(2.0f * ct);
        } else if (p->flt == 6u) {
            if (s->pre[13] > 0.0f) p->p2base = 2.0f * ct;
            else p->duty[0] = clampf(p->duty[0] + 0.5f * ct, 0.0f, 1.0f);
        } else {
            float g = syv_exp2(ct);
            p->fm_index = p->fm_index * g;
            p->fm2_index = p->fm2_index * g;
        }
    }
    p->gain = p->gain * (float)(64 + (s32)k->level) * (1.0f / 64.0f);
    if (k->p2) {
        switch (t->p2kind) {
        case SYV_P_RESO: p->reso = clampf(p->reso + 0.5f * c2, 0.0f, 0.95f); break;
        case SYV_P_ENV:
            p->fenv = p->fenv * (1.0f + c2);
            p->penv = p->penv * (1.0f + c2);
            break;
        case SYV_P_ATTACK: p->aa = 1.0f - pow_k(1.0f - p->aa, syv_exp2(-2.0f * c2)); break;
        case SYV_P_DETUNE: p->spread = p->spread * syv_exp2(1.5f * c2); break;
        case SYV_P_GLIDE: {
            float g = p->glide > 0.0f ? p->glide : c2 > 0.0f ? 0.998803f : 0.0f;   /* none: 40 ms to start from */
            p->glide = g > 0.0f ? pow_k(g, syv_exp2(-2.0f * c2)) : 0.0f;
            break;
        }
        case SYV_P_DUTY:
            p->duty[0] = clampf(p->duty[0] + 0.5f * c2, 0.0f, 1.0f);
            p->pw[0] = clampf(p->pw[0] + 0.45f * c2, 0.05f, 0.95f);
            break;
        case SYV_P_DRIVE: p->drive = maxf(1.0f, p->drive * syv_exp2(1.5f * c2)); break;
        case SYV_P_RATE: p->lfo_inc = p->lfo_inc * syv_exp2(2.0f * c2); break;
        case SYV_P_MIX: p->mix = clampf(p->mix + 0.5f * c2, 0.0f, 1.0f); break;
        case SYV_P_FM:
            p->fm_index = p->fm_index * (1.0f + c2);
            p->fm2_index = p->fm2_index * (1.0f + c2);
            break;
        default: break;
        }
    }
    if (k->oct >= 1u && k->oct <= 5u) p->octm = p->octm * OCT_MUL[k->oct - 1u];
    if (k->sus >= 1u && k->sus <= 101u) {               /* the decay and release times x 0.25..4 */
        float inv = syv_exp2(-((float)(k->sus - 1u) - 50.0f) * 0.04f);
        p->ad = pow_k(p->ad, inv);
        p->ar = pow_k(p->ar, inv);
        s->pre[1] = pow_k(s->pre[1], inv);
        s->pre[3] = pow_k(s->pre[3], inv);
    }
    if (k->dyn >= 1u && k->dyn <= 101u) p->avel = (float)(k->dyn - 1u) * 0.01f;
}

/* ---- notes ---- */

/* a period (12 kHz samples) in cents from A4: 1200 log2(12000 / 440) - 1200 log2(period) */
static inline float cents_of_period(float per) { return 5723.26449f - 1200.0f * syv_log2(maxf(per, 1.0f)); }

static inline void steady(syv_note_t *n, float cm) {
    float d = cm - n->c;
    float a = absf(d);
    n->c = n->c + d * (a > 25.0f ? 0.5f : a > 8.0f ? 0.15f : 0.02f);
}

SYV_NOTES static u32 repick(syv_note_t *n, float lv, s32 blk) {
    u32 w = n->nh % 9u;                                /* a ring of the last nine levels, this one included */
    n->hist[w] = lv;
    if (n->nh < 255u) n->nh++;
    float lo = n->hist[(w + 1u) % 9u];                 /* the level 8 blocks ago */
    if (blk - n->start < 40 || blk - n->rp < 30 || n->nh < 9u) return 0;
    if (lo > 0.0f && lo < 0.8f * n->peak && lv > REPICK * lo && lv > 0.25f * n->peak) {
        n->rp = blk;
        n->nh = 0;
        return 1;
    }
    return 0;
}

/* n's band stopped: a neighbour reading the same pitch, not another voice's, takes it over (1 if it moved) */
SYV_NOTES static u32 follow(syv_state_t *s, syv_note_t *n, const u8 *on, const float *rc, u32 nv,
                            unsigned long long *taken) {
    s32 k = n->band;
    for (s32 d = -1; d <= 1; d += 2) {
        s32 nk = k + d;
        if (nk < 0 || nk >= SYV_BANDS || !on[nk] || ((*taken >> nk) & 1ull)) continue;
        if (absf(rc[nk] - n->r) >= 60.0f) continue;
        u32 used = 0;
        for (u32 w = 0; w < nv; w++)
            if (&s->n[w] != n && s->n[w].gate && s->n[w].band == nk) used = 1;
        if (used) continue;
        n->band = (signed char)nk;
        *taken |= 1ull << nk;
        return 1;
    }
    return 0;
}

static inline float velocity(float peak, float vref) {
    if (peak <= 0.0f) return 0.05f;
    float v = syv_exp2(0.7f * syv_log2(peak / vref));
    return v < 0.05f ? 0.05f : v > 1.0f ? 1.0f : v;
}

typedef syv_ctl_t ctl_t;

/* SY test 15, GUARD: a young note's band went quiet as a band a whole multiple below began to sound (the analysis's
 * FUND: the pick's overtone came first): the note moves down to it, no new attack (1 if it moved) */
SYV_NOTES static u32 g_down(syv_state_t *s, syv_note_t *n, const u8 *on, u32 nv, unsigned long long *taken) {
    for (u32 q = 0; q < 5u; q++) {
        s32 j = n->band - SUBS[q];
        if (j < 0) break;
        if (!on[j] || ((*taken >> j) & 1ull)) continue;
        u32 used = 0;
        for (u32 w = 0; w < nv; w++)
            if (&s->n[w] != n && s->n[w].gate && s->n[w].band == j) used = 1;
        if (used) continue;
        n->band = (signed char)j;
        *taken |= 1ull << j;
        return 1;
    }
    return 0;
}

static inline float g_level(const syv_note_t *n, const float *tg) {
    return n->gate && tg[n->band] > 0.0f ? tg[n->band] : n->last;
}

/* Test 11's note manager. SY test 15: WAIT (a band is a new note once it has sounded wait + 1 blocks in a row; 0: the
 * block it begins, as test 11), SENS (a new note needs sens % of the loudest band) and GUARD (a band beginning next to
 * a note's band reading its pitch takes the note on; a young note moves down to its fundamental; a note's band back
 * soon, no louder, goes on; none with a new attack; a new note takes the quietest young note's voice only if quieter,
 * a note in full's only at G_STEAL x its level). */
SYV_NOTES static void notes_poly(syv_state_t *s, const syv_patch_t *p, const float *tg, const float *rc, float vref,
                                 ctl_t *c, u32 nv, const syv_knobs_t *kn) {
    const s32 blk = s->blk;
    const float *rc4 = s->rc_prev[blk & 3];            /* the readings four blocks ago */
    const u32 wait = kn->wait <= 12u ? kn->wait : 12u, guard = kn->guard != 0u;
    const u32 pickg = 0u;                              /* test 16: PICK is mono's (a strum's later strings make no pick
                                                          of their own); here it is ON */
    const float sens = (float)(kn->sens <= 50u ? kn->sens : 50u) * 0.01f;
    u8 on[SYV_BANDS];
    for (u32 k = 0; k < SYV_BANDS; k++)
        on[k] = tg[k] > 0.0f;
    const float lmax = s->pkh;                         /* test 16: the held peak (syv_block), not only the band now */
    unsigned long long taken = 0;
    for (u32 v = 0; v < nv; v++) {
        syv_note_t *n = &s->n[v];
        n->trig = 0;
        if (n->band < 0 || !n->gate) continue;
        if (on[n->band]) {
            n->off = 0;
            taken |= 1ull << n->band;
            continue;
        }
        if (follow(s, n, on, rc, nv, &taken) || (guard && n->young && g_down(s, n, on, nv, &taken))) {
            n->off = 0;
            continue;
        }
        n->off++;
        if (n->young || n->off > 3u) {
            n->gate = 0;
            n->rel = blk;
            n->fast = n->young;
        }
    }
    for (u32 k = 0; k < SYV_BANDS; k++) {            /* test 15: the run's (wait + 1)th block; 0: its first */
        if (!on[k] || s->run[k] != wait + 1u || ((taken >> k) & 1ull)) continue;
        if (sens > 0.0f && tg[k] < sens * lmax) continue;
        s32 best = -1;
        if (guard) {
            for (u32 v = 0; v < nv && best < 0; v++) {  /* a note's partial moving on to this band */
                syv_note_t *n = &s->n[v];
                if (n->band >= 0 && n->gate && (n->band - (s32)k == 1 || (s32)k - n->band == 1) &&
                    absf(rc[k] - n->r) < G_HAND)
                    best = (s32)v;
            }
            if (best >= 0) {
                s->n[best].band = (signed char)k;
                s->n[best].off = 0;
                taken |= 1ull << k;
                continue;
            }
            for (u32 v = 0; v < nv && best < 0; v++) {  /* a note's band back soon after it ended, no louder */
                const syv_note_t *n = &s->n[v];
                s32 d = n->band - (s32)k;
                if (n->band < 0 || n->gate || blk - n->rel > G_RESUME || d < -1 || d > 1 || tg[k] > G_BACK * n->last)
                    continue;
                if (d != 0 && absf(rc[k] - n->r) >= G_HAND) continue;
                best = (s32)v;
            }
            if (best >= 0) {
                syv_note_t *n = &s->n[best];
                n->band = (signed char)k;
                n->gate = 1;
                n->off = 0;
                n->fast = 0;
                taken |= 1ull << k;
                continue;
            }
            if (pickg) continue;                        /* test 16, PICK: no pick lately, no new note (a move or a
                                                           resume above still goes on) */
        }
        for (u32 v = 0; v < nv; v++)                    /* a free voice, released longest ago */
            if (!s->n[v].gate && (best < 0 || s->n[v].rel < s->n[best].rel)) best = (s32)v;
        if (best < 0 && !guard)                         /* else the quietest young voice (a blip) */
            for (u32 v = 0; v < nv; v++)
                if (s->n[v].young && (best < 0 || s->n[v].hist[8] < s->n[best].hist[8])) best = (s32)v;
        if (best < 0 && !guard)
            for (u32 v = 0; v < nv; v++)                /* else the oldest note */
                if (best < 0 || s->n[v].start < s->n[best].start) best = (s32)v;
        if (best < 0) {                                 /* GUARD: the quietest note's, young or not, only if G_STEAL x
                                                           quieter, else none (test 16: test 15 also gave a quieter
                                                           young note's voice away: a strum's strings, young together,
                                                           lost theirs to blips, with a click each) */
            for (u32 v = 0; v < nv; v++)
                if (best < 0 || g_level(&s->n[v], tg) < g_level(&s->n[best], tg)) best = (s32)v;
            if (G_STEAL * g_level(&s->n[best], tg) >= tg[k]) continue;
        }
        syv_note_t *n = &s->n[best];
        n->band = (signed char)k;
        n->gate = 1;
        n->off = 0;
        n->start = blk;
        n->peak = tg[k];
        n->c = rc[k];
        n->r = rc[k];
        n->last = tg[k];
        n->young = 1;
        n->fast = 0;
        n->lev = 1.0f;
        n->nh = 0;
        n->trig = 1;
        taken |= 1ull << k;
    }
    for (u32 v = 0; v < SYV_NV; v++) {
        syv_note_t *n = &s->n[v];
        if (v >= nv) {                                  /* past the tone's cap: silent */
            c->trig[v] = 0;
            c->gate[v] = 0.0f;
            c->conf[v] = 1.0f;
            c->fast[v] = 1;
            c->freq[v] = 0.0f;
            c->vel[v] = 0.05f;
            c->lev[v] = 1.0f;
            continue;
        }
        c->trig[v] = n->trig;
        c->gate[v] = 0.0f;
        c->conf[v] = 1.0f;
        c->fast[v] = 0;
        c->freq[v] = 0.0f;
        c->vel[v] = 0.05f;
        c->lev[v] = 1.0f;
        if (n->band < 0) continue;
        s32 k = n->band;
        u32 live = n->gate && on[k];
        if (live) {
            n->r = rc[k];
            n->last = tg[k];
            if (n->young) {
                n->c = rc[k];
                n->peak = maxf(n->peak, tg[k]);
                if (blk - n->start >= PROB && tg[k] >= PROB_HOLD * n->peak && blk >= 4 &&
                    absf(rc[k] - rc4[k]) < STABLE)
                    n->young = 0;
            } else {
                if (repick(n, tg[k], blk)) {
                    c->trig[v] = 1;
                    n->start = blk;
                    n->peak = tg[k];
                }
                steady(n, rc[k]);
                if (blk - n->start < 12) n->peak = maxf(n->peak, tg[k]);
            }
            n->lev = minf(1.0f, tg[k] / maxf(n->peak, 1e-9f));
        }
        c->gate[v] = n->gate ? 1.0f : 0.0f;
        c->freq[v] = 440.0f * syv_exp2(n->c * (1.0f / 1200.0f));
        c->vel[v] = velocity(n->peak, vref);
        c->lev[v] = n->lev;
        float vs = (1.0f - p->avel) + p->avel * c->vel[v];
        if (n->young && live) {
            float a = minf(1.0f, syv_exp2(0.7f * syv_log2(maxf(tg[k], 1e-12f) / vref)));
            n->hist[8] = minf(1.0f, a / maxf(vs, 0.05f));    /* a young voice keeps its last confidence here */
            c->conf[v] = n->hist[8];
        } else if (n->young) {
            c->conf[v] = n->hist[8];
        }
        c->fast[v] = n->fast;
    }
}

SYV_NOTES static void notes_mono(syv_state_t *s, const syv_patch_t *p, const float *tg, const float *rc,
                                 const float *e, float vref, ctl_t *c, const syv_knobs_t *kn) {
    const s32 blk = s->blk;
    const s32 wait = (s32)(kn->wait <= 12u ? kn->wait : 12u);   /* SY test 15: WAIT on top of CONFIRM, SENS, GUARD */
    const u32 guard = kn->guard != 0u;
    const u32 pick = kn->guard >= 2u;                  /* test 16: PICK: a band began within P_WIN_M of a pick */
    const float sens = (float)(kn->sens <= 50u ? kn->sens : 50u) * 0.01f;
    const float lmax = s->pkh;                         /* test 16: the held peak (syv_block) */
    const float *rc4 = s->rc_prev[blk & 3];
    const float *rc1 = s->rc_prev[(blk + 3) & 3];      /* the last block's readings */
    const float *e4 = s->e_prev[blk & 3];
    syv_note_t *n = &s->n[0];
    u8 on[SYV_BANDS];
    for (u32 k = 0; k < SYV_BANDS; k++)
        on[k] = tg[k] > 0.0f;
    n->trig = 0;
    if (n->band >= 0 && n->gate && !on[n->band]) {
        unsigned long long t = 0;
        if (follow(s, n, on, rc, 1, &t)) {
            s->pend_b0[n->band] = -1;
        } else {
            n->off++;
            u32 ride = guard && n->off <= G_RIDE && !(e[n->band] < G_END * n->elast);   /* test 16: GUARD's ride */
            if (n->off > 3u && !ride) {
                n->gate = 0;
                n->rel = blk;
            }
        }
    }
    for (u32 j = 0; j < SYV_BANDS; j++)
        if (on[j] && !s->prev[j] && ((s32)j != n->band || !n->gate)) {
            s->pend_b0[j] = blk;
            s->pend_pk[j] = tg[j];
        }
    u8 gone[SYV_BANDS];
    for (u32 j = 0; j < SYV_BANDS; j++)
        gone[j] = s->pend_b0[j] >= 0 && !on[j];
    for (u32 j = 0; j < SYV_BANDS; j++) {              /* a pending band moving on with its partial */
        if (!gone[j]) continue;
        s32 b0 = s->pend_b0[j];
        float pk = s->pend_pk[j];
        s->pend_b0[j] = -1;
        for (s32 d = -1; d <= 1; d += 2) {
            s32 nj = (s32)j + d;
            if (nj < 0 || nj >= SYV_BANDS || !on[nj] || s->pend_b0[nj] >= 0 || nj == n->band) continue;
            if (absf(rc[nj] - rc1[j]) >= 60.0f) continue;
            s->pend_b0[nj] = b0;
            s->pend_pk[nj] = maxf(pk, tg[nj]);
            break;
        }
    }
    s32 best = -1;
    for (u32 j = 0; j < SYV_BANDS; j++) {
        if (s->pend_b0[j] < 0) continue;
        if (tg[j] > s->pend_pk[j]) s->pend_pk[j] = tg[j];
        s32 age = blk - s->pend_b0[j];
        if (pick && (s32)kn->since > P_WIN_M + age) continue;   /* test 16, PICK: it began too long after a pick */
        u32 ok = age >= CONFIRM + wait && tg[j] >= HOLD_LEVEL * s->pend_pk[j] && blk >= 4 &&
                 absf(rc[j] - rc4[j]) < STABLE && absf(rc[j] - SYV_CENTRE[j]) < NEAR && tg[j] >= sens * lmax;
        if (ok && age < CONFIRM_MAX) {                 /* a fundamental still building up below: wait for it */
            for (u32 q = 0; q < 5u; q++) {
                s32 i = (s32)j - SUBS[q];
                if (i >= 0 && e[i] > 0.02f * e[j] && e[i] > 1.15f * e4[i]) {
                    ok = 0;
                    break;
                }
            }
        }
        if ((ok || (age >= CONFIRM_MAX + wait && tg[j] >= sens * lmax)) && (best < 0 || tg[j] > tg[best]))
            best = (s32)j;
    }
    if (best >= 0 && n->gate && n->band >= 0 && on[n->band] && blk - n->start < 45 && tg[best] < 0.8f * tg[n->band])
        best = -1;                                     /* a weaker band while the note is young: not a note */
    if (best >= 0 && guard && n->gate && n->band >= 0 && tg[best] < (on[n->band] ? tg[n->band] : n->last))
        best = -1;                                     /* test 16, GUARD: weaker than the note at any age */
    if (best >= 0) {
        u32 legato = n->gate || blk - n->rel < 4;
        s32 dist = best - n->band;
        u32 fix = n->gate && (guard ? blk - n->start < G_FIX : (dist == 1 || dist == -1) && blk - n->start < 15);
        n->band = (signed char)best;
        n->gate = 1;
        n->off = 0;
        n->c = rc[best];
        n->r = rc[best];
        n->last = tg[best];                            /* test 16 */
        n->elast = e[best];
        if (!fix) {
            n->start = blk;
            n->peak = s->pend_pk[best];
            n->nh = 0;
            if (!(legato && !p->retrig)) n->trig = 1;
        }
        s->pend_b0[best] = -1;
    }
    s32 k = n->band;
    if (k >= 0 && n->gate && on[k]) {
        n->off = 0;
        n->r = rc[k];
        n->last = tg[k];                               /* test 16 */
        n->elast = e[k];
        if (repick(n, tg[k], blk)) {
            n->trig = 1;
            n->start = blk;
            n->peak = tg[k];
        }
        steady(n, rc[k]);
        if (blk - n->start < 12) n->peak = maxf(n->peak, tg[k]);
        n->lev = minf(1.0f, tg[k] / maxf(n->peak, 1e-9f));
    }
    for (u32 v = 0; v < SYV_NV; v++) {
        c->trig[v] = 0;
        c->gate[v] = 0.0f;
        c->conf[v] = 1.0f;
        c->fast[v] = 0;
        c->freq[v] = 0.0f;
        c->vel[v] = 0.05f;
        c->lev[v] = 1.0f;
    }
    if (k >= 0) {
        c->trig[0] = n->trig;
        c->gate[0] = n->gate ? 1.0f : 0.0f;
        c->freq[0] = 440.0f * syv_exp2(n->c * (1.0f / 1200.0f));
        c->vel[0] = velocity(n->peak, vref);
        c->lev[0] = n->lev;
    }
}

/* ---- voices ---- */

/* one envelope stage step: attack towards 1.3 (stage 1), decay to sus (2), sustain (3), release (4) */
#define ENV_STEP(LEV, STG, ATT_ONE_MINUS, DEC, SUS, REL)                                                    \
    do {                                                                                                     \
        if (STG == 1u) {                                                                                     \
            LEV = 1.3f - (1.3f - LEV) * (ATT_ONE_MINUS);                                                     \
            if (LEV >= 1.0f) {                                                                               \
                LEV = 1.0f;                                                                                  \
                STG = 2;                                                                                     \
            }                                                                                                \
        } else if (STG == 2u) {                                                                              \
            LEV = (SUS) + (LEV - (SUS)) * (DEC);                                                             \
        } else if (STG == 4u) {                                                                              \
            LEV = LEV * (REL);                                                                               \
        }                                                                                                    \
    } while (0)

/* The oscillator passes: buf += lev x the wave over the block, the step dt ramping by ddt a sample; each returns the
 * phase. idt is 1 / dt at the block's start (the BLEPs' width). */
SYV_TEXT static float pass_saw(float *buf, float ph, float dt, float ddt, float idt, float lev) {
    for (u32 i = 0; i < SYV_FRAMES; i++) {
        ph = ph + dt;
        if (ph >= 1.0f) ph = ph - 1.0f;
        buf[i] = buf[i] + (2.0f * ph - 1.0f - blep(ph, dt, idt)) * lev;
        dt = dt + ddt;
    }
    return ph;
}

SYV_TEXT static float pass_pulse(float *buf, float ph, float dt, float ddt, float idt, float pw, float lev) {
    for (u32 i = 0; i < SYV_FRAMES; i++) {
        ph = ph + dt;
        if (ph >= 1.0f) ph = ph - 1.0f;
        float v = ph < pw ? 1.0f : -1.0f;
        float q = ph - pw;
        if (q < 0.0f) q = q + 1.0f;
        buf[i] = buf[i] + (v + blep(ph, dt, idt) - blep(q, dt, idt)) * lev;
        dt = dt + ddt;
    }
    return ph;
}

SYV_TEXT static float pass_shape(float *buf, u32 kind, float ph, float dt, float ddt, float lev) {
    for (u32 i = 0; i < SYV_FRAMES; i++) {             /* the triangle and the sine */
        ph = ph + dt;
        if (ph >= 1.0f) ph = ph - 1.0f;
        buf[i] = buf[i] + (kind == 3u ? 4.0f * absf(ph - 0.5f) - 1.0f : syv_sin(ph)) * lev;
        dt = dt + ddt;
    }
    return ph;
}

/* a Sound Generator wave; *rnd the random value it draws at each cycle (Grit), *ns the noise's LCG */
SYV_TEXT static float pass_sg(float *buf, u32 wave, float duty, float ph, float dt, float ddt, float lev, float *rnd,
                              u32 *ns) {
    float r = *rnd;
    u32 n = *ns;
    for (u32 i = 0; i < SYV_FRAMES; i++) {
        n = n * 1664525u + 1013904223u;
        float wn = (float)(s32)n * (1.0f / 2147483648.0f);
        ph = ph + dt;
        if (ph >= 1.0f) {
            ph = ph - 1.0f;
            r = wn;
        }
        buf[i] = buf[i] + sg_wave(wave, ph, duty, dt, r, wn) * lev;
        dt = dt + ddt;
    }
    *rnd = r;
    *ns = n;
    return ph;
}

/* the SG's heavy waves (LPSaw, LPSqr, Organ, Vowel: up to 64 harmonics or three formants a sample in wave_core) at
 * half rate: the wave at every odd sample, the even ones halfway between their neighbours (*prev: the block before's
 * last value) */
SYV_TEXT static float pass_sg_half(float *buf, u32 wave, float duty, float ph, float dt, float ddt, float lev,
                                   float *prev, float *rnd) {
    float last = *prev, r = *rnd;
    for (u32 i = 0; i < SYV_FRAMES; i += 2u) {
        float p0 = ph + dt;
        if (p0 >= 1.0f) p0 = p0 - 1.0f;
        float d1 = dt + ddt;
        ph = p0 + d1;
        if (ph >= 1.0f) ph = ph - 1.0f;
        float y = sg_wave(wave, ph, duty, d1, r, 0.0f) * lev;
        buf[i] = buf[i] + 0.5f * (last + y);
        buf[i + 1u] = buf[i + 1u] + y;
        last = y;
        dt = d1 + ddt;
    }
    *prev = last;
    return ph;
}

SYV_TEXT static void pass_supersaw(float *buf, float *uph, float dt, float ddt, float idt, float spread, float mix,
                                   float lev) {
    float cg = (-0.55366f * mix + 0.99785f) * 0.45f * lev, sgn = (-0.73764f * mix * mix + 1.2841f * mix + 0.044372f) *
                                                                   0.45f * lev;
    for (u32 u = 0; u < 7u; u++) {
        float r = 1.0f + UNI_DET[u] * spread, g = u == 3u ? cg : sgn, ph = uph[u], d = dt * r, dd = ddt * r;
        float id = idt / r;
        for (u32 i = 0; i < SYV_FRAMES; i++) {
            ph = ph + d;
            if (ph >= 1.0f) ph = ph - 1.0f;
            buf[i] = buf[i] + (2.0f * ph - 1.0f - blep(ph, d, id)) * g;
            d = d + dd;
        }
        uph[u] = ph;
    }
}

/* FM: a sine carrier, two modulators whose indices decay from the note's start (m1, m2: 1 at the start) */
SYV_TEXT static void pass_fm(float *buf, syv_voice_t *x, const syv_patch_t *p, float dt, float ddt) {
    float ph = x->ph[0], pm = x->phm, pm2 = x->phm2, m1 = x->m1, m2 = x->m2;
    const float fi = p->fm_index, ff = p->fm_floor, fi2 = p->fm2_index, dk1 = p->fm_dk, dk2 = p->fm2_dk;
    const float r1 = p->fm_ratio, r2 = p->fm2_ratio, lev = p->lev[0];
    for (u32 i = 0; i < SYV_FRAMES; i++) {
        float mod = fi * (ff + (1.0f - ff) * m1) * syv_sin(pm);
        float i2 = fi2 * m2;
        if (i2 > 1e-4f) {
            mod = mod + i2 * syv_sin(pm2);
            pm2 = pm2 + dt * r2;
            pm2 = pm2 - floorf_(pm2);
        }
        m1 = m1 * dk1;
        m2 = m2 * dk2;
        pm = pm + dt * r1;
        pm = pm - floorf_(pm);
        ph = ph + dt;
        if (ph >= 1.0f) ph = ph - 1.0f;
        buf[i] = buf[i] + syv_sin(ph + mod * 0.159154943f) * lev;
        dt = dt + ddt;
    }
    x->ph[0] = ph;
    x->phm = pm;
    x->phm2 = pm2;
    x->m1 = m1;
    x->m2 = m2;
}

/* oscillator 2 hard-synced to oscillator 1 (silent unless lev1): a saw or a pulse, its step x s2 ramping (the pitch
 * sweep from the filter envelope) */
SYV_TEXT static void pass_sync(float *buf, syv_voice_t *x, const syv_patch_t *p, float d1, float dd1, float d2,
                               float dd2, float idt2, float pw2, float lev2) {
    float ph1 = x->ph[0], ph2 = x->ph[1];
    const float lev1 = p->lev[0];
    const u32 kind = p->kind[1];
    for (u32 i = 0; i < SYV_FRAMES; i++) {
        ph1 = ph1 + d1;
        ph2 = ph2 + d2;
        if (ph2 >= 1.0f) ph2 = ph2 - floorf_(ph2);
        if (ph1 >= 1.0f) {
            ph1 = ph1 - 1.0f;
            ph2 = ph1 * d2 / d1;
        }
        float v = kind == 2u ? (ph2 < pw2 ? 1.0f : -1.0f) : 2.0f * ph2 - 1.0f - blep(ph2, d2, idt2);
        buf[i] = buf[i] + v * lev2 + (lev1 != 0.0f ? (2.0f * ph1 - 1.0f) * lev1 : 0.0f);
        d1 = d1 + dd1;
        d2 = d2 + dd2;
    }
    x->ph[0] = ph1;
    x->ph[1] = ph2;
}

SYV_TEXT static u32 render(syv_state_t *s, const syv_patch_t *p, const ctl_t *c, float *acc, u32 nv) {
    const u32 flt = p->flt, preset = p->preset;
    const float *pr = s->pre;                          /* the ENV preset, with SUSTAIN (knobs()) */
    const float crf = 0.990454f;                       /* test 16: a 10 ms release, 1% left (test 11: 3 ms) */
    const float g64 = p->glide > 0.0f ? pow_k(p->glide, 64.0f) : 0.0f;   /* glide's step over a block */
    const float dnorm = p->drive != 1.0f ? 1.0f / sat(p->drive) : 1.0f;
    const u32 has_pf = flt == 6u && pr[13] > 0.0f;
    const u32 half = (p->flags & 0x80u) != 0u;        /* flags' top bit: every SG wave at half rate (smooth pads) */
    float *buf = s->buf;
    u32 n_on = 0;
    for (u32 v = 0; v < nv; v++) {
        syv_voice_t *x = &s->v[v];
        if (c->trig[v] || (s->guard && c->gate[v] > 0.0f && !x->active)) {   /* test 15: GUARD's resume */
            x->astg = 1;
            x->fstg = 1;
            x->t = 0.0f;
            x->vel = c->vel[v];
            x->m1 = 1.0f;
            x->m2 = 1.0f;
            if (!x->active || p->glide <= 0.0f || x->f <= 0.0f) x->f = c->freq[v];
            if (!x->active) {
                x->aenv = 0.0f;
                x->fenv = 0.0f;
                x->c3 = 0.0f;
                x->conf = c->conf[v];
                x->lev = c->lev[v];
                x->lit = 0;                             /* test 16: not rendered yet */
            }
            x->active = 1;
        } else if (s->guard && c->gate[v] > 0.0f && x->astg == 4u) {   /* test 15: GUARD: back after a gap, no attack */
            x->astg = 2;
            x->fstg = 2;
        }
        if (c->gate[v] == 0.0f && x->astg > 0u && x->astg < 4u) {
            x->astg = 4;
            x->fstg = 4;
        }
        x->fast = c->fast[v];
        if (!x->active) continue;
        if (!x->lit) {                                  /* a faint blip: not worth a voice, until it first is (test */
            if (c->conf[v] < 0.05f && x->conf < 0.05f && x->astg != 4u) continue;   /* 11's: its attack waits) */
            x->lit = 1;                                 /* test 16: then rendered to its end (test 11 left it out */
        }                                               /*   again under 5%, a step each way: clicks) */
        n_on++;
        if (c->vel[v] > x->vel) x->vel = c->vel[v];
        /* the block's pitch (glide), LFO, confidence and level */
        const float ft = c->freq[v] > 0.0f ? c->freq[v] : x->f;
        const float f1 = ft + (x->f - ft) * g64;
        x->phl = x->phl + p->lfo_inc * 64.0f;
        x->phl = x->phl - floorf_(x->phl);
        float ld = (x->t + 32.0f) * p->lfo_dk;
        const float lfo = syv_sin(x->phl) * (ld < 1.0f ? ld : 1.0f);
        const float conf1 = x->conf + (c->conf[v] - x->conf) * 0.2263f;   /* 1 - (1 - 0.004)^64 */
        const float lev1 = x->lev + (c->lev[v] - x->lev) * 0.1203f;       /* 1 - (1 - 0.002)^64 */
        const float vs = (1.0f - p->avel) + p->avel * x->vel;
        const float lvl = vs * (1.0f + p->lfo_amp * lfo);
        const float k0 = lvl * ((1.0f - p->follow) + p->follow * x->lev) * x->conf;
        const float k1 = lvl * ((1.0f - p->follow) + p->follow * lev1) * conf1;
        const float cr = x->fast ? crf : (flt == 6u ? pr[3] : p->ar);
        const float pitch = 1.0f + p->lfo_pitch * lfo;
        const float fb = x->f * p->octm * pitch, fe_ = f1 * p->octm * pitch;   /* the block's start and end pitch */
        float dt[3], ddt[3], idt[3];
        for (u32 o = 0; o < 3u; o++) {
            float d0 = fb * p->ratio[o] * (1.0f / FS), d1 = fe_ * p->ratio[o] * (1.0f / FS);
            d0 = d0 > 0.45f ? 0.45f : d0;
            d1 = d1 > 0.45f ? 0.45f : d1;
            dt[o] = d0;
            ddt[o] = (d1 - d0) * (1.0f / 64.0f);
            idt[o] = d0 > 1e-6f ? 1.0f / d0 : 0.0f;
        }
        const float pw1 = clampf(p->pw[0] + p->lfo_pw * lfo, 0.05f, 0.95f);
        const float pw2 = clampf(p->pw[1] + p->lfo_pw * lfo, 0.05f, 0.95f);
        const float lv2 = p->lev[1] * (1.0f - p->lfo_vec * (0.5f + 0.5f * lfo));
        const float lv3 = p->lev[2] * (1.0f - p->lfo_vec * (0.5f - 0.5f * lfo));
        /* the oscillators */
        for (u32 i = 0; i < SYV_FRAMES; i++)
            buf[i] = 0.0f;
        const u32 k0d = p->kind[0], k1d = p->kind[1], k2d = p->kind[2];
        if (p->sync && k1d) {
            float s0 = 1.0f, s1 = 1.0f;
            if (p->penv != 0.0f) {                     /* the sweep at the block's start and (as the filter envelope
                                                          will be) its end */
                float fe = x->fenv, fs = x->fenv;
                u32 st = x->fstg;
                for (u32 i = 0; i < SYV_FRAMES; i++) ENV_STEP(fs, st, 1.0f - p->fa, p->fd, p->fsus, p->fr);
                s0 = syv_exp2(p->penv * fe * (1.0f / 12.0f));
                s1 = syv_exp2(p->penv * fs * (1.0f / 12.0f));
            }
            float a = minf(dt[1] * s0, 0.45f), b = minf((dt[1] + 64.0f * ddt[1]) * s1, 0.45f);
            pass_sync(buf, x, p, dt[0], ddt[0], a, (b - a) * (1.0f / 64.0f), a > 1e-6f ? 1.0f / a : 0.0f, pw2, lv2);
        } else {
            if (k0d == 5u) pass_supersaw(buf, x->uph, dt[0], ddt[0], idt[0], p->spread, p->mix, p->lev[0]);
            else if (k0d == 7u) pass_fm(buf, x, p, dt[0], ddt[0]);
            else if (k0d == 1u) x->ph[0] = pass_saw(buf, x->ph[0], dt[0], ddt[0], idt[0], p->lev[0]);
            else if (k0d == 2u) x->ph[0] = pass_pulse(buf, x->ph[0], dt[0], ddt[0], idt[0], pw1, p->lev[0]);
            else if (k0d == 3u || k0d == 4u) x->ph[0] = pass_shape(buf, k0d, x->ph[0], dt[0], ddt[0], p->lev[0]);
            else if (k0d == 6u && (half || (p->wave[0] >= 24u && p->wave[0] <= 27u)))
                x->ph[0] = pass_sg_half(buf, p->wave[0], p->duty[0], x->ph[0], dt[0], ddt[0], p->lev[0], &x->sgprev, &x->rnd);
            else if (k0d == 6u)
                x->ph[0] = pass_sg(buf, p->wave[0], p->duty[0], x->ph[0], dt[0], ddt[0], p->lev[0], &x->rnd, &x->ns);
            if (k1d == 1u) x->ph[1] = pass_saw(buf, x->ph[1], dt[1], ddt[1], idt[1], lv2);
            else if (k1d == 2u) x->ph[1] = pass_pulse(buf, x->ph[1], dt[1], ddt[1], idt[1], pw2, lv2);
            else if (k1d == 3u || k1d == 4u) x->ph[1] = pass_shape(buf, k1d, x->ph[1], dt[1], ddt[1], lv2);
            else if (k1d == 6u && half)
                x->ph[1] = pass_sg_half(buf, p->wave[1], p->duty[1], x->ph[1], dt[1], ddt[1], lv2, &x->m1, &x->rnd);
            else if (k1d == 6u)
                x->ph[1] = pass_sg(buf, p->wave[1], p->duty[1], x->ph[1], dt[1], ddt[1], lv2, &x->rnd, &x->ns);
        }
        if (k2d == 1u) x->ph[2] = pass_saw(buf, x->ph[2], dt[2], ddt[2], idt[2], lv3);
        else if (k2d == 2u) x->ph[2] = pass_pulse(buf, x->ph[2], dt[2], ddt[2], idt[2], p->pw[2], lv3);
        else if (k2d == 3u || k2d == 4u) x->ph[2] = pass_shape(buf, k2d, x->ph[2], dt[2], ddt[2], lv3);
        else if (k2d == 6u && half)
            x->ph[2] = pass_sg_half(buf, p->wave[2], p->duty[2], x->ph[2], dt[2], ddt[2], lv3, &x->m2, &x->rnd);
        else if (k2d == 6u)
            x->ph[2] = pass_sg(buf, p->wave[2], p->duty[2], x->ph[2], dt[2], ddt[2], lv3, &x->rnd, &x->ns);
        if (p->sub > 0.0f) {                           /* the sub, an octave down: a plain square (under the filter) */
            float ph = x->phs, d = dt[0] * 0.5f, dd = ddt[0] * 0.5f, g = p->sub;
            for (u32 i = 0; i < SYV_FRAMES; i++) {
                ph = ph + d;
                if (ph >= 1.0f) ph = ph - 1.0f;
                buf[i] = buf[i] + (ph < 0.5f ? g : -g);
                d = d + dd;
            }
            x->phs = ph;
        }
        if (p->noise > 0.0f) {
            u32 n = x->ns;
            for (u32 i = 0; i < SYV_FRAMES; i++) {
                n = n * 1664525u + 1013904223u;
                buf[i] = buf[i] + p->noise * ((float)(s32)n * (1.0f / 2147483648.0f));
            }
            x->ns = n;
        }
        /* the filter, the envelopes and the level */
        float aenv = x->aenv, fenv = x->fenv, ic1 = x->ic1, ic2 = x->ic2, k = k0;
        const float dk = (k1 - k0) * (1.0f / 64.0f);
        u32 astg = x->astg, fstg = x->fstg, alive = 1, n = SYV_FRAMES;
        if (flt == 6u) {                               /* the Sound Generator's ENV preset (env.c) */
            const float r0 = pr[0], r1 = pr[1], r2 = pr[2], q4 = pr[4], q5 = pr[5], q6 = pr[6], q7 = pr[7];
            const float sgf = x->f * p->octm * (1.0f / FS);
            float c1 = x->c1, c2 = x->c2, c3 = x->c3;
            u32 tick = x->tick;
            for (u32 i = 0; i < SYV_FRAMES; i++) {
                if (preset == 0u) {
                    if (astg == 4u) {
                        aenv = aenv - (x->fast ? 1.0f / 144.0f : 1.0f / 400.0f);
                        if (aenv <= 0.0f) {
                            alive = 0;
                            n = i;
                            break;
                        }
                    } else {
                        aenv = 1.0f;
                    }
                } else {
                    ENV_STEP(aenv, astg, r0, r1, r2, cr);
                    if (astg == 4u && aenv < 1e-5f) {
                        alive = 0;
                        n = i;
                        break;
                    }
                }
                float y = buf[i];
                if (has_pf) {
                    ENV_STEP(fenv, fstg, q4, q5, q6, q7);
                    if ((tick & 15u) == 0u) {
                        float rc = clampf(sgf * syv_exp2(pr[8] + pr[9] * fenv + p->p2base), 0.0006f, 0.45f);
                        float g = syv_tan(3.14159265f * rc);
                        float b1 = 1.0f / (1.0f + g * (g + pr[10]));
                        c1 = b1;
                        c2 = g * b1;
                        c3 = g * g * b1;
                    }
                    tick++;
                    float v3 = y * pr[11] - ic2;
                    float v1 = c1 * ic1 + c2 * v3;
                    float v2 = ic2 + c2 * ic1 + c3 * v3;
                    ic1 = 2.0f * v1 - ic1;
                    ic2 = 2.0f * v2 - ic2;
                    float yy = v2 * pr[12] * aenv;
                    float a = absf(yy);
                    if (a > 0.6f) {
                        float u = (a - 0.6f) * 2.5f;
                        float sv = 0.6f + 0.4f * u / (1.0f + u);
                        yy = yy < 0.0f ? -sv : sv;
                    }
                    y = yy;
                } else {
                    y = y * aenv;
                }
                acc[i] = acc[i] + y * k;
                k = k + dk;
            }
            x->c1 = c1;
            x->c2 = c2;
            x->c3 = c3;
            x->tick = tick;
        } else {
            const float am = 1.0f - p->aa, fm = 1.0f - p->fa, ad = p->ad, as = p->asus, fd = p->fd, fs = p->fsus,
                        fr = p->fr;
            float a1 = 0.0f, a2 = 0.0f, a3 = 0.0f, G = 0.0f, kd = 0.0f, kf = 0.0f, comp = 1.0f;
            if (flt) {                                 /* the block's coefficients */
                float kt = p->keytrk != 0.0f ? syv_exp2(p->keytrk * syv_log2(maxf(fb, 1.0f) * (1.0f / 261.63f)))
                                             : 1.0f;
                float fe = p->fenv * fenv * ((1.0f - p->fvel) + p->fvel * x->vel);
                float fc = clampf(p->cut * kt * syv_exp2(fe + p->lfo_cut * lfo), 20.0f, 0.45f * FS);
                float g = syv_tan(3.14159265f * fc * (1.0f / FS));
                if (flt <= 3u) {
                    kd = 2.0f - 1.96f * p->reso;
                    a1 = 1.0f / (1.0f + g * (g + kd));
                    a2 = g * a1;
                    a3 = g * a2;
                } else {
                    G = g / (1.0f + g);
                    kf = (flt == 4u ? 4.0f : 3.2f) * p->reso;
                    comp = 1.0f + (flt == 4u ? 0.6f : 0.5f) * kf;
                }
            }
            const float drive = p->drive;
            float z0 = x->y[0], z1 = x->y[1], z2 = x->y[2], z3 = x->y[3];
            for (u32 i = 0; i < SYV_FRAMES; i++) {
                ENV_STEP(aenv, astg, am, ad, as, cr);
                ENV_STEP(fenv, fstg, fm, fd, fs, fr);
                if (astg == 4u && aenv < 1e-5f) {
                    alive = 0;
                    n = i;
                    break;
                }
                float y = buf[i];
                if (drive != 1.0f) y = sat(y * drive) * dnorm;
                if (flt >= 1u && flt <= 3u) {
                    float v3 = y - ic2;
                    float v1 = a1 * ic1 + a2 * v3;
                    float v2 = ic2 + a2 * ic1 + a3 * v3;
                    ic1 = 2.0f * v1 - ic1;
                    ic2 = 2.0f * v2 - ic2;
                    y = flt == 1u ? v2 : flt == 2u ? v1 : y - kd * v1 - v2;
                } else if (flt == 4u || flt == 5u) {
                    float u = sat(y * 1.2f - kf * (flt == 4u ? z3 : z2));
                    float vv = G * (u - z0);
                    float y1 = vv + z0;
                    z0 = y1 + vv;
                    vv = G * (y1 - z1);
                    float y2 = vv + z1;
                    z1 = y2 + vv;
                    vv = G * (y2 - z2);
                    float y3 = vv + z2;
                    z2 = y3 + vv;
                    if (flt == 4u) {
                        vv = G * (y3 - z3);
                        float y4 = vv + z3;
                        z3 = y4 + vv;
                        y = y4 * comp;
                    } else {
                        y = y3 * comp;
                    }
                }
                acc[i] = acc[i] + y * aenv * k;
                k = k + dk;
            }
            x->y[0] = z0;
            x->y[1] = z1;
            x->y[2] = z2;
            x->y[3] = z3;
        }
        x->aenv = alive ? aenv : 0.0f;
        x->fenv = fenv;
        x->ic1 = ic1;
        x->ic2 = ic2;
        x->astg = (u8)astg;
        x->fstg = (u8)fstg;
        x->t = x->t + (float)n;
        if (!alive) x->active = 0;
        x->f = f1;
        x->conf = conf1;
        x->lev = lev1;
    }
    return n_on;
}

/* ---- the output: a DC blocker, the gain, the soft clip, the fade, the scale ---- */

SYV_DATA static float output(syv_state_t *s, const float *acc, float gain, float mg, float mgt, float fade,
                             float scale, s32 *out) {
    float xm1 = s->dcx, ym1 = s->dcy;
    for (u32 i = 0; i < SYV_FRAMES; i++) {
        float x = acc[i];
        ym1 = x - xm1 + 0.9995f * ym1;
        xm1 = x;
        float y = ym1 * gain;
        if (y > 1.0f) y = 1.0f;
        else if (y < -1.0f) y = -1.0f;
        else y = y * (1.5f - 0.5f * (y * y));
        if (mg < mgt) {
            mg = mg + fade;
            if (mg > mgt) mg = mgt;
        } else if (mg > mgt) {
            mg = mg - fade;
            if (mg < mgt) mg = mgt;
        }
        out[i] = (s32)(y * mg * scale);
    }
    s->dcx = xm1;
    s->dcy = ym1;
    return mg;
}

SYV_DATA float syv_block(syv_state_t *s, const syv_patch_t *tone, const syv_knobs_t *k, const float *tg,
                         const float *per, const float *e, const u8 *nper, float vref, float mg, float mgt, float fade,
                         float scale, s32 *out) {
    (void)nper;
    if (!s->started) syv_reset(s);
    for (u32 b = 0; b < SYV_BANDS; b++)                /* SY test 15: each band's run (WAIT) */
        s->run[b] = tg[b] > 0.0f ? (u8)(s->run[b] < 255u ? s->run[b] + 1u : 255u) : 0u;
    s->guard = k->guard != 0u;
    {
        float lm = 0.0f;                               /* SY test 16: SENS's held peak */
        for (u32 b = 0; b < SYV_BANDS; b++)
            if (tg[b] > lm) lm = tg[b];
        float hk = s->pkh * PKH_DK;
        s->pkh = lm > hk ? lm : hk;
    }
    knobs(s, tone, k);
    const syv_patch_t *p = &s->eff;
    float *rc = s->rc;
    for (u32 b = 0; b < SYV_BANDS; b++)
        rc[b] = cents_of_period(per[b]);
    ctl_t *cp = &s->ctl;
    u32 cap = p->flags & 0x0Fu;                      /* the tone's voice cap (flags' low bits) */
    u32 nv = p->mono ? 1u : cap && cap < SYV_NV ? cap : SYV_NV;
    if (p->mono) notes_mono(s, p, tg, rc, e, vref, cp, k);
    else notes_poly(s, p, tg, rc, vref, cp, nv, k);
    float *acc = s->acc;
    for (u32 i = 0; i < SYV_FRAMES; i++)
        acc[i] = 0.0f;
    s->cost = render(s, p, cp, acc, nv);
    mg = output(s, acc, p->gain, mg, mgt, fade, scale, out);
    float *slot = s->rc_prev[s->blk & 3];             /* this block's readings and energies, for four blocks on */
    float *es = s->e_prev[s->blk & 3];
    for (u32 b = 0; b < SYV_BANDS; b++) {
        slot[b] = rc[b];
        es[b] = e[b];
        s->prev[b] = tg[b] > 0.0f;
    }
    s->blk++;
    return mg;
}
