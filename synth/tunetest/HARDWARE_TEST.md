# Note tracker test 1: does the SP hear which note you play?

A test build: {{PARENT_REVISION}} (v9.52) plus a note tracker and the CPU meter. Not for sharing. To go back, patch
v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

Nothing new comes out of the speakers: the box only shows what the SP hears.

1. Volume down a bit. Guitar in, EXT SOURCE on, input FX Bypass (clean is best for a start).
2. On the main screen hold EXIT on its own for about a second: the box appears (hold it again to hide it).
3. Play single notes, low E string to high frets, one at a time with a gap. Then a few with the Gt Amp Sim on.

The box:

    E2 +3c Q92        the note it hears, how far off in cents, how sure (Q, 100 best)
    82.4Hz LV45 X1    the frequency, your input level, EXT SOURCE
    1ST 21 LCK 27     the last pluck: ms to a first guess, ms to a steady note
    AVG 25 N12 IN23   the average ms to the steady note over N plucks; the input FX
    TRK 4/6 MIX 9     what the tracker costs (% of the processor), the mixer
    MAX 30 OVR 0      the worst moment (%), overloads

Tell me: does the note match what you play (low and high strings), roughly the LCK and AVG numbers, and the TRK and
MAX lines. A photo of the box is enough.
