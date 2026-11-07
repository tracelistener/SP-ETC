# SY synth test 18: open strings fixed, a crash catcher, and the SY loudness law

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 17:

- **Every string plays.** Test 17 needed to see your pick, and it misses picks while other strings ring. Now a string
  counts as picked as soon as its own band jumps. Leads and basses (like FAT BASS) move to the newest string, and an
  open B or E over a ringing low E is no longer taken for one of its overtones.
- **A crash catcher.** If the SP crashes, it restarts by itself within a second instead of freezing with a tone. A few
  seconds after the restart a box shows `SY CRASH`, then PC, LR, CF and AD numbers. Take a photo of it: that tells me
  where it stopped.
- **TRACK page: LAW** (where WAIT was). OFF is test 17's loudness. 1:1 and 2:1 are the two readings of how the BOSS
  SY-1000 sets each voice's volume: 1:1 follows your picking dB for dB, and 2:1 doubles your dynamics (soft gets much
  softer). Both duck a string's neighbouring bands the SY way.

1. Volume low. FAT BASS (pad 9): pick the open strings one by one, letting them ring, then play a line.
2. A pad or keys tone: chords and single notes.
3. If you like: TRACK page (SHIFT tapped twice), turn CTRL 1 to 1:1, then 2:1, and play soft and hard.

Tell me: do all the strings sound now? Which LAW feels most like an SY? If it crashes, send the photo of the box.
