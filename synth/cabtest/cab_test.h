/* Cabinet test: what the integer side (cab_test.c: the meter, the UI, the RX/TX hooks) and the FPU side (cab_fp.c:
 * the cabinet on the captured input) share. */
#ifndef CAB_TEST_H
#define CAB_TEST_H

#include "cab.h"

typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;

#define FRAMES 64u
#define STACK_BYTES 2048u                   /* the FPU side's own stack (cab_fp_call) */

/* ct.state, written by the audio task only */
enum {
    CT_OFF = 0,                             /* not running; the UI may refill the block */
    CT_LOAD,                                /* one RX block: transform the IR the UI copied in */
    CT_RUN,                                 /* the captured input through the cabinet */
    CT_BAD,                                 /* the IR did not load */
    CT_SLOW                                 /* too slow: stopped */
};

/* The cabinet's memory: in the module (no pool block). The UI fills it while the cabinet is off. */
typedef struct __attribute__((aligned(32))) {
    cab_t cab;
    float ir[CAB_TAPS];                     /* the IR, copied from flash by the UI */
    float in[FRAMES], out[FRAMES];
    u32 stack[STACK_BYTES / 4];             /* stack top = &stack[STACK_BYTES / 4], 8-byte aligned */
} ct_block_t;

typedef struct {
    u32 blocks, cab_avg, cab_max, tot_max;  /* cycles: the cabinet per RX block, worst mixer + cabinet in one wake */
} ct_window;

typedef struct {
    /* written by the UI task */
    volatile u32 req;                       /* 1: the UI has filled the block and wants the cabinet running; 0: stop */
    u32 fx, ext, checked, checks;           /* input FX, EXT SOURCE, last check (cycle count), checks made */
    u32 starts;
    /* written by the audio task */
    volatile u32 state;
    u32 fresh;                              /* out[] holds a block TX has not added yet */
    s32 out[FRAMES];                        /* the next block for the DRY pair, at the 16-bit stems' scale */
    u32 peak;                               /* the capture's peak |sample| (the UI clears it per readout) */
    u32 rx, tx, steps;                      /* RX blocks seen, TX blocks added, FPU steps run */
    u32 task_attr;                          /* the audio task's TCB attribute (0x1000: an FPU task) */
    u32 last_mix;                           /* this wake's mixer cycles (meter_mix_end) */
    u32 w_n, w_sum, w_max, w_tot;           /* the window being collected */
    volatile u32 seq;                       /* odd while pub is written */
    ct_window pub;
    u32 tot_max_ever, over, slow_cycles;    /* since the readout was switched on: worst wake, wakes over a block;
                                               the wake (mixer + cabinet) that stopped it */
    u32 hot;                                /* wakes in a row over 90% of a block */
    u32 reset_req, reset_ack;
    u32 pair_peak[8];                       /* test 2: each RX pair's peak |sample| (the UI clears them per readout) */
} ct_t;

extern ct_t ct;
extern ct_block_t ct_block;

/* cab_fp.c */
u32 cab_fp_call(u32 (*fn)(ct_t *), ct_t *arg, void *stack_top);
u32 cab_fp_step(ct_t *n);

#endif
