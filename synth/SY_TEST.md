# SY synth test 1: a polyphonic guitar synth, the way BOSS's SY pedals do it

The user asked (2026-11-04) for the guitar synth to work "however boss sy-1/200/300/1000 does it with guitar input".
Guitar synth tests 1 to 6 (`TUNE_TEST.md`) find one note and play it on the Sound Generator, which has four voices
and is mono there. BOSS's SY pedals find no notes at all. Roland's patent US 9,542,923 ("Music synthesizer",
inventor Yukio Shigeno, filed 2015-09-29; it cites the SY-300's announcement) describes the method:

- the guitar is split into 49 band-pass filters a semitone apart, E2 (82.4 Hz) to E6 (1,318.5 Hz) for a guitar;
- each band's pitch comes from the intervals between its zero crossings, finer than a semitone, and its level from
  an envelope;
- each band drives an oscillator of its own (saw, square, sine) at that pitch and level;
- the bands are summed and go through a filter whose cutoff follows the playing (DYNAMICS).

A chord's strings land in different bands, so they play together. Harmonics drive oscillators too, which is part
of the sound. The patent does not give the band-pass filters' bandwidth or order, nor what happens when two partials
share a band. Those are this test's own choices, made on the model guitar (`tunetest/tune_ref.py`'s strings).

## The engine (`tunetest/sy_fp.c`; `tunetest/sy_ref.py` is the same in Python)

One step per RX block (64 frames, 1.33 ms), from RX pair 0's (L + R) / 2, which the tracker also reads:

- **Input:** a 4th-order Butterworth low-pass at 2 kHz, then every 4th sample (12 kHz, 16 a block). A peak follower
  falling with a 0.3 s time constant gives the playing's level.
- **Bands:** two band-pass stages per band, a 4th-order band-pass. Q is 8 at E2, rising to 16 at E4 and above. Each
  stage runs at 0.6436 x that Q, so the pair has one stage's -3 dB bandwidth.
  - Two stages leak half as much as one from strings 3-5 semitones away. With one stage and everything else as here,
    the beating of a chord's strings pulls the band pitches about: 96.2% of the sound sits on the chord's partials,
    10 cents RMS off, against 99.5% and 6 cents with two. One stage is faster, though: the low E reaches half its
    level 18 ms after the pick instead of 30. That is the first setting to change if low notes feel late.
  - Each band also keeps its energy, followed over 1.5 of its periods and at least 2 ms.
- **Pitch:** positive zero crossings. One counts once the band has gone below -0.25 x its level, and is placed by a
  straight line between its two samples.
  - A period within 300 cents of the band's centre feeds an alpha-beta tracker (0.2, 0.02), which starts at the
    centre when the band wakes.
  - The tracker smooths the beating of strings ringing together, and follows a bend without the 30-cent lag of a
    plain average.
  - A band under -60 dBFS sleeps, and measures again when it wakes.
- **Which bands sound:** a band sounds when it has counted two periods, its energy tops both neighbours', and its
  pitch is within 80 cents of its centre.
  - A partial then sounds from one band; its neighbours read the same pitch, weaker.
  - Bands between two partials stay silent: their crossings follow neither. Without this rule they play at about
    -12 dB: 84% of a chord's sound lands on its partials, with twice the bands sounding.
  - A band that starts to sound while a neighbour stops, on the same pitch within 1%, takes that neighbour's phase,
    so a bend hands its partial from band to band without a gap.
- **Oscillators:** a saw per sounding band (a ramp -1..1 with a polyBLEP at the wrap), at (level - floor) x 1.2,
  ramped over the block. They are run two bands at a time, which reads and writes the sum once for both.
- **Output:**
  - The sum goes through a resonant state-variable low-pass (Q 2). Its cutoff runs from 300 Hz (quiet) to 5 kHz (a
    hard pick), following the square root of the level over 0.25, on an exponential sweep.
  - Then a soft clip: 1.5x - 0.5x^3, and +-1 beyond.
  - The result is scaled x 16384: the clip's ceiling is -6 dBFS on the DRY stem, as the cabinet test's output was.
- **Arithmetic:** single precision, with no contraction: every fused multiply-add is an explicit `fmaf`. The Python
  twin rounds the same way (fmaf through double), and the module's output equals it value for value.

The tables (filter coefficients, period ranges, constants) come from `sy_ref.tables()`. The builder writes them into
`sy_tables.h` as hex floats, so the C and the twin share every number.

## Where it plays

- **When:** on every page but the Sound Generator's, while EXT SOURCE is on and ROUTING is on ExtIn. The Sound
  Generator page plays guitar synth test 6 as before.
- **Why not on Mix:** on Mix the effects chip hands back the mix as heard, so the engine would hear its own sound on
  DRY. The popup that test 5 showed on the Sound Generator page now shows on every stock page, once each time EXT
  SOURCE goes on with ROUTING on Mix.
- **Output:** the engine's block is added to TX line 3's DRY pair one block later, as the cabinet test's was. On
  ExtIn the direct guitar still plays on its bus. To hear the synth alone, put the input on BUS 1 (REMAIN + EXT
  SOURCE, lit) and cut BUS 1 with the Isolator. On ExtIn, pair 0 keeps the guitar past a cut bus (`CAB_TEST.md`,
  "Reopened").
- **Stopping:** leaving the conditions fades the output out over 8 blocks (10.7 ms), then the engine stops. Starting
  again clears it.
- **SLOW:** it stops itself when one step takes over a whole block, or when the mixer, the tracker and the engine take
  over 9/10 of one twice in a row.
- **Readout:** the CPU meter's readout (hold EXIT for 1 s on the main screen) shows the engine on line 3 as
  `SY avg/peak Bn`: its average and peak per RX block over the last 75 blocks, in % of a block, and the bands
  sounding. It shows `SY OFF` or `SY SLOW` otherwise. The line held test 6's pluck times before. MAX and OVR are now
  the worse of the tracker's wakes and the engine's.

## On the model guitar (the twin)

| | |
| --- | --- |
| Single notes E2..E5, sound on the string's partials (within 30 cents) | 98.9-100% |
| Six open chords, picked 0.3 s apart and strummed 30 ms apart | 99.3-99.9%, 4.6-7.4 cents RMS, 9-14 bands sounding |
| Time from the pick to half the synth's level | E2 30 ms, A2 16, D3 18, G3 11, B3 11, E4 10, A4 8, E5 7 (the guitar's own: 2 ms) |
| Bends (a tone on G3 and A4, a semitone on B3 and A2) and vibrato (25 cents on E4) | no dip in the fundamental; it trails the bend by 11-18 cents |
| Level against the guitar's | -0.3 to -4 dB (RMS) |
| Hiss and hum alone (-74 / -66 dBFS) | silent |

Low notes are the slow part. A band narrow enough to keep a chord's strings apart builds up over several periods
of its own note, so the low E reaches half its level about 30 ms after the pick. A distorted input makes tones of its
own (sums and differences of the strings), and the bands play those too: BOSS also asks for a clean signal first in
the chain.

## Cost

- **Module:** 39,616 bytes of the 45,056 in NAM's slot. `sy_block` is 4,224 bytes: the bands' state, the
  oscillators and a 2 KB stack. The tables (1.8 KB) are in .rodata.
- **Instructions a step:** the most is 44,830 (5.6% of a block at one a cycle), on a strummed G chord with 15 bands
  sounding.
  - The 49 bands take about 17k of that, and each sounding oscillator about 1k.
  - Unrolling the band loop by two, and running the oscillators in pairs with one test for the wrap, brought it down
    from 53,248, with the output unchanged.
  - From SDRAM, at the 2.3-3.4 cycles an instruction NAM and the cabinet measured, that is 13-19% of a block. It is
    likely less, since this code keeps its work in registers.

## Emulator checks

`test_tune_test.py` section 12 (48 checks, part of the 202 that pass on `release/sy-synth-test1`: APP1
`db337f65…8fd0d`, 3,197,280 bytes; the module 39,616 bytes):

- **When it plays:** every page but the Sound Generator's, with EXT SOURCE on and ROUTING ExtIn, cleared before each
  start. Leaving that fades it out over 8 blocks, then it stops. Not on Mix, not with EXT SOURCE off.
- **Against the twin:** the module's output equals `sy_ref.py`'s, value for value, on every block of six signals:
  - four open strings;
  - a G chord strummed;
  - a C chord picked 0.25 s apart;
  - G3 bent a tone;
  - an E chord strummed and clipped;
  - hiss and hum alone.
- **Musical checks:** the bands sounding are the strings' partials (98-99% within 30 cents). Hiss alone is silent,
  and the output reaches 0 within 0.2 s after the strings stop.
- **Registers and stacks:** s0-s31, FPSCR and r4-r11 are kept, and the step runs on the engine's own stack (716 of
  2,048 bytes).
- **Output:** `sy_tx` adds the block to DRY L/R once, clipped to 20 bits, and the whole mixer gives the parent's
  output plus that block.
- **Guards:** the SLOW rules, and the instructions a step takes.

## Not known (SY test 1 on the unit)

- Whether a real guitar's partials, pick noise and hum behave like the model's. A hum harmonic above -60 dBFS in a
  band's window would play as a faint tone.
- How the low notes' 20-30 ms feel when playing.
- The engine's cycles at SDRAM speed (the readout's SY line).
- Whether the synth's level against the dry guitar is right. There is no level control yet; the test's output peaks
  near -6 dBFS.
- Whether MUTE BUS on ExtIn also keeps pair 0, which would be a simpler way than the Isolator to hear the synth
  alone.
