# SY synth test 23: no clicks on held chords (GUARD PICK)

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 22:

- **GUARD PICK on the chord tones holds the chord.** Held low chords clicked because the synth's 6 voices kept
  switching between the guitar's overtones, which beat against each other. With GUARD PICK (CTRL 3 fully right on
  the TRACK page), a voice now rides through those dips, and a new voice needs a pick or a newly struck string.
  On your recording, POLY PAD's clicks on chords dropped from 118 to 12 (bridge pickup) and from 90 to 32 (neck).
- GUARD OFF and ON work as in test 22, and the leads and basses are unchanged.
- Next: repeated notes picked at the same loudness (still missed on leads and FM tones).

1. Volume low. POLY PAD (pad 1): TRACK page (tap SHIFT twice), turn CTRL 3 (GUARD) fully right for PICK.
2. Play the low G major 7 and a few other chords, held. Then the same with GUARD OFF to compare.
3. SG FM BELL (SHIFT + pad 5): the same, GUARD PICK, a few chords.

Tell me: are the clicks on held chords gone? Does any chord note go missing with PICK?
