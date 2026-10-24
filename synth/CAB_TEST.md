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
