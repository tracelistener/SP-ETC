# IR test 1: CPU meter and a test echo

A test build: {{PARENT_REVISION}} plus a CPU meter and a quiet test echo of the input. It is for
finding out whether an amp IR or NAM could run on the SP. Not for sharing. To go back, flash v9.49.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

**Turn your volume down first.**

1. **The echo, with the meter.** Plug a guitar or a mic into the input and switch EXT SOURCE on. On the main
   screen hold EXIT on its own for about a second: the box appears, and while it shows (and EXT SOURCE is on)
   everything the SP captures comes back once, quietly, about 0.15 s later. Hold EXIT again to hide it.
   Play a short note and tell me:
   - do you hear an echo? One, or several that fade away?
   - the box's last line, for example `IN23 LV45 E1`: the number after IN, LV while you play, and E (1 = echo on).
   - in INPUT SETTING (SHIFT + EXT SOURCE), ROUTING on Mix and on ExtIn: what changes?
2. **Input FX hidden pages.** Set the input FX to Gt Amp Sim (RECORD SETTING, VALUE). Back on the main screen,
   or anywhere else, hold VALUE and press EXT SOURCE: a box `GT AMP SIM 1/4` should appear, and EXT SOURCE
   should not switch. VALUE steps the pages, CTRL 1-3 change them.

The box, in percent of one audio block (1.33 ms) unless said:

```
MIX 23/41         the whole audio mix: average / peak
PAD 15/30 12v     the sample pads (most voices playing)
SG 6/12           the Sound Generator and drum kits
HI 3 OVR 0        blocks over 75% / over 100% (over 100% = a click)
MAX 57 CLK 600    the slowest block, and the processor's speed in MHz
IN23 LV45 E1      the input FX's number, the capture's level (% of full), the echo on (1) or off (0)
```
