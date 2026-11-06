# SY synth test 16: fewer clicks, and no extra notes when you let go

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth of test 11 (its tones and tracking) with the TRACK page. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 15:

- **Fewer clicks in chords.** A short stray note now fades over 10 ms instead of being cut in 3 ms, and a quiet voice
  no longer drops in and out. With GUARD on, a blip can't take the voice of a chord string that has just started.
- **Extra notes when you let go of a note:**
  - **SENS** now also compares a new note with what you just played (fading over about half a second), so the quiet
    sounds after a note stops stay out. Try 15-25.
  - **GUARD ON** on leads and basses: a weaker sound can't take over the note, and a note that drops out for a moment
    carries on instead of restarting.
  - **GUARD PICK** (CTRL 3 turned all the way up), for leads and basses: a new note needs a pick. What rings on after
    you let go (an open string, harmonics, the mute) can't start one. On chord tones PICK works as ON.
- The tones, knobs and screen are test 11's, and your settings carry over.

1. Volume low. Chords on the first pads with GUARD ON: are the clicks gone?
2. PUNCH BASS: single notes, letting each one go. Try GUARD PICK, then SENS 20 with it.

Tell me: any clicks left, and on which pad? Do the extra notes on release stop?
