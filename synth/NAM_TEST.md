# NAM test 1 (nam-test1): a NAM amp and a cabinet IR on the main processor

A test-only build, not for the patcher: v9.50 (combined-test11) with IR diagnostic test 3's CPU meter, and in place
of its echo a NAM amp and a cabinet on the captured input. It answers on the unit what IR diagnostic test 3 could
only bound: whether the SP's main processor runs a NAM amp in time, with the code and its memory where this fork
can put them, and how it sounds through the DRY return.

## What runs

- **The amp:** TONE3000's A2-Lite engine for the Cortex-M7 (tone-3000/embedded b84b60c, 2.0.0, MIT), unchanged,
  with its example capture (NeuralAmpModelerCore's A2-Lite test model, MIT). 1,871 weights, a 6,346-sample receptive
  field; TONE3000 measured 4,059 cycles a sample on a 480 MHz Daisy Seed with its code in ITCM.
- **The cabinet:** a uniformly partitioned convolution (64-frame partitions, 128-point FFTs, overlap-add: the
  algorithm of Codex's offline sp_cab_partitioned.c), 1,024 taps. The IR is a stand-in made from filters (low cut
  80 Hz, +4 dB at 120 Hz, -4 dB at 450 Hz, +3 dB at 2.5 kHz, a 4th-order roll-off at 5 kHz, faded out, its loudest
  frequency at 0 dB), not a measured cabinet.
- **Where:** after every RX block (bounce's rx bridge, `diag_rx`): the RX pair the recorder feed copies
  (`0x202ad0a0`), (L + R) / 2 at full scale = 1.0, through the amp and the cabinet; TX adds the result one block later
  to the DRY pair of TX line 3 at x 8192 (-12 dB at the stems' scale, as test 3's echo), clipped to 20 bits. With the
  Gt Amp Sim as the input FX (system `0x27c[0]` = 23) the amp is left out and the Gt Amp Sim's own sound goes
  through the cabinet.
- **When:** while the meter's readout is shown (hold EXIT a second on the main screen). Hiding it stops NAM.

## Memory

| What | Where | Size |
| --- | --- | --- |
| The module (integer side, FPU side, engine, cabinet, reader) | boot copy row `0x83FC9000`, between the kits' last zero row (`0x83fc8450`) and sg-subpad's row (`0x83fd4000`) | 42,948 bytes |
| The capture (.namb) and the IR (float32) | flash, after the image, in the MPU's cacheable read-only flash region; not copied at boot | 7,980 + 4,096 bytes |
| Weights, engine instance, its ring buffers (109 KB), the cabinet's spectra, buffers, a 4 KB stack | one block from the SP's first application pool, taken by the UI task when NAM starts, given back when it stops | 159,648 + 32 bytes |

No fixed SDRAM area of that size is free: the stock image's own rows, the native engine's buffers
(`0x8383a424..0x83f7a424`) and the fork's modules fill the rest. The block comes from the pool the stock malloc uses
(`0x80245820` = pool 1), through the pool's own get (`0x800d2f1e`, wait 0) and release (`0x800d2f28`): the stock malloc
`0x800e2c68` calls an error report (`0x800254f8`) when it fails, the get only returns an error. The readout shows the
pool's free memory (the query `0x20a4`: the free list summed, the largest piece).

## The FPU

The audio task's code is integer, but the task itself is created as an FPU task: `inittsk`'s descriptor at
`0x1fa74` has attribute `0x1001`, and the kernel's task switch (PendSV `0xdd3c`) saves and loads s16-s31 for a task
whose TCB+0x10 has `0x1000`. The readout's F flag shows the running task's attribute on the unit. Even so, every FPU
step goes through `nam_fp_call`, which runs it on the block's own stack with FPSCR and d0-d15 saved around it and
FPSCR set to round to nearest, flush to zero and default NaN (denormals are slow on the M7, and TONE3000's notes ask
for both). The builder checks that nam_test.c's functions (the meter's hooks, the UI and the RX/TX glue) and the
compiler helpers the link pulls in have no FPU instruction; only nam_fp.c, cab.c and the engine do.

## Steps

One step per RX block: LOAD1 checks the capture the UI copied in (A2-Lite, 48 kHz, CRC) and loads it; LOAD2 transforms
the IR; LOAD3 binds the engine (clearing its state, where both copies were); WARM runs 6,347 samples of silence, 64 a
block (100 blocks, the engine's own prewarm one call at a time); then RUN. A WARM or RUN step over 3/4 of a block, or
two wakes in a row whose mixer and NAM took over 9/10 of one, stop NAM (SLOW) so the audio task cannot starve the
others; the readout shows the wake that stopped it. A damaged capture gives BAD, a failed get MEM!.

## Checked in the emulator (not on hardware)

`python synth/test_nam_test.py OUT_DIR --kits kits-v9.46-test3/kits-manifest.json --zig ZIG`: the meter's checks as
in IR diagnostic test 3 (Unicorn's default CPU), and NAM on Unicorn's Cortex-M7 model (it has the FPv5 VFMA and
VMAXNM the engine uses):

- the UI's block: one get (pool 1, 159,680 bytes, wait 0), aligned to 32, cleared, the capture and the IR copied in;
- three loading steps, then 100 prewarm blocks whose result equals `nam_a2lite_prewarm` byte for byte;
- 40 blocks of TONE3000's golden input: the amp's output equals the same engine built for the PC (C tiles, FMA) bit
  for bit; the cabinet's equals a direct convolution to 2.4e-8; nt.out = the float output x 8192; TX adds it to DRY
  L/R only, once;
- s0-s31, FPSCR and r4-r11 as they were after every step; the step uses 776 bytes of its own 4 KB stack, the audio
  task's stack 24 bytes;
- the Gt Amp Sim gives the cabinet alone; hiding the readout stops NAM and the block goes back; the SLOW rules; MEM!;
  BAD; the whole mixer with a block ready is the parent's TX plus exactly that block; `diag_rx`/`diag_ui` still run
  bounce's own `bnc_rx`/`bnc_ui`.

A RUN step is 388,465 instructions (NAM and the cabinet), 49% of an 800,000-cycle block at one instruction a cycle.
The M7 issues two instructions a cycle at best; TONE3000's 4,059 cycles a sample is 259,776 a block (32% at 600 MHz)
with the code in ITCM. Here the code and the data are in SDRAM behind the caches.

## Not known (the hardware test)

- The real cycles with the code and the 109 KB of ring buffers in SDRAM: the readout's NAM line.
- Whether EXT SOURCE off keeps the capture while the direct input goes (then NAM can replace the clean signal).
- Whether the capture follows the input FX (test 3 read LV90 on the main screen, LV42 with the Gt Amp Sim).
- How much of the pool the SP really has free (POOL), and whether the DTCM past its pools is unused (D: words not zero).

## Test 1 on the unit (2026-10-24)

NAM SLOW 109 at once, at the first prewarm step. The box: `MIX 8/10 T0`, `POOL 2528/2528`, `MAX 109 D999 F1`,
`CLK 599* OVR 1`. So the audio task is an FPU task (F1), and the pool has 2.5 MB free in one piece. The DTCM past the
stock pools is not empty (D999): the audio task programs the eDMA's TCDs (`0x400e9000`, +0x20, +0x40, +0x60) with
buffers at `0x20000000 + (n << 12)` in 8 KB steps (ITCM `0x1cff6`, SDRAM `0x80003420`), so the audio DMA buffers live
there. The OCRAM at `0x20200000..0x2023f000` is the kernel's own memory (the free-list primitives `0xd3e4..0xd5ba`
serve the pool services). NAM's data stays in the SDRAM pool.

## Test 2 (nam-test2)

- The engine called `fmaf` about 9,800 times a block: Clang turns `__builtin_fmaf` into a library call under
  math-errno (its default; TONE3000 builds with GCC and -ffast-math). `-fno-math-errno` makes it a VFMA: the k6 kernel
  went from 7,986 to 5,560 bytes, a RUN step from 388k to 319k instructions, still bit-identical to the host engine.
- The cabinet uses real-input transforms: each 128-point real FFT is a 64-point complex FFT and a fix-up, and only
  the 65 non-redundant bins are kept and multiplied. A RUN step: 282k instructions; the spectra 32 to 16 KB.
- WARM starts with 8, 16 and 32 samples (the caches start cold): 102 steps; the state still equals
  `nam_a2lite_prewarm`'s byte for byte.
- SLOW: a step over the whole block, or mixer + NAM over 9/10 of it twice in a row. NAM's window is 75 blocks and is
  published when it stops, so the box says how fast it was. The DTCM census is gone.
- APP1 `4c808fc4...dc6bb`; module 40,128 bytes; pool block 143,520 bytes; 94 checks pass.

## Test 2 on the unit (2026-10-24)

`MIX 8/10 T105`, `NAM 72/94 SLOW`, `IN0 LV0 X1`, `POOL 2527/2527`, `MAX 105 F1`, `CLK 599* OVR 2`. The prewarm ran
(NAM's window was published): NAM alone averages 72% of a block and peaks at 94%, about 9,000 cycles a sample
(TONE3000: 4,059 on a Daisy Seed with its code in ITCM and its hot data in DTCM). With the mixer's 8-10% two wakes in a
row went over 90%, and the guard stopped it. At about 250k instructions a step that is 2.3 cycles an instruction: the
code and all of NAM's data are in SDRAM, the only memory free for it (the DTCM tail holds the audio DMA buffers, the
OCRAM heap is the kernel's). Inline FMAs and the real-input cabinet did not change the conclusion: A2-Lite needs
most of the main processor, more than the SP can spare beside its own audio. The cabinet alone (64-frame partitioned
convolution, about 30k instructions a block) is the part that fits.
