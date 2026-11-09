"""Checks for FX deep edit test 10 (build_fx_deep_edit.py): on the FX screen REMAIN + FX opens, VALUE through its
screens and the effect's extra screens, the input FX's too; an effect without extra settings is stock's; an FX
button alone as stock.

usage: python synth/test_fx_deep_edit.py OUT_DIR [FXMAP]     (unicorn, keystone, capstone on PYTHONPATH)

Reads OUT_DIR/manifest.json for the parent APP1 and DM-404's fxmap.json (or FXMAP). Static checks first: only the
header's scatter pointer, the TOP vtable slot, the DT1 builder's first ten bytes, the FX screen's VALUE toggle and
the appended tail differ from the parent, the guards hold on the parent, the
settings are exactly the parameters stock never sends, every popup line fits. Then the parent and the new image are
booted in Unicorn the way their scatter loader does it, with the boot's static constructors run (the RTOS under them
stubbed: its pool by a bump allocator, object creation by an id), the TOP page object made by its registry handler
as on page entry, and every byte to the chips' UARTs (LPUART1-8) logged. Real stock code runs: the UI task's
dispatcher (0x8003b530), TOP's registry handler, page dispatcher, key and knob handlers, the generic key handler and
its FX buttons, VALUE and REMAIN, the FX screen (constructor, show method, update, VALUE toggle), DOOM OS ED5E's page
filter, the system and settings getters and setters, the effect select, the chip reset, the DT1 builder 0x800d8118
(through the new jump) and its packet send, the popup. Modelled: the card (every file open fails), time (the FX
screen's 50 ms update is called by the test; the stock timer tick runs on TOP's 500 ms EXIT window); the FX screen's
close request 0x800bb180 is logged (the view stack's removal after it is not run). Not here: the screen (draw calls
stubbed), the effects chip itself, EXIT while the FX screen is up (stock destroys it, then waits on another task).

Checks:
- the builder, entered through the jump, sends fxmap's address for every setting on every bus, and exactly the
  parent's bytes for every parameter on every slot and for the whole boot chip reset;
- the FX screen: an FX button alone opens it as on the parent (it asks to close after 2 s; VALUE there is stock's);
  REMAIN + FX opens the screen that stays while the bus has an effect, as on the parent, and asks to close when that
  FX button turns the effect off or the bus has none;
- VALUE through the screens (REMAIN + FX): Tape Echo (screen 2, three extra screens), Isolator (one extra screen),
  Crusher (none: stock's toggle, as on the parent, no popup); the popups; nothing sent;
- on an extra screen CTRL 1-3 set its settings across their ranges, one frame per change; a knob without a setting
  does nothing; pads go on as usual; another button leaves (the popup goes) and goes on as usual; afterwards the
  knobs are stock's; every setting of every effect reaches its min and max; per bus; the input FX (slot 0) too;
- re-sending: after the firmware sends a bus's FxType (the effect select through the stock effect choice, the system
  setter, the bus swap), that bus's edited values for that effect follow it at once, and the rest of the traffic is
  the parent's byte for byte; a knob turn, another bus's FxType, the chip reset (FxType 0) and FxType for an effect
  without edits add nothing;
- with no extra screen up: four quick EXITs are STOP, every event (keys alone and in pairs, the FX buttons, VALUE,
  knobs, the encoder, pads) goes on exactly as on the parent.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_PROT_ALL, UC_HOOK_CODE
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE
from unicorn import arm_const as ar

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_fx_deep_edit import GUARDS, Runtime, scatter, decompress, branches_into, DT1, DT1_HEAD, TOGGLE, \
    TOGGLE_HEAD, EXCLUDED, SUPER_FILTER_OUT, HOOKS  # noqa: E402

FLASH, COPY, DECOMPRESS, ZERO = 0x60080000, 0x600800E4, 0x60080088, 0x60080100
HEAP = 0x32000000
KERNEL = {0x310C: 1, 0x22A4: 1, 0x32B8: 0}                 # RTOS object creation in the constructors: an id
SCREEN = (0x8006C088, 0x8006BD48, 0x8015F3A8, 0x800D8020, 0x800C1CC0)  # drawing: no display here
NOPS = (0xE668, 0x800D30A4)                              # debug prints
FILE_OPEN = 0x800DEC60                                   # (path, ...): no card here, every file is missing
CTORS, NCTORS = 0x8383A30C, 70
STACK, RET, EVENT = 0x30010000, 0x3001F000, 0x30095000
SYSPRM, BMC, SYS_SET, SYS_GET = 0x82DFEED0, 0x80592500, 0x800DE270, 0x800DA010
SETTINGS, SET_SET = 0x82E01144, 0x800DD0C0
SELECT, CHIP_RESET, SYS_INIT = 0x800D0CF0, 0x801803B0, 0x8006C3C0
UI_DISPATCH, PAGE_ID, PAGE_LIVE, PREFILTER, KEY_PAIRS = 0x8003B530, 0x80245880, 0x8024587A, 0x82DFD318, 0x80B119DC
TOP_REGISTRY, TOP_PAGE, DOOM_FILTER, VTABLE_SLOT = 0x8005EDA8, 0x80CFD350, 0x6031C8F8, 0x8022CE64
POPUP, KEYS = 0x800D3FF0, 0x80592448
FALLBACKS = (0x8003C758, 0x8003C798)                     # the dispatcher's own handling of a key no page took
TIMER_TICK, EXIT_WINDOW = 0x80100728, 0x82DFD2FC          # stock timer tick (timer, ms); TOP's EXIT-press window
DEFAULTS, MINIMA, MAXIMA, RECORDS, NAMES = 0x801ABE64, 0x801AD1FC, 0x801AC830, 0x802E5B40, 0x80245EE4
FXTYPE_SENT = 0x80246F38
EV_KEY, EV_KEY_UP, EV_ENCODER, EV_KNOB, EV_PAD, EV_PAD_UP = 5, 6, 7, 9, 0x10, 0x11
KEY_EXIT, KEY_VALUE, KEY_SHIFT = 0x22, 0x31, 0x2A
HEADER = bytes([0xF0, 0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x08, 0x12])
PAGE_MS, GONE_MS = 10000, 1
TAPE_ECHO, REVERB, CRUSHER, EQUALIZER = 9, 10, 4, 19
fails = []
cases = [0]


def check(cond, what):
    cases[0] += 1
    print(('PASS ' if cond else 'FAIL ') + what)
    if not cond:
        fails.append(what)
    return cond


def sha(b):
    return hashlib.sha256(b).hexdigest()


def s32(v):
    return struct.unpack('<i', struct.pack('<I', v & 0xFFFFFFFF))[0]


def frame(addr, value):
    body = bytes(addr) + bytes([value >> 4 & 15, value & 15])
    return HEADER + body + bytes([-sum(body) & 0x7F, 0xF7])


def fx_frame(fx, slot, aa, value):
    block = (fx - 1) * 5 + slot
    return frame((3, block >> 7, block & 0x7F, aa), value)


def fxtype_frame(slot, fx):
    return frame((2, 2, 0, 8 + 2 * slot), fx)


class Machine:
    def __init__(self, img, symbols=None):
        self.sym = symbols or {}
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for base, size in ((0x0, 0x20000), (0x20000000, 0x80000), (0x20200000, 0x100000), (0x80000000, 0x4000000),
                           (0x30000000, 0x100000), (0x60000000, 0x400000), (0x400E8000, 0x2000),
                           (0xE0000000, 0x100000), (0x40000000, 0xE8000), (0x400EA000, 0x316000),
                           (HEAP, 0x1000000)):
            uc.mem_map(base, size, UC_PROT_ALL)
        uc.mem_write(FLASH, img)
        for load, dst, size, handler in scatter(img):
            if handler == COPY:
                uc.mem_write(dst, img[load - FLASH:load - FLASH + size])
            elif handler == DECOMPRESS:
                uc.mem_write(dst, decompress(img[load - FLASH:], size))
            elif handler == ZERO:
                uc.mem_write(dst, bytes(size))
        uc.reg_write(ar.UC_ARM_REG_C1_C0_2, uc.reg_read(ar.UC_ARM_REG_C1_C0_2) | (0xF << 20))
        uc.reg_write(ar.UC_ARM_REG_FPEXC, 0x40000000)
        uc.mem_write(RET, b'\x00\xbf\x00\xbf')
        self.mprofile()
        self.heap = HEAP
        self.uart, self.popups, self.doom, self.fallback, self.opened = [], [], [], [], []
        uc.hook_add(UC_HOOK_CODE, self._malloc, None, begin=0x800E2C68, end=0x800E2C68)
        uc.hook_add(UC_HOOK_CODE, self._value, 0, begin=0x800E2CA8, end=0x800E2CA8)
        for a, v in KERNEL.items():
            uc.hook_add(UC_HOOK_CODE, self._value, v, begin=a, end=a)
        for a in SCREEN + NOPS:
            uc.hook_add(UC_HOOK_CODE, self._value, 0, begin=a, end=a)
        uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self._uart, None, begin=0x40184000, end=0x401A3FFF)
        uc.hook_add(UC_HOOK_CODE, self._popup, None, begin=POPUP, end=POPUP)
        uc.hook_add(UC_HOOK_CODE, self._doom, None, begin=DOOM_FILTER, end=DOOM_FILTER)
        uc.hook_add(UC_HOOK_CODE, self._open, None, begin=FILE_OPEN, end=FILE_OPEN)
        for a in FALLBACKS:
            uc.hook_add(UC_HOOK_CODE, self._fallback, None, begin=a, end=a)
        for fn in struct.unpack(f'<{NCTORS}I', bytes(uc.mem_read(CTORS, 4 * NCTORS))):
            self.call(fn & ~1 | 1, count=50_000_000)
        self.w32(PREFILTER, 0xFFFFFFFF)                 # no mode holds the keys
        uc.mem_write(KEY_PAIRS, b'\xff' * 0x80)         # no key pairs (memset -1 at boot)
        uc.mem_write(EVENT, struct.pack('<6h', 1, 0, 0, 0, 0, 0))
        self.call(TOP_REGISTRY, EVENT, count=20_000_000)  # the TOP page object, as on page entry
        self.page = self.r32(TOP_PAGE)
        uc.mem_write(PAGE_ID, struct.pack('<H', 1))
        uc.mem_write(PAGE_LIVE, struct.pack('<H', 1))
        self.clear()

    def mprofile(self):
        """M-profile special registers (the RTOS's critical sections): MSR -> nop.w, MRS -> mov.w rd, #0."""
        for base, size in ((0x400, 0x1F800), (0x80000000, 0x240000)):
            code = bytearray(self.uc.mem_read(base, size))
            for i in range(0, size - 4, 2):
                h1, h2 = code[i] | code[i + 1] << 8, code[i + 2] | code[i + 3] << 8
                if (h1 & 0xFFF0) == 0xF380 and (h2 & 0xFF00) == 0x8800 and 0x10 <= (h2 & 0xFF) <= 0x14:
                    code[i:i + 4] = bytes.fromhex('aff30080')
                elif h1 == 0xF3EF and (h2 & 0xF000) == 0x8000 and 0x10 <= (h2 & 0xFF) <= 0x14:
                    code[i:i + 4] = bytes([0x4F, 0xF0, 0x00, (h2 >> 8) & 15])
            self.uc.mem_write(base, bytes(code))

    def _ret(self, value=0):
        self.uc.reg_write(ar.UC_ARM_REG_R0, value & 0xFFFFFFFF)
        self.uc.reg_write(ar.UC_ARM_REG_PC, self.uc.reg_read(ar.UC_ARM_REG_LR))

    def _malloc(self, uc, a, size, _):
        n = (uc.reg_read(ar.UC_ARM_REG_R0) + 15) & ~7
        at = self.heap
        self.heap += n + 8
        uc.mem_write(at, bytes(n + 8))
        self._ret(at + 8)

    def _value(self, uc, a, size, value):
        self._ret(value)

    def _uart(self, uc, access, address, size, value, _):
        base, off = address & ~0x3FFF, address & 0x3FFF
        if access == UC_MEM_WRITE and off == 0x1C:
            self.uart.append(((base - 0x40184000) // 0x4000 + 1, value & 0xFF))
        elif off == 0x14:
            uc.mem_write(address, struct.pack('<I', 0x00C00000))    # transmit ready

    def _popup(self, uc, a, size, _):
        text = bytes(uc.mem_read(uc.reg_read(ar.UC_ARM_REG_R0), 64)).split(b'\0')[0].decode('latin-1')
        self.popups.append((text, uc.reg_read(ar.UC_ARM_REG_R1)))

    def _doom(self, uc, a, size, _):
        ev = uc.reg_read(ar.UC_ARM_REG_R1)
        self.doom.append((uc.reg_read(ar.UC_ARM_REG_R0), struct.unpack('<3h', bytes(uc.mem_read(ev, 6)))))

    def _open(self, uc, a, size, _):
        self.opened.append(bytes(uc.mem_read(uc.reg_read(ar.UC_ARM_REG_R0), 96)).split(b'\0')[0].decode('latin-1'))
        self._ret(-1)

    def _fallback(self, uc, a, size, _):
        self.fallback.append(struct.unpack('<2h', bytes(uc.mem_read(uc.reg_read(ar.UC_ARM_REG_R0), 4))))

    def clear(self):
        self.uart, self.popups, self.doom, self.fallback, self.opened = [], [], [], [], []

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack('<I', v & 0xFFFFFFFF))

    def r32(self, a):
        return struct.unpack('<I', self.uc.mem_read(a, 4))[0]

    def r16(self, a):
        return struct.unpack('<H', self.uc.mem_read(a, 2))[0]

    def call(self, fn, *args, count=5_000_000):
        uc = self.uc
        for k, v in enumerate(args):
            uc.reg_write(getattr(ar, f'UC_ARM_REG_R{k}'), v & 0xFFFFFFFF)
        uc.reg_write(ar.UC_ARM_REG_LR, RET | 1)
        uc.reg_write(ar.UC_ARM_REG_SP, STACK)
        uc.emu_start(fn | 1, RET, count=count)
        if uc.reg_read(ar.UC_ARM_REG_PC) != RET:
            raise RuntimeError(f'{fn:#x} did not return (pc {uc.reg_read(ar.UC_ARM_REG_PC):#x})')
        return uc.reg_read(ar.UC_ARM_REG_R0)

    def dispatch(self, kind, a1=0, a2=0):
        """An event through the UI task's own dispatcher (keys set and clear their held bits there)."""
        self.uc.mem_write(EVENT, struct.pack('<6h', kind, a1, a2, 0, 0, 0))
        return s32(self.call(UI_DISPATCH, EVENT, count=20_000_000))

    def pause(self, ms):
        """Time passing for TOP's EXIT handler (0x801349f8): four EXIT presses less than 500 ms apart are stock's
        STOP. The UI tick 0x8003c5f0 ages that window's timer 0x82dfd2fc through 0x80100728 once boot has set its
        ready flags, which the constructors don't; this runs that timer tick itself."""
        self.call(TIMER_TICK, EXIT_WINDOW, ms)

    def chord(self):
        """Hold EXIT, press and release VALUE, let go of EXIT; then the user's pace."""
        for kind, key in ((EV_KEY, KEY_EXIT), (EV_KEY, KEY_VALUE), (EV_KEY_UP, KEY_VALUE), (EV_KEY_UP, KEY_EXIT)):
            self.dispatch(kind, key)
        self.pause(600)

    def press(self, key=KEY_VALUE):
        self.dispatch(EV_KEY, key)
        self.dispatch(EV_KEY_UP, key)
        self.pause(600)

    def turn(self, n):
        self.dispatch(EV_ENCODER, 0, n)

    def packets(self, port=3):
        b = [v for p, v in self.uart if p == port]
        return [bytes(b[i:i + 4]) for i in range(0, len(b), 4)], len(b) % 4

    def frames(self):
        """The chip link's DT1 frames (04 x x x five times then 06 sum F7 and a filler byte), the other packets
        (e.g. MIDI out on cable 9), and whether the SysEx packets all formed such frames and nothing went to
        another UART."""
        pk, rest = self.packets()
        frames, other, cur = [], [], []
        ok = rest == 0 and not [p for p, v in self.uart if p != 3]
        for p in pk:
            cable, cin = p[0] >> 4, p[0] & 0xF
            if cable or cin not in (4, 5, 6, 7):
                other.append(p)
            elif cin == 4 and len(cur) < 5:
                cur.append(p)
            elif cin == 6 and len(cur) == 5:
                frames.append(b''.join(q[1:] for q in cur) + p[1:3])
                cur = []
            else:
                ok = False
        return frames, other, ok and not cur

    def set_bus(self, bus, fx, knobs=True):
        """The effect on a bus the way the stock MFX choice sets it (0x8006ccd6: 0x27b, 0x27c, the effect select,
        0x276 = 6), and the CTRL knobs on that bus (settings 0x3a)."""
        self.call(SYS_SET, SYSPRM, 0x27B, fx, bus)
        self.call(SYS_SET, SYSPRM, 0x27C, fx, bus)
        self.call(SELECT, SYSPRM, bus)
        self.call(SYS_SET, SYSPRM, 0x276, 6, bus)
        if knobs:
            self.call(SET_SET, SETTINGS, 0x3A, bus, 0)

    def knob_bus(self, bus):
        self.call(SET_SET, SETTINGS, 0x3A, bus, 0)

    def bus_effect(self, bus, fx):
        """0x27c[bus] written straight into the system object: the page's view, no frame sent."""
        self.uc.mem_write(SYSPRM + 0xC4 + 2 * bus, struct.pack('<h', fx))

    def state(self):
        b = bytes(self.uc.mem_read(self.sym['fde'], 48))
        return dict(screen=b[0], input=b[1], ext_held=b[2], value_down=b[3], bus=b[4], effect=b[5], off=b[6],
                    value_taken=b[7], sent=struct.unpack_from('<I', b, 8)[0],
                    resent=struct.unpack_from('<I', b, 12)[0], loaded=b[16], dirty=b[17], redraw=b[18],
                    loads=struct.unpack_from('<I', b, 20)[0], bad_files=struct.unpack_from('<I', b, 24)[0],
                    saves=struct.unpack_from('<I', b, 28)[0], save_errors=struct.unpack_from('<I', b, 32)[0],
                    redraw_at=struct.unpack_from('<I', b, 36)[0], redraws=struct.unpack_from('<I', b, 40)[0],
                    repairs=struct.unpack_from('<I', b, 44)[0])


class Settings:
    """The settings as the test derives them, from the parent image and fxmap alone."""

    def __init__(self, rt, fxmap):
        self.names = [rt.cstr(p & 0xFFFFFFFF) for p in rt.words(NAMES, 627)]
        self.default, self.max, self.min = (rt.words(a, 627) for a in (DEFAULTS, MAXIMA, MINIMA))
        self.effect_names = [rt.cstr(p & 0xFFFFFFFF).upper() for p in rt.words(0x8020B3D8, 49)]
        self.by_fx = {}
        for e in fxmap.values():
            record = rt.words(RECORDS + 24 * e['id'], 6)
            first = [x for x in record if x >= 0][0]
            base = [first - p['addr'] // 2 for p in e['params'] if self.names[first] == p['name']]
            base = [b for b in base if self.names[b:b + len(e['params'])] == [p['name'] for p in e['params']]]
            assert len(base) == 1, e['name']
            self.by_fx[e['id']] = [dict(id=base[0] + i, name=p['name'], aa=p['addr'], min=self.min[base[0] + i],
                                        max=self.max[base[0] + i], default=self.default[base[0] + i])
                                   for i, p in enumerate(e['params'])
                                   if p['default'] is None and base[0] + i not in record and
                                   (e['id'], p['name']) not in EXCLUDED]

    def text(self, bus, fx, cursor=0, value=None, edit=False):
        s = self.by_fx[fx][cursor]
        v = s['default'] if value is None else value
        return f'BUS{bus} {self.effect_names[fx]}\n{s["name"]} ' + (f'[{v}]' if edit else f'{v}')


def static_checks(out, man, img, parent, fxmap, st):
    check(sha(img) == man['sha256'] and len(img) == man['size'], 'APP1 matches its manifest')
    check(sha((out / 'SP404MKII_APP0.bin').read_bytes()) == man['app0_sha256'] ==
          '3e35ff30137f741a715566e205384f9b434ca7ac3847e247bad3f0c9c8a2bd23', 'APP0 is stock 5.52')
    sums = (out / 'SHA256SUMS.txt').read_text(encoding='utf-8').split()
    check(dict(zip(sums[1::2], sums[0::2])) == {n: sha((out / n).read_bytes()) for n in (
        'SP404MKII_APP0.bin', 'SP404MKII_APP1.bin', 'manifest.json')}, 'SHA256SUMS.txt matches the files')
    rows, prow = scatter(img), scatter(parent)
    blob_row = [FLASH + man['blob_file_offset'], man['blob_base'], man['blob_size'], COPY]
    check(rows == prow + [blob_row], 'scatter table: the parent\'s rows plus one copy row for the module')

    def file_off(addr):
        return [load - FLASH + addr - dst for load, dst, n, fn in prow if fn == COPY and load and dst <= addr < dst + n][0]
    vt, dt, tg, fu = file_off(VTABLE_SLOT), file_off(DT1), file_off(TOGGLE), file_off(0x802269E8)
    diff = [i for i in range(len(parent)) if img[i] != parent[i]]
    allowed = set(range(0x80, 0x88)) | set(range(vt, vt + 4)) | set(range(dt, dt + 10)) | set(range(tg, tg + 10)) | \
        set(range(fu, fu + 4))
    for site, head, *_ in HOOKS:
        allowed |= set(range(file_off(site), file_off(site) + len(head)))
    check(set(diff) <= allowed and img[:len(parent)] != parent,
          f'only the scatter pointer, the TOP vtable slot, the DT1 builder\'s first ten bytes, the FX screen\'s VALUE '
          f'toggle, (test10) the UI dispatcher\'s key press, key release and knob handlers\' first bytes and (test13) the '
          f'FX screen\'s update slot change inside the parent; the FX screen\'s show method (REMAIN held?) is stock '
          f'({len(diff)} bytes)')
    e0 = man['entries']
    good = []
    for site, head, resume, bridge, fn, what in HOOKS:
        lo, hi = e0[bridge] & 0xFFFF, e0[bridge] >> 16
        jump = struct.pack('<5H', 0xF240 | (lo >> 12) | ((lo >> 11) & 1) << 10, ((lo >> 8) & 7) << 12 | 12 << 8 | lo & 0xFF,
                           0xF2C0 | (hi >> 12) | ((hi >> 11) & 1) << 10, ((hi >> 8) & 7) << 12 | 12 << 8 | hi & 0xFF,
                           0x4760) + bytes.fromhex('00bf') * ((len(head) - 10) // 2)
        o = file_off(site)
        good.append(parent[o:o + len(head)] == head and img[o:o + len(head)] == jump and
                    not branches_into(Runtime(parent), site + 1, site + len(head)))
    check(all(good), 'test10: the dispatcher\'s key press, key release and knob handlers start with their stock '
                     'instructions on the parent and a jump to fde_down_bridge / fde_up_bridge / fde_knob_bridge here; '
                     'nothing branches into them')
    e = man['entries']
    check(parent[vt:vt + 4] == struct.pack('<I', DOOM_FILTER | 1) and img[vt:vt + 4] == struct.pack('<I', e['fde_filter']),
          'TOP vtable +8: DOOM OS\'s filter on the parent, fde_filter here')
    lo, hi = e['fde_dt1'] & 0xFFFF, e['fde_dt1'] >> 16
    want = struct.pack('<4HH', 0xF240 | (lo >> 12) | ((lo >> 11) & 1) << 10, ((lo >> 8) & 7) << 12 | 12 << 8 | lo & 0xFF,
                       0xF2C0 | (hi >> 12) | ((hi >> 11) & 1) << 10, ((hi >> 8) & 7) << 12 | 12 << 8 | hi & 0xFF, 0x4760)
    check(parent[dt:dt + 10] == DT1_HEAD and img[dt:dt + 10] == want,
          'DT1 builder entry: push.w / sub sp / movw sb on the parent, movw ip / movt ip / bx ip to fde_dt1 here')
    lo, hi = e['fde_value'] & 0xFFFF, e['fde_value'] >> 16
    want = struct.pack('<4HH', 0xF240 | (lo >> 12) | ((lo >> 11) & 1) << 10, ((lo >> 8) & 7) << 12 | 12 << 8 | lo & 0xFF,
                       0xF2C0 | (hi >> 12) | ((hi >> 11) & 1) << 10, ((hi >> 8) & 7) << 12 | 12 << 8 | hi & 0xFF, 0x4760)
    check(parent[tg:tg + 10] == TOGGLE_HEAD and img[tg:tg + 10] == want,
          'the FX screen\'s VALUE toggle: movw / ldrb / cmp / it on the parent, movw ip / movt ip / bx ip to fde_value '
          'here')
    rt, nrt = Runtime(parent), Runtime(img)
    check(not branches_into(rt, TOGGLE + 1, TOGGLE + 10), 'nothing branches into the toggle\'s first ten bytes')
    check(all(sha(rt.read(s, e2 - s)) == d for s, e2, d, w in GUARDS), f'{len(GUARDS)} guards hold on the parent')
    check(not branches_into(rt, DT1 + 1, DT1 + 10), 'nothing branches into the builder\'s first ten bytes')
    stock = nrt.read(e['fde_dt1_stock'] & ~1, 20)
    check(stock[:10] == DT1_HEAD and stock[10:] == struct.pack('<5H', 0xF248, 0x1C23, 0xF2C8, 0x0C0D, 0x4760),
          'fde_dt1_stock: the builder\'s first ten bytes, then movw ip / movt ip / bx ip to 0x800d8123')
    check(nrt.read(man['blob_base'], man['blob_size']) ==
          img[man['blob_file_offset']:man['blob_file_offset'] + man['blob_size']] and
          man['blob_base'] + man['blob_size'] <= man['slot'][1] <= 0x83FE6000, 'the module fits its slot')
    # the settings: compiled tables == the test's own derivation == the manifest
    n = man['settings_total']
    first = list(nrt.read(e['fde_first'], 49))
    count = list(nrt.read(e['fde_count'], 49))
    ids = list(struct.unpack(f'<{n}H', nrt.read(e['fde_ids'], 2 * n)))
    names = [nrt.read(e['fde_names'] + 10 * i, 10).split(b'\0')[0].decode() for i in range(n)]
    labels = [nrt.read(e['fde_effect_names'] + 13 * i, 13).split(b'\0')[0].decode() for i in range(49)]
    mine = [(p['id'], p['name']) for fx in range(1, 49) for p in st.by_fx[fx]]
    check(n == 135 and list(zip(ids, names)) == mine and
          all(count[fx] == len(st.by_fx[fx]) and first[fx] == sum(len(st.by_fx[k]) for k in range(1, fx))
              for fx in range(1, 49)) and count[0] == 0 and labels[1:] == st.effect_names[1:],
          f'the compiled settings are the {len(mine)} parameters with no boot value in fxmap and not in the knob '
          f'records, in fxmap order, with the firmware\'s names')
    check([(p['id'], p['name'], p['min'], p['max'], p['default']) for x in man['effects'] for p in x['settings']] ==
          [(p['id'], p['name'], p['min'], p['max'], p['default']) for fx in range(1, 49) for p in st.by_fx[fx]],
          'the manifest lists the same settings with the firmware\'s ranges and defaults')
    check(all(0 <= p['min'] <= p['default'] <= p['max'] <= 255 for fx in st.by_fx for p in st.by_fx[fx]),
          'every setting\'s range is inside 0..255 and holds its default')
    comp = [p['name'] for p in st.by_fx[28]]
    check(set(EXCLUDED) == {(28, 'MODE')} | {(34, x) for x in SUPER_FILTER_OUT} and count[28] == 0 and comp == [] and
          'MODE' not in names[first[28]:first[28] + count[28]],
          'test6: COMPRESSOR\'s MODE is left out (a user\'s report: dangerously loud); the Compressor has no extra '
          'settings now')
    check(count[34] == 0 and st.by_fx[34] == [] and labels[34] == 'SUPER FILTER' and
          not any(x in names for x in ('FLT SLOPE', 'FLT GAIN', 'MOD WAVE')),
          'test8: the SUPER FILTER\'s six extra settings (FLT SLOPE, FLT GAIN, MOD SW, MOD WAVE, ATTACK, LEVEL) are '
          'left out (a user\'s report: CTRL 2 spiked the volume); it has no extra settings now')
    lines = [f'{labels[fx]} {n}/{n}' for fx in range(1, 49)
             for n in [2 + any(x != -1 for x in rt.words(RECORDS + 24 * fx + 12, 3)) + (len(st.by_fx[fx]) + 2) // 3]] + \
            [f'C3 {p["name"]} {p["max"]}' for fx in st.by_fx for p in st.by_fx[fx]]
    check(all(len(x) <= 17 and x.isascii() for x in lines), 'every popup line is plain and at most 17 characters')


def builder_checks(img, parent, man, fxmap, st):
    """The builder through the jump: the parent's bytes for every parameter ID and slot and for the whole boot
    chip reset (fresh machines, the same history: even the stock packet buffer's leftover byte matches), and
    fxmap's addresses for every setting on every bus."""
    m, p = Machine(img, man['entries']), Machine(parent)
    bad, n = [], 0
    for pid in range(0, 627):
        for slot in ((0,) if pid < 0xA3 else range(5)):
            out = []
            for mm in (p, m):
                mm.clear()
                r = mm.call(DT1, BMC, pid, slot, 0x37)
                out.append((bytes(v for q, v in mm.uart), r))
            n += bool(out[0][0])
            if out[0] != out[1]:
                bad.append((pid, slot))
    check(not bad and n >= 104 + 464 * 5, f'through the jump, every parameter ID on every slot sends the parent\'s '
                                          f'bytes ({n} that send; {bad[:4]})')
    m, p = Machine(img, man['entries']), Machine(parent)
    out = []
    for mm in (p, m):
        mm.call(CHIP_RESET, 0x80591794, count=50_000_000)
        out.append(bytes(v for q, v in mm.uart))
    check(out[0] == out[1] and len(out[0]) > 15000, f'the boot chip reset sends the parent\'s {len(out[0])} bytes')
    bad, n = [], 0
    for fx in range(1, 49):
        for s in st.by_fx[fx]:
            for bus in range(5):
                m.clear()
                m.call(DT1, BMC, s['id'], bus, 0x5A)
                got, other, ok = m.frames()
                n += 1
                if not ok or other or got != [fx_frame(fx, bus, s['aa'], 0x5A)] or \
                        [x['addr'] for x in fxmap[fx]['params'] if x['name'] == s['name'] and x['default'] is None] != [s['aa']]:
                    bad.append((fx, s['name'], bus))
    check(not bad and n == 675, f'through the jump, the builder sends fxmap\'s address for all {n} setting/slot pairs '
                                f'({bad[:4]})')


FXVIEW_VT, VIEW_REMAIN, VIEW_SCREEN2, CLOSE_REQ = 0x802269C0, 0x1B3F, 0x1B40, 0x800BB180
VIEW_UPDATE, REMAIN_GLOBAL, KEY_REMAIN, KEY_FX1, KEY_HOLD = 0x80146599, 0x80592320, 0x24, 0x2B, 0x11
ISOLATOR = 3
SCREEN_MS = 600000


def has_screen2(rt, fx):
    return fx and any(x != -1 for x in rt.words(RECORDS + 24 * fx + 12, 3))


def screen_text(rt, st, bus, fx, screen, values=None):
    """An extra screen's popup, worked out from the parent's tables and fxmap."""
    s = st.by_fx[fx]
    two = has_screen2(rt, fx)
    n = (len(s) + 2) // 3
    lines = [f'{st.effect_names[fx]} {1 + two + screen}/{1 + two + n}']
    for k, x in enumerate(s[(screen - 1) * 3:screen * 3]):
        v = (values or {}).get(x['name'], x['default'])
        lines.append(f'C{k + 1} {x["name"]} {v}')
    return '\n'.join(lines)


def knob_value(s, raw):
    return s['min'] + ((s['max'] - s['min']) * raw + 63) // 127


class Screen:
    """The FX screen (vtable 0x802269c0) on TOP's view stack, its close requests (0x800bb180) logged."""

    def __init__(self, m):
        self.m = m
        m.closes = []
        m.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: m.closes.append(uc.reg_read(ar.UC_ARM_REG_R0)), None,
                      begin=CLOSE_REQ, end=CLOSE_REQ)

    def view(self):
        m = self.m
        for o in range(0x3DC, 0x3F0, 4):
            x = m.r32(m.page + o)
            if 0x30000000 <= x < 0x34000000 and m.r32(x) == FXVIEW_VT:
                return x
        return None

    def flag(self, off):
        return self.m.uc.mem_read(self.view() + off, 1)[0]

    def open(self, key=KEY_FX1, remain=True):
        m = self.m
        if remain:
            m.dispatch(EV_KEY, KEY_REMAIN)
        m.dispatch(EV_KEY, key)
        m.dispatch(EV_KEY_UP, key)
        if remain:
            m.dispatch(EV_KEY_UP, KEY_REMAIN)
        return self.view()

    def run(self, ms):
        """The screen's update every 50 ms (the view base's tick 0x80073b58 calls it so)."""
        v = self.view()
        for _ in range(ms // 50):
            self.m.call(VIEW_UPDATE, v, count=20_000_000)
        return [x for x in self.m.closes if x == v]

    def value(self):
        self.m.dispatch(EV_KEY, KEY_VALUE)
        self.m.dispatch(EV_KEY_UP, KEY_VALUE)


def fx_machine(image, man, bus=1, fx=TAPE_ECHO):
    m = Machine(image, man['entries'] if man else None)
    m.set_bus(bus, fx)
    sc = Screen(m)
    return m, sc


def screen_checks(img, parent, man, st):
    rt = Runtime(parent)
    m, sc = fx_machine(img, man)
    p, sp = fx_machine(parent, None)
    for mm, ss in ((m, sc), (p, sp)):
        ss.open(remain=False)
        mm.bus_effect(1, TAPE_ECHO)
    check(sc.flag(VIEW_REMAIN) == sp.flag(VIEW_REMAIN) == 0 and
          m.uc.mem_read(REMAIN_GLOBAL, 1)[0] == p.uc.mem_read(REMAIN_GLOBAL, 1)[0],
          'an FX button alone opens the FX screen as on the parent (+0x1b3f clear: test 2\'s hold is gone)')
    check(sp.run(2500), 'on the parent it asks to close after 2 s')
    seq = []
    for k in range(3):
        m.clear()
        sc.value()
        seq.append((sc.flag(VIEW_REMAIN), sc.flag(VIEW_SCREEN2), m.state()['screen'], m.popups))
    held = m.uc.mem_read(REMAIN_GLOBAL, 1)[0]
    check(seq == [(1, 1, 0, []), (1, 1, 1, [(screen_text(rt, st, 1, TAPE_ECHO, 1), SCREEN_MS)]),
                  (1, 1, 2, [(screen_text(rt, st, 1, TAPE_ECHO, 2), SCREEN_MS)])] and held == 1 and not sc.run(5000),
          f'test5: there a VALUE press holds the screen as REMAIN + FX does (+0x1b3f and 0x80592320 set) and steps on: '
          f'screen 2, then the extra screens; it stays (5 s, no close request) ({seq})')
    out = []
    for image, man_ in ((parent, None), (img, man)):
        mm, ss = fx_machine(image, man_, fx=CRUSHER)
        ss.open(remain=False)
        mm.bus_effect(1, CRUSHER)
        mm.clear()
        ss.value()
        out.append((ss.flag(VIEW_REMAIN), ss.flag(VIEW_SCREEN2), mm.popups, bool(ss.run(2500))))
    check(out[0] == out[1] == (0, 0, [], True),
          f'an effect with neither screen 2 nor extra settings (Crusher), opened without REMAIN: VALUE is stock\'s, '
          f'and the screen closes after 2 s, as on the parent ({out})')
    m, sc = fx_machine(img, man)
    p, sp = fx_machine(parent, None)
    for mm, ss in ((m, sc), (p, sp)):
        ss.open()
        mm.bus_effect(1, TAPE_ECHO)
    check(sc.flag(VIEW_REMAIN) == sp.flag(VIEW_REMAIN) == 1 and not sc.run(5000) and not sp.run(5000),
          'REMAIN + FX: the screen that stays (5 s of its 50 ms updates, no close request) while the bus has an '
          'effect, as on the parent')
    again = []
    for mm, ss in ((m, sc), (p, sp)):
        mm.dispatch(EV_KEY, KEY_FX1)
        mm.dispatch(EV_KEY_UP, KEY_FX1)
        again.append((mm.call(SYS_GET, SYSPRM, 0x276, 1), bool(ss.run(50))))
    check(again[0] == again[1],
          f'the same FX button again: the effect and the screen as on the parent ({again})')
    m, sc = fx_machine(img, man)
    sc.open()
    m.bus_effect(1, 0)
    check(sc.run(50), 'no effect on the bus: the screen asks to close, as stock\'s REMAIN screen does')

    # VALUE: screen 1, 2, the extra screens, screen 1
    m, sc = fx_machine(img, man)
    sc.open()
    m.bus_effect(1, TAPE_ECHO)
    te = st.by_fx[TAPE_ECHO]
    seq = []
    for k in range(5):
        m.clear()
        sc.value()
        seq.append((sc.flag(VIEW_SCREEN2), m.state()['screen'], m.popups, not m.uart))
    want = [(1, 0, [], True)] + \
        [(1, k, [(screen_text(rt, st, 1, TAPE_ECHO, k), SCREEN_MS)], True) for k in (1, 2, 3)] + \
        [(0, 0, [(screen_text(rt, st, 1, TAPE_ECHO, 3), GONE_MS)], True)]
    check(len(te) == 7 and seq == want,
          f'Tape Echo (CTRL 4-6, 7 extra settings): VALUE goes to screen 2, then the extra screens 3/5, 4/5, 5/5 in '
          f'the popup ("{screen_text(rt, st, 1, TAPE_ECHO, 1)}"), then screen 1 again (the popup gone); nothing '
          f'sent ({seq[1][2]})')
    m, sc = fx_machine(img, man, fx=ISOLATOR)
    sc.open()
    m.bus_effect(1, ISOLATOR)
    seq = []
    for k in range(3):
        m.clear()
        sc.value()
        seq.append((sc.flag(VIEW_SCREEN2), m.state()['screen'], m.popups))
    check(not has_screen2(rt, ISOLATOR) and seq == [(0, 1, [(screen_text(rt, st, 1, ISOLATOR, 1), SCREEN_MS)]),
                                                    (0, 0, [(screen_text(rt, st, 1, ISOLATOR, 1), GONE_MS)]),
                                                    (0, 1, [(screen_text(rt, st, 1, ISOLATOR, 1), SCREEN_MS)])],
          f'Isolator (no screen 2, one extra setting): VALUE goes to "{screen_text(rt, st, 1, ISOLATOR, 1)}" and back')
    out = []
    for image, man_ in ((parent, None), (img, man)):
        mm, ss = fx_machine(image, man_, fx=CRUSHER)
        ss.open()
        mm.bus_effect(1, CRUSHER)
        flags = []
        for k in range(3):
            mm.clear()
            ss.value()
            flags.append((ss.flag(VIEW_SCREEN2), mm.popups))
        out.append(flags)
    check(out[0] == out[1] == [(1, []), (0, []), (1, [])],
          f'Crusher (no screen 2, no extra settings): VALUE toggles stock\'s screen flag, as on the parent with REMAIN, '
          f'and shows no popup (test7) ({out[1]})')

    # the knobs on an extra screen
    m, sc = fx_machine(img, man)
    sc.open()
    m.bus_effect(1, TAPE_ECHO)
    sc.value()
    sc.value()                                          # the first extra screen: SYNC, BASS, TREBLE
    vals, seq = {}, []
    for k, raw in ((1, 127), (1, 0), (2, 64), (3, 127), (2, 41)):
        s = te[k - 1]
        v = knob_value(s, raw)
        old = vals.get(s['name'], s['default'])
        m.clear()
        m.dispatch(EV_KNOB, k, raw)
        vals[s['name']] = v
        got, other, ok = m.frames()
        seq.append(ok and not other and got == ([fx_frame(TAPE_ECHO, 1, s['aa'], v)] if v != old else []) and
                   m.popups == [(screen_text(rt, st, 1, TAPE_ECHO, 1, vals), SCREEN_MS)] and not m.doom)
    check(all(seq), f'on it CTRL 1-3 set SYNC, BASS and TREBLE across their ranges: one frame for each change (03 00 '
                    f'29 aa, the value), none when the value stays, the popup follows; stock\'s knob path not '
                    f'reached ({seq})')
    sc.value()
    sc.value()                                          # the third extra screen: TAPE DIST alone
    dist = te[6]
    m.clear()
    m.dispatch(EV_KNOB, 2, 99)
    m.dispatch(EV_KNOB, 3, 5)
    none = not m.uart and not m.doom
    m.clear()
    m.dispatch(EV_KNOB, 1, 16)
    got, other, ok = m.frames()
    v = knob_value(dist, 16)
    check(none and ok and got == [fx_frame(TAPE_ECHO, 1, dist['aa'], v)] and
          m.popups == [(screen_text(rt, st, 1, TAPE_ECHO, 3, {**vals, 'TAPE DIST': v}), SCREEN_MS)],
          f'5/5 has TAPE DIST on CTRL 1 alone: CTRL 2 and 3 do nothing there; CTRL 1 at 16 sends {v}')
    # leaving with another button; pads on it
    m.clear()
    r = [m.dispatch(EV_PAD, 3, 100), m.dispatch(EV_PAD_UP, 3, 0)]
    pads = (m.state()['screen'] == 3, [x[1][:2] for x in m.doom])
    m.clear()
    m.dispatch(EV_KEY, KEY_HOLD)
    m.dispatch(EV_KEY_UP, KEY_HOLD)
    check(pads == (True, [(EV_PAD, 3), (EV_PAD_UP, 3)]) and m.state()['screen'] == 0 and
          m.popups[0][1] == GONE_MS and [x[1][:2] for x in m.doom] == [(EV_KEY, KEY_HOLD), (EV_KEY_UP, KEY_HOLD)],
          'pads on an extra screen go on as usual and it stays; another button leaves it (the popup goes) and goes on '
          'to DOOM OS as usual')
    m.clear()
    m.dispatch(EV_KNOB, 1, 100)
    got, other, ok = m.frames()
    check(ok and got and fx_frame(TAPE_ECHO, 1, te[0]['aa'], knob_value(te[0], 100)) not in got,
          'after leaving, CTRL 1 is stock\'s again (it sends the effect\'s own CTRL 1 parameter)')
    # per bus
    for bus in (2, 3, 4):
        m, sc = fx_machine(img, man, bus=bus, fx=REVERB)
        sc.open()
        m.bus_effect(bus, REVERB)
        sc.value()
        sc.value()                                      # Reverb has CTRL 4-6: screen 2, then DENSITY
        rv = st.by_fx[REVERB][0]
        m.clear()
        m.dispatch(EV_KNOB, 1, 0)
        got, other, ok = m.frames()
        check(ok and got == [fx_frame(REVERB, bus, rv['aa'], rv['min'])] and
              m.popups[-1] == (screen_text(rt, st, bus, REVERB, 1, {'DENSITY': rv['min']}), SCREEN_MS),
              f'BUS {bus} Reverb: DENSITY goes to slot {bus}')
    m, sc = fx_machine(img, man)
    m.knob_bus(0)
    sc.open()
    m.bus_effect(0, REVERB)
    sc.value()
    sc.value()                                          # Reverb has CTRL 4-6: screen 2, then DENSITY
    rv = st.by_fx[REVERB][0]
    m.clear()
    m.dispatch(EV_KNOB, 1, 0)
    got, other, ok = m.frames()
    check(ok and got == [fx_frame(REVERB, 0, rv['aa'], rv['min'])] and m.state()['bus'] == 0 and
          m.popups[-1] == (screen_text(rt, st, 0, REVERB, 1, {'DENSITY': rv['min']}), SCREEN_MS),
          'the knobs on the input FX (test4): its extra screens too, Reverb\'s DENSITY goes to slot 0')


def range_checks(img, man, st):
    """Every setting of every effect, on BUS 3: CTRL at 0 and at 127 send the firmware's min and max."""
    bad, n = [], 0
    for fx in range(1, 49):
        if not st.by_fx[fx]:
            continue
        m, sc = fx_machine(img, man, bus=3, fx=fx)
        sc.open()
        m.bus_effect(3, fx)
        while m.state()['screen'] == 0:
            sc.value()
        for k, s in enumerate(st.by_fx[fx]):
            if k and not k % 3:
                sc.value()
            out = []
            for raw, v in ((0, s['min']), (127, s['max'])):
                m.clear()
                m.dispatch(EV_KNOB, k % 3 + 1, raw)
                out.append(m.frames() == ([fx_frame(fx, 3, s['aa'], v)], [], True) or
                           (v == s['default'] and raw == 0 and m.frames() == ([], [], True)))
            n += 1
            if not all(out):
                bad.append((fx, s['name'], out))
    check(not bad and n == 135, f'all {n} settings: CTRL at 0 sends the firmware\'s min, at 127 its max, one frame '
                                f'each ({bad[:4]})')


def resend_checks(img, parent, man, st):
    m, p = Machine(img, man['entries']), Machine(parent)
    for mm in (m, p):
        mm.set_bus(1, TAPE_ECHO)
        mm.set_bus(2, TAPE_ECHO, knobs=False)
    e = man['entries']
    te = {s['name']: (i, s) for i, s in enumerate(st.by_fx[TAPE_ECHO])}
    first = m.r32(e['fde_first'] + TAPE_ECHO) & 0xFF
    edits = {(1, 'TAPE DIST'): 2, (1, 'BASS'): 10, (2, 'TREBLE'): 19, (0, 'BASS'): 7}
    for (bus, name), v in edits.items():               # held as the extra screens leave them (slot 0: the input FX)
        i = first + te[name][0]
        m.uc.mem_write(e['fde_values'] + bus * 135 + i, bytes([v]))
        m.uc.mem_write(e['fde_edited'] + bus * 135 + i, bytes([1]))
    ours1 = [fx_frame(TAPE_ECHO, 1, te['BASS'][1]['aa'], 10), fx_frame(TAPE_ECHO, 1, te['TAPE DIST'][1]['aa'], 2)]
    ours2 = [fx_frame(TAPE_ECHO, 2, te['TREBLE'][1]['aa'], 19)]
    ours0 = [fx_frame(TAPE_ECHO, 0, te['BASS'][1]['aa'], 7)]

    def both(action, label, insert):
        """action on parent and image; the image must send the parent's frames with `insert` (FxType frame ->
        frames) right after each such FxType frame, and nothing else."""
        out = []
        for mm in (p, m):
            mm.clear()
            action(mm)
            out.append(mm.frames())
        (pf, po, pok), (mf, mo, mok) = out
        want = []
        for f in pf:
            want.append(f)
            want += insert.get(f, [])
        check(pok and mok and mo == po and mf == want and any(f in insert for f in pf) == bool(insert),
              f'{label}: the parent\'s {len(pf)} frames' + (f', and after the FxType frame the bus\'s edited values '
                                                             f'({sum(len(v) for v in insert.values())} frames)'
                                                             if insert else ', nothing added'))
        return pf

    both(lambda mm: mm.set_bus(1, REVERB), 'BUS 1 to Reverb (stock MFX choice)', {})
    pf = both(lambda mm: mm.set_bus(1, TAPE_ECHO), 'BUS 1 back to Tape Echo (stock MFX choice)',
              {fxtype_frame(1, TAPE_ECHO): ours1})
    check(fxtype_frame(1, TAPE_ECHO) in pf, 'the stock effect select did send FxType1 = 9 there')
    both(lambda mm: mm.set_bus(1, TAPE_ECHO), 'BUS 1 Tape Echo chosen again (stock sends no FxType: the chip still '
                                              'has it)', {})
    both(lambda mm: mm.dispatch(EV_KNOB, 1, 90), 'a CTRL knob on BUS 1 Tape Echo', {})
    both(lambda mm: mm.call(SYS_SET, SYSPRM, 0x7F, REVERB, 0), 'FxType1 = Reverb through the system setter', {})
    both(lambda mm: mm.call(SYS_SET, SYSPRM, 0x7F, TAPE_ECHO, 0), 'FxType1 = Tape Echo through the system setter',
         {fxtype_frame(1, TAPE_ECHO): ours1})
    both(lambda mm: mm.call(SYS_SET, SYSPRM, 0x80, REVERB, 0), 'FxType2 = Reverb through the system setter', {})
    both(lambda mm: mm.call(SYS_SET, SYSPRM, 0x80, TAPE_ECHO, 0), 'FxType2 = Tape Echo: BUS 2\'s values only',
         {fxtype_frame(2, TAPE_ECHO): ours2})
    both(lambda mm: mm.call(SYS_SET, SYSPRM, 0x81, TAPE_ECHO, 0), 'FxType3 = Tape Echo (no edits on BUS 3)', {})
    both(lambda mm: mm.call(DT1, 0x80B62F09, 0x7F, 0, TAPE_ECHO),
         'FxType1 = Tape Echo sent straight to the builder, as the BUS 1/2 swap 0x8001b8e2 sends it',
         {fxtype_frame(1, TAPE_ECHO): ours1})
    both(lambda mm: mm.call(DT1, 0x80B62F09, 0x7E, 0, TAPE_ECHO), 'FxType0 (the input FX) = Tape Echo: the input '
         'FX\'s edited values (test4)', {fxtype_frame(0, TAPE_ECHO): ours0})
    both(lambda mm: (mm.call(SYS_INIT, SYSPRM), mm.call(CHIP_RESET, 0x80591794, count=50_000_000)),
         'system init and the chip reset (every effect\'s CTRL 1-3 again, FxType 0 everywhere)', {})
    for mm in (m, p):
        mm.w32(FXTYPE_SENT + 4, 0xFFFFFFFF)            # the select's cache as boot leaves it
    both(lambda mm: mm.set_bus(1, TAPE_ECHO), 'after it, BUS 1 Tape Echo chosen again', {fxtype_frame(1, TAPE_ECHO): ours1})
    st_ = m.state()
    check(st_['resent'] == 2 + 2 + 1 + 2 + 1 + 2, f'the module counted 10 values sent again ({st_})')


def stop_checks(img, parent, man):
    """Four quick EXITs (no FX screen up) are STOP as on the parent."""
    out = []
    for image in (parent, img):
        m = Machine(image, man['entries'])
        for _ in range(4):
            m.dispatch(EV_KEY, KEY_EXIT)
            m.dispatch(EV_KEY_UP, KEY_EXIT)
        out.append((m.frames(), m.popups))
    check(out[0] == out[1] and out[0][1] == [('STOP', 1000)], 'four quick EXITs are stock\'s STOP, byte for byte as '
                                                               'on the parent')


SCRIPTS = (
    ('EXIT alone', [(EV_KEY, KEY_EXIT), (EV_KEY_UP, KEY_EXIT)]),
    ('VALUE alone', [(EV_KEY, KEY_VALUE), (EV_KEY_UP, KEY_VALUE)]),
    ('VALUE held, then EXIT', [(EV_KEY, KEY_VALUE), (EV_KEY, KEY_EXIT), (EV_KEY_UP, KEY_EXIT),
                               (EV_KEY_UP, KEY_VALUE)]),
    ('EXIT held, a pad', [(EV_KEY, KEY_EXIT), (EV_PAD, 3, 100), (EV_PAD_UP, 3, 0), (EV_KEY_UP, KEY_EXIT)]),
    ('EXIT held, SHIFT', [(EV_KEY, KEY_EXIT), (EV_KEY, KEY_SHIFT), (EV_KEY_UP, KEY_SHIFT), (EV_KEY_UP, KEY_EXIT)]),
    ('SHIFT held, VALUE', [(EV_KEY, KEY_SHIFT), (EV_KEY, KEY_VALUE), (EV_KEY_UP, KEY_VALUE),
                           (EV_KEY_UP, KEY_SHIFT)]),
    ('EXIT held, VALUE', [(EV_KEY, KEY_EXIT), (EV_KEY, KEY_VALUE), (EV_KEY_UP, KEY_VALUE), (EV_KEY_UP, KEY_EXIT)]),
    ('EXIT held, VALUE turned', [(EV_KEY, KEY_EXIT), (EV_ENCODER, 0, 1), (EV_ENCODER, 0, -1), (EV_KEY_UP, KEY_EXIT)]),
    ('VALUE turned', [(EV_ENCODER, 0, 1), (EV_ENCODER, 0, -3)]),
    ('knobs', [(EV_KNOB, 1, 40), (EV_KNOB, 2, 90), (EV_KNOB, 3, 127), (EV_KNOB, 3, 3)]),
    ('pads', [(EV_PAD, 0, 127), (EV_PAD_UP, 0, 0), (EV_PAD, 15, 60), (EV_PAD_UP, 15, 0)]),
    ('a VALUE release alone', [(EV_KEY_UP, KEY_VALUE)]),
    ('an EXIT release alone', [(EV_KEY_UP, KEY_EXIT)]),
)
KEYS_ALONE = [k for k in range(0x10, 0x32) if k not in (0x13, KEY_VALUE)]


def run_script(m, script):
    out = []
    for kind, a1, *rest in script:
        m.clear()
        try:
            r = m.dispatch(kind, a1, rest[0] if rest else 0)
        except Exception as e:                          # stock paths the harness can't run end the same way
            r = f'{type(e).__name__}'
        out.append((r, bytes(v for p, v in m.uart), tuple(m.popups), tuple(m.doom), tuple(m.fallback),
                    bytes(m.uc.mem_read(KEYS, 16)), m.r16(PAGE_ID)))
    return out


def passthrough_checks(img, parent, man):
    """No extra screen up, with edited values held: every event as on the parent, the FX buttons alone included."""
    e = man['entries']
    for label, script in SCRIPTS:
        a, b = Machine(parent), Machine(img, e)
        for m in (a, b):                                # BUS 1 with an effect on, so knobs reach the chip
            m.set_bus(1, REVERB)
        for bus in range(5):                            # an edited value held for every slot's Reverb and Tape Echo
            for fx in (REVERB, TAPE_ECHO):
                i = b.r32(e['fde_first'] + fx) & 0xFF
                b.uc.mem_write(e['fde_values'] + bus * 135 + i, bytes([3]))
                b.uc.mem_write(e['fde_edited'] + bus * 135 + i, bytes([1]))
        x, y = run_script(a, script), run_script(b, script)
        check(x == y and all(r[3] for r in y), f'{label}: as on the parent, every event through DOOM OS\'s filter '
                                               f'({sum(len(r[1]) for r in y)} chip bytes)')
    bad = []
    for k in KEYS_ALONE:
        script = [(EV_KEY, k), (EV_KEY_UP, k)]
        if run_script(Machine(parent), script) != run_script(Machine(img, man['entries']), script):
            bad.append(hex(k))
    check(not bad, f'each of {len(KEYS_ALONE)} keys pressed and released alone: as on the parent, the FX buttons '
                   f'included ({bad})')
    m = Machine(img, man['entries'])
    m.set_bus(1, REVERB)
    m.clear()
    m.dispatch(EV_KNOB, 3, 127)
    got, other, ok = m.frames()
    check(ok and got == [frame((3, 0, 0x2E, 4), 255)], f'TOP knob 3 with Reverb on BUS 1 still sends LEVEL 255 '
                                                       f'(03 00 2e 04 = 0f 0f) through the stock knob path (and '
                                                       f'{[q.hex() for q in other]} on MIDI out)')


GT_AMP_SIM, KEY_EXT = 23, 0x12


def input_text(st, fx, screen, values=None):
    """An input FX extra screen opened with VALUE + EXT SOURCE (test9): numbered among the extra screens alone."""
    x = st.by_fx[fx]
    lines = [f'{st.effect_names[fx]} {screen}/{(len(x) + 2) // 3}']
    for k, y in enumerate(x[(screen - 1) * 3:screen * 3]):
        lines.append(f'C{k + 1} {y["name"]} {(values or {}).get(y["name"], y["default"])}')
    return '\n'.join(lines)


def input_machine(image, man, fx_in=GT_AMP_SIM):
    """The knobs on BUS 1 (Tape Echo), as on the unit, and the input FX as its INPUT FX Setting screen sets it."""
    m = Machine(image, man['entries'] if man else None)
    m.set_bus(1, TAPE_ECHO)
    m.bus_effect(0, fx_in)
    m.clear()
    return m


def input_checks(img, parent, man, st):
    e = man['entries']
    gt = st.by_fx[GT_AMP_SIM]
    n = (len(gt) + 2) // 3
    chord = [(EV_KEY, KEY_VALUE), (EV_KEY, KEY_EXT), (EV_KEY_UP, KEY_EXT), (EV_KEY_UP, KEY_VALUE)]
    m, p = input_machine(img, man), input_machine(parent, None)
    a, b = run_script(p, chord), run_script(m, chord)
    first = input_text(st, GT_AMP_SIM, 1)
    st0 = m.state()
    check(b[0] == a[0] and b[1][2] == ((first, SCREEN_MS),) and not b[1][3] and not b[1][4] and not b[1][1] and
          b[2][1:5] == (b'', (), (), ()) and b[3] == a[3] and a[1][3] and st0['input'] == 1 and st0['bus'] == 0 and
          st0['effect'] == GT_AMP_SIM and st0['screen'] == 1,
          f'test9: VALUE held + EXT SOURCE opens the input FX\'s first extra screen ({first!r}); the EXT SOURCE press '
          f'and release are taken (nothing to DOOM OS\'s filter or the chip; the parent passes the press on)')
    seq = []
    for k in range(n):
        out = run_script(m, [(EV_KEY, KEY_VALUE), (EV_KEY_UP, KEY_VALUE)])
        now = m.state()
        seq.append((out[0][2], bool(out[0][3]), now['screen'], now['input']))
    want = [(((input_text(st, GT_AMP_SIM, k + 2), SCREEN_MS),), False, k + 2, 1) for k in range(n - 1)]
    last = seq[-1]
    check(seq[:-1] == want and last[1:] == (False, 0, 0) and len(last[0]) == 1 and last[0][0][1] == GONE_MS,
          f'VALUE steps the input FX\'s screens 2..{n} itself (the press taken) and closes after the last')
    # The knobs edit slot 0: SP TYPE (screen 3, CTRL 2) to its top, then MIC SET (CTRL 3).
    m = input_machine(img, man)
    run_script(m, chord)
    for _ in range(2):
        run_script(m, [(EV_KEY, KEY_VALUE), (EV_KEY_UP, KEY_VALUE)])
    m.clear()
    m.dispatch(EV_KNOB, 2, 127)
    sp = [x for x in gt if x['name'] == 'SP TYPE'][0]
    got, other, ok = m.frames()
    check(ok and got == [fx_frame(GT_AMP_SIM, 0, sp['aa'], sp['max'])] and not m.doom and
          m.popups == [(input_text(st, GT_AMP_SIM, 3, {'SP TYPE': sp['max']}), SCREEN_MS)],
          f'CTRL 2 on the third screen sets the input FX\'s SP TYPE to {sp["max"]} on slot 0 (one DT1; the knob '
          f'taken) and the screen shows it')
    gone = run_script(m, [(EV_KEY, KEY_EXIT), (EV_KEY_UP, KEY_EXIT)])
    st1 = m.state()
    after = run_script(m, [(EV_KEY, KEY_VALUE), (EV_KEY_UP, KEY_VALUE)])
    check(st1['screen'] == 0 and st1['input'] == 0 and len(gone[0][2]) == 1 and gone[0][2][0][1] == GONE_MS and
          gone[0][3] and after[0][3] and not after[0][2],
          'another button (EXIT) leaves: the screen goes, and VALUE is stock\'s again')
    # An input FX with no extra settings (Crusher), or none: nothing shows, the EXT SOURCE press is still taken.
    res = []
    for fx_in in (CRUSHER, 0):
        mm = input_machine(img, man, fx_in)
        out = run_script(mm, chord)
        res.append((out[1][2], out[1][3], out[1][1], out[2][3], mm.state()['screen'], mm.state()['input']))
    check(all(r == ((), (), b'', (), 0, 0) for r in res),
          f'an input FX without extra settings, or none: nothing shown, the input not switched ({res})')
    # test10: on a page the dispatcher hands nothing to (not TOP), the chord still opens and EXT SOURCE is still taken.
    mm = input_machine(img, man)
    mm.uc.mem_write(PAGE_LIVE, struct.pack('<H', 7))
    out = run_script(mm, chord)
    check(out[1][2] == ((first, SCREEN_MS),) and not out[1][1] and not out[1][3] and out[2][1:5] == (b'', (), (), ()) and
          mm.state()['input'] == 1,
          'test10: with no page taking events (another page than TOP), VALUE + EXT SOURCE still opens the input FX\'s '
          'first screen and the input is not switched')
    # test10: VALUE's hold as the dispatcher's handlers saw it is enough (its bit in 0x80592448 cleared by hand).
    mm = input_machine(img, man)
    run_script(mm, [(EV_KEY, KEY_VALUE)])
    keys = bytearray(mm.uc.mem_read(KEYS, 16))
    keys[KEY_VALUE >> 3] &= ~(1 << (KEY_VALUE & 7)) & 0xFF
    mm.uc.mem_write(KEYS, bytes(keys))
    out = run_script(mm, [(EV_KEY, KEY_EXT), (EV_KEY_UP, KEY_EXT), (EV_KEY_UP, KEY_VALUE)])
    check(out[0][2] == ((first, SCREEN_MS),) and not out[0][1] and mm.state()['value_down'] == 0,
          'test10: VALUE held per the dispatcher\'s own press and release is enough for the chord, and its release '
          'ends it')
    # EXT SOURCE alone (no VALUE): as the parent.
    x, y = run_script(input_machine(parent, None), [(EV_KEY, KEY_EXT), (EV_KEY_UP, KEY_EXT)]), \
        run_script(input_machine(img, man), [(EV_KEY, KEY_EXT), (EV_KEY_UP, KEY_EXT)])
    check(x == y and x[0][3], 'EXT SOURCE alone: as on the parent (it reaches DOOM OS\'s filter and the stock handling)')


# ---- test11: HOLD + VALUE, and the edits kept over a restart ----
FILE = dict(open=0x800DEC60, read=0x800DEC48, write=0x800DD9B8, close=0x800DEBD8)
SAVED, TOGGLE_MS = 'B:/_fx_hidden.bin', 1500


class FileMachine(Machine):
    """The internal storage as files in a dict: open 0 reads (a missing file fails), 0x601 creates or truncates
    (fails while fail_open); short makes a write one byte short."""

    def __init__(self, img, symbols=None, files=None):
        self.files = {k: bytearray(v) for k, v in (files or {}).items()}
        self.fds, self.fs, self.fail_open, self.short = {}, [], False, False
        super().__init__(img, symbols)
        for name, fn in (('read', self._rd), ('write', self._wr), ('close', self._cl)):
            self.uc.hook_add(UC_HOOK_CODE, fn, None, begin=FILE[name], end=FILE[name])

    def _args(self, n):
        return [self.uc.reg_read(getattr(ar, f'UC_ARM_REG_R{k}')) for k in range(n)]

    def _open(self, uc, a, size, _):
        path = bytes(uc.mem_read(uc.reg_read(ar.UC_ARM_REG_R0), 96)).split(b'\0')[0].decode('latin-1')
        flags = uc.reg_read(ar.UC_ARM_REG_R1)
        self.opened.append(path)
        self.fs.append(('open', path, flags))
        if (flags == 0 and path not in self.files) or (flags == 0x601 and self.fail_open):
            return self._ret(-1)
        if flags == 0x601:
            self.files[path] = bytearray()
        fd = 3
        while fd in self.fds:
            fd += 1
        self.fds[fd] = [path, 0]
        self._ret(fd)

    def _rd(self, uc, a, size, _):
        fd, buf, n = self._args(3)
        path, pos = self.fds[fd]
        data = bytes(self.files[path][pos:pos + n])
        uc.mem_write(buf, data)
        self.fds[fd][1] += len(data)
        self._ret(len(data))

    def _wr(self, uc, a, size, _):
        fd, buf, n = self._args(3)
        path, pos = self.fds[fd]
        n -= int(self.short)
        self.files[path][pos:pos + n] = bytes(uc.mem_read(buf, n))
        self.fds[fd][1] += n
        self.fs.append(('write', path, n))
        self._ret(n)

    def _cl(self, uc, a, size, _):
        self.fs.append(('close', self.fds.pop(self._args(1)[0])[0]))
        self._ret(0)


def fnv(b, h=2166136261):
    for x in b:
        h = ((h ^ x) * 16777619) & 0xFFFFFFFF
    return h


def saved_file(records, off=0, magic=b'FXHS', version=1):
    """The file as the module writes it: magic, version, the switch, the count, FNV-1a, (slot, value, ID) records."""
    body = b''.join(struct.pack('<BBH', bus, v, i) for bus, v, i in records)
    head = magic + bytes([version, off]) + struct.pack('<H', len(records))
    return head + struct.pack('<I', fnv(body, fnv(head))) + body


def read_saved(b):
    """(the switch, [(slot, value, ID)]) of a valid file, else None."""
    b = bytes(b or b'')
    if len(b) < 12 or b[:4] != b'FXHS' or b[4] != 1:
        return None
    n = struct.unpack_from('<H', b, 6)[0]
    if len(b) != 12 + 4 * n or struct.unpack_from('<I', b, 8)[0] != fnv(b[12:], fnv(b[:8])):
        return None
    return b[5], [struct.unpack_from('<BBH', b, 12 + 4 * k) for k in range(n)]


def hold_value(m):
    """HOLD down, VALUE pressed and let go, HOLD let go; the VALUE press's frames, popups and filter calls."""
    m.dispatch(EV_KEY, KEY_HOLD)
    m.clear()
    m.dispatch(EV_KEY, KEY_VALUE)
    got = (m.frames(), list(m.popups), list(m.doom))
    m.clear()
    m.dispatch(EV_KEY_UP, KEY_VALUE)
    up = list(m.doom)
    m.dispatch(EV_KEY_UP, KEY_HOLD)
    return got + (up,)


def toggle_checks(img, parent, man, st):
    e = man['entries']
    te = {x['name']: (i, x) for i, x in enumerate(st.by_fx[TAPE_ECHO])}
    edits = {(1, 'TAPE DIST'): 2, (1, 'BASS'): 10, (2, 'TREBLE'): 19, (0, 'BASS'): 7}

    def setup(mm, ours):
        mm.set_bus(1, TAPE_ECHO)
        mm.set_bus(2, TAPE_ECHO, knobs=False)
        mm.bus_effect(0, TAPE_ECHO)
        mm.call(DT1, 0x80B62F09, 0x7E, 0, TAPE_ECHO)    # the input FX's FxType, as its own screen sends it
        if ours:
            first = mm.r32(e['fde_first'] + TAPE_ECHO) & 0xFF
            for (bus, name), v in edits.items():
                i = first + te[name][0]
                mm.uc.mem_write(e['fde_values'] + bus * 135 + i, bytes([v]))
                mm.uc.mem_write(e['fde_edited'] + bus * 135 + i, bytes([1]))
        mm.clear()

    def sent(value):
        return [fx_frame(TAPE_ECHO, bus, te[name][1]['aa'], value(bus, name)) for bus in range(5)
                for name in sorted((n for b, n in edits if b == bus), key=lambda n: te[n][0])]

    m, p = Machine(img, e), Machine(parent)
    setup(m, True)
    setup(p, False)
    held = [run_script(x, [(EV_KEY, KEY_HOLD)]) for x in (p, m)]
    for x in (p, m):
        x.dispatch(EV_KEY_UP, KEY_HOLD)
    (got, other, ok), pops, doom, up = hold_value(m)
    want = sent(lambda bus, name: te[name][1]['default'])
    check(held[0] == held[1] and ok and got == want and pops == [('HIDDEN FX OFF', TOGGLE_MS)] and not doom and
          not up and m.state()['off'] == 1 and m.state()['value_taken'] == 0,
          f'test11: HOLD + VALUE: HIDDEN FX OFF, each slot\'s edited Tape Echo settings back to their defaults '
          f'({len(want)} DT1s, slot by slot in table order); the VALUE press and release taken; HOLD alone as on '
          f'the parent')
    out = []
    for mm in (p, m):
        mm.clear()
        mm.set_bus(1, REVERB)
        mm.set_bus(1, TAPE_ECHO)
        out.append(mm.frames())
    check(out[0] == out[1] and out[0][2], 'off: BUS 1 back to Tape Echo sends the parent\'s frames only (no edits)')
    chord = [(EV_KEY, KEY_VALUE), (EV_KEY, KEY_EXT), (EV_KEY_UP, KEY_EXT), (EV_KEY_UP, KEY_VALUE)]
    a, b = run_script(p, chord), run_script(m, chord)
    check(a == b and m.state()['input'] == 0, 'off: VALUE + EXT SOURCE as on the parent (the input FX\'s screens '
                                              'don\'t open, EXT SOURCE is stock\'s)')
    seqs = []
    for image, man_ in ((parent, None), (img, man)):
        mm, ss = fx_machine(image, man_)
        if man_:
            hold_value(mm)
        ss.open()
        mm.bus_effect(1, TAPE_ECHO)
        seq = []
        for k in range(3):
            mm.clear()
            ss.value()
            seq.append((ss.flag(VIEW_REMAIN), ss.flag(VIEW_SCREEN2), mm.popups))
        seqs.append(seq)
    check(seqs[0] == seqs[1], f'off: on the FX screen (REMAIN + FX) VALUE is stock\'s toggle of screens 1 and 2, no '
                              f'extra screens ({seqs[1]})')
    (got, other, ok), pops, doom, up = hold_value(m)
    want = sent(lambda bus, name: edits[(bus, name)])
    check(ok and got == want and pops == [('HIDDEN FX ON', TOGGLE_MS)] and m.state()['off'] == 0,
          f'HOLD + VALUE again: HIDDEN FX ON and the edits sent again ({len(want)} DT1s)')
    out = []
    for mm in (p, m):
        mm.clear()
        mm.set_bus(1, REVERB)
        mm.set_bus(1, TAPE_ECHO)
        out.append(mm.frames()[0])
    ours = sent(lambda bus, name: edits[(bus, name)])[1:3]          # BUS 1's two
    tail = [f for f in out[1] if f not in out[0]]
    check(tail == ours, 'on again: BUS 1 back to Tape Echo re-sends its edits after the FxType, as before')


def saved_checks(img, man, st):
    e = man['entries']
    x0 = st.by_fx[GT_AMP_SIM][0]                        # the input FX's first extra screen, CTRL 1
    raw, other_raw = (0, 127) if x0['default'] != x0['min'] else (127, 0)
    tv, ov = (x0['min'], x0['max']) if raw == 0 else (x0['max'], x0['min'])     # a turn that changes it, and back
    chord = [(EV_KEY, KEY_VALUE), (EV_KEY, KEY_EXT), (EV_KEY_UP, KEY_EXT), (EV_KEY_UP, KEY_VALUE)]
    leave = [(EV_KEY, KEY_EXIT), (EV_KEY_UP, KEY_EXIT)]

    def fresh(files=None):
        m = FileMachine(img, e, files)
        m.set_bus(1, TAPE_ECHO)
        m.bus_effect(0, GT_AMP_SIM)
        m.call(DT1, 0x80B62F09, 0x7E, 0, GT_AMP_SIM)    # the boot gives the chip the input FX
        m.clear()
        return m

    def first_event(m):
        """SHIFT pressed and let go on TOP: the frames its press sent."""
        m.clear()
        m.dispatch(EV_KEY, KEY_SHIFT)
        got = m.frames()
        m.dispatch(EV_KEY_UP, KEY_SHIFT)
        return got

    def ours(m, kind=None):
        """The module's file calls (DOOM OS opens B:/DOOMOS.CFG on its own)."""
        return [f for f in m.fs if f[1] == SAVED and (kind is None or f[0] == kind)]

    def edit(m, r):
        run_script(m, chord)
        m.dispatch(EV_KNOB, 1, r)

    # no file yet: the main screen's first event looks for it; an edit is written when its screen is left
    m = fresh()
    sent0 = first_event(m)[0]
    looked = ours(m)
    edit(m, raw)
    early = ours(m, 'write')
    run_script(m, leave)
    data = bytes(m.files.get(SAVED, b''))
    st_ = m.state()
    check(looked == [('open', SAVED, 0)] and not sent0 and not early and
          read_saved(data) == (0, [(0, tv, x0['id'])]) and st_['saves'] == 1 and st_['dirty'] == 0 and
          st_['loads'] == 0 and st_['bad_files'] == 0,
          f'test11: no file: the main screen\'s first event looks for {SAVED} once and sends nothing; an edit (the '
          f'input FX\'s {x0["name"]} to {tv}) is written when its screen is left: one record (slot 0, {tv}, ID '
          f'{x0["id"]})')
    # a restart: the file read at the first event, the edit sent for the effect the slot has
    m = fresh({SAVED: data})
    got, other, ok = first_event(m)
    first = m.r32(e['fde_first'] + GT_AMP_SIM) & 0xFF
    kept = (m.uc.mem_read(e['fde_values'] + first, 1)[0], m.uc.mem_read(e['fde_edited'] + first, 1)[0])
    check(ok and got == [fx_frame(GT_AMP_SIM, 0, x0['aa'], tv)] and kept == (tv, 1) and m.state()['loads'] == 1 and
          not ours(m, 'write'),
          'after a restart the first event reads it: the edit is back in RAM and sent to the input FX (one DT1), '
          'nothing written')
    m.clear()
    m.call(DT1, 0x80B62F09, 0x7E, 0, GT_AMP_SIM)
    check(fx_frame(GT_AMP_SIM, 0, x0['aa'], tv) in m.frames()[0],
          'and an FxType for the input FX re-sends it, as an edit made since boot')
    # switched off: kept too; after a restart nothing is sent
    hold_value(m)
    off_file = bytes(m.files[SAVED])
    m2 = fresh({SAVED: off_file})
    sent2 = first_event(m2)[0]
    check(read_saved(off_file) == (1, [(0, tv, x0['id'])]) and m2.state()['off'] == 1 and not sent2 and
          m2.state()['loads'] == 1,
          'HOLD + VALUE writes the switch: switched off, a restart sends nothing and stays off')
    (got2, _, ok2), pops, _, _ = hold_value(m2)
    check(ok2 and got2 == [fx_frame(GT_AMP_SIM, 0, x0['aa'], tv)] and pops == [('HIDDEN FX ON', TOGGLE_MS)] and
          read_saved(m2.files[SAVED]) == (0, [(0, tv, x0['id'])]),
          'switched on again there: the edit is sent and the file says on')
    # bad files change nothing; unknown settings are dropped and values kept in range
    good = saved_file([(0, tv, x0['id'])])
    bad = {'magic': b'FXHT' + good[4:], 'version': good[:4] + b'\x02' + good[5:], 'short': good[:-1],
           'long': good + b'\0', 'sum': good[:12] + bytes([good[12] ^ 1]) + good[13:]}
    res = {}
    for label, b in bad.items():
        mm = fresh({SAVED: b})
        sent_b = first_event(mm)[0]
        res[label] = (mm.state()['bad_files'], mm.state()['loads'], bool(sent_b),
                      mm.uc.mem_read(e['fde_edited'] + first, 1)[0])
    check(all(r == (1, 0, False, 0) for r in res.values()), f'a bad file (wrong magic, version, size or sum) is '
                                                              f'ignored: nothing applied or sent ({res})')
    mm = fresh({SAVED: saved_file([(0, 255, x0['id']), (0, 5, 9999), (7, 5, x0['id'])])})
    sent_c = first_event(mm)[0]
    v = mm.uc.mem_read(e['fde_values'] + first, 1)[0]
    check(v == min(255, x0['max']) and sent_c == [fx_frame(GT_AMP_SIM, 0, x0['aa'], v)] and
          mm.state()['loads'] == 1,
          f'a record for an ID this build lacks, or a slot past 4, is dropped; a value past the firmware\'s range is '
          f'kept inside it ({v})')
    # a failed write: counted, the edit stays pending and goes at the next leave
    mm = fresh()
    mm.fail_open = True
    edit(mm, raw)
    run_script(mm, leave)
    first_try = (mm.state()['save_errors'], mm.state()['dirty'], SAVED in mm.files)
    mm.fail_open = False
    edit(mm, other_raw)
    run_script(mm, leave)
    check(first_try == (1, 1, False) and read_saved(mm.files[SAVED]) == (0, [(0, ov, x0['id'])]) and
          mm.state()['dirty'] == 0,
          f'a write that can\'t open is counted and the edits stay pending; the next leave writes them ({first_try})')


FX_SHOWN = 0x8059259C                                   # the FX screen, from when it opens (stock clears it later)


def screen_stay_checks(img, parent, man, st):
    """Test12: HOLD + VALUE with the FX screen up holds it; the file waits until no FX screen is up."""
    e = man['entries']
    res = []
    for image, man_ in ((parent, None), (img, man)):
        mm, ss = fx_machine(image, man_)
        ss.open(remain=False)                           # the FX button alone: the screen that goes after 2 s
        mm.bus_effect(1, TAPE_ECHO)
        hold_value(mm)
        mm.bus_effect(1, TAPE_ECHO)
        res.append((ss.flag(VIEW_REMAIN), mm.uc.mem_read(REMAIN_GLOBAL, 1)[0], bool(ss.run(2500))))
    check(res[0] == (0, 0, True) and res[1] == (1, 1, False),
          f'test12: with the FX screen up (opened by its button alone), HOLD + VALUE holds it (+0x1b3f, 0x80592320) and '
          f'it stays past 2 s; on the parent it goes ({res})')
    # the file: nothing written while the FX screen is up; at the first key release after it is gone
    m = FileMachine(img, e)
    m.set_bus(1, TAPE_ECHO)
    sc = Screen(m)
    sc.open()
    m.bus_effect(1, TAPE_ECHO)
    for _ in range(2):
        sc.value()                                      # screen 2, then the first extra screen
    m.dispatch(EV_KNOB, 1, 127)
    sc.value()
    sc.value()                                          # on past the last extra screens: screen 1 again
    hold_value(m)
    during = [f for f in m.fs if f[1] == SAVED and f[0] == 'write']
    pending = m.state()['dirty']
    m.call(0x800C4E50, m.r32(TOP_PAGE) + 0x38, 4, 1, count=20_000_000)   # the FX screen closed, as stock closes it
    run_script(m, [(EV_KEY, KEY_SHIFT)])
    on_press = [f for f in m.fs if f[1] == SAVED and f[0] == 'write']
    run_script(m, [(EV_KEY_UP, KEY_SHIFT)])
    got = read_saved(m.files.get(SAVED))
    te = st.by_fx[TAPE_ECHO][0]
    check(not during and pending == 1 and not on_press and got == (1, [(1, te['max'], te['id'])]),
          f'an edit on the FX screen and HOLD + VALUE there: nothing written while the FX screen is up (it is still '
          f'pending), nor on the next key press; the next key release after the screen is gone writes both ({got})')


FX_UPDATE_SLOT, DRAWN_SCREEN2, POPUP_LEFT, CLOCK = 0x802269E8, 0x8059232C, 0x805922B4, 0x8059226C


def chip_redraw_checks(img, parent, man, st):
    """Test13: the effect the chip has (its FxTypes) gets the edits; the FX screen draws again after the popup."""
    e = man['entries']
    # the chip's effect, not 0x27c: after a restart the first event can be an FX button stock hasn't handled yet
    x0 = st.by_fx[TAPE_ECHO][0]
    good = saved_file([(1, x0['max'], x0['id'])])
    m = FileMachine(img, e, {SAVED: good})
    m.set_bus(1, TAPE_ECHO)                             # the boot: Tape Echo on BUS 1, on the chip
    chip = m.uc.mem_read(e['fde_chip'], 5)
    m.bus_effect(1, REVERB)                             # 0x27c[1] says otherwise for now
    m.clear()
    m.dispatch(EV_KEY, KEY_SHIFT)
    got = m.frames()[0]
    m.dispatch(EV_KEY_UP, KEY_SHIFT)
    check(chip[1] == TAPE_ECHO and got == [fx_frame(TAPE_ECHO, 1, x0['aa'], x0['max'])],
          f'test13: the module notes each FxType as the chip\'s effect ({list(chip)}); after a restart the saved edit '
          f'goes to the effect the chip has on BUS 1 (Tape Echo), while 0x27c[1] says Reverb ({len(got)} DT1)')
    # through the FX screen's vtable slot the update is stock's
    out = []
    for image, sym in ((parent, None), (img, e)):
        mm, ss = fx_machine(image, {'entries': sym} if sym else None)
        ss.open()
        mm.bus_effect(1, TAPE_ECHO)
        v = ss.view()
        fn = mm.r32(FX_UPDATE_SLOT)
        for _ in range(60):
            mm.call(fn & ~1, v, count=20_000_000)
        out.append((fn, bytes(mm.uc.mem_read(v + 0x1B10, 0x40)), bytes(mm.uc.mem_read(0x80592320, 0x40)),
                    bool([c for c in mm.closes if c == v])))
    check(out[0][0] == 0x80146599 and out[1][0] == e['fde_fx_update'] and out[0][1:] == out[1][1:],
          f'the FX screen\'s vtable +0x28 is fde_fx_update ({out[1][0]:#x}); 3 s of its updates through it leave the '
          f'screen and its globals as the stock update does')
    # HOLD + VALUE on it: the screen draws again once the popup's time is over and no popup is up
    m, sc = fx_machine(img, man)
    sc.open()
    m.bus_effect(1, TAPE_ECHO)
    v = sc.view()
    fn = m.r32(FX_UPDATE_SLOT) & ~1
    for _ in range(3):
        m.call(fn, v, count=20_000_000)
    m.w32(CLOCK, 1000)
    hold_value(m)
    writes = []
    m.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, acc, a, size, value, _: writes.append((a, value)), None,
                  begin=DRAWN_SCREEN2, end=DRAWN_SCREEN2)
    m.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, acc, a, size, value, _: writes.append((a, value)), None,
                  begin=v + 0x1B15, end=v + 0x1B15)
    seq = []
    for clock, left in ((1000, 1500), (1000 + 24 * 900, 600), (1000 + 24 * 1700, 200), (1000 + 24 * 1700, -1),
                        (1000 + 24 * 1800, -1)):
        m.w32(CLOCK, clock)
        m.w32(POPUP_LEFT, left)
        del writes[:]
        m.call(fn, v, count=20_000_000)
        drawn = [x for a, x in writes if a == DRAWN_SCREEN2]
        flag = [x for a, x in writes if a == v + 0x1B15]
        seq.append((m.state()['redraws'], len(drawn) == 2 and drawn[0] == 0xFFFFFFFF and drawn[1] in (0, 1),
                    1 in flag))
    check(seq == [(0, False, False)] * 3 + [(1, True, True), (1, False, False)],
          f'after HOLD + VALUE on the FX screen: no redraw while the popup\'s 1.6 s run or a popup is still up; the '
          f'first update after both takes its screen as changed (0x8059232c set to -1, then back to what it draws) and '
          f'asks to draw it (+0x1b15 = 1), once ({seq})')


def pointer_checks(img, parent, man, st):
    """Test14: another page's object built with the FX screen up on TOP (its constructor clears 0x8059259c): VALUE
    on TOP still steps to the hidden settings."""
    rt = Runtime(parent)
    res = []
    for image, man_ in ((parent, None), (img, man)):
        mm, ss = fx_machine(image, man_)
        ss.open()
        mm.bus_effect(1, TAPE_ECHO)
        v = ss.view()
        reg = mm.r32(mm.r32(0x801F8F74 + 16 * 5))
        mm.uc.mem_write(EVENT, struct.pack('<6h', 1, 0, 0, 0, 0, 0))
        mm.call(reg & ~1, EVENT, count=20_000_000)      # START/END's page object, as on its entry; TOP stays
        cleared = mm.r32(FX_SHOWN)
        seq = []
        for _ in range(2):
            mm.clear()
            ss.value()
            seq.append((ss.flag(VIEW_SCREEN2), mm.popups))
        res.append((cleared, ss.view() == v, mm.r32(FX_SHOWN) == v, seq))
    p, i = res
    want = [(1, []), (1, [(screen_text(rt, st, 1, TAPE_ECHO, 1), SCREEN_MS)])]
    check(p[0] == 0 and p[1] and not p[2] and p[3] == [(0, []), (0, [])] and i[0] == 0 and i[1] and i[2] and
          i[3] == want,
          f'test14: a page\'s constructor clears 0x8059259c with TOP\'s FX screen still up; on the parent VALUE then '
          f'reaches no FX screen (not even screen 2); here TOP\'s filter puts the pointer back and VALUE steps to screen '
          f'2, then the hidden settings ({i[3]})')
    m, sc = fx_machine(img, man)
    m.clear()
    run_script(m, [(EV_KEY, KEY_SHIFT), (EV_KEY_UP, KEY_SHIFT)])
    check(m.r32(FX_SHOWN) == 0 and m.state()['repairs'] == 0,
          'with no FX screen up, TOP\'s filter leaves stock\'s pointer alone')


KEY_PRESS, KEY_RELEASE, KNOB_HANDLER = 0x8003ABD0, 0x8003ADA0, 0x8003A8D8   # the dispatcher's type 5, 6, 9 handlers


def anypage_checks(img, parent, man, st):
    """Test15: an FX screen up where TOP's object is gone (on the unit: page 34 after REMAIN + FX on an unlit effect,
    the Sound Generator page 30 with the kits and the guitar synth screen), stock's pointer to it the only way there:
    VALUE through the dispatcher's key press handler steps it (screen 2, then the hidden settings) and is taken, its
    release too; CTRL 1 edits the setting shown; a key but VALUE and SHIFT leaves; with the hidden settings off, or no
    FX screen up, VALUE goes on as before."""
    rt = Runtime(parent)
    e = man['entries']
    m, sc = fx_machine(img, man)
    v = sc.open()
    m.bus_effect(1, TAPE_ECHO)
    m.w32(TOP_PAGE, 0)                                  # TOP's object gone, as on those pages; stock's pointer kept

    def ev(kind, a1=0, a2=0):
        m.uc.mem_write(EVENT, struct.pack('<6h', kind, a1, a2, 0, 0, 0))
        return EVENT

    seq = []
    for _ in range(2):
        m.clear()
        m.call(KEY_PRESS, ev(EV_KEY, KEY_VALUE), count=20_000_000)
        taken = m.state()['value_taken']
        m.call(KEY_RELEASE, ev(EV_KEY_UP, KEY_VALUE), count=20_000_000)
        seq.append((sc.flag(VIEW_SCREEN2), m.popups, taken, m.state()['value_taken'], m.state()['value_down']))
    want = [(1, [], 1, 0, 0), (1, [(screen_text(rt, st, 1, TAPE_ECHO, 1), SCREEN_MS)], 1, 0, 0)]
    check(m.r32(FX_SHOWN) == v and m.r32(TOP_PAGE) == 0 and seq == want,
          f'test15: with TOP\'s object gone and only stock\'s pointer to the FX screen (page 34, the Sound Generator '
          f'page), VALUE through the dispatcher\'s key press handler steps to screen 2, then the hidden settings, '
          f'press and release taken ({seq})')
    x0 = st.by_fx[TAPE_ECHO][0]
    m.clear()
    sent = m.state()['sent']
    m.call(KNOB_HANDLER, ev(EV_KNOB, 1, 127), count=20_000_000)
    got = m.frames()[0]
    text = screen_text(rt, st, 1, TAPE_ECHO, 1, {x0['name']: x0['max']})
    check(got == [fx_frame(TAPE_ECHO, 1, x0['aa'], x0['max'])] and m.state()['sent'] == sent + 1 and
          m.popups == [(text, SCREEN_MS)],
          f'test15: there CTRL 1 edits the first hidden setting shown ({x0["name"]} to {x0["max"]}: {len(got)} DT1, '
          f'the screen again)')
    m.clear()
    left = m.call(e['fde_key_down'], ev(EV_KEY, KEY_EXIT))
    check(left == 0 and m.state()['screen'] == 0 and m.popups and m.popups[-1][1] == GONE_MS,
          'test15: there a key but VALUE and SHIFT leaves the hidden settings and goes on (not taken)')
    m.uc.mem_write(e['fde'] + 6, b'\x01')               # the hidden settings off
    off = m.call(e['fde_key_down'], ev(EV_KEY, KEY_VALUE))
    m.call(e['fde_key_up'], ev(EV_KEY_UP, KEY_VALUE))
    m.uc.mem_write(e['fde'] + 6, b'\x00')
    m.w32(FX_SHOWN, 0)                                  # no FX screen up
    none = m.call(e['fde_key_down'], ev(EV_KEY, KEY_VALUE))
    held = m.state()['value_down']
    m.call(e['fde_key_up'], ev(EV_KEY_UP, KEY_VALUE))
    check(off == 0 and none == 0 and held == 1 and m.state()['value_down'] == 0,
          'test15: with the hidden settings off, or no FX screen up, VALUE is not taken (held until its release)')


def main():
    out = Path(sys.argv[1])
    man = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    img = (out / 'SP404MKII_APP1.bin').read_bytes()
    parent = Path(man['parent_app1']).read_bytes()
    fxmap_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(man['fxmap']['path'])
    fxmap_bytes = fxmap_path.read_bytes()
    if sha(fxmap_bytes) != man['fxmap']['sha256']:
        raise ValueError('fxmap.json differs from the one the build used')
    fxmap = {e['id']: e for e in json.loads(fxmap_bytes)}
    st = Settings(Runtime(parent), fxmap)
    static_checks(out, man, img, parent, fxmap, st)
    builder_checks(img, parent, man, fxmap, st)
    screen_checks(img, parent, man, st)
    range_checks(img, man, st)
    resend_checks(img, parent, man, st)
    stop_checks(img, parent, man)
    passthrough_checks(img, parent, man)
    input_checks(img, parent, man, st)
    toggle_checks(img, parent, man, st)
    saved_checks(img, man, st)
    screen_stay_checks(img, parent, man, st)
    chip_redraw_checks(img, parent, man, st)
    pointer_checks(img, parent, man, st)
    anypage_checks(img, parent, man, st)
    print(json.dumps(dict(cases=cases[0])))
    print('ALL PASS' if not fails else f'{len(fails)} FAILED')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
