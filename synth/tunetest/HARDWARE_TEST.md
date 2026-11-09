# SY synth test 26: GLITCH, much glitchier

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 25:

- **GLITCH 0 to 49 is test 25 exactly.**
- **From 50, chord sounds play test 11's own chord notes** (4 voices; every flicker can take over a held note).
- **From 50 to 100, real glitches grow in, on every sound:** test 11's pops, wrong notes (an octave, a fifth or a
  twelfth off, up to half the notes at 100) and stutter (held notes restart every 30-100 ms at 100).
- Lead tracking is as in test 25.

1. Volume low. POLY PAD (pad 1), chords: turn GLITCH from 0 to 100 slowly.
2. SYNC LEAD (pad 7), single notes: GLITCH 0, then 75, then 100.

Tell me: is it glitchy enough now, too much at 100, or the wrong kind of glitch?
