# NAM test 1: a NAM amp and a cabinet on the input

A test build: {{PARENT_REVISION}} (v9.50) plus a NAM amp, a cabinet and the CPU meter. It is for finding out
whether the SP can run a NAM amp itself. Not for sharing. To go back, flash v9.50.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

**Turn your volume down first.** The amp is TONE3000's example capture and the cabinet is a stand-in made from
filters, so judge whether it runs cleanly, not the tone.

1. Plug a guitar into the input, EXT SOURCE on, input FX off (Bypass). On the main screen hold EXIT on its own
   for about a second: the box appears and NAM starts (a moment of LOAD and WARM). Play.
   Hold EXIT again to stop it.
   - Do you hear the amp sound (on top of your clean guitar)? Any clicks or dropouts? Try a busy pattern too.
   - The box's first two lines while you play, for example `MIX 8/10 T44` and `NAM 30/34 RUN`.
2. Switch EXT SOURCE off while NAM runs: does the amp sound stay while the clean guitar goes?
3. Set the input FX to the Gt Amp Sim (its own SP SW hidden setting off, if you like). The box's second line
   says CAB: now the Gt Amp Sim plays through the stand-in cabinet.
4. Send a photo of the box, or its six lines.

The box, in percent of one audio block (1.33 ms) unless said:

```
MIX 8/10 T44      the whole audio mix: average / peak; T = the worst mix + NAM in one block
NAM 30/34 RUN     NAM (CAB with the Gt Amp Sim): average / peak; OFF LOAD WARM RUN, or BAD, SLOW, MEM!
IN0 LV45 X1       the input FX's number, the input level (% of full), EXT SOURCE on (1) or off (0)
POOL 2880/2800    free memory in the SP's pool (KB): in all / the biggest piece
MAX 52 D0 F1      the worst block since the box came on; D and F are for me
CLK 599 OVR 0     the processor's speed (MHz); blocks over 100% (a click) since the box came on
```

NAM SLOW 92 means NAM stopped itself because the audio got too close to full (92% of a block): tell me the
number.
MEM! means the SP had no room for it.
