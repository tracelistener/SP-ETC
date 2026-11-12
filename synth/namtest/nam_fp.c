/* NAM test, the FPU side: the NAM amp (TONE3000's A2-Lite engine for the Cortex-M7, MIT) and the cabinet on the
 * captured input. Everything here runs on the audio task through nam_fp_call: on the pool block's own stack, with
 * FPSCR and s0-s31 saved around it and FPSCR set to round to nearest, flush to zero and default NaN while it runs
 * (denormals are slow on the M7 FPU; TONE3000's integration notes ask for both). The audio task (inittsk, priority 1)
 * is created as an FPU task (attribute 0x1001), so the kernel switches its FPU registers anyway; saving them here
 * as well keeps every other task's FPU state as it was if that is not so.
 *
 * One step per RX block (nam_rx in nam_test.c decides when):
 *   NT_LOAD1  check the capture the UI copied into the block (A2-Lite, 48 kHz, CRC) and load it
 *   NT_LOAD2  transform the cabinet IR the UI copied into the block
 *   NT_LOAD3  bind the engine to the block (this clears the state, where both copies were)
 *   NT_WARM   NAM_A2LITE_PREWARM_SAMPLES of silence: the engine's prewarm, one call a block, of 8, 16 and 32
 *             samples at first (the caches start cold; test 1's first 64-sample step took a whole block), then 64
 *   NT_RUN    the captured input, (L + R) / 2 at full scale = 1.0, through the amp (mode 0) and the cabinet, into
 *             nt.out at 1.0 = 8192 (-12 dB at the stems' scale, as IR diagnostic test 3's echo)
 */
#include "nam_test.h"
#include "third_party/tone3000-embedded/namb_reader.h"
#include "nam_test_links.h"                  /* from the builder: MODEL_BYTES, IR_TAPS */

#define CAPTURE ((const volatile s16 *)0x202AD0A0u)   /* the RX pair the recorder feed copies: 64 x 2 */
#define IN_SCALE (1.0f / 65536.0f)                    /* (L + R) / 2 / 32768 */
#define OUT_SCALE 8192.0f
#define RATE_48K 0x40E7700000000000ull                /* 48000.0 as an IEEE double */

/* The engine's three maths calls, as single FPv5 instructions. */
float fmaf(float a, float b, float c) {
    __asm__("vfma.f32 %0, %1, %2" : "+t"(c) : "t"(a), "t"(b));
    return c;
}
float fmaxf(float a, float b) {
    float r;
    __asm__("vmaxnm.f32 %0, %1, %2" : "=t"(r) : "t"(a), "t"(b));
    return r;
}
float fabsf(float a) {
    float r;
    __asm__("vabs.f32 %0, %1" : "=t"(r) : "t"(a));
    return r;
}

/* fn(arg) on the stack that ends at stack_top (8-byte aligned), with FPSCR and d0-d15 saved on it. */
__attribute__((naked, used)) u32 nam_fp_call(u32 (*fn)(nt_t *), nt_t *arg, void *stack_top) {
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

static u32 load_capture(nt_block_t *b) {
    namb_model_t m;
    union {
        double d;
        unsigned long long u;
    } rate;
    if (namb_parse(MODEL_AT(b), MODEL_BYTES, &m) != NAMB_OK || namb_verify_crc(MODEL_AT(b), MODEL_BYTES) != NAMB_OK ||
        namb_check_a2lite(&m) != NAMB_OK)
        return NT_BAD;
    rate.d = m.sample_rate;
    if (rate.u != RATE_48K)
        return NT_BAD;
    return nam_a2lite_load_weights(&b->weights, m.weights, (int)m.weight_count) ? NT_BAD : NT_LOAD2;
}

static void amp(nt_block_t *b, u32 frames) {
    const float *in[1] = {b->in};
    float *out[1] = {b->amp};
    nam_a2lite_process(&b->inst, in, out, (int)frames);
}

u32 nam_fp_step(nt_t *n) {
    nt_block_t *b = n->blk;
    switch (n->state) {
    case NT_LOAD1:
        return load_capture(b);
    case NT_LOAD2:
        return cab_prepare(&b->cab, IR_AT(b), IR_TAPS) ? NT_BAD : NT_LOAD3;
    case NT_LOAD3:
        nam_a2lite_init(&b->inst, &b->weights, &b->state);
        n->warm = 0;
        return NT_WARM;
    case NT_WARM: {
        u32 k = NAM_A2LITE_PREWARM_SAMPLES - n->warm, step = n->warm < 8 ? 8 : n->warm < 24 ? 16 : n->warm < 56 ? 32 : FRAMES;
        if (k > step)
            k = step;
        for (u32 f = 0; f < k; f++)
            b->in[f] = 0.0f;
        amp(b, k);
        n->warm += k;
        return n->warm >= NAM_A2LITE_PREWARM_SAMPLES ? NT_RUN : NT_WARM;
    }
    case NT_RUN: {
        const volatile s16 *cap = CAPTURE;
        for (u32 f = 0; f < FRAMES; f++)
            b->in[f] = (float)((s32)cap[2 * f] + cap[2 * f + 1]) * IN_SCALE;
        if (!n->mode)
            amp(b, FRAMES);
        cab_process(&b->cab, n->mode ? b->in : b->amp, b->out);
        for (u32 f = 0; f < FRAMES; f++)
            n->out[f] = (s32)(b->out[f] * OUT_SCALE);
        n->fresh = 1;
        return NT_RUN;
    }
    }
    return n->state;
}
