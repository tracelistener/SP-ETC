# SY synth test 6: the screen's controls, FX screens, REMAIN, and smoother notes

A test build: {{PARENT_REVISION}} (v9.52) plus the SY synth and guitar synth test 6 on the Sound Generator page. Not
for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **The guitar synth screen** (hold EXT SOURCE, press RECORD SETTING):
  - VALUE and the pads pick the sound. CTRL 1 is now the sound's own setting (RESO, DETUNE, ATTACK...), CTRL 2 TONE
    (-50 to +50), CTRL 3 LEVEL (0-100, 50 as designed).
  - Tap SHIFT: OCTAVE, SUSTAIN and DYNAMICS. Lower DYNAMICS evens out loud and soft notes (it brings up quiet ones,
    such as the high E).
  - The bottom bar no longer shows PRM: SOUND.
- **FX screens on the synth screen:** the knobs, VALUE and SHIFT now go to the effect, so its screen stays while you
  adjust it. Holding MFX, VALUE, CTRL 3 or a pad picks the effect.
- **REMAIN on the Sound Generator page** (the synth screen, the plain Sound Generator and the kits): hold REMAIN and
  press an FX button to keep the FX screen up, as on other pages. Press REMAIN again to close it. A REMAIN tap on its
  own still changes the preview bus.
- **Smoother single notes:** the synth flickered between bands for the first 150 ms of each note (all through some
  notes). That is mostly gone. Each note now plays at the level of its loudest harmonic.
- **Kits:** every guitar note now hits a pad. The open low E is pad 1 (the kick), one pad per fret up to pad 16, and
  higher notes fold down an octave at a time.
- Your test 5 settings are kept.

1. Volume low at first. Guitar in, main screen.
2. Hold EXT SOURCE and press RECORD SETTING. Play single notes on every string, then chords. Try CTRL 1, and DYNAMICS
   on the SHIFT page.
3. Press an FX button and turn the knobs. Then hold REMAIN, press an FX button, let go, and turn the knobs.
4. On a kit (the Sound Generator page in drum mode), play notes all over the neck.

Tell me: do single notes sound better? Is the high E still too quiet? Do the FX screens and REMAIN work as you wanted?
