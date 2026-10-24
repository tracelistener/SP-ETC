/* NAM test 1: what the integer side (nam_test.c: the meter, the UI, the RX/TX hooks) and the FPU side (nam_fp.c:
 * the NAM amp and the cabinet on the captured input) share. */
#ifndef NAM_TEST_H
#define NAM_TEST_H

#include "third_party/tone3000-embedded/nam_a2lite.h"
#include "cab.h"

typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;

#define FRAMES 64u
#define STACK_BYTES 4096u                   /* the FPU side's own stack (fp_call) */

/* nt.state, written by the audio task only */
enum {
    NT_OFF = 0,                             /* nothing allocated in use; the UI may free the block */
    NT_LOAD1, NT_LOAD2, NT_LOAD3,           /* one step per RX block: the capture, the cabinet, the engine */
    NT_WARM,                                /* NAM_A2LITE_PREWARM_SAMPLES of silence, one block at a time */
    NT_RUN,                                 /* the captured input through the amp and the cabinet */
    NT_BAD,                                 /* the capture or the IR did not load: the block is left alone */
    NT_SLOW                                 /* one block took too long: stopped, the block is left alone */
};

/* The pool block (32-byte aligned payload). The model and the IR are copied into `state` by the UI and read from
 * there while loading; nam_a2lite_init then clears it. */
typedef struct __attribute__((aligned(32))) {
    nam_a2lite_weights_t weights;
    nam_a2lite_t inst;
    nam_a2lite_state_t state;
    cab_t cab;
    float in[FRAMES], amp[FRAMES], out[FRAMES];
    u32 stack[STACK_BYTES / 4];             /* stack top = &stack[STACK_BYTES / 4], 8-byte aligned */
} nt_block_t;

#define MODEL_AT(b) ((const u8 *)&(b)->state)
#define IR_AT(b) ((const float *)((const u8 *)&(b)->state + 8192))

typedef struct {
    u32 blocks, nam_avg, nam_max, tot_max;  /* cycles: NAM per RX block, worst mixer + NAM in one wake */
} nt_window;

typedef struct {
    /* written by the UI task */
    volatile u32 req;                       /* 1: the UI has published blk and wants NAM running; 0: stop */
    volatile u32 mode;                      /* 0: NAM + cabinet, 1: cabinet only (the input FX is the Gt Amp Sim) */
    nt_block_t *volatile blk;
    u32 raw;                                /* the pool allocation as the pool returned it (for the release) */
    u32 mem_fail;                           /* the last allocation failed: shown as MEM! */
    u32 fx, ext, checked, checks;           /* input FX, EXT SOURCE, last check (cycle count), checks made */
    u32 pool_free, pool_largest, pool_ok;   /* the pool's free bytes in all and in its largest piece */
    u32 dtcm_nonzero;                       /* DTCM words past the stock pools that are not zero */
    u32 allocs, frees;
    /* written by the audio task */
    volatile u32 state;
    u32 warm;                               /* prewarm samples done */
    u32 fresh;                              /* out[] holds a block TX has not added yet */
    s32 out[FRAMES];                        /* the next block for the DRY pair, at the 16-bit stems' scale */
    u32 peak;                               /* the capture's peak |sample| (the UI clears it per readout) */
    u32 rx, tx, steps;                      /* RX blocks seen, TX blocks added, FPU steps run */
    u32 task_attr;                          /* the audio task's TCB attribute (0x1000: an FPU task) */
    u32 last_mix;                           /* this wake's mixer cycles (meter_mix_end) */
    u32 w_n, w_sum, w_max, w_tot;           /* the window being collected */
    volatile u32 seq;                       /* odd while pub is written */
    nt_window pub;
    u32 tot_max_ever, over, slow_cycles;    /* since the readout was switched on: worst wake, wakes over a block;
                                               the wake (mixer + NAM) that stopped NAM */
    u32 hot;                                /* wakes in a row over 90% of a block */
    u32 reset_req, reset_ack;
} nt_t;

extern nt_t nt;

/* nam_fp.c */
u32 nam_fp_call(u32 (*fn)(nt_t *), nt_t *arg, void *stack_top);
u32 nam_fp_step(nt_t *n);

#endif
