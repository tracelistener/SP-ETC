# Cabinet test 1: the Gt Amp Sim through a cab IR

A test build: {{PARENT_REVISION}} (v9.50) plus a cab IR on the input and the CPU meter. NAM did not fit, so this is the
cab-only route: the SP's own amp, your cabinet. Not for sharing. To go back, flash v9.50.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

**Turn your volume down first, and set ROUTING to ExtIn** (REC, RECORD SETTING, CTRL 2 to ExtIn, EXIT). The box's IR
line ends in S for the stand-in cabinet made from filters, or W for a WAV I was given.

1. Input FX to the Gt Amp Sim, and in its hidden pages (hold VALUE, press EXT SOURCE) turn SP SW off, its own
   speaker. Guitar in, EXT SOURCE on.
2. On the main screen hold EXIT on its own for about a second: the box appears and the cab starts. Play. You should
   hear the amp twice: as the Gt Amp Sim makes it, and through the cab (a little quieter, a hair later). Does the cab
   copy sound like the amp (distorted, if you use gain), or like your clean guitar?
3. EXT SOURCE off while it runs: does the cab copy stay while the other one goes?
   If both go quiet: EXT SOURCE back on, send the input to BUS 1 (hold REMAIN and press EXT SOURCE until it is lit),
   then turn MUTE BUS on (SHIFT + BUS FX). Does the cab copy stay now?
4. Send the box's six lines.

The box, in percent of one audio block (1.33 ms) unless said:

```
MIX 8/10 T15      the whole audio mix: average / peak; T = the worst mix + cab in one block
CAB 4/5 RUN       the cab: average / peak; OFF LOAD RUN, or BAD, SLOW
IN23 LV45 X1      the input FX's number, the input level (% of full), EXT SOURCE on (1) or off (0)
IR 1024 S         the IR's length in samples; S the stand-in, W a WAV
MAX 18 F1         the worst block since the box came on; F is for me
CLK 599 OVR 0     the processor's speed (MHz); blocks over 100% (a click) since the box came on
```

To stop the cab, hold EXIT again.
