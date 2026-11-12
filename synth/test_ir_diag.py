"""Checks for IR diagnostic test 1 (build_ir_diag.py): T0's CPU meter checks on the v9.49 parent, and the echo.

usage: python synth/test_ir_diag.py OUT_DIR --kits KITS_MANIFEST [--seeds N] [--blocks N] [--mixer-runs N]

OUT_DIR is the builder's output (manifest.json names the parent APP1); KITS_MANIFEST is the kit stage's
kits-manifest.json (arp_symbols), the kit stage v9.49 carries unchanged (kits-v9.46-test3).
Both images are booted into Unicorn the way their scatter loaders do it, with the
same stubs, and run side by side. Writes OUT_DIR/test_report.json.

1. Static: only the header, the five patch spans and the appended tail differ from
   the parent; the scatter table is the parent's rows plus the module row and the
   echo's zero row.
2. Hook entries: from the mixer entry and from the popup tick entry (through bounce's
   ui bridge, which now calls diag_ui) to the first stock instruction after the
   displaced ones, registers and the stack frame match the parent (the mixer frame's
   saved return is the meter's exit, by design).
3. Voice chain: every slot's per-voice call (ITCM veneer 0x1008e) over randomised
   voices (render paths, release, declick, cue, mono/stereo, chunk ends, empty
   slots) leaves every byte of memory, bus/bus2 and the callee-saved registers as
   the parent does. A negative control (one stem word nudged on the meter side
   before each render) must be caught.
4. Whole mixer: blocks of 0x1c2d0 with randomised voices and four TR-606 cymbals on
   the kit page: the TX buffers and every byte of memory match the parent, block
   for block. (Memory = all of ITCM, DTCM, OCRAM, SDRAM and the test area, except
   the image itself, the patched spans, the meter's module area and the scratch
   stack below the caller.) Then, with the cycle counter driven by the instruction
   count, the meter's PAD, SG and MIX spans must equal stamps at the stock
   boundaries less its own few instructions, and its cost per block is measured
   against the parent.
5. Meter arithmetic with a controlled cycle counter: windows, averages, peaks,
   voices, HI/OVR thresholds, the measured budget, reset on switch-on, the counter
   start-up fallback.
6. Readout: every line of the worst case fits the stock popup (PBold widths from
   the image's font table), five lines fit the screen.
7. UI: hold EXIT 1 s on the main screen toggles; SHIFT, another page or another key
   cancels; a stock popup is left alone; switching off closes only our popup.
8. Echo: the ring takes each RX block as mono; each TX block gets the block written
   112 RX blocks before, at 1/4, on the DRY words only, clipped to 20 bits; through the
   whole mixer it is the parent's TX plus exactly that; off, nothing changes; the gate
   follows the input FX (Gt Amp Sim on, anything else off, read every 0.1 s); diag_rx and
   diag_ui still run bounce's own bnc_rx and bnc_ui.

Stock functions outside the audio path are stubbed identically in both machines and
their calls are logged and compared. Not a hardware test: no timing, no screen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_PROT_ALL, UC_HOOK_CODE
from unicorn import arm_const as ar

FLASH, COPY, DECOMPRESS, ZERO = 0x60080000, 0x600800E4, 0x60080088, 0x60080100
TEST = 0x90000000                       # test-only RAM: stacks, voices, streams, TX buffers
STACK, RET = TEST + 0x40000, TEST + 0x41000
SCRATCH, TXBUF, ARGS = TEST + 0x42000, TEST + 0x50000, TEST + 0x5F000
VOICES, VOICE_SIZE = TEST + 0x100000, 0x29000
STREAMS, STREAM_SIZE = TEST + 0x700000, 0x8400
MALLOC = TEST + 0xF00000
SLOT0, SLOT_SIZE = 0x202AE1A0, 0x58
STEMS = 0x202AD3A0
MIXER, VENEER, UI_TICK = 0x0001C2D0, 0x0001008E, 0x8006B950
POPUP_POST, POPUP_CLOSE = 0x800D3FF0, 0x8001F730
POPUP_TEXT, POPUP_PENDING, POPUP_SHOWN, PAGE, KEYS = 0x802468D8, 0x802458A0, 0x805922B0, 0x80245880, 0x80592448
KEY_EXIT, KEY_SHIFT, KEY_ROLL = 0x22, 0x2A, 0x21
BUS_ADDS = (0x15FEE, 0x16100, 0x1620C, 0x16298, 0x16308, 0x16384, 0x16400)
CONSUMER, RENDERER = 0x168FE, 0x14B88
FONT_TABLE, POPUP_FONT = 0x80249A68, 15
# Stock functions the audio path reaches outside ITCM, stubbed alike in both machines (address -> r0).
STUBS = {
    0x800DED08: 0, 0x800DECF8: 0, 0x800D31EE: 0,          # dispatch off/on, task delay
    0x800D314E: 0x1234567,                                 # random(): fixed
    0x800DDA38: 0, 0x80047DD0: 12000, 0x800D5640: 12000,   # project parameter, pad tempo, tempo
    0x8004C1E0: 0, 0x8005A358: 0, 0x80058570: 0,           # MIDI CC queue signal, control functions
    0x800A1078: 0, 0x8001C2C8: 0, 0x8001B2C0: 0, 0x8001B218: 0, 0x8001B360: 0, 0x8001B3A8: 0,
    0x80020440: 0, 0x800D93A0: 0, 0x800C3E58: 0, 0x0000E668: 0, 0x800E2CA8: 0,
    0x800D8B14: MALLOC,                                    # malloc: one fixed buffer
}
CHROMATIC, PAD_PATHS = 0x8005A6B4, {0x80066E78: 0x80066D0C, 0x800670CC: 0x80067054}
SETTINGS, SETTINGS_VTABLE, CC_QUEUE, KB = 0x82E01144, 0x8021CD10, 0x80D3D96C, 0x80591C48
SG_PAGE, SG_VOICES, STOCK_RESET, DISPATCH = 0x1E, (0x80249800, 0x8353A310, 0x8353A4C0, 0x8353A670), 0x80132340, 0x80066278

fails = []
report = {}


def check(cond, what):
    print(('PASS ' if cond else 'FAIL ') + what)
    if not cond:
        fails.append(what)
    return cond


def sha(b):
    return hashlib.sha256(b).hexdigest()


def scatter(img):
    a, b = struct.unpack_from('<2I', img, 0x80)
    return [list(struct.unpack_from('<4I', img, i)) for i in range(a + 0x80, b + 0x80, 16)]


def decompress(src, size):
    """armlink's LZ77 variant for RW data (as in test_kit_midi.py)."""
    out, i = bytearray(), 0
    while len(out) < size:
        token = src[i]; i += 1
        literal = token & 7
        if literal == 0:
            literal = src[i]; i += 1
        count = token >> 4
        if count == 0:
            count = src[i]; i += 1
        out += src[i:i + literal - 1]; i += max(literal - 1, 0)
        if token & 8:
            start = len(out) - src[i]; i += 1
            for k in range(count + 2):
                out.append(out[start + k])
        else:
            out += bytes(count)
    return bytes(out[:size])


REGIONS = ((0x0, 0x20000), (0x20000000, 0x80000), (0x20200000, 0x100000), (0x80000000, 0x4000000),
           (TEST, 0x1000000), (0x60000000, 0x400000), (0xE0000000, 0x1000), (0xE0002000, 0xFE000))


class Machine:
    def __init__(self, image: bytes, symbols=None):
        self.S = symbols or {}
        uc = self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for base, size in REGIONS:
            uc.mem_map(base, size, UC_PROT_ALL)
        self.cyc, self.cyc_step, self.dwt_ctrl, self.dwt_writes = 0, 0, 1, []
        uc.mmio_map(0xE0001000, 0x1000, self._dwt_read, None, self._dwt_write, None)
        uc.mem_write(FLASH, image)
        for load, dst, size, handler in scatter(image):
            if handler == COPY:
                uc.mem_write(dst, image[load - FLASH:load - FLASH + size])
            elif handler == DECOMPRESS:
                uc.mem_write(dst, decompress(image[load - FLASH:], size))
            elif handler == ZERO:
                uc.mem_write(dst, bytes(size))
            else:
                raise ValueError(f'unknown scatter handler {handler:#x}')
        uc.reg_write(ar.UC_ARM_REG_C1_C0_2, uc.reg_read(ar.UC_ARM_REG_C1_C0_2) | (0xF << 20))
        uc.reg_write(ar.UC_ARM_REG_FPEXC, 0x40000000)
        uc.mem_write(RET, b'\x00\xbf\x00\xbf')
        self.log = []
        for address, value in STUBS.items():
            self.stub(address, value)
        uc.hook_add(UC_HOOK_CODE, self._chromatic, begin=CHROMATIC, end=CHROMATIC)
        for site, epilogue in PAD_PATHS.items():
            uc.hook_add(UC_HOOK_CODE, self._pad_path, epilogue, begin=site, end=site)
        self.put(SETTINGS, SETTINGS_VTABLE, '<I')
        self.put(CC_QUEUE + 4, CC_QUEUE + 0xC, '<I')
        self.put(CC_QUEUE + 8, CC_QUEUE + 0xC, '<I')
        self.counts = {}

    # -- plumbing --
    def _dwt_read(self, uc, offset, size, data):
        if offset == 4:
            v = self.cyc & 0xFFFFFFFF
            self.cyc += self.cyc_step
            return v
        if offset == 0:
            return self.dwt_ctrl
        return 0

    def _dwt_write(self, uc, offset, size, value, data):
        self.dwt_writes.append((offset, value))
        if offset == 0:
            self.dwt_ctrl = value

    def stub(self, address, value):
        def hook(uc, a, size, _):
            self.log.append((a, uc.reg_read(ar.UC_ARM_REG_R0), uc.reg_read(ar.UC_ARM_REG_R1),
                             uc.reg_read(ar.UC_ARM_REG_R2), uc.reg_read(ar.UC_ARM_REG_R3)))
            uc.reg_write(ar.UC_ARM_REG_R0, value)
            uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))
        self.uc.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)

    def count(self, addresses):
        for a in addresses:
            self.counts[a] = 0
            self.uc.hook_add(UC_HOOK_CODE, lambda uc, x, s, _, a=a: self.counts.__setitem__(a, self.counts[a] + 1),
                             begin=a, end=a)

    def _chromatic(self, uc, address, size, _):
        self.log.append(('chromatic',))
        uc.reg_write(ar.UC_ARM_REG_PC, 0x8005A6AF)

    def _pad_path(self, uc, address, size, epilogue):
        self.log.append(('pad',))
        uc.reg_write(ar.UC_ARM_REG_PC, epilogue | 1)

    def call(self, fn, *args, sp=STACK, limit=20_000_000):
        uc = self.uc
        uc.reg_write(ar.UC_ARM_REG_SP, sp)
        for k, value in enumerate(args):
            uc.reg_write(getattr(ar, f'UC_ARM_REG_R{k}'), value & 0xFFFFFFFF)
        uc.reg_write(ar.UC_ARM_REG_LR, RET | 1)
        uc.emu_start(fn | 1, RET, count=limit)
        if uc.reg_read(ar.UC_ARM_REG_PC) != RET or uc.reg_read(ar.UC_ARM_REG_SP) != sp:
            raise RuntimeError(('did not return cleanly', hex(fn), hex(uc.reg_read(ar.UC_ARM_REG_PC)),
                                hex(uc.reg_read(ar.UC_ARM_REG_SP))))
        return uc.reg_read(ar.UC_ARM_REG_R0)

    def regs(self, names=('R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'SP')):
        return [self.uc.reg_read(getattr(ar, 'UC_ARM_REG_' + n)) for n in names]

    def put(self, address, value, fmt='<i'):
        if fmt == '<I':
            value &= 0xFFFFFFFF
        self.uc.mem_write(address, struct.pack(fmt, value))

    def get(self, address, fmt='<i'):
        return struct.unpack(fmt, bytes(self.uc.mem_read(address, struct.calcsize(fmt))))[0]

    def bytes(self, address, n):
        return bytes(self.uc.mem_read(address, n))

    def digest(self, skip):
        """Hash of every mapped region, leaving out the [lo, hi) spans in skip."""
        h = hashlib.sha256()
        for base, size in REGIONS:
            if base >= 0xE0000000:
                continue
            cuts = sorted((max(lo, base), min(hi, base + size)) for lo, hi in skip if lo < base + size and base < hi)
            at = base
            for lo, hi in cuts + [(base + size, base + size)]:
                while at < lo:
                    n = min(lo - at, 0x100000)
                    h.update(self.uc.mem_read(at, n))
                    at += n
                at = max(at, hi)
        return h.hexdigest()


def meter_state(m, sym):
    """The meter_t fields by name (layout of cpumeter/cpu_meter.c)."""
    names = ('magic stamps t_mix0 t_v0 t_v1 t_sg0 t_sg1 nvox mix_ret sg_ret have_prev budget dwt_fixed '
             'w_n w_mix_sum w_mix_max w_vox_sum w_vox_max w_sg_sum w_sg_max w_voices '
             'w_per_n w_per_sum w_per_min w_per_max seq '
             'p_blocks p_mix_avg p_mix_max p_vox_avg p_vox_max p_sg_avg p_sg_max p_voices p_per_avg p_per_min p_per_max '
             'reset_req reset_ack total hi over mix_max_ever vox_max_ever sg_max_ever voices_max_ever windows '
             'shown hold hold_t0 posted_seq posted_at posts toggles').split()
    vals = struct.unpack(f'<{len(names)}I', m.bytes(sym, 4 * len(names)))
    return dict(zip(names, vals))


# ---------------------------------------------------------------------------------------------
def static_checks(out, man, parent_img, img):
    check(sha(img) == man['sha256'] and len(img) == man['size'], 'APP1 matches the manifest')
    check(sha((out / 'SP404MKII_APP0.bin').read_bytes()) == man['app0_sha256'], 'APP0 is stock 5.52')
    rows_p, rows = scatter(parent_img), scatter(img)
    new_row = [FLASH + man['module_file_offset'], man['module_base'], man['module_size'], COPY]
    ring = [0, man['echo']['ring'], man['echo']['ring_bytes'], ZERO]
    check(rows == rows_p + [new_row, ring], "scatter table = parent rows + the module row + the echo's zero row")
    module = img[man['module_file_offset']:man['module_file_offset'] + man['module_size']]
    check(sha(module) == man['module_sha256'], 'module bytes match the manifest')
    spans = [(0x80, 0x88)]
    for p in man['patches']:
        off = None
        for load, dst, n, fn in rows_p:
            if fn == COPY and load and dst <= p['address'] and p['address'] + p['size'] <= dst + n:
                off = load - FLASH + p['address'] - dst
        spans.append((off, off + p['size']))
        check(parent_img[off:off + p['size']].hex() == p['original_hex'] and img[off:off + p['size']].hex() == p['replacement_hex'],
              f"patch {p['address']:#x}: parent bytes and replacement as recorded")
    diff = [i for i in range(len(parent_img)) if parent_img[i] != img[i] and not any(lo <= i < hi for lo, hi in spans)]
    check(not diff, f'nothing else differs inside the parent image ({len(diff)} other bytes)')
    check(len(img) > len(parent_img) and FLASH + len(img) <= 0x603FF000, 'appended tail stays below the settings sector')
    report['static'] = dict(patches=[hex(p['address']) for p in man['patches']], module_size=man['module_size'])


# ---------------------------------------------------------------------------------------------
def entry_checks(parent_img, img, sym):
    """Run each displaced prologue in both machines up to the first stock instruction after it."""
    out = {}
    for name, start, resume, entry_regs in (
            ('mixer', MIXER, 0x1C2DC, {'R0': ARGS, 'R1': 0x11, 'R2': 0x22, 'R3': 0x33}),
            ('popup tick', UI_TICK, 0x8006B95C, {'R0': 1, 'R1': 0x11, 'R2': 0x22, 'R3': 0x33})):
        res = []
        for image in (parent_img, img):
            m = Machine(image)
            m.put(0x80245880, 0, '<h')                        # not the main screen: the UI step stays idle
            regs = dict(entry_regs, R4=0x44, R5=0x55, R6=0x66, R7=0x77, R8=0x88, R9=0x99, R10=0xAA, R11=0xBB,
                        LR=0x1D09B if name == 'mixer' else 0x8003A9F5, SP=STACK)
            for r, v in regs.items():
                m.uc.reg_write(getattr(ar, 'UC_ARM_REG_' + r), v)
            m.uc.emu_start(start | 1, resume, count=200000)
            got = {r: m.uc.reg_read(getattr(ar, 'UC_ARM_REG_' + r)) for r in
                   ('R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'SP', 'LR', 'PC')}
            sp = got['SP']
            frame = m.bytes(sp, STACK - sp)
            res.append((got, frame, m))
        (gp, fp, mp), (gm, fm, mm) = res
        if name == 'mixer':
            # The saved return in the frame is meter_mix_exit; the meter keeps the original.
            st = meter_state(mm, sym['meter'])
            exit_ = sym['meter_mix_exit'] | 1
            same = all(gp[r] == gm[r] for r in ('R0', 'R1', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'SP', 'PC'))
            frame_ok = len(fp) == len(fm) and fp[:-4] == fm[:-4] and struct.unpack('<I', fm[-4:])[0] == exit_ and \
                struct.unpack('<I', fp[-4:])[0] == 0x1D09B
            check(same and frame_ok and st['mix_ret'] == 0x1D09B,
                  'mixer entry: registers and frame as stock, return routed through meter_mix_exit')
        else:
            same = all(gp[r] == gm[r] for r in ('R0', 'R1', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'SP', 'LR', 'PC'))
            check(same and fp == fm, "popup tick entry through bounce's ui bridge (diag_ui): registers and frame as "
                                     "the parent's (bnc_ui alone)")
        out[name] = dict(stock_sp=hex(gp['SP']), meter_sp=hex(gm['SP']))
    report['entries'] = out


# ---------------------------------------------------------------------------------------------
def make_voices(m, seed, occupancy=0.6, special=0.1):
    """Randomised but well-formed voices in all 32 slots (same seed -> same bytes)."""
    rng = random.Random(seed)
    m.put(0x83FFB8F4, rng.choice([0, 1]), '<B')               # global cue switch
    m.put(0x83FFB908, rng.choice([0, 1]), '<i')               # DRY stem select
    m.put(0x802457BC, rng.choice([0, 1, 2, 3]), '<B')         # envelope curve
    m.put(0x805968CC, rng.choice([0, 0, 5]), '<i')
    occupied = 0
    for k in range(32):
        slot = SLOT0 + k * SLOT_SIZE
        words = [0] + [rng.choice([0, 0, 1, 2, 3, 16, 17]) for _ in range(21)]
        m.uc.mem_write(slot, struct.pack('<22I', *words))
        if rng.random() >= occupancy:
            continue
        occupied += 1
        v, s = VOICES + k * VOICE_SIZE, STREAMS + k * STREAM_SIZE
        m.uc.mem_write(v, bytes(0x28810))
        m.uc.mem_write(slot, struct.pack('<I', v))
        vw = {0x2C: rng.randint(0, 12700), 0x38: k, 0xA8: rng.randint(0, 12700), 0xAC: rng.randint(0, 12700),
              0xEC: rng.choice([0, 0xD, 0x73, 5]), 0x114: 1 if rng.random() < special else 0,
              0x118: rng.randint(-5, 12700), 0x120: rng.choice([0, 0, 1, 2]), 0x124: rng.choice([0, 0, 0, 1]),
              0x12C: rng.randint(0, 12700), 0x130: rng.randint(0, 12700), 0x14268: s,
              0x14274: rng.choice([rng.randint(0, 159)] * 6 + [1000, 1001, 1002, -1]), 0x14278: k,
              0x1439C: rng.choice([0] * 6 + [1, 2, 5, 40]), 0x143AC: rng.choice([0] * 6 + [1, 3]),
              0x143B0: rng.randint(0, 64), 0x143D8: rng.choice([0, 0, 1, 2]), 0x143E0: rng.choice([0] * 7 + [1, 2, -1])}
        for off, val in vw.items():
            m.uc.mem_write(v + off, struct.pack('<I', val & 0xFFFFFFFF))
        for off, val in ((0x10, rng.choice([0, 0, 0, 1])), (0xC8, rng.choice([0, 0, 1])), (0xC9, rng.choice([0, 1])),
                         (0x143A0, rng.choice([0, 1])), (0x143E4, rng.choice([0, 0, 1]))):
            m.uc.mem_write(v + off, bytes([val]))
        chunks = [s + 0x40 + c * 0x2090 for c in range(4)]
        head = bytes([1 if rng.random() < 0.95 else 0, rng.choice([0, 1, 2, 3] * 8 + [0xFF])]) + bytes(10)
        head += struct.pack('<6i', rng.choice([-1, 0]), rng.choice([0, 1, 2, 3]), rng.randint(0, 1000),
                            rng.randint(0, 10000), rng.randint(0, 10000), 0)[:24]
        m.uc.mem_write(s, head[:0x20])
        m.uc.mem_write(s + 0x20, struct.pack('<4I', *chunks))
        for c in chunks:
            frames = rng.choice([64, 100, 2048, 30, 1, 0, 300])
            pos = rng.randint(0, 2048 - max(frames, 1))
            m.uc.mem_write(c, struct.pack('<IB3xii', 0xFFFFFFFF if rng.random() < 0.9 else 0, rng.choice([0, 0, 1]), frames, pos))
            m.uc.mem_write(c + 0x80, struct.pack('<4096h', *[rng.randint(-12000, 12000) for _ in range(4096)]))
            m.uc.mem_write(c + 0x2080, struct.pack('<I', rng.randint(0, 3000)))
    return occupied


def skip_spans(man):
    """What may differ between the two machines: the image itself (flash), the patched spans as
    copied to ITCM/SDRAM, the module area, the echo's ring, and the scratch stack below the caller."""
    e = man['echo']
    spans = [(man['module_base'], man['module_limit']), (e['ring'], e['ring'] + e['ring_bytes']), (TEST, STACK),
             (0x60000000, 0x60400000)]
    spans += [(p['address'], p['address'] + p['size']) for p in man['patches']]
    return spans


def voice_chain(parent_img, img, man, seeds, sabotage=False):
    """sabotage=True is the negative control: one stem word nudged before every render on the
    meter side only, which the comparison must catch."""
    sym = man['symbols']
    total_occupied, mismatches = 0, []
    counts = {a: 0 for a in BUS_ADDS + (CONSUMER, RENDERER)}
    for seed in range(seeds):
        res = []
        for image in (parent_img, img):
            m = Machine(image)
            m.count(BUS_ADDS + (CONSUMER, RENDERER))
            if sabotage and image is img:
                m.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _, m=m: m.put(STEMS + 0x40, m.get(STEMS + 0x40) + 1),
                              begin=RENDERER, end=RENDERER)
            occ = make_voices(m, 1000 + seed)
            m.uc.mem_write(STEMS, bytes(0xE00))
            outs = []
            for k in range(32):
                m.put(SCRATCH, -1)
                m.put(SCRATCH + 4, -1)
                m.uc.reg_write(ar.UC_ARM_REG_R4, 0x4444 + k)
                m.uc.reg_write(ar.UC_ARM_REG_R11, 0xBBBB + k)
                m.call(VENEER, SLOT0 + k * SLOT_SIZE, STEMS, SCRATCH, SCRATCH + 4)
                outs.append((m.get(SCRATCH), m.get(SCRATCH + 4), m.regs()))
            res.append((outs, m.log, m.digest(skip_spans(man)), m, occ))
        (op, lp, dp, mp, occ), (om, lm, dm, mm, _) = res
        total_occupied += occ
        for a in counts:
            counts[a] += mm.counts[a]
        if op != om or lp != lm or dp != dm:
            mismatches.append(dict(seed=seed, outputs=op == om, stubs=lp == lm, memory=dp == dm))
        st = meter_state(mm, sym['meter'])
        if st['nvox'] != occ or st['stamps'] & 3 != 3:
            mismatches.append(dict(seed=seed, nvox=st['nvox'], occupied=occ, stamps=st['stamps']))
    if sabotage:
        check(sum(1 for x in mismatches if x.get('memory') is False) == seeds,
              'negative control: a one-step change to one stem word on the meter side is caught')
        return
    check(not mismatches, f'voice chain: {seeds} seeds x 32 slots ({total_occupied} voices) identical to stock '
                          f'(memory, bus/bus2, registers, stub calls); slot 0/31 stamped, voices counted')
    check(all(counts[a] for a in (CONSUMER, 0x16384, 0x1620C, 0x15FEE, 0x16308)),
          'voice chain reached the stream consumer and the main, release, declick and cue bus adds')
    report['voice_chain'] = dict(seeds=seeds, voices=total_occupied, mismatches=mismatches[:5],
                                 calls={hex(a): n for a, n in counts.items()})


# ---------------------------------------------------------------------------------------------
def strike_cymbals(m, kit_sym):
    m.put(PAGE, SG_PAGE, '<h')
    for off, value in ((0, 1), (4, 0), (8, 0), (0xC, 0), (0x10, 0), (0x14, 0)):
        m.put(KB + off, value)
    for v in SG_VOICES:
        m.uc.mem_write(v, b'\0\0\0\0')
    m.call(STOCK_RESET, SG_VOICES[0])
    m.put(kit_sym['kit_mode'], 7, '<B')                       # TR606
    for _ in range(4):
        m.uc.mem_write(SCRATCH + 0x100, bytes([0, 0x9F, 36 + 6, 127]))   # pad 7: the 606 cymbal
        m.call(DISPATCH, SCRATCH + 0x100)
    return sum(1 for v in SG_VOICES if m.bytes(v, 1)[0])


def whole_mixer(parent_img, img, man, kit_sym, blocks, seeds):
    sym = man['symbols']
    results, mismatches = [], []
    for seed in range(seeds):
        machines = []
        for image in (parent_img, img):
            m = Machine(image)
            m.cyc_step = 7
            live = strike_cymbals(m, kit_sym) if seed % 2 == 0 else 0
            occ = make_voices(m, 5000 + seed, occupancy=0.5 if seed % 2 == 0 else 0.9)
            m.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
            machines.append((m, live, occ))
        (mp, live, occ), (mm, _, _) = machines
        tx_nonzero = 0
        for b in range(blocks):
            outs = []
            for m, _, _ in machines:
                m.uc.mem_write(TXBUF, bytes(0x3000))
                m.call(MIXER, ARGS)
                outs.append((m.bytes(TXBUF, 0x3000), m.log, m.regs()))
            tx_nonzero += any(outs[0][0])
            if outs[0] != outs[1]:
                mismatches.append(dict(seed=seed, block=b, tx=outs[0][0] == outs[1][0], stubs=outs[0][1] == outs[1][1]))
                break
        same = mp.digest(skip_spans(man)) == mm.digest(skip_spans(man))
        st = meter_state(mm, sym['meter'])
        if not same:
            mismatches.append(dict(seed=seed, memory=False))
        results.append(dict(seed=seed, kit_voices=live, sample_voices=occ, blocks=blocks, tx_blocks_with_sound=tx_nonzero,
                            meter_total=st['total'], stamps=st['stamps'], nvox=st['nvox']))
        if st['total'] != blocks or st['stamps'] != 15 or st['nvox'] != occ:
            mismatches.append(dict(seed=seed, meter=st))
    check(not mismatches, f'whole mixer: {seeds} runs x {blocks} blocks, TX buffers and all memory identical to stock')
    check(all(r['tx_blocks_with_sound'] for r in results) and any(r['kit_voices'] == 4 for r in results),
          'whole mixer runs carried sound, with four kit cymbals ringing in the kit runs')
    report['whole_mixer'] = dict(runs=results, mismatches=mismatches[:5])


# ---------------------------------------------------------------------------------------------
def counted(image, kit_sym, seed, cymbals, occupancy, blocks, meter=None):
    """Mixer blocks with the cycle counter driven by the instruction count; stamps at the stock
    boundaries: voice loop 0x1c710..0x1c73e, SG call 0x1c766..0x1c76a, mixer entry..return.
    With meter (its state address) each row also holds the meter's own spans for that block."""
    m = Machine(image)
    live = strike_cymbals(m, kit_sym) if cymbals else 0
    occ = make_voices(m, seed, occupancy=occupancy)
    m.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    marks = {}

    def every(uc, a, s, _):
        m.cyc += 1
    m.uc.hook_add(UC_HOOK_CODE, every)
    for name, at in (('mix0', MIXER), ('v0', 0x1C710), ('v1', 0x1C73E), ('sg0', 0x1C766), ('sg1', 0x1C76A)):
        def mark(uc, a, s, _, name=name):
            if name != 'v0' or 'v0' not in marks:
                marks[name] = m.cyc
        m.uc.hook_add(UC_HOOK_CODE, mark, begin=at, end=at)
    rows = []
    for _ in range(blocks):
        marks.clear()
        before = meter_state(m, meter)['w_mix_sum'] if meter else 0
        m.call(MIXER, ARGS)
        marks['mix1'] = m.cyc                                      # back at the caller
        row = dict(mix=marks['mix1'] - marks['mix0'], pad=marks['v1'] - marks['v0'], sg=marks['sg1'] - marks['sg0'])
        if meter:
            st = meter_state(m, meter)
            row.update(meter_mix=st['w_mix_sum'] - before, meter_pad=st['t_v1'] - st['t_v0'],
                       meter_sg=st['t_sg1'] - st['t_sg0'])
        rows.append(row)
    return rows, occ, live


def measurement_points(parent_img, img, man, kit_sym, blocks=3):
    """The meter's PAD, SG and MIX spans against the stock boundary stamps (what is left over is
    the meter's own few instructions on each side), and the meter's own cost per block against
    the parent image, idle and loaded (instructions, as a proxy for cycles)."""
    meter = man['symbols']['meter']
    out, offsets = {}, {'pad': [], 'sg': [], 'mix': []}
    for label, seed, cymbals, occupancy in (('idle', 1, False, 0.0), ('15 voices + 4 TR-606 cymbals', 777, True, 0.5),
                                            ('32 voices', 778, False, 1.01)):
        rows_p, occ, live = counted(parent_img, kit_sym, seed, cymbals, occupancy, blocks)
        rows_m, _, _ = counted(img, kit_sym, seed, cymbals, occupancy, blocks, meter=meter)
        for r in rows_m:
            for k in offsets:
                offsets[k].append(r[k] - r['meter_' + k])
        out[label] = dict(voices=occ, kit_voices=live, stock=rows_p, meter=rows_m,
                          meter_cost=[b['mix'] - a['mix'] for a, b in zip(rows_p, rows_m)])
    loaded = out['15 voices + 4 TR-606 cymbals']['meter'] + out['32 voices']['meter']
    big = all(r['pad'] > 10000 for r in loaded) and all(r['sg'] > 10000 for r in out['15 voices + 4 TR-606 cymbals']['meter'])
    lims = {'pad': 64, 'sg': 32, 'mix': 160}
    check(big and all(0 <= min(v) and max(v) <= lims[k] for k, v in offsets.items()),
          'measurement points: meter spans = stock boundary spans minus its own instructions (' +
          ', '.join(f'{k} {min(v)}..{max(v)}' for k, v in offsets.items()) + ')')
    cost = [c for v in out.values() for c in v['meter_cost']]
    check(max(cost) <= 1500, f'the meter itself costs {min(cost)}..{max(cost)} instructions per block '
                             f'({max(cost) / 8000:.2f}% of an 800,000-cycle block at one cycle each)')
    report['measurement_points'] = dict(cases=out, offsets={k: [min(v), max(v)] for k, v in offsets.items()},
                                        note='instructions; the cycle counter was driven by the instruction count')


# ---------------------------------------------------------------------------------------------
def arithmetic(img, man):
    sym = man['symbols']
    m = Machine(img)
    S = sym['meter']
    slot0, slot31 = SLOT0, SLOT0 + 31 * SLOT_SIZE
    for k in range(32):
        m.uc.mem_write(SLOT0 + k * SLOT_SIZE, bytes(4))             # empty slots: no renderer call
    t = 1000
    def block(mix, vox, sg, voices, period=800000):
        nonlocal t
        m.cyc = t
        m.call(sym['meter_mix_begin'], 0xABCD)
        m.cyc = t + 100
        m.call(sym['meter_voice'], slot0, STEMS, SCRATCH, SCRATCH + 4)
        m.put(S + 28, voices)                                         # nvox as if occupied slots rendered
        m.cyc = t + 100 + vox
        m.call(sym['meter_voice'], slot31, STEMS, SCRATCH, SCRATCH + 4)
        st = meter_state(m, S)
        m.put(S + 20, t + 200 + vox)                                  # SG stamps (the stub path is checked
        m.put(S + 24, t + 200 + vox + sg)                             # end to end in the mixer runs)
        m.put(S + 4, st['stamps'] | 12)
        m.cyc = t + mix
        r = m.call(sym['meter_mix_end'])
        t += period
        return r
    first = block(400000, 100000, 50000, 3)
    st = meter_state(m, S)
    check(first == 0xABCD and st['magic'] == 0x4D455452 and st['total'] == 1 and st['budget'] == 800000,
          'first block: initialised, returns to the saved caller, nominal budget')
    pattern = [(400000, 100000, 50000, 3)] * 300 + [(700000, 300000, 90000, 12)] * 70 + [(900000, 500000, 120000, 32)] * 4
    for p in pattern:
        block(*p)
    st = meter_state(m, S)
    n = 375
    mix_sum = 400000 * 301 + 700000 * 70 + 900000 * 4
    vox_sum = 100000 * 301 + 300000 * 70 + 500000 * 4
    sg_sum = 50000 * 301 + 90000 * 70 + 120000 * 4
    ok = (st['windows'] == 1 and st['seq'] == 2 and st['p_blocks'] == n and st['p_mix_avg'] == mix_sum // n and
          st['p_mix_max'] == 900000 and st['p_vox_avg'] == vox_sum // n and st['p_vox_max'] == 500000 and
          st['p_sg_avg'] == sg_sum // n and st['p_sg_max'] == 120000 and st['p_voices'] == 32 and
          st['p_per_avg'] == 800000 and st['p_per_min'] == 800000 and st['p_per_max'] == 800000)
    check(ok, 'window of 375 blocks: averages, peaks, most voices and block length exact')
    check(st['hi'] == 74 and st['over'] == 4 and st['mix_max_ever'] == 900000 and st['voices_max_ever'] == 32 and st['total'] == 375,
          'HI counts blocks over 75% (600k), OVR over 100% (800k), MAX the slowest block')
    window1 = dict(mix_avg=st['p_mix_avg'], mix_max=st['p_mix_max'], vox_avg=st['p_vox_avg'], vox_max=st['p_vox_max'],
                   sg_avg=st['p_sg_avg'], sg_max=st['p_sg_max'], voices=st['p_voices'], period_avg=st['p_per_avg'])
    # Measured block length drives the budget: 1.4 ms blocks = 840,000 cycles (the window's first
    # start-to-start still spans the previous 800,000-cycle block).
    for _ in range(375):
        block(500000, 0, 0, 0, period=840000)
    st = meter_state(m, S)
    want = (800000 + 374 * 840000) // 375
    check(st['p_per_avg'] == want and st['budget'] == want and st['hi'] == 74,
          f"budget follows the measured block length ({st['budget']}); 500k under 75% of the old 800k")
    for _ in range(375):
        block(650000, 0, 0, 0, period=840000)                        # over 75% of ~840k (630k), under 100%
    st = meter_state(m, S)
    check(st['hi'] == 74 + 375 and st['over'] == 4, 'thresholds use the measured budget: 650k counts as HI, not OVR')
    # Implausible block length (2 ms = 1.2M cycles) falls back to 800,000.
    for _ in range(375):
        block(100000, 0, 0, 0, period=1200000)
    check(meter_state(m, S)['budget'] == 800000, 'implausible block length: budget back to 800,000')
    # Reset requested by the UI: cleared at the next block end.
    m.put(S + 4 * 37, meter_state(m, S)['reset_req'] + 1)
    block(100000, 0, 0, 0)
    st = meter_state(m, S)
    check(st['total'] == 1 and st['hi'] == 0 and st['over'] == 0 and st['mix_max_ever'] == 100000 and st['reset_ack'] == st['reset_req'],
          'switch-on reset clears HI, OVR and MAX at the next block')
    # Empty slots never call the renderer; slot 0/31 stamps only.
    check(st['stamps'] == 15 and st['nvox'] == 0, 'stamps for slot 0, slot 31 and the SG span; empty slots render nothing')
    # Counter start-up fallback.
    m2 = Machine(img)
    m2.dwt_ctrl = 0
    m2.call(sym['meter_mix_begin'], 0x1234)
    st2 = meter_state(m2, S)
    check(st2['dwt_fixed'] == 1 and (0xFB0, 0xC5ACCE55) in m2.dwt_writes and m2.dwt_ctrl & 1,
          'cycle counter stopped at boot: the meter starts it (DEMCR, LAR, CTRL) and flags it')
    m3 = Machine(img)
    m3.call(sym['meter_mix_begin'], 0x1234)
    check(meter_state(m3, S)['dwt_fixed'] == 0 and not m3.dwt_writes, 'cycle counter running: nothing written to the DWT')
    report['arithmetic'] = dict(first_window=window1, measured_budget=want)


# ---------------------------------------------------------------------------------------------
def font_widths(img):
    m = Machine(img)
    d = m.get(FONT_TABLE + 4 * POPUP_FONT, '<I')
    lo, hi, dflt = m.get(d + 6, '<h'), m.get(d + 8, '<h'), m.get(d + 10, '<h')
    glyphs, line = m.get(d + 0x10, '<I'), m.get(d + 0xD, '<b')

    def width(ch):
        c = ord(ch)
        if c < lo or c > hi:
            if 0x61 <= c <= 0x7A:
                c -= 0x20
            if c < lo or c > hi:
                c = dflt
        return m.get(glyphs + (c - lo) * 12 + 4, '<h')
    return width, line


def readout(img, man):
    sym = man['symbols']
    width, line = font_widths(img)
    m = Machine(img)
    S = sym['meter']
    m.cyc = 5
    m.call(sym['meter_mix_begin'], 0)                                 # initialise (budget 800k)
    cases = {
        'idle': ((60000, 90000, 0, 0, 0, 0, 0, 800000, 800000, 800000), (0, 0, 120000)),
        'typical': ((184000, 328000, 120000, 240000, 48000, 96000, 12, 800000, 799000, 801000), (3, 0, 456000)),
        'worst': ((9999999, 9999999, 9999999, 9999999, 9999999, 9999999, 4000, 5000000, 0, 5000000), (99999, 99999, 9999999)),
    }
    texts = {}
    E = sym['echo']
    m.put(E + E_FX, 23)
    m.put(E + E_PEAK, 16384)
    m.put(E + E_ON, 1)
    for name, (w, (hi_, over, mx)) in cases.items():
        m.uc.mem_write(SCRATCH, struct.pack('<11I', 375, *w))
        m.put(S + 4 * 40, hi_)
        m.put(S + 4 * 41, over)
        m.put(S + 4 * 42, mx)
        m.call(sym['meter_format'], SCRATCH, SCRATCH + 0x100)
        text = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
        texts[name] = text
    lines = {k: v.split('\n') for k, v in texts.items()}
    check(texts['typical'] == 'MIX 23/41\nPAD 15/30 12v\nSG 6/12\nHI 3 OVR 0\nMAX 57 CLK 600\nIN23 LV50 E1',
          f"typical readout reads {texts['typical']!r}")
    check(texts['idle'] == 'MIX 8/11\nPAD 0/0 0v\nSG 0/0\nHI 0 OVR 0\nMAX 15 CLK 600\nIN23 LV50 E1',
          f"idle readout reads {texts['idle']!r}")
    widest = max(sum(width(c) for c in ln) for v in lines.values() for ln in v)
    # Stock popup (kind 5): box = text width - 1 + 2*8 + 2 must fit 128; height = lines*9 - 1 + 2*3 + 2.
    box_w, box_h = widest - 1 + 18, 6 * line - 1 + 8
    check(all(len(v) == 6 for v in lines.values()) and box_w <= 128 and box_h <= 64,
          f'worst-case readout fits the popup: widest line {widest} px -> box {box_w}x{box_h} (screen 128x64)')
    stock = 'PATTERN SELECT'
    report['readout'] = dict(texts=texts, widest_line_px=widest, box=[box_w, box_h],
                             stock_widest_example=dict(text=stock, px=sum(width(c) for c in stock)), line_px=line)


# ---------------------------------------------------------------------------------------------
def ui(img, man):
    sym = man['symbols']
    S = sym['meter']
    m = Machine(img)
    closes = []

    def close_hook(uc, a, s, _):
        closes.append(1)
        m.put(POPUP_SHOWN, 0, '<I')
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))
    m.uc.hook_add(UC_HOOK_CODE, close_hook, begin=POPUP_CLOSE, end=POPUP_CLOSE)
    m.cyc = 100
    m.call(sym['meter_mix_begin'], 0)
    m.cyc = 200
    m.call(sym['meter_mix_end'])
    second = 600000000

    def keys(*down):
        b = bytearray(11)
        for k in down:
            b[k >> 3] |= 1 << (k & 7)
        m.uc.mem_write(KEYS, bytes(b))

    def tick(dt=0):
        m.cyc += dt
        m.call(sym['meter_ui_tick'], 1)
        return meter_state(m, S)

    def built():
        """What the stock popup tick does next with a post: builds it (pending -> on screen)."""
        if m.get(POPUP_PENDING) >= 0:
            m.put(POPUP_PENDING, -1)
            m.put(POPUP_SHOWN, 0x1234, '<I')

    def text():
        return m.bytes(POPUP_TEXT, 0x60).split(b'\0')[0].decode('latin-1')

    m.put(PAGE, 1, '<h')
    m.put(POPUP_PENDING, -1)
    m.put(POPUP_SHOWN, 0, '<I')
    keys()
    st = tick()
    check(st['shown'] == 0 and st['posts'] == 0, 'idle: nothing shown')
    keys(KEY_EXIT)
    tick()
    st = tick(second - 1000)
    check(st['shown'] == 0 and st['posts'] == 0, 'EXIT held just under a second: no toggle')
    st = tick(2000)
    first = text()
    check(st['shown'] == 1 and st['posts'] == 1 and m.get(POPUP_PENDING) == 3 and first.startswith('MIX ') and
          first.count('\n') == 5 and m.get(0x802458A4) == 1500,
          f'EXIT held a second on the main screen: readout posted through the stock popup ({first!r}, 1500 ms)')
    built()
    st = tick(3 * second)
    check(st['shown'] == 1 and st['toggles'] == 1 and st['posts'] == 2,
          'still holding EXIT: no second toggle; the readout is kept alive')
    built()
    keys()
    st = tick(10)
    check(st['posts'] == 2, 'nothing new: no re-post')
    # A finished window refreshes it at once.
    m.put(S + 4 * 25, st['seq'] + 2)
    st = tick(10)
    check(st['posts'] == 3, 'a new window: re-posted at once')
    built()
    # A stock message on screen is left alone; when it is gone the readout comes back.
    m.uc.mem_write(POPUP_TEXT, b'Same EFX\non other BUS\0')
    st = tick(2 * second)
    check(st['posts'] == 3 and text() == 'Same EFX\non other BUS', 'a stock popup on screen: not covered')
    m.put(POPUP_SHOWN, 0, '<I')
    st = tick(10)
    check(st['posts'] == 4 and text().startswith('MIX '), 'stock popup gone: the readout comes back')
    built()
    m.put(POPUP_PENDING, 3)
    m.put(S + 4 * 25, st['seq'] + 2)
    st = tick(2 * second)
    check(st['posts'] == 4, 'a stock post waiting to be built: not overwritten')
    m.put(POPUP_PENDING, -1)
    tick(10)
    built()
    # Switch off: hold EXIT again; our popup is closed at once.
    keys(KEY_EXIT)
    tick()
    st = tick(second + 10)
    check(st['shown'] == 0 and closes == [1], 'EXIT held again: readout off, our popup closed')
    keys()
    st = tick(5 * second)
    posts_off = st['posts']
    check(m.get(POPUP_SHOWN, '<I') == 0, 'off: nothing re-posted')
    # Cancels: SHIFT held, another page, another key or a page change during the hold.
    for label, setup, during in (('SHIFT + EXIT', lambda: keys(KEY_EXIT, KEY_SHIFT), None),
                                 ('EXIT on another page', lambda: (m.put(PAGE, SG_PAGE, '<h'), keys(KEY_EXIT)), None),
                                 ('ROLL pressed during the hold', lambda: keys(KEY_EXIT), lambda: keys(KEY_EXIT, KEY_ROLL)),
                                 ('page change during the hold', lambda: keys(KEY_EXIT), lambda: m.put(PAGE, SG_PAGE, '<h'))):
        m.put(PAGE, 1, '<h')
        keys()
        tick()
        setup()
        tick()
        if during:
            tick(second // 2)
            during()
        st = tick(2 * second)
        check(st['shown'] == 0 and st['posts'] == posts_off, f'{label}: no toggle')
        keys()
        m.put(PAGE, 1, '<h')
        tick()
    # Off with a stock popup showing: that popup is not closed.
    keys(KEY_EXIT)
    tick()
    st = tick(second + 10)
    check(st['shown'] == 1, 'on again')
    built()
    keys()
    tick()
    m.uc.mem_write(POPUP_TEXT, b'BANK is Protected\0')
    keys(KEY_EXIT)
    tick()
    st = tick(second + 10)
    check(st['shown'] == 0 and closes == [1] and m.get(POPUP_SHOWN, '<I') != 0,
          'switching off while a stock popup is up leaves that popup')
    # A key already down before EXIT (a held pad, a stuck bit) does not block the gesture.
    keys()
    tick()
    keys(0x05)
    tick()
    keys(0x05, KEY_EXIT)
    tick()
    st = tick(second + 10)
    check(st['shown'] == 1, 'a key already down before EXIT does not block the gesture')
    # Never over DOOM OS's own screen (page 95); back on a stock page it shows again.
    built()
    keys()
    m.put(POPUP_SHOWN, 0, '<I')
    posts = tick(10)['posts']
    built()
    m.put(POPUP_SHOWN, 0, '<I')
    m.put(PAGE, 95, '<h')
    m.put(S + 4 * 25, meter_state(m, S)['seq'] + 2)
    st = tick(3 * second)
    check(st['posts'] == posts and st['shown'] == 1, "DOOM OS's own screen (page 95): nothing posted")
    m.put(PAGE, SG_PAGE, '<h')
    st = tick(10)
    check(st['posts'] == posts + 1, 'back on a stock page (the kit page): the readout returns')
    report['ui'] = dict(posts=st['posts'], toggles=st['toggles'], first_text=first)


# ---------------------------------------------------------------------------------------------
CAPTURE, SYSPRM, SYS_GET, SETTINGS_OBJ, SET_GET = 0x202AD0A0, 0x82DFEED0, 0x800DA010, 0x82E01144, 0x800D94D8
E_W, E_ON, E_FX, E_CHECKED, E_CHECKS, E_RX, E_TX, E_PEAK, E_EXT = 0, 4, 8, 12, 16, 20, 24, 28, 32   # echo_t
M_SHOWN = 4 * 47                                                                 # meter_t.shown


def mono(cap):
    return [(cap[2 * f] + cap[2 * f + 1]) >> 1 for f in range(64)]


def clip20(v):
    return max(-0x80000, min(0x7FFFF, v))


def capture_block(rng, n):
    loud = n % 7 == 3                                              # now and then full scale, to reach the clip
    return [rng.choice([-32768, 32767]) if loud and rng.random() < 0.5 else rng.randint(-20000, 20000)
            for _ in range(128)]


def echo_checks(parent_img, img, man):
    sym = man['symbols']
    e = sym['echo']
    frames = man['echo']['frames']
    delay = frames // 64
    rng = random.Random(404)
    # 1. The ring and the TX add, block by block (TX before RX, as the audio task runs them).
    m = Machine(img)
    m.put(e + E_ON, 1)
    m.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    sent, bad, clipped, nonzero = [], [], 0, 0
    blocks = delay + 40
    for n in range(blocks):
        base = [rng.randint(-0x80000, 0x7FFFF) if rng.random() < 0.2 else rng.randint(-40000, 40000) for _ in range(1024)]
        m.uc.mem_write(TXBUF, struct.pack('<1024i', *base))
        m.call(sym['echo_tx'], ARGS)
        got = list(struct.unpack('<1024i', m.bytes(TXBUF, 4096)))
        echo = [x >> 2 for x in mono(sent[n - delay])] if n >= delay else [0] * 64
        want = list(base)
        for f in range(64):
            for w in (0, 1):
                v = base[16 * f + w] + echo[f]
                clipped += v != clip20(v)
                want[16 * f + w] = clip20(v)
        nonzero += any(echo)
        if got != want:
            bad.append(n)
        cap = capture_block(rng, n)
        sent.append(cap)
        m.uc.mem_write(CAPTURE, struct.pack('<128h', *cap))
        m.call(sym['echo_rx'])
    st = struct.unpack('<9I', m.bytes(e, 36))
    check(not bad and nonzero == blocks - delay and clipped > 0 and st[E_RX // 4] == blocks and st[E_TX // 4] == blocks,
          f'echo: {blocks} blocks, each TX block = its words + the RX block {delay} blocks back as mono at 1/4 on '
          f'DRY L/R only, clipped to 20 bits ({clipped} clipped words); silent before the ring fills')
    # 2. Through the whole mixer (meter_mix_entry ... meter_mix_end): the parent's TX plus exactly the echo.
    machines = []
    for image in (parent_img, img):
        mm = Machine(image)
        make_voices(mm, 9090, occupancy=0.5)
        mm.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
        machines.append(mm)
    mp, md = machines
    md.put(e + E_ON, 1)
    rng = random.Random(7)
    caps, mismatch, loud = [], [], 0
    for n in range(delay + 6):
        if n >= delay:
            outs = []
            for mm in (mp, md):
                mm.uc.mem_write(TXBUF, bytes(0x3000))
                mm.call(MIXER, ARGS)
                outs.append(list(struct.unpack('<1024i', mm.bytes(TXBUF, 4096))) + [mm.bytes(TXBUF + 0x1000, 0x2000)])
            echo = [x >> 2 for x in mono(caps[n - delay])]
            want = outs[0][:1024]
            for f in range(64):
                for w in (0, 1):
                    want[16 * f + w] = clip20(want[16 * f + w] + echo[f])
            loud += any(outs[0][:1024])
            if outs[1][:1024] != want or outs[1][1024] != outs[0][1024]:
                mismatch.append(n)
        cap = capture_block(rng, n)
        caps.append(cap)
        md.uc.mem_write(CAPTURE, struct.pack('<128h', *cap))
        md.call(sym['echo_rx'])
    check(not mismatch and loud, f'whole mixer with the echo on: TX line 3 = the parent\'s + the echo on DRY L/R, '
                                 f'the other words and lines 1/2 the parent\'s ({len(range(delay, delay + 6))} blocks)')
    # 3. The gate (test3): the readout shown and EXT SOURCE on, read every 0.1 s from the UI task; the input FX's
    #    effect number reported.
    m = Machine(img)
    ext, calls = [1], []

    def getter(uc, a, s_, _):
        calls.append((a, uc.reg_read(ar.UC_ARM_REG_R0), uc.reg_read(ar.UC_ARM_REG_R1), uc.reg_read(ar.UC_ARM_REG_R2)))
        uc.reg_write(ar.UC_ARM_REG_R0, 23 if a == SYS_GET else ext[0])
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))
    for a in (SYS_GET, SET_GET):
        m.uc.hook_add(UC_HOOK_CODE, getter, begin=a, end=a)
    step = 60_000_000
    seen = []
    S = sym['meter']
    for cyc, shown, value in ((step, 0, 1), (2 * step, 1, 1), (2 * step + 1000, 1, 0), (3 * step + 5, 1, 0),
                              (4 * step + 10, 1, 1)):
        m.cyc = cyc
        m.put(S + M_SHOWN, shown)
        ext[0] = value
        m.call(sym['echo_ui'])
        seen.append(m.get(e + E_ON))
    want_calls = [(SYS_GET, SYSPRM, 0x27C, 0), (SET_GET, SETTINGS_OBJ, 0x25, 0)] * 4
    check(seen == [0, 1, 1, 0, 1] and calls == want_calls and m.get(e + E_FX) == 23,
          f'gate (test3): on while the readout is shown and EXT SOURCE is on, checked every 0.1 s ({len(calls) // 2} '
          f'checks); the input FX number reported ({seen})')
    # 4. Off, the TX block is untouched.
    m = Machine(img)
    m.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    block = struct.pack('<1024i', *[rng.randint(-0x80000, 0x7FFFF) for _ in range(1024)])
    m.uc.mem_write(TXBUF, block)
    m.cyc_step = 7
    m.call(sym['meter_mix_begin'], 0x1D09B, ARGS)
    r = m.call(sym['meter_mix_end'])
    check(r == 0x1D09B and m.bytes(TXBUF, 4096) == block, 'echo off: meter_mix_end leaves the TX block alone')
    # 5. diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui (same memory as the parent calling them).
    bb = man['bounce_bridges']
    for label, ours, theirs in (('diag_rx', sym['diag_rx'], bb['bnc_rx']), ('diag_ui', sym['diag_ui'], bb['bnc_ui'])):
        res = []
        cap = struct.pack('<128h', *capture_block(rng, 1))
        for image, fn in ((parent_img, theirs), (img, ours)):
            mm = Machine(image)
            mm.uc.mem_write(CAPTURE, cap)
            for _ in range(3):
                mm.call(fn, 1)
            res.append((mm.digest(skip_spans(man)), mm.log))
        check(res[0] == res[1], f"{label}: bounce's own {'bnc_rx' if label == 'diag_rx' else 'bnc_ui'} runs as in the "
                                f"parent (all memory but the module and the ring)")
    report['echo'] = dict(blocks=blocks, delay_blocks=delay, clipped_words=clipped, gate=seen, gate_reads=len(calls))


# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--kits', type=Path, required=True, help="the kit stage's kits-manifest.json (arp_symbols)")
    ap.add_argument('--seeds', type=int, default=12)
    ap.add_argument('--blocks', type=int, default=6)
    ap.add_argument('--mixer-runs', type=int, default=4)
    a = ap.parse_args()
    out = a.out.resolve()
    man = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    img = (out / 'SP404MKII_APP1.bin').read_bytes()
    parent_path = Path(man['parent_app1'])
    parent_img = parent_path.read_bytes()
    if sha(parent_img) != man['parent_sha256']:
        raise SystemExit('parent APP1 does not match the manifest')
    kit_sym = json.loads(a.kits.read_text(encoding='utf-8')).get('arp_symbols')
    if not kit_sym:
        raise SystemExit('no kit symbols beside the parent APP1')
    sym = man['symbols']
    static_checks(out, man, parent_img, img)
    entry_checks(parent_img, img, sym)
    arithmetic(img, man)
    readout(img, man)
    ui(img, man)
    voice_chain(parent_img, img, man, a.seeds)
    voice_chain(parent_img, img, man, 2, sabotage=True)
    whole_mixer(parent_img, img, man, kit_sym, a.blocks, a.mixer_runs)
    measurement_points(parent_img, img, man, kit_sym)
    echo_checks(parent_img, img, man)
    report['result'] = 'FAIL' if fails else 'PASS'
    report['fails'] = fails
    (out / 'test_report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'{len(fails)} failure(s)' if fails else 'all checks passed')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
