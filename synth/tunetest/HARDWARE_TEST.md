# SY synth test 3: three knobs per sound, saved

A test build: {{PARENT_REVISION}} (v9.52) plus the SY synth (15 sounds, now editable) and guitar synth test 6 on the
Sound Generator page. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new: each sound has three knobs. Hold VALUE (pushed in) and turn CTRL 1, 2 or 3. A popup shows the sound, the
setting and the knob's position: 64 is the sound as it was in test 2. Each sound keeps its own settings. While VALUE
is held the knobs don't touch the bus effect, but the next time you turn a knob without VALUE, the bus effect jumps
to where that knob now sits.

- CTRL 1, BRIGHT: darker to brighter.
- CTRL 2, one setting per sound: resonance (saw lead, wah), width (square, pulse), detune (supersaw), attack (pad,
  strings), rotary speed (organ), breath (flute), metal (bell), how far it opens on each pick (brass), sub level
  (bass, warm), sweep speed (sweep), step rate (seq: 1/8, 1/16, 1/32).
- CTRL 3, LEVEL: the synth's volume, from silent to twice as loud.

Your settings and the sound you picked are saved on the SP when you let go of VALUE, and come back after a restart.

Picking a sound is as in test 2: VALUE + pad 1-15, and pad 16 for off.

1. Volume low at first. Guitar in, EXT SOURCE on, input FX Bypass, ROUTING ExtIn, main screen.
2. Pick a sound, then hold VALUE and turn CTRL 1, 2 and 3 while you play.
3. Switch the SP off and on, press EXT SOURCE, and play: the same sound with your settings.

Tell me: are the knob settings useful, and which would you change? Did your settings come back after the restart?
