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
#define G_FIX 45                    /* mono: a band taking over a note this young moves it (no second attack; SY test
                                       17: 60 ms, a low string's own band comes 20-30 ms after its pick's overtones) */
#define PKH_DK 0.995f               /* SY test 16: SENS's held peak falls this much a block (-20 dB in 0.6 s) */
#define P_WIN 45                    /* SY test 16, PICK: a new note within this many blocks of a pick (60 ms: a low
                                       string sounds 20-30 ms after its pick); mono within P_WIN_M + CONFIRM */
#define P_WIN_M 45
#define B_HAND 17.0f                /* SY test 17: a band beginning next to a voice's at its pitch takes it on */
#define B_AGE 24                    /*   test 10's AGE_MIN: a voice younger than this ends at once */
#define B_WIN 45                    /*   a band beginning within this many blocks of a pick attacks; else soft */
#define B_REPICK 12                 /*   a re-pick needs the input's pick this recent */
#define B_GUARD 1.5f                /*   GUARD: a new band takes a sounding voice only at this x its level */
#define B_TAKE 1.5f                 /*   mono: a new band without a pick takes the note over at this x its level, */
#define B_TAKE_G 2.0f               /*   with GUARD at this x, */
#define B_TAKE_P 1.0f               /*   with a pick at this x */
#define B_LOUD 0.5f                /*   mono from silence without a pick: at this x the held peak */
#define M_YOUNG 60                  /*   mono: a band begun this many blocks ago or less may become the note */
#define AM_SOFT 0.99847f            /*   a soft start's rise: 1 - 1/653 a sample (about 20 ms) */
#define AM_QUICK 0.97917f           /*   a picked voice's gate: 1 - 1/48 a sample (the attack is the pick's) */
#define OFF_MAX 3                   /*   a voice in full rides this many blocks of its band off; a young one none */
#define G_RIDE 20                   /* SY test 16, GUARD on a mono tone: a note rides its band's gaps this long, */
#define G_END 0.1f                  /*   unless the band's energy falls under this x its last (the string stopped) */
/* SY test 18: a band the analysis saw struck (sy_fp.c: its energy at 2 x its last 32 blocks', in the last 32) as it
 * begins (its first M_YOUNG blocks) has an onset: a string picked, whether the input's pick detector saw it or not (it
 * misses picks over ringing strings). */
#define B_NEW 0.3f                  /*   mono: a band with an onset, begun after the note's own, at this x the note's
                                       level takes the note over, no pick needed (test 17: 1.5x without a pick), */
#define B_NEW_G 0.6f                /*   with GUARD at this x (GUARD PICK: only with a pick, as test 17), */
#define B_CONF 8                    /*   once it has sounded this many blocks (11 ms) reading steadily (STABLE): a
                                       pick's blips (mostly under 27 ms, unsteady) take nothing; */
#define B_STRUM 45                  /*   and it began this many blocks (60 ms) or more after the note took its string:
                                       a strum's later strings leave a mono note on its first (the user's take: 8x the
                                       chord attacks without this) */
#define LAW_MAX 2.0f                /* SY test 18, LAW 2:1: the factor (the band's level over a full pick's) at most */
/* SY test 19, a mono tone (test 18 on the unit, single notes: "extra notes", "late or missing notes"). On the user's
 * take the extra notes came at let-gos: the note moved on to what rang after it (the finger's lower fret, a
 * semitone down, 26 times; an open B or E; the octave), up to 290 ms; those bands began at 0.06x the playing's level
 * (pkh, median; a played note 1.0x) with no pick. */
#define M_MOVE 0.4f                 /*   a note moves on or starts without a pick only from a band at this x pkh (the
                                         tracker's test 6 MOVE_HOLD), */
#define M_PICK 0.2f                 /*   with a pick at this x */
/* The notes themselves from the SG tracker (YIN), when it runs: the bands put the overtones first (a low string's own
 * band sounds 21-31 ms after the pluck, its octave, twelfth and up before it: test 18 played them, 109 of the take's
 * 136 notes), YIN reads the note at 17-19 ms there (12-15 ms on the high strings, against the band's 9-15), wrong in
 * 5 of 128 notes (a semitone flat, mostly). */
#define Y_PRE 3                     /*   the tracker's pre: its analyses this soon after a pluck took samples before it */
#define Y_WIN 60                    /*   a pluck's note: its readings this many blocks after it (80 ms) */
#define Y_PEND 40                   /*   a note waits this long for its band (53 ms) from the last reading of it */
#define Y_FIX 2                     /*   a clean reading this many semitones or less off the note puts it right */
#define Y_RIDE 20                   /*   a note whose band stopped, a band a tone or less away sounding, waits this long
                                         for the tracker's move (27 ms; it reads a slide's note in 3 analyses) */
/* SY test 20 (test 19 on the unit: "missed notes still on fat bass and sync lead, no matter what settings"). Test 19
 * gave a pick an attack only when nothing sounded, or on a reading of another note (clean, or twice; a semitone: twice
 * with its band sounding); the tracker's own note (its lock) only moved the note, no attack. On lines picked note to
 * note (each pick cutting the note before, the user's take was mostly let go between notes) 37 of 126 picks came in
 * as a glide, no attack: every note picked again on its own pitch, and most semitone steps (the lock came first).
 * Every pluck of the tracker's now owes an attack (yowe) until it gets one: on a reading, or on the tracker's note-on
 * for it (its seq moved, the same note included: a re-pick its level rule passed). */
#define Y_OLD 12                    /*   a reading of the note before this soon after the pluck is that string ringing
                                         into the analysis (its window is 29 ms on a low string): not a new note */

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
SYV_TEXT static float pow_k(float a, float inv) {   /* SY test 20: in the voices' slot (the notes' was full) */
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
        s->n[v].born = -1000000;
        s->v[v].ns = 12345u + 7919u * v;
        for (u32 u = 0; u < 7u; u++) {
            float x = (float)u * 0.1371f + (float)v * 0.31f;
            s->v[v].uph[u] = x - floorf_(x);
        }
    }
    s->gat = -1000000;                                 /* SY test 18: the envelopes not started yet */
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

SYV_TEXT static u32 repick(syv_note_t *n, float lv, s32 blk) {   /* SY test 20: as pow_k */
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

static inline float b_level(const syv_note_t *n, const float *tg) {
    return n->gate && tg[n->band] > 0.0f ? tg[n->band] : n->last;
}

/* a voice on band k from this block (its envelopes: an attack with a pick, else soft: no sweep, a gentle rise) */
SYV_NOTES static void b_start(syv_note_t *n, s32 k, const float *tg, const float *rc, const float *e, s32 blk,
                             u32 pick) {   /* SY test 19: one copy (the notes' slot was full) */
    n->band = (signed char)k;
    n->gate = 1;
    n->off = 0;
    n->start = blk;
    n->born = blk;
    n->took = blk;                                     /* SY test 18 */
    n->peak = tg[k];
    n->c = rc[k];
    n->r = rc[k];
    n->last = tg[k];
    n->elast = e[k];
    n->lev = 1.0f;
    n->nh = 0;
    n->rp = -1000000;
    n->young = 1;
    n->fast = 0;
    n->trig = (u8)(pick != 0u);
    n->soft = (u8)(pick == 0u);
    n->yband = -1;                                     /* SY test 19: the bands' (the tracker's: y_start) */
}

/* SY test 17: no notes (BOSS SY's way, test 10's tracking; test 11's voices). The bands that sound are the analysis's
 * (sy_fp.c: a band owns, the gate, the hold, FUND): each has a voice of its own, up to SYV_NV, from the block it begins
 * (WAIT blocks later if set; SENS: at least that % of the held peak). The voice plays its band's own pitch, its tracked
 * period block by block (no smoothing: bends and vibrato as they are), and its level follows the band (test 11's young
 * confidence, then the tone's FOLLOW). A band beginning next to a voice's band at its pitch (B_HAND, test 10's 1%) takes
 * that voice on; a voice whose band stops goes on with a neighbour reading its pitch (B_FOLLOW), rides OFF_MAX blocks,
 * or ends (a fast release if younger than B_AGE: test 10's AGE_MIN). The envelopes start on a pick: a band beginning
 * within B_WIN blocks of the input's pick attacks (the tone's attack and filter sweep); later, it comes in softly (a
 * gentle rise, the filter at its sustain: a ring, an open string, a flicker); a voice whose band is picked again attacks
 * again (test 11's re-pick, with the input's pick). A new band takes a free voice, else the quietest voice's if louder
 * (GUARD: B_GUARD x louder). (SY test 18 tried attacks on the analysis's strikes here too: on the user's take they
 * quadrupled the chords' attacks, every partial of a strum struck; a soft start is heard, test 17's silence was the
 * envelopes', render() now opens them again.) */
SYV_NOTES static void bands_poly(syv_state_t *s, const syv_patch_t *p, const float *tg, const float *rc, const float *e,
                                 float vref, ctl_t *c, u32 nv, const syv_knobs_t *kn) {
    const s32 blk = s->blk;
    const float *rc4 = blk >= 4 ? s->rc_prev[blk & 3] : rc;
    const u32 wait = kn->wait <= 12u ? kn->wait : 12u, guard = kn->guard != 0u;
    const float sens = (float)(kn->sens <= 50u ? kn->sens : 50u) * 0.01f;
    const u32 since = kn->since;
    u8 on[SYV_BANDS];
    for (u32 k = 0; k < SYV_BANDS; k++)
        on[k] = tg[k] > 0.0f;
    unsigned long long taken = 0;
    for (u32 v = 0; v < nv; v++) {                     /* the voices go on, move with their partial, or end */
        syv_note_t *n = &s->n[v];
        n->trig = 0;
        n->soft = 0;
        n->glide = 0;
        if (n->band < 0 || !n->gate) continue;
        if (on[n->band]) {
            n->off = 0;
            taken |= 1ull << n->band;
            continue;
        }
        if (follow(s, n, on, rc, nv, &taken)) {
            n->off = 0;
            continue;
        }
        n->off++;
        if (n->young || n->off > OFF_MAX) {
            n->gate = 0;
            n->rel = blk;
            n->fast = (u8)(blk - n->born < B_AGE);
        }
    }
    for (u32 k = 0; k < SYV_BANDS; k++) {              /* the bands beginning (their run's (WAIT + 1)th block) */
        if (!on[k] || s->run[k] != wait + 1u || ((taken >> k) & 1ull)) continue;
        if (sens > 0.0f && tg[k] < sens * s->pkh) continue;
        s32 w = -1;
        for (u32 v = 0; v < nv && w < 0; v++) {        /* a voice's partial moving on to this band */
            const syv_note_t *n = &s->n[v];
            if (n->band >= 0 && n->gate && (n->band - (s32)k == 1 || (s32)k - n->band == 1) &&
                absf(rc[k] - n->r) < B_HAND)
                w = (s32)v;
        }
        if (w >= 0) {
            s->n[w].band = (signed char)k;
            s->n[w].off = 0;
            taken |= 1ull << k;
            continue;
        }
        for (u32 v = 0; v < nv; v++)                   /* a free voice, released longest ago */
            if (!s->n[v].gate && (w < 0 || s->n[v].rel < s->n[w].rel)) w = (s32)v;
        if (w < 0) {                                   /* else the quietest voice, if this band is louder */
            for (u32 v = 0; v < nv; v++)
                if (w < 0 || b_level(&s->n[v], tg) < b_level(&s->n[w], tg)) w = (s32)v;
            if ((guard ? B_GUARD : 1.0f) * b_level(&s->n[w], tg) >= tg[k]) continue;
        }
        b_start(&s->n[w], (s32)k, tg, rc, e, blk, since <= B_WIN + wait);
        taken |= 1ull << k;
    }
    for (u32 v = 0; v < nv; v++) {                     /* the pitch, the level, settling, re-picks */
        syv_note_t *n = &s->n[v];
        if (n->band < 0 || !n->gate || !on[n->band]) continue;
        s32 k = n->band;
        n->r = rc[k];
        n->c = rc[k];                                  /* the band's pitch as it is (test 10's) */
        n->last = tg[k];
        n->elast = e[k];
        if (n->young) {
            n->peak = maxf(n->peak, tg[k]);
            if (blk - n->start >= PROB && tg[k] >= PROB_HOLD * n->peak && blk >= 4 && absf(rc[k] - rc4[k]) < STABLE)
                n->young = 0;
        } else {
            if (repick(n, tg[k], blk) && since <= B_REPICK) {   /* picked again (the input's pick with it) */
                n->trig = 1;
                n->soft = 0;
                n->start = blk;
                n->peak = tg[k];
            }
            if (blk - n->start < 12) n->peak = maxf(n->peak, tg[k]);
        }
        n->lev = minf(1.0f, tg[k] / maxf(n->peak, 1e-9f));
    }
}

/* SY test 17, a mono tone: one voice, on a band. From silence a note starts only on a pick (a band beginning within
 * B_WIN blocks of one: what rings on after a note is let go starts nothing); a band beginning while the note sounds,
 * louder than B_TAKE x it (GUARD: as loud), takes it over: with a pick, an attack (legato tones glide); without, the
 * pitch moves (glide), no attack; GUARD PICK: only with a pick. The note plays its band's pitch as it is, rides its
 * band's gaps (GUARD: G_RIDE blocks unless the string stopped), and attacks again when its band is picked again.
 * SY test 18 (test 17 left open strings silent: the pick detector misses picks over ringing strings, and only a pick
 * or a 1.5x louder band could take the note): a band with an onset of its own counts as picked for starting a note
 * from silence (not with GUARD PICK), and one begun after the note's band takes the note at B_NEW x its level (GUARD:
 * B_NEW_G) once it has sounded B_CONF blocks reading steadily, unless it sits an octave, an octave and a fifth or two
 * octaves over a band struck lately at -20 dB of its energy or more (a new low string's partials own before the
 * string's own band): the newest string wins. */
static inline u32 over_struck(const u8 *struck, const float *e, s32 k) {
    const float f = 0.01f * e[k];
    return (k >= 12 && struck[k - 12] && e[k - 12] >= f) || (k >= 19 && struck[k - 19] && e[k - 19] >= f) ||
           (k >= 24 && struck[k - 24] && e[k - 24] >= f);
}

/* SY test 19: a mono note the SG tracker (YIN) found (its pluck's first voiced analysis): on band k from this block,
 * with an attack. Its band may not sound yet (a low string's sounds 21-31 ms after the pluck on the user's take, YIN
 * reads it at 17-19 ms): it waits for it (ypend) at the band's centre and the loudest band's level. */
SYV_NOTES static void y_start(syv_note_t *n, s32 k, const float *tg, const float *rc, const float *e, s32 blk, float lm) {
    b_start(n, k, tg, rc, e, blk, 1u);
    n->yat = blk;
    n->yband = (signed char)k;
    if (tg[k] > 0.0f) {
        n->ypend = 0;
    } else {
        n->ypend = 1;
        n->c = SYV_CENTRE[k];
        n->r = SYV_CENTRE[k];
        n->peak = lm;
        n->last = lm;
    }
}

/* SY test 20: a reading this many semitones off the note sounding is one of YIN's own slips as often as a new note
 * (a fourth, a fifth, an octave, a twelfth, two octaves: the 16th-note model read a fifth up once, clean) */
static inline u32 y_odd(s32 d) {
    const s32 a = d < 0 ? -d : d;
    return a == 5 || a == 7 || a == 12 || a == 19 || a == 24;
}

/* SY test 19: the note to band k, no attack (legato: the pitch glides), as the tracker says (its band may not sound
 * yet: it waits for it at the band's centre) */
SYV_NOTES static void y_move(syv_note_t *n, s32 k, const u8 *on, const float *tg, const float *rc, const float *e,
                             s32 blk) {
    n->band = (signed char)k;
    n->yband = (signed char)k;
    n->took = blk;
    n->yat = blk;
    n->off = 0;
    n->ypend = (u8)!on[k];
    n->c = on[k] ? rc[k] : SYV_CENTRE[k];
    n->r = n->c;
    if (on[k]) {
        n->last = tg[k];
        n->elast = e[k];
    }
    n->glide = 1;
}

SYV_NOTES static void bands_mono(syv_state_t *s, const syv_patch_t *p, const float *tg, const float *rc, const float *e,
                                 const u8 *struck, float vref, ctl_t *c, const syv_knobs_t *kn) {
    const s32 blk = s->blk;
    const float *rc4 = blk >= 4 ? s->rc_prev[blk & 3] : rc;
    const u32 wait = kn->wait <= 12u ? kn->wait : 12u, guard = kn->guard != 0u, pickg = kn->guard >= 2u;
    const float sens = (float)(kn->sens <= 50u ? kn->sens : 50u) * 0.01f;
    const u32 since = kn->since;
    syv_note_t *n = &s->n[0];
    const float mv = M_MOVE * s->pkh;                  /* SY test 19: the level a move needs */
    const u32 yrun = (kn->yflag & 0x80u) != 0u;        /* SY test 19: the tracker runs: its notes */
    if (yrun && !s->ymono) s->yseq = kn->yseq;         /* SY test 20: its note-ons from here on */
    s->ymono = (u8)yrun;
    if (yrun && kn->ysince == 0u) {                    /* the tracker's pluck: its first readings decide the note */
        s->yact = 0;
        s->yprev = 0;
        s->yowe = 1;                                   /* SY test 20: it owes an attack; the note before it */
        s->yold = (u8)(n->band >= 0 && (n->gate || blk - n->rel <= Y_WIN) ? n->band + 41 : 0);
    }
    if (!yrun || kn->ysince > Y_WIN) s->yowe = 0;
    u8 on[SYV_BANDS], onm[SYV_BANDS], onf[SYV_BANDS];
    float lm = 0.0f;
    /* SY test 19: with the tracker's notes a note follows its partial (a bend) only from the tracker's note up (a
     * string bends up from its fret, and back): below it is a let-go's lower fret (the tracker sees the level fall
     * and keeps its note) or a slide down (the tracker's move brings it) */
    const s32 yfloor = yrun && n->gate ? n->yband : -1;
    for (u32 k = 0; k < SYV_BANDS; k++) {
        on[k] = tg[k] > 0.0f;
        onm[k] = on[k] && tg[k] >= mv;                 /* SY test 19: the bands a note may move on to */
        onf[k] = onm[k] && (s32)k >= yfloor;           /*   and follow its partial to */
        if (tg[k] > lm) lm = tg[k];
    }
    n->trig = 0;
    n->soft = 0;
    n->glide = 0;
    unsigned long long taken = 0;
    if (n->band >= 0 && n->gate && !on[n->band]) {
        if (n->ypend && blk - n->yat < Y_PEND) {       /* SY test 19: the tracker's note, its band yet to sound */
            n->off = 0;
        } else {
            s32 j = -1;                                /* a young note's band (the pick's blip) gone: the band begun */
            if (n->young && !yrun)                     /*   lately and sounding now takes the note (no end, no attack; */
                for (u32 q = 0; q < SYV_BANDS; q++)    /*   not the tracker's notes) */
                    if (onm[q] && s->run[q] <= M_YOUNG && (j < 0 || tg[q] > tg[j])) j = (s32)q;
            if (follow(s, n, onf, rc, 1, &taken)) {
                n->off = 0;
                n->ypend = 0;
            } else if (j >= 0) {
                n->band = (signed char)j;
                n->off = 0;
                n->c = rc[j];
                n->r = rc[j];
                n->last = tg[j];
                n->elast = e[j];
                n->peak = maxf(n->peak, tg[j]);
            } else {
                n->off++;
                u32 ride = guard && n->off <= G_RIDE && !(e[n->band] < G_END * n->elast);
                u32 yride = 0;                         /* SY test 19: a band a tone or less away sounding: the */
                if (yrun && n->off <= Y_RIDE)          /*   tracker may move the note there (a hammer-on, a slide); */
                    for (s32 q = n->band - 2; q <= n->band + 2; q++)   /* it rides on until then, at its pitch */
                        if (q >= 0 && q < SYV_BANDS && q != n->band && on[q]) yride = 1;
                if ((n->young && !yrun) || n->ypend || (n->off > OFF_MAX && !ride && !yride)) {
                    n->gate = 0;
                    n->ypend = 0;
                    n->rel = blk;
                    n->fast = (u8)(blk - n->born < B_AGE);
                }
            }
        }
    }
    /* SY test 19: the tracker's note. Its pluck's first voiced analysis (from Y_PRE blocks on: before, its samples
     * came before the pluck) starts the note, or takes it over from another: then clean, or the same note read twice
     * (the first readings after a pick over a ringing string can read the old string, or a mix); one reading the
     * note sounding does nothing (the string rang into the analysis; a re-pick is the band's). A clean reading a tone
     * or less off it within Y_WIN of the pluck moves it there, no attack (the first period can read flat). Where the
     * tracker's own note moves (its lock on a pluck; legato: a slide, a hammer-on, a pull-off, read clean three
     * times, not a harmonic's jump, at 0.4 x its level: its let-go rule, which a let-go's lower fret, read clean,
     * does not pass) the note moves with it, no attack.
     * SY test 20: a pluck owes an attack (yowe) until it has one. Its first voiced reading from silence starts the
     * note, unless it reads the note before within Y_OLD of the pluck (that string ringing into the analysis: 16th
     * notes on the take's model started the note before again, then slid); over a note sounding, a reading of another
     * note takes over with an attack when clean (an octave, a fifth or a fourth off only twice: YIN's own slips) or
     * read twice, a semitone too (test 19 wanted its band sounding: the tracker's lock came first, a glide). The
     * tracker's note-on for the pluck (its seq moves: the same note too, a re-pick its level rule passed) attacks if
     * the pluck has not; after that its note-ons move the note, no attack, as test 19's. */
    const u32 yv = yrun && (kn->yflag & 1u) ? kn->ynote : 0u;   /* this block's voiced analysis' note + 1 */
    if (yrun && s->ysyn && !kn->ysyn) {                /* SY test 20: the tracker let go (its level fell fast: a hand on */
        if (n->gate && n->band + 41 == (s32)s->ysyn) {   /* the string; or long unvoiced): its note ends (test 19 */
            n->gate = 0;                               /*   rang on while its band did: a let-go note's held band */
            n->ypend = 0;                              /*   made a new pick's attack double) */
            n->rel = blk;
            n->fast = (u8)(blk - n->born < B_AGE);
        }
        s->yowe = 0;                                   /* a pluck's lock as a let-go (the level fell after it) */
    }
    if (yrun && kn->yseq != s->yseq) {
        const s32 k = (s32)kn->ysyn - 1 - 40;
        const u32 sounding = n->gate && n->band >= 0;
        s->yseq = kn->yseq;
        if (kn->ysyn && k >= 0 && k < SYV_BANDS) {
            if (s->yowe) {                             /* SY test 20: its pluck's note, not attacked yet */
                if (p->retrig || !sounding) {
                    y_start(n, k, tg, rc, e, blk, lm);
                } else if (k != n->band) {             /* a legato tone: the pitch moves (glide), no attack */
                    y_move(n, k, on, tg, rc, e, blk);
                }
                s->yowe = 0;
                s->yact = 2;
            } else if (k != n->band || !sounding) {
                if (sounding) {
                    y_move(n, k, on, tg, rc, e, blk);  /* legato: the pitch moves (glide), no attack */
                } else if (kn->ysince <= Y_WIN + Y_WIN) {   /* a pluck's note the readings missed: it starts */
                    y_start(n, k, tg, rc, e, blk, lm);
                }
                if (kn->ysince <= Y_WIN) s->yact = 2;
            }
        }
    }
    s->ysyn = kn->ysyn;
    if (yv) {
        const s32 k = (s32)yv - 1 - 40;
        const u32 clean = (kn->yflag & 2u) != 0u, twice = yv == s->yprev;
        const u32 sounding = n->gate && n->band >= 0;
        const s32 d = k - n->band;
        if (k < 0 || k >= SYV_BANDS) {
        } else if (kn->ysince >= Y_PRE && kn->ysince <= Y_WIN) {
            if (s->yowe) {
                if (!sounding) {
                    if (yv != s->yold || kn->ysince >= Y_OLD) {   /* SY test 20: not the string before */
                        y_start(n, k, tg, rc, e, blk, lm);
                        s->yowe = 0;
                        s->yact = 1;
                    }
                } else if (d != 0 && (twice || (clean && !y_odd(d)))) {
                    if (p->retrig) {
                        y_start(n, k, tg, rc, e, blk, lm);
                    } else {                           /* a legato tone: the pitch moves (glide), no attack */
                        y_move(n, k, on, tg, rc, e, blk);
                    }
                    s->yowe = 0;
                    s->yact = 1;
                }
            } else if (s->yact == 1u && clean && sounding && d != 0 && d <= Y_FIX && -d <= Y_FIX) {
                y_move(n, k, on, tg, rc, e, blk);      /* a first reading a semitone or two off: put right */
                s->yact = 2;
            } else if (clean && sounding && k == n->band) {
                n->yat = blk;                          /* read again: its band may come yet */
            }
        }
    }
    if (yrun && (kn->yflag & 1u)) s->yprev = (u8)yv;    /* an analysis: its note (+ 1), 0 if not voiced */
    s32 best = -1;                                     /* the loudest band begun lately (M_YOUNG), every block; SY */
    const u32 sounding = n->gate && n->band >= 0;      /*   test 18: over a note, none over a band struck lately */
    for (u32 k = 0; k < SYV_BANDS; k++) {
        if (!on[k] || s->run[k] < wait + 1u || s->run[k] > M_YOUNG || (s32)k == n->band) continue;
        if (sens > 0.0f && tg[k] < sens * s->pkh) continue;
        if (sounding && over_struck(struck, e, (s32)k)) continue;
        if (best < 0 || tg[k] > tg[best]) best = (s32)k;
    }
    /* SY test 19: with the tracker's notes the bands decide only what it left: a pluck it found no note for in Y_WIN
     * (a soft string under a loud one: they take the note over). A note starts only on the tracker's pluck (on the
     * take the bands' own starts after a let-go were its lower fret, struck by the finger leaving it). */
    if (best >= 0 && yrun && (!sounding || kn->ysince <= Y_WIN || n->ypend || s->yact)) best = -1;
    if (best >= 0) {
        const u32 picked = since <= (u32)s->run[best] + B_WIN;   /* a pick no more than B_WIN before it began */
        const u32 conf = s->run[best] >= B_CONF && blk >= 4 && absf(rc[best] - rc4[best]) < STABLE;   /* settled */
        const u32 lv = picked ? tg[best] >= M_PICK * s->pkh : onm[best] != 0u;   /* SY test 19: loud enough */
        const u32 hit = picked || (!pickg && s->onset[best] && conf);   /* SY test 18: or an onset of its own, */
        if (!n->gate || n->band < 0) {                                 /*   settled (a mute's click strikes many */
            if ((hit && lv) || tg[best] >= B_LOUD * s->pkh)   /* from silence: on a pick, or loud (a pick unseen) */
                b_start(n, best, tg, rc, e, blk, hit);
        } else {
            const float cur = b_level(n, tg);
            s32 d = best - n->band;
            u32 hand = (d == 1 || d == -1) && absf(rc[best] - n->r) < B_HAND;
            const u32 newer = !on[n->band] || s->run[best] < s->run[n->band];   /* test 18: begun after the note's */
            const float now = on[n->band] ? tg[n->band] : 0.0f;   /* test 18: the note's band now (0: let go) */
            const u32 strum = (blk - (s32)s->run[best]) - n->took >= B_STRUM;   /* test 18: begun B_STRUM after */
            const u32 newest = !pickg && s->onset[best] && newer && conf && strum &&   /* test 18: the newest */
                               tg[best] >= (guard ? B_NEW_G : B_NEW) * now;           /*   string */
            if (hand && lv) {                          /* its partial moving on */
                n->band = (signed char)best;
                n->off = 0;
            } else if (lv && (picked ? tg[best] >= B_TAKE_P * cur
                                     : newest || (!pickg && tg[best] >= (guard ? B_TAKE_G : B_TAKE) * cur))) {
                u32 young = blk - n->born < G_FIX;     /* the pick's first band was a blip: it moves, no second */
                if ((picked || newest) && !young && p->retrig) {   /*   attack (test 18: a newest string's too) */
                    b_start(n, best, tg, rc, e, blk, 1u);
                } else {
                    n->band = (signed char)best;       /* legato: the pitch moves (glide), no attack */
                    n->took = blk;                     /* SY test 18 */
                    n->off = 0;
                    n->c = rc[best];
                    n->r = rc[best];
                    n->last = tg[best];
                    n->elast = e[best];
                    n->peak = maxf(n->peak, tg[best]);
                    n->glide = 1;
                }
            }
        }
    }
    s32 k = n->band;
    if (k >= 0 && n->gate && on[k]) {
        if (n->ypend) {                                /* SY test 19: the tracker's note's band sounds: its own level */
            n->ypend = 0;                              /*   from here (the voice's velocity kept) */
            n->peak = tg[k];
        }
        n->off = 0;
        n->r = rc[k];
        n->c = rc[k];
        n->last = tg[k];
        n->elast = e[k];
        if (n->young) {
            n->peak = maxf(n->peak, tg[k]);
            if (blk - n->start >= PROB && tg[k] >= PROB_HOLD * n->peak && blk >= 4 && absf(rc[k] - rc4[k]) < STABLE)
                n->young = 0;
        } else {
            /* SY test 20: not with the tracker's notes (its plucks attack): a new pick's ring in the band of a note
             * let go struck that note again before the new one came (5 of 8 staccato notes had two attacks) */
            if (!yrun && repick(n, tg[k], blk) && since <= B_REPICK) {
                n->trig = 1;
                n->start = blk;
                n->peak = tg[k];
            }
            if (blk - n->start < 12) n->peak = maxf(n->peak, tg[k]);
        }
        n->lev = minf(1.0f, tg[k] / maxf(n->peak, 1e-9f));
    } else if (k >= 0 && n->gate && n->ypend) {
        n->lev = 1.0f;                                 /* SY test 19: waiting for its band: as loud as the pick */
        n->peak = maxf(n->peak, lm);
    }
    (void)vref;
    (void)c;
}

/* SY test 18, LAW: the voice's level x this for its band k. The SY-1000's per-voice volume (DSP row b47e, decoded
 * 2026-11-07) gives a band at a fraction r of the loudest of its five bands (k-2..k+2) r^2 of that one's volume, under
 * either reading of its divide step; the readings differ in how the volume follows the playing. 1, SY 1:1: x r (the
 * band's level over the five's loudest; levels are sqrt(2 x energy), so r = sqrt(e[k] / max e)): the volume follows
 * the guitar dB for dB. 2, SY 2:1: x the band's level over half a full pick's (vref / 2, at most LAW_MAX): a square
 * law, 2 dB of synth a dB of guitar, its neighbours' r^2 coming from the square itself (SY test 19: half; test 18's
 * full pick left it "too quiet to use" on the unit: a medium pick now plays as LAW OFF). 0: x 1 (test 17's levels).
 */
static inline float law_factor(u32 law, const syv_note_t *n, s32 k, const float *tg, const float *e, float vref) {
    if (law == 1u) {
        float m = 0.0f;
        for (s32 j = k - 2; j <= k + 2; j++)
            if (j >= 0 && j < SYV_BANDS && e[j] > m) m = e[j];
        return m > 0.0f && e[k] < m ? __builtin_sqrtf(e[k] / m) : 1.0f;
    }
    if (law == 2u) return minf(LAW_MAX, 2.0f * b_level(n, tg) / vref);
    return 1.0f;
}

/* the voices' word: gate, pitch, velocity, level, a young voice's confidence (its band's own level), the attack,
 * the soft start, the glide; SY test 18: LAW's factor */
SYV_NOTES static void to_voices(syv_state_t *s, const syv_patch_t *p, const float *tg, const float *e, float vref,
                                ctl_t *c, u32 nv, u32 law) {
    for (u32 v = 0; v < SYV_NV; v++) {
        syv_note_t *n = &s->n[v];
        c->trig[v] = 0;
        c->soft[v] = 0;
        c->glide[v] = 0;
        c->gate[v] = 0.0f;
        c->conf[v] = 1.0f;
        c->fast[v] = v >= nv;
        c->freq[v] = 0.0f;
        c->vel[v] = 0.05f;
        c->lev[v] = 1.0f;
        c->law[v] = 1.0f;
        if (v >= nv || n->band < 0) continue;
        c->law[v] = law_factor(law, n, n->band, tg, e, vref);
        s32 k = n->band;
        c->trig[v] = n->trig;
        c->soft[v] = n->soft;
        c->glide[v] = n->glide;
        c->gate[v] = n->gate ? 1.0f : 0.0f;
        c->freq[v] = 440.0f * syv_exp2(n->c * (1.0f / 1200.0f));
        c->vel[v] = velocity(n->peak, vref);
        c->lev[v] = n->lev;
        c->fast[v] = n->fast;
        if (n->young && !p->mono) {                    /* a young voice at its band's own level (test 11's) */
            if (n->gate && tg[k] > 0.0f) {
                float vs = (1.0f - p->avel) + p->avel * c->vel[v];
                float a = minf(1.0f, syv_exp2(0.7f * syv_log2(maxf(tg[k], 1e-12f) / vref)));
                n->cf = minf(1.0f, a / maxf(vs, 0.05f));
            }
            c->conf[v] = n->cf;
        }
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
    float *gab = s->gab, *gfb = s->gfb;
    {                                                  /* SY test 17: the pick's envelopes, every voice's */
        u32 st = s->gastg, fst = s->gfstg;
        float ga = s->ga, gf = s->gf;
        u32 strike = 0u, soft = 0u;                    /* SY test 18: a voice starting with an attack / softly */
        for (u32 v = 0; v < nv; v++) {
            if (c->trig[v]) strike = 1u;
            else if (c->soft[v]) soft = 1u;
        }
        const u32 fresh = s->blk - s->gat > B_WIN;     /* test 18: no (re)start lately (a pick's blips start none) */
        const u32 ylead = s->ymono && p->mono;         /* SY test 19: the tracker's notes: they start on its note */
        if ((ylead ? strike : s->pick || (strike && fresh)) || (st == 0u && s->anygate)) {   /* a pick (test 18: or */
            st = 1;                                    /*   a pick the detector missed); or a band before any pick */
            fst = 1;                                   /*   since the start (the synth or the tone came on with a */
            s->gat = s->blk;                           /*   string ringing) */
        } else if (soft && st == 4u) {                 /* test 18: a string after the release, no attack: they open */
            st = 1;                                    /*   again (test 17 left it silent): the amp as the tone's, */
            fst = 3;                                   /*   the filter at its sustain, no sweep */
            gf = flt == 6u ? pr[6] : p->fsus;
            s->gat = s->blk;
        } else if (!s->anygate && (ylead || s->since > B_WIN) && st > 0u && st < 4u) {   /* no band, and no pick */
            st = 4;                                                            /*   pick's band may still be coming) */
            fst = 4;
        }
        for (u32 i = 0; i < SYV_FRAMES; i++) {
            if (flt == 6u) {
                if (preset == 0u) {
                    if (st == 4u) ga = maxf(0.0f, ga - 1.0f / 400.0f);
                    else if (st) ga = 1.0f;
                } else {
                    ENV_STEP(ga, st, pr[0], pr[1], pr[2], pr[3]);
                }
                if (has_pf) ENV_STEP(gf, fst, pr[4], pr[5], pr[6], pr[7]);
            } else {
                ENV_STEP(ga, st, 1.0f - p->aa, p->ad, p->asus, p->ar);
                ENV_STEP(gf, fst, 1.0f - p->fa, p->fd, p->fsus, p->fr);
            }
            gab[i] = ga;
            gfb[i] = gf;
        }
        s->ga = ga;
        s->gf = gf;
        s->gastg = (u8)st;
        s->gfstg = (u8)fst;
    }
    for (u32 v = 0; v < nv; v++) {
        syv_voice_t *x = &s->v[v];
        if (c->trig[v] || c->soft[v] || (s->guard && c->gate[v] > 0.0f && !x->active)) {   /* test 17: soft too */
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
                x->lawf = c->law[v];                    /* test 18 */
                x->lit = 0;                             /* test 16: not rendered yet */
            }
            x->soft = c->soft[v];                       /* test 17: no pick: its gate rises gently, its strike spent */
            if (x->soft) {
                x->m1 = 0.0f;
                x->m2 = 0.0f;
            }
            x->gl = 0;
            x->active = 1;
        } else if (s->guard && c->gate[v] > 0.0f && x->astg == 4u) {   /* test 15: GUARD: back after a gap, no attack */
            x->astg = 1;
        }
        if (s->pick && x->active && !(s->ymono && p->mono)) {   /* test 17: the pick strikes every voice (FM) */
            x->m1 = 1.0f;
            x->m2 = 1.0f;
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
        if (c->glide[v]) x->gl = 1;                    /* test 17: glide only to a new note (mono's legato) */
        float f1 = ft;
        if (x->gl && g64 > 0.0f) {
            f1 = ft + (x->f - ft) * g64;
            if (absf(f1 - ft) < 0.0006f * ft) x->gl = 0;
        } else {
            x->gl = 0;
        }
        x->phl = x->phl + p->lfo_inc * 64.0f;
        x->phl = x->phl - floorf_(x->phl);
        float ld = (x->t + 32.0f) * p->lfo_dk;
        const float lfo = syv_sin(x->phl) * (ld < 1.0f ? ld : 1.0f);
        const float conf1 = x->conf + (c->conf[v] - x->conf) * 0.2263f;   /* 1 - (1 - 0.004)^64 */
        const float lev1 = x->lev + (c->lev[v] - x->lev) * 0.1203f;       /* 1 - (1 - 0.002)^64 */
        const float law1 = x->lawf + (c->law[v] - x->lawf) * 0.1203f;     /* SY test 18: LAW's factor, the same */
        const float vs = (1.0f - p->avel) + p->avel * x->vel;
        const float lvl = vs * (1.0f + p->lfo_amp * lfo);
        const float k0 = lvl * ((1.0f - p->follow) + p->follow * x->lev) * x->conf * x->lawf;
        const float k1 = lvl * ((1.0f - p->follow) + p->follow * lev1) * conf1 * law1;
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
                float fe = gfb[0], fs = gfb[SYV_FRAMES - 1];   /* test 17: the pick's filter envelope */
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
            const float vatt = x->soft ? AM_SOFT : AM_QUICK;   /* test 17: the voice's gate */
            const float sgf = x->f * p->octm * (1.0f / FS);
            float c1 = x->c1, c2 = x->c2, c3 = x->c3;
            u32 tick = x->tick;
            for (u32 i = 0; i < SYV_FRAMES; i++) {
                if (preset == 0u && astg == 4u) {
                    aenv = aenv - (x->fast ? 1.0f / 144.0f : 1.0f / 400.0f);
                    if (aenv <= 0.0f) {
                        alive = 0;
                        n = i;
                        break;
                    }
                } else {
                    ENV_STEP(aenv, astg, vatt, 1.0f, 1.0f, cr);   /* test 17: the voice's gate */
                    if (astg == 4u && aenv < 1e-5f) {
                        alive = 0;
                        n = i;
                        break;
                    }
                }
                float y = buf[i];
                if (has_pf) {
                    fenv = gfb[i];                     /* test 17: the pick's */
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
                    float yy = v2 * pr[12] * (aenv * gab[i]);
                    float a = absf(yy);
                    if (a > 0.6f) {
                        float u = (a - 0.6f) * 2.5f;
                        float sv = 0.6f + 0.4f * u / (1.0f + u);
                        yy = yy < 0.0f ? -sv : sv;
                    }
                    y = yy;
                } else {
                    y = y * (aenv * gab[i]);
                }
                acc[i] = acc[i] + y * k;
                k = k + dk;
            }
            x->c1 = c1;
            x->c2 = c2;
            x->c3 = c3;
            x->tick = tick;
        } else {
            const float vatt = x->soft ? AM_SOFT : AM_QUICK;   /* test 17: the voice's gate; the envelopes the pick's */
            float a1 = 0.0f, a2 = 0.0f, a3 = 0.0f, G = 0.0f, kd = 0.0f, kf = 0.0f, comp = 1.0f;
            if (flt) {                                 /* the block's coefficients */
                float kt = p->keytrk != 0.0f ? syv_exp2(p->keytrk * syv_log2(maxf(fb, 1.0f) * (1.0f / 261.63f)))
                                             : 1.0f;
                float fe = p->fenv * gfb[0] * ((1.0f - p->fvel) + p->fvel * x->vel);
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
                ENV_STEP(aenv, astg, vatt, 1.0f, 1.0f, cr);   /* test 17: the voice's gate */
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
                acc[i] = acc[i] + y * (aenv * gab[i]) * k;
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
        x->lawf = law1;                                 /* SY test 18 */
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
                         const float *per, const float *e, const u8 *struck, float vref, float mg, float mgt, float fade,
                         float scale, s32 *out) {
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
    for (u32 b = 0; b < SYV_BANDS; b++) {              /* SY test 18: onsets (struck in a band's first M_YOUNG */
        if (!(tg[b] > 0.0f)) s->onset[b] = 0;          /*   blocks; kept while it sounds) */
        else if (s->run[b] <= M_YOUNG && struck[b]) s->onset[b] = 1;
    }
    knobs(s, tone, k);
    const syv_patch_t *p = &s->eff;
    float *rc = s->rc;
    for (u32 b = 0; b < SYV_BANDS; b++)
        rc[b] = cents_of_period(per[b]);
    ctl_t *cp = &s->ctl;
    u32 cap = p->flags & 0x0Fu;                      /* the tone's voice cap (flags' low bits) */
    u32 nv = p->mono ? 1u : cap && cap < SYV_NV ? cap : SYV_NV;
    if (p->mono) bands_mono(s, p, tg, rc, e, struck, vref, cp, k);   /* SY test 17: the bands, no notes */
    else bands_poly(s, p, tg, rc, e, vref, cp, nv, k);
    to_voices(s, p, tg, e, vref, cp, nv, k->law <= 2u ? k->law : 0u);   /* SY test 18: LAW */
    s->pick = k->since == 0u;                          /* SY test 17: the pick's envelopes */
    s->since = k->since;
    s->anygate = 0;
    for (u32 v = 0; v < nv; v++)
        if (cp->gate[v] > 0.0f) s->anygate = 1;
    float *acc = s->acc;
    for (u32 i = 0; i < SYV_FRAMES; i++)
        acc[i] = 0.0f;
    s->cost = render(s, p, cp, acc, nv);
    mg = output(s, acc, p->gain, mg, mgt, fade, scale, out);
    float *slot = s->rc_prev[s->blk & 3];             /* this block's readings, for four blocks on */
    for (u32 b = 0; b < SYV_BANDS; b++)
        slot[b] = rc[b];
    s->blk++;
    return mg;
}
