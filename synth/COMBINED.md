# Combined: every feature test build in one APP1

**combined-test5** (section 6) follows the user's test of combined-test4: bounce, FX deep edit and note repeat
at their new revisions, the rest as in combined-test4 (section 5), then the fast boot. Sections 1-4 describe
combined-test1.

A hardware test build (`combined-test1`) with the latest test build of each feature in one APP1, so they can
be tried together. Branch `claude/combined`: the six feature branches merged on `main` (v9.46), plus
`build_combined.py`, which runs each feature's own builder in turn. Nothing in a feature changes: each module
is byte for byte the one in its own test build.

| Step | Feature | Branch | Builder | Slot | Module as in |
| --- | --- | --- | --- | --- | --- |
| 1 | bounce in place, stage 3 | `claude/bounce-stage3` | `build_bounce.py` | `0x83FE8000` 20 KB | `bounce-3-test7` |
| 2 | FX deep edit | `claude/fx-deep-edit` | `build_fx_deep_edit.py` | `0x83FE2000` 16 KB | `fx-deep-edit-test1` |
| 3 | pad envelopes, stage 1 | `claude/pad-env-pitchfilter` | `build_pad_env.py` | `0x83FDE000` 16 KB | `pad-env-test5` (stage 1) |
| 4 | pad envelopes, stage 2 | `claude/pad-env-pitchfilter` | `build_pad_pitch_filter.py` | `0x83FD9000` 12 KB | `pad-env-test5` |
| 5 | kit edits saved | `claude/kits-save` | `build_kits_save.py` | `0x83FD5000` 8 KB | `kits-save-test1` |
| 6 | note repeat | `claude/note-repeat` | `build_note_repeat.py` | `0x83FDC000` 8 KB | `note-repeat-test2` |
| 7 | chromatic scales | `claude/chroma-scales` | `build_chroma.py` | `0x83FD7000` 8 KB | `chroma-test1` |

Left out: the FX probe (`fx-probe-test1`). FX deep edit uses its TOP EXIT + VALUE chord and the same TOP
vtable slot (`0x8022ce64`), and the unit has answered the probe's questions.

## 1. Build

```
python synth/build_combined.py PARENT_DIR OUT_DIR --zig ZIG --fxmap dm-404/core/fx/fxmap.json --refs RELEASE_DIR
```

`PARENT_DIR` holds bounce-3-test7's parent, `resample-startfix-3` (`7d13c1e2…61cc`: the published v9.46's kit
stage plus the RESAMPLE start fix v3), with stock APP0 and its manifest. `RELEASE_DIR` holds the seven test
builds the modules are compared with. Each step writes `OUT_DIR-steps/<n>-<feature>/`; `OUT_DIR` gets the
final APP1, stock APP0, `manifest.json`, `SHA256SUMS.txt` and `steps/` (each step's own manifest).

The builder stops unless:
- each module's bytes are its test build's (blob SHA-256), and step 1's APP1 is bounce-3-test7's;
- on the final image, every step's patches are in place, its guards and table guards hold, its module is at
  its slot as built (with stage 2's links into stage 1), and no two slots overlap;
- APP1 ends below the 4 MB flash's end (`0x60400000`).

## 2. Order and guards

Every builder checks the code it relies on byte for byte (its guards) before it patches. So a builder runs
before the ones that patch inside its guards: FX deep edit and pad envelopes guard the UI dispatcher
`0x8003b530`, which note repeat bridges; note repeat guards the pad-event consumer (`0x80050be0..0x80050f20`)
and the pattern recorder (`0x800bd5a0..0x800bd7a0`), where chroma patches `0x80050e78` and `0x800bd644`.

One pair guards each other's site: note repeat guards the pad-event dispatcher `0x800bef10` that bounce
bridges, and bounce guards the pad note `0x800cdbd0` that note repeat bridges. Bounce goes first: its
builder refuses an APP1 past the kit PCM planning boundary, which the later modules cross. So note repeat's
builder checks an input with bounce's ten bytes at `0x800bef10` put back to stock, and its output gets them
again (`FOREIGN`). The step's manifest records it.

On the final image, 7 guards span another feature's hook. Each one holds with that hook's bytes put back to
stock, and `SHARED` says why its reason still holds:

| Guard (whose) | Hook inside it (whose) | Why it still holds |
| --- | --- | --- |
| pad note `0x800cdbd0` (bounce, 2 spans) | `0x800cdbd0` (note repeat) | note repeat's pad note acts only for the stock pad handler's press and HOLD let-go callers. Bounce triggers its source from its own code (`F_TRIGGER`), which goes straight on to the stock body |
| UI dispatcher `0x8003b530` (FX deep edit) | `0x8003b530` (note repeat) | the entry takes VALUE (press and release) only while ROLL is held, and VALUE turns only while ROLL is held or latched with a pad repeating. EXIT + VALUE on TOP reaches `fde_filter` |
| UI dispatcher `0x8003b530` (pad envelopes) | `0x8003b530` (note repeat) | the same: the ENVELOPE page's SHIFT and DEL are never taken |
| pad-event dispatcher `0x800bef10` (note repeat) | `0x800bef10` (bounce) | bounce's gate passes every event to the ring as stock unless a bounce owns the recorder. Then it drops note-ons except its own trigger, so repeats during a take are dropped like any other pad |
| pad-event consumer (note repeat) | `0x80050e78` (chroma) | chroma's note-off reads the stored note signed. The consumer still gives a type-4 note to the recorder, then plays it or lets it go |
| pattern recorder (note repeat) | `0x800bd644` (chroma) | `chroma_record` records a pad note with its note byte and goes on with the recorder, so a repeat is recorded as a tap, with chroma's note |

Nothing else is shared:
- **PADCONF reserved bytes:** pad envelopes stage 1 uses `0x64-0x6F`, note repeat `0x70`, stage 2 `0x71-0x7F`.
- **Files:** kits save writes its own `SG_KITS.BIN`.
- **RAM:** each module's state is in its own slot.

## 3. Size

APP1 is 3,148,576 bytes. That is 43,808 bytes past the kit PCM planning boundary (`0x60376000`, where
`kits/build_arp_kit.py` plans a PCM bank that holds nothing yet), as pad-env-test5 already was. It is
521,440 bytes below the end of the 4 MB flash (`0x60400000`).

## 4. Checked

**combined-test1:** APP1 `10616541…eb84`. The build passed every check in section 1. Unicorn, 2026-10-21, with
`analysis/kit_pr1_audit/dev_combined/run_suites.py`:
- Each feature suite ran on the final APP1, with that step's manifest re-pointed at it (`make_views.py`).
- The kit and start-fix suites ran on it through the v9.46 kits manifest and the start fix v3 manifest.

| Suite | Result | What fails |
| --- | --- | --- |
| `test_bounce.py` | 528 of 535 cases | 7 layout checks: the parent's bytes, the last two rows, the PCM boundary |
| `test_fx_deep_edit.py` | every behaviour check | 2 layout checks; against a parent without note repeat, also ROLL (key 0x21): it latches note repeat now |
| the same, parent: this chain without FX deep edit (`variant.py`) | every behaviour check, ROLL included | 2 layout checks; its UI dispatcher guard (note repeat's hook, `SHARED`) |
| `test_pad_env.py` (stage 1) | the audio and envelope sections (31) | 2 layout checks. The UI section stops at page 5, which stage 2 adds: the test knows 4 pages |
| the same, on step 3's output (stage 1, before stage 2) | 62 of 62 | |
| `test_pad_pitch_filter.py` (stage 2, all 8 pages) | 42 of 44 | 2 layout checks |
| `test_kits_save.py` | 120 of 122 | 2 layout checks |
| `test_note_repeat.py` | every behaviour check (97 cases) | the parent is not v9.46, 2 layout checks, its guard on bounce's gate (`SHARED`) |
| `test_chroma.py` | all | |
| `test_start_fix.py` (v3) | every behaviour check | 4 layout checks (the last row) |
| kit suites: kits, capture, chord, shortcut, midi, restart, hot resample, bounce (13 kits, 4 tweaked, flow) | 25 of 25 | |

The final scatter table is the parent's 25 rows plus the 8 rows the steps added, in order: bounce's
copy and zero-fill rows, and one copy row for each of the six other modules.

**One interaction found:** on the chromatic page, stock's ROLL + VALUE moves the root. Note repeat takes
VALUE turns while ROLL is held, so there it steps the roll division instead. That is
note-repeat-test2's behaviour on its own as well (NOTE_REPEAT.md section 5). The combination doesn't
change it.

**Not run:** dm-404 (not built on this machine: no `build/`, no MSYS2), and the unit.

## 5. combined-test4

From the user's test of combined-test3, every change in one build. Branch `claude/combined` merges the feature
branches at these revisions and `claude/boot-anim` (the fast boot); `build_combined.py` runs eight steps, then
`build_fast_boot.py` on its result, as for combined-test3.

| Step | Feature | Module as in | What changed since combined-test3 |
| --- | --- | --- | --- |
| 1 | bounce in place | `bounce-3-test8` | a pad tap picks the target (the source REPLACE, an empty pad TO PAD, a used pad PAD NOT EMPTY); RESAMPLE starts |
| 2 | FX deep edit | `fx-deep-edit-test2` | an FX button's screen stays (as REMAIN + FX); VALUE steps its screens, then the extra screens on CTRL 1-3 |
| 3, 4 | pad envelopes | `pad-env-test6` | page 1 named on its bottom line, TIME on VALUE press, VALUE turns the pages, no DROPS |
| 5 | kits save | `kits-save-test2` | an arp for each mode; the Sound Generator's settings saved per project (SG_KITS.BIN version 2) |
| 6 | note repeat | `note-repeat-test3` | chromatic rolls: 1/16 from power-on, nothing taken from the pad under the finger (pad 10) |
| 7 | chromatic scales | `chroma-test2` | -12..+27; VALUE held and turned: the scale; with SHIFT: the key |
| 8 | SUB PAD on the SG page | `sg-subpad-test1` | new: SUB PAD plays the last pad again, in melodic and drum mode |

- **Build:** every module byte for byte its own test build's; every patch in place and every guard holding on the
  final image, with the same 7 reviewed overlaps (`SHARED`) as combined-test1; no new one. `--refs` takes a folder
  of the seven test builds' manifests (`analysis/kit_pr1_audit/dev_combined4/refs`); the builds themselves are in
  the dev folders.
- **APP1** (after the fast boot): `adcb6f70…157f`, 3,151,616 bytes, in `analysis/kit_pr1_audit/release/combined-test4`.
- **SUB PAD's slot** `0x83FD4000`-`0x83FD5000` comes from the top of pad FX's planned room, below kits save.

**Checked** (Unicorn, 2026-10-22, `analysis/kit_pr1_audit/dev_combined4/run_suites.py`): every suite on the
flashable APP1 (fast boot included), each feature suite with its step's manifest re-pointed at it.

| Suite | Result | What fails |
| --- | --- | --- |
| `test_bounce.py` | 15 of 22 sections | 7 layout checks (the parent's bytes, the last rows, the PCM boundary, now 46,848 bytes over) |
| `test_fx_deep_edit.py` | 66 of 69 | 2 layout checks; against its parent (bounce only), ROLL (key 0x21): it latches note repeat now |
| `test_pad_env.py` (stage 1) | 29 | 2 layout checks; the UI section stops at page 5, which stage 2 adds (the test knows 4 pages) |
| the same, on step 3's output (stage 1, before stage 2) | 64 of 64 | |
| `test_pad_pitch_filter.py` | 42 of 44 | 2 layout checks |
| `test_kits_save.py` | 167 of 169 | 2 layout checks |
| `test_note_repeat.py` | 98 of 102 | the parent is not v9.46, 2 layout checks, its guard on bounce's gate (`SHARED`) |
| `test_chroma.py` | 35 of 38 | 2 layout checks; ROLL + VALUE turned no longer moves the key: note repeat takes it for the roll speed, as chosen (the key is SHIFT + VALUE held and turned) |
| `test_sg_subpad.py` | 24 of 25 | 1 layout check |
| `test_start_fix.py` (v3) | every behaviour check | 4 layout checks (the last row) |
| kit suites: kits, capture, chord, shortcut, midi, restart, hot resample, bounce (13 kits, 4 tweaked, flow) | 25 of 25 | |

The patcher test (`node synth/test_browser.cjs`, branch `claude/publish-v9.47`) passes with v9.47 = combined-test4.
**Not run:** dm-404, and the unit.

## 6. combined-test5

From the user's test of combined-test4, in one build. Branch `claude/combined` merges the three feature branches
at their new revisions; the other five steps are combined-test4's. `build_combined.py`, then `build_fast_boot.py`.

| Step | Feature | Module as in | What changed since combined-test4 |
| --- | --- | --- | --- |
| 1 | bounce in place | `bounce-3-test9` | a replaced pad sets up as a bounce (VALUE press for UNDO and back); the target pad lit steady white |
| 2 | FX deep edit | `fx-deep-edit-test3` | no FX button hold (it kept MFX's effect choice away); the extra screens on REMAIN + FX's screen |
| 6 | note repeat | `note-repeat-test4` | chromatic rolls: each pad its own division (byte 0x70 bits 4-7), 1/16 to start |

- **Build:** every module byte for byte its own test build's (`--refs analysis/kit_pr1_audit/dev_combined5/refs`);
  every patch in place and every guard holding on the final image, with the same 7 reviewed overlaps (`SHARED`).
  Bounce's new guard (the key light `0x800d4910`) covers code nothing patches.
- **APP1** (after the fast boot): `634f7af1…0bef`, 3,151,952 bytes, in `analysis/kit_pr1_audit/release/combined-test5`
  (the combined build before it: `292462e7…9a0a`).
- **The clicks** the user heard on chromatic rolls are RETRIG CUT on the sample's pad (NOTE_REPEAT.md 9.2): each
  repeat stops the ringing note as a re-hit does; RETRIG set to a fade fades it instead.

**Checked** (Unicorn, 2026-10-22, `analysis/kit_pr1_audit/dev_combined5/run_suites.py`): every suite on the
flashable APP1 (fast boot included), each feature suite with its step's manifest re-pointed at it. The same
results as combined-test4's, with the new checks passing.

| Suite | Result | What fails |
| --- | --- | --- |
| `test_bounce.py` | 543 cases, 15 of 22 sections | 7 layout checks (the parent's bytes, the last rows, the PCM boundary, now 47,184 bytes over) |
| `test_fx_deep_edit.py` | 65 of 68 | 2 layout checks; against its parent (bounce only), ROLL (key 0x21): it latches note repeat now |
| `test_pad_env.py` (stage 1) | 29 | 2 layout checks; the UI section stops at page 5, which stage 2 adds (the test knows 4 pages) |
| the same, on step 3's output (stage 1, before stage 2) | 64 of 64 | |
| `test_pad_pitch_filter.py` | 42 of 44 | 2 layout checks |
| `test_kits_save.py` | 167 of 169 | 2 layout checks |
| `test_note_repeat.py` | 99 of 103 | the parent is not v9.46, 2 layout checks, its guard on bounce's gate (`SHARED`); every chromatic check passes |
| `test_chroma.py` | 35 of 38 | 2 layout checks; ROLL + VALUE turned is the roll speed, as chosen |
| `test_sg_subpad.py` | 24 of 25 | 1 layout check |
| `test_start_fix.py` (v3) | every behaviour check | 4 layout checks (the last row) |
| kit suites: kits, capture, chord, shortcut, midi, restart, hot resample, bounce (13 kits, 4 tweaked, flow) | 25 of 25 | |

The patcher test (`node synth/test_browser.cjs`, branch `claude/publish-v9.47`) passes with v9.47 = combined-test5.
**Not run:** dm-404, and the unit.

## 7. combined-test6

From the user's test of combined-test5: the FX deep edit's extra screens never came (VALUE only flipped screens
1 and 2), and the drum kit screen's "SHIFT: PAGE" should go. `build_combined.py` with FX deep edit at
`fx-deep-edit-test4` (the input FX gets the extra screens too; an effect without any says NO EXTRA SETTINGS), the
other seven steps as in combined-test5; then `build_fast_boot.py`; then the new `build_kit_footer.py`.

- **Kit footer:** the kit stage's `kit_ui_footer_draw` (`kits/kit_ui.inc`) clears the Sound Generator page's footer
  while a kit is on and draws "SHIFT: PAGE" there (the first draw after entering drum mode showed it in the big
  font, cut to "SHIFT: PA"). The kit stage is baked into every feature build's parent, so the text goes in a step on
  top, as the fast boot does: the string's first byte at `0x83fbaf36` (the kit blob's boot copy row to
  `0x83fa2000`) becomes 0, so the footer is cleared and nothing is drawn. Guards: the 12 bytes, the footer's one
  literal for them (`0x83fa7718`) and that nothing else in the image refers to them.
- **APP1:** `e54935c3…d6e6`, 3,152,352 bytes, in `analysis/kit_pr1_audit/release/combined-test6` (the combined build
  `7fd46808…bf57`, after the fast boot `52d91be4…23e9`). Every module byte for byte its own test build's; the same
  7 reviewed overlaps.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined6/run_suites.py`, which takes a list of suites now): on
the final APP1, `test_fx_deep_edit.py` 65 of 68 (the same 2 layout checks and ROLL's key as on combined-test5)
and the kit suites kits, capture, chord, shortcut, midi, restart and hot resample pass. The kit suites check the
kit module's two hashes first; the runner re-points them at the module with the footer's one byte, and says so
in the view's manifest. Not rerun: the other feature suites and the 18 kit bounce runs, whose modules and code
are combined-test5's byte for byte. The patcher test passes with v9.47 = combined-test6.

## 8. combined-test7

From the user's test of combined-test6: the FX deep edit's extra screens still never came, on the main screen with
every FX button, and never the NO EXTRA SETTINGS note; screen 2 never stayed for more VALUE presses. So the FX
screen was not "held" when VALUE came (held is decided once, by REMAIN being down when the screen shows), and the
module stepped aside. FX deep edit at `fx-deep-edit-test5`: a VALUE press holds the screen itself when the effect
has screen 2 or extra settings, then steps on. The rest as in combined-test6, then the fast boot and the kit footer.

- **APP1:** `be758f67…34b4`, 3,152,432 bytes, in `analysis/kit_pr1_audit/release/combined-test7` (the combined build
  `94d2786c…8ea7`, after the fast boot `407d4a99…2b70`). Every module byte for byte its own test build's; the same 7
  reviewed overlaps.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined7/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 67 of 70 (the same 2 layout checks and ROLL's key) and the kit suites kits, capture, chord,
shortcut, midi, restart and hot resample pass (the kit module's hashes re-pointed for the footer byte). Not rerun:
the other feature suites and the 18 kit bounce runs (their modules are combined-test5's byte for byte). The patcher
test passes with v9.47 = combined-test7.

## 9. combined-test8

A user reported that the Compressor's hidden MODE setting on v9.47 (combined-test7) made the output dangerously
loud, and the user asked for the NO EXTRA SETTINGS note to go. FX deep edit at `fx-deep-edit-test7`: the
builder leaves the Compressor's MODE out of its table (`EXCLUDED`), and an effect without extra settings keeps
stock's VALUE with no popup. The rest as in combined-test7, then the fast boot and the kit footer.

- **APP1:** `fbcff606…e9f0`, 3,152,272 bytes, in `analysis/kit_pr1_audit/release/combined-test8` (the combined build
  `7e294a75…a4d6`, after the fast boot `7fb4371c…2c96`). Every module byte for byte its own test build's; the same 7
  reviewed overlaps. Only the FX deep edit module differs from combined-test7.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined8/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 68 of 71 (the same 2 layout checks and ROLL's key; the Compressor has no extra settings,
Crusher's VALUE shows no popup) and the kit suites kits, capture, chord, shortcut, midi, restart and hot resample
pass (the kit module's hashes re-pointed for the footer byte). Not rerun: the other feature suites and the 18 kit
bounce runs (their modules are combined-test7's byte for byte). The patcher test passes with v9.48 = combined-test8.

## 10. combined-test9

A user's report on v9.48 (combined-test8): on the Super Filter's extra screens CTRL 2 spiked the volume (FLT
GAIN, 0-12, is CTRL 2 on the first). The user asked for the Super Filter's hidden settings to go. FX deep edit at
`fx-deep-edit-test8`: all six are on the builder's `EXCLUDED` (135 settings remain). The rest as in combined-test8,
then the fast boot and the kit footer.

- **APP1:** `8f285b01…4750`, 3,152,144 bytes, in `analysis/kit_pr1_audit/release/combined-test9` (the combined build
  `484b4d3a…9184`, after the fast boot `c45a4ca9…2a60`). Every module byte for byte its own test build's; the same 7
  reviewed overlaps. Only the FX deep edit module differs from combined-test8.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined9/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 69 of 72 (the same 2 layout checks and ROLL's key; the Super Filter and the Compressor have
no extra settings) and the kit suites kits, capture, chord, shortcut, midi, restart and hot resample pass. Not
rerun: the other feature suites and the 18 kit bounce runs (their modules are combined-test7's byte for byte). The
patcher test passes with v9.49 = combined-test9.

## 11. combined-test10

The reference manual (v5.50, p. 36-37) shows the unit edits the input FX on its own screen (RECORD SETTING, then
VALUE), never the FX screen, so FX deep edit's input FX screens (test 4) never came on the unit. FX deep edit at
`fx-deep-edit-test9`: on the main screen, hold VALUE and press EXT SOURCE for the input FX's extra screens (the Gt
Amp Sim's 12 settings on four), VALUE to step them, CTRL 1-3 to edit them; the EXT SOURCE press is taken, so the
input is not switched. The rest as in combined-test9, then the fast boot and the kit footer.

- **APP1:** `f85d62c5...4e85`, 3,152,368 bytes, in `analysis/kit_pr1_audit/release/combined-test10` (the combined
  build `0d81ab9c...9efb`, after the fast boot `a00a4505...32cd`). Every module byte for byte its own test build's; the
  same 7 reviewed overlaps. Only the FX deep edit module differs from combined-test9.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined10/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 75 of 78 (the same 2 layout checks and ROLL's key; every test9 check passes) and the kit
suites kits, capture, chord, shortcut, midi, restart and hot resample pass. Not rerun: the other feature suites and
the 18 kit bounce runs (their modules are combined-test7's byte for byte). The IR diagnostic test 2
(`claude/ir-diag`) is this build plus the CPU meter and the test echo.

## 12. combined-test11

From the user's test of IR diagnostic test 2 (combined-test10 inside): VALUE + EXT SOURCE only switched the input off,
so the EXT SOURCE press never reached TOP's page filter as a chord. FX deep edit at `fx-deep-edit-test10`: the UI
dispatcher's key press, key release and knob handlers (`0x8003abd0`, `0x8003ada0`, `0x8003a8d8`) hand every event
to the module first, on any page and before the key-mode prefilter, with VALUE's hold tracked there. No other step
patches or guards those handlers. The rest as in combined-test10, then the fast boot and the kit footer.

- **APP1:** `b7662d50...31c5`, 3,152,672 bytes, in `analysis/kit_pr1_audit/release/combined-test11` (the combined
  build `1545410f...bca9`, after the fast boot `5984039b...36b1`). Every module byte for byte its own test build's;
  the same 7 reviewed overlaps. Only the FX deep edit module (and its three new hook sites) differs from
  combined-test10.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined11/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 78 of 81 (the same 2 layout checks and ROLL's key; every test10 check passes) and the kit
suites kits, capture, chord, shortcut, midi, restart and hot resample pass. Not rerun: the other feature suites and
the 18 kit bounce runs (their modules are combined-test7's byte for byte). IR diagnostic test 3 (`claude/ir-diag`)
is this build plus the CPU meter and the test echo.

## 13. combined-test12

From the user's test of v9.50 (combined-test11): on the START/END screen ROLL held previews the sample's end (manual
v5.50), and every ROLL tap there also toggled note repeat's latch (`Roll Latch On`). Note repeat at
`note-repeat-test5`: on the START/END screen (page 0x16) the module steps aside, as in DJ mode, so ROLL, VALUE, HOLD
and pads are stock's there and ROLL's release reaches stock's release handling; a latch is kept for afterwards, and a
ROLL press from before the screen opened stays note repeat's until it is let go. Its builder guards two more stock
words (page 0x16's page table entry and its handler table's first word), which no other step patches. The rest as
in combined-test11, then the fast boot and the kit footer.

- **APP1:** `e1bff602...3056`, 3,152,800 bytes, in `analysis/kit_pr1_audit/release/combined-test12` (the combined
  build `ac3f673d...73fc`, after the fast boot `af3fcee9...60d0`). Every module byte for byte its own test build's;
  the same 7 reviewed overlaps. Only the note repeat module differs from combined-test11.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined12/run_suites.py`): on the final APP1,
`test_note_repeat.py` 103 of 107 (the 4 layout checks every combined image fails; the 4 new START/END checks pass)
and the kit suites kits, capture, chord, shortcut, midi, restart and hot resample pass. note-repeat-test5 on its own
parent passes all 107. Not rerun: the other feature suites and the 18 kit bounce runs (their modules are
combined-test11's byte for byte).

**On the unit:** the popup still came. Page 0x16 is a recording screen, not START/END (see combined-test13).

## 14. combined-test13

From the user's test of combined-test12. Note repeat at `note-repeat-test6`: a key only asks for a page and the
page change writes it later; START/END asks for page 5, PITCH/SPEED (where ROLL opens Groove) for page 4. The module
steps aside on those two (ROLL the screen's, a latch kept, ROLL with stock's light: blinking on START/END), page
0x16 is its own again, and EXIT + pad (stock: the pad's sound stops) also stops that pad's roll, held rolls too.
Its builder guards six more stock ranges (pages 4 and 5's table entries and registry words, PITCH/SPEED's switch and
ROLL case, START/END's key release handler), which no other step patches. The rest as in combined-test11, then the
fast boot and the kit footer.

- **APP1:** `1ef31cb7...7fca`, 3,152,880 bytes, in `analysis/kit_pr1_audit/release/combined-test13`. Every module
  byte for byte its own test build's; the same 7 reviewed overlaps. Only the note repeat module differs from
  combined-test11.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined13/run_suites.py`): on the final APP1,
`test_note_repeat.py` 109 of 113 (the 4 layout checks every combined image fails; the 7 checks for ROLL's screens and
the 3 for EXIT + pad pass) and the kit suites kits, capture, chord, shortcut, midi, restart and hot resample pass.
note-repeat-test6 on its own parent passes all 113.

## 15. combined-test14

The user asked for a way to switch the hidden FX settings off ("could hold+value knob work"; off undoes the edits too,
an A/B) and for the edits to be kept over a restart. FX deep edit at `fx-deep-edit-test11`: HOLD + VALUE, on any page,
is HIDDEN FX OFF (each slot's edited settings of its effect back to the firmware's defaults, the FX screen's VALUE and
VALUE + EXT SOURCE stock's, no re-sends after an FxType) and HIDDEN FX ON again; the edits and the switch are kept in
`B:/_fx_hidden.bin` (read at TOP's first event after the boot, written on leaving an extra screen after an edit and on
each switch). Its new guards are the file calls kits-save guards too (no step patches them). With note repeat in the
image, HOLD's press still reaches note repeat first (held rolls) and VALUE goes on to FX deep edit unless ROLL is
held. The rest as in combined-test13, then the fast boot and the kit footer.

- **APP1:** `77ade9a5...ac48`, 3,156,832 bytes, in `analysis/kit_pr1_audit/release/combined-test14` (the combined
  build `012085f0...cfca`, after the fast boot `7757f6f9...90b8`). Every module byte for byte its own test build's;
  the same 7 reviewed overlaps. Only the FX deep edit module differs from combined-test13.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined14/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 92 of 95 (the same 2 layout checks and ROLL's key; the 6 switch checks and the 8 saved-file
checks pass), `test_note_repeat.py` 109 of 113 (the 4 layout checks) and the kit suites kits, capture, chord,
shortcut, midi, restart and hot resample pass. fx-deep-edit-test11 on its own parent passes all 95.

**On the unit:** REMAIN + an FX button locks the screen without switching the effect on (stock). With the effect on and
the screen locked, HOLD + VALUE sometimes sent the display back to the main screen, at first and then no longer.

## 16. combined-test15

FX deep edit at `fx-deep-edit-test12`: the hidden settings' file is written at a key's release once no FX screen and
no extra screen is up (test 11 wrote it right on the FX screen, from the UI task, the first time creating it), never
on a pad; HOLD + VALUE holds an FX screen that is up, found as the generic key handler finds it for VALUE
(`[0x8059259c]` among TOP's views). New guards `0x800a01c0..0x800a01d8` and `0x800cab96..0x800cabd4`, which no step
patches. The rest as in combined-test14, then the fast boot and the kit footer.

- **APP1:** `5ed02968...f997`, 3,156,880 bytes, in `analysis/kit_pr1_audit/release/combined-test15` (the combined
  build `590fb95c...79a1`, after the fast boot `8f7c5fd5...934e`). Every module byte for byte its own test build's;
  the same 7 reviewed overlaps. Only the FX deep edit module differs from combined-test14.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined15/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 94 of 97 (the same 2 layout checks and ROLL's key), `test_note_repeat.py` 109 of 113 (the 4
layout checks) and the kit suites pass. fx-deep-edit-test12 on its own parent passes all 97. Not known: whether the
write was what sent the screen back (the emulator draws nothing).

**On the unit:** it still went to the main screen at times (after HOLD + VALUE on an effect without hidden settings,
then on another); and after a restart the saved edits weren't heard until the effect was switched off and on.

## 17. combined-test16

FX deep edit at `fx-deep-edit-test13`: the FX screen's update (its vtable `0x802269c0` +0x28, the slot `0x802269e8`)
goes through `fde_fx_update`, which, after a HOLD + VALUE with an FX screen up, once the popup's 1.6 s are over and no
popup is on the screen, makes the screen draw itself again (stock draws the page under a popup that ends; the FX
screen draws only on a change); and the module notes every FxType, so the saved edits and the switch go to the effect
the chip has, not to what `0x27c` names at the main screen's first event. Its new guards are the view tick, the
popup tick past bounce's 12 bytes, the popup start and the clock step; no other step patches them (bounce's popup
tick hook ends at `0x8006b95c`). The rest as in combined-test15, then the fast boot and the kit footer.

- **APP1:** `9fb45ab8...900c`, 3,156,960 bytes, in `analysis/kit_pr1_audit/release/combined-test16` (the combined
  build `4920a9fe...ea97`, after the fast boot `011fd2c8...4312`). Every module byte for byte its own test build's;
  the same 7 reviewed overlaps. Only the FX deep edit module (and its new slot) differs from combined-test15.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined16/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 97 of 100 (the same 2 layout checks and ROLL's key), `test_note_repeat.py` 109 of 113 (the 4
layout checks) and the kit suites pass. fx-deep-edit-test13 on its own parent passes all 100. Not proven on the unit:
that the redraw is what was missing.

**On the unit:** saving across a restart works. At random, long after a restart (and on v9.51 too), VALUE on the FX
screen didn't reach the hidden settings until the effect was switched off and on.

## 18. combined-test17

FX deep edit at `fx-deep-edit-test14`. Every page's base constructor (`0x800ce1d0`) clears stock's pointer to the FX
screen (`0x8059259c`) while TOP keeps the FX screen up, and the generic key handler routes VALUE only through that
pointer; the module now finds the FX screen by its vtable among TOP's views and puts the pointer back at TOP's next
event. New guard: the constructor's clear (`0x800ce274..0x800ce284`), which no step patches. The rest as in
combined-test16, then the fast boot and the kit footer.

- **APP1:** `e7b75421...be79`, 3,157,104 bytes, in `analysis/kit_pr1_audit/release/combined-test17` (the combined
  build `2550ada6...2eb1`, after the fast boot `5a0eef88...3fca`). Every module byte for byte its own test build's;
  the same 7 reviewed overlaps. Only the FX deep edit module differs from combined-test16.

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined17/run_suites.py`): on the final APP1,
`test_fx_deep_edit.py` 99 of 102 (the same 2 layout checks and ROLL's key), `test_note_repeat.py` 109 of 113 (the 4
layout checks) and the kit suites pass. fx-deep-edit-test14 on its own parent passes all 102.

## 19. combined-test18

A fork user's MIDI keyboard has no velocity: every note comes at 127, and the Sound Generator played it at full volume
with no way to turn it down. Stock's LEVEL is no value of its own: its getter reads voice 0's level, so it shows the
last note's velocity, and only the page's pads use it (as their velocity, with FIXED VELOCITY on). The SG LEVEL step
(`build_sg_level.py`, module `sg-level-test1`, SG_LEVEL.md) goes on top of combined-test17, after the fast boot and the
kit footer:
- LEVEL (CTRL 3, CC 72) is kept by SetParam's Sound Generator call and read back by its getter.
- The Sound Generator's melodic MIDI note-ons play at velocity x LEVEL / 127 (at least 1), ARP on or off, on either M.CH
  route.
- A LEVEL change scales the MIDI keys the arp holds again.
- Drum mode and the pads are as before.

```
python synth/build_sg_level.py release/combined-test17/SP404MKII_APP1.bin OUT_DIR --zig ZIG \
    --kits release/bounce-3-test7/kits-manifest.json --revision combined-test18
```

- **APP1:** `e5788fca...170f`, 3,158,224 bytes, in `analysis/kit_pr1_audit/release/combined-test18`. Every module and
  patch of combined-test17 is as it was. The step adds three patches (`0x1ff20`, `0x80020480`, `0x83fa3448`) and one
  copy row (35 rows): the 552-byte module in a 2 KB slot at `0x83FA1800`. That slot is between v9.6's scale module and
  the kit stage, RAM no fork branch uses.
- **One patch inside another feature's guard:** `arp_midi_event`'s entry (`0x83fa3448`) is inside kits save's guard over
  the whole kit stage, as the kit footer's byte is. Kits save uses the kit stage's addresses and never calls
  `arp_midi_event`; the step's manifest says so (`inside_guards`).

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined18/run_suites.py`, every suite). It is combined-test17's runner,
with the kit manifest's module hashes re-pointed for the kit footer's byte and the entry patch. The suites not rerun on
combined-test17 got a baseline run there (`dev_combined18/baseline17`).

| Suite | Result | Against combined-test17 |
| --- | --- | --- |
| `test_sg_level.py` (new) | 26 of 26 | |
| `test_bounce.py` | 543 cases; 16 checks pass, 7 layout checks fail | the same |
| `test_fx_deep_edit.py` | 99 of 102 | the same (2 layout checks, ROLL's key) |
| `test_pad_env.py` (stage 1) | 29, then the UI section stops at page 5 | the same lines |
| the same, on step 3's output | 64 of 64 | |
| `test_pad_pitch_filter.py` | 42 of 44 | the same |
| `test_kits_save.py` | 166 of 169 | the same 3 (2 layout checks; its kit-stage guard: the footer's byte, now the entry too) |
| `test_note_repeat.py` | 109 of 113 | the same (4 layout checks) |
| `test_chroma.py` | 35 of 38 | the same |
| `test_sg_subpad.py` | 23 of 25 | one more layout check: the rows are SUB PAD's parent's plus one more (this step's) |
| `test_start_fix.py` (v3) | 13; 4 layout checks fail | the same |
| kit suites: kits, capture, chord, shortcut, midi (CC 72 included), restart, hot resample | pass | |
| kit bounce: 13 kits, 4 tweaked, flow | 18 of 18 | |

**DM-404** (SG_LEVEL.md section 6). MIDI notes on the real firmware, CTRL 3 at three positions:
- combined-test18: a note at velocity v and LEVEL l peaks as combined-test17's note at v x l / 127 does (565 and 275 at
  LEVEL 35, 1081 and 533 at 67), and at LEVEL 127 as before. The screen keeps the LEVEL set.
- combined-test17: CTRL 3 changes nothing for MIDI.

**Not run:** the unit.

## 20. combined-test19

The user said: "at 127, sound genrator is way too louf esp[ecially with 4 notes at a time. it should be similar to
loudness of a sample. same with kits". The same step, with the module at `sg-level-test2` (SG_LEVEL.md section 7),
replaces the kit stage's output stage. That stage (x2 and a knee, since v9.39) applied to melodic notes too.

- **Before (combined-test18):** one note -1.2 dBFS (in the knee), four notes -0.3 dBFS, kit hits -1.3 dBFS.
- **The reference:** samples reach the bus at their own level (DM-404: a sampled -6 dBFS sine plays back at -6 dBFS).
- **Now:** the same capture and knee, with x0.5 in melodic mode and x1 in drum mode. REC and BOUNC get twice that
  (BOUNC unchanged).

```
python synth/build_sg_level.py release/combined-test17/SP404MKII_APP1.bin OUT_DIR --zig ZIG \
    --kits release/bounce-3-test7/kits-manifest.json --revision combined-test19
```

- **APP1:** `95f6ce80...77a3`, 3,158,576 bytes, in `analysis/kit_pr1_audit/release/combined-test19`. It rebuilds byte
  for byte.
- **Two more patches** (8 bytes each): the SG render stub's exit `0x1fdd4` goes to `sgl_mix_gate`, which has
  `kit_mix_gate`'s shape (the SY builders check it); the REC exporter bridge `0x8353ba06` goes to `sgl_export_mix`.
  No step guards either.
- **The module** (912 bytes) stays in its slot at `0x83FA1800`.

| | combined-test18 | combined-test19 |
| --- | --- | --- |
| one note, LEVEL 127 (full-scale TYPEs) | -1.2 dBFS (knee), RMS -3.6 (sine) | -12.0 dBFS, RMS -15.1, no knee |
| four notes (C E G B) | -0.3 dBFS, RMS -2.5 | -1.2 to -2.0 dBFS, RMS -8.8; the knee on in-phase peaks only |
| kit pads alone | -1.3 dBFS (8 to 16 pads per kit in the knee) | at most -6.4 dBFS, none in the knee |

**Checked** (Unicorn, `analysis/kit_pr1_audit/dev_combined19/run_suites.py`, every suite):
- `test_sg_level.py` passes 36 of 36. It checks the stage sample for sample against a float32 model of the kit stage's
  knee (melodic, drum mode, other audio in the bus, the REC mix), and that the SG's raw mix is the parent's.
- Every other suite gives combined-test18's results (the layout checks' changed-byte counts aside).
- The kit suites (kits, capture, chord, shortcut, midi, restart, hot resample) pass. All 18 kit bounce runs pass:
  BOUNC goes through the stage at x2, as before.
- DM-404: one note -12.0 dBFS peak (RMS -15.1) and four notes -1.3 dBFS (RMS -9.1), against -1.2 and -0.3 on
  combined-test18, with the sampled reference unchanged.

**Not run:** the unit.
