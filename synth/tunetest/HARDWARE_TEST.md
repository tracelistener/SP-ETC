# SY synth test 25: GLITCH on pads, and softer picks

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 24:

- **GLITCH now bites on pads and the other chord sounds.** Turning it up shortens their attack and release. At 50 a
  pad's slow swell takes about 30 ms; at 100 every voice starts in 3 ms and stops in 40 ms, so the flicker becomes
  blips and cut-offs you hear. From 90 up, chord sounds on VOICES AUTO play at most 4 voices (test 11's), so notes
  get cut more. Leads and basses are as in test 24, and GLITCH 0 is test 24 exactly.
- **Soft picks over a ringing note count now.** While a note sounds, the note tracker also listens for the pick's
  scratch above 6 kHz. On your recording SYNC LEAD plays 269 of 318 picks (test 24: 257), and the first note is
  right more often (249 times, test 24: 243).

1. Volume low. SYNC LEAD (pad 7), TRACK page at GLITCH 0, SENS 0, VOICES AUTO. Play lines with soft repeated notes
   and soft notes after loud ones.
2. POLY PAD (pad 1), chords: turn GLITCH slowly from 0 to 100. Then STRINGS (pad 2).

Tell me: does SYNC LEAD catch more of your quiet notes, and does it play notes you didn't? Does GLITCH change the
pads enough now, and where does it get too much?
