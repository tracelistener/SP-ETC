# SY synth test 20: every pick attacks

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the quieter Sound Generator and kits) plus the
guitar synth. Not for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new since test 19:

- **Every pick gets its own attack on the basses and leads.** In test 19 a note picked while the one before still
  rang slid to its pitch with no attack, and a note picked again on the same pitch got none at all. On a bass line
  that sounds like a missed note. Now each pick restarts the tone's attack (the filter sweep on FAT BASS, the sync
  sweep on SYNC LEAD), repeats included.
- **No double attacks.** A pick right after a let-go could re-attack the old note first, then the new one. Gone.
- **Notes end when you let go**, as the tracker hears it, instead of ringing on a little.
- Hammer-ons and slides still glide without an attack, as before.
- Chords and the pad tones are unchanged.

1. Volume low. FAT BASS (pad 9): a bass line with repeated notes (E E G A A ...), then a chromatic run up one string.
2. SYNC LEAD (pad 7): a few phrases, some notes picked twice in a row.

Tell me: does every pick sound now? Any extra notes?
