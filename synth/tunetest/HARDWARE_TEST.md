# SY synth test 17: BOSS SY-style tracking with test 11's tones

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth rebuilt the way BOSS's SY pedals track. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **Tracks like test 10.** No more deciding what a note is: every string's band drives a voice of its own (up to 6, a
  full chord) from the moment the string sounds, at its exact pitch (bends and vibrato as you play them) and level.
- **Test 11's tones on top.** Each voice has test 11's waves and filters. The attack and the filter sweep come from
  your pick, shared by every string the way the SY pedals do it, so a string that starts ringing without a pick (an
  open string, a flicker) comes in softly instead of with an attack of its own.
- **Leads and basses:** a note starts on a pick; a hammer-on or slide moves the pitch with no new attack; glide only
  slides between notes now, not over bends and vibrato.
- **SHIFT:** a tap goes straight to the next page (no flash of the main page).
- The TRACK page still works: WAIT and SENS as before; GUARD ON makes it harder for a new string to take a sounding
  voice; PICK (leads and basses) lets only a pick change the note.

1. Volume low. Single notes, a bend, vibrato and chords on a few tones, including a lead (pad 7 or 8) and a bass
   (pads 9-11).
2. Compare it with how test 10 felt.

Tell me: does it track like test 10 now? How do the tones compare with test 11? If it freezes again, what were you
doing just before?
