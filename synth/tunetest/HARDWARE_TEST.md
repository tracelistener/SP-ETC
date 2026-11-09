# SY synth test 28: test 27's sound, with more room

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

It should sound exactly like test 27: checked sample for sample against it on your recordings. Underneath, the note
tracker does its work with 14% fewer instructions at its busiest, and about 5 KB is free for new features (test 27
left under 1 KB).

1. Volume low. Play as on test 27 for a few minutes: SYNC LEAD (pad 7) with your lick and some bends, then POLY PAD
   (pad 1) chords with GLITCH from 0 to 100.

Tell me if anything sounds or feels different from test 27, or if it freezes. And test 27's open questions: do the
picked notes in the lick attack, do bends still glide, and is GLITCH too much at 100?
