# SY synth test 27: GLITCH much glitchier, and picked note changes attack

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again. It has everything from test 26, so skip test 26.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 25:

- **Picked note changes on the leads attack.** When you fret a new note and pick it, the note tracker hears the
  pitch change first and the pick gets lost in the note already playing. A quick pitch change (a new fret) now
  attacks on SYNC LEAD, LADDER LEAD and any sound on VOICES MONO. Bends and slides still glide.
- **GLITCH 0 to 49 is test 25 exactly.** From 50, chord sounds play test 11's own chord notes, and pops, wrong notes
  and stutter grow in on every sound up to 100.

1. Volume low. SYNC LEAD (pad 7), GLITCH 0: play your F G G# lick, picking every note, and a few bends.
2. POLY PAD (pad 1), chords: turn GLITCH slowly from 0 to 100. Then SYNC LEAD at 75 and 100.

Tell me: do the picked notes in the lick attack now, and do bends still glide? Is GLITCH glitchy enough now, or too
much at 100?
