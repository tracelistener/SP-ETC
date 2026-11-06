# SY synth test 13: test 11's tones with test 10's tracking

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth with test 11's tones and test 10's tracking. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **Test 10's tracking.** Every note the bands find plays straight away, as in test 10 and test 11, and nothing in a
  chord is held back (test 12 dropped sevenths, ninths and other notes near overtones, and waited on every note).
- **Fewer glitches than test 11.** A band now has to sound for 8 ms before it gets a voice, and most of the pick's
  blips are gone by then. A note moving between bands, a pick's overtone giving way to the real note, and a string
  coming back after a dip keep their voice without a new attack. A blip can't cut off a string you're holding.
- The tones, knobs and screen are the same as test 11, and your tone settings carry over.

1. Volume low. On the guitar synth screen, play single notes, a bend, then chords, on a few tones.
2. Try a lead (pad 7 or 8) and a bass (pads 9-11) too.

Tell me: does it respond like test 10? Do chords sound full? Are there still glitches or extra notes?
