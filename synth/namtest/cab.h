/* NAM test 1: the cabinet, a uniformly partitioned convolution (64-frame partitions, 128-point FFTs, overlap-add),
 * mono float. The algorithm of Codex's sp_cab_partitioned.c (offline prototype), sized for this test. */
#ifndef CAB_H
#define CAB_H

#define CAB_PARTS 16                         /* 64-tap partitions: up to 1,024 taps, 21 ms at 48 kHz */
#define CAB_TAPS (CAB_PARTS * 64)

typedef struct {
    float re, im;
} cab_cpx;

typedef struct __attribute__((aligned(32))) {
    unsigned parts, slot;                    /* partitions in use; the newest input block's slot */
    cab_cpx h[CAB_PARTS][128];               /* the IR's partitions, transformed */
    cab_cpx x[CAB_PARTS][128];               /* the last `parts` input blocks, transformed */
    cab_cpx sum[128];
    float overlap[64];
} cab_t;

/* c must be zeroed by the caller. 0, or -1 for a bad tap count, -2 for a non-finite tap. */
int cab_prepare(cab_t *c, const float *ir, unsigned taps);
/* 64 frames in, 64 out; in and out may be the same buffer. */
void cab_process(cab_t *c, const float *in, float *out);

#endif
