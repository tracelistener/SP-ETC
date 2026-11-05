# SY synth test 4: the sound picker, and recording the synth

A test build: {{PARENT_REVISION}} (v9.52) plus the SY synth and guitar synth test 6 on the Sound Generator page. Not
for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **The picker:** hold VALUE and press EXT SOURCE.
  - The pads light up: your sound white, the other sounds blue, pad 16 red. Tap a pad to pick a sound; pad 16 turns
    the synth off.
  - While the pads are lit, CTRL 1-3 edit the sound without holding VALUE.
  - It closes after 4 seconds untouched, or with EXIT.
  - If the synth or EXT SOURCE was off, the chord turns it on.
  - Pressing VALUE in the picker opens the input FX's hidden settings, which VALUE + EXT SOURCE opened before.
  - VALUE + pad and VALUE + CTRL work as on stock again.
- **ROUTING can stay on Mix,** and the SP records the synth: REC, RESAMPLE, the looper and skip-back sampling.
  - On Mix you get everything, minus BUS 3/4 effects while the synth is on.
  - On ExtIn you get your guitar and the synth, without the pads.
  - The synth now plays whenever EXT SOURCE is on, on Mix too. Turn it off with pad 16 in the picker before you
    sample something else through the input.

1. Volume low at first. Guitar in, input FX Bypass, ROUTING on Mix (SHIFT + EXT SOURCE, CTRL 2), main screen.
2. Hold VALUE and press EXT SOURCE, tap a pad, and play. Turn CTRL 1-3 while the pads are lit.
3. Record a few bars with the looper, or RESAMPLE, while you play over some pads. Listen back: the synth should be
   there, as loud as it was live.

Tell me: is the picker better? Is the synth in your recordings, at the right level?
