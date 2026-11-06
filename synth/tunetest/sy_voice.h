/* SY synth test 11: a synth voice per note (sy_voice.c). The SY band engine (sy_fp.c) finds the notes; this turns
 * its sounding bands into notes (a note manager) and gives each note a voice of its own: up to three oscillators (band-
 * limited saw and pulse, triangle, sine, the Sound Generator's 32 waves, a seven-saw supersaw, two-modulator FM), a
 * filter with its own envelope (12 dB state-variable, 24 / 18 dB ladder, or the Sound Generator's ENV preset filter),
 * an amp envelope, an LFO, glide. No effects: the output is mono and dry, for the SP's own bus effects (the user's
 * choice: chorus and the rest from BUS 1 / BUS 2). Portable C (no libm, single precision, no fused operations but the
 * output stage's one, as sy_fp.c's): the module runs it on the SP, and a host build of the same file renders the demos
 * and checks it. */
#ifndef SY_VOICE_H
#define SY_VOICE_H

#ifndef SYV_TYPES
#define SYV_TYPES
typedef unsigned int syv_u32;
typedef int syv_s32;
typedef unsigned char syv_u8;
typedef signed char syv_s8;
#endif

#define SYV_NV 6                     /* voices (SY test 17: one a band, 6: a chord; a tone may cap them) */
#define SYV_BANDS 49
#define SYV_FRAMES 64

/* A tone (generated from sy_voices.py's VOICES; coefficients per sample at 48 kHz). */
typedef struct {
    syv_u8 kind[3];                  /* 0 off, 1 saw, 2 pulse, 3 triangle, 4 sine, 5 supersaw, 6 SG wave, 7 FM */
    syv_u8 wave[3];                  /* the Sound Generator wave (kind 6) */
    syv_u8 flt;                      /* 0 none, 1 LP 12 dB, 2 BP, 3 HP, 4 LP 24 dB ladder, 5 LP 18 dB, 6 SG preset */
    syv_u8 preset;                   /* the Sound Generator ENV preset (flt 6) */
    syv_u8 mono, retrig, chorus, sync;   /* chorus: unused (the SP's bus effects) */
    syv_u8 p2kind, flags, pad[2];
    float ratio[3], lev[3], pw[3], duty[3];
    float penv, sub, noise, ring, spread, mix;
    float fm_ratio, fm_index, fm_floor, fm_dk, fm2_ratio, fm2_index, fm2_dk;
    float cut, keytrk, reso, fenv, fvel, drive;
    float fa, fd, fsus, fr, aa, ad, asus, ar;
    float avel, follow;
    float lfo_inc, lfo_dk, lfo_pitch, lfo_cut, lfo_pw, lfo_amp, lfo_vec;
    float glide, gain, octm;
    float p2base, p2span;
} syv_patch_t;

/* The screen's settings for the tone playing: CTRL 1-3 as knob position - 64 (0: as designed), OCTAVE (0 as designed,
 * 1..5: -2..+2), SUSTAIN and DYNAMICS (0 as designed, 1..101: 0..100). SY test 15: the TRACK page's, for every tone:
 * WAIT (0..12: the blocks a band sounds before it is a new note), SENS (0..50: a new note's least level, % of the
 * loudest band) and GUARD (0 off, 1 on); 0 each is test 11's tracking. */
typedef struct {
    syv_s8 tone, p2, level;
    syv_u8 oct, sus, dyn, wait, sens, guard, since, pad[2];   /* SY test 16: GUARD 2 = PICK; since: blocks since
                                                               the input's last pick (255: long ago) */
} syv_knobs_t;

/* P2 kinds (CTRL 1): what it moves */
enum {
    SYV_P_NONE, SYV_P_RESO, SYV_P_ENV, SYV_P_ATTACK, SYV_P_DETUNE, SYV_P_GLIDE, SYV_P_DUTY, SYV_P_DRIVE, SYV_P_RATE,
    SYV_P_MIX, SYV_P_FM, SYV_P_ENVSEL
};

typedef struct {
    float ph[3], phs, phm, phm2, uph[7], phl;
    float f, aenv, fenv, y[4], ic1, ic2, g, c1, c2, c3, t, vel, lev, conf, m1, m2, rnd, sgprev;
    syv_u32 ns, tick;
    syv_u8 astg, fstg, active, fast, lit, soft, gl, pad;   /* lit: SY test 16, rendered since its start; soft,
                                                       gl: test 17, a start without a pick, gliding to a new note */
} syv_voice_t;

typedef struct {
    float peak, c, r, lev, hist[9];
    float last;                      /* SY test 15: its band's last level (GUARD) */
    float elast;                     /* SY test 16: its band's last energy (mono's ride) */
    float cf;                        /* SY test 17: its confidence while young */
    syv_s32 start, rel, rp, born;    /* born: SY test 17, the block its band began */
    syv_s8 band;
    syv_u8 gate, off, young, fast, nh, trig, soft, glide;   /* soft, glide: SY test 17 */
} syv_note_t;

typedef struct {                     /* the note manager's word to the voices, per block */
    float gate[SYV_NV], freq[SYV_NV], vel[SYV_NV], lev[SYV_NV], conf[SYV_NV];
    syv_u8 trig[SYV_NV], fast[SYV_NV], soft[SYV_NV], glide[SYV_NV];   /* soft, glide: SY test 17 */
} syv_ctl_t;

typedef struct {
    syv_voice_t v[SYV_NV];
    syv_note_t n[SYV_NV];
    float rc_prev[4][SYV_BANDS];     /* the readings of the last four blocks, in cents (settling) */
    syv_u8 run[SYV_BANDS];           /* SY test 15: the blocks each band has sounded in a row (WAIT) */
    syv_u8 started, guard, pad;      /* guard: GUARD, this block (the voices' resume) */
    float pkh;                       /* SY test 16: the held peak of the loudest band (-20 dB in 0.6 s): SENS's level */
    float ga, gf;                    /* SY test 17: the pick's amp and filter envelopes (every voice's) */
    syv_u8 gastg, gfstg, pick, anygate;   /*   their stages; a pick this block; a voice's band sounding */
    syv_u8 since, gpad[3];           /*   blocks since the input's pick (255: long ago) */
    syv_s32 blk;
    float dcx, dcy;
    syv_u32 cost;                    /* voices rendered in the last block */
    syv_patch_t eff;                 /* the tone with its settings, this block */
    float pre[14];                   /* its ENV preset with SUSTAIN (flt 6) */
    /* the block's work (here, not on the tracker's 2 KB stack) */
    float acc[SYV_FRAMES], buf[SYV_FRAMES], rc[SYV_BANDS];
    float gab[SYV_FRAMES], gfb[SYV_FRAMES];   /* SY test 17: the pick's envelopes over the block */
    syv_ctl_t ctl;
} syv_state_t;

/* One block: the bands' levels (tg, 0 = not sounding), periods (12 kHz samples), energies and periods counted since
 * each woke (nper; SY test 12, unused since test 15); vref the level a full pick reads. The output stage (as sy_fp.c's before): the soft clip (1.5x - 0.5x^3, +-1 beyond), the fade (mg towards
 * mgt by `fade` a sample) and x `scale` to out (truncated). Returns the fade. */
float syv_block(syv_state_t *s, const syv_patch_t *tone, const syv_knobs_t *k, const float *tg, const float *per,
                const float *e, const syv_u8 *nper, float vref, float mg, float mgt, float fade, float scale,
                syv_s32 *out);
void syv_reset(syv_state_t *s);

#endif
