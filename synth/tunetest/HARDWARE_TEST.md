# SY synth test 21: test 20 without the reboots

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 20:

- **The reboots.** Test 20's crash catcher restarted the SP on any fault, including a harmless kind the stock firmware
  ignores. Test 21 ignores that kind too. The synth's code is back in test 19's memory places, where it never
  crashed. Every pick still attacks, as in test 20.
- **If the synth itself goes wrong, only the synth stops**, not the SP: it goes quiet and a box with **SY CRASH**
  shows. EXT SOURCE off, then open the guitar synth screen again, and it plays again.
- Any other crash still restarts the SP, and the SY CRASH box shows about 4 seconds after it boots.
- The box stays up 30 seconds. A photo of it shows me where it stopped.

1. Volume low. FAT BASS (pad 9): a bass line with repeated notes (E E G A A ...), then a chromatic run up one string.
2. SYNC LEAD (pad 7): a few phrases, some notes picked twice in a row.
3. Play as long as test 20 took to crash, or longer.

Tell me: any restart, or the synth stopping (a photo of the SY CRASH box if one shows)? Does every pick sound? Any
extra notes?
