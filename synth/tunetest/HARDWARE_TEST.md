# SY synth test 15: test 11, with a TRACK page to tame its artifacts

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth of test 11 (its tones and tracking), with three new settings. Not for sharing. To go back, patch v9.52
again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **Test 11 again.** With the new settings at 0 (as they start), the synth plays exactly as test 11 did.
- **The TRACK page:** tap SHIFT twice on the guitar synth screen (main page, OTHERS, TRACK; a third tap goes back).
  The settings are for every tone and are saved.
  - **CTRL 1, WAIT (0-16 ms):** how long a string has to sound before it gets a note. Higher drops more of the pick's
    blips, but notes start later.
  - **CTRL 2, SENS (0-50):** how loud a new note must be, as % of the loudest string. Higher drops quiet stray notes;
    too high and quiet chord notes go too.
  - **CTRL 3, GUARD (OFF / ON):** ON stops blips from cutting off strings you hold, and stops the extra attacks when a
    note moves between bands, when a pick's overtone gives way to the real note, or when a string dips. No added
    latency.
- The tones, knobs and screen are test 11's, and your tone settings carry over.

1. Volume low. On the guitar synth screen, play single notes and chords: it should sound like test 11.
2. Tap SHIFT twice for TRACK. Turn GUARD on, then try SENS, then WAIT, playing as you go.

Tell me: which settings sound best to you, and which artifacts are still there?
