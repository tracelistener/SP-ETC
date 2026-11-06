# SY synth test 14: test 11's tones with test 10's timing

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth with test 11's tones and test 10's tracking and timing. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **No more waiting.** Test 13 waited 8 to 16 ms before a new note got a voice (13 ms on leads and basses). Test 14
  waits at most 2.7 ms, usually nothing, so notes start when test 10's did. Leads and basses start about 13 ms sooner
  than in test 11.
- **Kept from test 13:** every chord note plays; a note moving between bands, a pick's overtone giving way to the
  real note, and a string coming back after a dip keep their voice without a new attack; a blip can't cut off a
  string you're holding. There are more blips than in test 13 (that wait was what removed them), but fewer than in
  test 11.
- The tones, knobs and screen are the same as test 11, and your tone settings carry over.

1. Volume low. On the guitar synth screen, play single notes, a bend, then chords, on a few tones.
2. Try a lead (pad 7 or 8) and a bass (pads 9-11) too.

Tell me: is the timing right now? Are the blips that are left OK?
