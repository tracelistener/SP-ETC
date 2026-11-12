# Cabinet test 2: where does the SP keep your guitar?

A test build: {{PARENT_REVISION}} (v9.50) plus the cab IR, the CPU meter and new level meters. Not for sharing. To go
back, flash v9.50.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

Every audio block the effects chip hands the main processor 8 stereo signals. The cab test listened to only one of
them (the one sampling records), and on ROUTING ExtIn it was silent. This test shows all 8 levels, so we can find the
one with your guitar after the Gt Amp Sim.

**Volume down.** Input FX: the Gt Amp Sim (SP SW off, as before). Guitar in. On the main screen hold EXIT on its own
for about a second: the box appears. Then, **while you keep playing** (the numbers are the loudest moment of the last
half second), photograph the box or copy its A and B lines, in each of these:

1. ROUTING on ExtIn, EXT SOURCE on.
2. ROUTING on ExtIn, EXT SOURCE off.
3. ROUTING on Mix (REC, RECORD SETTING, CTRL 2), EXT SOURCE on.
4. If you like: Gt Amp Sim GAIN way up, then way down (EXT SOURCE on): which numbers change?

The box:

```
CAB 15/16 RUN     the cab: average / peak, in % of one audio block
IN23 LV45 X1      the input FX's number, the level the cab hears (% of full), EXT SOURCE on (1) or off (0)
A 0 45 0 0        the 8 signals' levels in % of full scale: 1 to 4 ...
B 0 0 0 0         ... and 5 to 8
MIX 10/11 T27     the SP's own audio work; T = the worst block with the cab
MAX 30 OVR 0      the worst block since the box came on; blocks over 100% (a click)
```

To stop, hold EXIT again.
