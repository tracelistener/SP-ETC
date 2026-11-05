# SY synth test 5: the guitar synth screen, and new sounds

A test build: {{PARENT_REVISION}} (v9.52) plus the SY synth and guitar synth test 6 on the Sound Generator page. Not
for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **The guitar synth screen:** on the main screen, hold EXT SOURCE and press RECORD SETTING. The Sound Generator's
  screen opens as the guitar synth, with the input on.
  - CTRL 1 picks the sound (all the way left is OFF), CTRL 2 is TONE, CTRL 3 is LEVEL.
  - Tap SHIFT for the second page: OCTAVE, the sound's own setting (RESO, DETUNE, ATTACK...) and SUSTAIN. Tap again to
    go back.
  - VALUE steps through the sounds. Pads 1-15 pick a sound and pad 16 turns the synth off. Pads never play samples
    here.
  - EXIT leaves. The synth keeps playing while EXT SOURCE is on, as in test 4.
- **New sounds:** each note now plays from its lowest band only, so the synth no longer copies the guitar's overtones.
  Notes hold like a synth's (SUSTAIN), some sounds are an octave down or up, and everything is 3 dB louder.
  `demos\` has each sound on a model guitar.
- VALUE + EXT SOURCE opens the input FX's hidden settings again (the picker is gone). Your test 3/4 knob settings start
  fresh, because the sounds changed.
- To hear the synth without your dry guitar: REMAIN + EXT SOURCE (lit) puts the input on BUS 1, then turn all the
  Isolator's bands down on BUS 1.

1. Volume low at first. Guitar in, main screen.
2. Hold EXT SOURCE and press RECORD SETTING. Play while you turn CTRL 1 through the sounds, tap a few pads, then tap
   SHIFT and try OCTAVE and SUSTAIN.
3. Press EXIT and play pads with the guitar.

Tell me: do the screen and its knobs work? Do the sounds stand out from the guitar now? Which ones do you like?
