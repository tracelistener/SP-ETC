# SY synth test 32: SENS, a fix for wrong low starts, SHAPE and FILTER pages, cleaner chords

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, the quieter Sound Generator and kits, and the
hidden FX fix) plus the guitar synth. Not for sharing. To go back, patch v9.52 again. It has everything from test 31.
No note starts later than in test 31.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

On the guitar synth screen, SHIFT taps now step through five pages: main, OTHERS, TRACK, SHAPE, FILTER.

- **SENS** (TRACK, CTRL 2): how quiet a pick can be and still play a note. 50 is as before. Turn it up if soft
  picks are missed, down if stray notes appear. (Your old SENS setting goes back to 50 once.)
- **SHAPE**: ATTACK (how fast a note fades in), RELEASE (how long it rings after you let go) and GLIDE (how
  single-note sounds slide between notes; OFF jumps), in ms. Each sound starts at its own setting.
- **FILTER**: ENV and RESO for every sound with a filter. On a sound whose own knob is ENV or RESO, it is the same
  setting.
- **Fast picking** no longer starts some notes on a wrong low note for a moment.
- **Chords** (POLY PAD, STRINGS and the other chord sounds): an overtone that got a voice of its own fades
  12 dB, so chords have fewer wrong notes.

1. SYNC LEAD (pad 7): fast runs and some soft picks. If soft picks are missed, raise SENS.
2. POLY PAD (pad 1): chords; then SHAPE: ATTACK up for a swell, RELEASE up for longer tails.
3. Any lead: GLIDE up and down.

Tell me: are the chords cleaner, do soft picks play with SENS up, and do the new knobs make sense?
