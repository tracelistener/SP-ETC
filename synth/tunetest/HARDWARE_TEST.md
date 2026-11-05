# SY synth test 8: the synth starts from its screen

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes) plus the SY synth and guitar synth test 6 on the
Sound Generator page. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **The synth starts from its screen.** EXT SOURCE on its own now gives your dry guitar only. The guitar synth plays
  once you open its screen (hold EXT SOURCE, press RECORD SETTING), and keeps playing after EXIT, on every page, until
  you turn EXT SOURCE off. Picking OFF on the screen still turns it off.
- Everything from test 7 stays: the synth's bus (push VALUE on the screen: OUT: DRY / BUS 1 / BUS 2 / BOTH) and LEVEL
  for MIDI notes on the Sound Generator.

1. Volume low at first. Guitar in, main screen. Turn EXT SOURCE on and play: only your guitar.
2. Hold EXT SOURCE and press RECORD SETTING, play (the synth), press EXIT, play again (still the synth).
3. Turn EXT SOURCE off and on again, and play: only your guitar again.
4. Test 7's steps, if you haven't yet: the synth on BUS 2 with DELAY on BUS 2 (OUT: BUS 2), then BUS 1 and BOTH.

Tell me: does the synth stay off until you open its screen? Does the synth get the effect on BUS 2 and BUS 1?
