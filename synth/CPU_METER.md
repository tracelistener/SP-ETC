# CPU meter (pad FX step 0, hardware test T0)

A test-only stage that times the audio task with the Cortex-M7 cycle counter (DWT_CYCCNT,
0xE0001004) and shows the result in the stock popup. It exists to measure, on the unit,
how much of each 64-frame block (1.33 ms, 800,000 cycles at 600 MHz) the stock pad voices
and the kits already use, before any pad FX code is written (pad FX study, `analysis/pad_fx/REPORT.md`
§4 and §12). It changes no audio and is not meant for the patcher.

## What it measures

| Readout | Span | Where |
| --- | --- | --- |
| MIX | the whole mixer `0x1c2d0`, entry to return | mixer entry patch; the return is routed through `meter_mix_exit` |
| PAD | the pad voice loop: the slot 0 per-voice call to the end of slot 31 | per-voice stub `0x80005870` |
| SG | the fork's SG render stub behind `0x1c766`: arp tick, the four SG voices, the kits | the stub's pre call `0x1fd84`; its return is routed through `meter_sg_end` |

Each is kept per 375-block window (0.5 s) as average and peak, next to the most voices
rendered in one block of the window. Since the readout was last switched on the meter also
counts blocks whose mixer took over 75% (HI) and over 100% (OVR) of a block, and keeps the
slowest mixer block (MAX). Percentages and thresholds use the measured block length when it
is between 600k and 1M cycles (else 800,000); CLK shows the core clock that length implies
(64 frames at 48 kHz: 800,000 cycles = 600 MHz).

Readout: on the main screen (page 1) hold EXIT alone for one second to show or hide it. No
event is consumed: EXIT does what it always does. SHIFT + EXIT, EXIT on any other page, or
any other key pressed or released during the hold does nothing. While shown, the stock popup
(`0x800d3ff0`, 1.5 s) is re-posted when a window finishes and at least once a second, on every
stock page (0–94; never on DOOM OS's own screen, page 95); a stock popup that is showing or
queued is left alone, and switching off closes only the meter's own popup (`0x8001f730`). Five lines in the popup's font (PBold, 9 px): the widest worst case is
107 px, a 124 x 52 box on the 128 x 64 screen.

## Patches

Every site is checked against its exact instructions (`GUARDS` in `build_cpu_meter.py`) and
nothing may branch into a displaced span. The module (`cpumeter/cpu_meter.c`, about 2.5 KB of
code and state) goes in a new boot copy row at `0x83FED000`, below the RESAMPLE start fix
(`0x83FEF000`); the builder checks that no row overlaps it and that nothing in the input refers
to it. The C is built integer-only (soft-float ABI): no FPU instruction can appear in the hooks.

| Site | Stock | Becomes | Notes |
| --- | --- | --- | --- |
| `0x0001c2d0` (12 bytes) | mixer prologue: `push.w {r4-r11, lr}; sub sp, #0x1c; movw r1, #0xb93c; str r0, [sp, #8]` | jump to `meter_mix_entry` | stamps the start, re-creates the four instructions with the saved return set to `meter_mix_exit`, continues at `0x1c2dc`; the mixer has one caller (`0x1d096`) |
| `0x80005870` (12 bytes) | per-voice stub: `voice = *slot; if (!voice) return;` then the renderer veneer | jump to `meter_voice` | same test, then `0x14b89(voice, stems, &bus, &bus2)` with the mixer's four arguments; stamps slot 0 and slot 31, counts voices |
| `0x0001fd84` (8 of 10 bytes) | the fork SG stub's `movw/movt ip` to its pre bridge (`0x83fa21b1` in v9.46-test1) | `movw/movt ip` to `meter_sg_pre` | `meter_sg_pre` stamps, swaps the stub's saved return (`[sp, #20]`) for `meter_sg_end`, then jumps to the original bridge with every register as it came |
| `0x8006b950` (12 bytes) | popup tick prologue: `push {r4-r6, lr}; movw/movt r4, 0x805922ac; ldr r1, [r4, #8]` | jump to `meter_ui_entry` | runs the meter's UI step (gesture, popup), re-creates the four instructions, continues at `0x8006b95c` |

The cycle counter: the stock tempo clock reads it, so it should already run. If it does not
at the first block, the meter starts it (DEMCR.TRCENA, DWT_LAR, DWT_CTRL.CYCCNTENA, as the
Oct 10 voice load test did) and shows a `*` after CLK.

## Build and test

Python 3.12, keystone, unicorn and capstone (`requirements.txt`), Zig 0.13.0. The input is a
fork build folder with stock APP0 beside the APP1 (and the kit stage's `kits-manifest.json`
for the tests):

```sh
python synth/build_cpu_meter.py out/kits-v946-final/SP404MKII_APP1.bin out/cpumeter-t0 --zig /path/to/zig
python synth/test_cpu_meter.py out/cpumeter-t0
```

The builder writes APP1, a copy of APP0, `manifest.json`, `HARDWARE_TEST.md` (from
`cpumeter/HARDWARE_TEST.md`) and `SHA256SUMS.txt`; it refuses to overwrite. The tests boot
the parent and the meter image in Unicorn side by side (scatter rows, same stubs) and write
`test_report.json`:

- static: only the header, the four patch spans and the appended tail differ; the scatter
  table is the parent's plus one row;
- hook entries: from the mixer entry and from the popup tick entry to the first stock
  instruction after the displaced ones, registers and frame equal the parent's (the mixer
  frame's saved return is `meter_mix_exit`, by design);
- voice chain: every slot's per-voice call over randomised voices (main, release, declick and
  cue paths, mono/stereo, chunk ends, empty slots; all seven bus-add helpers reached) leaves
  all memory, bus/bus2, the callee-saved registers and the stub calls as the parent does, and a
  negative control (one stem word nudged on the meter side) is caught;
- whole mixer: blocks of `0x1c2d0` with randomised voices and four TR-606 cymbals on the kit
  page: TX buffers and all memory (ITCM, DTCM, OCRAM, SDRAM, test area) equal the parent's,
  block for block, except the meter's own area and the scratch stack;
- measurement points: with the counter driven by the instruction count, the meter's spans
  equal stamps at the stock boundaries (voice loop `0x1c710..0x1c73e`, SG call
  `0x1c766..0x1c76a`, mixer entry to return) minus its own 16–117 instructions, and the meter
  costs about 550–620 instructions per block (under 0.1% of a block at one cycle each);
- arithmetic with a controlled counter (windows, averages, peaks, voices, HI/OVR, the
  measured budget and its fallback, reset on switch-on, the counter start-up fallback), the
  readout's text and pixel widths, and the UI gesture and popup rules.

## Unicorn preview (instructions, not cycles)

Instruction counts per block from the measurement-point runs on the parent image (synthetic
voices; real cycles on the unit will be higher, by how much is what T0 measures):

| Case | MIX | PAD | SG |
| --- | --- | --- | --- |
| idle | 30k | 0.7k | 20k |
| 32 voices | 240k–421k | 210k–380k | 20k |
| 15 voices + 4 TR-606 cymbals | 287k–439k | 92k–189k | 183k–240k |

The first block of a run is the slow end (chunk changes, cymbal onsets). At one cycle per
instruction, 32 voices plus four 606 cymbals would already be around 50–70% of a block, which
is why the pad FX budget waits for T0.

## For pad FX

The per-voice stub `0x80005870` is also the pad FX hook site. When pad FX is built, its wrapper
replaces `meter_voice` (and can keep the same slot 0 / slot 31 stamps for the adaptive cap); the
mixer and SG timing can stay as they are.
