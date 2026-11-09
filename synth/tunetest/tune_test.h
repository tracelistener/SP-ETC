/* Note tracker test: what the integer side (tune_test.c: the meter, the UI, the RX hook) and the FPU side
 * (tune_fp.c: the tracker) share. */
#ifndef TUNE_TEST_H
#define TUNE_TEST_H

typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;
typedef signed char s8;

#define FRAMES 64u                          /* frames an RX block (48 kHz) */
#define STACK_BYTES 1792u                   /* the FPU side's own stack (tune_fp_call; SY test 28: was 2,048, the suite's
                                               deepest use 1,164 with FP_SAVED, an interrupt's frame at most 108 more) */
#define FP_SAVED 176u                       /* SY test 21: what tune_fp_call and sy_fp_call keep under its top: the
                                               caller's r4-r11, sp and lr, its FPSCR and a pad, d0-d15 */
#define TT_RING 512u                        /* the input at 12 kHz: 42.7 ms */
#define TT_W6 100u                          /* the analysis at 6 kHz: window, lags 1..TT_T6MAX */
#define TT_T6MIN 4u                         /* 1,500 Hz */
#define TT_T6MAX 100u                       /* 60 Hz */
#define TT_W12 200u                         /* the refinement at 12 kHz: window */
#define TT_SPAN (TT_W12 + 2u * TT_T6MAX + 4u)   /* the newest samples an analysis reads */
#define TT_EVERY 2u                         /* SY test 24: an analysis every 2 blocks (2.7 ms) on the newest samples, all
                                               its lags at once (tests 1-23: every 4 blocks, 25 lags a block on a span
                                               taken 3 blocks before its decision: about 5 ms later on every string) */
#define TT_PEAKS 32u                        /* block peaks kept for the pluck test */
#define TT_BASE (TT_W12 + 2u * TT_T6MAX + 8u)   /* test 6: the samples before a pluck kept for the refinement */

/* tt.state, written by the audio task only */
enum {
    TT_OFF = 0,                             /* not running; the UI may clear the block */
    TT_RUN,                                 /* a tracker step every RX block */
    TT_SLOW                                 /* too slow: stopped */
};

/* What the readout shows; the FPU side writes it (tt.rseq odd while it does). */
typedef struct {
    s32 note;                               /* the steady note (MIDI), -1 none */
    s32 cents;                              /* the newest analysis against its nearest note */
    u32 freq10;                             /* the newest analysis' frequency x 10 */
    u32 quality;                            /* 100 - its aperiodicity x 100 */
    u32 voiced;                             /* the newest analysis found a note */
    u32 first_ms, lock_ms;                  /* the last pluck: to the first estimate, to the steady note */
    u32 onsets, locks, lock_sum, lock_min, lock_max;   /* plucks and steady notes since the readout came on */
    u32 analyses;
} tt_result;

typedef struct {
    u32 blocks, avg, max, tot_max;          /* cycles: the tracker per RX block, worst mixer + tracker in one wake */
} tt_window;

typedef struct {
    /* written by the UI task */
    volatile u32 req;                       /* 1: run the tracker; 0: stop */
    u32 fx, ext, routing, checked, checks, starts;  /* input FX, EXT SOURCE, ROUTING (0 Mix, 1 ExtIn), last check
                                                       (cycle count), checks made */
    u32 posted_rseq;                        /* the result the readout last showed */
    /* written by the audio task */
    volatile u32 state;
    u32 rx, steps, task_attr, last_mix;
    u32 peak[2];                            /* RX pairs 0 and 1: peak |sample| (the UI clears them per readout) */
    s16 in[FRAMES];                         /* this block for the FPU side: pair 0, (L + R) / 2 */
    u32 w_n, w_sum, w_max, w_tot;           /* the window being collected */
    volatile u32 seq;                       /* odd while pub is written */
    tt_window pub;
    u32 tot_max_ever, over, slow_cycles;    /* since the readout was switched on: worst wake, wakes over a block;
                                               the wake (mixer + tracker) that stopped it */
    u32 hot;                                /* wakes in a row over 90% of a block */
    u32 reset_req, reset_ack;
    volatile u32 rseq;                      /* odd while res is written */
    tt_result res;
    volatile u32 syn;                       /* the synth note, for the UI (syn_ui): seq << 16 | velocity << 8 |
                                               (note + 1), 0 none; the audio task writes it whole, and a note-on
                                               bumps seq */
    volatile u32 drum;                      /* syn_ui: the kits' drum mode is on (only plucks play notes there) */
    /* SY test 4 (UI task): the effects chip held on ExtIn while a synth listens to pair 0, so ROUTING can stay on
     * Mix; and what the recorder gets meanwhile */
    volatile u32 hold;                      /* 1: every ROUTING DT1 goes out as ExtIn (sy_route_dt1) */
    u32 hold_at;                            /* the hold's send (cycle count): the synths listen 20 ms after */
    volatile u32 rec_mix;                   /* the recorder's pair 0 := pair 1 x 2 (ROUTING Mix while held, and 30 ms
                                               after: the mix before BUS 3/4) */
    volatile u32 rec_ext;                   /* the synth added to the recorder's pair 0 (ROUTING ExtIn while held) */
    u32 grace, grace_at;                    /* rec_mix after the release, from when */
    u32 holds, route_sends, route_held, route_last;   /* hold starts; ROUTING DT1s seen, sent as ExtIn; the last value */
    u32 rec_blocks, rec_adds, rec_other;    /* blocks given pair 1, given the synth, left as the feed took another pair */
} tt_t;

/* The tracker's memory, in the module. The UI clears it before a start. */
typedef struct __attribute__((aligned(32))) {
    float ring[TT_RING];                    /* the low-passed input at 12 kHz */
    float span[TT_SPAN];                    /* an analysis' newest samples, newest first */
    float d6[TT_T6MAX + 1];                 /* the difference function at 6 kHz, lags 1..TT_T6MAX (SY test 28: its
                                               normalisation, dn6, is on the stack: decide()'s dn) */
    float peaks[TT_PEAKS];                  /* the blocks' peaks at 12 kHz */
    float z[2][2];                          /* the low-pass's two biquads (transposed direct form II) */
    u32 started, w, blk;                    /* ring writes, blocks */
    s32 last_onset, onset_blk, prev_note;
    u32 first_pending, lock_pending, agree, unvoiced;
    s32 syn_note;                           /* the synth note last sent (tt.syn), -1 none */
    u32 syn_sends;                          /* tt.syn writes since the start */
    float pluck_ref;                        /* the last pluck's reference: the highest peak of the 21 ms before it */
    u32 syn_strays;                         /* plucks heard while the synth played whose level did not rise */
    float voiced_level;                     /* the newest 4 blocks' peak at the last voiced analysis */
    u32 syn_holds;                          /* analyses the synth held its note through, unvoiced but not quieter */
    float pick_peak;                        /* the highest block peak from the last pluck to its steady note */
    u32 pluck_click;                        /* the last pluck clicked (a pick's highs; a thump has none) */
    u32 clicks;                             /* plucks only the click test heard */
    u32 murky;                              /* voiced analyses too murky to count (strings ringing together) */
    float zh[2];                            /* the click's 2 kHz high-pass (transposed direct form II) */
    float hfe[TT_PEAKS];                    /* the blocks' energy over 2 kHz */
    /* test 6 */
    float env;                              /* the level: a peak follower falling with a 0.3 s time constant */
    u32 sub_lock;                           /* the synth's note came from the subtraction (held through murk) */
    u32 stops, drops, sub_locks, blocked;   /* plucks whose level fell (let-gos), fast drops let go, notes the
                                               subtraction found, moves too quiet to play */
    u32 ycode;                              /* SY test 19: the newest analysis for the SY engine's mono tones: its
                                               nearest note (0..126) | 0x100 voiced | 0x200 clean (was padding) */
    float d_base[TT_T6MAX + 1];             /* the last difference function whose samples came before the pending
                                               pluck (SY test 27: copied from d6, which keeps the last analysis' until
                                               the next; d_last and dsub, 808 bytes, gone: the subtraction is
                                               normalised in place, now in decide()'s dn) */
    float base_x[TT_BASE];                  /* the 12 kHz samples before the pending pluck, newest first */
    float zh6[2];                           /* SY test 25: the soft click's 6 kHz high-pass, */
    float hf6[TT_PEAKS];                    /*   the blocks' energy over 6 kHz */
    s32 old_at;                             /* SY test 27: the block the synth's note was last read steady */
    u32 move_quick;                         /*   the last note-on a quick move (a fret change, for the SY voices) */
    u32 stack[STACK_BYTES / 4] __attribute__((aligned(8)));   /* stack top = &stack[STACK_BYTES / 4], 8-byte aligned */
} tt_block_t;
_Static_assert((__builtin_offsetof(tt_block_t, stack) & 7u) == 0, "the FPU side's stack must be 8-byte aligned");

extern tt_t tt;
extern tt_block_t tt_block;

/* tune_fp.c */
u32 tune_fp_call(u32 (*fn)(tt_t *), tt_t *arg, void *stack_top);
u32 tune_fp_step(tt_t *t);

/* ---- SY synth tests 1 and 2 (sy_fp.c): 49 semitone bands, oscillators each, to the DRY pair ---- */
#define SY_BANDS 49u
#define SY_SUB 16u                          /* 12 kHz samples a block */
#define SY_NTONES 20u                       /* SY test 11: the tones (sy_voices.py's VOICES) */

/* A band's constants (sy_tables.h, from sy_ref.py): b0, -a1, -a2 of both band-pass stages, the energy follower,
 * the centre period, the periods that count, the periods the band owns (12 kHz samples). */
typedef struct {
    float b0, na1, na2, lc, pc, plo, phi, olo, ohi;
} sy_band_t;

/* Test 2: a tone (sy_tables.h, from sy_ref.py's TONES). */
typedef struct {
    u32 wa, wb, fm, fmode;                  /* wave A (0 saw, 1 pulse, 2 triangle, 3 sine); wave B (0 none, else 1 +
                                               its wave); B modulates A's phase; the filter (0 LP, 1 BP, 2 HP) */
    u32 seq;                                /* the 16-step gate (bit n: step n sounds), 0 none */
    float pw, rb, lb, fm_env;               /* the pulse's edge (ramp units); B's frequency ratio; B's level (FM: the
                                               index); the index a pick adds */
    float att, rel;                         /* the band amplitude's step per block, rising and falling (1: at once) */
    float fc_lo, oct, xmax, r2;             /* the cutoff quiet, octaves at full level, at most (octaves), 1/Q */
    float fenv, fdec;                       /* octaves the pick envelope adds; its decay per block */
    float lfo_inc, vib, trem, lfo_oct;      /* the LFO's step per block (ramp units); vibrato (ratio), tremolo, cutoff
                                               (octaves) */
    float noise, gain;                      /* breath noise (x the bands' summed amplitude); the output gain */
    u32 p2kind, seqdiv;                     /* test 3: what CTRL 2 sets (sy_ref P_*); the steps a beat (4) */
    float p2base, p2span, bright;           /* test 3: CTRL 2's base value and span; CTRL 1's octaves (0) */
    u32 fund;                               /* test 5: 1: a note sounds from its lowest band only */
    float octm, roct;                       /* test 5: OCTAVE: the oscillators x octm (a power of two), rinc x 1/octm */
    float sus;                              /* test 5: SUSTAIN: a falling level's rate while the band sounds (0: none) */
    float dyn;                              /* test 6: DYNAMICS: how far a note's level follows the band's (1: all) */
} sy_tone_t;

/* sy.state, written by the audio task only */
enum {
    SY_OFF = 0,                             /* not running; the UI may clear the block */
    SY_RUN,                                 /* a step every RX block (fading out once req is 0) */
    SY_SLOW                                 /* too slow: stopped */
};

typedef struct {
    u32 blocks, avg, max, tot_max;          /* cycles: the engine per RX block, worst mixer + tracker + engine */
} sy_window;

typedef struct {
    /* written by the UI task */
    volatile u32 req;                       /* 1: run; 0: fade out and stop */
    u32 starts, stops;
    u32 reset_req;
    volatile u32 tone_req;                  /* test 2: the tone picked (test 11: SOUND 1-20: 0..19) */
    volatile u32 muted;                     /* test 2: the synth off (test 5: SOUND OFF) */
    u32 picks, taken;                       /* SOUND changes; test 5: keys 0..31 whose press was taken (and release) */
    volatile u32 bpm100;                    /* the SP's tempo for the step gate (BPM x 100), every 0.1 s */
    u32 tempo_checked;
    volatile s8 knob[SY_NTONES][3];         /* test 3: each tone's TONE, P2, LEVEL, as knob position - 64 (0: as
                                               designed) */
    u8 dirty, loaded;                       /* test 3: picks or knobs not in the file yet; the file was read */
    u8 pad3[2];
    volatile s8 oct[SY_NTONES];             /* test 5: each tone's OCTAVE: 0 as designed, 1..5 = -2..+2 */
    volatile u8 susk[SY_NTONES];            /* test 5: each tone's SUSTAIN: 0 as designed, 1..101 = 0..100 */
    volatile u8 dynk[SY_NTONES];            /* test 6: each tone's DYNAMICS: 0 as designed, 1..101 = 0..100 */
    u32 loads, saves, save_errors, bad_files;   /* test 3: the file */
    /* written by the audio task */
    volatile u32 state;
    u32 rx, steps, tx, fresh;               /* fresh: out[] holds a block TX has not added yet */
    u32 stopping;                           /* the FPU side fades out (req went 0 while it ran) */
    u32 sounding;                           /* bands sounding in the newest block */
    u32 last_mix;                           /* this wake's mixer (cycles), for the accounting */
    s32 out[FRAMES];                        /* the next block for the DRY pair, at the 16-bit stems' scale */
    u32 w_n, w_sum, w_max, w_tot;           /* the window being collected */
    volatile u32 seq;                       /* odd while pub is written */
    sy_window pub;
    u32 tot_max_ever, over, slow_cycles, hot, reset_ack;
    u32 run_steps;                          /* SY test 8: steps since this start (the first two not held to the budget) */
    /* test 5: the guitar synth screen (EXT SOURCE + RECORD SETTING: the Sound Generator page in SY mode), UI task */
    u32 mode;                               /* 0 off; 1 the screen is up (the SG page); 2 the page was asked for */
    u32 mode_at;                            /* when it was asked for (cycle count) */
    u32 rev, drawn_rev;                     /* what the columns and the footer show changed; redrawn up to */
    u32 bar_rev, bar_drawn;                 /* what the bar (PRM) shows changed; redrawn up to */
    u32 taken_hi;                           /* keys 32..63 whose press was taken (and release) */
    u32 pads_taken;                         /* pad events taken (pads 1-16, SUB PAD as bit 16): their releases too */
    u8 shift_page, shift_down, shift_used, ext_fix;   /* SHIFT tapped (the second page); SHIFT held; a knob turned
                                               while it was; EXT SOURCE's release to come (input on again after) */
    u32 enters, leaves, pads_ate, turns, vsteps;  /* the screen opened, closed; pads, knobs, VALUE steps it took */
    u32 foot, foot_vt;                      /* the footer widget last drawn on the screen, its vtable word */
    /* test 6: REMAIN on the Sound Generator page: its press taken (its held bit set as stock's would be, so REMAIN +
       an FX button freezes the FX screen); let go with no FX button pressed, the stock press and release follow (the
       preview bus) */
    u8 rem_down, rem_fx;
    volatile u8 out_bus;                    /* SY test 7: the synth's bus: 0 DRY, 1 BUS 1, 2 BUS 2, 3 both (half each) */
    volatile u8 armed;                      /* SY test 8: the synth may play: set while the screen is up, kept after
                                               EXIT, cleared once EXT SOURCE is off (not while the chord puts it back) */
    u32 rem_taps, rem_holds, fx_passes;     /* REMAIN taps handed on, REMAIN + FX freezes; events an FX screen got */
    u32 sg_page;                            /* the Sound Generator page's object (its views), from its update; 0 off it */
    /* test 4, audio task: the synth's newest block as TX added it, for the recorder on ROUTING ExtIn */
    volatile u32 rec_fresh;                 /* rec holds a block the recorder has not had */
    s16 rec[FRAMES];
    /* SY test 15, UI task: the TRACK page (SHIFT's third), for every tone: WAIT (0..12 blocks a band sounds before it
       is a new note), SENS (0..50: a new note's least level, % of the loudest band), GUARD (0/1), 0; 0 each is test
       11's tracking */
    volatile u8 trk[4];
} sy_t;

/* The engine's memory, in the module. The UI clears it before a start. Test 2: no stack of its own: the engine runs
 * on the tracker's (tt_block.stack), after the tracker's step in the same wake. */
typedef struct __attribute__((aligned(32))) {
    float dz[2][2];                         /* the 48 -> 12 kHz low-pass's two biquads */
    float xh[2];                            /* the block before's last two 12 kHz samples */
    float ua1[SY_BANDS], ua2[SY_BANDS];     /* the first band-pass stage's last two outputs */
    float yb1[SY_BANDS], yb2[SY_BANDS];     /* the second's */
    float e[SY_BANDS];                      /* the band's energy */
    float tl[SY_BANDS];                     /* its last positive crossing, from this block's start (12 kHz samples) */
    float per[SY_BANDS], trend[SY_BANDS];   /* its period (alpha-beta tracked) and the period's trend */
    float amp[SY_BANDS];                    /* SY test 11: its level while it sounds (the note manager's input) */
    u8 armed[SY_BANDS];                     /* went below -ARM x its level since the last crossing */
    u8 nper[SY_BANDS];                      /* periods counted since it woke (to 255) */
    u8 owned[SY_BANDS];                     /* sounding in the last block */
    u8 hold[SY_BANDS];                      /* test 6: blocks it sounds on after it stops owning */
    float ehold[SY_BANDS];                  /* test 6: its energy when it last owned */
    float env, mg;                          /* the input's peak follower; the fade */
    u32 tone;                               /* the tone playing */
    u32 started, blocks, crossings;
    u32 fund_cut;                           /* test 5: band-blocks FUND silenced (whole multiples of a lower band) */
    float peaks[32];                        /* SY test 16: the blocks' input peaks (test 10's pick rule) */
    s32 last_pick;                          /*   the block of the last pick */
    float es[SY_BANDS];                     /* SY test 18: the band's energy followed over about 32 blocks */
    u8 struck[SY_BANDS];                    /*   blocks left of a strike (its energy at SY_RISE x es lately) */
    u8 fresh[SY_BANDS];                     /*   a string struck at a multiple of a lower one ringing: FUND spares it
                                               while it owns */
    u8 oage[SY_BANDS];                      /*   blocks it has owned in a row (to 255) */
    u32 yan;                                /* SY test 19: the tracker's analyses seen (a new one: its word is fresh) */
    u32 mono;                               /*   the tone playing is mono: tune_ui runs the tracker for its notes */
} sy_block_t;

/* SY test 18: the crash catcher's record (section .sycrash: the top of the SY slot, which no boot row writes, so it
 * outlives the reset the fault handler asks for). */
typedef struct {
    u32 exc;                                /* the exception (IPSR: 3 HardFault, 4 MemManage, 5 BusFault, 6 Usage) */
    u32 pc, lr, psr, sp;                    /* the stacked PC, LR and xPSR; the stack the fault came from */
    u32 cfsr, hfsr, mmfar, bfar;            /* the SCB's fault status and address registers */
    u32 ret;                                /* the handler's EXC_RETURN */
    u32 blocks;                             /* the SY engine's blocks so far (sy_block.blocks) */
    u32 page;                               /* the page up */
    u32 sum;                                /* FNV-1a of the words above */
    u32 magic;                              /* CRASH_MAGIC while it holds a crash not shown yet */
} crash_t;

extern sy_t sy;
extern sy_block_t sy_block;
extern volatile crash_t sy_crash;
extern volatile u32 sy_crash_live;                 /* SY test 21: faults an FPU step came back from (the SP kept on) */

/* sy_fp.c */
u32 sy_fp_call(u32 (*fn)(sy_t *), sy_t *arg, void *stack_top);
u32 sy_fp_step(sy_t *s);
void sy_recover(void);                             /* SY test 21: a faulted FPU step's way back to its caller */

#endif
