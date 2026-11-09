/* FX deep edit (test build): extra screens on the FX screen for the effects (the input FX and BUS 1-4) that
 * edit the effect parameters stock 5.52 never sends to the effects chip (BMC).
 *
 * On the FX screen VALUE press steps its screens, and the screen stays from that press on, as with REMAIN + FX
 * (test5: however the screen was opened; until EXIT, REMAIN, or that FX button again). After screen 1 and screen 2
 * (where the effect has CTRL 4-6) come the effect's extra screens: three settings a screen, on CTRL 1-3, in the
 * stock popup:
 *
 *   TAPE ECHO 3/5
 *   C1 SYNC 0
 *   C2 BASS 15
 *   C3 TREBLE 15
 *
 * then screen 1 again. The slot is the one the CTRL knobs drive (settings 0x3a: 0 the input FX, 1-4 BUS 1-4,
 * what the knob path 0x800cc030 uses) and the effect that slot's (system 0x27c[slot], what the knob path and
 * the FX screen read). Test 4 adds the input FX (test 2 and 3 offered BUS 1-4 only, so with the knobs on the
 * input FX VALUE only flipped screens 1 and 2). An effect without extra settings keeps stock's VALUE (test4's
 * "NO EXTRA SETTINGS" note is gone since test7). An effect's settings are
 * its parameters that are not in its six-ID knob record (fx_deep_edit_tables.h, made by build_fx_deep_edit.py
 * from the firmware's tables and DM-404's fxmap.json). On an extra screen any button but VALUE and SHIFT leaves
 * it and then does what it always does; pads work as usual. (Test 1's TOP page, EXIT + VALUE, is gone, and
 * test 3 drops test 2's FX button hold, which kept MFX's effect choice away: an FX button alone is stock's.)
 *
 * Every change is one DT1 through the stock builder 0x800d8118 (link 0x80592500, parameter ID,
 * slot = bus, value), the call the bus-effect knobs end in, inside the firmware's own min/max for
 * the ID (0x801ad1fc/0x801ac830). A setting shows the firmware's default (0x801abe64) until edited.
 * Edited values live here, per slot and effect, in RAM only: a power cycle forgets them. The
 * firmware's own state is never touched.
 *
 * Re-sending: stock (re)selects an effect by sending its FxType (0x7e + slot), from the effect
 * select 0x800d0cf0, the system setter and the bus-swap path; it never re-sends an effect's knob
 * parameters on an effect change (only the boot chip reset 0x801803b0 sends them in bulk, after
 * setting every slot to FxType 0). So the jump written
 * over the builder's first ten bytes runs fde_dt1 for every DT1 the firmware sends: the frame goes
 * out unchanged through the displaced instructions (fde_dt1_stock), and an FxType for the input FX or
 * BUS 1-4 is followed by that slot's edited values for the effect it selects (fde_dt1_fxtype).
 *
 * The input FX (test9): it has its own screen (RECORD SETTING, then VALUE: INPUT FX Setting, the reference manual
 * p. 36-37), not the FX screen, so on the unit the knobs never drive it there and its extra screens never came (test 4
 * reached them in the emulator only by setting 0x3a to 0). On the main screen, hold VALUE and press EXT SOURCE: the
 * input FX's extra screens, numbered among themselves ("GT AMP SIM 1/4"); VALUE steps them and closes after the last,
 * CTRL 1-3 edit them on slot 0, any other button leaves. That EXT SOURCE press and its release are taken, so the
 * external input is not switched; an input FX without extra settings shows nothing.
 *
 * Test10: on the unit that chord, caught by TOP's page filter, only switched the input off, so it never arrived there
 * as one (another page, or a mode that takes keys before the page). Now the UI dispatcher's key press, key release
 * and knob handlers (event types 5, 6 and 9) hand every event to fde_key_down / fde_key_up / fde_knob first, on any
 * page and before the modes and the key bitmap see it, and VALUE's hold is tracked there as well as read from the
 * bitmap. The input FX's screens are worked there too (VALUE, CTRL 1-3, leaving); TOP's filter keeps the BUS screens.
 *
 * Test11: HOLD + VALUE (press), on any page, switches the hidden settings off: on each slot, the edited settings of
 * the effect it has go back to the firmware's defaults (the effect sounds as on stock), the FX screen's VALUE and
 * VALUE + EXT SOURCE are stock's, and an FxType re-sends nothing. HOLD + VALUE again switches them on and sends the
 * edits again. Popup "HIDDEN FX OFF" / "HIDDEN FX ON". The edits are kept either way.
 *
 * Test15 (the user on v9.52: the hidden settings never came on the Sound Generator page, the kits or the guitar synth
 * screen, nor after REMAIN + FX on an unlit effect until the effect went off and on): stock's generic key handler sends
 * VALUE to the FX screen on the main page only. REMAIN + FX on an unlit effect opens page 34, and the Sound Generator
 * page is page 30; their own handlers keep VALUE (DM-404: VALUE there never reached the FX screen's toggle, or toggled
 * screen 2 itself on page 34). Now the dispatcher's key press handler sends VALUE to the FX screen up on any page
 * (fx_up: stock's pointer, else TOP's list) and takes it, the knobs work any extra screen there, and any key but VALUE
 * and SHIFT leaves one there.
 *
 * The tables are generated by build_fx_deep_edit.py.
 */
typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;

#define EXPORT __attribute__((used))

#define BMC 0x80592500u                                  /* the chip link object 0x800d8118 takes */
#define SYSPRM 0x82DFEED0u                               /* the system parameter object */
#define SETTINGS 0x82E01144u                             /* the settings object */
#define SYS_GET ((s32 (*)(u32, s32, s32))0x800DA011u)    /* system GetParam(object, ID, index) */
#define SET_GET ((s32 (*)(u32, s32, s32))0x800D94D9u)    /* settings GetParam(object, ID, index) */
#define POPUP ((void (*)(const char *, s32))0x800D3FF1u)
#define DOOM_FILTER ((s32 (*)(void *, const s16 *))0x6031C8F9u)  /* TOP's +0x08 in DOOM OS ED5E */
#define DEFAULTS ((const s32 *)0x801ABE64u)              /* by parameter ID: default, max, min */
#define MAXIMA ((const s32 *)0x801AC830u)
#define MINIMA ((const s32 *)0x801AD1FCu)

#define KNOB_BUS 0x3A                                    /* settings: 0 input FX, 1-4 BUS 1-4 */
#define BUS_EFFECT 0x27C                                 /* system, by slot: the effect, 0 none */
#define FXTYPE0 0x7E                                     /* Effect_FxType0 + slot */
#define SLOTS 5                                          /* the input FX (0) and BUS 1-4 */
#define EFFECTS 49

#define RECORDS ((const s32 *)0x802E5B40u)               /* by effect: the six parameter IDs CTRL 1-6 send */
#define VIEW_REMAIN 0x1B3F                               /* the FX screen: REMAIN held when it showed */
#define REMAIN_MODE ((volatile u8 *)0x80592320u)          /* set with it by the show method (0x80146f7a) */
#define VIEW_SCREEN2 0x1B40                              /* the FX screen: screen 2 (CTRL 4-6) */
#define FX_SHOWN ((u8 *volatile *)0x8059259Cu)             /* stock's pointer to the FX screen, set when it opens */
#define FX_VIEW_VTABLE 0x802269C0u                        /* the FX screen's vtable (its constructor 0x80147ba0) */
#define TOP_OBJECT ((u8 *const volatile *)0x80CFD350u)      /* TOP's page object (its registry handler's) */
#define VIEW_AT ((u8 *(*)(u8 *, s32))0x800A01C1u)          /* (TOP + 0x38, i): TOP's i-th view, 0 past the last */
#define VIEWS 0x200                                      /* as far as the generic key handler looks */

#define EV_KEY 5
#define EV_KEY_UP 6
#define EV_KNOB 9                                        /* CTRL k: (9, k, position 0..127) */
#define KEY_SHIFT 0x2A
#define KEY_VALUE 0x31
#define KEY_EXT_SOURCE 0x12
#define KEY_HOLD 0x11
#define TOGGLE_MS 1500                                   /* the HIDDEN FX OFF / ON popup */
#define KEYS ((const volatile u8 *)0x80592448u)          /* held keys: bit (k & 7) of KEYS[k >> 3] */
#define KNOB_MAX 127
#define PER_SCREEN 3
#define SCREEN_MS 600000                                 /* an extra screen's popup: until it is left */
#define GONE_MS 1                                        /* leaving: the popup goes at the next tick */

/* Test11: the edits and the switch kept over a restart, in one file on the internal storage beside stock's own
 * there (B:/_emphasis.bin, B:/_BackSamplingRec.bin): a record per edited setting (slot, value, parameter ID), so a
 * build whose settings differ drops what it doesn't know rather than putting a value on another setting. Read the
 * first time TOP's filter sees an event (the main screen after the boot) or the user opens or switches anything;
 * written after an edit or a switch at the next key release with no FX screen and no extra screen up (test12: on the
 * unit, writing it with the FX screen up sent the display back to the main screen). */
#define FILE_OPEN ((s32 (*)(const char *, s32))0x800DEC61u)    /* 0 read, 0x601 write (create, truncate); < 0 fails */
#define FILE_READ ((s32 (*)(s32, void *, s32))0x800DEC49u)
#define FILE_WRITE ((s32 (*)(s32, const void *, s32))0x800DD9B9u)
#define FILE_CLOSE ((s32 (*)(s32))0x800DEBD9u)
#define FILE_MAGIC 0x53485846u                           /* "FXHS" */
#define FILE_VERSION 1
#define FILE_HEADER 12                                   /* magic, version, off, records (u16), FNV-1a of the rest */
#define FILE_RECORDS (SLOTS * FDE_PARAMS)
#define FNV 2166136261u

/* Test13: the FX screen drawn again after HOLD + VALUE's popup. Stock draws the page under a popup that ends, and the FX
 * screen draws only on a change, so on the unit the main screen showed while the FX screen was still up (its effect lit).
 * The FX screen's update (its vtable +0x28, every 50 ms, through fde_fx_update) takes a screen 2 value it never draws as
 * a change and draws the whole screen. */
#define FX_VIEW_UPDATE ((void (*)(u8 *))0x80146599u)       /* the stock update */
#define DRAWN_SCREEN2 ((volatile s32 *)0x8059232Cu)        /* screen 2 as the update last drew it: 0 or 1 */
#define POPUP_LEFT ((const volatile s32 *)0x805922B4u)      /* the popup on the screen: ms left, < 1 with none */
#define CLOCK ((const volatile u32 *)0x8059226Cu)           /* the audio clock: + 32 a 64-frame block, 24 a ms */
#define CLOCK_MS 24u

#include "fx_deep_edit_tables.h"

struct fde_state {
    u8 screen;           /* the extra screen shown, 1..; 0: the stock screens */
    u8 input;            /* test9: the input FX's extra screens, opened with VALUE + EXT SOURCE */
    u8 ext_held;         /* that EXT SOURCE press was taken: so is its release */
    u8 value_down;       /* test10: VALUE held, as the dispatcher's key handlers saw it */
    u8 bus, effect;      /* as shown: the slot (0 the input FX, 1-4 BUS 1-4) and its effect */
    u8 off;              /* test11: the hidden settings switched off (HOLD + VALUE) */
    u8 value_taken;      /* that VALUE press was taken: so is its release */
    u32 sent;            /* edits sent, since boot */
    u32 resent;          /* values sent again after an FxType, since boot */
    u8 loaded;           /* test11: the file was looked for */
    u8 dirty;            /* an edit not in the file yet */
    u8 redraw;           /* test13: the FX screen draws again once the switch's popup is gone ... */
    u8 spare;
    u32 loads, bad_files, saves, save_errors;
    u32 redraw_at;       /* ... at this audio clock or later */
    u32 redraws;
    u32 repairs;         /* test14: stock's FX screen pointer put back */
};

EXPORT volatile struct fde_state fde;
EXPORT u8 fde_chip[SLOTS];                              /* test13: the effect each slot's last FxType gave the chip */
EXPORT u8 fde_values[SLOTS][FDE_PARAMS];                /* by slot and setting */
EXPORT u8 fde_edited[SLOTS][FDE_PARAMS];
EXPORT char fde_text[40];
EXPORT const char fde_path[] = "B:/_fx_hidden.bin";
EXPORT u8 fde_file[FILE_HEADER + 4 * FILE_RECORDS] __attribute__((aligned(4)));

/* The stock builder's first three instructions, displaced by the jump to fde_dt1 written over them,
 * then on into the builder at 0x800d8122. Its own return ends the call. */
__attribute__((naked, noinline)) EXPORT u32 fde_dt1_stock(u32 link, s32 id, s32 slot, s32 value) {
    __asm__ volatile(
        "push.w {r4, r5, r6, r7, r8, r9, r10, r11, lr}\n\t"
        "sub sp, #12\n\t"
        "movw r9, #0xe1c8\n\t"
        "movw r12, #0x8123\n\t"
        "movt r12, #0x800d\n\t"
        "bx r12\n\t");
}

static u32 value_of(u32 bus, u32 i) {
    return fde_edited[bus][i] ? fde_values[bus][i] : (u32)DEFAULTS[fde_ids[i]];
}

/* After the firmware selects effect fx on a slot: that slot's edited values for fx, again. */
static void resend(u32 bus, s32 fx) {
    if ((u32)fx >= EFFECTS)
        return;
    for (u32 i = fde_first[fx], end = i + fde_count[fx]; i < end; i++) {
        if (fde_edited[bus][i]) {
            fde_dt1_stock(BMC, fde_ids[i], bus, fde_values[bus][i]);
            fde.resent++;
        }
    }
}

/* An FxType for the input FX or BUS 1-4: the frame, then that slot's edited values for the effect it selects
 * (none while the hidden settings are off). Test13: the effect is noted as the chip's for that slot. */
EXPORT u32 fde_dt1_fxtype(u32 link, s32 id, s32 slot, s32 value) {
    u32 r = fde_dt1_stock(link, id, slot, value);
    fde_chip[id - FXTYPE0] = (u8)value;
    if (!fde.off)
        resend(id - FXTYPE0, value);
    return r;
}

/* Every DT1 the firmware sends comes here first (the jump at 0x800d8118). Anything but an FxType for the
 * input FX or BUS 1-4 (0x7e..0x82) goes straight on, with the caller's own stack and return: the builder runs exactly as stock,
 * down to the frames it builds from leftover stack for the -1 entries of the knob records, which the boot
 * chip reset sends. */
__attribute__((naked)) EXPORT void fde_dt1(void) {
    __asm__ volatile(
        "sub r12, r1, #0x7e\n\t"
        "cmp r12, #4\n\t"
        "bhi.w fde_dt1_stock\n\t"
        "b.w fde_dt1_fxtype\n\t");
}

static u32 fnv(const u8 *p, u32 n, u32 h) {
    while (n--)
        h = (h ^ *p++) * 16777619u;
    return h;
}

static u32 get32(const u8 *p) {
    return p[0] | p[1] << 8 | p[2] << 16 | (u32)p[3] << 24;
}

static void put32(u8 *p, u32 v) {
    p[0] = (u8)v;
    p[1] = (u8)(v >> 8);
    p[2] = (u8)(v >> 16);
    p[3] = (u8)(v >> 24);
}

/* A value inside the firmware's range for the setting, as a byte holds it (what the knobs give). */
static u32 clamp(u32 id, s32 v) {
    s32 lo = MINIMA[id], hi = MAXIMA[id];
    if (hi > 255)
        hi = 255;
    if (lo < 0)
        lo = 0;
    return (u32)(v < lo ? lo : v > hi ? hi : v);
}

/* The file into RAM, once (test11): a missing file leaves everything as it is; a short, long or bad one (magic,
 * version, size, sum) too. Records for settings this build doesn't have are dropped, values kept in range. Then,
 * switched on, each slot's edits for the effect it has go to the chip. */
static void load(void) {
    fde.loaded = 1;
    s32 fd = FILE_OPEN(fde_path, 0);
    if (fd < 0)
        return;
    s32 n = FILE_READ(fd, fde_file, (s32)sizeof fde_file);
    FILE_CLOSE(fd);
    u32 count = (u32)fde_file[6] | (u32)fde_file[7] << 8;
    if (n < FILE_HEADER || (u32)n != FILE_HEADER + 4 * count || get32(fde_file) != FILE_MAGIC ||
        fde_file[4] != FILE_VERSION || get32(fde_file + 8) != fnv(fde_file + FILE_HEADER, 4 * count,
                                                                  fnv(fde_file, 8, FNV))) {
        fde.bad_files++;
        return;
    }
    for (u32 k = 0; k < count; k++) {
        const u8 *r = fde_file + FILE_HEADER + 4 * k;
        u32 bus = r[0], id = (u32)r[2] | (u32)r[3] << 8;
        for (u32 i = 0; i < FDE_PARAMS && bus < SLOTS; i++) {
            if (fde_ids[i] == id) {
                fde_values[bus][i] = (u8)clamp(id, r[1]);
                fde_edited[bus][i] = 1;
                break;
            }
        }
    }
    fde.off = fde_file[5] & 1;
    if (!fde.off)
        for (u32 bus = 0; bus < SLOTS; bus++)
            resend(bus, fde_chip[bus]);                /* test13: the chip's effect, not 0x27c (the boot's first */
                                                       /* event can be an FX button stock hasn't handled yet) */
    fde.loads++;
}

/* RAM into the file (test11): every edited setting and the switch, written whole (create, truncate). A failed open
 * or a short write is counted and the edits stay pending. */
static void save(void) {
    u32 count = 0;
    for (u32 bus = 0; bus < SLOTS; bus++) {
        for (u32 i = 0; i < FDE_PARAMS; i++) {
            if (fde_edited[bus][i]) {
                u8 *r = fde_file + FILE_HEADER + 4 * count++;
                r[0] = (u8)bus;
                r[1] = fde_values[bus][i];
                r[2] = (u8)fde_ids[i];
                r[3] = (u8)(fde_ids[i] >> 8);
            }
        }
    }
    put32(fde_file, FILE_MAGIC);
    fde_file[4] = FILE_VERSION;
    fde_file[5] = fde.off;
    fde_file[6] = (u8)count;
    fde_file[7] = (u8)(count >> 8);
    put32(fde_file + 8, fnv(fde_file + FILE_HEADER, 4 * count, fnv(fde_file, 8, FNV)));
    s32 size = (s32)(FILE_HEADER + 4 * count), n = -1;
    s32 fd = FILE_OPEN(fde_path, 0x601);
    if (fd >= 0) {
        n = FILE_WRITE(fd, fde_file, size);
        FILE_CLOSE(fd);
    }
    if (n == size) {
        fde.dirty = 0;
        fde.saves++;
    } else {
        fde.save_errors++;
    }
}

static void ready(void) {
    if (!fde.loaded)
        load();
}

static char *put(char *p, const char *s) {
    while (*s)
        *p++ = *s++;
    return p;
}

static char *number(char *p, u32 v) {
    if (v >= 100)
        *p++ = (char)('0' + v / 100);
    if (v >= 10)
        *p++ = (char)('0' + v / 10 % 10);
    *p++ = (char)('0' + v % 10);
    return p;
}

/* The slot the knobs drive (0 the input FX, 1-4 BUS 1-4), or the input FX when VALUE + EXT SOURCE opened the
 * screens, and its effect, as the firmware has them now. Unchanged since the extra screens last showed them: 1. */
static u32 follow(void) {
    s32 bus = fde.input ? 0 : SET_GET(SETTINGS, KNOB_BUS, 0);
    s32 fx = (u32)bus < SLOTS ? SYS_GET(SYSPRM, BUS_EFFECT, bus) : 0;
    if ((u32)bus > 255)
        bus = 255;
    if ((u32)fx >= EFFECTS)
        fx = 0;
    if ((u32)bus == fde.bus && (u32)fx == fde.effect)
        return 1;
    fde.bus = (u8)bus;
    fde.effect = (u8)fx;
    return 0;
}

/* The effect's extra screens: its settings, three a screen; none off the five slots. */
static u32 extra_screens(void) {
    return fde.bus < SLOTS ? (fde_count[fde.effect] + PER_SCREEN - 1) / PER_SCREEN : 0;
}

/* Stock's screen 2: the effect has CTRL 4-6 (its knob record, as the FX screen's update 0x801465de reads it). */
static u32 has_screen2(u32 fx) {
    const s32 *r = RECORDS + fx * 6;
    return fx && (r[3] != -1 || r[4] != -1 || r[5] != -1);
}

/* An extra screen in the popup: the effect and the screen's number among all of them, then a line per knob.
 *
 *   TAPE ECHO 3/5
 *   C1 SYNC 0
 *   C2 BASS 15
 *   C3 TREBLE 15
 */
static void show(void) {
    u32 bus = fde.bus, fx = fde.effect, before = fde.input ? 0 : 1 + has_screen2(fx);
    u32 first = fde_first[fx], end = first + fde_count[fx], at = first + (fde.screen - 1) * PER_SCREEN;
    char *p = put(fde_text, fde_effect_names[fx]);
    *p++ = ' ';
    p = number(p, before + fde.screen);
    *p++ = '/';
    p = number(p, before + extra_screens());
    for (u32 k = 0; k < PER_SCREEN && at + k < end; k++) {
        p = put(p, "\nC");
        *p++ = (char)('1' + k);
        *p++ = ' ';
        p = put(p, fde_names[at + k]);
        *p++ = ' ';
        p = number(p, value_of(bus, at + k));
    }
    *p = 0;
    POPUP(fde_text, SCREEN_MS);
}

static void leave(void) {
    fde.screen = 0;
    fde.input = 0;
    POPUP(fde_text, GONE_MS);
}

/* The FX screen while it is on TOP's view stack, found by its vtable, else 0. Test14: not by stock's pointer to it
 * (0x8059259c), which every page's constructor clears (0x800ce27c) while TOP keeps its FX screen up; the generic key
 * handler then sent VALUE to no FX screen, so the hidden settings (and stock's screen 2) didn't come until the FX
 * button opened a new one. */
static u8 *fx_screen(void) {
    u8 *top = *TOP_OBJECT, *found = 0;
    if (!top)
        return 0;
    for (s32 i = 0; i < VIEWS; i++) {
        u8 *w = VIEW_AT(top + 0x38, i);
        if (!w)
            break;
        if (*(const u32 *)w == FX_VIEW_VTABLE)
            found = w;
    }
    return found;
}

/* Test15: the FX screen that is up, on any page. While TOP's object is there (the main page, and pages built over it),
 * the one on TOP's list (test14: a page constructor clears stock's pointer while TOP keeps its screen; it is put back
 * here too, as TOP's filter does, since a VALUE press taken in the dispatcher never reaches that filter). Where TOP's
 * object is gone (the unit's REMAIN + FX on an unlit effect, page 34, and the Sound Generator page 30, where the kits
 * and the guitar synth screen are), stock's pointer: it is set while an FX screen is up and cleared when it closes,
 * by EXIT or after its 2 s (DM-404, on pages 1, 30 and 34). */
static u8 *fx_up(void) {
    u8 *v;
    if (*TOP_OBJECT) {
        v = fx_screen();
        if (v && *FX_SHOWN != v) {
            *FX_SHOWN = v;
            fde.repairs++;
        }
        return v;
    }
    v = *FX_SHOWN;
    return v && !((u32)v & 3u) && *(const u32 *)v == FX_VIEW_VTABLE ? v : 0;
}

/* VALUE pressed on the FX screen: stock's toggle of screens 1 and 2 (0x801479a0, called with the screen from
 * the generic key handler 0x800cba46) jumps here. Screen 1, screen 2 where the effect has one, then the extra
 * screens, then screen 1 again. A screen that opened without REMAIN held (stock: the press does nothing, VALUE
 * held peeks at screen 2) is held from this press on, as if REMAIN had been (test5: on the unit the screen came
 * up unheld however REMAIN was used, so VALUE only peeked); an effect with neither screen 2 nor extra settings
 * leaves it stock. */
EXPORT void fde_value(u8 *screen) {
    ready();
    if (fde.off) {                                     /* test11: the hidden settings off: stock's toggle */
        if (screen[VIEW_REMAIN])
            screen[VIEW_SCREEN2] ^= 1;
        return;
    }
    if (!screen[VIEW_REMAIN]) {
        follow();
        if (!has_screen2(fde.effect) && !extra_screens())
            return;
        screen[VIEW_REMAIN] = 1;
        *REMAIN_MODE = 1;
    }
    if (fde.screen) {
        if (follow() && fde.screen < extra_screens()) {
            fde.screen++;
            show();
            return;
        }
        leave();
        screen[VIEW_SCREEN2] = 0;
        return;
    }
    follow();
    if (has_screen2(fde.effect) && !screen[VIEW_SCREEN2]) {
        screen[VIEW_SCREEN2] = 1;
        return;
    }
    if (extra_screens()) {
        fde.screen = 1;
        show();
        return;
    }
    screen[VIEW_SCREEN2] ^= 1;                         /* stock's toggle */
}

/* CTRL k turned on an extra screen: its setting follows the knob across the firmware's range (one DT1 per
 * change); a knob without a setting there does nothing. */
static void knob(u32 k, s32 raw) {
    if (!follow()) {
        leave();
        return;
    }
    u32 bus = fde.bus, i = fde_first[fde.effect] + (fde.screen - 1) * PER_SCREEN + k;
    if (i >= fde_first[fde.effect] + fde_count[fde.effect])
        return;
    u32 id = fde_ids[i];
    s32 lo = MINIMA[id], hi = MAXIMA[id];
    if (hi > 255)
        hi = 255;
    if (lo < 0)
        lo = 0;
    raw = raw < 0 ? 0 : raw > KNOB_MAX ? KNOB_MAX : raw;
    s32 v = lo + ((hi - lo) * raw + KNOB_MAX / 2) / KNOB_MAX;
    if ((u32)v != value_of(bus, i)) {
        fde_values[bus][i] = (u8)v;
        fde_edited[bus][i] = 1;
        fde.dirty = 1;
        fde_dt1_stock(BMC, (s32)id, (s32)bus, v);
        fde.sent++;
    }
    show();
}

/* VALUE held, EXT SOURCE pressed (test9): the input FX's first extra screen, if it has any. */
static void input_open(void) {
    ready();
    fde.screen = 0;
    fde.input = 1;
    follow();
    if (fde.effect && extra_screens()) {
        fde.screen = 1;
        show();
    } else {
        fde.input = 0;
    }
}

static u32 value_held(void) {
    return fde.value_down || ((KEYS[KEY_VALUE >> 3] >> (KEY_VALUE & 7)) & 1);
}

/* HOLD + VALUE (test11): the hidden settings off, or on again. Each slot's edited settings of the effect the chip has
 * there get the firmware's default (off) or the edit (on) again, one DT1 each. An FX screen up stays, held as a VALUE
 * press there holds it, and draws again once the popup is gone (test13). The switch goes to the file with the edits,
 * later (fde_key_up). */
static void toggle(void) {
    ready();
    if (fde.screen)
        leave();
    u8 *v = fx_up();                                   /* test15: on any page */
    if (v) {
        v[VIEW_REMAIN] = 1;
        *REMAIN_MODE = 1;
        fde.redraw = 1;
        fde.redraw_at = *CLOCK + (TOGGLE_MS + 100) * CLOCK_MS;
    }
    fde.off ^= 1;
    fde.dirty = 1;
    for (u32 bus = 0; bus < SLOTS; bus++) {
        s32 fx = fde_chip[bus];
        if ((u32)fx >= EFFECTS)
            continue;
        for (u32 i = fde_first[fx], end = i + fde_count[fx]; i < end; i++) {
            if (fde_edited[bus][i]) {
                fde_dt1_stock(BMC, fde_ids[i], (s32)bus, fde.off ? DEFAULTS[fde_ids[i]] : fde_values[bus][i]);
                fde.resent++;
            }
        }
    }
    POPUP(fde.off ? "HIDDEN FX OFF" : "HIDDEN FX ON", TOGGLE_MS);
}

/* Every key press, on any page, before the dispatcher's own handling (test10): 1 takes it. HOLD + VALUE switches
 * the hidden settings off or on (test11). VALUE + EXT SOURCE opens the input FX's extra screens; on them VALUE steps
 * (and closes after the last), SHIFT passes, any other key leaves and goes on. */
EXPORT u32 fde_key_down(const s16 *ev) {
    s32 key = ev[1];
    if (key == KEY_VALUE && ((KEYS[KEY_HOLD >> 3] >> (KEY_HOLD & 7)) & 1)) {
        toggle();
        fde.value_taken = 1;
        return 1;
    }
    if (key == KEY_EXT_SOURCE && value_held() && !fde.off) {
        input_open();
        fde.ext_held = 1;
        return 1;
    }
    if (fde.input && fde.screen) {
        if (key == KEY_VALUE) {
            if (follow() && fde.screen < extra_screens()) {
                fde.screen++;
                show();
            } else {
                leave();
            }
            return 1;
        }
        if (key != KEY_SHIFT)
            leave();
    }
    if (fde.screen && !fde.input && key != KEY_VALUE && key != KEY_SHIFT)
        leave();                                       /* test15: a BUS extra screen, left on any page (TOP's filter */
                                                       /*   did it on TOP only) */
    if (key == KEY_VALUE)
        fde.value_down = 1;
    if (key == KEY_VALUE && !fde.off) {
        u8 *v = fx_up();
        if (v) {                                       /* test15: VALUE on an FX screen up on any page steps it here: */
            fde_value(v);                              /*   stock's generic key handler sends it to the screen on the */
            fde.value_taken = 1;                       /*   main page only (page 34's and the Sound Generator page's */
            return 1;                                  /*   own handlers keep it) */
        }
    }
    return 0;
}

/* Every key release (test10): VALUE's hold ends; the release of an EXT SOURCE press the chord took is taken too (the
 * press never set its bit, so the bitmap stays right). Test11: edits or a switch not in the file yet are written here,
 * once no FX screen and no extra screen is up (never while one is, never on a pad). */
EXPORT u32 fde_key_up(const s16 *ev) {
    s32 key = ev[1];
    if (fde.dirty && !fde.screen && !fx_up())          /* test15: an FX screen up on any page */
        save();
    if (key == KEY_VALUE && fde.value_taken) {
        fde.value_taken = 0;
        fde.value_down = 0;                            /* test15: a taken press counts as held until here */
        return 1;
    }
    if (key == KEY_VALUE)
        fde.value_down = 0;
    if (key == KEY_EXT_SOURCE && fde.ext_held) {
        fde.ext_held = 0;
        return 1;
    }
    return 0;
}

/* Every knob turn (test10): on the input FX's extra screens CTRL 1-3 are their settings'. Test15: on any extra screen,
 * on any page (TOP's filter took the BUS screens' on TOP only). */
EXPORT u32 fde_knob(const s16 *ev) {
    s32 k = ev[1];
    if (fde.screen && (u32)(k - 1) < PER_SCREEN) {
        knob((u32)(k - 1), ev[2]);
        return 1;
    }
    return 0;
}

/* The dispatcher's key press handler (0x8003abd0, event type 5) jumps here: fde_key_down first; unless it takes the
 * event, the four displaced instructions and on at 0x8003abdc. */
__attribute__((naked)) EXPORT void fde_down_bridge(void) {
    __asm__ volatile(
        "push {r0, lr}\n\t"
        "bl fde_key_down\n\t"
        "mov r12, r0\n\t"
        "pop {r0, lr}\n\t"
        "cmp r12, #0\n\t"
        "it ne\n\t"
        "bxne lr\n\t"
        "push {r4, r5, r6, r7, lr}\n\t"
        "sub sp, #4\n\t"
        "ldrsh.w r4, [r0, #2]\n\t"
        "movw r0, #0xd314\n\t"
        "movw r12, #0xabdd\n\t"
        "movt r12, #0x8003\n\t"
        "bx r12\n\t");
}

/* The key release handler (0x8003ada0, type 6): fde_key_up first; else the three displaced instructions, on at
 * 0x8003adaa. */
__attribute__((naked)) EXPORT void fde_up_bridge(void) {
    __asm__ volatile(
        "push {r0, lr}\n\t"
        "bl fde_key_up\n\t"
        "mov r12, r0\n\t"
        "pop {r0, lr}\n\t"
        "cmp r12, #0\n\t"
        "it ne\n\t"
        "bxne lr\n\t"
        "push {r4, r5, r7, lr}\n\t"
        "ldrsh.w r4, [r0, #2]\n\t"
        "movw r0, #0xd314\n\t"
        "movw r12, #0xadab\n\t"
        "movt r12, #0x8003\n\t"
        "bx r12\n\t");
}

/* The knob handler (0x8003a8d8, type 9): fde_knob first; else the four displaced instructions, on at 0x8003a8e4. */
__attribute__((naked)) EXPORT void fde_knob_bridge(void) {
    __asm__ volatile(
        "push {r0, lr}\n\t"
        "bl fde_knob\n\t"
        "mov r12, r0\n\t"
        "pop {r0, lr}\n\t"
        "cmp r12, #0\n\t"
        "it ne\n\t"
        "bxne lr\n\t"
        "push {r4, r5, r6, lr}\n\t"
        "mov r6, r0\n\t"
        "ldrsh.w r4, [r0, #2]\n\t"
        "ldrsh.w r5, [r0, #4]\n\t"
        "movw r12, #0xa8e5\n\t"
        "movt r12, #0x8003\n\t"
        "bx r12\n\t");
}

/* TOP's page filter (vtable 0x8022ce5c +0x08): on an extra screen CTRL 1-3 are its settings', and any button
 * but VALUE and SHIFT leaves it and then does what it always does. Everything else goes on to DOOM OS's filter
 * as before. (The input FX's screens are worked in the dispatcher's handlers above, before any page.) */
/* The FX screen's update (its vtable +0x28 points here; test13): after HOLD + VALUE on it, once the popup's time is
 * over and no popup is on the screen, the screen draws itself again; then the stock update. */
EXPORT void fde_fx_update(u8 *view) {
    if (fde.redraw && (s32)(*CLOCK - fde.redraw_at) >= 0 && *POPUP_LEFT < 1) {
        fde.redraw = 0;
        *DRAWN_SCREEN2 = -1;
        fde.redraws++;
    }
    FX_VIEW_UPDATE(view);
}

EXPORT s32 fde_filter(void *page, const s16 *ev) {
    s32 type = ev[0], what = ev[1];
    ready();                                           /* test11: the saved edits, at the main screen's first event */
    u8 *v = fx_screen();
    if (v && *FX_SHOWN != v) {
        *FX_SHOWN = v;                                 /* test14: stock's pointer back on the FX screen that is up */
        fde.repairs++;
    }
    if (fde.screen) {
        if (type == EV_KNOB && (u32)(what - 1) < PER_SCREEN) {
            knob((u32)(what - 1), ev[2]);
            return 1;
        }
        if (type == EV_KEY && what != KEY_VALUE && what != KEY_SHIFT)
            leave();
    }
    return DOOM_FILTER(page, ev);
}
