"""LEVEL for MIDI notes on the Sound Generator (hardware test build): a step on the finished combined APP1.

A step on combined-test17 (v9.52; SG_LEVEL.md), after the fast boot and the kit footer, as those two are. A fork
user's MIDI keyboard has no velocity: every note comes at 127 and the Sound Generator plays it at full volume. In
stock 5.52 a note's level is its velocity x 100 (pads and MIDI alike), LEVEL (CTRL 3, setting 0x7d) sets the
sounding voices' level and then shows the last note's velocity, and only the page's pads use it (as their velocity
with FIXED VELOCITY on). Here LEVEL is a value of its own and the Sound Generator's MIDI note-ons, melodic mode, ARP
on or off, play at velocity x LEVEL / 127 (at least 1). Drum mode and the pads are as before.

Three patches, each over whole instructions checked against the parent (the module, sg_level.c, goes on from there):
- 0x0001FF20 (10 bytes) SetParam's Sound Generator call, a jump to v9.5's parameter engine -> sgl_param, which
  keeps LEVEL's value and goes on to the engine;
- 0x80020480 (12 bytes) the getter's LEVEL case (+0x198 / 100) -> sgl_level_get;
- 0x83FA3448 (10 bytes) arp_midi_event's first three instructions -> sgl_midi_gate (the velocity scaled, then
  those instructions, and on at 0x83fa3452). This is inside the kit stage, which kits save guards whole (as booted,
  for its addresses): kits save never calls arp_midi_event, and nothing in the kit stage moves.
Stock and fork code the module relies on is checked byte for byte (GUARDS), the kit stage as v9.46's module with
the kit footer's one byte. No direct branch in the image's copy rows goes into a patched span. The module (Zig
0.13.0, -Os) goes in a new boot copy row in a 2 KB slot at 0x83FA1800: past v9.6's scale module (to 0x83fa17ec),
below the kit stage (0x83fa2000), RAM no fork branch uses; the builder checks that no row overlaps it and that
nothing in the input refers to it.

usage: python synth/build_sg_level.py IN_APP1 OUT_DIR --zig ZIG [--kits KITS_MANIFEST] [--revision NAME]
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

from build_arp import file_offset, jump, listing, read_module, scatter, checked_asm
from build_sg_subpad import Runtime
from build_start_fix import refs_into

HERE = Path(__file__).resolve().parent
FLASH, COPY = 0x60080000, 0x600800E4
APP0_SHA = '3e35ff30137f741a715566e205384f9b434ca7ac3847e247bad3f0c9c8a2bd23'
REVISION = 'sg-level-test1'
BASE, SLOT = 0x83FA1800, 0x800
SCALES_ROW, KIT_BASE, KIT_END = 0x83FA1000, 0x83FA2000, 0x83FC8450
# The kit stage (kits/build_arp_kit.py, v9.46-test3): its module as it boots (arp_module_sha256, kits save's guard),
# the kit footer step's byte in it, and the symbols the module uses (the v9.46 kits manifest's arp_symbols).
KIT_MODULE_SHA = '666e86b2e139224bb9dfc3f8f343088ccc059a8c2b5a6d3588fb38430ef5b16a'
KIT_FOOTER = (0x83FBAF36, 0x53, 0x00)
KIT = dict(arp_midi_event=0x83FA3449, kit_mode=0x83FC58E0, held_count=0x83FC7B84, held_note=0x83FC7B9C,
           held_vel=0x83FC7BAC, held_src=0x83FC7BBC)
ENTRIES = ('sgl_param', 'sgl_level_get', 'sgl_midi_gate', 'sgl_midi_velocity')
EXPORTS = ENTRIES + ('sgl_level', 'sgl_vel', 'sgl_notes', 'sgl_sets')
# (address, the parent's instructions, the entry that replaces them, what)
PATCHES = [
    (0x0001FF20, ['movw ip, #0xb181', 'movt ip, #0x8353', 'bx ip'], 'sgl_param',
     'SetParam\'s Sound Generator call (0x800dd27a: blx 0x1ff21, r1 setting, r2 value, r3 flags), a jump to v9.5\'s '
     'parameter engine 0x8353b181 -> sgl_param: LEVEL\'s value kept, then on to the engine'),
    (0x80020480, ['ldr.w r0, [r0, #0x198]', 'movw r1, #0x851f', 'movt r1, #0x51eb'], 'sgl_level_get',
     'the Sound Generator getter\'s LEVEL case (tbb 0x8002045a, setting 0x7d: the singleton\'s +0x198 / 100) -> '
     'sgl_level_get, LEVEL as it was set (it returns with bx lr, as the case did)'),
    (0x83FA3448, ['push.w {r4, r5, r6, r7, r8, sb, lr}', 'sub sp, #4', 'movw r6, #0x58e0'], 'sgl_midi_gate',
     'arp_midi_event\'s first three instructions (self, note, velocity, r3) -> sgl_midi_gate: a melodic note-on\'s '
     'velocity x LEVEL / 127, then those three instructions and on at 0x83fa3452'),
]
RESUME = (0x83FA3452, ['mov r4, r1', 'movt r6, #0x83fc'])      # arp_midi_event goes on: r6 = &kit_mode
# Stock 5.52, v9.5 and kit-stage code the module relies on, as in combined-test17: (start, end, SHA-256, what).
GUARDS = [
    (0x800DD0C0, 0x800DD0FA, '42f278bf8c918dd012e9defd6c7f186b599306f6bf3032d61a2448d1c389d85d',
     'SetParam (settings, id, value, flags): r8 = the setting, r6 = the value clamped to its range, r7 = the flags'),
    (0x800DD26C, 0x800DD27E, '6aec15148843fa613520dfdd8971949305810180a736e94bca0dd66dfcf9bbb6',
     'its case for the Sound Generator\'s settings 0x7a..0x82: blx 0x1ff21 with r1 = r8, r2 = r6, r3 = r7'),
    (0x0001FF20, 0x0001FF2A, 'aca1fc4078939842a3ec571898e639a5690d41f7172ffe3cbec99908a3fdce14',
     'the jump there to v9.5\'s parameter engine (patched)'),
    (0x8353B180, 0x8353B1F8, '2160e1e9c673884422873804b988a56f58f17acae133416c70df0372485f70b7',
     'v9.5\'s parameter engine: FREQ to freq_event; else the stock setter on the singleton, then TYPE, LEVEL, DUTY, '
     'BALANCE, TUNE and ENV on the three clones'),
    (0x80019E30, 0x8001A010, '89c6ffbcb80faef2613f9ab62cc07e55c8497e5ec81dd58cd88bb373f4b260ca',
     'the stock setter: LEVEL (0x80019ee4) sets the voice\'s +0x198 to value x 100, and +0x74 when it is idle'),
    (0x80020450, 0x80020498, '825fa6bfbad3acdc22e892388ca152a53d7675f65e4840002d566c12be509bee',
     'the stock getter: tbb on setting - 0x7a, LEVEL\'s case at 0x80020480 alone (+0x198 / 100; patched)'),
    (0x800D965C, 0x800D966C, '20ef3d7b8e9f1c17e3689f8a412340aad7b5a34b5b680e7a42c4b1e0c638c320',
     'GetParam\'s case for the settings 0x7a..0x82: that getter on the singleton 0x80249800, its only caller'),
    (0x8005A680, 0x8005A6A6, 'e0de836480b9eb761f382b75eef26101db41f045e91f00a12a30aae2f5e6e90f',
     'the channel-16 note handler (M.CH 16): on the SG page, arp_midi_event (page, note, velocity, off)'),
    (0x80132118, 0x8013227C, 'd6e6207cd08e89b07e4a92722a8e08223d6ba736d65e96caa957bd675693a80a',
     'the stock MIDI note-on (v9.5\'s midi_event, ARP off): the voice\'s level = velocity x 100'),
    (0x0001CBCC, 0x0001CBE2, '7a667917bd2242d0b2d5f9ce9756d683f7920f1b287e307f9c1ca50e9f9ff946',
     'the render loop: a voice\'s level (+0x74) moves to +0x198 one step a sample'),
    (0x8015C0C8, 0x8015C134, '9f35ff8e3e202fdd6640a9dcbb103734df80416158508040dac239fde227707d',
     'the SG page\'s pad: with FIXED VELOCITY (project setting 0xdb) on, its velocity is GetParam(0x7d), LEVEL'),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def kit_module(rt):
    """The kit stage's module as it boots, with the kit footer's byte put back: it must be v9.46's."""
    dense = bytearray(rt.read(KIT_BASE, KIT_END - KIT_BASE))
    at, stock, footer = KIT_FOOTER
    if dense[at - KIT_BASE] not in (stock, footer):
        raise ValueError(f'{at:#x}: neither the kit footer\'s byte nor the kit stage\'s')
    dense[at - KIT_BASE] = stock
    return bytes(dense)


def branches_into(img, spans):
    """Direct branches (b, bl, cbz, ...) in the copy rows' bytes whose target is inside a span, past its start."""
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    md.skipdata = True
    hits = []
    for load, dst, n, fn in scatter(img):
        if fn != COPY or not n:
            continue
        blob = img[load - FLASH:load - FLASH + n]
        for ins in md.disasm(blob, dst):
            if not ins.mnemonic.startswith(('b', 'cb')) or not ins.op_str.split(', ')[-1].startswith('#'):
                continue
            target = int(ins.op_str.split('#')[-1], 16)
            for start, end in spans:
                if start < target < end:
                    hits.append((ins.address, ins.mnemonic, target))
    return hits


def compile_module(folder: Path, zig: Path, base: int):
    folder.mkdir(parents=True, exist_ok=True)
    if subprocess.check_output([str(zig), 'version'], text=True).strip() != '0.13.0':
        raise ValueError('needs Zig 0.13.0')
    resume = RESUME[0] | 1
    links = (f'#define KIT_MODE_ADDR {KIT["kit_mode"]:#x}u\n#define HELD_COUNT_ADDR {KIT["held_count"]:#x}u\n'
             f'#define HELD_NOTE_ADDR {KIT["held_note"]:#x}u\n#define HELD_VEL_ADDR {KIT["held_vel"]:#x}u\n'
             f'#define HELD_SRC_ADDR {KIT["held_src"]:#x}u\n#define KIT_MODE_LO {KIT["kit_mode"] & 0xFFFF:#x}\n'
             f'#define MIDI_RESUME_LO {resume & 0xFFFF:#x}\n#define MIDI_RESUME_HI {resume >> 16:#x}\n')
    (folder / 'sgl_links.h').write_text(links, encoding='ascii', newline='\n')
    keep = ' '.join(f'KEEP(*(.text.{n}))' for n in ENTRIES)
    (folder / 'sg_level.ld').write_text(f'''ENTRY(sgl_param)
SECTIONS {{
 . = {base:#x};
 .text : {{ {keep} *(.text*) }}
 .rodata : ALIGN(16) {{ *(.rodata*) }}
 .data : ALIGN(16) {{ *(.data*) }}
 .bss : ALIGN(16) {{ *(.bss*) *(COMMON) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) }}
}}
''', encoding='ascii', newline='\n')
    source = folder / 'sg_level.c'              # compile LF-normalized source
    source.write_bytes((HERE / 'sg_level.c').read_bytes().replace(b'\r\n', b'\n'))
    cache = folder / 'cache'
    env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(cache), ZIG_LOCAL_CACHE_DIR=str(cache))
    # -g only keeps the symbol table (Zig's -Os strips it otherwise); --no-gc-sections keeps every export.
    subprocess.run([str(zig), 'cc', '-target', 'thumb-freestanding-eabihf', '-mcpu=cortex_m7+vfp4d16',
                    '-mfloat-abi=hard', '-Os', '-g', '-ffunction-sections', '-fdata-sections', '-nostdlib',
                    '-fno-builtin', '-Wall', '-Werror', '-I', str(folder), '-Wl,--no-undefined', '-Wl,--build-id=none',
                    '-Wl,--no-gc-sections', '-Wl,-e,sgl_param', '-Wl,-T,' + str(folder / 'sg_level.ld'),
                    str(source), '-o', str(folder / 'sg_level.elf')], check=True, env=env)
    code, symbols = read_module((folder / 'sg_level.elf').read_bytes(), base, base + SLOT)
    missing = [n for n in EXPORTS if n not in symbols]
    if missing:
        raise ValueError(f'module exports missing: {missing}')
    for name in ENTRIES:
        if not symbols[name] & 1:
            raise ValueError(f'{name} is not a Thumb function symbol')
    if code[symbols['sgl_level'] - base] != 127:
        raise ValueError('sgl_level does not start at 127')
    return code, {n: symbols[n] for n in EXPORTS}, sha(source.read_bytes()), links


def build(inp: Path, out: Path, zig: Path, revision: str, kits: Path = None, build_dir: Path = None):
    img = bytearray(inp.read_bytes())
    app0 = inp.with_name('SP404MKII_APP0.bin')
    if sha(app0.read_bytes()) != APP0_SHA:
        raise ValueError('expected stock APP0 beside the input APP1')
    for name in ('SP404MKII_APP1.bin', 'SP404MKII_APP0.bin', 'manifest.json'):
        if (out / name).exists():
            raise ValueError(f'refusing to overwrite {out / name}')
    if kits:
        symbols = json.loads(kits.read_text(encoding='utf-8'))['arp_symbols']
        for name, addr in KIT.items():
            if symbols.get(name) != addr:
                raise ValueError(f'{name}: the kits manifest has {symbols.get(name)}, not {addr:#x}')
    rt = Runtime(img)
    for start, end, digest, what in GUARDS:
        if sha(rt.read(start, end - start)) != digest:
            raise ValueError(f'{start:#x}..{end:#x} differs from what the module relies on ({what})')
    if sha(kit_module(rt)) != KIT_MODULE_SHA:
        raise ValueError('the kit stage is not v9.46\'s module as booted (the kit footer\'s byte aside)')
    sites = []
    for addr, old, entry, what in PATCHES:
        n = sum(len(i.bytes) for i in capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
                .disasm(rt.read(addr, 16), addr, len(old)))
        if listing(rt.read(addr, n), addr) != old:
            raise ValueError(f'{addr:#x}: expected {old} ({what})')
        sites.append((addr, n))
    if listing(rt.read(RESUME[0], 6), RESUME[0]) != RESUME[1]:
        raise ValueError(f'{RESUME[0]:#x}: expected {RESUME[1]} (arp_midi_event after its first three instructions)')
    hits = branches_into(bytes(img), [(a, a + n) for a, n in sites])
    if hits:
        raise ValueError(f'branches into a patched span: {[(hex(a), m, hex(t)) for a, m, t in hits[:6]]}')
    rows = scatter(img)
    if not any(dst == SCALES_ROW and dst + size <= BASE for load, dst, size, fn in rows):
        raise ValueError(f'expected v9.6\'s scale module row at {SCALES_ROW:#x}, ending below {BASE:#x}')
    if not any(dst == KIT_BASE for load, dst, size, fn in rows) or BASE + SLOT > KIT_BASE:
        raise ValueError(f'expected the kit stage\'s row at {KIT_BASE:#x}, above the slot')
    for load, dst, size, fn in rows:
        if max(dst, BASE) < min(dst + size, BASE + SLOT):
            raise ValueError(f'row {dst:#x}+{size:#x} overlaps the slot {BASE:#x}..{BASE + SLOT:#x}')
    refs = refs_into(bytes(img), BASE, BASE + SLOT)
    if refs:
        raise ValueError(f'input refers to the slot: {refs[:4]}')

    folder = build_dir or out / 'build'
    module, symbols, source_sha, links = compile_module(folder, zig, BASE)
    if len(module) > SLOT:
        raise ValueError(f'module ({len(module)} bytes) exceeds the slot')

    patches = []
    parent_sha = sha(img)
    for (addr, old, entry, what), (_, n) in zip(PATCHES, sites):
        new = checked_asm(jump(symbols[entry]) + 'nop\n' * ((n - 10) // 2), addr)
        if len(new) != n:
            raise ValueError(f'{addr:#x}: patch is {len(new)} bytes, the span {n}')
        off = file_offset(img, addr, n)
        original = bytes(img[off:off + n])
        img[off:off + n] = new
        patches.append(dict(address=addr, size=n, original=old, original_hex=original.hex(),
                            replacement_hex=new.hex(), entry=entry, target=symbols[entry], what=what))
    file_at = (len(img) + 15) & ~15
    img += bytes(file_at - len(img)) + module
    table = (len(img) + 15) & ~15
    img += bytes(table - len(img))
    for row in rows + [[FLASH + file_at, BASE, len(module), COPY]]:
        img += struct.pack('<4I', *row)
    struct.pack_into('<2I', img, 0x80, table - 0x80, len(img) - 0x80)
    if FLASH + len(img) > 0x60400000:
        raise ValueError('APP1 reaches the end of the 4 MB flash')
    after = Runtime(img)
    if after.read(BASE, len(module)) != module:
        raise ValueError('the new image does not reproduce the module')
    for p in patches:
        if after.read(p['address'], p['size']).hex() != p['replacement_hex']:
            raise ValueError(f'the new image does not hold the patch at {p["address"]:#x}')
    for start, end, digest, what in GUARDS:            # every guard, with this step's patches put back
        got = bytearray(after.read(start, end - start))
        for p in patches:
            lo, hi = max(start, p['address']), min(end, p['address'] + p['size'])
            if lo < hi:
                got[lo - start:hi - start] = bytes.fromhex(p['original_hex'])[lo - p['address']:hi - p['address']]
        if sha(got) != digest:
            raise AssertionError(f'{start:#x}..{end:#x}: more than this step\'s patches changed')

    out.mkdir(parents=True, exist_ok=True)
    (out / 'SP404MKII_APP1.bin').write_bytes(img)
    shutil.copy2(app0, out / 'SP404MKII_APP0.bin')
    parent_manifest = inp.with_name('manifest.json')
    manifest = dict(
        revision=revision, status='hardware-unverified', published=False,
        description='LEVEL (CTRL 3, CC 72) is a value of its own and turns down the Sound Generator\'s MIDI notes: a '
                    'melodic note-on plays at velocity x LEVEL / 127 (at least 1), ARP on or off, either M.CH route; '
                    'LEVEL 127 is as before. The LEVEL shown and saved is the LEVEL set, not the last note\'s velocity; '
                    'keys the arp holds from MIDI follow a LEVEL change. Drum mode and the pads are as before (pads '
                    'with FIXED VELOCITY on play at LEVEL, as stock). The rest of the parent as it was',
        module_revision=REVISION,
        parent_app1=str(inp), parent_sha256=parent_sha,
        parent_revision=json.loads(parent_manifest.read_text(encoding='utf-8')).get('revision')
        if parent_manifest.exists() else None,
        sha256=sha(img), size=len(img), app0_sha256=APP0_SHA,
        slot=[BASE, BASE + SLOT], blob_base=BASE, blob_file_offset=file_at, blob_size=len(module),
        blob_sha256=sha(module), source='synth/sg_level.c', source_sha256=source_sha, links=links,
        compiler='zig 0.13.0 cc -Os', entries=symbols, kit_stage=dict(symbols=KIT, module_sha256=KIT_MODULE_SHA,
                                                                       footer_byte=list(KIT_FOOTER)),
        patches=patches, guards=[dict(start=s, end=e, sha256=d, establishes=w) for s, e, d, w in GUARDS],
        inside_guards=[dict(
            guard=[KIT_BASE, KIT_END], guard_of='kits-save (kits-save-test2)', patch=0x83FA3448,
            why='kits save checks the kit stage whole, as booted, for the addresses it uses (the kit pads, KIT_MODE, '
                'the arp\'s settings and held list, kit_init_pads, the menu functions); the patch moves none of them '
                'and kits save never calls arp_midi_event. The kit footer\'s byte (0x83fbaf36) is in the same guard')],
        tool='synth/build_sg_level.py')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    sums = ''.join(f'{sha((out / n).read_bytes())}  {n}\n' for n in ('SP404MKII_APP0.bin', 'SP404MKII_APP1.bin',
                                                                       'manifest.json'))
    (out / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('app1', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--zig', type=Path, required=True)
    ap.add_argument('--kits', type=Path, help='the v9.46 kits manifest, to check the kit symbols against')
    ap.add_argument('--revision', default=REVISION)
    ap.add_argument('--build-dir', type=Path)
    a = ap.parse_args()
    m = build(a.app1.resolve(), a.out.resolve(), a.zig.resolve(), a.revision, a.kits.resolve() if a.kits else None,
              a.build_dir.resolve() if a.build_dir else None)
    print(json.dumps({k: m[k] for k in ('revision', 'sha256', 'size', 'blob_base', 'blob_size')}, indent=1))


if __name__ == '__main__':
    main()
