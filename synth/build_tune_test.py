"""SY synth test 5, with guitar synth test 6 (note tracker 3), on v9.52 (test only).

SY synth test 1: a polyphonic guitar synth in the way BOSS's SY pedals work (Roland's patent US 9,542,923). The
input the effects chip hands back (RX pair 0) is split into 49 bands a semitone apart, E2..E6; each band's pitch
(its zero crossings) and level drive a saw of its own, the bands' sum goes through a resonant low-pass that opens with
the playing, and the result is added to the DRY pair of TX line 3 one block later. It plays on every page but the
Sound Generator's while EXT SOURCE is on and ROUTING on ExtIn. tunetest/sy_fp.c is the engine, tunetest/sy_ref.py
the same in Python and the tables (written into sy_tables.h at build time). See synth/SY_TEST.md.

SY synth test 2: 15 tones and OFF (tunetest/sy_ref.py's TONES), picked with VALUE held + pad 1-16 where the synth can
play (a popup names it; the pad's press and release go no further). The key presses come through FX deep edit's
bridges in v9.52: the UI dispatcher's key press and release handlers (0x8003abd0, 0x8003ada0) jump to them, and each
calls its handler (bl); the builder re-points those two calls to sy_key_down / sy_key_up, which hand every key to
FX deep edit's handlers first / unless the pick took it. The engine now runs on the tracker's stack.

SY synth test 3: VALUE held + CTRL 1-3 set the picked tone's BRIGHT, its own setting and LEVEL (the knob events through
FX deep edit's knob bridge, its call re-pointed to sy_knob, which asks FX deep edit's handler first). The picks and
knobs are kept in B:/_sy_tones.bin, with the stock file calls FX deep edit's file uses (their code checked here).

SY synth test 4: VALUE held + EXT SOURCE opens a picker (any page but the Sound Generator's): the pads light, a pad
picks (16: off), CTRL 1-3 edit without VALUE held; it closes after 4 s untouched, on EXIT, the chord again or another
key; VALUE goes on to FX deep edit's input FX screens (which the chord opened before). VALUE + pad and VALUE + CTRL are
stock's again. The synths no longer need ROUTING ExtIn: while one listens (EXT SOURCE on) the builder's entry
(0x800d8118, whose jump to FX deep edit's fde_dt1 now goes to sy_dt1 first) sends every ROUTING DT1 as ExtIn, and
bounce's rx bridge calls sy_feed in place of the recorder feed: the pairs for the tracker, then the recorder's pair 0
as ROUTING asks (Mix: pair 1 x 2, the mix before BUS 3/4; ExtIn: the input plus the synth), then the feed.

SY synth test 5: the guitar synth screen. EXT SOURCE held + RECORD SETTING (main screen or Sound Generator page) opens
the Sound Generator page in SY mode: its three knob columns show SOUND / TONE / LEVEL (SHIFT: OCTAVE / the tone's own
setting / SUSTAIN), the bar PRM: SOUND, the footer the sound's name; CTRL 1-3 set them, VALUE steps SOUND, a pad picks
one (16: OFF), and the page's pads, knobs, VALUE, REC and SUB PAD never reach stock there. Every UI event comes first
to sy_event: note repeat's bridge at the UI dispatcher's entry (0x8003b530 jumps to it) calls its handler with one bl,
which the builder re-points (sy_event hands everything else on to it). The screen is drawn through the page's own
widgets: the SG knob column class's draw pointer (0x8022bbd4, the kits' kit_ui_draw), the footer class's
(0x802256fc, the kits' kit_ui_footer_draw) and the SG page's update (0x80229678, kits save's ks_sg_poll) now point to
sy_col_draw / sy_foot_draw / sy_sg_poll, and the arp's three bar bridges (its jumps at 0x800bbc98, 0x80123be6,
0x80123ce0) go to sy_bar_name / sy_bar_text / sy_bar_poll first; each hands on to what it replaced outside the screen.
The engine (tunetest/sy_fp.c, sy_ref.py): FUND (a note from its lowest band only), SUSTAIN, OCTAVE, new tones. Test 4's
picker is gone (VALUE + EXT SOURCE is FX deep edit's again, its key and knob calls no longer re-pointed).

On the Sound Generator page, guitar synth test 6 as before:
The input the effects chip hands back (RX pair 0, after the input FX) goes through a note tracker on the main
processor (YIN, an analysis every 5.3 ms); on the Sound Generator page with EXT SOURCE on and ROUTING on ExtIn, its
note plays there as MIDI IN would. Test 4: a pick's click (the energy over 2 kHz) counts as a pluck too, only clean
readings count, a new note picked while the one before rings always plays, the velocity is the pick's, OCT moves the
note; test 3's voice following is gone. Test 5: on ROUTING Mix pair 0 is the mix as heard, so the synth stays silent
there and the page says so in a popup. Test 6: a move or a pick going steady needs the level to hold (a fretted note
let go: the open string rang far quieter and test 5 played it), a fast drop lets go, and a pick over strings ringing
is read from what it added (the difference function less the one from before it), so a chord's notes picked one by
one play. The CPU meter's readout (hold EXIT on the main screen) shows the tracker. See
synth/TUNE_TEST.md.

The input is v9.52 (combined-test17); the hooks are cabinet test 2's (IR diagnostic test 3's):
  0x0001c2d0  mixer entry (12 bytes)             -> meter_mix_entry
  0x80005870  per-voice stub (12 bytes)          -> meter_voice
  0x0001fd84  the fork's SG stub, pre call's movw/movt (8 of 10 bytes) -> meter_sg_pre
  bounce's ui bridge, its bnc_ui call's movw/movt (8 bytes) -> diag_ui (bnc_ui, the meter, tune_ui)
  bounce's rx bridge, its bnc_rx call's movw/movt (8 bytes) -> diag_rx (bnc_rx, tune_rx, sy_rx)
  bounce's rx bridge, its feed call's movw/movt (8 bytes) -> sy_feed (SY test 4: tune_pairs, sy_rec, the feed)
  0x800d8118  the DT1 builder's jump to FX deep edit's fde_dt1, its movw/movt (8 bytes) -> sy_dt1 (SY test 4)
  note repeat's nr_event bridge (0x83fdc000), its bl nr_event_c (4 bytes) -> sy_event (SY test 5)
  0x8022bbd4, 0x802256fc, 0x80229678  the SG column draw, footer draw, page update pointers -> sy_col_draw,
              sy_foot_draw, sy_sg_poll (SY test 5)
  0x800bbc98, 0x80123be6, 0x80123ce0  the arp's jumps to its bar bridges, their movw/movt (8 bytes) -> sy_bar_name,
              sy_bar_text, sy_bar_poll (SY test 5)
The module (tunetest/: the integer side tune_test.c, the FPU side tune_fp.c, and the tracker's memory) goes in a new
boot copy row at BASE, in the free SDRAM between the kits' last zero row (0x83fc8450) and sg-subpad's row
(0x83fd4000).

usage: python synth/build_tune_test.py IN_APP1 OUT_DIR --zig ZIG [--build-dir DIR]
Needs Zig 0.13.0, capstone and keystone. Refuses to overwrite an existing output.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import capstone
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB, KS_MODE_LITTLE_ENDIAN

HERE = Path(__file__).resolve().parent
SRC = HERE / 'tunetest'
sys.path.insert(0, str(SRC))
import sy_ref  # noqa: E402  (the SY engine's tables)
INTEGER_SOURCE = SRC / 'tune_test.c'           # none of its functions may hold an FPU instruction
SOURCES = [INTEGER_SOURCE, SRC / 'tune_fp.c', SRC / 'sy_fp.c']
HEADERS = [SRC / 'tune_test.h', SRC / 'sy_ref.py']   # sy_ref.py writes sy_tables.h
THIRD_PARTY = ()
TEST_PLAN = SRC / 'HARDWARE_TEST.md'
FLASH, COPY, ZERO = 0x60080000, 0x600800E4, 0x60080100
FLASH_END = 0x603FF000              # settings sector: the image must end below it
FLASH_RO = (0x60300000, 0x60700000)  # MPU region 2: flash, cacheable, read-only
APP0_SHA = '3e35ff30137f741a715566e205384f9b434ca7ac3847e247bad3f0c9c8a2bd23'
REVISION = 'sy-synth-test10'
BASE = 0x83FC9000
LIMIT = 0x83FD4000                  # sg-subpad's row starts here
GAP_END = 0x83FF0000                # cacheable SDRAM ends here
BOUNCE_SLOT = (0x83FE8000, 0x83FED000)
# SY test 3: sy_block (the engine's memory, section .sybss) outside the module, in the slot no v9.52 feature uses
# between FX deep edit's (to 0x83FE6000) and bounce's (from 0x83FE8000); a boot zero row clears it.
SY_SLOT = (0x83FE6000, 0x83FE8000)
SY_BSS = (0x83FE6000, 0x83FE6C00)
# SY test 5: the guitar synth screen's code (tune_test.c's functions in section .sytext) in the rest of that slot, a boot
# copy row of its own (the module's own slot is full)
SY_TEXT = (0x83FE6C00, 0x83FE8000)
TX_BRIDGE, RX_BRIDGE, UI_BRIDGE = 0x83FE8000, 0x83FE8030, 0x83FE8080   # bounce-3-test9's bridges
TX_SITE, RX_SITE, FEED, LOOP, TX_BACK, TICK_REST = 0x0001D090, 0x0001D0C2, 0x0001CA80, 0x0001D05C, 0x0001D09A, 0x8006B95C

MIXER, ITCM_VENEER = 0x0001C2D0, 0x0001008E
STUB, RENDER_VENEER = 0x80005870, 0x800D2D5C
SG_CALL, SG_STUB, SG_PRE_SITE, SG_EXIT_SITE = 0x0001C766, 0x0001FD80, 0x0001FD84, 0x0001FDD4
UI_TICK, UI_CALLER = 0x8006B950, 0x8006F6FA
POPUP_POST, POPUP_CLOSE, KEY_QUERY, PAGE_QUERY = 0x800D3FF0, 0x8001F730, 0x800D9F20, 0x800D6380
PENDSV, CUR_TASK = 0x0000DD3C, 0x202BBBFC
ROUTING_GETTER = 0x80081158         # a stock getter of system 0x5c (INPUT SETTING's ROUTING), guarded below
# SY test 2: FX deep edit's key bridges (v9.52): the dispatcher's key press / release handler sites, where each bridge
# goes on in stock code, and FX deep edit's slot.
FDE_HOOKS = ((0x8003ABD0, 'down', 0x8003ABDD, ['push {r4, r5, r6, r7, lr}', 'sub sp, #4', 'ldrsh.w r4, [r0, #2]',
                                               'movw r0, #0xd314']),
             (0x8003ADA0, 'up', 0x8003ADAB, ['push {r4, r5, r7, lr}', 'ldrsh.w r4, [r0, #2]', 'movw r0, #0xd314']),
             (0x8003A8D8, 'knob', 0x8003A8E5, ['push {r4, r5, r6, lr}', 'mov r6, r0', 'ldrsh.w r4, [r0, #2]',
                                               'ldrsh.w r5, [r0, #4]']))
# SY test 3: stock code the file and the FX screen check rely on, unchanged since FX deep edit's test 11/12 checked it:
# (start, end, SHA-256 of the runtime bytes, what it establishes)
SHA_GUARDS = [
    (0x800DEC48, 0x800DEC74, '4c47643ec8919640e6d5e25d52995230bcb2544ac00915fb0b4f3a6c79718504',
     'file read (fd, buf, n) and open (path, flags: 0 read, 0x601 write, create, truncate)'),
    (0x800DEBD8, 0x800DEC48, '22abec76d1aba2f98baf9ba58a4383d2075417a6d981e86b791054dccef5d6bf', 'file close (fd)'),
    (0x800DD9B8, 0x800DD9F8, 'd204acf3596d8eab1eca7a6d4e1cf2aec6429890e0b05a88ed1357982cda0fb6',
     'file write (fd, buf, n): bytes written'),
    # SY test 5: the settings setter the screen switches EXT SOURCE on with (bounce's guard)
    (0x800DD0C0, 0x800DD0E0, '3e20a3e2a93b9efb07122e0dbe90268461453c13c9310ab2c018777060eef5cc',
     'settings set (obj, id, value, flag)'),
    (0x800A01C0, 0x800A01D8, '3bc4ce29b1296cab9716835efe4a5882e6bd89469d756e884a858981940aaee2',
     'a page\'s i-th view (list = page + 0x38), 0 past the last: the FX screen check walks TOP\'s'),
    (0x8005EDA8, 0x8005EE4A, 'c20fec979fc3f36e617c845a861d61a6201739654a997ff567b796b9c1dc2a3a',
     'TOP\'s registry handler: the page object [0x80cfd350] with vtable 0x8022ce5c (TOP\'s views at +0x38)'),
]
FDE_SLOT = (0x83FE2000, 0x83FE6000)
PAD_TEMPO = 0x80047DD0              # the stock sample tempo (BPM x 100) for a pad, as the arp asks it
# SY test 4: the DT1 builder's entry, where v9.52's FX deep edit jumps to its fde_dt1 (movw/movt ip, bx ip)
DT1_ENTRY = 0x800D8118
# SY test 5: note repeat's bridge at the UI dispatcher's entry (every UI event; its bl nr_event_c -> sy_event)
NR_SITE = 0x8003B530
NR_SLOT = (0x83FDC000, 0x83FDE000)
NR_RESUME = 0x8003B53B
# The SG page's widget pointers (v9.52: the kits' column and footer draws, kits save's page update) and the arp's jumps
# to its bar bridges (item name, value text, the bar's update): (address, value in v9.52, ours, the C's name for it,
# what it is)
SG_POINTERS = ((0x8022BBD4, 0x83FA755D, 'sy_col_draw', 'KIT_COL_DRAW', "the SG knob column class's draw (kit_ui_draw)"),
               (0x802256FC, 0x83FA76B5, 'sy_foot_draw', 'KIT_FOOT_DRAW', "the footer class's draw (kit_ui_footer_draw)"),
               (0x80229678, 0x83FD504B, 'sy_sg_poll', 'KS_SG_POLL', "the SG page's update (kits save's ks_sg_poll)"))
BAR_SITES = ((0x800BBC98, 0x83FA2001, 'sy_bar_name', 'ARP_NAME', "the item name: the arp's jump to its name bridge"),
             (0x80123BE6, 0x83FA2061, 'sy_bar_text', 'ARP_TEXT', "the value text: the arp's jump to its draw bridge"),
             (0x80123CE0, 0x83FA2161, 'sy_bar_poll', 'ARP_POLL', "the bar's update: the arp's jump to its poll bridge"))
# What the arp's bridges are (the screen's bridges go on into them, or past them into stock)
ARP_BRIDGES = {0x83FA2000: ['cmp r5, #5', 'bls #0x83fa202a', 'cmp r5, #0x16', 'bhi #0x83fa2020', 'mov r0, r5',
                            'mov r1, r4'],
               0x83FA2060: ['movw ip, #0x4fa1', 'movt ip, #0x800d', 'blx ip', 'cmp r6, #5', 'bls #0x83fa208a',
                            'cmp r6, #0x16', 'bhi #0x83fa2080', 'mov r0, r6', 'add r1, sp, #0x28'],
               0x83FA2160: ['push {r4, r5, r6, lr}', 'mov r4, r0']}

EXPORTS = ('meter_mix_entry', 'meter_mix_exit', 'meter_voice', 'meter_sg_pre', 'meter_sg_end',
           'meter_mix_begin', 'meter_mix_end', 'meter_ui_tick', 'tune_format', 'diag_ui', 'diag_rx',
           'tune_rx', 'tune_ui', 'tune_pairs', 'diag_rx_c', 'tune_fp_call', 'tune_fp_step', 'syn_ui', 'memset',
           'memcpy', 'meter', 'tt', 'tt_block', 'tt_layout', 'gsyn', 'sy_rx', 'sy_tx', 'sy_ui', 'sy_fp_call',
           'sy_fp_step', 'sy', 'sy_block', 'sy_layout', 'sy_path', 'sy_file', 'sy_feed', 'sy_dt1', 'sy_route_dt1',
           'sy_event', 'sy_shown', 'sy_col_draw', 'sy_foot_draw', 'sy_sg_poll', 'sy_bar_name', 'sy_bar_text',
           'sy_bar_poll', 'sy_bar_name_c', 'sy_bar_text_c', 'sy_bar_poll_c', 'sy_col_text', 'sy_foot_text')
DATA = ('meter', 'tt', 'tt_block', 'tt_layout', 'gsyn', 'sy', 'sy_block', 'sy_layout', 'sy_path', 'sy_file')

# Exact instructions at and around every site (capstone text).
GUARDS = [
    (MIXER, 12, ['push.w {r4, r5, r6, r7, r8, sb, sl, fp, lr}', 'sub sp, #0x1c', 'movw r1, #0xb93c',
                 'str r0, [sp, #8]'], 'mixer entry: the four instructions meter_mix_entry re-creates'),
    (TX_SITE, 10, ['movw ip, #0x8001', 'movt ip, #0x83fe', 'bx ip'],
     "audio task TX: bounce's jump to its tx bridge, which calls the mixer (checked in bounce_bridges)"),
    (RX_SITE, 10, ['movw ip, #0x8031', 'movt ip, #0x83fe', 'bx ip'],
     "audio task RX: bounce's jump to its rx bridge, which calls the recorder feed"),
    (0x0001C6EA, 4, ['movw fp, #0xe1a0'], 'voice loop: slot base low half'),
    (0x0001C6FA, 4, ['movt fp, #0x202a'], 'voice loop: slot base 0x202ae1a0'),
    (0x0001C710, 18, ['add.w r0, fp, r6', 'mov r1, sb', 'mov r2, sl', 'mov r3, r7', 'strd r4, r4, [sp, #0xc]',
                      'bl #0x1008e'], 'voice loop: per-voice call (slot, stems, &bus, &bus2), bus/bus2 = -1'),
    (0x0001C724, 2, ['adds r6, #0x58'], 'voice loop: slot stride 0x58'),
    (0x0001C738, 6, ['cmp.w r6, #0xb00', 'bne #0x1c710'], 'voice loop: 32 slots'),
    (ITCM_VENEER, 10, ['movw ip, #0x5871', 'movt ip, #0x8000', 'bx ip'], 'ITCM veneer to the SDRAM stub'),
    (STUB, 12, ['ldr r0, [r0]', 'cmp r0, #0', 'it eq', 'bxeq lr', 'b.w #0x800d2d5c'],
     'per-voice stub: empty slot returns, else renderer'),
    (RENDER_VENEER, 10, ['movw ip, #0x4b89', 'movt ip, #1', 'bx ip'], 'veneer to the renderer 0x14b88'),
    (SG_CALL, 4, ['bl #0x1fd80'], 'mixer: the fork SG render stub'),
    (SG_STUB, 4, ['push.w {r4, r5, r6, r7, r8, lr}'], 'SG stub frame: the mixer return is at [sp, #20]'),
    (UI_TICK, 12, ['movw ip, #0x8081', 'movt ip, #0x83fe', 'bx ip', 'nop'],
     "popup tick entry: bounce's jump to its ui bridge, which re-creates the four stock instructions"),
    (UI_CALLER, 4, ['b.w #0x8006b950'], 'the popup tick is reached from the UI timer tick'),
    (0x0001D0B4, 14, ['ldr r0, [r6, #4]', 'subs r1, r0, #1', 'it ne', 'addne r1, r0, #1', 'str r1, [r6, #4]',
                      'add.w r0, sb, r1, lsl #11'],
     'audio task RX site: this block\'s bank to [r6 + 4], the packet r9 + bank << 11 (diag_rx recomputes it)'),
    (POPUP_POST, 0x36, ['push {r4, lr}', 'mov r4, r1', 'mov r1, r0', 'movw r0, #0x68d8', 'movt r0, #0x8024',
                        'bl #0x800d31da', 'movw r0, #0x589c', 'movt r0, #0x8024', 'ldrb r1, [r0]', 'str r4, [r0, #8]',
                        'cmp r1, #0', 'it eq', 'popeq {r4, pc}', 'movs r1, #3', 'str r1, [r0, #4]',
                        'movw r0, #0x22ac', 'movs r1, #1', 'movt r0, #0x8059', 'strb r1, [r0]', 'pop {r4, pc}'],
     'popup post (text, ms): text to 0x802468d8, request 0x802458a0 = 3'),
    (POPUP_CLOSE, 0x32, ['push {r4, r5, r6, lr}', 'movw r4, #0x22ac', 'movt r4, #0x8059', 'ldr r0, [r4, #0x1c]',
                         'cbz r0, #0x8001f748', 'ldr r1, [r0]', 'ldr r1, [r1, #4]', 'blx r1', 'movs r0, #0',
                         'str r0, [r4, #0x1c]', 'ldr r0, [r4, #4]', 'cbz r0, #0x8001f756', 'ldr r1, [r0]',
                         'ldr r1, [r1, #4]', 'blx r1', 'movs r0, #0', 'str r0, [r4, #4]', 'movw r6, #0x589c',
                         'mov.w r5, #-1', 'movt r6, #0x8024'],
     'popup close: frees the popup bitmap at 0x805922b0 (the meter reads it as "a popup is showing")'),
    # The kits replace this function's first 12 bytes with their key gate (kit_ui_key_query, which
    # reads the same bytes); the stock body that documents the layout is still there.
    (KEY_QUERY + 0xC, 0x1E, ['movw r2, #0x2438', 'and r0, r0, #7', 'movt r2, #0x8059', 'add.w r1, r2, r1, lsr #3',
                             'ldrb r1, [r1, #0x10]', 'lsr.w r0, r1, r0', 'and r0, r0, #1', 'bx lr'],
     'key state: bit k of the bytes at 0x80592448, keys 0..0x54'),
    (PAGE_QUERY, 0x0E, ['movw r0, #0x5874', 'movt r0, #0x8024', 'ldrsh.w r0, [r0, #0xc]', 'bx lr'],
     'current page: the int16 at 0x80245880'),
    # INPUT SETTING's ROUTING (Mix 0, ExtIn 1; the looper's SHIFT + CTRL 2 shows the same setting) is system 0x5c,
    # Resample_Routing in the parameter names: this stock getter reads it with SHIFT (key 0x2a) held, through the
    # system getter tune_ui uses, index -1. tune_ui reads it the same way.
    (ROUTING_GETTER, 0x1E, ['movs r0, #0x2a', 'bl #0x800d9f20', 'cbz r0, #0x80081190', 'movw r0, #0xeed0',
                            'movs r1, #0x5c', 'movt r0, #0x82df', 'mov.w r2, #-1', 'pop.w {r7, lr}',
                            'b.w #0x800da010'],
     "ROUTING: the looper's SHIFT + CTRL 2 getter reads system 0x5c (object 0x82dfeed0, index -1) with 0x800da011"),
    # The kernel's task switch: the running task's TCB at 0x202bbbfc, its FPU registers switched when TCB+0x10 has
    # 0x1000 (the readout's F flag reads the audio task's).
    (PENDSV + 0x14, 10, ['ldr r4, [pc, #0x90]', 'mov.w r0, #0', 'ldr.w r8, [r4]'],
     'PendSV: r4 = &running task (literal 0x202bbbfc, checked)'),
    (PENDSV + 0x62, 8, ['ldr.w r0, [r8, #0x10]', 'ands r0, r0, #0x1000'],
     'PendSV: the incoming task\'s attribute; 0x1000 switches its FPU registers s16-s31'),
    # SY test 2: the SP's tempo as the arp reads it (arp.c refresh_tempo: PAD_TEMPO(bank x 16), bank 0x82dfff44)
    (PAD_TEMPO, 0x0C, ['push {r4, r5, r6, lr}', 'movw r4, #0x9d0', 'movt r4, #0x82e0', 'ldr r1, [r4, #0x50]'],
     'the sample tempo for a pad (r0 pad; BPM x 100), the function the arp calls for the tempo'),
    # SY test 4: the recorder feed's choice of pair (sy_rec gives pair 0 only when the feed takes it): word 2 (pair 1)
    # when settings + 0x64 is set, else twice the byte at 0x82e0e71c + 0x258; the frame read at r4 + word * 2.
    (FEED + 0x18, 0x2E, ['movw r0, #0xe71c', 'movt r0, #0x82e0', 'bl #0x1bb64', 'movw r1, #0x1144', 'movs r2, #2',
                         'movt r1, #0x82e0', 'movw ip, #0x179c', 'movt ip, #0x8059', 'movw lr, #0xd0a0',
                         'ldr r1, [r1, #0x64]', 'movt lr, #0x202a', 'cmp r1, #0', 'it eq', 'lsleq r2, r0, #1'],
     'recorder feed: pair 1 when [0x82e01144 + 0x64] is set, else the pair 0x1bb64 returns'),
    (0x0001BB64, 6, ['ldrb.w r0, [r0, #0x258]', 'bx lr'], 'the feed\'s pair: the byte at 0x82e0e71c + 0x258'),
    (FEED + 0x46, 0x0C, ['add.w r1, r4, r2, lsl #1', 'ldrh.w r4, [ip]', 'movs r2, #0', 'b #0x1caf2'],
     'recorder feed: reads the packet (r0 on entry, in r4) at that word'),
    # SY test 10: the looper
    (0x8015C676, 6, ['movs r0, #0x27', 'bl #0x800da598'], "the SG page's MARK asks for page 0x27, the looper"),
    (0x8015C6B0, 0x10, ['movw r0, #0xb71c', 'movt r0, #0x82e0', 'ldrb.w r0, [r0, #0x210]', 'cmp r0, #0'],
     "the SG page's REC: looper mode on (the byte at 0x82e0b92c) hands REC to the looper (LOOPER_ON)"),
    # SY test 6: REMAIN on the Sound Generator page, the FX screens, the bar's PRM part
    (0x8003ABD0, 0x0A, ['movw ip, #0x221f', 'movt ip, #0x83fe', 'bx ip'],
     "the UI dispatcher's key press: FX deep edit's bridge first (sy_stock_key hands a REMAIN tap and an EXIT here)"),
    (0x8003ABEE, 0x1E, ['movw r6, #0x2438', 'lsrs r0, r5, #3', 'movt r6, #0x8059', 'and r1, r5, #7', 'movs r2, #1',
                        'uxtab r0, r6, r0', 'lsl.w r1, r2, r1', 'ldrb r3, [r0, #0x10]', 'orrs r1, r3',
                        'strb r1, [r0, #0x10]'],
     "a key press sets the key's held bit at 0x80592448 (sy_key_bit does as it does for a REMAIN it takes)"),
    (0x8003ADA0, 0x0A, ['movw ip, #0x2249', 'movt ip, #0x83fe', 'bx ip'],
     "the UI dispatcher's key release: FX deep edit's bridge first (sy_stock_key)"),
    (0x80146F64, 0x18, ['movs r0, #0x24', 'bl #0x800d9f20', 'strb.w r0, [r6, #0x2a]', 'cbz r0, #0x80146f7c',
                        'movw r0, #0x2320', 'movs r1, #1', 'movt r0, #0x8059', 'strb r1, [r0]'],
     "the FX screen's show: REMAIN (0x24) held freezes it and sets 0x80592320 (FX_FROZEN)"),
    (0x8005BA98, 0x0C, ['movw r0, #0x2320', 'movt r0, #0x8059', 'ldrb r0, [r0]', 'bx lr'],
     "the FX screen's frozen flag, the byte at 0x80592320"),
    (0x8015C590, 2, ['lsls r4, r2, #4'], "the SG page's key table: REMAIN (0x24) to 0x8015c790"),
    (0x8015C790, 0x0C, ['movw r1, #0x9800', 'movt r1, #0x8024', 'ldr r0, [r1, #0xc]', 'cmp r0, #0'],
     "the SG page's REMAIN: the preview bus at 0x8024980c (a tap is handed on to it)"),
    (0x80123AF8, 0x10, ['ldr r0, [sp, #0x74]', 'str r0, [sp, #0x24]', 'ldr r5, [sp, #0x6c]', 'str r5, [sp, #0x1c]',
                        'movs r1, #0x49', 'str r1, [sp, #0x18]', 'movs r1, #0x5f', 'str r1, [sp, #0x20]'],
     "the bar's item box: x 73..95, y0 at sp + 0x1c, y1 at sp + 0x24 (sy_bar_text paints x 57..127 over)"),
    # SY test 5, the guitar synth screen: the stock code its draws and bridges use or go on into
    (0x800BBCC2, 4, ['add sp, #0x68', 'pop {r4, r5, r7, pc}'], "the bar's item name function ends (sy_bar_name)"),
    (0x80123C5A, 12, ['ldr.w r0, [sb, #0x14]', 'cmp r0, #1', 'bne #0x80123c7a', 'ldr.w r0, [r4, #0x84]'],
     "the bar's value text: drawn from sp + 0x28 here (the arp's draw bridge and sy_bar_text go on here)"),
    (0x800DA598, 8, ['push {r4, lr}', 'mov r4, r0', 'cmp r0, #1', 'bne #0x800da5b0'],
     'a page asked for (the kits\' KIT_PAGE_REQUEST): the screen asks for the SG page (0x1e)'),
    (0x800D0018, 0x16, ['ldrb.w r1, [r0, #0x94]', 'cmp r1, #0', 'itt ne', 'movne r1, #1', 'strbne.w r1, [r0, #0x55]',
                        'movs r1, #1', 'strb.w r1, [r0, #0x78]', 'bx lr'], 'a widget drawn again (flags only)'),
    (0x800D8018, 8, ['ldr r0, [r0]', 'ldr r3, [r0]', 'ldr r3, [r3, #0x20]', 'bx r3'], 'draw colour (fb, fore, back)'),
    (0x800CE580, 0x0A, ['push {r4, r5, r7, lr}', 'sub sp, #0x10', 'mov r4, r0', 'mov r5, sp', 'ldr r0, [r1, #0xc]'],
     'clear a rectangle (fb, x0 y0 x1 y1)'),
    (0x800D80D8, 8, ['ldr r0, [r0]', 'ldr r2, [r0]', 'ldr r2, [r2, #0x58]', 'bx r2'],
     'draw font (fb, id): the stock column draw uses 0x1d for the value, 2 for the rest'),
    (0x800D4FA0, 0x0C, ['push.w {r4, r5, r6, r7, r8, sb, sl, lr}', 'sub sp, #0x18', 'mov r6, r0', 'mov r0, r3',
                        'mov r4, r3'], 'draw text centred (fb, x, y, text)'),
    (0x8015BF18, 0x0A, ['push {r4, r5, r7, lr}', 'movw r1, #0x1a70', 'mov r4, r0', 'adds r5, r0, r1'],
     "the stock SG page update: its knob columns at page + 0x1a6c..0x1a74 (the kits' children)"),
    (0x80170838, 0x10, ['ldr.w r0, [r4, #0x308]', 'strh.w r0, [fp, #8]', 'cmp r0, #3', 'ldr.w r1, [r4, #0x310]'],
     'the stock knob column draw: its descriptor type at +0x308, its parameter at +0x310'),
]

MD = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
KS = Ks(KS_ARCH_ARM, KS_MODE_THUMB | KS_MODE_LITTLE_ENDIAN)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def lf(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


def listing(code, at):
    return [f'{i.mnemonic} {i.op_str}'.strip() for i in MD.disasm(code, at)]


def scatter(img):
    a, b = struct.unpack_from('<2I', img, 0x80)
    return [list(struct.unpack_from('<4I', img, i)) for i in range(a + 0x80, b + 0x80, 16)]


def file_offset(img, addr, size):
    for load, dst, n, fn in scatter(img):
        if fn == COPY and load and dst <= addr and addr + size <= dst + n:
            return load - FLASH + addr - dst
    raise ValueError(f'{addr:#x} not in a copy row')


def read(img, addr, size):
    off = file_offset(img, addr, size)
    return bytes(img[off:off + size])


def movw_movt(code, at):
    """(target, register) of a movw/movt pair, else None."""
    ins = list(MD.disasm(code, at))
    if len(ins) < 2 or ins[0].mnemonic != 'movw' or ins[1].mnemonic != 'movt':
        return None
    r0, r1 = ins[0].op_str.split(',')[0], ins[1].op_str.split(',')[0]
    if r0 != r1:
        return None
    return (int(ins[1].op_str.split('#')[-1], 0) << 16) | int(ins[0].op_str.split('#')[-1], 0), r0


def code_rows(img):
    """Copy rows holding code (ITCM and SDRAM), as (address, bytes)."""
    out = []
    for load, dst, n, fn in scatter(img):
        if fn == COPY and load and (dst < 0x20000 or 0x80000000 <= dst < 0x84000000):
            off = load - FLASH
            out.append((dst, bytes(img[off:off + n])))
    return out


def branches_into(img, lo, hi):
    """Direct Thumb branches (B, BL, B<cc>, CBZ/CBNZ) anywhere in the code rows whose target lies in
    [lo, hi). Linear decoding at every halfword, so data that happens to decode as a branch can
    show up too; the callers only use this to prove that nothing lands inside a displaced span."""
    hits = []
    for base, data in code_rows(img):
        for off in range(0, len(data) - 1, 2):
            h1 = struct.unpack_from('<H', data, off)[0]
            pc = base + off + 4
            target = None
            if (h1 & 0xF800) == 0xF000 and off + 4 <= len(data):
                h2 = struct.unpack_from('<H', data, off + 2)[0]
                if (h2 & 0xD000) in (0x9000, 0xD000, 0xC000):         # B.W / BL / BLX
                    s = (h1 >> 10) & 1
                    j1, j2 = (h2 >> 13) & 1, (h2 >> 11) & 1
                    i1, i2 = 1 - (j1 ^ s), 1 - (j2 ^ s)
                    imm = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
                    if s:
                        imm -= 1 << 25
                    target = pc + imm
                elif (h2 & 0xD000) == 0x8000 and ((h1 >> 6) & 0xE) != 0xE:   # B<cc>.W
                    s = (h1 >> 10) & 1
                    j1, j2 = (h2 >> 13) & 1, (h2 >> 11) & 1
                    imm = (s << 20) | (j2 << 19) | (j1 << 18) | ((h1 & 0x3F) << 12) | ((h2 & 0x7FF) << 1)
                    if s:
                        imm -= 1 << 21
                    target = pc + imm
            elif (h1 & 0xF800) == 0xE000:                              # B (T2)
                imm = (h1 & 0x7FF) << 1
                if imm & 0x800:
                    imm -= 0x1000
                target = pc + imm
            elif (h1 & 0xF000) == 0xD000 and (h1 & 0x0F00) < 0x0E00:   # B<cc> (T1)
                imm = (h1 & 0xFF) << 1
                if imm & 0x100:
                    imm -= 0x200
                target = pc + imm
            elif (h1 & 0xF500) == 0xB100:                              # CBZ / CBNZ
                target = pc + ((((h1 >> 9) & 1) << 6) | (((h1 >> 3) & 0x1F) << 1))
            if target is not None and lo <= target < hi:
                hits.append((base + off, target))
    return hits


def loaded_literal(img, off):
    """True if some Thumb PC-relative LDR/LDR.W/LDRD within 4 KB before `off` reads it."""
    for a in range(max(off - 4096, 0) & ~1, off, 2):
        h1 = struct.unpack_from('<H', img, a)[0]
        pc = (a + 4) & ~3
        if (h1 & 0xF800) == 0x4800 and pc + (h1 & 0xFF) * 4 == off:
            return True
        if a + 4 > len(img):
            continue
        h2 = struct.unpack_from('<H', img, a + 2)[0]
        if (h1 & 0xFF7F) == 0xF85F and (pc + (h2 & 0xFFF) if h1 & 0x80 else pc - (h2 & 0xFFF)) == off:
            return True
        if (h1 & 0xFE7F) in (0xE85F, 0xE95F) and (pc + (h2 & 0xFF) * 4 if h1 & 0x80 else pc - (h2 & 0xFF) * 4) == off:
            return True
    return False


def refs_into(img, lo_a, hi_a):
    """Loaded 32-bit literals and MOVW/MOVT pairs anywhere in the file that point into [lo_a, hi_a)."""
    hits = []
    for off in range(0, len(img) - 3, 4):
        v = struct.unpack_from('<I', img, off)[0]
        if lo_a <= v < hi_a and loaded_literal(img, off):
            hits.append(('literal', off, v))
    regs = {}
    for off in range(0, len(img) - 3, 2):
        h1, h2 = struct.unpack_from('<HH', img, off)
        if (h1 & 0xFBF0) in (0xF240, 0xF2C0) and not h2 & 0x8000:
            imm = ((h1 & 0xF) << 12) | (((h1 >> 10) & 1) << 11) | (((h2 >> 12) & 7) << 8) | (h2 & 0xFF)
            rd = (h2 >> 8) & 0xF
            if (h1 & 0xFBF0) == 0xF240:
                regs[rd] = (off, imm)
            elif rd in regs and off - regs[rd][0] <= 64:
                v = (imm << 16) | regs[rd][1]
                if lo_a <= v < hi_a:
                    hits.append(('movw/movt', off, v))
    return hits


def jump(target):
    """movw ip / movt ip / bx ip / nop: 12 bytes, any distance, no ITCM space."""
    code = bytes(KS.asm(f'movw ip, #{(target | 1) & 0xFFFF}\nmovt ip, #{(target | 1) >> 16}\nbx ip\nnop\n', 0)[0])
    if len(code) != 12:
        raise ValueError('jump encoding')
    return code


def ip_calls(code, at):
    """(movw address, target, the instruction after the pair) for every movw ip / movt ip pair."""
    ins = list(MD.disasm(code, at))
    out = []
    for k in range(len(ins) - 2):
        if ins[k].mnemonic == 'movw' and ins[k + 1].mnemonic == 'movt' and ins[k].op_str.startswith('ip,') and \
                ins[k + 1].op_str.startswith('ip,'):
            t = (int(ins[k + 1].op_str.split('#')[-1], 0) << 16) | int(ins[k].op_str.split('#')[-1], 0)
            out.append((ins[k].address, t, f'{ins[k + 2].mnemonic} {ins[k + 2].op_str}'.strip()))
    return out


def bounce_bridges(img):
    """Bounce-3-test9's three audio/UI bridges, as its builder writes them; the two calls to replace."""
    in_slot = lambda t: t & 1 and BOUNCE_SLOT[0] <= t < BOUNCE_SLOT[1]
    tx = read(img, TX_BRIDGE, 0x30)
    t = listing(tx, TX_BRIDGE)
    c = ip_calls(tx, TX_BRIDGE)
    if t[:2] != ['mov r0, r5', 'mov.w r1, #0x1000'] or [x[1:] for x in c[:1]] != [(MIXER | 1, 'blx ip')] or \
            len(c) < 3 or not in_slot(c[1][1]) or c[1][2] != 'blx ip' or c[2][1:] != (TX_BACK | 1, 'bx ip'):
        raise ValueError(f'bounce tx bridge {TX_BRIDGE:#x}: unexpected {t[:12]}')
    rx = read(img, RX_BRIDGE, 0x50)
    c = ip_calls(rx, RX_BRIDGE)
    if len(c) < 5 or c[0][2] != 'ldr.w ip, [ip]' or c[2][1:] != (FEED | 1, 'blx ip') or not in_slot(c[3][1]) or \
            c[3][2] != 'blx ip' or c[4][1:] != (LOOP | 1, 'bx ip'):
        raise ValueError(f'bounce rx bridge {RX_BRIDGE:#x}: unexpected {listing(rx, RX_BRIDGE)[:20]}')
    rx_call, bnc_rx, feed_call = c[3][0], c[3][1], c[2][0]
    ui = read(img, UI_BRIDGE, 0x30)
    t = listing(ui, UI_BRIDGE)
    c = ip_calls(ui, UI_BRIDGE)
    if t[:2] != ['push {r4, r5, r6, lr}', 'push {r0, r1}'] or len(c) < 2 or c[0][0] != UI_BRIDGE + 4 or \
            not in_slot(c[0][1]) or c[0][2] != 'blx ip' or t[5:9] != ['pop {r0, r1}', 'movw r4, #0x22ac', 'movt r4, #0x8059',
                                                                    'ldr r1, [r4, #8]'] or c[1][1:] != (TICK_REST | 1, 'bx ip'):
        raise ValueError(f'bounce ui bridge {UI_BRIDGE:#x}: unexpected {t[:12]}')
    return dict(rx_call=rx_call, bnc_rx=bnc_rx, ui_call=c[0][0], bnc_ui=c[0][1], feed_call=feed_call)


def dt1_hook(img):
    """SY test 4: v9.52's FX deep edit jumps from the DT1 builder's entry to its fde_dt1 (movw/movt ip, bx ip), which
    sends an FxType for slots 0-4 to fde_dt1_fxtype and everything else on to the builder (fde_dt1_stock). Returns
    fde_dt1 (Thumb) and its listing."""
    jump_code = read(img, DT1_ENTRY, 10)
    t = movw_movt(jump_code, DT1_ENTRY)
    if not t or t[1] != 'ip' or listing(jump_code, DT1_ENTRY)[2] != 'bx ip' or not t[0] & 1 or \
            not FDE_SLOT[0] <= t[0] < FDE_SLOT[1]:
        raise ValueError(f'{DT1_ENTRY:#x}: expected FX deep edit\'s jump to fde_dt1, found {listing(jump_code, DT1_ENTRY)}')
    at = t[0] & ~1
    body = listing(read(img, at, 0x10), at)
    if body[:2] != ['sub.w ip, r1, #0x7e', 'cmp.w ip, #4'] or not body[2].startswith('bhi.w #') or \
            not body[3].startswith('b.w #'):
        raise ValueError(f'fde_dt1 {at:#x}: unexpected {body}')
    stock = int(body[2].split('#')[-1], 0)
    tail = listing(read(img, stock, 0x14), stock)
    if tail != ['push.w {r4, r5, r6, r7, r8, sb, sl, fp, lr}', 'sub sp, #0xc', 'movw sb, #0xe1c8', 'movw ip, #0x8123',
                'movt ip, #0x800d', 'bx ip']:
        raise ValueError(f'fde_dt1_stock {stock:#x}: unexpected {tail}')
    return t[0], dict(entry=hex(DT1_ENTRY), fde_dt1=hex(at), fde_dt1_stock=hex(stock), listing=body[:4])


SG_NOTE_ON_SITE, SG_NOTE_OFF_SITE = 0x80066E64, 0x800670B8   # the stock note dispatcher: the kits' note gates


def sg_midi_entry(img):
    """The entry MIDI IN takes on the Sound Generator page (the synth's notes go there): the stock dispatcher's
    note-on and note-off sites jump to the kits' note gates (movw/movt ip, bx ip), and each gate's SG route loads the
    note, the velocity (0 for a note-off) and r3 (0 on, 1 off), restores the dispatcher's frame and b.w's to it."""
    out = {}
    for site, route in ((SG_NOTE_ON_SITE, ['ldrb r1, [r4, #2]', 'ldrb r2, [r4, #3]', 'movs r3, #0']),
                        (SG_NOTE_OFF_SITE, ['ldrb r1, [r4, #2]', 'movs r2, #0', 'movs r3, #1'])):
        mm = movw_movt(read(img, site, 8), site)
        if not mm or mm[1] != 'ip' or listing(read(img, site + 8, 2), site + 8) != ['bx ip']:
            raise ValueError(f"{site:#x}: expected the kits' jump to their note gate (movw/movt ip, bx ip)")
        gate = mm[0] & ~1
        ins = list(MD.disasm(read(img, gate, 0x60), gate))
        text = [f'{i.mnemonic} {i.op_str}'.strip() for i in ins]
        want = route + ['add sp, #4', 'pop.w {r4, r5, r6, r7, lr}']
        hits = [k for k in range(len(text) - len(want)) if text[k:k + len(want)] == want and
                text[k + len(want)].startswith('b.w #')]
        if len(hits) != 1:
            raise ValueError(f'note gate {gate:#x}: not one SG route ({text[:32]})')
        k = hits[0] + len(want)
        out[site] = dict(gate=gate, route=ins[hits[0]].address, entry=int(text[k].split('#')[-1], 0),
                         listing=text[hits[0]:k + 1])
    entries = {v['entry'] for v in out.values()}
    entry = entries.pop()
    if entries or not (0x83F80000 <= entry < GAP_END and not BASE <= entry < LIMIT):
        raise ValueError(f'the note gates reach no single SG entry in the fork module area: {out}')
    return entry | 1, {hex(s): dict(gate=hex(v['gate']), route=hex(v['route']), entry=hex(v['entry']),
                                    listing=v['listing']) for s, v in out.items()}


def kit_mode_flag(img, entry):
    """The kits' drum-mode byte (kit_mode), which the SG MIDI entry tests first: movw/movt r6 around a mov, then
    ldrb r7, [r6]; cmp r7, #0; beq (the melodic path). SY test 7: on combined-test18 (LEVEL for MIDI notes) the
    entry's first three instructions are a jump to sgl_midi_gate, which ends with them (push.w, sub sp, the movw r6)
    and jumps back to entry + 10: they are read there."""
    at = entry & ~1
    text = listing(read(img, at, 0x20), at)
    jump = movw_movt(read(img, at, 8), at)
    if jump and jump[1] == 'ip' and text[2] == 'bx ip':
        gate = jump[0] & ~1
        ins = list(MD.disasm(read(img, gate, 0x40), gate))
        gt = [f'{i.mnemonic} {i.op_str}'.strip() for i in ins]
        k = next((j for j in range(len(gt) - 5) if gt[j] == 'push.w {r4, r5, r6, r7, r8, sb, lr}'), None)
        back = movw_movt(read(img, ins[k + 3].address, 8), ins[k + 3].address) if k is not None else None
        if k is None or gt[k + 1] != 'sub sp, #4' or not gt[k + 2].startswith('movw r6, #') or not back or \
                back[1] != 'ip' or back[0] != (at + 10) | 1 or gt[k + 5] != 'bx ip':
            raise ValueError(f'SG MIDI entry {at:#x}: a jump to {gate:#x}, not the LEVEL gate expected ({gt[:12]})')
        text = gt[k:k + 3] + text[3:]
    if text[:2] != ['push.w {r4, r5, r6, r7, r8, sb, lr}', 'sub sp, #4'] or not text[2].startswith('movw r6, #') or \
            text[3] != 'mov r4, r1' or not text[4].startswith('movt r6, #') or \
            text[5:7] != ['ldrb r7, [r6]', 'cmp r7, #0'] or not text[7].startswith('beq #'):
        raise ValueError(f'SG MIDI entry {at:#x}: unexpected start {text[:8]}')
    addr = (int(text[4].split('#')[-1], 0) << 16) | int(text[2].split('#')[-1], 0)
    if not (0x83F80000 <= addr < GAP_END and not BASE <= addr < LIMIT):
        raise ValueError(f'kit mode byte {addr:#x} is not in the fork module area')
    return addr, text[:8]


def fde_bridges(img):
    """SY test 2: FX deep edit's key press and release bridges in the input: the dispatcher's handler jumps to each
    (movw/movt ip, bx ip), and each bridge is push {r0, lr}; bl <its handler>; mov ip, r0; pop {r0, lr}; cmp ip, #0;
    it ne; bxne lr, then the handler's displaced instructions and on in stock code. Returns each bridge's call
    (address) and handler."""
    out = {}
    for site, name, resume, displaced in FDE_HOOKS:
        jump_code = read(img, site, 10)
        target = movw_movt(jump_code, site)
        if not target or target[1] != 'ip' or listing(jump_code, site)[2] != 'bx ip':
            raise ValueError(f'{site:#x}: expected FX deep edit\'s jump (movw ip / movt ip / bx ip)')
        bridge = target[0]
        if not (bridge & 1 and FDE_SLOT[0] <= bridge < FDE_SLOT[1]):
            raise ValueError(f'{site:#x}: jump to {bridge:#x}, not into FX deep edit\'s slot')
        bridge &= ~1
        t = listing(read(img, bridge, 0x2C), bridge)
        want_head = ['push {r0, lr}', None, 'mov ip, r0', 'pop.w {r0, lr}', 'cmp.w ip, #0', 'it ne', 'bxne lr']
        tail = displaced + [f'movw ip, #{resume & 0xFFFF:#x}', f'movt ip, #{resume >> 16:#x}', 'bx ip']
        if any(w is not None and t[i] != w for i, w in enumerate(want_head)) or not t[1].startswith('bl #') or \
                t[7:7 + len(tail)] != tail:
            raise ValueError(f'FX deep edit {name} bridge {bridge:#x}: unexpected {t[:12]}')
        handler = int(t[1].split('#')[1], 16)
        if not FDE_SLOT[0] <= handler < FDE_SLOT[1]:
            raise ValueError(f'FX deep edit {name} handler {handler:#x} outside its slot')
        out[name] = dict(bridge=bridge, call=bridge + 2, handler=handler, listing=t[:7 + len(tail)])
    return out


def nr_hook(img):
    """SY test 5: note repeat's bridge at the UI dispatcher's entry, as its builder writes it: the dispatcher jumps to it
    (movw/movt ip, bx ip), and it is push {r0, lr}; bl nr_event_c; cmp r0, #0; pop {r0, lr}; it ne; bxne lr, then the
    dispatcher's four displaced instructions and on at its tbb. Returns the call's address and nr_event_c (Thumb)."""
    jump_code = read(img, NR_SITE, 10)
    t = movw_movt(jump_code, NR_SITE)
    if not t or t[1] != 'ip' or listing(jump_code, NR_SITE)[2] != 'bx ip' or not t[0] & 1 or \
            not NR_SLOT[0] <= t[0] < NR_SLOT[1]:
        raise ValueError(f'{NR_SITE:#x}: expected note repeat\'s jump to nr_event, found {listing(jump_code, NR_SITE)}')
    at = t[0] & ~1
    body = listing(read(img, at, 0x26), at)
    want = ['push {r0, lr}', None, 'cmp r0, #0', 'pop.w {r0, lr}', 'it ne', 'bxne lr', 'ldrsh.w r1, [r0]', 'subs r1, #5',
            'cmp r1, #0x20', 'it hi', 'bxhi lr', f'movw ip, #{NR_RESUME & 0xFFFF:#x}', f'movt ip, #{NR_RESUME >> 16:#x}',
            'bx ip']
    if len(body) < len(want) or any(w is not None and body[i] != w for i, w in enumerate(want)) or \
            not body[1].startswith('bl #'):
        raise ValueError(f'note repeat bridge {at:#x}: unexpected {body}')
    handler = int(body[1].split('#')[-1], 16)
    if not NR_SLOT[0] <= handler < NR_SLOT[1]:
        raise ValueError(f'nr_event_c {handler:#x} outside note repeat\'s slot')
    return at + 2, handler | 1, dict(site=hex(NR_SITE), nr_event=hex(at), call=hex(at + 2), nr_event_c=hex(handler),
                                     listing=body[:len(want)])


def screen_hooks(img):
    """SY test 5: the SG page's widget pointers and the arp's bar jumps as v9.52 has them, and the arp's bridges."""
    out = {}
    for addr, value, ours, name, what in SG_POINTERS:
        got = struct.unpack('<I', read(img, addr, 4))[0]
        if got != value:
            raise ValueError(f'{addr:#x} ({what}): expected {value:#x}, found {got:#x}')
        out[name] = dict(pointer=hex(addr), target=hex(value), what=what)
    for addr, value, ours, name, what in BAR_SITES:
        code = read(img, addr, 10)
        mm = movw_movt(code, addr)
        if not mm or mm[1] != 'ip' or mm[0] != value or listing(code, addr)[2] != 'bx ip':
            raise ValueError(f'{addr:#x} ({what}): expected movw/movt ip of {value:#x}, bx ip; found {listing(code, addr)}')
        out[name] = dict(site=hex(addr), target=hex(value), what=what)
    for at, want in ARP_BRIDGES.items():
        got = listing(read(img, at, 2 * len(want) + 8), at)[:len(want)]
        if got != want:
            raise ValueError(f'arp bridge {at:#x}: expected {want}, found {got}')
    return out


def check_guards(img):
    found = {}
    for addr, size, expect, why in GUARDS:
        got = listing(read(img, addr, size), addr)
        if got != expect:
            raise ValueError(f'{addr:#x} ({why}): expected {expect}, found {got}')
        found[addr] = dict(size=size, instructions=expect, why=why, hex=read(img, addr, size).hex())
    literal = PENDSV + 0xA8                                # ldr r4, [pc, #0x90] at PENDSV + 0x14
    if struct.unpack('<I', read(img, literal, 4))[0] != CUR_TASK:
        raise ValueError(f'PendSV literal {literal:#x}: expected the running task pointer {CUR_TASK:#x}')
    found['running_task'] = dict(literal=hex(literal), value=hex(CUR_TASK))
    # The SG stub: its pre call (movw/movt ip, blx ip) and its exit (movw/movt ip, bx ip) to a
    # continuation that ends in pop {r4-r8, pc}; nothing between touches sp or returns.
    pre = movw_movt(read(img, SG_PRE_SITE, 8), SG_PRE_SITE)
    if not pre or pre[1] != 'ip' or listing(read(img, SG_PRE_SITE + 8, 2), SG_PRE_SITE + 8) != ['blx ip']:
        raise ValueError(f'{SG_PRE_SITE:#x}: expected movw ip / movt ip / blx ip')
    pre_target = pre[0]
    if not (pre_target & 1 and 0x83F80000 <= pre_target < GAP_END and not BASE <= pre_target < LIMIT):
        raise ValueError(f'SG pre target {pre_target:#x} is not a Thumb address in the fork module area')
    body = listing(read(img, SG_PRE_SITE + 10, SG_EXIT_SITE - SG_PRE_SITE - 10), SG_PRE_SITE + 10)
    for ins in body:
        if 'sp' in ins or ins.startswith(('pop', 'push', 'bx', 'ldm', 'stm')):
            raise ValueError(f'SG stub body touches the frame: {ins}')
    ex = movw_movt(read(img, SG_EXIT_SITE, 8), SG_EXIT_SITE)
    if not ex or ex[1] != 'ip' or listing(read(img, SG_EXIT_SITE + 8, 2), SG_EXIT_SITE + 8) != ['bx ip']:
        raise ValueError(f'{SG_EXIT_SITE:#x}: expected movw ip / movt ip / bx ip')
    cont = ex[0] & ~1
    tail = listing(read(img, cont, 14), cont)
    if tail[:3] != ['mov r0, r4', 'mov r1, r5', 'mov r2, r6'] or not tail[3].startswith('bl #') or \
            tail[4] != 'pop.w {r4, r5, r6, r7, r8, pc}':
        raise ValueError(f'SG continuation {cont:#x}: unexpected {tail}')
    # The pre bridge returns with bx lr after restoring its frame, so entering it by a jump with
    # lr and sp as the stub's blx left them is the same as the stub's own call.
    bridge = listing(read(img, pre_target & ~1, 0x30), pre_target & ~1)
    pop = 'pop.w {r0, r1, r2, r3, ip, lr}'
    if bridge[:1] != ['push.w {r0, r1, r2, r3, ip, lr}'] or pop not in bridge or 'bx lr' not in bridge or \
            bridge.index('bx lr') < bridge.index(pop) or \
            any('sp' in i or 'lr' in i for i in bridge[bridge.index(pop) + 1:bridge.index('bx lr')]):
        raise ValueError(f'SG pre bridge {pre_target:#x}: unexpected {bridge}')
    found['sg'] = dict(pre_target=pre_target, continuation=cont, continuation_listing=tail[:5],
                       pre_bridge_listing=bridge[:bridge.index('bx lr') + 1])
    # Nothing may branch into the middle of a displaced span.
    bridges = bounce_bridges(img)
    for site, size in ((MIXER, 12), (STUB, 12), (SG_PRE_SITE, 10), (bridges['rx_call'], 8), (bridges['ui_call'], 8)):
        inside = [(hex(a), hex(t)) for a, t in branches_into(bytes(img), site + 1, site + size)]
        if inside:
            raise ValueError(f'branches into {site:#x}..{site + size:#x}: {inside[:4]}')
    # No direct branch reaches the mixer: bounce's tx bridge calls it (blx ip), and the meter's entry
    # keeps whatever return it is given.
    callers = [(hex(a), hex(t)) for a, t in branches_into(bytes(img), MIXER, MIXER + 1)]
    if callers:
        raise ValueError(f'mixer callers: {callers}')
    found['bounce'] = {k: hex(v) for k, v in bridges.items()}
    sg_midi, found['sg_midi'] = sg_midi_entry(img)
    kit_mode, start = kit_mode_flag(img, sg_midi)
    found['kit_mode'] = dict(address=hex(kit_mode), entry_listing=start)
    fde = fde_bridges(img)
    found['fde'] = {k: dict(bridge=hex(v['bridge']), call=hex(v['call']), handler=hex(v['handler']),
                            listing=v['listing']) for k, v in fde.items()}
    found['screen'] = screen_hooks(img)
    for lo, hi, digest, why in SHA_GUARDS:
        if sha(read(img, lo, hi - lo)) != digest:
            raise ValueError(f'{lo:#x}..{hi:#x} ({why}): its code is not the one FX deep edit checked')
        found[f'sha_{lo:#x}'] = dict(end=hex(hi), sha256=digest, why=why)
    return found, pre_target, bridges, sg_midi, kit_mode, fde


# ---- the cabinet IR: a stand-in, not a measured cabinet --------------------------------------------------------
CAB_STAGES = (('highpass', 80.0, 0.707, 0.0), ('peak', 120.0, 1.0, 4.0), ('peak', 450.0, 1.0, -4.0),
              ('peak', 2500.0, 1.5, 3.0), ('lowpass', 5000.0, 0.707, 0.0), ('lowpass', 5000.0, 0.707, 0.0))
CAB_FADE = 256                       # taps of half-Hann fade at the end


def elf_sections(data):
    if data[:7] != b'\x7fELF\x01\x01\x01' or struct.unpack_from('<H', data, 18)[0] != 40:
        raise ValueError('expected little-endian ARM ELF32')
    shoff = struct.unpack_from('<I', data, 32)[0]
    shsize, count, shstrndx = struct.unpack_from('<3H', data, 46)
    sections = [struct.unpack_from('<10I', data, shoff + i * shsize) for i in range(count)]
    names = data[sections[shstrndx][4]:sections[shstrndx][4] + sections[shstrndx][5]]
    return sections, names


def read_module(data, base, limit, extra=None, extra_text=None):
    """Allocated ELF sections (BSS as zeros), the global symbols, every function symbol with its size, and the
    .text span with its mapping symbols. A NOBITS section inside `extra` (lo, hi) is left out of the image; its span
    goes to extra_spans (SY test 3: sy_block). SY test 5: the section .sytext, inside `extra_text`, goes to sytext
    (address, bytes) and its maps to sytext_maps."""
    sections, names = elf_sections(data)
    syms, funcs, blocks, end, text = {}, [], [], base, None
    extra_spans, sytext = [], []
    for name, kind, flags, addr, off, size, link, info, align, entsize in sections:
        if flags & 2 and size:
            if extra and kind == 8 and extra[0] <= addr and addr + size <= extra[1]:
                extra_spans.append((addr, addr + size))
                continue
            if extra_text and extra_text[0] <= addr and addr + size <= extra_text[1]:
                if names[name:].split(b'\0')[0] != b'.sytext' or kind == 8:
                    raise ValueError(f'unexpected section at {addr:#x} in the screen\'s slot')
                sytext.append((addr, data[off:off + size]))
                continue
            if not base <= addr < limit or addr + size > limit:
                raise ValueError(f'ELF section at {addr:#x}+{size:#x} outside {base:#x}..{limit:#x}')
            blocks.append((addr, bytes(size) if kind == 8 else data[off:off + size]))
            end = max(end, addr + size)
            if names[name:].split(b'\0')[0] == b'.text':
                text = (addr, addr + size)
    maps = []
    for name, kind, flags, addr, off, size, link, info, align, entsize in sections:
        if kind == 2:
            strings = sections[link]
            strtab = data[strings[4]:strings[4] + strings[5]]
            for at in range(off, off + size, entsize):
                n, value, sym_size, sym_info = struct.unpack_from('<3IB', data, at)
                label = strtab[n:].split(b'\0')[0].decode('ascii')
                if sym_info >> 4 == 1 and label:
                    syms[label] = value
                if sym_info & 0xF == 2 and label:
                    funcs.append((label, value & ~1, sym_size))
                if label in ('$t', '$d', '$a') or label.startswith(('$t.', '$d.', '$a.')):
                    maps.append((value, label[1]))      # ARM ELF mapping symbols: code or data
    if text is None or text[0] != base:
        raise ValueError('expected .text first, at the base')
    out = bytearray(end - base)
    for addr, block in blocks:
        out[addr - base:addr - base + len(block)] = block
    read_module.extra_spans = extra_spans
    if len(sytext) > 1:
        raise ValueError('more than one .sytext')
    read_module.sytext = sytext[0] if sytext else None
    read_module.sytext_maps = sorted(set(maps))
    return bytes(out), syms, funcs, (text[0], text[1], sorted(set(maps)))


def integer_spans(map_text, obj):
    """[address, end) of every .text input section the link map gives for one object."""
    spans = []
    for line in map_text.splitlines():
        m = re.match(r'\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+(\S+):\((\.text[^)]*)\)\s*$', line)
        if m and Path(m.group(3)).name == obj:
            addr, size = int(m.group(1), 16), int(m.group(2), 16)
            if size:
                spans.append((addr, addr + size, m.group(4)))
    return spans


def compile_module(zig, folder, base, pre_target, bridges, sg_midi, kit_mode, fde_dt1, nr_event_c):
    folder.mkdir(parents=True, exist_ok=True)
    inc = folder / 'include'
    inc.mkdir(exist_ok=True)
    (inc / 'math.h').write_text('float fabsf(float);\nfloat fmaf(float, float, float);\nfloat fmaxf(float, float);\n',
                                encoding='ascii', newline='\n')
    (inc / 'string.h').write_text('#include <stddef.h>\nvoid *memcpy(void *, const void *, size_t);\n'
                                  'void *memset(void *, int, size_t);\nint memcmp(const void *, const void *, size_t);\n',
                                  encoding='ascii', newline='\n')
    (folder / 'tune_test_links.h').write_text(
        f'#define SG_PRE_TARGET {pre_target:#010x}\n#define BNC_UI {bridges["bnc_ui"]:#010x}u\n'
        f'#define BNC_RX {bridges["bnc_rx"]:#010x}u\n#define SG_MIDI {sg_midi:#010x}u\n'
        f'#define KIT_MODE {kit_mode:#010x}u\n'
        f'#define FDE_DT1_LO {fde_dt1 & 0xFFFF:#x}\n#define FDE_DT1_HI {fde_dt1 >> 16:#x}\n'
        f'#define NR_EVENT_C {nr_event_c:#010x}u\n' +
        ''.join(f'#define {name} {value | 1:#010x}u\n' for _, value, _, name, _ in SG_POINTERS) +
        ''.join(f'#define {name}_LO {value & 0xFFFF:#x}\n#define {name}_HI {value >> 16:#x}\n'
                for _, value, _, name, _ in BAR_SITES),
        encoding='ascii', newline='\n')
    (folder / 'sy_tables.h').write_text(sy_ref.c_header(), encoding='ascii', newline='\n')
    (folder / 'sy_names.h').write_text(sy_ref.c_names(), encoding='ascii', newline='\n')
    # The integer side (tune_test.o) first, from the base to tt_integer_end; then the FPU side. Unused sections go
    # (--gc-sections: Zig links its compiler_rt, of which only what something calls may stay).
    fp_keep = ' '.join(f'KEEP(*(.text.{n}))' for n in EXPORTS if n not in DATA and not n.startswith(('meter', 'diag')))
    (folder / 'tune_test.ld').write_text(f'''ENTRY(meter_mix_entry)
SECTIONS {{
 . = {base:#x};
 .text : {{ KEEP(*tune_test.o(.text.meter_mix_entry)) KEEP(*tune_test.o(.text*)) tt_integer_end = .; {fp_keep} *(.text*) }}
 .rodata : ALIGN(4) {{ KEEP(*(.rodata.tt_layout)) KEEP(*(.rodata.sy_layout)) *(.rodata*) }}
 .data : ALIGN(4) {{ *(.data*) }}
 .bss : ALIGN(32) {{ *(.bss*) *(COMMON) }}
 .sytext {SY_TEXT[0]:#x} : {{ KEEP(*(.sytext)) }}
 .sybss {SY_BSS[0]:#x} (NOLOAD) : {{ KEEP(*(.sybss)) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) *(.ARM.attributes) }}
}}
''', encoding='ascii', newline='\n')
    cache = folder / 'cache'
    env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(cache), ZIG_LOCAL_CACHE_DIR=str(cache))
    if subprocess.check_output([str(zig), 'version'], text=True).strip() != '0.13.0':
        raise ValueError('needs Zig 0.13.0')
    target = ['-target', 'thumb-freestanding-eabihf', '-mcpu=cortex_m7+fp_armv8d16sp']
    common = target + ['-O2', '-ffreestanding', '-fno-math-errno', '-fno-stack-protector', '-ffunction-sections',
                       '-fdata-sections', '-I', str(folder), '-I', str(inc), '-I', str(SRC)]
    objs = []
    for src in SOURCES:
        obj = folder / (src.stem + '.o')
        warn = ['-Wall'] if src in THIRD_PARTY else ['-Wall', '-Werror']
        subprocess.run([str(zig), 'cc', *common, *warn, '-c', str(src), '-o', str(obj)], check=True, env=env)
        objs.append(obj)
    elf = folder / 'tune_test.elf'
    subprocess.run([str(zig), 'cc', *target, '-nostdlib', '-Wl,--no-undefined', '-Wl,--build-id=none',
                    '-Wl,--gc-sections', '-Wl,-e,meter_mix_entry', '-Wl,-T,' + str(folder / 'tune_test.ld'),
                    *map(str, objs), '-o', str(elf)], check=True, env=env)
    code, syms, funcs, text = read_module(elf.read_bytes(), base, LIMIT, SY_BSS, SY_TEXT)
    extra = read_module.extra_spans
    st = read_module.sytext
    if not st or st[0] != SY_TEXT[0] or st[0] + len(st[1]) > SY_TEXT[1]:
        raise ValueError(f'the screen\'s code (.sytext) not at {SY_TEXT[0]:#x} within its slot: {st and hex(len(st[1]))}')
    compile_module.sytext = (st[0], st[1], (st[0], st[0] + len(st[1]), read_module.sytext_maps))
    if len(extra) != 1 or extra[0][0] != SY_BSS[0] or syms.get('sy_block') != SY_BSS[0]:
        raise ValueError(f'sy_block not alone at {SY_BSS[0]:#x}: {extra} {syms.get("sy_block")}')
    compile_module.sy_bss = extra[0]
    missing = [n for n in EXPORTS + ('tt_integer_end',) if n not in syms]
    if missing:
        raise ValueError(f'module symbols missing: {missing}')
    # Every function tune_test.o defines must have landed in the integer span.
    _, own, _, _ = read_module_obj(folder / 'tune_test.o')
    integer = [(base, syms['tt_integer_end'], 'tune_test.o'), (st[0], st[0] + len(st[1]), 'tune_test.o .sytext')]
    stray = [n for n, a, s in funcs if n in own and not base <= a < syms['tt_integer_end'] and
             not st[0] <= a < st[0] + len(st[1])]
    if stray or syms['meter_mix_entry'] & ~1 != base:
        raise ValueError(f'integer side outside its span: {stray}')
    return code, syms, funcs, text, integer


def read_module_obj(path):
    """The function names a relocatable object defines (STT_FUNC with a section)."""
    data = path.read_bytes()
    sections, _ = elf_sections(data)
    names = set()
    for name, kind, flags, addr, off, size, link, info, align, entsize in sections:
        if kind == 2:
            strings = sections[link]
            strtab = data[strings[4]:strings[4] + strings[5]]
            for at in range(off, off + size, entsize):
                n, value, sym_size, sym_info, _, shndx = struct.unpack_from('<3IBBH', data, at)
                label = strtab[n:].split(b'\0')[0].decode('ascii')
                if sym_info & 0xF == 2 and shndx and label:
                    names.add(label)
    return None, names, None, None


def code_spans(text):
    """Thumb code spans of .text from its mapping symbols ($t code, $d literal pools)."""
    start, end, maps = text
    marks = [(a, k) for a, k in maps if start <= a < end]
    if not marks or marks[0] != (start, 't') or any(k == 'a' for a, k in marks):
        raise ValueError(f'unexpected mapping symbols: {marks[:4]}')
    spans = []
    for (a, k), nxt in zip(marks, [m[0] for m in marks[1:]] + [end]):
        if k == 't' and nxt > a:
            spans.append((a, nxt))
    return spans


def check_module(code, text, base, integer, sytext=None):
    """Every code span decoded to its end; direct branches stay inside .text (SY test 5: or .sytext, whose own code is
    checked the same way); no FPU instruction in the integer side's functions (tune_test.c: the meter's hooks, the UI
    and the RX glue, the screen). Returns the FPU instruction count."""
    fpu = []
    spans = [(lo, hi, code, base) for lo, hi in code_spans(text)]
    if sytext:
        spans += [(lo, hi, sytext[1], sytext[0]) for lo, hi in code_spans(sytext[2])]
    inside = lambda t: text[0] <= t < text[1] or (sytext and sytext[2][0] <= t < sytext[2][1])  # noqa: E731
    for lo, hi, blob, at in spans:
        seen = lo
        for ins in MD.disasm(blob[lo - at:hi - at], lo):
            seen = ins.address + ins.size
            m = ins.mnemonic
            if m.startswith('v'):
                fpu.append(ins.address)
            base_m = m.split('.')[0]                    # SY test 6: 'bic.w ... asr #31' is no branch
            if m.startswith(('b', 'cb')) and base_m not in ('bx', 'blx', 'bkpt', 'bic', 'bics', 'bfc', 'bfi') and \
                    '#' in ins.op_str:
                target = int(ins.op_str.split('#')[-1], 16)
                if not inside(target):
                    raise ValueError(f'module branch at {ins.address:#x} to {target:#x}')
        if seen < hi and any(blob[seen - at:hi - at]):
            raise ValueError(f'code span {lo:#x}..{hi:#x} does not decode past {seen:#x}')
    for lo, hi, name in integer:
        bad = [hex(x) for x in fpu if lo <= x < hi]
        if bad:
            raise ValueError(f'FPU instruction in the integer side ({name}): {bad[:4]}')
    if not fpu:
        raise ValueError('no FPU instruction at all: the engine did not compile for the FPU')
    return len(fpu)


def append(img, data, align):
    at = (len(img) + align - 1) & ~(align - 1)
    img += bytes(at - len(img)) + data
    return at


def build(inp: Path, out: Path, zig: Path, base: int, build_dir: Path = None):
    img = bytearray(inp.read_bytes())
    app0 = inp.with_name('SP404MKII_APP0.bin')
    if sha(app0.read_bytes()) != APP0_SHA:
        raise ValueError('expected stock APP0 beside the input APP1')
    for name in ('SP404MKII_APP1.bin', 'SP404MKII_APP0.bin', 'manifest.json'):
        if (out / name).exists():
            raise ValueError(f'refusing to overwrite {out / name}')
    if not (BASE <= base and (base & 0xFFF) == 0 and base < LIMIT):
        raise ValueError(f'base {base:#x} outside {BASE:#x}..{LIMIT:#x}')
    guards, pre_target, bridges, sg_midi, kit_mode, fde = check_guards(img)
    fde_dt1, dt1_info = dt1_hook(img)
    nr_call, nr_event_c, nr_info = nr_hook(img)
    rows = scatter(img)
    for load, dst, n, fn in rows:
        if max(dst, base) < min(dst + n, LIMIT):
            raise ValueError(f'row {dst:#x}+{n:#x} overlaps the module area')
    hits = refs_into(bytes(img), base, LIMIT)
    if hits:
        raise ValueError(f'input refers to the module area: {hits[:4]}')
    for load, dst, n, fn in rows:                              # SY test 3: sy_block's slot is free in the input
        if max(dst, SY_SLOT[0]) < min(dst + n, SY_SLOT[1]):
            raise ValueError(f'row {dst:#x}+{n:#x} overlaps sy_block\'s slot')
    hits = refs_into(bytes(img), SY_SLOT[0], SY_SLOT[1])
    if hits:
        raise ValueError(f'input refers to sy_block\'s slot: {hits[:4]}')
    code, syms, funcs, text, integer = compile_module(zig, (build_dir or out / 'build').resolve(), base, pre_target,
                                                      bridges, sg_midi, kit_mode, fde_dt1, nr_event_c)
    end = base + len(code)
    if end > LIMIT or end > GAP_END:
        raise ValueError(f'module {base:#x}+{len(code):#x} passes {LIMIT:#x}')
    # Compiler helpers the link pulled in (they run from the integer side too) must be integer code as well.
    integer = integer + [(a, a + n, name) for name, a, n in funcs if name.startswith('__aeabi')]
    sytext = compile_module.sytext
    fpu_count = check_module(code, text, base, integer, sytext)
    block_bytes = struct.unpack_from('<I', code, syms['tt_layout'] - base + 11 * 4)[0]
    sy_block_bytes = struct.unpack_from('<I', code, syms['sy_layout'] - base + 6 * 4)[0]
    targets = {MIXER: syms['meter_mix_entry'], STUB: syms['meter_voice']}
    patches = []
    for site, target in targets.items():
        off = file_offset(img, site, 12)
        new = jump(target)
        if listing(new, site)[:3] != [f'movw ip, #{(target | 1) & 0xFFFF:#x}', f'movt ip, #{(target | 1) >> 16:#x}', 'bx ip']:
            raise ValueError(f'{site:#x}: bad jump encoding')
        patches.append(dict(address=site, size=12, original_hex=bytes(img[off:off + 12]).hex(),
                            replacement_hex=new.hex(), target=target))
        img[off:off + 12] = new
    sg = syms['meter_sg_pre'] | 1
    off = file_offset(img, SG_PRE_SITE, 10)
    new = bytes(KS.asm(f'movw ip, #{sg & 0xFFFF}\nmovt ip, #{sg >> 16}\nblx ip\n', SG_PRE_SITE)[0])
    if listing(new, SG_PRE_SITE) != [f'movw ip, #{sg & 0xFFFF:#x}', f'movt ip, #{sg >> 16:#x}', 'blx ip'] or len(new) != 10:
        raise ValueError('bad SG pre encoding')
    patches.append(dict(address=SG_PRE_SITE, size=10, original_hex=bytes(img[off:off + 10]).hex(),
                        replacement_hex=new.hex(), target=sg & ~1, original_target=pre_target))
    img[off:off + 10] = new
    for site, name, original, what in (
            (bridges['rx_call'], 'diag_rx', bridges['bnc_rx'], "bounce's bridge call -> diag_rx"),
            (bridges['ui_call'], 'diag_ui', bridges['bnc_ui'], "bounce's bridge call -> diag_ui"),
            (bridges['feed_call'], 'sy_feed', FEED | 1, "bounce's rx bridge: the recorder feed's call -> sy_feed"),
            (DT1_ENTRY, 'sy_dt1', fde_dt1, "the DT1 builder's jump to FX deep edit's fde_dt1 -> sy_dt1")) + tuple(
            (addr, ours, value, f'SY test 5, {what} -> {ours}') for addr, value, ours, _, what in BAR_SITES):
        t = syms[name] | 1
        off = file_offset(img, site, 8)
        mm = movw_movt(bytes(img[off:off + 8]), site)
        if not mm or mm[1] != 'ip' or mm[0] != original:
            raise ValueError(f'{site:#x}: expected movw/movt ip of {original:#x} before {name}')
        new = bytes(KS.asm(f'movw ip, #{t & 0xFFFF}\nmovt ip, #{t >> 16}\n', site)[0])
        if listing(new, site) != [f'movw ip, #{t & 0xFFFF:#x}', f'movt ip, #{t >> 16:#x}'] or len(new) != 8:
            raise ValueError(f'bad {name} encoding')
        patches.append(dict(address=site, size=8, original_hex=bytes(img[off:off + 8]).hex(), replacement_hex=new.hex(),
                            target=t & ~1, original_target=original & ~1, what=what))
        img[off:off + 8] = new
    # SY test 5: note repeat's bridge calls sy_event in place of nr_event_c (one bl), which hands on to it
    t = syms['sy_event'] & ~1
    off = file_offset(img, nr_call, 4)
    old = listing(bytes(img[off:off + 4]), nr_call)
    new = bytes(KS.asm(f'bl #{t:#x}', nr_call)[0])
    if old != [f'bl #{nr_event_c & ~1:#x}'] or listing(new, nr_call) != [f'bl #{t:#x}'] or len(new) != 4:
        raise ValueError(f'{nr_call:#x}: expected bl nr_event_c ({old}), or a bad sy_event call')
    patches.append(dict(address=nr_call, size=4, original_hex=bytes(img[off:off + 4]).hex(), replacement_hex=new.hex(),
                        target=t, original_target=nr_event_c & ~1,
                        what="note repeat's nr_event bridge: bl -> sy_event (which calls nr_event_c)"))
    img[off:off + 4] = new
    # SY test 5: the SG page's widget pointers -> the screen's draws and update (each calls what it replaced)
    for addr, value, ours, _, what in SG_POINTERS:
        off = file_offset(img, addr, 4)
        if struct.unpack('<I', bytes(img[off:off + 4]))[0] != value:
            raise ValueError(f'{addr:#x}: expected {value:#x} ({what})')
        new = struct.pack('<I', syms[ours] | 1)
        patches.append(dict(address=addr, size=4, original_hex=bytes(img[off:off + 4]).hex(), replacement_hex=new.hex(),
                            target=syms[ours] & ~1, original_target=value & ~1, what=f'SY test 5, {what} -> {ours}'))
        img[off:off + 4] = new
    file_at = append(img, code, 16)
    sytext_at = append(img, sytext[1], 16)
    table = append(img, b'', 16)
    sy_lo, sy_hi = compile_module.sy_bss
    for row in rows + [[FLASH + file_at, base, len(code), COPY], [FLASH + sytext_at, sytext[0], len(sytext[1]), COPY],
                       [0, sy_lo, sy_hi - sy_lo, ZERO]]:
        img += struct.pack('<4I', *row)
    struct.pack_into('<2I', img, 0x80, table - 0x80, len(img) - 0x80)
    if FLASH + len(img) > FLASH_END:
        raise ValueError('image reaches the settings sector')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'SP404MKII_APP1.bin').write_bytes(img)
    shutil.copy2(app0, out / 'SP404MKII_APP0.bin')
    parent_manifest = inp.with_name('manifest.json')
    parent = json.loads(parent_manifest.read_text(encoding='utf-8')) if parent_manifest.exists() else {}
    manifest = dict(
        revision=REVISION, status='hardware-unverified', published=False, test_only=True,
        description='SY synth test 10: the footer drawn when the screen opens over the Sound Generator page '
                    '(plain or drum mode) already up; the chord on the looper page (0x27); REC on the screen to the '
                    'looper while looper mode is on (0x82e0b92c). '
                    'SY synth test 9: test 8 on combined-test19 (v9.52 with LEVEL for MIDI notes and the Sound '
                    'Generator and kits at about a sample\'s loudness). '
                    'SY synth test 8: the synth plays from the guitar synth screen on (sy.armed): off at power-on '
                    'and whenever EXT SOURCE goes on, on once the screen opens, on after EXIT on every page but the '
                    'plain Sound Generator\'s until EXT SOURCE goes off (or SOUND OFF); the ROUTING hold follows it. '
                    'SY synth test 7: the synth\'s bus, DRY / BUS 1 / BUS 2 / BOTH (half each), on TX line 3\'s stems '
                    '(words 0/1, 2/3, 4/5), stepped by VALUE\'s push on the screen, shown in the bar ("OUT: BUS 2"), '
                    'kept in the file (byte 98); on combined-test18 (v9.52 + LEVEL for MIDI notes: the guitar synth\'s '
                    'Sound Generator notes follow LEVEL too). '
                    'SY synth test 6 (test 5 on the unit): on the screen VALUE and the pads pick the sound, CTRL 1 is '
                    'the tone\'s own setting, CTRL 2 TONE (-50..+50), CTRL 3 LEVEL (0..100, 50 as designed), SHIFT '
                    'OCTAVE / SUSTAIN / DYNAMICS (new: a note\'s level L x (L / 0.1)^(d - 1)); the bar\'s PRM part '
                    'blank; with an FX screen up (found on the SG page\'s own object: 0x80cfd350 is 0 there) the knobs, '
                    'VALUE and SHIFT go to it, the pads too while MFX is held; REMAIN on the SG page (screen, plain, '
                    'kits): its press taken with its held bit set, so REMAIN + an FX button freezes the FX screen, a '
                    'tap alone handed to the stock key handlers (the preview bus), REMAIN with a frozen FX screen up '
                    'closes it (an EXIT). Engine: a band 20 dB under the loudest owned one silent, a band that stops '
                    'owning sounds on 4 blocks while it keeps 0.8 of its energy, FUND to the 16th harmonic and only '
                    'from a band at 0.01 of the multiple\'s energy or more, a note at its loudest partial\'s level; tones '
                    're-levelled on single notes to test 5\'s. File v3 (DYNAMICS; a v2 file read). Drum mode: every '
                    'guitar note strikes a pad (open low E pad 1, a pad a fret, higher notes an octave down at a time). '
                    'SY synth test 5: the guitar synth screen: EXT SOURCE held + RECORD SETTING (main screen or '
                    'SG page) opens the Sound Generator page in SY mode (the input on): the knob columns show SOUND '
                    '(OFF, 1-15) / TONE / LEVEL, SHIFT (tap: page; held) OCTAVE / the tone\'s own setting / SUSTAIN; '
                    'the bar PRM: SOUND; the footer the sound\'s name; CTRL 1-3 set them, VALUE steps SOUND, a pad '
                    'picks (16 OFF); its pads, knobs, VALUE, REC, SUB PAD never reach stock (sy_event at note repeat\'s '
                    'bridge, the UI dispatcher\'s entry); EXIT leaves, SHIFT + RECORD SETTING gives the page back to '
                    'the Sound Generator; drawn through the page\'s widgets (column and footer draws, page update, the '
                    'arp\'s bar bridges, each handing on outside the screen). Engine: FUND (a note from its lowest band '
                    'only: whole multiples 2..8 of a lower sounding band silent), SUSTAIN (a falling level held at 40 '
                    'ms x 2^(0.08 s) while the band sounds), OCTAVE (-2..+2); 15 new tones levelled 3 dB over test 4\'s '
                    'SAW LEAD on a strummed chord, the ceiling -3 dBFS (OUT_SCALE 23170). File v2 (B:/_sy_tones.bin, 88 '
                    'bytes, OCTAVE and SUSTAIN per tone). Test 4\'s picker gone (VALUE + EXT SOURCE is FX deep edit\'s '
                    'again). SY synth test 4: ROUTING Mix works: while a synth listens (EXT SOURCE on, the SY synth not off or the SG page) every '
                    'ROUTING DT1 goes to the chip as ExtIn (sy_dt1 at the builder entry, before FX deep edit\'s '
                    'fde_dt1), and the recorder feed (sampling, resampling, looper, skip-back) gets pair 1 x 2 on Mix '
                    '(the mix before BUS 3/4) or the input plus the synth on ExtIn (sy_feed, before the feed). '
                    'SY synth test 3: VALUE held + CTRL 1-3 set the picked tone\'s BRIGHT (-2..+2 octaves), its own '
                    'setting (sy_ref TONES p2) and LEVEL (0..2 x), through FX deep edit\'s knob bridge (its call '
                    're-pointed to sy_knob); picks and knobs kept in B:/_sy_tones.bin (read at the first key or knob '
                    'event, written when VALUE is let go after a change, no FX screen up). '
                    'SY synth test 2: 15 tones and OFF (sy_ref.py TONES: saw lead, square, pulse, supersaw, pad, '
                    'strings, organ, flute, FM bell, brass, bass, sweep, wah, a 16-step gate at the SP\'s tempo, '
                    'warm; each band\'s waves A/B, FM, attack and release, the filter mode, range, pick envelope and '
                    'LFO, noise, gain), picked with VALUE held + pad 1-16 where the synth can play (popup; the pad\'s '
                    'press and release taken), through FX deep edit\'s key bridges (their handler calls re-pointed); '
                    'a new tone fades out and in over 8 blocks; the engine on the tracker\'s stack. '
                    'SY synth test 1: a polyphonic synth in the way BOSS\'s SY pedals work (Roland\'s patent US '
                    '9,542,923): RX pair 0 at 12 kHz through 49 fourth-order band-passes a semitone apart (E2..E6); '
                    'each band\'s zero-crossing periods (an alpha-beta tracker) and energy; a band sounds when its '
                    'energy tops both neighbours\' and its pitch is within 80 cents of its centre, a saw at its pitch '
                    '(polyBLEP) at its level; the sum through a resonant low-pass whose cutoff follows the input '
                    'level (300 Hz .. 5 kHz), a soft clip, to the DRY pair of TX line 3 one block later; on every page '
                    'but the Sound Generator\'s with EXT SOURCE on and ROUTING ExtIn (the popup on Mix now on every '
                    'stock page); readout line 3 shows the engine (SY avg/peak %, bands sounding). '
                    'Guitar synth test 6 (on the Sound Generator page): after test 5 on the unit (a second note when a fretted note is let go '
                    'right after the pick; a chord held and picked string by string: notes missing): a move needs '
                    'the level over a period at 0.4 x a 0.3 s peak follower, a pick going steady 0.25 x the level '
                    'before it (else nothing plays and the note stops), the synth lets go when the newest 13 blocks '
                    'fall under 0.2 x the follower, a jump is a pluck only over 1.3 x it; a pick over strings '
                    'ringing is read from the difference function less the last one before it (negative lags 0, '
                    'only lags past the pick, first dip under 0.3), used when the plain reading is murky or a '
                    'common period 2..6 x lower; such a note holds through murky readings and does not move. '
                    'Test 5: test 4 played only on ROUTING ExtIn (system 0x5c = 1), since on Mix the '
                    'effects chip hands back the mix as heard and the synth held its own note; on Mix with EXT SOURCE '
                    'on, the Sound Generator page shows a popup saying so. Test 4: '
                    'on the Sound Generator page with EXT SOURCE on, the input the effects chip '
                    'hands back (RX pair 0, after the input FX) goes through note tracker test 2 (YIN at 6 kHz refined '
                    'at 12 kHz, an analysis every 4 RX blocks), and the UI tick plays its note on the Sound Generator '
                    "through the entry MIDI IN takes (the kits' note gates' SG route), one note at a time: on when a "
                    'pluck goes steady, moved when the steady note moves (not in drum mode), off when the string '
                    'stops. Test 4: a pluck is a block peak twice the highest of the 21 ms before, or a click (the '
                    'energy over 2 kHz twice the most of the 20 ms before); only analyses with an aperiodicity under '
                    '0.15 count (strings ringing together read murky and count as nothing heard); a pluck going steady '
                    'on the note playing restarts it only if the level kept 0.5 x its reference (clicked) or rose 1.2 '
                    'x (not), another note always plays; velocity 50 + 77 x sqrt(pick peak / 0.4); the note + 12 x '
                    "the SG's OCT (drum mode: the guitar's note). The CPU meter's readout (hold EXIT on the main "
                    'screen) shows the tracker as in note tracker test 2.',
        sg_midi_entry=sg_midi, kit_mode_flag=kit_mode,
        parent_app1=str(inp), parent_sha256=sha(inp.read_bytes()), parent_folder=inp.parent.name,
        parent_revision=parent.get('revision'), parent_parent_revision=parent.get('parent_revision'),
        sha256=sha(img), size=len(img), app0_sha256=APP0_SHA,
        module_base=base, module_file_offset=file_at, module_size=len(code), module_sha256=sha(code),
        module_limit=LIMIT, symbols={k: syms[k] for k in EXPORTS}, functions={n: [a, s] for n, a, s in funcs},
        integer_spans=[[lo, hi, name] for lo, hi, name in integer], fpu_instructions=fpu_count,
        tt_block_bytes=block_bytes, sy_block_bytes=sy_block_bytes, bounce_bridges={k: v for k, v in bridges.items()},
        source_sha256={str(p.relative_to(HERE)): sha(lf(p)) for p in SOURCES + HEADERS},
        test_plan_sha256=sha(lf(TEST_PLAN)), tool_sha256=sha(lf(Path(__file__))),
        compiler='zig 0.13.0 cc -target thumb-freestanding-eabihf -mcpu=cortex_m7+fp_armv8d16sp -O2',
        rows_added=[dict(kind='copy', address=base, size=len(code)),
                    dict(kind='copy', address=sytext[0], size=len(sytext[1]), file_offset=sytext_at,
                         what='the guitar synth screen\'s code (SY test 5: .sytext, out of the module)'),
                    dict(kind='zero', address=sy_lo, size=sy_hi - sy_lo, what='sy_block (SY test 3: out of the module)')],
        sy_bss=dict(slot=[SY_BSS[0], SY_BSS[1]], used=[sy_lo, sy_hi]),
        sytext=dict(slot=[SY_TEXT[0], SY_TEXT[1]], address=sytext[0], size=len(sytext[1]), file_offset=sytext_at,
                    sha256=sha(sytext[1])),
        dt1_hook=dt1_info, nr_hook=nr_info, screen=guards['screen'],
        routing=dict(hold='while EXT SOURCE is on and the SY synth is not off (or on the Sound Generator page): '
                          'ROUTING (system 0x5c) goes to the chip as ExtIn, the user\'s value kept and sent back after',
                     recorder='the feed\'s pair 0 (when it takes pair 0): ROUTING Mix -> pair 1 x 2 (the mix before '
                              'BUS 3/4), for 30 ms after the hold too; ExtIn -> the input + the synth\'s block'),
        patches=patches, guards={hex(k) if isinstance(k, int) else k: v for k, v in guards.items()},
        tune=dict(memory='tt_block in the module (tt_block_bytes): the 12 kHz ring, an analysis\' span, the '
                         'difference functions, a 2 KB stack',
                  steps='every RX block: pair 0 (L + R) / 2 -> 4th-order low-pass 1.6 kHz -> every 4th sample to '
                        'the 12 kHz ring; the pluck test; 25 of an analysis\' 100 lags; every 4th block the note',
                  slow='a step over the whole block, or mixer + tracker over 9/10 of it in two wakes in a row, stops '
                       'it (SLOW); the 75-block window is published then',
                  fpu='tune_fp_call: the module\'s own 2 KB stack, FPSCR and d0-d15 saved, FPSCR = nearest, FZ, DN'),
        sy=dict(memory='sy_block in the module (sy_block_bytes): the bands\' filters, energies, periods and '
                       'oscillators (test 2: no stack: the tracker\'s); the tables and tones (sy_tables.h, from '
                       'tunetest/sy_ref.py) in .rodata',
                tones=[t['name'] for t in sy_ref.TONES],
                pick='test 4: VALUE held + EXT SOURCE opens the picker; pads 1-15 a tone, pad 16 off; popup, '
                     'pads lit (white playing, blue the others, red 16)',
                knobs='test 4: CTRL 1-3 in the picker: BRIGHT, ' +
                      '/'.join(sorted({t['p2'][0] for t in sy_ref.TONES})) + ', LEVEL of the picked tone; popup',
                file='B:/_sy_tones.bin, 60 bytes: "SYTN", version 1, tone, muted, 15, 45 knob positions, 3 zero, '
                     'FNV-1a of the first 56',
                steps='every RX block, after the tracker: pair 0 (L + R) / 2 -> 4th-order low-pass 2 kHz -> 12 kHz '
                      '-> 49 bands x 16 samples; the sounding bands\' saws x 64 samples; the output filter; 64 '
                      'values for TX\'s DRY pair',
                slow='a step over the whole block, or mixer + tracker + engine over 9/10 of it in two wakes in a '
                     'row, stops it (SLOW)',
                fpu='sy_fp_call: the tracker\'s 2 KB stack (tt_block), FPSCR and d0-d15 saved, FPSCR = nearest, FZ, '
                    'DN; no contraction (fmaf only where written), as tunetest/sy_ref.py computes it'),
        readout='main screen: hold EXIT alone for 1 s to show or hide; stock popup 0x800d3ff0, every 0.1 s while '
                'the tracker runs',
        tool='synth/build_tune_test.py')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    plan = lf(TEST_PLAN).decode('utf-8')
    for key, value in (('PARENT_REVISION', inp.parent.name),
                       ('APP1_SIZE', f'{len(img):,}'), ('APP1_SHA256', manifest['sha256']), ('APP0_SHA256', APP0_SHA)):
        plan = plan.replace('{{' + key + '}}', value)
    if '{{' in plan:
        raise ValueError('unfilled placeholder in HARDWARE_TEST.md')
    (out / 'HARDWARE_TEST.md').write_text(plan, encoding='utf-8', newline='\n')
    names = ('SP404MKII_APP0.bin', 'SP404MKII_APP1.bin', 'manifest.json', 'HARDWARE_TEST.md')
    sums = ''.join(f'{sha((out / n).read_bytes())}  {n}\n' for n in names)
    (out / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('app1', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--zig', type=Path, required=True)
    ap.add_argument('--base', type=lambda s: int(s, 0), default=BASE)
    ap.add_argument('--build-dir', type=Path, help='compiler intermediates (default OUT_DIR/build)')
    a = ap.parse_args()
    m = build(a.app1.resolve(), a.out.resolve(), a.zig.resolve(), a.base, a.build_dir)
    print(json.dumps({k: m[k] for k in ('revision', 'sha256', 'size', 'module_base', 'module_size', 'tt_block_bytes',
                                        'sy_block_bytes', 'fpu_instructions')}, indent=1))


if __name__ == '__main__':
    main()
