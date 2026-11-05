"""Checks for SY synth test 3 with guitar synth test 6 (build_tune_test.py): the CPU meter as in cabinet test 2, the
tracker (note tracker test 2's, with test 4's click and clean readings), the SY engine (12. below), and the synth: the tracker's note on the Sound Generator,
the cases synth test 3 got wrong on the unit (picks at the ringing string's level, strings ringing together) and
test 2's (a thump, a re-pick, vibrato, drum mode), the pick's velocity, OCT; test 5's ROUTING gate (silent on Mix,
where pair 0 is the mix as heard) and its popup; test 6's cases from test 5 on the unit: a fretted note let go right
after the pick (one note, let go soon), chords held and picked string by string (each note plays).

usage: python synth/test_tune_test.py OUT_DIR --kits KITS_MANIFEST [--seeds N] [--blocks N] [--mixer-runs N] [--only ...]
(--only: static,tune,synth,sy,meter)

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
     one pluck a note; noise alone gives no note;
   - the hardware test's run: six open strings through a pickup (tune_ref.py's open_strings), each rung 1.5 s and
     stopped by hand: one pluck and one steady note a string, the right notes (tune-test1's pluck test took the
     ringing for new plucks: N51 from six notes on the unit, 14-15 here);
   - the FPU registers, FPSCR and the callee-saved registers are as they were after every step; the step runs on the
     module's own stack (its depth measured), the task's stack sees only tune_rx's frame; the instructions a step
     takes, by phase;
   - hiding the readout stops it, showing it again starts afresh; the SLOW rules;
   - diag_rx with the RX site's r6/r9: pairs 0 and 1's peaks and pair 0's (L + R) >> 1 from this block's bank;
   - the readout through the UI tick: the tracker's lines, every 0.1 s while it runs;
   - diag_rx and diag_ui run bounce's own bnc_rx and bnc_ui as the parent does.

12. SY synth test 1 (tunetest/sy_fp.c, the glue in tune_test.c):
   - it plays on every page but the Sound Generator's with EXT SOURCE on and ROUTING on ExtIn, cleared before each
     start; leaving that fades it out over 8 blocks, then OFF; not on Mix, not with EXT SOURCE off;
   - the module's output = tunetest/sy_ref.py's, value for value, on open strings, a strummed and a picked chord, a
     bend, a clipped strum, hiss alone; the bands sounding are the strings' partials; silence after the strings stop;
   - s0-s31, FPSCR, r4-r11 kept; its own stack; sy_tx adds its block to the DRY pair once, clipped to 20 bits, and
     the whole mixer is the parent's plus that block; the SLOW rules; the instructions a step takes;
   - test 2: every tone value for value against sy_ref.py (the SEQ tone at the stub's tempo); VALUE + pad picks a
     tone (popup, the pad's press and release taken, FX deep edit's handlers asked first / for every other key),
     pad 16 stops the synth and another pad starts it again; a new tone fades out, switches and fades in, value for
     value; the builder's two calls in FX deep edit's bridges; the popups fit the screen;
   - test 3: VALUE + CTRL 1-3 set the picked tone's knobs (FX deep edit's knob handler asked first, the turn taken, a
     popup); every tone with its knobs turned value for value against sy_ref.py; the file (the stock file calls
     emulated): written when VALUE is let go after a change (not with an FX screen up), read at the first key event of
     a fresh start (the tone and knobs back, the engine as the twin with them), a bad or missing file ignored;
     sy_block in its own zeroed slot.

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
TT_HEAD = 'req fx ext routing checked checks starts posted_rseq state rx steps task_attr last_mix'.split()
ROUTING, EXTIN = 0x5C, 1           # system 0x5c, INPUT SETTING's ROUTING: 0 Mix, 1 ExtIn
TT_MID = 'w_n w_sum w_max w_tot seq p_blocks p_avg p_max p_tot_max tot_max_ever over slow_cycles hot reset_req reset_ack rseq'.split()
report = base.report
PACKET = TXBUF + 0x6000


class Layout:
    """tt_t and tt_block_t offsets, from the module's tt_layout table."""
    def __init__(self, m, sym):
        v = struct.unpack('<22I', m.bytes(sym['tt_layout'], 88))
        (self.tt_bytes, self.state, self.peak, self.inp, self.w_n, self.pub, self.tot_max_ever, self.reset_ack,
         self.rseq, self.res, self.res_bytes, self.block_bytes, self.b_ring, self.b_span, self.b_d6, self.b_peaks,
         self.b_z, self.b_started, self.b_stack, self.posted_rseq, self.b_pick, self.b_env) = v
        self.syn = self.res + self.res_bytes
        check(self.state == 4 * TT_HEAD.index('state') and self.posted_rseq == 4 * TT_HEAD.index('posted_rseq') and
              self.peak == 4 * len(TT_HEAD) and self.inp == self.peak + 8 and self.w_n == self.inp + 128 and
              self.pub == self.w_n + 20 and self.rseq == self.w_n + 4 * (len(TT_MID) - 1) and
              self.res == self.rseq + 4 and self.res_bytes == 4 * len(ref.RESULT) and
              self.tt_bytes == self.syn + 8 and self.b_pick + 16 <= self.b_stack and self.b_env + 24 <= self.b_stack,
              'tt_t layout as the test reads it (syn, drum at the end)')


def tt_state(m, sym, lay):
    t = sym['tt']
    st = dict(zip(TT_HEAD, struct.unpack(f'<{len(TT_HEAD)}I', m.bytes(t, 4 * len(TT_HEAD)))))
    st.update(zip(TT_MID, struct.unpack(f'<{len(TT_MID)}I', m.bytes(t + lay.w_n, 4 * len(TT_MID)))))
    st['peak'] = list(struct.unpack('<2I', m.bytes(t + lay.peak, 8)))
    st['in'] = list(struct.unpack('<64h', m.bytes(t + lay.inp, 128)))
    r = dict(zip(ref.RESULT, struct.unpack(f'<{len(ref.RESULT)}i', m.bytes(t + lay.res, lay.res_bytes))))
    st['res'] = r
    st['syn'] = struct.unpack('<I', m.bytes(t + lay.syn, 4))[0]
    st['drum'] = struct.unpack('<I', m.bytes(t + lay.syn + 4, 4))[0]
    return st


# ---------------------------------------------------------------------------------------------
def static_checks(out, man, parent_img, img):
    check(sha(img) == man['sha256'] and len(img) == man['size'], 'APP1 matches the manifest')
    check(sha((out / 'SP404MKII_APP0.bin').read_bytes()) == man['app0_sha256'], 'APP0 is stock 5.52')
    rows_p, rows = scatter(parent_img), scatter(img)
    new_row = [FLASH + man['module_file_offset'], man['module_base'], man['module_size'], COPY]
    zero_rows = [[0, r['address'], r['size'], base.ZERO] for r in man['rows_added'] if r['kind'] == 'zero']
    check(rows == rows_p + [new_row] + zero_rows and len(zero_rows) == 1 and
          zero_rows[0][1] == man['symbols']['sy_block'],
          'scatter table = parent rows + the module row + sy_block\'s zero row (SY test 3: out of the module)')
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

    def sy_put(state=0, sounding=0, avg=0, mx=0, tot_max_ever=0, over=0):
        at = sym['sy']
        m.put(at + SY_RUN_AT + 4 * SY_RUNF.index('state'), state, '<I')
        m.put(at + SY_RUN_AT + 4 * SY_RUNF.index('sounding'), sounding, '<I')
        tail = at + SY_OUT_AT + 256
        for k, v in (('seq', 0), ('p_avg', avg), ('p_max', mx), ('tot_max_ever', tot_max_ever), ('over', over)):
            m.put(tail + 4 * SY_TAIL.index(k), v, '<I')

    def res(**kw):
        r = dict.fromkeys(ref.RESULT, 0)
        r['note'] = -1
        r.update(kw)
        return struct.pack(f'<{len(ref.RESULT)}i', *[r[k] for k in ref.RESULT])

    cases = {
        'idle': ((60000, 90000, 0, 0, 0, 0, 0, 800000, 800000, 800000), (0, 0, 0, 0), res(),
                 dict(state=TT_OFF, fx=0, ext=1, tot_max_ever=90000, over=0, peak=[0, 0]), dict(state=SY_OFF)),
        'typical': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (75, 32000, 48000, 360000),
                    res(note=40, cents=3, freq10=824, quality=92, voiced=1, first_ms=21, lock_ms=27, onsets=14,
                        locks=12, lock_sum=300, lock_min=16, lock_max=32, analyses=900),
                    dict(state=TT_RUN, fx=23, ext=1, tot_max_ever=368000, over=0, peak=[14746, 7000]),
                    dict(state=SY_RUN, sounding=14, avg=72000, mx=96000, tot_max_ever=400000, over=2)),
        'high': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (75, 32000, 48000, 360000),
                 res(note=88, cents=-50, freq10=13185, quality=100, voiced=1, first_ms=5, lock_ms=16, locks=3,
                     onsets=3, lock_sum=48, analyses=60),
                 dict(state=TT_RUN, fx=0, ext=0, tot_max_ever=368000, over=0, peak=[32768, 0]), dict(state=SY_OFF)),
        'worst': ((9999999, 9999999, 9999999, 9999999, 9999999, 9999999, 4000, 5000000, 0, 5000000),
                  (75, 9999999, 9999999, 9999999),
                  res(note=70, cents=-50, freq10=99999, quality=100, voiced=1, first_ms=9999, lock_ms=9999,
                      locks=9999, onsets=9999, lock_sum=99999999, analyses=9999),
                  dict(state=TT_SLOW, fx=99, ext=1, tot_max_ever=9999999, over=99999, peak=[32768, 32768]),
                  dict(state=SY_SLOW, sounding=99, tot_max_ever=9999999, over=99999)),
        'sy wide': ((184000, 328000, 0, 0, 0, 0, 0, 800000, 799000, 801000), (75, 32000, 48000, 360000),
                    res(note=40, cents=3, freq10=824, quality=92, voiced=1, analyses=900),
                    dict(state=TT_RUN, fx=23, ext=1, tot_max_ever=368000, over=0, peak=[14746, 7000]),
                    dict(state=SY_RUN, sounding=49, avg=9999999, mx=9999999, tot_max_ever=0, over=0)),
    }
    texts = {}
    for name, (w, tw, r, tv, sv) in cases.items():
        m.uc.mem_write(SCRATCH, struct.pack('<11I', 375, *w))
        m.uc.mem_write(SCRATCH + 0x80, struct.pack('<4I', *tw))
        m.uc.mem_write(SCRATCH + 0xC0, r)
        tt_put(**tv)
        sy_put(**sv)
        m.call(sym['tune_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0xC0, SCRATCH + 0x100)
        texts[name] = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    lines = {k: v.split('\n') for k, v in texts.items()}
    check(texts['typical'] ==
          'E2 +3c Q92\n82.4Hz LV45 X1\nSY 9/12 B14\nAVG 25 N12 P14\nTRK 4/6 MIX 23\nMAX 50 OVR 2',
          f"typical readout reads {texts['typical']!r} (SY test 1: line 3 the engine; MAX and OVR the worse of the "
          f"tracker's and the engine's)")
    check(texts['idle'] == '-- Q0\n--Hz LV0 X1\nSY OFF\nAVG 0 N0 P0\nTRK OFF MIX 8\nMAX 11 OVR 0',
          f"idle readout reads {texts['idle']!r}")
    check(lines['worst'][2] == 'SY SLOW' and lines['sy wide'][2] == 'SY 99/99 B49',
          f"the engine stopped: SY SLOW; at its widest: {lines['sy wide'][2]!r}")
    m.uc.mem_write(SCRATCH + 0xC0, bytes(4 * len(ref.RESULT)))         # never started: all zero, note 0
    m.call(sym['tune_format'], SCRATCH, SCRATCH + 0x80, SCRATCH + 0xC0, SCRATCH + 0x100)
    zero = m.bytes(SCRATCH + 0x100, 0x80).split(b'\0')[0].decode('ascii')
    check(zero.startswith('-- Q0\n'), f'a result never started (all zero) shows no note, not C-1 ({zero!r})')
    check(lines['high'][:2] == ['E6 -50c Q100', '1318Hz LV100 X0'] and lines['high'][3] == 'AVG 16 N3 P3',
          f"a high note: no decimal from 1 kHz up ({lines['high'][:4]!r})")
    check(lines['worst'][0] == 'A#4 -50c Q100' and lines['worst'][3] == 'AVG 999 N99 P99' and
          lines['worst'][4] == 'TRK SLOW MIX 99' and lines['worst'][5] == 'MAX 999 OVR 999',
          f"worst-case lines read {lines['worst']!r}")
    widest = max(sum(width(c) for c in ln) for v in lines.values() for ln in v)
    box_w, box_h = widest - 1 + 18, 6 * line - 1 + 8
    check(all(len(v) == 6 for v in lines.values()) and box_w <= 128 and box_h <= 64,
          f'worst-case readout fits the popup: widest line {widest} px -> box {box_w}x{box_h} (screen 128x64)')
    report['readout'] = dict(texts=texts, widest_line_px=widest, box=[box_w, box_h], line_px=line)


# ---------------------------------------------------------------------------------------------
class TuneMachine(Machine):
    """The image on the Cortex-M7 model, with the input FX, EXT SOURCE and ROUTING getters stubbed."""
    def __init__(self, img, man, fx=0, ext=1, routing=EXTIN):
        super().__init__(img, m7=True)
        self.man, self.sym = man, man['symbols']
        self.lay = Layout(self, self.sym)
        self.fx, self.ext, self.routing, self.getters = fx, ext, routing, []
        self.put(CUR_TASK, TCB, '<I')
        self.put(TCB + 0x10, 0x1001, '<I')
        for a in (SYS_GET, SET_GET):
            self.uc.hook_add(UC_HOOK_CODE, self._getter, begin=a, end=a)

    def _getter(self, uc, a, s, _):
        r1 = uc.reg_read(ar.UC_ARM_REG_R1)
        self.getters.append((a, uc.reg_read(ar.UC_ARM_REG_R0), r1, uc.reg_read(ar.UC_ARM_REG_R2)))
        v = self.ext if a == SET_GET else self.routing if r1 == ROUTING else self.fx
        uc.reg_write(ar.UC_ARM_REG_R0, v & 0xFFFFFFFF)
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
OPEN = (40, 45, 50, 55, 59, 64)    # E2 A2 D3 G3 B3 E4
GUITAR = [  # the hardware test's run: open strings through a pickup, each rung 1.5 s and stopped by hand
    ('open strings', dict()),
    ('open strings, overdriven, neck pickup', dict(drive=3.0, p=0.12, q=0.25, seed=7)),
]
GUITAR_CENTS = 15                  # a stiff wound string's overtones run sharp: it reads up to 12 cents sharp


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
    check(m.getters == [(SYS_GET, SYSPRM, 0x27C, 0), (SET_GET, SETTINGS_OBJ, 0x25, 0),
                        (SYS_GET, SYSPRM, ROUTING, 0xFFFFFFFF)] and
          st['fx'] == 23 and st['ext'] == 1 and st['routing'] == EXTIN,
          f'every 0.1 s: the input FX, EXT SOURCE and ROUTING (system 0x5c, index -1 as the stock getter reads it) '
          f'({[tuple(hex(x) for x in g) for g in m.getters]})')
    st = m.rx([0] * 64)
    check(st['state'] == TT_RUN and st['steps'] == 1 and m.get(blk + lay.b_started, '<I') == 1,
          'RUN from the first block')
    # 2. Plucked strings through the module and through tune_ref.py.
    runs = [(label, notes, ref.to_blocks(signal(notes, drive, 10 * si, legato), noise=1e-4, seed=si), legato, 3)
            for si, (label, notes, drive, legato) in enumerate(SIGNALS)]
    runs += [(label, OPEN, ref.to_blocks(ref.open_strings(OPEN, **kw)), False, GUITAR_CENTS) for label, kw in GUITAR]
    found, mism, wrong, open_counts = [], [], [], []
    for label, notes, blocks, legato, tol in runs:
        mm = TuneMachine(img, man)
        mm.ui(1)
        tr = ref.Tracker()
        locks, probe = [], None
        for b, values in enumerate(blocks):
            st = mm.rx(values)
            tr.step(values)
            got, want = st['res'], tr.res
            same = all(got[k] == want[k] for k in ('note', 'voiced', 'first_ms', 'lock_ms', 'onsets', 'locks',
                                                   'lock_min', 'lock_max', 'analyses')) and st['syn'] == tr.syn
            close = (abs(got['freq10'] - want['freq10']) <= max(1, want['freq10'] // 1000) and
                     abs(got['cents'] - want['cents']) <= 1 and abs(got['quality'] - want['quality']) <= 2)
            if not (same and close) and len(mism) < 4:
                mism.append((label, b, {k: (got[k], want[k]) for k in ref.RESULT if got[k] != want[k]},
                             (hex(st['syn']), hex(tr.syn))))
            if got['locks'] > len(locks):
                locks.append([got['note'], got['lock_ms'], got['first_ms'], None])
                probe = b + 112                                   # 150 ms on: past the attack
            if b == probe and got['voiced'] and got['note'] == locks[-1][0]:
                locks[-1][3] = got['cents']
        found.append((label, [(ref.name(n), lk, fs) for n, lk, fs, _ in locks]))
        if notes is OPEN:
            open_counts.append((label, st['res']['onsets'], st['res']['locks']))
        if legato:                                                   # C = Python there; no claim on the notes
            continue
        if [n for n, _, _, _ in locks] != list(notes):
            wrong.append((label, [ref.name(n) for n, _, _, _ in locks], [ref.name(n) for n in notes]))
        off = [(ref.name(n), c) for n, _, _, c in locks if c is None or abs(c) > tol]   # 150 ms after the lock
        if off:
            wrong.append((label, 'cents', off))
        if st['res']['onsets'] != len(notes):
            wrong.append((label, 'plucks', st['res']['onsets']))
    check(not mism, f'C and tune_ref.py agree after every block: notes, plucks, times, counts, the synth note; '
                    f'frequency within 0.1%, cents within 1 ({mism})')
    check(not wrong, f'every pluck played one at a time is one pluck and gives its string\'s note, within 3 cents '
                     f'150 ms after it went steady ({GUITAR_CENTS} for the pickup-like strings: a stiff string\'s '
                     f'overtones run sharp) ({wrong})')
    check(open_counts and all(p == n == len(OPEN) for _, p, n in open_counts),
          f'the hardware test\'s run, six open strings rung 1.5 s and stopped by hand: one pluck and one steady note '
          f'a string ({open_counts}; tune-test1 counted 14-15 plucks on the clean run)')
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
SG_PAGE = 0x1E
SG_OCT = 0x80591C4C                                                    # the Sound Generator's OCT (keyboard + 4)


class SynthMachine(TuneMachine):
    """TuneMachine on a page, with the Sound Generator's MIDI entry (the kits' gates' target) stubbed: every call
    recorded as (block, r0, note, velocity, r3)."""
    def __init__(self, img, man, page=SG_PAGE, oct=0, **kw):
        super().__init__(img, man, **kw)
        self.midi, self.blk = [], 0
        a = man['sg_midi_entry'] & ~1
        self.uc.hook_add(UC_HOOK_CODE, self._midi, begin=a, end=a)
        self.page(page)
        self.put(SG_OCT, oct & 0xFFFFFFFF, '<I')

    def page(self, p):
        self.put(base.PAGE, p, '<h')

    def _midi(self, uc, a, s, _):
        self.midi.append((self.blk,) + tuple(uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(4)))
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    def gsyn(self):
        return dict(zip(('sounding', 'done', 'ons', 'offs', 'mix', 'hint_due', 'hints'),
                        struct.unpack('<i6I', self.bytes(self.sym['gsyn'], 28))))

    def popups(self, shown=0):
        """No popup showing or waiting (a stock one showing if `shown`)."""
        self.put(base.POPUP_PENDING, -1)
        self.put(base.POPUP_SHOWN, shown, '<I')

    def posted(self):
        """The text of a post waiting to be built, else None."""
        if self.get(base.POPUP_PENDING) < 0:
            return None
        return self.bytes(base.POPUP_TEXT, 0x80).split(b'\0')[0].decode('latin-1')

    def bfields(self):
        f = struct.unpack('<f3I', self.bytes(self.block + self.lay.b_pick, 16))
        return dict(zip(('pick_peak', 'pluck_click', 'clicks', 'murky'), f))

    def b6(self):
        """Test 6's counters: the level, a note from the subtraction playing, let-gos, fast drops, notes the
        subtraction found, moves too quiet to play."""
        f = struct.unpack('<f5I', self.bytes(self.block + self.lay.b_env, 24))
        return dict(zip(('env', 'sub_lock', 'stops', 'drops', 'sub_locks', 'blocked'), f))

    def tick(self, values=None):
        """One RX block (silence if None), then syn_ui as the next UI tick runs it."""
        st = self.rx(values if values is not None else [0] * 64)
        self.call(self.sym['syn_ui'])
        self.blk += 1
        return st


def syn_model(words, drum=False, oct=0):
    """syn_ui on the page, in Python: (block, tt.syn) changes -> the MIDI calls it makes."""
    sounding, done, out = -1, 0, []
    for b, w in words:
        seq, vel, note = w >> 16, (w >> 8) & 0x7F, (w & 0xFF) - 1
        if seq != done:
            done = seq
            if sounding >= 0:
                out.append((b, 2, sounding, 0, 1))
                sounding = -1
            if note >= 0:
                n = note if drum else note + 12 * max(-3, min(4, oct))
                if 12 <= n <= 127:
                    out.append((b, 2, n, vel or 100, 0))
                    sounding = n
        elif note < 0 and sounding >= 0:
            out.append((b, 2, sounding, 0, 1))
            sounding = -1
    return out


class Run:
    """One signal through the module (SynthMachine) and the twin, side by side."""
    def __init__(self, img, man, x, noise=0.0, drum=False, oct=0):
        ms = self.ms = SynthMachine(img, man, oct=oct)
        if drum:
            ms.uc.mem_write(man['kit_mode_flag'], b'\x01')               # kit_mode: a kit, drum mode
        ms.ui(0)
        ms.ui(0)                                                         # the first reads EXT SOURCE, the second starts
        self.started = ms.tt()['req'] == 1
        tr = self.tr = ref.Tracker(drum=drum)
        self.words, self.locks, self.seen, prev = [], [], [], 0
        for b, values in enumerate(ref.to_blocks(x, noise=noise, seed=4)):
            st = ms.tick(values)
            tr.step(values)
            if tr.syn != prev:
                self.words.append((b, tr.syn))
                prev = tr.syn
            if st['res']['locks'] > len(self.locks):
                self.locks.append((b, st['res']['lock_ms']))
            if st['res']['note'] >= 0 and (not self.seen or self.seen[-1] != st['res']['note']):
                self.seen.append(st['res']['note'])
        self.st = st
        self.model = syn_model(self.words, drum, oct)
        self.g = ms.gsyn()
        self.bf = ms.bfields()
        self.b6 = ms.b6()
        self.tw = (tr.stops, tr.drops, tr.sub_locks, tr.blocked)

    def calls(self):
        return [(n, 'on' if v else 'off') for _, _, n, v, _ in self.ms.midi]

    def ons(self):
        return [(n, v) for _, _, n, v, off in self.ms.midi if v]

    def times(self):
        return [(round(b * 64 / 48000, 3), n, 'on' if v else 'off') for b, _, n, v, _ in self.ms.midi]


def held(tms):
    """Each note held until the next: every note-off comes with the next note-on (the mono synth's change of note)
    but the last, after the last note-on. tms: Run.times()."""
    ons = [t for t, n, k in tms if k == 'on']
    offs = [t for t, n, k in tms if k == 'off']
    return bool(ons) and len(offs) == len(ons) and offs[:-1] == ons[1:] and offs[-1] > ons[-1]


def twin_events(x, **kw):
    """tune_ref.py's tracker alone (test6=False: test 5's rules): [(seconds, note name or 'off')]."""
    tr, prev, out = ref.Tracker(**kw), 0, []
    for b, v in enumerate(ref.to_blocks(x, seed=4)):
        tr.step(v)
        if tr.syn != prev:
            n = (tr.syn & 0xFF) - 1
            out.append((round(b * 64 / 48000, 3), ref.name(n) if n >= 0 else 'off'))
            prev = tr.syn
    return out


def synth_checks(img, man, kit_sym):
    import numpy as np
    entry = man['sg_midi_entry']
    gates = man['guards']['sg_midi']
    check(entry == kit_sym.get('arp_midi_event') and all(g['entry'] == hex(entry & ~1) for g in gates.values()) and
          man['kit_mode_flag'] == kit_sym.get('kit_mode'),
          f"the synth's notes go to arp_midi_event {entry & ~1:#x}, where both of the kits' note gates' SG routes "
          f"jump, and drum mode is the byte it tests first, {man['kit_mode_flag']:#x} (the kits' own symbols agree): "
          f"{[g['listing'] for g in gates.values()]}")
    fs = 48000
    hz = {n: 440 * 2 ** ((n - 69) / 12) for n in range(30, 90)}

    def noisy(x, seed):
        r = np.random.default_rng(seed)
        t = np.arange(len(x)) / fs
        return x + r.normal(0, 2e-4, len(x)) + 5e-4 * np.sin(2 * np.pi * 60 * t + r.uniform(0, 2 * np.pi))

    def stopped(x):
        x = x.copy()
        d = int(0.05 * fs)
        x[-d:] *= np.linspace(1, 0, d)
        return x

    def one_string(notes, gap, amps=None, seed=0):
        """Picked one after another on one string, each pick restarting it (no gap), the last stopped by hand."""
        parts = [ref.guitar(hz[n], gap, amp=amps[k] if amps else 0.45, seed=seed + k, B=1e-4 if n < 55 else 3e-5)
                 for k, n in enumerate(notes)]
        return noisy(np.concatenate([np.zeros(fs // 5), stopped(np.concatenate(parts)), np.zeros(fs // 2)]), seed)

    def ringing(notes, gap, seed=0):
        """Each note on its own string, `gap` s apart, every string left ringing; all stopped at the end."""
        total = gap * len(notes) + 1.0
        x = np.zeros(int(total * fs))
        for k, n in enumerate(notes):
            at = int(k * gap * fs)
            s = ref.guitar(hz[n], total - k * gap, seed=seed + k, B=1e-4 if n < 55 else 3e-5)
            x[at:at + len(s)] += s[:len(x) - at]
        return noisy(np.concatenate([np.zeros(fs // 5), stopped(x), np.zeros(fs // 2)]), seed)

    report['synth'] = {}
    # 1. Six open strings on the Sound Generator page, EXT SOURCE on, the readout hidden: one note a string, each on
    # in the block its pluck went steady, at the pick's velocity, off when its string is stopped.
    r = Run(img, man, ref.open_strings(OPEN))
    ons = [(b, n, v) for b, r0, n, v, off in r.ms.midi if v]
    pairs = [(n, r.ms.midi[k + 1][2]) for k, (b, r0, n, v, off) in enumerate(r.ms.midi) if v and k + 1 < len(r.ms.midi)]
    check(r.started and r.ms.midi == r.model and [n for _, n, _ in ons] == list(OPEN) and
          all(a == c for a, c in pairs) and r.ms.midi[-1][2:] == (OPEN[-1], 0, 1) and
          [b for b, _, _ in ons] == [b for b, _ in r.locks] and all(100 <= v <= 127 for _, _, v in ons) and
          r.g['sounding'] == -1 and r.g['ons'] == 6 and r.g['offs'] == 6,
          f"six open strings: six notes, each on in the block its pluck went steady "
          f"({[lk for _, lk in r.locks]} ms after it), at the pick's velocity, off when its string is stopped "
          f"(the module's tt.syn the twin's after every block): {r.ons()}")
    report['synth']['open_strings'] = dict(ons=r.ons(), lock_ms=[lk for _, lk in r.locks])
    # 2. Synth test 3 on the unit: "stuck notes. bad tracking". A pick at the level of the ringing string never
    # doubled the peak; its click counts now.
    r = Run(img, man, one_string((52,) * 6, 0.3))
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [52] * 6 and r.st['res']['onsets'] == 6 and
          r.bf['clicks'] == 5,
          f"E3 picked six times on one string, 0.3 s apart, as hard: six notes (five plucks only the click heard, "
          f"test 2 heard one and held it) {r.times()}")
    r = Run(img, man, one_string((52, 55, 57, 59, 57, 55), 0.3, seed=10))
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [52, 55, 57, 59, 57, 55] and
          r.st['res']['onsets'] == 6,
          f"a melody on one string (E3 G3 A3 B3 A3 G3, 0.3 s each, no gaps): each note once, on its pick "
          f"({r.times()})")
    r = Run(img, man, one_string((40, 40, 43, 45, 40), 0.25, seed=20))
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [40, 40, 43, 45, 40],
          f"a riff on the low E (E2 E2 G2 A2 E2, 0.25 s each): every note, the repeat too ({r.ons()})")
    r = Run(img, man, one_string((45,) * 4, 0.4, amps=(0.45, 0.2, 0.08, 0.03), seed=30))
    vels = [v for _, v in r.ons()]
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [45] * 4 and vels == sorted(vels, reverse=True) and
          vels[0] >= 115 and vels[-1] <= 75 and min(vels) >= 50,
          f"an A2 picked four times, softer each time (0.45, 0.2, 0.08, 0.03 of full scale): four notes, "
          f"velocities {vels} (50 + 77 x the square root of the pick's peak over 0.4)")
    report['synth']['repeats'] = dict(softer=vels)
    # 3. Strings left ringing together read murky (test 3: wrong low 'common' notes); test 6 reads a pick over them from
    # what it added, so each note plays, held while the strings ring (test 4: G3, then the synth let go).
    want = [55, 57, 59, 62, 64, 67]
    r = Run(img, man, ringing(want, 0.3, seed=40))
    tms = r.times()
    on_n = [n for n, _ in r.ons()]
    off_at = [t for t, n, k in tms if k == 'off']
    check(r.ms.midi == r.model and on_n == [n for n in want if n in on_n] and len(on_n) >= 5 and
          held(tms) and off_at[-1] > 0.2 + 0.3 * 6 and r.bf['murky'] > 100 and r.b6['sub_locks'] >= 4,
          f"G3 A3 B3 D4 E4 G4 picked 0.3 s apart on six strings, all left ringing: {len(on_n)} of the 6 play in order, "
          f"none wrong ({r.b6['sub_locks']} read from what the pick added), each held until the next, let go when "
          f"they are stopped; the plain readings murky ({r.bf['murky']} analyses): {tms}")
    # 4. Test 2's cases: a thump, a re-pick, a sharp note with vibrato, drum mode; and a hammer-on.
    ring = ref.guitar(hz[40], 1.6, seed=21)
    at, w = int(0.8 * fs), int(0.003 * fs)
    bump = np.zeros(len(ring))
    bump[at:at + w] = 2.5 * np.max(np.abs(ring[at - 960:at])) * np.sin(np.pi * np.arange(w) / w)
    r = Run(img, man, noisy(np.concatenate([np.zeros(fs // 5), stopped(ring + bump), np.zeros(fs // 2)]), 21))
    check(r.ms.midi == r.model and r.calls() == [(40, 'on'), (40, 'off')] and r.st['res']['onsets'] == 2 and
          r.tr.syn_strays == 1 and r.bf['clicks'] == 0,
          f"a thump on a ringing low E (2.5 x its peak for 3 ms, 0.8 s on): a pluck without a click, its level never "
          f"rose, so the synth note goes on ({r.calls()})")
    r = Run(img, man, noisy(np.concatenate([np.zeros(fs // 5), ref.guitar(hz[40], 2.0, seed=31),
                                            stopped(ref.guitar(hz[40], 1.0, seed=32)), np.zeros(fs // 2)]), 31))
    check(r.ms.midi == r.model and r.calls() == [(40, 'on'), (40, 'off'), (40, 'on'), (40, 'off')] and
          r.st['res']['onsets'] == 2,
          f'the low E picked again 2 s on, as hard: the synth starts the note again ({r.calls()})')
    r = Run(img, man, noisy(np.concatenate([np.zeros(fs // 5), stopped(ref.guitar(hz[55], 1.5, seed=41, B=3e-5,
                                                                                   cents=40, vibrato=(-25, 5.5))),
                                            np.zeros(fs // 2)]), 41))
    check(r.ms.midi == r.model and r.calls() == [(55, 'on'), (55, 'off')] and 56 in r.seen,
          f'a G3 40 cents sharp with 25 cents of vibrato: the steady note flickers '
          f'({[ref.name(n) for n in r.seen]}), the synth holds G3 ({r.calls()})')
    hammer = noisy(np.concatenate([np.zeros(fs // 5), stopped(ref.guitar(hz[40], 1.4, seed=50, bend=(0.6, 0.601, 300))),
                                   np.zeros(fs // 2)]), 50)
    r = Run(img, man, hammer)
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [40, 43] and r.st['res']['onsets'] == 1,
          f'a hammer-on on the low E, E2 to G2 0.6 s in (no pick, no click): one pluck, the note moves '
          f'({r.times()})')
    r = Run(img, man, hammer, drum=True, oct=2)
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [40] and len(r.seen) >= 2,
          f"drum mode (kit_mode set, OCT +2), the hammer-on: the steady note moves ({[ref.name(n) for n in r.seen]}) "
          f"but only the pick plays, one hit at the guitar's own note, the pad ({r.ons()})")
    r = Run(img, man, one_string((40, 40, 43, 45, 40), 0.25, seed=20), drum=True)
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [40, 40, 43, 45, 40],
          f'drum mode, the riff: a hit for every pick ({r.ons()})')
    # 5. OCT moves the note (0: the octave tests 1 and 2 played, as the Sound Generator sounds MIDI).
    one = noisy(np.concatenate([np.zeros(fs // 5), stopped(ref.guitar(hz[45], 0.8, seed=6)), np.zeros(fs // 2)]), 6)
    got = {}
    for oct in (1, -1, 9, -7):
        got[oct] = [n for n, _ in Run(img, man, one, oct=oct).ons()]
    check(got == {1: [57], -1: [33], 9: [93], -7: []},
          f"the Sound Generator's OCT moves the note: A2 at OCT +1, -1, 9 and -7 (held to -3..+4 as OCT is) plays "
          f"{got} (under MIDI 12: nothing)")
    # 6. Off the page (the readout shown, the tracker running): nothing to the Sound Generator.
    mo = SynthMachine(img, man, page=1)
    mo.ui(1)
    st = None
    for values in ref.to_blocks(ref.open_strings((40, 45), ring=0.8))[:1200]:
        st = mo.tick(values)
    check(st['state'] == TT_RUN and st['res']['locks'] >= 1 and not mo.midi and mo.gsyn()['sounding'] == -1,
          f"off the Sound Generator page the tracker runs for the readout but plays nothing ({st['res']['locks']} "
          f"steady notes, {len(mo.midi)} calls)")
    # 7. EXT SOURCE off on the page: the tracker stays off.
    me = SynthMachine(img, man, ext=0)
    me.ui(0)
    me.ui(0)
    for values in ref.to_blocks(ref.open_strings((40,), ring=0.6))[:600]:
        st = me.tick(values)
    check(st['req'] == 0 and st['state'] == TT_OFF and st['steps'] == 0 and not me.midi,
          'Sound Generator page with EXT SOURCE off: the tracker stays off, nothing plays')
    # 8. A note playing, then EXT SOURCE off: the tracker stops and lets go of it.
    sig = ref.to_blocks(ref.open_strings((40,), ring=1.5))
    mx = SynthMachine(img, man)
    mx.ui(0)
    mx.ui(0)
    b = 0
    while not mx.midi and b < 600:
        mx.tick(sig[b])
        b += 1
    on = list(mx.midi)
    mx.ext = 0
    mx.ui(0)
    mx.ui(0)
    for k in range(3):
        st = mx.tick(sig[b + k])
    check(len(on) == 1 and on[0][2] == 40 and on[0][4] == 0 and st['state'] == TT_OFF and
          mx.midi[1:] == [(on[0][0] + 1, 2, 40, 0, 1)] and mx.gsyn()['sounding'] == -1,
          f'a note playing when the tracker stops (EXT SOURCE off): let go at the next UI tick ({mx.midi})')
    # 9. A note playing, then the page closed: forgotten (the SG stops its own voices), nothing replays on return.
    ml = SynthMachine(img, man)
    ml.ui(0)
    ml.ui(0)
    b = 0
    while not ml.midi and b < 600:
        ml.tick(sig[b])
        b += 1
    ml.page(1)
    ml.tick(sig[b])
    gone = ml.gsyn()['sounding'] == -1 and len(ml.midi) == 1
    ml.page(SG_PAGE)
    for k in range(1, 900):
        ml.tick(sig[b + k] if b + k < len(sig) else None)
    check(gone and len(ml.midi) == 1 and ml.gsyn()['sounding'] == -1,
          f'a note playing when the page closes: forgotten without a call (the Sound Generator stops its voices '
          f'itself); back on the page it does not play again ({ml.midi})')
    # 10. Test 5: ROUTING. On Mix the effects chip hands back the mix as heard and the synth heard its own note (tests
    # 2-4 on the unit: stuck notes), so it plays only on ExtIn, and the page says so on Mix.
    width, line = base.font_widths(img)
    hint = 'SYNTH NEEDS\nROUTING ExtIn\nSHIFT+EXT SRC'
    widest = max(sum(width(c) for c in ln) for ln in hint.split('\n'))
    box_w, box_h = widest - 1 + 18, 3 * line - 1 + 8
    mm = SynthMachine(img, man, routing=0)
    mm.popups()
    mm.ui(0)
    mm.ui(0)
    posts = []
    for b in range(600):
        st = mm.tick(sig[b])
        t = mm.posted()
        if t is not None:
            posts.append((b, t))
            mm.popups(shown=0x1234)                                    # the popup is up
    g = mm.gsyn()
    check(st['req'] == 0 and st['state'] == TT_OFF and st['steps'] == 0 and not mm.midi and
          posts == [(0, hint)] and g['hints'] == 1 and box_w <= 128 and box_h <= 64,
          f"ROUTING Mix on the page with EXT SOURCE on: the tracker stays off, a pluck plays nothing, and a popup says "
          f"so once, at the first UI tick ({posts}; widest line {widest} px -> box {box_w}x{box_h}, screen 128x64)")
    mm.popups()
    mm.page(1)
    mm.tick()
    mm.page(SG_PAGE)
    mm.tick()
    same = mm.posted() is None                                         # SY test 1: still on Mix, so not again

    def ext_again(machine):
        machine.ext = 0
        machine.ui(0)
        machine.tick()
        machine.ext = 1
        machine.ui(0)
    ext_again(mm)
    mm.tick()
    back = mm.posted()
    mm.popups(shown=0x1234)                                            # a stock message is up as it turns on
    ext_again(mm)
    for _ in range(5):
        mm.tick()
    waited = mm.posted() is None and mm.gsyn()['hint_due'] == 1
    mm.popups()                                                        # it closes
    mm.tick()
    after = mm.posted()
    check(same and back == hint and waited and after == hint and mm.gsyn()['hints'] == 3,
          f'the popup again each time EXT SOURCE turns on with ROUTING Mix (SY test 1: on every stock page, so not '
          f'on a page change); never over a message already up: it waits for it to close ({mm.gsyn()})')
    mq = SynthMachine(img, man, ext=0, routing=0)
    mq.popups()
    mq.ui(0)
    mq.ui(0)
    for _ in range(10):
        mq.tick()
    mp = SynthMachine(img, man, page=1, routing=0)
    md = SynthMachine(img, man, page=DOOM_PAGE, routing=0)
    for x in (mp, md):
        x.popups()
        x.ui(0)
        x.ui(0)
        for _ in range(10):
            x.tick()
    check(mq.posted() is None and mq.gsyn()['hints'] == 0 and md.posted() is None and md.gsyn()['hints'] == 0 and
          mp.posted() == hint and mp.gsyn()['hints'] == 1,
          "no popup with EXT SOURCE off (the synths are off anyway) or on DOOM OS's own pages; SY test 1: on the "
          "main screen too (the SY engine needs ExtIn as well)")
    mx = SynthMachine(img, man)
    mx.ui(0)
    mx.ui(0)
    b = 0
    while not mx.midi and b < 600:
        mx.tick(sig[b])
        b += 1
    on = list(mx.midi)
    mx.routing = 0
    mx.ui(0)
    mx.ui(0)
    for k in range(3):
        st = mx.tick(sig[b + k])
    check(len(on) == 1 and on[0][2] == 40 and on[0][4] == 0 and st['state'] == TT_OFF and
          mx.midi[1:] == [(on[0][0] + 1, 2, 40, 0, 1)] and mx.gsyn()['sounding'] == -1,
          f'a note playing when ROUTING turns Mix: let go at the next UI tick ({mx.midi})')
    mr = SynthMachine(img, man, routing=0)
    mr.ui(1)
    for values in ref.to_blocks(ref.open_strings((40, 45), ring=0.8))[:1200]:
        st = mr.tick(values)
    check(st['state'] == TT_RUN and st['res']['locks'] >= 1 and not mr.midi and mr.gsyn()['sounding'] == -1,
          f"the readout shown on the page on Mix: the tracker runs for it ({st['res']['locks']} steady notes) but "
          f"nothing plays ({len(mr.midi)} calls)")
    report['synth']['routing'] = dict(hint=hint, hint_box=[box_w, box_h])
    # 11. Test 6. Synth test 5 on the unit: "if you pluck a note and release right away you hear a second note on
    # release". A fretted note let go 0.15 s after the pick: the note is damped (5 ms), the open string or a touch
    # harmonic rings briefly far quieter, the string leaving the fret clicks; test 5 moved to the open string.
    lets, five, offs, bad = [(1, 5, 'open', 0.08), (2, 3, 'open', 0.08), (3, 7, 'open', 0.08), (5, 3, 'open', 0.08),
                             (6, 5, 'harm', 0.3), (4, 12, 'open', 0.3)], 0, [], []
    for s_, f_, kind, ac in lets:
        x, note = ref.let_go(s_, f_, kind=kind, a_click=ac, a_new=0.5 if kind == 'harm' else 0.3, seed=s_ * 31 + f_)
        r = Run(img, man, x)
        tms = r.times()
        off_at = [t for t, n, k in tms if k == 'off']
        if not (r.ms.midi == r.model and [n for n, _ in r.ons()] == [note] and off_at and off_at[0] - 0.35 < 0.06):
            bad.append((s_, f_, kind, tms))
        offs.append(round((off_at[0] - 0.35) * 1000) if off_at else None)
        five += len([e for e in twin_events(x, test6=False) if e[1] != 'off']) > 1
    check(not bad and five >= 5,
          f"a fretted note let go right after the pick (strings 1, 2, 3, 5 at frets 5, 3, 7, 3 to the open string, a "
          f"touch harmonic on the low E at fret 5, the D string at fret 12): one note each, let go {offs} ms after the "
          f"let-go; test 5's rules played a second note in {five} of {len(lets)} ({bad})")
    report['synth']['let_go_off_ms'] = offs
    # "Hold a chord and play the notes, they sometimes don't sound": each string of a held chord picked in turn.
    arps, bad, played5 = [('D', 0.3, 5), ('Am', 0.3, 5), ('G', 0.5, 5), ('C', 0.5, 5)], [], []
    for chord, gap, seed in arps:
        x, notes = ref.arpeggio(ref.CHORDS[chord], gap, seed=seed)
        r = Run(img, man, x)
        tms = r.times()
        if not (r.ms.midi == r.model and [n for n, _ in r.ons()] == notes and held(tms)):
            bad.append((chord, gap, tms))
        played5.append(len([e for e in twin_events(x, test6=False) if e[1] in [ref.name(n) for n in notes]]))
    check(not bad,
          f"chords held and picked string by string (D and Am 0.3 s apart, G and C 0.5 s): every note plays in order, "
          f"each held until the next, let go when the strings are stopped; test 5's rules played {played5} of "
          f"5, 5, 6 and 5 notes, and wrong low ones ({bad})")
    # A chord left to fade (no hand): no note from an older string coming through, one note-off when it is quiet.
    notes = [ref.OPEN[s_] + f_ for s_, f_ in ref.CHORDS['D']]
    total = 0.4 * len(notes) + 6.0
    x = np.zeros(int(total * fs))
    for k, n in enumerate(notes):
        at = int(k * 0.4 * fs)
        g = ref.guitar(hz[n], total - k * 0.4, seed=k, B=1e-4 if n < 55 else 3e-5)
        x[at:at + len(g)] += g[:len(x) - at]
    ev = twin_events(noisy(np.concatenate([np.zeros(fs // 5), x]), 1))
    check([n for _, n in ev] == [ref.name(n) for n in notes] + ['off'],
          f'the D chord picked 0.4 s apart and left to fade 6 s (tune_ref.py): its four notes, then let go once '
          f'quiet ({ev})')
    report['synth']['entry'] = hex(entry & ~1)


# ---------------------------------------------------------------------------------------------
# SY synth tests 1 to 3: the 49-band engine (sy_fp.c), its glue (tune_test.c: sy_ui, sy_rx, sy_tx, sy_key_down,
# sy_key_up, sy_knob, the file) and its twin (sy_ref.py).
SY_OFF, SY_RUN, SY_SLOW = range(3)
SY_HEAD = 'req starts stops reset_req tone_req muted picks taken bpm100 tempo_checked'.split()
SY_FILE = 'loads saves save_errors bad_files'.split()
SY_RUNF = 'state rx steps tx fresh stopping sounding last_mix'.split()
SY_KNOB_AT = 4 * len(SY_HEAD)                  # test 3: s8 knob[15][3], dirty, loaded, a pad byte
SY_FILE_AT = SY_KNOB_AT + 48
SY_RUN_AT = SY_FILE_AT + 4 * len(SY_FILE)
SY_OUT_AT = SY_RUN_AT + 4 * len(SY_RUNF)
SY_TAIL = 'w_n w_sum w_max w_tot seq p_blocks p_avg p_max p_tot_max tot_max_ever over slow_cycles hot reset_ack'.split()
DOOM_PAGE = 0x60                   # a page above the stock ones (DOOM OS's own screens)


class SyLayout:
    """sy_t and sy_block_t offsets, from the module's sy_layout table."""
    def __init__(self, m, sym):
        v = struct.unpack('<21I', m.bytes(sym['sy_layout'], 84))
        (self.sy_bytes, self.state, self.out, self.w_n, self.pub, self.tot_max_ever, self.block_bytes, self.e,
         self.per, self.ph, self.amp, self.owned, self.env, self.started, self.tone, self.nper, self.tone_req,
         self.fe, self.knob, self.dirty, self.loads) = v
        check(self.state == SY_RUN_AT and self.out == SY_OUT_AT and self.knob == SY_KNOB_AT and
              self.dirty == SY_KNOB_AT + 45 and self.loads == SY_FILE_AT and
              self.w_n == self.out + 256 and self.pub == self.w_n + 20 and self.tot_max_ever == self.pub + 16 and
              self.sy_bytes == self.tot_max_ever + 20 and self.tone_req == 4 * SY_HEAD.index('tone_req') and
              self.started + 12 <= self.block_bytes,
              'sy_t and sy_block_t layout as the test reads it')


class SyMachine(SynthMachine):
    """SynthMachine on the main screen, its RX block running tune_rx then sy_rx (as diag_rx_c), then the UI tick's
    syn_ui and sy_ui."""
    def __init__(self, img, man, page=1, store=None, **kw):
        super().__init__(img, man, page=page, **kw)
        self.sl = SyLayout(self, self.sym)
        self.files = Files(self, store)                # test 3: the stock file calls, on files kept in Python

    def sy(self):
        s = self.sym['sy']
        st = dict(zip(SY_HEAD, struct.unpack(f'<{len(SY_HEAD)}I', self.bytes(s, 4 * len(SY_HEAD)))))
        kb = self.bytes(s + SY_KNOB_AT, 48)
        st['knob'] = [list(struct.unpack('<3b', kb[3 * t:3 * t + 3])) for t in range(15)]
        st['dirty'], st['loaded'] = kb[45], kb[46]
        st.update(zip(SY_FILE, struct.unpack(f'<{len(SY_FILE)}I', self.bytes(s + SY_FILE_AT, 4 * len(SY_FILE)))))
        st.update(zip(SY_RUNF, struct.unpack(f'<{len(SY_RUNF)}I', self.bytes(s + SY_RUN_AT, 4 * len(SY_RUNF)))))
        st['out'] = list(struct.unpack('<64i', self.bytes(s + self.sl.out, 256)))
        st.update(zip(SY_TAIL, struct.unpack(f'<{len(SY_TAIL)}I', self.bytes(s + self.sl.w_n, 4 * len(SY_TAIL)))))
        return st

    def start(self):
        """The UI's 0.1 s check (input FX, EXT SOURCE, ROUTING), then sy_ui."""
        self.ui(0)
        self.call(self.sym['sy_ui'])

    def step(self, values=None):
        self.feed(values if values is not None else [0] * 64)
        self.call(self.sym['tune_rx'])
        self.call(self.sym['sy_rx'])
        self.call(self.sym['syn_ui'])
        self.call(self.sym['sy_ui'])
        self.blk += 1
        return self.sy()

    def bands(self):
        """The module's bands after the last block: sounding (amplitude > 0) as (band, frequency, amplitude)."""
        b = self.sym['sy_block']
        per = struct.unpack('<49f', self.bytes(b + self.sl.per, 196))
        amp = struct.unpack('<49f', self.bytes(b + self.sl.amp, 196))
        return [(k, 12000.0 / per[k], amp[k]) for k in range(49) if amp[k] > 0]


def sy_strum(name, spread=0.03, secs=1.5, seed=0, gain=1.0):
    """A chord strummed: its strings 30 ms apart, ringing `secs`, over hiss and hum."""
    import numpy as np
    notes = [ref.OPEN[s] + f for s, f in ref.CHORDS[name]]
    x = np.zeros(int((secs + 0.3) * 48000))
    for k, n in enumerate(notes):
        at = int((0.1 + k * spread) * 48000)
        s = ref.guitar(ref._hz(n), secs, amp=0.3, seed=seed + k, B=ref._stiff(n))
        x[at:at + len(s)] += s[:len(x) - at]
    return np.clip(ref.hiss(x, seed) * gain, -1, 1), notes


def sy_partials(notes, fmax=1450.0):
    out = []
    for n in notes:
        f0, B, k = ref._hz(n), ref._stiff(n), 1
        while k * f0 * (1 + B * k * k) ** 0.5 <= fmax:
            out.append(k * f0 * (1 + B * k * k) ** 0.5)
            k += 1
    return out


def sy_right(bands, notes, tol=30.0):
    """(amplitude on a partial of the notes within tol cents, all amplitude)."""
    import math
    parts = sy_partials(notes)
    right = sum(a for k, f, a in bands if min(abs(1200 * math.log2(f / p)) for p in parts) <= tol)
    return right, sum(a for k, f, a in bands)


def sy_checks(parent_img, img, man, kit_sym):
    import numpy as np
    import sy_ref
    sym = man['symbols']
    rng = random.Random(404)
    report['sy'] = {}
    # 1. When it plays: every page but the Sound Generator's, with EXT SOURCE on and ROUTING on ExtIn.
    m = SyMachine(img, man)
    lay = m.sl
    m.uc.mem_write(sym['sy_block'], b'\xA5' * lay.block_bytes)         # leftovers of an earlier run
    m.call(sym['sy_ui'])
    check(m.sy()['req'] == 0, 'before the UI has read EXT SOURCE and ROUTING: the engine not started')
    m.start()
    st = m.sy()
    check(st['req'] == 1 and st['starts'] == 1 and not any(m.bytes(sym['sy_block'], lay.block_bytes)),
          'main screen, EXT SOURCE on, ROUTING ExtIn: the engine cleared and handed over')
    st = m.step()
    check(st['state'] == SY_RUN and st['steps'] == 1 and st['fresh'] == 1 and
          m.get(sym['sy_block'] + lay.started, '<I') == 1 and st['out'] == [0] * 64,
          'RUN from the first block (silence in, silence out), its block ready for TX')
    sig = ref.to_blocks(sy_strum('G')[0])
    for b in range(200):
        st = m.step(sig[b])
    loud = max(abs(v) for v in st['out'])
    m.page(SG_PAGE)
    fade = []
    for k in range(10):
        st = m.step(sig[200 + k])
        fade.append((st['state'], st['stopping'], max(abs(v) for v in st['out']), st['out'][-1], st['fresh']))
    steps = st['steps']
    check(loud > 2000 and [f[0] for f in fade] == [SY_RUN] * 8 + [SY_OFF] * 2 and st['stops'] == 1 and
          fade[8][3] == 0 and fade[8][4] == 1 and fade[9][4] == 0 and all(f[2] > 0 for f in fade[1:8]) and
          m.step(sig[210])['steps'] == steps,
          f'the Sound Generator page: the engine fades out over 8 blocks (its last block ends at 0, added once), then '
          f'OFF, no more steps (peaks {[f[2] for f in fade]})')
    m.page(1)
    m.step(sig[211])
    st = m.step(sig[212])
    check(st['starts'] == 2 and st['state'] == SY_RUN and st['steps'] == steps + 1 and
          m.get(sym['sy_block'] + lay.started, '<I') == 1,
          'back on the main screen: cleared and started afresh')
    quiet = {}
    for label, kw, page in (('ROUTING Mix', dict(routing=0), 1), ('EXT SOURCE off', dict(ext=0), 1),
                            ('Sound Generator page', dict(), SG_PAGE)):
        q = SyMachine(img, man, page=page, **kw)
        q.start()
        for b in range(40):
            st = q.step(sig[b])
        quiet[label] = (st['req'], st['state'], st['steps'], st['starts'])
    d = SyMachine(img, man, page=DOOM_PAGE)
    d.start()
    st = d.step(sig[0])
    check(all(v == (0, SY_OFF, 0, 0) for v in quiet.values()) and st['state'] == SY_RUN,
          f'not on ROUTING Mix, not with EXT SOURCE off, not on the Sound Generator page; on any other page, '
          f'DOOM OS\'s too ({quiet})')
    mm = SyMachine(img, man)
    mm.start()
    for b in range(100):
        mm.step(sig[b])
    mm.routing = 0
    mm.ui(0)
    states = [mm.step(sig[100 + k])['state'] for k in range(12)]
    check(states[:8] == [SY_RUN] * 8 and states[9:] == [SY_OFF] * 3,
          f'ROUTING turned to Mix while it plays: it fades out and stops ({states})')
    # 2. The module against sy_ref.py, value for value, on the same blocks.
    bend = np.concatenate([np.zeros(4800), ref.guitar(ref._hz(55), 0.9, bend=(0.2, 0.5, 200)), np.zeros(2400)])
    # (signal, the notes whose partials should sound: none for the bend, whose pitch moves, and the clipped strum,
    # whose distortion adds tones of its own); each ends in 0.4 s of hiss and hum
    cases = [('four open strings', ref.open_strings((40, 50, 59, 64), ring=0.4, gap=0.1), (40, 50, 59, 64)),
             ('G strummed', *sy_strum('G')),
             ('C picked 0.25 s apart', *ref.arpeggio(ref.CHORDS['C'], 0.25, seed=2, extra=0.5)),
             ('G3 bent a tone', ref.hiss(bend, 3), ()),
             ('E strummed, clipped', sy_strum('E', secs=0.7, gain=4.0)[0], ()),
             ('hiss and hum alone', np.zeros(4800), ())]
    counter = [0]

    def every(uc, a_, s_, _):
        counter[0] += 1
    results, worst, mism = {}, 0, []
    for label, x, notes in cases:
        x = np.concatenate([x, ref.hiss(np.zeros(19200), 11)])
        mc = SyMachine(img, man)
        mc.start()
        eng = sy_ref.Engine()
        right = total = 0.0
        sounding, peak, nz_end = [], 0, None
        blocks = ref.to_blocks(x)
        for b, values in enumerate(blocks):
            mc.feed(values)
            h = mc.uc.hook_add(UC_HOOK_CODE, every)
            counter[0] = 0
            mc.call(sym['sy_rx'])
            mc.uc.hook_del(h)
            worst = max(worst, counter[0])
            got = list(struct.unpack('<64i', mc.bytes(sym['sy'] + lay.out, 256)))
            want, _ = eng.step(values)
            if got != want:
                mism.append((label, b))
            peak = max(peak, max(abs(v) for v in got))
            if any(got):
                nz_end = b
            if notes and b % 4 == 0:
                bd = mc.bands()
                sounding.append(len(bd))
                r, t = sy_right(bd, notes)
                right += r
                total += t
        results[label] = dict(blocks=len(blocks), share=round(right / total, 4) if total else None,
                              bands=round(sum(sounding) / len(sounding), 1) if sounding else 0, peak=peak,
                              last_sound_ms=None if nz_end is None else round((nz_end + 1) * 4 / 3),
                              length_ms=round(len(blocks) * 4 / 3))
    check(not mism, f'the module\'s output = sy_ref.py\'s, value for value, on every block of {len(cases)} signals '
                    f'({sum(r["blocks"] for r in results.values())} blocks; first differences {mism[:3]})')
    shares = {k: r['share'] for k, r in results.items() if r['share'] is not None}
    check(all(v >= 0.97 for v in shares.values()),
          f'the bands sounding are the strings\' partials (within 30 cents): {shares}')
    hh = results['hiss and hum alone']
    check(hh['peak'] == 0 and hh['last_sound_ms'] is None, 'hiss and hum alone (-74 / -66 dBFS): no sound at all')
    tails = {k: r['length_ms'] - r['last_sound_ms'] for k, r in results.items() if r['last_sound_ms'] is not None}
    check(all(v >= 200 for v in tails.values()),
          f'once the strings stop (each signal ends in 0.4 s of hiss and hum) the output goes to 0 within 0.2 s: ms of '
          f'silence at the end {tails}')
    check(worst <= 60000, f'the most instructions a step takes: {worst} ({worst / 8000:.1f}% of a block at one a '
                          f'cycle; the bands {", ".join(f"{k}: {r["bands"]}" for k, r in results.items())})')
    report['sy']['signals'] = results
    report['sy']['worst_step_instructions'] = worst
    # 3. Registers and stacks: the engine on the tracker's stack (test 2), every FPU register and FPSCR as they were.
    #    One step first: the model's first FPU instruction opens the task's FPU context and loads FPSCR from FPDSCR
    #    (0), as the audio task's own first one did long before (the tracker's check has its earlier steps for this).
    mr = SyMachine(img, man)
    mr.start()
    mr.step()
    fpu_ok = regs_ok = True
    stack_depth = task_depth = 0
    sig = ref.to_blocks(sy_strum('Am')[0])
    for b in range(60):
        pattern = [rng.getrandbits(32) for _ in range(32)]
        for k in range(32):
            mr.uc.reg_write(getattr(ar, f'UC_ARM_REG_S{k}'), pattern[k])
        fpscr = 0x00400000 | (b & 1) * 0x9F
        mr.uc.reg_write(ar.UC_ARM_REG_FPSCR, fpscr)
        gpr = [rng.getrandbits(32) for _ in range(8)]
        for k, v in enumerate(gpr):
            mr.uc.reg_write(getattr(ar, f'UC_ARM_REG_R{k + 4}'), v)
        mr.uc.mem_write(mr.block + mr.lay.b_stack, b'\xEE' * 2048)
        mr.uc.mem_write(STACK - 0x800, b'\xEE' * 0x800)
        mr.feed(sig[40 + b])
        mr.call(sym['sy_rx'])
        fpu_ok &= [mr.uc.reg_read(getattr(ar, f'UC_ARM_REG_S{k}')) for k in range(32)] == pattern and \
            mr.uc.reg_read(ar.UC_ARM_REG_FPSCR) & 0xF7C0009F == fpscr & 0xF7C0009F
        regs_ok &= [mr.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k + 4}')) for k in range(8)] == gpr
        stk = mr.bytes(mr.block + mr.lay.b_stack, 2048)
        stack_depth = max(stack_depth, 2048 - next(i for i in range(2048) if stk[i] != 0xEE))
        tsk = mr.bytes(STACK - 0x800, 0x800)
        task_depth = max(task_depth, 0x800 - next((i for i in range(0x800) if tsk[i] != 0xEE), 0x800))
    check(fpu_ok and regs_ok, 'SY: s0-s31, FPSCR and r4-r11 as they were after every step')
    check(0 < stack_depth <= 1536 and task_depth <= 96,
          f'SY: the step runs on the tracker\'s stack ({stack_depth} of 2,048 bytes); the task\'s stack sees '
          f'{task_depth} bytes (sy_rx\'s frame)')
    report['sy'].update(private_stack_bytes=stack_depth, task_stack_bytes=task_depth)
    # 4. TX: the block onto TX line 3's DRY pair (words 0/1 of each 16-word frame), clipped to 20 bits, once.
    st = mr.sy()
    basew = [rng.randint(-0x80000, 0x7FFFF) if rng.random() < 0.1 else rng.randint(-40000, 40000) for _ in range(1024)]
    mr.uc.mem_write(TXBUF, struct.pack('<1024i', *basew))
    mr.uc.mem_write(base.ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    mr.call(sym['sy_tx'], base.ARGS, 123456)
    got = list(struct.unpack('<1024i', mr.bytes(TXBUF, 4096)))
    exp = list(basew)
    for f in range(64):
        for w in (0, 1):
            exp[16 * f + w] = max(-0x80000, min(0x7FFFF, basew[16 * f + w] + st['out'][f]))
    mr.call(sym['sy_tx'], base.ARGS, 123456)
    again = list(struct.unpack('<1024i', mr.bytes(TXBUF, 4096)))
    st2 = mr.sy()
    check(any(st['out']) and st['fresh'] == 1 and got == exp and again == exp and st2['fresh'] == 0 and
          st2['tx'] == st['tx'] + 1 and st2['last_mix'] == 123456,
          'sy_tx adds the block to DRY L/R only (words 0/1 of TX line 3), clipped to 20 bits, once')
    mp, mw = Machine(parent_img), SyMachine(img, man)
    for x in (mp, mw):
        base.make_voices(x, 9090, occupancy=0.5)
        x.uc.mem_write(base.ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    mw.start()
    sig = ref.to_blocks(sy_strum('D')[0])
    for b in range(150):                                               # into the chord (it starts at 0.1 s)
        mw.step(sig[b])
    bad, heard = [], 0
    for n in range(4):
        st = mw.step(sig[150 + n])
        outs = []
        for x in (mp, mw):
            x.uc.mem_write(TXBUF, bytes(0x3000))
            x.call(base.MIXER, base.ARGS)
            outs.append(list(struct.unpack('<1024i', x.bytes(TXBUF, 4096))) + [x.bytes(TXBUF + 0x1000, 0x2000)])
        want = outs[0][:1024]
        for f in range(64):
            for w in (0, 1):
                want[16 * f + w] = max(-0x80000, min(0x7FFFF, want[16 * f + w] + st['out'][f]))
        heard += any(outs[0][:1024]) and any(st['out'])
        if outs[1][:1024] != want or outs[1][1024] != outs[0][1024]:
            bad.append(n)
    check(not bad and heard == 4, 'whole mixer with the engine\'s block ready: TX line 3 = the parent\'s + the block on '
                                  'DRY L/R, the other words and lines 1/2 the parent\'s (4 blocks)')
    # 5. SLOW: two wakes in a row over 9/10 (mixer + tracker + engine), or one step over the whole block.
    ms = SyMachine(img, man)
    ms.start()
    ms.step()
    hot = []
    for mix, step in ((300_000, 450_000), (300_000, 300_000), (300_000, 450_000), (300_000, 450_000)):
        ms.call(sym['sy_tx'], 0, mix)                                  # the mixer's cycles, as meter_mix_end hands them
        ms.cyc_step = step
        ms.feed([1000] * 64)
        ms.call(sym['sy_rx'])
        ms.cyc_step = 0
        st = ms.sy()
        hot.append((st['state'], st['hot']))
    check(hot == [(SY_RUN, 1), (SY_RUN, 0), (SY_RUN, 1), (SY_SLOW, 2)] and st['slow_cycles'] == 750_000 and
          st['fresh'] == 0,
          f'mixer + tracker + engine over 9/10 of the block twice in a row: SLOW; once, then a cooler wake: RUN on '
          f'({hot})')
    steps = ms.step()['steps']
    check(ms.step()['steps'] == steps and ms.sy()['state'] == SY_SLOW,
          'SLOW stays while the engine is wanted (no fade, no restart)')
    ms.page(SG_PAGE)
    ms.step()
    ms.step()
    ms.page(1)
    ms.step()
    ms.cyc_step = 850_000
    ms.feed([1000] * 64)
    ms.call(sym['sy_rx'])
    ms.cyc_step = 0
    st = ms.sy()
    check(st['state'] == SY_SLOW and st['slow_cycles'] == 850_000 and st['p_max'] == 850_000 and st['starts'] == 2,
          'left and back: started afresh; one step over the whole 800,000-cycle block: SLOW at once, the window so '
          'far published')
    report['sy']['tables'] = {k: round(float(v), 9) for k, v in sy_ref.G.items()}
    sy_tone_checks(img, man)


def sy_signal():
    """A strummed G chord (0.6 s) and a bent E4, over hiss and hum, ending in silence."""
    import numpy as np
    notes = [ref.OPEN[s] + f for s, f in ref.CHORDS['G']]
    x = np.zeros(int(0.5 * 48000))
    for k, n in enumerate(notes):
        at = int((0.05 + k * 0.03) * 48000)
        sg = ref.guitar(ref._hz(n), 0.45, amp=0.3, seed=k, B=ref._stiff(n))
        x[at:at + len(sg)] += sg[:len(x) - at]
    bend = ref.guitar(ref._hz(64), 0.35, bend=(0.08, 0.25, 200))
    return ref.hiss(np.concatenate([x, bend, np.zeros(4800)]), 3)


def sy_tone_checks(img, man):
    """SY test 2: the tones, the pick, a tone change."""
    import sy_ref
    sym = man['symbols']
    fde = man['guards']['fde']
    # 1. Every tone (picked before the start: the engine starts on it) against sy_ref.py, value for value.
    counter = [0]

    def every(uc, a_, s_, _):
        counter[0] += 1
    blocks = ref.to_blocks(sy_signal())
    mism, worst, peaks = [], {}, {}
    for tone in range(len(sy_ref.TONES)):
        mt = SyMachine(img, man)
        mt.put(sym['sy'] + mt.sl.tone_req, tone, '<I')
        mt.start()
        eng = sy_ref.Engine(tone)
        top = pk = 0
        for b, values in enumerate(blocks):
            mt.feed(values)
            if 40 <= b < 160 and b % 4 == 0:                           # counted where the chord rings fullest
                h = mt.uc.hook_add(UC_HOOK_CODE, every)
                counter[0] = 0
                mt.call(sym['sy_rx'])
                mt.uc.hook_del(h)
                top = max(top, counter[0])
            else:
                mt.call(sym['sy_rx'])
            got = list(struct.unpack('<64i', mt.bytes(sym['sy'] + mt.sl.out, 256)))
            want, _ = eng.step(values, bpm100=mt.sy()['bpm100'])
            pk = max(pk, max(abs(v) for v in want))
            if got != want:
                mism.append((tone, b))
        worst[sy_ref.TONES[tone]['name']] = top
        peaks[sy_ref.TONES[tone]['name']] = pk
    check(not mism and all(v > 1000 for v in peaks.values()),
          f'every tone: the module\'s output = sy_ref.py\'s, value for value ({len(sy_ref.TONES)} tones x '
          f'{len(blocks)} blocks; first differences {mism[:3]})')
    check(max(worst.values()) <= 100000,
          f'the most instructions a step takes, by tone: {worst} (the most is {max(worst.values()) / 8000:.1f}% of a '
          f'block at one a cycle)')
    report['sy']['tones'] = dict(worst_step_instructions=worst, peaks=peaks,
                                 names=[t['name'] for t in sy_ref.TONES])
    # 2. The pick: VALUE held + a pad, where the synth can play. FX deep edit's handlers (stubbed: they record the
    #    call and return 0) are asked first on a press, and on every release the pick did not take.
    down, up = int(fde['down']['handler'], 16), int(fde['up']['handler'], 16)
    mk = SyMachine(img, man)
    mk.stub(down, 0)
    mk.stub(up, 0)
    mk.start()
    width, line = base.font_widths(img)

    def key(fn, k):
        mk.uc.mem_write(SCRATCH + 0x200, struct.pack('<4h', 5, k, 0, 0))
        mk.log.clear()
        r = mk.call(sym[fn], SCRATCH + 0x200)
        return r, [(a, r0) for a, r0, *_ in mk.log]

    def value(held):
        b = mk.get(base.KEYS + 6, '<B')
        mk.put(base.KEYS + 6, (b | 2) if held else (b & ~2), '<B')

    mk.popups()
    value(False)
    plain = key('sy_key_down', 3)
    plain_up = key('sy_key_up', 3)
    value(True)
    mk.popups()
    took = key('sy_key_down', 3)
    text = mk.posted()
    st = mk.sy()
    released = key('sy_key_up', 3)
    st2 = mk.sy()
    other = key('sy_key_down', 0x22)                                   # EXIT with VALUE held: not a pad
    check(plain == (0, [(down, SCRATCH + 0x200)]) and plain_up == (0, [(up, SCRATCH + 0x200)]) and
          took == (1, [(down, SCRATCH + 0x200)]) and text == sy_ref.popup_name(3) and st['tone_req'] == 3 and
          st['taken'] == 8 and st['picks'] == 1 and released == (1, []) and st2['taken'] == 0 and
          other == (0, [(down, SCRATCH + 0x200)]),
          f'VALUE + pad 4: FX deep edit asked first, then tone 4 picked ({text!r}), the press and its release taken '
          f'(the release never reaches FX deep edit); a pad without VALUE, and VALUE + another key, go on as before')
    mk.popups()
    off = key('sy_key_down', 15)
    off_text = mk.posted()
    key('sy_key_up', 15)
    sig = ref.to_blocks(sy_strum('G')[0])
    states = [mk.step(sig[k])['state'] for k in range(12)]
    st = mk.sy()
    mk.popups()
    key('sy_key_down', 6)
    key('sy_key_up', 6)
    mk.step(sig[12])
    st3 = mk.step(sig[13])
    check(off[0] == 1 and off_text == 'SY OFF' and st['muted'] == 1 and states[-1] == SY_OFF and
          SY_RUN in states and st3['state'] == SY_RUN and st3['muted'] == 0 and st3['tone_req'] == 6 and
          st3['starts'] == 2 and mk.get(sym['sy_block'] + mk.sl.tone, '<I') == 6,
          f'VALUE + pad 16: SY OFF, the synth fades out and stops ({states}); VALUE + pad 7: on again, started '
          f'afresh on tone 7')
    quiet = []
    for label, kw, page in (('ROUTING Mix', dict(routing=0), 1), ('Sound Generator page', dict(), SG_PAGE)):
        q = SyMachine(img, man, page=page, **kw)
        q.stub(down, 0)
        q.start()
        q.put(base.KEYS + 6, 2, '<B')
        q.uc.mem_write(SCRATCH + 0x200, struct.pack('<4h', 5, 2, 0, 0))
        quiet.append((label, q.call(sym['sy_key_down'], SCRATCH + 0x200), q.sy()['tone_req']))
    check(all(r == 0 and t == 0 for _, r, t in quiet),
          f'where the synth cannot play (ROUTING Mix, the Sound Generator page) VALUE + pad goes on to the page '
          f'({quiet})')
    texts = [sy_ref.popup_name(p) for p in range(16)]
    widest = max(sum(width(c) for c in t) for t in texts)
    check(widest - 1 + 18 <= 128, f'every pick\'s popup fits the screen: widest {widest} px ({max(texts, key=len)!r})')
    # 3. A tone change while playing: out over 8 blocks, the new tone from rest, in over 8, value for value.
    mc = SyMachine(img, man)
    mc.stub(down, 0)
    mc.start()
    eng = sy_ref.Engine(0)
    blocks = ref.to_blocks(sy_strum('Am')[0])
    mism, fade = [], []
    for b, values in enumerate(blocks[:420]):
        if b == 200:
            mc.put(base.KEYS + 6, 2, '<B')
            mc.uc.mem_write(SCRATCH + 0x200, struct.pack('<4h', 5, 8, 0, 0))
            mc.call(sym['sy_key_down'], SCRATCH + 0x200)
        mc.feed(values)
        mc.call(sym['sy_rx'])
        got = list(struct.unpack('<64i', mc.bytes(sym['sy'] + mc.sl.out, 256)))
        want, _ = eng.step(values, tone_req=8 if b >= 200 else 0, bpm100=mc.sy()['bpm100'])
        if got != want:
            mism.append(b)
        if 198 <= b <= 218:
            fade.append((b, mc.get(sym['sy_block'] + mc.sl.tone, '<I'), max(abs(v) for v in got)))
    switched = next(b for b, t, _ in fade if t == 8)
    check(not mism and switched == 207 and fade[2][2] > 0 and fade[9][2] < fade[2][2],
          f'VALUE + pad 9 while playing: the output fades out over 8 blocks, tone 9 from block {switched}, fades in; '
          f'the module = sy_ref.py value for value across it (first differences {mism[:3]})')
    # 4. The builder's three calls: FX deep edit's bridges now call sy_key_down / sy_key_up / sy_knob.
    pairs = (('down', 'sy_key_down'), ('up', 'sy_key_up'), ('knob', 'sy_knob'))
    calls = {name: (mk.bytes(int(fde[name]['call'], 16), 4).hex(), fn) for name, fn in pairs}
    patched = [p for p in man['patches'] if 'FX deep edit' in p.get('what', '')]
    check(len(patched) == 3 and all(p['target'] == sym[fn] & ~1 and p['original_target'] == int(fde[n]['handler'], 16)
                                    for p, (n, fn) in zip(patched, pairs)) and
          all(mk.bytes(p['address'], 4).hex() == p['replacement_hex'] for p in patched),
          f'FX deep edit\'s bridges call sy_key_down, sy_key_up and sy_knob (bl), in place of its handlers {calls}')
    sy_knob_checks(img, man)


FILE_OPEN, FILE_READ, FILE_WRITE, FILE_CLOSE = 0x800DEC60, 0x800DEC48, 0x800DD9B8, 0x800DEBD8
VIEW_AT, TOP_OBJECT, FX_VIEW_VTABLE = 0x800A01C0, 0x80CFD350, 0x802269C0
SY_PATH = 'B:/_sy_tones.bin'


class Files:
    """The stock file calls (open, read, write, close) on a machine, on files kept here: path -> bytes."""
    def __init__(self, m, store=None):
        self.m, self.store, self.fds, self.writes = m, dict(store or {}), {}, []
        for a, fn in ((FILE_OPEN, self._open), (FILE_READ, self._read), (FILE_WRITE, self._write),
                      (FILE_CLOSE, self._close)):
            m.uc.hook_add(UC_HOOK_CODE, fn, begin=a, end=a)

    def _ret(self, uc, v):
        uc.reg_write(ar.UC_ARM_REG_R0, v & 0xFFFFFFFF)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    def _open(self, uc, a, s_, _):
        path = self.m.bytes(uc.reg_read(ar.UC_ARM_REG_R0), 64).split(b'\0')[0].decode('ascii')
        mode = uc.reg_read(ar.UC_ARM_REG_R1)
        if mode == 0 and path not in self.store:
            return self._ret(uc, -1)
        if mode:
            self.store[path] = b''
        fd = 3 + len(self.fds)
        self.fds[fd] = [path, 0]
        self._ret(uc, fd)

    def _read(self, uc, a, s_, _):
        fd, buf, n = (uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(3))
        path, pos = self.fds[fd]
        data = self.store[path][pos:pos + n]
        uc.mem_write(buf, data)
        self.fds[fd][1] += len(data)
        self._ret(uc, len(data))

    def _write(self, uc, a, s_, _):
        fd, buf, n = (uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(3))
        data = self.m.bytes(buf, n)
        self.store[self.fds[fd][0]] += data
        self.writes.append((self.fds[fd][0], data))
        self._ret(uc, n)

    def _close(self, uc, a, s_, _):
        self._ret(uc, 0)


def sy_file_bytes(tone, muted, knobs):
    """B:/_sy_tones.bin as sy_save writes it: "SYTN", version 1, tone, muted, 15, 45 knob positions, 3 zero, FNV-1a."""
    body = b'SYTN' + bytes([1, tone, muted, 15]) + bytes(64 + d for row in knobs for d in row) + bytes(3)
    h = 2166136261
    for c in body:
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return body + struct.pack('<I', h)


def sy_knob_checks(img, man):
    """SY test 3: the knobs and the file."""
    import sy_ref
    sym = man['symbols']
    fde = man['guards']['fde']
    down, up, knob = (int(fde[n]['handler'], 16) for n in ('down', 'up', 'knob'))
    ev = SCRATCH + 0x200

    def machine(store=None, **kw):
        x = SyMachine(img, man, store=store, **kw)
        for a in (down, up, knob):
            x.stub(a, 0)
        x.start()
        return x, x.files

    def send(x, fn, kind, k, pos=0):
        x.uc.mem_write(ev, struct.pack('<4h', kind, k, pos, 0))
        x.log.clear()
        r = x.call(sym[fn], ev)
        return r, [a for a, *_ in x.log]

    def value(x, held):
        b = x.get(base.KEYS + 6, '<B')
        x.put(base.KEYS + 6, (b | 2) if held else (b & ~2), '<B')
    # 1. VALUE + CTRL 1-3 on the picked tone (SUPERSAW): the knob's position, the popup, the turn taken.
    m, files = machine()
    value(m, True)
    send(m, 'sy_key_down', 5, 3)
    send(m, 'sy_key_up', 6, 3)
    m.popups()
    turned = send(m, 'sy_knob', 9, 2, 100)
    text = m.posted()
    st = m.sy()
    m.popups()
    bright = send(m, 'sy_knob', 9, 1, 0)
    level = send(m, 'sy_knob', 9, 3, 127)
    ctrl4 = send(m, 'sy_knob', 9, 4, 30)
    value(m, False)
    plain = send(m, 'sy_knob', 9, 2, 10)
    st2 = m.sy()
    check(turned == (1, [knob]) and text == 'SY 4 SUPERSAW\nDETUNE 100' and st['knob'][3] == [0, 36, 0] and
          st['dirty'] == 1 and bright[0] == 1 and level[0] == 1 and st2['knob'][3] == [-64, 36, 63] and
          ctrl4 == (0, [knob]) and plain == (0, [knob]) and st2['knob'][3][1] == 36,
          f'VALUE + CTRL 2 on SUPERSAW: FX deep edit\'s knob handler asked first, then DETUNE to the knob\'s 100 '
          f'({text!r}), the turn taken; CTRL 1 and 3 BRIGHT and LEVEL; CTRL 4, and a turn without VALUE, go on')
    # 2. The file: written when VALUE is let go after the change, not with an FX screen up.
    m.put(TOP_OBJECT, SCRATCH + 0x400, '<I')
    m.put(SCRATCH + 0x600, FX_VIEW_VTABLE, '<I')
    shown = [True]

    def view_at(uc, a, s_, _):
        i = uc.reg_read(ar.UC_ARM_REG_R1)
        uc.reg_write(ar.UC_ARM_REG_R0, SCRATCH + 0x600 if (shown[0] and i == 0) else 0)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))
    m.uc.hook_add(UC_HOOK_CODE, view_at, begin=VIEW_AT, end=VIEW_AT)
    value(m, True)
    send(m, 'sy_key_down', 5, 0x31)
    rel = send(m, 'sy_key_up', 6, 0x31)
    held_back = (len(files.writes), m.sy()['dirty'])
    shown[0] = False
    rel2 = send(m, 'sy_key_up', 6, 0x31)
    st3 = m.sy()
    want = sy_file_bytes(3, 0, st3['knob'])
    check(held_back == (0, 1) and rel == (0, [up]) and rel2 == (0, [up]) and
          files.writes == [(SY_PATH, want)] and st3['dirty'] == 0 and st3['saves'] == 1,
          f'VALUE let go with an FX screen up: no file yet; with none, {SY_PATH} written once ({len(want)} bytes: '
          f'"SYTN", version 1, tone 4, the 45 knobs, FNV-1a), the release still FX deep edit\'s')
    # 3. A fresh start with that file: read at the first key event; the tone and knobs back; the engine as the twin.
    mf, f2 = machine({SY_PATH: want})
    before = mf.sy()['loaded']
    send(mf, 'sy_key_down', 5, 0x12)                                   # EXT SOURCE: any key reads the file first
    st4 = mf.sy()
    eng = sy_ref.Engine(3)
    eng.knobs[3] = st4['knob'][3]
    mf.call(sym['sy_ui'])
    mism = []
    blocks = ref.to_blocks(sy_strum('G')[0])
    for b, values in enumerate(blocks[:300]):
        mf.feed(values)
        mf.call(sym['sy_rx'])
        got = list(struct.unpack('<64i', mf.bytes(sym['sy'] + mf.sl.out, 256)))
        if got != eng.step(values, bpm100=mf.sy()['bpm100'])[0]:
            mism.append(b)
    check(before == 0 and st4['loaded'] == 1 and st4['loads'] == 1 and st4['tone_req'] == 3 and
          st4['knob'][3] == [-64, 36, 63] and not mism,
          f'a fresh start with the file: read at the first key event (EXT SOURCE), tone 4 and its knobs back, the '
          f'engine = sy_ref.py with them, value for value (300 blocks; first differences {mism[:3]})')
    bad = bytearray(want)
    bad[20] ^= 1
    mb, f3 = machine({SY_PATH: bytes(bad)})
    send(mb, 'sy_key_down', 5, 0x12)
    mn, f4 = machine()
    send(mn, 'sy_knob', 9, 2, 50)
    sb, sn = mb.sy(), mn.sy()
    check(sb['bad_files'] == 1 and sb['loads'] == 0 and sb['tone_req'] == 0 and all(r == [0, 0, 0] for r in sb['knob'])
          and sn['loaded'] == 1 and sn['loads'] == 0 and sn['bad_files'] == 0 and not f4.writes,
          'a file whose sum is wrong is ignored (the tones as designed); no file: nothing read, nothing written yet')
    # 4. The popups fit the screen: the tone's line and the setting's at the knob's top.
    width, line = base.font_widths(img)
    texts = [f'{sy_ref.popup_name(t)}\n{n} 127' for t in range(len(sy_ref.TONES))
             for n in ('BRIGHT', sy_ref.TONE[t]['p2name'], 'LEVEL')]
    widest = max(sum(width(c) for c in ln) for t in texts for ln in t.split('\n'))
    check(widest - 1 + 18 <= 128 and 2 * line - 1 + 8 <= 64,
          f'every knob popup fits the screen: widest line {widest} px')
    report['sy']['knobs'] = dict(p2=[t['p2name'] for t in sy_ref.TONE], file=SY_PATH, file_bytes=len(want),
                                 widest_popup_px=widest)


def entry_checks(parent_img, img, sym):
    """test_nam_test.entry_checks, but at the popup tick's resume point LR is not compared (SY test 2). Bounce's ui
    bridge runs the stock prologue's push {r4, r5, r6, lr} before it calls diag_ui (checked here), and the stock
    body ends with pop {r4, r5, r6, pc}: LR is dead there. diag_ui's last call (since test 2 the tempo function's,
    from sy_ui) leaves its own return address in it; test 1's LR matched the parent's only because no call came
    last."""
    out = {}
    for name, start, resume, entry_regs in (
            ('mixer', base.MIXER, 0x1C2DC, {'R0': base.ARGS, 'R1': 0x11, 'R2': 0x22, 'R3': 0x33}),
            ('popup tick', base.UI_TICK, 0x8006B95C, {'R0': 1, 'R1': 0x11, 'R2': 0x22, 'R3': 0x33})):
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
            res.append((got, m.bytes(sp, STACK - sp), m))
        (gp, fp, mp), (gm, fm, mm) = res
        if name == 'mixer':
            st = base.meter_state(mm, sym['meter'])
            exit_ = sym['meter_mix_exit'] | 1
            same = all(gp[r] == gm[r] for r in ('R0', 'R1', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'SP', 'PC'))
            frame_ok = len(fp) == len(fm) and fp[:-4] == fm[:-4] and struct.unpack('<I', fm[-4:])[0] == exit_ and \
                struct.unpack('<I', fp[-4:])[0] == 0x1D09B
            check(same and frame_ok and st['mix_ret'] == 0x1D09B,
                  'mixer entry: registers and frame as stock, return routed through meter_mix_exit')
        else:
            import capstone
            same = all(gp[r] == gm[r] for r in ('R0', 'R1', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'SP', 'PC'))
            md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
            head = [f'{i.mnemonic} {i.op_str}' for i in md.disasm(mm.bytes(0x83FE8080, 8), 0x83FE8080)]
            check(same and fp == fm and head[:1] == ['push {r4, r5, r6, lr}'],
                  "popup tick entry through bounce's ui bridge (diag_ui): registers (but the dead LR) and frame as "
                  "the parent's (bnc_ui alone); the bridge saves LR before the call")
        out[name] = dict(stock_sp=hex(gp['SP']), meter_sp=hex(gm['SP']))
    report['entries'] = out


# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--kits', type=Path, required=True, help="the kit stage's kits-manifest.json (arp_symbols)")
    ap.add_argument('--seeds', type=int, default=12)
    ap.add_argument('--blocks', type=int, default=6)
    ap.add_argument('--mixer-runs', type=int, default=4)
    ap.add_argument('--only', help='comma-separated: static,tune,synth,sy,meter (default all)')
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
    only = set((a.only or 'static,tune,synth,sy,meter').split(','))
    if 'static' in only:
        static_checks(out, man, parent_img, img)
    if 'tune' in only:
        tracker_checks(parent_img, img, man)
    if 'synth' in only:
        synth_checks(img, man, kit_sym)
    if 'sy' in only:
        sy_checks(parent_img, img, man, kit_sym)
    if 'meter' in only:
        entry_checks(parent_img, img, sym)
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
