# IR diagnostic test 1 (ir-diag-test1): CPU meter and a test echo, on v9.49

A test-only build, not for the patcher. It answers, on the unit, what an amp IR or NAM stage on the main
processor would face, before one is written:

- **How much of each audio block is free.** NAM A2-Lite needs about 4,000 cycles a sample on a Cortex-M7
  (TONE3000's embedded engine: 41% of a 480 MHz Daisy Seed, code and weights in TCM). The SP's audio runs in
  1.33 ms blocks of 64 frames; the CPU meter (T0, `CPU_METER.md`, built Oct 13 and never flashed) times the
  mixer, the pad voices and the SG/kit render in every block.
- **What the capture holds and where a return goes.** The echo takes the RX pair the recorder feed copies
  (`0x202ad0a0`: what INPUT SETTING's ROUTING picks, Mix or ExtIn) and puts it back on the DRY pair. One
  listen tells whether the return is heard, whether it is captured again (feedback), whether the capture is
  after the input FX, and whether EXT SOURCE off keeps the capture while the direct input goes.

## The echo

- After every RX block (bounce's rx bridge, `diag_rx`): bounce's `bnc_rx`, then the feed's 64 frames into a
  7,168-frame ring as mono, (L + R) / 2. The ring is a zero row at `0x83FE4000` (14,336 bytes: the FX probe's
  unused slot and the top of FX deep edit's).
- After every mixer call (`meter_mix_end`): while on, the ring's oldest block, at 1/4 (-12 dB), onto words 0/1
  (DRY L/R) of the TX line 3 block the mixer has just packed, clipped to 20 bits as the packer clips. TX runs
  before RX in a wake, so the block added is the one 112 RX blocks back: about 149 ms.
- On while the input FX is the Gt Amp Sim: `echo_ui` reads system `0x27c[0]` (`SYS_GET`, the getter FX deep
  edit uses) every 0.1 s from the UI task (bounce's ui bridge, `diag_ui`: `bnc_ui`, the meter's UI step, then
  this).
- With ROUTING on Mix the DRY return is in the capture again (the record mix is TX words 0-7 at unity), so each
  pass comes back 12 dB quieter: decaying repeats, never louder.

## Sites

The input is v9.49 (combined-test9, APP1 `8f285b01...4750`); the output is `687502de...46a2`. T0's own jumps at
the audio task's mixer call and at the popup tick are taken by bounce in place, so those two go behind
bounce's bridges; the rest is T0's.

| Site | Becomes |
| --- | --- |
| `0x0001c2d0` mixer entry (12 bytes) | jump to `meter_mix_entry`, which keeps the mixer's argument (TX line 3 is its word 0) |
| `0x80005870` per-voice stub (12 bytes) | jump to `meter_voice` |
| `0x0001fd84` SG stub's pre call (8 of 10 bytes) | `meter_sg_pre` |
| bounce's rx bridge, its `bnc_rx` call (8 bytes) | `diag_rx` |
| bounce's ui bridge, its `bnc_ui` call (8 bytes) | `diag_ui` |

The builder checks bounce-3-test9's three bridges instruction by instruction (`bounce_bridges`), that nothing
branches into a replaced span, that no row overlaps the module (`0x83FED000`, 8 KB) or the ring, and that
nothing in the input refers to either.

## Checked in the emulator (not on hardware)

`python synth/test_ir_diag.py OUT_DIR --kits kits-v9.46-test3/kits-manifest.json`: 59 checks pass. T0's
checks on the v9.49 parent (the voice chain over 12 seeds, the whole mixer with 606 cymbals: TX and all memory
as the parent's with the echo off; the measurement points; the meter's arithmetic, readout and UI), the popup
tick through bounce's ui bridge as the parent's, and the echo: 152 blocks of ring and TX add against a Python
model (DRY L/R only, the 112-block delay, the 20-bit clip), the whole mixer with the echo on (the parent's TX
plus exactly the echo), the gate (23 on, anything else off, one read per 0.1 s), off leaving TX alone, and
`diag_rx`/`diag_ui` running bounce's own `bnc_rx`/`bnc_ui` as the parent does.

## Not known (the hardware test)

- The real cycles: the emulator counts instructions. The Oct 10 voice load test ran 4-5 times its instruction
  count from SDRAM.
- Whether the effects chip passes the DRY return as the stems' scale says, whether the capture is after the
  input FX, and whether EXT SOURCE off stops the capture too.

## Test 2 (ir-diag-test2)

The same module on combined-test10 (v9.49 plus FX deep edit test9: hold VALUE and press EXT SOURCE on the main
screen for the input FX's extra screens), so one flash tries all three. APP1 `bb6eee9d...6bce3`; 59 checks pass.
