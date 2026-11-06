/* SY synth test 10, with guitar synth test 6 (note tracker 3): on v9.52 + LEVEL for MIDI notes (combined-test18; SY
 * test 6 was on v9.52 (combined-test17) with the CPU meter of IR
 * diagnostic test 3 and note tracker test 2's readout. SY synth test 1 (sy_fp.c) is a polyphonic synth in the way
 * BOSS's SY pedals work: 49 semitone bands, each with its own oscillators, from RX pair 0, added to the DRY pair of
 * TX line 3 one block later, on every page while EXT SOURCE is on (the Sound Generator's only in the guitar synth
 * screen).
 * Test 2: 15 tones and OFF; the UI reads the SP's tempo every 0.1 s for the SEQ tone's steps. Test 3: each tone's TONE
 * (BRIGHT), its own setting (P2) and LEVEL (sy.knob); the settings are kept in B:/_sy_tones.bin beside FX deep edit's
 * file, read at the first key, pad or knob event after the boot, written at a key release (never from the UI tick,
 * never while an FX screen is up).
 * Test 4 lifts the ExtIn rule: while a synth listens (EXT SOURCE on), every ROUTING DT1 goes to the effects chip as
 * ExtIn (route_hold, sy_dt1), so pair 0 is the input alone whatever ROUTING says, and the recorder feed is given what
 * ROUTING asks for: on Mix the chip's pair 1 x 2 (the mix before BUS 3/4, the synth in it), on ExtIn the input with the
 * synth added (sy_feed, before the feed).
 * Test 5: the guitar synth screen. Hold EXT SOURCE and press RECORD SETTING (main screen or Sound Generator page): the
 * Sound Generator page opens in SY mode, the input on. Its three knob columns show SOUND / TONE / LEVEL (SHIFT tapped
 * or held: OCTAVE / the tone's own setting / SUSTAIN), the bar PRM: SOUND, the footer the sound's name; CTRL 1-3 set
 * them, VALUE steps SOUND, a pad picks a sound (16: OFF). The page's pads, knobs, VALUE, REC and SUB PAD never reach
 * stock there (no sample, no Sound Generator note), through note repeat's bridge at the UI dispatcher's entry (its call
 * to nr_event_c, re-pointed to sy_event). EXIT leaves; SHIFT + RECORD SETTING gives the page back to the Sound
 * Generator. The screen is drawn through the page's own widgets (the builder re-points the knob column's and the
 * footer's draw, the page's update and the bar's three arp bridges to sy_*; outside the screen they hand on). The
 * picker of test 4 is gone: VALUE + EXT SOURCE opens FX deep edit's input FX screens again.
 * Test 6 (test 5 on the unit): VALUE picks the sound, so CTRL 1 is the tone's own setting, CTRL 2 TONE (-50..+50),
 * CTRL 3 LEVEL (0..100, 50 as designed); SHIFT: OCTAVE / SUSTAIN / DYNAMICS. The bar's PRM part is blank. While an FX
 * screen is up the knobs, VALUE and SHIFT are its (the effect never saw them, so its screen closed), and the pads too
 * while MFX is held (picking an effect). REMAIN on the Sound Generator page (the screen, the plain page, the kits):
 * held + an FX button freezes the FX screen as on the other pages (its press is taken, so the page's own REMAIN, the
 * preview bus, waits); let go with no FX button, the stock press and release follow (the preview bus); with a frozen FX
 * screen up it closes it. Drum mode: every guitar note strikes a pad (the open low E pad 1, a pad a fret to pad 16,
 * higher notes an octave lower at a time).
 * Test 7: the synth's bus. VALUE's push on the screen steps it DRY -> BUS 1 -> BUS 2 -> BOTH, the bar shows it ("OUT:
 * BUS 2"), the file keeps it (byte 98). On BUS 1 or BUS 2 the synth plays on that bus's TX stem (words 2/3, 4/5), so
 * the bus's effect (the FX buttons) is on it; BOTH puts half on each. The guitar's own bus stays INPUT BUS (REMAIN +
 * EXT SOURCE), so the two can sit on any buses: the guitar on BUS 1 cut by the Isolator, the synth on BUS 2.
 * Test 8: the synth plays from the screen on (sy.armed): off at power-on and whenever EXT SOURCE goes on (the guitar
 * dry, ROUTING as set), on once the guitar synth screen opens, and on after EXIT, on every page but the plain Sound
 * Generator's, until EXT SOURCE goes off (or SOUND OFF). The ROUTING hold follows it.
 * Test 10: the screen opened over a Sound Generator page already up (the plain page, drum mode) draws its footer at
 * once (it kept the page's own until SHIFT); the chord works on the looper's page (0x27) too, as SHIFT + RECORD
 * SETTING does there; with looper mode on, REC on the screen goes to the looper (capturing a loop) as on the stock page.
 * On the Sound Generator page guitar synth test 6 plays as before: The SP's main
 * processor follows the note from the input the effects chip hands back (RX pair 0, after the input FX: cabinet
 * test 2 on the unit found the input only in pairs 0 and 1). INPUT SETTING's ROUTING picks what pair 0 holds: on
 * ExtIn the input alone, on Mix the mix as heard, the synth's own note included, so test 5 played only on ExtIn;
 * SY test 4 holds the chip on ExtIn while a synth listens.
 *
 * The tracker runs while the meter's readout is shown (hold EXIT a second on the main screen), and on the Sound
 * Generator page while EXT SOURCE is on (and the hold): the audio task copies pair 0, (L + R) / 2, from every RX block
 * (before the recorder feed) and runs one tracker step (tune_fp.c). It stops itself (SLOW) when one step takes over a whole block, or the
 * mixer and the tracker take over 9/10 of one twice in a row. On the Sound Generator page the UI tick (syn_ui) plays
 * its note there as MIDI IN on the page's channel would (the kits' note gate's SG route, arp_midi_event): one note at a
 * time, so ARP and drum mode take it as they take MIDI. Test 2: stray plucks (the level does not rise) and drum mode
 * play nothing new; a move without a pluck needs 3 analyses within 30 cents (tune_fp.c). Test 4: the velocity is the
 * pick's (tune_fp.c), and the Sound Generator's OCT moves the note (0: the octave tests 1 and 2 played, an octave below
 * the guitar, as the SG sounds MIDI; drum mode keeps the guitar's note, the pad it strikes). Test 3's voice following
 * is gone. Test 6 (tune_fp.c): a fretted note let go no longer plays the open string, a hand on the strings lets go
 * sooner, and a chord's strings picked one by one play.
 *
 * Readout (the stock popup; every 0.1 s while the tracker runs, else with the meter's half-second window):
 *   E2 +3c Q92        the steady note (-- none); the newest analysis: cents off its nearest note, quality
 *   82.4Hz LV45 X1    the newest analysis' frequency (--Hz unvoiced), pair 0's peak in % of full scale, EXT SOURCE
 *   SY 9/12 B14       SY test 1: the engine's average/peak per RX block over the last 75 (OFF, SLOW), in % of a
 *                     block, and the bands sounding (test 6 showed the last pluck's times to the note here)
 *   AVG 25 N12 P14    the average ms to the steady note over N plucks since the readout came on; P plucks heard
 *                     (a hand stopping a string may count; test 1 showed the input FX here instead)
 *   TRK 4/6 MIX 9     the tracker's average/peak per RX block over the last 75 (OFF, SLOW), the mixer's average, in %
 *                     of a block
 *   MAX 30 OVR 0      the worst wake since the readout came on (%); wakes whose mixer + tracker (+ SY engine) took
 *                     over a block
 *
 * Hooks, as in cabinet test 2:
 *   0x0001c2d0  mixer entry       -> meter_mix_entry (the return comes back to meter_mix_exit)
 *   0x80005870  per-voice stub    -> meter_voice
 *   0x0001fd84  SG stub's pre call -> meter_sg_pre
 *   bounce's ui bridge: its bnc_ui call -> diag_ui (bnc_ui, the meter's UI step, tune_ui, syn_ui, sy_ui)
 *   bounce's rx bridge: its bnc_rx call -> diag_rx (bnc_rx, tune_rx, sy_rx)
 *   bounce's rx bridge: its feed call -> sy_feed (test 4: the pairs, the recorder's pair 0, then the feed)
 *   0x800d8118  the DT1 builder's jump to FX deep edit's fde_dt1 -> sy_dt1 (test 4: ROUTING held on ExtIn)
 *   the meter's mixer exit (meter_mix_end): sy_tx adds the engine's newest block to TX line 3's DRY pair
 *   note repeat's nr_event bridge (from the UI dispatcher 0x8003b530): its bl nr_event_c -> sy_event (test 5)
 *   SG knob column draw 0x8022bbd4, footer draw 0x802256fc, page update 0x80229678 -> sy_col_draw, sy_foot_draw,
 *   sy_sg_poll (test 5; each hands on to the kits' / kits save's)
 *   0x800bbc98, 0x80123be6, 0x80123ce0  the arp's bar bridges (item name, value text, screen update) -> sy_bar_*
 *
 * The CPU meter, as T0 had it: the DWT cycle counter times every 64-frame block (800,000 cycles at 600 MHz); MIX
 * the whole mixer 0x1c2d0, entry to return; PAD and SG are still kept (the readout does not show them). This file is
 * the integer side: the builder checks that none of its functions has an FPU instruction.
 */
#include "tune_test_links.h"   /* from the builder: SG_PRE_TARGET, BNC_UI, BNC_RX, SG_MIDI, KIT_MODE, FDE_DT1_LO/HI,
                                  NR_EVENT_C, KIT_COL_DRAW, KIT_FOOT_DRAW, KS_SG_POLL, ARP_NAME/TEXT/POLL_LO/HI */
#include "tune_test.h"
#include "syv_names.h"         /* from the builder (sy_voices.py): SYV_NAME, SYV_P2NAME, SYV_P2KIND, SYV_DYN_DESIGN,
                                  SYV_PRESET_OF, SYV_PRESET_NAME, SY_OFF_PAD, SY_OCT_ZERO, SY_OCTAVES */

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
#define KEY_VALUE 0x31             /* the VALUE knob's push */
#define KEY_REMAIN 0x24            /* test 6 */
#define KEY_FX1 0x2B               /* the effect buttons FX1..FX6 (FILTER+DRIVE .. MFX) */
#define KEY_MFX 0x30
#define KEYS_RW ((volatile u8 *)0x80592448u)                     /* test 6: REMAIN's held bit, set and cleared */
#define FX_FROZEN (*(volatile u8 *)0x80592320u)                  /* an FX screen frozen (REMAIN held at its show) */
#define KEY_DOWN_FN ((void (*)(const s16 *))0x8003ABD1u)         /* the UI dispatcher's key press and release */
#define KEY_UP_FN ((void (*)(const s16 *))0x8003ADA1u)
#define SY_BAR_X0 57                                             /* the bar's PRM part (the item box x 73..95) */
#define SY_GRACE 2u                                              /* SY test 8: steps after a start not held to SLOW */
#define LOOPER_PAGE 0x27                                         /* SY test 10: the looper (MARK with MARK = Looper) */
#define LOOPER_ON (*(volatile const u8 *)0x82E0B92Cu)            /* looper mode on: the SG page's REC goes to it */
#define SY_BAR_X1 127
#define PADS 16u                   /* key IDs 0..15 are the pads */
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
EXPORT sy_t sy;
/* SY test 3: the engine's memory outside the module, in a slot of its own (the builder places .sybss and gives it a
 * boot zero row); sy_start clears it before each start anyway. */
EXPORT __attribute__((section(".sybss"))) sy_block_t sy_block;
#define OFFSET(t, f) ((u32)__builtin_offsetof(t, f))
EXPORT const u32 tt_layout[] = {                          /* the tests read these */
    sizeof(tt_t), OFFSET(tt_t, state), OFFSET(tt_t, peak), OFFSET(tt_t, in), OFFSET(tt_t, w_n), OFFSET(tt_t, pub),
    OFFSET(tt_t, tot_max_ever), OFFSET(tt_t, reset_ack), OFFSET(tt_t, rseq), OFFSET(tt_t, res), sizeof(tt_result),
    sizeof(tt_block_t), OFFSET(tt_block_t, ring), OFFSET(tt_block_t, span), OFFSET(tt_block_t, d6),
    OFFSET(tt_block_t, peaks), OFFSET(tt_block_t, z), OFFSET(tt_block_t, started), OFFSET(tt_block_t, stack),
    OFFSET(tt_t, posted_rseq), OFFSET(tt_block_t, pick_peak), OFFSET(tt_block_t, env), OFFSET(tt_t, hold)};
EXPORT const u32 sy_layout[] = {                          /* SY tests 1 and 2: the tests read these */
    sizeof(sy_t), OFFSET(sy_t, state), OFFSET(sy_t, out), OFFSET(sy_t, w_n), OFFSET(sy_t, pub),
    OFFSET(sy_t, tot_max_ever), sizeof(sy_block_t), OFFSET(sy_block_t, e), OFFSET(sy_block_t, per),
    OFFSET(sy_block_t, amp), OFFSET(sy_block_t, amp), OFFSET(sy_block_t, owned), OFFSET(sy_block_t, env),
    OFFSET(sy_block_t, started), OFFSET(sy_block_t, tone), OFFSET(sy_block_t, nper), OFFSET(sy_t, tone_req),
    OFFSET(sy_block_t, mg), OFFSET(sy_t, knob), OFFSET(sy_t, dirty), OFFSET(sy_t, loads), OFFSET(sy_t, mode),
    OFFSET(sy_t, rec), OFFSET(sy_t, oct), OFFSET(sy_t, susk), OFFSET(sy_block_t, fund_cut), OFFSET(sy_t, dynk),
    OFFSET(sy_t, rem_down), OFFSET(sy_block_t, hold), OFFSET(sy_t, out_bus), OFFSET(sy_t, armed)};

/* ---- the tracker: what the UI and the audio task reach ---- */
#define SYSPRM 0x82DFEED0u                             /* the system parameter object */
#define SYS_GET ((s32 (*)(u32, s32, s32))0x800DA011u)  /* system GetParam(object, ID, index) */
#define SETTINGS 0x82E01144u                           /* the settings object */
#define SET_GET ((s32 (*)(u32, s32, s32))0x800D94D9u)  /* settings GetParam(object, ID, index) */
#define EXT_SOURCE 0x25                                /* settings: EXT SOURCE on */
/* System 0x5C (Resample_Routing, sent to the effects chip as 02 01 00 1e), index -1 as the stock getters read it: INPUT
 * SETTING's ROUTING, what the chip hands back in RX pair 0. 0 Mix: the mix as heard, so the synth would hear its own
 * note (synth tests 2-4 on the unit: stuck notes); 1 ExtIn: the input alone, after the input FX. */
#define ROUTING 0x5C
#define ROUTING_EXTIN 1
#define BUS_EFFECT 0x27C                               /* system, by slot: the effect (slot 0 = input FX) */
#define CHECK_CYCLES 60000000u                         /* the input FX is read every 0.1 s */
#define REFRESH_CYCLES 60000000u                       /* the readout follows the tracker every 0.1 s */
#define CUR_TASK (*(volatile u32 *)0x202BBBFCu)        /* the kernel's running task (its TCB) */
#define TCB_ATTR 0x10
#define TX_WORDS 16u                                   /* TX line 3: 16 words a frame, DRY = words 0/1 */
/* Test 2: the SP's tempo, as the arp reads it: the stock sample-tempo function for the first pad of the bank on the
 * pads (BPM x 100). */
#define PAD_TEMPO ((s32 (*)(s32))0x80047DD1u)
#define CUR_BANK (*(volatile s32 *)0x82DFFF44u)
#define BANKS 10
#define SY_TONE_COUNT SY_NTONES                        /* SY test 11: 20 */
/* Test 3: the file, with the stock calls FX deep edit's file uses (the builder checks their code). */
#define FILE_OPEN ((s32 (*)(const char *, s32))0x800DEC61u)    /* 0 read, 0x601 write (create, truncate); < 0 fails */
#define FILE_READ ((s32 (*)(s32, void *, s32))0x800DEC49u)
#define FILE_WRITE ((s32 (*)(s32, const void *, s32))0x800DD9B9u)
#define FILE_CLOSE ((s32 (*)(s32))0x800DEBD9u)
#define SY_FILE_MAGIC 0x4E545953u                              /* "SYTN" */
#define SY_FILE_VERSION 4u                                     /* SY test 11: the 20 tones */
/* Version 4: magic, version, tone, muted, 20; 60 knob positions, 20 OCTAVE, 20 SUSTAIN, 20 DYNAMICS, the bus, 3 zero;
 * FNV-1a of the first 132. Version 3 (tests 6-10, 104 bytes, the sum of the first 100 at 100: the old 15 tones): only
 * its bus (byte 98) and SOUND OFF are kept, the new tones start as designed. */
#define SY_FILE_BYTES 136
#define SY_FILE_SUM 132
#define SY_FILE_KNOB 8
#define SY_FILE_OCT (SY_FILE_KNOB + 3 * SY_NTONES)
#define SY_FILE_SUS (SY_FILE_OCT + SY_NTONES)
#define SY_FILE_DYN (SY_FILE_SUS + SY_NTONES)
#define SY_FILE_BUS (SY_FILE_DYN + SY_NTONES)
#define SY_FILE3_BYTES 104
#define SY_FILE3_SUM 100
#define FNV 2166136261u
/* Test 3: an FX screen up (as FX deep edit finds it: the view on TOP's list whose vtable is the FX screen's). */
#define TOP_OBJECT (*(u8 *const volatile *)0x80CFD350u)
#define VIEW_AT ((u8 *(*)(u8 *, s32))0x800A01C1u)              /* (TOP + 0x38, i): TOP's i-th view, 0 past the last */
#define FX_VIEW_VTABLE 0x802269C0u
#define VIEWS 0x200
#define DRY_MAX 0x7FFFF                                /* the packer clips every stem to 20 bits */
#define DRY_MIN (-0x80000)

/* ---- SY test 4: ROUTING Mix, the recorder ---- */
/* The stock DT1 builder (context, ID, index, value): its entry jumps to sy_dt1, then FX deep edit's fde_dt1 and stock. */
#define DT1_SEND ((u32 (*)(u32, s32, s32, s32))0x800D8119u)
#define BMC 0x80592500u                                /* the effects chip's DT1 context, as the system setter passes */
#define HOLD_SETTLE 12000000u                          /* 20 ms: the chip has the hold before a synth listens */
#define REC_GRACE 18000000u                            /* 30 ms: the recorder keeps pair 1 while the chip goes back */
/* The recorder feed (0x1ca80) copies pair 1 when settings + 0x64 is set, else the pair the byte at 0x82e0e974 names. */
#define FEED_PAIR1 (*(volatile u32 *)0x82E011A8u)
#define FEED_PAIR (*(volatile u8 *)0x82E0E974u)
#define FEED_ENTRY ((u32 (*)(volatile s16 *, u32))0x0001CA81u)
#define KEY_EXT_SOURCE 0x12

/* ---- SY test 5: the guitar synth screen (the Sound Generator page in SY mode) ---- */
#define EV_KEY 5                                       /* UI events: (type, what, value) */
#define EV_KEY_UP 6
#define EV_ENCODER 7                                   /* VALUE turned: what 0, value the steps */
#define EV_KNOB 9                                      /* CTRL 1-3: what 1..3, value the position 0..127 */
#define EV_PAD 0x10                                    /* a pad hit (pads 0..15, SUB PAD 0x13) */
#define EV_PAD_UP 0x11
#define KEY_SUB_PAD 0x13
#define KEY_REC_SET 0x16                               /* RECORD SETTING */
#define KEY_REC 0x1B
/* Note repeat's handler for every UI event (the builder reads it from its bridge's call, which now comes here). */
#define NR_EVENT ((s32 (*)(const s16 *))NR_EVENT_C)
#define PAGE_REQUEST ((void (*)(s32))0x800DA599u)     /* ask for a page: it comes at a later UI event */
#define SET_SET ((void (*)(u32, s32, s32, s32))0x800DD0C1u)   /* settings set (object, ID, value, flag) */
#define LIGHTS (*(volatile u16 *)0x802496F0u)         /* |= 0x10: stock paints the keys' lights again */
#define MODE_WAIT 600000000u                           /* 1 s: the page asked for and not there: give up */
/* The widgets' draws as the parent has them (the kits' column and footer draws, kits save's page update) and the stock
 * drawing calls the kits use: colour (framebuffer, fore, back), clear a rectangle, font, centred text. */
#define COL_DRAW ((void (*)(void *))KIT_COL_DRAW)
#define FOOT_DRAW ((void (*)(void *))KIT_FOOT_DRAW)
#define SG_POLL ((void (*)(void *))KS_SG_POLL)
#define INVALIDATE ((void (*)(void *))0x800D0019u)
#define F_COLOR ((void (*)(void *, u32, u32))0x800D8019u)
#define F_RECT ((void (*)(void *, const s32 *))0x800CE581u)
#define F_FONT ((void (*)(void *, s32))0x800D80D9u)
#define F_TEXT ((void (*)(void *, s32, s32, const char *))0x800D4FA1u)
#define FONT_SMALL 0x1D                                /* the stock knob column's: the name small at +3, */
#define FONT_BIG 2                                     /* the value big at +15 (DM-404 renders them so) */
#define COL_BASE 0x7B                                  /* the SG knob columns' parameter IDs (SHIFT: 0x7e..0x80) */
#define SG_CHILDREN 0x1A6C                             /* the SG page's three knob columns */
#define SY_SOUNDS (SY_NTONES + 1u)                     /* SOUND: OFF, then the tones (test 11: 20) */
#define SY_SHIFT_TONES (SY_NTONES - 15u)               /* SY test 11: SHIFT + pads 1-5: tones 16-20 */

/* ---- the synth: the tracker's note on the Sound Generator ---- */
#define SG_PAGE 0x1E                                   /* the Sound Generator page (the kits' and the arp's) */
#define SYN_VELOCITY 100                               /* a word without one (never sent by tune_fp.c) */
#define SG_OCT (*(volatile const s32 *)0x80591C4Cu)    /* the Sound Generator's OCT, -3..+4 (keyboard + 4); the SG
                                                          sounds MIDI note n at TUNE x 2^((n - 81) / 12), an
                                                          octave below the note: OCT +1 is the guitar's pitch */
/* The kits' note gates jump here on their SG route: (2, note, velocity, 0) on, (2, note, 0, 1) off. The builder
 * reads the address from both gates' b.w. */
#define SG_MIDI_EVENT ((void (*)(u32, s32, s32, s32))SG_MIDI)
/* The kits' drum mode (kit_mode, nonzero: the kit), the byte that entry tests first; the builder reads its address
 * from the entry's own code. */
#define KIT_MODE_ON (*(volatile const u8 *)KIT_MODE != 0)

typedef struct {
    s32 sounding;                                      /* the note the Sound Generator holds for us, -1 none */
    u32 done;                                          /* the last tt.syn sequence handled */
    u32 ons, offs;                                     /* note-ons and note-offs sent */
    u32 mix, hint_due, hints;                          /* on the page with EXT SOURCE on and ROUTING Mix; the hint
                                                          still to show; hints shown */
} gsyn_t;
EXPORT gsyn_t gsyn = {-1, 0, 0, 0, 0, 0, 0};

/* Shown once each time the page is open with EXT SOURCE on and ROUTING on Mix (the synth stays silent there). The
 * widest line is 95 px in the popup font: a 112 px box (test_tune_test.py checks it fits the 128 px screen). */
#define SYN_HINT "SYNTH NEEDS\nROUTING ExtIn\nSHIFT+EXT SRC"
#define HINT_MS 2500

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

static s32 sat16(s32 v) { return v > 32767 ? 32767 : v < -32768 ? -32768 : v; }

/* After the mixer: the SY engine's newest block, if TX has not added it yet, onto the DRY pair of the TX line 3 block
 * the mixer has just packed (as cabinet test 2's cab_tx). Test 4: also kept for the recorder (sy_rec, this wake's RX)
 * at the capture's scale, which is the stems'. */
/* SY test 7: on the synth's bus: TX line 3's stems are DRY (words 0/1), BUS 1 (2/3: pads on BUS 1 play there, DM-404)
 * and BUS 2 (4/5); both: half on each. In the SY slot's text (.sytext): the module is full. */
EXPORT __attribute__((section(".sytext"))) void sy_tx(const volatile u32 *bufs, u32 mix) {
    sy_t *s = &sy;
    s->last_mix = mix;
    if (!s->fresh || !bufs) return;
    volatile s32 *p = (volatile s32 *)bufs[0];
    u32 bus = s->out_bus, w = bus == 1u ? 2u : bus == 2u ? 4u : 0u;
    for (u32 f = 0; f < FRAMES; f++, p += TX_WORDS) {
        s32 e = s->out[f];
        if (bus == 3u) {
            s32 h = e >> 1;
            p[2] = clip20(p[2] + h);
            p[3] = clip20(p[3] + h);
            p[4] = clip20(p[4] + h);
            p[5] = clip20(p[5] + h);
        } else {
            p[w] = clip20(p[w] + e);
            p[w + 1] = clip20(p[w + 1] + e);
        }
        s->rec[f] = (s16)sat16(e);
    }
    s->rec_fresh = 1;
    s->fresh = 0;
    s->tx++;
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
    sy_tx(mix_bufs, mix);
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

static u32 trk_cycles;                 /* this wake's tracker step (cycles), 0 when it did not run */

/* After the recorder feed and tune_pairs (audio task): one tracker step while the UI wants it. */
EXPORT void tune_rx(void) {
    tt_t *t = &tt;
    trk_cycles = 0;
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
    trk_cycles = clamp(dt);
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

static void sy_publish(sy_t *s) {
    s->seq++;
    BARRIER();
    s->pub.blocks = s->w_n;
    s->pub.avg = s->w_sum / s->w_n;
    s->pub.max = s->w_max;
    s->pub.tot_max = s->w_tot;
    BARRIER();
    s->seq++;
    s->w_n = s->w_sum = s->w_max = s->w_tot = 0;
}

/* An engine step's cycles, with this wake's mixer and tracker: the window, the worst wake, overruns. Returns the
 * wake's cycles. */
static u32 sy_account(sy_t *s, u32 dt, u32 budget) {
    u32 tot = clamp(clamp(dt) + s->last_mix + trk_cycles);
    dt = clamp(dt);
    s->last_mix = 0;
    if (s->reset_ack != s->reset_req) {
        s->tot_max_ever = s->over = 0;
        s->w_n = s->w_sum = s->w_max = s->w_tot = 0;
        s->reset_ack = s->reset_req;
    }
    if (tot > budget) s->over++;
    if (tot > s->tot_max_ever) s->tot_max_ever = tot;
    s->w_n++;
    s->w_sum += dt;
    if (dt > s->w_max) s->w_max = dt;
    if (tot > s->w_tot) s->w_tot = tot;
    if (s->w_n >= TT_WINDOW) sy_publish(s);
    return tot;
}

/* After the tracker (audio task): one SY engine step while the UI wants it, and on through the fade once it stops
 * wanting it (8 blocks). It stops itself (SLOW) when one step takes over a whole block, or the mixer, the tracker and
 * the engine take over 9/10 of one twice in a row. SY test 8: not in the first SY_GRACE steps after a start (a cold
 * first step: DM-404 timed one at 1,232,940 cycles, the emulator translating the code), since a SLOW now holds until
 * EXT SOURCE goes off. */
EXPORT void sy_rx(void) {
    sy_t *s = &sy;
    s->rx++;
    u32 st = s->state;
    if (!s->req) {
        if (st != SY_RUN) {
            if (st != SY_OFF) s->state = SY_OFF;
            s->fresh = 0;
            return;
        }
        s->stopping = 1;
    }
    if (st == SY_SLOW) return;
    if (st == SY_OFF) {
        s->state = st = SY_RUN;
        s->stopping = 0;
        s->run_steps = 0;
    }
    u32 budget = meter.budget ? meter.budget : NOMINAL;
    u32 t0 = DWT_CYCCNT;
    u32 next = sy_fp_call(sy_fp_step, s, &tt_block.stack[STACK_BYTES / 4]);   /* test 2: the tracker's stack */
    u32 dt = DWT_CYCCNT - t0;
    s->steps++;
    s->fresh = 1;
    u32 tot = sy_account(s, dt, budget);
    s->hot = tot > budget / 10u * 9u ? s->hot + 1u : 0u;
    if (s->run_steps < 255u) s->run_steps++;
    if (s->run_steps > SY_GRACE && (dt > budget || s->hot >= 2u)) {
        next = SY_SLOW;
        s->slow_cycles = tot;
        s->fresh = 0;
        if (s->w_n) sy_publish(s);
    }
    s->state = next;
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
/* SY test 5: the guitar synth screen's code goes in the SY slot (the builder's .sytext copy row): the module is full */
#define SCREEN __attribute__((section(".sytext")))

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

static const char *const STATE_NAMES[] = {"OFF", "RUN", "SLOW"};    /* the tracker's and the SY engine's */
static const char *const NOTE_NAMES[] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

UI_SMALL static char *put_s(char *p, s32 v) {
    *p++ = v < 0 ? '-' : '+';
    return put_u(p, (u32)(v < 0 ? -v : v));
}

UI_SMALL static u32 two(u32 v) { return v > 99u ? 99u : v; }

static int read_sy_window(sy_window *out) {
    sy_t *s = &sy;
    for (int tries = 0; tries < 4; ++tries) {
        u32 q = s->seq;
        BARRIER();
        if (q & 1u) continue;
        *out = s->pub;
        BARRIER();
        if (s->seq == q) return 1;
    }
    return 0;
}

/* Six lines in the popup's font (PBold, 9 px lines): test_tune_test.py checks that the widest worst case leaves the
 * popup box inside the 128 x 64 screen. */
EXPORT UI_SMALL void tune_format(const meter_window *w, const tt_window *tw, const tt_result *r, char *out) {
    const meter_t *m = &meter;
    const tt_t *t = &tt;
    const sy_t *s = &sy;
    u32 b = m->budget ? m->budget : NOMINAL;
    u32 st = t->state, sst = s->state;
    sy_window sw;
    char *p = out;
    if (!read_sy_window(&sw)) sw.avg = sw.max = 0;
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
    p = put_str(p, "\nSY ");                             /* test 6 showed the last pluck's times here */
    if (sst == SY_RUN) {
        p = put_u(p, two(pct(sw.avg, b)));
        *p++ = '/';
        p = put_u(p, two(pct(sw.max, b)));
        p = put_str(p, " B");
        p = put_u(p, two(s->sounding));
    } else {
        p = put_str(p, STATE_NAMES[sst < 3u ? sst : 0u]);
    }
    p = put_str(p, "\nAVG ");
    p = put_u(p, r->locks ? cap(r->lock_sum / r->locks) : 0u);
    p = put_str(p, " N");
    p = put_u(p, two(r->locks));
    p = put_str(p, " P");
    p = put_u(p, two(r->onsets));                       /* test 1's IN (the input FX) made room for it */
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
    p = put_str(p, "\nMAX ");                            /* the worse of the tracker's wakes and the engine's */
    p = put_u(p, pct(t->tot_max_ever > s->tot_max_ever ? t->tot_max_ever : s->tot_max_ever, b));
    p = put_str(p, " OVR ");
    p = put_u(p, cap(t->over > s->over ? t->over : s->over));
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
        sy.reset_req++;
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

/* The synths need pair 0 to be the input alone (ROUTING ExtIn): on Mix the effects chip hands back the mix as heard, so
 * the tracker would hear the synth's own note and hold it (synth tests 2-4 on the unit). SY test 4: they play with
 * EXT SOURCE on once the chip has been held on ExtIn for 20 ms (route_hold), whatever ROUTING says. */
static inline u32 syn_live(const tt_t *t) { return t->ext && t->hold && DWT_CYCCNT - t->hold_at >= HOLD_SETTLE; }

/* SY test 4, every UI tick: hold the effects chip on ExtIn while a synth wants pair 0 (EXT SOURCE on, and the SY synth
 * not off by pad 16, or the Sound Generator page's synth), and give the user's ROUTING back when nothing does. The hold
 * sends ExtIn through the builder (sy_dt1 lets it pass); while it is on, sy_route_dt1 turns every ROUTING DT1 the
 * firmware sends into ExtIn too (the RECORD SETTING and looper screens, its chip resets). The recorder meanwhile gets
 * the mix (pair 1 x 2) on ROUTING Mix, the input and the synth on ExtIn (sy_rec). */
UI_SMALL static void route_hold(tt_t *t, u32 now) {
    u32 want = t->ext && ((PAGE == SG_PAGE && !sy.mode) || (!sy.muted && sy.armed));   /* test 5: the SG page's own
                                                                                           synth; SY test 8: armed */
    if (want && !t->hold) {
        t->hold = 1;
        t->hold_at = now;
        t->holds++;
        BARRIER();
        DT1_SEND(BMC, ROUTING, 0, ROUTING_EXTIN);
    } else if (!want && t->hold) {
        t->hold = 0;
        t->grace = 1;
        t->grace_at = now;
        BARRIER();
        DT1_SEND(BMC, ROUTING, 0, (s32)t->routing);
    }
    if (t->grace && now - t->grace_at >= REC_GRACE) t->grace = 0;
    t->rec_mix = (t->hold || t->grace) && t->routing != ROUTING_EXTIN;
    t->rec_ext = t->hold && t->routing == ROUTING_EXTIN;
}

/* Every UI tick: the tracker on while the readout is shown, or on the Sound Generator page with EXT SOURCE on (and the
 * hold). Every 0.1 s: the input FX, EXT SOURCE and ROUTING. */
EXPORT UI_SMALL void tune_ui(void) {
    tt_t *t = &tt;
    u32 now = DWT_CYCCNT;
    if (now - t->checked >= CHECK_CYCLES) {
        t->checked = now;
        t->checks++;
        t->fx = (u32)SYS_GET(SYSPRM, BUS_EFFECT, 0);
        t->ext = SET_GET(SETTINGS, EXT_SOURCE, 0) != 0;
        t->routing = (u32)SYS_GET(SYSPRM, ROUTING, -1);
    }
    route_hold(t, now);
    u32 want = meter.shown || (PAGE == SG_PAGE && !sy.mode && syn_live(t));   /* test 5: not in the SY screen */
    if (!want) t->req = 0;
    if (want && !t->req && t->state == TT_OFF) tune_start(t);
}

/* SY test 4: every DT1 the firmware sends for ROUTING (sy_dt1 calls this with its value): ExtIn while the hold is on. */
EXPORT s32 sy_route_dt1(s32 value) {
    tt_t *t = &tt;
    t->route_sends++;
    if (t->hold) {
        value = ROUTING_EXTIN;
        t->route_held++;
    }
    t->route_last = (u32)value;
    return value;
}

/* The builder's entry (0x800d8118) jumps here in place of FX deep edit's fde_dt1: a DT1 for ROUTING (0x5c) has its value
 * (r3) passed through sy_route_dt1; every DT1 then goes on to fde_dt1 with the caller's registers and, for all but
 * ROUTING, its stack untouched (the builder makes some boot frames from leftover stack). */
__attribute__((naked, used)) void sy_dt1(void) {
    __asm__ volatile(
        "cmp r1, #0x5c\n"
        "bne 1f\n"
        "push {r0, r1, r2, lr}\n"
        "mov r0, r3\n"
        "bl sy_route_dt1\n"
        "mov r3, r0\n"
        "pop {r0, r1, r2, lr}\n"
        "1:\n"
        "movw r12, #" XS(FDE_DT1_LO) "\n"
        "movt r12, #" XS(FDE_DT1_HI) "\n"
        "bx r12\n");
}

/* Clear the SY engine, then hand it to the audio task (only while it is off). */
UI_SMALL static void sy_start(sy_t *s) {
    memset(&sy_block, 0, sizeof(sy_block));
    s->starts++;
    BARRIER();
    s->req = 1;
}

/* Where the synth can play: every page but the Sound Generator's (guitar synth test 6 plays there; test 5: but the SY
 * screen's), with EXT SOURCE on and the chip held on ExtIn (test 4; on Mix it hands back the mix as heard: the engine
 * would hear its own sound). */
static inline u32 sy_can_play(void) { return syn_live(&tt) && sy.armed && (PAGE != SG_PAGE || sy.mode); }

UI_SMALL SCREEN static void sy_mode_tick(sy_t *s, u32 now);

/* Every UI tick: the SY engine where it can play, unless SOUND is OFF (test 2: pad 16). Leaving that lets it fade out
 * over 8 blocks. Every 0.1 s: the SP's tempo (test 2: the SEQ tone's steps), as the arp reads it. Test 5: the guitar
 * synth screen's page and EXT SOURCE. */
EXPORT UI_SMALL void sy_ui(void) {
    sy_t *s = &sy;
    u32 now = DWT_CYCCNT;
    if (PAGE != SG_PAGE) s->sg_page = 0;                /* SY test 6: its object goes with the page */
    sy_mode_tick(s, now);
    if (s->mode == 1u)                                  /* SY test 8: the screen arms the synth; EXT SOURCE off */
        s->armed = 1;                                   /* disarms it (not while the chord's release puts it on) */
    else if (!tt.ext && !s->ext_fix)
        s->armed = 0;
    if (now - s->tempo_checked >= CHECK_CYCLES) {
        s->tempo_checked = now;
        s32 bank = CUR_BANK;
        if ((u32)bank < BANKS) {
            s32 t = PAD_TEMPO(bank * 16);
            if (t >= 2000 && t <= 30000) s->bpm100 = (u32)t;
        }
    }
    u32 want = sy_can_play() && !s->muted;
    if (!want) {
        if (s->req) {
            s->req = 0;
            s->stops++;
        }
        return;
    }
    if (!s->req && s->state == SY_OFF) sy_start(s);
}

EXPORT const char sy_path[] = "B:/_sy_tones.bin";
EXPORT u8 sy_file[SY_FILE_BYTES] __attribute__((aligned(4)));

UI_SMALL static u32 sy_fnv(const u8 *p, u32 n) {
    u32 h = FNV;
    while (n--) h = (h ^ *p++) * 16777619u;
    return h;
}

UI_SMALL static u32 get32(const u8 *p) { return (u32)p[0] | (u32)p[1] << 8 | (u32)p[2] << 16 | (u32)p[3] << 24; }

UI_SMALL static void put32(u8 *p, u32 v) {
    for (u32 i = 0; i < 4u; i++) p[i] = (u8)(v >> (8u * i));
}

/* Test 3: the file into RAM, once (the first key, pad or knob event after the boot): a missing, short, long or bad file
 * (magic, version, tones, sum) leaves the tones as designed. Test 5: version 2 (the tones changed: a version 1 file is
 * left alone), with each tone's OCTAVE (0..5) and SUSTAIN (0..101) after the knobs. */
UI_SMALL static void sy_ready(void) {
    sy_t *s = &sy;
    if (s->loaded) return;
    s->loaded = 1;
    s32 fd = FILE_OPEN(sy_path, 0);
    if (fd < 0) return;
    s32 n = FILE_READ(fd, sy_file, SY_FILE_BYTES);
    FILE_CLOSE(fd);
    if (n == SY_FILE3_BYTES && get32(sy_file) == SY_FILE_MAGIC && sy_file[4] == 3u &&
        get32(sy_file + SY_FILE3_SUM) == sy_fnv(sy_file, SY_FILE3_SUM)) {   /* SY test 11: tests 6-10's file */
        u32 bus = sy_file[98];
        s->out_bus = (u8)(bus <= 3u ? bus : 0u);
        s->muted = sy_file[6] & 1u;
        s->dirty = 1;                                   /* written as version 4 at the next save */
        s->loads++;
        return;
    }
    if (n != SY_FILE_BYTES || get32(sy_file) != SY_FILE_MAGIC || sy_file[4] != SY_FILE_VERSION ||
        sy_file[7] != SY_TONE_COUNT || get32(sy_file + SY_FILE_SUM) != sy_fnv(sy_file, SY_FILE_SUM)) {
        s->bad_files++;
        return;
    }
    for (u32 i = 0; i < 3u * SY_TONE_COUNT; i++) {
        u32 v = sy_file[SY_FILE_KNOB + i];
        s->knob[i / 3u][i % 3u] = (s8)((v > 127u ? 127u : v) - 64u);
    }
    for (u32 i = 0; i < SY_TONE_COUNT; i++) {
        u32 o = sy_file[SY_FILE_OCT + i], su = sy_file[SY_FILE_SUS + i], dk = sy_file[SY_FILE_DYN + i];
        s->oct[i] = (s8)(o <= SY_OCTAVES ? o : 0u);
        s->susk[i] = (u8)(su <= 101u ? su : 0u);
        s->dynk[i] = (u8)(dk <= 101u ? dk : 0u);
    }
    {
        u32 bus = sy_file[SY_FILE_BUS];                 /* SY test 7: the synth's bus */
        s->out_bus = (u8)(bus <= 3u ? bus : 0u);
    }
    s->tone_req = sy_file[5] < SY_TONE_COUNT ? sy_file[5] : 0u;
    s->muted = sy_file[6] & 1u;
    s->loads++;
}

/* Test 3: an FX screen on TOP's list (writing the file with one up sent the display to the main screen: FX deep edit's
 * test 12 on the unit). SY test 6: TOP (the main page's object) is gone on the Sound Generator page (DM-404: 0 there),
 * whose own object holds its views the same way: the page sy_sg_poll last had, while the page is up. */
UI_SMALL SCREEN static u32 sy_fx_screen(void) {
    u8 *top = TOP_OBJECT;
    if (!top && PAGE == SG_PAGE) top = (u8 *)sy.sg_page;
    if (!top) return 0;
    for (s32 i = 0; i < VIEWS; i++) {
        u8 *w = VIEW_AT(top + 0x38, i);
        if (!w) break;
        if (*(const volatile u32 *)w == FX_VIEW_VTABLE) return 1;
    }
    return 0;
}

/* Test 3: RAM into the file, whole (create, truncate); a failed open or short write is counted and stays pending. */
UI_SMALL static void sy_save(void) {
    sy_t *s = &sy;
    put32(sy_file, SY_FILE_MAGIC);
    sy_file[4] = SY_FILE_VERSION;
    sy_file[5] = (u8)s->tone_req;
    sy_file[6] = (u8)s->muted;
    sy_file[7] = SY_TONE_COUNT;
    for (u32 i = 0; i < 3u * SY_TONE_COUNT; i++) sy_file[SY_FILE_KNOB + i] = (u8)(s->knob[i / 3u][i % 3u] + 64);
    for (u32 i = 0; i < SY_TONE_COUNT; i++) {
        sy_file[SY_FILE_OCT + i] = (u8)s->oct[i];
        sy_file[SY_FILE_SUS + i] = s->susk[i];
        sy_file[SY_FILE_DYN + i] = s->dynk[i];
    }
    sy_file[SY_FILE_BUS] = s->out_bus;                  /* SY test 7 */
    for (u32 i = SY_FILE_BUS + 1u; i < SY_FILE_SUM; i++) sy_file[i] = 0;
    put32(sy_file + SY_FILE_SUM, sy_fnv(sy_file, SY_FILE_SUM));
    s32 n = -1, fd = FILE_OPEN(sy_path, 0x601);
    if (fd >= 0) {
        n = FILE_WRITE(fd, sy_file, SY_FILE_BYTES);
        FILE_CLOSE(fd);
    }
    if (n == SY_FILE_BYTES) {
        s->dirty = 0;
        s->saves++;
    } else {
        s->save_errors++;
    }
}

static inline u32 key_held(u32 k) { return (KEYS[k >> 3] >> (k & 7u)) & 1u; }

/* Test 3: the file is written at a key release, never with an FX screen up (writing with one up sent the display to the
 * main screen: FX deep edit's test 12 on the unit). */
UI_SMALL static void sy_flush(sy_t *s) {
    if (s->dirty && !sy_fx_screen()) sy_save();
}

/* ---- SY test 5: the guitar synth screen ---- */

/* The screen is up: SY mode, on the Sound Generator page (the draws and the bar's bridges ask). */
EXPORT SCREEN u32 sy_shown(void) { return sy.mode && PAGE == SG_PAGE; }

UI_SMALL SCREEN static void sy_changed(sy_t *s) {
    s->rev++;
    s->bar_rev++;
}

static inline u32 sy_tone(const sy_t *s) { return s->tone_req < SY_TONE_COUNT ? s->tone_req : 0u; }

/* EXT SOURCE on through the stock setter (as bounce switches it: the setter sends the input's level to the chip), and
 * its light. */
UI_SMALL SCREEN static void sy_ext_on(void) {
    SET_SET(SETTINGS, EXT_SOURCE, 1, 0);
    LIGHTS |= 0x10;
}

UI_SMALL SCREEN static void sy_mode_off(sy_t *s) {
    if (!s->mode) return;
    s->mode = 0;
    s->leaves++;
    sy_changed(s);                                      /* the page's own draws come back if it stays up */
}

/* EXT SOURCE + RECORD SETTING: the screen on the Sound Generator page (asked for from the main screen), the synth on with
 * the sound it had. The EXT SOURCE press went to stock: the input off now (the press toggled it off) is put on again,
 * and its release is watched (with GATE on stock switches the input off there). */
UI_SMALL SCREEN static void sy_mode_on(sy_t *s) {
    s->enters++;
    if (s->muted) {
        s->muted = 0;
        s->dirty = 1;
    }
    if (!SET_GET(SETTINGS, EXT_SOURCE, 0)) sy_ext_on();
    s->ext_fix = 1;
    s->shift_down = 0;                                  /* test 10: the footer kept (it was cleared here, so a screen
                                                           opened over the page up kept the page's own footer) */
    sy_changed(s);
    if (PAGE == SG_PAGE) {
        s->mode = 1;
    } else {
        s->mode = 2;
        s->mode_at = DWT_CYCCNT;
        PAGE_REQUEST(SG_PAGE);
    }
}

/* Every UI tick: the page asked for has come (or 1 s passed: given up); another page closes the screen; EXT SOURCE let
 * go after the chord: the input on again if stock put it off (GATE). */
UI_SMALL SCREEN static void sy_mode_tick(sy_t *s, u32 now) {
    if (s->mode == 2) {
        if (PAGE == SG_PAGE) {
            s->mode = 1;
            sy_changed(s);
        } else if (now - s->mode_at >= MODE_WAIT) {
            sy_mode_off(s);
        }
    } else if (s->mode == 1 && PAGE != SG_PAGE) {
        sy_mode_off(s);
    }
    if (PAGE != SG_PAGE) s->foot = 0;
    if (s->ext_fix && !key_held(KEY_EXT_SOURCE)) {
        s->ext_fix = 0;
        if (!SET_GET(SETTINGS, EXT_SOURCE, 0)) sy_ext_on();
    }
}

/* SOUND: 0 OFF, 1..15 the tones. */
UI_SMALL SCREEN static u32 sy_sound(const sy_t *s) { return s->muted ? 0u : sy_tone(s) + 1u; }

UI_SMALL SCREEN static void sy_sound_set(sy_t *s, u32 n) {
    if (n == sy_sound(s)) return;
    if (n) {
        s->tone_req = n - 1u;
        s->muted = 0;
    } else {
        s->muted = 1;
    }
    s->picks++;
    s->dirty = 1;
    sy_changed(s);
}

/* SY test 11: a pad's SOUND: pads 1-15 the tones 1-15, pad 16 OFF; with SHIFT held, pads 1-5 the tones 16-20 (SHIFT
 * then counts as used: its release keeps the page). */
UI_SMALL SCREEN static u32 sy_pad_sound(sy_t *s, u32 pad) {
    if (key_held(KEY_SHIFT) && pad < SY_SHIFT_TONES) {
        s->shift_used = 1;
        return 16u + pad;
    }
    return pad == SY_OFF_PAD ? 0u : pad + 1u;
}

/* CTRL 1-3 on the screen (k 0..2, the knob's position 0..127): test 6: the tone's own setting, TONE and LEVEL (knob -
 * 64, 0 as designed; VALUE and the pads pick the sound); on the SHIFT page (tapped, or SHIFT held): OCTAVE (5 zones,
 * -2..+2), SUSTAIN (0..100) and DYNAMICS (0..100). */
UI_SMALL SCREEN static void sy_screen_knob(sy_t *s, u32 k, s32 pos) {
    pos = pos < 0 ? 0 : pos > 127 ? 127 : pos;
    u32 tone = sy_tone(s), shift = s->shift_page ^ s->shift_down;
    if (s->shift_down) s->shift_used = 1;
    s->turns++;
    if (!shift)
        s->knob[tone][k == 0 ? 1 : k == 1u ? 0 : 2] = (s8)(pos - 64);
    else if (k == 0)
        s->oct[tone] = (s8)(1 + ((pos * (s32)SY_OCTAVES) >> 7));
    else if (k == 1)
        s->susk[tone] = (u8)(1 + ((pos * 101) >> 7));
    else
        s->dynk[tone] = (u8)(1 + ((pos * 101) >> 7));
    s->dirty = 1;
    s->rev++;
}

/* Presses the screen took have their releases taken too (keys by ID; pad events by pad, SUB PAD as bit 16). */
UI_SMALL SCREEN static void sy_take(sy_t *s, s32 key) {
    if (key < 32)
        s->taken |= 1u << key;
    else
        s->taken_hi |= 1u << (key - 32);
}

UI_SMALL SCREEN static u32 sy_untake(sy_t *s, s32 type, s32 what) {
    volatile u32 *w;
    u32 bit;
    if (type == EV_PAD_UP) {
        w = &s->pads_taken;
        bit = (u32)what < PADS ? 1u << what : what == KEY_SUB_PAD ? 1u << 16 : 0u;
    } else {
        if ((u32)what >= 64u) return 0;
        w = what < 32 ? &s->taken : &s->taken_hi;
        bit = 1u << (what & 31);
    }
    if (!(*w & bit)) return 0;
    *w &= ~bit;
    return 1;
}

/* Test 6: an event an FX screen up on the screen takes: the knobs, VALUE (turned, pushed), SHIFT; the pads while MFX
 * is held (MFX + a pad picks an effect). */
UI_SMALL SCREEN static u32 sy_fx_event(s32 type, s32 what) {
    if (type == EV_KNOB || type == EV_ENCODER) return 1;
    if (type == EV_KEY || type == EV_KEY_UP) {
        if (what == KEY_VALUE || what == KEY_SHIFT) return 1;
        if ((u32)what < PADS || what == KEY_SUB_PAD) return key_held(KEY_MFX);
        return 0;
    }
    return (type == EV_PAD || type == EV_PAD_UP) && key_held(KEY_MFX);
}

/* Test 6: a REMAIN press on the Sound Generator page: taken, its held bit set as the stock press's would be (an FX
 * screen opened while it is held reads it and freezes); with a frozen FX screen up, an EXIT closes it instead (the
 * page's own REMAIN is the preview bus). 1 takes it. */
UI_SMALL SCREEN static void sy_key_bit(u32 k, u32 on) {
    volatile u8 *p = KEYS_RW + (k >> 3);
    u8 m = (u8)(1u << (k & 7u));
    *p = on ? (u8)(*p | m) : (u8)(*p & (u8)~m);
}

UI_SMALL SCREEN static void sy_stock_key(s32 key, s32 val) {
    s16 e[3] = {EV_KEY, (s16)key, (s16)val};
    KEY_DOWN_FN(e);
    e[0] = EV_KEY_UP;
    KEY_UP_FN(e);
}

UI_SMALL SCREEN static u32 sy_remain(sy_t *s, s32 type, s32 what, s32 val) {
    if (what != KEY_REMAIN) {
        if (type == EV_KEY && s->rem_down && (u32)(what - KEY_FX1) <= (u32)(KEY_MFX - KEY_FX1)) s->rem_fx = 1;
        return 0;
    }
    if (type == EV_KEY && PAGE == SG_PAGE) {
        if (sy_fx_screen()) {
            if (!FX_FROZEN) return 0;
            sy_take(s, KEY_REMAIN);                     /* its release taken too */
            FX_FROZEN = 0;
            sy_stock_key(KEY_EXIT, 0);
            s->rem_holds++;
            return 1;
        }
        s->rem_down = 1;
        s->rem_fx = 0;
        sy_key_bit(KEY_REMAIN, 1);
        return 1;
    }
    if (type == EV_KEY_UP && s->rem_down) {
        s->rem_down = 0;
        sy_key_bit(KEY_REMAIN, 0);
        if (s->rem_fx) {
            s->rem_holds++;
        } else if (PAGE == SG_PAGE) {
            sy_stock_key(KEY_REMAIN, val);              /* a tap: the page's own REMAIN (the preview bus) */
            s->rem_taps++;
        }
        return 1;
    }
    return 0;
}

/* An event on the screen; 1 takes it. A pad picks a sound (pad 16: OFF), silently: its press as a pad hit and as a key,
 * and SUB PAD's, never reach stock (no sample, no Sound Generator note). CTRL 1-3 edit, VALUE steps SOUND; VALUE's
 * push and REC are taken (no edit mode, no export). SHIFT goes on (its held bit) and is noted for the page; SHIFT +
 * RECORD SETTING closes the screen and goes on (the stock Sound Generator); EXIT and the rest go on. */
UI_SMALL SCREEN static u32 sy_screen_event(sy_t *s, s32 type, s32 what, s32 val) {
    if (type == EV_PAD) {
        if ((u32)what < PADS) {
            s->pads_taken |= 1u << what;
            s->pads_ate++;
            sy_sound_set(s, sy_pad_sound(s, (u32)what));
            return 1;
        }
        if (what != KEY_SUB_PAD) return 0;
        s->pads_taken |= 1u << 16;
        return 1;
    }
    if (type == EV_KNOB) {
        if ((u32)(what - 1) >= 3u) return 0;
        sy_screen_knob(s, (u32)(what - 1), val);
        return 1;
    }
    if (type == EV_ENCODER) {
        if (what || !val) return 0;
        s32 n = (s32)sy_sound(s) + (val > 0 ? 1 : -1);
        sy_sound_set(s, (u32)(n < 0 ? 0 : n > (s32)SY_SOUNDS - 1 ? (s32)SY_SOUNDS - 1 : n));
        s->vsteps++;
        return 1;
    }
    if (type == EV_KEY) {
        if ((u32)what < PADS) {
            sy_take(s, what);
            sy_sound_set(s, sy_pad_sound(s, (u32)what));
            return 1;
        }
        if (what == KEY_REC && LOOPER_ON) return 0;    /* test 10: the looper's REC (a loop), as on the stock page */
        if (what == KEY_SUB_PAD || what == KEY_REC || what == KEY_VALUE) {
            sy_take(s, what);
            if (what == KEY_VALUE) {                    /* SY test 7: the synth's bus, DRY -> BUS 1 -> BUS 2 -> BOTH */
                s->out_bus = (u8)((s->out_bus + 1u) & 3u);
                s->dirty = 1;
                sy_changed(s);
            }
            return 1;
        }
        if (what == KEY_SHIFT) {
            s->shift_down = 1;
            s->shift_used = 0;
            s->rev++;
        } else if (what == KEY_REC_SET && key_held(KEY_SHIFT)) {
            sy_mode_off(s);
        }
        return 0;
    }
    if (type == EV_KEY_UP && what == KEY_SHIFT && s->shift_down) {
        if (!s->shift_used) s->shift_page ^= 1u;
        s->shift_down = 0;
        s->rev++;
    }
    return 0;
}

/* Every UI event, at the UI dispatcher's entry (note repeat's bridge calls this in place of nr_event_c); 1 takes it.
 * The file is read at the first key, pad or knob event after the boot and written at a key release. EXT SOURCE held +
 * RECORD SETTING, on the main screen or the Sound Generator page, opens the guitar synth screen (its press and release
 * taken). The screen's own events (sy_screen_event); everything else on to note repeat's handler. */
EXPORT SCREEN s32 sy_event(const s16 *ev) {
    sy_t *s = &sy;
    s32 type = ev[0], what = ev[1];
    if ((u32)(type - EV_KEY) <= (u32)(EV_KNOB - EV_KEY) || type == EV_PAD || type == EV_PAD_UP) sy_ready();
    if ((type == EV_KEY_UP || type == EV_PAD_UP) && sy_untake(s, type, what)) return 1;
    if ((type == EV_KEY || type == EV_KEY_UP) && sy_remain(s, type, what, ev[2])) return 1;
    if (type == EV_KEY_UP) sy_flush(s);
    if (type == EV_KEY && what == KEY_REC_SET && key_held(KEY_EXT_SOURCE) && !key_held(KEY_SHIFT) &&
        (PAGE == MAIN_PAGE || PAGE == SG_PAGE || PAGE == LOOPER_PAGE)) {   /* test 10: the looper too */
        sy_take(s, what);
        sy_mode_on(s);
        return 1;
    }
    if (sy_shown()) {
        if (sy_fx_screen() && sy_fx_event(type, what)) {
            s->fx_passes++;                             /* test 6: the FX screen's */
            return NR_EVENT(ev);
        }
        if (sy_screen_event(s, type, what, ev[2])) return 1;
    }
    return NR_EVENT(ev);
}

/* "+5", "0", "-12". */
UI_SMALL SCREEN static char *put_signed(char *p, s32 v) {
    if (v) *p++ = v < 0 ? '-' : '+';
    return put_u(p, (u32)(v < 0 ? -v : v));
}

static const char *const SY_LABELS[6] = {0, "TONE", "LEVEL", "OCTAVE", "SUSTAIN", "DYNAMICS"};

/* Test 6: a knob's offset from 64 (-64..63) as -50..+50, and a position (0..127) as 0..100 with 64 at 50. */
UI_SMALL SCREEN static s32 sy_pm50(s32 d) { return d >= 0 ? (d * 50 + 31) / 63 : -((-d * 50 + 32) / 64); }
UI_SMALL SCREEN static u32 sy_pct(u32 pos) { return pos <= 64u ? (pos * 50u + 32u) / 64u : 50u + ((pos - 64u) * 50u + 31u) / 63u; }

/* A knob column's name and value (test 6): the tone's own setting and TONE (-50..+50), LEVEL (0..100, 50 as
 * designed); the SHIFT page: OCTAVE (-2..+2), SUSTAIN and DYNAMICS (0..100). */
EXPORT UI_SMALL SCREEN void sy_col_text(u32 col, char *label, char *value) {
    const sy_t *s = &sy;
    u32 tone = sy_tone(s), i = col + ((s->shift_page ^ s->shift_down) ? 3u : 0u);
    *put_str(label, i == 0u ? SYV_P2NAME[tone] : SY_LABELS[i]) = 0;
    char *p = value;
    if (i == 0 && SYV_P2KIND[tone] == SYV_P_ENVSEL) {   /* SY test 11: the ENV preset itself, by name */
        s32 k = s->knob[tone][1], z = ((64 + k) * 10) >> 7;
        u32 pre = k ? (u32)(z < 0 ? 0 : z > 9 ? 9 : z) : SYV_PRESET_OF[tone];
        p = put_str(p, SYV_PRESET_NAME[pre]);
    } else if (i == 0)
        p = put_signed(p, sy_pm50(s->knob[tone][1]));
    else if (i == 1)
        p = put_signed(p, sy_pm50(s->knob[tone][0]));
    else if (i == 2)
        p = put_u(p, sy_pct((u32)(64 + s->knob[tone][2])));
    else if (i == 3)
        p = put_signed(p, (u32)s->oct[tone] - 1u < SY_OCTAVES ? (s32)s->oct[tone] - (s32)SY_OCT_ZERO : 0);
    else if (i == 4)
        p = put_u(p, s->susk[tone] ? s->susk[tone] - 1u : 50u);   /* SY test 11: 50 as designed (x1 the times) */
    else
        p = put_u(p, s->dynk[tone] ? s->dynk[tone] - 1u : SYV_DYN_DESIGN[tone]);
    *p = 0;
}

/* The footer: the sound's name ("SUPERSAW"), "SYNTH OFF". The footer's box is 64 px wide (DM-404: "SY 1 SAW LEAD" lost
 * its last letter), its number is in the column and the bar. */
EXPORT UI_SMALL SCREEN void sy_foot_text(char *out) {
    const sy_t *s = &sy;
    *put_str(out, s->muted ? "SYNTH OFF" : SYV_NAME[sy_tone(s)]) = 0;
}

/* A widget's frame (framebuffer at +0x84, rectangle x0 y0 x1 y1 at +4), cleared as the stock draws do. */
UI_SMALL SCREEN static void *sy_clear(s32 *w) {
    void *fb = *(void **)((u8 *)w + 0x84);
    F_COLOR(fb, 0xFFFFFF, 0);
    F_RECT(fb, w + 1);
    return fb;
}

/* The SG page's knob column draw (all knob widgets of its class come here, in place of the kits' kit_ui_draw). On the
 * screen, for the three columns (descriptor type 0, parameter 0x7b..0x80): the name small at the top and the value big,
 * where the stock column draws its own (0x80170994: font 0x1d at +3; 0x801709fa: font 2 at +15); anything else to the
 * kits' draw. */
EXPORT SCREEN void sy_col_draw(void *widget) {
    s32 *w = (s32 *)widget;
    s32 col = w[0x310 / 4] - COL_BASE;
    if (col >= 3 && col <= 5) col -= 3;
    if (!sy_shown() || w[0x308 / 4] || (u32)col > 2u) {
        COL_DRAW(widget);
        return;
    }
    char label[12], value[8];
    sy_col_text((u32)col, label, value);
    void *fb = sy_clear(w);
    s32 x = (w[1] + w[3]) / 2, y = w[2];
    F_FONT(fb, FONT_SMALL);
    F_TEXT(fb, x, y + 3, label);
    F_FONT(fb, FONT_BIG);
    F_TEXT(fb, x, y + 15, value);                       /* the big font left current, as the stock draw leaves it */
}

/* The footer widgets' draw (in place of the kits' kit_ui_footer_draw). On the screen: the sound's name, in the small
 * font; the widget is kept to be drawn again when the sound changes (sy_sg_poll, only while the page stays up and the
 * widget's first word is still its vtable). */
EXPORT SCREEN void sy_foot_draw(void *widget) {
    sy_t *s = &sy;
    s32 *w = (s32 *)widget;
    if (PAGE == SG_PAGE) {                              /* test 10: kept outside the screen too, so the screen's */
        s->foot = (u32)widget;                          /* first update redraws it (the mode tick forgets it off
                                                           the page) */
        s->foot_vt = (u32)w[0];
    }
    if (!sy_shown()) {
        FOOT_DRAW(widget);
        return;
    }
    char text[24];
    sy_foot_text(text);
    void *fb = sy_clear(w);
    F_FONT(fb, FONT_SMALL);
    F_TEXT(fb, (w[1] + w[3]) / 2, w[2] + 1, text);
}

/* The SG page's update (in place of kits save's ks_sg_poll, which it calls first): when what the screen shows changed,
 * the page's three knob columns are drawn again (the page's current children, never kept), and the footer. */
EXPORT SCREEN void sy_sg_poll(void *page) {
    SG_POLL(page);
    sy_t *s = &sy;
    s->sg_page = (u32)page;                             /* SY test 6: its views (sy_fx_screen) */
    if (s->drawn_rev == s->rev) return;
    s->drawn_rev = s->rev;
    void *const *children = (void *const *)((u8 *)page + SG_CHILDREN);
    for (u32 i = 0; i < 3u; i++)
        if (children[i]) INVALIDATE(children[i]);
    if (s->foot && PAGE == SG_PAGE && *(const volatile u32 *)s->foot == s->foot_vt) INVALIDATE((void *)s->foot);
}

/* The bar (PRM: item, value). Test 6: blank on the screen (VALUE picks the sound, the footer names it): no item name,
 * no value, and its part of the bar (x 57 on, the item's box, "PRM:") painted over. Test 7: the synth's bus there
 * ("OUT: BUS 2"), in the bar's own font, centred, one row down as the stock item text is. */
static const char *const SY_BUS_TEXT[4] = {"OUT: DRY", "OUT: BUS 1", "OUT: BUS 2", "OUT: BOTH"};
EXPORT UI_SMALL SCREEN void sy_bar_name_c(char *out) { *out = 0; }

EXPORT UI_SMALL SCREEN void sy_bar_text_c(char *out) { *out = 0; }

EXPORT UI_SMALL SCREEN void sy_bar_blank_c(void *fb, s32 y0, s32 y1) {
    const s32 r[4] = {SY_BAR_X0, y0, SY_BAR_X1, y1};
    F_COLOR(fb, 0xFFFFFF, 0);
    F_RECT(fb, r);
    F_TEXT(fb, (SY_BAR_X0 + SY_BAR_X1) / 2, y0 + 1, SY_BUS_TEXT[sy.out_bus & 3u]);
}

/* The bar's update: 1 when it should be drawn again (what it shows changed, or the screen came or went). */
EXPORT SCREEN u32 sy_bar_poll_c(void) {
    sy_t *s = &sy;
    if (s->bar_drawn == s->bar_rev) return 0;
    s->bar_drawn = s->bar_rev;
    return 1;
}

/* From 0x800bbc98 (the arp re-pointed it to its bridge; the builder re-points it here): r4 the text, r5 the item, mid
 * function. On the screen the item name is ours and the function ends (0x800bbcc2: add sp, #0x68; pop {r4, r5, r7,
 * pc}); else on to the arp's bridge with every register as it came. */
__attribute__((naked, used)) SCREEN void sy_bar_name(void) {
    __asm__ volatile(
        "push {r0, r1, r2, r3, r4, lr}\n"
        "bl sy_shown\n"
        "cmp r0, #0\n"
        "pop {r0, r1, r2, r3, r4, lr}\n"
        "beq 1f\n"
        "mov r0, r4\n"
        "bl sy_bar_name_c\n"
        "movw r12, #0xbcc3\n"
        "movt r12, #0x800b\n"
        "bx r12\n"
        "1:\n"
        "movw r12, #" XS(ARP_NAME_LO) "\n"
        "movt r12, #" XS(ARP_NAME_HI) "\n"
        "bx r12\n");
}

/* From 0x80123be6 (likewise): r0-r3 the displaced draw call's arguments, r4 the bar, r6 the item, the item box's y0
 * and y1 at sp + 0x1c and sp + 0x24, the value text at sp + 0x28. On the screen (test 6): the displaced draw skipped,
 * the PRM part painted over, an empty value text, on at 0x80123c5a (which draws it); else the arp's bridge (it draws
 * first). */
__attribute__((naked, used)) SCREEN void sy_bar_text(void) {
    __asm__ volatile(
        "push {r0, r1, r2, r3, r4, lr}\n"
        "bl sy_shown\n"
        "cmp r0, #0\n"
        "pop {r0, r1, r2, r3, r4, lr}\n"
        "beq 1f\n"
        "ldr r0, [r4, #0x84]\n"
        "ldr r1, [sp, #0x1c]\n"
        "ldr r2, [sp, #0x24]\n"
        "bl sy_bar_blank_c\n"
        "add r0, sp, #0x28\n"
        "bl sy_bar_text_c\n"
        "movw r12, #0x3c5b\n"
        "movt r12, #0x8012\n"
        "bx r12\n"
        "1:\n"
        "movw r12, #" XS(ARP_TEXT_LO) "\n"
        "movt r12, #" XS(ARP_TEXT_HI) "\n"
        "bx r12\n");
}

/* From 0x80123ce0, the bar's update (likewise, at the function's entry: r0 the bar, lr the caller): drawn again when
 * sy_bar_poll_c says so, then the arp's bridge with r0-r3 and lr as they came. */
__attribute__((naked, used)) SCREEN void sy_bar_poll(void) {
    __asm__ volatile(
        "push {r0, r1, r2, r3, r4, lr}\n"
        "mov r4, r0\n"
        "bl sy_bar_poll_c\n"
        "cmp r0, #0\n"
        "beq 1f\n"
        "mov r0, r4\n"
        "movw r12, #0x0019\n"
        "movt r12, #0x800d\n"
        "blx r12\n"
        "1:\n"
        "pop {r0, r1, r2, r3, r4, lr}\n"
        "movw r12, #" XS(ARP_POLL_LO) "\n"
        "movt r12, #" XS(ARP_POLL_HI) "\n"
        "bx r12\n");
}

/* Every UI tick, on the Sound Generator page: the tracker's note there, through the entry MIDI IN on the page's
 * channel takes (the kits' note gates' SG route: r0 = 2, r1 note, r2 velocity, r3 0 on / 1 off), so ARP and drum
 * mode treat it as they treat MIDI. One note at a time: a new note lets go of the one before. Leaving the page
 * stops the Sound Generator's voices (as for MIDI), so what was playing is just forgotten there; a stopped tracker
 * (EXT SOURCE off, SLOW) lets go of it. Runs in the UI task: a note-on may wait about 3 ms for a busy voice to
 * fade (v9.5's stealing), as it does for MIDI, which the audio task must never do.
 * Test 4: the word's velocity (the pick's); the note plus OCT octaves (drum mode: the guitar's note, the pad it
 * strikes), played only within MIDI 12..127.
 * Test 5: silent unless EXT SOURCE is on and pair 0 is the input alone (the readout can run the tracker on the page on
 * Mix: its notes are not played). SY test 4: the hold (route_hold) makes pair 0 the input alone whatever ROUTING says,
 * so test 5's "SYNTH NEEDS ROUTING ExtIn" popup is gone.
 * SY test 6: drum mode strikes a pad for every guitar note: the kits play notes 36..51 only (pads 1..16), and the
 * guitar's E2..D#3 struck pads 5..16. Now the open low E is pad 1 (36), a pad a fret to G3 on pad 16, and the notes
 * outside an octave nearer at a time. */
UI_SMALL SCREEN static s32 syn_kit_note(s32 note) {
    s32 v = note - 40;
    while (v < 0) v += 12;
    while (v > 15) v -= 12;
    return 36 + v;
}

EXPORT UI_SMALL void syn_ui(void) {
    gsyn_t *s = &gsyn;
    u32 drum = KIT_MODE_ON;
    tt.drum = drum;                                     /* the tracker plays only plucks in drum mode */
    u32 w = tt.syn, seq = w >> 16;
    s32 note = (s32)(w & 0xFFu) - 1, vel = (s32)((w >> 8) & 0x7Fu);
    if (PAGE != SG_PAGE || sy.mode) {                  /* SY test 5: the SY screen plays the SY synth instead */
        if (PAGE == SG_PAGE && s->sounding >= 0) {     /* the screen opened on the page: let our note go */
            SG_MIDI_EVENT(2u, s->sounding, 0, 1);
            s->offs++;
        }
        s->sounding = -1;
        s->done = seq;
        return;
    }
    if (tt.state != TT_RUN || !syn_live(&tt)) {
        note = -1;
        s->done = seq;
    }
    if (seq != s->done) {
        s->done = seq;
        if (s->sounding >= 0) {
            SG_MIDI_EVENT(2u, s->sounding, 0, 1);
            s->offs++;
            s->sounding = -1;
        }
        if (note >= 0) {
            s32 oct = SG_OCT, out = note;
            if (!drum)
                out += 12 * (oct < -3 ? -3 : oct > 4 ? 4 : oct);
            else
                out = syn_kit_note(note);
            if (out >= 12 && out <= 127) {
                SG_MIDI_EVENT(2u, out, vel ? vel : SYN_VELOCITY, 0);
                s->ons++;
                s->sounding = out;
            }
        }
    } else if (note < 0 && s->sounding >= 0) {
        SG_MIDI_EVENT(2u, s->sounding, 0, 1);
        s->offs++;
        s->sounding = -1;
    }
}

/* Bounce's ui bridge (the popup tick, UI task, every millisecond) calls this in place of bnc_ui. */
EXPORT void diag_ui(int elapsed) {
    ((void (*)(int))BNC_UI)(elapsed);
    meter_ui_tick(elapsed);
    tune_ui();
    syn_ui();
    sy_ui();
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

/* SY test 4: what the recorder feed copies from pair 0 (sampling, resampling, the looper, skip-back all take the copy):
 * on ROUTING Mix while the chip is held on ExtIn, pair 1 x 2 (the mix before BUS 3/4: pads, input, synth, BUS 1/2's
 * effects; it comes back at half pair 0's level); on ExtIn, the input with the synth's newest block added. Only when the
 * feed takes pair 0 (else it takes pair 1 or another pair: as stock). The tracker has had pair 0 already. */
static void sy_rec(volatile s16 *packet) {
    tt_t *t = &tt;
    sy_t *s = &sy;
    u32 fresh = s->rec_fresh;
    s->rec_fresh = 0;
    if (!t->rec_mix && !t->rec_ext) return;
    if (FEED_PAIR1 || FEED_PAIR) {
        t->rec_other++;
        return;
    }
    if (t->rec_mix) {
        for (u32 f = 0; f < FRAMES; f++) {
            volatile s16 *q = packet + f * 16u;
            q[0] = (s16)sat16(2 * q[2]);
            q[1] = (s16)sat16(2 * q[3]);
        }
        t->rec_blocks++;
    } else if (fresh) {
        for (u32 f = 0; f < FRAMES; f++) {
            volatile s16 *q = packet + f * 16u;
            q[0] = (s16)sat16(q[0] + s->rec[f]);
            q[1] = (s16)sat16(q[1] + s->rec[f]);
        }
        t->rec_adds++;
    }
}

/* SY test 4: bounce's rx bridge calls this in place of the recorder feed (r0 the RX packet, r1 0x800, as the audio
 * task's RX site passes them): pair 0 for the tracker and the peaks first, then the recorder's pair 0, then the feed. */
EXPORT u32 sy_feed(volatile s16 *packet, u32 n) {
    tune_pairs(packet);
    sy_rec(packet);
    return FEED_ENTRY(packet, n);
}

/* Bounce's rx bridge (after the recorder feed, audio task) calls this in place of bnc_rx. Test 4: the pairs were read
 * before the feed (sy_feed). */
EXPORT void diag_rx_c(const volatile s16 *packet) {
    (void)packet;
    ((void (*)(void))BNC_RX)();
    tune_rx();
    sy_rx();
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
