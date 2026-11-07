# SY synth test 19: single notes from the note tracker

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 18:

- **Single-note tones (the basses and leads) take their notes from the note tracker**, the one the Sound Generator
  page's guitar synth uses, instead of from the bands. On a low string the bands hear the overtones first, and test 18
  played them: the extra notes at each pick. The tracker reads the real note sooner (about 18 ms after the pick on the
  low strings) and almost never wrong, so notes should start cleanly and no later than before.
- **No more notes on let-go.** Lifting a finger used to play the fret under it, or an open string, for up to 0.3 s.
  The tracker's let-go rule now decides, so those are gone.
- **No more dropout every 7 seconds.** Since test 4 a timer wrap stopped and restarted the synth about every 7 s,
  cutting whatever was ringing. Fixed.
- **LAW 2:1 is louder:** a medium pick now plays as loud as LAW OFF.
- Chords and the pad tones are unchanged.

1. Volume low. FAT BASS (pad 9): pick the open strings one by one, letting them ring, then play a bass line.
2. A lead (SYNC LEAD, pad 7, or LADDER LEAD, pad 8): a few phrases with slides and hammer-ons.

Tell me: any extra notes? Any late or missing ones?
