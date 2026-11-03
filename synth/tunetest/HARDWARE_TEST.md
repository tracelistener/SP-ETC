# Note tracker test 2: does the SP hear which note you play?

A test build: {{PARENT_REVISION}} (v9.52) plus a note tracker and the CPU meter. Not for sharing. To go back, patch
v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

Nothing new comes out of the speakers: the box only shows what the SP hears. Test 1 kept taking a ringing string for
new plucks (N51 from six notes); test 2 counts a pluck only when the level jumps.

1. Volume down a bit. Guitar in, EXT SOURCE on, input FX Bypass.
2. On the main screen hold EXIT on its own for about a second: the box appears. If it was already showing, hide it
   and show it again: that zeroes AVG, N, P and MAX.
3. Play the six open strings once each, low E to high E, stopping each string with your hand before the next.
4. Read AVG, N and P. N and P should both be 6.

The box (as test 1, plus P):

    E2 +3c Q92          the note it hears, how far off in cents, how sure (Q, 100 best)
    82.4Hz LV45 X1      the frequency, your input level, EXT SOURCE
    1ST 21 LCK 27       the last pluck: ms to a first guess, ms to a steady note
    AVG 22 N6 P6        the average ms to the steady note over N notes; P plucks heard
    TRK 4/6 MIX 9       what the tracker costs (% of the processor), the mixer
    MAX 19 OVR 0        the worst moment (%), overloads

Tell me AVG, N and P after the six strings, and whether the note names were right. A photo of the box is enough.
