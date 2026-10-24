"""IR diagnostic test 1: the CPU meter (T0) and a test echo of the input, on v9.49 (test only).

What an amp IR or NAM stage on the main processor would face, measured on the unit before any is written:
the meter times the mixer, the pad voices and the SG/kit render every 64-frame block (as T0,
synth/CPU_METER.md); the echo sends the captured input (the RX pair ROUTING picks) back on the DRY pair
about 149 ms later at -12 dB, only while the input FX is the Gt Amp Sim. See synth/IR_DIAG.md.

The input is v9.49 (combined-test9): bounce in place holds the audio task's TX and RX sites and the popup
tick, so the meter's UI step and the echo's ring go behind bounce's bridges instead of T0's own jumps:
  0x0001c2d0  mixer entry (12 bytes)             -> meter_mix_entry (its exit also adds the echo)
  0x80005870  per-voice stub (12 bytes)          -> meter_voice
  0x0001fd84  the fork's SG stub, pre call's movw/movt (8 of 10 bytes) -> meter_sg_pre
  bounce's ui bridge, its bnc_ui call's movw/movt (8 bytes) -> diag_ui (bnc_ui, then the meter and the echo)
  bounce's rx bridge, its bnc_rx call's movw/movt (8 bytes) -> diag_rx (bnc_rx, then the echo's ring)
The module (irdiag/ir_diag.c) goes in a new boot copy row at BASE, below the RESAMPLE start fix
(0x83FEF000); the echo's ring is a zero row at ECHO_RING (the FX probe's unused slot and the top of FX deep
edit's).

usage: python synth/build_ir_diag.py IN_APP1 OUT_DIR --zig ZIG [--base 0x83FED000] [--build-dir DIR]
Needs Zig 0.13.0, capstone and keystone. Refuses to overwrite an existing output.
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

import capstone
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB, KS_MODE_LITTLE_ENDIAN

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'irdiag' / 'ir_diag.c'
TEST_PLAN = HERE / 'irdiag' / 'HARDWARE_TEST.md'
FLASH, COPY, ZERO = 0x60080000, 0x600800E4, 0x60080100
FLASH_END = 0x603FF000              # settings sector: the image must end below it
APP0_SHA = '3e35ff30137f741a715566e205384f9b434ca7ac3847e247bad3f0c9c8a2bd23'
REVISION = 'ir-diag-test2'
BASE = 0x83FED000
LIMIT = 0x83FEF000                  # the RESAMPLE start fix's row starts here
GAP_END = 0x83FF0000                # cacheable SDRAM ends here
ECHO_RING, ECHO_FRAMES = 0x83FE4000, 7168     # 112 blocks: 149 ms at 48 kHz, mono 16-bit
ECHO_BYTES = 2 * ECHO_FRAMES
BOUNCE_SLOT = (0x83FE8000, 0x83FED000)
TX_BRIDGE, RX_BRIDGE, UI_BRIDGE = 0x83FE8000, 0x83FE8030, 0x83FE8080   # bounce-3-test9's bridges
TX_SITE, RX_SITE, FEED, LOOP, TX_BACK, TICK_REST = 0x0001D090, 0x0001D0C2, 0x0001CA80, 0x0001D05C, 0x0001D09A, 0x8006B95C

MIXER, ITCM_VENEER = 0x0001C2D0, 0x0001008E
STUB, RENDER_VENEER = 0x80005870, 0x800D2D5C
SG_CALL, SG_STUB, SG_PRE_SITE, SG_EXIT_SITE = 0x0001C766, 0x0001FD80, 0x0001FD84, 0x0001FDD4
UI_TICK, UI_CALLER = 0x8006B950, 0x8006F6FA
POPUP_POST, POPUP_CLOSE, KEY_QUERY, PAGE_QUERY = 0x800D3FF0, 0x8001F730, 0x800D9F20, 0x800D6380

EXPORTS = ('meter_mix_entry', 'meter_mix_exit', 'meter_voice', 'meter_sg_pre', 'meter_sg_end',
           'meter_mix_begin', 'meter_mix_end', 'meter_ui_tick', 'meter_format', 'diag_ui', 'diag_rx',
           'echo_tx', 'echo_rx', 'echo_ui', 'meter', 'echo')
DATA = ('meter', 'echo')

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
]

MD = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
KS = Ks(KS_ARCH_ARM, KS_MODE_THUMB | KS_MODE_LITTLE_ENDIAN)


def sha(b):
    return hashlib.sha256(b).hexdigest()


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
                    i1, i2 = ~(j1 ^ s) & 1, ~(j2 ^ s) & 1
                    imm = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
                    if s:
                        imm -= 1 << 25
                    target = pc + imm
                elif (h2 & 0xD000) == 0x8000 and ((h1 >> 6) & 0xF) < 0xE:  # B<cc>.W
                    s = (h1 >> 10) & 1
                    imm = (s << 20) | (((h2 >> 11) & 1) << 19) | (((h2 >> 13) & 1) << 18) | ((h1 & 0x3F) << 12) | ((h2 & 0x7FF) << 1)
                    if s:
                        imm -= 1 << 21
                    target = pc + imm
            elif (h1 & 0xF800) == 0xE000:                                  # B (16-bit)
                imm = (h1 & 0x7FF) << 1
                if imm & 0x800:
                    imm -= 0x1000
                target = pc + imm
            elif (h1 & 0xF000) == 0xD000 and (h1 & 0x0F00) < 0x0E00:       # B<cc> (16-bit)
                imm = (h1 & 0xFF) << 1
                if imm & 0x100:
                    imm -= 0x200
                target = pc + imm
            elif (h1 & 0xF500) == 0xB100:                                  # CBZ/CBNZ
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
    rx_call, bnc_rx = c[3][0], c[3][1]
    ui = read(img, UI_BRIDGE, 0x30)
    t = listing(ui, UI_BRIDGE)
    c = ip_calls(ui, UI_BRIDGE)
    if t[:2] != ['push {r4, r5, r6, lr}', 'push {r0, r1}'] or len(c) < 2 or c[0][0] != UI_BRIDGE + 4 or \
            not in_slot(c[0][1]) or c[0][2] != 'blx ip' or t[5:9] != ['pop {r0, r1}', 'movw r4, #0x22ac', 'movt r4, #0x8059',
                                                                    'ldr r1, [r4, #8]'] or c[1][1:] != (TICK_REST | 1, 'bx ip'):
        raise ValueError(f'bounce ui bridge {UI_BRIDGE:#x}: unexpected {t[:12]}')
    return dict(rx_call=rx_call, bnc_rx=bnc_rx, ui_call=c[0][0], bnc_ui=c[0][1])


def check_guards(img):
    found = {}
    for addr, size, expect, why in GUARDS:
        got = listing(read(img, addr, size), addr)
        if got != expect:
            raise ValueError(f'{addr:#x} ({why}): expected {expect}, found {got}')
        found[addr] = dict(size=size, instructions=expect, why=why, hex=read(img, addr, size).hex())
    # The SG stub: its pre call (movw/movt ip, blx ip) and its exit (movw/movt ip, bx ip) to a
    # continuation that ends in pop {r4-r8, pc}; nothing between touches sp or returns.
    pre = movw_movt(read(img, SG_PRE_SITE, 8), SG_PRE_SITE)
    if not pre or pre[1] != 'ip' or listing(read(img, SG_PRE_SITE + 8, 2), SG_PRE_SITE + 8) != ['blx ip']:
        raise ValueError(f'{SG_PRE_SITE:#x}: expected movw ip / movt ip / blx ip')
    pre_target = pre[0]
    if not (pre_target & 1 and 0x83F80000 <= pre_target < BASE):
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
    return found, pre_target, bridges


def read_module(data, base, limit):
    """Allocated ELF sections (BSS as zeros), every global symbol, and the .text span."""
    if data[:7] != b'\x7fELF\x01\x01\x01' or struct.unpack_from('<H', data, 18)[0] != 40:
        raise ValueError('expected little-endian ARM ELF32')
    shoff = struct.unpack_from('<I', data, 32)[0]
    shsize, count, shstrndx = struct.unpack_from('<3H', data, 46)
    sections = [struct.unpack_from('<10I', data, shoff + i * shsize) for i in range(count)]
    names = data[sections[shstrndx][4]:sections[shstrndx][4] + sections[shstrndx][5]]
    syms, blocks, end, text = {}, [], base, None
    for name, kind, flags, addr, off, size, link, info, align, entsize in sections:
        if flags & 2 and size:
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
                n, value, _, sym_info = struct.unpack_from('<3IB', data, at)
                label = strtab[n:].split(b'\0')[0].decode('ascii')
                if sym_info >> 4 == 1 and label:
                    syms[label] = value
                if label in ('$t', '$d', '$a') or label.startswith(('$t.', '$d.', '$a.')):
                    maps.append((value, label[1]))      # ARM ELF mapping symbols: code or data
    if text is None or text[0] != base:
        raise ValueError('expected .text first, at the base')
    out = bytearray(end - base)
    for addr, block in blocks:
        out[addr - base:addr - base + len(block)] = block
    return bytes(out), syms, (text[0], text[1], sorted(set(maps)))


def compile_module(zig, folder, base, pre_target, bridges):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'ir_diag_links.h').write_text(
        f'#define SG_PRE_TARGET {pre_target:#010x}\n#define BNC_UI {bridges["bnc_ui"]:#010x}u\n'
        f'#define BNC_RX {bridges["bnc_rx"]:#010x}u\n#define ECHO_RING {ECHO_RING:#010x}u\n'
        f'#define ECHO_FRAMES {ECHO_FRAMES}u\n', encoding='ascii', newline='\n')
    keep = ' '.join(f'KEEP(*(.text.{name}))' for name in EXPORTS if name not in DATA)
    (folder / 'ir_diag.ld').write_text(f'''ENTRY(meter_mix_entry)
SECTIONS {{
 . = {base:#x};
 .text : {{ {keep} *(.text*) }}
 .rodata : ALIGN(4) {{ *(.rodata*) }}
 .data : ALIGN(4) {{ *(.data*) }}
 .bss : ALIGN(4) {{ *(.bss*) *(COMMON) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) *(.ARM.attributes) }}
}}
''', encoding='ascii', newline='\n')
    cache = folder / 'cache'
    env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(cache), ZIG_LOCAL_CACHE_DIR=str(cache))
    if subprocess.check_output([str(zig), 'version'], text=True).strip() != '0.13.0':
        raise ValueError('needs Zig 0.13.0')
    src = folder / 'ir_diag.c'
    src.write_bytes(SOURCE.read_bytes().replace(b'\r\n', b'\n'))
    # Integer-only module: soft-float ABI, so no FPU instruction can appear in the audio-task hooks.
    subprocess.run([str(zig), 'cc', '-target', 'thumb-freestanding-eabi', '-mcpu=cortex_m7', '-mfloat-abi=soft',
                    '-O2', '-ffreestanding', '-fno-stack-protector', '-ffunction-sections', '-fdata-sections',
                    '-nostdlib', '-Wall', '-Werror', '-Wl,--no-undefined', '-Wl,--build-id=none',
                    '-Wl,-e,meter_mix_entry', '-Wl,-T,' + str(folder / 'ir_diag.ld'),
                    '-I', str(folder), str(src), '-o', str(folder / 'ir_diag.elf')], check=True, env=env)
    code, syms, text = read_module((folder / 'ir_diag.elf').read_bytes(), base, LIMIT)
    missing = [n for n in EXPORTS if n not in syms]
    if missing:
        raise ValueError(f'module symbols missing: {missing}')
    return code, syms, text


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


def check_module(code, text, base):
    """Integer code only, every code span decoded to its end; direct branches stay inside .text."""
    for lo, hi in code_spans(text):
        seen = lo
        for ins in MD.disasm(code[lo - base:hi - base], lo):
            seen = ins.address + ins.size
            m = ins.mnemonic
            if m.startswith('v'):
                raise ValueError(f'FPU instruction in the module at {ins.address:#x}: {m} {ins.op_str}')
            if m.startswith(('b', 'cb')) and m not in ('bx', 'blx', 'bkpt', 'bic', 'bics', 'bfc', 'bfi') and '#' in ins.op_str:
                target = int(ins.op_str.split('#')[-1], 16)
                if not text[0] <= target < text[1]:
                    raise ValueError(f'module branch at {ins.address:#x} to {target:#x}')
        if seen < hi and any(code[seen - base:hi - base]):
            raise ValueError(f'code span {lo:#x}..{hi:#x} does not decode past {seen:#x}')


def build(inp: Path, out: Path, zig: Path, base: int, build_dir: Path = None):
    img = bytearray(inp.read_bytes())
    app0 = inp.with_name('SP404MKII_APP0.bin')
    if sha(app0.read_bytes()) != APP0_SHA:
        raise ValueError('expected stock APP0 beside the input APP1')
    for name in ('SP404MKII_APP1.bin', 'SP404MKII_APP0.bin', 'manifest.json'):
        if (out / name).exists():
            raise ValueError(f'refusing to overwrite {out / name}')
    guards, pre_target, bridges = check_guards(img)
    code, syms, text = compile_module(zig, (build_dir or out / 'build').resolve(), base, pre_target, bridges)
    end = base + len(code)
    if end > LIMIT or end > GAP_END:
        raise ValueError(f'module {base:#x}+{len(code):#x} passes {LIMIT:#x}')
    rows = scatter(img)
    for lo, hi, what in ((base, end, 'the module area'), (ECHO_RING, ECHO_RING + ECHO_BYTES, "the echo's ring")):
        for load, dst, n, fn in rows:
            if max(dst, lo) < min(dst + n, hi):
                raise ValueError(f'row {dst:#x}+{n:#x} overlaps {what}')
        hits = refs_into(bytes(img), lo & ~0xFFF, (hi + 0xFFF) & ~0xFFF)
        if hits:
            raise ValueError(f'input refers to {what}: {hits[:4]}')
    if not (BOUNCE_SLOT[1] <= base and ECHO_RING + ECHO_BYTES <= BOUNCE_SLOT[0]):
        raise ValueError('module or ring inside bounce\'s slot')
    check_module(code, text, base)
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
    for site, name, original in ((bridges['rx_call'], 'diag_rx', bridges['bnc_rx']),
                                 (bridges['ui_call'], 'diag_ui', bridges['bnc_ui'])):
        t = syms[name] | 1
        off = file_offset(img, site, 8)
        new = bytes(KS.asm(f'movw ip, #{t & 0xFFFF}\nmovt ip, #{t >> 16}\n', site)[0])
        if listing(new, site) != [f'movw ip, #{t & 0xFFFF:#x}', f'movt ip, #{t >> 16:#x}'] or len(new) != 8:
            raise ValueError(f'bad {name} encoding')
        patches.append(dict(address=site, size=8, original_hex=bytes(img[off:off + 8]).hex(), replacement_hex=new.hex(),
                            target=t & ~1, original_target=original & ~1, what=f"bounce's bridge call -> {name}"))
        img[off:off + 8] = new
    file_at = (len(img) + 15) & ~15
    img += bytes(file_at - len(img)) + code
    table = (len(img) + 15) & ~15
    img += bytes(table - len(img))
    for row in rows + [[FLASH + file_at, base, len(code), COPY], [0, ECHO_RING, ECHO_BYTES, ZERO]]:
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
        description='IR diagnostic test 1: the CPU meter (T0: the mixer, the pad voice loop and the SG/kit render '
                    'timed with the DWT cycle counter, shown in the stock popup) and a test echo: the captured input '
                    '(the RX pair ROUTING picks) back on the DRY pair 149 ms later at -12 dB while the input FX is '
                    'the Gt Amp Sim',
        parent_app1=str(inp), parent_sha256=sha(inp.read_bytes()), parent_folder=inp.parent.name,
        parent_revision=parent.get('revision'), parent_parent_revision=parent.get('parent_revision'),
        sha256=sha(img), size=len(img), app0_sha256=APP0_SHA,
        module_base=base, module_file_offset=file_at, module_size=len(code), module_sha256=sha(code),
        module_limit=LIMIT, symbols={k: syms[k] for k in EXPORTS},
        echo=dict(ring=ECHO_RING, ring_bytes=ECHO_BYTES, frames=ECHO_FRAMES, delay_ms=round(ECHO_FRAMES / 48, 1),
                  gain='1/4 (-12 dB), mono (L+R)/2 onto DRY L and R, clipped to 20 bits as the packer clips',
                  source='the recorder feed\'s copy 0x202ad0a0 (the RX pair INPUT SETTING\'s ROUTING picks), after '
                         'every RX block', target='TX line 3 words 0/1 (DRY) of the block the mixer has just packed',
                  gate='system 0x27c[0] (the input FX) = 23, Gt Amp Sim, read from the UI task every 0.1 s'),
        bounce_bridges={k: v for k, v in bridges.items()},
        source_sha256=sha(SOURCE.read_bytes().replace(b'\r\n', b'\n')),
        test_plan_sha256=sha(TEST_PLAN.read_bytes().replace(b'\r\n', b'\n')),
        tool_sha256=sha(Path(__file__).read_bytes().replace(b'\r\n', b'\n')),
        compiler='zig 0.13.0 cc -target thumb-freestanding-eabi -mcpu=cortex_m7 -mfloat-abi=soft -O2',
        rows_added=[dict(kind='copy', address=base, size=len(code)), dict(kind='zero', address=ECHO_RING, size=ECHO_BYTES)],
        patches=patches, guards={hex(k) if isinstance(k, int) else k: v for k, v in guards.items()},
        measures=dict(block_cycles_nominal=800000, window_blocks=375,
                      mix='mixer 0x1c2d0, entry to return (every block)',
                      pad='voice loop: slot 0 per-voice call to the end of slot 31',
                      sg='the fork SG render stub behind 0x1c766 (arp tick, SG voices, kits)',
                      hi='blocks whose mixer took > 75% of a block, since the readout was switched on',
                      ovr='blocks whose mixer took > 100% of a block, since the readout was switched on',
                      clk='core clock implied by the measured block length (64 frames at 48 kHz)'),
        readout='main screen: hold EXIT alone for 1 s to show or hide; stock popup 0x800d3ff0, refreshed every 0.5 s',
        tool='synth/build_ir_diag.py')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    plan = TEST_PLAN.read_text(encoding='utf-8').replace('\r\n', '\n')
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
    print(json.dumps({k: m[k] for k in ('revision', 'sha256', 'size', 'module_base', 'module_size')}, indent=1))


if __name__ == '__main__':
    main()
