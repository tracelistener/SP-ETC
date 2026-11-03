/* Note tracker test 1: which note the guitar plays, on the screen, on v9.52 (combined-test17) with the CPU meter of
 * IR diagnostic test 3. The first step towards a guitar synth (the Sound Generator played from the guitar): how well
 * and how fast the SP's main processor can follow the note from the input the effects chip hands back (RX pair 0,
 * after the input FX: cabinet test 2 on the unit found the input only in pairs 0 and 1).
 *
 * While the meter's readout is shown (hold EXIT a second on the main screen), the audio task copies pair 0,
 * (L + R) / 2, after every RX block and runs one tracker step (tune_fp.c). Hiding the readout stops it. It stops
 * itself (SLOW) when one step takes over a whole block, or the mixer and the tracker take over 9/10 of one twice in
 * a row. Nothing goes to the output.
 *
 * Readout (the stock popup; every 0.1 s while the tracker runs, else with the meter's half-second window):
 *   E2 +3c Q92        the steady note (-- none); the newest analysis: cents off its nearest note, quality
 *   82.4Hz LV45 X1    the newest analysis' frequency (--Hz unvoiced), pair 0's peak in % of full scale, EXT SOURCE
 *   1ST 21 LCK 27     the last pluck: ms to the first estimate, ms to the steady note
 *   AVG 25 N12 IN23   the average ms to the steady note over N plucks since the readout came on; the input FX
 *   TRK 4/6 MIX 9     the tracker's average/peak per RX block over the last 75 (OFF, SLOW), the mixer's average, in %
 *                     of a block
 *   MAX 30 OVR 0      the worst wake since the readout came on (%); wakes whose mixer + tracker took over a block
 *
 * Hooks, as in cabinet test 2:
 *   0x0001c2d0  mixer entry       -> meter_mix_entry (the return comes back to meter_mix_exit)
 *   0x80005870  per-voice stub    -> meter_voice
 *   0x0001fd84  SG stub's pre call -> meter_sg_pre
 *   bounce's ui bridge: its bnc_ui call -> diag_ui (bnc_ui, the meter's UI step, tune_ui)
 *   bounce's rx bridge: its bnc_rx call -> diag_rx (the RX packet from the audio task's r9 and [r6 + 4], as its
 *                     RX site computed it; bnc_rx, the pairs, tune_rx)
 *
 * The CPU meter, as T0 had it: the DWT cycle counter times every 64-frame block (800,000 cycles at 600 MHz); MIX
 * the whole mixer 0x1c2d0, entry to return; PAD and SG are still kept (the readout does not show them). This file is
 * the integer side: the builder checks that none of its functions has an FPU instruction.
 */
#include "tune_test_links.h"   /* from the builder: SG_PRE_TARGET, BNC_UI, BNC_RX */
#include "tune_test.h"

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
#define TT_WINDOW 75u              /* the tracker's window: 0.1 s */
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
EXPORT tt_t tt;
EXPORT tt_block_t tt_block;
#define OFFSET(t, f) ((u32)__builtin_offsetof(t, f))
EXPORT const u32 tt_layout[] = {                          /* the tests read these */
    sizeof(tt_t), OFFSET(tt_t, state), OFFSET(tt_t, peak), OFFSET(tt_t, in), OFFSET(tt_t, w_n), OFFSET(tt_t, pub),
    OFFSET(tt_t, tot_max_ever), OFFSET(tt_t, reset_ack), OFFSET(tt_t, rseq), OFFSET(tt_t, res), sizeof(tt_result),
    sizeof(tt_block_t), OFFSET(tt_block_t, ring), OFFSET(tt_block_t, span), OFFSET(tt_block_t, d6),
    OFFSET(tt_block_t, energy), OFFSET(tt_block_t, z), OFFSET(tt_block_t, started), OFFSET(tt_block_t, stack),
    OFFSET(tt_t, posted_rseq)};

/* ---- the tracker: what the UI and the audio task reach ---- */
#define SYSPRM 0x82DFEED0u                             /* the system parameter object */
#define SYS_GET ((s32 (*)(u32, s32, s32))0x800DA011u)  /* system GetParam(object, ID, index) */
#define SETTINGS 0x82E01144u                           /* the settings object */
#define SET_GET ((s32 (*)(u32, s32, s32))0x800D94D9u)  /* settings GetParam(object, ID, index) */
#define EXT_SOURCE 0x25                                /* settings: EXT SOURCE on */
#define BUS_EFFECT 0x27C                               /* system, by slot: the effect (slot 0 = input FX) */
#define CHECK_CYCLES 60000000u                         /* the input FX is read every 0.1 s */
#define REFRESH_CYCLES 60000000u                       /* the readout follows the tracker every 0.1 s */
#define CUR_TASK (*(volatile u32 *)0x202BBBFCu)        /* the kernel's running task (its TCB) */
#define TCB_ATTR 0x10

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

EXPORT void meter_mix_begin(u32 ret, const volatile u32 *bufs) {
    u32 now = DWT_CYCCNT;
    meter_t *m = &meter;
    (void)bufs;
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
    tt.last_mix = mix;
    return m->mix_ret;
}

static void tt_publish(tt_t *t) {
    t->seq++;
    BARRIER();
    t->pub.blocks = t->w_n;
    t->pub.avg = t->w_sum / t->w_n;
    t->pub.max = t->w_max;
    t->pub.tot_max = t->w_tot;
    BARRIER();
    t->seq++;
    t->w_n = t->w_sum = t->w_max = t->w_tot = 0;
}

/* A step's cycles, with this wake's mixer: the window, the worst wake, overruns. Returns the wake's cycles. */
static u32 tt_account(tt_t *t, u32 dt, u32 budget) {
    u32 tot = clamp(clamp(dt) + t->last_mix);
    dt = clamp(dt);
    t->last_mix = 0;
    if (t->reset_ack != t->reset_req) {
        t->tot_max_ever = t->over = 0;
        t->w_n = t->w_sum = t->w_max = t->w_tot = 0;
        t->reset_ack = t->reset_req;
    }
    if (tot > budget) t->over++;
    if (tot > t->tot_max_ever) t->tot_max_ever = tot;
    t->w_n++;
    t->w_sum += dt;
    if (dt > t->w_max) t->w_max = dt;
    if (tot > t->w_tot) t->w_tot = tot;
    if (t->w_n >= TT_WINDOW) tt_publish(t);
    return tot;
}

/* After the recorder feed and tune_pairs (audio task): one tracker step while the UI wants it. */
EXPORT void tune_rx(void) {
    tt_t *t = &tt;
    t->rx++;
    t->task_attr = *(volatile u32 *)(CUR_TASK + TCB_ATTR);
    u32 st = t->state;
    if (!t->req) {
        if (st != TT_OFF) t->state = TT_OFF;
        return;
    }
    if (st == TT_SLOW) return;
    if (st == TT_OFF) t->state = TT_RUN;
    u32 budget = meter.budget ? meter.budget : NOMINAL;
    u32 t0 = DWT_CYCCNT;
    tune_fp_call(tune_fp_step, t, &tt_block.stack[STACK_BYTES / 4]);
    u32 dt = DWT_CYCCNT - t0;
    t->steps++;
    /* Stop before the audio task can starve the others: one step over a whole block, or two wakes in a row whose
     * mixer + tracker took over 9/10 of one. What the window has so far is published, to be read. */
    u32 tot = tt_account(t, dt, budget);
    t->hot = tot > budget / 10u * 9u ? t->hot + 1u : 0u;
    if (dt > budget || t->hot >= 2u) {
        t->state = TT_SLOW;
        t->slow_cycles = tot;
        if (t->w_n) tt_publish(t);
    }
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

static const char *const STATE_NAMES[] = {"OFF", "RUN", "SLOW"};
static const char *const NOTE_NAMES[] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

UI_SMALL static char *put_s(char *p, s32 v) {
    *p++ = v < 0 ? '-' : '+';
    return put_u(p, (u32)(v < 0 ? -v : v));
}

UI_SMALL static u32 two(u32 v) { return v > 99u ? 99u : v; }

/* Six lines in the popup's font (PBold, 9 px lines): test_tune_test.py checks that the widest worst case leaves the
 * popup box inside the 128 x 64 screen. */
EXPORT UI_SMALL void tune_format(const meter_window *w, const tt_window *tw, const tt_result *r, char *out) {
    const meter_t *m = &meter;
    const tt_t *t = &tt;
    u32 b = m->budget ? m->budget : NOMINAL;
    u32 st = t->state;
    char *p = out;
    if (r->analyses && r->note >= 0 && r->note < 128) {   /* none before the first analysis: the readout's first
                                                            post comes before tune_ui starts the tracker */
        p = put_str(p, NOTE_NAMES[(u32)r->note % 12u]);
        if (r->note < 12) {
            p = put_str(p, "-1");
        } else {
            p = put_u(p, (u32)r->note / 12u - 1u);
        }
    } else {
        p = put_str(p, "--");
    }
    if (r->voiced) {
        *p++ = ' ';
        p = put_s(p, r->cents < -50 ? -50 : r->cents > 50 ? 50 : r->cents);
        *p++ = 'c';
    }
    p = put_str(p, " Q");
    p = put_u(p, r->quality > 100u ? 100u : r->quality);
    *p++ = '\n';
    if (r->voiced) {
        u32 f = r->freq10 > 99999u ? 99999u : r->freq10;
        p = put_u(p, f / 10u);
        if (f < 10000u) {
            *p++ = '.';
            p = put_u(p, f % 10u);
        }
    } else {
        p = put_str(p, "--");
    }
    p = put_str(p, "Hz LV");
    p = put_u(p, (t->peak[0] > 32768u ? 32768u : t->peak[0]) * 100u / 32768u);
    p = put_str(p, t->ext ? " X1" : " X0");
    p = put_str(p, "\n1ST ");
    p = put_u(p, cap(r->first_ms));
    p = put_str(p, " LCK ");
    p = put_u(p, cap(r->lock_ms));
    p = put_str(p, "\nAVG ");
    p = put_u(p, r->locks ? cap(r->lock_sum / r->locks) : 0u);
    p = put_str(p, " N");
    p = put_u(p, two(r->locks));
    p = put_str(p, " IN");
    p = put_u(p, two(t->fx));
    p = put_str(p, "\nTRK ");
    if (st == TT_RUN) {
        p = put_u(p, two(pct(tw->avg, b)));
        *p++ = '/';
        p = put_u(p, two(pct(tw->max, b)));
    } else {
        p = put_str(p, STATE_NAMES[st < 3u ? st : 0u]);
    }
    p = put_str(p, " MIX ");
    p = put_u(p, two(pct(w->mix_avg, b)));
    p = put_str(p, "\nMAX ");
    p = put_u(p, pct(t->tot_max_ever, b));
    p = put_str(p, " OVR ");
    p = put_u(p, cap(t->over));
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

static int read_tt_window(tt_window *out) {
    tt_t *t = &tt;
    for (int tries = 0; tries < 4; ++tries) {
        u32 s = t->seq;
        BARRIER();
        if (s & 1u) continue;
        *out = t->pub;
        BARRIER();
        if (t->seq == s) return 1;
    }
    return 0;
}

static int read_result(tt_result *out, u32 *seq) {
    tt_t *t = &tt;
    for (int tries = 0; tries < 4; ++tries) {
        u32 s = t->rseq;
        BARRIER();
        if (s & 1u) continue;
        *out = t->res;
        BARRIER();
        if (t->rseq == s) {
            *seq = s;
            return 1;
        }
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
    tt_window tw;
    tt_result r;
    u32 rseq;
    char text[TEXT_MAX];
    if ((u32)PAGE >= STOCK_PAGES) return;               /* never over DOOM OS's own screens */
    if (POPUP_PENDING >= 0) return;                     /* someone else's post is queued */
    if (POPUP_SHOWN && !ours_on_screen(m)) return;      /* leave a stock message alone */
    if (!read_window(&w) || !read_tt_window(&tw) || !read_result(&r, &rseq)) return;
    tune_format(&w, &tw, &r, text);
    tt.peak[0] = tt.peak[1] = 0;                        /* a peak per readout */
    for (int i = 0; i < TEXT_MAX; ++i) {
        m->text[i] = text[i];
        if (!text[i]) break;
    }
    POPUP_POST(m->text, POPUP_MS);
    m->posted_seq = m->seq;
    tt.posted_rseq = rseq;
    m->posted_at = now;
    m->posts++;
}

static void toggle(meter_t *m, u32 now) {
    m->toggles++;
    if (!m->shown) {
        m->shown = 1;
        m->reset_req++;                                 /* HI, OVR and MAX start again */
        tt.reset_req++;
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
    if (m->shown && (m->posted_seq != m->seq || now - m->posted_at >= KEEPALIVE ||
                     (tt.rseq != tt.posted_rseq && now - m->posted_at >= REFRESH_CYCLES))) post(m, now);
}

/* Clear the tracker and its result, then hand it to the audio task (only while it is off). */
UI_SMALL static void tune_start(tt_t *t) {
    memset(&tt_block, 0, sizeof(tt_block));
    memset(&t->res, 0, sizeof(t->res));
    t->res.note = -1;
    t->rseq += 2u;                                      /* a new result: the readout refreshes */
    t->starts++;
    BARRIER();
    t->req = 1;
}

/* Every UI tick: the tracker on while the readout is shown. Every 0.1 s: the input FX and EXT SOURCE. */
EXPORT UI_SMALL void tune_ui(void) {
    tt_t *t = &tt;
    u32 want = meter.shown;
    if (!want) t->req = 0;
    if (want && !t->req && t->state == TT_OFF) tune_start(t);
    u32 now = DWT_CYCCNT;
    if (now - t->checked < CHECK_CYCLES) return;
    t->checked = now;
    t->checks++;
    t->fx = (u32)SYS_GET(SYSPRM, BUS_EFFECT, 0);
    t->ext = SET_GET(SETTINGS, EXT_SOURCE, 0) != 0;
}

/* Bounce's ui bridge (the popup tick, UI task, every millisecond) calls this in place of bnc_ui. */
EXPORT void diag_ui(int elapsed) {
    ((void (*)(int))BNC_UI)(elapsed);
    meter_ui_tick(elapsed);
    tune_ui();
}

/* Every RX block: pairs 0 and 1's peaks, and pair 0 as (L + R) / 2 for the tracker (32-byte frames, 64 of them).
 * The packet is in DTCM, which the D-cache does not cover. */
EXPORT void tune_pairs(const volatile s16 *packet) {
    tt_t *t = &tt;
    u32 p0 = t->peak[0], p1 = t->peak[1];
    for (u32 f = 0; f < FRAMES; f++) {
        const volatile s16 *q = packet + f * 16u;
        s32 l = q[0], r = q[1], l1 = q[2], r1 = q[3];
        u32 a = (u32)(l < 0 ? -l : l);
        if (a > p0) p0 = a;
        a = (u32)(r < 0 ? -r : r);
        if (a > p0) p0 = a;
        a = (u32)(l1 < 0 ? -l1 : l1);
        if (a > p1) p1 = a;
        a = (u32)(r1 < 0 ? -r1 : r1);
        if (a > p1) p1 = a;
        t->in[f] = (s16)((l + r) >> 1);
    }
    t->peak[0] = p0;
    t->peak[1] = p1;
}

/* Bounce's rx bridge (after the recorder feed, audio task) calls this in place of bnc_rx. */
EXPORT void diag_rx_c(const volatile s16 *packet) {
    ((void (*)(void))BNC_RX)();
    tune_pairs(packet);
    tune_rx();
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
