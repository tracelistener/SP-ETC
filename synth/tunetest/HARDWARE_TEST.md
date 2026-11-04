# Guitar synth test 5: the synth checks ROUTING

A test build: {{PARENT_REVISION}} (v9.52) plus a guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What changed since test 4:

- The synth plays only when INPUT SETTING's ROUTING is ExtIn. On Mix the SP hands back everything it plays, so
  the synth heard its own note and held it.
- On the Sound Generator page with EXT SOURCE on and ROUTING on Mix, a popup says SYNTH NEEDS / ROUTING ExtIn /
  SHIFT+EXT SRC, and the synth stays silent.
- Tracking is test 4's.

1. Volume low at first. Guitar in, EXT SOURCE on, input FX Bypass.
2. SHIFT + EXT SOURCE, CTRL 2: ROUTING Mix, then EXIT. Open the Sound Generator: the popup shows, and picking plays
   nothing.
3. Set ROUTING to ExtIn the same way and go back to the Sound Generator: it plays as test 4 did.

Tell me: did the popup show on Mix, and does it play as before on ExtIn?
