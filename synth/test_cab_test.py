"""Checks for cabinet test 2 (build_cab_test.py): the CPU meter as in IR diagnostic test 3, and the cabinet.

usage: python synth/test_cab_test.py OUT_DIR --kits KITS_MANIFEST [--seeds N] [--blocks N] [--mixer-runs N] [--only ...]

The meter's checks are NAM test 2's (test_nam_test.py, imported: the same hooks, the same meter_t), run on this
image: hook entries, the voice chain and its negative control, the whole mixer with the cabinet off (TX and all
memory as the parent's), the measurement points, the meter's arithmetic, the UI toggle. On top of them:

1. Static: only the header, the five patch spans and the appended tail differ from the parent; the scatter table is
   the parent's rows plus the module row; the IR sits in the tail as the manifest says.
2. The readout's six lines and their widths in the popup font.
3. The cabinet, on Unicorn's Cortex-M7 model, with the input FX/EXT SOURCE getters stubbed:
   - the UI clears the cabinet and copies the IR in, then hands it over; one loading step, then RUN;
   - RUN on random captures: the output equals a direct convolution with the IR; ct.out = the output x 16384
     (truncated); TX adds it to DRY L/R only, once per block;
   - the FPU registers, FPSCR and the callee-saved registers are as they were after every step; the step runs on the
     module's own stack (its depth measured), the task's stack sees only cab_rx's frame;
   - hiding the readout stops it, showing it again starts afresh; the SLOW rules; a damaged IR gives BAD;
   - through the whole mixer with a block ready: the parent's TX plus exactly that block on DRY L/R;
   - diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui as the parent does.

Not a hardware test: no timing (instructions are counted as a proxy), no screen.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import struct
import sys
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn import arm_const as ar

import test_nam_test as base
from test_nam_test import (Machine, check, sha, scatter, FLASH, COPY, STACK, SCRATCH, TXBUF, ARGS, MIXER, CAPTURE,
                           SYSPRM, SYS_GET, SETTINGS_OBJ, SET_GET, CUR_TASK, TCB, M_SHOWN, make_voices, skip_spans)

CT_OFF, CT_LOAD, CT_RUN, CT_BAD, CT_SLOW = range(5)
CT_NAMES = 'req fx ext checked checks starts state fresh'.split()
CT_TAIL = ('peak rx tx steps task_attr last_mix w_n w_sum w_max w_tot seq p_blocks p_cab_avg p_cab_max p_tot_max '
           'tot_max_ever over slow_cycles hot reset_req reset_ack').split()
report = base.report


class Layout:
    """ct_t and ct_block_t offsets, from the module's ct_layout table."""
    def __init__(self, m, sym):
        v = struct.unpack('<15I', m.bytes(sym['ct_layout'], 60))
        (self.ct_bytes, self.state, self.out, self.peak, self.pub, self.tot_max_ever, self.reset_ack,
         self.block_bytes, self.b_cab, self.b_ir, self.b_in, self.b_out, self.b_stack, self.cab_bytes,
         self.pair_peak) = v
        check(self.state == 4 * (len(CT_NAMES) - 2) and self.out == self.state + 8 and self.peak == self.out + 256 and
              self.reset_ack == self.peak + 4 * (len(CT_TAIL) - 1) and self.pair_peak == self.reset_ack + 4 and
              self.ct_bytes == self.pair_peak + 32, 'ct_t layout as the test reads it')


def ct_state(m, sym, lay):
    head = dict(zip(CT_NAMES, struct.unpack(f'<{len(CT_NAMES)}I', m.bytes(sym['ct'], 4 * len(CT_NAMES)))))
    head.update(zip(CT_TAIL, struct.unpack(f'<{len(CT_TAIL)}I', m.bytes(sym['ct'] + lay.peak, 4 * len(CT_TAIL)))))
    head['out'] = list(struct.unpack('<64i', m.bytes(sym['ct'] + lay.out, 256)))
    head['pairs'] = list(struct.unpack('<8I', m.bytes(sym['ct'] + lay.pair_peak, 32)))
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
    a = man['assets']['ir']
    ir = img[a['file_offset']:a['file_offset'] + a['bytes']]
    taps = struct.unpack(f"<{a['taps']}f", ir)
    check(sha(ir) == a['sha256'] and a['flash'] == FLASH + a['file_offset'] and
          len(parent_img) <= a['file_offset'] < man['module_file_offset'] and
          all(math.isfinite(v) for v in taps) and max(abs(v) for v in taps) < 1.0,
          'the IR sits in the tail, before the module, as recorded; finite, below 1.0')
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
                            fpu_instructions=man['fpu_instructions'], block_bytes=man['ct_block_bytes'])


# ---------------------------------------------------------------------------------------------
def readout(img, man):
    sym = man['symbols']
    width, line = base.font_widths(img)
    m = Machine(img)
    S, C = sym['meter'], sym['ct']
    lay = Layout(m, sym)
    m.cyc = 5
    m.call(sym['meter_mix_begin'], 0)                                 # initialise (budget 800k)

    def ct_put(**kw):
        for k, v in kw.items():
            if k == 'pairs':
                m.uc.mem_write(C + lay.pair_peak, struct.pack('<8I', *v))
            elif k in CT_NAMES:
                m.put(C + 4 * CT_NAMES.index(k), v, '<I')
            else:
                m.put(C + lay.peak + 4 * CT_TAIL.index(k), v, '<I')
    cases = {
        'idle': ((60000, 90000, 0, 0, 0, 0, 0, 800000, 800000, 800000), (375, 0, 0, 60000),
                 dict(state=CT_OFF, fx=0, peak=0, ext=1, task_attr=0x1001, tot_max_ever=90000, over=0,
                      pairs=[0] * 8)),
        'typical': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (75, 32000, 40000, 360000),
                    dict(state=CT_RUN, fx=23, peak=16384, ext=1, task_attr=0x1001, tot_max_ever=368000, over=0,
                         pairs=[0, 16384, 0, 3277, 0, 0, 32767, 100])),
        'worst': ((9999999, 9999999, 9999999, 9999999, 9999999, 9999999, 4000, 5000000, 0, 5000000),
                  (75, 9999999, 9999999, 9999999),
                  dict(state=CT_SLOW, fx=99, peak=32768, ext=0, task_attr=0x1001, tot_max_ever=9999999, over=99999,
                       pairs=[32768] * 8)),
    }
    texts = {}
    for name, (w, cw, ctv) in cases.items():
        m.put(S + 48, 1 if name == 'worst' else 0)                    # dwt_fixed: CLK gets its '*'
        m.uc.mem_write(SCRATCH, struct.pack('<11I', 375, *w))
        m.uc.mem_write(SCRATCH + 0x80, struct.pack('<4I', *cw))
        ct_put(**ctv)
        m.call(sym['meter_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0x100)
        texts[name] = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    lines = {k: v.split('\n') for k, v in texts.items()}
    check(texts['typical'] == 'CAB 4/5 RUN\nIN23 LV50 X1\nA 0 50 0 10\nB 0 0 99 0\nMIX 23/41 T45\nMAX 46 OVR 0',
          f"typical readout reads {texts['typical']!r}")
    check(texts['idle'] == 'CAB 0/0 OFF\nIN0 LV0 X1\nA 0 0 0 0\nB 0 0 0 0\nMIX 8/11 T8\nMAX 11 OVR 0',
          f"idle readout reads {texts['idle']!r}")
    check(lines['worst'][0] == 'CAB 99/99 SLOW' and lines['worst'][2] == 'A 99 99 99 99' and
          lines['worst'][5] == 'MAX 999 OVR 999', f"worst-case lines read {lines['worst']!r}")
    widest = max(sum(width(c) for c in ln) for v in lines.values() for ln in v)
    box_w, box_h = widest - 1 + 18, 6 * line - 1 + 8
    check(all(len(v) == 6 for v in lines.values()) and box_w <= 128 and box_h <= 64,
          f'worst-case readout fits the popup: widest line {widest} px -> box {box_w}x{box_h} (screen 128x64)')
    report['readout'] = dict(texts=texts, widest_line_px=widest, box=[box_w, box_h], line_px=line)


# ---------------------------------------------------------------------------------------------
class CabMachine(Machine):
    """The image on the Cortex-M7 model, with the input FX and EXT SOURCE getters stubbed."""
    def __init__(self, img, man, fx=23, ext=1):
        super().__init__(img, m7=True)
        self.man, self.sym = man, man['symbols']
        self.lay = Layout(self, self.sym)
        self.fx, self.ext, self.getters = fx, ext, []
        self.put(CUR_TASK, TCB, '<I')
        self.put(TCB + 0x10, 0x1001, '<I')
        for a in (SYS_GET, SET_GET):
            self.uc.hook_add(UC_HOOK_CODE, self._getter, begin=a, end=a)

    def _getter(self, uc, a, s, _):
        self.getters.append((a, uc.reg_read(ar.UC_ARM_REG_R0), uc.reg_read(ar.UC_ARM_REG_R1)))
        uc.reg_write(ar.UC_ARM_REG_R0, (self.fx if a == SYS_GET else self.ext) & 0xFFFFFFFF)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    @property
    def block(self):
        return self.sym['ct_block']

    def ct(self):
        return ct_state(self, self.sym, self.lay)

    def ui(self, shown, advance=60_000_001):
        self.put(self.sym['meter'] + M_SHOWN, shown)
        self.cyc += advance
        self.call(self.sym['cab_ui'])

    def capture(self, left, right=None):
        right = left if right is None else right
        self.uc.mem_write(CAPTURE, struct.pack('<128h', *[v for pair in zip(left, right) for v in pair]))

    def rx(self):
        self.call(self.sym['cab_rx'])
        return self.ct()


def cab_checks(parent_img, img, man):
    sym = man['symbols']
    a = man['assets']['ir']
    ir_bytes = img[a['file_offset']:a['file_offset'] + a['bytes']]
    ir = list(struct.unpack(f"<{a['taps']}f", ir_bytes))
    m = CabMachine(img, man)
    lay, blk = m.lay, m.block
    rng = random.Random(1024)
    # 1. Start: the UI clears the cabinet, copies the IR in and hands it over.
    m.uc.mem_write(blk + lay.b_cab, b'\xA5' * lay.cab_bytes)              # leftovers of an earlier run
    m.ui(0)
    check(m.ct()['req'] == 0 and m.ct()['starts'] == 0, 'readout hidden: nothing started')
    m.getters.clear()
    m.ui(1)
    st = m.ct()
    check(st['req'] == 1 and st['starts'] == 1 and not any(m.bytes(blk + lay.b_cab, lay.cab_bytes)) and
          m.bytes(blk + lay.b_ir, len(ir_bytes)) == ir_bytes,
          'readout shown: the cabinet cleared, the IR copied in from flash, handed over')
    check(m.getters == [(SYS_GET, SYSPRM, 0x27C), (SET_GET, SETTINGS_OBJ, 0x25)] and st['fx'] == 23 and st['ext'] == 1,
          'every 0.1 s: the input FX and EXT SOURCE')
    m.capture([0] * 64)
    st = m.rx()
    check(st['state'] == CT_RUN and st['steps'] == 1 and st['fresh'] == 0, 'one loading step (the IR\'s transform), '
                                                                           'then RUN')
    # 2. RUN: the convolution, the output words, TX's add; registers and stacks.
    xs, ys, ints_ok, fpu_ok, regs_ok, stack_depth, task_depth = [], [], True, True, True, 0, 0
    blocks = 24
    for b in range(blocks):
        s16 = [max(-32768, min(32767, int(20000 * math.sin(2 * math.pi * (b * 64 + i) / 97.0)) + rng.randint(-4000, 4000)))
               for i in range(64)]
        m.capture(s16)
        pattern = [rng.getrandbits(32) for _ in range(32)]
        for k in range(32):
            m.uc.reg_write(getattr(ar, f'UC_ARM_REG_S{k}'), pattern[k])
        fpscr = 0x00400000 | (b & 1) * 0x9F
        m.uc.reg_write(ar.UC_ARM_REG_FPSCR, fpscr)
        gpr = [rng.getrandbits(32) for _ in range(8)]
        for k, v in enumerate(gpr):
            m.uc.reg_write(getattr(ar, f'UC_ARM_REG_R{k + 4}'), v)
        m.uc.mem_write(blk + lay.b_stack, b'\xEE' * 2048)
        m.uc.mem_write(STACK - 0x800, b'\xEE' * 0x800)
        st = m.rx()
        fpu_ok &= [m.uc.reg_read(getattr(ar, f'UC_ARM_REG_S{k}')) for k in range(32)] == pattern and \
            m.uc.reg_read(ar.UC_ARM_REG_FPSCR) & 0xF7C0009F == fpscr & 0xF7C0009F
        regs_ok &= [m.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k + 4}')) for k in range(8)] == gpr
        stk = m.bytes(blk + lay.b_stack, 2048)
        stack_depth = max(stack_depth, 2048 - next(i for i in range(2048) if stk[i] != 0xEE))
        tsk = m.bytes(STACK - 0x800, 0x800)
        task_depth = max(task_depth, 0x800 - next((i for i in range(0x800) if tsk[i] != 0xEE), 0x800))
        xs += [(2 * v) / 65536.0 for v in s16]
        y = m.floats(blk + lay.b_out, 64)
        ys += y
        ints_ok &= st['out'] == [int(struct.unpack('<f', struct.pack('<f', v * 16384.0))[0]) for v in y] and st['fresh'] == 1
        basew = [rng.randint(-0x80000, 0x7FFFF) if rng.random() < 0.1 else rng.randint(-40000, 40000) for _ in range(1024)]
        m.uc.mem_write(TXBUF, struct.pack('<1024i', *basew))
        m.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
        m.call(sym['cab_tx'], ARGS, 123456)
        got = list(struct.unpack('<1024i', m.bytes(TXBUF, 4096)))
        exp = list(basew)
        for f in range(64):
            for w in (0, 1):
                exp[16 * f + w] = max(-0x80000, min(0x7FFFF, basew[16 * f + w] + st['out'][f]))
        m.call(sym['cab_tx'], ARGS, 123456)
        again = list(struct.unpack('<1024i', m.bytes(TXBUF, 4096)))
        ints_ok &= got == exp and again == exp and m.ct()['fresh'] == 0 and m.ct()['last_mix'] == 123456
    err = max(abs(ys[n] - sum(ir[k] * xs[n - k] for k in range(min(len(ir), n + 1)))) for n in range(len(ys)))
    peak = max(abs(v) for v in ys)
    check(err <= 2e-5 and peak > 0.05, f'RUN, {blocks} blocks: the output = a direct convolution with the '
                                       f'{len(ir)}-tap IR (max error {err:.2e}, peak {peak:.3f})')
    check(ints_ok, 'ct.out = the output x 16384 (truncated); TX adds it to DRY L/R only, clipped to 20 bits, once')
    check(fpu_ok and regs_ok, 's0-s31, FPSCR and r4-r11 as they were after every step')
    check(0 < stack_depth <= 1536 and task_depth <= 96,
          f'the step runs on the module\'s own stack ({stack_depth} of 2,048 bytes); the task\'s stack sees '
          f'{task_depth} bytes (cab_rx\'s frame)')
    counter = [0]

    def every(uc, a_, s_, _):
        counter[0] += 1
    h = m.uc.hook_add(UC_HOOK_CODE, every)
    m.capture([rng.randint(-20000, 20000) for _ in range(64)])
    m.rx()
    m.uc.hook_del(h)
    run_instructions = counter[0]
    # 3. Stop; start again afresh.
    m.ui(0)
    m.capture([0] * 64)
    st = m.rx()
    steps = st['steps']
    check(st['req'] == 0 and st['state'] == CT_OFF and st['fresh'] == 0, 'readout hidden: the cabinet stops (OFF)')
    m.capture([0] * 64)
    check(m.rx()['steps'] == steps, 'stopped: no more steps')
    m.ui(1)
    m.capture([0] * 64)
    st = m.rx()
    x2 = [rng.randint(-20000, 20000) for _ in range(64)]
    m.capture(x2)
    m.rx()
    y2 = m.floats(blk + lay.b_out, 64)
    xin = [(2 * v) / 65536.0 for v in x2]
    err2 = max(abs(y2[n] - sum(ir[k] * xin[n - k] for k in range(n + 1))) for n in range(64))
    check(st['state'] == CT_RUN and m.ct()['starts'] == 2 and err2 <= 2e-5,
          f'shown again: cleared, loaded, and the first block convolves from silence (max error {err2:.2e})')
    # 4. SLOW: two wakes in a row over 9/10 (mixer + cabinet), or one step over the whole block.
    hot = []
    for mix, step in ((300_000, 450_000), (300_000, 300_000), (300_000, 450_000), (300_000, 450_000)):
        m.call(sym['cab_tx'], ARGS, mix)
        m.cyc_step = step
        m.capture([1000] * 64)
        st = m.rx()
        m.cyc_step = 0
        hot.append((st['state'], st['hot']))
    check(hot == [(CT_RUN, 1), (CT_RUN, 0), (CT_RUN, 1), (CT_SLOW, 2)] and st['slow_cycles'] == 750_000 and
          st['fresh'] == 0, f'mixer + cabinet over 9/10 of the block twice in a row: SLOW; once, then a cooler wake: '
                            f'RUN on ({hot})')
    m.capture([0] * 64)
    steps = m.rx()['steps']
    m.capture([0] * 64)
    check(m.rx()['steps'] == steps and m.ct()['state'] == CT_SLOW, 'SLOW stays until the readout is hidden')
    m.ui(0)
    m.capture([0] * 64)
    m.rx()
    m.ui(1)
    m.capture([0] * 64)
    m.rx()
    m.cyc_step = 850_000
    m.capture([1000] * 64)
    st = m.rx()
    m.cyc_step = 0
    pub = struct.unpack('<4I', m.bytes(sym['ct'] + lay.pub, 16))
    check(st['state'] == CT_SLOW and st['slow_cycles'] == 850_000 and pub[2] == 850_000,
          'one step over the whole 800,000-cycle block: SLOW at once; the window so far published')
    # 5. A damaged IR: BAD.
    m2 = CabMachine(img, man)
    m2.ui(1)
    m2.put(m2.block + m2.lay.b_ir + 40, 0x7FC00000, '<I')                 # a NaN tap
    m2.capture([0] * 64)
    st = m2.rx()
    m2.capture([0] * 64)
    check(st['state'] == CT_BAD and m2.rx()['steps'] == 1, 'a non-finite tap: BAD, and nothing more runs')
    # 6. Through the whole mixer with a block ready: the parent's TX plus exactly that block on DRY L/R.
    mp = Machine(parent_img)
    mm = CabMachine(img, man)
    for x in (mp, mm):
        make_voices(x, 9090, occupancy=0.5)
        x.uc.mem_write(ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    mm.ui(1)
    mm.capture([0] * 64)
    mm.rx()
    mism, loud = [], 0
    for n in range(4):
        mm.capture([rng.randint(-20000, 20000) for _ in range(64)])
        out = mm.rx()['out']
        outs = []
        for x in (mp, mm):
            x.uc.mem_write(TXBUF, bytes(0x3000))
            x.call(MIXER, ARGS)
            outs.append(list(struct.unpack('<1024i', x.bytes(TXBUF, 4096))) + [x.bytes(TXBUF + 0x1000, 0x2000)])
        want = outs[0][:1024]
        for f in range(64):
            for w in (0, 1):
                want[16 * f + w] = max(-0x80000, min(0x7FFFF, want[16 * f + w] + out[f]))
        loud += any(outs[0][:1024]) and any(out)
        if outs[1][:1024] != want or outs[1][1024] != outs[0][1024]:
            mism.append(n)
    check(not mism and loud, 'whole mixer with the cabinet\'s block ready: TX line 3 = the parent\'s + the block on DRY '
                             'L/R, the other words and lines 1/2 the parent\'s (4 blocks)')
    # 7. The RX pairs' peaks. The audio task's RX site leaves this block's bank in [r6 + 4] and the banks' base in r9
    #    (guarded by the builder; bounce's bridge and the stock feed keep r6 and r9), so diag_rx is entered here with
    #    them as the site leaves them (the feed's own consumers need the whole system, which this harness has not):
    #    the packet is r9 + bank << 11, each pair's peak its own; the readout's refresh clears them.
    mq = CabMachine(img, man)
    rxbase, task = TXBUF + 0x4000, SCRATCH + 0x800
    amps = [0, 20000, 0, 3000, 0, 0, 32767, 100]
    packet = []
    for f in range(64):
        for k in range(8):
            for c in range(2):
                v = amps[k] if (f + c) % 2 else -amps[k]
                packet.append(max(-32768, min(32767, v)))
    mq.uc.mem_write(rxbase, b'\x55' * 0x800)                            # bank 0: not this block's
    mq.uc.mem_write(rxbase + 0x800, struct.pack('<1024h', *packet))     # bank 1: this block's
    mq.put(task + 4, 1, '<I')                                           # the RX site stored this block's bank: 1
    mq.uc.reg_write(ar.UC_ARM_REG_R6, task)
    mq.uc.reg_write(ar.UC_ARM_REG_R9, rxbase)
    mq.call(sym['diag_rx'])
    st = mq.ct()
    check(st['pairs'] == [min(a, 32767) for a in amps] and mq.uc.reg_read(ar.UC_ARM_REG_R6) == task and
          mq.uc.reg_read(ar.UC_ARM_REG_R9) == rxbase,
          f"diag_rx with r6/r9 as the RX site leaves them: every pair's peak from this block's packet, not the other "
          f"bank's ({st['pairs']}); r6 and r9 kept")
    mq.put(sym['meter'] + M_SHOWN, 1)
    mq.call(sym['meter_mix_begin'], 0)
    mq.call(sym['meter_mix_end'])
    mq.put(base.PAGE, 1, '<h')
    mq.put(base.POPUP_PENDING, -1)
    mq.cyc += 600_000_001
    mq.call(sym['meter_ui_tick'], 1)
    text = mq.bytes(base.POPUP_TEXT, 0x80).split(b'\0')[0].decode('latin-1')
    check('\nA 0 61 0 9\nB 0 0 99 0\n' in text and mq.ct()['pairs'] == [0] * 8,
          f'the readout shows them and its refresh clears them ({text!r})')
    # 8. diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui (the cabinet off: same memory as the parent).
    bb = man['bounce_bridges']
    for label, ours, theirs in (('diag_rx', sym['diag_rx'], bb['bnc_rx']), ('diag_ui', sym['diag_ui'], bb['bnc_ui'])):
        res = []
        cap = struct.pack('<128h', *[rng.randint(-20000, 20000) for _ in range(128)])
        for image, fn in ((parent_img, theirs), (img, ours)):
            x = Machine(image)
            x.uc.mem_write(CAPTURE, cap)
            x.put(SCRATCH + 0x804, 1, '<I')
            x.uc.reg_write(ar.UC_ARM_REG_R6, SCRATCH + 0x800)
            x.uc.reg_write(ar.UC_ARM_REG_R9, TXBUF + 0x4000)
            for _ in range(3):
                x.call(fn, 1)
            res.append((x.digest(skip_spans(man)), x.log))
        check(res[0] == res[1], f"{label}: bounce's own {'bnc_rx' if label == 'diag_rx' else 'bnc_ui'} runs as in the "
                                f"parent (all memory but the module)")
    report['cab'] = dict(run_blocks=blocks, max_error=err, out_peak=peak, private_stack_bytes=stack_depth,
                         task_stack_bytes=task_depth, run_step_instructions=run_instructions,
                         run_step_percent_at_one_cycle=round(run_instructions / 8000, 1))


# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--kits', type=Path, required=True, help="the kit stage's kits-manifest.json (arp_symbols)")
    ap.add_argument('--seeds', type=int, default=12)
    ap.add_argument('--blocks', type=int, default=6)
    ap.add_argument('--mixer-runs', type=int, default=4)
    ap.add_argument('--only', help='comma-separated: static,cab,meter (default all)')
    a = ap.parse_args()
    out = a.out.resolve()
    man = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    img = (out / 'SP404MKII_APP1.bin').read_bytes()
    parent_img = Path(man['parent_app1']).read_bytes()
    if sha(parent_img) != man['parent_sha256']:
        raise SystemExit('parent APP1 does not match the manifest')
    kit_sym = json.loads(a.kits.read_text(encoding='utf-8')).get('arp_symbols')
    if not kit_sym:
        raise SystemExit('no kit symbols beside the parent APP1')
    sym = man['symbols']
    only = set((a.only or 'static,cab,meter').split(','))
    if 'static' in only:
        static_checks(out, man, parent_img, img)
    if 'cab' in only:
        cab_checks(parent_img, img, man)
    if 'meter' in only:
        base.entry_checks(parent_img, img, sym)
        base.arithmetic(img, man)
        readout(img, man)
        base.ui(img, man, head='CAB ')
        base.voice_chain(parent_img, img, man, a.seeds)
        base.voice_chain(parent_img, img, man, 2, sabotage=True)
        base.whole_mixer(parent_img, img, man, kit_sym, a.blocks, a.mixer_runs)
        base.measurement_points(parent_img, img, man, kit_sym)
    fails = base.fails
    report['result'] = 'FAIL' if fails else 'PASS'
    report['fails'] = fails
    (out / 'test_report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'{len(fails)} failure(s)' if fails else 'all checks passed')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
