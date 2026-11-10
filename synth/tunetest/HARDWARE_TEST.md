# SY synth test 31: guitar notes switch, REMAIN + FX fix

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, the quieter Sound Generator and kits, and the
hidden FX fix) plus the guitar synth. Not for sharing. To go back, patch v9.52 again. It has everything from test 30,
and the guitar synth sounds the same.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new, on the Sound Generator page and the kits:

- **Guitar notes on/off:** hold EXT SOURCE and press SUB PAD. A popup says GUITAR NOTES OFF or ON, and the SP
  remembers it. The guitar's own sound stays as it was.
- **REMAIN + FX on a lit effect** keeps the FX screen up and no longer changes the preview bus. A REMAIN tap on its
  own still changes the preview bus.

1. EXT SOURCE on, Sound Generator page or a kit: play a few notes, then EXT SOURCE + SUB PAD (OFF). The guitar
   plays no notes. EXT SOURCE + SUB PAD again (ON): the notes come back.
2. Press DELAY to light it, then straight away REMAIN + DELAY: the screen stays up and DELAY stays lit.

Tell me: does the switch work on the plain page and on a kit, and does REMAIN + FX keep the screen up?
