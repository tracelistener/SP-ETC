/* Cabinet test 1, the FPU side: the cabinet on the captured input. Everything here runs on the audio task through
 * cab_fp_call: on the module's own 2 KB stack, with FPSCR and s0-s31 saved around it and FPSCR set to round to
 * nearest, flush to zero and default NaN. The audio task (inittsk) is an FPU task (attribute 0x1001; the readout's F1
 * on the unit), so the kernel switches its FPU registers anyway; saving them here keeps every other task's as it was.
 *
 * One step per RX block (cab_rx in cab_test.c decides when):
 *   CT_LOAD  transform the IR the UI copied into the block
 *   CT_RUN   the captured input, (L + R) / 2 at full scale = 1.0, through the cabinet, into ct.out at 1.0 = 16384
 *            (-6 dB at the stems' scale: with ROUTING on Mix the return comes back into the capture at most half as
 *            loud, so it fades instead of feeding back)
 */
#include "cab_test.h"
#include "cab_test_links.h"                  /* from the builder: IR_TAPS */

#define CAPTURE ((const volatile s16 *)0x202AD0A0u)   /* the RX pair the recorder feed copies: 64 x 2 */
#define IN_SCALE (1.0f / 65536.0f)                    /* (L + R) / 2 / 32768 */
#define OUT_SCALE 16384.0f

/* fn(arg) on the stack that ends at stack_top (8-byte aligned), with FPSCR and d0-d15 saved on it. */
__attribute__((naked, used)) u32 cab_fp_call(u32 (*fn)(ct_t *), ct_t *arg, void *stack_top) {
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

u32 cab_fp_step(ct_t *n) {
    ct_block_t *b = &ct_block;
    switch (n->state) {
    case CT_LOAD:
        return cab_prepare(&b->cab, b->ir, IR_TAPS) ? CT_BAD : CT_RUN;
    case CT_RUN: {
        const volatile s16 *cap = CAPTURE;
        for (u32 f = 0; f < FRAMES; f++)
            b->in[f] = (float)((s32)cap[2 * f] + cap[2 * f + 1]) * IN_SCALE;
        cab_process(&b->cab, b->in, b->out);
        for (u32 f = 0; f < FRAMES; f++)
            n->out[f] = (s32)(b->out[f] * OUT_SCALE);
        n->fresh = 1;
        return CT_RUN;
    }
    }
    return n->state;
}
