# SY synth test 7: the synth's bus, and LEVEL for MIDI notes

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes) plus the SY synth and guitar synth test 6 on the
Sound Generator page. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **The synth's bus:** on the guitar synth screen, push VALUE to step where the synth plays: DRY, BUS 1, BUS 2, BOTH.
  The bar shows it ("OUT: BUS 2").
  - DRY is as before: the FX buttons' effects don't reach the synth.
  - On BUS 1 or BUS 2 the synth goes through that bus's effect. With Routing Type A, BUS 1 also feeds BUS 2.
  - BOTH puts half the synth on each bus (with Type B: two effects side by side).
  - Your guitar's bus is still REMAIN + EXT SOURCE (dark DRY, lit BUS 1, blinking BUS 2), so any pairing works.
- **LEVEL for MIDI notes** (combined-test18): the Sound Generator's LEVEL now turns down notes played from MIDI. The
  guitar synth's notes on the Sound Generator page follow it too.
- Everything from test 6 stays, your settings too.

1. Volume low at first. Guitar in, main screen.
2. Pick BUS 2 for the effects (BUS FX blinking) and turn on DELAY. Open the guitar synth screen and push VALUE until
   the bar shows OUT: BUS 2. Play: the synth should echo.
3. Try OUT: BUS 1 with an effect on BUS 1, and OUT: BOTH.
4. On the plain Sound Generator page, play from a MIDI keyboard and turn LEVEL down.

Tell me: does the synth get the effect on BUS 2? On BUS 1? Does LEVEL turn MIDI notes down?
