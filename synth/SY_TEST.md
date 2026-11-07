# SY synth tests 1 to 18: a polyphonic guitar synth, the way BOSS's SY pedals do it

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

## SY synth test 3 (sy-synth-test3): knob editing, saved

The user asked about parameter editing, then chose to include saving.

- **Editing:** hold VALUE and turn CTRL 1-3 where the synth can play. Each turn sets that knob of the picked tone to
  the knob's position (0..127; 64 is the tone as designed). A popup shows the tone, the setting and the position,
  for example `SY 4 SUPERSAW` / `DETUNE 100`. The bus effect never sees the turn, but the knob's position is shared:
  the next turn without VALUE moves the bus effect to it.
  - **CTRL 1, BRIGHT:** -2..+2 octaves on the cutoff.
  - **CTRL 3, LEVEL:** the output, 0..2x.
  - **CTRL 2, by tone** (`sy_ref.TONES` p2):

    | Tone | CTRL 2 | Range |
    | --- | --- | --- |
    | saw lead | RESO | Q x 2^(+-2) |
    | wah | RESO | Q x 2^(+-1.5) |
    | square, pulse | WIDTH | the pulse edge +-0.9 and +-0.45 |
    | supersaw | DETUNE | 12 cents x 2^(+-2) |
    | pad, strings | ATTACK | 350 ms and 160 ms x 2^(+-2) |
    | organ | ROTARY | 6.5 Hz x 2^(+-2) |
    | sweep | SPEED | 0.35 Hz x 2^(+-3) |
    | flute | BREATH | 0..2x |
    | bell | METAL | the FM depth at a pick, 0..2x |
    | brass | OPEN | the pick envelope's octaves, 0..2x |
    | bass, warm | SUB | wave B's level, 0..2x |
    | seq | RATE | 1/8, 1/16 or 1/32 |

  - A CTRL 2 at 64 leaves the tone's own value untouched. The exp2 the knobs use is a close approximation, not the
    table's exact value. Attack is computed as x - x^2/2: through exp2, 1 - 2^-x lost 40% of itself at long
    attacks.
- **How the turns arrive:** v9.52's FX deep edit also hooks the dispatcher's knob handler (0x8003a8d8). Its bridge
  calls fde_knob, and the builder re-points that call to sy_knob, which asks FX deep edit's handler first: it takes
  turns only on its own input FX screens.
- **The file:** `B:/_sy_tones.bin`, beside FX deep edit's `B:/_fx_hidden.bin`, written with the stock file calls
  FX deep edit uses. The builder checks their code, the view list call and TOP's handler against the hashes FX deep
  edit recorded.
  - 60 bytes: "SYTN", version 1, the tone picked, OFF, 15, the 45 knob positions, 3 zero bytes, and an FNV-1a of
    the first 56.
  - Read once, at the first key or knob event after the boot. EXT SOURCE has to be pressed before the synth plays,
    so the file is read before it plays.
  - Written when VALUE is let go after a pick or a knob turn, never while an FX screen is up. FX deep edit learned
    that one on the unit: a write with the FX screen up sent the display to the main screen.
  - A missing, short or bad file (magic, version, count, sum) leaves the tones as designed.
- **Memory:** the module overflowed its slot by 260 bytes. So `sy_block` (2,560 bytes, section `.sybss`) moved out to
  0x83FE6000, in the free slot between FX deep edit's (to 0x83FE6000) and bounce's (from 0x83FE8000). The builder
  checks that no row overlaps that slot and nothing in the input refers to it, and gives it a boot zero row. The
  module is 42,756 bytes of 45,056.
- **Emulator checks:** 264 pass on `release/sy-synth-test3` (APP1 `d3d4365a…aa0fe`, 3,200,448 bytes). The SY
  section has 107 of them, 11 for test 3:
  - VALUE + CTRL 2 on SUPERSAW sets DETUNE to the knob's 100. FX deep edit's handler is asked first, the popup reads
    `SY 4 SUPERSAW` / `DETUNE 100`, and the turn is taken.
  - CTRL 1 and 3 set BRIGHT and LEVEL; CTRL 4, or a turn without VALUE, goes on.
  - With the stock file calls emulated:
    - VALUE let go with an FX screen up writes nothing;
    - with no FX screen, the file is written once, byte for byte as expected;
    - a fresh start reads it at the first key event, and tone 4 comes back with its knobs, the engine equal to
      `sy_ref.py` with them;
    - a file with a wrong sum is ignored, and with no file nothing is read or written.
  - The popups fit the screen.
  - The scatter table has `sy_block`'s zero row.
  - The builder's three calls are in FX deep edit's bridges.
  - Separately, every tone with its knobs turned (four settings across the tones) equals the twin value for value.

## SY synth test 4 (sy-synth-test4): the picker, and ROUTING Mix

On the unit (2026-11-04) test 3 "works really well", and bus FX already work with the synth. Then the user asked for
a better way to pick sounds than holding VALUE, for the synth on ROUTING Mix without switching to ExtIn, and to "use
guitar synth sound with looper sampling etc"; and suggested VALUE + EXT SOURCE to bring the synth up.

**What tests 2 and 3 took over.** VALUE held + pad is a stock shortcut (manual p. 162: it selects a sample without
playing it), and VALUE held + CTRL 1-3 is stock's sub-parameter edit on the FX screen. Test 4 gives both back.

**The picker** (`tune_test.c`: `sy_key_down`, `sy_key_up`, `sy_knob`, `sy_picker_*`):
- Hold VALUE and press EXT SOURCE, on any page but the Sound Generator's. FX deep edit opened the input FX's extra
  screens with that chord; now `sy_key_down` sees it before FX deep edit does.
  - With EXT SOURCE on, its press and release are taken, so the input stays on. With EXT SOURCE off, the press goes on
    to stock, which switches the input on.
  - If pad 16 had put the synth off, it comes back on with the sound it had.
- The pads light while it is open, through the key light bounce uses (`0x800d4910`, repainted every UI tick over
  whatever stock paints): the sound playing white, the other sounds blue, pad 16 red, bright while the synth is off.
- A pad picks; pad 16 puts the synth off and closes the picker. CTRL 1-3 edit the sound as test 3 did, without VALUE.
- It closes on EXIT, the chord again, 4 s untouched, another page, or any other key (that key then goes on as usual).
  Closing asks stock to paint the pads again (`0x802496f0 |= 2`) and closes the picker's popup if it is the one up.
- VALUE in the picker closes it and goes on to the input FX's extra screens. FX deep edit's handler gets VALUE's press
  (so it counts VALUE as held), then an EXT SOURCE press and release: its own chord.
- The file is written at the key that closes the picker, or at the next key release after a timeout. It is never
  written from the UI tick, and never with an FX screen up.
- Popups: `SY 4 SUPERSAW` / `TAP A PAD` when the picker opens; the sound's name after a pick; test 3's popup on a knob.
  The widest line is 94 px.

**ROUTING Mix.** Pair 0 is the input alone only on ExtIn. ROUTING itself (system 0x5c, sent to the chip as DT1
`02 01 00 1e`) only chooses what REC, RESAMPLE, the looper and skip-back record (manual p. 36, 41, 44); it doesn't
change what is heard. So:
- **The hold** (`route_hold`, every UI tick): while a synth listens, the chip is told ExtIn, and the user's own value
  goes back when nothing does. A synth listens while EXT SOURCE is on and the SY synth isn't off (pad 16), or on the
  Sound Generator page for test 6.
  - v9.52's FX deep edit already catches every DT1 at the builder's entry (`0x800d8118` jumps to its `fde_dt1`). The
    builder re-points that jump to `sy_dt1`, which passes ROUTING's value through `sy_route_dt1` (ExtIn while held)
    and goes on to `fde_dt1`. That covers the RECORD SETTING and looper screens, and the chip resets
    (`0x801803b0` sends ROUTING 0).
  - Other IDs go on with the caller's registers and stack untouched. The builder makes some boot frames from leftover
    stack.
  - The synths start 20 ms after the hold goes out, so the chip has switched first.
- **The recorder.** The feed (`0x1ca80`) copies one pair of the RX packet for every recording, inside its own call:
  pair 1 if settings + 0x64 is set, else the pair the byte at `0x82e0e974` names (both guarded). Bounce's rx bridge
  now calls `sy_feed` in place of the feed: the tracker's pairs first, then `sy_rec`, then the feed. When the feed
  will take pair 0:
  - **ROUTING Mix, held:** pair 0 becomes pair 1 x 2, saturated. Pair 1 is the mix before BUS 3/4: it came back 4
    frames before pair 0 in the bounce probe, carried pads on DRY and BUS 1, and read half pair 0's level in cab test
    2 (13-14% against 27-28%). So a recording made with the synth on has the pads, the guitar, the synth and BUS 1/2's
    effects, but not BUS 3/4's. This lasts 30 ms past the hold while the chip switches back.
  - **ROUTING ExtIn, held:** pair 0 gets the synth's newest block added, as `sy_tx` added it to TX. The stems are at
    the capture's scale.
  - **The feed taking another pair:** the packet is left as it is.
- Test 5's popup (`SYNTH NEEDS` / `ROUTING ExtIn`) is gone.
- **Memory:** the module is 44,420 bytes of 45,056.

**Emulator checks:** 299 (155 distinct: the two layout checks run with every emulated machine) pass on `release/sy-synth-test4` (APP1 `e6fa0a91…d834`, 3,202,080 bytes). The SY section has
142 (44 distinct) of them, 21 distinct checks for test 4:
- **Picker:**
  - The chord opens it: the press and release are taken, FX deep edit never sees them, the pads are lit, and the
    popup fits.
  - VALUE + pad with the picker closed goes on.
  - A pad picks and its press and release are taken; pad 16 closes the picker and puts the synth off; the chord again
    brings the synth back.
  - With EXT SOURCE off, the chord's press goes on to stock.
  - EXIT, another page, another key (which goes on), the chord again and 4 s untouched each close it. The pads are
    repainted every tick until then. A pick is written at the next release, not from the tick.
  - VALUE hands on to FX deep edit's chord, in the expected order and with the expected events.
  - The Sound Generator page keeps the chord for FX deep edit.
- **Knobs and file** (test 3's checks through the picker): EXIT with an FX screen up holds the file back, and the next
  release with none writes it byte for byte.
- **Hold:**
  - On Mix, the Sound Generator page plays and the main screen's engine runs, 20 ms after the hold.
  - EXT SOURCE off or pad 16 sends the user's Mix back.
  - A firmware ROUTING DT1 goes out as ExtIn while held and as sent otherwise; other IDs are untouched, on the
    caller's stack.
  - The readout with EXT SOURCE off runs the tracker without a hold.
- **Recorder:**
  - Mix gives pair 1 x 2, saturated, and the tracker still gets the guitar.
  - ExtIn adds the synth's block once.
  - The feed taking another pair leaves the packet alone.
  - The 30 ms grace, then stock again.
- **Tracker:** `sy_feed` reads the pairs from its r0 packet, then calls the feed with the same r0 and r1.

## SY synth test 5 (sy-synth-test5): the guitar synth screen, and new tones

On the unit (2026-11-05): picking a sound in test 4's picker also played the sample on that pad, and the tones "do not
stand out much from guitar sound". The user asked for a guitar synth mode whose menu stays up, entered maybe with
EXT SOURCE + RECORD SETTING, "like our sound generator or kits gui displays", with a CTRL knob switching the presets.

**Why the pads played.** A pad sends two UI events. One is a key press (type 5, key 0-15), which FX deep edit's
bridge handed to the picker. The other is a pad hit (type 0x10, with its velocity), which goes from the UI dispatcher
to the page's pad handler (`0x800c7db8`) and the stock pad note. The picker took only the first.

**Every UI event first.** v9.52's note repeat already bridges the UI dispatcher's entry: `0x8003b530` jumps to its
`nr_event`, which calls `nr_event_c` with one `bl`. The builder re-points that `bl` to `sy_event`, which hands everything
it doesn't take on to `nr_event_c`. FX deep edit's bridges call their own handlers again.

**The screen** (`tune_test.c`: `sy_event`, `sy_screen_event`, `sy_col_draw`, `sy_foot_draw`, `sy_sg_poll`, `sy_bar_*`):
- Hold EXT SOURCE and press RECORD SETTING, on the main screen or the Sound Generator page. (SHIFT + RECORD SETTING
  opens the Sound Generator itself.)
  - RECORD SETTING's press and release are taken. The Sound Generator page is asked for (`0x800da598`, as the kits ask
    for it), and the screen comes up when it arrives, or gives up after 1 s.
  - The input goes on. If it was on, the EXT SOURCE press toggled it off, so the chord puts it on again through the
    settings setter (`0x800dd0c0`, ID 0x25, as bounce does). Once EXT SOURCE is let go, it does so again if stock put
    the input off (GATE).
  - SOUND OFF comes back on with the sound it had.
- It is the Sound Generator page, with its own widgets drawing ours, the way the kits draw theirs:
  - **The knob columns:** the class's draw pointer (`0x8022bbd4`, the kits' `kit_ui_draw`). The name is small and the
    value big, where and in the fonts the stock column uses: font 0x1d at +3, font 2 at +15. DM-404 showed that font 2
    is the big one.
  - **The footer** (`0x802256fc`, `kit_ui_footer_draw`): the sound's name. Its box is 64 px wide, so "SY 1 SAW LEAD"
    lost its last letter.
  - **The bar:** the arp's item name, value text and update bridges (its jumps at `0x800bbc98`, `0x80123be6`,
    `0x80123ce0`) go to `sy_bar_name` / `sy_bar_text` / `sy_bar_poll` first. They show PRM: SOUND and its number.
  - **The page's update** (`0x80229678`, kits save's `ks_sg_poll`, which it calls first) draws the columns and the
    footer again when something changed. The columns are the page's children at +0x1a6c, read every time. The footer
    is kept from its last draw only while the page is up and its first word is still its vtable.
  - Outside the screen, each of these hands on with every register as it came.
- On the screen:
  - CTRL 1 is SOUND: 16 zones of 8 positions, OFF and then 1-15.
  - CTRL 2 is TONE (test 3's BRIGHT, knob - 64), CTRL 3 LEVEL (0-198%).
  - SHIFT tapped, or held, gives OCTAVE (5 zones, -2..+2), the tone's own setting (test 3's P2) and SUSTAIN (0-100). A
    turn while SHIFT is held edits that page, and the release keeps the page.
  - VALUE steps SOUND by one per turn event. A pad picks a sound, pad 16 OFF.
  - Taken: the pads' hits and key presses, SUB PAD, VALUE's push (no edit mode), REC (no export), and the release of
    every press taken. Everything else goes on: EXIT leaves (the page changes, so the screen closes), and SHIFT + RECORD
    SETTING gives the page back to the Sound Generator.
  - The SY synth plays on the Sound Generator page in the screen. Guitar synth test 6 doesn't: its note is let go when
    the screen opens there.
- **The file** (`B:/_sy_tones.bin`, version 2, 88 bytes): test 3's, plus each tone's OCTAVE and SUSTAIN (0 = as
  designed). A version 1 file is ignored, since the tones changed. It is still written at a key release, never with an
  FX screen up.
- **Memory:** the module filled its 45,056-byte slot. The screen's code went into the SY slot (`.sytext`, a boot copy
  row of its own at `0x83fe6c00`, 2,236 bytes), and sy_block keeps `0x83fe6000`-`0x83fe6c00`. The module is 44,248 bytes.

**The tones** (`sy_ref.py`, `sy_fp.c`). Every partial of a note had an oscillator of its own at the partial's level, so
the synth kept the guitar's spectrum and its decay. Three settings per tone:
- **FUND:** a band whose pitch is a whole multiple 2-8 (within 3%) of a lower band sounding in the same block stays
  silent. A note then sounds from its lowest band, and the tone's own wave makes all its harmonics. An octave or a
  twelfth on another string goes too: in an open E chord, E2, B2 and G#3 stay. Every tone has it but PAD and STRINGS.
- **SUSTAIN** 0-100: while a band still sounds, a falling level follows with a time constant of 40 ms x 2^(0.08 s)
  (s 100: 10 s) instead of the release's. A note holds until its string dies (under -60 dBFS) or its band loses to a
  neighbour.
- **OCTAVE** -2..+2: the oscillators' increments x 2^OCTAVE (exact: a power of two).
- **The pitch at a note's start** (`sy_period`). With FUND a note's fundamental band plays alone, and it came in flat.
  The first periods a band reads after it wakes span the band-pass's start: -138, -51, -22, -12 cents on every string,
  and the tracker took them in. The low E began 36 cents flat and took 100 ms to come up; the overtones had covered
  it. Now a band's first 4 periods are counted, not tracked: it still sounds after 2, at its centre, and tracks from
  the fifth. Every open string is within 5 cents from its first sounding block (the twin), and the low E still sounds
  36 ms after the pick.

The 15 tones are SAW LEAD, SQR LEAD, SYN BASS (an octave down), SUPERSAW, PAD, STRINGS, ORGAN, FLUTE, BELL (an octave
up), BRASS, SUB BASS (down), SWEEP, WAH, SEQ and OCT LEAD (up).
- The ceiling is 3 dB higher (OUT_SCALE 23170, -3 dBFS at the clip).
- The gains put each tone's RMS on a strummed G chord 3 dB above test 4's SAW LEAD (the twin, two passes for the soft
  clip). WAH needed 22x: its band-pass hears the fundamentals only now.
- The release has `demos\sy5-NN-name.wav`: each tone on the model guitar (single notes, a strum, a picked chord, a
  bend). Peaks 0.36-0.71.

**DM-404** (the real 5.52 firmware in the full emulator, snapshot disks):
- The chord opened the screen: page 0x1e, the screen up, the engine running.
- CTRL 1-3, VALUE, SHIFT and the pads changed what they should, and pad 16 stopped the synth. EXIT went back to the
  main screen.
- A pad hit on the main screen before the chord made A-5 the current pad. The pads hit on the screen didn't change it:
  they never reached stock.
- The release's `screens\` has the screen as it drew.

**Emulator checks:** 308 (160 distinct) pass on `release/sy-synth-test5`, 145 (45 distinct) of them in the SY section. Test 5's:
- **The screen:** the chord (taken, the page asked for, up once it is there; RECORD SETTING alone goes on); pads, SUB
  PAD, VALUE's push and REC taken with their releases, and nothing reaches note repeat; SOUND's 16 zones, VALUE's
  steps and their ends; the SHIFT page, tapped and held; the columns', footer's and bar's text and drawing calls; the
  page's update drawing them once; another descriptor type, another page, and the arp's bridges with every register as
  it came; SHIFT + RECORD SETTING; the input put on, and again after GATE; giving up after 1 s; the SY synth on the
  Sound Generator page in the screen, test 6 silent.
- **The file:** version 2 written at a key release (none with an FX screen up), read back with the engine = the twin,
  a version 1 file and a bad sum ignored.
- **The engine:** every tone value for value; OCTAVE and SUSTAIN turned on four tones value for value; a tone change
  from the screen value for value. The engine's own checks (the bands on the partials, silence after the strings)
  now run on WAH, the one tone with no release: the saw lead releases over 150 ms and sustains. The bands on the
  partials: 97.0% on four open strings, 98.6% on the G strum, 99.1% on the picked C (FUND leaves only the
  fundamentals, so their start weighs more: 95.2% on the open strings before the start was fixed).
- **The builder:** note repeat's bridge calls `sy_event`; the six pointers and jumps go to the screen's; FX deep
  edit's bridges call their own handlers.

## SY synth test 6 (sy-synth-test6): the screen's controls, FX screens, REMAIN, smoother notes

On the unit (2026-11-05), test 5: "good work. some issues". The bar's PRM: SOUND is redundant; VALUE picks the sound,
so CTRL 1 should do something else (the user chose the sound's own setting); TONE should read -50..+50 and LEVEL
0..100 (the synth's level, after a talk about a real synth/dry mix). An FX picked on the screen "does not stay on long
enough to adjust its parameters", and REMAIN + an FX button doesn't keep it up (the plain Sound Generator and the kits
too): REMAIN changes the preview bus instead (stock, manual p. 46; "we need another way to preview": a REMAIN tap). The
synth is barely heard on the high E; single notes sound "pretty bad (tracking good)", chords a bit better. The kits:
every guitar note should hit a pad.

**FX screens.** DM-404 on test 5: with Filter+Drive up on the screen, CTRL 1 changed the synth's sound (to BRASS) and
the FX screen closed 3 s later. The screen took the knobs, VALUE and the pads, so the effect never saw a control (its
screen closes a few seconds after the last one, manual p. 33), and MFX + VALUE, CTRL 3 or a pad (picking an effect,
p. 32) were taken too. Now, with an FX screen up, the knobs, VALUE (turned and pushed) and SHIFT go on to it, and the
pads too while MFX is held. Test 3's `sy_fx_screen` read the main page's object (`0x80cfd350`, its view list). DM-404
showed it 0 on the Sound Generator page: stock destroys the main page's object there (`0x8005ee26`). The SG page keeps
its views on its own object, in the same list (+0x38: the count at +0x44, the views at +0x3d4). `sy_sg_poll`, the
page's update, records the object (DM-404: `0x835aac28`, the FX view its seventh), and `sy_ui` forgets it off the page.

**REMAIN on the Sound Generator page** (the screen, the plain page, the kits). Stock: the page's key method steps the
preview bus on REMAIN's press (the case at `0x8015c790`, the bus at `0x8024980c`, a popup), with an FX screen up too.
DM-404 on test 5: REMAIN held + DELAY did freeze the FX screen (its show reads REMAIN held, `0x80146f64`, and sets
`0x80592320`), but the press stepped the bus. Now:
- REMAIN's press is taken, and its held bit set as the key press handler would (`0x8003abee`), so an FX button pressed
  meanwhile opens a frozen FX screen. Its release is taken and the bit cleared.
- Let go with no FX button, the stock key handlers get a press and a release (`0x8003abd0` / `0x8003ada0`, through FX
  deep edit's bridges): the preview bus steps, as a tap did.
- With a frozen FX screen up, REMAIN closes it with an EXIT (as REMAIN does on the other pages) and clears the flag.
- With an FX screen up that is not frozen, and on every other page, REMAIN goes on as stock.

**The screen.** VALUE and the pads pick the sound. CTRL 1 is the tone's own setting, CTRL 2 TONE, CTRL 3 LEVEL; SHIFT:
OCTAVE, SUSTAIN, DYNAMICS. TONE and the tone's own setting read -50..+50 (the knob's offset scaled), LEVEL 0..100 (50
as designed, 100 twice). The bar's PRM part (x 57..127: "PRM:", the item's box, the value) is painted over in
`sy_bar_text`, with an empty name and value; "SHIFT:OTHERS" stays. The file is version 3 (104 bytes: DYNAMICS per
tone); a version 2 file (test 5's) is read, DYNAMICS as designed.

**Single notes.** The twin on single open strings (SAW LEAD): a band's ownership switched on and off nearly every block
in a note's first 150 ms (1,460 switches over seven notes), and on the low E and the B string all through the note
(559). The causes: the neighbour rule while the band-passes settle, the pick ringing empty bands, partials above the
8th. FUND made it audible: a note sounds from one band, which dropped for a block or let its harmonics back. Now:
- **the gate:** a band 20 dB under the loudest owned band is silent;
- **the hold:** a band that stops owning sounds on 4 blocks while its energy keeps 0.8 of what it had owning;
- **FUND** to the 16th harmonic, and only from a band at -20 dB of the multiple's energy or more (a pick's ring an
  octave under a note muted the note);
- **the level:** a note at its loudest partial's, FUND's fundamental taking the level of the strongest band it silenced
  (a pickup's fundamental can be under its harmonics).

Switching: 241 in the attack, 0 after. The hold was the cost (`scratchpad sy6/variants.py`): 8 blocks without the
energy rule kept the pick's rings sounding, 91% of the sound on the open strings' partials against test 5's 97%; now
96.8 / 97.8 / 98.3% (test 5: 97.0 / 98.6 / 99.1).

**The high E.** In the twin every string comes out within 2 dB at the same input level, so on the unit it is the guitar:
a weaker string, or its fundamental under its harmonics, which the loudest-partial level now covers. DYNAMICS (SHIFT +
CTRL 3, 0..100, 100 as designed) pulls the levels toward one: L x (L / 0.1)^(d - 1), in single precision through a cubic
log2 (error under 0.0013) and test 3's exp2.

**Levels.** The loudest partial lifts chords more than single notes (an octave string lifts the note under it), so the
tones are levelled on single notes (E2, G3, E4) to test 5's: chords 0.7..3.1 dB over test 5, peaks at most 0.71
(`sy6/level6.py`). The release has `demos\sy6-NN-name.wav`.

**Kits.** Drum mode plays notes 36..51 only (pads 1..16, `kits/kit_midi.inc`), and guitar synth test 6 sent the
guitar's own note: E2..D#3 struck pads 5..16, nothing higher, and pad 1 (the kick, C2) never. `syn_ui` now sends 36
+ the note's offset from E2, folded into 0..15 an octave at a time: the open low E on pad 1, G3 on pad 16, G#3 on 5.

**Notes from the bands (asked, not built).** The Sound Generator has four voices and plays MIDI chords, but guitar
synth test 6 sends one note at a time. A prototype took notes from the SY engine's bands: on test 6's chord cases 116
right and 666 wrong (test 6's tracker: 164, 8), 3 of 12 single-string cases (11). The bands make good sound but bad
notes: the pick rings empty bands, partials own bands of their own, and a pickup's fundamental is weaker than its
harmonics and settles last (E3 holds its band at 32 ms, its 3rd harmonic B4 at 11). Chords would need a real
multi-pitch step.

**DM-404** (the real 5.52 firmware in the full emulator, snapshot disks, the release's APP1):
- The columns read RESO -23 / TONE +22 / LEVEL 77 after the knobs, OCTAVE / SUSTAIN / DYNAMICS on the SHIFT page
  ("DYNAMICS" fits), the bar blank beside "SHIFT:OTHERS".
- Filter+Drive up: CTRL 1 moved its CUTOFF, the synth's settings unchanged; the screen closed a few seconds after.
- A REMAIN tap stepped the bus (BUS 1 to BUS 2, the popup). REMAIN held + DELAY: Sync Delay frozen over 4 s, the bus
  left; CTRL 2 moved its FEEDBACK; REMAIN closed it, still on the page.
- MFX held + pad 5 picked Zan-Zou on the MFX screen, the synth's sound unchanged.
- The plain Sound Generator page: a REMAIN tap stepped the bus, REMAIN + DELAY froze the FX screen and left the bus.
- The release's `screens\` has them.

**Emulator checks:** 319 (163 distinct) pass on `release/sy-synth-test6`, 157 (47 distinct) of them in the SY section. Test 6's:
- **FX screens:** the knobs, VALUE and SHIFT going on with one up, the synth's settings untouched; the pads the
  screen's, silent, unless MFX is held.
- **REMAIN:** taken with its held bit set and cleared; a tap handed to the stock key handlers as a press and a release;
  held + DELAY with no tap; a frozen FX screen closed with an EXIT, the flag cleared; not frozen, or another page: stock.
- **The screen:** CTRL 1 the tone's own setting, the sound left; the columns' labels and values (-50..+50, 0..100); the
  bar blank (no name, the rectangle painted, no value, the displaced draw skipped).
- **The file:** version 3 (104 bytes) written and read back with DYNAMICS = the twin; a version 2 file read.
- **The engine:** every tone with OCTAVE, SUSTAIN and DYNAMICS turned value for value; the bands on the partials at 96%
  or more; drum mode's pads (E2 pad 1, the riff E2 E2 G2 A2 E2 on pads 1, 1, 4, 6, 1).

## SY synth test 7 (sy-synth-test7): the synth's bus, on combined-test18

The user asked whether the guitar synth goes through the effects. It didn't: it plays on the DRY bus, which BUS 1 and
BUS 2's effects never reach (manual p. 34); BUS 3 and BUS 4 reach it only with DRY Routing on BUS3 (p. 143). The
guitar's own sound goes to INPUT BUS (REMAIN + EXT SOURCE). The user then asked for a bus setting, built on
combined-test18 (v9.52 with LEVEL for MIDI notes, `COMBINED.md`) so one flash has both. The user confirmed that
Routing Type A ("serial") is BUS 1 feeding BUS 2.

**The bus.** TX line 3's stems are DRY (words 0/1), BUS 1 (2/3: pads on BUS 1 play there in DM-404) and BUS 2 (4/5:
DM-404's reading, not seen yet). `sy_tx` adds the synth to the stem `sy.out_bus` names: DRY, BUS 1, BUS 2, or BOTH
(half on each, for Type B's two effects side by side). On the screen VALUE's push steps it DRY -> BUS 1 -> BUS 2 ->
BOTH (its press and release taken, as before), and the bar's PRM part shows it ("OUT: BUS 2", the bar's font,
centred, one row down as the stock item is). The file keeps it in byte 98, still version 3: test 6's files have 0
there (DRY); a byte out of range reads as DRY. With ROUTING Mix a sample has the synth with its bus's effect; with ExtIn
`sy_rec` still adds the synth without it. `sy_tx` moved to `.sytext` (the module is 44,936 bytes).

**combined-test18 under it.** That build's `sgl_midi_gate` takes the SG MIDI entry's first three instructions
(`0x83fa3448`: push.w, sub sp, the movw of the drum-mode byte's low half) and jumps back at entry + 10. The builder's
`kit_mode_flag` follows the jump and reads them in the gate: the same byte as before (`0x83fc58e0`). The guitar synth
test 6's notes (`syn_ui` through `arp_midi_event`) now follow LEVEL as MIDI notes do.

**DM-404** (the release's APP1): four VALUE pushes stepped the bus 1, 2, 3, 0 and the bar read OUT: BUS 1 / BUS 2 /
BOTH / DRY; test 6's FX screen, REMAIN and MFX steps gave test 6's results on the new base. DM-404 has no audio input,
so the synth itself was not heard there: the unit's test says whether BUS 2's stem is BUS 2.

**Emulator checks:** 327 (165 distinct) pass on `release/sy-synth-test7`, 165 (49 distinct) of them in the SY section. Test 7's: the
synth on each bus's words (BUS 1 2/3, BUS 2 4/5, BOTH half on each, DRY again; the other words untouched, clipped to 20
bits); VALUE's push stepping the bus with its press and release taken; the bar's text for each; the file's byte 98
written and read back, a bad one read as DRY; the layout's `out_bus`.

## SY synth test 8 (sy-synth-test8): the synth starts from its screen

On the unit, test 7: "without going to guitar synth mode, ext in still has synth sound with guitar in". Since test 1
the synth played on every page whenever EXT SOURCE was on (unless SOUND was OFF); the screen only edited it. The user
chose: off at power-on and whenever EXT SOURCE goes on, on once the guitar synth screen opens, and on after EXIT
(every page but the plain Sound Generator's) until EXT SOURCE goes off.

- `sy.armed` (the byte after `out_bus`): `sy_ui` sets it while the screen is up (mode 1) and clears it when `tt.ext`
  (EXT SOURCE, read every 0.1 s) is off, but not while the chord's EXT SOURCE release is still to be undone
  (`ext_fix`, GATE). The BSS zero is off.
- `sy_can_play` needs it, and so does the ROUTING hold (`route_hold`): with the synth off, ROUTING is the user's own (the
  plain Sound Generator page's tracker keeps its hold as before). SOUND OFF still turns it off; opening the screen turns
  a SOUND OFF on again, as in test 5.
- **A start's first two steps are not held to the budget** (`SY_GRACE`, `sy.run_steps`). DM-404 timed the engine's
  first step after a start at 1,232,940 cycles (steady steps 50-80k; the emulator translating the code), which set
  SLOW at once. Tests 6 and 7 restarted it on the next page change, so it never showed; with test 8 it held until
  EXT SOURCE went off. On the unit a cold first step should stay far under the 800,000-cycle block, but a SLOW there
  now costs the whole session. A real overload still stops it from the third step.
- The checks start their machines armed (as if the screen had been opened) unless a check says otherwise; the first
  engine check sees the arming cleared before the UI has read EXT SOURCE.

**DM-404** (the release's APP1): EXT SOURCE on at the main screen: not armed, no engine; the screen: armed, the engine
asked for; EXIT: still armed; EXT SOURCE off: disarmed; on again: not armed. The first step after the start read 1,245,660 cycles there, and the engine kept running (1,313 steps by the screen, 2,182 after EXIT, no step after it over 9/10 of a block).

**Emulator checks:** 333 (167 distinct) pass on `release/sy-synth-test8`. Test 8's: EXT SOURCE on with the screen never opened (no
engine, no hold), the screen (armed, held on ExtIn, the engine on), EXIT (on), EXT SOURCE off (disarmed, the hold let
go: the user's ROUTING sent back), on again (off until the screen).

## SY synth test 9 (sy-synth-test9): test 8 on combined-test19

The user found the Sound Generator "way too loud" at LEVEL 127, especially with four notes, and the kits too: they
should be about as loud as a sample. That went to the combined build as combined-test19 (`COMBINED.md`,
`SG_LEVEL.md`): the kit stage's output stage had doubled melodic notes as well as kit hits since v9.39. Now one note at
127 peaks at -12.0 dBFS (was -1.2), four at -1.2 to -2.0 dBFS, kit pads alone at -6.4 dBFS at most (was -1.3); REC and
BOUNC record as before. The SY code is test 8's; only the parent changed, and every guard holds on it.

**Emulator checks:** 333 (167 distinct) pass on `release/sy-synth-test9`.

## SY synth test 10 (sy-synth-test10): the footer, and the looper

On the unit (tests 8/9): "if i go into sound gen mode then back to guitar synth mode, guitar synth mode shows
chromatic mode on bottom menu until i press shift. drum mode-guitar synth it is blank until shift. also guitar synth
mode won't open when in looper mode." Asked how the looper should behave: like the Sound Generator and kits, leaving
the looper's screen for the guitar synth's, with REC still capturing the loop.

- **The footer:** `sy_mode_on` cleared the kept footer widget (`sy.foot`), and `sy_foot_draw` kept it only while the
  screen was up. A screen opened over the SG page already up redrew its columns (the page update), but not the footer,
  so the page's own stayed ("CHROMATIC INPUT", drum mode's blank) until SHIFT made the page draw it again. Now every
  footer draw on the SG page keeps the widget, the chord no longer clears it, and the mode tick still forgets it off
  the page; the screen's first page update redraws it.
- **The looper's page (0x27, MARK with MARK Function = Looper)** takes the chord too, as SHIFT + RECORD SETTING does
  there; the SG page is asked for as from the main screen.
- **REC with looper mode on** (the byte at 0x82e0b92c, which the SG page's REC case tests at 0x8015c6b0) goes on to
  stock: the page posts the looper's REC (0x800c23c8(0, 0, 0), message 0xa4) as on the stock page. With looper mode off
  the screen takes REC as before (no export). Guards: 0x8015c676 (the page's MARK asks for 0x27) and 0x8015c6b0.

**DM-404** (the release's APP1): the screen opened over the plain SG page showed "SAW LEAD" in the footer at once (it
was "CHROMATIC INPUT"), and over drum mode too (it was blank). REC on the screen with looper mode off posted nothing.
With looper mode on (SHIFT + VALUE, OK), MARK opened the looper (page 0x27, "empty"); the stock SG page's REC reached
from there posted the looper's message (0xa4, as the ring at 0x80b5dfa4 showed); the chord on the looper's page opened
the screen (page 0x1e, mode 1), and REC on it posted 0xa4 too, each time, with the screen staying up. Back on the
looper it read "rec wait" (AUTO TRIG on, no input in DM-404).

**Emulator checks:** 340 (168 distinct) pass on `release/sy-synth-test10`. Test 10's: the page's own footer kept outside the
screen and redrawn with the columns once the screen opens over the page; the chord on page 0x27 asks for the SG page;
REC passed on with looper mode on, taken with it off.

## SY synth test 11 (sy-synth-test11): a synth voice per note

The user (after test 10): the tracking is "amazing", but the tones "do not sound very good"; they wanted tones like
the Sound Generator's and in the styles of the synths they like (Korg polys; their plug-ins: Juno-106, Jupiter-8,
SH-101, TB-303, Minimoog, Wavestation, Poly-800, the Usual Suspects' Virus and JP-8000 emulations), "more than 15
tones", and no effects inside the synth ("can just use bus fx ie chorus"). An offline prototype's demos (session
scratchpad `sy10/proto`, `release\..\demos\sy-voice-demos1`) were approved: "Good, build them".

- **The engine** (`tunetest/sy_voice.c`, new). Tests 1-10 gave every sounding band oscillators of its own, all through
  one filter, at the guitar's level. Now:
  - The SY analysis is unchanged, with FUND always on and no DYNAMICS shaping. It hands each band's level, frequency
    and energy to sy_voice.c.
  - A note manager turns the bands into notes. A pick rings short blips in other bands (in the demos' lead phrase,
    281 band segments for about 25 notes), and a note's ownership can start one band low while its first periods
    read flat.
    - Poly: a new band plays at once at its own level, as before, and becomes a synth note once it has held for 32 ms
      with a settled reading.
    - Mono: a note is confirmed after 13 ms, with a settled reading near its band's centre, while no lower band that
      could be its fundamental is building up. The loudest candidate wins.
    - A voice follows its partial to a neighbouring band (a bend), and a note picked again attacks again.
  - Each note gets a voice of its own:
    - oscillators as passes over the block: BLEP saw and pulse, triangle, sine; the Sound Generator's 32 waves (its
      own wave_eval for types 15-31, with the heavy LPSaw, LPSqr, Organ and Vowel at half rate); a seven-saw
      supersaw; two-modulator FM; a hard-synced oscillator 2 with a pitch sweep;
    - a filter: a 12 dB state-variable, a 24 or 18 dB ladder, or the SG's ENV preset with its own filter (env.c's);
    - amp and filter envelopes, an LFO, glide.
  - Four voices (three for SUPERSAW, SG VOWEL and VECTOR PAD). The output is mono and dry: effects come from the
    SP's bus FX.
- **20 tones** (`tunetest/sy_voices.py` VOICES), each levelled to the old SAW LEAD's RMS (-17.7 dB of the clip) with
  peaks under 0.9: POLY PAD, STRINGS, POLY BRASS, ENSEMBLE, POLY KEYS, VECTOR PAD, SYNC LEAD, LADDER LEAD, FAT BASS,
  ACID BASS, PUNCH BASS, SUPERSAW, FM PIANO, FM BELL, then six made from the SG's own waves and ENV presets (SG ACID,
  SG VOWEL, SG ORGAN, SG CZ KEYS, SG PLUCK, SG FM BELL).
- **The screen:**
  - Pads 1-15 pick tones 1-15, SHIFT + pads 1-5 pick tones 16-20, pad 16 is OFF; VALUE steps through all of them.
  - CTRL 1 is the tone's own setting. On the SG tones it picks the ENV preset, shown by name.
  - TONE moves the cutoff +-2 octaves. On an SG preset it moves that preset's filter, or DUTY if it has none; on the
    FM tones it moves the brightness.
  - LEVEL, OCTAVE, SUSTAIN (the decay and release times x 0.25..4) and DYNAMICS (pick sensitivity).
  - The file is version 4 (136 bytes). A version 3 file keeps only its bus and SOUND OFF.
- **Memory:** test slots that v9.52 leaves free, each a boot row, each checked unused in the parent:
  - the code, 7.1 KB at 0x83fed000 (the CPU meter's and bounce probe's test slots);
  - the note manager, 4.8 KB at 0x83fd7a00 (the free top of chromatic scales' slot);
  - the constants and smaller functions, 2.5 KB at 0x83fef100 (the rest of the start fix's slot);
  - the state, 4.0 KB at 0x83fe4800 (the free top of FX deep edit's slot), with the block's buffers, so the step
    uses 1.1 KB of the tracker's 2 KB stack.
  A public release would need these slots planned with those features.
- **CPU:** at most 44-91k instructions a step on the tone checks' signal (SG ORGAN 91,001, 11.4% of a block; tests
  1-10's tones: 47-77k). The first two steps after a tone switch are not held to SLOW, as a start's are (DM-404
  timed 1.76 M cycles on code run for the first time).
- **The twin:** sy_ref.py keeps the analysis. The notes, voices and output stage are the host build of the same C
  (sy_voices.Host: x86-64, no fused operations, FTZ and DAZ as the module's FPSCR), so the module and the twin agree
  value for value.

**DM-404** (the release's APP1): the screen opens with the new tones:
- the columns show ATTACK / TONE / LEVEL on POLY PAD and DETUNE on SUPERSAW;
- pad 12 picks SUPERSAW and SHIFT + pad 2 picks SG ORGAN, whose ENV column reads OFF and, after CTRL 1, Bass;
- the SHIFT page reads OCTAVE 0, SUSTAIN 50, DYNAMICS 60;
- VALUE stops at SG FM BELL (Perc);
- the engine runs throughout.

**Emulator checks:** 352 (168 distinct) pass on `release/sy-synth-test11`. Test 11's: every tone against the twin,
value for value, at most 100k instructions a step; the screen's names, columns and SHIFT + pads; the file version 4
and a version 3 file's bus.

**Demos:** `release\..\demos\sy-voice-demos2` is rendered by the engine itself, so it is what the unit plays.

## SY synth test 12 (sy-synth-test12): clean note tracking

The user on test 11: the tones "sound amazing", but guitar synth mode has "weird glitches/artifacts/extra notes"
(Sound Generator mode's tracking "is really good now"). The cause was test 11's note manager. It gave every band that
switched on a voice at once, at the band's level. A pick lights 7-9 bands for 20-35 ms: the string's overtones come
before a low note's own band, and the band-passes ring. A real string also flickers between bands, and open strings
ring along. Each of those became a synth note with an attack, and the notes stole voices from the real ones.

- **The evidence.** The twin was run on real guitar: the user's own takes (Documents\SP404) and a clean recording
  they made for this through the SP's input (testdry.wav, 107 s: chromatic runs, chords, an arpeggio). Both stayed
  local and are not in the repo. The Sound Generator tracker (tune_ref.Tracker) gave the reference notes. On the clean
  recording, test 11's poly tones made 2084 attacks for the 136 notes of the runs, 1840 of them under 60 ms, plus 1235
  in the chords. Its mono tones made 339 attacks, 149 of them short. The suite's simulated guitar showed the same at
  15x (91 notes for 6 open strings).
- **The note manager v4** (`sy_voice.c` notes(), replacing notes_poly and notes_mono; tuned on the recording with a
  prototype). A band becomes a note only once it holds:
  - 8 blocks (10.7 ms) on, with gaps of 2 allowed;
  - its pitch measured: the bands' period counts (nper) are now passed to syv_block, and the first SY_SKIP periods
    read the band's centre, not the string;
  - settled (15 cents over 4 blocks), within 45 cents of its band's centre, half its run's peak, a quarter of the
    loudest band, and 0.12 of a held peak (-20 dB in 0.6 s), which keeps strings ringing along out;
  - no lower band that could be its fundamental (2x..8x, +-1 band, since overtones run sharp) building up or
    sounding, unless it has waited 80 blocks;
  - not a note's quieter neighbour, not an overtone of a note (or of a note that can still resume) or of a lower
    candidate, and not a louder candidate's neighbour.

  A candidate below a young note at an overtone interval, or a louder neighbour, moves that note there (no new
  attack). A note follows a bend and rides gaps of 45 blocks while its band's energy stays above 0.1 of its last
  (a string stopped or muted releases after 4 blocks). It resumes without an attack when its band returns within
  100 blocks, no louder than 1.6x. A re-pick needs a drop below half the peak and a return above 0.6. Only
  confirmed notes take voices, the quietest note older than 30 blocks giving way to a louder new one. Mono plays the
  newest note unless it is weaker than the current note's level.
- **The voices:** a note that goes on after a gap returns its envelope to decay/sustain (no attack); a gated note
  whose voice died restarts it. With no voice sounding, the output's DC blocker lets its tail go in about 5 ms
  (0.99 a sample, not 0.9995), so the output is exact silence soon after the last voice ends.
- **The cost:** low notes start once 6 of their periods are measured. That puts them 30-40 ms after the Sound
  Generator tracker on E2-C3, level with it from D3 up, and the suite's strums sound 63-71 ms after their low
  string. Measuring fewer periods on the low bands found 115-117 of the notes with 27-30 extras, so it was left as
  is. The suite's TX and screen checks now wait for the first note.
- **On the recording** (the same scoring for both): the runs give 144 attacks, 120 of the 136 notes found, 24 extras
  and none under 60 ms, with the median attack 2 ms after the Sound Generator tracker's (90%: 19 ms). The chords give
  40 attacks, none short. Mono: 145 attacks, 121 found, 12 short. On the user's processed takes, short notes fell from
  about 25,000 to 66.

**Emulator checks:** 352 (168 distinct) pass on `release/sy-synth-test12`.

**Demos:** `release\..\demos\sy-voice-demos3` has the recording through test 11 and test 12, rendered by each
test's own engine.

## SY synth test 13 (sy-synth-test13): test 11's tones with test 10's tracking

The user on test 12: "awful. response is not good and lacks character especially with chords", and then: "I just want
test 11 tones with clean accurate response as heard in test 10 tracking". Test 12's v4 waited for every note (its pitch
measured over SKIP_P + 2 periods: 30-40 ms on the low strings) and held back every band within a band of a sounding
note's overtones, besides FUND's exact multiples: a chord's major sevenths (11 semitones), minor ninths (13) and the
like. (On test 11 the user had also said the extra notes "sound really cool": they were asked about, not reported as a
fault.)

- **What tests 10 and 11 did.** The analysis (sy_fp.c, unchanged since test 10) decides which bands sound: a band owns,
  the gate, the hold, FUND. Test 10 gave each sounding band an oscillator at the band's level. Test 11 gave each band
  that began to sound a voice at once, young voices at the band's level, so it kept test 10's speed; but a synth voice
  for each of the pick's blips made them heard, and with 4 voices the blips took held strings' voices.
- **The note manager v5** (`sy_voice.c` notes()) takes the analysis's sounding bands and holds none back:
  - a band that has sounded HOLD_N (6) blocks in a row (8 ms) is a note; HOLD_H (12) when it is +-1 band from a whole
    multiple of a sounding note, HOLD_M (10) on a mono tone. On the user's clean recording 64% of the bands that start
    from E4 up are gone within 6 blocks, against 9% of the played notes' own band starts;
  - test 10's moves keep a note's voice, with no new attack: a band starting next to a note's band and reading its pitch
    within 17 cents (test 10's 1%); a young note's band going quiet as a band a whole multiple below sounds (FUND: the
    pick's overtone came first); a note's band back within 20 blocks of its end, no louder than 1.6x. A bend crossing
    bands still follows the note (test 11's follow());
  - a new note takes a free voice, else the quietest young note's if quieter, else the quietest note's if 1.5x louder:
    a blip never takes a held string's voice. Young notes sound at their band's level (test 11's confidence) on poly
    tones; a mono tone's voice keeps its level, as test 11's did;
  - mono: the newest band unless weaker than the note (weighed again for 15 blocks, so it takes over as the note
    fades); a band taking over a note younger than 20 blocks moves it (no second attack);
  - re-picks: test 11's rule again (test 12's was stricter).
- **On the recording**, scored from what each engine tells its voices:
  - POLY PAD, runs: 766 attacks (test 11: 2084, test 12: 144), 556 under 60 ms (test 11: 1840), notes 6.7 ms after
    test 10's bands (test 11: at once; test 12: 11-32 ms later by register). Chords: 295 attacks (test 11: 1226), 3.0
    voices sounding on average (test 11: 2.7);
  - mono (LADDER LEAD, FAT BASS): 279 attacks (test 11: 339), 109 under 60 ms (149), 78 in the chords (225), notes
    12 ms after test 10's bands (test 11: 13.3 ms).

**Emulator checks:** 352 pass on `release/sy-synth-test13`.

**Demos:** `release\..\demos\sy-voice-demos4` has the recording through test 11 and test 13, on five tones.

## SY synth test 14 (sy-synth-test14): test 13 with test 10's timing

The user on test 13: "still too much latency". Test 13 waited HOLD_N 6 blocks (8 ms) before a band was a new note,
HOLD_H 12 (16 ms) when the band was +-1 from a whole multiple of a sounding note (in a chord or a melody, a good share
of the notes), and HOLD_M 10 (13 ms) on a mono tone.

- **Test 14 waits 2 blocks** for every new note, poly and mono (HOLD_N = HOLD_H = HOLD_M = 2: at most 2.7 ms). On the
  user's clean recording that leaves the notes' starts where test 10's bands began (median +0 ms, 90% within 1.3 ms),
  and keeps out the one-block blips. Mono tones now start about 13 ms sooner than test 11's, whose mono confirmed 10
  blocks.
- **Kept from test 13:** no band held back (every chord note); the moves without a new attack (a neighbour band reading
  the note's pitch, an overtone giving way to its fundamental, a band back after a dip); a blip never takes a held
  string's voice; mono's takeover in a note's first 20 blocks moves it.
- **The cost:** the blips test 13's wait removed are back in part. On the recording, POLY PAD: 1415 attacks in the
  runs, 1190 under 60 ms (test 11: 2084 and 1840; test 13: 766 and 556), 539 in the chords (test 11: 1226; test 13:
  295). Mono (LADDER LEAD): 365 attacks, 187 under 60 ms (test 11: 339 and 149), 191 in the chords (test 11: 225).

**Emulator checks:** 352 pass on `release/sy-synth-test14`.

## SY synth test 15 (sy-synth-test15): test 11, with a TRACK page

The user on test 14: "no better hmmm. any way to go back to test 11 but have new setting parameters that can adjust
unwanted artifacts" (first written as test 10, then "oh my bad i meant test 11"). Measured before it, on the user's
recording: test 14's sound is heard as soon as test 10's after a pick, and its plucky tones reach full level sooner, so
the lag the user felt was not when the notes start; tests 12-14 had all changed test 11's note manager.

- **Test 11's voice code again** (b322ab2's sy_voice.c and .h), with three settings for every tone on a TRACK page,
  SHIFT's third: a tap steps the main page, OTHERS, TRACK and back; SHIFT held shows OTHERS, or the main page from
  OTHERS.
  - **WAIT** (CTRL 1, 0..12 blocks, shown as 0..16 ms): a band is a new note at its run's (WAIT + 1)th block (0: the
    block it begins, test 11's). Mono: its CONFIRM plus WAIT.
  - **SENS** (CTRL 2, 0..50): a new note needs SENS % of the loudest band (mono: its candidates).
  - **GUARD** (CTRL 3, ON in its upper half): test 13's moves without a new attack (a band beginning next to a note's
    band and reading its pitch within 17 cents; a young note moving down to its fundamental; a note's band back within
    20 blocks, no louder than 1.6x) and its stealing (a young note's voice only if quieter, a note in full's only at
    1.5x its level). Mono: a takeover in a note's first 20 blocks moves it. The voices' resume (a note back after a gap
    goes on without an attack) only with GUARD on.
  - At 0 each (as they start, and as tests 11-14's files read), the voices are test 11's: on the user's recording, 8
    tones x 80,250 blocks match b322ab2's DLL value for value.
- **The file:** version 4 as before, the three settings in its spare bytes 129-131 (zero in tests 11-14's files).
- **sy_t:** trk[4] at its end, sy_layout's 32nd entry. The note manager with the settings did not fit .syvnotes (6014
  of 5632 bytes): knobs() and g_down() moved to .syvdata (now 3804 of 3840; notes 4748).
- **On the recording** (the shares of short attacks, under 60 ms). POLY PAD, runs and chords; test 11 (all 0): 1840
  of 2084 in the runs, 1226 attacks in the chords. GUARD: 1304 and 651. SENS 20: 1264 and 886. WAIT 2 + GUARD: 1088
  and 482, notes within 2.7 ms of test 11's. WAIT 2 + SENS 20 + GUARD: 801 and 402. Mono (LADDER LEAD; test 11: 149
  short, 225 attacks in the chords): GUARD 131 and 188; WAIT 2 + GUARD 113 and 153.

**Emulator checks:** 360 pass on `release/sy-synth-test15`.

## SY synth test 16 (sy-synth-test16): fewer clicks, and no extra notes when a note is let go

The user on test 15: it "works better but seems to be subtle clicking (using chords with first few patches)", and
"if i test single notes on like punch bass, on note release triggers multiple extra notes no matter settings".

- **The release notes, measured** (sy15/release.py: the Sound Generator tracker's note-offs on the user's recording,
  the synth's attacks from 20 ms before to 400 ms after each). PUNCH BASS, test 11's tracking: 243 attacks around 134
  note-offs, up to 18 after one; most very quiet (median 5% of the note let go), median 95 ms after it. SENS could not
  stop them: it weighed a new note against the loudest band at that moment, which after a release is the quiet sound
  itself. The loud rest were other pitches, many below the note (an open string ringing as the finger lifts).
- **SENS** now weighs a new note against the louder of the loudest band and a held peak of it (PKH_DK 0.995 a block:
  -20 dB in 0.6 s; state pkh, updated in syv_block).
- **GUARD on a mono tone:** a band weaker than the note sounding does not take it over at any age (test 11: while
  the note was young); the note rides its band's gaps for G_RIDE (20) blocks unless the band's energy falls under G_END
  (0.1) of its last (the string stopped), so a held note's dropout neither ends it nor needs a new start.
- **PICK, GUARD's third position** (CTRL 3 in thirds: OFF, ON, PICK; file byte 131 0..2): mono tones only (on a poly
  tone a strum's later strings make no pick of their own, so chords lost their notes; there PICK is ON). The pick is
  test 10's rule again (sy_fp.c and sy_ref.py: a block's input peak at P_RATIO 2x the highest of blocks 3..18 back,
  over P_MIN, REFRACTORY 24 blocks), passed down as the blocks since it (syv_knobs_t.since, 255 long ago). With PICK a
  pending band is a note only if it began within P_WIN_M (45) blocks of a pick, whenever it confirms.
- **The clicks:** a young note's fast release over 10 ms (crf 0.990454 a sample; test 11: 3 ms); a faint voice (under
  5%) still waits to be rendered at its start, as test 11's did, but once rendered it stays rendered to its end (test 11
  left it out again whenever it fell under 5%, a step each way); and GUARD gives a sounding note's voice, young or not,
  only to a band G_STEAL (1.5x) louder (test 15 also gave a quieter young note's voice away: a strum's strings, young
  together, lost theirs to blips).
- **At all 0** the voices are no longer test 11's value for value on poly tones (the faint voices and the 10 ms
  release): their 10 ms levels are a median 0.4-0.6 dB from test 11's on the recording. Mono tones at all 0 still match
  it exactly.
- **On the recording.** PUNCH BASS (attacks around note-offs, the most after one; the runs' attacks and short ones):
  test 11 243 (18), 339 / 149; GUARD ON 163 (6), 247 / 48; PICK 82 (4), 161 / 27; PICK + SENS 20 68 (4), 144 / 15;
  135 of 136 notes heard in each, no later. POLY PAD with GUARD ON: runs 1452 / 1225 (test 11: 2084 / 1840), chords 609
  attacks, 3.3 voices sounding; with SENS 20, runs 721 / 571.
- **Slots:** g_down() back in .syvnotes (4878 of 5632); .syvdata 3680 of 3840; sy_block_t gains peaks[32] and
  last_pick (2368 bytes).

**Emulator checks:** 360 pass on `release/sy-synth-test16`.

## SY synth test 17 (sy-synth-test17): BOSS SY's way, test 10's tracking with test 11's voices

The user on test 16: "also trackign still bad. why can't it be as good as test 10:(", then "yeah whole point was to
emulate how boss sy pedals track". Test 10 decided no notes (each of 49 bands an oscillator of its own at its own level,
the filter's pick envelope over all of them); test 11's tones were synth voices per note, which need a note manager and
its decisions (start, end, which of 4 voices), and every one could go wrong. Test 17 keeps test 11's voices and drops
the notes:

- **The bands are the voices** (`sy_voice.c` bands_poly / bands_mono in place of notes_poly / notes_mono; SYV_NV 6).
  Every band the analysis sounds (unchanged since test 10: a band owns, the gate, the hold, FUND) has a voice from the
  block it begins (WAIT, SENS as on the TRACK page), at its own tracked pitch block by block (no smoothing: test 11's
  steady() and glide flattened vibrato) and its level (test 11's young confidence, then the tone's FOLLOW). A band
  beginning next to a voice's band at its pitch (17 cents, test 10's 1%) takes that voice on; a voice whose band stops
  follows a neighbour at its pitch, rides 3 blocks, or ends (a fast release under 24 blocks, test 10's AGE_MIN). A new
  band takes a free voice, else the quietest one's if louder (GUARD: 1.5x).
- **The pick's envelopes:** one amp and one filter envelope for every voice (the tone's ADSRs, the SG presets'),
  started at each input pick (test 10's pick rule, sy_fp.c), released once no band sounds and no pick came within
  B_WIN (45) blocks. Each voice sounds inside them with a gate of its own: a quick rise as its band begins (1 ms), a
  gentle one without a pick within B_WIN (20 ms: a ring, an open string, a flicker comes in softly), the tone's release
  as its band stops. The FM strike at each pick.
- **Mono:** every block, the loudest band begun within M_YOUNG (60) blocks may become the note: from silence on a pick
  (one at most B_WIN blocks before the band began) or at half the held peak (a pick unseen); over a sounding note with
  a pick at its level, without one at 1.5x (GUARD 2x; PICK: never); a young note (G_FIX, 45 blocks) moves, and one whose
  band dies moves to the band begun after it (the pick's blip gone), with no second attack; legato tones glide, and
  glide only between notes.
- **SHIFT:** a tap steps the page without showing the held page first (a knob turned with SHIFT held still does).
- **On the recording:** PUNCH BASS heard 135 of 136 notes, starts with test 10's bands (test 11's mono confirmed for
  13 ms), 130 attacks in the runs (test 11: 339), 4 under 60 ms (149; SENS 20 + GUARD: 0). Poly: notes start with
  test 10's bands, chords 3.5 voices sounding (test 11: 2.7). The demos (sy-voice-demos5) sound as much as test 11's
  but for SG PLUCK, whose pluck now comes once a pick (test 11 plucked again on every flicker).
- **The cost:** 6 voices take up to 105k instructions a step (FM PIANO; 13% of a block at one a cycle); the suite's
  limit is now 120k.

**Emulator checks:** 360 pass on `release/sy-synth-test17`.

## SY synth test 18 (sy-synth-test18): every string plays, a crash catcher, and the SY loudness law

Test 17 on the unit (FAT BASS, guitar on the Isolator): "most didn't sound", then a freeze with a steady high pitch
until the power was pulled. On the model guitar (open strings picked 0.6 s apart and left ringing, and softly over a
ringing low E) the twin showed why: the input's pick detector misses picks over ringing strings, a mono note moved to
a new string only on a pick or at 1.5x its level, the pick's envelopes never opened again after their release without a
pick, and FUND muted an open B or E picked over a ringing low E (its 3rd and 4th partials).

- **Strikes (sy_fp.c, sy_ref.py):** a band is struck while its energy is at 2x a follower over about 32 blocks
  (`ES_K` 1/32) and awake; the strike lasts 32 blocks (43 ms). A note's own partials rise with it; a string picked over
  others ringing rises alone. The voice engine gets the strikes in place of `nper` (unused since test 15).
- **FUND spares a struck string:** a whole multiple of lower sounding bands that only ring (each owned 32 blocks or
  more, not struck, not spared itself) is a string of its own while it owns (`fresh`). A multiple of a band struck with
  it is still its partial: B3 sounds over a ringing E2, B4 (B3's octave) does not.
- **Envelopes:** a string beginning softly after the pick's envelopes have released opens them again (the amp as the
  tone's, the filter at its sustain, no sweep).
- **Mono:** a struck band counts as picked for a start from silence once it has sounded 8 blocks reading steadily (a
  mute's click strikes many bands at once). A struck band begun 60 ms or more after the note took its string
  (`B_STRUM`: a strum's later strings leave the note on its first) takes the note at 0.3x the note's level now, once
  settled (`B_CONF` 8 blocks, `STABLE`), unless it sits an octave, an octave and a fifth or two octaves over a band
  struck lately with -20 dB of its energy (a new low string's partials own before its own band). Takeovers by the
  newest string attack as a pick's do (legato tones glide).
- **TRACK page:** CTRL 1 is LAW (OFF, 1:1, 2:1 in thirds) in WAIT's place; WAIT is 0. The file keeps LAW in WAIT's
  byte marked 0x80, OFF as 0 (a test 15-17 file's WAIT reads OFF, and a file with LAW OFF is byte for byte test 17's). LAW follows the SY-1000's per-voice volume step (DSP row b47e,
  decoded 2026-11-07): a band at a fraction r of the loudest of its five bands plays at r^2 of that one's volume under
  both readings of its divide step. 1:1 multiplies a voice's level by r (the band's level over the five's loudest):
  the synth follows the guitar dB for dB. 2:1 multiplies it by the band's level over a full pick's (at most 2): a square
  law, 2 dB of synth per dB of guitar, its neighbours' r^2 coming from the square itself.
- **The crash catcher:** the ITCM vector table's HardFault, MemManage, BusFault and UsageFault entries (the reset
  handler sets VTOR to 0 from its literals at 0x60080044) point at `sy_fault`, which keeps the stacked PC, LR, xPSR,
  the stack, CFSR, HFSR, MMFAR, BFAR, EXC_RETURN, the SY blocks and the page in `sy_crash` (0x83FE7F80, the SY slot's
  top: no boot row writes it), cleans its D-cache lines and writes SYSRESETREQ. After the reboot the UI tick shows
  `SY CRASH n` (the exception: 3 HardFault, 4 MemManage, 5 BusFault, 6 UsageFault), PC, LR, CF (CFSR) and AD (BFAR, or
  MMFAR) once, 4 s in, for 12 s. Not caught: a hang that is not a fault, and anything the reset does not keep (SDRAM
  across a SYSRESETREQ is kept on this SoC as far as is known, but unverified).

On the model guitar (FAT BASS's note band 60 ms after each pick): all six strings right when stopped, let go or left
ringing; softly over ringing strings the D string reads its octave for about 100 ms before it settles. On the user's
clean take (score17 / score18, test 17 -> 18): PUNCH BASS heard 135/136 both, attacks 130 -> 143, short 4 -> 10,
attacks in the chord part 16 -> 62, attacks after let-gos 119 -> 131; POLY PAD heard 133 -> 132, attacks 1420 -> 1455,
chord attacks 207 -> 207, chord voices 3.52 -> 4.14 (strings at a fifth or an octave now sound), after let-gos 1191 ->
1224. Starts as test 10's (median +0 ms). LAW 2:1 is about 5 dB quieter at the peaks (soft playing gets softer).

## Still not known

- How each test 2 tone sounds on a real guitar, and which are worth keeping.
- The heavier tones' cycles at SDRAM speed (the readout's SY line): the FM bell, supersaw, pad, organ and bass take
  about 1.4-1.6 times the saw lead's instructions.
- Test 4: whether a RESAMPLE or looper take with the synth on is as loud as one with it off (pair 1 x 2 is from
  the readout's rounded peaks).
- Test 5: whether FUND loses notes a chord needs; whether the screen's chord feels right with GATE on.
- Test 7: whether TX words 4/5 are BUS 2 (DM-404's reading): the synth on BUS 2 with an effect there.
- Test 6: whether single notes sound smooth now; whether the high E is still quiet (DYNAMICS); whether the stock FX
  screens and REMAIN behave on the unit as in DM-404; how the kit pads feel across the neck.
- Whether the chip takes a ROUTING DT1 while sampling is armed without a click in the recording.
- How the low notes' 20-30 ms feel in longer playing (nothing was reported against them).
- Test 3: whether the file saves and comes back on the unit (FX deep edit's way of saving works there), and whether
  the shared knob positions (the bus effect jumping after an edit) get in the way.
- Test 10: whether a looper take made from the guitar synth screen has the synth in it.
- Test 11: which tones sound good on a real guitar; whether the pick's blips or settling notes are heard; the engine's real cycles on the unit (the readout's SY line), and whether SLOW ever stops it.
- Test 12 on the unit: "awful" (late notes, chords without character); replaced by test 13.
- Test 13 on the unit: "still too much latency"; replaced by test 14.
- Test 14 on the unit: "no better"; replaced by test 15.
- Test 15 on the unit: "works better", subtle clicks in chords, extra notes on release; replaced by test 16.
- Test 16 on the unit: a SHIFT flash, a freeze (cause unknown, not reproduced), "trackign still bad"; replaced by test 17.
- Test 17 on the unit: "most didn't sound" (FAT BASS, open strings), then a freeze with a steady high pitch;
  replaced by test 18.
- Test 18: whether every string sounds on the unit; which LAW feels like an SY; whether the crash catcher's record
  survives the reset (a crash would show it).
- Whether MUTE BUS on ExtIn also keeps pair 0, which would be a simpler way than the Isolator to hear the synth
  alone.
