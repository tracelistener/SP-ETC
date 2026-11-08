"""Checks for SY synth test 5 with guitar synth test 6 (build_tune_test.py): the CPU meter as in cabinet test 2, the
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
     sy_block in its own zeroed slot;
   - test 4: VALUE + EXT SOURCE opens the picker (taken with EXT SOURCE on, on to stock with it off; FX deep edit never
     sees it; the pads lit), a pad picks, pad 16 puts the synth off and closes it, CTRL 1-3 edit there; EXIT, the chord,
     another page or key, 4 s close it; VALUE hands on to FX deep edit's input FX chord; VALUE + pad and VALUE + CTRL go
     on as stock; the file at the closing key or the next release (never from the tick, never with an FX screen up);
     the chip held on ExtIn while a synth listens (a ROUTING DT1 out as ExtIn, others untouched on the caller's stack),
     ROUTING Mix playing, the user's value back after; sy_feed: the pairs before the feed, then pair 1 x 2 on Mix /
     the synth added on ExtIn / nothing when the feed takes another pair, 30 ms grace;
   - test 5 (the picker above is gone): EXT SOURCE held + RECORD SETTING opens the guitar synth screen (taken, the SG
     page asked for, the input put on); there pads (hits and key presses), SUB PAD, VALUE's push and REC are taken and
     never reach note repeat's handler (no sample), a pad or CTRL 1 picks SOUND (zones), VALUE steps it, CTRL 2/3 and
     the SHIFT page (tap; held) edit TONE, LEVEL, OCTAVE, the tone's own setting, SUSTAIN; the columns, footer and bar
     drawn through the stubbed stock drawing calls, the page's update drawing them again once; outside the screen every
     draw and bridge hands on (the arp's with every register as it came); SHIFT + RECORD SETTING and another page close
     it; the file version 2 (OCTAVE, SUSTAIN) at a key release, read back, a version 1 file ignored; every tone with
     OCTAVE and SUSTAIN turned value for value; the engine's FUND, SUSTAIN and OCTAVE in the twin.

Not a hardware test: no timing (instructions are counted as a proxy), no screen, synthetic strings.
"""
from __future__ import annotations

import argparse
import json
import random
import struct
import sys
from pathlib import Path

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import arm_const as ar

import test_nam_test as base
from test_nam_test import (Machine, check, sha, scatter, FLASH, COPY, STACK, RET, SCRATCH, TXBUF, CAPTURE, SYSPRM,
                           SYS_GET, SETTINGS_OBJ, SET_GET, CUR_TASK, TCB, M_SHOWN, skip_spans)

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tunetest'))
import tune_ref as ref  # noqa: E402

TT_OFF, TT_RUN, TT_SLOW = range(3)
TT_HEAD = 'req fx ext routing checked checks starts posted_rseq state rx steps task_attr last_mix'.split()
ROUTING, EXTIN = 0x5C, 1           # system 0x5c, INPUT SETTING's ROUTING: 0 Mix, 1 ExtIn
TT_MID = 'w_n w_sum w_max w_tot seq p_blocks p_avg p_max p_tot_max tot_max_ever over slow_cycles hot reset_req reset_ack rseq'.split()
# SY test 4: the hold and the recorder, after drum
TT_TAIL = ('hold hold_at rec_mix rec_ext grace grace_at holds route_sends route_held route_last rec_blocks rec_adds '
           'rec_other').split()
FEED_PAIR1, FEED_PAIR = 0x82E011A8, 0x82E0E974     # the recorder feed takes pair 1 if the first is set, else this pair
LED, LED_REFRESH = 0x800D4910, 0x802496F0          # the key light (key, mode, level); |= 2: stock paints the pads
FEED_FN = 0x0001CA80
HOLD_SETTLE, REC_GRACE = 12_000_000, 18_000_000    # 20 ms, 30 ms
report = base.report
PACKET = TXBUF + 0x6000


class Layout:
    """tt_t and tt_block_t offsets, from the module's tt_layout table."""
    def __init__(self, m, sym):
        v = struct.unpack('<23I', m.bytes(sym['tt_layout'], 92))
        (self.tt_bytes, self.state, self.peak, self.inp, self.w_n, self.pub, self.tot_max_ever, self.reset_ack,
         self.rseq, self.res, self.res_bytes, self.block_bytes, self.b_ring, self.b_span, self.b_d6, self.b_peaks,
         self.b_z, self.b_started, self.b_stack, self.posted_rseq, self.b_pick, self.b_env, self.hold) = v
        self.syn = self.res + self.res_bytes
        check(self.state == 4 * TT_HEAD.index('state') and self.posted_rseq == 4 * TT_HEAD.index('posted_rseq') and
              self.peak == 4 * len(TT_HEAD) and self.inp == self.peak + 8 and self.w_n == self.inp + 128 and
              self.pub == self.w_n + 20 and self.rseq == self.w_n + 4 * (len(TT_MID) - 1) and
              self.res == self.rseq + 4 and self.res_bytes == 4 * len(ref.RESULT) and
              self.hold == self.syn + 8 and self.tt_bytes == self.hold + 4 * len(TT_TAIL) and
              self.b_pick + 16 <= self.b_stack and self.b_env + 24 <= self.b_stack,
              'tt_t layout as the test reads it (syn, drum, then SY test 4\'s hold and recorder fields at the end)')


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
    st.update(zip(TT_TAIL, struct.unpack(f'<{len(TT_TAIL)}I', m.bytes(t + lay.hold, 4 * len(TT_TAIL)))))
    return st


# ---------------------------------------------------------------------------------------------
def static_checks(out, man, parent_img, img):
    check(sha(img) == man['sha256'] and len(img) == man['size'], 'APP1 matches the manifest')
    check(sha((out / 'SP404MKII_APP0.bin').read_bytes()) == man['app0_sha256'], 'APP0 is stock 5.52')
    rows_p, rows = scatter(parent_img), scatter(img)
    new_row = [FLASH + man['module_file_offset'], man['module_base'], man['module_size'], COPY]
    st = man['sytext']
    text_row = [FLASH + st['file_offset'], st['address'], st['size'], COPY]
    zero_rows = [[0, r['address'], r['size'], base.ZERO] for r in man['rows_added'] if r['kind'] == 'zero']
    added = [[0, r['address'], r['size'], base.ZERO] if r['kind'] == 'zero' else
             [FLASH + r.get('file_offset', man['module_file_offset']), r['address'], r['size'], COPY]
             for r in man['rows_added']]
    sv = man['syv']
    in_slots = all(lo <= r['address'] and r['address'] + r['size'] <= hi for r, (lo, hi) in
                   zip(man['rows_added'][3:], (sv['text']['slot'], sv['notes']['slot'], sv['data']['slot'],
                                               sv['state']['slot'])))
    check(rows == rows_p + added and added[:2] == [new_row, text_row] and len(zero_rows) == 2 and
          zero_rows[0][1] == man['symbols']['sy_block'] and zero_rows[1][1] == sv['state']['used'][0] == 0x83FE4800 and
          st['address'] == 0x83FE6C00 and st['address'] + st['size'] <= 0x83FE8000 and
          zero_rows[0][1] + zero_rows[0][2] <= st['address'] and in_slots and
          sha(img[st['file_offset']:st['file_offset'] + st['size']]) == st['sha256'] and
          all(sha(img[r['file_offset']:r['file_offset'] + r['size']]) == sv[k]['sha256']
              for r, k in zip(man['rows_added'][3:6], ('text', 'notes', 'data'))),
          'scatter table = parent rows + the module row + the screen code\'s row (SY test 5, .sytext in the SY slot) + '
          'sy_block\'s zero row (SY test 3) + SY test 11\'s voice engine: three copy rows (its code, its notes, its '
          'constants) and its state\'s zero row, each inside its slot')
    # SY test 22: the stock copy and zero handlers (0x600800e4, 0x60080100) move 16-, 8- and 4-byte pieces and drop a
    # row's last size % 4 bytes; tests 20 and 21 lost b_start's closing bx lr that way
    check(all(r['size'] % 4 == 0 and r['address'] % 4 == 0 for r in man['rows_added']),
          'every boot row this build adds is whole words (the stock copy drops a row\'s last size % 4 bytes)')
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
        # SY test 4: what reaches FX deep edit's fde_dt1 (sy_dt1 goes there) is recorded as (ID, index, value) and
        # goes no further (the stock builder talks to the chip); the recorder feed records the packet's pairs 0 and 1
        # as it finds them (r0) and returns 1; the key light records (key, mode, level).
        self.dt1, self.dt1_sp, self.feeds, self.leds = [], [], [], []
        self.fde_dt1 = int(man['dt1_hook']['fde_dt1'], 16)
        self.uc.hook_add(UC_HOOK_CODE, self._dt1, begin=self.fde_dt1, end=self.fde_dt1)
        self.uc.hook_add(UC_HOOK_CODE, self._feed, begin=FEED_FN, end=FEED_FN)
        self.uc.hook_add(UC_HOOK_CODE, self._led, begin=LED, end=LED)

    def _dt1(self, uc, a, s, _):
        self.dt1.append(tuple(uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(4)))
        self.dt1_sp.append(uc.reg_read(ar.UC_ARM_REG_SP))
        uc.reg_write(ar.UC_ARM_REG_R0, 0)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    def _feed(self, uc, a, s, _):
        r0, r1 = uc.reg_read(ar.UC_ARM_REG_R0), uc.reg_read(ar.UC_ARM_REG_R1)
        pk = struct.unpack('<1024h', self.bytes(r0, 2048))
        self.feeds.append((r0, r1, [pk[16 * f:16 * f + 4] for f in range(64)]))
        uc.reg_write(ar.UC_ARM_REG_R0, 1)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    def _led(self, uc, a, s, _):
        self.leds.append(tuple(uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(3)))
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    def routing_dt1(self):
        """The ROUTING values sent so far (DT1 ID 0x5c, BMC context, index 0)."""
        return [v for c, i, x, v in self.dt1 if i == ROUTING and c == 0x80592500 and x == 0]

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
        """The UI's 0.1 s check, then another tick 20 ms on (SY test 4: the chip's hold settled by then)."""
        self.put(self.sym['meter'] + M_SHOWN, shown)
        self.cyc += advance
        self.call(self.sym['tune_ui'])
        self.cyc += HOLD_SETTLE + 1
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
    # 6. SY test 4: bounce's rx bridge calls sy_feed in place of the feed (the packet in r0, 0x800 in r1, as the RX
    #    site leaves them): pairs 0 and 1 read from that packet, then the feed with the same r0/r1; diag_rx after it
    #    no longer reads them. (Test 3: diag_rx read them from r6/r9.)
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
    ret = mq.call(sym['sy_feed'], rxbase + 0x800, 0x800)
    st = mq.tt()
    want_in = [(packet[16 * f] + packet[16 * f + 1]) >> 1 for f in range(64)]
    p0 = max(max(abs(packet[16 * f]), abs(packet[16 * f + 1])) for f in range(64))
    fed = mq.feeds[-1] if mq.feeds else None
    mq.put(sym['tt'] + lay.inp, 0, '<I')
    mq.call(sym['diag_rx'])
    check(st['in'] == want_in and st['peak'] == [p0, 3000] and ret == 1 and fed is not None and
          fed[:2] == (rxbase + 0x800, 0x800) and [list(x) for x in fed[2]] == [packet[16 * f:16 * f + 4] for f in range(64)]
          and mq.tt()['in'][:2] == [0, 0],
          f"sy_feed (in place of the feed): pair 0's (L + R) >> 1 and the peaks of pairs 0 and 1 from the packet it is "
          f"given ({st['peak']}), then the feed with the same r0 and r1, the packet as it was (no hold change on "
          f"ROUTING ExtIn with no synth block), its return passed back; diag_rx after it reads no pairs")
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


def kit_note(note):
    """SY test 6: drum mode's pad for a guitar note: the open low E pad 1 (36), a pad a fret to G3 on pad 16 (51), the
    notes outside an octave nearer at a time."""
    v = note - 40
    while v < 0:
        v += 12
    while v > 15:
        v -= 12
    return 36 + v


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
                n = kit_note(note) if drum else note + 12 * max(-3, min(4, oct))
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
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [36] and len(r.seen) >= 2,
          f"drum mode (kit_mode set, OCT +2), the hammer-on: the steady note moves ({[ref.name(n) for n in r.seen]}) "
          f"but only the pick plays, one hit: SY test 6, the open low E on pad 1 (note 36) ({r.ons()})")
    r = Run(img, man, one_string((40, 40, 43, 45, 40), 0.25, seed=20), drum=True)
    check(r.ms.midi == r.model and [n for n, _ in r.ons()] == [36, 36, 39, 41, 36],
          f'drum mode, the riff: a hit for every pick, SY test 6\'s pads (E2 pad 1, G2 pad 4, A2 pad 6) ({r.ons()})')
    pads = [kit_note(n) for n in (40, 43, 52, 55, 56, 64, 76, 88, 38)]
    check(pads == [36, 39, 48, 51, 40, 48, 48, 48, 46],
          f'SY test 6, the kits\' note-to-pad map: E2 pad 1, G2 4, E3 13, G3 16, G#3 an octave down (5), E4, E5, E6 13, '
          f'drop-D D2 an octave up (11) ({pads})')
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
    # 10. Test 5 played only on ROUTING ExtIn (on Mix the effects chip hands back the mix as heard, and the synth heard
    #     its own note: tests 2-4 on the unit). SY test 4: with EXT SOURCE on the chip is held on ExtIn whatever
    #     ROUTING says, so the page plays on Mix too, 20 ms after the hold went out; no popup any more.
    mm = SynthMachine(img, man, routing=0)
    mm.popups()
    mm.ui(0)
    hold_st = mm.tt()
    sends = mm.routing_dt1()
    posts = []
    for b in range(600):
        st = mm.tick(sig[b])
        if mm.posted() is not None:
            posts.append((b, mm.posted()))
    check(hold_st['hold'] == 1 and hold_st['holds'] == 1 and sends == [1] and hold_st['rec_mix'] == 1 and
          hold_st['rec_ext'] == 0 and st['state'] == TT_RUN and mm.midi and mm.midi[0][2] == 40 and not posts,
          f"ROUTING Mix, EXT SOURCE on, the Sound Generator page: the chip held on ExtIn (one ROUTING DT1, value 1: "
          f"{sends}), the recorder given the mix; the tracker runs and the pluck plays ({mm.midi[:1]}); no popup "
          f"({posts})")
    mw = SynthMachine(img, man, routing=0)
    mw.cyc += 60_000_001
    mw.call(mw.sym['tune_ui'])                                            # the check: EXT SOURCE on, the hold sent
    early = mw.tt()
    mw.cyc += HOLD_SETTLE - 1_000
    mw.call(mw.sym['tune_ui'])
    early2 = mw.tt()
    mw.cyc += 2_000
    mw.call(mw.sym['tune_ui'])
    late = mw.tt()
    check(early['hold'] == 1 and early['req'] == 0 and early2['req'] == 0 and late['req'] == 1 and
          mw.routing_dt1() == [1],
          'the Sound Generator page waits 20 ms after the hold before its tracker listens (the chip switches first)')
    mm.ext = 0
    mm.ui(0)
    for _ in range(3):
        st = mm.tick()
    off = mm.tt()
    check(off['hold'] == 0 and mm.routing_dt1() == [1, 0] and off['grace'] == 1 and off['rec_mix'] == 1 and
          st['state'] == TT_OFF,
          f"EXT SOURCE off: the hold lets go, the user's ROUTING (Mix) sent back ({mm.routing_dt1()}); the recorder "
          f"keeps the mix 30 ms while the chip switches back; the tracker stops")
    mm.cyc += REC_GRACE
    mm.call(mm.sym['tune_ui'])
    check(mm.tt()['grace'] == 0 and mm.tt()['rec_mix'] == 0,
          'after 30 ms the recorder takes pair 0 as stock again')
    mx = SynthMachine(img, man)
    mx.ui(0)
    b = 0
    while not mx.midi and b < 600:
        mx.tick(sig[b])
        b += 1
    on = list(mx.midi)
    mx.ext = 0
    mx.ui(0)
    for k in range(3):
        st = mx.tick(sig[b + k])
    check(len(on) == 1 and on[0][2] == 40 and on[0][4] == 0 and st['state'] == TT_OFF and
          mx.midi[1:] == [(on[0][0] + 1, 2, 40, 0, 1)] and mx.gsyn()['sounding'] == -1,
          f'a note playing when EXT SOURCE goes off: let go at the next UI tick ({mx.midi})')
    mr = SynthMachine(img, man, routing=0, ext=0)
    mr.ui(1)
    for values in ref.to_blocks(ref.open_strings((40, 45), ring=0.8))[:1200]:
        st = mr.tick(values)
    check(st['state'] == TT_RUN and st['res']['locks'] >= 1 and not mr.midi and mr.gsyn()['sounding'] == -1 and
          mr.tt()['hold'] == 0 and not mr.routing_dt1(),
          f"the readout shown on the page with EXT SOURCE off: the tracker runs for it ({st['res']['locks']} steady "
          f"notes), nothing plays, no hold ({len(mr.midi)} calls)")
    report['synth']['routing'] = dict(hold='EXT SOURCE on: ROUTING DT1s go out as ExtIn; 20 ms settle')
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
# SY synth tests 1 to 5: the 49-band engine (sy_fp.c), its glue (tune_test.c: sy_ui, sy_rx, sy_tx, the file, test 5's
# screen through sy_event and the SG page's widgets) and its twin (sy_ref.py).
SY_OFF, SY_RUN, SY_SLOW = range(3)
SY_PLAIN = 10                      # SY test 11: PUNCH BASS, mono with a short release (the engine's own checks run on it)
SY_NT = 20                         # SY test 11: the tones (sy_voices.py's VOICES)
SY_STEP_MAX = 120000               # SY test 17: instructions a step may take (6 voices: measured 44-105k, 13% of a block;
#                                    test 11: 100000 for 44-91k with 4; tests 1-10: 60000 / 100000)
SY_HEAD = 'req starts stops reset_req tone_req muted picks taken bpm100 tempo_checked'.split()
SY_FILE = 'loads saves save_errors bad_files'.split()
SY_RUNF = 'state rx steps tx fresh stopping sounding last_mix'.split()
SY_KNOB_AT = 4 * len(SY_HEAD)                  # test 3: s8 knob[20][3], dirty, loaded, two pad bytes; oct, susk, dynk
SY_FILE_AT = SY_KNOB_AT + 124                  # SY test 11: 20 tones (60 + 4 + 3 x 20)
SY_RUN_AT = SY_FILE_AT + 4 * len(SY_FILE)
SY_OUT_AT = SY_RUN_AT + 4 * len(SY_RUNF)
SY_TAIL = ('w_n w_sum w_max w_tot seq p_blocks p_avg p_max p_tot_max tot_max_ever over slow_cycles hot reset_ack '
           'run_steps').split()
SY_SCREEN = 'mode mode_at rev drawn_rev bar_rev bar_drawn taken_hi pads_taken'.split()   # test 5, then 4 bytes,
SY_COUNTS = 'enters leaves pads_ate turns vsteps foot foot_vt'.split()   # these; SY test 6: rem_down, rem_fx,
SY_REM = 'rem_taps rem_holds fx_passes sg_page rec_fresh'.split()          # two pad bytes, these, then rec[64]
KEY_EXT, KEY_EXIT, KEY_VALUE = 0x12, 0x22, 0x31
KEY_SUB_PAD, KEY_REC_SET, KEY_REC, KEY_SHIFT = 0x13, 0x16, 0x1B, 0x2A
KEY_REMAIN, KEY_FX1, KEY_MFX = 0x24, 0x2B, 0x30                          # SY test 6
KEY_DOWN_FN, KEY_UP_FN, FX_FROZEN = 0x8003ABD0, 0x8003ADA0, 0x80592320
EV_KEY, EV_KEY_UP, EV_ENC, EV_KNOB, EV_PAD, EV_PAD_UP = 5, 6, 7, 9, 0x10, 0x11
PAGE_REQ, SET_SET = 0x800DA598, 0x800DD0C0
F_COLOR, F_RECT, F_FONT, F_TEXT, INVALIDATE = 0x800D8018, 0x800CE580, 0x800D80D8, 0x800D4FA0, 0x800D0018
BAR_END, BAR_DRAWN = 0x800BBCC2, 0x80123C5A
WIDGET, FOOTER, FB, FOOTER_VT = SCRATCH + 0x800, SCRATCH + 0x900, 0x12345670, 0x80227000
BAR_BUF, BAR_SCREEN, BAR_DRAW_ARGS = SCRATCH + 0xC00, SCRATCH + 0xD00, (0x111, 0x222, 0x333, 0x444)
BAR_Y0, BAR_Y1 = 41, 51                                                  # SY test 6: the item box's rows (any)
EV = SCRATCH + 0x200
DOOM_PAGE = 0x60                   # a page above the stock ones (DOOM OS's own screens)


class SyLayout:
    """sy_t and sy_block_t offsets, from the module's sy_layout table."""
    def __init__(self, m, sym):
        v = struct.unpack('<32I', m.bytes(sym['sy_layout'], 128))
        (self.sy_bytes, self.state, self.out, self.w_n, self.pub, self.tot_max_ever, self.block_bytes, self.e,
         self.per, self.ph, self.amp, self.owned, self.env, self.started, self.tone, self.nper, self.tone_req,
         self.fe, self.knob, self.dirty, self.loads, self.mode, self.rec, self.oct, self.susk, self.fund_cut,
         self.dynk, self.rem_down, self.hold, self.out_bus, self.armed, self.trk) = v
        check(self.state == SY_RUN_AT and self.out == SY_OUT_AT and self.knob == SY_KNOB_AT and
              self.dirty == SY_KNOB_AT + 60 and self.oct == SY_KNOB_AT + 64 and self.susk == self.oct + 20 and
              self.dynk == self.susk + 20 and self.loads == SY_FILE_AT and
              self.w_n == self.out + 256 and self.pub == self.w_n + 20 and self.tot_max_ever == self.pub + 16 and
              self.mode == self.tot_max_ever + 24 and self.rem_down == self.mode + 64 and self.rec == self.mode + 88 and
              self.trk == self.rec + 128 and self.sy_bytes == self.trk + 4 and
              self.tone_req == 4 * SY_HEAD.index('tone_req') and
              self.started + 12 <= self.block_bytes and self.fund_cut + 4 <= self.block_bytes and
              self.hold + 49 <= self.block_bytes and self.out_bus == self.rem_down + 2 and
              self.armed == self.rem_down + 3,
              'sy_t and sy_block_t layout as the test reads it (SY test 6: DYNAMICS, REMAIN, the bands\' hold; SY '
              'test 15: the TRACK page\'s trk at the end)')


class SyMachine(SynthMachine):
    """SynthMachine on the main screen, its RX block running tune_rx then sy_rx (as diag_rx_c), then the UI tick's
    syn_ui and sy_ui. Test 5: UI events go in through sy_event (note repeat's handler, nr_event_c, stubbed: it records
    what reaches it and returns 0); the page request and the settings setter recorded (EXT SOURCE follows the setter)."""
    def __init__(self, img, man, page=1, store=None, armed=True, **kw):
        super().__init__(img, man, page=page, **kw)
        self.sl = SyLayout(self, self.sym)
        if armed:                                      # SY test 8: as if the guitar synth screen had been opened
            self.put(self.sym['sy'] + self.sl.armed, 1, '<B')
        self.files = Files(self, store)                # test 3: the stock file calls, on files kept in Python
        self.passed, self.requests, self.sets, self.stock_keys = [], [], [], []
        nr = int(man['nr_hook']['nr_event_c'], 16)
        self.uc.hook_add(UC_HOOK_CODE, self._nr, begin=nr, end=nr)
        for a in (KEY_DOWN_FN, KEY_UP_FN):                 # SY test 6: the stock key press and release, recorded
            self.uc.hook_add(UC_HOOK_CODE, self._stock_key, begin=a, end=a)
        self.uc.hook_add(UC_HOOK_CODE, self._req, begin=PAGE_REQ, end=PAGE_REQ)
        self.uc.hook_add(UC_HOOK_CODE, self._set, begin=SET_SET, end=SET_SET)

    def _ret(self, uc, v=0):
        uc.reg_write(ar.UC_ARM_REG_R0, v & 0xFFFFFFFF)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))

    def _nr(self, uc, a, s, _):
        self.passed.append(struct.unpack('<3h', self.bytes(uc.reg_read(ar.UC_ARM_REG_R0), 6)))
        self._ret(uc)

    def _req(self, uc, a, s, _):
        self.requests.append(uc.reg_read(ar.UC_ARM_REG_R0))
        self._ret(uc)

    def _stock_key(self, uc, a, s, _):
        self.stock_keys.append(struct.unpack('<3h', self.bytes(uc.reg_read(ar.UC_ARM_REG_R0), 6)))
        self._ret(uc)

    def _set(self, uc, a, s, _):
        args = tuple(uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(1, 4))
        self.sets.append(args)
        if args[0] == 0x25:
            self.ext = args[1]
        self._ret(uc)

    def sy(self):
        s = self.sym['sy']
        st = dict(zip(SY_HEAD, struct.unpack(f'<{len(SY_HEAD)}I', self.bytes(s, 4 * len(SY_HEAD)))))
        kb = self.bytes(s + SY_KNOB_AT, 124)
        st['knob'] = [list(struct.unpack('<3b', kb[3 * t:3 * t + 3])) for t in range(SY_NT)]
        st['dirty'], st['loaded'] = kb[60], kb[61]
        st['oct'] = list(struct.unpack('<20b', kb[64:84]))
        st['susk'] = list(kb[84:104])
        st['dynk'] = list(kb[104:124])
        st.update(zip(SY_FILE, struct.unpack(f'<{len(SY_FILE)}I', self.bytes(s + SY_FILE_AT, 4 * len(SY_FILE)))))
        st.update(zip(SY_RUNF, struct.unpack(f'<{len(SY_RUNF)}I', self.bytes(s + SY_RUN_AT, 4 * len(SY_RUNF)))))
        st['out'] = list(struct.unpack('<64i', self.bytes(s + self.sl.out, 256)))
        st.update(zip(SY_TAIL, struct.unpack(f'<{len(SY_TAIL)}I', self.bytes(s + self.sl.w_n, 4 * len(SY_TAIL)))))
        st.update(zip(SY_SCREEN, struct.unpack('<8I', self.bytes(s + self.sl.mode, 32))))
        (st['shift_page'], st['shift_down'], st['shift_used'], st['ext_fix']) = self.bytes(s + self.sl.mode + 32, 4)
        st.update(zip(SY_COUNTS, struct.unpack('<7I', self.bytes(s + self.sl.mode + 36, 28))))
        st['rem_down'], st['rem_fx'], st['out_bus'], st['armed'] = self.bytes(s + self.sl.rem_down, 4)
        st.update(zip(SY_REM, struct.unpack('<5I', self.bytes(s + self.sl.rem_down + 4, 20))))
        st['rec'] = list(struct.unpack('<64h', self.bytes(s + self.sl.rec, 128)))
        st['trk'] = list(self.bytes(s + self.sl.trk, 4))           # SY test 15: WAIT, SENS, GUARD, 0
        return st

    def ev(self, kind, what, val=0):
        """One UI event through sy_event: (what it returned, whether it reached note repeat's handler)."""
        self.uc.mem_write(EV, struct.pack('<4h', kind, what, val, 0))
        before = len(self.passed)
        r = self.call(self.sym['sy_event'], EV)
        return r, len(self.passed) > before

    def hold(self, key, on):
        b = self.get(base.KEYS + (key >> 3), '<B')
        bit = 1 << (key & 7)
        self.put(base.KEYS + (key >> 3), (b | bit) if on else (b & ~bit), '<B')

    def open_screen(self):
        """EXT SOURCE + RECORD SETTING, the SG page there, a UI tick: the screen up."""
        self.hold(KEY_EXT, True)
        self.ev(EV_KEY, KEY_REC_SET)
        self.hold(KEY_EXT, False)
        self.ev(EV_KEY_UP, KEY_REC_SET)
        self.page(SG_PAGE)
        self.call(self.sym['sy_ui'])

    def packet(self, pair0, pair1):
        """A packet at PACKET: pair 0 L = R = pair0, pair 1 L = R = pair1 (lists of 64), the others 0."""
        pk = [0] * 1024
        for f in range(64):
            pk[16 * f] = pk[16 * f + 1] = pair0[f]
            pk[16 * f + 2] = pk[16 * f + 3] = pair1[f]
        self.uc.mem_write(PACKET, struct.pack('<1024h', *pk))
        return PACKET

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


class ScreenMachine(SyMachine):
    """SyMachine with the stock drawing calls stubbed (each recorded: colour, rectangle, font, text), the stock
    invalidate recorded, and the kits' column and footer draws and kits save's page update stubbed (recorded)."""
    def __init__(self, img, man, **kw):
        super().__init__(img, man, **kw)
        self.draws, self.invalid, self.kits = [], [], []
        for a, fn in ((F_COLOR, self._color), (F_RECT, self._rect), (F_FONT, self._font), (F_TEXT, self._text),
                      (INVALIDATE, self._invalid)):
            self.uc.hook_add(UC_HOOK_CODE, fn, begin=a, end=a)
        for name in ('KIT_COL_DRAW', 'KIT_FOOT_DRAW', 'KS_SG_POLL'):
            a = int(man['screen'][name]['target'], 16) & ~1
            self.uc.hook_add(UC_HOOK_CODE, self._kit, begin=a, end=a)

    def _reg(self, k):
        return self.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}'))

    def _color(self, uc, a, s, _):
        self.draws.append(('color', self._reg(1), self._reg(2)))
        self._ret(uc)

    def _rect(self, uc, a, s, _):
        self.draws.append(('rect', *struct.unpack('<4i', self.bytes(self._reg(1), 16))))
        self._ret(uc)

    def _font(self, uc, a, s, _):
        self.draws.append(('font', self._reg(1)))
        self._ret(uc)

    def _text(self, uc, a, s, _):
        raw = tuple(self._reg(k) for k in range(4))
        text = self.bytes(raw[3], 32).split(b'\0')[0].decode('latin-1')
        self.draws.append(('text', struct.unpack('<i', struct.pack('<I', raw[1]))[0],
                           struct.unpack('<i', struct.pack('<I', raw[2]))[0], text, raw))
        self._ret(uc)

    def _invalid(self, uc, a, s, _):
        self.invalid.append(self._reg(0))
        self._ret(uc)

    def _kit(self, uc, a, s, _):
        self.kits.append((a, self._reg(0)))
        self._ret(uc)

    def draw_column(self, col, param, kind=0):
        """sy_col_draw on a knob column widget (rectangle at +4, framebuffer +0x84, type +0x308, parameter +0x310)."""
        x0 = (0, 42, 84)[col]
        self.uc.mem_write(WIDGET, bytes(0x320))
        self.uc.mem_write(WIDGET + 4, struct.pack('<4i', x0, 0, x0 + 43, 39))
        self.put(WIDGET + 0x84, FB, '<I')
        self.put(WIDGET + 0x308, kind, '<I')
        self.put(WIDGET + 0x310, param, '<I')
        self.draws.clear()
        self.call(self.sym['sy_col_draw'], WIDGET)
        return list(self.draws)

    def draw_footer(self):
        self.uc.mem_write(FOOTER, bytes(0x100))
        self.put(FOOTER, FOOTER_VT, '<I')
        self.uc.mem_write(FOOTER + 4, struct.pack('<4i', 0, 54, 127, 63))
        self.put(FOOTER + 0x84, FB, '<I')
        self.draws.clear()
        self.call(self.sym['sy_foot_draw'], FOOTER)
        return list(self.draws)

    def bridge(self, fn, regs, ends):
        """A bridge entered mid-function with these registers, run until it reaches one of `ends` (address -> tag):
        (tag, the registers there)."""
        uc = self.uc
        for r, v in regs.items():
            uc.reg_write(getattr(ar, 'UC_ARM_REG_' + r), v)
        hit, hooks = [], []
        for a, tag in ends.items():
            def h(uc_, addr, size, _, tag=tag):
                hit.append((tag, {r: uc_.reg_read(getattr(ar, 'UC_ARM_REG_' + r)) for r in
                                  ('R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'LR', 'SP')}))
                uc_.reg_write(ar.UC_ARM_REG_PC, RET | 1)
            hooks.append(uc.hook_add(UC_HOOK_CODE, h, begin=a, end=a))
        uc.emu_start(fn | 1, RET, count=200000)
        for k in hooks:
            uc.hook_del(k)
        return hit[0] if hit else (None, {})

    def bar_name(self):
        regs = dict(R0=0x10, R1=0x11, R2=0x12, R3=0x13, R4=BAR_BUF, R5=7, R6=0x66, LR=0x0BADC0DF, SP=STACK - 0x100)
        self.uc.mem_write(BAR_BUF, bytes(16))
        tag, r = self.bridge(self.sym['sy_bar_name'], regs, {BAR_END: 'end', 0x83FA2000: 'arp'})
        return tag, self.bytes(BAR_BUF, 16).split(b'\0')[0].decode(), all(r[k] == regs[k] for k in regs)

    def bar_text(self):
        regs = dict(R0=BAR_DRAW_ARGS[0], R1=BAR_DRAW_ARGS[1], R2=BAR_DRAW_ARGS[2], R3=BAR_DRAW_ARGS[3], R4=WIDGET,
                    R5=0x55, R6=7, LR=0x0BADC0DF, SP=STACK - 0x100)
        self.uc.mem_write(WIDGET, bytes(0x100))
        self.put(WIDGET + 0x84, FB, '<I')
        self.uc.mem_write(STACK - 0x100 + 0x18, struct.pack('<4i', 73, BAR_Y0, 95, BAR_Y1))   # the item box
        self.uc.mem_write(STACK - 0x100 + 0x28, b'XX' + bytes(14))
        self.draws.clear()
        tag, r = self.bridge(self.sym['sy_bar_text'], regs, {BAR_DRAWN: 'drawn', 0x83FA2060: 'arp'})
        args = next((d[4] for d in self.draws if d[0] == 'text'), None)
        return (tag, self.bytes(STACK - 0x100 + 0x28, 16).split(b'\0')[0].decode(), args,
                all(r[k] == regs[k] for k in regs), [d for d in self.draws if d[0] in ('color', 'rect')])

    def bar_poll(self):
        regs = dict(R0=BAR_SCREEN, R1=0x11, R2=0x12, R3=0x13, R4=0x44, LR=0x0BADC0DF, SP=STACK - 0x100)
        self.invalid.clear()
        tag, r = self.bridge(self.sym['sy_bar_poll'], regs, {0x83FA2160: 'arp'})
        return tag, list(self.invalid), all(r[k] == regs[k] for k in regs)


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
    # 1. When it plays: every page but the Sound Generator's, with EXT SOURCE on (test 4: ROUTING Mix too, the chip
    #    held on ExtIn).
    m = SyMachine(img, man)
    lay = m.sl
    m.uc.mem_write(sym['sy_block'], b'\xA5' * lay.block_bytes)         # leftovers of an earlier run
    m.call(sym['sy_ui'])
    check(m.sy()['req'] == 0, 'before the UI has read EXT SOURCE and ROUTING: the engine not started')
    disarmed = m.sy()['armed']                         # SY test 8: EXT SOURCE not read yet (off): disarmed
    m.put(sym['sy'] + lay.armed, 1, '<B')              # the screen opened since (the arming: sy_screen_checks)
    m.start()
    st = m.sy()
    check(disarmed == 0 and st['req'] == 1 and st['starts'] == 1 and
          not any(m.bytes(sym['sy_block'], lay.block_bytes)) and m.routing_dt1() == [1],
          'main screen, EXT SOURCE on, ROUTING ExtIn: the chip held (ROUTING DT1 ExtIn), the engine cleared and handed '
          'over')
    st = m.step()
    check(st['state'] == SY_RUN and st['steps'] == 1 and st['fresh'] == 1 and
          m.get(sym['sy_block'] + lay.started, '<I') == 1 and st['out'] == [0] * 64,
          'RUN from the first block (silence in, silence out), its block ready for TX')
    sig = ref.to_blocks(sy_strum('G')[0])
    loud = 0
    for b in range(200):
        st = m.step(sig[b])
        if b >= 180:
            loud = max(loud, max(abs(v) for v in st['out']))
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
    for label, kw, page in (('EXT SOURCE off', dict(ext=0), 1), ('Sound Generator page', dict(), SG_PAGE)):
        q = SyMachine(img, man, page=page, **kw)
        q.start()
        for b in range(40):
            st = q.step(sig[b])
        quiet[label] = (st['req'], st['state'], st['steps'], st['starts'])
    d = SyMachine(img, man, page=DOOM_PAGE)
    d.start()
    st = d.step(sig[0])
    mix = SyMachine(img, man, routing=0)
    mix.start()
    for b in range(40):
        st_mix = mix.step(sig[b])
    check(all(v == (0, SY_OFF, 0, 0) for v in quiet.values()) and st['state'] == SY_RUN and
          st_mix['state'] == SY_RUN and st_mix['starts'] == 1 and mix.routing_dt1() == [1] and
          mix.tt()['rec_mix'] == 1,
          f'not with EXT SOURCE off, not on the Sound Generator page; on any other page, DOOM OS\'s too; test 4: on '
          f'ROUTING Mix too (the chip held on ExtIn, the recorder given the mix) ({quiet})')
    mm = SyMachine(img, man)
    mm.start()
    for b in range(100):
        mm.step(sig[b])
    mm.routing = 0
    mm.ui(0)
    states = [mm.step(sig[100 + k])['state'] for k in range(12)]
    t = mm.tt()
    check(states == [SY_RUN] * 12 and t['rec_mix'] == 1 and t['rec_ext'] == 0 and mm.routing_dt1() == [1],
          f'ROUTING turned to Mix while it plays: it plays on (the hold stays), the recorder now given the mix '
          f'({states})')
    # 2. The module against sy_ref.py, value for value, on the same blocks. Test 5: on WAH (tone 13), the one tone with
    #    no release, so a band stopping stops at once as test 1's saw did (the saw lead now releases over 150 ms and
    #    sustains: its tails and its releasing bands are what the tone asks for, checked value for value below).
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
        mc.put(sym['sy'] + mc.sl.tone_req, SY_PLAIN, '<I')
        mc.start()
        eng = sy_ref.Engine(SY_PLAIN)
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
    check(all(v >= 0.95 for v in shares.values()),
          f'the bands sounding are the strings\' partials (within 30 cents; 95% since SY test 11, FUND always on: the '
          f'note manager\'s input; test 10 on WAH: 96.6 / 97.4 / 97.9): {shares}')
    hh = results['hiss and hum alone']
    check(hh['peak'] == 0 and hh['last_sound_ms'] is None, 'hiss and hum alone (-74 / -66 dBFS): no sound at all')
    tails = {k: r['length_ms'] - r['last_sound_ms'] for k, r in results.items() if r['last_sound_ms'] is not None}
    check(all(v >= 50 for v in tails.values()),
          f'once the strings stop (each signal ends in 0.4 s of hiss and hum) the output goes to 0 within 0.35 s (SY '
          f'test 11: PUNCH BASS\'s 90 ms release after the note ends; WAH had none): ms of silence at the end {tails}')
    check(worst <= SY_STEP_MAX, f'the most instructions a step takes: {worst} ({worst / 8000:.1f}% of a block at one a '
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
    for b in range(60):                                                # SY test 12: blocks 110-169, the strum's notes
        #                                                                sounding (a note starts once it holds: block
        #                                                                122 here, the low string at 75)
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
        mr.feed(sig[110 + b])
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
    # SY test 7: the synth's bus: BUS 1 (words 2/3), BUS 2 (4/5), BOTH (half on each), each once, the others untouched.
    bus_ok = []
    for bus, words, div in ((1, (2, 3), 1), (2, (4, 5), 1), (3, (2, 3, 4, 5), 2), (0, (0, 1), 1)):
        mr.uc.mem_write(TXBUF, struct.pack('<1024i', *basew))
        mr.put(sym['sy'] + mr.sl.out_bus, bus, '<B')
        mr.put(sym['sy'] + SY_RUN_AT + 4 * SY_RUNF.index('fresh'), 1, '<I')
        mr.call(sym['sy_tx'], base.ARGS, 123456)
        got = list(struct.unpack('<1024i', mr.bytes(TXBUF, 4096)))
        exp = list(basew)
        for f in range(64):
            for w in words:
                exp[16 * f + w] = max(-0x80000, min(0x7FFFF, basew[16 * f + w] + (st['out'][f] >> (div - 1))))
        bus_ok.append(got == exp)
    check(all(bus_ok), f'SY test 7, the synth\'s bus: BUS 1 on words 2/3, BUS 2 on 4/5, BOTH half on each, DRY 0/1 '
                       f'again; every other word untouched, clipped to 20 bits ({bus_ok})')
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
    ms.step()                                                          # the UI asks for it again
    ms.step()                                                          # SY test 8: the start's two steps, then
    ms.step()                                                          # the one over the whole block
    ms.cyc_step = 850_000
    ms.feed([1000] * 64)
    ms.call(sym['sy_rx'])
    ms.cyc_step = 0
    st = ms.sy()
    check(st['state'] == SY_SLOW and st['slow_cycles'] == 850_000 and st['p_max'] == 850_000 and st['starts'] == 2,
          'left and back: started afresh; one step over the whole 800,000-cycle block: SLOW at once, the window so '
          'far published')
    # SY test 8: the first two steps after a start are not held to it (a cold first step): a 1.3 M-cycle first step
    # and a hot second one leave it running; the third over the whole block stops it.
    mg = SyMachine(img, man)
    mg.start()
    seq = []
    for cyc in (1_300_000, 750_000, 850_000):
        mg.cyc_step = cyc
        mg.feed([1000] * 64)
        mg.call(sym['sy_rx'])
        mg.cyc_step = 0
        g = mg.sy()
        seq.append((g['state'], g['run_steps']))
    check(seq == [(SY_RUN, 1), (SY_RUN, 2), (SY_SLOW, 3)],
          f'SY test 8: a start\'s first two steps are not held to the budget (DM-404 timed a first step at 1.2 M cycles); '
          f'the third over the whole block: SLOW ({seq})')
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
    import sy_voices
    sym = man['symbols']
    fde = man['guards']['fde']
    # 1. Every tone (picked before the start: the engine starts on it) against sy_ref.py, value for value.
    counter = [0]

    def every(uc, a_, s_, _):
        counter[0] += 1
    blocks = ref.to_blocks(sy_signal())
    mism, worst, peaks = [], {}, {}
    for tone in range(len(sy_voices.VOICES)):
        mt = SyMachine(img, man)
        mt.put(sym['sy'] + mt.sl.tone_req, tone, '<I')                 # (test 5: the default OCTAVE, SUSTAIN)
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
        worst[sy_voices.VOICES[tone]['name']] = top
        peaks[sy_voices.VOICES[tone]['name']] = pk
    check(not mism and all(v > 1000 for v in peaks.values()),
          f'every tone: the module\'s output = sy_ref.py\'s (SY test 11: its analysis, then the host build of '
          f'sy_voice.c), value for value ({len(sy_voices.VOICES)} tones x {len(blocks)} blocks; first differences '
          f'{mism[:3]})')
    check(max(worst.values()) <= SY_STEP_MAX,
          f'the most instructions a step takes, by tone: {worst} (the most is {max(worst.values()) / 8000:.1f}% of a '
          f'block at one a cycle)')
    report['sy']['tones'] = dict(worst_step_instructions=worst, peaks=peaks,
                                 names=[t['name'] for t in sy_voices.VOICES])
    # 1b. SY test 15: the TRACK page set (SY test 18: LAW 2:1 / 1:1 in WAIT's place, SENS 20, GUARD on) on a poly, a mono
    #     and an SG tone: the module's output = sy_ref.py's with the same settings, value for value, and not test 11's
    #     (the settings reach the notes).
    tmism, tdiff, tworst = [], {}, 0
    for tone, guard, law in ((0, 1, 2), (7, 2, 1), (18, 2, 2)):       # SY test 16: GUARD 2 is PICK
        mt = SyMachine(img, man)
        mt.put(sym['sy'] + mt.sl.tone_req, tone, '<I')
        mt.uc.mem_write(sym['sy'] + mt.sl.trk, bytes([law, 20, guard, 0]))
        mt.start()
        eng = sy_ref.Engine(tone)
        eng.trk = [law, 20, guard]
        plain = sy_ref.Engine(tone)
        differs = 0
        for b, values in enumerate(blocks):
            mt.feed(values)
            h = mt.uc.hook_add(UC_HOOK_CODE, every)
            counter[0] = 0
            mt.call(sym['sy_rx'])
            mt.uc.hook_del(h)
            tworst = max(tworst, counter[0])
            got = list(struct.unpack('<64i', mt.bytes(sym['sy'] + mt.sl.out, 256)))
            want, _ = eng.step(values, bpm100=mt.sy()['bpm100'])
            base11, _ = plain.step(values, bpm100=mt.sy()['bpm100'])
            differs += want != base11
            if got != want:
                tmism.append((tone, b))
        tdiff[sy_voices.VOICES[tone]['name']] = differs
    check(not tmism and all(v > 0 for v in tdiff.values()) and tworst <= SY_STEP_MAX,
          f'SY test 15: with the TRACK page set (LAW 2:1 / 1:1 / 2:1 (SY test 18), SENS 20, GUARD ON; PICK on the last '
          f'two: test 16) the module\'s '
          f'output = sy_ref.py\'s with the same settings, value for value (POLY PAD, LADDER LEAD, SG PLUCK x '
          f'{len(blocks)} blocks; first differences '
          f'{tmism[:3]}), unlike the settings at 0 in blocks {tdiff}; the most instructions a step takes {tworst}')
    # 1c. SY test 19: a mono tone's notes from the SG tracker. FAT BASS on the six open strings, each picked as the last
    #     is let go: once the engine plays the mono tone, tune_ui starts the tracker; then each block (tune_rx, then
    #     sy_rx, as diag_rx_c) the module's output = sy_ref.py's with tune_ref.py's tracker (from the same block),
    #     value for value; every string's note by 40 ms after its pick, no other pitch on the way; the tracker and the
    #     engine together within a block's instructions.
    import numpy as np
    ynotes = (40, 45, 50, 55, 59, 64)
    yx = np.zeros(int((0.2 + 0.5 * len(ynotes) + 0.6) * 48000))
    for i, n in enumerate(ynotes):
        at = int((0.2 + 0.5 * i) * 48000)
        sg = ref.guitar(ref._hz(n), 0.53, amp=0.3, seed=i, B=ref._stiff(n))
        sg[-1440:] *= np.linspace(1, 0, 1440)
        yx[at:at + len(sg)] += sg[:len(yx) - at]
    yblocks = ref.to_blocks(np.clip(ref.hiss(yx, 1), -1, 1))
    my = SyMachine(img, man)
    my.put(sym['sy'] + my.sl.tone_req, 8, '<I')
    my.start()
    eng = sy_ref.Engine(8)
    ymism, ytop, ybands, yrun = [], 0, [], []
    for b, values in enumerate(yblocks):
        my.feed(values)
        h = my.uc.hook_add(UC_HOOK_CODE, every) if b % 16 == 8 else None
        counter[0] = 0
        my.call(sym['tune_rx'])
        my.call(sym['sy_rx'])
        if h is not None:
            my.uc.hook_del(h)
            ytop = max(ytop, counter[0])
        if b == 0:
            my.call(sym['tune_ui'])                                    # the engine plays a mono tone: the tracker
        got = list(struct.unpack('<64i', my.bytes(sym['sy'] + my.sl.out, 256)))
        want, _ = eng.step(values, bpm100=my.sy()['bpm100'])
        if b == 0:
            eng.yin = ref.Tracker()                                    #   runs from the next block
        if got != want:
            ymism.append(b)
        yrun.append(eng.ykn[1] >= 0x80)
        nb_, ng_ = struct.unpack_from('<bB', eng.host().state, 6 * 160 + 84)   # n[0]'s band and gate (6 voices
        ybands.append(40 + nb_ if ng_ and nb_ >= 0 else -1)                    #   of 160 bytes before the notes)
    ylate, yother = [], []
    for i, n in enumerate(ynotes):
        i0 = int((0.2 + 0.5 * i) * 48000) // 64
        seq = ybands[i0:i0 + 120]
        at = seq.index(n) if n in seq else None
        ylate.append(None if at is None else round(at * 64 / 48.0))
        prev = ynotes[i - 1] if i else -1
        yother += [v for v in seq[:at if at is not None else 120] if v not in (-1, n, prev)]
    tst = my.tt()
    check(not ymism and all(v is not None and v <= 40 for v in ylate) and not yother and all(yrun[2:]) and
          tst['state'] == TT_RUN and ytop <= SY_STEP_MAX,
          f'SY test 19: FAT BASS with the tracker (tune_ui runs it for a mono tone): the module\'s output = sy_ref.py\'s '
          f'with tune_ref.py\'s tracker, value for value ({len(yblocks)} blocks; first differences {ymism[:3]}); each '
          f'open string\'s note {ylate} ms after its pick, no other pitch on the way ({yother[:6]}); the tracker '
          f'running ({tst["steps"]} steps); tracker + engine at most {ytop} instructions a block')
    report['sy']['yin_mono'] = dict(blocks=len(yblocks), mismatches=ymism[:20], note_ms=ylate, other=yother[:20],
                                    tracker_steps=tst['steps'], worst_block_instructions=ytop)
    # 1d. SY test 19: the cycle counter's wrap. syn_live compared DWT_CYCCNT - hold_at (32 bits: round every 7.16 s at
    #     600 MHz) with the 20 ms settle, so in tests 4-18 a UI tick 2^32 cycles after the hold found it unsettled and
    #     stopped the synth (DM-404: the tracker restarting on its own). UI ticks every 0.5 s for 7 s, then one 1 ms
    #     into that window: the engine plays on (no stop, no restart).
    mw = SyMachine(img, man)
    mw.start()
    for _ in range(8):
        mw.step()
    sent = mw.tt()['hold_at']
    for k in range(14):
        mw.cyc += 300_000_000
        mw.call(sym['tune_ui'])
        mw.call(sym['syn_ui'])
        mw.call(sym['sy_ui'])
        mw.step()
    mw.cyc = sent + (1 << 32) + 600_000
    mw.call(sym['tune_ui'])
    mw.call(sym['syn_ui'])
    mw.call(sym['sy_ui'])
    for _ in range(12):
        sw = mw.step()
    check(sw['state'] == SY_RUN and sw['stops'] == 0 and sw['starts'] == 1 and mw.tt()['hold'] == 1,
          f'SY test 19: a UI tick 2^32 cycles after the hold (7.16 s at 600 MHz; tests 4-18 stopped the synth there) '
          f'leaves the engine playing (state {sw["state"]}, starts {sw["starts"]}, stops {sw["stops"]})')
    # 1e. SY test 20: a bass line picked note to note (test 19 on the unit: "missed notes still on fat bass and sync
    #     lead"): E2 E2 G2 A2 A2 B2 A2 G2 twice, a pick every 0.25 s on one string, each cutting the note before. With the
    #     tracker, the module's output = sy_ref.py's value for value, and every pick gets one attack, at its own pitch
    #     by 45 ms (test 19: the repeats and some steps came in as a glide, no attack); no attack before the first pick.
    import math
    rnotes = [40, 40, 43, 45, 45, 47, 45, 43] * 2
    rx = np.zeros(int((0.3 + 0.25 * len(rnotes) + 0.6) * 48000))
    for i, n in enumerate(rnotes):
        at = int((0.3 + 0.25 * i) * 48000)
        end = at + int(0.253 * 48000) if i + 1 < len(rnotes) else len(rx)
        sg = ref.guitar(ref._hz(n), (end - at) / 48000 + 0.01, amp=0.4, seed=i, B=ref._stiff(n))[:end - at]
        if end < len(rx):
            sg[-144:] *= np.linspace(1, 0, 144)
        rx[at:at + len(sg)] += sg
    rblocks = ref.to_blocks(np.clip(ref.hiss(rx, 0), -1, 1))
    mr = SyMachine(img, man)
    mr.put(sym['sy'] + mr.sl.tone_req, 8, '<I')
    mr.start()
    eng = sy_ref.Engine(8)
    ctl = 6 * 4 * 6 + 4 * 6                                            # syv_ctl_t, the state's last member
    rmism, rtrig, rpitch = [], [], []
    for b, values in enumerate(rblocks):
        mr.feed(values)
        mr.call(sym['tune_rx'])
        mr.call(sym['sy_rx'])
        if b == 0:
            mr.call(sym['tune_ui'])
        got = list(struct.unpack('<64i', mr.bytes(sym['sy'] + mr.sl.out, 256)))
        want, _ = eng.step(values, bpm100=mr.sy()['bpm100'])
        if b == 0:
            eng.yin = ref.Tracker()
        if got != want:
            rmism.append(b)
        st = eng.host().state.raw
        cf = struct.unpack_from('<12f', st, len(st) - ctl)               # gate[6], freq[6]
        rtrig.append(st[len(st) - ctl + 6 * 4 * 6] != 0)                # trig[0]
        rpitch.append(int(round(69 + 12 * math.log2(cf[6] / 440.0))) if cf[0] > 0 and cf[6] > 0 else -1)
    rbad, rlate = [], []
    for i, n in enumerate(rnotes):
        b0 = int((0.3 + 0.25 * i) * 48000) // 64
        b1 = int((0.3 + 0.25 * (i + 1)) * 48000) // 64 if i + 1 < len(rnotes) else len(rblocks)
        att = [b for b in range(b0 - 2, b1 - 2) if rtrig[b]]
        at = next((b for b in range(b0, b1) if rpitch[b] == n), None)
        rlate.append(None if not att else round((att[0] - b0) * 64 / 48.0))
        if len(att) != 1 or at is None or (att[0] - b0) * 64 / 48.0 > 45:
            rbad.append((i, n, len(att), rlate[-1]))
    early = sum(rtrig[:int(0.3 * 48000) // 64 - 2])
    check(not rmism and not rbad and not early,
          f'SY test 20: FAT BASS on a line picked note to note (E2 E2 G2 A2 A2 B2 A2 G2 x 2, each pick cutting the note '
          f'before): the module\'s output = sy_ref.py\'s with the tracker, value for value ({len(rblocks)} blocks; first '
          f'differences {rmism[:3]}); every pick one attack at its pitch, ms after the pick: {rlate} (not so: '
          f'{rbad[:4]}); attacks before the first pick {early}')
    report['sy']['line_attacks'] = dict(blocks=len(rblocks), mismatches=rmism[:20], attack_ms=rlate, bad=rbad[:20])
    # 2. Test 5: a tone change while playing, from the screen (the Sound Generator page in SY mode): VALUE steps SOUND
    #    1 -> 9; out over 8 blocks, the new tone from rest, in over 8, value for value.
    mc = ScreenMachine(img, man, page=SG_PAGE)
    mc.put(sym['sy'] + mc.sl.mode, 1, '<I')
    mc.start()
    eng = sy_ref.Engine(0)
    blocks = ref.to_blocks(sy_strum('Am')[0])
    mism, fade = [], []
    for b, values in enumerate(blocks[:420]):
        if b == 200:
            for _ in range(8):
                mc.ev(EV_ENC, 0, 1)
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
          f'SOUND 1 -> 9 on the screen while playing: the output fades out over 8 blocks, tone 9 from block {switched}, '
          f'fades in; the module = sy_ref.py value for value across it (first differences {mism[:3]})')
    # 3. The builder's calls: note repeat's bridge calls sy_event; the SG widgets' pointers and the arp's bar jumps go
    #    to the screen's; FX deep edit's bridges call their own handlers again (test 4's picker is gone).
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    nr = man['nr_hook']
    ours = sorted((p for p in man['patches'] if p.get('what', '').startswith(("note repeat's", 'SY test 5,'))),
                  key=lambda p: not p['what'].startswith("note repeat's"))
    fde_calls = {n: [f'{i.mnemonic} {i.op_str}' for i in md.disasm(mc.bytes(int(v['call'], 16), 4), int(v['call'], 16))]
                 for n, v in fde.items()}
    check(len(ours) == 7 and ours[0]['address'] == int(nr['call'], 16) and ours[0]['target'] == sym['sy_event'] & ~1
          and ours[0]['original_target'] == int(nr['nr_event_c'], 16) and
          {p['address'] for p in ours[1:]} == {0x8022BBD4, 0x802256FC, 0x80229678, 0x800BBC98, 0x80123BE6, 0x80123CE0}
          and all(mc.bytes(p['address'], p['size']).hex() == p['replacement_hex'] for p in ours) and
          all(fde_calls[n] == [f'bl #{int(v["handler"], 16):#x}'] for n, v in fde.items()),
          f'note repeat\'s bridge calls sy_event (bl); the SG column, footer and page update pointers and the arp\'s '
          f'three bar jumps go to the screen\'s; FX deep edit\'s bridges call their own handlers ({fde_calls})')
    sy_knob_checks(img, man)
    sy_screen_checks(img, man)
    sy_route_checks(img, man)


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


def sy_file_bytes(tone, muted, knobs, octs=None, suss=None, dyns=None, version=4, bus=0, trk=(0, 0, 0)):
    """B:/_sy_tones.bin as sy_save writes it (SY test 11, version 4): "SYTN", 4, tone, muted, 20, 60 knob positions,
    20 OCTAVE, 20 SUSTAIN, 20 DYNAMICS, the bus, SY test 15's WAIT, SENS and GUARD (trk; zeros before), FNV-1a of the
    first 132. version=3: tests 6-10's (15
    tones: 104 bytes, the bus at 98, the sum of the first 100); version=2: test 5's (88 bytes)."""
    n = 20 if version == 4 else 15
    octs = octs or [0] * n
    suss = suss or [0] * n
    dyns = dyns or [0] * n
    body = (b'SYTN' + bytes([version, tone, muted, n]) + bytes(64 + d for row in knobs[:n] for d in row) +
            bytes(o & 0xFF for o in octs[:n]) + bytes(suss[:n]))
    if version == 4:
        body += bytes(dyns[:n]) + bytes([bus, *trk])
    elif version == 3:
        body += bytes(dyns[:n]) + bytes([bus, 0])
    else:
        body += bytes(1)
    h = 2166136261
    for c in body:
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return body + struct.pack('<I', h)


def sy_knob_checks(img, man):
    """SY test 3's knobs and file, set on the screen (SY test 6: CTRL 1 the tone's own setting, CTRL 2 TONE, CTRL 3
    LEVEL; SHIFT: OCTAVE, SUSTAIN, DYNAMICS; file version 3, a version 2 file read)."""
    import sy_ref
    sym = man['symbols']

    def machine(store=None, **kw):
        x = ScreenMachine(img, man, store=store, **kw)
        x.start()
        return x, x.files
    # 1. On the screen, SUPERSAW: CTRL 1 DETUNE (its own setting), CTRL 2/3 TONE and LEVEL to the knob's position - 64,
    #    SHIFT page: OCTAVE, SUSTAIN, DYNAMICS; each turn taken; the file not yet written (never from a turn).
    m, files = machine()
    m.open_screen()
    m.ev(EV_KEY, 3)
    m.ev(EV_KEY_UP, 3)
    turns = [m.ev(EV_KNOB, 1, 20), m.ev(EV_KNOB, 2, 100), m.ev(EV_KNOB, 3, 127)]
    before = len(files.writes)
    m.ev(EV_KEY, KEY_SHIFT)
    m.ev(EV_KEY_UP, KEY_SHIFT)                                         # tapped: the SHIFT page; a key release
    at_shift = len(files.writes)
    turns += [m.ev(EV_KNOB, 1, 0), m.ev(EV_KNOB, 2, 64), m.ev(EV_KNOB, 3, 30)]
    st = m.sy()
    check(all(t == (1, False) for t in turns) and st['knob'][3] == [36, -44, 63] and st['oct'][3] == 1 and
          st['susk'][3] == 1 + (64 * 101 >> 7) and st['dynk'][3] == 1 + (30 * 101 >> 7) and st['dirty'] == 1 and
          before == 0 and at_shift == 1 and len(files.writes) == 1 and st['shift_page'] == 1,
          f'the screen on SUPERSAW: DETUNE, TONE and LEVEL, then (SHIFT tapped) OCTAVE -2, SUSTAIN and DYNAMICS to the '
          f'knobs, each turn taken; the file written at the release of SHIFT, never at a turn ({st["knob"][3]}, oct '
          f'{st["oct"][3]}, sus {st["susk"][3]}, dyn {st["dynk"][3]})')
    # 2. The file at a key release, never with an FX screen up.
    m.put(TOP_OBJECT, SCRATCH + 0x400, '<I')
    m.put(SCRATCH + 0x600, FX_VIEW_VTABLE, '<I')
    shown = [True]

    def view_at(uc, a, s_, _):
        i = uc.reg_read(ar.UC_ARM_REG_R1)
        uc.reg_write(ar.UC_ARM_REG_R0, SCRATCH + 0x600 if (shown[0] and i == 0) else 0)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))
    m.uc.hook_add(UC_HOOK_CODE, view_at, begin=VIEW_AT, end=VIEW_AT)
    m.ev(EV_KEY, KEY_EXIT)
    up1 = m.ev(EV_KEY_UP, KEY_EXIT)
    held_back = (len(files.writes), m.sy()['dirty'])
    shown[0] = False
    up2 = m.ev(EV_KEY_UP, 0x20)
    st3 = m.sy()
    want = sy_file_bytes(3, 0, st3['knob'], st3['oct'], st3['susk'], st3['dynk'])
    check(up1 == (0, True) and held_back == (1, 1) and up2 == (0, True) and len(files.writes) == 2 and
          files.writes[-1] == (SY_PATH, want) and st3['dirty'] == 0 and st3['saves'] == 2 and len(want) == 136,
          f'a key release with an FX screen up: no file yet; at the next release with none, {SY_PATH} written once '
          f'({len(want)} bytes: "SYTN", version 4, tone 4, 60 knobs, 20 OCTAVE, 20 SUSTAIN, 20 DYNAMICS, the bus, '
          f'FNV-1a); both releases go on to note repeat')
    # 3. A fresh start with that file: read at the first key event; the engine as the twin with the same settings.
    mf, f2 = machine({SY_PATH: want})
    before = mf.sy()['loaded']
    mf.ev(EV_KEY, KEY_EXT)                                             # any key event reads the file first
    st4 = mf.sy()
    eng = sy_ref.Engine(3)
    eng.knobs[3] = st4['knob'][3]
    eng.octs[3] = st4['oct'][3]
    eng.suss[3] = st4['susk'][3]
    eng.dyns[3] = st4['dynk'][3]
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
          st4['knob'][3] == [36, -44, 63] and st4['oct'][3] == 1 and st4['susk'][3] == st3['susk'][3] and
          st4['dynk'][3] == st3['dynk'][3] and not mism,
          f'a fresh start with the file: read at the first key event, tone 4 and its settings back, the engine = '
          f'sy_ref.py with them, value for value (300 blocks; first differences {mism[:3]})')
    bad = bytearray(want)
    bad[20] ^= 1
    mb, f3 = machine({SY_PATH: bytes(bad)})
    mb.ev(EV_KEY, KEY_EXT)
    v1 = b'SYTN' + bytes([1, 3, 0, 15]) + bytes(64 for _ in range(45)) + bytes(3)
    h = 2166136261
    for c in v1:
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    m1, _ = machine({SY_PATH: v1 + struct.pack('<I', h)})
    m1.ev(EV_KEY, KEY_EXT)
    mn, f4 = machine()
    mn.ev(EV_KNOB, 2, 50)
    v2 = sy_file_bytes(5, 0, [[k, -k, 2 * k] for k in range(15)], [3] * 15, [40] * 15, version=2)
    m2, _ = machine({SY_PATH: v2})
    m2.ev(EV_KEY, KEY_EXT)
    v3 = sy_file_bytes(5, 1, [[k, -k, 2 * k] for k in range(15)], [3] * 15, [40] * 15, [7] * 15, version=3, bus=2)
    m3, _ = machine({SY_PATH: v3})
    m3.ev(EV_KEY, KEY_EXT)
    sb, s1, sn, s2, s3 = mb.sy(), m1.sy(), mn.sy(), m2.sy(), m3.sy()
    check(sb['bad_files'] == 1 and sb['loads'] == 0 and sb['tone_req'] == 0 and all(r == [0, 0, 0] for r in sb['knob'])
          and s1['bad_files'] == 1 and s1['tone_req'] == 0 and sn['loaded'] == 1 and sn['loads'] == 0 and
          sn['bad_files'] == 0 and not f4.writes and len(v2) == 88 and s2['bad_files'] == 1 and s2['loads'] == 0 and
          len(v3) == 104 and s3['loads'] == 1 and s3['bad_files'] == 0 and s3['out_bus'] == 2 and s3['muted'] == 1 and
          s3['tone_req'] == 0 and all(r == [0, 0, 0] for r in s3['knob']) and s3['oct'] == [0] * SY_NT and
          s3['dirty'] == 1,
          'a file whose sum is wrong is ignored, and so are versions 1 and 2 (the old tones); tests 6-10\'s file '
          '(version 3, 104 bytes) keeps only its bus and SOUND OFF (the new tones as designed) and is written as '
          'version 4 at the next save; no file: nothing read, nothing written yet')
    # 4. Every tone with OCTAVE, SUSTAIN and DYNAMICS turned, value for value (the knobs' cubic exp2 and log2 paths).
    blocks = ref.to_blocks(sy_signal())
    mism = []
    for tone, octave, sustain, dyn in ((0, 5, 101, 1), (2, 1, 1, 51), (8, 4, 51, 101), (13, 2, 80, 31)):
        mt = SyMachine(img, man)
        mt.put(sym['sy'] + mt.sl.tone_req, tone, '<I')
        mt.put(sym['sy'] + mt.sl.oct + tone, octave, '<B')
        mt.put(sym['sy'] + mt.sl.susk + tone, sustain, '<B')
        mt.put(sym['sy'] + mt.sl.dynk + tone, dyn, '<B')
        mt.start()
        eng = sy_ref.Engine(tone)
        eng.octs[tone], eng.suss[tone], eng.dyns[tone] = octave, sustain, dyn
        for b, values in enumerate(blocks):
            mt.feed(values)
            mt.call(sym['sy_rx'])
            got = list(struct.unpack('<64i', mt.bytes(sym['sy'] + mt.sl.out, 256)))
            if got != eng.step(values, bpm100=mt.sy()['bpm100'])[0]:
                mism.append((tone, b))
    check(not mism, f'OCTAVE, SUSTAIN and DYNAMICS from the screen (+2 / 100 / 0, -2 / 0 / 50, +1 / 50 / 100, '
                    f'-1 / 79 / 30 on four tones): the module = sy_ref.py value for value ({len(blocks)} blocks each; '
                    f'first differences {mism[:3]})')
    import sy_voices
    report['sy']['knobs'] = dict(p2=[sy_voices.P2_NAMES[t.get('p2', sy_voices.P_RESO)] for t in sy_voices.VOICES],
                                 file=SY_PATH, file_bytes=len(want))


def fx_view(m):
    """SY test 6: an FX screen on TOP's view list (VIEW_AT stubbed); the list's flag turns it off ([0] = False)."""
    m.put(TOP_OBJECT, SCRATCH + 0x400, '<I')
    m.put(SCRATCH + 0x600, FX_VIEW_VTABLE, '<I')
    shown = [True]

    def view_at(uc, a, s_, _):
        i = uc.reg_read(ar.UC_ARM_REG_R1)
        uc.reg_write(ar.UC_ARM_REG_R0, SCRATCH + 0x600 if (shown[0] and i == 0) else 0)
        uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))
    m.uc.hook_add(UC_HOOK_CODE, view_at, begin=VIEW_AT, end=VIEW_AT)
    return shown


def sy_screen_checks(img, man):
    """SY test 5: the guitar synth screen: the chord, its events, its draws, the bar, leaving."""
    import sy_ref
    sym = man['symbols']
    scr = man['screen']
    col_draw, foot_draw, sg_poll = (int(scr[n]['target'], 16) & ~1 for n in ('KIT_COL_DRAW', 'KIT_FOOT_DRAW',
                                                                              'KS_SG_POLL'))
    # 1. EXT SOURCE held + RECORD SETTING on the main screen (EXT SOURCE on): taken, note repeat never sees it, the SG
    #    page asked for; its release taken; the SG page there at the next UI tick: the screen up.
    m = ScreenMachine(img, man)
    m.start()
    plain = m.ev(EV_KEY, KEY_REC_SET)
    m.ev(EV_KEY_UP, KEY_REC_SET)
    m.hold(KEY_EXT, True)
    chord = m.ev(EV_KEY, KEY_REC_SET)
    st = m.sy()
    m.hold(KEY_EXT, False)
    chord_up = m.ev(EV_KEY_UP, KEY_REC_SET)
    shown_before = m.call(sym['sy_shown'])
    m.call(sym['sy_ui'])
    st_wait = m.sy()
    m.page(SG_PAGE)
    m.call(sym['sy_ui'])
    st2 = m.sy()
    check(plain == (0, True) and chord == (1, False) and chord_up == (1, False) and m.requests == [SG_PAGE] and
          st['mode'] == 2 and st['enters'] == 1 and not m.sets and shown_before == 0 and st_wait['mode'] == 2 and
          st2['mode'] == 1 and m.call(sym['sy_shown']) == 1 and st2['taken'] == 0,
          'RECORD SETTING alone goes on; EXT SOURCE held + RECORD SETTING on the main screen: taken (note repeat never '
          'sees it, nor its release), the Sound Generator page asked for; the screen up once the page is there')
    # 2. Pads on the screen: a pad hit (and its key press) picks the sound, silently: neither reaches note repeat or
    #    stock (no sample, no Sound Generator note), nor their releases; pad 16: OFF; SUB PAD taken.
    m.passed.clear()
    rp = [m.ev(EV_PAD, 3, 100), m.ev(EV_KEY, 3)]
    st3 = m.sy()
    rp += [m.ev(EV_PAD_UP, 3), m.ev(EV_KEY_UP, 3)]
    st4 = m.sy()
    m.ev(EV_PAD, 15, 90)
    off = m.sy()
    m.ev(EV_PAD_UP, 15)
    sub = [m.ev(EV_PAD, KEY_SUB_PAD, 90), m.ev(EV_KEY, KEY_SUB_PAD), m.ev(EV_PAD_UP, KEY_SUB_PAD),
           m.ev(EV_KEY_UP, KEY_SUB_PAD)]
    check(all(r == (1, False) for r in rp + sub) and st3['tone_req'] == 3 and st3['muted'] == 0 and
          st3['pads_taken'] == 8 and st3['taken'] == 8 and st4['pads_taken'] == 0 and st4['taken'] == 0 and
          off['muted'] == 1 and m.sy()['pads_taken'] == 0 and not m.passed,
          'on the screen a pad picks a sound (pad 4: ENSEMBLE), pad 16 OFF; the pad hit and its key press, SUB PAD and '
          'every release taken: nothing reaches note repeat or stock (no sample plays)')
    # 3. SY test 6: CTRL 1 is the tone's own setting (VALUE and the pads pick the sound); VALUE steps SOUND; VALUE's
    #    push and REC taken; CTRL 4 and another encoder go on.
    m.ev(EV_PAD, 0, 100)
    m.ev(EV_PAD_UP, 0)                                                 # SOUND 1 (POLY PAD)
    k1 = m.ev(EV_KNOB, 1, 100)
    st_k1 = m.sy()
    steps = []
    for d in (1, 1, -3, 5):                                            # one a turn event: 1 -> 2 -> 3 -> 2 -> 3
        steps.append(m.ev(EV_ENC, 0, d))
    st5 = m.sy()
    for _ in range(20):
        m.ev(EV_ENC, 0, 1)
    top = m.sy()['tone_req']
    for _ in range(20):
        m.ev(EV_ENC, 0, -1)
    bottom = m.sy()['muted']
    keys = [m.ev(EV_KEY, KEY_VALUE), m.ev(EV_KEY_UP, KEY_VALUE), m.ev(EV_KEY, KEY_REC), m.ev(EV_KEY_UP, KEY_REC)]
    other = m.ev(EV_KNOB, 4, 30)
    other2 = m.ev(EV_ENC, 1, 1)
    check(k1 == (1, False) and st_k1['knob'][0][1] == 36 and st_k1['tone_req'] == 0 and st_k1['muted'] == 0 and
          all(s == (1, False) for s in steps) and st5['tone_req'] == 2 and st5['muted'] == 0 and
          top == SY_NT - 1 and bottom == 1 and all(k == (1, False) for k in keys) and other == (0, True) and
          other2 == (0, True),
          'CTRL 1 sets the sound\'s own setting (POLY PAD\'s ATTACK), the sound stays; VALUE steps SOUND one a turn, '
          'OFF..20 and no further; VALUE\'s push and REC taken (no edit mode, no export); CTRL 4 and another encoder '
          'go on')
    # 4. SHIFT: a tap turns the page; held, a turn edits the other page and the release keeps it; SHIFT goes on.
    m.ev(EV_PAD, 4, 100)
    m.ev(EV_PAD_UP, 4)                                                 # SOUND 5 (PAD)
    tone = m.sy()['tone_req']
    sh = [m.ev(EV_KEY, KEY_SHIFT), m.ev(EV_KEY_UP, KEY_SHIFT)]
    page1 = m.sy()['shift_page']
    m.ev(EV_KNOB, 1, 127)
    oct_ = m.sy()['oct'][tone]
    m.ev(EV_KEY, KEY_SHIFT)
    m.ev(EV_KNOB, 3, 0)
    m.ev(EV_KEY_UP, KEY_SHIFT)
    st6 = m.sy()
    check(sh == [(0, True), (0, True)] and page1 == 1 and oct_ == 5 and st6['knob'][tone][2] == -64 and
          st6['shift_page'] == 1 and st6['tone_req'] == tone,
          'SHIFT goes on (its held bit); tapped: the second page (CTRL 1 OCTAVE: +2 at the top); held again, CTRL 3 '
          'edits the first page\'s LEVEL and the release keeps the second page')
    # 5. The draws: each knob column (descriptor type 0, parameter 0x7b..0x80) cleared, its name small, its value big;
    #    the footer the sound's name; a column of another type, or outside the screen, to the kits' draws.
    for _ in range(2):                                                 # SY test 15: OTHERS -> TRACK -> the first page
        m.ev(EV_KEY, KEY_SHIFT)
        m.ev(EV_KEY_UP, KEY_SHIFT)
    m.ev(EV_PAD, 3, 100)
    m.ev(EV_PAD_UP, 3)                                                 # SOUND 4 (ENSEMBLE)
    m.ev(EV_KNOB, 2, 64 + 12)
    m.ev(EV_KNOB, 3, 96)
    cols = []
    for col, param in ((0, 0x7B), (1, 0x7C), (2, 0x80)):
        cols.append(m.draw_column(col, param))
    m.ev(EV_KEY, KEY_SHIFT)
    m.ev(EV_KEY_UP, KEY_SHIFT)
    cols2 = [m.draw_column(c, 0x7B + c) for c in range(3)]
    # SY test 15: a third tap, the TRACK page: CTRL 1 WAIT (12 blocks: 16 ms at the top), CTRL 2 SENS (64: 25), CTRL 3
    # GUARD (the upper half on); the columns; the next tap back to the first page; the settings in the file
    m.ev(EV_KEY, KEY_SHIFT)
    m.ev(EV_KEY_UP, KEY_SHIFT)
    page_t = m.sy()['shift_page']
    t_before = list(m.sy()['trk'])
    m.ev(EV_KNOB, 1, 127)
    m.ev(EV_KNOB, 2, 64)
    m.ev(EV_KNOB, 3, 100)
    cols3 = [m.draw_column(c, 0x7B + c) for c in range(3)]
    trk = list(m.sy()['trk'])
    m.ev(EV_KNOB, 3, 20)
    guard_off = m.sy()['trk'][2]
    m.ev(EV_KNOB, 3, 64)
    guard_on = (m.sy()['trk'][2], [d[3] for d in m.draw_column(2, 0x7D) if d[0] == 'text'])
    m.ev(EV_KNOB, 3, 100)
    m.ev(EV_KEY, KEY_SHIFT)
    m.ev(EV_KEY_UP, KEY_SHIFT)
    page_back = m.sy()['shift_page']
    t_writes = [w for w in m.files.writes if w[0] == SY_PATH]
    t_file = t_writes[-1][1] if t_writes else b''
    texts3 = [[d[3] for d in c if d[0] == 'text'] for c in cols3]
    check(page_t == 2 and t_before == [0, 0, 0, 0] and trk == [2, 25, 2, 0] and guard_off == 0 and page_back == 0 and
          guard_on == (1, ['GUARD', 'ON']) and texts3 == [['LAW', '2:1'], ['SENS', '25'], ['GUARD', 'PICK']] and
          len(t_file) == 136 and list(t_file[129:132]) == [0x82, 25, 2],
          f'SY test 15: SHIFT\'s third tap shows the TRACK page (every tone): CTRL 1 (SY test 18) LAW in thirds (OFF, '
          f'1:1, 2:1), CTRL 2 SENS 0..50 (64: 25), CTRL 3 GUARD in thirds (SY test 16: OFF, ON, PICK); the next tap '
          f'goes back to the first page; the file keeps them in its spare bytes 129-131, LAW marked 0x80 ({texts3}, '
          f'{trk}, {list(t_file[129:132]) if t_file else None})')
    foot = m.draw_footer()
    texts = [[d[3] for d in c if d[0] == 'text'] for c in cols + cols2]
    t3 = m.sy()
    want_cols = [['ENV', '0'], ['TONE', '+10'], ['LEVEL', '75'],
                 ['OCTAVE', str(t3['oct'][3] - 3) if t3['oct'][3] else '0'],
                 ['SUSTAIN', '50'], ['DYNAMICS', '60']]
    shape = cols[0]
    check(texts == want_cols and shape[:3] == [('color', 0xFFFFFF, 0), ('rect', 0, 0, 43, 39), ('font', 0x1D)] and
          shape[3][1:3] == (21, 3) and shape[4] == ('font', 2) and shape[5][1:3] == (21, 15) and len(shape) == 6 and
          [d[3] for d in foot if d[0] == 'text'] == ['ENSEMBLE'] and ('font', 0x1D) in foot and not m.kits,
          f'the columns (SY test 6: the sound\'s own setting, TONE -50..+50 (+12 shows +10), LEVEL 0..100 (96 shows '
          f'75); SHIFT: OCTAVE, SUSTAIN, DYNAMICS): the name small at +3 (font 0x1d), the value big at +15 (font 2), '
          f'where the stock column draws its own ({texts}); the footer shows the name of the sound, small '
          f'("ENSEMBLE"); no kit draw asked')
    other_type = m.draw_column(0, 0x7B, kind=1)
    m.page(1)
    m.call(sym['sy_ui'])
    outside = m.draw_column(0, 0x7B)
    outside_f = m.draw_footer()
    check(not other_type and not outside and not outside_f and
          [k[0] for k in m.kits] == [col_draw, col_draw, foot_draw] and m.sy()['mode'] == 0 and
          m.sy()['leaves'] == 1,
          'a column of another descriptor type, and every draw once another page closed the screen: the kits\' draws')
    # 6. The page's update: kits save's first; when what the screen shows changed, the three columns and the footer
    #    drawn again, once.
    p = ScreenMachine(img, man, page=SG_PAGE)
    p.start()
    p.put(sym['sy'] + p.sl.mode, 1, '<I')
    p.draw_footer()
    page_obj = SCRATCH + 0x1000
    kids = [SCRATCH + 0xA00 + 0x40 * k for k in range(3)]
    p.uc.mem_write(page_obj + 0x1A6C, struct.pack('<3I', *kids))
    p.ev(EV_KNOB, 2, 70)
    p.invalid.clear()
    p.call(sym['sy_sg_poll'], page_obj)
    first = list(p.invalid)
    p.call(sym['sy_sg_poll'], page_obj)
    second = list(p.invalid)
    check([k[0] for k in p.kits if k[0] == sg_poll] == [sg_poll, sg_poll] and first == kids + [FOOTER] and
          second == first,
          'the page\'s update: kits save\'s ks_sg_poll first, then (a knob turned) the three columns and the footer '
          'drawn again, once')
    # 7. The bar (SY test 6: blank on the screen): no item name, its PRM part painted over (x 57..127, the item box's
    #    rows), no value, the stock function ends / goes on at 0x80123c5a, redrawn when SOUND changed; outside it the
    #    arp's bridges with every register as it came.
    b = ScreenMachine(img, man, page=SG_PAGE)
    b.start()
    b.put(sym['sy'] + b.sl.mode, 1, '<I')
    b.ev(EV_ENC, 0, 4)
    name = b.bar_name()
    text = b.bar_text()
    bar_text = [d[1:4] for d in b.draws if d[0] == 'text']           # SY test 7: OUT: DRY
    poll = b.bar_poll()
    poll2 = b.bar_poll()
    b.put(sym['sy'] + b.sl.mode, 0, '<I')
    name_o = b.bar_name()
    text_o = b.bar_text()
    check(name[:2] == ('end', '') and text[:2] == ('drawn', '') and bar_text == [(92, BAR_Y0 + 1, 'OUT: DRY')] and
          text[4] == [('color', 0xFFFFFF, 0), ('rect', 57, BAR_Y0, 127, BAR_Y1)] and
          poll[0] == 'arp' and poll[1] == [BAR_SCREEN] and poll[2] and poll2[1] == [] and
          name_o[0] == 'arp' and name_o[2] and text_o[0] == 'arp' and text_o[3],
          f'the bar on the screen: no item name, x 57..127 of the item box\'s rows painted over, no value, the '
          f'displaced draw skipped, SY test 7\'s "OUT: DRY" centred there; redrawn once after SOUND changed; outside it '
          f'the arp\'s bridges with r0-r5 and lr as they came ({name}, {text[:2]}, {text[4]}, {bar_text})')
    # 8. Leaving and the input: SHIFT + RECORD SETTING gives the page back (and goes on); the chord with EXT SOURCE off
    #    (the press toggled it off) puts it on; with GATE, its release putting it off: on again; a page asked for that
    #    never comes: given up after 1 s.
    q = ScreenMachine(img, man, page=SG_PAGE)
    q.start()
    q.hold(KEY_EXT, True)
    q.ev(EV_KEY, KEY_REC_SET)
    on_page = q.sy()['mode']
    q.hold(KEY_EXT, False)
    q.ev(EV_KEY_UP, KEY_REC_SET)
    q.hold(KEY_SHIFT, True)
    back = q.ev(EV_KEY, KEY_REC_SET)
    q.hold(KEY_SHIFT, False)
    st8 = q.sy()
    e = ScreenMachine(img, man, ext=0)
    e.start()
    e.hold(KEY_EXT, True)
    e.ev(EV_KEY, KEY_REC_SET)
    sets1 = list(e.sets)
    e.ext = 0                                                          # GATE: the release put it off
    e.call(sym['sy_ui'])
    held_sets = len(e.sets)
    e.hold(KEY_EXT, False)
    e.call(sym['sy_ui'])
    sets2 = list(e.sets)
    e.call(sym['sy_ui'])
    w = ScreenMachine(img, man)
    w.start()
    w.hold(KEY_EXT, True)
    w.ev(EV_KEY, KEY_REC_SET)
    w.cyc += 600_000_001
    w.call(sym['sy_ui'])
    check(on_page == 1 and back == (0, True) and st8['mode'] == 0 and st8['leaves'] == 1 and
          sets1 == [(0x25, 1, 0)] and held_sets == 1 and sets2 == [(0x25, 1, 0), (0x25, 1, 0)] and
          len(e.sets) == 2 and w.sy()['mode'] == 0 and w.requests == [SG_PAGE],
          'on the Sound Generator page the chord opens the screen at once; SHIFT + RECORD SETTING closes it and goes on '
          '(the stock Sound Generator); with EXT SOURCE off the chord puts it on (the settings setter, 0x25 = 1), and '
          'again once EXT SOURCE is let go if GATE put it off; a page that never comes: given up after 1 s')
    # 9. The synth plays on the Sound Generator page in the screen (the tracker's synth, test 6, does not).
    g = SyMachine(img, man, page=SG_PAGE)
    g.put(sym['sy'] + g.sl.mode, 1, '<I')
    g.start()
    sig = ref.to_blocks(sy_strum('G')[0])
    for k in range(200):                                               # SY test 12: the first note at block 128
        sg = g.step(sig[k])
    t6 = g.tt()
    check(sg['state'] == SY_RUN and any(sg['out']) and t6['req'] == 0 and g.gsyn()['ons'] == 0,
          'in the screen the SY synth plays on the Sound Generator page; the tracker (guitar synth test 6) stays off')
    # 10. SY test 6: an FX screen up on the screen: the knobs, VALUE (turned and pushed) and SHIFT are its (they go on,
    #     the synth's settings and page stay); the pads stay the screen's (a pick, silent) unless MFX is held: then
    #     they go on (MFX + a pad picks an effect).
    f = ScreenMachine(img, man, page=SG_PAGE)
    f.start()
    f.put(sym['sy'] + f.sl.mode, 1, '<I')
    fx_up = fx_view(f)
    fb = f.sy()
    fr = [f.ev(EV_KNOB, 1, 10), f.ev(EV_KNOB, 3, 120), f.ev(EV_ENC, 0, 1), f.ev(EV_KEY, KEY_VALUE),
          f.ev(EV_KEY_UP, KEY_VALUE), f.ev(EV_KEY, KEY_SHIFT), f.ev(EV_KEY_UP, KEY_SHIFT)]
    fa = f.sy()
    pad = [f.ev(EV_PAD, 5, 90), f.ev(EV_KEY, 5), f.ev(EV_PAD_UP, 5), f.ev(EV_KEY_UP, 5)]
    tone_pad = f.sy()['tone_req']
    f.hold(KEY_MFX, True)
    mpad = [f.ev(EV_PAD, 6, 90), f.ev(EV_KEY, 6), f.ev(EV_PAD_UP, 6), f.ev(EV_KEY_UP, 6)]
    f.hold(KEY_MFX, False)
    tone_mfx = f.sy()['tone_req']
    fx_up[0] = False
    back = f.ev(EV_KNOB, 1, 10)
    check(all(x == (0, True) for x in fr) and fa['knob'] == fb['knob'] and fa['tone_req'] == fb['tone_req'] and
          fa['muted'] == fb['muted'] and fa['shift_page'] == fb['shift_page'] and fa['fx_passes'] == 7 and
          all(x == (1, False) for x in pad) and tone_pad == 5 and all(x == (0, True) for x in mpad) and
          tone_mfx == 5 and back == (1, False),
          'an FX screen up on the screen: CTRL 1-3, VALUE (turned, pushed) and SHIFT go on to it, the synth\'s settings '
          'untouched (its screen closed for want of them on the unit); a pad stays the screen\'s, silent, unless MFX is '
          'held (then it goes on: MFX + a pad picks an effect); the FX screen gone, the knobs are the screen\'s again')
    # 11. SY test 6: REMAIN on the Sound Generator page: its press taken and its held bit set (an FX screen opened while
    #     it is held reads it and freezes); let go alone: the stock press and release follow (the preview bus); held +
    #     an FX button: the button goes on, no stock REMAIN; with a frozen FX screen up: an EXIT closes it and the flag
    #     is cleared; with one up not frozen, and on another page: REMAIN goes on as stock.
    rm = ScreenMachine(img, man, page=SG_PAGE)
    rm.start()

    def bit(x):
        return (x.get(base.KEYS + (KEY_REMAIN >> 3), '<B') >> (KEY_REMAIN & 7)) & 1
    d1 = rm.ev(EV_KEY, KEY_REMAIN)
    held1 = bit(rm)
    u1 = rm.ev(EV_KEY_UP, KEY_REMAIN)
    held2 = bit(rm)
    tap = list(rm.stock_keys)
    rm.stock_keys.clear()
    d2 = rm.ev(EV_KEY, KEY_REMAIN)
    fxk = [rm.ev(EV_KEY, KEY_FX1 + 2), rm.ev(EV_KEY_UP, KEY_FX1 + 2)]       # DELAY
    u2 = rm.ev(EV_KEY_UP, KEY_REMAIN)
    after_hold = list(rm.stock_keys)
    st_r = rm.sy()
    up_r = fx_view(rm)
    rm.put(FX_FROZEN, 1, '<B')
    d3 = rm.ev(EV_KEY, KEY_REMAIN)
    u3 = rm.ev(EV_KEY_UP, KEY_REMAIN)
    closed = list(rm.stock_keys)
    frozen = rm.get(FX_FROZEN, '<B')
    rm.stock_keys.clear()
    d4 = rm.ev(EV_KEY, KEY_REMAIN)
    u4 = rm.ev(EV_KEY_UP, KEY_REMAIN)
    up_r[0] = False
    mm = ScreenMachine(img, man)
    mm.start()
    d5 = mm.ev(EV_KEY, KEY_REMAIN)
    u5 = mm.ev(EV_KEY_UP, KEY_REMAIN)
    check(d1 == (1, False) and held1 == 1 and u1 == (1, False) and held2 == 0 and
          tap == [(EV_KEY, KEY_REMAIN, 0), (EV_KEY_UP, KEY_REMAIN, 0)] and
          d2 == (1, False) and fxk == [(0, True), (0, True)] and u2 == (1, False) and after_hold == [] and
          st_r['rem_taps'] == 1 and st_r['rem_holds'] == 1 and st_r['rem_down'] == 0 and
          d3 == (1, False) and u3 == (1, False) and closed == [(EV_KEY, KEY_EXIT, 0), (EV_KEY_UP, KEY_EXIT, 0)] and
          frozen == 0 and d4 == (0, True) and u4 == (0, True) and not rm.stock_keys and
          d5 == (0, True) and u5 == (0, True) and not mm.stock_keys,
          'REMAIN on the Sound Generator page: its press taken, its held bit set (an FX screen opened now freezes) and '
          'cleared at the release; alone, the stock press and release follow it (the preview bus); held + DELAY: the '
          'button goes on, no stock REMAIN; with a frozen FX screen up: taken, an EXIT closes it, the flag cleared; '
          'not frozen, and on the main screen: REMAIN goes on as stock')
    # 12. SY test 7: VALUE's push steps the synth's bus, DRY -> BUS 1 -> BUS 2 -> BOTH -> DRY, its press and release
    #     taken; the bar shows each ("OUT: BUS 2"), redrawn after each; written to the file's byte 128 (SY test 11's
    #     version 4; 98 in version 3) at a key release
    #     and read back; a bad byte there (4) read as DRY.
    v = ScreenMachine(img, man, page=SG_PAGE)
    v.start()
    v.put(sym['sy'] + v.sl.mode, 1, '<I')
    seen, texts, pushes, polls = [], [], [], []
    for _ in range(4):
        pushes += [v.ev(EV_KEY, KEY_VALUE), v.ev(EV_KEY_UP, KEY_VALUE)]
        seen.append(v.sy()['out_bus'])
        polls.append(v.bar_poll()[1] == [BAR_SCREEN])
        v.bar_text()
        texts.append([d[3] for d in v.draws if d[0] == 'text'])
    v.ev(EV_KEY, KEY_VALUE)
    v.ev(EV_KEY, KEY_VALUE)
    v.ev(EV_KEY_UP, KEY_VALUE)                                       # BUS 2 (its release is taken: no file)
    v.ev(EV_KEY_UP, 0x20)                                            # a key release that goes on writes it
    wrote = v.files.writes[-1][1] if v.files.writes else b''
    vf, _ = ScreenMachine(img, man, store={SY_PATH: wrote}), None
    vf.start()
    vf.ev(EV_KEY, KEY_EXT)
    bad = sy_file_bytes(0, 0, [[0, 0, 0]] * 20, bus=4)
    vb = ScreenMachine(img, man, store={SY_PATH: bad})
    vb.start()
    vb.ev(EV_KEY, KEY_EXT)
    check(all(x == (1, False) for x in pushes) and seen == [1, 2, 3, 0] and all(polls) and
          texts == [['OUT: BUS 1'], ['OUT: BUS 2'], ['OUT: BOTH'], ['OUT: DRY']] and len(wrote) == 136 and
          wrote[128] == 2 and vf.sy()['out_bus'] == 2 and vf.sy()['loads'] == 1 and vb.sy()['out_bus'] == 0 and
          vb.sy()['loads'] == 1,
          f'SY test 7: VALUE\'s push steps the synth\'s bus DRY -> BUS 1 -> BUS 2 -> BOTH -> DRY ({seen}), press and '
          f'release taken; the bar shows each ({texts}), redrawn after each; the file keeps it (byte 128 = '
          f'{wrote[128] if wrote else None}) and gives it back; a bus byte out of range reads as DRY')
    # 13. SY test 8: the synth plays from the screen on. EXT SOURCE on, the screen never opened: no engine, no ROUTING
    #     hold; the screen opens: armed, the hold and the engine; EXIT to the main screen: it plays on; EXT SOURCE off:
    #     disarmed; on again: silent (no hold) until the screen opens again.
    a = ScreenMachine(img, man, armed=False)
    a.start()
    a.call(sym['sy_ui'])
    s0, hold0 = a.sy(), list(a.routing_dt1())
    a.open_screen()
    a.ui(0)
    a.call(sym['sy_ui'])
    s1, hold1 = a.sy(), list(a.routing_dt1())
    a.page(1)
    a.call(sym['sy_ui'])
    a.ui(0)
    a.call(sym['sy_ui'])
    s2 = a.sy()
    a.ext = 0
    a.ui(0)
    a.call(sym['sy_ui'])
    s3 = a.sy()
    a.ext = 1
    a.ui(0)
    a.call(sym['sy_ui'])
    s4, hold4 = a.sy(), list(a.routing_dt1())
    check(s0['armed'] == 0 and s0['req'] == 0 and not hold0 and s1['armed'] == 1 and s1['mode'] == 1 and
          hold1 and hold1[-1] == 1 and s1['req'] == 1 and s2['mode'] == 0 and s2['armed'] == 1 and s2['req'] == 1 and
          s3['armed'] == 0 and s3['req'] == 0 and s4['armed'] == 0 and s4['req'] == 0 and
          len(hold4) == len(hold1) + 1 and hold4[-1] == a.tt()['routing'],
          f'SY test 8: EXT SOURCE on, the screen never opened: no synth, no ROUTING hold; the screen opened: armed, held '
          f'on ExtIn, the synth on; EXIT: it plays on; EXT SOURCE off: disarmed, the hold let go (the user\'s ROUTING '
          f'sent back); on again: silent until the screen opens (ROUTING sent {hold0} / {hold1} / {hold4})')
    # 14. SY test 10: the footer drawn on the plain Sound Generator page (outside the screen) is kept, so opening the
    #     screen over that page redraws it at once; the chord on the looper page (0x27) opens the screen; with looper
    #     mode on (0x82e0b92c), REC on the screen goes on (the looper's), off: taken as before.
    f2 = ScreenMachine(img, man, page=SG_PAGE)
    f2.start()
    page2 = SCRATCH + 0x1000
    kids2 = [SCRATCH + 0xA00 + 0x40 * k for k in range(3)]
    f2.uc.mem_write(page2 + 0x1A6C, struct.pack('<3I', *kids2))
    f2.draw_footer()                                   # the page's own footer ("CHROMATIC INPUT"), the screen not up
    kept = f2.sy()['foot']
    f2.hold(KEY_EXT, True)
    f2.ev(EV_KEY, KEY_REC_SET)
    f2.hold(KEY_EXT, False)
    f2.ev(EV_KEY_UP, KEY_REC_SET)
    f2.call(sym['sy_ui'])
    f2.invalid.clear()
    f2.call(sym['sy_sg_poll'], page2)
    redrawn = list(f2.invalid)
    lp = ScreenMachine(img, man, page=0x27)
    lp.start()
    lp.hold(KEY_EXT, True)
    lchord = lp.ev(EV_KEY, KEY_REC_SET)
    lp.hold(KEY_EXT, False)
    lreq = list(lp.requests)
    rc = ScreenMachine(img, man, page=SG_PAGE)
    rc.start()
    rc.put(sym['sy'] + rc.sl.mode, 1, '<I')
    rc.put(0x82E0B92C, 1, '<B')
    rec_on = [rc.ev(EV_KEY, KEY_REC), rc.ev(EV_KEY_UP, KEY_REC)]
    rc.put(0x82E0B92C, 0, '<B')
    rec_off = [rc.ev(EV_KEY, KEY_REC), rc.ev(EV_KEY_UP, KEY_REC)]
    check(kept == FOOTER and redrawn == kids2 + [FOOTER] and lchord == (1, False) and lreq == [SG_PAGE] and
          rec_on == [(0, True), (0, True)] and rec_off == [(1, False), (1, False)],
          f'SY test 10: the page\'s own footer kept outside the screen, so the screen opened over the page redraws it '
          f'with the columns ({redrawn}); the chord on the looper page asks for the Sound Generator page ({lreq}); with '
          f'looper mode on REC goes on to the looper, with it off REC is taken as before')
    report['sy']['screen'] = dict(columns=want_cols, footer='ENSEMBLE', bar='OUT: <bus>', fx_passes=fa['fx_passes'],
                                  remain=dict(taps=st_r['rem_taps'], holds=st_r['rem_holds']), bus_texts=texts)


def sy_route_checks(img, man):
    """SY test 4: ROUTING held on ExtIn while a synth listens, and what the recorder feed is given meanwhile."""
    sym = man['symbols']
    bmc = 0x80592500
    rng = random.Random(44)
    g = [rng.randint(-12000, 12000) for _ in range(64)]                  # the guitar alone (pair 0 on ExtIn)
    mx = [rng.randint(-20000, 20000) for _ in range(64)]                 # the mix before BUS 3/4, half level (pair 1)

    def sat(v):
        return max(-32768, min(32767, v))
    # 1. ROUTING Mix: the recorder's pair 0 := pair 1 x 2 (saturated), pair 1 left; the tracker had the guitar first.
    m = SyMachine(img, man, routing=0)
    m.start()
    m.call(sym['sy_feed'], m.packet(g, mx), 0x800)
    fed = m.feeds[-1][2]
    t = m.tt()
    check([x[0] for x in fed] == [sat(2 * v) for v in mx] and [x[1] for x in fed] == [sat(2 * v) for v in mx] and
          [x[2] for x in fed] == mx and t['in'] == g and t['rec_blocks'] == 1 and any(abs(2 * v) > 32767 for v in mx),
          'ROUTING Mix, held: the feed copies pair 1 x 2 as pair 0 (the mix before BUS 3/4, saturated at 16 bits), '
          'pair 1 left; the tracker read the guitar before')
    # 2. The feed taking pair 1 itself (settings + 0x64) or another pair (the byte): the packet left as it is.
    kept = []
    for addr, fmt in ((FEED_PAIR1, '<I'), (FEED_PAIR, '<B')):
        m.put(addr, 1, fmt)
        m.call(sym['sy_feed'], m.packet(g, mx), 0x800)
        kept.append([x[0] for x in m.feeds[-1][2]] == g)
        m.put(addr, 0, fmt)
    check(all(kept) and m.tt()['rec_other'] == 2 and m.tt()['rec_blocks'] == 1,
          'the feed taking pair 1 itself or another pair: the packet left as stock has it')
    # 3. ROUTING ExtIn: the synth's newest block, as sy_tx added it to TX, added to the input once.
    e = SyMachine(img, man)
    e.start()
    sig = ref.to_blocks(sy_strum('G')[0])
    for b in range(200):
        e.step(sig[b])
    out = e.sy()['out']
    e.uc.mem_write(TXBUF, bytes(4096))
    e.uc.mem_write(base.ARGS, struct.pack('<3I', TXBUF, TXBUF + 0x1000, TXBUF + 0x2000))
    e.call(sym['sy_tx'], base.ARGS, 1000)
    se = e.sy()
    e.call(sym['sy_feed'], e.packet(g, mx), 0x800)
    fed = e.feeds[-1][2]
    e.call(sym['sy_feed'], e.packet(g, mx), 0x800)
    fed2 = e.feeds[-1][2]
    check(any(out) and se['rec'] == [sat(v) for v in out] and se['rec_fresh'] == 1 and
          [x[0] for x in fed] == [sat(a + r) for a, r in zip(g, se['rec'])] and [x[2] for x in fed] == mx and
          [x[0] for x in fed2] == g and e.tt()['rec_adds'] == 1 and e.sy()['rec_fresh'] == 0 and
          e.tt()['rec_mix'] == 0,
          'ROUTING ExtIn, held: the feed copies the input with the synth\'s newest block added (as sy_tx added it to '
          'TX), once per block')
    # 4. The synth off (SOUND OFF) on the main screen: the hold lets go, ROUTING (Mix) sent back, after 30 ms the packet
    #    is the feed's own.
    o = SyMachine(img, man, routing=0)
    o.start()
    o.put(sym['sy'] + 4 * SY_HEAD.index('muted'), 1, '<I')
    o.ui(0)
    during = o.tt()['rec_mix']
    o.cyc += REC_GRACE
    o.call(sym['tune_ui'])
    o.call(sym['sy_feed'], o.packet(g, mx), 0x800)
    check(o.routing_dt1() == [1, 0] and during == 1 and o.tt()['hold'] == 0 and o.tt()['rec_mix'] == 0 and
          [x[0] for x in o.feeds[-1][2]] == g,
          'the synth off (SOUND OFF) on the main screen: the hold lets go and Mix goes back to the chip; the recorder '
          'keeps the mix 30 ms, then takes pair 0 as stock')
    # 5. A ROUTING DT1 the firmware sends while held goes out as ExtIn; other IDs untouched, on the caller's stack;
    #    with nothing listening, as sent.
    h = SyMachine(img, man, routing=0)
    h.start()
    h.dt1.clear()
    h.dt1_sp.clear()
    h.call(0x800D8119, bmc, 0x5C, 0, 0)
    h.call(0x800D8119, bmc, 0x2B, 0, 5)
    th = h.tt()
    q = SyMachine(img, man, ext=0, routing=0)
    q.start()
    q.dt1.clear()
    q.call(0x800D8119, bmc, 0x5C, 0, 0)
    check(h.dt1 == [(bmc, 0x5C, 0, 1), (bmc, 0x2B, 0, 5)] and h.dt1_sp[1] == STACK and th['route_sends'] == 2 and
          th['route_held'] == 2 and th['route_last'] == 1 and q.dt1 == [(bmc, 0x5C, 0, 0)] and
          q.tt()['route_held'] == 0,
          f'held: a ROUTING DT1 from the firmware (RECORD SETTING, the looper, a chip reset) goes to FX deep edit\'s '
          f'fde_dt1 as ExtIn; another ID untouched, the stack as the caller left it; nothing listening: as sent')
    report['sy']['routing'] = dict(recorder_mix='pair 1 x 2', recorder_extin='input + synth', grace_ms=30, settle_ms=20)


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


def crash_checks(parent_img, img, man):
    """SY test 18, the crash catcher: the four fault vectors -> sy_fault; the handler (entered with a fake stacked
    frame, EXC_RETURN 0xFFFFFFF9: MSP) keeps the frame and the SCB's fault registers in sy_crash with its FNV-1a sum,
    cleans the record's D-cache lines, writes SYSRESETREQ and writes nothing else but its own stack; after a 'reboot'
    (a fresh machine with the record kept) the UI tick shows it once in a popup after CRASH_WAIT_MS, and a fresh machine
    without one shows nothing."""
    sym = man['symbols']
    fault, crash = sym['sy_fault'], sym['sy_crash']
    vec = [Machine(i).get(a, '<I') for i in (parent_img, img) for a in (0xC, 0x10, 0x14, 0x18)]
    check(vec[:4] == [0x8003C921, 0x800406A9, 0x80036119, 0x800437D1] and vec[4:] == [fault | 1] * 4 and
          crash == 0x83FE7F80,
          f'SY test 18: the ITCM vector table\'s HardFault, MemManage, BusFault and UsageFault entries -> sy_fault '
          f'({[hex(v) for v in vec]}); sy_crash at the SY slot\'s top ({crash:#x})')
    m = SyMachine(img, man)
    frame = 0x20280000 - 0x100                                 # a stack in OCRAM, as the SP's tasks have
    words = [0x10, 0x11, 0x12, 0x13, 0x1C, 0x12345679, 0x8001234A, 0x21000000]
    m.uc.mem_write(frame, struct.pack('<8I', *words))
    scb = {0xE000ED28: 0x00008200, 0xE000ED2C: 0x40000000, 0xE000ED34: 0, 0xE000ED38: 0xDEADBEE0}
    for a, v in scb.items():
        m.put(a, v, '<I')
    writes, stop = [], []

    def on_write(uc, access, address, size, value, _):
        writes.append((address, size, value & 0xFFFFFFFF))
        if address == 0xE000ED0C:
            stop.append(value & 0xFFFFFFFF)
            uc.emu_stop()
    h = m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
    m.uc.reg_write(ar.UC_ARM_REG_SP, frame)
    m.uc.reg_write(ar.UC_ARM_REG_LR, 0xFFFFFFF9)
    m.uc.emu_start(fault | 1, 0, count=200000)
    m.uc.hook_del(h)
    rec = struct.unpack('<14I', m.bytes(crash, 56))

    def fnv(ws):
        x = 2166136261
        for w in ws:
            for b in struct.pack('<I', w):
                x = ((x ^ b) * 16777619) & 0xFFFFFFFF
        return x
    page = m.get(base.PAGE, '<h')
    want = [0, 0x8001234A, 0x12345679, 0x21000000, frame, 0x00008200, 0x40000000, 0, 0xDEADBEE0, 0xFFFFFFF9,
            m.get(m.sym['sy_block'] + m.sl.started + 4, '<I'), page & 0xFFFFFFFF]
    cleans = sorted(v for a, s, v in writes if a == 0xE000EF68)
    other = [(hex(a), s) for a, s, v in writes if not (crash <= a < crash + 56 or a in (0xE000EF68, 0xE000ED0C) or
                                                        frame - 0x100 <= a < frame)]
    check(stop == [0x05FA0004] and list(rec[:12]) == want and rec[12] == fnv(want) and rec[13] == 0x48535243 and
          cleans == [0x83FE7F80, 0x83FE7FA0] and not other,
          f'SY test 18: sy_fault keeps the stacked PC, LR, xPSR, the stack, CFSR, HFSR, MMFAR, BFAR, EXC_RETURN, the '
          f'SY blocks and the page in sy_crash with its FNV-1a sum and the magic, cleans its two D-cache lines '
          f'({[hex(c) for c in cleans]}), then writes SYSRESETREQ ({[hex(v) for v in stop]}); nothing else written '
          f'but its stack ({other[:4]}; record {[hex(v) for v in rec]})')
    kept = m.bytes(crash, 56)
    shown = []
    for record in (kept, None):
        r = SyMachine(img, man)
        if record is not None:
            r.uc.mem_write(crash, record)
        r.popups()
        texts = []
        for k in range(6):
            r.call(r.sym['diag_ui'], 1000)
            t = r.posted()
            if t is not None:
                texts.append((k, t))
                r.popups()
        shown.append((texts, r.get(crash + 52, '<I')))
    expect = 'SY CRASH 0\nPC 8001234A\nLR 12345679\nCF 00008200\nAD DEADBEE0'
    check(shown[0] == ([(4, expect)], 0) and shown[1][0] == [],
          f'SY test 18: after a reboot the UI tick shows the kept crash once, 4 s in ({shown[0][0]}), and clears its '
          f'magic; without one nothing shows ({shown[1][0]})')
    # SY test 21: an imprecise bus error alone (CFSR = IMPRECISERR, HFSR = FORCED) returns as the stock handler (bx lr)
    # does: its two status bits cleared, no record, no reset; with anything more it resets as above.
    import capstone
    from unicorn import UcError
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    fa = fault & ~1                                            # the symbol carries the Thumb bit
    code = Machine(img).bytes(fa, 0x60)
    bx = next(i.address for i in md.disasm(code, fa) if i.mnemonic == 'bx' and i.op_str == 'lr')
    outcomes = []
    for cfsr, hfsr in ((0x400, 0x40000000), (0x400, 0x0), (0x8400, 0x40000000), (0x400, 0x40000002),
                       (0x100, 0x40000000)):
        m3 = SyMachine(img, man)
        m3.uc.mem_write(frame, struct.pack('<8I', *words))
        for a, v in {0xE000ED28: cfsr, 0xE000ED2C: hfsr, 0xE000ED34: 0, 0xE000ED38: 0}.items():
            m3.put(a, v, '<I')
        w3, last = [], []

        def on_w3(uc, access, address, size, value, _):
            w3.append((address, size, value & 0xFFFFFFFF))
            if address == 0xE000ED0C:
                uc.emu_stop()
        h3 = m3.uc.hook_add(UC_HOOK_MEM_WRITE, on_w3)
        hc = m3.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: last.append(a), begin=fa, end=fa + 0x60)
        m3.uc.reg_write(ar.UC_ARM_REG_SP, frame)
        m3.uc.reg_write(ar.UC_ARM_REG_LR, 0xFFFFFFFD)
        try:
            m3.uc.emu_start(fault | 1, 0, count=200000)
        except UcError:
            pass
        m3.uc.hook_del(h3)
        m3.uc.hook_del(hc)
        resets = [v for a, s, v in w3 if a == 0xE000ED0C]
        scb = [(hex(a), hex(v)) for a, s, v in w3 if a in (0xE000ED28, 0xE000ED2C)]
        rec3 = struct.unpack('<14I', m3.bytes(crash, 56))
        outcomes.append((hex(cfsr), hex(hfsr), bool(resets), scb, rec3[13] == 0x48535243, last[-1:] == [bx]))
    want3 = [('0x400', '0x40000000', False, [('0xe000ed28', '0x400'), ('0xe000ed2c', '0x40000000')], False, True),
             ('0x400', '0x0', False, [('0xe000ed28', '0x400'), ('0xe000ed2c', '0x40000000')], False, True),
             ('0x8400', '0x40000000', True, [], True, False),
             ('0x400', '0x40000002', True, [], True, False),
             ('0x100', '0x40000000', True, [], True, False)]
    check(outcomes == want3,
          f'SY test 21: an imprecise bus error alone (CFSR 0x400, HFSR FORCED or 0) goes on as stock\'s bare return '
          f'does (bx lr at {bx:#x}, CFSR and HFSR cleared, no record, no reset); with a precise one, VECTTBL or an '
          f'instruction fault it keeps the record and resets ({outcomes})')
    # SY test 21: a fault inside an FPU step comes back without a reset. A strum playing (110 blocks), then a step
    # stopped where render begins (deep in sy_rx -> sy_fp_call -> sy_fp_step -> syv_block), its frame stacked under the
    # step's SP as the core would (thread mode, process stack: EXC_RETURN 0xFFFFFFFD); sy_fault_c (as sy_fault branches
    # to it, on another stack) points the frame at sy_recover; the exception return (the frame popped into the
    # registers) runs sy_recover, back into sy_rx after its call, which stops the engine and returns. Every register
    # the caller had (r4-r11, s0-s31, FPSCR, sp) as it was; the record kept, no reset; the popup at the next UI tick.
    mf = SyMachine(img, man)
    mf.start()
    sig = ref.to_blocks(sy_strum('Am')[0])
    for b in range(110):
        mf.step(sig[b])
    mf.popups()
    mf.call(mf.sym['diag_ui'], 1)                              # crash_ui has looked once: no record at the boot
    render = man['functions']['render'][0]
    rngf = random.Random(21)
    pattern = [rngf.getrandbits(32) for _ in range(32)]
    for k in range(32):
        mf.uc.reg_write(getattr(ar, f'UC_ARM_REG_S{k}'), pattern[k])
    mf.uc.reg_write(ar.UC_ARM_REG_FPSCR, 0x00400000)
    gpr = [rngf.getrandbits(32) for _ in range(8)]
    for k, v in enumerate(gpr):
        mf.uc.reg_write(getattr(ar, f'UC_ARM_REG_R{k + 4}'), v)
    for a, v in {0xE000ED28: 0x82, 0xE000ED2C: 0x40000000, 0xE000ED34: 0xDEAD0000, 0xE000ED38: 0}.items():
        mf.put(a, v, '<I')
    mf.feed(sig[110])
    stop = []
    hr = mf.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: (stop.append(a), uc.emu_stop()), begin=render, end=render)
    mf.uc.reg_write(ar.UC_ARM_REG_SP, STACK)
    mf.uc.reg_write(ar.UC_ARM_REG_LR, RET | 1)
    mf.uc.emu_start(mf.sym['sy_rx'] | 1, RET, count=20_000_000)
    mf.uc.hook_del(hr)
    step_sp = mf.uc.reg_read(ar.UC_ARM_REG_SP)
    frame = step_sp - 32
    lr_at = mf.uc.reg_read(ar.UC_ARM_REG_LR)
    mf.uc.mem_write(frame, struct.pack('<8I', *(mf.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(4)),
                                       mf.uc.reg_read(ar.UC_ARM_REG_R12), lr_at, render, 0x01000000))
    wf = []
    hw = mf.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, acc, a, s, v, _: wf.append((a, v & 0xFFFFFFFF)))
    mf.call(mf.sym['sy_fault_c'], frame, 0xFFFFFFFD, sp=STACK - 0x400)
    fr = struct.unpack('<8I', mf.bytes(frame, 32))
    for k, v in enumerate(fr[:4]):                             # the exception return: the frame into the registers
        mf.uc.reg_write(getattr(ar, f'UC_ARM_REG_R{k}'), v)
    mf.uc.reg_write(ar.UC_ARM_REG_R12, fr[4])
    mf.uc.reg_write(ar.UC_ARM_REG_LR, fr[5])
    mf.uc.reg_write(ar.UC_ARM_REG_SP, frame + 32)
    mf.uc.emu_start(fr[6] | 1, RET, count=100000)
    mf.uc.hook_del(hw)
    tops = mf.sym['tt_block'] + mf.lay.b_stack + 2048           # the steps' stack top
    back = dict(pc=mf.uc.reg_read(ar.UC_ARM_REG_PC) == RET, sp=mf.uc.reg_read(ar.UC_ARM_REG_SP) == STACK,
                r4_r11=[mf.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k + 4}')) for k in range(8)] == gpr,
                s0_s31=[mf.uc.reg_read(getattr(ar, f'UC_ARM_REG_S{k}')) for k in range(32)] == pattern,
                fpscr=mf.uc.reg_read(ar.UC_ARM_REG_FPSCR) & 0xF7C0009F == 0x00400000)
    rec4 = struct.unpack('<14I', mf.bytes(crash, 56))
    st4 = mf.sy()
    tts = mf.get(mf.sym['tt'] + 32, '<I')
    live = mf.get(mf.sym['sy_crash_live'], '<I')
    resets4 = [v for a, v in wf if a == 0xE000ED0C]
    scb4 = [(hex(a), hex(v)) for a, v in wf if a in (0xE000ED28, 0xE000ED2C)]
    steps4 = st4['steps']
    mf.step(sig[111])                                          # stopped: the next block does nothing
    mf.popups()
    mf.call(mf.sym['diag_ui'], 1)
    shown4 = mf.posted()
    expect4 = f'SY CRASH 0\nPC {render:08X}\nLR {lr_at:08X}\nCF 00000082\nAD DEAD0000'
    check(stop == [render] and fr[0] == tops - 176 and fr[6] == mf.sym['sy_recover'] & ~1 and fr[7] == 0x01000000 and
          all(back.values()) and rec4[13] == 0x48535243 and rec4[1] == render and not resets4 and
          scb4 == [('0xe000ed28', '0x82'), ('0xe000ed2c', '0x40000000')] and st4['state'] == 2 and tts == 2 and
          live == 1 and mf.sy()['steps'] == steps4 and shown4 == expect4,
          f'SY test 21: a fault in an FPU step (here as render begins, the step\'s stack at {step_sp:#x}) comes back '
          f'without a reset: the frame to sy_recover (r0 the saved block {fr[0]:#x}, xPSR {fr[7]:#x}), the caller\'s '
          f'registers as they were ({back}), the engine and the tracker SLOW ({st4["state"]}, {tts}), the record kept '
          f'(PC {rec4[1]:#x}), CFSR and HFSR cleared {scb4}, no reset {resets4}; the next block does nothing; the '
          f'popup at the next UI tick ({shown4!r})')
    report['crash'] = dict(handler=hex(fault), record=hex(crash), popup=expect, imprecise_return=hex(bx),
                           recover=hex(mf.sym['sy_recover']), recovered_popup=shown4)


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
        crash_checks(parent_img, img, man)                    # SY test 18
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
