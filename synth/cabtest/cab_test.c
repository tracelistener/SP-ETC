/* Cabinet test 2: a cabinet IR on the captured input, on v9.50 with the CPU meter of IR diagnostic test 3. NAM tests
 * 1 and 2 showed that a NAM amp does not fit beside the SP's own audio (NAM alone 72% of a block on average, 94% at
 * its peak); the cabinet alone costs a fraction of that. With the Gt Amp Sim as the input FX (its own speaker, SP SW,
 * off) the SP's amp plays through the IR: the test is whether the capture follows the input FX, whether EXT SOURCE
 * off keeps the capture while the direct sound goes, how it sounds, and what it costs.
 *
 * Test 1 on the unit: CAB 15-17% of a block, T27, MAX 30, no overrun; but LV0 while playing on ROUTING ExtIn, one
 * sound, and nothing with EXT SOURCE off. The recorder feed (0x1ca80) copies one of the 8 stereo pairs the effects
 * chip sends back every block (32-byte frames; pair 1 when settings+0x64 is set, else the pair numbered by the byte at
 * 0x82e0e974). Test 2 shows every pair's peak in the readout, to find the one that carries the input after the input
 * FX whether or not EXT SOURCE plays it.
 *
 * While the meter's readout is shown (hold EXIT a second on the main screen), the UI task copies the IR from flash
 * into the module's cabinet memory and hands it to the audio task. After every RX block the audio task then runs one
 * step of cab_fp.c: the IR's transform once, then the captured input (the RX pair the recorder feed copies, as the
 * echo had it) through the cabinet. TX adds each block to the DRY pair of TX line 3 one block later, at -6 dB,
 * clipped to 20 bits as the packer clips. Hiding the readout stops it. The cabinet stops itself (SLOW) when one step
 * takes over a whole block, or the mixer and the cabinet take over 9/10 of one twice in a row.
 *
 * Readout (the stock popup, refreshed every half second):
 *   CAB 4/5 RUN       the cabinet's average/peak per RX block over the last 75; OFF LOAD RUN BAD SLOW
 *   IN23 LV45 X1      the input FX's effect number, the capture's peak in % of full scale, EXT SOURCE
 *   A 0 45 0 0        test 2: the peak of RX pairs 0-3 in % of full scale since the last refresh
 *   B 0 0 0 0         test 2: pairs 4-7
 *   MIX 8/10 T15      the mixer's average/peak in % of a block; the worst mixer + cabinet in one wake (T)
 *   MAX 18 OVR 0      the worst wake since the readout came on (%); wakes whose mixer + cabinet took over a block
 *
 * Hooks, as in IR diagnostic test 3:
 *   0x0001c2d0  mixer entry       -> meter_mix_entry (the return comes back to meter_mix_exit, which adds the block)
 *   0x80005870  per-voice stub    -> meter_voice
 *   0x0001fd84  SG stub's pre call -> meter_sg_pre
 *   bounce's ui bridge: its bnc_ui call -> diag_ui (bnc_ui, the meter's UI step, cab_ui)
 *   bounce's rx bridge: its bnc_rx call -> diag_rx (the RX packet from the audio task's r9 and [r6 + 4], as its
 *                     RX site computed it; bnc_rx, the pair peaks, cab_rx)
 *
 * The CPU meter, as T0 had it: the DWT cycle counter times every 64-frame block (800,000 cycles at 600 MHz); MIX
 * the whole mixer 0x1c2d0, entry to return; PAD and SG are still kept (the readout no longer shows them). This file is
 * the integer side: the builder checks that none of its functions has an FPU instruction.
 */
#include "cab_test_links.h"    /* from the builder: SG_PRE_TARGET, BNC_UI, BNC_RX, IR_ADDR, IR_TAPS, IR_KIND */
#include "cab_test.h"

#define EXPORT __attribute__((used))
#define S_(x) #x
#define XS(x) S_(x)

#define DWT_CTRL (*(volatile u32 *)0xE0001000u)
#define DWT_CYCCNT (*(volatile u32 *)0xE0001004u)
#define DWT_LAR (*(volatile u32 *)0xE0001FB0u)
#define DEMCR (*(volatile u32 *)0xE000EDFCu)

#define SLOT0 0x202AE1A0          /* 32 voice slots, 0x58 bytes each */
#define SLOT31 0x202AEC48         /* SLOT0 + 31 * 0x58 */
#define RENDER 0x00014B89         /* stock voice renderer (voice, stems, &bus, &bus2) */
#define MIX_RESUME 0x0001C2DD     /* mixer, after the four displaced instructions */

#define POPUP_POST ((void (*)(const char *, int))0x800D3FF1u)   /* stock popup (text, ms) */
#define POPUP_CLOSE ((void (*)(void))0x8001F731u)               /* stock: close the popup now */
#define POPUP_TEXT ((volatile const char *)0x802468D8u)          /* text of the newest popup */
#define POPUP_PENDING (*(volatile s32 *)0x802458A0u)             /* >= 0: a post not built yet */
#define POPUP_SHOWN (*(volatile u32 *)0x805922B0u)               /* the popup's bitmap, 0 = none */
#define PAGE (*(volatile s16 *)0x80245880u)                      /* current page, 1 = main screen */
#define KEYS ((volatile const u8 *)0x80592448u)                  /* held keys 0..0x54, one bit each */

#define KEY_EXIT 0x22
#define KEY_SHIFT 0x2A
#define KEY_BYTES 11
#define MAIN_PAGE 1
#define STOCK_PAGES 95             /* pages 0..94 are stock; DOOM OS adds its own screens above */

#define MAGIC 0x4D455452u          /* "METR" */
#define WINDOW 375u                /* blocks: 0.5 s */
#define CAB_WINDOW 75u             /* the cabinet's window: 0.1 s */
#define NOMINAL 800000u            /* cycles per block at 600 MHz */
#define CLAMP 10000000u            /* per-block clamp, keeps 375-block sums in 32 bits */
#define HOLD_CYCLES 600000000u     /* EXIT held this long toggles the readout (1 s at 600 MHz) */
#define KEEPALIVE 600000000u       /* re-post at least this often while shown */
#define POPUP_MS 1500
#define TEXT_MAX 96

/* Offsets the assembly hooks use; checked against the struct below. */
#define OFF_STAMPS 4
#define OFF_T_V0 12
#define OFF_T_V1 16
#define OFF_T_SG0 20
#define OFF_T_SG1 24
#define OFF_NVOX 28
#define OFF_SG_RET 36

typedef struct {
    u32 blocks;                    /* blocks in the window */
    u32 mix_avg, mix_max;          /* cycles */
    u32 vox_avg, vox_max;
    u32 sg_avg, sg_max;
    u32 voices_max;                /* most voices rendered in one block */
    u32 period_avg, period_min, period_max;   /* cycles between mixer starts */
} meter_window;

typedef struct {
    /* written by the audio task's hooks */
    u32 magic;
    u32 stamps;                    /* bit 0/1 voice loop start/end, bit 2/3 SG start/end */
    u32 t_mix0;                    /* this block's mixer start */
    u32 t_v0, t_v1, t_sg0, t_sg1;
    u32 nvox;                      /* voices rendered in this block */
    u32 mix_ret;                   /* the mixer's caller (bounce's tx bridge) */
    u32 sg_ret;                    /* the SG stub's caller (the mixer) */
    u32 have_prev;
    u32 budget;                    /* cycles per block, measured (600k..1M) or NOMINAL */
    u32 dwt_fixed;                 /* 1 if the meter had to start the cycle counter */
    /* window being collected */
    u32 w_n, w_mix_sum, w_mix_max, w_vox_sum, w_vox_max, w_sg_sum, w_sg_max, w_voices;
    u32 w_per_n, w_per_sum, w_per_min, w_per_max;
    /* last finished window; seq is odd while it is written */
    volatile u32 seq;
    meter_window pub;
    /* since the readout was last switched on */
    u32 reset_req, reset_ack;
    u32 total, hi, over, mix_max_ever, vox_max_ever, sg_max_ever, voices_max_ever;
    u32 windows;                   /* windows published since boot */
    /* UI task */
    u32 shown, hold, hold_t0, posted_seq, posted_at, posts, toggles;
    u8 hold_keys[KEY_BYTES + 1];
    char text[TEXT_MAX];           /* the text last handed to the popup */
} meter_t;

_Static_assert(__builtin_offsetof(meter_t, stamps) == OFF_STAMPS, "layout");
_Static_assert(__builtin_offsetof(meter_t, t_v0) == OFF_T_V0, "layout");
_Static_assert(__builtin_offsetof(meter_t, t_v1) == OFF_T_V1, "layout");
_Static_assert(__builtin_offsetof(meter_t, t_sg0) == OFF_T_SG0, "layout");
_Static_assert(__builtin_offsetof(meter_t, t_sg1) == OFF_T_SG1, "layout");
_Static_assert(__builtin_offsetof(meter_t, nvox) == OFF_NVOX, "layout");
_Static_assert(__builtin_offsetof(meter_t, sg_ret) == OFF_SG_RET, "layout");

EXPORT meter_t meter;
EXPORT ct_t ct;
EXPORT ct_block_t ct_block;
#define OFFSET(t, f) ((u32)__builtin_offsetof(t, f))
EXPORT const u32 ct_layout[] = {                          /* the tests read these */
    sizeof(ct_t), OFFSET(ct_t, state), OFFSET(ct_t, out), OFFSET(ct_t, peak), OFFSET(ct_t, pub),
    OFFSET(ct_t, tot_max_ever), OFFSET(ct_t, reset_ack),
    sizeof(ct_block_t), OFFSET(ct_block_t, cab), OFFSET(ct_block_t, ir), OFFSET(ct_block_t, in),
    OFFSET(ct_block_t, out), OFFSET(ct_block_t, stack), sizeof(cab_t), OFFSET(ct_t, pair_peak)};
_Static_assert(IR_TAPS >= 1u && IR_TAPS <= CAB_TAPS, "the IR fits the cabinet");

/* ---- the cabinet: what the UI and the audio task reach ---- */
#define CAPTURE ((const volatile s16 *)0x202AD0A0u)   /* the RX pair the recorder feed copies: 64 x 2 */
#define SYSPRM 0x82DFEED0u                             /* the system parameter object */
#define SYS_GET ((s32 (*)(u32, s32, s32))0x800DA011u)  /* system GetParam(object, ID, index) */
#define SETTINGS 0x82E01144u                           /* the settings object */
#define SET_GET ((s32 (*)(u32, s32, s32))0x800D94D9u)  /* settings GetParam(object, ID, index) */
#define EXT_SOURCE 0x25                                /* settings: EXT SOURCE on */
#define BUS_EFFECT 0x27C                               /* system, by slot: the effect (slot 0 = input FX) */
#define CHECK_CYCLES 60000000u                         /* the input FX is read every 0.1 s */
#define CUR_TASK (*(volatile u32 *)0x202BBBFCu)        /* the kernel's running task (its TCB) */
#define TCB_ATTR 0x10
#define TX_WORDS 16u                                   /* TX line 3: 16 words a frame, DRY = words 0/1 */
#define DRY_MAX 0x7FFFF                                /* the packer clips every stem to 20 bits */
#define DRY_MIN (-0x80000)

#define BARRIER() __asm__ volatile("" ::: "memory")

/* The compiler may turn loops into these calls; keep them local. Word stores where both ends allow. */
EXPORT void *memset(void *d, int c, unsigned n) {
    volatile u8 *p = (volatile u8 *)d;
    u32 v = (u8)c * 0x01010101u;
    while (n && ((u32)p & 3u)) {
        *p++ = (u8)c;
        n--;
    }
    for (; n >= 4; n -= 4, p += 4)
        *(volatile u32 *)p = v;
    while (n--)
        *p++ = (u8)c;
    return d;
}
EXPORT void *memcpy(void *d, const void *s, unsigned n) {
    volatile u8 *p = (volatile u8 *)d;
    const volatile u8 *q = (const volatile u8 *)s;
    if (!(((u32)p | (u32)q) & 3u))
        for (; n >= 4; n -= 4, p += 4, q += 4)
            *(volatile u32 *)p = *(const volatile u32 *)q;
    while (n--)
        *p++ = *q++;
    return d;
}
EXPORT int memcmp(const void *a, const void *b, unsigned n) {
    const volatile u8 *p = (const volatile u8 *)a, *q = (const volatile u8 *)b;
    for (; n; n--, p++, q++)
        if (*p != *q)
            return *p < *q ? -1 : 1;
    return 0;
}

static u32 clamp(u32 v) { return v > CLAMP ? CLAMP : v; }

static void window_clear(meter_t *m) {
    m->w_n = 0;
    m->w_mix_sum = m->w_mix_max = 0;
    m->w_vox_sum = m->w_vox_max = 0;
    m->w_sg_sum = m->w_sg_max = 0;
    m->w_voices = 0;
    m->w_per_n = m->w_per_sum = m->w_per_max = 0;
    m->w_per_min = 0xFFFFFFFFu;
}

static void totals_clear(meter_t *m) {
    m->total = m->hi = m->over = 0;
    m->mix_max_ever = m->vox_max_ever = m->sg_max_ever = m->voices_max_ever = 0;
}

/* ---- audio task ---- */

static const volatile u32 *mix_bufs;   /* the mixer's argument: TX line 3, line 1, line 2 */

EXPORT void meter_mix_begin(u32 ret, const volatile u32 *bufs) {
    u32 now = DWT_CYCCNT;
    meter_t *m = &meter;
    mix_bufs = bufs;
    if (m->magic != MAGIC) {
        /* The stock tempo clock reads this counter, so it should be running; start
         * it if not (as the Oct 10 voice load test did) and say so in the readout. */
        if (!(DWT_CTRL & 1u)) {
            DEMCR |= 1u << 24;
            DWT_LAR = 0xC5ACCE55u;
            DWT_CTRL |= 1u;
            m->dwt_fixed = 1;
        }
        m->budget = NOMINAL;
        m->have_prev = 0;
        window_clear(m);
        totals_clear(m);
        m->magic = MAGIC;
        now = DWT_CYCCNT;
    }
    if (m->have_prev) {
        u32 per = clamp(now - m->t_mix0);
        m->w_per_n++;
        m->w_per_sum += per;
        if (per > m->w_per_max) m->w_per_max = per;
        if (per < m->w_per_min) m->w_per_min = per;
    }
    m->t_mix0 = now;
    m->have_prev = 1;
    m->stamps = 0;
    m->nvox = 0;
    m->mix_ret = ret;
}

static void publish(meter_t *m) {
    u32 n = m->w_n;
    m->seq++;
    BARRIER();
    m->pub.blocks = n;
    m->pub.mix_avg = m->w_mix_sum / n;
    m->pub.mix_max = m->w_mix_max;
    m->pub.vox_avg = m->w_vox_sum / n;
    m->pub.vox_max = m->w_vox_max;
    m->pub.sg_avg = m->w_sg_sum / n;
    m->pub.sg_max = m->w_sg_max;
    m->pub.voices_max = m->w_voices;
    if (m->w_per_n) {
        m->pub.period_avg = m->w_per_sum / m->w_per_n;
        m->pub.period_min = m->w_per_min;
        m->pub.period_max = m->w_per_max;
    } else {
        m->pub.period_avg = m->pub.period_min = m->pub.period_max = 0;
    }
    BARRIER();
    m->seq++;
    m->windows++;
    /* Percentages and the HI/OVR thresholds use the measured block length when it
     * is plausible (600k..1M cycles); 800,000 otherwise. */
    {
        u32 p = m->pub.period_avg;
        m->budget = (p >= 600000u && p <= 1000000u) ? p : NOMINAL;
    }
    window_clear(m);
}

static s32 clip20(s32 v) { return v > DRY_MAX ? DRY_MAX : v < DRY_MIN ? DRY_MIN : v; }

/* After the mixer: the cabinet's newest block, if TX has not added it yet, onto the DRY pair of the TX line 3 block
 * the mixer has just packed. */
EXPORT void cab_tx(const volatile u32 *bufs, u32 mix) {
    ct_t *n = &ct;
    n->last_mix = mix;
    if (!n->fresh)
        return;
    volatile s32 *p = (volatile s32 *)bufs[0];
    for (u32 f = 0; f < FRAMES; f++, p += TX_WORDS) {
        s32 e = n->out[f];
        p[0] = clip20(p[0] + e);
        p[1] = clip20(p[1] + e);
    }
    n->fresh = 0;
    n->tx++;
}

EXPORT u32 meter_mix_end(void) {
    u32 now = DWT_CYCCNT;
    meter_t *m = &meter;
    u32 mix = clamp(now - m->t_mix0);
    u32 vox = (m->stamps & 3u) == 3u ? clamp(m->t_v1 - m->t_v0) : 0u;
    u32 sg = (m->stamps & 12u) == 12u ? clamp(m->t_sg1 - m->t_sg0) : 0u;
    u32 voices = m->nvox;
    if (m->reset_ack != m->reset_req) {
        totals_clear(m);
        m->reset_ack = m->reset_req;
    }
    m->total++;
    if (mix > m->budget) m->over++;
    if (mix > m->budget - (m->budget >> 2)) m->hi++;
    if (mix > m->mix_max_ever) m->mix_max_ever = mix;
    if (vox > m->vox_max_ever) m->vox_max_ever = vox;
    if (sg > m->sg_max_ever) m->sg_max_ever = sg;
    if (voices > m->voices_max_ever) m->voices_max_ever = voices;
    m->w_n++;
    m->w_mix_sum += mix;
    if (mix > m->w_mix_max) m->w_mix_max = mix;
    m->w_vox_sum += vox;
    if (vox > m->w_vox_max) m->w_vox_max = vox;
    m->w_sg_sum += sg;
    if (sg > m->w_sg_max) m->w_sg_max = sg;
    if (voices > m->w_voices) m->w_voices = voices;
    if (m->w_n >= WINDOW) publish(m);
    cab_tx(mix_bufs, mix);
    return m->mix_ret;
}

static void cab_publish(ct_t *n) {
    n->seq++;
    BARRIER();
    n->pub.blocks = n->w_n;
    n->pub.cab_avg = n->w_sum / n->w_n;
    n->pub.cab_max = n->w_max;
    n->pub.tot_max = n->w_tot;
    BARRIER();
    n->seq++;
    n->w_n = n->w_sum = n->w_max = n->w_tot = 0;
}

/* A RUN step's cycles, with this wake's mixer: the window, the worst wake, overruns. Returns the wake's cycles. */
static u32 cab_account(ct_t *n, u32 dt, u32 budget) {
    u32 tot = clamp(clamp(dt) + n->last_mix);
    dt = clamp(dt);
    n->last_mix = 0;
    if (n->reset_ack != n->reset_req) {
        n->tot_max_ever = n->over = 0;
        n->w_n = n->w_sum = n->w_max = n->w_tot = 0;
        n->reset_ack = n->reset_req;
    }
    if (tot > budget) n->over++;
    if (tot > n->tot_max_ever) n->tot_max_ever = tot;
    n->w_n++;
    n->w_sum += dt;
    if (dt > n->w_max) n->w_max = dt;
    if (tot > n->w_tot) n->w_tot = tot;
    if (n->w_n >= CAB_WINDOW) cab_publish(n);
    return tot;
}

/* After the recorder feed (audio task): the capture's peak, then one cabinet step while the UI wants it. */
EXPORT void cab_rx(void) {
    ct_t *n = &ct;
    const volatile s16 *cap = CAPTURE;
    u32 peak = n->peak;
    for (u32 i = 0; i < 2 * FRAMES; i++) {
        s32 v = cap[i];
        u32 a = (u32)(v < 0 ? -v : v);
        if (a > peak) peak = a;
    }
    n->peak = peak;
    n->rx++;
    n->task_attr = *(volatile u32 *)(CUR_TASK + TCB_ATTR);
    u32 st = n->state;
    if (!n->req) {
        if (st != CT_OFF) n->state = CT_OFF;
        n->fresh = 0;
        return;
    }
    if (st >= CT_BAD) return;
    if (st == CT_OFF) n->state = st = CT_LOAD;
    u32 budget = meter.budget ? meter.budget : NOMINAL;
    u32 t0 = DWT_CYCCNT;
    u32 next = cab_fp_call(cab_fp_step, n, &ct_block.stack[STACK_BYTES / 4]);
    u32 dt = DWT_CYCCNT - t0;
    n->steps++;
    if (st == CT_RUN) {
        /* Stop before the audio task can starve the others: one step over a whole block, or two wakes in a row
         * whose mixer + cabinet took over 9/10 of one. What the window has so far is published, to be read. */
        u32 tot = cab_account(n, dt, budget);
        n->hot = tot > budget / 10u * 9u ? n->hot + 1u : 0u;
        if (dt > budget || n->hot >= 2u) {
            next = CT_SLOW;
            n->slow_cycles = tot;
            n->fresh = 0;
            if (n->w_n) cab_publish(n);
        }
    }
    n->state = next;
}

/* Mixer entry (0x1c2d0 jumps here). r0 = the TX buffers, lr = bounce's tx bridge.
 * Stamp the start, send the mixer's return through meter_mix_exit, then run the
 * four displaced stock instructions and continue at 0x1c2dc. */
__attribute__((naked, used)) void meter_mix_entry(void) {
    __asm__ volatile(
        "push {r0, r1, r2, r3}\n"
        "mov r1, r0\n"
        "mov r0, lr\n"
        "bl meter_mix_begin\n"
        "pop {r0, r1, r2, r3}\n"
        "ldr lr, =meter_mix_exit\n"
        "push.w {r4, r5, r6, r7, r8, r9, r10, r11, lr}\n"
        "sub sp, #0x1c\n"
        "movw r1, #0xb93c\n"
        "str r0, [sp, #8]\n"
        "ldr r12, =" XS(MIX_RESUME) "\n"
        "bx r12\n"
        ".ltorg\n");
}

/* The mixer returns here. Record the block, then return to the audio task. */
__attribute__((naked, used)) void meter_mix_exit(void) {
    __asm__ volatile(
        "push {r0, r1, r2, r3}\n"
        "bl meter_mix_end\n"
        "mov r12, r0\n"
        "pop {r0, r1, r2, r3}\n"
        "bx r12\n");
}

/* Per-voice stub (0x80005870 jumps here), once per slot per block:
 * r0 = slot, r1 = stems, r2 = &bus, r3 = &bus2. As stock: an empty slot returns,
 * an occupied one renders through 0x14b89 with the same four arguments. Slot 0
 * stamps the loop's start, slot 31 its end. */
__attribute__((naked, used)) void meter_voice(void) {
    __asm__ volatile(
        "push {r4, r5, r6, lr}\n"
        "mov r6, r0\n"
        "ldr r4, =meter\n"
        "ldr r5, =0xE0001004\n"
        "ldr r12, =" XS(SLOT0) "\n"
        "cmp r6, r12\n"
        "bne 1f\n"
        "ldr r12, [r5]\n"
        "str r12, [r4, #" XS(OFF_T_V0) "]\n"
        "ldr r12, [r4, #" XS(OFF_STAMPS) "]\n"
        "orr r12, r12, #1\n"
        "str r12, [r4, #" XS(OFF_STAMPS) "]\n"
        "1:\n"
        "ldr r0, [r6]\n"
        "cbz r0, 2f\n"
        "ldr r12, [r4, #" XS(OFF_NVOX) "]\n"
        "add r12, r12, #1\n"
        "str r12, [r4, #" XS(OFF_NVOX) "]\n"
        "ldr r12, =" XS(RENDER) "\n"
        "blx r12\n"
        "2:\n"
        "ldr r12, =" XS(SLOT31) "\n"
        "cmp r6, r12\n"
        "bne 3f\n"
        "ldr r12, [r5]\n"
        "str r12, [r4, #" XS(OFF_T_V1) "]\n"
        "ldr r12, [r4, #" XS(OFF_STAMPS) "]\n"
        "orr r12, r12, #2\n"
        "str r12, [r4, #" XS(OFF_STAMPS) "]\n"
        "3:\n"
        "pop {r4, r5, r6, pc}\n"
        ".ltorg\n");
}

/* The fork's SG render stub (called at 0x1c766) starts with push {r4-r8, lr} and
 * then calls its pre bridge with blx ip; that call comes here. [sp, #20] holds the
 * mixer's return address. Stamp the start, route that return through meter_sg_end
 * and go on to the original bridge with every register as it came. */
__attribute__((naked, used)) void meter_sg_pre(void) {
    __asm__ volatile(
        "push {r0, r1}\n"
        "ldr r0, =meter\n"
        "ldr r1, =0xE0001004\n"
        "ldr r1, [r1]\n"
        "str r1, [r0, #" XS(OFF_T_SG0) "]\n"
        "ldr r1, [r0, #" XS(OFF_STAMPS) "]\n"
        "orr r1, r1, #4\n"
        "str r1, [r0, #" XS(OFF_STAMPS) "]\n"
        "ldr r1, [sp, #28]\n"
        "str r1, [r0, #" XS(OFF_SG_RET) "]\n"
        "ldr r1, =meter_sg_end\n"
        "str r1, [sp, #28]\n"
        "pop {r0, r1}\n"
        "ldr r12, =" XS(SG_PRE_TARGET) "\n"
        "bx r12\n"
        ".ltorg\n");
}

/* The SG stub's final pop {r4-r8, pc} lands here: stamp the end, back to the mixer. */
__attribute__((naked, used)) void meter_sg_end(void) {
    __asm__ volatile(
        "push {r0, r1}\n"
        "ldr r0, =meter\n"
        "ldr r1, =0xE0001004\n"
        "ldr r1, [r1]\n"
        "str r1, [r0, #" XS(OFF_T_SG1) "]\n"
        "ldr r1, [r0, #" XS(OFF_STAMPS) "]\n"
        "orr r1, r1, #8\n"
        "str r1, [r0, #" XS(OFF_STAMPS) "]\n"
        "ldr r12, [r0, #" XS(OFF_SG_RET) "]\n"
        "pop {r0, r1}\n"
        "bx r12\n"
        ".ltorg\n");
}

/* ---- UI task ---- */

#define UI_SMALL __attribute__((noinline, minsize))

UI_SMALL static char *put_str(char *p, const char *s) {
    while (*s) *p++ = *s++;
    return p;
}

UI_SMALL static char *put_u(char *p, u32 v) {
    char t[10];
    int n = 0;
    do {
        t[n++] = (char)('0' + v % 10u);
        v /= 10u;
    } while (v);
    while (n) *p++ = t[--n];
    return p;
}

UI_SMALL static u32 pct(u32 cycles, u32 budget) {
    u32 p;
    if (cycles > 9999999u) cycles = 9999999u;
    p = (cycles * 100u + budget / 2u) / budget;
    return p > 999u ? 999u : p;
}

static u32 cap(u32 v) { return v > 999u ? 999u : v; }

static const char *const STATE_NAMES[] = {"OFF", "LOAD", "RUN", "BAD", "SLOW"};

/* Six lines in the popup's font (PBold, 9 px lines): test_cab_test.py checks that the
 * widest worst case leaves the popup box inside the 128 x 64 screen. */
EXPORT UI_SMALL void meter_format(const meter_window *w, const ct_window *cw, char *out) {
    const meter_t *m = &meter;
    const ct_t *n = &ct;
    u32 b = m->budget ? m->budget : NOMINAL;
    u32 st = n->state;
    char *p = out;
    p = put_str(p, "CAB ");
    p = put_u(p, pct(cw->cab_avg, b) > 99u ? 99u : pct(cw->cab_avg, b));    /* two digits: the box is narrow */
    *p++ = '/';
    p = put_u(p, pct(cw->cab_max, b) > 99u ? 99u : pct(cw->cab_max, b));
    *p++ = ' ';
    p = put_str(p, STATE_NAMES[st < 5u ? st : 0u]);
    p = put_str(p, "\nIN");
    p = put_u(p, n->fx > 99u ? 99u : n->fx);
    p = put_str(p, " LV");
    p = put_u(p, (n->peak > 32768u ? 32768u : n->peak) * 100u / 32768u);
    p = put_str(p, n->ext ? " X1" : " X0");
    for (u32 k = 0; k < 8u; k++) {
        if (!(k & 3u)) p = put_str(p, k ? "\nB" : "\nA");
        *p++ = ' ';
        p = put_u(p, (n->pair_peak[k] > 32767u ? 32767u : n->pair_peak[k]) * 100u / 32768u);
    }
    p = put_str(p, "\nMIX ");
    p = put_u(p, pct(w->mix_avg, b));
    *p++ = '/';
    p = put_u(p, pct(w->mix_max, b));
    p = put_str(p, " T");
    p = put_u(p, pct(cw->tot_max, b));
    p = put_str(p, "\nMAX ");
    p = put_u(p, pct(n->tot_max_ever, b));
    p = put_str(p, " OVR ");
    p = put_u(p, cap(n->over));
    *p = 0;
}

static int read_window(meter_window *out) {
    meter_t *m = &meter;
    for (int tries = 0; tries < 4; ++tries) {
        u32 s = m->seq;
        BARRIER();
        if (s & 1u) continue;
        *out = m->pub;
        BARRIER();
        if (m->seq == s) return 1;
    }
    return 0;
}

static int read_cab_window(ct_window *out) {
    ct_t *n = &ct;
    for (int tries = 0; tries < 4; ++tries) {
        u32 s = n->seq;
        BARRIER();
        if (s & 1u) continue;
        *out = n->pub;
        BARRIER();
        if (n->seq == s) return 1;
    }
    return 0;
}

static int ours_on_screen(const meter_t *m) {
    volatile const char *a = POPUP_TEXT;
    const char *b = m->text;
    if (!POPUP_SHOWN || !b[0]) return 0;
    for (int i = 0; i < TEXT_MAX; ++i) {
        if (a[i] != b[i]) return 0;
        if (!b[i]) return 1;
    }
    return 0;
}

static void post(meter_t *m, u32 now) {
    meter_window w;
    ct_window cw;
    char text[TEXT_MAX];
    if ((u32)PAGE >= STOCK_PAGES) return;               /* never over DOOM OS's own screens */
    if (POPUP_PENDING >= 0) return;                     /* someone else's post is queued */
    if (POPUP_SHOWN && !ours_on_screen(m)) return;      /* leave a stock message alone */
    if (!read_window(&w) || !read_cab_window(&cw)) return;
    meter_format(&w, &cw, text);
    ct.peak = 0;                                        /* a peak per readout */
    for (int k = 0; k < 8; ++k) ct.pair_peak[k] = 0;
    for (int i = 0; i < TEXT_MAX; ++i) {
        m->text[i] = text[i];
        if (!text[i]) break;
    }
    POPUP_POST(m->text, POPUP_MS);
    m->posted_seq = m->seq;
    m->posted_at = now;
    m->posts++;
}

static void toggle(meter_t *m, u32 now) {
    m->toggles++;
    if (!m->shown) {
        m->shown = 1;
        m->reset_req++;                                 /* HI, OVR and MAX start again */
        ct.reset_req++;
        m->posted_seq = m->seq - 2u;                    /* show the current window at once */
        m->posted_at = now - KEEPALIVE;
    } else {
        m->shown = 0;
        if (ours_on_screen(m)) POPUP_CLOSE();
    }
}

static int exit_alone_changed(const meter_t *m) {
    for (int i = 0; i < KEY_BYTES; ++i) {
        u8 now = KEYS[i], then = m->hold_keys[i];
        if (i == (KEY_EXIT >> 3)) {
            now &= (u8)~(1u << (KEY_EXIT & 7));
            then &= (u8)~(1u << (KEY_EXIT & 7));
        }
        if (now != then) return 1;
    }
    return 0;
}

enum { HOLD_IDLE, HOLD_TIMING, HOLD_DONE };

/* Every UI tick, before the stock popup tick. */
EXPORT UI_SMALL void meter_ui_tick(int elapsed) {
    meter_t *m = &meter;
    u32 now = DWT_CYCCNT;
    (void)elapsed;
    if (m->magic != MAGIC) return;
    if (!((KEYS[KEY_EXIT >> 3] >> (KEY_EXIT & 7)) & 1u)) {
        m->hold = HOLD_IDLE;
    } else if (m->hold == HOLD_IDLE) {
        /* Starts only on the main screen and without SHIFT (SHIFT + EXIT is stock).
         * Any other key pressed or let go during the hold cancels it. */
        if (PAGE == MAIN_PAGE && !((KEYS[KEY_SHIFT >> 3] >> (KEY_SHIFT & 7)) & 1u)) {
            for (int i = 0; i < KEY_BYTES; ++i) m->hold_keys[i] = KEYS[i];
            m->hold_t0 = now;
            m->hold = HOLD_TIMING;
        } else {
            m->hold = HOLD_DONE;
        }
    } else if (m->hold == HOLD_TIMING) {
        if (PAGE != MAIN_PAGE || exit_alone_changed(m)) {
            m->hold = HOLD_DONE;
        } else if (now - m->hold_t0 >= HOLD_CYCLES) {
            m->hold = HOLD_DONE;
            toggle(m, now);
        }
    }
    if (m->shown && (m->posted_seq != m->seq || now - m->posted_at >= KEEPALIVE)) post(m, now);
}

/* Fill the cabinet's memory and hand it to the audio task (only while it is off). */
UI_SMALL static void cab_start(ct_t *n) {
    memset(&ct_block.cab, 0, sizeof(ct_block.cab));
    memcpy(ct_block.ir, (const void *)IR_ADDR, IR_TAPS * 4u);
    n->starts++;
    BARRIER();
    n->req = 1;
}

/* Every UI tick: the cabinet on while the readout is shown. Every 0.1 s: the input FX and EXT SOURCE. */
EXPORT UI_SMALL void cab_ui(void) {
    ct_t *n = &ct;
    u32 want = meter.shown;
    if (!want) n->req = 0;
    if (want && !n->req && n->state == CT_OFF) cab_start(n);
    u32 now = DWT_CYCCNT;
    if (now - n->checked < CHECK_CYCLES) return;
    n->checked = now;
    n->checks++;
    n->fx = (u32)SYS_GET(SYSPRM, BUS_EFFECT, 0);
    n->ext = SET_GET(SETTINGS, EXT_SOURCE, 0) != 0;
}

/* Bounce's ui bridge (the popup tick, UI task, every millisecond) calls this in place of bnc_ui. */
EXPORT void diag_ui(int elapsed) {
    ((void (*)(int))BNC_UI)(elapsed);
    meter_ui_tick(elapsed);
    cab_ui();
}

/* Every RX block: the peak of each of the packet's 8 stereo pairs (32-byte frames, 64 of them). The packet is in
 * DTCM, which the D-cache does not cover. */
EXPORT void cab_pairs(const volatile s16 *packet) {
    ct_t *n = &ct;
    for (u32 k = 0; k < 8u; k++) {
        u32 peak = n->pair_peak[k];
        for (u32 f = 0; f < FRAMES; f++) {
            for (u32 c = 0; c < 2u; c++) {
                s32 v = packet[f * 16u + k * 2u + c];
                u32 a = (u32)(v < 0 ? -v : v);
                if (a > peak) peak = a;
            }
        }
        n->pair_peak[k] = peak;
    }
}

/* Bounce's rx bridge (after the recorder feed, audio task) calls this in place of bnc_rx. */
EXPORT void diag_rx_c(const volatile s16 *packet) {
    ((void (*)(void))BNC_RX)();
    cab_pairs(packet);
    cab_rx();
}

/* The bridge comes here with the audio task's registers as its RX site left them: r9 the RX banks, [r6 + 4] this
 * block's bank (0x1d0b4..0x1d0be: r0 = r9 + bank << 11, 2,048 bytes a bank), so the packet the feed just read is
 * r9 + ([r6 + 4] << 11). */
__attribute__((naked, used)) void diag_rx(void) {
    __asm__ volatile(
        "ldr r0, [r6, #4]\n"
        "add.w r0, r9, r0, lsl #11\n"
        "b diag_rx_c\n");
}
