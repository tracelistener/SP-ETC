# Note tracker tests 1 and 2, guitar synth tests 1 to 4

Test-only builds, not for the patcher: v9.52 (combined-test17) with the CPU meter of IR diagnostic test 3 and a
note tracker on the input. Test 2 (tune-test2) is test 1 with a new pluck test and the plucks heard on the readout
(see "Test 1 on the unit" below). Guitar synth test 1 (gtr-synth-test1) is test 2 playing the Sound Generator (next
section); synth test 2 (gtr-synth-test2) is synth test 1 without its extra notes; synth test 3 (gtr-synth-test3)
plays like the SY-1000's Dynamic Synth; synth test 4 (gtr-synth-test4) undoes test 3's voice following and fixes
what made test 3 worse on the unit (the sections after).

## Guitar synth test 1 (gtr-synth-test1)

Test 2's tracker plays the Sound Generator, one note at a time:

- **When:** on the Sound Generator page (page 0x1E) with EXT SOURCE on, the tracker runs with the readout hidden
  (and, as before, while the readout is shown, on any page).
- **The note** (audio task, `tune_fp.c`): `tt.syn` = seq << 16 | (note + 1), 0 none, written whole. On when a pluck
  goes steady; moved (a new note-on) when the steady note changes while it plays (a slide, a hammer-on: no pluck);
  none when the steady note is gone (4 unvoiced analyses: the string stopped, or faded under -54 dBFS). A note going
  steady without a pluck while nothing plays starts nothing (another string ringing on after one was stopped).
- **Playing it** (UI task, `syn_ui`, every 1 ms tick): through the entry MIDI IN takes on that page. The kits' note
  gates (the stock dispatcher's 0x80066e64 note-on and 0x800670b8 note-off jump to them) end their SG route with
  `b.w arp_midi_event` (0x83fa3448): r0 = 2 (the route), r1 the note, r2 the velocity (0 for off), r3 0 on / 1 off.
  The builder reads the address from both gates. A new note-on first lets go of the one before; velocity 100. So
  ARP takes the note into its list and drum mode turns notes 36-51 into pads 1-16, as for MIDI. In the UI task
  because a note-on may wait about 3 ms for a busy voice to fade (v9.5's stealing), as the MIDI task's does: the
  audio task must never wait for itself.
- **Leaving the page** stops the Sound Generator's voices (as for MIDI): `syn_ui` forgets its note without a call,
  and back on the page nothing replays. A stopped tracker (EXT SOURCE off, SLOW) lets go of its note.
- **The delay:** the steady note 15-32 ms after a pluck (emulator; the unit's low E: 32), up to a 1 ms UI tick, then
  the voice's start.
- **On the unit (2026-11-03):** "tracking not the best / no stuck notes. sometimes extra notes especially with drum
  kits" (in drum mode every note-on is a hit).

## Guitar synth test 2 (gtr-synth-test2): fewer extra notes

Three ways synth test 1 made extra notes, found in the emulator, and their fixes in `tune_fp.c`:

- **A thump or a scrape on a ringing string** (the hand, the pick) spoils the analyses that span it: 4 unvoiced in
  a row cleared the steady note, the synth let go, and the pluck it also made went steady and started the note
  again. Now the synth lets go only once the newest 4 blocks' peak is under 0.3 x what it was at the last voiced
  analysis (a hand on the string), else after 12 unvoiced analyses (64 ms, so nothing sticks); and a pluck heard
  while it plays starts a note only if that peak is 1.5 x the pluck's reference by the time it goes steady (a real
  re-pick lifts the string; a thump does not).
- **A note between two semitones** (a sharp string, vibrato) flickered the steady note, and every flicker moved the
  synth. A move without a pluck now needs 3 analyses in a row on a note, each within 30 cents of it, and is never
  an octave or a harmonic's interval (12, 19, 24, 28, 31: the tracker's own mistakes).
- **Drum mode** played every move as a hit: there only plucks play. `syn_ui` copies the kits' `kit_mode` (0x83fc58e0,
  the byte `arp_midi_event` tests first; the builder reads its address there) to `tt.drum` every tick.

The readout's steady note is unchanged (it still shows the flicker).

## Guitar synth test 3 (gtr-synth-test3): Dynamic Synth ways

Test 2's rules stay. Three changes follow the SY-1000's Dynamic Synth. Its controls come from the SY-1000 v1.20's
own parameter list (its readable host image; the synth's DSP code itself sits in its encrypted BMC image): PLAY
FEEL (FEEL1-4, NO DYNA), DYNAMICS 1-10, LOW VELO CUT, CHROMATIC OFF/TYPE1-3, and envelopes with an ATTACK but no
decay or release of their own.

- **Velocity from the pick** (PLAY FEEL, DYNAMICS): the note-on's velocity is 200.8 x the square root of the
  highest block peak (low-passed, at 12 kHz) from the pluck to its steady note. 127 is at 0.4 of full scale; in
  `tune_ref.py`'s pickup model, a pick peaking at 0.45, 0.15, 0.05 and 0.015 of full scale plays 121, 70, 40 and
  22. The stock MIDI note-on sets the voice's level to velocity x 100 (`+0x74`, applied every sample), so this is
  loudness. MIDI notes never used the LEVEL knob.
- **The guitar's own pitch:** the Sound Generator sounds MIDI note n at pitch n - 48 (`+0x5c`), frequency TUNE x
  2^((pitch - 33) / 12): an octave below n. Tests 1 and 2 played an octave down. `syn_ui` now sends n + 12 + 12 x OCT
  (the SG's OCT, -3..+4, at 0x80591c4c), within MIDI 12-127. Drum mode keeps the guitar's note (the pad it strikes).
- **The voice follows the string** (CHROMATIC OFF; the level following the string). With ARP off and not in drum
  mode (`tt.dyn`, from `kit_mode` and the arp's `arp_mode` 0x83fc7b70, the word `arp_midi_event`'s melodic path tests
  first; the builder reads it there), there are no moves. Every block, `voice_update` writes the voice holding our
  note: sounding, not releasing, its `+0x194` the note `syn_ui` sent (`tt.sent`), not a noise type (13, 14).
  - Its pitch steps, `+0x20` = f / 48000 and `+0x38` = 2 pi f / 48000: the stock code sets them only at a note's
    start, and the oscillator adds them to its two phases every sample. They come from the voice's own pitch and
    TUNE, bent to the tracked pitch. Every voiced analysis after the steady note moves the followed pitch: a step
    under a semitone at once (a bend, vibrato), a bigger one (a hammer-on, a slide's end) once 3 analyses in a row
    agree on its note, never by an octave or a harmonic's interval. The voice glides 0.3 of the way a block. The
    fork's filter envelopes read `+0x20` for their cutoff, so the cutoff bends too. The FPU here is single
    precision: the doubles are written as raw words.
  - Its level, `+0x74`: the same velocity of the string's level now (the highest peak of the newest 13 blocks, 17
    ms, longer than the lowest period), 0.5 of the way a block up and 0.15 down.
  - With ARP on, the moves stay test 2's (the arp needs notes), and the voices are left alone.
- The builder guards the stock code this relies on: the MIDI note-on's `+0x194`, `+0x5c`, `+0x60`, its `+0x20` and
  `+0x38` stores and their 48000 and pi literals, an idle voice's level; the oscillator's use of all three every
  sample; and the fork's SG module loading the clones' base, 0x8353a310.

Stock pitch bend would not do: the SP-404MKII's MIDI implementation chart receives pitch bend only for the Vocoder
input FX (channel 11), never the Sound Generator. Hence the voice writes.

**On the unit (2026-11-03):** "stuck notes. bad tracking. worse than before."

## Guitar synth test 4 (gtr-synth-test4): test 3's stuck notes

Why test 3 got worse, in `tune_ref.py` with strings played as on a guitar (the emulator's phrases had stopped each
string before the next, or played legato without picks):

- **Picks at the ringing string's level were missed.** The pluck test wants a block peak twice the highest of the 21
  ms before. A melody on one string, each note picked as hard as the last (E3 G3 A3 B3 A3 G3, 0.3 s each), is 1
  pluck of 6; E3 picked 6 times is 1 pluck, one held note. Test 2 still played the melody through its moves (the
  steady note changes); test 3 had no moves, so its voice slid the first note through the melody: one stuck,
  sliding note.
- **Strings ringing together** (an arpeggio, a melody across strings) mix into a "common" period below them: the
  tracker read C2, D2, E2, G2 for G3..G4 ringing, and every pluck it heard there started a wrong low note.

Test 4 (`tune_fp.c`, the same in `tune_ref.py`):

- No voice following (test 3's pitch and level writes, the ARP read and the voice guards are gone); moves are test
  2's again, everywhere but drum mode.
- **A pick's click** is a pluck too: the block's energy over 2 kHz (a 2nd-order Butterworth high-pass on the input,
  before the low-pass) at least 1e-4 and twice the most of blocks 2-16 back (20 ms, over the lowest period, since a
  low string's wave sends its highs once a period), with the block's peak at least -48 dBFS. A ringing string's
  highs die fast; a new pick brings them back. On the pickup model the click at picks is 2.3-36 x (2.3: a re-pick
  at less than half the ringing level) and elsewhere at most 1.6 (a thump); heavy overdrive reaches 2.9 only within
  6 blocks after a pick, inside the 32 ms where no new pluck can start.
- **Only clean readings count:** an analysis whose dip bottom is over 0.15 counts as unvoiced. The bottom is a
  parabola's through the 6 kHz dip and its neighbours (YIN's step 5): at whole lags, a period between two of them
  reads murky on one clean string (E6, 4.55 lags: 0.2; the first build of test 4 lost its E6 there). With it, one
  string from B1 to E6 reads under 0.08 (vibrato, fast bends, decays and heavy overdrive included); strings ringing
  together read up to 0.33, their wrong low notes 0.23-0.33. So a mix plays nothing new, and after 12 murky
  analyses (64 ms) the synth lets go instead of holding a stuck note.
- **A pluck going steady on another note always plays it** (test 2 asked any pluck heard while a note played for a
  1.5 x rise). On the note playing it starts it again if the highest peak since 4 blocks after the pluck is 0.5 x
  its reference when the pick clicked (an even or softer re-pick), else 1.2 x (a thump has no click and its level
  never rises).
- Velocity 50 + 77 x the square root of the pick's peak over 0.4 (127 there), a move's the string's level now:
  softer than test 3's curve, so a soft pick stays audible.
- OCT moves the note; at 0 the octave tests 1 and 2 played (the Sound Generator sounds MIDI an octave low), +1 the
  guitar's own pitch. Drum mode keeps the guitar's note.

Cost on the twin: the steady note comes about 6 ms later (the first readings after a pick are murkier): the open
strings run AVG 29 ms (test 2: 22), a re-pick about 30 ms.

The first step towards a guitar synth (the Sound Generator played from the guitar): how
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

## Test 2 on the unit (2026-11-03)

- **The open low E alone,** rung about 5 s, then stopped by hand: E2 throughout, N1 P1, still P1 after the hand
  stopped it. The open high E the same (E4).
- **The six open strings slowly** (each rung about 3 s, stopped, then the next): P 1, 2, 3, 4, 5, 6.
- **The first, quicker run:** LCK 32 after the low E (the emulator: 28), AVG 33, MAX 21, but P23. The extra plucks
  did not go steady (phantoms going steady would have pulled AVG towards 11), and "sometimes P jumps on its own
  before I get to the next string": something between strings (the hand, the pick) passes the pluck test now and
  then. For the synth that is harmless while the string is stopping (nothing goes steady), but on a string still
  ringing it goes steady on the same note and the synth starts that note again: watch for repeated notes in synth
  test 1 (a fix would ask a re-pick of the same note to keep its level up after the pluck).

## Checked in the emulator (not on hardware)

`python synth/test_tune_test.py OUT_DIR --kits kits-v9.46-test3/kits-manifest.json`: NAM test 2's meter checks
(imported) on this image, and the tracker on Unicorn's Cortex-M7 model, against `tune_ref.py` after every block.
128 checks pass on `release/gtr-synth-test4` (APP1 `daf588a7…d52f`, 3,182,432 bytes; the module 24,768 bytes), 126
on `release/gtr-synth-test3` (APP1 `03679e29…420d`, 3,182,304 bytes; the module 24,640 bytes), 111
on `release/gtr-synth-test2` (APP1 `637424b5…1a63`, 3,180,576 bytes; the module 22,912 bytes), 103 on
`release/gtr-synth-test1` (APP1 `19df4dda…1559`), 90 on `release/tune-test2` (APP1 `68691893…96d2`), 87 on
`release/tune-test1` (APP1 `7cd37ebf…17cb`). Test 3's tracker step, without voice writes: 14,746 / 12,417 / 12,417 /
26,136 instructions by phase, 272 bytes of its own stack; the voice writes' cost is not measured.

Synth test 4's own checks (the module against `tune_ref.py` after every block, the MIDI entry stubbed):

- Six open strings: notes 40 45 50 55 59 64, velocities 126 124 121 123 124 122, each on 39 31 27 29 25 23 ms after
  its pluck (test 2: 28 31 21 19 20 17).
- E3 picked six times on one string, 0.3 s apart, as hard: six notes (five plucks only the click heard; test 2 heard
  one and held it). A melody on one string (E3 G3 A3 B3 A3 G3, no gaps): each note once, on its pick. A riff on the
  low E (E2 E2 G2 A2 E2, 0.25 s each): every note, the repeat too; in drum mode, a hit for each.
- An A2 picked four times, softer each time (0.45, 0.2, 0.08, 0.03 of full scale): velocities 123 97 81 69.
- G3 A3 B3 D4 E4 G4 picked 0.3 s apart on six strings, all left ringing: G3 plays, then 149 murky analyses and the
  synth lets go 0.569 s in, 0.1 s after the A3 (no wrong low note, no stuck G3).
- Test 2's thump (a pluck without a click: the note goes on), re-pick 2 s on (plays again) and sharp vibrato (G3
  held while the steady note flickers) hold. A hammer-on (E2 to G2, no click): the note moves 36 ms after it; in
  drum mode at OCT +2, one hit at the guitar's note.
- OCT +1, -1, 9 and -7 play an A2 as 57, 33, 93 (held to +4) and nothing (held to -3: MIDI 9, under 12).
- The step: 15,333 / 13,004 / 13,004 / 26,632 instructions by phase (the click's high-pass adds about 590 a block),
  316 bytes of its own stack.

Synth test 3's own checks (the MIDI entry stubbed as a voice the stock note-on sets up; every voice write against
`tune_ref.py`'s in the same block and against the module's own bend and level):

- The stub sets a voice as the stock MIDI note-on (0x80132118, run in the emulator) does: sounding, the note at
  `+0x194`, pitch note - 48, level velocity x 100, the steps of TUNE x 2^((pitch - 33) / 12). MIDI 57 (A3, 220 Hz)
  sounds at 110 Hz: an octave below.
- Six open strings: notes 52 57 62 67 71 76 (the guitar's + 12), velocities 126 121 118 120 122 118; 7,086 voice
  writes, the worst 0.0004 cents and 0.0001 of a velocity from the twin, the pitch step within 4e-7 of its own bend.
- An A2 picked hard then softly (0.45 and 0.05 of full scale): velocities 121 and 40.
- A whole-step bend on G3: one note, its voice bent from 0.7 to 202.7 cents; its level 11,921 -> 7,733 halfway.
- Hammer-ons E2 G2 A2 B2: one note (52), 3 steps, the voice up to 700 cents. With ARP on: test 2's moves (52, 55, 57,
  59), no voice writes.
- A G3 40 cents sharp with 25 cents of vibrato: one note, the voice following 16..65 cents.
- Test 2's thump, re-pick and drum-mode checks hold (drum mode at OCT +2: one hit, the guitar's own note 40).
- OCT +1, -1, 9 and -7 play an A2 as 69, 45, 105 (held to +4) and 21 (held to -3); a noise type's voice is left
  alone; off the page, nothing is written.

Synth test 2's own checks (the module against `tune_ref.py` after every block, the MIDI entry stubbed):

- A thump on a ringing low E (2.5 x its peak for 3 ms, 0.8 s on) is heard as a pluck and goes steady, but the
  level never rose: the synth note goes on, (40 on, 40 off). Test 1's rules let go and started it again.
- The low E picked again 2 s on, as hard: the level rose, so the note starts again (on, off, on, off).
- Drum mode (`kit_mode` set), the legato phrase: the steady note moves E2 G2 A2 B2, one hit (40 on).
- A G3 40 cents sharp with 25 cents of vibrato: the steady note flickers G3/G#3 16 times, the synth holds G3.
- `tune_ref.py` alone: thumps of 2-6 x the ringing peak at 0.5-1.1 s on E2, A2, G3 and E4 all hold the note; the
  six open strings overdriven (drive 3 and 6, both pickups) give one note a string.
- The drum-mode byte is the kits' own `kit_mode`; a step costs 14,741 / 12,412 / 12,412 / 26,130 instructions.

The synth (gtr-synth-test1), with the MIDI entry stubbed and `syn_ui` run after every block:

- The notes go to `arp_midi_event` 0x83fa3448, where both kits' note gates' SG routes jump (the kits' own symbol
  agrees); the module's `tt.syn` equals `tune_ref.py`'s after every block of every phrase.
- Six open strings on the Sound Generator page, EXT SOURCE on, the readout hidden: six notes, each on (2, note, 100,
  0) in the block its pluck went steady (28, 31, 21, 19, 20, 17 ms after it) and off (2, note, 0, 1) when its
  string is stopped.
- Legato (one pluck heard): the synth follows the steady note, E2 G2 A2 B2, each move an off then an on.
- Off the page (the readout shown, the tracker running): nothing. EXT SOURCE off on the page: the tracker stays off.
  A note playing when EXT SOURCE goes off: let go at the next tick. A note playing when the page closes: forgotten
  without a call, and nothing replays back on the page.
- A step costs the same: 14,739 / 12,410 / 12,410 / 26,127 instructions by phase.

The tracker (tune-test2, and gtr-synth-test1 the same):

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

## Not known (synth test 4 on the unit)

- Synth test 1 played on the unit (no stuck notes), so the UI tick reaches the Sound Generator as MIDI does. Test 2
  was not reported on its own; test 3 was worse (above).
- Whether a real pick clicks as the pickup model's do (the model has no pick noise; a real pick should click more),
  and whether fret or hand noise clicks: a click on the note playing restarts it only if the level kept half, a
  click with no steady note plays nothing.
- Whether a real string reads as clean as the model's (under 0.08). A guitar that reads murkier (a chorus or a
  noisy input before the SP) would play fewer notes: the readout's Q is 100 minus the whole-lag reading x 100, a
  rough guide (Q 85 or more is clean either way).
- Strings ringing together still play nothing new: a mono tracker on one input hears a chord's common pitch. Play
  one string at a time, or stop the one before.
- How late the synth feels: the steady note about 6 ms later than test 2's (23-39 ms after a pick on the model).
