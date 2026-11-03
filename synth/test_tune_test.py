"""Checks for note tracker test 1 (build_tune_test.py): the CPU meter as in cabinet test 2, and the tracker.

usage: python synth/test_tune_test.py OUT_DIR --kits KITS_MANIFEST [--seeds N] [--blocks N] [--mixer-runs N] [--only ...]

The meter's checks are NAM test 2's (test_nam_test.py, imported: the same hooks, the same meter_t), run on this
image. On top of them:

1. Static: only the header, the five patch spans and the appended module differ from the parent; the scatter table is
   the parent's rows plus the module row.
2. The readout's six lines and their widths in the popup font.
3. The tracker, on Unicorn's Cortex-M7 model, with the input FX/EXT SOURCE getters stubbed:
   - the UI clears the tracker and its result, then hands it over; RUN from the first block;
   - plucked strings (tunetest/tune_ref.py's) from 62 Hz to 1.3 kHz, clean and overdriven, through the module and
     through tune_ref.py's tracker: after every block the same steady note, voiced flag, plucks, times to the first
     estimate and to the steady note; the frequency within 0.1%; the note right and within 3 cents of the string;
     noise alone gives no note;
   - the FPU registers, FPSCR and the callee-saved registers are as they were after every step; the step runs on the
     module's own stack (its depth measured), the task's stack sees only tune_rx's frame; the instructions a step
     takes, by phase;
   - hiding the readout stops it, showing it again starts afresh; the SLOW rules;
   - diag_rx with the RX site's r6/r9: pairs 0 and 1's peaks and pair 0's (L + R) >> 1 from this block's bank;
   - the readout through the UI tick: the tracker's lines, every 0.1 s while it runs;
   - diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui as the parent does.

Not a hardware test: no timing (instructions are counted as a proxy), no screen, synthetic strings.
"""
from __future__ import annotations

import argparse
import json
import random
import struct
import sys
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn import arm_const as ar

import test_nam_test as base
from test_nam_test import (Machine, check, sha, scatter, FLASH, COPY, STACK, SCRATCH, TXBUF, CAPTURE, SYSPRM, SYS_GET,
                           SETTINGS_OBJ, SET_GET, CUR_TASK, TCB, M_SHOWN, skip_spans)

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tunetest'))
import tune_ref as ref  # noqa: E402

TT_OFF, TT_RUN, TT_SLOW = range(3)
TT_HEAD = 'req fx ext checked checks starts posted_rseq state rx steps task_attr last_mix'.split()
TT_MID = 'w_n w_sum w_max w_tot seq p_blocks p_avg p_max p_tot_max tot_max_ever over slow_cycles hot reset_req reset_ack rseq'.split()
report = base.report
PACKET = TXBUF + 0x6000


class Layout:
    """tt_t and tt_block_t offsets, from the module's tt_layout table."""
    def __init__(self, m, sym):
        v = struct.unpack('<20I', m.bytes(sym['tt_layout'], 80))
        (self.tt_bytes, self.state, self.peak, self.inp, self.w_n, self.pub, self.tot_max_ever, self.reset_ack,
         self.rseq, self.res, self.res_bytes, self.block_bytes, self.b_ring, self.b_span, self.b_d6, self.b_energy,
         self.b_z, self.b_started, self.b_stack, self.posted_rseq) = v
        check(self.state == 4 * TT_HEAD.index('state') and self.posted_rseq == 4 * TT_HEAD.index('posted_rseq') and
              self.peak == 4 * len(TT_HEAD) and self.inp == self.peak + 8 and self.w_n == self.inp + 128 and
              self.pub == self.w_n + 20 and self.rseq == self.w_n + 4 * (len(TT_MID) - 1) and
              self.res == self.rseq + 4 and self.res_bytes == 4 * len(ref.RESULT) and
              self.tt_bytes == self.res + self.res_bytes, 'tt_t layout as the test reads it')


def tt_state(m, sym, lay):
    t = sym['tt']
    st = dict(zip(TT_HEAD, struct.unpack(f'<{len(TT_HEAD)}I', m.bytes(t, 4 * len(TT_HEAD)))))
    st.update(zip(TT_MID, struct.unpack(f'<{len(TT_MID)}I', m.bytes(t + lay.w_n, 4 * len(TT_MID)))))
    st['peak'] = list(struct.unpack('<2I', m.bytes(t + lay.peak, 8)))
    st['in'] = list(struct.unpack('<64h', m.bytes(t + lay.inp, 128)))
    r = dict(zip(ref.RESULT, struct.unpack(f'<{len(ref.RESULT)}i', m.bytes(t + lay.res, lay.res_bytes))))
    st['res'] = r
    return st


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
    spans = [(0x80, 0x88)]
    for p in man['patches']:
        off = None
        for load, dst, n, fn in rows_p:
            if fn == COPY and load and dst <= p['address'] and p['address'] + p['size'] <= dst + n:
                off = load - FLASH + p['address'] - dst
        spans.append((off, off + p['size']))
        check(parent_img[off:off + p['size']].hex() == p['original_hex'] and
              img[off:off + p['size']].hex() == p['replacement_hex'],
              f"patch {p['address']:#x}: parent bytes and replacement as recorded")
    diff = [i for i in range(len(parent_img)) if parent_img[i] != img[i] and not any(lo <= i < hi for lo, hi in spans)]
    check(not diff, f'nothing else differs inside the parent image ({len(diff)} other bytes)')
    check(len(img) > len(parent_img) and FLASH + len(img) <= 0x603FF000, 'appended tail stays below the settings sector')
    report['static'] = dict(patches=[hex(p['address']) for p in man['patches']], module_size=man['module_size'],
                            fpu_instructions=man['fpu_instructions'], block_bytes=man['tt_block_bytes'])


# ---------------------------------------------------------------------------------------------
def readout(img, man):
    sym = man['symbols']
    width, line = base.font_widths(img)
    m = Machine(img)
    S, T = sym['meter'], sym['tt']
    lay = Layout(m, sym)
    m.cyc = 5
    m.call(sym['meter_mix_begin'], 0)                                 # initialise (budget 800k)

    def tt_put(**kw):
        for k, v in kw.items():
            if k == 'peak':
                m.uc.mem_write(T + lay.peak, struct.pack('<2I', *v))
            elif k in TT_HEAD:
                m.put(T + 4 * TT_HEAD.index(k), v, '<I')
            else:
                m.put(T + lay.w_n + 4 * TT_MID.index(k), v, '<I')

    def res(**kw):
        r = dict.fromkeys(ref.RESULT, 0)
        r['note'] = -1
        r.update(kw)
        return struct.pack(f'<{len(ref.RESULT)}i', *[r[k] for k in ref.RESULT])

    cases = {
        'idle': ((60000, 90000, 0, 0, 0, 0, 0, 800000, 800000, 800000), (0, 0, 0, 0), res(),
                 dict(state=TT_OFF, fx=0, ext=1, tot_max_ever=90000, over=0, peak=[0, 0])),
        'typical': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (75, 32000, 48000, 360000),
                    res(note=40, cents=3, freq10=824, quality=92, voiced=1, first_ms=21, lock_ms=27, onsets=14,
                        locks=12, lock_sum=300, lock_min=16, lock_max=32, analyses=900),
                    dict(state=TT_RUN, fx=23, ext=1, tot_max_ever=368000, over=0, peak=[14746, 7000])),
        'high': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (75, 32000, 48000, 360000),
                 res(note=88, cents=-50, freq10=13185, quality=100, voiced=1, first_ms=5, lock_ms=16, locks=3,
                     lock_sum=48, analyses=60),
                 dict(state=TT_RUN, fx=0, ext=0, tot_max_ever=368000, over=0, peak=[32768, 0])),
        'worst': ((9999999, 9999999, 9999999, 9999999, 9999999, 9999999, 4000, 5000000, 0, 5000000),
                  (75, 9999999, 9999999, 9999999),
                  res(note=70, cents=-50, freq10=99999, quality=100, voiced=1, first_ms=9999, lock_ms=9999,
                      locks=9999, lock_sum=99999999, analyses=9999),
                  dict(state=TT_SLOW, fx=99, ext=1, tot_max_ever=9999999, over=99999, peak=[32768, 32768])),
    }
    texts = {}
    for name, (w, tw, r, tv) in cases.items():
        m.uc.mem_write(SCRATCH, struct.pack('<11I', 375, *w))
        m.uc.mem_write(SCRATCH + 0x80, struct.pack('<4I', *tw))
        m.uc.mem_write(SCRATCH + 0xC0, r)
        tt_put(**tv)
        m.call(sym['tune_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0xC0, SCRATCH + 0x100)
        texts[name] = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    lines = {k: v.split('\n') for k, v in texts.items()}
    check(texts['typical'] == 'E2 +3c Q92\n82.4Hz LV45 X1\n1ST 21 LCK 27\nAVG 25 N12 IN23\nTRK 4/6 MIX 23\nMAX 46 OVR 0',
          f"typical readout reads {texts['typical']!r}")
    check(texts['idle'] == '-- Q0\n--Hz LV0 X1\n1ST 0 LCK 0\nAVG 0 N0 IN0\nTRK OFF MIX 8\nMAX 11 OVR 0',
          f"idle readout reads {texts['idle']!r}")
    m.uc.mem_write(SCRATCH + 0xC0, bytes(4 * len(ref.RESULT)))         # never started: all zero, note 0
    m.call(sym['tune_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0xC0, SCRATCH + 0x100)
    zero = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    check(zero.startswith('-- Q0\n'), f'a result never started (all zero) shows no note, not C-1 ({zero!r})')
    check(lines['high'][:2] == ['E6 -50c Q100', '1318Hz LV100 X0'] and lines['high'][3] == 'AVG 16 N3 IN0',
          f"a high note: no decimal from 1 kHz up ({lines['high'][:4]!r})")
    check(lines['worst'][0] == 'A#4 -50c Q100' and lines['worst'][3] == 'AVG 999 N99 IN99' and
          lines['worst'][4] == 'TRK SLOW MIX 99' and lines['worst'][5] == 'MAX 999 OVR 999',
          f"worst-case lines read {lines['worst']!r}")
    widest = max(sum(width(c) for c in ln) for v in lines.values() for ln in v)
    box_w, box_h = widest - 1 + 18, 6 * line - 1 + 8
    check(all(len(v) == 6 for v in lines.values()) and box_w <= 128 and box_h <= 64,
          f'worst-case readout fits the popup: widest line {widest} px -> box {box_w}x{box_h} (screen 128x64)')
    report['readout'] = dict(texts=texts, widest_line_px=widest, box=[box_w, box_h], line_px=line)


# ---------------------------------------------------------------------------------------------
class TuneMachine(Machine):
    """The image on the Cortex-M7 model, with the input FX and EXT SOURCE getters stubbed."""
    def __init__(self, img, man, fx=0, ext=1):
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
        return self.sym['tt_block']

    def tt(self):
        return tt_state(self, self.sym, self.lay)

    def ui(self, shown, advance=60_000_001):
        self.put(self.sym['meter'] + M_SHOWN, shown)
        self.cyc += advance
        self.call(self.sym['tune_ui'])

    def feed(self, values, pair1=None):
        """One RX block: pair 0 with L = R = values, pair 1 as given (else silent), the others silent."""
        pk = [0] * 1024
        for f in range(64):
            pk[16 * f] = pk[16 * f + 1] = values[f]
            if pair1 is not None:
                pk[16 * f + 2] = pk[16 * f + 3] = pair1[f]
        self.uc.mem_write(PACKET, struct.pack('<1024h', *pk))
        self.call(self.sym['tune_pairs'], PACKET)

    def rx(self, values=None):
        if values is not None:
            self.feed(values)
        self.call(self.sym['tune_rx'])
        return self.tt()


SIGNALS = [  # (label, MIDI notes, overdrive, legato): one at a time, or legato with the string before ringing
    ('low strings', (35, 38, 40, 45), 0.0, False),
    ('middle', (50, 55, 59, 64), 0.0, False),
    ('high frets', (69, 76, 81, 88), 0.0, False),
    ('overdriven', (40, 52, 64, 76), 4.0, False),
    ('legato', (40, 43, 45, 47), 0.0, True),
]


def signal(notes, drive, seed, legato=False):
    return ref.phrase(notes, drive, seed, legato)


def tracker_checks(parent_img, img, man):
    sym = man['symbols']
    m = TuneMachine(img, man, fx=23)
    lay, blk = m.lay, m.block
    rng = random.Random(4096)
    # 1. Start: the UI clears the tracker and its result, then hands it over.
    m.uc.mem_write(blk, b'\xA5' * (lay.b_stack))                       # leftovers of an earlier run
    m.uc.mem_write(sym['tt'] + lay.res, b'\x5A' * lay.res_bytes)
    m.ui(0)
    check(m.tt()['req'] == 0 and m.tt()['starts'] == 0, 'readout hidden: nothing started')
    m.getters.clear()
    rseq0 = m.tt()['rseq']
    m.ui(1)
    st = m.tt()
    want_res = dict.fromkeys(ref.RESULT, 0)
    want_res['note'] = -1
    check(st['req'] == 1 and st['starts'] == 1 and not any(m.bytes(blk, lay.b_stack)) and st['res'] == want_res and
          st['rseq'] == rseq0 + 2,
          'readout shown: the tracker and its result cleared (no note), a new result for the readout, handed over')
    check(m.getters == [(SYS_GET, SYSPRM, 0x27C), (SET_GET, SETTINGS_OBJ, 0x25)] and st['fx'] == 23 and st['ext'] == 1,
          'every 0.1 s: the input FX and EXT SOURCE')
    st = m.rx([0] * 64)
    check(st['state'] == TT_RUN and st['steps'] == 1 and m.get(blk + lay.b_started, '<I') == 1,
          'RUN from the first block')
    # 2. Plucked strings through the module and through tune_ref.py.
    found, mism, wrong = [], [], []
    for si, (label, notes, drive, legato) in enumerate(SIGNALS):
        mm = TuneMachine(img, man)
        mm.ui(1)
        tr = ref.Tracker()
        locks, probe = [], None
        for b, values in enumerate(ref.to_blocks(signal(notes, drive, 10 * si, legato), noise=1e-4, seed=si)):
            st = mm.rx(values)
            tr.step(values)
            got, want = st['res'], tr.res
            same = all(got[k] == want[k] for k in ('note', 'voiced', 'first_ms', 'lock_ms', 'onsets', 'locks',
                                                   'lock_min', 'lock_max', 'analyses'))
            close = (abs(got['freq10'] - want['freq10']) <= max(1, want['freq10'] // 1000) and
                     abs(got['cents'] - want['cents']) <= 1 and abs(got['quality'] - want['quality']) <= 2)
            if not (same and close) and len(mism) < 4:
                mism.append((label, b, {k: (got[k], want[k]) for k in ref.RESULT if got[k] != want[k]}))
            if got['locks'] > len(locks):
                locks.append([got['note'], got['lock_ms'], got['first_ms'], None])
                probe = b + 112                                   # 150 ms on: past the attack
            if b == probe and got['voiced'] and got['note'] == locks[-1][0]:
                locks[-1][3] = got['cents']
        found.append((label, [(ref.name(n), lk, fs) for n, lk, fs, _ in locks]))
        if legato:                                                   # C = Python there; no claim on the notes
            continue
        if [n for n, _, _, _ in locks] != list(notes):
            wrong.append((label, [ref.name(n) for n, _, _, _ in locks], [ref.name(n) for n in notes]))
        off = [(ref.name(n), c) for n, _, _, c in locks if c is None or abs(c) > 3]   # within 3 cents, 150 ms on
        if off:
            wrong.append((label, 'cents', off))
    check(not mism, f'C and tune_ref.py agree after every block: notes, plucks, times, counts; frequency within 0.1%, '
                    f'cents within 1 ({mism})')
    check(not wrong, f'every pluck played one at a time gives its string\'s note, within 3 cents 150 ms after '
                     f'it went steady '
                     f'({wrong})')
    lock_times = [lk for label, ls in found if label != 'legato' for _, lk, _ in ls]
    first_times = [fs for label, ls in found if label != 'legato' for _, _, fs in ls]
    check(lock_times and max(lock_times) <= 40, f'steady note {min(lock_times)}-{max(lock_times)} ms after a pluck, '
                                                f'first estimate {min(first_times)}-{max(first_times)} ms ({found})')
    mn = TuneMachine(img, man)
    mn.ui(1)
    import numpy as np
    for values in ref.to_blocks(np.random.default_rng(5).normal(0, 0.05, 48000)):
        st = mn.rx(values)
    check(st['res']['note'] == -1 and st['res']['locks'] == 0, 'a second of noise: no note')
    # 3. Registers, stacks, instructions by phase.
    fpu_ok = regs_ok = True
    stack_depth = task_depth = 0
    by_phase = [0, 0, 0, 0]
    counter = [0]

    def every(uc, a_, s_, _):
        counter[0] += 1
    sig = ref.to_blocks(signal((45,), 0.0, 3), noise=1e-3)
    for b in range(40):
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
        m.feed(sig[20 + b])
        phase = m.get(blk + lay.b_started + 8, '<I') & 3
        counter[0] = 0
        h = m.uc.hook_add(UC_HOOK_CODE, every)
        m.call(sym['tune_rx'])
        m.uc.hook_del(h)
        by_phase[phase] = max(by_phase[phase], counter[0])
        fpu_ok &= [m.uc.reg_read(getattr(ar, f'UC_ARM_REG_S{k}')) for k in range(32)] == pattern and \
            m.uc.reg_read(ar.UC_ARM_REG_FPSCR) & 0xF7C0009F == fpscr & 0xF7C0009F
        regs_ok &= [m.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k + 4}')) for k in range(8)] == gpr
        stk = m.bytes(blk + lay.b_stack, 2048)
        stack_depth = max(stack_depth, 2048 - next(i for i in range(2048) if stk[i] != 0xEE))
        tsk = m.bytes(STACK - 0x800, 0x800)
        task_depth = max(task_depth, 0x800 - next((i for i in range(0x800) if tsk[i] != 0xEE), 0x800))
    check(fpu_ok and regs_ok, 's0-s31, FPSCR and r4-r11 as they were after every step')
    check(0 < stack_depth <= 1536 and task_depth <= 96,
          f'the step runs on the module\'s own stack ({stack_depth} of 2,048 bytes); the task\'s stack sees '
          f'{task_depth} bytes (tune_rx\'s frame)')
    check(max(by_phase) <= 80000, f'instructions a step, by phase 0-3: {by_phase} (the most is '
                                  f'{max(by_phase) / 8000:.1f}% of a block at one a cycle)')
    # 4. Stop; start again afresh.
    m.ui(0)
    st = m.rx([0] * 64)
    steps = st['steps']
    check(st['req'] == 0 and st['state'] == TT_OFF, 'readout hidden: the tracker stops (OFF)')
    check(m.rx([0] * 64)['steps'] == steps, 'stopped: no more steps')
    m.ui(1)
    st = m.rx([0] * 64)
    check(st['state'] == TT_RUN and st['starts'] == 2 and st['res']['analyses'] == 0 and
          m.get(blk + lay.b_started + 8, '<I') == 1, 'shown again: cleared, and the first block starts afresh')
    # 5. SLOW: two wakes in a row over 9/10 (mixer + tracker), or one step over the whole block.
    hot = []
    for mix, step in ((300_000, 450_000), (300_000, 300_000), (300_000, 450_000), (300_000, 450_000)):
        m.put(sym['tt'] + 4 * TT_HEAD.index('last_mix'), mix, '<I')
        m.cyc_step = step
        st = m.rx([1000] * 64)
        m.cyc_step = 0
        hot.append((st['state'], st['hot']))
    check(hot == [(TT_RUN, 1), (TT_RUN, 0), (TT_RUN, 1), (TT_SLOW, 2)] and st['slow_cycles'] == 750_000,
          f'mixer + tracker over 9/10 of the block twice in a row: SLOW; once, then a cooler wake: RUN on ({hot})')
    steps = m.rx([0] * 64)['steps']
    check(m.rx([0] * 64)['steps'] == steps and m.tt()['state'] == TT_SLOW, 'SLOW stays until the readout is hidden')
    m.ui(0)
    m.rx([0] * 64)
    m.ui(1)
    m.rx([0] * 64)
    m.cyc_step = 850_000
    st = m.rx([1000] * 64)
    m.cyc_step = 0
    pub = struct.unpack('<4I', m.bytes(sym['tt'] + lay.pub, 16))
    check(st['state'] == TT_SLOW and st['slow_cycles'] == 850_000 and pub[2] == 850_000,
          'one step over the whole 800,000-cycle block: SLOW at once; the window so far published')
    # 6. diag_rx with r6/r9 as the RX site leaves them: this block's bank, pairs 0 and 1, pair 0's (L + R) >> 1.
    mq = TuneMachine(img, man)
    rxbase, task = TXBUF + 0x4000, SCRATCH + 0x800
    packet = []
    for f in range(64):
        for k in range(8):
            for c in range(2):
                v = [(f * 397) % 20001 - 10000, 3000 if (f + c) % 2 else -3000][k] if k < 2 else 30000
                packet.append(v + (7 if (k == 0 and c == 1) else 0))
    mq.uc.mem_write(rxbase, b'\x55' * 0x800)                            # bank 0: not this block's
    mq.uc.mem_write(rxbase + 0x800, struct.pack('<1024h', *packet))     # bank 1: this block's
    mq.put(task + 4, 1, '<I')
    mq.uc.reg_write(ar.UC_ARM_REG_R6, task)
    mq.uc.reg_write(ar.UC_ARM_REG_R9, rxbase)
    mq.call(sym['diag_rx'])
    st = mq.tt()
    want_in = [(packet[16 * f] + packet[16 * f + 1]) >> 1 for f in range(64)]
    p0 = max(max(abs(packet[16 * f]), abs(packet[16 * f + 1])) for f in range(64))
    check(st['in'] == want_in and st['peak'] == [p0, 3000] and mq.uc.reg_read(ar.UC_ARM_REG_R6) == task and
          mq.uc.reg_read(ar.UC_ARM_REG_R9) == rxbase,
          f"diag_rx with r6/r9 as the RX site leaves them: pair 0's (L + R) >> 1 and the peaks of pairs 0 and 1 from "
          f"this block's packet, not the other bank's ({st['peak']}); r6 and r9 kept")
    # 7. The readout through the UI tick: the tracker's lines; every 0.1 s while results come.
    mr = TuneMachine(img, man, fx=23)
    mr.put(base.PAGE, 1, '<h')
    mr.put(base.POPUP_PENDING, -1)
    mr.put(base.POPUP_SHOWN, 0, '<I')
    mr.call(sym['meter_mix_begin'], 0)
    mr.call(sym['meter_mix_end'])
    mr.put(sym['meter'] + M_SHOWN, 1)
    mr.ui(1)
    sig = ref.to_blocks(signal((52,), 0.0, 7), noise=1e-4)
    posts, texts = [], []
    for b in range(300):
        mr.rx(sig[b])
        if b % 15 == 14:                                                 # 20 ms of UI ticks
            mr.cyc += 12_000_000
            mr.call(sym['meter_ui_tick'], 1)
            if mr.get(base.POPUP_PENDING) >= 0:
                posts.append(b)
                texts.append(mr.bytes(base.POPUP_TEXT, 0x80).split(b'\0')[0].decode('latin-1'))
                mr.put(base.POPUP_PENDING, -1)
                mr.put(base.POPUP_SHOWN, 0x1234, '<I')
    gaps = [b - a for a, b in zip(posts, posts[1:])]
    check(texts and texts[-1].startswith('E3 ') and texts[-1].split('\n')[4].startswith('TRK ') and
          gaps and min(gaps) >= 75 and max(gaps) <= 90,
          f'the readout follows the tracker every 0.1 s ({len(posts)} posts, gaps {sorted(set(gaps))} blocks): '
          f'{texts[-1]!r}')
    # 8. diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui (the tracker off: same memory as the parent).
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
    report['tune'] = dict(plucks=found, private_stack_bytes=stack_depth, task_stack_bytes=task_depth,
                          step_instructions_by_phase=by_phase,
                          step_percent_at_one_cycle=round(max(by_phase) / 8000, 1))


# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--kits', type=Path, required=True, help="the kit stage's kits-manifest.json (arp_symbols)")
    ap.add_argument('--seeds', type=int, default=12)
    ap.add_argument('--blocks', type=int, default=6)
    ap.add_argument('--mixer-runs', type=int, default=4)
    ap.add_argument('--only', help='comma-separated: static,tune,meter (default all)')
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
    only = set((a.only or 'static,tune,meter').split(','))
    if 'static' in only:
        static_checks(out, man, parent_img, img)
    if 'tune' in only:
        tracker_checks(parent_img, img, man)
    if 'meter' in only:
        base.entry_checks(parent_img, img, sym)
        base.arithmetic(img, man)
        readout(img, man)
        base.ui(img, man, head='--')
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
