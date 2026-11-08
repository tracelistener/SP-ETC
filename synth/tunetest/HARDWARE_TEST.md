# SY synth test 22: test 21's crash, found and fixed

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 21:

- **The crash is fixed.** Your SY CRASH numbers pointed at the very end of one of the synth's routines. At power-on
  the SP copies the synth's code into memory in 4-byte pieces, and that part of the code ran 2 bytes past a whole
  piece, so its last instruction, the one that returns, was never copied. The synth ran on into whatever was left in
  memory. Test 20 had the same fault, which is why it rebooted. The emulator missed it because its memory starts
  empty; the checks now copy exactly the way the SP does.
- Nothing else changes: test 20's note logic (every pick attacks) and test 21's safety net stay.

1. Volume low. FAT BASS (pad 9): a bass line with repeated notes (E E G A A ...), then a chromatic run up one string.
2. SYNC LEAD (pad 7): a few phrases, some notes picked twice in a row.
3. POLY PAD (pad 1): a few chords.

Tell me: any SY CRASH box or restart (a photo if so)? Does every pick sound? Any extra notes?
