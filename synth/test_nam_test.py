"""Checks for NAM test 1 (build_nam_test.py): the CPU meter as in IR diagnostic test 3, and the NAM amp and cabinet.

usage: python synth/test_nam_test.py OUT_DIR --kits KITS_MANIFEST --zig ZIG [--seeds N] [--blocks N] [--mixer-runs N]

OUT_DIR is the builder's output (manifest.json names the parent APP1); KITS_MANIFEST is the kit stage's
kits-manifest.json (arp_symbols), the kit stage v9.50 carries unchanged (kits-v9.46-test3); ZIG builds the host
reference of the NAM engine (the same source, C tiles, x86-64 with FMA). Both images are booted into Unicorn the way
their scatter loaders do it, with the same stubs. The meter's checks run on Unicorn's default CPU as IR diagnostic
test 3's did; everything that runs NAM runs on its Cortex-M7 model, which has the FPv5 instructions the engine
uses (VFMA, VMAXNM). Writes OUT_DIR/test_report.json.

1. Static: only the header, the five patch spans and the appended tail differ from the parent; the scatter table
   is the parent's rows plus the module row; the capture and the IR sit in the tail as the manifest says.
2-7. The meter, as IR diagnostic test 3 checked it: hook entries, the voice chain (and its negative control), the
   whole mixer (NAM off: TX and all memory as the parent's), the measurement points, the meter's arithmetic, the
   UI toggle. The readout's six lines and their widths in the popup font.
8. NAM, on the Cortex-M7 model, with the pool's get/release/query and the input FX/EXT SOURCE getters stubbed:
   - the UI takes the block (pool id, nt_block_bytes + 32, wait 0), aligns it, clears it and copies the capture and
     the IR into it, then hands it over; the audio task loads in three steps and prewarms in 100 (the state equals the
     engine's own nam_a2lite_prewarm);
   - RUN on TONE3000's golden input: the amp's output against the host reference engine, the cabinet's against a
     direct convolution, nt.out against the float output x 8192, and TX's add on DRY L/R only, once per block;
   - the FPU registers, FPSCR and the callee-saved registers are as they were after every step; the step runs on
     the block's own stack (its depth measured), the task's stack sees only nam_rx's frame;
   - the Gt Amp Sim gives the cabinet alone; hiding the readout stops NAM and the block goes back; a slow step stops
     it (SLOW) and the block goes back; a failed get shows MEM! and runs nothing; a damaged capture gives BAD;
   - through the whole mixer with NAM's block ready: the parent's TX plus exactly that block on DRY L/R;
   - diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui as the parent does.

Not a hardware test: no timing (instructions are counted as a proxy), no screen.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import random
import struct
import subprocess
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
BLOCK_RAW = TEST + 0x900004             # the pool block as the stubbed get returns it (not 32-aligned)
TCB = TEST + 0xE00000
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
CAPTURE, SYSPRM, SYS_GET, SETTINGS_OBJ, SET_GET = 0x202AD0A0, 0x82DFEED0, 0x800DA010, 0x82E01144, 0x800D94D8
POOL_ID, POOL_GET, POOL_RELEASE, POOL_QUERY, CUR_TASK = 0x80245820, 0x800D2F1E, 0x800D2F28, 0x000020A4, 0x202BBBFC
M_SHOWN = 4 * 47                                                                 # meter_t.shown
NT_OFF, NT_LOAD1, NT_LOAD2, NT_LOAD3, NT_WARM, NT_RUN, NT_BAD, NT_SLOW = range(8)
NT_NAMES = ('req mode blk raw mem_fail fx ext checked checks pool_free pool_largest pool_ok allocs '
            'frees state warm fresh').split()
NT_TAIL = ('peak rx tx steps task_attr last_mix w_n w_sum w_max w_tot seq p_blocks p_nam_avg p_nam_max p_tot_max '
           'tot_max_ever over slow_cycles hot reset_req reset_ack').split()
PREWARM = 6347
WARM_STEPS = 3 + -(-(PREWARM - 56) // 64)       # 8, 16 and 32 samples, then 64 a step: 102

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


def f32(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


class Machine:
    def __init__(self, image: bytes, symbols=None, m7=False):
        self.S = symbols or {}
        uc = self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        if m7:
            uc.ctl_set_cpu_model(ar.UC_CPU_ARM_CORTEX_M7)
        for base, size in REGIONS:
            uc.mem_map(base, size, UC_PROT_ALL)
        self.cyc, self.cyc_step, self.dwt_ctrl, self.dwt_writes = 0, 0, 1, []
        uc.mmio_map(0xE0001000, 0x1000, self._dwt_read, None, self._dwt_write, None)
        uc.mem_write(FLASH, image)
        # The stock copy (0x600800e4) and zero (0x60080100) handlers move 16-, 8- and 4-byte pieces: a row's last
        # size % 4 bytes are never written, so on the unit they keep whatever the SDRAM held (SY test 22: test 20 and
        # 21's note manager ended 2 bytes past a whole word, and its last instruction, b_start's bx lr, never arrived).
        # Here those bytes read as udf #254 (0xdefe), so code or data that needs them fails as it would on the unit.
        for load, dst, size, handler in scatter(image):
            whole, left = size & ~3, size & 3
            if handler == COPY:
                uc.mem_write(dst, image[load - FLASH:load - FLASH + whole])
            elif handler == DECOMPRESS:
                uc.mem_write(dst, decompress(image[load - FLASH:], size))
                left = 0
            elif handler == ZERO:
                uc.mem_write(dst, bytes(whole))
            else:
                raise ValueError(f'unknown scatter handler {handler:#x}')
            if left:
                uc.mem_write(dst + whole, (b'\xfe\xde' * 2)[:left])
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

    def floats(self, address, n):
        return list(struct.unpack(f'<{n}f', self.bytes(address, 4 * n)))

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
    """The meter_t fields by name (layout of nam_test.c, as cpu_meter.c)."""
    names = ('magic stamps t_mix0 t_v0 t_v1 t_sg0 t_sg1 nvox mix_ret sg_ret have_prev budget dwt_fixed '
             'w_n w_mix_sum w_mix_max w_vox_sum w_vox_max w_sg_sum w_sg_max w_voices '
             'w_per_n w_per_sum w_per_min w_per_max seq '
             'p_blocks p_mix_avg p_mix_max p_vox_avg p_vox_max p_sg_avg p_sg_max p_voices p_per_avg p_per_min p_per_max '
             'reset_req reset_ack total hi over mix_max_ever vox_max_ever sg_max_ever voices_max_ever windows '
             'shown hold hold_t0 posted_seq posted_at posts toggles').split()
    vals = struct.unpack(f'<{len(names)}I', m.bytes(sym, 4 * len(names)))
    return dict(zip(names, vals))


class Layout:
    """nt_t and nt_block_t offsets, from the module's nt_layout table."""
    def __init__(self, m, sym):
        v = struct.unpack('<19I', m.bytes(sym['nt_layout'], 76))
        (self.nt_bytes, self.state, self.out, self.peak, self.pub, self.tot_max_ever, self.reset_ack,
         self.b_weights, self.b_inst, self.b_state, self.b_cab, self.b_in, self.b_amp, self.b_out, self.b_stack,
         self.weights_bytes, self.inst_bytes, self.state_bytes, self.cab_bytes) = v
        check(self.state == 4 * len(NT_NAMES) - 12 and self.out == self.state + 12 and self.peak == self.out + 256 and
              self.reset_ack == self.peak + 4 * (len(NT_TAIL) - 1) and self.nt_bytes == self.reset_ack + 4,
              'nt_t layout as the test reads it')


def nt_state(m, sym, lay):
    head = dict(zip(NT_NAMES, struct.unpack(f'<{len(NT_NAMES)}I', m.bytes(sym['nt'], 4 * len(NT_NAMES)))))
    tail = dict(zip(NT_TAIL, struct.unpack(f'<{len(NT_TAIL)}I', m.bytes(sym['nt'] + lay.peak, 4 * len(NT_TAIL)))))
    head.update(tail)
    head['out'] = list(struct.unpack('<64i', m.bytes(sym['nt'] + lay.out, 256)))
    return head


# ---------------------------------------------------------------------------------------------
def static_checks(out, man, parent_img, img):
    check(sha(img) == man['sha256'] and len(img) == man['size'], 'APP1 matches the manifest')
    check(sha((out / 'SP404MKII_APP0.bin').read_bytes()) == man['app0_sha256'], 'APP0 is stock 5.52')
    rows_p, rows = scatter(parent_img), scatter(img)
    new_row = [FLASH + man['module_file_offset'], man['module_base'], man['module_size'], COPY]
    check(rows == rows_p + [new_row], 'scatter table = parent rows + the module row')
    module = img[man['module_file_offset']:man['module_file_offset'] + man['module_size']]
    check(sha(module) == man['module_sha256'] and man['module_base'] + man['module_size'] <= man['module_limit'],
          f"module bytes match the manifest and end below {man['module_limit']:#x}")
    a = man['assets']
    model = img[a['model']['file_offset']:a['model']['file_offset'] + a['model']['bytes']]
    ir = img[a['ir']['file_offset']:a['ir']['file_offset'] + a['ir']['bytes']]
    check(sha(model) == a['model']['sha256'] and sha(ir) == a['ir']['sha256'] and
          a['model']['flash'] == FLASH + a['model']['file_offset'] and a['ir']['flash'] == FLASH + a['ir']['file_offset'] and
          len(parent_img) <= a['model']['file_offset'] < a['ir']['file_offset'] < man['module_file_offset'],
          'the capture and the IR sit in the tail, before the module, as recorded')
    taps = struct.unpack(f"<{a['ir']['taps']}f", ir)
    check(all(math.isfinite(v) for v in taps) and max(abs(v) for v in taps) < 1.0, 'the IR is finite and below 1.0')
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
    report['static'] = dict(patches=[hex(p['address']) for p in man['patches']], module_size=man['module_size'],
                            fpu_instructions=man['fpu_instructions'], block_bytes=man['nt_block_bytes'])


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
    copied to ITCM/SDRAM, the module area, and the scratch stack below the caller."""
    spans = [(man['module_base'], man['module_limit']), (TEST, STACK), (0x60000000, 0x60400000)]
    spans += [(p['address'], p['address'] + p['size']) for p in man['patches']]
    if man.get('sytext'):                                # SY synth test 5: the screen's code, a copy row of its own
        spans.append((man['sytext']['address'], man['sytext']['address'] + man['sytext']['size']))
    for k in ('text', 'notes', 'data', 'more',           # SY synth test 11: the voice engine's code slots (24: more;
              'tone0', 'tone1', 'tone2'):                #   MIDI out test 4: the tones' table, three slots)
        if man.get('syv', {}).get(k):
            spans.append(tuple(man['syv'][k]['slot']))
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
    for _ in range(375):
        block(100000, 0, 0, 0, period=1200000)
    check(meter_state(m, S)['budget'] == 800000, 'implausible block length: budget back to 800,000')
    m.put(S + 4 * 37, meter_state(m, S)['reset_req'] + 1)
    block(100000, 0, 0, 0)
    st = meter_state(m, S)
    check(st['total'] == 1 and st['hi'] == 0 and st['over'] == 0 and st['mix_max_ever'] == 100000 and st['reset_ack'] == st['reset_req'],
          'switch-on reset clears HI, OVR and MAX at the next block')
    check(st['stamps'] == 15 and st['nvox'] == 0, 'stamps for slot 0, slot 31 and the SG span; empty slots render nothing')
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
    S, N = sym['meter'], sym['nt']
    lay = Layout(m, sym)
    m.cyc = 5
    m.call(sym['meter_mix_begin'], 0)                                 # initialise (budget 800k)

    def nt_put(**kw):
        for k, v in kw.items():
            if k in NT_NAMES:
                m.put(N + 4 * NT_NAMES.index(k), v, '<I')
            else:
                m.put(N + lay.peak + 4 * NT_TAIL.index(k), v, '<I')
    cases = {
        'idle': ((60000, 90000, 0, 0, 0, 0, 0, 800000, 800000, 800000), (375, 0, 0, 60000),
                 dict(state=NT_OFF, fx=0, peak=0, ext=1, mode=0, pool_ok=1, pool_free=2950 * 1024,
                      pool_largest=2900 * 1024, task_attr=0x1001, tot_max_ever=90000, over=0, mem_fail=0)),
        'typical': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (375, 248000, 272000, 600000),
                    dict(state=NT_RUN, fx=0, peak=16384, ext=1, mode=0, pool_ok=1, pool_free=2794 * 1024,
                         pool_largest=2744 * 1024, task_attr=0x1001, tot_max_ever=616000, over=0, mem_fail=0)),
        'cabinet': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (375, 24000, 26000, 354000),
                    dict(state=NT_RUN, fx=23, peak=8000, ext=0, mode=1, pool_ok=1, pool_free=2794 * 1024,
                         pool_largest=2744 * 1024, task_attr=0x1001, tot_max_ever=380000, over=0, mem_fail=0)),
        'worst': ((9999999, 9999999, 9999999, 9999999, 9999999, 9999999, 4000, 5000000, 0, 5000000),
                  (375, 9999999, 9999999, 9999999),
                  dict(state=NT_SLOW, fx=99, peak=32768, ext=1, mode=0, pool_ok=1, pool_free=0xFFFFFFFF,
                       pool_largest=0xFFFFFFFF, task_attr=0x1001, tot_max_ever=9999999, over=99999, mem_fail=1)),
    }
    texts = {}
    for name, (w, nw, ntv) in cases.items():
        m.put(S + 48, 1 if name == 'worst' else 0)              # dwt_fixed: CLK gets its '*'
        m.uc.mem_write(SCRATCH, struct.pack('<11I', 375, *w))
        m.uc.mem_write(SCRATCH + 0x80, struct.pack('<4I', *nw))
        nt_put(**ntv)
        m.call(sym['meter_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0x100)
        texts[name] = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    nt_put(state=NT_SLOW, slow_cycles=520000, mem_fail=0)
    m.call(sym['meter_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0x100)
    texts['slow'] = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    nt_put(pool_ok=0, mem_fail=0, state=NT_LOAD2)
    m.call(sym['meter_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0x100)
    texts['no pool'] = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    lines = {k: v.split('\n') for k, v in texts.items()}
    check(texts['typical'] == 'MIX 23/41 T75\nNAM 31/34 RUN\nIN0 LV50 X1\nPOOL 2794/2744\nMAX 77 F1\nCLK 600 OVR 0',
          f"typical readout reads {texts['typical']!r}")
    check(texts['idle'] == 'MIX 8/11 T8\nNAM 0/0 OFF\nIN0 LV0 X1\nPOOL 2950/2900\nMAX 11 F1\nCLK 600 OVR 0',
          f"idle readout reads {texts['idle']!r}")
    check(texts['cabinet'].startswith('MIX 23/41 T44\nCAB 3/3 RUN\nIN23 LV24 X0\n') and
          texts['worst'].split('\n')[1].endswith(' MEM!') and lines['no pool'][1].endswith(' LOAD') and
          lines['slow'][1] == 'NAM 99/99 SLOW' and lines['worst'][1] == 'NAM 99/99 MEM!' and
          lines['worst'][5] == 'CLK 999* OVR 999' and
          lines['no pool'][3] == 'POOL ?',
          f"cabinet, MEM!, LOAD and no-pool lines ({texts['cabinet']!r}, {lines['worst'][1]!r}, {lines['no pool']!r})")
    widest = max(sum(width(c) for c in ln) for v in lines.values() for ln in v)
    box_w, box_h = widest - 1 + 18, 6 * line - 1 + 8
    check(all(len(v) == 6 for v in lines.values()) and box_w <= 128 and box_h <= 64,
          f'worst-case readout fits the popup: widest line {widest} px -> box {box_w}x{box_h} (screen 128x64)')
    report['readout'] = dict(texts=texts, widest_line_px=widest, box=[box_w, box_h], line_px=line)


# ---------------------------------------------------------------------------------------------
def ui(img, man, head='MIX '):
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
    check(st['shown'] == 1 and st['posts'] == 1 and m.get(POPUP_PENDING) == 3 and first.startswith(head) and
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
    m.put(S + 4 * 25, st['seq'] + 2)
    st = tick(10)
    check(st['posts'] == 3, 'a new window: re-posted at once')
    built()
    m.uc.mem_write(POPUP_TEXT, b'Same EFX\non other BUS\0')
    st = tick(2 * second)
    check(st['posts'] == 3 and text() == 'Same EFX\non other BUS', 'a stock popup on screen: not covered')
    m.put(POPUP_SHOWN, 0, '<I')
    st = tick(10)
    check(st['posts'] == 4 and text().startswith(head), 'stock popup gone: the readout comes back')
    built()
    m.put(POPUP_PENDING, 3)
    m.put(S + 4 * 25, st['seq'] + 2)
    st = tick(2 * second)
    check(st['posts'] == 4, 'a stock post waiting to be built: not overwritten')
    m.put(POPUP_PENDING, -1)
    tick(10)
    built()
    keys(KEY_EXIT)
    tick()
    st = tick(second + 10)
    check(st['shown'] == 0 and closes == [1], 'EXIT held again: readout off, our popup closed')
    keys()
    st = tick(5 * second)
    posts_off = st['posts']
    check(m.get(POPUP_SHOWN, '<I') == 0, 'off: nothing re-posted')
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
    keys()
    tick()
    keys(0x05)
    tick()
    keys(0x05, KEY_EXIT)
    tick()
    st = tick(second + 10)
    check(st['shown'] == 1, 'a key already down before EXIT does not block the gesture')
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
REF_C = r'''
#include "nam_a2lite.h"
#include "namb_reader.h"
static nam_a2lite_weights_t w;
static nam_a2lite_t inst;
static nam_a2lite_state_t st;
__declspec(dllexport) int ref_open(const void *namb, int size) {
    namb_model_t m;
    if (namb_parse(namb, (size_t)size, &m) != NAMB_OK || namb_check_a2lite(&m) != NAMB_OK) return -1;
    if (nam_a2lite_load_weights(&w, m.weights, (int)m.weight_count)) return -2;
    nam_a2lite_init(&inst, &w, &st);
    nam_a2lite_prewarm(&inst);
    return 0;
}
__declspec(dllexport) void ref_process(const float *in, float *out, int n) {
    const float *i[1] = {in};
    float *o[1] = {out};
    nam_a2lite_process(&inst, i, o, n);
}
'''


def host_reference(zig: Path, out: Path, man):
    """The same engine source built for this PC (C tiles, FMA), to compare the module's amp against."""
    folder = out / 'test_build'
    folder.mkdir(parents=True, exist_ok=True)
    tp = Path(__file__).resolve().parent / 'namtest' / 'third_party' / 'tone3000-embedded'
    (folder / 'nam_ref.c').write_text(REF_C, encoding='ascii', newline='\n')
    dll = folder / 'nam_ref.dll'
    env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(folder / 'cache'), ZIG_LOCAL_CACHE_DIR=str(folder / 'cache'))
    subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu', '-shared', '-O2', '-mfma',
                    '-DNAM_A2LITE_MAX_BUFFER_SIZE=64', '-I', str(tp), str(tp / 'nam_a2lite.c'), str(tp / 'namb_reader.c'),
                    str(folder / 'nam_ref.c'), '-o', str(dll)], check=True, env=env)
    lib = ctypes.CDLL(str(dll))
    model = Path(man['assets']['model']['source']).read_bytes()
    buf = ctypes.create_string_buffer(model, len(model))
    if lib.ref_open(buf, len(model)) != 0:
        raise RuntimeError('host reference did not load the capture')
    lib._model_buf = buf

    def process(x):
        n = len(x)
        a = (ctypes.c_float * n)(*x)
        b = (ctypes.c_float * n)()
        lib.ref_process(a, b, n)
        return [float(v) for v in b]
    return process


def golden_input():
    tp = Path(__file__).resolve().parent / 'namtest' / 'third_party' / 'tone3000-embedded'
    src = tp / 'golden_input_head.raw'               # the first 4,096 samples of test/golden_input.raw
    if src.exists():
        data = src.read_bytes()
        return list(struct.unpack(f'<{len(data) // 4}f', data))
    rng = random.Random(48000)                     # a guitar-like stand-in: decaying partials and noise
    out = []
    for n in range(48000):
        t = n / 48000.0
        env = math.exp(-3 * (t % 0.5))
        out.append(0.5 * env * (math.sin(2 * math.pi * 110 * t) + 0.5 * math.sin(2 * math.pi * 220 * t) +
                                0.25 * math.sin(2 * math.pi * 330 * t)) / 1.75 + 0.01 * (rng.random() - 0.5))
    return out


class NamMachine(Machine):
    """The image on the Cortex-M7 model, with the pool and the getters stubbed."""
    def __init__(self, img, man, fx=0, ext=1, pool_fail=False):
        super().__init__(img, m7=True)
        self.man, self.sym = man, man['symbols']
        self.lay = Layout(self, self.sym)
        self.fx, self.ext, self.pool_fail = fx, ext, pool_fail
        self.gets, self.releases, self.queries, self.getters = [], [], 0, []
        self.put(POOL_ID, 1)
        self.put(CUR_TASK, TCB, '<I')
        self.put(TCB + 0x10, 0x1001, '<I')
        for a, fn in ((POOL_GET, self._get), (POOL_RELEASE, self._release), (POOL_QUERY, self._query),
                      (SYS_GET, self._getter), (SET_GET, self._getter)):
            self.uc.hook_add(UC_HOOK_CODE, fn, begin=a, end=a)
        self.uc.mem_write(BLOCK_RAW - 4, b'\xA5' * (man['nt_block_bytes'] + 64))   # the pool's leftovers

    def _ret(self, uc, value):
        uc.reg_write(ar.UC_ARM_REG_R0, value & 0xFFFFFFFF)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    def _get(self, uc, a, s, _):
        args = [uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(4)]
        self.gets.append(args)
        if self.pool_fail:
            self._ret(uc, -0x12)
            return
        uc.mem_write(args[2], struct.pack('<I', BLOCK_RAW))
        self._ret(uc, 0)

    def _release(self, uc, a, s, _):
        self.releases.append((uc.reg_read(ar.UC_ARM_REG_R0), uc.reg_read(ar.UC_ARM_REG_R1)))
        self._ret(uc, 0)

    def _query(self, uc, a, s, _):
        self.queries += 1
        uc.mem_write(uc.reg_read(ar.UC_ARM_REG_R1), struct.pack('<4I', 0, 0, 2900 * 1024, 2800 * 1024))
        self._ret(uc, 0)

    def _getter(self, uc, a, s, _):
        self.getters.append((a, uc.reg_read(ar.UC_ARM_REG_R0), uc.reg_read(ar.UC_ARM_REG_R1)))
        self._ret(uc, self.fx if a == SYS_GET else self.ext)

    @property
    def block(self):
        return (BLOCK_RAW + 31) & ~31

    def nt(self):
        return nt_state(self, self.sym, self.lay)

    def ui(self, shown, advance=60_000_001):
        self.put(self.sym['meter'] + M_SHOWN, shown)
        self.cyc += advance
        self.call(self.sym['nam_ui'])

    def capture(self, left, right=None):
        right = left if right is None else right
        self.uc.mem_write(CAPTURE, struct.pack('<128h', *[v for pair in zip(left, right) for v in pair]))

    def rx(self):
        self.call(self.sym['nam_rx'])
        return self.nt()


def run_to(m, state, limit=200):
    for _ in range(limit):
        if m.nt()['state'] == state:
            return True
        m.capture([0] * 64)
        m.rx()
    return m.nt()['state'] == state


def nam_checks(parent_img, img, man, zig, out):
    sym = man['symbols']
    a = man['assets']
    model = img[a['model']['file_offset']:a['model']['file_offset'] + a['model']['bytes']]
    ir_bytes = img[a['ir']['file_offset']:a['ir']['file_offset'] + a['ir']['bytes']]
    ir = list(struct.unpack(f"<{a['ir']['taps']}f", ir_bytes))
    m = NamMachine(img, man)
    lay, blk = m.lay, m.block
    # 1. Start: the UI takes the block and hands it over.
    m.ui(0)
    check(not m.gets and m.nt()['req'] == 0, 'readout hidden: no block taken')
    m.getters.clear()
    m.queries = 0
    m.ui(1)
    st = m.nt()
    want_size = man['nt_block_bytes'] + 32
    data = m.bytes(blk, man['nt_block_bytes'])
    sb = lay.b_state
    copies_ok = data[sb:sb + len(model)] == model and data[sb + 8192:sb + 8192 + len(ir_bytes)] == ir_bytes
    rest = data[:sb] + data[sb + len(model):sb + 8192] + data[sb + 8192 + len(ir_bytes):]
    check(m.gets == [[1, want_size, m.gets[0][2] if m.gets else 0, 0]] and st['req'] == 1 and st['blk'] == blk and
          st['raw'] == BLOCK_RAW and copies_ok and not any(rest) and st['allocs'] == 1,
          f'readout shown: one get (pool 1, {want_size} bytes, wait 0); the block aligned to 32, cleared, the '
          f'capture and the IR copied in, handed over')
    check(m.queries == 1 and st['pool_ok'] == 1 and st['pool_free'] == 2900 * 1024 and st['pool_largest'] == 2800 * 1024 and
          m.getters == [(SYS_GET, SYSPRM, 0x27C), (SET_GET, SETTINGS_OBJ, 0x25)] and st['mode'] == 0 and st['ext'] == 1,
          'every 0.1 s: the input FX, EXT SOURCE and the pool (free, largest piece)')
    # 2. Loading, one step a block, then 100 prewarm blocks.
    seen = []
    for _ in range(3):
        m.capture([0] * 64)
        seen.append(m.rx()['state'])
    check(seen == [NT_LOAD2, NT_LOAD3, NT_WARM], f'three loading steps: capture, cabinet, engine ({seen})')
    warm = 0
    while m.nt()['state'] == NT_WARM and warm < 200:
        m.capture([0] * 64)
        m.rx()
        warm += 1
    st = m.nt()
    check(warm == WARM_STEPS and st['state'] == NT_RUN and st['warm'] == PREWARM and st['fresh'] == 0,
          f'prewarm: {warm} blocks ({PREWARM} samples: 8, 16, 32, then 64 a block), then RUN')
    # The engine's own prewarm on a second machine gives the same instance and state.
    m2 = NamMachine(img, man)
    m2.ui(1)
    for _ in range(3):
        m2.capture([0] * 64)
        m2.rx()
    top = m2.block + lay.b_stack + 4096
    m2.call(sym['nam_fp_call'], sym['nam_a2lite_prewarm'] | 1, m2.block + lay.b_inst, top, limit=400_000_000)
    same = (m.bytes(blk + lay.b_inst, lay.inst_bytes) == m2.bytes(m2.block + lay.b_inst, lay.inst_bytes) and
            m.bytes(blk + lay.b_state, lay.state_bytes) == m2.bytes(m2.block + lay.b_state, lay.state_bytes))
    check(same, 'incremental prewarm = nam_a2lite_prewarm (instance and state byte for byte)')
    # 3. RUN on the golden input against the host reference and a direct convolution.
    ref = host_reference(zig, out, man)             # prewarmed as the module is
    gin = golden_input()
    blocks = 40
    errs_amp, errs_cab, ints_ok, fpu_ok, regs_ok, stack_depth, task_depth = 0.0, 0.0, True, True, True, 0, 0
    amp_all, out_all, in_all = [], [], []
    rng = random.Random(9)
    for b in range(blocks):
        x = gin[b * 64:(b + 1) * 64]
        s16 = [max(-32768, min(32767, round(v * 16384))) for v in x]
        m.capture(s16)
        xin = [(2 * v) / 65536.0 for v in s16]
        # FPU and callee-saved registers before, the stacks marked.
        pattern = [rng.getrandbits(32) for _ in range(32)]
        for k in range(32):
            m.uc.reg_write(getattr(ar, f'UC_ARM_REG_S{k}'), pattern[k])
        fpscr = 0x00400000 | (b & 1) * 0x9F                       # round towards +inf, some flags
        m.uc.reg_write(ar.UC_ARM_REG_FPSCR, fpscr)
        gpr = [rng.getrandbits(32) for _ in range(8)]
        for k, v in enumerate(gpr):
            m.uc.reg_write(getattr(ar, f'UC_ARM_REG_R{k + 4}'), v)
        m.uc.mem_write(blk + lay.b_stack, b'\xEE' * 4096)
        m.uc.mem_write(STACK - 0x800, b'\xEE' * 0x800)
        st = m.rx()
        fpu_ok &= [m.uc.reg_read(getattr(ar, f'UC_ARM_REG_S{k}')) for k in range(32)] == pattern and \
            m.uc.reg_read(ar.UC_ARM_REG_FPSCR) & 0xF7C0009F == fpscr & 0xF7C0009F
        regs_ok &= [m.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k + 4}')) for k in range(8)] == gpr
        stk = m.bytes(blk + lay.b_stack, 4096)
        stack_depth = max(stack_depth, 4096 - next(i for i in range(4096) if stk[i] != 0xEE))
        tsk = m.bytes(STACK - 0x800, 0x800)
        task_depth = max(task_depth, 0x800 - next((i for i in range(0x800) if tsk[i] != 0xEE), 0x800))
        amp = m.floats(blk + lay.b_amp, 64)
        y = m.floats(blk + lay.b_out, 64)
        amp_all += amp
        out_all += y
        in_all += xin
        want = ref(xin)
        errs_amp = max(errs_amp, max(abs(p - q) for p, q in zip(amp, want)))
        ints_ok &= st['out'] == [int(struct.unpack('<f', struct.pack('<f', v * 8192.0))[0]) for v in y] and st['fresh'] == 1
        # TX adds the block once.
        base = [rng.randint(-0x80000, 0x7FFFF) if rng.random() < 0.1 else rng.randint(-40000, 40000) for _ in range(1024)]
        m.uc.mem_write(TXBUF, struct.pack('<1024i', *base))
        m.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
        m.call(sym['nam_tx'], ARGS, 123456)
        got = list(struct.unpack('<1024i', m.bytes(TXBUF, 4096)))
        exp = list(base)
        for f in range(64):
            for w in (0, 1):
                exp[16 * f + w] = max(-0x80000, min(0x7FFFF, base[16 * f + w] + st['out'][f]))
        m.call(sym['nam_tx'], ARGS, 123456)
        again = list(struct.unpack('<1024i', m.bytes(TXBUF, 4096)))
        ints_ok &= got == exp and again == exp and m.nt()['fresh'] == 0 and m.nt()['last_mix'] == 123456
    for n in range(len(out_all)):
        acc = sum(ir[k] * amp_all[n - k] for k in range(min(len(ir), n + 1)))
        errs_cab = max(errs_cab, abs(out_all[n] - acc))
    peak_amp, peak_out = max(abs(v) for v in amp_all), max(abs(v) for v in out_all)
    check(errs_amp <= 1e-5 and peak_amp > 0.05,
          f'RUN, {blocks} blocks of the golden input: the amp = the host reference engine (max error {errs_amp:.2e}, '
          f'peak {peak_amp:.3f})')
    check(errs_cab <= 2e-5 and peak_out > 0.01,
          f'the cabinet = a direct convolution with the 1,024-tap IR (max error {errs_cab:.2e}, peak {peak_out:.3f})')
    check(ints_ok, 'nt.out = the float output x 8192 (truncated); TX adds it to DRY L/R only, clipped to 20 bits, once')
    check(fpu_ok and regs_ok, 's0-s31, FPSCR and r4-r11 as they were after every step')
    check(0 < stack_depth <= 2048 and task_depth <= 96,
          f'the step runs on the block\'s own stack ({stack_depth} of 4,096 bytes); the task\'s stack sees '
          f'{task_depth} bytes (nam_rx\'s frame)')
    # Instructions per RUN step (a proxy for cycles).
    counter = [0]

    def every(uc, a, s, _):
        counter[0] += 1
    h = m.uc.hook_add(UC_HOOK_CODE, every)
    m.capture([max(-32768, min(32767, round(v * 16384))) for v in gin[blocks * 64:(blocks + 1) * 64]])
    m.rx()
    m.uc.hook_del(h)
    run_instructions = counter[0]
    hist = amp_all + m.floats(blk + lay.b_amp, 64)            # everything the cabinet has taken in so far
    # 4. The Gt Amp Sim: the cabinet alone, on the input (its history still holds the amp's blocks).
    m.fx = 23
    m.ui(1)
    check(m.nt()['mode'] == 1, 'input FX = Gt Amp Sim (23): cabinet-only mode')
    ys, amp_before = [], m.bytes(blk + lay.b_amp, 256)
    for b in range(4):
        m.capture([rng.randint(-12000, 12000) for _ in range(64)])
        m.rx()
        hist += m.floats(blk + lay.b_in, 64)
        ys += m.floats(blk + lay.b_out, 64)
    start = len(hist) - len(ys)
    err = max(abs(ys[i] - sum(ir[k] * hist[start + i - k] for k in range(len(ir)))) for i in range(len(ys)))
    check(err <= 2e-5 and m.bytes(blk + lay.b_amp, 256) == amp_before,
          f'cabinet only: the input through the cabinet, the amp not run (max error {err:.2e} against the convolution '
          f'of everything the cabinet took in)')
    # 5. Stop: hiding the readout.
    m.fx = 0
    m.ui(0)
    st = m.nt()
    check(st['req'] == 0 and st['blk'] == blk and not m.releases, 'readout hidden: NAM asked to stop, the block kept')
    m.capture([0] * 64)
    st = m.rx()
    steps = st['steps']
    check(st['state'] == NT_OFF and st['fresh'] == 0, 'the audio task lets go at its next block (OFF)')
    m.ui(0)
    st = m.nt()
    check(m.releases == [(1, BLOCK_RAW)] and st['blk'] == 0 and st['frees'] == 1, 'then the UI gives the block back '
                                                                                    '(pool 1, the raw pointer)')
    m.capture([0] * 64)
    check(m.rx()['steps'] == steps, 'stopped: no more steps')
    # 6. Too slow: two wakes in a row over 9/10 of a block (mixer + NAM), or one step over 3/4, stop NAM; the block
    #    goes back while the readout still shows.
    m.ui(1)
    check(run_to(m, NT_RUN), 'shown again: back to RUN')
    hot = []
    for mix, step in ((300_000, 450_000), (300_000, 300_000), (300_000, 450_000), (300_000, 450_000)):
        m.call(sym['nam_tx'], ARGS, mix)
        m.cyc_step = step                                     # each cycle-counter read moves on: a step of `step`
        m.capture([1000] * 64)
        st = m.rx()
        m.cyc_step = 0
        hot.append((st['state'], st['hot']))
    check(hot == [(NT_RUN, 1), (NT_RUN, 0), (NT_RUN, 1), (NT_SLOW, 2)] and st['slow_cycles'] == 750_000 and
          st['fresh'] == 0, f'mixer + NAM over 9/10 of the block twice in a row (750k > 720k): SLOW; once, then a '
                            f'cooler wake: RUN on ({hot})')
    m.ui(0)
    m.capture([0] * 64)
    m.rx()
    m.ui(0)
    m.ui(1)
    check(run_to(m, NT_RUN), 'hidden and shown again: back to RUN')
    m.cyc_step = 650_000
    m.capture([1000] * 64)
    st = m.rx()
    check(st['state'] == NT_RUN and st['hot'] == 0, 'one 650k step (81% of the block) alone: still RUN')
    m.cyc_step = 850_000
    m.capture([1000] * 64)
    st = m.rx()
    m.cyc_step = 0
    pub = struct.unpack('<4I', m.bytes(sym['nt'] + lay.pub, 16))
    check(st['state'] == NT_SLOW and st['slow_cycles'] == 850_000 and st['fresh'] == 0 and pub[2] == 850_000,
          'one step over the whole 800,000-cycle block (850k): SLOW at once, nothing for TX; the window so far '
          'published (its peak is that step)')
    steps = st['steps']
    m.ui(1)
    st = m.nt()
    check(len(m.releases) == 3 and st['blk'] == 0 and st['req'] == 1, 'SLOW: the UI gives the block back at once')
    m.capture([0] * 64)
    check(m.rx()['steps'] == steps and m.nt()['state'] == NT_SLOW, 'SLOW stays until the readout is hidden')
    m.ui(0)
    m.capture([0] * 64)
    check(m.rx()['state'] == NT_OFF, 'hidden: OFF again')
    # 7. No memory: MEM!, nothing runs; hiding clears it.
    m3 = NamMachine(img, man, pool_fail=True)
    m3.ui(1)
    st = m3.nt()
    m3.capture([0] * 64)
    st2 = m3.rx()
    check(st['mem_fail'] == 1 and st['req'] == 0 and st['blk'] == 0 and len(m3.gets) == 1 and st2['steps'] == 0,
          'a failed get: MEM!, nothing handed over, no step runs')
    m3.ui(1)
    check(len(m3.gets) == 1, 'MEM! is not retried while the readout stays')
    m3.ui(0)
    check(m3.nt()['mem_fail'] == 0, 'hiding the readout clears MEM!')
    # 8. A damaged capture: BAD, and the block goes back.
    m4 = NamMachine(img, man)
    m4.ui(1)
    at = m4.block + lay.b_state + 200
    m4.uc.mem_write(at, bytes([m4.bytes(at, 1)[0] ^ 0x40]))
    m4.capture([0] * 64)
    st = m4.rx()
    m4.ui(1)
    check(st['state'] == NT_BAD and m4.releases == [(1, BLOCK_RAW)], 'a damaged capture (CRC): BAD, the block back')
    # 9. Through the whole mixer, with a block ready: the parent's TX plus exactly that block on DRY L/R.
    mp = Machine(parent_img)
    mm = NamMachine(img, man)
    for x in (mp, mm):
        make_voices(x, 9090, occupancy=0.5)
        x.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    mm.ui(1)
    run_to(mm, NT_RUN)
    mism, loud = [], 0
    for n in range(4):
        mm.capture([rng.randint(-20000, 20000) for _ in range(64)])
        blk_out = mm.rx()['out']
        outs = []
        for x in (mp, mm):
            x.uc.mem_write(TXBUF, bytes(0x3000))
            x.call(MIXER, ARGS)
            outs.append(list(struct.unpack('<1024i', x.bytes(TXBUF, 4096))) + [x.bytes(TXBUF + 0x1000, 0x2000)])
        want = outs[0][:1024]
        for f in range(64):
            for w in (0, 1):
                want[16 * f + w] = max(-0x80000, min(0x7FFFF, want[16 * f + w] + blk_out[f]))
        loud += any(outs[0][:1024]) and any(blk_out)
        if outs[1][:1024] != want or outs[1][1024] != outs[0][1024]:
            mism.append(n)
    check(not mism and loud, 'whole mixer with NAM\'s block ready: TX line 3 = the parent\'s + the block on DRY L/R, '
                             'the other words and lines 1/2 the parent\'s (4 blocks)')
    # 10. diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui (NAM off: same memory as the parent).
    bb = man['bounce_bridges']
    for label, ours, theirs in (('diag_rx', sym['diag_rx'], bb['bnc_rx']), ('diag_ui', sym['diag_ui'], bb['bnc_ui'])):
        res = []
        cap = struct.pack('<128h', *[rng.randint(-20000, 20000) for _ in range(128)])
        for image, fn in ((parent_img, theirs), (img, ours)):
            x = Machine(image)
            x.uc.mem_write(CAPTURE, cap)
            for _ in range(3):
                x.call(fn, 1)
            res.append((x.digest(skip_spans(man)), x.log))
        check(res[0] == res[1], f"{label}: bounce's own {'bnc_rx' if label == 'diag_rx' else 'bnc_ui'} runs as in the "
                                f"parent (all memory but the module)")
    report['nam'] = dict(warm_blocks=warm, run_blocks=blocks, amp_max_error=errs_amp, cabinet_max_error=errs_cab,
                         amp_peak=peak_amp, out_peak=peak_out, private_stack_bytes=stack_depth,
                         task_stack_bytes=task_depth, run_step_instructions=run_instructions,
                         run_step_percent_at_one_cycle=round(run_instructions / 8000, 1),
                         note='instructions, not cycles: TONE3000 measured 4,059 cycles a sample (259,776 a 64-frame '
                              'block) on a 480 MHz Daisy Seed with code in ITCM; here code and data are in SDRAM')


# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--kits', type=Path, required=True, help="the kit stage's kits-manifest.json (arp_symbols)")
    ap.add_argument('--zig', type=Path, required=True)
    ap.add_argument('--seeds', type=int, default=12)
    ap.add_argument('--blocks', type=int, default=6)
    ap.add_argument('--mixer-runs', type=int, default=4)
    ap.add_argument('--only', help='comma-separated: static,nam,meter (default all)')
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
    only = set((a.only or 'static,nam,meter').split(','))
    if 'static' in only:
        static_checks(out, man, parent_img, img)
    if 'nam' in only:
        nam_checks(parent_img, img, man, a.zig.resolve(), out)
    if 'meter' not in only:
        only = None
    if only:
        entry_checks(parent_img, img, sym)
        arithmetic(img, man)
        readout(img, man)
        ui(img, man)
        voice_chain(parent_img, img, man, a.seeds)
        voice_chain(parent_img, img, man, 2, sabotage=True)
        whole_mixer(parent_img, img, man, kit_sym, a.blocks, a.mixer_runs)
        measurement_points(parent_img, img, man, kit_sym)
    report['result'] = 'FAIL' if fails else 'PASS'
    report['fails'] = fails
    (out / 'test_report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'{len(fails)} failure(s)' if fails else 'all checks passed')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
