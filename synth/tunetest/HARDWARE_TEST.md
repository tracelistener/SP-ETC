# Guitar synth test 3: bends and pick dynamics

A test build: {{PARENT_REVISION}} (v9.52) plus a guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

Test 2's rules against extra notes stay. New, after the SY-1000's Dynamic Synth:

- The synth now plays at your guitar's pitch. Tests 1 and 2 played an octave lower. The Sound Generator's OCT
  setting moves it.
- How hard you pick sets how loud the note is, and the synth fades as the string fades.
- With ARP OFF in melodic mode, the synth follows bends, vibrato and slides, and a hammer-on glides to the new note
  instead of starting a new one.

1. Volume low at first. Guitar in, EXT SOURCE on, input FX Bypass.
2. Open the Sound Generator in melodic mode with ARP OFF. Pick single notes, some soft and some hard.
3. Bend a note up a whole step, then add some vibrato.
4. A slow melody with hammer-ons and a slide.
5. Drum mode: single notes from the low E up to D# on the A string (pads 5 to 16), soft and hard.

Tell me: does the synth follow your bends, do soft and hard picks sound different, and are there extra notes or
hits left?
