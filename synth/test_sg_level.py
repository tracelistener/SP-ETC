"""LEVEL for MIDI notes on the Sound Generator (build_sg_level.py), through the real stock MIDI dispatcher.

Both APP1s boot into Unicorn the way test_kit_midi.py's machine does (its harness: the scatter rows in order, real
Sound Generator code, the RTOS dispatch and delay calls and the peripherals stubbed; no screen, no timing). The
build is compared with its parent (combined-test17) wherever nothing should change. This is not a hardware test.

1. Layout: the three patches and the module in place, every guard holding with them put back, the kit stage
   v9.46's apart from the kit footer's byte and the entry patch.
2. LEVEL: SetParam sets it (clamped as stock) and the voices as the parent's; it reads back as set at power-on
   (127) and after pad and MIDI notes (the parent reads the last note's velocity); the other settings as the parent.
3. MIDI, ARP off, M.CH 16 and M.CH 1: every LEVEL x velocity, a note-on's voice at velocity x LEVEL / 127 (at least 1)
   x 100; note-offs (also a note-on at velocity 0) release. A note at velocity v and LEVEL l plays exactly as the
   parent's note at the scaled velocity (voices and audio, sample for sample); at LEVEL 127 a chord-and-steal
   sequence is the parent's.
4. ARP on: MIDI keys are held at the scaled velocity and the steps start at it; a LEVEL change scales the MIDI keys
   again from their own velocities (a pad key stays); with LEVEL 127 the arp's steps are the parent's.
5. Drum mode, pads: as the parent at any LEVEL.
6. CC 72 on M.CH sets LEVEL (after the screen update) and MIDI follows it.

Usage: python synth/test_sg_level.py BUILD_DIR PARENT_DIR KITS_MANIFEST
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn import arm_const as ar

from build_sg_level import GUARDS, KIT_BASE, KIT_END, KIT_FOOTER, KIT_MODULE_SHA
from build_sg_subpad import Runtime
from test_kit_midi import Machine, NOTE_ENGINE, RET, SETTINGS, STACK, VOICES

SETPARAM = 0x800DD0C0
PROJECT_PARAM = 0x800DDA38              # (0x82e009d0, id, pad): stubbed, the project's settings from SG.project
SG_PAD_TAIL = 0x8015C0C8                # the SG page's pad press, from FIXED VELOCITY on (r4 pad, r5 velocity, r6 note)
FIXED_VELOCITY = 0xDB
LEVEL = 0x7D
OTHERS = (0x7B, 0x7C, 0x7E, 0x7F, 0x80, 0x81, 0x82)
MIDI_SRC = 0x100
results = []


def check(ok, what, detail: object = None):
    results.append((bool(ok), what))
    print(('PASS ' if ok else 'FAIL ') + what + (f' ({detail})' if detail is not None else ''), flush=True)
    return ok


def sha(b):
    return hashlib.sha256(b).hexdigest()


def want(vel, level):
    if vel <= 0 or level >= 127:
        return vel
    return max(1, vel * level // 127)


class SG(Machine):
    def __init__(self, folder, symbols, entries=None):
        self.project = {}
        super().__init__(folder, symbols)
        self.E = entries or {}

    def stub(self, address, value=0, log=None):
        if address != PROJECT_PARAM:
            return super().stub(address, value, log)

        def hook(uc, a, size, _):                          # the project's settings: 0 (bank A, FIXED VELOCITY off)
            uc.reg_write(ar.UC_ARM_REG_R0, self.project.get(uc.reg_read(ar.UC_ARM_REG_R1), value))
            uc.reg_write(ar.UC_ARM_REG_PC, uc.reg_read(ar.UC_ARM_REG_LR))
        self.uc.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)

    def sg_pad(self, pad, vel):
        """The SG page's pad press from its FIXED VELOCITY test on (0x8015c0c8) to its note event and return."""
        uc, sp = self.uc, STACK - 0x18
        uc.mem_write(sp, struct.pack('<6I', 0, 0, 0, 0, 0, RET | 1))   # [sp] the note event's 5th argument; r4-r7, pc
        for reg, value in ((ar.UC_ARM_REG_R4, pad), (ar.UC_ARM_REG_R5, vel), (ar.UC_ARM_REG_R6, self.pad_note(pad)),
                           (ar.UC_ARM_REG_SP, sp)):
            uc.reg_write(reg, value & 0xFFFFFFFF)
        uc.emu_start(SG_PAD_TAIL | 1, RET, count=5_000_000)
        if uc.reg_read(ar.UC_ARM_REG_PC) != RET or uc.reg_read(ar.UC_ARM_REG_SP) != STACK:
            raise RuntimeError('the SG pad press did not return cleanly')

    def setparam(self, sid, value):
        self.call(SETPARAM, SETTINGS, sid, value, 0)

    def raw(self):
        return [bytes(self.uc.mem_read(v, 0x1B0)) for v in VOICES]

    def live(self):
        out = []
        for v in VOICES:
            raw = bytes(self.uc.mem_read(v, 0x1B0))
            if raw[0]:
                out.append(dict(released=raw[1], now=struct.unpack_from('<i', raw, 0x74)[0],
                                to=struct.unpack_from('<i', raw, 0x198)[0], midi=raw[0x194],
                                source=struct.unpack_from('<i', raw, 0x1AC)[0]))
        return out

    def mch(self, ch):
        self.setsym('kit_midi_channel', ch - 1)

    def on(self, ch, note, vel):
        return self.send(0x90 | (ch - 1), note, vel)

    def off(self, ch, note):
        return self.send(0x80 | (ch - 1), note, 0)

    def held(self):
        n = self.sym('held_count', '<i')
        return [(self.get(self.S['held_src'] + 2 * k, '<H'), self.get(self.S['held_note'] + k, '<b'),
                 self.get(self.S['held_vel'] + k, '<B')) for k in range(n)]

    def mod(self, name, fmt='<B'):
        return self.get(self.E[name] & ~1, fmt)


def view(folder: Path, build: Path, kits: dict):
    folder.mkdir(parents=True)
    img = (build / 'SP404MKII_APP1.bin').read_bytes()
    shutil.copy2(build / 'SP404MKII_APP1.bin', folder / 'SP404MKII_APP1.bin')
    man = dict(kits, sha256=sha(img), size=len(img), view_note=f'{build.name} with the kit stage\'s manifest')
    (folder / 'manifest.json').write_text(json.dumps(man), encoding='utf-8')
    return folder


def main():
    build, parent, kits_path = (Path(a).resolve() for a in sys.argv[1:4])
    man = json.loads((build / 'manifest.json').read_text(encoding='utf-8'))
    kits = json.loads(kits_path.read_text(encoding='utf-8'))
    E = man['entries']
    tmp = Path(tempfile.mkdtemp(prefix='sg_level_'))
    try:
        new_view, old_view = view(tmp / 'new', build, kits), view(tmp / 'old', parent, kits)
        symbols = kits['symbols']
        fresh = lambda: SG(new_view, symbols, E)
        stock = lambda: SG(old_view, symbols)
        run(build, parent, man, fresh, stock)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [w for ok, w in results if not ok]
    print(json.dumps({'cases': len(results)}))
    if failed:
        print(f'{len(failed)} FAILED')
        sys.exit(1)
    print('all passed')


def run(build, parent, man, fresh, stock):
    # 1. Layout -------------------------------------------------------------------------------------------------
    img = (build / 'SP404MKII_APP1.bin').read_bytes()
    rt = Runtime(img)
    check(sha(img) == man['sha256'] and sha((parent / 'SP404MKII_APP1.bin').read_bytes()) == man['parent_sha256'],
          'the build and its parent are the manifest\'s')
    check(all(rt.read(p['address'], p['size']).hex() == p['replacement_hex'] for p in man['patches']),
          'the three patches are in place', [hex(p['address']) for p in man['patches']])
    blob = rt.read(man['blob_base'], man['blob_size'])
    check(sha(blob) == man['blob_sha256'] and man['slot'] == [0x83FA1800, 0x83FA2000],
          'the module is at its slot as built', f'{man["blob_size"]} bytes')
    bad = []
    for start, end, digest, what in GUARDS:
        got = bytearray(rt.read(start, end - start))
        for p in man['patches']:
            lo, hi = max(start, p['address']), min(end, p['address'] + p['size'])
            if lo < hi:
                got[lo - start:hi - start] = bytes.fromhex(p['original_hex'])[lo - p['address']:hi - p['address']]
        if sha(got) != digest:
            bad.append(hex(start))
    check(not bad, 'every guard holds (this step\'s own patches put back)', bad or len(GUARDS))
    dense = bytearray(rt.read(KIT_BASE, KIT_END - KIT_BASE))
    at, stock_byte, _ = KIT_FOOTER
    dense[at - KIT_BASE] = stock_byte
    entry = next(p for p in man['patches'] if p['address'] == 0x83FA3448)
    dense[0x83FA3448 - KIT_BASE:0x83FA3448 - KIT_BASE + entry['size']] = bytes.fromhex(entry['original_hex'])
    check(sha(bytes(dense)) == KIT_MODULE_SHA, 'the kit stage is v9.46\'s apart from the kit footer\'s byte and the entry')
    prt = Runtime((parent / 'SP404MKII_APP1.bin').read_bytes())
    same = all(prt.read(p['address'], p['size']).hex() == p['original_hex'] for p in man['patches'])
    check(same, 'the parent has the original bytes at every patch')

    # 2. LEVEL --------------------------------------------------------------------------------------------------
    m, s = fresh(), stock()
    check(m.setting(LEVEL) == 127 == s.setting(LEVEL) and m.mod('sgl_level') == 127, 'power-on LEVEL 127, as the parent')
    rows = []
    for v in (0, 1, 40, 64, 100, 126, 127, 200, -5):
        m.idle(); s.idle()
        m.setparam(LEVEL, v); s.setparam(LEVEL, v)
        rows.append((v, m.setting(LEVEL), s.setting(LEVEL), m.raw() == s.raw()))
    check(all(a == b and same for v, a, b, same in rows) and rows[-2][1] == 127 and rows[-1][1] == 0,
          'SetParam sets LEVEL (clamped 0..127) and the voices exactly as the parent', [r[:2] for r in rows])
    m, s = fresh(), stock()
    for x in (m, s):
        x.setparam(LEVEL, 64)
        x.call(NOTE_ENGINE, 0, x.pad_note(3), 100, 0, stack0=3)
        x.idle()
        x.on(16, 62, 90)
    check(m.setting(LEVEL) == 64 and s.setting(LEVEL) == 90, 'LEVEL reads as set after a pad and a MIDI note '
          '(the parent reads the last note\'s velocity)', (m.setting(LEVEL), s.setting(LEVEL)))
    m, s = fresh(), stock()
    vals = {0x7B: 5, 0x7C: 7, 0x7E: 12, 0x7F: 30, 0x80: -20, 0x81: 4400, 0x82: 3}
    for x in (m, s):
        for sid, v in vals.items():
            x.setparam(sid, v)
    got = [(hex(sid), m.setting(sid), s.setting(sid)) for sid in OTHERS]
    check(all(a == b for _, a, b in got) and m.raw() == s.raw(), 'the other settings and the voices as the parent', got)

    # 3. MIDI, ARP off --------------------------------------------------------------------------------------------
    for ch in (16, 1):
        bad, n = [], 0
        m = fresh()
        m.mch(ch)
        for level in (127, 100, 64, 40, 1, 0):
            m.setparam(LEVEL, level)
            for vel in (127, 100, 64, 10, 1):
                m.idle()
                m.on(ch, 60, vel)
                live = m.live()
                w = want(vel, level) * 100
                if live != [dict(released=0, now=w, to=w, midi=60, source=-1)]:
                    bad.append((level, vel, live))
                m.off(ch, 60)
                if [v['released'] for v in m.live()] != [1]:
                    bad.append((level, vel, 'off'))
                m.idle()
                m.on(ch, 60, vel)
                m.on(ch, 60, 0)                             # a note-on at velocity 0 is a note-off
                if [v['released'] for v in m.live()] != [1]:
                    bad.append((level, vel, 'on 0'))
                n += 1
        check(not bad, f'M.CH {ch}, ARP off: a note-on plays at velocity x LEVEL / 127 (at least 1) x 100, note-offs '
              f'and velocity-0 note-ons release', bad[:3] or f'{n} cases')
    bad = []
    for ch in (16, 1):
        for level, vel in ((64, 127), (40, 100), (1, 127), (0, 80), (100, 37)):
            m, s = fresh(), stock()
            for x in (m, s):
                x.mch(ch)
                x.setparam(LEVEL, level)
            m.on(ch, 64, vel)
            s.on(ch, 64, want(vel, level))
            if m.raw() != s.raw() or m.render(6) != s.render(6):
                bad.append((ch, level, vel))
    check(not bad, 'a MIDI note at velocity v and LEVEL l: the parent\'s note at the scaled velocity, voices and '
          'audio sample for sample (6 blocks)', bad or '10 cases')
    m, s = fresh(), stock()
    seq = [('on', 60, 127), ('on', 64, 100), ('on', 67, 90), ('on', 71, 80), ('on', 74, 70), ('off', 64, 0),
           ('on', 76, 60), ('off', 60, 0), ('on', 60, 127), ('off', 74, 0), ('off', 76, 0), ('off', 67, 0)]
    diffs = 0
    for kind, note, vel in seq:
        for x in (m, s):
            (x.on(16, note, vel) if kind == 'on' else x.off(16, note))
        diffs += m.raw() != s.raw()
        diffs += m.render(2) != s.render(2)
    check(diffs == 0, 'LEVEL 127: a chord, steals and note-offs exactly as the parent (voices and audio)', len(seq))

    # 4. ARP on ---------------------------------------------------------------------------------------------------
    m = fresh()
    m.setsym('arp_mode', 1, '<i')
    m.setparam(LEVEL, 64)
    m.on(16, 60, 127)
    m.on(16, 64, 100)
    m.call(NOTE_ENGINE, 0, m.pad_note(5), 90, 0, stack0=5)
    held = m.held()
    check(held == [(MIDI_SRC, 12, 64), (MIDI_SRC, 16, 50), (5, m.pad_note(5), 90)],
          'ARP on: MIDI keys held at the scaled velocity, a pad key at its own', held)
    started, steps = [], 0
    for _ in range(300):                                    # 120 BPM, 1/16: a step every ~94 blocks
        m.render(1)
        if m.sym('arp_steps', '<I') != steps:
            steps = m.sym('arp_steps', '<I')
            started.append(sorted(v['to'] for v in m.live() if not v['released'])[-1])
    check(started[:3] == [9000, 6400, 5000], 'UP: the steps start at the pad key\'s 90, then the MIDI keys\' scaled '
          'velocities (64, 50) x 100', started)
    m.setparam(LEVEL, 32)
    a = m.held()
    m.setparam(LEVEL, 127)
    b = m.held()
    m.setparam(LEVEL, 0)
    c = m.held()
    check([h[2] for h in a] == [32, 25, 90] and [h[2] for h in b] == [127, 100, 90] and [h[2] for h in c] == [1, 1, 90],
          'a LEVEL change scales the held MIDI keys again from their own velocities; the pad key stays', (a, b, c))
    m.page(0x14)
    m.setparam(LEVEL, 50)
    check([h[2] for h in m.held()] == [1, 1, 90], 'off the SG page a LEVEL change leaves the held list alone')
    m.page(0x1E)
    m.off(16, 60)
    m.off(16, 64)
    check([h[0] for h in m.held()] == [5], 'MIDI note-offs take their keys out as before', m.held())
    m, s = fresh(), stock()
    for x in (m, s):
        x.setsym('arp_mode', 1, '<i')
        x.on(16, 60, 110)
        x.on(16, 63, 90)
        x.on(16, 67, 70)
    m_audio, s_audio = m.render(400), s.render(400)
    check(m.raw() == s.raw() and m_audio == s_audio and m.sym('arp_steps', '<I') == s.sym('arp_steps', '<I') >= 4,
          'LEVEL 127, ARP on: the arp\'s steps exactly as the parent\'s (400 blocks)',
          (m.raw() == s.raw(), m_audio == s_audio, m.sym('arp_steps', '<I')))
    m, s = fresh(), stock()
    for x in (m, s):
        x.setsym('arp_mode', 1, '<i')
    m.setparam(LEVEL, 64)
    s.setparam(LEVEL, 64)
    m.on(16, 60, 127)
    s.on(16, 60, 64)
    check(m.render(120) == s.render(120) and m.raw() == s.raw(),
          'ARP on, LEVEL 64: a key at 127 steps exactly as the parent\'s key at 64 (120 blocks)')

    # 5. Drum mode, pads ------------------------------------------------------------------------------------------
    bad = []
    for level in (127, 40, 0):
        m, s = fresh(), stock()
        for x in (m, s):
            x.setsym('kit_mode', 1)
            x.setparam(LEVEL, level)
            x.on(16, 36, 100)
            x.on(16, 40, 60)
        if m.raw() != s.raw() or m.render(8) != s.render(8):
            bad.append(level)
    check(not bad, 'drum mode: MIDI hits as the parent\'s at LEVEL 127, 40 and 0 (voices and audio)', bad or 3)
    bad = []
    for level in (127, 40):
        m, s = fresh(), stock()
        for x in (m, s):
            x.setparam(LEVEL, level)
            x.call(NOTE_ENGINE, 0, x.pad_note(2), 100, 0, stack0=2)
            x.call(NOTE_ENGINE, 0, x.pad_note(7), 45, 0, stack0=7)
        if m.raw() != s.raw() or m.render(6) != s.render(6):
            bad.append(level)
    check(not bad, 'pads: as the parent\'s at LEVEL 127 and 40 (their own velocity)', bad or 2)
    m = fresh()
    m.setparam(LEVEL, 40)
    m.call(NOTE_ENGINE, 0, m.pad_note(2), 100, 0, stack0=2)
    check([v['to'] for v in m.live()] == [10000] and m.mod('sgl_notes', '<I') == 0,
          'a pad note never goes through the MIDI gate', m.live())
    got = []
    for fixed in (0, 1):
        m, s = fresh(), stock()
        for x in (m, s):
            x.project[FIXED_VELOCITY] = fixed
            x.setparam(LEVEL, 40)
            x.on(16, 60, 100)                               # MIDI on voice 0 (here at 31, the parent at 100)
            x.idle()
            x.sg_pad(4, 110)
        got.append(([v['to'] for v in m.live()], [v['to'] for v in s.live()]))
    check(got == [([11000], [11000]), ([4000], [10000])], 'the SG page\'s pad press: FIXED VELOCITY off, its own '
          'velocity; on, LEVEL as set (the parent: the last note\'s velocity, LEVEL as it reads there)', got)

    # 6. CC 72 ----------------------------------------------------------------------------------------------------
    m = fresh()
    m.mch(1)
    m.cc(1, 72, 64)
    m.poll()
    lv = m.setting(LEVEL)
    m.idle()
    m.on(1, 60, 127)
    check(lv == 64 and [v['to'] for v in m.live()] == [6400], 'CC 72 on M.CH sets LEVEL (after the screen update) and '
          'MIDI follows it', (lv, m.live()))


if __name__ == '__main__':
    main()
