/* Note tracker test: what the integer side (tune_test.c: the meter, the UI, the RX hook) and the FPU side
 * (tune_fp.c: the tracker) share. */
#ifndef TUNE_TEST_H
#define TUNE_TEST_H

typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;

#define FRAMES 64u                          /* frames an RX block (48 kHz) */
#define STACK_BYTES 2048u                   /* the FPU side's own stack (tune_fp_call) */
#define TT_RING 512u                        /* the input at 12 kHz: 42.7 ms */
#define TT_W6 100u                          /* the analysis at 6 kHz: window, lags 1..TT_T6MAX */
#define TT_T6MIN 4u                         /* 1,500 Hz */
#define TT_T6MAX 100u                       /* 60 Hz */
#define TT_W12 200u                         /* the refinement at 12 kHz: window */
#define TT_SPAN (TT_W12 + 2u * TT_T6MAX + 4u)   /* the newest samples an analysis reads */
#define TT_SLICE 25u                        /* lags a block: an analysis takes 4 blocks (5.3 ms) */
#define TT_PEAKS 32u                        /* block peaks kept for the pluck test */

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
    u32 fx, ext, checked, checks, starts;   /* input FX, EXT SOURCE, last check (cycle count), checks made */
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
} tt_t;

/* The tracker's memory, in the module. The UI clears it before a start. */
typedef struct __attribute__((aligned(32))) {
    float ring[TT_RING];                    /* the low-passed input at 12 kHz */
    float span[TT_SPAN];                    /* an analysis' newest samples, newest first */
    float d6[TT_T6MAX + 1];                 /* the difference function at 6 kHz, lags 1..TT_T6MAX */
    float dn6[TT_T6MAX + 1];                /* its cumulative-mean normalisation */
    float peaks[TT_PEAKS];                  /* the blocks' peaks at 12 kHz */
    float z[2][2];                          /* the low-pass's two biquads (transposed direct form II) */
    u32 started, w, blk;                    /* ring writes, blocks */
    s32 last_onset, onset_blk, prev_note;
    u32 first_pending, lock_pending, agree, unvoiced;
    u32 stack[STACK_BYTES / 4];             /* stack top = &stack[STACK_BYTES / 4], 8-byte aligned */
} tt_block_t;

extern tt_t tt;
extern tt_block_t tt_block;

/* tune_fp.c */
u32 tune_fp_call(u32 (*fn)(tt_t *), tt_t *arg, void *stack_top);
u32 tune_fp_step(tt_t *t);

#endif
