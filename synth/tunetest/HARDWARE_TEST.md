# Guitar synth test 6: letting notes go, and chords

A test build: {{PARENT_REVISION}} (v9.52) plus a guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What changed since test 5:

- Letting a fretted note go no longer plays a second note. That second note was the open string ringing for a
  moment. The synth note also stops sooner when you stop the strings.
- On a held chord, each string you pick plays its note. In test 5 the strings ringing together sounded murky, so the
  synth played nothing. A string an octave above one that's still ringing may come out an octave off.

ROUTING stays on ExtIn, as in test 5.

1. Volume low at first. Guitar in, EXT SOURCE on, input FX Bypass, Sound Generator open.
2. Pick single notes and let each one go right away: one note each, no second note.
3. Hold a chord and pick its strings one by one: each one plays.
4. Play as you did in test 5 (melodies, riffs): it should be no worse.

Tell me: are there any second notes left? Which chord notes still don't play, or play wrong? Did anything get worse?
