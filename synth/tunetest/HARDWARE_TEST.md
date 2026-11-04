# Guitar synth test 2: fewer extra notes

A test build: {{PARENT_REVISION}} (v9.52) plus a guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

Against test 1's extra notes, the synth now ignores bumps and scrapes that do not make the string louder, holds its
note through short glitches instead of stopping and starting it again, never jumps an octave by itself, and in drum
mode plays a hit only for a real pick.

1. Volume low at first. Guitar in, EXT SOURCE on, input FX Bypass.
2. Open the Sound Generator in melodic mode with ARP OFF. Pick single notes, let each ring, then stop the string.
3. A slow melody with a slide or two.
4. Drum mode: pick single notes from the low E up to D# on the A string (pads 5 to 16), one hit per pick.

Tell me: any extra notes or hits left, and if the tracking still feels off, which: wrong notes, late notes, or
notes it misses.
