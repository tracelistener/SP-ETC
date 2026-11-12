# NAM test 2: the faster NAM build

A test build: {{PARENT_REVISION}} (v9.50) plus a NAM amp, a cabinet and the CPU meter. Test 1 stopped at once (NAM SLOW
109); this one does the same work in about a quarter fewer instructions and starts gently. Not for sharing. To go
back, flash v9.50.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

**Turn your volume down first, and set ROUTING to ExtIn** (REC, RECORD SETTING, CTRL 2 to ExtIn, EXIT): on Mix the
amp's own sound goes back into it and can hum. The amp is TONE3000's example capture and the cabinet a stand-in, so
judge whether it runs cleanly, not the tone.

1. Guitar in, EXT SOURCE on, input FX off. On the main screen hold EXIT on its own for about a second: the box appears
   and NAM starts. Play. Do you hear the amp? Any clicks? Send the box's six lines (they now say how fast it is even
   when it stops with SLOW).
2. Play a busy pattern while it runs: does it stay on RUN or go SLOW?
3. EXT SOURCE off while it runs: does the amp sound stay while the clean guitar goes?
4. Input FX to the Gt Amp Sim: the box says CAB, and the Gt Amp Sim plays through the stand-in cabinet.

The box, in percent of one audio block (1.33 ms) unless said:

```
MIX 8/10 T60      the whole audio mix: average / peak; T = the worst mix + NAM in one block
NAM 50/55 RUN     NAM (CAB with the Gt Amp Sim): average / peak; OFF LOAD WARM RUN, or BAD, SLOW, MEM!
IN0 LV45 X1       the input FX's number, the input level (% of full), EXT SOURCE on (1) or off (0)
POOL 2528/2528    free memory in the SP's pool (KB): in all / the biggest piece
MAX 66 F1         the worst block since the box came on; F is for me
CLK 599 OVR 0     the processor's speed (MHz); blocks over 100% (a click) since the box came on
```

SLOW means NAM stopped itself so the SP would not freeze: a block took over 100%, or over 90% twice in a row.
MEM! means the SP had no room for it. To stop NAM, hold EXIT again.
