# IR test 1: CPU meter and a test echo

A test build: {{PARENT_REVISION}} plus a CPU meter and a quiet test echo of the input. It is for
finding out whether an amp IR or NAM could run on the SP. Not for sharing. To go back, flash v9.49.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

**Turn your volume down first.**

1. **CPU meter.** On the main screen, hold EXIT on its own for about a second; do it again to
   hide it. Write down the box's numbers with nothing playing, then while you play your busiest
   pattern (lots of pads and a drum kit) for 10 seconds.
2. **Echo.** Plug a guitar or a mic into the input, switch EXT SOURCE on and set the input FX
   to Gt Amp Sim. Play a short note: you should hear it, then one quiet echo about 0.15 s later.
   Tell me:
   - one echo, or several that fade away?
   - does the echo sound like the amp, or clean?
   - with EXT SOURCE off: does the echo still come, on its own?
   - in INPUT SETTING (SHIFT + EXT SOURCE), ROUTING on Mix and on ExtIn: what changes?

The echo is only there while the input FX is the Gt Amp Sim.

The box, all in percent of one audio block (1.33 ms):

```
MIX 23/41         the whole audio mix: average / peak
PAD 15/30 12v     the sample pads (most voices playing)
SG 6/12           the Sound Generator and drum kits
HI 3 OVR 0        blocks over 75% / over 100% (over 100% = a click)
MAX 57 CLK 600    the slowest block, and the processor's speed in MHz
```
