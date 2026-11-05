/* The Sound Generator's level (hardware test build), on v9.52 (combined-test17): LEVEL for MIDI notes (test 1) and
 * the output level of the Sound Generator and the kits (test 2). SG_LEVEL.md.
 *
 * 1. LEVEL for MIDI notes. A fork user's keyboard has no velocity: every note arrives at 127 and the Sound Generator plays it at full
 * volume. In stock 5.52 a Sound Generator note's loudness is its velocity alone: the pad and MIDI note-ons set the
 * voice's level to velocity x 100 (+0x74 now, +0x198 the level it moves to, one step a sample; 12700 = unity).
 * LEVEL (CTRL 3, setting 0x7d, also CC 72 on M.CH) is no setting of its own either: the setter writes every voice's
 * +0x198 (its getter reads the singleton's +0x198 / 100), so it turns the notes that sound down, and the next note
 * sets its own level from its velocity again. LEVEL shows that note's velocity then (a pad hit at 100 makes it 100),
 * and kits save keeps that number with the project. Only the page's pads read LEVEL, as their velocity when FIXED
 * VELOCITY (SHIFT + pad 1) is on (0x8015c0c8); MIDI never does.
 *
 * Here LEVEL is a value of its own and MIDI notes play at velocity x LEVEL / 127 (at least 1, so a note-on stays one):
 *   - sgl_param (SetParam's Sound Generator call, 0x1ff20) keeps every LEVEL that SetParam sets: CTRL 3, CC 72, a
 *     project's saved LEVEL (kits save, at each project load). Then the voices get it as before.
 *   - sgl_level_get (the LEVEL getter case, 0x80020480) returns that value, not the last note's velocity: the
 *     screen, FIXED VELOCITY's pads and kits save read the LEVEL that was set.
 *   - sgl_midi_gate (arp_midi_event's entry, 0x83fa3448): every Sound Generator MIDI note passes there, on either
 *     M.CH route, ARP on or off; a melodic note-on's velocity is scaled before it goes on. ARP off: the stock MIDI
 *     note-on plays it (the voice's level = scaled x 100). ARP on: the arp keeps the scaled velocity for its steps.
 *     Drum mode (a kit on) is left alone: its notes are pad strikes with each pad's own Level.
 *   - A LEVEL change also scales again the keys the arp holds from MIDI (from each key's own velocity), so a
 *     latched chord follows the knob; the voices already sounding follow it as before (the setter).
 * At LEVEL 127 MIDI is as before. Pads are as before. The power-on LEVEL is 127 (the stock data's).
 *
 * 2. The output level. A voice at LEVEL 127 and velocity 127 peaks at 16384 on the bus's signed 16-bit scale (-6 dBFS),
 * the scale a sample reaches the bus at from a full press (DM-404: a recorded sample plays at its PCM level). The kit
 * stage (v9.39 on) ends the mix with x2 (+6 dB) and a knee from 24576 to 32000 (kit_master_sample, in kit_mix_finish
 * for what is heard and kit_export_mix for REC and BOUNC): one sine note came out at -1.2 dBFS (in the knee, RMS
 * -3.6 dBFS, as loud as a normalized sine sample), four at -0.3 dBFS held by the knee, and kit hits at -1.3 dBFS.
 *   - sgl_mix_gate (the SG render's exit, 0x1fdd4, in place of kit_mix_gate) and sgl_mix_finish: the same stage on the
 *     kit stage's own capture of the bus, with x0.5 in melodic mode (one note -12 dBFS, sine RMS -15 dBFS; four
 *     notes can reach 0 dBFS only in phase) and x1 in drum mode (the kit engine's own level: hits at most -6.3 dBFS);
 *     the knee as it was.
 *   - sgl_export_mix (the REC exporter's bridge, 0x8353ba06, in place of kit_export_mix): v9.5's export mix halves
 *     each voice, so x1 melodic and x2 drum mode (kit_export_mix's) make a REC or BOUNC sound as it is heard.
 * The gains are powers of two and the knee is the kit stage's expression, so its results are the kit stage's exactly
 * for the same input (BOUNC writes what it wrote). */
#include "sgl_links.h"       /* the kit stage's addresses in v9.46 (written and checked by build_sg_level.py) */

typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef signed char s8;

#define EXPORT __attribute__((used))
#define STR_(x) #x
#define STR(x) STR_(x)

/* stock 5.52 and the v9.5 poly layer (the builder checks the bytes) */
#define PAGE (*(volatile short *)0x80245880u)
#define SG_PAGE 0x1E
#define LEVEL_ID 0x7D
typedef void (*param_fn)(u32 r0, int id, int value, int flags);
#define PARAM_ENGINE ((param_fn)0x8353B181u)      /* v9.5's: the stock setter on every voice */
typedef int (*void_fn)(void);
#define DISPATCH_OFF ((void_fn)0x800DED09u)       /* no task switch: the MIDI and audio tasks wait */
#define DISPATCH_ON ((void_fn)0x800DECF9u)

/* the kit stage (v9.46, arp_v9_9_3.c + kit_engine.c) */
#define KIT_MODE (*(volatile u8 *)KIT_MODE_ADDR)  /* 0 melodic, else a kit (drum mode) */
#define HELD_COUNT (*(volatile int *)HELD_COUNT_ADDR)
#define HELD_NOTE ((volatile s8 *)HELD_NOTE_ADDR)
#define HELD_VEL ((volatile u8 *)HELD_VEL_ADDR)
#define HELD_SRC ((volatile u16 *)HELD_SRC_ADDR)
#define MAXN 16
#define MIDI_SRC 0x100                             /* held_src of a MIDI key; its held_note is the MIDI note - 48 */

EXPORT volatile u8 sgl_level = 127;               /* LEVEL, as SetParam last set it */
EXPORT volatile u8 sgl_vel[128];                  /* each MIDI note's velocity as it came in (melodic) */
EXPORT volatile u32 sgl_notes;                    /* melodic MIDI note-ons seen (the tests read these) */
EXPORT volatile u32 sgl_sets;                     /* LEVEL sets */

static int scaled(int vel, int level) {
    if (level >= 127) return vel;
    int v = vel * level / 127;
    return v < 1 ? 1 : v;
}

/* From sgl_midi_gate: (note, velocity) -> the velocity the note plays at. */
EXPORT int sgl_midi_velocity(int note, int vel) {
    if (vel <= 0 || KIT_MODE) return vel;         /* note-offs; drum mode */
    if ((u32)note < 128) sgl_vel[note] = (u8)vel;
    sgl_notes = sgl_notes + 1;
    return scaled(vel, sgl_level);
}

/* SetParam's Sound Generator call (0x1ff20, from 0x800dd27a): r1 the setting, r2 its value as SetParam clamped
 * it, r3 the flags; on to v9.5's parameter engine. */
EXPORT void sgl_param(u32 r0, int id, int value, int flags) {
    if (id == LEVEL_ID) {
        int level = value < 0 ? 0 : value > 127 ? 127 : value;
        sgl_sets = sgl_sets + 1;
        if (level != sgl_level) {
            sgl_level = (u8)level;
            /* The arp holds keys only on the SG page (it forgets them off it), so a project load never
             * comes here; the knob and CC 72 come from the UI task, as the VALUE menu's arp steps do. */
            if (PAGE == SG_PAGE && HELD_COUNT > 0) {
                DISPATCH_OFF();
                int n = HELD_COUNT;
                for (int k = 0; k < n && k < MAXN; ++k) {
                    if (HELD_SRC[k] != MIDI_SRC) continue;
                    int note = HELD_NOTE[k] + 48;
                    if ((u32)note < 128 && sgl_vel[note]) HELD_VEL[k] = (u8)scaled(sgl_vel[note], level);
                }
                DISPATCH_ON();
            }
        }
    }
    PARAM_ENGINE(r0, id, value, flags);
}

/* The LEVEL getter (0x80020480, the singleton's setting 0x7d). */
EXPORT int sgl_level_get(void) {
    return sgl_level;
}

/* ---- 2. The output level ---- */
#define GAIN_MELODIC 0.5f
#define GAIN_KIT 1.0f
#define MIX_COUNT (*(volatile int *)(KIT_MIX_STATE_ADDR + 0x14))   /* kit_mix_capture's frames x channels */
#define MIX_BUS (*(int *volatile *)(KIT_MIX_STATE_ADDR + 0x18))    /* and its bus */
#define MIX_BASE ((const volatile int *)KIT_MIX_BASELINE_ADDR)     /* the bus before the SG's voices */
#define KNEE_COUNT (*(volatile u32 *)KIT_MASTER_LIMITED_ADDR)       /* kit_master_limited: samples the knee took */
typedef int (*export_fn)(int pos, int fp, int limit);
#define V95_EXPORT_MIX ((export_fn)(V95_EXPORT_MIX_ADDR | 1u))     /* v9.5's REC mix: each voice halved, summed */

EXPORT volatile u32 sgl_blocks;                   /* render blocks the stage took (the tests read these) */
EXPORT volatile u32 sgl_exports;                  /* REC frames */

/* The kit stage's master with another gain: kit_master_sample's knee, in its order (-ffp-contract=off). */
static int sgl_master(int input, float gain) {
    float y = (float)input * gain, a = y < 0 ? -y : y;
    if (a > 24576) {
        a = 24576 + 7424 * (a - 24576) / (7424 + a - 24576);
        y = y < 0 ? -a : a;
        KNEE_COUNT = KNEE_COUNT + 1;
    }
    return (int)y;
}

/* The SG render's end (from sgl_mix_gate): the SG's part of the bus through the stage, as kit_mix_finish. */
EXPORT void sgl_mix_finish(int *bus, int frames, int channels) {
    if (bus != MIX_BUS || frames * channels != MIX_COUNT) return;
    float gain = KIT_MODE ? GAIN_KIT : GAIN_MELODIC;
    int n = MIX_COUNT;
    for (int i = 0; i < n; ++i) bus[i] = MIX_BASE[i] + sgl_master(bus[i] - MIX_BASE[i], gain);
    MIX_COUNT = 0;
    sgl_blocks = sgl_blocks + 1;
}

/* r4 bus, r5 frames, r6 channels (the SG render stub's frame); its pop returns from the stub, as kit_mix_gate's. */
__attribute__((naked, used)) EXPORT void sgl_mix_gate(void) {
    __asm__ volatile("mov r0, r4\n\tmov r1, r5\n\tmov r2, r6\n\tbl sgl_mix_finish\n\tpop.w {r4, r5, r6, r7, r8, pc}\n");
}

/* The REC exporter's frame (pos, frames, limit), from its bridge: v9.5's mix, then the stage at twice the gain. */
EXPORT int sgl_export_mix(int pos, int fp, int limit) {
    int y = V95_EXPORT_MIX(pos, fp, limit);
    sgl_exports = sgl_exports + 1;
    return sgl_master(y, KIT_MODE ? 2 * GAIN_KIT : 2 * GAIN_MELODIC);
}

/* arp_midi_event's entry (self, note, velocity, r3): the velocity scaled, then arp_midi_event's first three
 * instructions (displaced by the jump here) and on at the fourth. */
__attribute__((naked, used)) EXPORT void sgl_midi_gate(void) {
    __asm__ volatile(
        "push {r0, r1, r3, lr}\n\t"
        "mov r0, r1\n\t"
        "mov r1, r2\n\t"
        "bl sgl_midi_velocity\n\t"
        "mov r2, r0\n\t"
        "pop {r0, r1, r3, lr}\n\t"
        "push.w {r4, r5, r6, r7, r8, r9, lr}\n\t"
        "sub sp, #4\n\t"
        "movw r6, #" STR(KIT_MODE_LO) "\n\t"
        "movw r12, #" STR(MIDI_RESUME_LO) "\n\t"
        "movt r12, #" STR(MIDI_RESUME_HI) "\n\t"
        "bx r12\n");
}
