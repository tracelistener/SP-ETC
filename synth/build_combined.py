"""combined-test20: the fork's latest feature test builds in one APP1 (combined-test17's chain with FX deep edit test15:
the hidden settings on every page, the Sound Generator page and page 34 (REMAIN + FX on an unlit effect) too; then the
fast boot, the kit footer and the SG level step as for combined-test19).

Each feature's own builder runs in turn on the output of the one before, from bounce-3-test9's parent (the
published v9.46's kit stage plus the RESAMPLE start fix v3, resample-startfix-3):

  1 bounce in place, stage 3   build_bounce.py            0x83FE8000   as in bounce-3-test9
  2 FX deep edit               build_fx_deep_edit.py      0x83FE2000   fx-deep-edit-test15
  3 pad envelopes, stage 1     build_pad_env.py           0x83FDE000   pad-env-test6's stage 1
  4 pad envelopes, stage 2     build_pad_pitch_filter.py  0x83FD9000   pad-env-test6
  5 kit edits saved            build_kits_save.py         0x83FD5000   kits-save-test2
  6 note repeat                build_note_repeat.py       0x83FDC000   note-repeat-test6
  7 chromatic scales           build_chroma.py            0x83FD7000   chroma-test2
  8 SUB PAD on the SG page     build_sg_subpad.py         0x83FD4000   sg-subpad-test1

Each module has to come out byte for byte as in its own test build (its blob SHA-256), and step 1 as
bounce-3-test9's APP1. The FX probe stays out: it used the TOP vtable slot FX deep edit takes. The fast boot
(build_fast_boot.py) goes on top of the result as it did for combined-test3.

Each builder checks the code it relies on byte for byte (its guards), so it runs before the builders that
patch inside them: FX deep edit and pad envelopes guard the UI dispatcher note repeat bridges, note repeat
the pad-event consumer and the pattern recorder chroma bridges. One pair guards each other's site: note
repeat the pad-event dispatcher 0x800bef10 bounce bridges, bounce the pad note 0x800cdbd0 note repeat
bridges. Bounce goes first (its builder keeps APP1 below the kit PCM planning boundary, which the later
modules cross, as pad-env-test5 does), so note repeat's builder gets its input with bounce's ten bytes at
0x800bef10 put back to stock, and its output gets them again (FOREIGN).

SHARED says why each such guard still holds with the other feature's hook in place. check_combined checks
every step's patches, guards, table guards and module bytes on the final image; a guard spanning another
feature's patch passes only where SHARED lists the pair, and only with that patch's bytes put back to stock.

usage: python synth/build_combined.py PARENT_DIR OUT_DIR --zig ZIG --fxmap FXMAP --refs RELEASE_DIR
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from build_arp import file_offset
from build_kits_save import Runtime

HERE = Path(__file__).resolve().parent
REVISION = 'combined-test20'
FLASH = 0x60080000
PCM_BANK, FLASH_LIMIT = 0x60376000, 0x60400000   # kits/build_arp_kit.py: kit PCM bank, flash planning limit
APP0_SHA = '3e35ff30137f741a715566e205384f9b434ca7ac3847e247bad3f0c9c8a2bd23'
PARENT_SHA = '7d13c1e26d222cea7cada8b6b8ac986b432bf1b32508b5f39ac9c6c117ea61cc'     # resample-startfix-3
NAMES = ('SP404MKII_APP0.bin', 'SP404MKII_APP1.bin', 'manifest.json')
# (step, builder, the feature's own test build, where its manifest keeps this module)
STEPS = [
    ('bounce', 'build_bounce.py', 'bounce-3-test9', None),
    ('fx-deep-edit', 'build_fx_deep_edit.py', 'fx-deep-edit-test15', None),
    ('pad-env-1', 'build_pad_env.py', 'pad-env-test6', 'stage1'),
    ('pad-env-2', 'build_pad_pitch_filter.py', 'pad-env-test6', None),
    ('kits-save', 'build_kits_save.py', 'kits-save-test2', None),
    ('note-repeat', 'build_note_repeat.py', 'note-repeat-test6', None),
    ('chroma', 'build_chroma.py', 'chroma-test2', None),
    ('sg-subpad', 'build_sg_subpad.py', 'sg-subpad-test1', None),
]
FOREIGN = {'note-repeat': [('bounce', 0x800BEF10)]}
DISPATCHER = ('note repeat\'s entry takes VALUE (press and release) only while ROLL is held and VALUE turns only '
              'while ROLL is held or latched with a pad repeating (in chromatic mode not with VALUE held); every '
              'other event goes on to the stock dispatcher, which sets and clears the held bits and calls the page '
              'as before')
# (the feature whose patch it is, its site, the feature whose guard spans it) -> why that guard's reason holds
SHARED = {
    ('bounce', 0x800BEF10, 'note-repeat'):
        'bounce\'s gate hands every event on to the ring as stock unless a bounce owns the recorder, when it drops '
        'note-ons but its own trigger: repeats are dropped during a take like any other pad',
    ('note-repeat', 0x800CDBD0, 'bounce'):
        'note repeat\'s pad note acts only for the stock pad handler\'s press and HOLD let-go callers; bounce\'s '
        'trigger (F_TRIGGER, from its own code) goes straight on to the stock body',
    ('note-repeat', 0x8003B530, 'fx-deep-edit'): DISPATCHER + '; EXIT + VALUE on TOP reaches fde_filter',
    ('note-repeat', 0x8003B530, 'pad-env-1'): DISPATCHER + '; the ENVELOPE page\'s keys (SHIFT, DEL) are not taken',
    ('chroma', 0x80050E78, 'note-repeat'):
        'chroma\'s note-off reads the stored note signed (scale notes below the stock range); the consumer still '
        'gives a type-4 note to the recorder, then plays or lets it go',
    ('chroma', 0x800BD644, 'note-repeat'):
        'chroma_record records a pad note with its note byte and goes on with the recorder: a repeat is recorded '
        'as a tap, with chroma\'s note',
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def patches_of(man):
    seen, out = set(), []
    for p in man.get('patches', []) + man.get('data_patches', []):
        if p['address'] not in seen:
            seen.add(p['address'])
            out.append(p)
    return out


def blob_of(step_dir, man):
    img = (step_dir / 'SP404MKII_APP1.bin').read_bytes()
    return img[man['blob_file_offset']:man['blob_file_offset'] + man['blob_size']]


def put_back(img, patches, which):
    """Each patch's original bytes (which='original_hex') or its replacement, checking the other is there."""
    other = 'replacement_hex' if which == 'original_hex' else 'original_hex'
    for p in patches:
        off = file_offset(img, p['address'], p['size'])
        if img[off:off + p['size']].hex() != p[other]:
            raise ValueError(f'{p["address"]:#x}: expected {p[other]}, found {img[off:off + p["size"]].hex()}')
        img[off:off + p['size']] = bytes.fromhex(p[which])


def run_step(name, builder, inp, out, zig, fxmap, done):
    view = None
    if name in FOREIGN:
        foreign = [p for owner, at in FOREIGN[name] for p in patches_of(done[owner]['manifest']) if p['address'] == at]
        view = out.with_name(out.name + '-input')
        view.mkdir(parents=True)
        img = bytearray((inp / 'SP404MKII_APP1.bin').read_bytes())
        put_back(img, foreign, 'original_hex')
        (view / 'SP404MKII_APP1.bin').write_bytes(img)
        for n in ('SP404MKII_APP0.bin', 'manifest.json'):
            shutil.copy2(inp / n, view / n)
    args = [sys.executable, str(HERE / builder), str((view or inp) / 'SP404MKII_APP1.bin'), str(out), '--zig', str(zig)]
    if name == 'fx-deep-edit':
        args += ['--fxmap', str(fxmap)]
    if subprocess.run(args, cwd=HERE, env=os.environ).returncode:
        raise ValueError(f'{builder} failed')
    man = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    if view:
        img = bytearray((out / 'SP404MKII_APP1.bin').read_bytes())
        put_back(img, foreign, 'replacement_hex')
        (out / 'SP404MKII_APP1.bin').write_bytes(img)
        parent = (inp / 'SP404MKII_APP1.bin').read_bytes()
        man.update(parent_app1=str(inp / 'SP404MKII_APP1.bin'), parent_sha256=sha(parent), sha256=sha(img),
                   size=len(img), combined_foreign=[dict(owner=owner, address=at) for owner, at in FOREIGN[name]],
                   combined_note=f'the builder checked {view}, the parent with those patches put back to stock; '
                                 f'this output has them again')
        (out / 'manifest.json').write_text(json.dumps(man, indent=2) + '\n', encoding='utf-8', newline='\n')
        sums = ''.join(f'{sha((out / n).read_bytes())}  {n}\n' for n in NAMES)
        (out / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
    return man


class Image(Runtime):
    """Runtime bytes, and flash (DOOM OS's code runs in place) as the file has it."""

    def read(self, addr, n):
        if FLASH <= addr and addr + n <= FLASH + len(self.img):
            return self.img[addr - FLASH:addr - FLASH + n]
        return super().read(addr, n)


def check_combined(img, steps):
    """Every step's patches, guards, table guards and module bytes on the final image: (failures, shared)."""
    rt = Image(img)
    patches = [(s['name'], p) for s in steps for p in patches_of(s['manifest'])]
    bad, shared = [], []
    for name, p in patches:
        if rt.read(p['address'], p['size']).hex() != p['replacement_hex']:
            bad.append(f'{name}: the patch at {p["address"]:#x} is not in place')
    for s in steps:
        for g in s['manifest'].get('guards', []):
            a, e = g['start'], g['end']
            got = bytearray(rt.read(a, e - a))
            if sha(got) == g['sha256']:
                continue
            inside = [(n, p) for n, p in patches if max(a, p['address']) < min(e, p['address'] + p['size'])]
            for n, p in inside:                   # its own patches, and other features' hooks
                lo, hi = max(a, p['address']), min(e, p['address'] + p['size'])
                got[lo - a:hi - a] = bytes.fromhex(p['original_hex'])[lo - p['address']:hi - p['address']]
            keys = [(n, p['address'], s['name']) for n, p in inside if n != s['name']]
            if inside and sha(got) == g['sha256'] and all(k in SHARED for k in keys):
                if keys:
                    shared.append(dict(guard=[a, e], guard_of=s['name'], establishes=g.get('establishes'),
                                       hooks=[dict(of=n, address=at, why=SHARED[(n, at, s['name'])])
                                              for n, at, _ in keys]))
            else:
                bad.append(f'{s["name"]}: the guard {a:#x}..{e:#x} fails ({(g.get("establishes") or "")[:70]}; '
                           f'inside it: {[(n, hex(p["address"])) for n, p in inside]})')
        for t in s['manifest'].get('table_guards', []):
            if struct.unpack('<H', rt.read(t['address'], 2))[0] != t['value']:     # TBH entries
                bad.append(f'{s["name"]}: the table guard at {t["address"]:#x} fails')
        m = s['manifest']
        want = bytearray(s['blob'])
        for n, p in patches:                  # later modules' links into this one (stage 2 into stage 1)
            at = p['address'] - m['blob_base']
            if n != s['name'] and 0 <= at and at + p['size'] <= len(want):
                want[at:at + p['size']] = bytes.fromhex(p['replacement_hex'])
        if rt.read(m['blob_base'], m['blob_size']) != want:
            bad.append(f'{s["name"]}: the module at {m["blob_base"]:#x} is not its build\'s bytes')
    slots = sorted((s['manifest']['slot'][0], s['manifest']['slot'][1], s['name']) for s in steps)
    for (a, b, x), (c, d, y) in zip(slots, slots[1:]):
        if c < b:
            bad.append(f'the slots of {x} and {y} overlap')
    return bad, shared


def build(parent: Path, out: Path, zig: Path, fxmap: Path, refs: Path):
    if sha((parent / 'SP404MKII_APP1.bin').read_bytes()) != PARENT_SHA:
        raise ValueError('expected resample-startfix-3 (bounce-3-test7\'s parent) as the parent APP1')
    if sha((parent / 'SP404MKII_APP0.bin').read_bytes()) != APP0_SHA:
        raise ValueError('expected stock APP0 beside the parent APP1')
    for n in NAMES:
        if (out / n).exists():
            raise ValueError(f'refusing to overwrite {out / n}')
    work = out.with_name(out.name + '-steps')
    if work.exists():
        raise ValueError(f'refusing to reuse {work}')
    done, steps, inp = {}, [], parent
    for i, (name, builder, ref, key) in enumerate(STEPS, 1):
        step_dir = work / f'{i}-{name}'
        man = run_step(name, builder, inp, step_dir, zig, fxmap, done)
        ref_man = json.loads((refs / ref / 'manifest.json').read_text(encoding='utf-8'))
        ref_blob = (ref_man[key] if key else ref_man)['blob_sha256']
        blob = blob_of(step_dir, man)
        if sha(blob) != ref_blob or man['blob_sha256'] != ref_blob:
            raise ValueError(f'{name}: the module is not {ref}\'s ({sha(blob)} against {ref_blob})')
        if name == 'bounce' and man['sha256'] != ref_man['sha256']:
            raise ValueError(f'step 1 is not {ref}\'s APP1 ({man["sha256"]})')
        done[name] = step = dict(name=name, builder=builder, reference=ref, dir=step_dir, manifest=man, blob=blob)
        steps.append(step)
        inp = step_dir
    img = (inp / 'SP404MKII_APP1.bin').read_bytes()
    bad, shared = check_combined(img, steps)
    if bad:
        raise ValueError('the combined image fails:\n  ' + '\n  '.join(bad))
    if FLASH + len(img) > FLASH_LIMIT:
        raise ValueError(f'APP1 reaches the flash planning limit {FLASH_LIMIT:#x}')

    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(inp / 'SP404MKII_APP1.bin', out / 'SP404MKII_APP1.bin')
    shutil.copy2(parent / 'SP404MKII_APP0.bin', out / 'SP404MKII_APP0.bin')
    (out / 'steps').mkdir(exist_ok=True)
    for i, s in enumerate(steps, 1):
        shutil.copy2(s['dir'] / 'manifest.json', out / 'steps' / f'{i}-{s["name"]}.manifest.json')
    manifest = dict(
        revision=REVISION, status='hardware-unverified', published=False,
        description='every latest feature test build in one APP1: bounce in place (bounce-3-test9), FX deep edit '
                    '(fx-deep-edit-test15), pad envelopes stages 1 and 2 (pad-env-test6), kit edits and the Sound '
                    'Generator saved with the project (kits-save-test2), note repeat (note-repeat-test6), chromatic '
                    'scales (chroma-test2) and SUB PAD on the Sound Generator page (sg-subpad-test1), each module '
                    'byte for byte its own build\'s, on the RESAMPLE start fix v3; not the FX probe',
        parent_app1=str(parent / 'SP404MKII_APP1.bin'), parent_sha256=PARENT_SHA, parent_revision='resample-startfix-3',
        sha256=sha(img), size=len(img), app0_sha256=APP0_SHA,
        kit_pcm_planning_boundary=dict(address=PCM_BANK, bytes_over=max(0, FLASH + len(img) - PCM_BANK),
                                       note='crossed, as pad-env-test5 does; nothing is stored there yet'),
        flash_planning_limit=dict(address=FLASH_LIMIT, bytes_left=FLASH_LIMIT - FLASH - len(img)),
        steps=[dict(step=i, feature=s['name'], builder=f'synth/{s["builder"]}', module_as_in=s['reference'],
                    revision=s['manifest']['revision'], slot=s['manifest']['slot'], blob_base=s['manifest']['blob_base'],
                    blob_size=s['manifest']['blob_size'], blob_sha256=s['manifest']['blob_sha256'],
                    blob_file_offset=s['manifest']['blob_file_offset'], patches=len(patches_of(s['manifest'])),
                    guards=len(s['manifest'].get('guards', [])), manifest=f'steps/{i}-{s["name"]}.manifest.json')
               for i, s in enumerate(steps, 1)],
        foreign=dict(note='note repeat\'s builder checked its input with bounce\'s gate at 0x800bef10 put back to '
                          'stock; its output has bounce\'s bytes again', patches=[hex(at) for at in (0x800BEF10,)]),
        shared_hooks=shared,
        left_out=dict(feature='FX probe (fx-probe-test1)', why='FX deep edit uses the same TOP vtable slot 0x8022ce64; '
                      'the probe\'s hardware questions are answered'),
        tool='synth/build_combined.py')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    sums = ''.join(f'{sha((out / n).read_bytes())}  {n}\n' for n in NAMES)
    (out / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('parent', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--zig', type=Path, required=True)
    ap.add_argument('--fxmap', type=Path, required=True)
    ap.add_argument('--refs', type=Path, required=True)
    a = ap.parse_args()
    m = build(a.parent.resolve(), a.out.resolve(), a.zig.resolve(), a.fxmap.resolve(), a.refs.resolve())
    print(json.dumps({k: m[k] for k in ('revision', 'sha256', 'size')}, indent=1))
    print(json.dumps([[s['feature'], hex(s['blob_base']), s['blob_size']] for s in m['steps']]))
    print(f'{len(m["shared_hooks"])} guards span another feature\'s hook (SHARED)')


if __name__ == '__main__':
    main()
