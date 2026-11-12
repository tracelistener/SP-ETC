# CPU meter T0: how much audio CPU is left (hardware test)

A test-only build: {{PARENT_REVISION}} plus a CPU meter. It times the SP's audio work
every 1.33 ms block with the processor's cycle counter and shows the numbers in a popup.
**It changes no sound.** Everything else is exactly {{PARENT_REVISION}}. The numbers decide how
many pads can get pad FX (filter, EQ, SUBSONIC) next to the kits.

Not for publishing. Flash APP0 and APP1 as usual; to go back, flash {{PARENT_REVISION}} (or
the published v9.43, or stock 5.52). Never launch Roland Cloud Manager for this.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

`manifest.json` lists every patch; `SHA256SUMS.txt` the files; `test_report.json` the
emulator checks (Unicorn): the meter leaves the mix bit-identical to {{PARENT_REVISION}}.

## Show and hide the meter

On the main screen, **hold EXIT on its own for about a second.** The popup appears and
updates twice a second, on every page. Hold EXIT again on the main screen to hide it. EXIT
still does what it always does; the meter only watches how long you hold it. Showing the
meter zeroes HI, OVR and MAX, so hide and show it between tests.

```
MIX 23/41
PAD 15/30 12v
SG 6/12
HI 3 OVR 0
MAX 57 CLK 600
```

All numbers are **percent of one audio block** (64 samples, 1.33 ms). 100% means the
processor spent the whole block on audio.

| Line | Meaning |
| --- | --- |
| `MIX a/p` | the whole audio mix: average / peak over the last half second |
| `PAD a/p Nv` | the sample pads' voices (part of MIX); `N` = most voices playing in that half second (the SP plays up to 32) |
| `SG a/p` | the Sound Generator and the drum kits (part of MIX) |
| `HI n OVR n` | since you showed the meter: blocks whose mix took over 75%, and over 100% (over 100% = the audio ran out of time, a click or worse) |
| `MAX m CLK c` | the slowest block since you showed the meter (%), and the processor clock in MHz worked out from the block length: it should read **600** |

A `*` after the CLK number means the meter had to start the cycle counter itself. Tell me
if you ever see it.

## T0: the tests

Fill in the table as you go (MIX, PAD and SG as average/peak). Hide and show the meter
before each row, play for 5–10 seconds, then read it.

| # | Test | MIX | PAD | voices | SG | HI | OVR | MAX | CLK |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | idle | | | | | | | | |
| 2 | 8 voices | | | | | | | | |
| 3 | 16 voices | | | | | | | | |
| 4 | 32 voices | | | | | | | | |
| 5 | kit: 4 × TR606 cymbal | | | | | | | | |
| 6 | kit: 4 × TR808 cymbal | | | | | | | | |
| 7 | 32 voices + 4 × TR606 cymbal | | | | | | | | |

1. **Idle.** Main screen, nothing playing.
2. **8 / 16 / 32 voices.** Use a long sample (5 seconds or more). If hitting the pad
   again cuts the previous hit, turn the pad's polyphonic setting on, so each hit adds a
   voice. Hold ROLL and the pad: the `v` count on the PAD line climbs. Write a row when it
   reaches 8, 16 and 32. Hitting several long pads quickly works too.
3. **Kit, four cymbals.** SHIFT + PATTERN EDIT, VALUE to KIT, pick **TR606**. Pad 7 is the
   cymbal: hit it four times quickly so four ring at once (the kits have four voices). Then
   the same with **TR808**, pad 8. Read SG and MIX.
4. **Both together.** Get 32 voices going on the main screen with samples that keep
   playing on their own (LOOP pads, or a pattern full of long pads), then SHIFT + PATTERN
   EDIT into TR606 and hit pad 7 four times. If the voices stop when you change page, use a
   pattern for them.

## Also check

- The sound is exactly as in {{PARENT_REVISION}}: pads, kits, REC, RESAMPLE, BOUNC.
- Holding EXIT on the main screen does nothing else new. SHIFT + EXIT and EXIT on other
  pages behave as before and do not toggle the meter.
- A stock message (for example "Same EFX on other BUS") still shows; the meter waits until
  it is gone.
- DOOM OS (REMAIN + SUB PAD) opens and works as before. The meter does not draw over
  DOOM's screen; it comes back when you leave DOOM.

Report back the table, plus anything odd: a click, a freeze, a popup that won't go away.
