# SY synth test 11: a synth voice for every note, 20 tones

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
SY synth with a voice of its own for every note. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **Every note gets a full synth voice**: oscillators, a filter and envelopes of its own. The tracking is the same as
  before; only the sound changed.
- **20 tones**, in the styles you picked: Juno, Jupiter, Polysix, Poly-800 and Wavestation pads and keys, Mono/Poly
  and Minimoog leads, Moog, 303 and SH-101 basses, a supersaw, DX7-style FM, and six Sound Generator tones made with
  its own waves and envelopes.
  - Pads 1-15 pick tones 1-15, SHIFT + pads 1-5 pick tones 16-20, pad 16 is OFF. VALUE steps through all of them.
  - The footer shows the tone's name.
- **The knobs:**
  - CTRL 1 is the tone's own setting. On the SG tones it picks the SG's ENV preset (Pluck, Keys, Acid, FPad...).
  - CTRL 2 (TONE) moves the filter, and CTRL 3 is LEVEL.
  - The SHIFT page has OCTAVE, SUSTAIN (how long notes ring) and DYNAMICS.
- **No effects inside the synth.** Put chorus, delay or reverb on its bus with the SP's own effects (push VALUE for OUT:
  BUS 1 or BUS 2).
- Your tone settings from tests 6-10 don't carry over, since the tones are new. Your bus setting does.

1. Volume low. On the guitar synth screen, play single notes, a bend, then chords, on a few tones.
2. Try a lead (pad 7 or 8), a bass (pads 9-11) and an SG tone (SHIFT + pads 1-5).
3. The heaviest tones are SG VOWEL and SG ORGAN (SHIFT + pads 1 and 2) and SUPERSAW (pad 12). Note if the synth ever
   goes silent by itself while you play.

Tell me: which tones sound good, and which need work? Do notes start cleanly, or do you hear wrong notes at the pick?
Does the synth ever stop on its own?
