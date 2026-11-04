# Cabinet test 1 (cab-test1): a cabinet IR on the captured input

A test-only build, not for the patcher: v9.50 (combined-test11) with IR diagnostic test 3's CPU meter and a cabinet
IR on the captured input. NAM tests 1 and 2 (`NAM_TEST.md`) showed that a NAM amp does not fit beside the SP's own
audio (NAM alone 72% of a block on average, 94% at its peak, from SDRAM). The cabinet alone does: with the Gt Amp Sim
as the input FX and its own speaker (SP SW) off, the SP's amp plays through the IR.

## What runs

- **The cabinet:** NAM test 2's (`cabtest/cab.c`): a uniformly partitioned convolution, 64-frame partitions,
  128-point real FFTs as 64-point complex ones, 65 bins, overlap-add; 1,024 taps (21 ms).
- **The IR:** the stand-in made from filters (low cut 80 Hz, +4 dB at 120 Hz, -4 dB at 450 Hz, +3 dB at 2.5 kHz, a
  4th-order roll-off at 5 kHz, faded, its loudest frequency at 0 dB), or a WAV given to the builder (`--ir-wav`: any
  rate, PCM or float, its first channel, resampled to 48 kHz with a windowed sinc, cut to 1,024 taps with a 64-tap
  fade, its loudest frequency at 0 dB). It stays in flash after the image; the UI task copies it in at the start.
- **Where:** after every RX block (bounce's rx bridge, `diag_rx`): the RX pair the recorder feed copies
  (`0x202ad0a0`), (L + R) / 2, through the cabinet; TX adds the result one block later to the DRY pair of TX line 3 at
  x 16384 (-6 dB at the stems' scale), clipped to 20 bits. With ROUTING on Mix the return comes back into the capture at
  most half as loud: it fades instead of feeding back (NAM's +23 dB was what made Mix dangerous).
- **When:** while the meter's readout is shown (hold EXIT a second on the main screen).
- **Memory:** in the module (no pool block): `ct_block`, 24,608 bytes (the cabinet 17.4 KB, the IR copy 4 KB, buffers,
  a 2 KB stack for `cab_fp_call`, which saves FPSCR and d0-d15). The module, 36,544 bytes, is in NAM's slot
  `0x83FC9000..0x83FD4000`.
- **Guard:** a RUN step over a whole block, or mixer + cabinet over 9/10 of one twice in a row, stops it (SLOW).

## Checked in the emulator (not on hardware)

`python synth/test_cab_test.py OUT_DIR --kits kits-v9.46-test3/kits-manifest.json`: NAM test 2's meter checks
(imported) on this image, and the cabinet on Unicorn's Cortex-M7 model: the output equals a direct convolution with
the IR to 1.2e-7; ct.out = the output x 16384; TX adds it to DRY L/R once; s0-s31, FPSCR and r4-r11 kept; 844 bytes
of the own stack, 24 of the task's; stop and restart afresh; the SLOW rules; a non-finite tap gives BAD; the whole
mixer with a block ready is the parent's TX plus exactly that block; `diag_rx`/`diag_ui` still run bounce's own.
77 checks. A RUN step is 35,284 instructions: 4.4% of a block at one a cycle, about 10% at the 2.3 cycles an
instruction NAM test 2 showed for SDRAM code.

## Not known (the hardware test)

- Whether the capture follows the input FX: the cab copy should sound like the Gt Amp Sim's amp.
- Whether EXT SOURCE off keeps the capture while the direct sound goes, or failing that, whether the input on a
  muted bus (MUTE BUS) does.
- The real cost on the unit (the CAB line).

## Test 1 on the unit (2026-10-24)

`MIX 10/11 T27`, `CAB 15/16 (17) RUN`, `IN23 LV0 X1`, `IR 1024 S`, `MAX 30 F1`, `CLK 599* OVR 0`; one sound heard,
nothing with EXT SOURCE off. The cabinet costs 15-17% of a block (about 3.4 cycles an instruction) and fits. But LV0
while playing, on ROUTING ExtIn: the capture was empty (IR test 3, before ROUTING was changed, read LV42 with the Gt
Amp Sim). The recorder feed `0x1ca80` copies one of the 8 stereo pairs in the RX packet (32-byte frames): pair 1 when
settings+0x64 is set, else the pair numbered by the byte at `0x82e0e974`; on ExtIn that pair is silent outside
sampling, it seems.

## Test 2 (cab-test2)

The readout shows each RX pair's peak (`A` pairs 0-3, `B` pairs 4-7) since the last refresh, read from the packet the
feed read: `diag_rx` is now a naked entry that takes the packet from the audio task's registers as its RX site
`0x1d0b4..0x1d0be` leaves them (r9 the banks, [r6 + 4] this block's bank, packet = r9 + bank << 11; the builder guards
those instructions, bounce's bridge and the feed keep r6 and r9). The cabinet still takes the feed's copy. The test:
the A/B lines while playing on ExtIn with EXT SOURCE on and off, on Mix, and with the Gt Amp Sim's GAIN changed, to
find the pair with the input after the input FX that EXT SOURCE does not mute. APP1 `4c3acaf8...d1f`; 80 checks.

## Test 2 on the unit (2026-10-24)

The A/B lines while playing (Gt Amp Sim, SP SW off): ExtIn with EXT SOURCE on `A 27 14 0 0  B 0 0 0 0`; ExtIn with EXT
SOURCE off all zero; Mix with EXT SOURCE on `A 28 13 0 0  B 0 0 0 0`. Only pairs 0 and 1 carry the guitar, and EXT
SOURCE off silences both: the input is muted before the effects chip sends it on, so no pair has it then. Still open:
which of the two is after the Gt Amp Sim (its GAIN), and whether MUTE BUS (the input on BUS 1) or the input LEVEL at 0
silences the output but leaves a pair carrying the input.
Then: the Gt Amp Sim's GAIN changes both pair 0 and pair 1 (both are after the input FX); MUTE BUS with the input on
BUS 1, and the input LEVEL at 0, each leave all 8 pairs at 0. So every mute the user has silences what the main
processor receives as well. Last cheap check: the input on BUS 1 with BUS 1's effect cutting everything (Isolator,
all bands down) and MUTE BUS off: if the pairs keep the guitar while the speakers go quiet, they are taken before the
bus effects and the cabinet can be heard alone.
The check: the input on BUS 1, the Isolator on BUS 1 with all bands down, MUTE BUS off, ROUTING Mix: all 8 pairs at 0
and nothing heard. The effects chip hands the main processor the input only after the bus effects, i.e. only what is
played anyway.

## Conclusion (2026-10-24)

On this hardware a cabinet IR (or an amp) on the main processor cannot replace the Gt Amp Sim's sound: every way to
silence the direct sound (EXT SOURCE, MUTE BUS, input LEVEL, a bus effect) also silences what the main processor
receives, so the processed copy can only be heard on top of the original, 2-3 ms later. With NAM too heavy (72-94% of
a block) the live "your own amp and cab" idea ends here. What the work leaves: the cabinet costs 15-17% of a block on
the unit and works on anything the main processor renders itself (the pads); the CPU meter; the RX pair map.

## Reopened (2026-11-03): ROUTING ExtIn

The checks above ran on INPUT SETTING's ROUTING Mix (SHIFT + EXT SOURCE, CTRL 2). On Mix, RX pair 0 is the mix as
heard; on ExtIn it is the input alone after the input FX (manual p. 36). This turned up through the guitar synth's
stuck notes (`TUNE_TEST.md`, synth test 4).

The check, with gtr-synth-test4's readout (LV is pair 0's peak): ExtIn, the input on BUS 1, the Isolator on BUS 1
with all bands down, playing. The user's report: "lv moves!". So on ExtIn the main processor gets the guitar before
the bus effects, while the cut bus silences the direct sound. A cabinet on DRY could then be heard alone, about 3 ms
after the pick: the conclusion above holds only for Mix.

A cabinet test 3 must take pair 0 straight from the RX packet, as the tracker does. The recorder feed's copy that
tests 1 and 2 used was empty on ExtIn outside sampling. Pads on BUS 1 would be cut with the direct sound, so they
belong on BUS 2 or DRY. NAM stays too heavy.
