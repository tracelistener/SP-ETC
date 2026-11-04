# Guitar synth test 1: the Sound Generator plays what your guitar plays

A test build: {{PARENT_REVISION}} (v9.52) plus a guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

Keep the volume low at first: the synth plays on top of your dry guitar.

1. Guitar in, EXT SOURCE on, input FX Bypass.
2. Open the Sound Generator in melodic mode with ARP OFF. Pick a sound with a clear start, LEVEL not too high.
3. Pick single notes, let each ring, then stop the string with your hand. The synth should play the same note when
   you pick and stop when you stop the string.
4. Play a slow melody, and try a slide or a hammer-on: the synth should follow.

- It plays only while the Sound Generator is open and EXT SOURCE is on (EXT SOURCE off stops it).
- One note at a time, all at the same strength for now.
- With ARP on, the arp plays your note. In drum mode, the notes from the low E up to D# on the A string play pads
  5 to 16.
- The box (hold EXIT on the main screen) still shows what it hears, as in note tracker test 2.

Tell me: are the notes right, do they start and stop with the strings, does the synth feel late, and any stuck or
extra notes.
