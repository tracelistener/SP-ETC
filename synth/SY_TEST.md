# SY synth tests 1 and 2: a polyphonic guitar synth, the way BOSS's SY pedals do it

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

## On the unit (2026-11-04)

"OMG IT works really well!" So the method carries over from the model guitar to a real one: the real partials,
pick noise and hum gave no trouble the user mentioned. No details yet on chords, low notes or the readout's numbers.

## SY synth test 2 (sy-synth-test2): 15 tones

The user asked how the synth could make many sounds without the Sound Generator, and what BOSS's pedals offer (the
SY-1's 121 sounds in 11 types, the SY-200's 170 in 12 groups, the SY-300's three oscillators, filters, LFOs and step
sequencer), then said "Build it".

- **Picking:** push the VALUE knob in, keep it held, and press pad 1-16, where the synth can play. A popup names the
  tone, for example `SY 4 SUPERSAW`. The pad's press and release go no further, so no sample plays. Pad 16 is
  `SY OFF`: the synth fades out and stops, and any other pad starts it again on that tone. A new tone fades the
  output out over 8 blocks, switches, and fades it in again. The filter, the LFO, the pick envelope and the gate
  start from rest; the bands' analysis goes on.
- **How the keys arrive:** v9.52's FX deep edit already hooks the UI dispatcher's key press and release handlers
  (0x8003abd0, 0x8003ada0). Each jumps to a bridge in its module, which calls its handler with `bl`. The builder
  re-points those two calls to `sy_key_down` / `sy_key_up`.
  - A press goes to FX deep edit's handler first. If FX deep edit doesn't take it, VALUE + pad picks a tone.
  - A release of a pad whose press the pick took is taken too. Any other release goes to FX deep edit's handler.
  - Where the synth can't play (ROUTING Mix, the Sound Generator page), VALUE + pad goes on as before.
- **The tones** (`sy_ref.TONES`, written into `sy_tables.h`):

  | Pad | Tone | Recipe |
  | --- | --- | --- |
  | 1 | SAW LEAD | test 1's sound |
  | 2 | SQUARE | a square through a low-pass, 400 Hz-4 kHz, Q 1.5 |
  | 3 | PULSE | a 25% pulse, 500 Hz-6 kHz |
  | 4 | SUPERSAW | two saws 12 cents apart; 20 ms attack, 150 ms release |
  | 5 | PAD | two saws 9 cents apart; 350 ms attack, 900 ms release; a dark filter swept by a 0.25 Hz LFO |
  | 6 | STRINGS | a saw; 160 ms attack, 450 ms release; 5.5 Hz vibrato |
  | 7 | ORGAN | a sine plus a sine an octave up; a rotary-like 6.5 Hz vibrato and tremolo |
  | 8 | FLUTE | a sine with breath noise; 60 ms attack, vibrato |
  | 9 | BELL | FM: a sine whose phase a sine at 3.5 x moves, the index raised at each pick; 900 ms release |
  | 10 | BRASS | a saw; 35 ms attack; a filter envelope at each pick (+1.6 octaves, 260 ms) |
  | 11 | BASS | a square plus a triangle an octave down; a low filter, 150 Hz-1.5 kHz |
  | 12 | SWEEP | a saw through a resonant low-pass (Q 5) swept by a 0.35 Hz LFO |
  | 13 | WAH | a saw through a band-pass (Q 4) that the playing and each pick open |
  | 14 | SEQ | a saw plus a triangle an octave down, gated by a 16-step pattern at 1/16 of the SP's tempo |
  | 15 | WARM | a triangle plus a sine an octave down; a soft filter |

  The gains bring each tone's level on a strummed chord to within about 1 dB of the saw lead's. Exceptions: the
  bass is 1.7 dB louder, the gated SEQ and the wah somewhat quieter.
- **The engine's additions** (each in sy_fp.c and the same in sy_ref.py):
  - two waves a band, with polyBLEPs on the saw and the pulse;
  - attack and release per band;
  - a pick detector (the tracker's test 2 rule) driving a filter envelope and the FM index;
  - an LFO for vibrato, tremolo and cutoff;
  - breath noise;
  - band-pass and high-pass;
  - the step gate. The SP's tempo is read every 0.1 s as the arp reads it (the stock sample tempo 0x80047dd0 for
    the first pad of the bank on the pads).
- **Releases cost bands:** with releases, every brief owner left a tail when ownership flickered between
  neighbours, so a strummed chord kept 18-26 bands running instead of 9-12, at worst 36. Now:
  - a band that sounded under 32 ms stops at once;
  - a band taking over its neighbour's partial takes the neighbour's phases, amplitude and age, and the neighbour
    stops;
  - a release ends at 1e-3 of full scale.
- **Cost:**
  - The first build of the tones took up to 161,582 instructions a step (the bass) with one oscillator loop for
    every wave.
  - Each wave now has its own loop, one pass for wave A and one for B, and the bass and SEQ sub-octaves are
    triangles.
  - The most a step takes is now 80,008 (the FM bell, 10% of a block at one a cycle). Others: supersaw, pad and organ
    about 71,000, bass 72,840, square and pulse 58,500, saw lead about 51,000.
  - The module is 43,104 bytes of 45,056; `sy_block` is 2,560 bytes, with no stack of its own: the engine runs on
    the tracker's.
- **Demos:** `release/sy-synth-test2/demos/sy2-NN-name.wav` holds each tone on the model guitar, through the twin:
  single notes, a strummed G, a picked C, a bend.
- **Emulator checks:** 250 pass on `release/sy-synth-test2` (APP1 `8f0f9f08…5942c`, 3,200,768 bytes). The SY
  section has 94 of them, 16 for test 2:
  - every tone equals `sy_ref.py` value for value on a strummed chord and a bend (15 x 712 blocks; the SEQ tone at
    the stub's 120 BPM);
  - VALUE + pad 4 picks SUPERSAW: FX deep edit's handler is asked first, the popup reads `SY 4 SUPERSAW`, and the
    press and its release are taken;
  - a pad without VALUE, and VALUE + another key, go on to FX deep edit;
  - pad 16 fades the synth out and stops it, and pad 7 starts it again on tone 7;
  - on ROUTING Mix or the Sound Generator page, VALUE + pad goes on to the page;
  - the popups fit the screen (widest 94 px);
  - a tone change mid-chord fades out over 8 blocks, switches and fades in, equal to the twin throughout;
  - the builder's two calls are in FX deep edit's bridges.
  - The meter's popup-tick entry check no longer compares LR at the resume point. Bounce's bridge saves LR before
    calling diag_ui, so LR is dead there, and since test 2 diag_ui's last call (the tempo read) leaves its own.

## Still not known

- How each test 2 tone sounds on a real guitar, and which are worth keeping.
- The heavier tones' cycles at SDRAM speed (the readout's SY line): the FM bell, supersaw, pad, organ and bass take
  about 1.4-1.6 times the saw lead's instructions.
- Whether anything on the unit uses VALUE + pad (nothing in v9.52's modules does; stock is not known to).
- How the low notes' 20-30 ms feel in longer playing (nothing was reported against them).
- Whether the synth's level against the dry guitar is right. There is no level control yet; the test's output peaks
  near -6 dBFS.
- Whether MUTE BUS on ExtIn also keeps pair 0, which would be a simpler way than the Isolator to hear the synth
  alone.
