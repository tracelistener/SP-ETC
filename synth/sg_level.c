/* LEVEL for MIDI notes on the Sound Generator (hardware test build), on v9.52 (combined-test17). SG_LEVEL.md.
 *
 * A fork user's keyboard has no velocity: every note arrives at 127 and the Sound Generator plays it at full
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
 * At LEVEL 127 MIDI is as before. Pads are as before. The power-on LEVEL is 127 (the stock data's). */
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
