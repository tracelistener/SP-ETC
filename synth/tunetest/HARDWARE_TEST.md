# Guitar synth test 4: fixing test 3's stuck notes

A test build: {{PARENT_REVISION}} (v9.52) plus a guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What changed since test 3:

- No more bending. A pick the tracker missed made test 3 slide the old note instead of playing the new one.
- Picks are now heard by their click too, so a note picked again at the same strength plays again.
- When strings ring together and the tracker can't tell the note, the synth stops instead of guessing.
- Back to tests 1 and 2's octave. Set the Sound Generator's OCT to +1 to play at your guitar's pitch.
- Soft picks are a bit quieter than hard ones; less difference than in test 3.

1. Volume low at first. Guitar in, EXT SOURCE on, input FX Bypass.
2. Open the Sound Generator in melodic mode with ARP OFF. Pick one note four times in a row, evenly.
3. A melody on one string, then a melody across strings.
4. Drum mode: a riff with repeated notes.

Tell me: any stuck notes left, any wrong or missing notes, and does each repeated note play?
