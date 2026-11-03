# Note tracker tests 1 and 2 (tune-test1, tune-test2): which note the guitar plays

Test-only builds, not for the patcher: v9.52 (combined-test17) with the CPU meter of IR diagnostic test 3 and a
note tracker on the input. Test 2 is test 1 with a new pluck test and the plucks heard on the readout (see "Test 1 on
the unit" below). The first step towards a guitar synth (the Sound Generator played from the guitar): how
well and how fast the SP's main processor can follow the note. Nothing goes to the output; the meter's readout (hold
EXIT a second on the main screen) shows what the tracker hears.

Cabinet test 2 (`CAB_TEST.md`) found the input in RX pairs 0 and 1 only, after the input FX, the bus effects and
every mute. A tracker only listens, so that is enough: the guitar must be heard anyway.

## What runs

- **Where:** after every RX block (bounce's rx bridge, `diag_rx`): pair 0 of the packet, (L + R) >> 1, into
  `tt.in` (`tune_pairs`), then one step of `tunetest/tune_fp.c` on the module's own stack (`tune_fp_call`, FPSCR and
  d0-d15 saved), while the readout is shown.
- **The signal:** a 4th-order Butterworth low-pass at 1.6 kHz, every 4th sample into a 512-sample ring at 12 kHz.
- **The pluck test (test 2):** a block's peak at 12 kHz at least -48 dBFS and twice the highest of blocks 3-18 back,
  24 blocks (32 ms) after the last pluck. Those 16 blocks (21 ms) are longer than the lowest string's period (B1
  16 ms), so a ringing string's peaks never jump: while one rings, a block's peak stays under 1.12 x the reference
  from B1 to E6, clean or overdriven, bridge or neck pickup (`tune_ref.guitar`). The cost: picking a string again
  while it still rings loudly is no new pluck until it has faded to about half (the steady note still follows a new
  pitch without a pluck). Test 1's: a block's energy over 4 x the average of blocks 5-12 back, at least -54 dBFS.
- **An analysis every 4 blocks (5.3 ms),** spread over them: YIN at 6 kHz on every other sample of the newest 400
  (copied at the first block), lags 1-100 (60 Hz up) over a 100-sample window, 25 lags a block; at the fourth block
  the cumulative-mean normalisation, the first dip under 0.2 from lag 4 (1.5 kHz) on, else the deepest; refined at
  12 kHz around twice that lag (7 lags, a 200-sample window, a parabola, its vertex within a lag); above 1 kHz, half
  that lag wins when it is as deep within 20% (at 6 kHz a period under 6 samples falls between the lags and YIN's
  first dip is twice it: E6 read as E5 without it).
- **The result:** voiced at -54 dBFS RMS and an aperiodicity under 0.35; the steady note once two voiced analyses in
  a row agree, gone after 4 unvoiced ones; after a pluck, the ms to the first voiced analysis and to the steady
  note. An analysis whose samples were taken before the pluck's block only shows its numbers (the string before may
  still ring: without this a new pluck could go steady on the old note at once).
- **Memory:** `tt_block` in the module (6.7 KB: the ring, an analysis' span, the difference functions, 32 block
  peaks, a 2 KB stack); the module in NAM's slot `0x83FC9000..0x83FD4000`.
- **Guard:** a step over a whole block, or mixer + tracker over 9/10 of one twice in a row, stops it (SLOW).

`tunetest/tune_ref.py` is the same tracker in Python, and makes the test strings: up to 12 decaying harmonics at an
exact frequency with a noise burst at the attack, clean or overdriven (tanh); and since test 2 a string through a
magnetic pickup (`guitar`: released from rest, the pickup sensing its velocity, so every harmonic in sine phase and
the wave pulse-like as a real pickup's; stiff-string inharmonicity, higher harmonics dying faster, the pickup's
resonance, a slow beat, hiss and hum), played as the hardware test plays it (`open_strings`: each open string rung
1.5 s and stopped by hand).

## Readout

    E2 +3c Q92        the steady note (-- none); the newest analysis: cents off its nearest note, quality
    82.4Hz LV45 X1    the newest analysis' frequency, pair 0's peak in % of full scale, EXT SOURCE
    1ST 21 LCK 27     the last pluck: ms to the first estimate, ms to the steady note
    AVG 25 N12 P14    the average ms to the steady note over N plucks since the readout came on; P plucks heard
                      (a hand stopping a string may count; test 1 showed the input FX, IN23, in its place)
    TRK 4/6 MIX 9     the tracker's average/peak per RX block (OFF, SLOW), the mixer's average, % of a block
    MAX 30 OVR 0      the worst wake since the readout came on (%); wakes whose mixer + tracker took over a block

Every 0.1 s while the tracker runs, else with the meter's half-second window.

## Test 1 on the unit (2026-11-03)

The six open strings once each, low to high, each stopped by hand before the next, the box shown afresh:

- **N51, AVG 12; LCK 11 after the low E.** Phantom plucks: a ringing string kept making new ones, and each went
  steady at once on the note already followed (the earliest a steady note can come after a pluck is 9-13 ms: the
  analyses finishing under 3 blocks after it do not count, then two must agree). An RX block is 1.33 ms, a ninth of
  the low E's period, and a pickup's wave is pulse-like: a ringing string's block energies swing far more than 4 x
  within a period. `tune_ref.guitar` gives the same: test 1's pluck test counts 14-15 plucks on `open_strings`
  (the phantoms going steady in 9-13 ms), test 2's 6.
- **MAX 19 dry, 21 with the Gt Amp Sim; OVR not reported.** The worst wake, the mixer and the tracker, about a fifth
  of a block: the estimate of about 11% for the tracker at 3.4 cycles an instruction holds.
- **TRK moves all the time:** as it should, it is the last tenth of a second's average/peak.
- Not reported: whether the notes were right.

## Checked in the emulator (not on hardware)

`python synth/test_tune_test.py OUT_DIR --kits kits-v9.46-test3/kits-manifest.json`: NAM test 2's meter checks
(imported) on this image, and the tracker on Unicorn's Cortex-M7 model, against `tune_ref.py` after every block.
90 checks pass on `release/tune-test2` (APP1 `68691893…96d2`, 3,179,808 bytes; the module 22,144 bytes); test 1
passed 87 on `release/tune-test1` (APP1 `7cd37ebf…17cb`):

- The module and `tune_ref.py` agree after every block on four phrases played one at a time (B1 D2 E2 A2, D3 G3 B3
  E4, A4 E5 A5 E6, and E2 E3 E4 E5 overdriven), one legato, and (test 2) the hardware test's run twice, clean on a
  bridge pickup and overdriven on a neck pickup: the steady note, the plucks, the times and counts; the frequency
  within 0.1%.
- Every note played one at a time is one pluck and its string's note, within 3 cents 150 ms after it goes steady
  (the pickup's strings within 15: a stiff wound string's overtones run sharp, its low E reads 8-12 cents sharp).
  The hardware test's run: 6 plucks and 6 steady notes, AVG 22 (E2 28, A2 31, D3 21, G3 19, B3 20, E4 17 ms); test
  1's pluck test counts 14-15 plucks there. `tune_ref.py` alone, every semitone B1-F#6 clean and overdriven: the
  right note, within 2 cents then; at the moment it goes steady the low notes read up to 11 cents sharp (the attack).
- The steady note 15-32 ms after a pluck (high notes first, B1-E2 about 31 ms), the first estimate 9-27 ms.
- A second of noise gives no note. Legato (the string before still ringing) is a mono tracker's weak spot: the test
  makes no claim on its notes (test 2 hears one pluck of its four; the steady note still follows).
- A step: 14,739 / 12,410 / 12,410 / 26,124 instructions by phase (test 1: 14,579 / 12,250 / 12,250 / 26,075; 3.3% of
  a block at one a cycle, about 11% at the 3.4 cycles an instruction the cabinet showed on the unit; test 1 on the
  unit: the worst wake, mixer and tracker, 19-21%). 240 bytes of its own stack, 28 of the task's.
- FPU and callee-saved registers kept; stop, restart afresh, the SLOW rules; diag_rx with the RX site's registers
  takes this block's bank; the readout every 0.1 s while results come, and `--` before the first analysis (its first
  post comes before tune_ui starts the tracker: an all-zero result read C-1); bounce's own bnc_rx and bnc_ui run as
  in the parent; the meter's checks.

## Not known (test 2 on the unit)

- Whether the notes are right on a real guitar (test 1's report did not say).
- The real times from a real pluck (AVG over the six open strings: 22 here), and whether N and P are 6.
- Re-picking a string that still rings: no new pluck until it has faded to about half. For the synth step a pick's
  click (the highs, which a ringing string loses fast) may tell a re-pick: it needs a real guitar's numbers.
