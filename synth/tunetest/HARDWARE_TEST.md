# SY synth test 12: clean note tracking for the guitar synth

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth with test 11's tones and new note tracking. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **No more glitches and extra notes.** Test 11 gave a synth note to every flicker the guitar made. On your clean
  recording that was about 2,000 notes for the 136 you played, most of them under 60 ms. Test 12 starts a note only
  once a string's pitch is clear. It ignores a note's overtones and the open strings ringing along, and it doesn't
  restart a note that only dips. On the same recording: 144 notes, none under 60 ms.
- **Same feel.** Notes start about as fast as in Sound Generator mode.
- The tones, knobs and screen are the same as test 11, and your tone settings carry over.

1. Volume low. On the guitar synth screen, play single notes, a bend, then chords, on a few tones.
2. Try a lead (pad 7 or 8) and a bass (pads 9-11) too.

Tell me: are the glitches and extra notes gone? Does any note you play get missed or come in late?
