# SY synth test 24: quicker single notes, GLITCH and VOICES

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 23:

- **Single notes start sooner.** The note tracker now checks the newest sound every 2 blocks instead of every 4 on
  sound 3 blocks old. On your recording, lead and bass notes start 4-5 ms sooner on every string, and are as often
  right.
- **The TRACK page (tap SHIFT twice) is now GLITCH, SENS and VOICES.** LAW stays at 1:1 and GUARD at PICK, built in.
  - **GLITCH (CTRL 1), 0 to 100:** 0 is test 23's clean sound. Turning it up gives each voice its own attack and
    filter sweep, and lets every overtone and flicker start a voice. At 100 it's as glitchy as test 11. On the leads
    and basses, from 50 up the notes come from test 11's own note rules.
  - **SENS (CTRL 2), 0 to 100:** how loud a string must be, against your recent playing, to start a note. Twice the
    old range, and it now works on the leads and basses too (soft ghost notes start nothing).
  - **VOICES (CTRL 3):** AUTO plays each sound as designed. MONO makes any sound play single notes from the note
    tracker (pads and FM tones as leads). 2 to 6 caps the chord voices (fewer: calmer chords).

1. Volume low. SYNC LEAD (pad 7), TRACK page at GLITCH 0, SENS 0, VOICES AUTO. Play single notes up and down the neck.
2. SG FM BELL (SHIFT + pad 5) with VOICES at MONO: single-note lines. Then back to AUTO for chords, and try 3.
3. Turn GLITCH slowly up to 100 while you play, on SYNC LEAD and then on POLY PAD (pad 1) with chords.
4. Try SENS on a lead: around 30, then 60, with soft and hard picking.

Tell me: do single notes feel quicker than test 23? Does SG FM BELL on MONO stop missing notes? Where on GLITCH
does it start to sound like test 11? If a SY SLOW message ever shows, tell me where.
