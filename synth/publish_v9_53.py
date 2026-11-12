"""Generate the guarded browser overlay for Sound Generator + Kits v9.53 (MIDI out test 15).

v9.53 is v9.52 with:
- the SG level step (sg-level-test2): LEVEL turns the Sound Generator's MIDI notes down, and the Sound Generator and
  the kits play at about a sample's loudness (COMBINED.md sections 19 and 20; SG_LEVEL.md);
- FX deep edit at fx-deep-edit-test16: the hidden settings on every page; HOLD + MFX switches them off and on, HOLD +
  VALUE opens the input FX's (VALUE + EXT SOURCE is stock's again) (COMBINED.md sections 21 and 22);
- the guitar synth (MIDI out test 15, on combined-test21): a guitar into the SP plays 32 synth sounds, the guitar's
  notes play the Sound Generator and the kits, and those notes go out over MIDI (SY_TEST.md, TUNE_TEST.md).
The user has played the guitar synth's test builds on the unit up to MIDI out test 13 (test 15 = test 14's final 32 sounds, with only VALUE alone stepping OUT on its screen); hardware_verified stays False
until v9.53 itself is.

v9.53 is built in five steps: build_combined.py (every feature branch's module, byte for byte its own test build's,
on resample-startfix-3: the published v9.46's kit stage plus the RESAMPLE start fix v3), build_fast_boot.py,
build_kit_footer.py, build_sg_level.py (combined-test21), then build_tune_test.py (midi-out-test15). The overlay
turns the DOOM OS base into midi-out-test15. Before writing kits-data.js, this script checks:
- the candidate's hash and the five stages' manifests, back to v9.46's kit stage;
- every module's source against this tree (the guitar synth's eight, its builder and its sound table too).

usage: python synth/publish_v9_53.py /path/to/stock/SP404MKII_APP1.bin \
           --combined dev_combined21/combined-test21-base --candidate release/midi-out-test15
"""
import argparse
import base64
import json
from pathlib import Path

import build

RELEASE, REVISION, LABEL = 'v9.53', 'midi-out-test15', '5.52+kits-v9.53'
EXPECTED_SHA, EXPECTED_SIZE = 'faeea5b004273f2dbcfca00387cfcc59078d3ba42fd832d52d363209d8b3b75e', 3239840
SG_LEVEL_SHA = '1d31464916aff9bce8b75765718cc9ca0a5f39d40559801fecea78167deb4406'     # combined-test21
FOOTER_SHA = '973ee28a741fc818e3d6d43ff3336f7057dbe8cf2ef6a8cb7a41c81f24189f53'
FASTBOOT_SHA = '198791d5c32b4b3743a0329fd5fb06bb96ec4869eda93243e5edbd876fde8e37'
COMBINED_SHA = '8618c5c61c339d8e70d33d8141b15bd00a12ade7177628d09753fe273a0b9907'
PARENT_SHA = '7d13c1e26d222cea7cada8b6b8ac986b432bf1b32508b5f39ac9c6c117ea61cc'      # resample-startfix-3
KIT_STAGE_SHA = '88384c3c9760559e721c1a14973ef3a2ced6abf016572b0a73c5dfb0cef492ba'   # v9.46-test3, as in v9.46
SOUND_TABLE, SOUND_TABLE_SHA = 'synth/tunetest/sy_final.py', \
    'dcf55388ac5504d2906b33c4b35fc491048f91204cf39c79fe08c7734d221498'   # the 32 sounds (not in the module's manifest)
STEPS = ['bounce', 'fx-deep-edit', 'pad-env-1', 'pad-env-2', 'kits-save', 'note-repeat', 'chroma', 'sg-subpad']
KITS = ['TR808', 'DR110', 'KPR77', 'UDS', 'FM', 'TR909', 'TR606', 'SDS-V', 'MP-7', 'CR78', 'CR8K', 'TR707', 'TR727']
FEATURES = ['bounce in place', 'pad envelopes', 'note repeat', 'chromatic scales', 'kit edits saved',
            'Sound Generator settings saved', 'an arpeggiator for each mode', 'FX deep edit', 'SUB PAD on the Sound '
            'Generator', 'fast boot', 'RESAMPLE start fix v3', 'LEVEL for the Sound Generator\'s MIDI notes',
            'a guitar synth', 'guitar notes on the Sound Generator and the kits', 'MIDI out']


def text_sha(path):
    return build.sha(path.read_text(encoding='utf-8').encode())


def stage(app1_path, sha, tool, parent, patches=None):
    """A stage's manifest beside its APP1: its hash, tool, parent and (if given) patch addresses."""
    m = json.loads(Path(app1_path).with_name('manifest.json').read_text(encoding='utf-8'))
    if (m['sha256'] != sha or m['tool'] != tool or m['parent_sha256'] != parent or
            (patches is not None and [x['address'] for x in m['patches']] != patches)):
        raise ValueError(f'unexpected {tool} stage metadata')
    return m


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('stock', type=Path)
    p.add_argument('--combined', type=Path, required=True, help='the combined build: APP1, manifest.json, steps/')
    p.add_argument('--candidate', type=Path, required=True, help='midi-out-test15: APP1 and manifest.json')
    a = p.parse_args()
    stock = a.stock.read_bytes()
    build.require_hash(stock, build.v2.STOCK_SHA256, 'stock APP1')
    build.require_hash(a.stock.with_name('SP404MKII_APP0.bin').read_bytes(), build.APP0_SHA, 'stock APP0')

    # 5. The guitar synth (build_tune_test.py) on combined-test21: its eight sources, builder and sound table.
    image = (a.candidate / 'SP404MKII_APP1.bin').read_bytes()
    build.require_hash(image, EXPECTED_SHA, 'v9.53 APP1')
    synth = stage(a.candidate / 'SP404MKII_APP1.bin', EXPECTED_SHA, 'synth/build_tune_test.py', SG_LEVEL_SHA)
    if len(image) != EXPECTED_SIZE or synth['revision'] != REVISION or synth['parent_revision'] != 'combined-test21':
        raise ValueError('unexpected guitar synth stage metadata')
    for rel, want in synth['source_sha256'].items():
        build.require_hash((build.REPO / 'synth' / rel.replace('\\', '/')).read_text(encoding='utf-8').encode(), want,
                           rel)
    build.require_hash((build.REPO / synth['tool']).read_text(encoding='utf-8').encode(), synth['tool_sha256'],
                       synth['tool'])
    if text_sha(build.REPO / SOUND_TABLE) != SOUND_TABLE_SHA:
        raise ValueError(f'{SOUND_TABLE} is not the sound table v9.53 was built with')

    # 4. The SG level step (build_sg_level.py), 3. the kit footer, 2. the fast boot.
    level = stage(synth['parent_app1'], SG_LEVEL_SHA, 'synth/build_sg_level.py', FOOTER_SHA)
    if level['revision'] != 'combined-test21' or level['module_revision'] != 'sg-level-test2':
        raise ValueError('unexpected SG level stage metadata')
    build.require_hash((build.REPO / level['source']).read_text(encoding='utf-8').encode(), level['source_sha256'],
                       level['source'])
    footer = stage(level['parent_app1'], FOOTER_SHA, 'synth/build_kit_footer.py', FASTBOOT_SHA, [0x83FBAF36])
    stage(footer['parent_app1'], FASTBOOT_SHA, 'synth/build_fast_boot.py', COMBINED_SHA, [0x8013DCAA])

    # 1. The combined build: every step's manifest and source.
    combined = json.loads((a.combined / 'manifest.json').read_text(encoding='utf-8'))
    build.require_hash((a.combined / 'SP404MKII_APP1.bin').read_bytes(), COMBINED_SHA, 'combined build APP1')
    if (combined['sha256'] != COMBINED_SHA or combined['parent_sha256'] != PARENT_SHA or
            combined['tool'] != 'synth/build_combined.py' or [s['feature'] for s in combined['steps']] != STEPS):
        raise ValueError('unexpected combined stage metadata')
    for i, step in enumerate(combined['steps'], 1):
        m = json.loads((a.combined / step['manifest']).read_text(encoding='utf-8'))
        if m['blob_sha256'] != step['blob_sha256'] or (i == 1 and m['parent_sha256'] != PARENT_SHA):
            raise ValueError(f'step {i} ({step["feature"]}): its manifest is not the combined one\'s')
        build.require_hash((build.REPO / m['source']).read_text(encoding='utf-8').encode(), m['source_sha256'],
                           m['source'])
    start_fix = json.loads((a.combined / 'steps' / '1-bounce.manifest.json').read_text(encoding='utf-8'))
    if start_fix['parent_revision'] != 'resample-startfix-3':
        raise ValueError('bounce is not on resample-startfix-3')
    parent_manifest = Path(combined['parent_app1']).with_name('manifest.json')
    if parent_manifest.exists():
        pm = json.loads(parent_manifest.read_text(encoding='utf-8'))
        if pm['sha256'] != PARENT_SHA or pm['parent_sha256'] != KIT_STAGE_SHA:
            raise ValueError('resample-startfix-3 is not on v9.46\'s kit stage')

    base, _ = build.build(stock)
    overlay = build.make_overlay(base, image, LABEL)
    metadata = dict(release=RELEASE, revision=REVISION, sha256=EXPECTED_SHA, size=EXPECTED_SIZE,
                    base_sha256=build.sha(base), combined_sha256=COMBINED_SHA, start_fix='resample-startfix-3',
                    kit_stage_sha256=KIT_STAGE_SHA, kits=KITS, kit_selector_range=[1, 13], synthesis_only=True,
                    features=FEATURES, hardware_verified=False)
    text = '// Generated by synth/publish_v9_53.py. Guarded overlay; no complete firmware.\n'
    text += 'window.DOOMOS_KITS = ' + json.dumps(metadata, sort_keys=True) + ';\n'
    text += 'window.DOOMOS_KITS_PATCH = ' + json.dumps(base64.b64encode(overlay).decode('ascii')) + ';\n'
    (build.REPO / 'kits-data.js').write_text(text, encoding='ascii', newline='\n')
    print('Verified v9.53 overlay:', build.sha(image), f'({len(overlay)} bytes)')


if __name__ == '__main__':
    main()
