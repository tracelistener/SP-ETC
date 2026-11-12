// Test the actual shipped JS applier and page event handlers with a minimal DOM.
// This is not a visual browser test or a device/DOOM OS runtime test.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const root = path.join(__dirname, '..');
const input = process.argv[2];
if (!input) throw new Error('Usage: node synth/test_browser.cjs /path/to/stock/SP404MKII_APP1.bin');
const stock = new Uint8Array(fs.readFileSync(input));
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const KITS_SHA = 'faeea5b004273f2dbcfca00387cfcc59078d3ba42fd832d52d363209d8b3b75e';
const KITS_SIZE = 3239840;

function load(includeKits = true) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, {
      id, checked: false, hidden: false, disabled: false, value: '', listeners: {},
      classList: { add() {}, remove() {} },
      addEventListener(event, fn) { this.listeners[event] = fn; },
      click() {},
    });
    return elements.get(id);
  };
  let start, blob = null;
  const context = vm.createContext({
    window: { addEventListener() {} },
    document: {
      readyState: 'loading',
      addEventListener(event, fn) { if (event === 'DOMContentLoaded') start = fn; },
      querySelectorAll() { return []; },
      getElementById(id) { return get(id); },
    },
    module: { exports: {} },
    setTimeout(fn) { fn(); },
    Blob,
    URL: { createObjectURL(value) { blob = value; return 'blob:test'; }, revokeObjectURL() { blob = null; } },
  });
  if (includeKits) vm.runInContext(fs.readFileSync(path.join(root, 'kits-data.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(root, 'doomos-patcher.js'), 'utf8'), context);
  start();
  return { context, get, api: context.module.exports, blob: () => blob };
}

async function choose(page, bytes, name = 'SP404MKII_APP1.bin') {
  page.get('file').files = [{ name, size: bytes.length, async arrayBuffer() { return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength); } }];
  await page.get('file').listeners.change();
}

async function download(page) {
  return digest(new Uint8Array(await page.blob().arrayBuffer()));
}

(async () => {
  const page = load();
  const { api } = page;
  for (let len = 0; len < 128; len++) {
    const original = Uint8Array.from({ length: len }, (_, i) => (i * 73 + len) & 255);
    assert.equal(Buffer.from(api.fromBase64(Buffer.from(original).toString('base64'))).toString('hex'), Buffer.from(original).toString('hex'));
  }
  assert.equal(api.hex(api.sha256(stock)), digest(stock), 'browser SHA matches Node');

  // The overlays: DOOM OS base from stock 5.52, then v9.53 (midi-out-test15: the combined feature build + fast boot + kit
  // footer + the SG level step (combined-test21), then the guitar synth).
  const kits = page.context.window.DOOMOS_KITS;
  const doom = api.applyPatch(api.fromBase64(page.context.window.DOOMOS_PATCH), stock);
  assert.equal(doom.digest, kits.base_sha256);
  const kitOverlay = api.fromBase64(page.context.window.DOOMOS_KITS_PATCH);
  const kitResult = api.applyPatch(kitOverlay, doom.bytes);
  assert.equal(kitResult.digest, KITS_SHA);
  assert.equal(kitResult.bytes.length, KITS_SIZE);
  assert.equal(kits.sha256, KITS_SHA);
  assert.equal(kits.size, KITS_SIZE);
  assert.equal(kits.release, 'v9.53');
  assert.equal(kits.revision, 'midi-out-test15');
  assert.equal(kits.start_fix, 'resample-startfix-3');
  assert.equal(kits.combined_sha256, '8618c5c61c339d8e70d33d8141b15bd00a12ade7177628d09753fe273a0b9907');
  assert.equal(kits.kit_stage_sha256, '88384c3c9760559e721c1a14973ef3a2ced6abf016572b0a73c5dfb0cef492ba');
  assert.equal(kits.features.length, 15);
  assert.equal(kits.hardware_verified, false);
  assert.equal(JSON.stringify(kits.kit_selector_range), '[1,13]');
  assert.equal(kits.kits.length, 13);
  assert.equal(kits.synthesis_only, true);
  assert.throws(() => api.applyPatch(kitOverlay, stock), /unsupported firmware/);
  const badKit = kitOverlay.slice(); badKit[badKit.length - 1] ^= 1;
  assert.throws(() => api.applyPatch(badKit, doom.bytes), /came out wrong/);

  // One build, no selector: drop in stock, press Patch, get v9.53.
  const panel = page.get('doomos-patcher').innerHTML;
  assert.equal((panel.match(/type="checkbox"/g) || []).length, 0, 'no build selector');
  assert.match(panel, /Builds SP-ETC on DOOM OS 0\.6\.1 \(ED5E\)\./);    // v9.53 (the user): no other version there
  assert.doesNotMatch(panel, /v9\.|Sound Generator \+ Kits/);
  await choose(page, stock);
  assert.equal(page.get('patch').disabled, false);
  await page.get('patch').listeners.click();
  assert.equal(page.get('download').hidden, false);
  assert.equal(await download(page), KITS_SHA);
  assert.match(page.get('status').textContent, /Sound Generator \+ Kits v9\.53 with DOOM OS 0\.6\.1 has been patched into firmware 5\.52\+kits-v9\.53/);

  page.get('reset').listeners.click();
  assert.equal(page.get('download').hidden, true);
  await choose(page, stock);
  await page.get('patch').listeners.click();
  assert.equal(await download(page), KITS_SHA, 'patching again gives the same file');

  page.get('reset').listeners.click();
  await choose(page, kitResult.bytes);
  assert.equal(page.get('patch').disabled, true);
  assert.equal(page.get('download').hidden, true);
  assert.match(page.get('status').textContent, /not a firmware file this patcher knows/);
  await choose(page, new Uint8Array([1, 2, 3]), 'SP404MKII_APP0.bin');
  assert.match(page.get('status').textContent, /This is SP404MKII_APP0.bin/);

  // A failed overlay must never create a downloadable corrupt result.
  const broken = load();
  broken.context.window.DOOMOS_KITS_PATCH = Buffer.from(badKit).toString('base64');
  await choose(broken, stock);
  await broken.get('patch').listeners.click();
  assert.equal(broken.blob(), null);
  assert.equal(broken.get('download').hidden, true);
  assert.match(broken.get('status').textContent, /came out wrong/);

  // Without the kit data the script still makes the DOOM OS base, as upstream does.
  const plain = load(false);
  assert.doesNotMatch(plain.get('doomos-patcher').innerHTML, /Builds SP-ETC/);
  await choose(plain, stock);
  await plain.get('patch').listeners.click();
  assert.equal(await download(plain), doom.digest);
  assert.match(plain.get('status').textContent, /Base build without synth additions/);

  // The page and README.
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  assert.match(html, /kits-data\.js\?v=kits-v9-53-faeea5b0/);
  assert.match(html, /doomos-patcher\.js\?v=sp-etc-v9-53-doom-os"/);
  assert.doesNotMatch(html, /synth-data\.js|waves-data\.js|kits-midi-data|MIDI test guide|v9\.43|v9\.44/);
  assert.doesNotMatch(html, /[Tt]ick one|unticked|Pick one of/);
  // The page is the patcher and what it gives: no version header and no version history (that is on GitHub).
  assert.doesNotMatch(html, /What's new|class="facts"|<dl|class="builds"|v9\.4\d|v9\.5\d/);
  assert.match(html, /href="https:\/\/github\.com\/tracelistener\/SP-ETC\/blob\/main\/CHANGELOG\.md">Version history/);
  // The volume note below the patcher (a user's report on v9.47: the Compressor's MODE was dangerously loud; then the
  // Super Filter), and no NO EXTRA SETTINGS note.
  const note = html.indexOf('class="volume-note"');
  assert.ok(note > html.indexOf('id="doomos-patcher"') && note < html.indexOf('id="features"'), 'the volume note is right below the patcher');
  assert.ok(/Compressor's MODE and the Super Filter's settings\. Both are removed\. Still, keep your volume low/.test(html),
            'the volume note: the Compressor and the Super Filter, removed; keep the volume low');
  assert.ok(readme.includes('Keep your volume low when you try the hidden effect settings'), 'the README warning');
  assert.ok(readme.includes('If you installed v9.47 or v9.48, patch again with v9.53'), 'patch again after v9.47 or v9.48');
  for (const text of [html, readme]) {
    assert.ok(!text.includes('patch again with v9.48') && !text.includes('patch again with v9.49') &&
              !text.includes('patch again with v9.50') && !text.includes('patch again with v9.51') &&
              !text.includes('patch again with v9.52'),
              'no older patch-again line');
    assert.doesNotMatch(text, /says NO EXTRA SETTINGS|some can get loud/);
  }
  assert.ok(readme.includes('**Safety fix:**') && readme.includes('the Super Filter\'s hidden settings are gone') &&
            readme.includes('**Input FX hidden settings:** hold VALUE and press EXT SOURCE') &&
            readme.includes('**ROLL on START/END and PITCH/SPEED:**') && readme.includes('**Stop one roll:**') &&
            readme.includes('**Hidden settings on and off:** hold HOLD and press VALUE') &&
            readme.includes('**Edits kept:**') && readme.includes('**Always there:**'),
            'the README keeps the history');
  // v9.52: the edits are kept over a restart; v9.53: HOLD + MFX switches the hidden settings off and on, HOLD + VALUE
  // opens the input FX's, VALUE + EXT SOURCE is stock's again.
  assert.ok(html.includes('Your edits are kept when you turn the SP off. Hold HOLD and press MFX') &&
            readme.includes('Your edits are kept when you turn the\n  SP off. Hold HOLD and press MFX'),
            'the guide and the README: edits kept, and the switch');
  assert.ok(html.includes('For the input FX: hold HOLD and press VALUE') &&
            html.includes('VALUE + EXT SOURCE switches the input, as on a stock SP') &&
            readme.includes('**Changed buttons:** the hidden effect settings\' switch is now **HOLD +\n  MFX**'),
            'v9.53: the moved buttons on the page and in the README');
  assert.doesNotMatch(html + readme, /reset when you turn the/);
  assert.ok(html.includes('<strong>Stop one pad:</strong> hold EXIT and press a rolling pad') &&
            html.includes('<strong>START/END and PITCH/SPEED:</strong> ROLL works as it normally does there'),
            'the page explains EXIT + pad and ROLL on START/END and PITCH/SPEED');
  for (const q of ['I already have DOOM OS, or an older version of this mod', 'Which file do I need?',
                   'Will I lose my work?', 'What do I need for the guitar synth?']) {
    assert.ok(html.includes(q) && readme.includes(q), 'the page and README answer: ' + q);
  }
  // Every feature, in the cheat sheet below the patcher, with how to reach it.
  const feats = html.slice(html.indexOf('id="features"'), html.indexOf('id="install"'));
  for (const feature of ['Sound Generator', 'Drum kits', 'MIDI', 'Kit to sample bank', 'Bounce in place', 'Pad envelopes',
                         'Note repeat', 'Chromatic scales', 'Hidden effect settings',
                         'Input FX hidden settings', 'Hidden settings on and off', 'DOOM OS 0.6.1', 'Saved with the project', 'Faster start-up',
                         'Cleaner resampling', 'Guitar synth', 'Guitar synth screen', 'Guitar notes', 'MIDI out']) {
    assert.ok(feats.includes('<h4>' + feature + '</h4>'), 'the page lists ' + feature);
  }
  assert.ok(feats.includes('Hold <kbd>HOLD</kbd> and press <kbd>MFX</kbd>') &&
            feats.includes('Hold <kbd>HOLD</kbd> and press <kbd>VALUE</kbd>') &&
            feats.includes('Hold <kbd>HOLD</kbd> and press <kbd>EXT SOURCE</kbd>') &&
            feats.includes('Hold <kbd>VALUE</kbd> and press <kbd>RECORD SETTING</kbd>') &&
            feats.includes('Hold <kbd>REMAIN</kbd> and press <kbd>SUB PAD</kbd>'), 'the cheat sheet gives the buttons');
  assert.ok(!feats.includes('Hold <kbd>VALUE</kbd> and press <kbd>EXT SOURCE</kbd>'), 'VALUE + EXT SOURCE is stock again');
  // v9.53 (the user): SUB PAD on the Sound Generator is not on the page; Always on names DOOM OS's version.
  assert.ok(!feats.includes('SUB PAD on the Sound Generator') &&
            feats.includes("Klangfeld Labs' pattern sequencer (0.6.1, build ED5E)"), 'the cheat sheet: no SUB PAD, DOOM OS 0.6.1');
  for (const feature of ['DOOM OS included', 'Bounce in place', 'Pad envelopes', 'Note repeat', 'Chromatic scales',
                         'Saved with the project', 'SUB PAD on the Sound Generator', 'Hidden effect settings',
                         'Faster start-up', 'Cleaner resampling', 'Guitar synth', 'Guitar notes', 'MIDI out',
                         'A MIDI channel for each mode', 'LEVEL for MIDI notes', 'Quieter Sound Generator and kits',
                         'Hidden effect settings on every screen', 'Changed buttons']) {
    assert.ok(readme.includes('**' + feature + ':**'), 'README lists ' + feature);
  }
  assert.doesNotMatch(html + readme, /reset at power-on|are not saved|returns to 16 at power-on/);
  assert.match(html + readme, /THIRD-PARTY-NOTICES\.md/);
  assert.ok(fs.existsSync(path.join(root, 'THIRD-PARTY-NOTICES.md')), 'the DM-404 notice is in the repository');
  // The three parts and the guides come after the features and the install steps.
  const more = html.indexOf('id="more"');
  assert.ok(more > html.indexOf('id="install"') && more > html.indexOf('id="features"'), 'the details are lower down');
  for (const guide of ['Drum kits', 'MIDI', 'Envelope presets (ENV)', 'Scales and MIDI IN', 'Arpeggiator',
                       'Bounce in place', 'Pad envelopes', 'Note repeat (rolls)', 'Chromatic mode',
                       'Hidden effect settings: the full list', 'Guitar synth: setting up', 'Guitar synth: buttons',
                       'Guitar synth: the screen\'s pages', 'Guitar synth: the 32 sounds', 'Guitar notes and MIDI out']) {
    assert.ok(html.includes('<summary>' + guide + '</summary>'), 'the page has the guide ' + guide);
  }
  for (const fx of ['<strong>Tape Echo:</strong> SYNC, BASS, TREBLE', '<strong>Gt Amp Sim (input FX only):</strong> AMP SW',
                    '<strong>Vocoder (input FX only):</strong> COLOR, LEVEL']) {
    assert.ok(html.includes(fx), 'the hidden settings list has ' + fx);
  }
  assert.ok(!/<strong>(Compressor|Super Filter)[^<]*:<\/strong>/.test(html), 'no Compressor or Super Filter settings listed');
  assert.ok(html.includes('How do I go back to the original firmware?'), 'the page says how to go back');
  // v9.53: the guitar synth's full guide is in the repository and linked from the page and the README.
  assert.ok(fs.existsSync(path.join(root, 'synth', 'GUITAR_SYNTH.md')), 'the guitar synth guide is in the repository');
  assert.ok(html.includes('synth/GUITAR_SYNTH.md') && readme.includes('(synth/GUITAR_SYNTH.md)'), 'the guide is linked');
  assert.match(readme, /Sound Generator envelopes \(v9\.9\.3\)/);
  assert.match(readme, /## Scale pads \(v9\.9\.3\)/);
  assert.match(readme, /## Arpeggiator \(v9\.9\.3\)/);
  assert.match(readme, /### Using the kits \(v9\.46\)/);
  assert.doesNotMatch(readme, /Pattern sequencer with a graphical interface|## Main controls|## Upstream plans|## Improvements/);
  assert.doesNotMatch(html, /Base released|data-doomos="version"|data-doomos="build"/);
  // The page says the firmware includes DOOM OS and links its quickstart.
  assert.match(html, /DOOM OS is included/);
  assert.match(html, /Included unchanged \(0\.6\.1, build ED5E\)/);
  assert.match(html, /href="manual\/">DOOM OS quickstart/);
  assert.ok(fs.existsSync(path.join(root, 'manual', 'index.html')), 'DOOM OS quickstart is in the repository');
  assert.match(readme, /built on, and includes, \*\*DOOM OS 0\.6\.1\*\*/);
  for (const name of ['OFF', 'Pluck', 'Perc', 'Keys', 'Pad', 'Swell', 'Bass', 'Acid', 'Sweep', 'FPad']) {
    assert.ok(html.includes(name), 'page documents ENV preset ' + name);
    assert.ok(readme.includes('| ' + name + ' |'), 'README documents ENV preset ' + name);
  }
  assert.doesNotMatch(html, /For V8, start at modest LEVEL|Uncheck Wave Lab|Expected Wave Lab V8 APP1/);
  assert.doesNotMatch(readme, /<img[^>]*doom-os-512/);
  assert.doesNotMatch(html, /<img[^>]*doom-os/);
  console.log('PASS: one build, no selector: stock 5.52 gives exactly Sound Generator + Kits v9.53 (midi-out-test15), repeatably; overlay metadata, wrong-input and corruption rejection, no corrupt download, DOOM OS base without kit data; page (patcher first, no version history) and README text.');
})().catch(error => { console.error(error); process.exitCode = 1; });
