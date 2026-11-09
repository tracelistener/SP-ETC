# FX deep edit: a settings page for what the bus effects never get

A hardware test build. Stock 5.52 sends only the six knob parameters (CTRL 1-6) of each effect to
the effects chip (BMC); 142 of the 383 effect parameters are never sent. The FX probe (local branch
`claude/fx-probe`, `synth/FX_PROBE.md` there) showed on the unit that the chip acts on every one it
tried. This page lets you set them.

It is a stage on top of the published Sound Generator + Kits v9.46 (APP1 `7b5fbcb4…684a`). The
firmware's own state is never changed. Values live in RAM, per bus and effect, and (test 11) in one file of the
module's own. Outside the page the build behaves as v9.46, except that an edited value goes to
the chip again whenever the firmware selects that effect on that bus.

## Test 14 (fx-deep-edit-test14): the hidden settings whatever page came in between

On the unit (combined-test16, and v9.51, test 10's FX deep edit): sometimes, at random and long after a restart, DELAY
and REMAIN + DELAY gave the FX screen but VALUE never reached the hidden settings until the effect was switched off and
on. Run in Unicorn: the generic key handler sends VALUE to the FX screen only through stock's pointer to it
(`[0x8059259c]`, among TOP's views), and the page base constructor (`0x800ce1d0`, every page's registry handler calls
it) clears that pointer (`0x800ce27c`) while TOP keeps its FX screen up. Build any page's object (START/END's, in the
check) and VALUE on TOP reaches no FX screen: not the hidden settings, not even stock's screen 2. An FX button press
opens a new FX screen and sets the pointer again (`0x800bd800`), which is why off and on helped.

- The module finds the FX screen by its vtable (`0x802269c0`) among TOP's views (`0x800a01c0(TOP + 0x38, i)`), and at
  every event TOP's filter sees puts stock's pointer back on it if it isn't there, before the event goes on (so the
  same VALUE press gets there). With no FX screen up the pointer is left alone.
- Guard: the constructor's clear `0x800ce274..0x800ce284`.

Checked in the emulator: 102 checks pass (test 13's 100, and: with START/END's page object built and TOP's FX screen
up, the parent's VALUE reaches no FX screen while here the pointer comes back and VALUE steps to screen 2, then the
hidden settings; with no FX screen up the pointer is left as it is).

## Test 13 (fx-deep-edit-test13): the FX screen drawn again after the switch; edits to the chip's effect

On the unit (combined-test15): "after switching it again on different fx (one with no hidden fx) when i went to try
again on another fx it goes off again"; and "when u start machine, press delay then remain delay, no hidden
parameters until u turn delay on and off".

- **The screen.** In the emulator the locked FX screen survives HOLD + VALUE in every order, on the parent and on
  test 12 alike (no lock cleared, no close, no pop), so what went wrong is in what the emulator doesn't do: drawing.
  The FX screen's update (`0x80146598`, its vtable +0x28, every 50 ms through the view tick `0x80073b58`) only
  draws on a change (screen 2 against `0x8059232c`, the CTRL values); when a popup ends the stock draws the page
  under it. The extra screens' popups go with a change of the FX screen (VALUE steps it), so they never showed it;
  the switch's 1.5 s popup ends on its own and the main screen showed while the FX screen was still up and locked
  (its button lit; pressing it twice gave it back). Now the vtable slot points at `fde_fx_update`, which calls the
  stock update and, after a HOLD + VALUE with an FX screen up, once 1.6 s have passed on the audio clock
  (`0x8059226c`, 24 a ms) and no popup is on the screen (`[0x805922b4]` < 1: the popup tick past bounce's hook), sets
  `0x8059232c` to -1: the update takes the screen as changed and draws it all (`+0x1b15`). Not proven on the unit.
- **The chip's effect.** The saved edits went to the effect `0x27c` names on each slot, read at the main screen's
  first event: when that event is an FX button stock hasn't handled yet, `0x27c` names the old effect, and the chip
  (Delay since the boot) gets nothing until an FxType, as off and on gives. The module now notes every FxType it
  sees (`fde_chip`), and the load and the switch send the edits for the effect the chip has.
- Guards: the view tick `0x80073b58..0x80073b7c`, the popup tick `0x8006b95c..0x8006b9e8` (bounce hooks its first 12
  bytes), the popup start `0x8006bc88..0x8006bca4` (its ms into `0x805922b4`), the clock step `0x80004f70..0x80004fae`;
  the slot `0x802269e8` must hold `0x80146599`, the only place that does.

Checked in the emulator: 100 checks pass (test 12's 97, and: after a restart a saved edit goes to the effect the
chip has on BUS 1 while `0x27c` names another; through the vtable slot 3 s of updates leave the FX screen and its
globals as the stock update does; after HOLD + VALUE on the FX screen no redraw while the popup's 1.6 s run or a popup
is up, and the first update after both sets `0x8059232c` to -1, takes the screen as changed and asks to draw it, once).

## Test 12 (fx-deep-edit-test12): no file write while an FX screen is up

On the unit (combined-test14): "turn delay on, press remain delay, screen locked now, press hold+value to toggle
hidden, screen goes to bpm with fx still lit. then later it stopped doing that". In the emulator the locked screen
stays through HOLD + VALUE (no close request), but the emulator neither draws nor models the storage; what test 11
newly did there was write `B:/_fx_hidden.bin` from the UI task with the FX screen up, the first time creating it
(and "later it stopped" fits a first, slow creation). So:

- The file is written at a key's release (`fde_key_up`), once no FX screen and no extra screen is up, after an edit
  or a switch: on leaving the FX screen that is usually EXIT's release. Never while a screen is up, never on a pad.
- HOLD + VALUE holds an FX screen that is up, as a VALUE press there does (`+0x1b3f`, `0x80592320`): one opened with
  the FX button alone would otherwise close after its 2 s. The FX screen is found as the generic key handler finds
  it for VALUE: `[0x8059259c]`, only if it is among TOP's views (`0x800a01c0(TOP + 0x38, i)`; the pointer stays after
  the screen goes).
- Guards: `0x800a01c0..0x800a01d8` and the generic key handler's VALUE lookup `0x800cab96..0x800cabd4`.

Checked in the emulator: 97 checks pass (test 11's 95, and: with the FX screen opened by its button alone, HOLD + VALUE
holds it and it stays past 2 s, where on the parent it goes; an edit on the FX screen and HOLD + VALUE there write
nothing while the FX screen is up, nor on the next key press, and the next key release after it is gone writes both).
Not known: whether the file write really was what sent the screen back; the emulator draws nothing.

## Test 11 (fx-deep-edit-test11): a switch, and the edits kept over a restart

From the user's test of v9.50: "Maybe an option to toggle the hidden effects too. could hold+value knob work", then
"could the hidden paramter edits be saved upon restart?". Asked what off should do, the user chose that it undoes the
edits too (an A/B).

- **HOLD + VALUE** (press), on any page, caught in `fde_key_down` like the input FX's chord (VALUE's press and
  release taken; HOLD itself goes on): **HIDDEN FX OFF**. On each slot the edited settings of the effect it has get
  the firmware's default (one DT1 each, through the stock builder), so the effects sound as on stock; the FX screen's
  VALUE is stock's toggle (`+0x1b40 ^= 1` with `+0x1b3f` set, what `0x801479a0` does), VALUE + EXT SOURCE is stock's,
  and an FxType re-sends nothing. Again: **HIDDEN FX ON**, each slot's edits for its effect sent again. The edits are
  kept either way. Stock has no HOLD + VALUE (the manual's VALUE chords are VALUE + GATE and SHIFT + VALUE). With note
  repeat in the same image, a HOLD press while rolls go on also holds them, as it always does.
- **Saved** in `B:/_fx_hidden.bin`, at the internal drive's root beside stock's own `B:/_emphasis.bin` and
  `B:/_BackSamplingRec.bin` (stock keeps its system data, the FX parameters it retains included, in QSPI flash, so
  there is no stock file to join): "FXHS", version 1, the switch, the record count (u16), FNV-1a 32 of the header's
  first 8 bytes and the records; then a record per edited setting: slot, value, parameter ID (u16). A build whose
  settings list differs drops IDs it doesn't have instead of putting a value on another setting; values are kept
  inside the firmware's range. One file for the unit, like stock's retained FX parameters (manual p. 33), not one per
  project.
- **Read** once, at the first event TOP's filter sees after the boot (the main screen; the file system is up), or
  at the first VALUE + EXT SOURCE or HOLD + VALUE if those come first; then, switched on, each slot's edits for the
  effect it has go to the chip. A missing, short, long or bad file (magic, version, size, sum) changes nothing.
- **Written** whole (open `0x601`, create and truncate; one write; close, as kits-save writes) on leaving an extra
  screen after an edit, and on each HOLD + VALUE. Edits made on a screen still open at power-off are lost. A failed
  open or short write is counted and the edits stay pending for the next leave. A factory reset leaves the file.
- Guards: the file calls (`0x800dec48..0x800dec74` open and read, `0x800debd8..0x800dec48` close,
  `0x800dd9b8..0x800dd9f8` write; the same bytes kits-save guards).

Checked in the emulator: 95 checks pass (test 10's 81, and: HOLD + VALUE sends each slot's edited settings' defaults
slot by slot, takes VALUE's press and release, HOLD as on the parent; off, an FxType sends the parent's frames only,
VALUE + EXT SOURCE and the FX screen's VALUE are the parent's; on again, the edits sent again and re-sent after an
FxType; no file: looked for once at the first event, an edit written on leaving with its one record; after a restart
the first event reads it into RAM and sends it, an FxType re-sends it; off is kept over a restart and nothing is sent;
bad files ignored; unknown IDs and slots dropped, values clamped; a failed write retried at the next leave).

## Test 10 (fx-deep-edit-test10): the chord where every key press arrives

On the unit test 9's VALUE + EXT SOURCE only switched the input off: the EXT SOURCE press never reached TOP's page
filter as a chord (another page than TOP, or a mode the dispatcher hands keys to before any page; the emulator,
which runs TOP with no such mode, opened the screens). Now the UI dispatcher's own handlers for a key press (type 5,
`0x8003abd0`), a key release (type 6, `0x8003ada0`) and a knob (type 9, `0x8003a8d8`) jump to bridges in the module
(`fde_down_bridge`, `fde_up_bridge`, `fde_knob_bridge`): each hands the event to `fde_key_down` / `fde_key_up` /
`fde_knob` first and, unless it is taken, runs the displaced instructions and goes on. That is before the key-mode
prefilter (`0x8006b258`), the key bitmap and any page, so the chord works on any page. VALUE's hold is tracked there
too (`fde.value_down`), besides its bit in `0x80592448`. The input FX's screens are worked there (VALUE steps, CTRL 1-3,
any other key leaves); TOP's filter keeps the BUS screens.

- A taken press never sets its bit in the bitmap, and its release (also taken) never clears it, so the bitmap stays
  right; VALUE's own press and release always go on.
- Guards: the three handlers' code (`0x8003abd0..0x8003acc8`, `0x8003ada0..0x8003ae58`, `0x8003a8d8..0x8003a968`);
  nothing branches into the displaced bytes; the builder checks each bridge instruction by instruction.

Checked in the emulator: 81 checks pass (test 9's, every key, VALUE and knob alone as on the parent, and: the chord
with no page taking events, and with VALUE's bitmap bit cleared by hand).

## Test 9 (fx-deep-edit-test9): VALUE + EXT SOURCE for the input FX

The reference manual (v5.50, p. 36-37) settles how the unit edits the input FX: on its own screen, RECORD SETTING
in sampling standby then VALUE (INPUT FX Setting: VALUE moves a cursor, CTRL 1-3 edit), and its type also under
EFX SET > OTHER > Input FX. Never on the FX screen the FX buttons open, so the knob bus (settings 0x3a) is never 0
where the extra screens live: test 4's input FX screens were reached in the emulator only by setting it there. The
user asked for a way in.

- **On the main screen, hold VALUE and press EXT SOURCE:** the input FX's extra screens (slot 0, the effect in
  system 0x27c[0]), numbered among themselves (`GT AMP SIM 1/4`, the Gt Amp Sim's 12 settings on four screens).
  VALUE steps them and closes after the last; CTRL 1-3 edit them (DT1 on slot 0); any other button leaves and goes
  on as usual. VALUE + EXT SOURCE is no stock combo (the manual's shortcut lists, p. 160-163).
- The EXT SOURCE press and its release are taken (TOP's filter returns 1), so the external input is not switched.
  An input FX without extra settings (or none) shows nothing.
- `fde.input` keeps `follow()` on slot 0 while those screens are up; leaving clears it.

Checked in the emulator: 78 checks pass (test 8's, and: the chord's first screen with the EXT SOURCE events kept
from DOOM OS's filter and the chip, VALUE stepping to 4/4 and closing, CTRL 2 on screen 3 sending SP TYPE 15 on
slot 0, EXIT leaving, Crusher or no input FX showing nothing, EXT SOURCE alone as on the parent).

## Test 8 (fx-deep-edit-test8): the Super Filter's settings are left out

A user's report on v9.48: on the Super Filter's extra screens CTRL 2 spiked the volume (FLT GAIN, 0-12, is
CTRL 2 on the first). The user asked for the Super Filter's hidden settings to go, so all six are on
`EXCLUDED`: the Super Filter has no extra settings, and 135 settings remain. Checked in the emulator.

## Test 7 (fx-deep-edit-test7): no NO EXTRA SETTINGS popup

The user asked for test 4's note to go: an effect without extra settings keeps stock's VALUE, with no popup. The
Compressor's MODE stays left out (test 6). Checked in the emulator: 71 checks pass (Crusher's VALUE as on the
parent, no popup).

## Test 6 (fx-deep-edit-test6): the Compressor's MODE is left out

A user's report on v9.47: the Compressor's extra setting on CTRL 1 (MODE, 0-1) "almost blew my ears off".
Set to 1 it makes the output dangerously loud. The builder now has a list of settings left out on purpose
(`EXCLUDED`), and MODE is on it: the Compressor has no extra settings. 141
settings remain. The patcher page and README tell everyone to turn the volume down before trying the hidden
settings, since others (gains, EQ boosts, feedback, resonance) can also get loud. Checked in the emulator: 71
checks pass (the Compressor offers nothing; every other test 5 check).

## Test 5 (fx-deep-edit-test5): VALUE holds the screen itself

From the user's test of combined-test6: still no extra screens, never the NO EXTRA SETTINGS note, on the main
screen with every FX button, and screen 2 never stayed for more presses: VALUE only peeked at screen 2. The FX
screen is "held" (+0x1b3f) only if REMAIN is down at the moment the show method runs (`0x80146f66`); a screen
that comes up otherwise stays while REMAIN is held but treats VALUE as stock does (the press does nothing, VALUE
held shows screen 2), and the module stepped aside. Now a VALUE press on an FX screen that is not held holds it,
as the show method would have (+0x1b3f and `0x80592320` set), when the effect has screen 2 or extra settings, and
steps on from there: screen 2, the extra screens, screen 1. An effect with neither keeps stock's VALUE. So the
extra screens come however the screen was opened, the FX button alone included; MFX's effect choice before any
VALUE press is stock's.

Checked in the emulator (70 checks pass): FX button alone, then VALUE: held, screen 2, extra screens, no close for
5 s; Crusher opened alone: VALUE stock's, closes after 2 s as on the parent; every test 4 check.

## Test 4 (fx-deep-edit-test4): the input FX too, and a note when there is nothing

From the user's test of combined-test5: on the held FX screen (REMAIN + FX) VALUE only flipped screens 1 and 2,
and the extra screens never came, even after a restart. The extra screens follow the slot the CTRL knobs drive
(settings `0x3a`) and its effect (`0x27c[slot]`), as the FX screen itself does (its update `0x80146598` reads the
same two). Tests 2 and 3 offered them on BUS 1-4 only, so with the knobs on the input FX (slot 0), or on an effect
without extra settings (11 of 48), VALUE quietly did stock's toggle.

- **The input FX** gets its extra screens too. Slot 0 is part of the chip's address map (`03 hi lo aa` with
  hi:lo = (effect − 1) × 5 + slot), and the stock knob path already sends it with slot = `0x3a`. Values are kept per
  slot (`fde_values[5][142]`), and an FxType for slot 0 (`0x7e`) sends the input FX's edited values again, as the
  FxTypes for BUS 1-4 do (`fde_dt1` now passes `0x7e..0x82` to `fde_dt1_fxtype`).
- **An effect without extra settings** says so: the VALUE press that goes back to screen 1 (every press, on an
  effect without screen 2) shows `CHORUS` / `NO EXTRA SETTINGS` for 1.5 s, and stock's toggle runs as before.

Checked in the emulator (68 checks pass): the input FX's extra screen (Reverb's DENSITY on slot 0, `03 .. .. ..`
for slot 0), Crusher's note with stock's flag toggles as on the parent, the input FX's FxType re-sending its edits
(and adding nothing without), the builder's address for all 710 setting/slot pairs, and every test 3 check.

## Test 3 (fx-deep-edit-test3): no FX button hold

From the user's test of combined-test4: "fx screen hold is broken. now on mfx, once pressed cannot get to menu to
change. just get rid of that for now." Test 3 drops test 2's hold (the patch at `0x80146f66`): an FX button alone
is stock again (its screen closes after 2 s, and MFX's effect choice is stock's). The extra screens stay on the
screen REMAIN + FX opens (stock's screen that stays): there VALUE press steps screen 1, screen 2, the extra screens
and screen 1 again, as test 2 did. Three changes in 5.52 space now (the TOP vtable slot, the DT1 builder's entry,
the VALUE toggle).

Checked in the emulator (68 checks pass): only those three sites change inside the parent; an FX button alone opens
the FX screen as on the parent (+0x1b3f clear, VALUE stock's, the close request after 2 s); REMAIN + FX gives the
screen that stays, as on the parent, and the same FX button again does what the parent does (the effect stays on,
the screen stays); every test 2 check of the screens, knobs and re-sending, now with REMAIN + FX.

## Test 2 (fx-deep-edit-test2): on the FX screen

From the user's test of combined-test3: the FX screen should stay up after an FX button, as it does with REMAIN +
FX, and the extra settings should be more screens of the FX screen, reached with VALUE. Test 1's TOP page (EXIT +
VALUE, VALUE turns) is gone; sections below that describe it are test 1's.

### Using it

- **An FX button** opens the FX screen as REMAIN + FX does in stock: it stays until EXIT, REMAIN, or that FX button
  again (the effect goes off). Another FX button shows that one.
- **VALUE press** steps the screens: screen 1 (CTRL 1-3), screen 2 (CTRL 4-6, where the effect has them), then the
  effect's **extra screens**, then screen 1 again. Effects without extra settings keep stock's screens.
- **An extra screen** is a popup with three of the effect's extra settings on CTRL 1-3:

  ```
  TAPE ECHO 3/5
  C1 SYNC 0
  C2 BASS 15
  C3 TREBLE 15
  ```

  Turning CTRL k sets its setting across the firmware's range (knob at 0: the minimum, at the top: the maximum);
  each change is one DT1, as in test 1. A knob without a setting there does nothing.
- On an extra screen, pads play as usual; any button but VALUE and SHIFT leaves it (the popup goes) and does what
  it always does.
- Values are still per bus and effect, in RAM, and sent again after every FxType for that bus.

### How stock's FX screen works (5.52, read in the code and run in Unicorn)

- An FX button (keys 0x2b-0x2f, MFX 0x30) lights its button (system 0x276[bus]) and pushes the FX screen onto TOP's
  view stack (TOP + 0x3dc): constructor `0x80147ba0`, vtable `0x802269c0`, a 2000 ms timer at +0x1b10.
- Its show method (`0x80146e78`) keeps **whether REMAIN (key 0x24) is held** in +0x1b3f (`0x80146f66`), and sets
  `0x80592320` then.
- Its update (`0x80146598`, every 50 ms) counts the timer down and asks to close (`0x800bb180(screen, 1)`) when it
  runs out, unless MFX is held. With +0x1b3f set, the timer is re-armed while the bus has an effect, and screen 2
  shows while +0x1b40 is set and the effect has CTRL 4-6; without it, screen 2 shows while VALUE is held. It asks to
  close when its FX button goes off.
- VALUE pressed: the generic key handler (`0x800cba46`) calls `0x801479a0`, which toggles +0x1b40 when +0x1b3f is
  set. REMAIN pressed closes it (`0x801479b8`); EXIT destroys it.

### Patches

| Site | Stock | Now |
| --- | --- | --- |
| `0x80146f66` | `bl 0x800d9f20` (is REMAIN held?) | `movs r0, #1; nop`: every FX screen is REMAIN's |
| `0x801479a0` | the VALUE toggle's first ten bytes | jump to `fde_value`: screen 1, 2, the extra screens, 1 |
| `0x8022ce64` | TOP vtable +8, DOOM OS's filter | `fde_filter`: CTRL 1-3 on an extra screen, leaving it |
| `0x800d8118` | the DT1 builder's first ten bytes | `fde_dt1`, as test 1 (sending again after an FxType) |

Six more guards (27): the FX screen's constructor, show method, update and VALUE toggle, the generic handler's VALUE
call, TOP's knob handler.

### Checked in the emulator

`test_fx_deep_edit.py` (69 checks) on fx-deep-edit-test2:
- the FX screen: an FX button alone opens it as REMAIN + FX (on v9.46 only with REMAIN held); it stays through 5 s of
  updates where v9.46's asks to close after 2 s; that FX button again, or no effect on the bus, closes it;
- VALUE: Tape Echo goes to screen 2, its three extra screens, then screen 1; Isolator to its one extra screen and
  back; Crusher toggles stock's flag as v9.46 does with REMAIN; nothing sent;
- extra screens: CTRL 1-3 set their settings (one frame a change, none if the value stays), a knob without a setting
  does nothing, pads play, another button leaves, then the knobs are stock's; all 142 settings reach their min and
  max; BUS 2-4; none on the input FX;
- sending again after an FxType, as in test 1; four quick EXITs are STOP; every key alone, the FX buttons included,
  and the other scripts go on as on v9.46.

### Not known

- How the popup looks with four lines on the unit (test 1 showed two).
- EXIT on the FX screen: stock destroys it (the emulator stops there, waiting on another task).

## Using it (test 1)

On the TOP page, **hold EXIT and press VALUE**. The stock popup (`0x800d3ff0`) shows the bus the
CTRL knobs drive, its effect and the first of that effect's extra settings:

```
BUS1 TAPE ECHO          turn VALUE: the next or previous setting
TAPE DIST 4             press VALUE: edit
```

```
BUS1 TAPE ECHO          editing: turn VALUE to change it (each change goes to the chip at once)
TAPE DIST [4]           press VALUE again: stop editing
```

- **EXIT**, or any other button, closes the page and then does what it always does (four quick EXITs
  are still STOP). Pads and knobs work as usual while the page is open, so you can play and listen.
- A setting shows the firmware's default (`0x801abe64`) until you edit it. Numbers are raw: what they
  mean (dB, Hz, cents) is not known.
- Every value stays inside the firmware's own min/max for that parameter (`0x801ad1fc`/`0x801ac830`).
- The popup stays 10 s after the last VALUE action; the page stays open until EXIT or another button
  (turn VALUE to see it again).
- Other popups: `BUS1 / NO EFFECT` (nothing on the bus), `BUS1 CRUSHER / NO EXTRA SETTINGS` (an effect
  whose parameters stock already sends), `INPUT FX / BUS 1-4 ONLY` (the knobs are on the input FX).
- If the bus's effect changes while the page is open, the next VALUE action starts over on the new
  effect's first setting.

## What the page reads and sends

- **Bus:** settings `0x3a` (`0x82e01144`, getter `0x800d94d8`): 0 input FX, 1-4 BUS 1-4. TOP's CTRL
  1-3 path `0x80183c48` → `0x800cc030` picks the slot from it.
- **Effect:** system `0x27c[bus]` (`0x82dfeed0 + 0xc4 + 2 × bus`, getter `0x800da010`), 0 = none; the
  knob path does nothing while it is 0. (`0x276[bus]` is the lit FX button, 1-5 or 6 = MFX; `0x27b` the
  MFX choice; `0x80018bf0` turns those into `0x27c` and calls the effect select.)
- **Settings:** an effect's parameters that are not in its six-ID knob record (`0x802e5b40`) and that
  DM-404's `fxmap.json` gives no boot value; IDs from the firmware's name table (`0x80245ee4`) joined
  with fxmap. The builder insists the firmware's name for every ID is fxmap's name at that address.
  11 effects have none: Crusher, Overdrive, Distortion, Chorus, Downer, Auto Pitch, COMPRESSOR 2, SBF,
  Harmony, Sub Sonic, Cloud Delay.
- **A change** is one DT1 through the stock builder `0x800d8118(0x80592500, parameter ID, bus, value)`,
  the call the bus-effect knobs end in; slot = bus, so `03 hi lo aa` with hi:lo = (effect − 1) × 5 + bus.
  Opening, browsing, entering and leaving edit, a turn past min/max, and closing send nothing.

## Sending again

Stock (re)selects an effect on a slot by sending its FxType (`0x7e` + slot). It never re-sends an
effect's knob parameters on an effect change: the effect select `0x800d0cf0` sends the FxType when it
differs from its cache `0x80246f38`, and the bus switch; the knob stores are per bus and effect and are
sent only by knob moves (`0x80018a98`) and the boot chip reset `0x801803b0`, which first sets every slot
to FxType 0, then sends CTRL 1-3 of every effect on every slot. FxType goes out from the effect select,
the system setter (`0x800de270`, IDs up to `0xa1`), the second setter (`0x8008cabe`), the BUS 1/2 swap
(`0x8001b8e2`, `0x8001b95e`) and the chip reset.

So the hook is on the builder itself: after any FxType for BUS 1-4 (`0x7f..0x82`) with effect *e*, the
bus's edited values for *e* go out, in the page's order, right behind it. That covers an effect
change and coming back, and a project or boot reload that selects the effect again. Nothing else adds
a frame: a knob turn, an FxType for an effect without edits, the input FX's FxType, the chip reset's
FxType 0. Choosing the effect the chip already has sends no FxType (stock's cache), so nothing is
re-sent then either: the chip still has it.

## The patches

1. **TOP's page vtable** `0x8022ce5c`, slot `+0x08` (`0x8022ce64`): DOOM OS ED5E's filter `0x6031c8f9` →
   `fde_filter`, which takes the chord, VALUE while the page is open, and closes the page on any other
   button; every event goes on to DOOM OS's filter as before unless the page took it.
2. **The DT1 builder's first ten bytes** (`0x800d8118`: `push.w {r4-r11, lr}`, `sub sp, #12`,
   `movw sb, #0xe1c8`) → `movw ip / movt ip / bx ip` to `fde_dt1`. Nothing branches into those bytes but
   the entry (the builder checks every BL, B.W and literal). `fde_dt1` is four instructions: anything
   but an FxType for BUS 1-4 branches to `fde_dt1_stock` (the three displaced instructions, then on at
   `0x800d8122`) with the caller's own stack and return address, so the builder runs exactly as stock,
   down to the frames it builds from leftover stack for the `-1` entries of the knob records (the chip
   reset sends 25 of those, with addresses like `d6 00 00 00`); an FxType for BUS 1-4 goes to
   `fde_dt1_fxtype`, which sends it the same way and then the bus's edited values.

The module (Zig 0.13.0, `-Os`, about 5 KB) lives in a new boot copy row in a 16 KB slot at `0x83FE2000`,
below the FX probe's slot `0x83FE6000`, bounce stage 3 `0x83FE8000`, the CPU meter, the bounce probe and
the start fix. 21 SHA-256 guards cover the stock code and tables it calls, reads or relies on.

## The settings

Name, the firmware's min-max, (its default). Effects 23 Gt Amp Sim and 42 Vocoder are not in the BUS
menu; their rows only matter if they ever get onto a bus.

| Effect | Settings |
| --- | --- |
| 1 FILTER+DRIVE | LEVEL 0-255 (255) |
| 2 TIMECTRLDLY | HIGH CUT 0-14 (14), HIGH DAMP 0-81 (81), LOW DAMP 0-81 (81) |
| 3 ISOLATOR | BALANCE 0-255 (255) |
| 5 PHASER | TYPE 0-3 (2) |
| 6 FLANGER | LOW CUT F 0-17 (0), MODE 0-1 (0) |
| 9 TAPE ECHO | SYNC 0-1 (0), BASS 0-30 (15), TREBLE 0-30 (15), PAN S 0-255 (128), PAN M 0-255 (128), PAN L 0-255 (128), TAPE DIST 0-8 (4) |
| 10 REVERB | DENSITY 0-10 (10) |
| 11 WRMSATURATOR | LOW FREQ 0-255 (88), LOW GAIN 0-48 (10), HI SLOPE 0-2 (2), HI FREQ 0-255 (200), PRE1 TYPE 0-4 (0), PRE1 FREQ 0-255 (88), PRE1 GAIN 0-48 (24), PST1 TYPE 0-4 (3), PST1 FREQ 0-255 (88), PST2 TYPE 0-4 (4), PST2 FREQ 0-255 (200), PST3 TYPE 0-4 (4), PST3 FREQ 0-255 (149), PST3 GAIN 0-48 (24), PST3 Q 5-160 (5), SENSE 0-60 (20), POST GAIN 0-60 (57), BALANCE 0-255 (255) |
| 12 RESONATOR | BALANCE 0-255 (255), LOW CUT F 0-17 (0) |
| 13 DJFX LOOPER | LEVEL 0-255 (255) |
| 15 JUNO CHORUS | LEVEL 0-255 (255) |
| 16 TREMOLO/PAN | EQ LOW 0-30 (15), EQ HIGH 0-30 (15), LEVEL 0-255 (255), PHASE 0-180 (90) |
| 17 WAH | BALANCE 0-255 (255), EQ LOW 0-30 (15), EQ HIGH 0-30 (15), LEVEL 0-255 (255) |
| 18 SYNC DELAY | HIGH CUT 0-14 (14), HIGH DAMP 0-81 (81), LOW DAMP 0-81 (81) |
| 19 EQUALIZER | MID Q 0-4 (0), MID2 FREQ 0-16 (7), MID2 GAIN 0-30 (15), MID2 Q 0-4 (0), LEVEL 0-255 (255), BALANCE 0-255 (255) |
| 20 LO-FI | POST FILT 0-2 (1) |
| 21 RING MOD | LEVEL 0-255 (255) |
| 22 CHROMATIC PS | FINE1 0-200 (100), LEVEL1 0-255 (255), FINE2 0-200 (100), LEVEL2 0-255 (255), EQ LOW 0-30 (15), EQ HIGH 0-30 (15), LEVEL 0-255 (255) |
| 23 GT AMP SIM | AMP SW 0-1 (1), AMP TYPE 0-13 (0), MASTER 0-255 (200), GAIN 0-2 (1), PRESENCE 0-255 (0), BRIGHT 0-1 (0), SP SW 0-1 (1), SP TYPE 0-15 (4), MIC SET 0-2 (1), MIC LEVEL 0-255 (255), DIRECT 0-255 (0), PAN 0-255 (128) |
| 24 STOPPER | HOLD 0-1 (1) |
| 26 SLICER | ATTACK 0-255 (100), RESET SW 0-1 (0), RESET THR 0-255 (120), LEVEL 0-255 (255) |
| 28 COMPRESSOR | none since test6 (MODE 0-1 (0) was left out: set to 1 it made the output dangerously loud) |
| 30 SCATTER | BALANCE 0-255 (255) |
| 31 404 VINYLSIM | DIST 0-255 (60), DISC TYPE 0-2 (0), BALANCE 0-255 (255) |
| 32 303 VINYLSIM | BALANCE 0-255 (255) |
| 33 ZAN-ZOU | M D LEVEL 0-255 (0), M D MODE 0-2 (2), M D SYNC 0-1 (0), M D TIME 0-255 (188), M D FBK 0-255 (153), M HF DAMP 0-17 (17), M D PAN1 0-255 (0), M D PAN2 0-255 (255), M D PAN3 0-255 (64), M D PAN4 0-255 (192), S D PAN1 0-255 (0), S D PAN2 0-255 (255), S D PAN3 0-255 (64), S D PAN4 0-255 (192) |
| 34 SUPER FILTER | none since test8 (FLT SLOPE 0-2 (0), FLT GAIN 0-12 (0), MOD SW 0-1 (1), MOD WAVE 0-4 (2), ATTACK 0-255 (100), LEVEL 0-255 (255) were left out: CTRL 2 spiked the volume) |
| 35 HYPER-RESO | BALANCE 0-255 (255), LOW CUT F 0-17 (0) |
| 36 KO-DA-MA | LEVEL 0-255 (255), TAP 0-255 (128), HIGH CUT 0-14 (14), HIGH DAMP 0-81 (81), LOW DAMP 0-81 (81) |
| 37 HA-DOU | DENSITY 0-10 (10) |
| 38 TO-GU-RO | HOLD 0-1 (0) |
| 39 CASSETTE SIM | BALANCE 0-255 (255) |
| 41 SX DELAY | SYNC 0-1 (1), PHASE 0-1 (0), FBK ROUTE 0-1 (0), HF DAMP 0-17 (17), MOD SW 0-1 (0), MOD RATE 0-255 (0), MOD DEPTH 0-255 (0), EQ LOW 0-30 (15), EQ HIGH 0-30 (15), LEVEL 0-255 (255) |
| 42 VOCODER | COLOR 0-255 (0), LEVEL 0-255 (255) |
| 44 SX REVERB | TYPE 0-5 (3), PRE DELAY 0-125 (26), LEVEL 0-255 (255) |
| 46 BACK SPIN | MODE 0-5 (1), FLT MOD 0-255 (0), SYNC 0-1 (1), RESONANCE 0-255 (0), AMP MOD 0-255 (0) |
| 48 DJFX DELAY | HIGH CUT 0-14 (14), HIGH DAMP 0-81 (81), H DAMP F 0-14 (13), LOW DAMP 0-81 (81), L DAMP F 0-11 (8) |

## Checked in the emulator (not on hardware)

`python synth/test_fx_deep_edit.py OUT_DIR` (74 checks), on the image with its static constructors run
and the TOP page made on page entry, every chip byte logged, through the real UI dispatcher, DOOM OS's
filter, TOP's EXIT and knob handlers, the system and settings getters and setters, the effect select,
the chip reset and the DT1 builder:

- static: only the scatter pointer, the TOP vtable word and the builder's first ten bytes change inside
  the parent; one copy row added; the guards hold; nothing reaches into the ten bytes; the compiled
  settings are exactly the 142 the test derives itself from the parent and fxmap; every popup line fits;
- through the jump, every parameter ID on every slot (2,483 that send) and the whole boot chip reset
  (19,560 bytes, its 25 garbage frames included) send the parent's bytes; fxmap's address for all 142
  settings on all 4 buses;
- the page: the chord, browsing, editing (one frame per change, nothing else), every one of the 142
  settings stopping at the firmware's min and max, per-bus and per-effect values, the four other popups,
  the effect changing while open, EXIT;
- sending again, against the parent's own traffic: effect away and back through the stock MFX choice,
  the system setter, an FxType sent straight to the builder as the bus swap does, and system init plus
  the chip reset followed by the effect chosen again: the edited values follow the FxType frame, and
  nothing else differs; a knob turn, another bus, the input FX and FxType 0 add nothing;
- outside the page: every key alone, EXIT and VALUE alone and in pairs, knobs, pads, the encoder, four
  quick EXITs (STOP), a lost VALUE release: as on the parent, with edited values held; while it is open,
  pads and knobs as on the parent, and EXIT or any other button closes it and goes on as on the parent.

The kit suites (test_kits, capture, chord, shortcut, midi, restart, hot resample, test_kit_bounce flow,
13 kits and 4 tweaked) pass on the image. test_start_fix passes on its own release; on this image its
trim and threshold checks pass and its 4 structural checks fail by design (they assert the start fix is
the top stage). Two builds from different build folders are byte-identical.

## Test15: the hidden settings on every page

The user on v9.52: in pad mode HOLD + VALUE, FX and VALUE reach the hidden settings, and REMAIN + FX keeps them while
the effect is lit; with the effect unlit, REMAIN + FX holds the FX screen but VALUE never reaches them (nor after the
FX button lights the effect there, until it goes off and on again); and on the Sound Generator page, the kits and the
guitar synth screen they never come.

- **Cause** (DM-404, the real firmware): stock's generic key handler sends VALUE to the FX screen (`0x800cba46` ->
  `0x801479a0`, the toggle this module hooks) on the main page (1) only. REMAIN + FX on an unlit effect opens page 34
  (TOP's object gone, `0x80cfd350` = 0), whose own handler toggles screen 2 itself while the screen is held and does
  nothing once the FX button has lit the effect there; the Sound Generator page (30: the kits and the guitar synth
  screen are on it) keeps VALUE. Stock's pointer `0x8059259c` holds the FX screen on both, and is cleared when it
  closes (EXIT, or after its 2 s), as on the main page.
- **Now** the dispatcher's key press handler (`fde_key_down`, every page, before the page) sends VALUE to the FX
  screen that is up and takes it (press and release): TOP's list while TOP's object is there (the pointer put back,
  as TOP's filter does), else stock's pointer if it holds a view with the FX screen's vtable (`fx_up`). The knob
  handler works the BUS extra screens too, and any key but VALUE and SHIFT leaves one, on any page (TOP's filter did
  both on TOP only). With the hidden settings off, or no FX screen up, VALUE goes on as before. The file is held while
  an FX screen is up on any page; HOLD + VALUE holds an FX screen on any page.
- **Checked:** `test_fx_deep_edit.py` 106 of 106 (4 new: VALUE, CTRL 1 and leaving with TOP's object gone and only
  stock's pointer to the screen; VALUE not taken with the settings off or no screen up). The blob is 10,208 bytes
  (test14: 10,112).

## Not known (the hardware test, or later)

- What the numbers mean, and whether the chip uses the firmware's ranges.
- Whether the chip's own value for a never-sent parameter at power-on is the firmware's default (the
  page shows the default until edited).
- Whether the chip keeps a never-sent value across an effect change. The page re-sends after every
  FxType, so it should not matter.
- How a project load reaches the chip: stock re-selects effects through the same setters (so FxType goes
  out when the effect differs from the select's cache), but the load path itself was not traced. If a
  project load restarts the unit, the edits are gone like at power-off.
- BUS 3/4: stock's knobs write both slots 3 and 4; the page writes only the bus it shows.

## Build

```sh
python synth/build_fx_deep_edit.py PATH/kits-v9.46-test3/SP404MKII_APP1.bin OUT_DIR \
    --zig PATH/zig.exe --fxmap PATH/dm-404/core/fx/fxmap.json [--build-dir DIR]
python synth/test_fx_deep_edit.py OUT_DIR
```

Stock APP0 must sit beside the input APP1. keystone, unicorn and capstone on PYTHONPATH, Zig 0.13.0.
The manifest lists every setting with its ID, BUS 1 address, range and default, the patches and the
guards.
